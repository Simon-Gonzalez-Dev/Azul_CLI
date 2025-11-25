import { BaseLLMProvider, ProviderInfo } from "./base.js";
import { ChatMessage } from "../types.js";

type GeminiPart = { text: string };
type GeminiContent = { role: string; parts: GeminiPart[] };

export class GeminiProvider extends BaseLLMProvider {
  private readonly apiKey: string;
  private readonly providerName = "Google Gemini";
  private model: string = "gemini-2.0-flash-001";

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
    console.log(`  Gemini Provider ready (model: ${this.model})`);
  }

  async cleanup(): Promise<void> {
    // Stateless HTTP client
  }

  private buildGeminiPayload(messages: ChatMessage[]): {
    systemInstruction?: { parts: GeminiPart[] };
    contents: GeminiContent[];
  } {
    const contents: GeminiContent[] = [];
    let systemInstruction;

    messages.forEach((msg, index) => {
      if (index === 0 && msg.role === "system") {
        systemInstruction = {
          parts: [{ text: msg.content ?? "" }],
        };
        return;
      }

      if (msg.role === "tool") {
        contents.push({
          role: "user",
          parts: [{ text: this.formatToolResult(msg.content, msg.tool_call_id) }],
        });
        return;
      }

      const role = msg.role === "assistant" ? "model" : "user";
      let text = msg.content ?? "";
      if (msg.role === "assistant" && msg.tool_calls && msg.tool_calls.length > 0) {
        const xmlCalls = this.formatToolCallsAsXml(msg.tool_calls);
        text = `${text}\n${xmlCalls}`.trim();
      }

      contents.push({
        role,
        parts: [{ text }],
      });
    });

    return { systemInstruction, contents };
  }

  protected async generateCompletion(
    messages: ChatMessage[],
    onToken?: (token: string) => void
  ): Promise<{ response: string; inputTokens: number; outputTokens: number }> {
    try {
      const { systemInstruction, contents } = this.buildGeminiPayload(messages);
      const url = `https://generativelanguage.googleapis.com/v1beta/models/${this.model}:streamGenerateContent?alt=sse&key=${this.apiKey}`;

      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          contents,
          systemInstruction,
          generationConfig: {
            temperature: 0.4,
            maxOutputTokens: 4096,
          },
        }),
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(`Gemini API error: ${response.status} - ${text}`);
      }

      if (!response.body) {
        throw new Error("Gemini API returned no response body");
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
            const candidates = payload.candidates ?? [];
            for (const candidate of candidates) {
              const parts: GeminiPart[] = candidate.content?.parts ?? [];
              for (const part of parts) {
                if (part.text) {
                  fullResponse += part.text;
                  if (onToken) onToken(fullResponse);
                }
              }
            }
          } catch {
            // Ignore partial chunks
          }
        }
      }

      const promptSegments = [
        ...(systemInstruction?.parts ?? []).map((p) => p.text),
        ...contents.flatMap((c) => c.parts.map((p) => p.text)),
      ].join("\n");

      const inputTokens = this.estimateTokensFromText(promptSegments);
      const outputTokens = this.estimateTokensFromText(fullResponse);

      return {
        response: fullResponse,
        inputTokens,
        outputTokens,
      };
    } catch (error) {
      console.error("Gemini generation error:", error);
      throw error;
    }
  }
}

