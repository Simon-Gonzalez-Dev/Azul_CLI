"""Semantic code chunker using Tree-sitter."""

import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import tree_sitter
from tree_sitter import Language, Parser
import tiktoken

logger = logging.getLogger(__name__)


class Chunker:
    """Semantic code chunker with Tree-sitter support."""
    
    def __init__(self, config):
        """Initialize chunker."""
        self.config = config
        rag_config = config.get("rag", {})
        self.max_tokens = rag_config.get("chunk_max_tokens", 512)
        self.overlap_lines = rag_config.get("chunk_overlap_lines", 2)
        
        # Initialize tokenizer
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self.tokenizer = None
        
        # Initialize Tree-sitter parsers (lazy loading)
        self._parsers = {}
        self._load_parsers()
    
    def _load_parsers(self) -> None:
        """Load Tree-sitter parsers for supported languages."""
        # Python is available via tree-sitter-python
        # The language() function returns a PyCapsule that needs to be wrapped in Language()
        self._parsers = {}
        self._parser_errors = {}
        
        # Try to load Python parser
        try:
            from tree_sitter_python import language as python_language_func
            
            # Get the language capsule and wrap it in Language()
            try:
                lang_capsule = python_language_func()
                python_language = Language(lang_capsule)
                
                # Verify it works by creating a test parser
                test_parser = Parser()
                test_parser.language = python_language
                
                # If successful, store the Language object
                self._parsers["python"] = python_language
                logger.info("Successfully loaded Python Tree-sitter parser")
            except TypeError as e:
                # Language constructor failed
                logger.error(f"Failed to create Language object: {e}")
                logger.error("This usually means tree-sitter or tree-sitter-python version is incompatible.")
                self._parser_errors["python"] = f"Language object creation failed: {e}"
            except AttributeError as e:
                # Parser.language assignment failed
                logger.error(f"Failed to set parser language: {e}")
                logger.error("This usually means tree-sitter version is incompatible.")
                logger.error("Please ensure tree-sitter>=0.20.0,<0.22.0 is installed.")
                self._parser_errors["python"] = f"Parser language assignment failed: {e}"
            except Exception as e:
                # Other error when trying to set language
                logger.error(f"Failed to initialize parser: {e}")
                self._parser_errors["python"] = f"Parser initialization error: {e}"
        except ImportError as e:
            logger.warning(f"tree-sitter-python not available: {e}")
            logger.info("Install it with: pip install tree-sitter-python")
            self._parser_errors["python"] = f"Import error: {e}"
        except Exception as e:
            logger.error(f"Failed to load Python parser: {e}")
            self._parser_errors["python"] = f"Unexpected error: {e}"
    
    def is_ready(self) -> bool:
        """Check if chunker is ready (has at least one working parser)."""
        return len(self._parsers) > 0
    
    def get_parser_errors(self) -> dict:
        """Get any parser loading errors."""
        return self._parser_errors.copy()
    
    def _get_parser(self, language: str) -> Optional[Parser]:
        """Get parser for a language."""
        if language not in self._parsers:
            return None
        
        try:
            parser = Parser()
            language_obj = self._parsers[language]
            
            # Assign language directly (this is the correct API for tree-sitter 0.20+)
            parser.language = language_obj
            return parser
        except AttributeError as e:
            logger.error(f"Error setting language for {language}: {e}")
            logger.error("This usually indicates a tree-sitter version mismatch.")
            logger.error("Please ensure tree-sitter>=0.20.0,<0.22.0 is installed.")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating parser for {language}: {e}")
            return None
    
    def _detect_language(self, file_path: Path) -> str:
        """Detect language from file extension."""
        ext = file_path.suffix.lower()
        lang_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".cpp": "cpp",
            ".c": "c",
            ".cs": "csharp",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
        }
        return lang_map.get(ext, "text")
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        # Fallback: approximate 1 token = 4 characters
        return len(text) // 4
    
    def _generate_hash(self, content: str) -> str:
        """Generate MD5 hash of content."""
        return hashlib.md5(content.encode()).hexdigest()
    
    def _chunk_by_ast(self, code: str, language: str, file_path: Path) -> List[Dict[str, Any]]:
        """Chunk code using AST (Tree-sitter)."""
        # Ensure code is a valid string
        if not code or not isinstance(code, str):
            logger.warning(f"Invalid code for AST chunking: {file_path}")
            return []
        
        parser = self._get_parser(language)
        if not parser:
            # No parser available, will fall back to character splitting
            return []
        
        try:
            # Parse the code
            tree = parser.parse(bytes(code, "utf8"))
            
            # Check if tree is valid
            if not tree or not hasattr(tree, 'root_node'):
                logger.warning(f"Invalid parse tree for {file_path}")
                return []
            chunks = []
            
            # Traverse AST to find function/class definitions
            def traverse(node, depth=0):
                # Node types to chunk (functions, classes, methods)
                chunkable_types = [
                    "function_definition",
                    "class_definition",
                    "method_definition",
                ]
                
                if node.type in chunkable_types:
                    # Extract the code for this node
                    start_byte = node.start_byte
                    end_byte = node.end_byte
                    chunk_content = code[start_byte:end_byte]
                    
                    # Validate chunk content
                    if not chunk_content or not isinstance(chunk_content, str):
                        return
                    
                    # Count tokens
                    token_count = self._count_tokens(chunk_content)
                    
                    # If chunk is too large, try to split it
                    if token_count > self.max_tokens:
                        # Split by inner statements
                        for child in node.children:
                            if child.type in ["block", "suite"]:
                                # Split by statements in block
                                for stmt in child.children:
                                    if stmt.type in ["expression_statement", "assignment", "return_statement"]:
                                        stmt_content = code[stmt.start_byte:stmt.end_byte]
                                        # Validate statement content
                                        if stmt_content and isinstance(stmt_content, str) and self._count_tokens(stmt_content) <= self.max_tokens:
                                            chunks.append({
                                                "content": stmt_content,
                                                "start_line": node.start_point[0] + 1,
                                                "end_line": stmt.end_point[0] + 1,
                                                "chunk_hash": self._generate_hash(stmt_content),
                                            })
                    else:
                        # Chunk is small enough, add it
                        # Get line numbers
                        start_line = node.start_point[0] + 1
                        end_line = node.end_point[0] + 1
                        
                        chunks.append({
                            "content": chunk_content,
                            "start_line": start_line,
                            "end_line": end_line,
                            "chunk_hash": self._generate_hash(chunk_content),
                        })
                
                # Recursively traverse children
                for child in node.children:
                    traverse(child, depth + 1)
            
            traverse(tree.root_node)
            
            # Add overlap if needed
            if self.overlap_lines > 0 and len(chunks) > 1:
                overlapped_chunks = []
                for i, chunk in enumerate(chunks):
                    if i > 0:
                        # Add overlap from previous chunk
                        prev_chunk = chunks[i - 1]
                        lines = code.split("\n")
                        overlap_start = max(0, chunk["start_line"] - self.overlap_lines - 1)
                        overlap_end = min(len(lines), chunk["start_line"])
                        
                        if overlap_start < overlap_end:
                            # Filter out None values and ensure all are strings before joining
                            overlap_lines_clean = [str(line) if line is not None else "" for line in lines[overlap_start:overlap_end]]
                            if overlap_lines_clean:
                                overlap_content = "\n".join(overlap_lines_clean)
                                chunk_content = chunk.get("content", "")
                                if chunk_content:
                                    chunk["content"] = overlap_content + "\n" + chunk_content
                                    chunk["start_line"] = overlap_start + 1
                    
                    overlapped_chunks.append(chunk)
                chunks = overlapped_chunks
            
            return chunks
        
        except AttributeError as e:
            # This is the critical error - set_language or similar API issue
            logger.error(f"Tree-sitter API error parsing {file_path}: {e}")
            logger.error("This indicates a tree-sitter version mismatch. Falling back to character-based chunking.")
            return []
        except Exception as e:
            # Other parsing errors - log but don't crash
            logger.debug(f"AST parsing failed for {file_path}: {e}. Falling back to character-based chunking.")
            return []
    
    def _chunk_by_chars(self, code: str, file_path: Path) -> List[Dict[str, Any]]:
        """Chunk code using recursive character splitting (fallback)."""
        # Ensure code is a valid string
        if not code or not isinstance(code, str):
            logger.warning(f"Invalid code for chunking: {file_path}")
            return []
        
        lines = code.split("\n")
        # Filter out None values immediately (shouldn't happen with split, but defensive)
        lines = [line if line is not None else "" for line in lines]
        
        chunks = []
        current_chunk = []
        current_tokens = 0
        start_line = 1
        
        for line_num, line in enumerate(lines, 1):
            # Ensure line is a string
            if line is None:
                line = ""
            line_tokens = self._count_tokens(str(line))
            
            if current_tokens + line_tokens > self.max_tokens and current_chunk:
                # Save current chunk - filter None values and ensure all are strings
                current_chunk_clean = [str(line) if line is not None else "" for line in current_chunk]
                if current_chunk_clean:
                    chunk_content = "\n".join(current_chunk_clean)
                    chunks.append({
                        "content": chunk_content,
                        "start_line": start_line,
                        "end_line": line_num - 1,
                        "chunk_hash": self._generate_hash(chunk_content),
                    })
                
                # Start new chunk with overlap
                if self.overlap_lines > 0:
                    overlap_start = max(0, len(current_chunk) - self.overlap_lines)
                    current_chunk = current_chunk[overlap_start:]
                    start_line = line_num - len(current_chunk)
                    current_tokens = sum(self._count_tokens(l) for l in current_chunk)
                else:
                    current_chunk = []
                    start_line = line_num
                    current_tokens = 0
            
            current_chunk.append(line)
            current_tokens += line_tokens
        
        # Add final chunk - filter None values and ensure all are strings
        if current_chunk:
            current_chunk_clean = [str(line) if line is not None else "" for line in current_chunk]
            if current_chunk_clean:
                chunk_content = "\n".join(current_chunk_clean)
                chunks.append({
                    "content": chunk_content,
                    "start_line": start_line,
                    "end_line": len(lines),
                    "chunk_hash": self._generate_hash(chunk_content),
                })
        
        return chunks
    
    def chunk_file(self, file_path: Path, content: str) -> List[Dict[str, Any]]:
        """
        Chunk a file into semantic pieces.
        
        Args:
            file_path: Path to the file
            content: File content
            
        Returns:
            List of chunk dicts with metadata (never None, always returns a list)
        """
        # Validate inputs
        if not content or not isinstance(content, str):
            logger.warning(f"Invalid content for file {file_path}, returning empty chunks")
            return []
        
        if not file_path:
            logger.warning("Invalid file_path, returning empty chunks")
            return []
        
        try:
            language = self._detect_language(file_path)
            
            # Try AST-based chunking first
            chunks = self._chunk_by_ast(content, language, file_path)
            
            # Fallback to character splitting if AST chunking failed or returned nothing
            if not chunks:
                chunks = self._chunk_by_chars(content, file_path)
            
            # Ensure chunks is a list (never None)
            if chunks is None:
                logger.warning(f"Chunker returned None for {file_path}, using empty list")
                chunks = []
            
            # Validate and add file metadata to each chunk
            # Use file_path as-is (will be converted to relative in indexer if needed)
            try:
                if file_path:
                    file_path_str = str(file_path)
                else:
                    file_path_str = "unknown"
            except Exception as e:
                logger.error(f"Error generating file path string for {file_path}: {e}")
                file_path_str = "unknown"
            
            validated_chunks = []
            for chunk in chunks:
                if not chunk or not isinstance(chunk, dict):
                    logger.warning(f"Skipping invalid chunk (not a dict) for {file_path}")
                    continue
                
                # Validate required fields
                if not chunk.get("content"):
                    logger.warning(f"Skipping chunk with no content for {file_path}")
                    continue
                
                if chunk.get("chunk_hash") is None:
                    logger.warning(f"Generating missing chunk_hash for {file_path}")
                    chunk["chunk_hash"] = self._generate_hash(chunk["content"])
                
                # Set metadata
                chunk["file_path"] = file_path_str
                chunk["language"] = language
                chunk["chunk_type"] = chunk.get("chunk_type", "function" if language != "text" else "text")
                
                # Generate chunk ID
                try:
                    from azul.rag.vector_db import VectorDB
                    chunk["chunk_id"] = VectorDB.generate_chunk_id(
                        chunk["file_path"],
                        chunk.get("start_line", 0),
                        chunk.get("end_line", 0),
                        chunk["chunk_hash"]
                    )
                    validated_chunks.append(chunk)
                except Exception as e:
                    logger.error(f"Error generating chunk ID: {e}, skipping chunk")
                    continue
            
            return validated_chunks
            
        except Exception as e:
            logger.error(f"Error chunking file {file_path}: {e}", exc_info=True)
            return []  # Always return a list, never None

