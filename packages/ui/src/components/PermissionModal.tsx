import React from "react";
import { Box, Text, useInput } from "ink";
import { ApprovalRequest } from "../types.js";
import { DiffView } from "./DiffView.js";

interface PermissionModalProps {
  approval: ApprovalRequest;
  onApprove: (approved: boolean) => void;
}

export const PermissionModal: React.FC<PermissionModalProps> = ({
  approval,
  onApprove,
}) => {
  useInput((input: string, key: any) => {
    if (input === "y" || input === "Y") {
      onApprove(true);
    } else if (input === "n" || input === "N" || key.escape) {
      onApprove(false);
    } else if (key.ctrl && input === "c") {
      // Cancel approval and exit
      onApprove(false);
      process.exit(0);
    }
  });

  // Determine if this is a bash command (show command preview)
  const isBash = approval.tool === "bash";
  const command = isBash ? approval.args?.command : null;

  // Get risk level color for bash commands
  const getRiskColor = () => {
    // Check for dangerous patterns in command
    if (!command) return "yellow";
    const lowerCmd = command.toLowerCase();
    if (lowerCmd.includes("sudo") || lowerCmd.includes("rm -rf") || lowerCmd.includes("chmod 777")) {
      return "red";
    }
    if (lowerCmd.includes("rm ") || lowerCmd.includes("mv ") || lowerCmd.includes("git push")) {
      return "yellow";
    }
    return "cyan";
  };

  return (
    <Box
      flexDirection="column"
      borderStyle="double"
      borderColor="yellow"
      padding={1}
    >
      <Text bold color="yellow">
        ⚠️  Permission Required
      </Text>
      <Text> </Text>
      <Text>
        The agent wants to execute: <Text bold color="cyan">{approval.tool}</Text>
      </Text>

      {/* Bash command preview */}
      {isBash && command && (
        <Box flexDirection="column" marginTop={1}>
          <Text bold>Command:</Text>
          <Box borderStyle="single" borderColor={getRiskColor()} paddingX={1}>
            <Text color={getRiskColor() as any}>$ {command}</Text>
          </Box>
          {getRiskColor() === "red" && (
            <Text color="red" bold>⚠️  HIGH RISK COMMAND - Review carefully!</Text>
          )}
        </Box>
      )}

      {/* Non-bash: show arguments */}
      {!isBash && (
        <Box flexDirection="column" marginTop={1}>
          <Text dimColor>Arguments:</Text>
          <Text>{JSON.stringify(approval.args, null, 2)}</Text>
        </Box>
      )}

      {/* Diff view for file operations */}
      {approval.diff && (
        <Box flexDirection="column" marginTop={1}>
          <Text bold>Proposed Changes:</Text>
          <DiffView
            diff={approval.diff}
            added={approval.added}
            removed={approval.removed}
          />
        </Box>
      )}

      <Text> </Text>
      <Box>
        <Text color="green">Y</Text>
        <Text> = Approve | </Text>
        <Text color="red">N</Text>
        <Text> = Deny | </Text>
        <Text dimColor>Esc = Cancel</Text>
      </Box>
    </Box>
  );
};

