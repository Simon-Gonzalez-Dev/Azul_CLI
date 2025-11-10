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

export interface MessageCallback {
  (message: { type: string; [key: string]: any }): void;
}

export interface Config {
  modelPath: string;
  contextSize: number;
  maxTokens: number;
  gpuLayers: number;
  threads: number;
  flashAttention: boolean;
  batchSize: number;
  memoryLock: boolean;
  temperature: number;
  topP: number;
  topK: number;
}

export interface TokenStats {
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  tokensPerSecond: number;
  generationTimeMs: number;
}

