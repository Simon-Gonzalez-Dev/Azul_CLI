/**
 * Shared streaming utilities for all API providers
 * Consolidates duplicate SSE (Server-Sent Events) parsing logic
 */

/**
 * Parse SSE stream chunks from OpenAI-compatible APIs
 * Handles buffering and partial JSON parsing
 */
export async function parseSSEStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  onToken?: (accumulatedText: string) => void
): Promise<string> {
  const decoder = new TextDecoder();
  let fullResponse = "";
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed === "data: [DONE]") continue;
      if (!trimmed.startsWith("data:")) continue;

      try {
        const payload = JSON.parse(trimmed.slice(5).trim());
        const delta = payload.choices?.[0]?.delta?.content;
        if (delta) {
          fullResponse += delta;
          if (onToken) onToken(fullResponse);
        }
      } catch {
        // Ignore partial chunks - they'll be parsed on next iteration
      }
    }
  }

  return fullResponse;
}

