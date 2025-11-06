"""Tool executor for agentic operations - returns structured results only."""

import subprocess
import threading
import pty
import os
import select
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

from azul.file_handler import get_file_handler
from azul.editor import get_editor
from azul.tree_generator import generate_tree
from azul.sandbox import get_sandbox


@dataclass
class ToolResult:
    """Structured result from tool execution."""
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for AI consumption."""
        return {
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "message": self.message
        }


class ToolExecutor:
    """Executes tools called by the AI agent. Returns structured results only."""
    
    def __init__(self, project_root: Path):
        """Initialize tool executor."""
        self.project_root = project_root
        self.file_handler = get_file_handler()
        self.editor = get_editor()
        self.sandbox = get_sandbox(project_root)
    
    def execute_tree(self) -> ToolResult:
        """Execute tree() tool - display directory structure."""
        try:
            tree_output = generate_tree(self.project_root, max_depth=3)
            return ToolResult(
                success=True,
                stdout=tree_output,
                message="Directory structure retrieved"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                stderr=str(e),
                message=f"Error generating tree: {e}"
            )
    
    def execute_read(self, file_path: str) -> ToolResult:
        """Execute read() tool - read file content."""
        try:
            content, error = self.file_handler.read_file(file_path)
            
            if error:
                return ToolResult(
                    success=False,
                    stderr=error,
                    message=f"Error reading file: {error}"
                )
            
            formatted_content = f"--- file: {file_path} ---\n{content}"
            return ToolResult(
                success=True,
                stdout=formatted_content,
                message=f"File {file_path} read successfully"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                stderr=str(e),
                message=f"Error reading file: {e}"
            )
    
    def execute_write(self, file_path: str, content: str) -> ToolResult:
        """Execute write() tool - create or overwrite file."""
        try:
            # Validate path
            safe_path = self.sandbox.get_safe_path(file_path)
            if safe_path is None:
                return ToolResult(
                    success=False,
                    stderr=f"File path is outside the project directory: {file_path}",
                    message=f"Invalid path: {file_path}"
                )
            
            # Write file
            error = self.file_handler.write_file(file_path, content)
            if error:
                return ToolResult(
                    success=False,
                    stderr=error,
                    message=f"Error writing file: {error}"
                )
            
            # Get file size
            import os
            try:
                file_size = os.path.getsize(safe_path)
                return ToolResult(
                    success=True,
                    stdout=f"File written: {file_path} ({file_size} bytes)",
                    message=f"Successfully wrote {file_size} bytes to {file_path}"
                )
            except:
                return ToolResult(
                    success=True,
                    stdout=f"File written: {file_path}",
                    message=f"Successfully wrote file: {file_path}"
                )
        except Exception as e:
            return ToolResult(
                success=False,
                stderr=str(e),
                message=f"Error writing file: {e}"
            )
    
    def execute_diff(self, file_path: str, diff_content: str) -> ToolResult:
        """Execute diff() tool - apply unified diff."""
        try:
            # Validate path
            safe_path = self.sandbox.get_safe_path(file_path)
            if safe_path is None:
                return ToolResult(
                    success=False,
                    stderr=f"File path is outside the project directory: {file_path}",
                    message=f"Invalid path: {file_path}"
                )
            
            # Check if file exists
            if not self.file_handler.file_exists(file_path):
                return ToolResult(
                    success=False,
                    stderr=f"File not found: {file_path}",
                    message=f"File not found: {file_path}"
                )
            
            # Wrap in markdown diff block for edit_file
            diff_block = f"```diff\n{diff_content}\n```"
            success, error = self.editor.edit_file(file_path, diff_block, show_preview=False)
            
            if success:
                return ToolResult(
                    success=True,
                    stdout=f"File updated: {file_path}",
                    message=f"Successfully updated {file_path}"
                )
            else:
                return ToolResult(
                    success=False,
                    stderr=error or "Unknown error",
                    message=f"Error updating {file_path}: {error}"
                )
        except Exception as e:
            return ToolResult(
                success=False,
                stderr=str(e),
                message=f"Error applying diff: {e}"
            )
    
    def execute_delete(self, file_path: str) -> ToolResult:
        """Execute delete() tool - delete file or directory."""
        try:
            # STRICT INPUT VALIDATION: Only accept single, concrete file paths
            if not file_path or not isinstance(file_path, str):
                return ToolResult(
                    success=False,
                    stderr="Invalid input: file_path must be a non-empty string",
                    message="Invalid file_path argument"
                )
            
            file_path = file_path.strip()
            
            # Reject wildcards and shell patterns - delete tool only accepts single paths
            if '*' in file_path or '?' in file_path or '[' in file_path or '**' in file_path:
                return ToolResult(
                    success=False,
                    stderr=f"Invalid path: '{file_path}' contains wildcards. The delete() tool only accepts single, concrete file or directory paths. Use exec('rm -rf ...') for shell-style operations with wildcards.",
                    message=f"Wildcards not allowed in delete() tool. Use exec('rm -rf ...') for shell patterns."
                )
            
            # Validate path - prevent dangerous operations
            if file_path == "/" or file_path == "." or file_path == "..":
                return ToolResult(
                    success=False,
                    stderr=f"Cannot delete root path or current directory: {file_path}",
                    message=f"Invalid delete target: {file_path}"
                )
            
            # Validate path is within sandbox
            safe_path = self.sandbox.get_safe_path(file_path)
            if safe_path is None:
                return ToolResult(
                    success=False,
                    stderr=f"Path is outside the project directory: {file_path}",
                    message=f"Invalid path: {file_path}"
                )
            
            # Additional safety check: ensure we're not deleting the project root itself
            if safe_path.resolve() == self.project_root.resolve():
                return ToolResult(
                    success=False,
                    stderr=f"Cannot delete the project root directory: {file_path}",
                    message=f"Invalid delete target: {file_path}"
                )
            
            # Check if path actually exists using os.path.exists
            import os
            if not os.path.exists(safe_path):
                # File doesn't exist - this is actually a success case (nothing to delete)
                # Return success with informational message
                return ToolResult(
                    success=True,
                    stdout=f"Path does not exist (already deleted or never existed): {file_path}",
                    message=f"Path {file_path} does not exist - nothing to delete"
                )
            
            # Delete file or directory
            success, error = self.editor.delete_file(file_path, show_preview=False)
            
            if success:
                return ToolResult(
                    success=True,
                    stdout=f"Deleted: {file_path}",
                    message=f"Successfully deleted {file_path}"
                )
            else:
                return ToolResult(
                    success=False,
                    stderr=error or "Unknown error",
                    message=f"Error deleting {file_path}: {error}"
                )
        except Exception as e:
            return ToolResult(
                success=False,
                stderr=str(e),
                message=f"Error deleting: {e}"
            )
    
    def execute_exec(self, command: str, background: bool = False) -> ToolResult:
        """
        Execute exec() tool - run shell command.
        
        Args:
            command: Shell command to execute
            background: Whether to run in background (for long-running commands)
            
        Returns:
            ToolResult with structured output
        """
        try:
            if background:
                # For background commands, stream output in real-time
                return self._run_command_async_stream(command)
            else:
                # Synchronous execution - buffer output
                return self._run_command_sync_capture(command)
        except Exception as e:
            return ToolResult(
                success=False,
                stderr=str(e),
                exit_code=-1,
                message=f"Error executing command: {e}"
            )
    
    def _run_command_sync_capture(self, command: str) -> ToolResult:
        """
        Run command synchronously and capture all output.
        Does NOT print to stdout - only captures.
        
        Returns:
            ToolResult with structured output
        """
        try:
            result = subprocess.run(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(self.project_root),
                timeout=300  # 5 minute timeout
            )
            
            stdout = result.stdout if result.stdout else ""
            stderr = result.stderr if result.stderr else ""
            
            return ToolResult(
                success=(result.returncode == 0),
                stdout=stdout,
                stderr=stderr,
                exit_code=result.returncode,
                message=f"Command finished with exit code {result.returncode}"
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                stderr="Command timed out after 5 minutes",
                exit_code=-1,
                message="Command timed out"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                stderr=str(e),
                exit_code=-1,
                message=f"Error executing command: {e}"
            )
    
    def _run_command_async_capture(self, command: str) -> ToolResult:
        """
        Run command asynchronously with pty support for interactive commands.
        Captures all output without printing to stdout.
        
        Returns:
            ToolResult with structured output
        """
        stdout_buffer = []
        stderr_buffer = []
        exit_code = [-1]
        error_occurred = [None]
        
        def target():
            try:
                # Create a pseudo-terminal for interactive commands
                master_fd, slave_fd = pty.openpty()
                
                # Start the process
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    close_fds=True,
                    cwd=str(self.project_root),
                    preexec_fn=os.setsid
                )
                
                os.close(slave_fd)
                
                # Read output and handle interactive prompts
                while process.poll() is None:
                    r, _, _ = select.select([master_fd], [], [], 0.1)
                    if r:
                        try:
                            data = os.read(master_fd, 1024)
                            if data:
                                output = data.decode('utf-8', errors='replace')
                                stdout_buffer.append(output)
                                
                                # Handle interactive prompts automatically
                                output_lower = output.lower()
                                
                                if "ok to proceed?" in output_lower or "ok to proceed? (y)" in output_lower:
                                    os.write(master_fd, b'y\n')
                                elif "would you like to use" in output_lower and "defaults?" in output_lower:
                                    os.write(master_fd, b'\n')
                                elif "would you like to use typescript?" in output_lower:
                                    os.write(master_fd, b'y\n')
                                elif "would you like to use eslint?" in output_lower:
                                    os.write(master_fd, b'y\n')
                                elif "would you like to use" in output_lower and "?" in output_lower:
                                    os.write(master_fd, b'\n')
                        except OSError:
                            break
                
                process.wait()
                os.close(master_fd)
                exit_code[0] = process.returncode
                
            except Exception as e:
                error_occurred[0] = str(e)
                exit_code[0] = -1
        
        # Run in thread and wait
        thread = threading.Thread(target=target, daemon=False)
        thread.start()
        thread.join()  # Wait for completion
        
        stdout = "".join(stdout_buffer)
        stderr = "".join(stderr_buffer) if stderr_buffer else ""
        
        if error_occurred[0]:
            stderr = error_occurred[0]
        
        return ToolResult(
            success=(exit_code[0] == 0),
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code[0],
            message=f"Command finished with exit code {exit_code[0]}"
        )
    
    def _run_command_async_stream(self, command: str) -> ToolResult:
        """
        Run command asynchronously with pty support, streaming output in real-time.
        For background commands - streams output line-by-line with [exec]: prefix.
        
        Returns:
            ToolResult with structured output (also streamed to console)
        """
        from azul.formatter import get_formatter
        formatter = get_formatter()
        
        stdout_buffer = []
        stderr_buffer = []
        exit_code = [-1]
        error_occurred = [None]
        
        def target():
            try:
                # Create a pseudo-terminal for interactive commands
                master_fd, slave_fd = pty.openpty()
                
                # Start the process
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    close_fds=True,
                    cwd=str(self.project_root),
                    preexec_fn=os.setsid
                )
                
                os.close(slave_fd)
                
                # Read output line-by-line and stream to console
                line_buffer = ""
                while process.poll() is None:
                    r, _, _ = select.select([master_fd], [], [], 0.1)
                    if r:
                        try:
                            data = os.read(master_fd, 1024)
                            if data:
                                output = data.decode('utf-8', errors='replace')
                                stdout_buffer.append(output)
                                line_buffer += output
                                
                                # Stream complete lines to console
                                while '\n' in line_buffer:
                                    line, line_buffer = line_buffer.split('\n', 1)
                                    if line.strip():  # Only print non-empty lines
                                        formatter.console.print(f"[exec]: {line}")
                                
                                # Handle interactive prompts automatically
                                output_lower = output.lower()
                                
                                if "ok to proceed?" in output_lower or "ok to proceed? (y)" in output_lower:
                                    os.write(master_fd, b'y\n')
                                elif "would you like to use" in output_lower and "defaults?" in output_lower:
                                    os.write(master_fd, b'\n')
                                elif "would you like to use typescript?" in output_lower:
                                    os.write(master_fd, b'y\n')
                                elif "would you like to use eslint?" in output_lower:
                                    os.write(master_fd, b'y\n')
                                elif "would you like to use" in output_lower and "?" in output_lower:
                                    os.write(master_fd, b'\n')
                        except OSError:
                            break
                
                # Print any remaining buffer
                if line_buffer.strip():
                    formatter.console.print(f"[exec]: {line_buffer}")
                
                process.wait()
                os.close(master_fd)
                exit_code[0] = process.returncode
                
            except Exception as e:
                error_occurred[0] = str(e)
                exit_code[0] = -1
        
        # Run in thread and wait
        thread = threading.Thread(target=target, daemon=False)
        thread.start()
        thread.join()  # Wait for completion
        
        stdout = "".join(stdout_buffer)
        stderr = "".join(stderr_buffer) if stderr_buffer else ""
        
        if error_occurred[0]:
            stderr = error_occurred[0]
        
        return ToolResult(
            success=(exit_code[0] == 0),
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code[0],
            message=f"Command finished with exit code {exit_code[0]}"
        )
    
    def execute_next_step(self) -> ToolResult:
        """
        Execute next_step() tool - signal that current plan step is complete.
        
        Returns:
            ToolResult indicating step completion
        """
        return ToolResult(
            success=True,
            stdout="Step completed. Ready for next step.",
            message="Step completed successfully"
        )
    
    def execute_tool(self, tool_name: str, arguments: dict) -> ToolResult:
        """
        Execute a tool call and return structured result.
        
        Args:
            tool_name: Name of the tool
            arguments: Tool arguments
            
        Returns:
            ToolResult with structured output
        """
        if tool_name == "next_step":
            return self.execute_next_step()
        
        elif tool_name == "tree":
            return self.execute_tree()
        
        elif tool_name == "read":
            file_path = arguments.get('file_path')
            if not file_path:
                return ToolResult(
                    success=False,
                    stderr="read() requires file_path argument",
                    message="Missing file_path argument"
                )
            return self.execute_read(file_path)
        
        elif tool_name == "write":
            file_path = arguments.get('file_path')
            content = arguments.get('content', '')
            if not file_path:
                return ToolResult(
                    success=False,
                    stderr="write() requires file_path argument",
                    message="Missing file_path argument"
                )
            return self.execute_write(file_path, content)
        
        elif tool_name == "diff":
            file_path = arguments.get('file_path')
            diff_content = arguments.get('content') or arguments.get('diff_content', '')
            if not file_path:
                return ToolResult(
                    success=False,
                    stderr="diff() requires file_path argument",
                    message="Missing file_path argument"
                )
            if not diff_content:
                return ToolResult(
                    success=False,
                    stderr="diff() requires diff_content argument",
                    message="Missing diff_content argument"
                )
            return self.execute_diff(file_path, diff_content)
        
        elif tool_name == "delete":
            file_path = arguments.get('file_path')
            if not file_path:
                return ToolResult(
                    success=False,
                    stderr="delete() requires file_path argument",
                    message="Missing file_path argument"
                )
            return self.execute_delete(file_path)
        
        elif tool_name == "exec":
            command = arguments.get('command')
            background = arguments.get('background', False)
            if not command:
                return ToolResult(
                    success=False,
                    stderr="exec() requires command argument",
                    message="Missing command argument"
                )
            return self.execute_exec(command, background)
        
        else:
            return ToolResult(
                success=False,
                stderr=f"Unknown tool '{tool_name}'",
                message=f"Unknown tool: {tool_name}"
            )
