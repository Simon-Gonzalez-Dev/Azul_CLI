"""Setup script for AZUL."""
'''


1. Set the model path using the AZUL_MODEL_PATH environment variable. The code reads it from azul/config/manager.py (lines 23-37).
Set it in your terminal session:



export AZUL_MODEL_PATH=/Users/simongonzalez/Desktop/AZUL/Azul_CLI/azul/models/qwen2.5-coder-7b-instruct-q4_k_m.gguf

--------------------------------
2. Install the dependencies:
pip install -r requirements.txt

3. Activate the virtual environment:
source azul_env/bin/activate

4. Install AZUL in development mode:
pip install -e .

5. Run the AZUL CLI:
azul














'''
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="azul",
    version="0.1.0",
    author="AZUL Team",
    description="An agentic AI coding assistant using local LLMs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "azul=azul.cli:main",
        ],
    },
)

