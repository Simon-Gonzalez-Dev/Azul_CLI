"""Configuration management for AZUL backend."""

from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class AzulConfig(BaseSettings):
    """AZUL backend configuration."""
    
    # Model settings
    model_path: Path = Field(
        default=Path(__file__).parent.parent.parent.parent / "models" / "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
        description="Path to the GGUF model file"
    )
    n_ctx: int = Field(default=8192, description="Context window size")
    n_gpu_layers: int = Field(default=-1, description="Number of GPU layers (-1 for all)")
    n_batch: int = Field(default=512, description="Batch size for prompt processing")
    
    # Agent settings
    max_iterations: int = Field(default=50, description="Maximum agent loop iterations")
    temperature: float = Field(default=0.7, description="LLM temperature")
    top_p: float = Field(default=0.9, description="Nucleus sampling threshold")
    repeat_penalty: float = Field(default=1.1, description="Repetition penalty")
    max_tokens: int = Field(default=8192, description="Maximum tokens to generate")
    
    # WebSocket settings
    websocket_host: str = Field(default="localhost", description="WebSocket server host")
    websocket_port: int = Field(default=8765, description="WebSocket server port")
    
    class Config:
        env_prefix = "AZUL_"
        env_file = ".env"


# Global config instance
config = AzulConfig()

