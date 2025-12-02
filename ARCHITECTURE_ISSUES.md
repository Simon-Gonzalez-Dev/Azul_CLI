# Architecture Issues Analysis

## Critical Issues Hindering Desired Architecture

### 1. **Dual Streaming Message Types - Complexity & Duplication**

**Location:** `agent.ts` lines 341-351, 371-382, `App.tsx` lines 83-146

**Problem:**
- Two separate message types: `agent_thought_stream` and `agent_response_stream`
- UI must merge them, creating complex state management
- No single source of truth for streaming state
- Race conditions possible when both update simultaneously

**Impact:**
- Duplication of thoughts/responses
- Complex UI logic to find and merge messages
- Potential for bugs when messages arrive out of order

**Solution:**
- Single unified `agent_stream` message type with `thought` and `content` fields
- Single update path in UI
- Clear state machine for streaming lifecycle

---

### 2. **Incomplete Local Provider Streaming**

**Location:** `local.ts` lines 83-89

**Problem:**
- `onToken` callback has comment "safety net" but doesn't actually call `onToken`
- Relies entirely on `onTextChunk` which might not fire for every token
- Small chunks might be missed

**Impact:**
- Streaming might skip tokens for local models
- Inconsistent streaming behavior
- Not truly "always active"

**Solution:**
- Actually implement the safety net in `onToken`
- Ensure every token triggers streaming callback
- Add debouncing/throttling at UI level if needed, not provider level

---

### 3. **Multiple Completion Markers - State Confusion**

**Location:** `agent.ts` lines 363-383, 422-432

**Problem:**
- Completion marked multiple times:
  - `isComplete: true` sent in `agent_response_stream`
  - Final `agent_response` message sent separately
  - UI tries to merge but logic is complex

**Impact:**
- Duplicate final messages
- Confusion about when streaming actually completes
- Tool execution might start before streaming visually completes

**Solution:**
- Single completion event
- Clear state transition: streaming → complete → tools execute
- Remove redundant `agent_response` message type

---

### 4. **Tool Execution Not Visible During Streaming**

**Location:** `agent.ts` lines 405-415

**Problem:**
- Tools execute AFTER streaming completes
- User sees streaming, then suddenly tools appear
- No indication during streaming that tools will execute
- Tool results appear disconnected from the thought/response

**Impact:**
- Poor UX - user doesn't see what's happening
- Tools feel disconnected from the conversation
- No real-time feedback during tool execution

**Solution:**
- Parse tool calls DURING streaming (real-time XML parsing)
- Show tool calls as they're detected in stream
- Execute tools while still showing streaming indicator
- Integrate tool results into the streaming message flow

---

### 5. **Complex UI Message Finding Logic**

**Location:** `App.tsx` lines 114-146

**Problem:**
- Multiple `findIndex` calls to locate streaming messages
- Different logic for `agent_thought_stream` vs `agent_response_stream`
- Searches backwards through array (O(n) complexity)
- Potential for finding wrong message if multiple streams exist

**Impact:**
- Performance issues with many messages
- Bugs when multiple streams exist
- Hard to maintain and debug

**Solution:**
- Use message IDs or timestamps for direct lookup
- Maintain a map of active streams
- Single update function for all streaming messages

---

### 6. **Empty Message Filtering in Render**

**Location:** `LogView.tsx` lines 128-131

**Problem:**
- Empty streaming messages filtered in render, not state
- Messages still exist in state array
- Causes unnecessary re-renders
- State becomes polluted with empty messages

**Impact:**
- Performance degradation
- Memory waste
- Confusing state

**Solution:**
- Filter empty messages in state management
- Don't add empty messages to state
- Clean up empty messages when streaming completes

---

### 7. **Legacy Message Types Still Present**

**Location:** `LogView.tsx` line 43, `agent.ts` line 310

**Problem:**
- `agent_thought` (legacy) still handled separately
- `agent_thinking` still used for clearing
- Multiple code paths for same functionality

**Impact:**
- Code complexity
- Potential for bugs
- Inconsistent behavior

**Solution:**
- Remove legacy types
- Use unified streaming types only
- Single code path for all agent output

---

### 8. **Error Retry Logic Adds to History**

**Location:** `agent.ts` lines 442-463

**Problem:**
- Invalid XML responses add correction messages to conversation history
- Could cause infinite retry loops
- Error messages pollute conversation context
- No limit on retries

**Impact:**
- Potential infinite loops
- Conversation history pollution
- Token waste
- Poor error recovery

**Solution:**
- Limit retry attempts (max 2-3)
- Don't add system correction messages to history
- Better error messages to user
- Fallback to showing raw response if parsing fails repeatedly

---

### 9. **Path Resolution Inconsistency**

**Location:** `agent.ts` line 640, `tools/filesystem.ts` resolvePath functions

**Problem:**
- Tools handle path resolution internally
- Agent removed path resolution code
- But tools might receive unresolved paths
- Inconsistent behavior

**Impact:**
- Potential path resolution bugs
- Tools might fail with relative paths
- Confusion about where resolution happens

**Solution:**
- Clear contract: tools always receive resolved paths OR tools always resolve
- Document which layer handles resolution
- Consistent behavior across all tools

---

### 10. **Streaming Content Shows Raw XML**

**Location:** `LogView.tsx` lines 143-148

**Problem:**
- Streaming shows raw XML (`<thought>`, `<tool_code>` tags)
- Not user-friendly
- Should parse and display formatted content

**Impact:**
- Poor UX - users see XML tags
- Not aesthetic
- Confusing for non-technical users

**Solution:**
- Parse XML during streaming
- Display formatted thought and tool calls
- Hide XML structure from user
- Show tool calls as they're detected

---

### 11. **No Real-time Tool Call Detection**

**Location:** `agent.ts` lines 319-328

**Problem:**
- `parseStreamingContent` only checks for `hasToolCode` boolean
- Doesn't actually parse tool calls during streaming
- Tools only parsed after streaming completes

**Impact:**
- Can't show tool calls during streaming
- No preview of what tools will execute
- User waits without feedback

**Solution:**
- Parse tool calls in real-time during streaming
- Show tool calls as they're detected
- Execute tools as soon as complete tool call is parsed
- Don't wait for full response

---

### 12. **Token Stats Update Separately**

**Location:** `agent.ts` lines 385-396, `App.tsx` lines 69-82

**Problem:**
- Token stats sent as separate message type
- Not integrated with streaming
- Appears disconnected from the response

**Impact:**
- Stats feel separate from content
- Not part of unified streaming experience
- Could appear before/after streaming completes

**Solution:**
- Include stats in streaming message
- Update stats in real-time during streaming
- Show stats as part of the response, not separate

---

### 13. **No Stream State Machine**

**Location:** Throughout `agent.ts` and `App.tsx`

**Problem:**
- No clear state machine for streaming lifecycle
- States: idle → streaming → complete → tools → done
- Current code mixes these states

**Impact:**
- Hard to reason about state
- Bugs when state transitions incorrectly
- No clear completion signal

**Solution:**
- Implement explicit state machine
- Clear transitions between states
- Single source of truth for stream state

---

### 14. **Approval Request Blocks Streaming**

**Location:** `agent.ts` lines 652-670

**Problem:**
- Approval requests block tool execution
- But streaming might still be active
- No clear indication that approval is needed
- User might miss approval request

**Impact:**
- Poor UX during approval
- Streaming and approval feel disconnected
- Tools wait indefinitely

**Solution:**
- Show approval request during streaming
- Integrate approval into streaming UI
- Clear visual indication when approval needed

---

### 15. **Multiple Message Updates Per Token**

**Location:** `agent.ts` lines 331-354

**Problem:**
- Every token update sends TWO messages:
  - `agent_thought_stream` (if thought changed)
  - `agent_response_stream` (always)
- Causes double state updates
- Performance impact

**Impact:**
- Unnecessary re-renders
- Performance degradation
- Complex state management

**Solution:**
- Single message per token update
- Batch updates if needed
- Single state update path

---

## Summary of Required Changes

### High Priority (Architecture Breaking)
1. Unify streaming message types (single `agent_stream` type)
2. Fix local provider streaming (ensure every token streams)
3. Real-time tool call parsing during streaming
4. Remove legacy message types
5. Implement stream state machine

### Medium Priority (UX Improvements)
6. Parse and format XML during streaming (hide raw XML)
7. Show tool calls during streaming
8. Integrate token stats into streaming
9. Filter empty messages in state, not render
10. Simplify UI message finding logic

### Low Priority (Polish)
11. Limit error retry attempts
12. Consistent path resolution
13. Integrate approval into streaming UI
14. Single message update per token
15. Clear completion handling

---

## Recommended Refactoring Order

1. **Phase 1: Unify Streaming**
   - Create single `agent_stream` message type
   - Update agent to send unified messages
   - Update UI to handle unified messages
   - Remove legacy types

2. **Phase 2: Real-time Parsing**
   - Parse XML during streaming
   - Detect tool calls in real-time
   - Show tool calls as detected
   - Execute tools as soon as complete

3. **Phase 3: State Machine**
   - Implement explicit state machine
   - Clear state transitions
   - Single source of truth

4. **Phase 4: Polish**
   - Format XML output
   - Integrate stats
   - Improve error handling
   - Performance optimizations

