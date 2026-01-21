import React, { useState, useMemo, useEffect } from "react";
import { Box, Text, useInput } from "ink";
import { AgentMode, InputMode, COMMANDS, RECENT_BASH_COMMANDS } from "../types.js";

interface UserInputProps {
  onSubmit: (text: string) => void;
  onInputChange?: (text: string) => void;
  onModeToggle?: () => void;
  disabled?: boolean;
  agentMode: AgentMode;
  inputMode: InputMode;
}

export const UserInput: React.FC<UserInputProps> = ({
  onSubmit,
  onInputChange,
  onModeToggle,
  disabled = false,
  agentMode,
  inputMode,
}) => {
  const [input, setInput] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);

  // Detect current input mode based on prefix
  const currentInputMode: InputMode = useMemo(() => {
    if (input.startsWith('$')) return 'bash';
    if (input.startsWith('/')) return 'command';
    return 'chat';
  }, [input]);

  // Get suggestions based on input mode
  const suggestions = useMemo(() => {
    if (currentInputMode === 'command') {
      const query = input.slice(1).toLowerCase();
      if (query === "") {
        return COMMANDS;
      }
      return COMMANDS.filter((cmd) =>
        cmd.name.toLowerCase().startsWith(query)
      );
    }

    if (currentInputMode === 'bash' && RECENT_BASH_COMMANDS.length > 0) {
      const query = input.slice(1).toLowerCase();
      if (query === "") {
        return RECENT_BASH_COMMANDS.slice(0, 5).map(cmd => ({
          name: cmd,
          description: "Recent command"
        }));
      }
      return RECENT_BASH_COMMANDS
        .filter(cmd => cmd.toLowerCase().includes(query))
        .slice(0, 5)
        .map(cmd => ({
          name: cmd,
          description: "Recent command"
        }));
    }

    return [];
  }, [input, currentInputMode]);

  const shouldShowSuggestions = suggestions.length > 0;

  // Auto-select first match when filtering changes
  useEffect(() => {
    if (suggestions.length > 0 && selectedIndex >= suggestions.length) {
      setSelectedIndex(0);
    }
  }, [suggestions.length, selectedIndex]);

  // Notify parent of input changes
  useEffect(() => {
    if (onInputChange) {
      onInputChange(input);
    }
  }, [input, onInputChange]);

  useInput((inputChar: string, key: any) => {
    if (disabled) return;

    // Handle Shift+Tab - toggle agent mode
    if (key.tab && key.shift) {
      if (onModeToggle) {
        onModeToggle();
      }
      return;
    }

    // Handle Tab - cycle through suggestions
    if (key.tab && !key.shift && shouldShowSuggestions && suggestions.length > 0) {
      const newIndex = (selectedIndex + 1) % suggestions.length;
      setSelectedIndex(newIndex);
      return;
    }

    // Handle escape to clear input
    if (key.escape) {
      setInput("");
      setSelectedIndex(0);
      return;
    }

    // Handle enter/return
    if (key.return) {
      if (input.trim()) {
        // If we have command suggestions selected, use the selected command
        if (currentInputMode === 'command' && shouldShowSuggestions && suggestions.length > 0) {
          const selectedCommand = suggestions[selectedIndex];
          onSubmit(`/${selectedCommand.name}`);
        } else if (currentInputMode === 'bash' && shouldShowSuggestions && suggestions.length > 0) {
          // For bash, insert the selected command
          const selectedCommand = suggestions[selectedIndex];
          onSubmit(`$${selectedCommand.name}`);
        } else {
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

  // Determine prompt style based on modes
  const getPromptStyle = () => {
    if (agentMode === 'plan') {
      return { text: "plan>", color: "magenta" as const };
    }
    if (currentInputMode === 'bash') {
      return { text: "$", color: "green" as const };
    }
    if (currentInputMode === 'command') {
      return { text: "/", color: "yellow" as const };
    }
    return { text: ">", color: "cyan" as const };
  };

  const promptStyle = getPromptStyle();

  // Get the display text (without the mode prefix for visual clarity)
  const displayText = useMemo(() => {
    if (currentInputMode === 'bash' && input.startsWith('$')) {
      return input.slice(1);
    }
    if (currentInputMode === 'command' && input.startsWith('/')) {
      return input.slice(1);
    }
    return input;
  }, [input, currentInputMode]);

  // Get border color based on state
  const borderColor = useMemo(() => {
    if (disabled) return "gray";
    if (agentMode === 'plan') return "magenta";
    if (currentInputMode === 'bash') return "green";
    if (currentInputMode === 'command') return "yellow";
    return "cyan";
  }, [disabled, agentMode, currentInputMode]);

  // Suggestion header text
  const suggestionHeader = currentInputMode === 'bash'
    ? "Recent Commands"
    : "Commands";

  return (
    <Box flexDirection="column">
      {/* Mode indicator bar */}
      <Box paddingX={1} marginBottom={0}>
        <Text dimColor>
          <Text color={currentInputMode === 'bash' ? 'green' : 'gray'}>
            {currentInputMode === 'bash' ? '●' : '○'} $Bash
          </Text>
          <Text> </Text>
          <Text color={currentInputMode === 'command' ? 'yellow' : 'gray'}>
            {currentInputMode === 'command' ? '●' : '○'} /Cmd
          </Text>
          <Text> </Text>
          <Text color={currentInputMode === 'chat' ? 'cyan' : 'gray'}>
            {currentInputMode === 'chat' ? '●' : '○'} Chat
          </Text>
          <Text>  │  </Text>
          <Text color={agentMode === 'plan' ? 'magenta' : 'gray'}>
            [{agentMode === 'plan' ? 'PLAN' : 'NORMAL'}]
          </Text>
          <Text dimColor> Shift+Tab to toggle</Text>
        </Text>
      </Box>

      {/* Suggestions box */}
      {shouldShowSuggestions && (
        <Box
          flexDirection="column"
          borderStyle="single"
          borderColor="gray"
          marginBottom={0}
          paddingX={1}
        >
          <Text color="gray" dimColor>
            {suggestionHeader} (Tab to cycle, Enter to select):
          </Text>
          {suggestions.map((cmd, idx) => (
            <Box key={cmd.name} paddingX={1}>
              <Text color={idx === selectedIndex ? borderColor : "white"}>
                {idx === selectedIndex ? "▸ " : "  "}
                {currentInputMode === 'bash' ? '' : '/'}
                {cmd.name}
              </Text>
              <Text color="gray" dimColor>
                {" "}- {cmd.description}
              </Text>
            </Box>
          ))}
        </Box>
      )}

      {/* Input box */}
      <Box paddingX={1} borderStyle="round" borderColor={borderColor}>
        <Text color={promptStyle.color} bold>
          {promptStyle.text}{" "}
        </Text>
        <Text>{displayText}</Text>
        <Text color="gray">│</Text>
      </Box>
    </Box>
  );
};
