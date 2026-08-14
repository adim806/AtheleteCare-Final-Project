import { useCallback, useEffect, useRef, useState } from "react";
import {
  addMessage,
  createConversation,
  deleteConversation,
  getConversations,
  getMessages,
  updateConversationTitle,
  type ConversationRow,
} from "../db/sqliteDb";

export type Turn = { role: "user" | "assistant"; content: string };

function titleFromMessage(text: string): string {
  const trimmed = text.trim().replace(/\s+/g, " ");
  if (trimmed.length <= 48) return trimmed || "New conversation";
  return `${trimmed.slice(0, 48)}…`;
}

export function useConversations() {
  const [ready, setReady] = useState(false);
  const [conversations, setConversations] = useState<ConversationRow[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [activeTurns, setActiveTurns] = useState<Turn[]>([]);

  // Ref mirrors activeId synchronously — avoids stale closures in appendTurn.
  const activeIdRef = useRef<string | null>(null);
  const homeEpochRef = useRef(0);

  const refreshConversations = useCallback(async () => {
    const rows = await getConversations();
    setConversations(rows);
    return rows;
  }, []);

  const loadMessages = useCallback(async (id: string) => {
    const rows = await getMessages(id);
    setActiveTurns(
      rows.map((m) => ({
        role: m.role,
        content: m.content,
      })),
    );
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      await refreshConversations();
      if (cancelled) return;
      setReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshConversations]);

  const goHome = useCallback(() => {
    homeEpochRef.current += 1;
    activeIdRef.current = null;
    setActiveId(null);
    setActiveTurns([]);
  }, []);

  const newConversation = goHome;

  const selectConversation = useCallback(
    async (id: string) => {
      activeIdRef.current = id;
      setActiveId(id);
      await loadMessages(id);
    },
    [loadMessages],
  );

  const appendTurn = useCallback(
    async (turn: Turn) => {
      const epoch = homeEpochRef.current;

      // Read from ref — always reflects the latest value, never stale.
      let convId = activeIdRef.current;

      if (!convId) {
        convId = await createConversation(
          turn.role === "user" ? titleFromMessage(turn.content) : "New conversation",
        );
        // Update ref synchronously so the next appendTurn call sees the new id.
        activeIdRef.current = convId;
        setActiveId(convId);
      }

      await addMessage(convId, turn.role, turn.content);

      if (turn.role === "user") {
        const messages = await getMessages(convId);
        if (messages.filter((m) => m.role === "user").length === 1) {
          await updateConversationTitle(convId, titleFromMessage(turn.content));
        }
      }

      if (epoch !== homeEpochRef.current) {
        // User navigated home mid-flight — save to DB but don't update UI.
        await refreshConversations();
        return convId;
      }

      setActiveTurns((prev) => [...prev, turn]);
      await refreshConversations();
      return convId;
    },
    [refreshConversations],
  );

  const removeConversation = useCallback(
    async (id: string) => {
      await deleteConversation(id);
      await refreshConversations();
      if (activeIdRef.current === id) {
        activeIdRef.current = null;
        setActiveId(null);
        setActiveTurns([]);
      }
    },
    [refreshConversations],
  );

  const renameConversation = useCallback(
    async (id: string, newTitle: string) => {
      const trimmed = newTitle.trim();
      if (!trimmed) return;
      await updateConversationTitle(id, trimmed);
      await refreshConversations();
    },
    [refreshConversations],
  );

  return {
    ready,
    conversations,
    activeId,
    activeTurns,
    goHome,
    newConversation,
    selectConversation,
    appendTurn,
    deleteConversation: removeConversation,
    renameConversation,
  };
}
