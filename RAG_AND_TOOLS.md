## Azul CLI – RAG & Tooling Architecture

This document explains how the current Azul CLI agent is set up in terms of **retrieval / search (RAG‑style behavior)** and **tools**, and how the LLM interacts with them.

---

## 1. High‑Level Flow

- **Agent (`agent.ts`)**
  - Maintains the conversation history and orchestrates tool calls.
  - Sends prompts to the active LLM provider via a provider‑agnostic interface.
  - Parses model output using **XML tags**:
    - `<thought>`: internal reasoning / planning.
    - `<tool_code>`: tool invocations with parameters.
  - Executes tools, collects results, and feeds them back into the conversation.
  - Handles **interactive approval** for risky tools (file writes/edits, shell commands).

- **LLM Orchestrator**
  - Wraps multiple providers behind a single interface (`ILLMService`).
  - Chooses between:
    - API providers (Hugging Face, Gemini, Groq, OpenRouter) in a **fallback chain**.
    - Local provider (`node-llama-cpp`) when in local mode.
  - Always streams responses to the UI.
  - Notifies the UI when the active provider/model changes.

- **Tools Layer (`packages/server/src/tools/`)**
  - Exposes a set of **filesystem, search, and shell tools** used for code editing and information retrieval.
  - All tools share a common `ToolDefinition` schema and are registered in `tools/index.ts`.

- **UI Layer (`packages/ui`)**
  - Displays the agent’s thoughts, messages, tool approvals, diffs, and status.
  - Shows the current mode (API vs Local) and active provider/model in the status bar.

---

## 2. Tool System Overview

### 2.1 Tool Definitions and Registry

- **Location**: `packages/server/src/tools/index.ts`
- **Registered tools**:
  - `read_file`
  - `edit_file`
  - `write_file`
  - `list_dir`
  - `execute_command`
  - `search_files`
- Each tool is a `ToolDefinition`:
  - `name`: string identifier used in tool calls.
  - `description`: natural‑language description for the LLM.
  - `parameters`: JSON‑schema‑like object (type, properties, required).
  - `requiresApproval`: whether the UI must prompt the user before execution.
  - `execute(args)`: async function implementing the tool.

The helper `getToolByName(name)` finds tools by name at runtime.

---

### 2.2 Filesystem Tools (`filesystem.ts`)

#### `read_file`
- **Purpose**: Read the contents of a file.
- **Key details**:
  - Parameters: `{ path: string }` (required).
  - Returns `{ success, content }` or `{ success: false, error }`.
  - No approval required (safe, read‑only).

#### `write_file`
- **Purpose**: Create or fully overwrite a file, with **diff preview**.
- **Key details**:
  - Parameters:
    - `path: string` (required).
    - `content: string` (required).
  - Cleans markdown content via `extractCodeFromMarkdown`:
    - Strips surrounding ``` fences if the agent sends code blocks.
  - Ensures parent directories exist (`fs.mkdir(..., { recursive: true })`).
  - If the file existed:
    - Reads old content.
    - Writes new content.
    - Computes a **human‑readable diff** via `computeDiff(oldContent, newContent)`:
      - Line‑by‑line diff with context.
      - Counts of `added` and `removed` lines.
      - Truncates very large diffs.
  - Returns metadata: `filePath`, `fileExists`, `diff`, `added`, `removed`, `changed`.
  - **requiresApproval: true** → the UI shows a diff (via `PermissionModal` + `DiffView`) and asks the user to approve.

#### `edit_file`
- **Purpose**: **Surgical** search & replace edits, safer than rewriting entire files.
- **Key details**:
  - Parameters:
    - `path: string`
    - `search: string` – exact block to find (whitespace‑sensitive).
    - `replace: string` – new block.
  - Normalizes line endings (`\r\n` → `\n`) for both file and search block.
  - If `normalizedContent.includes(normalizedSearch)`:
    - Replaces the first occurrence.
    - Writes the new content.
    - Computes a diff using `computeDiff(normalizedSearch, replace)` to show what changed.
  - If the search block is not found:
    - Returns `success: false` with a **guidance message**:
      - Tells the agent to `read_file` first to match exact whitespace.
  - **requiresApproval: true** with diff shown in the UI.

#### `list_dir`
- **Purpose**: List the contents of a directory.
- **Key details**:
  - Parameters: `{ path: string }` (required).
  - Returns a list of items with `name`, `isDirectory`, `isFile`.
  - No approval required.

#### `computeDiff` (shared utility)
- **Purpose**: Lightweight diff for human review.
- **Behavior**:
  - Splits old and new content into lines.
  - Tracks `added` and `removed` line counts.
  - Includes a few lines of context around changes.
  - Limits diff length to avoid huge payloads.
  - Returns `{ added, removed, diff }`.

This function is used by both `write_file` and `edit_file` to power the interactive diff workflow.

---

### 2.3 Search / RAG‑Style Tooling (`search.ts`)

#### `search_files`
- **Purpose**: Text search across files (similar to `grep`), used as a **lightweight retrieval mechanism**.
- **Key details**:
  - Parameters:
    - `pattern: string` (required) – text or simple pattern to look for.
    - `path?: string` (optional) – root directory (defaults to `"."`).
  - Implementation:
    - Uses `grep -rn -I`:
      - `-r`: recursive.
      - `-n`: include line numbers.
      - `-I`: skip binary files.
    - Errors from `grep` (like “no matches”) are suppressed (`... || true`).
  - Post‑processing:
    - Splits `stdout` into lines, filters empty lines.
    - Limits to first **50 results**.
    - Returns:
      - `results`: array of `file:line:content` strings.
      - `count`: number of results included.
      - `truncated`: whether there were more than 50 matches.
  - **requiresApproval: false** (safe, read‑only).

> **Note on RAG**:  
> The current system does **not** use vector embeddings or a semantic index.  
> Instead, it relies on `search_files` (grep‑based search) + `read_file` to implement a **keyword‑driven retrieval‑augmented workflow**:
> - Agent searches for relevant code or docs with `search_files`.
> - Then reads specific files/segments with `read_file`.
> - Uses that retrieved content to plan edits or answer questions.

This provides a simple, fast, and provider‑agnostic retrieval layer that works both locally and with API models.

---

### 2.4 Shell Tool with Timeout (`shell.ts`)

#### `execute_command`
- **Purpose**: Run shell commands (builds, tests, linters, small scripts) with **automatic timeout** for long‑running processes.
- **Key details**:
  - Parameters:
    - `command: string` (required).
    - `cwd?: string` (optional working directory, defaults to `process.cwd()`).
  - Implementation:
    - Uses `spawn("sh", ["-c", command])`:
      - This avoids manual argument parsing and leverages the shell for pipelines, etc.
    - Captures `stdout` and `stderr` incrementally.
    - Listens for `close` to resolve with:
      - `success: true` if exit code `0`.
      - `success: false` if non‑zero exit code, including the captured output.
    - **Timeout**:
      - A timer (currently **5000 ms**) kills the process if it runs too long.
      - On timeout:
        - The process is terminated.
        - The tool resolves with:
          - `success: true` (treated as a controlled condition, not a hard failure).
          - `stdout` / `stderr` up to that point.
          - A `message` explaining the timeout and that this is expected for servers/watchers.
    - Handles process startup errors via the `error` event.
  - **requiresApproval: true** (shell access is sensitive).

#### Agent‑Level Guidance for `execute_command`
- The system prompt in `agent.ts` includes explicit instructions:
  - If a command starts a long‑running process (e.g., `npm run dev`):
    - The tool will run it briefly and **stop it** to capture initial logs.
    - If the returned logs show the server is running/ready, the agent should **treat the task as successful**.
    - The agent should **not** attempt to keep servers running indefinitely; just verify they start cleanly.

This prevents the agent from hanging on long‑running commands while still giving it enough information to validate behavior.

---

## 3. Agent Prompting & Tool Calling Protocol

### 3.1 XML‑Based Tool Calls

- The agent’s system prompt (in `agent.ts`) enforces a **strict XML format**:
  - All reasoning must be inside:
    - `<thought> ... </thought>`
  - All tool calls must be inside:
    - `<tool_code> ... </tool_code>`
  - Each tool call block contains:
    - `<tool_name>tool_name_here</tool_name>`
    - `<parameters> ... </parameters>` with one XML tag per parameter:
      - Example structure (conceptual, enforced via placeholders in the prompt):
        - `<path>...</path>`
        - `<pattern>...</pattern>`
        - `<command>...</command>`
  - **No text is allowed outside `<thought>` or `<tool_code>`**; such text is ignored.
  - The prompt also stresses:
    - All listed tool parameters are **required**.
    - The agent must fill all placeholders (`<parameter_name>`) with actual values.

### 3.2 Parsing Logic

- The agent parses model responses with a **hybrid parser**:
  - Primary path:
    - Extract `<thought>` content.
    - Scan for all `<tool_code>` blocks.
    - For each block:
      - Extract `tool_name`.
      - Parse each `<param>value</param>` inside `<parameters>` into a plain object.
  - Fallback path (for robustness):
    - If no XML is found, it can detect an older `Tool calls: [...]` JSON pattern and parse it.
    - This exists only to avoid hard failures with misbehaving models; the prompt tries hard to keep everything in XML.

This XML protocol is **provider‑agnostic** and works uniformly across local and API models.

---

## 4. RAG Behavior in Practice

While there is no dedicated vector database yet, the combination of tools effectively enables **retrieval‑augmented behavior**:

- **Discovery Phase**
  - Use `list_dir` to understand the project structure.
  - Use `search_files` to locate relevant code, configuration, or documentation by keyword.

- **Retrieval Phase**
  - After narrowing down candidate files, use `read_file` to pull full content into context.
  - The agent can re‑use snippets in its reasoning and tools (e.g., `edit_file`).

- **Editing / Refactoring Phase**
  - Use `edit_file` for localized patches with a safe diff and approval.
  - Use `write_file` for creating new files or completely rewriting small ones.

- **Verification Phase**
  - Use `execute_command` to run builds, tests, linters.
  - Use `search_files` and `read_file` again if errors appear, to inspect logs or error locations.

This pattern gives you a **codebase‑aware agent** without requiring any model‑ or provider‑specific features.

---

## 5. Safety & UX Features

- **Approval workflow**
  - Tools that can modify disk or run arbitrary commands (`write_file`, `edit_file`, `execute_command`) require approval.
  - The UI shows:
    - Tool name and arguments.
    - For file writes/edits: a full diff (`DiffView`) with counts of added/removed lines.

- **Silent Actor Pattern**
  - Tools run “silently” in the background from the model’s perspective.
  - The UI summarizes:
    - Which tools ran.
    - Whether they succeeded.
    - High‑signal outputs (like diffs or command logs).

- **Timeouts for Commands**
  - Prevents accidental long‑running or stuck processes from blocking the agent.
  - Still surfaces enough output for debugging and validation.

---

## 6. Extending RAG & Tools

Given the current design, adding more advanced RAG or tools is straightforward:

- **Vector RAG**:
  - Implement a new tool (e.g., `semantic_search`) that queries an embedding index.
  - Keep the same `ToolDefinition` pattern so it plugs into the existing XML tool‑calling flow.

- **Additional Utilities**:
  - Formatters, test runners, HTTP clients, etc. can be added as new tools in `tools/`.
  - Each should:
    - Define clear parameters and descriptions.
    - Declare `requiresApproval` appropriately.
    - Return structured, concise results optimized for the model to reason about.

The existing architecture (XML tools + provider‑agnostic LLM interface + orchestrator + approval UI) is designed to support these future extensions cleanly.


