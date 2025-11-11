import { getLlama, LlamaModel, LlamaContext, LlamaChatSession, TokenMeter } from "node-llama-cpp";
import { ChatMessage, ToolDefinition, TokenStats } from "./types.js";
import * as path from "path";

export class LLMService {
  private model: LlamaModel | null = null;
  private context: LlamaContext | null = null;
  private session: LlamaChatSession | null = null;
  private contextSize: number;
  private maxTokens: number;
  private totalInputTokens: number = 0;
  private totalOutputTokens: number = 0;

  constructor(contextSize: number = 8192, maxTokens: number = 2048) {
    this.contextSize = contextSize;
    this.maxTokens = maxTokens;
  }

  getTokenStats(): TokenStats {
    return {
      inputTokens: this.totalInputTokens,
      outputTokens: this.totalOutputTokens,
      totalTokens: this.totalInputTokens + this.totalOutputTokens,
      tokensPerSecond: 0, // Will be calculated per generation
      generationTimeMs: 0,
    };
  }

  resetTokenStats(): void {
    this.totalInputTokens = 0;
    this.totalOutputTokens = 0;
  }

  async initialize(modelPath: string): Promise<void> {
    console.log("  Initializing LLM...");
    console.log(`  Loading model from: ${modelPath}`);

    const llama = await getLlama();
    
    this.model = await llama.loadModel({
      modelPath: modelPath,
    });

    this.context = await this.model.createContext({
      contextSize: this.contextSize,
    });

    this.session = new LlamaChatSession({
      contextSequence: this.context.getSequence(),
    });

    
  }

  async getCompletion(
    systemPrompt: string,
    conversationHistory: ChatMessage[],
    tools?: ToolDefinition[]
  ): Promise<{ response: string; stats: TokenStats }> {
    if (!this.session || !this.model) {
      throw new Error("LLM not initialized. Call initialize() first.");
    }

    // Build the system prompt with tool definitions
    // System prompt is passed separately and will be cached by KV cache
    let fullSystemPrompt = systemPrompt;
    
    if (tools && tools.length > 0) {
      fullSystemPrompt += "\n\nYou have access to the following tools:\n\n";
      tools.forEach(tool => {
        fullSystemPrompt += `### ${tool.name}\n`;
        fullSystemPrompt += `Description: ${tool.description}\n`;
        fullSystemPrompt += `Parameters: ${JSON.stringify(tool.parameters, null, 2)}\n\n`;
      });
      
      fullSystemPrompt += `\nTo use a tool, respond with a JSON object in this format:
{
  "thought": "Your reasoning about what to do",
  "tool_calls": [
    {
      "name": "tool_name",
      "arguments": { "param1": "value1" }
    }
  ]
}

If you don't need to use any tools, respond with:
{
  "thought": "Your response",
  "response": "Your answer to the user"
}`;
    }

    // Build full prompt: system prompt + conversation history
    // The KV cache will efficiently handle the repeated system prompt
    let fullPrompt = fullSystemPrompt;

    // Include conversation history (only user and assistant messages)
    for (const msg of conversationHistory) {
      if (msg.role === "user") {
        fullPrompt += `\n\nUser: ${msg.content}`;
      } else if (msg.role === "assistant") {
        fullPrompt += `\n\nAssistant: ${msg.content}`;
      }
    }

    fullPrompt += "\n\nAssistant:";

    // Token metrics
    const promptTokens = this.model.tokenize(fullPrompt, true).length;
    const sequence = this.session.sequence;
    const meterStart = sequence.tokenMeter.getState();

    const startTime = Date.now();
    let streamedOutputTokens = 0;

    try {
      const response = await this.session.prompt(fullPrompt, {
        maxTokens: this.maxTokens,
        temperature: 0.7,
        onToken: (tokens) => {
          streamedOutputTokens += tokens.length;
        },
      });

      const endTime = Date.now();
      const generationTimeMs = endTime - startTime;
      const meterEnd = sequence.tokenMeter.getState();
      const meterDiff = TokenMeter.diff(meterEnd, meterStart);

      const inputTokenCount = meterDiff.usedInputTokens;
      const outputTokenCount = meterDiff.usedOutputTokens || streamedOutputTokens;

      this.totalInputTokens += inputTokenCount;
      this.totalOutputTokens += outputTokenCount;

      const tokensPerSecond =
        outputTokenCount > 0 && generationTimeMs > 0
          ? outputTokenCount / (generationTimeMs / 1000)
          : 0;

      const stats: TokenStats = {
        inputTokens: inputTokenCount,
        outputTokens: outputTokenCount,
        totalTokens: inputTokenCount + outputTokenCount,
        tokensPerSecond: tokensPerSecond,
        generationTimeMs: generationTimeMs,
        promptTokens,
        contextTokens: sequence.contextTokens.length,
      };

      return { response, stats };
    } catch (error) {
      console.error("Error generating completion:", error);
      throw error;
    }
  }

  async cleanup(): Promise<void> {
    if (this.context) {
      await this.context.dispose();
    }
    if (this.model) {
      await this.model.dispose();
    }
  }
}

