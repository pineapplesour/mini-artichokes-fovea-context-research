export type QuoteCitationMatch = {
  label: string;
  leadingText: string;
};

const PRD_TOKEN_SOURCE = String.raw`\[prd:[A-Za-z0-9-]+\]`;
const CASE_NUMBER_SOURCE = String.raw`\d{2,4}\s*[가-힣]{1,4}\s*\d{1,6}(?:\s*,\s*\d{1,6})*`;
const COURT_DATE_PREFIX_SOURCE = String.raw`(?:[가-힣A-Za-z]{1,30}(?:법원|법|지법|지원|재판소)?\s+)?(?:\d{4}\.?\s*\d{1,2}\.?\s*\d{1,2}\.?\s*)?(?:선고\s*)?`;
const CASE_CITATION_SOURCE = String.raw`${COURT_DATE_PREFIX_SOURCE}\[?(${CASE_NUMBER_SOURCE})\]?\s*판결(?:\s*\([^)]{0,160}\))?`;

function stripDisplayMarkdown(text: string): string {
  return String(text || "")
    .replace(/^\s{0,3}#{1,6}\s+/, "")
    .replace(/\*\*/g, "")
    .replace(/`/g, "")
    .trim();
}

function trimCitationPunctuation(text: string): string {
  return String(text || "")
    .trim()
    .replace(/[.。．,，;；:：]+$/g, "")
    .trim();
}

function stripOuterCitationParens(text: string): string {
  let current = trimCitationPunctuation(stripDisplayMarkdown(text));
  let changed = true;
  while (changed) {
    changed = false;
    const parenMatch = current.match(/^\(([\s\S]*)\)$/);
    if (parenMatch) {
      current = trimCitationPunctuation(parenMatch[1]);
      changed = true;
      continue;
    }
    const bracketMatch = current.match(/^\[([\s\S]*)\]$/);
    if (bracketMatch) {
      current = trimCitationPunctuation(bracketMatch[1]);
      changed = true;
    }
  }
  return current;
}

export function extractStandaloneCitationLabel(text: string): string | null {
  const cleaned = stripOuterCitationParens(text);
  if (!cleaned) return null;
  const prdToken = String.raw`\s*(?:${PRD_TOKEN_SOURCE})?`;
  const casePattern = new RegExp(String.raw`^${CASE_CITATION_SOURCE}${prdToken}$`);
  const referencePattern = new RegExp(String.raw`^(?:참조\s*판례|LBOX\s*익명화)${prdToken}$`);
  const caseMatch = cleaned.match(casePattern);
  if (caseMatch) {
    const token = cleaned.match(new RegExp(`${PRD_TOKEN_SOURCE}\\s*$`))?.[0] || "";
    const caseNumber = caseMatch[1].replace(/\s+/g, "");
    return `${caseNumber} 판결${token ? ` ${token}` : ""}`.trim();
  }
  if (referencePattern.test(cleaned)) {
    return cleaned.replace(/\s+/g, " ").trim();
  }
  return null;
}

export function extractQuoteCitationMatch(text: string): QuoteCitationMatch | null {
  const cleaned = stripDisplayMarkdown(text);
  const standalone = extractStandaloneCitationLabel(cleaned);
  if (standalone) {
    return { label: standalone, leadingText: "" };
  }

  const trailingCitation = new RegExp(
    String.raw`([\s\S]*?)((?:\(\s*)?(?:${CASE_CITATION_SOURCE}|(?:참조\s*판례|LBOX\s*익명화)(?:\s*${PRD_TOKEN_SOURCE})?)(?:\s*\))?)\s*[.。．,，;；:：]*$`,
  );
  const match = cleaned.match(trailingCitation);
  if (!match) return null;

  const label = extractStandaloneCitationLabel(match[2]);
  if (!label) return null;

  return {
    label,
    leadingText: match[1].replace(/\s+$/g, "").trim(),
  };
}

export function extractLeadingQuoteCitation(text: string): { label: string; quoteText: string } | null {
  const lines = String(text || "").split(/\n/);
  const firstContentIndex = lines.findIndex((line) => line.trim());
  if (firstContentIndex < 0) return null;
  const label = extractStandaloneCitationLabel(lines[firstContentIndex]);
  if (!label) return null;
  const nextLines = [...lines.slice(0, firstContentIndex), ...lines.slice(firstContentIndex + 1)];
  const quoteText = nextLines.join("\n").trim();
  if (!quoteText) return null;
  return { label, quoteText };
}

export function extractQuoteBlockCitationLabel(text: string): string | null {
  const lines = String(text || "").split(/\n/).map((line) => line.trim()).filter(Boolean);
  if (lines.length !== 1) return null;
  return extractStandaloneCitationLabel(lines[0]);
}
