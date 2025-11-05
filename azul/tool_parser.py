"""Tool call parser for detecting and extracting tool calls from AI output."""

import re
import ast
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


@dataclass
class ToolCall:
    """Represents a parsed tool call."""
    tool_name: str
    arguments: Dict[str, Any]
    raw_code: str


def detect_tool_call(buffer: str) -> Optional[str]:
    """
    Detect if a potentially incomplete tool call tag is present in the buffer.
    Returns the incomplete tag if found, None otherwise.
    
    Args:
        buffer: Accumulated text buffer
        
    Returns:
        Incomplete tool tag if detected, None otherwise
    """
    # Look for opening tag
    if '<tool_code>' in buffer.lower():
        # Check if we have a closing tag
        # Use case-insensitive matching
        pattern = r'<tool_code>(.*?)</tool_code>'
        match = re.search(pattern, buffer, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(0)  # Return complete tag
        else:
            # Check if we're still building the tag
            opening_match = re.search(r'<tool_code>', buffer, re.IGNORECASE)
            if opening_match:
                # Check if we have enough content to potentially parse
                after_opening = buffer[opening_match.end():]
                # If we have a closing tag attempt, return it
                if '</tool_code>' in after_opening.lower():
                    return None  # Let extract_tool_call handle it
                return None  # Still incomplete
    return None


def extract_tool_call(content: str) -> Optional[ToolCall]:
    """
    Extract a complete tool call from content.
    
    Args:
        content: Text containing tool call in <tool_code> tags
        
    Returns:
        ToolCall object if found, None otherwise
    """
    # Pattern to match tool_code tags (case-insensitive)
    pattern = r'<tool_code>(.*?)</tool_code>'
    match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
    
    if not match:
        return None
    
    tool_code = match.group(1).strip()
    raw_code = match.group(0)  # Full tag including <tool_code>...</tool_code>
    
    # Try to parse as Python function call
    try:
        # Parse the tool code as a Python expression
        parsed = ast.parse(tool_code, mode='eval')
        
        if isinstance(parsed.body, ast.Call):
            func = parsed.body
            tool_name = func.func.id if isinstance(func.func, ast.Name) else None
            
            if tool_name is None:
                return None
            
            # Parse arguments
            arguments = {}
            
            # Handle positional arguments (convert to keyword args where possible)
            for i, arg in enumerate(func.args):
                if isinstance(arg, (ast.Str, ast.Constant)):
                    # String literal
                    value = arg.s if hasattr(arg, 's') else arg.value
                    arguments[f'arg_{i}'] = value
                elif isinstance(arg, ast.Name):
                    arguments[f'arg_{i}'] = arg.id
                else:
                    # Try to evaluate
                    try:
                        value = ast.literal_eval(arg)
                        arguments[f'arg_{i}'] = value
                    except:
                        arguments[f'arg_{i}'] = None
            
            # Handle keyword arguments
            for keyword in func.keywords:
                if keyword.arg:
                    if isinstance(keyword.value, (ast.Str, ast.Constant)):
                        value = keyword.value.s if hasattr(keyword.value, 's') else keyword.value.value
                        arguments[keyword.arg] = value
                    elif isinstance(keyword.value, ast.NameConstant):  # Python < 3.8
                        # Handle True, False, None
                        arguments[keyword.arg] = keyword.value.value
                    elif isinstance(keyword.value, ast.Constant):  # Python 3.8+
                        # Handle True, False, None, numbers, strings
                        arguments[keyword.arg] = keyword.value.value
                    elif isinstance(keyword.value, ast.Name):
                        # Handle variable names like True, False, None
                        name = keyword.value.id
                        if name == 'True':
                            arguments[keyword.arg] = True
                        elif name == 'False':
                            arguments[keyword.arg] = False
                        elif name == 'None':
                            arguments[keyword.arg] = None
                        else:
                            arguments[keyword.arg] = name
                    else:
                        try:
                            value = ast.literal_eval(keyword.value)
                            arguments[keyword.arg] = value
                        except:
                            arguments[keyword.arg] = None
            
            # Special handling for common tools
            # For exec tool: first arg is command
            if tool_name == 'exec':
                if 'arg_0' in arguments:
                    if isinstance(arguments['arg_0'], str):
                        if 'command' not in arguments:
                            arguments['command'] = arguments.pop('arg_0')
                # background parameter should already be handled by keyword args
            else:
                # If first positional arg looks like a file path, use 'file_path' key
                if 'arg_0' in arguments:
                    if isinstance(arguments['arg_0'], str):
                        if 'file_path' not in arguments:
                            arguments['file_path'] = arguments.pop('arg_0')
                
                # If second positional arg looks like content, use 'content' key
                if 'arg_1' in arguments:
                    if 'content' not in arguments and 'diff_content' not in arguments:
                        arguments['content'] = arguments.pop('arg_1')
            
            return ToolCall(
                tool_name=tool_name,
                arguments=arguments,
                raw_code=raw_code
            )
    except SyntaxError:
        # If parsing fails, try simple regex extraction
        # Pattern: function_name('arg1', 'arg2') or function_name()
        func_pattern = r'(\w+)\s*\(([^)]*)\)'
        func_match = re.match(func_pattern, tool_code.strip())
        
        if func_match:
            tool_name = func_match.group(1)
            args_str = func_match.group(2).strip()
            
            arguments = {}
            
            if args_str:
                # Try to parse arguments (simple string extraction)
                # Handle quoted strings
                arg_pattern = r"(['\"])((?:(?=(\\?))\3.)*?)\1"
                string_args = re.findall(arg_pattern, args_str)
                
                # Handle keyword arguments like background=True
                keyword_pattern = r'(\w+)\s*=\s*(True|False|None|\w+|\'[^\']*\'|"[^"]*")'
                keyword_args = re.findall(keyword_pattern, args_str)
                
                # Process keyword arguments
                for key, value in keyword_args:
                    # Parse boolean values
                    if value == 'True':
                        arguments[key] = True
                    elif value == 'False':
                        arguments[key] = False
                    elif value == 'None':
                        arguments[key] = None
                    elif value.startswith(("'", '"')):
                        # String value
                        arguments[key] = value.strip('\'"')
                    else:
                        arguments[key] = value
                
                # Process positional arguments (if any strings found)
                if string_args:
                    parsed_args = [arg[1] for arg in string_args]
                    if parsed_args:
                        if tool_name == 'exec':
                            arguments['command'] = parsed_args[0]
                        else:
                            arguments['file_path'] = parsed_args[0]
                    if len(parsed_args) > 1:
                        arguments['content'] = parsed_args[1]
                elif not keyword_args:
                    # No quotes, try simple split (for non-string args)
                    parts = args_str.split(',')
                    if parts:
                        if tool_name == 'exec':
                            arguments['command'] = parts[0].strip()
                        else:
                            arguments['file_path'] = parts[0].strip()
                    if len(parts) > 1:
                        arguments['content'] = parts[1].strip()
            
            return ToolCall(
                tool_name=tool_name,
                arguments=arguments,
                raw_code=raw_code
            )
    
    return None


def remove_tool_call_from_content(content: str, tool_call: ToolCall) -> str:
    """
    Remove a tool call from content, returning the remaining text.
    
    Args:
        content: Original content
        tool_call: Tool call to remove
        
    Returns:
        Content with tool call removed
    """
    return content.replace(tool_call.raw_code, "", 1).strip()

