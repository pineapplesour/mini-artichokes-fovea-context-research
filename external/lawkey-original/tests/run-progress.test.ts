import { describe, expect, it } from "vitest";

import {
  estimateActiveApiSeconds,
  estimateChunkWaveSeconds,
  estimateEtaFallback,
  estimateOverallJobRemainingSeconds,
  estimateProgressPercent,
  buildProgressEtaLabel,
  estimateRemainingSeconds,
  formatEtaLabel,
  formatTotalElapsedLabel,
  nextDisplayedEtaSeconds,
  resolveDisplayedElapsedSeconds,
} from "../lib/run-progress";

describe("run progress helpers", () => {
  it("estimates remaining time from throughput", () => {
    expect(estimateRemainingSeconds({ completed: 12, total: 24, elapsedSeconds: 60 })).toBe(60);
  });

  it("formats ETA labels for long runs", () => {
    expect(formatEtaLabel(125)).toBe("2m 5s");
  });

  it("formats completed answer elapsed labels in Korean", () => {
    expect(formatTotalElapsedLabel(125)).toBe("총 2분 5초 소요");
    expect(formatTotalElapsedLabel(45)).toBe("총 45초 소요");
    expect(formatTotalElapsedLabel(0)).toBe("");
  });

  it("shows elapsed time instead of 마무리 중 while an active job has no visible ETA", () => {
    expect(
      buildProgressEtaLabel({
        displayEta: 0,
        state: "analyzing_chunks",
        elapsedSeconds: 220,
        isCeiling: false,
      }),
    ).toBe("경과 3m 40s");
  });

  it("uses a local elapsed clock while a pending request has no server status yet", () => {
    expect(
      resolveDisplayedElapsedSeconds({
        elapsedSeconds: 0,
        localStartedAtMs: 1000,
        nowMs: 12_400,
        running: true,
      }),
    ).toBe(11);
    expect(
      resolveDisplayedElapsedSeconds({
        elapsedSeconds: 8,
        localStartedAtMs: 1000,
        nowMs: 12_400,
        running: true,
      }),
    ).toBe(8);
  });

  it("keeps progress below 100 until the job is actually completed", () => {
    expect(estimateProgressPercent({ state: "analyzing_chunks", completed: 9, total: 9 })).toBe(86);
    expect(estimateProgressPercent({ state: "writing_final_draft", completed: 9, total: 9 })).toBe(90);
    expect(estimateProgressPercent({ state: "applying_coverage_patch", completed: 9, total: 9 })).toBe(96);
    expect(estimateProgressPercent({ state: "completed", completed: 9, total: 9 })).toBe(100);
  });

  it("supplies fallback eta values for the final writing phases", () => {
    expect(estimateEtaFallback("writing_final_draft", 0)).toBe(18);
    expect(estimateEtaFallback("applying_coverage_patch", 0)).toBe(3);
    expect(estimateEtaFallback("completed", 0)).toBe(0);
  });

  it("caps chunk ETA against whole-job elapsed spikes", () => {
    expect(estimateChunkWaveSeconds({ completed: 30, total: 44, elapsedSeconds: 1800, workerCount: 10 })).toBe(94);
  });

  it("estimates active API timeout ceiling from runtime timestamps", () => {
    expect(
      estimateActiveApiSeconds({
        lastApiActivityAt: "2026-04-11T02:11:32Z",
        lastApiEvent: "start",
        inflight: 1,
        timeoutSeconds: 600,
        nowMs: Date.parse("2026-04-11T02:12:32Z"),
      }),
    ).toBe(540);
  });

  it("uses a conservative whole-job ETA floor for final stages", () => {
    expect(
      estimateOverallJobRemainingSeconds({
        state: "writing_final_draft",
        elapsedSeconds: 180,
        progressPercent: 90,
        fallbackSeconds: 18,
      }),
    ).toBe(25);
    expect(
      estimateOverallJobRemainingSeconds({
        state: "applying_coverage_patch",
        elapsedSeconds: 240,
        progressPercent: 96,
        fallbackSeconds: 3,
      }),
    ).toBe(13);
  });

  it("does not extrapolate early startup stages into huge whole-job ETAs", () => {
    expect(
      estimateOverallJobRemainingSeconds({
        state: "generating_keywords",
        elapsedSeconds: 1800,
        progressPercent: 6,
        fallbackSeconds: 14,
      }),
    ).toBe(14);
  });

  it("never increases the displayed ETA after it has started counting down", () => {
    expect(
      nextDisplayedEtaSeconds({
        current: 12,
        target: 40,
        state: "writing_final_draft",
        hasShownPositive: true,
      }),
    ).toBe(12);
    expect(
      nextDisplayedEtaSeconds({
        current: 0,
        target: 18,
        state: "exporting_artifacts",
        hasShownPositive: true,
        allowRestartFromZero: false,
      }),
    ).toBe(0);
    expect(
      nextDisplayedEtaSeconds({
        current: 0,
        target: 18,
        state: "analyzing_chunks",
        hasShownPositive: false,
      }),
    ).toBe(18);
    expect(
      nextDisplayedEtaSeconds({
        current: 0,
        target: 94,
        state: "analyzing_chunks",
        hasShownPositive: true,
        allowRestartFromZero: true,
      }),
    ).toBe(94);
    expect(
      nextDisplayedEtaSeconds({
        current: 30,
        target: 10,
        state: "applying_coverage_patch",
        hasShownPositive: true,
      }),
    ).toBe(10);
  });
});
