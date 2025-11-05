"""Command handlers for @ commands."""

from pathlib import Path
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
        elif cmd == 'index':
            return self.handle_index(parsed.args)
        elif cmd == 'rag':
            return self.handle_rag(parsed.args)
        elif cmd == 'stats':
            return self.handle_stats(parsed.args)
        elif cmd == 'context':
            return self.handle_context()
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
            stream = self.ollama.stream_chat(prompt, self.session.get_recent_history())
            # Get first token to stop status
            first_token = next(stream, None)
            if first_token:
                status.__exit__(None, None, None)  # Stop status
                # Print first token using standard print for streaming
                import sys
                sys.stdout.write(first_token)
                sys.stdout.flush()
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
            stream = self.ollama.stream_chat(prompt, self.session.get_recent_history())
            # Get first token to stop status
            first_token = next(stream, None)
            if first_token:
                status.__exit__(None, None, None)  # Stop status
                # Print first token using standard print for streaming
                import sys
                sys.stdout.write(first_token)
                sys.stdout.flush()
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

  @model [name]          - Change Ollama model (or show current model)
  @edit <file> <inst>    - Edit a file with instruction
  @create <file> <inst>  - Create a new file with instruction
  @delete <file>         - Delete a file
  @read <file>           - Read and display a file
  @ls                    - List files in current directory
  @path                  - Show current directory path
  @cd <dir>              - Change directory
  @clear                 - Clear terminal screen
  @reset                 - Clear conversation history
  @index [--clean]        - Index project for RAG (--clean rebuilds from scratch)
  @rag [on/off]          - Toggle RAG pipeline on/off
  @stats [on/off]        - Toggle performance stats display on/off
  @context               - Show RAG context from last prompt (debugging)
  @help                  - Show this help message
  @exit / @quit          - Exit AZUL

Everything else is treated as a natural language prompt to the AI.
"""
        self.formatter.console.print(help_text)
        return True, None
    
    def handle_index(self, args: list) -> Tuple[bool, Optional[str]]:
        """Handle @index command."""
        from azul.rag import get_rag_manager
        from pathlib import Path
        
        # Check for --clean flag
        clean = False
        if args:
            # Filter out None values and join
            clean_args = [str(arg) for arg in args if arg is not None]
            if clean_args:
                clean = '--clean' in ' '.join(clean_args)
        
        # Get RAG manager (create if doesn't exist)
        project_root = Path.cwd()
        rag_manager = get_rag_manager(project_root)
        if rag_manager is None:
            # Create RAG manager
            from azul.rag import RAGManager
            rag_manager = RAGManager(project_root)
            from azul.rag import reset_rag_manager
            reset_rag_manager()
            # Set it globally
            get_rag_manager(project_root)
        
        # Check if index exists and ask for confirmation
        if rag_manager.index_exists() and not clean:
            self.formatter.print_warning("Index already exists. Use @index --clean to rebuild from scratch.")
            # Still proceed with incremental update
            clean = False
        
        # Perform indexing
        try:
            metrics = rag_manager.index(clean=clean)
            
            # Display metrics
            self.formatter.console.print("\n[bold green]Indexing complete![/bold green]")
            self.formatter.console.print(f"  Files indexed: {metrics.get('files_indexed', 0)}")
            self.formatter.console.print(f"  Chunks created: {metrics.get('chunks_created', 0)}")
            self.formatter.console.print(f"  Index size: {metrics.get('index_size_mb', 0):.2f} MB")
            self.formatter.console.print(f"  Time: {metrics.get('indexing_time', 0):.2f}s")
            self.formatter.console.print()
            
            return True, None
        except Exception as e:
            return False, f"Error indexing: {e}"
    
    def handle_rag(self, args: list) -> Tuple[bool, Optional[str]]:
        """Handle @rag command."""
        from azul.rag import get_rag_manager, RAGManager
        from pathlib import Path
        
        project_root = Path.cwd()
        rag_manager = get_rag_manager(project_root)
        if rag_manager is None:
            # Create RAG manager
            rag_manager = RAGManager(project_root)
            from azul.rag import reset_rag_manager
            reset_rag_manager()
            get_rag_manager(project_root)
        
        # Parse arguments
        if args and len(args) > 0:
            arg = args[0].lower()
            if arg == 'on':
                rag_manager.set_rag(True)
                self.formatter.print_info("[INFO] RAG pipeline enabled")
            elif arg == 'off':
                rag_manager.set_rag(False)
                self.formatter.print_info("[INFO] RAG pipeline disabled")
            else:
                # Toggle
                new_state = rag_manager.toggle_rag()
                status = "enabled" if new_state else "disabled"
                self.formatter.print_info(f"[INFO] RAG pipeline {status}")
        else:
            # Toggle
            new_state = rag_manager.toggle_rag()
            status = "enabled" if new_state else "disabled"
            self.formatter.print_info(f"[INFO] RAG pipeline {status}")
        
        return True, None
    
    def handle_stats(self, args: list) -> Tuple[bool, Optional[str]]:
        """Handle @stats command."""
        from azul.rag import get_rag_manager, RAGManager
        from pathlib import Path
        
        project_root = Path.cwd()
        rag_manager = get_rag_manager(project_root)
        if rag_manager is None:
            # Create RAG manager
            rag_manager = RAGManager(project_root)
            from azul.rag import reset_rag_manager
            reset_rag_manager()
            get_rag_manager(project_root)
        
        # Parse arguments
        if args and len(args) > 0:
            arg = args[0].lower()
            if arg == 'on':
                rag_manager.set_stats(True)
                self.formatter.print_info("[INFO] Performance stats will now be displayed")
            elif arg == 'off':
                rag_manager.set_stats(False)
                self.formatter.print_info("[INFO] Performance stats will now be hidden")
            else:
                # Toggle
                new_state = rag_manager.toggle_stats()
                status = "displayed" if new_state else "hidden"
                self.formatter.print_info(f"[INFO] Performance stats will now be {status}")
        else:
            # Toggle
            new_state = rag_manager.toggle_stats()
            status = "displayed" if new_state else "hidden"
            self.formatter.print_info(f"[INFO] Performance stats will now be {status}")
        
        return True, None
    
    def handle_context(self) -> Tuple[bool, Optional[str]]:
        """Handle @context command - show RAG context from last prompt."""
        from azul.rag import get_rag_manager, RAGManager
        from pathlib import Path
        
        project_root = Path.cwd()
        rag_manager = get_rag_manager(project_root)
        if rag_manager is None:
            # Create RAG manager
            rag_manager = RAGManager(project_root)
            from azul.rag import reset_rag_manager
            reset_rag_manager()
            get_rag_manager(project_root)
        
        if not rag_manager.rag_enabled:
            self.formatter.print_warning("RAG is currently disabled. Enable it with @rag on")
            return True, None
        
        if not rag_manager.index_exists():
            self.formatter.print_warning("No index found. Create one with @index")
            return True, None
        
        # Get last user message from session
        history = self.session.get_recent_history()
        if not history:
            self.formatter.print_info("No conversation history yet. Ask a question first.")
            return True, None
        
        # Find last user message
        last_user_msg = None
        for msg in reversed(history):
            if msg.get("role") == "user":
                last_user_msg = msg.get("content", "")
                break
        
        if not last_user_msg:
            self.formatter.print_info("No user message found in history.")
            return True, None
        
        # Perform retrieval (same as in RAG pipeline)
        chunks = rag_manager.retriever.retrieve(last_user_msg)
        
        # Build augmented prompt
        augmented_prompt = rag_manager.augmenter.augment(
            last_user_msg,
            chunks,
            history
        )
        
        # Display context
        self.formatter.console.print("\n[bold cyan]=== RAG Context Debug ===[/bold cyan]\n")
        self.formatter.console.print(f"[bold]Last User Prompt:[/bold] {last_user_msg}\n")
        
        if chunks:
            self.formatter.console.print(f"[bold]Retrieved Chunks ({len(chunks)}):[/bold]")
            for i, chunk in enumerate(chunks, 1):
                file_path = chunk.get("file_path", "unknown")
                start_line = chunk.get("start_line", 0)
                end_line = chunk.get("end_line", 0)
                content = chunk.get("content", "")[:200]  # First 200 chars
                self.formatter.console.print(f"\n  [{i}] {file_path}:{start_line}-{end_line}")
                self.formatter.print_code_block(content, "python")
        else:
            self.formatter.console.print("[yellow]No chunks retrieved[/yellow]\n")
        
        self.formatter.console.print(f"\n[bold]Full Augmented Prompt:[/bold]")
        self.formatter.print_code_block(augmented_prompt, "text")
        self.formatter.console.print()
        
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

