import type { AnalysisMode } from "./api";

export type VisibleAnalysisMode = Exclude<AnalysisMode, "beta1">;

export type AnalysisModeOption = {
  mode: VisibleAnalysisMode;
  title: string;
  description: string;
};

export const PUBLIC_ANALYSIS_MODE: VisibleAnalysisMode = "beta6";

const ADMIN_ANALYSIS_MODE_OPTIONS: AnalysisModeOption[] = [
  {
    mode: "fast",
    title: "빠른 분석",
    description: "판례 30건, 키워드 주변만 읽어 빠르게 분석",
  },
  {
    mode: "precise",
    title: "정밀 분석",
    description: "판례 100건, 전체 본문 정밀 분석",
  },
  {
    mode: "beta2",
    title: "분석 BETA-2",
    description: "Gemma 의미 그룹 확장 + 실제 본문 학습으로 반복 검색, 30만 판례에서 핵심 판례를 놓치지 않고 회수",
  },
  {
    mode: "beta3",
    title: "분석 BETA-3",
    description: "R25 스타일: FTS 광범위 회수 → 로컬 BM25 + Gemma 0-9 점수 → RRF 융합",
  },
  {
    mode: "beta4",
    title: "분석 BETA-4",
    description: "라운드별 점진 확대 (10→20→30→40) + 100개까지 반복 판정, 1라운드마다 새 검색 각도 학습",
  },
  {
    mode: "beta5",
    title: "분석 BETA-5",
    description: "질의 구조화 → 후보 union → 행위자/대상/도구 검증 → 짧은 본문 window 판정으로 키워드 유사 오답을 낮춤",
  },
  {
    mode: "beta6",
    title: "분석 BETA-6",
    description: "r133 통과 선택기 원리를 포팅: union 후보, 검증기, 거절 장부, 최대 5라운드 재구조화로 판례를 고름",
  },
  {
    mode: "beta7",
    title: "분석 BETA-7",
    description: "최소 프롬프트 + 토큰 인용 + 커버리지 패치 제거: writer 가 신뢰할 만한 claim 만 본인 판단으로 인용. 빠르고 자연스러운 흐름.",
  },
  {
    mode: "beta8",
    title: "분석 BETA-8",
    description: "BETA-6 판례 선택에 법률명제 self-check를 붙여 선택형·견해-설명형 오답을 최종 노출 전 검증",
  },
];

const PUBLIC_ANALYSIS_MODE_OPTIONS: AnalysisModeOption[] = [
  {
    mode: PUBLIC_ANALYSIS_MODE,
    title: "정밀 분석",
    description: "판례를 정밀하게 선별해 분석합니다.",
  },
];

export function isVisibleAnalysisMode(value: string): value is VisibleAnalysisMode {
  return value === "precise" || value === "fast" || value === "beta2" || value === "beta3" || value === "beta4" || value === "beta5" || value === "beta6" || value === "beta7" || value === "beta8";
}

export function normalizeAnalysisModeForRole(value: string, isAdmin: boolean): VisibleAnalysisMode {
  if (!isAdmin) {
    return PUBLIC_ANALYSIS_MODE;
  }
  if (value === "beta1") {
    return "fast";
  }
  return isVisibleAnalysisMode(value) ? value : PUBLIC_ANALYSIS_MODE;
}

export function getVisibleAnalysisModeOptions(isAdmin: boolean): AnalysisModeOption[] {
  return isAdmin ? ADMIN_ANALYSIS_MODE_OPTIONS : PUBLIC_ANALYSIS_MODE_OPTIONS;
}

export function getAnalysisModeLabel(mode: VisibleAnalysisMode, isAdmin: boolean): string {
  const normalized = normalizeAnalysisModeForRole(mode, isAdmin);
  const options = getVisibleAnalysisModeOptions(isAdmin);
  return options.find((item) => item.mode === normalized)?.title || "정밀 분석";
}
