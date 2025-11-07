python3.12 -m venv azul_cli  
source azul_env/bin/activate
pip install -e ".[metal]"   
pip install --upgrade pip   
which azul          
alias azul='source /Users/simongonzalez/Desktop/AZUL/Azul_CLI/venv/bin/activate && azul'
source ~/.zshrc







Setup instructions
Step 1: Create a virtual environment
# Navigate to the project directorycd /Users/simongonzalez/Desktop/AZUL/Azul_CLI# Create a virtual environment (choose one method)python3.12 -m venv venv# Or if you prefer a different namepython3.12 -m venv azul_env
Step 2: Activate the virtual environment
# On macOS/Linux:source venv/bin/activate# Or if you named it azul_env:source azul_env/bin/activate
You should see (venv) or (azul_env) in your terminal prompt.
Step 3: Install AZUL and dependencies
Choose one based on your system:
For Mac (with Metal GPU support - recommended):
pip install -e ".[metal]"
For Linux/Windows (CPU only):
pip install -e .
For NVIDIA GPU (if you have CUDA installed):
pip install -e ".[cuda]"
The -e flag installs in editable mode, so code changes take effect immediately.
Step 4: Verify installation
After installation, the azul command should be available in your terminal:
# Check if azul is installedwhich azul# Or test the commandazul --help
Step 5: Download the model
Before running AZUL, download the model file:
Download qwen2.5-coder-7b-instruct-q4_k_m.gguf from a trusted source (e.g., Hugging Face)
Place it in one of these locations:
azul/models/ (in the project directory)
~/.azul/models/ (create this directory if needed)
~/models/ (create this directory if needed)
Current working directory
Or specify the path when running:
azul --model-path /path/to/your/model.gguf
Step 6: Start the app
Agentic Mode (default - with TUI):
azul
Simple Mode (command-line interface):
simple
azul --simple
With custom model path:
azul --model-path ~/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf
Making azul accessible from any terminal
The azul command is available globally when:
The virtual environment is activated, or
AZUL is installed system-wide
Option A: Always activate the virtual environment
Add this to your ~/.zshrc (or ~/.bashrc on Linux):
# Add this line to your shell config filealias azul='source /Users/simongonzalez/Desktop/AZUL/Azul_CLI/venv/bin/activate && azul'
Then reload your shell:
source ~/.zshrc
Option B: Install system-wide (recommended for global access)
If you want azul available without activating the venv:
# Deactivate virtual environment firstdeactivate# Install system-wide (may require sudo on some systems)pip install -e .# Or with GPU supportpip install -e ".[metal]"
This installs azul into your system Python, making it available from any terminal.
Option C: Use a wrapper script
Create a script at /usr/local/bin/azul (or ~/bin/azul and add to PATH):
#!/bin/bashsource /Users/simongonzalez/Desktop/AZUL/Azul_CLI/venv/bin/activateexec azul "$@"
Make it executable:
chmod +x /usr/local/bin/azul
Quick start checklist
[ ] Python 3.12+ installed
[ ] Virtual environment created and activated
[ ] Dependencies installed (pip install -e ".[metal]" or similar)
[ ] Model file downloaded and placed in a search path
[ ] Test: azul --help works
[ ] Run: azul to start the app
Troubleshooting
If azul command not found:
Ensure the virtual environment is activated
Verify installation: pip list | grep azul
Check entry point: pip show azul should show the console script
If you need to switch to agent mode to make edits, let me know.