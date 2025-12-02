import { BaseLLMProvider, ProviderInfo } from "./base.js";
import { ChatMessage } from "../types.js";
import { parseSSEStream } from "./stream-utils.js";

export class HuggingFaceProvider extends BaseLLMProvider {
  private readonly apiKey: string;
  private readonly providerName = "HuggingFace Inference";
  private readonly apiUrl = "https://api-inference.huggingface.co/v1/chat/completions";
  private model: string = "meta-llama/Meta-Llama-3-8B-Instruct";

  constructor(apiKey: string, model?: string) {
    super();
    this.apiKey = apiKey.trim();
    if (model && model.trim().length > 0) {
      this.model = model.trim();
    }
  }

  getProviderInfo(): ProviderInfo {
    return {
      provider: this.providerName,
      model: this.model,
    };
  }

  async initialize(): Promise<void> {
    // Provider ready - no console output needed (UI shows status)
  }

  async cleanup(): Promise<void> {
    // Stateless HTTP client
  }

  protected async generateCompletion(
    messages: ChatMessage[],
    onToken?: (token: string) => void
  ): Promise<{ response: string; inputTokens: number; outputTokens: number }> {
    try {
      const formattedMessages = this.mapToOpenAIChatMessages(messages);

      const response = await fetch(this.apiUrl, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: this.model,
          messages: formattedMessages,
          max_tokens: 2048,
          stream: true,
          temperature: 0.4,
        }),
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(`HuggingFace API error: ${response.status} - ${text}`);
      }

      if (!response.body) {
        throw new Error("HuggingFace API returned no response body");
      }

      const reader = response.body.getReader();
      const fullResponse = await parseSSEStream(reader, onToken);

      const promptText = formattedMessages.map((m) => m.content).join("\n");
      const inputTokens = this.estimateTokensFromText(promptText);
      const outputTokens = this.estimateTokensFromText(fullResponse);

      return {
        response: fullResponse,
        inputTokens,
        outputTokens,
      };
    } catch (error) {
      throw error;
    }
  }
}

