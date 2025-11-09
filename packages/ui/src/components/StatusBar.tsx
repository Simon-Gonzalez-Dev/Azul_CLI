import React from "react";
import { Box, Text } from "ink";
import { TokenStats } from "../types.js";

interface StatusBarProps {
  connected: boolean;
  modelName?: string;
  tokenStats: TokenStats;
}

export const StatusBar: React.FC<StatusBarProps> = ({ 
  connected, 
  modelName = "Qwen 2.5 Coder",
  tokenStats 
}) => {
  const formatTokens = (tokens: number): string => {
    if (tokens >= 1000000) {
      return `${(tokens / 1000000).toFixed(1)}M`;
    } else if (tokens >= 1000) {
      return `${(tokens / 1000).toFixed(1)}K`;
    }
    return tokens.toString();
  };

  const totalTokens = (tokenStats.totalInputTokens || 0) + (tokenStats.totalOutputTokens || 0);
  const tokensPerSec = tokenStats.tokensPerSecond || 0;

  return (
    <Box
      paddingX={1}
      borderStyle="round"
      borderColor={connected ? "green" : "red"}
      justifyContent="space-between"
    >
      <Box>
        <Text bold color="cyan">
          AZUL
        </Text>
        <Text dimColor> | AI Coding Assistant</Text>
      </Box>
      <Box>
        <Text dimColor>{modelName} | </Text>
        <Text dimColor>
          Tokens: {formatTokens(totalTokens)} | 
        </Text>
        {tokensPerSec > 0 && (
          <Text dimColor>
            {tokensPerSec.toFixed(1)} tok/s | 
          </Text>
        )}
        <Text color={connected ? "green" : "red"}>
          {connected ? "● Connected" : "○ Disconnected"}
        </Text>
      </Box>
    </Box>
  );
};

