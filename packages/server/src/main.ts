#!/usr/bin/env node

// Clear terminal immediately on start - ensures clean slate
console.clear();

import * as path from "path";
import * as fs from "fs/promises";
import { fileURLToPath } from "url";
import { LLMOrchestrator, ProviderStatus } from "./orchestrator.js";
import { Config } from "./types.js";
import { Agent } from "./agent.js";
import { render } from "ink";
import React from "react";
import { openInEditor, findAzulMdPath } from "./utils/editor.js";
// Import from dist - TypeScript will use .d.ts files for type checking
import { App } from "../../ui/dist/App.js";

// Get __dirname equivalent for ES modules (needed for finding package root)
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const BANNER = `

    █████╗   ███████╗   ██╗   ██╗   ██╗
   ██╔══██╗   ╚════██╗  ██║   ██║   ██║
  ███████║    █████╔╝   ██║   ██║   ██║
 ██╔══██║    ██╔═══╝    ██║   ██║   ██║
██║  ██║     ███████╗   ╚██████╔╝   ███████╗
╚═╝  ╚═╝     ╚══════╝    ╚═════╝    ╚══════╝

║   Local AI Coding Assistant  ║


`;

// Helper to find package root (where config.json should be)
function findPackageRoot(): string {
  // __dirname points to packages/server/dist
  // Go up 3 levels: dist -> server -> packages -> root
  return path.resolve(__dirname, "../../..");
}

async function loadConfig(): Promise<{ config: Config; configPath: string }> {
  // Try to find config.json in current working directory first
  // This allows users to have project-specific configs
  const cwdConfigPath = path.join(process.cwd(), "config.json");

  try {
    await fs.access(cwdConfigPath);
    const configData = await fs.readFile(cwdConfigPath, "utf-8");
    const config = JSON.parse(configData);
    return { config, configPath: path.dirname(cwdConfigPath) };
  } catch (error) {
    // Config not found in current directory, try package directory
  }

  // Try to find config in package directory (for global installs)
  // Look for config.json relative to this file's location
  const packageRoot = findPackageRoot();
  const packageConfigPath = path.join(packageRoot, "config.json");

  try {
    await fs.access(packageConfigPath);
    const configData = await fs.readFile(packageConfigPath, "utf-8");
    const config = JSON.parse(configData);
    return { config, configPath: packageRoot };
  } catch (error) {
    // Config not found, use defaults
  }

  // Use package root as configPath for defaults
  return {
    config: {
      modelPath: "./models/qwen2.5-coder-7b-instruct-q4_k_m.gguf",
      contextSize: 16384,
      maxTokens: 16384,
    },
    configPath: packageRoot,
  };
}

async function main() {
  const queuedMessages: any[] = [];
  let uiReady = false;

  const messageHandlers: {
    onMessage: (message: any) => void;
    onApproval: (requestId: string, approved: boolean) => void;
  } = {
    onMessage: (message: any) => {
      queuedMessages.push(message);
    },
    onApproval: () => {},
  };

  const enqueueMessage = (message: any) => {
    const enrichedMessage = {
      ...message,
      timestamp: message.timestamp ?? Date.now(),
    };
    if (uiReady) {
      messageHandlers.onMessage(enrichedMessage);
    } else {
      queuedMessages.push(enrichedMessage);
    }
  };

  // Load configuration
  const { config, configPath } = await loadConfig();

  // Resolve model path relative to config file location, not current working directory
  let modelPath: string;
  if (path.isAbsolute(config.modelPath)) {
    modelPath = config.modelPath;
  } else {
    // Try relative to config file location first
    const configRelativePath = path.resolve(configPath, config.modelPath);
    try {
      await fs.access(configRelativePath);
      modelPath = configRelativePath;
    } catch {
      // If not found relative to config, try current working directory
      const cwdRelativePath = path.resolve(process.cwd(), config.modelPath);
      try {
        await fs.access(cwdRelativePath);
        modelPath = cwdRelativePath;
      } catch {
        // If still not found, use config relative path (will show error later)
        modelPath = configRelativePath;
      }
    }
  }

  // Provider configuration (local only)
  const providerConfig = {
    localModelPath: modelPath,
    localContextSize: config.contextSize,
    localMaxTokens: config.maxTokens,
  };

  const handleProviderStatus = (status: ProviderStatus) => {
    enqueueMessage({
      type: "provider_status",
      status,
    });
    enqueueMessage({
      type: "system",
      message: `Local provider: ${status.provider} (${status.model})`,
    });
  };

  const orchestrator = new LLMOrchestrator(providerConfig, handleProviderStatus);

  // Initialize Local LLM
  try {
    await orchestrator.initialize();
  } catch (error) {
    enqueueMessage({
      type: "error",
      message: `Failed to initialize local LLM: ${error}`,
    });
  }

  // Track working directory (starts from where azul was called)
  let workingDirectory: string = process.cwd();

  // Create agent with direct callback, working directory context, and context size
  const agent = new Agent((message: any) => {
    enqueueMessage(message);
  }, orchestrator, workingDirectory, config.contextSize);

  // Initialize agent (loads AZUL.md)
  await agent.initialize();

  // Update agent's working directory when it changes
  const updateAgentWorkingDirectory = async () => {
    await agent.setWorkingDirectory(workingDirectory);
  };

  // Handle approval requests
  messageHandlers.onApproval = (requestId: string, approved: boolean) => {
    agent.handleApproval(requestId, approved);
  };

  // Handle user input
  const handleUserInput = (text: string) => {
    agent.handleUserMessage(text);
  };

  // Handle reset command
  const handleReset = () => {
    agent.reset();
  };

  // Handle directory change
  const handleChangeDirectory = async (dirPath: string): Promise<void> => {
    try {
      const resolvedPath = path.isAbsolute(dirPath)
        ? dirPath
        : path.resolve(workingDirectory, dirPath);

      // Check if directory exists
      const stats = await fs.stat(resolvedPath);
      if (!stats.isDirectory()) {
        enqueueMessage({
          type: "error",
          message: `Not a directory: ${dirPath}`,
        });
        return;
      }

      workingDirectory = resolvedPath;
      process.chdir(workingDirectory);
      await updateAgentWorkingDirectory();

      enqueueMessage({
        type: "system",
        message: `Changed directory to: ${workingDirectory}`,
      });
    } catch (error: any) {
      enqueueMessage({
        type: "error",
        message: `cd: ${error.message}`,
      });
    }
  };

  // Handle list directory
  const handleListDirectory = async (dirPath?: string): Promise<void> => {
    try {
      const targetPath = dirPath
        ? (path.isAbsolute(dirPath) ? dirPath : path.resolve(workingDirectory, dirPath))
        : workingDirectory;

      const entries = await fs.readdir(targetPath, { withFileTypes: true });

      const items = entries.map(entry => {
        const name = entry.name;
        const isDir = entry.isDirectory();
        const fullPath = path.join(targetPath, name);
        return { name, isDir, path: fullPath };
      }).sort((a, b) => {
        // Directories first, then alphabetically
        if (a.isDir && !b.isDir) return -1;
        if (!a.isDir && b.isDir) return 1;
        return a.name.localeCompare(b.name);
      });

      const dirs = items.filter(item => item.isDir).map(item => item.name + "/");
      const files = items.filter(item => !item.isDir).map(item => item.name);

      const output = [
        `Directory: ${targetPath}`,
        "",
        dirs.length > 0 ? `Directories:\n  ${dirs.join("\n  ")}` : "",
        files.length > 0 ? `Files:\n  ${files.join("\n  ")}` : "",
        dirs.length === 0 && files.length === 0 ? "(empty)" : "",
      ].filter(Boolean).join("\n");

      enqueueMessage({
        type: "system",
        message: output,
      });
    } catch (error: any) {
      enqueueMessage({
        type: "error",
        message: `ls: ${error.message}`,
      });
    }
  };

  // Handle /memory command - open AZUL.md in editor
  const handleOpenMemory = async (): Promise<void> => {
    const azulMdPath = await findAzulMdPath(workingDirectory);

    if (!azulMdPath) {
      enqueueMessage({
        type: "system",
        message: "No AZUL.md found. Use /init to create one.",
      });
      return;
    }

    const result = await openInEditor(azulMdPath);

    enqueueMessage({
      type: "system",
      message: result.message,
    });
  };

  // Render UI with direct callbacks
  render(
    React.createElement(App, {
      onUserInput: handleUserInput,
      onApproval: messageHandlers.onApproval,
      onMessage: (handler: (message: any) => void) => {
        messageHandlers.onMessage = handler;
        uiReady = true;
        // Start fresh with clean UI
        queuedMessages.length = 0;
      },
      onReset: handleReset,
      onChangeDirectory: handleChangeDirectory,
      onListDirectory: handleListDirectory,
      onOpenMemory: handleOpenMemory,
    })
  );

  // Graceful shutdown
  const shutdown = async () => {
    await orchestrator.cleanup();
    process.exit(0);
  };

  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}

main().catch((error) => {
  process.exit(1);
});
