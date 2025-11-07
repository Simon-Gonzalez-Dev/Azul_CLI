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
    get_current_path_tool,
    list_directory_tool,
    read_file_tool,
    respond_to_user_tool,
    set_permission_callback,
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
    
    SYSTEM_PROMPT = """You are AZUL, an autonomous AI coding assistant operating in a command-line interface. You have access to REAL tools that perform ACTUAL file system operations. You MUST use these tools - NEVER guess, assume, or hallucinate information.

**CRITICAL RULE: NEVER HALLUCINATE**
- If you don't know something, USE A TOOL to find out
- If asked about the current directory, use get_current_path()
- If asked what files exist, use list_directory()
- If you need to read a file, use read_file()
- NEVER make up paths, file names, or directory contents
- NEVER say "I don't have access" - you DO have access through tools

**YOUR AVAILABLE TOOLS (USE THESE):**

1. **get_current_path()**
   - Purpose: Get the absolute path of the current working directory
   - Usage: get_current_path()
   - Returns: The full path like "/Users/username/project"
   - When to use: When user asks "where am I", "current directory", "current path", etc.
   - Example: User asks "what's my current directory?" → Call get_current_path()

2. **list_directory(directory_path)**
   - Purpose: List all files and folders in a directory
   - Usage: list_directory('.') for current dir, or list_directory('path/to/dir')
   - Returns: A formatted list of files and folders
   - When to use: To see what files exist before reading them, or when user asks "what files are here"
   - Example: User asks "read the first file" → First call list_directory('.') to see files, then read_file()

3. **read_file(file_path)**
   - Purpose: Read the complete contents of a file
   - Usage: read_file('filename.txt') or read_file('path/to/file.txt')
   - Returns: File contents with metadata
   - When to use: When user wants to see file contents
   - Important: Only works on FILES, not directories. Use list_directory first if unsure.

4. **write_file_nano(file_path, new_content)**
   - Purpose: Create a new file or overwrite an existing file
   - Usage: write_file_nano('filename.txt', 'file content here')
   - Returns: Success or error message (may require user permission for overwrites)
   - When to use: When user asks to create, write, or save a file
   - Note: Overwriting existing files requires user permission (y/n)

5. **delete_file(file_path)**
   - Purpose: Delete a file from the filesystem
   - Usage: delete_file('filename.txt')
   - Returns: Success or error message (requires user permission)
   - When to use: When user asks to delete or remove a file
   - Note: Always requires user permission (y/n)

6. **respond_to_user(message)**
   - Purpose: Signal that you've completed the task and provide final answer
   - Usage: respond_to_user('Your final response here')
   - When to use: ALWAYS at the end when task is complete
   - Important: This tells the system you're done

**HOW TO USE TOOLS:**

To call a tool, write it EXACTLY in your response like this (the system will execute it):
- get_current_path()
- list_directory('.')
- list_directory('subfolder')
- read_file('app.py')
- write_file_nano('test.txt', 'Hello World')
- delete_file('old.txt')
- respond_to_user('Task completed!')

CRITICAL: Write the tool call directly in your response. Examples:
- "I'll check the directory: list_directory('.')"
- "Let me read that file: read_file('data.txt')"
- "I'll get the current path: get_current_path()"

The tool will be executed automatically when you write it in this format.

**REMEMBER:**
- You have REAL tools that work on the REAL filesystem
- Use them instead of guessing
- Every tool call returns real results
- If a tool returns an error, read it carefully and try a different approach
- Always complete multi-step tasks autonomously
- For write_file_nano and delete_file, user permission may be required - wait for it

Now, when the user asks something, USE YOUR TOOLS to find the answer, then use respond_to_user() to give them the result."""
    
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
                name="get_current_path",
                func=get_current_path_tool,
                description="Returns the absolute path of the current working directory. Takes no arguments. Use this when asked about current location."
            ),
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
                description="Create or overwrite a file with new content. Returns success or error message. May require user permission for overwrites."
            ),
            Tool(
                name="delete_file",
                func=delete_file_tool,
                description="Delete a file from the filesystem. Returns success or error message. Requires user permission."
            ),
            Tool(
                name="respond_to_user",
                func=respond_to_user_tool,
                description="Signal that you have completed the task and provide a response to the user. Always call this when done."
            )
        ]
        
        # Set up permission callback if provided
        if "permission_request" in self.callbacks:
            set_permission_callback(self.callbacks["permission_request"])
        
        # Create model wrapper (for potential future use)
        self.model = LlamaCppLangChainWrapper(
            llama_client=self.llama_client,
            system_prompt=self.SYSTEM_PROMPT
        )
        
        self.executor = ThreadPoolExecutor(max_workers=1)
    
    def _execute_tool(self, tool_name: str, args: List[str]) -> str:
        """Execute a tool by name."""
        tool_map = {
            "get_current_path": get_current_path_tool,
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
        """Parse tool calls from model response with improved pattern matching."""
        tool_calls = []
        seen_calls = set()  # Prevent duplicates
        
        # Get all valid tool names
        valid_tools = {tool.name for tool in self.tools}
        
        # Multiple patterns to catch different tool call formats
        patterns = [
            r"ACTION:\s*(\w+)\(([^)]*)\)",  # ACTION: tool_name(args)
            r"⚡\s*(\w+)\(([^)]*)\)",        # ⚡ tool_name(args)
            r"Call\s+(\w+)\(([^)]*)\)",     # Call tool_name(args)
            r"I'll\s+use\s+(\w+)\(([^)]*)\)",  # I'll use tool_name(args)
            r"Using\s+(\w+)\(([^)]*)\)",    # Using tool_name(args)
            r"(\w+)\(([^)]*)\)",            # tool_name(args) - catch-all
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                tool_name = match.group(1).lower()
                
                # Check if it's a valid tool (case-insensitive)
                matching_tool = None
                for tool in self.tools:
                    if tool.name.lower() == tool_name:
                        matching_tool = tool.name
                        break
                
                if not matching_tool:
                    continue
                
                tool_name = matching_tool  # Use canonical name
                args_str = match.group(2)
                
                # Create unique key to prevent duplicates
                call_key = (tool_name, args_str)
                if call_key in seen_calls:
                    continue
                seen_calls.add(call_key)
                
                # Parse arguments
                args = []
                if args_str.strip():
                    # Handle quoted strings that might contain commas
                    # Simple approach: split by comma but respect quotes
                    parts = []
                    current = ""
                    in_quotes = False
                    quote_char = None
                    
                    for char in args_str:
                        if char in ['"', "'"] and (not in_quotes or char == quote_char):
                            if in_quotes:
                                in_quotes = False
                                quote_char = None
                            else:
                                in_quotes = True
                                quote_char = char
                            current += char
                        elif char == ',' and not in_quotes:
                            if current.strip():
                                parts.append(current.strip())
                            current = ""
                        else:
                            current += char
                    
                    if current.strip():
                        parts.append(current.strip())
                    
                    # Process parts and remove quotes
                    for part in parts:
                        part = part.strip()
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
                
                # Create prompt with explicit tool usage instructions
                prompt = f"""You are AZUL, an autonomous AI coding assistant.

AVAILABLE TOOLS:
{tool_descriptions}

CONVERSATION:
{context}

{('OBSERVATIONS FROM PREVIOUS TOOL CALLS:\n' + '\n'.join(observations[-3:]) + '\n') if observations else ''}

INSTRUCTIONS:
1. Analyze what you need to do
2. Call the appropriate tool(s) by writing: tool_name('arg1', 'arg2') or tool_name() for no args
3. After seeing tool results, decide if you need more tools or can respond
4. When complete, call respond_to_user('your final answer')

EXAMPLES OF TOOL CALLS:
- To get current directory: get_current_path()
- To list files: list_directory('.')
- To read a file: read_file('filename.txt')
- To write a file: write_file_nano('file.txt', 'content')
- To delete a file: delete_file('file.txt')
- To finish: respond_to_user('Task completed')

IMPORTANT: Write tool calls directly in your response. The system will execute them automatically.

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
                    # Execute tools sequentially
                    for tool_call in tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]
                        
                        # Trigger callback
                        if tool_args:
                            args_str = ", ".join([f"'{arg}'" if isinstance(arg, str) else str(arg) for arg in tool_args])
                            call_display = f"{tool_name}({args_str})"
                        else:
                            call_display = f"{tool_name}()"
                        
                        self._trigger_callback("tool_call", call_display)
                        
                        # Execute tool
                        result = self._execute_tool(tool_name, tool_args)
                        
                        # Trigger observation callback
                        self._trigger_callback("observation", result)
                        
                        # Check for errors in tool result
                        if result.startswith("Error:") or result.startswith("Permission denied"):
                            # Add error to observations with emphasis
                            observations.append(f"ERROR from {tool_name}: {result}")
                            # Don't continue if it's respond_to_user (shouldn't error, but handle gracefully)
                            if tool_name == "respond_to_user":
                                return f"Error: {result}"
                        else:
                            # Check if it's respond_to_user
                            if tool_name == "respond_to_user" and "RESPOND:" in result:
                                return result.split("RESPOND:", 1)[1].strip()
                            
                            # Add successful observation (truncate very long results)
                            obs_text = result[:500] if len(result) > 500 else result
                            if len(result) > 500:
                                obs_text += "... (truncated)"
                            observations.append(f"{tool_name} result: {obs_text}")
                    
                    # After executing tools, continue loop to let model process results
                    iteration += 1
                    continue
                
                # Check if response contains final answer
                if "RESPOND:" in response:
                    return response.split("RESPOND:", 1)[1].strip()
                
                # Check if model says it's done (but only if no tools were called)
                if not tool_calls:
                    if "respond_to_user" in response.lower() or "task complete" in response.lower():
                        # Try to extract final message
                        lines = response.split("\n")
                        for line in reversed(lines):
                            if line.strip() and not line.strip().startswith("THINK") and not line.strip().startswith("PLAN"):
                                return line.strip()
                    
                    # If no tool calls and we have a substantial response, return it
                    if response.strip() and len(response) > 20:
                        # Check if response mentions tools but didn't call them - might need another iteration
                        tool_mentioned = any(tool.name in response.lower() for tool in self.tools)
                        if not tool_mentioned:
                            return response.strip()
                
                iteration += 1
                
                # Safety check: if we've made progress (have observations), continue
                # If no progress after 3 iterations, try to extract response
                if iteration > 3 and not observations and not tool_calls:
                    if response.strip():
                        return response.strip()
            
            # Max iterations reached
            return "Task completed (max iterations reached)."
        
        except KeyboardInterrupt:
            raise  # Re-raise to be handled by CLI
        except Exception as e:
            return f"Error: {str(e)}"

