Definitive Architectural Blueprint for "Azul": A React/Express AI Engineering Agent
You are a world-class AI agent developer, acting as a lead systems architect. Your mission is to generate the complete source code for Azul, a cutting-edge, locally-run AI coding assistant. This prompt is your definitive specification, detailing a robust, single-language architecture that directly implements the core philosophies of modern terminal applications within a unified React and Express framework.
Azul is a powerful, locally-run agent whose architecture is built entirely on TypeScript. This design choice maximizes code sharing, simplifies the build process, and creates a seamless development experience managed entirely by NPM.
Part 1: The React/Express Centered Architecture
Azul is a monorepo application, meaning the frontend and backend components live in the same repository and are managed by a single NPM command set. This tightly integrated structure consists of two main packages:
The Frontend (UI Layer): A terminal-based user interface built with React and Ink.[1][2][3]
Responsibility: All user-facing rendering and interaction within the terminal. It captures user input and displays formatted data received from the backend.
Tech Stack: TypeScript, React, Ink (which uses Yoga for layout).[1][2][3] This directly mirrors the UI technology of Claude Code.
Execution: Renders within a Node.js process initiated by the Express backend.
The Backend (Execution Layer): An Express.js server.
Responsibility: All heavy lifting. This includes managing the agent's logic, handling the WebSocket connection, executing tools (filesystem access, shell commands), and, crucially, running the local Large Language Model (LLM) through Llama.cpp bindings.
Tech Stack: TypeScript, Express.js, node-llama-cpp, and a WebSocket library like ws.
Execution: Runs as the main Node.js process, serving the UI and managing the AI core.
Communication Channel: The frontend and backend communicate in real-time over a local WebSocket connection. The Express server hosts the WebSocket server, and the React/Ink frontend acts as the client, enabling fluid, bidirectional data exchange.
Part 2: The Project Structure - An NPM Monorepo
The entire project will be managed using NPM Workspaces, which makes managing dependencies and running scripts across packages effortless.[4][5]
code
Code
azul/
├── package.json           # Root package.json with workspace definitions and global scripts
├── tsconfig.base.json     # Shared TypeScript configuration
└── packages/
    ├── ui/                # The React/Ink frontend package
    │   ├── package.json
    │   ├── tsconfig.json
    │   └── src/
    │       ├── main.tsx             # Main application entry point, establishes WebSocket connection
    │       ├── App.tsx              # Root React component, manages global state
    │       └── components/
    │           ├── LogView.tsx
    │           ├── StatusBar.tsx
    │           ├── UserInput.tsx
    │           ├── TodoDrawer.tsx
    │           └── PermissionModal.tsx
    └── server/            # The Express.js backend package
        ├── package.json
        ├── tsconfig.json
        └── src/
            ├── main.ts              # Main server entry point (starts Express, prints banner)
            ├── agent.ts             # The core async agentic loop logic
            ├── llm.ts               # Handles all node-llama-cpp interaction
            ├── tools/               # Agent's toolkit module (filesystem.ts, shell.ts, etc.)
            └── websocket.ts         # Manages WebSocket connections and message routing
Part 3: The Backend - The Express/Llama.cpp Core
This is the brain of Azul, a headless service that runs the AI and exposes its functionality over a WebSocket.
3.1. Core Logic (main.ts & agent.ts)
The main.ts script will:
Print the glorious "AZUL" banner.
Initialize and start an Express server.
Set up a WebSocket server attached to the Express instance.
Instantiate and run the React/Ink UI.
The websocket.ts file handles incoming connections. When a UI client connects, a new instance of the Agent from agent.ts is spawned.
The Agent runs its "Thought -> Plan -> Action -> Observation" loop. After each step, it serializes its state (e.g., thought, plan) into a JSON message and sends it over the WebSocket to the UI.[6]
3.2. Local AI with Llama.cpp (llm.ts)
This module uses the node-llama-cpp library to load and interact with a local GGUF model file.[7][8]
It will expose simple functions like getCompletion(prompt) that the agent.ts can call. The library handles the complexities of managing model context and generating responses.[9]
The path to the local model file will be configurable.
Part 4: The Frontend - The TypeScript/React/Ink UI
This is the user-facing application, built exactly as described in the Claude Code documentation but managed within the NPM ecosystem.
4.1. UI Components & State Management
App.tsx: The root component uses React Hooks (useState, useEffect, useReducer) to manage the application's state, which is a direct reflection of the JSON messages received from the Express backend.
useEffect Hook: A useEffect hook in main.tsx will establish the WebSocket connection on component mount and register handlers for incoming messages, which then dispatch state updates.
Component Breakdown:
LogView.tsx: Renders the stream of agent thoughts, code, and tool outputs.
UserInput.tsx: An interactive text input for the user.
TodoDrawer.tsx: A collapsible view showing the agent's current plan, toggled by a hotkey.
PermissionModal.tsx: Conditionally rendered to ask for user confirmation on potentially destructive actions (e.g., running a shell command).
Part 5: The WebSocket Communication Protocol
A strict JSON-based protocol ensures clean communication between the Express server and the React/Ink client.
Client -> Server Messages:
{"type": "user_prompt", "payload": {"text": "..."}}
{"type": "action_response", "payload": {"approved": true}}
Server -> Client Messages:
{"type": "agent_thought", "payload": {"text": "..."}}
{"type": "agent_plan", "payload": {"tasks": [...]}}
{"type": "action_request", "payload": {"tool_name": "execute_shell", "arguments": {...}}}
{"type": "tool_observation", "payload": {"stdout": "...", "stderr": "..."}}
Part 6: Build, Packaging, and Execution with NPM
The monorepo structure and NPM Workspaces make the entire process incredibly simple.[4]
Installation: Running npm install in the root directory will install all dependencies for both the ui and server packages.
Build Step: A single command, npm run build, will execute the TypeScript compiler (tsc) for both packages/ui and packages/server, outputting the compiled JavaScript to dist/ folders within each package.
Execution (azul command):
The server/package.json will contain a "bin" field: "azul": "./dist/main.js".
Running npm link during development will create a global azul command.
The npm start script in the root package.json will simply run node packages/server/dist/main.js.
This single command starts the Express server, which in turn renders the React/Ink UI in the same terminal process, creating a seamless, unified application experience. When the user quits, the single process terminates cleanly.
This architectural blueprint delivers a modern, robust, and developer-friendly foundation for Azul, leveraging the power and simplicity of a unified React/Express stack, all easily managed with NPM.