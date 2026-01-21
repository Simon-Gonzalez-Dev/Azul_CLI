import { spawn } from "child_process";
import { ToolDefinition, ToolContext } from "../types.js";

// ============================================================================
// BASH SANDBOXING - Safety filters for shell commands
// ============================================================================

// BLOCKED - Extremely dangerous commands that will NOT execute
const BLOCKED_COMMANDS = [
  'rm -rf /',
  'rm -rf ~',
  'rm -rf *',
  'rm -rf .',
  'dd if=/dev',
  'mkfs.',
  ':(){:|:&};:',           // Fork bomb
  '> /dev/sda',
  '> /dev/hda',
  'chmod -R 777 /',
  'chown -R',
  'mv / ',
  'mv /* ',
  ':(){ :|:& };:',         // Fork bomb variant
  'wget http',             // Prevent arbitrary downloads (basic)
  'curl http',             // Prevent arbitrary downloads (basic)
];

// BLOCKED - Interactive commands that would hang the agent
const INTERACTIVE_BLOCKED = [
  'vim',
  'vi',
  'nano',
  'emacs',
  'pico',
  'less',
  'more',
  'man',
  'top',
  'htop',
  'ssh',
  'telnet',
  'ftp',
  'sftp',
  'mysql',
  'psql',
  'mongo',
  'redis-cli',
  'python',     // Interactive REPL
  'python3',    // Interactive REPL
  'node',       // Interactive REPL (without args)
  'irb',        // Ruby REPL
  'ghci',       // Haskell REPL
];

// HIGH RISK - Commands that require extra confirmation
const HIGH_RISK_PATTERNS = [
  /^sudo\s/,
  /rm\s+-rf/,
  /rm\s+-r\s/,
  /rm\s+--recursive/,
  /chmod\s+777/,
  /chmod\s+-R/,
  /chown\s/,
  /mkfs\./,
  /dd\s+if=/,
  />\s*\/dev\//,
  /format\s/i,
  /shutdown/,
  /reboot/,
  /init\s+0/,
  /init\s+6/,
  /systemctl\s+(stop|disable|mask)/,
  /launchctl\s+(unload|remove)/,
  /kill\s+-9/,
  /killall/,
  /pkill/,
];

// Categorize command risk level
export interface CommandRisk {
  level: 'blocked' | 'high' | 'medium' | 'low';
  reason?: string;
}

export function categorizeCommand(command: string): CommandRisk {
  const trimmedCmd = command.trim().toLowerCase();
  const cmdParts = trimmedCmd.split(/\s+/);
  const baseCmd = cmdParts[0];

  // Check blocked commands
  for (const blocked of BLOCKED_COMMANDS) {
    if (trimmedCmd.includes(blocked.toLowerCase())) {
      return {
        level: 'blocked',
        reason: `Command contains blocked pattern: "${blocked}"`,
      };
    }
  }

  // Check interactive commands
  for (const interactive of INTERACTIVE_BLOCKED) {
    if (baseCmd === interactive || trimmedCmd.startsWith(interactive + ' ')) {
      // Allow non-interactive uses like 'python script.py' or 'node file.js'
      if ((baseCmd === 'python' || baseCmd === 'python3' || baseCmd === 'node') && cmdParts.length > 1) {
        continue;
      }
      return {
        level: 'blocked',
        reason: `Interactive command "${interactive}" not supported`,
      };
    }
  }

  // Check high risk patterns
  for (const pattern of HIGH_RISK_PATTERNS) {
    if (pattern.test(command)) {
      return {
        level: 'high',
        reason: `Command matches high-risk pattern`,
      };
    }
  }

  // Check for write/modify operations (medium risk)
  const writePatterns = [
    /\s+>\s+/,           // Redirect to file
    /\s+>>\s+/,          // Append to file
    /\brm\b/,            // Any rm command
    /\bmv\b/,            // Any mv command
    /\bcp\b.*-[rf]/,     // cp with recursive/force flags
    /\bnpm\s+(install|uninstall|update)/,
    /\byarn\s+(add|remove)/,
    /\bgit\s+(push|reset|checkout|rebase)/,
    /\bmake\s+install/,
  ];

  for (const pattern of writePatterns) {
    if (pattern.test(command)) {
      return {
        level: 'medium',
        reason: `Command may modify files or system state`,
      };
    }
  }

  // Default to low risk for read-only commands
  return { level: 'low' };
}

// ============================================================================
// TOOL: bash - Execute shell commands (Claude Code style with sandboxing)
// ============================================================================
export const bashTool: ToolDefinition = {
  name: "bash",
  description: "Execute a shell command. Some dangerous commands are blocked. Long-running commands will timeout after 30 seconds.",
  parameters: {
    type: "object",
    properties: {
      command: {
        type: "string",
        description: "The shell command to execute",
      },
    },
    required: ["command"],
  },
  requiresApproval: true,
  async execute(args: { command: string }, context?: ToolContext) {
    const timeoutMs = 30000; // 30 second timeout
    const cwd = context?.workingDirectory || process.cwd();

    // Check command safety
    const risk = categorizeCommand(args.command);

    if (risk.level === 'blocked') {
      return {
        success: false,
        error: `Command blocked: ${risk.reason}`,
        blocked: true,
        riskLevel: 'blocked',
      };
    }

    return new Promise((resolve) => {
      let output = "";
      let errorOutput = "";
      let completed = false;

      // Use sh -c to run the command
      const child = spawn("sh", ["-c", args.command], {
        cwd,
        shell: false,
        stdio: ["ignore", "pipe", "pipe"],
      });

      // Capture output
      child.stdout?.on("data", (data) => {
        output += data.toString();
      });
      child.stderr?.on("data", (data) => {
        errorOutput += data.toString();
      });

      // Handle process exit
      child.on("close", (code) => {
        if (completed) return;
        completed = true;

        if (code === 0) {
          resolve({
            success: true,
            stdout: output.trim(),
            stderr: errorOutput.trim(),
            message: "Command completed successfully",
            riskLevel: risk.level,
          });
        } else {
          resolve({
            success: false,
            stdout: output.trim(),
            stderr: errorOutput.trim(),
            error: `Command failed with exit code ${code}`,
            riskLevel: risk.level,
          });
        }
      });

      // Handle timeout
      const timer = setTimeout(() => {
        if (completed) return;

        child.kill();
        completed = true;

        resolve({
          success: true,
          stdout: output.trim(),
          stderr: errorOutput.trim(),
          message: `Command timed out after ${timeoutMs / 1000}s. Partial output captured.`,
          timedOut: true,
          riskLevel: risk.level,
        });
      }, timeoutMs);

      // Handle startup errors
      child.on("error", (err) => {
        if (completed) return;
        completed = true;
        clearTimeout(timer);
        resolve({
          success: false,
          error: err.message,
          stdout: output.trim(),
          stderr: errorOutput.trim(),
          riskLevel: risk.level,
        });
      });
    });
  },
};

// Legacy export for backwards compatibility during transition
export const executeCommandTool = bashTool;
