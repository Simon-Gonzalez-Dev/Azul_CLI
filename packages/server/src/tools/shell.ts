import { spawn } from "child_process";
import { ToolDefinition } from "../types.js";

export const executeCommandTool: ToolDefinition = {
  name: "execute_command",
  description: "Execute a shell command and return the output. Long-running commands (like servers) will be terminated after 5 seconds and partial output returned.",
  parameters: {
    type: "object",
    properties: {
      command: {
        type: "string",
        description: "The shell command to execute",
      },
      cwd: {
        type: "string",
        description: "The working directory to execute the command in (optional)",
      },
    },
    required: ["command"],
  },
  requiresApproval: true,
  async execute(args: { command: string; cwd?: string }) {
    const timeoutMs = 5000;
    const cwd = args.cwd || process.cwd();

    return new Promise((resolve) => {
      let output = "";
      let errorOutput = "";
      let completed = false;

      // Use sh -c to run the command so we don't have to parse args manually
      const child = spawn("sh", ["-c", args.command], {
        cwd,
        shell: false, // We are explicitly using sh -c
        stdio: ["ignore", "pipe", "pipe"],
      });

      // Capture Output
      child.stdout?.on("data", (data) => {
        output += data.toString();
      });
      child.stderr?.on("data", (data) => {
        errorOutput += data.toString();
      });

      // Handle Process Exit (The Happy Path for short commands)
      child.on("close", (code) => {
        if (completed) return; // Prevent double resolve
        completed = true;

        if (code === 0) {
          resolve({
            success: true,
            stdout: output.trim(),
            stderr: errorOutput.trim(),
            message: "Process exited with code 0.",
          });
        } else {
          resolve({
            success: false,
            stdout: output.trim(),
            stderr: errorOutput.trim(),
            error: `Process failed with code ${code}.`,
          });
        }
      });

      // Handle Timeout (The Fix for Servers/Hanging)
      const timer = setTimeout(() => {
        if (completed) return;

        // Kill the process so the agent can resume
        child.kill();
        completed = true;

        resolve({
          success: true, // Treat timeout as success for inspection
          stdout: output.trim(),
          stderr: errorOutput.trim(),
          message: `Command timed out after ${timeoutMs}ms. This is expected for long-running processes (servers, watchers). output captured so far.`,
        });
      }, timeoutMs);

      // Handle Startup Errors
      child.on("error", (err) => {
        if (completed) return;
        completed = true;
        clearTimeout(timer);
        resolve({
          success: false,
          error: err.message,
          stdout: output.trim(),
          stderr: errorOutput.trim(),
        });
      });
    });
  },
};
