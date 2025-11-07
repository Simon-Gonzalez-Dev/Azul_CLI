import React from 'react';
import { Box, Text } from 'ink';

interface StatusBarProps {
  status: 'idle' | 'thinking' | 'executing' | 'error';
  statusText: string;
  todoVisible: boolean;
}

const StatusBar: React.FC<StatusBarProps> = ({ status, statusText, todoVisible }) => {
  const getStatusColor = (): string => {
    switch (status) {
      case 'idle':
        return 'green';
      case 'thinking':
        return 'yellow';
      case 'executing':
        return 'blue';
      case 'error':
        return 'red';
      default:
        return 'white';
    }
  };
  
  const getStatusIcon = (): string => {
    switch (status) {
      case 'idle':
        return '●';
      case 'thinking':
        return '◐';
      case 'executing':
        return '◑';
      case 'error':
        return '✖';
      default:
        return '○';
    }
  };
  
  return (
    <Box borderStyle="single" borderColor="gray" paddingX={1}>
      <Box flexGrow={1}>
        <Text color={getStatusColor()} bold>
          {getStatusIcon()} {statusText}
        </Text>
      </Box>
      
      <Box marginLeft={2}>
        <Text dimColor>[</Text>
        <Text color={todoVisible ? 'cyan' : 'gray'}>Ctrl+T: Todos</Text>
        <Text dimColor>]</Text>
      </Box>
      
      <Box marginLeft={2}>
        <Text dimColor>[</Text>
        <Text color="gray">Ctrl+C: Exit</Text>
        <Text dimColor>]</Text>
      </Box>
    </Box>
  );
};

export default StatusBar;

