"""Editor module for parsing and applying unified diffs."""

import re
from pathlib import Path
from typing import Optional, List, Tuple
from difflib import SequenceMatcher

from azul.file_handler import get_file_handler
from azul.sandbox import get_sandbox
from azul.permissions import get_permission_manager
from azul.formatter import get_formatter
from azul.config.manager import get_config_manager


class DiffEditor:
    """Handles parsing and applying unified diffs."""
    
    def __init__(self):
        """Initialize diff editor."""
        self.file_handler = get_file_handler()
        self.sandbox = get_sandbox()
        self.permissions = get_permission_manager()
        self.formatter = get_formatter()
        self.config = get_config_manager()
    
    def extract_diff_from_markdown(self, content: str) -> Optional[str]:
        """
        Extract unified diff from markdown code block.
        
        Args:
            content: Markdown content that may contain diff
            
        Returns:
            Extracted diff content, or None if not found
        """
        # Pattern to match diff code blocks
        pattern = r'```diff\s*\n(.*?)```'
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            return match.group(1).strip()
        
        # Try without language tag
        pattern = r'```\s*\n(.*?)^---\s+a/.*?^```'
        match = re.search(pattern, content, re.DOTALL | re.MULTILINE)
        if match:
            diff_content = match.group(1).strip()
            if diff_content.startswith('---'):
                return diff_content
        
        return None
    
    def parse_unified_diff(self, diff_content: str) -> List[Tuple[str, int, int, List[str]]]:
        """
        Parse unified diff into hunks.
        
        Args:
            diff_content: Unified diff content
            
        Returns:
            List of (file_path, old_start, old_count, lines) tuples
        """
        hunks = []
        lines = diff_content.split('\n')
        
        i = 0
        current_file = None
        
        while i < len(lines):
            line = lines[i]
            
            # Parse file header
            if line.startswith('--- a/'):
                current_file = line[6:].strip()
            elif line.startswith('+++ b/'):
                # File path is in the +++ line
                if current_file is None:
                    current_file = line[6:].strip()
            elif line.startswith('@@'):
                # Parse hunk header: @@ -start,count +start,count @@
                match = re.match(r'@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@', line)
                if match:
                    old_start = int(match.group(1))
                    old_count = int(match.group(2) or 1)
                    new_start = int(match.group(3))
                    new_count = int(match.group(4) or 1)
                    
                    # Collect hunk lines
                    hunk_lines = [line]
                    i += 1
                    while i < len(lines) and not lines[i].startswith('@@') and not lines[i].startswith('---'):
                        hunk_lines.append(lines[i])
                        i += 1
                    
                    if current_file:
                        hunks.append((current_file, old_start, old_count, hunk_lines))
                    continue
            
            i += 1
        
        return hunks
    
    def apply_diff_to_file(
        self,
        file_path: str,
        diff_content: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Apply unified diff to a file.
        
        Args:
            file_path: Path to file
            diff_content: Unified diff content
            
        Returns:
            Tuple of (success, error_message)
        """
        # Extract diff from markdown if needed
        diff = self.extract_diff_from_markdown(diff_content)
        if not diff:
            diff = diff_content
        
        # Parse diff
        hunks = self.parse_unified_diff(diff)
        
        if not hunks:
            return False, "No valid diff hunks found"
        
        # For now, apply first hunk to specified file
        # In full implementation, you'd handle multiple files
        target_file = hunks[0][0] if hunks[0][0] else file_path
        
        # Read current file
        current_content, error = self.file_handler.read_file(target_file)
        if error:
            return False, error
        
        # Apply changes
        lines = current_content.split('\n')
        new_lines = lines.copy()
        
        # Sort hunks by line number (reverse order to maintain indices)
        hunks.sort(key=lambda x: x[1], reverse=True)
        
        for hunk_file, old_start, old_count, hunk_lines in hunks:
            if hunk_file != target_file:
                continue
            
            # Apply hunk
            # Remove old lines
            for _ in range(old_count):
                if old_start - 1 < len(new_lines):
                    new_lines.pop(old_start - 1)
            
            # Insert new lines
            new_content_lines = []
            for line in hunk_lines[1:]:  # Skip @@ header
                if line.startswith('+') and not line.startswith('+++'):
                    new_content_lines.append(line[1:])
                elif line.startswith(' ') or line.startswith('-'):
                    # Context line or removed line
                    pass
            
            # Insert new lines
            for line in reversed(new_content_lines):
                new_lines.insert(old_start - 1, line)
        
        new_content = '\n'.join(new_lines)
        
        # Write file
        error = self.file_handler.write_file(target_file, new_content)
        if error:
            return False, error
        
        return True, None
    
    def edit_file(
        self,
        file_path: str,
        diff_content: str,
        show_preview: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        Edit a file with permission.
        
        Args:
            file_path: Path to file
            diff_content: Unified diff content
            show_preview: Whether to show diff preview
            
        Returns:
            Tuple of (success, error_message)
        """
        # Extract and format diff
        diff = self.extract_diff_from_markdown(diff_content)
        if not diff:
            diff = diff_content
        
        # Show preview
        if show_preview:
            self.formatter.print_diff(diff)
        
        # Request permission
        if not self.permissions.request_edit_permission(file_path, diff):
            return False, "Permission denied"
        
        # Find the actual file path (searches recursively)
        actual_file_path = self.file_handler.find_file(file_path)
        if actual_file_path is None:
            return False, f"File not found: {file_path}"
        
        # Apply diff
        success, error = self.apply_diff_to_file(str(actual_file_path), diff)
        
        if not success:
            return False, error
        
        self.formatter.print_success("Changes applied")
        return True, None
    
    def extract_file_content(self, content: str) -> Optional[Tuple[str, str]]:
        """
        Extract file content from markdown code block.
        
        Args:
            content: Markdown content that may contain file content
            
        Returns:
            Tuple of (file_path, file_content) or None if not found
        """
        # Pattern to match file creation code blocks: ```file:filename
        pattern = r'```file:([^\n]+)\n(.*?)```'
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            file_path = match.group(1).strip()
            file_content = match.group(2).strip()
            return file_path, file_content
        
        return None
    
    def extract_delete_file(self, content: str) -> Optional[str]:
        """
        Extract file path from delete markdown code block.
        
        Args:
            content: Markdown content that may contain delete instruction
            
        Returns:
            File path to delete or None if not found
        """
        # Pattern to match delete code blocks: ```delete:filename
        pattern = r'```delete:([^\n]+)```'
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            return match.group(1).strip()
        
        return None
    
    def create_file(
        self,
        file_path: str,
        file_content: str,
        show_preview: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        Create a new file with permission.
        
        Args:
            file_path: Path to file to create
            file_content: Content to write to file
            show_preview: Whether to show file preview
            
        Returns:
            Tuple of (success, error_message)
        """
        # Show preview
        if show_preview:
            self.formatter.print_info(f"New file: {file_path}")
            self.formatter.print_code_block(file_content, self._detect_language(file_path))
        
        # Request permission
        if not self.permissions.request_file_creation_permission(file_path, file_content if show_preview else None):
            return False, "Permission denied"
        
        # Write file
        error = self.file_handler.write_file(file_path, file_content)
        if error:
            return False, error
        
        self.formatter.print_success("File created")
        return True, None
    
    def delete_file(
        self,
        file_path: str,
        show_preview: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        Delete a file with permission.
        
        Args:
            file_path: Path to file to delete
            show_preview: Whether to show file info
            
        Returns:
            Tuple of (success, error_message)
        """
        # Validate file exists
        if not self.file_handler.file_exists(file_path):
            return False, f"File not found: {file_path}"
        
        # Show preview
        if show_preview:
            self.formatter.print_warning(f"This will delete: {file_path}")
        
        # Request permission
        if not self.permissions.request_permission(
            action="delete this file",
            description=f"This will permanently delete: {file_path}"
        ):
            return False, "Permission denied"
        
        # Find the actual file path (searches recursively)
        actual_file_path = self.file_handler.find_file(file_path)
        if actual_file_path is None:
            return False, f"File not found: {file_path}"
        
        # Delete file
        safe_path = actual_file_path
        
        try:
            safe_path.unlink()
        except (OSError, IOError) as e:
            return False, f"Error deleting file: {e}"
        
        self.formatter.print_success("File deleted")
        return True, None
    
    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        ext = Path(file_path).suffix.lower()
        lang_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.rb': 'ruby',
            '.cpp': 'cpp',
            '.c': 'c',
            '.h': 'c',
            '.hpp': 'cpp',
            '.html': 'html',
            '.css': 'css',
            '.json': 'json',
            '.xml': 'xml',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.md': 'markdown',
            '.sh': 'bash',
            '.bash': 'bash',
            '.zsh': 'bash',
        }
        return lang_map.get(ext, 'text')


# Global editor instance
_editor: Optional[DiffEditor] = None


def get_editor() -> DiffEditor:
    """Get the global editor instance."""
    global _editor
    if _editor is None:
        _editor = DiffEditor()
    return _editor

