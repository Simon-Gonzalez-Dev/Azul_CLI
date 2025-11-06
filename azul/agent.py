"""Clean state machine agent implementation."""

import re
import sys
from pathlib import Path
from typing import Optional

from azul.agent_state import AgentState, PlanStep
from azul.llama_client import get_llama_client
from azul.tools import ToolExecutor, ToolResult
from azul.tool_parser import extract_tool_call, remove_tool_call_from_content
from azul.formatter import get_formatter
from azul.tree_generator import generate_tree
from azul.session_manager import get_session_manager
from azul.editor import get_editor
from azul.permissions import get_permission_manager


class Agent:
    """Clean state machine agent - single source of truth architecture."""
    
    def __init__(self, project_root: Path, initial_prompt: str):
        """Initialize agent with state."""
        self.project_root = project_root
        self.state = AgentState(initial_prompt=initial_prompt)
        self.llama = get_llama_client()
        self.tool_executor = ToolExecutor(project_root)
        self.formatter = get_formatter()
        self.session = get_session_manager(project_root)
        self.editor = get_editor()
        self.permissions = get_permission_manager()
    
    def run(self) -> None:
        """Main agent loop - blocking execution."""
        # Phase 1: Planning
        self._generate_plan()
        
        if not self.state.plan:
            self.formatter.print_error("Failed to generate plan. Agent cannot proceed.")
            return
        
        # Display plan to user
        self.formatter.console.print("\n[bold cyan][AZUL][/bold cyan] Plan:")
        for i, step in enumerate(self.state.plan, 1):
            self.formatter.console.print(f"  {i}. {step.description}")
        self.formatter.console.print()
        
        # Phase 2: Execution - Multi-turn loop for each step
        while self.state.current_step < len(self.state.plan):
            step = self.state.get_current_step()
            if step is None:
                break
            
            # Execute one turn (Think -> Act -> Observe)
            # The turn will continue until next_step() is called or failure occurs
            success = self._execute_turn()
            
            if not success:
                # Check if we added a nudge - if so, retry the turn
                # Count how many nudges we've added for this step to avoid infinite loops
                if not hasattr(step, '_nudge_count'):
                    step._nudge_count = 0
                
                # Check if a nudge was added in the last turn
                if hasattr(step, '_nudge_added') and step._nudge_added:
                    step._nudge_count += 1
                    step._nudge_added = False  # Reset flag
                    if step._nudge_count < 3:  # Allow up to 3 retries
                        self.formatter.console.print(
                            f"[bold yellow][AZUL][/bold yellow] "
                            f"Retrying turn {step._nudge_count} after nudge...\n"
                        )
                        continue  # Retry the turn
                
                # Too many retries or no nudge - give up
                self.formatter.print_error(f"Agent failed to produce a valid action on step {self.state.current_step + 1}. Stopping execution.")
                if step:
                    step.status = "failed"
                break
        
        # Phase 3: Completion
        if self.state.is_complete():
            self.formatter.print_success("✅ All steps completed successfully.")
        else:
            self.formatter.print_warning("⚠️  Execution incomplete. Some steps may have failed.")
        
        # Sync state to session manager
        for msg in self.state.conversation_history:
            self.session.add_message(msg.get('role', 'user'), msg.get('content', ''))
        
        # Save session history
        self.session.save_history()
    
    def _generate_plan(self) -> None:
        """Generate plan from user prompt using planning prompt."""
        self.formatter.console.print("[bold cyan][AZUL][/bold cyan] Generating plan...\n")
        
        # Use planning prompt
        prompt = self.llama.build_prompt(
            self.state.initial_prompt,
            conversation_history=[],
            system_prompt=self.llama.PLANNING_PROMPT
        )
        
        # Generate plan
        response = ""
        try:
            stream = self.llama.stream_chat(
                self.state.initial_prompt,
                [],
                system_prompt=self.llama.PLANNING_PROMPT
            )
            
            # Stream response to user with thinking prefix
            self.formatter.console.print("[bold blue][AZUL thinking]:[/bold blue] ", end="")
            for token in stream:
                response += token
                self.formatter.console.print(token, end="", style="")
            self.formatter.console.print()  # Newline after completion
        except Exception as e:
            self.formatter.print_error(f"Error generating plan: {e}")
            return
        
        # Parse plan from response
        plan_steps = self._parse_plan(response)
        
        if plan_steps:
            self.state.plan = plan_steps
            self.state.planning_complete = True
            self.state.add_message("user", self.state.initial_prompt)
            self.state.add_message("assistant", response)
        else:
            self.formatter.print_error("Could not parse plan from response. Expected numbered list.")
    
    def _parse_plan(self, response: str) -> list[PlanStep]:
        """Parse numbered plan from response."""
        plan_steps = []
        # Pattern to match numbered lists: 1. description, 2. description, etc.
        pattern = r'^\s*(\d+)\.\s+(.+)$'
        
        for line in response.split('\n'):
            line = line.strip()
            match = re.match(pattern, line)
            if match:
                step_num = int(match.group(1))
                description = match.group(2).strip()
                plan_steps.append(PlanStep(description=description))
        
        return plan_steps
    
    def _execute_turn(self) -> bool:
        """
        Execute one turn (Think -> Act -> Observe) for the current step.
        Returns True if turn was successful, False if agent failed to produce action.
        The step continues until next_step() is called.
        """
        step = self.state.get_current_step()
        if step is None:
            return False
        
        # Mark step as in progress if not already
        if step.status == "pending":
            step.status = "in_progress"
            step_num = self.state.current_step + 1
            # Display step start (only once)
            self.formatter.console.print(
                f"\n[bold cyan][AZUL][/bold cyan] "
                f"Working on step {step_num}/{len(self.state.plan)}: {step.description}\n"
            )
        
        step_num = self.state.current_step + 1
        
        # Build execution prompt with plan context
        plan_context = self._build_plan_context()
        execution_prompt = self.llama.EXECUTION_PROMPT.format(
            total_steps=len(self.state.plan),
            current_step=step_num,
            current_step_description=step.description,
            plan_context=plan_context
        )
        
        # Add context: initial tree if first turn of first step
        if self.state.current_step == 0 and len(self.state.conversation_history) <= 1:
            tree_output = generate_tree(self.project_root, max_depth=3)
            self.state.add_message("tool", f"Tool Output:\n{tree_output}")
        
        # --- EAGER PARSING LOGIC WITH TRANSPARENT THINKING ---
        tool_call_buffer = ""
        parsing_tool_call = False
        tool_detected = False
        tool_call = None
        conversational_text = ""
        thinking_prefix_shown = False
        
        try:
            # Start streaming from the AI
            stream = self.llama.stream_chat(
                f"Execute step {step_num}: {step.description}",
                self.state.conversation_history,
                system_prompt=execution_prompt
            )
            
            # Watch for the start of a tool call
            for token in stream:
                # Check if we've detected the start of a tool call
                if not parsing_tool_call:
                    # Look for complete opening tag in current token or accumulated buffer
                    temp_buffer = conversational_text + token
                    
                    # Check for complete <tool_code> tag (not just substring)
                    tag_pos = temp_buffer.lower().find("<tool_code>")
                    if tag_pos != -1:
                        # Extract any text before the tag as conversational
                        if tag_pos > 0:
                            conversational_text = temp_buffer[:tag_pos].strip()
                            # Display any remaining conversational text before tool
                            if conversational_text:
                                if not thinking_prefix_shown:
                                    self.formatter.console.print("[bold blue][AZUL thinking]:[/bold blue] ", end="")
                                    thinking_prefix_shown = True
                                self.formatter.console.print(conversational_text, end="", style="")
                        
                        # Start parsing tool call
                        parsing_tool_call = True
                        tool_call_buffer = temp_buffer[tag_pos:]
                        
                        # Newline after thinking if we displayed any
                        if thinking_prefix_shown:
                            self.formatter.console.print()
                        continue
                    else:
                        # Still conversational text - stream it with thinking prefix
                        conversational_text += token
                        if not thinking_prefix_shown:
                            self.formatter.console.print("[bold blue][AZUL thinking]:[/bold blue] ", end="")
                            thinking_prefix_shown = True
                        # Print token without newline for streaming effect
                        self.formatter.console.print(token, end="", style="")
                        continue
                
                # We're parsing a tool call - buffer silently (don't print)
                if parsing_tool_call:
                    tool_call_buffer += token
                    
                    # Check if we have a complete tool call
                    potential_tool = extract_tool_call(tool_call_buffer)
                    if potential_tool:
                        tool_detected = True
                        tool_call = potential_tool
                        # Stop streaming immediately and execute
                        break
            
            # If we stopped streaming but didn't detect a tool yet, try one more time
            if parsing_tool_call and not tool_detected:
                potential_tool = extract_tool_call(tool_call_buffer)
                if potential_tool:
                    tool_detected = True
                    tool_call = potential_tool
            
            # Final newline if we printed conversational text
            if thinking_prefix_shown and not parsing_tool_call:
                self.formatter.console.print()
        
        except Exception as e:
            self.formatter.print_error(f"Error during AI generation: {e}")
            # Don't mark step as failed - allow retry
            return False
        
        # If no tool detected, return False to indicate turn failure
        if not tool_detected or not tool_call:
            self.formatter.print_error("AI did not provide a tool call for this turn.")
            nudge_added = False
            if conversational_text.strip():
                self.state.add_message("assistant", conversational_text)
                # Add forceful nudge to guide AI to act
                # Check recent tool history to provide context-aware guidance
                recent_tools = [msg.get('content', '') for msg in self.state.conversation_history[-5:] 
                               if msg.get('role') == 'assistant' and '<tool_code>' in msg.get('content', '')]
                
                # If we just observed, we must take action
                if any('exec' in tool and 'ls' in tool for tool in recent_tools):
                    nudge_message = (
                        f"[SYSTEM-FEEDBACK] CRITICAL: You have already observed the files with ls. "
                        f"You MUST now take ACTION, not observe again. "
                        f"For step '{step.description}', you must DELETE files using delete('path') for each file/directory. "
                        f"Example: <tool_code>delete('.next/')</tool_code> or <tool_code>delete('.gitignore')</tool_code>. "
                        f"DO NOT run ls again. You must DELETE files now."
                    )
                else:
                    nudge_message = (
                        f"[SYSTEM-FEEDBACK] You stated your intent but did not provide a tool call. "
                        f"You MUST use a <tool_code> block to execute actions. "
                        f"For the current step '{step.description}', please provide a specific tool call. "
                        f"If you need to delete, use delete('path') for each file/directory. "
                        f"Then verify with exec('ls') before calling next_step()."
                    )
                self.state.add_message("user", nudge_message)
                nudge_added = True
            
            # Mark that we added a nudge for retry logic
            if not hasattr(step, '_nudge_added'):
                step._nudge_added = False
            step._nudge_added = nudge_added
            
            # Don't mark step as failed yet - allow retry
            return False
        
        # Remove tool call from conversational text if it was mixed
        if conversational_text.strip():
            self.state.add_message("assistant", conversational_text)
        
        # Add the tool call as assistant message
        self.state.add_message("assistant", tool_call_buffer)
        
        # Execute tool immediately
        tool_result = self._execute_tool(tool_call)
        
        # Format tool result for AI
        tool_output = self._format_tool_result(tool_result)
        self.state.add_message("tool", f"Tool Output:\n{tool_output}")
        
        # Display tool result to user
        self._display_tool_result(tool_call, tool_result)
        
        # If tool succeeded but wasn't next_step(), add a contextual reminder
        # This helps prevent the AI from stopping after a single observation
        if tool_result.success and tool_call.tool_name != "next_step":
            # Provide specific guidance based on the tool used
            if tool_call.tool_name == "exec" and "ls" in tool_call.arguments.get('command', ''):
                # After observation, we should take action
                continuation_hint = (
                    f"[SYSTEM-HINT] You have observed the files. "
                    f"Now you MUST take action to complete step {step_num}: '{step.description}'. "
                    f"If you need to delete files, use delete('path') for each file/directory, or exec('rm -rf path') for shell operations. "
                    f"After taking actions, verify with exec('ls') and then call next_step() when done."
                )
            elif tool_call.tool_name == "read":
                # After reading, we might need to write or diff
                continuation_hint = (
                    f"[SYSTEM-HINT] You have read the file. "
                    f"Continue working on step {step_num}: '{step.description}'. "
                    f"Use write(), diff(), or delete() as needed, then call next_step() when complete."
                )
            else:
                # Generic continuation hint
                continuation_hint = (
                    f"[SYSTEM-HINT] Tool executed successfully. "
                    f"Continue working on step {step_num}: '{step.description}'. "
                    f"Use additional tools as needed, then call next_step() when the step is complete."
                )
            # Add hint as a user message to guide next turn
            self.state.add_message("user", continuation_hint)
        
        # Handle tool result - check for next_step() tool
        if tool_call.tool_name == "next_step":
            # AI has decided the step is complete
            step.status = "completed"
            self.state.mark_step_completed()
            self.formatter.print_success(f"Step {step_num} completed. Moving to next step.")
            # Add confirmation to history
            self.state.add_message("tool", "Tool Output:\nConfirmed. Moving to next step.")
            return True
        
        # Regular tool execution - update step status based on result
        if tool_result.success:
            # Tool succeeded - step continues (don't mark as completed yet)
            # The step remains in_progress until next_step() is called
            pass  # Step stays in_progress
        else:
            # Tool failed - implement self-correction logic
            self.state.mark_step_failed(tool_result.message)
            self.formatter.print_error(f"Tool execution failed: {tool_result.message}")
            
            # SELF-CORRECTION LOGIC: Allow agent to recover from failure
            if self._should_attempt_correction(step, tool_result):
                self.formatter.console.print(
                    f"\n[bold yellow][AZUL][/bold yellow] "
                    f"Attempting self-correction for step {step_num}...\n"
                )
                
                # Format tool result for AI
                tool_output = self._format_tool_result(tool_result)
                self.state.add_message("tool", f"Tool Output:\n{tool_output}")
                
                # Formulate corrective prompt
                error_message = tool_result.stderr or tool_result.message
                correction_prompt = (
                    f"[SYSTEM-FEEDBACK] Your last action failed with the error: '{error_message}'. "
                    f"Please re-examine your plan and the state of the filesystem. "
                    f"You MUST propose a different action to recover. "
                    f"If you were trying to delete files, you MUST first use exec('ls -laF') to see what actually exists. "
                    f"Then delete files one at a time using concrete paths (no wildcards)."
                )
                
                self.state.add_message("user", correction_prompt)
                
                # Retry the turn with correction context
                return self._execute_turn_with_correction()
            else:
                # Cannot correct - step failed
                step.status = "failed"
                return False
        
        return True
    
    def _execute_tool(self, tool_call) -> ToolResult:
        """Execute a tool call and return structured result."""
        tool_name = tool_call.tool_name
        arguments = tool_call.arguments
        
        # Handle tools that require permissions
        if tool_name == "write":
            # Write is implicit permission - auto-execute
            file_path = arguments.get('file_path')
            content = arguments.get('content', '')
            if file_path and content:
                success, error = self.editor.create_file(file_path, content, show_preview=False)
                if success:
                    import os
                    try:
                        from azul.file_handler import get_file_handler
                        file_handler = get_file_handler()
                        found_path = file_handler.find_path(file_path)
                        if found_path:
                            file_size = os.path.getsize(found_path)
                            return ToolResult(
                                success=True,
                                stdout=f"File written: {file_path} ({file_size} bytes)",
                                message=f"Successfully wrote {file_size} bytes to {file_path}"
                            )
                    except:
                        pass
                    return ToolResult(success=True, message=f"Successfully wrote file: {file_path}")
                else:
                    return ToolResult(success=False, stderr=error or "Unknown error", message=f"Error: {error}")
        
        elif tool_name == "diff":
            # Diff requires explicit permission
            file_path = arguments.get('file_path')
            diff_content = arguments.get('content') or arguments.get('diff_content', '')
            if file_path and diff_content:
                # Show preview and request permission
                diff_block = f"```diff\n{diff_content}\n```"
                self.formatter.print_info(f"\nDetected file edit: {file_path}")
                success, error = self.editor.edit_file(file_path, diff_block, show_preview=True)
                if success:
                    return ToolResult(success=True, message=f"Successfully updated {file_path}")
                else:
                    return ToolResult(success=False, stderr=error or "Unknown error", message=f"Error: {error}")
        
        elif tool_name == "delete":
            # Delete requires explicit permission
            file_path = arguments.get('file_path')
            if file_path:
                self.formatter.print_info(f"\nDetected file deletion: {file_path}")
                success, error = self.editor.delete_file(file_path, show_preview=True)
                if success:
                    return ToolResult(success=True, message=f"Successfully deleted {file_path}")
                else:
                    return ToolResult(success=False, stderr=error or "Unknown error", message=f"Error: {error}")
        
        # For other tools (read, tree, exec), use tool executor
        result = self.tool_executor.execute_tool(tool_name, arguments)
        return result
    
    def _format_tool_result(self, result: ToolResult) -> str:
        """Format tool result for AI consumption."""
        if result.success:
            output = f"Success: {result.message}"
            if result.stdout:
                output += f"\nOutput:\n{result.stdout}"
        else:
            output = f"Error: {result.message}"
            if result.stderr:
                output += f"\nError details:\n{result.stderr}"
            if result.exit_code != 0:
                output += f"\nExit code: {result.exit_code}"
        
        return output
    
    def _display_tool_result(self, tool_call, result: ToolResult) -> None:
        """Display tool result to user using formatter."""
        tool_name = tool_call.tool_name
        
        if tool_name == "exec":
            command = tool_call.arguments.get('command', '')
            background = tool_call.arguments.get('background', False)
            
            # Show command being executed
            bg_text = " (background)" if background else ""
            self.formatter.console.print(f"[bold cyan][AZUL][/bold cyan] Executing: {command}{bg_text}\n")
            
            # Show output
            if result.stdout:
                self.formatter.console.print(f"[bold green]Command output:[/bold green]")
                self.formatter.console.print(result.stdout)
            
            if result.stderr:
                self.formatter.console.print(f"\n[bold red]Error output:[/bold red]")
                self.formatter.console.print(result.stderr)
            
            # Show result
            if result.exit_code == 0:
                self.formatter.console.print(f"\n[bold green]✓ Command succeeded (exit code {result.exit_code})[/bold green]\n")
            else:
                self.formatter.console.print(f"\n[bold red]✗ Command failed (exit code {result.exit_code})[/bold red]\n")
        
        elif tool_name in ("read", "tree"):
            # For read/tree, show output
            if result.stdout:
                self.formatter.console.print(f"\n[bold cyan]Result:[/bold cyan]")
                self.formatter.console.print(result.stdout)
        
        elif tool_name == "write":
            if result.success:
                self.formatter.print_success(result.message)
            else:
                self.formatter.print_error(result.message)
        
        elif tool_name == "diff":
            if result.success:
                self.formatter.print_success(result.message)
            else:
                self.formatter.print_error(result.message)
        
        elif tool_name == "delete":
            if result.success:
                self.formatter.print_success(result.message)
            else:
                self.formatter.print_error(result.message)
    
    def _should_attempt_correction(self, step: PlanStep, tool_result: ToolResult) -> bool:
        """Determine if we should attempt self-correction for a failed step."""
        # Don't correct if we've already tried correcting this step
        if hasattr(step, '_correction_attempted') and step._correction_attempted:
            return False
        
        # Only attempt correction for certain types of errors
        error_msg = (tool_result.stderr or tool_result.message or "").lower()
        
        # Attempt correction for:
        # - File not found errors (might need to observe first)
        # - Invalid path/wildcard errors (definitely needs correction)
        # - Path outside project errors
        if any(phrase in error_msg for phrase in [
            "not found",
            "does not exist",
            "wildcard",
            "invalid path",
            "outside the project"
        ]):
            return True
        
        return False
    
    def _execute_turn_with_correction(self) -> bool:
        """Execute one turn with correction context - allows recovery from failure."""
        step = self.state.get_current_step()
        if step is None:
            return False
        
        # Mark that we've attempted correction
        if not hasattr(step, '_correction_attempted'):
            step._correction_attempted = True
        step.status = "in_progress"
        step_num = self.state.current_step + 1
        
        self.formatter.console.print(
            f"[bold cyan][AZUL][/bold cyan] "
            f"Retrying with correction context...\n"
        )
        
        # Use same execution prompt but with correction context in history
        plan_context = self._build_plan_context()
        execution_prompt = self.llama.EXECUTION_PROMPT.format(
            total_steps=len(self.state.plan),
            current_step=step_num,
            current_step_description=step.description,
            plan_context=plan_context
        )
        
        # EAGER PARSING with correction context and transparent thinking
        tool_call_buffer = ""
        parsing_tool_call = False
        tool_detected = False
        tool_call = None
        conversational_text = ""
        thinking_prefix_shown = False
        
        try:
            stream = self.llama.stream_chat(
                f"Continue working on step {step_num}: {step.description}",
                self.state.conversation_history,
                system_prompt=execution_prompt
            )
            
            for token in stream:
                if not parsing_tool_call:
                    temp_buffer = conversational_text + token
                    tag_pos = temp_buffer.lower().find("<tool_code>")
                    if tag_pos != -1:
                        if tag_pos > 0:
                            conversational_text = temp_buffer[:tag_pos].strip()
                            if conversational_text:
                                if not thinking_prefix_shown:
                                    self.formatter.console.print("[bold blue][AZUL thinking]:[/bold blue] ", end="")
                                    thinking_prefix_shown = True
                                self.formatter.console.print(conversational_text, end="", style="")
                        parsing_tool_call = True
                        tool_call_buffer = temp_buffer[tag_pos:]
                        if thinking_prefix_shown:
                            self.formatter.console.print()
                        continue
                    else:
                        conversational_text += token
                        if not thinking_prefix_shown:
                            self.formatter.console.print("[bold blue][AZUL thinking]:[/bold blue] ", end="")
                            thinking_prefix_shown = True
                        self.formatter.console.print(token, end="", style="")
                        continue
                
                if parsing_tool_call:
                    tool_call_buffer += token
                    potential_tool = extract_tool_call(tool_call_buffer)
                    if potential_tool:
                        tool_detected = True
                        tool_call = potential_tool
                        break
            
            if parsing_tool_call and not tool_detected:
                potential_tool = extract_tool_call(tool_call_buffer)
                if potential_tool:
                    tool_detected = True
                    tool_call = potential_tool
            
            if thinking_prefix_shown and not parsing_tool_call:
                self.formatter.console.print()
        
        except Exception as e:
            self.formatter.print_error(f"Error during correction: {e}")
            step.status = "failed"
            return False
        
        if not tool_detected or not tool_call:
            self.formatter.print_error("AI did not provide a tool call during correction attempt.")
            step.status = "failed"
            return False
        
        if conversational_text.strip():
            self.state.add_message("assistant", conversational_text)
        
        self.state.add_message("assistant", tool_call_buffer)
        
        # Handle tool execution
        if tool_call.tool_name == "next_step":
            # AI decided step is complete after correction
            step.status = "completed"
            self.state.mark_step_completed()
            self.formatter.print_success(f"Step {step_num} completed after correction. Moving to next step.")
            self.state.add_message("tool", "Tool Output:\nConfirmed. Moving to next step.")
            return True
        
        # Execute regular tool
        tool_result = self._execute_tool(tool_call)
        
        # Format and add result
        tool_output = self._format_tool_result(tool_result)
        self.state.add_message("tool", f"Tool Output:\n{tool_output}")
        
        # Display result
        self._display_tool_result(tool_call, tool_result)
        
        # Update status
        if tool_result.success:
            return True  # Step continues
        else:
            step.status = "failed"
            return False
    
    def _build_plan_context(self) -> str:
        """Build plan context string for execution prompt."""
        if not self.state.plan:
            return "No plan available."
        
        context_parts = []
        for i, step in enumerate(self.state.plan, 1):
            status_symbol = {
                "pending": "[pending]",
                "in_progress": "[in progress]",
                "completed": "✓",
                "failed": "✗"
            }.get(step.status, "[?]")
            context_parts.append(f"{i}. {step.description} {status_symbol}")
        
        return "\n".join(context_parts)
