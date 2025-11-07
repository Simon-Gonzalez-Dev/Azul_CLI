"""Main CLI entry point for AZUL."""

import sys
from pathlib import Path

from azul.agent import AzulAgent
from azul.config.manager import Config
from azul.session_manager import SessionManager
from azul.tui import AzulTUI


def main():
    """Main entry point for AZUL CLI."""
    try:
        # Initialize configuration
        config = Config()
        
        # Initialize TUI
        tui = AzulTUI()
        tui.display_banner()
        
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
                "tool_call": tui.on_tool_call,
                "observation": tui.on_observation,
            }
        )
        
        # Interactive loop
        while True:
            try:
                # Get user input
                user_input = tui.get_user_input()
                
                # Check for exit commands
                if user_input.lower() in ["exit", "quit", "q"]:
                    tui.console.print("Goodbye!", style="cyan")
                    break
                
                if not user_input.strip():
                    continue
                
                # Display user input
                tui.display_user_input(user_input)
                
                # Add to session
                session_manager.add_message("user", user_input)
                
                # Execute agent
                response = agent.execute(user_input)
                
                # Clear agent box
                tui.clear_agent_box()
                
                # Display response
                if response:
                    tui.display_agent_response(response)
                    session_manager.add_message("assistant", response)
                else:
                    tui.display_error("No response from agent")
            
            except KeyboardInterrupt:
                tui.console.print("\n\nInterrupted. Goodbye!", style="yellow")
                break
            except Exception as e:
                tui.display_error(str(e))
    
    except ValueError as e:
        print(f"Configuration Error: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

