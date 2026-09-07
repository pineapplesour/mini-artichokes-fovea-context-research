"""Single source of truth for "is this a question job or a document job?"

Mirrors `lib/intent.ts` — both must stay in lockstep. Backend ingress
(both `LawkeyJobManager.create_job` and `LawkeyJobManager.follow_up
forceNewJob`) and frontend submit MUST call this same function so that
adding a new keyword pattern in one place updates routing everywhere.

Historically, three independent implementations drifted (frontend submit,
backend follow-up guard, backend create_job guard) and `고소장 작성해줘`
ended up stuck in `mode=question` on the follow-up path. This consolidates.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

JobMode = Literal["question", "document"]
JobIntentReason = Literal["chip_document", "phrase_in_question_chip", "follow_up_phrase", "default"]

# Regex set MUST match `lib/document-flow.ts`. Allow a couple of filler
# chars between syllables to catch typos (`고1소장`, `고-소-장`).
_DOCUMENT_TYPE_PATTERN = re.compile(
    r"고[^가-힣]{0,2}소[^가-힣]{0,2}(?:장|작)"
    r"|고[^가-힣]{0,2}발[^가-힣]{0,2}장"
    r"|내[^가-힣]{0,2}용[^가-힣]{0,2}증[^가-힣]{0,2}명"
    r"|변호인\s*의견서|변호인의견서|의견서|준비서면|답변서|항소이유서|탄원서|진정서|계약서|합의서"
)
_DOCUMENT_ACTION_PATTERN = re.compile(
    r"작성|써\s*줘|써줘|만들|초안|문서화|양식|정리해\s*줘|정리해줘|제출|작성해\s*줘|작성해줘|보내|보내야"
)
_DOCUMENT_PHRASE_OVERRIDE = re.compile(
    r"문서화|문서로\s*(?:작성|만들|정리)|초안으로\s*(?:작성|만들)|양식으로\s*(?:작성|만들)"
)
_COMPLAINT_PRESET_HINT = re.compile(
    r"고\s*소\s*(?:장|작)|고소취지|고소인|피고소인|범죄사실|처벌하여\s*주시"
)


def _should_route_to_document(prompt: str) -> bool:
    text = (prompt or "").strip()
    if not text:
        return False
    if _DOCUMENT_PHRASE_OVERRIDE.search(text):
        return True
    return bool(_DOCUMENT_TYPE_PATTERN.search(text) and _DOCUMENT_ACTION_PATTERN.search(text))


def _infer_preset(prompt: str) -> str:
    text = (prompt or "").strip()
    if _COMPLAINT_PRESET_HINT.search(text):
        return "complaint"
    return ""


@dataclass
class JobIntent:
    mode: JobMode
    document_preset: str
    reason: JobIntentReason


def decide_job_intent(
    *,
    input_mode_chip: JobMode,
    prompt: str,
    is_follow_up: bool = False,
    explicit_preset: str = "",
) -> JobIntent:
    if input_mode_chip == "document":
        return JobIntent(
            mode="document",
            document_preset=(explicit_preset or _infer_preset(prompt)),
            reason="chip_document",
        )
    if _should_route_to_document(prompt):
        return JobIntent(
            mode="document",
            document_preset=(explicit_preset or _infer_preset(prompt)),
            reason=("follow_up_phrase" if is_follow_up else "phrase_in_question_chip"),
        )
    return JobIntent(mode="question", document_preset="", reason="default")
