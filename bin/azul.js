#!/usr/bin/env node

// This is the global entry point for azul
// It resolves the actual main.js file relative to this script's location
const path = require('path');
const { spawn } = require('child_process');

// Find the actual main.js file
// When installed globally, this script is in node_modules/.bin/azul
// The actual package is in node_modules/azul
const packageRoot = path.resolve(__dirname, '..');
const mainJs = path.join(packageRoot, 'packages', 'server', 'dist', 'main.js');

// Preserve the original working directory where azul was called from
// This allows azul to work from any directory
const originalCwd = process.env.INIT_CWD || process.cwd();

// Spawn the actual Node process with the original working directory
const child = spawn(process.execPath, [mainJs], {
  stdio: 'inherit',
  cwd: originalCwd,
  env: {
    ...process.env,
    INIT_CWD: originalCwd
  }
});

child.on('exit', (code) => {
  process.exit(code || 0);
});
