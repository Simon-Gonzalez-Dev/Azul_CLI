import { ToolDefinition } from "../types.js";
import { readFileTool, writeFileTool, listDirTool, editFileTool } from "./filesystem.js";
import { executeCommandTool } from "./shell.js";
import { searchFilesTool, grepTool } from "./search.js";

export const tools: ToolDefinition[] = [
  readFileTool,
  editFileTool,
  writeFileTool, // Keep for backwards compatibility but prefer edit_file
  listDirTool,
  executeCommandTool,
  grepTool, // Enhanced grep tool
  searchFilesTool, // Simple search (backwards compatible)
];

// Optimized tool lookup using Map for O(1) access
const toolMap = new Map<string, ToolDefinition>();
tools.forEach(tool => {
  toolMap.set(tool.name, tool);
});

export function getToolByName(name: string): ToolDefinition | undefined {
  return toolMap.get(name);
}

// Individual tools are only used internally - no need to export them
// They're accessible via getToolByName() or the tools array

