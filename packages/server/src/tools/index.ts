import { ToolDefinition } from "../types.js";
import { lsTool, viewTool, editTool, writeTool } from "./filesystem.js";
import { bashTool } from "./shell.js";
import { grepTool } from "./search.js";

// Claude Code style tools
export const tools: ToolDefinition[] = [
  lsTool,       // List directory contents
  viewTool,     // Read file with line numbers
  editTool,     // Edit file via search/replace
  writeTool,    // Create new file
  bashTool,     // Execute shell commands (sandboxed)
  grepTool,     // Search for patterns
];

// Optimized tool lookup using Map for O(1) access
const toolMap = new Map<string, ToolDefinition>();
tools.forEach(tool => {
  toolMap.set(tool.name, tool);
});

export function getToolByName(name: string): ToolDefinition | undefined {
  return toolMap.get(name);
}

// Re-export individual tools for direct imports
export { lsTool, viewTool, editTool, writeTool, bashTool, grepTool };
