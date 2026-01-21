import React from "react";
import { Box, Text } from "ink";
import { TokenStats, ProviderStatusMessage, ContextStats, AgentMode } from "../types.js";

type AgentStatus = 'IDLE' | 'THINKING' | 'STREAMING' | 'EXECUTING_TOOL' | 'AWAITING_APPROVAL' | 'COMPLETE';

interface StatusBarProps {
  connected: boolean;
  modelName?: string;
  tokenStats: TokenStats;
  providerStatus?: ProviderStatusMessage;
  contextStats?: ContextStats;
  agentMode?: AgentMode;
  agentStatus?: AgentStatus;
  currentToolName?: string;
  currentToolIndex?: number;
  totalTools?: number;
}

export const StatusBar: React.FC<StatusBarProps> = ({
  connected,
  modelName = "Local Model",
  tokenStats,
  providerStatus,
  contextStats,
  agentMode = 'normal',
  agentStatus = 'IDLE',
  currentToolName,
  currentToolIndex = 0,
  totalTools = 0,
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

  // Agent status display
  const getStatusDisplay = () => {
    switch (agentStatus) {
      case 'THINKING':
        return { text: 'Thinking...', color: 'yellow' };
      case 'STREAMING':
        return { text: 'Streaming...', color: 'cyan' };
      case 'EXECUTING_TOOL':
        const toolInfo = totalTools > 1
          ? `${currentToolName} (${currentToolIndex + 1}/${totalTools})`
          : currentToolName || 'tool';
        return { text: `Running ${toolInfo}`, color: 'blue' };
      case 'AWAITING_APPROVAL':
        return { text: `Approval: ${currentToolName}`, color: 'yellow' };
      case 'COMPLETE':
        return { text: 'Complete', color: 'green' };
      default:
        return { text: 'Ready', color: 'gray' };
    }
  };

  const statusDisplay = getStatusDisplay();

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

      {/* Bottom row: Provider + Status + Context */}
      <Box justifyContent="space-between" width="100%" marginTop={0}>
        <Box>
          <Text dimColor>
            {providerName} • {modelDisplayName}
          </Text>
          {agentStatus !== 'IDLE' && (
            <Text>
              <Text dimColor> • </Text>
              <Text color={statusDisplay.color as any}>{statusDisplay.text}</Text>
            </Text>
          )}
        </Box>
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
