import { ChatMessage, ToolDefinition, TokenStats } from "./types.js";

export interface ILLMService {
  getCompletion(
    systemPrompt: string,
    conversationHistory: ChatMessage[],
    tools?: ToolDefinition[],
    onToken?: (token: string) => void
  ): Promise<{ response: string; stats: TokenStats }>;
  
  initialize(config: any): Promise<void>;
  cleanup(): Promise<void>;
  getTokenStats(): TokenStats;
  resetTokenStats(): void;
}

