import { WebSocketServer, WebSocket } from "ws";
import { Server as HttpServer } from "http";
import { WebSocketMessage } from "./types.js";
import { Agent } from "./agent.js";
import { LLMService } from "./llm.js";

export class WebSocketManager {
  private wss: WebSocketServer;
  private agents: Map<WebSocket, Agent> = new Map();
  private llm: LLMService;

  constructor(server: HttpServer, llm: LLMService) {
    this.wss = new WebSocketServer({ server });
    this.llm = llm;
    this.setupConnectionHandling();
  }

  private setupConnectionHandling(): void {
    this.wss.on("connection", (ws: WebSocket) => {
      console.log("🔌 New WebSocket connection established");

      // Create a new agent for this connection
      const agent = new Agent((message: WebSocketMessage) => {
        this.sendMessage(ws, message);
      }, this.llm);

      this.agents.set(ws, agent);

      // Send initial connection message
      this.sendMessage(ws, {
        type: "connected",
        message: "Connected to Azul server",
      });

      ws.on("message", async (data: Buffer) => {
        try {
          const message: WebSocketMessage = JSON.parse(data.toString());
          await this.handleMessage(ws, message);
        } catch (error) {
          console.error("Error parsing message:", error);
          this.sendMessage(ws, {
            type: "error",
            message: "Invalid message format",
          });
        }
      });

      ws.on("close", () => {
        console.log("🔌 WebSocket connection closed");
        this.agents.delete(ws);
      });

      ws.on("error", (error) => {
        console.error("WebSocket error:", error);
      });
    });
  }

  private async handleMessage(
    ws: WebSocket,
    message: WebSocketMessage
  ): Promise<void> {
    const agent = this.agents.get(ws);
    if (!agent) {
      console.error("No agent found for connection");
      return;
    }

    switch (message.type) {
      case "user_message":
        await agent.handleUserMessage(message.content);
        break;

      case "approval":
        agent.handleApproval(message.requestId, message.approved);
        break;

      default:
        console.warn(`Unknown message type: ${message.type}`);
    }
  }

  private sendMessage(ws: WebSocket, message: WebSocketMessage): void {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message));
    }
  }

  public broadcast(message: WebSocketMessage): void {
    this.wss.clients.forEach((client) => {
      if (client.readyState === WebSocket.OPEN) {
        client.send(JSON.stringify(message));
      }
    });
  }

  public close(): void {
    this.wss.close();
  }
}

