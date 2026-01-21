import React from "react";
import { Box, Text } from "ink";
import { Message, ProviderStatusMessage, AgentMode, PlanStep } from "../types.js";
import { DiffView } from "./DiffView.js";

interface LogViewProps {
  messages: Message[];
  agentMode?: AgentMode;
}

export const LogView: React.FC<LogViewProps> = ({ messages, agentMode = 'normal' }) => {
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

      case "user_message":
        // New user message format with agent mode indicator
        const userAgentMode = (message as any).agentMode || 'normal';
        return (
          <Box key={messageKey} marginY={0} flexDirection="column">
            <Box>
              <Text color="cyan" bold>You</Text>
              {userAgentMode === 'plan' && (
                <Text color="magenta"> [plan]</Text>
              )}
              <Text dimColor> ({time})</Text>
            </Box>
            <Box paddingLeft={1}>
              <Text>{message.content}</Text>
            </Box>
          </Box>
        );

      case "user_bash":
        // Direct bash command from user ($ prefix)
        return (
          <Box key={messageKey} marginY={0} flexDirection="column">
            <Text color="green" bold>$ {(message as any).command}</Text>
          </Box>
        );

      case "bash_result":
        // Result from direct bash execution
        const bashResult = message as any;
        return (
          <Box key={messageKey} marginY={0} flexDirection="column">
            {bashResult.stdout && (
              <Box paddingLeft={1}>
                <Text>{bashResult.stdout}</Text>
              </Box>
            )}
            {bashResult.stderr && (
              <Box paddingLeft={1}>
                <Text color="red">{bashResult.stderr}</Text>
              </Box>
            )}
            {!bashResult.success && (
              <Text color="red">Command failed</Text>
            )}
          </Box>
        );

      case "plan_received":
        // Plan mode: show received plan steps
        const planSteps: PlanStep[] = (message as any).steps || [];
        return (
          <Box key={messageKey} marginY={0} flexDirection="column" borderStyle="single" borderColor="magenta" paddingX={1}>
            <Text color="magenta" bold>Plan Received:</Text>
            {planSteps.map((step, idx) => (
              <Box key={step.id} paddingLeft={1}>
                <Text color="white">
                  {idx + 1}. {step.description}
                </Text>
                {step.toolName && (
                  <Text dimColor> ({step.toolName})</Text>
                )}
              </Box>
            ))}
            <Text dimColor>Review and approve in the overlay below.</Text>
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
        const toolName = result.toolName || message.tool || "tool";
        const toolIndexInfo = message.totalTools > 1
          ? ` (${(message.toolIndex || 0) + 1}/${message.totalTools})`
          : "";

        // Show tool name context for all results
        if (result.success) {
          // Show diff if available (for file edits/writes)
          if (result.diff && result.filePath) {
            return (
              <Box key={messageKey} marginY={0} flexDirection="column">
                <Text color="green" dimColor>
                  ✓ {toolName}{toolIndexInfo}: {result.message || "Updated"}
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
          // Show content for bash/grep/view if available
          if (result.content && result.content.length > 0) {
            const contentLines = result.content.split('\n');
            const isLong = contentLines.length > 20;
            const displayContent = isLong
              ? contentLines.slice(0, 20).join('\n') + `\n... (${contentLines.length - 20} more lines)`
              : result.content;

            return (
              <Box key={messageKey} marginY={0} flexDirection="column">
                <Text color="green" dimColor>
                  ✓ {toolName}{toolIndexInfo}: {result.message || "Completed"}
                </Text>
                <Box borderStyle="single" borderColor="gray" paddingX={1} marginTop={0}>
                  <Text dimColor>{displayContent}</Text>
                </Box>
              </Box>
            );
          }
          // Minimal success message with tool name
          return (
            <Box key={messageKey} marginY={0}>
              <Text color="green" dimColor>
                ✓ {toolName}{toolIndexInfo}: {result.message || "Completed"}
              </Text>
            </Box>
          );
        }
        // Show error with tool name context
        return (
          <Box key={messageKey} marginY={0}>
            <Text color="red">✗ {toolName}{toolIndexInfo}: {result.message || result.error || "Failed"}</Text>
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
        
        // Show "Thinking..." even for empty streams if streaming
        const showThinkingIndicator = isStreaming && !displayThought && !displayContent && toolCalls.length === 0;

        // Don't render truly empty completed streams
        if (!displayThought && !displayContent && toolCalls.length === 0 && !isStreaming) {
          return null;
        }
        
        return (
          <Box key={messageKey} marginY={0} flexDirection="column">
            {/* Show thinking indicator even when no content yet */}
            {showThinkingIndicator && (
              <Box flexDirection="column">
                <Box>
                  <Text color="magenta" bold>Azul</Text>
                  <Text dimColor> (thinking...)</Text>
                  <Text color="cyan">▌</Text>
                </Box>
              </Box>
            )}
            {displayThought && (
              <Box marginBottom={(displayContent || toolCalls.length > 0) ? 1 : 0} flexDirection="column">
                <Box>
                  <Text color="magenta" bold>Azul</Text>
                  <Text dimColor> (thinking...)</Text>
                </Box>
                <Box paddingLeft={1}>
                  <Text dimColor italic>{displayThought}</Text>
                </Box>
              </Box>
            )}
            {toolCalls.length > 0 && (
              <Box marginBottom={displayContent ? 1 : 0} flexDirection="column">
                {toolCalls.map((tc: any, idx: number) => (
                  <Box key={idx}>
                    <Text color="blue">→ </Text>
                    <Text color="blue" dimColor>Running {tc.name}...</Text>
                  </Box>
                ))}
              </Box>
            )}
            {displayContent && (
              <Box flexDirection="column">
                <Box>
                  <Text color="cyanBright" bold>Azul</Text>
                  {isStreaming ? (
                    <Text dimColor> (streaming...)</Text>
                  ) : (
                    <Text dimColor> ({time})</Text>
                  )}
                </Box>
                <Box paddingLeft={1}>
                  <Text>{displayContent}</Text>
                  {isStreaming && (
                    <Text color="cyan">▌</Text>
                  )}
                </Box>
              </Box>
            )}
            {streamState === "tools_executing" && (
              <Box marginTop={1}>
                <Text color="yellow">⚙ </Text>
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

      case "task_complete":
        // Task completion message with checkmark
        return (
          <Box key={messageKey} marginY={1} paddingX={1}>
            <Text color="green" bold>✓ </Text>
            <Text color="green">{(message as any).summary || "Task complete."}</Text>
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
          <Box key={messageKey} marginY={0}>
            <Text color="cyan">
              Active provider: {status.provider}{status.model ? ` (${status.model})` : ""}
            </Text>
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

