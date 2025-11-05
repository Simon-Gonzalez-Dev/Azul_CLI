"""RAG (Retrieval-Augmented Generation) pipeline for AZUL CLI."""

from pathlib import Path
from typing import Optional

from azul.rag.vector_db import VectorDB
from azul.rag.indexer import Indexer
from azul.rag.chunker import Chunker
from azul.rag.retriever import Retriever
from azul.rag.augmenter import Augmenter
from azul.rag.metrics import MetricsCollector
from azul.config.manager import get_config_manager

__all__ = ['RAGManager', 'get_rag_manager', 'reset_rag_manager']


class RAGManager:
    """Orchestrates the entire RAG pipeline."""
    
    def __init__(self, project_root: Path):
        """Initialize RAG manager."""
        self.project_root = project_root
        self.index_path = project_root / ".azul_index"
        self.config = get_config_manager()
        
        # Initialize components
        self.vector_db = VectorDB(self.index_path)
        self.chunker = Chunker(self.config)
        self.indexer = Indexer(self.project_root, self.vector_db, self.chunker, self.config)
        self.retriever = Retriever(self.vector_db, self.config)
        self.augmenter = Augmenter(self.config)
        self.metrics = MetricsCollector()
        
        # Session state (per session, defaults from config)
        # Check if embedding model is available before enabling RAG
        rag_config = self.config.get("rag", {})
        default_enabled = rag_config.get("enabled_by_default", True)
        
        # Verify embedding model exists
        if default_enabled:
            try:
                import ollama
                models = ollama.list()
                local_models = [m["name"] for m in models.get("models", [])]
                embedding_model = rag_config.get("embedding_model", "nomic-embed-text")
                if embedding_model not in local_models:
                    default_enabled = False
            except Exception:
                default_enabled = False
        
        self.rag_enabled = default_enabled
        self.stats_enabled = self.config.get("stats", {}).get("show_by_default", True)
        
        # Check if index exists
        self._index_exists = self.index_path.exists() and (self.index_path / "chroma.sqlite3").exists()
    
    def index_exists(self) -> bool:
        """Check if index exists for current project."""
        return self._index_exists
    
    def toggle_rag(self) -> bool:
        """Toggle RAG on/off. Returns new state."""
        self.rag_enabled = not self.rag_enabled
        return self.rag_enabled
    
    def set_rag(self, enabled: bool) -> None:
        """Set RAG enabled state."""
        self.rag_enabled = enabled
    
    def toggle_stats(self) -> bool:
        """Toggle stats display on/off. Returns new state."""
        self.stats_enabled = not self.stats_enabled
        return self.stats_enabled
    
    def set_stats(self, enabled: bool) -> None:
        """Set stats display state."""
        self.stats_enabled = enabled
    
    def index(self, clean: bool = False) -> dict:
        """Index the project. Returns indexing metrics."""
        if clean:
            # Delete existing index
            if self.index_path.exists():
                import shutil
                shutil.rmtree(self.index_path)
            self._index_exists = False
        
        metrics = self.indexer.index(clean=clean)
        self._index_exists = True
        return metrics
    
    def retrieve_and_augment(self, query: str, conversation_history: list) -> tuple[str, dict]:
        """
        Retrieve relevant chunks and augment prompt.
        
        Returns:
            Tuple of (augmented_prompt, metrics_dict)
        """
        if not self.rag_enabled or not self._index_exists:
            return query, {}
        
        # Start metrics collection
        self.metrics.start_query()
        
        # Retrieve chunks
        chunks = self.retriever.retrieve(query)
        self.metrics.record_retrieval(len(chunks))
        self.metrics.record_retrieval_end(chunks)
        
        # Augment prompt
        augmented_prompt = self.augmenter.augment(query, chunks, conversation_history)
        
        # Record input tokens
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        input_tokens = len(enc.encode(augmented_prompt))
        self.metrics.record_input_tokens(input_tokens)
        
        return augmented_prompt, self.metrics.get_query_metrics()
    
    def get_stats_display(self) -> Optional[str]:
        """Get formatted stats display string if stats are enabled."""
        if not self.stats_enabled:
            return None
        
        metrics = self.metrics.get_query_metrics()
        if not metrics:
            return None
        
        # Format: 📊 [Latency: 3.5s | Performance: 85.2 tok/s | Context: 5 chunks from 3 files]
        latency = metrics.get("total_time", 0)
        tokens_per_sec = metrics.get("tokens_per_second", 0)
        chunks_count = metrics.get("retrieved_chunks", 0)
        files_count = metrics.get("source_files", 0)
        
        return f"📊 [Latency: {latency:.1f}s | Performance: {tokens_per_sec:.1f} tok/s | Context: {chunks_count} chunks from {files_count} files]"
    
    def record_ttft(self, ttft_ms: float) -> None:
        """Record time to first token."""
        self.metrics.record_ttft(ttft_ms)
    
    def record_generation(self, output_tokens: int, generation_time: float) -> None:
        """Record generation metrics."""
        self.metrics.record_generation(output_tokens, generation_time)
        self.metrics.end_query()
    
    def update_index_on_file_change(self, file_path: str) -> None:
        """Update index when a file changes."""
        if not self._index_exists or not self.rag_enabled:
            return
        
        # Trigger incremental re-index for this file
        self.indexer.update_file(file_path)


# Global RAG manager instance (per project)
_rag_manager: Optional[RAGManager] = None


def get_rag_manager(project_root: Optional[Path] = None) -> Optional[RAGManager]:
    """Get the global RAG manager instance."""
    global _rag_manager
    if project_root is not None:
        if _rag_manager is None or _rag_manager.project_root != project_root:
            _rag_manager = RAGManager(project_root)
    return _rag_manager


def reset_rag_manager() -> None:
    """Reset the global RAG manager (for @cd)."""
    global _rag_manager
    _rag_manager = None

