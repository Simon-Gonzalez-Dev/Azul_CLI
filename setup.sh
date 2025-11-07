#!/usr/bin/env bash
# AZUL Setup Script
# This script automates the complete setup of AZUL

set -e  # Exit on error

# Colors for output
CYAN='\033[96m'
GREEN='\033[92m'
YELLOW='\033[93m'
RED='\033[91m'
RESET='\033[0m'

# Banner
BANNER="
    █████╗   ███████╗   ██╗   ██╗   ██╗       
   ██╔══██╗   ╚════██╗  ██║   ██║   ██║      
  ███████║    █████╔╝   ██║   ██║   ██║       
 ██╔══██║    ██╔═══╝    ██║   ██║   ██║       
██║  ██║     ███████╗   ╚██████╔╝   ███████╗  
╚═╝  ╚═╝     ╚══════╝    ╚═════╝    ╚══════╝ 
"

echo -e "${CYAN}${BANNER}${RESET}"
echo -e "${CYAN}AZUL Setup Script${RESET}"
echo -e "${CYAN}==================${RESET}\n"

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Function to print status
print_status() {
    echo -e "${GREEN}✓${RESET} $1"
}

print_error() {
    echo -e "${RED}✗${RESET} $1"
}

print_info() {
    echo -e "${YELLOW}ℹ${RESET} $1"
}

# Check Python version
echo "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed. Please install Python 3.10 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
    print_error "Python 3.10 or higher is required. Found: $PYTHON_VERSION"
    exit 1
fi

print_status "Python $PYTHON_VERSION found"

# Step 1: Create virtual environment
echo ""
echo "Step 1: Creating Python virtual environment..."
if [ -d "azul_env" ]; then
    print_info "Virtual environment 'azul_env' already exists. Removing old one..."
    rm -rf azul_env
fi

python3 -m venv azul_env
print_status "Virtual environment 'azul_env' created"

# Step 2: Activate virtual environment and upgrade pip
echo ""
echo "Step 2: Setting up Python environment..."
source azul_env/bin/activate

print_info "Upgrading pip3, setuptools, and wheel..."
pip3 install --upgrade pip3 setuptools wheel || {
    print_error "Failed to upgrade pip3"
    exit 1
}
print_status "pip3 upgraded"

# Step 3: Install Python dependencies
echo ""
echo "Step 3: Installing Python dependencies..."
print_info "This may take 5-15 minutes (llama-cpp-python compilation)..."
print_info "Installing core dependencies..."

# Install dependencies with error checking
echo "  → Installing websockets..."
pip3 install "websockets>=12.0" || {
    print_error "Failed to install websockets"
    exit 1
}

echo "  → Installing langchain..."
pip3 install "langchain>=0.1.0" || {
    print_error "Failed to install langchain"
    exit 1
}

echo "  → Installing langchain-core..."
pip3 install "langchain-core>=0.1.0" || {
    print_error "Failed to install langchain-core"
    exit 1
}

echo "  → Installing langgraph..."
pip3 install "langgraph>=0.0.20" || {
    print_error "Failed to install langgraph"
    exit 1
}

echo "  → Installing langchain-community..."
pip3 install "langchain-community>=0.0.20" || {
    print_error "Failed to install langchain-community"
    exit 1
}

echo "  → Installing pydantic..."
pip3 install "pydantic>=2.0" || {
    print_error "Failed to install pydantic"
    exit 1
}

echo "  → Installing pydantic-settings..."
pip3 install "pydantic-settings>=2.0" || {
    print_error "Failed to install pydantic-settings"
    exit 1
}

print_status "Core dependencies installed"

# Install llama-cpp-python (this takes the longest)
echo ""
print_info "Installing llama-cpp-python (this will take several minutes)..."
print_info "If you have a GPU, it will be automatically detected and used."

# Detect platform and set appropriate CMAKE args
CMAKE_ARGS=""
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS - check for Apple Silicon
    if [[ $(uname -m) == "arm64" ]]; then
        CMAKE_ARGS="-DLLAMA_METAL=on"
        print_info "Detected macOS Apple Silicon - enabling Metal GPU acceleration"
    fi
elif command -v nvidia-smi &> /dev/null; then
    CMAKE_ARGS="-DLLAMA_CUBLAS=on"
    print_info "Detected NVIDIA GPU - enabling CUDA acceleration"
fi

echo "  → Installing llama-cpp-python (this may take 5-10 minutes)..."
if [ -n "$CMAKE_ARGS" ]; then
    CMAKE_ARGS="$CMAKE_ARGS" pip3 install llama-cpp-python || {
        print_error "Failed to install llama-cpp-python with GPU support. Trying CPU-only build..."
        pip3 install llama-cpp-python || {
            print_error "Failed to install llama-cpp-python"
            print_info "You may need to install build tools: xcode-select --install"
            exit 1
        }
    }
else
    pip3 install llama-cpp-python || {
        print_error "Failed to install llama-cpp-python"
        print_info "You may need to install build tools: xcode-select --install"
        exit 1
    }
fi

print_status "llama-cpp-python installed"

# Step 4: Install Bun if not present
echo ""
echo "Step 4: Setting up Bun (JavaScript runtime)..."
if ! command -v bun &> /dev/null; then
    print_info "Bun not found. Installing Bun..."
    curl -fsSL https://bun.sh/install | bash
    
    # Add Bun to PATH for current session
    export BUN_INSTALL="$HOME/.bun"
    export PATH="$BUN_INSTALL/bin:$PATH"
    
    # Reload shell config if possible
    if [ -f "$HOME/.zshrc" ]; then
        echo 'export BUN_INSTALL="$HOME/.bun"' >> "$HOME/.zshrc"
        echo 'export PATH="$BUN_INSTALL/bin:$PATH"' >> "$HOME/.zshrc"
    elif [ -f "$HOME/.bashrc" ]; then
        echo 'export BUN_INSTALL="$HOME/.bun"' >> "$HOME/.bashrc"
        echo 'export PATH="$BUN_INSTALL/bin:$PATH"' >> "$HOME/.bashrc"
    fi
    
    print_info "Bun installed. You may need to restart your terminal or run: exec \$SHELL"
else
    print_status "Bun already installed"
fi

# Verify Bun is accessible
if ! command -v bun &> /dev/null; then
    print_error "Bun installation failed or not in PATH"
    print_info "Please install Bun manually: curl -fsSL https://bun.sh/install | bash"
    print_info "Then restart your terminal and run this script again"
    exit 1
fi

BUN_VERSION=$(bun --version)
print_status "Bun $BUN_VERSION found"

# Step 5: Install frontend dependencies
echo ""
echo "Step 5: Installing frontend dependencies..."
cd azul-ui

# Remove and reinstall ink-box if needed (fixes common issue)
if [ -d "node_modules" ]; then
    print_info "Removing existing node_modules..."
    rm -rf node_modules
fi

print_info "Running bun install..."
bun install || {
    print_error "Failed to install frontend dependencies"
    print_info "Trying to fix ink-box issue..."
    bun remove ink-box 2>/dev/null || true
    bun add ink-box || {
        print_error "Failed to fix ink-box issue"
        exit 1
    }
    bun install || {
        print_error "Failed to install frontend dependencies after retry"
        exit 1
    }
}

print_status "Frontend dependencies installed"

cd ..

# Step 6: Verify model file
echo ""
echo "Step 6: Verifying model file..."
MODEL_PATH="models/qwen2.5-coder-7b-instruct-q4_k_m.gguf"
if [ -f "$MODEL_PATH" ]; then
    MODEL_SIZE=$(ls -lh "$MODEL_PATH" | awk '{print $5}')
    print_status "Model file found: $MODEL_SIZE"
else
    print_error "Model file not found at: $MODEL_PATH"
    print_info "Please download a GGUF model and place it in the models/ directory"
    print_info "Download from: https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"
fi

# Step 7: Create activation script
echo ""
echo "Step 7: Creating activation helper..."
cat > activate_azul.sh << 'EOF'
#!/bin/bash
# AZUL Environment Activation Script
# Source this file to activate the AZUL environment

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/azul_env/bin/activate"

# Add Bun to PATH if not already there
if [ -d "$HOME/.bun/bin" ] && [[ ":$PATH:" != *":$HOME/.bun/bin:"* ]]; then
    export BUN_INSTALL="$HOME/.bun"
    export PATH="$BUN_INSTALL/bin:$PATH"
fi

echo "AZUL environment activated!"
echo "Python: $(which python)"
echo "Bun: $(which bun 2>/dev/null || echo 'not in PATH')"
EOF

chmod +x activate_azul.sh
print_status "Activation script created: activate_azul.sh"

# Step 8: Create global launcher
echo ""
echo "Step 8: Creating global launcher..."

# Create a wrapper script that can be called from anywhere
cat > azul_launcher.sh << 'LAUNCHER_EOF'
#!/bin/bash
# AZUL Global Launcher
# This script can be called from anywhere

# Get the directory where AZUL is installed
AZUL_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Run azul.py from the AZUL directory
cd "$AZUL_DIR"
python3 azul.py "$@"
LAUNCHER_EOF

chmod +x azul_launcher.sh
print_status "Global launcher created"

# Step 9: Create symlink in /usr/local/bin if possible
echo ""
echo "Step 9: Setting up global command..."
SYMLINK_TARGET="/usr/local/bin/azul"

if [ -w "/usr/local/bin" ]; then
    ln -sf "$SCRIPT_DIR/azul_launcher.sh" "$SYMLINK_TARGET"
    print_status "Global 'azul' command installed in /usr/local/bin"
    print_info "You can now run 'azul' from any directory!"
elif sudo -n true 2>/dev/null; then
    sudo ln -sf "$SCRIPT_DIR/azul_launcher.sh" "$SYMLINK_TARGET"
    print_status "Global 'azul' command installed in /usr/local/bin (with sudo)"
    print_info "You can now run 'azul' from any directory!"
else
    print_info "Cannot write to /usr/local/bin (no sudo access)"
    print_info "To create global command, run:"
    print_info "  sudo ln -sf $SCRIPT_DIR/azul_launcher.sh /usr/local/bin/azul"
    print_info ""
    print_info "Or add this to your shell config (~/.zshrc or ~/.bashrc):"
    print_info "  alias azul='$SCRIPT_DIR/azul_launcher.sh'"
fi

print_status "Launcher ready (will use azul_env automatically)"

# Summary
echo ""
echo -e "${CYAN}========================================${RESET}"
echo -e "${GREEN}✓ Setup Complete!${RESET}"
echo -e "${CYAN}========================================${RESET}"
echo ""
echo "AZUL is now installed and ready to use!"
echo ""

# Check if global command was installed
if [ -L "/usr/local/bin/azul" ]; then
    echo -e "${GREEN}Launch AZUL from anywhere:${RESET}"
    echo "   ${CYAN}azul${RESET}"
    echo ""
else
    echo "Launch AZUL:"
    echo "   ${CYAN}cd $SCRIPT_DIR${RESET}"
    echo "   ${CYAN}python azul.py${RESET}"
    echo ""
    echo "Or from anywhere:"
    echo "   ${CYAN}$SCRIPT_DIR/azul_launcher.sh${RESET}"
    echo ""
fi

echo "The launcher will automatically:"
echo "  • Use the azul_env virtual environment"
echo "  • Start the backend server"
echo "  • Launch the frontend UI"
echo ""
echo "For manual testing:"
echo "  Backend: ${CYAN}cd $SCRIPT_DIR/azul-backend/src && $SCRIPT_DIR/azul_env/bin/python -m azul_core.server${RESET}"
echo "  Frontend: ${CYAN}cd $SCRIPT_DIR/azul-ui && bun run src/main.tsx${RESET}"
echo ""
echo -e "${YELLOW}Tip: Press Ctrl+C in the UI to exit cleanly${RESET}"
echo ""

