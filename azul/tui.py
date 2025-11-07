"""Rich-based TUI frontend for AZUL with streaming support."""

import threading
import time
from typing import Optional, Dict
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
        self.stats: Optional[Dict[str, float]] = None
    
    def display_banner(self) -> None:
        """Display the AZUL banner."""
        self.console.print(self.BANNER, style="cyan")
        self.console.print()
    
    def start_live_display(self) -> None:
        """Start the Live display context."""
        self.live = Live(self._generate_panel(), console=self.console, refresh_per_second=10, screen=False)
        self.live.start()
    
    def stop_live_display(self) -> None:
        """Stop the Live display and restore terminal."""
        if self.live:
            try:
                self.live.stop()
            except Exception:
                pass
            self.live = None
        # Ensure cursor is visible
        try:
            self.console.show_cursor(True)
        except Exception:
            pass
    
    def on_thinking_stream(self, token: str) -> None:
        """Handle streaming thinking tokens - append incrementally."""
        with self.agent_box_lock:
            # Append token, don't replace
            self.streaming_tokens += token
            self.is_streaming = True
            # Only update if we have a live display
            if self.live:
                try:
                    self.live.update(self._generate_panel())
                except Exception:
                    pass  # Don't crash on update errors
    
    def on_thinking(self, message: str) -> None:
        """Handle thinking callback."""
        with self.agent_box_lock:
            self.current_thinking = message
            # Don't clear streaming tokens here - let them accumulate
            self.is_streaming = False
            if self.live:
                try:
                    self.live.update(self._generate_panel())
                except Exception:
                    pass
    
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
                try:
                    self.live.update(self._generate_panel())
                except Exception:
                    pass
    
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
                try:
                    self.live.update(self._generate_panel())
                except Exception:
                    pass
    
    def on_stats(self, stats: Dict[str, float]) -> None:
        """Handle stats callback."""
        self.stats = stats
    
    def start_generation(self) -> None:
        """Mark start of generation."""
        with self.agent_box_lock:
            self.generation_start_time = time.time()
            self.is_streaming = True
            self.streaming_tokens = ""
    
    def _generate_panel(self) -> Panel:
        """Generate the panel to be displayed."""
        lines = []
        
        # Add thinking/streaming content - show accumulated tokens
        if self.is_streaming and self.streaming_tokens:
            # Truncate if too long, show last portion
            display_tokens = self.streaming_tokens[-200:] if len(self.streaming_tokens) > 200 else self.streaming_tokens
            thinking_line = f"    THINKING: {display_tokens}"
            lines.append(thinking_line)
            # Add timer and token count
            elapsed = time.time() - self.generation_start_time if self.generation_start_time else 0
            token_count = len(self.streaming_tokens.split())  # Rough estimate
            lines.append(f"    [dim]Generating... ({elapsed:.1f}s, ~{token_count} tokens)[/dim]")
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
            result_text = f"   RESULT: {self.current_result[:200]}"
            if len(self.current_result) > 200:
                result_text += "..."
            if self.observation_count > 1:
                result_text += f" [dim](repeated {self.observation_count}x)[/dim]"
            lines.append(result_text)
        
        # Only show box if there's content
        if not lines:
            return Panel("", title="[bold cyan]Agent is working...[/bold cyan]", border_style="cyan")
        
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
        """Display agent response with stats."""
        formatted = f"  AZUL: {response}"
        self.conversation_log.append(formatted)
        self.console.print(formatted, style="green")
        
        # Display stats if available
        if self.stats:
            stats_text = (
                f"[dim]Stats: Input: {self.stats.get('input_tokens', 0)} tokens | "
                f"Output: {self.stats.get('output_tokens', 0)} tokens | "
                f"Speed: {self.stats.get('tokens_per_second', 0):.1f} tok/s | "
                f"Time: {self.stats.get('generation_time', 0):.2f}s[/dim]"
            )
            self.console.print(stats_text)
            self.stats = None
        
        self.console.print()
    
    def display_error(self, error: str) -> None:
        """Display error message."""
        formatted = f"AZUL: Error: {error}"
        self.conversation_log.append(formatted)
        self.console.print(formatted, style="red")
        self.console.print()
    
    def clear_agent_box(self) -> None:
        """Clear the agent working box state."""
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
                try:
                    self.live.update(self._generate_panel())
                except Exception:
                    pass
    
    def request_permission(self, operation: str, details: str) -> bool:
        """Request permission from user for destructive operations."""
        # Stop live display temporarily for input
        was_running = False
        if self.live:
            try:
                self.live.stop()
                was_running = True
            except Exception:
                pass
        
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
            if was_running and self.live:
                try:
                    self.live.start()
                except Exception:
                    pass
    
    def get_user_input(self, prompt: str = "> User: ") -> str:
        """Get user input."""
        # Stop live display temporarily for input
        was_running = False
        if self.live:
            try:
                self.live.stop()
                was_running = True
            except Exception:
                pass
        
        try:
            return input(prompt)
        finally:
            if was_running and self.live:
                try:
                    self.live.start()
                except Exception:
                    pass
