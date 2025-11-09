import { getLlama, LlamaModel, LlamaContext, LlamaChatSession } from "node-llama-cpp";
import { ChatMessage, ToolDefinition, TokenStats } from "./types.js";
import * as path from "path";

// Simple token counter - approximates tokens by counting words and characters
// This is a rough approximation; for accurate counting, you'd need the model's tokenizer
function estimateTokens(text: string): number {
  // Rough approximation: ~0.75 tokens per word, or ~4 characters per token
  const words = text.split(/\s+/).filter(w => w.length > 0).length;
  const chars = text.length;
  // Use the average of both methods
  return Math.ceil((words * 0.75 + chars / 4) / 2);
}

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
    console.log("🔧 Initializing LLM...");
    console.log(`📁 Loading model from: ${modelPath}`);

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

    console.log("✅ LLM initialized successfully");
  }

  async getCompletion(
    messages: ChatMessage[],
    tools?: ToolDefinition[]
  ): Promise<{ response: string; stats: TokenStats }> {
    if (!this.session) {
      throw new Error("LLM not initialized. Call initialize() first.");
    }

    // Build the system prompt with tool definitions
    let systemPrompt = messages.find(m => m.role === "system")?.content || "";
    
    if (tools && tools.length > 0) {
      systemPrompt += "\n\nYou have access to the following tools:\n\n";
      tools.forEach(tool => {
        systemPrompt += `### ${tool.name}\n`;
        systemPrompt += `Description: ${tool.description}\n`;
        systemPrompt += `Parameters: ${JSON.stringify(tool.parameters, null, 2)}\n\n`;
      });
      
      systemPrompt += `\nTo use a tool, respond with a JSON object in this format:
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

    // Build full conversation history for token counting
    let fullPrompt = systemPrompt;
    let inputTokenCount = estimateTokens(systemPrompt);

    // Include all conversation messages
    for (const msg of messages) {
      if (msg.role === "user") {
        fullPrompt += `\n\nUser: ${msg.content}`;
        inputTokenCount += estimateTokens(`User: ${msg.content}`);
      } else if (msg.role === "assistant") {
        fullPrompt += `\n\nAssistant: ${msg.content}`;
        inputTokenCount += estimateTokens(`Assistant: ${msg.content}`);
      }
    }

    fullPrompt += "\n\nAssistant:";

    // Count input tokens
    this.totalInputTokens += inputTokenCount;

    const startTime = Date.now();

    try {
      const response = await this.session.prompt(fullPrompt, {
        maxTokens: this.maxTokens,
        temperature: 0.7,
      });

      const endTime = Date.now();
      const generationTimeMs = endTime - startTime;
      const outputTokenCount = estimateTokens(response);
      this.totalOutputTokens += outputTokenCount;

      const tokensPerSecond = outputTokenCount / (generationTimeMs / 1000);

      const stats: TokenStats = {
        inputTokens: inputTokenCount,
        outputTokens: outputTokenCount,
        totalTokens: inputTokenCount + outputTokenCount,
        tokensPerSecond: tokensPerSecond,
        generationTimeMs: generationTimeMs,
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

