import { ToolDefinition } from "../types.js";
import { readFileTool, writeFileTool, listDirTool, editFileTool } from "./filesystem.js";
import { executeCommandTool } from "./shell.js";
import { searchFilesTool } from "./search.js";

export const tools: ToolDefinition[] = [
  readFileTool,
  editFileTool,
  writeFileTool, // Keep for backwards compatibility but prefer edit_file
  listDirTool,
  executeCommandTool,
  searchFilesTool,
];

export function getToolByName(name: string): ToolDefinition | undefined {
  return tools.find((tool) => tool.name === name);
}

export { readFileTool, writeFileTool, editFileTool, listDirTool, executeCommandTool, searchFilesTool };

