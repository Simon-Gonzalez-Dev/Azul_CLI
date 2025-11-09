import React from "react";
import { render } from "ink";
import { WebSocket } from "ws";
import { App } from "./App.js";

export function renderUI(port: number = 3737): void {
  const ws = new WebSocket(`ws://localhost:${port}`);

  ws.on("open", () => {
    
  });

  ws.on("error", (error) => {
    console.error("Failed to connect to server:", error);
    process.exit(1);
  });

  render(<App ws={ws} />);
}

