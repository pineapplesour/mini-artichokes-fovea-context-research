import { describe, expect, it } from "vitest";

import { validateDomainAnswerPayload } from "../lib/domain-api";

const validPayload = {
  jobId: "job-domain-1700000000000-abcdef1234",
  product: "islam",
  query: "어떻게 해야 천국에 가나요",
  language: "ko",
  answerMarkdown: "## 근거 기반 답변",
  answerSections: [{ kind: "direct", title: "### 바로 답변", body: "근거 답변 [S1]", citations: ["S1"] }],
  passages: [{ label: "S1", sourceId: "doc-quran", citation: "Quran 2:25", title: "Quran", authorityBody: "Qur'an", topic: "Paradise", type: "scripture_window", dataset: "islam/all/scripture", score: 10, verdict: "accepted", excerpt: "believe and do righteous deeds" }],
  sources: [{ id: "doc-quran", label: "S1", title: "Quran", citation: "Quran 2:25", authorityBody: "Qur'an", date: "", topic: "Paradise", type: "scripture_window", dataset: "islam/all/scripture", path: "quran/2/25", url: "", score: 10, verdict: "accepted", excerpt: "believe and do righteous deeds" }],
  selectedEvidence: [],
  safetyNotice: "근거 기반 종교 학습 보조일 뿐입니다.",
  delivery: {
    mode: "server-side-sqlite-fts",
    corpusShippedToClient: false,
    sourcePagination: { offset: 0, limit: 8, returned: 1 },
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
    facets: ["paradise", "jannah"],
    queryStructuring: {
      language: "ko",
      surfaceFacets: ["천국에"],
      expandedFacets: ["paradise", "jannah"],
      familyCount: 4,
    },
    queryFamilies: [{ label: "cross_lingual" }],
    candidateFrontier: { candidateCount: 80, selectedCount: 1 },
    verifier: { acceptedCount: 1, rejectedCount: 50 },
    rejectedLedger: [{ reason: "low_overlap" }],
    selectedCount: 1,
    chunkCount: 1,
    selectedEvidenceHandoff: "answerSections+citationMap+passages",
  },
};

describe("domain API response validation", () => {
  it("accepts the grounded domain answer contract used by the chat workspace", () => {
    const answer = validateDomainAnswerPayload(validPayload);

    expect(answer.jobId).toBe(validPayload.jobId);
    expect(answer.sources[0].citation).toBe("Quran 2:25");
    expect(answer.beta6.rejectedLedger.length).toBe(1);
    expect(answer.delivery?.corpusShippedToClient).toBe(false);
  });

  it("rejects malformed responses before they reach UI state", () => {
    expect(() => validateDomainAnswerPayload({ ...validPayload, sources: "bad" })).toThrow(/sources/);
    expect(() =>
      validateDomainAnswerPayload({
        ...validPayload,
        beta6: { ...validPayload.beta6, rejectedLedger: "bad" },
      }),
    ).toThrow(/rejectedLedger/);
    expect(() => validateDomainAnswerPayload({ ...validPayload, jobId: "" })).toThrow(/jobId/);
  });

  it("rejects responses that would indicate client-side corpus leakage", () => {
    expect(() =>
      validateDomainAnswerPayload({
        ...validPayload,
        delivery: { ...validPayload.delivery, corpusShippedToClient: true },
      }),
    ).toThrow(/corpus/);
  });

  it("rejects unsanitized corpus metadata, HTML tags, and replacement characters", () => {
    expect(() =>
      validateDomainAnswerPayload({
        ...validPayload,
        answerSections: [{ kind: "direct", title: "### 바로 답변", body: "[META] leaked", citations: [] }],
      }),
    ).toThrow(/unsafe public text/);
    expect(() =>
      validateDomainAnswerPayload({
        ...validPayload,
        sources: [
          {
            ...validPayload.sources[0],
            excerpt: '<span class="italic">literal html</span>',
          },
        ],
      }),
    ).toThrow(/unsafe public text/);
    expect(() =>
      validateDomainAnswerPayload({
        ...validPayload,
        passages: [
          {
            ...validPayload.passages[0],
            excerpt: "malformed � text",
          },
        ],
      }),
    ).toThrow(/unsafe public text/);
    expect(() =>
      validateDomainAnswerPayload({
        ...validPayload,
        sources: [
          {
            ...validPayload.sources[0],
            excerpt: "基于输入的患者医案记录，直接给出你的疾病诊断，无需给出原因。",
          },
        ],
      }),
    ).toThrow(/unsafe public text/);
  });
});
