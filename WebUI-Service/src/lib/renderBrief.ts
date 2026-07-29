/** Minimal Markdown → HTML for clinical briefs (headers, lists, bold, paragraphs). */
export function renderBriefMarkdown(md: string): string {
  const escaped = md
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  const lines = escaped.split(/\r?\n/);
  const out: string[] = [];
  let inList = false;

  const flushList = () => {
    if (inList) {
      out.push("</ul>");
      inList = false;
    }
  };

  const inline = (s: string) =>
    s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/\*(.+?)\*/g, "<em>$1</em>");

  for (const line of lines) {
    if (/^###\s+/.test(line)) {
      flushList();
      out.push(`<h4>${inline(line.replace(/^###\s+/, ""))}</h4>`);
      continue;
    }
    if (/^##\s+/.test(line)) {
      flushList();
      out.push(`<h3>${inline(line.replace(/^##\s+/, ""))}</h3>`);
      continue;
    }
    if (/^#\s+/.test(line)) {
      flushList();
      out.push(`<h2>${inline(line.replace(/^#\s+/, ""))}</h2>`);
      continue;
    }
    if (/^[-*]\s+/.test(line)) {
      if (!inList) {
        out.push("<ul>");
        inList = true;
      }
      out.push(`<li>${inline(line.replace(/^[-*]\s+/, ""))}</li>`);
      continue;
    }
    if (/^\d+\.\s+/.test(line)) {
      flushList();
      out.push(`<p class="numbered">${inline(line)}</p>`);
      continue;
    }
    if (!line.trim()) {
      flushList();
      continue;
    }
    flushList();
    out.push(`<p>${inline(line)}</p>`);
  }
  flushList();
  return out.join("\n");
}
