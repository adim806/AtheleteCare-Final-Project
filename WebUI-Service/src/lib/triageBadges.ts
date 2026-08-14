export function parseScore(value: string | undefined): number | null {
  if (value == null || value.trim() === "") return null;
  const n = Number.parseInt(value, 10);
  return Number.isFinite(n) ? n : null;
}

export function severityBadgeClass(score: string | undefined): string {
  const n = parseScore(score);
  if (n == null) return "badge-severity-unknown";
  if (n <= 2) return "badge-severity-low";
  if (n === 3) return "badge-severity-mid";
  return "badge-severity-high";
}

export function imagingBadgeClass(score: string | undefined): string {
  const n = parseScore(score);
  if (n == null) return "badge-imaging-unknown";
  if (n === 1) return "badge-imaging-normal";
  if (n === 5) return "badge-imaging-abnormal";
  return "badge-imaging-uncertain";
}

export function httpStatusBadgeClass(ok: boolean, status: number): string {
  if (ok) return "badge-http-ok";
  if (status === 400) return "badge-guardrail";
  return "badge-http-error";
}

export function severityLabel(score: string | undefined): string {
  const n = parseScore(score);
  if (n == null) return "Severity";
  return `Severity ${n}/5`;
}

export function imagingLabel(score: string | undefined): string {
  const n = parseScore(score);
  if (n == null) return "Imaging";
  if (n === 1) return "Imaging 1/5 · normal proxy";
  if (n === 5) return "Imaging 5/5 · abnormal proxy";
  return `Imaging ${n}/5`;
}
