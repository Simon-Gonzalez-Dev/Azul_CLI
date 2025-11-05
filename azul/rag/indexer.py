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
        
        for text in texts:
            # Validate text
            if not text or not isinstance(text, str):
                # Return None for invalid texts to maintain mapping
                embeddings.append(None)
                continue
            
            try:
                response = ollama.embeddings(
                    model=self.embedding_model,
                    prompt=text
                )
                if "embedding" in response and response["embedding"]:
                    embeddings.append(response["embedding"])
                else:
                    logger.warning("Empty embedding response")
                    embeddings.append(None)
            except Exception as e:
                # Don't spam errors - pre-flight check should have caught model issues
                # Only log to logger, not to user
                logger.error(f"Error generating embedding (batch): {e}")
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
        
        # PRE-FLIGHT CHECK: Verify embedding model is available BEFORE starting
        try:
            models_response = ollama.list()
            
            # Extract model names - handle different response formats
            local_models = []
            
            # Try different ways to extract models
            models_list = []
            
            # Handle ListResponse object (has .models attribute)
            if hasattr(models_response, 'models'):
                try:
                    models_list = models_response.models
                    # If models is a property that returns a dict with 'models' key, extract it
                    if isinstance(models_list, dict) and 'models' in models_list:
                        models_list = models_list['models']
                except (AttributeError, TypeError):
                    # Try dict conversion
                    try:
                        models_dict = dict(models_response) if hasattr(models_response, '__dict__') else {}
                        if 'models' in models_dict:
                            models_list = models_dict['models']
                    except:
                        pass
            # Handle dict-like objects
            elif isinstance(models_response, dict):
                # Try "models" key first
                if "models" in models_response:
                    models_list = models_response["models"]
                # Try other possible keys
                elif "data" in models_response:
                    models_list = models_response["data"]
                # Maybe the dict itself is the model list wrapper
                elif len(models_response) == 1 and isinstance(list(models_response.values())[0], list):
                    models_list = list(models_response.values())[0]
            # Handle list directly
            elif isinstance(models_response, list):
                models_list = models_response
            # Try to access as attribute if it's an object
            elif hasattr(models_response, '__dict__'):
                # Try common attribute names
                for attr in ['models', 'data', 'items']:
                    if hasattr(models_response, attr):
                        value = getattr(models_response, attr)
                        if isinstance(value, list):
                            models_list = value
                            break
            
            # Extract model names from the list
            for m in models_list:
                if isinstance(m, dict):
                    # Try multiple possible keys for model name
                    name = (
                        m.get("name") or 
                        m.get("model") or 
                        m.get("model_name") or
                        m.get("id")  # Sometimes it's "id"
                    )
                    if name:
                        name_str = str(name).strip()
                        if name_str:
                            # Store full name
                            local_models.append(name_str)
                            # Also add base name without tag for matching
                            if ":" in name_str:
                                base_name = name_str.split(":")[0]
                                if base_name and base_name not in local_models:
                                    local_models.append(base_name)
                elif isinstance(m, str):
                    m_str = m.strip()
                    if m_str:
                        local_models.append(m_str)
                        if ":" in m_str:
                            base_name = m_str.split(":")[0]
                            if base_name and base_name not in local_models:
                                local_models.append(base_name)
            
            # Check both exact match and base name match (without tag)
            embedding_base = self.embedding_model.split(":")[0] if ":" in self.embedding_model else self.embedding_model
            
            # Also check if any model starts with the base name (more flexible matching)
            model_found = False
            for model_name in local_models:
                model_str = str(model_name)
                # Check exact match
                if model_str == self.embedding_model or model_str == embedding_base:
                    model_found = True
                    break
                # Check if model starts with base name (handles tags)
                if model_str.startswith(embedding_base + ":") or model_str.startswith(self.embedding_model + ":"):
                    model_found = True
                    break
                # Check if base name matches (reverse check)
                if ":" in model_str and model_str.split(":")[0] == embedding_base:
                    model_found = True
                    break
            
            if not model_found:
                # Don't print error here - it's already handled in command handler
                # Return error in metrics for handler to display
                return {
                    "indexing_time": 0.0,
                    "files_indexed": 0,
                    "files_list": [],
                    "chunks_created": 0,
                    "index_size_mb": 0.0,
                    "peak_ram_mb": 0.0,
                    "error": f"Embedding model '{self.embedding_model}' not found"
                }
        except Exception as e:
            # Don't print error here - it's already handled in command handler
            return {
                "indexing_time": 0.0,
                "files_indexed": 0,
                "files_list": [],
                "chunks_created": 0,
                "index_size_mb": 0.0,
                "peak_ram_mb": 0.0,
                "error": str(e)
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
        skipped_files = []  # Track skipped files with reasons for summary
        error_files = []  # Track files with errors
        
        # Process files with progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[dim]{task.completed}/{task.total} files[/dim]"),
            transient=False,
        ) as progress:
            file_task = progress.add_task("Processing files...", total=len(files))
            chunk_task = progress.add_task("Chunking...", total=0)
            embed_task = progress.add_task("Generating embeddings...", total=0)
            
            # Process files in batches
            for file_path in files:
                try:
                    # Read file with defensive handling
                    try:
                        content, error = self.file_handler.read_file(str(file_path))
                        if error:
                            logger.warning(f"Skipping {file_path}: {error}")
                            try:
                                rel_path = file_path.relative_to(self.project_root)
                                skipped_files.append((str(rel_path), error))
                            except:
                                skipped_files.append((str(file_path), error))
                            progress.update(file_task, advance=1)
                            continue
                        
                        # Explicitly check for None or empty content
                        if content is None or not isinstance(content, str) or not content.strip():
                            logger.warning(f"Skipping empty or unreadable file: {file_path}")
                            try:
                                rel_path = file_path.relative_to(self.project_root)
                                skipped_files.append((str(rel_path), "Empty or unreadable file"))
                            except:
                                skipped_files.append((str(file_path), "Empty or unreadable file"))
                            progress.update(file_task, advance=1)
                            continue
                        
                        # Chunk file - always returns a list (never None)
                        chunks = self.chunker.chunk_file(file_path, content)
                        
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
                                content = chunk.get("content")
                                if (content and isinstance(content, str) and content.strip() and 
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
                                    logger.warning(f"Skipping invalid chunk from {file_path}: missing or invalid content/hash")
                        
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
                        logger.error(f"Unicode decode error for {file_path}: {e}", exc_info=True)
                        try:
                            rel_path = file_path.relative_to(self.project_root)
                            error_files.append((str(rel_path), f"Encoding error: {e}"))
                        except:
                            error_files.append((str(file_path), f"Encoding error: {e}"))
                        progress.update(file_task, advance=1)
                        continue
                    except IOError as e:
                        logger.error(f"IO error reading {file_path}: {e}", exc_info=True)
                        try:
                            rel_path = file_path.relative_to(self.project_root)
                            error_files.append((str(rel_path), f"IO error: {e}"))
                        except:
                            error_files.append((str(file_path), f"IO error: {e}"))
                        progress.update(file_task, advance=1)
                        continue
                
                except Exception as e:
                    logger.error(f"Failed to process file {file_path}: {e}", exc_info=True)
                    try:
                        rel_path = file_path.relative_to(self.project_root)
                        error_files.append((str(rel_path), f"Processing error: {e}"))
                    except:
                        error_files.append((str(file_path), f"Processing error: {e}"))
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
            chunks_stored = 0  # Initialize before storage
            if valid_chunks_for_storage and embeddings:
                if len(valid_chunks_for_storage) != len(embeddings):
                    logger.warning(f"Chunk/embedding count mismatch: {len(valid_chunks_for_storage)} chunks, {len(embeddings)} embeddings")
                    # Ensure matching counts
                    min_len = min(len(valid_chunks_for_storage), len(embeddings))
                    valid_chunks_for_storage = valid_chunks_for_storage[:min_len]
                    embeddings = embeddings[:min_len]
                
                store_task = progress.add_task("Storing in vector database...", total=len(valid_chunks_for_storage))
                self.vector_db.add_chunks(valid_chunks_for_storage, embeddings)
                progress.update(store_task, completed=len(valid_chunks_for_storage))
                
                # Track chunks stored for metrics
                chunks_stored = len(valid_chunks_for_storage)
        
        indexing_time = time.time() - start_time
        
        # Get metrics - chunks_stored is set during storage phase
        final_chunks_stored = chunks_stored if 'chunks_stored' in locals() else 0
        
        indexing_metrics = metrics.get_indexing_metrics(
            indexing_time,
            files_indexed,
            final_chunks_stored,  # Use actual stored chunks
            self.project_root / ".azul_index"
        )
        
        # Add summary information
        indexing_metrics["skipped_files"] = skipped_files
        indexing_metrics["error_files"] = error_files
        
        # Display summary if there were skipped/error files
        if skipped_files or error_files:
            total_issues = len(skipped_files) + len(error_files)
            if total_issues > 0:
                self.formatter.console.print(f"\n[dim]Skipped {len(skipped_files)} file(s), {len(error_files)} error(s)[/dim]")
        
        # Add warning if no chunks were stored
        if final_chunks_stored == 0 and len(files) > 0:
            indexing_metrics["warning"] = "No chunks were successfully indexed. Check logs for errors."
            self.formatter.print_warning("⚠️  Warning: No chunks were successfully indexed. The index may be empty.")
        
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

