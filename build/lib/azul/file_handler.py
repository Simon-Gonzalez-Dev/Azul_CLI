"""Safe file I/O operations with validation and backups."""

import shutil
from pathlib import Path
from typing import Optional, Tuple

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
            file_path: Path to file (relative or absolute)
            
        Returns:
            Tuple of (content, error_message). content is None if error occurred.
        """
        safe_path = self.sandbox.get_safe_path(file_path)
        
        if safe_path is None:
            return None, "File path is outside the project directory or invalid"
        
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
    
    def create_backup(self, file_path: str) -> Tuple[Optional[Path], Optional[str]]:
        """
        Create a backup of a file.
        
        Args:
            file_path: Path to file to backup
            
        Returns:
            Tuple of (backup_path, error_message). backup_path is None if error occurred.
        """
        safe_path = self.sandbox.get_safe_path(file_path)
        
        if safe_path is None:
            return None, "File path is outside the project directory or invalid"
        
        if not safe_path.exists():
            return None, f"File does not exist: {file_path}"
        
        backup_path = safe_path.with_suffix(safe_path.suffix + '.bak')
        
        try:
            shutil.copy2(safe_path, backup_path)
            return backup_path, None
        except (IOError, OSError) as e:
            return None, f"Error creating backup: {e}"
    
    def write_file(self, file_path: str, content: str) -> Optional[str]:
        """
        Safely write content to a file.
        
        Args:
            file_path: Path to file
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
        """Check if a file exists and is accessible."""
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

