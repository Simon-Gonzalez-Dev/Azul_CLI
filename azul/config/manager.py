"""Configuration manager for AZUL CLI."""

import json
import os
from pathlib import Path
from typing import Optional


class ConfigManager:
    """Manages persistent configuration for AZUL."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration manager.
        
        Args:
            config_path: Optional path to config file. Defaults to ~/.azul/config.json
        """
        if config_path is None:
            self.config_dir = Path.home() / ".azul"
            self.config_path = self.config_dir / "config.json"
        else:
            self.config_path = Path(config_path)
            self.config_dir = self.config_path.parent
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing config or create default
        self._config = self._load_config()
    
    def _load_config(self) -> dict:
        """Load configuration from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                # If config is corrupted, create default
                return self._default_config()
        return self._default_config()
    
    def _default_config(self) -> dict:
        """Return default configuration."""
        return {
            "model_path": None,
            "max_history_messages": 20,
            "context_window_size": 4096,
            "session_dir": str(Path.home() / ".azul" / "sessions"),
        }
    
    def _save_config(self):
        """Save configuration to file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self._config, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save config: {e}")
    
    def get_model_path(self) -> Optional[str]:
        """Get cached model path."""
        return self._config.get("model_path")
    
    def set_model_path(self, model_path: str):
        """Set and cache model path."""
        self._config["model_path"] = model_path
        self._save_config()
    
    def get_session_dir(self) -> Path:
        """Get session directory path."""
        session_dir = self._config.get("session_dir")
        if session_dir:
            path = Path(session_dir)
            path.mkdir(parents=True, exist_ok=True)
            return path
        else:
            # Use default
            default_dir = Path.home() / ".azul" / "sessions"
            default_dir.mkdir(parents=True, exist_ok=True)
            return default_dir
    
    def set_session_dir(self, session_dir: str):
        """Set session directory path."""
        self._config["session_dir"] = session_dir
        self._save_config()
    
    def get_max_history_messages(self) -> int:
        """Get maximum number of history messages."""
        return self._config.get("max_history_messages", 20)
    
    def get_context_window_size(self) -> int:
        """Get context window size."""
        return self._config.get("context_window_size", 4096)
    
    def resolve_model_path(self, model_path: Optional[str] = None) -> Optional[Path]:
        """Resolve model path with priority order.
        
        Priority:
        1. Explicit model_path argument
        2. Cached model path from config
        3. azul/models/ directory
        4. ~/.azul/models/ directory
        5. ~/models/ directory
        6. Current working directory
        7. Home directory
        
        Args:
            model_path: Optional explicit model path
            
        Returns:
            Path to model file if found, None otherwise
        """
        # Priority 1: Explicit path
        if model_path:
            path = Path(model_path)
            if path.exists():
                return path.resolve()
        
        # Priority 2: Cached path
        cached_path = self.get_model_path()
        if cached_path:
            path = Path(cached_path)
            if path.exists():
                return path.resolve()
        
        # Priority 3: azul/models/
        package_dir = Path(__file__).parent.parent.parent
        model_dirs = [
            package_dir / "azul" / "models",
            Path.home() / ".azul" / "models",
            Path.home() / "models",
            Path.cwd(),
            Path.home(),
        ]
        
        # Look for common model filenames
        model_names = [
            "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
            "*.gguf",  # Any GGUF file
        ]
        
        for model_dir in model_dirs:
            if not model_dir.exists():
                continue
            for model_name in model_names:
                matches = list(model_dir.glob(model_name))
                if matches:
                    # Prefer exact match
                    exact_match = model_dir / model_name
                    if exact_match.exists():
                        return exact_match.resolve()
                    # Otherwise return first match
                    return matches[0].resolve()
        
        return None

