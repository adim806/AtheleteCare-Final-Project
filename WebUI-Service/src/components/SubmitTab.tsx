import { useState, type FormEvent } from "react";
import { Scan, TriangleAlert } from "lucide-react";
import {
  parseImageUrls,
  submitTriage,
  type TriageResult,
} from "../api/triage";
import { MedicalReport } from "./MedicalReport";
import { SubmitLoadingLabel } from "./SubmitLoadingLabel";
import { TriageSkeleton } from "./TriageSkeleton";

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

  return (
    <section className="panel submit-panel" aria-label="Injury submission">
      <h2>Submit injury report</h2>
      <p className="lede">
        Posts to the n8n webhook (proxied). Requires n8n active and backend
        services reachable from n8n.
      </p>

      <aside className="disclaimer" role="note">
        <TriangleAlert className="disclaimer-icon" size={18} aria-hidden="true" />
        <div>
          <strong>Clinical imaging notice.</strong> Image URLs should be direct links to
          clinical X-ray radiographs only. The imaging score (1 or 5) is an automated
          normal-vs-abnormal proxy — not a diagnosis, fracture confirmation, or
          return-to-play estimate. Club protocols and case history come from retrieved
          documents, not from the image model alone.
        </div>
      </aside>

      <form onSubmit={onSubmit}>
        <div className="form-section">
          <h3 className="form-section-header">Patient &amp; clinical context</h3>
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
        </div>

        <div className="form-section border-t border-slate-200 pt-4 mt-4">
          <h3 className="form-section-header">Imaging analysis</h3>
          <div className="field">
            <label htmlFor="images">Image URLs (clinical X-rays only)</label>
            <div className="imaging-dropzone">
              <div className="imaging-dropzone-label">
                <Scan size={16} aria-hidden="true" />
                Enter X-ray URL or paste links below
              </div>
              <textarea
                id="images"
                value={imageUrls}
                onChange={(e) => setImageUrls(e.target.value)}
                placeholder="One public X-ray URL per line or comma-separated"
                rows={3}
                disabled={busy}
              />
            </div>
            <p className="field-hint">
              Colour photos and non-radiograph images may be rejected by the image analyser.
            </p>
          </div>
        </div>

        <div className="actions">
          <button className="btn" type="submit" disabled={busy || !text.trim()}>
            {busy ? <SubmitLoadingLabel active={busy} /> : "Submit to AthleteCare"}
          </button>
        </div>
      </form>

      <TriageSkeleton active={busy} />

      {info && (
        <p className={`status ${result?.ok ? "ok" : "info"}`}>{info}</p>
      )}
      {error && <p className="status error">{error}</p>}

      {result && <MedicalReport result={result} meta={meta} />}
    </section>
  );
}
