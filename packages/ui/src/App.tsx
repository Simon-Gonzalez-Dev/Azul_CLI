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
}

export const App: React.FC<AppProps> = ({ onUserInput, onApproval, onMessage }) => {
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

    if (text.toLowerCase().trim() === "exit" || text.toLowerCase().trim() === "quit") {
      process.exit(0);
      return;
    }

    onUserInput(text);
  };

  const handleApproval = (approved: boolean) => {
    if (!state.pendingApproval) return;

    onApproval(state.pendingApproval.requestId, approved);
    setState((prev) => ({ ...prev, pendingApproval: null }));
  };

  return (
    <Box flexDirection="column" height="100%">
      <StatusBar connected={state.connected} tokenStats={state.tokenStats} />
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
