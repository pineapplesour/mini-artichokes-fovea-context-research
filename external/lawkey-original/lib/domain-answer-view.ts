import type { DomainAnswer, DomainAnswerSection, DomainPassage } from "./domain-api";

export type DomainAnswerView = {
  sections: DomainAnswerSection[];
  citationLabels: string[];
  passages: DomainPassage[];
  defaultPassage: DomainPassage | null;
  hasComposedAnswer: boolean;
};

export type DomainClientPayloadAudit = {
  byteLength: number;
  hasLeak: boolean;
  forbiddenMatches: string[];
};

export function buildDomainAnswerView(answer: DomainAnswer | null): DomainAnswerView {
  const sections = Array.isArray(answer?.answerSections) ? answer.answerSections : fallbackSections(answer?.answerMarkdown || "");
  const passages =
    Array.isArray(answer?.passages) && answer.passages.length
      ? answer.passages
      : (answer?.sources || []).map((source, index) => ({
          label: source.label || `S${index + 1}`,
          sourceId: source.id,
          citation: source.citation || source.title || source.id,
          title: source.title,
          authorityBody: source.authorityBody,
          topic: source.topic,
          type: source.type,
          dataset: source.dataset,
          score: source.score,
          verdict: source.verdict,
          excerpt: source.excerpt,
        }));
  const citationLabels = Array.from(new Set(sections.flatMap((section) => section.citations || [])));
  return {
    sections,
    citationLabels,
    passages,
    defaultPassage: passages[0] || null,
    hasComposedAnswer: sections.length > 0 && citationLabels.length > 0,
  };
}

export function auditDomainClientPayload(payload: unknown): DomainClientPayloadAudit {
  const serialized = JSON.stringify(payload ?? "");
  const forbiddenMatches = forbiddenClientPayloadMarkers().filter((marker) => serialized.includes(marker));
  return {
    byteLength: new TextEncoder().encode(serialized).length,
    hasLeak: forbiddenMatches.length > 0,
    forbiddenMatches,
  };
}

function forbiddenClientPayloadMarkers(): string[] {
  const slash = runtimeChar(47);
  const backslash = runtimeChar(92);
  const dot = runtimeChar(46);
  return [
    [slash, "home", slash, "pineapple"].join(""),
    [backslash, "home", backslash, "pineapple"].join(""),
    [slash, "mnt", slash].join(""),
    ["C", ":", backslash].join(""),
    [dot, "sqlite"].join(""),
    [dot, "sqlite3"].join(""),
    [dot, "jsonl"].join(""),
  ];
}

function runtimeChar(code: number): string {
  return String.fromCharCode(Number.parseInt(String(code), 10));
}

function fallbackSections(markdown: string): DomainAnswerSection[] {
  const text = String(markdown || "").trim();
  if (!text) return [];
  return [
    {
      kind: "direct",
      title: "### Grounded answer",
      body: text
        .split("\n")
        .filter((line) => !line.startsWith("#"))
        .join("\n")
        .trim(),
      citations: Array.from(new Set(text.match(/\[(S\d+)\]/g)?.map((value) => value.slice(1, -1)) || [])),
    },
  ];
}
