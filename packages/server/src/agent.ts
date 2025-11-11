import { LLMService } from "./llm.js";
import { ChatMessage, ToolCall, WebSocketMessage, ToolDefinition } from "./types.js";
import { tools, getToolByName } from "./tools/index.js";

export class Agent {
  private llm: LLMService;
  private conversationHistory: ChatMessage[] = []; // Only user and assistant messages
  private systemPrompt: string = ""; // Base system prompt - never changes
  private sendMessage: (message: WebSocketMessage) => void;
  private pendingApprovals: Map<string, { resolve: (approved: boolean) => void }> = new Map();
  private maxLoopIterations: number = 10;
  private currentLoopCount: number = 0;

  constructor(sendMessage: (message: WebSocketMessage) => void, llm: LLMService) {
    this.sendMessage = sendMessage;
    this.llm = llm;
    this.initializeSystemPrompt();
  }

  private initializeSystemPrompt(): void {
    // This is the foundational instruction that never changes
    // It's separated from conversation history for efficient KV caching
    this.systemPrompt = `You are Azul, an AI coding assistant running locally. You help users with coding tasks by analyzing files, executing commands, and providing solutions.

You have access to tools that let you interact with the filesystem and execute shell commands. Use these tools to help the user effectively.

When responding, think step by step:
1. Understand what the user is asking
2. Determine which tools (if any) you need to use
3. Execute the tools
4. Provide a helpful response

Always be concise and helpful. Format code blocks with proper syntax highlighting.`;
  }


  async handleUserMessage(content: string): Promise<void> {
    // Handle reset command
    if (content.toLowerCase().trim() === "reset") {
      this.reset();
      this.sendMessage({
        type: "agent_response",
        content: "Memory reset. Conversation history cleared.",
      });
      return;
    }

    // Handle exit command
    if (content.toLowerCase().trim() === "exit" || content.toLowerCase().trim() === "quit") {
      this.sendMessage({
        type: "agent_response",
        content: "Goodbye! Exiting...",
      });
      return;
    }

    // Reset loop counter for new message
    this.currentLoopCount = 0;

    // Add user message to history
    this.conversationHistory.push({
      role: "user",
      content,
    });

    this.sendMessage({
      type: "user_message_received",
      content,
    });

    // Start the agent loop
    await this.runAgentLoop();
  }

  reset(): void {
    // Clear conversation history only - system prompt remains unchanged
    // This leverages KV caching: system prompt is cached, only new history is processed
    this.conversationHistory = [];
    this.llm.resetTokenStats();
    this.currentLoopCount = 0;
    
    // Cancel any pending approvals
    this.pendingApprovals.forEach((pending) => {
      pending.resolve(false);
    });
    this.pendingApprovals.clear();
  }

  private async runAgentLoop(): Promise<void> {
    // Prevent infinite loops
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
      // Send thinking state
      this.sendMessage({
        type: "agent_thinking",
        content: "Thinking...",
      });

      // Get completion from LLM
      // Pass system prompt separately from conversation history for efficient KV caching
      const { response, stats } = await this.llm.getCompletion(
        this.systemPrompt,
        this.conversationHistory,
        tools
      );

      // Send token statistics
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

      // Parse the response
      const parsedResponse = this.parseResponse(response);

      if (parsedResponse.thought) {
        this.sendMessage({
          type: "agent_thought",
          content: parsedResponse.thought,
        });
      }

      // If there are tool calls, execute them
      if (parsedResponse.tool_calls && parsedResponse.tool_calls.length > 0) {
        await this.executeToolCalls(parsedResponse.tool_calls);
        
        // After executing tools, run the loop again to get final response
        await this.runAgentLoop();
      } else if (parsedResponse.response) {
        // Send final response
        this.sendMessage({
          type: "agent_response",
          content: parsedResponse.response,
        });

        // Add assistant response to history
        this.conversationHistory.push({
          role: "assistant",
          content: parsedResponse.response,
        });
      } else {
        // If no response or tool calls, treat the raw response as the answer
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
      // Try to find JSON in the response
      const jsonMatch = response.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const parsed = JSON.parse(jsonMatch[0]);
        return parsed;
      }
    } catch (error) {
      // If parsing fails, treat the whole response as a text response
    }

    // If no JSON found or parsing failed, return as plain response
    return { response };
  }

  private async executeToolCalls(toolCalls: ToolCall[]): Promise<void> {
    for (const toolCall of toolCalls) {
      const tool = getToolByName(toolCall.name);
      
      if (!tool) {
        this.sendMessage({
          type: "error",
          message: `Unknown tool: ${toolCall.name}`,
        });
        continue;
      }

      // Send tool call notification
      this.sendMessage({
        type: "tool_call",
        tool: toolCall.name,
        args: toolCall.arguments,
      });

      // Check if approval is required
      if (tool.requiresApproval) {
        const approved = await this.requestApproval(toolCall.name, toolCall.arguments);
        
        if (!approved) {
          this.sendMessage({
            type: "tool_result",
            tool: toolCall.name,
            result: { success: false, error: "User denied approval" },
          });
          
          // Add to conversation history
          this.conversationHistory.push({
            role: "assistant",
            content: `Tool ${toolCall.name} was denied by the user.`,
          });
          continue;
        }
      }

      // Execute the tool
      try {
        const result = await tool.execute(toolCall.arguments);
        
        this.sendMessage({
          type: "tool_result",
          tool: toolCall.name,
          result,
        });

        // Add to conversation history
        this.conversationHistory.push({
          role: "assistant",
          content: `Executed ${toolCall.name} with result: ${JSON.stringify(result)}`,
        });
      } catch (error: any) {
        this.sendMessage({
          type: "tool_result",
          tool: toolCall.name,
          result: { success: false, error: error.message },
        });

        this.conversationHistory.push({
          role: "assistant",
          content: `Error executing ${toolCall.name}: ${error.message}`,
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

      // Set a timeout for approval
      setTimeout(() => {
        if (this.pendingApprovals.has(requestId)) {
          this.pendingApprovals.delete(requestId);
          resolve(false);
        }
      }, 60000); // 60 second timeout
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

