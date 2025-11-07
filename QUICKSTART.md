# AZUL Quick Start Guide

## 🚀 Get Started in 3 Steps

### Step 1: Install Dependencies

```bash
# Install Poetry (Python package manager)
curl -sSL https://install.python-poetry.org | python3 -

# Install Bun (JavaScript runtime)
curl -fsSL https://bun.sh/install | bash

# Install Python dependencies
cd azul-backend
poetry install

# Install Node dependencies
cd ../azul-ui
bun install
```

**⏱️ Expected time**: 5-15 minutes (llama-cpp-python compilation takes the longest)

### Step 2: Verify Model

Make sure you have the model file:

```bash
ls models/qwen2.5-coder-7b-instruct-q4_k_m.gguf
```

If the model is missing, download a GGUF model and place it in the `models/` directory.

### Step 3: Launch AZUL

```bash
cd /path/to/Azul_CLI
python azul.py
```

That's it! 🎉

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
Try with explicit flags:
```bash
# macOS Metal (GPU)
CMAKE_ARGS="-DLLAMA_METAL=on" poetry install

# CUDA (NVIDIA GPU)
CMAKE_ARGS="-DLLAMA_CUBLAS=on" poetry install
```

## 🔧 Manual Testing

Test each component separately:

**Backend only**:
```bash
cd azul-backend/src
python -m azul_core.server
```

**Frontend only** (start backend first):
```bash
cd azul-ui
bun run src/main.tsx
```

## 📚 Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Explore the architecture in [BACKEND_ARCHITECTURE.md](BACKEND_ARCHITECTURE.md)
- Check out the UI design in [AZUL_ESTETHIC.md](AZUL_ESTETHIC.md)

---

**Happy coding with AZUL! 🎨**

