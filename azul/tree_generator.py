"""Directory tree generator for displaying project structure."""

from pathlib import Path
from typing import Set


def generate_tree(project_root: Path, max_depth: int = 3) -> str:
    """
    Generate a text representation of the directory tree structure.
    
    Args:
        project_root: Root directory to generate tree from
        max_depth: Maximum depth to traverse (default: 3)
        
    Returns:
        Formatted tree string
    """
    # Files and directories to ignore
    ignore_patterns: Set[str] = {
        '__pycache__',
        '.pyc',
        '.pyo',
        '.pyd',
        '.git',
        '.DS_Store',
        'node_modules',
        '.venv',
        'venv',
        'env',
        'ENV',
        '.eggs',
        '*.egg-info',
        '.pytest_cache',
        '.mypy_cache',
        '.tox',
        'dist',
        'build',
        'htmlcov',
        '.coverage',
    }
    
    def should_ignore(path: Path) -> bool:
        """Check if path should be ignored."""
        # Check if any part of the path matches ignore patterns
        for part in path.parts:
            if any(pattern in part for pattern in ignore_patterns):
                return True
        return False
    
    def is_hidden(path: Path) -> bool:
        """Check if path is hidden (starts with .)."""
        return any(part.startswith('.') for part in path.parts if part != '.')
    
    lines: list[str] = []
    lines.append(f"Project Structure ({project_root}):\n")
    
    def _build_tree(current_path: Path, prefix: str = "", depth: int = 0, is_last: bool = True):
        """Recursively build tree structure."""
        if depth > max_depth:
            return
        
        if current_path != project_root:
            # Skip hidden files/directories (except at root level)
            if is_hidden(current_path) or should_ignore(current_path):
                return
            
            # Tree connector
            connector = "└── " if is_last else "├── "
            name = current_path.name
            lines.append(f"{prefix}{connector}{name}\n")
            
            # Update prefix for children
            prefix += "    " if is_last else "│   "
        
        # Process children
        if current_path.is_dir():
            try:
                # Get all items and sort (directories first, then files)
                items = sorted(current_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
                
                # Filter out ignored items
                items = [item for item in items if not (is_hidden(item) or should_ignore(item))]
                
                for i, item in enumerate(items):
                    is_last_item = i == len(items) - 1
                    _build_tree(item, prefix, depth + 1, is_last_item)
            except PermissionError:
                # Skip directories we can't read
                pass
    
    # Start building from root
    _build_tree(project_root)
    
    return "".join(lines)

