import { exec } from "child_process";
import { promisify } from "util";
import { ToolDefinition } from "../types.js";

const execAsync = promisify(exec);

export const executeCommandTool: ToolDefinition = {
  name: "execute_command",
  description: "Execute a shell command and return the output",
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
    try {
      const options = args.cwd ? { cwd: args.cwd } : {};
      const { stdout, stderr } = await execAsync(args.command, options);
      return {
        success: true,
        stdout: stdout.trim(),
        stderr: stderr.trim(),
      };
    } catch (error: any) {
      return {
        success: false,
        error: error.message,
        stdout: error.stdout?.trim() || "",
        stderr: error.stderr?.trim() || "",
      };
    }
  },
};

