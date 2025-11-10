import { getLlama, LlamaModel, LlamaContext, LlamaChatSession } from "node-llama-cpp";
import { ChatMessage, ToolDefinition, TokenStats, Config } from "./types.js";
import * as path from "path";

function estimateTokens(text: string): number {
  const words = text.split(/\s+/).filter(w => w.length > 0).length;
  const chars = text.length;
  return Math.ceil((words * 0.75 + chars / 4) / 2);
}

export class LLMService {
  private model: LlamaModel | null = null;
  private context: LlamaContext | null = null;
  private session: LlamaChatSession | null = null;
  private config: Config;
  private totalInputTokens: number = 0;
  private totalOutputTokens: number = 0;

  constructor(config: Config) {
    this.config = config;
  }

  getTokenStats(): TokenStats {
    return {
      inputTokens: this.totalInputTokens,
      outputTokens: this.totalOutputTokens,
      totalTokens: this.totalInputTokens + this.totalOutputTokens,
      tokensPerSecond: 0,
      generationTimeMs: 0,
    };
  }

  resetTokenStats(): void {
    this.totalInputTokens = 0;
    this.totalOutputTokens = 0;
  }

  async initialize(modelPath: string): Promise<void> {
    console.log("  Initializing LLM with Metal acceleration...");
    console.log(`  Loading model from: ${modelPath}`);
    
    const isMacOS = process.platform === 'darwin';
    if (isMacOS) {
      console.log("  macOS detected - Using Metal GPU acceleration");
      console.log(`  GPU Layers: ${this.config.gpuLayers === 999 ? 'all' : this.config.gpuLayers}`);
      console.log(`  Threads: ${this.config.threads}`);
      console.log(`  Flash Attention: ${this.config.flashAttention ? 'enabled' : 'disabled'}`);
    } else {
      console.log("  Using CPU inference");
    }

    const llama = await getLlama();
    
    // Load model with Metal optimization settings
    this.model = await llama.loadModel({
      modelPath: modelPath,
      gpuLayers: this.config.gpuLayers === 999 ? undefined : this.config.gpuLayers,
      // Note: threads, flashAttention, batchSize, memoryLock are context-level settings
    });

    // Create context with optimization settings
    this.context = await this.model.createContext({
      contextSize: this.config.contextSize,
      threads: this.config.threads,
      // Note: flashAttention, batchSize, memoryLock may need to be set differently
      // Check node-llama-cpp docs for exact API
    });

    // Create chat session
    this.session = new LlamaChatSession({
      contextSequence: this.context.getSequence(),
    });

    console.log(`   LLM initialized successfully`);
    console.log(`   Context Size: ${this.config.contextSize.toLocaleString()} tokens`);
    console.log(`   Max Output: ${this.config.maxTokens.toLocaleString()} tokens`);
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
  "thought": "Your reasoning about what to do, including any enhancements you'll add",
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
}

CRITICAL GUIDELINES FOR FILE GENERATION:
- Generate COMPLETE, FULL implementations - never truncate or summarize code
- Include ALL necessary code, imports, functions, classes, and complete implementations
- For HTML/CSS/JS files: Provide the entire file with beautiful, modern designs
- Add thoughtful features and enhancements beyond the basic requirements
- Create production-ready code with proper error handling and best practices
- For multi-page or large files: Generate ALL content completely, don't abbreviate
- Think like a senior engineer: add polish, design, and features that elevate the solution`;
    }

    // Build conversation history (excluding system message)
    const conversationMessages = messages.filter(m => m.role !== "system");
    let inputTokenCount = estimateTokens(systemPrompt);

    // Count tokens for all messages
    for (const msg of conversationMessages) {
      inputTokenCount += estimateTokens(msg.content);
    }

    this.totalInputTokens += inputTokenCount;

    const startTime = Date.now();

    try {
      // Build full prompt with system prompt and conversation
      let fullPrompt = systemPrompt;
      for (const msg of conversationMessages) {
        if (msg.role === "user") {
          fullPrompt += `\n\nUser: ${msg.content}`;
        } else if (msg.role === "assistant") {
          fullPrompt += `\n\nAssistant: ${msg.content}`;
        }
      }
      fullPrompt += "\n\nAssistant:";

      // Use the session to generate response
      const response = await this.session.prompt(fullPrompt, {
        maxTokens: this.config.maxTokens,
        temperature: this.config.temperature,
        topP: this.config.topP,
        topK: this.config.topK,
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
