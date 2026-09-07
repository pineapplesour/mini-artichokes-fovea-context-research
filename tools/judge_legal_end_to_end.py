#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared_platform.beta6 import default_llm_client_from_env
from tools.benchmark_provider import create_benchmark_llm_client
from tools.score_unified_benchmarks import load_json_artifacts


def judge_legal_artifacts(
    private_manifest: dict[str, Any],
    artifacts: list[dict[str, Any]],
    *,
    llm_client: Any,
    model: str,
    repetitions: int = 2,
    timeout_seconds: float = 300.0,
) -> dict[str, Any]:
    grader_by_id = {
        str(item.get("graderId") or ""): item
        for item in private_manifest.get("graders") or []
        if isinstance(item, dict) and str(item.get("graderId") or "")
    }
    cases: list[dict[str, Any]] = []
    pass_count = 0
    repeat_count = max(1, int(repetitions))
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        artifact_id = str(artifact.get("id") or artifact.get("caseId") or "")
        grader_id = str(artifact.get("graderId") or artifact.get("caseId") or artifact_id)
        grader = grader_by_id.get(grader_id)
        judgments: list[dict[str, Any]] = []
        failures: list[str] = []
        if grader is None:
            failures.append(f"missing_grader:{grader_id}")
        elif not isinstance(grader.get("semanticJudge"), dict):
            failures.append("semantic_judge_rubric_missing")
        else:
            messages = _judge_messages(grader, artifact)
            for _ in range(repeat_count):
                try:
                    raw = str(
                        llm_client.complete(
                            messages,
                            model=model,
                            timeout_seconds=timeout_seconds,
                        )
                        or ""
                    )
                    parsed = _json_object(raw)
                    judgment_failures = _judgment_failures(grader, parsed)
                    grounding_failures = _grounding_failures(grader, parsed)
                    judgments.append(
                        {
                            "validJson": bool(parsed),
                            "passed": not judgment_failures,
                            "failures": judgment_failures,
                            "groundingPassed": not grounding_failures,
                            "groundingFailures": grounding_failures,
                            "judgment": parsed,
                        }
                    )
                    failures.extend(judgment_failures)
                except Exception as exc:  # noqa: BLE001 - judge failure is a failed evaluation, never a pass.
                    error = f"judge_error:{exc}"
                    judgments.append(
                        {
                            "validJson": False,
                            "passed": False,
                            "failures": [error],
                            "groundingPassed": False,
                            "groundingFailures": [error],
                            "judgment": {},
                        }
                    )
                    failures.append(error)
        passed = bool(len(judgments) == repeat_count and all(item.get("passed") for item in judgments))
        grounding_passed = bool(
            len(judgments) == repeat_count and all(item.get("groundingPassed") for item in judgments)
        )
        if passed:
            pass_count += 1
        cases.append(
            {
                "caseId": str(artifact.get("caseId") or artifact_id),
                "artifactId": artifact_id,
                "graderId": grader_id,
                "passed": passed,
                "groundingPassed": grounding_passed,
                "failures": _unique(failures),
                "judgments": judgments,
            }
        )
    total = len(cases)
    return {
        "benchmarkId": str(private_manifest.get("benchmarkId") or ""),
        "taskType": "legal_retrieval_answer_semantic_judge",
        "repetitions": repeat_count,
        "total": total,
        "passed": pass_count,
        "groundingPassed": sum(1 for item in cases if item["groundingPassed"]),
        "accuracy": (pass_count / total) if total else 0.0,
        "failedArtifactIds": [item["artifactId"] for item in cases if not item["passed"]],
        "judgeModelMetadata": _model_metadata(llm_client, model),
        "cases": cases,
    }


def _judge_messages(grader: dict[str, Any], artifact: dict[str, Any]) -> list[dict[str, str]]:
    rubric = grader.get("semanticJudge") if isinstance(grader.get("semanticJudge"), dict) else {}
    targets = []
    for item in grader.get("primaryTargets") or []:
        if not isinstance(item, dict):
            continue
        target_id = _target_id(item)
        if target_id:
            targets.append(
                {
                    "targetId": target_id,
                    "court": item.get("court", ""),
                    "decisionDate": item.get("decisionDate", ""),
                    "requiredAnswerText": item.get("requiredAnswerText", ""),
                }
            )
    evidence = []
    for key in ("selectedEvidence", "retrievedCases", "sources", "contextPackets"):
        value = artifact.get(key)
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            normalized = {
                "sourceId": item.get("sourceId") or item.get("file_id") or item.get("canonical_id") or item.get("id") or "",
                "title": item.get("title") or item.get("case_name") or "",
                "caseNumber": item.get("caseNumber") or item.get("case_number") or "",
                "citation": item.get("citation") or "",
                "quote": str(
                    item.get("exactQuote")
                    or item.get("full_text")
                    or item.get("fullText")
                    or item.get("text")
                    or ""
                )[:3000],
            }
            if normalized not in evidence:
                evidence.append(normalized)
            if len(evidence) >= 20:
                break
        if len(evidence) >= 20:
            break
    payload = {
        "question": str(artifact.get("query") or ""),
        "answer": str(artifact.get("answer") or artifact.get("answerMarkdown") or ""),
        "requiredAuthorities": targets,
        "authorityPolicy": str(rubric.get("authorityPolicy") or "all_primary"),
        "requiredChecks": [str(item) for item in rubric.get("requiredChecks") or [] if str(item)],
        "rubric": [str(item) for item in rubric.get("rubric") or [] if str(item)],
        "retrievedEvidence": evidence,
    }
    return [
        {
            "role": "system",
            "content": (
                "You are a strict, independent evaluator of a Korean legal answer. The answer is blinded: "
                "do not infer which system wrote it. Mere citation, case-number listing, vague topic overlap, "
                "or a correct conclusion without the required legal reasoning does not count as substantive use. "
                "For each required authority, separately decide whether the answer states that authority's "
                "relevant rule accurately and applies it to the question's facts. Use retrieved excerpts to "
                "check support when present. Return JSON only with this schema: "
                '{"overallPass":true,"checks":{"check_id":true},"authorityUse":['
                '{"targetId":"...","substantivelyUsed":true,"ruleAccurate":true,'
                '"factApplied":true,"evidenceSupported":true}],'
                '"equivalentAuthorityUsed":false,"equivalentAuthorityCitation":"",'
                '"equivalentAuthorityEvidenceSupported":false,'
                '"exactAnswerPresent":true,"reason":"..."}. '
                "Set overallPass false whenever any required item fails."
            ),
        },
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
    ]


def _judgment_failures(grader: dict[str, Any], judgment: dict[str, Any]) -> list[str]:
    if not judgment:
        return ["invalid_judge_json"]
    failures: list[str] = []
    if judgment.get("overallPass") is not True:
        failures.append("judge_overall_pass_false")
    rubric = grader.get("semanticJudge") if isinstance(grader.get("semanticJudge"), dict) else {}
    checks = judgment.get("checks") if isinstance(judgment.get("checks"), dict) else {}
    for check in [str(item) for item in rubric.get("requiredChecks") or [] if str(item)]:
        if checks.get(check) is not True:
            failures.append(f"required_check_failed:{check}")
    authority_by_id = {
        str(item.get("targetId") or ""): item
        for item in judgment.get("authorityUse") or []
        if isinstance(item, dict) and str(item.get("targetId") or "")
    }
    target_ids = [_target_id(item) for item in grader.get("primaryTargets") or [] if isinstance(item, dict)]
    target_ids = [item for item in target_ids if item]
    policy = str(rubric.get("authorityPolicy") or "all_primary")
    passing_authorities = 0
    for target_id in target_ids:
        use = authority_by_id.get(target_id, {})
        passed = (
            use.get("substantivelyUsed") is True
            and use.get("ruleAccurate") is True
            and use.get("factApplied") is True
        )
        if passed:
            passing_authorities += 1
        elif policy == "all_primary":
            failures.append(f"authority_not_substantively_used:{target_id}")
    if policy == "any_primary_or_equivalent":
        equivalent = judgment.get("equivalentAuthorityUsed") is True and bool(
            str(judgment.get("equivalentAuthorityCitation") or "").strip()
        )
        if passing_authorities <= 0 and not equivalent:
            failures.append("no_primary_or_equivalent_authority_substantively_used")
    exact_answer = str(rubric.get("requiredExactAnswer") or "")
    if exact_answer and judgment.get("exactAnswerPresent") is not True:
        failures.append("required_exact_answer_not_verified")
    return _unique(failures)


def _grounding_failures(grader: dict[str, Any], judgment: dict[str, Any]) -> list[str]:
    if not judgment:
        return ["invalid_judge_json"]
    rubric = grader.get("semanticJudge") if isinstance(grader.get("semanticJudge"), dict) else {}
    authority_by_id = {
        str(item.get("targetId") or ""): item
        for item in judgment.get("authorityUse") or []
        if isinstance(item, dict) and str(item.get("targetId") or "")
    }
    target_ids = [_target_id(item) for item in grader.get("primaryTargets") or [] if isinstance(item, dict)]
    target_ids = [item for item in target_ids if item]
    policy = str(rubric.get("authorityPolicy") or "all_primary")
    supported = [
        target_id
        for target_id in target_ids
        if authority_by_id.get(target_id, {}).get("substantivelyUsed") is True
        and authority_by_id.get(target_id, {}).get("evidenceSupported") is True
    ]
    if policy == "all_primary":
        return [f"authority_not_grounded:{target_id}" for target_id in target_ids if target_id not in supported]
    if policy == "any_primary_or_equivalent":
        equivalent_supported = (
            judgment.get("equivalentAuthorityUsed") is True
            and judgment.get("equivalentAuthorityEvidenceSupported") is True
            and bool(str(judgment.get("equivalentAuthorityCitation") or "").strip())
        )
        if not supported and not equivalent_supported:
            return ["no_primary_or_equivalent_authority_grounded"]
    return []


def _target_id(target: dict[str, Any]) -> str:
    for key in ("caseNumber", "fileName", "sourceId", "canonicalId", "id"):
        value = str(target.get(key) or "").strip()
        if value:
            return value
    return ""


def _json_object(value: str) -> dict[str, Any]:
    text = str(value or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _model_metadata(client: Any, model: str) -> dict[str, Any]:
    decoding = getattr(client, "decoding", None)
    if not isinstance(decoding, dict):
        decoding = {}
        for name in ("temperature", "top_p", "top_k", "max_tokens", "thinking_level"):
            if hasattr(client, name):
                value = getattr(client, name)
                if value not in (None, ""):
                    decoding[name] = value
    return {
        "provider": str(getattr(client, "provider", "custom_llm") or "custom_llm"),
        "model": str(model or getattr(client, "default_model", "") or ""),
        "decoding": {str(key): value for key, value in sorted(decoding.items())},
    }


def _unique(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        if value and value not in out:
            out.append(value)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Semantically judge legal benchmark answers with a private rubric.")
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    private = json.loads(args.private.read_text(encoding="utf-8"))
    client = create_benchmark_llm_client(
        model=args.model,
        fallback_factory=default_llm_client_from_env,
    )
    if client is None:
        raise SystemExit("no LLM client configured")
    report = judge_legal_artifacts(
        private,
        load_json_artifacts(args.results_dir),
        llm_client=client,
        model=args.model,
        repetitions=args.repetitions,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["passed"] == report["total"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
