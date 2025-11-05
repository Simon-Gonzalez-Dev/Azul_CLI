"""Metrics collection for RAG pipeline performance."""

import time
import psutil
import os
from typing import Dict, Any, Optional
from pathlib import Path


class MetricsCollector:
    """Collects performance metrics for indexing and queries."""
    
    def __init__(self):
        """Initialize metrics collector."""
        self.reset()
        self._indexing_start_time: Optional[float] = None
        self._indexing_peak_ram_mb: float = 0.0
    
    def reset(self) -> None:
        """Reset all metrics."""
        self.query_start_time: Optional[float] = None
        self.retrieval_start_time: Optional[float] = None
        self.retrieval_end_time: Optional[float] = None
        self.ttft_start_time: Optional[float] = None
        self.generation_start_time: Optional[float] = None
        
        self.total_time: float = 0.0
        self.retrieval_time: float = 0.0
        self.ttft_ms: float = 0.0
        self.generation_time: float = 0.0
        
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.retrieved_chunks: int = 0
        self.source_files: int = 0
        
        self._peak_ram_mb: float = 0.0
        self._process = psutil.Process(os.getpid())
    
    def start_query(self) -> None:
        """Start timing a query."""
        self.reset()
        self.query_start_time = time.time()
        self._update_peak_ram()
    
    def start_retrieval(self) -> None:
        """Start timing retrieval (call before generating query embedding)."""
        if self.query_start_time:
            self.retrieval_start_time = time.time()
    
    def record_retrieval(self, chunks_count: int) -> None:
        """Record retrieval metrics (chunks count)."""
        self.retrieved_chunks = chunks_count
        # Count unique source files
        # This will be updated when we have the actual chunks
        self.source_files = chunks_count  # Approximate, will be refined
    
    def record_retrieval_end(self, chunks: list) -> None:
        """Record end of retrieval and count unique files."""
        if self.retrieval_start_time:
            self.retrieval_end_time = time.time()
            self.retrieval_time = (self.retrieval_end_time - self.retrieval_start_time) * 1000  # ms
        
        # Count unique source files from chunks
        if chunks:
            unique_files = set(chunk.get("file_path") for chunk in chunks if chunk.get("file_path"))
            self.source_files = len(unique_files)
    
    def record_input_tokens(self, tokens: int) -> None:
        """Record input token count."""
        self.input_tokens = tokens
    
    def start_ttft(self) -> None:
        """Start timing TTFT (call when prompt is sent to LLM)."""
        self.ttft_start_time = time.time()
    
    def record_ttft(self, ttft_ms: float) -> None:
        """Record time to first token."""
        self.ttft_ms = ttft_ms
        if self.ttft_start_time:
            self.generation_start_time = time.time()
    
    def record_generation(self, output_tokens: int, generation_time: float) -> None:
        """Record generation metrics."""
        self.output_tokens = output_tokens
        self.generation_time = generation_time
    
    def start_indexing(self) -> None:
        """Start timing indexing process."""
        self._indexing_start_time = time.time()
        self._indexing_peak_ram_mb = 0.0
        self._update_peak_ram()
    
    def end_query(self) -> None:
        """End query timing and calculate final metrics."""
        if self.query_start_time:
            self.total_time = time.time() - self.query_start_time
        self._update_peak_ram()
    
    def _update_peak_ram(self) -> None:
        """Update peak RAM usage."""
        try:
            ram_mb = self._process.memory_info().rss / 1024 / 1024
            if ram_mb > self._peak_ram_mb:
                self._peak_ram_mb = ram_mb
        except Exception:
            pass
    
    def get_query_metrics(self) -> Dict[str, Any]:
        """Get current query metrics."""
        tokens_per_second = 0.0
        if self.generation_time > 0 and self.output_tokens > 0:
            tokens_per_second = self.output_tokens / self.generation_time
        
        return {
            "total_time": self.total_time,
            "retrieval_time": self.retrieval_time,
            "ttft_ms": self.ttft_ms,
            "generation_time": self.generation_time,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "retrieved_chunks": self.retrieved_chunks,
            "source_files": self.source_files,
            "tokens_per_second": tokens_per_second,
            "peak_ram_mb": self._peak_ram_mb,
        }
    
    def get_indexing_metrics(
        self,
        indexing_time: float,
        files_indexed: list,
        chunks_created: int,
        index_path: Path
    ) -> Dict[str, Any]:
        """Get indexing metrics."""
        # Calculate index size
        index_size_mb = 0.0
        if index_path.exists():
            try:
                total_size = sum(
                    f.stat().st_size for f in index_path.rglob('*') if f.is_file()
                )
                index_size_mb = total_size / 1024 / 1024
            except Exception:
                pass
        
        # Get peak RAM (use indexing-specific if available, otherwise query peak)
        peak_ram = self._indexing_peak_ram_mb if self._indexing_peak_ram_mb > 0 else self._peak_ram_mb
        self._update_peak_ram()
        if self._peak_ram_mb > peak_ram:
            peak_ram = self._peak_ram_mb
        
        # Try to get VRAM info (optional)
        peak_vram_mb = self._get_vram_usage()
        
        return {
            "indexing_time": indexing_time,
            "files_indexed": len(files_indexed),
            "files_list": files_indexed[:10],  # First 10 files
            "chunks_created": chunks_created,
            "index_size_mb": index_size_mb,
            "peak_ram_mb": peak_ram,
            "peak_vram_mb": peak_vram_mb,
        }
    
    def _get_vram_usage(self) -> Optional[float]:
        """Attempt to get VRAM usage in MB. Returns None if not available."""
        try:
            # Try nvidia-ml-py first (if available)
            try:
                import pynvml
                pynvml.nvmlInit()
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                return info.used / 1024 / 1024  # Convert to MB
            except ImportError:
                pass
            except Exception:
                pass
            
            # Try querying Ollama API for GPU info
            try:
                import ollama
                # Ollama doesn't directly expose GPU memory, but we can try
                # This is a placeholder - actual implementation would need Ollama API support
                pass
            except Exception:
                pass
            
            # Return None if no method available
            return None
        except Exception:
            return None
    
    def update_indexing_ram(self) -> None:
        """Update peak RAM during indexing."""
        try:
            ram_mb = self._process.memory_info().rss / 1024 / 1024
            if ram_mb > self._indexing_peak_ram_mb:
                self._indexing_peak_ram_mb = ram_mb
            if ram_mb > self._peak_ram_mb:
                self._peak_ram_mb = ram_mb
        except Exception:
            pass

