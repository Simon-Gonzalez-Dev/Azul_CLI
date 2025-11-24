import * as path from "path";
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
  private workingDirectory: string;

  constructor(sendMessage: MessageCallback, llm: ILLMService, workingDirectory?: string) {
    this.sendMessage = sendMessage;
    this.llm = llm;
    this.workingDirectory = workingDirectory || process.cwd();
    this.initializeSystemPrompt();
  }

  setLLM(llm: ILLMService): void {
    this.llm = llm;
  }

  setWorkingDirectory(dir: string): void {
    this.workingDirectory = dir;
  }

  getWorkingDirectory(): string {
    return this.workingDirectory;
  }

  private initializeSystemPrompt(): void {
    this.systemPrompt = `You are Azul, an elite autonomous coding agent with direct CLI and Filesystem access. 
Your goal is to complete programming tasks efficiently, accurately, and with minimal token usage.

# CORE OPERATING RULES

1. **ACTION OVER CHATTER**: 
   - Do NOT describe code changes in the chat before making them. 
   - Do NOT output "Here is the code:" followed by a block of code if you intend to use a tool to write it immediately after. 
   - **JUST CALL THE TOOL.**

2. **EXPLORE FIRST**: 
   - Never guess file paths or contents. 
   - Always start by mapping the territory using *ls* (list_dir) and *read_file*. 
   - If a file doesn't exist, verify the directory structure before creating it.

3. **SURGICAL EDITING (The "Patch" Protocol)**:
   - **PREFER *edit_file* (Search & Replace) over *write_file***.
   - *write_file* overwrites the ENTIRE file. Only use it for creating new files or very small files (<50 lines).
   - For existing files, locate the unique block of code you want to change and provide a replacement.
   - The *search* block must be sufficient to be unique, but minimal enough to save tokens.

4. **VERIFICATION**:
   - After editing code, you are encouraged to run linter checks, build commands, or tests via *run_shell* to verify your changes worked.
   - If a tool fails, read the error, analyze the cause, and self-correct.

# TOOL USAGE GUIDELINES

You have access to a suite of native tools. You must use them to interact with the environment.

## 1. *ls* (List Files)
   - Use this frequently to understand the directory structure.
   - Don't assume standard paths (e.g., *src/* vs *app/*). Check first.

## 2. *read_file*
   - Read file contents to understand logic.
   - For massive files, read relevant chunks if possible, or read the whole file if you need full context.

## 3. *edit_file* (Search & Replace)
   - **Input:** *path*, *search_block*, *replace_block*.
   - **Constraint:** The *search_block* must match the file content EXACTLY (including whitespace).
   - **Strategy:** Copy-paste the *search_block* from a previous *read_file* output to ensure exact matching.

## 4. *run_shell*
   - Execute shell commands (git, npm, python, etc.).
   - NOTE: You cannot use interactive tools like *nano*, *vim*, or *npm init* that require keyboard input.
   - Use *grep* or *find* for large scale searches instead of reading every file.

# RESPONSE FORMATTING

- **When Thinking:** If you need to plan, you may output a short "Thought" before a tool call, but keep it brief (1-2 sentences).
- **When Acting:** Issue the Tool Call immediately.
- **When Finished:** Only address the User when the task is complete or you need clarification. `;
  }

  async handleUserMessage(content: string): Promise<void> {
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
      const STREAM_MIN_CHARS = 32;
      const STREAM_INTERVAL_MS = 80;
      let lastStreamLength = 0;
      let lastStreamTime = 0;

      const flushStream = (content: string) => {
        this.streamingResponse = content;
        lastStreamLength = content.length;
        lastStreamTime = Date.now();
        this.sendMessage({
          type: "agent_response_stream",
          content,
        });
      };

      const { response, toolCalls, stats } = await this.llm.getCompletion(
        this.systemPrompt,
        this.conversationHistory,
        tools,
        (accumulatedText: string) => {
          if (isFirstToken) {
            isFirstToken = false;
            this.sendMessage({
              type: "agent_thinking",
              content: "",
            });
          }
          
          if (accumulatedText && accumulatedText.length > lastStreamLength) {
            const now = Date.now();
            const sizeDelta = accumulatedText.length - lastStreamLength;
            const timeDelta = now - lastStreamTime;

            if (sizeDelta >= STREAM_MIN_CHARS || timeDelta >= STREAM_INTERVAL_MS) {
              flushStream(accumulatedText);
            }
          }
        }
      );

      // Ensure the final streamed content is flushed
      if (response && response.length > lastStreamLength) {
        flushStream(response);
      }

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

      // Handle native tool calls (from Groq API)
      if (toolCalls && toolCalls.length > 0) {
        // Add assistant message with tool calls to history
        this.conversationHistory.push({
          role: "assistant",
          content: response || null, // Can be null when only tool calls are present
          tool_calls: toolCalls,
        });

        // Execute tools silently
        await this.executeToolCalls(toolCalls);
        
        // Loop continues automatically with tool results
        await this.runAgentLoop();
        return;
      }

      // Handle text response (no tools)
      if (response) {
        this.sendMessage({
          type: "agent_response",
          content: response,
        });

        this.conversationHistory.push({
          role: "assistant",
          content: response,
        });
      } else {
        // Fallback: try parsing JSON response (for local LLM that doesn't support native tools)
        const parsedResponse = this.parseResponse(this.streamingResponse || response);
        
        if (parsedResponse.tool_calls && parsedResponse.tool_calls.length > 0) {
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
          // Fallback to raw response
          const finalResponse = this.streamingResponse || response || "I'm ready to help.";
          this.sendMessage({
            type: "agent_response",
            content: finalResponse,
          });
          this.conversationHistory.push({
            role: "assistant",
            content: finalResponse,
          });
        }
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
        
        this.conversationHistory.push({
          role: "tool",
          content: JSON.stringify({ success: false, error: `Unknown tool: ${toolCall.name}` }),
          tool_call_id: toolCallId,
        });
        continue;
      }

      // Resolve paths relative to working directory for file operations
      const resolvedArgs = { ...toolCall.arguments };
      if (toolCall.name === "read_file" || toolCall.name === "write_file" || toolCall.name === "edit_file" || toolCall.name === "list_dir") {
        if (resolvedArgs.path && !path.isAbsolute(resolvedArgs.path)) {
          resolvedArgs.path = path.resolve(this.workingDirectory, resolvedArgs.path);
        }
      }

      // Show status instead of full tool details (Silent Actor pattern)
      this.sendMessage({
        type: "tool_call",
        tool: toolCall.name,
        args: { status: `Running ${toolCall.name}...` }, // Don't show full args
      });

      if (tool.requiresApproval) {
        const approved = await this.requestApproval(toolCall.name, resolvedArgs);
        
        if (!approved) {
          const result = { success: false, error: "User denied approval" };
          this.sendMessage({
            type: "tool_result",
            tool: toolCall.name,
            result: { success: false, message: "User denied approval" }, // Minimal result
          });
          
          this.conversationHistory.push({
            role: "tool",
            content: JSON.stringify(result),
            tool_call_id: toolCallId,
          });
          continue;
        }
      }

      try {
        const result = await tool.execute(resolvedArgs);
        
        // Show minimal result (Silent Actor pattern)
        this.sendMessage({
          type: "tool_result",
          tool: toolCall.name,
          result: {
            success: result.success,
            message: result.message || (result.success ? "Completed successfully" : result.error),
            // Only show diff for file operations, not full content
            diff: result.diff,
            added: result.added,
            removed: result.removed,
            filePath: result.filePath,
          },
        });

        // Add full tool result to history for LLM context
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
          result: { success: false, message: error.message },
        });

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
