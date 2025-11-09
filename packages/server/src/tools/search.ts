import { exec } from "child_process";
import { promisify } from "util";
import { ToolDefinition } from "../types.js";

const execAsync = promisify(exec);

export const searchFilesTool: ToolDefinition = {
  name: "search_files",
  description: "Search for a pattern in files (similar to grep)",
  parameters: {
    type: "object",
    properties: {
      pattern: {
        type: "string",
        description: "The pattern to search for",
      },
      path: {
        type: "string",
        description: "The path to search in (optional, defaults to current directory)",
      },
    },
    required: ["pattern"],
  },
  requiresApproval: false,
  async execute(args: { pattern: string; path?: string }) {
    try {
      const searchPath = args.path || ".";
      // Use grep -r for recursive search, -n for line numbers, -I to skip binary files
      const command = `grep -rn -I "${args.pattern}" "${searchPath}" 2>/dev/null || true`;
      const { stdout } = await execAsync(command);
      
      const lines = stdout.trim().split("\n").filter(line => line.length > 0);
      const results = lines.slice(0, 50); // Limit to first 50 results
      
      return {
        success: true,
        results,
        count: results.length,
        truncated: lines.length > 50,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message,
      };
    }
  },
};

