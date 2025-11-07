"""Rich-based TUI frontend for AZUL."""

import threading
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.text import Text


class AzulTUI:
    """Minimalist TUI using Rich library matching AZUL_ESTETHIC.md."""
    
    BANNER = """
    █████╗   ███████╗   ██╗   ██╗   ██╗       
   ██╔══██╗   ╚════██╗  ██║   ██║   ██║      
  ███████║    █████╔╝   ██║   ██║   ██║       
 ██╔══██║    ██╔═══╝    ██║   ██║   ██║       
██║  ██║     ███████╗   ╚██████╔╝   ███████╗  
╚═╝  ╚═╝     ╚══════╝    ╚═════╝    ╚══════╝ 
"""
    
    def __init__(self):
        self.console = Console()
        self.agent_box_lock = threading.Lock()
        self.current_thinking = ""
        self.current_plan = []
        self.current_action = ""
        self.current_result = ""
    
    def display_banner(self) -> None:
        """Display the AZUL banner."""
        self.console.print(self.BANNER, style="cyan")
        self.console.print()
    
    def on_thinking(self, message: str) -> None:
        """Handle thinking callback."""
        with self.agent_box_lock:
            self.current_thinking = message
            self._update_agent_box()
    
    def on_tool_call(self, tool_call: str) -> None:
        """Handle tool call callback."""
        with self.agent_box_lock:
            self.current_action = tool_call
            self._update_agent_box()
    
    def on_observation(self, observation: str) -> None:
        """Handle observation callback."""
        with self.agent_box_lock:
            self.current_result = observation
            self._update_agent_box()
    
    def _update_agent_box(self) -> None:
        """Update the agent working box display."""
        # Build box content
        lines = []
        
        if self.current_thinking:
            lines.append(f"    THINKING: {self.current_thinking}")
        
        if self.current_plan:
            lines.append("    PLAN:")
            for i, step in enumerate(self.current_plan, 1):
                lines.append(f"    {i}. {step}")
        
        if self.current_action:
            lines.append(f" ⚡ ACTION: {self.current_action}")
        
        if self.current_result:
            lines.append(f"   RESULT: {self.current_result}")
        
        # Only show box if there's content
        if not lines:
            return
        
        # Create box with exact border style from aesthetic
        box_lines = []
        box_lines.append("┌─ Agent is working... " + "─" * 40 + "┐")
        for line in lines:
            # Pad line to match box width (approximately 65 chars)
            padded_line = line + " " * max(0, 60 - len(line))
            box_lines.append("│ " + padded_line + " │")
        box_lines.append("└" + "─" * 62 + "┘")
        
        # Print agent box
        self.console.print("\n".join(box_lines), style="cyan")
        self.console.print()
    
    def display_user_input(self, user_input: str) -> None:
        """Display user input."""
        self.console.print(f"> User: {user_input}", style="yellow")
        self.console.print()
    
    def display_agent_response(self, response: str) -> None:
        """Display agent response."""
        self.console.print(f"  AZUL: {response}", style="green")
        self.console.print()
    
    def display_error(self, error: str) -> None:
        """Display error message."""
        self.console.print(f"AZUL: Error: {error}", style="red")
        self.console.print()
    
    def clear_agent_box(self) -> None:
        """Clear the agent working box."""
        with self.agent_box_lock:
            self.current_thinking = ""
            self.current_plan = []
            self.current_action = ""
            self.current_result = ""
    
    def get_user_input(self, prompt: str = "> User: ") -> str:
        """Get user input."""
        return input(prompt)

