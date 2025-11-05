"""High-performance llama.cpp client optimized for maximum speed."""

from typing import Iterator, Optional, List, Dict
import os
from pathlib import Path

try:
    from llama_cpp import Llama
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False

from azul.config.manager import get_config_manager
from azul.formatter import get_formatter


def _get_azul_package_dir() -> Path:
    """Get the azul package directory where models folder is located."""
    import azul
    # Get the directory containing azul package
    package_dir = Path(azul.__file__).parent
    return package_dir


class LlamaClient:
    """High-performance client for llama.cpp models, optimized for speed."""
    
    # Optimized system prompt - shorter for faster processing
    SYSTEM_PROMPT = """You are AZUL, an expert AI coding partner integrated into a command-line interface. Your primary goal is to help the user write, understand, and refactor code efficiently and safely.

*** CORE DIRECTIVES ***
1.  **Be Concise:** Your responses should be code-focused and to the point. Avoid conversational filler.
2.  **Ask for Clarity:** If a user's request is ambiguous, incomplete, or could be interpreted in multiple ways, you MUST ask clarifying questions before proceeding.
3.  **Admit Ignorance:** If you do not know the answer or cannot perform a task, state it clearly. Do not invent information.
4.  **Use Provided Context:** Base your analysis and file modifications on the code context provided in the prompt. Do not assume the existence of files or functions not mentioned.
5.  **No Shell Commands:** You are a code assistant, not a shell. NEVER output shell commands like `rm`, `mv`, or `mkdir` for the user to run. All file operations must use your special formats.

*** STRICT FILE OPERATION RULES ***
When a request requires modifying the filesystem, you MUST respond ONLY with the specified markdown code block and nothing else. Do not add sentences like "Here is the diff:" or "Okay, creating the file:".

1.  **EDITING A FILE:** Provide the changes as a unified diff inside a `diff` block.
    ````diff
    --- a/path/to/original_file.py
    +++ b/path/to/modified_file.py
    @@ -1,5 +1,5 @@
     def some_function():
    -    return "old value"
    +    return "new value"
    ````

2.  **CREATING A FILE:** Provide the full file content inside a `file` block with the target path.
    ````file:path/to/new_file.py
    def new_function():
        ""This is a new file.""
        return True
    ````

3.  **DELETING A FILE:** Indicate the file to be deleted using an empty `delete` block with the target path.
    ````delete:path/to/file_to_delete.log
    ````

*** GENERAL CONVERSATION ***
For all other requests (e.g., explaining code, answering questions, generating ideas), provide clear, well-formatted markdown responses."""
    
    def __init__(self):
        """Initialize llama.cpp client."""
        if not LLAMA_CPP_AVAILABLE:
            raise ImportError(
                "llama-cpp-python is not installed. Install with: "
                "pip install llama-cpp-python"
            )
        
        self.config = get_config_manager()
        self.formatter = get_formatter()
        self._model: Optional[Llama] = None
        self._model_path: Optional[str] = None
        
        # Cache system prompt to avoid repeated string operations
        self._cached_system_prompt = self.SYSTEM_PROMPT
        
        # Get azul package directory for models folder
        self._azul_package_dir = _get_azul_package_dir()
        
        # Load model path from config
        model_path = self.config.get("model_path", None)
        if model_path and os.path.exists(model_path):
            self.set_model_path(model_path)
        else:
            # Try default model - prioritize azul/models/ folder first
            default_model = "qwen2.5-coder-7b-instruct-q4_k_m.gguf"
            possible_paths = [
                str(self._azul_package_dir / "models" / default_model),  # azul/models/ first
                os.path.join(os.path.expanduser("~"), "models", default_model),  # ~/models/ second
                os.path.join(os.path.expanduser("~"), default_model),  # ~/ third
                default_model,  # Current directory last
            ]
            
            model_found = False
            for path in possible_paths:
                if os.path.exists(path):
                    self.set_model_path(path)
                    model_found = True
                    break
            
            if not model_found:
                expected_path = self._azul_package_dir / "models" / default_model
                self.formatter.print_warning(
                    f"\n[bold yellow]Model not found in default locations.[/bold yellow]\n"
                    f"Expected: {expected_path}\n"
                    f"Please set model path with: @model /path/to/{default_model}\n"
                )
    
    def _load_model(self, model_path: str) -> bool:
        """Load model with optimized settings for M4 Mac."""
        try:
            if not os.path.exists(model_path):
                return False
            
            # Skip reload if same model
            if self._model_path == model_path and self._model is not None:
                return True
            
            # Unload existing model
            if self._model is not None:
                del self._model
                self._model = None
            
            # Show loading message
            self.formatter.print_info(f"Loading model: {os.path.basename(model_path)}...")
            
            # Maximum performance settings for M4 Mac (Metal GPU)
            # CRITICAL: n_gpu_layers=-1 offloads ALL layers to GPU
            # Suppress verbose Metal kernel warnings for clean output
            import contextlib
            import io
            
            # Capture stderr to suppress Metal initialization warnings (these are normal and harmless)
            with contextlib.redirect_stderr(io.StringIO()):
                self._model = Llama(
                    model_path=model_path,
                    # CRITICAL: This MUST be -1 to offload all layers to the GPU.
                    # If this is 0 or a small number, you will get CPU performance.
                    n_gpu_layers=-1,       # Full Metal GPU acceleration
                    
                    # Performance Tuning: These help feed the GPU faster.
                    n_ctx=4096,            # Optimal context window
                    n_batch=4096,          # Make this large to speed up prompt processing.
                    
                    # Memory Optimization for Apple Silicon
                    use_mlock=True,        # Prevent swapping to the SSD.
                    use_mmap=True,         # Use efficient memory mapping.
                    
                    verbose=False,         # Set to True temporarily to see debug info on load.
                                           # Look for "llm_load_tensors: offloaded X/X layers to GPU"
                )
            
            self._model_path = model_path
            self.formatter.print_success(f"Model loaded: {os.path.basename(model_path)}")
            return True
            
        except Exception as e:
            self.formatter.print_error(f"Error loading model: {e}")
            self._model = None
            self._model_path = None
            return False
    
    def get_model(self) -> str:
        """Get current model name."""
        if self._model_path:
            return os.path.basename(self._model_path)
        return "Not loaded"
    
    def set_model_path(self, model_path: str) -> bool:
        """
        Set and load model path - optimized path resolution.
        Supports: absolute paths, relative paths, model names, and azul/models/ folder.
        """
        original_path = model_path
        model_path = os.path.expanduser(model_path)
        
        # Resolve relative paths - check multiple locations efficiently
        if not os.path.isabs(model_path):
            # If path contains "models/", extract just the filename
            if "models/" in model_path:
                model_path = os.path.basename(model_path)
            
            # Priority order for path resolution:
            # 1. azul/models/ folder (most common location)
            azul_models_path = self._azul_package_dir / "models" / model_path
            if azul_models_path.exists():
                model_path = str(azul_models_path)
            # 2. ~/models/ folder
            elif os.path.exists(os.path.join(os.path.expanduser("~"), "models", model_path)):
                model_path = os.path.join(os.path.expanduser("~"), "models", model_path)
            # 3. Current working directory
            elif os.path.exists(os.path.join(os.getcwd(), model_path)):
                model_path = os.path.join(os.getcwd(), model_path)
            # 4. Home directory
            elif os.path.exists(os.path.join(os.path.expanduser("~"), model_path)):
                model_path = os.path.join(os.path.expanduser("~"), model_path)
        
        # Convert to absolute path for consistency
        if os.path.exists(model_path):
            model_path = os.path.abspath(model_path)
        else:
            self.formatter.print_error(
                f"Model file not found: {original_path}\n"
                f"Searched in: azul/models/, ~/models/, current directory, and home directory"
            )
            return False
        
        # Load the model
        success = self._load_model(model_path)
        if success:
            self.config.set("model_path", model_path)
        return success
    
    def set_model(self, model_path: str) -> bool:
        """Alias for set_model_path."""
        return self.set_model_path(model_path)
    
    def build_prompt(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Build prompt using Qwen's chat template - optimized for speed.
        Uses pre-allocated list and single join for maximum efficiency.
        """
        if system_prompt is None:
            system_prompt = self._cached_system_prompt
        
        # Pre-allocate list with estimated size for efficiency
        # System + user + assistant start + history = ~4 + len(history)
        estimated_size = 4 + (len(conversation_history) if conversation_history else 0)
        parts = []
        parts.append(f"<|im_start|>system\n{system_prompt}<|im_end|>\n")
        
        # Process history efficiently
        if conversation_history:
            # Pre-compute format strings to avoid repeated lookups
            user_format = "<|im_start|>user\n"
            assistant_format = "<|im_start|>assistant\n"
            end_format = "<|im_end|>\n"
            
            for msg in conversation_history:
                role = msg.get('role', '')
                content = msg.get('content', '')
                if role and content:
                    if role == 'user':
                        parts.append(user_format)
                        parts.append(content)
                        parts.append(end_format)
                    elif role == 'assistant':
                        parts.append(assistant_format)
                        parts.append(content)
                        parts.append(end_format)
        
        # Current user message
        parts.append("<|im_start|>user\n")
        parts.append(user_message)
        parts.append("<|im_end|>\n")
        
        # Assistant response start
        parts.append("<|im_start|>assistant\n")
        
        # Single join - most efficient
        return "".join(parts)
    
    def stream_chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None
    ) -> Iterator[str]:
        """
        Stream chat response - optimized for maximum speed.
        Yields tokens immediately without buffering.
        """
        if self._model is None:
            error_msg = "No model loaded. Use @model to set model path."
            self.formatter.print_error(error_msg)
            yield f"\n[Error: {error_msg}]"
            return
        
        try:
            # Build prompt using Qwen format
            prompt = self.build_prompt(user_message, conversation_history, system_prompt)
            
            # Stream with optimized parameters
            # Higher temperature = more creative, but we optimize for speed
            # repeat_penalty prevents repetition
            # stop tokens for Qwen format
            stream = self._model(
                prompt,
                max_tokens=2048,        # Max tokens per response
                temperature=0.7,       # Balanced creativity/speed
                top_p=0.9,             # Nucleus sampling
                repeat_penalty=1.1,    # Prevent repetition
                stream=True,            # Enable streaming
                stop=["<|im_end|>", "<|im_start|>", "User:", "System:"],  # Stop sequences
            )
            
            # Hot path: maximum speed, zero buffering
            # Direct iteration with minimal attribute access
            for chunk in stream:
                # Single check, direct access - fastest path
                try:
                    text = chunk['choices'][0]['text']
                    if text:
                        yield text
                except (KeyError, IndexError):
                    # Skip malformed chunks silently for speed
                    continue
                        
        except Exception as e:
            self.formatter.print_error(f"Error: {e}")
            yield f"\n[Error: {e}]"
    
    def chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None
    ) -> str:
        """Non-streaming chat (for compatibility)."""
        if self._model is None:
            return "Error: No model loaded."
        
        try:
            prompt = self.build_prompt(user_message, conversation_history, system_prompt)
            
            response = self._model(
                prompt,
                max_tokens=2048,
                temperature=0.7,
                top_p=0.9,
                repeat_penalty=1.1,
                stop=["<|im_end|>", "<|im_start|>", "User:", "System:"],
            )
            
            if response.get('choices'):
                return response['choices'][0].get('text', '')
            return "Error: No response"
                
        except Exception as e:
            return f"Error: {e}"


# Global instance
_llama_client: Optional[LlamaClient] = None


def get_llama_client() -> LlamaClient:
    """Get global llama client instance."""
    global _llama_client
    if _llama_client is None:
        _llama_client = LlamaClient()
    return _llama_client


