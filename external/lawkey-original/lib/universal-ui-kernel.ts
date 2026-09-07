import {
  buildHeadlineFrames,
  cancelJob,
  createJob,
  followUpJob,
  getInitialPrecedentId,
  getJobResult,
  getJobStatus,
  getPrecedentDetail,
  listDocumentPresets,
  sanitizeJobResultPayload,
  type FollowUpJobResponse,
  type JobResultPayload,
  type JobStatusPayload,
  type PrecedentDetailPayload,
} from "./api";

export type LawkeyKernelCreateJobPayload = Parameters<typeof createJob>[0];
export type LawkeyKernelFollowUpPayload = Parameters<typeof followUpJob>[1];

export type LawkeyUniversalKernel = {
  listDocumentPresets: typeof listDocumentPresets;
  createJob: typeof createJob;
  getJobStatus: typeof getJobStatus;
  getJobResult: typeof getJobResult;
  cancelJob: typeof cancelJob;
  followUpJob: typeof followUpJob;
  getPrecedentDetail: typeof getPrecedentDetail;
  sanitizeJobResultPayload: typeof sanitizeJobResultPayload;
  buildHeadlineFrames: typeof buildHeadlineFrames;
  getInitialPrecedentId: typeof getInitialPrecedentId;
};

export const lawkeyUniversalKernel: LawkeyUniversalKernel = {
  listDocumentPresets,
  createJob,
  getJobStatus,
  getJobResult,
  cancelJob,
  followUpJob,
  getPrecedentDetail,
  sanitizeJobResultPayload,
  buildHeadlineFrames,
  getInitialPrecedentId,
};

export function createLawkeyUniversalKernel(
  overrides: Partial<LawkeyUniversalKernel> = {},
): LawkeyUniversalKernel {
  return {
    ...lawkeyUniversalKernel,
    ...overrides,
  };
}

export type {
  FollowUpJobResponse,
  JobResultPayload,
  JobStatusPayload,
  PrecedentDetailPayload,
};
