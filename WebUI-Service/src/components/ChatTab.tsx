import { useState, type FormEvent, type KeyboardEvent } from "react";
import { chatWithOllama } from "../api/ollama";

type Turn = { role: "user" | "assistant"; content: string };

export function ChatTab() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send() {
    const text = draft.trim();
    if (!text || busy) return;

    setError(null);
    setBusy(true);
    setDraft("");
    setTurns((prev) => [...prev, { role: "user", content: text }]);

    try {
      const reply = await chatWithOllama(turns, text);
      setTurns((prev) => [...prev, { role: "assistant", content: reply }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void send();
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  }

  return (
    <section className="panel" aria-label="Conversational assistant">
      <h2>Club assistant</h2>
      <p className="lede">
        Local Ollama chat for AthleteCare orientation. Not a clinician — asks for
        escalation on red flags.
      </p>

      <div className="chat-log" role="log" aria-live="polite">
        {turns.length === 0 && (
          <div className="bubble assistant">
            Ask how triage works, what imaging_only vs multi_step means, or general
            injury education. Off-topic and definitive diagnoses are refused.
          </div>
        )}
        {turns.map((t, i) => (
          <div key={`${t.role}-${i}`} className={`bubble ${t.role}`}>
            {t.content}
          </div>
        ))}
        {busy && <div className="bubble assistant">Thinking…</div>}
      </div>

      <form className="chat-compose" onSubmit={onSubmit}>
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Message AthleteCare assistant…"
          rows={2}
          disabled={busy}
          aria-label="Chat message"
        />
        <button className="btn" type="submit" disabled={busy || !draft.trim()}>
          Send
        </button>
      </form>

      {error && <p className="status error">{error}</p>}
    </section>
  );
}
