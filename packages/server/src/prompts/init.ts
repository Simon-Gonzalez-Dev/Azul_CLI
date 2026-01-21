/**
 * Prompt template for /init command
 * Instructs the agent to analyze the project and generate AZUL.md
 */

export const INIT_PROMPT = `You are generating an AZUL.md file for this project. This file will be loaded into your context whenever you work on this project.

## Your Task

Analyze this project and create a helpful AZUL.md file that contains:
1. Project overview and purpose
2. Build and run commands
3. Key architecture decisions
4. Coding conventions and patterns
5. Important files and their purposes

## Steps to Follow

1. **Explore the project structure:**
   - Use \`ls\` to see the root directory
   - Look for configuration files (package.json, tsconfig.json, etc.)

2. **Read key files:**
   - Use \`view\` to read package.json (dependencies, scripts)
   - Read any existing README.md or documentation
   - Check configuration files to understand the tech stack

3. **Analyze what you find:**
   - Identify the language/framework (Node.js, Python, etc.)
   - Note the project structure (monorepo, src folder, etc.)
   - Extract build/test/run commands from scripts
   - Understand testing approach if tests exist

4. **Generate AZUL.md:**
   Create a file with these sections:

   \`\`\`markdown
   # AZUL.md

   ## Project Overview
   [Brief description - 1-2 sentences about what this project does]

   ## Tech Stack
   - [List key technologies]

   ## Build Commands
   \`\`\`bash
   npm install    # Install dependencies
   npm run build  # Build the project
   npm run test   # Run tests
   \`\`\`

   ## Architecture
   [Key directories and their purposes]

   ## Coding Guidelines
   [Patterns and conventions observed in the codebase]

   ## Key Files
   - [Important files an AI should know about]
   \`\`\`

5. **Write the file:**
   Use the \`write\` tool to create AZUL.md in the project root.

## Guidelines

- Keep it concise but informative (50-100 lines ideal)
- Focus on information that helps you (the AI) work effectively
- Include actual commands from package.json, not placeholders
- Don't include information you don't find - omit sections if not applicable
- Use @import syntax if you want to split into multiple files (e.g., \`@./docs/conventions.md\`)

Now begin by exploring the project structure.`;

/**
 * Creates the full init message for the agent
 * @param workingDirectory - The current working directory
 */
export function createInitMessage(workingDirectory: string): string {
  return `${INIT_PROMPT}

## Current Directory
${workingDirectory}

Begin by using \`ls\` to explore the project structure.`;
}
