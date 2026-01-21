import React, { useState, useEffect, useCallback } from "react";
import { Box } from "ink";
import { LogView } from "./components/LogView.js";
import { UserInput } from "./components/UserInput.js";
import { StatusBar } from "./components/StatusBar.js";
import { PermissionModal } from "./components/PermissionModal.js";
import { Banner } from "./components/Banner.js";
import { PlanModeOverlay } from "./components/PlanModeOverlay.js";
import {
  Message,
  AppState,
  ApprovalRequest,
  ProviderStatusMessage,
  ContextStats,
  AgentMode,
  InputMode,
  PlanStep,
  RECENT_BASH_COMMANDS,
} from "./types.js";

export interface AppProps {
  onUserInput: (text: string, agentMode?: AgentMode) => void;
  onApproval: (requestId: string, approved: boolean) => void;
  onMessage: (handler: (message: any) => void) => void;
  onReset: () => void;
  onChangeDirectory: (path: string) => void;
  onListDirectory: (path?: string) => void;
  onBashCommand?: (command: string) => void;
  onExecutePlan?: (planId: string) => void;
  onCancelPlan?: () => void;
}

export const App: React.FC<AppProps> = ({
  onUserInput,
  onApproval,
  onMessage,
  onReset,
  onChangeDirectory,
  onListDirectory,
  onBashCommand,
  onExecutePlan,
  onCancelPlan,
}) => {
  const [state, setState] = useState<AppState>({
    messages: [],
    connected: true,
    userInput: "",
    pendingApproval: null,
    tokenStats: {
      inputTokens: 0,
      outputTokens: 0,
      totalTokens: 0,
      tokensPerSecond: 0,
      generationTimeMs: 0,
      totalInputTokens: 0,
      totalOutputTokens: 0,
    },
    providerStatus: undefined,
    contextStats: undefined,
    // New mode state
    inputMode: 'chat',
    agentMode: 'normal',
    planSteps: null,
    pendingPlan: false,
  });

  useEffect(() => {
    // Clear all messages on mount - start fresh
    setState((prev) => ({
      ...prev,
      messages: [],
      tokenStats: {
        inputTokens: 0,
        outputTokens: 0,
        totalTokens: 0,
        tokensPerSecond: 0,
        generationTimeMs: 0,
        totalInputTokens: 0,
        totalOutputTokens: 0,
      },
    }));

    // Register message handler
    onMessage((message: any) => {
      handleServerMessage(message);
    });
  }, []);

  // Toggle agent mode (Normal <-> Plan)
  const toggleAgentMode = useCallback(() => {
    setState((prev) => {
      const newMode: AgentMode = prev.agentMode === 'normal' ? 'plan' : 'normal';

      // Show system message about mode change
      const modeMessage: Message = {
        type: "system",
        message: newMode === 'plan'
          ? "Switched to PLAN mode. Agent will show plans before executing."
          : "Switched to NORMAL mode. Agent will execute immediately.",
        timestamp: Date.now(),
      };

      return {
        ...prev,
        agentMode: newMode,
        messages: [...prev.messages, modeMessage],
        // Clear pending plan when switching modes
        planSteps: newMode === 'normal' ? null : prev.planSteps,
        pendingPlan: false,
      };
    });
  }, []);

  // Update input mode based on text
  const updateInputMode = useCallback((text: string) => {
    let newMode: InputMode = 'chat';
    if (text.startsWith('$')) {
      newMode = 'bash';
    } else if (text.startsWith('/')) {
      newMode = 'command';
    }

    setState((prev) => {
      if (prev.inputMode !== newMode) {
        return { ...prev, inputMode: newMode };
      }
      return prev;
    });
  }, []);

  const handleServerMessage = (message: any) => {
    if (message.type === "approval_request") {
      setState((prev) => ({
        ...prev,
        pendingApproval: {
          requestId: message.requestId,
          tool: message.tool,
          args: message.args,
          diff: message.diff,
          added: message.added,
          removed: message.removed,
        },
      }));
    } else if (message.type === "token_stats") {
      const timestamp = Date.now();
      setState((prev) => ({
        ...prev,
        tokenStats: message.stats,
        messages: [
          ...prev.messages.filter((m) => m.type !== "token_stats"),
          {
            type: "token_stats",
            stats: message.stats,
            timestamp,
          },
        ],
      }));
    } else if (message.type === "agent_stream") {
      // Unified streaming message handler
      setState((prev) => {
        const streamId = message.streamId;
        const newMessages = [...prev.messages];

        // Find existing stream by streamId
        let streamingIndex = -1;
        for (let i = newMessages.length - 1; i >= 0; i--) {
          if (newMessages[i].type === "agent_stream" && newMessages[i].streamId === streamId) {
            streamingIndex = i;
            break;
          }
        }

        // Don't add empty streams
        const hasContent = message.thought || (message.content && message.content.trim()) || (message.toolCalls && message.toolCalls.length > 0);
        if (!hasContent && !message.isComplete) {
          return prev;
        }

        if (streamingIndex >= 0) {
          // Update existing stream
          newMessages[streamingIndex] = {
            ...newMessages[streamingIndex],
            ...message,
            timestamp: newMessages[streamingIndex].timestamp || Date.now(),
          };
        } else {
          // Create new stream
          newMessages.push({
            ...message,
            timestamp: Date.now(),
          });
        }

        // Update token stats if provided
        const updatedState: Partial<AppState> = { messages: newMessages };
        if (message.stats) {
          updatedState.tokenStats = message.stats;
        }

        return { ...prev, ...updatedState };
      });
    } else if (message.type === "plan_response") {
      // Handle plan mode response from agent
      setState((prev) => ({
        ...prev,
        planSteps: message.steps || [],
        pendingPlan: true,
        messages: [
          ...prev.messages,
          {
            type: "plan_received",
            steps: message.steps,
            timestamp: Date.now(),
          },
        ],
      }));
    } else if (message.type === "plan_step_update") {
      // Update a specific plan step status
      setState((prev) => {
        if (!prev.planSteps) return prev;

        const updatedSteps = prev.planSteps.map((step) =>
          step.id === message.stepId
            ? { ...step, status: message.status, result: message.result, error: message.error }
            : step
        );

        return { ...prev, planSteps: updatedSteps };
      });
    } else if (message.type === "plan_complete") {
      // Plan execution finished
      setState((prev) => ({
        ...prev,
        pendingPlan: false,
        messages: [
          ...prev.messages,
          {
            type: "system",
            message: message.success
              ? "Plan executed successfully."
              : `Plan execution failed: ${message.error}`,
            timestamp: Date.now(),
          },
        ],
      }));
    } else if (message.type === "bash_result") {
      // Direct bash command result
      setState((prev) => ({
        ...prev,
        messages: [
          ...prev.messages,
          {
            type: "bash_result",
            command: message.command,
            stdout: message.stdout,
            stderr: message.stderr,
            success: message.success,
            timestamp: Date.now(),
          },
        ],
      }));
    } else if (message.type === "provider_status") {
      const providerStatus: ProviderStatusMessage = message.status;
      setState((prev) => ({
        ...prev,
        providerStatus,
        messages: [
          ...prev.messages,
          {
            type: "provider_status",
            status: providerStatus,
            timestamp: Date.now(),
          },
        ],
      }));
    } else if (message.type === "context_stats") {
      // Update context stats for StatusBar display
      setState((prev) => ({
        ...prev,
        contextStats: message.stats,
      }));
    } else {
      // All other messages
      setState((prev) => ({
        ...prev,
        messages: [
          ...prev.messages,
          { ...message, timestamp: Date.now() },
        ],
      }));
    }
  };

  const handleUserSubmit = (text: string) => {
    if (!state.connected) return;

    const trimmedText = text.trim();
    if (!trimmedText) return;

    // === BASH MODE: Direct execution ===
    if (trimmedText.startsWith("$")) {
      const command = trimmedText.slice(1).trim();
      if (!command) return;

      // Add to recent commands
      if (!RECENT_BASH_COMMANDS.includes(command)) {
        RECENT_BASH_COMMANDS.unshift(command);
        if (RECENT_BASH_COMMANDS.length > 10) {
          RECENT_BASH_COMMANDS.pop();
        }
      }

      // Show user's bash command
      setState((prev) => ({
        ...prev,
        messages: [
          ...prev.messages,
          {
            type: "user_bash",
            command,
            timestamp: Date.now(),
          },
        ],
      }));

      // Execute directly (bypasses agent)
      if (onBashCommand) {
        onBashCommand(command);
      } else {
        // Fallback: send as regular input with bash indicator
        onUserInput(`[BASH] ${command}`, state.agentMode);
      }
      return;
    }

    // === COMMAND MODE: Slash commands ===
    if (trimmedText.startsWith("/")) {
      const lowerText = trimmedText.toLowerCase();
      const parts = trimmedText.slice(1).split(" ");
      const command = parts[0].toLowerCase();
      const args = parts.slice(1).join(" ");

      if (command === "quit") {
        process.exit(0);
        return;
      }

      if (command === "reset") {
        onReset();
        handleServerMessage({
          type: "system",
          message: "Agent memory reset. Conversation context cleared.",
          timestamp: Date.now(),
        });
        return;
      }

      if (command === "clear") {
        setState((prev) => ({
          ...prev,
          messages: [],
        }));
        return;
      }

      if (command === "cd") {
        if (!args) {
          handleServerMessage({
            type: "error",
            message: "cd: missing directory argument. Usage: /cd <directory>",
            timestamp: Date.now(),
          });
        } else {
          onChangeDirectory(args);
        }
        return;
      }

      if (command === "ls") {
        onListDirectory(args || undefined);
        return;
      }

      if (command === "plan") {
        toggleAgentMode();
        return;
      }

      if (command === "config") {
        handleServerMessage({
          type: "system",
          message: `Current Configuration:
Mode: ${state.agentMode.toUpperCase()}
Provider: ${state.providerStatus?.provider || 'Local'}
Model: ${state.providerStatus?.model || 'Unknown'}
Context: ${state.contextStats?.usagePercent || 0}% used`,
          timestamp: Date.now(),
        });
        return;
      }

      if (command === "help") {
        handleServerMessage({
          type: "system",
          message: `Available Commands:
/help     - Show this help message
/reset    - Reset agent memory/context
/clear    - Clear the screen
/cd <dir> - Change directory
/ls [dir] - List directory contents
/plan     - Toggle plan mode (Shift+Tab)
/config   - Show configuration
/quit     - Exit the application

Input Modes:
$command  - Execute bash command directly
/command  - Slash commands
text      - Chat with agent

Keyboard:
Shift+Tab - Toggle Normal/Plan mode
Tab       - Cycle suggestions
Escape    - Clear input`,
          timestamp: Date.now(),
        });
        return;
      }

      // Unknown command
      handleServerMessage({
        type: "error",
        message: `Unknown command: ${trimmedText}. Type /help for available commands.`,
        timestamp: Date.now(),
      });
      return;
    }

    // === CHAT MODE: Send to agent ===
    // Show user's message
    setState((prev) => ({
      ...prev,
      messages: [
        ...prev.messages,
        {
          type: "user_message",
          content: trimmedText,
          agentMode: state.agentMode,
          timestamp: Date.now(),
        },
      ],
    }));

    // Send to agent with current mode
    onUserInput(trimmedText, state.agentMode);
  };

  const handleApproval = (approved: boolean) => {
    if (!state.pendingApproval) return;

    onApproval(state.pendingApproval.requestId, approved);
    setState((prev) => ({ ...prev, pendingApproval: null }));
  };

  // Handle plan actions
  const handleExecutePlan = () => {
    if (state.planSteps && onExecutePlan) {
      onExecutePlan(state.planSteps[0]?.id || 'plan');
    }
  };

  const handleCancelPlan = () => {
    setState((prev) => ({
      ...prev,
      planSteps: null,
      pendingPlan: false,
    }));
    if (onCancelPlan) {
      onCancelPlan();
    }
  };

  return (
    <Box flexDirection="column" height="100%">
      <Banner />
      <StatusBar
        connected={state.connected}
        tokenStats={state.tokenStats}
        providerStatus={state.providerStatus}
        contextStats={state.contextStats}
        agentMode={state.agentMode}
      />
      <Box flexDirection="column" flexGrow={1} paddingY={1}>
        <LogView
          messages={state.messages}
          agentMode={state.agentMode}
        />
      </Box>
      {state.pendingApproval ? (
        <PermissionModal
          approval={state.pendingApproval}
          onApprove={handleApproval}
        />
      ) : state.pendingPlan && state.planSteps && state.planSteps.length > 0 ? (
        <PlanModeOverlay
          steps={state.planSteps}
          onExecute={handleExecutePlan}
          onCancel={handleCancelPlan}
        />
      ) : (
        <UserInput
          onSubmit={handleUserSubmit}
          onInputChange={updateInputMode}
          onModeToggle={toggleAgentMode}
          disabled={!state.connected}
          agentMode={state.agentMode}
          inputMode={state.inputMode}
        />
      )}
    </Box>
  );
};
