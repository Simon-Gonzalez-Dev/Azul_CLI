# AZUL - Local Agentic AI Coding Assistant

AZUL is a fully agentic coding assistant that operates entirely on your local machine. It uses llama.cpp via llama-cpp-python to run the qwen2.5-coder-7b-instruct-q4_k_m.gguf model locally, orchestrated through LangChain for tool-calling, presented via a Textual TUI, and executing file operations transparently through nano via pexpect.

## Features

- **Fully Local**: Runs entirely on your machine, no API calls
- **Agentic Architecture**: Uses LangChain for Think-Plan-Act loops
- **Transparent File Operations**: All edits performed through nano for full auditability
- **Modern TUI**: Beautiful, responsive terminal interface built with Textual
- **Two Operation Modes**: Agentic mode (default) and Simple mode (backward compatible)

## Installation

### Prerequisites

- Python 3.12 or higher
- 4-8GB RAM (for 7B model)
- GPU optional but recommended (Metal on Mac, CUDA on NVIDIA)

### Install AZUL

```bash
# Clone the repository
git clone <repository-url>
cd Azul_CLI

# Install with pip
pip install -e .

# Or install with GPU support (Mac)
pip install -e ".[metal]"

# Or install with GPU support (NVIDIA)
pip install -e ".[cuda]"
```

### Download Model

Download the qwen2.5-coder-7b-instruct-q4_k_m.gguf model and place it in one of these locations:

1. `azul/models/` (package directory)
2. `~/.azul/models/` (user-specific)
3. `~/models/` (common location)
4. Current working directory

Or specify the path with `--model-path` when running AZUL.

## Usage

### Agentic Mode (Default)

```bash
azul
```

This launches the interactive TUI. Simply type your request:

```
User: Create a Python script that reads a CSV file and prints statistics
Agent: [THINKING] → [PLAN] → [read_file] → [write_file_nano] → [RESPOND]
```

### Simple Mode

```bash
azul --simple
```

For quick tasks without the full agentic interface.

### Command Line Options

```bash
azul --help              # Show help
azul --model-path PATH   # Specify model file path
azul --simple            # Use simple mode
```

## Architecture

See [local_ai_process.md](local_ai_process.md) for complete architecture documentation.

## Development

### Setup Development Environment

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests (when implemented)
pytest
```

### Project Structure

```
azul/
├── __init__.py
├── cli.py                 # Main entry point
├── llama_client.py        # LLM model wrapper
├── agent.py               # LangChain agent executor
├── tools.py               # Tool implementations
├── tui.py                 # Textual TUI application
├── session_manager.py     # Conversation history
└── config/
    ├── __init__.py
    └── manager.py         # Configuration management
```

## Troubleshooting

### Model Not Found

Ensure the model file is in one of the search paths or use `--model-path` to specify it directly.

### Out of Memory

- Use a smaller quantized model (q4_k_m or q3_k_m)
- Reduce context window size in configuration
- Close other applications

### Nano Not Working

Ensure `nano` is installed and available in your PATH:
```bash
which nano
```

### GPU Not Detected

- Mac: Install with `pip install -e ".[metal]"`
- NVIDIA: Install with `pip install -e ".[cuda]"` and ensure CUDA is properly installed

## License

MIT

## Contributing

Contributions welcome! Please read the architecture documentation and follow the existing code style.

