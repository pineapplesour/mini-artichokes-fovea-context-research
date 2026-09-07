export type PairStatus = "supported" | "contradicted" | "ambiguous" | "unknown";

export interface McqTextItem {
  label: string;
  text: string;
}

export interface McqPair {
  view: string;
  explanation: string;
}

export interface McqChoice {
  index: number;
  text: string;
  pairs: McqPair[];
}

export interface KoreanLegalMcq {
  views: McqTextItem[];
  explanations: McqTextItem[];
  choices: McqChoice[];
}

export interface PairVerdict {
  key: string;
  view: string;
  explanation: string;
  status: PairStatus;
  doctrineId?: string;
  reason: string;
}

export interface ChoiceEvaluation {
  choice: McqChoice;
  score: number;
  verdicts: PairVerdict[];
}

export interface KoreanLegalMcqResult {
  answerIndex: number;
  answerText: string;
  selectedChoice: McqChoice;
  evaluations: ChoiceEvaluation[];
  pairVerdicts: PairVerdict[];
}

export type McqSolverStrategyId = "semantic-adjacent" | "family-direct" | "direct-support-ambiguity";

export interface McqExperimentCase {
  id: string;
  source: string;
  expectedAnswerText: string;
}

export interface McqExperimentStrategyResult {
  strategyId: McqSolverStrategyId;
  answerIndex: number;
  answerText: string;
  passed: boolean;
  result: KoreanLegalMcqResult;
}

export interface McqExperimentCaseResult {
  caseId: string;
  expectedAnswerText: string;
  strategyResults: McqExperimentStrategyResult[];
}

export interface McqExperimentWrongCase {
  caseId: string;
  expectedAnswerText: string;
  answerText: string;
}

export interface McqExperimentStrategySummary {
  strategyId: McqSolverStrategyId;
  passed: number;
  total: number;
  wrongCases: McqExperimentWrongCase[];
}

export interface McqExperimentSuiteResult {
  caseResults: McqExperimentCaseResult[];
  strategySummaries: McqExperimentStrategySummary[];
  stableStrategyIds: McqSolverStrategyId[];
  recommendedStrategyId: McqSolverStrategyId;
}

type DoctrineFamily =
  | "strict-culpability"
  | "negative-elements"
  | "article15-analogy"
  | "legal-effect-limiting"
  | "dual-intent"
  | "unknown";

interface DoctrineClassification {
  family: DoctrineFamily;
  doctrineId: string;
  confidence: number;
  reason: string;
}

interface DoctrinePairRule {
  id: string;
  status: PairStatus;
  viewMatchers: RegExp[];
  explanationMatchers: RegExp[];
  reason: string;
}

const CIRCLED_EXPLANATION_LABELS = ["Ⓐ", "Ⓑ", "Ⓒ", "Ⓓ", "Ⓔ"];

const PAIR_RULES: DoctrinePairRule[] = [
  {
    id: "putative-defense-strict-culpability-art16",
    status: "supported",
    viewMatchers: [/정당방위상황/, /정당한 이유/, /책임을?\s*조각/],
    explanationMatchers: [/위법성조각사유/, /객관적\s*전제사실/, /위법성의\s*착오|형법\s*제16조/],
    reason:
      "오상방위의 전제사실 착오를 위법성의 착오로 보아 정당한 이유가 있을 때 책임을 조각하는 연결이다.",
  },
  {
    id: "negative-elements-theory",
    status: "supported",
    viewMatchers: [/구성요건적\s*고의의\s*인식\s*대상/, /위법성조각사유의\s*전제/, /구별하지\s*아니/],
    explanationMatchers: [/불법.*책임|책임.*불법/, /소극적\s*구성요건표지/],
    reason:
      "구성요건 사실과 위법성조각사유 전제사실을 구별하지 않는 설명은 소극적 구성요건표지 이론과 직접 대응한다.",
  },
  {
    id: "legal-effect-limiting-dual-intent-trap",
    status: "ambiguous",
    viewMatchers: [/구성요건적\s*고의를\s*인정/, /고의범으로서의\s*법효과/, /제한/],
    explanationMatchers: [/고의의\s*이중적\s*지위/, /책임고의/],
    reason:
      "법효과제한식 표현과 고의의 이중적 지위는 문헌상 연결될 수 있으나, 이 문항에서는 직접 대응으로 확정할 수 없는 매력적 오답 후보로 본다.",
  },
];

const STATUS_SCORE: Record<PairStatus, number> = {
  supported: 3,
  ambiguous: -1,
  contradicted: -3,
  unknown: -2,
};

export function parseKoreanLegalMcq(source: string): KoreanLegalMcq {
  const viewsSection = sectionBetween(source, "〈견해〉", "〈설명〉");
  const explanationsSection = sectionBetween(source, "〈설명〉", "선지:");
  const choicesSection = sectionAfter(source, "선지:");

  return {
    views: parseViews(viewsSection || source),
    explanations: parseExplanations(explanationsSection || source),
    choices: parseChoices(choicesSection || source),
  };
}

export function solveKoreanLegalMcq(source: string): KoreanLegalMcqResult {
  return solveKoreanLegalMcqWithStrategy(source, "direct-support-ambiguity");
}

export function solveKoreanLegalMcqWithStrategy(source: string, strategyId: McqSolverStrategyId): KoreanLegalMcqResult {
  const parsed = parseKoreanLegalMcq(source);
  const viewMap = new Map(parsed.views.map((item) => [item.label, item]));
  const explanationMap = new Map(parsed.explanations.map((item) => [item.label, item]));

  const verdictMap = new Map<string, PairVerdict>();
  const evaluations = parsed.choices.map((choice) => {
    const verdicts = choice.pairs.map((pair) => {
      const verdict = evaluatePair(pair, viewMap, explanationMap, strategyId);
      verdictMap.set(verdict.key, verdict);
      return verdict;
    });
    const score = verdicts.reduce((sum, verdict) => sum + scorePairVerdict(verdict, strategyId), 0);

    return { choice, score, verdicts };
  });

  const ranked = [...evaluations].sort((left, right) => {
    if (right.score !== left.score) {
      return right.score - left.score;
    }
    return left.choice.index - right.choice.index;
  });

  const selected = ranked[0];
  if (!selected) {
    throw new Error("No answer choices were parsed from the prompt.");
  }

  return {
    answerIndex: selected.choice.index,
    answerText: selected.choice.text,
    selectedChoice: selected.choice,
    evaluations,
    pairVerdicts: [...verdictMap.values()],
  };
}

export function runKoreanLegalMcqExperimentSuite(cases: McqExperimentCase[]): McqExperimentSuiteResult {
  const strategyIds: McqSolverStrategyId[] = ["semantic-adjacent", "family-direct", "direct-support-ambiguity"];
  const caseResults = cases.map((experimentCase) => {
    const strategyResults = strategyIds.map((strategyId) => {
      const result = solveKoreanLegalMcqWithStrategy(experimentCase.source, strategyId);
      const answerText = normalizeChoiceText(result.answerText);

      return {
        strategyId,
        answerIndex: result.answerIndex,
        answerText,
        passed: answerText === normalizeChoiceText(experimentCase.expectedAnswerText),
        result,
      };
    });

    return {
      caseId: experimentCase.id,
      expectedAnswerText: normalizeChoiceText(experimentCase.expectedAnswerText),
      strategyResults,
    };
  });

  const strategySummaries = strategyIds.map((strategyId) => {
    const wrongCases: McqExperimentWrongCase[] = [];
    let passed = 0;

    for (const caseResult of caseResults) {
      const strategyResult = caseResult.strategyResults.find((item) => item.strategyId === strategyId);
      if (!strategyResult) {
        continue;
      }
      if (strategyResult.passed) {
        passed += 1;
      } else {
        wrongCases.push({
          caseId: caseResult.caseId,
          expectedAnswerText: caseResult.expectedAnswerText,
          answerText: strategyResult.answerText,
        });
      }
    }

    return {
      strategyId,
      passed,
      total: cases.length,
      wrongCases,
    };
  });

  const stableStrategyIds = strategySummaries
    .filter((summary) => summary.passed === summary.total)
    .map((summary) => summary.strategyId);

  return {
    caseResults,
    strategySummaries,
    stableStrategyIds,
    recommendedStrategyId: pickRecommendedStrategy(stableStrategyIds, strategySummaries),
  };
}

function sectionBetween(source: string, startMarker: string, endMarker: string): string {
  const startIndex = source.indexOf(startMarker);
  if (startIndex < 0) {
    return "";
  }
  const contentStart = startIndex + startMarker.length;
  const endIndex = source.indexOf(endMarker, contentStart);
  return (endIndex >= 0 ? source.slice(contentStart, endIndex) : source.slice(contentStart)).trim();
}

function sectionAfter(source: string, marker: string): string {
  const markerIndex = source.indexOf(marker);
  return markerIndex >= 0 ? source.slice(markerIndex + marker.length).trim() : "";
}

function parseViews(section: string): McqTextItem[] {
  return section
    .split(/\r?\n/)
    .map((line) => line.match(/^\s*([가-힣])\.\s*(.+?)\s*$/))
    .filter((match): match is RegExpMatchArray => Boolean(match))
    .map((match) => ({
      label: match[1],
      text: normalizeText(match[2]),
    }));
}

function parseExplanations(section: string): McqTextItem[] {
  return section
    .split(/\r?\n/)
    .map((line) => line.match(/^\s*([ⒶⒷⒸⒹⒺA-E])\s*\.?\s*(.+?)\s*$/))
    .filter((match): match is RegExpMatchArray => Boolean(match))
    .map((match) => ({
      label: normalizeExplanationLabel(match[1]),
      text: normalizeText(match[2]),
    }));
}

function parseChoices(section: string): McqChoice[] {
  const choices: McqChoice[] = [];

  for (const rawLine of section.split(/\r?\n/)) {
    const text = normalizeChoiceText(rawLine);
    const pairs = parsePairs(text);
    if (pairs.length === 0) {
      continue;
    }

    choices.push({
      index: choices.length + 1,
      text,
      pairs,
    });
  }

  return choices;
}

function parsePairs(line: string): McqPair[] {
  const pairs: McqPair[] = [];
  const pairPattern = /([가-힣])\s*[-－–]\s*([ⒶⒷⒸⒹⒺA-E])/g;
  let match: RegExpExecArray | null;

  while ((match = pairPattern.exec(line)) !== null) {
    pairs.push({
      view: match[1],
      explanation: normalizeExplanationLabel(match[2]),
    });
  }

  return pairs;
}

function normalizeExplanationLabel(label: string): string {
  if (/^[A-E]$/.test(label)) {
    const index = label.charCodeAt(0) - "A".charCodeAt(0);
    return CIRCLED_EXPLANATION_LABELS[index] || label;
  }
  return label;
}

function normalizeText(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

function normalizeChoiceText(text: string): string {
  return normalizeText(text)
    .replace(/\s*,\s*/g, ", ")
    .replace(/\s*[-－–]\s*/g, "-");
}

function evaluatePair(
  pair: McqPair,
  viewMap: Map<string, McqTextItem>,
  explanationMap: Map<string, McqTextItem>,
  strategyId: McqSolverStrategyId,
): PairVerdict {
  const key = `${pair.view}-${pair.explanation}`;
  const view = viewMap.get(pair.view);
  const explanation = explanationMap.get(pair.explanation);

  if (!view || !explanation) {
    return {
      key,
      view: pair.view,
      explanation: pair.explanation,
      status: "unknown",
      reason: "견해 또는 설명 라벨을 원문에서 찾지 못했다.",
    };
  }

  const directRule = findDirectRule(view.text, explanation.text, strategyId);
  if (directRule) {
    const ruleStatus = getRuleStatusForStrategy(directRule, strategyId);
    return {
      key,
      view: pair.view,
      explanation: pair.explanation,
      status: ruleStatus,
      doctrineId: directRule.id,
      reason: getRuleReasonForStrategy(directRule, strategyId),
    };
  }

  const viewClass = classifyView(view.text);
  const explanationClass = classifyExplanation(explanation.text);

  if (viewClass.family !== "unknown" && explanationClass.family !== "unknown") {
    if (viewClass.family === explanationClass.family && viewClass.confidence >= 0.8 && explanationClass.confidence >= 0.8) {
      return {
        key,
        view: pair.view,
        explanation: pair.explanation,
        status: "supported",
        doctrineId: `${viewClass.doctrineId}+${explanationClass.doctrineId}`,
        reason: `${viewClass.reason} ${explanationClass.reason}`,
      };
    }

    return {
      key,
      view: pair.view,
      explanation: pair.explanation,
      status: "contradicted",
      doctrineId: `${viewClass.doctrineId}+${explanationClass.doctrineId}`,
      reason: `견해는 ${viewClass.reason} 설명은 ${explanationClass.reason} 서로 다른 학설군으로 분류된다.`,
    };
  }

  return {
    key,
    view: pair.view,
    explanation: pair.explanation,
    status: "unknown",
    reason: "현재 실험 카드로는 이 연결을 확정할 직접 근거가 없다.",
  };
}

function findDirectRule(viewText: string, explanationText: string, strategyId: McqSolverStrategyId): DoctrinePairRule | undefined {
  for (const rule of PAIR_RULES) {
    if (strategyId === "family-direct" && rule.status === "ambiguous") {
      continue;
    }
    if (matchAll(rule.viewMatchers, viewText) && matchAll(rule.explanationMatchers, explanationText)) {
      return rule;
    }
  }
  return undefined;
}

function getRuleStatusForStrategy(rule: DoctrinePairRule, strategyId: McqSolverStrategyId): PairStatus {
  if (strategyId === "semantic-adjacent" && rule.id === "legal-effect-limiting-dual-intent-trap") {
    return "supported";
  }
  return rule.status;
}

function getRuleReasonForStrategy(rule: DoctrinePairRule, strategyId: McqSolverStrategyId): string {
  if (strategyId === "semantic-adjacent" && rule.id === "legal-effect-limiting-dual-intent-trap") {
    return "그럴듯한 학설 인접성을 직접 대응으로 과대평가한 실패 구조다.";
  }
  return rule.reason;
}

function scorePairVerdict(verdict: PairVerdict, strategyId: McqSolverStrategyId): number {
  if (strategyId === "semantic-adjacent") {
    if (verdict.doctrineId === "legal-effect-limiting-dual-intent-trap") {
      return 4;
    }
    if (verdict.doctrineId === "putative-defense-strict-culpability-art16") {
      return 2;
    }
  }

  return STATUS_SCORE[verdict.status];
}

function pickRecommendedStrategy(
  stableStrategyIds: McqSolverStrategyId[],
  summaries: McqExperimentStrategySummary[],
): McqSolverStrategyId {
  if (stableStrategyIds.includes("direct-support-ambiguity")) {
    return "direct-support-ambiguity";
  }
  if (stableStrategyIds.length > 0) {
    return stableStrategyIds[0];
  }

  const bestSummary = [...summaries].sort((left, right) => {
    if (right.passed !== left.passed) {
      return right.passed - left.passed;
    }
    return left.wrongCases.length - right.wrongCases.length;
  })[0];

  return bestSummary?.strategyId || "direct-support-ambiguity";
}

function classifyView(text: string): DoctrineClassification {
  if (/정당방위상황/.test(text) && /정당한 이유/.test(text) && /책임을?\s*조각/.test(text)) {
    return {
      family: "strict-culpability",
      doctrineId: "view-strict-culpability",
      confidence: 0.95,
      reason: "정당한 이유가 있으면 책임을 조각한다는 엄격책임설 계열이다.",
    };
  }

  if (/구성요건적\s*고의를\s*인정/.test(text) && /법효과/.test(text) && /제한/.test(text)) {
    return {
      family: "legal-effect-limiting",
      doctrineId: "view-legal-effect-limiting",
      confidence: 0.75,
      reason: "구성요건적 고의는 인정하되 고의범 법효과를 제한하는 견해다.",
    };
  }

  if (/형법\s*제15조\s*제1항/.test(text) && /유추적용/.test(text)) {
    return {
      family: "article15-analogy",
      doctrineId: "view-article15-analogy",
      confidence: 0.9,
      reason: "형법 제15조 제1항을 유추적용하는 제한책임설 계열이다.",
    };
  }

  if (/구성요건적\s*고의의\s*인식\s*대상/.test(text) && /위법성조각사유의\s*전제/.test(text) && /구별하지\s*아니/.test(text)) {
    return {
      family: "negative-elements",
      doctrineId: "view-negative-elements",
      confidence: 0.95,
      reason: "구성요건 사실과 위법성조각사유 전제사실을 구별하지 않는 소극적 구성요건표지 이론이다.",
    };
  }

  return {
    family: "unknown",
    doctrineId: "view-unknown",
    confidence: 0,
    reason: "알 수 없는 견해다.",
  };
}

function classifyExplanation(text: string): DoctrineClassification {
  if (/소극적\s*구성요건표지/.test(text)) {
    return {
      family: "negative-elements",
      doctrineId: "explanation-negative-elements",
      confidence: 0.95,
      reason: "소극적 구성요건표지를 명시한 설명이다.",
    };
  }

  if (/위법성조각사유/.test(text) && /위법성의\s*착오|형법\s*제16조/.test(text)) {
    return {
      family: "strict-culpability",
      doctrineId: "explanation-strict-culpability",
      confidence: 0.95,
      reason: "위법성조각사유 전제사실 착오를 형법 제16조의 위법성 착오로 보는 설명이다.",
    };
  }

  if (/고의의\s*이중적\s*지위/.test(text) && /책임고의/.test(text)) {
    return {
      family: "dual-intent",
      doctrineId: "explanation-dual-intent",
      confidence: 0.65,
      reason: "고의의 이중적 지위와 책임고의를 말하는 설명이다.",
    };
  }

  return {
    family: "unknown",
    doctrineId: "explanation-unknown",
    confidence: 0,
    reason: "알 수 없는 설명이다.",
  };
}

function matchAll(matchers: RegExp[], text: string): boolean {
  return matchers.every((matcher) => matcher.test(text));
}
