// Predefined demo flow for the welcome-screen "체험 시연" button.
//
// User intent: when an admin presses the demo button, the workspace replays
// the actual `job-6c210c2d3e1f` (beta-4) precedent analysis as a slideshow:
//   1) Auto-type the original 스노우보드 사고 question into the composer.
//   2) Walk a synthetic 5-stage loader (~2 s per stage).
//   3) Render the cached result with our optimized 한눈에/법조인용 layout.
//   4) Present a slide sequence advanced by clicks: scroll to 1층 → 2층
//      → citation/highlight → claim cards → end.
//
// All hyperlinks/citations are preserved verbatim from the real beta-4 run;
// only the 1층/2층 narrative was re-written to match our new ideology.

import type { JobResultPayload, JobStatusPayload } from "./api";
import demoSnapshot from "../data/demo/snapshot.json";

export type DemoSnapshot = {
  status: JobStatusPayload;
  result: JobResultPayload;
};

const SNAPSHOT = demoSnapshot as unknown as DemoSnapshot;

export const DEMO_PROMPT = String((SNAPSHOT.status as { userTask?: string }).userTask || "").trim();
export const DEMO_JOB_ID = String(SNAPSHOT.status.jobId || "demo-job");

export function loadDemoSnapshot(): DemoSnapshot {
  return SNAPSHOT;
}

export type DemoStage = {
  id: string;
  label: string;
  state: string;
  durationMs: number;
};

export const DEMO_STAGES: DemoStage[] = [
  { id: "keywords", label: "키워드 생성", state: "generating_keywords", durationMs: 2000 },
  { id: "selection", label: "근거 선별", state: "building_chunk_plan", durationMs: 2000 },
  { id: "analyze", label: "문서별 관련성 분석", state: "analyzing_chunks", durationMs: 2000 },
  { id: "synthesize", label: "근거 기반 답변 합성", state: "writing_final_draft", durationMs: 2000 },
  { id: "done", label: "완료", state: "completed", durationMs: 200 },
];

// Slide step descriptors driving the post-result click-to-advance flow.
// Anchors are heading texts inside the optimized markdown; the controller
// scrolls until the matching DOM heading is centered, OR programmatically
// opens a precedent detail.
export type DemoSlide =
  | { kind: "scroll"; anchor: string; tip: string }
  | { kind: "precedent"; precedentId: string; anchor: string; tip: string }
  | { kind: "back"; tip: string }
  | { kind: "claim_cards"; tip: string }
  | { kind: "end" };

export const DEMO_SLIDES: DemoSlide[] = [
  // 1: top — laypeople easy overview (the prepended layer1).
  { kind: "scroll", anchor: "## 어렵지 않아요", tip: "어렵지 않아요" },
  // 2: backend-prepended summary block (가장 같은 사실관계 판례).
  { kind: "scroll", anchor: "### 가장 같은 사실관계 판례", tip: "가장 같은 사실관계 판례" },
  // 3: 가장 가능성 높은 결론 + 결론 근거.
  { kind: "scroll", anchor: "### 가장 가능성 높은 결론", tip: "가장 가능성 높은 결론" },
  // 4: 종합 판단 본문.
  { kind: "scroll", anchor: "## 종합 판단", tip: "종합 판단" },
  // 5: 가해자 및 시설물 책임 축.
  { kind: "scroll", anchor: "### 가해자 및 시설물 책임", tip: "가해자 및 시설물 책임 축" },
  // 6: open precedent detail with highlight.
  { kind: "precedent", precedentId: pickFirstUsedPrecedentId(), anchor: "### 가해자 및 시설물 책임", tip: "인용 판례 본문 하이라이트" },
  // 7: back to answer.
  { kind: "back", tip: "응답으로 돌아가기" },
  // 8: 사고-상병 인과관계 축.
  { kind: "scroll", anchor: "### 사고와 상병 간의 인과관계 및 기왕증", tip: "사고-부상 인과관계 축" },
  // 9: 참고 판례 목록.
  { kind: "scroll", anchor: "## 참고 판례 목록", tip: "참고 판례 목록" },
  // 10: claim cards (주장 카드).
  { kind: "claim_cards", tip: "주장 카드 — 같은 근거가 여러 주장을 지지" },
  { kind: "end" },
];

function pickFirstUsedPrecedentId(): string {
  const used = SNAPSHOT.result?.usedPrecedents;
  if (used && used.length > 0 && used[0].precedentId) {
    return used[0].precedentId;
  }
  const selected = SNAPSHOT.result?.selectedPrecedents;
  if (selected && selected.length > 0 && selected[0].precedentId) {
    return selected[0].precedentId;
  }
  return "";
}

// Type-an-input animation: returns each progressively-longer prefix at the
// requested cadence. Caller wires this into the prompt state.
export function buildTypingFrames(text: string, perCharMs = 35): { ms: number; value: string }[] {
  const frames: { ms: number; value: string }[] = [];
  let acc = 0;
  for (let i = 1; i <= text.length; i++) {
    acc += perCharMs;
    frames.push({ ms: acc, value: text.slice(0, i) });
  }
  return frames;
}
