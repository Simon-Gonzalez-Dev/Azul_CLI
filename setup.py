"""Setup script for AZUL CLI."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="azul-cli",
    version="0.1.0",
    author="AZUL CLI",
    description="A Claude-like coding assistant with local LLMs via Ollama",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/azul-cli",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0.0",
        "prompt-toolkit>=3.0.0",
        "ollama>=0.1.0",
        "rich>=13.0.0",
        "tree-sitter>=0.20.0",
        "tree-sitter-python>=0.20.0",
        "watchdog>=3.0.0",
    ],
    entry_points={
        "console_scripts": [
            "azul=azul.cli:main",
        ],
    },
)

