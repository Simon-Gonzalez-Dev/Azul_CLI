#!/usr/bin/env node

import express from "express";
import http from "http";
import * as path from "path";
import * as fs from "fs/promises";
import { WebSocketManager } from "./websocket.js";
import { LLMService } from "./llm.js";
import { Config } from "./types.js";
import { renderUI } from "../../ui/dist/main.js";

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
      port: 3737,
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
  console.log(`   Port: ${config.port}`);
  console.log(`   Context Size: ${config.contextSize}\n`);

  // Initialize LLM
  const llm = new LLMService(config.contextSize, config.maxTokens);
  const modelPath = path.resolve(process.cwd(), config.modelPath);
  
  try {
    await llm.initialize(modelPath);
  } catch (error) {
    console.error(" Failed to initialize LLM:", error);
    console.error("\nMake sure the model file exists at:", modelPath);
    process.exit(1);
  }

  // Create Express app
  const app = express();
  const server = http.createServer(app);

  // Initialize WebSocket
  const wsManager = new WebSocketManager(server, llm);
  console.log(" WebSocket server initialized\n");

  // Health check endpoint
  app.get("/health", (req, res) => {
    res.json({ status: "ok" });
  });

  // Start server
  server.listen(config.port, () => {
    console.log(` Server running on port ${config.port}\n`);
    console.log("Starting UI...\n");
    
    // Wait a bit for server to be fully ready
    setTimeout(() => {
      // Render the Ink UI
      renderUI(config.port);
    }, 500);
  });

  // Graceful shutdown
  const shutdown = async () => {
    console.log("\n\n🛑 Shutting down...");
    wsManager.close();
    await llm.cleanup();
    server.close(() => {
      console.log("👋 Goodbye!");
      process.exit(0);
    });
  };

  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}

// Export the llm instance for use by agents
export let globalLLM: LLMService;

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});

