#!/usr/bin/env node

import * as path from "path";
import * as fs from "fs/promises";
import { LLMService } from "./llm.js";
import { Agent } from "./agent.js";
import { Config } from "./types.js";

const BANNER = `

    █████╗   ███████╗   ██╗   ██╗   ██╗       
   ██╔══██╗   ╚════██╗  ██║   ██║   ██║      
  ███████║    █████╔╝   ██║   ██║   ██║       
 ██╔══██║    ██╔═══╝    ██║   ██║   ██║       
██║  ██║     ███████╗   ╚██████╔╝   ███████╗  
╚═╝  ╚═╝     ╚══════╝    ╚═════╝    ╚══════╝ 

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
      maxTokens: 16384,
      gpuLayers: 999,
      threads: 10,
      flashAttention: true,
      batchSize: 512,
      memoryLock: true,
      temperature: 0.85,
      topP: 0.95,
      topK: 40,
    };
  }
}

// Global agent instance for UI access
export let globalAgent: Agent | null = null;

async function main() {
  console.clear();
  console.log(BANNER);
  console.log("Starting Azul...\n");

  const config = await loadConfig();
  console.log(`   Configuration loaded`);
  console.log(`   Model: ${config.modelPath}`);
  console.log(`   Context Size: ${config.contextSize.toLocaleString()} tokens`);
  console.log(`   Max Output: ${config.maxTokens.toLocaleString()} tokens`);
  console.log(`   GPU Layers: ${config.gpuLayers === 999 ? 'all' : config.gpuLayers}`);
  console.log(`   Threads: ${config.threads}`);
  console.log(`   Flash Attention: ${config.flashAttention ? 'enabled' : 'disabled'}\n`);

  // Initialize LLM
  const llm = new LLMService(config);
  const modelPath = path.resolve(process.cwd(), config.modelPath);
  
  try {
    await llm.initialize(modelPath);
  } catch (error) {
    console.error("  Failed to initialize LLM:", error);
    console.error("\nMake sure the model file exists at:", modelPath);
    process.exit(1);
  }

  // Create message handler that will be passed to UI
  let messageHandler: ((message: any) => void) | null = null;

  // Create agent with direct message callback
  const agent = new Agent((message) => {
    // Forward messages to UI handler
    if (messageHandler) {
      messageHandler(message);
    }
  }, llm);

  // Store agent globally
  globalAgent = agent;

  console.log("  Azul ready!\n");
  console.log("Starting UI...\n");

  // Dynamically import UI at runtime
  const uiPath = path.resolve(process.cwd(), "packages/ui/dist/main.js");
  const { renderUI } = await import(uiPath);
  
  // Render UI - pass agent and message handler setter
  renderUI(agent, (handler: (message: any) => void) => {
    messageHandler = handler;
    // Send initial connection message
    handler({
      type: "connected",
      message: "Connected to Azul",
      timestamp: Date.now(),
    });
  });

  // Graceful shutdown
  const shutdown = async () => {
    console.log("\n\n  Shutting down...");
    await llm.cleanup();
    process.exit(0);
  };

  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
