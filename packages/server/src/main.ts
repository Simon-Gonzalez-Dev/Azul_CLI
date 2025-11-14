#!/usr/bin/env node

import * as path from "path";
import * as fs from "fs/promises";
import { fileURLToPath } from "url";
import * as dotenv from "dotenv";
import { LLMService } from "./llm.js";
import { OpenRouterLLMService } from "./openrouter-llm.js";
import { ILLMService } from "./llm-interface.js";
import { Config } from "./types.js";
import { Agent } from "./agent.js";
import { render } from "ink";
import React from "react";
// Import from dist - TypeScript will use .d.ts files for type checking
import { App } from "../../ui/dist/App.js";

// Load environment variables
dotenv.config();

// Get __dirname equivalent for ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const BANNER = `
  
    █████╗   ███████╗   ██╗   ██╗   ██╗       
   ██╔══██╗   ╚════██╗  ██║   ██║   ██║      
  ███████║    █████╔╝   ██║   ██║   ██║       
 ██╔══██║    ██╔═══╝    ██║   ██║   ██║       
██║  ██║     ███████╗   ╚██████╔╝   ███████╗  
╚═╝  ╚═╝     ╚══════╝    ╚═════╝    ╚══════╝ 

║   AI Coding Assistant - Local Mode  ║


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
    console.error(`Failed to load config.json from ${packageConfigPath}, using defaults`);
  }
  
  // Use package root as configPath for defaults
  return {
    config: {
      modelPath: "./models/qwen2.5-coder-7b-instruct-q4_k_m.gguf",
      contextSize: 8192,
      maxTokens: 2048,
    },
    configPath: packageRoot,
  };
}

async function main() {
  console.clear();
  console.log(BANNER);
  console.log("Starting Azul...\n");

  // Load configuration
  const { config, configPath } = await loadConfig();
  console.log(`   Configuration loaded`);
  console.log(`   Model: ${config.modelPath}`);
  console.log(`   Context Size: ${config.contextSize}\n`);

  // Initialize mode tracking
  let currentMode: "local" | "api" = "local";
  let currentLLM: ILLMService;

  // Initialize Local LLM
  const localLLM = new LLMService(config.contextSize, config.maxTokens);
  
  // Resolve model path relative to config file location, not current working directory
  // This allows the model to be found regardless of where azul is called from
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
  
  try {
    await localLLM.initialize(modelPath);
    console.log("   Local LLM initialized\n");
    currentLLM = localLLM;
  } catch (error) {
    console.error(" Failed to initialize local LLM:", error);
    console.error("\nMake sure the model file exists at:", modelPath);
    process.exit(1);
  }

  // Initialize OpenRouter API (if API key is available)
  const openRouterApiKey = process.env.OPENROUTER_API_KEY;
  let apiLLM: OpenRouterLLMService | null = null;
  
  if (openRouterApiKey) {
    try {
      apiLLM = new OpenRouterLLMService(openRouterApiKey);
      await apiLLM.initialize({});
      console.log("   OpenRouter API initialized (use /api to switch)\n");
    } catch (error: any) {
      console.error("   Warning: Failed to initialize OpenRouter API:", error.message);
      console.error("   Continuing with local mode only\n");
    }
  } else {
    console.log("   OpenRouter API key not found in .env (OPENROUTER_API_KEY)");
    console.log("   Continuing with local mode only\n");
  }

  // Create message handler for UI
  const messageHandlers: {
    onMessage: (message: any) => void;
    onApproval: (requestId: string, approved: boolean) => void;
  } = {
    onMessage: () => {},
    onApproval: () => {},
  };

  // Track working directory (starts from where azul was called)
  let workingDirectory: string = process.cwd();

  // Create agent with direct callback and working directory context
  const agent = new Agent((message: any) => {
    messageHandlers.onMessage(message);
  }, currentLLM, workingDirectory);
  
  // Update agent's working directory when it changes
  const updateAgentWorkingDirectory = () => {
    agent.setWorkingDirectory(workingDirectory);
  };

  // Handle approval requests
  messageHandlers.onApproval = (requestId: string, approved: boolean) => {
    agent.handleApproval(requestId, approved);
  };

  // Handle user input
  const handleUserInput = (text: string) => {
    // Commands starting with / are handled in the UI
    // This function only receives non-command input
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
        messageHandlers.onMessage({
          type: "error",
          message: `Not a directory: ${dirPath}`,
          timestamp: Date.now(),
        });
        return;
      }
      
      workingDirectory = resolvedPath;
      process.chdir(workingDirectory); // Also change Node's cwd
      updateAgentWorkingDirectory(); // Update agent's working directory
      
      messageHandlers.onMessage({
        type: "system",
        message: `Changed directory to: ${workingDirectory}`,
        timestamp: Date.now(),
      });
    } catch (error: any) {
      messageHandlers.onMessage({
        type: "error",
        message: `cd: ${error.message}`,
        timestamp: Date.now(),
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
      
      messageHandlers.onMessage({
        type: "system",
        message: output,
        timestamp: Date.now(),
      });
    } catch (error: any) {
      messageHandlers.onMessage({
        type: "error",
        message: `ls: ${error.message}`,
        timestamp: Date.now(),
      });
    }
  };

  // Handle mode switching
  const handleSwitchMode = (mode: "local" | "api") => {
    if (mode === "api") {
      if (apiLLM) {
        currentMode = "api";
        currentLLM = apiLLM;
        agent.setLLM(apiLLM);
        messageHandlers.onMessage({
          type: "mode_changed",
          mode: "api",
          timestamp: Date.now(),
        });
      } else {
        messageHandlers.onMessage({
          type: "error",
          message: "OpenRouter API not available. Make sure OPENROUTER_API_KEY is set in .env file.",
          timestamp: Date.now(),
        });
      }
    } else if (mode === "local") {
      currentMode = "local";
      currentLLM = localLLM;
      agent.setLLM(localLLM);
      messageHandlers.onMessage({
        type: "mode_changed",
        mode: "local",
        timestamp: Date.now(),
      });
    }
  };

  // Render UI with direct callbacks
  render(
    React.createElement(App, {
      onUserInput: handleUserInput,
      onApproval: messageHandlers.onApproval,
      onMessage: (handler: (message: any) => void) => {
        messageHandlers.onMessage = handler;
      },
      onReset: handleReset,
      onSwitchMode: handleSwitchMode,
      onChangeDirectory: handleChangeDirectory,
      onListDirectory: handleListDirectory,
      currentMode: currentMode,
    })
  );

  // Graceful shutdown
  const shutdown = async () => {
    console.log("\n\n🛑 Shutting down...");
    await currentLLM.cleanup();
    console.log("👋 Goodbye!");
    process.exit(0);
  };

  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
