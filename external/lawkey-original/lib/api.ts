export type JobMode = "question" | "document";

export type JobStatusPayload = {
  jobId: string;
  clientId?: string;
  mode: JobMode;
  userTask?: string;
  phase: string;
  state: string;
  selectedPrecedentCount: number;
  completedChunks: number;
  totalChunks: number;
  workerCount: number;
  elapsedSeconds: number;
  etaSeconds: number;
  currentCaseNumber: string;
  currentExcerpt: string;
  selectionKeywords?: string[];
  headlineFrames?: string[];
  lastApiActivityAt?: string;
  lastApiEvent?: string;
  lastApiResult?: string;
  scheduler: {
    keyCount: number;
    coolingKeys: number;
    inflight: number;
    nextReadyInMs: number;
    minGapMs: number;
    maxInflightPerKey: number;
    rpmLimit: number;
    tpmLimit: number;
    globalMaxInflight: number;
  };
  error: string;
  createdAt: number;
  finishedAt: number | null;
  queuePosition?: number;
  analysisMode?: AnalysisMode;
};

const SELECTION_HEADLINES = [
  "관련 판례를 선별하는 중",
  "유형과 쟁점을 정리하는 중",
  "유사 판례 후보를 좁히는 중",
  "핵심 논점에 맞는 판례를 모으는 중",
];

const ACTIVE_PROCESSING_STATES = new Set([
  "analyzing_chunks",
  "summarizing_precedents",
  "writing_final_draft",
  "writing_document",
  "applying_coverage_patch",
  "exporting_artifacts",
]);
const ACTIVE_PROCESSING_HEADLINES = [
  "선택된 판례를 정리하는 중",
  "핵심 논리를 묶는 중",
  "주장과 인용을 엮는 중",
  "최종 분석 문장을 다듬는 중",
];

export type SelectedPrecedent = {
  precedentId: string;
  alternatePrecedentIds?: string[];
  caseNumber: string;
  title: string;
  citation?: string;
  court: string;
  decisionDate: string;
  sourcePath: string;
  relativePath: string;
  fullText: string;
  excerpt: string;
  summary?: string;
};

export type UsedQuote = {
  quote: string;
  charStart: number | null;
  charEnd: number | null;
  quoteRole: string;
  claimAxis: string;
  whyItMatters: string;
  evidenceId: string;
};

export type PrecedentDetailPayload = SelectedPrecedent & {
  usedQuotes: UsedQuote[];
  summaryOverlay: string;
  contextOverlay: string;
};

export type JobResultPayload = {
  jobId: string;
  mode: JobMode;
  answerMarkdown: string;
  selectedPrecedents: SelectedPrecedent[];
  usedPrecedents?: SelectedPrecedent[];
  claims: ClaimRecord[];
  selectedClaims?: ClaimRecord[];
  // Beta-7+: writer's actual citations vs planner candidates.
  citedClaims?: ClaimRecord[];
  candidateClaims?: ClaimRecord[];
  answerPlan?: {
    likely_outcome?: string;
    confidence_basis?: string[];
    helpful_facts?: string[];
    harmful_facts?: string[];
    body_claim_ids?: string[];
    claim_groups?: Array<{
      label: string;
      claim_ids: string[];
    }>;
    precedent_buckets?: {
      very_similar?: PrecedentBucketItem[];
      similar?: PrecedentBucketItem[];
      usable?: PrecedentBucketItem[];
      other?: PrecedentBucketItem[];
    };
  };
  usedPrecedentIds: string[];
  summary: Record<string, unknown>;
  outputPaths: {
    runDir: string;
    variantDir: string;
    answerPath: string;
    markdownPath: string;
    markdownUrl: string;
    htmlPath: string;
    htmlUrl: string;
    hwpxPath: string;
    hwpxUrl: string;
    pdfPath: string;
    pdfUrl: string;
    previewImagePaths: string[];
    previewImageUrls: string[];
  };
};

export type PrecedentBucketItem = {
  case_number?: string;
  court?: string;
  decision_date?: string;
  case_name?: string;
  supported_claim_ids?: string[];
  supported_claim_axes?: string[];
  why?: string;
  precedentId?: string;
  title?: string;
  citation?: string;
  excerpt?: string;
  summary?: string;
};

export type ClaimRecord = {
  claim_id?: string;
  claim_axis?: string;
  claim_text?: string;
  citation?: string;
  stance_to_user_goal?: string;
  certainty?: string;
  certainty_reason?: string;
  case_number?: string;
  court?: string;
  decision_date?: string;
  case_name?: string;
  source_file_id?: string;
  supporting_case_count?: number;
  supporting_cases?: Array<{
    case_number?: string;
    court?: string;
    decision_date?: string;
    case_name?: string;
    document_title?: string;
    relative_path?: string;
  }>;
  context_summary?: string;
  case_summary?: string;
  favorable_basis?: string[];
  unfavorable_basis?: string[];
  favorable_factors?: string[];
  unfavorable_factors?: string[];
  required_facts?: string[];
  missing_facts?: string[];
  cautions?: string[];
  counter_evidence?: string[];
  support_spans?: Array<{ quote?: string; evidence_id?: string }>;
  oppose_spans?: Array<{ quote?: string; evidence_id?: string }>;
};

export type DocumentPreset = {
  id: string;
  label: string;
  path: string;
  paths?: string[];
};

export type DocumentConversationItem = {
  role: "user" | "assistant";
  text: string;
};

export type DocumentPreflightPayload = {
  userTask: string;
  documentPresetId?: string;
  samplePath?: string;
  sourceJobId?: string;
  conversation?: DocumentConversationItem[];
};

export type DocumentPreflightResponse = {
  ready: boolean;
  questions: string[];
  retrievalTask: string;
  draftingGoal: string;
  summary: string;
};

export type JobListItem = JobStatusPayload;

export type FollowUpJobResponse =
  | {
      mode: "answered_from_existing";
      sourceJobId: string;
      answerMarkdown: string;
      neededKeywords?: string[];
      missingInformation?: string[];
    }
  | {
      mode: "new_job_started";
      sourceJobId: string;
      jobId: string;
      statusUrl: string;
      resultUrl: string;
      neededKeywords?: string[];
      missingInformation?: string[];
    };

export type HighlightSegment = {
  text: string;
  highlighted: boolean;
};

function normalizeQuoteForMatch(value: string): string {
  return String(value || "").replace(/\s+/g, "");
}

const API_BASE = process.env.EXPO_PUBLIC_LAWKEY_API_BASE ?? "";

const ANSWER_META_LEAK_PATTERNS = [
  /Input:\s*A draft/i,
  /Goal:\s*Rewrite/i,
  /Constraints:/i,
  /Self[-\s]?Correction/i,
  /Final check/i,
  /Drafting the final response/i,
  /Wait,\s*the prompt/i,
  /Wait,\s*the instruction/i,
  /the prompt says/i,
  /Let's go/i,
  /claim_id lists?/i,
];

const DOCUMENT_META_LEAK_PATTERNS = [
  /Legal Professional/i,
  /Legal Opinion Writer/i,
  /Complaint\s*\(\s*고\s*소\s*장\s*\)/i,
  /Write a\s+"?(?:Complaint|Legal Opinion)/i,
  /Use\s+\*?only\*?\s+the provided ledger/i,
  /The user provided/i,
  /The user'?s task/i,
  /though the user'?s task/i,
  /Wait,\s*let'?s re-read/i,
  /Wait,\s*looking at the prompt/i,
  /Contradiction Check\s*:/i,
  /Resolution\s*:/i,
  /Problem\s*:/i,
  /Decision\s*:/i,
  /Strategy\s*:/i,
  /Subject Matter\s*:/i,
  /\bClaim\s+\d+\s*:/i,
  /\bStructure\s*:/i,
  /\bTone\s*:/i,
  /Drafting Content\s*:/i,
  /Refining the/i,
  /Check against constraints/i,
  /Final Review of the Ledger usage/i,
  /Final Polish/i,
  /Final Plan\s*:/i,
  /Final Text Construction\s*:/i,
  /Mental Draft\s*:/i,
  /Final check/i,
  /\*?\s*Check\s*:\s*/i,
  /Formatting\s*:\s*Plain text/i,
  /Drafting the final response/i,
  /Proceeding to generate/i,
];

const DOCUMENT_STRUCTURAL_OUTPUT_START_PATTERNS = [
  /^\s*(?:#+\s*)?고\s*소\s*장\s*$/im,
  /^\s*(?:#+\s*)?1\.\s*고소인(?=\s|$)/im,
];

const DOCUMENT_OUTPUT_START_PATTERNS = [
  /법률\s*검토\s*의견서|변호인\s*의견서|변호인의견서|내용증명|고\s*소\s*장|고발장|준비서면|답변서|항소이유서|탄원서|진정서/i,
  /^사\s*건\s+.+$/m,
  /^수\s*신(?:인)?\s*[:：]?\s*.+$/m,
  /^발\s*신(?:인)?\s*[:：]?\s*.+$/m,
  /^제\s*목\s*[:：]?\s*.+$/m,
];

const ALL_META_LEAK_PATTERNS = [...ANSWER_META_LEAK_PATTERNS, ...DOCUMENT_META_LEAK_PATTERNS];

function findDocumentOutputStart(raw: string, after: number): number | null {
  const searchStart = Math.max(0, after);
  const searchArea = raw.slice(searchStart);
  for (const pattern of DOCUMENT_STRUCTURAL_OUTPUT_START_PATTERNS) {
    const match = pattern.exec(searchArea);
    if (!match || match.index === undefined) {
      continue;
    }
    return searchStart + match.index;
  }
  let best: number | null = null;
  for (const pattern of DOCUMENT_OUTPUT_START_PATTERNS) {
    const match = pattern.exec(searchArea);
    if (!match || match.index === undefined) {
      continue;
    }
    const candidate = searchStart + match.index;
    best = best === null ? candidate : Math.min(best, candidate);
  }
  return best;
}

function ensureDocumentHeading(markdown: string): string {
  const cleaned = String(markdown || "").trim();
  if (/^(?:#+\s*)?1\.\s*고소인(?=\s|$)/i.test(cleaned)) {
    return `고    소    장\n\n${cleaned}`;
  }
  return cleaned;
}

export function stripAnswerMetaLeak(markdown: string): string {
  const raw = String(markdown || "").trim();
  if (!raw) {
    return "";
  }
  if (!ALL_META_LEAK_PATTERNS.some((pattern) => pattern.test(raw))) {
    return raw;
  }
  const finalAnswerMatches = [...raw.matchAll(/##\s*종합\s*판단/g)];
  if (finalAnswerMatches.length) {
    const start = finalAnswerMatches[finalAnswerMatches.length - 1].index ?? 0;
    return raw.slice(start).replace(/^\*?\s*let'?s go\.?\s*\*?/i, "").trim() || raw;
  }
  const summaryMatches = [...raw.matchAll(/###\s*가장\s*가능성\s*높은\s*결론/g)];
  if (summaryMatches.length) {
    const start = summaryMatches[summaryMatches.length - 1].index ?? 0;
    return raw.slice(start).replace(/^\*?\s*let'?s go\.?\s*\*?/i, "").trim() || raw;
  }
  const markerEnds = ALL_META_LEAK_PATTERNS.flatMap((pattern) => {
    const flags = pattern.flags.includes("g") ? pattern.flags : `${pattern.flags}g`;
    const globalPattern = new RegExp(pattern.source, flags);
    return [...raw.matchAll(globalPattern)].map((match) => (match.index ?? 0) + match[0].length);
  });
  const documentStart = findDocumentOutputStart(raw, Math.max(0, ...markerEnds));
  if (documentStart !== null) {
    return ensureDocumentHeading(raw.slice(documentStart).trim() || raw);
  }
  return raw
    .split(/\r?\n/)
    .filter((line) => !ALL_META_LEAK_PATTERNS.some((pattern) => pattern.test(line)))
    .join("\n")
    .trim();
}

export function sanitizeJobResultPayload(result: JobResultPayload): JobResultPayload {
  return {
    ...result,
    answerMarkdown: stripAnswerMetaLeak(result.answerMarkdown),
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
      ...init,
    });
  } catch (caught) {
    const rawMessage = caught instanceof Error ? caught.message : String(caught || "");
    const detail = rawMessage && !/Load failed|Failed to fetch/i.test(rawMessage) ? ` (${rawMessage})` : "";
    throw new Error(`서버 연결에 실패했습니다${detail}`);
  }
  if (!response.ok) {
    const message = await response.text();
    throw new Error(formatApiError(response.status, message));
  }
  return (await response.json()) as T;
}

function formatApiError(status: number, body: string): string {
  const raw = String(body || "").trim();
  if (/<!doctype html|<html[\s>]/i.test(raw)) {
    if (status === 524 || /524:\s*A timeout occurred|A timeout occurred/i.test(raw)) {
      return "서버 요청이 시간 초과되었습니다. 추가질문은 새 작업으로 다시 보내주세요. (HTTP 524)";
    }
    return `서버가 HTML 오류 페이지를 반환했습니다. (HTTP ${status})`;
  }
  return raw || `Request failed: ${status}`;
}

export type AnalysisMode = "precise" | "fast" | "beta1" | "beta2" | "beta3" | "beta4" | "beta5" | "beta6" | "beta7" | "beta8";

export type IntentClassifyResult = {
  intent: "question" | "document";
  documentType: string;
  questions: string[];
};

export async function classifyIntent(payload: {
  userTask: string;
  context?: string;
}): Promise<IntentClassifyResult> {
  return request<IntentClassifyResult>("/api/intent-classify", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function createJob(payload: {
  mode: JobMode;
  userTask: string;
  clientId?: string;
  documentPresetId?: string;
  documentContext?: string;
  samplePath?: string;
  analysisMode?: AnalysisMode;
  skipIntentCheck?: boolean;
}): Promise<{ jobId: string; statusUrl: string; resultUrl: string }> {
  return request("/api/jobs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getJobStatus(jobId: string): Promise<JobStatusPayload> {
  return request(`/api/jobs/${jobId}`);
}

export async function getJobResult(jobId: string): Promise<JobResultPayload> {
  return sanitizeJobResultPayload(await request<JobResultPayload>(`/api/jobs/${jobId}/result`));
}

export async function cancelJob(jobId: string): Promise<JobStatusPayload> {
  return request(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: "POST",
    body: JSON.stringify({ reason: "user_cancelled" }),
  });
}

export async function followUpJob(
  jobId: string,
  payload: { userTask: string; clientId?: string; forceNewJob?: boolean },
): Promise<FollowUpJobResponse> {
  const response = await request<FollowUpJobResponse>(`/api/jobs/${encodeURIComponent(jobId)}/follow-up`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (response.mode === "answered_from_existing") {
    return {
      ...response,
      answerMarkdown: stripAnswerMetaLeak(response.answerMarkdown),
    };
  }
  return response;
}

export async function getPrecedentDetail(jobId: string, precedentId: string): Promise<PrecedentDetailPayload> {
  return request(`/api/jobs/${encodeURIComponent(jobId)}/precedents/${encodeURIComponent(precedentId)}`);
}

export async function listDocumentPresets(): Promise<DocumentPreset[]> {
  return request("/api/document-presets");
}

export async function listJobs(clientId?: string): Promise<JobListItem[]> {
  const suffix = clientId?.trim() ? `?clientId=${encodeURIComponent(clientId.trim())}` : "";
  return request(`/api/jobs${suffix}`);
}

export async function uploadSampleFile(file: File): Promise<{ path: string; sampleId?: string; label: string }> {
  const formData = new FormData();
  formData.append("file", file);
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/uploads`, {
      method: "POST",
      body: formData,
    });
  } catch (caught) {
    const rawMessage = caught instanceof Error ? caught.message : String(caught || "");
    const detail = rawMessage && !/Load failed|Failed to fetch/i.test(rawMessage) ? ` (${rawMessage})` : "";
    throw new Error(`서버 연결에 실패했습니다${detail}`);
  }
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Upload failed: ${response.status}`);
  }
  return (await response.json()) as { path: string; label: string };
}

export async function preflightDocument(payload: DocumentPreflightPayload): Promise<DocumentPreflightResponse> {
  return request("/api/document-preflight", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

function sanitizeHeadlineText(value: string): string {
  const normalizedLines = String(value || "")
    .replace(/<br\s*\/?>/gi, "\n")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((line) => !/^\[판례\s*\d+\]$/i.test(line))
    .filter((line) => !/^제목:/i.test(line))
    .filter((line) => !/^확정\s*날짜:/i.test(line))
    .filter((line) => !/^url:/i.test(line))
    .filter((line) => !/^\[사건\s*정보\]$/i.test(line))
    .filter((line) => !/^\d+\s*심$/i.test(line))
    .filter((line) => !/^(취득세|소득세|법인세|부가가치세|양도소득세|상속세|증여세|지방세)$/i.test(line))
    .filter((line) => !/^[가-힣A-Za-z0-9·()\s]+법원\s+\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*선고\s*[0-9가-힣()누구합단도재마나카허저]+\s*판결(?:\s*\[[^\]]+\])?$/i.test(line));
  const collapsed = normalizedLines.join(" ");
  const sanitized = collapsed
    .replace(/\[판례\s*\d+\]\s*/gi, "")
    .replace(/^[가-힣A-Za-z0-9·()\s]+법원\s+\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*선고\s*[0-9가-힣()누구합단도재마나카허저]+판결\s*/i, "")
    .replace(/제목:\s*/gi, "")
    .replace(/확정\s*날짜:\s*/gi, "")
    .replace(/【[^】]+】/g, " ")
    .replace(/▣[^\n]+/g, " ")
    .replace(/url:\s*https?:\/\/\S+/gi, "")
    .replace(/\[사건\s*정보\]/gi, " ")
    .replace(/[-]{5,}/g, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/^(?:(?:\d+\s*심)|(?:취득세|소득세|법인세|부가가치세|양도소득세|상속세|증여세|지방세))\s+/gi, "")
    .replace(/^(?:(?:\d+\s*심)|(?:취득세|소득세|법인세|부가가치세|양도소득세|상속세|증여세|지방세))\s+/gi, "")
    .replace(/^(?:주문|이유)\s*/i, "")
    .replace(/^\d+\.\s*/g, "")
    .replace(/\s+(?:주문|이유)\s+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  const sentence = sanitized.split(/(?<=[.!?다])\s+/)[0]?.trim() || sanitized;
  return sentence.slice(0, 140);
}

function isMeaningfulHeadlineText(value: string): boolean {
  const text = sanitizeHeadlineText(value);
  if (!text) {
    return false;
  }
  const bare = text.replace(/^\[[^\]]+\]\s*/, "").trim().replace(/^[·.\-–—()\s]+|[·.\-–—()\s]+$/g, "");
  if (!bare) {
    return false;
  }
  if (/^[0-9.]+$/.test(bare)) {
    return false;
  }
  if (/^[0-9.\-–—()\s]+$/.test(bare)) {
    return false;
  }
  if (bare.length <= 2 && /^[A-Za-z0-9가-힣]+$/.test(bare)) {
    return false;
  }
  return true;
}

export function buildHeadlineFrames(status: JobStatusPayload | null, result: JobResultPayload | null): string[] {
  const frames: string[] = [];
  const statusFrames = (status?.headlineFrames ?? [])
    .map((frame) => sanitizeHeadlineText(frame))
    .filter((frame) => frame && isMeaningfulHeadlineText(frame));
  const selectionState = status?.state
    ? ["queued", "waiting_for_capacity", "generating_keywords"].includes(status.state)
    : false;
  if (statusFrames.length) {
    frames.push(...statusFrames);
  } else if (selectionState) {
    return SELECTION_HEADLINES;
  }
  if (!frames.length && status?.currentExcerpt?.trim()) {
    const currentFrame = [status.currentCaseNumber ? `[${status.currentCaseNumber}]` : "", sanitizeHeadlineText(status.currentExcerpt)]
      .filter(Boolean)
      .join(" ")
      .trim();
    if (currentFrame && isMeaningfulHeadlineText(currentFrame)) {
      frames.push(currentFrame);
    }
  }
  if (!frames.length && status?.state && ACTIVE_PROCESSING_STATES.has(status.state)) {
    frames.push(...ACTIVE_PROCESSING_HEADLINES);
  }
  for (const precedent of result?.selectedPrecedents ?? []) {
    const body = sanitizeHeadlineText(precedent.summary || precedent.title || precedent.excerpt);
    const frame = [precedent.caseNumber ? `[${precedent.caseNumber}]` : "", body]
      .filter(Boolean)
      .join(" ")
      .trim();
    if (frame && isMeaningfulHeadlineText(frame)) {
      frames.push(frame);
    }
  }
  const unique = frames.filter(Boolean).filter((value, index, array) => array.indexOf(value) === index);
  return unique.length ? unique : ["실시간 분석 준비 중"];
}

export function getInitialPrecedentId(result: JobResultPayload | null, currentId: string): string {
  if (!result) {
    return "";
  }
  const ids = new Set((result.usedPrecedents?.length ? result.usedPrecedents : result.selectedPrecedents).map((item) => item.precedentId));
  if (currentId && ids.has(currentId)) {
    return currentId;
  }
  const explicitUsed = result.usedPrecedents?.find((item) => item.precedentId && ids.has(item.precedentId))?.precedentId;
  if (explicitUsed) {
    return explicitUsed;
  }
  const used = result.usedPrecedentIds.find((id) => ids.has(id));
  if (used) {
    return used;
  }
  return (result.usedPrecedents?.[0]?.precedentId || result.selectedPrecedents[0]?.precedentId) ?? "";
}

export function buildHighlightSegments(fullText: string, usedQuotes: UsedQuote[]): HighlightSegment[] {
  if (!fullText) {
    return [];
  }
  const ranges = [...usedQuotes]
    .filter((quote) => typeof quote.charStart === "number" && typeof quote.charEnd === "number" && (quote.charEnd ?? 0) > (quote.charStart ?? 0))
    .map((quote) => ({
      charStart: Math.max(0, quote.charStart ?? 0),
      charEnd: Math.min(fullText.length, quote.charEnd ?? 0),
    }))
    .filter((quote) => quote.charEnd > quote.charStart)
    .sort((left, right) => left.charStart - right.charStart);
  if (!ranges.length) {
    return [{ text: fullText, highlighted: false }];
  }

  const mergedRanges: Array<{ charStart: number; charEnd: number }> = [];
  for (const range of ranges) {
    const previous = mergedRanges[mergedRanges.length - 1];
    if (previous && range.charStart <= previous.charEnd) {
      previous.charEnd = Math.max(previous.charEnd, range.charEnd);
      continue;
    }
    mergedRanges.push({ ...range });
  }

  const segments: HighlightSegment[] = [];
  let cursor = 0;
  for (const range of mergedRanges) {
    const start = range.charStart;
    const end = range.charEnd;
    if (start > cursor) {
      segments.push({ text: fullText.slice(cursor, start), highlighted: false });
    }
    if (end > start) {
      segments.push({ text: fullText.slice(start, end), highlighted: true });
    }
    cursor = Math.max(cursor, end);
  }
  if (cursor < fullText.length) {
    segments.push({ text: fullText.slice(cursor), highlighted: false });
  }
  return segments.filter((segment) => segment.text.length > 0);
}

export function findTargetUsedQuote(usedQuotes: UsedQuote[], targetQuoteText?: string): UsedQuote | undefined {
  const resolved = usedQuotes.filter((quote) => typeof quote.charStart === "number" && (quote.charStart ?? -1) >= 0);
  if (!resolved.length) {
    return undefined;
  }
  const target = normalizeQuoteForMatch(targetQuoteText || "");
  if (target) {
    const exact = resolved.find((quote) => normalizeQuoteForMatch(quote.quote) === target);
    if (exact) {
      return exact;
    }
    const contained = resolved.find((quote) => {
      const current = normalizeQuoteForMatch(quote.quote);
      return current.includes(target) || target.includes(current);
    });
    if (contained) {
      return contained;
    }
  }
  return resolved[0];
}
