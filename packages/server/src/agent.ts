import * as path from "path";
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

# CRITICAL IDENTITY RULES
1. **YOU HAVE ACCESS.** Never say "I don't have access" or "I cannot see." You have tools. USE THEM.
2. **BE PROACTIVE.** If the user says "fix the html" and you don't see a path, do NOT ask "which file?". Use list_dir immediately to find it yourself.
3. **SILENT EXECUTION.** Do not chatter. Do not print code to the chat if you are about to write it to a file.

# THE "AMBIGUITY" PROTOCOL (Use when user is vague)
If the user request is generic (e.g., "update the html page", "fix the bug", "refactor the code") and no file path is provided:
1. **IMMEDIATELY call list_dir** with path "." to inspect the current directory.
2. **Scan for relevant files** based on the user's intent (e.g., *.html* files for "html page").
3. **If a likely candidate is found**, READ IT immediately using read_file.
4. **Proceed with the task** using that context.
5. Only ask the user for clarification if there are MULTIPLE conflicting candidates (e.g., 5 different HTML files).

# CORE OPERATING RULES

1. **ACTION OVER CHATTER**: 
   - Do NOT describe code changes in the chat before making them. 
   - Do NOT output "Here is the code:" followed by a block of code if you intend to use a tool to write it immediately after. 
   - **JUST CALL THE TOOL.**

2. **EXPLORE FIRST**: 
   - Never guess file paths or contents. 
   - Always start by mapping the territory using list_dir and read_file. 
   - If a file doesn't exist, verify the directory structure before creating it.

3. **SURGICAL EDITING (The "Patch" Protocol)**:
   - **PREFER edit_file (Search & Replace) over write_file**.
   - write_file overwrites the ENTIRE file. Only use it for creating new files or very small files (<50 lines).
   - For existing files, locate the unique block of code you want to change and provide a replacement.
   - The search block must match the file content EXACTLY (including whitespace).

4. **VERIFICATION**:
   - After editing code, you are encouraged to run linter checks, build commands, or tests via execute_command to verify your changes worked.
   - If a tool fails, read the error, analyze the cause, and self-correct.

# TOOL USAGE - CRITICAL: ALL PARAMETERS ARE REQUIRED

When calling tools, you MUST provide ALL required parameters. The tool system will reject calls with missing parameters.

## Tool: list_dir
**Purpose:** List contents of a directory
**Required Parameters:**
- path: <directory_path>

## Tool: read_file
**Purpose:** Read file contents
**Required Parameters:**
- path: <file_path>

## Tool: edit_file
**Purpose:** Surgical file editing via search & replace
**Required Parameters:**
- path: <file_path>
- search: <exact_code_block_to_find>
- replace: <new_code_block>

**IMPORTANT:** The search parameter must match the file content EXACTLY including whitespace. Copy the search block from a previous read_file output.

## Tool: write_file
**Purpose:** Create new files or completely overwrite existing files
**Required Parameters:**
- path: <file_path>
- content: <complete_file_content>

## Tool: execute_command
**Purpose:** Execute shell commands
**Required Parameters:**
- command: <shell_command>

## Tool: search_files
**Purpose:** Search for text patterns in files
**Required Parameters:**
- pattern: <search_pattern>
- directory: <directory_path>

# RESPONSE FORMATTING

- **When Thinking:** If you need to plan, you may output a short "Thought" before a tool call, but keep it brief (1-2 sentences).
- **When Acting:** Issue the Tool Call immediately with ALL required parameters.
- **When Finished:** Only address the User when the task is complete or you need clarification.

# CRITICAL REMINDER
- ALL tool parameters listed above are REQUIRED. Do not omit any parameters.
- Provide actual values for all placeholders (<parameter_name>) when calling tools.
- The tool system validates all parameters and will reject calls with missing parameters.`;
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

      // Attempt to parse the response as JSON (for local models or Groq falling back to text)
      // This handles the case where the model outputs ```json ... ```
      // IMPORTANT: We must try to parse BEFORE treating it as plain text
      const parsedResponse = this.parseResponse(response || this.streamingResponse || "");

      if (parsedResponse.error) {
         // If it looks like it WAS trying to be JSON (had braces) but failed
         if ((response || "").includes("```json") || (response || "").trim().startsWith("{")) {
             console.warn("JSON Parse Error:", parsedResponse.error);
             this.conversationHistory.push({
               role: "user", 
               content: `System Error: Invalid JSON format. Please output RAW JSON only, no markdown. Error: ${parsedResponse.error}`
             });
             await this.runAgentLoop();
             return;
         }
         // Otherwise, treat as normal text (fall through)
      } else if (parsedResponse.tool_calls && parsedResponse.tool_calls.length > 0) {
        // We successfully parsed tool calls from the text response
        this.conversationHistory.push({
          role: "assistant",
          content: parsedResponse.thought || "I'll use tools to complete this task.",
          tool_calls: parsedResponse.tool_calls,
        });
        
        await this.executeToolCalls(parsedResponse.tool_calls);
        await this.runAgentLoop();
        return;
      }

      // If we get here, it's a pure text response (or parsing failed and it's not JSON-like)
      const textContent = parsedResponse.response || response || "I'm ready to help.";
      
      this.sendMessage({
        type: "agent_response",
        content: textContent,
      });

      this.conversationHistory.push({
        role: "assistant",
        content: textContent,
      });
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
      // 1. Aggressive Sanitization: Remove markdown code blocks
      let cleanResponse = response.replace(/```json\s*|\s*```/g, "");
      
      // 2. Regex Heuristic: Look for "tool_calls" pattern specifically if standard JSON fails
      // This helps when models output: Thought: ... Tool calls: [...]
      if (!cleanResponse.trim().startsWith("{") && cleanResponse.includes("Tool calls:")) {
         const match = cleanResponse.match(/Tool calls:\s*(\[.*\])/s);
         if (match) {
            try {
               const toolCalls = JSON.parse(match[1]);
               return { 
                 thought: cleanResponse.split("Tool calls:")[0].trim(),
                 tool_calls: Array.isArray(toolCalls) ? toolCalls : [toolCalls]
               };
            } catch (e) {
               // Continue to standard extraction
            }
         }
      }

      // 3. Standard Extraction: Locate the first { and last } to isolate JSON
      const firstBrace = cleanResponse.indexOf('{');
      const lastBrace = cleanResponse.lastIndexOf('}');
      
      if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
        const jsonStr = cleanResponse.substring(firstBrace, lastBrace + 1);
        try {
          const parsed = JSON.parse(jsonStr);
          
          // Normalize result
          if (parsed.tool_calls) {
             return parsed;
          }
          // Handle case where model outputs a single tool call object directly
          if (parsed.name && parsed.arguments) {
             return { tool_calls: [parsed] };
          }
          
          return parsed;
        } catch (e) {
           return { error: "Invalid JSON format inside braces." };
        }
      }
    } catch (error: any) {
      return { error: error.message };
    }

    // No JSON object found, treat as pure text response
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
