"""Session manager for conversation history."""

import hashlib
import json
from pathlib import Path
from typing import List, Dict, Optional


class SessionManager:
    """Manages conversation history for AZUL sessions."""
    
    def __init__(self, session_dir: Path, project_root: Optional[Path] = None, max_history: int = 20):
        """Initialize session manager.
        
        Args:
            session_dir: Directory to store session files
            project_root: Root directory of current project (for session ID generation)
            max_history: Maximum number of messages to keep in history
        """
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.max_history = max_history
        
        # Generate session ID from project root
        if project_root is None:
            project_root = Path.cwd()
        self.project_root = Path(project_root).resolve()
        self.session_id = self._generate_session_id(self.project_root)
        self.session_file = self.session_dir / f"{self.session_id}.json"
        
        # Load conversation history
        self._history: List[Dict[str, str]] = []
        self._dirty = False
        self.load()
    
    @staticmethod
    def _generate_session_id(project_root: Path) -> str:
        """Generate session ID from project root path.
        
        Args:
            project_root: Root directory path
            
        Returns:
            Session ID (first 16 chars of SHA256 hash)
        """
        path_str = str(project_root)
        hash_obj = hashlib.sha256(path_str.encode())
        return hash_obj.hexdigest()[:16]
    
    def load(self):
        """Load conversation history from disk."""
        if self.session_file.exists():
            try:
                with open(self.session_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._history = data.get("history", [])
                    
                    # Apply sliding window if history exceeds limit
                    if len(self._history) > self.max_history:
                        self._history = self._history[-self.max_history:]
                        self._dirty = True
            except (json.JSONDecodeError, IOError, KeyError):
                self._history = []
                self._dirty = False
        else:
            self._history = []
            self._dirty = False
    
    def save(self):
        """Save conversation history to disk."""
        if not self._dirty:
            return
        
        try:
            data = {
                "session_id": self.session_id,
                "project_root": str(self.project_root),
                "history": self._history,
            }
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            self._dirty = False
        except IOError as e:
            print(f"Warning: Could not save session: {e}")
    
    def add_message(self, role: str, content: str):
        """Add a message to conversation history.
        
        Args:
            role: Message role ('user' or 'assistant')
            content: Message content
        """
        if role not in ["user", "assistant"]:
            raise ValueError(f"Invalid role: {role}. Must be 'user' or 'assistant'")
        
        self._history.append({"role": role, "content": content})
        self._dirty = True
        
        # Apply sliding window
        if len(self._history) > self.max_history:
            self._history = self._history[-self.max_history:]
    
    def get_history(self) -> List[Dict[str, str]]:
        """Get full conversation history.
        
        Returns:
            List of message dictionaries with 'role' and 'content' keys
        """
        return self._history
    
    def get_recent_history(self, n: int = 10) -> List[Dict[str, str]]:
        """Get recent conversation history.
        
        Args:
            n: Number of recent messages to return
            
        Returns:
            List of recent message dictionaries
        """
        return self._history[-n:] if len(self._history) > n else self._history
    
    def clear(self):
        """Clear conversation history."""
        self._history = []
        self._dirty = True
        self.save()
    
    def get_session_id(self) -> str:
        """Get current session ID."""
        return self.session_id
    
    def get_project_root(self) -> Path:
        """Get project root path."""
        return self.project_root

