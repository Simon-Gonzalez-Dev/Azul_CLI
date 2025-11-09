import * as fs from "fs/promises";
import * as path from "path";
import { ToolDefinition } from "../types.js";

export const readFileTool: ToolDefinition = {
  name: "read_file",
  description: "Read the contents of a file from the filesystem",
  parameters: {
    type: "object",
    properties: {
      path: {
        type: "string",
        description: "The path to the file to read",
      },
    },
    required: ["path"],
  },
  requiresApproval: false,
  async execute(args: { path: string }) {
    try {
      const content = await fs.readFile(args.path, "utf-8");
      return { success: true, content };
    } catch (error: any) {
      return { success: false, error: error.message };
    }
  },
};

export const writeFileTool: ToolDefinition = {
  name: "write_file",
  description: "Write or create a file with the given content",
  parameters: {
    type: "object",
    properties: {
      path: {
        type: "string",
        description: "The path to the file to write",
      },
      content: {
        type: "string",
        description: "The content to write to the file",
      },
    },
    required: ["path", "content"],
  },
  requiresApproval: true,
  async execute(args: { path: string; content: string }) {
    try {
      // Ensure the directory exists
      const dir = path.dirname(args.path);
      await fs.mkdir(dir, { recursive: true });
      
      await fs.writeFile(args.path, args.content, "utf-8");
      return { success: true, message: `File written to ${args.path}` };
    } catch (error: any) {
      return { success: false, error: error.message };
    }
  },
};

export const listDirTool: ToolDefinition = {
  name: "list_dir",
  description: "List the contents of a directory",
  parameters: {
    type: "object",
    properties: {
      path: {
        type: "string",
        description: "The path to the directory to list",
      },
    },
    required: ["path"],
  },
  requiresApproval: false,
  async execute(args: { path: string }) {
    try {
      const entries = await fs.readdir(args.path, { withFileTypes: true });
      const items = entries.map((entry) => ({
        name: entry.name,
        isDirectory: entry.isDirectory(),
        isFile: entry.isFile(),
      }));
      return { success: true, items };
    } catch (error: any) {
      return { success: false, error: error.message };
    }
  },
};

