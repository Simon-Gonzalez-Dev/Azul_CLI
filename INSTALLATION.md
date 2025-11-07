# AZUL Installation Guide

## System Requirements

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

###1. Install poetry ###

The curl installer is now deprecated. The modern, recommended way to install Python command-line applications like Poetry is with a tool called pipx. This tool installs applications into their own isolated environments, so their dependencies never conflict with each other or your global Python.
This is the most robust and future-proof solution.
**Step 1: Clean Up the Old Installation**
First, we need to completely remove the installation made by the old script to prevent any conflicts.
code
Bash
# This command removes the binaries and the environment created by the old installer
rm -rf "$HOME/.local/bin/poetry"
rm -rf "$HOME/Library/Application Support/pypoetry"
You should also remove the export PATH="$HOME/.local/bin:$PATH" line from your shell's startup file (e.g., ~/.zshrc, ~/.bash_profile) if you added it there, as pipx will provide its own instructions.
**Step 2: Install pipx**
pipx is the correct tool for this job. You can install it using Homebrew (if you have it) or with Python itself.
code
Bash
# The recommended way is with Homebrew
brew install pipx
pipx ensurepath
After running pipx ensurepath, you may need to restart your terminal for the PATH changes to take effect.
**Step 3: Install Poetry with pipx**
Now, use pipx to install Poetry. pipx will automatically handle creating a clean, compatible environment for it.
code
Bash
pipx install poetry
Step 4: Verify the New Installation
After restarting your terminal or sourcing your profile, test the new installation. This should now work correctly.
code
Bash
poetry --version
This command should now print the Poetry version without any TypeError.

**Add to PATH** (if needed):
```bash
export PATH="$HOME/.local/bin:$PATH"
```

Verify installation:
```bash
poetry --version
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

Verify installation:
```bash
bun --version
```

### 3. Navigate to Project Directory

```bash
cd /Users/simongonzalez/Desktop/AZUL/Azul_CLI
```

### 4. Install Backend Dependencies

```bash
cd azul-backend
poetry install
```

**This will install:**
- websockets (WebSocket server)
- llama-cpp-python (LLM inference - **takes 5-10 minutes to compile**)
- langchain (Agent framework)
- langgraph (Agent execution)
- pydantic (Data validation)

**Troubleshooting llama-cpp-python:**

If installation fails, try platform-specific builds:

**macOS with Apple Silicon (M1/M2/M3):**
```bash
CMAKE_ARGS="-DLLAMA_METAL=on" poetry install
```

**Linux/Windows with NVIDIA GPU:**
```bash
CMAKE_ARGS="-DLLAMA_CUBLAS=on" poetry install
```

**CPU Only (no GPU acceleration):**
```bash
CMAKE_ARGS="-DLLAMA_BLAS=OFF -DLLAMA_CUBLAS=OFF -DLLAMA_METAL=OFF" poetry install
```

### 5. Install Frontend Dependencies

```bash
cd ../azul-ui
bun install
```

**This will install:**
- ink (Terminal UI framework)
- react (UI library)
- ws (WebSocket client)
- ink-text-input (Input component)
- TypeScript and type definitions

### 6. Verify Model File

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

```bash
cd azul-backend/src
python -m azul_core.server
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

### Issue: "poetry: command not found"

**Solution**: Add Poetry to PATH
```bash
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc  # or ~/.bashrc
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
# Remove Python dependencies
cd azul-backend
poetry env remove --all

# Remove Node dependencies
cd ../azul-ui
rm -rf node_modules

# Remove Poetry and Bun (optional)
curl -sSL https://install.python-poetry.org | python3 - --uninstall
rm -rf ~/.bun
```

## Updates

To update dependencies:

```bash
# Update backend
cd azul-backend
poetry update

# Update frontend
cd ../azul-ui
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

