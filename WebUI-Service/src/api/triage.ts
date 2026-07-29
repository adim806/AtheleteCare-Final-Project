export type TriageRequest = {
  text: string;
  image_urls: string[];
  agent_name?: string;
};

export type TriageMeta = {
  route?: string;
  severity?: string;
  imagingScore?: string;
  emails?: Record<string, string>;
};

export type TriageResult = {
  ok: boolean;
  status: number;
  raw: unknown;
  displayText: string;
  meta: TriageMeta;
};

const TRIAGE_TIMEOUT_MS = 10 * 60 * 1000;

const BRIEF_KEYS = [
  "brief",
  "safe_text",
  "report_markdown",
  "body",
  "message",
  "text",
] as const;

function asRecord(v: unknown): Record<string, unknown> | null {
  return v !== null && typeof v === "object" ? (v as Record<string, unknown>) : null;
}

function pickString(o: Record<string, unknown>, keys: readonly string[]): string | null {
  for (const key of keys) {
    const v = o[key];
    if (typeof v === "string" && v.trim()) return v;
  }
  return null;
}

/** Prefer clinical brief fields; never dump raw JSON as the main view when a brief exists. */
export function pickDisplayText(payload: unknown): string {
  if (payload == null) return "(empty response)";
  if (typeof payload === "string") return payload;

  const o = asRecord(payload);
  if (!o) return String(payload);

  const direct = pickString(o, BRIEF_KEYS);
  if (direct) return direct;

  const nested = asRecord(o.output);
  if (nested) {
    const fromOut = pickString(nested, BRIEF_KEYS);
    if (fromOut) return fromOut;
  }

  return JSON.stringify(payload, null, 2);
}

export function extractMeta(payload: unknown): TriageMeta {
  const o = asRecord(payload);
  if (!o) return {};

  const emailsRaw = asRecord(o.emails);
  const emails: Record<string, string> | undefined = emailsRaw
    ? Object.fromEntries(
        Object.entries(emailsRaw).filter(
          (e): e is [string, string] => typeof e[1] === "string",
        ),
      )
    : undefined;

  return {
    route: typeof o.route === "string" ? o.route : undefined,
    severity:
      o.severity_score != null
        ? String(o.severity_score)
        : o.severity != null
          ? String(o.severity)
          : undefined,
    imagingScore:
      o.imaging_condition_score != null
        ? String(o.imaging_condition_score)
        : undefined,
    emails: emails && Object.keys(emails).length ? emails : undefined,
  };
}

export async function submitTriage(req: TriageRequest): Promise<TriageResult> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TRIAGE_TIMEOUT_MS);

  try {
    const res = await fetch("/api/triage", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
      signal: controller.signal,
    });

    const contentType = res.headers.get("content-type") || "";
    let raw: unknown;
    if (contentType.includes("application/json")) {
      raw = await res.json();
    } else {
      raw = await res.text();
    }

    return {
      ok: res.ok,
      status: res.status,
      raw,
      displayText: pickDisplayText(raw),
      meta: extractMeta(raw),
    };
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(
        "Triage timed out after 10 minutes. Check n8n execution and service tunnels.",
      );
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export function parseImageUrls(input: string): string[] {
  return input
    .split(/[\n,]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}
