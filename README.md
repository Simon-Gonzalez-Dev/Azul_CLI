# AZUL - Local AI Coding Assistant

```
    █████╗   ███████╗   ██╗   ██╗   ██╡       
   ██╔══██╗   ╚════██╗  ██║   ██║   ██║      
  ███████║    █████╔╝   ██║   ██║   ██║       
 ██╔══██║    ██╔═══╝    ██║   ██║   ██║       
██║  ██║     ███████╗   ╚██████╔╝   ███████╗  
╚═╝  ╚═╝     ╚══════╝    ╚═════╝    ╚══════╝ 
```

AZUL is a **local-first AI coding assistant** that mirrors the architecture of Claude Code. It features a hybrid architecture with a Python backend running a LangChain agent and a TypeScript/React/Ink frontend for a beautiful terminal UI.

## ✨ Features

- 🤖 **Fully Local**: Runs entirely on your machine using llama-cpp-python
- 🎨 **Beautiful TUI**: React/Ink-based terminal interface with real-time updates
- 🔧 **Agentic Tools**: File operations, shell execution, and directory navigation
- 💭 **Transparent Reasoning**: See the agent think, plan, and execute in real-time
- 📋 **Task Planning**: Built-in todo drawer to track agent's execution plan
- ⚡ **WebSocket Communication**: Real-time bidirectional updates between backend and frontend

## 🏗️ Architecture

AZUL consists of two processes that communicate over WebSockets:

### Backend (Python)
- **WebSocket Server**: Handles client connections on `ws://localhost:8765`
- **LangChain Agent**: ReAct-style agent with tool calling
- **llama-cpp-python**: Local LLM inference with the Qwen 2.5 Coder model
- **Tools**: File operations, shell commands, directory listing

### Frontend (TypeScript/Ink)
- **React Components**: LogView, UserInput, StatusBar, TodoDrawer
- **WebSocket Client**: Connects to backend and handles message streams
- **Real-time UI**: Updates as the agent thinks, acts, and responds

## 📋 Prerequisites

Before installing AZUL, ensure you have:

1. **Python 3.10+** - [Download Python](https://www.python.org/downloads/)
2. **Poetry** - Python package manager
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```
3. **Bun** - Fast JavaScript runtime and package manager
   ```bash
   curl -fsSL https://bun.sh/install | bash
   ```
4. **GGUF Model** - The Qwen 2.5 Coder model is already included in `models/`

## 🚀 Installation

### 1. Install Backend Dependencies

```bash
cd azul-backend
poetry install
```

This will install:
- `websockets` - WebSocket server
- `llama-cpp-python` - LLM inference (may take a while to compile)
- `langchain` - Agent framework
- `langgraph` - Agent execution graph
- `pydantic` - Message validation

**Note**: `llama-cpp-python` installation may take 5-10 minutes as it compiles from source. If you have a GPU, it will automatically use it for acceleration.

### 2. Install Frontend Dependencies

```bash
cd azul-ui
bun install
```

This will install:
- `ink` - React for terminal UIs
- `react` - UI framework
- `ws` - WebSocket client
- `ink-text-input` - Input component
- Other UI dependencies

## 🎮 Usage

### Quick Start

From the project root, simply run:

```bash
python azul.py
```

Or make it executable and run directly:

```bash
chmod +x azul.py
./azul.py
```

The launcher will:
1. ✓ Check all dependencies
2. ✓ Start the Python backend server
3. ✓ Wait for the server to be ready
4. ✓ Launch the Ink-based frontend UI
5. ✓ Handle cleanup on exit

### Using AZUL

Once launched, you'll see the AZUL terminal UI:

```
> Create a Python file named hello.py that prints "Hello, AZUL!"

💭 I need to create a Python file with print statement...
⚡ write_file({"file_path": "hello.py", "content": "print(\"Hello, AZUL!\")"})
✓ Successfully wrote to /path/to/hello.py

AZUL: I've created the file hello.py for you.
```

### Keyboard Shortcuts

- **Enter** - Submit your input
- **Ctrl+T** - Toggle the Todo/Plan drawer
- **Ctrl+C** - Exit AZUL

### Example Commands

Try asking AZUL to:

- `Create a Python script that calculates fibonacci numbers`
- `Read the contents of package.json`
- `List all Python files in the current directory`
- `Execute ls -la and show me the results`
- `Delete the test.txt file`

## 🛠️ Available Tools

AZUL's agent has access to these tools:

| Tool | Description | Example |
|------|-------------|---------|
| `read_file` | Read file contents | Read configuration files |
| `write_file` | Create or overwrite files | Generate code, create configs |
| `delete_file` | Delete files | Clean up temporary files |
| `execute_shell` | Run shell commands | Run tests, install packages |
| `list_directory` | List directory contents | Explore project structure |

## 📁 Project Structure

```
Azul_CLI/
├── azul.py                 # Main launcher script
├── models/                 # LLM models
│   └── qwen2.5-coder-7b-instruct-q4_k_m.gguf
│
├── azul-backend/           # Python backend
│   ├── pyproject.toml      # Poetry dependencies
│   └── src/
│       └── azul_core/
│           ├── server.py   # WebSocket server
│           ├── agent.py    # LangChain agent
│           ├── llm.py      # LLM wrapper
│           ├── tools.py    # Agent tools
│           ├── protocol.py # Message types
│           └── config.py   # Configuration
│
└── azul-ui/                # TypeScript frontend
    ├── package.json        # Bun dependencies
    ├── tsconfig.json       # TypeScript config
    └── src/
        ├── main.tsx        # Entry point
        ├── App.tsx         # Main component
        └── components/
            ├── LogView.tsx    # Message log
            ├── UserInput.tsx  # Input box
            ├── StatusBar.tsx  # Status display
            └── TodoDrawer.tsx # Plan viewer
```

## ⚙️ Configuration

### Backend Configuration

Edit `azul-backend/src/azul_core/config.py` to customize:

```python
# Model settings
model_path: Path        # Path to GGUF model
n_ctx: int = 8192      # Context window size
n_gpu_layers: int = -1 # GPU layers (-1 = all)

# Agent settings
max_iterations: int = 50    # Max agent loops
temperature: float = 0.7    # LLM creativity
max_tokens: int = 8192      # Generation limit

# WebSocket settings
websocket_host: str = "localhost"
websocket_port: int = 8765
```

You can also use environment variables:

```bash
export AZUL_WEBSOCKET_PORT=9000
export AZUL_TEMPERATURE=0.5
```

### Using a Different Model

To use a different GGUF model:

1. Download your model (must be GGUF format)
2. Place it in the `models/` directory
3. Update `config.py` with the new model path:

```python
model_path = Path(__file__).parent.parent.parent.parent / "models" / "your-model.gguf"
```

## 🐛 Troubleshooting

### Backend won't start

```bash
# Check if Python dependencies are installed
cd azul-backend
poetry install

# Run backend directly to see errors
cd azul-backend/src
python -m azul_core.server
```

### Frontend won't start

```bash
# Check if Bun dependencies are installed
cd azul-ui
bun install

# Run frontend directly to see errors
bun run src/main.tsx
```

### Port 8765 already in use

Another AZUL instance may be running. Find and kill it:

```bash
# macOS/Linux
lsof -ti:8765 | xargs kill -9

# Or change the port in config.py
```

### Model not loading

- Ensure the model file exists in `models/`
- Check that you have enough RAM (7B model needs ~8GB)
- Verify the model is in GGUF format

### llama-cpp-python installation fails

Try installing with specific build flags:

```bash
# For macOS with Metal GPU support
CMAKE_ARGS="-DLLAMA_METAL=on" pip install llama-cpp-python

# For CUDA GPU support
CMAKE_ARGS="-DLLAMA_CUBLAS=on" pip install llama-cpp-python

# For CPU only
pip install llama-cpp-python
```

## 🎯 Development

### Running Backend Standalone

```bash
cd azul-backend/src
python -m azul_core.server
```

### Running Frontend Standalone

Make sure the backend is running first, then:

```bash
cd azul-ui
bun run src/main.tsx
```

### Development Mode

For frontend hot reload during development:

```bash
cd azul-ui
bun run dev
```

## 📝 Technical Details

### WebSocket Protocol

Messages follow this JSON schema:

**Client → Server:**
```json
{
  "type": "user_prompt",
  "text": "Your request here"
}
```

**Server → Client:**
```json
{
  "type": "agent_thought",
  "text": "Analyzing the request..."
}

{
  "type": "tool_call",
  "tool": "write_file",
  "args": {"file_path": "...", "content": "..."}
}

{
  "type": "tool_result",
  "result": "Success message",
  "success": true
}
```

### Agent Workflow

1. **THINK**: Analyze user request
2. **PLAN**: Break down into steps (optional)
3. **ACT**: Execute tools
4. **OBSERVE**: Process results
5. **RESPOND**: Provide answer

## 🤝 Contributing

AZUL is a local-first project designed for personal use and learning. Feel free to:

- Fork and modify for your needs
- Add new tools in `azul-backend/src/azul_core/tools.py`
- Customize the UI in `azul-ui/src/components/`
- Experiment with different models

## 📄 License

This project is provided as-is for educational and personal use.

## 🙏 Acknowledgments

- **Anthropic** - For the Claude Code architecture inspiration
- **llama.cpp** - For making local LLM inference possible
- **LangChain** - For the agent framework
- **Ink** - For beautiful terminal UIs with React

## 🚀 What's Next?

Potential enhancements:

- [ ] Streaming responses (token-by-token)
- [ ] Multi-file editing support
- [ ] Code search and navigation
- [ ] Git integration
- [ ] Custom tool creation
- [ ] Session persistence
- [ ] Multiple model support
- [ ] Plan extraction and visualization

---

**Built with ❤️ for local-first AI development**

