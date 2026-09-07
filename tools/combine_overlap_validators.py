#!/usr/bin/env python3
"""Mechanically intersect two accepted strict-overlap verifier decisions."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.prepare_plain_codex_file_benchmark import canonical_digest, sha256_file
from tools.run_plain_codex_file_agent import verify_frozen_inputs
from tools.validate_overlap_adjudication import DECISION_RE, validate_overlap_adjudication


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            raise ValueError(f"blank JSONL line {line_number}: {path}")
        row = json.loads(raw)
        if not isinstance(row, dict):
            raise ValueError(f"non-object JSONL line {line_number}: {path}")
        rows.append(row)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def verify_receipt(campaign: Path) -> dict[str, Any]:
    receipt_path = campaign / "solver/run_receipt.json"
    receipt = load_json(receipt_path)
    claimed = str(receipt.get("receiptSha256") or "")
    observed = canonical_digest({key: value for key, value in receipt.items() if key != "receiptSha256"})
    if not claimed or claimed != observed:
        raise ValueError(f"receipt self-hash mismatch: {campaign}")
    process = receipt.get("process") if isinstance(receipt.get("process"), dict) else {}
    artifact = receipt.get("artifactValidation") if isinstance(receipt.get("artifactValidation"), dict) else {}
    integrity = receipt.get("inputIntegrity") if isinstance(receipt.get("inputIntegrity"), dict) else {}
    if not (
        receipt.get("status") == "accepted"
        and receipt.get("role") == "solver"
        and receipt.get("semanticModelInvocations") == 1
        and process.get("exitCode") == 0
        and process.get("timedOut") is False
        and artifact.get("passed") is True
        and integrity.get("passed") is True
    ):
        raise ValueError(f"receipt is not an accepted one-call strict verifier: {campaign}")
    return receipt


def valid_switch_ids(campaign: Path, eligible_ids: list[str]) -> list[str]:
    lines = (campaign / "solver/output/decisions.log").read_text(encoding="utf-8").splitlines()
    decisions: list[dict[str, str]] = []
    for line_number, line in enumerate(lines, 1):
        match = DECISION_RE.fullmatch(line)
        if not match:
            raise ValueError(f"invalid decision line {line_number}: {campaign}")
        decisions.append({key: value.strip() for key, value in match.groupdict().items()})
    if [row["id"] for row in decisions] != eligible_ids:
        raise ValueError(f"decision IDs/order do not match frozen eligible IDs: {campaign}")
    return [row["id"] for row in decisions if row["gate"] == "VALID" and row["action"] == "SWITCH"]


def combine(validator_1: Path, validator_2: Path, output_dir: Path) -> dict[str, Any]:
    validator_1 = validator_1.resolve()
    validator_2 = validator_2.resolve()
    output_dir = output_dir.resolve()
    if validator_1 == validator_2:
        raise ValueError("validator campaigns must be distinct")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty combination directory: {output_dir}")

    integrity_1 = verify_frozen_inputs(campaign_dir=validator_1, role="solver")
    integrity_2 = verify_frozen_inputs(campaign_dir=validator_2, role="solver")
    strict_1 = validate_overlap_adjudication(validator_1, write_report=False)
    strict_2 = validate_overlap_adjudication(validator_2, write_report=False)
    if not strict_1.get("passed") or not strict_2.get("passed"):
        raise ValueError("both strict verifier artifacts must pass fail-closed validation")
    freeze_1 = load_json(validator_1 / "solver/freeze.json")
    freeze_2 = load_json(validator_2 / "solver/freeze.json")
    for key in (
        "freezeSha256",
        "questionsSha256",
        "instructionsSha256",
        "expectedIdsSha256",
        "overlapManifestSha256",
        "eligibleIdsSha256",
        "candidateBundleSha256",
        "candidateProvenanceSha256",
    ):
        if freeze_1.get(key) != freeze_2.get(key):
            raise ValueError(f"validator frozen input mismatch for {key}")

    receipt_1 = verify_receipt(validator_1)
    receipt_2 = verify_receipt(validator_2)
    if receipt_1["receiptSha256"] == receipt_2["receiptSha256"]:
        raise ValueError("validator receipts must be distinct")
    trace_1 = validator_1 / "solver/codex_trace.jsonl"
    trace_2 = validator_2 / "solver/codex_trace.jsonl"
    if not trace_1.is_file() or not trace_2.is_file() or sha256_file(trace_1) == sha256_file(trace_2):
        raise ValueError("validator invocation traces must exist and be distinct")

    expected = load_json(validator_1 / "solver/input/expected_ids.json")
    expected_ids = expected.get("ids")
    if not isinstance(expected_ids, list):
        raise ValueError("expected IDs missing")
    manifest = load_jsonl(validator_1 / "solver/input/overlap_manifest.jsonl")
    eligible_ids = [str(row["id"]) for row in manifest if row.get("eligible") is True]
    valid_1 = valid_switch_ids(validator_1, eligible_ids)
    valid_2 = valid_switch_ids(validator_2, eligible_ids)
    intersection_set = set(valid_1) & set(valid_2)
    intersection = [case_id for case_id in eligible_ids if case_id in intersection_set]

    base_rows = load_jsonl(validator_1 / "solver/input/candidates/base.jsonl")
    auxiliary_rows = load_jsonl(validator_1 / "solver/input/candidates/auxiliary_1.jsonl")
    if [row.get("id") for row in base_rows] != expected_ids or [row.get("id") for row in auxiliary_rows] != expected_ids:
        raise ValueError("candidate IDs/order mismatch")
    auxiliary = {str(row["id"]): str(row["finalAnswer"]) for row in auxiliary_rows}
    final_rows = [
        {
            "id": str(row["id"]),
            "finalAnswer": auxiliary[str(row["id"])] if row["id"] in intersection_set else str(row["finalAnswer"]),
        }
        for row in base_rows
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    answers_path = output_dir / "answers.jsonl"
    write_jsonl(answers_path, final_rows)
    report: dict[str, Any] = {
        "schemaVersion": 1,
        "status": "accepted",
        "protocol": "mini_artichokes_two_validator_intersection_v1",
        "combinationRule": "SWITCH iff validator_1 and validator_2 both record VALID+SWITCH; otherwise exact base",
        "frozenInputSha256": freeze_1["freezeSha256"],
        "expectedRows": len(expected_ids),
        "eligibleRows": len(eligible_ids),
        "validator1": {
            "campaign": str(validator_1),
            "receiptSha256": receipt_1["receiptSha256"],
            "traceSha256": sha256_file(trace_1),
            "decisionsSha256": strict_1["decisionsSha256"],
            "validSwitchRows": len(valid_1),
            "validSwitchIdsSha256": canonical_digest(valid_1),
            "inputIntegrity": integrity_1,
        },
        "validator2": {
            "campaign": str(validator_2),
            "receiptSha256": receipt_2["receiptSha256"],
            "traceSha256": sha256_file(trace_2),
            "decisionsSha256": strict_2["decisionsSha256"],
            "validSwitchRows": len(valid_2),
            "validSwitchIdsSha256": canonical_digest(valid_2),
            "inputIntegrity": integrity_2,
        },
        "intersectionRows": len(intersection),
        "intersectionIdsSha256": canonical_digest(intersection),
        "answersSha256": sha256_file(answers_path),
        "implementationSha256": sha256_file(Path(__file__).resolve()),
    }
    report["receiptSha256"] = canonical_digest(report)
    write_json(output_dir / "combination_receipt.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validator-1", type=Path, required=True)
    parser.add_argument("--validator-2", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = combine(args.validator_1, args.validator_2, args.output_dir)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
