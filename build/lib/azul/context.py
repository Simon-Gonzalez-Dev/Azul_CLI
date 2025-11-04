"""Intelligent context management with Tree-sitter parsing."""

import re
from pathlib import Path
from typing import Optional, List, Dict, Set
from dataclasses import dataclass

try:
    import tree_sitter
    from tree_sitter import Language, Parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

from azul.file_handler import get_file_handler
from azul.sandbox import get_sandbox


@dataclass
class FunctionInfo:
    """Information about a function."""
    name: str
    start_line: int
    end_line: int
    signature: str
    content: str


@dataclass
class ClassInfo:
    """Information about a class."""
    name: str
    start_line: int
    end_line: int
    content: str


class ContextManager:
    """Manages intelligent context injection for code."""
    
    def __init__(self):
        """Initialize context manager."""
        self.file_handler = get_file_handler()
        self.sandbox = get_sandbox()
        self._parsers: Dict[str, Parser] = {}
        self._last_referenced_files: List[str] = []
    
    def _get_parser(self, language: str) -> Optional[Parser]:
        """Get or create a parser for a language."""
        if not TREE_SITTER_AVAILABLE:
            return None
        
        if language in self._parsers:
            return self._parsers[language]
        
        # For now, we'll use a simple approach
        # In production, you'd load language grammars
        # This is a placeholder - tree-sitter setup requires compiled grammars
        return None
    
    def extract_function(
        self,
        file_path: str,
        function_name: str
    ) -> Optional[FunctionInfo]:
        """
        Extract a specific function from a file.
        
        Args:
            file_path: Path to file
            function_name: Name of function to extract
            
        Returns:
            FunctionInfo if found, None otherwise
        """
        content, error = self.file_handler.read_file(file_path)
        if error or not content:
            return None
        
        # Simple regex-based extraction (fallback when tree-sitter not available)
        # Pattern to match function definitions
        pattern = rf'def\s+{re.escape(function_name)}\s*\([^)]*\)\s*:'
        match = re.search(pattern, content)
        
        if not match:
            return None
        
        start_line = content[:match.start()].count('\n') + 1
        start_pos = match.start()
        
        # Find the end of the function (next function/class or end of file)
        # Simple indentation-based approach
        lines = content[start_pos:].split('\n')
        function_lines = [lines[0]]  # First line (def ...)
        
        if len(lines) > 1:
            # Determine base indentation
            base_indent = len(lines[1]) - len(lines[1].lstrip())
            
            for line in lines[1:]:
                if line.strip() == '':
                    function_lines.append(line)
                    continue
                
                current_indent = len(line) - len(line.lstrip())
                # If we hit something at same or less indentation, stop
                if current_indent <= base_indent and line.strip():
                    break
                
                function_lines.append(line)
        
        function_content = '\n'.join(function_lines)
        end_line = start_line + len(function_lines) - 1
        
        # Extract signature (first line)
        signature = function_lines[0].strip()
        
        return FunctionInfo(
            name=function_name,
            start_line=start_line,
            end_line=end_line,
            signature=signature,
            content=function_content
        )
    
    def extract_functions_from_file(self, file_path: str) -> List[FunctionInfo]:
        """
        Extract all functions from a file.
        
        Args:
            file_path: Path to file
            
        Returns:
            List of FunctionInfo objects
        """
        content, error = self.file_handler.read_file(file_path)
        if error or not content:
            return []
        
        functions = []
        pattern = r'def\s+(\w+)\s*\([^)]*\)\s*:'
        
        for match in re.finditer(pattern, content):
            func_name = match.group(1)
            func_info = self.extract_function(file_path, func_name)
            if func_info:
                functions.append(func_info)
        
        return functions
    
    def get_function_signatures(self, file_path: str) -> List[str]:
        """
        Get just the signatures of all functions in a file.
        
        Args:
            file_path: Path to file
            
        Returns:
            List of function signatures
        """
        functions = self.extract_functions_from_file(file_path)
        return [f.signature for f in functions]
    
    def detect_file_references(self, text: str) -> List[str]:
        """
        Detect file references in text.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of file paths mentioned
        """
        # Patterns to detect file references
        patterns = [
            r'file\s+["\']([^"\']+)["\']',  # file "path"
            r'in\s+["\']([^"\']+\.(py|js|ts|java|go|rs|rb))["\']',  # in "file.py"
            r'`([^`]+\.(py|js|ts|java|go|rs|rb))`',  # `file.py`
            r'([a-zA-Z0-9_/]+\.(py|js|ts|java|go|rs|rb))',  # file.py
        ]
        
        files = set()
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    file_path = match[0]
                else:
                    file_path = match
                
                # Validate file exists
                if self.file_handler.file_exists(file_path):
                    files.add(file_path)
        
        return list(files)
    
    def detect_function_references(self, text: str, file_path: Optional[str] = None) -> List[str]:
        """
        Detect function references in text.
        
        Args:
            text: Text to analyze
            file_path: Optional file path to search in
            
        Returns:
            List of function names mentioned
        """
        # Pattern to detect function names
        patterns = [
            r'function\s+(\w+)',  # function name
            r'def\s+(\w+)',  # def name
            r'(\w+)\s*\(',  # name(
        ]
        
        functions = set()
        for pattern in patterns:
            matches = re.findall(pattern, text)
            functions.update(matches)
        
        return list(functions)
    
    def build_context(
        self,
        user_message: str,
        include_files: Optional[List[str]] = None
    ) -> str:
        """
        Build context string for AI prompt.
        
        Args:
            user_message: User's message
            include_files: Optional list of files to include
            
        Returns:
            Context string to prepend to prompt
        """
        context_parts = []
        
        # Detect file references
        referenced_files = self.detect_file_references(user_message)
        if include_files:
            referenced_files.extend(include_files)
        
        # Remove duplicates
        referenced_files = list(set(referenced_files))
        
        # For each referenced file, include relevant parts
        for file_path in referenced_files:
            # Detect function references
            func_refs = self.detect_function_references(user_message, file_path)
            
            if func_refs:
                # Extract only referenced functions
                for func_name in func_refs:
                    func_info = self.extract_function(file_path, func_name)
                    if func_info:
                        context_parts.append(f"\n--- {file_path} (function: {func_name}) ---\n")
                        context_parts.append(func_info.content)
            else:
                # Include file signatures or full file if small
                signatures = self.get_function_signatures(file_path)
                if signatures:
                    context_parts.append(f"\n--- {file_path} (signatures) ---\n")
                    context_parts.append('\n'.join(signatures))
                else:
                    # Include full file if it's small
                    content, _ = self.file_handler.read_file(file_path)
                    if content and len(content) < 2000:
                        context_parts.append(f"\n--- {file_path} ---\n")
                        context_parts.append(content)
        
        self._last_referenced_files = referenced_files
        return '\n'.join(context_parts)
    
    def get_last_referenced_files(self) -> List[str]:
        """Get list of files referenced in last context build."""
        return self._last_referenced_files.copy()


# Global context manager instance
_context_manager: Optional[ContextManager] = None


def get_context_manager() -> ContextManager:
    """Get the global context manager instance."""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager

