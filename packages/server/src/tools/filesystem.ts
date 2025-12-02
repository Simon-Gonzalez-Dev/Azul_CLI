import * as fs from "fs/promises";
import * as path from "path";
import { ToolDefinition } from "../types.js";

// Smart path resolution - handles relative paths, ~ expansion, and normalization
function resolvePath(filePath: string, workingDirectory: string): string {
  // Handle home directory expansion
  if (filePath.startsWith("~")) {
    const homeDir = process.env.HOME || process.env.USERPROFILE || "";
    if (homeDir) {
      filePath = path.join(homeDir, filePath.slice(1));
    }
  }
  
  // Resolve relative paths against working directory
  if (!path.isAbsolute(filePath)) {
    return path.resolve(workingDirectory, filePath);
  }
  
  return path.normalize(filePath);
}

// Smart whitespace normalization - preserves intent while handling common issues
function normalizeWhitespace(content: string, preserveIndentation: boolean = true): string {
  // Normalize line endings to \n
  let normalized = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  
  // Remove trailing whitespace from lines (but preserve leading indentation)
  if (preserveIndentation) {
    normalized = normalized.split('\n').map(line => {
      // Preserve leading whitespace (indentation) but remove trailing
      return line.replace(/[ \t]+$/, '');
    }).join('\n');
  }
  
  // Ensure file ends with single newline (if it had content)
  if (normalized.length > 0 && !normalized.endsWith('\n')) {
    normalized += '\n';
  }
  
  return normalized;
}

// Extract code from markdown code blocks (smart extraction)
function extractCodeFromMarkdown(content: string): string {
  // Check for complete code block with language identifier
  const codeBlockRegex = /^```[\w]*\n([\s\S]*?)\n```$/;
  const match = content.match(codeBlockRegex);
  if (match) {
    return match[1];
  }
  
  // Check for inline code blocks (multiple)
  const inlineCodeRegex = /```[\w]*\n([\s\S]*?)\n```/g;
  const matches = [...content.matchAll(inlineCodeRegex)];
  if (matches.length === 1) {
    return matches[0][1];
  }
  
  // No code blocks found, return as-is
  return content;
}

// Smart diff utility with better context and formatting
export function computeDiff(oldContent: string, newContent: string): {
  added: number;
  removed: number;
  diff: string;
} {
  const oldLines = oldContent.split("\n");
  const newLines = newContent.split("\n");
  
  let added = 0;
  let removed = 0;
  const diffLines: string[] = [];
  const contextLines = 3;
  let lastChangeIndex = -contextLines - 1;
  
  const maxLen = Math.max(oldLines.length, newLines.length);
  for (let i = 0; i < maxLen; i++) {
    const oldLine = oldLines[i];
    const newLine = newLines[i];
    const isChanged = oldLine !== newLine;
    const isUnchanged = oldLine === newLine && oldLine !== undefined;
    const shouldShowContext = isUnchanged && (i - lastChangeIndex <= contextLines);
    
    if (oldLine === undefined) {
      diffLines.push(`+ ${newLine}`);
      added++;
      lastChangeIndex = i;
    } else if (newLine === undefined) {
      diffLines.push(`- ${oldLine}`);
      removed++;
      lastChangeIndex = i;
    } else if (isChanged) {
      diffLines.push(`- ${oldLine}`);
      diffLines.push(`+ ${newLine}`);
      removed++;
      added++;
      lastChangeIndex = i;
    } else if (shouldShowContext) {
      diffLines.push(`  ${oldLine}`);
    } else if (i === 0 || i === maxLen - 1) {
      diffLines.push(`  ${oldLine}`);
    }
  }
  
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

// Smart search block finder with fuzzy matching hints
function findSearchBlock(content: string, search: string): {
  found: boolean;
  exactMatch: boolean;
  suggestions?: string[];
} {
  const normalizedContent = normalizeWhitespace(content, true);
  const normalizedSearch = normalizeWhitespace(search, true);
  
  // Exact match
  if (normalizedContent.includes(normalizedSearch)) {
    return { found: true, exactMatch: true };
  }
  
  // Try without trailing whitespace
  const searchTrimmed = normalizedSearch.trim();
  if (normalizedContent.includes(searchTrimmed)) {
    return { found: true, exactMatch: false };
  }
  
  // Generate suggestions for similar blocks
  const suggestions: string[] = [];
  const searchLines = normalizedSearch.split('\n');
  if (searchLines.length > 0) {
    const firstLine = searchLines[0].trim();
    const contentLines = normalizedContent.split('\n');
    
    // Find lines containing the first line
    for (let i = 0; i < contentLines.length; i++) {
      if (contentLines[i].includes(firstLine)) {
        // Try to extract a similar block
        const start = Math.max(0, i - 2);
        const end = Math.min(contentLines.length, i + searchLines.length + 2);
        const candidate = contentLines.slice(start, end).join('\n');
        if (candidate.length > 0 && candidate.length < 500) {
          suggestions.push(candidate);
          if (suggestions.length >= 3) break;
        }
      }
    }
  }
  
  return { found: false, exactMatch: false, suggestions };
}

export const readFileTool: ToolDefinition = {
  name: "read_file",
  description: "Read the contents of a file from the filesystem. Returns the full file content.",
  parameters: {
    type: "object",
    properties: {
      path: {
        type: "string",
        description: "The path to the file to read (supports relative paths, absolute paths, and ~ expansion)",
      },
    },
    required: ["path"],
  },
  requiresApproval: false,
  async execute(args: { path: string }, context?: { workingDirectory?: string }) {
    try {
      const workingDir = context?.workingDirectory || process.cwd();
      const resolvedPath = resolvePath(args.path, workingDir);
      
      // Check if file exists first
      try {
        await fs.access(resolvedPath);
      } catch {
        return {
          success: false,
          error: `File not found: ${resolvedPath}`,
          suggestion: "Use list_dir to check the directory structure.",
        };
      }
      
      const content = await fs.readFile(resolvedPath, "utf-8");
      return {
        success: true,
        content,
        path: resolvedPath,
        size: content.length,
        lines: content.split('\n').length,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message,
        path: args.path,
      };
    }
  },
};

export const writeFileTool: ToolDefinition = {
  name: "write_file",
  description: "Create a new file or completely overwrite an existing file. Use this only for new files or very small files (<50 lines). For existing files, prefer edit_file.",
  parameters: {
    type: "object",
    properties: {
      path: {
        type: "string",
        description: "The path to the file to write (supports relative paths, absolute paths, and ~ expansion)",
      },
      content: {
        type: "string",
        description: "The complete content to write to the file. Markdown code blocks will be automatically extracted.",
      },
    },
    required: ["path", "content"],
  },
  requiresApproval: true,
  async execute(args: { path: string; content: string }, context?: { workingDirectory?: string }) {
    try {
      const workingDir = context?.workingDirectory || process.cwd();
      const resolvedPath = resolvePath(args.path, workingDir);
      
      // Extract code from markdown if present
      const cleanContent = extractCodeFromMarkdown(args.content);
      
      // Normalize whitespace
      const normalizedContent = normalizeWhitespace(cleanContent, true);
      
      // Check if file exists to compute diff
      let oldContent = "";
      let fileExists = false;
      try {
        oldContent = await fs.readFile(resolvedPath, "utf-8");
        fileExists = true;
      } catch {
        fileExists = false;
      }
      
      // Ensure the directory exists
      const dir = path.dirname(resolvedPath);
      try {
        await fs.mkdir(dir, { recursive: true });
      } catch (error: any) {
        return {
          success: false,
          error: `Failed to create directory: ${error.message}`,
        };
      }
      
      // Write the file
      await fs.writeFile(resolvedPath, normalizedContent, "utf-8");
      
      const result: any = {
        success: true,
        message: fileExists ? `File updated: ${resolvedPath}` : `File created: ${resolvedPath}`,
        filePath: resolvedPath,
        fileExists,
        lines: normalizedContent.split('\n').length,
      };
      
      // If file existed, compute and include diff
      if (fileExists) {
        const diff = computeDiff(oldContent, normalizedContent);
        result.diff = diff.diff;
        result.added = diff.added;
        result.removed = diff.removed;
        result.changed = diff.added > 0 || diff.removed > 0;
      }
      
      return result;
    } catch (error: any) {
      return {
        success: false,
        error: error.message,
        path: args.path,
      };
    }
  },
};

export const listDirTool: ToolDefinition = {
  name: "list_dir",
  description: "List the contents of a directory. Returns files and subdirectories with their types.",
  parameters: {
    type: "object",
    properties: {
      path: {
        type: "string",
        description: "The path to the directory to list (supports relative paths, absolute paths, and ~ expansion). Use '.' for current directory.",
      },
    },
    required: ["path"],
  },
  requiresApproval: false,
  async execute(args: { path: string }, context?: { workingDirectory?: string }) {
    try {
      const workingDir = context?.workingDirectory || process.cwd();
      const resolvedPath = resolvePath(args.path, workingDir);
      
      // Check if path exists and is a directory
      try {
        const stats = await fs.stat(resolvedPath);
        if (!stats.isDirectory()) {
          return {
            success: false,
            error: `Path is not a directory: ${resolvedPath}`,
            suggestion: "Use read_file to read files.",
          };
        }
      } catch {
        return {
          success: false,
          error: `Directory not found: ${resolvedPath}`,
          suggestion: "Check the path or use list_dir on a parent directory.",
        };
      }
      
      const entries = await fs.readdir(resolvedPath, { withFileTypes: true });
      const items = entries
        .map((entry) => ({
          name: entry.name,
          isDirectory: entry.isDirectory(),
          isFile: entry.isFile(),
          path: path.join(resolvedPath, entry.name),
        }))
        .sort((a, b) => {
          // Directories first, then alphabetically
          if (a.isDirectory && !b.isDirectory) return -1;
          if (!a.isDirectory && b.isDirectory) return 1;
          return a.name.localeCompare(b.name);
        });
      
      return {
        success: true,
        items,
        path: resolvedPath,
        count: items.length,
        directories: items.filter(i => i.isDirectory).length,
        files: items.filter(i => i.isFile).length,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message,
        path: args.path,
      };
    }
  },
};

export const editFileTool: ToolDefinition = {
  name: "edit_file",
  description: "Surgically edit a file by replacing a unique code block. This is the preferred method for editing existing files. The search block must match exactly including whitespace. Use read_file first to get the exact formatting.",
  parameters: {
    type: "object",
    properties: {
      path: {
        type: "string",
        description: "The path to the file to edit (supports relative paths, absolute paths, and ~ expansion)",
      },
      search: {
        type: "string",
        description: "The exact unique code block to locate. Must match file content EXACTLY including whitespace, indentation, and line endings. Copy this directly from read_file output.",
      },
      replace: {
        type: "string",
        description: "The new code block to insert in place of the search block. Will be normalized for whitespace.",
      },
    },
    required: ["path", "search", "replace"],
  },
  requiresApproval: true,
  async execute(args: { path: string; search: string; replace: string }, context?: { workingDirectory?: string }) {
    try {
      const workingDir = context?.workingDirectory || process.cwd();
      const resolvedPath = resolvePath(args.path, workingDir);
      
      // Read file content
      let content: string;
      try {
        content = await fs.readFile(resolvedPath, 'utf-8');
      } catch (error: any) {
        return {
          success: false,
          error: `File not found: ${resolvedPath}`,
          suggestion: "Use read_file to verify the file exists, or write_file to create it.",
        };
      }
      
      // Normalize whitespace for matching (preserve structure)
      const normalizedContent = normalizeWhitespace(content, true);
      const normalizedSearch = normalizeWhitespace(args.search, true);
      const normalizedReplace = normalizeWhitespace(args.replace, true);
      
      // Smart search with fuzzy matching hints
      const searchResult = findSearchBlock(normalizedContent, normalizedSearch);
      
      if (!searchResult.found) {
        // Try one more time with trimmed search (in case of trailing whitespace issues)
        const trimmedSearch = normalizedSearch.trim();
        if (normalizedContent.includes(trimmedSearch)) {
          // Found with trimmed version - use it
          const newContent = normalizedContent.replace(trimmedSearch, normalizedReplace);
          await fs.writeFile(resolvedPath, newContent, 'utf-8');
          
          const diff = computeDiff(trimmedSearch, normalizedReplace);
          return {
            success: true,
            message: "Patch applied successfully (matched with trimmed whitespace).",
            filePath: resolvedPath,
            diff: diff.diff,
            added: diff.added,
            removed: diff.removed,
            warning: "Search block was matched after trimming trailing whitespace.",
          };
        }
        
        // Not found - provide helpful error
        return {
          success: false,
          error: "Search block not found in file.",
          suggestion: searchResult.suggestions && searchResult.suggestions.length > 0
            ? `Similar blocks found. Use read_file to see the exact formatting. Here are some similar blocks:\n${searchResult.suggestions.slice(0, 2).map((s, i) => `\nBlock ${i + 1}:\n${s.substring(0, 200)}...`).join('\n')}`
            : "Read the file first using read_file to see the exact formatting, whitespace, and indentation. Copy the exact block you want to replace.",
          filePath: resolvedPath,
        };
      }
      
      // Perform replacement
      const newContent = normalizedContent.replace(normalizedSearch, normalizedReplace);
      await fs.writeFile(resolvedPath, newContent, 'utf-8');
      
      // Compute diff for display
      const diff = computeDiff(normalizedSearch, normalizedReplace);
      
      return {
        success: true,
        message: "Patch applied successfully.",
        filePath: resolvedPath,
        diff: diff.diff,
        added: diff.added,
        removed: diff.removed,
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message,
        path: args.path,
      };
    }
  },
};
