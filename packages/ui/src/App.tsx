import React, { useState, useEffect } from "react";
import { Box } from "ink";
import { LogView } from "./components/LogView.js";
import { UserInput } from "./components/UserInput.js";
import { StatusBar } from "./components/StatusBar.js";
import { PermissionModal } from "./components/PermissionModal.js";
import { Banner } from "./components/Banner.js";
import { Message, AppState, ApprovalRequest, ProviderStatusMessage } from "./types.js";

export interface AppProps {
  onUserInput: (text: string) => void;
  onApproval: (requestId: string, approved: boolean) => void;
  onMessage: (handler: (message: any) => void) => void;
  onReset: () => void;
  onSwitchMode: (mode: "local" | "api") => void;
  onChangeDirectory: (path: string) => void;
  onListDirectory: (path?: string) => void;
  currentMode?: "local" | "api";
}

export const App: React.FC<AppProps> = ({ onUserInput, onApproval, onMessage, onReset, onSwitchMode, onChangeDirectory, onListDirectory, currentMode = "local" }) => {
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
    providerStatusApi: undefined,
    providerStatusLocal: undefined,
  });

  const [mode, setMode] = useState<"local" | "api">(currentMode);

  useEffect(() => {
    // Clear all messages on mount - start fresh with only banner
    // This ensures clean state even if component remounts
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // onMessage is stable, handleServerMessage is defined in component

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
      // Unified streaming message handler - single source of truth
      setState((prev) => {
        const streamId = message.streamId;
        const newMessages = [...prev.messages];
        
        // Find existing stream by streamId (O(1) lookup potential with map, but array is fine for now)
        let streamingIndex = -1;
        for (let i = newMessages.length - 1; i >= 0; i--) {
          if (newMessages[i].type === "agent_stream" && newMessages[i].streamId === streamId) {
            streamingIndex = i;
            break;
          }
        }

        // Don't add empty streams (filter in state management, not render)
        const hasContent = message.thought || (message.content && message.content.trim()) || (message.toolCalls && message.toolCalls.length > 0);
        if (!hasContent && !message.isComplete) {
          return prev; // Skip empty non-complete streams
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
    } else if (message.type === "token_stats") {
      // Token stats can come separately or integrated in stream
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
    } else if (message.type === "mode_changed") {
      setMode(message.mode);
      setState((prev) => ({
        ...prev,
        messages: [
          ...prev.messages,
          {
            type: "system",
            message: `Switched to ${message.mode === "api" ? "API" : "Local"} mode`,
            timestamp: Date.now(),
          },
        ],
      }));
    } else if (message.type === "provider_status") {
      const providerStatus: ProviderStatusMessage = message.status;
      setState((prev) => ({
        ...prev,
        providerStatusApi:
          providerStatus.mode === "api" ? providerStatus : prev.providerStatusApi,
        providerStatusLocal:
          providerStatus.mode === "local" ? providerStatus : prev.providerStatusLocal,
        messages: [
          ...prev.messages,
          {
            type: "provider_status",
            status: providerStatus,
            timestamp: Date.now(),
          },
        ],
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
    const lowerText = trimmedText.toLowerCase();

    // Handle commands (must start with /)
    if (trimmedText.startsWith("/")) {
      const command = lowerText.slice(1).split(" ")[0]; // Get command name (before any args)
      
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
        // Don't clear UI messages - only reset agent memory
        return;
      }
      
      if (command === "clear") {
        setState((prev) => ({
          ...prev,
          messages: [], // Clear all messages including token stats
        }));
        // Don't send system message - just clear silently
        return;
      }
      
      if (command === "api") {
        onSwitchMode("api");
        return;
      }
      
      if (command === "local") {
        onSwitchMode("local");
        return;
      }
      
      if (command === "cd") {
        const args = trimmedText.slice(4).trim(); // Remove "/cd " prefix
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
        const args = trimmedText.slice(3).trim(); // Remove "/ls " prefix
        onListDirectory(args || undefined);
        return;
      }
      
      if (command === "help") {
        handleServerMessage({
          type: "system",
          message: `Available Commands:
/help     - Show this help message
/reset    - Reset agent memory/context (keeps screen)
/clear    - Clear the screen (keeps memory)
/cd <dir> - Change directory (e.g., /cd /path/to/dir or /cd ..)
/ls [dir] - List directory contents (e.g., /ls or /ls /path)
/api      - Switch to API mode (HF -> Gemini -> Groq -> OpenRouter)
/local    - Switch to local LLM mode
/quit     - Exit the application

Current mode: ${mode === "api" ? "API (cloud cascade)" : "Local LLM"}

All commands must start with /. Type / and press Tab to see available commands.`,
          timestamp: Date.now(),
        });
        return;
      }
      
      // Unknown command - show error
      handleServerMessage({
        type: "error",
        message: `Unknown command: ${trimmedText}. Type /help for available commands.`,
        timestamp: Date.now(),
      });
      return;
    }

    // All commands must use / prefix - no exceptions
    // Regular input - send to agent
    onUserInput(text);
  };

  const handleApproval = (approved: boolean) => {
    if (!state.pendingApproval) return;

    onApproval(state.pendingApproval.requestId, approved);
    setState((prev) => ({ ...prev, pendingApproval: null }));
  };

  return (
    <Box flexDirection="column" height="100%">
      <Banner />
      <StatusBar
        connected={state.connected}
        tokenStats={state.tokenStats}
        mode={mode}
        providerStatus={mode === "api" ? state.providerStatusApi : state.providerStatusLocal}
      />
      <Box flexDirection="column" flexGrow={1} paddingY={1}>
        <LogView messages={state.messages} />
      </Box>
      {state.pendingApproval ? (
        <PermissionModal
          approval={state.pendingApproval}
          onApprove={handleApproval}
        />
      ) : (
        <UserInput
          onSubmit={handleUserSubmit}
          disabled={!state.connected}
        />
      )}
    </Box>
  );
};
