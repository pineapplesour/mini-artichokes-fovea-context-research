import { describe, expect, it } from "vitest";

import {
  filterVisibleHistory,
  findLatestVisibleSessionId,
  findSessionPrompt,
  getBrowserClientId,
  isRestorableJobState,
  loadResultSnapshot,
  loadStatusSnapshot,
  normalizeDraftState,
  pruneEmbeddedSourceSessionHistory,
  saveResultSnapshot,
  saveStatusSnapshot,
  shouldPersistLastSession,
  shouldSkipSourceDocumentHistoryUpdate,
  upsertContinuationSessionHistory,
  upsertSessionHistory,
  type SessionHistoryItem,
} from "../lib/session-history";

describe("session history helpers", () => {
  it("updates an existing history row in place", () => {
    const current: SessionHistoryItem[] = [
      { id: "job-1", title: "첫 요청", meta: "대기 중", prompt: "원래 질문" },
      { id: "job-2", title: "둘째 요청", meta: "완료", prompt: "다른 질문" },
    ];

    const next = upsertSessionHistory(current, {
      id: "job-1",
      title: "첫 요청",
      meta: "완료",
      prompt: "원래 질문",
    });

    expect(next).toEqual([
      { id: "job-1", title: "첫 요청", meta: "완료", prompt: "원래 질문" },
      { id: "job-2", title: "둘째 요청", meta: "완료", prompt: "다른 질문" },
    ]);
  });

  it("prepends new rows and trims to the limit", () => {
    const current: SessionHistoryItem[] = [
      { id: "job-1", title: "하나", meta: "완료" },
      { id: "job-2", title: "둘", meta: "완료" },
    ];

    const next = upsertSessionHistory(current, { id: "job-3", title: "셋", meta: "완료" }, 2);

    expect(next).toEqual([
      { id: "job-3", title: "셋", meta: "완료" },
      { id: "job-1", title: "하나", meta: "완료" },
    ]);
  });

  it("keeps more than eight conversations by default", () => {
    const current: SessionHistoryItem[] = Array.from({ length: 8 }, (_, index) => ({
      id: `job-${index + 1}`,
      title: `요청 ${index + 1}`,
      meta: "완료",
      createdAt: index + 1,
    }));

    const next = upsertSessionHistory(current, {
      id: "job-9",
      title: "요청 9",
      meta: "완료",
      createdAt: 9,
    });

    expect(next).toHaveLength(9);
    expect(next.map((item) => item.id)).toContain("job-1");
    expect(next[0].id).toBe("job-9");
  });

  it("trims by newest createdAt instead of stale storage order", () => {
    const current: SessionHistoryItem[] = [
      { id: "job-old", title: "오래된 요청", meta: "진행 중", createdAt: 1 },
      { id: "job-newer", title: "새 요청", meta: "완료", createdAt: 20 },
      { id: "job-newest", title: "최신 요청", meta: "완료", createdAt: 30 },
    ];

    const next = upsertSessionHistory(
      current,
      { id: "job-old", title: "오래된 요청", meta: "완료", createdAt: 1 },
      2,
    );

    expect(next.map((item) => item.id)).toEqual(["job-newer", "job-newest"]);
  });

  it("replaces the source history row when a continuation starts a new job", () => {
    const current: SessionHistoryItem[] = [
      { id: "job-source", title: "카카오톡 단체방 모욕죄", meta: "완료", prompt: "처음 질문" },
      { id: "job-other", title: "다른 질문", meta: "완료", prompt: "다른 질문" },
    ];

    const next = upsertContinuationSessionHistory(
      current,
      {
        id: "job-document",
        title: "모욕죄 고소장 작성",
        meta: "진행 중",
        prompt: "모욕죄 고소장 작성",
      },
      "job-source",
    );

    expect(next.map((item) => item.id)).toEqual(["job-document", "job-other"]);
    expect(next.find((item) => item.id === "job-source")).toBeUndefined();
  });

  it("does not rewrite the source row while document setup still uses the source job id", () => {
    expect(
      shouldSkipSourceDocumentHistoryUpdate({
        mode: "document",
        activeJobId: "job-source",
        pendingDocumentSetupSourceJobId: "job-source",
      }),
    ).toBe(true);
    expect(
      shouldSkipSourceDocumentHistoryUpdate({
        mode: "document",
        activeJobId: "job-source",
        continuationSourceJobId: "job-source",
      }),
    ).toBe(true);
    expect(
      shouldSkipSourceDocumentHistoryUpdate({
        mode: "document",
        activeJobId: "job-document",
        continuationSourceJobId: "job-source",
      }),
    ).toBe(false);
  });

  it("prunes source rows already embedded in a document thread", () => {
    const current: SessionHistoryItem[] = [
      { id: "job-document", title: "모욕죄 고소장", meta: "완료", prompt: "모욕죄 고소장" },
      {
        id: "job-source",
        title: "카카오톡 단체방에서 모욕죄가 성립하려면 어떤 요건을 봐야해?",
        meta: "완료",
        prompt: "카카오톡 단체방에서 모욕죄가 성립하려면 어떤 요건을 봐야해?",
      },
      { id: "job-other", title: "다른 질문", meta: "완료", prompt: "다른 질문" },
    ];

    const next = pruneEmbeddedSourceSessionHistory(current, "job-document", [
      { role: "user", text: "카카오톡 단체방에서 모욕죄가 성립하려면 어떤 요건을 봐야해?" },
      { role: "assistant", text: "공연성, 특정성, 모욕성을 봐야 합니다." },
      { role: "user", text: "그거에 대한 고소장 작성해줘" },
    ]);

    expect(next.map((item) => item.id)).toEqual(["job-document", "job-other"]);
  });

  it("prefers the stored full prompt over the truncated title", () => {
    const history: SessionHistoryItem[] = [
      { id: "job-1", title: "잘린 제목…", meta: "완료", prompt: "실제 보낸 전체 질문" },
    ];

    expect(findSessionPrompt(history, "job-1")).toBe("실제 보낸 전체 질문");
  });

  it("filters interrupted and failed sessions from the visible sidebar history", () => {
    const history: SessionHistoryItem[] = [
      { id: "job-1", title: "첫 요청", meta: "진행 중" },
      { id: "job-2", title: "둘째 요청", meta: "중단됨" },
      { id: "job-3", title: "셋째 요청", meta: "실패" },
      { id: "job-4", title: "넷째 요청", meta: "완료" },
    ];

    expect(filterVisibleHistory(history).map((item) => item.id)).toEqual(["job-1", "job-4"]);
  });

  it("does not clear the last session key before hydration completes", () => {
    expect(shouldPersistLastSession("", false)).toBe(false);
    expect(shouldPersistLastSession("job-1", false)).toBe(false);
    expect(shouldPersistLastSession("job-1", true)).toBe(true);
  });

  it("does not auto-restore interrupted jobs", () => {
    expect(isRestorableJobState("completed")).toBe(true);
    expect(isRestorableJobState("analyzing_chunks")).toBe(true);
    expect(isRestorableJobState("failed")).toBe(false);
    expect(isRestorableJobState("interrupted")).toBe(false);
  });

  it("finds the latest visible session id without returning interrupted rows", () => {
    const history: SessionHistoryItem[] = [
      { id: "job-3", title: "셋째", meta: "중단됨" },
      { id: "job-2", title: "둘째", meta: "완료" },
      { id: "job-1", title: "첫째", meta: "진행 중" },
    ];

    expect(findLatestVisibleSessionId(history)).toBe("job-2");
  });

  it("stores compact status and result snapshots for local restore", () => {
    const store = new Map<string, string>();
    const originalWindow = (globalThis as Record<string, unknown>).window;
    (globalThis as Record<string, unknown>).window = {
      localStorage: {
        getItem: (key: string) => store.get(key) ?? null,
        setItem: (key: string, value: string) => {
          store.set(key, value);
        },
        removeItem: (key: string) => {
          store.delete(key);
        },
      },
    };
    saveStatusSnapshot("job-1", {
      jobId: "job-1",
      mode: "question",
      phase: "done",
      state: "completed",
      selectedPrecedentCount: 2,
      completedChunks: 2,
      totalChunks: 2,
      workerCount: 10,
      elapsedSeconds: 20,
      etaSeconds: 0,
      currentCaseNumber: "",
      currentExcerpt: "",
      scheduler: {
        keyCount: 10,
        coolingKeys: 0,
        inflight: 0,
        nextReadyInMs: 0,
        minGapMs: 2000,
        maxInflightPerKey: 1,
        rpmLimit: 20,
        tpmLimit: 100000,
        globalMaxInflight: 10,
      },
      error: "",
      createdAt: 1,
      finishedAt: 2,
    });
    saveResultSnapshot("job-1", {
      jobId: "job-1",
      mode: "question",
      answerMarkdown: "# 답변",
      selectedPrecedents: [
        {
          precedentId: "file-1",
          caseNumber: "2020구합12259",
          title: "징계처분취소",
          court: "서울행정법원",
          decisionDate: "2021-06-17",
          sourcePath: "/tmp/a.txt",
          relativePath: "a.txt",
          fullText: "매우 긴 원문",
          excerpt: "발췌",
        },
      ],
      claims: [],
      usedPrecedentIds: [],
      summary: {},
      outputPaths: {
        runDir: "/tmp/run",
        variantDir: "/tmp/run/question_selected_manual",
        answerPath: "/tmp/run/final_answer.md",
        markdownPath: "",
        markdownUrl: "",
        htmlPath: "",
        htmlUrl: "",
        hwpxPath: "",
        hwpxUrl: "",
        pdfPath: "",
        pdfUrl: "",
        previewImagePaths: [],
        previewImageUrls: [],
      },
    });

    expect(loadStatusSnapshot("job-1")?.state).toBe("completed");
    expect(loadResultSnapshot("job-1")?.selectedPrecedents[0]?.fullText).toBe("");
    (globalThis as Record<string, unknown>).window = originalWindow;
  });

  it("normalizes persisted draft state including submitted prompt and document chat", () => {
    const normalized = normalizeDraftState({
      mode: "document",
      prompt: "",
      submittedPrompt: "기숙사 벌점 처분 의견서 작성",
      questionMessages: [
        { role: "user", text: "처음 질문" },
        { role: "user", text: "추가 질문" },
        { role: "assistant", text: "ignored" },
      ],
      samplePath: "/tmp/sample.md",
      uploadedSampleLabel: "sample.md",
      documentPresetId: "complaint",
      useCustomSamplePath: true,
      documentMessages: [
        { role: "user", text: "고소장 형식으로" },
        { role: "assistant", text: "피해 일시가 더 필요합니다." },
        { role: "system", text: "ignored" },
      ],
    });

    expect(normalized.mode).toBe("document");
    expect(normalized.submittedPrompt).toBe("기숙사 벌점 처분 의견서 작성");
    expect(normalized.questionMessages).toEqual([
      { role: "user", text: "처음 질문" },
      { role: "user", text: "추가 질문" },
    ]);
    expect(normalized.documentMessages).toEqual([
      { role: "user", text: "고소장 형식으로" },
      { role: "assistant", text: "피해 일시가 더 필요합니다." },
    ]);
  });

  it("creates and reuses a browser client id in local storage", () => {
    const store = new Map<string, string>();
    const originalWindow = (globalThis as Record<string, unknown>).window;
    (globalThis as Record<string, unknown>).window = {
      crypto: { randomUUID: () => "client-uuid" },
      localStorage: {
        getItem: (key: string) => store.get(key) ?? null,
        setItem: (key: string, value: string) => {
          store.set(key, value);
        },
        removeItem: (key: string) => {
          store.delete(key);
        },
      },
    };

    const first = getBrowserClientId();
    const second = getBrowserClientId();

    expect(first).toBe("lawkey-client-uuid");
    expect(second).toBe(first);
    (globalThis as Record<string, unknown>).window = originalWindow;
  });
});
