#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.codex_home_failover import CodexHomeFailoverClient, load_unique_homes, resolve_codex_home_paths
from tools.prompt_identity import canonical_json_sha256
from tools.resource_gate import collect_resource_snapshot
from tools.run_plain_db_only_full_benchmark import (
    FREEZE_ID,
    MODE,
    SCHEMA_VERSION,
    TERMINAL_DISPOSITIONS,
    load_db_batch_plan,
    sha256_file,
    validate_batch_artifact,
    validate_freeze,
    write_json,
)
from tools.run_subject_batch_benchmark import DB_PRODUCT_BY_PUBLIC_PRODUCT
from tools.score_plain_no_db_full_benchmark import (
    MAX_JUDGE_TOKENS,
    TERMINAL_GROUP_DISPOSITIONS,
    collect_unresolved_semantic_rows,
    deterministic_reports,
    finalize_group,
    judge_artifact_digest,
    judge_attempt_errors,
    ledger_totals,
    partition_rows,
    validate_judge_artifact,
    write_partial_judge_artifact,
)
from tools.score_subject_batch_semantic import run_semantic_batch_attempt


SCORER_ID = "plain-db-only-full-closed-consensus-v1"
EXPECTED_READY_CASES = 619


def group_id(*, benchmark_id: str, case_ids: list[str], judge_model: str) -> str:
    return "judgedb-" + canonical_json_sha256(
        {
            "scorerId": SCORER_ID,
            "benchmarkId": benchmark_id,
            "caseIds": case_ids,
            "judgeModel": judge_model,
        }
    )[:20]


def validate_solver_outputs(
    *,
    registry_path: Path,
    freeze_path: Path,
    solver_root: Path,
) -> tuple[dict[str, Any], list[Any]]:
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    batches = validate_freeze(freeze, freeze_path=freeze_path, registry_path=registry_path)
    freeze_sha = sha256_file(freeze_path)
    ledger_path = solver_root / "solver-ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    if ledger.get("complete") is not True or int(ledger.get("totals", {}).get("terminalCases") or 0) != EXPECTED_READY_CASES:
        raise ValueError("database solver ledger is not complete")
    if ledger.get("freezeSha256") != freeze_sha:
        raise ValueError("database solver ledger freeze mismatch")
    records = ledger.get("records") if isinstance(ledger.get("records"), list) else []
    records_by_id = {str(record.get("batchId") or ""): record for record in records if isinstance(record, dict)}
    if len(records_by_id) != len(batches) or len(records_by_id) != len(records):
        raise ValueError("database solver ledger batch coverage mismatch")
    model = str(freeze.get("model") or "")
    result_count = 0
    for batch in batches:
        public_product = str(batch.manifest.get("product") or "").strip().lower()
        db_product = DB_PRODUCT_BY_PUBLIC_PRODUCT[public_product]
        database = freeze["databaseIdentities"][db_product]
        record = records_by_id.get(batch.batch_id)
        if not record or record.get("disposition") not in TERMINAL_DISPOSITIONS:
            raise ValueError(f"database solver batch is not terminal: {batch.batch_id}")
        artifact_path = Path(str(record.get("artifactPath") or ""))
        if not artifact_path.is_file() or record.get("artifactSha256") != sha256_file(artifact_path):
            raise ValueError(f"database solver artifact changed: {batch.batch_id}")
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        validate_batch_artifact(
            artifact,
            batch=batch,
            model=model,
            freeze_sha256=freeze_sha,
            database=database,
            db_product=db_product,
        )
        for case_id in batch.case_ids:
            result_path = solver_root / "results" / f"{case_id}.json"
            if not result_path.is_file():
                raise ValueError(f"database solver result missing: {case_id}")
            result = json.loads(result_path.read_text(encoding="utf-8"))
            expected_error = "" if artifact.get("disposition") == "accepted" else str(artifact.get("disposition") or "")
            if (
                result.get("id") != case_id
                or result.get("caseId") != case_id
                or result.get("benchmarkId") != batch.benchmark_id
                or result.get("mode") != MODE
                or result.get("model") != model
                or result.get("batchId") != batch.batch_id
                or result.get("batchArtifactDigest") != artifact.get("artifactDigest")
                or result.get("prediction") != artifact.get("predictions", {}).get(case_id)
                or str(result.get("error") or "") != expected_error
                or result.get("databaseProduct") != db_product
                or result.get("databaseIdentity") != database
                or result.get("dbOnlyAuditPassed") is not (artifact.get("dbOnlyAudit", {}).get("passed") is True)
            ):
                raise ValueError(f"database solver result changed: {case_id}")
            boundary = result.get("toolAccess") if isinstance(result.get("toolAccess"), dict) else {}
            expected_boundary = {
                "webSearch": False,
                "shellOrCode": False,
                "mcpOtherThanReadOnlySubjectDatabase": False,
                "readOnlySubjectDatabase": True,
                "customSkills": False,
                "universalEngine": False,
                "beta6Engine": False,
            }
            if boundary != expected_boundary:
                raise ValueError(f"database solver result boundary changed: {case_id}")
            result_count += 1
    if result_count != EXPECTED_READY_CASES:
        raise ValueError("database solver result coverage mismatch")
    return ledger, batches


def run_scoring(
    *,
    registry_path: Path,
    freeze_path: Path,
    solver_root: Path,
    score_root: Path,
    explicit_homes: list[Path],
    discovery_root: Path | None,
    maximum_new_groups: int,
    timeout_seconds: float,
    dry_run: bool,
) -> dict[str, Any]:
    solver_ledger, _batches = validate_solver_outputs(
        registry_path=registry_path,
        freeze_path=freeze_path,
        solver_root=solver_root,
    )
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    judge_model = str(freeze.get("model") or "")
    reports = deterministic_reports(
        registry_path=registry_path,
        solver_root=solver_root,
        score_root=score_root,
        persist=not dry_run,
    )
    group_specs: list[dict[str, Any]] = []
    for item in reports:
        public = json.loads(Path(item["publicPath"]).read_text(encoding="utf-8"))
        private = json.loads(Path(item["privatePath"]).read_text(encoding="utf-8"))
        rows = collect_unresolved_semantic_rows(
            deterministic_report=item["report"],
            public_manifest=public,
            private_manifest=private,
            results_dir=solver_root / "results",
        )
        for group_rows in partition_rows(rows):
            case_ids = [str(row["id"]) for row in group_rows]
            group_specs.append(
                {
                    "groupId": group_id(benchmark_id=item["benchmarkId"], case_ids=case_ids, judge_model=judge_model),
                    "benchmarkId": item["benchmarkId"],
                    "rows": group_rows,
                    "deterministic": item["report"],
                }
            )
    score_ledger_path = score_root / "score-ledger.json"
    score_ledger: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "scorerId": SCORER_ID,
        "freezeId": FREEZE_ID,
        "freezeSha256": sha256_file(freeze_path),
        "solverLedgerSha256": sha256_file(solver_root / "solver-ledger.json"),
        "records": [],
    }
    if score_ledger_path.exists():
        score_ledger = json.loads(score_ledger_path.read_text(encoding="utf-8"))
        for field, expected in (
            ("scorerId", SCORER_ID),
            ("freezeSha256", sha256_file(freeze_path)),
            ("solverLedgerSha256", sha256_file(solver_root / "solver-ledger.json")),
        ):
            if score_ledger.get(field) != expected:
                raise ValueError(f"database score ledger mismatch: {field}")
    records_by_id = {
        str(record.get("groupId") or ""): record
        for record in score_ledger.get("records", [])
        if isinstance(record, dict) and record.get("groupId")
    }
    if len(records_by_id) != len(score_ledger.get("records", [])):
        raise ValueError("database score ledger contains duplicate group IDs")
    if not dry_run and not score_ledger.get("resourceGateAtStart"):
        score_ledger["resourceGateAtStart"] = collect_resource_snapshot(allow_existing_swap_single_task=True)
    homes = load_unique_homes(resolve_codex_home_paths(explicit_homes, discovery_root)) if not dry_run else []
    client = None
    if not dry_run:
        client = CodexHomeFailoverClient(
            homes=homes,
            default_model=judge_model,
            timeout_seconds=min(600.0, max(1.0, float(timeout_seconds))),
            reasoning_effort="low",
            verbosity="low",
            web_search_enabled=False,
            calculation_tools_enabled=False,
            domain_evidence_mcp_enabled=False,
            domain_beta6_frontier_enabled=False,
            skill_paths=[],
            agent_workspace_enabled=False,
            state_path=score_root / "judge-pool-state.json",
        )
    new_groups = 0
    for index, spec in enumerate(group_specs, start=1):
        gid = str(spec["groupId"])
        rows = list(spec["rows"])
        rows_by_id = {str(row["id"]): row for row in rows}
        artifact_path = score_root / "judge-groups" / f"{gid}.json"
        record = records_by_id.get(gid)
        if record and record.get("disposition") in TERMINAL_GROUP_DISPOSITIONS:
            if not artifact_path.is_file() or record.get("artifactSha256") != sha256_file(artifact_path):
                raise ValueError(f"database judge group artifact changed: {gid}")
            validate_judge_artifact(
                json.loads(artifact_path.read_text(encoding="utf-8")),
                group_id_value=gid,
                benchmark_id=str(spec["benchmarkId"]),
                rows=rows,
                judge_model=judge_model,
                terminal=True,
            )
            continue
        if dry_run or (maximum_new_groups > 0 and new_groups >= maximum_new_groups):
            continue
        if client is None:
            raise RuntimeError("database judge client is unavailable")
        attempts: list[dict[str, Any]] = []
        if artifact_path.is_file():
            attempts = validate_judge_artifact(
                json.loads(artifact_path.read_text(encoding="utf-8")),
                group_id_value=gid,
                benchmark_id=str(spec["benchmarkId"]),
                rows=rows,
                judge_model=judge_model,
                terminal=False,
            )
        seen_repeats = {int(attempt["repeat"]) for attempt in attempts}
        for repeat in (1, 2):
            if repeat in seen_repeats:
                continue
            attempt = run_semantic_batch_attempt(rows=rows, repeat=repeat, judge_client=client, judge_model=judge_model)
            errors = judge_attempt_errors(attempt, rows_by_id=rows_by_id, judge_model=judge_model)
            if errors:
                raise RuntimeError(f"database judge attempt failed integrity: {gid}: {','.join(errors)}")
            attempts.append(attempt)
            seen_repeats.add(repeat)
            write_partial_judge_artifact(
                artifact_path,
                group_id_value=gid,
                benchmark_id=str(spec["benchmarkId"]),
                case_ids=list(rows_by_id),
                attempts=attempts,
            )
        primary = [attempt for attempt in attempts if int(attempt.get("repeat") or 0) in {1, 2}]
        preliminary = finalize_group(
            deterministic=spec["deterministic"], rows=rows, attempts=primary, judge_model=judge_model
        )
        unresolved_ids = {
            str(case["caseId"])
            for case in preliminary.get("cases", [])
            if case.get("gradingPath") == "semantic_batch_judge_unresolved"
        }
        if unresolved_ids:
            third_rows = [row for row in rows if str(row["id"]) in unresolved_ids]
            existing_third = next((attempt for attempt in attempts if int(attempt.get("repeat") or 0) == 3), None)
            if existing_third is not None:
                if [str(value) for value in existing_third.get("caseIds", [])] != [str(row["id"]) for row in third_rows]:
                    raise ValueError(f"database judge tie-break set changed: {gid}")
            else:
                attempt = run_semantic_batch_attempt(rows=third_rows, repeat=3, judge_client=client, judge_model=judge_model)
                errors = judge_attempt_errors(
                    attempt,
                    rows_by_id={str(row["id"]): row for row in third_rows},
                    judge_model=judge_model,
                )
                if errors:
                    raise RuntimeError(f"database judge tie-break failed integrity: {gid}: {','.join(errors)}")
                attempts.append(attempt)
                write_partial_judge_artifact(
                    artifact_path,
                    group_id_value=gid,
                    benchmark_id=str(spec["benchmarkId"]),
                    case_ids=list(rows_by_id),
                    attempts=attempts,
                )
        elif 3 in seen_repeats:
            raise ValueError(f"database judge group contains unnecessary tie-break: {gid}")
        final = finalize_group(
            deterministic=spec["deterministic"], rows=rows, attempts=attempts, judge_model=judge_model
        )
        disposition = "scored" if int(final.get("unresolved") or 0) == 0 else "judge_unresolved"
        artifact = {
            "schemaVersion": SCHEMA_VERSION,
            "groupId": gid,
            "benchmarkId": spec["benchmarkId"],
            "caseIds": list(rows_by_id),
            "attempts": attempts,
            "final": final,
            "disposition": disposition,
        }
        artifact["artifactDigest"] = judge_artifact_digest(artifact)
        write_json(artifact_path, artifact)
        judge_tokens = sum(
            int(attempt.get("modelTrace", {}).get("tokenUsage", {}).get("totalTokens") or 0) for attempt in attempts
        )
        record = {
            "groupId": gid,
            "benchmarkId": spec["benchmarkId"],
            "caseIds": list(rows_by_id),
            "disposition": disposition,
            "artifactPath": str(artifact_path.resolve()),
            "artifactSha256": sha256_file(artifact_path),
            "artifactDigest": artifact["artifactDigest"],
            "judgeCalls": len(attempts),
            "judgeTokens": judge_tokens,
            "recordedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        records_by_id[gid] = record
        ordered = [records_by_id[key] for key in sorted(records_by_id)]
        score_ledger["records"] = ordered
        score_ledger["totals"] = ledger_totals(ordered, len(group_specs))
        score_ledger["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        write_json(score_ledger_path, score_ledger)
        new_groups += 1
        print(
            json.dumps(
                {
                    "index": index,
                    "groupId": gid,
                    "benchmarkId": spec["benchmarkId"],
                    "cases": len(rows),
                    "disposition": disposition,
                    "passed": final.get("passed"),
                    "failed": final.get("failed"),
                    "unresolved": final.get("unresolved"),
                    "totals": score_ledger["totals"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    ordered = [records_by_id[key] for key in sorted(records_by_id)]
    score_ledger["records"] = ordered
    score_ledger["totals"] = ledger_totals(ordered, len(group_specs))
    score_ledger["complete"] = score_ledger["totals"]["terminalGroups"] == len(group_specs)
    if dry_run:
        score_ledger["resourceGateAtStart"] = score_ledger.get("resourceGateAtStart") or collect_resource_snapshot(
            allow_existing_swap_single_task=True
        )
    else:
        write_json(score_ledger_path, score_ledger)
    if score_ledger["complete"] and not dry_run:
        final_by_benchmark: dict[str, dict[str, Any]] = {}
        for item in reports:
            semantic_by_id: dict[str, dict[str, Any]] = {}
            for record in ordered:
                if record.get("benchmarkId") != item["benchmarkId"]:
                    continue
                artifact = json.loads(Path(record["artifactPath"]).read_text(encoding="utf-8"))
                semantic_by_id.update(
                    {str(case["caseId"]): case for case in artifact.get("final", {}).get("cases", [])}
                )
            cases = [
                semantic_by_id.get(str(case["caseId"]), case)
                for case in item["report"].get("cases", [])
            ]
            total = len(cases)
            passed = sum(case.get("verdict") == "pass" for case in cases)
            failed = sum(case.get("verdict") == "fail" for case in cases)
            report = {
                "schemaVersion": SCHEMA_VERSION,
                "benchmarkId": item["benchmarkId"],
                "total": total,
                "passed": passed,
                "failed": failed,
                "unresolved": total - passed - failed,
                "accuracy": passed / total if total else 0.0,
                "cases": cases,
            }
            output = score_root / "final" / f"{canonical_json_sha256(item['benchmarkId'])[:16]}.json"
            write_json(output, report)
            final_by_benchmark[item["benchmarkId"]] = {
                **report,
                "path": str(output.resolve()),
                "sha256": sha256_file(output),
            }
        aggregate_total = sum(item["total"] for item in final_by_benchmark.values())
        if aggregate_total != EXPECTED_READY_CASES:
            raise ValueError("database final score coverage mismatch")
        aggregate = {
            "schemaVersion": SCHEMA_VERSION,
            "scorerId": SCORER_ID,
            "freezeId": FREEZE_ID,
            "freezeSha256": sha256_file(freeze_path),
            "solverLedgerSha256": sha256_file(solver_root / "solver-ledger.json"),
            "scoreLedgerSha256": sha256_file(score_ledger_path),
            "total": aggregate_total,
            "passed": sum(item["passed"] for item in final_by_benchmark.values()),
            "failed": sum(item["failed"] for item in final_by_benchmark.values()),
            "unresolved": sum(item["unresolved"] for item in final_by_benchmark.values()),
            "byBenchmark": final_by_benchmark,
            "solverTotals": solver_ledger["totals"],
            "judgeTotals": score_ledger["totals"],
        }
        aggregate["accuracy"] = aggregate["passed"] / aggregate_total if aggregate_total else 0.0
        write_json(score_root / "aggregate.json", aggregate)
    return score_ledger


def main() -> int:
    parser = argparse.ArgumentParser(description="Independently score the full optional-DB Plain Codex comparison arm.")
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--solver-root", type=Path, required=True)
    parser.add_argument("--score-root", type=Path, required=True)
    parser.add_argument("--codex-home", type=Path, action="append", default=[])
    parser.add_argument("--discover-codex-home-root", type=Path)
    parser.add_argument("--maximum-new-groups", type=int, default=0)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    ledger = run_scoring(
        registry_path=args.registry,
        freeze_path=args.freeze,
        solver_root=args.solver_root,
        score_root=args.score_root,
        explicit_homes=args.codex_home,
        discovery_root=args.discover_codex_home_root,
        maximum_new_groups=args.maximum_new_groups,
        timeout_seconds=args.timeout_seconds,
        dry_run=args.dry_run,
    )
    print(json.dumps({"complete": ledger.get("complete"), "totals": ledger.get("totals")}, ensure_ascii=False, indent=2))
    return 0 if ledger.get("complete") or args.dry_run or args.maximum_new_groups > 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
