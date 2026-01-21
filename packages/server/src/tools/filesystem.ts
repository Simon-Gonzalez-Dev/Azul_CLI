import * as fs from "fs/promises";
import * as path from "path";
import { ToolDefinition } from "../types.js";

// Directories/files to filter out from ls
const FILTERED_ENTRIES = new Set([
  '.git',
  'node_modules',
  '.DS_Store',
  '.Spotlight-V100',
  '.Trashes',
  '.fseventsd',
  'Thumbs.db',
  'desktop.ini',
]);

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

// Enhanced search block finder with multiple fallback strategies
function findSearchBlock(content: string, search: string): {
  found: boolean;
  exactMatch: boolean;
  matchStrategy?: string;
  suggestions?: string[];
} {
  const normalizedContent = normalizeWhitespace(content, true);
  const normalizedSearch = normalizeWhitespace(search, true);

  // Strategy 1: Exact match
  if (normalizedContent.includes(normalizedSearch)) {
    return { found: true, exactMatch: true, matchStrategy: "exact" };
  }

  // Strategy 2: Trimmed match (trailing whitespace)
  const searchTrimmed = normalizedSearch.trim();
  if (normalizedContent.includes(searchTrimmed)) {
    return { found: true, exactMatch: false, matchStrategy: "trimmed" };
  }

  // Strategy 3: Line-by-line matching (for multi-line blocks)
  const searchLines = normalizedSearch.split('\n').map(l => l.trim()).filter(l => l.length > 0);
  const contentLines = normalizedContent.split('\n');

  if (searchLines.length > 1) {
    // Try to find the block by matching first and last lines
    const firstLine = searchLines[0];
    const lastLine = searchLines[searchLines.length - 1];

    let firstLineIndex = -1;
    let lastLineIndex = -1;

    for (let i = 0; i < contentLines.length; i++) {
      const line = contentLines[i].trim();
      if (firstLineIndex === -1 && line.includes(firstLine)) {
        firstLineIndex = i;
      }
      if (line.includes(lastLine) && i >= firstLineIndex && firstLineIndex !== -1) {
        lastLineIndex = i;
        break;
      }
    }

    if (firstLineIndex !== -1 && lastLineIndex !== -1 && lastLineIndex >= firstLineIndex) {
      // Found matching block boundaries
      const matchedBlock = contentLines.slice(firstLineIndex, lastLineIndex + 1).join('\n');
      const normalizedMatched = normalizeWhitespace(matchedBlock, true);

      // Check if the matched block is similar enough (at least 70% of search lines match)
      const matchedLines = normalizedMatched.split('\n').map(l => l.trim()).filter(l => l.length > 0);
      const matchingLines = searchLines.filter(sl =>
        matchedLines.some(ml => ml.includes(sl) || sl.includes(ml))
      );

      if (matchingLines.length >= Math.ceil(searchLines.length * 0.7)) {
        return {
          found: true,
          exactMatch: false,
          matchStrategy: "line_boundary",
          suggestions: [matchedBlock]
        };
      }
    }
  }

  // Strategy 4: Context-based matching (find by unique identifier)
  const uniqueIdentifiers = searchLines
    .filter(line => {
      const trimmed = line.trim();
      return trimmed.match(/^(function|class|const|let|var|export|import)\s+\w+/) ||
             trimmed.match(/\/\/.*[A-Z]/) ||
             trimmed.length > 20;
    })
    .slice(0, 2);

  if (uniqueIdentifiers.length > 0) {
    for (const identifier of uniqueIdentifiers) {
      const idTrimmed = identifier.trim();
      for (let i = 0; i < contentLines.length; i++) {
        if (contentLines[i].trim().includes(idTrimmed)) {
          const start = Math.max(0, i - 1);
          const end = Math.min(contentLines.length, i + searchLines.length + 3);
          const candidate = contentLines.slice(start, end).join('\n');
          const normalizedCandidate = normalizeWhitespace(candidate, true);

          const candidateLines = normalizedCandidate.split('\n').map(l => l.trim()).filter(l => l.length > 0);
          const matchingCandidateLines = searchLines.filter(sl =>
            candidateLines.some(cl => cl.includes(sl) || sl.includes(cl))
          );

          if (matchingCandidateLines.length >= Math.ceil(searchLines.length * 0.6)) {
            return {
              found: true,
              exactMatch: false,
              matchStrategy: "context_based",
              suggestions: [candidate]
            };
          }
        }
      }
    }
  }

  // Generate suggestions for debugging
  const suggestions: string[] = [];
  if (searchLines.length > 0) {
    const firstLine = searchLines[0];
    for (let i = 0; i < contentLines.length; i++) {
      if (contentLines[i].includes(firstLine)) {
        const start = Math.max(0, i - 2);
        const end = Math.min(contentLines.length, i + searchLines.length + 5);
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

// ============================================================================
// TOOL: ls - List directory contents (Claude Code style)
// ============================================================================
export const lsTool: ToolDefinition = {
  name: "ls",
  description: "List directory contents. Filters out .git, node_modules, .DS_Store and other noise.",
  parameters: {
    type: "object",
    properties: {
      path: {
        type: "string",
        description: "Directory path (optional, defaults to current directory '.')",
      },
    },
    required: [],
  },
  requiresApproval: false,
  async execute(args: { path?: string }, context?: { workingDirectory?: string }) {
    try {
      const workingDir = context?.workingDirectory || process.cwd();
      const targetPath = args.path || ".";
      const resolvedPath = resolvePath(targetPath, workingDir);

      // Check if path exists and is a directory
      try {
        const stats = await fs.stat(resolvedPath);
        if (!stats.isDirectory()) {
          return {
            success: false,
            toolName: "ls",
            error: `Path is not a directory: ${resolvedPath}`,
            message: `Path is not a directory: ${resolvedPath}. Use view to read files.`,
            filePath: resolvedPath,
          };
        }
      } catch {
        return {
          success: false,
          toolName: "ls",
          error: `Directory not found: ${resolvedPath}`,
          message: `Directory not found: ${resolvedPath}. Check the path or use ls on a parent directory.`,
          filePath: resolvedPath,
        };
      }

      const entries = await fs.readdir(resolvedPath, { withFileTypes: true });
      const items = entries
        // Filter out noise
        .filter(entry => !FILTERED_ENTRIES.has(entry.name))
        .map((entry) => ({
          name: entry.name,
          type: entry.isDirectory() ? "dir" : "file",
        }))
        .sort((a, b) => {
          // Directories first, then alphabetically
          if (a.type === "dir" && b.type !== "dir") return -1;
          if (a.type !== "dir" && b.type === "dir") return 1;
          return a.name.localeCompare(b.name);
        });

      // Format output as simple list (Claude Code style)
      const output = items.map(i =>
        i.type === "dir" ? `${i.name}/` : i.name
      ).join("\n");

      return {
        success: true,
        toolName: "ls",
        content: output,
        filePath: resolvedPath,
        message: `Listed ${items.length} items in ${resolvedPath}`,
      };
    } catch (error: any) {
      return {
        success: false,
        toolName: "ls",
        error: error.message,
        message: error.message,
        filePath: args.path,
      };
    }
  },
};

// ============================================================================
// TOOL: view - Read file with line numbers (Claude Code style)
// ============================================================================
export const viewTool: ToolDefinition = {
  name: "view",
  description: "Read file contents with line numbers. Use for examining code before making edits.",
  parameters: {
    type: "object",
    properties: {
      path: {
        type: "string",
        description: "File path to read",
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
          toolName: "view",
          error: `File not found: ${resolvedPath}`,
          message: `File not found: ${resolvedPath}. Use ls to check the directory structure.`,
          filePath: resolvedPath,
        };
      }

      const content = await fs.readFile(resolvedPath, "utf-8");
      const lines = content.split('\n');

      // Add line numbers (Claude Code style: "1| code here")
      const numberedContent = lines.map((line, i) =>
        `${(i + 1).toString().padStart(4)}| ${line}`
      ).join('\n');

      return {
        success: true,
        toolName: "view",
        content: numberedContent,
        filePath: resolvedPath,
        message: `Read ${lines.length} lines from ${resolvedPath}`,
        lines: lines.length,
      };
    } catch (error: any) {
      return {
        success: false,
        toolName: "view",
        error: error.message,
        message: error.message,
        filePath: args.path,
      };
    }
  },
};

// ============================================================================
// TOOL: edit - Edit file via search/replace (Claude Code style)
// ============================================================================
export const editTool: ToolDefinition = {
  name: "edit",
  description: "Edit a file by replacing a code block. Use unique identifiers (function names, class names, unique comments) to locate the block - do NOT use line numbers. Include 2-3 lines of context for better matching.",
  parameters: {
    type: "object",
    properties: {
      path: {
        type: "string",
        description: "File path to edit",
      },
      old_string: {
        type: "string",
        description: "The exact code block to find. Include unique identifiers (function/class names). Don't worry about exact whitespace.",
      },
      new_string: {
        type: "string",
        description: "The replacement code block.",
      },
    },
    required: ["path", "old_string", "new_string"],
  },
  requiresApproval: true,
  async execute(args: { path: string; old_string: string; new_string: string }, context?: { workingDirectory?: string }) {
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
          toolName: "edit",
          error: `File not found: ${resolvedPath}`,
          message: `File not found: ${resolvedPath}. Use view to verify the file exists, or write to create it.`,
          filePath: resolvedPath,
        };
      }

      // Normalize whitespace for matching
      const normalizedContent = normalizeWhitespace(content, true);
      const normalizedSearch = normalizeWhitespace(args.old_string, true);
      const normalizedReplace = normalizeWhitespace(args.new_string, true);

      // Enhanced smart search with multiple fallback strategies
      const searchResult = findSearchBlock(normalizedContent, normalizedSearch);

      if (!searchResult.found) {
        const errorMsg = searchResult.suggestions && searchResult.suggestions.length > 0
          ? `Search block not found. Similar blocks:\n${searchResult.suggestions.slice(0, 2).map((s, i) => `\nBlock ${i + 1}:\n${s.substring(0, 300)}...`).join('\n')}\n\nTip: Use unique identifiers from the block.`
          : "Search block not found. Use view to see the file, then include unique identifiers in old_string.";

        return {
          success: false,
          toolName: "edit",
          error: "Search block not found in file.",
          message: errorMsg,
          filePath: resolvedPath,
        };
      }

      // Perform replacement
      let newContent: string;
      let matchedBlock: string;

      if (searchResult.matchStrategy === "exact" || searchResult.matchStrategy === "trimmed") {
        const searchToUse = searchResult.matchStrategy === "trimmed"
          ? normalizedSearch.trim()
          : normalizedSearch;
        matchedBlock = searchToUse;
        newContent = normalizedContent.replace(searchToUse, normalizedReplace);
      } else if (searchResult.matchStrategy === "line_boundary" || searchResult.matchStrategy === "context_based") {
        matchedBlock = searchResult.suggestions![0];
        const normalizedMatched = normalizeWhitespace(matchedBlock, true);
        newContent = normalizedContent.replace(normalizedMatched, normalizedReplace);
      } else {
        matchedBlock = normalizedSearch;
        newContent = normalizedContent.replace(normalizedSearch, normalizedReplace);
      }

      await fs.writeFile(resolvedPath, newContent, 'utf-8');

      // Compute diff for display
      const diff = computeDiff(matchedBlock, normalizedReplace);

      const matchNote = searchResult.matchStrategy && searchResult.matchStrategy !== "exact"
        ? ` (matched via ${searchResult.matchStrategy})`
        : "";

      return {
        success: true,
        toolName: "edit",
        message: `Edited ${resolvedPath}${matchNote}`,
        filePath: resolvedPath,
        diff: diff.diff,
        added: diff.added,
        removed: diff.removed,
      };
    } catch (error: any) {
      return {
        success: false,
        toolName: "edit",
        error: error.message,
        message: error.message,
        filePath: args.path,
      };
    }
  },
};

// ============================================================================
// TOOL: write - Create new file (Claude Code style)
// ============================================================================
export const writeTool: ToolDefinition = {
  name: "write",
  description: "Create a new file or overwrite an existing one. Use ONLY for new files or very small files (<50 lines). For existing files, prefer edit.",
  parameters: {
    type: "object",
    properties: {
      path: {
        type: "string",
        description: "File path to create/write",
      },
      content: {
        type: "string",
        description: "File content to write",
      },
    },
    required: ["path", "content"],
  },
  requiresApproval: true,
  async execute(args: { path: string; content: string }, context?: { workingDirectory?: string }) {
    try {
      const workingDir = context?.workingDirectory || process.cwd();
      const resolvedPath = resolvePath(args.path, workingDir);

      // Check if file already exists
      let fileExists = false;
      try {
        await fs.access(resolvedPath);
        fileExists = true;
      } catch {
        fileExists = false;
      }

      // Create parent directories if needed
      const parentDir = path.dirname(resolvedPath);
      await fs.mkdir(parentDir, { recursive: true });

      // Write the file
      const normalizedContent = normalizeWhitespace(args.content, true);
      await fs.writeFile(resolvedPath, normalizedContent, 'utf-8');

      const contentLines = normalizedContent.split('\n');
      const lineCount = contentLines.length;
      const action = fileExists ? "Overwrote" : "Created";

      // Generate diff-like output showing all content as additions (for new files)
      // or a full replacement diff (for overwrites)
      const diffLines = contentLines.map(line => `+ ${line}`);
      const diff = diffLines.join('\n');

      return {
        success: true,
        toolName: "write",
        message: `${action} ${resolvedPath} (${lineCount} lines)`,
        filePath: resolvedPath,
        created: !fileExists,
        lines: lineCount,
        diff: diff,
        added: lineCount,
        removed: 0,
      };
    } catch (error: any) {
      return {
        success: false,
        toolName: "write",
        error: error.message,
        message: error.message,
        filePath: args.path,
      };
    }
  },
};
