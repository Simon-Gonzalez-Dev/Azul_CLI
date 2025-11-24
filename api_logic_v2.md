Azul V2: The "Silent Actor" Architecture
1. The Core Shift: Thought vs. Action
Currently, your agent treats "Tool Calls" as just another part of the text generation. We need to decouple them using Native Function Calling (supported by OpenAI, Anthropic, and others).
The New Loop Logic
Instead of User -> Prompt -> Text Response, the loop becomes:
User Input
LLM Decision:
Option A (Talk): Return text to user.
Option B (Act): Return a Tool Call Object (no text).
Client/Server Action: Execute tool.
Recursion: Feed tool result back to LLM automatically.
The Efficiency Fix (Prompting)
You must explicitly forbid the AI from outputting code in the chat if it intends to use a tool.
New System Prompt Injection:
code
Text
When you edit files, DO NOT output the code updates in the chat. 
Directly call the `edit_file` tool. 
Only speak to the user to explain WHAT you did or if you need clarification.
2. The "Search & Replace" Protocol (Crucial)
Stop using write_file (overwriting the whole file). It is slow, dangerous, and token-heavy. You need a Search & Replace tool.
New Tool: edit_file
This tool allows the agent to surgically patch files.
Schema:
code
TypeScript
{
  name: "edit_file",
  description: "Replace a unique block of text with a new block.",
  parameters: {
    path: "string (path to file)",
    search: "string (exact unique code block to locate)",
    replace: "string (new code block to insert)"
  }
}
Why this works better:
Token Savings: If updating 5 lines in a 1000-line file, the agent sends ~10 lines of tokens instead of 1000.
Reliability: It prevents the "Lazy AI" problem where the AI writes // ... rest of code and accidentally deletes your file content.
3. The Re-Architected Implementation
Here is how you rewrite the code to handle this efficiency.
Step A: Refactor Agent.ts (The Loop)
Don't just append strings. Use a structured message array.
code
TypeScript
// packages/server/src/agent.ts

export async function runAgentLoop(userMessage: string, history: Message[]) {
  const messages = [...history, { role: "user", content: userMessage }];
  let isFinished = false;

  while (!isFinished) {
    // 1. Call LLM with Tools
    const response = await llm.chat({
      messages,
      tools: TOOL_DEFINITIONS,
      tool_choice: "auto" 
    });

    const { content, tool_calls } = response.message;

    // 2. If the AI wants to talk, stream it to UI
    if (content) {
      server.sendToUi({ type: "text", content });
      messages.push({ role: "assistant", content });
    }

    // 3. If no tools, we are done
    if (!tool_calls || tool_calls.length === 0) {
      isFinished = true;
      break;
    }

    // 4. Handle Tools SILENTLY (Don't print code to user)
    messages.push({ role: "assistant", content: null, tool_calls });
    
    for (const tool of tool_calls) {
      // Notify UI we are working (but don't show the huge payload)
      server.sendToUi({ type: "status", status: `Running ${tool.name}...` });

      // Execute
      const result = await executeTool(tool.name, tool.arguments);

      // Add result to history
      messages.push({
        role: "tool",
        tool_call_id: tool.id,
        content: JSON.stringify(result) 
      });
    }
    // Loop repeats automatically with new tool results
  }
}
Step B: The Server-Side Patcher (edit_file)
Implement this logic in your tool execution layer.
code
TypeScript
// packages/server/src/tools/fileTools.ts

import fs from 'fs/promises';

export async function editFile({ path, search, replace }) {
  const content = await fs.readFile(path, 'utf-8');

  // Normalizing line endings is crucial for AI matching
  const normalizedContent = content.replace(/\r\n/g, '\n');
  const normalizedSearch = search.replace(/\r\n/g, '\n');

  if (normalizedContent.includes(normalizedSearch)) {
    // Perform replacement
    const newContent = normalizedContent.replace(normalizedSearch, replace);
    await fs.writeFile(path, newContent);
    return { success: true, message: "Patch applied successfully." };
  } else {
    // Smart Failure: Help the AI fix its mistake
    return { 
      success: false, 
      error: "Search block not found. Ensure whitespace matches exactly or use `read_file` to verify context." 
    };
  }
}
4. Expected Result (Comparison)
OLD Flow (Your Logs)
User: Fix the header.
Azul: Here is the fixed header: <header>... 20 lines ...</header>
Azul: Calls write_file with 2000 lines of code.
UI: Scrolls wildly.
Cost: 4000 tokens.
NEW Flow (Agentic)
User: Fix the header.
Azul (Internal Thought): I need to replace the header block.
Azul (Tool): edit_file(path="index.html", search="<header>Old...</header>", replace="<header>New...</header>")
Server: Patches file.
Azul (Text): I've updated the header styling for you.
Cost: 150 tokens.
5. Immediate Action Plan
Stop the Echo: In your UI (packages/ui/src/App.tsx), stop rendering the tool inputs/outputs by default. Only render message.content from the assistant. Use a small "Spinner" or "Status Bar" for tool usage.
Update System Prompt: Add the "Silent Editing" instruction found in Section 1.
Implement edit_file: Add the patch logic from Section 3.
Switch to Native Tools: If you are using OpenAI/Anthropic SDKs, switch from prompt engineering to client.chat.completions.create({ tools: [...] }).