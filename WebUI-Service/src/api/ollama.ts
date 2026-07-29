import { OLLAMA_SYSTEM_PROMPT } from "../prompts/ollamaSystem";

export type ChatMessage = {
  role: "system" | "user" | "assistant";
  content: string;
};

export async function chatWithOllama(
  history: { role: "user" | "assistant"; content: string }[],
  userMessage: string,
): Promise<string> {
  const model = import.meta.env.VITE_OLLAMA_MODEL || "llama3";
  const messages: ChatMessage[] = [
    { role: "system", content: OLLAMA_SYSTEM_PROMPT },
    ...history,
    { role: "user", content: userMessage },
  ];

  const res = await fetch("/api/ollama/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model,
      messages,
      stream: false,
    }),
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(
      `Ollama error ${res.status}: ${body || res.statusText}. Is Ollama running (ollama serve) with model "${model}"?`,
    );
  }

  const data = (await res.json()) as {
    message?: { content?: string };
  };
  const content = data.message?.content?.trim();
  if (!content) {
    throw new Error("Ollama returned an empty message.");
  }
  return content;
}
