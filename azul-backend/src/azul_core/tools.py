"""LangChain tools for file operations and shell execution."""

import os
import subprocess
from pathlib import Path
from typing import Optional, Callable
from langchain_core.tools import tool


# Global callback for tool events
_tool_callback: Optional[Callable[[str, str], None]] = None


def set_tool_callback(callback: Optional[Callable[[str, str], None]]):
    """Set the global tool callback for notifications."""
    global _tool_callback
    _tool_callback = callback


def _notify(event_type: str, message: str):
    """Notify via callback if set."""
    if _tool_callback:
        _tool_callback(event_type, message)


@tool
def read_file(file_path: str) -> str:
    """Read the contents of a file.
    
    Args:
        file_path: Path to the file to read
        
    Returns:
        File contents or error message
    """
    try:
        path = Path(file_path).resolve()
        _notify("tool_start", f"Reading file: {path}")
        
        if not path.exists():
            return f"Error: File not found: {path}"
        
        if not path.is_file():
            return f"Error: Not a file: {path}"
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        _notify("tool_end", f"Read {len(content)} characters from {path}")
        return content
    
    except PermissionError:
        return f"Error: Permission denied: {file_path}"
    except UnicodeDecodeError:
        return f"Error: Cannot read binary file: {file_path}"
    except Exception as e:
        return f"Error reading file: {str(e)}"


@tool
def write_file(file_path: str, content: str) -> str:
    """Write content to a file. Creates the file if it doesn't exist, overwrites if it does.
    
    Args:
        file_path: Path to the file to write
        content: Content to write to the file
        
    Returns:
        Success or error message
    """
    try:
        path = Path(file_path).resolve()
        _notify("tool_start", f"Writing to file: {path}")
        
        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        _notify("tool_end", f"Successfully wrote {len(content)} characters to {path}")
        return f"Successfully wrote to {path}"
    
    except PermissionError:
        return f"Error: Permission denied: {file_path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"


@tool
def delete_file(file_path: str) -> str:
    """Delete a file.
    
    Args:
        file_path: Path to the file to delete
        
    Returns:
        Success or error message
    """
    try:
        path = Path(file_path).resolve()
        _notify("tool_start", f"Deleting file: {path}")
        
        if not path.exists():
            return f"Error: File not found: {path}"
        
        if not path.is_file():
            return f"Error: Not a file (cannot delete directories): {path}"
        
        path.unlink()
        
        _notify("tool_end", f"Successfully deleted {path}")
        return f"Successfully deleted {path}"
    
    except PermissionError:
        return f"Error: Permission denied: {file_path}"
    except Exception as e:
        return f"Error deleting file: {str(e)}"


@tool
def execute_shell(command: str) -> str:
    """Execute a shell command and return the output.
    
    Args:
        command: Shell command to execute
        
    Returns:
        Command output or error message
    """
    try:
        _notify("tool_start", f"Executing command: {command}")
        
        # Security check: prevent dangerous commands
        dangerous_patterns = ['rm -rf /', 'mkfs', 'dd if=', ':(){:|:&};:']
        if any(pattern in command.lower() for pattern in dangerous_patterns):
            return "Error: Dangerous command blocked"
        
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        output = []
        if result.stdout:
            output.append(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            output.append(f"STDERR:\n{result.stderr}")
        
        output.append(f"\nExit code: {result.returncode}")
        
        full_output = "\n".join(output)
        _notify("tool_end", f"Command completed with exit code {result.returncode}")
        
        return full_output
    
    except subprocess.TimeoutExpired:
        return "Error: Command timed out (30s limit)"
    except Exception as e:
        return f"Error executing command: {str(e)}"


@tool
def list_directory(directory_path: str = ".") -> str:
    """List contents of a directory.
    
    Args:
        directory_path: Path to the directory to list (default: current directory)
        
    Returns:
        Directory listing or error message
    """
    try:
        path = Path(directory_path).resolve()
        _notify("tool_start", f"Listing directory: {path}")
        
        if not path.exists():
            return f"Error: Directory not found: {path}"
        
        if not path.is_dir():
            return f"Error: Not a directory: {path}"
        
        items = []
        for item in sorted(path.iterdir()):
            item_type = "DIR " if item.is_dir() else "FILE"
            items.append(f"{item_type} {item.name}")
        
        if not items:
            result = f"Directory is empty: {path}"
        else:
            result = f"Contents of {path}:\n" + "\n".join(items)
        
        _notify("tool_end", f"Listed {len(items)} items in {path}")
        return result
    
    except PermissionError:
        return f"Error: Permission denied: {directory_path}"
    except Exception as e:
        return f"Error listing directory: {str(e)}"


# Export all tools as a list
ALL_TOOLS = [
    read_file,
    write_file,
    delete_file,
    execute_shell,
    list_directory
]

