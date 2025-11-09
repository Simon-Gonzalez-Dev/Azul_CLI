import { ToolDefinition } from "../types.js";
import { readFileTool, writeFileTool, listDirTool } from "./filesystem.js";
import { executeCommandTool } from "./shell.js";
import { searchFilesTool } from "./search.js";

export const tools: ToolDefinition[] = [
  readFileTool,
  writeFileTool,
  listDirTool,
  executeCommandTool,
  searchFilesTool,
];

export function getToolByName(name: string): ToolDefinition | undefined {
  return tools.find((tool) => tool.name === name);
}

export { readFileTool, writeFileTool, listDirTool, executeCommandTool, searchFilesTool };

