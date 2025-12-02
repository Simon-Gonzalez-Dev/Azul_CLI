import React from "react";
import { Box, Text } from "ink";
import { Message, ProviderStatusMessage } from "../types.js";
import { DiffView } from "./DiffView.js";

interface LogViewProps {
  messages: Message[];
}

export const LogView: React.FC<LogViewProps> = ({ messages }) => {
  // Generate stable keys for messages - optimized for performance
  const getMessageKey = (message: Message, index: number): string => {
    // Use streamId if available (for streaming messages), otherwise fallback
    if ((message as any).streamId) {
      return `${message.type}-${(message as any).streamId}`;
    }
    // For non-streaming messages, use timestamp + type + index
    return `${message.type}-${message.timestamp}-${index}`;
  };

  const renderMessage = (message: Message, index: number) => {
    const time = new Date(message.timestamp).toLocaleTimeString();
    const messageKey = getMessageKey(message, index);

    switch (message.type) {
      case "connected":
        return (
          <Box key={messageKey} marginY={0}>
            <Text color="green">✓ {message.message}</Text>
          </Box>
        );

      case "user_message_received":
        return (
          <Box key={messageKey} marginY={0} flexDirection="column">
            <Text color="cyan" bold>
              You ({time}):
            </Text>
            <Text>{message.content}</Text>
          </Box>
        );


      case "tool_call":
        // Silent Actor pattern: Show minimal status, not full details
        const toolArgs = message.args || {};
        if (toolArgs.status) {
          // New format: just show status
          return (
            <Box key={messageKey} marginY={0}>
              <Text color="blue" dimColor>
                {toolArgs.status}
              </Text>
            </Box>
          );
        }
        // Fallback for old format (backwards compatibility)
        if (message.tool === "write_file" && toolArgs.path) {
          return (
            <Box key={messageKey} marginY={0}>
              <Text color="blue" dimColor>
                Writing file: {toolArgs.path}
              </Text>
            </Box>
          );
        }
        return (
          <Box key={messageKey} marginY={0}>
            <Text color="blue" dimColor>
              Running {message.tool}...
            </Text>
          </Box>
        );

      case "tool_result":
        const result = message.result || {};
        // Silent Actor pattern: Show minimal feedback
        if (result.success) {
          // Show diff if available (for file edits)
          if (result.diff && result.filePath) {
            return (
              <Box key={messageKey} marginY={0} flexDirection="column">
                <Text color="green" dimColor>
                  {result.message || "Updated"}
                </Text>
                <DiffView
                  diff={result.diff}
                  added={result.added}
                  removed={result.removed}
                  filePath={result.filePath}
                />
              </Box>
            );
          }
          // Minimal success message
          return (
            <Box key={messageKey} marginY={0}>
              <Text color="green" dimColor>
                ✓ {result.message || "Completed"}
              </Text>
            </Box>
          );
        }
        // Show error (errors are important to see)
        return (
          <Box key={messageKey} marginY={0}>
            <Text color="red">✗ {result.message || result.error || "Failed"}</Text>
          </Box>
        );

      case "agent_stream":
        // Unified streaming display - parse XML and show formatted content
        const streamMessage = message as any;
        const streamState = streamMessage.state || "streaming";
        const isStreaming = streamState === "streaming";
        const isComplete = streamMessage.isComplete || streamState === "complete" || streamState === "done";
        const thought = streamMessage.thought;
        const rawContent = streamMessage.content || "";
        const toolCalls = streamMessage.toolCalls || [];
        
        // Parse XML content to extract formatted thought and hide raw XML
        let displayThought = thought;
        let displayContent = "";
        
        if (rawContent) {
          // Extract thought from raw content if not already extracted
          if (!displayThought) {
            const thoughtMatch = rawContent.match(/<thought>([\s\S]*?)<\/thought>/i);
            if (thoughtMatch) {
              displayThought = thoughtMatch[1].trim();
            }
          }
          
          // Extract content outside XML tags (should be minimal per our prompt)
          // But show tool calls as they're detected
          const withoutThought = rawContent.replace(/<thought>[\s\S]*?<\/thought>/gi, "").trim();
          const withoutToolCode = withoutThought.replace(/<tool_code>[\s\S]*?<\/tool_code>/gi, "").trim();
          displayContent = withoutToolCode;
        }
        
        // Don't render empty streams
        if (!displayThought && !displayContent && toolCalls.length === 0) {
          return null;
        }
        
        return (
          <Box key={messageKey} marginY={0} flexDirection="column">
            {displayThought && (
              <Box marginBottom={(displayContent || toolCalls.length > 0) ? 1 : 0} flexDirection="column">
                <Text color="magenta" bold>
                  Azul (thinking):
                </Text>
                <Text dimColor>{displayThought}</Text>
              </Box>
            )}
            {toolCalls.length > 0 && (
              <Box marginBottom={displayContent ? 1 : 0} flexDirection="column">
                <Text color="blue" bold>
                  Tools detected:
                </Text>
                {toolCalls.map((tc: any, idx: number) => (
                  <Text key={idx} color="blue" dimColor>
                    - {tc.name}
                  </Text>
                ))}
              </Box>
            )}
            {displayContent && (
              <Box flexDirection="column">
                <Text color="green" bold>
                  {isStreaming ? "Azul (streaming...)" : `Azul (${time}):`}
                </Text>
                <Text>{displayContent}</Text>
                {isStreaming && (
                  <Text color="cyan" dimColor>|</Text>
                )}
              </Box>
            )}
            {streamState === "tools_executing" && (
              <Box marginTop={1}>
                <Text color="yellow" dimColor>Executing tools...</Text>
              </Box>
            )}
          </Box>
        );

      case "token_stats":
        return (
          <Box key={messageKey} marginY={0}>
            {(() => {
              const stats = message.stats || {};
              const promptTokens =
                stats.promptTokens ??
                stats.contextTokens ??
                stats.inputTokens ??
                0;
              const inputTokens = stats.inputTokens ?? 0;
              const outputTokens = stats.outputTokens ?? 0;
              const tokensPerSecond = stats.tokensPerSecond ?? 0;
              const generationTime = stats.generationTimeMs ?? 0;
              const cumulativeTotal =
                stats.cumulativeTotalTokens ??
                (stats.totalInputTokens ?? 0) +
                  (stats.totalOutputTokens ?? 0);

              const parts: string[] = [
                `Ctx ${promptTokens} tok`,
                `In ${inputTokens} tok`,
                `Out ${outputTokens} tok`,
              ];

              if (tokensPerSecond > 0) {
                parts.push(`${tokensPerSecond.toFixed(1)} tok/s`);
              }

              if (generationTime > 0) {
                parts.push(`${generationTime} ms`);
              }

              if (cumulativeTotal > 0) {
                parts.push(`Σ ${cumulativeTotal} tok`);
              }

              return (
                <Text dimColor> {parts.join(" | ")}</Text>
              );
            })()}
          </Box>
        );

      case "error":
        return (
          <Box key={messageKey} marginY={0}>
            <Text color="red"> Error: {message.message}</Text>
          </Box>
        );

      case "system":
        return (
          <Box key={messageKey} marginY={0} flexDirection="column">
            <Text color="yellow" bold>
              System:
            </Text>
            <Text>{message.message}</Text>
          </Box>
        );

      case "mode_changed":
        return (
          <Box key={messageKey} marginY={0}>
            <Text color="cyan">
              Mode switched to: {message.mode === "api" ? "API" : "Local"}
            </Text>
          </Box>
        );

      case "provider_status":
        const status: ProviderStatusMessage = message.status;
        return (
          <Box key={messageKey} marginY={0} flexDirection="column">
            <Text color={status.mode === "api" ? "yellow" : "cyan"}>
              {status.fallback
                ? `Fallback to ${status.provider}${status.model ? ` (${status.model})` : ""}`
                : `Active provider: ${status.provider}${status.model ? ` (${status.model})` : ""}`}
            </Text>
            {status.fallback && status.reason && (
              <Text dimColor>Reason: {status.reason}</Text>
            )}
          </Box>
        );

      default:
        return (
          <Box key={messageKey} marginY={0}>
            <Text dimColor>[{message.type}]</Text>
          </Box>
        );
    }
  };

  return (
    <Box flexDirection="column" paddingX={1}>
      {messages.length === 0 ? (
        <Text dimColor>No messages yet. Type a message to start.</Text>
      ) : (
        messages.map((msg, idx) => renderMessage(msg, idx))
      )}
    </Box>
  );
};

