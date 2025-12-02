import { ILLMService } from "./llm-interface.js";
import { ChatMessage, ToolDefinition, ToolCall, TokenStats } from "./types.js";
import { BaseLLMProvider, ProviderInfo } from "./providers/base.js";
import { HuggingFaceProvider } from "./providers/huggingface.js";
import { GeminiProvider } from "./providers/gemini.js";
import { GroqProvider } from "./providers/groq.js";
import { OpenRouterProvider } from "./providers/openrouter.js";
import { LocalProvider } from "./providers/local.js";

interface ProviderConfig {
  hfApiKey?: string;
  hfModel?: string;
  geminiApiKey?: string;
  geminiModel?: string;
  groqApiKey?: string;
  groqModel?: string;
  openRouterApiKey?: string;
  openRouterModel?: string;
  localModelPath?: string;
  localContextSize?: number;
  localMaxTokens?: number;
}

interface ProviderEntry {
  instance: BaseLLMProvider;
  initialized: boolean;
}

export interface ProviderStatus {
  mode: "local" | "api";
  provider: string;
  model: string;
  fallback?: boolean;
  reason?: string;
  previousProvider?: string;
}

export class LLMOrchestrator implements ILLMService {
  private readonly providers: ProviderEntry[] = [];
  private readonly mode: "local" | "api";
  private readonly config: ProviderConfig;
  private readonly onStatusChange?: (status: ProviderStatus) => void;
  private activeProviderIndex = 0;
  private initialized = false;

  constructor(
    config: ProviderConfig,
    isApiMode: boolean,
    onStatusChange?: (status: ProviderStatus) => void
  ) {
    this.config = config;
    this.mode = isApiMode ? "api" : "local";
    this.onStatusChange = onStatusChange;
  }

  async initialize(): Promise<void> {
    if (this.initialized) {
      return;
    }

    if (this.mode === "local") {
      if (!this.config.localModelPath) {
        throw new Error("Local model path is required for local mode.");
      }
      const contextSize = this.config.localContextSize ?? 8192;
      const maxTokens = this.config.localMaxTokens ?? 2048;
      this.providers.push({
        instance: new LocalProvider(this.config.localModelPath, contextSize, maxTokens),
        initialized: false,
      });
    } else {
      // API provider order: HuggingFace, Groq, OpenRouter, Gemini (Gemini last)
      if (this.config.hfApiKey) {
        this.providers.push({
          instance: new HuggingFaceProvider(this.config.hfApiKey, this.config.hfModel),
          initialized: false,
        });
      }
      if (this.config.groqApiKey) {
        this.providers.push({
          instance: new GroqProvider(this.config.groqApiKey, this.config.groqModel),
          initialized: false,
        });
      }
      if (this.config.openRouterApiKey) {
        this.providers.push({
          instance: new OpenRouterProvider(
            this.config.openRouterApiKey,
            this.config.openRouterModel
          ),
          initialized: false,
        });
      }
      if (this.config.geminiApiKey) {
        this.providers.push({
          instance: new GeminiProvider(this.config.geminiApiKey, this.config.geminiModel),
          initialized: false,
        });
      }

      if (this.providers.length === 0) {
        throw new Error("No API keys provided for API mode.");
      }
    }

    await this.ensureProviderInitialized(0);
    this.activeProviderIndex = 0;
    this.emitStatus({ fallback: false });
    this.initialized = true;
  }

  private async ensureProviderInitialized(index: number): Promise<void> {
    const entry = this.providers[index];
    if (!entry.initialized) {
      await entry.instance.initialize({});
      entry.initialized = true;
    }
  }

  private emitStatus(update: { fallback: boolean; reason?: string; previousProvider?: string }) {
    if (!this.onStatusChange) {
      return;
    }
    const info = this.providers[this.activeProviderIndex].instance.getProviderInfo();
    this.onStatusChange({
      mode: this.mode,
      provider: info.provider,
      model: info.model,
      fallback: update.fallback,
      reason: update.reason,
      previousProvider: update.previousProvider,
    });
  }

  private emitUpcomingFallback(nextIndex: number, reason: string, previousInfo: ProviderInfo) {
    if (!this.onStatusChange) {
      return;
    }
    const nextInfo = this.providers[nextIndex].instance.getProviderInfo();
    this.onStatusChange({
      mode: this.mode,
      provider: nextInfo.provider,
      model: nextInfo.model,
      fallback: true,
      reason,
      previousProvider: previousInfo.provider,
    });
  }

  async cleanup(): Promise<void> {
    for (const entry of this.providers) {
      await entry.instance.cleanup();
    }
  }

  getTokenStats(): TokenStats {
    if (this.providers.length === 0) {
      return {
        inputTokens: 0,
        outputTokens: 0,
        totalTokens: 0,
        tokensPerSecond: 0,
        generationTimeMs: 0,
      };
    }
    return this.providers[this.activeProviderIndex].instance.getTokenStats();
  }

  resetTokenStats(): void {
    this.providers.forEach((entry) => entry.instance.resetTokenStats());
  }

  async getCompletion(
    systemPrompt: string,
    conversationHistory: ChatMessage[],
    tools?: ToolDefinition[],
    onToken?: (token: string) => void
  ): Promise<{ response: string; toolCalls?: ToolCall[]; stats: TokenStats }> {
    let lastError: unknown = null;

    for (let i = 0; i < this.providers.length; i++) {
      try {
        await this.ensureProviderInitialized(i);
        const result = await this.providers[i].instance.getCompletion(
          systemPrompt,
          conversationHistory,
          tools,
          onToken
        );
        if (this.activeProviderIndex !== i) {
          this.activeProviderIndex = i;
          this.emitStatus({ fallback: false });
        } else if (!this.initialized) {
          this.emitStatus({ fallback: false });
        }
        return result;
      } catch (error: any) {
        lastError = error;
        const reason =
          typeof error?.message === "string"
            ? error.message
            : typeof error === "string"
            ? error
            : "Unknown provider error";

        const isLastProvider = i === this.providers.length - 1;
        if (this.mode === "local" || isLastProvider) {
          const info = this.providers[i].instance.getProviderInfo();
          throw new Error(
            `All providers failed. Last provider (${info.provider}) error: ${reason}`
          );
        }

        const previousInfo = this.providers[i].instance.getProviderInfo();
        this.emitUpcomingFallback(i + 1, reason, previousInfo);
      }
    }

    throw lastError ?? new Error("No providers available");
  }
}

