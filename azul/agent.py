"""Agent executor for AZUL using LangChain 1.0.x with LangGraph."""

from typing import Optional, Callable, Dict, Any, List, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from langchain_core.language_models import BaseLanguageModel

try:
    from langchain_core.tools import Tool
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
    from langgraph.prebuilt import create_react_agent
    from langgraph.graph import StateGraph, END
    from langchain_core.runnables import RunnableConfig, Runnable
    LANGCHAIN_AVAILABLE = True
except ImportError as e:
    LANGCHAIN_AVAILABLE = False
    print(f"Warning: LangChain imports failed: {e}")
    print("Install with: pip install langchain langchain-community langgraph")

from azul.tools import (
    read_file_tool,
    write_file_nano_tool,
    delete_file_tool,
    respond_to_user_tool,
    set_nano_callback,
)
from azul.llama_client import LlamaClient


# Agentic mode system prompt
AGENTIC_SYSTEM_PROMPT = """You are AZUL, an autonomous AI coding assistant that operates within a CLI. You fulfill user requests by reasoning, planning, and executing file operations using available tools.

AVAILABLE TOOLS:

1. read_file(file_path: str) -> str
   - Reads the content of a file and returns it as a string.
   - Use this to understand existing code before making changes.
   - Example: read_file("src/main.py")

2. write_file_nano(file_path: str, new_content: str) -> str
   - Creates or overwrites a file with new content using the nano editor.
   - This tool performs actual file operations transparently.
   - Example: write_file_nano("main.py", "print('Hello')\\n")

3. delete_file(file_path: str) -> str
   - Deletes a file from the filesystem.
   - Use with caution and only when explicitly requested.
   - Example: delete_file("old_file.py")

4. respond_to_user(message: str) -> str
   - Sends a message to the user and terminates the agent loop.
   - Use this when the task is complete or if you need clarification.
   - Example: respond_to_user("I've created the file as requested.")

WORKFLOW:
For every user request, follow this process:
1. THINK: Analyze the user's request and determine what needs to be done
2. PLAN: List the sequence of tool calls needed to accomplish the task
3. ACT: Execute tools one by one, using the results to inform next steps
4. RESPOND: When complete, use respond_to_user() to communicate the result

Be concise, precise, and code-focused in your responses."""


class LlamaCppLangChainWrapper(Runnable):
    """Wrapper to make LlamaClient compatible with LangChain LLM interface."""
    
    def __init__(self, llama_client: LlamaClient):
        """Initialize wrapper.
        
        Args:
            llama_client: Instance of LlamaClient
        """
        super().__init__()
        self.llama_client = llama_client
        self._llm_type = "llama_cpp"
        self._bound_tools = None  # Store bound tools
    
    def bind_tools(self, tools: List[Tool], **kwargs):
        """Bind tools to the LLM (required by LangGraph).
        
        Args:
            tools: List of Tool objects to bind
            **kwargs: Additional arguments
            
        Returns:
            Self with tools bound (for chaining)
        """
        self._bound_tools = tools
        return self
    
    def invoke(self, messages: List[BaseMessage], config: Optional[RunnableConfig] = None, **kwargs) -> BaseMessage:
        """Invoke the LLM with messages.
        
        Args:
            messages: List of LangChain message objects
            config: Optional runnable config
            **kwargs: Additional arguments
            
        Returns:
            AIMessage with the response
        """
        # Convert LangChain messages to our format
        conversation_history = []
        user_message = ""
        
        for msg in messages:
            if isinstance(msg, SystemMessage):
                # System message is handled separately
                continue
            elif isinstance(msg, HumanMessage):
                user_message = msg.content
            elif isinstance(msg, AIMessage):
                conversation_history.append({"role": "assistant", "content": msg.content})
        
        # Get system prompt from first SystemMessage if present
        system_prompt = None
        for msg in messages:
            if isinstance(msg, SystemMessage):
                system_prompt = msg.content
                break
        
        # If tools are bound, include tool descriptions in system prompt
        if self._bound_tools:
            tool_descriptions = "\n".join([f"- {tool.name}: {tool.description}" for tool in self._bound_tools])
            if system_prompt:
                system_prompt = f"{system_prompt}\n\nAvailable tools:\n{tool_descriptions}"
            else:
                system_prompt = f"Available tools:\n{tool_descriptions}"
        
        # Generate response using our LlamaClient
        response = self.llama_client.chat(
            user_message=user_message,
            conversation_history=conversation_history if conversation_history else None,
            system_prompt=system_prompt or AGENTIC_SYSTEM_PROMPT,
            max_tokens=kwargs.get("max_tokens", 2048),
            temperature=kwargs.get("temperature", 0.7),
            top_p=kwargs.get("top_p", 0.9),
            repeat_penalty=kwargs.get("repeat_penalty", 1.1),
        )
        
        return AIMessage(content=response)
    
    def stream(self, messages: List[BaseMessage], config: Optional[RunnableConfig] = None, **kwargs):
        """Stream responses from the LLM.
        
        Args:
            messages: List of LangChain message objects
            config: Optional runnable config
            **kwargs: Additional arguments
            
        Yields:
            AIMessage chunks
        """
        # Convert messages
        conversation_history = []
        user_message = ""
        system_prompt = None
        
        for msg in messages:
            if isinstance(msg, SystemMessage):
                system_prompt = msg.content
            elif isinstance(msg, HumanMessage):
                user_message = msg.content
            elif isinstance(msg, AIMessage):
                conversation_history.append({"role": "assistant", "content": msg.content})
        
        # If tools are bound, include tool descriptions
        if self._bound_tools:
            tool_descriptions = "\n".join([f"- {tool.name}: {tool.description}" for tool in self._bound_tools])
            if system_prompt:
                system_prompt = f"{system_prompt}\n\nAvailable tools:\n{tool_descriptions}"
            else:
                system_prompt = f"Available tools:\n{tool_descriptions}"
        
        # Stream response
        for token in self.llama_client.stream_chat(
            user_message=user_message,
            conversation_history=conversation_history if conversation_history else None,
            system_prompt=system_prompt or AGENTIC_SYSTEM_PROMPT,
            max_tokens=kwargs.get("max_tokens", 2048),
            temperature=kwargs.get("temperature", 0.7),
            top_p=kwargs.get("top_p", 0.9),
            repeat_penalty=kwargs.get("repeat_penalty", 1.1),
        ):
            yield AIMessage(content=token)


class AzulAgent:
    """Agent executor for AZUL using LangChain 1.0.x with LangGraph."""
    
    def __init__(
        self,
        model_path: Path,
        n_ctx: int = 4096,
        n_gpu_layers: int = -1,
        max_iterations: int = 10,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        callbacks: Optional[Dict[str, Callable]] = None,
    ):
        """Initialize AZUL agent.
        
        Args:
            model_path: Path to GGUF model file
            n_ctx: Context window size
            n_gpu_layers: Number of GPU layers (-1 for all)
            max_iterations: Maximum agent loop iterations
            conversation_history: Previous conversation history
            callbacks: Dictionary of callback functions:
                - 'thinking': Called with thinking text
                - 'tool_call': Called with tool name and args
                - 'observation': Called with tool result
                - 'nano_output': Called with nano session output
        """
        if not LANGCHAIN_AVAILABLE:
            raise ImportError("LangChain is required for agentic mode. Install with: pip install langchain langchain-community langgraph")
        
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.max_iterations = max_iterations
        self.callbacks = callbacks or {}
        
        # Set up nano callback
        if 'nano_output' in self.callbacks:
            set_nano_callback(self.callbacks['nano_output'])
        
        # Initialize our LlamaClient
        self.llama_client = LlamaClient(
            model_path=model_path,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
        )
        
        # Wrap it for LangChain
        self.llm = LlamaCppLangChainWrapper(self.llama_client)
        
        # Define tools
        self.tools = [
            Tool(
                name="read_file",
                func=read_file_tool,
                description="Reads the content of a file and returns it as a string. Use this to understand existing code before making changes. Example: read_file('src/main.py')"
            ),
            Tool(
                name="write_file_nano",
                func=self._write_file_nano_with_callback,
                description="Creates or overwrites a file with new content using the nano editor. This tool performs actual file operations transparently. Example: write_file_nano('main.py', 'print(\"Hello\")\\n')"
            ),
            Tool(
                name="delete_file",
                func=delete_file_tool,
                description="Deletes a file from the filesystem. Use with caution and only when explicitly requested. Example: delete_file('old_file.py')"
            ),
            Tool(
                name="respond_to_user",
                func=respond_to_user_tool,
                description="Sends a message to the user and terminates the agent loop. Use this when the task is complete or if you need clarification. Example: respond_to_user('I've created the file as requested.')"
            ),
        ]
        
        # Create agent using LangGraph
        try:
            # Bind tools to LLM first (required by create_react_agent)
            llm_with_tools = self.llm.bind_tools(self.tools)
            
            # Use create_react_agent from LangGraph
            # Note: system prompt is passed via messages, not as a parameter
            self.agent_executor = create_react_agent(
                llm_with_tools,
                self.tools,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to create agent: {e}. Please ensure LangGraph is properly installed.")
        
        # Store conversation history
        self.conversation_history = conversation_history or []
    
    def _write_file_nano_with_callback(self, file_path: str, new_content: str) -> str:
        """Wrapper for write_file_nano that triggers callbacks."""
        # Trigger tool_call callback
        if 'tool_call' in self.callbacks:
            self.callbacks['tool_call'](f"write_file_nano({file_path})")
        
        result = write_file_nano_tool(file_path, new_content)
        
        # Trigger observation callback
        if 'observation' in self.callbacks:
            self.callbacks['observation'](result)
        
        return result
    
    def execute(self, user_input: str) -> str:
        """Execute agent with user input.
        
        Args:
            user_input: User's request/instruction
            
        Returns:
            Final response from agent
        """
        try:
            # Trigger thinking callback
            if 'thinking' in self.callbacks:
                self.callbacks['thinking'](f"Processing: {user_input}")
            
            # Build messages from conversation history and current input
            messages = [SystemMessage(content=AGENTIC_SYSTEM_PROMPT)]
            
            # Add conversation history
            for msg in self.conversation_history[-10:]:  # Last 10 messages
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))
            
            # Add current user input
            messages.append(HumanMessage(content=user_input))
            
            # Execute agent
            # LangGraph agents use invoke with messages
            result = self.agent_executor.invoke({"messages": messages})
            
            # Extract response from result
            if isinstance(result, dict):
                # Get the last AI message
                output_messages = result.get("messages", [])
                ai_messages = [msg for msg in output_messages if isinstance(msg, AIMessage)]
                if ai_messages:
                    output = ai_messages[-1].content
                else:
                    output = str(result)
            else:
                output = str(result)
            
            # Check if response indicates termination
            if isinstance(output, str) and output.startswith("RESPOND: "):
                output = output[9:]  # Remove "RESPOND: " prefix
            
            return str(output)
        
        except Exception as e:
            error_msg = f"Error in agent execution: {str(e)}"
            if 'observation' in self.callbacks:
                self.callbacks['observation'](error_msg)
            return error_msg
    
    def get_memory(self):
        """Get conversation memory (for compatibility)."""
        return self.conversation_history
