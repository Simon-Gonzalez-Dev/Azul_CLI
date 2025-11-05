"""Command handlers for @ commands."""

import logging
from pathlib import Path
from typing import Optional, Tuple

from azul.command_parser import ParsedCommand

logger = logging.getLogger(__name__)
from azul.ollama_client import get_ollama_client
from azul.session_manager import get_session_manager
from azul.file_handler import get_file_handler
from azul.context import get_context_manager
from azul.editor import get_editor
from azul.formatter import get_formatter
from azul.config.manager import get_config_manager


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
        
        # Pre-flight check: Verify embedding model BEFORE showing warnings
        # This prevents showing "index exists" warning when we can't even index
        try:
            import ollama
            models_response = ollama.list()
            
            # Extract model names - handle different response formats
            local_models = []
            
            # Debug: log the raw response structure
            # logger.debug(f"Ollama response type: {type(models_response)}, content: {models_response}")
            
            # Try different ways to extract models - be very aggressive
            models_list = []
            
            # Handle ListResponse object (has .models attribute) - CHECK THIS FIRST
            if hasattr(models_response, 'models'):
                try:
                    # Access .models attribute directly
                    models_attr = getattr(models_response, 'models')
                    
                    # Handle different types .models might be
                    if isinstance(models_attr, list):
                        models_list = models_attr
                    elif isinstance(models_attr, dict):
                        # If it's a dict, try to extract the list
                        if 'models' in models_attr:
                            models_list = models_attr['models']
                        elif 'data' in models_attr:
                            models_list = models_attr['data']
                        else:
                            # Try to find any list value in the dict
                            for v in models_attr.values():
                                if isinstance(v, list):
                                    models_list = v
                                    break
                    elif hasattr(models_attr, '__iter__') and not isinstance(models_attr, (str, bytes)):
                        # If it's iterable (but not a list), convert to list
                        models_list = list(models_attr)
                    else:
                        # Try to get it as a property/descriptor
                        models_list = models_attr
                except Exception as e:
                    # If accessing .models fails, try alternative methods
                    logger.debug(f"Error accessing .models: {e}")
                    models_list = []
            # Handle dict-like objects
            elif isinstance(models_response, dict):
                # Try "models" key first (most common)
                if "models" in models_response:
                    models_list = models_response["models"]
                # Try other possible keys
                elif "data" in models_response:
                    models_list = models_response["data"]
                # Try any key that contains a list
                else:
                    for key, value in models_response.items():
                        if isinstance(value, list) and len(value) > 0:
                            # Check if it looks like a list of models (has dicts with "name" or string)
                            if isinstance(value[0], dict) and ("name" in value[0] or "model" in value[0]):
                                models_list = value
                                break
                            elif isinstance(value[0], str):
                                models_list = value
                                break
            # Handle list directly
            elif isinstance(models_response, list):
                models_list = models_response
            # Try to access as attribute if it's an object
            elif hasattr(models_response, '__dict__'):
                # Try common attribute names
                for attr in ['models', 'data', 'items']:
                    if hasattr(models_response, attr):
                        value = getattr(models_response, attr)
                        if isinstance(value, list):
                            models_list = value
                            break
            
            # Extract model names from the list
            # Debug: log models_list for troubleshooting
            # logger.debug(f"models_list type: {type(models_list)}, length: {len(models_list) if hasattr(models_list, '__len__') else 'N/A'}")
            
            if models_list:
                for m in models_list:
                    if isinstance(m, dict):
                        # Try multiple possible keys for model name
                        name = (
                            m.get("name") or 
                            m.get("model") or 
                            m.get("model_name") or
                            m.get("id")  # Sometimes it's "id"
                        )
                        if name:
                            name_str = str(name).strip()
                            if name_str:
                                # Store full name
                                local_models.append(name_str)
                                # Also add base name without tag for matching
                                if ":" in name_str:
                                    base_name = name_str.split(":")[0]
                                    if base_name and base_name not in local_models:
                                        local_models.append(base_name)
                    elif isinstance(m, str):
                        m_str = m.strip()
                        if m_str:
                            local_models.append(m_str)
                            if ":" in m_str:
                                base_name = m_str.split(":")[0]
                                if base_name and base_name not in local_models:
                                    local_models.append(base_name)
            elif hasattr(models_response, 'models'):
                # models_list is empty, but .models exists - try direct iteration
                try:
                    # Maybe .models is iterable directly
                    for m in models_response.models:
                        if isinstance(m, dict):
                            name = m.get("name") or m.get("model") or m.get("model_name") or m.get("id")
                            if name:
                                name_str = str(name).strip()
                                if name_str:
                                    local_models.append(name_str)
                                    if ":" in name_str:
                                        base_name = name_str.split(":")[0]
                                        if base_name and base_name not in local_models:
                                            local_models.append(base_name)
                        elif isinstance(m, str):
                            m_str = m.strip()
                            if m_str:
                                local_models.append(m_str)
                except (TypeError, AttributeError):
                    pass
            
            # Get embedding model from config
            config_manager = get_config_manager()
            rag_config = config_manager.get("rag", {})
            embedding_model = rag_config.get("embedding_model", "nomic-embed-text")
            
            # Check both exact match and base name match (without tag)
            embedding_base = embedding_model.split(":")[0] if ":" in embedding_model else embedding_model
            
            # Also check if any model starts with the base name (more flexible matching)
            model_found = False
            for model_name in local_models:
                model_str = str(model_name)
                # Check exact match
                if model_str == embedding_model or model_str == embedding_base:
                    model_found = True
                    break
                # Check if model starts with base name (handles tags)
                if model_str.startswith(embedding_base + ":") or model_str.startswith(embedding_model + ":"):
                    model_found = True
                    break
                # Check if base name matches (reverse check)
                if ":" in model_str and model_str.split(":")[0] == embedding_base:
                    model_found = True
                    break
            
            if not model_found:
                # Show available models in error for debugging
                available_str = ", ".join(local_models[:5]) if local_models else "none"
                if len(local_models) > 5:
                    available_str += f" ... ({len(local_models)} total)"
                
                # If we found no models, show raw response structure for debugging
                debug_info = ""
                if not local_models:
                    debug_info = f"\nDebug: Ollama response type: {type(models_response).__name__}"
                    if isinstance(models_response, dict):
                        debug_info += f", keys: {list(models_response.keys())[:5]}"
                    elif isinstance(models_response, list):
                        debug_info += f", length: {len(models_response)}"
                    elif hasattr(models_response, '__dict__'):
                        debug_info += f", attributes: {list(models_response.__dict__.keys())[:5]}"
                    elif hasattr(models_response, 'models'):
                        try:
                            models_attr = getattr(models_response, 'models')
                            debug_info += f", models attr type: {type(models_attr).__name__}"
                            if isinstance(models_attr, (list, tuple)):
                                debug_info += f", models length: {len(models_attr)}"
                                if len(models_attr) > 0:
                                    first_item = models_attr[0]
                                    debug_info += f", first item type: {type(first_item).__name__}"
                                    if isinstance(first_item, dict):
                                        debug_info += f", first item keys: {list(first_item.keys())[:5]}"
                            elif isinstance(models_attr, dict):
                                debug_info += f", models keys: {list(models_attr.keys())[:5]}"
                            else:
                                debug_info += f", models repr: {repr(models_attr)[:100]}"
                            # Also show models_list state
                            debug_info += f", models_list length: {len(models_list)}"
                        except Exception as e:
                            debug_info += f", error accessing models: {e}"
                
                error_msg = f"Embedding model '{embedding_model}' not found.\n"
                error_msg += f"Available models: {available_str}{debug_info}\n"
                error_msg += f"Please run: ollama pull {embedding_model}\n"
                error_msg += "Indexing cannot proceed without the embedding model."
                return False, error_msg
        except Exception as e:
            return False, f"Could not verify embedding model availability: {e}"
        
        # Check if index exists and ask for confirmation (only if we can proceed)
        if rag_manager.index_exists() and not clean:
            self.formatter.print_warning("Index already exists. Use @index --clean to rebuild from scratch.")
            # Still proceed with incremental update
            clean = False
        
        # Perform indexing
        try:
            metrics = rag_manager.index(clean=clean)
            
            # Check if indexing failed (shouldn't happen after pre-flight check, but safety)
            if metrics.get("error"):
                return False, metrics.get("error")
            
            # Check if no chunks were created (possible failure)
            chunks_created = metrics.get('chunks_created', 0)
            if chunks_created == 0:
                warning = metrics.get('warning', '')
                if warning:
                    self.formatter.print_warning(warning)
                self.formatter.console.print("\n[bold yellow]Indexing completed with warnings[/bold yellow]")
            else:
                self.formatter.console.print("\n[bold green]Indexing complete![/bold green]")
            
            # Display metrics
            self.formatter.console.print(f"  Files indexed: {metrics.get('files_indexed', 0)}")
            self.formatter.console.print(f"  Chunks created: {metrics.get('chunks_created', 0)}")
            self.formatter.console.print(f"  Index size: {metrics.get('index_size_mb', 0):.2f} MB")
            self.formatter.console.print(f"  Time: {metrics.get('indexing_time', 0):.2f}s")
            
            # Show skipped/error files summary if any
            skipped = metrics.get('skipped_files', [])
            errors = metrics.get('error_files', [])
            if skipped or errors:
                total = len(skipped) + len(errors)
                if total <= 10:  # Show details if few issues
                    if skipped:
                        self.formatter.console.print(f"\n  [yellow]Skipped files ({len(skipped)}):[/yellow]")
                        for file_path, reason in skipped[:5]:
                            self.formatter.console.print(f"    • {file_path}: {reason}")
                        if len(skipped) > 5:
                            self.formatter.console.print(f"    ... and {len(skipped) - 5} more")
                    if errors:
                        self.formatter.console.print(f"\n  [red]Errors ({len(errors)}):[/red]")
                        for file_path, error in errors[:5]:
                            self.formatter.console.print(f"    • {file_path}: {error}")
                        if len(errors) > 5:
                            self.formatter.console.print(f"    ... and {len(errors) - 5} more")
                else:  # Too many, just show counts
                    self.formatter.console.print(f"\n  [dim]Note: {total} files had issues (see logs for details)[/dim]")
            
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

