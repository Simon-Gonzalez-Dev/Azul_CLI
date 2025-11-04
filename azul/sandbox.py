"""Sandboxed environment for file operations."""

import os
from pathlib import Path
from typing import Optional


class Sandbox:
    """Validates file paths to ensure they're within the project directory."""
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize sandbox with project root.
        
        Args:
            project_root: Root directory of the project. Defaults to current working directory.
        """
        if project_root is None:
            project_root = Path.cwd()
        self.project_root = Path(project_root).resolve()
        
    def validate_path(self, file_path: Path) -> bool:
        """
        Validate that a file path is within the project directory.
        
        Args:
            file_path: Path to validate
            
        Returns:
            True if path is safe, False otherwise
        """
        try:
            resolved_path = Path(file_path).resolve()
            # Check if the resolved path is within project root
            return resolved_path.is_relative_to(self.project_root)
        except (ValueError, OSError):
            return False
    
    def get_safe_path(self, file_path: str) -> Optional[Path]:
        """
        Get a safe, validated path within the sandbox.
        
        Args:
            file_path: File path (relative or absolute)
            
        Returns:
            Validated Path object, or None if path is unsafe
        """
        path = Path(file_path)
        
        # If absolute, validate directly
        if path.is_absolute():
            if self.validate_path(path):
                return path
            return None
        
        # If relative, resolve against project root
        resolved = (self.project_root / path).resolve()
        if self.validate_path(resolved):
            return resolved
        
        return None
    
    def is_safe(self, file_path: str) -> bool:
        """
        Check if a file path is safe to access.
        
        Args:
            file_path: File path to check
            
        Returns:
            True if safe, False otherwise
        """
        safe_path = self.get_safe_path(file_path)
        return safe_path is not None
    
    def block_path_traversal(self, file_path: str) -> bool:
        """
        Check if path contains traversal attempts.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if path traversal detected, False otherwise
        """
        # Check for obvious path traversal attempts
        if ".." in file_path or file_path.startswith("/"):
            # Still validate - it might be a legitimate absolute path within project
            return not self.is_safe(file_path)
        return False


# Global sandbox instance
_sandbox: Optional[Sandbox] = None


def get_sandbox(project_root: Optional[Path] = None) -> Sandbox:
    """Get the global sandbox instance."""
    global _sandbox
    if _sandbox is None:
        _sandbox = Sandbox(project_root)
    elif project_root is not None:
        # Update project root if provided and different
        new_root = Path(project_root).resolve()
        if _sandbox.project_root != new_root:
            _sandbox = Sandbox(project_root)
    return _sandbox

