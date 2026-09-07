from __future__ import annotations

import json
from pathlib import Path

from tools import build_evidence_arbitration_manifest
from tools import run_evidence_arbitration


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


class FakeClient:
    provider = "fixture_provider"
    default_model = "fixture-model"
    decoding = {"temperature": 0}

    def __init__(self, response: str = "") -> None:
        self.response = response
        self.calls = []

    def complete(self, messages, *, model="", timeout_seconds=None):
        self.calls.append({"messages": messages, "model": model})
        return self.response


def test_manifest_builder_uses_only_public_arm_artifacts_and_keeps_disagreements(tmp_path: Path) -> None:
    direct = tmp_path / "direct"
    universal = tmp_path / "universal"
    _write(
        direct / "q1.json",
        {"id": "q1", "caseId": "q1", "query": "question 1", "prediction": "1", "answer": "정답: 1"},
    )
    _write(
        universal / "q1.json",
        {
            "id": "q1",
            "caseId": "q1",
            "query": "question 1",
            "prediction": "2",
            "answer": "정답: 2",
            "selectedEvidence": [{"sourceId": "doc1", "exactQuote": "support", "title": "source"}],
        },
    )
    _write(direct / "q2.json", {"id": "q2", "caseId": "q2", "query": "question 2", "prediction": "3"})
    _write(universal / "q2.json", {"id": "q2", "caseId": "q2", "query": "question 2", "prediction": "3"})

    manifest = build_evidence_arbitration_manifest.build_manifest(
        direct_results_dir=direct,
        universal_results_dir=universal,
        benchmark_id="arbitration.fixture.v1",
    )

    assert [item["id"] for item in manifest["cases"]] == ["q1"]
    case = manifest["cases"][0]
    assert case["directPrediction"] == "1"
    assert case["universalPrediction"] == "2"
    assert case["evidence"][0]["sourceId"] == "doc1"
    encoded = json.dumps(manifest, ensure_ascii=False).lower()
    assert "correctoptionid" not in encoded
    assert '"gold"' not in encoded


def test_no_evidence_preserves_direct_without_calling_arbiter(tmp_path: Path) -> None:
    public = tmp_path / "public.json"
    _write(
        public,
        {
            "schemaVersion": 1,
            "benchmarkId": "arbitration.fixture.v1",
            "taskType": "evidence_intervention_arbitration",
            "cases": [
                {
                    "id": "q1",
                    "query": "question",
                    "directPrediction": "1",
                    "universalPrediction": "2",
                    "directAnswer": "정답: 1",
                    "universalAnswer": "정답: 2",
                    "evidence": [],
                }
            ],
        },
    )
    client = FakeClient('not called')

    summary = run_evidence_arbitration.run_manifest(
        public_path=public,
        output_dir=tmp_path / "out",
        model="fixture-model",
        llm_client=client,
    )

    artifact = json.loads((tmp_path / "out" / "results" / "q1.json").read_text())
    assert client.calls == []
    assert artifact["decision"] == "direct"
    assert artifact["prediction"] == "1"
    assert artifact["arbiterStatus"] == "structural_no_evidence"
    assert summary["total"] == {"total": 1, "predicted": 1, "errors": 0}


def test_evidence_arbiter_can_override_only_from_supplied_packets(tmp_path: Path) -> None:
    public = tmp_path / "public.json"
    _write(
        public,
        {
            "schemaVersion": 1,
            "benchmarkId": "arbitration.fixture.v1",
            "taskType": "evidence_intervention_arbitration",
            "cases": [
                {
                    "id": "q1",
                    "query": "question\n1. alpha\n2. beta",
                    "directPrediction": "1",
                    "universalPrediction": "2",
                    "directAnswer": "정답: 1",
                    "universalAnswer": "정답: 2",
                    "evidence": [{"sourceId": "doc1", "exactQuote": "beta is explicitly supported"}],
                }
            ],
        },
    )
    client = FakeClient(
        json.dumps(
            {
                "decision": "universal",
                "confidence": "high",
                "priorSupported": False,
                "evidenceAnswerSupported": True,
                "evidenceDiscriminates": True,
                "supportingSourceIds": ["doc1"],
                "rationale": "The packet directly distinguishes beta.",
            }
        )
    )

    run_evidence_arbitration.run_manifest(
        public_path=public,
        output_dir=tmp_path / "out",
        model="fixture-model",
        llm_client=client,
    )

    artifact = json.loads((tmp_path / "out" / "results" / "q1.json").read_text())
    assert artifact["decision"] == "universal"
    assert artifact["prediction"] == "2"
    prompt = json.dumps(client.calls[0]["messages"], ensure_ascii=False)
    assert "beta is explicitly supported" in prompt
    assert "correctOptionId" not in prompt
    assert "gold" not in prompt.lower()
