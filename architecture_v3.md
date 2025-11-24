1. Core Architecture: The Unified "Agent Loop"
Requirement: The application logic must be identical for both Local Models and APIs. The agent must be a recursive state machine, not a linear chain.
Abstraction Layer: Create an LLMProvider interface. The core loop sends messages[] and receives AgentAction.
The Loop:
User Input -> History.
while (goal_not_reached):
Send history to LLM.
Parser Layer: Intercept response.
Decision:
If ToolCall: Execute Tool -> Auto-feed result to History -> Continue Loop immediately (No user interaction).
If Text: Stream to UI -> Wait for user input.
Goal Persistence: The agent MUST NOT STOP after a single tool execution. It continues looping until it explicitly decides the user's request is satisfied.
2. Robustness & Parsing (The "Local Model" Fix)
Problem: Local models often output Markdown (```json) or conversational filler ("Here is the code") which breaks execution.
Solution: Implement an Aggressive Response Parser.
Sanitization: Before parsing JSON, use Regex to strip all Markdown code blocks (```json ... ```) and surrounding text.
Extraction: Locate the first { and last } to isolate the JSON object.
Error Recovery: If JSON.parse fails, automatically feed a "System Error" message back to the LLM context: "Invalid JSON format. Please output RAW JSON only." and retry the loop.
3. The "Perfect" System Prompt
Embed a system prompt that enforces strict behavioral protocols:
Silent Operator: Do not chat. Do not say "I will now read the file." Just call the tool.
Ambiguity Protocol: If the user says "fix the bug" and no file is specified, DO NOT ASK. Use ls and read_file to find it yourself.
Surgical Editing: Forbid write_file for existing files. Mandate edit_file (Search & Replace) to prevent overwriting/truncation.
Format Compliance: Explicitly forbid Markdown formatting in JSON outputs.
4. UI/UX & Streaming (Ink)
Requirement: A clean, stable, hacker-style terminal UI.
Sticky Header: Keep the Azul Logo/Status bar at the very top. Ensure no whitespace drift (clearing console properly on renders).
Streaming Pipeline: All LLM tokens must stream to the UI in real-time.
State Management: Use a reducer pattern to handle the complex state of the conversation history + current tool execution status.
5. The "Interactive Diff" Workflow
Requirement: Safe execution of dangerous commands.
Classification:
Safe Tools (ls, read_file, search, grep): Execute automatically without user prompt.
Side-Effect Tools (edit_file, run_shell, write_file): REQUIRE CONFIRMATION.
The Diff View Component:
When edit_file is proposed, pause the loop.
Render a Diff View in the CLI:
Red lines (-) for removed code.
Green lines (+) for added code.
User presses [y] Accept or [n] Reject.
Post-Action: Upon acceptance, collapse the diff view into a single line summary (e.g., ✔ Updated src/app.ts) to keep the terminal clean.