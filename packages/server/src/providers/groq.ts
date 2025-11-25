import { BaseLLMProvider, ProviderInfo } from "./base.js";
import { ChatMessage } from "../types.js";

export class GroqProvider extends BaseLLMProvider {
  private readonly apiKey: string;
  private readonly providerName = "Groq";
  private model: string = "llama-3.3-70b-versatile";

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
    console.log(`  Groq Provider ready (model: ${this.model})`);
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
      const response = await fetch("https://api.groq.com/openai/v1/chat/completions", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: this.model,
          messages: formattedMessages,
          max_tokens: 4096,
          stream: true,
          temperature: 0.4,
        }),
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(`Groq API error: ${response.status} - ${text}`);
      }

      if (!response.body) {
        throw new Error("Groq API returned no response body");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullResponse = "";
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || trimmed === "data: [DONE]") continue;
          if (!trimmed.startsWith("data:")) continue;

          try {
            const payload = JSON.parse(trimmed.slice(5).trim());
            const delta = payload.choices?.[0]?.delta?.content;
            if (delta) {
              fullResponse += delta;
              if (onToken) onToken(fullResponse);
            }
          } catch {
            // Ignore partial chunks
          }
        }
      }

      const promptText = formattedMessages.map((m) => m.content).join("\n");
      const inputTokens = this.estimateTokensFromText(promptText);
      const outputTokens = this.estimateTokensFromText(fullResponse);

      return {
        response: fullResponse,
        inputTokens,
        outputTokens,
      };
    } catch (error) {
      console.error("Groq generation error:", error);
      throw error;
    }
  }
}

