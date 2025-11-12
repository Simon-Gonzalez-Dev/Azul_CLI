import React from "react";
import { Box, Text } from "ink";
import chalk from "chalk";

interface DiffViewProps {
  diff: string;
  added?: number;
  removed?: number;
  filePath?: string;
}

export const DiffView: React.FC<DiffViewProps> = ({ diff, added = 0, removed = 0, filePath }) => {
  const lines = diff.split("\n");
  const maxDisplayLines = 150; // Optimized for terminal display
  
  return (
    <Box flexDirection="column" marginY={1}>
      {filePath && (
        <Text color="cyan" bold>
          {filePath}
        </Text>
      )}
      <Box flexDirection="row" marginY={0}>
        {added > 0 && (
          <Text color="green" bold>
            +{added} 
          </Text>
        )}
        {removed > 0 && (
          <Text color="red" bold>
            {" "}-{removed}
          </Text>
        )}
        {(added > 0 || removed > 0) && (
          <Text dimColor> lines changed</Text>
        )}
      </Box>
      <Box flexDirection="column" borderStyle="single" borderColor="gray" paddingX={1} marginY={0}>
        {lines.slice(0, maxDisplayLines).map((line, idx) => {
          if (line.startsWith("+ ")) {
            return (
              <Text key={idx} color="green" backgroundColor="black">
                {line}
              </Text>
            );
          } else if (line.startsWith("- ")) {
            return (
              <Text key={idx} color="red" backgroundColor="black">
                {line}
              </Text>
            );
          } else {
            return (
              <Text key={idx} dimColor>
                {line}
              </Text>
            );
          }
        })}
        {lines.length > maxDisplayLines && (
          <Text dimColor>
            ... ({lines.length - maxDisplayLines} more lines, showing first {maxDisplayLines})
          </Text>
        )}
      </Box>
    </Box>
  );
};

