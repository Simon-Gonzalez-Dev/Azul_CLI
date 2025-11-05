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
from azul.metrics import MetricsTracker
from azul.response_parser import parse_response
from azul.intent_filter import is_likely_false_positive
from azul.tool_parser import extract_tool_call, detect_tool_call, remove_tool_call_from_content
from azul.tools import ToolExecutor
from azul.tree_generator import generate_tree


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
        Handle a natural language prompt with agentic tool-using loop.
        Supports iterative tool execution and context gathering.
        """
        # Get conversation history
        conversation_history = self.session.get_recent_history(n=10)
        
        # Add initial tree() context if this is a new conversation or first interaction
        # Check if history is empty or very short
        user_input_with_context = user_input
        if len(conversation_history) <= 2:
            # Add tree output as a tool message to provide initial context
            tree_output = generate_tree(self.project_root, max_depth=3)
            formatted_tree = f"Tool Output:\n{tree_output}"
            self.session.add_message("tool", formatted_tree)
        
        # Add to session
        self.session.add_message("user", user_input)
        
        # Agentic loop: continue until no more tools are called
        max_iterations = 10  # Safety limit
        iteration = 0
        final_actions = []
        
        while iteration < max_iterations:
            iteration += 1
            
            # Get updated conversation history for this iteration
            conversation_history = self.session.get_recent_history(n=20)
            
            # Initialize metrics tracker
            tracker = MetricsTracker()
            # For iterations after the first, we don't need a new user message
            # The conversation history contains everything
            current_user_message = user_input_with_context if iteration == 1 else ""
            full_prompt = self.llama.build_prompt(
                current_user_message, 
                conversation_history
            )
            tracker.start(full_prompt)
            
            # Stream response with tool detection
            response_content = ""
            buffer = ""
            tool_detected = False
            tool_call = None
            spinner = None
            first_token_received = False
            
            try:
                # Start spinner
                spinner = self.formatter.console.status(
                    "[bold blue]AZUL is thinking...[/bold blue]", 
                    spinner="dots"
                )
                spinner.__enter__()
                
                # Get stream
                stream = self.llama.stream_chat(
                    current_user_message, 
                    conversation_history
                )
                
                # Stream tokens and detect tool calls
                for token in stream:
                    buffer += token
                    response_content += token
                    
                    # Check for tool call during streaming
                    if '<tool_code>' in buffer.lower():
                        # Check if we have a complete tool call
                        potential_tool = extract_tool_call(buffer)
                        if potential_tool:
                            tool_detected = True
                            tool_call = potential_tool
                            # Stop streaming - we found a tool
                            break
                    
                    # Display token to user (conversational text)
                    if not first_token_received:
                        tracker.record_first_token()
                        first_token_received = True
                        if spinner:
                            spinner.__exit__(None, None, None)
                            spinner = None
                    sys.stdout.write(token)
                    sys.stdout.flush()
                
                if spinner:
                    spinner.__exit__(None, None, None)
                    spinner = None
                
                # Final newline if we didn't hit a tool
                if not tool_detected:
                    sys.stdout.write('\n')
                    sys.stdout.flush()
                    
            except StopIteration:
                if spinner:
                    spinner.__exit__(None, None, None)
                response_content = ""
            except Exception as e:
                if spinner:
                    spinner.__exit__(None, None, None)
                import traceback
                self.formatter.print_error(f"Error: {e}")
                self.formatter.print_error(traceback.format_exc())
                response_content = ""
            
            # Record metrics
            tracker.record_completion(response_content)
            stats = tracker.get_stats()
            
            # If tool was detected, extract it and execute
            if tool_detected and tool_call:
                # Remove tool call from conversational text
                conversational_text = remove_tool_call_from_content(response_content, tool_call)
                
                # Add assistant's conversational response (if any)
                if conversational_text.strip():
                    self.session.add_message("assistant", conversational_text)
                
                # Show status message
                tool_name = tool_call.tool_name
                if tool_name == "read":
                    file_path = tool_call.arguments.get('file_path', 'file')
                    self.formatter.print_info(f"[AZUL is reading {file_path}...]")
                elif tool_name == "tree":
                    self.formatter.print_info("[AZUL is exploring project structure...]")
                elif tool_name in ["write", "diff", "delete"]:
                    # These are final actions - we'll handle them after the loop
                    file_path = tool_call.arguments.get('file_path', 'file')
                    final_actions.append({
                        'tool': tool_call,
                        'conversational_text': conversational_text
                    })
                    # Break loop - we found a final action
                    break
                
                # Execute tool
                tool_output = self.tool_executor.execute_tool(
                    tool_call.tool_name,
                    tool_call.arguments
                )
                
                # Add tool output to conversation history
                formatted_output = f"Tool Output:\n{tool_output}"
                self.session.add_message("tool", formatted_output)
                
                # Continue loop - AI will respond with next step
                continue
            
            # No tool detected - this is a final response
            # Add assistant response to history
            if response_content.strip():
                self.session.add_message("assistant", response_content)
            
            # Display stats
            if stats:
                stats_text = (
                    f"[bold blue]Stats:[/bold blue] "
                    f"TTFT: [bold]{stats['ttft_ms']:.0f}ms[/bold] | "
                    f"Gen: [bold]{stats['generation_time_s']:.2f}s[/bold] | "
                    f"Prompt: [bold]{int(stats['prompt_tokens'])}[/bold] | "
                    f"Output: [bold]{int(stats['output_tokens'])}[/bold] | "
                    f"Speed: [bold]{stats['tokens_per_second']:.1f}[/bold] tok/s"
                )
                self.formatter.console.print(f"\n{stats_text}\n")
            
            # Check for traditional file operations (diff, file, delete blocks)
            conversational_text, potential_actions = parse_response(response_content)
            is_false_positive = is_likely_false_positive(conversational_text, potential_actions, user_input)
            
            # Process traditional actions if they pass the filter
            if potential_actions and not is_false_positive:
                for action in potential_actions:
                    action_type = action.get("type")
                    file_path = action.get("path")
                    content = action.get("content")
                    
                    if action_type == "edit":
                        if file_path and content:
                            self.formatter.print_info(f"\nDetected file edit: {file_path}")
                            success, error = self.editor.edit_file(file_path, content)
                            if not success and error:
                                self.formatter.print_warning(f"Could not edit file: {error}")
                    
                    elif action_type == "create":
                        if file_path and content:
                            success, error = self.editor.create_file(file_path, content)
                            if not success and error:
                                self.formatter.print_warning(f"Could not create file: {error}")
                    
                    elif action_type == "delete":
                        if file_path:
                            self.formatter.print_info(f"\nDetected file deletion: {file_path}")
                            success, error = self.editor.delete_file(file_path)
                            if not success and error:
                                self.formatter.print_warning(f"Could not delete file: {error}")
            
            # Break loop - no more tools to execute
            break
        
        # Handle final actions from tool calls (write, diff, delete)
        for final_action in final_actions:
            tool_call = final_action['tool']
            tool_name = tool_call.tool_name
            file_path = tool_call.arguments.get('file_path')
            # For diff, content is the diff string; for write, content is file content
            content = tool_call.arguments.get('content') or tool_call.arguments.get('diff_content', '')
            
            if tool_name == "write":
                if file_path and content:
                    success, error = self.editor.create_file(file_path, content)
                    if not success and error:
                        self.formatter.print_warning(f"Could not create file: {error}")
            
            elif tool_name == "diff":
                if file_path and content:
                    self.formatter.print_info(f"\nDetected file edit: {file_path}")
                    # Content is the diff string - wrap it in markdown diff block for edit_file
                    diff_block = f"```diff\n{content}\n```"
                    success, error = self.editor.edit_file(file_path, diff_block)
                    if not success and error:
                        self.formatter.print_warning(f"Could not edit file: {error}")
            
            elif tool_name == "delete":
                if file_path:
                    self.formatter.print_info(f"\nDetected file deletion: {file_path}")
                    success, error = self.editor.delete_file(file_path)
                    if not success and error:
                        self.formatter.print_warning(f"Could not delete file: {error}")
        
        # Save history
        self.session.save_history()
    
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
