import * as fs from "fs/promises";
import { ILLMService } from "./llm-interface.js";
import { ChatMessage, ToolCall, ToolDefinition } from "./types.js";
import { tools, getToolByName } from "./tools/index.js";
import { computeDiff } from "./tools/filesystem.js";

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
    this.systemPrompt = `# ROLE: Azul - Autonomous Coding Agent

You are Azul, an elite autonomous coding agent with direct filesystem and CLI access. Your purpose is to complete programming tasks autonomously, efficiently, and accurately.

## CORE IDENTITY PRINCIPLES

**Principle 1: Autonomous Action**
- You have full access to tools. Never claim you "cannot see" or "don't have access"
- When information is missing, use tools to discover it yourself
- Only ask users for clarification when multiple valid interpretations exist

**Principle 2: Silent Execution**
- Actions speak louder than words. Execute tools instead of describing actions
- Never show code in chat that you're about to write to a file
- Avoid meta-commentary like "I will now..." or "Here's the code:"

**Principle 3: Exploration Before Assumption**
- Never guess file paths, structures, or contents
- Always verify context using list_dir and read_file before making changes
- Map the codebase territory before acting

**Principle 4: Surgical Precision**
- Prefer edit_file (search & replace) over write_file for existing files
- Use write_file only for new files or very small files (<50 lines)
- Match search blocks EXACTLY including whitespace and indentation

---

# OPERATIONAL PROTOCOLS

## Protocol A: Ambiguity Resolution

When user requests are vague (e.g., "fix the bug", "update the HTML", "refactor this"):
1. Execute list_dir with path "." to discover the codebase structure
2. Identify relevant files based on context clues
3. Read candidate files using read_file
4. Proceed with the task using discovered context
5. Only request clarification if multiple conflicting candidates exist (>3 similar files)

## Protocol B: Error Recovery

When a tool fails:
1. Read the error message carefully
2. Analyze root cause (path issues, syntax errors, missing dependencies)
3. Self-correct by fixing the issue and retrying
4. If stuck after 2 attempts, explain the blocker in <thought> tags

## Protocol C: Verification

After making code changes, run linters/formatters/build commands via execute_command and verify changes work.

---

# BEHAVIORAL CONSTRAINTS

**MUST Do:**
- Use tools to discover information yourself
- Execute actions instead of describing them
- Verify changes after making them
- Use edit_file for existing files (write_file only for new files <50 lines)
- Put all reasoning in <thought> tags
- Put all tool calls in <tool_code> tags

**MUST NOT Do:**
- Claim you don't have access (you have tools)
- Ask users for file paths when you can discover them
- Show code in chat before writing it to files
- Use write_file on existing files
- Output text outside XML tags
- Use markdown formatting
- Describe actions instead of executing them

Remember: You are an autonomous agent. Act first, explain if necessary. Tools are your superpower—use them.`;
  }

  async handleUserMessage(content: string): Promise<void> {
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
    
    this.pendingApprovals.forEach((pending) => {
      pending.resolve(false);
    });
    this.pendingApprovals.clear();
  }

  private async runAgentLoop(): Promise<void> {
    try {
      // Stream state machine
      type StreamState = "idle" | "streaming" | "complete" | "tools_executing" | "done";
      let streamState: StreamState = "idle";
      const streamId = `stream_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
      
      this.streamingResponse = "";
      let lastParsedThought = "";
      let parsedToolCalls: ToolCall[] = [];
      let lastStreamUpdate = 0;
      const STREAM_UPDATE_THROTTLE_MS = 16; // ~60fps max update rate
      
      // Real-time XML parser for streaming - enhanced to parse tool calls
      const parseStreamingContent = (content: string): { 
        thought?: string; 
        toolCalls: ToolCall[];
        rawContent: string;
      } => {
        // Extract thought tag content (even if incomplete)
        const thoughtMatch = content.match(/<thought>([\s\S]*?)(?:<\/thought>|$)/i);
        const thought = thoughtMatch ? thoughtMatch[1].trim() : undefined;
        
        // Parse complete tool_code blocks in real-time
        const toolCalls: ToolCall[] = [];
        const toolCodeRegex = /<tool_code>([\s\S]*?)<\/tool_code>/gi;
        let match;
        
        while ((match = toolCodeRegex.exec(content)) !== null) {
          const toolBlock = match[1];
          const parsed = this.parseToolBlock(toolBlock);
          if (parsed) {
            toolCalls.push(parsed);
          }
        }
        
        return { thought, toolCalls, rawContent: content };
      };

      // Unified stream handler - single message type, always active
      const handleStream = (accumulatedText: string) => {
        this.streamingResponse = accumulatedText;
        
        // Throttle updates for performance (but ensure we always get final update)
        const now = Date.now();
        const shouldUpdate = (now - lastStreamUpdate) >= STREAM_UPDATE_THROTTLE_MS;
        
        if (!shouldUpdate && streamState !== "complete") {
          return; // Skip this update, will catch up on next
        }
        
        lastStreamUpdate = now;
        streamState = "streaming";
        
        // Parse streaming content in real-time
        const parsed = parseStreamingContent(accumulatedText);
        
        // Update thought if it changed
        if (parsed.thought && parsed.thought !== lastParsedThought) {
          lastParsedThought = parsed.thought;
        }
        
        // Track new tool calls
        if (parsed.toolCalls.length > parsedToolCalls.length) {
          parsedToolCalls = parsed.toolCalls;
        }
        
        // Send unified streaming message (only if we have content to show)
        const hasContent = parsed.thought || parsed.rawContent.trim() || parsedToolCalls.length > 0;
        if (hasContent) {
          this.sendMessage({
            type: "agent_stream",
            streamId,
            state: streamState,
            thought: parsed.thought || lastParsedThought || undefined,
            content: parsed.rawContent, // Keep raw for parsing, but UI will format
            toolCalls: parsedToolCalls.length > 0 ? parsedToolCalls : undefined,
            isComplete: false,
          });
        }
      };

      const { response, toolCalls, stats } = await this.llm.getCompletion(
        this.systemPrompt,
        this.conversationHistory,
        tools,
        handleStream
      );

      // Finalize streaming - parse final content
      const finalContent = response || this.streamingResponse || "";
      streamState = "complete";
      
      const totalStats = this.llm.getTokenStats();
      const finalParsed = parseStreamingContent(finalContent);
      
      // Update parsed tool calls with final parse
      if (finalParsed.toolCalls.length > 0) {
        parsedToolCalls = finalParsed.toolCalls;
      }
      
      // Send final unified stream message with completion
      this.sendMessage({
        type: "agent_stream",
        streamId,
        state: "complete",
        thought: finalParsed.thought || lastParsedThought || undefined,
        content: finalContent,
        toolCalls: parsedToolCalls.length > 0 ? parsedToolCalls : undefined,
        isComplete: true,
        stats: {
          ...stats,
          cumulativeInputTokens: totalStats.inputTokens,
          cumulativeOutputTokens: totalStats.outputTokens,
          cumulativeTotalTokens: totalStats.totalTokens,
          totalInputTokens: totalStats.inputTokens,
          totalOutputTokens: totalStats.outputTokens,
        },
      });

      // Parse the response using XML parser (model agnostic - no native function calling)
      const parsedResponse = this.parseResponse(finalContent);

      // If parsing succeeded and we have tool calls
      if (parsedResponse.tool_calls && parsedResponse.tool_calls.length > 0) {
        streamState = "tools_executing";
        this.conversationHistory.push({
          role: "assistant",
          content: parsedResponse.thought || "I'll use tools to complete this task.",
          tool_calls: parsedResponse.tool_calls,
        });
        
        // Update stream state to show tools executing
        this.sendMessage({
          type: "agent_stream",
          streamId,
          state: "tools_executing",
          thought: parsedResponse.thought || lastParsedThought || undefined,
          content: finalContent,
          toolCalls: parsedResponse.tool_calls,
          isComplete: true,
        });
        
        await this.executeToolCalls(parsedResponse.tool_calls);
        
        // Mark as done after tools execute
        streamState = "done";
        await this.runAgentLoop();
        return;
      }
      
      // If no tool calls but we have thought, treat as final response
      if (parsedResponse.thought && (!parsedResponse.tool_calls || parsedResponse.tool_calls.length === 0)) {
          streamState = "done";
          // Stream message already sent with completion, just update conversation
          this.conversationHistory.push({
            role: "assistant",
            content: parsedResponse.thought,
          });
          return;
      }

      // If parsing failed entirely (no tags found), and we have raw text
      if (!parsedResponse.thought && !parsedResponse.tool_calls) {
         const textContent = parsedResponse.response || finalContent || "";
         let retryCount = 0;
         
         // Limit retries to prevent infinite loops
         const retryKey = "xml_parse_retry_count";
         const currentRetryCount = (this.conversationHistory[this.conversationHistory.length - 1] as any)?.[retryKey] || 0;
         
         if (currentRetryCount >= 2) {
           // Max retries reached - show error and stop
           streamState = "done";
           this.sendMessage({
             type: "error",
             message: "Failed to parse response after multiple attempts. Please check the model output format.",
           });
           return;
         }
         
         // If it looks like it TRIED to use tools but failed XML?
         if (textContent.includes("<tool_code>") || textContent.includes("<thought>")) {
             // Incomplete XML - ask model to retry with proper format
             const retryMsg: ChatMessage = {
                 role: "user",
                 content: "System: Invalid XML format detected. You must use complete <thought> and <tool_code> tags. Please retry with proper XML format."
             };
             (retryMsg as any)[retryKey] = currentRetryCount + 1;
             this.conversationHistory.push(retryMsg);
             await this.runAgentLoop();
             return;
         }

         // If there's raw text without XML tags, treat as violation of format rules
         if (textContent.trim().length > 0) {
             const retryMsg: ChatMessage = {
                 role: "user",
                 content: `System: You provided text without XML tags: "${textContent.substring(0, 100)}...". All responses must use <thought> tags for reasoning and <tool_code> tags for tool calls. Please retry with proper XML format.`
             };
             (retryMsg as any)[retryKey] = currentRetryCount + 1;
             this.conversationHistory.push(retryMsg);
             await this.runAgentLoop();
             return;
         }

         // Empty response - mark as done
         streamState = "done";
         return;
      }
      
      // Mark as done
      streamState = "done";

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
    error?: string;
  } {
    try {
      // XML Parsing Logic with robust handling of incomplete tags
      let thought: string | undefined;
      const tool_calls: ToolCall[] = [];

      // 1. Extract Thought (handle both complete and incomplete tags)
      const thoughtMatch = response.match(/<thought>([\s\S]*?)<\/thought>/i);
      if (thoughtMatch) {
        thought = thoughtMatch[1].trim();
      } else {
        // Check for incomplete thought tag (opening without closing)
        const incompleteThoughtMatch = response.match(/<thought>([\s\S]*?)$/i);
        if (incompleteThoughtMatch) {
          thought = incompleteThoughtMatch[1].trim();
        }
        // Check for incomplete thought tag (closing without opening - less common but handle it)
        const closingThoughtMatch = response.match(/^([\s\S]*?)<\/thought>/i);
        if (closingThoughtMatch && !thought) {
          thought = closingThoughtMatch[1].trim();
        }
      }

      // 2. Extract Tool Calls (handle both complete and incomplete tags)
      // First, try to find complete <tool_code>...</tool_code> blocks
      const toolCodeRegex = /<tool_code>([\s\S]*?)<\/tool_code>/gi;
      let match;
      
      while ((match = toolCodeRegex.exec(response)) !== null) {
        const toolBlock = match[1];
        const parsed = this.parseToolBlock(toolBlock);
        if (parsed) {
          tool_calls.push(parsed);
        }
      }

      // 3. Handle incomplete tool_code tags (opening without closing)
      // Check if there's a <tool_code> that doesn't have a matching </tool_code>
      const incompleteToolCodeMatch = response.match(/<tool_code>([\s\S]*?)$/i);
      if (incompleteToolCodeMatch) {
        // Check if we already parsed this in the complete regex above
        const lastCompleteIndex = response.lastIndexOf('</tool_code>');
        const lastOpeningIndex = response.lastIndexOf('<tool_code>');
        
        // If the last opening is after the last closing, we have an incomplete tag
        if (lastOpeningIndex > lastCompleteIndex) {
          const incompleteBlock = response.substring(lastOpeningIndex + '<tool_code>'.length);
          const parsed = this.parseToolBlock(incompleteBlock);
          if (parsed) {
            tool_calls.push(parsed);
          }
        }
      }

      // 4. Handle incomplete tool_code tags (closing without opening - less common)
      // Check if there's a </tool_code> that doesn't have a matching <tool_code>
      const closingToolCodeMatch = response.match(/^([\s\S]*?)<\/tool_code>/i);
      if (closingToolCodeMatch && tool_calls.length === 0) {
        // Only process if we haven't found any complete tool calls
        const incompleteBlock = closingToolCodeMatch[1];
        const parsed = this.parseToolBlock(incompleteBlock);
        if (parsed) {
          tool_calls.push(parsed);
        }
      }

      // If no XML tags found, return original response as plain text (or partial thought)
      if (!thought && tool_calls.length === 0) {
         // Fallback for JSON-style tool calls (for legacy/inconsistent models)
         if (response.includes("Tool calls:")) {
            const match = response.match(/Tool calls:\s*(\[.*\])/s);
            if (match) {
                try {
                    const jsonCalls = JSON.parse(match[1]);
                    const calls = Array.isArray(jsonCalls) ? jsonCalls : [jsonCalls];
                    // Map to expected structure if needed, but usually it matches
                    // We treat everything before "Tool calls:" as thought
                    const splitThought = response.split("Tool calls:")[0].trim();
                    return {
                        thought: splitThought,
                        tool_calls: calls
                    };
                } catch (e) {
                    // ignore
                }
            }
         }

         // Check if it's just text without tags
         return { response: response };
      }

      return {
        thought,
        tool_calls: tool_calls.length > 0 ? tool_calls : undefined
      };

    } catch (error: any) {
      return { error: error.message, response: response };
    }
  }

  private parseToolBlock(toolBlock: string): ToolCall | null {
    // Extract tool name (handle incomplete tags)
    const nameMatch = toolBlock.match(/<tool_name>([\s\S]*?)(?:<\/tool_name>|$)/i);
    if (!nameMatch) {
      return null;
    }
    
    const toolName = nameMatch[1].trim();
    if (!toolName) {
      return null;
    }
    
    // Extract parameters block (handle incomplete tags)
    const paramsMatch = toolBlock.match(/<parameters>([\s\S]*?)(?:<\/parameters>|$)/i);
    const args: any = {};
    
    if (paramsMatch) {
      const paramsContent = paramsMatch[1];
      // Regex to find all tags inside parameters
      // Match <key>value</key> or <key>value (if incomplete)
      const paramRegex = /<([^>]+)>([\s\S]*?)(?:<\/\1>|$)/gi;
      let paramMatch;
      
      while ((paramMatch = paramRegex.exec(paramsContent)) !== null) {
        const key = paramMatch[1].trim();
        const value = paramMatch[2].trim();
        if (key && value !== undefined) {
          args[key] = value;
        }
      }
    }

    return {
      name: toolName,
      arguments: args
    };
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

      // Prepare context for tools
      const toolContext = {
        workingDirectory: this.workingDirectory,
      };

      // Show status instead of full tool details (Silent Actor pattern)
      // Note: Tool execution is now integrated into the stream flow
      this.sendMessage({
        type: "tool_call",
        tool: toolCall.name,
        args: { status: ` Running ${toolCall.name}...` }, // Don't show full args
      });

      if (tool.requiresApproval) {
        const approved = await this.requestApproval(toolCall.name, toolCall.arguments);
        
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
        // Pass context to tool execution
        const result = await tool.execute(toolCall.arguments, toolContext);
        
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
    
    let diffData: { diff: string; added: number; removed: number } | undefined;

    // Interactive Diff: Compute diff for file modifications
    if (toolName === "edit_file" || toolName === "write_file") {
      try {
        let oldContent = "";
        let newContent = "";
        const filePath = args.path;

        // Try to read existing file
        try {
          oldContent = await fs.readFile(filePath, "utf-8");
        } catch {
          // File doesn't exist (for write_file this is creation)
          oldContent = "";
        }

        if (toolName === "edit_file") {
          // For edit_file, we need to simulate the replacement
          const search = args.search;
          const replace = args.replace;
          
          // Normalizing line endings
          const normalizedContent = oldContent.replace(/\r\n/g, '\n');
          const normalizedSearch = search.replace(/\r\n/g, '\n');
          
          if (normalizedContent.includes(normalizedSearch)) {
            // We compute the diff of the *change* specifically
            // Or we could compute the diff of the whole file. 
            // For surgical edits, diffing the search/replace block is cleaner.
            diffData = computeDiff(normalizedSearch, replace);
          } else {
            // If search block not found, we can't show a valid diff, but we can warn
            diffData = { diff: "⚠️  Search block not found in file. Tool execution will fail.", added: 0, removed: 0 };
          }
        } else if (toolName === "write_file") {
          // For write_file, we compare old content vs new content
          // Clean content from markdown if needed (simple check)
          let content = args.content;
          if (content.startsWith("```")) {
             // Simple extraction if the agent still output markdown
             const match = content.match(/^```[\w]*\n([\s\S]*?)\n```$/);
             if (match) content = match[1];
          }
          diffData = computeDiff(oldContent, content);
        }
      } catch (error) {
        console.error("Failed to compute diff for approval:", error);
      }
    }

    return new Promise((resolve) => {
      this.pendingApprovals.set(requestId, { resolve });
      
      this.sendMessage({
        type: "approval_request",
        requestId,
        tool: toolName,
        args,
        diff: diffData?.diff,
        added: diffData?.added,
        removed: diffData?.removed,
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
