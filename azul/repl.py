"""Interactive REPL optimized for maximum performance."""

from typing import Optional, Tuple
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from pathlib import Path
import sys

from azul.command_parser import get_command_parser, ParsedCommand
from azul.commands.handlers import get_command_handler
from azul.llama_client import get_llama_client
from azul.session_manager import get_session_manager
from azul.formatter import get_formatter
from azul.editor import get_editor
from azul.file_monitor import get_file_monitor
from azul.config.manager import get_config_manager
from azul.tools import ToolExecutor


class REPL:
    """High-performance Interactive Read-Eval-Print Loop."""
    
    def __init__(self, project_root: Optional[Path] = None):
        """Initialize REPL with optimized settings."""
        self.project_root = project_root or Path.cwd()
        
        # Initialize sandbox first
        from azul.sandbox import get_sandbox
        get_sandbox(self.project_root)
        
        # Initialize components
        self.command_parser = get_command_parser()
        self.command_handler = get_command_handler()
        self.command_handler.set_repl(self)
        self.llama = get_llama_client()
        self.session = get_session_manager(self.project_root)
        self.formatter = get_formatter()
        self.editor = get_editor()
        self.config = get_config_manager()
        self.tool_executor = ToolExecutor(self.project_root)
        
        # Commands for autocomplete
        commands = ['@model', '@edit', '@create', '@delete', '@read', '@ls', '@path', '@cd', '@clear', '@reset', '@help', '@exit', '@quit']
        command_completer = WordCompleter(commands, ignore_case=True, sentence=True)
        
        # History file
        history_file = Path.home() / ".azul" / "history"
        history_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.session_prompt = PromptSession(
            completer=command_completer,
            history=FileHistory(str(history_file)),
            multiline=False,
            complete_while_typing=True
        )
        
        # Setup file monitoring
        self.file_monitor = get_file_monitor(self.project_root)
        self.file_monitor.start(self._on_file_change)
        
        self.running = True
        self.last_referenced_file: Optional[str] = None
    
    def _on_file_change(self, file_path: str) -> None:
        """Handle file change notification."""
        pass
    
    def _check_file_notifications(self) -> None:
        """Check and display file change notifications."""
        notifications = self.file_monitor.get_notifications()
        if notifications:
            for file_path in notifications[:3]:
                self.formatter.print_info(
                    f"File modified: {file_path}. Say 'review it' or '@read {file_path}' to see changes."
                )
    
    def _handle_command(self, parsed: ParsedCommand) -> bool:
        """Handle a command."""
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
        """
        Handle a natural language prompt by delegating to the new Agent.
        """
        # Use new clean Agent implementation
        from azul.agent import Agent
        agent = Agent(self.project_root, user_input)
        agent.run()
    
    def change_directory(self, target_dir: str) -> Tuple[bool, Optional[str]]:
        """Change directory and update all components."""
        import os
        from pathlib import Path
        
        try:
            if Path(target_dir).is_absolute():
                new_dir = Path(target_dir)
            else:
                new_dir = self.project_root / target_dir
            
            new_dir = new_dir.resolve()
            
            if not new_dir.exists() or not new_dir.is_dir():
                return False, f"Directory does not exist: {target_dir}"
            
            os.chdir(new_dir)
            self.project_root = new_dir
            
            # Update components
            from azul.sandbox import get_sandbox
            from azul.file_monitor import get_file_monitor
            
            get_sandbox(new_dir)
            self.session = get_session_manager(new_dir)
            
            self.file_monitor.stop()
            self.file_monitor = get_file_monitor(new_dir)
            self.file_monitor.start(self._on_file_change)
            
            self.command_handler.file_handler.sandbox = get_sandbox(new_dir)
            
            self.formatter.print_success(f"Changed directory to: {new_dir}")
            self.formatter.console.print(f"Directory: {self.project_root}\n")
            return True, None
        except Exception as e:
            return False, f"Error changing directory: {e}"
    
    def _print_banner(self) -> None:
        """Print AZUL banner."""
        banner = """
    █████╗   ███████╗   ██╗   ██╗   ██╗       
   ██╔══██╗   ╚════██╗  ██║   ██║   ██║      
  ███████║    █████╔╝   ██║   ██║   ██║       
 ██╔══██║    ██╔═══╝    ██║   ██║   ██║       
██║  ██║     ███████╗   ╚██████╔╝   ███████╗  
╚═╝  ╚═╝     ╚══════╝    ╚═════╝    ╚══════╝ 
"""
        self.formatter.console.print(banner, style="bold blue")
        self.formatter.console.print()
    
    def _print_status(self) -> None:
        """Print current status."""
        self.formatter.console.print("[bold blue]AZUL CLI[/bold blue] - Type @help for commands, or just ask a question! made by SG")
        model_name = self.llama.get_model()
        if model_name == "Not loaded":
            self.formatter.console.print(f"[yellow]Model: {model_name}[/yellow] - Use @model to set model path")
        else:
            self.formatter.console.print(f"Model: [green]{model_name}[/green]")
        self.formatter.console.print(f"Directory: {self.project_root}\n")
    
    def run(self) -> None:
        """Run the REPL."""
        self._print_banner()
        self._print_status()
        
        while self.running:
            try:
                self._check_file_notifications()
                
                user_input = self.session_prompt.prompt("azul> ")
                
                if not user_input.strip():
                    continue
                
                if self.command_parser.is_command(user_input):
                    parsed = self.command_parser.parse(user_input)
                    if parsed:
                        if not self._handle_command(parsed):
                            break
                else:
                    self._handle_prompt(user_input)
            
            except KeyboardInterrupt:
                self.formatter.console.print("\n[bold yellow]Interrupted. Type @exit to quit.[/bold yellow]")
                continue
            except EOFError:
                break
            except Exception as e:
                self.formatter.print_error(f"Unexpected error: {e}")
                continue
        
        self.file_monitor.stop()
        # Save session history before exit
        self.session.save_history()
        self.formatter.console.print("\n[bold blue]Goodbye![/bold blue]")


def start_repl(project_root: Optional[Path] = None) -> None:
    """Start the interactive REPL."""
    repl = REPL(project_root)
    repl.run()
