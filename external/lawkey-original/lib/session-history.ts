import type { JobResultPayload, JobStatusPayload } from "./api";

export type SessionHistoryItem = {
  id: string;
  title: string;
  meta: string;
  prompt?: string;
  createdAt?: number;
  finishedAt?: number | null;
};

export type SessionSnapshot = {
  jobId: string;
  prompt?: string;
  mode?: "question" | "document";
  selectedPrecedentId?: string;
  samplePath?: string;
  documentPresetId?: string;
  useCustomSamplePath?: boolean;
  questionMessages?: Array<{ role: "user"; text: string }>;
  documentMessages?: Array<{ role: "user" | "assistant"; text: string }>;
};

type ConversationMessage = { role: string; text: string };

export type PendingTurnDraft = {
  id: string;
  mode: "question" | "document";
  text: string;
  sourceJobId?: string;
};

export type DraftState = {
  mode?: "question" | "document";
  prompt?: string;
  submittedPrompt?: string;
  samplePath?: string;
  uploadedSampleLabel?: string;
  documentPresetId?: string;
  useCustomSamplePath?: boolean;
  questionMessages?: Array<{ role: "user"; text: string }>;
  documentMessages?: Array<{ role: "user" | "assistant"; text: string }>;
  pendingTurn?: PendingTurnDraft | null;
};

const TERMINAL_METAS = new Set(["중단됨", "실패"]);
const TERMINAL_JOB_STATES = new Set(["failed", "cancelled", "interrupted"]);
const DEFAULT_SESSION_HISTORY_LIMIT = 50;
const SNAPSHOT_STORAGE_KEY = "lawkey-session-snapshots-v1";
export const VIEWED_SESSION_STORAGE_KEY = "lawkey-viewed-session-v1";
const STATUS_SNAPSHOT_STORAGE_KEY = "lawkey-status-snapshots-v1";
const RESULT_SNAPSHOT_STORAGE_KEY = "lawkey-result-snapshots-v1";
const BROWSER_CLIENT_ID_STORAGE_KEY = "lawkey-browser-client-id-v1";
const BROWSER_DB_NAME = "lawkey-browser-store-v1";
const BROWSER_DB_VERSION = 1;
const STATUS_STORE = "statusSnapshots";
const RESULT_STORE = "resultSnapshots";
const DELETED_IDS_STORAGE_KEY = "lawkey-deleted-session-ids-v1";

// Soft-deleted job ids: kept on the server, hidden client-side from sidebar
// history, list-jobs merges, and direct URL access. The user explicitly asked
// for "delete from list but leave the server data intact and unreachable
// externally" semantics.
export function loadDeletedSessionIds(): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = window.localStorage?.getItem(DELETED_IDS_STORAGE_KEY);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.filter((id) => typeof id === "string" && id.trim()));
  } catch {
    return new Set();
  }
}

export function persistDeletedSessionIds(ids: Set<string>): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage?.setItem(DELETED_IDS_STORAGE_KEY, JSON.stringify(Array.from(ids)));
  } catch {
    /* ignore quota */
  }
}

export function markSessionDeleted(jobId: string): Set<string> {
  const id = String(jobId || "").trim();
  const ids = loadDeletedSessionIds();
  if (id) {
    ids.add(id);
    persistDeletedSessionIds(ids);
  }
  return ids;
}

export function isSessionDeleted(jobId: string): boolean {
  const id = String(jobId || "").trim();
  if (!id) return false;
  return loadDeletedSessionIds().has(id);
}

export function upsertSessionHistory(
  current: SessionHistoryItem[],
  next: SessionHistoryItem,
  limit = DEFAULT_SESSION_HISTORY_LIMIT,
): SessionHistoryItem[] {
  const existingIndex = current.findIndex((item) => item.id === next.id);
  // Preserve the original position when the item already exists. Display order
  // is decided by createdAt at render time (filterVisibleHistory), so simply
  // clicking on a chat must not bubble it to the top of the list.
  if (existingIndex >= 0) {
    const previous = current[existingIndex];
    // Title and createdAt are write-once on first create. Re-renders driven
    // by clicks (where `status` may briefly be stale or null) must NOT
    // overwrite the title or shift the createdAt: that's what made the
    // sidebar visibly reshuffle / retitle every click.
    const merged: SessionHistoryItem = {
      ...previous,
      ...next,
      title: previous.title || next.title,
      prompt: previous.prompt || next.prompt,
      createdAt: previous.createdAt ?? next.createdAt,
      finishedAt: next.finishedAt ?? previous.finishedAt,
    };
    const updated = current.slice();
    updated[existingIndex] = merged;
    return trimSessionHistory(updated, limit);
  }
  // New item: insert at the front so it's immediately visible while the list
  // is later sorted deterministically at render time.
  const updated = [next, ...current];
  return trimSessionHistory(updated, limit);
}

export function upsertContinuationSessionHistory(
  current: SessionHistoryItem[],
  next: SessionHistoryItem,
  sourceJobId: string,
  limit = DEFAULT_SESSION_HISTORY_LIMIT,
): SessionHistoryItem[] {
  const source = String(sourceJobId || "").trim();
  if (!source || source === next.id) {
    return upsertSessionHistory(current, next, limit);
  }
  return upsertSessionHistory(
    current.filter((item) => item.id !== source),
    next,
    limit,
  );
}

function trimSessionHistory(items: SessionHistoryItem[], limit: number): SessionHistoryItem[] {
  if (!Number.isFinite(limit) || limit <= 0) {
    return [];
  }
  if (items.length <= limit) {
    return items;
  }
  const keepIds = new Set(
    items
      .map((item, index) => ({ id: item.id, index, createdAt: Number(item.createdAt ?? 0) }))
      .sort((a, b) => {
        if (b.createdAt !== a.createdAt) {
          return b.createdAt - a.createdAt;
        }
        return a.index - b.index;
      })
      .slice(0, limit)
      .map((item) => item.id),
  );
  return items.filter((item) => keepIds.has(item.id));
}

export function shouldSkipSourceDocumentHistoryUpdate({
  mode,
  activeJobId,
  continuationSourceJobId,
  pendingDocumentSetupSourceJobId,
}: {
  mode: string;
  activeJobId: string;
  continuationSourceJobId?: string;
  pendingDocumentSetupSourceJobId?: string;
}): boolean {
  const active = String(activeJobId || "").trim();
  if (!active || mode !== "document") {
    return false;
  }
  return [continuationSourceJobId, pendingDocumentSetupSourceJobId]
    .map((value) => String(value || "").trim())
    .some((value) => !!value && value === active);
}

function normalizeHistoryMatchText(value: string): string {
  return String(value || "").replace(/\s+/g, " ").trim();
}

export function pruneEmbeddedSourceSessionHistory(
  current: SessionHistoryItem[],
  activeJobId: string,
  documentMessages: ConversationMessage[],
): SessionHistoryItem[] {
  const active = String(activeJobId || "").trim();
  if (!active || !documentMessages.length) {
    return current;
  }
  const embeddedUserMessages = new Set(
    documentMessages
      .filter((message) => message.role === "user")
      .map((message) => normalizeHistoryMatchText(message.text))
      .filter(Boolean),
  );
  if (!embeddedUserMessages.size) {
    return current;
  }
  return current.filter((item) => {
    if (item.id === active) {
      return true;
    }
    const prompt = normalizeHistoryMatchText(item.prompt || "");
    const title = normalizeHistoryMatchText(item.title || "");
    return !embeddedUserMessages.has(prompt) && !embeddedUserMessages.has(title);
  });
}

export function findSessionPrompt(history: SessionHistoryItem[], jobId: string): string {
  const match = history.find((item) => item.id === jobId);
  if (!match) {
    return "";
  }
  return (match.prompt || match.title || "").trim();
}

export function filterVisibleHistory(history: SessionHistoryItem[]): SessionHistoryItem[] {
  return history
    .filter((item) => !TERMINAL_METAS.has((item.meta || "").trim()))
    .slice()
    .sort((a, b) => {
      // Newest first by createdAt so a click on an existing item never moves
      // it to the top. Items missing createdAt fall back to original
      // insertion order via Array.sort stability — that keeps the legacy
      // unsorted-history fixtures (and any pre-existing local snapshots
      // without createdAt) in their pre-sort order.
      const aCreated = Number(a.createdAt ?? 0);
      const bCreated = Number(b.createdAt ?? 0);
      if (bCreated === aCreated) {
        return 0;
      }
      return bCreated - aCreated;
    });
}

export function findLatestVisibleSessionId(history: SessionHistoryItem[]): string {
  return filterVisibleHistory(history)[0]?.id ?? "";
}

export function isRestorableJobState(state: string): boolean {
  return !TERMINAL_JOB_STATES.has((state || "").trim());
}

export function shouldPersistLastSession(activeJobId: string, hydrated: boolean): boolean {
  return hydrated && !!activeJobId.trim();
}

export function loadSessionSnapshots(): Record<string, SessionSnapshot> {
  if (typeof window === "undefined") {
    return {};
  }
  try {
    const raw = window.localStorage.getItem(SNAPSHOT_STORAGE_KEY);
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw) as Record<string, SessionSnapshot>;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

export function saveSessionSnapshot(snapshot: SessionSnapshot): void {
  if (typeof window === "undefined" || !snapshot.jobId.trim()) {
    return;
  }
  try {
    const current = loadSessionSnapshots();
    current[snapshot.jobId] = snapshot;
    window.localStorage.setItem(SNAPSHOT_STORAGE_KEY, JSON.stringify(current));
  } catch {
    // Ignore local storage quota issues.
  }
}

export function loadSessionSnapshot(jobId: string): SessionSnapshot | null {
  if (!jobId.trim()) {
    return null;
  }
  const current = loadSessionSnapshots();
  return current[jobId] ?? null;
}

export function clearSessionSnapshot(jobId: string): void {
  if (typeof window === "undefined" || !jobId.trim()) {
    return;
  }
  try {
    const current = loadSessionSnapshots();
    delete current[jobId];
    window.localStorage.setItem(SNAPSHOT_STORAGE_KEY, JSON.stringify(current));
  } catch {
    // Ignore local storage quota issues.
  }
}

export function normalizeDraftState(raw: unknown): DraftState {
  if (!raw || typeof raw !== "object") {
    return {};
  }
  const row = raw as Record<string, unknown>;
  const normalizedQuestionMessages: Array<{ role: "user"; text: string }> = [];
  if (Array.isArray(row.questionMessages)) {
    for (const item of row.questionMessages) {
      if (!item || typeof item !== "object") {
        continue;
      }
      const payload = item as Record<string, unknown>;
      const role = String(payload.role || "").trim();
      const text = String(payload.text || "").trim();
      if (role === "user" && text) {
        normalizedQuestionMessages.push({ role, text });
      }
    }
  }
  const normalizedDocumentMessages: Array<{ role: "user" | "assistant"; text: string }> = [];
  if (Array.isArray(row.documentMessages)) {
    for (const item of row.documentMessages) {
      if (!item || typeof item !== "object") {
        continue;
      }
      const payload = item as Record<string, unknown>;
      const role = String(payload.role || "").trim();
      const text = String(payload.text || "").trim();
      if ((role === "user" || role === "assistant") && text) {
        normalizedDocumentMessages.push({ role, text });
      }
    }
  }
  const mode = String(row.mode || "").trim();
  let pendingTurn: PendingTurnDraft | null = null;
  if (row.pendingTurn && typeof row.pendingTurn === "object") {
    const pt = row.pendingTurn as Record<string, unknown>;
    const ptMode = String(pt.mode || "").trim();
    const ptText = String(pt.text || "").trim();
    const ptId = String(pt.id || "").trim();
    if ((ptMode === "question" || ptMode === "document") && ptText && ptId) {
      pendingTurn = {
        id: ptId,
        mode: ptMode,
        text: ptText,
        sourceJobId: String(pt.sourceJobId || "") || undefined,
      };
    }
  }
  return {
    mode: mode === "document" ? "document" : mode === "question" ? "question" : undefined,
    prompt: String(row.prompt || ""),
    submittedPrompt: String(row.submittedPrompt || ""),
    samplePath: String(row.samplePath || ""),
    uploadedSampleLabel: String(row.uploadedSampleLabel || ""),
    documentPresetId: String(row.documentPresetId || ""),
    useCustomSamplePath: typeof row.useCustomSamplePath === "boolean" ? row.useCustomSamplePath : undefined,
    questionMessages: normalizedQuestionMessages,
    documentMessages: normalizedDocumentMessages,
    pendingTurn,
  };
}

export function loadViewedSessionId(): string {
  if (typeof window === "undefined") {
    return "";
  }
  try {
    // sessionStorage first so different tabs stay isolated; fall back to
    // localStorage so new-tab/browser-restart still restores the last session.
    return (window.sessionStorage?.getItem(VIEWED_SESSION_STORAGE_KEY) || window.localStorage?.getItem(VIEWED_SESSION_STORAGE_KEY) || "").trim();
  } catch {
    return "";
  }
}

export function saveViewedSessionId(jobId: string): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    if (jobId.trim()) {
      // Write to both so: sessionStorage keeps tabs isolated, and localStorage
      // survives browser restart / new-tab reloads. Readers prefer
      // sessionStorage first.
      window.sessionStorage?.setItem(VIEWED_SESSION_STORAGE_KEY, jobId.trim());
      window.localStorage?.setItem(VIEWED_SESSION_STORAGE_KEY, jobId.trim());
    } else {
      window.sessionStorage?.removeItem(VIEWED_SESSION_STORAGE_KEY);
      window.localStorage?.removeItem(VIEWED_SESSION_STORAGE_KEY);
    }
  } catch {
    // Ignore local storage quota issues.
  }
}

export function getBrowserClientId(): string {
  if (typeof window === "undefined") {
    return "";
  }
  try {
    const existing = window.localStorage?.getItem(BROWSER_CLIENT_ID_STORAGE_KEY)?.trim();
    if (existing) {
      return existing;
    }
    const cryptoLike = window.crypto as Crypto | undefined;
    const randomPart =
      typeof cryptoLike?.randomUUID === "function"
        ? cryptoLike.randomUUID()
        : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
    const next = `lawkey-${randomPart}`;
    window.localStorage?.setItem(BROWSER_CLIENT_ID_STORAGE_KEY, next);
    return next;
  } catch {
    return `lawkey-ephemeral-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  }
}

function loadStoredMap<T>(key: string): Record<string, T> {
  if (typeof window === "undefined") {
    return {};
  }
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw) as Record<string, T>;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function saveStoredMap<T>(key: string, value: Record<string, T>): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Ignore local storage quota issues.
  }
}

let browserDbPromise: Promise<IDBDatabase | null> | null = null;

function openBrowserDb(): Promise<IDBDatabase | null> {
  if (typeof window === "undefined" || typeof window.indexedDB === "undefined") {
    return Promise.resolve(null);
  }
  if (browserDbPromise) {
    return browserDbPromise;
  }
  browserDbPromise = new Promise((resolve) => {
    try {
      const request = window.indexedDB.open(BROWSER_DB_NAME, BROWSER_DB_VERSION);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains(STATUS_STORE)) {
          db.createObjectStore(STATUS_STORE);
        }
        if (!db.objectStoreNames.contains(RESULT_STORE)) {
          db.createObjectStore(RESULT_STORE);
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => resolve(null);
    } catch {
      resolve(null);
    }
  });
  return browserDbPromise;
}

async function browserStorePut<T>(storeName: string, key: string, value: T): Promise<void> {
  const db = await openBrowserDb();
  if (!db || !key.trim()) {
    return;
  }
  await new Promise<void>((resolve) => {
    try {
      const tx = db.transaction(storeName, "readwrite");
      tx.objectStore(storeName).put(value, key);
      tx.oncomplete = () => resolve();
      tx.onerror = () => resolve();
      tx.onabort = () => resolve();
    } catch {
      resolve();
    }
  });
}

async function browserStoreGet<T>(storeName: string, key: string): Promise<T | null> {
  const db = await openBrowserDb();
  if (!db || !key.trim()) {
    return null;
  }
  return new Promise<T | null>((resolve) => {
    try {
      const tx = db.transaction(storeName, "readonly");
      const request = tx.objectStore(storeName).get(key);
      request.onsuccess = () => resolve((request.result as T | undefined) ?? null);
      request.onerror = () => resolve(null);
      tx.onabort = () => resolve(null);
    } catch {
      resolve(null);
    }
  });
}

export function saveStatusSnapshot(jobId: string, status: JobStatusPayload): void {
  if (!jobId.trim()) {
    return;
  }
  const current = loadStoredMap<JobStatusPayload>(STATUS_SNAPSHOT_STORAGE_KEY);
  current[jobId] = status;
  saveStoredMap(STATUS_SNAPSHOT_STORAGE_KEY, current);
}

export async function saveStatusSnapshotAsync(jobId: string, status: JobStatusPayload): Promise<void> {
  saveStatusSnapshot(jobId, status);
  await browserStorePut(STATUS_STORE, jobId, status);
}

export function loadStatusSnapshot(jobId: string): JobStatusPayload | null {
  if (!jobId.trim()) {
    return null;
  }
  const current = loadStoredMap<JobStatusPayload>(STATUS_SNAPSHOT_STORAGE_KEY);
  return current[jobId] ?? null;
}

export async function loadStatusSnapshotAsync(jobId: string): Promise<JobStatusPayload | null> {
  const local = loadStatusSnapshot(jobId);
  if (local) {
    return local;
  }
  return browserStoreGet<JobStatusPayload>(STATUS_STORE, jobId);
}

function compactResult(result: JobResultPayload): JobResultPayload {
  return {
    ...result,
    selectedPrecedents: (result.selectedPrecedents || []).map((precedent) => ({
      ...precedent,
      fullText: "",
    })),
  };
}

export function saveResultSnapshot(jobId: string, result: JobResultPayload): void {
  if (!jobId.trim()) {
    return;
  }
  const current = loadStoredMap<JobResultPayload>(RESULT_SNAPSHOT_STORAGE_KEY);
  current[jobId] = compactResult(result);
  saveStoredMap(RESULT_SNAPSHOT_STORAGE_KEY, current);
}

export async function saveResultSnapshotAsync(jobId: string, result: JobResultPayload): Promise<void> {
  const compact = compactResult(result);
  const current = loadStoredMap<JobResultPayload>(RESULT_SNAPSHOT_STORAGE_KEY);
  current[jobId] = compact;
  saveStoredMap(RESULT_SNAPSHOT_STORAGE_KEY, current);
  await browserStorePut(RESULT_STORE, jobId, compact);
}

export function loadResultSnapshot(jobId: string): JobResultPayload | null {
  if (!jobId.trim()) {
    return null;
  }
  const current = loadStoredMap<JobResultPayload>(RESULT_SNAPSHOT_STORAGE_KEY);
  return current[jobId] ?? null;
}

export async function loadResultSnapshotAsync(jobId: string): Promise<JobResultPayload | null> {
  const local = loadResultSnapshot(jobId);
  if (local) {
    return local;
  }
  return browserStoreGet<JobResultPayload>(RESULT_STORE, jobId);
}
