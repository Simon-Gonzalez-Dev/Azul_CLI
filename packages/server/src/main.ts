#!/usr/bin/env node

import * as path from "path";
import * as fs from "fs/promises";
import { fileURLToPath } from "url";
import * as dotenv from "dotenv";
import { LLMOrchestrator, ProviderStatus } from "./orchestrator.js";
import { Config } from "./types.js";
import { Agent } from "./agent.js";
import { render } from "ink";
import React from "react";
// Import from dist - TypeScript will use .d.ts files for type checking
import { App } from "../../ui/dist/App.js";

// Get __dirname equivalent for ES modules (needed for finding package root)
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Load environment variables - try package root first, then current directory
// Current directory .env will override package root .env values
const packageRoot = path.resolve(__dirname, "../../..");
const packageEnvPath = path.join(packageRoot, ".env");
const cwdEnvPath = path.join(process.cwd(), ".env");

// Store .env loading messages
const envLoadMessages: string[] = [];

// Try package root .env first (for global installs)
let packageEnvLoaded = false;
try {
  const packageEnv = dotenv.config({ path: packageEnvPath });
  if (!packageEnv.error) {
    packageEnvLoaded = true;
    const msg = `Loaded .env from package root: ${packageEnvPath}`;
    console.log(`   ${msg}`);
    envLoadMessages.push(msg);
  } else {
    const errorCode = (packageEnv.error as any).code;
    if (errorCode && errorCode !== 'ENOENT') {
      const msg = `Warning: Error loading .env from package root: ${packageEnv.error.message}`;
      console.warn(`   ${msg}`);
      envLoadMessages.push(msg);
    }
  }
} catch (error: any) {
  // Ignore if file doesn't exist
}

// Also try current directory .env (allows project-specific overrides)
// Use override: true so current directory .env takes precedence
let cwdEnvLoaded = false;
try {
  const cwdEnv = dotenv.config({ path: cwdEnvPath, override: true });
  if (!cwdEnv.error) {
    cwdEnvLoaded = true;
    const msg = `Loaded .env from current directory: ${cwdEnvPath}`;
    console.log(`   ${msg}`);
    envLoadMessages.push(msg);
  } else {
    const errorCode = (cwdEnv.error as any).code;
    if (errorCode && errorCode !== 'ENOENT') {
      const msg = `Warning: Error loading .env from current directory: ${cwdEnv.error.message}`;
      console.warn(`   ${msg}`);
      envLoadMessages.push(msg);
    }
  }
} catch (error: any) {
  // Ignore if file doesn't exist
}

// Debug: Show which .env files were loaded
if (!packageEnvLoaded && !cwdEnvLoaded) {
  const msg = `No .env file found (checked: ${packageEnvPath}, ${cwdEnvPath})`;
  console.log(`   ${msg}`);
  envLoadMessages.push(msg);
}


const BANNER = `
  
    █████╗   ███████╗   ██╗   ██╗   ██╗       
   ██╔══██╗   ╚════██╗  ██║   ██║   ██║      
  ███████║    █████╔╝   ██║   ██║   ██║       
 ██╔══██║    ██╔═══╝    ██║   ██║   ██║       
██║  ██║     ███████╗   ╚██████╔╝   ███████╗  
╚═╝  ╚═╝     ╚══════╝    ╚═════╝    ╚══════╝ 

║   AI Coding Assistant - Universal Mode  ║


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
      contextSize: 16384,
      maxTokens: 16384,
    },
    configPath: packageRoot,
  };
}

async function main() {
  console.clear();
  console.log(BANNER);
  console.log("Starting Azul...");

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

  // Add .env loading messages to init messages (loaded at module level)
  if (envLoadMessages.length > 0) {
    enqueueMessage({
      type: "system",
      message: envLoadMessages.join("\n"),
    });
  }

  // Load configuration
  const { config, configPath } = await loadConfig();
  const configMsg = `Configuration loaded\nModel: ${config.modelPath}\nContext Size: ${config.contextSize}`;
  console.log(`   Configuration loaded`);
  console.log(`   Model: ${config.modelPath}`);
  console.log(`   Context Size: ${config.contextSize}`);
  enqueueMessage({
    type: "system",
    message: configMsg,
  });

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

  // Gather API Keys
  const providerConfig = {
    hfApiKey: process.env.HF_API_KEY,
    hfModel: process.env.HF_MODEL,
    geminiApiKey: process.env.GEMINI_API_KEY,
    geminiModel: process.env.GEMINI_MODEL,
    groqApiKey: process.env.GROK_API_KEY || process.env.GROQ_API_KEY,
    groqModel: process.env.GROK_MODEL || process.env.GROQ_MODEL,
    openRouterApiKey: process.env.OPENROUTER_API_KEY,
    openRouterModel: process.env.OPENROUTER_MODEL,
    localModelPath: modelPath,
    localContextSize: config.contextSize,
    localMaxTokens: config.maxTokens,
  };

  // Initialize mode tracking
  let currentMode: "local" | "api" = "local";

  const handleProviderStatus = (status: ProviderStatus) => {
    enqueueMessage({
      type: "provider_status",
      status,
    });

    if (status.fallback && status.reason && status.previousProvider) {
      enqueueMessage({
        type: "system",
        message: `Fallback (${status.previousProvider} → ${status.provider}): ${status.reason}`,
      });
    } else if (!status.fallback) {
      const modeLabel = status.mode === "api" ? "API" : "Local";
      enqueueMessage({
        type: "system",
        message: `${modeLabel} provider: ${status.provider} (${status.model})`,
      });
    }
  };

  const apiOrchestrator = new LLMOrchestrator(providerConfig, true, handleProviderStatus);
  const localOrchestrator = new LLMOrchestrator(providerConfig, false, handleProviderStatus);

  // Initialize Local by default
  try {
    await localOrchestrator.initialize();
    console.log("   Local LLM initialized\n");
    enqueueMessage({
      type: "system",
      message: "Local LLM initialized",
    });
  } catch (error) {
    console.error(" Failed to initialize local LLM:", error);
    enqueueMessage({
      type: "error",
      message: `Failed to initialize local LLM: ${error}`,
    });
  }

  // Pre-initialize API if keys exist (optional, but good for fast switching)
  // Just check if keys exist to show status
  const apiKeysExist = providerConfig.hfApiKey || providerConfig.geminiApiKey || providerConfig.groqApiKey || providerConfig.openRouterApiKey;
  if (apiKeysExist) {
    try {
        await apiOrchestrator.initialize();
        const msg = "API Providers initialized (HF, Gemini, Groq, OpenRouter)";
        console.log(`   ${msg}\n`);
        enqueueMessage({
          type: "system",
          message: msg,
        });
    } catch (e) {
        // ignore initialization errors for API until switched
         console.log(`   API initialization warning: ${e}\n`);
    }
  }

  let currentLLM = localOrchestrator;

  // Track working directory (starts from where azul was called)
  let workingDirectory: string = process.cwd();

  // Create agent with direct callback and working directory context
  const agent = new Agent((message: any) => {
    enqueueMessage(message);
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
        enqueueMessage({
          type: "error",
          message: `Not a directory: ${dirPath}`,
        });
        return;
      }
      
      workingDirectory = resolvedPath;
      process.chdir(workingDirectory); // Also change Node's cwd
      updateAgentWorkingDirectory(); // Update agent's working directory
      
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

  // Handle mode switching
  const handleSwitchMode = (mode: "local" | "api") => {
    if (mode === "api") {
      if (apiKeysExist) {
        currentMode = "api";
        currentLLM = apiOrchestrator;
        agent.setLLM(apiOrchestrator);
        enqueueMessage({
          type: "mode_changed",
          mode: "api",
        });
      } else {
        enqueueMessage({
          type: "error",
          message: "No API keys found in .env (HF_API_KEY, GEMINI_API_KEY, GROK_API_KEY/GROQ_API_KEY, OPENROUTER_API_KEY)",
        });
      }
    } else if (mode === "local") {
      currentMode = "local";
      currentLLM = localOrchestrator;
      agent.setLLM(localOrchestrator);
      enqueueMessage({
        type: "mode_changed",
        mode: "local",
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
        uiReady = true;
        queuedMessages.forEach((msg) => handler(msg));
        queuedMessages.length = 0;
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
    console.log("\n\n Shutting down...");
    await localOrchestrator.cleanup();
    await apiOrchestrator.cleanup();
    console.log(" Goodbye!");
    process.exit(0);
  };

  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
