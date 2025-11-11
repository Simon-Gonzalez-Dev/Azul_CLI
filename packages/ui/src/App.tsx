import React, { useState, useEffect } from "react";
import { Box } from "ink";
import { WebSocket } from "ws";
import { LogView } from "./components/LogView.js";
import { UserInput } from "./components/UserInput.js";
import { StatusBar } from "./components/StatusBar.js";
import { PermissionModal } from "./components/PermissionModal.js";
import { Message, AppState, ApprovalRequest } from "./types.js";

interface AppProps {
  ws: WebSocket;
}

export const App: React.FC<AppProps> = ({ ws }) => {
  const [state, setState] = useState<AppState>({
    messages: [],
    connected: false,
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
    ws.on("open", () => {
      setState((prev) => ({ ...prev, connected: true }));
    });

    ws.on("message", (data: Buffer) => {
      try {
        const message = JSON.parse(data.toString());
        handleServerMessage(message);
      } catch (error) {
        console.error("Error parsing message:", error);
      }
    });

    ws.on("close", () => {
      setState((prev) => ({ ...prev, connected: false }));
    });

    ws.on("error", (error) => {
      console.error("WebSocket error:", error);
    });

    return () => {
      ws.removeAllListeners();
    };
  }, [ws]);

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
          ...prev.messages,
          {
            type: "token_stats",
            stats: message.stats,
            timestamp,
          },
        ],
      }));
    } else {
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

    // Handle exit command
    if (text.toLowerCase().trim() === "exit" || text.toLowerCase().trim() === "quit") {
      ws.close();
      process.exit(0);
      return;
    }

    ws.send(
      JSON.stringify({
        type: "user_message",
        content: text,
      })
    );
  };

  const handleApproval = (approved: boolean) => {
    if (!state.pendingApproval) return;

    ws.send(
      JSON.stringify({
        type: "approval",
        requestId: state.pendingApproval.requestId,
        approved,
      })
    );

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

