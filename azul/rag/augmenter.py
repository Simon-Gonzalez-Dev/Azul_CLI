"""Augmenter for context assembly and prompt engineering."""

import tiktoken
from typing import List, Dict, Any, Optional
from azul.config.manager import get_config_manager


class Augmenter:
    """Assembles context from retrieved chunks."""
    
    def __init__(self, config):
        """Initialize augmenter."""
        self.config = config
        self.context_window = config.get("context_window_size", 4096)
        
        # Initialize tokenizer
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self.tokenizer = None
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        # Fallback: approximate 1 token = 4 characters
        return len(text) // 4
    
    def _deduplicate_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate chunks."""
        seen_hashes = set()
        unique_chunks = []
        
        for chunk in chunks:
            chunk_hash = chunk.get("chunk_hash")
            if chunk_hash and chunk_hash not in seen_hashes:
                seen_hashes.add(chunk_hash)
                unique_chunks.append(chunk)
            elif not chunk_hash:
                # If no hash, compare by content
                content = chunk.get("content", "")
                if content not in seen_hashes:
                    seen_hashes.add(content)
                    unique_chunks.append(chunk)
        
        return unique_chunks
    
    def _format_chunk(self, chunk: Dict[str, Any]) -> str:
        """Format a chunk with file citation."""
        file_path = chunk.get("file_path", "unknown")
        start_line = chunk.get("start_line", 0)
        end_line = chunk.get("end_line", 0)
        content = chunk.get("content", "")
        
        return f"--- Relevant Code from {file_path}:{start_line} ---\n{content}\n"
    
    def augment(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Augment prompt with retrieved context.
        
        Args:
            query: Original user query
            chunks: Retrieved chunks
            conversation_history: Optional conversation history
            
        Returns:
            Augmented prompt string
        """
        # Deduplicate chunks
        chunks = self._deduplicate_chunks(chunks)
        
        # Build context section
        context_parts = []
        context_tokens = 0
        
        # Reserve tokens for system prompt, query, and conversation history
        reserved_tokens = 500  # Approximate
        available_tokens = self.context_window - reserved_tokens
        
        # Add chunks until we hit token limit
        for chunk in chunks:
            formatted_chunk = self._format_chunk(chunk)
            chunk_tokens = self._count_tokens(formatted_chunk)
            
            if context_tokens + chunk_tokens <= available_tokens:
                context_parts.append(formatted_chunk)
                context_tokens += chunk_tokens
            else:
                # Try to fit partial chunk
                remaining_tokens = available_tokens - context_tokens
                if remaining_tokens > 100:  # Only if meaningful space left
                    # Truncate chunk content
                    content = chunk.get("content", "")
                    if not content:
                        break
                    lines = content.split("\n")
                    truncated = []
                    current_tokens = self._count_tokens(f"--- Relevant Code from {chunk.get('file_path', 'unknown')}:{chunk.get('start_line', 0)} ---\n")
                    
                    for line in lines:
                        if line is None:
                            continue
                        line_tokens = self._count_tokens(str(line) + "\n")
                        if current_tokens + line_tokens <= remaining_tokens:
                            truncated.append(str(line))
                            current_tokens += line_tokens
                        else:
                            break
                    
                    if truncated:
                        # Filter None values before joining
                        truncated_clean = [line for line in truncated if line is not None]
                        if truncated_clean:
                            partial_content = "\n".join(truncated_clean)
                            context_parts.append(
                                f"--- Relevant Code from {chunk.get('file_path', 'unknown')}:{chunk.get('start_line', 0)} (truncated) ---\n{partial_content}\n"
                            )
                break
        
        # Assemble context - filter None values
        if context_parts:
            context_parts_clean = [part for part in context_parts if part is not None]
            if context_parts_clean:
                context = "\n".join(context_parts_clean)
            else:
                context = ""
            
            # Build augmented prompt
            # Structure: System Prompt → Code Context → Conversation History → User Prompt
            augmented = f"{context}\n\nUser: {query}\n\nAssistant:"
        else:
            # No context available, return original query
            augmented = query
        
        return augmented

