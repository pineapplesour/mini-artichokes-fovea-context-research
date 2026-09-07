import { parseKoreanLegalMcq, type KoreanLegalMcq, type McqChoice, type McqPair, type McqTextItem } from "./exam-mcq-solver";

export type LegalVerificationStatus = "supported" | "contradicted" | "ambiguous" | "unsupported";
export type AuthorityRelation = "direct" | "broad" | "contradict";

export interface LegalAuthorityStatement {
  id: string;
  title: string;
  text: string;
  concepts: string[];
  relation: AuthorityRelation;
}

export interface LegalProposition {
  key: string;
  text: string;
  concepts: string[];
  kind: "mcq-pair" | "advice-claim";
}

export interface LegalPropositionVerdict {
  key: string;
  proposition: LegalProposition;
  status: LegalVerificationStatus;
  authorityIds: string[];
  reason: string;
}

export interface LegalPropositionVerification {
  propositions: LegalProposition[];
  propositionVerdicts: LegalPropositionVerdict[];
  choiceVerdicts: Array<{
    choice: McqChoice;
    supported: boolean;
    score: number;
    verdicts: LegalPropositionVerdict[];
  }>;
  recommendedAnswerText: string;
}

export interface LegalDraftIssue {
  propositionKey: string;
  status: LegalVerificationStatus;
  reason: string;
}

export interface LegalDraftSelfCheck {
  ok: boolean;
  issues: LegalDraftIssue[];
  recommendedAnswerText?: string;
}

const STATUS_SCORE: Record<LegalVerificationStatus, number> = {
  supported: 3,
  ambiguous: -1,
  unsupported: -2,
  contradicted: -3,
};

const CIRCLED_LABELS = ["Ⓐ", "Ⓑ", "Ⓒ", "Ⓓ", "Ⓔ"];

export function buildLegalPropositionVerification(
  source: string,
  authorities: LegalAuthorityStatement[],
): LegalPropositionVerification {
  const parsed = parseKoreanLegalMcq(source);
  const propositions = extractMcqPairPropositions(parsed);
  const verdictMap = new Map<string, LegalPropositionVerdict>();

  for (const proposition of propositions) {
    verdictMap.set(proposition.key, verifyLegalProposition(proposition, authorities));
  }

  const choiceVerdicts = parsed.choices.map((choice) => {
    const verdicts = choice.pairs.map((pair) => verdictMap.get(pairKey(pair))).filter((item): item is LegalPropositionVerdict => Boolean(item));
    const score = verdicts.reduce((sum, verdict) => sum + STATUS_SCORE[verdict.status], 0);

    return {
      choice,
      supported: verdicts.length === choice.pairs.length && verdicts.every((verdict) => verdict.status === "supported"),
      score,
      verdicts,
    };
  });

  const supportedChoice = choiceVerdicts.find((item) => item.supported);
  const recommended = supportedChoice || [...choiceVerdicts].sort((left, right) => right.score - left.score || left.choice.index - right.choice.index)[0];

  return {
    propositions,
    propositionVerdicts: [...verdictMap.values()],
    choiceVerdicts,
    recommendedAnswerText: recommended?.choice.text || "",
  };
}

export function selfCheckLegalAnswerDraft(draft: string, verification: LegalPropositionVerification): LegalDraftSelfCheck {
  const assertedPairs = extractAssertedPairKeys(draft);
  const verdictsByKey = new Map(verification.propositionVerdicts.map((verdict) => [verdict.key, verdict]));
  const issues: LegalDraftIssue[] = [];

  for (const key of assertedPairs) {
    const verdict = verdictsByKey.get(key);
    if (!verdict) {
      continue;
    }
    if (verdict.status !== "supported") {
      issues.push({
        propositionKey: key,
        status: verdict.status,
        reason: verdict.reason,
      });
    }
  }

  return {
    ok: issues.length === 0,
    issues,
    recommendedAnswerText: issues.length ? verification.recommendedAnswerText : undefined,
  };
}

export function verifyAdviceDraftClaims(draft: string, authorities: LegalAuthorityStatement[]): LegalDraftSelfCheck {
  const propositions = extractAdvicePropositions(draft);
  const issues: LegalDraftIssue[] = [];

  for (const proposition of propositions) {
    const verdict = verifyLegalProposition(proposition, authorities);
    if (verdict.status !== "supported") {
      issues.push({
        propositionKey: proposition.key,
        status: verdict.status,
        reason: verdict.reason,
      });
    }
  }

  return {
    ok: issues.length === 0,
    issues,
  };
}

export function verifyLegalProposition(
  proposition: LegalProposition,
  authorities: LegalAuthorityStatement[],
): LegalPropositionVerdict {
  const polarityContradictions = authorities.filter((authority) => contradictsByPolarity(authority.concepts, proposition.concepts));
  if (polarityContradictions.length > 0) {
    return {
      key: proposition.key,
      proposition,
      status: "contradicted",
      authorityIds: polarityContradictions.map((authority) => authority.id),
      reason: `같은 법률 쟁점에 대해 반대 결론의 근거가 있다: ${polarityContradictions.map((authority) => authority.title).join(", ")}`,
    };
  }

  const matching = authorities.filter((authority) => coversConcepts(authority.concepts, proposition.concepts));
  const contradictory = matching.filter((authority) => authority.relation === "contradict");
  if (contradictory.length > 0) {
    return {
      key: proposition.key,
      proposition,
      status: "contradicted",
      authorityIds: contradictory.map((authority) => authority.id),
      reason: `근거가 명제와 충돌한다: ${contradictory.map((authority) => authority.title).join(", ")}`,
    };
  }

  const direct = matching.filter((authority) => authority.relation === "direct");
  if (direct.length > 0) {
    return {
      key: proposition.key,
      proposition,
      status: "supported",
      authorityIds: direct.map((authority) => authority.id),
      reason: `직접 근거가 있다: ${direct.map((authority) => authority.title).join(", ")}`,
    };
  }

  const broad = matching.filter((authority) => authority.relation === "broad");
  if (broad.length > 0) {
    return {
      key: proposition.key,
      proposition,
      status: "ambiguous",
      authorityIds: broad.map((authority) => authority.id),
      reason: `관련 근거는 있으나 직접 지지는 아니다: ${broad.map((authority) => authority.title).join(", ")}`,
    };
  }

  return {
    key: proposition.key,
    proposition,
    status: "unsupported",
    authorityIds: [],
    reason: "검색된 근거가 이 명제를 직접 지지하지 않는다.",
  };
}

function extractMcqPairPropositions(parsed: KoreanLegalMcq): LegalProposition[] {
  const viewMap = new Map(parsed.views.map((item) => [item.label, item]));
  const explanationMap = new Map(parsed.explanations.map((item) => [item.label, item]));
  const seen = new Set<string>();
  const propositions: LegalProposition[] = [];

  for (const choice of parsed.choices) {
    for (const pair of choice.pairs) {
      const key = pairKey(pair);
      if (seen.has(key)) {
        continue;
      }
      seen.add(key);
      const view = viewMap.get(pair.view);
      const explanation = explanationMap.get(pair.explanation);
      propositions.push(buildPairProposition(pair, view, explanation));
    }
  }

  return propositions;
}

function buildPairProposition(pair: McqPair, view?: McqTextItem, explanation?: McqTextItem): LegalProposition {
  const viewConcept = classifyMcqSide(view?.text || "");
  const explanationConcept = classifyMcqSide(explanation?.text || "");

  return {
    key: pairKey(pair),
    text: `${pair.view} 견해와 ${pair.explanation} 설명이 직접 대응한다.`,
    concepts: [viewConcept, explanationConcept].filter((concept) => concept !== "unknown"),
    kind: "mcq-pair",
  };
}

function extractAdvicePropositions(draft: string): LegalProposition[] {
  const compact = draft.replace(/\s+/g, "");
  const propositions: LegalProposition[] = [];
  const mentionsSelfEvidence = /자기|자신|본인/.test(compact) && /증거.*(인멸|없애|없)/.test(compact);
  const saysPunishable = /죄.*성립|처벌|범죄|유죄/.test(compact) && !/성립하지않|처벌되지않|불가벌|죄가아니/.test(compact);
  const saysNotPunishable = /성립하지않|처벌되지않|불가벌|죄가아니/.test(compact);

  if (mentionsSelfEvidence && saysPunishable) {
    propositions.push({
      key: "self-evidence-destruction-punishable",
      text: "자기 형사사건 증거를 직접 인멸하면 증거인멸죄가 성립한다.",
      concepts: ["self-evidence-destruction", "punishable"],
      kind: "advice-claim",
    });
  } else if (mentionsSelfEvidence && saysNotPunishable) {
    propositions.push({
      key: "self-evidence-destruction-not-punishable",
      text: "자기 형사사건 증거를 직접 인멸하는 행위는 원칙적으로 증거인멸죄가 성립하지 않는다.",
      concepts: ["self-evidence-destruction", "not-punishable"],
      kind: "advice-claim",
    });
  }

  return propositions;
}

function classifyMcqSide(text: string): string {
  if (/정당방위상황/.test(text) && /정당한\s*이유/.test(text) && /책임을?\s*조각/.test(text)) {
    return "putative-defense-justification";
  }
  if (/위법성조각사유/.test(text) && (/형법\s*제16조/.test(text) || /위법성의\s*착오/.test(text))) {
    return "art16-prohibition-error";
  }
  if (/구성요건적\s*고의/.test(text) && /법효과/.test(text) && /제한/.test(text)) {
    return "legal-effect-limiting";
  }
  if (/고의의\s*이중적\s*지위/.test(text) || /책임고의/.test(text)) {
    return "dual-intent";
  }
  if (/형법\s*제15조\s*제1항/.test(text) || /사실의\s*착오.*유추/.test(text)) {
    return "article15-analogy";
  }
  if (/구별하지\s*아니/.test(text) || (/구성요건적\s*고의의\s*인식\s*대상/.test(text) && /위법성조각사유의\s*전제/.test(text))) {
    return "no-distinction-justification-facts";
  }
  if (/소극적\s*구성요건표지/.test(text)) {
    return "negative-elements-theory";
  }
  return "unknown";
}

function coversConcepts(authorityConcepts: string[], propositionConcepts: string[]): boolean {
  if (propositionConcepts.length === 0) {
    return false;
  }
  return propositionConcepts.every((concept) => authorityConcepts.includes(concept));
}

function contradictsByPolarity(authorityConcepts: string[], propositionConcepts: string[]): boolean {
  const sharedSubject = propositionConcepts
    .filter((concept) => concept !== "punishable" && concept !== "not-punishable")
    .some((concept) => authorityConcepts.includes(concept));
  if (!sharedSubject) {
    return false;
  }
  return (
    (propositionConcepts.includes("punishable") && authorityConcepts.includes("not-punishable")) ||
    (propositionConcepts.includes("not-punishable") && authorityConcepts.includes("punishable"))
  );
}

function extractAssertedPairKeys(draft: string): string[] {
  const keys = new Set<string>();
  const pattern = /([가-힣])\s*[-－–]\s*([ⒶⒷⒸⒹⒺA-E])/g;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(draft)) !== null) {
    keys.add(`${match[1]}-${normalizeExplanationLabel(match[2])}`);
  }
  return [...keys];
}

function normalizeExplanationLabel(label: string): string {
  if (/^[A-E]$/.test(label)) {
    const index = label.charCodeAt(0) - "A".charCodeAt(0);
    return CIRCLED_LABELS[index] || label;
  }
  return label;
}

function pairKey(pair: McqPair): string {
  return `${pair.view}-${pair.explanation}`;
}
