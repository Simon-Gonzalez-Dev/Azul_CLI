import React, { useState } from "react";
import { Box, Text, useInput } from "ink";
import { PlanStep } from "../types.js";

interface PlanModeOverlayProps {
  steps: PlanStep[];
  onExecute: () => void;
  onCancel: () => void;
}

export const PlanModeOverlay: React.FC<PlanModeOverlayProps> = ({
  steps,
  onExecute,
  onCancel,
}) => {
  const [selectedAction, setSelectedAction] = useState<"execute" | "cancel">("execute");

  useInput((input, key) => {
    // Tab or arrow keys to switch between actions
    if (key.tab || key.leftArrow || key.rightArrow) {
      setSelectedAction((prev) => (prev === "execute" ? "cancel" : "execute"));
      return;
    }

    // Enter to confirm action
    if (key.return) {
      if (selectedAction === "execute") {
        onExecute();
      } else {
        onCancel();
      }
      return;
    }

    // Escape to cancel
    if (key.escape) {
      onCancel();
      return;
    }

    // Keyboard shortcuts
    if (input === "e" || input === "E") {
      onExecute();
      return;
    }
    if (input === "c" || input === "C") {
      onCancel();
      return;
    }
  });

  const getStepStatusIcon = (status: PlanStep["status"]): string => {
    switch (status) {
      case "pending":
        return "○";
      case "approved":
        return "◐";
      case "executing":
        return "◑";
      case "completed":
        return "●";
      case "failed":
        return "✗";
      default:
        return "○";
    }
  };

  const getStepStatusColor = (status: PlanStep["status"]): string => {
    switch (status) {
      case "pending":
        return "gray";
      case "approved":
        return "yellow";
      case "executing":
        return "cyan";
      case "completed":
        return "green";
      case "failed":
        return "red";
      default:
        return "gray";
    }
  };

  return (
    <Box
      flexDirection="column"
      borderStyle="round"
      borderColor="magenta"
      paddingX={2}
      paddingY={1}
    >
      {/* Header */}
      <Box marginBottom={1}>
        <Text backgroundColor="magenta" color="white" bold>
          {" PLAN MODE "}
        </Text>
        <Text dimColor> - Review before execution</Text>
      </Box>

      {/* Plan steps */}
      <Box flexDirection="column" marginBottom={1}>
        <Text color="magenta" bold>
          Azul will:
        </Text>
        {steps.map((step, index) => (
          <Box key={step.id} paddingLeft={1}>
            <Text color={getStepStatusColor(step.status)}>
              {getStepStatusIcon(step.status)}
            </Text>
            <Text color="white">
              {" "}
              {index + 1}. {step.description}
            </Text>
            {step.toolName && (
              <Text dimColor> ({step.toolName})</Text>
            )}
            {step.status === "completed" && step.result && (
              <Text color="green" dimColor>
                {" "}
                ✓
              </Text>
            )}
            {step.status === "failed" && step.error && (
              <Text color="red">
                {" "}
                - {step.error}
              </Text>
            )}
          </Box>
        ))}
      </Box>

      {/* Action buttons */}
      <Box marginTop={1}>
        <Box marginRight={2}>
          <Text
            backgroundColor={selectedAction === "execute" ? "green" : undefined}
            color={selectedAction === "execute" ? "white" : "green"}
            bold={selectedAction === "execute"}
          >
            {selectedAction === "execute" ? " [E] Execute Plan " : " (E) Execute Plan "}
          </Text>
        </Box>
        <Box>
          <Text
            backgroundColor={selectedAction === "cancel" ? "red" : undefined}
            color={selectedAction === "cancel" ? "white" : "red"}
            bold={selectedAction === "cancel"}
          >
            {selectedAction === "cancel" ? " [C] Cancel " : " (C) Cancel "}
          </Text>
        </Box>
      </Box>

      {/* Help text */}
      <Box marginTop={1}>
        <Text dimColor>
          Tab to switch • Enter to confirm • Esc to cancel
        </Text>
      </Box>
    </Box>
  );
};
