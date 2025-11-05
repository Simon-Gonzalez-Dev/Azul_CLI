"""Response parser module for separating conversational text from file operations."""

import re
from typing import List, Dict, Tuple


def parse_response(response_text: str) -> Tuple[str, List[Dict]]:
    """
    Parse AI response and separate conversational text from potential file operations.
    
    Args:
        response_text: Full AI response text
        
    Returns:
        Tuple of (conversational_part, potential_actions)
        - conversational_part: Text with action blocks removed
        - potential_actions: List of action dicts with keys: type, path, content
          type can be: "edit", "create", "delete"
    """
    conversational_part = response_text
    potential_actions = []
    
    # Pattern to match diff code blocks: ```diff ... ```
    diff_pattern = r'```diff\s*\n(.*?)```'
    diff_matches = list(re.finditer(diff_pattern, response_text, re.DOTALL))
    
    for match in diff_matches:
        # Store the full diff block (including markdown) for edit_file which expects markdown format
        full_diff_block = match.group(0)
        diff_content = match.group(1).strip()
        # Extract file path from diff (look for --- a/path, +++ b/path, or just filenames)
        file_path = None
        
        # Try standard format first: --- a/path or +++ b/path
        path_match = re.search(r'---\s+a/([^\n]+)|\+\+\+\s+b/([^\n]+)', diff_content)
        if path_match:
            file_path = (path_match.group(1) or path_match.group(2)).strip()
        else:
            # Fallback: try to find filename in --- or +++ lines without a/b prefix
            path_match = re.search(r'---\s+([^\n]+\.\w+)|(?:\+\+\+)\s+([^\n]+\.\w+)', diff_content)
            if path_match:
                file_path = (path_match.group(1) or path_match.group(2)).strip()
        
        if file_path:
            potential_actions.append({
                "type": "edit",
                "path": file_path,
                "content": full_diff_block  # Pass full markdown block for edit_file
            })
            # Remove this block from conversational text
            conversational_part = conversational_part.replace(match.group(0), "", 1)
    
    # Pattern to match file creation code blocks: ```file:filename ... ```
    file_pattern = r'```file:([^\n]+)\n(.*?)```'
    file_matches = list(re.finditer(file_pattern, response_text, re.DOTALL))
    
    for match in file_matches:
        file_path = match.group(1).strip()
        file_content = match.group(2).strip()
        
        potential_actions.append({
            "type": "create",
            "path": file_path,
            "content": file_content
        })
        # Remove this block from conversational text
        conversational_part = conversational_part.replace(match.group(0), "", 1)
    
    # Pattern to match delete code blocks: ```delete:filename```
    delete_pattern = r'```delete:([^\n]+)```'
    delete_matches = list(re.finditer(delete_pattern, response_text, re.DOTALL))
    
    for match in delete_matches:
        file_path = match.group(1).strip()
        
        potential_actions.append({
            "type": "delete",
            "path": file_path,
            "content": None
        })
        # Remove this block from conversational text
        conversational_part = conversational_part.replace(match.group(0), "", 1)
    
    # Clean up conversational part: remove extra whitespace/newlines
    conversational_part = conversational_part.strip()
    
    return conversational_part, potential_actions

