# Azul - Local AI Coding Assistant

Azul is a powerful, locally-run AI coding assistant with a terminal-based UI. Built with TypeScript, React/Ink, Express, and node-llama-cpp, it provides an intelligent agent that can help with coding tasks using local LLM inference.

## Features

- **Local AI Processing** - Uses Qwen 2.5 Coder model via llama.cpp (no cloud dependencies)
- **Terminal UI** - Beautiful terminal interface built with React and Ink
- **Tool System** - File operations, shell commands, and search capabilities
- **Permission System** - Approval flow for potentially destructive operations
- ⚡ **Real-time Communication** - WebSocket-based client-server architecture

## Architecture

- **Monorepo**: NPM workspaces with two packages
  - `packages/server` - Express backend with LLM and agent logic
  - `packages/ui` - React/Ink terminal interface
- **Tech Stack**: TypeScript, React, Ink, Express, WebSocket, node-llama-cpp
- **Model**: Qwen 2.5 Coder 7B (quantized GGUF format)

## Prerequisites

- Node.js v18+ (tested with v22.14.0)
- NPM v9+
- At least 8GB RAM (for running the 7B model)
- macOS, Linux, or Windows with WSL

## Installation

1. **Clone or navigate to the project**:
```bash
cd azul_new
```

2. **Install dependencies**:
```bash
npm install
```

3. **Build the project**:
```bash
npm run build
```

4. **(Optional) Create global command**:
```bash
cd packages/server
npm link
```

## Usage

### Running Azul

From the project root:
```bash
npm run dev
```

Or if you've linked the package:
```bash
azul
```

### Configuration

Edit `config.json` in the project root:
```json
{
  "modelPath": "./models/qwen2.5-coder-7b-instruct-q4_k_m.gguf",
  "port": 3737,
  "contextSize": 8192,
  "maxTokens": 2048
}
```

### Available Tools

The AI agent has access to the following tools:

1. **read_file** - Read file contents
2. **write_file** - Create or modify files (requires approval)
3. **list_dir** - List directory contents
4. **execute_command** - Run shell commands (requires approval)
5. **search_files** - Search for patterns in files (grep-like)

### Using the Interface

- **Type messages** to interact with the AI
- **Press Enter** to send
- **Y/N keys** to approve/deny tool execution requests
- **Ctrl+C** to exit

## Project Structure

```
azul_new/
├── package.json              # Root workspace configuration
├── tsconfig.base.json        # Shared TypeScript config
├── config.json               # Runtime configuration
├── models/                   # GGUF model files
│   └── qwen2.5-coder-7b-instruct-q4_k_m.gguf
└── packages/
    ├── server/               # Backend package
    │   ├── src/
    │   │   ├── main.ts       # Server entry point
    │   │   ├── llm.ts        # LLM service
    │   │   ├── agent.ts      # Agent loop logic
    │   │   ├── websocket.ts  # WebSocket manager
    │   │   ├── types.ts      # Shared types
    │   │   └── tools/        # Tool implementations
    │   └── package.json
    └── ui/                   # Frontend package
        ├── src/
        │   ├── main.tsx      # UI entry point
        │   ├── App.tsx       # Root component
        │   ├── types.ts      # UI types
        │   └── components/   # React components
        └── package.json
```

## Development

### Build individual packages:
```bash
# Build server
cd packages/server && npm run build

# Build UI
cd packages/ui && npm run build
```

### Clean build artifacts:
```bash
npm run clean
```

## How It Works

1. **Server Initialization**: Express server starts and loads the LLM model
2. **WebSocket Setup**: WebSocket server is created for real-time communication
3. **UI Rendering**: React/Ink UI renders in the terminal and connects to WebSocket
4. **Agent Loop**: 
   - User sends message
   - Agent thinks and determines required tools
   - Tools are executed (with approval if needed)
   - Agent provides response
5. **Graceful Shutdown**: Ctrl+C cleanly shuts down all services

## Troubleshooting

### Model fails to load
- Ensure the model file exists at the path specified in `config.json`
- Check you have enough RAM (7B Q4 model needs ~5-6GB)
- Verify the model file is not corrupted

### Port already in use
- Change the `port` in `config.json`
- Check if another instance is running

### Build errors
- Clear node_modules and reinstall: `rm -rf node_modules && npm install`
- Rebuild: `npm run clean && npm run build`

## License

MIT

## Contributing

This is a reference implementation. Feel free to extend with additional tools, improve the UI, or optimize the agent logic.

