import { useEffect, useMemo, useRef, useState } from "react";
import { Animated, Easing, StyleSheet, Text, View } from "react-native";

import { theme } from "../../constants/theme";
import { resolveDisplayedElapsedSeconds } from "../../lib/run-progress";

type ProgressStripProps = {
  state: string;
  completedChunks: number;
  totalChunks: number;
  etaSeconds: number;
  elapsedSeconds: number;
  workerCount?: number;
  apiInflight?: number;
  lastApiActivityAt?: string;
  lastApiEvent?: string;
  constrained: boolean;
  headline?: string;
  selectionKeywords?: string[];
};

const TERMINAL_STATES = new Set(["completed", "failed", "cancelled", "interrupted"]);
const FAILED_STATES = new Set(["failed", "cancelled", "interrupted"]);

type StageId = "keywords" | "selection" | "analyze" | "synthesize" | "done";
type StageDef = { id: StageId; label: string; states: string[] };

const STAGES: StageDef[] = [
  { id: "keywords", label: "키워드 생성", states: ["queued", "waiting_for_capacity", "generating_keywords"] },
  { id: "selection", label: "근거 선별", states: ["building_chunk_plan", "packing_chunks", "chunking_records"] },
  { id: "analyze", label: "문서별 관련성 분석", states: ["analyzing_chunks", "summarizing_precedents"] },
  {
    id: "synthesize",
    label: "근거 기반 답변 합성",
    states: ["writing_final_draft", "writing_document", "applying_coverage_patch", "exporting_artifacts"],
  },
  { id: "done", label: "완료", states: ["completed"] },
];

function stageIndexForState(state: string): number {
  for (let i = 0; i < STAGES.length; i++) {
    if (STAGES[i].states.includes(state)) {
      return i;
    }
  }
  if (FAILED_STATES.has(state)) {
    return -1;
  }
  return 0;
}

type StageStatus = "pending" | "active" | "done" | "failed";

function statusForStage(stageIndex: number, currentIndex: number, state: string): StageStatus {
  if (FAILED_STATES.has(state)) {
    return stageIndex <= Math.max(0, currentIndex) ? "failed" : "pending";
  }
  if (state === "completed") {
    return "done";
  }
  if (stageIndex < currentIndex) {
    return "done";
  }
  if (stageIndex === currentIndex) {
    return "active";
  }
  return "pending";
}

function formatElapsedMillis(ms: number): string {
  const safe = Math.max(0, ms);
  return `${(safe / 1000).toFixed(3)}s`;
}

export function ProgressStrip({
  state,
  completedChunks,
  totalChunks,
  elapsedSeconds,
  constrained,
  headline,
  selectionKeywords,
}: ProgressStripProps) {
  const running = !TERMINAL_STATES.has(state);
  const currentStageIndex = stageIndexForState(state);

  const slide = useRef(new Animated.Value(0)).current;
  const localStartedAtMs = useRef(Date.now());
  // Anchor for the smooth ms-precise local clock. We re-anchor whenever the
  // server's coarse `elapsedSeconds` jumps ahead of what local thought (e.g.
  // after a refresh mid-run, server says 30s but local just mounted), so the
  // displayed elapsed always advances every animation frame instead of
  // freezing at `.000` between server polls.
  const elapsedAnchorMs = useRef<number | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    if (!running) {
      elapsedAnchorMs.current = null;
      return;
    }
    let rafId = 0;
    const tick = () => {
      setNowMs(Date.now());
      rafId = requestAnimationFrame(tick);
    };
    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, [running]);

  // Re-anchor when the server reports more elapsed time than our local clock
  // thinks (cold reload mid-run) so the next render starts at server's value
  // and ticks from there with sub-second precision.
  useEffect(() => {
    if (!running) return;
    const serverMs = Math.max(0, Math.round(elapsedSeconds || 0)) * 1000;
    const now = Date.now();
    if (elapsedAnchorMs.current == null) {
      elapsedAnchorMs.current = now - serverMs;
      return;
    }
    const localElapsed = now - elapsedAnchorMs.current;
    if (serverMs > localElapsed + 1500) {
      elapsedAnchorMs.current = now - serverMs;
    }
  }, [elapsedSeconds, running]);

  const serverElapsedMs =
    resolveDisplayedElapsedSeconds({
      elapsedSeconds,
      localStartedAtMs: localStartedAtMs.current,
      nowMs,
      running,
    }) * 1000;
  const anchoredElapsedMs = running && elapsedAnchorMs.current != null
    ? Math.max(0, nowMs - elapsedAnchorMs.current)
    : 0;
  // Use the anchored local clock as the SINGLE source of truth for display.
  // It re-anchors only when the server jumps further ahead, so the displayed
  // time always advances every animation frame instead of briefly freezing
  // at `s.000` whenever the server's integer-second poll temporarily wins
  // a `Math.max(serverMs, localMs, anchoredMs)` race.
  const displayedMs = running
    ? anchoredElapsedMs || Math.max(0, nowMs - localStartedAtMs.current)
    : serverElapsedMs;
  const elapsedLabel = formatElapsedMillis(displayedMs);

  const isCompleted = state === "completed";
  const isFailed = FAILED_STATES.has(state);
  // Weight each stage by rough time share so the bar advances from stage 0
  // (키워드 생성) onward, not only during chunk analysis. Sum == 100.
  const STAGE_WEIGHTS = [10, 15, 55, 19, 1];
  const useDeterminateBar = running || isCompleted;
  let accumulated = 0;
  for (let i = 0; i < Math.max(0, currentStageIndex); i++) {
    accumulated += STAGE_WEIGHTS[i] ?? 0;
  }
  let withinStage = 0;
  if (state === "analyzing_chunks" && totalChunks > 0) {
    withinStage = (STAGE_WEIGHTS[2] ?? 0) * (completedChunks / Math.max(1, totalChunks));
  } else if (currentStageIndex >= 0 && currentStageIndex < STAGE_WEIGHTS.length) {
    // For non-chunk stages, show a small baseline (~30% of the stage weight)
    // so the bar keeps moving visibly while the stage is active.
    withinStage = (STAGE_WEIGHTS[currentStageIndex] ?? 0) * 0.3;
  }
  const determinatePercent = isCompleted
    ? 100
    : isFailed
      ? Math.min(100, Math.max(2, Math.round(accumulated)))
      : Math.min(99, Math.max(2, Math.round(accumulated + withinStage)));

  useEffect(() => {
    if (!running || useDeterminateBar) {
      slide.stopAnimation();
      slide.setValue(0);
      return;
    }
    slide.setValue(0);
    const loop = Animated.loop(
      Animated.timing(slide, {
        toValue: 1,
        duration: constrained ? 1800 : 1300,
        easing: Easing.inOut(Easing.ease),
        useNativeDriver: true,
      }),
    );
    loop.start();
    return () => {
      loop.stop();
      slide.stopAnimation();
    };
  }, [constrained, running, slide, useDeterminateBar]);

  const translateX = slide.interpolate({ inputRange: [0, 1], outputRange: [-220, 760] });

  const headlineText = headline?.trim() || (STAGES[currentStageIndex] || STAGES[0]).label;

  return (
    <View style={[styles.card, constrained ? styles.cardConstrained : null]}>
      <View style={styles.headerRow}>
        <Text numberOfLines={1} ellipsizeMode="tail" style={styles.headline}>
          {headlineText}
        </Text>
        <Text style={styles.elapsed}>{elapsedLabel}</Text>
      </View>

      <View style={styles.barTrack}>
        {useDeterminateBar ? (
          <View style={[styles.barFill, { width: `${determinatePercent}%` }]} />
        ) : null}
        {running && !isCompleted ? (
          <Animated.View
            style={[
              styles.barGhost,
              useDeterminateBar ? styles.barGhostOverlay : styles.barGhostIndeterminate,
              { transform: [{ translateX }] },
            ]}
          />
        ) : null}
      </View>

      <View style={styles.stageList}>
        {STAGES.map((stage, index) => {
          const status = statusForStage(index, currentStageIndex, state);
          const showAnalyzeMeta = stage.id === "analyze" && (status === "active" || status === "done") && totalChunks > 0;
          // While the analyze stage is still active, the backend reports
          // `completedChunks` as the chunk currently being processed (1-based).
          // Showing "13/13" mid-flight makes users think it stalled at the end.
          // Subtract one so the user sees the previous chunk as done while the
          // current chunk is still in progress; on completion, show the full count.
          const analyzeDisplay = status === "active"
            ? Math.max(0, Math.min(completedChunks, totalChunks) - 1)
            : Math.min(completedChunks, totalChunks);
          return (
            <View key={stage.id} style={styles.stageRow}>
              <StageDot status={status} />
              <View style={styles.stageBody}>
                <Text
                  style={[
                    styles.stageLabel,
                    status === "active" ? styles.stageLabelActive : null,
                    status === "pending" ? styles.stageLabelPending : null,
                    status === "failed" ? styles.stageLabelFailed : null,
                  ]}
                >
                  {stage.label}
                  {showAnalyzeMeta ? (
                    <Text style={styles.stageMeta}>{`  · 청크 ${analyzeDisplay} / ${totalChunks}`}</Text>
                  ) : null}
                </Text>
              </View>
            </View>
          );
        })}
      </View>
    </View>
  );
}

function StageDot({ status }: { status: StageStatus }) {
  const pulse = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (status !== "active") {
      pulse.stopAnimation();
      pulse.setValue(0);
      return;
    }
    pulse.setValue(0);
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 700, easing: Easing.out(Easing.ease), useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0, duration: 700, easing: Easing.in(Easing.ease), useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => {
      loop.stop();
      pulse.stopAnimation();
    };
  }, [pulse, status]);
  const ringScale = pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.9] });
  const ringOpacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.35, 0] });
  return (
    <View style={styles.stageDotWrap}>
      {status === "active" ? (
        <Animated.View
          style={[styles.stageDotRing, { opacity: ringOpacity, transform: [{ scale: ringScale }] }]}
        />
      ) : null}
      <View
        style={[
          styles.stageDotBase,
          status === "done" ? styles.stageDotDone : null,
          status === "active" ? styles.stageDotActive : null,
          status === "failed" ? styles.stageDotFailed : null,
          status === "pending" ? styles.stageDotPending : null,
        ]}
      >
        {status === "done" ? <Text style={styles.stageDotCheck}>✓</Text> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderWidth: 1,
    borderColor: theme.colors.line,
    borderRadius: 8,
    padding: 20,
    backgroundColor: "#ffffff",
    gap: 14,
    shadowColor: "#000000",
    shadowOpacity: 0.02,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
  },
  cardConstrained: { shadowOpacity: 0 },
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 16,
  },
  headline: {
    flex: 1,
    color: "#111111",
    fontFamily: theme.fonts.serif,
    fontSize: 16,
    lineHeight: 24,
    fontWeight: "700",
  },
  elapsed: {
    color: theme.colors.text,
    fontFamily: theme.fonts.serif,
    fontSize: 15,
    fontWeight: "700",
    letterSpacing: 0.4,
    fontVariant: ["tabular-nums"],
  },
  barTrack: {
    height: 6,
    borderRadius: 999,
    backgroundColor: "#f1f1f1",
    overflow: "hidden",
    position: "relative",
  },
  barFill: {
    height: "100%",
    borderRadius: 999,
    backgroundColor: "#101010",
  },
  barGhost: {
    position: "absolute",
    top: 0,
    bottom: 0,
    width: 160,
    borderRadius: 999,
    backgroundColor: "#101010",
  },
  barGhostIndeterminate: { opacity: 0.22 },
  barGhostOverlay: { opacity: 0.14 },
  stageList: {
    gap: 10,
    paddingTop: 4,
  },
  stageRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 12,
  },
  stageDotWrap: {
    width: 14,
    height: 22,
    alignItems: "center",
    justifyContent: "center",
    position: "relative",
  },
  stageDotBase: {
    width: 10,
    height: 10,
    borderRadius: 5,
    alignItems: "center",
    justifyContent: "center",
  },
  stageDotPending: {
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#cccccc",
  },
  stageDotActive: {
    backgroundColor: "#101010",
  },
  stageDotDone: {
    backgroundColor: "#101010",
  },
  stageDotFailed: {
    backgroundColor: "#b53737",
  },
  stageDotRing: {
    position: "absolute",
    width: 14,
    height: 14,
    borderRadius: 7,
    backgroundColor: "#101010",
  },
  stageDotCheck: {
    color: "#ffffff",
    fontSize: 7,
    lineHeight: 10,
    fontWeight: "900",
    marginTop: 0,
  },
  stageBody: {
    flex: 1,
    gap: 6,
  },
  stageLabel: {
    fontFamily: theme.fonts.serif,
    fontSize: 14,
    lineHeight: 20,
    color: "#444444",
  },
  stageLabelActive: {
    color: "#101010",
    fontWeight: "700",
  },
  stageLabelPending: {
    color: "#999999",
  },
  stageLabelFailed: {
    color: "#b53737",
    fontWeight: "700",
  },
  stageMeta: {
    fontFamily: theme.fonts.serif,
    fontSize: 13,
    color: "#555555",
    fontVariant: ["tabular-nums"],
    fontWeight: "400",
  },
  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 6,
  },
  chip: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: theme.colors.line,
    backgroundColor: "#fafafa",
  },
  chipMuted: {
    backgroundColor: "#ffffff",
    borderColor: "#ececec",
  },
  chipText: {
    fontSize: 12,
    color: "#222222",
    fontFamily: theme.fonts.serif,
  },
  chipTextMuted: {
    color: "#888888",
  },
});
