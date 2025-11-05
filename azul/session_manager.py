"""Optimized session management for conversation history."""

import json
import hashlib
from pathlib import Path
from typing import List, Dict, Optional
from azul.config.manager import get_config_manager


class SessionManager:
    """High-performance session manager optimized for speed."""
    
    def __init__(self, project_root: Optional[Path] = None):
        """Initialize session manager."""
        self.config = get_config_manager()
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.sessions_dir = Path.home() / ".azul_sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = self._generate_session_id()
        self.session_file = self.sessions_dir / f"{self.session_id}.json"
        self.max_history = self.config.get("max_history_messages", 20)
        self._history: Optional[List[Dict[str, str]]] = None
        self._dirty = False  # Track if history needs saving
    
    def _generate_session_id(self) -> str:
        """Generate session ID."""
        abs_path = str(self.project_root.resolve())
        return hashlib.sha256(abs_path.encode()).hexdigest()[:16]
    
    def load_history(self) -> List[Dict[str, str]]:
        """Load conversation history - optimized."""
        if self._history is not None:
            return self._history
        
        if self.session_file.exists():
            try:
                with open(self.session_file, 'r') as f:
                    data = json.load(f)
                    self._history = data.get('history', [])
                    # Apply sliding window once
                    if len(self._history) > self.max_history:
                        self._history = self._history[-self.max_history:]
            except (json.JSONDecodeError, IOError, KeyError):
                self._history = []
        else:
            self._history = []
        
        return self._history
    
    def save_history(self) -> None:
        """Save history - deferred to reduce blocking."""
        if self._history is None:
            self._history = []
        
        if not self._dirty:
            return  # No changes to save
        
        try:
            data = {
                'session_id': self.session_id,
                'project_root': str(self.project_root),
                'history': self._history
            }
            with open(self.session_file, 'w') as f:
                json.dump(data, f, indent=2)
            self._dirty = False
        except (IOError, OSError):
            pass  # Silently fail - don't block
    
    def add_message(self, role: str, content: str) -> None:
        """Add message - optimized for speed."""
        if self._history is None:
            self.load_history()
        
        self._history.append({'role': role, 'content': content})
        
        # Apply sliding window efficiently
        if len(self._history) > self.max_history:
            self._history = self._history[-self.max_history:]
        
        self._dirty = True
        # Defer save to reduce blocking - save on next access or exit
    
    def clear_history(self) -> None:
        """Clear history."""
        self._history = []
        self._dirty = True
        self.save_history()
    
    def get_history(self) -> List[Dict[str, str]]:
        """Get history - no copy for speed."""
        if self._history is None:
            self.load_history()
        return self._history  # Return reference, not copy
    
    def get_recent_history(self, n: Optional[int] = None) -> List[Dict[str, str]]:
        """
        Get recent history - optimized slicing.
        Returns reference to slice, not copy, for maximum speed.
        """
        if self._history is None:
            self.load_history()
        
        if n is None:
            n = self.max_history
        
        # Use slice directly - no copy needed
        history_len = len(self._history)
        if history_len > n:
            return self._history[-n:]
        return self._history


# Global instance
_session_manager: Optional[SessionManager] = None


def get_session_manager(project_root: Optional[Path] = None) -> SessionManager:
    """Get global session manager."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager(project_root)
    return _session_manager
