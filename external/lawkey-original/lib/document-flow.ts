import type { DocumentConversationItem, DocumentPreflightResponse } from "./api";

const COMPLAINT_DOCUMENT_PATTERN = /고\s*소\s*(?:장|작)|고소취지|고소인|피고소인|범죄사실|처벌하여\s*주시/;
const DOCUMENT_TYPE_PATTERN =
  /고\s*소\s*(?:장|작)|고발장|내용증명|변호인\s*의견서|변호인의견서|의견서|준비서면|답변서|항소이유서|탄원서|진정서|계약서|합의서/;
const DOCUMENT_ACTION_PATTERN = /작성|써\s*줘|써줘|만들|초안|문서화|양식|정리해\s*줘|정리해줘|제출|작성해\s*줘|작성해줘/;

export function shouldRouteQuestionToDocument(prompt: string): boolean {
  const text = String(prompt || "").trim();
  if (!text) {
    return false;
  }
  if (/문서화|문서로\s*(?:작성|만들|정리)|초안으로\s*(?:작성|만들)|양식으로\s*(?:작성|만들)/.test(text)) {
    return true;
  }
  return DOCUMENT_TYPE_PATTERN.test(text) && DOCUMENT_ACTION_PATTERN.test(text);
}

export function resolvePromptSubmitMode(inputMode: "question" | "document", prompt: string): "question" | "document" {
  if (inputMode === "question" && shouldRouteQuestionToDocument(prompt)) {
    return "document";
  }
  return inputMode;
}

export function shouldStartDocumentSetup({
  inputMode,
  routedMode,
  documentPresetConfirmed,
  shouldSendAsNewRequest,
}: {
  inputMode: "question" | "document";
  routedMode: "question" | "document";
  documentPresetConfirmed: boolean;
  shouldSendAsNewRequest: boolean;
}): boolean {
  if (routedMode !== "document") {
    return false;
  }
  return inputMode === "question" || shouldSendAsNewRequest || !documentPresetConfirmed;
}

export function buildFallbackDocumentPreflight(prompt: string): DocumentPreflightResponse {
  const isComplaint = inferDocumentPresetIdFromPrompt(prompt, "") === "complaint";
  const questions = isComplaint
    ? [
        "피고소인(상대방)을 어떻게 표시할지, 알고 있는 인적사항이나 관계를 알려주세요.",
        "피고소인이 어떤 말이나 행동을 했는지, 문제된 표현을 가능한 한 그대로 알려주세요.",
        "사건이 발생한 날짜와 대략적인 시각을 알려주세요.",
      ]
    : [
        "문서에서 가장 핵심적으로 주장하거나 요구할 결론을 한 문장으로 적어주세요.",
        "문제된 행위나 처분이 언제 있었는지 알 수 있는 날짜·시각을 적어주세요.",
        "문서의 당사자와 상대방이 누구인지, 관계가 무엇인지 적어주세요.",
      ];
  return {
    ready: false,
    questions,
    retrievalTask: "",
    draftingGoal: "",
    summary: "문서 작성 전에 필요한 사실을 먼저 확인해야 합니다.",
  };
}

export function inferDocumentPresetIdFromPrompt(prompt: string, fallbackPresetId = ""): string {
  const text = String(prompt || "").trim();
  if (COMPLAINT_DOCUMENT_PATTERN.test(text)) {
    return "complaint";
  }
  return String(fallbackPresetId || "").trim();
}

function joinedUserText(conversation: DocumentConversationItem[]): string {
  return conversation
    .filter((item) => item.role === "user")
    .map((item) => item.text.trim())
    .filter(Boolean)
    .join("\n");
}

function renderConversationBlock(item: DocumentConversationItem): string {
  const text = item.text.trim();
  if (!text) {
    return "";
  }
  return `[${item.role === "user" ? "사용자" : "기존 Lawkey 답변"}]\n${text}`;
}

function truncateBlockTail(block: string, limit: number): string {
  if (block.length <= limit) {
    return block;
  }
  if (limit <= 16) {
    return "";
  }
  return `...\n${block.slice(-(limit - 4)).trim()}`.trim();
}

function compactConversationContext(conversation: DocumentConversationItem[], limit = 4000): string {
  const blocks = conversation.slice(-8).map(renderConversationBlock).filter(Boolean);
  const chunks: string[] = [];
  let remaining = limit;

  for (let index = blocks.length - 1; index >= 0; index -= 1) {
    const block = blocks[index];
    const separatorCost = chunks.length ? 2 : 0;
    const cost = block.length + separatorCost;
    if (cost <= remaining) {
      chunks.unshift(block);
      remaining -= cost;
      continue;
    }
    const role = conversation.slice(-8).filter((item) => !!item.text.trim())[index]?.role;
    if (chunks.length && role === "assistant") {
      continue;
    }
    const available = remaining - separatorCost;
    if (available > 120) {
      const truncated = truncateBlockTail(block, available);
      if (truncated) {
        chunks.unshift(truncated);
      }
    }
    break;
  }

  return chunks.join("\n\n").trim();
}

// Fast path: clear instructions from user to stop asking and start drafting.
// This is a safety net; the preflight LLM is also instructed to detect this
// intent more flexibly (see _build_document_preflight_prompt).
const FORCE_DRAFT_PATTERN =
  /그만\s*(?:물어|질문|묻)|질문\s*(?:그만|없|말고|말아|안\s*해)|바로\s*(?:써|작성|만들|초안)|일단\s*(?:써|작성|만들|초안)|그냥\s*(?:써|작성|만들|초안|해)|이제\s*(?:써|작성|만들|초안|충분)|추가\s*질문\s*(?:없|말|그만)|모르겠|모르는\s*건\s*(?:빼|넘어)|더\s*(?:물어보지|묻지|질문|필요)\s*말/;

export function shouldForceDocumentDraft({
  currentPrompt,
  conversation,
}: {
  currentPrompt: string;
  conversation: DocumentConversationItem[];
}): boolean {
  // 1. Explicit user instruction to stop asking
  const text = String(currentPrompt || "").trim();
  if (text && FORCE_DRAFT_PATTERN.test(text)) return true;
  // 2. Already answered 2+ preflight clarification rounds. A clarification
  //    round is identified by the assistant message that starts with
  //    `문서 초안 전에` (the standard preflight question opener) — only
  //    user turns whose immediately-preceding assistant message is such a
  //    clarification request count as preflight answers. Prior question-mode
  //    turns and the initial document request itself are NOT counted, so
  //    we don't skip preflight on the first document submit.
  let preflightAnswerCount = 0;
  for (let i = 0; i < conversation.length; i += 1) {
    const item = conversation[i];
    if (item.role !== "user") continue;
    const prev = conversation[i - 1];
    if (prev && prev.role === "assistant" && /^문서\s*초안\s*전에/.test(String(prev.text || "").trim())) {
      preflightAnswerCount += 1;
    }
  }
  if (preflightAnswerCount >= 2) return true;
  return false;
}

function buildDocumentContext(conversation: DocumentConversationItem[]): string {
  const context = compactConversationContext(conversation);
  if (!context) {
    return "";
  }
  return [
    "[추가질문 문서화 맥락]",
    "아래 기존 질문·답변·추가요청을 모두 반영해 같은 사건의 문서로 작성한다. 문서 유형이 고소장이면 변호인의견서 형식을 쓰지 말고 고소장 형식만 사용한다.",
    context,
  ]
    .filter(Boolean)
    .join("\n\n");
}

export function buildDocumentDraftRequest({
  currentPrompt,
  conversation,
  preflight,
}: {
  currentPrompt: string;
  conversation: DocumentConversationItem[];
  preflight?: DocumentPreflightResponse | null;
}): {
  shouldSubmit: boolean;
  retrievalTask: string;
  draftingGoal: string;
  documentContext: string;
  assistantMessage: string;
} {
  const fallbackGoal = joinedUserText(conversation) || currentPrompt.trim();
  const draftingGoal = (preflight?.draftingGoal || fallbackGoal).trim();
  const retrievalTask = (preflight?.retrievalTask || draftingGoal || fallbackGoal).trim();
  const documentContext = buildDocumentContext(conversation);
  const forceDraft = shouldForceDocumentDraft({ currentPrompt, conversation });
  if (!forceDraft && preflight && !preflight.ready && preflight.questions.length) {
    return {
      shouldSubmit: false,
      retrievalTask,
      draftingGoal: draftingGoal || retrievalTask || currentPrompt.trim(),
      documentContext,
      assistantMessage: ["문서 초안 전에 아래 사실을 먼저 확인해야 합니다.", ...preflight.questions.map((question) => `- ${question.trim()}`)].join("\n"),
    };
  }
  const assistantMessage = preflight?.ready && preflight.summary ? preflight.summary.trim() : "";
  return {
    shouldSubmit: true,
    retrievalTask,
    draftingGoal: draftingGoal || retrievalTask || currentPrompt.trim(),
    documentContext,
    assistantMessage,
  };
}
