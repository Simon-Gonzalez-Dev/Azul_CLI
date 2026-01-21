import React from "react";
import { Box, Text } from "ink";

interface BannerProps {
  version?: string;
}

export const Banner: React.FC<BannerProps> = ({ version = "1.0" }) => {
  return (
    <Box
      flexDirection="row"
      paddingX={1}
      paddingY={0}
      borderStyle="round"
      borderColor="cyan"
    >
      <Box flexDirection="column">
        <Text color="cyanBright" bold>
          ▄▀█ ▀█ █ █ █
        </Text>
        <Text color="cyanBright" bold>
          █▀█ █▄ █▄█ █▄▄
        </Text>
      </Box>
      <Box flexDirection="column" marginLeft={2}>
        <Text color="white">Autonomous Coding Agent</Text>
        <Text dimColor>v{version}</Text>
      </Box>
    </Box>
  );
};

