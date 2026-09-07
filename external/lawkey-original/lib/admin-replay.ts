// Admin presentation replay layer.
//
// When an admin (the LoginGate has authed with username `admin`) runs a real
// job, the workspace snapshots the prompt + final status + final result into
// localStorage under this module. From then on, opening that job in admin
// mode replays the saved progression with a deterministic 2-second-per-stage
// loader animation (no real API call), and the cached final answer is shown.
//
// The user explicitly asked: "first time it's a real send; after that, any
// input from that history row is treated as the original prompt and re-press
// re-plays the predefined stages" — so this module exposes:
//   - saveAdminReplaySnapshot / loadAdminReplaySnapshot
//   - replay stage definitions (each 2 s)
//   - editAdminReplayAnswer (admin-only post-edit of the cached markdown)
//
// All state is local to the browser. Server-side data is untouched.

import type { JobResultPayload, JobStatusPayload } from "./api";

export type AdminReplaySnapshot = {
  version: 1;
  jobId: string;
  prompt: string;
  savedAt: number;
  status: JobStatusPayload;
  result: JobResultPayload;
};

export type AdminReplayStage = {
  id: string;
  label: string;
  state: string;
  durationMs: number;
};

const STORAGE_KEY = "lawkey-admin-replay-v1";

// 5 stages × 2 s ≈ 10 s of dramatic loading time, mirroring the real
// pipeline order (key → select → analyze → synth → done).
export const ADMIN_REPLAY_STAGES: AdminReplayStage[] = [
  { id: "keywords", label: "키워드 생성", state: "generating_keywords", durationMs: 2000 },
  { id: "selection", label: "근거 선별", state: "building_chunk_plan", durationMs: 2000 },
  { id: "analyze", label: "문서별 관련성 분석", state: "analyzing_chunks", durationMs: 2000 },
  { id: "synthesize", label: "근거 기반 답변 합성", state: "writing_final_draft", durationMs: 2000 },
  { id: "done", label: "완료", state: "completed", durationMs: 200 },
];

function loadAll(): Record<string, AdminReplaySnapshot> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage?.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return {};
    const out: Record<string, AdminReplaySnapshot> = {};
    for (const [key, value] of Object.entries(parsed)) {
      if (value && typeof value === "object" && (value as AdminReplaySnapshot).jobId) {
        out[String(key)] = value as AdminReplaySnapshot;
      }
    }
    return out;
  } catch {
    return {};
  }
}

function saveAll(map: Record<string, AdminReplaySnapshot>): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage?.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch {
    /* ignore quota */
  }
}

export function saveAdminReplaySnapshot(snapshot: Omit<AdminReplaySnapshot, "version" | "savedAt"> & {
  savedAt?: number;
}): void {
  if (!snapshot.jobId.trim()) return;
  const map = loadAll();
  map[snapshot.jobId] = {
    ...snapshot,
    version: 1,
    savedAt: snapshot.savedAt ?? Date.now(),
  };
  saveAll(map);
}

export function loadAdminReplaySnapshot(jobId: string): AdminReplaySnapshot | null {
  const id = String(jobId || "").trim();
  if (!id) return null;
  return loadAll()[id] ?? null;
}

export function deleteAdminReplaySnapshot(jobId: string): void {
  const id = String(jobId || "").trim();
  if (!id) return;
  const map = loadAll();
  if (id in map) {
    delete map[id];
    saveAll(map);
  }
}

export function editAdminReplayAnswer(jobId: string, nextMarkdown: string): AdminReplaySnapshot | null {
  const snapshot = loadAdminReplaySnapshot(jobId);
  if (!snapshot) return null;
  const updated: AdminReplaySnapshot = {
    ...snapshot,
    savedAt: Date.now(),
    result: {
      ...snapshot.result,
      answerMarkdown: String(nextMarkdown || "").trim(),
    },
  };
  const map = loadAll();
  map[jobId] = updated;
  saveAll(map);
  return updated;
}

// Drive a synthetic status timeline through the predefined stages. Caller
// supplies onUpdate (typically setStatus) and onComplete (set the final
// result). Returns a cancel function.
export function runAdminReplay({
  snapshot,
  onUpdate,
  onComplete,
  jobId,
}: {
  snapshot: AdminReplaySnapshot;
  onUpdate: (status: JobStatusPayload) => void;
  onComplete: (result: JobResultPayload, finalStatus: JobStatusPayload) => void;
  jobId: string;
}): () => void {
  let cancelled = false;
  let timer: ReturnType<typeof setTimeout> | null = null;
  const startedAt = Date.now();
  const baseStatus: JobStatusPayload = {
    ...snapshot.status,
    jobId,
    state: "queued",
    phase: "replay",
    completedChunks: 0,
    totalChunks: snapshot.status.totalChunks || 0,
    elapsedSeconds: 0,
    etaSeconds: 0,
  };
  onUpdate(baseStatus);

  const stepInto = (index: number) => {
    if (cancelled) return;
    if (index >= ADMIN_REPLAY_STAGES.length) {
      onComplete(snapshot.result, {
        ...baseStatus,
        state: "completed",
        elapsedSeconds: Math.max(1, Math.round((Date.now() - startedAt) / 1000)),
        finishedAt: Date.now() / 1000,
      });
      return;
    }
    const stage = ADMIN_REPLAY_STAGES[index];
    const nextStatus: JobStatusPayload = {
      ...baseStatus,
      state: stage.state,
      phase: stage.id,
      completedChunks:
        stage.state === "analyzing_chunks"
          ? Math.max(1, Math.min(snapshot.status.totalChunks || 1, snapshot.status.completedChunks || 1))
          : baseStatus.completedChunks,
      elapsedSeconds: Math.max(0, Math.round((Date.now() - startedAt) / 1000)),
      etaSeconds: Math.max(
        0,
        Math.round(
          ADMIN_REPLAY_STAGES.slice(index + 1).reduce((sum, item) => sum + item.durationMs, 0) / 1000,
        ),
      ),
    };
    onUpdate(nextStatus);
    timer = setTimeout(() => stepInto(index + 1), stage.durationMs);
  };

  // Begin with a tiny delay so the initial "queued" frame is visible.
  timer = setTimeout(() => stepInto(0), 200);

  return () => {
    cancelled = true;
    if (timer) clearTimeout(timer);
  };
}
