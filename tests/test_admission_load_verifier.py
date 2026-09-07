import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


def load_admission_verifier():
    path = Path("tools/verify_admission_load.py")
    if not path.exists():
        pytest.fail("tools/verify_admission_load.py is missing")
    spec = importlib.util.spec_from_file_location("verify_admission_load", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_admission_load_verifier_exercises_real_http_backpressure(tmp_path):
    verifier = load_admission_verifier()

    report = verifier.build_report(
        requests=8,
        concurrency=4,
        max_workers=1,
        max_pending_jobs=3,
        retry_after_seconds=19,
        max_p95_ms=5000,
        runs_root=tmp_path / "runs",
    )

    assert report["passes"] is True
    assert report["requests"]["total"] == 8
    assert report["requests"]["accepted"] == 3
    assert report["requests"]["rejected"] == 5
    assert report["requests"]["unexpected"] == 0
    assert report["backpressure"]["allRejectedStructured"] is True
    assert report["backpressure"]["retryAfterSeconds"] == 19
    assert report["artifacts"]["jobRunDirs"] == 3
    assert report["artifacts"]["rejectedJobArtifacts"] == 0
    assert report["latency"]["p95Ms"] <= 5000
    assert report["capacity"]["maxPendingJobs"] == 3
    assert report["capacity"]["saturatedDuringLoad"] is True


def test_admission_load_verifier_exercises_durable_queue_only_admission(tmp_path):
    verifier = load_admission_verifier()

    report = verifier.build_report(
        requests=8,
        concurrency=4,
        max_workers=1,
        max_pending_jobs=8,
        retry_after_seconds=19,
        max_p95_ms=5000,
        runs_root=tmp_path / "runs",
        durable_queue_only=True,
    )

    assert report["passes"] is True
    assert report["mode"] == "durable_queue_only"
    assert report["requests"]["accepted"] == 8
    assert report["requests"]["rejected"] == 0
    assert report["artifacts"]["jobRunDirs"] == 8
    assert report["artifacts"]["queueRows"] == 8
    assert report["artifacts"]["durableQueueOnlyRows"] == 8
    assert report["capacity"]["maxPendingJobs"] == 8


def test_admission_load_verifier_can_drain_durable_queue_only_jobs_with_external_worker(tmp_path):
    verifier = load_admission_verifier()

    report = verifier.build_report(
        requests=8,
        concurrency=4,
        max_workers=1,
        max_pending_jobs=8,
        retry_after_seconds=19,
        max_p95_ms=5000,
        runs_root=tmp_path / "runs",
        durable_queue_only=True,
        drain_with_worker=True,
        worker_count=2,
    )

    assert report["passes"] is True
    assert report["workerDrain"]["enabled"] is True
    assert report["workerDrain"]["resumed"] == 8
    assert report["workerDrain"]["completed"] == 8
    assert report["workerDrain"]["queueRowsCompleted"] == 8
    assert report["artifacts"]["durableQueueOnlyRows"] == 0


def test_admission_load_verifier_counts_temporary_artifacts_before_cleanup():
    verifier = load_admission_verifier()

    report = verifier.build_report(
        requests=4,
        concurrency=2,
        max_workers=1,
        max_pending_jobs=4,
        retry_after_seconds=19,
        max_p95_ms=5000,
        durable_queue_only=True,
    )

    assert report["passes"] is True
    assert report["artifacts"]["jobRunDirs"] == 4
    assert report["artifacts"]["queueRows"] == 4
    assert report["artifacts"]["durableQueueOnlyRows"] == 4


def test_admission_load_verifier_dry_run_declares_non_llm_safety_contract(tmp_path):
    verifier = load_admission_verifier()

    report = verifier.build_report(
        requests=10000,
        concurrency=128,
        max_workers=4,
        max_pending_jobs=64,
        dry_run=True,
        runs_root=tmp_path / "runs",
    )

    assert report["passes"] is True
    assert report["dryRun"] is True
    assert report["safety"]["llmDisabled"] is True
    assert report["safety"]["usesTemporaryCorpus"] is True
    assert report["requests"]["total"] == 10000
    assert report["capacity"]["maxPendingJobs"] == 64
    assert report["expected"]["acceptedAtMost"] == 64
    assert report["expected"]["structured503AtLeast"] == 9936


def test_admission_load_verifier_cli_runs_from_tools_path(tmp_path):
    output = tmp_path / "admission-load.json"

    completed = subprocess.run(
        [
            sys.executable,
            "tools/verify_admission_load.py",
            "--json",
            "--dry-run",
            "--requests",
            "10",
            "--concurrency",
            "2",
            "--max-pending-jobs",
            "3",
            "--output",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert output.exists()
    assert '"passes": true' in completed.stdout
