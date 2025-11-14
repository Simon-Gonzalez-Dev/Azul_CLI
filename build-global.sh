#!/bin/bash
# Build script for global installation (doesn't use workspaces)

echo "Building packages for global installation..."

cd packages/server
npm run build
cd ../ui
npm run build
cd ../..

echo "Build complete! You can now run: npm install -g ."

