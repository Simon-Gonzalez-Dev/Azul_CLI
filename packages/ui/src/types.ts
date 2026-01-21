// =============================================================================
// INPUT & AGENT MODES
// =============================================================================

/** Input mode based on prefix character */
export type InputMode = 'chat' | 'bash' | 'command';

/** Agent execution mode (toggled with Shift+Tab) */
export type AgentMode = 'normal' | 'plan';

/** Plan step for plan mode */
export interface PlanStep {
  id: string;
  description: string;
  toolName?: string;
  toolArgs?: Record<string, any>;
  status: 'pending' | 'approved' | 'executing' | 'completed' | 'failed';
  result?: string;
  error?: string;
}

// =============================================================================
// MESSAGES
// =============================================================================

export interface Message {
  type: string;
  content?: string;
  timestamp: number;
  [key: string]: any;
}

// =============================================================================
// APP STATE
// =============================================================================

export interface AppState {
  messages: Message[];
  connected: boolean;
  userInput: string;
  pendingApproval: ApprovalRequest | null;
  tokenStats: TokenStats;
  providerStatus?: ProviderStatusMessage;
  contextStats?: ContextStats;
  // New mode-related state
  inputMode: InputMode;
  agentMode: AgentMode;
  planSteps: PlanStep[] | null;
  pendingPlan: boolean;  // True when waiting for plan approval
}

// =============================================================================
// APPROVAL & PERMISSIONS
// =============================================================================

export interface ApprovalRequest {
  requestId: string;
  tool: string;
  args: any;
  diff?: string;
  added?: number;
  removed?: number;
}

// =============================================================================
// TOKEN & CONTEXT STATS
// =============================================================================

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

export interface ContextStats {
  estimatedTokens: number;
  maxTokens: number;
  usagePercent: number;
  messageCount: number;
  compressedCount: number;
}

// =============================================================================
// PROVIDER STATUS
// =============================================================================

export interface ProviderStatusMessage {
  provider: string;
  model: string;
}

// =============================================================================
// COMMANDS
// =============================================================================

export interface Command {
  name: string;
  description: string;
  shortcut?: string;
}

/** Available slash commands */
export const COMMANDS: Command[] = [
  { name: "help", description: "Show available commands" },
  { name: "reset", description: "Reset agent memory/context" },
  { name: "clear", description: "Clear the screen" },
  { name: "cd", description: "Change directory (e.g., /cd /path)" },
  { name: "ls", description: "List directory contents" },
  { name: "plan", description: "Toggle plan mode", shortcut: "Shift+Tab" },
  { name: "config", description: "Show configuration" },
  { name: "quit", description: "Exit the application" },
];

/** Recent bash commands (maintained at runtime) */
export const RECENT_BASH_COMMANDS: string[] = [];
