const URGENT_PATTERN =
  /\b(urgent|emergency|fracture|rupture|ACL|concussion|severe|critical)\b/gi;
const ROUTINE_PATTERN =
  /\b(routine|stable|cleared|mobilisation|mobilization|normal proxy)\b/gi;

function wrapMatches(html: string, pattern: RegExp, className: string): string {
  return html.replace(pattern, (match) => {
    return `<span class="${className}">${match}</span>`;
  });
}

/** Post-process rendered HTML to highlight clinical urgency terms. */
export function applyMedicalHighlights(html: string): string {
  let out = wrapMatches(html, URGENT_PATTERN, "med-term-urgent");
  out = wrapMatches(out, ROUTINE_PATTERN, "med-term-routine");
  return out;
}
