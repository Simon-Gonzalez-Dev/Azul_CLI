"""Safe file I/O operations with validation."""

from pathlib import Path
from typing import Optional, Tuple, List

from azul.sandbox import get_sandbox


class FileHandler:
    """Handles file operations with safety checks."""
    
    MAX_FILE_SIZE_MB = 10
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
    
    def __init__(self):
        """Initialize file handler."""
        self.sandbox = get_sandbox()
    
    def is_binary_file(self, file_path: Path) -> bool:
        """
        Detect if a file is binary.
        
        Args:
            file_path: Path to file
            
        Returns:
            True if file appears to be binary
        """
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(8192)
                # Check for null bytes or high percentage of non-text characters
                if b'\x00' in chunk:
                    return True
                # Check if more than 30% are non-printable (excluding newlines, tabs)
                text_chars = sum(1 for byte in chunk if 32 <= byte <= 126 or byte in (9, 10, 13))
                if len(chunk) > 0:
                    text_ratio = text_chars / len(chunk)
                    return text_ratio < 0.7
        except (IOError, OSError):
            pass
        return False
    
    def is_file_too_large(self, file_path: Path) -> bool:
        """
        Check if file exceeds size limit.
        
        Args:
            file_path: Path to file
            
        Returns:
            True if file is too large
        """
        try:
            size = file_path.stat().st_size
            return size > self.MAX_FILE_SIZE_BYTES
        except (OSError, IOError):
            return True
    
    def read_file(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Safely read a text file.
        
        Args:
            file_path: Path to file (relative or absolute, will search if not found)
            
        Returns:
            Tuple of (content, error_message). content is None if error occurred.
        """
        # Try to find the file (searches recursively if needed)
        safe_path = self.find_file(file_path)
        
        if safe_path is None:
            # Try direct path first
            safe_path = self.sandbox.get_safe_path(file_path)
            if safe_path is None:
                return None, f"File not found: {file_path} (searched in {self.sandbox.project_root})"
        
        if not safe_path.exists():
            return None, f"File does not exist: {file_path}"
        
        if not safe_path.is_file():
            return None, f"Path is not a file: {file_path}"
        
        if self.is_binary_file(safe_path):
            return None, f"Binary files are not supported: {file_path}"
        
        if self.is_file_too_large(safe_path):
            return None, f"File is too large (>{self.MAX_FILE_SIZE_MB}MB): {file_path}"
        
        try:
            # Try UTF-8 first, then fall back to other encodings
            encodings = ['utf-8', 'latin-1', 'cp1252']
            for encoding in encodings:
                try:
                    with open(safe_path, 'r', encoding=encoding) as f:
                        return f.read(), None
                except UnicodeDecodeError:
                    continue
            return None, f"Could not decode file with any supported encoding: {file_path}"
        except (IOError, OSError) as e:
            return None, f"Error reading file: {e}"
    
    def find_file(self, filename: str) -> Optional[Path]:
        """
        Search for a file by name in the project directory (recursively).
        
        Args:
            filename: Name of the file to find (can include subdirectories)
            
        Returns:
            Path to the file if found, None otherwise
        """
        # First try exact path match
        safe_path = self.sandbox.get_safe_path(filename)
        if safe_path and safe_path.exists() and safe_path.is_file():
            return safe_path
        
        # If not found, search recursively
        project_root = self.sandbox.project_root
        filename_only = Path(filename).name
        
        # Search recursively for the file
        for path in project_root.rglob(filename_only):
            # Skip hidden directories and files
            if any(part.startswith('.') for part in path.parts):
                continue
            
            # Validate it's within sandbox
            if self.sandbox.validate_path(path) and path.is_file():
                return path
        
        # Also try searching with the full relative path
        if '/' in filename or '\\' in filename:
            # Try as relative path
            potential_path = project_root / filename
            safe_path = self.sandbox.get_safe_path(str(potential_path))
            if safe_path and safe_path.exists() and safe_path.is_file():
                return safe_path
        
        return None
    
    def write_file(self, file_path: str, content: str) -> Optional[str]:
        """
        Safely write content to a file.
        
        Args:
            file_path: Path to file (can include subdirectories)
            content: Content to write
            
        Returns:
            Error message if error occurred, None otherwise
        """
        safe_path = self.sandbox.get_safe_path(file_path)
        
        if safe_path is None:
            return "File path is outside the project directory or invalid"
        
        try:
            # Ensure parent directory exists
            safe_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(safe_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return None
        except (IOError, OSError) as e:
            return f"Error writing file: {e}"
    
    def file_exists(self, file_path: str) -> bool:
        """Check if a file exists and is accessible (searches recursively)."""
        found_path = self.find_file(file_path)
        if found_path:
            return True
        # Fallback to direct path check
        safe_path = self.sandbox.get_safe_path(file_path)
        return safe_path is not None and safe_path.exists() and safe_path.is_file()


# Global file handler instance
_file_handler: Optional[FileHandler] = None


def get_file_handler() -> FileHandler:
    """Get the global file handler instance."""
    global _file_handler
    if _file_handler is None:
        _file_handler = FileHandler()
    return _file_handler

