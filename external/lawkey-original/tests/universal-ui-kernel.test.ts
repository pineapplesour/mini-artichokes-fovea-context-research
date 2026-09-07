import { describe, expect, it } from "vitest";

import { createLawkeyUniversalKernel, lawkeyUniversalKernel } from "../lib/universal-ui-kernel";
import type { JobResultPayload, JobStatusPayload } from "../lib/api";

const emptyScheduler: JobStatusPayload["scheduler"] = {
  keyCount: 0,
  coolingKeys: 0,
  inflight: 0,
  nextReadyInMs: 0,
  minGapMs: 0,
  maxInflightPerKey: 0,
  rpmLimit: 0,
  tpmLimit: 0,
  globalMaxInflight: 0,
};

const emptyOutputPaths: JobResultPayload["outputPaths"] = {
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
};

describe("lawkey universal UI kernel adapter", () => {
  it("exposes the common job, progress, cancel, result, and source-detail operations", () => {
    for (const key of [
      "listDocumentPresets",
      "createJob",
      "getJobStatus",
      "getJobResult",
      "cancelJob",
      "followUpJob",
      "getPrecedentDetail",
      "sanitizeJobResultPayload",
      "buildHeadlineFrames",
      "getInitialPrecedentId",
    ] as const) {
      expect(typeof lawkeyUniversalKernel[key]).toBe("function");
    }
  });

  it("allows Lawkey to keep its current UI while swapping transport behind the kernel boundary", async () => {
    const calls: string[] = [];
    const kernel = createLawkeyUniversalKernel({
      createJob: async (payload) => {
        calls.push(`create:${payload.mode}:${payload.userTask}`);
        return { jobId: "job-kernel", statusUrl: "/api/jobs/job-kernel", resultUrl: "/api/jobs/job-kernel/result" };
      },
      getJobStatus: async (jobId) => {
        calls.push(`status:${jobId}`);
        return {
          jobId,
          mode: "question",
          phase: "selection",
          state: "completed",
          selectedPrecedentCount: 1,
          completedChunks: 1,
          totalChunks: 1,
          workerCount: 1,
          elapsedSeconds: 1,
          etaSeconds: 0,
          currentCaseNumber: "",
          currentExcerpt: "",
          scheduler: emptyScheduler,
          error: "",
          createdAt: 0,
          finishedAt: 1,
        };
      },
      getJobResult: async (jobId) => {
        calls.push(`result:${jobId}`);
        return {
          jobId,
          mode: "question",
          answerMarkdown: "## 종합 판단\n답변",
          selectedPrecedents: [],
          claims: [],
          usedPrecedentIds: [],
          summary: {},
          outputPaths: emptyOutputPaths,
        };
      },
    });

    const created = await kernel.createJob({ mode: "question", userTask: "모욕죄 공연성" });
    const status = await kernel.getJobStatus(created.jobId);
    const result = await kernel.getJobResult(created.jobId);

    expect(created.jobId).toBe("job-kernel");
    expect(status.state).toBe("completed");
    expect(result.answerMarkdown).toContain("답변");
    expect(calls).toEqual(["create:question:모욕죄 공연성", "status:job-kernel", "result:job-kernel"]);
  });
});
