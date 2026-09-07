#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.codex_home_failover import load_unique_homes, resolve_codex_home_paths
from tools.rewrite_open_response_prompts import (
    VALIDATOR_VERSION,
    _closed_tool_trace_errors,
    _safe_case_id,
    _validate_stored_artifact,
)


SCHEMA_VERSION = 1
SUPERVISOR_ID = "semantic-rewrite-staging-sequential-v1"
TERMINAL_DISPOSITIONS = {
    "approved",
    "author_semantic_reject",
    "deterministic_reject",
    "review_semantic_reject",
    "policy_reject",
}


@dataclass(frozen=True)
class RewriteTarget:
    benchmark_id: str
    case_id: str
    public_path: Path
    private_path: Path
    manifest: dict[str, Any]
    case: dict[str, Any]
    answer_spec: dict[str, Any]

    @property
    def prompt_chars(self) -> int:
        return len(str(self.case.get("prompt") or ""))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_targets(registry_path: Path) -> tuple[list[RewriteTarget], dict[str, str]]:
    registry_path = registry_path.resolve()
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    base = registry_path.parent
    targets: list[RewriteTarget] = []
    canonical_inputs = {str(registry_path): sha256_file(registry_path)}
    for entry in registry.get("entries", []):
        if not isinstance(entry, dict):
            continue
        public_path = (base / str(entry.get("publicManifest") or "")).resolve()
        private_path = (base / str(entry.get("privateManifest") or "")).resolve()
        manifest = json.loads(public_path.read_text(encoding="utf-8"))
        private = json.loads(private_path.read_text(encoding="utf-8"))
        canonical_inputs[str(public_path)] = sha256_file(public_path)
        canonical_inputs[str(private_path)] = sha256_file(private_path)
        answer_by_id = {
            str(answer.get("caseId") or ""): answer
            for answer in private.get("answers", [])
            if isinstance(answer, dict) and answer.get("caseId")
        }
        for case in manifest.get("cases", []):
            if not isinstance(case, dict):
                continue
            conversion = (
                case.get("metadata", {}).get("openResponseConversion", {})
                if isinstance(case.get("metadata"), dict)
                else {}
            )
            case_id = str(case.get("id") or "")
            if conversion.get("status") != "needs_semantic_rewrite" or case_id not in answer_by_id:
                continue
            targets.append(
                RewriteTarget(
                    benchmark_id=str(entry.get("benchmarkId") or manifest.get("benchmarkId") or ""),
                    case_id=case_id,
                    public_path=public_path,
                    private_path=private_path,
                    manifest=manifest,
                    case=case,
                    answer_spec=answer_by_id[case_id],
                )
            )
    targets.sort(key=lambda target: (target.prompt_chars, target.benchmark_id, target.case_id))
    return targets, dict(sorted(canonical_inputs.items()))


def assert_canonical_inputs(canonical_inputs: dict[str, str]) -> None:
    for raw_path, expected in canonical_inputs.items():
        path = Path(raw_path)
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"canonical input changed during staging: {path}")


def case_output_dir(output_root: Path, case_id: str) -> Path:
    legacy = output_root / f"semantic-rewrite-{case_id}-v1"
    if legacy.exists():
        return legacy
    safe = _safe_case_id(case_id)
    suffix = hashlib.sha256(case_id.encode("utf-8")).hexdigest()[:10]
    return output_root / f"semantic-rewrite-{safe}-{suffix}-v1"


def artifact_path_for(output_dir: Path, case_id: str) -> Path:
    return output_dir / "drafts-private" / f"{_safe_case_id(case_id)}.private.json"


def _trace_is_closed(trace: Any) -> bool:
    return not _closed_tool_trace_errors(trace)


def classify_artifact(artifact: dict[str, Any], *, review_repeats: int) -> str:
    if artifact.get("approved") is True:
        return "approved"
    author = artifact.get("author") if isinstance(artifact.get("author"), dict) else {}
    author_trace = artifact.get("authorTrace")
    reviews = artifact.get("reviews") if isinstance(artifact.get("reviews"), list) else []
    error = str(artifact.get("error") or "")
    deterministic = artifact.get("deterministicErrors") if isinstance(artifact.get("deterministicErrors"), list) else []
    trace_errors = artifact.get("traceErrors") if isinstance(artifact.get("traceErrors"), list) else []
    if trace_errors:
        return "policy_reject"
    if author.get("status") == "reject" and error == "author_rejected" and _trace_is_closed(author_trace):
        return "author_semantic_reject"
    if author.get("status") == "ok" and deterministic and _trace_is_closed(author_trace) and not reviews:
        return "deterministic_reject"
    if (
        author.get("status") == "ok"
        and not error
        and not deterministic
        and _trace_is_closed(author_trace)
        and len(reviews) == int(review_repeats)
        and all(isinstance(review, dict) and _trace_is_closed(review.get("trace")) for review in reviews)
        and any(
            review.get("verdict") != "pass"
            or any(
                review.get(field) is not True
                for field in (
                    "answerableWithoutChoices",
                    "uniquelyTargetsCanonical",
                    "canonicalDirectlyAnswers",
                    "sameKnowledgeTarget",
                    "factuallyPlausible",
                    "noAnswerLeakage",
                )
            )
            for review in reviews
        )
    ):
        return "review_semantic_reject"
    return "infrastructure_failure"


def artifact_record(
    target: RewriteTarget,
    output_dir: Path,
    artifact_path: Path,
    artifact: dict[str, Any],
    *,
    model: str,
    review_repeats: int,
) -> dict[str, Any]:
    _validate_stored_artifact(
        artifact,
        manifest=target.manifest,
        case=target.case,
        answer_spec=target.answer_spec,
        model=model,
        review_repeats=review_repeats,
    )
    disposition = classify_artifact(artifact, review_repeats=review_repeats)
    reviews = artifact.get("reviews") if isinstance(artifact.get("reviews"), list) else []
    traces = []
    if isinstance(artifact.get("authorTrace"), dict) and artifact.get("authorTrace"):
        traces.append(artifact["authorTrace"])
    traces.extend(
        review["trace"]
        for review in reviews
        if isinstance(review, dict) and isinstance(review.get("trace"), dict) and review.get("trace")
    )
    total_tokens = sum(
        int(trace.get("tokenUsage", {}).get("totalTokens") or 0)
        for trace in traces
        if isinstance(trace.get("tokenUsage"), dict)
    )
    return {
        "benchmarkId": target.benchmark_id,
        "caseId": target.case_id,
        "promptChars": target.prompt_chars,
        "publicPromptSha256": hashlib.sha256(str(target.case.get("prompt") or "").encode("utf-8")).hexdigest(),
        "outputDir": str(output_dir.resolve()),
        "artifactPath": str(artifact_path.resolve()),
        "artifactSha256": sha256_file(artifact_path),
        "artifactDigest": str(artifact.get("artifactDigest") or ""),
        "validatorVersion": str(artifact.get("validatorVersion") or ""),
        "disposition": disposition,
        "approved": artifact.get("approved") is True,
        "authorStatus": str(artifact.get("author", {}).get("status") or "") if isinstance(artifact.get("author"), dict) else "",
        "reviewVerdicts": [str(review.get("verdict") or "") for review in reviews if isinstance(review, dict)],
        "reviewReasons": [str(review.get("reason") or "") for review in reviews if isinstance(review, dict)],
        "deterministicErrors": list(artifact.get("deterministicErrors") or []),
        "traceErrors": list(artifact.get("traceErrors") or []),
        "error": str(artifact.get("error") or "")[:1000],
        "modelCalls": len(traces),
        "totalTokens": total_tokens,
        "allTracesClosed": bool(traces) and all(_trace_is_closed(trace) for trace in traces),
        "lastCodexHomeAlias": str(traces[-1].get("codexHomeAlias") or "") if traces else "",
        "recordedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }


def ledger_totals(records: list[dict[str, Any]], target_count: int) -> dict[str, int]:
    terminal = [record for record in records if record.get("disposition") in TERMINAL_DISPOSITIONS]
    return {
        "targetCases": int(target_count),
        "terminalCases": len(terminal),
        "approved": sum(record.get("disposition") == "approved" for record in terminal),
        "rejected": sum(record.get("disposition") != "approved" for record in terminal),
        "infrastructureFailures": sum(record.get("disposition") == "infrastructure_failure" for record in records),
        "pending": int(target_count) - len(terminal),
        "modelCalls": sum(int(record.get("modelCalls") or 0) for record in records),
        "totalTokens": sum(int(record.get("totalTokens") or 0) for record in records),
    }


def build_child_command(
    target: RewriteTarget,
    output_dir: Path,
    *,
    model: str,
    reasoning_effort: str,
    timeout_seconds: float,
    review_repeats: int,
    homes: list[Path],
) -> list[str]:
    command = [
        sys.executable,
        str(REPO_ROOT / "tools" / "rewrite_open_response_prompts.py"),
        "--public",
        str(target.public_path),
        "--private",
        str(target.private_path),
        "--output-dir",
        str(output_dir),
        "--model",
        model,
        "--reasoning-effort",
        reasoning_effort,
        "--timeout-seconds",
        str(timeout_seconds),
        "--case-id",
        target.case_id,
        "--max-cases",
        "1",
        "--max-model-calls",
        str(1 + int(review_repeats)),
        "--review-repeats",
        str(review_repeats),
        "--allow-existing-swap-single-task",
    ]
    for home in homes:
        command.extend(["--codex-home", str(home)])
    return command


def rotated_homes(homes: list[Path], preferred_alias: str) -> list[Path]:
    if not preferred_alias:
        return list(homes)
    matching = [path for path in homes if path.name.lstrip(".") == preferred_alias]
    return matching + [path for path in homes if path not in matching]


def main() -> int:
    parser = argparse.ArgumentParser(description="Resume-safe, exactly-one-case-at-a-time semantic rewrite staging.")
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--codex-home", action="append", type=Path, default=[])
    parser.add_argument("--discover-codex-home-root", type=Path)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--reasoning-effort", default="low")
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--review-repeats", type=int, default=2)
    parser.add_argument("--maximum-new-cases", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.review_repeats not in {1, 2}:
        parser.error("review repeats must be one or two")

    targets, canonical_inputs = load_targets(args.registry)
    if len(targets) != 472:
        raise RuntimeError(f"expected exactly 472 frozen rewrite targets, found {len(targets)}")
    assert_canonical_inputs(canonical_inputs)
    homes = load_unique_homes(resolve_codex_home_paths(args.codex_home, args.discover_codex_home_root))
    home_paths = [home.path for home in homes]
    ledger = {
        "schemaVersion": SCHEMA_VERSION,
        "supervisorId": SUPERVISOR_ID,
        "model": args.model,
        "reasoningEffort": args.reasoning_effort,
        "reviewRepeats": args.review_repeats,
        "canonicalInputs": canonical_inputs,
        "canonicalPromotionPerformed": False,
        "records": [],
    }
    if args.ledger.exists():
        ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
        for field, expected in (
            ("schemaVersion", SCHEMA_VERSION),
            ("supervisorId", SUPERVISOR_ID),
            ("model", args.model),
            ("reviewRepeats", args.review_repeats),
            ("canonicalInputs", canonical_inputs),
        ):
            if ledger.get(field) != expected:
                raise RuntimeError(f"staging ledger mismatch: {field}")
    records_by_id = {
        str(record.get("caseId") or ""): record
        for record in ledger.get("records", [])
        if isinstance(record, dict) and record.get("caseId")
    }
    preferred_alias = str(ledger.get("preferredCodexHomeAlias") or "")
    new_cases = 0
    for index, target in enumerate(targets, start=1):
        assert_canonical_inputs(canonical_inputs)
        output_dir = case_output_dir(args.output_root, target.case_id)
        artifact_path = artifact_path_for(output_dir, target.case_id)
        existing = records_by_id.get(target.case_id)
        if existing and existing.get("disposition") in TERMINAL_DISPOSITIONS and not artifact_path.exists():
            raise RuntimeError(f"terminal ledger record lost its artifact: {target.case_id}")
        if artifact_path.exists():
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            record = artifact_record(
                target,
                output_dir,
                artifact_path,
                artifact,
                model=args.model,
                review_repeats=args.review_repeats,
            )
        elif args.dry_run or (args.maximum_new_cases > 0 and new_cases >= args.maximum_new_cases):
            continue
        else:
            output_dir.parent.mkdir(parents=True, exist_ok=True)
            command = build_child_command(
                target,
                output_dir,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                timeout_seconds=args.timeout_seconds,
                review_repeats=args.review_repeats,
                homes=rotated_homes(home_paths, preferred_alias),
            )
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=(1 + args.review_repeats) * args.timeout_seconds + 90.0,
                check=False,
            )
            new_cases += 1
            if not artifact_path.exists():
                record = {
                    "benchmarkId": target.benchmark_id,
                    "caseId": target.case_id,
                    "promptChars": target.prompt_chars,
                    "outputDir": str(output_dir.resolve()),
                    "artifactPath": str(artifact_path.resolve()),
                    "disposition": "infrastructure_failure",
                    "approved": False,
                    "modelCalls": 0,
                    "totalTokens": 0,
                    "allTracesClosed": False,
                    "error": f"child_exit_{completed.returncode}_without_artifact",
                    "childOutputPreview": completed.stdout[-2000:],
                    "recordedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                }
            else:
                artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
                record = artifact_record(
                    target,
                    output_dir,
                    artifact_path,
                    artifact,
                    model=args.model,
                    review_repeats=args.review_repeats,
                )
                record["childExitCode"] = completed.returncode
                if completed.returncode != 0 and record["disposition"] in TERMINAL_DISPOSITIONS:
                    record["disposition"] = "infrastructure_failure"
                    record["error"] = f"child_exit_{completed.returncode}_after_artifact"

        records_by_id[target.case_id] = record
        if record.get("lastCodexHomeAlias"):
            preferred_alias = str(record["lastCodexHomeAlias"])
        ordered_records = [records_by_id[key] for key in sorted(records_by_id)]
        ledger["records"] = ordered_records
        ledger["preferredCodexHomeAlias"] = preferred_alias
        ledger["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        ledger["totals"] = ledger_totals(ordered_records, len(targets))
        write_json(args.ledger, ledger)
        print(
            json.dumps(
                {
                    "index": index,
                    "caseId": target.case_id,
                    "disposition": record.get("disposition"),
                    "caseTokens": record.get("totalTokens"),
                    "totals": ledger["totals"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        if record.get("disposition") == "infrastructure_failure":
            return 3

    ordered_records = [records_by_id[key] for key in sorted(records_by_id)]
    ledger["records"] = ordered_records
    ledger["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    ledger["totals"] = ledger_totals(ordered_records, len(targets))
    ledger["complete"] = ledger["totals"]["terminalCases"] == len(targets)
    write_json(args.ledger, ledger)
    print(json.dumps({"complete": ledger["complete"], "totals": ledger["totals"]}, ensure_ascii=False), flush=True)
    return 0 if ledger["complete"] or args.dry_run or args.maximum_new_cases > 0 else 4


if __name__ == "__main__":
    raise SystemExit(main())
