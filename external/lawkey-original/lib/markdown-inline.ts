export type InlineSegment = { text: string; bold: boolean };

export function normalizeInlineMarkdownSource(text: string): string {
  return String(text || "")
    .replace(/\*\*(\s*\*\*)+/g, "**")
    .replace(/\*\*\s*\(/g, "**(")
    .replace(/\)\s*\*\*/g, ")**");
}

export function splitBoldSegments(source: string): InlineSegment[] {
  const out: InlineSegment[] = [];
  let cursor = 0;
  while (cursor < source.length) {
    const open = source.indexOf("**", cursor);
    if (open < 0) {
      out.push({ text: source.slice(cursor).replace(/\*\*/g, ""), bold: false });
      break;
    }
    const close = source.indexOf("**", open + 2);
    if (close < 0) {
      out.push({ text: source.slice(cursor).replace(/\*\*/g, ""), bold: false });
      break;
    }
    if (open > cursor) {
      out.push({ text: source.slice(cursor, open), bold: false });
    }
    const boldText = source.slice(open + 2, close);
    if (boldText) {
      out.push({ text: boldText, bold: true });
    }
    cursor = close + 2;
  }
  return out;
}
