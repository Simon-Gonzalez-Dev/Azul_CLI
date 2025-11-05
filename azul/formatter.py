"""Rich output formatting for AZUL CLI."""

from typing import Optional, Iterator
from rich.console import Console
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.panel import Panel
import re

from azul.config.manager import get_config_manager


class Formatter:
    """Handles formatting and display of AI responses."""
    
    def __init__(self):
        """Initialize formatter."""
        self.console = Console()
        self.config = get_config_manager()
    
    def print_markdown(self, content: str) -> None:
        """Print markdown content with rich formatting."""
        markdown = Markdown(content)
        self.console.print(markdown)
    
    def print_code_block(self, code: str, language: str = "text") -> None:
        """Print a code block with syntax highlighting."""
        syntax = Syntax(code, language, theme="monokai", line_numbers=False)
        self.console.print(syntax)
    
    def print_diff(self, diff_content: str) -> None:
        """Print a unified diff with color coding."""
        lines = diff_content.split('\n')
        for line in lines:
            if line.startswith('+++') or line.startswith('---'):
                self.console.print(f"[bold blue]{line}[/bold blue]")
            elif line.startswith('@@'):
                self.console.print(f"[bold blue]{line}[/bold blue]")
            elif line.startswith('+'):
                self.console.print(f"[bold blue]{line}[/bold blue]")
            elif line.startswith('-'):
                self.console.print(f"[bold blue]{line}[/bold blue]")
            else:
                self.console.print(line)
    
    def extract_code_blocks(self, content: str) -> list:
        """Extract code blocks from markdown content."""
        # Pattern to match markdown code blocks
        pattern = r'```(\w+)?\n(.*?)```'
        matches = re.findall(pattern, content, re.DOTALL)
        return matches
    
    def stream_response(self, generator: Iterator[str]) -> str:
        """
        Stream response token by token with real-time display.
        
        Args:
            generator: Iterator that yields tokens
            
        Returns:
            Complete response text
        """
        full_response = ""
        buffer = ""
        
        try:
            for token in generator:
                full_response += token
                buffer += token
                
                # Print immediately for better UX (token-by-token)
                # Use standard print for token streaming, Rich for formatting
                import sys
                sys.stdout.write(token)
                sys.stdout.flush()
        except StopIteration:
            pass
        
        # New line after response
        print()  # Use standard print for newline
        return full_response
    
    def show_status(self, message: str):
        """Show a status spinner context manager."""
        return self.console.status(f"[bold green]{message}[/bold green]")
    
    def print_error(self, message: str) -> None:
        """Print an error message."""
        self.console.print(f"[bold red]Error:[/bold red] {message}")
    
    def print_success(self, message: str) -> None:
        """Print a success message."""
        self.console.print(f"[bold green]✓[/bold green] {message}")
    
    def print_warning(self, message: str) -> None:
        """Print a warning message."""
        self.console.print(f"[bold yellow]Warning:[/bold yellow] {message}")
    
    def print_info(self, message: str) -> None:
        """Print an info message."""
        self.console.print(f"[bold blue]Info:[/bold blue] {message}")
    
    def format_file_preview(self, file_path: str, content: str, max_lines: int = 50) -> str:
        """Format a file preview for display."""
        lines = content.split('\n')
        if len(lines) > max_lines:
            preview = '\n'.join(lines[:max_lines])
            preview += f"\n... ({len(lines) - max_lines} more lines)"
        else:
            preview = content
        
        panel = Panel(
            preview,
            title=f"[bold]{file_path}[/bold]",
            border_style="blue"
        )
        return panel


# Global formatter instance
_formatter: Optional[Formatter] = None


def get_formatter() -> Formatter:
    """Get the global formatter instance."""
    global _formatter
    if _formatter is None:
        _formatter = Formatter()
    return _formatter

