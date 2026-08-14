import initSqlJs, { type Database } from "sql.js";
import wasmUrl from "sql.js/dist/sql-wasm.wasm?url";

const STORAGE_KEY = "ac-db";

export type ConversationRow = {
  id: string;
  title: string;
  created_at: number;
};

export type MessageRow = {
  id: number;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  ts: number;
};

let dbPromise: Promise<Database> | null = null;

function persist(db: Database): void {
  const data = db.export();
  localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(data)));
}

function loadSavedDb(): Uint8Array | undefined {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return undefined;
  try {
    return new Uint8Array(JSON.parse(raw) as number[]);
  } catch {
    return undefined;
  }
}

function initSchema(db: Database): void {
  db.run(`
    CREATE TABLE IF NOT EXISTS conversations (
      id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      created_at INTEGER NOT NULL
    );
  `);
  db.run(`
    CREATE TABLE IF NOT EXISTS messages (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      conversation_id TEXT NOT NULL,
      role TEXT NOT NULL,
      content TEXT NOT NULL,
      ts INTEGER NOT NULL,
      FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
    );
  `);
}

export async function getDb(): Promise<Database> {
  if (!dbPromise) {
    dbPromise = (async () => {
      const SQL = await initSqlJs({ locateFile: () => wasmUrl });
      const saved = loadSavedDb();
      const db = saved ? new SQL.Database(saved) : new SQL.Database();
      initSchema(db);
      return db;
    })();
  }
  return dbPromise;
}

export async function createConversation(title = "New conversation"): Promise<string> {
  const db = await getDb();
  const id = crypto.randomUUID();
  const created_at = Date.now();
  db.run("INSERT INTO conversations (id, title, created_at) VALUES (?, ?, ?)", [
    id,
    title,
    created_at,
  ]);
  persist(db);
  return id;
}

export async function addMessage(
  conversationId: string,
  role: "user" | "assistant",
  content: string,
): Promise<void> {
  const db = await getDb();
  db.run(
    "INSERT INTO messages (conversation_id, role, content, ts) VALUES (?, ?, ?, ?)",
    [conversationId, role, content, Date.now()],
  );
  persist(db);
}

export async function updateConversationTitle(
  conversationId: string,
  title: string,
): Promise<void> {
  const db = await getDb();
  db.run("UPDATE conversations SET title = ? WHERE id = ?", [title, conversationId]);
  persist(db);
}

export async function getConversations(): Promise<ConversationRow[]> {
  const db = await getDb();
  const result = db.exec(
    "SELECT id, title, created_at FROM conversations ORDER BY created_at DESC",
  );
  if (!result.length) return [];
  const { columns, values } = result[0];
  return values.map((row: unknown[]) => {
    const obj: Record<string, unknown> = {};
    columns.forEach((col: string, i: number) => {
      obj[col] = row[i];
    });
    return obj as ConversationRow;
  });
}

export async function getMessages(conversationId: string): Promise<MessageRow[]> {
  const db = await getDb();
  const stmt = db.prepare(
    "SELECT id, conversation_id, role, content, ts FROM messages WHERE conversation_id = ? ORDER BY ts ASC",
  );
  stmt.bind([conversationId]);
  const rows: MessageRow[] = [];
  while (stmt.step()) {
    const row = stmt.getAsObject() as Record<string, unknown>;
    rows.push({
      id: Number(row.id),
      conversation_id: String(row.conversation_id),
      role: row.role as "user" | "assistant",
      content: String(row.content),
      ts: Number(row.ts),
    });
  }
  stmt.free();
  return rows;
}

export async function deleteConversation(conversationId: string): Promise<void> {
  const db = await getDb();
  db.run("DELETE FROM messages WHERE conversation_id = ?", [conversationId]);
  db.run("DELETE FROM conversations WHERE id = ?", [conversationId]);
  persist(db);
}
