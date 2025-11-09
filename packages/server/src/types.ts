export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface ToolDefinition {
  name: string;
  description: string;
  parameters: {
    type: "object";
    properties: Record<string, any>;
    required?: string[];
  };
  requiresApproval: boolean;
  execute: (args: any) => Promise<any>;
}

export interface ToolCall {
  name: string;
  arguments: any;
}

export interface WebSocketMessage {
  type: string;
  [key: string]: any;
}

export interface Config {
  modelPath: string;
  port: number;
  contextSize: number;
  maxTokens: number;
}

export interface TokenStats {
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  tokensPerSecond: number;
  generationTimeMs: number;
}

