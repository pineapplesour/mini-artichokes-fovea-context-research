import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

from tools import run_frozen_beta6_benchmark


def _fake_baseline(root: Path):
    package = root / "shared_platform"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "products.py").write_text(
        """
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class ProductProfile:
    key: str
    name: str
    db_path: Path
    db_shape: str
    languages: tuple[str, ...]
    default_language: str
    theme: str
    safety_notice: str
""",
        encoding="utf-8",
    )
    (package / "beta6.py").write_text(
        """
class Client:
    provider = "frozen_fixture_provider"
    default_model = "wrong-default"
    decoding = {"temperature": 0.2}

def default_llm_client_from_env():
    return Client()

class Beta6JobManager:
    def __init__(self, profiles, *, runs_root, llm_client, model, resume_pending_jobs):
        self.model = model

    def answer_sync(self, *, product, query, language, limit, analysis_mode):
        return {
            "answer": "정답: 2",
            "selectedEvidence": [{"file_id": "frozen-doc", "full_text": "frozen evidence"}],
            "sources": [{"id": "frozen-doc"}],
            "beta6SelectedRecords": [{"file_id": "frozen-doc"}],
            "contextPackets": [],
            "selector": {"status": "completed", "candidateIds": ["frozen-doc"]},
            "writer": {"status": "completed", "mode": "llm_writer", "provider": "frozen_fixture_provider", "model": self.model},
            "beta6": {
                "selectorStatus": "completed",
                "selectionSource": "frozen_beta6",
                "candidateCount": 1,
                "selectedCount": 1,
                "writerStatus": "completed",
                "writerProvider": "frozen_fixture_provider",
                "writerModel": self.model,
            },
            "llmUsed": True,
        }

    def shutdown(self, *, wait=False):
        pass
""",
        encoding="utf-8",
    )


def test_worker_imports_frozen_runtime_and_honors_explicit_model(tmp_path):
    baseline_root = tmp_path / "baseline"
    _fake_baseline(baseline_root)
    output_dir = tmp_path / "out"
    plan = {
        "schemaVersion": 1,
        "baseline": {"sourceRoot": str(baseline_root), "commit": "fixture-commit", "tree": "fixture-tree"},
        "benchmarkId": "mcq.fixture.v1",
        "taskType": "mcq",
        "product": {
            "key": "fixture",
            "name": "Fixture",
            "dbPath": str(tmp_path / "db.sqlite3"),
            "dbShape": "precedents",
            "languages": ["ko"],
            "defaultLanguage": "ko",
            "theme": "fixture",
            "safetyNotice": "fixture",
        },
        "model": "shared-model",
        "analysisMode": "fast",
        "limit": 40,
        "outputDir": str(output_dir),
        "tasks": [
            {
                "artifactId": "q1",
                "caseId": "q1",
                "query": "문제\n1. 갑\n2. 을",
                "language": "ko",
                "parser": "mcq",
                "optionIds": ["1", "2"],
            }
        ],
    }
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(Path(run_frozen_beta6_benchmark.__file__)), "--worker-plan", str(plan_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    artifact = json.loads((output_dir / "results" / "q1.json").read_text(encoding="utf-8"))
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert artifact["prediction"] == "2"
    assert artifact["selectionSource"] == "frozen_beta6"
    assert artifact["modelMetadata"]["model"] == "shared-model"
    assert summary["baseline"] == {"commit": "fixture-commit", "tree": "fixture-tree"}


def test_build_tasks_uses_public_manifest_only_and_shared_query_contract(tmp_path):
    public = {
        "benchmarkId": "short.fixture.v1",
        "taskType": "short_answer",
        "product": "fixture",
        "language": "ko",
        "cases": [{"id": "q1", "prompt": "무엇인가?"}],
    }

    tasks = run_frozen_beta6_benchmark.build_tasks(public, max_cases=0, case_ids=None)

    encoded = json.dumps(tasks, ensure_ascii=False)
    assert len(tasks) == 1
    assert tasks[0]["parser"] == "short_answer"
    assert '{"finalAnswer":"정확한 답 문자열"}' in tasks[0]["query"]
    assert "correctAnswer" not in encoded
    assert "correctOptionId" not in encoded


def test_materialize_baseline_includes_frozen_provider_dependencies(tmp_path, monkeypatch):
    def fake_git_value(*args):
        return "fixture-commit" if "^{commit}" in args[-1] else "fixture-tree"

    def fake_run(command, **kwargs):
        assert command[-2:] == ["shared_platform", "scripts"]
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:") as bundle:
            for name, payload in (
                ("shared_platform/beta6.py", b"# frozen beta6\n"),
                ("scripts/legal_evidence_rag.py", b"# frozen provider\n"),
            ):
                member = tarfile.TarInfo(name)
                member.size = len(payload)
                bundle.addfile(member, io.BytesIO(payload))
        return subprocess.CompletedProcess(command, 0, stdout=stream.getvalue(), stderr=b"")

    monkeypatch.setattr(run_frozen_beta6_benchmark, "_git_value", fake_git_value)
    monkeypatch.setattr(run_frozen_beta6_benchmark.subprocess, "run", fake_run)

    target = tmp_path / "materialized"
    metadata = run_frozen_beta6_benchmark.materialize_baseline_source("fixture", target)

    assert metadata["commit"] == "fixture-commit"
    assert (target / "shared_platform" / "beta6.py").exists()
    assert (target / "scripts" / "legal_evidence_rag.py").exists()
