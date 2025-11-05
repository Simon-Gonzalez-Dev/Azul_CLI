"""Retriever for query embedding and similarity search."""

import ollama
from typing import List, Dict, Any
from azul.rag.vector_db import VectorDB
from azul.config.manager import get_config_manager
from azul.formatter import get_formatter


class Retriever:
    """Handles query embedding and similarity search."""
    
    def __init__(self, vector_db: VectorDB, config):
        """Initialize retriever."""
        self.vector_db = vector_db
        self.config = config
        rag_config = config.get("rag", {})
        self.embedding_model = rag_config.get("embedding_model", "nomic-embed-text")
        self.top_k = rag_config.get("top_k_chunks", 5)
        self.formatter = get_formatter()
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using Ollama."""
        try:
            response = ollama.embeddings(
                model=self.embedding_model,
                prompt=text
            )
            if "embedding" not in response:
                raise ValueError("No embedding in response")
            return response["embedding"]
        except Exception as e:
            error_msg = str(e)
            if "not found" in error_msg.lower():
                self.formatter.print_error(f"Embedding model '{self.embedding_model}' not found.")
                self.formatter.print_info(f"Please run: ollama pull {self.embedding_model}")
                self.formatter.print_info("RAG features will be disabled. Use @rag to re-enable after pulling the model.")
            else:
                self.formatter.print_error(f"Error generating embedding: {e}")
            # Return zero vector as fallback (will result in poor matches, but won't crash)
            return [0.0] * 768  # Default embedding size
    
    def retrieve(self, query: str) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks for a query.
        
        Args:
            query: User query text
            
        Returns:
            List of chunk dicts with metadata
        """
        # Generate query embedding
        query_embedding = self._generate_embedding(query)
        
        # Search vector database
        chunks = self.vector_db.query(query_embedding, top_k=self.top_k)
        
        return chunks

