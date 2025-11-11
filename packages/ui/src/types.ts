export interface Message {
  type: string;
  content?: string;
  timestamp: number;
  [key: string]: any;
}

export interface AppState {
  messages: Message[];
  connected: boolean;
  userInput: string;
  pendingApproval: ApprovalRequest | null;
  tokenStats: TokenStats;
}

export interface ApprovalRequest {
  requestId: string;
  tool: string;
  args: any;
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

