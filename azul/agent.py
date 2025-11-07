"""LangChain/LangGraph agent integration."""

import re
from pathlib import Path
from typing import Callable, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import Tool

from azul.llama_client import LlamaClient
from azul.tools import (
    delete_file_tool,
    list_directory_tool,
    read_file_tool,
    respond_to_user_tool,
    write_file_nano_tool,
)


class LlamaCppLangChainWrapper(Runnable):
    """Wrapper to make LlamaClient compatible with LangChain."""
    
    def __init__(
        self,
        llama_client: LlamaClient,
        system_prompt: Optional[str] = None
    ):
        self.llama_client = llama_client
        self.system_prompt = system_prompt
    
    def invoke(
        self,
        input: List[BaseMessage],
        config: Optional[Dict] = None
    ) -> AIMessage:
        """Invoke the model with messages."""
        # Convert LangChain messages to dict format
        messages = []
        for msg in input:
            if isinstance(msg, SystemMessage):
                messages.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                messages.append({"role": "assistant", "content": msg.content})
        
        # Get the last user message
        user_message = messages[-1]["content"] if messages else ""
        
        # Get conversation history (excluding last message)
        history = messages[:-1] if len(messages) > 1 else []
        
        # Generate response
        response = self.llama_client.chat(
            user_message=user_message,
            conversation_history=history,
            system_prompt=self.system_prompt
        )
        
        return AIMessage(content=response)
    
    def stream(
        self,
        input: List[BaseMessage],
        config: Optional[Dict] = None
    ):
        """Stream response tokens."""
        # Convert LangChain messages to dict format
        messages = []
        for msg in input:
            if isinstance(msg, SystemMessage):
                messages.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                messages.append({"role": "assistant", "content": msg.content})
        
        # Get the last user message
        user_message = messages[-1]["content"] if messages else ""
        
        # Get conversation history (excluding last message)
        history = messages[:-1] if len(messages) > 1 else []
        
        # Stream response
        full_response = ""
        for token in self.llama_client.stream_chat(
            user_message=user_message,
            conversation_history=history,
            system_prompt=self.system_prompt
        ):
            full_response += token
            yield AIMessage(content=token)
        
        # Yield final message
        yield AIMessage(content=full_response)
    
    def bind_tools(self, tools: List[Tool]) -> "LlamaCppLangChainWrapper":
        """Bind tools to the model (for compatibility, tools handled separately)."""
        return self


class AzulAgent:
    """Main agent executor using LangGraph ReAct pattern."""
    
    SYSTEM_PROMPT = """You are AZUL, an autonomous AI coding assistant that operates within a CLI.

AVAILABLE TOOLS:
1. list_directory(directory_path: str) -> str - List files and subdirectories in a directory (default: current directory). Use this to see directory contents, NOT read_file().
2. read_file(file_path: str) -> str - Read a file from the filesystem. Only works on files, not directories.
3. write_file_nano(file_path: str, new_content: str) -> str - Create or overwrite a file
4. delete_file(file_path: str) -> str - Delete a file from the filesystem
5. respond_to_user(message: str) -> str - Signal completion and respond to the user

IMPORTANT:
- Use list_directory() to see what's in a directory, NOT read_file()
- read_file() only works on files, not directories
- If a tool returns an error, analyze the error and try a different approach
- Always acknowledge when a tool fails and explain what went wrong

WORKFLOW:
1. THINK: Analyze the user's request
2. PLAN: List the sequence of tool calls needed
3. ACT: Execute tools one by one
4. OBSERVE: Check tool results - if there's an error, reconsider your approach
5. RESPOND: Use respond_to_user() when complete

Always use respond_to_user() when you have completed the task."""
    
    def __init__(
        self,
        model_path: Path,
        n_ctx: int = 8192,
        n_gpu_layers: int = -1,
        max_iterations: int = 50,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        callbacks: Optional[Dict[str, Callable]] = None
    ):
        self.llama_client = LlamaClient(
            model_path=model_path,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers
        )
        self.max_iterations = max_iterations
        self.conversation_history = conversation_history or []
        self.callbacks = callbacks or {}
        
        # Create tools
        self.tools = [
            Tool(
                name="list_directory",
                func=list_directory_tool,
                description="List files and subdirectories in a directory. Use this to see directory contents, not read_file(). Defaults to current directory if no path provided."
            ),
            Tool(
                name="read_file",
                func=read_file_tool,
                description="Read a file from the filesystem. Returns file content or error message. Only works on files, not directories."
            ),
            Tool(
                name="write_file_nano",
                func=write_file_nano_tool,
                description="Create or overwrite a file with new content. Returns success or error message."
            ),
            Tool(
                name="delete_file",
                func=delete_file_tool,
                description="Delete a file from the filesystem. Returns success or error message."
            ),
            Tool(
                name="respond_to_user",
                func=respond_to_user_tool,
                description="Signal that you have completed the task and provide a response to the user. Always call this when done."
            )
        ]
        
        # Create model wrapper (for potential future use)
        self.model = LlamaCppLangChainWrapper(
            llama_client=self.llama_client,
            system_prompt=self.SYSTEM_PROMPT
        )
        
        self.executor = ThreadPoolExecutor(max_workers=1)
    
    def _execute_tool(self, tool_name: str, args: List[str]) -> str:
        """Execute a tool by name."""
        tool_map = {
            "list_directory": list_directory_tool,
            "read_file": read_file_tool,
            "write_file_nano": write_file_nano_tool,
            "delete_file": delete_file_tool,
            "respond_to_user": respond_to_user_tool,
        }
        
        if tool_name not in tool_map:
            return f"Error: Unknown tool: {tool_name}"
        
        tool_func = tool_map[tool_name]
        
        try:
            # Call tool with arguments
            if len(args) == 0:
                result = tool_func()
            elif len(args) == 1:
                result = tool_func(args[0])
            elif len(args) == 2:
                result = tool_func(args[0], args[1])
            else:
                result = tool_func(*args)
            
            return str(result)
        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"
    
    def _parse_tool_calls(self, content: str) -> List[Dict]:
        """Parse tool calls from model response."""
        tool_calls = []
        
        # Look for patterns like: tool_name('arg1', 'arg2')
        # Or: ACTION: tool_name('arg1', 'arg2')
        patterns = [
            r"ACTION:\s*(\w+)\(([^)]+)\)",
            r"(\w+)\(([^)]+)\)",
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                tool_name = match.group(1)
                args_str = match.group(2)
                
                # Skip if it's not one of our tools
                if tool_name not in [tool.name for tool in self.tools]:
                    continue
                
                # Parse arguments (simple: split by comma, strip quotes)
                args = []
                if args_str.strip():
                    # Try to parse as JSON-like or simple string args
                    parts = args_str.split(",")
                    for part in parts:
                        part = part.strip()
                        # Remove quotes
                        if part.startswith('"') and part.endswith('"'):
                            args.append(part[1:-1])
                        elif part.startswith("'") and part.endswith("'"):
                            args.append(part[1:-1])
                        else:
                            args.append(part)
                
                tool_calls.append({
                    "name": tool_name,
                    "args": args,
                    "id": f"call_{len(tool_calls)}"
                })
        
        return tool_calls
    
    def _trigger_callback(self, callback_name: str, message: str) -> None:
        """Trigger a callback if it exists."""
        if callback_name in self.callbacks:
            try:
                self.callbacks[callback_name](message)
            except Exception:
                pass  # Don't crash on callback errors
    
    def execute(self, user_input: str) -> str:
        """Execute the agent with user input using ReAct pattern with streaming."""
        try:
            # Trigger thinking callback
            self._trigger_callback("thinking", f"Analyzing request: {user_input}")
            
            # Build conversation context
            conversation_context = []
            for msg in self.conversation_history[-10:]:  # Last 10 messages
                conversation_context.append(msg)
            
            # Add current user message
            conversation_context.append({"role": "user", "content": user_input})
            
            # ReAct loop
            iteration = 0
            observations = []
            
            while iteration < self.max_iterations:
                # Build prompt with tool descriptions
                tool_descriptions = "\n".join([
                    f"- {tool.name}: {tool.description}"
                    for tool in self.tools
                ])
                
                # Build context with observations
                context_parts = []
                for msg in conversation_context:
                    context_parts.append(f"{msg['role'].upper()}: {msg['content']}")
                
                if observations:
                    context_parts.append("\nOBSERVATIONS:")
                    for obs in observations[-3:]:  # Last 3 observations
                        context_parts.append(f"- {obs}")
                
                context = "\n".join(context_parts)
                
                # Create prompt
                prompt = f"""You are AZUL, an autonomous AI coding assistant.

AVAILABLE TOOLS:
{tool_descriptions}

CONVERSATION:
{context}

Think step by step. Use tools when needed. When done, use respond_to_user(message) to respond.

Your response:"""
                
                # Check if we have streaming callback
                has_streaming = "thinking_stream" in self.callbacks
                
                if has_streaming:
                    # Stream response
                    if "start_generation" in self.callbacks:
                        self.callbacks["start_generation"]()
                    
                    full_response = ""
                    for token in self.llama_client.stream_chat(
                        user_message=prompt,
                        conversation_history=[],
                        system_prompt=self.SYSTEM_PROMPT,
                        max_tokens=2048,
                        temperature=0.7
                    ):
                        full_response += token
                        self._trigger_callback("thinking_stream", token)
                    
                    response = full_response
                else:
                    # Non-streaming fallback
                    response = self.llama_client.chat(
                        user_message=prompt,
                        conversation_history=[],
                        system_prompt=self.SYSTEM_PROMPT,
                        max_tokens=2048,
                        temperature=0.7
                    )
                
                # Parse response for tool calls
                tool_calls = self._parse_tool_calls(response)
                
                if tool_calls:
                    # Execute tools
                    for tool_call in tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]
                        
                        # Trigger callback
                        args_str = ", ".join([f"'{arg}'" if isinstance(arg, str) else str(arg) for arg in tool_args])
                        self._trigger_callback("tool_call", f"{tool_name}({args_str})")
                        
                        # Execute tool
                        result = self._execute_tool(tool_name, tool_args)
                        
                        # Trigger observation callback
                        self._trigger_callback("observation", result)
                        
                        # Check for errors in tool result
                        if result.startswith("Error:"):
                            # Add error to observations with emphasis
                            observations.append(f"ERROR from {tool_name}: {result}")
                            # Don't continue if it's respond_to_user (shouldn't error, but handle gracefully)
                            if tool_name == "respond_to_user":
                                return f"Error: {result}"
                        else:
                            # Check if it's respond_to_user
                            if tool_name == "respond_to_user" and "RESPOND:" in result:
                                return result.split("RESPOND:", 1)[1].strip()
                            
                            # Add successful observation
                            observations.append(f"{tool_name} result: {result}")
                
                # Check if response contains final answer
                if "RESPOND:" in response:
                    return response.split("RESPOND:", 1)[1].strip()
                
                # Check if model says it's done
                if "respond_to_user" in response.lower() or "task complete" in response.lower():
                    # Try to extract final message
                    lines = response.split("\n")
                    for line in reversed(lines):
                        if line.strip() and not line.strip().startswith("THINK") and not line.strip().startswith("PLAN"):
                            return line.strip()
                
                iteration += 1
                
                # If no tool calls and we have a response, return it
                if not tool_calls and response.strip():
                    # Check if it looks like a final response
                    if len(response) > 20 and not any(tool.name in response for tool in self.tools):
                        return response.strip()
            
            # Max iterations reached
            return "Task completed (max iterations reached)."
        
        except KeyboardInterrupt:
            raise  # Re-raise to be handled by CLI
        except Exception as e:
            return f"Error: {str(e)}"

