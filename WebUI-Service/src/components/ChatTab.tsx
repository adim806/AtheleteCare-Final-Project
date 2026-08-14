import { Brain, ClipboardList, Stethoscope } from "lucide-react";
import { motion } from "framer-motion";
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import homeHero from "../assets/athletecare-home-hero.png";
import { streamChatWithOllama } from "../api/ollama";
import { renderBriefMarkdown } from "../lib/renderBrief";
import { applyMedicalHighlights } from "../lib/medicalHighlight";
import type { Turn } from "../hooks/useConversations";
import { PromptCard } from "./PromptCard";

type ChatTabProps = {
  turns: Turn[];
  onTurnAdd: (turn: Turn) => Promise<string | void>;
  homeResetToken: number;
  activeConversationId: string | null;
};

const PROMPT_CARDS = [
  {
    icon: ClipboardList,
    title: "Injury Protocol Guidance",
    question: "How does AthleteCare triage work?",
  },
  {
    icon: Brain,
    title: "Pipeline Decision Types",
    question: "What is imaging_only vs multi_step?",
  },
  {
    icon: Stethoscope,
    title: "Severity Scoring",
    question: "What does condition_score 1 or 5 mean?",
  },
] as const;

function isAbortError(e: unknown): boolean {
  return e instanceof DOMException && e.name === "AbortError";
}

function renderMarkdown(content: string): string {
  return applyMedicalHighlights(renderBriefMarkdown(content));
}

function AssistantAvatar() {
  return (
    <div className="avatar assistant-avatar" aria-hidden="true">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M22 12h-4l-3 9L9 3l-3 9H2"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}

export function ChatTab({
  turns,
  onTurnAdd,
  homeResetToken,
  activeConversationId,
}: ChatTabProps) {
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [streamingText, setStreamingText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const streamingRef = useRef<string | null>(null);
  const stoppedRef = useRef(false);
  const prevConversationIdRef = useRef<string | null>(activeConversationId);
  const model = import.meta.env.VITE_OLLAMA_MODEL || "llama3";

  useEffect(() => {
    abortRef.current?.abort();
    setDraft("");
    setBusy(false);
    setStreamingText(null);
    streamingRef.current = null;
    stoppedRef.current = false;
    setError(null);
  }, [homeResetToken]);

  useEffect(() => {
    const prevId = prevConversationIdRef.current;
    prevConversationIdRef.current = activeConversationId;
    if (prevId === activeConversationId) return;
    if (busy) return;
    setDraft("");
    setError(null);
    setStreamingText(null);
    streamingRef.current = null;
  }, [activeConversationId, busy]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, busy, streamingText]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
  }, [draft]);

  async function send(text?: string) {
    const message = (text ?? draft).trim();
    if (!message || busy) return;

    setError(null);
    setBusy(true);
    setStreamingText(null);
    streamingRef.current = null;
    stoppedRef.current = false;
    setDraft("");

    const controller = new AbortController();
    abortRef.current = controller;

    await onTurnAdd({ role: "user", content: message });

    try {
      const reply = await streamChatWithOllama(
        turns,
        message,
        (accumulated) => {
          streamingRef.current = accumulated;
          setStreamingText(accumulated);
        },
        controller.signal,
      );
      if (stoppedRef.current) return;
      setStreamingText(null);
      streamingRef.current = null;
      await onTurnAdd({ role: "assistant", content: reply });
    } catch (e) {
      if (isAbortError(e) || stoppedRef.current) return;
      setStreamingText(null);
      streamingRef.current = null;
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (!stoppedRef.current) {
        setBusy(false);
      }
      abortRef.current = null;
    }
  }

  async function stop() {
    stoppedRef.current = true;
    abortRef.current?.abort();
    const partial = streamingRef.current?.trim();
    if (partial) {
      await onTurnAdd({ role: "assistant", content: partial });
    }
    streamingRef.current = null;
    setStreamingText(null);
    setBusy(false);
    abortRef.current = null;
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (busy) {
      void stop();
      return;
    }
    void send();
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  }

  const showEmpty = turns.length === 0 && !busy && streamingText === null;
  const waitingForFirstToken = busy && streamingText === null;

  const messageMotion = {
    initial: { opacity: 0, y: 8 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.22, ease: "easeOut" as const },
  };

  return (
    <section
      className={`chat-view${showEmpty ? " chat-view-home" : ""}`}
      aria-label="Conversational assistant"
    >
      <div className="chat-view-body" ref={logRef}>
        {showEmpty ? (
          <div className="chat-empty">
            <header className="chat-empty-header">
              <h2 className="chat-empty-title">Club assistant</h2>
              <p className="chat-empty-sub">
                Ask about AthleteCare triage, injury types, or the clinical pipeline.
              </p>
            </header>

            <motion.figure
              className="chat-empty-hero"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, ease: "easeOut", delay: 0.08 }}
            >
              <div className="chat-empty-hero-frame">
                <img
                  src={homeHero}
                  alt="AI Sports Medicine System — clinical triage, injury risk, and performance analytics"
                  width={960}
                  height={540}
                  decoding="async"
                />
              </div>
              <figcaption className="chat-empty-hero-caption">
                AI Sports Medicine System · Optimize · Prevent · Perform
              </figcaption>
            </motion.figure>

            <div className="prompt-card-grid">
              {PROMPT_CARDS.map((card) => (
                <PromptCard
                  key={card.question}
                  icon={card.icon}
                  title={card.title}
                  question={card.question}
                  onClick={() => void send(card.question)}
                  disabled={busy}
                />
              ))}
            </div>
          </div>
        ) : (
          <div className="chat-messages">
            {turns.map((t, i) => (
              <motion.div
                key={`${t.role}-${i}`}
                className={`message-row ${t.role}`}
                {...messageMotion}
              >
                {t.role === "assistant" && <AssistantAvatar />}
                <div className={`message-bubble ${t.role}`}>
                  {t.role === "assistant" ? (
                    <div
                      className="bubble-markdown"
                      dangerouslySetInnerHTML={{ __html: renderMarkdown(t.content) }}
                    />
                  ) : (
                    t.content
                  )}
                </div>
                {t.role === "user" && (
                  <div className="avatar user-avatar" aria-hidden="true">
                    You
                  </div>
                )}
              </motion.div>
            ))}

            {waitingForFirstToken && (
              <motion.div className="message-row assistant" {...messageMotion}>
                <AssistantAvatar />
                <div className="message-bubble assistant thinking-bubble">
                  <span className="typing-indicator">
                    <span />
                    <span />
                    <span />
                  </span>
                </div>
              </motion.div>
            )}

            {streamingText !== null && (
              <motion.div className="message-row assistant streaming-row" {...messageMotion}>
                <AssistantAvatar />
                <div className="message-bubble assistant streaming-bubble">
                  <div
                    className="bubble-markdown streaming-text"
                    dangerouslySetInnerHTML={{
                      __html: renderMarkdown(streamingText),
                    }}
                  />
                  <span className="streaming-cursor" aria-hidden="true" />
                </div>
              </motion.div>
            )}
          </div>
        )}
      </div>

      <div className="chat-view-footer">
        <form className="chat-compose" onSubmit={onSubmit}>
          <textarea
            ref={textareaRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Message AthleteCare assistant…"
            disabled={busy}
            aria-label="Chat message"
          />
          {busy ? (
            <button
              className="btn-stop-circle"
              type="button"
              onClick={() => void stop()}
              aria-label="Stop generation"
              title="Stop generation"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <rect x="6" y="6" width="12" height="12" rx="1" />
              </svg>
            </button>
          ) : (
            <button
              className="btn-send-circle"
              type="submit"
              disabled={!draft.trim()}
              aria-label="Send message"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path
                  d="M12 19V5M5 12l7-7 7 7"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          )}
        </form>
        <p className="chat-footer-note">
          Local Ollama ({model}) · AI orientation only — not clinical advice
        </p>
        {error && <p className="status error">{error}</p>}
      </div>
    </section>
  );
}
