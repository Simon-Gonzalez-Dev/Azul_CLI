"""Metrics tracking for performance monitoring."""

import time
import tiktoken
from typing import Dict, Optional


class MetricsTracker:
    """Tracks performance metrics for a single query."""
    
    def __init__(self):
        """Initialize metrics tracker."""
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception:
            # Fallback if tiktoken fails
            self.tokenizer = None
        
        self.prompt_tokens = 0
        self.generated_tokens = 0
        self.start_time: Optional[float] = None
        self.first_token_time: Optional[float] = None
        self.end_time: Optional[float] = None
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if self.tokenizer:
            try:
                return len(self.tokenizer.encode(text))
            except Exception:
                pass
        # Fallback: approximate 1 token = 4 characters
        return len(text) // 4
    
    def start(self, prompt: str) -> None:
        """
        Call this right before sending the prompt to the model.
        
        Args:
            prompt: The full prompt being sent (including history)
        """
        self.start_time = time.monotonic()
        self.prompt_tokens = self._count_tokens(prompt)
    
    def record_first_token(self) -> None:
        """Call this as soon as the first token arrives from the stream."""
        if self.first_token_time is None:
            self.first_token_time = time.monotonic()
    
    def record_completion(self, full_response: str) -> None:
        """
        Call this after the entire response is received.
        
        Args:
            full_response: The complete response text
        """
        self.end_time = time.monotonic()
        self.generated_tokens = self._count_tokens(full_response)
    
    def get_stats(self) -> Dict[str, float]:
        """
        Calculate and return the final metrics.
        
        Returns:
            Dictionary with performance metrics, or empty dict if not all stages recorded
        """
        if self.start_time is None or self.end_time is None:
            return {}  # Not all stages were recorded
        
        # Calculate TTFT (Time To First Token) in milliseconds
        ttft_ms = 0.0
        if self.first_token_time:
            ttft_ms = (self.first_token_time - self.start_time) * 1000
        
        # Calculate generation time (time from first token to completion)
        generation_time = 0.0
        if self.first_token_time:
            generation_time = self.end_time - self.first_token_time
        
        # Calculate tokens per second
        tokens_per_second = 0.0
        if generation_time > 0:
            tokens_per_second = self.generated_tokens / generation_time
        
        return {
            "ttft_ms": ttft_ms,
            "generation_time_s": generation_time,
            "prompt_tokens": float(self.prompt_tokens),
            "output_tokens": float(self.generated_tokens),
            "tokens_per_second": tokens_per_second
        }

