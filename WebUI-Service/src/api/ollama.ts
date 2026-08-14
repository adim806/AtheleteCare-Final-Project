import { OLLAMA_SYSTEM_PROMPT } from "../prompts/ollamaSystem";

export type ChatMessage = {
  role: "system" | "user" | "assistant";
  content: string;
};

function buildMessages(
  history: { role: "user" | "assistant"; content: string }[],
  userMessage: string,
): ChatMessage[] {
  return [
    { role: "system", content: OLLAMA_SYSTEM_PROMPT },
    ...history,
    { role: "user", content: userMessage },
  ];
}

function ollamaError(status: number, body: string, model: string): Error {
  return new Error(
    `Ollama error ${status}: ${body || "request failed"}. Is Ollama running (ollama serve) with model "${model}"?`,
  );
}

/** Non-streaming fallback (kept for tests / simple callers). */
export async function chatWithOllama(
  history: { role: "user" | "assistant"; content: string }[],
  userMessage: string,
): Promise<string> {
  const model = import.meta.env.VITE_OLLAMA_MODEL || "llama3";
  const res = await fetch("/api/ollama/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model,
      messages: buildMessages(history, userMessage),
      stream: false,
    }),
  });

  if (!res.ok) {
    throw ollamaError(res.status, await res.text(), model);
  }

  const data = (await res.json()) as { message?: { content?: string } };
  const content = data.message?.content?.trim();
  if (!content) throw new Error("Ollama returned an empty message.");
  return content;
}

/**
 * Stream Ollama chat tokens. Calls `onChunk` with accumulated text as tokens arrive.
 * Returns the full trimmed response when the stream completes.
 */
export async function streamChatWithOllama(
  history: { role: "user" | "assistant"; content: string }[],
  userMessage: string,
  onChunk: (accumulated: string) => void,
  signal?: AbortSignal,
): Promise<string> {
  const model = import.meta.env.VITE_OLLAMA_MODEL || "llama3";
  const res = await fetch("/api/ollama/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model,
      messages: buildMessages(history, userMessage),
      stream: true,
    }),
    signal,
  });

  if (!res.ok) {
    throw ollamaError(res.status, await res.text(), model);
  }

  if (!res.body) {
    throw new Error("Ollama returned no response body for streaming.");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let full = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;

        let parsed: { message?: { content?: string }; done?: boolean };
        try {
          parsed = JSON.parse(trimmed) as typeof parsed;
        } catch {
          continue;
        }

        const piece = parsed.message?.content ?? "";
        if (piece) {
          full += piece;
          onChunk(full);
        }
      }
    }
  } catch (e) {
    if (signal?.aborted) {
      const partial = full.trim();
      if (partial) return partial;
      throw e;
    }
    throw e;
  } finally {
    reader.releaseLock();
  }

  if (signal?.aborted) {
    const partial = full.trim();
    if (partial) return partial;
    throw new DOMException("Aborted", "AbortError");
  }

  const content = full.trim();
  if (!content) throw new Error("Ollama returned an empty message.");
  return content;
}
