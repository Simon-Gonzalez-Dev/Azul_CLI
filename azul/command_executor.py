"""Command executor for running shell commands with real-time streaming."""

import subprocess
import threading
from typing import Callable, Optional
from pathlib import Path

from azul.formatter import get_formatter


class CommandExecutor:
    """Executes shell commands with real-time output streaming."""
    
    def __init__(self, project_root: Path):
        """Initialize command executor."""
        self.project_root = project_root
        self.formatter = get_formatter()
    
    def run_command_async(
        self, 
        command: str, 
        on_complete_callback: Optional[Callable[[int], None]] = None
    ) -> None:
        """
        Runs a command in a separate thread and streams its output in real-time.
        Calls callback with exit code when done.
        
        Args:
            command: Shell command to execute
            on_complete_callback: Callback function called with exit code when command completes
        """
        def target():
            try:
                # Start the subprocess in the project directory
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,  # Merge stderr into stdout
                    text=True,
                    bufsize=1,  # Line buffered
                    cwd=str(self.project_root),
                    universal_newlines=True
                )
                
                # Real-time streaming of output
                if process.stdout:
                    for line in iter(process.stdout.readline, ''):
                        if line:  # Only print non-empty lines
                            self.formatter.console.print(
                                f"[bold magenta][exec]:[/bold magenta] {line.rstrip()}"
                            )
                
                # Wait for process to finish
                process.wait()
                
                # Call callback with exit code
                if on_complete_callback:
                    on_complete_callback(process.returncode)
                    
            except Exception as e:
                self.formatter.print_error(f"Error executing command: {e}")
                if on_complete_callback:
                    on_complete_callback(-1)
        
        # Start the command in a new thread to avoid blocking
        thread = threading.Thread(target=target, daemon=True)
        thread.start()
    
    def run_command_sync(self, command: str) -> tuple[int, str]:
        """
        Runs a command synchronously and captures all output.
        
        Args:
            command: Shell command to execute
            
        Returns:
            Tuple of (exit_code, output_text)
        """
        try:
            result = subprocess.run(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(self.project_root),
                timeout=300  # 5 minute timeout for safety
            )
            
            output = result.stdout if result.stdout else ""
            return result.returncode, output
            
        except subprocess.TimeoutExpired:
            return -1, "Error: Command timed out after 5 minutes"
        except Exception as e:
            return -1, f"Error executing command: {e}"

