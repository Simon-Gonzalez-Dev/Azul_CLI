"""File system tools for the agent."""

import os
from pathlib import Path
from typing import Optional


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

