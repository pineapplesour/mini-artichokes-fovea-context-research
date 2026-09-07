#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = Path("benchmarks/open_response_v2/evaluation_registry.open_response.json")
READY_STATUSES = frozenset({"ready_hide_options", "ready_semantic_rewrite"})
PLAIN_MODES = frozenset({"codex_home_pool_open_response", "codex_native_open_response"})


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _conversion_status(case: dict[str, Any]) -> str:
    metadata = case.get("metadata") if isinstance(case.get("metadata"), dict) else {}
    conversion = (
        metadata.get("openResponseConversion")
        if isinstance(metadata.get("openResponseConversion"), dict)
        else {}
    )
    return str(conversion.get("status") or "")


def _plain_result_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if str(payload.get("mode") or "") not in PLAIN_MODES:
        errors.append("not_plain_open_response_mode")
    if str(payload.get("model") or "") != "gpt-5.6-luna":
        errors.append("not_luna")
    if payload.get("error"):
        errors.append("execution_error")
    if not str(payload.get("prediction") or "").strip():
        errors.append("prediction_missing")
    for field in (
        "publicProductContextEnabled",
        "singlePassSelfVerifyEnabled",
        "domainClassificationSkillEnabled",
        "nativeAgentEnabled",
    ):
        if payload.get(field):
            errors.append(f"{field}_enabled")
    trace = payload.get("modelTrace")
    if not isinstance(trace, dict):
        errors.append("model_trace_missing")
    else:
        if trace.get("provider") != "codex_exec" or trace.get("status") != "completed":
            errors.append("codex_completion_unverified")
        for field in ("webSearchEvents", "commandExecutionEvents", "mcpToolEvents"):
            if not isinstance(trace.get(field), list):
                errors.append(f"{field}_missing")
            elif trace[field]:
                errors.append(f"{field}_nonempty")
    return errors


def _score_evidence(repo_root: Path, relative_path: str) -> dict[str, Any]:
    path = repo_root / relative_path
    score = _read_json(path)
    return {
        "path": relative_path,
        "sha256": _sha256(path),
        "total": int(score.get("total") or 0),
        "passed": int(score.get("passed") or 0),
        "failed": int(score.get("failed") or 0),
        "unresolved": int(score.get("unresolved") or 0),
        "accuracy": float(score.get("accuracy") or 0.0),
    }


def build_inventory(*, repo_root: Path = REPO_ROOT, generated_at: str) -> dict[str, Any]:
    registry_path = repo_root / REGISTRY_PATH
    registry = _read_json(registry_path)
    manifest_root = registry_path.parent
    ready_by_benchmark: dict[str, set[str]] = {}
    manifest_metadata: dict[str, dict[str, Any]] = {}

    for entry in registry.get("entries", []):
        public_path = manifest_root / str(entry["publicManifest"])
        private_path = manifest_root / str(entry["privateManifest"])
        public = _read_json(public_path)
        private = _read_json(private_path)
        public_status = {str(case["id"]): _conversion_status(case) for case in public.get("cases", [])}
        private_status = {
            str(answer["caseId"]): str(answer.get("conversionStatus") or "")
            for answer in private.get("answers", [])
        }
        if public_status != private_status:
            raise ValueError(f"public/private conversion status mismatch: {entry['benchmarkId']}")
        ready_by_benchmark[str(entry["benchmarkId"])] = {
            case_id for case_id, status in public_status.items() if status in READY_STATUSES
        }
        manifest_metadata[str(entry["benchmarkId"])] = {
            "publicPath": public_path.relative_to(repo_root).as_posix(),
            "publicSha256": _sha256(public_path),
            "privatePath": private_path.relative_to(repo_root).as_posix(),
            "privateSha256": _sha256(private_path),
            "statusCounts": dict(sorted(Counter(public_status.values()).items())),
        }

    eligible_paths: dict[tuple[str, str], list[str]] = defaultdict(list)
    for path in sorted((repo_root / "runs/luna-pilot").rglob("*.json")):
        relative = path.relative_to(repo_root).as_posix()
        if "/results/" not in relative or "direct" not in relative.casefold():
            continue
        try:
            payload = _read_json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        benchmark_id = str(payload.get("benchmarkId") or "")
        case_id = str(payload.get("caseId") or payload.get("id") or "")
        if case_id not in ready_by_benchmark.get(benchmark_id, set()):
            continue
        if _plain_result_errors(payload):
            continue
        eligible_paths[(benchmark_id, case_id)].append(relative)

    entries: list[dict[str, Any]] = []
    total_ready = 0
    total_direct = 0
    for entry in registry.get("entries", []):
        benchmark_id = str(entry["benchmarkId"])
        ready_ids = ready_by_benchmark[benchmark_id]
        direct_ids = sorted(
            case_id
            for candidate_benchmark, case_id in eligible_paths
            if candidate_benchmark == benchmark_id
        )
        result_files = [
            {"caseId": case_id, "path": path, "sha256": _sha256(repo_root / path)}
            for case_id in direct_ids
            for path in eligible_paths[(benchmark_id, case_id)]
        ]
        counts = manifest_metadata[benchmark_id]["statusCounts"]
        ready_count = len(ready_ids)
        direct_count = len(direct_ids)
        total_ready += ready_count
        total_direct += direct_count
        entries.append(
            {
                "benchmarkId": benchmark_id,
                "sourceBenchmarkId": entry.get("sourceBenchmarkId", ""),
                "totalConvertedCases": int(entry.get("cases") or 0),
                "readyCases": ready_count,
                "needsSemanticRewriteCases": int(counts.get("needs_semantic_rewrite") or 0),
                "plainDirectCompletedReadyCases": direct_count,
                "readySubsetComplete": direct_count == ready_count,
                "fullConvertedBenchmarkComplete": (
                    direct_count == int(entry.get("cases") or 0)
                    and int(counts.get("needs_semantic_rewrite") or 0) == 0
                ),
                "directCaseIds": direct_ids,
                "resultFiles": result_files,
                **manifest_metadata[benchmark_id],
            }
        )

    buddhist_public = repo_root / "benchmarks/unified/short_answer_buddhist_sangha3_290.public.json"
    buddhist_private = repo_root / "benchmarks/unified/short_answer_buddhist_sangha3_290.private.json"
    inventory = {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "policy": {
            "unit": "unique ready case with a nonempty Luna prediction",
            "plainDirectDefinition": "closed-tool Codex/Luna result: no web, shell, MCP, native agent, domain skill, public product context, or self-review",
            "excluded": [
                "multiple-choice runs",
                "candidate or routed-skill arms",
                "non-ready choice-dependent conversions",
                "custom legal retrieval pilots from official open-response accuracy",
            ],
        },
        "registry": {
            "path": REGISTRY_PATH.as_posix(),
            "sha256": _sha256(registry_path),
            "registeredConvertedCases": int(registry.get("totalConvertedMcqCases") or 0),
            "registeredReadyCases": total_ready,
            "plainDirectCompletedReadyCases": total_direct,
            "plainDirectReadyCoverage": total_direct / total_ready if total_ready else 0.0,
            "allRegisteredReadyCasesExecuted": total_direct == total_ready,
            "allRegisteredConvertedCasesExecuted": all(
                item["fullConvertedBenchmarkComplete"] for item in entries
            ),
        },
        "benchmarks": entries,
        "unregisteredIntendedBenchmarks": [
            {
                "benchmarkId": "short_answer.buddhist.sangha3_290",
                "cases": 290,
                "plainDirectCompletedCases": 0,
                "publicPath": buddhist_public.relative_to(repo_root).as_posix(),
                "publicSha256": _sha256(buddhist_public),
                "privatePath": buddhist_private.relative_to(repo_root).as_posix(),
                "privateSha256": _sha256(buddhist_private),
                "reason": "source exists but is not registered in open_response_v2 and has no plain Codex run",
            }
        ],
        "verifiedScores": {
            "lawReadyOne": _score_evidence(
                repo_root, "runs/luna-pilot/legal-leet2026-q027-direct-v1/score-deterministic.json"
            ),
            "tcmReadySeventeen": _score_evidence(
                repo_root, "runs/luna-pilot/tcm28-direct-valid-additions/score-ready17-final.json"
            ),
            "psychQ009": _score_evidence(
                repo_root, "runs/luna-pilot/psych-q009-direct-v1/score-final.json"
            ),
            "psychQ050": _score_evidence(
                repo_root,
                "runs/luna-pilot/universal-native-skill-generalization-psych-dev-v1-direct/deterministic-score.json",
            ),
            "christianBibleQ001": _score_evidence(
                repo_root,
                "runs/luna-pilot/christian-bible100-q001-direct-v1/score-deterministic.json",
            ),
            "christianBibleQ002": _score_evidence(
                repo_root,
                "runs/luna-pilot/christian-bible100-q002-direct-v1/score-deterministic.json",
            ),
            "christianBibleQ003": _score_evidence(
                repo_root,
                "runs/luna-pilot/christian-bible100-q003-direct-v1/score-deterministic.json",
            ),
        },
        "scoreCaveats": {
            "christianBibleQ004": {
                "executionCountedInCoverage": True,
                "currentDeterministicScore": _score_evidence(
                    repo_root,
                    "runs/luna-pilot/christian-bible100-q004-direct-v1/score-deterministic.json",
                ),
                "legacySemanticScorePath": (
                    "runs/luna-pilot/christian-bible100-q004-direct-v1/score-semantic.json"
                ),
                "legacySemanticScoreSha256": _sha256(
                    repo_root / "runs/luna-pilot/christian-bible100-q004-direct-v1/score-semantic.json"
                ),
                "currentVerifiedPass": None,
                "reason": (
                    "the historical semantic pass used strict-equivalence-consensus-v2 without the current "
                    "closed-trace contract, so the solver execution is frozen but its pass is not promoted"
                ),
            }
        },
        "separatePilots": {
            "suppliedRuleBusinessTax": _score_evidence(
                repo_root, "runs/luna-pilot/calculation5-direct/score.json"
            ),
            "customLegalTen": {
                "summaryPath": "runs/luna-pilot/legal10-direct/summary-final.json",
                "summarySha256": _sha256(repo_root / "runs/luna-pilot/legal10-direct/summary-final.json"),
                "predicted": 10,
                "errors": 0,
                "officialOpenResponseAccuracy": None,
                "reason": "the old score also requires retrieval ranking, which a Direct arm cannot satisfy",
            },
        },
        "conclusion": {
            "allPlainCodexBenchmarksComplete": False,
            "nextMissingLargeSlices": [
                "Christian Bible100 remaining ready 79",
                "Christian Provao2012 ready 78",
                "Islam CISI100 remaining ready 56",
                "Psych remaining ready 223",
                "Buddhist short-answer 290 registration and run",
                "semantic rewrite of remaining 472 registered cases",
            ],
        },
    }
    return inventory


def main() -> int:
    parser = argparse.ArgumentParser(description="Build artifact-backed plain Codex open-response coverage inventory.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--generated-at", required=True)
    args = parser.parse_args()
    payload = build_inventory(generated_at=args.generated_at)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["registry"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
