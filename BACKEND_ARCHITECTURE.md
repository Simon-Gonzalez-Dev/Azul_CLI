# AZUL Backend Architecture

## Overview

This document describes the backend architecture for AZUL, an agentic AI coding assistant. The backend is designed to support a minimalist TUI frontend that displays real-time agent reasoning, tool execution, and responses.

## Core Philosophy

- **Agentic Loop**: Think → Plan → Act → Observe → Respond
- **Real-time Feedback**: All agent steps are exposed via callbacks
- **Tool Transparency**: Every tool execution is logged and visible
- **Local-First**: Runs entirely on local hardware using llama-cpp-python
- **Modular Design**: Clean separation between LLM, agent logic, and tools

## Required Libraries

### Core Dependencies

```python
# LLM Inference
llama-cpp-python>=0.2.0  # Local LLM inference engine

# Agent Framework
langchain>=0.1.0          # Core LangChain abstractions
langchain-core>=0.1.0     # Core message types and runnables
langgraph>=0.0.20         # Agent execution graph
langchain-community>=0.0.20  # Community integrations

# Utilities
pathlib                  # Path handling (stdlib)
asyncio                  # Async execution (stdlib)
typing                   # Type hints (stdlib)
```

### Optional Dependencies

```python
pexpect>=4.8.0           # For transparent nano editor integration
```

## Architecture Components

### 1. LLM Client Layer (`llama_client.py`)

**Purpose**: Direct interface to llama-cpp-python for local model inference.

**Key Responsibilities**:
- Model loading and management
- Prompt formatting (Qwen chat template)
- Token generation (streaming and non-streaming)
- Context window management

**Core Interface**:

```python
class LlamaClient:
    def __init__(
        self,
        model_path: Path,
        n_ctx: int = 8192,        # Context window size
        n_gpu_layers: int = -1    # GPU acceleration
    )
    
    def chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
        top_p: float = 0.9,
        repeat_penalty: float = 1.1
    ) -> str
    
    def stream_chat(...) -> Generator[str, None, None]
```

**Design Decisions**:
- **Lazy Loading**: Model loads only when first used
- **High Token Limits**: 8192 max_tokens for complex multi-step tasks
- **Streaming Support**: Real-time token generation for responsive UI
- **Context Management**: Automatic history trimming to fit n_ctx

### 2. LangChain Integration Layer (`agent.py`)

**Purpose**: Bridge between llama-cpp-python and LangChain/LangGraph frameworks.

**Key Components**:

#### 2.1 LlamaCppLangChainWrapper

Wraps `LlamaClient` to make it compatible with LangChain's `BaseLanguageModel` interface.

```python
class LlamaCppLangChainWrapper(Runnable):
    def invoke(messages: List[BaseMessage], ...) -> AIMessage
    def stream(messages: List[BaseMessage], ...) -> Generator[AIMessage, None, None]
    def bind_tools(tools: List[Tool]) -> Self
```

**Key Features**:
- Converts LangChain messages to Qwen chat format
- Handles system prompts and tool descriptions
- Supports tool binding for agent execution
- Maintains conversation history

#### 2.2 AzulAgent

Main agent executor using LangGraph's ReAct agent pattern.

```python
class AzulAgent:
    def __init__(
        self,
        model_path: Path,
        n_ctx: int = 8192,
        n_gpu_layers: int = -1,
        max_iterations: int = 50,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        callbacks: Optional[Dict[str, Callable]] = None
    )
    
    def execute(user_input: str) -> str
```

**Agent Workflow**:

1. **Input Processing**
   - Receives user input
   - Triggers `thinking` callback: "Analyzing request: {input}"
   - Builds message history from conversation context

2. **Agent Execution**
   - Invokes LangGraph ReAct agent with messages
   - Agent autonomously decides tool usage
   - Each tool call triggers `tool_call` callback
   - Each tool result triggers `observation` callback

3. **Response Extraction**
   - Searches for final AI message with content
   - Handles tool call chains (especially `respond_to_user`)
   - Extracts tool results when needed
   - Returns meaningful response or fallback message

**Callback System**:

```python
callbacks = {
    'thinking': Callable[[str], None],      # Agent reasoning
    'tool_call': Callable[[str], None],     # Tool being called
    'observation': Callable[[str], None],    # Tool result
    'nano_output': Callable[[str], None]    # Nano editor output
}
```

**Design Decisions**:
- **High Iteration Limit**: 50 max_iterations for complex tasks
- **Callback-Driven**: All agent steps exposed for UI display
- **Robust Extraction**: Multiple strategies to find final response
- **Error Handling**: Graceful degradation with informative messages

### 3. Tool System (`tools.py`)

**Purpose**: File system operations that the agent can execute.

**Tool Architecture**:

Each tool is a simple Python function that:
- Takes typed parameters
- Performs real file operations
- Returns success/error messages
- Can trigger callbacks for UI updates

**Available Tools**:

#### 3.1 read_file

```python
def read_file_tool(file_path: str) -> str
```

**Functionality**:
- Reads file content from filesystem
- Returns content as string with metadata
- Handles errors (not found, permission denied)

**Use Case**: Agent reads existing code before making changes

#### 3.2 write_file_nano

```python
def write_file_nano_tool(file_path: str, new_content: str) -> str
```

**Functionality**:
- Creates or overwrites files
- Uses direct file I/O (fast and reliable)
- Optional nano integration for transparency
- Ensures directory structure exists

**Design Decision**: Direct I/O instead of actual nano editing for speed, but can show nano output for transparency

#### 3.3 delete_file

```python
def delete_file_tool(file_path: str) -> str
```

**Functionality**:
- Deletes files from filesystem
- Validates file existence and type
- Returns success/error messages

#### 3.4 respond_to_user

```python
def respond_to_user_tool(message: str) -> str
```

**Functionality**:
- Special tool that signals agent completion
- Returns "RESPOND: {message}" format
- Agent executor recognizes this and terminates loop

**Design Decision**: Explicit termination tool prevents infinite loops

**Tool Registration**:

Tools are registered with LangChain using the `Tool` class:

```python
Tool(
    name="tool_name",
    func=tool_function,
    description="Clear description for LLM"
)
```

**Key Features**:
- **Real Operations**: All tools perform actual filesystem operations
- **Error Handling**: Comprehensive error messages
- **Callback Integration**: Tools can trigger UI callbacks
- **Type Safety**: Clear parameter types for LLM understanding

### 4. System Prompt Engineering

**Purpose**: Guide the LLM to follow the Think-Plan-Act-Respond pattern.

**Core System Prompt**:

```
You are AZUL, an autonomous AI coding assistant that operates within a CLI.

AVAILABLE TOOLS:
1. read_file(file_path: str) -> str
2. write_file_nano(file_path: str, new_content: str) -> str
3. delete_file(file_path: str) -> str
4. respond_to_user(message: str) -> str

WORKFLOW:
1. THINK: Analyze the user's request
2. PLAN: List the sequence of tool calls needed
3. ACT: Execute tools one by one
4. RESPOND: Use respond_to_user() when complete
```

**Design Decisions**:
- **Explicit Workflow**: Clear Think-Plan-Act-Respond structure
- **Tool Descriptions**: Detailed tool documentation in prompt
- **Termination Signal**: `respond_to_user` tool for explicit completion
- **Concise Instructions**: Minimal but complete guidance

### 5. Agent Execution Flow

**Complete Flow Diagram**:

```
User Input
    ↓
[AzulAgent.execute()]
    ↓
Trigger 'thinking' callback
    ↓
Build message history
    ↓
[LangGraph ReAct Agent]
    ↓
    ├─→ LLM generates tool call
    │   ↓
    │   Trigger 'tool_call' callback
    │   ↓
    │   [Execute Tool]
    │   ↓
    │   Trigger 'observation' callback
    │   ↓
    │   LLM processes result
    │   ↓
    └─→ Loop until respond_to_user() called
    ↓
Extract final response
    ↓
Return to TUI
```

**Key Execution Details**:

1. **Non-Blocking**: Agent runs in executor thread
2. **Real-time Updates**: Callbacks fire during execution
3. **Iteration Control**: Max 50 iterations prevents infinite loops
4. **Response Extraction**: Multiple fallback strategies
5. **Error Recovery**: Exceptions caught and returned as error messages

### 6. Conversation Management

**Purpose**: Maintain context across multiple interactions.

**Storage Format**:

```python
conversation_history: List[Dict[str, str]] = [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
]
```

**Context Window Management**:
- Last 10 messages included in agent execution
- Full history stored in session manager
- Automatic trimming if approaching n_ctx limit

**Design Decisions**:
- **Recent Context**: Only last 10 messages for agent (reduces token usage)
- **Full History**: Complete history in session (for persistence)
- **Smart Trimming**: Preserve important context when trimming

### 7. Error Handling Strategy

**Three-Tier Error Handling**:

1. **Tool Level**: Tools return error messages as strings
2. **Agent Level**: Agent catches exceptions and returns error messages
3. **TUI Level**: TUI displays errors with "AZUL: Error: ..." format

**Error Types**:
- **File Not Found**: Clear message with file path
- **Permission Denied**: Security-aware error messages
- **Agent Timeout**: Max iterations reached
- **LLM Errors**: Model loading or generation failures
- **Tool Execution Errors**: Tool-specific error messages

### 8. Performance Optimizations

**Key Optimizations**:

1. **Lazy Model Loading**: Model loads only when needed
2. **GPU Acceleration**: n_gpu_layers=-1 uses all GPU layers
3. **Batch Processing**: n_batch=512 for efficient token generation
4. **Memory Mapping**: use_mmap=True for faster model loading
5. **Context Caching**: Conversation history cached in memory
6. **Async Execution**: Agent runs in executor, TUI stays responsive

**Resource Management**:
- Model unloads when not in use (optional)
- Context window sized appropriately (8192 tokens)
- Tool execution is synchronous but fast (file I/O)

### 9. Integration Points

**Frontend Integration**:

The backend exposes these integration points:

1. **Agent Initialization**:
   ```python
   agent = AzulAgent(
       model_path=model_path,
       n_ctx=8192,
       max_iterations=50,
       callbacks={
           'thinking': tui.on_thinking,
           'tool_call': tui.on_tool_call,
           'observation': tui.on_observation
       }
   )
   ```

2. **Execution**:
   ```python
   result = agent.execute(user_input)
   ```

3. **Callbacks**:
   - All callbacks fire during execution
   - TUI updates in real-time
   - Final result returned after completion

**Session Integration**:
- Conversation history passed to agent
- Agent updates history after execution
- Session manager persists to disk

## Data Flow

### Request Flow

```
TUI Input
    ↓
[Session Manager] → Add to history
    ↓
[AzulAgent.execute()]
    ↓
[LangGraph Agent] → Tool calls
    ↓
[Tools] → File operations
    ↓
[LangGraph Agent] → Process results
    ↓
[AzulAgent] → Extract response
    ↓
[Session Manager] → Save to history
    ↓
TUI Display
```

### Callback Flow

```
Agent Step
    ↓
Callback Triggered
    ↓
TUI Update
    ↓
User Sees Progress
```

## Configuration

**Key Configuration Parameters**:

```python
# Model Configuration
n_ctx = 8192              # Context window
n_gpu_layers = -1         # GPU acceleration
max_tokens = 8192         # Generation limit

# Agent Configuration
max_iterations = 50       # Agent loop limit
temperature = 0.7         # Creativity
top_p = 0.9              # Nucleus sampling
repeat_penalty = 1.1      # Repetition control

# Tool Configuration
enable_nano_transparency = True  # Show nano output
```

## Testing Strategy

**Unit Tests**:
- Tool functions (read, write, delete)
- LLM client (prompt formatting, generation)
- Agent response extraction

**Integration Tests**:
- Full agent execution with tools
- Callback system
- Error handling

**End-to-End Tests**:
- Complete user request → agent execution → response
- Multi-step operations
- Error scenarios

## Future Enhancements

**Potential Improvements**:

1. **Streaming Responses**: Stream final response tokens to TUI
2. **Tool Extensions**: Add more tools (grep, find, etc.)
3. **Plan Extraction**: Parse LLM output to extract explicit plans
4. **Parallel Tool Execution**: Execute independent tools in parallel
5. **Response Caching**: Cache common responses
6. **Model Switching**: Support multiple models
7. **Custom Tools**: Allow user-defined tools

## Summary

The AZUL backend architecture is designed for:

- **Clarity**: Clean separation of concerns
- **Transparency**: All agent steps exposed via callbacks
- **Reliability**: Robust error handling and response extraction
- **Performance**: Optimized for local execution
- **Extensibility**: Easy to add new tools and capabilities

The architecture supports the minimalist TUI frontend by providing:
- Real-time agent step visibility
- Clear tool execution logging
- Meaningful final responses
- Graceful error handling

All components work together to create a responsive, transparent, and powerful agentic coding assistant.

