The system mimics the "nO" (Master Agent Loop) architecture found in Claude Code. It is a recursive state machine that cycles through Think → Act → Observe.

3.1 The Agent Loop (REPL)
Unlike a basic chatbot, this agent operates in a loop:

Capture Input: User types a request.

Context Construction: System combines:

System Prompt (Identity + Tools).

CLAUDE.md (Project rules).

Conversation History (Sliding window).

Inference: Stream request to Ollama.

Decision:

Case A: Model streams text → Render to UI.

Case B: Model requests a tool (e.g., read_file) → Pause & Intercept.

Tool Execution:

Validate arguments with Zod.

Check Permissions (Ask user Y/N for dangerous actions).

Execute (Read file, Run command).

Recursion: Feed the tool result back to the model as a new message and restart step 3.

3.2 The CLAUDE.md Logic
To replicate the "memory" feature:

Startup Scan: On boot, the app checks the current directory for CLAUDE.md.

Injection: The content of this file is wrapped in XML tags (e.g., <project_context>) and appended to the System Prompt.

Persistence: Unlike user messages which may slide out of context, the System Prompt is "pinned" at the start of every request, ensuring the agent never forgets project conventions (e.g., "Always use TypeScript," "Run tests via npm test").

4. UI/UX Implementation Strategy
Claude Code's distinct feel comes from how it handles information density. We replicate this using React components.

4.1 The Main Component Tree
JavaScript
<App>
  <Header />          {/* Project Name, Model Version */}
  <MessageList>       {/* Scrollable History */}
    {history.map(msg => (
      msg.type === 'user'? <UserMessage text={msg.content} /> :
      msg.type === 'tool'? <CollapsibleToolLog tool={msg.name} output={msg.result} /> :
      <AgentMessage text={msg.content} />
    ))}
  </MessageList>
  <StatusLine />      {/* "Thinking...", "Reading file...", "Waiting for input" */}
  <InputArea />       {/* Sticky bottom input */}
</App>
4.2 Collapsible Tool Logs (The "Clean" Look)
Tools like grep or npm test produce massive output. We must not flood the terminal.

Logic: When a tool runs, render a <Box> with a summary: > Executed: npm test (View Output).

State: Use useState(false) for isExpanded.

Interaction: Since terminal clicks are flaky, use keyboard focus or simply default to "Collapsed" and allow the user to use a specialized command (e.g., /logs) to see the last output, OR print only the first 5 lines and truncate the rest with a ... (450 lines hidden) message.

4.3 Streaming Text & "Thinking"
The Spinner: While waiting for the first token, show <Spinner type="dots" />.

The Stream: As chunks arrive from Ollama, append them to a string in useState. React Ink handles the re-rendering.

Tool Interruption: If the stream detects a tool call start, switch the UI from "Streaming Text" to a "Tool Execution" status indicator (e.g., yellow text: Reading src/app.ts...).

5. Tool Implementation (Simplified)
We strip the complex MCP protocol and hardcode these essential tools using Zod for definition.

5.1 ls (File Listing)
Inputs: path (string, optional).

Logic: Uses globby. Crucial: Must ignore .git, node_modules, and lockfiles to prevent context pollution.

5.2 read_file (File Viewer)
Inputs: paths (array of strings).

Logic: Reads file content.

UX Feature: Adds line numbers to the output (1 | import...) so the LLM can reference lines during editing.

5.3 edit_file (The Edit Agent)
Inputs: path, search_string (unique code block), replace_string.

Logic: We avoid "rewrite the whole file" (too slow/expensive) and "line numbers" (too brittle). We use Search & Replace blocks.

Safety: Before applying, compute a diff and show it to the user.

const x = 1;

const x = 2; Apply this change? (Y/n)

5.4 bash (Command Runner)
Inputs: command.

Logic: Runs child_process.spawn.

Safety: Blocking. This tool must pause the loop and require explicit user confirmation unless a --yolo flag is passed at startup.

6. Context Management (Handling Local Limits)
Local models have smaller context windows (e.g., 8k - 32k tokens) compared to Claude's 200k. We need aggressive management.

Sliding Window: Keep the last 10-15 messages.

Tool Output Pruning: If a read_file output is older than 3 turns, replace it with a placeholder: <system>File content hidden to save memory</system>. The model usually retains the understanding of the file from previous turns.

Summarization (Advanced): Every 10 turns, ask a smaller model (like llama3.2:3b) to summarize the conversation history and replace the log with that summary.

7. Implementation Roadmap
Phase 1: The Loop. Build a Node.js script that connects to Ollama, sends a prompt, and prints the stream.

Phase 2: The Tools. Implement read_file and ls. Teach the model to output JSON for tool calls (Ollama handles this natively with recent updates).

Phase 3: The UI. Port the loop to React Ink. Create the distinct visual styles for User vs. Agent.

Phase 4: The Brain. Implement the CLAUDE.md loader and the sliding context window logic.

Phase 5: Safety. Add the "Allow/Deny" confirmation step for tool execution.

This architecture provides the full "Agentic" experience of Claude Code—reading files, making plans, and editing code—while running 100% offline