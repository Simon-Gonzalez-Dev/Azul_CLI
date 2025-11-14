#!/usr/bin/env node

import * as path from "path";
import * as fs from "fs/promises";
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

const BANNER = `
  
    █████╗   ███████╗   ██╗   ██╗   ██╗       
   ██╔══██╗   ╚════██╗  ██║   ██║   ██║      
  ███████║    █████╔╝   ██║   ██║   ██║       
 ██╔══██║    ██╔═══╝    ██║   ██║   ██║       
██║  ██║     ███████╗   ╚██████╔╝   ███████╗  
╚═╝  ╚═╝     ╚══════╝    ╚═════╝    ╚══════╝ 

║   AI Coding Assistant - Local Mode  ║


`;

async function loadConfig(): Promise<Config> {
  try {
    const configPath = path.join(process.cwd(), "config.json");
    const configData = await fs.readFile(configPath, "utf-8");
    return JSON.parse(configData);
  } catch (error) {
    console.error("Failed to load config.json, using defaults");
    return {
      modelPath: "./models/qwen2.5-coder-7b-instruct-q4_k_m.gguf",
      contextSize: 8192,
      maxTokens: 2048,
    };
  }
}

async function main() {
  console.clear();
  console.log(BANNER);
  console.log("Starting Azul...\n");

  // Load configuration
  const config = await loadConfig();
  console.log(`   Configuration loaded`);
  console.log(`   Model: ${config.modelPath}`);
  console.log(`   Context Size: ${config.contextSize}\n`);

  // Initialize mode tracking
  let currentMode: "local" | "api" = "local";
  let currentLLM: ILLMService;

  // Initialize Local LLM
  const localLLM = new LLMService(config.contextSize, config.maxTokens);
  const modelPath = path.resolve(process.cwd(), config.modelPath);
  
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

  // Create agent with direct callback
  const agent = new Agent((message: any) => {
    messageHandlers.onMessage(message);
  }, currentLLM);

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
