#!/usr/bin/env python3
"""AZUL - Local AI Coding Assistant Launcher.

This script orchestrates the backend and frontend processes.
"""

import subprocess
import sys
import time
import signal
import socket
from pathlib import Path

# Color codes for terminal output
CYAN = '\033[96m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'

BANNER = """
    █████╗   ███████╗   ██╗   ██╗   ██╗       
   ██╔══██╗   ╚════██╗  ██║   ██║   ██║      
  ███████║    █████╔╝   ██║   ██║   ██║       
 ██╔══██║    ██╔═══╝    ██║   ██║   ██║       
██║  ██║     ███████╗   ╚██████╔╝   ███████╗  
╚═╝  ╚═╝     ╚══════╝    ╚═════╝    ╚══════╝ 
"""

PROJECT_ROOT = Path(__file__).parent
BACKEND_DIR = PROJECT_ROOT / "azul-backend"
FRONTEND_DIR = PROJECT_ROOT / "azul-ui"


def print_banner():
    """Print the AZUL banner."""
    print(f"{CYAN}{BANNER}{RESET}")
    print(f"{CYAN}AZUL - Local AI Coding Assistant{RESET}")
    print(f"{CYAN}{'=' * 50}{RESET}\n")


def check_port_available(port: int) -> bool:
    """Check if a port is available."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('localhost', port))
        sock.close()
        return True
    except OSError:
        return False


def wait_for_server(host: str, port: int, timeout: int = 30) -> bool:
    """Wait for the server to be ready."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((host, port))
            sock.close()
            return True
        except (socket.error, ConnectionRefusedError):
            time.sleep(0.5)
    return False


def check_dependencies():
    """Check if required dependencies are installed."""
    errors = []
    
    # Check Python dependencies
    try:
        import websockets
        import llama_cpp
        import langchain
    except ImportError as e:
        errors.append(f"Python dependency missing: {e.name}")
        errors.append(f"  Install with: cd azul-backend && poetry install")
    
    # Check if Bun is installed
    try:
        result = subprocess.run(['bun', '--version'], capture_output=True, text=True)
        if result.returncode != 0:
            errors.append("Bun is not installed")
            errors.append("  Install from: https://bun.sh")
    except FileNotFoundError:
        errors.append("Bun is not installed")
        errors.append("  Install from: https://bun.sh")
    
    # Check if model exists
    model_path = PROJECT_ROOT / "models" / "qwen2.5-coder-7b-instruct-q4_k_m.gguf"
    if not model_path.exists():
        errors.append(f"Model not found at: {model_path}")
        errors.append("  Download a GGUF model and place it in the models/ directory")
    
    return errors


def main():
    """Main entry point."""
    print_banner()
    
    # Check dependencies
    print(f"{YELLOW}Checking dependencies...{RESET}")
    errors = check_dependencies()
    if errors:
        print(f"\n{RED}❌ Dependency errors:{RESET}")
        for error in errors:
            print(f"{RED}{error}{RESET}")
        sys.exit(1)
    print(f"{GREEN}✓ All dependencies found{RESET}\n")
    
    # Check if port is available
    if not check_port_available(8765):
        print(f"{RED}❌ Port 8765 is already in use{RESET}")
        print(f"{YELLOW}Another AZUL instance may be running{RESET}")
        sys.exit(1)
    
    backend_process = None
    frontend_process = None
    
    try:
        # Start backend server
        print(f"{YELLOW}Starting AZUL backend server...{RESET}")
        backend_process = subprocess.Popen(
            [sys.executable, "-m", "azul_core.server"],
            cwd=BACKEND_DIR / "src",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for server to be ready
        print(f"{YELLOW}Waiting for backend server...{RESET}")
        if not wait_for_server('localhost', 8765, timeout=30):
            print(f"{RED}❌ Backend server failed to start{RESET}")
            if backend_process.poll() is not None:
                _, stderr = backend_process.communicate()
                print(f"{RED}Error: {stderr.decode()}{RESET}")
            sys.exit(1)
        
        print(f"{GREEN}✓ Backend server running on ws://localhost:8765{RESET}\n")
        
        # Install frontend dependencies if needed
        node_modules = FRONTEND_DIR / "node_modules"
        if not node_modules.exists():
            print(f"{YELLOW}Installing frontend dependencies...{RESET}")
            subprocess.run(['bun', 'install'], cwd=FRONTEND_DIR, check=True)
            print(f"{GREEN}✓ Frontend dependencies installed{RESET}\n")
        
        # Start frontend UI
        print(f"{CYAN}Starting AZUL UI...{RESET}\n")
        frontend_process = subprocess.Popen(
            ['bun', 'run', 'src/main.tsx'],
            cwd=FRONTEND_DIR
        )
        
        # Wait for frontend to exit
        frontend_process.wait()
    
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Shutting down AZUL...{RESET}")
    
    except Exception as e:
        print(f"\n{RED}❌ Error: {e}{RESET}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup processes
        if frontend_process and frontend_process.poll() is None:
            frontend_process.terminate()
            try:
                frontend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                frontend_process.kill()
        
        if backend_process and backend_process.poll() is None:
            backend_process.terminate()
            try:
                backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend_process.kill()
        
        print(f"{GREEN}✓ AZUL stopped{RESET}")


if __name__ == "__main__":
    main()

