"""Interactive REPL for AZUL CLI."""

from typing import Optional
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from pathlib import Path

from azul.command_parser import get_command_parser, ParsedCommand
from azul.commands.handlers import get_command_handler
from azul.ollama_client import get_ollama_client
from azul.session_manager import get_session_manager
from azul.context import get_context_manager
from azul.formatter import get_formatter
from azul.editor import get_editor
from azul.file_monitor import get_file_monitor


class REPL:
    """Interactive Read-Eval-Print Loop."""
    
    def __init__(self, project_root: Optional[Path] = None):
        """Initialize REPL."""
        self.project_root = project_root or Path.cwd()
        
        # Initialize sandbox first with project root
        from azul.sandbox import get_sandbox
        get_sandbox(self.project_root)
        
        # Now initialize other components
        self.command_parser = get_command_parser()
        self.command_handler = get_command_handler()
        self.ollama = get_ollama_client()
        self.session = get_session_manager(self.project_root)
        self.context = get_context_manager()
        self.formatter = get_formatter()
        self.editor = get_editor()
        
        # Setup prompt session
        command_completer = WordCompleter(
            ['@model', '@edit', '@read', '@clear', '@help', '@exit', '@quit'],
            ignore_case=True
        )
        
        history_file = Path.home() / ".azul" / "history"
        history_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.session_prompt = PromptSession(
            completer=command_completer,
            history=FileHistory(str(history_file)),
            multiline=True
        )
        
        # Setup file monitoring
        self.file_monitor = get_file_monitor(self.project_root)
        self.file_monitor.start(self._on_file_change)
        
        self.running = True
        self.last_referenced_file: Optional[str] = None
    
    def _on_file_change(self, file_path: str) -> None:
        """Handle file change notification (non-intrusive)."""
        # Store for later display
        pass
    
    def _check_file_notifications(self) -> None:
        """Check and display file change notifications."""
        notifications = self.file_monitor.get_notifications()
        if notifications:
            for file_path in notifications[:3]:  # Limit to 3 notifications
                self.formatter.print_info(
                    f"File modified: {file_path}. Say 'review it' or '@read {file_path}' to see changes."
                )
    
    def _handle_command(self, parsed: ParsedCommand) -> bool:
        """
        Handle a command.
        
        Returns:
            True if should continue, False if should exit
        """
        handled, message = self.command_handler.handle_command(parsed)
        
        if message == "exit":
            return False
        
        if message:
            if handled:
                self.formatter.print_info(message)
            else:
                self.formatter.print_error(message)
        
        return True
    
    def _handle_prompt(self, user_input: str) -> None:
        """Handle a natural language prompt."""
        # Build context
        context_str = self.context.build_context(user_input)
        
        # Add context to prompt if available
        if context_str:
            full_prompt = f"{context_str}\n\nUser: {user_input}\n\nAssistant:"
        else:
            full_prompt = user_input
        
        # Add to session
        self.session.add_message("user", user_input)
        
        # Stream response
        # Show status briefly, then stream tokens
        status = self.formatter.show_status("AZUL is thinking...")
        status.__enter__()
        try:
            stream = self.ollama.stream_chat(
                full_prompt,
                self.session.get_recent_history()
            )
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
            import traceback
            self.formatter.print_error(f"Error: {e}")
            self.formatter.print_error(traceback.format_exc())
            response = ""
        
        # Add response to session
        self.session.add_message("assistant", response)
        
        # Check if response contains diff (for natural language edits)
        if "```diff" in response or "--- a/" in response:
            # Extract file references from context
            referenced_files = self.context.get_last_referenced_files()
            if referenced_files:
                # Try to apply edit to first referenced file
                file_path = referenced_files[0]
                self.formatter.print_info(f"\nDetected file edit for: {file_path}")
                success, error = self.editor.edit_file(file_path, response)
                if not success and error:
                    self.formatter.print_warning(f"Could not apply edit: {error}")
    
    def run(self) -> None:
        """Run the REPL."""
        self.formatter.console.print("[bold blue]AZUL CLI[/bold blue] - Type @help for commands, or just ask a question!")
        self.formatter.console.print(f"Model: {self.ollama.get_model()}\n")
        
        while self.running:
            try:
                # Check for file notifications
                self._check_file_notifications()
                
                # Get user input
                user_input = self.session_prompt.prompt("azul> ")
                
                if not user_input.strip():
                    continue
                
                # Check if it's a command
                if self.command_parser.is_command(user_input):
                    parsed = self.command_parser.parse(user_input)
                    if parsed:
                        if not self._handle_command(parsed):
                            break
                else:
                    # Treat as natural language prompt
                    self._handle_prompt(user_input)
            
            except KeyboardInterrupt:
                self.formatter.console.print("\n[bold yellow]Interrupted. Type @exit to quit.[/bold yellow]")
                continue
            except EOFError:
                break
            except Exception as e:
                self.formatter.print_error(f"Unexpected error: {e}")
                continue
        
        # Cleanup
        self.file_monitor.stop()
        self.formatter.console.print("\n[bold green]Goodbye![/bold green]")


def start_repl(project_root: Optional[Path] = None) -> None:
    """Start the interactive REPL."""
    repl = REPL(project_root)
    repl.run()

