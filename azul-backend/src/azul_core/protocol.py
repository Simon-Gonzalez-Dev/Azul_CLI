"""WebSocket protocol message definitions."""

from typing import Literal, Any, Optional
from pydantic import BaseModel, Field


class Message(BaseModel):
    """Base message type."""
    type: str


# Client → Server Messages

class UserPromptMessage(Message):
    """User input message."""
    type: Literal["user_prompt"] = "user_prompt"
    text: str


class ActionResponseMessage(Message):
    """User response to action approval request."""
    type: Literal["action_response"] = "action_response"
    approved: bool


# Server → Client Messages

class AgentThoughtMessage(Message):
    """Agent's internal reasoning."""
    type: Literal["agent_thought"] = "agent_thought"
    text: str


class TaskItem(BaseModel):
    """A single task in the agent's plan."""
    id: str
    text: str
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"


class AgentPlanMessage(Message):
    """Agent's execution plan."""
    type: Literal["agent_plan"] = "agent_plan"
    tasks: list[TaskItem]


class ToolCallMessage(Message):
    """Tool execution request."""
    type: Literal["tool_call"] = "tool_call"
    tool: str
    args: dict[str, Any]
    tool_call_id: Optional[str] = None


class ToolResultMessage(Message):
    """Tool execution result."""
    type: Literal["tool_result"] = "tool_result"
    result: str
    success: bool
    tool_call_id: Optional[str] = None


class AgentResponseMessage(Message):
    """Final agent response."""
    type: Literal["agent_response"] = "agent_response"
    text: str


class StatusUpdateMessage(Message):
    """Agent status update."""
    type: Literal["status_update"] = "status_update"
    status: Literal["idle", "thinking", "executing", "error"]
    text: Optional[str] = None


class ErrorMessage(Message):
    """Error message."""
    type: Literal["error"] = "error"
    error: str
    details: Optional[str] = None


# Union type for all server messages
ServerMessage = (
    AgentThoughtMessage |
    AgentPlanMessage |
    ToolCallMessage |
    ToolResultMessage |
    AgentResponseMessage |
    StatusUpdateMessage |
    ErrorMessage
)

# Union type for all client messages
ClientMessage = UserPromptMessage | ActionResponseMessage

