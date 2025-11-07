"""Llama client for LLM model interaction."""

from pathlib import Path
from typing import List, Dict, Optional, Iterator, Generator
import sys

try:
    from llama_cpp import Llama
except ImportError:
    print("Error: llama-cpp-python is not installed. Install with: pip install llama-cpp-python")
    sys.exit(1)


class LlamaClient:
    """Client for interacting with llama.cpp models."""
    
    # Simple mode system prompt
    SIMPLE_SYSTEM_PROMPT = """You are AZUL, an AI coding assistant. You help with coding tasks, file editing, and documentation.

FILE OPERATIONS:
1. EDITING: Provide changes as unified diff in ```diff code block
2. CREATING: Provide file content in ```file:filename code block  
3. DELETING: Indicate with ```delete:filename code block

Be concise and code-focused.
"""
    
    def __init__(self, model_path: Optional[Path] = None, n_ctx: int = 4096, n_gpu_layers: int = -1):
        """Initialize Llama client.
        
        Args:
            model_path: Path to GGUF model file
            n_ctx: Context window size in tokens
            n_gpu_layers: Number of GPU layers (-1 for all layers)
        """
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self._model: Optional[Llama] = None
        self._cached_system_prompt = self.SIMPLE_SYSTEM_PROMPT
        self._current_model_path: Optional[Path] = None
    
    def _load_model(self):
        """Load the model if not already loaded."""
        if self._model is not None and self._current_model_path == self.model_path:
            return
        
        if self.model_path is None:
            raise ValueError("Model path not set. Please provide a model path.")
        
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model file not found: {self.model_path}")
        
        # Unload previous model if different
        if self._model is not None and self._current_model_path != self.model_path:
            del self._model
            self._model = None
        
        # Load new model
        try:
            self._model = Llama(
                model_path=str(self.model_path),
                n_ctx=self.n_ctx,
                n_threads=None,  # Auto-detect CPU cores
                n_gpu_layers=self.n_gpu_layers,
                n_batch=512,
                verbose=False,
                use_mlock=True,
                use_mmap=True,
                n_threads_batch=None,
            )
            self._current_model_path = self.model_path
        except Exception as e:
            raise RuntimeError(f"Failed to load model: {e}")
    
    def ensure_loaded(self):
        """Ensure model is loaded (lazy loading)."""
        if self._model is None:
            self._load_model()
    
    def build_prompt(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Build formatted prompt using Qwen chat template.
        
        Args:
            user_message: Current user input
            conversation_history: List of previous messages (optional)
            system_prompt: System prompt override (optional)
            
        Returns:
            Formatted prompt string
        """
        if system_prompt is None:
            system_prompt = self._cached_system_prompt
        
        # Pre-compute format strings for efficiency
        im_start = "<|im_start|>"
        im_end = "<|im_end|>"
        system_start = f"{im_start}system\n"
        user_start = f"{im_start}user\n"
        assistant_start = f"{im_start}assistant\n"
        
        # Build prompt using list for efficiency
        prompt_parts = []
        
        # System prompt
        prompt_parts.append(system_start)
        prompt_parts.append(system_prompt)
        prompt_parts.append(im_end)
        prompt_parts.append("\n")
        
        # Conversation history
        if conversation_history:
            for message in conversation_history:
                role = message.get("role", "user")
                content = message.get("content", "")
                
                if role == "user":
                    prompt_parts.append(user_start)
                    prompt_parts.append(content)
                    prompt_parts.append(im_end)
                    prompt_parts.append("\n")
                elif role == "assistant":
                    prompt_parts.append(assistant_start)
                    prompt_parts.append(content)
                    prompt_parts.append(im_end)
                    prompt_parts.append("\n")
        
        # Current user message
        prompt_parts.append(user_start)
        prompt_parts.append(user_message)
        prompt_parts.append(im_end)
        prompt_parts.append("\n")
        
        # Assistant response start
        prompt_parts.append(assistant_start)
        
        return "".join(prompt_parts)
    
    def stream_chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
        repeat_penalty: float = 1.1,
    ) -> Generator[str, None, None]:
        """Stream chat response from model.
        
        Args:
            user_message: User input message
            conversation_history: Previous conversation messages
            system_prompt: System prompt override
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            repeat_penalty: Repetition penalty
            
        Yields:
            Token strings as they are generated
        """
        self.ensure_loaded()
        
        if self._model is None:
            yield "Error: Model not loaded"
            return
        
        # Build prompt
        prompt = self.build_prompt(user_message, conversation_history, system_prompt)
        
        # Generate response
        try:
            stream = self._model(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                repeat_penalty=repeat_penalty,
                stream=True,
                stop=["<|im_end|>", "<|im_start|>", "User:", "System:", "<|endoftext|>"],
            )
            
            for chunk in stream:
                if "choices" in chunk and len(chunk["choices"]) > 0:
                    delta = chunk["choices"][0].get("delta", {})
                    text = delta.get("text", "")
                    if text:
                        yield text
        except Exception as e:
            yield f"Error: {str(e)}"
    
    def chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.9,
        repeat_penalty: float = 1.1,
    ) -> str:
        """Get complete chat response (non-streaming).
        
        Args:
            user_message: User input message
            conversation_history: Previous conversation messages
            system_prompt: System prompt override
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            repeat_penalty: Repetition penalty
            
        Returns:
            Complete response string
        """
        return "".join(self.stream_chat(
            user_message, conversation_history, system_prompt,
            max_tokens, temperature, top_p, repeat_penalty
        ))
    
    def set_system_prompt(self, system_prompt: str):
        """Set system prompt."""
        self._cached_system_prompt = system_prompt
    
    def get_system_prompt(self) -> str:
        """Get current system prompt."""
        return self._cached_system_prompt
    
    def unload_model(self):
        """Unload the model to free memory."""
        if self._model is not None:
            del self._model
            self._model = None
            self._current_model_path = None

