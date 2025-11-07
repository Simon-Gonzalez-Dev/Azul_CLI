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
    execute_shell_command_tool,
    get_current_path_tool,
    list_directory_tool,
    read_file_tool,
    reset_memory_tool,
    respond_to_user_tool,
    search_code_base_tool,
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
        response, _ = self.llama_client.chat(
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
        for token, _ in self.llama_client.stream_chat(
            user_message=user_message,
            conversation_history=history,
            system_prompt=self.system_prompt
        ):
            if token:  # Skip empty token (stats marker)
                full_response += token
                yield AIMessage(content=token)
        
        # Yield final message
        yield AIMessage(content=full_response)
    
    def bind_tools(self, tools: List[Tool]) -> "LlamaCppLangChainWrapper":
        """Bind tools to the model (for compatibility, tools handled separately)."""
        return self


class AzulAgent:
    """Main agent executor using LangGraph ReAct pattern."""
    
    SYSTEM_PROMPT = """You are AZUL, an elite AI software engineer operating autonomously in a command-line environment. Your core identity is that of a proactive, methodical problem-solver who NEVER guesses or hallucinates. You possess REAL tools that interact with the ACTUAL filesystem - these are your only source of truth.

**FUNDAMENTAL PRINCIPLES (NON-NEGOTIABLE):**

1. **VERIFICATION MANDATE**: Every action you take MUST be verified. After writing a file, read it back. After creating something, list the directory. After modifying code, search for it to confirm changes.

2. **TOOL-FIRST COGNITION**: Information you don't possess MUST be acquired through tools. The question "Do I know this?" should immediately trigger tool usage, not assumption.

3. **AUTONOMOUS EXECUTION**: Complete multi-step tasks without asking the user for information you can discover yourself. If you need to know what files exist, use list_directory. If you need the current path, use get_current_path.

4. **ERROR RECOVERY**: When a tool returns an error, analyze it systematically. Read error messages carefully. Try alternative approaches. Never give up after a single failure.

**COGNITIVE ARCHITECTURE (YOUR THINKING PROCESS):**

For every user request, follow this structured approach:

**ORIENT**: Assess the current state
- What is the user's ultimate objective?
- What is my current working directory? (Use get_current_path if uncertain)
- What files and directories exist? (Use list_directory if uncertain)
- What information gaps exist that prevent me from proceeding?

**PLAN**: Construct a step-by-step strategy
- Break the objective into discrete, executable steps
- Begin with information gathering steps before any modifications
- Include verification steps after each modification
- The final step MUST always be verification of the complete task

**ACT**: Execute one step at a time
- Call exactly ONE tool per action
- Wait for the tool's result before proceeding
- Format tool calls as: tool_name('arg1', 'arg2') or tool_name() for no arguments

**VERIFY**: Validate and adapt
- Did the tool execute successfully?
- Does the result match expectations?
- What does this new information reveal about the next step?
- Update your plan based on new information
- If verification fails, diagnose and retry

**AVAILABLE TOOLS (YOUR CAPABILITIES):**

1. get_current_path() → Returns absolute path of current working directory
   Use when: You need to know where you are operating

2. list_directory(directory_path: str) → Lists files and subdirectories
   Use when: You need to see what exists before reading/modifying
   Default: Use '.' for current directory

3. read_file(file_path: str) → Returns complete file contents
   Use when: You need to examine file contents
   Critical: Only works on files, not directories

4. write_file_nano(file_path: str, new_content: str) → Creates/overwrites file
   Use when: Creating new files or modifying existing ones
   Note: Overwriting requires user permission (wait for y/n response)

5. delete_file(file_path: str) → Removes a file
   Use when: User requests file deletion
   Note: Always requires user permission (wait for y/n response)

6. search_code_base(query: str) → Recursively searches code for patterns
   Use when: Finding where functions/classes are defined or used
   Returns: Matching lines with file paths and line numbers

7. execute_shell_command(command: str) → Runs shell commands
   Use when: Running tests, linters, or verifying operations
   Safety: Dangerous commands are blocked automatically

8. reset_memory() → Clears conversation history
   Use when: User explicitly requests memory reset

9. respond_to_user(message: str, thought_process: str) → Signals completion
   Use when: Task is fully verified and complete
   Include thought_process to explain your reasoning

**TOOL CALL SYNTAX:**

Write tool calls directly in your response. The system parses and executes them automatically:
- get_current_path()
- list_directory('.')
- read_file('path/to/file.py')
- write_file_nano('file.txt', 'content')
- search_code_base('function_name')
- execute_shell_command('ls -l')
- respond_to_user('Final answer', 'Reasoning summary')

**CRITICAL CONSTRAINTS:**

- NEVER invent file paths, directory contents, or file names
- NEVER say "I don't have access" - you have full tool access
- NEVER skip verification steps
- NEVER ask the user for information you can obtain via tools
- NEVER proceed with modifications without first understanding the current state
- ALWAYS verify your work before calling respond_to_user

**WORKFLOW PATTERN:**

When you receive a request:
1. ORIENT: Use get_current_path() and list_directory() to understand context
2. PLAN: Outline steps mentally (you can express this in your thinking)
3. ACT: Execute tools sequentially, one at a time
4. VERIFY: After each action, confirm success before proceeding
5. COMPLETE: Once verified, use respond_to_user() with your final answer

Remember: You are an autonomous agent. Take initiative. Verify everything. Never guess."""
    
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
                name="search_code_base",
                func=search_code_base_tool,
                description="Search for code snippets or keywords in the current directory recursively. Returns matching lines with file paths and line numbers. Use this to find where functions are defined or used."
            ),
            Tool(
                name="execute_shell_command",
                func=execute_shell_command_tool,
                description="Execute a shell command and return output. Use for verification (ls, python, pytest, etc.). Use with caution - only safe, non-interactive commands."
            ),
            Tool(
                name="reset_memory",
                func=reset_memory_tool,
                description="Reset/clear the conversation memory/history. Use when user asks to forget previous conversation or start fresh."
            ),
            Tool(
                name="respond_to_user",
                func=respond_to_user_tool,
                description="Signal that you have completed the task and provide a response to the user. Always call this when done. Can include optional thought_process parameter."
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
            "search_code_base": search_code_base_tool,
            "execute_shell_command": execute_shell_command_tool,
            "reset_memory": reset_memory_tool,
            "respond_to_user": respond_to_user_tool,
        }
        
        if tool_name not in tool_map:
            return f"Error: Unknown tool: {tool_name}"
        
        tool_func = tool_map[tool_name]
        
        try:
            # Handle reset_memory specially
            if tool_name == "reset_memory":
                result = tool_func()
                return result
            
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
            thought_process_steps = []  # Track reasoning steps
            
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
4. When complete, call respond_to_user('your final answer', 'your reasoning')

IMPORTANT: Write tool calls directly in your response. The system will execute them automatically.

Your response:"""
                
                # Check if we have streaming callback
                has_streaming = "thinking_stream" in self.callbacks
                
                if has_streaming:
                    # Stream response
                    if "start_generation" in self.callbacks:
                        self.callbacks["start_generation"]()
                    
                    full_response = ""
                    stats = None
                    for token, token_stats in self.llama_client.stream_chat(
                        user_message=prompt,
                        conversation_history=[],
                        system_prompt=self.SYSTEM_PROMPT,
                        max_tokens=2048,
                        temperature=0.7
                    ):
                        if token_stats is not None:
                            # Final stats received
                            stats = token_stats
                            if "stats" in self.callbacks:
                                self.callbacks["stats"](stats)
                        else:
                            full_response += token
                            self._trigger_callback("thinking_stream", token)
                    
                    response = full_response
                else:
                    # Non-streaming fallback
                    response, stats = self.llama_client.chat(
                        user_message=prompt,
                        conversation_history=[],
                        system_prompt=self.SYSTEM_PROMPT,
                        max_tokens=2048,
                        temperature=0.7
                    )
                    if "stats" in self.callbacks:
                        self.callbacks["stats"](stats)
                
                # Parse response for tool calls
                tool_calls = self._parse_tool_calls(response)
                
                if tool_calls:
                    # Execute tools sequentially
                    for tool_call in tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]
                        
                        # Handle reset_memory specially
                        if tool_name == "reset_memory":
                            result = self._execute_tool(tool_name, tool_args)
                            # Clear conversation history
                            self.conversation_history = []
                            observations = []
                            thought_process_steps = []
                            return "Memory reset successfully. Conversation history cleared."
                        
                        # Trigger callback
                        if tool_args:
                            args_str = ", ".join([f"'{arg}'" if isinstance(arg, str) else str(arg) for arg in tool_args])
                            call_display = f"{tool_name}({args_str})"
                        else:
                            call_display = f"{tool_name}()"
                        
                        self._trigger_callback("tool_call", call_display)
                        
                        # Track thought process
                        if tool_name != "respond_to_user":
                            thought_process_steps.append(f"Executed {tool_name}")
                        
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
                                # Extract message and thought process
                                response_parts = result.split("RESPOND:", 1)[1].strip()
                                if "THOUGHT_PROCESS:" in response_parts:
                                    msg, thought = response_parts.split("THOUGHT_PROCESS:", 1)
                                    return msg.strip() + "\n\n[Thought Process]\n" + thought.strip()
                                else:
                                    # Include tracked thought process if available
                                    if thought_process_steps:
                                        thought_summary = "\n\n[Thought Process]\n" + "\n".join(thought_process_steps[-5:])
                                        return response_parts + thought_summary
                                    return response_parts
                            
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

