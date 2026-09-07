import { useEffect, useMemo, useState } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { Link, useLocalSearchParams } from "expo-router";

import { theme } from "../../constants/theme";
import { MarkdownView } from "../../components/lawkey/markdown-view";
import {
  fetchJudgeCases,
  fetchJudgeProfile,
  fetchPrecedentText,
  getStoredJudgesPassword,
  predictWithJudge,
  storeJudgesPassword,
  submitJudgeReview,
  summarizeJudge,
  type JudgeCase,
  type JudgePrecedentText,
  type JudgeProfilePayload,
  type JudgePredictPayload,
  type JudgeSummaryRecord,
} from "../../lib/judges-api";

const CLIENT_ID_KEY = "lawkey-client-id-v1";

function normalizePrecedentText(raw: string): string {
  return String(raw || "")
    .replace(/\r\n/g, "\n")
    .replace(/<br\s*\/?>/gi, "\n\n")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function getOrCreateClientId(): string {
  if (typeof window === "undefined") return "anon";
  try {
    const existing = window.localStorage.getItem(CLIENT_ID_KEY);
    if (existing) return existing;
    const fresh = `lawkey-${crypto.randomUUID()}`;
    window.localStorage.setItem(CLIENT_ID_KEY, fresh);
    return fresh;
  } catch {
    return "anon";
  }
}

export default function JudgeProfile() {
  const params = useLocalSearchParams<{ id: string }>();
  const judgeId = String(params.id || "");
  const [password, setPassword] = useState(() => getStoredJudgesPassword());
  const [needPassword, setNeedPassword] = useState(!password);
  const [profile, setProfile] = useState<JudgeProfilePayload | null>(null);
  const [cases, setCases] = useState<JudgeCase[]>([]);
  const [casesTotal, setCasesTotal] = useState(0);
  const [casesLoading, setCasesLoading] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [predictQuestion, setPredictQuestion] = useState("");
  const [predicting, setPredicting] = useState(false);
  const [prediction, setPrediction] = useState<JudgePredictPayload | null>(null);
  const [summarizing, setSummarizing] = useState(false);
  const [summary, setSummary] = useState<JudgeSummaryRecord | null>(null);
  const [reviewBody, setReviewBody] = useState("");
  const [reviewRating, setReviewRating] = useState(5);
  const [reviewBusy, setReviewBusy] = useState(false);
  const [precedentLoading, setPrecedentLoading] = useState(false);
  const [precedentOpen, setPrecedentOpen] = useState(false);
  const [precedent, setPrecedent] = useState<JudgePrecedentText | null>(null);
  const [width, setWidth] = useState(() => (typeof window !== "undefined" ? window.innerWidth : 1024));
  const compact = width < 720;
  const clientId = useMemo(getOrCreateClientId, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const onResize = () => setWidth(window.innerWidth);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchJudgeProfile(password, judgeId);
      setProfile(data);
      setCases(data.casesPage.cases);
      setCasesTotal(data.casesPage.total);
      setSummary(data.summary);
      setNeedPassword(false);
    } catch (caught) {
      if (caught instanceof Error && caught.message === "UNAUTHORIZED") {
        setNeedPassword(true);
        setError("비밀번호를 입력해 주세요.");
      } else {
        setError(caught instanceof Error ? caught.message : "프로필을 불러올 수 없습니다.");
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!judgeId || !password) return;
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [judgeId, password]);

  const loadMoreCases = async () => {
    if (casesLoading || cases.length >= casesTotal) return;
    setCasesLoading(true);
    try {
      const page = await fetchJudgeCases(password, judgeId, cases.length, 20);
      setCases((prev) => [...prev, ...page.cases]);
      setCasesTotal(page.total);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "판례 추가 로드 실패");
    } finally {
      setCasesLoading(false);
    }
  };

  const runSummarize = async () => {
    setSummarizing(true);
    setError("");
    try {
      const { summary: s } = await summarizeJudge(password, judgeId, clientId);
      setSummary(s);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "요약 생성 실패");
    } finally {
      setSummarizing(false);
    }
  };

  const submitPrediction = async () => {
    if (!predictQuestion.trim()) return;
    setPredicting(true);
    setPrediction(null);
    try {
      const result = await predictWithJudge(password, judgeId, predictQuestion.trim(), clientId);
      setPrediction(result);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "추정 실패");
    } finally {
      setPredicting(false);
    }
  };

  const submitReview = async () => {
    if (reviewBody.trim().length < 5) {
      setError("리뷰는 5자 이상 작성해 주세요.");
      return;
    }
    setReviewBusy(true);
    setError("");
    try {
      const updated = await submitJudgeReview(password, judgeId, reviewRating, reviewBody.trim(), clientId);
      setProfile((prev) => (prev ? { ...prev, reviews: updated } : prev));
      setReviewBody("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "리뷰 등록 실패");
    } finally {
      setReviewBusy(false);
    }
  };

  const openPrecedent = async (canonicalId: string) => {
    setPrecedentLoading(true);
    setPrecedentOpen(true);
    setPrecedent(null);
    try {
      const data = await fetchPrecedentText(password, canonicalId);
      setPrecedent(data);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "판례 본문 로드 실패");
    } finally {
      setPrecedentLoading(false);
    }
  };

  if (needPassword) {
    return (
      <View style={styles.gateOuter}>
        <View style={[styles.gateCard, compact ? styles.gateCardCompact : null]}>
          <Text style={styles.gateBrand}>판사어때</Text>
          <Text style={styles.gateSubtitle}>계속하려면 비밀번호를 입력해 주세요.</Text>
          <View style={styles.gateDivider} />
          <TextInput
            value={password}
            onChangeText={setPassword}
            placeholder="비밀번호"
            secureTextEntry
            style={styles.gateInput}
            onSubmitEditing={() => {
              storeJudgesPassword(password);
              void load();
            }}
          />
          <Pressable
            style={({ pressed }) => [styles.gateButton, pressed ? styles.pressed : null]}
            onPress={() => {
              storeJudgesPassword(password);
              void load();
            }}
          >
            <Text style={styles.gateButtonText}>입장</Text>
          </Pressable>
          {error ? <Text style={styles.gateError}>{error}</Text> : null}
          <Link href="/judges" style={styles.gateBack}>
            ← 판사어때 검색으로
          </Link>
        </View>
      </View>
    );
  }

  if (loading || !profile) {
    return (
      <View style={styles.appOuter}>
        <View style={[styles.topBar, compact ? styles.topBarCompact : null]}>
          <Link href="/judges" style={styles.topBarBack}>← 판사어때</Link>
        </View>
        <View style={styles.loadingBox}>
          <Text style={styles.loadingText}>{loading ? "불러오는 중..." : error || "데이터가 없습니다."}</Text>
        </View>
      </View>
    );
  }

  const { judge, career, reviews } = profile;
  const courts = judge.courts || [];
  const careerYears = judge.firstSeen && judge.lastSeen ? `${judge.firstSeen}~${judge.lastSeen}` : "-";

  return (
    <View style={styles.appOuter}>
      <View style={[styles.topBar, compact ? styles.topBarCompact : null]}>
        <Link href="/judges" style={styles.topBarBack}>← 판사어때</Link>
        <Link href="/" style={styles.topBarHome}>Lawkey 분석</Link>
      </View>

      <ScrollView style={styles.scroller} contentContainerStyle={[styles.scrollerContent, compact ? styles.scrollerContentCompact : null]}>
        {/* HERO */}
        <View style={[styles.hero, compact ? styles.heroCompact : null]}>
          <View style={styles.heroAvatar}>
            <Text style={styles.heroAvatarText}>{judge.name?.[0] || "?"}</Text>
          </View>
          <View style={styles.heroBody}>
            <View style={styles.heroNameLine}>
              <Text style={styles.heroName}>{judge.name}</Text>
              {judge.hanja ? <Text style={styles.heroHanja}>{judge.hanja}</Text> : null}
            </View>
            <Text style={styles.heroMeta}>{careerYears} · 활동 기간</Text>
          </View>
        </View>

        {/* STATS */}
        <View style={[styles.statsRow, compact ? styles.statsRowCompact : null]}>
          <View style={styles.statCard}>
            <Text style={styles.statValue}>{judge.appearanceCount.toLocaleString()}</Text>
            <Text style={styles.statLabel}>판례</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statValue}>{courts.length}</Text>
            <Text style={styles.statLabel}>법원</Text>
          </View>
          <View style={styles.statCard}>
            <Text style={styles.statValue}>{reviews.reviewCount}</Text>
            <Text style={styles.statLabel}>리뷰</Text>
          </View>
        </View>

        {/* COURTS */}
        <View style={styles.courtsRow}>
          {courts.slice(0, 8).map((court) => (
            <Text key={court} style={styles.courtChip}>
              {court}
            </Text>
          ))}
          {courts.length > 8 ? <Text style={styles.courtChipMore}>외 {courts.length - 8}곳</Text> : null}
        </View>

        {/* SUMMARY CARD */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>성향 요약</Text>
            {!summary ? (
              <Pressable
                onPress={runSummarize}
                disabled={summarizing}
                style={({ pressed }) => [styles.sectionAction, pressed ? styles.pressed : null]}
              >
                <Text style={styles.sectionActionText}>{summarizing ? "생성 중..." : "간단 분석"}</Text>
              </Pressable>
            ) : null}
          </View>
          {summary ? (
            <View>
              <Text style={styles.summaryBody}>{summary.summary}</Text>
              <Text style={styles.summaryFooter}>
                표본 {summary.samplesUsed}건 · 전체 {summary.totalCases}건 · 최초 생성 시점에 귀속 (이후 동일 결과 재사용)
              </Text>
            </View>
          ) : (
            <Text style={styles.emptyText}>
              아직 이 판사의 성향 요약이 없습니다. [간단 분석]을 누르면 한 번만 생성되고, 이후 모든 사용자에게 동일 요약이 표시됩니다.
            </Text>
          )}
        </View>

        {/* PREDICT */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>이 판사라면 어떻게 판결할까?</Text>
          <Text style={styles.helpText}>
            이 판사가 다룬 판례 표본만으로 추정합니다. 표본과 거리가 먼 쟁점은 신뢰도가 낮습니다.
          </Text>
          <TextInput
            value={predictQuestion}
            onChangeText={setPredictQuestion}
            placeholder="예: 카카오톡 단체방 모욕 사건에서 양형은 어떻게 정할까요?"
            multiline
            style={styles.textArea}
          />
          <Pressable
            style={({ pressed }) => [styles.primaryButton, pressed ? styles.pressed : null]}
            onPress={submitPrediction}
            disabled={predicting}
          >
            <Text style={styles.primaryButtonText}>{predicting ? "추정 중..." : "추정 결과 보기"}</Text>
          </Pressable>
          {prediction ? (
            <View style={styles.predictionBox}>
              <Text style={styles.predictionMeta}>
                표본 {prediction.samplesUsed}건 · 전체 {prediction.totalCases ?? "-"}건
              </Text>
              <MarkdownView markdown={prediction.answerMarkdown} mode="plain" hideHeader />
            </View>
          ) : null}
        </View>

        {/* CAREER */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>경력 타임라인</Text>
          <View style={styles.careerList}>
            {career.length === 0 ? <Text style={styles.emptyText}>경력 데이터가 없습니다.</Text> : null}
            {career.map((entry, idx) => (
              <View key={`${entry.court}-${entry.year}-${idx}`} style={styles.careerRow}>
                <Text style={styles.careerYear}>{entry.year || "-"}</Text>
                <View style={{ flex: 1 }}>
                  <Text style={styles.careerCourt}>{entry.court}</Text>
                  <Text style={styles.careerSub}>{entry.role} · {entry.count}건</Text>
                </View>
              </View>
            ))}
          </View>
        </View>

        {/* CASES */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>처리 판례</Text>
            <Text style={styles.sectionHeaderMeta}>
              {cases.length} / {casesTotal.toLocaleString()}건
            </Text>
          </View>
          <View style={styles.casesList}>
            {cases.length === 0 ? <Text style={styles.emptyText}>판례가 없습니다.</Text> : null}
            {cases.map((c, idx) => (
              <Pressable
                key={`${c.canonicalId}-${idx}`}
                style={({ pressed }) => [styles.caseRow, pressed ? styles.caseRowPressed : null]}
                onPress={() => openPrecedent(c.canonicalId)}
              >
                <View style={{ flex: 1 }}>
                  <Text style={styles.caseNumber}>{c.caseNumber || "(번호 미상)"}</Text>
                  <Text style={styles.caseMeta}>{c.court} · {c.decisionDate || "-"} · {c.role}</Text>
                </View>
                <Text style={styles.caseChevron}>›</Text>
              </Pressable>
            ))}
          </View>
          {cases.length < casesTotal ? (
            <Pressable
              onPress={loadMoreCases}
              disabled={casesLoading}
              style={({ pressed }) => [styles.secondaryButton, pressed ? styles.pressed : null]}
            >
              <Text style={styles.secondaryButtonText}>
                {casesLoading ? "불러오는 중..." : `더 보기 (+${Math.min(20, casesTotal - cases.length)})`}
              </Text>
            </Pressable>
          ) : null}
        </View>

        {/* REVIEWS */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>익명 리뷰</Text>
            <Text style={styles.sectionHeaderMeta}>
              ★ {reviews.averageRating.toFixed(1)} · {reviews.reviewCount}건
            </Text>
          </View>
          <Text style={styles.helpText}>
            주관적·익명 의견. 한 브라우저당 1건만 등록·갱신. 명예훼손·허위 사실 금지.
          </Text>
          <View style={styles.ratingRow}>
            {[1, 2, 3, 4, 5].map((n) => (
              <Pressable key={n} onPress={() => setReviewRating(n)}>
                <Text style={[styles.star, n <= reviewRating ? styles.starOn : styles.starOff]}>★</Text>
              </Pressable>
            ))}
          </View>
          <TextInput
            value={reviewBody}
            onChangeText={setReviewBody}
            placeholder="리뷰 본문 (5~2000자)"
            multiline
            style={styles.textArea}
          />
          <Pressable
            style={({ pressed }) => [styles.primaryButton, pressed ? styles.pressed : null]}
            onPress={submitReview}
            disabled={reviewBusy}
          >
            <Text style={styles.primaryButtonText}>{reviewBusy ? "등록 중..." : "리뷰 등록"}</Text>
          </Pressable>
          <View style={styles.reviewList}>
            {reviews.reviews.map((rv) => (
              <View key={rv.reviewId} style={styles.reviewRow}>
                <Text style={styles.reviewRating}>{"★".repeat(rv.rating)}{"☆".repeat(5 - rv.rating)}</Text>
                <Text style={styles.reviewBody}>{rv.body}</Text>
              </View>
            ))}
          </View>
        </View>

        {error ? <Text style={styles.inlineError}>{error}</Text> : null}
      </ScrollView>

      {/* PRECEDENT MODAL */}
      <Modal visible={precedentOpen} animationType="slide" onRequestClose={() => setPrecedentOpen(false)}>
        <View style={styles.modalContainer}>
          <View style={[styles.modalTopBar, compact ? styles.topBarCompact : null]}>
            <Pressable onPress={() => setPrecedentOpen(false)}>
              <Text style={styles.topBarBack}>← 닫기</Text>
            </Pressable>
          </View>
          <ScrollView contentContainerStyle={[styles.modalContent, compact ? styles.modalContentCompact : null]}>
            {precedentLoading ? (
              <Text style={styles.emptyText}>판례 본문을 불러오는 중...</Text>
            ) : precedent ? (
              <>
                <Text style={styles.modalCaseNumber}>{precedent.caseNumber || "(번호 미상)"}</Text>
                <Text style={styles.modalCaseMeta}>
                  {precedent.court} · {precedent.decisionDate || "-"}
                  {precedent.caseName ? ` · ${precedent.caseName}` : ""}
                </Text>
                <View style={styles.modalDivider} />
                <MarkdownView markdown={normalizePrecedentText(precedent.fullText)} mode="plain" hideHeader />
              </>
            ) : (
              <Text style={styles.emptyText}>데이터 없음</Text>
            )}
          </ScrollView>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  // Gate
  gateOuter: { flex: 1, backgroundColor: "#fafafa", justifyContent: "center", alignItems: "center", padding: 20 },
  gateCard: {
    width: "100%",
    maxWidth: 420,
    padding: 32,
    borderRadius: 16,
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#ececec",
    gap: 10,
    shadowColor: "#000000",
    shadowOpacity: 0.04,
    shadowRadius: 20,
    shadowOffset: { width: 0, height: 6 },
  },
  gateCardCompact: { padding: 22 },
  gateBrand: { fontFamily: theme.fonts.serif, fontSize: 28, fontWeight: "700", color: theme.colors.text, letterSpacing: -0.3 },
  gateSubtitle: { fontFamily: theme.fonts.serif, fontSize: 13, color: "#666666" },
  gateDivider: { height: 1, backgroundColor: "#eeeeee", marginVertical: 10 },
  gateInput: { borderWidth: 1, borderColor: "#dcdcdc", borderRadius: 10, paddingHorizontal: 14, paddingVertical: 12, fontFamily: theme.fonts.serif, fontSize: 15, backgroundColor: "#fafafa" },
  gateButton: { backgroundColor: "#101010", paddingVertical: 13, borderRadius: 10, alignItems: "center", marginTop: 4 },
  gateButtonText: { color: "#ffffff", fontFamily: theme.fonts.serif, fontSize: 14, fontWeight: "700", letterSpacing: 0.3 },
  gateError: { color: "#b53737", fontFamily: theme.fonts.serif, fontSize: 13, marginTop: 4 },
  gateBack: { fontFamily: theme.fonts.serif, fontSize: 12, color: "#777777", textAlign: "center", marginTop: 14, textDecorationLine: "underline" },

  // App
  appOuter: { flex: 1, backgroundColor: "#fafafa" },
  topBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 32,
    paddingVertical: 18,
    backgroundColor: "#ffffff",
    borderBottomWidth: 1,
    borderBottomColor: "#ececec",
  },
  topBarCompact: { paddingHorizontal: 18, paddingVertical: 14 },
  topBarBack: { fontFamily: theme.fonts.serif, fontSize: 13, color: "#101010", textDecorationLine: "underline" },
  topBarHome: { fontFamily: theme.fonts.serif, fontSize: 13, color: "#555555", textDecorationLine: "underline" },

  loadingBox: { padding: 40, alignItems: "center" },
  loadingText: { fontFamily: theme.fonts.serif, fontSize: 14, color: "#666666" },

  scroller: { flex: 1 },
  scrollerContent: { paddingHorizontal: 32, paddingVertical: 28, gap: 18, maxWidth: 880, alignSelf: "center", width: "100%", paddingBottom: 80 },
  scrollerContentCompact: { paddingHorizontal: 16, paddingVertical: 18 },

  // Hero
  hero: {
    flexDirection: "row",
    alignItems: "center",
    gap: 18,
    padding: 22,
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#ececec",
    borderRadius: 16,
  },
  heroCompact: { padding: 18, gap: 14 },
  heroAvatar: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: "#101010",
    alignItems: "center",
    justifyContent: "center",
  },
  heroAvatarText: { color: "#ffffff", fontFamily: theme.fonts.serif, fontSize: 30, fontWeight: "700" },
  heroBody: { flex: 1 },
  heroNameLine: { flexDirection: "row", alignItems: "baseline", gap: 8 },
  heroName: { fontFamily: theme.fonts.serif, fontSize: 30, fontWeight: "700", color: theme.colors.text, letterSpacing: -0.3 },
  heroHanja: { fontFamily: theme.fonts.serif, fontSize: 18, color: "#888888" },
  heroMeta: { fontFamily: theme.fonts.serif, fontSize: 13, color: "#666666", marginTop: 3 },

  // Stats
  statsRow: { flexDirection: "row", gap: 10 },
  statsRowCompact: { gap: 8 },
  statCard: {
    flex: 1,
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#ececec",
    borderRadius: 12,
    paddingVertical: 16,
    paddingHorizontal: 14,
    alignItems: "center",
  },
  statValue: { fontFamily: theme.fonts.serif, fontSize: 26, fontWeight: "700", color: theme.colors.text, fontVariant: ["tabular-nums"] },
  statLabel: { fontFamily: theme.fonts.serif, fontSize: 12, color: "#888888", marginTop: 2 },

  // Courts
  courtsRow: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  courtChip: {
    fontFamily: theme.fonts.serif,
    fontSize: 12,
    color: "#555555",
    backgroundColor: "#f1f1f1",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
  },
  courtChipMore: { fontFamily: theme.fonts.serif, fontSize: 12, color: "#999999", alignSelf: "center", paddingHorizontal: 6 },

  // Section cards
  section: {
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#ececec",
    borderRadius: 16,
    padding: 22,
    gap: 10,
  },
  sectionHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  sectionTitle: { fontFamily: theme.fonts.serif, fontSize: 18, fontWeight: "700", color: theme.colors.text, letterSpacing: -0.2 },
  sectionHeaderMeta: { fontFamily: theme.fonts.serif, fontSize: 13, color: "#888888", fontVariant: ["tabular-nums"] },
  sectionAction: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: theme.colors.text,
  },
  sectionActionText: { fontFamily: theme.fonts.serif, fontSize: 12, fontWeight: "700", color: theme.colors.text },

  summaryBody: { fontFamily: theme.fonts.serif, fontSize: 14, lineHeight: 22, color: theme.colors.text },
  summaryFooter: { fontFamily: theme.fonts.serif, fontSize: 11, color: "#888888", marginTop: 8 },

  helpText: { fontFamily: theme.fonts.serif, fontSize: 12, color: "#777777", lineHeight: 18 },
  emptyText: { fontFamily: theme.fonts.serif, fontSize: 13, color: "#999999", padding: 8 },

  textArea: {
    borderWidth: 1,
    borderColor: "#dcdcdc",
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontFamily: theme.fonts.serif,
    fontSize: 14,
    backgroundColor: "#fafafa",
    minHeight: 80,
    textAlignVertical: "top",
  },
  primaryButton: { backgroundColor: "#101010", paddingVertical: 12, borderRadius: 10, alignItems: "center" },
  primaryButtonText: { color: "#ffffff", fontFamily: theme.fonts.serif, fontSize: 14, fontWeight: "700" },
  secondaryButton: { borderWidth: 1, borderColor: "#dcdcdc", paddingVertical: 11, borderRadius: 10, alignItems: "center", marginTop: 8, backgroundColor: "#ffffff" },
  secondaryButtonText: { color: theme.colors.text, fontFamily: theme.fonts.serif, fontSize: 13, fontWeight: "700" },
  predictionBox: { borderTopWidth: 1, borderTopColor: "#eeeeee", paddingTop: 12, marginTop: 8 },
  predictionMeta: { fontFamily: theme.fonts.serif, fontSize: 12, color: "#888888", marginBottom: 4 },

  careerList: { gap: 0 },
  careerRow: { flexDirection: "row", paddingVertical: 10, gap: 14, borderBottomWidth: 1, borderBottomColor: "#f5f5f5", alignItems: "center" },
  careerYear: { fontFamily: theme.fonts.serif, fontSize: 14, fontWeight: "700", width: 48, fontVariant: ["tabular-nums"], color: theme.colors.text },
  careerCourt: { fontFamily: theme.fonts.serif, fontSize: 14, color: theme.colors.text },
  careerSub: { fontFamily: theme.fonts.serif, fontSize: 12, color: "#888888", marginTop: 1 },

  casesList: { gap: 0 },
  caseRow: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: "#f5f5f5" },
  caseRowPressed: { backgroundColor: "#f9f9f9" },
  caseNumber: { fontFamily: theme.fonts.serif, fontSize: 14, fontWeight: "700", color: theme.colors.text },
  caseMeta: { fontFamily: theme.fonts.serif, fontSize: 12, color: "#666666", marginTop: 2 },
  caseChevron: { fontSize: 20, color: "#cccccc" },

  ratingRow: { flexDirection: "row", gap: 4, marginTop: 4 },
  star: { fontSize: 28, fontWeight: "700" },
  starOn: { color: "#101010" },
  starOff: { color: "#dcdcdc" },

  reviewList: { gap: 8, marginTop: 8 },
  reviewRow: { borderWidth: 1, borderColor: "#eeeeee", borderRadius: 10, padding: 12, gap: 4, backgroundColor: "#fafafa" },
  reviewRating: { fontFamily: theme.fonts.serif, fontSize: 13, color: "#101010" },
  reviewBody: { fontFamily: theme.fonts.serif, fontSize: 13, color: theme.colors.text, lineHeight: 19 },

  inlineError: { color: "#b53737", fontFamily: theme.fonts.serif, fontSize: 13 },

  // Modal
  modalContainer: { flex: 1, backgroundColor: "#ffffff" },
  modalTopBar: {
    flexDirection: "row",
    paddingHorizontal: 32,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: "#ececec",
    backgroundColor: "#ffffff",
  },
  modalContent: { padding: 32, gap: 8, paddingBottom: 80, maxWidth: 820, alignSelf: "center", width: "100%" },
  modalContentCompact: { padding: 18, paddingBottom: 60 },
  modalCaseNumber: { fontFamily: theme.fonts.serif, fontSize: 22, fontWeight: "700", color: theme.colors.text },
  modalCaseMeta: { fontFamily: theme.fonts.serif, fontSize: 13, color: "#666666", marginTop: 2 },
  modalDivider: { height: 1, backgroundColor: "#ececec", marginVertical: 14 },

  pressed: { opacity: 0.7 },
});
