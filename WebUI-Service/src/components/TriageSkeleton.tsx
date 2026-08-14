import { useEffect, useState } from "react";

const TRIAGE_STEPS = [
  "Validating input (Guardrails)…",
  "Extracting clinical fields…",
  "Running AI agent (LangGraph)…",
  "Analysing imaging (if X-ray URLs provided)…",
  "Retrieving protocols and cases (RAG)…",
  "Writing clinical brief…",
  "Validating output and routing…",
];

type TriageSkeletonProps = {
  active: boolean;
};

export function TriageSkeleton({ active }: TriageSkeletonProps) {
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    if (!active) {
      setStepIndex(0);
      return;
    }

    const timer = window.setInterval(() => {
      setStepIndex((i) => (i + 1) % TRIAGE_STEPS.length);
    }, 4500);

    return () => window.clearInterval(timer);
  }, [active]);

  if (!active) return null;

  return (
    <div className="triage-skeleton" aria-live="polite" aria-busy="true">
      <p className="triage-skeleton-title">Running AthleteCare triage</p>
      <p className="triage-skeleton-step">{TRIAGE_STEPS[stepIndex]}</p>
      <p className="triage-skeleton-note">
        This can take several minutes while n8n orchestrates backend services.
      </p>
      <div className="skeleton-lines" aria-hidden="true">
        <div className="skeleton-line skeleton-line-wide" />
        <div className="skeleton-line skeleton-line-medium" />
        <div className="skeleton-line skeleton-line-short" />
        <div className="skeleton-line skeleton-line-medium" />
      </div>
    </div>
  );
}
