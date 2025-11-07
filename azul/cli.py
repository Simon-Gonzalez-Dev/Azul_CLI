"""CLI entry point for AZUL."""

import sys
import argparse
from pathlib import Path
from typing import Optional

from azul.config.manager import ConfigManager
from azul.session_manager import SessionManager
from azul.llama_client import LlamaClient
from azul.agent import AzulAgent
from azul.tui import run_tui


def find_model_path(config: ConfigManager, model_path_arg: Optional[str]) -> Path:
    """Find and validate model path.
    
    Args:
        config: Configuration manager
        model_path_arg: Optional model path from CLI argument
        
    Returns:
        Path to model file
        
    Raises:
        FileNotFoundError: If model not found
    """
    resolved_path = config.resolve_model_path(model_path_arg)
    
    if resolved_path is None:
        print("Error: Model file not found.")
        print("\nPlease provide a model file in one of these locations:")
        print("  1. azul/models/")
        print("  2. ~/.azul/models/")
        print("  3. ~/models/")
        print("  4. Current working directory")
        print("\nOr specify with --model-path PATH")
        sys.exit(1)
    
    # Cache the resolved path
    config.set_model_path(str(resolved_path))
    
    return resolved_path


def simple_mode(model_path: Path, config: ConfigManager):
    """Run in simple mode (direct LLM interaction).
    
    Args:
        model_path: Path to model file
        config: Configuration manager
    """
    print("AZUL Simple Mode")
    print("=" * 50)
    print("Type 'exit' or 'quit' to exit\n")
    
    # Initialize client
    client = LlamaClient(
        model_path=model_path,
        n_ctx=config.get_context_window_size(),
    )
    
    # Initialize session
    session = SessionManager(
        session_dir=config.get_session_dir(),
        max_history=config.get_max_history_messages(),
    )
    
    try:
        while True:
            user_input = input("azul> ").strip()
            
            if user_input.lower() in ['exit', 'quit', 'q']:
                break
            
            if not user_input:
                continue
            
            # Get history
            history = session.get_recent_history(n=10)
            
            # Generate response
            print("\nAZUL: ", end="", flush=True)
            response = ""
            for token in client.stream_chat(user_input, history):
                print(token, end="", flush=True)
                response += token
            print("\n")
            
            # Save to session
            session.add_message("user", user_input)
            session.add_message("assistant", response)
            session.save()
    
    except KeyboardInterrupt:
        print("\n\nExiting...")
    finally:
        session.save()
        client.unload_model()


def agentic_mode(model_path: Path, config: ConfigManager):
    """Run in agentic mode (TUI with LangChain agent).
    
    Args:
        model_path: Path to model file
        config: Configuration manager
    """
    print("Initializing AZUL Agentic Mode...")
    print(f"Model: {model_path}")
    
    # Initialize session
    session = SessionManager(
        session_dir=config.get_session_dir(),
        max_history=config.get_max_history_messages(),
    )
    
    # Get conversation history for agent
    conversation_history = session.get_recent_history(n=10)
    
    # Initialize agent
    try:
        agent = AzulAgent(
            model_path=model_path,
            n_ctx=config.get_context_window_size(),
            max_iterations=10,
            conversation_history=conversation_history,
        )
    except ImportError as e:
        print(f"Error: {e}")
        print("\nLangChain is required for agentic mode.")
        print("Install with: pip install langchain langchain-community")
        sys.exit(1)
    except Exception as e:
        print(f"Error initializing agent: {e}")
        sys.exit(1)
    
    # Run TUI
    try:
        run_tui(agent=agent, session=session)
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        session.save()


def main():
    """Main entry point for AZUL CLI."""
    parser = argparse.ArgumentParser(
        description="AZUL - Local Agentic AI Coding Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  azul                          # Run in agentic mode (default)
  azul --simple                 # Run in simple mode
  azul --model-path /path/to/model.gguf  # Specify model path
        """
    )
    
    parser.add_argument(
        "--model-path",
        type=str,
        help="Path to GGUF model file",
    )
    
    parser.add_argument(
        "--simple",
        action="store_true",
        help="Run in simple mode (no agent, direct LLM interaction)",
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="AZUL 0.1.0",
    )
    
    args = parser.parse_args()
    
    # Initialize configuration
    config = ConfigManager()
    
    # Find model path
    try:
        model_path = find_model_path(config, args.model_path)
    except FileNotFoundError:
        sys.exit(1)
    
    # Run in appropriate mode
    if args.simple:
        simple_mode(model_path, config)
    else:
        agentic_mode(model_path, config)


if __name__ == "__main__":
    main()

