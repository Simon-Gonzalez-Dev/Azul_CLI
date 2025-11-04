"""Command handlers for @ commands."""

from typing import Optional, Tuple

from azul.command_parser import ParsedCommand
from azul.ollama_client import get_ollama_client
from azul.session_manager import get_session_manager
from azul.file_handler import get_file_handler
from azul.context import get_context_manager
from azul.editor import get_editor
from azul.formatter import get_formatter


class CommandHandler:
    """Handles @ commands."""
    
    def __init__(self):
        """Initialize command handler."""
        self.ollama = get_ollama_client()
        self.session = get_session_manager()
        self.file_handler = get_file_handler()
        self.context = get_context_manager()
        self.editor = get_editor()
        self.formatter = get_formatter()
        self.last_referenced_file: Optional[str] = None
    
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
        elif cmd == 'read':
            return self.handle_read(parsed.args)
        elif cmd == 'clear':
            return self.handle_clear()
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
        if not args:
            current_model = self.ollama.get_model()
            self.formatter.print_info(f"Current model: {current_model}")
            return True, None
        
        model_name = args[0]
        success = self.ollama.set_model(model_name)
        return success, None
    
    def handle_edit(self, args: list) -> Tuple[bool, Optional[str]]:
        """Handle @edit command."""
        if len(args) < 2:
            return False, "Usage: @edit <file> <instruction>"
        
        file_path = args[0]
        instruction = args[1]
        
        # Validate file exists
        if not self.file_handler.file_exists(file_path):
            return False, f"File not found: {file_path}"
        
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
            stream = self.ollama.stream_chat(prompt, self.session.get_recent_history())
            # Get first token to stop status
            first_token = next(stream, None)
            if first_token:
                status.__exit__(None, None, None)  # Stop status
                self.formatter.console.print(first_token, end="", flush=True)
                # Stream remaining tokens
                response = first_token + self.formatter.stream_response(stream)
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
        self.last_referenced_file = file_path
        
        content, error = self.file_handler.read_file(file_path)
        if error:
            return False, error
        
        self.formatter.print_code_block(content, "text")
        return True, None
    
    def handle_clear(self) -> Tuple[bool, Optional[str]]:
        """Handle @clear command."""
        self.session.clear_history()
        self.formatter.print_success("Conversation history cleared")
        return True, None
    
    def handle_help(self) -> Tuple[bool, Optional[str]]:
        """Handle @help command."""
        help_text = """
Available @ commands:

  @model [name]          - Change Ollama model (or show current model)
  @edit <file> <inst>    - Edit a file with instruction
  @read <file>           - Read and display a file
  @clear                 - Clear conversation history
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

