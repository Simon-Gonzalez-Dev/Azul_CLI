import React from "react";
import { Box, Text } from "ink";
import { Message } from "../types.js";
import chalk from "chalk";

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

      case "agent_thinking":
        return (
          <Box key={index} marginY={0}>
            <Text color="yellow">🤔 {message.content}</Text>
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
        return (
          <Box key={index} marginY={0}>
            <Text color="blue">
              🔧 Calling tool: {message.tool} with args{" "}
              {JSON.stringify(message.args)}
            </Text>
          </Box>
        );

      case "tool_result":
        return (
          <Box key={index} marginY={0} flexDirection="column">
            <Text color="blue">📋 Tool result from {message.tool}:</Text>
            <Text dimColor>{JSON.stringify(message.result, null, 2)}</Text>
          </Box>
        );

      case "agent_response":
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
            <Text dimColor>
              📊 Tokens: {message.stats.inputTokens} in, {message.stats.outputTokens} out 
              ({message.stats.tokensPerSecond.toFixed(1)} tok/s, {message.stats.generationTimeMs}ms)
            </Text>
          </Box>
        );

      case "error":
        return (
          <Box key={index} marginY={0}>
            <Text color="red">❌ Error: {message.message}</Text>
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

