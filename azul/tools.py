"""File system tools for the agent."""

import os
from pathlib import Path
from typing import Optional


def list_directory_tool(directory_path: str = ".") -> str:
    """
    List the contents of a directory.
    
    Args:
        directory_path: Path to the directory to list (default: current directory)
        
    Returns:
        Directory listing as formatted string, or error message
    """
    try:
        path = Path(directory_path).resolve()
        
        if not path.exists():
            return f"Error: Directory not found: {directory_path}"
        
        if not path.is_dir():
            return f"Error: Path is not a directory: {directory_path}"
        
        items = []
        dirs = []
        files = []
        
        for item in sorted(path.iterdir()):
            if item.is_dir():
                dirs.append(f"{item.name}/")
            else:
                files.append(item.name)
        
        items = dirs + files
        
        if not items:
            return f"Directory {directory_path} is empty."
        
        result = f"Contents of {directory_path}:\n"
        result += "\n".join(f"  {item}" for item in items)
        return result
    
    except PermissionError:
        return f"Error: Permission denied reading directory: {directory_path}"
    except Exception as e:
        return f"Error listing directory {directory_path}: {str(e)}"


def read_file_tool(file_path: str) -> str:
    """
    Read a file from the filesystem.
    
    Args:
        file_path: Path to the file to read
        
    Returns:
        File content as string with metadata, or error message
    """
    try:
        path = Path(file_path).resolve()
        
        if not path.exists():
            return f"Error: File not found: {file_path}"
        
        if not path.is_file():
            return f"Error: Path is not a file: {file_path}"
        
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        
        return f"File: {file_path}\nSize: {len(content)} characters\n\n{content}"
    
    except PermissionError:
        return f"Error: Permission denied reading file: {file_path}"
    except Exception as e:
        return f"Error reading file {file_path}: {str(e)}"


def write_file_nano_tool(file_path: str, new_content: str) -> str:
    """
    Create or overwrite a file with new content.
    
    Args:
        file_path: Path to the file to create/overwrite
        new_content: Content to write to the file
        
    Returns:
        Success or error message
    """
    try:
        path = Path(file_path).resolve()
        
        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        
        return f"Successfully wrote to {file_path}"
    
    except PermissionError:
        return f"Error: Permission denied writing to file: {file_path}"
    except Exception as e:
        return f"Error writing file {file_path}: {str(e)}"


def delete_file_tool(file_path: str) -> str:
    """
    Delete a file from the filesystem.
    
    Args:
        file_path: Path to the file to delete
        
    Returns:
        Success or error message
    """
    try:
        path = Path(file_path).resolve()
        
        if not path.exists():
            return f"Error: File not found: {file_path}"
        
        if not path.is_file():
            return f"Error: Path is not a file: {file_path}"
        
        path.unlink()
        return f"Successfully deleted {file_path}"
    
    except PermissionError:
        return f"Error: Permission denied deleting file: {file_path}"
    except Exception as e:
        return f"Error deleting file {file_path}: {str(e)}"


def respond_to_user_tool(message: str) -> str:
    """
    Signal that the agent has completed its task and should respond to the user.
    
    Args:
        message: The final response message for the user
        
    Returns:
        Formatted response string
    """
    return f"RESPOND: {message}"

