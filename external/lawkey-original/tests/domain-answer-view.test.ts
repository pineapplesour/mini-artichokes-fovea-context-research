import { describe, expect, it } from "vitest";

import { auditDomainClientPayload, buildDomainAnswerView } from "../lib/domain-answer-view";
import type { DomainAnswer } from "../lib/domain-api";

const answer: DomainAnswer = {
  jobId: "job-domain-1700000000000-abcdef1234",
  product: "islam",
  query: "qibla prayer",
  language: "en",
  answerMarkdown: "## Grounded answer",
  answerSections: [
    {
      kind: "direct",
      title: "### Direct answer",
      body: "Use the selected evidence [S1].",
      citations: ["S1"],
    },
  ],
  citationMap: {
    S1: {
      sourceId: "doc-fiqh-1",
      citation: "Prayer",
      title: "Prayer Times",
      authorityBody: "Hanafi fiqh",
      dataset: "islam/hanafi/fiqh",
      type: "legal_issue_bundle",
      score: 42,
      excerpt: "Prayer time qibla fasting worship practice.",
    },
  },
  passages: [
    {
      label: "S1",
      sourceId: "doc-fiqh-1",
      citation: "Prayer",
      title: "Prayer Times",
      authorityBody: "Hanafi fiqh",
      topic: "Prayer time ruling",
      type: "legal_issue_bundle",
      dataset: "islam/hanafi/fiqh",
      score: 42,
      verdict: "accepted",
      excerpt: "Prayer time qibla fasting worship practice.",
    },
  ],
  sources: [
    {
      id: "doc-fiqh-1",
      label: "S1",
      title: "Prayer Times",
      citation: "Prayer",
      authorityBody: "Hanafi fiqh",
      date: "",
      topic: "Prayer time ruling",
      type: "legal_issue_bundle",
      dataset: "islam/hanafi/fiqh",
      path: "fiqh/prayer",
      url: "",
      score: 42,
      verdict: "accepted",
      excerpt: "Prayer time qibla fasting worship practice.",
    },
  ],
  selectedEvidence: [],
  safetyNotice: "religious safety",
  delivery: {
    mode: "server-side-sqlite-fts",
    corpusShippedToClient: false,
    sourcePagination: { offset: 0, limit: 3, returned: 1 },
  },
  securityControls: {
    sqliteMode: "read-only-query-only",
    sqlParameters: "parameterized",
    pathPolicy: "profile-db-allowlist",
    queryBounds: { maxChars: 5000, maxLimit: 30 },
    timeoutCancel: "sqlite-progress-handler-and-job-cancel-event",
    retrievedTextPolicy: "evidence-not-instruction",
  },
  beta6: {
    analysisMode: "beta6-domain",
    facets: ["qibla", "prayer"],
    rejectedLedger: [],
    selectedCount: 1,
    chunkCount: 1,
    selectedEvidenceHandoff: "answerSections+citationMap+passages",
  },
};

describe("domain answer view helpers", () => {
  it("builds a composed answer view with citation labels and a default passage", () => {
    const view = buildDomainAnswerView(answer);

    expect(view.sections).toEqual(answer.answerSections);
    expect(view.citationLabels).toEqual(["S1"]);
    expect(view.passages[0].label).toBe("S1");
    expect(view.defaultPassage?.sourceId).toBe("doc-fiqh-1");
    expect(view.hasComposedAnswer).toBe(true);
  });

  it("audits client payloads for forbidden local corpus paths", () => {
    expect(auditDomainClientPayload(answer)).toMatchObject({
      hasLeak: false,
      forbiddenMatches: [],
    });

    const unsafe = { ...answer, sources: [{ ...answer.sources[0], path: "/workspace/private/islam.sqlite3" }] };
    const audit = auditDomainClientPayload(unsafe);
    expect(audit.hasLeak).toBe(true);
    expect(audit.forbiddenMatches).toContain("/workspace");
    expect(audit.forbiddenMatches).toContain(".sqlite");
  });
});
