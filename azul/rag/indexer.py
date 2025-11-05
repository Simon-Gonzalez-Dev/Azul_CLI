"""Indexer for file discovery, chunking, embedding, and storage."""

import hashlib
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import ollama
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TaskID

from azul.rag.vector_db import VectorDB
from azul.rag.chunker import Chunker
from azul.rag.metrics import MetricsCollector
from azul.config.manager import get_config_manager
from azul.file_handler import get_file_handler
from azul.formatter import get_formatter

logger = logging.getLogger(__name__)


class Indexer:
    """Handles indexing of codebase."""
    
    def __init__(self, project_root: Path, vector_db: VectorDB, chunker: Chunker, config):
        """Initialize indexer."""
        self.project_root = project_root
        self.vector_db = vector_db
        self.chunker = chunker
        self.config = config
        self.file_handler = get_file_handler()
        self.formatter = get_formatter()
        
        rag_config = config.get("rag", {})
        self.embedding_model = rag_config.get("embedding_model", "nomic-embed-text")
        self.batch_size = rag_config.get("embedding_batch_size", 10)
        
        # Try to import gitignore parser
        try:
            import gitignore_parser
            self.gitignore_parser = gitignore_parser
        except ImportError:
            self.gitignore_parser = None
    
    def _should_index_file(self, file_path: Path) -> bool:
        """Check if a file should be indexed."""
        # Skip hidden files
        if any(part.startswith('.') for part in file_path.parts):
            return False
        
        # Skip binary files
        if self.file_handler.is_binary_file(file_path):
            return False
        
        # Skip large files
        if self.file_handler.is_file_too_large(file_path):
            return False
        
        # Check file extensions (configurable)
        code_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs',
            '.cpp', '.c', '.h', '.hpp', '.cs', '.rb', '.php', '.swift',
            '.kt', '.scala', '.sh', '.bash', '.zsh', '.yaml', '.yml',
            '.json', '.xml', '.html', '.css', '.scss', '.md', '.rst',
            '.toml', '.ini', '.conf', '.sql', '.r', '.m', '.lua', '.pl',
            '.txt'  # Add .txt files
        }
        
        if file_path.suffix.lower() not in code_extensions:
            return False
        
        return True
    
    def _is_ignored_by_gitignore(self, file_path: Path) -> bool:
        """Check if file is ignored by .gitignore."""
        if not self.gitignore_parser:
            return False
        
        # Find .gitignore files
        gitignore_paths = []
        current = file_path.parent
        while current != self.project_root.parent:
            gitignore = current / ".gitignore"
            if gitignore.exists():
                gitignore_paths.append(gitignore)
            current = current.parent
        
        # Check against all .gitignore files
        for gitignore_path in reversed(gitignore_paths):  # More specific first
            try:
                with open(gitignore_path, 'r') as f:
                    patterns = self.gitignore_parser.parse_gitignore(f)
                    rel_path = file_path.relative_to(gitignore_path.parent)
                    if patterns(str(rel_path)):
                        return True
            except Exception:
                pass
        
        return False
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Calculate MD5 hash of file content."""
        try:
            content, _ = self.file_handler.read_file(str(file_path))
            if content:
                return hashlib.md5(content.encode()).hexdigest()
        except Exception:
            pass
        return ""
    
    def discover_files(self) -> List[Path]:
        """Discover all files to index."""
        files = []
        
        for file_path in self.project_root.rglob('*'):
            if file_path.is_file():
                # Skip .azul_index directory
                if '.azul_index' in file_path.parts:
                    continue
                
                # Check if should index
                if not self._should_index_file(file_path):
                    continue
                
                # Check gitignore
                if self._is_ignored_by_gitignore(file_path):
                    continue
                
                files.append(file_path)
        
        return files
    
    def _generate_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embeddings for a batch of texts.
        
        Returns:
            List of embeddings (or None if embedding generation failed for that text)
            Maintains 1:1 correspondence with input texts
        """
        embeddings = []
        model_error_shown = False
        
        for text in texts:
            # Validate text - ensure it's not empty or whitespace only
            if not text or not isinstance(text, str) or not text.strip():
                # Return None for invalid texts to maintain mapping
                logger.debug(f"Skipping empty text for embedding")
                embeddings.append(None)
                continue
            
            # Skip if text is too long (Ollama has limits)
            if len(text) > 8192:  # Reasonable limit
                logger.debug(f"Text too long for embedding ({len(text)} chars), truncating")
                text = text[:8192]
            
            try:
                response = ollama.embeddings(
                    model=self.embedding_model,
                    prompt=text
                )
                if "embedding" in response and response["embedding"]:
                    embeddings.append(response["embedding"])
                else:
                    logger.debug("Empty embedding response")
                    embeddings.append(None)
            except Exception as e:
                error_msg = str(e)
                if "not found" in error_msg.lower():
                    if not model_error_shown:
                        self.formatter.print_error(f"Embedding model '{self.embedding_model}' not found.")
                        self.formatter.print_info(f"Please run: ollama pull {self.embedding_model}")
                        model_error_shown = True
                    embeddings.append(None)
                elif "EOF" in error_msg or "500" in error_msg:
                    # This usually means invalid input or server error
                    logger.debug(f"Embedding generation failed (likely invalid input): {e}")
                    embeddings.append(None)
                else:
                    logger.debug(f"Error generating embedding: {e}")
                    embeddings.append(None)
        
        return embeddings
    
    def index(self, clean: bool = False) -> Dict[str, Any]:
        """
        Index the project.
        
        Args:
            clean: If True, clear existing index first
            
        Returns:
            Indexing metrics dict
        """
        start_time = time.time()
        metrics = MetricsCollector()
        metrics.start_indexing()
        
        # Pre-flight check: Verify chunker is ready
        if not self.chunker.is_ready():
            parser_errors = self.chunker.get_parser_errors()
            error_msg = "Tree-sitter parsers failed to load. Cannot proceed with indexing.\n"
            if parser_errors:
                error_msg += "Errors:\n"
                for lang, err in parser_errors.items():
                    error_msg += f"  - {lang}: {err}\n"
            error_msg += "\nPlease ensure tree-sitter and tree-sitter-python are correctly installed."
            self.formatter.print_error(error_msg)
            return {
                "indexing_time": 0.0,
                "files_indexed": 0,
                "files_list": [],
                "chunks_created": 0,
                "index_size_mb": 0.0,
                "peak_ram_mb": 0.0,
                "peak_vram_mb": None,
                "errors": ["Tree-sitter parser initialization failed"]
            }
        
        if clean:
            self.vector_db.clear()
        
        # Discover files
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task("Discovering files...", total=None)
            files = self.discover_files()
            progress.update(task, completed=True)
        
        files_indexed = []
        all_chunks = []
        processing_errors = []  # Aggregate errors instead of spamming
        
        # Process files with progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            transient=False,
        ) as progress:
            file_task = progress.add_task("Processing files...", total=len(files))
            chunk_task = progress.add_task("Chunking...", total=0)
            embed_task = progress.add_task("Generating embeddings...", total=0)
            
            # Process files in batches
            for file_path in files:
                try:
                    # Update RAM tracking periodically
                    metrics.update_indexing_ram()
                    
                    # Read file with defensive handling
                    try:
                        content, error = self.file_handler.read_file(str(file_path))
                        if error:
                            # Store error for summary, don't spam console
                            processing_errors.append({
                                "file": str(file_path),
                                "error": f"Read error: {error}"
                            })
                            logger.debug(f"Skipping {file_path}: {error}")
                            progress.update(file_task, advance=1)
                            continue
                        
                        # Explicitly check for None or empty content
                        if content is None or not isinstance(content, str) or not content.strip():
                            processing_errors.append({
                                "file": str(file_path),
                                "error": "Empty or unreadable file"
                            })
                            logger.debug(f"Skipping empty file: {file_path}")
                            progress.update(file_task, advance=1)
                            continue
                        
                        # Chunk file - always returns a list (never None)
                        try:
                            chunks = self.chunker.chunk_file(file_path, content)
                        except AttributeError as e:
                            # Critical: Tree-sitter API error - this is a fatal error for this file
                            processing_errors.append({
                                "file": str(file_path),
                                "error": f"Tree-sitter parsing error: {str(e)}"
                            })
                            logger.error(f"Tree-sitter error processing {file_path}: {e}")
                            progress.update(file_task, advance=1)
                            continue
                        except Exception as e:
                            # Other chunking errors - log and continue
                            processing_errors.append({
                                "file": str(file_path),
                                "error": f"Chunking error: {str(e)}"
                            })
                            logger.debug(f"Chunking failed for {file_path}: {e}")
                            progress.update(file_task, advance=1)
                            continue
                        
                        # Ensure chunks is a list
                        if chunks is None:
                            logger.warning(f"Chunker returned None for {file_path}, skipping")
                            chunks = []
                        
                        # Validate chunks - ensure no None values and set relative file paths
                        valid_chunks = []
                        try:
                            # Get relative path once for all chunks from this file
                            rel_path = file_path.relative_to(self.project_root)
                            rel_path_str = str(rel_path) if rel_path else None
                        except (ValueError, AttributeError) as e:
                            logger.warning(f"Error getting relative path for {file_path}: {e}")
                            rel_path_str = str(file_path) if file_path else None
                        
                        for chunk in chunks:
                            if chunk and isinstance(chunk, dict):
                                # Validate required fields - ensure content is a non-empty string
                                chunk_content = chunk.get("content")
                                if (chunk_content and isinstance(chunk_content, str) and chunk_content.strip() and 
                                    chunk.get("chunk_hash") is not None):
                                    # Set relative file path (ensure it's a string, not None)
                                    if rel_path_str:
                                        chunk["file_path"] = rel_path_str
                                    elif chunk.get("file_path"):
                                        chunk["file_path"] = str(chunk["file_path"])
                                    else:
                                        chunk["file_path"] = "unknown"
                                    valid_chunks.append(chunk)
                                else:
                                    logger.debug(f"Skipping invalid chunk from {file_path}: missing or invalid content/hash")
                        
                        if valid_chunks:
                            all_chunks.extend(valid_chunks)
                            # Add file to indexed list (only once per file)
                            if rel_path_str:
                                files_indexed.append(rel_path_str)
                            else:
                                files_indexed.append(str(file_path) if file_path else "unknown")
                        
                        progress.update(file_task, advance=1)
                        progress.update(chunk_task, total=len(all_chunks))
                    
                    except UnicodeDecodeError as e:
                        processing_errors.append({
                            "file": str(file_path),
                            "error": f"Encoding error: {str(e)}"
                        })
                        logger.debug(f"Unicode decode error for {file_path}: {e}")
                        progress.update(file_task, advance=1)
                        continue
                    except IOError as e:
                        processing_errors.append({
                            "file": str(file_path),
                            "error": f"IO error: {str(e)}"
                        })
                        logger.debug(f"IO error reading {file_path}: {e}")
                        progress.update(file_task, advance=1)
                        continue
                    except PermissionError as e:
                        processing_errors.append({
                            "file": str(file_path),
                            "error": f"Permission denied: {str(e)}"
                        })
                        logger.debug(f"Permission error reading {file_path}: {e}")
                        progress.update(file_task, advance=1)
                        continue
                
                except Exception as e:
                    processing_errors.append({
                        "file": str(file_path),
                        "error": f"Unexpected error: {str(e)}"
                    })
                    logger.debug(f"Failed to process file {file_path}: {e}")
                    progress.update(file_task, advance=1)
                    continue
            
            # Generate embeddings in batches - maintain strict 1:1 mapping
            progress.update(embed_task, total=len(all_chunks))
            embeddings = []
            valid_chunks_for_storage = []  # Keep chunks that have embeddings
            
            for i in range(0, len(all_chunks), self.batch_size):
                batch = all_chunks[i:i + self.batch_size]
                batch_items = []  # List of (chunk, text) tuples
                
                # Collect valid chunks and their texts (maintain order)
                for chunk in batch:
                    if chunk and chunk.get("content"):
                        batch_items.append((chunk, chunk["content"]))
                
                if batch_items:
                    # Update RAM tracking during embedding generation
                    metrics.update_indexing_ram()
                    
                    # Generate embeddings for all texts
                    batch_texts = [item[1] for item in batch_items]
                    batch_embeddings = self._generate_embeddings_batch(batch_texts)
                    
                    # Maintain strict 1:1 mapping - embeddings list matches texts list
                    # Only add pairs where embedding succeeded (not None)
                    for idx, embedding in enumerate(batch_embeddings):
                        if idx < len(batch_items) and embedding is not None:
                            chunk = batch_items[idx][0]
                            valid_chunks_for_storage.append(chunk)
                            embeddings.append(embedding)
                
                progress.update(embed_task, advance=len(batch))
            
            # Store in vector DB - use only chunks that have embeddings
            if valid_chunks_for_storage and embeddings:
                if len(valid_chunks_for_storage) != len(embeddings):
                    self.formatter.print_warning(f"Storing {len(embeddings)} chunks (some may have been skipped due to embedding errors)")
                    # Ensure matching counts
                    min_len = min(len(valid_chunks_for_storage), len(embeddings))
                    valid_chunks_for_storage = valid_chunks_for_storage[:min_len]
                    embeddings = embeddings[:min_len]
                
                store_task = progress.add_task("Storing in vector database...", total=len(valid_chunks_for_storage))
                # Update RAM before storing
                metrics.update_indexing_ram()
                self.vector_db.add_chunks(valid_chunks_for_storage, embeddings)
                progress.update(store_task, completed=len(valid_chunks_for_storage))
                
                # Update all_chunks count for metrics
                all_chunks = valid_chunks_for_storage
        
        indexing_time = time.time() - start_time
        
        # Final RAM update
        metrics.update_indexing_ram()
        
        # Get metrics
        indexing_metrics = metrics.get_indexing_metrics(
            indexing_time,
            files_indexed,
            len(all_chunks),
            self.project_root / ".azul_index"
        )
        
        # Add error summary to metrics
        if processing_errors:
            indexing_metrics["processing_errors"] = processing_errors
            indexing_metrics["error_count"] = len(processing_errors)
            
            # Display error summary if there are errors
            if len(processing_errors) > 0:
                self.formatter.console.print(f"\n[yellow]⚠️  Warning: {len(processing_errors)} file(s) could not be processed[/yellow]")
                if len(processing_errors) <= 5:
                    for err in processing_errors:
                        self.formatter.console.print(f"  - {err['file']}: {err['error']}")
                else:
                    # Show first 5 errors
                    for err in processing_errors[:5]:
                        self.formatter.console.print(f"  - {err['file']}: {err['error']}")
                    self.formatter.console.print(f"  ... and {len(processing_errors) - 5} more errors (check logs for details)")
                self.formatter.console.print()
        
        return indexing_metrics
    
    def update_file(self, file_path: str) -> None:
        """Incrementally update index for a single file."""
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.is_absolute():
                file_path_obj = self.project_root / file_path
            
            # Check if file should be indexed
            if not self._should_index_file(file_path_obj):
                return
            
            # Delete old chunks for this file
            self.vector_db.delete_chunks_by_file(str(file_path_obj.relative_to(self.project_root)))
            
            # Read and chunk file with validation
            content, error = self.file_handler.read_file(str(file_path_obj))
            if error:
                return
            
            if content is None or not content.strip():
                return
            
            chunks = self.chunker.chunk_file(file_path_obj, content)
            if not chunks:
                return
            
            # Validate chunks
            valid_chunks = []
            for chunk in chunks:
                if (chunk and isinstance(chunk, dict) and 
                    chunk.get("content") and 
                    chunk.get("file_path") and 
                    chunk.get("chunk_hash") is not None):
                    valid_chunks.append(chunk)
            
            if not valid_chunks:
                return
            
            # Generate embeddings
            chunk_texts = [chunk["content"] for chunk in valid_chunks]
            embeddings = self._generate_embeddings_batch(chunk_texts)
            
            # Ensure matching counts
            if len(valid_chunks) == len(embeddings):
                # Store new chunks
                self.vector_db.add_chunks(valid_chunks, embeddings)
        except Exception as e:
            # Silently fail - don't interrupt user
            pass

