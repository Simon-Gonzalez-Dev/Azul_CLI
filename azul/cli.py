"""Main CLI entry point for AZUL."""

import os
import signal
import subprocess
import sys
from pathlib import Path

from rich.console import Console

from azul.agent import AzulAgent
from azul.config.manager import Config
from azul.session_manager import SessionManager
from azul.tui import AzulTUI


# Global flag for graceful shutdown
shutdown_requested = False


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    global shutdown_requested
    shutdown_requested = True
    print("\n\nShutting down gracefully...", file=sys.stderr)


def handle_manual_command(command: str, tui: AzulTUI, session_manager: SessionManager, agent: AzulAgent) -> bool:
    """
    Handle manual commands starting with @.
    Returns True if command was handled, False otherwise.
    """
    if not command.startswith('@'):
        return False
    
    parts = command[1:].strip().split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    
    if cmd == "ls":
        # Handle @ls command
        try:
            if args:
                # List specific directory
                result = subprocess.run(['ls', '-la', args], capture_output=True, text=True, timeout=5)
            else:
                # List current directory
                result = subprocess.run(['ls', '-la'], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                tui.console.print(result.stdout)
            else:
                tui.console.print(f"[red]Error:[/red] {result.stderr}", style="red")
        except subprocess.TimeoutExpired:
            tui.console.print("[red]Error: Command timed out[/red]")
        except Exception as e:
            tui.console.print(f"[red]Error executing ls:[/red] {str(e)}")
        return True
    
    elif cmd == "cd":
        # Handle @cd command
        try:
            if args:
                target_dir = args.strip()
            else:
                # Default to home directory
                target_dir = os.path.expanduser("~")
            
            os.chdir(target_dir)
            tui.console.print(f"[green]Changed directory to:[/green] {os.getcwd()}")
        except FileNotFoundError:
            tui.console.print(f"[red]Error: Directory not found:[/red] {args}")
        except PermissionError:
            tui.console.print(f"[red]Error: Permission denied:[/red] {args}")
        except Exception as e:
            tui.console.print(f"[red]Error changing directory:[/red] {str(e)}")
        return True
    
    elif cmd == "reset":
        # Handle @reset command
        try:
            # Clear session manager
            session_manager.clear()
            # Clear agent conversation history
            agent.conversation_history = []
            tui.console.print("[yellow]Memory reset: Conversation history cleared.[/yellow]")
            tui.clear_agent_box()
        except Exception as e:
            tui.console.print(f"[red]Error resetting memory:[/red] {str(e)}")
        return True
    
    # Unknown @ command
    tui.console.print(f"[yellow]Unknown command:[/yellow] @{cmd}")
    tui.console.print("[dim]Available commands: @ls, @cd [path], @reset[/dim]")
    return True


def main():
    """Main entry point for AZUL CLI."""
    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Initialize configuration
        config = Config()
        
        # Initialize TUI
        tui = AzulTUI()
        tui.display_banner()
        tui.start_live_display()
        
        # Initialize session manager
        session_manager = SessionManager(config.get_session_path())
        
        # Initialize agent with callbacks
        agent = AzulAgent(
            model_path=config.model_path,
            n_ctx=config.n_ctx,
            n_gpu_layers=config.n_gpu_layers,
            max_iterations=config.max_iterations,
            conversation_history=session_manager.get_history(),
            callbacks={
                "thinking": tui.on_thinking,
                "thinking_stream": tui.on_thinking_stream,
                "tool_call": tui.on_tool_call,
                "observation": tui.on_observation,
                "start_generation": tui.start_generation,
                "permission_request": tui.request_permission,
                "stats": tui.on_stats,
            }
        )
        
        # Interactive loop
        while True:
            try:
                # Check for shutdown
                if shutdown_requested:
                    break
                
                # Get user input
                user_input = tui.get_user_input()
                
                # Check for exit commands
                if user_input.lower() in ["exit", "quit", "q"]:
                    tui.console.print("Goodbye!", style="cyan")
                    break
                
                if not user_input.strip():
                    continue
                
                # Handle manual commands (take priority, don't send to model)
                if handle_manual_command(user_input, tui, session_manager, agent):
                    continue  # Skip sending to agent
                
                # Display user input
                tui.display_user_input(user_input)
                
                # Add to session
                session_manager.add_message("user", user_input)
                
                # Execute agent
                try:
                    response = agent.execute(user_input)
                except KeyboardInterrupt:
                    tui.console.print("\n\n[yellow]Interrupted by user. Stopping agent...[/yellow]")
                    tui.clear_agent_box()
                    continue
                
                # Handle memory reset
                if "RESET_MEMORY:" in response or "Memory reset successfully" in response:
                    session_manager.clear()
                    tui.console.print("[yellow]Memory reset: Conversation history cleared.[/yellow]")
                    tui.clear_agent_box()
                    continue
                
                # Clear agent box
                tui.clear_agent_box()
                
                # Display response
                if response:
                    tui.display_agent_response(response)
                    session_manager.add_message("assistant", response)
                else:
                    tui.display_error("No response from agent")
            
            except KeyboardInterrupt:
                tui.console.print("\n\n[yellow]Interrupted. Goodbye![/yellow]")
                break
            except Exception as e:
                tui.display_error(str(e))
    
    except ValueError as e:
        print(f"Configuration Error: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nInterrupted during startup. Goodbye!", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        # Ensure terminal is cleaned up properly
        if tui:
            tui.stop_live_display()
        # Ensure cursor is visible
        try:
            console = Console()
            console.show_cursor(True)
        except Exception:
            pass


if __name__ == "__main__":
    main()
