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
