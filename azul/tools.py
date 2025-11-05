"""Tool executor for agentic operations."""

from pathlib import Path
from typing import Optional, Tuple

from azul.file_handler import get_file_handler
from azul.editor import get_editor
from azul.tree_generator import generate_tree
from azul.formatter import get_formatter
from azul.sandbox import get_sandbox


class ToolExecutor:
    """Executes tools called by the AI agent."""
    
    def __init__(self, project_root: Path):
        """Initialize tool executor."""
        self.project_root = project_root
        self.file_handler = get_file_handler()
        self.editor = get_editor()
        self.formatter = get_formatter()
        self.sandbox = get_sandbox(project_root)
    
    def execute_tree(self) -> str:
        """
        Execute tree() tool - display directory structure.
        
        Returns:
            Formatted tree string
        """
        return generate_tree(self.project_root, max_depth=3)
    
    def execute_read(self, file_path: str) -> str:
        """
        Execute read() tool - read file content.
        
        Args:
            file_path: Path to file to read
            
        Returns:
            Formatted file content or error message
        """
        content, error = self.file_handler.read_file(file_path)
        
        if error:
            return f"Error: {error}"
        
        # Format for AI consumption
        return f"--- file: {file_path} ---\n{content}"
    
    def execute_write(self, file_path: str, content: str) -> str:
        """
        Execute write() tool - create or overwrite file.
        Note: This is for the agent loop - final actions still require user confirmation.
        
        Args:
            file_path: Path to file
            content: Content to write
            
        Returns:
            Success or error message
        """
        # Validate path
        safe_path = self.sandbox.get_safe_path(file_path)
        if safe_path is None:
            return f"Error: File path is outside the project directory: {file_path}"
        
        # For agent loop, we'll prepare the file but not write yet
        # The actual write will happen with user confirmation later
        return f"Prepared to write: {file_path} ({len(content)} characters)"
    
    def execute_diff(self, file_path: str, diff_content: str) -> str:
        """
        Execute diff() tool - apply unified diff.
        Note: This is for the agent loop - final actions still require user confirmation.
        
        Args:
            file_path: Path to file to modify
            diff_content: Unified diff content
            
        Returns:
            Success or error message
        """
        # Validate path
        safe_path = self.sandbox.get_safe_path(file_path)
        if safe_path is None:
            return f"Error: File path is outside the project directory: {file_path}"
        
        # Check if file exists
        if not self.file_handler.file_exists(file_path):
            return f"Error: File not found: {file_path}"
        
        # For agent loop, validate the diff but don't apply yet
        # The actual edit will happen with user confirmation later
        return f"Prepared to apply diff to: {file_path}"
    
    def execute_delete(self, file_path: str) -> str:
        """
        Execute delete() tool - delete file or directory.
        Note: This is for the agent loop - final actions still require user confirmation.
        
        Args:
            file_path: Path to file or directory to delete
            
        Returns:
            Success or error message
        """
        # Validate path
        safe_path = self.sandbox.get_safe_path(file_path)
        if safe_path is None:
            return f"Error: Path is outside the project directory: {file_path}"
        
        # Check if path exists (file or directory)
        if not self.file_handler.path_exists(file_path):
            return f"Error: File or directory not found: {file_path}"
        
        # For agent loop, prepare deletion but don't delete yet
        # The actual deletion will happen with user confirmation later
        return f"Prepared to delete: {file_path}"
    
    def execute_exec(self, command: str, background: bool = False) -> str:
        """
        Execute exec() tool - run shell command.
        Note: This is a placeholder for the agent loop - actual execution happens in REPL with confirmation.
        
        Args:
            command: Shell command to execute
            background: Whether to run in background (for long-running commands)
            
        Returns:
            Placeholder message
        """
        # This is just a placeholder - actual execution happens in REPL with user confirmation
        return f"Prepared to execute: {command} (background={background})"
    
    def execute_tool(self, tool_name: str, arguments: dict) -> str:
        """
        Execute a tool call.
        
        Args:
            tool_name: Name of the tool
            arguments: Tool arguments
            
        Returns:
            Tool output string
        """
        if tool_name == "tree":
            return self.execute_tree()
        
        elif tool_name == "read":
            file_path = arguments.get('file_path')
            if not file_path:
                return "Error: read() requires file_path argument"
            return self.execute_read(file_path)
        
        elif tool_name == "write":
            file_path = arguments.get('file_path')
            content = arguments.get('content', '')
            if not file_path:
                return "Error: write() requires file_path argument"
            return self.execute_write(file_path, content)
        
        elif tool_name == "diff":
            file_path = arguments.get('file_path')
            # Try both 'content' and 'diff_content' for compatibility
            diff_content = arguments.get('content') or arguments.get('diff_content', '')
            if not file_path:
                return "Error: diff() requires file_path argument"
            if not diff_content:
                return "Error: diff() requires diff_content argument"
            return self.execute_diff(file_path, diff_content)
        
        elif tool_name == "delete":
            file_path = arguments.get('file_path')
            if not file_path:
                return "Error: delete() requires file_path argument"
            return self.execute_delete(file_path)
        
        elif tool_name == "exec":
            command = arguments.get('command')
            background = arguments.get('background', False)
            if not command:
                return "Error: exec() requires command argument"
            return self.execute_exec(command, background)
        
        else:
            return f"Error: Unknown tool '{tool_name}'. Available tools: tree, read, write, diff, delete, exec"

