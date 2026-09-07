from __future__ import annotations

import hashlib
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INVENTORY = REPO_ROOT / "docs/research/native_codex_question_identity_inventory_20260720.json"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_native_codex_question_inventory_resolves_every_frozen_question_identity():
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    benchmark_rows = inventory["benchmarkQuestions"]
    synthetic_rows = inventory["syntheticPublicQuestions"]

    assert inventory["overallPassed"] is True
    assert len(benchmark_rows) == inventory["benchmarkQuestionCount"] == 8
    assert len(synthetic_rows) == inventory["syntheticPublicQuestionCount"] == 12
    assert len(benchmark_rows) + len(synthetic_rows) == inventory["gateCount"] == 20

    for row in benchmark_rows:
        assert _sha256_file(REPO_ROOT / row["gatePath"]) == row["gateSha256"]
        manifest = json.loads((REPO_ROOT / row["publicManifest"]).read_text(encoding="utf-8"))
        case = next(item for item in manifest["cases"] if item["id"] == row["caseId"])
        if row["variantId"]:
            variant = next(item for item in case["variants"] if item["id"] == row["variantId"])
            public_question = variant["query"]
        else:
            public_question = case["prompt"]
        assert _sha256_text(public_question) == row["questionSha256"]
        assert row["identityMatchesSource"] is True

    for row in synthetic_rows:
        gate_path = REPO_ROOT / row["gatePath"]
        assert _sha256_file(gate_path) == row["gateSha256"]
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
        assert gate["gateId"] == row["gateId"]
        assert _sha256_text(gate["task"]["publicQuestion"]) == row["questionSha256"]
        assert row["identityMatchesSource"] is True
