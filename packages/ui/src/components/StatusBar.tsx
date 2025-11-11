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

  const promptTokens = tokenStats.promptTokens ?? 0;
  const inputTokens = tokenStats.inputTokens ?? 0;
  const outputTokens = tokenStats.outputTokens ?? 0;
  const cumulativeInput =
    tokenStats.cumulativeInputTokens ?? tokenStats.totalInputTokens ?? 0;
  const cumulativeOutput =
    tokenStats.cumulativeOutputTokens ?? tokenStats.totalOutputTokens ?? 0;
  const cumulativeTotal =
    tokenStats.cumulativeTotalTokens ?? cumulativeInput + cumulativeOutput;

  const formattedPromptTokens = formatTokens(promptTokens);
  const formattedInputTokens = formatTokens(inputTokens);
  const formattedOutputTokens = formatTokens(outputTokens);
  const formattedCumulative = formatTokens(cumulativeTotal);

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
          Ctx: {formattedPromptTokens} | In: {formattedInputTokens} | Out: {formattedOutputTokens} | Σ: {formattedCumulative} | 
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

