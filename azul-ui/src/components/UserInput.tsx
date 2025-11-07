import React, { useState } from 'react';
import { Box, Text } from 'ink';
import TextInput from 'ink-text-input';

interface UserInputProps {
  onSubmit: (input: string) => void;
  enabled: boolean;
  placeholder?: string;
}

const UserInput: React.FC<UserInputProps> = ({ onSubmit, enabled, placeholder = "Ask AZUL..." }) => {
  const [value, setValue] = useState('');
  
  const handleSubmit = () => {
    if (value.trim() && enabled) {
      onSubmit(value.trim());
      setValue('');
    }
  };
  
  return (
    <Box>
      <Box marginRight={1}>
        <Text color="cyan" bold>{enabled ? '>' : '⋯'}</Text>
      </Box>
      {enabled ? (
        <TextInput
          value={value}
          onChange={setValue}
          onSubmit={handleSubmit}
          placeholder={placeholder}
        />
      ) : (
        <Text dimColor>{placeholder}</Text>
      )}
    </Box>
  );
};

export default UserInput;

