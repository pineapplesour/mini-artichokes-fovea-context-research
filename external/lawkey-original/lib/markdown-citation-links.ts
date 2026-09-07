export type CitationLinkRange = { start: number; end: number; precedentId: string | undefined };

export type PrecedentLookupRef = {
  precedentId: string;
  caseNumber?: string;
  alternatePrecedentIds?: string[];
};

// Matches Korean case numbers like `2023노2405`, `2023 노 2405`,
// `2023고합121`, `2022도15868`, `2025헌마1781`, `84도2527`.
const CASE_NUMBER_REGEX = /\b(\d{2,4})\s*([가-힣]{1,4})\s*(\d{1,6}(?:\s*,\s*\d{1,6})*)\b/g;
export const PRD_TOKEN_REGEX = /\[prd:([A-Za-z0-9-]+)\]/g;

// Backend injects invisible precedent-id tokens for anonymous/LBOX rows.
// Accept both legacy `[prd:abc123]` and actual DB ids like
// `[prd:prd-1ff6fe8d3d3020c3]`.
const LBOX_CITATION_WITH_TOKEN =
  /(?:\(\s*)?(?:참조\s*판례\s*\(\s*)?LBOX\s*익명화\s*(?:\)?\s*)?\[prd:([A-Za-z0-9-]+)\]\s*\)?/g;
const LBOX_CITATION_WITH_TRAILING_TOKEN =
  /(?:\(\s*)?참조\s*판례\s*\(\s*LBOX\s*익명화\s*\)\s*\[prd:([A-Za-z0-9-]+)\]\s*\)?/g;
const REFERENCE_CITATION_WITH_TOKEN = /(?:\(\s*)?참조\s*판례\s*\[prd:([A-Za-z0-9-]+)\]\s*\)?/g;

// Match the entire `(법원 [선고일] [선고] 사건번호 판결)` envelope (including
// its surrounding parens). The user expects clicking anywhere on the
// citation, not just the bare case number, to open the precedent.
const FULL_CITATION_REGEX =
  /\(\s*[가-힣A-Za-z]{1,30}(?:법원|법|지법|지원|재판소)\s*(?:\d{4}\.?\s*\d{1,2}\.?\s*\d{1,2}\.?)?\s*(?:선고\s*)?(\d{2,4}\s*[가-힣]{1,4}\s*\d{1,6}(?:\s*,\s*\d{1,6})*)\s*판결[^()]*\)/g;

function normalizeCaseNumber(raw: string): string {
  return String(raw || "").replace(/\s+/g, "").trim();
}

// Expand a compound case number like `2016고합538,558` into its constituent
// full case numbers (`2016고합538`, `2016고합558`).
export function expandCompoundCaseNumber(caseNumber: string): string[] {
  const norm = normalizeCaseNumber(caseNumber);
  if (!norm) return [];
  const match = norm.match(/^(\d{2,4}[가-힣]{1,4})(\d{1,6}(?:,\d{1,6})*)$/);
  if (!match) return [norm];
  const [, prefix, numsStr] = match;
  const nums = numsStr.split(",").filter(Boolean);
  const out = new Set<string>([norm]);
  for (const n of nums) {
    out.add(prefix + n);
  }
  return Array.from(out);
}

export function buildPrecedentLookup(precedents: PrecedentLookupRef[] | undefined): Map<string, string> {
  const map = new Map<string, string>();
  if (!precedents) return map;
  for (const item of precedents) {
    const id = (item.precedentId || "").trim();
    if (!id) continue;
    for (const key of expandCompoundCaseNumber(item.caseNumber || "")) {
      if (!map.has(key)) map.set(key, id);
    }
    for (const alt of item.alternatePrecedentIds || []) {
      const altId = (alt || "").trim();
      if (altId) map.set(altId, id);
    }
  }
  return map;
}

export function stripPrecedentIdTokensForDisplay(text: string): string {
  return String(text || "")
    .replace(PRD_TOKEN_REGEX, "")
    .replace(/\s+\)/g, ")")
    .replace(/\(\s+/g, "(")
    .replace(/\s{2,}/g, " ")
    .trim();
}

function pushTokenRanges(
  text: string,
  regex: RegExp,
  ranges: CitationLinkRange[],
): void {
  regex.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(text)) !== null) {
    ranges.push({ start: match.index, end: match.index + match[0].length, precedentId: match[1] });
  }
}

export function collectCitationLinkRanges(
  text: string,
  precedentLookup: Map<string, string>,
): CitationLinkRange[] {
  const ranges: CitationLinkRange[] = [];
  if (!text) return ranges;

  pushTokenRanges(text, LBOX_CITATION_WITH_TRAILING_TOKEN, ranges);
  pushTokenRanges(text, LBOX_CITATION_WITH_TOKEN, ranges);
  pushTokenRanges(text, REFERENCE_CITATION_WITH_TOKEN, ranges);

  FULL_CITATION_REGEX.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = FULL_CITATION_REGEX.exec(text)) !== null) {
    const caseNumberInside = m[1];
    const norm = normalizeCaseNumber(caseNumberInside);
    let precedentId = precedentLookup.get(norm);
    if (!precedentId) {
      for (const alt of expandCompoundCaseNumber(caseNumberInside)) {
        const candidate = precedentLookup.get(alt);
        if (candidate) {
          precedentId = candidate;
          break;
        }
      }
    }
    if (precedentId) {
      ranges.push({ start: m.index, end: m.index + m[0].length, precedentId });
    }
  }

  CASE_NUMBER_REGEX.lastIndex = 0;
  while ((m = CASE_NUMBER_REGEX.exec(text)) !== null) {
    const start = m.index;
    const end = m.index + m[0].length;
    if (ranges.some((r) => start >= r.start && end <= r.end)) continue;
    const norm = normalizeCaseNumber(m[0]);
    let precedentId = precedentLookup.get(norm);
    if (!precedentId) {
      for (const alt of expandCompoundCaseNumber(m[0])) {
        const candidate = precedentLookup.get(alt);
        if (candidate) {
          precedentId = candidate;
          break;
        }
      }
    }
    ranges.push({ start, end, precedentId });
  }

  ranges.sort((a, b) => a.start - b.start || b.end - a.end);
  return ranges.filter((range, index) => {
    return !ranges.some((other, otherIndex) => otherIndex !== index && range.start >= other.start && range.end <= other.end && other.end - other.start > range.end - range.start);
  });
}
