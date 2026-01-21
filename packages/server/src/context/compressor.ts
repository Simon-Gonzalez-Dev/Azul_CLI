import { ChatMessage } from "../types.js";

/**
 * Context Window Management
 *
 * Handles token estimation and context compression to stay within
 * the model's context window limits.
 */

// Approximate token estimation: ~4 characters per token (conservative)
const CHARS_PER_TOKEN = 4;

export interface ContextStats {
  estimatedTokens: number;
  maxTokens: number;
  usagePercent: number;
  messageCount: number;
  compressedCount: number;
}

export interface CompressionConfig {
  maxContextTokens: number;      // Maximum context window size
  compressionThreshold: number;  // Start compressing at this % (e.g., 0.8 = 80%)
  keepRecentTurns: number;       // Keep last N turns at full fidelity
  minToolOutputLength: number;   // Only compress tool outputs longer than this
}

const DEFAULT_CONFIG: CompressionConfig = {
  maxContextTokens: 32000,
  compressionThreshold: 0.80,
  keepRecentTurns: 15,
  minToolOutputLength: 500,
};

/**
 * Estimate token count for a string
 */
export function estimateTokens(text: string): number {
  if (!text) return 0;
  return Math.ceil(text.length / CHARS_PER_TOKEN);
}

/**
 * Estimate total tokens in conversation history
 */
export function estimateConversationTokens(
  systemPrompt: string,
  messages: ChatMessage[]
): number {
  let total = estimateTokens(systemPrompt);

  for (const msg of messages) {
    total += estimateTokens(msg.content || "");

    // Account for tool calls in assistant messages
    if (msg.tool_calls) {
      for (const tc of msg.tool_calls) {
        total += estimateTokens(tc.name);
        total += estimateTokens(JSON.stringify(tc.arguments));
      }
    }
  }

  return total;
}

/**
 * Get context usage statistics
 */
export function getContextStats(
  systemPrompt: string,
  messages: ChatMessage[],
  config: CompressionConfig = DEFAULT_CONFIG
): ContextStats {
  const estimatedTokens = estimateConversationTokens(systemPrompt, messages);
  const compressedCount = messages.filter(m => (m as any)._compressed).length;

  return {
    estimatedTokens,
    maxTokens: config.maxContextTokens,
    usagePercent: Math.round((estimatedTokens / config.maxContextTokens) * 100),
    messageCount: messages.length,
    compressedCount,
  };
}

/**
 * Compress a tool output to a summary
 */
function compressToolOutput(content: string, toolName: string): string {
  try {
    const parsed = JSON.parse(content);

    // For file reads (view tool), summarize the content
    if (toolName === "view" && parsed.content) {
      const lines = parsed.content.split('\n').length;
      const path = parsed.path || "file";
      return JSON.stringify({
        success: parsed.success,
        message: `[Compressed: Read ${lines} lines from ${path}]`,
        _compressed: true,
      });
    }

    // For ls tool, keep just the summary
    if (toolName === "ls" && parsed.content) {
      const itemCount = parsed.content.split('\n').length;
      return JSON.stringify({
        success: parsed.success,
        message: `[Compressed: Listed ${itemCount} items in ${parsed.path || "directory"}]`,
        _compressed: true,
      });
    }

    // For grep tool, summarize matches
    if (toolName === "grep" && parsed.matches) {
      const matchCount = parsed.matches.length;
      return JSON.stringify({
        success: parsed.success,
        message: `[Compressed: Found ${matchCount} matches for pattern]`,
        _compressed: true,
      });
    }

    // For bash tool, summarize output
    if (toolName === "bash" && (parsed.stdout || parsed.stderr)) {
      const hasOutput = (parsed.stdout?.length || 0) + (parsed.stderr?.length || 0);
      return JSON.stringify({
        success: parsed.success,
        message: `[Compressed: Command executed, ${hasOutput} chars output]`,
        _compressed: true,
      });
    }

    // For edit/write, keep the success message but remove diff
    if ((toolName === "edit" || toolName === "write") && parsed.success) {
      return JSON.stringify({
        success: true,
        message: parsed.message || `[Compressed: File operation completed]`,
        filePath: parsed.filePath,
        _compressed: true,
      });
    }

    // Default: if content is too long, truncate
    if (content.length > 500) {
      return JSON.stringify({
        success: parsed.success ?? true,
        message: `[Compressed: Tool output truncated (${content.length} chars)]`,
        _compressed: true,
      });
    }

    return content;
  } catch {
    // Not JSON, just truncate
    if (content.length > 500) {
      return `[Compressed: ${content.length} chars of output]`;
    }
    return content;
  }
}

/**
 * Extract tool name from conversation context
 * Looks at the previous assistant message for tool calls
 */
function findToolNameForToolMessage(messages: ChatMessage[], toolMessageIndex: number): string {
  // Look backwards for the assistant message that made this tool call
  for (let i = toolMessageIndex - 1; i >= 0; i--) {
    const msg = messages[i];
    if (msg.role === "assistant" && msg.tool_calls) {
      // Find matching tool call by ID if available
      const toolMsg = messages[toolMessageIndex];
      if (toolMsg.tool_call_id) {
        const matchingCall = msg.tool_calls.find(tc => tc.id === toolMsg.tool_call_id);
        if (matchingCall) {
          return matchingCall.name;
        }
      }
      // Otherwise return the first tool call name
      return msg.tool_calls[0]?.name || "unknown";
    }
  }
  return "unknown";
}

/**
 * Compress conversation history to fit within context window
 *
 * Strategy:
 * 1. Never compress: system prompt, AZUL.md content (they're in system prompt)
 * 2. Keep last N turns at full fidelity
 * 3. Compress older tool outputs (they're usually verbose)
 * 4. Summarize very old turns if still over threshold
 */
export function compressConversation(
  systemPrompt: string,
  messages: ChatMessage[],
  config: CompressionConfig = DEFAULT_CONFIG
): ChatMessage[] {
  const currentTokens = estimateConversationTokens(systemPrompt, messages);
  const threshold = config.maxContextTokens * config.compressionThreshold;

  // If under threshold, no compression needed
  if (currentTokens < threshold) {
    return messages;
  }

  // Create a copy to modify
  const compressed = [...messages];

  // Calculate how many messages are in "recent" zone (protected from compression)
  const recentStartIndex = Math.max(0, compressed.length - config.keepRecentTurns * 2);

  // Pass 1: Compress old tool outputs
  for (let i = 0; i < recentStartIndex; i++) {
    const msg = compressed[i];
    const content = msg.content || "";

    // Only compress tool messages with long content
    if (msg.role === "tool" && content.length > config.minToolOutputLength) {
      // Check if already compressed
      if ((msg as any)._compressed) continue;

      const toolName = findToolNameForToolMessage(compressed, i);
      const compressedContent = compressToolOutput(content, toolName);

      compressed[i] = {
        ...msg,
        content: compressedContent,
        _compressed: true,
      } as ChatMessage;
    }
  }

  // Check if we're now under threshold
  const afterPass1 = estimateConversationTokens(systemPrompt, compressed);
  if (afterPass1 < threshold) {
    return compressed;
  }

  // Pass 2: Summarize very old assistant messages (if still over)
  // Keep the thought/reasoning but make it more concise
  for (let i = 0; i < Math.floor(recentStartIndex / 2); i++) {
    const msg = compressed[i];
    const content = msg.content || "";

    if (msg.role === "assistant" && content.length > 300) {
      if ((msg as any)._compressed) continue;

      // Truncate long assistant messages
      const truncated = content.substring(0, 200) + "... [truncated for context]";
      compressed[i] = {
        ...msg,
        content: truncated,
        _compressed: true,
      } as ChatMessage;
    }
  }

  return compressed;
}

/**
 * Check if compression is needed
 */
export function needsCompression(
  systemPrompt: string,
  messages: ChatMessage[],
  config: CompressionConfig = DEFAULT_CONFIG
): boolean {
  const currentTokens = estimateConversationTokens(systemPrompt, messages);
  const threshold = config.maxContextTokens * config.compressionThreshold;
  return currentTokens >= threshold;
}

export { DEFAULT_CONFIG };
