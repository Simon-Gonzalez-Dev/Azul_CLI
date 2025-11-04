# AZUL CLI

A Claude-like coding assistant powered by local LLMs via Ollama. AZUL provides an interactive command-line interface for code editing, explanations, documentation, and more - all running locally on your machine.

## Features

- **Interactive REPL**: Natural language conversation with your AI assistant
- **File Editing**: Safe, permission-based file editing with unified diff support
- **Code Awareness**: Intelligent context injection using Tree-sitter for efficient code parsing
- **Git Integration**: Automatic branch creation and file staging for edits
- **Session Management**: Directory-based conversation history
- **Real-time Streaming**: Token-by-token response streaming for immediate feedback
- **Sandboxed Environment**: Secure file operations restricted to your project directory

## Requirements

### Hardware Recommendations

**⚠️ GPU Acceleration is Strongly Recommended**

AZUL performs significantly better with GPU acceleration. The difference between CPU and GPU inference can be dramatic:

- **CPU**: Slower responses, higher latency
- **GPU**: Fast, responsive, real-time experience

For best results:
- Use a GPU with at least 8GB VRAM for the default model (qwen2.5-coder:14b)
- NVIDIA GPUs work best with CUDA support
- Apple Silicon (M1/M2/M3) also provides excellent performance

### Software Requirements

- Python 3.10 or higher
- [Ollama](https://ollama.ai/) installed and running
- The `qwen2.5-coder:14b` model (or another coding model) installed in Ollama

## Installation

1. **Install Ollama** (if not already installed):
   ```bash
   # macOS/Linux
   curl -fsSL https://ollama.ai/install.sh | sh
   
   # Or download from https://ollama.ai
   ```

2. **Pull the recommended model**:
   ```bash
   ollama pull qwen2.5-coder:14b
   ```

3. **Install AZUL CLI**:
   ```bash
   # Clone the repository
   git clone <repository-url>
   cd Azul_CLI
   
   # Install in development mode
   pip install -e .
   ```

4. **Verify installation**:
   ```bash
   azul --help
   ```

## Usage

### Basic Usage

Start AZUL in your project directory:

```bash
azul
```

This launches the interactive REPL where you can:
- Ask questions about your code
- Request file edits
- Get explanations and documentation
- Use `@` commands for specific actions

### Starting with a File

```bash
azul path/to/file.py
```

This loads the file into context and starts a conversation about it.

### @ Commands

All commands in AZUL use the `@` prefix. Everything else is treated as a natural language prompt.

- `@model [name]` - Change Ollama model or show current model
- `@edit <file> <instruction>` - Edit a file with a specific instruction
- `@read <file>` - Read and display a file
- `@clear` - Clear conversation history
- `@help` - Show available commands
- `@exit` / `@quit` - Exit AZUL

### Examples

#### Natural Language Prompts

```bash
azul> explain the main function in app.py
azul> add error handling to the calculate function
azul> document the User class
azul> what does this code do?
```

#### Using @ Commands

```bash
azul> @read src/main.py
azul> @edit src/main.py add type hints to all functions
azul> @model llama3.2
azul> @clear
```

#### File Editing Flow

1. Request an edit (via `@edit` or natural language):
   ```
   azul> @edit utils.py add docstrings to all functions
   ```

2. AZUL shows a color-coded diff preview:
   ```
   --- a/utils.py
   +++ b/utils.py
   @@ -5,6 +5,10 @@
   +"""
   +Utility functions for the application.
   +"""
   def calculate_total(items):
   +    """
   +    Calculate the total of a list of items.
   +    """
       return sum(items)
   ```

3. Confirm the changes:
   ```
   Apply these changes? (y/n): y
   ```

4. AZUL creates a git branch (if git is available), applies changes, and stages files.

## Configuration

AZUL stores configuration in `~/.azul/config.json`. The default configuration includes:

```json
{
  "model": "qwen2.5-coder:14b",
  "temperature": 0.7,
  "max_history_messages": 20,
  "max_file_size_mb": 10,
  "auto_git_branch": true,
  "auto_git_stage": true,
  "git_branch_prefix": "azul-edit",
  "permission_defaults": {
    "auto_approve": false,
    "remember_choices": true
  },
  "context_window_size": 4096,
  "enable_file_monitoring": true,
  "enable_cherry_picking": false
}
```

### Changing the Default Model

You can change the default model in two ways:

1. **Via @model command** (temporary, for current session):
   ```
   azul> @model llama3.2
   ```

2. **Edit config file** (permanent):
   ```bash
   # Edit ~/.azul/config.json
   {
     "model": "your-preferred-model"
   }
   ```

## Architecture

### Components

- **REPL**: Interactive shell with prompt-toolkit
- **Ollama Client**: Streaming communication with Ollama API
- **Session Manager**: Per-directory conversation history
- **Context Manager**: Intelligent code parsing with Tree-sitter
- **Editor**: Unified diff parsing and application
- **Permission System**: Safe file operations with user confirmation
- **Sandbox**: Path validation and security
- **File Monitor**: Watchdog-based file change notifications

### Security

- **Sandboxed File Operations**: All file paths validated to prevent directory traversal
- **Permission-Based**: Read-only by default, explicit permission required for edits
- **Backup Creation**: Automatic backups before file modifications
- **Git Integration**: Automatic branching for safe experimentation

## Performance Tips

1. **Use GPU Acceleration**: Ensure Ollama is using your GPU:
   ```bash
   # Check GPU usage
   nvidia-smi  # For NVIDIA
   ```

2. **Model Selection**: Smaller models are faster but less capable:
   - `qwen2.5-coder:14b` - Recommended balance
   - `qwen2.5-coder:7b` - Faster, slightly less capable
   - `codellama:34b` - More capable, requires more VRAM

3. **Context Management**: AZUL automatically manages context to stay within model limits

## Troubleshooting

### Ollama Connection Errors

If you see connection errors:
```bash
# Check if Ollama is running
ollama list

# Start Ollama server if needed
ollama serve
```

### Model Not Found

If a model isn't found:
```bash
# List available models
ollama list

# Pull the model
ollama pull qwen2.5-coder:14b
```

### File Permission Errors

If file operations fail:
- Check that files are within the project directory
- Ensure you have write permissions
- Verify the file isn't binary or too large (>10MB)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License

## Acknowledgments

- Built with [Ollama](https://ollama.ai/)
- Inspired by Anthropic's Claude Code
- Uses [Rich](https://github.com/Textualize/rich) for beautiful terminal output

