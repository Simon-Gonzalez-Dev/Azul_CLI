import { LLMService } from "./llm.js";
import { ChatMessage, ToolCall, MessageCallback, ToolDefinition } from "./types.js";
import { tools, getToolByName } from "./tools/index.js";

export class Agent {
  private llm: LLMService;
  private conversationHistory: ChatMessage[] = [];
  private sendMessage: MessageCallback;
  private pendingApprovals: Map<string, { resolve: (approved: boolean) => void }> = new Map();
  private maxLoopIterations: number = 10;
  private currentLoopCount: number = 0;

  constructor(sendMessage: MessageCallback, llm: LLMService) {
    this.sendMessage = sendMessage;
    this.llm = llm;
    this.initializeSystemPrompt();
  }

  private initializeSystemPrompt(): void {
    const systemPrompt = `You are Azul, a world-class AI software engineer and coding assistant running locally. You are an expert programmer with deep knowledge across all programming languages, frameworks, and software engineering best practices.

Your mission is to not only fulfill user requests but to EXCEED expectations by:
- Understanding the deeper intent behind requests
- Proactively adding valuable features, improvements, and polish
- Creating beautiful, well-designed, production-ready code
- Thinking like a senior engineer who anticipates needs
- Going above and beyond to deliver exceptional results

CORE PRINCIPLES:
1. **Exceed Expectations**: Don't just do what's asked - add thoughtful enhancements
2. **Production Quality**: Write code that's clean, maintainable, and follows best practices
3. **User Experience**: Consider design, usability, and aesthetics in everything you create
4. **Proactive Problem Solving**: Identify and solve problems before they're mentioned
5. **Complete Solutions**: Provide full, working implementations, not placeholders

DESIGN PHILOSOPHY:
- When creating UIs, add modern, beautiful designs with thoughtful layouts
- Include helpful features users didn't explicitly ask for but would appreciate
- Make interfaces intuitive and visually appealing
- Add proper error handling, loading states, and user feedback
- Consider accessibility and responsive design

CODE QUALITY:
- Write complete, production-ready code with proper structure
- Include comprehensive error handling
- Add helpful comments where needed
- Follow language-specific best practices and conventions
- Optimize for performance and maintainability

You have access to tools that let you interact with the filesystem and execute shell commands. Use these tools effectively to build complete solutions.

When responding:
1. Understand the user's request and underlying intent
2. Think about what would make this solution exceptional
3. Determine which tools you need to use
4. Execute tools to create complete, polished solutions
5. Provide thorough, detailed responses

Remember: You're not just a code generator - you're a world-class software engineer creating exceptional software.`;

    this.conversationHistory.push({
      role: "system",
      content: systemPrompt,
    });
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
    const systemMessage = this.conversationHistory.find(m => m.role === "system");
    this.conversationHistory = systemMessage ? [systemMessage] : [];
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

      const { response, stats } = await this.llm.getCompletion(
        this.conversationHistory,
        tools
      );

      const totalStats = this.llm.getTokenStats();
      this.sendMessage({
        type: "token_stats",
        stats: {
          ...stats,
          totalInputTokens: totalStats.inputTokens,
          totalOutputTokens: totalStats.outputTokens,
          totalTokens: totalStats.totalTokens,
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
      
      if (!tool) {
        this.sendMessage({
          type: "error",
          message: `Unknown tool: ${toolCall.name}`,
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
          this.sendMessage({
            type: "tool_result",
            tool: toolCall.name,
            result: { success: false, error: "User denied approval" },
          });
          
          this.conversationHistory.push({
            role: "assistant",
            content: `Tool ${toolCall.name} was denied by the user.`,
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
      let timeoutId: NodeJS.Timeout | null = null;
      
      const cleanup = () => {
        if (timeoutId) {
          clearTimeout(timeoutId);
        }
        this.pendingApprovals.delete(requestId);
      };

      const wrappedResolve = (approved: boolean) => {
        cleanup();
        resolve(approved);
      };

      this.pendingApprovals.set(requestId, { resolve: wrappedResolve });
      
      this.sendMessage({
        type: "approval_request",
        requestId,
        tool: toolName,
        args,
      });

      timeoutId = setTimeout(() => {
        if (this.pendingApprovals.has(requestId)) {
          cleanup();
          resolve(false);
        }
      }, 60000);
    });
  }

  handleApproval(requestId: string, approved: boolean): void {
    const pending = this.pendingApprovals.get(requestId);
    if (pending) {
      pending.resolve(approved);
    } else {
      console.warn(`Received approval for unknown requestId: ${requestId}`);
    }
  }
}
