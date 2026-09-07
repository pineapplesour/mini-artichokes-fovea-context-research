import { startTransition, useEffect, useMemo, useRef, useState } from "react";
import { Animated, Image, Linking, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, useWindowDimensions, View } from "react-native";
import { useLocalSearchParams } from "expo-router";

import { theme } from "../../constants/theme";
import { workspaceModes } from "../../constants/mock-run";
import {
  classifyIntent,
  getJobStatus,
  listJobs,
  preflightDocument,
  uploadSampleFile,
  type ClaimRecord,
  type DocumentConversationItem,
  type DocumentPreset,
} from "../../lib/api";
import {
  buildDocumentDraftRequest,
  buildFallbackDocumentPreflight,
  inferDocumentPresetIdFromPrompt,
  resolvePromptSubmitMode,
  shouldStartDocumentSetup,
} from "../../lib/document-flow";
import {
  buildDocumentConversationItems,
  buildPendingLoaderHeadline,
  buildPendingLoaderState,
  buildQuestionConversationTurns,
  composeQuestionAnswerMarkdown,
  resolveConversationMode,
  shouldShowDocumentResultCard,
  shouldShowSeparateAnalysisSummaryCard,
  shouldSubmitComposerKey,
  shouldShowDocumentConfigurator,
  shouldShowRunLoader,
  shouldUseStatusForPendingLoader,
  type PendingTurn,
} from "../../lib/conversation-pending";
import { isConstrainedClient } from "../../lib/performance-mode";
import {
  clearSessionSnapshot,
  filterVisibleHistory,
  findSessionPrompt,
  getBrowserClientId,
  isRestorableJobState,
  isSessionDeleted,
  loadDeletedSessionIds,
  loadResultSnapshot,
  loadResultSnapshotAsync,
  loadStatusSnapshot,
  loadStatusSnapshotAsync,
  markSessionDeleted,
  normalizeDraftState,
  pruneEmbeddedSourceSessionHistory,
  loadSessionSnapshot,
  saveResultSnapshot,
  saveResultSnapshotAsync,
  saveStatusSnapshot,
  saveStatusSnapshotAsync,
  saveViewedSessionId,
  saveSessionSnapshot,
  shouldPersistLastSession,
  shouldSkipSourceDocumentHistoryUpdate,
  upsertContinuationSessionHistory,
  VIEWED_SESSION_STORAGE_KEY,
  type SessionHistoryItem,
  upsertSessionHistory,
} from "../../lib/session-history";
import { LawkeyLogo } from "./lawkey-logo";
import { useLawkeyJob } from "../../lib/use-lawkey-job";
import { MarkdownView } from "./markdown-view";
import { PrecedentDrawer } from "./precedent-drawer";
import { ProgressStrip } from "./progress-strip";
import { formatTotalElapsedLabel } from "../../lib/run-progress";
import { isPresentationAuthValid, loadAuthState, persistAuthState } from "../../lib/auth-gate";
import {
  getAnalysisModeLabel,
  getVisibleAnalysisModeOptions,
  normalizeAnalysisModeForRole,
  type VisibleAnalysisMode,
} from "../../lib/analysis-mode";
import { resolveLoginButtonPress } from "../../lib/login-trigger";
import { LoginButton } from "../login-button";
import {
  ADMIN_REPLAY_STAGES,
  editAdminReplayAnswer,
  loadAdminReplaySnapshot,
  runAdminReplay,
  saveAdminReplaySnapshot,
  type AdminReplaySnapshot,
} from "../../lib/admin-replay";
import {
  DEMO_JOB_ID,
  DEMO_PROMPT,
  DEMO_SLIDES,
  DEMO_STAGES,
  buildTypingFrames,
  loadDemoSnapshot,
} from "../../lib/demo-flow";
import { slugifyHeading } from "./markdown-view";

const LEGACY_HISTORY_STORAGE_KEY = "lawkey-history-v3";
const HISTORY_STORAGE_KEY_PREFIX = "lawkey-history-v4";
const DRAFT_STORAGE_KEY = "lawkey-draft-v2";
const LAST_SESSION_STORAGE_KEY = "lawkey-last-session-v2";
const aiBubbleDataProps = Platform.OS === "web" ? ({ dataSet: { aiBubble: "1" } } as any) : {};
const webTextInputFocusReset =
  Platform.OS === "web"
    ? ({
        outlineColor: "transparent",
        outlineStyle: "none",
        outlineWidth: 0,
      } as any)
    : null;

type PendingDocumentSetup = {
  id: string;
  prompt: string;
  conversation: DocumentConversationItem[];
  sourceJobId: string;
};

type PendingConversationScrollTarget = "bottom" | "latestAnswerStart";

const DOCUMENT_SETUP_MESSAGE =
  "네, 알겠습니다. 문서 작성으로 이어가겠습니다.\n\n프리셋을 선택해주세요. 직접 쓰려는 양식이 있으면 파일을 업로드해도 됩니다.";

function historyStorageKey(clientId: string): string {
  const clean = clientId.trim();
  return clean ? `${HISTORY_STORAGE_KEY_PREFIX}:${clean}` : HISTORY_STORAGE_KEY_PREFIX;
}

function readTabStorage(key: string): string {
  if (typeof window === "undefined") {
    return "";
  }
  try {
    // Prefer per-tab sessionStorage (keeps different tabs isolated), but
    // fall back to localStorage so that closing and reopening the tab or the
    // browser still recovers the last active job / draft.
    const sess = window.sessionStorage?.getItem(key);
    if (sess) return sess;
    return window.localStorage?.getItem(key) || "";
  } catch {
    return "";
  }
}

function writeTabStorage(key: string, value: string): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    if (value) {
      window.sessionStorage?.setItem(key, value);
      // Mirror into localStorage so refreshing via new tab / browser restart
      // still restores the session instead of wiping the chat.
      window.localStorage?.setItem(key, value);
    } else {
      window.sessionStorage?.removeItem(key);
      window.localStorage?.removeItem(key);
    }
  } catch {
    // Ignore browser storage errors.
  }
}

export function LawkeyWorkspace() {
  const { width } = useWindowDimensions();
  const constrained = isConstrainedClient();
  const compact = width < 900;
  const routeParams = useLocalSearchParams<{ id?: string }>();
  const routeJobId = typeof routeParams.id === "string" ? routeParams.id : "";
  const [isAdmin, setIsAdmin] = useState(() => loadAuthState());
  const [loginDialogOpen, setLoginDialogOpen] = useState(false);
  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const loginLastPressAtRef = useRef(0);
  const loginOpenTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [mode, setMode] = useState<"question" | "document">("question");
  const [analysisMode, setAnalysisModeState] = useState<VisibleAnalysisMode>(() => {
    if (typeof window === "undefined") return normalizeAnalysisModeForRole("", false);
    try {
      const raw = window.localStorage.getItem("lawkey-analysis-mode-v1");
      return normalizeAnalysisModeForRole(raw || "", loadAuthState());
    } catch {
      return normalizeAnalysisModeForRole("", false);
    }
  });
  const [modeMenuOpen, setModeMenuOpen] = useState(false);
  // Tracks whether the user has manually picked an analysis mode since this
  // page mount. Used to suppress the "sync from active job" effect once the
  // user has expressed an explicit preference for the next request.
  const userTouchedAnalysisModeRef = useRef(false);
  const setAnalysisMode = (next: VisibleAnalysisMode) => {
    const normalized = normalizeAnalysisModeForRole(next, isAdmin);
    userTouchedAnalysisModeRef.current = true;
    setAnalysisModeState(normalized);
    try {
      window.localStorage?.setItem("lawkey-analysis-mode-v1", normalized);
    } catch {
      /* ignore */
    }
  };
  const [prompt, setPrompt] = useState("");
  const [samplePath, setSamplePath] = useState("");
  const [documentPresetId, setDocumentPresetId] = useState("");
  const [useCustomSamplePath, setUseCustomSamplePath] = useState(false);
  const [uploadedSampleLabel, setUploadedSampleLabel] = useState("");
  const [headlineIndex, setHeadlineIndex] = useState(0);
  const [submittedPrompt, setSubmittedPrompt] = useState("");
  const [questionMessages, setQuestionMessages] = useState<Array<{ role: "user"; text: string }>>([]);
  const [documentMessages, setDocumentMessages] = useState<DocumentConversationItem[]>([]);
  const [pendingTurn, setPendingTurn] = useState<PendingTurn | null>(null);
  const [composerSendsNewRequest, setComposerSendsNewRequest] = useState(false);
  const [pendingDocumentSetup, setPendingDocumentSetup] = useState<PendingDocumentSetup | null>(null);
  const [documentPresetConfirmed, setDocumentPresetConfirmed] = useState(false);
  const [continuationSourceJobId, setContinuationSourceJobId] = useState("");
  const [carriedQuestionAnswer, setCarriedQuestionAnswer] = useState<{
    sourceJobId: string;
    markdown: string;
    // Capture the precedents that belonged to the previous answer so that
    // the hyperlinks embedded in the earlier assistant bubble still resolve
    // after a follow-up swaps `result` to a new job's selection.
    selectedPrecedents?: Array<{ precedentId: string; caseNumber?: string; alternatePrecedentIds?: string[] }>;
  } | null>(null);
  const [history, setHistory] = useState<SessionHistoryItem[]>([]);
  const [storageHydrated, setStorageHydrated] = useState(false);
  const [browserClientId, setBrowserClientId] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [precedentsExpanded, setPrecedentsExpanded] = useState(false);
  const [targetQuoteText, setTargetQuoteText] = useState("");
  const filePickerBusy = useRef(false);
  const conversationScrollRef = useRef<ScrollView | null>(null);
  const lastScrollYRef = useRef(0);
  const lastContentHeightRef = useRef(0);
  const lastViewportHeightRef = useRef(0);
  // True when the user has scrolled away from the bottom of the chat. Auto-
  // scroll on new content is suppressed in that state so reading the question
  // mid-stream isn't yanked to the bottom by an arriving answer.
  const userScrolledAwayRef = useRef(false);
  // Hard expiry on pending scroll-to-end. Set when the user submits or
  // switches chats; cleared on first consume. The expiry timestamp acts as
  // a safety net: if some renderer re-fires `onContentSizeChange` 3 minutes
  // later (when the answer arrives), we don't want to yank the user to the
  // bottom mid-read. After this timestamp passes, pending is treated as
  // false regardless of the ref value.
  const pendingScrollToEndExpiryRef = useRef<number>(0);
  // Latches a one-shot scroll-to-end the next time content size grows. Used
  // when the user explicitly submits a new prompt or switches chat — we want
  // them at the bottom for that one render even if they were scrolled up
  // before.
  const pendingScrollToEndRef = useRef(false);
  const pendingConversationScrollTargetRef = useRef<PendingConversationScrollTarget>("bottom");
  const savedAnswerScrollYRef = useRef<number | null>(null);
  const prevDetailOpenRef = useRef(false);
  const documentPanelProgress = useRef(new Animated.Value(0)).current;

  const {
    activeJobId,
    status,
    result,
    documentPresets,
    headlineFrames,
    selectedPrecedentId,
    setSelectedPrecedentId,
    selectedDetail,
    detailOpen,
    setDetailOpen,
    submitting,
    error,
    submit,
    followUp,
    cancelActiveJob,
    openJob,
    restoreLocalJob,
    resetView,
    beginReplay,
    pushReplayStatus,
    finishReplay,
    exitReplay,
    updateReplayResultMarkdown,
  } = useLawkeyJob();

  const openPrecedentDetail = (precedentId: string, quoteText = "") => {
    if (!precedentId) return;
    setTargetQuoteText(quoteText || "");
    setSelectedPrecedentId(precedentId);
    setDetailOpen(true);
    setPrecedentsExpanded(true);
  };

  // Admin auth + replay state. Admin = anyone who passed the login dialog. The
  // replay machinery is admin-only and controls the demo flow described by
  // the user: re-clicking a cached chat replays a deterministic 2-second-
  // per-stage loader and shows the cached answer immediately, regardless of
  // what the admin actually types.
  useEffect(() => {
    const authed = loadAuthState();
    setIsAdmin(authed);
    setAnalysisModeState((current) => normalizeAnalysisModeForRole(current, authed));
  }, []);
  const [replayArmedJobId, setReplayArmedJobId] = useState("");
  const [replayInFlight, setReplayInFlight] = useState(false);
  const [answerEditDraft, setAnswerEditDraft] = useState<string | null>(null);

  useEffect(() => {
    setTargetQuoteText("");
  }, [activeJobId]);
  const replayCancelRef = useRef<(() => void) | null>(null);
  // Demo slideshow state. `demoActive` toggles the click-overlay + advance
  // controls; `demoSlideIndex` walks through DEMO_SLIDES once the loader
  // sequence completes and the cached result is rendered.
  const [demoActive, setDemoActive] = useState(false);
  const [demoSlideIndex, setDemoSlideIndex] = useState(-1);
  const demoTimersRef = useRef<Array<ReturnType<typeof setTimeout>>>([]);
  const demoCancelRef = useRef<(() => void) | null>(null);

  const cancelDemoTimers = () => {
    demoTimersRef.current.forEach((t) => clearTimeout(t));
    demoTimersRef.current = [];
    if (demoCancelRef.current) {
      demoCancelRef.current();
      demoCancelRef.current = null;
    }
  };

  const applySnapshotState = (snapshot: ReturnType<typeof loadSessionSnapshot>) => {
    if (!snapshot) {
      return;
    }
    if (snapshot.prompt) setSubmittedPrompt(snapshot.prompt);
    if (snapshot.mode) setMode(snapshot.mode);
    if (snapshot.selectedPrecedentId) setSelectedPrecedentId(snapshot.selectedPrecedentId);
    if (typeof snapshot.samplePath === "string") setSamplePath(snapshot.samplePath);
    if (typeof snapshot.documentPresetId === "string") setDocumentPresetId(snapshot.documentPresetId);
    if (typeof snapshot.useCustomSamplePath === "boolean") setUseCustomSamplePath(snapshot.useCustomSamplePath);
    if (Array.isArray(snapshot.questionMessages)) setQuestionMessages(snapshot.questionMessages);
    if (Array.isArray(snapshot.documentMessages)) {
      setDocumentMessages(snapshot.documentMessages);
      if (snapshot.documentMessages.length) {
        setDocumentPresetConfirmed(true);
      }
    }
  };

  const persistDraftSnapshot = (overrides?: Partial<{
    mode: "question" | "document";
    prompt: string;
    submittedPrompt: string;
    samplePath: string;
    uploadedSampleLabel: string;
    documentPresetId: string;
    useCustomSamplePath: boolean;
    questionMessages: Array<{ role: "user"; text: string }>;
    documentMessages: DocumentConversationItem[];
    pendingTurn: PendingTurn | null;
  }>) => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      writeTabStorage(
        DRAFT_STORAGE_KEY,
        JSON.stringify({
          mode: overrides?.mode ?? mode,
          prompt: overrides?.prompt ?? prompt,
          submittedPrompt: overrides?.submittedPrompt ?? submittedPrompt,
          samplePath: overrides?.samplePath ?? samplePath,
          uploadedSampleLabel: overrides?.uploadedSampleLabel ?? uploadedSampleLabel,
          documentPresetId: overrides?.documentPresetId ?? documentPresetId,
          useCustomSamplePath: overrides?.useCustomSamplePath ?? useCustomSamplePath,
          questionMessages: overrides?.questionMessages ?? questionMessages,
          documentMessages: overrides?.documentMessages ?? documentMessages,
          pendingTurn: overrides?.pendingTurn !== undefined ? overrides.pendingTurn : pendingTurn,
        }),
      );
    } catch {
      // Ignore browser storage errors.
    }
  };

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const resolvedClientId = getBrowserClientId();
        setBrowserClientId(resolvedClientId);
        window.localStorage.removeItem(LEGACY_HISTORY_STORAGE_KEY);
        const rawHistory = window.localStorage.getItem(historyStorageKey(resolvedClientId));
        if (rawHistory) {
          setHistory(pruneEmbeddedSourceSessionHistory(JSON.parse(rawHistory) as SessionHistoryItem[], activeJobId, documentMessages));
        }
        const urlJobId = routeJobId.trim();
        // Soft-deleted jobs must not load via direct URL or viewed-session
        // restore — the user's intent is "delete from list and from external
        // access; server keeps the data only".
        const deletedIds = loadDeletedSessionIds();
        const filterDeleted = (id: string) => (id && !deletedIds.has(id) ? id : "");
        const viewedSessionId = filterDeleted(readTabStorage(VIEWED_SESSION_STORAGE_KEY).trim());
        const preferredJobId = filterDeleted(urlJobId) || viewedSessionId || filterDeleted(readTabStorage(LAST_SESSION_STORAGE_KEY).trim()) || "";
        const rawDraft = readTabStorage(DRAFT_STORAGE_KEY);
        if (rawDraft) {
          const saved = normalizeDraftState(JSON.parse(rawDraft));
          if (saved.mode) setMode(saved.mode);
          if (saved.prompt) setPrompt(saved.prompt);
          if (saved.samplePath) setSamplePath(saved.samplePath);
          if (saved.uploadedSampleLabel) setUploadedSampleLabel(saved.uploadedSampleLabel);
          if (saved.documentPresetId) setDocumentPresetId(saved.documentPresetId);
          if (typeof saved.useCustomSamplePath === "boolean") setUseCustomSamplePath(saved.useCustomSamplePath);
          if (Array.isArray(saved.documentMessages)) {
            setDocumentMessages(saved.documentMessages);
          }
          if (Array.isArray(saved.questionMessages)) {
            setQuestionMessages(saved.questionMessages);
          }
          if (saved.submittedPrompt) {
            setSubmittedPrompt(saved.submittedPrompt);
          }
          if (saved.pendingTurn) {
            setPendingTurn({
              id: saved.pendingTurn.id,
              mode: saved.pendingTurn.mode,
              text: saved.pendingTurn.text,
              sourceJobId: saved.pendingTurn.sourceJobId || "",
            });
          }
        }
        if (preferredJobId) {
          const lastJobId = preferredJobId;
          pendingConversationScrollTargetRef.current = "latestAnswerStart";
          const snapshot = loadSessionSnapshot(lastJobId);
          const localStatus = loadStatusSnapshot(lastJobId) || (await loadStatusSnapshotAsync(lastJobId));
          const localResult = loadResultSnapshot(lastJobId) || (await loadResultSnapshotAsync(lastJobId));
          applySnapshotState(snapshot);
          if (localResult || localStatus) {
            restoreLocalJob({
              jobId: lastJobId,
              status: localStatus,
              result: localResult,
              selectedPrecedentId: snapshot?.selectedPrecedentId,
            });
          } else {
            openJob(lastJobId);
          }
          setStorageHydrated(true);
          void getJobStatus(lastJobId)
            .then((payload) => {
              if (cancelled) {
                return;
              }
              if (!isRestorableJobState(payload.state) && payload.state !== "completed" && !localResult) {
                writeTabStorage(LAST_SESSION_STORAGE_KEY, "");
                saveViewedSessionId("");
              }
            })
            .catch(async () => {
              if (cancelled || localResult || localStatus) {
                return;
              }
              try {
                const jobs = await listJobs(resolvedClientId);
                if (cancelled) {
                  return;
                }
                const live = jobs.find((item) => item.queuePosition === 1 && isRestorableJobState(item.state));
                if (live?.jobId) {
                  openJob(live.jobId);
                  saveViewedSessionId(live.jobId);
                } else {
                  writeTabStorage(LAST_SESSION_STORAGE_KEY, "");
                  saveViewedSessionId("");
                }
              } catch {
                writeTabStorage(LAST_SESSION_STORAGE_KEY, "");
              }
            });
        } else {
          setStorageHydrated(true);
        }
      } catch {
        // Ignore local storage hydration issues.
        setStorageHydrated(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [openJob, restoreLocalJob]);

  useEffect(() => {
    if (!browserClientId.trim()) {
      return undefined;
    }
    let cancelled = false;
    void listJobs(browserClientId)
      .then((jobs) => {
        if (cancelled || !jobs.length) {
          return;
        }
        setHistory((current) => {
          const deleted = loadDeletedSessionIds();
          const merged = mergeServerHistory(current, jobs).filter((item) => !deleted.has(item.id));
          return pruneEmbeddedSourceSessionHistory(merged, activeJobId, documentMessages);
        });
      })
      .catch(() => {
        // Ignore history bootstrap failures.
      });
    return () => {
      cancelled = true;
    };
  }, [activeJobId, browserClientId, documentMessages]);

  useEffect(() => {
    if (!documentPresetId && documentPresets.length > 0) {
      setDocumentPresetId(documentPresets[0].id);
    }
  }, [documentPresetId, documentPresets]);

  useEffect(() => {
    if (mode === "document" && !activeJobId && !result && !status) {
      setSubmittedPrompt("");
    }
  }, [activeJobId, mode, result, status]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    // Wait until hydration finishes so we don't overwrite the stored draft
    // (with initial `null` values) before restoration runs.
    if (!storageHydrated) {
      return;
    }
    try {
      writeTabStorage(
        DRAFT_STORAGE_KEY,
        JSON.stringify({
          mode,
          prompt,
          submittedPrompt,
          samplePath,
          uploadedSampleLabel,
          documentPresetId,
          useCustomSamplePath,
          questionMessages,
          documentMessages,
          pendingTurn,
        }),
      );
    } catch {
      // Ignore local storage quota issues.
    }
  }, [documentMessages, documentPresetId, mode, pendingTurn, prompt, questionMessages, samplePath, storageHydrated, submittedPrompt, uploadedSampleLabel, useCustomSamplePath]);

  const headlineSignature = useMemo(() => headlineFrames.join("||"), [headlineFrames]);

  useEffect(() => {
    setHeadlineIndex(0);
  }, [headlineSignature]);

  useEffect(() => {
    if (headlineFrames.length <= 1) {
      return undefined;
    }
    const handle = setInterval(() => {
      startTransition(() => {
        setHeadlineIndex((current) => (current + 1) % headlineFrames.length);
      });
    }, constrained ? 5200 : 3400);
    return () => clearInterval(handle);
  }, [constrained, headlineFrames.length]);

  useEffect(() => {
    if (!activeJobId) {
      return;
    }
    const sourceJobId = continuationSourceJobId;
    if (
      shouldSkipSourceDocumentHistoryUpdate({
        mode,
        activeJobId,
        continuationSourceJobId: sourceJobId,
        pendingDocumentSetupSourceJobId: pendingDocumentSetup?.sourceJobId,
      })
    ) {
      return;
    }
    setHistory((current) => {
      const fallbackTitle = mode === "document" ? "문서 초안" : "분석 세션";
      const meta = buildHistoryMeta({ result, status, mode });
      const historyPrompt = submittedPrompt.trim() || String(status?.userTask || "").trim() || findSessionPrompt(current, activeJobId);
      const nextItem: SessionHistoryItem = {
        id: activeJobId,
        title: buildHistoryTitle(historyPrompt, fallbackTitle),
        meta,
        prompt: historyPrompt,
        createdAt: status?.createdAt ?? Date.now() / 1000,
        finishedAt: status?.finishedAt ?? null,
      };
      return pruneEmbeddedSourceSessionHistory(
        upsertContinuationSessionHistory(current, nextItem, sourceJobId),
        activeJobId,
        documentMessages,
      );
    });
    if (sourceJobId && sourceJobId !== activeJobId) {
      setContinuationSourceJobId("");
    }
  }, [activeJobId, continuationSourceJobId, documentMessages, mode, pendingDocumentSetup?.sourceJobId, result, status, submittedPrompt]);

  useEffect(() => {
    return () => {
      if (loginOpenTimerRef.current) {
        clearTimeout(loginOpenTimerRef.current);
        loginOpenTimerRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!compact) {
      setSidebarOpen(false);
    }
  }, [compact]);

  // Snapshot every successfully-completed job for admin replay. Server data
  // is untouched; the snapshot is purely local-only and is only consumed
  // when the same admin browser revisits the chat from the sidebar.
  useEffect(() => {
    if (!isAdmin) return;
    if (replayInFlight) return;
    if (!activeJobId) return;
    if (!status || status.state !== "completed") return;
    if (!result || result.jobId !== activeJobId || !result.answerMarkdown) return;
    const promptForReplay = submittedPrompt.trim() || String(status.userTask || "").trim() || "";
    if (!promptForReplay) return;
    if (loadAdminReplaySnapshot(activeJobId)) return;
    saveAdminReplaySnapshot({
      jobId: activeJobId,
      prompt: promptForReplay,
      status,
      result,
    });
  }, [isAdmin, replayInFlight, activeJobId, status, result, submittedPrompt]);

  // Sync the analysis-mode menu to the active job's stored mode when the user
  // hasn't manually picked something else this session. Refreshing the page
  // mid-run (or after run completion) should put the menu back on whatever
  // mode the job actually used.
  useEffect(() => {
    if (userTouchedAnalysisModeRef.current) return;
    const incoming = status?.analysisMode;
    if (!incoming) return;
    const normalized = normalizeAnalysisModeForRole(incoming, isAdmin);
    setAnalysisModeState(normalized);
    if (isAdmin) {
      try {
        window.localStorage?.setItem("lawkey-analysis-mode-v1", normalized);
      } catch {
        /* ignore */
      }
    }
  }, [isAdmin, status?.analysisMode]);

  useEffect(() => {
    if (result?.jobId) {
      setPrecedentsExpanded(false);
    }
  }, [result?.jobId]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      window.localStorage.removeItem(LEGACY_HISTORY_STORAGE_KEY);
      if (!browserClientId.trim()) {
        return;
      }
      window.localStorage.setItem(historyStorageKey(browserClientId), JSON.stringify(history));
    } catch {
      // Ignore local storage quota issues.
    }
  }, [browserClientId, history]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      if (shouldPersistLastSession(activeJobId, storageHydrated)) {
        writeTabStorage(LAST_SESSION_STORAGE_KEY, activeJobId);
      } else if (storageHydrated) {
        writeTabStorage(LAST_SESSION_STORAGE_KEY, "");
      }
    } catch {
      // Ignore local storage quota issues.
    }
  }, [activeJobId, storageHydrated]);

  // Sync URL path with the active job so reload restores the same conversation.
  // Use history.replaceState directly so the React component does NOT remount
  // (router.replace would unmount /chat/[id] vs / and lose all state).
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!storageHydrated) return;
    const currentPath = window.location.pathname || "/";
    if (activeJobId.trim()) {
      const desired = `/chat/${encodeURIComponent(activeJobId)}`;
      if (currentPath !== desired) {
        try {
          window.history.replaceState({}, "", desired);
        } catch {
          /* ignore */
        }
      }
    } else if (currentPath.startsWith("/chat/")) {
      try {
        window.history.replaceState({}, "", "/");
      } catch {
        /* ignore */
      }
    }
  }, [activeJobId, storageHydrated]);

  useEffect(() => {
    if (!activeJobId.trim()) {
      return;
    }
    saveViewedSessionId(activeJobId);
    saveSessionSnapshot({
      jobId: activeJobId,
      prompt: submittedPrompt.trim(),
      mode,
      selectedPrecedentId,
      samplePath,
      documentPresetId,
      useCustomSamplePath,
      questionMessages,
      documentMessages,
    });
  }, [activeJobId, documentMessages, documentPresetId, mode, questionMessages, samplePath, selectedPrecedentId, submittedPrompt, useCustomSamplePath]);

  useEffect(() => {
    if (!activeJobId || !status) {
      return;
    }
    saveStatusSnapshot(activeJobId, status);
    void saveStatusSnapshotAsync(activeJobId, status);
  }, [activeJobId, status]);

  useEffect(() => {
    if (!activeJobId || !result) {
      return;
    }
    saveResultSnapshot(activeJobId, result);
    void saveResultSnapshotAsync(activeJobId, result);
  }, [activeJobId, result]);

  useEffect(() => {
    if (!activeJobId || submittedPrompt.trim()) {
      return;
    }
    const restoredPrompt = findSessionPrompt(history, activeJobId);
    if (restoredPrompt) {
      setSubmittedPrompt(restoredPrompt);
      setQuestionMessages((current) => (current.length ? current : [{ role: "user", text: restoredPrompt }]));
    }
  }, [activeJobId, history, submittedPrompt]);

  const heroTicker = headlineFrames[headlineIndex % headlineFrames.length] ?? headlineFrames[0] ?? "";
  // While we're holding the loader between status=completed and result
  // arriving, swap the headline to a celebratory line so the gap reads as
  // "almost done" rather than "still grinding".
  const loaderHeadline = (() => {
    if (!pendingTurn) return heroTicker;
    if (status?.state === "completed" && (!result || result.jobId !== activeJobId || !result.answerMarkdown)) {
      return "답변이 준비되었습니다!";
    }
    return buildPendingLoaderHeadline(pendingTurn.mode, heroTicker);
  })();
  // While we hold the loader between status=completed and result arriving for
  // THIS job, show the bar at 100% (state=completed). For the unrelated
  // pre-submit "old job completed but new turn pending" flicker, fall back to
  // the standard buildPendingLoaderState which masks state=completed.
  const isCelebratingCurrentJob =
    !!pendingTurn &&
    status?.state === "completed" &&
    status?.jobId === activeJobId &&
    (!result || result.jobId !== activeJobId || !result.answerMarkdown);
  const loaderState = isCelebratingCurrentJob
    ? "completed"
    : buildPendingLoaderState(status?.state, !!pendingTurn);
  const loaderStatus = shouldUseStatusForPendingLoader(status?.state, !!pendingTurn) ? status : null;
  const statusIsTerminal = isTerminalRunState(status?.state);
  const showRunLoader = shouldShowRunLoader({
    detailOpen,
    hasResult: !!result,
    hasStatus: !!status && !statusIsTerminal,
    submitting,
    hasPendingTurn: !!pendingTurn,
  });
  const canCancelRequest = !!activeJobId && (!!pendingTurn || (!!status && !statusIsTerminal) || submitting);
  const documentThreadStarted =
    mode === "document" && (!!activeJobId || !!result || !!status || documentMessages.length > 0);
  const documentConfiguratorVisible = shouldShowDocumentConfigurator({ mode, documentThreadStarted });
  const conversationMode = resolveConversationMode({
    inputMode: mode,
    pendingMode: pendingTurn?.mode,
    statusMode: status?.mode,
    resultMode: result?.mode,
    hasDocumentMessages: documentMessages.length > 0,
  });
  const showDocumentResultCard = shouldShowDocumentResultCard({
    conversationMode,
    detailOpen,
    hasAnswerMarkdown: !!result?.answerMarkdown,
    hasPendingTurn: !!pendingTurn || !!pendingDocumentSetup,
    resultMode: result?.mode,
  });
  const resultElapsedSeconds =
    status?.finishedAt && status.createdAt ? Math.max(0, status.finishedAt - status.createdAt) : status?.elapsedSeconds ?? 0;
  const resultElapsedLabel = result ? formatTotalElapsedLabel(resultElapsedSeconds) : "";
  const questionAnswerMarkdown = useMemo(() => {
    const currentAnswer = conversationMode === "question" && result?.mode === "question" ? result.answerMarkdown || "" : "";
    if (conversationMode === "question" && carriedQuestionAnswer?.markdown && activeJobId && activeJobId !== carriedQuestionAnswer.sourceJobId) {
      return composeQuestionAnswerMarkdown(carriedQuestionAnswer.markdown, currentAnswer);
    }
    return currentAnswer;
  }, [activeJobId, carriedQuestionAnswer, conversationMode, result?.answerMarkdown, result?.mode]);
  const questionConversationTurns = useMemo(
    () =>
      buildQuestionConversationTurns({
        submittedPrompt,
        questionMessages,
        answerMarkdown: questionAnswerMarkdown,
        hasPendingTurn: conversationMode === "question" && showRunLoader,
      }),
    [conversationMode, questionAnswerMarkdown, questionMessages, showRunLoader, submittedPrompt],
  );
  const questionAssistantTurnCount = useMemo(
    () => questionConversationTurns.filter((turn) => turn.type === "assistant").length,
    [questionConversationTurns],
  );
  const hasConversationState =
    !!activeJobId ||
    !!status ||
    !!result ||
    !!detailOpen ||
    !!pendingDocumentSetup ||
    !!submittedPrompt.trim() ||
    questionMessages.length > 0 ||
    documentMessages.length > 0;
  const showWelcome = !hasConversationState;
  const showConversation = hasConversationState || detailOpen;
  const [deletedIdsTick, setDeletedIdsTick] = useState(0);
  const visibleHistory = useMemo(() => {
    const deleted = loadDeletedSessionIds();
    return filterVisibleHistory(history).filter((item) => !deleted.has(item.id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [history, deletedIdsTick]);
  const welcomeTitleFontSize = compact ? Math.max(24, Math.min(35, (width - 44) / 11.5)) : 35;
  const welcomeTitleLineHeight = Math.round(welcomeTitleFontSize * 1.14);

  useEffect(() => {
    Animated.timing(documentPanelProgress, {
      toValue: documentConfiguratorVisible ? 1 : 0,
      duration: constrained ? 160 : 240,
      useNativeDriver: false,
    }).start();
  }, [constrained, documentConfiguratorVisible, documentPanelProgress]);

  // When the user explicitly switches chats or submits a new prompt, latch a
  // one-shot scroll-to-end so the next layout puts the loader/answer at the
  // bottom — but never yank the viewport while the user is reading an arriving
  // answer or a chunk update.
  useEffect(() => {
    if (!showConversation || detailOpen) {
      return;
    }
    if (prevDetailOpenRef.current) {
      return;
    }
    // Only fire scroll-to-end on user-initiated transitions (chat switch or
    // submit). Do NOT fire when new messages arrive — answer-arrival scroll
    // jumps were specifically reported as disruptive while reading. We also
    // set a 5-second expiry so any layout shift after the user has clearly
    // started reading does NOT re-trigger an auto-scroll, even if some
    // unrelated effect re-sets `pendingScrollToEndRef.current = true`.
    pendingScrollToEndRef.current = true;
    pendingScrollToEndExpiryRef.current = Date.now() + 5000;
    userScrolledAwayRef.current = false;
  }, [activeJobId, detailOpen, showConversation, submittedPrompt]);

  useEffect(() => {
    const wasOpen = prevDetailOpenRef.current;
    if (detailOpen && !wasOpen) {
      // Opening detail: remember where the answer body was scrolled to so we
      // can restore that exact reading position when the drawer closes.
      savedAnswerScrollYRef.current = lastScrollYRef.current;
      // We intentionally do NOT scroll outer to y=0 here. The PrecedentDrawer
      // handles outer scroll via document-level scrollIntoView({block:
      // "center"}) on the highlight, which walks up scrollable ancestors and
      // brings BOTH the inner full-text scroll AND the outer chat scroll to
      // a position where the highlight is visible. If we forced y=0 here,
      // outer would land at the top while inner ScrollView centers the
      // highlight, leaving the user staring at empty space.
      prevDetailOpenRef.current = detailOpen;
      return undefined;
    }
    if (wasOpen && !detailOpen && savedAnswerScrollYRef.current != null) {
      const target = savedAnswerScrollYRef.current;
      const handle = setTimeout(() => {
        conversationScrollRef.current?.scrollTo({ y: target, animated: false });
        savedAnswerScrollYRef.current = null;
      }, 80);
      prevDetailOpenRef.current = detailOpen;
      return () => clearTimeout(handle);
    }
    prevDetailOpenRef.current = detailOpen;
    return undefined;
  }, [detailOpen, selectedPrecedentId]);

  useEffect(() => {
    if (!pendingTurn || !status?.jobId) {
      return;
    }
    if (status.jobId !== activeJobId) {
      return;
    }
    if (!isTerminalRunState(status.state)) {
      return;
    }
    // Failed/cancelled/interrupted: clear pendingTurn immediately so the
    // error UI takes over.
    if (status.state !== "completed") {
      setPendingTurn(null);
      return;
    }
    // Completed: hold the loader (now showing the celebratory "답변이
    // 준비되었습니다!" headline) until the result payload actually arrives.
    // Otherwise the loader vanishes for the seconds it takes to fetch
    // /api/jobs/{id}/result and the user sees an empty viewport.
    if (result?.jobId === activeJobId && result?.answerMarkdown) {
      setPendingTurn(null);
    }
  }, [pendingTurn, status?.jobId, status?.state, activeJobId, result?.jobId, result?.answerMarkdown]);

  // After hydration, if the active job is still in flight (e.g. user reloaded
  // mid-run or re-entered the chat), synthesize a pendingTurn so the progress
  // strip and live status feed render again.
  useEffect(() => {
    if (!storageHydrated) return;
    if (!status) return;
    if (statusIsTerminal) return;
    if (pendingTurn) return;
    if (!status.jobId) return;
    setPendingTurn({
      id: `${Date.now()}-restored-${status.jobId}`,
      mode: status.mode === "document" ? "document" : "question",
      text: status.userTask || submittedPrompt || "",
      sourceJobId: status.jobId,
    });
  }, [storageHydrated, status?.jobId, status?.state, statusIsTerminal, pendingTurn, submittedPrompt]);

  useEffect(() => {
    if (pendingTurn && error) {
      setPendingTurn(null);
    }
  }, [error, pendingTurn]);

  const getVisibleQuestionAnswerMarkdown = () => {
    const currentAnswer = result?.mode === "question" ? result.answerMarkdown || "" : "";
    if (carriedQuestionAnswer?.markdown && activeJobId && activeJobId !== carriedQuestionAnswer.sourceJobId) {
      return composeQuestionAnswerMarkdown(carriedQuestionAnswer.markdown, currentAnswer);
    }
    return currentAnswer;
  };

  const startDocumentSetup = ({
    nextPrompt,
    nextThread,
  }: {
    nextPrompt: string;
    nextThread: DocumentConversationItem[];
  }) => {
    const recommendedPresetId = inferDocumentPresetIdFromPrompt(nextPrompt, documentPresetId || documentPresets[0]?.id || "");
    const nextMessages: DocumentConversationItem[] = [...nextThread, { role: "assistant", text: DOCUMENT_SETUP_MESSAGE }];
    if (recommendedPresetId) {
      setDocumentPresetId(recommendedPresetId);
    }
    setMode("document");
    // Preserve the prior question answer + precedents so hyperlinks in the
    // embedded question turn keep resolving after the document job replaces
    // `result` with a document-mode payload that has no question precedents.
    const carriedPrecedentsForDocument = (carriedQuestionAnswer?.selectedPrecedents ?? []).concat(
      result?.selectedPrecedents ?? [],
    );
    const visiblePriorAnswer = getVisibleQuestionAnswerMarkdown();
    if (visiblePriorAnswer && carriedPrecedentsForDocument.length) {
      setCarriedQuestionAnswer({
        sourceJobId: activeJobId || "",
        markdown: visiblePriorAnswer,
        selectedPrecedents: carriedPrecedentsForDocument,
      });
    } else {
      setCarriedQuestionAnswer(null);
    }
    setSubmittedPrompt("");
    setQuestionMessages([]);
    setDocumentMessages(nextMessages);
    setPendingDocumentSetup({
      id: `${Date.now()}-document-setup`,
      prompt: nextPrompt,
      conversation: nextThread,
      sourceJobId: activeJobId || "",
    });
    setDocumentPresetConfirmed(false);
    setPendingTurn(null);
    persistDraftSnapshot({
      mode: "document",
      prompt: "",
      submittedPrompt: "",
      documentPresetId: recommendedPresetId || documentPresetId,
      questionMessages: [],
      documentMessages: nextMessages,
    });
  };

  const startDocumentDraft = async ({
    nextPrompt,
    nextThread,
    activeClientId,
    selectedPresetId,
    selectedSamplePath,
    displayMessages,
    sourceJobId,
  }: {
    nextPrompt: string;
    nextThread: DocumentConversationItem[];
    activeClientId: string;
    selectedPresetId?: string;
    selectedSamplePath?: string;
    displayMessages?: DocumentConversationItem[];
    sourceJobId?: string;
  }) => {
    pendingConversationScrollTargetRef.current = "bottom";
    const resolvedPresetId = selectedPresetId ?? documentPresetId;
    const resolvedSamplePath = selectedSamplePath !== undefined ? selectedSamplePath.trim() || undefined : samplePath.trim() || undefined;
    const currentDisplayMessages = displayMessages?.length ? displayMessages : nextThread;
    if (resolvedPresetId) {
      setDocumentPresetId(resolvedPresetId);
    }
    setMode("document");
    setSubmittedPrompt("");
    setQuestionMessages([]);
    setDocumentMessages(currentDisplayMessages);
    setPendingDocumentSetup(null);
    setDocumentPresetConfirmed(true);
    const resolvedSourceJobId = sourceJobId ?? activeJobId ?? "";
    if (resolvedSourceJobId) {
      setContinuationSourceJobId(resolvedSourceJobId);
    }
    setPendingTurn({ id: `${Date.now()}-document`, mode: "document", text: nextPrompt, sourceJobId: resolvedSourceJobId });
    persistDraftSnapshot({
      mode: "document",
      prompt: "",
      submittedPrompt: "",
      documentPresetId: resolvedPresetId,
      samplePath: resolvedSamplePath || "",
      questionMessages: [],
      documentMessages: currentDisplayMessages,
    });
    let draftRequest = buildDocumentDraftRequest({
      currentPrompt: nextPrompt,
      conversation: nextThread,
      preflight: null,
    });
    try {
      const preflight = await preflightDocument({
        userTask: nextPrompt,
        documentPresetId: resolvedPresetId,
        samplePath: resolvedSamplePath,
        sourceJobId: resolvedSourceJobId || undefined,
        conversation: nextThread,
      });
      draftRequest = buildDocumentDraftRequest({
        currentPrompt: nextPrompt,
        conversation: nextThread,
        preflight,
      });
      if (draftRequest.assistantMessage) {
        const nextMessages: DocumentConversationItem[] = [...currentDisplayMessages, { role: "assistant", text: draftRequest.assistantMessage }];
        setDocumentMessages(nextMessages);
        persistDraftSnapshot({
          mode: "document",
          prompt: "",
          submittedPrompt: draftRequest.draftingGoal,
          documentPresetId: resolvedPresetId,
          samplePath: resolvedSamplePath || "",
          questionMessages: [],
          documentMessages: nextMessages,
        });
      }
    } catch (caught) {
      draftRequest = buildDocumentDraftRequest({
        currentPrompt: nextPrompt,
        conversation: nextThread,
        preflight: buildFallbackDocumentPreflight(nextPrompt),
      });
      const nextMessages: DocumentConversationItem[] = [...currentDisplayMessages, { role: "assistant", text: draftRequest.assistantMessage }];
      setDocumentMessages(nextMessages);
      persistDraftSnapshot({
        mode: "document",
        prompt: "",
        submittedPrompt: draftRequest.draftingGoal,
        documentPresetId: resolvedPresetId,
        samplePath: resolvedSamplePath || "",
        questionMessages: [],
        documentMessages: nextMessages,
      });
    }
    setSubmittedPrompt(draftRequest.draftingGoal);
    if (!draftRequest.shouldSubmit) {
      setPendingTurn(null);
      return;
    }
    await submit({
      mode: "document",
      userTask: draftRequest.retrievalTask,
      clientId: activeClientId,
      documentPresetId: resolvedPresetId,
      documentContext: draftRequest.documentContext,
      samplePath: resolvedSamplePath,
      analysisMode,
      skipIntentCheck: true,
    });
  };

  const handleConfirmDocumentPreset = async (presetId: string) => {
    const setup = pendingDocumentSetup;
    if (!setup || submitting) {
      return;
    }
    setUseCustomSamplePath(false);
    setSamplePath("");
    setUploadedSampleLabel("");
    const activeClientId = browserClientId || getBrowserClientId();
    if (!browserClientId && activeClientId) {
      setBrowserClientId(activeClientId);
    }
    await startDocumentDraft({
      nextPrompt: setup.prompt,
      nextThread: setup.conversation,
      activeClientId,
      selectedPresetId: presetId,
      selectedSamplePath: "",
      displayMessages: documentMessages,
      sourceJobId: setup.sourceJobId,
    });
  };

  const scrollToHeadingAnchor = (anchorMarkdown: string) => {
    if (Platform.OS !== "web" || typeof document === "undefined") return;
    // Anchor is in markdown form, e.g. "## 어렵지 않아요".
    const m = String(anchorMarkdown || "").match(/^(#{1,3})\s+(.+)$/);
    if (!m) return;
    const level = m[1].length;
    const text = m[2].trim();
    const id = `lk-h${level}-${slugifyHeading(text)}`;
    // Defer to next frame so any layout change settles first.
    const fire = () => {
      const node = document.getElementById(id) as HTMLElement | null;
      if (node && typeof node.scrollIntoView === "function") {
        try {
          node.scrollIntoView({ behavior: "smooth", block: "start" });
        } catch {
          node.scrollIntoView();
        }
      }
    };
    const t = setTimeout(fire, 80);
    demoTimersRef.current.push(t);
  };

  const startDemoFlow = () => {
    cancelDemoTimers();
    // Reset workspace to a clean composer-ready state.
    pendingConversationScrollTargetRef.current = "bottom";
    resetView();
    setReplayArmedJobId("");
    setReplayInFlight(false);
    setPendingTurn(null);
    setSubmittedPrompt("");
    setQuestionMessages([]);
    setDocumentMessages([]);
    setComposerSendsNewRequest(false);
    setPendingDocumentSetup(null);
    setDocumentPresetConfirmed(false);
    setDetailOpen(false);
    setPrecedentsExpanded(false);
    setSidebarOpen(false);
    setMode("question");
    setAnalysisModeState("beta4");
    setPrompt("");
    setDemoActive(true);
    setDemoSlideIndex(-1);

    // Phase 1: type the prompt char-by-char.
    const frames = buildTypingFrames(DEMO_PROMPT, 35);
    for (const frame of frames) {
      const t = setTimeout(() => setPrompt(frame.value), frame.ms);
      demoTimersRef.current.push(t);
    }
    const typingDoneAt = (frames[frames.length - 1]?.ms ?? 0) + 400;

    // Phase 2: submit + drive synthetic loader timeline through DEMO_STAGES.
    const t2 = setTimeout(() => {
      const snapshot = loadDemoSnapshot();
      setPrompt("");
      setSubmittedPrompt(DEMO_PROMPT);
      setQuestionMessages([{ role: "user", text: DEMO_PROMPT }]);
      setPendingTurn({ id: `${Date.now()}-demo`, mode: "question", text: DEMO_PROMPT });
      setReplayInFlight(true);
      beginReplay(DEMO_JOB_ID);

      let acc = 0;
      const startMs = Date.now();
      DEMO_STAGES.forEach((stage, idx) => {
        const fireAt = acc;
        acc += stage.durationMs;
        const t = setTimeout(() => {
          const elapsed = Math.max(0, Math.round((Date.now() - startMs) / 1000));
          const totalChunks = snapshot.status.totalChunks || 13;
          // Once the analyze stage starts, "completed chunks" must only ever
          // grow — synthesize/done should not flip the counter back to 0.
          const completedSoFar = (() => {
            if (stage.state === "analyzing_chunks") {
              return Math.min(totalChunks, Math.max(1, Math.floor(((idx + 0.5) / DEMO_STAGES.length) * totalChunks)));
            }
            if (
              stage.state === "writing_final_draft" ||
              stage.state === "writing_document" ||
              stage.state === "applying_coverage_patch" ||
              stage.state === "exporting_artifacts" ||
              stage.state === "completed"
            ) {
              return totalChunks;
            }
            return 0;
          })();
          pushReplayStatus({
            ...snapshot.status,
            jobId: DEMO_JOB_ID,
            state: stage.state,
            phase: stage.id,
            elapsedSeconds: elapsed,
            etaSeconds: Math.max(0, Math.round((acc - (Date.now() - startMs)) / 1000)),
            completedChunks: completedSoFar,
            totalChunks,
          });
        }, fireAt);
        demoTimersRef.current.push(t);
      });

      // Phase 3: finishReplay → result rendered → enter slide mode.
      const t3 = setTimeout(() => {
        const elapsedSec = Math.max(1, Math.round(acc / 1000));
        const nowSec = Date.now() / 1000;
        finishReplay(
          {
            ...snapshot.status,
            jobId: DEMO_JOB_ID,
            state: "completed",
            elapsedSeconds: elapsedSec,
            // Override BOTH createdAt and finishedAt so the
            // `formatTotalElapsedLabel(finishedAt - createdAt)` displayed
            // above the answer reflects the synthetic 11 s demo runtime
            // (instead of 2026-now minus the snapshot's frozen 2023
            // createdAt → many minutes off).
            createdAt: nowSec - elapsedSec,
            finishedAt: nowSec,
          },
          { ...snapshot.result, jobId: DEMO_JOB_ID },
        );
        setPendingTurn(null);
        setReplayInFlight(false);
        // Wait briefly for the result layout to settle, then start slides.
        const t4 = setTimeout(() => setDemoSlideIndex(0), 400);
        demoTimersRef.current.push(t4);
      }, acc + 200);
      demoTimersRef.current.push(t3);
    }, typingDoneAt);
    demoTimersRef.current.push(t2);
  };

  const stopDemoFlow = () => {
    cancelDemoTimers();
    setDemoActive(false);
    setDemoSlideIndex(-1);
    exitReplay();
  };

  const lastDemoClickAtRef = useRef(0);
  const handleDemoOverlayPress = () => {
    if (!demoActive) return;
    if (demoSlideIndex < 0) return;
    const now = Date.now();
    const delta = now - lastDemoClickAtRef.current;
    lastDemoClickAtRef.current = now;
    if (delta > 0 && delta < 350) {
      // Double-click → go back to the previous slide.
      setDemoSlideIndex((idx) => Math.max(0, idx - 1));
      return;
    }
    if (demoSlideIndex >= DEMO_SLIDES.length) return;
    const current = DEMO_SLIDES[demoSlideIndex];
    if (!current) return;
    setDemoSlideIndex(demoSlideIndex + 1);
  };
  const advanceDemoSlide = handleDemoOverlayPress;

  // Apply slide effects when demoSlideIndex changes.
  useEffect(() => {
    if (!demoActive) return;
    if (demoSlideIndex < 0) return;
    const slide = DEMO_SLIDES[demoSlideIndex];
    if (!slide) {
      stopDemoFlow();
      return;
    }
    if (slide.kind === "end") {
      stopDemoFlow();
      return;
    }
    // Whenever the slide is not a precedent slide, ensure the detail panel
    // is closed so re-entering the answer view (via "다음" or via
    // double-click going back from a precedent slide) doesn't leave a stale
    // drawer open.
    if (slide.kind !== "precedent" && detailOpen) {
      setDetailOpen(false);
    }
    if (slide.kind === "scroll") {
      scrollToHeadingAnchor(slide.anchor);
      return;
    }
    if (slide.kind === "precedent") {
      if (slide.anchor) scrollToHeadingAnchor(slide.anchor);
      if (slide.precedentId) {
        setTargetQuoteText("");
        setSelectedPrecedentId(slide.precedentId);
        setDetailOpen(true);
        setPrecedentsExpanded(true);
      }
      return;
    }
    if (slide.kind === "back") {
      setDetailOpen(false);
      return;
    }
    if (slide.kind === "claim_cards") {
      // Scroll to the claim card stack at the bottom of the answer card.
      if (Platform.OS === "web" && typeof document !== "undefined") {
        const t = setTimeout(() => {
          const node = document.getElementById("lawkey-claim-stack-anchor") as HTMLElement | null;
          if (node && typeof node.scrollIntoView === "function") {
            try {
              node.scrollIntoView({ behavior: "smooth", block: "start" });
            } catch {
              node.scrollIntoView();
            }
          }
        }, 60);
        demoTimersRef.current.push(t);
      }
      return;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demoActive, demoSlideIndex]);

  const triggerAdminReplay = (snapshot: AdminReplaySnapshot) => {
    pendingConversationScrollTargetRef.current = "bottom";
    setPrompt("");
    setComposerSendsNewRequest(false);
    setPrecedentsExpanded(false);
    setQuestionMessages([{ role: "user", text: snapshot.prompt }]);
    setSubmittedPrompt(snapshot.prompt);
    setMode("question");
    setPendingTurn({
      id: `${Date.now()}-replay-${snapshot.jobId}`,
      mode: "question",
      text: snapshot.prompt,
    });
    setReplayInFlight(true);
    beginReplay(snapshot.jobId);
    if (replayCancelRef.current) {
      replayCancelRef.current();
      replayCancelRef.current = null;
    }
    replayCancelRef.current = runAdminReplay({
      snapshot,
      jobId: snapshot.jobId,
      onUpdate: (nextStatus) => {
        pushReplayStatus(nextStatus);
      },
      onComplete: (finalResult, finalStatus) => {
        finishReplay(finalStatus, finalResult);
        setPendingTurn(null);
        setReplayInFlight(false);
        replayCancelRef.current = null;
      },
    });
  };

  const handleSubmit = async () => {
    // Admin replay short-circuit: if the user re-entered a cached job from
    // history, ignore whatever they actually typed and re-play the stored
    // session through the predefined 2 s/stage loader sequence.
    if (isAdmin && replayArmedJobId) {
      const snapshot = loadAdminReplaySnapshot(replayArmedJobId);
      if (snapshot) {
        setReplayArmedJobId("");
        triggerAdminReplay(snapshot);
        return;
      }
      // Snapshot was wiped — disarm and fall through to a real send.
      setReplayArmedJobId("");
    }
    if (!prompt.trim()) {
      return;
    }
    const nextPrompt = prompt.trim();
    pendingConversationScrollTargetRef.current = "bottom";
    const shouldSendAsNewRequest = composerSendsNewRequest;
    const activeClientId = browserClientId || getBrowserClientId();
    if (!browserClientId && activeClientId) {
      setBrowserClientId(activeClientId);
    }
    setPrompt("");
    setComposerSendsNewRequest(false);
    setPrecedentsExpanded(false);
    let routedMode = resolvePromptSubmitMode(mode, nextPrompt);
    // Show an optimistic pending turn IMMEDIATELY so the user sees their
    // message bubble + loader while intent classification runs. If the
    // eventual route turns out to be `document`, the document-setup branch
    // below resets these states.
    const optimisticPendingId = `${Date.now()}-optimistic`;
    if (mode === "question" && routedMode === "question") {
      const previousPrompt = submittedPrompt.trim();
      const hasExistingMessages = questionMessages.length > 0 || previousPrompt.length > 0;
      const optimisticQuestionMessages = shouldSendAsNewRequest || !hasExistingMessages
        ? [{ role: "user" as const, text: nextPrompt }]
        : [
            ...(questionMessages.length
              ? questionMessages
              : previousPrompt
                ? [{ role: "user" as const, text: previousPrompt }]
                : []),
            { role: "user" as const, text: nextPrompt },
          ];
      setQuestionMessages(optimisticQuestionMessages);
      if (!shouldSendAsNewRequest) {
        setSubmittedPrompt(previousPrompt || nextPrompt);
      } else {
        setSubmittedPrompt(nextPrompt);
      }
      setPendingTurn({
        id: optimisticPendingId,
        mode: "question",
        text: nextPrompt,
        sourceJobId: activeJobId || "",
      });
      // Persist draft now so reloading while the follow-up is in-flight still
      // restores the pending message + loader.
      const previousPromptForSnapshot = submittedPrompt.trim();
      persistDraftSnapshot({
        questionMessages: optimisticQuestionMessages,
        submittedPrompt: shouldSendAsNewRequest ? nextPrompt : (previousPromptForSnapshot || nextPrompt),
        pendingTurn: {
          id: optimisticPendingId,
          mode: "question",
          text: nextPrompt,
          sourceJobId: activeJobId || "",
        },
      });
    }
    // Ask Gemma to classify intent. If Gemma says document, route to document
    // setup (preset/upload selection first, clarification AFTER user picks).
    if (mode === "question" && routedMode === "question") {
      try {
        const priorAnswer = shouldSendAsNewRequest ? "" : getVisibleQuestionAnswerMarkdown();
        const context = priorAnswer
          ? `${submittedPrompt.trim()}\n\n이전 답변 요약:\n${priorAnswer.slice(0, 2000)}`
          : "";
        const intentResult = await classifyIntent({ userTask: nextPrompt, context });
        if (intentResult.intent === "document") {
          routedMode = "document";
        }
      } catch {
        /* on failure keep the rule-based result */
      }
    }
    if (routedMode === "document") {
      const sourcePrompt = shouldSendAsNewRequest ? "" : submittedPrompt.trim() || status?.userTask || findSessionPrompt(history, activeJobId);
      const nextThread = buildDocumentConversationItems({
        documentMessages: shouldSendAsNewRequest ? [] : documentMessages,
        submittedPrompt: shouldSendAsNewRequest ? "" : submittedPrompt,
        sourcePrompt,
        questionMessages: shouldSendAsNewRequest ? [] : questionMessages,
        answerMarkdown: shouldSendAsNewRequest ? "" : getVisibleQuestionAnswerMarkdown(),
        nextPrompt,
      });
      if (
        shouldStartDocumentSetup({
          inputMode: mode,
          routedMode,
          documentPresetConfirmed,
          shouldSendAsNewRequest,
        })
      ) {
        startDocumentSetup({ nextPrompt, nextThread });
        return;
      }
      await startDocumentDraft({
        nextPrompt,
        nextThread,
        activeClientId,
        selectedPresetId: documentPresetId,
        selectedSamplePath: samplePath.trim(),
        sourceJobId: activeJobId || "",
      });
      return;
    }
    if (!shouldSendAsNewRequest && activeJobId && result?.answerMarkdown && (!status || status.state === "completed")) {
      const previousPrompt = submittedPrompt.trim();
      const nextQuestionMessages = [...(questionMessages.length ? questionMessages : previousPrompt ? [{ role: "user" as const, text: previousPrompt }] : []), { role: "user" as const, text: nextPrompt }];
      const previousAnswerMarkdown = getVisibleQuestionAnswerMarkdown();
      if (previousAnswerMarkdown) {
        // Carry over the previous job's selectedPrecedents so hyperlinks in
        // the earlier assistant bubble keep resolving even after the active
        // job (and its `result`) flips to the follow-up.
        const carriedPrecedents = (carriedQuestionAnswer?.selectedPrecedents ?? [])
          .concat(result?.selectedPrecedents ?? []);
        setCarriedQuestionAnswer({
          sourceJobId: activeJobId,
          markdown: previousAnswerMarkdown,
          selectedPrecedents: carriedPrecedents,
        });
      }
      setContinuationSourceJobId(activeJobId);
      setQuestionMessages(nextQuestionMessages);
      setSubmittedPrompt(previousPrompt || nextPrompt);
      setPendingTurn({ id: `${Date.now()}-follow-up`, mode: "question", text: nextPrompt, sourceJobId: activeJobId });
      persistDraftSnapshot({
        prompt: "",
        submittedPrompt: previousPrompt || nextPrompt,
        questionMessages: nextQuestionMessages,
      });
      try {
        const response = await followUp({
          userTask: nextPrompt,
          clientId: activeClientId,
          forceNewJob: true,
        });
        if (response.mode === "new_job_started") {
          persistDraftSnapshot({ prompt: "", submittedPrompt: previousPrompt || nextPrompt, questionMessages: nextQuestionMessages });
        } else {
          setPendingTurn(null);
        }
      } catch {
        setPrompt(nextPrompt);
        setPendingTurn(null);
      }
      return;
    }
    setSubmittedPrompt(nextPrompt);
    setCarriedQuestionAnswer(null);
    setContinuationSourceJobId("");
    setQuestionMessages([{ role: "user", text: nextPrompt }]);
    setDocumentMessages([]);
    setDocumentPresetConfirmed(false);
    setPendingDocumentSetup(null);
    setPendingTurn({ id: `${Date.now()}-question`, mode: "question", text: nextPrompt, sourceJobId: activeJobId || "" });
    await submit({
      mode,
      userTask: nextPrompt,
      clientId: activeClientId,
      documentPresetId: undefined,
      samplePath: undefined,
      analysisMode,
      skipIntentCheck: true,
    });
  };

  const handleEditPrompt = (text: string, targetMode: "question" | "document") => {
    const nextText = text.trim();
    if (!nextText) {
      return;
    }
    const routedMode = resolvePromptSubmitMode(targetMode, nextText);
    setMode(routedMode);
    setPrompt(nextText);
    setComposerSendsNewRequest(true);
  };

  const handleRetryPrompt = async (text: string, targetMode: "question" | "document") => {
    const nextPrompt = text.trim();
    if (!nextPrompt || submitting) {
      return;
    }
    const routedMode = resolvePromptSubmitMode(targetMode, nextPrompt);
    pendingConversationScrollTargetRef.current = "bottom";
    const activeClientId = browserClientId || getBrowserClientId();
    if (!browserClientId && activeClientId) {
      setBrowserClientId(activeClientId);
    }
    setMode(routedMode);
    setCarriedQuestionAnswer(null);
    setContinuationSourceJobId("");
    setPrompt("");
    setPrecedentsExpanded(false);
    setDetailOpen(false);
    if (routedMode === "document") {
      const nextThread: DocumentConversationItem[] = [{ role: "user", text: nextPrompt }];
      setSubmittedPrompt("");
      setQuestionMessages([]);
      setDocumentMessages(nextThread);
      setPendingTurn({ id: `${Date.now()}-retry-document`, mode: "document", text: nextPrompt, sourceJobId: activeJobId || "" });
      const preflight = await preflightDocument({
        userTask: nextPrompt,
        documentPresetId,
        samplePath: samplePath.trim() || undefined,
        sourceJobId: activeJobId || undefined,
        conversation: nextThread,
      }).catch(() => null);
      const draftRequest = buildDocumentDraftRequest({
        currentPrompt: nextPrompt,
        conversation: nextThread,
        preflight,
      });
      if (draftRequest.assistantMessage) {
        setDocumentMessages([...nextThread, { role: "assistant", text: draftRequest.assistantMessage }]);
      }
      setSubmittedPrompt(draftRequest.draftingGoal);
      if (!draftRequest.shouldSubmit) {
        setPendingTurn(null);
        return;
      }
      await submit({
        mode: "document",
        userTask: draftRequest.retrievalTask,
        clientId: activeClientId,
        documentPresetId,
        documentContext: draftRequest.documentContext,
        samplePath: samplePath.trim() || undefined,
        analysisMode,
      skipIntentCheck: true,
      });
      return;
    }
    setSubmittedPrompt(nextPrompt);
    setQuestionMessages([{ role: "user", text: nextPrompt }]);
    setDocumentMessages([]);
    setPendingTurn({ id: `${Date.now()}-retry-question`, mode: "question", text: nextPrompt, sourceJobId: activeJobId || "" });
    await submit({
      mode: "question",
      userTask: nextPrompt,
      clientId: activeClientId,
      documentPresetId: undefined,
      samplePath: undefined,
      analysisMode,
      skipIntentCheck: true,
    });
  };

  const handleCancelActiveJob = async () => {
    if (!canCancelRequest) {
      return;
    }
    try {
      await cancelActiveJob();
    } finally {
      setPendingTurn(null);
    }
  };

  const pickCustomSampleFile = async (): Promise<{ path: string; label: string } | null> => {
    if (typeof document === "undefined" || filePickerBusy.current) {
      return null;
    }
    filePickerBusy.current = true;
    return new Promise((resolve) => {
      const input = document.createElement("input");
      input.type = "file";
      input.accept = ".md,.txt,.pdf,.hwp,.hwpx,.doc,.docx";
      const finish = (value: { path: string; label: string } | null) => {
        filePickerBusy.current = false;
        resolve(value);
      };
      input.onchange = async () => {
        try {
          const file = input.files?.[0];
          if (!file) {
            finish(null);
            return;
          }
          const uploaded = await uploadSampleFile(file);
          finish({ path: uploaded.path, label: uploaded.label || file.name });
        } catch (caught) {
          console.error(caught);
          finish(null);
        }
      };
      (input as unknown as { oncancel?: () => void }).oncancel = () => finish(null);
      input.click();
    });
  };

  const handleCustomFilePick = async () => {
    const uploaded = await pickCustomSampleFile();
    if (!uploaded) {
      return;
    }
    setUseCustomSamplePath(true);
    setSamplePath(uploaded.path);
    setUploadedSampleLabel(uploaded.label);
  };

  const handleUploadDocumentSetupFile = async () => {
    const setup = pendingDocumentSetup;
    if (!setup || submitting) {
      return;
    }
    const uploaded = await pickCustomSampleFile();
    if (!uploaded) {
      return;
    }
    const activeClientId = browserClientId || getBrowserClientId();
    if (!browserClientId && activeClientId) {
      setBrowserClientId(activeClientId);
    }
    setUseCustomSamplePath(true);
    setSamplePath(uploaded.path);
    setUploadedSampleLabel(uploaded.label);
    await startDocumentDraft({
      nextPrompt: setup.prompt,
      nextThread: setup.conversation,
      activeClientId,
      selectedPresetId: documentPresetId,
      selectedSamplePath: uploaded.path,
      displayMessages: documentMessages,
      sourceJobId: setup.sourceJobId,
    });
  };

  const visibleAnalysisModeOptions = useMemo(() => getVisibleAnalysisModeOptions(isAdmin), [isAdmin]);
  const analysisModeTriggerLabel = getAnalysisModeLabel(analysisMode, isAdmin);

  const submitAdminLogin = () => {
    if (!isPresentationAuthValid(loginUsername, loginPassword)) {
      setLoginError("아이디 또는 비밀번호가 올바르지 않습니다.");
      return;
    }
    persistAuthState(true);
    setIsAdmin(true);
    setLoginError("");
    setLoginPassword("");
    setLoginDialogOpen(false);
    setAnalysisModeState((current) => normalizeAnalysisModeForRole(current, true));
  };

  const clearLoginOpenTimer = () => {
    if (loginOpenTimerRef.current) {
      clearTimeout(loginOpenTimerRef.current);
      loginOpenTimerRef.current = null;
    }
  };

  const startHiddenDemoFromLogin = () => {
    clearLoginOpenTimer();
    loginLastPressAtRef.current = 0;
    setModeMenuOpen(false);
    setLoginDialogOpen(false);
    startDemoFlow();
  };

  const handleStartNewCase = () => {
    pendingConversationScrollTargetRef.current = "bottom";
    resetView();
    setPrompt("");
    setComposerSendsNewRequest(false);
    setPendingDocumentSetup(null);
    setDocumentPresetConfirmed(false);
    setSubmittedPrompt("");
    setQuestionMessages([]);
    setDocumentMessages([]);
    setSamplePath("");
    setUploadedSampleLabel("");
    setDocumentPresetId("");
    setUseCustomSamplePath(false);
    setDetailOpen(false);
    setPrecedentsExpanded(false);
    setSidebarOpen(false);
    if (typeof window !== "undefined") {
      try {
        writeTabStorage(LAST_SESSION_STORAGE_KEY, "");
        writeTabStorage(DRAFT_STORAGE_KEY, "");
      } catch {
        // Ignore local storage quota issues.
      }
    }
    saveViewedSessionId("");
    if (activeJobId) {
      clearSessionSnapshot(activeJobId);
    }
  };

  return (
    <View style={styles.appContainer}>
      {compact && sidebarOpen ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="사이드바 닫기"
          onPress={() => setSidebarOpen(false)}
          style={styles.sidebarScrim}
        />
      ) : null}
      <View style={[styles.sidebar, compact ? styles.sidebarCompact : null, compact && sidebarOpen ? styles.sidebarOpen : null]}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="새로운 사건 분석"
          onPress={handleStartNewCase}
          style={({ pressed }) => [styles.brandRow, pressed ? styles.buttonPressed : null]}
        >
          <LawkeyLogo style={styles.sidebarLogo} monochrome compact />
          <Text style={styles.brand}>Lawkey AI</Text>
        </Pressable>
        <Pressable
          accessibilityRole="button"
          onPress={handleStartNewCase}
          style={({ pressed }) => [styles.newRunButton, pressed ? styles.buttonPressed : null]}
        >
          <Text style={styles.newRunText}>+ 새로운 사건 분석</Text>
        </Pressable>
        <View style={styles.history}>
          <Text style={styles.historyTitle}>최근 목록</Text>
          <ScrollView
            nativeID="lawkey-history-scroll"
            style={styles.historyScroll}
            contentContainerStyle={styles.historyScrollContent}
            showsVerticalScrollIndicator={false}
          >
            {visibleHistory.length ? (
              visibleHistory.map((item) => (
                <View key={item.id} style={styles.historyItem}>
                  <View style={styles.historyItemRow}>
                    <Pressable
                      accessibilityRole="button"
                      onPress={() => {
                        pendingConversationScrollTargetRef.current = "latestAnswerStart";
                        setComposerSendsNewRequest(false);
                        setPendingDocumentSetup(null);
                        setDocumentPresetConfirmed(false);
                        writeTabStorage(LAST_SESSION_STORAGE_KEY, item.id);
                        setPrecedentsExpanded(false);
                        setSidebarOpen(false);
                        resetView();
                        // Admin replay path: if a snapshot exists, reset the
                        // viewport to "ready to send" and arm the replay so
                        // the next submit re-plays the predefined stages
                        // followed by the cached answer.
                        const adminSnapshot = isAdmin ? loadAdminReplaySnapshot(item.id) : null;
                        if (adminSnapshot) {
                          if (replayCancelRef.current) {
                            replayCancelRef.current();
                            replayCancelRef.current = null;
                          }
                          setReplayInFlight(false);
                          setPendingTurn(null);
                          setSubmittedPrompt("");
                          setQuestionMessages([]);
                          setDocumentMessages([]);
                          setReplayArmedJobId(item.id);
                          saveViewedSessionId(item.id);
                          return;
                        }
                        setSubmittedPrompt(item.prompt || item.title || "");
                        setQuestionMessages(item.prompt || item.title ? [{ role: "user", text: item.prompt || item.title || "" }] : []);
                        void (async () => {
                          const snapshot = loadSessionSnapshot(item.id);
                          applySnapshotState(snapshot);
                          const localStatus = loadStatusSnapshot(item.id) || (await loadStatusSnapshotAsync(item.id));
                          const localResult = loadResultSnapshot(item.id) || (await loadResultSnapshotAsync(item.id));
                          if (localStatus || localResult) {
                            restoreLocalJob({
                              jobId: item.id,
                              status: localStatus,
                              result: localResult,
                              selectedPrecedentId: snapshot?.selectedPrecedentId,
                            });
                          } else {
                            openJob(item.id);
                          }
                        })();
                        saveViewedSessionId(item.id);
                      }}
                      style={({ pressed }) => [styles.historyItemButton, item.id === activeJobId ? styles.historyItemButtonActive : null, pressed ? styles.buttonPressed : null]}
                    >
                      <Text style={styles.historyItemTitle}>{item.title}</Text>
                      <Text style={styles.historyItemMeta}>{item.meta}</Text>
                    </Pressable>
                    <Pressable
                      accessibilityRole="button"
                      accessibilityLabel="목록에서 삭제"
                      onPress={() => {
                        markSessionDeleted(item.id);
                        if (item.id === activeJobId) {
                          resetView();
                          setSubmittedPrompt("");
                          setQuestionMessages([]);
                          setDocumentMessages([]);
                          writeTabStorage(LAST_SESSION_STORAGE_KEY, "");
                          saveViewedSessionId("");
                        }
                        setHistory((current) => current.filter((row) => row.id !== item.id));
                        setDeletedIdsTick((tick) => tick + 1);
                      }}
                      style={({ pressed }) => [styles.historyDeleteButton, pressed ? styles.buttonPressed : null]}
                    >
                      <Text style={styles.historyDeleteText}>×</Text>
                    </Pressable>
                  </View>
                </View>
              ))
            ) : (
              <Text style={styles.historyItemMeta}>실행한 세션이 여기에 누적됩니다.</Text>
            )}
          </ScrollView>
        </View>
      </View>

      <View style={styles.mainContent}>
        <View style={styles.topRightBar} pointerEvents="box-none">
          <LoginButton
            onPress={() => {
              const action = resolveLoginButtonPress({
                now: Date.now(),
                lastPressAt: loginLastPressAtRef.current,
                demoActive,
              });
              loginLastPressAtRef.current = action.nextLastPressAt;
              if (action.action === "open-login") {
                clearLoginOpenTimer();
                setModeMenuOpen(false);
                setLoginError("");
                loginOpenTimerRef.current = setTimeout(() => {
                  loginOpenTimerRef.current = null;
                  setLoginDialogOpen(true);
                }, 280);
              } else if (action.action === "start-demo") {
                startHiddenDemoFromLogin();
              }
            }}
            onDoubleClick={startHiddenDemoFromLogin}
          />
        </View>
        {loginDialogOpen && !demoActive ? (
          <View style={styles.loginDialogLayer} pointerEvents="box-none">
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="로그인 창 닫기"
              onPress={() => setLoginDialogOpen(false)}
              style={styles.loginDialogBackdrop}
            />
            <View style={styles.loginDialogCard}>
              <Text style={styles.loginDialogTitle}>로그인</Text>
              <Text style={styles.loginDialogSubtitle}>관리자 계정으로 로그인하면 베타 분석 모드가 표시됩니다.</Text>
              <Text style={styles.loginDialogLabel}>아이디</Text>
              <TextInput
                accessibilityLabel="아이디"
                autoCapitalize="none"
                autoCorrect={false}
                placeholder="admin"
                placeholderTextColor="#9ca3af"
                value={loginUsername}
                onChangeText={(value) => {
                  setLoginUsername(value);
                  if (loginError) setLoginError("");
                }}
                onSubmitEditing={submitAdminLogin}
                style={[styles.loginDialogInput, webTextInputFocusReset as any]}
              />
              <Text style={styles.loginDialogLabel}>비밀번호</Text>
              <TextInput
                accessibilityLabel="비밀번호"
                autoCapitalize="none"
                autoCorrect={false}
                placeholder="비밀번호"
                placeholderTextColor="#9ca3af"
                secureTextEntry
                value={loginPassword}
                onChangeText={(value) => {
                  setLoginPassword(value);
                  if (loginError) setLoginError("");
                }}
                onSubmitEditing={submitAdminLogin}
                style={[styles.loginDialogInput, webTextInputFocusReset as any]}
              />
              {loginError ? <Text style={styles.loginDialogError}>{loginError}</Text> : null}
              <View style={styles.loginDialogActions}>
                <Pressable
                  accessibilityRole="button"
                  onPress={() => setLoginDialogOpen(false)}
                  style={({ pressed }) => [styles.loginDialogCancel, pressed ? styles.buttonPressed : null]}
                >
                  <Text style={styles.loginDialogCancelText}>취소</Text>
                </Pressable>
                <Pressable
                  accessibilityRole="button"
                  onPress={submitAdminLogin}
                  style={({ pressed }) => [styles.loginDialogSubmit, pressed ? styles.buttonPressed : null]}
                >
                  <Text style={styles.loginDialogSubmitText}>로그인</Text>
                </Pressable>
              </View>
            </View>
          </View>
        ) : null}
        {demoActive && demoSlideIndex >= 0 && demoSlideIndex < DEMO_SLIDES.length ? (
          <>
            {/* Click anywhere on the conversation/drawer area to advance
                the demo. Double-click within 350 ms goes back to the
                previous slide. The handler in `handleDemoOverlayPress`
                distinguishes the two via timestamp. */}
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="데모 다음 단계 (더블 클릭: 이전)"
              onPress={advanceDemoSlide}
              style={styles.demoOverlayClickCatcher}
            />
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="데모 다음 단계"
              onPress={advanceDemoSlide}
              style={({ pressed }) => [styles.demoOverlayHint, pressed ? styles.buttonPressed : null]}
            >
              <View style={styles.demoOverlayBadge}>
                <Text style={styles.demoOverlayBadgeText}>{Math.min(demoSlideIndex + 1, DEMO_SLIDES.length)}</Text>
              </View>
              <Text style={styles.demoOverlayHintText}>
                {(() => {
                  const slide = DEMO_SLIDES[demoSlideIndex];
                  return slide && slide.kind !== "end" ? "다음 →" : "데모 종료";
                })()}
              </Text>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="데모 종료"
                onPress={stopDemoFlow}
                style={({ pressed }) => [styles.adminEditButton, pressed ? styles.buttonPressed : null, { marginLeft: 6 }]}
              >
                <Text style={styles.adminEditButtonText}>×</Text>
              </Pressable>
            </Pressable>
          </>
        ) : null}
        {compact ? (
          <View style={styles.mobileTopBar}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="사이드바 열기"
              onPress={() => setSidebarOpen(true)}
              style={({ pressed }) => [styles.mobileMenuButton, pressed ? styles.buttonPressed : null]}
            >
              <View style={styles.mobileMenuLine} />
              <View style={styles.mobileMenuLine} />
              <View style={styles.mobileMenuLine} />
            </Pressable>
            <View pointerEvents="box-none" style={styles.mobileTopBrand}>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="새로운 사건 분석"
                onPress={handleStartNewCase}
                style={({ pressed }) => [styles.mobileTopBrandButton, pressed ? styles.buttonPressed : null]}
              >
                <LawkeyLogo compact style={styles.mobileTopLogo} />
                <Text style={styles.mobileTopTitle}>Lawkey AI</Text>
              </Pressable>
            </View>
          </View>
        ) : null}

        <View
          pointerEvents="box-none"
          style={[styles.modeSwitcherRow, compact ? styles.modeSwitcherRowCompact : null]}
        >
          <Pressable
            accessibilityRole="button"
            onPress={() => setModeMenuOpen((v) => !v)}
            style={({ pressed }) => [styles.modeTriggerButton, pressed ? styles.buttonPressed : null]}
          >
            <Text style={styles.modeTriggerLabel}>{analysisModeTriggerLabel}</Text>
            <Text style={styles.modeTriggerChevron}>{modeMenuOpen ? "▴" : "▾"}</Text>
          </Pressable>
          {modeMenuOpen ? (
            <>
              <Pressable style={styles.modeMenuBackdrop} onPress={() => setModeMenuOpen(false)} />
              <View style={styles.modeMenu}>
                {visibleAnalysisModeOptions.map((item) => (
                  <Pressable
                    key={item.mode}
                    onPress={() => {
                      setAnalysisMode(item.mode);
                      setModeMenuOpen(false);
                    }}
                    style={({ pressed }) => [styles.modeMenuItem, pressed ? styles.modeMenuItemHover : null]}
                  >
                    <View style={styles.modeMenuItemHeader}>
                      <Text style={styles.modeMenuItemTitle}>{item.title}</Text>
                      {analysisMode === item.mode ? <Text style={styles.modeMenuItemCheck}>✓</Text> : null}
                    </View>
                    <Text style={styles.modeMenuItemDesc}>{item.description}</Text>
                  </Pressable>
                ))}
              </View>
            </>
          ) : null}
        </View>

        <ScrollView
          ref={conversationScrollRef}
          contentContainerStyle={[styles.chatContainer, compact ? styles.chatContainerCompact : null]}
          showsVerticalScrollIndicator={false}
          scrollEventThrottle={16}
          onScroll={(event) => {
            const y = event.nativeEvent.contentOffset.y;
            const layoutHeight = event.nativeEvent.layoutMeasurement?.height ?? lastViewportHeightRef.current;
            const contentHeight = event.nativeEvent.contentSize?.height ?? lastContentHeightRef.current;
            lastScrollYRef.current = y;
            if (layoutHeight) lastViewportHeightRef.current = layoutHeight;
            if (contentHeight) lastContentHeightRef.current = contentHeight;
            // "Near the bottom" tolerance: ~120px so a one-line layout shift
            // doesn't unstick the user from auto-follow.
            const distanceFromBottom = Math.max(0, contentHeight - layoutHeight - y);
            userScrolledAwayRef.current = distanceFromBottom > 120;
          }}
          onLayout={(event) => {
            lastViewportHeightRef.current = event.nativeEvent.layout.height;
          }}
          onContentSizeChange={(_, height) => {
            lastContentHeightRef.current = height;
            if (!showConversation || detailOpen) {
              return;
            }
            // Don't auto-scroll-to-end while we're trying to restore the
            // saved reading position after closing a precedent detail.
            if (savedAnswerScrollYRef.current != null) {
              return;
            }
            // Only scroll-to-end as a one-shot right after the user actively
            // submitted a new prompt or switched chats. Never follow the
            // bottom on subsequent layout changes (loader updates, answer
            // arrival, chunk progress) — the user explicitly asked not to be
            // yanked while reading.
            if (pendingScrollToEndRef.current && Date.now() < pendingScrollToEndExpiryRef.current) {
              pendingScrollToEndRef.current = false;
              pendingScrollToEndExpiryRef.current = 0;
              const scrollTarget = pendingConversationScrollTargetRef.current;
              // Restoring an old conversation should land on the beginning of
              // the latest assistant answer. New submissions still go to the
              // loader/bottom so the user sees progress immediately.
              if (scrollTarget === "latestAnswerStart" && typeof document !== "undefined") {
                const aiBubbles = document.querySelectorAll<HTMLElement>('[data-ai-bubble="1"]');
                const last = aiBubbles[aiBubbles.length - 1];
                if (last && typeof last.scrollIntoView === "function") {
                  try {
                    last.scrollIntoView({ behavior: "smooth", block: "start", inline: "nearest" });
                  } catch {
                    last.scrollIntoView();
                  }
                  return;
                }
              }
              conversationScrollRef.current?.scrollToEnd({ animated: true });
            } else if (pendingScrollToEndRef.current) {
              // Expired — treat as already consumed so a stale flag never
              // triggers scroll on a future content-size change.
              pendingScrollToEndRef.current = false;
              pendingScrollToEndExpiryRef.current = 0;
            }
          }}
        >
          {showWelcome ? (
            <View style={styles.welcomeScreen}>
              <LawkeyLogo style={styles.welcomeLogo} />
              <Text
                adjustsFontSizeToFit
                minimumFontScale={0.72}
                numberOfLines={1}
                style={[styles.welcomeTitle, compact ? { fontSize: welcomeTitleFontSize, lineHeight: welcomeTitleLineHeight } : null]}
              >
                무엇을 도와드릴까요?
              </Text>
              <Text style={styles.welcomeBody}>
                Lawkey AI는 최신 판례를 기반으로{`\n`}전문적인 법리 분석과 법률 문서 초안을 제공합니다.
              </Text>
            </View>
          ) : null}

          {showConversation ? (
            <>
              {conversationMode === "question"
                ? questionConversationTurns.map((turn, index) => {
                    if (turn.type === "user") {
                      // When a precedent detail is open, the user has clicked a
                      // hyperlink to focus on one judgment. Hide the chat turns
                      // above so only the detail pane fills the viewport.
                      if (detailOpen) return null;
                      return (
                        <View key={`question-user-${index}`} style={styles.messageWrapper}>
                          <View style={styles.userMessage}>
                            <Text style={styles.userMessageText}>{turn.text}</Text>
                            <MessageActionRow
                              disabled={submitting}
                              onEdit={() => handleEditPrompt(turn.text, "question")}
                              onRetry={() => {
                                void handleRetryPrompt(turn.text, "question");
                              }}
                            />
                          </View>
                        </View>
                      );
                    }
                    if (turn.type === "loader") {
                      return (
                        <View key={`question-loader-${index}`} style={styles.messageWrapper}>
                          <View style={styles.aiMessage}>
                            <View style={styles.loaderCard}>
                              <ProgressStrip
                                state={loaderState}
                                completedChunks={loaderStatus?.completedChunks ?? 0}
                                totalChunks={loaderStatus?.totalChunks ?? 0}
                                etaSeconds={loaderStatus?.etaSeconds ?? 0}
                                elapsedSeconds={loaderStatus?.elapsedSeconds ?? 0}
                                workerCount={loaderStatus?.workerCount ?? 10}
                                apiInflight={loaderStatus?.scheduler?.inflight ?? 0}
                                lastApiActivityAt={loaderStatus?.lastApiActivityAt}
                                lastApiEvent={loaderStatus?.lastApiEvent}
                                constrained={constrained}
                                headline={loaderHeadline}
                                selectionKeywords={loaderStatus?.selectionKeywords}
                              />
                              <RequestActionRow
                                canCancel={canCancelRequest}
                                onCancel={() => {
                                  void handleCancelActiveJob();
                                }}
                              />
                            </View>
                          </View>
                        </View>
                      );
                    }
                    if (detailOpen) {
                      return null;
                    }
                    const assistantIndex = questionConversationTurns
                      .slice(0, index + 1)
                      .filter((candidate) => candidate.type === "assistant").length;
                    const isFirstAssistant = assistantIndex === 1;
                    const isLastAssistant = assistantIndex === questionAssistantTurnCount;
                    return (
                      <View key={`question-assistant-${index}`} style={styles.messageWrapper}>
                        <View {...aiBubbleDataProps} style={styles.aiMessage}>
                          <View style={styles.aiHeader}>
                            <LawkeyLogo compact />
                            <Text style={styles.aiHeaderText}>{isFirstAssistant ? "Lawkey 분석 결과" : "Lawkey 이어서 답변"}</Text>
                          </View>
                          {isLastAssistant && resultElapsedLabel ? <Text style={styles.resultMetaText}>{resultElapsedLabel}</Text> : null}

                          {/* The answerPlan/claims in `result` belong to the
                             *currently* active job. Attaching them to the
                             first (oldest) assistant turn caused the new
                             conclusion to visually jump to the top of the
                             previous answer. Render the summary card next to
                             the most recent assistant turn instead. */}
                          {isLastAssistant && analysisMode !== "beta7" && shouldShowSeparateAnalysisSummaryCard({
                            answerMarkdown: turn.text,
                            hasAnswerPlan: !!result?.answerPlan,
                            hasClaims: !!(result?.selectedClaims?.length || result?.claims?.length),
                          }) ? (
                            <AnalysisSummaryCard answerPlan={result?.answerPlan} claims={result?.selectedClaims?.length ? result.selectedClaims : result?.claims ?? []} />
                          ) : null}

                          {isLastAssistant && isAdmin && answerEditDraft != null ? (
                            <View style={styles.adminEditorWrap}>
                              <TextInput
                                accessibilityLabel="관리자 답변 편집"
                                multiline
                                value={answerEditDraft}
                                onChangeText={setAnswerEditDraft}
                                style={[styles.adminEditorTextArea, webTextInputFocusReset as any]}
                              />
                              <View style={styles.adminEditorActions}>
                                <Pressable
                                  accessibilityRole="button"
                                  onPress={() => setAnswerEditDraft(null)}
                                  style={({ pressed }) => [styles.adminEditorButton, styles.adminEditorButtonGhost, pressed ? styles.buttonPressed : null]}
                                >
                                  <Text style={styles.adminEditorButtonGhostText}>취소</Text>
                                </Pressable>
                                <Pressable
                                  accessibilityRole="button"
                                  onPress={() => {
                                    const next = String(answerEditDraft || "").trim();
                                    if (!next) return;
                                    if (activeJobId) {
                                      editAdminReplayAnswer(activeJobId, next);
                                    }
                                    updateReplayResultMarkdown(next);
                                    setAnswerEditDraft(null);
                                  }}
                                  style={({ pressed }) => [styles.adminEditorButton, pressed ? styles.buttonPressed : null]}
                                >
                                  <Text style={styles.adminEditorButtonText}>저장</Text>
                                </Pressable>
                              </View>
                            </View>
                          ) : (
                            <MarkdownView
                              markdown={turn.text}
                              mode="question"
                              precedents={[
                                ...(carriedQuestionAnswer?.selectedPrecedents ?? []),
                                ...(result?.selectedPrecedents ?? []),
                              ]}
                              onOpenPrecedent={openPrecedentDetail}
                            />
                          )}
                          {isLastAssistant && isAdmin && answerEditDraft == null ? (
                            <Pressable
                              accessibilityRole="button"
                              onPress={() => setAnswerEditDraft(turn.text)}
                              style={({ pressed }) => [styles.adminEditButton, pressed ? styles.buttonPressed : null]}
                            >
                              <Text style={styles.adminEditButtonText}>관리자: 답변 편집</Text>
                            </Pressable>
                          ) : null}

                          {isLastAssistant ? <LegalDisclaimer /> : null}
                          {isLastAssistant && result && (result.selectedClaims?.length || result.claims.length) ? (
                            <View nativeID="lawkey-claim-stack-anchor" style={styles.claimStack}>
                              <Text style={styles.claimStackTitle}>선택된 주장</Text>
                              <GroupedClaims
                                claims={result.selectedClaims?.length ? result.selectedClaims : result.claims}
                                claimGroups={result.answerPlan?.claim_groups}
                                precedents={result.selectedPrecedents}
                                onOpen={(precedentId) => openPrecedentDetail(precedentId)}
                              />
                            </View>
                          ) : null}
                        </View>
                      </View>
                    );
                  })
                : null}

              {conversationMode === "document" && documentMessages.length
                ? documentMessages.map((message, index) => (
                    <View key={`${message.role}-${index}`} style={styles.messageWrapper}>
                      <View
                        {...(message.role === "user" ? {} : aiBubbleDataProps)}
                        style={message.role === "user" ? styles.userMessage : styles.aiMessage}
                      >
                        {message.role === "user" ? (
                          <>
                            <Text style={styles.userMessageText}>{message.text}</Text>
                            <MessageActionRow
                              disabled={submitting}
                              onEdit={() => handleEditPrompt(message.text, "document")}
                              onRetry={() => {
                                void handleRetryPrompt(message.text, "document");
                              }}
                            />
                          </>
                        ) : (
                          <MarkdownView
                            markdown={message.text}
                            mode="question"
                            hideHeader
                            precedents={[
                              ...(carriedQuestionAnswer?.selectedPrecedents ?? []),
                              ...(result?.selectedPrecedents ?? []),
                            ]}
                            onOpenPrecedent={openPrecedentDetail}
                          />
                        )}
                      </View>
                    </View>
                  ))
                : null}

              {conversationMode === "document" && pendingDocumentSetup ? (
                <View style={styles.messageWrapper}>
                  <View style={styles.aiMessage}>
                    <DocumentSetupPanel
                      presets={documentPresets}
                      selectedPresetId={documentPresetId}
                      uploading={submitting || filePickerBusy.current}
                      onSelectPreset={(presetId) => {
                        void handleConfirmDocumentPreset(presetId);
                      }}
                      onUpload={() => {
                        void handleUploadDocumentSetupFile();
                      }}
                    />
                  </View>
                </View>
              ) : null}

              {conversationMode === "document" && showRunLoader ? (
                <View style={styles.messageWrapper}>
                  <View style={styles.aiMessage}>
                    <View style={styles.loaderCard}>
                      <ProgressStrip
                        state={loaderState}
                        completedChunks={loaderStatus?.completedChunks ?? 0}
                        totalChunks={loaderStatus?.totalChunks ?? 0}
                        etaSeconds={loaderStatus?.etaSeconds ?? 0}
                        elapsedSeconds={loaderStatus?.elapsedSeconds ?? 0}
                        workerCount={loaderStatus?.workerCount ?? 10}
                        apiInflight={loaderStatus?.scheduler?.inflight ?? 0}
                        lastApiActivityAt={loaderStatus?.lastApiActivityAt}
                        lastApiEvent={loaderStatus?.lastApiEvent}
                        constrained={constrained}
                        headline={loaderHeadline}
                        selectionKeywords={loaderStatus?.selectionKeywords}
                      />
                      <RequestActionRow
                        canCancel={canCancelRequest}
                        onCancel={() => {
                          void handleCancelActiveJob();
                        }}
                      />
                    </View>
                  </View>
                </View>
              ) : null}

              {showDocumentResultCard && result?.answerMarkdown ? (
                <View style={styles.messageWrapper}>
                  <View {...aiBubbleDataProps} style={styles.aiMessage}>
                    <View style={styles.aiHeader}>
                      <LawkeyLogo compact />
                      <Text style={styles.aiHeaderText}>Lawkey 분석 결과</Text>
                    </View>
                    {resultElapsedLabel ? <Text style={styles.resultMetaText}>{resultElapsedLabel}</Text> : null}

                    {conversationMode === "document" && (result.outputPaths.markdownUrl || result.outputPaths.hwpxUrl || result.outputPaths.pdfUrl) ? (
                      <View style={styles.exportBar}>
                        <ExportButton label="Markdown" url={result.outputPaths.markdownUrl} />
                        <ExportButton label="HWPX" url={result.outputPaths.hwpxUrl} />
                        <ExportButton label="PDF" url={result.outputPaths.pdfUrl} />
                      </View>
                    ) : null}

                    <MarkdownView
                      markdown={result.answerMarkdown}
                      mode={conversationMode}
                      precedents={result.selectedPrecedents}
                      onOpenPrecedent={openPrecedentDetail}
                    />

                    <LegalDisclaimer />

                    {(result.selectedClaims?.length || result.claims.length) ? (
                      <View style={styles.claimStack}>
                        <Text style={styles.claimStackTitle}>선택된 주장</Text>
                        <GroupedClaims
                          claims={result.selectedClaims?.length ? result.selectedClaims : result.claims}
                          claimGroups={result.answerPlan?.claim_groups}
                          precedents={result.selectedPrecedents}
                          onOpen={(precedentId) => openPrecedentDetail(precedentId)}
                        />
                      </View>
                    ) : null}

                    {conversationMode === "document" && result.outputPaths.previewImageUrls.length ? (
                      <View style={styles.previewCard}>
                        <Text style={styles.previewTitle}>문서 미리보기</Text>
                        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.previewRow}>
                          {result.outputPaths.previewImageUrls.map((url, index) => (
                            <View key={url} style={styles.previewTile}>
                              <Image source={{ uri: url }} style={styles.previewImage} />
                              <Text style={styles.previewCaption}>page {index + 1}</Text>
                            </View>
                          ))}
                        </ScrollView>
                      </View>
                    ) : null}
                  </View>
                </View>
              ) : null}

              {error ? (
                <View style={styles.messageWrapper}>
                  <View style={styles.errorMessage}>
                    <Text style={styles.errorTitle}>오류</Text>
                    <Text style={styles.errorBody}>{error}</Text>
                  </View>
                </View>
              ) : null}
            </>
          ) : null}

          {!pendingTurn && !pendingDocumentSetup && conversationMode === "question" && (result?.selectedPrecedents.length || detailOpen) ? (
            <View style={styles.drawerWrap}>
              {!detailOpen && !precedentsExpanded ? (
                <Pressable
                  accessibilityRole="button"
                  onPress={() => setPrecedentsExpanded(true)}
                  style={({ pressed }) => [styles.precedentToggle, pressed ? styles.buttonPressed : null]}
                >
                  <Text style={styles.precedentToggleTitle}>참고 판례와 원문 보기</Text>
                  <Text style={styles.precedentToggleMeta}>
                    {result?.selectedPrecedents.length || 0}건 선별 · 매우 유사/유사/이용 가능 분류 보기
                  </Text>
                </Pressable>
              ) : (
                <PrecedentDrawer
                  precedents={result?.selectedPrecedents ?? []}
                  usedPrecedents={result?.usedPrecedents ?? []}
                  usedPrecedentIds={result?.usedPrecedentIds ?? []}
                  precedentBuckets={result?.answerPlan?.precedent_buckets}
                  detailOpen={detailOpen}
                  selectedId={selectedPrecedentId}
                  selectedDetail={selectedDetail}
                  targetQuoteText={targetQuoteText}
                  onOpen={(id) => openPrecedentDetail(id)}
                  onBack={() => setDetailOpen(false)}
                />
              )}
            </View>
          ) : null}
        </ScrollView>

        <View style={styles.inputWrapper}>
          <View style={styles.inputBox}>
            <View style={styles.inputModeRow}>
              {workspaceModes.map((item) => {
                const active = item.id === mode;
                return (
                  <Pressable
                    key={item.id}
                    accessibilityRole="button"
                    onPress={() => setMode(item.id as "question" | "document")}
                    style={({ pressed }) => [styles.inputModeButton, active ? styles.inputModeButtonActive : null, pressed ? styles.buttonPressed : null]}
                  >
                    <Text style={[styles.inputModeText, active ? styles.inputModeTextActive : null]}>{item.label}</Text>
                  </Pressable>
                );
              })}
            </View>
            {documentConfiguratorVisible ? (
              <Animated.View
                style={[
                  styles.documentConfigurator,
                  {
                    opacity: documentPanelProgress,
                    transform: [
                      {
                        translateX: documentPanelProgress.interpolate({
                          inputRange: [0, 1],
                          outputRange: [32, 0],
                        }),
                      },
                    ],
                  },
                ]}
              >
                <View style={styles.documentConfiguratorHeader}>
                  <View style={styles.documentConfiguratorHeading}>
                    <Text style={styles.documentConfiguratorTitle}>문서 양식</Text>
                    <Text style={styles.documentConfiguratorHint}>예시 문서를 고르거나 직접 파일을 넣어 초안 기준을 맞춥니다.</Text>
                  </View>
                </View>
                <View style={styles.docPresetWrap}>
                  {documentPresets.map((preset) => {
                    const active = preset.id === documentPresetId && !useCustomSamplePath;
                    return (
                      <Pressable
                        key={preset.id}
                        accessibilityRole="button"
                        onPress={() => {
                          setDocumentPresetId(preset.id);
                          setUseCustomSamplePath(false);
                        }}
                        style={({ pressed }) => [styles.docPresetChip, active ? styles.docPresetChipActive : null, pressed ? styles.buttonPressed : null]}
                      >
                        <Text style={[styles.docPresetChipText, active ? styles.docPresetChipTextActive : null]}>{preset.label}</Text>
                      </Pressable>
                    );
                  })}
                  <Pressable
                    accessibilityRole="button"
                    onPress={() => setUseCustomSamplePath(true)}
                    style={({ pressed }) => [styles.docPresetChip, useCustomSamplePath ? styles.docPresetChipActive : null, pressed ? styles.buttonPressed : null]}
                  >
                    <Text style={[styles.docPresetChipText, useCustomSamplePath ? styles.docPresetChipTextActive : null]}>커스텀 파일</Text>
                  </Pressable>
                </View>
                {useCustomSamplePath ? (
                  <View style={styles.documentCustomRow}>
                    <Pressable
                      accessibilityRole="button"
                      onPress={() => {
                        void handleCustomFilePick();
                      }}
                      style={({ pressed }) => [styles.uploadChip, pressed ? styles.buttonPressed : null]}
                    >
                      <Text style={styles.uploadChipText}>파일 선택</Text>
                    </Pressable>
                    <TextInput
                      value={samplePath}
                      onChangeText={setSamplePath}
                      style={[styles.pathInput, webTextInputFocusReset]}
                      placeholder="업로드된 예시 문서 토큰"
                      placeholderTextColor={theme.colors.subtle}
                      selectionColor="#111111"
                    />
                  </View>
                ) : null}
                {uploadedSampleLabel ? <Text style={styles.uploadedSampleLabel}>{uploadedSampleLabel}</Text> : null}
              </Animated.View>
            ) : null}
            <TextInput
              multiline
              value={prompt}
              onChangeText={setPrompt}
              style={[styles.textarea, webTextInputFocusReset]}
              placeholder={mode === "document" && documentMessages.length ? "이어서 문서에 반영할 내용을 적습니다." : "사실관계나 요청 문서 유형을 적습니다."}
              placeholderTextColor={theme.colors.subtle}
              selectionColor="#111111"
              blurOnSubmit={false}
              onKeyPress={(event) => {
                if (Platform.OS !== "web") {
                  return;
                }
                const nativeEvent = event.nativeEvent as { key?: string; shiftKey?: boolean; isComposing?: boolean };
                if (!shouldSubmitComposerKey(nativeEvent)) {
                  return;
                }
                (event as unknown as { preventDefault?: () => void }).preventDefault?.();
                void handleSubmit();
              }}
            />

            <Pressable
              accessibilityRole="button"
              onPress={() => {
                void handleSubmit();
              }}
              style={({ pressed }) => [styles.sendButton, (submitting || !prompt.trim()) ? styles.sendButtonDisabled : null, pressed ? styles.buttonPressed : null]}
              disabled={submitting || !prompt.trim()}
            >
              <Text style={styles.sendButtonText}>↗</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </View>
  );
}

function ExportButton({ label, url }: { label: string; url: string }) {
  if (!url) {
    return null;
  }
  const resolvedUrl = url.startsWith("/") && typeof window !== "undefined" ? new URL(url, window.location.origin).toString() : url;
  return (
    <Pressable
      accessibilityRole="button"
      onPress={() => {
        void Linking.openURL(resolvedUrl);
      }}
      style={({ pressed }) => [styles.exportButton, pressed ? styles.buttonPressed : null]}
    >
      <Text style={styles.exportButtonText}>{label}</Text>
    </Pressable>
  );
}

function MessageActionRow({
  disabled,
  onEdit,
  onRetry,
}: {
  disabled?: boolean;
  onEdit: () => void;
  onRetry: () => void;
}) {
  return (
    <View style={styles.messageActionRow}>
      <Pressable
        accessibilityRole="button"
        onPress={onEdit}
        disabled={disabled}
        style={({ pressed }) => [styles.messageActionButton, disabled ? styles.messageActionButtonDisabled : null, pressed ? styles.buttonPressed : null]}
      >
        <Text style={styles.messageActionText}>편집</Text>
      </Pressable>
      <Pressable
        accessibilityRole="button"
        onPress={onRetry}
        disabled={disabled}
        style={({ pressed }) => [styles.messageActionButton, disabled ? styles.messageActionButtonDisabled : null, pressed ? styles.buttonPressed : null]}
      >
        <Text style={styles.messageActionText}>다시 답변받기</Text>
      </Pressable>
    </View>
  );
}

function RequestActionRow({ canCancel, onCancel }: { canCancel: boolean; onCancel: () => void }) {
  if (!canCancel) {
    return null;
  }
  return (
    <View style={styles.requestActionRow}>
      <Pressable
        accessibilityRole="button"
        onPress={onCancel}
        style={({ pressed }) => [styles.cancelRequestButton, pressed ? styles.buttonPressed : null]}
      >
        <Text style={styles.cancelRequestText}>요청 취소</Text>
      </Pressable>
    </View>
  );
}

function DocumentSetupPanel({
  presets,
  selectedPresetId,
  uploading,
  onSelectPreset,
  onUpload,
}: {
  presets: DocumentPreset[];
  selectedPresetId: string;
  uploading?: boolean;
  onSelectPreset: (presetId: string) => void;
  onUpload: () => void;
}) {
  return (
    <View style={styles.documentSetupPanel}>
      <Text style={styles.documentSetupTitle}>문서 양식을 선택해주세요.</Text>
      <Text style={styles.documentSetupBody}>프리셋을 고르면 필요한 사실을 먼저 확인한 뒤 초안 작성을 시작합니다.</Text>
      <View style={styles.documentSetupPresetRow}>
        {presets.length ? (
          presets.map((preset) => {
            const active = preset.id === selectedPresetId;
            return (
              <Pressable
                key={preset.id}
                accessibilityRole="button"
                onPress={() => onSelectPreset(preset.id)}
                style={({ pressed }) => [styles.documentSetupPresetButton, active ? styles.documentSetupPresetButtonActive : null, pressed ? styles.buttonPressed : null]}
              >
                <Text style={[styles.documentSetupPresetText, active ? styles.documentSetupPresetTextActive : null]}>{preset.label}</Text>
              </Pressable>
            );
          })
        ) : (
          <Text style={styles.documentSetupBody}>프리셋을 불러오는 중입니다.</Text>
        )}
        <Pressable
          accessibilityRole="button"
          onPress={onUpload}
          disabled={uploading}
          style={({ pressed }) => [styles.documentSetupUploadButton, uploading ? styles.messageActionButtonDisabled : null, pressed ? styles.buttonPressed : null]}
        >
          <Text style={styles.documentSetupUploadText}>파일 업로드</Text>
        </Pressable>
      </View>
    </View>
  );
}

function isTerminalRunState(state: string | undefined): boolean {
  return ["completed", "failed", "cancelled", "interrupted"].includes(String(state || "").trim());
}

function compactUiText(value: string, limit = 120) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (text.length <= limit) {
    return text;
  }
  const clipped = text.slice(0, limit).replace(/\s+\S*$/, "").trim();
  return `${clipped || text.slice(0, limit).trim()}…`;
}

function LegalDisclaimer() {
  return (
    <View style={styles.disclaimerBox}>
      <Text style={styles.disclaimerTitle}>참고용 안내</Text>
      <Text style={styles.disclaimerBody}>
        본 분석은 Lawkey AI가 제공된 판례 데이터를 기반으로 자동 생성한 참고 자료입니다.
        구체적인 사건의 결론·소송 전략·법적 책임은 사실관계와 증거에 따라 달라질 수 있으며,
        AI는 사실관계를 잘못 인식하거나 판례를 부정확하게 인용할 수 있습니다.
      </Text>
    </View>
  );
}

function ClaimRow({
  claim,
  onOpen,
}: {
  claim: ClaimRecord;
  onOpen: (precedentId: string) => void;
}) {
  const sourceId = claim.source_file_id ?? "";
  const supportQuote = claim.support_spans?.[0]?.quote ?? "";
  const primaryCase = claim.supporting_cases?.[0];
  const claimMeta = buildClaimCitation(claim, primaryCase);
  return (
    <Pressable
      accessibilityRole="button"
      onPress={() => {
        if (sourceId) {
          onOpen(sourceId);
        }
      }}
      style={({ pressed }) => [styles.claimRow, pressed ? styles.buttonPressed : null]}
    >
      <Text style={styles.claimAxis}>{claim.claim_axis || claim.claim_text || "주장"}</Text>
      <Text style={styles.claimText}>{claim.claim_text || claim.context_summary || "설명 없음"}</Text>
      {claimMeta ? <Text style={styles.claimMeta}>{claimMeta}</Text> : null}
      {supportQuote ? <Text style={styles.claimQuote}>“{supportQuote}”</Text> : null}
    </Pressable>
  );
}

type SupportingCase = NonNullable<ClaimRecord["supporting_cases"]>[number];

function GroupedClaims({
  claims,
  claimGroups,
  precedents,
  onOpen,
}: {
  claims: ClaimRecord[];
  claimGroups?: Array<{ label: string; claim_ids: string[] }>;
  precedents: Array<{ precedentId: string; citation?: string; court?: string; decisionDate?: string; caseNumber?: string; title?: string }>;
  onOpen: (precedentId: string) => void;
}) {
  const groups = useMemo(() => {
    if (claimGroups?.length) {
      const byId = new Map(claims.map((claim) => [String(claim.claim_id || "").trim(), claim]));
      const explicitGroups = claimGroups
        .map((group) => {
          const groupedClaims = (group.claim_ids || [])
            .map((claimId) => byId.get(String(claimId || "").trim()))
            .filter(Boolean) as ClaimRecord[];
          if (!groupedClaims.length) {
            return null;
          }
          let primary = groupedClaims[0];
          for (const claim of groupedClaims.slice(1)) {
            const currentSupport = Number(primary.supporting_case_count || 0);
            const nextSupport = Number(claim.supporting_case_count || 0);
            if (nextSupport > currentSupport) {
              primary = claim;
            }
          }
          return {
            axis: group.label,
            primary,
            claims: groupedClaims,
          };
        })
        .filter(Boolean) as Array<{
        axis: string;
        primary: ClaimRecord;
        claims: ClaimRecord[];
      }>;
      if (explicitGroups.length) {
        return explicitGroups;
      }
    }
    const bucket = new Map<
      string,
      {
        axis: string;
        primary: ClaimRecord;
        claims: ClaimRecord[];
      }
    >();
    for (const claim of claims) {
      const axis = (claim.claim_axis || claim.claim_text || "주장").trim();
      const current = bucket.get(axis);
      if (!current) {
        bucket.set(axis, { axis, primary: claim, claims: [claim] });
        continue;
      }
      current.claims.push(claim);
      const currentSupport = Number(current.primary.supporting_case_count || 0);
      const nextSupport = Number(claim.supporting_case_count || 0);
      if (nextSupport > currentSupport) {
        current.primary = claim;
      }
    }
    return [...bucket.values()];
  }, [claims]);

  return (
    <>
      {groups.map((group) => (
        <GroupedClaimCard key={group.axis} group={group} precedents={precedents} onOpen={onOpen} />
      ))}
    </>
  );
}

function GroupedClaimCard({
  group,
  precedents,
  onOpen,
}: {
  group: {
    axis: string;
    primary: ClaimRecord;
    claims: ClaimRecord[];
  };
  precedents: Array<{ precedentId: string; citation?: string; court?: string; decisionDate?: string; caseNumber?: string; title?: string }>;
  onOpen: (precedentId: string) => void;
}) {
  const supportingCases = dedupeSupportingCases(group.claims, precedents);
  const primary = group.primary;
  const uniqueSupportCount = supportingCases.length;
  const confidenceLine =
    uniqueSupportCount >= 2
      ? `이 묶음은 표시된 판례 ${uniqueSupportCount}건이 같은 방향으로 반복적으로 지지해 신뢰도가 높습니다.`
      : primary.certainty_reason || "";
  const overviewLine = String(primary.claim_text || primary.context_summary || "핵심 논리를 정리 중입니다.").trim();

  return (
    <View style={styles.claimGroupCard}>
      <View style={styles.claimAxisRow}>
        <Text style={styles.claimAxis}>{group.axis}</Text>
        {uniqueSupportCount ? <Text style={styles.claimAxisCount}>판례 {uniqueSupportCount}건</Text> : null}
      </View>
      <Text style={styles.claimText}>{compactUiText(overviewLine, 180)}</Text>
      {confidenceLine ? <Text style={styles.claimConfidence}>{confidenceLine}</Text> : null}
      {supportingCases.length ? (
        <>
          {supportingCases.map((item, index) => (
            <View
              key={`${item.precedentId || item.caseNumber || item.citation}-${index}`}
              style={styles.claimEvidenceCard}
            >
              <Text style={styles.claimSubitem}>ㄴ {compactUiText(item.claimAxis || group.axis || "관련 논리", 96)}</Text>
              {item.claimText ? <Text style={styles.claimSubbody}>{compactUiText(item.claimText, 170)}</Text> : null}
              {item.citation ? <Text style={styles.claimSubmeta}>{compactUiText(item.citation, 120)}</Text> : null}
              {item.quote ? <Text style={styles.claimQuote}>“{compactUiText(item.quote, 130)}”</Text> : null}
              {item.precedentId ? (
                <Pressable
                  accessibilityRole="button"
                  onPress={() => onOpen(item.precedentId)}
                  style={({ pressed }) => [styles.inlineActionButton, pressed ? styles.buttonPressed : null]}
                >
                  <Text style={styles.inlineActionText}>전문 보기</Text>
                </Pressable>
              ) : null}
            </View>
          ))}
        </>
      ) : (
        <View style={styles.claimSubgroup}>
          {group.claims.map((claim, index) => {
            const subBody = String(claim.claim_text || claim.context_summary || "").trim();
            return (
              <View key={`${claim.claim_id || claim.claim_axis || "sub"}-${index}`} style={styles.claimSubcard}>
                <Text style={styles.claimSubitem}>ㄴ {claim.claim_axis || claim.claim_text || "관련 주장"}</Text>
                {subBody && subBody !== overviewLine ? <Text style={styles.claimSubbody}>{compactUiText(subBody, 150)}</Text> : null}
              </View>
            );
          })}
        </View>
      )}
    </View>
  );
}

function dedupeSupportingCases(
  claims: ClaimRecord[],
  precedents: Array<{ precedentId: string; citation?: string; court?: string; decisionDate?: string; caseNumber?: string; title?: string }>,
) {
  const precedentById = new Map(precedents.map((precedent) => [precedent.precedentId, precedent]));
  const rows: Array<{ precedentId: string; caseNumber: string; citation: string; quote: string; claimAxis: string; claimText: string; supportCount: number }> = [];
  const seen = new Set<string>();
  for (const claim of claims) {
    const primaryCase = claim.supporting_cases?.[0];
    const citation = buildClaimCitation(claim, primaryCase, precedents);
    const caseNumber = claim.case_number || primaryCase?.case_number || "";
    const precedentId = claim.source_file_id || "";
    const precedent = precedentById.get(precedentId);
    const quote = claim.support_spans?.[0]?.quote || "";
    const resolvedCitation = citation || String(precedent?.citation || "").trim();
    const key = `${precedentId}::${caseNumber}::${resolvedCitation}`;
    if (!resolvedCitation || seen.has(key)) {
      continue;
    }
    seen.add(key);
    rows.push({
      precedentId,
      caseNumber,
      citation: resolvedCitation,
      quote,
      claimAxis: String(claim.claim_axis || "").trim(),
      claimText: String(claim.claim_text || claim.context_summary || "").trim(),
      supportCount: Number(claim.supporting_case_count || 0),
    });
  }
  return rows;
}

function AnalysisSummaryCard({
  answerPlan,
  claims,
}: {
  answerPlan?: {
    likely_outcome?: string;
    confidence_basis?: string[];
    helpful_facts?: string[];
    harmful_facts?: string[];
    claim_groups?: Array<{ label: string; claim_ids: string[] }>;
  };
  claims: ClaimRecord[];
}) {
  const cleanSummaryText = (value: string) =>
    String(value || "")
      .replace(/\s*\(\s*(?:CLAIM-\d+\s*[,;]\s*)*CLAIM-\d+\s*\)/g, "")
      .replace(/\bCLAIM-\d+\b/g, "")
      .replace(/\s{2,}/g, " ")
      .trim();

  const helpfulFactsFromClaims = useMemo(() => {
    return dedupeFacts(
      claims.flatMap((claim) => {
        const stance = String(claim.stance_to_user_goal || "").trim();
        if (!stance.includes("유리")) {
          return [];
        }
        return [
          ...((claim.favorable_factors || []) as string[]),
          ...((claim.required_facts || []) as string[]),
          ...((claim.favorable_basis || []) as string[]),
          String(claim.claim_text || "").trim(),
        ].filter(Boolean);
      }),
    ).slice(0, 4);
  }, [claims]);

  const harmfulFactsFromClaims = useMemo(() => {
    return dedupeFacts(
      claims.flatMap((claim) => {
        const stance = String(claim.stance_to_user_goal || "").trim();
        if (!stance.includes("불리")) {
          return [];
        }
        return [
          ...((claim.unfavorable_factors || []) as string[]),
          ...((claim.missing_facts || []) as string[]),
          ...((claim.cautions || []) as string[]),
          ...((claim.counter_evidence || []) as string[]),
          String(claim.claim_text || "").trim(),
        ].filter(Boolean);
      }),
    ).slice(0, 4);
  }, [claims]);

  const fallbackSummary = useMemo(() => {
    if (!claims.length) {
      return {
        likelyOutcome: "",
        confidenceBasis: [] as string[],
        helpfulFacts: [] as string[],
        harmfulFacts: [] as string[],
      };
    }
    const byId = new Map(claims.map((claim) => [String(claim.claim_id || "").trim(), claim]));
    const grouped =
      answerPlan?.claim_groups?.map((group) => ({
        label: group.label,
        claims: (group.claim_ids || [])
          .map((claimId) => byId.get(String(claimId || "").trim()))
          .filter(Boolean) as ClaimRecord[],
      })) ||
      [];
    const rankedGroups =
      grouped.length > 0
        ? grouped
            .map((group) => ({
              label: group.label,
              claims: group.claims,
              support: Math.max(
                ...group.claims.map((claim) => Number(claim.supporting_case_count || 0)),
                0,
              ),
              favorableCount: group.claims.filter((claim) => String(claim.stance_to_user_goal || "").trim() === "유리").length,
            }))
            .sort((a, b) => b.support - a.support || b.favorableCount - a.favorableCount || a.label.localeCompare(b.label))
        : claims
            .map((claim) => ({
              label: String(claim.claim_axis || claim.claim_text || "주장").trim(),
              claims: [claim],
              support: Number(claim.supporting_case_count || 0),
              favorableCount: String(claim.stance_to_user_goal || "").trim() === "유리" ? 1 : 0,
            }))
            .sort((a, b) => b.support - a.support || b.favorableCount - a.favorableCount || a.label.localeCompare(b.label));
    const top = rankedGroups[0];
    const runnerUp = rankedGroups[1];
    if (!top) {
      return { likelyOutcome: "", confidenceBasis: [] as string[], helpfulFacts: [] as string[], harmfulFacts: [] as string[] };
    }
    const topClaim =
      [...top.claims].sort(
        (a, b) =>
          Number(b.supporting_case_count || 0) - Number(a.supporting_case_count || 0),
      )[0] || top.claims[0];
    const support = Number(topClaim?.supporting_case_count || top.support || 0);
    const favorableStrength = rankedGroups.reduce(
      (total, group) =>
        total +
        group.claims.reduce(
          (groupTotal, claim) =>
            groupTotal +
            (String(claim.stance_to_user_goal || "").includes("유리")
              ? Math.max(Number(claim.supporting_case_count || 0), 1)
              : 0),
          0,
        ),
      0,
    );
    const harmfulStrength = rankedGroups.reduce(
      (total, group) =>
        total +
        group.claims.reduce(
          (groupTotal, claim) =>
            groupTotal +
            (String(claim.stance_to_user_goal || "").includes("불리")
              ? Math.max(Number(claim.supporting_case_count || 0), 1)
              : 0),
          0,
        ),
      0,
    );
    const repeatedLine =
      support >= 2
        ? `${top.label} 묶음은 별개 판례 ${support}건 안팎이 같은 방향으로 반복적으로 뒷받침하므로 가장 신뢰도가 높습니다.`
        : `${top.label} 묶음이 현재 선택된 판례 중 가장 직접적인 판단축으로 보입니다.`;
    const supportingExamples = [...new Set((topClaim?.supporting_cases || []).map((item) => String(item?.case_number || "").trim()).filter(Boolean))].slice(0, 3);
    const claimLine = String(topClaim?.claim_text || topClaim?.context_summary || "").trim().replace(/\s+/g, " ");
    const likelyDirection =
      favorableStrength > harmfulStrength * 1.15
        ? "질문자에게 유리한 방향의 결론"
        : harmfulStrength > favorableStrength * 1.15
          ? "질문자에게 불리한 방향의 결론"
          : "핵심 사실관계에 따라 결론이 갈릴 가능성";
    const leadSupport = Math.max(Number(top.support || 0), Number(topClaim?.supporting_case_count || 0));
    const runnerSupport = Math.max(Number(runnerUp?.support || 0), 0);
    const supportLead =
      leadSupport >= 2 && leadSupport > runnerSupport
        ? `${top.label} 축은 다음으로 많이 나온 축보다 ${Math.max(leadSupport - runnerSupport, 1)}건 이상 더 반복되어, 현재 가장 신뢰도 높은 주된 논리로 볼 수 있습니다.`
        : "";
    const supportExampleLine = supportingExamples.length
      ? `${supportingExamples.join(", ")} 등에서 같은 논리가 반복됩니다.`
      : "";
    const likelyOutcome = claimLine
      ? `현재 자료상 ${likelyDirection}이 가장 높습니다. 특히 ${top.label} 묶음이 핵심 판단축이고, ${repeatedLine} ${supportLead} ${supportExampleLine} 따라서 지금 단계의 주된 결론은 ${claimLine}`
      : `현재 자료상 ${likelyDirection}이 가장 높습니다. 특히 ${top.label} 묶음이 핵심 판단축이고, ${repeatedLine} ${supportLead} ${supportExampleLine}`;
    const helpfulFacts = dedupeFacts(
      rankedGroups.flatMap((group) =>
        group.claims.flatMap((claim) => [
          ...(claim.favorable_factors || []),
          ...(claim.required_facts || []),
        ]),
      ),
    ).slice(0, 4);
    const harmfulFacts = dedupeFacts(
      rankedGroups.flatMap((group) =>
        group.claims.flatMap((claim) => [
          ...(claim.unfavorable_factors || []),
          ...(claim.missing_facts || []),
          ...(claim.cautions || []),
          ...(claim.counter_evidence || []),
        ]),
      ),
    ).slice(0, 4);
    return {
      likelyOutcome,
      confidenceBasis: [repeatedLine, supportLead].filter(Boolean),
      helpfulFacts,
      harmfulFacts,
    };
  }, [answerPlan?.claim_groups, claims]);

  if (!answerPlan && !fallbackSummary.likelyOutcome) {
    return null;
  }
  const explicitLikelyOutcome = cleanSummaryText(String(answerPlan?.likely_outcome || ""));
  const weakExplicitLikelyOutcome =
    !explicitLikelyOutcome ||
    /주장할\s+수\s+있(?:다|으나)|가능하(?:다|지만)|반면|다만|대비해야|정리할\s+수\s+있|양쪽|모두|갈릴\s+여지|단정하기\s+어렵/.test(explicitLikelyOutcome);
  const likelyOutcome = String(
    (weakExplicitLikelyOutcome ? fallbackSummary.likelyOutcome : explicitLikelyOutcome) || fallbackSummary.likelyOutcome || explicitLikelyOutcome || "",
  ).trim();
  const confidenceBasis = (answerPlan?.confidence_basis?.length ? answerPlan.confidence_basis : fallbackSummary.confidenceBasis)
    .map((item) => cleanSummaryText(String(item || "")))
    .filter(Boolean)
    .slice(0, 3);
  const helpfulFacts = (
    (answerPlan?.helpful_facts?.length ? answerPlan.helpful_facts : fallbackSummary.helpfulFacts.length ? fallbackSummary.helpfulFacts : helpfulFactsFromClaims) || []
  )
    .map((item) => cleanSummaryText(String(item || "")))
    .filter(Boolean)
    .slice(0, 4);
  const harmfulFacts = (
    (answerPlan?.harmful_facts?.length ? answerPlan.harmful_facts : fallbackSummary.harmfulFacts.length ? fallbackSummary.harmfulFacts : harmfulFactsFromClaims) || []
  )
    .map((item) => cleanSummaryText(String(item || "")))
    .filter(Boolean)
    .slice(0, 4);

  if (!likelyOutcome && !confidenceBasis.length && !helpfulFacts.length && !harmfulFacts.length) {
    return null;
  }

  return (
    <View style={styles.analysisSummaryCard}>
      {likelyOutcome ? (
        <View style={styles.analysisSummaryBlock}>
          <Text style={styles.analysisSummaryLabel}>가장 가능성 높은 결론</Text>
          <Text style={styles.analysisSummaryBody}>{likelyOutcome}</Text>
        </View>
      ) : null}
      {confidenceBasis.length ? (
        <View style={styles.analysisSummaryBlock}>
          <Text style={styles.analysisSummaryLabel}>결론 근거</Text>
          {confidenceBasis.map((item, index) => (
            <Text key={`confidence-${index}`} style={styles.analysisSummaryBullet}>
              • {item}
            </Text>
          ))}
        </View>
      ) : null}
      {(helpfulFacts.length || harmfulFacts.length) ? (
        <View style={styles.analysisSummarySplit}>
          <View style={styles.analysisSummaryColumn}>
            <Text style={styles.analysisSummaryLabel}>유리하게 만들 요소</Text>
            {helpfulFacts.length ? helpfulFacts.map((item, index) => (
              <Text key={`helpful-${index}`} style={styles.analysisSummaryBullet}>
                • {item}
              </Text>
            )) : <Text style={styles.analysisSummaryMuted}>정리 중</Text>}
          </View>
          <View style={styles.analysisSummaryColumn}>
            <Text style={styles.analysisSummaryLabel}>불리하게 만들 요소</Text>
            {harmfulFacts.length ? harmfulFacts.map((item, index) => (
              <Text key={`harmful-${index}`} style={styles.analysisSummaryBullet}>
                • {item}
              </Text>
            )) : <Text style={styles.analysisSummaryMuted}>정리 중</Text>}
          </View>
        </View>
      ) : null}
    </View>
  );
}

function dedupeFacts(values: string[]) {
  const out: string[] = [];
  for (const value of values) {
    const normalized = String(value || "").trim().replace(/\s+/g, " ");
    if (!normalized || out.includes(normalized)) {
      continue;
    }
    out.push(normalized);
  }
  return out;
}

function buildClaimCitation(
  claim: ClaimRecord,
  primaryCase?: SupportingCase,
  precedents: Array<{ precedentId: string; citation?: string; court?: string; decisionDate?: string; caseNumber?: string; title?: string }> = [],
) {
  const explicitCitation = String(claim.citation || "").trim();
  if (explicitCitation) {
    return explicitCitation;
  }
  const selectedPrecedent = precedents.find((precedent) => precedent.precedentId === (claim.source_file_id || ""));
  const selectedCitation = String(selectedPrecedent?.citation || "").trim();
  if (selectedCitation) {
    return selectedCitation;
  }
  const primary = primaryCase || {};
  const caseNumber = String(claim.case_number || primary?.case_number || selectedPrecedent?.caseNumber || "").trim();
  return caseNumber ? `${caseNumber} 판결` : "참조 판례";
}

function normalizeDecisionDate(value: string) {
  const digits = String(value || "").replace(/\D/g, "");
  if (digits.length >= 8) {
    return `${digits.slice(0, 4)}. ${digits.slice(4, 6)}. ${digits.slice(6, 8)}.`;
  }
  return String(value || "").trim();
}

function normalizeCaseName(value: string) {
  const text = String(value || "").trim();
  if (!text || /^\d+$/.test(text)) {
    return "";
  }
  return text;
}

function formatStateLabel(state: string, mode: "question" | "document") {
  if (state === "queued") return "대기 중";
  if (state === "waiting_for_capacity") return "실행 대기";
  if (state === "generating_keywords") return "판례 선별";
  if (state === "building_chunk_plan" || state === "packing_chunks" || state === "chunking_records") return "선별 결과 정리";
  if (state === "analyzing_chunks") return "최종 분석";
  if (state === "writing_final_draft") return mode === "document" ? "문서 작성" : "응답 작성";
  if (state === "applying_coverage_patch") return "본문 반영";
  if (state === "writing_document") return "문서 작성";
  if (state === "exporting_artifacts") return "문서 출력";
  if (state === "retrying_after_transient_error") return "자동 재시도";
  if (state === "completed") return "완료";
  if (state === "failed") return "실패";
  if (state === "interrupted") return "중단됨";
  return state || "준비 중";
}

function buildHistoryMeta({
  result,
  status,
  mode,
}: {
  result: ReturnType<typeof useLawkeyJob>["result"];
  status: ReturnType<typeof useLawkeyJob>["status"];
  mode: "question" | "document";
}) {
  if (result) {
    return "완료";
  }
  if (!status) {
    return "실행 대기";
  }
  if (status.queuePosition && status.queuePosition > 1) {
    return "대기 중";
  }
  if (status.state === "completed") {
    return "완료";
  }
  if (status.state === "failed" || status.state === "cancelled" || status.state === "interrupted") {
    return "중단됨";
  }
  return "진행 중";
}

function buildHistoryMetaFromJob(item: {
  state?: string;
  queuePosition?: number;
}) {
  if (item.queuePosition && item.queuePosition > 1) {
    return "대기 중";
  }
  if (item.state === "completed") {
    return "완료";
  }
  if (item.state === "failed" || item.state === "cancelled" || item.state === "interrupted") {
    return "중단됨";
  }
  return "진행 중";
}

function mergeServerHistory(
  current: SessionHistoryItem[],
  jobs: Array<{
    jobId?: string;
    userTask?: string;
    mode?: "question" | "document";
    state?: string;
    queuePosition?: number;
    createdAt?: number;
    finishedAt?: number | null;
  }>,
) {
  let next = [...current];
  for (const item of jobs) {
    const jobId = String(item.jobId || "").trim();
    if (!jobId) {
      continue;
    }
    next = upsertSessionHistory(next, {
      id: jobId,
      title: buildHistoryTitle(
        String(item.userTask || ""),
        item.mode === "document" ? "문서 초안" : "분석 세션",
      ),
      meta: buildHistoryMetaFromJob(item),
      prompt: String(item.userTask || "").trim(),
      createdAt: item.createdAt,
      finishedAt: item.finishedAt ?? null,
    });
  }
  return next;
}

function buildHistoryTitle(prompt: string, fallback: string) {
  const trimmed = (prompt || "").trim().replace(/\s+/g, " ");
  if (!trimmed) {
    return fallback;
  }
  return trimmed.length > 42 ? `${trimmed.slice(0, 42)}…` : trimmed;
}

const styles = StyleSheet.create({
  appContainer: {
    flex: 1,
    flexDirection: "row",
    backgroundColor: "#ffffff",
    position: "relative",
  },
  sidebar: {
    width: 280,
    backgroundColor: "#0a0a0a",
    borderRightWidth: 1,
    borderRightColor: "#222222",
    paddingHorizontal: 24,
    paddingVertical: 24,
    flexDirection: "column",
  },
  sidebarCompact: {
    display: "none",
  },
  sidebarOpen: {
    display: "flex",
    position: "absolute",
    left: 0,
    top: 0,
    bottom: 0,
    zIndex: 30,
    height: "100%",
    shadowColor: "#000000",
    shadowOpacity: 0.25,
    shadowRadius: 22,
    shadowOffset: { width: 6, height: 0 },
  },
  sidebarScrim: {
    position: "absolute",
    left: 0,
    right: 0,
    top: 0,
    bottom: 0,
    zIndex: 20,
    backgroundColor: "rgba(0,0,0,0.22)",
  },
  brand: {
    color: "#ffffff",
    fontFamily: theme.fonts.serif,
    fontSize: 22,
    fontWeight: "800",
    letterSpacing: 0.4,
  },
  brandRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    marginBottom: 40,
  },
  sidebarLogo: {
    marginBottom: 0,
  },
  headerLogo: {
    marginLeft: "auto",
    marginRight: 8,
  },
  newRunButton: {
    borderWidth: 1,
    borderColor: "#444444",
    borderRadius: 6,
    paddingHorizontal: 14,
    paddingVertical: 14,
    backgroundColor: "transparent",
  },
  newRunText: {
    color: "#ffffff",
    fontSize: 15,
    fontWeight: "600",
  },
  history: {
    marginTop: 30,
    flex: 1,
    minHeight: 0,
  },
  historyTitle: {
    color: "#888888",
    fontSize: 12,
    marginBottom: 12,
    textTransform: "uppercase",
    letterSpacing: 1,
  },
  historyScroll: {
    flex: 1,
    minHeight: 0,
    // Hide scrollbar on web while keeping scroll behavior intact.
    ...(Platform.OS === "web"
      ? ({ scrollbarWidth: "none", msOverflowStyle: "none" } as any)
      : null),
  },
  historyScrollContent: {
    paddingBottom: 12,
  },
  historyItem: {
    marginBottom: 16,
  },
  historyItemRow: {
    flexDirection: "row",
    alignItems: "stretch",
    gap: 4,
  },
  historyItemButton: {
    flex: 1,
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 6,
  },
  historyDeleteButton: {
    width: 26,
    borderRadius: 6,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "transparent",
  },
  historyDeleteText: {
    color: "#9ca3af",
    fontSize: 18,
    fontWeight: "700",
    lineHeight: 18,
  },
  adminEditorWrap: {
    borderWidth: 1,
    borderColor: theme.colors.line,
    borderRadius: 10,
    backgroundColor: "#fcfcfd",
    padding: 12,
    gap: 10,
  },
  adminEditorTextArea: {
    minHeight: 220,
    fontSize: 14,
    lineHeight: 22,
    color: theme.colors.text,
    fontFamily: theme.fonts.serif,
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: theme.colors.line,
    borderRadius: 8,
    padding: 10,
    textAlignVertical: "top",
  },
  adminEditorActions: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: 8,
  },
  adminEditorButton: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: "#101010",
  },
  adminEditorButtonText: {
    color: "#ffffff",
    fontSize: 13,
    fontWeight: "700",
  },
  adminEditorButtonGhost: {
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: theme.colors.line,
  },
  adminEditorButtonGhostText: {
    color: theme.colors.text,
    fontSize: 13,
    fontWeight: "700",
  },
  adminEditButton: {
    alignSelf: "flex-end",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: theme.colors.line,
    backgroundColor: "#fafafa",
  },
  adminEditButtonText: {
    color: theme.colors.muted,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0.4,
  },
  historyItemButtonActive: {
    backgroundColor: "#141414",
  },
  historyItemTitle: {
    color: "#e5e7eb",
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 4,
  },
  historyItemMeta: {
    color: "#9ca3af",
    fontSize: 12,
    lineHeight: 18,
  },
  mainContent: {
    flex: 1,
    backgroundColor: "#ffffff",
    width: "100%",
  },
  mobileTopBar: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: 58,
    zIndex: 12,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255,255,255,0.96)",
    borderBottomWidth: 1,
    borderBottomColor: "#ededed",
  },
  topRightBar: {
    position: "absolute",
    top: 14,
    right: 18,
    zIndex: 60,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  loginDialogLayer: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 70,
    alignItems: "flex-end",
    paddingTop: 56,
    paddingRight: 18,
  },
  loginDialogBackdrop: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(255,255,255,0.01)",
  },
  loginDialogCard: {
    width: 320,
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: theme.colors.line,
    borderRadius: 10,
    paddingHorizontal: 16,
    paddingVertical: 14,
    gap: 8,
    shadowColor: "#000000",
    shadowOpacity: 0.1,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 8 },
  },
  loginDialogTitle: {
    fontFamily: theme.fonts.serif,
    fontSize: 17,
    fontWeight: "700",
    color: theme.colors.text,
  },
  loginDialogSubtitle: {
    fontFamily: theme.fonts.serif,
    fontSize: 12,
    lineHeight: 18,
    color: "#667085",
    marginBottom: 2,
  },
  loginDialogLabel: {
    fontFamily: theme.fonts.serif,
    fontSize: 12,
    fontWeight: "700",
    color: theme.colors.text,
    marginTop: 2,
  },
  loginDialogInput: {
    borderWidth: 1,
    borderColor: "#d7dce2",
    borderRadius: 7,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 14,
    color: theme.colors.text,
    backgroundColor: "#ffffff",
  },
  loginDialogError: {
    fontFamily: theme.fonts.serif,
    fontSize: 12,
    color: "#b42318",
  },
  loginDialogActions: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: 8,
    marginTop: 4,
  },
  loginDialogCancel: {
    borderWidth: 1,
    borderColor: "#d7dce2",
    borderRadius: 7,
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: "#ffffff",
  },
  loginDialogCancelText: {
    fontFamily: theme.fonts.serif,
    fontSize: 13,
    fontWeight: "700",
    color: theme.colors.text,
  },
  loginDialogSubmit: {
    borderWidth: 1,
    borderColor: theme.colors.text,
    borderRadius: 7,
    paddingHorizontal: 13,
    paddingVertical: 8,
    backgroundColor: theme.colors.text,
  },
  loginDialogSubmitText: {
    fontFamily: theme.fonts.serif,
    fontSize: 13,
    fontWeight: "700",
    color: "#ffffff",
  },
  modeSwitcherRow: {
    paddingHorizontal: 18,
    paddingTop: 12,
    paddingBottom: 4,
    alignSelf: "flex-start",
    position: "relative",
    zIndex: 20,
  },
  modeSwitcherRowCompact: {
    paddingTop: 68,
  },
  modeTriggerButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 4,
    paddingVertical: 4,
  },
  modeTriggerLabel: {
    fontFamily: theme.fonts.serif,
    fontSize: 15,
    fontWeight: "700",
    color: theme.colors.text,
  },
  modeTriggerChevron: {
    fontFamily: theme.fonts.serif,
    fontSize: 12,
    color: "#888888",
    marginLeft: 2,
  },
  modeMenuBackdrop: {
    position: "absolute",
    top: -2000,
    left: -2000,
    right: -2000,
    bottom: -2000,
    zIndex: 19,
  },
  modeMenu: {
    position: "absolute",
    top: 44,
    left: 18,
    minWidth: 280,
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: theme.colors.line,
    borderRadius: 10,
    paddingVertical: 4,
    shadowColor: "#000000",
    shadowOpacity: 0.08,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 6 },
    zIndex: 21,
  },
  modeMenuItem: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    gap: 3,
  },
  modeMenuItemHover: {
    backgroundColor: "#f7f7f7",
  },
  modeMenuItemHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  modeMenuItemTitle: {
    fontFamily: theme.fonts.serif,
    fontSize: 14,
    fontWeight: "700",
    color: theme.colors.text,
  },
  modeMenuItemCheck: {
    fontFamily: theme.fonts.serif,
    fontSize: 13,
    color: theme.colors.text,
    fontWeight: "700",
  },
  modeMenuItemDesc: {
    fontFamily: theme.fonts.serif,
    fontSize: 12,
    color: "#777777",
    lineHeight: 17,
  },
  mobileMenuButton: {
    position: "absolute",
    left: 10,
    width: 44,
    height: 44,
    zIndex: 2,
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
  },
  mobileTopBrand: {
    position: "absolute",
    left: 0,
    right: 0,
    top: 0,
    bottom: 0,
    alignItems: "center",
    justifyContent: "center",
  },
  mobileTopBrandButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  mobileTopLogo: {
    marginBottom: 0,
  },
  mobileTopTitle: {
    color: "#111111",
    fontFamily: theme.fonts.serif,
    fontSize: 17,
    fontWeight: "800",
    letterSpacing: 0.2,
  },
  mobileMenuLine: {
    width: 18,
    height: 2,
    borderRadius: 999,
    backgroundColor: "#101010",
  },
  header: {
    minHeight: 88,
    borderBottomWidth: 1,
    borderBottomColor: "#e5e5e5",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255,255,255,0.95)",
    paddingVertical: 12,
  },
  headerInner: {
    width: "100%",
    alignItems: "center",
    gap: 10,
  },
  modeToggle: {
    flexDirection: "row",
    backgroundColor: "#f4f4f5",
    borderRadius: 8,
    padding: 4,
  },
  modeButton: {
    paddingHorizontal: 24,
    paddingVertical: 8,
    borderRadius: 6,
  },
  modeButtonActive: {
    backgroundColor: "#000000",
  },
  modeButtonText: {
    color: "#777777",
    fontSize: 15,
    fontWeight: "600",
  },
  modeButtonTextActive: {
    color: "#ffffff",
  },
  chatContainer: {
    paddingHorizontal: 20,
    paddingTop: 40,
    paddingBottom: 300,
    alignItems: "center",
    gap: 32,
  },
  chatContainerCompact: {
    paddingTop: 76,
    paddingHorizontal: 14,
  },
  welcomeDemoButton: {
    marginTop: 36,
    paddingHorizontal: 22,
    paddingVertical: 12,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: theme.colors.line,
    backgroundColor: "#101010",
    alignSelf: "center",
  },
  welcomeDemoButtonText: {
    color: "#ffffff",
    fontSize: 14,
    fontWeight: "700",
    letterSpacing: 0.4,
  },
  demoOverlayHint: {
    position: "absolute",
    bottom: 96,
    right: 28,
    paddingHorizontal: 14,
    paddingVertical: 9,
    borderRadius: 999,
    backgroundColor: "rgba(15,15,17,0.92)",
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    zIndex: 50,
  },
  demoOverlayHintText: {
    color: "#ffffff",
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0.3,
  },
  demoOverlayBadge: {
    width: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: "#ffffff",
    alignItems: "center",
    justifyContent: "center",
  },
  demoOverlayBadgeText: {
    color: "#101010",
    fontSize: 10,
    fontWeight: "800",
  },
  demoOverlayClickCatcher: {
    position: "absolute",
    left: 0,
    right: 0,
    top: 0,
    bottom: 0,
    zIndex: 49,
  },
  welcomeScreen: {
    marginTop: "15%",
    paddingHorizontal: 20,
    alignItems: "center",
    justifyContent: "center",
  },
  welcomeLogo: {
    marginBottom: 18,
  },
  welcomeTitle: {
    color: "#000000",
    fontFamily: theme.fonts.serif,
    fontSize: 35,
    lineHeight: 40,
    fontWeight: "800",
    marginBottom: 16,
    textAlign: "center",
    maxWidth: "100%",
  },
  welcomeBody: {
    color: "#777777",
    fontSize: 17,
    lineHeight: 26,
    textAlign: "center",
  },
  messageWrapper: {
    width: "100%",
    maxWidth: 800,
  },
  userMessage: {
    alignSelf: "flex-end",
    maxWidth: "85%",
    padding: 24,
    borderWidth: 1,
    borderColor: "#e5e5e5",
    borderRadius: 12,
    borderBottomRightRadius: 4,
    backgroundColor: "#f8f9fa",
    gap: 12,
  },
  userMessageText: {
    color: "#111111",
    fontSize: 16,
    lineHeight: 26,
  },
  docPrepText: {
    color: "#222222",
    fontSize: 15,
    lineHeight: 25,
  },
  aiMessage: {
    width: "100%",
    padding: 0,
    borderWidth: 0,
    borderColor: "transparent",
    borderRadius: 0,
    borderBottomLeftRadius: 0,
    backgroundColor: "#ffffff",
    shadowOpacity: 0,
    gap: 18,
  },
  aiHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    borderBottomWidth: 2,
    borderBottomColor: "#000000",
    paddingBottom: 12,
  },
  aiHeaderText: {
    color: "#111111",
    fontFamily: theme.fonts.serif,
    fontSize: 18,
    fontWeight: "800",
  },
  resultMetaText: {
    alignSelf: "flex-start",
    color: "#4b5563",
    fontSize: 12,
    fontWeight: "700",
    borderWidth: 1,
    borderColor: "#d1d5db",
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 5,
    backgroundColor: "#f9fafb",
  },
  analysisSummaryCard: {
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 12,
    padding: 16,
    gap: 14,
    backgroundColor: "#f8f9fb",
  },
  analysisSummaryBlock: {
    gap: 6,
  },
  analysisSummarySplit: {
    flexDirection: "row",
    gap: 16,
    flexWrap: "wrap",
  },
  analysisSummaryColumn: {
    flex: 1,
    minWidth: 220,
    gap: 6,
  },
  analysisSummaryLabel: {
    color: "#5f6673",
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 0.8,
    textTransform: "uppercase",
  },
  analysisSummaryBody: {
    color: "#111827",
    fontFamily: theme.fonts.serif,
    fontSize: 17,
    lineHeight: 27,
    fontWeight: "700",
  },
  analysisSummaryBullet: {
    color: "#2f3440",
    fontSize: 14,
    lineHeight: 22,
  },
  analysisSummaryMuted: {
    color: "#6b7280",
    fontSize: 13,
    lineHeight: 20,
  },
  loaderCard: {
    gap: 14,
  },
  requestActionRow: {
    flexDirection: "row",
    justifyContent: "flex-end",
  },
  cancelRequestButton: {
    alignSelf: "flex-end",
    borderWidth: 1,
    borderColor: "#b91c1c",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 7,
    backgroundColor: "#fff7f7",
  },
  cancelRequestText: {
    color: "#8c1d18",
    fontSize: 12,
    fontWeight: "700",
  },
  messageActionRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "flex-end",
    gap: 8,
  },
  messageActionButton: {
    borderWidth: 1,
    borderColor: "#d1d5db",
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    backgroundColor: "#ffffff",
  },
  messageActionButtonDisabled: {
    opacity: 0.45,
  },
  messageActionText: {
    color: "#111111",
    fontSize: 11,
    fontWeight: "700",
  },
  documentSetupPanel: {
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 8,
    padding: 16,
    gap: 12,
    backgroundColor: "#f8f9fb",
  },
  documentSetupTitle: {
    color: "#111111",
    fontFamily: theme.fonts.serif,
    fontSize: 18,
    lineHeight: 26,
    fontWeight: "800",
  },
  documentSetupBody: {
    color: "#4b5563",
    fontSize: 13,
    lineHeight: 21,
  },
  documentSetupPresetRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
  },
  documentSetupPresetButton: {
    borderWidth: 1,
    borderColor: "#d1d5db",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: "#ffffff",
  },
  documentSetupPresetButtonActive: {
    borderColor: "#111111",
    backgroundColor: "#111111",
  },
  documentSetupPresetText: {
    color: "#111111",
    fontSize: 13,
    fontWeight: "700",
  },
  documentSetupPresetTextActive: {
    color: "#ffffff",
  },
  documentSetupUploadButton: {
    borderWidth: 1,
    borderColor: "#111111",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: "#ffffff",
  },
  documentSetupUploadText: {
    color: "#111111",
    fontSize: 13,
    fontWeight: "700",
  },
  headerTickerRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    maxWidth: 760,
    paddingHorizontal: 24,
  },
  headerTickerText: {
    flex: 1,
    color: theme.colors.text,
    fontFamily: theme.fonts.serif,
    fontSize: 14,
    lineHeight: 22,
  },
  exportBar: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
  },
  exportButton: {
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "#e5e5e5",
    backgroundColor: "#f5f6f8",
    paddingHorizontal: 14,
    paddingVertical: 9,
  },
  exportButtonText: {
    color: "#111111",
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0.4,
  },
  claimStack: {
    gap: 12,
  },
  claimStackTitle: {
    color: "#000000",
    fontFamily: theme.fonts.serif,
    fontSize: 20,
    fontWeight: "700",
  },
  disclaimerBox: {
    marginTop: 18,
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderTopWidth: 1,
    borderTopColor: theme.colors.line,
    gap: 4,
  },
  disclaimerTitle: {
    fontFamily: theme.fonts.serif,
    fontSize: 12,
    color: "#666666",
    fontWeight: "700",
    letterSpacing: 0.4,
    textTransform: "uppercase",
  },
  disclaimerBody: {
    fontFamily: theme.fonts.serif,
    fontSize: 12,
    lineHeight: 18,
    color: "#666666",
  },
  claimRow: {
    borderWidth: 1,
    borderColor: "#e5e5e5",
    borderRadius: 10,
    padding: 18,
    gap: 8,
    backgroundColor: "#ffffff",
  },
  claimGroupCard: {
    borderWidth: 1,
    borderColor: "#e5e5e5",
    borderRadius: 12,
    padding: 16,
    gap: 10,
    backgroundColor: "#ffffff",
  },
  claimSection: {
    paddingTop: 2,
  },
  claimSectionLabel: {
    color: "#6b7280",
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.8,
    textTransform: "uppercase",
  },
  claimAxis: {
    color: "#111111",
    fontFamily: theme.fonts.serif,
    fontSize: 18,
    fontWeight: "700",
    lineHeight: 26,
  },
  claimText: {
    color: "#222222",
    fontSize: 15,
    lineHeight: 24,
  },
  claimMeta: {
    color: "#777777",
    fontSize: 12,
    lineHeight: 19,
  },
  claimQuote: {
    color: "#2f3440",
    fontFamily: theme.fonts.serif,
    fontSize: 14,
    lineHeight: 22,
  },
  claimConfidence: {
    color: "#4b5563",
    fontSize: 13,
    lineHeight: 20,
  },
  claimAxisRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12,
  },
  claimAxisCount: {
    color: "#5f6673",
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.6,
    textTransform: "uppercase",
  },
  claimSubgroup: {
    gap: 8,
  },
  claimSubcard: {
    borderLeftWidth: 2,
    borderLeftColor: "#d9dde5",
    paddingLeft: 12,
    gap: 4,
  },
  claimSubitem: {
    color: "#4b5563",
    fontSize: 13,
    lineHeight: 20,
  },
  claimSubbody: {
    color: "#4b5563",
    fontSize: 13,
    lineHeight: 20,
  },
  claimSubmeta: {
    color: "#6b7280",
    fontSize: 12,
    lineHeight: 18,
  },
  claimEvidenceCard: {
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 10,
    padding: 12,
    gap: 6,
    backgroundColor: "#f8f9fb",
  },
  inlineActionButton: {
    alignSelf: "flex-start",
    borderWidth: 1,
    borderColor: "#d1d5db",
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 6,
    backgroundColor: "#ffffff",
  },
  inlineActionText: {
    color: "#111111",
    fontSize: 11,
    fontWeight: "700",
  },
  previewCard: {
    gap: 12,
  },
  previewTitle: {
    color: "#111111",
    fontFamily: theme.fonts.serif,
    fontSize: 18,
    fontWeight: "700",
  },
  previewRow: {
    gap: 14,
  },
  previewTile: {
    width: 340,
    gap: 8,
  },
  previewImage: {
    width: 340,
    height: 480,
    borderWidth: 1,
    borderColor: "#e5e5e5",
    borderRadius: 8,
    backgroundColor: "#ffffff",
  },
  previewCaption: {
    color: "#777777",
    fontSize: 11,
    fontWeight: "600",
    letterSpacing: 0.5,
    textTransform: "uppercase",
  },
  drawerWrap: {
    width: "100%",
    maxWidth: 800,
  },
  precedentToggle: {
    borderWidth: 1,
    borderColor: "#e5e5e5",
    borderRadius: 12,
    backgroundColor: "#ffffff",
    paddingHorizontal: 18,
    paddingVertical: 16,
    gap: 4,
  },
  precedentToggleTitle: {
    color: "#111111",
    fontFamily: theme.fonts.serif,
    fontSize: 18,
    fontWeight: "700",
  },
  precedentToggleMeta: {
    color: "#777777",
    fontSize: 12,
    lineHeight: 18,
  },
  documentConfigurator: {
    borderTopWidth: 1,
    borderTopColor: "#e5e7eb",
    borderBottomWidth: 1,
    borderBottomColor: "#e5e7eb",
    backgroundColor: "#f8f9fb",
    paddingHorizontal: 16,
    paddingVertical: 14,
    gap: 12,
    marginTop: 10,
  },
  documentConfiguratorHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: 16,
  },
  documentConfiguratorHeading: {
    gap: 4,
  },
  documentConfiguratorTitle: {
    color: "#111111",
    fontFamily: theme.fonts.serif,
    fontSize: 18,
    fontWeight: "700",
  },
  documentConfiguratorHint: {
    color: theme.colors.subtle,
    fontSize: 13,
    lineHeight: 21,
  },
  documentCustomRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  documentModeBadge: {
    width: "100%",
    maxWidth: 800,
    alignSelf: "center",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 16,
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 14,
    backgroundColor: "#f8f9fb",
    paddingHorizontal: 18,
    paddingVertical: 14,
    marginBottom: 6,
  },
  documentModeBadgeTextWrap: {
    flex: 1,
    gap: 2,
  },
  documentModeBadgeTitle: {
    color: "#111111",
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0.8,
    textTransform: "uppercase",
  },
  documentModeBadgeBody: {
    color: "#667085",
    fontSize: 13,
    lineHeight: 20,
  },
  inputWrapper: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    paddingHorizontal: 24,
    paddingTop: 20,
    paddingBottom: 32,
    backgroundColor: "rgba(255,255,255,0.96)",
  },
  inputBox: {
    width: "100%",
    maxWidth: 800,
    alignSelf: "center",
    position: "relative",
    borderWidth: 1,
    borderColor: "#e5e5e5",
    borderRadius: 12,
    backgroundColor: "#ffffff",
    shadowColor: "#000000",
    shadowOpacity: 0.06,
    shadowRadius: 30,
    shadowOffset: { width: 0, height: 8 },
    overflow: "hidden",
  },
  inputModeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 14,
    paddingTop: 12,
  },
  inputModeButton: {
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 7,
    backgroundColor: "#f3f3f3",
  },
  inputModeButtonActive: {
    backgroundColor: "#000000",
  },
  inputModeText: {
    color: "#777777",
    fontSize: 12,
    fontWeight: "700",
  },
  inputModeTextActive: {
    color: "#ffffff",
  },
  docPresetBar: {
    paddingHorizontal: 18,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: "#e5e5e5",
    backgroundColor: "#fafafa",
    gap: 10,
  },
  docPresetLabel: {
    fontSize: 14,
    fontWeight: "700",
    color: "#111111",
  },
  docPresetWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
  },
  uploadChip: {
    alignSelf: "flex-start",
    borderWidth: 1,
    borderColor: "#111111",
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: "#ffffff",
  },
  uploadChipText: {
    color: "#111111",
    fontSize: 13,
    fontWeight: "700",
  },
  docPresetChip: {
    borderWidth: 1,
    borderColor: "#e5e5e5",
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: "#ffffff",
  },
  docPresetChipActive: {
    backgroundColor: "#000000",
    borderColor: "#000000",
  },
  docPresetChipText: {
    color: "#111111",
    fontSize: 13,
    fontWeight: "600",
  },
  docPresetChipTextActive: {
    color: "#ffffff",
  },
  pathInputWrap: {
    borderBottomWidth: 1,
    borderBottomColor: "#e5e5e5",
    backgroundColor: "#ffffff",
  },
  pathInput: {
    flex: 1,
    minHeight: 44,
    paddingHorizontal: 18,
    paddingVertical: 12,
    color: "#111111",
    fontSize: 14,
    borderWidth: 1,
    borderColor: "#e5e5e5",
    borderRadius: 10,
    backgroundColor: "#ffffff",
  },
  uploadedSampleLabel: {
    color: theme.colors.subtle,
    fontSize: 12,
    lineHeight: 18,
  },
  textarea: {
    width: "100%",
    minHeight: 72,
    maxHeight: 220,
    paddingLeft: 20,
    paddingRight: 64,
    paddingTop: 20,
    paddingBottom: 20,
    borderWidth: 0,
    color: "#111111",
    fontSize: 16,
    lineHeight: 26,
    textAlignVertical: "top",
  },
  sendButton: {
    position: "absolute",
    right: 14,
    bottom: 12,
    width: 40,
    height: 40,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#000000",
  },
  sendButtonDisabled: {
    opacity: 0.4,
  },
  sendButtonText: {
    color: "#ffffff",
    fontSize: 20,
    fontWeight: "700",
    marginTop: -2,
  },
  errorMessage: {
    width: "100%",
    padding: 18,
    borderWidth: 1,
    borderColor: "#d6a2a2",
    borderRadius: 12,
    backgroundColor: "#fff3f1",
    gap: 8,
  },
  errorTitle: {
    color: "#8c1d18",
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0.7,
    textTransform: "uppercase",
  },
  errorBody: {
    color: "#5d1a16",
    fontSize: 14,
    lineHeight: 22,
  },
  buttonPressed: {
    opacity: 0.88,
  },
});
