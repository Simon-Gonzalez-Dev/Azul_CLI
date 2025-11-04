"""Command parser for @ commands."""

import re
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass


@dataclass
class ParsedCommand:
    """Represents a parsed command."""
    command: str
    args: list
    raw_input: str


class CommandParser:
    """Parses @ commands from user input."""
    
    COMMANDS = {
        'model': r'@model\s+(.+)',
        'edit': r'@edit\s+(\S+)\s+(.+)',
        'create': r'@create\s+(\S+)\s+(.+)',
        'delete': r'@delete\s+(\S+)',
        'read': r'@read\s+(\S+)',
        'ls': r'@ls',
        'path': r'@path',
        'clear': r'@clear',
        'reset': r'@reset',
        'help': r'@help',
        'exit': r'@exit',
        'quit': r'@quit',
    }
    
    def is_command(self, text: str) -> bool:
        """Check if text starts with @ command."""
        return text.strip().startswith('@')
    
    def parse(self, text: str) -> Optional[ParsedCommand]:
        """
        Parse a command from text.
        
        Args:
            text: Input text
            
        Returns:
            ParsedCommand if command found, None otherwise
        """
        text = text.strip()
        
        if not text.startswith('@'):
            return None
        
        # Try each command pattern
        for cmd_name, pattern in self.COMMANDS.items():
            match = re.match(pattern, text, re.DOTALL)
            if match:
                args = list(match.groups()) if match.groups() else []
                return ParsedCommand(
                    command=cmd_name,
                    args=args,
                    raw_input=text
                )
        
        # Unknown command
        return ParsedCommand(
            command='unknown',
            args=[],
            raw_input=text
        )


# Global command parser instance
_command_parser: Optional[CommandParser] = None


def get_command_parser() -> CommandParser:
    """Get the global command parser instance."""
    global _command_parser
    if _command_parser is None:
        _command_parser = CommandParser()
    return _command_parser

