#!/bin/bash
# Quick test script to verify the launcher works

echo "Testing AZUL launcher..."
echo ""

echo "1. Testing direct launcher:"
/Users/simongonzalez/Desktop/AZUL/Azul_CLI/azul_launcher.sh --help 2>&1 || echo "Launcher test complete"

echo ""
echo "2. Testing global command (if installed):"
which azul && echo "Global 'azul' command found at: $(which azul)"

echo ""
echo "3. Verifying venv Python:"
/Users/simongonzalez/Desktop/AZUL/Azul_CLI/azul_env/bin/python --version

echo ""
echo "4. Checking dependencies in venv:"
/Users/simongonzalez/Desktop/AZUL/Azul_CLI/azul_env/bin/python -c "import websockets, llama_cpp, langchain; print('✅ All dependencies OK!')" 2>&1 || echo "❌ Dependencies missing - run ./setup.sh"

echo ""
echo "All tests complete!"

