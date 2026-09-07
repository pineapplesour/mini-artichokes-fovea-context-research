#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.rewrite_open_response_prompts import (
    VALIDATOR_VERSION,
    _closed_tool_trace_errors,
    _conversion,
    _validate_stored_artifact,
)
from tools.run_semantic_rewrite_staging import (
    TERMINAL_DISPOSITIONS,
    RewriteTarget,
    assert_canonical_inputs,
    classify_artifact,
    load_targets,
)


SCHEMA_VERSION = 1
CONSOLIDATOR_ID = "semantic-rewrite-staging-consolidator-v1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clone_json(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def artifact_traces(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    author_trace = artifact.get("authorTrace")
    if isinstance(author_trace, dict) and author_trace:
        traces.append(author_trace)
    reviews = artifact.get("reviews")
    if isinstance(reviews, list):
        traces.extend(
            review["trace"]
            for review in reviews
            if isinstance(review, dict) and isinstance(review.get("trace"), dict) and review.get("trace")
        )
    return traces


def validate_ledger_shape(
    ledger: dict[str, Any],
    targets: list[RewriteTarget],
) -> dict[str, dict[str, Any]]:
    records = ledger.get("records")
    if not isinstance(records, list):
        raise ValueError("staging ledger records must be a list")
    target_ids = [target.case_id for target in targets]
    record_ids = [str(record.get("caseId") or "") for record in records if isinstance(record, dict)]
    if len(target_ids) != len(set(target_ids)):
        raise ValueError("rewrite target IDs are not unique")
    if len(record_ids) != len(records) or len(record_ids) != len(set(record_ids)):
        raise ValueError("staging ledger record IDs are missing or duplicated")
    if set(record_ids) != set(target_ids):
        missing = sorted(set(target_ids) - set(record_ids))
        extra = sorted(set(record_ids) - set(target_ids))
        raise ValueError(f"staging ledger target mismatch: missing={missing[:5]} extra={extra[:5]}")
    if ledger.get("complete") is not True:
        raise ValueError("staging ledger is not complete")
    totals = ledger.get("totals") if isinstance(ledger.get("totals"), dict) else {}
    if (
        int(totals.get("targetCases") or 0) != len(targets)
        or int(totals.get("terminalCases") or 0) != len(targets)
        or int(totals.get("pending") or 0) != 0
        or int(totals.get("infrastructureFailures") or 0) != 0
    ):
        raise ValueError("staging ledger totals are not terminal and infrastructure-clean")
    if any(record.get("disposition") not in TERMINAL_DISPOSITIONS for record in records):
        raise ValueError("staging ledger contains a non-terminal disposition")
    return {str(record["caseId"]): record for record in records}


def validate_artifacts(
    *,
    targets: list[RewriteTarget],
    records_by_id: dict[str, dict[str, Any]],
    model: str,
    review_repeats: int,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    artifacts: dict[str, dict[str, Any]] = {}
    trace_count = 0
    token_count = 0
    for target in targets:
        record = records_by_id[target.case_id]
        if str(record.get("benchmarkId") or "") != target.benchmark_id:
            raise ValueError(f"benchmark mismatch for {target.case_id}")
        expected_prompt_sha = hashlib.sha256(str(target.case.get("prompt") or "").encode("utf-8")).hexdigest()
        if record.get("publicPromptSha256") != expected_prompt_sha:
            raise ValueError(f"public prompt changed for {target.case_id}")
        artifact_path = Path(str(record.get("artifactPath") or ""))
        if not artifact_path.is_file() or record.get("artifactSha256") != sha256_file(artifact_path):
            raise ValueError(f"artifact file changed for {target.case_id}")
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        if str(artifact.get("caseId") or "") != target.case_id:
            raise ValueError(f"artifact case ID mismatch for {target.case_id}")
        _validate_stored_artifact(
            artifact,
            manifest=target.manifest,
            case=target.case,
            answer_spec=target.answer_spec,
            model=model,
            review_repeats=review_repeats,
        )
        disposition = classify_artifact(artifact, review_repeats=review_repeats)
        if disposition != record.get("disposition"):
            raise ValueError(f"artifact disposition changed for {target.case_id}")
        if bool(artifact.get("approved")) != bool(record.get("approved")):
            raise ValueError(f"artifact approval mismatch for {target.case_id}")
        traces = artifact_traces(artifact)
        trace_errors = [error for trace in traces for error in _closed_tool_trace_errors(trace)]
        if not traces or trace_errors:
            raise ValueError(f"closed-tool trace validation failed for {target.case_id}: {trace_errors}")
        tokens = sum(int(trace["tokenUsage"]["totalTokens"]) for trace in traces)
        if int(record.get("modelCalls") or 0) != len(traces):
            raise ValueError(f"model call count mismatch for {target.case_id}")
        if int(record.get("totalTokens") or 0) != tokens:
            raise ValueError(f"token count mismatch for {target.case_id}")
        if record.get("allTracesClosed") is not True:
            raise ValueError(f"ledger trace closure mismatch for {target.case_id}")
        artifacts[target.case_id] = artifact
        trace_count += len(traces)
        token_count += tokens
    return artifacts, {
        "artifactsValidated": len(artifacts),
        "tracesValidated": trace_count,
        "tokensValidated": token_count,
        "closedToolTraceErrors": 0,
        "webSearchEvents": 0,
        "commandExecutionEvents": 0,
        "mcpToolEvents": 0,
        "invalidCodexJsonlLines": 0,
    }


def promote_pair(
    public_manifest: dict[str, Any],
    private_manifest: dict[str, Any],
    approved_artifacts: dict[str, dict[str, Any]],
    *,
    model: str,
    review_repeats: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, int]]:
    public = clone_json(public_manifest)
    private = clone_json(private_manifest)
    for case in public.get("cases", []):
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("id") or "")
        artifact = approved_artifacts.get(case_id)
        if not artifact:
            continue
        conversion = _conversion(case)
        prior_risks = list(conversion.get("riskReasons", []))
        case["prompt"] = str(artifact["author"]["rewrittenPrompt"])
        conversion["status"] = "ready_semantic_rewrite"
        conversion["riskReasons"] = []
        conversion["semanticRewrite"] = {
            "model": model,
            "validatorVersion": VALIDATOR_VERSION,
            "reviewRepeats": int(review_repeats),
            "inputDigest": artifact["inputDigest"],
            "artifactDigest": artifact["artifactDigest"],
            "resolvedRiskReasons": prior_risks,
        }
    for answer in private.get("answers", []):
        if not isinstance(answer, dict):
            continue
        case_id = str(answer.get("caseId") or "")
        artifact = approved_artifacts.get(case_id)
        if artifact:
            answer["conversionStatus"] = "ready_semantic_rewrite"
            answer["semanticRewriteArtifactDigest"] = artifact["artifactDigest"]
    public_status = {
        str(case.get("id") or ""): str(_conversion(case).get("status") or "")
        for case in public.get("cases", [])
        if isinstance(case, dict)
    }
    private_status = {
        str(answer.get("caseId") or ""): str(answer.get("conversionStatus") or "")
        for answer in private.get("answers", [])
        if isinstance(answer, dict)
    }
    if public_status != private_status:
        raise ValueError(f"public/private conversion status mismatch for {public.get('benchmarkId', '')}")
    counts = Counter(public_status.values())
    audit = public.setdefault("conversionAudit", {})
    audit["statusCounts"] = dict(sorted(counts.items()))
    audit["semanticRewriteModel"] = model
    audit["semanticRewriteValidator"] = VALIDATOR_VERSION
    audit["semanticRewriteReviewRepeats"] = int(review_repeats)
    return public, private, dict(sorted(counts.items()))


def consolidate(*, registry_path: Path, ledger_path: Path, output_dir: Path) -> dict[str, Any]:
    registry_path = registry_path.resolve()
    ledger_path = ledger_path.resolve()
    targets, canonical_inputs = load_targets(registry_path)
    assert_canonical_inputs(canonical_inputs)
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    if ledger.get("canonicalInputs") != canonical_inputs:
        raise ValueError("ledger canonical input hashes do not match current canonical files")
    model = str(ledger.get("model") or "")
    review_repeats = int(ledger.get("reviewRepeats") or 0)
    records_by_id = validate_ledger_shape(ledger, targets)
    artifacts, trace_audit = validate_artifacts(
        targets=targets,
        records_by_id=records_by_id,
        model=model,
        review_repeats=review_repeats,
    )
    approved_artifacts = {case_id: artifact for case_id, artifact in artifacts.items() if artifact.get("approved") is True}
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    base = registry_path.parent
    staged_registry = clone_json(registry)
    staged_hashes: dict[str, str] = {}
    benchmark_counts: dict[str, dict[str, int]] = {}
    for entry in staged_registry.get("entries", []):
        if not isinstance(entry, dict):
            continue
        public_name = str(entry.get("publicManifest") or "")
        private_name = str(entry.get("privateManifest") or "")
        public = json.loads((base / public_name).read_text(encoding="utf-8"))
        private = json.loads((base / private_name).read_text(encoding="utf-8"))
        public_ids = {str(case.get("id") or "") for case in public.get("cases", []) if isinstance(case, dict)}
        pair_approved = {case_id: artifact for case_id, artifact in approved_artifacts.items() if case_id in public_ids}
        staged_public, staged_private, counts = promote_pair(
            public,
            private,
            pair_approved,
            model=model,
            review_repeats=review_repeats,
        )
        public_output = output_dir / public_name
        private_output = output_dir / private_name
        write_json(public_output, staged_public)
        write_json(private_output, staged_private)
        staged_hashes[str(public_output.resolve())] = sha256_file(public_output)
        staged_hashes[str(private_output.resolve())] = sha256_file(private_output)
        entry["statusCounts"] = counts
        benchmark_id = str(entry.get("benchmarkId") or "")
        benchmark_counts[benchmark_id] = {
            "approvedThisRound": len(pair_approved),
            **counts,
        }
    aggregate = Counter()
    for counts in benchmark_counts.values():
        for status in ("ready_hide_options", "ready_semantic_rewrite", "needs_semantic_rewrite"):
            aggregate[status] += int(counts.get(status, 0))
    staged_registry["readyHideOptionsCases"] = int(
        aggregate["ready_hide_options"] + aggregate["ready_semantic_rewrite"]
    )
    staged_registry["needsSemanticRewriteCases"] = int(aggregate["needs_semantic_rewrite"])
    staged_registry["semanticRewriteStaging"] = {
        "consolidatorId": CONSOLIDATOR_ID,
        "sourceRegistrySha256": sha256_file(registry_path),
        "sourceLedgerSha256": sha256_file(ledger_path),
        "model": model,
        "validatorVersion": VALIDATOR_VERSION,
        "reviewRepeats": review_repeats,
        "approvedThisRound": len(approved_artifacts),
        "rejectedThisRound": len(targets) - len(approved_artifacts),
        "canonicalPromotionPerformed": False,
    }
    staged_registry_path = output_dir / "evaluation_registry.open_response.staging.json"
    write_json(staged_registry_path, staged_registry)
    staged_hashes[str(staged_registry_path.resolve())] = sha256_file(staged_registry_path)
    assert_canonical_inputs(canonical_inputs)
    disposition_counts = Counter(str(record.get("disposition") or "") for record in records_by_id.values())
    report = {
        "schemaVersion": SCHEMA_VERSION,
        "consolidatorId": CONSOLIDATOR_ID,
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "complete": True,
        "canonicalPromotionPerformed": False,
        "sourceRegistry": str(registry_path),
        "sourceRegistrySha256": sha256_file(registry_path),
        "sourceLedger": str(ledger_path),
        "sourceLedgerSha256": sha256_file(ledger_path),
        "canonicalInputs": canonical_inputs,
        "targetCases": len(targets),
        "approved": len(approved_artifacts),
        "rejected": len(targets) - len(approved_artifacts),
        "dispositionCounts": dict(sorted(disposition_counts.items())),
        "aggregateStatusCounts": dict(sorted(aggregate.items())),
        "benchmarkCounts": dict(sorted(benchmark_counts.items())),
        "traceAudit": trace_audit,
        "stagedRegistry": str(staged_registry_path.resolve()),
        "stagedFiles": dict(sorted(staged_hashes.items())),
    }
    report_path = output_dir / "consolidation-report.json"
    write_json(report_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and consolidate approved semantic rewrites without canonical promotion.")
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = consolidate(registry_path=args.registry, ledger_path=args.ledger, output_dir=args.output_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
