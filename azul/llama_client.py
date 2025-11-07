"""LLM client wrapper for llama-cpp-python."""

import time
from pathlib import Path
from typing import Dict, Generator, List, Optional, Tuple
from llama_cpp import Llama


class LlamaClient:
    """Direct interface to llama-cpp-python for local model inference."""
    
    def __init__(
        self,
        model_path: Path,
        n_ctx: int = 8192,
        n_gpu_layers: int = -1
    ):
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self._model: Optional[Llama] = None
    
    @property
    def model(self) -> Llama:
        """Lazy load the model."""
        if self._model is None:
            # Suppress llama.cpp verbose output
            import os
            import sys
            from io import StringIO
            
            # Redirect stderr temporarily to suppress verbose output
            old_stderr = sys.stderr
            sys.stderr = StringIO()
            
            try:
                self._model = Llama(
                    model_path=str(self.model_path),
                    n_ctx=self.n_ctx,
                    n_gpu_layers=self.n_gpu_layers,
                    n_batch=512,
                    use_mmap=True,
                    verbose=False,
                    logits_all=False
                )
            finally:
                sys.stderr = old_stderr
        
        return self._model
    
    def _format_qwen_messages(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None
    ) -> str:
        """Format messages using Qwen chat template."""
        formatted_parts = []
        
        if system_prompt:
            formatted_parts.append(f"<|im_start|>system\n{system_prompt}<|im_end|>\n")
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                formatted_parts.append(f"<|im_start|>system\n{content}<|im_end|>\n")
            elif role == "user":
                formatted_parts.append(f"<|im_start|>user\n{content}<|im_end|>\n")
            elif role == "assistant":
                formatted_parts.append(f"<|im_start|>assistant\n{content}<|im_end|>\n")
        
        # Add assistant prompt for response
        formatted_parts.append("<|im_start|>assistant\n")
        
        return "".join(formatted_parts)
    
    def _trim_history(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Trim conversation history to fit context window."""
        # Simple strategy: keep last 10 messages
        if len(messages) > 10:
            return messages[-10:]
        return messages
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation: ~4 characters per token."""
        return len(text) // 4
    
    def chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
        top_p: float = 0.9,
        repeat_penalty: float = 1.1
    ) -> Tuple[str, Dict[str, float]]:
        """Generate a chat response with stats."""
        messages = conversation_history or []
        messages.append({"role": "user", "content": user_message})
        
        # Trim history if needed
        messages = self._trim_history(messages, system_prompt)
        
        # Format prompt
        prompt = self._format_qwen_messages(messages, system_prompt)
        
        # Estimate input tokens
        input_tokens = self._estimate_tokens(prompt)
        
        # Generate response with timing
        start_time = time.time()
        response = self.model(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            repeat_penalty=repeat_penalty,
            stop=["<|im_end|>", "<|im_start|>"],
            echo=False
        )
        elapsed_time = time.time() - start_time
        
        output_text = response["choices"][0]["text"].strip()
        output_tokens = self._estimate_tokens(output_text)
        
        # Calculate tokens per second
        tokens_per_sec = output_tokens / elapsed_time if elapsed_time > 0 else 0
        
        stats = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "tokens_per_second": tokens_per_sec,
            "generation_time": elapsed_time
        }
        
        return output_text, stats
    
    def stream_chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
        top_p: float = 0.9,
        repeat_penalty: float = 1.1
    ) -> Generator[Tuple[str, Optional[Dict[str, float]]], None, None]:
        """Stream chat response tokens with stats."""
        messages = conversation_history or []
        messages.append({"role": "user", "content": user_message})
        
        # Trim history if needed
        messages = self._trim_history(messages, system_prompt)
        
        # Format prompt
        prompt = self._format_qwen_messages(messages, system_prompt)
        
        # Estimate input tokens
        input_tokens = self._estimate_tokens(prompt)
        
        # Stream response with timing
        start_time = time.time()
        full_text = ""
        
        stream = self.model(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            repeat_penalty=repeat_penalty,
            stop=["<|im_end|>", "<|im_start|>"],
            echo=False,
            stream=True
        )
        
        for chunk in stream:
            if "choices" in chunk and len(chunk["choices"]) > 0:
                delta = chunk["choices"][0].get("text", "")
                if delta:
                    full_text += delta
                    yield delta, None
        
        # Calculate final stats
        elapsed_time = time.time() - start_time
        output_tokens = self._estimate_tokens(full_text)
        tokens_per_sec = output_tokens / elapsed_time if elapsed_time > 0 else 0
        
        stats = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "tokens_per_second": tokens_per_sec,
            "generation_time": elapsed_time
        }
        
        # Yield final stats
        yield "", stats

