import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  type AnalysisMode,
  type DocumentPreset,
  type FollowUpJobResponse,
  type JobMode,
  type JobResultPayload,
  type JobStatusPayload,
  type SelectedPrecedent,
  type PrecedentDetailPayload,
  type UsedQuote,
} from "./api";
import { lawkeyUniversalKernel } from "./universal-ui-kernel";
import {
  loadResultSnapshot,
  loadResultSnapshotAsync,
  saveViewedSessionId,
  loadStatusSnapshot,
  loadStatusSnapshotAsync,
} from "./session-history";

const POLL_MS = 1800;

function normalized(value: string | undefined): string {
  return String(value || "").replace(/\s+/g, " ").trim();
}

// Characters the LLM may wrap around a quoted span that aren't present in the
// underlying precedent text. Stripping these before matching avoids "「..」" or
// curly-quote wrapping defeating the lookup.
const QUOTE_WRAP_PATTERN = /^[\s"'`“”‘’「」『』《》<>()（）\[\]【】]+|[\s"'`“”‘’「」『』《》<>()（）\[\]【】]+$/gu;

function stripQuoteWrap(value: string): string {
  return String(value || "").replace(QUOTE_WRAP_PATTERN, "").trim();
}

export function appendFollowUpAnswerMarkdown(priorMarkdown: string, answerMarkdown: string): string {
  return [priorMarkdown.trim(), "---", answerMarkdown.trim()].filter(Boolean).join("\n\n");
}

export function shouldClearJobErrorForStatus(state: string): boolean {
  return !["failed", "interrupted"].includes(state);
}

function precedentMatchesClaim(precedent: SelectedPrecedent, claim: JobResultPayload["claims"][number]): boolean {
  if (claim.source_file_id && claim.source_file_id === precedent.precedentId) {
    return true;
  }
  const caseNumber = normalized(precedent.caseNumber);
  if (caseNumber && normalized(claim.case_number) === caseNumber) {
    return true;
  }
  return (claim.supporting_cases || []).some((item) => normalized(item.case_number) === caseNumber);
}

export type LocatedQuote = {
  charStart: number | null;
  charEnd: number | null;
  matchedText?: string; // The actual sentence from fullText, used to replace the LLM quote.
};

function locateQuote(fullText: string, quote: string): LocatedQuote {
  if (!fullText) {
    return { charStart: null, charEnd: null };
  }
  const trimmed = quote.trim();
  if (!trimmed) {
    return { charStart: null, charEnd: null };
  }

  // 1) Exact substring match — fast path when the LLM emitted the quote
  //    verbatim. matchedText echoes the original quote unchanged.
  const direct = fullText.indexOf(trimmed);
  if (direct >= 0) {
    return { charStart: direct, charEnd: direct + trimmed.length, matchedText: trimmed };
  }

  // 2) Strip wrap chars and try exact again.
  const unwrapped = stripQuoteWrap(trimmed);
  if (unwrapped && unwrapped !== trimmed) {
    const directUnwrapped = fullText.indexOf(unwrapped);
    if (directUnwrapped >= 0) {
      return { charStart: directUnwrapped, charEnd: directUnwrapped + unwrapped.length, matchedText: unwrapped };
    }
  }

  // 3) Whitespace-normalized full-needle match.
  const indexed = buildNormalizedIndex(fullText);
  const baseNeedle = normalized(unwrapped || trimmed);
  if (baseNeedle && indexed.indices.length) {
    const fullMatch = locateNormalizedNeedle(indexed, baseNeedle);
    if (fullMatch) {
      return {
        ...fullMatch,
        matchedText: fullText.slice(fullMatch.charStart, fullMatch.charEnd),
      };
    }
  }

  // 4) Force-match by similarity: split fullText into candidate sentences and
  //    pick the single highest-similarity match, regardless of how different
  //    it is. The user's intent is "small char/whitespace differences should
  //    deterministically yield the one closest sentence — replace LLM quote
  //    with that real sentence to block hallucination".
  const forced = forceMatchSentence(fullText, baseNeedle || normalized(trimmed));
  if (forced) {
    return forced;
  }

  return { charStart: null, charEnd: null };
}

// Split into sentence-ish chunks on common Korean/CJK terminators.
// Keeps each chunk's [start, end) offsets in the original text.
function splitFullTextIntoSentences(fullText: string): Array<{ text: string; start: number; end: number }> {
  const out: Array<{ text: string; start: number; end: number }> = [];
  const length = fullText.length;
  let cursor = 0;
  for (let i = 0; i < length; i += 1) {
    const ch = fullText[i];
    const isTerminator = ch === "." || ch === "?" || ch === "!" || ch === "다" || ch === "\n";
    if (isTerminator) {
      // 다 (Korean sentence-final) only counts when followed by a sentence
      // boundary (whitespace/punctuation/EOF) to avoid splitting mid-word.
      if (ch === "다") {
        const next = fullText[i + 1] || "";
        if (next && !/[\s.?!,;:、。\n]/.test(next)) {
          continue;
        }
      }
      // Greedily consume trailing whitespace + punctuation to end the segment.
      let end = i + 1;
      while (end < length && /[\s.?!]/.test(fullText[end])) end += 1;
      const segment = fullText.slice(cursor, end);
      if (segment.trim().length >= 8) {
        out.push({ text: segment, start: cursor, end });
      }
      cursor = end;
    }
  }
  if (cursor < length) {
    const tail = fullText.slice(cursor);
    if (tail.trim().length >= 8) {
      out.push({ text: tail, start: cursor, end: length });
    }
  }
  return out;
}

// Token-overlap similarity. Counts the number of normalized 3-character
// shingles shared by the needle and the candidate, divided by the smaller
// shingle set size. Insensitive to whitespace, robust to a few char drops.
function trigramSimilarity(a: string, b: string): number {
  const setA = trigrams(a);
  const setB = trigrams(b);
  if (setA.size === 0 || setB.size === 0) return 0;
  let common = 0;
  for (const tg of setA) {
    if (setB.has(tg)) common += 1;
  }
  return common / Math.min(setA.size, setB.size);
}

function trigrams(value: string): Set<string> {
  const compact = value.replace(/\s+/g, "");
  const set = new Set<string>();
  for (let i = 0; i + 3 <= compact.length; i += 1) {
    set.add(compact.slice(i, i + 3));
  }
  return set;
}

function forceMatchSentence(fullText: string, needle: string): LocatedQuote | null {
  if (!fullText || !needle) return null;
  const candidates = splitFullTextIntoSentences(fullText);
  if (!candidates.length) return null;
  let bestScore = 0;
  let bestIdx = -1;
  for (let i = 0; i < candidates.length; i += 1) {
    const score = trigramSimilarity(needle, normalized(candidates[i].text));
    if (score > bestScore) {
      bestScore = score;
      bestIdx = i;
    }
  }
  // Require a minimum similarity floor so we don't return random sentences
  // when the LLM hallucinated something with no overlap.
  // Loose floor — the user's intent is "small char/whitespace differences
  // should yield exactly one closest sentence". Any nonzero overlap is good
  // enough to lock onto a real sentence.
  if (bestIdx < 0 || bestScore < 0.08) return null;
  const picked = candidates[bestIdx];
  return {
    charStart: picked.start,
    charEnd: picked.end,
    matchedText: picked.text.trim(),
  };
}

function locateNormalizedNeedle(
  indexed: { text: string; indices: number[] },
  needle: string,
): { charStart: number; charEnd: number } | null {
  if (!needle) {
    return null;
  }
  const pos = indexed.text.indexOf(needle);
  if (pos < 0) {
    return null;
  }
  const startChar = indexed.indices[pos];
  const endPos = Math.min(pos + needle.length - 1, indexed.indices.length - 1);
  const endChar = (indexed.indices[endPos] ?? startChar ?? 0) + 1;
  if (typeof startChar !== "number") {
    return null;
  }
  return { charStart: startChar, charEnd: endChar };
}

function buildNormalizedIndex(text: string): { text: string; indices: number[] } {
  const chars: string[] = [];
  const indices: number[] = [];
  let previousWasSpace = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (/\s/.test(char)) {
      if (!previousWasSpace && chars.length) {
        chars.push(" ");
        indices.push(index);
      }
      previousWasSpace = true;
      continue;
    }
    chars.push(char);
    indices.push(index);
    previousWasSpace = false;
  }
  // Drop any trailing space marker so `indices` and `text` stay aligned after
  // the consumer trims trailing whitespace from the joined string.
  while (chars.length && chars[chars.length - 1] === " ") {
    chars.pop();
    indices.pop();
  }
  return { text: chars.join(""), indices };
}

function buildLocalPrecedentDetail(result: JobResultPayload | null, precedentId: string): PrecedentDetailPayload | null {
  if (!result || !precedentId) {
    return null;
  }
  const byId = new Map<string, SelectedPrecedent>();
  [...(result.usedPrecedents || []), ...result.selectedPrecedents].forEach((precedent) => {
    byId.set(precedent.precedentId, precedent);
    (precedent.alternatePrecedentIds || []).forEach((alternateId) => {
      if (alternateId) {
        byId.set(alternateId, precedent);
      }
    });
  });
  const precedent = byId.get(precedentId);
  if (!precedent) {
    return null;
  }
  const matchedClaims = result.claims.filter((claim) => precedentMatchesClaim(precedent, claim));
  const usedQuotes: UsedQuote[] = [];
  matchedClaims.forEach((claim, claimIndex) => {
    [
      { spans: claim.support_spans || [], role: "support" },
      { spans: claim.oppose_spans || [], role: "oppose" },
    ].forEach((group) => {
      group.spans.forEach((span, spanIndex) => {
        const quote = String(span.quote || "").trim();
        if (!quote) {
          return;
        }
        const located = locateQuote(precedent.fullText, quote);
        // Force-replace the LLM quote with the actual matched sentence from
        // the precedent's full text whenever a similarity match is found.
        // This blocks small char/whitespace hallucinations from leaking
        // through to the inline citation card.
        const displayQuote = (located.matchedText || quote).trim();
        usedQuotes.push({
          quote: displayQuote,
          charStart: located.charStart,
          charEnd: located.charEnd,
          quoteRole: group.role,
          claimAxis: String(claim.claim_axis || "").trim(),
          whyItMatters: String(claim.context_summary || claim.claim_text || "").trim(),
          evidenceId: String(span.evidence_id || `${precedent.precedentId}-${claimIndex}-${spanIndex}`),
        });
      });
    });
  });
  const firstClaim = matchedClaims[0];
  const fullTextSnippet = deriveFullTextSnippet(precedent.fullText);
  return {
    ...precedent,
    usedQuotes: usedQuotes.slice(0, 10),
    summaryOverlay: precedent.summary || firstClaim?.case_summary || precedent.excerpt || fullTextSnippet || "요약이 아직 정리되지 않았습니다.",
    contextOverlay: firstClaim?.context_summary || firstClaim?.claim_text || precedent.excerpt || fullTextSnippet || "맥락이 아직 정리되지 않았습니다.",
  };
}

function deriveFullTextSnippet(fullText: string | undefined | null): string {
  const text = String(fullText || "").trim();
  if (!text) return "";
  // Skip known section header lines (`[주문]`, `[이유]`, etc.) and find the
  // first paragraph of substantive content. Used as a last-resort fallback
  // when neither summary nor excerpt is present.
  const lines = text.split(/\r?\n/);
  const buf: string[] = [];
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) {
      if (buf.length) break;
      continue;
    }
    if (/^\[[^\]]{1,30}\]$/.test(line)) continue;
    if (/^[0-9]+\.\s*$/.test(line)) continue;
    buf.push(line);
    if (buf.join(" ").length > 240) break;
  }
  const snippet = buf.join(" ").replace(/\s+/g, " ").trim();
  if (!snippet) return "";
  return snippet.length > 300 ? snippet.slice(0, 297) + "…" : snippet;
}

export function useLawkeyJob() {
  const [documentPresets, setDocumentPresets] = useState<DocumentPreset[]>([]);
  const [activeJobId, setActiveJobId] = useState("");
  const [status, setStatus] = useState<JobStatusPayload | null>(null);
  const [result, setResult] = useState<JobResultPayload | null>(null);
  const [selectedPrecedentId, setSelectedPrecedentId] = useState("");
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailCache, setDetailCache] = useState<Record<string, PrecedentDetailPayload>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const loadedResultFor = useRef("");
  // Set true while admin replay is driving synthetic status frames so the
  // server poll doesn't overwrite the predefined timeline with the real
  // (cached/completed) job state.
  const replayPausedRef = useRef(false);

  useEffect(() => {
    lawkeyUniversalKernel.listDocumentPresets().then(setDocumentPresets).catch(() => setDocumentPresets([]));
  }, []);

  useEffect(() => {
    if (!activeJobId) {
      return undefined;
    }
    let cancelled = false;

    const tick = async () => {
      // Admin replay drives status synthetically; skip the real poll while
      // the synthetic timeline is running so the server's actual completed
      // state doesn't short-circuit the 2-second-per-stage animation.
      if (replayPausedRef.current) {
        return;
      }
      try {
        const nextStatus = await lawkeyUniversalKernel.getJobStatus(activeJobId);
        if (cancelled) {
          return;
        }
        setStatus(nextStatus);
        if (nextStatus.state === "completed" && loadedResultFor.current !== activeJobId) {
          const nextResult = await lawkeyUniversalKernel.getJobResult(activeJobId);
          if (cancelled) {
            return;
          }
          const sanitizedNextResult = lawkeyUniversalKernel.sanitizeJobResultPayload(nextResult);
          loadedResultFor.current = activeJobId;
          setResult(sanitizedNextResult);
          setSelectedPrecedentId((current) => lawkeyUniversalKernel.getInitialPrecedentId(sanitizedNextResult, current));
        }
        if (["failed", "interrupted"].includes(nextStatus.state)) {
          setError(nextStatus.error || "분석 실행에 실패했습니다.");
        } else if (shouldClearJobErrorForStatus(nextStatus.state)) {
          setError("");
        }
      } catch (caught) {
        if (cancelled) {
          return;
        }
        const localStatus = loadStatusSnapshot(activeJobId) || (await loadStatusSnapshotAsync(activeJobId));
        const localResult = loadResultSnapshot(activeJobId) || (await loadResultSnapshotAsync(activeJobId));
        if (localStatus) {
          setStatus(localStatus);
        }
        if (localResult) {
          const sanitizedLocalResult = lawkeyUniversalKernel.sanitizeJobResultPayload(localResult);
          loadedResultFor.current = activeJobId;
          setResult(sanitizedLocalResult);
          setSelectedPrecedentId((current) => lawkeyUniversalKernel.getInitialPrecedentId(sanitizedLocalResult, current));
          setError("");
          return;
        }
        const message = caught instanceof Error ? caught.message : "";
        // Transient gateway / restart errors: swallow silently so polling retries.
        if (/HTTP\s5\d\d|HTML 오류|서버 연결에 실패|서버 요청이 시간 초과/i.test(message)) {
          return;
        }
        setError(message || "상태 조회 중 오류가 발생했습니다.");
      }
    };

    void tick();
    const handle = setInterval(() => {
      void tick();
    }, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(handle);
    };
  }, [activeJobId]);

  useEffect(() => {
    if (!activeJobId || !selectedPrecedentId || !detailOpen || detailCache[selectedPrecedentId]) {
      return;
    }
    let cancelled = false;
    lawkeyUniversalKernel.getPrecedentDetail(activeJobId, selectedPrecedentId)
      .then((detail) => {
        if (!cancelled) {
          setDetailCache((current) => ({ ...current, [selectedPrecedentId]: detail }));
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          if (buildLocalPrecedentDetail(result, selectedPrecedentId)) {
            return;
          }
          setError(caught instanceof Error ? caught.message : "판례 상세를 불러오지 못했습니다.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activeJobId, detailCache, detailOpen, result, selectedPrecedentId]);

  const headlineFrames = useMemo(() => lawkeyUniversalKernel.buildHeadlineFrames(status, result), [result, status]);
  const localSelectedDetail = useMemo(
    () => buildLocalPrecedentDetail(result, selectedPrecedentId),
    [result, selectedPrecedentId],
  );
  const selectedDetail = selectedPrecedentId ? detailCache[selectedPrecedentId] ?? localSelectedDetail : null;

  const openJob = useCallback((jobId: string) => {
    if (!jobId) {
      return;
    }
    saveViewedSessionId(jobId);
    setError("");
    setStatus(null);
    setResult(null);
    setSelectedPrecedentId("");
    setDetailOpen(false);
    setDetailCache({});
    loadedResultFor.current = "";
    setActiveJobId(jobId);
  }, []);

  const restoreLocalJob = useCallback(
    (payload: {
      jobId: string;
      status?: JobStatusPayload | null;
      result?: JobResultPayload | null;
      selectedPrecedentId?: string;
    }) => {
      const jobId = payload.jobId.trim();
      if (!jobId) {
        return;
      }
      saveViewedSessionId(jobId);
      setError("");
      setDetailOpen(false);
      setDetailCache({});
      const sanitizedResult = payload.result ? lawkeyUniversalKernel.sanitizeJobResultPayload(payload.result) : null;
      // Local snapshots are only a fast restore path; the server may have produced
      // a newer final artifact after the snapshot was written.
      loadedResultFor.current = "";
      setActiveJobId(jobId);
      setStatus(payload.status ?? null);
      setResult(sanitizedResult);
      setSelectedPrecedentId((current) =>
        lawkeyUniversalKernel.getInitialPrecedentId(sanitizedResult, payload.selectedPrecedentId || current),
      );
    },
    [],
  );

  const resetView = useCallback(() => {
    saveViewedSessionId("");
    setError("");
    setStatus(null);
    setResult(null);
    setSelectedPrecedentId("");
    setDetailOpen(false);
    setDetailCache({});
    loadedResultFor.current = "";
    setActiveJobId("");
  }, []);

  const submit = async (payload: {
    mode: JobMode;
    userTask: string;
    clientId?: string;
    documentPresetId?: string;
    documentContext?: string;
    samplePath?: string;
    analysisMode?: AnalysisMode;
    skipIntentCheck?: boolean;
  }) => {
    setSubmitting(true);
    setError("");
    setResult(null);
    setStatus(null);
    setSelectedPrecedentId("");
    setDetailOpen(false);
    setDetailCache({});
    loadedResultFor.current = "";
    try {
      const created = await lawkeyUniversalKernel.createJob(payload);
      openJob(created.jobId);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "실행 요청을 시작하지 못했습니다.");
    } finally {
      setSubmitting(false);
    }
  };

  const followUp = async (payload: {
    userTask: string;
    clientId?: string;
    forceNewJob?: boolean;
  }): Promise<FollowUpJobResponse> => {
    if (!activeJobId.trim()) {
      throw new Error("이어갈 기존 분석이 없습니다.");
    }
    setSubmitting(true);
    setError("");
    setDetailOpen(false);
    try {
      const response = await lawkeyUniversalKernel.followUpJob(activeJobId, payload);
      if (response.mode === "answered_from_existing") {
        const answer = response.answerMarkdown.trim();
        if (answer) {
          setResult((current) => {
            if (!current) {
              return current;
            }
            return {
              ...current,
              answerMarkdown: appendFollowUpAnswerMarkdown(current.answerMarkdown, answer),
            };
          });
        }
      } else if (response.jobId) {
        openJob(response.jobId);
      }
      return response;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "추가 질문 처리 중 오류가 발생했습니다.");
      throw caught;
    } finally {
      setSubmitting(false);
    }
  };

  const cancelActiveJob = async (): Promise<JobStatusPayload | null> => {
    const jobId = activeJobId.trim();
    if (!jobId) {
      return null;
    }
    setSubmitting(true);
    setError("");
    try {
      const nextStatus = await lawkeyUniversalKernel.cancelJob(jobId);
      setStatus(nextStatus);
      loadedResultFor.current = "";
      return nextStatus;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "요청 취소 중 오류가 발생했습니다.");
      throw caught;
    } finally {
      setSubmitting(false);
    }
  };

  const beginReplay = useCallback((replayJobId: string) => {
    const id = String(replayJobId || "").trim();
    if (!id) return;
    replayPausedRef.current = true;
    setError("");
    setDetailOpen(false);
    setDetailCache({});
    loadedResultFor.current = "";
    setResult(null);
    setStatus(null);
    setActiveJobId(id);
  }, []);

  const pushReplayStatus = useCallback((nextStatus: JobStatusPayload) => {
    setStatus(nextStatus);
  }, []);

  const finishReplay = useCallback(
    (finalStatus: JobStatusPayload, finalResult: JobResultPayload) => {
      const sanitized = lawkeyUniversalKernel.sanitizeJobResultPayload(finalResult);
      loadedResultFor.current = finalStatus.jobId || "";
      setStatus(finalStatus);
      setResult(sanitized);
      setSelectedPrecedentId((current) => lawkeyUniversalKernel.getInitialPrecedentId(sanitized, current));
      // Keep replayPaused true so subsequent polls don't overwrite the
      // edited/cached final state. Caller can release via exitReplay if a
      // real new send is started.
    },
    [],
  );

  const exitReplay = useCallback(() => {
    replayPausedRef.current = false;
  }, []);

  const updateReplayResultMarkdown = useCallback((nextMarkdown: string) => {
    setResult((current) => (current ? { ...current, answerMarkdown: nextMarkdown } : current));
  }, []);

  return {
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
  };
}
