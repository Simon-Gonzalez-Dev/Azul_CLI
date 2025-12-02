import path from "path";
import { BaseLLMProvider, ProviderInfo } from "./base.js";
import { ChatMessage } from "../types.js";
import { getLlama, LlamaModel, LlamaContext, LlamaChatSession, TokenMeter, Token } from "node-llama-cpp";

export class LocalProvider extends BaseLLMProvider {
  private readonly modelPath: string;
  private readonly contextSize: number;
  private readonly maxTokens: number;

  private model: LlamaModel | null = null;
  private context: LlamaContext | null = null;
  private session: LlamaChatSession | null = null;

  constructor(modelPath: string, contextSize: number = 8192, maxTokens: number = 2048) {
    super();
    this.modelPath = modelPath;
    this.contextSize = contextSize;
    this.maxTokens = maxTokens;
  }

  getProviderInfo(): ProviderInfo {
    return {
      provider: "Local GGUF",
      model: path.basename(this.modelPath),
    };
  }

  async initialize(): Promise<void> {
    // Load model silently - UI will show status
    const llama = await getLlama();
    this.model = await llama.loadModel({ modelPath: this.modelPath });
    this.context = await this.model.createContext({ contextSize: this.contextSize });
    this.session = new LlamaChatSession({
      contextSequence: this.context.getSequence(),
    });
  }

  async cleanup(): Promise<void> {
    if (this.context) {
      await this.context.dispose();
      this.context = null;
    }
    if (this.model) {
      await this.model.dispose();
      this.model = null;
    }
    this.session = null;
  }

  protected async generateCompletion(
    messages: ChatMessage[],
    onToken?: (token: string) => void
  ): Promise<{ response: string; inputTokens: number; outputTokens: number }> {
    if (!this.session || !this.model) {
      throw new Error("Local LLM not initialized");
    }

    const prompt = this.formatConversationAsPlaintext(messages);
    const sequence = this.session.sequence;
    const meterStart = sequence.tokenMeter.getState();

    let streamedOutputTokens = 0;
    let streamedText = "";

    const startTime = Date.now();

    const responseText = await this.session.prompt(prompt, {
      maxTokens: this.maxTokens,
      temperature: 0.4,
      onTextChunk: (chunk: string) => {
        if (!chunk) {
          return;
        }
        streamedText += chunk;
        // Always call onToken callback immediately for smooth streaming
        // No throttling - let the UI handle rendering performance
        if (onToken) {
          onToken(streamedText);
        }
      },
      onToken: (tokens: Token[]) => {
        streamedOutputTokens += tokens.length;
        // Safety net: If onTextChunk didn't fire for some reason, ensure streaming
        // This handles edge cases where text chunks might be delayed
        if (onToken && tokens.length > 0 && streamedText) {
          // Only call if we have accumulated text and onTextChunk might have missed it
          // This ensures every token triggers streaming callback
          onToken(streamedText);
        }
      },
    });

    const endTime = Date.now();
    const meterEnd = sequence.tokenMeter.getState();
    const diff = TokenMeter.diff(meterEnd, meterStart);

    const inputTokens = diff.usedInputTokens;
    const outputTokens = diff.usedOutputTokens || streamedOutputTokens;

    const finalResponse = streamedText || responseText || "";

    return {
      response: finalResponse,
      inputTokens,
      outputTokens,
    };
  }
}

