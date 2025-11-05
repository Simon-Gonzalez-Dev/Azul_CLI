"""Environment checker for validating required models and dependencies."""

import ollama
from typing import Tuple, Optional
from azul.config.manager import get_config_manager
from azul.formatter import get_formatter


def check_models(config) -> Tuple[bool, bool]:
    """
    Check if required models are available.
    
    Args:
        config: Configuration dict
        
    Returns:
        Tuple of (chat_model_available, rag_available)
    """
    try:
        # Get list of available models
        models_response = ollama.list()
        
        # Handle different response structures
        local_models = []
        if isinstance(models_response, dict):
            models_list = models_response.get("models", [])
        elif isinstance(models_response, list):
            models_list = models_response
        else:
            models_list = []
        
        # Extract model names safely
        for m in models_list:
            if isinstance(m, dict):
                model_name = m.get("name") or m.get("model")
                if model_name:
                    local_models.append(model_name)
            elif isinstance(m, str):
                local_models.append(m)
        
        # Check chat model - if not found, still allow continuation
        chat_model = config.get("model", "qwen2.5-coder:14b")
        chat_available = chat_model in local_models if local_models else True  # Allow if can't check
        
        # RAG removed - return False for rag_available
        return chat_available, False
        
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

