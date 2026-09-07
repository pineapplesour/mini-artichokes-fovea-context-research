import type { DocumentConversationItem, JobMode } from "./api";

export type PendingTurn = {
  id: string;
  mode: JobMode;
  text: string;
  sourceJobId?: string;
};

export type QuestionConversationTurn =
  | { type: "user"; text: string }
  | { type: "assistant"; text: string }
  | { type: "loader" };

export function shouldShowRunLoader({
  detailOpen,
  hasResult,
  hasStatus,
  submitting,
  hasPendingTurn,
}: {
  detailOpen: boolean;
  hasResult: boolean;
  hasStatus: boolean;
  submitting: boolean;
  hasPendingTurn: boolean;
}): boolean {
  if (detailOpen) {
    return false;
  }
  if (hasPendingTurn) {
    return true;
  }
  return !hasResult && (hasStatus || submitting);
}

export function buildPendingLoaderHeadline(mode: JobMode, fallback: string): string {
  if (mode === "document") {
    return "문서 초안을 준비하는 중";
  }
  if (mode === "question") {
    return "질문을 보내는 중";
  }
  return (fallback || "").trim();
}

export function buildPendingLoaderState(statusState: string | undefined, hasPendingTurn: boolean): string {
  const state = String(statusState || "").trim();
  if (hasPendingTurn && state === "completed") {
    return "generating_keywords";
  }
  if (state) {
    return state;
  }
  return hasPendingTurn ? "generating_keywords" : "";
}

export function shouldShowDocumentResultCard({
  conversationMode,
  detailOpen,
  hasAnswerMarkdown,
  hasPendingTurn,
  resultMode,
}: {
  conversationMode: JobMode;
  detailOpen: boolean;
  hasAnswerMarkdown: boolean;
  hasPendingTurn: boolean;
  resultMode?: string;
}): boolean {
  const resolvedResultMode = String(resultMode || "").trim();
  return conversationMode === "document" && resolvedResultMode !== "question" && !detailOpen && !hasPendingTurn && hasAnswerMarkdown;
}

export function shouldUseStatusForPendingLoader(statusState: string | undefined, hasPendingTurn: boolean): boolean {
  return !(hasPendingTurn && String(statusState || "").trim() === "completed");
}

export function shouldShowDocumentConfigurator({
  mode,
  documentThreadStarted,
}: {
  mode: JobMode;
  documentThreadStarted: boolean;
}): boolean {
  void mode;
  void documentThreadStarted;
  return false;
}

export function shouldShowSeparateAnalysisSummaryCard({
  hasAnswerPlan,
  hasClaims,
}: {
  answerMarkdown?: string;
  hasAnswerPlan: boolean;
  hasClaims: boolean;
}): boolean {
  // 사용자 요구: "최상단 요약" 카드는 모드(fast/beta-4/5/6)에 무관하게
  // 항상 답변 위에 노출되어야 한다. 본문 markdown에 동등한 헤더가
  // 들어 있더라도 카드는 별도로 그대로 보여 준다 — 두 표현이 시각적으로
  // 보완 관계이지 중복으로 받아들여지지 않게 디자인했다.
  if (!hasAnswerPlan && !hasClaims) {
    return false;
  }
  return true;
}

export function resolveConversationMode({
  inputMode,
  pendingMode,
  statusMode,
  resultMode,
  hasDocumentMessages,
}: {
  inputMode: JobMode;
  pendingMode?: JobMode;
  statusMode?: string;
  resultMode?: string;
  hasDocumentMessages?: boolean;
}): JobMode {
  if (pendingMode === "question" || pendingMode === "document") {
    return pendingMode;
  }
  if (inputMode === "document" && hasDocumentMessages) {
    return "document";
  }
  const resolvedResultMode = String(resultMode || "").trim();
  if (resolvedResultMode === "question" || resolvedResultMode === "document") {
    return resolvedResultMode;
  }
  const resolvedStatusMode = String(statusMode || "").trim();
  if (resolvedStatusMode === "question" || resolvedStatusMode === "document") {
    return resolvedStatusMode;
  }
  return inputMode;
}

function normalizeDocumentMessages(messages: DocumentConversationItem[]): DocumentConversationItem[] {
  return messages
    .map((message) => ({ role: message.role, text: message.text.trim() }))
    .filter((message): message is DocumentConversationItem => (message.role === "user" || message.role === "assistant") && !!message.text);
}

export function buildDocumentConversationItems({
  documentMessages,
  submittedPrompt,
  sourcePrompt,
  questionMessages,
  answerMarkdown,
  nextPrompt,
}: {
  documentMessages: DocumentConversationItem[];
  submittedPrompt: string;
  sourcePrompt?: string;
  questionMessages: Array<{ role: "user"; text: string }>;
  answerMarkdown?: string;
  nextPrompt: string;
}): DocumentConversationItem[] {
  const nextText = nextPrompt.trim();
  const answerText = String(answerMarkdown || "").trim();
  const base = normalizeDocumentMessages(documentMessages);
  if (!base.length) {
    for (const turn of buildQuestionConversationTurns({
      submittedPrompt,
      sourcePrompt,
      questionMessages,
      answerMarkdown: answerText,
      hasPendingTurn: false,
    })) {
      if (turn.type === "loader") {
        continue;
      }
      base.push({ role: turn.type, text: turn.text });
    }
  } else if (answerText && !base.some((message) => message.role === "assistant" && message.text === answerText)) {
    base.push({ role: "assistant", text: answerText });
  }
  if (nextText) {
    base.push({ role: "user", text: nextText });
  }
  return base;
}

export function shouldSubmitComposerKey({
  key,
  shiftKey,
  isComposing,
}: {
  key?: string;
  shiftKey?: boolean;
  isComposing?: boolean;
}): boolean {
  return key === "Enter" && !shiftKey && !isComposing;
}

function normalizeUserTexts({
  submittedPrompt,
  sourcePrompt,
  questionMessages,
}: {
  submittedPrompt: string;
  sourcePrompt?: string;
  questionMessages: Array<{ role: "user"; text: string }>;
}): string[] {
  const messages = questionMessages
    .filter((message) => message.role === "user")
    .map((message) => message.text.trim())
    .filter(Boolean);
  if (messages.length) {
    return messages;
  }
  const fallback = submittedPrompt.trim() || String(sourcePrompt || "").trim();
  return fallback ? [fallback] : [];
}

function splitAssistantMarkdown(answerMarkdown: string): string[] {
  const markdown = String(answerMarkdown || "").trim();
  if (!markdown) {
    return [];
  }
  return markdown
    .split(/\n{2}---\n{2}(?=##\s*(?:추가|이어서)\s*답변)/g)
    .map((part) => part.trim())
    .filter(Boolean);
}

export function composeQuestionAnswerMarkdown(previousMarkdown: string, currentMarkdown: string): string {
  const previous = String(previousMarkdown || "").trim();
  const current = String(currentMarkdown || "").trim();
  if (!previous) {
    return current;
  }
  if (!current) {
    return previous;
  }
  const currentWithContinuationHeading = /^##\s*(?:추가|이어서)\s*답변/.test(current)
    ? current
    : `## 추가 답변\n${current}`;
  return [previous, "---", currentWithContinuationHeading].join("\n\n");
}

export function buildQuestionConversationTurns({
  submittedPrompt,
  sourcePrompt,
  questionMessages,
  answerMarkdown,
  hasPendingTurn,
}: {
  submittedPrompt: string;
  sourcePrompt?: string;
  questionMessages: Array<{ role: "user"; text: string }>;
  answerMarkdown?: string;
  hasPendingTurn: boolean;
}): QuestionConversationTurn[] {
  const users = normalizeUserTexts({ submittedPrompt, sourcePrompt, questionMessages });
  const assistants = splitAssistantMarkdown(answerMarkdown || "");
  const turns: QuestionConversationTurn[] = [];
  const count = Math.max(users.length, assistants.length);
  for (let index = 0; index < count; index += 1) {
    if (users[index]) {
      turns.push({ type: "user", text: users[index] });
    }
    if (assistants[index]) {
      turns.push({ type: "assistant", text: assistants[index] });
    }
  }
  if (hasPendingTurn) {
    turns.push({ type: "loader" });
  }
  return turns;
}
