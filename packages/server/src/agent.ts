import * as fs from "fs/promises";
import * as path from "path";
import { ILLMService } from "./llm-interface.js";
import { ChatMessage, ToolCall, ToolDefinition, AgentStatus } from "./types.js";
import { tools, getToolByName } from "./tools/index.js";
import { computeDiff } from "./tools/filesystem.js";
import {
  compressConversation,
  getContextStats,
  CompressionConfig,
  DEFAULT_CONFIG,
} from "./context/compressor.js";

export type MessageCallback = (message: {
  type: string;
  [key: string]: any;
}) => void;

// AZUL.md content loaded at startup
let azulMdContent: string | null = null;

/**
 * Load AZUL.md from the working directory or parent directories
 * Search order: {cwd}/AZUL.md, {cwd}/.azul/AZUL.md, parent dirs
 */
async function loadAzulMd(workingDir: string): Promise<string | null> {
  const searchPaths = [
    path.join(workingDir, "AZUL.md"),
    path.join(workingDir, ".azul", "AZUL.md"),
  ];

  // Also check parent directories (for monorepos)
  let currentDir = workingDir;
  for (let i = 0; i < 3; i++) {
    const parentDir = path.dirname(currentDir);
    if (parentDir === currentDir) break;
    searchPaths.push(path.join(parentDir, "AZUL.md"));
    searchPaths.push(path.join(parentDir, ".azul", "AZUL.md"));
    currentDir = parentDir;
  }

  for (const searchPath of searchPaths) {
    try {
      const content = await fs.readFile(searchPath, "utf-8");
      console.log(`Loaded project instructions from: ${searchPath}`);

      // Process @import directives
      const basePath = path.dirname(searchPath);
      const processedContent = await processAzulMdImports(content, basePath);

      return processedContent;
    } catch {
      // File not found, continue searching
    }
  }

  return null;
}

/**
 * Process @import directives in AZUL.md content
 * Syntax: @path/to/file or @import path/to/file
 * Lines starting with @ followed by a path are treated as file imports
 */
async function processAzulMdImports(
  content: string,
  basePath: string
): Promise<string> {
  const importedPaths = new Set<string>(); // Prevent circular imports
  const lines = content.split("\n");
  const result: string[] = [];

  for (const line of lines) {
    const trimmed = line.trim();

    // Check for import directives: @path/to/file or @import path/to/file
    if (trimmed.startsWith("@")) {
      let importPath: string | null = null;

      // Handle @import syntax
      if (trimmed.startsWith("@import ")) {
        importPath = trimmed.slice(8).trim();
      }
      // Handle @path syntax (must contain / or start with . to distinguish from mentions)
      else if (trimmed.includes("/") || trimmed.startsWith("@.")) {
        importPath = trimmed.slice(1).trim();
      }

      if (importPath) {
        // Resolve path relative to AZUL.md location
        const resolvedPath = path.isAbsolute(importPath)
          ? importPath
          : path.resolve(basePath, importPath);

        // Skip if already imported (circular import protection)
        if (importedPaths.has(resolvedPath)) {
          result.push(`<!-- Skipped circular import: ${importPath} -->`);
          continue;
        }

        importedPaths.add(resolvedPath);

        try {
          const importedContent = await fs.readFile(resolvedPath, "utf-8");
          result.push(`<!-- @import ${importPath} -->`);
          result.push(importedContent);
          result.push(`<!-- end @import ${importPath} -->`);
          continue;
        } catch {
          // If import fails, keep original line with warning
          result.push(`<!-- Failed to import: ${importPath} -->`);
          result.push(line);
          continue;
        }
      }
    }

    result.push(line);
  }

  return result.join("\n");
}

// Maximum iterations to prevent infinite loops
const MAX_AGENT_ITERATIONS = 10;

export class Agent {
  private llm: ILLMService;
  private conversationHistory: ChatMessage[] = [];
  private systemPrompt: string = "";
  private sendMessage: MessageCallback;
  private pendingApprovals: Map<string, { resolve: (approved: boolean) => void }> = new Map();
  private streamingResponse: string = "";
  private workingDirectory: string;
  private compressionConfig: CompressionConfig;

  // Persistent agent state tracking (across recursion loops)
  private agentStatus: AgentStatus = 'IDLE';
  private currentToolCalls: ToolCall[] = [];
  private executingToolIndex: number = 0;

  constructor(sendMessage: MessageCallback, llm: ILLMService, workingDirectory?: string, contextSize?: number) {
    this.sendMessage = sendMessage;
    this.llm = llm;
    this.workingDirectory = workingDirectory || process.cwd();
    // Configure compression based on context size
    this.compressionConfig = {
      ...DEFAULT_CONFIG,
      maxContextTokens: contextSize || DEFAULT_CONFIG.maxContextTokens,
    };
    this.initializeSystemPrompt();
  }

  async initialize(): Promise<void> {
    // Load AZUL.md on initialization
    azulMdContent = await loadAzulMd(this.workingDirectory);
    this.initializeSystemPrompt();
  }

  setLLM(llm: ILLMService): void {
    this.llm = llm;
  }

  async setWorkingDirectory(dir: string): Promise<void> {
    this.workingDirectory = dir;
    // Reload AZUL.md when directory changes
    azulMdContent = await loadAzulMd(dir);
    this.initializeSystemPrompt();
  }

  getWorkingDirectory(): string {
    return this.workingDirectory;
  }

  private initializeSystemPrompt(): void {
    // Build AZUL.md section if available
    const azulMdSection = azulMdContent
      ? `\n\n## PROJECT INSTRUCTIONS (from AZUL.md)\n\n${azulMdContent}`
      : "";

    this.systemPrompt = `# ROLE: Azul - Autonomous Coding Agent

You are Azul, an autonomous coding agent with direct filesystem and shell access. Complete tasks autonomously using your tools.

## CORE PRINCIPLES

**1. Autonomous Action**
- You have FULL access to tools. Never claim you "cannot see" or "don't have access"
- When information is missing, use tools to discover it yourself
- Only ask users for clarification when multiple valid interpretations exist

**2. Silent Execution**
- Execute actions instead of describing them
- Never show code in chat that you're about to write to a file
- Avoid meta-commentary like "I will now..." or "Here's the code:"

**3. Explore Before Assume**
- Never guess file paths, structures, or contents
- Always verify using ls and view before making changes
- Map the codebase before acting

**4. Smart Editing**
- Prefer edit over write for existing files
- Use write only for NEW files or very small files (<50 lines)
- For edit: Use unique identifiers (function names, class names), NOT line numbers
- Include 2-3 lines of context for better matching

---

## TOOLS

You have these tools available:

| Tool | Purpose | Requires Approval |
|------|---------|-------------------|
| ls | List directory contents (filters .git, node_modules) | No |
| view | Read file with line numbers | No |
| edit | Edit file via search/replace (use code blocks, not line numbers) | Yes |
| write | Create new files | Yes |
| bash | Execute shell commands (sandboxed) | Yes |
| grep | Search for patterns in files | No |

---

## OUTPUT FORMAT

**CRITICAL: You MUST use XML tags for ALL output.**

<thought>
Your reasoning about the task. What you observe, what you plan to do.
</thought>

<tool_code>
<tool_name>view</tool_name>
<parameters>
<path>./src/main.ts</path>
</parameters>
</tool_code>

You can include multiple <tool_code> blocks if needed.

---

## BEHAVIORAL RULES

**MUST DO:**
- Use tools to discover information
- Execute actions instead of describing them
- Verify changes work (run tests, build, etc.)
- Put reasoning in <thought> tags
- Put tool calls in <tool_code> tags

**MUST NOT:**
- Claim you don't have access (you have tools!)
- Ask for file paths when you can use ls to find them
- Show code in chat before writing to files
- Use write on existing files (use edit)
- Use line numbers for editing (use unique code blocks)
- Output text outside XML tags

---

## TASK COMPLETION (CRITICAL)

**When to STOP:**
- After completing ALL requested actions successfully
- After providing the final answer or confirmation
- When there are no more actions needed to fulfill the user's request

**DO NOT continue looping:**
- Do not view/verify files after successful writes unless explicitly requested
- Do not make additional edits after the request is fulfilled
- Do not start new actions that weren't requested
- One successful write/edit is usually enough - trust the tool result

**Completion Signal:**
When the task is complete, output ONLY a thought with a brief summary and checkmark:

<thought>
✓ [Brief summary of what was done - ONE sentence max]
</thought>

Example completions:
- ✓ Created fizzbuzz.py with the FizzBuzz implementation.
- ✓ Updated config.json with the new API endpoint.
- ✓ Fixed the syntax error in main.ts line 42.

---

## COMPLEMENTARY TEXT STYLE

Before EACH tool call, include a brief one-line description:

<thought>
I'll create a Python file with the FizzBuzz solution.
</thought>
<tool_code>
<tool_name>write</tool_name>
...
</tool_code>

**Style Guidelines:**
- Keep descriptions to ONE sentence
- Start with "I'll..." or "Let me..."
- Be specific but concise
- No multi-paragraph explanations
${azulMdSection}

## ENVIRONMENT
Working Directory: ${this.workingDirectory}`;
  }

  async handleUserMessage(content: string): Promise<void> {
    // Check for system commands
    if (content.startsWith("[SYSTEM:INIT]")) {
      // Import the init prompt dynamically
      const { createInitMessage } = await import("./prompts/init.js");
      content = createInitMessage(this.workingDirectory);
    }

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
    this.agentStatus = 'IDLE';
    this.currentToolCalls = [];
    this.executingToolIndex = 0;

    this.pendingApprovals.forEach((pending) => {
      pending.resolve(false);
    });
    this.pendingApprovals.clear();
  }

  // Update and emit agent status for UI coherence
  private setAgentStatus(status: AgentStatus, toolName?: string, toolIndex?: number): void {
    this.agentStatus = status;
    if (toolIndex !== undefined) {
      this.executingToolIndex = toolIndex;
    }

    this.sendMessage({
      type: "agent_status",
      status,
      toolName,
      toolIndex: this.executingToolIndex,
      totalTools: this.currentToolCalls.length,
    });
  }

  // Get current agent status (for external queries)
  getAgentStatus(): AgentStatus {
    return this.agentStatus;
  }

  private async runAgentLoop(loopCount: number = 0): Promise<void> {
    // Prevent infinite loops with maximum iteration check
    if (loopCount >= MAX_AGENT_ITERATIONS) {
      this.setAgentStatus('IDLE');
      this.sendMessage({
        type: "system",
        message: `⚠️ Reached maximum iterations (${MAX_AGENT_ITERATIONS}). Task may be incomplete. Please provide more specific instructions.`,
      });
      return;
    }

    try {
      // Set initial status to THINKING
      this.setAgentStatus('THINKING');

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

      // Compress conversation if needed to stay within context window
      const compressedHistory = compressConversation(
        this.systemPrompt,
        this.conversationHistory,
        this.compressionConfig
      );

      // Get and send context stats to UI
      const contextStats = getContextStats(
        this.systemPrompt,
        compressedHistory,
        this.compressionConfig
      );
      this.sendMessage({
        type: "context_stats",
        stats: contextStats,
      });

      // Use compressed history for LLM call
      const { response, toolCalls, stats } = await this.llm.getCompletion(
        this.systemPrompt,
        compressedHistory,
        tools,
        handleStream
      );

      // Finalize streaming - parse final content
      const finalContent = response || this.streamingResponse || "";
      streamState = "complete";

      const totalStats = this.llm.getTokenStats();
      const finalParsed = parseStreamingContent(finalContent);

      // Merge streaming-detected tool calls with final parse (don't replace entirely)
      // This ensures we don't lose tool calls detected during streaming
      if (finalParsed.toolCalls.length > 0) {
        // If final parse found more tool calls, use those (they're more complete)
        // But if streaming found some that final didn't, keep them
        const existingNames = new Set(parsedToolCalls.map(tc => `${tc.name}:${JSON.stringify(tc.arguments)}`));
        const finalNames = new Set(finalParsed.toolCalls.map(tc => `${tc.name}:${JSON.stringify(tc.arguments)}`));

        // Start with streaming results, add any new ones from final parse
        const mergedToolCalls = [...parsedToolCalls];
        for (const tc of finalParsed.toolCalls) {
          const key = `${tc.name}:${JSON.stringify(tc.arguments)}`;
          if (!existingNames.has(key)) {
            mergedToolCalls.push(tc);
          }
        }

        // If final parse has strictly more/different results, prefer it
        // (streaming parser may have incomplete parsing)
        if (finalParsed.toolCalls.length >= parsedToolCalls.length) {
          parsedToolCalls = finalParsed.toolCalls;
        } else {
          parsedToolCalls = mergedToolCalls;
        }
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

        // Track current tool calls for status reporting
        this.currentToolCalls = parsedResponse.tool_calls;
        this.executingToolIndex = 0;
        this.setAgentStatus('EXECUTING_TOOL', parsedResponse.tool_calls[0]?.name, 0);

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

        // Mark as done after tools execute, clear tool tracking
        streamState = "done";
        this.currentToolCalls = [];
        this.executingToolIndex = 0;

        await this.runAgentLoop(loopCount + 1);
        return;
      }

      // If no tool calls but we have thought, treat as final response
      if (parsedResponse.thought && (!parsedResponse.tool_calls || parsedResponse.tool_calls.length === 0)) {
          streamState = "done";
          this.setAgentStatus('COMPLETE');

          // Check for task completion signal (✓ or completion keywords)
          const thought = parsedResponse.thought;
          const isTaskComplete = thought.includes("✓") ||
                                 thought.toLowerCase().includes("task complete") ||
                                 thought.toLowerCase().includes("completed successfully") ||
                                 (thought.toLowerCase().includes("done") && thought.length < 200);

          if (isTaskComplete) {
            // Send task completion notification to UI
            this.sendMessage({
              type: "task_complete",
              summary: thought.replace(/^✓\s*/, "").trim(), // Remove leading checkmark for cleaner display
            });
          }

          // Stream message already sent with completion, just update conversation
          this.conversationHistory.push({
            role: "assistant",
            content: parsedResponse.thought,
          });

          // Reset to IDLE after task completion
          this.setAgentStatus('IDLE');
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
             await this.runAgentLoop(loopCount + 1);
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
             await this.runAgentLoop(loopCount + 1);
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
      this.setAgentStatus('IDLE');
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
    for (let i = 0; i < toolCalls.length; i++) {
      const toolCall = toolCalls[i];
      const tool = getToolByName(toolCall.name);

      // Update agent status for each tool
      this.setAgentStatus('EXECUTING_TOOL', toolCall.name, i);

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
        this.setAgentStatus('AWAITING_APPROVAL', toolCall.name, i);
        const approved = await this.requestApproval(toolCall.name, toolCall.arguments);

        if (!approved) {
          const result = { success: false, error: "User denied approval", toolName: toolCall.name };
          this.sendMessage({
            type: "tool_result",
            tool: toolCall.name,
            toolIndex: i,
            totalTools: toolCalls.length,
            result: { success: false, toolName: toolCall.name, message: "User denied approval" },
          });

          this.conversationHistory.push({
            role: "tool",
            content: JSON.stringify(result),
            tool_call_id: toolCallId,
          });
          continue;
        }

        // Resume EXECUTING_TOOL status after approval
        this.setAgentStatus('EXECUTING_TOOL', toolCall.name, i);
      }

      try {
        // Pass context to tool execution
        const result = await tool.execute(toolCall.arguments, toolContext);

        // Show minimal result (Silent Actor pattern) with toolName from result
        this.sendMessage({
          type: "tool_result",
          tool: toolCall.name,
          toolIndex: i,
          totalTools: toolCalls.length,
          result: {
            success: result.success,
            toolName: result.toolName || toolCall.name,
            message: result.message || (result.success ? "Completed successfully" : result.error),
            // Only show diff for file operations, not full content
            diff: result.diff,
            added: result.added,
            removed: result.removed,
            filePath: result.filePath,
            // Include additional fields for UI
            content: result.content,
            commandPreview: result.commandPreview,
            riskLevel: result.riskLevel,
          },
        });

        // Add full tool result to history for LLM context
        this.conversationHistory.push({
          role: "tool",
          content: JSON.stringify(result),
          tool_call_id: toolCallId,
        });
      } catch (error: any) {
        const result = { success: false, error: error.message, toolName: toolCall.name };
        this.sendMessage({
          type: "tool_result",
          tool: toolCall.name,
          toolIndex: i,
          totalTools: toolCalls.length,
          result: { success: false, toolName: toolCall.name, message: error.message },
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
    // Updated to use new tool names: edit, write
    if (toolName === "edit" || toolName === "write") {
      try {
        let oldContent = "";
        let newContent = "";
        const filePath = args.path;

        // Try to read existing file
        try {
          oldContent = await fs.readFile(filePath, "utf-8");
        } catch {
          // File doesn't exist (for write this is creation)
          oldContent = "";
        }

        if (toolName === "edit") {
          // For edit, we need to simulate the replacement
          const search = args.old_string;
          const replace = args.new_string;

          // Normalizing line endings
          const normalizedContent = oldContent.replace(/\r\n/g, '\n');
          const normalizedSearch = search?.replace(/\r\n/g, '\n') || "";

          if (normalizedContent.includes(normalizedSearch)) {
            // We compute the diff of the *change* specifically
            diffData = computeDiff(normalizedSearch, replace || "");
          } else {
            // If search block not found, we can't show a valid diff, but we can warn
            diffData = { diff: "⚠️  Search block not found in file. Tool execution will fail.", added: 0, removed: 0 };
          }
        } else if (toolName === "write") {
          // For write, we compare old content vs new content
          // Clean content from markdown if needed (simple check)
          let content = args.content || "";
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
