import type { DomainAnswer, DomainPassage, DomainSource } from "./domain-api";
import { getDomainProduct, type DomainKey } from "./domain-factory";

export type DomainFeatureStatus = "idle" | "active" | "watch";

export type DomainFeatureConfig = {
  id: string;
  title: string;
  kicker: string;
  referenceMotif: string;
  keywords: string[];
  engineFacets: string[];
  engineScope: string;
  safetyBoundary?: boolean;
};

export type DomainFeatureState = DomainFeatureConfig & {
  status: DomainFeatureStatus;
  detail: string;
  evidenceLabels: string[];
  evidenceCount: number;
};

export type DomainControlPayload = {
  id: string;
  scope: string;
  facets: string[];
  safetyBoundary?: boolean;
};

export const DOMAIN_FEATURES: Record<DomainKey, DomainFeatureConfig[]> = {
  islam: [
    {
      id: "source-lineage",
      title: "Source lineage",
      kicker: "Qur'an · Hadith · Tafsir",
      referenceMotif: "Isnad evidence rail and source-scope chips",
      keywords: ["quran", "hadith", "tafsir", "scripture", "sunnah", "fiqh"],
      engineFacets: ["quran", "hadith", "tafsir", "fiqh", "source lineage", "isnad"],
      engineScope: "islam.source-lineage",
    },
    {
      id: "original-language",
      title: "Original text",
      kicker: "Arabic / translation",
      referenceMotif: "Arabic verse blocks and RTL scholarly reading",
      keywords: ["arabic", "primary text", "quran", "ar", "translation"],
      engineFacets: ["arabic", "original text", "translation", "source language"],
      engineScope: "islam.original-language",
    },
    {
      id: "translation-style",
      title: "Translation style",
      kicker: "Literal · study aid",
      referenceMotif: "Devotional dark query frame with source controls",
      keywords: ["translation", "meaning", "citation", "quran", "mercy", "faith"],
      engineFacets: ["translation", "meaning", "study aid", "citation"],
      engineScope: "islam.translation-style",
    },
    {
      id: "scholarly-boundary",
      title: "Scholarly boundary",
      kicker: "Not a fatwa",
      referenceMotif: "Restrained religious-study safety boundary",
      keywords: ["fatwa", "authority", "safety", "boundary", "religious", "종교", "학습"],
      engineFacets: ["fatwa boundary", "scholarly authority", "religious study safety"],
      engineScope: "islam.scholarly-boundary",
      safetyBoundary: true,
    },
  ],
  tcm: [
    {
      id: "pattern-map",
      title: "Pattern map",
      kicker: "辨證 · 체질",
      referenceMotif: "Diagnosis and constitution mapping",
      keywords: ["pattern", "변증", "체질", "spleen", "stomach", "cold", "heat", "한열"],
      engineFacets: ["pattern", "辨證", "체질", "spleen", "stomach", "cold", "heat", "한열"],
      engineScope: "tcm.pattern-map",
    },
    {
      id: "formula-herb",
      title: "Herb / formula",
      kicker: "本草 · 처방",
      referenceMotif: "Herb directory and formula grid",
      keywords: ["herb", "formula", "본초", "약재", "처방", "감초"],
      engineFacets: ["herb", "formula", "本草", "처방", "약재", "方劑"],
      engineScope: "tcm.formula-herb",
    },
    {
      id: "acupuncture-channel",
      title: "Acupuncture channel",
      kicker: "經絡 · 침구",
      referenceMotif: "Channel/acupoint consult module",
      keywords: ["acupuncture", "channel", "acupoint", "침", "경혈", "침구"],
      engineFacets: ["acupuncture", "acupoint", "channel", "针灸", "針灸", "침구", "경혈"],
      engineScope: "tcm.acupuncture-channel",
    },
    {
      id: "contraindication-safety",
      title: "Contraindication",
      kicker: "禁忌 · 안전",
      referenceMotif: "Expert verification and contraindication panel",
      keywords: ["contraindication", "safety", "pregnancy", "medication", "금기", "안전", "임신"],
      engineFacets: ["contraindication", "safety", "pregnancy", "medication", "禁忌", "금기"],
      engineScope: "tcm.contraindication-safety",
      safetyBoundary: true,
    },
  ],
  psychology: [
    {
      id: "mood-checkin",
      title: "Mood check-in",
      kicker: "Affect · note",
      referenceMotif: "Therapeutic Aurora mood/session card",
      keywords: ["mood", "depression", "anxiety", "worry", "우울", "불안", "기분"],
      engineFacets: ["mood", "depression", "anxiety", "worry", "우울", "불안", "check-in"],
      engineScope: "psychology.mood-checkin",
    },
    {
      id: "grounding-plan",
      title: "Grounding plan",
      kicker: "Here · now",
      referenceMotif: "Grounding exercise and soft session rail",
      keywords: ["grounding", "panic", "breath", "skill", "공황", "호흡", "안정"],
      engineFacets: ["grounding", "panic", "breathing", "coping skill", "공황", "호흡", "안정화"],
      engineScope: "psychology.grounding-plan",
    },
    {
      id: "crisis-boundary",
      title: "Crisis boundary",
      kicker: "Escalation",
      referenceMotif: "Safety-boundary card",
      keywords: ["self harm", "self-harm", "suicide", "crisis", "harm", "자해", "자살", "위기"],
      engineFacets: ["self harm", "suicide", "crisis", "danger", "자해", "자살", "위기"],
      engineScope: "psychology.crisis-boundary",
      safetyBoundary: true,
    },
    {
      id: "session-notes",
      title: "Session notes",
      kicker: "History",
      referenceMotif: "Note history and session list",
      keywords: ["session", "note", "history", "plan", "기록", "메모"],
      engineFacets: ["session note", "history", "plan", "기록", "follow-up"],
      engineScope: "psychology.session-notes",
    },
  ],
};

export function buildDomainFeatureStates(domain: string, answer: DomainAnswer | null, query = ""): DomainFeatureState[] {
  const key = getDomainProduct(domain).key;
  const evidence = evidenceCards(answer);
  const haystack = searchableText(answer, query);
  return DOMAIN_FEATURES[key].map((feature) => {
    const labels = labelsForFeature(feature, evidence, haystack);
    const status = statusForFeature(key, feature, labels, haystack);
    return {
      ...feature,
      status,
      detail: detailForFeature(key, feature, answer, labels, evidence),
      evidenceLabels: labels,
      evidenceCount: labels.length,
    };
  });
}

export function buildDomainControlPayload(
  domain: string,
  features: DomainFeatureState[],
  activeFeatureId = "",
): DomainControlPayload[] {
  const key = getDomainProduct(domain).key;
  const selected =
    activeFeatureId && features.some((feature) => feature.id === activeFeatureId)
      ? features.filter((feature) => feature.id === activeFeatureId)
      : features.filter((feature) => feature.status !== "idle");
  return selected.slice(0, 4).map((feature) => ({
    id: feature.id,
    scope: `${key}.${feature.engineScope.split(".").pop() || feature.id}`,
    facets: feature.engineFacets.slice(0, 10),
    safetyBoundary: feature.safetyBoundary,
  }));
}

function evidenceCards(answer: DomainAnswer | null): Array<DomainPassage | DomainSource> {
  if (Array.isArray(answer?.passages) && answer.passages.length) return answer.passages;
  return Array.isArray(answer?.sources) ? answer.sources : [];
}

function searchableText(answer: DomainAnswer | null, query: string): string {
  const parts = [
    query,
    answer?.query,
    answer?.language,
    answer?.safetyNotice,
    ...(answer?.beta6?.facets || []),
    ...(answer?.beta6?.queryStructuring?.surfaceFacets || []),
    ...(answer?.beta6?.queryStructuring?.expandedFacets || []),
    ...(answer?.answerSections || []).flatMap((section) => [section.title, section.body]),
    ...evidenceCards(answer).flatMap((item) => [
      "citation" in item ? item.citation : "",
      "title" in item ? item.title : "",
      "authorityBody" in item ? item.authorityBody : "",
      "topic" in item ? item.topic : "",
      "type" in item ? item.type : "",
      "dataset" in item ? item.dataset : "",
      "excerpt" in item ? item.excerpt : "",
    ]),
  ];
  return parts.join("\n").toLowerCase();
}

function labelsForFeature(
  feature: DomainFeatureConfig,
  evidence: Array<DomainPassage | DomainSource>,
  haystack: string,
): string[] {
  const hasGlobalMatch = feature.keywords.some((keyword) => includesKeyword(haystack, keyword));
  const labels: string[] = [];
  for (const item of evidence) {
    const text = [
      "citation" in item ? item.citation : "",
      "title" in item ? item.title : "",
      "authorityBody" in item ? item.authorityBody : "",
      "topic" in item ? item.topic : "",
      "type" in item ? item.type : "",
      "dataset" in item ? item.dataset : "",
      "excerpt" in item ? item.excerpt : "",
    ]
      .join("\n")
      .toLowerCase();
    if (hasGlobalMatch || feature.keywords.some((keyword) => includesKeyword(text, keyword))) {
      const label = "label" in item ? item.label : "";
      if (label && !labels.includes(label)) labels.push(label);
    }
  }
  return labels;
}

function statusForFeature(
  domain: DomainKey,
  feature: DomainFeatureConfig,
  labels: string[],
  haystack: string,
): DomainFeatureStatus {
  if (
    (domain === "psychology" && feature.id === "crisis-boundary" && labels.length) ||
    (domain === "tcm" && feature.id === "contraindication-safety" && labels.length)
  ) {
    return "watch";
  }
  if (labels.length || feature.keywords.some((keyword) => includesKeyword(haystack, keyword))) return "active";
  return "idle";
}

function detailForFeature(
  domain: DomainKey,
  feature: DomainFeatureConfig,
  answer: DomainAnswer | null,
  labels: string[],
  evidence: Array<DomainPassage | DomainSource>,
): string {
  const count = labels.length || evidence.length;
  const countText = `${count} ${count === 1 ? "source" : "sources"}`;
  const first = evidence[0];
  const firstCitation = first && "citation" in first ? first.citation : "";
  const language = String(answer?.language || "");
  if (domain === "islam") {
    if (feature.id === "source-lineage") return `${countText} selected: ${labels.join(", ") || "pending"}`;
    if (feature.id === "original-language") return `${language || "auto"} answer with original/source-language passage controls.`;
    if (feature.id === "translation-style") return `${firstCitation || "Selected source"} is shown as study translation evidence, not authority.`;
    return answer?.safetyNotice || "Grounded religious-study aid only; not a binding fatwa.";
  }
  if (domain === "tcm") {
    if (feature.id === "pattern-map") return `Facets and sources are mapped into pattern/formula review before any clinical use.`;
    if (feature.id === "formula-herb") return `${countText} available for herb and formula review.`;
    if (feature.id === "acupuncture-channel") return `Acupuncture/channel signals stay evidence-linked to citations.`;
    return answer?.safetyNotice || "Classical text aid only; consult a qualified clinician.";
  }
  if (feature.id === "mood-checkin") return `Mood and symptom terms are separated from diagnosis.`;
  if (feature.id === "grounding-plan") return `${countText} linked to grounding or coping evidence.`;
  if (feature.id === "crisis-boundary") return answer?.safetyNotice || "Escalate immediately if there is danger.";
  return `${countText} saved into this session note trail.`;
}

function includesKeyword(text: string, keyword: string): boolean {
  return text.includes(String(keyword || "").toLowerCase());
}
