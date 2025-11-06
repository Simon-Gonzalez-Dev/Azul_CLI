"""Agentic loop for autonomous AI agent execution."""

import sys
import threading
from pathlib import Path
from typing import Optional, List

from azul.llama_client import get_llama_client
from azul.session_manager import get_session_manager
from azul.formatter import get_formatter
from azul.editor import get_editor
from azul.tools import ToolExecutor
from azul.tree_generator import generate_tree
from azul.tool_parser import extract_tool_call, remove_tool_call_from_content
from azul.permissions import get_permission_manager
from azul.metrics import MetricsTracker
from azul.file_handler import get_file_handler


class AgenticLoop:
    """Manages the autonomous agent loop: Think, Act, Observe."""
    
    def __init__(self, project_root: Path):
        """Initialize the agentic loop."""
        self.project_root = project_root
        self.llama = get_llama_client()
        self.session = get_session_manager(project_root)
        self.formatter = get_formatter()
        self.editor = get_editor()
        self.tool_executor = ToolExecutor(project_root)
        self.permissions = get_permission_manager()
        self.file_handler = get_file_handler()
    
    def _display_status(self, message: str) -> None:
        """
        Display a status message to the user in a consistent format.
        
        Args:
            message: Status message to display
        """
        self.formatter.console.print(f"[bold cyan][AZUL][/bold cyan] {message}")
    
    def _detect_plan(self, response: str) -> Optional[List[str]]:
        """
        Detect if the AI has generated a numbered plan from its response.
        
        Args:
            response: The AI's response text
            
        Returns:
            List of plan steps if detected, None otherwise
        """
        import re
        # Pattern to match numbered lists (1., 2., 3., etc.)
        plan_pattern = r'^\s*(\d+)\.\s+(.+)$'
        lines = response.split('\n')
        plan_steps = []
        
        for line in lines:
            match = re.match(plan_pattern, line.strip())
            if match:
                step_num = int(match.group(1))
                step_text = match.group(2).strip()
                plan_steps.append(step_text)
        
        # If we found 2+ steps, consider it a plan
        if len(plan_steps) >= 2:
            return plan_steps
        
        return None
    
    def _display_plan_progress(self, plan: List[str], completed_steps: List[int], current_step: int) -> None:
        """
        Display plan progress to the user.
        
        Args:
            plan: List of plan steps
            completed_steps: List of step indices that are completed
            current_step: Current step index (0-based)
        """
        if not plan:
            return
        
        progress_parts = []
        for i, step in enumerate(plan):
            step_num = i + 1
            if i in completed_steps:
                progress_parts.append(f"{step_num}. {step} ✓")
            elif i == current_step:
                progress_parts.append(f"{step_num}. {step} [in progress]")
            else:
                progress_parts.append(f"{step_num}. {step} [pending]")
        
        plan_display = " | ".join(progress_parts)
        self._display_status(f"Plan: {plan_display}")
    
    def _is_repeating(self, response: str, last_responses: List[str], similarity_threshold: float = 0.8) -> bool:
        """
        Check if the AI is repeating a previous response.
        
        Args:
            response: Current response text
            last_responses: List of previous responses
            similarity_threshold: Threshold for considering responses similar (0.0-1.0)
            
        Returns:
            True if response is similar to a previous one
        """
        if not last_responses:
            return False
        
        response_lower = response.lower().strip()
        
        # Simple similarity check: if response is very similar to any previous response
        for prev_response in last_responses:
            prev_lower = prev_response.lower().strip()
            
            # Calculate simple similarity (ratio of matching words)
            response_words = set(response_lower.split())
            prev_words = set(prev_lower.split())
            
            if len(response_words) == 0 or len(prev_words) == 0:
                continue
            
            # Jaccard similarity
            intersection = response_words & prev_words
            union = response_words | prev_words
            similarity = len(intersection) / len(union) if union else 0
            
            if similarity >= similarity_threshold:
                return True
        
        return False
    
    def execute(self, user_input: str) -> None:
        """
        Execute the agentic loop for a user prompt.
        
        This implements the "Think, Act, Observe" loop:
        1. AI Turn (Think): Generate response with potential tool calls
        2. System Turn (Act & Observe): Execute tools, capture results
        3. State Update: Add observations to conversation history
        4. Repeat until no tools or task complete
        """
        # Get conversation history
        conversation_history = self.session.get_recent_history(n=10)
        
        # Add initial tree() context if this is a new conversation
        user_input_with_context = user_input
        if len(conversation_history) <= 2:
            tree_output = generate_tree(self.project_root, max_depth=3)
            formatted_tree = f"Tool Output:\n{tree_output}"
            self.session.add_message("tool", formatted_tree)
        
        # Add user message to history
        self.session.add_message("user", user_input)
        
        # Plan state management
        plan: Optional[List[str]] = None
        current_step = 0
        completed_steps = []
        
        # Repetition detection
        last_responses: List[str] = []
        
        # Agentic loop: continue until task is complete
        # This loop forces the AI to be grounded - it cannot proceed without tool observations
        # It also auto-nudges the AI if it stalls without completing actions
        max_iterations = 20  # Safety limit (increased for complex tasks)
        max_nudges = 5  # Maximum auto-nudges before giving up
        iteration = 0
        nudge_count = 0
        task_in_progress = True
        
        while task_in_progress and iteration < max_iterations and nudge_count < max_nudges:
            iteration += 1
            
            # Get updated conversation history for this iteration
            conversation_history = self.session.get_recent_history(n=20)
            
            # Initialize metrics tracker
            tracker = MetricsTracker()
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
            stop_printing = False  # Flag to stop printing tokens when tool detected
            
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
                        # Immediately stop printing tokens to prevent hallucinated output
                        stop_printing = True
                        
                        # Check if we have a complete tool call
                        potential_tool = extract_tool_call(buffer)
                        if potential_tool:
                            tool_detected = True
                            tool_call = potential_tool
                            # Stop streaming - we found a tool
                            break
                    
                    # Display token to user (conversational text) - only if not stopped
                    if not stop_printing:
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
                if not tool_detected and not stop_printing:
                    sys.stdout.write('\n')
                    sys.stdout.flush()
                
                # If tool was detected but we stopped printing, ensure we have full response
                if stop_printing and not tool_detected:
                    # Continue buffering to get complete tool call
                    for token in stream:
                        buffer += token
                        response_content += token
                        potential_tool = extract_tool_call(buffer)
                        if potential_tool:
                            tool_detected = True
                            tool_call = potential_tool
                            break
                    
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
            
            # Detect plan in first iteration if not already detected
            if iteration == 1 and plan is None:
                detected_plan = self._detect_plan(response_content)
                if detected_plan:
                    plan = detected_plan
                    self._display_status("Plan detected:")
                    for i, step in enumerate(plan):
                        self._display_status(f"  {i+1}. {step}")
            
            # Display plan progress if we have a plan
            if plan:
                self._display_plan_progress(plan, completed_steps, current_step)
            
            # If tool was detected, extract it and execute
            tool_called_this_turn = False
            if tool_detected and tool_call:
                tool_called_this_turn = True
                nudge_count = 0  # Reset nudge counter on successful action
                
                # Remove tool call from conversational text
                conversational_text = remove_tool_call_from_content(response_content, tool_call)
                
                # Add assistant's conversational response (if any)
                if conversational_text.strip():
                    self.session.add_message("assistant", conversational_text)
                
                # Show status message
                tool_name = tool_call.tool_name
                
                # Handle exec tool calls
                if tool_name == "exec":
                    command = tool_call.arguments.get('command')
                    background = tool_call.arguments.get('background', False)
                    
                    if not command:
                        tool_output = "Error: exec() requires command argument"
                        formatted_output = f"Tool Output:\n{tool_output}"
                        self.session.add_message("tool", formatted_output)
                        continue
                    
                    # Display clear status message before execution
                    bg_status = " (background)" if background else ""
                    self._display_status(f"Executing: {command}{bg_status}")
                    
                    # Execute command (implicit permission - no confirmation required for exec)
                    if background:
                        # Background execution with real-time streaming
                        completion_event = threading.Event()
                        exit_code = [-1]  # Use list to allow modification in callback
                        
                        def on_complete(code):
                            exit_code[0] = code
                            completion_event.set()
                        
                        # Start async command using ToolExecutor
                        self.tool_executor.run_command_async(command, on_complete)
                        
                        # Wait for completion (output streams in real-time)
                        completion_event.wait()
                        
                        # Format tool output for AI with concrete result
                        if exit_code[0] == 0:
                            tool_output = f"Command '{command}' finished with exit code 0 (success)."
                            self._display_status(f"Background command completed successfully (exit code {exit_code[0]})")
                        else:
                            tool_output = f"Command '{command}' finished with exit code {exit_code[0]} (failed)."
                            self._display_status(f"Background command failed (exit code {exit_code[0]})")
                    else:
                        # Synchronous execution using ToolExecutor
                        exit_code, output = self.tool_executor.run_command_sync(command)
                        
                        # Display actual output to user clearly
                        if output:
                            self.formatter.console.print(f"\n[bold green]Command output:[/bold green]")
                            self.formatter.console.print(output)
                        
                        # Format tool output for AI with concrete result
                        if exit_code == 0:
                            tool_output = f"Command '{command}' finished with exit code 0 (success)."
                            if output:
                                # Include last few lines of output for verification
                                lines = output.strip().split('\n')
                                if len(lines) > 10:
                                    tool_output += f"\nLast 10 lines of output:\n" + '\n'.join(lines[-10:])
                                else:
                                    tool_output += f"\nOutput:\n{output}"
                        else:
                            tool_output = f"Command '{command}' finished with exit code {exit_code} (failed)."
                            if output:
                                # Include error output
                                lines = output.strip().split('\n')
                                if len(lines) > 10:
                                    tool_output += f"\nLast 10 lines of error output:\n" + '\n'.join(lines[-10:])
                                else:
                                    tool_output += f"\nError output:\n{output}"
                        
                        # Display result status to user
                        if exit_code == 0:
                            self._display_status(f"Command completed successfully (exit code {exit_code})")
                        else:
                            self._display_status(f"Command failed (exit code {exit_code})")
                    
                    # Add tool output to conversation history
                    formatted_output = f"Tool Output:\n{tool_output}"
                    self.session.add_message("tool", formatted_output)
                    
                    # Update plan progress if tool succeeded (for background commands)
                    if plan and exit_code[0] == 0:
                        if current_step < len(plan):
                            if current_step not in completed_steps:
                                completed_steps.append(current_step)
                            current_step = min(current_step + 1, len(plan) - 1)
                    
                    # Continue loop - AI will see command result and continue
                    continue
                
                # Handle read and tree tools (implicit permission)
                elif tool_name == "read":
                    file_path = tool_call.arguments.get('file_path', 'file')
                    self._display_status(f"Reading: {file_path}")
                    tool_output = self.tool_executor.execute_tool(
                        tool_call.tool_name,
                        tool_call.arguments
                    )
                    # Format as tool output observation
                    formatted_output = f"Tool Output:\n{tool_output}"
                    self.session.add_message("tool", formatted_output)
                    # Continue loop - AI will see the file content
                    continue
                
                elif tool_name == "tree":
                    self._display_status("Exploring project structure...")
                    tool_output = self.tool_executor.execute_tool(
                        tool_call.tool_name,
                        tool_call.arguments
                    )
                    # Format as tool output observation
                    formatted_output = f"Tool Output:\n{tool_output}"
                    self.session.add_message("tool", formatted_output)
                    # Continue loop - AI will see the directory structure
                    continue
                
                # Handle write tool (implicit permission - auto-execute)
                elif tool_name == "write":
                    file_path = tool_call.arguments.get('file_path')
                    content = tool_call.arguments.get('content', '')
                    if file_path and content:
                        self._display_status(f"Writing: {file_path}")
                        # Execute write directly (implicit permission)
                        success, error = self.editor.create_file(file_path, content, show_preview=False)
                        if not success and error:
                            tool_output = f"Error: {error}"
                            self._display_status(f"Failed to write {file_path}: {error}")
                        else:
                            # Provide concrete success message with file size
                            import os
                            try:
                                found_path = self.file_handler.find_path(file_path)
                                if found_path:
                                    file_size = os.path.getsize(found_path)
                                    tool_output = f"Successfully wrote {file_size} bytes to {file_path}"
                                    self._display_status(f"Successfully wrote {file_size} bytes to {file_path}")
                                else:
                                    tool_output = f"Successfully wrote file: {file_path}"
                                    self._display_status(f"Successfully wrote file: {file_path}")
                            except:
                                tool_output = f"Successfully wrote file: {file_path}"
                                self._display_status(f"Successfully wrote file: {file_path}")
                        
                        # Update plan progress if tool succeeded
                        if plan and success:
                            if current_step < len(plan):
                                if current_step not in completed_steps:
                                    completed_steps.append(current_step)
                                current_step = min(current_step + 1, len(plan) - 1)
                        
                        formatted_output = f"Tool Output:\n{tool_output}"
                        self.session.add_message("tool", formatted_output)
                        continue
                
                # Handle diff tool (explicit permission required)
                elif tool_name == "diff":
                    file_path = tool_call.arguments.get('file_path')
                    diff_content = tool_call.arguments.get('content') or tool_call.arguments.get('diff_content', '')
                    if file_path and diff_content:
                        self._display_status(f"Updating: {file_path}")
                        # Request permission and execute
                        self.formatter.print_info(f"\nDetected file edit: {file_path}")
                        # Wrap in markdown diff block for edit_file
                        diff_block = f"```diff\n{diff_content}\n```"
                        success, error = self.editor.edit_file(file_path, diff_block)
                        if success:
                            tool_output = f"Successfully updated {file_path}"
                            self._display_status(f"Successfully updated {file_path}")
                        else:
                            tool_output = f"Error updating {file_path}: {error}"
                            self._display_status(f"Failed to update {file_path}: {error}")
                        
                        # Update plan progress if tool succeeded
                        if plan and success:
                            if current_step < len(plan):
                                if current_step not in completed_steps:
                                    completed_steps.append(current_step)
                                current_step = min(current_step + 1, len(plan) - 1)
                        
                        formatted_output = f"Tool Output:\n{tool_output}"
                        self.session.add_message("tool", formatted_output)
                        # Continue loop - AI will see update result
                        continue
                
                elif tool_name == "delete":
                    file_path = tool_call.arguments.get('file_path')
                    if file_path:
                        self._display_status(f"Deleting: {file_path}")
                        # Request permission and execute
                        self.formatter.print_info(f"\nDetected file deletion: {file_path}")
                        success, error = self.editor.delete_file(file_path)
                        if success:
                            tool_output = f"Successfully deleted {file_path}"
                            self._display_status(f"Successfully deleted {file_path}")
                        else:
                            tool_output = f"Error deleting {file_path}: {error}"
                            self._display_status(f"Failed to delete {file_path}: {error}")
                        
                        # Update plan progress if tool succeeded
                        if plan and success:
                            if current_step < len(plan):
                                if current_step not in completed_steps:
                                    completed_steps.append(current_step)
                                current_step = min(current_step + 1, len(plan) - 1)
                        
                        formatted_output = f"Tool Output:\n{tool_output}"
                        self.session.add_message("tool", formatted_output)
                        # Continue loop - AI will see deletion result
                        continue
                
                # Unknown tool
                else:
                    tool_output = self.tool_executor.execute_tool(
                        tool_call.tool_name,
                        tool_call.arguments
                    )
                    formatted_output = f"Tool Output:\n{tool_output}"
                    self.session.add_message("tool", formatted_output)
                    continue
            
            # No tool detected - check if AI has completed or stalled
            if not tool_called_this_turn:
                # Add assistant response to history
                if response_content.strip():
                    self.session.add_message("assistant", response_content)
                
                # Check for repetition BEFORE checking completion
                is_repeating = self._is_repeating(response_content, last_responses)
                if is_repeating:
                    nudge_count += 1
                    self.formatter.print_warning(f"⚠️  Agent is repeating itself (attempt {nudge_count}/{max_nudges})")
                    
                    # Assertive nudge for repetition
                    nudge_message = (
                        "[SYSTEM-FEEDBACK] You are repeating yourself. Your last action failed. "
                        "Re-examine your plan and the last tool output, then decide on a new course of action. "
                        "If you cannot proceed, you must inform the user why."
                    )
                    
                    # Add plan context if available
                    if plan:
                        nudge_message += f"\n\nYour plan was:\n"
                        for i, step in enumerate(plan):
                            status = "✓" if i in completed_steps else "[pending]"
                            nudge_message += f"{i+1}. {step} {status}\n"
                        nudge_message += f"\nYou are currently on step {current_step + 1} of {len(plan)}."
                    
                    self.session.add_message("user", nudge_message)
                    last_responses.append(response_content.strip())
                    
                    # If repetition persists 2+ times, break loop
                    if nudge_count >= 2:
                        self.formatter.print_error("Agent loop broken: persistent repetition detected.")
                        self.formatter.print_error("The agent is stuck in a loop. Please try rephrasing your request.")
                        task_in_progress = False
                        break
                    
                    continue
                
                # Track response for future repetition detection
                if response_content.strip():
                    last_responses.append(response_content.strip())
                    # Keep only last 3 responses
                    if len(last_responses) > 3:
                        last_responses.pop(0)
                
                # Check for explicit task completion
                if "<task_complete>" in response_content.lower() or "task complete" in response_content.lower():
                    self.formatter.print_success("✅ Task complete.")
                    task_in_progress = False
                    break
                
                # Intelligent nudge: Analyze AI's response for unfulfilled intent
                response_lower = response_content.lower()
                
                # Heuristic keywords to detect unfulfilled intent
                action_phrases = [
                    "i will now",
                    "let's start by",
                    "next, i will",
                    "i'll run the command",
                    "let's execute",
                    "i will create",
                    "i will delete",
                    "i will read",
                    "i will write",
                    "i will update",
                    "i will modify",
                    "i will remove",
                    "i will run",
                    "i will execute",
                    "i will call",
                    "i will use",
                    "i will start",
                    "i will begin",
                    "i will list",
                    "i will check",
                    "i will verify",
                    "going to create",
                    "going to delete",
                    "going to run",
                    "about to create",
                    "about to delete",
                    "about to run"
                ]
                
                stalled_intent = None
                for phrase in action_phrases:
                    if phrase in response_lower:
                        stalled_intent = phrase
                        break
                
                if stalled_intent:
                    # AI described an action but didn't execute it - intelligent contextual nudge
                    nudge_count += 1
                    self.formatter.print_info(f"... (agent paused, providing intelligent nudge - attempt {nudge_count}/{max_nudges})")
                    
                    # Construct contextual nudge based on detected intent
                    # Extract more context from the response
                    intent_context = stalled_intent
                    if "delete" in response_lower:
                        intent_context = "delete files"
                    elif "create" in response_lower or "next.js" in response_lower or "nextjs" in response_lower:
                        intent_context = "create a Next.js app"
                    elif "list" in response_lower or "see" in response_lower:
                        intent_context = "list files"
                    elif "read" in response_lower:
                        intent_context = "read a file"
                    elif "write" in response_lower or "create" in response_lower:
                        intent_context = "write a file"
                    elif "run" in response_lower or "execute" in response_lower:
                        intent_context = "run a command"
                    
                    nudge_message = (
                        f"[SYSTEM-FEEDBACK] Your previous turn was incomplete. "
                        f"You stated an intent to act (e.g., '{stalled_intent}...') but did not provide a `<tool_code>` block. "
                        "You MUST provide the tool call to proceed. "
                        "For example, if you said you will delete files, first use <tool_code>exec('ls')</tool_code> or <tool_code>tree()</tool_code> to see what exists, "
                        "then use <tool_code>delete('filename')</tool_code> for each file."
                    )
                    
                    # Add plan context if available
                    if plan:
                        nudge_message += f"\n\nYour plan was:\n"
                        for i, step in enumerate(plan):
                            status = "✓" if i in completed_steps else "[pending]"
                            nudge_message += f"{i+1}. {step} {status}\n"
                        nudge_message += f"\nYou are currently on step {current_step + 1} of {len(plan)}."
                    
                    # Add intelligent nudge message to history
                    self.session.add_message("user", nudge_message)
                    
                    # Continue loop - AI will see the specific feedback and generate again
                    continue
                
                # No clear action intent detected - use generic but helpful nudge
                nudge_count += 1
                self.formatter.print_info(f"... (agent paused, providing generic nudge - attempt {nudge_count}/{max_nudges})")
                
                nudge_message = (
                    "[SYSTEM-FEEDBACK] Your previous turn did not result in an action or task completion. "
                    "Please re-evaluate your plan and provide the next `<tool_code>` action."
                )
                
                # Add plan context if available
                if plan:
                    nudge_message += f"\n\nYour plan was:\n"
                    for i, step in enumerate(plan):
                        status = "✓" if i in completed_steps else "[pending]"
                        nudge_message += f"{i+1}. {step} {status}\n"
                    nudge_message += f"\nYou are currently on step {current_step + 1} of {len(plan)}."
                
                # Add generic nudge message to history
                self.session.add_message("user", nudge_message)
                
                # Continue loop - AI will see the feedback and generate again
                continue
            
            # Display stats after tool execution (if we have stats)
            if stats and tool_called_this_turn:
                stats_text = (
                    f"[bold blue]Stats:[/bold blue] "
                    f"TTFT: [bold]{stats['ttft_ms']:.0f}ms[/bold] | "
                    f"Gen: [bold]{stats['generation_time_s']:.2f}s[/bold] | "
                    f"Prompt: [bold]{int(stats['prompt_tokens'])}[/bold] | "
                    f"Output: [bold]{int(stats['output_tokens'])}[/bold] | "
                    f"Speed: [bold]{stats['tokens_per_second']:.1f}[/bold] tok/s"
                )
                self.formatter.console.print(f"\n{stats_text}\n")
            
            # If tool was called, continue loop automatically (already handled above)
            # This point should not be reached if tool_called_this_turn is True
        
        # Save history
        self.session.save_history()

