"""Textual TUI application for AZUL."""

import asyncio
from typing import Optional
from pathlib import Path

try:
    from textual.app import App, ComposeResult
    from textual.widgets import RichLog, Input, Static
    from textual.containers import Container, Horizontal, Vertical
    from textual.binding import Binding
    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    print("Error: Textual is not installed. Install with: pip install textual")

from azul.agent import AzulAgent
from azul.session_manager import SessionManager


class AzulTUI(App):
    """Main TUI application for AZUL."""
    
    CSS = """
    #history {
        height: 30%;
        border: solid $primary;
    }
    
    #workspace {
        height: 50%;
        border: solid $primary;
    }
    
    #status_bar {
        height: 20%;
        border: solid $primary;
    }
    
    #agent_log {
        height: 100%;
    }
    
    #nano_display {
        height: 100%;
        display: none;
    }
    
    #nano_display:visible {
        display: block;
    }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit"),
    ]
    
    def __init__(
        self,
        agent: Optional[AzulAgent] = None,
        session: Optional[SessionManager] = None,
    ):
        """Initialize TUI.
        
        Args:
            agent: Pre-initialized agent (optional)
            session: Session manager for history (optional)
        """
        super().__init__()
        self.agent = agent
        self.session = session
        self.is_running = False
        self.input_queue = []
    
    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        with Vertical():
            # Conversation history panel
            with Container(id="history"):
                yield RichLog(id="history_log", markup=True, wrap=True)
            
            # Live workspace panel
            with Container(id="workspace"):
                yield RichLog(id="agent_log", markup=True, wrap=True)
                yield RichLog(id="nano_display", markup=True, wrap=True, classes="hidden")
            
            # Status and input panel
            with Container(id="status_bar"):
                yield Static("Status: Ready", id="status")
                yield Input(placeholder="Enter your instruction...", id="user_input")
    
    def on_mount(self):
        """Called when app is mounted."""
        self.query_one("#user_input").focus()
        
        # Load conversation history if available
        if self.session:
            history = self.session.get_history()
            history_log = self.query_one("#history_log")
            for msg in history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    history_log.write(f"[bold blue]User:[/bold blue] {content}")
                else:
                    history_log.write(f"[bold green]AZUL:[/bold green] {content}")
    
    def on_input_submitted(self, event: Input.Submitted):
        """Handle user input submission."""
        user_input = event.value.strip()
        if not user_input:
            return
        
        if self.is_running:
            # Queue input if agent is running
            self.input_queue.append(user_input)
            self.update_status("Input queued. Agent is running...")
            self.query_one("#user_input", Input).value = ""
            return
        
        # Clear input
        self.query_one("#user_input", Input).value = ""
        
        # Add to history log
        history_log = self.query_one("#history_log")
        history_log.write(f"[bold blue]User:[/bold blue] {user_input}")
        
        # Add to session if available
        if self.session:
            self.session.add_message("user", user_input)
        
        # Execute agent
        if self.agent:
            self.run_agent(user_input)
        else:
            self.update_status("Error: Agent not initialized")
            self.query_one("#agent_log").write("[red]Error: Agent not initialized[/red]")
    
    def run_agent(self, user_input: str):
        """Run agent with user input (non-blocking)."""
        self.is_running = True
        self.update_status("Running Agent...")
        
        # Clear workspace for new task
        agent_log = self.query_one("#agent_log")
        agent_log.clear()
        
        # Hide nano display
        nano_display = self.query_one("#nano_display")
        nano_display.add_class("hidden")
        
        # Set up callbacks
        callbacks = {
            'thinking': self.on_thinking,
            'tool_call': self.on_tool_call,
            'observation': self.on_observation,
            'nano_output': self.on_nano_output,
        }
        
        # Update agent callbacks
        self.agent.callbacks = callbacks
        
        # Run agent in background
        self.set_timer(0.1, lambda: asyncio.create_task(self._execute_agent(user_input)))
    
    async def _execute_agent(self, user_input: str):
        """Execute agent asynchronously."""
        try:
            # Run agent in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self.agent.execute, user_input)
            
            # Display result
            agent_log = self.query_one("#agent_log")
            agent_log.write(f"[bold green]✓ Task completed[/bold green]")
            agent_log.write(f"[bold]Response:[/bold] {result}")
            
            # Add to history
            history_log = self.query_one("#history_log")
            history_log.write(f"[bold green]AZUL:[/bold green] {result}")
            
            # Save to session
            if self.session:
                self.session.add_message("assistant", result)
                self.session.save()
            
            # Process queued input
            if self.input_queue:
                next_input = self.input_queue.pop(0)
                self.run_agent(next_input)
            else:
                self.is_running = False
                self.update_status("Ready")
                self.query_one("#user_input").focus()
        
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.query_one("#agent_log").write(f"[red]{error_msg}[/red]")
            self.update_status("Error occurred")
            self.is_running = False
            self.query_one("#user_input").focus()
    
    def on_thinking(self, text: str):
        """Handle thinking callback."""
        agent_log = self.query_one("#agent_log")
        agent_log.write(f"[yellow]🤔 THINKING:[/yellow] {text}")
        agent_log.action_scroll_end()
    
    def on_tool_call(self, tool_call: str):
        """Handle tool call callback."""
        agent_log = self.query_one("#agent_log")
        agent_log.write(f"[cyan]⚡ [CALLING TOOL][/cyan] {tool_call}")
        agent_log.action_scroll_end()
        
        if "write_file_nano" in tool_call:
            self.update_status("Awaiting Nano Input...")
    
    def on_observation(self, observation: str):
        """Handle observation callback."""
        agent_log = self.query_one("#agent_log")
        agent_log.write(f"[dim][OBSERVATION][/dim] {observation[:200]}...")  # Truncate long observations
        agent_log.action_scroll_end()
    
    def on_nano_output(self, output: str):
        """Handle nano session output."""
        nano_display = self.query_one("#nano_display")
        nano_display.remove_class("hidden")
        nano_display.write(f"[dim][NANO SESSION][/dim]\n{output}")
        nano_display.action_scroll_end()
    
    def update_status(self, status: str):
        """Update status bar."""
        status_widget = self.query_one("#status", Static)
        status_widget.update(f"Status: {status}")
    
    def action_quit(self):
        """Quit the application."""
        if self.session:
            self.session.save()
        self.exit()


def run_tui(agent: AzulAgent, session: SessionManager):
    """Run the TUI application.
    
    Args:
        agent: Initialized agent
        session: Session manager
    """
    if not TEXTUAL_AVAILABLE:
        print("Error: Textual is required for TUI mode. Install with: pip install textual")
        return
    
    app = AzulTUI(agent=agent, session=session)
    app.run()

