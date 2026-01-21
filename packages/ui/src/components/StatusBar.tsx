import React from "react";
import { Box, Text } from "ink";
import { TokenStats, ProviderStatusMessage, ContextStats, AgentMode } from "../types.js";

interface StatusBarProps {
  connected: boolean;
  modelName?: string;
  tokenStats: TokenStats;
  providerStatus?: ProviderStatusMessage;
  contextStats?: ContextStats;
  agentMode?: AgentMode;
}

export const StatusBar: React.FC<StatusBarProps> = ({
  connected,
  modelName = "Local Model",
  tokenStats,
  providerStatus,
  contextStats,
  agentMode = 'normal',
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

  // Context bar visual
  const renderContextBar = (usagePercent: number): string => {
    const barWidth = 10;
    const filled = Math.round((usagePercent / 100) * barWidth);
    const empty = barWidth - filled;
    return "█".repeat(filled) + "░".repeat(empty);
  };

  // Context bar color based on usage
  const getContextColor = (usagePercent: number): string => {
    if (usagePercent < 60) return "green";
    if (usagePercent < 80) return "yellow";
    return "red";
  };

  const tokensPerSec = tokenStats.tokensPerSecond || 0;

  // Context stats
  const ctxUsage = contextStats?.usagePercent ?? 0;
  const ctxEstimated = contextStats?.estimatedTokens ?? 0;
  const ctxMax = contextStats?.maxTokens ?? 32000;

  // Provider info
  const providerName = providerStatus?.provider || "Local";
  const modelDisplayName = providerStatus?.model || modelName;

  // Mode badge colors
  const modeBadgeColor = agentMode === 'plan' ? 'magenta' : 'cyan';
  const modeBadgeText = agentMode === 'plan' ? 'PLAN' : 'NORMAL';

  return (
    <Box
      width="100%"
      paddingX={1}
      paddingY={0}
      borderStyle="round"
      borderColor={connected ? "cyan" : "gray"}
      flexDirection="column"
    >
      {/* Top row: Branding + Mode + Status */}
      <Box justifyContent="space-between" width="100%">
        <Box>
          <Text color="cyanBright" bold>
            AZUL
          </Text>
          <Text dimColor> • Autonomous Coding Agent</Text>
        </Box>
        <Box>
          {/* Mode badge */}
          <Text backgroundColor={modeBadgeColor} color="white" bold>
            {` ${modeBadgeText} `}
          </Text>
          <Text> </Text>
          {/* Connection status */}
          <Text color={connected ? "green" : "red"}>
            {connected ? "●" : "○"}
          </Text>
        </Box>
      </Box>

      {/* Bottom row: Provider + Context */}
      <Box justifyContent="space-between" width="100%" marginTop={0}>
        <Text dimColor>
          {providerName} • {modelDisplayName}
        </Text>
        <Box>
          {/* Context usage bar */}
          {contextStats && (
            <Text>
              <Text dimColor>Ctx: </Text>
              <Text color={getContextColor(ctxUsage)}>
                {renderContextBar(ctxUsage)}
              </Text>
              <Text dimColor>
                {" "}{ctxUsage}%
              </Text>
            </Text>
          )}
          {/* Tokens per second */}
          {tokensPerSec > 0 && (
            <Text dimColor>
              {" "}• {tokensPerSec.toFixed(1)} tok/s
            </Text>
          )}
        </Box>
      </Box>
    </Box>
  );
};
