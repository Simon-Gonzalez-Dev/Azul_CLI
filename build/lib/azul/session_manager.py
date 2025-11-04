"""Session management for conversation history."""

import json
import hashlib
import os
from pathlib import Path
from typing import List, Dict, Optional, Any

from azul.config.manager import get_config_manager


class SessionManager:
    """Manages conversation history on a per-directory basis."""
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize session manager.
        
        Args:
            project_root: Root directory of the project
        """
        self.config = get_config_manager()
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.sessions_dir = Path.home() / ".azul_sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = self._generate_session_id()
        self.session_file = self.sessions_dir / f"{self.session_id}.json"
        self.max_history = self.config.get("max_history_messages", 20)
        self._history: Optional[List[Dict[str, str]]] = None
    
    def _generate_session_id(self) -> str:
        """Generate a unique session ID based on directory path."""
        abs_path = str(self.project_root.resolve())
        return hashlib.sha256(abs_path.encode()).hexdigest()[:16]
    
    def load_history(self) -> List[Dict[str, str]]:
        """Load conversation history from session file."""
        if self._history is not None:
            return self._history
        
        if self.session_file.exists():
            try:
                with open(self.session_file, 'r') as f:
                    data = json.load(f)
                    self._history = data.get('history', [])
                    # Apply sliding window
                    if len(self._history) > self.max_history:
                        self._history = self._history[-self.max_history:]
                    return self._history
            except (json.JSONDecodeError, IOError, KeyError):
                self._history = []
        else:
            self._history = []
        
        return self._history
    
    def save_history(self) -> None:
        """Save conversation history to session file."""
        if self._history is None:
            self._history = []
        
        try:
            data = {
                'session_id': self.session_id,
                'project_root': str(self.project_root),
                'history': self._history
            }
            with open(self.session_file, 'w') as f:
                json.dump(data, f, indent=2)
        except (IOError, OSError) as e:
            print(f"Warning: Could not save session history: {e}")
    
    def add_message(self, role: str, content: str) -> None:
        """
        Add a message to the conversation history.
        
        Args:
            role: 'user' or 'assistant'
            content: Message content
        """
        if self._history is None:
            self.load_history()
        
        self._history.append({
            'role': role,
            'content': content
        })
        
        # Apply sliding window
        if len(self._history) > self.max_history:
            # Keep system messages and recent history
            # For now, just keep the last N messages
            self._history = self._history[-self.max_history:]
        
        self.save_history()
    
    def clear_history(self) -> None:
        """Clear conversation history for current session."""
        self._history = []
        self.save_history()
    
    def get_history(self) -> List[Dict[str, str]]:
        """Get current conversation history."""
        if self._history is None:
            self.load_history()
        return self._history.copy()
    
    def get_recent_history(self, n: Optional[int] = None) -> List[Dict[str, str]]:
        """
        Get recent conversation history.
        
        Args:
            n: Number of recent messages to return. Defaults to max_history.
            
        Returns:
            List of recent messages
        """
        history = self.get_history()
        if n is None:
            n = self.max_history
        return history[-n:] if len(history) > n else history
    
    def estimate_tokens(self, text: str) -> int:
        """
        Rough estimation of token count.
        
        Args:
            text: Text to estimate
            
        Returns:
            Estimated token count (rough approximation: 1 token ≈ 4 characters)
        """
        return len(text) // 4
    
    def get_context_size(self) -> int:
        """Get estimated total context size of current history."""
        total = 0
        for message in self.get_history():
            total += self.estimate_tokens(message.get('content', ''))
        return total


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def get_session_manager(project_root: Optional[Path] = None) -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager(project_root)
    return _session_manager

