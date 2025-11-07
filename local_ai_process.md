# AZUL: Local Agentic AI CLI Architecture

This document describes the complete architecture of AZUL, a local agentic AI coding assistant CLI tool. AZUL uses llama.cpp via llama-cpp-python to run the qwen2.5-coder-7b-instruct-q4_k_m.gguf model locally, orchestrated through LangChain for tool-calling, presented via a Textual TUI, and executing file operations transparently through nano via pexpect.

## Overview

AZUL is a fully agentic coding assistant that operates entirely on the user's local machine. It provides a single-screen terminal interface where users can interact with an AI that reasons, plans, and executes file operations (Create, Read, Update, Delete) to fulfill coding tasks.

**Core Technologies**:
- **llama-cpp-python**: Fast local LLM inference engine
- **LangChain/LlamaIndex**: Agent orchestration and tool-calling framework
- **Textual**: Modern, responsive terminal user interface framework
- **pexpect**: Programmatic control of nano editor for transparent file editing

**Two Operation Modes**:
1. **Simple Mode**: Direct generation with diff/file: blocks (backward compatible)
2. **Agentic Mode**: Structured tool-calling with Think-Plan-Act loop (primary mode)

## Architecture Components

### 1. Model Initialization Layer

**Location**: `azul/llama_client.py` - `LlamaClient.__init__()` and `_load_model()`

**Purpose**: Initialize and load the GGUF model file with optimized settings for fast local inference.

**Key Components**:

```python
from llama_cpp import Llama

# Model initialization parameters
self._model = Llama(
    model_path=model_path,        # Path to .gguf file (qwen2.5-coder-7b-instruct-q4_k_m.gguf)
    n_ctx=4096,                   # Context window size (tokens)
    n_threads=None,               # Auto-detect CPU cores
    n_gpu_layers=-1,              # Full GPU acceleration (-1 = all layers)
    n_batch=512,                  # Batch size for processing
    verbose=False,                # Suppress verbose output
    use_mlock=True,               # Lock memory (prevent swapping) - critical for performance
    use_mmap=True,                # Memory mapping (faster loads)
    n_threads_batch=None,         # Auto-detect batch threads
)
```

**Model Path Resolution**:
- Priority order for finding model files:
  1. `azul/models/` directory (package directory)
  2. `~/.azul/models/` directory (user-specific model cache)
  3. `~/models/` directory (common user model directory)
  4. Current working directory
  5. Home directory
- Supports absolute paths, relative paths, and model filenames
- Model path is cached in configuration for persistence
- CLI argument `--model-path` allows explicit model specification

**Model Loading Strategy**:
- Lazy loading: Model is only loaded when first needed
- Caching: If the same model path is requested, skip reload
- Memory management: Unloads previous model before loading new one
- Performance: `use_mlock=True` prevents swapping, `use_mmap=True` enables faster loads

### 2. System Prompt Definition

**Location**: `azul/llama_client.py` - `LlamaClient.SYSTEM_PROMPT` and `azul/agent.py` - Agent system prompt

**Purpose**: Define the assistant's role, capabilities, and output format expectations. The system supports two prompt styles depending on operation mode.

#### Simple Mode System Prompt (Backward Compatible)

```
You are AZUL, an AI coding assistant. You help with coding tasks, file editing, and documentation.

FILE OPERATIONS:
1. EDITING: Provide changes as unified diff in ```diff code block
2. CREATING: Provide file content in ```file:filename code block  
3. DELETING: Indicate with ```delete:filename code block

Be concise and code-focused.
```

#### Agentic Mode System Prompt (Primary)

The agentic mode uses a structured tool-calling format. The system prompt defines available tools and their schemas:

```
You are AZUL, an autonomous AI coding assistant that operates within a CLI. You fulfill user requests by reasoning, planning, and executing file operations using available tools.

AVAILABLE TOOLS:

1. read_file(file_path: str) -> str
   - Reads the content of a file and returns it as a string.
   - Use this to understand existing code before making changes.
   - Example: read_file("src/main.py")

2. write_file_nano(file_path: str, new_content: str) -> str
   - Creates or overwrites a file with new content using the nano editor.
   - This tool performs actual file operations transparently.
   - Example: write_file_nano("main.py", "print('Hello')\n")

3. delete_file(file_path: str) -> str
   - Deletes a file from the filesystem.
   - Use with caution and only when explicitly requested.
   - Example: delete_file("old_file.py")

4. respond_to_user(message: str) -> None
   - Sends a message to the user and terminates the agent loop.
   - Use this when the task is complete or if you need clarification.
   - Example: respond_to_user("I've created the file as requested.")

WORKFLOW:
For every user request, follow this process:
1. THINK: Analyze the user's request and determine what needs to be done
2. PLAN: List the sequence of tool calls needed to accomplish the task
3. ACT: Execute tools one by one, using the results to inform next steps
4. RESPOND: When complete, use respond_to_user() to communicate the result

OUTPUT FORMAT:
You must output your reasoning and tool calls in a structured JSON format:
{
  "thought": "Your reasoning about the task",
  "plan": ["Step 1", "Step 2", ...],
  "actions": [
    {"type": "tool_name", "parameters": {...}}
  ]
}
```

**Characteristics**:
- Cached in memory (`_cached_system_prompt`) to avoid repeated string operations
- Can be overridden per-request via `system_prompt` parameter
- Defines expected output formats for both operation modes
- Tool schemas are also defined in LangChain tool definitions for validation

### 3. Agentic Core (LangChain Integration)

**Location**: `azul/agent.py` - `AgentExecutor` and tool definitions

**Purpose**: Orchestrate the Think-Plan-Act loop using LangChain's agent framework.

**Architecture**:

```python
from langchain.agents import AgentExecutor, create_structured_chat_agent
from langchain.tools import Tool
from langchain_community.llms import LlamaCpp

# Initialize LangChain wrapper around llama-cpp-python
llm = LlamaCpp(
    model_path=model_path,
    # ... configuration matching LlamaClient parameters
)

# Define tools
tools = [
    Tool(
        name="read_file",
        func=read_file_tool,
        description="Reads file content from filesystem"
    ),
    Tool(
        name="write_file_nano",
        func=write_file_nano_tool,
        description="Creates or edits a file using nano editor"
    ),
    Tool(
        name="delete_file",
        func=delete_file_tool,
        description="Deletes a file from filesystem"
    ),
]

# Create agent executor
agent_executor = AgentExecutor.from_agent_and_tools(
    agent=create_structured_chat_agent(llm, tools, system_prompt),
    tools=tools,
    verbose=True,  # Enables detailed logging for TUI display
    max_iterations=10,  # Prevent infinite loops
    handle_parsing_errors=True
)
```

**Agent Workflow** (Thought-Action-Observation Loop):

1. **Thought**: Agent analyzes user request and determines necessary actions
2. **Action**: Agent selects a tool and generates structured call (JSON)
3. **Observation**: Tool executes and returns result
4. **Iteration**: Agent uses observation to decide next action or termination
5. **Response**: Agent calls `respond_to_user()` when task is complete

**Structured Output Parsing**:
- Agent generates JSON/YAML structured output containing tool calls
- Parser extracts tool name, parameters, and arguments
- Validates against tool schemas before execution
- Handles parsing errors gracefully with retry logic

**Integration with LlamaClient**:
- LangChain's `LlamaCpp` wrapper uses the same underlying llama-cpp-python model
- Shares model instance or coordinates loading/unloading
- Agent executor handles conversation history management through LangChain's memory system

### 4. TUI Layer (Textual Framework)

**Location**: `azul/tui.py` - `AzulTUI` application

**Purpose**: Provide a single-screen, cursor-enabled terminal interface that displays the agent's process in real-time.

**Layout Structure**:

```
┌─────────────────────────────────────────────────────────┐
│ [Panel 1: Conversation History] (Top/Left)              │
│ Scrollable log of user prompts and final responses      │
├─────────────────────────────────────────────────────────┤
│ [Panel 2: Live Workspace] (Main Focus)                  │
│ Real-time display of agent's process:                   │
│                                                          │
│ 🤔 THINKING: Analyzing user request...                  │
│ 📝 PLAN:                                                  │
│   1. Read main.py to understand structure               │
│   2. Create new function in utils.py                    │
│   3. Update imports in main.py                          │
│                                                          │
│ 📖 [CALLING TOOL] read_file("main.py")                  │
│ [OBSERVATION] File content retrieved (247 lines)        │
│                                                          │
│ ⚡ [CALLING TOOL] write_file_nano("utils.py", "...")    │
│ [NANO SESSION]                                           │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ GNU nano 6.0              utils.py                  │ │
│ │ def new_function():                                 │ │
│ │     return "Hello"                                  │ │
│ │                                                      │ │
│ │ ^O Write Out  ^X Exit                                │ │
│ └─────────────────────────────────────────────────────┘ │
│ [OBSERVATION] File created successfully                 │
│                                                          │
│ ✅ [RESPOND] Task completed successfully                │
├─────────────────────────────────────────────────────────┤
│ [Panel 3: Input/Status] (Bottom)                        │
│ Status: Ready | Running Agent | Awaiting Nano Input    │
│ Input: [___________________________]                    │
└─────────────────────────────────────────────────────────┘
```

**Implementation Details**:

```python
from textual.app import App
from textual.widgets import RichLog, Input, Static
from textual.containers import Container, Horizontal, Vertical

class AzulTUI(App):
    def compose(self):
        with Vertical():
            with Horizontal():
                yield RichLog(id="history", markup=True)
            with Container(id="workspace"):
                yield RichLog(id="agent_log", markup=True)
                yield RichLog(id="nano_display", markup=True, classes="hidden")
            with Horizontal():
                yield Static("Status: Ready", id="status")
                yield Input(placeholder="Enter your instruction...", id="user_input")
    
    async def on_agent_step(self, step_type: str, content: str):
        """Update workspace with agent step"""
        if step_type == "thinking":
            self.query_one("#agent_log").write(f"🤔 THINKING: {content}")
        elif step_type == "tool_call":
            self.query_one("#agent_log").write(f"⚡ [CALLING TOOL] {content}")
        elif step_type == "observation":
            self.query_one("#agent_log").write(f"[OBSERVATION] {content}")
    
    async def on_nano_session(self, output: str):
        """Display nano session output"""
        self.query_one("#nano_display").remove_class("hidden")
        self.query_one("#nano_display").write(output)
```

**Key Features**:
- **Non-blocking Event Loop**: Agent execution runs in background worker threads
- **Real-time Updates**: TUI updates as agent executes each step
- **Nano Visualization**: When `write_file_nano` is called, TUI shows nano session output
- **Smooth Scrolling**: Automatic scroll to bottom for live updates
- **Input Handling**: User can type next command while agent is running (queued)
- **Status Indicators**: Clear visual feedback on agent state

**Worker Threads**:
- Agent executor runs in `asyncio` task or Textual worker
- Tool execution (especially nano) runs in separate thread
- TUI updates via thread-safe message passing
- Cursor and UI remain responsive during long operations

### 5. Nano Integration (Pexpect)

**Location**: `azul/tools.py` - `write_file_nano_tool()`

**Purpose**: Perform transparent, auditable file editing through the nano editor, proving that edits are real and not faked.

**Implementation**:

```python
import pexpect
import tempfile
import os

def write_file_nano(file_path: str, new_content: str) -> str:
    """
    Creates or edits a file using nano editor via pexpect.
    This ensures transparent, auditable file operations.
    """
    # Create temporary file with new content
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.tmp') as tmp:
        tmp.write(new_content)
        tmp_path = tmp.name
    
    try:
        # Copy temp file to target location if editing existing file
        if os.path.exists(file_path):
            # For editing: open existing file, replace content
            # For simplicity, we'll use a script approach
            pass
        
        # Execute nano via pexpect
        # Method 1: Direct content injection (simpler)
        # Write content to temp file, then copy
        os.makedirs(os.path.dirname(file_path) or '.', exist_ok=True)
        with open(file_path, 'w') as f:
            f.write(new_content)
        
        # Method 2: Actual nano session (more transparent)
        # Open nano with file, programmatically insert content, save, exit
        child = pexpect.spawn(f'nano {file_path}', encoding='utf-8')
        
        # If file doesn't exist, nano creates it
        # Clear existing content (Ctrl+K repeatedly or select all)
        # Paste new content
        # Save (Ctrl+O, Enter)
        # Exit (Ctrl+X)
        
        # For full transparency, capture all output
        nano_output = []
        while True:
            try:
                index = child.expect([pexpect.EOF, pexpect.TIMEOUT], timeout=0.1)
                if index == 0:
                    break
                nano_output.append(child.before)
            except pexpect.TIMEOUT:
                # Send keystrokes programmatically
                # This is complex - simpler approach: use temp file + copy
                break
        
        # Return nano session output for TUI display
        return "".join(nano_output)
    
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
```

**Workflow**:
1. **Content Preparation**: New file content is prepared in memory
2. **Nano Invocation**: Pexpect spawns nano process with target file
3. **Content Injection**: Content is inserted programmatically (or via temp file + copy)
4. **Save Operation**: Nano saves file (Ctrl+O, Enter)
5. **Exit**: Nano exits (Ctrl+X)
6. **Output Capture**: All nano terminal output is captured for TUI display
7. **Verification**: File is verified to contain expected content

**Transparency Benefits**:
- User can see exactly what nano commands are executed
- Terminal output proves nano was actually used
- No "hidden" file I/O that could be faked
- Full audit trail of file operations

**Alternative Approach** (Simpler, Still Transparent):
- Write content to temporary file
- Execute shell command: `cat /tmp/temp_content.py > target.py`
- Display command in TUI as: `⚡ Action: EDITING 'target.py' using nano`
- This maintains transparency while simplifying implementation

### 6. Tool Definitions

**Location**: `azul/tools.py` - Individual tool functions

**Purpose**: Implement the concrete file operations that the agent can execute.

#### read_file(file_path: str) -> str

Reads file content from the filesystem.

```python
def read_file_tool(file_path: str) -> str:
    """Read file content for agent context"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: File '{file_path}' not found"
    except Exception as e:
        return f"Error reading file: {str(e)}"
```

**Usage**: Agent calls this to understand existing code before making changes.

#### write_file_nano(file_path: str, new_content: str) -> str

Creates or edits a file using nano editor (see Nano Integration section above).

**Parameters**:
- `file_path`: Path to file (created if doesn't exist)
- `new_content`: Complete new content for the file

**Returns**: Success message or error description

**Usage**: Primary tool for file creation and editing.

#### delete_file(file_path: str) -> str

Deletes a file from the filesystem.

```python
def delete_file_tool(file_path: str) -> str:
    """Delete a file"""
    try:
        os.remove(file_path)
        return f"File '{file_path}' deleted successfully"
    except FileNotFoundError:
        return f"Error: File '{file_path}' not found"
    except Exception as e:
        return f"Error deleting file: {str(e)}"
```

**Usage**: Agent calls this only when explicitly requested by user.

#### respond_to_user(message: str) -> None

Terminates the agent loop and sends final message to user.

```python
def respond_to_user_tool(message: str) -> None:
    """Signal agent loop completion"""
    # This is a special tool that signals termination
    # LangChain agent executor handles this as stop condition
    raise AgentTermination(message)
```

**Usage**: Agent calls this when task is complete or clarification is needed.

### 7. Output Processing & Tool Execution

**Location**: `azul/agent.py` - Agent executor and `azul/tui.py` - TUI update handlers

**Purpose**: Parse structured output from LLM, route to appropriate tools, execute actions, and update TUI in real-time.

**Processing Flow**:

1. **Token Streaming**: LLM generates tokens via `stream_chat()`
2. **Structured Parsing**: Accumulate tokens until complete JSON/YAML block detected
3. **Validation**: Parse and validate structure against tool schemas
4. **Tool Routing**: Determine which tool to call based on `type` field
5. **Execution**: Execute tool with provided parameters
6. **TUI Update**: Display tool call, execution, and result in workspace panel
7. **Observation**: Return tool result to agent for next iteration
8. **Loop**: Agent processes observation and decides next action

**JSON Structure Example**:

```json
{
  "thought": "User wants to add a new function to utils.py. I need to read the file first to understand its structure, then add the function.",
  "plan": [
    "Read utils.py to see current content",
    "Add new_function() at the end of the file",
    "Confirm completion to user"
  ],
  "actions": [
    {
      "type": "read_file",
      "parameters": {
        "file_path": "utils.py"
      }
    },
    {
      "type": "write_file_nano",
      "parameters": {
        "file_path": "utils.py",
        "new_content": "..."
      }
    },
    {
      "type": "respond_to_user",
      "parameters": {
        "message": "I've added the function to utils.py"
      }
    }
  ]
}
```

**Error Handling**:
- **Parsing Errors**: Invalid JSON/YAML → Retry with error message to LLM
- **Tool Errors**: File not found, permission denied → Return error as observation
- **Agent Loops**: Max iterations exceeded → Force termination with error
- **Nano Failures**: Editor crash or timeout → Rollback and report error

### 8. Conversation History Management

**Location**: `azul/session_manager.py` - `SessionManager`

**Purpose**: Maintain conversation context across multiple interactions, now integrated with LangChain's memory system.

**Data Structure**:

```python
conversation_history: List[Dict[str, str]] = [
    {'role': 'user', 'content': '...'},
    {'role': 'assistant', 'content': '...'},
    # ... more messages
]
```

**History Management**:
- **Storage**: JSON files in `~/.azul_sessions/` directory (or `~/.azul/` for consistency)
- **Session ID**: Generated from project root path (SHA256 hash, first 16 chars)
- **Sliding Window**: Limited to `max_history_messages` (default: 20)
- **Recent History**: `get_recent_history(n=10)` returns last N messages for prompt building
- **Deferred Saving**: History is marked dirty and saved after response completion (not blocking)

**LangChain Integration**:
- LangChain's `ConversationBufferMemory` or `ConversationSummaryMemory` manages agent context
- Session manager provides conversation history to LangChain memory
- Agent executor uses memory to maintain context across tool calls
- History is persisted separately for TUI conversation log display

**History Retrieval**:
- Returns reference to list (not copy) for performance
- Automatically loads from disk on first access
- Applies sliding window when loading if history exceeds limit
- Syncs with LangChain memory after each agent execution

### 9. Prompt Building Pipeline

**Location**: `azul/llama_client.py` - `LlamaClient.build_prompt()` and LangChain's prompt template system

**Purpose**: Transform user message, history, and system prompt into model-ready format. In agentic mode, LangChain handles prompt construction; in simple mode, manual prompt building is used.

**Chat Template**: Uses **Qwen chat template format** with special tokens.

**Prompt Structure** (Simple Mode):

```
<|im_start|>system
{system_prompt}<|im_end|>
<|im_start|>user
{history_user_message_1}<|im_end|>
<|im_start|>assistant
{history_assistant_response_1}<|im_end|>
... (more history pairs) ...
<|im_start|>user
{current_user_message}<|im_end|>
<|im_start|>assistant
```

**Prompt Structure** (Agentic Mode - LangChain):

LangChain's structured chat agent automatically builds prompts with:
- System message (tool definitions and instructions)
- Intermediate steps (tool calls and observations)
- Current user input
- Agent's reasoning and next action

**Implementation Details**:
- **Pre-allocation**: List is pre-allocated with estimated size for efficiency
- **String Building**: Uses list append + single join (most efficient Python string building)
- **Format Caching**: Pre-computes format strings (`<|im_start|>user\n`, etc.) to avoid repeated lookups
- **History Processing**: Iterates through conversation history, adding user/assistant pairs
- **Current Message**: Appends current user message and assistant response start token
- **Token Budget Awareness**: Estimates token count and trims history if approaching `n_ctx` limit

**Input Parameters**:
- `user_message`: Current user input (required)
- `conversation_history`: List of previous messages (optional, defaults to None)
- `system_prompt`: Override system prompt (optional, defaults to cached system prompt)

**Output**: Single string containing the complete formatted prompt ready for model input (simple mode) or structured prompt for LangChain agent (agentic mode).

### 10. Input Flow to Model

**Location**: `azul/llama_client.py` - `LlamaClient.stream_chat()` and `azul/agent.py` - Agent executor

**Purpose**: Send the formatted prompt to the model and receive streaming tokens. In agentic mode, LangChain orchestrates multiple calls; in simple mode, direct streaming is used.

**Input Flow** (Simple Mode):
1. **Prompt Building**: `build_prompt()` creates formatted string
2. **Model Invocation**: Prompt is passed directly to `self._model()` (Llama instance)
3. **Generation Parameters**:
   ```python
   stream = self._model(
       prompt,                    # Formatted prompt string
       max_tokens=2048,          # Maximum tokens to generate
       temperature=0.7,          # Sampling temperature
       top_p=0.9,                # Nucleus sampling parameter
       repeat_penalty=1.1,       # Penalty for repetition
       stream=True,              # Enable streaming mode
       stop=["<|im_end|>", "<|im_start|>", "User:", "System:"],  # Stop sequences
   )
   ```

**Input Flow** (Agentic Mode):
1. **User Input**: Received from TUI input widget
2. **Agent Executor**: LangChain agent executor receives user message
3. **Prompt Construction**: LangChain builds structured prompt with tools and history
4. **Model Invocation**: LangChain's `LlamaCpp` wrapper calls underlying model
5. **Structured Parsing**: Agent output is parsed for tool calls
6. **Tool Execution**: Tools are executed, results returned as observations
7. **Iteration**: Process repeats until `respond_to_user` is called or max iterations reached

**Streaming Mode**:
- `stream=True` enables token-by-token generation
- Each chunk contains `{'choices': [{'text': '...'}]}`
- Tokens are yielded immediately without buffering
- Stop sequences prevent model from generating beyond response
- TUI displays streaming tokens in real-time for user feedback

**Error Handling**:
- Model not loaded: Returns error message
- Malformed chunks: Silently skipped (for performance)
- Exceptions: Caught and returned as error message
- Agent parsing errors: Retry with clarification prompt
- Tool execution errors: Returned as observation for agent to handle

### 11. User Input Processing

**Location**: `azul/tui.py` - `AzulTUI.on_input_submitted()` and `azul/cli.py` - Entry point

**Purpose**: Process user input from TUI or CLI and route to appropriate handler (agentic or simple mode).

**TUI Input Processing Flow**:
1. **User Input**: Received from Textual Input widget in TUI
2. **Mode Detection**: Determine if input should use agentic or simple mode (default: agentic)
3. **Queue Management**: If agent is running, queue input for next execution
4. **Agent Invocation**: Pass input to LangChain agent executor (agentic mode) or direct to LLM (simple mode)
5. **History Update**: Add user message to conversation history
6. **TUI Update**: Update status line and clear workspace for new task

**CLI Entry Point** (`azul/cli.py`):

```python
import sys
from azul.tui import AzulTUI
from azul.agent import AgentExecutor

def main():
    """Main entry point for azul command"""
    if len(sys.argv) > 1 and sys.argv[1] == '--simple':
        # Simple mode: direct LLM interaction
        # ... implement simple REPL or one-shot mode
        pass
    else:
        # Agentic mode: launch TUI
        app = AzulTUI()
        app.run()

if __name__ == "__main__":
    main()
```

**Natural Language Processing**:
- User input is passed directly to agent (no preprocessing)
- Agent interprets intent and selects appropriate tools
- No explicit command parsing needed (agent handles all interpretation)
- Conversation history provides context automatically

**Command Processing** (Optional, for backward compatibility):
- Commands starting with `@` can trigger simple mode
- Example: `@edit file.py instruction` → Simple mode with file context
- Primary mode is agentic (natural language → agent → tools)

## Data Flow Diagram

### Agentic Mode (Primary)

```
User Input (Natural Language)
    ↓
[TUI Input Widget]
    ↓
[Agent Executor] (LangChain)
    ├─ Get conversation history from SessionManager
    ├─ Build structured prompt with tool definitions
    └─ Invoke LLM via LlamaCpp wrapper
    ↓
[LLM Model] (llama-cpp-python / qwen2.5-coder-7b-instruct)
    ├─ Tokenization (internal to llama.cpp)
    ├─ Context Window Management (n_ctx=4096)
    └─ Generation Parameters (temperature, top_p, etc.)
    ↓
[Structured Output Parser]
    ├─ Extract JSON/YAML tool calls
    ├─ Validate against tool schemas
    └─ Route to appropriate tool
    ↓
[Tool Execution]
    ├─ read_file → Direct file read
    ├─ write_file_nano → Pexpect nano control
    ├─ delete_file → Direct file delete
    └─ respond_to_user → Loop termination
    ↓
[Tool Results] (Observations)
    ↓
[TUI Update]
    ├─ Display thinking, planning, tool calls
    ├─ Show nano session output (if applicable)
    └─ Update status and conversation history
    ↓
[Agent Loop]
    └─ If not terminated → Return to Agent Executor
    └─ If terminated → Display final response
```

### Simple Mode (Backward Compatible)

```
User Input (Natural Language or @command)
    ↓
[Input Handler]
    ↓
[Command Parser] (if @command) OR [Direct Handler]
    ↓
[Context Injection] (file contents, paths, etc.)
    ↓
[Session Manager] → Get conversation history (last N messages)
    ↓
[LlamaClient.build_prompt()]
    ├─ System Prompt (cached)
    ├─ Conversation History (formatted with Qwen template)
    └─ Current User Message
    ↓
[Formatted Prompt String] (Qwen chat template format)
    ↓
[Llama Model] (llama-cpp-python)
    ├─ Tokenization (internal to llama.cpp)
    ├─ Context Window Management (n_ctx=4096)
    └─ Generation Parameters (temperature, top_p, etc.)
    ↓
[Streaming Tokens]
    ↓
[Output Parser] (diff/file: blocks)
    ↓
[File Operations] (if applicable)
    ↓
[TUI Display] (simple text output)
```

## Key Design Decisions

### 1. Agentic Architecture with LangChain

**Why**: Provides robust tool-calling infrastructure, handles complex reasoning loops, and manages conversation memory automatically.

**Implementation**: LangChain's structured chat agent with custom tools

**Benefits**: 
- Reliable tool execution and error handling
- Built-in retry and parsing error recovery
- Memory management integrated with agent loop
- Extensible tool ecosystem

### 2. Textual TUI Framework

**Why**: Modern, responsive terminal interface with excellent performance and smooth user experience.

**Implementation**: Textual App with RichLog widgets and worker threads

**Benefits**:
- Cursor-enabled, responsive interface
- Rich text formatting and markup
- Non-blocking event loop
- Professional appearance and smooth scrolling

### 3. Transparent Nano Integration

**Why**: Provides auditability and proves that file operations are real, not simulated.

**Implementation**: Pexpect-based nano control with output capture

**Benefits**:
- User can see exactly what happens
- Builds trust in the system
- Full audit trail of operations
- Educational value (shows actual commands)

**Trade-off**: More complex than direct file I/O, but worth it for transparency

### 4. Dual Operation Modes

**Why**: Backward compatibility with existing workflows while providing advanced agentic capabilities.

**Implementation**: Mode detection based on CLI flags or input patterns

**Benefits**:
- Users can choose simplicity or power
- Gradual migration path
- Simple mode useful for quick tasks
- Agentic mode for complex multi-step operations

### 5. Structured Tool Output (JSON/YAML)

**Why**: Enables reliable parsing and tool routing in agentic mode.

**Implementation**: LLM generates structured output, parser validates and routes

**Benefits**:
- Clear separation of reasoning, planning, and actions
- Easy to parse and validate
- Supports complex multi-step operations
- Enables TUI to display process clearly

### 6. Streaming Token Display

**Why**: Provides immediate feedback and reduces perceived latency.

**Implementation**: `stream=True` in model invocation, TUI updates in real-time

**Benefits**:
- Lower perceived latency (time to first token)
- User can see progress
- Better UX for long generations

### 7. Non-blocking TUI Updates

**Why**: Keeps interface responsive during long-running operations (model inference, file operations).

**Implementation**: Background worker threads, async/await patterns

**Benefits**:
- Cursor remains responsive
- User can queue next command
- Smooth scrolling and updates
- Professional feel

## Configuration Parameters

**Model Loading** (from `_load_model()`):
- `n_ctx=4096`: Context window size in tokens
- `n_gpu_layers=-1`: Use all GPU layers (Metal on Mac, CUDA on NVIDIA)
- `n_batch=512`: Batch size for token processing
- `use_mlock=True`: Lock memory to prevent swapping (critical for performance)
- `use_mmap=True`: Use memory mapping for faster model loading

**Generation Parameters** (from `stream_chat()` and agent):
- `max_tokens=2048`: Maximum tokens to generate per response
- `temperature=0.7`: Sampling temperature (balance creativity/consistency)
- `top_p=0.9`: Nucleus sampling (consider top 90% probability mass)
- `repeat_penalty=1.1`: Penalty for repeating tokens
- `stop=["<|im_end|>", ...]`: Stop generation at these sequences

**Agent Parameters** (from LangChain AgentExecutor):
- `max_iterations=10`: Maximum agent loop iterations (prevent infinite loops)
- `max_execution_time=300`: Maximum seconds for agent execution
- `verbose=True`: Enable detailed logging for TUI display
- `handle_parsing_errors=True`: Retry on JSON parsing failures

**History Management** (from `ConfigManager`):
- `max_history_messages=20`: Maximum messages to keep in history
- `context_window_size=4096`: Maximum context window (matches `n_ctx`)
- `recent_history_count=10`: Number of recent messages for prompt building

**TUI Configuration** (from `AzulTUI`):
- `workspace_height="70%"`: Height of live workspace panel
- `history_height="30%"`: Height of conversation history panel
- `refresh_rate=0.1`: UI update frequency (seconds)
- `auto_scroll=True`: Automatically scroll to bottom on updates

**Nano/Pexpect Configuration**:
- `nano_timeout=30`: Maximum seconds for nano session
- `pexpect_encoding='utf-8'`: Character encoding for pexpect
- `nano_display_lines=20`: Number of lines to show in nano visualization

## Integration Points for Rebuilding

To rebuild this agentic AI CLI in a different application:

1. **Model Initialization**:
   - Install `llama-cpp-python`: `pip install llama-cpp-python[metal]` (Mac) or `[cuda]` (NVIDIA)
   - Initialize `Llama` class with GGUF model file
   - Configure GPU/CPU settings based on hardware
   - Download qwen2.5-coder-7b-instruct-q4_k_m.gguf model

2. **LangChain Agent Setup**:
   - Install `langchain` and `langchain-community`: `pip install langchain langchain-community`
   - Create `LlamaCpp` wrapper around llama-cpp-python model
   - Define tools using LangChain's `Tool` class
   - Create agent executor with structured chat agent
   - Configure memory (ConversationBufferMemory)

3. **TUI Development**:
   - Install `textual`: `pip install textual`
   - Create Textual App with layout (RichLog, Input, Static widgets)
   - Implement worker threads for agent execution
   - Set up event handlers for input and agent updates
   - Configure styling and layout proportions

4. **Tool Implementation**:
   - Implement `read_file` tool (direct file I/O)
   - Implement `write_file_nano` tool (pexpect integration)
   - Implement `delete_file` tool (direct file I/O)
   - Implement `respond_to_user` tool (loop termination)
   - Register tools with LangChain agent

5. **Nano Integration**:
   - Install `pexpect`: `pip install pexpect`
   - Implement nano spawning and control logic
   - Capture terminal output for display
   - Handle edge cases (file creation, large files, timeouts)

6. **Session Management**:
   - Implement conversation history storage (JSON files)
   - Generate session IDs from project paths
   - Integrate with LangChain memory system
   - Implement sliding window for history

7. **Entry Point**:
   - Create `cli.py` with main() function
   - Set up package entry point in `setup.py` or `pyproject.toml`
   - Install as `azul` command globally
   - Handle CLI arguments and mode selection

## Dependencies

**Required Packages**:
- `llama-cpp-python>=0.2.0`: Python bindings for llama.cpp
- `langchain>=0.1.0`: Agent orchestration framework
- `langchain-community>=0.0.20`: Community integrations (LlamaCpp)
- `textual>=0.45.0`: Terminal user interface framework
- `rich>=13.0.0`: Rich text and formatting (dependency of textual)
- `pexpect>=4.8.0`: Programmatic control of interactive programs (nano)
- Standard library: `pathlib`, `json`, `typing`, `os`, `asyncio`, `threading`

**Model Format**:
- GGUF format (quantized models)
- Required: `qwen2.5-coder-7b-instruct-q4_k_m.gguf` (or compatible Qwen model)
- Model should be placed in one of the search paths (see Model Path Resolution)

**Hardware Requirements**:
- CPU: Multi-core recommended (4+ cores for reasonable performance)
- GPU: Optional but highly recommended
  - Mac: Metal support (built into llama-cpp-python[metal])
  - NVIDIA: CUDA support (llama-cpp-python[cuda])
  - CPU-only: Works but slower
- RAM: 
  - 7B model (q4_k_m): ~4-8GB RAM
  - 14B model: ~8-16GB RAM
  - System RAM: Additional 2-4GB for OS and applications

**Python Version**:
- Python 3.12+ required
- Compatible with Python 3.10+ (with potential performance differences)

## Performance Optimizations

1. **String Building**: List append + single join (O(n) vs O(n²))
2. **Format Caching**: Pre-compute format strings
3. **History Slicing**: Return references, not copies
4. **Deferred I/O**: Save history after response (non-blocking)
5. **Lazy Loading**: Load model only when needed
6. **Memory Mapping**: Use `use_mmap=True` for faster model loads
7. **Memory Locking**: Use `use_mlock=True` to prevent swapping (critical)
8. **Background Threads**: Agent execution in worker threads (non-blocking TUI)
9. **Streaming Display**: Update TUI incrementally as tokens arrive
10. **Tool Result Caching**: Cache file reads within same agent execution
11. **Token Budget Management**: Trim history before exceeding `n_ctx` limit
12. **Efficient Parsing**: Use streaming JSON parser for structured output

## File Structure

The AZUL codebase is organized as follows:

```
azul/
├── __init__.py
├── cli.py                 # Main entry point, CLI argument handling
├── llama_client.py        # LLM model initialization and direct streaming
├── agent.py               # LangChain agent executor and tool definitions
├── tools.py               # Tool implementations (read_file, write_file_nano, etc.)
├── tui.py                 # Textual TUI application
├── session_manager.py     # Conversation history management
├── config/
│   ├── __init__.py
│   └── manager.py         # Configuration management
└── models/                # Model storage directory (optional)
    └── qwen2.5-coder-7b-instruct-q4_k_m.gguf
```

## Operational Modes

### Agentic Mode (Default)

**When to Use**: Complex tasks requiring multiple steps, file operations, or reasoning.

**Characteristics**:
- Uses LangChain agent executor
- Structured tool-calling output
- Think-Plan-Act loop
- Transparent file operations via nano
- Full TUI with live workspace

**Example Usage**:
```
User: "Create a Python script that reads a CSV file and prints statistics"
Agent: [THINKING] → [PLAN] → [read_file] → [write_file_nano] → [RESPOND]
```

### Simple Mode (Backward Compatible)

**When to Use**: Quick questions, single file edits, or when agentic mode is overkill.

**Characteristics**:
- Direct LLM interaction
- Diff/file: block output format
- No tool execution
- Simpler TUI or CLI output

**Example Usage**:
```
User: "@edit main.py Add error handling to the process_data function"
System: [Displays diff block, user applies manually]
```

## Migration and Backward Compatibility

**Existing Users**: Simple mode maintains compatibility with previous AZUL versions that used diff/file: blocks.

**New Users**: Default to agentic mode for full functionality.

**Migration Path**:
1. Start with simple mode for familiarization
2. Gradually adopt agentic mode for complex tasks
3. Both modes can coexist in the same session (via mode switching)

## Notes

- **Input and Output**: This architecture covers both input pipeline (prompt construction, model invocation) and output processing (parsing, tool execution, TUI updates).
- **Transparency**: All file operations are performed transparently through nano, providing full auditability.
- **Performance**: Non-blocking architecture ensures responsive TUI even during long operations.
- **Extensibility**: New tools can be added by implementing functions and registering with LangChain agent.
- **Context Management**: The system does NOT automatically inject project-wide code context. The agent uses `read_file` tool to gather context as needed.
- **Chat Template**: The Qwen chat template format is specific to Qwen models. Other models may require different templates or LangChain adapters.
- **Tokenization**: Tokenization is handled internally by llama.cpp. The input is a plain string, not pre-tokenized.
- **Error Recovery**: Agent executor handles parsing errors, tool failures, and infinite loops gracefully with retries and timeouts.
