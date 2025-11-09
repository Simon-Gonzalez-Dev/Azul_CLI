import React, { useState } from "react";
import { Box, Text, useInput } from "ink";

interface UserInputProps {
  onSubmit: (text: string) => void;
  disabled?: boolean;
}

export const UserInput: React.FC<UserInputProps> = ({ onSubmit, disabled = false }) => {
  const [input, setInput] = useState("");

  useInput((inputChar: string, key: any) => {
    if (disabled) return;

    if (key.return) {
      if (input.trim()) {
        onSubmit(input.trim());
        setInput("");
      }
    } else if (key.backspace || key.delete) {
      setInput(input.slice(0, -1));
    } else if (!key.ctrl && !key.meta && inputChar) {
      setInput(input + inputChar);
    }
  });

  return (
    <Box paddingX={1} borderStyle="single" borderColor={disabled ? "gray" : "cyan"}>
      <Text color="cyan" bold>
        {">"}{" "}
      </Text>
      <Text>{input}</Text>
      <Text color="gray">█</Text>
    </Box>
  );
};

