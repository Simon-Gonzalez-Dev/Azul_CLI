import { spawn } from "child_process";
import * as path from "path";
import * as fs from "fs/promises";

/**
 * Get the user's preferred editor
 * Priority: $EDITOR -> $VISUAL -> platform default
 */
function getEditor(): string {
  // Check environment variables first
  if (process.env.EDITOR) {
    return process.env.EDITOR;
  }
  if (process.env.VISUAL) {
    return process.env.VISUAL;
  }

  // Platform-specific defaults
  const platform = process.platform;

  if (platform === "darwin") {
    // macOS: Use open command which respects default app associations
    return "open";
  } else if (platform === "win32") {
    // Windows: Use notepad as safe default
    return "notepad";
  } else {
    // Linux/other: Try nano as safe fallback
    return "nano";
  }
}

/**
 * Open a file in the user's preferred editor
 */
export async function openInEditor(filePath: string): Promise<{
  success: boolean;
  message: string;
  editor?: string;
}> {
  const editor = getEditor();
  const platform = process.platform;

  // Check if file exists
  try {
    await fs.access(filePath);
  } catch {
    return {
      success: false,
      message: `File not found: ${filePath}`,
    };
  }

  return new Promise((resolve) => {
    let child;

    try {
      if (platform === "darwin" && editor === "open") {
        // macOS: use 'open -t' for default text editor
        child = spawn("open", ["-t", filePath], {
          detached: true,
          stdio: "ignore",
        });
      } else if (platform === "win32") {
        // Windows: use start command
        child = spawn("cmd", ["/c", "start", "", filePath], {
          detached: true,
          stdio: "ignore",
          shell: true,
        });
      } else {
        // Linux/other: spawn editor directly
        // Note: Terminal editors won't work well with Ink UI
        child = spawn(editor, [filePath], {
          detached: true,
          stdio: "ignore",
        });
      }

      child.on("error", (err) => {
        resolve({
          success: false,
          message: `Failed to open editor (${editor}): ${err.message}`,
          editor,
        });
      });

      // Detach the process so it continues after we resolve
      child.unref();

      // Small delay to ensure process started
      setTimeout(() => {
        resolve({
          success: true,
          message: `Opened ${path.basename(filePath)} in ${editor}`,
          editor,
        });
      }, 100);
    } catch (err: any) {
      resolve({
        success: false,
        message: `Failed to spawn editor: ${err.message}`,
        editor,
      });
    }
  });
}

/**
 * Find AZUL.md file path in the project
 * Uses same search order as loadAzulMd in agent.ts
 */
export async function findAzulMdPath(
  workingDir: string
): Promise<string | null> {
  const searchPaths = [
    path.join(workingDir, "AZUL.md"),
    path.join(workingDir, ".azul", "AZUL.md"),
  ];

  // Also check parent directories (for monorepos)
  let currentDir = workingDir;
  for (let i = 0; i < 3; i++) {
    const parentDir = path.dirname(currentDir);
    if (parentDir === currentDir) break;
    searchPaths.push(path.join(parentDir, "AZUL.md"));
    searchPaths.push(path.join(parentDir, ".azul", "AZUL.md"));
    currentDir = parentDir;
  }

  for (const searchPath of searchPaths) {
    try {
      await fs.access(searchPath);
      return searchPath;
    } catch {
      // Continue searching
    }
  }

  return null;
}
