"""LLM client using llama-cpp-python."""

import logging
from pathlib import Path
from typing import Generator, Optional
from llama_cpp import Llama

from .config import config

logger = logging.getLogger(__name__)


class LlamaClient:
    """Client for llama-cpp-python with Qwen chat template support."""
    
    def __init__(
        self,
        model_path: Optional[Path] = None,
        n_ctx: Optional[int] = None,
        n_gpu_layers: Optional[int] = None,
        n_batch: Optional[int] = None,
        verbose: bool = False
    ):
        """Initialize the LLM client.
        
        Args:
            model_path: Path to GGUF model file
            n_ctx: Context window size
            n_gpu_layers: Number of GPU layers (-1 for all)
            n_batch: Batch size for processing
            verbose: Enable verbose logging
        """
        self.model_path = model_path or config.model_path
        self.n_ctx = n_ctx or config.n_ctx
        self.n_gpu_layers = n_gpu_layers if n_gpu_layers is not None else config.n_gpu_layers
        self.n_batch = n_batch or config.n_batch
        self.verbose = verbose
        
        self._llm: Optional[Llama] = None
        
    def _ensure_loaded(self):
        """Lazy load the model."""
        if self._llm is None:
            logger.info(f"Loading model from {self.model_path}")
            if not self.model_path.exists():
                raise FileNotFoundError(f"Model not found at {self.model_path}")
            
            self._llm = Llama(
                model_path=str(self.model_path),
                n_ctx=self.n_ctx,
                n_gpu_layers=self.n_gpu_layers,
                n_batch=self.n_batch,
                verbose=self.verbose,
                chat_format="chatml"  # Qwen uses ChatML format
            )
            logger.info("Model loaded successfully")
    
    def chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        repeat_penalty: Optional[float] = None,
        stop: Optional[list[str]] = None
    ) -> str:
        """Generate a chat completion.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling threshold
            repeat_penalty: Repetition penalty
            stop: Stop sequences
            
        Returns:
            Generated text
        """
        self._ensure_loaded()
        
        response = self._llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens or config.max_tokens,
            temperature=temperature or config.temperature,
            top_p=top_p or config.top_p,
            repeat_penalty=repeat_penalty or config.repeat_penalty,
            stop=stop or []
        )
        
        return response["choices"][0]["message"]["content"]
    
    def stream_chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        repeat_penalty: Optional[float] = None,
        stop: Optional[list[str]] = None
    ) -> Generator[str, None, None]:
        """Generate a streaming chat completion.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling threshold
            repeat_penalty: Repetition penalty
            stop: Stop sequences
            
        Yields:
            Generated text chunks
        """
        self._ensure_loaded()
        
        stream = self._llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens or config.max_tokens,
            temperature=temperature or config.temperature,
            top_p=top_p or config.top_p,
            repeat_penalty=repeat_penalty or config.repeat_penalty,
            stop=stop or [],
            stream=True
        )
        
        for chunk in stream:
            if "choices" in chunk and len(chunk["choices"]) > 0:
                delta = chunk["choices"][0].get("delta", {})
                if "content" in delta:
                    yield delta["content"]
    
    def unload(self):
        """Unload the model from memory."""
        if self._llm is not None:
            del self._llm
            self._llm = None
            logger.info("Model unloaded")

