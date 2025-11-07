"""AZUL Agent using LangChain and LangGraph."""

import logging
import json
from typing import Optional, Callable, Any
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable

from .llm import LlamaClient
from .tools import ALL_TOOLS, set_tool_callback
from .config import config

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are AZUL, an autonomous AI coding assistant. You help users by thinking step-by-step and using available tools.

WORKFLOW:
1. THINK: Analyze the user's request carefully
2. PLAN: Break down the task into clear steps
3. ACT: Execute tools one by one to accomplish the task
4. OBSERVE: Process the results from each tool
5. RESPOND: Provide a clear final answer to the user

IMPORTANT GUIDELINES:
- Always think before acting
- Use tools when you need to interact with files or the system
- Be precise and thorough
- If you encounter an error, explain it clearly to the user
- When your task is complete, provide a comprehensive response

Available tools allow you to read files, write files, delete files, execute shell commands, and list directories. Use them wisely."""


class LlamaChatModel(BaseChatModel):
    """LangChain-compatible wrapper for LlamaClient."""
    
    llama_client: LlamaClient
    
    def __init__(self, llama_client: LlamaClient, **kwargs):
        super().__init__(llama_client=llama_client, **kwargs)
    
    def _generate(self, messages: list[BaseMessage], stop: Optional[list[str]] = None, **kwargs) -> ChatResult:
        """Generate a response from messages."""
        # Convert LangChain messages to llama.cpp format
        formatted_messages = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                formatted_messages.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                formatted_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                formatted_messages.append({"role": "assistant", "content": msg.content})
            elif isinstance(msg, ToolMessage):
                # Tool results are added as user messages with context
                formatted_messages.append({
                    "role": "user", 
                    "content": f"Tool result: {msg.content}"
                })
        
        # Generate response
        response_text = self.llama_client.chat(
            messages=formatted_messages,
            stop=stop,
            **kwargs
        )
        
        # Create AIMessage with the response
        message = AIMessage(content=response_text)
        generation = ChatGeneration(message=message)
        
        return ChatResult(generations=[generation])
    
    @property
    def _llm_type(self) -> str:
        return "llama-cpp"
    
    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"model_path": str(self.llama_client.model_path)}


class AzulAgent:
    """AZUL agent with LangChain/LangGraph integration."""
    
    def __init__(
        self,
        model_path: Optional[Path] = None,
        on_thought: Optional[Callable[[str], None]] = None,
        on_tool_call: Optional[Callable[[str, dict], None]] = None,
        on_tool_result: Optional[Callable[[str, bool], None]] = None,
        on_response: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None
    ):
        """Initialize the AZUL agent.
        
        Args:
            model_path: Path to the GGUF model
            on_thought: Callback for agent thoughts
            on_tool_call: Callback for tool calls
            on_tool_result: Callback for tool results
            on_response: Callback for final responses
            on_status: Callback for status updates
        """
        self.model_path = model_path or config.model_path
        
        # Callbacks
        self.on_thought = on_thought
        self.on_tool_call = on_tool_call
        self.on_tool_result = on_tool_result
        self.on_response = on_response
        self.on_status = on_status
        
        # Initialize LLM
        logger.info("Initializing AZUL agent")
        self.llama_client = LlamaClient(model_path=self.model_path)
        self.llm = LlamaChatModel(llama_client=self.llama_client)
        
        # Set up tool callbacks
        def tool_callback(event_type: str, message: str):
            if event_type == "tool_start" and self.on_tool_call:
                # Parse out the tool being called
                self.on_status("executing")
            elif event_type == "tool_end" and self.on_tool_result:
                self.on_tool_result(message, True)
        
        set_tool_callback(tool_callback)
        
        # Conversation history
        self.conversation_history: list[dict[str, str]] = []
        
        logger.info("AZUL agent initialized")
    
    def _create_agent_executor(self) -> AgentExecutor:
        """Create the LangChain agent executor."""
        # Create prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])
        
        # Create agent with ReAct-style prompting
        # Note: Since we're using a custom LLM that may not support native tool calling,
        # we'll use a simpler approach where the agent decides when to call tools
        # based on its reasoning in the response text
        
        # For now, we'll implement a manual ReAct loop
        return None  # We'll handle this manually in execute()
    
    def execute(self, user_input: str) -> str:
        """Execute the agent on a user input.
        
        Args:
            user_input: User's input text
            
        Returns:
            Agent's final response
        """
        try:
            if self.on_status:
                self.on_status("thinking")
            
            # Add user input to conversation history
            self.conversation_history.append({"role": "user", "content": user_input})
            
            # Build the full conversation context
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            
            # Add recent conversation history (last 10 messages)
            recent_history = self.conversation_history[-10:]
            messages.extend(recent_history)
            
            # Manual ReAct loop
            max_iterations = config.max_iterations
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                
                # Generate response
                response = self.llama_client.chat(messages=messages)
                
                if self.on_thought:
                    self.on_thought(response)
                
                # Check if the agent wants to use a tool
                tool_call = self._parse_tool_call(response)
                
                if tool_call:
                    # Execute the tool
                    tool_name = tool_call["tool"]
                    tool_args = tool_call["args"]
                    
                    if self.on_tool_call:
                        self.on_tool_call(tool_name, tool_args)
                    
                    if self.on_status:
                        self.on_status("executing")
                    
                    # Find and execute the tool
                    tool_result = self._execute_tool(tool_name, tool_args)
                    
                    if self.on_tool_result:
                        self.on_tool_result(tool_result, "Error:" not in tool_result)
                    
                    # Add tool call and result to conversation
                    messages.append({
                        "role": "assistant",
                        "content": f"I will use the {tool_name} tool with arguments: {json.dumps(tool_args)}"
                    })
                    messages.append({
                        "role": "user",
                        "content": f"Tool result: {tool_result}"
                    })
                    
                    if self.on_status:
                        self.on_status("thinking")
                else:
                    # No tool call - this is the final response
                    if self.on_status:
                        self.on_status("idle")
                    
                    if self.on_response:
                        self.on_response(response)
                    
                    # Add to conversation history
                    self.conversation_history.append({"role": "assistant", "content": response})
                    
                    return response
            
            # Max iterations reached
            error_msg = "Agent reached maximum iterations without completing the task."
            if self.on_status:
                self.on_status("error")
            return error_msg
        
        except Exception as e:
            logger.error(f"Error in agent execution: {e}", exc_info=True)
            if self.on_status:
                self.on_status("error")
            return f"Error: {str(e)}"
    
    def _parse_tool_call(self, response: str) -> Optional[dict]:
        """Parse a tool call from the agent's response.
        
        The agent should indicate tool usage with a specific format like:
        TOOL: tool_name
        ARGS: {"arg1": "value1", "arg2": "value2"}
        
        Or in a more natural way we can parse.
        """
        # Simple heuristic: look for common patterns
        response_lower = response.lower()
        
        # Check for explicit tool mentions
        for tool in ALL_TOOLS:
            tool_name = tool.name
            if f"use {tool_name}" in response_lower or f"call {tool_name}" in response_lower:
                # Try to extract arguments
                # This is a simplified version - in production, you'd want more robust parsing
                return None  # For now, return None to use direct instruction approach
        
        return None
    
    def _execute_tool(self, tool_name: str, args: dict) -> str:
        """Execute a tool by name with arguments."""
        for tool in ALL_TOOLS:
            if tool.name == tool_name:
                try:
                    result = tool.invoke(args)
                    return str(result)
                except Exception as e:
                    return f"Error executing {tool_name}: {str(e)}"
        
        return f"Error: Unknown tool '{tool_name}'"
    
    def reset_conversation(self):
        """Reset the conversation history."""
        self.conversation_history = []
        logger.info("Conversation history reset")

