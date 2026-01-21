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

// Unified tool result format for consistent UI handling
export interface ToolResult {
  success: boolean;
  message: string;
  error?: string;
  toolName: string;           // Which tool produced this result
  filePath?: string;          // Standardized path field (not "path")
  content?: string;           // For view, grep, bash output
  diff?: string;              // For edit, write operations
  added?: number;             // Lines added (for diffs)
  removed?: number;           // Lines removed (for diffs)
  // Tool-specific optional fields
  lines?: number;             // For view/write - line count
  created?: boolean;          // For write - was file created
  riskLevel?: 'blocked' | 'high' | 'medium' | 'low';  // For bash
  commandPreview?: string;    // For bash approval modal
  truncated?: boolean;        // For grep - results truncated
  matchCount?: number;        // For grep - total matches
}

// Agent status for persistent state tracking
export type AgentStatus = 'IDLE' | 'THINKING' | 'STREAMING' | 'EXECUTING_TOOL' | 'AWAITING_APPROVAL' | 'COMPLETE';

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

