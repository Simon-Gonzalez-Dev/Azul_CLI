"""Ollama client with streaming support."""

import ollama
from typing import Iterator, Optional, List, Dict, Any
from rich.console import Console

from azul.config.manager import get_config_manager
from azul.formatter import get_formatter


class OllamaClient:
    """Client for interacting with Ollama API."""
    
    SYSTEM_PROMPT = """You are AZUL, an AI coding assistant powered by local LLMs. You help users with coding tasks, file editing, code explanations, and documentation.

FILE OPERATIONS:

1. EDITING A FILE: When asked to edit a file, you MUST provide the changes in unified diff format inside a single markdown code block labeled `diff`. The format should be:

```diff
--- a/filename
+++ b/filename
@@ -line,count +line,count @@
 context line
-old line
+new line
 context line
```

2. CREATING A FILE: When asked to create a file, you MUST provide the file content in a markdown code block with the label `file:filename`. The format should be:

```file:filename
// File content here
```

3. DELETING A FILE: When asked to delete a file, you MUST indicate it with a markdown code block labeled `delete:filename`. The format should be:

```delete:filename
```

For other tasks (explanations, documentation, etc.), provide clear, helpful responses in markdown format.

Be conversational and context-aware. Reference files and code naturally when the user mentions them."""
    
    def __init__(self):
        """Initialize Ollama client."""
        self.config = get_config_manager()
        self.console = Console()
        self.formatter = get_formatter()
        self._check_connection()
    
    def _check_connection(self) -> bool:
        """Check if Ollama server is available."""
        try:
            ollama.list()  # This will raise an exception if server is not available
            return True
        except Exception as e:
            self.formatter.print_error(
                f"Could not connect to Ollama server: {e}\n"
                "Please ensure Ollama is running. Start it with: ollama serve"
            )
            return False
    
    def get_model(self) -> str:
        """Get the current model name."""
        return self.config.get_model()
    
    def set_model(self, model: str) -> bool:
        """
        Set the model to use.
        
        Args:
            model: Model name
            
        Returns:
            True if model is available, False otherwise
        """
        try:
            # Check if model exists
            models_response = ollama.list()
            
            # Handle different response structures
            model_names = []
            if isinstance(models_response, dict):
                models_list = models_response.get("models", [])
            elif isinstance(models_response, list):
                models_list = models_response
            else:
                models_list = []
            
            for m in models_list:
                if isinstance(m, dict):
                    name = m.get("name") or m.get("model")
                    if name:
                        model_names.append(name)
                elif isinstance(m, str):
                    model_names.append(m)
            
            # Check for exact match or partial match
            if model in model_names:
                self.config.set_model(model)
                self.formatter.print_success(f"Model changed to: {model}")
                return True
            else:
                # Try to find similar models
                similar = [m for m in model_names if model.lower() in m.lower()]
                if similar:
                    self.formatter.print_warning(
                        f"Model '{model}' not found. Did you mean: {', '.join(similar[:3])}"
                    )
                else:
                    if model_names:
                        self.formatter.print_error(
                            f"Model '{model}' not found. Available models: {', '.join(model_names[:5])}"
                        )
                    else:
                        self.formatter.print_error(f"Model '{model}' not found.")
                return False
        except Exception as e:
            self.formatter.print_error(f"Error checking models: {e}")
            return False
    
    def _build_messages(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Build messages list for Ollama API."""
        messages = []
        
        # Add system prompt
        if system_prompt is None:
            system_prompt = self.SYSTEM_PROMPT
        
        messages.append({
            "role": "system",
            "content": system_prompt
        })
        
        # Add conversation history
        if conversation_history:
            messages.extend(conversation_history)
        
        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        return messages
    
    def stream_chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None
    ) -> Iterator[str]:
        """
        Stream chat response from Ollama.
        
        Args:
            user_message: User's message
            conversation_history: Previous conversation messages
            system_prompt: Optional custom system prompt
            
        Yields:
            Response tokens as strings
        """
        model = self.get_model()
        
        try:
            messages = self._build_messages(user_message, conversation_history, system_prompt)
            
            response = ollama.chat(
                model=model,
                messages=messages,
                stream=True
            )
            
            for chunk in response:
                if 'message' in chunk and 'content' in chunk['message']:
                    content = chunk['message']['content']
                    if content:
                        yield content
                elif 'error' in chunk:
                    error_msg = chunk.get('error', 'Unknown error')
                    self.formatter.print_error(f"Ollama error: {error_msg}")
                    yield f"\n[Error: {error_msg}]"
        except Exception as e:
            self.formatter.print_error(f"Error communicating with Ollama: {e}")
            import traceback
            self.formatter.print_error(traceback.format_exc())
            yield f"\n[Error: {e}]"
    
    def chat(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Get chat response from Ollama (non-streaming).
        
        Args:
            user_message: User's message
            conversation_history: Previous conversation messages
            system_prompt: Optional custom system prompt
            
        Returns:
            Complete response text
        """
        model = self.get_model()
        
        try:
            messages = self._build_messages(user_message, conversation_history, system_prompt)
            
            response = ollama.chat(
                model=model,
                messages=messages,
                stream=False
            )
            
            return response['message']['content']
        except Exception as e:
            self.formatter.print_error(f"Error communicating with Ollama: {e}")
            return f"Error: {e}"


# Global Ollama client instance
_ollama_client: Optional[OllamaClient] = None


def get_ollama_client() -> OllamaClient:
    """Get the global Ollama client instance."""
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient()
    return _ollama_client

