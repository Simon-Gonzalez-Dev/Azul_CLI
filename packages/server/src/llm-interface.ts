import { ChatMessage, ToolDefinition, TokenStats, ToolCall } from "./types.js";

export interface ILLMService {
  getCompletion(
    systemPrompt: string,
    conversationHistory: ChatMessage[],
    tools?: ToolDefinition[],
    onToken?: (token: string) => void
  ): Promise<{ response: string; toolCalls?: ToolCall[]; stats: TokenStats }>;
  
  initialize(config: any): Promise<void>;
  cleanup(): Promise<void>;
  getTokenStats(): TokenStats;
  resetTokenStats(): void;
}

