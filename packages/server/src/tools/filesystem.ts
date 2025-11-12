import * as fs from "fs/promises";
import * as path from "path";
import { ToolDefinition } from "../types.js";

// Extract code from markdown code blocks
function extractCodeFromMarkdown(content: string): string {
  // Check if content is wrapped in markdown code blocks
  const codeBlockRegex = /^```[\w]*\n([\s\S]*?)\n```$/;
  const match = content.match(codeBlockRegex);
  if (match) {
    return match[1];
  }
  // Check for inline code blocks
  const inlineCodeRegex = /```[\w]*\n([\s\S]*?)\n```/g;
  const inlineMatch = content.match(inlineCodeRegex);
  if (inlineMatch && inlineMatch.length === 1) {
    return inlineMatch[0].replace(/```[\w]*\n/, '').replace(/\n```$/, '');
  }
  // No code blocks found, return as-is
  return content;
}

// Simple diff utility to show changes (optimized for readability)
function computeDiff(oldContent: string, newContent: string): {
  added: number;
  removed: number;
  diff: string;
} {
  const oldLines = oldContent.split("\n");
  const newLines = newContent.split("\n");
  
  let added = 0;
  let removed = 0;
  const diffLines: string[] = [];
  const contextLines = 3; // Show 3 lines of context around changes
  let lastChangeIndex = -contextLines - 1;
  
  // Simple line-by-line comparison with context
  const maxLen = Math.max(oldLines.length, newLines.length);
  for (let i = 0; i < maxLen; i++) {
    const oldLine = oldLines[i];
    const newLine = newLines[i];
    const isChanged = oldLine !== newLine;
    const isUnchanged = oldLine === newLine && oldLine !== undefined;
    
    // Show context around changes
    const shouldShowContext = isUnchanged && (i - lastChangeIndex <= contextLines);
    
    if (oldLine === undefined) {
      // New line added
      diffLines.push(`+ ${newLine}`);
      added++;
      lastChangeIndex = i;
    } else if (newLine === undefined) {
      // Line removed
      diffLines.push(`- ${oldLine}`);
      removed++;
      lastChangeIndex = i;
    } else if (isChanged) {
      // Line changed
      diffLines.push(`- ${oldLine}`);
      diffLines.push(`+ ${newLine}`);
      removed++;
      added++;
      lastChangeIndex = i;
    } else if (shouldShowContext) {
      // Show context around changes
      diffLines.push(`  ${oldLine}`);
    } else if (i === 0 || i === maxLen - 1) {
      // Always show first and last line
      diffLines.push(`  ${oldLine}`);
    }
    // Skip unchanged lines that are far from changes
  }
  
  // Limit diff size for very large files
  const maxDiffLines = 200;
  if (diffLines.length > maxDiffLines) {
    diffLines.splice(maxDiffLines);
    diffLines.push(`... (showing first ${maxDiffLines} lines of diff)`);
  }
  
  return {
    added,
    removed,
    diff: diffLines.join("\n"),
  };
}

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
  description: "Write or create a file with the given content. If the file exists, it will be updated and a diff will be shown. Use this tool whenever the user asks you to create, update, or modify a file. Extract the actual code content from any markdown code blocks if present.",
  parameters: {
    type: "object",
    properties: {
      path: {
        type: "string",
        description: "The path to the file to write (e.g., 'calc.py', './src/main.ts', 'app.js')",
      },
      content: {
        type: "string",
        description: "The complete content to write to the file. If the content is in a markdown code block, extract just the code without the markdown formatting.",
      },
    },
    required: ["path", "content"],
  },
  requiresApproval: true,
  async execute(args: { path: string; content: string }) {
    try {
      // Extract code from markdown if present
      const cleanContent = extractCodeFromMarkdown(args.content);
      
      // Check if file exists to compute diff
      let oldContent = "";
      let fileExists = false;
      try {
        oldContent = await fs.readFile(args.path, "utf-8");
        fileExists = true;
      } catch {
        // File doesn't exist, will be created
        fileExists = false;
      }
      
      // Ensure the directory exists
      const dir = path.dirname(args.path);
      await fs.mkdir(dir, { recursive: true });
      
      // Write the file with cleaned content
      await fs.writeFile(args.path, cleanContent, "utf-8");
      
      const result: any = {
        success: true,
        message: fileExists ? `File updated: ${args.path}` : `File created: ${args.path}`,
        filePath: args.path,
        fileExists,
      };
      
      // If file existed, compute and include diff
      if (fileExists) {
        const diff = computeDiff(oldContent, cleanContent);
        result.diff = diff.diff;
        result.added = diff.added;
        result.removed = diff.removed;
        result.changed = diff.added > 0 || diff.removed > 0;
      }
      
      return result;
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
