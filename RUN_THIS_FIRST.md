# 🚀 AZUL - Quick Start

## Step 1: Run Setup

```bash
cd /Users/simongonzalez/Desktop/AZUL/Azul_CLI
./setup.sh
```

**⏱️ This takes 5-15 minutes** (llama-cpp-python compiles from source)

You'll now see:
- ✅ Which packages install successfully
- ❌ Which packages fail (if any)
- Real-time progress updates

## Step 2: Launch AZUL

After setup completes successfully:

### If you saw "Global 'azul' command installed":
```bash
azul
```
You can run this from **any directory**!

### If global command wasn't installed:
```bash
cd /Users/simongonzalez/Desktop/AZUL/Azul_CLI
python azul.py
```

## Common Issues

### "Python dependencies not installed in azul_env"

This means setup didn't complete. Run `./setup.sh` again and watch for errors.

### "Failed to install llama-cpp-python"

You may need Xcode Command Line Tools:
```bash
xcode-select --install
```

Then run `./setup.sh` again.

### "Port 8765 already in use"

Another AZUL instance is running:
```bash
lsof -ti:8765 | xargs kill -9
```

## Creating a Global Alias (Optional)

If setup couldn't create `/usr/local/bin/azul`, add this to `~/.zshrc`:

```bash
alias azul='/Users/simongonzalez/Desktop/AZUL/Azul_CLI/azul_launcher.sh'
```

Then reload:
```bash
source ~/.zshrc
```

Now `azul` works from anywhere!

## Verify Installation

```bash
source /Users/simongonzalez/Desktop/AZUL/Azul_CLI/azul_env/bin/activate
python -c "import websockets, llama_cpp, langchain; print('✅ All dependencies OK!')"
```

## Need Help?

- 📖 Full docs: `README.md`
- 🚀 Quick guide: `QUICKSTART.md`
- 🔧 Detailed setup: `INSTALLATION.md`
- 📋 What changed: `SETUP_CHANGES.md`

