import { ILLMService } from "./llm-interface.js";
import { ChatMessage, ToolCall, ToolDefinition } from "./types.js";
import { tools, getToolByName } from "./tools/index.js";

export type MessageCallback = (message: {
  type: string;
  [key: string]: any;
}) => void;

export class Agent {
  private llm: ILLMService;
  private conversationHistory: ChatMessage[] = [];
  private systemPrompt: string = "";
  private sendMessage: MessageCallback;
  private pendingApprovals: Map<string, { resolve: (approved: boolean) => void }> = new Map();
  private maxLoopIterations: number = 10;
  private currentLoopCount: number = 0;
  private streamingResponse: string = "";

  constructor(sendMessage: MessageCallback, llm: ILLMService) {
    this.sendMessage = sendMessage;
    this.llm = llm;
    this.initializeSystemPrompt();
  }

  setLLM(llm: ILLMService): void {
    this.llm = llm;
  }

  private initializeSystemPrompt(): void {
    this.systemPrompt = `You are Azul, an AI coding assistant running locally. You help users with coding tasks by analyzing files, executing commands, and providing solutions.

You have access to tools that let you interact with the filesystem and execute shell commands. Use these tools to help the user effectively.

CRITICAL - File Operations:
- When the user asks you to create, update, or modify a file, you MUST use the write_file tool
- Do NOT just show the code in your response - actually write it to the file using the tool
- After writing a file, the tool will show you a diff of changes
- Always use the write_file tool when generating or updating code files

IMPORTANT - Tool Usage Pattern:
1. When you need to use a tool, respond with a JSON object containing "tool_calls" array
2. After you make a tool call, you will receive a "Tool Result" message showing the outcome
3. Read the tool result carefully - if it shows success, your task may be complete
4. If the tool result shows success, provide a final response to the user explaining what was done
5. Only make additional tool calls if the previous ones failed or if more work is needed

When responding, think step by step:
1. Understand what the user is asking
2. Determine which tools (if any) you need to use
3. Execute the tools (especially write_file for code changes!)
4. Review the tool results
5. Provide a helpful final response to the user

Always be concise and helpful. Format code blocks with proper syntax highlighting.`;
  }

  async handleUserMessage(content: string): Promise<void> {
    // All commands are handled in the UI layer - this only processes regular user messages
    this.currentLoopCount = 0;
    this.conversationHistory.push({
      role: "user",
      content,
    });

    this.sendMessage({
      type: "user_message_received",
      content,
    });

    await this.runAgentLoop();
  }

  reset(): void {
    this.conversationHistory = [];
    this.llm.resetTokenStats();
    this.currentLoopCount = 0;
    
    this.pendingApprovals.forEach((pending) => {
      pending.resolve(false);
    });
    this.pendingApprovals.clear();
  }

  private async runAgentLoop(): Promise<void> {
    if (this.currentLoopCount >= this.maxLoopIterations) {
      this.sendMessage({
        type: "error",
        message: "Maximum loop iterations reached. Stopping to prevent infinite loop.",
      });
      this.sendMessage({
        type: "agent_response",
        content: "I've reached the maximum number of iterations. Please rephrase your request or try a different approach.",
      });
      return;
    }

    this.currentLoopCount++;

    try {
      this.sendMessage({
        type: "agent_thinking",
        content: "Thinking...",
      });

      this.streamingResponse = "";
      let isFirstToken = true;

      const { response, stats } = await this.llm.getCompletion(
        this.systemPrompt,
        this.conversationHistory,
        tools,
        (token: string) => {
          // Stream tokens for faster time-to-first-token
          if (isFirstToken) {
            isFirstToken = false;
            // Clear thinking message when first token arrives
            this.sendMessage({
              type: "agent_thinking",
              content: "",
            });
          }
          this.streamingResponse += token;
          this.sendMessage({
            type: "agent_response_stream",
            content: this.streamingResponse,
          });
        }
      );

      const totalStats = this.llm.getTokenStats();
      this.sendMessage({
        type: "token_stats",
        stats: {
          ...stats,
          cumulativeInputTokens: totalStats.inputTokens,
          cumulativeOutputTokens: totalStats.outputTokens,
          cumulativeTotalTokens: totalStats.totalTokens,
          totalInputTokens: totalStats.inputTokens,
          totalOutputTokens: totalStats.outputTokens,
        },
      });

      const parsedResponse = this.parseResponse(response);

      if (parsedResponse.thought) {
        this.sendMessage({
          type: "agent_thought",
          content: parsedResponse.thought,
        });
      }

      if (parsedResponse.tool_calls && parsedResponse.tool_calls.length > 0) {
        // Add assistant's tool call decision to history
        this.conversationHistory.push({
          role: "assistant",
          content: parsedResponse.thought || "I'll use tools to complete this task.",
          tool_calls: parsedResponse.tool_calls,
        });
        
        await this.executeToolCalls(parsedResponse.tool_calls);
        await this.runAgentLoop();
      } else if (parsedResponse.response) {
        this.sendMessage({
          type: "agent_response",
          content: parsedResponse.response,
        });

        this.conversationHistory.push({
          role: "assistant",
          content: parsedResponse.response,
        });
      } else {
        this.sendMessage({
          type: "agent_response",
          content: response,
        });
        this.conversationHistory.push({
          role: "assistant",
          content: response,
        });
      }
    } catch (error: any) {
      console.error("Error in agent loop:", error);
      this.sendMessage({
        type: "error",
        message: error.message || "An error occurred",
      });
    }
  }

  private parseResponse(response: string): {
    thought?: string;
    tool_calls?: ToolCall[];
    response?: string;
  } {
    try {
      const jsonMatch = response.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0]);
        return parsed;
      }
    } catch (error) {
      // If parsing fails, treat the whole response as a text response
    }

    return { response };
  }

  private async executeToolCalls(toolCalls: ToolCall[]): Promise<void> {
    for (const toolCall of toolCalls) {
      const tool = getToolByName(toolCall.name);
      
      // Generate unique ID for tool call if not provided
      const toolCallId = toolCall.id || `call_${Math.random().toString(36).substring(2, 15)}`;
      
      if (!tool) {
        this.sendMessage({
          type: "error",
          message: `Unknown tool: ${toolCall.name}`,
        });
        
        // Add error result to history as tool message
        this.conversationHistory.push({
          role: "tool",
          content: JSON.stringify({ success: false, error: `Unknown tool: ${toolCall.name}` }),
          tool_call_id: toolCallId,
        });
        continue;
      }

      this.sendMessage({
        type: "tool_call",
        tool: toolCall.name,
        args: toolCall.arguments,
      });

      if (tool.requiresApproval) {
        const approved = await this.requestApproval(toolCall.name, toolCall.arguments);
        
        if (!approved) {
          const result = { success: false, error: "User denied approval" };
          this.sendMessage({
            type: "tool_result",
            tool: toolCall.name,
            result,
          });
          
          // Add denial result to history as tool message
          this.conversationHistory.push({
            role: "tool",
            content: JSON.stringify(result),
            tool_call_id: toolCallId,
          });
          continue;
        }
      }

      try {
        const result = await tool.execute(toolCall.arguments);
        
        this.sendMessage({
          type: "tool_result",
          tool: toolCall.name,
          result,
        });

        // Add tool result to history with "tool" role - this is critical for the loop!
        this.conversationHistory.push({
          role: "tool",
          content: JSON.stringify(result),
          tool_call_id: toolCallId,
        });
      } catch (error: any) {
        const result = { success: false, error: error.message };
        this.sendMessage({
          type: "tool_result",
          tool: toolCall.name,
          result,
        });

        // Add error result to history as tool message
        this.conversationHistory.push({
          role: "tool",
          content: JSON.stringify(result),
          tool_call_id: toolCallId,
        });
      }
    }
  }

  private async requestApproval(toolName: string, args: any): Promise<boolean> {
    const requestId = Math.random().toString(36).substring(7);
    
    return new Promise((resolve) => {
      this.pendingApprovals.set(requestId, { resolve });
      
      this.sendMessage({
        type: "approval_request",
        requestId,
        tool: toolName,
        args,
      });

      setTimeout(() => {
        if (this.pendingApprovals.has(requestId)) {
          this.pendingApprovals.delete(requestId);
          resolve(false);
        }
      }, 60000);
    });
  }

  handleApproval(requestId: string, approved: boolean): void {
    const pending = this.pendingApprovals.get(requestId);
    if (pending) {
      pending.resolve(approved);
      this.pendingApprovals.delete(requestId);
    }
  }
}
