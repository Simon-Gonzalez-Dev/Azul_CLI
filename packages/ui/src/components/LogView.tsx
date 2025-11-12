import React from "react";
import { Box, Text } from "ink";
import { Message } from "../types.js";
import chalk from "chalk";
import { DiffView } from "./DiffView.js";

interface LogViewProps {
  messages: Message[];
}

export const LogView: React.FC<LogViewProps> = ({ messages }) => {
  const renderMessage = (message: Message, index: number) => {
    const time = new Date(message.timestamp).toLocaleTimeString();

    switch (message.type) {
      case "connected":
        return (
          <Box key={index} marginY={0}>
            <Text color="green">✓ {message.message}</Text>
          </Box>
        );

      case "user_message_received":
        return (
          <Box key={index} marginY={0} flexDirection="column">
            <Text color="cyan" bold>
              You ({time}):
            </Text>
            <Text>{message.content}</Text>
          </Box>
        );

      case "agent_thought":
        return (
          <Box key={index} marginY={0} flexDirection="column">
            <Text color="magenta" bold>
              Azul (thinking):
            </Text>
            <Text dimColor>{message.content}</Text>
          </Box>
        );

      case "tool_call":
        const toolArgs = message.args || {};
        // Special formatting for write_file tool
        if (message.tool === "write_file" && toolArgs.path) {
          return (
            <Box key={index} marginY={0} flexDirection="column">
              <Text color="blue" bold>
                Writing file: {toolArgs.path}
              </Text>
              <Text dimColor>
                Content length: {toolArgs.content?.length || 0} characters
              </Text>
            </Box>
          );
        }
        return (
          <Box key={index} marginY={0}>
            <Text color="blue">
               Calling tool: {message.tool}
            </Text>
            {Object.keys(toolArgs).length > 0 && (
              <Text dimColor> {JSON.stringify(toolArgs, null, 2)}</Text>
            )}
          </Box>
        );

      case "tool_result":
        const result = message.result || {};
        // Show diff if available (file write/update)
        if (result.diff && result.success) {
          return (
            <Box key={index} marginY={0} flexDirection="column">
              <Text color="green" bold>
                ✓ {result.message || "Tool executed successfully"}
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
        // Show success/error message
        if (result.success) {
          return (
            <Box key={index} marginY={0}>
              <Text color="green">✓ {result.message || JSON.stringify(result)}</Text>
            </Box>
          );
        }
        return (
          <Box key={index} marginY={0} flexDirection="column">
            <Text color="red">✗ Error: {result.error || JSON.stringify(result)}</Text>
          </Box>
        );

      case "agent_response":
      case "agent_response_stream":
        return (
          <Box key={index} marginY={0} flexDirection="column">
            <Text color="green" bold>
              Azul ({time}):
            </Text>
            <Text>{message.content}</Text>
          </Box>
        );

      case "token_stats":
        return (
          <Box key={index} marginY={0}>
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
          <Box key={index} marginY={0}>
            <Text color="red"> Error: {message.message}</Text>
          </Box>
        );

      default:
        return (
          <Box key={index} marginY={0}>
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

