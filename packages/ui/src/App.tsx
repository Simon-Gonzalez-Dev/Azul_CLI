import React, { useState, useEffect } from "react";
import { Box } from "ink";
import { LogView } from "./components/LogView.js";
import { UserInput } from "./components/UserInput.js";
import { StatusBar } from "./components/StatusBar.js";
import { PermissionModal } from "./components/PermissionModal.js";
import { Message, AppState, ApprovalRequest } from "./types.js";

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
  });

  const [mode, setMode] = useState<"local" | "api">(currentMode);

  useEffect(() => {
    // Register message handler
    onMessage((message: any) => {
      handleServerMessage(message);
    });

    // Send connected message
    handleServerMessage({
      type: "connected",
      message: "Connected to Azul server",
      timestamp: Date.now(),
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
    } else if (message.type === "agent_response_stream") {
      // Handle streaming response - update the last streaming message
      setState((prev) => {
        const newMessages = [...prev.messages];
        const lastStreamingIndex = newMessages.findIndex(
          (m, idx) => m.type === "agent_response_stream" && idx === newMessages.length - 1
        );

        if (lastStreamingIndex >= 0) {
          newMessages[lastStreamingIndex] = {
            ...newMessages[lastStreamingIndex],
            content: message.content,
            timestamp: Date.now(),
          };
        } else {
          newMessages.push({
            type: "agent_response_stream",
            content: message.content,
            timestamp: Date.now(),
          });
        }

        return { ...prev, messages: newMessages };
      });
    } else if (message.type === "agent_thinking") {
      // Clear thinking message if empty, otherwise add/update it
      if (!message.content) {
        setState((prev) => ({
          ...prev,
          messages: prev.messages.filter((m) => m.type !== "agent_thinking"),
        }));
      } else {
        setState((prev) => {
          const newMessages = [...prev.messages];
          const lastThinkingIndex = newMessages.findIndex(
            (m) => m.type === "agent_thinking"
          );

          if (lastThinkingIndex >= 0) {
            newMessages[lastThinkingIndex] = {
              ...newMessages[lastThinkingIndex],
              content: message.content,
              timestamp: Date.now(),
            };
          } else {
            newMessages.push({
              type: "agent_thinking",
              content: message.content,
              timestamp: Date.now(),
            });
          }

          return { ...prev, messages: newMessages };
        });
      }
    } else if (message.type === "mode_changed") {
      setMode(message.mode);
      setState((prev) => ({
        ...prev,
        messages: [
          ...prev.messages,
          {
            type: "system",
            message: `Switched to ${message.mode === "api" ? "API (OpenRouter)" : "Local LLM"} mode`,
            timestamp: Date.now(),
          },
        ],
      }));
    } else {
      // Replace streaming message with final response if it exists
      if (message.type === "agent_response") {
        setState((prev) => {
          const newMessages = prev.messages.filter(
            (m) => m.type !== "agent_response_stream"
          );
          newMessages.push({
            ...message,
            timestamp: Date.now(),
          });
          return { ...prev, messages: newMessages };
        });
      } else {
        setState((prev) => ({
          ...prev,
          messages: [
            ...prev.messages,
            { ...message, timestamp: Date.now() },
          ],
        }));
      }
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
          messages: prev.messages.filter((m) => m.type === "token_stats"), // Keep token stats
        }));
        handleServerMessage({
          type: "system",
          message: "Screen cleared.",
          timestamp: Date.now(),
        });
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
/api      - Switch to API mode (OpenRouter)
/local    - Switch to local LLM mode
/quit     - Exit the application

Current mode: ${mode === "api" ? "API (OpenRouter)" : "Local LLM"}

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
      <StatusBar connected={state.connected} tokenStats={state.tokenStats} mode={mode} />
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
