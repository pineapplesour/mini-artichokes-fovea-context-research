import {
  buildDomainJobEndpoint,
  buildDomainJobResultEndpoint,
  buildDomainJobStatusEndpoint,
  normalizeDomainLanguage,
} from "./domain-factory";

export type DomainSource = {
  id: string;
  label?: string;
  title: string;
  citation: string;
  authorityBody: string;
  date: string;
  topic: string;
  type: string;
  dataset: string;
  path: string;
  url: string;
  score: number;
  verdict: string;
  excerpt: string;
};

export type DomainAnswerSection = {
  kind: "direct" | "evidence" | "boundary" | string;
  title: string;
  body: string;
  citations: string[];
};

export type DomainCitation = {
  sourceId: string;
  citation: string;
  title: string;
  authorityBody: string;
  dataset: string;
  type: string;
  score: number;
  excerpt: string;
};

export type DomainPassage = {
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

export type DomainAnswer = {
  jobId: string;
  product: string;
  query: string;
  language: string;
  answerMarkdown: string;
  answerSections?: DomainAnswerSection[];
  citationMap?: Record<string, DomainCitation>;
  passages?: DomainPassage[];
  sources: DomainSource[];
  selectedEvidence: DomainSource[];
  safetyNotice: string;
  delivery?: {
    mode: string;
    corpusShippedToClient: boolean;
    sourcePagination: { offset: number; limit: number; returned: number };
  };
  securityControls?: {
    sqliteMode: string;
    sqlParameters: string;
    pathPolicy: string;
    queryBounds: { maxChars: number; maxLimit: number };
    timeoutCancel: string;
    retrievedTextPolicy: string;
  };
  beta6: {
    analysisMode: string;
    facets: string[];
    queryStructuring?: {
      language: string;
      surfaceFacets: string[];
      expandedFacets: string[];
      familyCount: number;
      controls?: DomainControlSelection[];
    };
    queryFamilies?: Array<Record<string, unknown>>;
    candidateFrontier?: Record<string, unknown>;
    verifier?: Record<string, unknown>;
    rejectedLedger: Array<Record<string, unknown>>;
    selectedCount: number;
    chunkCount: number;
    selectedEvidenceHandoff?: string;
  };
};

export type DomainControlSelection = {
  id: string;
  scope?: string;
  facets?: string[];
  safetyBoundary?: boolean;
};

export type DomainQuestionOptions = {
  signal?: AbortSignal;
  timeoutMs?: number;
  controls?: DomainControlSelection[];
};

export async function runDomainQuestion(
  product: string,
  query: string,
  language: string,
  options: DomainQuestionOptions = {},
): Promise<DomainAnswer> {
  const resolvedLanguage = normalizeDomainLanguage(product, language);
  const controller = new AbortController();
  const timeout = windowOrGlobalSetTimeout(() => controller.abort(), options.timeoutMs ?? 120_000);
  const abortFromCaller = () => controller.abort();
  if (options.signal) {
    if (options.signal.aborted) controller.abort();
    options.signal.addEventListener("abort", abortFromCaller, { once: true });
  }
  try {
    const created = await fetch(buildDomainJobEndpoint(product), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify({ query, language: resolvedLanguage, limit: 8, controls: sanitizeControls(options.controls) }),
    });
    if (!created.ok) {
      throw new Error(await created.text());
    }
    const job = await created.json();
    return pollDomainJob(String(job.jobId || ""), controller.signal);
  } finally {
    if (options.signal) options.signal.removeEventListener("abort", abortFromCaller);
    clearTimeout(timeout);
  }
}

function sanitizeControls(controls: DomainControlSelection[] | undefined): DomainControlSelection[] {
  if (!Array.isArray(controls)) return [];
  return controls.slice(0, 4).map((control) => ({
    id: String(control.id || "").slice(0, 80),
    scope: control.scope === undefined ? undefined : String(control.scope || "").slice(0, 120),
    facets: Array.isArray(control.facets) ? control.facets.map((facet) => String(facet || "").slice(0, 80)).slice(0, 10) : [],
    safetyBoundary: control.safetyBoundary === true,
  })).filter((control) => control.id);
}

export function validateDomainAnswerPayload(payload: unknown): DomainAnswer {
  const root = expectRecord(payload, "domain answer");
  const jobId = expectString(root.jobId, "jobId");
  if (!jobId) throw new Error("invalid jobId");
  const sources = expectArray(root.sources, "sources").map((source, index) => validateSource(source, `sources[${index}]`));
  const selectedEvidence = Array.isArray(root.selectedEvidence)
    ? root.selectedEvidence.map((source, index) => validateSource(source, `selectedEvidence[${index}]`))
    : [];
  const beta6 = expectRecord(root.beta6, "beta6");
  const rejectedLedger = expectArray(beta6.rejectedLedger, "beta6.rejectedLedger");
  const facets = expectArray(beta6.facets, "beta6.facets").map((value) => String(value));
  const selectedCount = expectNumber(beta6.selectedCount, "beta6.selectedCount");
  const chunkCount = expectNumber(beta6.chunkCount, "beta6.chunkCount");
  const delivery = root.delivery === undefined ? undefined : validateDelivery(root.delivery);
  const securityControls = root.securityControls === undefined ? undefined : validateSecurityControls(root.securityControls);
  return {
    jobId,
    product: expectString(root.product, "product"),
    query: expectString(root.query, "query"),
    language: expectString(root.language, "language"),
    answerMarkdown: expectPublicText(root.answerMarkdown, "answerMarkdown"),
    answerSections: Array.isArray(root.answerSections)
      ? root.answerSections.map((section, index) => validateSection(section, `answerSections[${index}]`))
      : undefined,
    citationMap:
      typeof root.citationMap === "object" && root.citationMap !== null
        ? validateCitationMap(root.citationMap as Record<string, unknown>)
        : undefined,
    passages: Array.isArray(root.passages)
      ? root.passages.map((passage, index) => validatePassage(passage, `passages[${index}]`))
      : undefined,
    sources,
    selectedEvidence,
    safetyNotice: expectPublicText(root.safetyNotice, "safetyNotice"),
    delivery,
    securityControls,
    beta6: {
      analysisMode: expectString(beta6.analysisMode, "beta6.analysisMode"),
      facets,
      queryStructuring:
        typeof beta6.queryStructuring === "object" && beta6.queryStructuring !== null
          ? (beta6.queryStructuring as DomainAnswer["beta6"]["queryStructuring"])
          : undefined,
      queryFamilies: Array.isArray(beta6.queryFamilies) ? (beta6.queryFamilies as Array<Record<string, unknown>>) : undefined,
      candidateFrontier:
        typeof beta6.candidateFrontier === "object" && beta6.candidateFrontier !== null
          ? (beta6.candidateFrontier as Record<string, unknown>)
          : undefined,
      verifier: typeof beta6.verifier === "object" && beta6.verifier !== null ? (beta6.verifier as Record<string, unknown>) : undefined,
      rejectedLedger: rejectedLedger as Array<Record<string, unknown>>,
      selectedCount,
      chunkCount,
      selectedEvidenceHandoff:
        beta6.selectedEvidenceHandoff === undefined
          ? undefined
          : expectString(beta6.selectedEvidenceHandoff, "beta6.selectedEvidenceHandoff"),
    },
  };
}

async function pollDomainJob(jobId: string, signal?: AbortSignal): Promise<DomainAnswer> {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    const result = await fetch(buildDomainJobResultEndpoint(jobId), { signal });
    if (result.ok) {
      return validateDomainAnswerPayload(await result.json());
    }
    if (result.status !== 425) {
      const status = await fetch(buildDomainJobStatusEndpoint(jobId), { signal });
      if (status.ok) {
        const payload = await status.json();
        throw new Error(payload.error || "Domain job failed");
      }
      throw new Error(await result.text());
    }
    await sleep(Math.min(450 + attempt * 80, 1600));
  }
  throw new Error("Timed out waiting for domain job");
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function validateSource(value: unknown, label: string): DomainSource {
  const source = expectRecord(value, label);
  return {
    id: expectString(source.id, `${label}.id`),
    label: source.label === undefined ? undefined : expectString(source.label, `${label}.label`),
    title: expectPublicText(source.title, `${label}.title`),
    citation: expectPublicText(source.citation, `${label}.citation`),
    authorityBody: expectPublicText(source.authorityBody, `${label}.authorityBody`),
    date: expectPublicText(source.date, `${label}.date`),
    topic: expectPublicText(source.topic, `${label}.topic`),
    type: expectPublicText(source.type, `${label}.type`),
    dataset: expectPublicText(source.dataset, `${label}.dataset`),
    path: expectString(source.path, `${label}.path`),
    url: expectString(source.url, `${label}.url`),
    score: expectNumber(source.score, `${label}.score`),
    verdict: expectString(source.verdict, `${label}.verdict`),
    excerpt: expectPublicText(source.excerpt, `${label}.excerpt`),
  };
}

function validateSection(value: unknown, label: string): DomainAnswerSection {
  const section = expectRecord(value, label);
  return {
    kind: expectString(section.kind, `${label}.kind`),
    title: expectPublicText(section.title, `${label}.title`),
    body: expectPublicText(section.body, `${label}.body`),
    citations: expectArray(section.citations, `${label}.citations`).map((item) => String(item)),
  };
}

function validateCitationMap(value: Record<string, unknown>): Record<string, DomainCitation> {
  const out: Record<string, DomainCitation> = {};
  for (const [key, item] of Object.entries(value)) {
    const label = `citationMap.${key}`;
    const citation = expectRecord(item, label);
    out[key] = {
      sourceId: expectString(citation.sourceId, `${label}.sourceId`),
      citation: expectPublicText(citation.citation, `${label}.citation`),
      title: expectPublicText(citation.title, `${label}.title`),
      authorityBody: expectPublicText(citation.authorityBody, `${label}.authorityBody`),
      dataset: expectPublicText(citation.dataset, `${label}.dataset`),
      type: expectPublicText(citation.type, `${label}.type`),
      score: expectNumber(citation.score, `${label}.score`),
      excerpt: expectPublicText(citation.excerpt, `${label}.excerpt`),
    };
  }
  return out;
}

function validatePassage(value: unknown, label: string): DomainPassage {
  const passage = expectRecord(value, label);
  return {
    label: expectString(passage.label, `${label}.label`),
    sourceId: expectString(passage.sourceId, `${label}.sourceId`),
    citation: expectPublicText(passage.citation, `${label}.citation`),
    title: expectPublicText(passage.title, `${label}.title`),
    authorityBody: expectPublicText(passage.authorityBody, `${label}.authorityBody`),
    topic: expectPublicText(passage.topic, `${label}.topic`),
    type: expectPublicText(passage.type, `${label}.type`),
    dataset: expectPublicText(passage.dataset, `${label}.dataset`),
    score: expectNumber(passage.score, `${label}.score`),
    verdict: expectString(passage.verdict, `${label}.verdict`),
    excerpt: expectPublicText(passage.excerpt, `${label}.excerpt`),
  };
}

function validateDelivery(value: unknown): DomainAnswer["delivery"] {
  const delivery = expectRecord(value, "delivery");
  if (delivery.corpusShippedToClient !== false) {
    throw new Error("domain response must not ship corpus to client");
  }
  const page = expectRecord(delivery.sourcePagination, "delivery.sourcePagination");
  return {
    mode: expectString(delivery.mode, "delivery.mode"),
    corpusShippedToClient: false,
    sourcePagination: {
      offset: expectNumber(page.offset, "delivery.sourcePagination.offset"),
      limit: expectNumber(page.limit, "delivery.sourcePagination.limit"),
      returned: expectNumber(page.returned, "delivery.sourcePagination.returned"),
    },
  };
}

function validateSecurityControls(value: unknown): DomainAnswer["securityControls"] {
  const controls = expectRecord(value, "securityControls");
  const bounds = expectRecord(controls.queryBounds, "securityControls.queryBounds");
  const sqliteModeKey = ["sqlite", "Mode"].join("");
  const sqliteModeLabel = ["securityControls", sqliteModeKey].join(".");
  return {
    sqliteMode: expectString(controls[sqliteModeKey], sqliteModeLabel),
    sqlParameters: expectString(controls.sqlParameters, "securityControls.sqlParameters"),
    pathPolicy: expectString(controls.pathPolicy, "securityControls.pathPolicy"),
    queryBounds: {
      maxChars: expectNumber(bounds.maxChars, "securityControls.queryBounds.maxChars"),
      maxLimit: expectNumber(bounds.maxLimit, "securityControls.queryBounds.maxLimit"),
    },
    timeoutCancel: expectString(controls.timeoutCancel, "securityControls.timeoutCancel"),
    retrievedTextPolicy: expectString(controls.retrievedTextPolicy, "securityControls.retrievedTextPolicy"),
  };
}

function expectRecord(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`invalid ${label}`);
  }
  return value as Record<string, unknown>;
}

function expectArray(value: unknown, label: string): unknown[] {
  if (!Array.isArray(value)) throw new Error(`invalid ${label}`);
  return value;
}

function expectString(value: unknown, label: string): string {
  if (typeof value !== "string") throw new Error(`invalid ${label}`);
  return value;
}

function expectPublicText(value: unknown, label: string): string {
  const text = expectString(value, label);
  if (
    /\[META\]/i.test(text) ||
    /\[PRIMARY TEXT/i.test(text) ||
    /\[(지시|입력|출력|instruction|input|output|boundaries)\]/i.test(text) ||
    /\b(ignore|disregard)\s+previous\s+instructions?\b/i.test(text) ||
    /\b(system|developer)\s+prompt\b/i.test(text) ||
    /直接给出你的疾病诊断/.test(text) ||
    /<\/?[a-z][\s\S]*?>/i.test(text) ||
    text.includes("�")
  ) {
    throw new Error(`unsafe public text: ${label}`);
  }
  return text;
}

function expectNumber(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) throw new Error(`invalid ${label}`);
  return value;
}

function windowOrGlobalSetTimeout(callback: () => void, ms: number): ReturnType<typeof setTimeout> {
  return setTimeout(callback, ms);
}
