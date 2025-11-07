"""Configuration management for AZUL."""

import os
from pathlib import Path
from typing import Optional


class Config:
    """Configuration manager for AZUL."""
    
    def __init__(self):
        self.model_path = self._get_model_path()
        self.n_ctx = 8192
        self.n_gpu_layers = -1
        self.max_tokens = 8192
        self.max_iterations = 50
        self.temperature = 0.7
        self.top_p = 0.9
        self.repeat_penalty = 1.1
        self.session_dir = Path.home() / ".azul" / "sessions"
        self.session_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_model_path(self) -> Path:
        """Get model path from environment variable."""
        model_path = os.getenv("AZUL_MODEL_PATH")
        if not model_path:
            raise ValueError(
                "AZUL_MODEL_PATH environment variable is required. "
                "Please set it to the path of your GGUF model file."
            )
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Model file not found: {model_path}. "
                "Please check that AZUL_MODEL_PATH points to a valid model file."
            )
        return path
    
    def get_session_path(self, session_id: Optional[str] = None) -> Path:
        """Get path to session file."""
        if session_id is None:
            session_id = "default"
        return self.session_dir / f"{session_id}.json"

