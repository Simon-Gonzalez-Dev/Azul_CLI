"""Environment checker for validating required models and dependencies."""

from typing import Tuple, Optional
import os
from pathlib import Path
from azul.config.manager import get_config_manager
from azul.formatter import get_formatter


def check_models(config) -> Tuple[bool, bool]:
    """
    Check if required model file is available.
    
    Args:
        config: Configuration dict
        
    Returns:
        Tuple of (chat_model_available, rag_available)
    """
    try:
        # Check if llama-cpp-python is available
        try:
            import llama_cpp
            llama_available = True
        except ImportError:
            llama_available = False
        
        if not llama_available:
            return False, False
        
        # Check if model file exists
        model_path = config.get("model_path", None)
        if model_path and os.path.exists(model_path):
            return True, False
        
        # Check for default model name - prioritize azul/models/ folder
        default_model = "qwen2.5-coder-7b-instruct-q4_k_m.gguf"
        # Get azul package directory
        import azul
        from pathlib import Path
        azul_package_dir = Path(azul.__file__).parent
        
        # Try common locations (azul/models/ first)
        possible_paths = [
            str(azul_package_dir / "models" / default_model),  # azul/models/ first
            os.path.join(os.path.expanduser("~"), "models", default_model),  # ~/models/ second
            os.path.join(os.path.expanduser("~"), default_model),  # Home directory
            default_model,  # Current directory last
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return True, False
        
        # Model not found but llama-cpp available - allow continuation
        return True, False
        
    except Exception:
        # Silently fail - allow app to start, models will be checked when used
        return True, False


def validate_environment() -> Tuple[bool, bool]:
    """
    Validate the entire environment on startup.
    
    Returns:
        Tuple of (chat_model_available, rag_available)
    """
    config_manager = get_config_manager()
    config = config_manager.load_config()
    
    return check_models(config)

