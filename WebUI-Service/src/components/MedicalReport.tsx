import { toast } from "sonner";
import type { TriageMeta, TriageResult } from "@/api/triage";
import {
  httpStatusBadgeClass,
  imagingBadgeClass,
  imagingLabel,
  severityBadgeClass,
  severityLabel,
} from "@/lib/triageBadges";
import { renderBriefMarkdown } from "@/lib/renderBrief";
import { applyMedicalHighlights } from "@/lib/medicalHighlight";

type MedicalReportProps = {
  result: TriageResult;
  meta: TriageMeta;
};

export function MedicalReport({ result, meta }: MedicalReportProps) {
  const looksLikeJsonDump = result.displayText.trimStart().startsWith("{");
  const timestamp = new Date().toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });

  async function copyReport() {
    try {
      await navigator.clipboard.writeText(result.displayText);
      toast.success("Report copied to clipboard");
    } catch {
      toast.error("Could not copy report");
    }
  }

  function downloadPdf() {
    window.print();
  }

  return (
    <article className="medical-report" aria-label="AthleteCare triage report">
      <header className="medical-report-header">
        <div>
          <h3 className="medical-report-title">AthleteCare Triage Report</h3>
          <p className="medical-report-subtitle">Clinical decision-support summary · {timestamp}</p>
        </div>
        <div className="report-meta-badges">
          <span className={`badge ${httpStatusBadgeClass(result.ok, result.status)}`}>
            HTTP {result.status}
          </span>
          {meta.route && (
            <span className={`badge route-${meta.route}`}>Route: {meta.route}</span>
          )}
          {meta.severity && (
            <span className={`badge ${severityBadgeClass(meta.severity)}`}>
              {severityLabel(meta.severity)}
            </span>
          )}
          {meta.imagingScore && (
            <span className={`badge ${imagingBadgeClass(meta.imagingScore)}`}>
              {imagingLabel(meta.imagingScore)}
            </span>
          )}
        </div>
      </header>

      <div className="medical-report-body">
        <h4 className="medical-report-section-title">Key findings</h4>
        {looksLikeJsonDump ? (
          <pre className="report-body">{result.displayText}</pre>
        ) : (
          <div
            className="report-brief"
            dangerouslySetInnerHTML={{
              __html: applyMedicalHighlights(renderBriefMarkdown(result.displayText)),
            }}
          />
        )}

        {meta.emails && (
          <>
            <h4 className="medical-report-section-title mt-4">Notifications</h4>
            <div className="report-emails">
              <ul>
                {Object.entries(meta.emails).map(([role, addr]) => (
                  <li key={role}>
                    <strong>{role.replace(/_/g, " ")}</strong>: {addr}
                  </li>
                ))}
              </ul>
            </div>
          </>
        )}
      </div>

      <footer className="medical-report-actions">
        <button type="button" className="btn-secondary" onClick={downloadPdf}>
          Download PDF
        </button>
        <button type="button" className="btn-secondary" onClick={() => void copyReport()}>
          Copy report
        </button>
      </footer>
    </article>
  );
}
