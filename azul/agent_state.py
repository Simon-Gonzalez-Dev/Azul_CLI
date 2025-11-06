"""Agent state management - single source of truth for agent state."""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class PlanStep:
    """Represents a single step in the agent's plan."""
    description: str
    status: str = "pending"  # "pending", "in_progress", "completed", "failed"
    
    def __str__(self) -> str:
        status_symbol = {
            "pending": "[pending]",
            "in_progress": "[in progress]",
            "completed": "✓",
            "failed": "✗"
        }.get(self.status, "[?]")
        return f"{self.description} {status_symbol}"


@dataclass
class AgentState:
    """Single source of truth for agent state."""
    initial_prompt: str
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    plan: List[PlanStep] = field(default_factory=list)
    current_step: int = 0
    planning_complete: bool = False
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message to conversation history."""
        self.conversation_history.append({"role": role, "content": content})
    
    def get_current_step(self) -> Optional[PlanStep]:
        """Get the current step being executed."""
        if self.current_step < len(self.plan):
            return self.plan[self.current_step]
        return None
    
    def mark_step_completed(self) -> None:
        """Mark current step as completed and advance."""
        if self.current_step < len(self.plan):
            self.plan[self.current_step].status = "completed"
            self.current_step += 1
    
    def mark_step_failed(self, reason: str = "") -> None:
        """Mark current step as failed."""
        if self.current_step < len(self.plan):
            self.plan[self.current_step].status = "failed"
    
    def is_complete(self) -> bool:
        """Check if all steps are completed."""
        return self.current_step >= len(self.plan) and self.plan and all(
            step.status in ("completed", "failed") for step in self.plan
        )

