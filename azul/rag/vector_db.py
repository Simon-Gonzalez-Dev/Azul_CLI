"""Vector database wrapper for ChromaDB."""

import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)


class VectorDB:
    """Wrapper for ChromaDB vector storage."""
    
    COLLECTION_NAME = "azul_code_index"
    
    def __init__(self, index_path: Path):
        """Initialize vector database."""
        self.index_path = index_path
        self.index_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB client with persistent storage
        self.client = chromadb.PersistentClient(
            path=str(self.index_path),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        try:
            self.collection = self.client.get_collection(name=self.COLLECTION_NAME)
        except Exception:
            # Collection doesn't exist, create it
            self.collection = self.client.create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}  # Use cosine similarity
            )
    
    def add_chunks(self, chunks: List[Dict[str, Any]], embeddings: List[List[float]]) -> None:
        """
        Add chunks with embeddings to the database.
        
        Args:
            chunks: List of chunk dicts with metadata
            embeddings: List of embedding vectors
        """
        if not chunks or not embeddings:
            return
        
        # Validate chunks before storing
        valid_chunks = []
        valid_embeddings = []
        
        for chunk, embedding in zip(chunks, embeddings):
            if not chunk or not isinstance(chunk, dict):
                continue
            
            # Validate required fields
            if (chunk.get("chunk_id") and 
                chunk.get("file_path") is not None and 
                chunk.get("content") is not None and
                chunk.get("chunk_hash") is not None and
                embedding and isinstance(embedding, list)):
                valid_chunks.append(chunk)
                valid_embeddings.append(embedding)
        
        if not valid_chunks:
            return
        
        # Prepare data for ChromaDB
        ids = []
        metadatas = []
        
        for chunk in valid_chunks:
            ids.append(chunk["chunk_id"])
            metadatas.append({
                "file_path": str(chunk.get("file_path", "")),
                "start_line": int(chunk.get("start_line", 0)),
                "end_line": int(chunk.get("end_line", 0)),
                "language": str(chunk.get("language", "text")),
                "chunk_type": str(chunk.get("chunk_type", "text")),
                "chunk_hash": str(chunk.get("chunk_hash", "")),
                "content": str(chunk.get("content", ""))  # Store content for retrieval
            })
        
        # Add to collection
        try:
            # Final validation - ensure no None values in strings
            clean_ids = [str(id_val) if id_val is not None else "" for id_val in ids]
            clean_metadatas = []
            for meta in metadatas:
                clean_meta = {}
                for key, value in meta.items():
                    if value is None:
                        clean_meta[key] = ""
                    elif not isinstance(value, str):
                        clean_meta[key] = str(value)
                    else:
                        clean_meta[key] = value
                clean_metadatas.append(clean_meta)
            
            self.collection.add(
                ids=clean_ids,
                embeddings=valid_embeddings,
                metadatas=clean_metadatas
            )
            logger.info(f"Successfully stored {len(valid_chunks)} chunks in vector DB")
        except Exception as e:
            # Log error but don't crash
            logger.error(f"Error adding chunks to vector DB: {e}", exc_info=True)
    
    def query(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Query similar chunks.
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            
        Returns:
            List of chunk dicts with metadata
        """
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        # Transform results into chunk dicts
        chunks = []
        if results["ids"] and len(results["ids"][0]) > 0:
            for i in range(len(results["ids"][0])):
                chunk = {
                    "chunk_id": results["ids"][0][i],
                    "file_path": results["metadatas"][0][i]["file_path"],
                    "start_line": int(results["metadatas"][0][i]["start_line"]),
                    "end_line": int(results["metadatas"][0][i]["end_line"]),
                    "language": results["metadatas"][0][i]["language"],
                    "chunk_type": results["metadatas"][0][i]["chunk_type"],
                    "chunk_hash": results["metadatas"][0][i]["chunk_hash"],
                    "content": results["metadatas"][0][i]["content"],
                    "distance": results["distances"][0][i] if "distances" in results else None
                }
                chunks.append(chunk)
        
        return chunks
    
    def delete_chunks_by_file(self, file_path: str) -> None:
        """Delete all chunks for a specific file."""
        # Get all chunks for this file
        all_results = self.collection.get()
        
        if not all_results["ids"]:
            return
        
        # Find chunks matching file_path
        ids_to_delete = []
        for i, metadata in enumerate(all_results["metadatas"]):
            if metadata.get("file_path") == file_path:
                ids_to_delete.append(all_results["ids"][i])
        
        if ids_to_delete:
            self.collection.delete(ids=ids_to_delete)
    
    def delete_chunks_by_hash(self, chunk_hashes: List[str]) -> None:
        """Delete chunks by their hashes."""
        if not chunk_hashes:
            return
        
        # Get all chunks
        all_results = self.collection.get()
        
        if not all_results["ids"]:
            return
        
        # Find chunks matching hashes
        ids_to_delete = []
        for i, metadata in enumerate(all_results["metadatas"]):
            if metadata.get("chunk_hash") in chunk_hashes:
                ids_to_delete.append(all_results["ids"][i])
        
        if ids_to_delete:
            self.collection.delete(ids=ids_to_delete)
    
    def get_all_chunk_hashes_for_file(self, file_path: str) -> List[str]:
        """Get all chunk hashes for a specific file."""
        all_results = self.collection.get()
        
        if not all_results["ids"]:
            return []
        
        hashes = []
        for metadata in all_results["metadatas"]:
            if metadata.get("file_path") == file_path:
                hashes.append(metadata.get("chunk_hash"))
        
        return hashes
    
    def clear(self) -> None:
        """Clear all chunks from the collection."""
        try:
            self.client.delete_collection(name=self.COLLECTION_NAME)
            # Recreate collection
            self.collection = self.client.create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )
        except Exception:
            pass
    
    def count(self) -> int:
        """Get total number of chunks in the database."""
        try:
            return self.collection.count()
        except Exception:
            return 0
    
    @staticmethod
    def generate_chunk_id(file_path: str, start_line: int, end_line: int, chunk_hash: str) -> str:
        """Generate a unique chunk ID."""
        content = f"{file_path}:{start_line}:{end_line}:{chunk_hash}"
        return hashlib.md5(content.encode()).hexdigest()

