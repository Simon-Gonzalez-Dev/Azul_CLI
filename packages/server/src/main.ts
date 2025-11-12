#!/usr/bin/env node

import * as path from "path";
import * as fs from "fs/promises";
import { LLMService } from "./llm.js";
import { Config } from "./types.js";
import { Agent } from "./agent.js";
import { render } from "ink";
import React from "react";
// Import from dist - TypeScript will use .d.ts files for type checking
import { App } from "../../ui/dist/App.js";

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

  // Initialize LLM
  const llm = new LLMService(config.contextSize, config.maxTokens);
  const modelPath = path.resolve(process.cwd(), config.modelPath);
  
  try {
    await llm.initialize(modelPath);
    console.log("   LLM initialized\n");
  } catch (error) {
    console.error(" Failed to initialize LLM:", error);
    console.error("\nMake sure the model file exists at:", modelPath);
    process.exit(1);
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
  }, llm);

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

  // Render UI with direct callbacks
  render(
    React.createElement(App, {
      onUserInput: handleUserInput,
      onApproval: messageHandlers.onApproval,
      onMessage: (handler: (message: any) => void) => {
        messageHandlers.onMessage = handler;
      },
      onReset: handleReset,
    })
  );

  // Graceful shutdown
  const shutdown = async () => {
    console.log("\n\n🛑 Shutting down...");
    await llm.cleanup();
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
