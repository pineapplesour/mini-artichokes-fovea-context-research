import { useEffect, useRef, useState } from "react";
import { Animated, Easing, LayoutChangeEvent, Platform, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { theme } from "../../constants/theme";
import { buildHighlightSegments, findTargetUsedQuote, type PrecedentBucketItem, type PrecedentDetailPayload, type SelectedPrecedent } from "../../lib/api";

function highlightAnchorId(precedentId: string, charStart: number | null | undefined): string {
  const suffix = typeof charStart === "number" && charStart >= 0 ? String(charStart) : "first";
  return `lawkey-quote-anchor-${String(precedentId || "default").replace(/[^a-zA-Z0-9_-]/g, "_")}-${suffix}`;
}

function cleanLabel(value: string): string {
  return String(value || "")
    .replace(/\[판례\s*\d+\]/gi, " ")
    .replace(/^(제목|확정\s*날짜|항소\s*날짜|날짜|url)\s*:\s*/gi, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function compactText(value: string, limit = 110): string {
  const cleaned = cleanLabel(value);
  if (cleaned.length <= limit) {
    return cleaned;
  }
  const clipped = cleaned.slice(0, limit).replace(/\s+\S*$/, "").trim();
  return `${clipped || cleaned.slice(0, limit).trim()}…`;
}

function normalizeCaseNumberLabel(value: string): string {
  const cleaned = cleanLabel(value);
  const match = cleaned.match(/\b(\d{2,4})\s*([가-힣]{1,4})\s*(\d{1,6}(?:\s*,\s*\d{1,6})*)\b/);
  return match ? `${match[1]}${match[2]}${match[3].replace(/\s+/g, "")} 판결` : "";
}

function buildBucketCitation(item: PrecedentBucketItem): string {
  return normalizeCaseNumberLabel(item.case_number || item.citation || "") || "참조 판례";
}

function buildSparseDetailCitation(detail: PrecedentDetailPayload): string {
  return normalizeCaseNumberLabel(detail.caseNumber || detail.citation || "") || "참조 판례";
}

type PrecedentDrawerProps = {
  precedents: SelectedPrecedent[];
  usedPrecedents?: SelectedPrecedent[];
  usedPrecedentIds: string[];
  precedentBuckets?: {
    very_similar?: PrecedentBucketItem[];
    similar?: PrecedentBucketItem[];
    usable?: PrecedentBucketItem[];
    other?: PrecedentBucketItem[];
  };
  detailOpen: boolean;
  selectedId: string;
  selectedDetail: PrecedentDetailPayload | null;
  targetQuoteText?: string;
  onOpen: (id: string) => void;
  onBack: () => void;
};

export function PrecedentDrawer({
  precedentBuckets,
  detailOpen,
  selectedId,
  selectedDetail,
  targetQuoteText,
  onOpen,
  onBack,
}: PrecedentDrawerProps) {
  const fullTextScrollRef = useRef<ScrollView | null>(null);
  const autoScrolledFor = useRef("");
  const highlightPulse = useRef(new Animated.Value(0)).current;
  const [textMetrics, setTextMetrics] = useState({ contentHeight: 0, viewportHeight: 0 });

  useEffect(() => {
    setTextMetrics({ contentHeight: 0, viewportHeight: 0 });
  }, [selectedDetail?.precedentId]);

  // Reset the auto-scroll guard whenever the user closes the detail panel so
  // that re-opening the same precedent triggers a fresh scroll-to-highlight
  // and pulse animation.
  useEffect(() => {
    if (!detailOpen) {
      autoScrolledFor.current = "";
    }
  }, [detailOpen]);

  useEffect(() => {
    if (!detailOpen || !selectedDetail || !selectedDetail.usedQuotes.length) {
      return;
    }
    const targetQuote = findTargetUsedQuote(selectedDetail.usedQuotes, targetQuoteText);
    if (!targetQuote) {
      return;
    }
    const scrollKey = `${selectedDetail.precedentId}:${targetQuote.charStart ?? "first"}:${targetQuoteText || ""}`;
    if (autoScrolledFor.current === scrollKey) {
      return;
    }
    const runHighlightPulse = () => {
      autoScrolledFor.current = scrollKey;
      // Briefly flash a brighter accent (peak), then settle on a strong
      // saturated yellow so the matched span stays visibly highlighted as
      // long as the drawer is open. The previous animation faded all the way
      // back to the base color, which read as the highlight being "released".
      highlightPulse.setValue(0);
      Animated.sequence([
        Animated.timing(highlightPulse, {
          toValue: 1,
          duration: 320,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: false,
        }),
        Animated.delay(900),
        Animated.timing(highlightPulse, {
          toValue: 0.6,
          duration: 700,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: false,
        }),
      ]).start();
    };

    // On web, defer to the browser to scroll every ancestor scroll container
    // so the highlight lands exactly centered in the viewport — that handles
    // both the outer chat scroll and the inner full-text scroll precisely
    // without ratio-based approximation.
    if (Platform.OS === "web" && typeof document !== "undefined") {
      const handle = setTimeout(() => {
        const node = document.getElementById(highlightAnchorId(selectedDetail.precedentId, targetQuote.charStart)) as HTMLElement | null;
        if (node && typeof node.scrollIntoView === "function") {
          try {
            node.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
          } catch {
            node.scrollIntoView();
          }
        }
        runHighlightPulse();
      }, 140);
      return () => clearTimeout(handle);
    }

    if (!textMetrics.contentHeight || !textMetrics.viewportHeight) {
      return;
    }
    const ratio = Math.min(1, Math.max(0, Number(targetQuote.charStart || 0) / Math.max(selectedDetail.fullText.length, 1)));
    const maxOffset = Math.max(textMetrics.contentHeight - textMetrics.viewportHeight, 0);
    // Subtract about a third of the viewport so the highlight lands slightly
    // above center rather than at the very top (the previous approximation
    // landed it slightly above the highlight too often).
    const approxOffsetY = Math.max(0, Math.round(ratio * maxOffset - textMetrics.viewportHeight / 3));
    const handle = setTimeout(() => {
      fullTextScrollRef.current?.scrollTo({ y: approxOffsetY, animated: true });
      runHighlightPulse();
    }, 120);
    return () => clearTimeout(handle);
  }, [detailOpen, highlightPulse, selectedDetail, targetQuoteText, textMetrics.contentHeight, textMetrics.viewportHeight]);

  if (detailOpen && !selectedDetail) {
    return (
      <View style={styles.shell}>
        <View style={styles.detailHeader}>
          <Pressable accessibilityRole="button" onPress={onBack} style={({ pressed }) => [styles.backButton, pressed ? styles.pressed : null]}>
            <Text style={styles.backButtonText}>← 응답으로 돌아가기</Text>
          </Pressable>
          <Text style={styles.paneLabel}>판례 상세</Text>
        </View>
        <Text style={styles.sectionHint}>전문과 하이라이트를 불러오는 중입니다.</Text>
      </View>
    );
  }

  if (detailOpen && selectedDetail) {
    const segments = buildHighlightSegments(selectedDetail.fullText, selectedDetail.usedQuotes);
    const sparseDetailCitation = buildSparseDetailCitation(selectedDetail);
    // Resting state (pulse=0) keeps the base highlight, the resting-after-
    // pulse state (~0.6) holds a saturated accent, and the brief peak (=1)
    // flashes the strongest tone for attention. The Animated.Value settles
    // at 0.6 after `runHighlightPulse`, so the highlight stays clearly
    // visible instead of fading back to invisible.
    const animatedHighlightStyle = {
      backgroundColor: highlightPulse.interpolate({
        inputRange: [0, 0.6, 1],
        outputRange: [theme.colors.highlight, "#ffd84d", "#ffb700"],
      }),
    };

    return (
      <View style={styles.shell}>
        <View style={styles.detailHeader}>
          <Pressable accessibilityRole="button" onPress={onBack} style={({ pressed }) => [styles.backButton, pressed ? styles.pressed : null]}>
            <Text style={styles.backButtonText}>← 응답으로 돌아가기</Text>
          </Pressable>
          <Text style={styles.paneLabel}>판례 상세</Text>
        </View>

        <Text style={styles.detailTitle}>{sparseDetailCitation}</Text>
        <Text style={styles.detailMeta}>본문 하이라이트와 사용된 인용</Text>

        <View style={styles.overlayRow}>
          <OverlayCard label="판례 요약" body={selectedDetail.summaryOverlay || "요약이 아직 정리되지 않았습니다."} />
          <OverlayCard label="맥락" body={selectedDetail.contextOverlay || "맥락이 아직 정리되지 않았습니다."} />
        </View>

        <ScrollView
          ref={fullTextScrollRef}
          style={styles.fullTextShell}
          contentContainerStyle={styles.fullTextContent}
          showsVerticalScrollIndicator={false}
          onLayout={(event: LayoutChangeEvent) => {
            const nextHeight = event.nativeEvent.layout.height;
            setTextMetrics((current) => (current.viewportHeight === nextHeight ? current : { ...current, viewportHeight: nextHeight }));
          }}
          onContentSizeChange={(_, height) => {
            setTextMetrics((current) => (current.contentHeight === height ? current : { ...current, contentHeight: height }));
          }}
        >
          <Text style={styles.fullText}>
            {(() => {
              let firstHighlightSeen = false;
              let cursor = 0;
              const targetQuote = findTargetUsedQuote(selectedDetail.usedQuotes, targetQuoteText);
              const targetStart = typeof targetQuote?.charStart === "number" ? targetQuote.charStart : null;
              const fallbackAnchorId = highlightAnchorId(selectedDetail.precedentId, null);
              const targetAnchorId = highlightAnchorId(selectedDetail.precedentId, targetStart);
              return segments.map((segment, index) => {
                const segmentStart = cursor;
                const segmentEnd = cursor + segment.text.length;
                cursor = segmentEnd;
                if (segment.highlighted) {
                  const isFirstHighlight = !firstHighlightSeen;
                  if (isFirstHighlight) firstHighlightSeen = true;
                  const isTargetHighlight =
                    typeof targetStart === "number" && targetStart >= segmentStart && targetStart < segmentEnd;
                  return (
                    <Animated.Text
                      key={`segment-${index}`}
                      // Web-only id used as a scroll anchor. RN web maps
                      // `nativeID` onto the rendered DOM element's `id`.
                      nativeID={isTargetHighlight ? targetAnchorId : isFirstHighlight ? fallbackAnchorId : undefined}
                      style={[styles.highlight, animatedHighlightStyle]}
                    >
                      {segment.text}
                    </Animated.Text>
                  );
                }
                return <Text key={`segment-${index}`}>{segment.text}</Text>;
              });
            })()}
          </Text>
        </ScrollView>

        <View style={styles.quoteList}>
          <Text style={styles.sectionTitle}>사용된 인용</Text>
          {selectedDetail.usedQuotes.length ? (
            selectedDetail.usedQuotes.map((quote, index) => (
              <View key={`${quote.evidenceId}-${index}`} style={styles.quoteCard}>
                <Text style={styles.quoteMeta}>
                  {quote.quoteRole.toUpperCase()} · {quote.claimAxis || "주장 축 미상"}
                </Text>
                <Text style={styles.quoteBody}>{quote.quote}</Text>
              </View>
            ))
          ) : (
            <Text style={styles.sectionHint}>이 판례에서 직접 채택된 인용이 아직 없습니다.</Text>
          )}
        </View>
      </View>
    );
  }

  return (
    <View style={styles.shell}>
      <View style={styles.listHeader}>
        <Text style={styles.paneLabel}>참고 판례 목록</Text>
      </View>
      <ScrollView contentContainerStyle={styles.listContent} showsVerticalScrollIndicator={false}>
        <BucketSection label="매우 유사한 판례" items={precedentBuckets?.very_similar ?? []} onOpen={onOpen} />
        <BucketSection label="유사한 판례" items={precedentBuckets?.similar ?? []} onOpen={onOpen} />
        <BucketSection label="이용할 만한 판례" items={precedentBuckets?.usable ?? []} onOpen={onOpen} />
        <BucketSection label="기타" items={precedentBuckets?.other ?? []} onOpen={onOpen} compact />
      </ScrollView>

    </View>
  );
}

function BucketSection({
  label,
  items,
  onOpen,
  compact = false,
}: {
  label: string;
  items: PrecedentBucketItem[];
  onOpen: (id: string) => void;
  compact?: boolean;
}) {
  return (
    <View style={styles.bucketSection}>
      <Text style={styles.sectionTitle}>{label}</Text>
      {items.length ? (
        items.map((item, index) => {
          const displayTitle = buildBucketCitation(item);
          const secondary = compactText(item.summary || item.excerpt || item.why || "", compact ? 80 : 118);
          const relatedAxes = compactText((item.supported_claim_axes || []).filter(Boolean).join(" · "), 92);
          if (!displayTitle && !secondary) {
            return null;
          }
          return (
            <View
              key={`${item.case_number || item.precedentId || label}-${index}`}
              style={styles.bucketCard}
            >
              {displayTitle ? <Text style={styles.bucketCitation}>{compactText(displayTitle, compact ? 84 : 100)}</Text> : null}
              {!compact && relatedAxes ? <Text style={styles.bucketAxis}>관련 주장: {relatedAxes}</Text> : null}
              {!compact && item.why ? <Text style={styles.bucketReason}>{compactText(item.why, 88)}</Text> : null}
              {!compact && secondary ? <Text style={styles.bucketSummary}>{secondary}</Text> : null}
              {item.precedentId ? (
                <Pressable
                  accessibilityRole="button"
                  onPress={() => onOpen(item.precedentId || "")}
                  style={({ pressed }) => [styles.smallActionButton, pressed ? styles.pressed : null]}
                >
                  <Text style={styles.smallActionText}>전문 보기</Text>
                </Pressable>
              ) : null}
            </View>
          );
        })
      ) : (
        <Text style={styles.sectionHint}>해당 없음</Text>
      )}
    </View>
  );
}

function OverlayCard({ label, body }: { label: string; body: string }) {
  return (
    <View style={styles.overlayCard}>
      <Text style={styles.overlayLabel}>{label}</Text>
      <Text style={styles.overlayBody}>{body}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  shell: {
    borderWidth: 1,
    borderColor: theme.colors.line,
    borderRadius: 12,
    overflow: "hidden",
    backgroundColor: "#ffffff",
    padding: 20,
    gap: 16,
  },
  listHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  detailHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12,
  },
  paneLabel: {
    color: theme.colors.muted,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  listContent: {
    gap: 10,
  },
  bucketSection: {
    gap: 8,
    marginBottom: 16,
  },
  bucketCard: {
    borderWidth: 1,
    borderColor: theme.colors.line,
    borderRadius: 12,
    padding: 14,
    backgroundColor: "#ffffff",
    gap: 6,
  },
  smallActionButton: {
    alignSelf: "flex-start",
    borderWidth: 1,
    borderColor: "#d1d5db",
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 6,
    backgroundColor: "#f5f6f8",
  },
  smallActionText: {
    color: theme.colors.text,
    fontSize: 11,
    fontWeight: "700",
  },
  bucketCitation: {
    color: theme.colors.text,
    fontFamily: theme.fonts.serif,
    fontSize: 16,
    lineHeight: 24,
    fontWeight: "700",
  },
  bucketReason: {
    color: theme.colors.text,
    fontSize: 13,
    lineHeight: 20,
  },
  bucketAxis: {
    color: "#6b7280",
    fontSize: 12,
    lineHeight: 18,
  },
  bucketSummary: {
    color: theme.colors.subtle,
    fontSize: 13,
    lineHeight: 20,
  },
  listItem: {
    borderWidth: 1,
    borderColor: theme.colors.line,
    borderRadius: 12,
    padding: 14,
    backgroundColor: "#ffffff",
    gap: 8,
  },
  listItemActive: {
    borderColor: "#101010",
  },
  listEyebrowRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12,
  },
  listItemEyebrow: {
    color: "#6b7280",
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.7,
  },
  listItemTitle: {
    color: theme.colors.text,
    fontFamily: theme.fonts.serif,
    fontSize: 18,
    fontWeight: "700",
    lineHeight: 24,
  },
  listItemMeta: {
    color: theme.colors.subtle,
    fontSize: 13,
    lineHeight: 20,
  },
  detailTitle: {
    color: theme.colors.text,
    fontFamily: theme.fonts.serif,
    fontSize: 24,
    fontWeight: "700",
    lineHeight: 32,
  },
  detailMeta: {
    color: theme.colors.subtle,
    fontSize: 12,
    lineHeight: 18,
  },
  backButton: {
    borderWidth: 1,
    borderColor: theme.colors.line,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: "#f5f6f8",
  },
  backButtonText: {
    color: theme.colors.text,
    fontSize: 12,
    fontWeight: "700",
  },
  overlayRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
  },
  overlayCard: {
    minWidth: 240,
    flexBasis: 280,
    flexGrow: 1,
    borderRadius: 22,
    borderWidth: 1,
    borderColor: "#d1d5db",
    backgroundColor: "#f8f9fb",
    padding: 18,
    gap: 8,
  },
  overlayLabel: {
    color: theme.colors.muted,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.7,
    textTransform: "uppercase",
  },
  overlayBody: {
    color: theme.colors.text,
    fontSize: 14,
    lineHeight: 22,
  },
  fullTextShell: {
    maxHeight: 460,
    borderWidth: 1,
    borderColor: theme.colors.line,
    borderRadius: 10,
    backgroundColor: "#fcfcfc",
  },
  fullTextContent: {
    padding: 18,
  },
  fullText: {
    color: theme.colors.text,
    fontSize: 15,
    lineHeight: 26,
  },
  highlight: {
    backgroundColor: theme.colors.highlight,
  },
  quoteList: {
    gap: 10,
  },
  sectionTitle: {
    color: theme.colors.text,
    fontSize: 13,
    fontWeight: "700",
    letterSpacing: 0.6,
    textTransform: "uppercase",
  },
  quoteCard: {
    borderRadius: 16,
    borderWidth: 1,
    borderColor: theme.colors.line,
    backgroundColor: "#f8f9fb",
    padding: 14,
    gap: 8,
  },
  quoteMeta: {
    color: theme.colors.muted,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.6,
    textTransform: "uppercase",
  },
  quoteBody: {
    color: theme.colors.text,
    fontSize: 14,
    lineHeight: 22,
  },
  sectionHint: {
    color: theme.colors.subtle,
    fontSize: 12,
    lineHeight: 18,
  },
  pressed: {
    opacity: 0.88,
  },
});
