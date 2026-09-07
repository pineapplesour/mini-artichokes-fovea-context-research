import { useMemo, useRef, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, useWindowDimensions, View } from "react-native";

import { buildDomainAnswerView, type DomainAnswerView } from "../../lib/domain-answer-view";
import { runDomainQuestion, type DomainAnswer } from "../../lib/domain-api";
import { buildDomainControlPayload, buildDomainFeatureStates, type DomainControlPayload, type DomainFeatureState } from "../../lib/domain-features";
import {
  buildDomainPalette,
  getDomainLocaleCopy,
  getDomainProduct,
  normalizeDomainLanguage,
  type DomainKey,
  type DomainLocaleCopy,
  type DomainProduct,
} from "../../lib/domain-factory";
import { isConstrainedClient } from "../../lib/performance-mode";

type Props = {
  domain: string;
};

type DomainConversationTurn = {
  id: string;
  query: string;
  language: string;
  answer: DomainAnswer;
  createdAt: number;
};

type WorkspaceState = {
  product: DomainProduct;
  copy: DomainLocaleCopy;
  palette: ReturnType<typeof buildDomainPalette>;
  compact: boolean;
  constrained: boolean;
  language: string;
  query: string;
  loading: boolean;
  pendingQuery: string;
  turns: DomainConversationTurn[];
  activeTurn: DomainConversationTurn | null;
  activeTurnId: string;
  hasChatWorkspace: boolean;
  answer: DomainAnswer | null;
  answerView: DomainAnswerView;
  featureStates: DomainFeatureState[];
  controlPayload: DomainControlPayload[];
  activeFeatureId: string;
  selectedPassageLabel: string;
  error: string;
  styles: ReturnType<typeof createStyles>;
  setLanguage: (language: string) => void;
  setQuery: (query: string) => void;
  setActiveTurnId: (id: string) => void;
  setActiveFeatureId: (id: string) => void;
  setSelectedPassageLabel: (label: string) => void;
  submit: (query?: string) => void;
  cancel: () => void;
};

export function DomainWorkspace({ domain }: Props) {
  const { width } = useWindowDimensions();
  const constrained = isConstrainedClient();
  const compact = width < 880;
  const product = getDomainProduct(domain);
  const palette = buildDomainPalette(product.key);
  const [language, setLanguage] = useState(product.defaultLanguage);
  const [query, setQuery] = useState(product.examples[0]?.query || "");
  const [loading, setLoading] = useState(false);
  const [pendingQuery, setPendingQuery] = useState("");
  const [turns, setTurns] = useState<DomainConversationTurn[]>([]);
  const [activeTurnId, setActiveTurnId] = useState("");
  const [activeFeatureId, setActiveFeatureId] = useState("");
  const [selectedPassageLabel, setSelectedPassageLabel] = useState("");
  const [error, setError] = useState("");
  const requestIdRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);
  const resolvedLanguage = normalizeDomainLanguage(product.key, language);
  const copy = getDomainLocaleCopy(product.key, resolvedLanguage);
  const activeTurn = useMemo(
    () => turns.find((turn) => turn.id === activeTurnId) || turns[turns.length - 1] || null,
    [activeTurnId, turns],
  );
  const answer = activeTurn?.answer || null;
  const answerView = useMemo(() => buildDomainAnswerView(answer), [answer]);
  const featureStates = useMemo(
    () => buildDomainFeatureStates(product.key, answer, pendingQuery || activeTurn?.query || query),
    [product.key, answer, pendingQuery, activeTurn?.query, query],
  );
  const controlPayload = useMemo(
    () => buildDomainControlPayload(product.key, featureStates, activeFeatureId),
    [product.key, featureStates, activeFeatureId],
  );
  const styles = useMemo(
    () => createStyles(palette, compact, product.key, copy.direction),
    [palette, compact, product.key, copy.direction],
  );
  const hasChatWorkspace = Boolean(loading || error || turns.length);

  const submit = async (nextQuery = query) => {
    const trimmed = nextQuery.trim();
    if (!trimmed || loading) return;
    abortRef.current?.abort();
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    const controller = new AbortController();
    abortRef.current = controller;
    setQuery(trimmed);
    setPendingQuery(trimmed);
    setLoading(true);
    setError("");
    try {
      const requestFeatures = buildDomainFeatureStates(product.key, answer, trimmed);
      const result = await runDomainQuestion(product.key, trimmed, resolvedLanguage, {
        signal: controller.signal,
        timeoutMs: 120_000,
        controls: buildDomainControlPayload(product.key, requestFeatures, activeFeatureId),
      });
      if (requestId !== requestIdRef.current) return;
      const turn: DomainConversationTurn = {
        id: result.jobId || `${Date.now()}`,
        query: trimmed,
        language: result.language || resolvedLanguage,
        answer: result,
        createdAt: Date.now(),
      };
      setTurns((current) => [...current, turn]);
      setActiveTurnId(turn.id);
      setSelectedPassageLabel(result.passages?.[0]?.label || result.sources?.[0]?.label || "");
      setQuery("");
    } catch (exc) {
      if (controller.signal.aborted && requestId !== requestIdRef.current) return;
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      if (requestId === requestIdRef.current) {
        setPendingQuery("");
        setLoading(false);
        abortRef.current = null;
      }
    }
  };

  const cancel = () => {
    requestIdRef.current += 1;
    abortRef.current?.abort();
    abortRef.current = null;
    setPendingQuery("");
    setLoading(false);
  };

  const state: WorkspaceState = {
    product,
    copy,
    palette,
    compact,
    constrained,
    language: resolvedLanguage,
    query,
    loading,
    pendingQuery,
    turns,
    activeTurn,
    activeTurnId,
    hasChatWorkspace,
    answer,
    answerView,
    featureStates,
    controlPayload,
    activeFeatureId,
    selectedPassageLabel,
    error,
    styles,
    setLanguage,
    setQuery,
    setActiveTurnId,
    setActiveFeatureId,
    setSelectedPassageLabel,
    submit,
    cancel,
  };

  return (
    <ScrollView style={styles.page} contentContainerStyle={styles.shell}>
      {product.referenceLayout === "islam-centered-thread" ? <IslamLayout state={state} /> : null}
      {product.referenceLayout === "hanji-consult" ? <TcmLayout state={state} /> : null}
      {product.referenceLayout === "therapeutic-aurora" ? <PsychologyLayout state={state} /> : null}
    </ScrollView>
  );
}

function IslamLayout({ state }: { state: WorkspaceState }) {
  const { product, copy, styles, compact } = state;
  return (
    <View>
      <View style={[styles.islamNav, compact && styles.stackHeader]}>
        <BrandBlock state={state} />
        {!compact ? (
          <View style={styles.islamNavLinks}>
            <Text style={styles.navText}>QUR'AN</Text>
            <Text style={styles.navText}>HADITH</Text>
            <Text style={styles.navText}>FIQH</Text>
          </View>
        ) : null}
        <LanguageSwitcher state={state} />
      </View>

      {state.hasChatWorkspace ? <ChatWorkspace state={state} /> : null}
      {!state.hasChatWorkspace ? (
      <View style={styles.islamHero}>
        <View style={styles.islamOrnament}>
          <DomainOrnament domain="islam" />
        </View>
        <Text style={styles.islamEyebrow}>{product.eyebrow}</Text>
        <Text style={styles.islamHeadline}>
          <Text>Hikmah </Text>
          <Text style={styles.islamHeadlineAccent}>Archive</Text>
        </Text>
        <Text style={styles.islamArabic}>ٱلْعِلْمُ نُور</Text>
        <Text style={styles.islamSubline}>{product.subline}</Text>
        <QueryBox state={state} variant="islam" />
        <ExampleChips state={state} centered />
        <FeaturePanel state={state} />
      </View>
      ) : null}

      {!state.hasChatWorkspace ? (
      <View style={styles.islamThread}>
        <View style={styles.threadDivider}>
          <View style={styles.threadLine} />
          <Text style={styles.panelLabel}>{copy.answerLabel}</Text>
          <View style={styles.threadLine} />
        </View>
        <AnswerPanel state={state} threaded />
        <SourceRail state={state} />
      </View>
      ) : null}
    </View>
  );
}

function TcmLayout({ state }: { state: WorkspaceState }) {
  const { product, copy, styles, compact } = state;
  return (
    <View>
      <View style={[styles.tcmTopbar, compact && styles.stackHeader]}>
        <BrandBlock state={state} />
        {!compact ? (
          <View style={styles.tcmNavLinks}>
            <Text style={styles.tcmNavText}>상담</Text>
            <Text style={styles.tcmNavText}>체질</Text>
            <Text style={styles.tcmNavText}>본초</Text>
            <Text style={styles.tcmNavText}>고서</Text>
          </View>
        ) : null}
        <LanguageSwitcher state={state} />
      </View>

      {state.hasChatWorkspace ? <ChatWorkspace state={state} /> : null}
      {!state.hasChatWorkspace ? (
      <View style={[styles.tcmHero, compact && styles.tcmHeroCompact]}>
        <View style={styles.tcmHeroCopy}>
          <Text style={styles.tcmEyebrow}>{product.eyebrow}</Text>
          <Text style={styles.tcmHeadline}>{product.headline}</Text>
          <Text style={styles.tcmSubline}>{product.subline}</Text>
          <QueryBox state={state} variant="tcm" />
          <ExampleChips state={state} />
        </View>
        <View style={styles.tcmMandala}>
          <DomainOrnament domain="tcm" />
          <Text style={styles.tcmGlyph}>醫</Text>
          <Text style={[styles.cornerTag, styles.cornerTopLeft]}>東方{"\n"}木</Text>
          <Text style={[styles.cornerTag, styles.cornerTopRight]}>南方{"\n"}火</Text>
          <Text style={[styles.cornerTag, styles.cornerBottomLeft]}>北方{"\n"}水</Text>
          <Text style={[styles.cornerTag, styles.cornerBottomRight]}>西方{"\n"}金</Text>
        </View>
      </View>
      ) : null}

      {!state.hasChatWorkspace ? (
      <View style={[styles.consultPanel, compact && styles.consultPanelCompact]}>
        <View style={styles.consultAside}>
          <View style={styles.doctorRow}>
            <View style={styles.doctorAvatar}>
              <Text style={styles.doctorAvatarText}>醫</Text>
            </View>
            <View>
              <Text style={styles.doctorName}>문헌 상담</Text>
              <Text style={styles.doctorRole}>CLASSIC · FTS · SOURCE</Text>
            </View>
          </View>
          <Text style={styles.asideHeading}>{copy.safetyLabel}</Text>
          <Text style={styles.safetyText}>{product.safetyNotice}</Text>
          <FeaturePanel state={state} compactPanel />
          <SourceRail state={state} compactRail />
        </View>
        <View style={styles.consultMain}>
          <View style={styles.consultHead}>
            <Text style={styles.consultTitle}>{copy.answerLabel}</Text>
            <Text style={styles.consultMeta}>BETA-6 DOMAIN</Text>
          </View>
          <AnswerPanel state={state} threaded />
        </View>
      </View>
      ) : null}
    </View>
  );
}

function PsychologyLayout({ state }: { state: WorkspaceState }) {
  const { product, copy, styles, compact } = state;
  return (
    <View style={styles.psychStage}>
      <View style={styles.psychRingLarge} />
      <View style={styles.psychRingSmall} />
      <View style={[styles.psychHeader, compact && styles.stackHeader]}>
        <BrandBlock state={state} />
        <LanguageSwitcher state={state} />
      </View>

      {state.hasChatWorkspace ? <ChatWorkspace state={state} /> : null}
      {!state.hasChatWorkspace ? (
      <View style={[styles.psychGrid, compact && styles.psychGridCompact]}>
        <View style={styles.psychMain}>
          <Text style={styles.psychEyebrow}>{product.eyebrow}</Text>
          <Text style={styles.psychHeadline}>{product.headline}</Text>
          <Text style={styles.psychSubline}>{product.subline}</Text>
          <QueryBox state={state} variant="psychology" />
          <ExampleChips state={state} />
          <AnswerPanel state={state} />
        </View>
        <View style={styles.psychRail}>
          <Text style={styles.railKicker}>{copy.safetyLabel}</Text>
          <Text style={styles.safetyText}>{product.safetyNotice}</Text>
          <FeaturePanel state={state} compactPanel />
          <View style={styles.softDivider} />
          <SourceRail state={state} compactRail />
        </View>
      </View>
      ) : null}
    </View>
  );
}

function BrandBlock({ state }: { state: WorkspaceState }) {
  const { product, styles } = state;
  return (
    <View style={styles.brand}>
      <DomainMark domain={product.key} />
      <View>
        <Text style={styles.brandName}>{product.name}</Text>
        <Text style={styles.brandSub}>{product.shortName}</Text>
      </View>
    </View>
  );
}

function LanguageSwitcher({ state }: { state: WorkspaceState }) {
  const { product, language, styles, setLanguage } = state;
  return (
    <View style={styles.languageRow}>
      {product.languages.map((item) => (
        <Pressable
          key={item}
          accessibilityRole="button"
          onPress={() => setLanguage(item)}
          style={[styles.langPill, language === item && styles.langPillActive]}
        >
          <Text style={[styles.langText, language === item && styles.langTextActive]}>{item.toUpperCase()}</Text>
        </Pressable>
      ))}
    </View>
  );
}

function QueryBox({ state, variant }: { state: WorkspaceState; variant: DomainKey }) {
  const { product, copy, query, loading, styles, setQuery, submit, cancel } = state;
  return (
    <View style={[styles.queryBox, variant === "islam" && styles.queryBoxIslam, variant === "tcm" && styles.queryBoxTcm]}>
      <View style={styles.queryLabelRow}>
        <Text style={styles.queryLabel}>{copy.askLabel}</Text>
        <Text style={styles.queryMode}>BETA-6 · FTS</Text>
      </View>
      <TextInput
        value={query}
        onChangeText={setQuery}
        multiline
        placeholder={copy.queryPlaceholder || product.examples[0]?.query || ""}
        placeholderTextColor={state.palette.muted}
        style={styles.input}
        accessibilityLabel={`${product.name} query`}
      />
      <View style={styles.queryToolbar}>
        <Text style={styles.queryHint}>{copy.safetyLabel}</Text>
        <Pressable onPress={() => (loading ? cancel() : submit())} style={styles.sendButton} accessibilityRole="button">
          <Text style={styles.sendText}>{loading ? copy.cancelLabel : copy.sendLabel}</Text>
        </Pressable>
      </View>
    </View>
  );
}

function ExampleChips({ state, centered = false }: { state: WorkspaceState; centered?: boolean }) {
  const { product, copy, styles, submit } = state;
  return (
    <View style={[styles.exampleWrap, centered && styles.exampleWrapCentered]}>
      <Text style={styles.exampleLabel}>{copy.examplesLabel}</Text>
      {product.examples.map((example) => (
        <Pressable key={example.label} onPress={() => submit(example.query)} style={styles.example} accessibilityRole="button">
          <Text style={styles.exampleText}>{example.label}</Text>
        </Pressable>
      ))}
    </View>
  );
}

function ChatWorkspace({ state }: { state: WorkspaceState }) {
  const { compact, copy, loading, pendingQuery, product, styles, turns, activeTurn } = state;
  const activeQuery = loading ? pendingQuery : activeTurn?.query || pendingQuery || state.query;
  return (
    <View style={[styles.chatShell, compact && styles.chatShellCompact]}>
      {!compact ? <HistoryRail state={state} /> : <HistoryStrip state={state} />}
      <View style={styles.chatMain}>
        <View style={styles.chatCrumbs}>
          <Text style={styles.chatCrumbPill}>{product.postQueryWorkspace.corpusLabel}</Text>
          <Text style={styles.chatCrumbSep}>/</Text>
          <Text style={styles.chatCrumbHere}>{activeQuery || copy.answerLabel}</Text>
        </View>
        <View style={styles.chatThread}>
          {activeQuery ? (
            <View style={styles.userTurn}>
              <View style={styles.userMark} />
              <View style={styles.userTurnBody}>
                <Text style={styles.questionNumber}>Q{String(turns.length + (loading ? 1 : 0)).padStart(2, "0")}</Text>
                <Text style={styles.questionTitle}>{activeQuery}</Text>
                <Text style={styles.questionMeta}>{state.language.toUpperCase()} · BETA-6 DOMAIN</Text>
              </View>
            </View>
          ) : null}
          <View style={styles.assistantTurn}>
            <View style={styles.assistantRule} />
            <View style={styles.assistantBody}>
              <AnswerPanel state={state} threaded />
              {state.answer?.beta6 ? <Beta6Trace state={state} /> : null}
            </View>
          </View>
        </View>
        <QueryBox state={state} variant={product.key} />
      </View>
      <View style={styles.chatEvidence}>
        <View style={styles.evidenceHead}>
          <Text style={styles.evidenceTitle}>{product.postQueryWorkspace.evidenceLabel}</Text>
          <Text style={styles.evidenceCount}>{String(state.answerView.passages.length).padStart(2, "0")}</Text>
        </View>
        <SourceRail state={state} compactRail />
        <FeaturePanel state={state} compactPanel />
      </View>
    </View>
  );
}

function FeaturePanel({ state, compactPanel = false }: { state: WorkspaceState; compactPanel?: boolean }) {
  const { activeFeatureId, featureStates, styles, setActiveFeatureId, setSelectedPassageLabel } = state;
  return (
    <View style={[styles.featurePanel, compactPanel && styles.featurePanelCompact]}>
      <Text style={styles.panelLabel}>Domain controls</Text>
      <View style={styles.featureGrid}>
        {featureStates.map((feature) => (
          <Pressable
            key={feature.id}
            accessibilityRole="button"
            accessibilityLabel={`${feature.title} ${feature.status}`}
            onPress={() => {
              setActiveFeatureId(activeFeatureId === feature.id ? "" : feature.id);
              if (feature.evidenceLabels[0]) setSelectedPassageLabel(feature.evidenceLabels[0]);
            }}
            style={[
              styles.featureCard,
              activeFeatureId === feature.id && styles.featureCardActive,
              feature.status === "watch" && styles.featureCardWatch,
            ]}
          >
            <View style={styles.featureHead}>
              <Text style={styles.featureKicker}>{feature.kicker}</Text>
              <Text style={[styles.featureStatus, feature.status === "active" && styles.featureStatusActive, feature.status === "watch" && styles.featureStatusWatch]}>
                {activeFeatureId === feature.id ? "filter" : feature.status}
              </Text>
            </View>
            <Text style={styles.featureTitle}>{feature.title}</Text>
            <Text style={styles.featureDetail}>{feature.detail}</Text>
            {feature.evidenceLabels.length ? (
              <View style={styles.featureEvidenceRow}>
                {feature.evidenceLabels.slice(0, 3).map((label) => (
                  <Pressable
                    key={`${feature.id}-${label}`}
                    accessibilityRole="button"
                    onPress={() => setSelectedPassageLabel(label)}
                    style={styles.featureEvidenceChip}
                  >
                    <Text style={styles.featureEvidenceText}>{label}</Text>
                  </Pressable>
                ))}
              </View>
            ) : null}
          </Pressable>
        ))}
      </View>
    </View>
  );
}

function HistoryRail({ state }: { state: WorkspaceState }) {
  const { activeTurnId, loading, pendingQuery, product, styles, turns, setActiveTurnId } = state;
  const recent = [...turns].reverse();
  return (
    <View style={styles.historyRail}>
      <Text style={styles.historySearch}>{product.postQueryWorkspace.railLabel}</Text>
      <View style={styles.historyList}>
        {loading && pendingQuery ? <HistoryItem active label={pendingQuery} meta="running" state={state} /> : null}
        {recent.map((turn, index) => (
          <Pressable key={turn.id} onPress={() => setActiveTurnId(turn.id)} accessibilityRole="button">
            <HistoryItem active={turn.id === activeTurnId} label={turn.query} meta={`Q${String(recent.length - index).padStart(2, "0")}`} state={state} />
          </Pressable>
        ))}
      </View>
      <View style={styles.historyCorpus}>
        <Text style={styles.historyCorpusLabel}>selected</Text>
        <Text style={styles.historyCorpusValue}>{state.answer?.sources?.length || 0}</Text>
      </View>
    </View>
  );
}

function HistoryStrip({ state }: { state: WorkspaceState }) {
  const { turns, styles, activeTurnId, setActiveTurnId } = state;
  if (!turns.length) return null;
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.historyStrip}>
      {[...turns].reverse().map((turn) => (
        <Pressable key={turn.id} onPress={() => setActiveTurnId(turn.id)} style={[styles.historyStripItem, turn.id === activeTurnId && styles.historyStripItemActive]}>
          <Text style={styles.historyStripText} numberOfLines={1}>{turn.query}</Text>
        </Pressable>
      ))}
    </ScrollView>
  );
}

function HistoryItem({ active, label, meta, state }: { active: boolean; label: string; meta: string; state: WorkspaceState }) {
  const { styles } = state;
  return (
    <View style={[styles.historyItem, active && styles.historyItemActive]}>
      <View style={[styles.historyDot, active && styles.historyDotActive]} />
      <Text style={styles.historyItemLabel} numberOfLines={1}>{label}</Text>
      <Text style={styles.historyItemMeta}>{meta}</Text>
    </View>
  );
}

function Beta6Trace({ state }: { state: WorkspaceState }) {
  const { answer, styles } = state;
  const beta6 = answer?.beta6;
  if (!beta6) return null;
  const expanded = beta6.queryStructuring?.expandedFacets || [];
  const verifier = beta6.verifier || {};
  return (
    <View style={styles.beta6Trace}>
      <Text style={styles.beta6TraceLabel}>BETA-6 TRACE</Text>
      <Text style={styles.beta6TraceText}>
        {[
          `${beta6.queryStructuring?.familyCount || beta6.queryFamilies?.length || 0} families`,
          `${Number(verifier.acceptedCount || beta6.selectedCount || 0)} accepted`,
          `${Number(verifier.rejectedCount || beta6.rejectedLedger.length || 0)} rejected`,
          expanded.slice(0, 5).join(" · "),
        ]
          .filter(Boolean)
          .join(" / ")}
      </Text>
    </View>
  );
}

function AnswerPanel({ state, threaded = false }: { state: WorkspaceState; threaded?: boolean }) {
  const { answer, answerView, copy, error, loading, styles } = state;
  return (
    <View style={[styles.answerPanel, threaded && styles.answerPanelThreaded]}>
      <Text style={styles.panelLabel}>{copy.answerLabel}</Text>
      {loading ? <LoadingBars /> : null}
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {!loading && !error && answer && answerView.sections.length ? <AnswerSections state={state} /> : null}
      {!loading && !error && answer && !answerView.sections.length ? <AnswerText markdown={answer.answerMarkdown} /> : null}
      {!loading && !error && !answer ? <Text style={styles.empty}>{copy.emptyAnswer}</Text> : null}
    </View>
  );
}

function SourceRail({ state, compactRail = false }: { state: WorkspaceState; compactRail?: boolean }) {
  const { activeFeatureId, answer, answerView, constrained, copy, featureStates, selectedPassageLabel, setSelectedPassageLabel, styles } = state;
  const maxPassages = constrained ? (compactRail ? 3 : 5) : compactRail ? 4 : 8;
  const activeFeature = featureStates.find((feature) => feature.id === activeFeatureId);
  const scopedLabels = activeFeature?.evidenceLabels || [];
  const visiblePassages = scopedLabels.length
    ? answerView.passages.filter((passage) => scopedLabels.includes(passage.label))
    : answerView.passages;
  const passages = visiblePassages.slice(0, maxPassages);
  const selectedPassage =
    visiblePassages.find((passage) => passage.label === selectedPassageLabel) || passages[0] || answerView.defaultPassage;
  return (
    <View style={[styles.sourcePanel, compactRail && styles.sourcePanelCompact]}>
      <Text style={styles.panelLabel}>{copy.sourcesLabel}</Text>
      {activeFeature ? (
        <Text style={styles.activeFilterText}>
          {activeFeature.title} · {scopedLabels.length ? scopedLabels.join(" ") : "all evidence"}
        </Text>
      ) : null}
      {passages.map((source) => (
        <SourceCard
          key={source.sourceId || source.label}
          source={source}
          active={source.label === selectedPassage?.label}
          onPress={() => setSelectedPassageLabel(source.label)}
          state={state}
        />
      ))}
      {!answer?.sources?.length ? <Text style={styles.empty}>{copy.emptySources}</Text> : null}
      {selectedPassage ? <PassageViewer passage={selectedPassage} state={state} /> : null}
    </View>
  );
}

function DomainMark({ domain }: { domain: DomainKey }) {
  return (
    <View style={[markStyles.mark, domain === "islam" && markStyles.arch, domain === "psychology" && markStyles.round]}>
      <Text style={markStyles.markText}>{domain === "tcm" ? "醫" : domain === "islam" ? "ح" : "m"}</Text>
    </View>
  );
}

function DomainOrnament({ domain }: { domain: DomainKey }) {
  if (domain === "islam") {
    return (
      <>
        <View style={[ornamentStyles.arch, ornamentStyles.big]} />
        <View style={[ornamentStyles.diamond, ornamentStyles.gold]} />
        <View style={[ornamentStyles.diamond, ornamentStyles.jade]} />
      </>
    );
  }
  if (domain === "tcm") {
    return (
      <>
        <View style={[ornamentStyles.ring, ornamentStyles.big]} />
        <View style={[ornamentStyles.ring, ornamentStyles.mid]} />
        <View style={[ornamentStyles.ring, ornamentStyles.small]} />
        <View style={ornamentStyles.seal} />
      </>
    );
  }
  return (
    <>
      <View style={[ornamentStyles.ring, ornamentStyles.big]} />
      <View style={[ornamentStyles.ring, ornamentStyles.mid]} />
      <View style={[ornamentStyles.ring, ornamentStyles.small]} />
    </>
  );
}

function LoadingBars() {
  return (
    <View style={loadingStyles.wrap}>
      <View style={loadingStyles.line} />
      <View style={[loadingStyles.line, { width: "74%" }]} />
      <View style={[loadingStyles.line, { width: "52%" }]} />
    </View>
  );
}

function AnswerText({ markdown }: { markdown: string }) {
  const lines = markdown
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((line) => !line.startsWith("## "));
  return (
    <View>
      {lines.map((line, index) => {
        const isHeading = line.startsWith("### ");
        return (
          <Text key={`${line}-${index}`} style={isHeading ? textStyles.answerHeading : textStyles.answerLine}>
            {line.replace(/^###\s+/, "").replace(/\*\*/g, "")}
          </Text>
        );
      })}
    </View>
  );
}

function AnswerSections({ state }: { state: WorkspaceState }) {
  const { answerView, selectedPassageLabel, setSelectedPassageLabel, styles } = state;
  return (
    <View style={styles.answerSections}>
      {answerView.sections.map((section, index) => (
        <View key={`${section.kind}-${index}`} style={styles.answerSection}>
          <Text style={styles.answerSectionTitle}>{section.title.replace(/^#+\s*/, "")}</Text>
          <Text style={styles.answerSectionBody}>{stripMarkdown(section.body)}</Text>
          {section.citations?.length ? (
            <View style={styles.citationRow}>
              {section.citations.map((label) => (
                <Pressable
                  key={label}
                  accessibilityRole="button"
                  onPress={() => setSelectedPassageLabel(label)}
                  style={[styles.citationChip, selectedPassageLabel === label && styles.citationChipActive]}
                >
                  <Text style={[styles.citationChipText, selectedPassageLabel === label && styles.citationChipTextActive]}>
                    {label}
                  </Text>
                </Pressable>
              ))}
            </View>
          ) : null}
        </View>
      ))}
    </View>
  );
}

type PassageCard = {
  label: string;
  sourceId: string;
  citation: string;
  title: string;
  authorityBody: string;
  topic: string;
  type: string;
  dataset: string;
  score: number;
  verdict: string;
  excerpt: string;
};

function SourceCard({
  source,
  active,
  onPress,
  state,
}: {
  source: PassageCard;
  active: boolean;
  onPress: () => void;
  state: WorkspaceState;
}) {
  const { styles } = state;
  return (
    <Pressable
      onPress={onPress}
      style={[styles.sourceCard, active && styles.sourceCardActive]}
      accessibilityRole="button"
      accessibilityLabel={`${source.label} ${source.citation || source.title || source.sourceId}`}
    >
      <View style={styles.sourceTitleRow}>
        <Text style={styles.sourceLabelBadge}>{source.label}</Text>
        <Text style={styles.sourceTitle}>{source.citation || source.title || source.sourceId}</Text>
      </View>
      <Text style={styles.sourceMeta}>{[source.authorityBody || source.dataset, source.type].filter(Boolean).join(" · ")}</Text>
      <Text style={styles.sourceExcerpt}>{source.excerpt}</Text>
    </Pressable>
  );
}

function PassageViewer({ passage, state }: { passage: PassageCard; state: WorkspaceState }) {
  const { styles } = state;
  return (
    <View style={styles.passageViewer}>
      <View style={styles.sourceTitleRow}>
        <Text style={styles.sourceLabelBadge}>{passage.label}</Text>
        <Text style={styles.passageTitle}>{passage.citation || passage.title || passage.sourceId}</Text>
      </View>
      <Text style={styles.sourceMeta}>
        {[passage.authorityBody || passage.dataset, passage.topic, passage.verdict, `score ${passage.score}`]
          .filter(Boolean)
          .join(" · ")}
      </Text>
      <Text style={styles.passageQuote}>{passage.excerpt}</Text>
    </View>
  );
}

function stripMarkdown(text: string): string {
  return String(text || "")
    .replace(/\*\*/g, "")
    .replace(/\[(S\d+)\]/g, "$1");
}

function createStyles(
  palette: ReturnType<typeof buildDomainPalette>,
  compact: boolean,
  domain: DomainKey,
  direction: "ltr" | "rtl",
) {
  const displayFont = domain === "islam" ? "Palatino" : "Georgia";
  const textAlign = direction === "rtl" ? "right" : "left";
  return StyleSheet.create({
    page: {
      flex: 1,
      backgroundColor: palette.page,
    },
    shell: {
      minHeight: "100%",
      paddingHorizontal: compact ? 16 : 56,
      paddingVertical: compact ? 18 : 28,
      direction,
    },
    stackHeader: {
      flexDirection: "column",
      alignItems: "stretch",
    },
    brand: {
      flexDirection: "row",
      alignItems: "center",
      gap: 13,
    },
    brandName: {
      color: palette.text,
      fontSize: compact ? 23 : 28,
      fontFamily: displayFont,
      fontWeight: "500",
    },
    brandSub: {
      color: palette.muted,
      fontSize: 11,
      letterSpacing: 2,
      marginTop: 3,
    },
    languageRow: {
      flexDirection: "row",
      flexWrap: "wrap",
      gap: 8,
      justifyContent: compact ? "flex-start" : "flex-end",
      maxWidth: compact ? "100%" : 560,
    },
    langPill: {
      borderWidth: 1,
      borderColor: palette.line,
      borderRadius: 999,
      paddingVertical: 7,
      paddingHorizontal: 11,
      minHeight: 34,
    },
    langPillActive: {
      backgroundColor: palette.accent,
      borderColor: palette.accent,
    },
    langText: {
      color: palette.muted,
      fontSize: 11,
      fontWeight: "700",
    },
    langTextActive: {
      color: palette.colorScheme === "dark" ? palette.page : "#fffdf6",
    },
    islamNav: {
      borderBottomWidth: 1,
      borderColor: palette.line,
      paddingBottom: 22,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 18,
    },
    islamNavLinks: {
      flexDirection: "row",
      gap: 34,
    },
    navText: {
      color: palette.muted,
      fontSize: 12,
      letterSpacing: 2,
      fontWeight: "600",
    },
    islamHero: {
      alignItems: "center",
      paddingVertical: compact ? 42 : 70,
      position: "relative",
      overflow: "hidden",
    },
    islamOrnament: {
      position: "absolute",
      top: compact ? 36 : 58,
      width: compact ? 250 : 330,
      height: compact ? 250 : 330,
      opacity: 0.42,
      alignItems: "center",
      justifyContent: "center",
    },
    islamEyebrow: {
      color: palette.accent,
      fontSize: 12,
      letterSpacing: 3,
      fontWeight: "700",
      textTransform: "uppercase",
      marginBottom: 24,
      textAlign: "center",
    },
    islamHeadline: {
      color: palette.text,
      fontSize: compact ? 48 : 84,
      lineHeight: compact ? 54 : 88,
      fontFamily: displayFont,
      fontWeight: "300",
      textAlign: "center",
      zIndex: 1,
    },
    islamHeadlineAccent: {
      color: palette.accent,
      fontStyle: "italic",
    },
    islamArabic: {
      color: palette.accent,
      fontSize: compact ? 26 : 34,
      fontFamily: "Palatino",
      marginTop: 10,
      writingDirection: "rtl",
      textAlign: "center",
      zIndex: 1,
    },
    islamSubline: {
      color: palette.muted,
      fontSize: compact ? 16 : 18,
      lineHeight: compact ? 23 : 27,
      marginTop: 18,
      marginBottom: 22,
      maxWidth: 640,
      textAlign: "center",
    },
    islamThread: {
      maxWidth: 920,
      width: "100%",
      alignSelf: "center",
      paddingBottom: 46,
      gap: 18,
    },
    threadDivider: {
      flexDirection: "row",
      alignItems: "center",
      gap: 16,
      marginBottom: 6,
    },
    threadLine: {
      flex: 1,
      height: 1,
      backgroundColor: palette.line,
    },
    tcmTopbar: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 18,
      paddingBottom: 22,
    },
    tcmNavLinks: {
      flexDirection: "row",
      gap: 28,
    },
    tcmNavText: {
      color: palette.text,
      fontSize: 13,
      fontWeight: "600",
    },
    tcmHero: {
      minHeight: compact ? undefined : 560,
      flexDirection: "row",
      alignItems: "center",
      gap: 46,
      paddingVertical: compact ? 24 : 44,
    },
    tcmHeroCompact: {
      flexDirection: "column",
      alignItems: "stretch",
    },
    tcmHeroCopy: {
      flex: 1,
      minWidth: 0,
    },
    tcmEyebrow: {
      color: palette.accent,
      fontSize: 12,
      letterSpacing: 2,
      fontWeight: "700",
      marginBottom: 20,
      textTransform: "uppercase",
      textAlign,
    },
    tcmHeadline: {
      color: palette.text,
      fontSize: compact ? 44 : 66,
      lineHeight: compact ? 51 : 72,
      fontFamily: "Georgia",
      fontWeight: "400",
      maxWidth: 720,
      textAlign,
    },
    tcmSubline: {
      color: palette.muted,
      fontSize: compact ? 17 : 22,
      lineHeight: compact ? 25 : 31,
      marginTop: 18,
      maxWidth: 640,
      textAlign,
    },
    tcmMandala: {
      width: compact ? "100%" : 410,
      minHeight: compact ? 280 : 410,
      alignItems: "center",
      justifyContent: "center",
    },
    tcmGlyph: {
      color: palette.text,
      fontFamily: "Georgia",
      fontSize: 88,
      fontWeight: "300",
    },
    cornerTag: {
      position: "absolute",
      color: palette.muted,
      fontSize: 10,
      letterSpacing: 2,
      lineHeight: 15,
    },
    cornerTopLeft: { top: 10, left: 10 },
    cornerTopRight: { top: 10, right: 10, textAlign: "right" },
    cornerBottomLeft: { bottom: 10, left: 10 },
    cornerBottomRight: { bottom: 10, right: 10, textAlign: "right" },
    consultPanel: {
      borderWidth: 1,
      borderColor: palette.text,
      backgroundColor: palette.surface,
      flexDirection: "row",
      minHeight: 520,
      marginBottom: 48,
    },
    consultPanelCompact: {
      flexDirection: "column",
    },
    consultAside: {
      width: compact ? "100%" : 320,
      borderRightWidth: compact ? 0 : 1,
      borderBottomWidth: compact ? 1 : 0,
      borderColor: palette.line,
      backgroundColor: palette.surfaceAlt,
      padding: 24,
      gap: 20,
    },
    doctorRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: 14,
      paddingBottom: 18,
      borderBottomWidth: 1,
      borderColor: palette.line,
    },
    doctorAvatar: {
      width: 52,
      height: 52,
      borderRadius: 999,
      backgroundColor: palette.text,
      alignItems: "center",
      justifyContent: "center",
    },
    doctorAvatarText: {
      color: palette.page,
      fontSize: 22,
      fontFamily: "Georgia",
    },
    doctorName: {
      color: palette.text,
      fontFamily: "Georgia",
      fontSize: 18,
    },
    doctorRole: {
      color: palette.muted,
      fontSize: 11,
      letterSpacing: 2,
      marginTop: 2,
    },
    asideHeading: {
      color: palette.muted,
      fontSize: 12,
      letterSpacing: 2,
      fontWeight: "800",
    },
    consultMain: {
      flex: 1,
      minWidth: 0,
    },
    consultHead: {
      padding: 22,
      borderBottomWidth: 1,
      borderColor: palette.line,
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 12,
    },
    consultTitle: {
      color: palette.text,
      fontFamily: "Georgia",
      fontSize: 20,
    },
    consultMeta: {
      color: palette.muted,
      fontSize: 11,
      letterSpacing: 2,
    },
    psychStage: {
      minHeight: compact ? undefined : 720,
      paddingBottom: 44,
    },
    psychHeader: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 18,
      marginBottom: compact ? 28 : 58,
    },
    psychRingLarge: {
      position: "absolute",
      top: compact ? 120 : 90,
      right: compact ? -90 : 80,
      width: compact ? 260 : 420,
      height: compact ? 260 : 420,
      borderRadius: 999,
      borderWidth: 1,
      borderColor: palette.line,
    },
    psychRingSmall: {
      position: "absolute",
      top: compact ? 170 : 180,
      right: compact ? -20 : 190,
      width: compact ? 120 : 180,
      height: compact ? 120 : 180,
      borderRadius: 999,
      borderWidth: 1,
      borderColor: palette.accentAlt,
      opacity: 0.45,
    },
    psychGrid: {
      flexDirection: "row",
      gap: 28,
      alignItems: "flex-start",
    },
    psychGridCompact: {
      flexDirection: "column",
    },
    psychMain: {
      flex: 1,
      minWidth: 0,
      maxWidth: 780,
    },
    psychRail: {
      width: compact ? "100%" : 340,
      borderLeftWidth: compact ? 0 : 1,
      borderTopWidth: compact ? 1 : 0,
      borderColor: palette.line,
      paddingLeft: compact ? 0 : 24,
      paddingTop: compact ? 20 : 0,
      gap: 16,
    },
    psychEyebrow: {
      color: palette.accent,
      fontSize: 12,
      letterSpacing: 2,
      fontWeight: "800",
      marginBottom: 18,
      textTransform: "uppercase",
      textAlign,
    },
    psychHeadline: {
      color: palette.text,
      fontFamily: "Georgia",
      fontSize: compact ? 40 : 62,
      lineHeight: compact ? 48 : 70,
      fontWeight: "400",
      maxWidth: 680,
      textAlign,
    },
    psychSubline: {
      color: palette.muted,
      fontSize: compact ? 16 : 20,
      lineHeight: compact ? 24 : 30,
      marginTop: 18,
      maxWidth: 620,
      textAlign,
    },
    railKicker: {
      color: palette.accent,
      fontSize: 12,
      fontWeight: "800",
      letterSpacing: 2,
      textTransform: "uppercase",
    },
    softDivider: {
      height: 1,
      backgroundColor: palette.line,
      marginVertical: 4,
    },
    queryBox: {
      marginTop: 26,
      borderWidth: 1,
      borderColor: palette.line,
      backgroundColor: palette.surface,
      borderRadius: palette.radius,
      padding: compact ? 16 : 22,
      maxWidth: 760,
      width: "100%",
    },
    queryBoxIslam: {
      maxWidth: 880,
      backgroundColor: palette.surface,
      borderColor: palette.accent,
    },
    queryBoxTcm: {
      borderColor: palette.line,
      borderRadius: 4,
    },
    queryLabelRow: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 12,
      marginBottom: 10,
    },
    queryLabel: {
      color: palette.accent,
      fontSize: 12,
      letterSpacing: 2,
      fontWeight: "800",
      textTransform: "uppercase",
    },
    queryMode: {
      color: palette.muted,
      fontSize: 11,
      letterSpacing: 1,
    },
    input: {
      minHeight: 86,
      color: palette.text,
      fontSize: 18,
      lineHeight: 26,
      textAlignVertical: "top",
      textAlign,
      writingDirection: direction,
    },
    queryToolbar: {
      flexDirection: compact ? "column" : "row",
      alignItems: compact ? "stretch" : "center",
      justifyContent: "space-between",
      gap: 14,
      borderTopWidth: 1,
      borderColor: palette.line,
      paddingTop: 14,
      marginTop: 10,
    },
    queryHint: {
      flex: 1,
      color: palette.muted,
      fontSize: 12,
      lineHeight: 18,
    },
    sendButton: {
      backgroundColor: palette.accent,
      borderRadius: domain === "tcm" ? 999 : palette.radius,
      minHeight: 42,
      paddingVertical: 10,
      paddingHorizontal: 22,
      alignItems: "center",
      justifyContent: "center",
    },
    sendText: {
      color: palette.colorScheme === "dark" ? palette.page : "#fffdf6",
      fontWeight: "800",
    },
    exampleWrap: {
      flexDirection: "row",
      flexWrap: "wrap",
      alignItems: "center",
      gap: 9,
      marginTop: 14,
      maxWidth: 840,
    },
    exampleWrapCentered: {
      justifyContent: "center",
    },
    exampleLabel: {
      color: palette.muted,
      fontSize: 11,
      letterSpacing: 2,
      fontWeight: "700",
      textTransform: "uppercase",
      marginRight: 4,
    },
    example: {
      borderWidth: 1,
      borderColor: palette.line,
      backgroundColor: palette.surfaceAlt,
      borderRadius: 999,
      paddingVertical: 8,
      paddingHorizontal: 12,
    },
    exampleText: {
      color: palette.text,
      fontSize: 13,
      fontWeight: "600",
    },
    answerPanel: {
      borderWidth: 1,
      borderColor: palette.line,
      backgroundColor: palette.surface,
      borderRadius: palette.radius,
      padding: compact ? 18 : 22,
      marginTop: 18,
    },
    answerPanelThreaded: {
      marginTop: 0,
      borderRadius: domain === "tcm" ? 0 : palette.radius,
    },
    answerSections: {
      gap: 16,
    },
    answerSection: {
      borderTopWidth: 1,
      borderColor: palette.line,
      paddingTop: 14,
    },
    answerSectionTitle: {
      color: palette.text,
      fontFamily: displayFont,
      fontSize: compact ? 18 : 21,
      lineHeight: compact ? 24 : 28,
      fontWeight: "700",
      textAlign,
      marginBottom: 8,
    },
    answerSectionBody: {
      color: palette.text,
      fontSize: compact ? 15 : 16,
      lineHeight: compact ? 23 : 25,
      textAlign,
    },
    citationRow: {
      flexDirection: "row",
      flexWrap: "wrap",
      gap: 8,
      marginTop: 10,
    },
    citationChip: {
      borderWidth: 1,
      borderColor: palette.line,
      borderRadius: 999,
      paddingVertical: 6,
      paddingHorizontal: 10,
      backgroundColor: palette.surfaceAlt,
    },
    citationChipActive: {
      backgroundColor: palette.accent,
      borderColor: palette.accent,
    },
    citationChipText: {
      color: palette.text,
      fontSize: 12,
      fontWeight: "800",
    },
    citationChipTextActive: {
      color: palette.colorScheme === "dark" ? palette.page : "#fffdf6",
    },
    sourcePanel: {
      borderWidth: 1,
      borderColor: palette.line,
      backgroundColor: palette.surface,
      borderRadius: palette.radius,
      padding: compact ? 16 : 18,
      marginTop: 18,
    },
    sourcePanelCompact: {
      borderWidth: 0,
      backgroundColor: "transparent",
      padding: 0,
      marginTop: 0,
    },
    featurePanel: {
      width: "100%",
      maxWidth: 880,
      marginTop: 18,
      borderWidth: domain === "tcm" ? 1 : 0,
      borderColor: palette.line,
      backgroundColor: domain === "islam" ? "rgba(10,19,32,0.34)" : "transparent",
      padding: domain === "tcm" ? 12 : 0,
    },
    featurePanelCompact: {
      maxWidth: "100%",
      marginTop: 12,
      borderWidth: 0,
      backgroundColor: "transparent",
      padding: 0,
    },
    featureGrid: {
      flexDirection: "row",
      flexWrap: "wrap",
      gap: 8,
    },
    featureCard: {
      flexGrow: 1,
      flexBasis: compact ? "100%" : domain === "islam" ? "22%" : "46%",
      minWidth: compact ? "100%" : 148,
      borderWidth: 1,
      borderColor: palette.line,
      backgroundColor:
        domain === "islam"
          ? "rgba(13,43,52,0.78)"
          : domain === "tcm"
            ? "rgba(255,253,246,0.72)"
            : "rgba(255,253,248,0.62)",
      borderRadius: domain === "tcm" ? 2 : palette.radius,
      padding: 12,
    },
    featureCardWatch: {
      borderColor: palette.accent,
    },
    featureCardActive: {
      borderColor: palette.accent,
      backgroundColor:
        domain === "islam"
          ? "rgba(201,168,107,0.16)"
          : domain === "tcm"
            ? "rgba(182,84,58,0.12)"
            : "rgba(161,74,43,0.10)",
    },
    featureHead: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "space-between",
      gap: 8,
      marginBottom: 8,
    },
    featureKicker: {
      flex: 1,
      color: palette.muted,
      fontSize: 10,
      lineHeight: 14,
      letterSpacing: 1,
      textTransform: "uppercase",
    },
    featureStatus: {
      color: palette.muted,
      borderWidth: 1,
      borderColor: palette.line,
      paddingVertical: 2,
      paddingHorizontal: 6,
      fontSize: 10,
      fontWeight: "800",
      textTransform: "uppercase",
    },
    featureStatusActive: {
      color: palette.colorScheme === "dark" ? palette.page : "#fffdf6",
      backgroundColor: palette.accent,
      borderColor: palette.accent,
    },
    featureStatusWatch: {
      color: palette.colorScheme === "dark" ? palette.page : "#fffdf6",
      backgroundColor: palette.accent,
      borderColor: palette.accent,
    },
    featureTitle: {
      color: palette.text,
      fontFamily: displayFont,
      fontSize: 16,
      lineHeight: 21,
      fontWeight: "700",
      textAlign,
    },
    featureDetail: {
      color: palette.muted,
      fontSize: 12,
      lineHeight: 18,
      marginTop: 6,
      textAlign,
    },
    featureEvidenceRow: {
      flexDirection: "row",
      flexWrap: "wrap",
      gap: 6,
      marginTop: 9,
    },
    featureEvidenceChip: {
      borderWidth: 1,
      borderColor: palette.line,
      backgroundColor: domain === "islam" ? palette.page : palette.surfaceAlt,
      borderRadius: 999,
      paddingVertical: 3,
      paddingHorizontal: 8,
    },
    featureEvidenceText: {
      color: palette.text,
      fontSize: 11,
      fontWeight: "900",
    },
    chatShell: {
      minHeight: compact ? undefined : 680,
      marginTop: compact ? 22 : 34,
      marginBottom: 44,
      borderWidth: 1,
      borderColor: domain === "tcm" ? palette.text : palette.line,
      backgroundColor: domain === "psychology" ? "rgba(255,253,248,0.72)" : palette.surface,
      flexDirection: "row",
      overflow: "hidden",
    },
    chatShellCompact: {
      flexDirection: "column",
      minHeight: undefined,
    },
    historyRail: {
      width: 248,
      borderRightWidth: 1,
      borderColor: palette.line,
      backgroundColor: domain === "islam" ? palette.page : palette.surfaceAlt,
      padding: 14,
      gap: 12,
    },
    historySearch: {
      borderWidth: 1,
      borderColor: palette.line,
      color: palette.muted,
      backgroundColor: domain === "islam" ? palette.surface : palette.surface,
      paddingVertical: 9,
      paddingHorizontal: 11,
      fontSize: 12,
      letterSpacing: 2,
      textTransform: "uppercase",
      fontWeight: "800",
    },
    historyList: {
      gap: 2,
    },
    historyItem: {
      minHeight: 38,
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      paddingVertical: 8,
      paddingHorizontal: 8,
      backgroundColor: "transparent",
    },
    historyItemActive: {
      backgroundColor: domain === "islam" ? "rgba(201,168,107,0.11)" : "rgba(28,26,23,0.06)",
    },
    historyDot: {
      width: 5,
      height: 5,
      backgroundColor: palette.muted,
    },
    historyDotActive: {
      backgroundColor: palette.accent,
    },
    historyItemLabel: {
      flex: 1,
      minWidth: 0,
      color: palette.text,
      fontSize: 13,
      lineHeight: 18,
    },
    historyItemMeta: {
      color: palette.muted,
      fontSize: 11,
      fontWeight: "700",
    },
    historyCorpus: {
      marginTop: "auto",
      borderTopWidth: 1,
      borderColor: palette.line,
      paddingTop: 12,
      flexDirection: "row",
      justifyContent: "space-between",
    },
    historyCorpusLabel: {
      color: palette.muted,
      fontSize: 11,
      letterSpacing: 2,
      textTransform: "uppercase",
    },
    historyCorpusValue: {
      color: palette.text,
      fontSize: 13,
      fontWeight: "800",
    },
    historyStrip: {
      borderBottomWidth: 1,
      borderColor: palette.line,
      backgroundColor: domain === "islam" ? palette.page : palette.surfaceAlt,
      maxHeight: 48,
    },
    historyStripItem: {
      maxWidth: 220,
      paddingVertical: 10,
      paddingHorizontal: 12,
      borderRightWidth: 1,
      borderColor: palette.line,
    },
    historyStripItemActive: {
      backgroundColor: domain === "islam" ? "rgba(201,168,107,0.11)" : "rgba(28,26,23,0.06)",
    },
    historyStripText: {
      color: palette.text,
      fontSize: 13,
    },
    chatMain: {
      flex: 1,
      minWidth: 0,
      backgroundColor: domain === "islam" ? palette.surface : palette.surface,
    },
    chatCrumbs: {
      minHeight: 48,
      borderBottomWidth: 1,
      borderColor: palette.line,
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      paddingHorizontal: compact ? 14 : 20,
    },
    chatCrumbPill: {
      color: palette.text,
      borderWidth: 1,
      borderColor: palette.line,
      paddingVertical: 4,
      paddingHorizontal: 8,
      fontSize: 12,
      backgroundColor: domain === "islam" ? palette.page : palette.surfaceAlt,
    },
    chatCrumbSep: {
      color: palette.muted,
      fontSize: 12,
    },
    chatCrumbHere: {
      flex: 1,
      color: palette.muted,
      fontSize: 13,
    },
    chatThread: {
      maxWidth: 780,
      width: "100%",
      alignSelf: "center",
      paddingHorizontal: compact ? 16 : 34,
      paddingVertical: compact ? 22 : 34,
      gap: 30,
    },
    userTurn: {
      flexDirection: "row",
      gap: 16,
      alignItems: "flex-start",
    },
    userMark: {
      width: 8,
      height: 8,
      backgroundColor: palette.text,
      marginTop: 11,
    },
    userTurnBody: {
      flex: 1,
      minWidth: 0,
      borderBottomWidth: 1,
      borderColor: palette.line,
      paddingBottom: 14,
    },
    questionNumber: {
      color: palette.muted,
      fontSize: 11,
      fontWeight: "800",
      letterSpacing: 1,
      marginBottom: 5,
    },
    questionTitle: {
      color: palette.text,
      fontFamily: displayFont,
      fontSize: compact ? 21 : 27,
      lineHeight: compact ? 28 : 35,
      fontWeight: "600",
      textAlign,
    },
    questionMeta: {
      color: palette.muted,
      fontSize: 12,
      marginTop: 8,
      letterSpacing: 1,
      textAlign,
    },
    assistantTurn: {
      flexDirection: "row",
      gap: 16,
      alignItems: "stretch",
    },
    assistantRule: {
      width: 1,
      backgroundColor: palette.line,
      marginHorizontal: 3,
    },
    assistantBody: {
      flex: 1,
      minWidth: 0,
    },
    chatEvidence: {
      width: compact ? "100%" : 360,
      borderLeftWidth: compact ? 0 : 1,
      borderTopWidth: compact ? 1 : 0,
      borderColor: palette.line,
      backgroundColor: domain === "islam" ? palette.page : palette.surfaceAlt,
      padding: compact ? 14 : 16,
    },
    evidenceHead: {
      flexDirection: "row",
      alignItems: "center",
      gap: 10,
      paddingBottom: 12,
      borderBottomWidth: 1,
      borderColor: palette.line,
      marginBottom: 2,
    },
    evidenceTitle: {
      color: palette.text,
      fontSize: 12,
      letterSpacing: 2,
      textTransform: "uppercase",
      fontWeight: "800",
    },
    evidenceCount: {
      color: palette.muted,
      borderWidth: 1,
      borderColor: palette.line,
      paddingHorizontal: 7,
      paddingVertical: 2,
      fontSize: 11,
      fontWeight: "800",
    },
    activeFilterText: {
      color: palette.muted,
      fontSize: 12,
      lineHeight: 18,
      marginTop: -8,
      marginBottom: 8,
      textAlign,
    },
    beta6Trace: {
      borderTopWidth: 1,
      borderColor: palette.line,
      paddingTop: 12,
      marginTop: 12,
    },
    beta6TraceLabel: {
      color: palette.accent,
      fontSize: 11,
      letterSpacing: 2,
      fontWeight: "900",
      marginBottom: 5,
    },
    beta6TraceText: {
      color: palette.muted,
      fontSize: 12,
      lineHeight: 18,
    },
    sourceCard: {
      borderTopWidth: 1,
      borderColor: palette.line,
      paddingVertical: 12,
      gap: 6,
    },
    sourceCardActive: {
      backgroundColor: domain === "islam" ? "rgba(201,168,107,0.11)" : "rgba(182,84,58,0.08)",
      paddingHorizontal: 10,
      marginHorizontal: -10,
    },
    sourceTitleRow: {
      flexDirection: "row",
      alignItems: "center",
      gap: 8,
      minWidth: 0,
    },
    sourceLabelBadge: {
      color: palette.colorScheme === "dark" ? palette.page : "#fffdf6",
      backgroundColor: palette.accent,
      borderRadius: 999,
      overflow: "hidden",
      paddingHorizontal: 8,
      paddingVertical: 3,
      fontSize: 11,
      fontWeight: "900",
    },
    sourceTitle: {
      flex: 1,
      color: palette.text,
      fontSize: 14,
      fontWeight: "800",
      lineHeight: 20,
      textAlign,
    },
    sourceMeta: {
      color: palette.muted,
      fontSize: 12,
      lineHeight: 17,
      textAlign,
    },
    sourceExcerpt: {
      color: palette.muted,
      fontSize: 13,
      lineHeight: 19,
      textAlign,
    },
    passageViewer: {
      borderTopWidth: 1,
      borderColor: palette.line,
      marginTop: 14,
      paddingTop: 14,
      gap: 8,
    },
    passageTitle: {
      flex: 1,
      color: palette.text,
      fontFamily: displayFont,
      fontSize: 17,
      lineHeight: 23,
      fontWeight: "700",
      textAlign,
    },
    passageQuote: {
      color: palette.text,
      fontSize: 14,
      lineHeight: 22,
      borderLeftWidth: direction === "rtl" ? 0 : 3,
      borderRightWidth: direction === "rtl" ? 3 : 0,
      borderColor: palette.accent,
      paddingLeft: direction === "rtl" ? 0 : 12,
      paddingRight: direction === "rtl" ? 12 : 0,
      textAlign,
    },
    panelLabel: {
      color: palette.accent,
      letterSpacing: 2,
      fontSize: 11,
      fontWeight: "800",
      textTransform: "uppercase",
      marginBottom: 14,
      textAlign,
    },
    safetyText: {
      color: palette.muted,
      fontSize: 13,
      lineHeight: 20,
      textAlign,
    },
    empty: {
      color: palette.muted,
      fontSize: 14,
      lineHeight: 21,
      textAlign,
    },
    error: {
      color: palette.accent,
      fontSize: 13,
      lineHeight: 20,
      textAlign,
    },
  });
}

const markStyles = StyleSheet.create({
  mark: {
    width: 42,
    height: 42,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "rgba(128,128,128,0.35)",
    alignItems: "center",
    justifyContent: "center",
  },
  arch: {
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
  },
  round: {
    borderRadius: 999,
  },
  markText: {
    fontFamily: "Georgia",
    fontWeight: "700",
    fontSize: 21,
  },
});

const ornamentStyles = StyleSheet.create({
  ring: {
    position: "absolute",
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "rgba(128,128,128,0.35)",
  },
  arch: {
    position: "absolute",
    borderWidth: 1,
    borderColor: "rgba(201,168,107,0.46)",
    borderTopLeftRadius: 180,
    borderTopRightRadius: 180,
    borderBottomLeftRadius: 18,
    borderBottomRightRadius: 18,
  },
  big: {
    width: 260,
    height: 260,
  },
  mid: {
    width: 178,
    height: 178,
  },
  small: {
    width: 92,
    height: 92,
  },
  diamond: {
    position: "absolute",
    width: 145,
    height: 145,
    borderWidth: 1,
    transform: [{ rotate: "45deg" }],
  },
  gold: {
    borderColor: "rgba(201,168,107,0.62)",
  },
  jade: {
    width: 96,
    height: 96,
    borderColor: "rgba(74,138,123,0.58)",
  },
  seal: {
    position: "absolute",
    width: 72,
    height: 72,
    borderRadius: 16,
    borderWidth: 2,
    borderColor: "#b6543a",
    transform: [{ rotate: "12deg" }],
  },
});

const loadingStyles = StyleSheet.create({
  wrap: {
    gap: 8,
  },
  line: {
    height: 9,
    width: "92%",
    borderRadius: 999,
    backgroundColor: "rgba(128,128,128,0.22)",
  },
});

const textStyles = StyleSheet.create({
  answerHeading: {
    fontSize: 18,
    fontWeight: "800",
    marginTop: 12,
    marginBottom: 4,
    lineHeight: 24,
  },
  answerLine: {
    fontSize: 15,
    lineHeight: 24,
    marginBottom: 8,
  },
  sourceCard: {
    borderTopWidth: 1,
    borderColor: "rgba(128,128,128,0.24)",
    paddingVertical: 12,
  },
  sourceTitle: {
    fontSize: 14,
    fontWeight: "800",
    lineHeight: 20,
  },
  sourceMeta: {
    fontSize: 12,
    opacity: 0.7,
    marginTop: 2,
  },
  sourceExcerpt: {
    fontSize: 13,
    lineHeight: 19,
    marginTop: 7,
  },
});
