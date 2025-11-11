1. The Core Concept: System Prompt vs. User Prompt
First, you should structure your CLI tool to differentiate between two types of input:
System Prompt: This is the foundational instruction, role, or context you want the AI to adhere to throughout the entire conversation. It defines its personality, constraints, and goals. This is the part you want to "feed only once."[1][2][3]
User Prompt: This is the specific, dynamic input the user provides at each turn (e.g., "hi", "what's the weather?").[4]
By separating these, you create a clear structure where the system prompt provides a consistent framework for every interaction.[2]
2. The Efficiency Trick: Key-Value (KV) Caching
This is the technical solution that makes your goal possible. Modern LLM inference engines are optimized to avoid redundant work. The most important optimization here is the KV Cache.[5]
Here's how it works in simple terms:
First Input: When you send the initial System Prompt + first User Input, the model processes it and calculates a set of internal states (called key-value tensors) for every token. This is the "slow" part.
Caching the State: The model's inference engine automatically saves, or caches, these calculated states in memory (often on the GPU).[6]
Subsequent Inputs: When you send the next input (System Prompt + History + new User Input), the engine is smart. It sees that the first part of the prompt is identical to what it just processed. Instead of re-calculating everything, it instantly loads the cached states and only computes the new values for the new user input.[5][7]
This means that even though you are technically re-sending the system prompt and history, the computational cost is minimal after the first turn. The performance hit is only for the new text, not the entire context. This gives you the speed and efficiency you're looking for without the model having to be truly "stateful."[6]
How to Implement This Efficiently
Here is the best way to manage memory and structure your CLI tool, ensuring your reset command still works perfectly.
Define Your Base System Prompt:
In your code, have a constant or variable that holds your main instruction set. This never changes unless the user explicitly modifies it.
code
Python
# This is the instruction you want to "feed once"
SYSTEM_PROMPT = "You are a helpful command-line assistant. You are concise and accurate."
Maintain a Separate Conversation History:
Use a list to store the history of user and assistant messages. This is your tool's short-term memory.
code
Python
conversation_history = []
Combine for Inference on Each Turn:
For every new user input, combine the system prompt, the managed history, and the new message.
code
Python
def get_full_prompt(new_user_input):
  # Format the history into a string
  history_string = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history])
  
  # Combine everything
  return f"{SYSTEM_PROMPT}\n{history_string}\nuser: {new_user_input}\nassistant:"

# --- On user input ---
user_input = "hi" 
full_prompt = get_full_prompt(user_input)

# Send full_prompt to your local model
# The model's backend will use the KV cache to process it efficiently

# Add the new messages to history
conversation_history.append({"role": "user", "content": user_input})
# ... after getting the model's response ...
conversation_history.append({"role": "assistant", "content": model_response})
Implement the reset Command:
Your reset command now has a very simple and clear job: clear the conversation history.
code
Python
def reset_memory():
  global conversation_history
  conversation_history = []
  print("Memory has been reset.")
When reset is called, the history is wiped. The next user input will be combined with only the original system prompt, effectively starting a fresh conversation while preserving the AI's core instructions.
By adopting this structure, you get the best of both worlds:
Efficiency: You leverage the power of KV caching in your local model, so the static system prompt and old history don't cause significant slowdowns.[5][8]
Clarity: Your code cleanly separates the AI's core instructions from the conversational history.
Control: Your reset command works reliably by targeting the exact component that needs to be cleared—the conversation history.
