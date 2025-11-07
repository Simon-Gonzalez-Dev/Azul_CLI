#!/bin/bash
# AZUL Global Launcher
# This script can be called from anywhere

# Get the directory where AZUL is installed
AZUL_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Run azul.py from the AZUL directory
cd "$AZUL_DIR"
python3 azul.py "$@"
