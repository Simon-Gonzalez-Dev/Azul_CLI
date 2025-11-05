#!/bin/bash
# GPU Performance Fix Script for AZUL CLI
# This script fixes the root cause of slow llama.cpp performance on Apple Silicon

set -e

echo "=========================================="
echo "AZUL CLI GPU Performance Fix"
echo "=========================================="
echo ""

# Step 1: Check if Xcode Command Line Tools need to be reinstalled
echo "Step 1: Checking Xcode Command Line Tools..."
if [ -d "/Library/Developer/CommandLineTools" ]; then
    echo "  ✓ Command Line Tools found at: $(xcode-select -p)"
    echo ""
    echo "  ⚠️  MANUAL STEP REQUIRED:"
    echo "  Please run these commands in your terminal (requires password):"
    echo ""
    echo "    sudo rm -rf /Library/Developer/CommandLineTools"
    echo "    xcode-select --install"
    echo ""
    echo "  Then wait for the installation to complete before continuing."
    echo ""
    read -p "Press Enter after you've completed the Xcode Command Line Tools reinstall..."
else
    echo "  ⚠️  Command Line Tools not found. Installing..."
    xcode-select --install
    read -p "Press Enter after installation completes..."
fi

# Step 2: Verify installation
echo ""
echo "Step 2: Verifying Xcode Command Line Tools installation..."
XCODE_PATH=$(xcode-select -p)
if [ -n "$XCODE_PATH" ]; then
    echo "  ✓ Command Line Tools installed at: $XCODE_PATH"
else
    echo "  ✗ Command Line Tools not found. Please install them first."
    exit 1
fi

# Step 3: Activate virtual environment
echo ""
echo "Step 3: Activating virtual environment..."
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo "  ✓ Virtual environment activated"
else
    echo "  ✗ Virtual environment not found. Please create it first."
    exit 1
fi

# Step 4: Force rebuild llama-cpp-python with Metal
echo ""
echo "Step 4: Force rebuilding llama-cpp-python with Metal support..."
echo "  This may take several minutes..."
CMAKE_ARGS="-DLLAMA_METAL=on" pip install --force-reinstall --no-cache-dir llama-cpp-python

echo ""
echo "=========================================="
echo "✓ Rebuild complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Test your AZUL application: azul"
echo "2. Check the Speed metric - it should now be 50-80+ tok/s"
echo "3. If you want to verify with native llama.cpp benchmark, see README"
echo ""

