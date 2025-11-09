import React from "react";
import { Box, Text, useInput } from "ink";
import { ApprovalRequest } from "../types.js";

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
      <Text> </Text>
      <Text dimColor>Arguments:</Text>
      <Text>{JSON.stringify(approval.args, null, 2)}</Text>
      <Text> </Text>
      <Box>
        <Text color="green">Y</Text>
        <Text> = Approve | </Text>
        <Text color="red">N</Text>
        <Text> = Deny</Text>
      </Box>
    </Box>
  );
};

