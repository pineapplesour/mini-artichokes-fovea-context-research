export type EstimateRemainingSecondsInput = {
  completed: number;
  total: number;
  elapsedSeconds: number;
};

export type EstimateChunkWaveSecondsInput = EstimateRemainingSecondsInput & {
  workerCount?: number;
  tailSeconds?: number;
};

export type EstimateActiveApiSecondsInput = {
  lastApiActivityAt?: string;
  lastApiEvent?: string;
  inflight?: number;
  timeoutSeconds?: number;
  nowMs?: number;
};

export type ProgressEstimateInput = {
  state: string;
  completed: number;
  total: number;
};

export type EstimateOverallJobRemainingSecondsInput = {
  state: string;
  elapsedSeconds: number;
  progressPercent: number;
  fallbackSeconds: number;
};

export type NextDisplayedEtaSecondsInput = {
  current: number;
  target: number;
  state: string;
  hasShownPositive: boolean;
  allowRestartFromZero?: boolean;
};

export type ProgressEtaLabelInput = {
  displayEta: number;
  state: string;
  elapsedSeconds: number;
  isCeiling?: boolean;
};

export type DisplayedElapsedSecondsInput = {
  elapsedSeconds: number;
  localStartedAtMs: number;
  nowMs: number;
  running: boolean;
};

const TERMINAL_STATES = new Set(["completed", "failed", "cancelled", "interrupted"]);
const STARTUP_STATES = new Set(["queued", "waiting_for_capacity", "generating_keywords", "building_chunk_plan", "packing_chunks", "chunking_records"]);

export const estimateRemainingSeconds = ({
  completed,
  total,
  elapsedSeconds,
}: EstimateRemainingSecondsInput) => {
  if (completed <= 0 || total <= completed || elapsedSeconds <= 0) {
    return 0;
  }

  const itemsPerSecond = completed / elapsedSeconds;
  if (!Number.isFinite(itemsPerSecond) || itemsPerSecond <= 0) {
    return 0;
  }

  return Math.round((total - completed) / itemsPerSecond);
};

export const estimateChunkWaveSeconds = ({
  completed,
  total,
  elapsedSeconds,
  workerCount = 10,
  tailSeconds = 24,
}: EstimateChunkWaveSecondsInput) => {
  if (total <= 0 || total <= completed) {
    return tailSeconds;
  }
  const parallelism = Math.max(1, Math.min(Math.round(workerCount || 10), total));
  const remaining = Math.max(0, total - completed);
  const remainingWaves = Math.max(1, Math.ceil(remaining / parallelism));
  let waveSeconds = 18;
  const completedWaves = completed / parallelism;
  if (completedWaves >= 1 && elapsedSeconds > 0) {
    const observedWaveSeconds = elapsedSeconds / completedWaves;
    waveSeconds = Math.max(10, Math.min(35, observedWaveSeconds));
  }
  return Math.round(remainingWaves * waveSeconds + tailSeconds);
};

export const estimateActiveApiSeconds = ({
  lastApiActivityAt,
  lastApiEvent,
  inflight = 0,
  timeoutSeconds = 600,
  nowMs = Date.now(),
}: EstimateActiveApiSecondsInput) => {
  if (lastApiEvent !== "start" || inflight <= 0 || !lastApiActivityAt) {
    return 0;
  }
  const startedMs = Date.parse(lastApiActivityAt);
  if (!Number.isFinite(startedMs)) {
    return 0;
  }
  const elapsedSeconds = Math.max(0, (nowMs - startedMs) / 1000);
  return Math.max(0, Math.round(timeoutSeconds - elapsedSeconds));
};

export const formatEtaLabel = (seconds: number) => {
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return "0s";
  }

  const wholeSeconds = Math.round(seconds);
  const minutes = Math.floor(wholeSeconds / 60);
  const remainingSeconds = wholeSeconds % 60;

  if (minutes <= 0) {
    return `${remainingSeconds}s`;
  }

  return `${minutes}m ${remainingSeconds}s`;
};

export const formatTotalElapsedLabel = (seconds: number) => {
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return "";
  }
  const wholeSeconds = Math.max(1, Math.round(seconds));
  const minutes = Math.floor(wholeSeconds / 60);
  const remainingSeconds = wholeSeconds % 60;
  if (minutes <= 0) {
    return `총 ${remainingSeconds}초 소요`;
  }
  return remainingSeconds > 0 ? `총 ${minutes}분 ${remainingSeconds}초 소요` : `총 ${minutes}분 소요`;
};

export const buildProgressEtaLabel = ({
  displayEta,
  state,
  elapsedSeconds,
  isCeiling = false,
}: ProgressEtaLabelInput) => {
  const eta = Math.max(0, Math.round(displayEta || 0));
  if (eta > 0) {
    return `${isCeiling ? "최대 " : ""}${formatEtaLabel(eta)} 남음`;
  }
  if (state === "completed") {
    return "완료";
  }
  if (TERMINAL_STATES.has(state)) {
    return "중단됨";
  }
  const elapsed = Math.max(0, Math.round(elapsedSeconds || 0));
  if (elapsed > 0) {
    return `경과 ${formatEtaLabel(elapsed)}`;
  }
  if (state === "queued" || state === "waiting_for_capacity") {
    return "준비 중";
  }
  return "진행 중";
};

export const resolveDisplayedElapsedSeconds = ({
  elapsedSeconds,
  localStartedAtMs,
  nowMs,
  running,
}: DisplayedElapsedSecondsInput) => {
  const serverElapsed = Math.max(0, Math.round(elapsedSeconds || 0));
  if (serverElapsed > 0 || !running) {
    return serverElapsed;
  }
  const startedAt = Number(localStartedAtMs || 0);
  const now = Number(nowMs || 0);
  if (!Number.isFinite(startedAt) || !Number.isFinite(now) || now <= startedAt) {
    return 0;
  }
  return Math.max(0, Math.floor((now - startedAt) / 1000));
};

export const estimateProgressPercent = ({ state, completed, total }: ProgressEstimateInput) => {
  if (state === "completed") {
    return 100;
  }
  if (state === "failed" || state === "cancelled" || state === "interrupted") {
    return 0;
  }
  if (state === "queued" || state === "waiting_for_capacity" || state === "generating_keywords") {
    return 6;
  }
  if (state === "building_chunk_plan" || state === "packing_chunks" || state === "chunking_records") {
    return 14;
  }
  if (state === "analyzing_chunks") {
    if (total <= 0) {
      return 18;
    }
    const ratio = Math.min(1, Math.max(0, completed / total));
    return Math.max(18, Math.min(86, Math.round(18 + ratio * 68)));
  }
  if (state === "summarizing_precedents") {
    return 87;
  }
  if (state === "writing_final_draft" || state === "writing_document") {
    return total > 0 && completed >= total ? 90 : 89;
  }
  if (state === "applying_coverage_patch") {
    return total > 0 && completed >= total ? 96 : 94;
  }
  if (state === "exporting_artifacts") {
    return 99;
  }
  return 8;
};

export const estimateOverallJobRemainingSeconds = ({
  state,
  elapsedSeconds,
  progressPercent,
  fallbackSeconds,
}: EstimateOverallJobRemainingSecondsInput) => {
  if (state === "completed") {
    return 0;
  }
  const fallback = Math.max(0, Math.round(fallbackSeconds || 0));
  if (TERMINAL_STATES.has(state)) {
    return 0;
  }
  if (STARTUP_STATES.has(state)) {
    return fallback;
  }
  if (elapsedSeconds <= 0 || progressPercent <= 0) {
    return fallback;
  }
  const progress = Math.max(5, Math.min(99, progressPercent));
  const remainingByWholeJob = Math.ceil(elapsedSeconds * ((100 - progress) / progress) * 1.25);
  return Math.max(fallback, remainingByWholeJob);
};

export const nextDisplayedEtaSeconds = ({
  current,
  target,
  state,
  hasShownPositive,
  allowRestartFromZero = false,
}: NextDisplayedEtaSecondsInput) => {
  if (state === "completed" || TERMINAL_STATES.has(state)) {
    return 0;
  }
  const currentSeconds = Math.max(0, Math.round(current || 0));
  const targetSeconds = Math.max(0, Math.round(target || 0));
  if (hasShownPositive && currentSeconds <= 0 && !allowRestartFromZero) {
    return 0;
  }
  if (currentSeconds <= 0) {
    return targetSeconds;
  }
  if (targetSeconds <= 0) {
    return currentSeconds;
  }
  return Math.min(currentSeconds, targetSeconds);
};

export const estimateEtaFallback = (state: string, currentEtaSeconds: number) => {
  if (Number.isFinite(currentEtaSeconds) && currentEtaSeconds > 0) {
    return Math.round(currentEtaSeconds);
  }
  if (state === "queued" || state === "waiting_for_capacity") {
    return 8;
  }
  if (state === "generating_keywords") {
    return 14;
  }
  if (state === "building_chunk_plan" || state === "packing_chunks" || state === "chunking_records") {
    return 20;
  }
  if (state === "analyzing_chunks") {
    return 45;
  }
  if (state === "summarizing_precedents") {
    return 60;
  }
  if (state === "writing_final_draft" || state === "writing_document") {
    return 18;
  }
  if (state === "applying_coverage_patch") {
    return 3;
  }
  if (state === "exporting_artifacts") {
    return 5;
  }
  return 0;
};
