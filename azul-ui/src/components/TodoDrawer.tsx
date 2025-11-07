import React from 'react';
import { Box, Text } from 'ink';

interface Task {
  id: string;
  text: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
}

interface TodoDrawerProps {
  tasks: Task[];
}

const TodoDrawer: React.FC<TodoDrawerProps> = ({ tasks }) => {
  const getStatusIcon = (status: Task['status']): string => {
    switch (status) {
      case 'pending':
        return '○';
      case 'in_progress':
        return '◐';
      case 'completed':
        return '✓';
      case 'failed':
        return '✖';
      default:
        return '?';
    }
  };
  
  const getStatusColor = (status: Task['status']): string => {
    switch (status) {
      case 'pending':
        return 'gray';
      case 'in_progress':
        return 'yellow';
      case 'completed':
        return 'green';
      case 'failed':
        return 'red';
      default:
        return 'white';
    }
  };
  
  return (
    <Box flexDirection="column" paddingX={1} paddingY={1}>
      <Box marginBottom={1}>
        <Text bold color="cyan">Plan</Text>
      </Box>
      
      {tasks.length === 0 ? (
        <Text dimColor>No active plan</Text>
      ) : (
        tasks.map((task, index) => (
          <Box key={task.id} marginBottom={1}>
            <Box marginRight={1}>
              <Text color={getStatusColor(task.status)}>
                {getStatusIcon(task.status)}
              </Text>
            </Box>
            <Box flexDirection="column" flexGrow={1}>
              <Text color={getStatusColor(task.status)}>
                {task.text}
              </Text>
            </Box>
          </Box>
        ))
      )}
    </Box>
  );
};

export default TodoDrawer;

