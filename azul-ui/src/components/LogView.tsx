import React from 'react';
import { Box, Text } from 'ink';

interface Message {
  type: string;
  content: string;
  timestamp: Date;
}

interface LogViewProps {
  messages: Message[];
}

const LogView: React.FC<LogViewProps> = ({ messages }) => {
  const getMessageColor = (type: string): string => {
    switch (type) {
      case 'user':
        return 'white';
      case 'thought':
        return 'gray';
      case 'plan':
        return 'blue';
      case 'tool_call':
        return 'yellow';
      case 'tool_result':
        return 'green';
      case 'response':
        return 'cyan';
      case 'error':
        return 'red';
      case 'system':
        return 'magenta';
      default:
        return 'white';
    }
  };
  
  const getMessagePrefix = (type: string): string => {
    switch (type) {
      case 'user':
        return '> ';
      case 'thought':
        return '💭 ';
      case 'plan':
        return '📋 ';
      case 'tool_call':
        return '⚡ ';
      case 'tool_result':
        return '✓ ';
      case 'response':
        return 'AZUL: ';
      case 'error':
        return '❌ ';
      case 'system':
        return '• ';
      default:
        return '';
    }
  };
  
  return (
    <Box flexDirection="column" paddingX={1}>
      {messages.length === 0 ? (
        <Box>
          <Text dimColor>No messages yet. Ask AZUL something!</Text>
        </Box>
      ) : (
        messages.map((msg, index) => (
          <Box key={index} marginBottom={msg.type === 'response' ? 1 : 0}>
            <Text color={getMessageColor(msg.type)}>
              {getMessagePrefix(msg.type)}
              {msg.content}
            </Text>
          </Box>
        ))
      )}
    </Box>
  );
};

export default LogView;

