# AZUL Quick Start Guide

## 🚀 Get Started in 2 Steps

### Step 1: Run the Setup Script

The setup script automates everything! It will:
- ✅ Create a Python virtual environment (`azul_env`)
- ✅ Install all Python dependencies
- ✅ Install Bun (if not already installed)
- ✅ Install frontend dependencies
- ✅ Verify the model file

```bash
# Make sure you're in the project root
cd /path/to/Azul_CLI

# Run the setup script
./setup.sh
```

**⏱️ Expected time**: 5-15 minutes (llama-cpp-python compilation takes the longest)

**Note**: The script will automatically detect your platform and enable GPU acceleration if available (Metal on macOS, CUDA on Linux/Windows).

### Step 2: Launch AZUL

The setup script verifies the model automatically. If it's missing, you'll see instructions.

Now launch AZUL:

**Option A: Global command (if installed with sudo)**
```bash
# From ANY directory
azul
```

**Option B: From project directory**
```bash
# From the project root (no need to activate venv manually)
cd /path/to/Azul_CLI
python azul.py
```

**Option C: Using the launcher**
```bash
# From ANY directory
/path/to/Azul_CLI/azul_launcher.sh
```

That's it! 🎉

**Note**: The launcher automatically uses the `azul_env` virtual environment, so you don't need to activate it manually.

## 📝 First Commands to Try

Once AZUL is running, try these:

1. **Simple file creation**:
   ```
   Create a Python file named test.py that prints "Hello, AZUL!"
   ```

2. **Read a file**:
   ```
   Read the contents of README.md
   ```

3. **List directory**:
   ```
   What files are in the current directory?
   ```

4. **Execute a command**:
   ```
   Run "echo Hello from AZUL" in the terminal
   ```

## 🎮 Keyboard Shortcuts

- `Ctrl+T` - Toggle the task plan drawer
- `Ctrl+C` - Exit AZUL

## ⚠️ Common Issues

### "Port 8765 already in use"
Kill any existing AZUL processes:
```bash
lsof -ti:8765 | xargs kill -9
```

### "Model not found"
Ensure the GGUF model is in the `models/` directory:
```bash
ls -lh models/
```

### "llama-cpp-python won't install"
The setup script handles this automatically, but if you're installing manually:

```bash
# macOS Metal (GPU)
CMAKE_ARGS="-DLLAMA_METAL=on" pip install llama-cpp-python

# CUDA (NVIDIA GPU)
CMAKE_ARGS="-DLLAMA_CUBLAS=on" pip install llama-cpp-python
```

## 🔧 Manual Testing

Test each component separately:

**Backend only** (using venv):
```bash
# Activate the virtual environment first
source azul_env/bin/activate

# Then run the server
cd azul-backend/src
python -m azul_core.server
```

**Or use the venv Python directly**:
```bash
azul_env/bin/python -m azul_core.server
```

**Frontend only** (start backend first):
```bash
cd azul-ui
bun run src/main.tsx
```

## 🛠️ Manual Setup (Alternative)

If you prefer to set up manually instead of using the script:

1. **Create virtual environment**:
   ```bash
   python3 -m venv azul_env
   source azul_env/bin/activate
   ```

2. **Install Python dependencies**:
   ```bash
   pip install --upgrade pip
   pip install websockets langchain langchain-core langgraph langchain-community pydantic pydantic-settings
   pip install llama-cpp-python  # May take 5-10 minutes
   ```

3. **Install Bun** (if not installed):
   ```bash
   curl -fsSL https://bun.sh/install | bash
   exec /bin/zsh  # or restart terminal
   ```

4. **Install frontend dependencies**:
   ```bash
   cd azul-ui
   bun install
   ```

## 📚 Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Explore the architecture in [BACKEND_ARCHITECTURE.md](BACKEND_ARCHITECTURE.md)
- Check out the UI design in [AZUL_ESTETHIC.md](AZUL_ESTETHIC.md)

---

**Happy coding with AZUL! 🎨**

