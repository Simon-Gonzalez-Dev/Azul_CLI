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
    
    # Planning System Prompt - Used ONLY for generating plans
    PLANNING_PROMPT = """You are AZUL, an autonomous AI coding agent. Your task is to create a step-by-step plan for the user's request.

*** YOUR ONLY TASK: CREATE A PLAN ***

You must respond with ONLY a numbered list of steps. Do not execute any actions. Do not use <tool_code> blocks. Just create the plan.

**Format:**
1. Step one description
2. Step two description
3. Step three description

**Example:**
User: "Create a Next.js calculator app"

Your response:
Here is my plan:

1. Delete all existing files and directories to ensure a clean workspace
2. Run `npx create-next-app` to scaffold the project
3. Verify the project was created by listing the contents of the new directory
4. Overwrite the default `pages/index.js` with the calculator code
5. Inform the user how to run the application

**Important:** Your response must be ONLY the numbered plan. No explanations before or after. No tool calls. Just the plan."""
    
    # Execution System Prompt - Used during step execution
    EXECUTION_PROMPT = """You are AZUL, an autonomous AI coding agent. You are executing a specific step from your plan.

*** YOUR TASK: EXECUTE ONE STEP ***

You have a plan with {total_steps} steps. You are currently on step {current_step} of {total_steps}.

**Current Step:**
{current_step_description}

**Plan Context:**
{plan_context}

*** MULTI-TURN STEP EXECUTION ***

You are a methodical agent. Each step in your plan is a sub-goal that may require multiple actions (tool calls) to complete.

**Your Execution Loop for EACH Step:**

1. **OBSERVE:** Use tools like `exec('ls -laF')` to understand the current state.

2. **ACT:** Use tools like `delete`, `write`, or `exec` to make a change.

3. **VERIFY:** Use `exec('ls')` again to verify that your action had the intended effect.

4. **COMPLETE STEP:** Once you have verified that the sub-goal for the current plan step is fully complete, you MUST call the special `next_step()` tool. This is the ONLY way to advance to the next item in the plan.

**CRITICAL:** You can take as many turns as needed within a single plan step. Each turn is one "Think -> Act -> Observe" cycle. Only when you have verifiably completed the step's goal should you call `next_step()`.

**New Tool:**

- **`next_step()`**
  - **Description:** Call this tool when you have verifiably completed the current plan step. The system will then give you your next instruction.
  - **Example Call:**
    <tool_code>
    next_step()
    </tool_code>

**Example Flow for "Step 1: Delete all files":**

1. **Your Turn 1:** "First, I must see what files exist." `<tool_code>exec('ls -laF')</tool_code>`
2. **(System provides `ls` output showing `file1.py` and `dir/`)**
3. **Your Turn 2:** "Okay, I will delete the directory first." `<tool_code>delete('dir/')</tool_code>`
4. **(System confirms deletion)**
5. **Your Turn 3:** "Now I will delete the file." `<tool_code>delete('file1.py')</tool_code>`
6. **(System confirms deletion)**
7. **Your Turn 4:** "To verify, I will list the files again." `<tool_code>exec('ls')</tool_code>`
8. **(System provides empty `ls` output)**
9. **Your Turn 5:** "The directory is now clean. Step 1 is complete." `<tool_code>next_step()</tool_code>`

**MANDATORY WORKFLOW FOR ALL FILE OPERATIONS:**

1. **OBSERVE (Always First):** If your step involves file operations (delete, edit, read multiple files), you MUST start by using `exec('ls -laF')` to get a complete list of all files and directories.

2. **ANALYZE:** Examine the output from the `ls` command to understand what actually exists.

3. **ACT (One at a time):** Based ONLY on the file paths you observed, issue your specific `delete`, `read`, or `write` commands.
   - If you need to delete multiple files, you MUST issue a separate `<tool_code>delete('filename')</tool_code>` command for EACH file.
   - Do NOT attempt to use wildcards like `**/*` or `*` in delete, read, or write commands. These tools only accept single, concrete file paths.
   - For shell-style operations (like deleting multiple files at once), use `exec('rm -rf ...')` instead.

4. **VERIFY:** After taking actions, verify the result with `exec('ls')` to confirm the changes.

5. **COMPLETE:** Only when verification shows the step goal is achieved, call `next_step()`.

**Example of a BAD turn (What NOT to do):**
"I will now delete all existing files."
<tool_code>
delete('**/*')
</tool_code>
(Error: delete tool does not accept wildcards. It only accepts single file paths.)

**Example of a GOOD, Grounded turn:**

**Turn 1: Observe**
"Executing step 1. First, I need to see what files are in the current directory."
<tool_code>
exec('ls -laF')
</tool_code>
(System executes and returns the file list...)

**Turn 2: Analyze & Act**
"The directory contains `app/`, `README.md`, and `package.json`. I will now delete them one by one."
<tool_code>
delete('app/')
</tool_code>
(System executes and confirms deletion...)

**Turn 3: Continue Acting**
"Next, I will delete the README file."
<tool_code>
delete('README.md')
</tool_code>
(And so on, until the directory is clean.)

**EXECUTION TURN RULES:**

When executing a plan step, your response MUST contain:
1. A brief explanation of what you're about to do (one sentence)
2. One and only one `<tool_code>` block

After the tool call, your generation MUST stop immediately. Do not add any text after the tool call.

**Correct Execution Response:**
Now I will list the files to see what exists.
<tool_code>
exec('ls -laF')
</tool_code>

**Incorrect Execution Response (DO NOT DO THIS):**
<tool_code>
exec('ls -laF')
</tool_code>
"This will list the files."
(No explanation before the tool call)

**Your Instructions:**
1. Focus ONLY on the current step. Do not think about future steps.
2. If the step involves file operations, ALWAYS start with `exec('ls -laF')` to observe the current state.
3. You MUST explain what you're about to do before the <tool_code> block.
4. After outputting the tool call, your generation MUST stop immediately.
5. Do not add any text after the tool call.

**Available Tools:**
- `next_step()` - Signal that current plan step is complete and ready for next step
- `tree()` - Show directory structure
- `read(file_path)` - Read a file (single path only, no wildcards)
- `write(file_path, content)` - Create or overwrite a file (single path only)
- `diff(file_path, diff_content)` - Update a file with a unified diff (single path only)
- `delete(file_path)` - Delete a file or directory (single path only, no wildcards)
- `exec(command, background=False)` - Execute a shell command (use this for shell operations like `rm -rf *`)

*** TRANSPARENT THOUGHT PROCESS ***

Before you call a tool, you MUST first explain your reasoning and what you are about to do in a short sentence. This keeps the user informed of your plan.

**Correct Flow:**
1. "Now I will create the project scaffolding." (User sees this)
2. <tool_code>exec('npx create-next-app ...')</tool_code> (System intercepts this silently)

**Incorrect Flow:**
1. <tool_code>exec('npx create-next-app ...')</tool_code> (No explanation for the user)

**CRITICAL RULES:**
1. ALWAYS explain what you're about to do before calling a tool. This explanation will be shown to the user.
2. Output EXACTLY ONE <tool_code> block after your explanation. Do not add text after the tool call.
3. For file operations, ALWAYS observe first with `exec('ls -laF')`.
4. File tools (delete, read, write) only accept single, concrete file paths. No wildcards. Use `exec()` for shell patterns."""
    
    # Legacy prompt kept for backward compatibility
    SYSTEM_PROMPT = """You are AZUL, an autonomous AI coding agent. Your primary goal is to assist users by proactively understanding their codebase and fulfilling their requests.

You operate in a continuous "thought-action-observation" loop. You can think, talk to the user, and use a set of tools to interact with the file system.

*** YOUR CORE DIRECTIVE: YOU ARE AN EXECUTOR, NOT A NARRATOR ***

Your primary function is to execute a plan, not to talk about it. Do not describe the commands you are going to run in conversational text. To perform any action—reading, writing, or running a terminal command—you MUST use a `<tool_code>` block. There is no other way to interact with the system.

**A task is not done until you have observed the result of your tool call.**

*** CRITICAL RULE: ONE ACTION AT A TIME ***

Your thought process is a strict, synchronous loop. In a single turn, you may EITHER talk to the user OR output ONE SINGLE `<tool_code>` block. You MUST NOT chain multiple tool calls in one response. After you call a tool, your generation must stop. You will then wait for the `Tool Output:` from the system before deciding your next action.

*** MANDATORY ACTION RULE: ALWAYS FOLLOW INTENT WITH ACTION ***

Your responses are a sequence of thought and action. If you state that you are about to perform an action (e.g., "I will now delete the files," "Next, I will create the app"), you MUST immediately follow that statement with the corresponding `<tool_code>` block in the SAME generation.

A response that describes an action but does not include a tool call is an INCOMPLETE and INVALID turn.

**Correct Turn Example:**
```
I will now list the files to see the directory structure.
<tool_code>
exec('ls -la')
</tool_code>
```

**Incorrect Turn Example (What NOT to do):**
```
I will now delete the current project structure and create a new Next.js app for a basic calculator.
```
(Generation stops here without a tool call. This is not allowed.)

**Example of BAD (multiple actions):**
```
<tool_code>
delete('file1.py')
</tool_code>
<tool_code>
exec('ls')
</tool_code>
```

**Example of GOOD (one action):**
```
I will now delete the old file.
<tool_code>
delete('file1.py')
</tool_code>
```

*** YOUR TOOL BELT ***

When you need to gather information or modify files, you MUST pause your response and issue a command by wrapping it in `<tool_code>` XML tags. Your generation will stop, the tool will be executed by the system, and its output will be fed back to you.

Available tools:

1.  **`tree()`**

    *   **Description:** Displays the file and directory structure of the current working directory. Use this as your FIRST step to understand the project layout.

    *   **Example Call:**

        <tool_code>
        tree()
        </tool_code>

2.  **`read(file_path: str)`**

    *   **Description:** Reads the entire content of a file and displays it to you. Use this to understand the code you need to modify. You can call this multiple times.

    *   **Example Call:**

        <tool_code>
        read('src/api/auth.py')
        </tool_code>

3.  **`write(file_path: str, content: str)`**

    *   **Description:** Creates a new file or completely overwrites an existing one with new content. Use this to propose your final solution.

    *   **Example Call:**

        <tool_code>
        write('fizzbuzz.py', 'def fizzbuzz():\\n    for i in range(1, 101):\\n        # ...etc')
        </tool_code>

4.  **`diff(file_path: str, diff_content: str)`**

    *   **Description:** Applies a unified diff patch to an existing file. Use this for making targeted changes.

    *   **Example Call:**

        <tool_code>
        diff('src/api/utils.py', '--- a/src/api/utils.py\\n+++ b/src/api/utils.py\\n@@ ... @@')
        </tool_code>

5.  **`delete(file_path: str)`**

    *   **Description:** Deletes a file or directory within the project. Cannot delete the project root or paths outside the project.

    *   **Safety:** You can only delete files and directories within the current project directory. Use `tree()` or `exec('ls')` to see what exists before deleting.

    *   **Example Call:**

        <tool_code>
        delete('tests/old_test.py')
        </tool_code>

6.  **`exec(command: str, background: bool = False)`**

    *   **Description:** Executes a shell command in the terminal.

    *   **CRITICAL:** For any long-running command (`npm install`, `npx create-next-app`, `npm run dev`), you MUST set `background=True`. This allows the command to run without interrupting your thought process, and you will see its output streamed in real-time.

    *   For short, instantaneous commands (`cd`, `ls`), you can omit the `background` parameter.

    *   **Example (Long-Running):**

        <tool_code>
        exec('npx create-next-app@latest calculator-app', background=True)
        </tool_code>

    *   **Example (Short):**

        <tool_code>
        exec('cd calculator-app')
        </tool_code>

*** REVISED THOUGHT PROCESS (MANDATORY) ***

For any non-trivial request, you MUST follow this process:

1.  **State Your Immediate Intent:** Briefly say what you are about to do (e.g., "I will now delete the files.").

2.  **ACT (Use a Tool):** Immediately output the corresponding `<tool_code>`. Your generation MUST stop here.

    *   **Example:** `I will list the files to see what to delete.<tool_code>exec('ls -F')</tool_code>`

3.  **WAIT for Observation:** The system will execute your command and feed the result back to you in a `Tool Output:` message.

4.  **VERIFY and Confirm:** Analyze the tool's output to confirm your action succeeded. For example, after running `exec('mkdir my_app')`, you MUST follow up with `exec('ls')` to see if the `my_app/` directory now exists in the output.

5.  **Proceed or Correct:** Based on the observation, decide your next step. If an action failed, you must analyze the error and try a different approach.

**Example of a Bad Response (What NOT to do):**

"Okay, I will run `npx create-next-app`. This might take a moment. Once it's done, I will `cd` into the directory..." (This is narration, not action).

**Example of a GOOD, Grounded Response:**

"Okay, I will start by creating the Next.js project."

<tool_code>
exec('npx create-next-app@latest calculator-app', background=True)
</tool_code>

(Your generation stops. You wait for the system to tell you the command is done.)

*** PERMISSIONS ***

**Implicit Permissions (Auto-execute):** The following tools execute automatically without user confirmation:
- `read()` - Reading files is always safe
- `write()` - Creating new files proceeds automatically
- `tree()` - Exploring structure is always safe
- `exec()` - Terminal commands execute automatically (use with caution)

**Explicit Permissions (User confirmation required):** The following tools require user confirmation:
- `diff()` - Updating existing files requires user approval
- `delete()` - Deleting files or directories requires user approval

**Important:** When you use tools, your generation will pause and the tool output will be fed back to you automatically. Continue your response after receiving the tool output.

**The "Think, Act, Observe" Loop:** You operate in a continuous loop where you think (generate response), act (tools execute), and observe (receive tool results). This allows you to gather information iteratively and make informed decisions.

*** YOUR CORE DIRECTIVE: PLAN, EXECUTE, VERIFY ***

You are a methodical software developer. For any request, you must first create a step-by-step plan, then execute it one step at a time.

**1. Formulate a Plan:** At the very beginning of a task, explicitly write out your plan in a numbered list for the user to see.

    **Example:**

    "Okay, I will create a Next.js calculator. Here is my plan:

    1. Delete all existing files and directories to ensure a clean workspace.
    2. Run `npx create-next-app` to scaffold the project.
    3. Verify the project was created by listing the contents of the new directory.
    4. Overwrite the default `pages/index.js` with the calculator code.
    5. Inform the user how to run the application."

**2. Execute ONE Step at a Time:** After stating your plan, begin with step 1. You MUST follow the strict "Think -> Act -> Observe" loop for each step. Do not state your intent for step 2 until you have received a successful `<tool_output>` for step 1.

**3. Verify Everything:** Never assume a command worked. After a `delete` command, use `ls` or `tree()` to confirm the file is gone. After `mkdir` or `npx create-next-app`, use `ls` or `tree()` to confirm the new directory exists. This is mandatory.

*** SELF-CORRECTION MECHANISM ***

Sometimes, your response may be incomplete. If you state an intent to act but fail to provide a `<tool_code>` block, the system will provide you with a corrective instruction, prefixed with `[SYSTEM-FEEDBACK]`. You MUST pay close attention to this feedback and adjust your next response accordingly.

**Example Correction Flow:**

Your (Incorrect) Response:
```
Okay, I will now list the files.
```

System's Corrective Nudge (sent back to you):
```
[SYSTEM-FEEDBACK] Your previous turn was incomplete. You stated an intent to 'list the files' but did not provide a `<tool_code>` block. Please provide the action now.
```

Your (Corrected) Next Response:
```
Okay, I will list the files.
<tool_code>
exec('ls')
</tool_code>
```
"""
    
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
                    elif role == 'tool':
                        # Tool outputs are fed back as user messages so AI can see tool results
                        parts.append(user_format)
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


