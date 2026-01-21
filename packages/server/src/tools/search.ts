import { exec } from "child_process";
import { promisify } from "util";
import * as path from "path";
import { ToolDefinition } from "../types.js";
import * as fs from "fs/promises";

const execAsync = promisify(exec);

// Smart path resolution
function resolvePath(filePath: string, workingDirectory: string): string {
  if (filePath.startsWith("~")) {
    const homeDir = process.env.HOME || process.env.USERPROFILE || "";
    if (homeDir) {
      filePath = path.join(homeDir, filePath.slice(1));
    }
  }
  
  if (!path.isAbsolute(filePath)) {
    return path.resolve(workingDirectory, filePath);
  }
  
  return path.normalize(filePath);
}

// Enhanced grep tool with better options
export const grepTool: ToolDefinition = {
  name: "grep",
  description: "Search for text patterns in files using grep. Supports regex patterns, case-insensitive search, and file filtering. More powerful than search_files.",
  parameters: {
    type: "object",
    properties: {
      pattern: {
        type: "string",
        description: "The text pattern or regex to search for. Use regex syntax for advanced matching.",
      },
      path: {
        type: "string",
        description: "The directory or file path to search in (defaults to current directory). Supports relative and absolute paths.",
      },
      caseSensitive: {
        type: "boolean",
        description: "Whether the search should be case-sensitive (default: true)",
      },
      filePattern: {
        type: "string",
        description: "Optional file pattern filter (e.g., '*.ts', '*.{ts,tsx}'). Only search in matching files.",
      },
      maxResults: {
        type: "number",
        description: "Maximum number of results to return (default: 100)",
      },
    },
    required: ["pattern"],
  },
  requiresApproval: false,
  async execute(args: {
    pattern: string;
    path?: string;
    caseSensitive?: boolean;
    filePattern?: string;
    maxResults?: number;
  }, context?: { workingDirectory?: string }) {
    try {
      const workingDir = context?.workingDirectory || process.cwd();
      const searchPath = args.path ? resolvePath(args.path, workingDir) : workingDir;
      const caseSensitive = args.caseSensitive !== false; // Default to true
      const maxResults = args.maxResults || 100;
      
      // Check if path exists
      try {
        const stats = await fs.stat(searchPath);
        if (!stats.isDirectory() && !stats.isFile()) {
          return {
            success: false,
            toolName: "grep",
            error: `Path is not a file or directory: ${searchPath}`,
            message: `Path is not a file or directory: ${searchPath}`,
            filePath: searchPath,
          };
        }
      } catch {
        return {
          success: false,
          toolName: "grep",
          error: `Path not found: ${searchPath}`,
          message: `Path not found: ${searchPath}`,
          filePath: searchPath,
        };
      }
      
      // Build grep command with smart options
      let command = "grep";
      
      // Add flags
      const flags: string[] = [];
      flags.push("-rn"); // recursive, line numbers
      flags.push("-I"); // skip binary files
      
      if (!caseSensitive) {
        flags.push("-i");
      }
      
      // Add file pattern filter if specified
      if (args.filePattern) {
        flags.push(`--include=${args.filePattern}`);
      } else {
        // Default: exclude common binary and build artifacts
        flags.push("--exclude-dir=node_modules");
        flags.push("--exclude-dir=.git");
        flags.push("--exclude-dir=dist");
        flags.push("--exclude-dir=build");
        flags.push("--exclude=*.min.js");
        flags.push("--exclude=*.min.css");
      }
      
      // Escape pattern for shell (handle special characters)
      const escapedPattern = args.pattern.replace(/"/g, '\\"');
      const escapedPath = searchPath.replace(/"/g, '\\"');
      
      command = `grep ${flags.join(" ")} "${escapedPattern}" "${escapedPath}" 2>/dev/null || true`;
      
      const { stdout } = await execAsync(command, {
        maxBuffer: 10 * 1024 * 1024, // 10MB buffer for large results
      });
      
      const lines = stdout.trim().split("\n").filter(line => line.length > 0);
      const results = lines.slice(0, maxResults);
      const truncated = lines.length > maxResults;
      
      // Parse results into structured format
      const parsedResults = results.map(line => {
        // Format: path:line:content
        const match = line.match(/^(.+?):(\d+):(.+)$/);
        if (match) {
          return {
            file: match[1],
            line: parseInt(match[2], 10),
            content: match[3],
            fullLine: line,
          };
        }
        return {
          file: searchPath,
          line: 0,
          content: line,
          fullLine: line,
        };
      });
      
      // Format results into content string for UI display
      const content = parsedResults.map(r =>
        `${r.file}:${r.line}: ${r.content}`
      ).join('\n');

      const message = parsedResults.length > 0
        ? `Found ${lines.length} matches for "${args.pattern}"${truncated ? ` (showing first ${maxResults})` : ''}`
        : `No matches found for "${args.pattern}"`;

      return {
        success: true,
        toolName: "grep",
        message,
        content,
        filePath: searchPath,
        results: parsedResults,
        rawResults: results,
        matchCount: lines.length,
        truncated,
        pattern: args.pattern,
      };
    } catch (error: any) {
      return {
        success: false,
        toolName: "grep",
        error: error.message,
        message: error.message,
        pattern: args.pattern,
      };
    }
  },
};

