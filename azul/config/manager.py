"""Configuration management for AZUL CLI."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigManager:
    """Manages JSON configuration file for AZUL CLI."""
    
    DEFAULT_CONFIG = {
        "model_path": None,  # Path to .gguf model file
        "temperature": 0.7,
        "max_history_messages": 20,
        "max_file_size_mb": 10,
        "permission_defaults": {
            "auto_approve": False,
            "remember_choices": True
        },
        "context_window_size": 4096,
        "enable_file_monitoring": True,
        "enable_cherry_picking": False
    }
    
    def __init__(self):
        """Initialize config manager."""
        self.config_dir = Path.home() / ".azul"
        self.config_file = self.config_dir / "config.json"
        self._config: Optional[Dict[str, Any]] = None
        
    def _ensure_config_dir(self) -> None:
        """Create config directory if it doesn't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default."""
        if self._config is not None:
            return self._config
            
        self._ensure_config_dir()
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    self._config = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    self._config = {**self.DEFAULT_CONFIG, **self._config}
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load config: {e}. Using defaults.")
                self._config = self.DEFAULT_CONFIG.copy()
        else:
            self._config = self.DEFAULT_CONFIG.copy()
            self.save_config()
        
        return self._config
    
    def save_config(self) -> None:
        """Save configuration to file."""
        if self._config is None:
            self._config = self.load_config()
        
        self._ensure_config_dir()
        
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self._config, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save config: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        config = self.load_config()
        return config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        config = self.load_config()
        config[key] = value
        self._config = config
        self.save_config()
    
    def get_model(self) -> str:
        """Get the configured model name."""
        return self.get("model", self.DEFAULT_CONFIG["model"])
    
    def set_model(self, model: str) -> None:
        """Set the model name."""
        self.set("model", model)


# Global config manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get the global config manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager

