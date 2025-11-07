"""Session management for conversation history."""

import json
from pathlib import Path
from typing import Dict, List, Optional


class SessionManager:
    """Manages conversation history persistence."""
    
    def __init__(self, session_path: Path):
        self.session_path = session_path
        self._history: List[Dict[str, str]] = []
        self.load()
    
    def load(self) -> None:
        """Load conversation history from disk."""
        if self.session_path.exists():
            try:
                with open(self.session_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._history = data.get("history", [])
            except (json.JSONDecodeError, IOError):
                self._history = []
        else:
            self._history = []
    
    def save(self) -> None:
        """Save conversation history to disk."""
        try:
            self.session_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.session_path, "w", encoding="utf-8") as f:
                json.dump({"history": self._history}, f, indent=2)
        except IOError as e:
            # Log error but don't crash
            print(f"Warning: Could not save session: {e}")
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history."""
        self._history.append({"role": role, "content": content})
        self.save()
    
    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """Get conversation history, optionally limited to last N messages."""
        if limit is None:
            return self._history.copy()
        return self._history[-limit:] if len(self._history) > limit else self._history.copy()
    
    def clear(self) -> None:
        """Clear conversation history."""
        self._history = []
        self.save()

