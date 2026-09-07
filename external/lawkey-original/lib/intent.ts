// Single source of truth for "is this a question job or a document job?"
// All three historical entry points (frontend submit / frontend retry /
// backend follow-up `forceNewJob` ingress / backend `create_job` ingress)
// must end up calling this function. Adding a new pattern in one place
// must update the others — historically the patches drifted.
//
// Backend has a parallel implementation in `backend/intent.py` with the
// same regex set. They MUST stay in sync.

import { inferDocumentPresetIdFromPrompt, shouldRouteQuestionToDocument } from "./document-flow";

export type JobMode = "question" | "document";

export type JobIntentReason =
  | "chip_document"
  | "phrase_in_question_chip"
  | "follow_up_phrase"
  | "default";

export type JobIntent = {
  mode: JobMode;
  documentPreset: string;
  reason: JobIntentReason;
};

export type DecideJobIntentInput = {
  // The composer chip the user clicked at submit time.
  inputModeChip: JobMode;
  // The prompt text the user is sending.
  prompt: string;
  // True when this is a follow-up (existing job + `forceNewJob`) — backend
  // ingress used to skip routing here, leaving "고소장 작성해줘" stuck in
  // mode=question. We always re-route follow-ups too.
  isFollowUp?: boolean;
  // Optional: explicit preset already chosen via UI (overrides inference).
  explicitPreset?: string;
};

export function decideJobIntent(input: DecideJobIntentInput): JobIntent {
  const { inputModeChip, prompt, isFollowUp = false, explicitPreset = "" } = input;

  if (inputModeChip === "document") {
    return {
      mode: "document",
      documentPreset: explicitPreset || inferDocumentPresetIdFromPrompt(prompt, ""),
      reason: "chip_document",
    };
  }

  if (shouldRouteQuestionToDocument(prompt)) {
    return {
      mode: "document",
      documentPreset: explicitPreset || inferDocumentPresetIdFromPrompt(prompt, ""),
      reason: isFollowUp ? "follow_up_phrase" : "phrase_in_question_chip",
    };
  }

  return { mode: "question", documentPreset: "", reason: "default" };
}
