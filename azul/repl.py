"""Interactive REPL for AZUL CLI."""

from typing import Optional, Tuple
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
from azul.config.manager import get_config_manager


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
        # Set REPL instance in command handler for @cd
        self.command_handler.set_repl(self)
        self.ollama = get_ollama_client()
        self.session = get_session_manager(self.project_root)
        self.context = get_context_manager()
        self.formatter = get_formatter()
        self.editor = get_editor()
        self.config = get_config_manager()
        
        # Setup prompt session with autocomplete
        commands = ['@model', '@edit', '@create', '@delete', '@read', '@ls', '@path', '@cd', '@clear', '@reset', '@index', '@rag', '@stats', '@context', '@help', '@exit', '@quit']
        command_completer = WordCompleter(
            commands,
            ignore_case=True,
            sentence=True  # Match anywhere in the text
        )
        
        history_file = Path.home() / ".azul" / "history"
        history_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.session_prompt = PromptSession(
            completer=command_completer,
            history=FileHistory(str(history_file)),
            multiline=False,  # Single line input - Enter submits
            complete_while_typing=True  # Show completions while typing @ and allow Tab to navigate
        )
        
        # Initialize RAG manager first (before file monitor)
        from azul.rag import get_rag_manager
        self.rag_manager = get_rag_manager(self.project_root)
        
        # Setup file monitoring (after RAG manager is initialized)
        self.file_monitor = get_file_monitor(self.project_root)
        self.file_monitor.start(self._on_file_change)
        
        self.running = True
        self.last_referenced_file: Optional[str] = None
    
    def _on_file_change(self, file_path: str) -> None:
        """Handle file change notification (non-intrusive)."""
        # Trigger incremental re-indexing if RAG is enabled
        # Check if rag_manager attribute exists (may not be initialized yet)
        if hasattr(self, 'rag_manager') and self.rag_manager and self.rag_manager.rag_enabled:
            config = self.config.load_config()
            if config.get("rag", {}).get("auto_reindex_on_change", True):
                # Use a timer to batch changes (quiet period)
                import threading
                quiet_period = config.get("rag", {}).get("reindex_quiet_period", 5)
                
                # Cancel previous timer if exists
                if hasattr(self, '_reindex_timer'):
                    self._reindex_timer.cancel()
                
                # Schedule re-indexing after quiet period
                def reindex_file():
                    try:
                        # Get relative path
                        file_path_obj = Path(file_path)
                        if file_path_obj.is_absolute():
                            rel_path = file_path_obj.relative_to(self.project_root)
                        else:
                            rel_path = file_path_obj
                        
                        self.rag_manager.update_index_on_file_change(str(rel_path))
                        self.formatter.print_info("[INFO] Index updated to reflect recent changes")
                    except Exception as e:
                        # Silently fail - don't interrupt user
                        pass
                
                self._reindex_timer = threading.Timer(quiet_period, reindex_file)
                self._reindex_timer.daemon = True
                self._reindex_timer.start()
    
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
        import time
        import sys
        import tiktoken
        
        # Retrieve and augment with RAG if enabled
        query_metrics = {}
        if self.rag_manager and self.rag_manager.rag_enabled:
            augmented_prompt, query_metrics = self.rag_manager.retrieve_and_augment(
                user_input,
                self.session.get_recent_history()
            )
        else:
            augmented_prompt = user_input
        
        # Build context
        context_str = self.context.build_context(augmented_prompt)
        
        # Add context to prompt if available
        if context_str:
            full_prompt = f"{context_str}\n\nUser: {augmented_prompt}\n\nAssistant:"
        else:
            full_prompt = augmented_prompt
        
        # Add to session
        self.session.add_message("user", user_input)
        
        # Stream response
        # Show status briefly, then stream tokens
        status = self.formatter.show_status("AZUL is thinking...")
        status.__enter__()
        
        ttft_start = time.time()
        output_tokens = 0
        generation_start = None
        
        try:
            stream = self.ollama.stream_chat(
                full_prompt,
                self.session.get_recent_history()
            )
            # Get first token to stop status
            first_token = next(stream, None)
            if first_token:
                ttft_ms = (time.time() - ttft_start) * 1000
                if self.rag_manager:
                    self.rag_manager.record_ttft(ttft_ms)
                
                generation_start = time.time()
                status.__exit__(None, None, None)  # Stop status
                # Print first token using standard print for streaming
                sys.stdout.write(first_token)
                sys.stdout.flush()
                
                # Count tokens
                enc = tiktoken.get_encoding("cl100k_base")
                output_tokens = len(enc.encode(first_token))
                
                # Stream remaining tokens
                remaining = self.formatter.stream_response(stream)
                output_tokens += len(enc.encode(remaining))
                response = first_token + remaining
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
        
        # Record generation metrics
        if generation_start:
            generation_time = time.time() - generation_start
            if self.rag_manager:
                self.rag_manager.record_generation(output_tokens, generation_time)
        
        # Add response to session
        self.session.add_message("assistant", response)
        
        # Display stats if enabled
        if self.rag_manager:
            stats_display = self.rag_manager.get_stats_display()
            if stats_display:
                self.formatter.console.print(f"\n{stats_display}\n")
        
        # Check for file operations in response
        # 1. Check for file creation
        file_info = self.editor.extract_file_content(response)
        if file_info:
            file_path, file_content = file_info
            self.formatter.print_info(f"\nDetected file creation: {file_path}")
            success, error = self.editor.create_file(file_path, file_content)
            if not success and error:
                self.formatter.print_warning(f"Could not create file: {error}")
            return  # Don't check for other operations if we created a file
        
        # 2. Check for file deletion
        delete_file = self.editor.extract_delete_file(response)
        if delete_file:
            self.formatter.print_info(f"\nDetected file deletion: {delete_file}")
            success, error = self.editor.delete_file(delete_file)
            if not success and error:
                self.formatter.print_warning(f"Could not delete file: {error}")
            return  # Don't check for edits if we deleted a file
        
        # 3. Check if response contains diff (for natural language edits)
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
    
    def change_directory(self, target_dir: str) -> Tuple[bool, Optional[str]]:
        """
        Change directory and update all components.
        
        Args:
            target_dir: Directory to change to
            
        Returns:
            Tuple of (success, error_message)
        """
        import os
        from pathlib import Path
        
        try:
            # Resolve the target path
            if Path(target_dir).is_absolute():
                new_dir = Path(target_dir)
            else:
                new_dir = self.project_root / target_dir
            
            new_dir = new_dir.resolve()
            
            if not new_dir.exists():
                return False, f"Directory does not exist: {target_dir}"
            
            if not new_dir.is_dir():
                return False, f"Path is not a directory: {target_dir}"
            
            # Change actual working directory
            os.chdir(new_dir)
            
            # Update project root
            self.project_root = new_dir
            
            # Update all components
            from azul.sandbox import get_sandbox
            from azul.file_monitor import get_file_monitor
            
            # Update sandbox
            get_sandbox(new_dir)
            
            # Update session manager
            self.session = get_session_manager(new_dir)
            
            # Update file monitor
            self.file_monitor.stop()
            self.file_monitor = get_file_monitor(new_dir)
            self.file_monitor.start(self._on_file_change)
            
            # Update file handler's sandbox reference (it uses global sandbox which is updated)
            # Force file handler to get the updated sandbox
            self.command_handler.file_handler.sandbox = get_sandbox(new_dir)
            
            # Update context manager (it may cache file references)
            # The context manager will automatically use the updated file handler
            
            # Reinitialize RAG manager for new directory
            from azul.rag import get_rag_manager, reset_rag_manager
            reset_rag_manager()
            self.rag_manager = get_rag_manager(new_dir)
            
            # Check if index exists and prompt if needed
            if self.rag_manager and not self.rag_manager.index_exists():
                config = self.config.load_config()
                if config.get("rag", {}).get("auto_index_on_start", True):
                    project_name = new_dir.name
                    self.formatter.console.print(f"\n[bold yellow]Project '{project_name}' is not indexed.[/bold yellow]")
                    self.formatter.console.print("Index it now to enable full codebase awareness? (Y/n): ", end="")
                    try:
                        response = input().strip().lower()
                        if response in ('', 'y', 'yes'):
                            self.rag_manager.index(clean=False)
                            self.formatter.print_success("Indexing complete! RAG is now enabled.")
                    except (EOFError, KeyboardInterrupt):
                        pass
            
            self.formatter.print_success(f"Changed directory to: {new_dir}")
            # Show updated status
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
        """Print current status (model and directory)."""
        self.formatter.console.print("[bold blue]AZUL CLI[/bold blue] - Type @help for commands, or just ask a question! made by SG")
        self.formatter.console.print(f"Model: {self.ollama.get_model()}")
        self.formatter.console.print(f"Directory: {self.project_root}\n")
    
    def run(self) -> None:
        """Run the REPL."""
        # Print banner
        self._print_banner()
        
        # Print welcome message
        self._print_status()
        
        # Check for RAG index and prompt if needed
        if self.rag_manager and not self.rag_manager.index_exists():
            config = self.config.load_config()
            if config.get("rag", {}).get("auto_index_on_start", True):
                project_name = self.project_root.name
                self.formatter.console.print(f"\n[bold yellow]Project '{project_name}' is not indexed.[/bold yellow]")
                self.formatter.console.print("Index it now to enable full codebase awareness? (Y/n): ", end="")
                try:
                    response = input().strip().lower()
                    if response in ('', 'y', 'yes'):
                        self.rag_manager.index(clean=False)
                        self.formatter.print_success("Indexing complete! RAG is now enabled.")
                except (EOFError, KeyboardInterrupt):
                    pass
        
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

