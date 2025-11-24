import React from "react";
import { Box, Text } from "ink";
import { TokenStats } from "../types.js";

interface StatusBarProps {
  connected: boolean;
  modelName?: string;
  tokenStats: TokenStats;
  mode?: "local" | "api";
}

export const StatusBar: React.FC<StatusBarProps> = ({
  connected,
  modelName = "Qwen 2.5 Coder",
  tokenStats,
  mode = "local",
}) => {
  const formatTokens = (tokens: number): string => {
    if (tokens >= 1_000_000) {
      return `${(tokens / 1_000_000).toFixed(1)}M`;
    }
    if (tokens >= 1_000) {
      return `${(tokens / 1_000).toFixed(1)}K`;
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

  const modeLabel =
    mode === "api" ? "API • Groq" : `Local • ${modelName}`;

  return (
    <Box
      width="100%"
      paddingX={1}
      paddingY={1}
      borderStyle="round"
      borderColor={connected ? "cyan" : "gray"}
      flexDirection="column"
    >
      <Box justifyContent="space-between" width="100%">
        <Text>
          <Text color="cyanBright" bold>
            AZUL
          </Text>
          <Text dimColor> · Autonomous Coding Partner</Text>
        </Text>
        <Text color={connected ? "green" : "red"}>
          {connected ? "● ONLINE" : "○ OFFLINE"}
        </Text>
      </Box>
      <Box justifyContent="space-between" width="100%" marginTop={1}>
        <Text color={mode === "api" ? "yellow" : "cyan"}>
          {modeLabel}
        </Text>
        <Text dimColor>
          ctx {formattedPromptTokens} · in {formattedInputTokens} · out{" "}
          {formattedOutputTokens} · Σ {formattedCumulative}
          {tokensPerSec > 0 ? ` · ${tokensPerSec.toFixed(1)} tokens/s` : ""}
        </Text>
      </Box>
    </Box>
  );
};

