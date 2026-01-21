import { ILLMService } from "./llm-interface.js";
import { ChatMessage, ToolDefinition, ToolCall, TokenStats } from "./types.js";
import { LocalProvider } from "./providers/local.js";

interface ProviderConfig {
  localModelPath: string;
  localContextSize?: number;
  localMaxTokens?: number;
}

export interface ProviderStatus {
  provider: string;
  model: string;
}

export class LLMOrchestrator implements ILLMService {
  private provider: LocalProvider | null = null;
  private readonly config: ProviderConfig;
  private readonly onStatusChange?: (status: ProviderStatus) => void;
  private initialized = false;

  constructor(
    config: ProviderConfig,
    onStatusChange?: (status: ProviderStatus) => void
  ) {
    this.config = config;
    this.onStatusChange = onStatusChange;
  }

  async initialize(): Promise<void> {
    if (this.initialized) {
      return;
    }

    if (!this.config.localModelPath) {
      throw new Error("Local model path is required.");
    }

    const contextSize = this.config.localContextSize ?? 8192;
    const maxTokens = this.config.localMaxTokens ?? 2048;

    this.provider = new LocalProvider(this.config.localModelPath, contextSize, maxTokens);
    await this.provider.initialize();

    this.emitStatus();
    this.initialized = true;
  }

  private emitStatus() {
    if (!this.onStatusChange || !this.provider) {
      return;
    }
    const info = this.provider.getProviderInfo();
    this.onStatusChange({
      provider: info.provider,
      model: info.model,
    });
  }

  async cleanup(): Promise<void> {
    if (this.provider) {
      await this.provider.cleanup();
    }
  }

  getTokenStats(): TokenStats {
    if (!this.provider) {
      return {
        inputTokens: 0,
        outputTokens: 0,
        totalTokens: 0,
        tokensPerSecond: 0,
        generationTimeMs: 0,
      };
    }
    return this.provider.getTokenStats();
  }

  resetTokenStats(): void {
    if (this.provider) {
      this.provider.resetTokenStats();
    }
  }

  async getCompletion(
    systemPrompt: string,
    conversationHistory: ChatMessage[],
    tools?: ToolDefinition[],
    onToken?: (token: string) => void
  ): Promise<{ response: string; toolCalls?: ToolCall[]; stats: TokenStats }> {
    if (!this.provider) {
      throw new Error("Provider not initialized. Call initialize() first.");
    }

    return this.provider.getCompletion(
      systemPrompt,
      conversationHistory,
      tools,
      onToken
    );
  }
}
