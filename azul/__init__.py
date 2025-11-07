"""AZUL - Local Agentic AI Coding Assistant CLI."""

__version__ = "0.1.0"
__author__ = "AZUL Contributors"

from azul.config.manager import ConfigManager
from azul.session_manager import SessionManager
from azul.llama_client import LlamaClient

__all__ = [
    "ConfigManager",
    "SessionManager",
    "LlamaClient",
    "__version__",
]

