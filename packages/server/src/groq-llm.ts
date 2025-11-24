import Groq from "groq-sdk";
import { ChatMessage, ToolDefinition, TokenStats } from "./types.js";
import { ILLMService } from "./llm-interface.js";

export class GroqLLMService implements ILLMService {
  private groq: Groq;
  private apiKey: string;
  private model: string = "openai/gpt-oss-20b";
  private totalInputTokens: number = 0;
  private totalOutputTokens: number = 0;
  private chatHistory: ChatMessage[] = [];

  constructor(apiKey: string, model?: string) {
    // Validate API key
    if (!apiKey || typeof apiKey !== 'string' || apiKey.trim().length === 0) {
      throw new Error('Groq API key is required and cannot be empty');
    }
    this.apiKey = apiKey.trim();
    this.groq = new Groq({ apiKey: this.apiKey });
    if (model) {
      this.model = model;
    }
  }

  async initialize(config: any): Promise<void> {
    // Log masked API key for debugging
    const maskedKey = this.apiKey.length > 11 
      ? `${this.apiKey.substring(0, 7)}...${this.apiKey.substring(this.apiKey.length - 4)}`
      : '***';
    console.log(`  Groq API initialized (model: ${this.model}, key: ${maskedKey})`);
  }

  async cleanup(): Promise<void> {
    // Nothing to clean up
  }

  getTokenStats(): TokenStats {
    return {
      inputTokens: this.totalInputTokens,
      outputTokens: this.totalOutputTokens,
      totalTokens: this.totalInputTokens + this.totalOutputTokens,
      tokensPerSecond: 0,
      generationTimeMs: 0,
      totalInputTokens: this.totalInputTokens,
      totalOutputTokens: this.totalOutputTokens,
    };
  }

  resetTokenStats(): void {
    this.totalInputTokens = 0;
    this.totalOutputTokens = 0;
    this.chatHistory = [];
  }

  async getCompletion(
    systemPrompt: string,
    conversationHistory: ChatMessage[],
    tools?: ToolDefinition[],
    onToken?: (token: string) => void
  ): Promise<{ response: string; stats: TokenStats }> {
    const startTime = Date.now();

    // Build messages array for Groq API
    const messages: any[] = [
      { role: "system", content: this.buildSystemPrompt(systemPrompt, tools) }
    ];

    // Add conversation history
    for (const msg of conversationHistory) {
      if (msg.role === "tool") {
        // Groq uses different format for tool responses
        // We'll encode it as a user message with context
        messages.push({
          role: "user",
          content: `[Tool Result: ${msg.tool_call_id}]\n${msg.content}`
        });
      } else if (msg.role === "assistant" && msg.tool_calls) {
        // Format tool calls as assistant message
        messages.push({
          role: "assistant",
          content: JSON.stringify({
            thought: "Using tools to complete the task",
            tool_calls: msg.tool_calls
          })
        });
      } else {
        messages.push({
          role: msg.role,
          content: msg.content
        });
      }
    }

    try {
      let content = "";
      let inputTokens = 0;
      let outputTokens = 0;
      let totalTokens = 0;

      // Use streaming if onToken callback is provided
      if (onToken) {
        // Handle streaming response - Groq SDK returns async iterable when stream: true
        const stream = await this.groq.chat.completions.create({
          messages: messages,
          model: this.model,
          temperature: 0.9,
          max_tokens: 8192,
          top_p: 1,
          stop: null,
          stream: true,
        });

        let accumulatedContent = "";
        for await (const chunk of stream) {
          const deltaContent = chunk.choices?.[0]?.delta?.content;
          if (deltaContent) {
            accumulatedContent += deltaContent;
            content = accumulatedContent;
            // Stream accumulated content
            onToken(content);
          }

          // Note: Groq streaming chunks don't include usage stats
          // We'll estimate tokens or leave them at 0 for streaming
          // Usage stats are only available in non-streaming responses
        }

        // For streaming, we don't have usage stats from the API
        // You could estimate tokens here if needed, but we'll leave them at 0
        // The cumulative stats won't be updated for streaming responses
      } else {
        // Non-streaming response
        const data = await this.groq.chat.completions.create({
          messages: messages,
          model: this.model,
          temperature: 0.9,
          max_tokens: 8192,
          top_p: 1,
          stop: null,
          stream: false,
        });

        content = data.choices?.[0]?.message?.content || "";

        // Update token stats if available
        if (data.usage) {
          inputTokens = data.usage.prompt_tokens || 0;
          outputTokens = data.usage.completion_tokens || 0;
          totalTokens = data.usage.total_tokens || 0;
          
          this.totalInputTokens += inputTokens;
          this.totalOutputTokens += outputTokens;
        }
      }

      const endTime = Date.now();
      const generationTimeMs = endTime - startTime;
      const tokensPerSecond = outputTokens > 0 && generationTimeMs > 0
        ? outputTokens / (generationTimeMs / 1000)
        : 0;

      const stats: TokenStats = {
        inputTokens: inputTokens,
        outputTokens: outputTokens,
        totalTokens: totalTokens,
        tokensPerSecond: tokensPerSecond,
        generationTimeMs: generationTimeMs,
      };

      return { response: content, stats };
    } catch (error: any) {
      console.error("Error calling Groq API:", error);
      let errorMessage = `Groq API error: ${error.message || error}`;
      
      // Provide helpful error messages for common issues
      if (error.status === 401) {
        errorMessage += '\n\nAuthentication failed. Please check that your GROK_API_KEY is correct in your .env file.';
      } else if (error.status === 429) {
        errorMessage += '\n\nRate limit exceeded. Please try again later.';
      }
      
      throw new Error(errorMessage);
    }
  }

  private buildSystemPrompt(systemPrompt: string, tools?: ToolDefinition[]): string {
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

IMPORTANT:
- When the user asks you to create, update, or modify a file, you MUST use the write_file tool
- Do NOT just show the code in your response - actually call the write_file tool
- Extract code from markdown blocks before writing (remove \`\`\` markers)

If you don't need to use any tools, respond with:
{
  "thought": "Your response",
  "response": "Your answer to the user"
}`;
    }

    return fullSystemPrompt;
  }
}

