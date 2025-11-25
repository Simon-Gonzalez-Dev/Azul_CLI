import { ChatMessage, ToolDefinition, TokenStats, ToolCall } from "../types.js";
import { ILLMService } from "../llm-interface.js";

export interface ProviderInfo {
  provider: string;
  model: string;
}

export abstract class BaseLLMProvider implements ILLMService {
  protected totalInputTokens: number = 0;
  protected totalOutputTokens: number = 0;
  
  abstract initialize(config: any): Promise<void>;
  abstract cleanup(): Promise<void>;
  abstract getProviderInfo(): ProviderInfo;
  
  // Abstract method for the specific provider implementation
  protected abstract generateCompletion(
    messages: ChatMessage[],
    onToken?: (token: string) => void
  ): Promise<{ response: string; inputTokens: number; outputTokens: number }>;

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
  }

  protected formatToolResult(content: string | null, toolCallId?: string): string {
    const label = toolCallId ? `Tool Result (${toolCallId})` : "Tool Result";
    return `${label}: ${content ?? ""}`;
  }

  protected formatToolCallsAsXml(toolCalls: ToolCall[]): string {
    return toolCalls.map(call => {
      let argsXml = "";
      if (call.arguments) {
        for (const [key, value] of Object.entries(call.arguments)) {
          argsXml += `<${key}>${value}</${key}>\n`;
        }
      }
      return `<tool_code>\n<tool_name>${call.name}</tool_name>\n<parameters>\n${argsXml}</parameters>\n</tool_code>`;
    }).join("\n\n");
  }

  protected mapToOpenAIChatMessages(messages: ChatMessage[]): { role: "system" | "user" | "assistant"; content: string }[] {
    return messages.map((msg) => {
      if (msg.role === "tool") {
        return {
          role: "user",
          content: this.formatToolResult(msg.content, msg.tool_call_id),
        };
      }

      if (msg.role === "assistant" && msg.tool_calls && msg.tool_calls.length > 0) {
        const xmlCalls = this.formatToolCallsAsXml(msg.tool_calls);
        const baseContent = msg.content ? `${msg.content}\n\n` : "";
        return {
          role: "assistant",
          content: `${baseContent}${xmlCalls}`.trim(),
        };
      }

      return {
        role: msg.role as "system" | "user" | "assistant",
        content: msg.content ?? "",
      };
    });
  }

  protected formatConversationAsPlaintext(messages: ChatMessage[]): string {
    let output = "";

    for (const msg of messages) {
      if (msg.role === "system") {
        output += `${msg.content ?? ""}\n\n`;
      } else if (msg.role === "user") {
        output += `User: ${msg.content ?? ""}\n\n`;
      } else if (msg.role === "assistant") {
        if (msg.tool_calls && msg.tool_calls.length > 0) {
          output += `Assistant: ${msg.content ?? "I'll use tools to help."}\n`;
          output += `${this.formatToolCallsAsXml(msg.tool_calls)}\n\n`;
        } else {
          output += `Assistant: ${msg.content ?? ""}\n\n`;
        }
      } else if (msg.role === "tool") {
        output += `${this.formatToolResult(msg.content, msg.tool_call_id)}\n\n`;
      }
    }

    output += "Assistant:";
    return output;
  }

  protected estimateTokensFromText(text: string): number {
    if (!text) return 0;
    return Math.max(1, Math.round(text.length / 4));
  }

  async getCompletion(
    systemPrompt: string,
    conversationHistory: ChatMessage[],
    tools?: ToolDefinition[],
    onToken?: (token: string) => void
  ): Promise<{ response: string; toolCalls?: ToolCall[]; stats: TokenStats }> {
    const startTime = Date.now();

    // Unified Prompt Construction
    // This ensures ALL providers see exactly the same prompt structure
    let fullSystemPrompt = systemPrompt;

    if (tools && tools.length > 0) {
      fullSystemPrompt += "\n\nYou have access to the following tools:\n\n";
      tools.forEach(tool => {
        fullSystemPrompt += `### ${tool.name}\n`;
        fullSystemPrompt += `Description: ${tool.description}\n`;
        fullSystemPrompt += `Parameters: ${JSON.stringify(tool.parameters, null, 2)}\n\n`;
      });

      // Standardized XML tool call format for ALL providers
      fullSystemPrompt += `\nTo use a tool, you MUST use the following XML format.
ALL of your reasoning must be contained within <thought> tags.
ALL tool calls must be contained within <tool_code> tags.

Format:
<thought>
Explain your reasoning here...
</thought>
<tool_code>
<tool_name>tool_name</tool_name>
<parameters>
<param_name>param_value</param_name>
<another_param>
multi-line
value
</another_param>
</parameters>
</tool_code>

IMPORTANT:
- You MUST use valid XML tags.
- Do NOT use markdown code blocks for the XML.
- Text outside <thought> or <tool_code> tags will be ignored.
- For tool parameters that contain code, just put the code directly inside the tag. No need to escape quotes.
`;
    }

    // Combine system prompt with history
    // We create a new array to avoid mutating the original
    const messages: ChatMessage[] = [
      { role: "system", content: fullSystemPrompt },
      ...conversationHistory
    ];

    try {
      const result = await this.generateCompletion(messages, onToken);
      
      // Update stats
      this.totalInputTokens += result.inputTokens;
      this.totalOutputTokens += result.outputTokens;

      const endTime = Date.now();
      const generationTimeMs = endTime - startTime;
      const tokensPerSecond = result.outputTokens > 0 && generationTimeMs > 0
        ? result.outputTokens / (generationTimeMs / 1000)
        : 0;

      const stats: TokenStats = {
        inputTokens: result.inputTokens,
        outputTokens: result.outputTokens,
        totalTokens: result.inputTokens + result.outputTokens,
        tokensPerSecond,
        generationTimeMs,
      };

      // We do NOT use native tool calls. The Agent's parser handles the text response.
      return { response: result.response, toolCalls: undefined, stats };

    } catch (error) {
      console.error("Provider generation error:", error);
      throw error;
    }
  }
}

