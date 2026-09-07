#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.benchmark_provider import CodexExecLLMClient
from tools.codex_home_failover import CodexHomeFailoverClient, load_unique_homes, resolve_codex_home_paths
from tools.resource_gate import collect_resource_snapshot, heavy_cli_allowed


OFFICIAL_CONVERSION_STATUSES = frozenset({"ready_hide_options", "ready_semantic_rewrite"})
SEMANTIC_JUDGE_POLICY_VERSION = "strict-equivalence-consensus-v3-closed-trace"


@dataclass(frozen=True)
class GradeDecision:
    verdict: str
    path: str
    reason: str
    judge_attempts: tuple[dict[str, Any], ...] = ()


class JudgeBudget:
    def __init__(self, maximum_calls: int = 0) -> None:
        self.maximum_calls = max(0, int(maximum_calls))
        self.used_calls = 0

    def consume(self) -> bool:
        if self.maximum_calls and self.used_calls >= self.maximum_calls:
            return False
        self.used_calls += 1
        return True


def normalize_answer(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = normalized.strip(" \t\r\n\"'`.,;:!?。、，；：！？()[]{}")
    return normalized


def normalize_exact_formula_surface(value: str) -> str | None:
    """Normalize presentation-only differences for an otherwise identical formula.

    This is intentionally not an algebra solver: it removes whitespace and a
    few unambiguous Unicode operator glyphs only when the entire answer is an
    expression-like ASCII surface containing at least one operator.
    """

    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    normalized = normalized.translate(str.maketrans({"−": "-", "×": "*", "÷": "/"}))
    if not normalized or not re.fullmatch(r"[a-z0-9_+*/^=().\[\]{}\s-]+", normalized):
        return None
    if not re.search(r"[+*/^=-]", normalized) or not re.search(r"[a-z0-9]", normalized):
        return None
    return re.sub(r"\s+", "", normalized)


def semantic_judge_input_sha256(
    *,
    case_id: str,
    question: str,
    candidate: str,
    canonical: str,
    aliases: list[str],
    judge_model: str,
) -> str:
    payload = {
        "policyVersion": SEMANTIC_JUDGE_POLICY_VERSION,
        "caseId": str(case_id or ""),
        "question": str(question or ""),
        "candidateAnswer": str(candidate or ""),
        "canonicalAnswer": str(canonical or ""),
        "acceptableAliases": [str(value) for value in aliases],
        "judgeModel": str(judge_model or ""),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _declared_answer_surfaces(values: list[str]) -> set[str]:
    surfaces: set[str] = set()
    for value in values:
        raw = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
        if not raw:
            continue
        surfaces.add(normalize_answer(raw))
        base_and_rest = re.split(r"\s*[([{（［【]", raw, maxsplit=1)
        surfaces.add(normalize_answer(base_and_rest[0]))
        if len(base_and_rest) == 2:
            annotation = base_and_rest[1].rstrip(")]}）］】 ")
            surfaces.update(
                normalize_answer(part)
                for part in re.split(r"[,;/；，、]", annotation)
                if normalize_answer(part)
            )
    return {value for value in surfaces if value}


def _matches_declared_parenthetical_annotation(candidate: str, declared_answers: list[str]) -> bool:
    """Accept a parenthetical only when every surface is curator-declared."""

    normalized_candidate = unicodedata.normalize("NFKC", str(candidate or "")).casefold().strip()
    opening_positions = [position for marker in "([{（［【" if (position := normalized_candidate.find(marker)) >= 0]
    if not opening_positions:
        return False
    opening_index = min(opening_positions)
    base = normalize_answer(normalized_candidate[:opening_index])
    annotation = normalized_candidate[opening_index:].strip()
    bracket_pairs = {"(": ")", "[": "]", "{": "}", "（": "）", "［": "］", "【": "】"}
    if len(annotation) < 3 or annotation[0] not in bracket_pairs or annotation[-1] != bracket_pairs[annotation[0]]:
        return False
    annotation_body = annotation[1:-1].strip()
    if not annotation_body:
        return False
    declared_surfaces = _declared_answer_surfaces(declared_answers)
    annotation_surfaces = [
        normalize_answer(part)
        for part in re.split(r"[,;/；，、]", annotation_body)
        if normalize_answer(part)
    ]
    return bool(base and annotation_surfaces) and base in declared_surfaces and all(
        surface in declared_surfaces for surface in annotation_surfaces
    )


def grade_candidate(
    *,
    case_id: str = "",
    question: str,
    candidate: str,
    answer_spec: dict[str, Any],
    judge_client: Any | None = None,
    judge_model: str = "",
    judge_budget: JudgeBudget | None = None,
    existing_judge_attempts: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
) -> GradeDecision:
    canonical = str(answer_spec.get("canonicalAnswer") or "")
    aliases = [str(value) for value in answer_spec.get("aliases", []) if str(value)]
    normalized_candidate = normalize_answer(candidate)
    if not normalized_candidate:
        return GradeDecision("fail", "invalid_prediction", "empty candidate")
    if normalized_candidate == normalize_answer(canonical):
        return GradeDecision("pass", "normalized_exact", "candidate matches canonical answer after conservative normalization")
    candidate_formula = normalize_exact_formula_surface(candidate)
    canonical_formula = normalize_exact_formula_surface(canonical)
    if candidate_formula is not None and candidate_formula == canonical_formula:
        return GradeDecision(
            "pass",
            "formula_surface_exact",
            "candidate matches the canonical formula after presentation-only operator and whitespace normalization",
        )
    declared_answers = [canonical, *aliases]
    if _matches_declared_parenthetical_annotation(candidate, declared_answers):
        return GradeDecision(
            "pass",
            "canonical_with_parenthetical_annotation",
            "candidate base and every parenthetical surface are curator-declared answers or aliases",
        )
    if any(normalized_candidate == normalize_answer(alias) for alias in aliases):
        return GradeDecision("pass", "declared_alias_exact", "candidate matches a declared alias")
    keyword_decision = _grade_explicit_keyword_rules(candidate, answer_spec.get("keywordRules"))
    if keyword_decision is not None:
        return keyword_decision
    semantic_input_sha256 = semantic_judge_input_sha256(
        case_id=case_id,
        question=question,
        candidate=candidate,
        canonical=canonical,
        aliases=aliases,
        judge_model=judge_model,
    )
    resumed_decision = _decision_from_existing_attempts(
        existing_judge_attempts or (),
        expected_input_sha256=semantic_input_sha256,
        expected_judge_model=judge_model,
    )
    if resumed_decision is not None:
        return resumed_decision
    if judge_client is None or not judge_model:
        return GradeDecision("unresolved", "semantic_judge_not_run", "deterministic checks did not decide equivalence")
    return _semantic_consensus(
        question=question,
        candidate=candidate,
        canonical=canonical,
        aliases=aliases,
        judge_client=judge_client,
        judge_model=judge_model,
        semantic_input_sha256=semantic_input_sha256,
        budget=judge_budget or JudgeBudget(),
        existing_attempts=existing_judge_attempts or (),
    )


def _grade_explicit_keyword_rules(candidate: str, raw_rules: Any) -> GradeDecision | None:
    if not isinstance(raw_rules, dict) or not bool(raw_rules.get("autoConfirm")):
        return None
    normalized_candidate = normalize_answer(candidate)
    forbidden = [normalize_answer(value) for value in raw_rules.get("mustNotIncludeAny", []) if normalize_answer(value)]
    if any(term in normalized_candidate for term in forbidden):
        return GradeDecision("fail", "explicit_keyword_forbidden", "candidate contains an explicitly forbidden concept")
    groups = raw_rules.get("mustIncludeGroups")
    if not isinstance(groups, list) or not groups:
        return None
    for group in groups:
        terms = [normalize_answer(value) for value in group if normalize_answer(value)] if isinstance(group, list) else []
        if not terms or not any(term in normalized_candidate for term in terms):
            return None
    return GradeDecision("pass", "explicit_keyword_confirm", "all curator-declared concept groups matched and no forbidden concept matched")


def _semantic_consensus(
    *,
    question: str,
    candidate: str,
    canonical: str,
    aliases: list[str],
    judge_client: Any,
    judge_model: str,
    semantic_input_sha256: str,
    budget: JudgeBudget,
    existing_attempts: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
) -> GradeDecision:
    attempts = _validated_existing_attempts(
        existing_attempts,
        expected_input_sha256=semantic_input_sha256,
        expected_judge_model=judge_model,
    )
    seen_repeats = {int(item["repeat"]) for item in attempts}

    for repeat in range(1, 3):
        if repeat in seen_repeats:
            continue
        attempt = _run_semantic_judge(
            question=question,
            candidate=candidate,
            canonical=canonical,
            aliases=aliases,
            judge_client=judge_client,
            judge_model=judge_model,
            semantic_input_sha256=semantic_input_sha256,
            repeat=repeat,
            budget=budget,
        )
        attempts.append(attempt)
        if isinstance(attempt.get("equivalent"), bool):
            seen_repeats.add(repeat)
    valid = [attempt for attempt in attempts if isinstance(attempt.get("equivalent"), bool)]
    if len(valid) == 2 and valid[0]["equivalent"] == valid[1]["equivalent"]:
        passed = bool(valid[0]["equivalent"])
        return GradeDecision("pass" if passed else "fail", "semantic_judge_2of2", _consensus_reason(valid), tuple(attempts))
    if 3 not in seen_repeats:
        attempt = _run_semantic_judge(
            question=question,
            candidate=candidate,
            canonical=canonical,
            aliases=aliases,
            judge_client=judge_client,
            judge_model=judge_model,
            semantic_input_sha256=semantic_input_sha256,
            repeat=3,
            budget=budget,
        )
        attempts.append(attempt)
    valid = [item for item in attempts if isinstance(item.get("equivalent"), bool)]
    pass_count = sum(1 for item in valid if item["equivalent"] is True)
    fail_count = sum(1 for item in valid if item["equivalent"] is False)
    if pass_count >= 2:
        return GradeDecision("pass", "semantic_judge_2of3", _consensus_reason(valid), tuple(attempts))
    if fail_count >= 2:
        return GradeDecision("fail", "semantic_judge_2of3", _consensus_reason(valid), tuple(attempts))
    return GradeDecision("unresolved", "semantic_judge_unresolved", "fewer than two valid agreeing judge decisions", tuple(attempts))


def _validated_existing_attempts(
    existing_attempts: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    expected_input_sha256: str,
    expected_judge_model: str,
) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    seen_repeats: set[int] = set()
    for raw_attempt in existing_attempts:
        if not isinstance(raw_attempt, dict) or not isinstance(raw_attempt.get("equivalent"), bool):
            continue
        if raw_attempt.get("semanticInputSha256") != expected_input_sha256:
            continue
        if str(raw_attempt.get("judgeModel") or "") != str(expected_judge_model or ""):
            continue
        if raw_attempt.get("policyVersion") != SEMANTIC_JUDGE_POLICY_VERSION:
            continue
        trace_audit = raw_attempt.get("closedToolTraceAudit")
        if not isinstance(trace_audit, dict) or trace_audit.get("passed") is not True:
            continue
        if trace_audit.get("violations") != []:
            continue
        if not isinstance(raw_attempt.get("contradiction"), bool):
            continue
        missing = raw_attempt.get("missingCriticalFacts")
        if not isinstance(missing, list) or not all(isinstance(value, str) for value in missing):
            continue
        if not isinstance(raw_attempt.get("reason"), str) or not raw_attempt["reason"].strip():
            continue
        if raw_attempt["equivalent"] is True and (
            raw_attempt["contradiction"] is True or any(value.strip() for value in missing)
        ):
            continue
        repeat = int(raw_attempt.get("repeat") or 0)
        if repeat not in {1, 2, 3} or repeat in seen_repeats:
            continue
        attempts.append(dict(raw_attempt))
        seen_repeats.add(repeat)
    return sorted(attempts, key=lambda item: int(item.get("repeat") or 0))


def _decision_from_existing_attempts(
    existing_attempts: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    expected_input_sha256: str,
    expected_judge_model: str,
) -> GradeDecision | None:
    valid = _validated_existing_attempts(
        existing_attempts,
        expected_input_sha256=expected_input_sha256,
        expected_judge_model=expected_judge_model,
    )
    first_two = [item for item in valid if int(item.get("repeat") or 0) in {1, 2}]
    if len(first_two) == 2 and first_two[0]["equivalent"] == first_two[1]["equivalent"]:
        passed = bool(first_two[0]["equivalent"])
        return GradeDecision(
            "pass" if passed else "fail",
            "semantic_judge_2of2_resumed",
            _consensus_reason(first_two),
            tuple(valid),
        )
    pass_count = sum(1 for item in valid if item["equivalent"] is True)
    fail_count = sum(1 for item in valid if item["equivalent"] is False)
    if pass_count >= 2 or fail_count >= 2:
        return GradeDecision(
            "pass" if pass_count >= 2 else "fail",
            "semantic_judge_2of3_resumed",
            _consensus_reason(valid),
            tuple(valid),
        )
    return None


def _run_semantic_judge(
    *,
    question: str,
    candidate: str,
    canonical: str,
    aliases: list[str],
    judge_client: Any,
    judge_model: str,
    semantic_input_sha256: str,
    repeat: int,
    budget: JudgeBudget,
) -> dict[str, Any]:
    if not budget.consume():
        return {"repeat": repeat, "error": "judge_call_budget_exhausted"}
    payload = {
        "question": question,
        "canonicalAnswer": canonical,
        "acceptableAliases": aliases,
        "candidateAnswer": candidate,
    }
    prompt = (
        "You are a strict semantic equivalence grader for an open-response benchmark. "
        "Decide whether the candidate conveys the same answer required by the question as the canonical answer. "
        "Reject answers with a wrong subject, object, polarity, causal direction, quantity, condition, exception, or missing critical fact. "
        "Do not require identical wording. Do not infer correctness from shared keywords alone. "
        "The payload intentionally contains no multiple-choice distractors. "
        "Return exactly one JSON object with keys equivalent (boolean), contradiction (boolean), "
        "missingCriticalFacts (array of strings), and reason (short string).\n\n"
        f"PRIVATE_GRADING_PAYLOAD_JSON:\n{json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n"
        f"INDEPENDENT_REPEAT: {repeat}"
    )
    started = time.monotonic()
    trace: dict[str, Any] = {}
    try:
        raw = str(judge_client.complete([{"role": "user", "content": prompt}], model=judge_model) or "")
        trace = _consume_judge_trace(judge_client)
        trace_audit = _audit_closed_judge_trace(trace)
        if not trace_audit["passed"]:
            raise ValueError("semantic_judge_closed_tool_trace_failed:" + ",".join(trace_audit["violations"]))
        parsed = _parse_judge_json(raw)
        parsed["repeat"] = repeat
        parsed["policyVersion"] = SEMANTIC_JUDGE_POLICY_VERSION
        parsed["semanticInputSha256"] = semantic_input_sha256
        parsed["judgeModel"] = judge_model
        parsed["elapsedSec"] = round(time.monotonic() - started, 3)
        parsed["rawPreview"] = raw[:1200]
        parsed["modelTrace"] = trace
        parsed["closedToolTraceAudit"] = trace_audit
        return parsed
    except Exception as exc:
        if not trace:
            trace = _consume_judge_trace(judge_client)
        trace_audit = _audit_closed_judge_trace(trace)
        return {
            "repeat": repeat,
            "elapsedSec": round(time.monotonic() - started, 3),
            "error": str(exc)[:500],
            "modelTrace": trace,
            "closedToolTraceAudit": trace_audit,
        }


def _consume_judge_trace(judge_client: Any) -> dict[str, Any]:
    consume = getattr(judge_client, "consume_last_call_trace", None)
    trace = consume() if callable(consume) else None
    return trace if isinstance(trace, dict) else {}


def _audit_closed_judge_trace(trace: dict[str, Any]) -> dict[str, Any]:
    violations: list[str] = []
    if str(trace.get("provider") or "") not in {"codex_exec", "openai_codex_exec"}:
        violations.append("judge_trace_provider_not_codex_exec")
    if str(trace.get("status") or "") != "completed":
        violations.append("judge_trace_not_completed")
    if int(trace.get("codexJsonlEventCount") or 0) <= 0:
        violations.append("judge_trace_missing_jsonl_events")
    if int(trace.get("codexJsonlInvalidLineCount") or 0) != 0:
        violations.append("judge_trace_invalid_jsonl")
    if trace.get("webSearchEnabled") is not False:
        violations.append("judge_web_search_not_proven_disabled")
    if trace.get("domainEvidenceMcpEnabled") is not False:
        violations.append("judge_domain_mcp_not_proven_disabled")
    if trace.get("agentWorkspaceEnabled") is not False:
        violations.append("judge_workspace_not_proven_disabled")
    for key, label in (
        ("webSearchEvents", "judge_web_search_event_present"),
        ("commandExecutionEvents", "judge_command_event_present"),
        ("mcpToolEvents", "judge_mcp_event_present"),
        ("skillEvents", "judge_skill_event_present"),
    ):
        if trace.get(key) != []:
            violations.append(label)
    usage = trace.get("tokenUsage") if isinstance(trace.get("tokenUsage"), dict) else {}
    if int(usage.get("totalTokens") or 0) <= 0:
        violations.append("judge_trace_missing_positive_token_usage")
    return {
        "policy": "closed_codex_jsonl_no_web_shell_mcp_skill_v1",
        "passed": not violations,
        "violations": violations,
    }


def _parse_judge_json(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if text.startswith("```") and text.endswith("```"):
        text = "\n".join(text.splitlines()[1:-1]).strip()
    payload = json.loads(text)
    required_keys = {"equivalent", "contradiction", "missingCriticalFacts", "reason"}
    if not isinstance(payload, dict) or set(payload) != required_keys:
        raise ValueError("judge response must contain exactly the required keys")
    if not isinstance(payload.get("equivalent"), bool) or not isinstance(payload.get("contradiction"), bool):
        raise ValueError("judge response verdict fields must be boolean")
    if not isinstance(payload.get("missingCriticalFacts"), list) or not all(
        isinstance(value, str) for value in payload["missingCriticalFacts"]
    ):
        raise ValueError("judge response missingCriticalFacts must be an array of strings")
    if not isinstance(payload.get("reason"), str) or not payload["reason"].strip():
        raise ValueError("judge response reason must be a nonempty string")
    if payload["equivalent"] is True and (
        payload["contradiction"] is True or any(value.strip() for value in payload["missingCriticalFacts"])
    ):
        raise ValueError("judge response is internally inconsistent")
    return {
        "equivalent": payload["equivalent"],
        "contradiction": payload["contradiction"],
        "missingCriticalFacts": [value for value in payload["missingCriticalFacts"] if value],
        "reason": payload["reason"][:500],
    }


def _consensus_reason(valid: list[dict[str, Any]]) -> str:
    reasons = [str(item.get("reason") or "").strip() for item in valid if str(item.get("reason") or "").strip()]
    return " | ".join(reasons[:3])[:1000] or "semantic judges agreed"


def score_run(
    *,
    public_manifest: dict[str, Any],
    private_manifest: dict[str, Any],
    results_dir: Path,
    additional_results_dirs: list[Path] | None = None,
    judge_client: Any | None = None,
    judge_model: str = "",
    maximum_judge_calls: int = 0,
    max_cases: int = 0,
    case_ids: list[str] | None = None,
    resource_gate_snapshot: dict[str, Any] | None = None,
    resumed_cases: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    result_directories = [Path(results_dir), *[Path(value) for value in additional_results_dirs or []]]
    public_by_id = {
        str(case.get("id") or ""): case
        for case in public_manifest.get("cases", [])
        if isinstance(case, dict) and case.get("id")
    }
    answer_specs = [item for item in private_manifest.get("answers", []) if isinstance(item, dict) and item.get("caseId")]
    allowed = {str(value) for value in case_ids or [] if str(value)}
    if allowed:
        answer_specs = [item for item in answer_specs if str(item.get("caseId") or "") in allowed]
    excluded_rewrite_cases = sum(
        1
        for item in answer_specs
        if str(item.get("conversionStatus") or "ready_hide_options") not in OFFICIAL_CONVERSION_STATUSES
    )
    answer_specs = [
        item
        for item in answer_specs
        if str(item.get("conversionStatus") or "ready_hide_options") in OFFICIAL_CONVERSION_STATUSES
    ]
    if max_cases > 0:
        answer_specs = answer_specs[:max_cases]
    budget = JudgeBudget(maximum_judge_calls)
    cases: list[dict[str, Any]] = []
    for spec in answer_specs:
        case_id = str(spec.get("caseId") or "")
        matching_paths = [directory / f"{case_id}.json" for directory in result_directories]
        matching_paths = [path for path in matching_paths if path.exists()]
        if len(matching_paths) > 1:
            raise ValueError(
                f"duplicate result artifact for {case_id}: "
                + ", ".join(str(path) for path in matching_paths)
            )
        result_path = matching_paths[0] if matching_paths else result_directories[0] / f"{case_id}.json"
        artifact = json.loads(result_path.read_text(encoding="utf-8")) if matching_paths else {}
        candidate = str(artifact.get("prediction") or "")
        public_case = public_by_id.get(case_id, {})
        resumed_case = (resumed_cases or {}).get(case_id, {})
        resumed_result_path = str(resumed_case.get("resultPath") or "")
        if resumed_result_path and Path(resumed_result_path).resolve() != result_path.resolve():
            raise ValueError(f"resumed judge report result path mismatch for {case_id}")
        artifact_error = str(artifact.get("error") or "").strip()
        if artifact_error:
            decision = GradeDecision(
                "unresolved",
                "result_artifact_error",
                "solver artifact was quarantined before grading: " + artifact_error[:500],
            )
        else:
            decision = grade_candidate(
                case_id=case_id,
                question=str(public_case.get("prompt") or ""),
                candidate=candidate,
                answer_spec=spec,
                judge_client=judge_client,
                judge_model=judge_model,
                judge_budget=budget,
                existing_judge_attempts=resumed_case.get("judgeAttempts", []),
            )
        cases.append(
            {
                "caseId": case_id,
                "verdict": decision.verdict,
                "gradingPath": decision.path,
                "reason": decision.reason,
                "judgeAttempts": list(decision.judge_attempts),
                "resultPath": str(result_path) if matching_paths else "",
            }
        )
    total = len(cases)
    passed = sum(1 for case in cases if case["verdict"] == "pass")
    failed = sum(1 for case in cases if case["verdict"] == "fail")
    unresolved = total - passed - failed
    return {
        "benchmarkId": private_manifest.get("benchmarkId", ""),
        "taskType": "open_response",
        "total": total,
        "passed": passed,
        "failed": failed,
        "unresolved": unresolved,
        "excludedSemanticRewriteCases": excluded_rewrite_cases,
        "accuracy": (passed / total) if total else 0.0,
        "judgeModel": judge_model,
        "judgeCallsUsed": budget.used_calls,
        "judgeCallBudget": budget.maximum_calls,
        "resourceGateAtStart": resource_gate_snapshot,
        "resultDirectories": [str(path) for path in result_directories],
        "cases": cases,
    }


def validate_single_case_judge_swap_override(
    *,
    requested: bool,
    judge_model: str,
    case_ids: list[str],
    max_cases: int,
    max_judge_calls: int,
    resume_judge_report: bool = False,
) -> None:
    if not requested:
        return
    if not str(judge_model).strip():
        raise ValueError("judge existing-swap override requires --judge-model")
    unique_case_ids = {str(value).strip() for value in case_ids if str(value).strip()}
    if len(unique_case_ids) != 1:
        raise ValueError("judge existing-swap override requires exactly one --case-id")
    if int(max_cases) not in {0, 1}:
        raise ValueError("judge existing-swap override requires --max-cases 1 or omission")
    allowed_budgets = {1, 2, 3} if resume_judge_report else {2, 3}
    if int(max_judge_calls) not in allowed_budgets:
        expected = "1, 2, or 3" if resume_judge_report else "2 or 3"
        raise ValueError(f"judge existing-swap override requires --max-judge-calls {expected}")


def live_judge_required(*, judge_model: str, max_judge_calls: int) -> bool:
    return bool(str(judge_model or "").strip()) and int(max_judge_calls) > 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Score choice-hidden open responses using deterministic gates and an optional semantic judge.")
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--additional-results-dir", action="append", type=Path, default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--judge-model", default="")
    parser.add_argument("--judge-reasoning-effort", default="low")
    parser.add_argument("--judge-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--codex-home", action="append", type=Path, default=[])
    parser.add_argument("--discover-codex-home-root", type=Path)
    parser.add_argument("--judge-pool-state", type=Path)
    parser.add_argument(
        "--resume-judge-report",
        action="append",
        type=Path,
        default=[],
        help="Reuse valid per-case semantic attempts from a prior score report; only missing consensus calls are made.",
    )
    parser.add_argument("--max-judge-calls", type=int, default=0)
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument(
        "--allow-existing-swap-single-task",
        action="store_true",
        help="User-authorized one-case semantic grading only; calls remain sequential and the resource snapshot is persisted.",
    )
    args = parser.parse_args()
    try:
        validate_single_case_judge_swap_override(
            requested=args.allow_existing_swap_single_task,
            judge_model=args.judge_model,
            case_ids=args.case_id,
            max_cases=args.max_cases,
            max_judge_calls=args.max_judge_calls,
            resume_judge_report=bool(args.resume_judge_report),
        )
    except ValueError as exc:
        parser.error(str(exc))
    needs_live_judge = live_judge_required(
        judge_model=args.judge_model,
        max_judge_calls=args.max_judge_calls,
    )
    if needs_live_judge and not heavy_cli_allowed(
        allow_existing_swap_single_task=args.allow_existing_swap_single_task,
    ):
        return 2
    resource_gate_snapshot = (
        collect_resource_snapshot(
            allow_existing_swap_single_task=args.allow_existing_swap_single_task,
        )
        if needs_live_judge
        else None
    )
    public = json.loads(args.public.read_text(encoding="utf-8"))
    private = json.loads(args.private.read_text(encoding="utf-8"))
    resumed_cases: dict[str, dict[str, Any]] = {}
    for resume_report_path in args.resume_judge_report:
        resumed_report = json.loads(resume_report_path.read_text(encoding="utf-8"))
        if resumed_report.get("benchmarkId") != private.get("benchmarkId"):
            parser.error("--resume-judge-report benchmarkId does not match --private")
        resumed_model = str(resumed_report.get("judgeModel") or "")
        if args.judge_model and resumed_model and resumed_model != args.judge_model:
            parser.error("--resume-judge-report judgeModel does not match --judge-model")
        for case in resumed_report.get("cases", []):
            if not isinstance(case, dict) or not case.get("caseId"):
                continue
            case_id = str(case["caseId"])
            if case_id in resumed_cases:
                parser.error(f"duplicate resumed judge case: {case_id}")
            resumed_cases[case_id] = case
    judge_client = None
    if needs_live_judge:
        client_options = {
            "default_model": args.judge_model,
            "timeout_seconds": min(600.0, max(1.0, float(args.judge_timeout_seconds))),
            "reasoning_effort": args.judge_reasoning_effort,
            "verbosity": "low",
            "web_search_enabled": False,
        }
        pool_paths = resolve_codex_home_paths(args.codex_home, args.discover_codex_home_root)
        if pool_paths:
            judge_client = CodexHomeFailoverClient(
                homes=load_unique_homes(pool_paths),
                state_path=args.judge_pool_state,
                **client_options,
            )
        else:
            judge_client = CodexExecLLMClient(
                max_attempts=2,
                worker_threads=1,
                **client_options,
            )
    report = score_run(
        public_manifest=public,
        private_manifest=private,
        results_dir=args.results_dir,
        additional_results_dirs=args.additional_results_dir,
        judge_client=judge_client,
        judge_model=args.judge_model,
        maximum_judge_calls=args.max_judge_calls,
        max_cases=args.max_cases,
        case_ids=args.case_id,
        resource_gate_snapshot=resource_gate_snapshot,
        resumed_cases=resumed_cases,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
