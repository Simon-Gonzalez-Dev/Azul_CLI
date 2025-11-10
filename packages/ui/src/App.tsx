import React, { useState, useEffect } from "react";
import { Box } from "ink";
import { Agent } from "../../server/dist/agent.js";
import { LogView } from "./components/LogView.js";
import { UserInput } from "./components/UserInput.js";
import { StatusBar } from "./components/StatusBar.js";
import { PermissionModal } from "./components/PermissionModal.js";
import { Message, AppState, ApprovalRequest } from "./types.js";

interface AppProps {
  agent: Agent;
  setMessageHandler: (handler: (message: any) => void) => void;
}

export const App: React.FC<AppProps> = ({ agent, setMessageHandler }) => {
  const [state, setState] = useState<AppState>({
    messages: [],
    connected: true, // Always connected since it's direct
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
    // Set up message handler for agent to send messages to UI
    const handleMessage = (message: any) => {
      if (message.type === "approval_request") {
        setState((prev) => {
          if (prev.pendingApproval) {
            console.warn(`Received new approval request (${message.requestId}) while one is already pending. Ignoring.`);
            return prev;
          }
          return {
            ...prev,
            pendingApproval: {
              requestId: message.requestId,
              tool: message.tool,
              args: message.args,
            },
          };
        });
      } else if (message.type === "token_stats") {
        setState((prev) => ({
          ...prev,
          tokenStats: message.stats,
        }));
      } else {
        if (message.type === "tool_result" || message.type === "tool_call") {
          setState((prev) => {
            if (prev.pendingApproval) {
              console.log(`Clearing pending approval (${prev.pendingApproval.requestId}) due to ${message.type}`);
            }
            return {
              ...prev,
              pendingApproval: null,
              messages: [
                ...prev.messages,
                { ...message, timestamp: Date.now() },
              ],
            };
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

    // Register the message handler
    setMessageHandler(handleMessage);
  }, [agent, setMessageHandler]);

  const handleUserSubmit = (text: string) => {
    if (text.toLowerCase().trim() === "exit" || text.toLowerCase().trim() === "quit") {
      process.exit(0);
      return;
    }

    // Directly call agent method
    agent.handleUserMessage(text);
  };

  const handleApproval = (approved: boolean) => {
    if (!state.pendingApproval) {
      console.warn("Attempted to approve but no pending approval exists");
      return;
    }

    // Directly call agent method
    agent.handleApproval(state.pendingApproval.requestId, approved);
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
