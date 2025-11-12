import React, { useState, useMemo, useEffect } from "react";
import { Box, Text, useInput } from "ink";

interface UserInputProps {
  onSubmit: (text: string) => void;
  disabled?: boolean;
}

// Available commands
const COMMANDS = [
  { name: "help", description: "Show available commands" },
  { name: "exit", description: "Exit the application" },
  { name: "quit", description: "Exit the application (alias)" },
  { name: "clear", description: "Clear the screen" },
];

export const UserInput: React.FC<UserInputProps> = ({ onSubmit, disabled = false }) => {
  const [input, setInput] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);

  // Filter commands based on input
  const filteredCommands = useMemo(() => {
    if (!input.startsWith("/")) {
      return [];
    }

    const query = input.slice(1).toLowerCase();
    if (query === "") {
      return COMMANDS;
    }

    return COMMANDS.filter((cmd) =>
      cmd.name.toLowerCase().startsWith(query)
    );
  }, [input]);

  // Show suggestions when typing / or when there are filtered commands
  const shouldShowSuggestions = input.startsWith("/") && filteredCommands.length > 0;

  // Auto-select first match when filtering changes
  useEffect(() => {
    if (filteredCommands.length > 0 && selectedIndex >= filteredCommands.length) {
      setSelectedIndex(0);
    }
  }, [filteredCommands.length, selectedIndex]);

  useInput((inputChar: string, key: any) => {
    if (disabled) return;

    // Handle tab key - only cycle through visual selection, don't modify input
    if (key.tab && shouldShowSuggestions && filteredCommands.length > 0) {
      const newIndex = (selectedIndex + 1) % filteredCommands.length;
      setSelectedIndex(newIndex);
      return;
    }

    // Handle escape to clear input and suggestions
    if (key.escape) {
      setInput("");
      setSelectedIndex(0);
      return;
    }

    // Handle enter/return
    if (key.return) {
      if (input.trim()) {
        // If we have suggestions, use the selected command
        if (shouldShowSuggestions && filteredCommands.length > 0) {
          const selectedCommand = filteredCommands[selectedIndex];
          onSubmit(`/${selectedCommand.name}`);
        } else {
          // Regular input - send as-is
          onSubmit(input.trim());
        }
        setInput("");
        setSelectedIndex(0);
      }
      return;
    }

    // Handle backspace/delete
    if (key.backspace || key.delete) {
      const newInput = input.slice(0, -1);
      setInput(newInput);
      setSelectedIndex(0);
      return;
    }

    // Handle regular character input
    if (!key.ctrl && !key.meta && inputChar) {
      const newInput = input + inputChar;
      setInput(newInput);
      setSelectedIndex(0);
    }
  });

  return (
    <Box flexDirection="column">
      {shouldShowSuggestions && (
        <Box
          flexDirection="column"
          borderStyle="single"
          borderColor="gray"
          marginBottom={1}
          paddingX={1}
        >
          <Text color="gray" >
            Commands (Press Tab to cycle, Enter to select):
          </Text>
          {filteredCommands.map((cmd, idx) => (
            <Box key={cmd.name} paddingX={1}>
              <Text color={idx === selectedIndex ? "cyan" : "white"}>
                {idx === selectedIndex ? "▶ " : "  "}
                /{cmd.name}
              </Text>
              <Text color="gray">
                {" "}- {cmd.description}
              </Text>
            </Box>
          ))}
        </Box>
      )}
      <Box paddingX={1} borderStyle="single" borderColor={disabled ? "gray" : "cyan"}>
        <Text color="cyan" bold>
          {">"}{" "}
        </Text>
        <Text>{input}</Text>
        <Text color="gray">█</Text>
      </Box>
    </Box>
  );
};
