import { useEffect, useMemo, useState } from "react";
import { Dimensions, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { Link, useRouter } from "expo-router";

import { theme } from "../constants/theme";
import {
  authJudges,
  getStoredJudgesPassword,
  searchJudges,
  storeJudgesPassword,
  type JudgeSummary,
} from "../lib/judges-api";

export default function JudgesIndex() {
  const router = useRouter();
  const [password, setPassword] = useState(() => getStoredJudgesPassword());
  const [authed, setAuthed] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<JudgeSummary[]>([]);
  const [width, setWidth] = useState(() => (typeof window !== "undefined" ? window.innerWidth : 1024));
  const compact = width < 720;

  useEffect(() => {
    if (typeof window === "undefined") return;
    const onResize = () => setWidth(window.innerWidth);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    if (!password) return;
    void (async () => {
      try {
        await authJudges(password);
        setAuthed(true);
        storeJudgesPassword(password);
      } catch {
        setAuthed(false);
      }
    })();
  }, []);

  const handleAuth = async () => {
    setError("");
    setBusy(true);
    try {
      await authJudges(password);
      storeJudgesPassword(password);
      setAuthed(true);
    } catch (caught) {
      setError(
        caught instanceof Error && caught.message === "UNAUTHORIZED"
          ? "비밀번호가 일치하지 않습니다."
          : "인증 실패",
      );
      setAuthed(false);
    } finally {
      setBusy(false);
    }
  };

  const handleSearch = async () => {
    setError("");
    setBusy(true);
    try {
      const list = await searchJudges(password, query);
      setResults(list);
    } catch (caught) {
      if (caught instanceof Error && caught.message === "UNAUTHORIZED") {
        setAuthed(false);
        setError("세션이 만료되었습니다. 비밀번호를 다시 입력해 주세요.");
      } else {
        setError(caught instanceof Error ? caught.message : "검색 실패");
      }
    } finally {
      setBusy(false);
    }
  };

  const sortedResults = useMemo(() => results, [results]);

  if (!authed) {
    return (
      <View style={styles.gateOuter}>
        <View style={[styles.gateCard, compact ? styles.gateCardCompact : null]}>
          <Text style={styles.gateBrand}>판사어때</Text>
          <Text style={styles.gateSubtitle}>한국 법관 프로필 · 성향 요약 · 판결 추정</Text>
          <View style={styles.gateDivider} />
          <Text style={styles.gateLabel}>접근 비밀번호</Text>
          <TextInput
            value={password}
            onChangeText={setPassword}
            placeholder="비밀번호"
            secureTextEntry
            style={styles.gateInput}
            onSubmitEditing={handleAuth}
          />
          <Pressable
            style={({ pressed }) => [styles.gateButton, pressed ? styles.pressed : null]}
            onPress={handleAuth}
            disabled={busy}
          >
            <Text style={styles.gateButtonText}>{busy ? "확인 중..." : "입장"}</Text>
          </Pressable>
          {error ? <Text style={styles.gateError}>{error}</Text> : null}
          <Link href="/" style={styles.gateBack}>
            ← Lawkey AI 돌아가기
          </Link>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.appOuter}>
      <View style={[styles.topBar, compact ? styles.topBarCompact : null]}>
        <View style={styles.topBarBrand}>
          <Text style={styles.brandMark}>판사어때</Text>
          <Text style={styles.brandTag}>BETA</Text>
        </View>
        <Link href="/" style={styles.topBarBack}>
          ← Lawkey 분석
        </Link>
      </View>

      <ScrollView style={styles.scroller} contentContainerStyle={[styles.scrollerContent, compact ? styles.scrollerContentCompact : null]}>
        <View style={styles.heroCard}>
          <Text style={styles.heroTitle}>어떤 판사를 찾고 계신가요?</Text>
          <Text style={styles.heroDesc}>
            법관 이름으로 검색하면 과거 판례, 경력, 판결 성향 요약을 볼 수 있습니다.
            동명이인은 시기와 소속 법원을 기준으로 자동 분리됩니다.
          </Text>
          <View style={[styles.searchBar, compact ? styles.searchBarCompact : null]}>
            <TextInput
              value={query}
              onChangeText={setQuery}
              placeholder="판사 이름 (예: 김민수)"
              style={styles.searchInput}
              onSubmitEditing={handleSearch}
            />
            <Pressable
              style={({ pressed }) => [styles.searchButton, pressed ? styles.pressed : null]}
              onPress={handleSearch}
              disabled={busy}
            >
              <Text style={styles.searchButtonText}>{busy ? "검색 중..." : "검색"}</Text>
            </Pressable>
          </View>
        </View>

        {error ? <Text style={styles.inlineError}>{error}</Text> : null}

        {sortedResults.length === 0 && !busy ? (
          <View style={styles.emptyState}>
            <Text style={styles.emptyIcon}>⚖</Text>
            <Text style={styles.emptyTitle}>검색어를 입력하세요</Text>
            <Text style={styles.emptyDesc}>
              이름 뒤에 한자·법원 등 힌트를 붙여도 되고, 이름만으로 찾아 뒤에 나오는 법원·시기로 판별해도 됩니다.
            </Text>
          </View>
        ) : null}

        <View style={styles.resultsList}>
          {sortedResults.map((judge) => (
            <Pressable
              key={judge.judgeId}
              style={({ pressed }) => [styles.resultCard, pressed ? styles.resultCardPressed : null]}
              onPress={() => router.push(`/judges/${judge.judgeId}`)}
            >
              <View style={styles.resultHeader}>
                <View style={styles.resultAvatar}>
                  <Text style={styles.resultAvatarText}>{judge.name?.[0] || "?"}</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <View style={styles.resultNameLine}>
                    <Text style={styles.resultName}>{judge.name}</Text>
                    {judge.hanja ? <Text style={styles.resultHanja}>{judge.hanja}</Text> : null}
                  </View>
                  <Text style={styles.resultRange}>
                    {judge.firstSeen}~{judge.lastSeen}
                    {"  "}· 판례 {judge.appearanceCount.toLocaleString()}건
                  </Text>
                </View>
                <Text style={styles.resultChevron}>›</Text>
              </View>
              <View style={styles.resultCourtsRow}>
                {(judge.courts || []).slice(0, 4).map((court) => (
                  <Text key={court} style={styles.resultCourt}>
                    {court}
                  </Text>
                ))}
                {judge.courts && judge.courts.length > 4 ? (
                  <Text style={styles.resultCourtMore}>외 {judge.courts.length - 4}곳</Text>
                ) : null}
              </View>
            </Pressable>
          ))}
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  // Gate
  gateOuter: {
    flex: 1,
    backgroundColor: "#fafafa",
    justifyContent: "center",
    alignItems: "center",
    padding: 20,
  },
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
  gateCardCompact: {
    padding: 22,
  },
  gateBrand: {
    fontFamily: theme.fonts.serif,
    fontSize: 28,
    fontWeight: "700",
    color: theme.colors.text,
    letterSpacing: -0.3,
  },
  gateSubtitle: {
    fontFamily: theme.fonts.serif,
    fontSize: 13,
    color: "#666666",
    marginBottom: 4,
  },
  gateDivider: {
    height: 1,
    backgroundColor: "#eeeeee",
    marginVertical: 10,
  },
  gateLabel: {
    fontFamily: theme.fonts.serif,
    fontSize: 12,
    fontWeight: "700",
    color: "#444444",
    letterSpacing: 0.3,
    textTransform: "uppercase",
  },
  gateInput: {
    borderWidth: 1,
    borderColor: "#dcdcdc",
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontFamily: theme.fonts.serif,
    fontSize: 15,
    backgroundColor: "#fafafa",
  },
  gateButton: {
    backgroundColor: "#101010",
    paddingVertical: 13,
    borderRadius: 10,
    alignItems: "center",
    marginTop: 4,
  },
  gateButtonText: {
    color: "#ffffff",
    fontFamily: theme.fonts.serif,
    fontSize: 14,
    fontWeight: "700",
    letterSpacing: 0.3,
  },
  gateError: {
    color: "#b53737",
    fontFamily: theme.fonts.serif,
    fontSize: 13,
    marginTop: 4,
  },
  gateBack: {
    fontFamily: theme.fonts.serif,
    fontSize: 12,
    color: "#777777",
    textAlign: "center",
    marginTop: 14,
    textDecorationLine: "underline",
  },

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
  topBarBrand: { flexDirection: "row", alignItems: "baseline", gap: 6 },
  brandMark: {
    fontFamily: theme.fonts.serif,
    fontSize: 20,
    fontWeight: "700",
    color: theme.colors.text,
    letterSpacing: -0.2,
  },
  brandTag: {
    fontFamily: theme.fonts.serif,
    fontSize: 10,
    fontWeight: "700",
    color: "#ffffff",
    backgroundColor: "#101010",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    letterSpacing: 0.8,
    overflow: "hidden",
  },
  topBarBack: {
    fontFamily: theme.fonts.serif,
    fontSize: 13,
    color: "#555555",
    textDecorationLine: "underline",
  },

  scroller: { flex: 1 },
  scrollerContent: { paddingHorizontal: 32, paddingVertical: 28, gap: 18, maxWidth: 880, alignSelf: "center", width: "100%" },
  scrollerContentCompact: { paddingHorizontal: 16, paddingVertical: 18 },

  heroCard: {
    backgroundColor: "#ffffff",
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#ececec",
    padding: 28,
    gap: 10,
  },
  heroTitle: {
    fontFamily: theme.fonts.serif,
    fontSize: 24,
    fontWeight: "700",
    color: theme.colors.text,
    letterSpacing: -0.3,
  },
  heroDesc: {
    fontFamily: theme.fonts.serif,
    fontSize: 13,
    color: "#666666",
    lineHeight: 20,
    marginBottom: 4,
  },
  searchBar: {
    flexDirection: "row",
    gap: 8,
    marginTop: 6,
  },
  searchBarCompact: { flexDirection: "column" },
  searchInput: {
    flex: 1,
    borderWidth: 1,
    borderColor: "#dcdcdc",
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontFamily: theme.fonts.serif,
    fontSize: 15,
    backgroundColor: "#fafafa",
  },
  searchButton: {
    paddingHorizontal: 22,
    paddingVertical: 12,
    backgroundColor: "#101010",
    borderRadius: 10,
    alignItems: "center",
    justifyContent: "center",
  },
  searchButtonText: { color: "#ffffff", fontFamily: theme.fonts.serif, fontSize: 14, fontWeight: "700" },

  inlineError: { color: "#b53737", fontFamily: theme.fonts.serif, fontSize: 13 },

  emptyState: {
    alignItems: "center",
    padding: 40,
    gap: 6,
  },
  emptyIcon: { fontSize: 48, color: "#cccccc" },
  emptyTitle: { fontFamily: theme.fonts.serif, fontSize: 16, fontWeight: "700", color: "#555555" },
  emptyDesc: { fontFamily: theme.fonts.serif, fontSize: 13, color: "#888888", textAlign: "center", maxWidth: 360 },

  resultsList: { gap: 10 },
  resultCard: {
    backgroundColor: "#ffffff",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#ececec",
    padding: 16,
    gap: 10,
  },
  resultCardPressed: { backgroundColor: "#f5f5f5" },
  resultHeader: { flexDirection: "row", alignItems: "center", gap: 12 },
  resultAvatar: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: "#101010",
    alignItems: "center",
    justifyContent: "center",
  },
  resultAvatarText: { color: "#ffffff", fontFamily: theme.fonts.serif, fontSize: 18, fontWeight: "700" },
  resultNameLine: { flexDirection: "row", alignItems: "baseline", gap: 6 },
  resultName: { fontFamily: theme.fonts.serif, fontSize: 17, fontWeight: "700", color: theme.colors.text },
  resultHanja: { fontFamily: theme.fonts.serif, fontSize: 13, color: "#888888" },
  resultRange: { fontFamily: theme.fonts.serif, fontSize: 12, color: "#666666", marginTop: 2 },
  resultChevron: { fontSize: 22, color: "#cccccc" },
  resultCourtsRow: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  resultCourt: {
    fontFamily: theme.fonts.serif,
    fontSize: 11,
    color: "#555555",
    backgroundColor: "#f1f1f1",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 999,
  },
  resultCourtMore: { fontFamily: theme.fonts.serif, fontSize: 11, color: "#999999", alignSelf: "center" },
  pressed: { opacity: 0.7 },
});
