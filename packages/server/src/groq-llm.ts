import Groq from "groq-sdk";
import { ChatMessage, ToolDefinition, TokenStats, ToolCall } from "./types.js";
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

  // Convert ToolDefinition[] to Groq's native tools format
  private convertToolsToGroqFormat(tools?: ToolDefinition[]): any[] | undefined {
    if (!tools || tools.length === 0) {
      return undefined;
    }

    return tools.map(tool => ({
      type: 'function' as const,
      function: {
        name: tool.name,
        description: tool.description,
        parameters: tool.parameters,
      },
    }));
  }

  // Convert Groq's tool_calls to our ToolCall format
  private convertGroqToolCalls(groqToolCalls: any[]): ToolCall[] {
    return groqToolCalls.map(tc => ({
      id: tc.id,
      name: tc.function.name,
      arguments: JSON.parse(tc.function.arguments || '{}'),
    }));
  }

  // Convert ChatMessage[] to Groq's message format
  private convertMessagesToGroqFormat(messages: ChatMessage[]): any[] {
    return messages.map(msg => {
      if (msg.role === 'tool') {
        // Groq uses 'tool' role with tool_call_id
        return {
          role: 'tool' as const,
          content: msg.content,
          tool_call_id: msg.tool_call_id,
        };
      } else if (msg.role === 'assistant' && msg.tool_calls) {
        // Assistant message with tool calls
        return {
          role: 'assistant' as const,
          content: msg.content || null,
          tool_calls: msg.tool_calls.map(tc => ({
            id: tc.id || `call_${Math.random().toString(36).substring(2, 15)}`,
            type: 'function' as const,
            function: {
              name: tc.name,
              arguments: JSON.stringify(tc.arguments),
            },
          })),
        };
      } else {
        // Regular user or assistant message
        return {
          role: msg.role,
          content: msg.content,
        };
      }
    });
  }

  async getCompletion(
    systemPrompt: string,
    conversationHistory: ChatMessage[],
    tools?: ToolDefinition[],
    onToken?: (token: string) => void
  ): Promise<{ response: string; toolCalls?: ToolCall[]; stats: TokenStats }> {
    const startTime = Date.now();

    // Build messages array for Groq API
    const messages: any[] = [
      { role: "system", content: systemPrompt },
      ...this.convertMessagesToGroqFormat(conversationHistory),
    ];

    // Convert tools to Groq format
    const groqTools = this.convertToolsToGroqFormat(tools);

    try {
      let content = "";
      let toolCalls: ToolCall[] | undefined = undefined;
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
          tools: groqTools,
          tool_choice: groqTools ? 'auto' : undefined,
        });

        let accumulatedContent = "";
        let accumulatedToolCalls: any[] = [];
        
        for await (const chunk of stream) {
          const delta = chunk.choices?.[0]?.delta;
          
          // Handle content delta
          if (delta?.content) {
            accumulatedContent += delta.content;
            content = accumulatedContent;
            onToken(content);
          }

          // Handle tool calls delta
          if (delta?.tool_calls) {
            for (const toolCallDelta of delta.tool_calls) {
              const index = toolCallDelta.index || 0;
              if (!accumulatedToolCalls[index]) {
                accumulatedToolCalls[index] = {
                  id: toolCallDelta.id || '',
                  type: 'function',
                  function: { name: '', arguments: '' },
                };
              }
              if (toolCallDelta.id) {
                accumulatedToolCalls[index].id = toolCallDelta.id;
              }
              if (toolCallDelta.function?.name) {
                accumulatedToolCalls[index].function.name = toolCallDelta.function.name;
              }
              if (toolCallDelta.function?.arguments) {
                accumulatedToolCalls[index].function.arguments += toolCallDelta.function.arguments;
              }
            }
          }

          // Extract usage stats if available (usually in last chunk)
          // Note: Groq streaming chunks don't include usage stats
        }

        // Convert accumulated tool calls
        if (accumulatedToolCalls.length > 0) {
          toolCalls = this.convertGroqToolCalls(accumulatedToolCalls);
        }
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
          tools: groqTools,
          tool_choice: groqTools ? 'auto' : undefined,
        });

        const choice = data.choices?.[0];
        content = choice?.message?.content || "";

        // Extract tool calls if present
        if (choice?.message?.tool_calls && choice.message.tool_calls.length > 0) {
          toolCalls = this.convertGroqToolCalls(choice.message.tool_calls);
        }

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

      return { response: content, toolCalls, stats };
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
}
