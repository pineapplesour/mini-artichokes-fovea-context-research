#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.codex_home_failover import CodexHomeFailoverClient, load_unique_homes, resolve_codex_home_paths
from tools.resource_gate import collect_resource_snapshot, heavy_cli_allowed


VALIDATOR_VERSION = "choice-hidden-rewrite-v5"
MAXIMUM_RAW_MODEL_RESPONSE_CHARS = 20_000
CHOICE_DEPENDENT_PATTERNS = (
    r"다음\s*중",
    r"옳(?:지\s*않)?은\s*것",
    r"아닌\s*것",
    r"해당하는\s*것",
    r"고르(?:시오|라)",
    r"which\s+(?:of\s+the\s+)?following",
    r"select\s+(?:the|one|all)",
    r"choose\s+(?:the|one|all)",
    r"(?:보기|선택지)(?:에서|중|를|를\s*보고|에)",
    r"(?:above|below|listed)\s+(?:choice|option|item)s?",
    r"all\s+of\s+the\s+above",
)
OPTION_MARKER_RE = re.compile(r"(?:[①②③④⑤⑥⑦⑧⑨⑩]|(?:^|\s)[1-9][.)]\s)")


class CallBudget:
    def __init__(self, maximum: int = 0) -> None:
        self.maximum = max(0, int(maximum))
        self.used = 0

    def consume(self) -> bool:
        if self.maximum <= 0 or self.used >= self.maximum:
            return False
        self.used += 1
        return True


def validate_rewritten_prompt(prompt: str, answer_spec: dict[str, Any]) -> list[str]:
    candidate = str(prompt or "").strip()
    errors: list[str] = []
    if len(candidate) < 12:
        errors.append("rewritten_prompt_too_short")
    if any(re.search(pattern, candidate, re.IGNORECASE) for pattern in CHOICE_DEPENDENT_PATTERNS):
        errors.append("choice_dependent_wording_remains")
    if OPTION_MARKER_RE.search(candidate):
        errors.append("option_markers_remain")
    answer_forms = [str(answer_spec.get("canonicalAnswer") or "")]
    answer_forms.extend(str(value) for value in answer_spec.get("aliases", []) if str(value))
    compact_prompt = _compact_for_leak_check(candidate)
    for answer in answer_forms:
        compact_answer = _compact_for_leak_check(answer)
        if (
            len(compact_answer) >= 2
            and compact_answer in compact_prompt
        ) or (
            len(compact_answer) == 1
            and re.search(
                rf"(?<!\w){re.escape(compact_answer)}(?=(?:이라고|라고|입니다|이다|으로|은|는|이|가|을|를|의|로)|$|[^\w])",
                unicodedata.normalize("NFKC", candidate).casefold(),
            )
        ):
            errors.append("answer_text_leakage")
            break
    return errors


def build_author_prompt(
    *,
    manifest: dict[str, Any],
    case: dict[str, Any],
    answer_spec: dict[str, Any],
) -> str:
    payload = {
        "domain": manifest.get("product", ""),
        "language": case.get("language") or manifest.get("language", ""),
        "originalQuestion": case.get("prompt", ""),
        "canonicalAnswer": answer_spec.get("canonicalAnswer", ""),
        "acceptableAliases": answer_spec.get("aliases", []),
        "riskReasons": _conversion(case).get("riskReasons", []),
    }
    return (
        "You are privately authoring a choice-hidden open-response benchmark. Rewrite the question so it can be answered "
        "without seeing any options and the canonical answer is the uniquely intended answer. Preserve the tested knowledge, "
        "not the original wording. You may add a concise, factually sound discriminating description of the target, but do not "
        "print or visibly embed the canonical answer or an alias in the rewritten question. A prompt asking for any member of a "
        "multi-member category is NOT unique and must be rejected unless you add enough non-answer clues to identify one member. "
        "The canonical answer must directly and completely answer every slot requested by rewrittenPrompt; do not ask for a broad "
        "category, multiple effects, a range, or both a scope and a reason when the canonical supplies only one proposition. "
        "When the source uses several variables, actors, groups, times, or locations, preserve every distinction needed to derive the "
        "canonical answer; never give two symbols the same description after dropping a city, time, role, or condition. "
        "If the source is already a self-contained passage, scenario, table, or fill-in-the-blank problem after option bodies were removed, "
        "prefer a minimal stem-only rewrite and retain the complete source body verbatim. Do not summarize, relabel, or reconstruct its data. "
        "If the supplied gold appears false, internally inconsistent, or cannot be targeted uniquely without fabricating facts, reject it. "
        "Do not provide choices, option numbers, a solution, or a rationale inside rewrittenPrompt. Return exactly one JSON object: "
        "status ('ok' or 'reject'), rewrittenPrompt (string), expectedAnswerType (short string), uniquenessBasis (short string), "
        "and reason (short string).\n\n"
        f"PRIVATE_AUTHORING_PAYLOAD_JSON:\n{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}"
    )


def build_reviewer_prompt(
    *,
    manifest: dict[str, Any],
    case: dict[str, Any],
    answer_spec: dict[str, Any],
    rewritten_prompt: str,
    repeat: int,
) -> str:
    payload = {
        "domain": manifest.get("product", ""),
        "language": case.get("language") or manifest.get("language", ""),
        "originalQuestion": case.get("prompt", ""),
        "proposedQuestion": rewritten_prompt,
        "canonicalAnswer": answer_spec.get("canonicalAnswer", ""),
        "acceptableAliases": answer_spec.get("aliases", []),
    }
    return (
        "You are an independent private reviewer of a choice-hidden open-response benchmark. Be strict. A question is invalid if "
        "several real-world answers satisfy it while the key contains only one example. Check whether the canonical answer directly "
        "and uniquely answers the proposed question, whether the proposal preserves the original knowledge target, whether its added "
        "clues are factually plausible, and whether it leaks the answer text. Converting recognition or option-consistency judgment into "
        "free recall is the intended response-format change and does NOT by itself change the knowledge target; sameKnowledgeTarget asks "
        "whether the underlying fact, rule, concept, or inference remains the same. Still reject when the proposed question asks for any "
        "information not fully supplied by the canonical answer. Also reject if any source variables, actors, groups, times, locations, "
        "or conditions needed for the answer become indistinguishable in the proposal. When the source was already a self-contained passage, "
        "scenario, table, or fill-in-the-blank after choices were removed, reject a summary that drops or relabels any source data instead of "
        "making a minimal stem-only conversion. Return exactly one JSON object with verdict ('pass' or "
        "'reject'), answerableWithoutChoices (boolean), uniquelyTargetsCanonical (boolean), canonicalDirectlyAnswers (boolean), "
        "sameKnowledgeTarget (boolean), factuallyPlausible (boolean), noAnswerLeakage (boolean), and reason (short string).\n\n"
        f"PRIVATE_REVIEW_PAYLOAD_JSON:\n{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n"
        f"INDEPENDENT_REPEAT: {repeat}"
    )


def rewrite_manifests(
    *,
    public_manifest: dict[str, Any],
    private_manifest: dict[str, Any],
    output_dir: Path,
    llm_client: Any,
    model: str = "gpt-5.6-luna",
    case_ids: list[str] | None = None,
    max_cases: int = 0,
    max_model_calls: int = 0,
    review_repeats: int = 1,
    resume: bool = False,
    resource_gate_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if public_manifest.get("taskType") != "open_response":
        raise ValueError("expected public taskType=open_response")
    answer_by_id = {
        str(item.get("caseId") or ""): item
        for item in private_manifest.get("answers", [])
        if isinstance(item, dict) and item.get("caseId")
    }
    allowed = {str(value) for value in case_ids or [] if str(value)}
    candidates = [
        case
        for case in public_manifest.get("cases", [])
        if isinstance(case, dict)
        and _conversion(case).get("status") == "needs_semantic_rewrite"
        and str(case.get("id") or "") in answer_by_id
    ]
    if allowed:
        candidates = [case for case in candidates if str(case.get("id") or "") in allowed]
    if max_cases > 0:
        candidates = candidates[:max_cases]
    output_dir.mkdir(parents=True, exist_ok=True)
    drafts_dir = output_dir / "drafts-private"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    budget = CallBudget(max_model_calls)
    artifacts: dict[str, dict[str, Any]] = {}
    started = time.monotonic()
    for case in candidates:
        case_id = str(case.get("id") or "")
        answer_spec = answer_by_id[case_id]
        input_digest = _rewrite_input_digest(public_manifest, case, answer_spec)
        artifact_path = drafts_dir / f"{_safe_case_id(case_id)}.private.json"
        if resume and artifact_path.exists():
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            _validate_stored_artifact(
                artifact,
                manifest=public_manifest,
                case=case,
                answer_spec=answer_spec,
                model=model,
                review_repeats=max(1, int(review_repeats)),
            )
            artifacts[case_id] = artifact
            continue
        artifact: dict[str, Any] = {
            "schemaVersion": 2,
            "validatorVersion": VALIDATOR_VERSION,
            "caseId": case_id,
            "model": model,
            "inputDigest": input_digest,
            "authorPromptSha256": input_digest,
            "rewriteToolSha256": _rewrite_tool_sha256(),
            "privateCanonicalAnswer": answer_spec.get("canonicalAnswer", ""),
            "author": {},
            "authorTrace": {},
            "traceErrors": [],
            "deterministicErrors": [],
            "reviews": [],
            "approved": False,
            "error": "",
        }
        if not budget.consume():
            artifact["error"] = "model_call_budget_exhausted_before_author"
            _write_artifact(artifact_path, artifact)
            artifacts[case_id] = artifact
            break
        try:
            author_prompt = build_author_prompt(manifest=public_manifest, case=case, answer_spec=answer_spec)
            raw = str(
                llm_client.complete(
                    [{"role": "user", "content": author_prompt}],
                    model=model,
                )
                or ""
            )
            if len(raw) > MAXIMUM_RAW_MODEL_RESPONSE_CHARS:
                raise ValueError("author response exceeds maximum length")
            artifact["author"] = _parse_author(raw)
            artifact["authorRawResponse"] = raw
            artifact["authorRawResponseSha256"] = _text_sha256(raw)
            artifact["authorTrace"] = _consume_trace(llm_client)
            artifact["traceErrors"] = [
                f"author:{error}" for error in _closed_tool_trace_errors(artifact["authorTrace"])
            ]
        except Exception as exc:
            artifact["error"] = str(exc)[:1000]
            _write_artifact(artifact_path, artifact)
            artifacts[case_id] = artifact
            continue
        rewritten_prompt = str(artifact["author"].get("rewrittenPrompt") or "")
        if artifact["author"].get("status") != "ok":
            artifact["error"] = "author_rejected"
        else:
            artifact["deterministicErrors"] = validate_rewritten_prompt(rewritten_prompt, answer_spec)
        if not artifact["error"] and not artifact["deterministicErrors"] and not artifact["traceErrors"]:
            for repeat in range(1, max(1, int(review_repeats)) + 1):
                if not budget.consume():
                    artifact["error"] = "model_call_budget_exhausted_before_review"
                    break
                try:
                    reviewer_prompt = build_reviewer_prompt(
                        manifest=public_manifest,
                        case=case,
                        answer_spec=answer_spec,
                        rewritten_prompt=rewritten_prompt,
                        repeat=repeat,
                    )
                    raw = str(
                        llm_client.complete(
                            [{"role": "user", "content": reviewer_prompt}],
                            model=model,
                        )
                        or ""
                    )
                    if len(raw) > MAXIMUM_RAW_MODEL_RESPONSE_CHARS:
                        raise ValueError("review response exceeds maximum length")
                    review = _parse_review(raw)
                    review["repeat"] = repeat
                    review["promptSha256"] = _text_sha256(reviewer_prompt)
                    review["rawResponse"] = raw
                    review["rawResponseSha256"] = _text_sha256(raw)
                    review["trace"] = _consume_trace(llm_client)
                    review["traceErrors"] = _closed_tool_trace_errors(review["trace"])
                    artifact["reviews"].append(review)
                except Exception as exc:
                    artifact["reviews"].append({"repeat": repeat, "error": str(exc)[:1000]})
        artifact["approved"] = (
            not artifact["error"]
            and not artifact["deterministicErrors"]
            and not artifact["traceErrors"]
            and len(artifact["reviews"]) == max(1, int(review_repeats))
            and all(_review_passes(review) for review in artifact["reviews"])
        )
        _write_artifact(artifact_path, artifact)
        artifacts[case_id] = artifact

    all_case_by_id = {
        str(case.get("id") or ""): case
        for case in public_manifest.get("cases", [])
        if isinstance(case, dict) and case.get("id")
    }
    for artifact_path in sorted(drafts_dir.glob("*.private.json")):
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        case_id = str(artifact.get("caseId") or "")
        case = all_case_by_id.get(case_id)
        answer_spec = answer_by_id.get(case_id)
        if case is None or answer_spec is None:
            continue
        _validate_stored_artifact(
            artifact,
            manifest=public_manifest,
            case=case,
            answer_spec=answer_spec,
            model=model,
            review_repeats=max(1, int(review_repeats)),
        )
        artifacts.setdefault(case_id, artifact)

    promoted_public = json.loads(json.dumps(public_manifest, ensure_ascii=False))
    promoted_private = json.loads(json.dumps(private_manifest, ensure_ascii=False))
    for case in promoted_public.get("cases", []):
        case_id = str(case.get("id") or "") if isinstance(case, dict) else ""
        artifact = artifacts.get(case_id)
        if not artifact or not artifact.get("approved"):
            continue
        case["prompt"] = artifact["author"]["rewrittenPrompt"]
        conversion = _conversion(case)
        prior_risks = list(conversion.get("riskReasons", []))
        conversion["status"] = "ready_semantic_rewrite"
        conversion["riskReasons"] = []
        conversion["semanticRewrite"] = {
            "model": model,
            "validatorVersion": VALIDATOR_VERSION,
            "reviewRepeats": max(1, int(review_repeats)),
            "inputDigest": artifact["inputDigest"],
            "artifactDigest": artifact["artifactDigest"],
            "resolvedRiskReasons": prior_risks,
        }
    for answer_spec in promoted_private.get("answers", []):
        case_id = str(answer_spec.get("caseId") or "") if isinstance(answer_spec, dict) else ""
        if artifacts.get(case_id, {}).get("approved"):
            answer_spec["conversionStatus"] = "ready_semantic_rewrite"
            answer_spec["semanticRewriteArtifactDigest"] = artifacts[case_id]["artifactDigest"]
    status_counts = Counter(
        str(_conversion(case).get("status") or "")
        for case in promoted_public.get("cases", [])
        if isinstance(case, dict)
    )
    audit = promoted_public.setdefault("conversionAudit", {})
    audit["statusCounts"] = dict(sorted(status_counts.items()))
    audit["semanticRewriteModel"] = model
    audit["semanticRewriteValidator"] = VALIDATOR_VERSION
    public_output = output_dir / f"{public_manifest.get('benchmarkId', 'benchmark')}.rewritten.public.json"
    private_output = output_dir / f"{private_manifest.get('benchmarkId', 'benchmark')}.rewritten.private.json"
    _write_json(public_output, promoted_public)
    _write_json(private_output, promoted_private)
    approved = sum(1 for artifact in artifacts.values() if artifact.get("approved"))
    report = {
        "benchmarkId": public_manifest.get("benchmarkId", ""),
        "model": model,
        "validatorVersion": VALIDATOR_VERSION,
        "selectedCandidates": len(candidates),
        "processedArtifacts": len(artifacts),
        "approved": approved,
        "rejectedOrUnresolved": len(artifacts) - approved,
        "modelCallsUsed": budget.used,
        "modelCallBudget": budget.maximum,
        "resourceGateAtStart": resource_gate_snapshot,
        "publicOutput": str(public_output),
        "privateOutput": str(private_output),
        "elapsedSec": round(time.monotonic() - started, 3),
    }
    _write_json(output_dir / "rewrite-summary.json", report)
    return report


def _parse_author(raw: str) -> dict[str, Any]:
    payload = _parse_json_object(raw)
    required = {"status", "rewrittenPrompt", "expectedAnswerType", "uniquenessBasis", "reason"}
    if set(payload) != required or any(not isinstance(payload.get(field), str) for field in required):
        raise ValueError("author response must contain exactly the required string fields")
    status = str(payload.get("status") or "")
    if status not in {"ok", "reject"}:
        raise ValueError("author response has invalid status")
    if not str(payload.get("reason") or "").strip():
        raise ValueError("author response reason must be nonempty")
    if status == "ok" and any(
        not str(payload.get(field) or "").strip()
        for field in ("rewrittenPrompt", "expectedAnswerType", "uniquenessBasis")
    ):
        raise ValueError("approved author response fields must be nonempty")
    return {
        "status": status,
        "rewrittenPrompt": str(payload.get("rewrittenPrompt") or "").strip(),
        "expectedAnswerType": str(payload.get("expectedAnswerType") or "")[:200],
        "uniquenessBasis": str(payload.get("uniquenessBasis") or "")[:500],
        "reason": str(payload.get("reason") or "")[:500],
    }


def _parse_review(raw: str) -> dict[str, Any]:
    payload = _parse_json_object(raw)
    verdict = str(payload.get("verdict") or "")
    fields = (
        "answerableWithoutChoices",
        "uniquelyTargetsCanonical",
        "canonicalDirectlyAnswers",
        "sameKnowledgeTarget",
        "factuallyPlausible",
        "noAnswerLeakage",
    )
    required = {"verdict", *fields, "reason"}
    if set(payload) != required or not isinstance(payload.get("reason"), str):
        raise ValueError("review response must contain exactly the required fields")
    if verdict not in {"pass", "reject"} or any(not isinstance(payload.get(field), bool) for field in fields):
        raise ValueError("review response is missing strict boolean fields")
    if not str(payload.get("reason") or "").strip():
        raise ValueError("review response reason must be nonempty")
    return {"verdict": verdict, **{field: payload[field] for field in fields}, "reason": str(payload.get("reason") or "")[:500]}


def _review_passes(review: dict[str, Any]) -> bool:
    required = (
        "answerableWithoutChoices",
        "uniquelyTargetsCanonical",
        "canonicalDirectlyAnswers",
        "sameKnowledgeTarget",
        "factuallyPlausible",
        "noAnswerLeakage",
    )
    return (
        review.get("verdict") == "pass"
        and not review.get("traceErrors")
        and all(review.get(field) is True for field in required)
    )


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if text.startswith("```") and text.endswith("```"):
        text = "\n".join(text.splitlines()[1:-1]).strip()
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("model response must be a JSON object")
    return payload


def _conversion(case: dict[str, Any]) -> dict[str, Any]:
    metadata = case.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("case metadata must be an object")
    conversion = metadata.setdefault("openResponseConversion", {})
    if not isinstance(conversion, dict):
        raise ValueError("openResponseConversion must be an object")
    return conversion


def _compact_for_leak_check(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return "".join(character for character in normalized if character.isalnum())


def _text_sha256(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _rewrite_tool_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _rewrite_input_digest(
    manifest: dict[str, Any],
    case: dict[str, Any],
    answer_spec: dict[str, Any],
) -> str:
    return _text_sha256(build_author_prompt(manifest=manifest, case=case, answer_spec=answer_spec))


def _safe_case_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or ""))[:180]


def _consume_trace(client: Any) -> dict[str, Any]:
    consume = getattr(client, "consume_last_call_trace", None)
    trace = consume() if callable(consume) else None
    return trace if isinstance(trace, dict) else {}


def _closed_tool_trace_errors(trace: Any) -> list[str]:
    if not isinstance(trace, dict) or not trace:
        return ["trace_missing"]
    errors: list[str] = []
    if trace.get("provider") != "codex_exec" or trace.get("status") != "completed":
        errors.append("codex_completion_not_verified")
    if int(trace.get("codexJsonlInvalidLineCount") or 0):
        errors.append("invalid_codex_jsonl")
    for field, label in (
        ("webSearchEvents", "web_search_used"),
        ("commandExecutionEvents", "shell_used"),
        ("mcpToolEvents", "mcp_used"),
    ):
        value = trace.get(field)
        if not isinstance(value, list):
            errors.append(f"{field}_missing")
        elif value:
            errors.append(label)
    usage = trace.get("tokenUsage")
    if not isinstance(usage, dict) or int(usage.get("totalTokens") or 0) <= 0:
        errors.append("token_usage_missing")
    return errors


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _artifact_digest(artifact: dict[str, Any]) -> str:
    payload = {key: value for key, value in artifact.items() if key != "artifactDigest"}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_artifact(path: Path, artifact: dict[str, Any]) -> None:
    artifact["artifactDigest"] = _artifact_digest(artifact)
    _write_json(path, artifact)


def _validate_stored_artifact(
    artifact: dict[str, Any],
    *,
    manifest: dict[str, Any],
    case: dict[str, Any],
    answer_spec: dict[str, Any],
    model: str,
    review_repeats: int,
) -> None:
    case_id = str(case.get("id") or "")
    if artifact.get("schemaVersion") != 2 or artifact.get("validatorVersion") != VALIDATOR_VERSION:
        raise ValueError(f"stored rewrite validator changed for {case_id}")
    expected_input_digest = _rewrite_input_digest(manifest, case, answer_spec)
    if artifact.get("inputDigest") != expected_input_digest:
        raise ValueError(f"stored rewrite input changed for {case_id}")
    if artifact.get("authorPromptSha256") != expected_input_digest:
        raise ValueError(f"stored rewrite author prompt digest mismatch for {case_id}")
    if artifact.get("rewriteToolSha256") != _rewrite_tool_sha256():
        raise ValueError(f"stored rewrite tool changed for {case_id}")
    if str(artifact.get("model") or "") != str(model or ""):
        raise ValueError(f"stored rewrite model changed for {case_id}")
    if artifact.get("artifactDigest") != _artifact_digest(artifact):
        raise ValueError(f"stored rewrite artifact digest mismatch for {case_id}")
    if artifact.get("approved") is not True:
        return
    author = artifact.get("author")
    if not isinstance(author, dict) or author.get("status") != "ok":
        raise ValueError(f"stored approved rewrite lacks an ok author for {case_id}")
    author_raw = artifact.get("authorRawResponse")
    if not isinstance(author_raw, str) or len(author_raw) > MAXIMUM_RAW_MODEL_RESPONSE_CHARS:
        raise ValueError(f"stored approved rewrite author response is invalid for {case_id}")
    if artifact.get("authorRawResponseSha256") != _text_sha256(author_raw) or _parse_author(author_raw) != author:
        raise ValueError(f"stored approved rewrite author response mismatch for {case_id}")
    rewritten_prompt = str(author.get("rewrittenPrompt") or "")
    deterministic_errors = validate_rewritten_prompt(rewritten_prompt, answer_spec)
    if deterministic_errors or artifact.get("deterministicErrors") != deterministic_errors:
        raise ValueError(f"stored approved rewrite fails current deterministic validation for {case_id}")
    if str(artifact.get("error") or ""):
        raise ValueError(f"stored approved rewrite contains an error for {case_id}")
    expected_trace_errors = [
        f"author:{error}" for error in _closed_tool_trace_errors(artifact.get("authorTrace"))
    ]
    if expected_trace_errors or artifact.get("traceErrors") != expected_trace_errors:
        raise ValueError(f"stored approved rewrite author trace contract failed for {case_id}")
    reviews = artifact.get("reviews")
    if not isinstance(reviews, list) or len(reviews) != review_repeats:
        raise ValueError(f"stored approved rewrite review count mismatch for {case_id}")
    repeats = [int(review.get("repeat") or 0) for review in reviews if isinstance(review, dict)]
    if repeats != list(range(1, review_repeats + 1)) or not all(_review_passes(review) for review in reviews):
        raise ValueError(f"stored approved rewrite review contract failed for {case_id}")
    for review in reviews:
        repeat = int(review["repeat"])
        expected_prompt = build_reviewer_prompt(
            manifest=manifest,
            case=case,
            answer_spec=answer_spec,
            rewritten_prompt=rewritten_prompt,
            repeat=repeat,
        )
        raw_response = review.get("rawResponse")
        if not isinstance(raw_response, str) or len(raw_response) > MAXIMUM_RAW_MODEL_RESPONSE_CHARS:
            raise ValueError(f"stored approved rewrite review response is invalid for {case_id}")
        parsed_review = _parse_review(raw_response)
        if review.get("promptSha256") != _text_sha256(expected_prompt):
            raise ValueError(f"stored approved rewrite review prompt mismatch for {case_id}")
        if review.get("rawResponseSha256") != _text_sha256(raw_response):
            raise ValueError(f"stored approved rewrite review response digest mismatch for {case_id}")
        for key, value in parsed_review.items():
            if review.get(key) != value:
                raise ValueError(f"stored approved rewrite review response mismatch for {case_id}")
        if _closed_tool_trace_errors(review.get("trace")) or review.get("traceErrors") != []:
            raise ValueError(f"stored approved rewrite review trace contract failed for {case_id}")


def validate_single_case_swap_override(
    *,
    requested: bool,
    case_ids: list[str],
    max_cases: int,
    max_model_calls: int,
    review_repeats: int,
) -> None:
    if not requested:
        return
    if len({str(value).strip() for value in case_ids if str(value).strip()}) != 1:
        raise ValueError("rewrite existing-swap override requires exactly one --case-id")
    if int(max_cases) not in {0, 1}:
        raise ValueError("rewrite existing-swap override requires --max-cases 1 or omission")
    if int(review_repeats) not in {1, 2}:
        raise ValueError("rewrite existing-swap override permits one or two sequential reviews")
    if int(max_model_calls) != 1 + int(review_repeats):
        raise ValueError("rewrite existing-swap override requires one author call plus the requested reviews")


def main() -> int:
    parser = argparse.ArgumentParser(description="Privately rewrite choice-dependent open-response cases with Luna and strict review.")
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--codex-home", action="append", type=Path, default=[])
    parser.add_argument("--discover-codex-home-root", type=Path)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--reasoning-effort", default="low")
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--max-model-calls", type=int, default=0)
    parser.add_argument("--review-repeats", type=int, default=1)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--allow-existing-swap-single-task",
        action="store_true",
        help="User-authorized one-case author/reviewer sequence only; starting resources are persisted.",
    )
    args = parser.parse_args()
    try:
        validate_single_case_swap_override(
            requested=args.allow_existing_swap_single_task,
            case_ids=args.case_id,
            max_cases=args.max_cases,
            max_model_calls=args.max_model_calls,
            review_repeats=args.review_repeats,
        )
    except ValueError as exc:
        parser.error(str(exc))
    if not heavy_cli_allowed(allow_existing_swap_single_task=args.allow_existing_swap_single_task):
        return 2
    resource_gate_snapshot = collect_resource_snapshot(
        allow_existing_swap_single_task=args.allow_existing_swap_single_task,
    )
    homes = load_unique_homes(resolve_codex_home_paths(args.codex_home, args.discover_codex_home_root))
    client = CodexHomeFailoverClient(
        homes=homes,
        default_model=args.model,
        timeout_seconds=args.timeout_seconds,
        reasoning_effort=args.reasoning_effort,
        verbosity="low",
        web_search_enabled=False,
        state_path=args.output_dir / "codex-home-state.json",
    )
    report = rewrite_manifests(
        public_manifest=json.loads(args.public.read_text(encoding="utf-8")),
        private_manifest=json.loads(args.private.read_text(encoding="utf-8")),
        output_dir=args.output_dir,
        llm_client=client,
        model=args.model,
        case_ids=args.case_id,
        max_cases=args.max_cases,
        max_model_calls=args.max_model_calls,
        review_repeats=max(1, args.review_repeats),
        resume=args.resume,
        resource_gate_snapshot=resource_gate_snapshot,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
