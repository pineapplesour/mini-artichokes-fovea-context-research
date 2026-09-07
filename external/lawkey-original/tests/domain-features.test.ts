import { describe, expect, it } from "vitest";

import { buildDomainControlPayload, buildDomainFeatureStates, DOMAIN_FEATURES } from "../lib/domain-features";
import type { DomainAnswer } from "../lib/domain-api";

const baseAnswer: DomainAnswer = {
  jobId: "job-domain-1700000000000-abcdef1234",
  product: "islam",
  query: "어떻게 해야 천국에 가나요",
  language: "ko",
  answerMarkdown: "## 근거 기반 답변",
  answerSections: [
    {
      kind: "direct",
      title: "### 바로 답변",
      body: "믿고 의로운 일을 하는 이들에게 낙원이 약속됩니다. [S1]",
      citations: ["S1"],
    },
  ],
  citationMap: {},
  passages: [
    {
      label: "S1",
      sourceId: "doc-quran-2-25",
      citation: "Quran 2:25",
      title: "Qur'an Arabic Uthmani Hafs",
      authorityBody: "Qur'an",
      topic: "Paradise for belief and righteous deeds",
      type: "scripture_window",
      dataset: "islam/all/scripture",
      score: 822,
      verdict: "accepted",
      excerpt: "[PRIMARY TEXT — ar] Give glad tidings to those who believe and do righteous deeds that they will have gardens beneath which rivers flow.",
    },
    {
      label: "S2",
      sourceId: "doc-tafsir",
      citation: "Quran 98:7",
      title: "Tafsir passage",
      authorityBody: "tafsir",
      topic: "Righteous deeds",
      type: "commentary_window",
      dataset: "islam/all/tafsir",
      score: 312,
      verdict: "accepted",
      excerpt: "Faith, repentance, mercy, and righteous deeds are discussed together.",
    },
  ],
  sources: [
    {
      id: "doc-quran-2-25",
      label: "S1",
      title: "Qur'an Arabic Uthmani Hafs",
      citation: "Quran 2:25",
      authorityBody: "Qur'an",
      date: "",
      topic: "Paradise for belief and righteous deeds",
      type: "scripture_window",
      dataset: "islam/all/scripture",
      path: "quran/2/25",
      url: "",
      score: 822,
      verdict: "accepted",
      excerpt: "[PRIMARY TEXT — ar] Give glad tidings to those who believe and do righteous deeds.",
    },
    {
      id: "doc-tafsir",
      label: "S2",
      title: "Tafsir passage",
      citation: "Quran 98:7",
      authorityBody: "tafsir",
      date: "",
      topic: "Righteous deeds",
      type: "commentary_window",
      dataset: "islam/all/tafsir",
      path: "tafsir/98/7",
      url: "",
      score: 312,
      verdict: "accepted",
      excerpt: "Faith, repentance, mercy, and righteous deeds are discussed together.",
    },
  ],
  selectedEvidence: [],
  safetyNotice: "근거 기반 종교 학습 보조일 뿐입니다.",
  delivery: {
    mode: "server-side-sqlite-fts",
    corpusShippedToClient: false,
    sourcePagination: { offset: 0, limit: 8, returned: 2 },
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
    facets: ["천국에", "paradise", "jannah", "believe", "righteous", "mercy", "repentance"],
    queryStructuring: {
      language: "ko",
      surfaceFacets: ["어떻게", "해야", "천국에", "가나요"],
      expandedFacets: ["paradise", "jannah", "believe", "righteous", "mercy", "repentance"],
      familyCount: 6,
    },
    queryFamilies: [{ label: "cross_lingual_success", strategy: "ko_salvation_to_en_success_hereafter_terms" }],
    candidateFrontier: { selectedCount: 2, candidateCount: 160 },
    verifier: { acceptedCount: 2, rejectedCount: 50 },
    rejectedLedger: [{ reason: "low_overlap" }],
    selectedCount: 2,
    chunkCount: 1,
    selectedEvidenceHandoff: "answerSections+citationMap+passages",
  },
};

describe("domain specialized feature states", () => {
  it("declares non-generic reference feature sets per product", () => {
    expect(DOMAIN_FEATURES.islam.map((feature) => feature.id)).toEqual([
      "source-lineage",
      "original-language",
      "translation-style",
      "scholarly-boundary",
    ]);
    expect(DOMAIN_FEATURES.tcm.map((feature) => feature.id)).toEqual([
      "pattern-map",
      "formula-herb",
      "acupuncture-channel",
      "contraindication-safety",
    ]);
    expect(DOMAIN_FEATURES.psychology.map((feature) => feature.id)).toEqual([
      "mood-checkin",
      "grounding-plan",
      "crisis-boundary",
      "session-notes",
    ]);
  });

  it("derives Islam source and translation controls from selected evidence", () => {
    const states = buildDomainFeatureStates("islam", baseAnswer, baseAnswer.query);

    expect(states.find((item) => item.id === "source-lineage")).toMatchObject({
      status: "active",
      evidenceCount: 2,
      evidenceLabels: ["S1", "S2"],
    });
    expect(states.find((item) => item.id === "original-language")?.detail).toContain("ko");
    expect(states.find((item) => item.id === "translation-style")?.detail).toContain("Quran 2:25");
    expect(states.find((item) => item.id === "scholarly-boundary")?.detail).toContain("근거 기반");
  });

  it("derives TCM panels from facets, query, and source excerpts", () => {
    const tcmAnswer = {
      ...baseAnswer,
      product: "tcm",
      language: "ko",
      query: "불면 침 치료와 감초 처방 금기",
      safetyNotice: "진단이나 처방이 아닙니다.",
      beta6: {
        ...baseAnswer.beta6,
        facets: ["불면", "insomnia", "acupuncture", "herb", "formula", "contraindication", "safety"],
      },
      sources: [
        {
          ...baseAnswer.sources[0],
          label: "S1",
          citation: "동의보감",
          authorityBody: "classic",
          type: "classic_formula",
          excerpt: "insomnia acupuncture formula herb contraindication safety pattern spleen stomach",
        },
      ],
      passages: [],
    } satisfies DomainAnswer;

    const states = buildDomainFeatureStates("tcm", tcmAnswer, tcmAnswer.query);

    expect(states.find((item) => item.id === "pattern-map")?.status).toBe("active");
    expect(states.find((item) => item.id === "formula-herb")).toMatchObject({
      status: "active",
      evidenceCount: 1,
    });
    expect(states.find((item) => item.id === "contraindication-safety")?.detail).toContain("진단이나 처방");
  });

  it("builds typed domain-control payloads for the shared engine", () => {
    const tcmAnswer = {
      ...baseAnswer,
      product: "tcm",
      language: "ko",
      query: "불면 침 치료 근거",
      beta6: {
        ...baseAnswer.beta6,
        facets: ["불면", "insomnia", "acupuncture"],
      },
      sources: [
        {
          ...baseAnswer.sources[0],
          label: "S1",
          citation: "침구 임상",
          excerpt: "insomnia acupuncture acupoint",
        },
      ],
      passages: [],
    } satisfies DomainAnswer;
    const states = buildDomainFeatureStates("tcm", tcmAnswer, tcmAnswer.query);

    const controls = buildDomainControlPayload("tcm", states, "acupuncture-channel");

    expect(controls).toEqual([
      {
        id: "acupuncture-channel",
        scope: "tcm.acupuncture-channel",
        facets: ["acupuncture", "acupoint", "channel", "针灸", "針灸", "침구", "경혈"],
        safetyBoundary: undefined,
      },
    ]);
  });

  it("derives psychology safety and grounding panels from facets and passages", () => {
    const psychologyAnswer = {
      ...baseAnswer,
      product: "psychology",
      language: "en",
      query: "panic grounding and self harm safety plan",
      safetyNotice: "If there is self-harm risk, contact emergency support now.",
      beta6: {
        ...baseAnswer.beta6,
        facets: ["panic", "grounding", "self", "harm", "safety", "mood"],
      },
      sources: [
        {
          ...baseAnswer.sources[0],
          label: "S1",
          citation: "WHO safety planning",
          authorityBody: "WHO",
          type: "guideline",
          excerpt: "grounding skills, crisis safety planning, mood monitoring, self harm warning signs",
        },
      ],
      passages: [],
    } satisfies DomainAnswer;

    const states = buildDomainFeatureStates("psychology", psychologyAnswer, psychologyAnswer.query);

    expect(states.find((item) => item.id === "grounding-plan")).toMatchObject({
      status: "active",
      evidenceLabels: ["S1"],
    });
    expect(states.find((item) => item.id === "crisis-boundary")).toMatchObject({
      status: "watch",
      evidenceCount: 1,
    });
    expect(states.find((item) => item.id === "session-notes")?.detail).toContain("1 source");
  });
});
