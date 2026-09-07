import { describe, expect, it } from "vitest";

import {
  buildPendingLoaderHeadline,
  buildPendingLoaderState,
  buildDocumentConversationItems,
  composeQuestionAnswerMarkdown,
  buildQuestionConversationTurns,
  resolveConversationMode,
  shouldShowDocumentResultCard,
  shouldSubmitComposerKey,
  shouldShowDocumentConfigurator,
  shouldShowSeparateAnalysisSummaryCard,
  shouldShowRunLoader,
  shouldUseStatusForPendingLoader,
} from "../lib/conversation-pending";

describe("conversation pending UI helpers", () => {
  it("keeps the loader visible for a follow-up even while the previous answer is still rendered", () => {
    expect(
      shouldShowRunLoader({
        detailOpen: false,
        hasResult: true,
        hasStatus: false,
        submitting: true,
        hasPendingTurn: true,
      }),
    ).toBe(true);
  });

  it("does not show the normal loader over a completed answer unless a pending turn exists", () => {
    expect(
      shouldShowRunLoader({
        detailOpen: false,
        hasResult: true,
        hasStatus: false,
        submitting: false,
        hasPendingTurn: false,
      }),
    ).toBe(false);
  });

  it("uses a send-stage headline instead of stale precedent ticker text while a question is pending", () => {
    expect(buildPendingLoaderHeadline("question", "이전 판례 헤드라인")).toBe("질문을 보내는 중");
  });

  it("uses a document-stage headline while a document turn is pending", () => {
    expect(buildPendingLoaderHeadline("document", "이전 판례 헤드라인")).toBe("문서 초안을 준비하는 중");
  });

  it("uses a real start-stage state for pending sends before server status exists", () => {
    expect(buildPendingLoaderState("", true)).toBe("generating_keywords");
    expect(buildPendingLoaderState("analyzing_chunks", true)).toBe("analyzing_chunks");
  });

  it("does not reuse a completed previous job state while a new turn is pending", () => {
    expect(buildPendingLoaderState("completed", true)).toBe("generating_keywords");
  });

  it("hides a stale document result card while a document turn is pending", () => {
    expect(
      shouldShowDocumentResultCard({
        conversationMode: "document",
        detailOpen: false,
        hasAnswerMarkdown: true,
        hasPendingTurn: true,
        resultMode: "document",
      }),
    ).toBe(false);
    expect(
      shouldShowDocumentResultCard({
        conversationMode: "document",
        detailOpen: false,
        hasAnswerMarkdown: true,
        hasPendingTurn: false,
        resultMode: "document",
      }),
    ).toBe(true);
  });

  it("does not render a previous question result as a document result card", () => {
    expect(
      shouldShowDocumentResultCard({
        conversationMode: "document",
        detailOpen: false,
        hasAnswerMarkdown: true,
        hasPendingTurn: false,
        resultMode: "question",
      }),
    ).toBe(false);
  });

  it("does not feed a completed previous job status into a pending loader", () => {
    expect(shouldUseStatusForPendingLoader("completed", true)).toBe(false);
    expect(shouldUseStatusForPendingLoader("analyzing_chunks", true)).toBe(true);
    expect(shouldUseStatusForPendingLoader("completed", false)).toBe(true);
  });

  it("does not open the document configurator just because document mode is selected", () => {
    expect(shouldShowDocumentConfigurator({ mode: "document", documentThreadStarted: false })).toBe(false);
  });

  it("renders the summary card whenever there is plan or claim data, regardless of inline markdown summary", () => {
    // 사용자 요구로 카드는 mode 무관하게 항상 노출되도록 변경됨.
    expect(
      shouldShowSeparateAnalysisSummaryCard({
        answerMarkdown: "### 가장 같은 사실관계 판례\n- A\n\n---\n\n### 가장 가능성 높은 결론\nB",
        hasAnswerPlan: true,
        hasClaims: true,
      }),
    ).toBe(true);
    expect(
      shouldShowSeparateAnalysisSummaryCard({
        answerMarkdown: "## 종합 판단\n본문만 있음",
        hasAnswerPlan: true,
        hasClaims: false,
      }),
    ).toBe(true);
    expect(
      shouldShowSeparateAnalysisSummaryCard({
        answerMarkdown: "본문 없음",
        hasAnswerPlan: false,
        hasClaims: false,
      }),
    ).toBe(false);
  });

  it("places follow-up user messages after the existing answer and before the pending loader", () => {
    const turns = buildQuestionConversationTurns({
      submittedPrompt: "처음 질문",
      questionMessages: [
        { role: "user", text: "처음 질문" },
        { role: "user", text: "추가 질문" },
      ],
      answerMarkdown: "## 종합 판단\n기존 답변",
      hasPendingTurn: true,
    });

    expect(turns.map((turn) => turn.type)).toEqual(["user", "assistant", "user", "loader"]);
    expect(turns.map((turn) => ("text" in turn ? turn.text : ""))).toEqual([
      "처음 질문",
      "## 종합 판단\n기존 답변",
      "추가 질문",
      "",
    ]);
  });

  it("interleaves appended follow-up answers with the matching user turns", () => {
    const turns = buildQuestionConversationTurns({
      submittedPrompt: "처음 질문",
      questionMessages: [
        { role: "user", text: "처음 질문" },
        { role: "user", text: "추가 질문" },
      ],
      answerMarkdown: "## 종합 판단\n기존 답변\n\n---\n\n## 추가 답변\n이어지는 답변",
      hasPendingTurn: false,
    });

    expect(turns.map((turn) => turn.type)).toEqual(["user", "assistant", "user", "assistant"]);
    expect(turns[2]?.type === "user" ? turns[2].text : "").toBe("추가 질문");
    expect(turns[3]?.type === "assistant" ? turns[3].text : "").toContain("이어지는 답변");
  });

  it("preserves the previous assistant answer while a follow-up runs as a new async job", () => {
    const carried = composeQuestionAnswerMarkdown("## 종합 판단\n기존 답변", "");
    const pendingTurns = buildQuestionConversationTurns({
      submittedPrompt: "처음 질문",
      questionMessages: [
        { role: "user", text: "처음 질문" },
        { role: "user", text: "추가 질문" },
      ],
      answerMarkdown: carried,
      hasPendingTurn: true,
    });

    expect(pendingTurns.map((turn) => turn.type)).toEqual(["user", "assistant", "user", "loader"]);
    expect(pendingTurns[1]?.type === "assistant" ? pendingTurns[1].text : "").toContain("기존 답변");

    const completed = composeQuestionAnswerMarkdown("## 종합 판단\n기존 답변", "## 추가 답변\n새 job 답변");
    const completedTurns = buildQuestionConversationTurns({
      submittedPrompt: "처음 질문",
      questionMessages: [
        { role: "user", text: "처음 질문" },
        { role: "user", text: "추가 질문" },
      ],
      answerMarkdown: completed,
      hasPendingTurn: false,
    });

    expect(completedTurns.map((turn) => turn.type)).toEqual(["user", "assistant", "user", "assistant"]);
    expect(completedTurns[3]?.type === "assistant" ? completedTurns[3].text : "").toContain("새 job 답변");
  });

  it("keeps an existing question result rendered as question even if the next send mode is document", () => {
    expect(resolveConversationMode({ inputMode: "document", resultMode: "question", statusMode: "" })).toBe("question");
    expect(resolveConversationMode({ inputMode: "document", resultMode: "", statusMode: "question" })).toBe("question");
    expect(resolveConversationMode({ inputMode: "document", resultMode: "", statusMode: "" })).toBe("document");
  });

  it("keeps a started document clarification thread visible over a previous question result", () => {
    expect(resolveConversationMode({ inputMode: "document", resultMode: "question", statusMode: "question", hasDocumentMessages: true })).toBe("document");
  });

  it("renders a pending document send as document even while the previous result was a question", () => {
    expect(resolveConversationMode({ inputMode: "document", resultMode: "question", statusMode: "question", pendingMode: "document" })).toBe("document");
  });

  it("seeds document continuation with the previous chat before appending the new document request", () => {
    const messages = buildDocumentConversationItems({
      documentMessages: [],
      submittedPrompt: "처음 질문",
      questionMessages: [{ role: "user", text: "처음 질문" }],
      answerMarkdown: "## 종합 판단\n기존 답변",
      nextPrompt: "고소장 작성해줘",
    });

    expect(messages).toEqual([
      { role: "user", text: "처음 질문" },
      { role: "assistant", text: "## 종합 판단\n기존 답변" },
      { role: "user", text: "고소장 작성해줘" },
    ]);
  });

  it("uses the source job prompt when restored question state lost local question messages", () => {
    const messages = buildDocumentConversationItems({
      documentMessages: [],
      submittedPrompt: "",
      sourcePrompt: "경찰, 국가에 대한 회의감 표출이 죄가 되는지 질문",
      questionMessages: [],
      answerMarkdown: "## 종합 판단\n발언 대상과 구체적 사실 여부가 핵심입니다.",
      nextPrompt: "그럼 이 사람을 고소하는 고소장 작성해줘",
    });

    expect(messages).toEqual([
      { role: "user", text: "경찰, 국가에 대한 회의감 표출이 죄가 되는지 질문" },
      { role: "assistant", text: "## 종합 판단\n발언 대상과 구체적 사실 여부가 핵심입니다." },
      { role: "user", text: "그럼 이 사람을 고소하는 고소장 작성해줘" },
    ]);
  });

  it("carries the previous document result forward before a document follow-up", () => {
    const messages = buildDocumentConversationItems({
      documentMessages: [{ role: "user", text: "고소장 작성해줘" }],
      submittedPrompt: "",
      questionMessages: [],
      answerMarkdown: "고    소    장\n\n본문",
      nextPrompt: "피해 일시도 반영해줘",
    });

    expect(messages).toEqual([
      { role: "user", text: "고소장 작성해줘" },
      { role: "assistant", text: "고    소    장\n\n본문" },
      { role: "user", text: "피해 일시도 반영해줘" },
    ]);
  });

  it("submits on Enter but keeps Shift+Enter and IME composition for newlines/composition", () => {
    expect(shouldSubmitComposerKey({ key: "Enter", shiftKey: false, isComposing: false })).toBe(true);
    expect(shouldSubmitComposerKey({ key: "Enter", shiftKey: true, isComposing: false })).toBe(false);
    expect(shouldSubmitComposerKey({ key: "Enter", shiftKey: false, isComposing: true })).toBe(false);
    expect(shouldSubmitComposerKey({ key: "a", shiftKey: false, isComposing: false })).toBe(false);
  });
});
