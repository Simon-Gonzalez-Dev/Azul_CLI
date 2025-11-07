"""Rich-based TUI frontend for AZUL with streaming support."""

import threading
import time
from typing import Optional
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text


class AzulTUI:
    """Minimalist TUI using Rich library with Live display and streaming."""
    
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
        self.streaming_tokens = ""
        self.is_streaming = False
        self.last_tool_call = None
        self.last_observation = None
        self.tool_call_count = 0
        self.observation_count = 0
        self.conversation_log = []  # Store conversation for display
        self.live: Optional[Live] = None
        self.generation_start_time = None
    
    def display_banner(self) -> None:
        """Display the AZUL banner."""
        self.console.print(self.BANNER, style="cyan")
        self.console.print()
    
    def start_live_display(self) -> None:
        """Start the Live display context."""
        self.live = Live(self._generate_panel(), console=self.console, refresh_per_second=10, screen=False)
        self.live.start()
    
    def stop_live_display(self) -> None:
        """Stop the Live display."""
        if self.live:
            self.live.stop()
            self.live = None
    
    def on_thinking_stream(self, token: str) -> None:
        """Handle streaming thinking tokens."""
        with self.agent_box_lock:
            self.streaming_tokens += token
            self.is_streaming = True
            if self.live:
                self.live.update(self._generate_panel())
    
    def on_thinking(self, message: str) -> None:
        """Handle thinking callback."""
        with self.agent_box_lock:
            self.current_thinking = message
            self.streaming_tokens = ""  # Clear streaming when new thinking starts
            self.is_streaming = False
            if self.live:
                self.live.update(self._generate_panel())
    
    def on_tool_call(self, tool_call: str) -> None:
        """Handle tool call callback."""
        with self.agent_box_lock:
            if tool_call == self.last_tool_call:
                self.tool_call_count += 1
            else:
                self.last_tool_call = tool_call
                self.tool_call_count = 1
            self.current_action = tool_call
            self.is_streaming = False
            if self.live:
                self.live.update(self._generate_panel())
    
    def on_observation(self, observation: str) -> None:
        """Handle observation callback."""
        with self.agent_box_lock:
            if observation == self.last_observation:
                self.observation_count += 1
            else:
                self.last_observation = observation
                self.observation_count = 1
            self.current_result = observation
            self.is_streaming = False
            if self.live:
                self.live.update(self._generate_panel())
    
    def start_generation(self) -> None:
        """Mark start of generation."""
        with self.agent_box_lock:
            self.generation_start_time = time.time()
            self.is_streaming = True
            self.streaming_tokens = ""
    
    def _generate_panel(self) -> Panel:
        """Generate the panel to be displayed."""
        lines = []
        
        # Add thinking/streaming content
        if self.is_streaming and self.streaming_tokens:
            # Show streaming tokens with a spinner
            thinking_line = f"    THINKING: {self.streaming_tokens}"
            lines.append(thinking_line)
            # Add timer indicator
            elapsed = time.time() - self.generation_start_time if self.generation_start_time else 0
            lines.append(f"    [dim]Generating... ({elapsed:.1f}s)[/dim]")
        elif self.current_thinking:
            lines.append(f"    THINKING: {self.current_thinking}")
        
        # Add plan if exists
        if self.current_plan:
            lines.append("    PLAN:")
            for i, step in enumerate(self.current_plan, 1):
                lines.append(f"    {i}. {step}")
        
        # Add action
        if self.current_action:
            action_text = f" ⚡ ACTION: {self.current_action}"
            if self.tool_call_count > 1:
                action_text += f" [dim](repeated {self.tool_call_count}x)[/dim]"
            lines.append(action_text)
        
        # Add result
        if self.current_result:
            result_text = f"   RESULT: {self.current_result[:200]}"  # Truncate long results
            if len(self.current_result) > 200:
                result_text += "..."
            if self.observation_count > 1:
                result_text += f" [dim](repeated {self.observation_count}x)[/dim]"
            lines.append(result_text)
        
        # Only show box if there's content
        if not lines:
            return Panel("", title="[bold cyan]Agent is working...[/bold cyan]", border_style="cyan")
        
        # Create box with exact border style from aesthetic
        content = "\n".join(lines)
        return Panel(
            content,
            title="[bold cyan]Agent is working...[/bold cyan]",
            border_style="cyan",
            padding=(1, 2)
        )
    
    def display_user_input(self, user_input: str) -> None:
        """Display user input."""
        formatted = f"> User: {user_input}"
        self.conversation_log.append(formatted)
        self.console.print(formatted, style="yellow")
        self.console.print()
    
    def display_agent_response(self, response: str) -> None:
        """Display agent response."""
        formatted = f"  AZUL: {response}"
        self.conversation_log.append(formatted)
        self.console.print(formatted, style="green")
        self.console.print()
    
    def display_error(self, error: str) -> None:
        """Display error message."""
        formatted = f"AZUL: Error: {error}"
        self.conversation_log.append(formatted)
        self.console.print(formatted, style="red")
        self.console.print()
    
    def clear_agent_box(self) -> None:
        """Clear the agent working box."""
        with self.agent_box_lock:
            self.current_thinking = ""
            self.current_plan = []
            self.current_action = ""
            self.current_result = ""
            self.streaming_tokens = ""
            self.is_streaming = False
            self.last_tool_call = None
            self.last_observation = None
            self.tool_call_count = 0
            self.observation_count = 0
            self.generation_start_time = None
            if self.live:
                self.live.update(self._generate_panel())
    
    def request_permission(self, operation: str, details: str) -> bool:
        """Request permission from user for destructive operations."""
        # Stop live display temporarily for input
        if self.live:
            self.live.stop()
        
        try:
            self.console.print(f"\n[yellow]⚠️  Permission Request[/yellow]")
            self.console.print(f"[yellow]Operation:[/yellow] {operation}")
            self.console.print(f"[yellow]Details:[/yellow] {details}")
            
            while True:
                response = input("\nAllow this operation? (y/n): ").strip().lower()
                if response in ['y', 'yes']:
                    return True
                elif response in ['n', 'no']:
                    return False
                else:
                    self.console.print("[red]Please enter 'y' for yes or 'n' for no[/red]")
        finally:
            if self.live:
                self.live.start()
    
    def get_user_input(self, prompt: str = "> User: ") -> str:
        """Get user input."""
        # Stop live display temporarily for input
        if self.live:
            self.live.stop()
        try:
            return input(prompt)
        finally:
            if self.live:
                self.live.start()
