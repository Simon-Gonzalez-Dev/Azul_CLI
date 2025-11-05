"""Main CLI entry point for AZUL."""

import click
from pathlib import Path

from azul.repl import start_repl
from azul.env_checker import validate_environment


@click.command()
@click.argument('file', required=False, type=click.Path(exists=True))
@click.option('--model', '-m', help='Ollama model to use')
@click.option('--project-root', '-p', type=click.Path(), help='Project root directory')
def main(file, model, project_root):
    """AZUL CLI - A Claude-like coding assistant with local LLMs."""
    
    # Validate environment silently - don't show warnings if Ollama is connected
    chat_available, rag_available = validate_environment()
    
    # Determine project root
    if project_root:
        project_root = Path(project_root).resolve()
    elif file:
        project_root = Path(file).parent.resolve()
    else:
        project_root = Path.cwd()
    
    # Initialize sandbox with project root first
    from azul.sandbox import get_sandbox
    get_sandbox(project_root)
    
    # Set model if provided
    if model:
        from azul.ollama_client import get_ollama_client
        ollama = get_ollama_client()
        ollama.set_model(model)
    
    # Disable RAG if embedding model not available
    if not rag_available:
        from azul.config.manager import get_config_manager
        config = get_config_manager()
        config.set("rag", {**config.get("rag", {}), "enabled_by_default": False})
    
    # If file provided, add it to context and start conversation
    if file:
        from azul.file_handler import get_file_handler
        from azul.formatter import get_formatter
        
        file_handler = get_file_handler()
        formatter = get_formatter()
        
        content, error = file_handler.read_file(file)
        if error:
            formatter.print_error(error)
            return
        
        # Start REPL with file context
        formatter.print_info(f"Loaded file: {file}")
        formatter.print_code_block(content, "text")
        formatter.console.print("\n")
    
    # Start interactive REPL
    start_repl(project_root)


if __name__ == '__main__':
    main()

