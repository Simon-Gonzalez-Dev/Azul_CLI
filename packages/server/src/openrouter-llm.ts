import { ChatMessage, ToolDefinition, TokenStats } from "./types.js";
import { ILLMService } from "./llm-interface.js";

export class OpenRouterLLMService implements ILLMService {
  private apiKey: string;
  private model: string = "qwen/qwen-2.5-coder-32b-instruct:free";
  private totalInputTokens: number = 0;
  private totalOutputTokens: number = 0;
  private chatHistory: ChatMessage[] = [];

  constructor(apiKey: string, model?: string) {
    this.apiKey = apiKey;
    if (model) {
      this.model = model;
    }
  }

  async initialize(config: any): Promise<void> {
    // No initialization needed for API
    console.log(`  OpenRouter API initialized (model: ${this.model})`);
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

    // Build messages array for OpenRouter API
    const messages: any[] = [
      { role: "system", content: this.buildSystemPrompt(systemPrompt, tools) }
    ];

    // Add conversation history
    for (const msg of conversationHistory) {
      if (msg.role === "tool") {
        // OpenRouter uses different format for tool responses
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
      const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${this.apiKey}`,
          "Content-Type": "application/json",
          "HTTP-Referer": "https://github.com/azul-cli",
          "X-Title": "Azul CLI"
        },
        body: JSON.stringify({
          model: this.model,
          messages: messages,
          temperature: 0.7,
          max_tokens: 2048
        })
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`OpenRouter API error: ${response.status} - ${errorText}`);
      }

      const data: any = await response.json();
      const content = data.choices[0]?.message?.content || "";

      // Update token stats if available
      if (data.usage) {
        this.totalInputTokens += data.usage.prompt_tokens || 0;
        this.totalOutputTokens += data.usage.completion_tokens || 0;
      }

      // Call onToken if provided (for streaming effect)
      if (onToken && content) {
        onToken(content);
      }

      const endTime = Date.now();
      const generationTimeMs = endTime - startTime;
      const outputTokens = data.usage?.completion_tokens || 0;
      const tokensPerSecond = outputTokens > 0 && generationTimeMs > 0
        ? outputTokens / (generationTimeMs / 1000)
        : 0;

      const stats: TokenStats = {
        inputTokens: data.usage?.prompt_tokens || 0,
        outputTokens: data.usage?.completion_tokens || 0,
        totalTokens: data.usage?.total_tokens || 0,
        tokensPerSecond: tokensPerSecond,
        generationTimeMs: generationTimeMs,
      };

      return { response: content, stats };
    } catch (error) {
      console.error("Error calling OpenRouter API:", error);
      throw error;
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

