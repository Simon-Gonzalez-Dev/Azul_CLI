#!/usr/bin/env python3
"""Setup script for AZUL CLI package."""

from setuptools import setup, find_packages
from pathlib import Path

# Read README if it exists
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

setup(
    name="azul",
    version="0.1.0",
    description="AZUL - Local Agentic AI Coding Assistant CLI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="AZUL Contributors",
    license="MIT",
    python_requires=">=3.12",
    packages=find_packages(),
    install_requires=[
        "llama-cpp-python>=0.2.0",
        "langchain>=0.1.0",
        "langchain-community>=0.0.20",
        "langgraph>=1.0.0",
        "textual>=0.45.0",
        "rich>=13.0.0",
        "pexpect>=4.8.0",
    ],
    extras_require={
        "metal": ["llama-cpp-python[metal]>=0.2.0"],
        "cuda": ["llama-cpp-python[cuda]>=0.2.0"],
    },
    entry_points={
        "console_scripts": [
            "azul=azul.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "azul": ["models/*.gguf"],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
    ],
)

