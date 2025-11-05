"""Command handlers for @ commands."""

import sys
from pathlib import Path
from typing import Optional, Tuple

from azul.command_parser import ParsedCommand
from azul.llama_client import get_llama_client
from azul.session_manager import get_session_manager
from azul.file_handler import get_file_handler
from azul.editor import get_editor
from azul.formatter import get_formatter


class CommandHandler:
    """Handles @ commands."""
    
    def __init__(self):
        """Initialize command handler."""
        self.llama = get_llama_client()
        self.session = get_session_manager()
        self.file_handler = get_file_handler()
        self.editor = get_editor()
        self.formatter = get_formatter()
        self.last_referenced_file: Optional[str] = None
        self._repl_instance = None  # Will be set by REPL
    
    def set_repl(self, repl_instance):
        """Set the REPL instance for directory changes."""
        self._repl_instance = repl_instance
    
    def handle_command(self, parsed: ParsedCommand) -> Tuple[bool, Optional[str]]:
        """
        Handle a parsed command.
        
        Args:
            parsed: Parsed command
            
        Returns:
            Tuple of (handled, message)
        """
        cmd = parsed.command
        
        if cmd == 'model':
            return self.handle_model(parsed.args)
        elif cmd == 'edit':
            return self.handle_edit(parsed.args)
        elif cmd == 'create':
            return self.handle_create(parsed.args)
        elif cmd == 'delete':
            return self.handle_delete(parsed.args)
        elif cmd == 'read':
            return self.handle_read(parsed.args)
        elif cmd == 'ls':
            return self.handle_ls()
        elif cmd == 'path':
            return self.handle_path()
        elif cmd == 'cd':
            return self.handle_cd(parsed.args)
        elif cmd == 'clear':
            return self.handle_clear()
        elif cmd == 'reset':
            return self.handle_reset()
        elif cmd == 'help':
            return self.handle_help()
        elif cmd == 'exit' or cmd == 'quit':
            return self.handle_exit()
        elif cmd == 'unknown':
            return False, f"Unknown command: {parsed.raw_input}. Type @help for available commands."
        else:
            return False, f"Command not implemented: {cmd}"
    
    def handle_model(self, args: list) -> Tuple[bool, Optional[str]]:
        """Handle @model command."""
        # Filter out None values from regex optional groups
        args = [a for a in args if a is not None]
        
        if not args:
            # Show current model
            current_model = self.llama.get_model()
            if hasattr(self.llama, '_model_path') and self.llama._model_path:
                full_path = self.llama._model_path
                self.formatter.console.print(f"[bold]Current model:[/bold] {current_model}")
                self.formatter.console.print(f"[dim]Path: {full_path}[/dim]")
            else:
                self.formatter.print_info(f"Current model: {current_model}")
            return True, None
        
        model_path = args[0]
        # Try to load the model
        success = self.llama.set_model_path(model_path)
        if success:
            return True, None
        else:
            return False, f"Failed to load model: {model_path}"
    
    def handle_edit(self, args: list) -> Tuple[bool, Optional[str]]:
        """Handle @edit command."""
        if len(args) < 2:
            return False, "Usage: @edit <file> <instruction>"
        
        file_path = args[0]
        instruction = args[1]
        
        # Find the actual file (searches recursively)
        actual_path = self.file_handler.find_file(file_path)
        if actual_path is None:
            return False, f"File not found: {file_path} (searched in project directory)"
        
        # Use the found path
        file_path = str(actual_path.relative_to(Path.cwd())) if actual_path.is_relative_to(Path.cwd()) else str(actual_path)
        
        # Read file for context
        file_content, error = self.file_handler.read_file(file_path)
        if error:
            return False, error
        
        # Build prompt for AI
        prompt = f"Edit the file {file_path} with the following instruction:\n\n{instruction}\n\nCurrent file content:\n```\n{file_content}\n```\n\nProvide the changes as a unified diff in a markdown code block labeled 'diff'."
        
        # Get AI response
        status = self.formatter.show_status("AZUL is thinking...")
        status.__enter__()
        try:
            stream = self.llama.stream_chat(prompt, self.session.get_recent_history())
            # Get first token to stop status
            first_token = next(stream, None)
            if first_token:
                status.__exit__(None, None, None)  # Stop status
                # Stream tokens directly for maximum speed
                response = first_token
                sys.stdout.write(first_token)
                sys.stdout.flush()
                # Stream remaining tokens with minimal overhead
                for token in stream:
                    response += token
                    sys.stdout.write(token)
                    sys.stdout.flush()
                sys.stdout.write('\n')
                sys.stdout.flush()
            else:
                status.__exit__(None, None, None)
                response = ""
        except StopIteration:
            status.__exit__(None, None, None)
            response = ""
        except Exception as e:
            status.__exit__(None, None, None)
            self.formatter.print_error(f"Error: {e}")
            response = ""
        
        # Extract and apply diff
        success, error = self.editor.edit_file(file_path, response)
        
        if success:
            # Add to session
            self.session.add_message("user", f"@edit {file_path} {instruction}")
            self.session.add_message("assistant", response)
            return True, None
        else:
            return False, error
    
    def handle_read(self, args: list) -> Tuple[bool, Optional[str]]:
        """Handle @read command."""
        if not args:
            return False, "Usage: @read <file>"
        
        file_path = args[0]
        
        # Find the actual file (searches recursively)
        actual_path = self.file_handler.find_file(file_path)
        if actual_path:
            # Show the relative path if found
            rel_path = actual_path.relative_to(Path.cwd()) if actual_path.is_relative_to(Path.cwd()) else actual_path
            self.formatter.print_info(f"Found: {rel_path}")
            file_path = str(rel_path)
        
        self.last_referenced_file = file_path
        
        content, error = self.file_handler.read_file(file_path)
        if error:
            return False, error
        
        self.formatter.print_code_block(content, "text")
        return True, None
    
    def handle_ls(self) -> Tuple[bool, Optional[str]]:
        """Handle @ls command - list files in current directory."""
        from pathlib import Path
        import os
        
        current_dir = Path.cwd()
        try:
            files = []
            dirs = []
            
            for item in sorted(current_dir.iterdir()):
                # Skip hidden files/dirs (starting with .)
                if item.name.startswith('.'):
                    continue
                
                if item.is_file():
                    files.append(item.name)
                elif item.is_dir():
                    dirs.append(item.name + '/')
            
            # Display directories first, then files
            all_items = dirs + files
            
            if all_items:
                self.formatter.console.print("\n[bold]Files and directories:[/bold]")
                # Display in columns for better readability
                for item in all_items:
                    if item.endswith('/'):
                        self.formatter.console.print(f"  [cyan]{item}[/cyan]")
                    else:
                        self.formatter.console.print(f"  {item}")
                self.formatter.console.print()
            else:
                self.formatter.print_info("Directory is empty (excluding hidden files)")
            
            return True, None
        except Exception as e:
            return False, f"Error listing files: {e}"
    
    def handle_path(self) -> Tuple[bool, Optional[str]]:
        """Handle @path command - show current directory path."""
        from pathlib import Path
        
        current_path = Path.cwd().resolve()
        self.formatter.console.print(f"\n[bold]Current directory:[/bold] [cyan]{current_path}[/cyan]\n")
        return True, None
    
    def handle_cd(self, args: list) -> Tuple[bool, Optional[str]]:
        """Handle @cd command - change directory."""
        if not args:
            return False, "Usage: @cd <directory>"
        
        target_dir = args[0]
        
        # If we have REPL instance, use its method to change directory
        if self._repl_instance:
            return self._repl_instance.change_directory(target_dir)
        
        # Fallback: just change directory without updating components
        import os
        from pathlib import Path
        
        try:
            # Resolve the target path
            if Path(target_dir).is_absolute():
                new_dir = Path(target_dir)
            else:
                new_dir = Path.cwd() / target_dir
            
            new_dir = new_dir.resolve()
            
            if not new_dir.exists():
                return False, f"Directory does not exist: {target_dir}"
            
            if not new_dir.is_dir():
                return False, f"Path is not a directory: {target_dir}"
            
            # Change directory
            os.chdir(new_dir)
            self.formatter.print_success(f"Changed directory to: {new_dir}")
            return True, None
        except Exception as e:
            return False, f"Error changing directory: {e}"
    
    def handle_clear(self) -> Tuple[bool, Optional[str]]:
        """Handle @clear command - clear terminal screen."""
        import os
        os.system('clear' if os.name != 'nt' else 'cls')
        return True, None
    
    def handle_reset(self) -> Tuple[bool, Optional[str]]:
        """Handle @reset command - clear conversation history."""
        self.session.clear_history()
        self.formatter.print_success("Conversation history cleared")
        return True, None
    
    def handle_create(self, args: list) -> Tuple[bool, Optional[str]]:
        """Handle @create command."""
        if len(args) < 2:
            return False, "Usage: @create <file> <instruction>"
        
        file_path = args[0]
        instruction = args[1]
        
        # Build prompt for AI
        prompt = f"Create a new file {file_path} with the following instruction:\n\n{instruction}\n\nProvide the complete file content in a markdown code block labeled 'file:{file_path}'."
        
        # Get AI response
        status = self.formatter.show_status("AZUL is thinking...")
        status.__enter__()
        try:
            stream = self.llama.stream_chat(prompt, self.session.get_recent_history())
            # Get first token to stop status
            first_token = next(stream, None)
            if first_token:
                status.__exit__(None, None, None)  # Stop status
                # Stream tokens directly for maximum speed
                response = first_token
                sys.stdout.write(first_token)
                sys.stdout.flush()
                # Stream remaining tokens with minimal overhead
                for token in stream:
                    response += token
                    sys.stdout.write(token)
                    sys.stdout.flush()
                sys.stdout.write('\n')
                sys.stdout.flush()
            else:
                status.__exit__(None, None, None)
                response = ""
        except StopIteration:
            status.__exit__(None, None, None)
            response = ""
        except Exception as e:
            status.__exit__(None, None, None)
            self.formatter.print_error(f"Error: {e}")
            response = ""
        
        # Extract and create file
        file_info = self.editor.extract_file_content(response)
        if file_info:
            file_path_from_response, file_content = file_info
            # Use file path from command if provided, otherwise from response
            target_path = file_path if file_path else file_path_from_response
            success, error = self.editor.create_file(target_path, file_content)
            
            if success:
                # Add to session
                self.session.add_message("user", f"@create {file_path} {instruction}")
                self.session.add_message("assistant", response)
                return True, None
            else:
                return False, error
        else:
            return False, "Could not extract file content from response. Make sure the model provides content in ```file:filename format."
    
    def handle_delete(self, args: list) -> Tuple[bool, Optional[str]]:
        """Handle @delete command."""
        if not args:
            return False, "Usage: @delete <file>"
        
        file_path = args[0]
        
        # Find the actual file (searches recursively)
        actual_path = self.file_handler.find_file(file_path)
        if actual_path:
            # Use the found path
            file_path = str(actual_path.relative_to(Path.cwd())) if actual_path.is_relative_to(Path.cwd()) else str(actual_path)
        
        # Delete file
        success, error = self.editor.delete_file(file_path)
        
        if success:
            # Add to session
            self.session.add_message("user", f"@delete {file_path}")
            self.session.add_message("assistant", f"Deleted {file_path}")
            return True, None
        else:
            return False, error
    
    def handle_help(self) -> Tuple[bool, Optional[str]]:
        """Handle @help command."""
        help_text = """
Available @ commands:

  @model [path]          - Change model path (or show current model)
  @edit <file> <inst>    - Edit a file with instruction
  @create <file> <inst>  - Create a new file with instruction
  @delete <file>         - Delete a file
  @read <file>           - Read and display a file
  @ls                    - List files in current directory
  @path                  - Show current directory path
  @cd <dir>              - Change directory
  @clear                 - Clear terminal screen
  @reset                 - Clear conversation history
  @help                  - Show this help message
  @exit / @quit          - Exit AZUL

Everything else is treated as a natural language prompt to the AI.
"""
        self.formatter.console.print(help_text)
        return True, None
    
    def handle_exit(self) -> Tuple[bool, Optional[str]]:
        """Handle @exit/@quit command."""
        return True, "exit"  # Special return value to signal exit


# Global command handler instance
_command_handler: Optional[CommandHandler] = None


def get_command_handler() -> CommandHandler:
    """Get the global command handler instance."""
    global _command_handler
    if _command_handler is None:
        _command_handler = CommandHandler()
    return _command_handler

