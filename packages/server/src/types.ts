export interface ChatMessage {
  role: "system" | "user" | "assistant" | "tool";
  content: string | null; // Can be null for assistant messages with tool calls
  tool_call_id?: string; // For tool role messages
  tool_calls?: ToolCall[]; // For assistant messages with tool calls
}

export interface ToolContext {
  workingDirectory?: string;
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
  execute: (args: any, context?: ToolContext) => Promise<any>;
}

export interface ToolCall {
  id?: string; // Unique ID for the tool call
  name: string;
  arguments: any;
}

export interface Config {
  modelPath: string;
  contextSize: number;
  maxTokens: number;
}

export interface TokenStats {
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  tokensPerSecond: number;
  generationTimeMs: number;
  promptTokens?: number;
  contextTokens?: number;
  cumulativeInputTokens?: number;
  cumulativeOutputTokens?: number;
  cumulativeTotalTokens?: number;
  totalInputTokens?: number;
  totalOutputTokens?: number;
}

