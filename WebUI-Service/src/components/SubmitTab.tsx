import { useState, type FormEvent } from "react";
import {
  parseImageUrls,
  submitTriage,
  type TriageResult,
} from "../api/triage";
import { renderBriefMarkdown } from "../lib/renderBrief";

export function SubmitTab() {
  const [agentName, setAgentName] = useState("");
  const [text, setText] = useState("");
  const [imageUrls, setImageUrls] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [result, setResult] = useState<TriageResult | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const report = text.trim();
    if (!report) {
      setError("Clinical report text is required.");
      return;
    }

    setError(null);
    setInfo("Triage running — this can take several minutes…");
    setBusy(true);
    setResult(null);

    try {
      const payload = {
        text: report,
        image_urls: parseImageUrls(imageUrls),
        ...(agentName.trim() ? { agent_name: agentName.trim() } : {}),
      };
      const res = await submitTriage(payload);
      setResult(res);
      setInfo(
        res.ok
          ? `Completed (HTTP ${res.status}).`
          : `Pipeline returned HTTP ${res.status} (often a guardrail reject).`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setInfo(null);
    } finally {
      setBusy(false);
    }
  }

  const meta = result?.meta ?? {};
  const looksLikeJsonDump =
    !!result && result.displayText.trimStart().startsWith("{");

  return (
    <section className="panel" aria-label="Injury submission">
      <h2>Submit injury report</h2>
      <p className="lede">
        Posts to the n8n webhook (proxied). Requires n8n active and backend
        services reachable from n8n.
      </p>

      <form onSubmit={onSubmit}>
        <div className="field">
          <label htmlFor="agent">Physio / agent name</label>
          <input
            id="agent"
            value={agentName}
            onChange={(e) => setAgentName(e.target.value)}
            placeholder="Optional"
            disabled={busy}
          />
        </div>

        <div className="field">
          <label htmlFor="report">Clinical report</label>
          <textarea
            id="report"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Player, mechanism, pain, imaging, clinical request…"
            required
            disabled={busy}
          />
        </div>

        <div className="field">
          <label htmlFor="images">Image URLs</label>
          <textarea
            id="images"
            value={imageUrls}
            onChange={(e) => setImageUrls(e.target.value)}
            placeholder="One URL per line or comma-separated"
            rows={3}
            disabled={busy}
          />
        </div>

        <div className="actions">
          <button className="btn" type="submit" disabled={busy || !text.trim()}>
            {busy ? "Running triage…" : "Submit to AthleteCare"}
          </button>
        </div>
      </form>

      {info && (
        <p className={`status ${result && !result.ok ? "info" : "ok"}`}>{info}</p>
      )}
      {error && <p className="status error">{error}</p>}

      {result && (
        <div className="report">
          <div className="report-meta">
            <span>HTTP {result.status}</span>
            {meta.route && (
              <span className={`badge route-${meta.route}`}>
                Route: {meta.route}
              </span>
            )}
            {meta.severity && <span>Severity: {meta.severity}/5</span>}
            {meta.imagingScore && (
              <span>Imaging score: {meta.imagingScore}/5</span>
            )}
          </div>

          {meta.emails && (
            <div className="report-emails">
              <span className="emails-label">Notified</span>
              <ul>
                {Object.entries(meta.emails).map(([role, addr]) => (
                  <li key={role}>
                    <strong>{role.replace(/_/g, " ")}</strong>: {addr}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {looksLikeJsonDump ? (
            <pre className="report-body">{result.displayText}</pre>
          ) : (
            <div
              className="report-brief"
              dangerouslySetInnerHTML={{
                __html: renderBriefMarkdown(result.displayText),
              }}
            />
          )}
        </div>
      )}
    </section>
  );
}
