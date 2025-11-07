# AZUL Installation Guide

## ⚡ Quick Setup (Recommended)

**For the fastest setup, use the automated script:**

```bash
./setup.sh
```

This script will automatically:
- Create the `azul_env` virtual environment
- Install all Python dependencies
- Install Bun (if needed)
- Install frontend dependencies
- Verify everything is ready

**Skip to "First Launch" section below if using the script.**

---

## Manual Installation

If you prefer to install manually or need more control, follow the steps below.

- **Operating System**: macOS, Linux, or Windows (WSL recommended)
- **Python**: 3.10 or higher
- **RAM**: Minimum 8GB (16GB recommended for larger models)
- **Disk Space**: ~10GB free (for dependencies and model)
- **Optional**: NVIDIA GPU with CUDA for faster inference

## Pre-Installation Checklist

Before you begin, verify you have:

- [ ] Python 3.10+ installed (`python3 --version`)
- [ ] Git installed (for cloning if needed)
- [ ] Internet connection (for downloading dependencies)
- [ ] Terminal access

## Step-by-Step Installation

### 1. Create Python Virtual Environment

```bash
# Navigate to project directory
cd /path/to/Azul_CLI

# Create virtual environment
python3 -m venv azul_env

# Activate virtual environment
source azul_env/bin/activate  # On macOS/Linux
# or
azul_env\Scripts\activate  # On Windows
```

Verify activation (you should see `(azul_env)` in your prompt):
```bash
which python  # Should point to azul_env/bin/python
```

### 2. Install Bun (JavaScript Runtime)

**macOS/Linux:**
```bash
curl -fsSL https://bun.sh/install | bash
```

**Windows (PowerShell):**
```powershell
irm bun.sh/install.ps1 | iex
```
Make path visable
```bash
exec /bin/zsh
```

Verify installation:
```bash
bun --version
```

### 3. Install Backend Dependencies

Make sure the virtual environment is activated (you should see `(azul_env)` in your prompt):

```bash
# Upgrade pip first
pip install --upgrade pip setuptools wheel

# Install core dependencies
pip install websockets ">=12.0"
pip install "langchain>=0.1.0"
pip install "langchain-core>=0.1.0"
pip install "langgraph>=0.0.20"
pip install "langchain-community>=0.0.20"
pip install "pydantic>=2.0"
pip install "pydantic-settings>=2.0"

# Install llama-cpp-python (takes 5-10 minutes)
pip install llama-cpp-python
```

**For GPU acceleration** (optional but recommended):

**macOS with Apple Silicon (M1/M2/M3):**
```bash
CMAKE_ARGS="-DLLAMA_METAL=on" pip install llama-cpp-python
```

**Linux/Windows with NVIDIA GPU:**
```bash
CMAKE_ARGS="-DLLAMA_CUBLAS=on" pip install llama-cpp-python
```

**CPU Only (no GPU acceleration):**
```bash
pip install llama-cpp-python
```

**This will install:**
- websockets (WebSocket server)
- llama-cpp-python (LLM inference - **takes 5-10 minutes to compile**)
- langchain (Agent framework)
- langgraph (Agent execution)
- pydantic (Data validation)

### 4. Install Frontend Dependencies

```bash
cd azul-ui
bun install
```

# ink box issue

``` bash
# First, remove the bad entry
bun remove ink-box

# Then, add it back correctly
bun add ink-box
```

**This will install:**
- ink (Terminal UI framework)
- react (UI library)
- ws (WebSocket client)
- ink-text-input (Input component)
- TypeScript and type definitions

### 5. Verify Model File

Check that the model file exists:

```bash
cd ..
ls -lh models/qwen2.5-coder-7b-instruct-q4_k_m.gguf
```

You should see something like:
```
-rw-r--r--  1 user  staff   4.7G  models/qwen2.5-coder-7b-instruct-q4_k_m.gguf
```

**If model is missing**, download a GGUF model:
- Qwen 2.5 Coder: https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF
- Other models: https://huggingface.co/models?search=gguf

Place the downloaded `.gguf` file in the `models/` directory.

## Verification

Test each component separately:

### Test Backend

Make sure the virtual environment is activated:

```bash
source azul_env/bin/activate  # If not already activated
cd azul-backend/src
python -m azul_core.server
```

Or use the venv Python directly:
```bash
azul_env/bin/python -m azul_core.server
```

Expected output:
```
INFO - Starting AZUL server on ws://localhost:8765
INFO - Server started, waiting for connections...
```

Press `Ctrl+C` to stop.

### Test Frontend

Start backend first, then in another terminal:

```bash
cd azul-ui
bun run src/main.tsx
```

You should see the AZUL interface.

## First Launch

From the project root:

```bash
python azul.py
```

You should see:
1. ✅ Dependency checks passing
2. ✅ Backend server starting
3. ✅ Frontend UI launching
4. 🎨 AZUL banner and interface

## Post-Installation Configuration (Optional)

### 1. Create Environment Variables File

```bash
cat > .env << EOF
AZUL_TEMPERATURE=0.7
AZUL_MAX_ITERATIONS=50
AZUL_WEBSOCKET_PORT=8765
EOF
```

### 2. GPU Configuration

Check GPU detection:

```bash
# macOS Metal
system_profiler SPDisplaysDataType | grep Metal

# NVIDIA CUDA
nvidia-smi
```

### 3. Model Configuration

To use a different model, edit `azul-backend/src/azul_core/config.py`:

```python
model_path: Path = Path(__file__).parent.parent.parent.parent / "models" / "your-model.gguf"
```

## Common Installation Issues

### Issue: "azul_env not found"

**Solution**: Run the setup script or create manually
```bash
# Use the automated script
./setup.sh

# Or create manually
python3 -m venv azul_env
source azul_env/bin/activate
```

### Issue: "bun: command not found"

**Solution**: Restart terminal or add to PATH
```bash
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"
```

### Issue: "llama-cpp-python compilation failed"

**Solution**: Install build tools

**macOS:**
```bash
xcode-select --install
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install build-essential cmake
```

**Fedora/RHEL:**
```bash
sudo dnf install gcc gcc-c++ cmake
```

### Issue: "Port 8765 already in use"

**Solution**: Kill existing process
```bash
# macOS/Linux
lsof -ti:8765 | xargs kill -9

# Or change port in config.py
```

### Issue: "Model loads but inference is slow"

**Solutions:**
1. Check GPU acceleration is enabled
2. Use smaller context window in config.py (e.g., `n_ctx = 4096`)
3. Use a smaller model (3B instead of 7B)
4. Reduce `n_batch` in config.py

### Issue: "Out of memory"

**Solutions:**
1. Close other applications
2. Use a smaller model
3. Reduce context window size
4. Enable memory mapping (already default)

## Uninstallation

To remove AZUL:

```bash
# Remove virtual environment
rm -rf azul_env

# Remove Node dependencies
cd azul-ui
rm -rf node_modules

# Remove Bun (optional)
rm -rf ~/.bun
```

## Updates

To update dependencies:

```bash
# Activate virtual environment
source azul_env/bin/activate

# Update backend dependencies
pip install --upgrade websockets langchain langchain-core langgraph langchain-community pydantic pydantic-settings llama-cpp-python

# Update frontend
cd azul-ui
bun update
```

## Support

For issues:
1. Check the troubleshooting section in README.md
2. Verify all dependencies are installed correctly
3. Try running backend and frontend separately
4. Check logs in terminal for error messages

## Next Steps

After successful installation:
1. Read [QUICKSTART.md](QUICKSTART.md) for usage examples
2. Explore the [README.md](README.md) for detailed documentation
3. Try example commands to test functionality
4. Customize tools and configuration to your needs

---

**Installation complete! Welcome to AZUL! 🎉**

