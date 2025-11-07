# AZUL - Agentic AI Coding Assistant

AZUL is an autonomous AI coding assistant that runs entirely on your local hardware using llama-cpp-python. It provides real-time visibility into agent reasoning, tool execution, and responses through a minimalist TUI interface.

## Features

- **Local-First**: Runs entirely on local hardware using llama-cpp-python
- **Agentic Loop**: Think → Plan → Act → Observe → Respond
- **Real-time Feedback**: All agent steps are exposed via callbacks
- **Tool Transparency**: Every tool execution is logged and visible
- **Minimalist TUI**: Clean, agentic interface matching Claude Code aesthetic

## Requirements

- Python 3.8 or higher
- A GGUF model file (compatible with llama-cpp-python)
- CUDA/GPU support (optional, but recommended for performance)

## Installation

1. **Clone or navigate to the AZUL directory:**
   ```bash
   cd Azul_CLI
   ```

2. **Create a virtual environment:**
   ```bash
   python3 -m venv azul_env
   ```

3. **Activate the virtual environment:**
   ```bash
   # On macOS/Linux:
   source azul_env/bin/activate
   
   # On Windows:
   azul_env\Scripts\activate
   ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Install AZUL in development mode:**
   ```bash
   pip install -e .
   ```

6. **Set the model path environment variable:**
   ```bash
   export AZUL_MODEL_PATH=/path/to/your/model.gguf
   ```

   Or add it to your shell profile (`.bashrc`, `.zshrc`, etc.):
   ```bash
   echo 'export AZUL_MODEL_PATH=/path/to/your/model.gguf' >> ~/.zshrc
   source ~/.zshrc
   ```

## Usage

After activating the virtual environment and setting `AZUL_MODEL_PATH`, simply run:

```bash
azul
```

This will start an interactive session. Type your requests and AZUL will execute them using its available tools:

- `read_file(file_path)` - Read files from the filesystem
- `write_file_nano(file_path, new_content)` - Create or overwrite files
- `delete_file(file_path)` - Delete files
- `respond_to_user(message)` - Signal completion and respond

Type `exit`, `quit`, or `q` to exit the session.

## Example

```
> User: Create a python file named app.py that prints "Hello, Agent!"

┌─ Agent is working... ──────────────────────────────────────────────────┐
│    THINKING: Analyzing request: Create a python file...                 │
│    PLAN:                                                                │
│    1. Call write_file_nano with path 'app.py' and the Python code.     │
│ ⚡ ACTION: write_file_nano('app.py', 'print("Hello, Agent!")')          │
│   RESULT: Successfully wrote to app.py.                                │
└────────────────────────────────────────────────────────────────────────┘
  AZUL: I have created the file `app.py` for you.
```

## Architecture

AZUL consists of several key components:

- **llama_client.py**: Direct interface to llama-cpp-python
- **agent.py**: LangChain/LangGraph agent integration with ReAct pattern
- **tools.py**: File system operations (read, write, delete)
- **tui.py**: Rich-based TUI frontend
- **session_manager.py**: Conversation history persistence
- **cli.py**: Main CLI entry point

## Configuration

Configuration is managed through environment variables:

- `AZUL_MODEL_PATH` (required): Path to your GGUF model file

Session data is stored in `~/.azul/sessions/` by default.

## Troubleshooting

**Model not found:**
- Ensure `AZUL_MODEL_PATH` is set correctly
- Verify the model file exists at the specified path
- Check file permissions

**Import errors:**
- Make sure the virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`

**Performance issues:**
- Ensure you have GPU support enabled (n_gpu_layers=-1 by default)
- Try a smaller model or reduce n_ctx if running out of memory

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

