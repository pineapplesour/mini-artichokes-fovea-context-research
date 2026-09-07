from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import threading
import time
from pathlib import Path

from tools import run_durable_benchmark


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _manifest(*, legal: bool = False) -> dict:
    if legal:
        return {
            "schemaVersion": 1,
            "benchmarkId": "legal.fixture.v1",
            "taskType": "legal_retrieval_answer",
            "product": "fixture",
            "cases": [
                {
                    "id": "case1",
                    "variants": [
                        {"id": "v1", "query": "first"},
                        {"id": "v2", "query": "second"},
                    ],
                }
            ],
        }
    return {
        "schemaVersion": 1,
        "benchmarkId": "mcq.fixture.v1",
        "taskType": "mcq",
        "product": "fixture",
        "cases": [
            {"id": "q1", "prompt": "one\n1. a\n2. b"},
            {"id": "q2", "prompt": "two\n1. a\n2. b"},
        ],
    }


def _spec(tmp_path: Path, *, settings: dict | None = None) -> Path:
    public_path = tmp_path / "public.json"
    output_dir = tmp_path / "out"
    _write_json(public_path, _manifest())
    spec_path = tmp_path / "durable-spec.json"
    _write_json(
        spec_path,
        {
            "schemaVersion": 1,
            "arm": "direct",
            "publicPath": str(public_path),
            "outputDir": str(output_dir),
            "settings": settings or {"model": "fixture-model", "timeoutSeconds": 30},
            "operational": {"pollSeconds": 0.02, "maxAttempts": 2},
        },
    )
    return spec_path


def _fake_runner(tmp_path: Path) -> Path:
    script = tmp_path / "fake_runner.py"
    script.write_text(
        """
import json
import sys
import time
from pathlib import Path

output_dir = Path(sys.argv[1])
case_id = sys.argv[2]
sleep_seconds = float(sys.argv[3])
fail_once = sys.argv[4] == "1"
attempt_file = output_dir / "attempts" / f"{case_id}.txt"
attempt_file.parent.mkdir(parents=True, exist_ok=True)
attempt = int(attempt_file.read_text() if attempt_file.exists() else "0") + 1
attempt_file.write_text(str(attempt))
time.sleep(sleep_seconds)
result = output_dir / "results" / f"{case_id}.json"
result.parent.mkdir(parents=True, exist_ok=True)
if fail_once and attempt == 1:
    result.write_text("{partial")
    raise SystemExit(7)
result.write_text(json.dumps({"id": case_id, "caseId": case_id, "prediction": "1", "error": ""}))
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return script


def _attested_universal_spec(tmp_path: Path, *, expected_sha256: str | None = None) -> tuple[Path, Path]:
    public_path = tmp_path / "public.json"
    output_dir = tmp_path / "out"
    db_path = tmp_path / "corpus.sqlite3"
    _write_json(public_path, _manifest())
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE precedents (canonical_id TEXT PRIMARY KEY, full_text TEXT NOT NULL)")
        conn.execute("INSERT INTO precedents VALUES ('doc.fixture.1', 'fixture evidence')")
    digest = hashlib.sha256(db_path.read_bytes()).hexdigest()
    spec_path = tmp_path / "durable-spec.json"
    _write_json(
        spec_path,
        {
            "schemaVersion": 1,
            "arm": "universal",
            "publicPath": str(public_path),
            "outputDir": str(output_dir),
            "dbPath": str(db_path),
            "databaseAttestation": {
                "required": True,
                "expectedSha256": expected_sha256 or digest,
                "expectedSizeBytes": db_path.stat().st_size,
            },
            "settings": {"model": "fixture-model", "candidateLimit": 4, "evidenceLimit": 2},
            "operational": {"pollSeconds": 0.02, "maxAttempts": 2},
        },
    )
    return spec_path, output_dir


def test_expected_artifacts_cover_all_legal_variants() -> None:
    units = run_durable_benchmark.case_units(_manifest(legal=True))

    assert units == [{"caseId": "case1", "artifactIds": ["case1__v1", "case1__v2"]}]


def test_custom_runner_template_is_argv_only_and_receives_live_settings(tmp_path: Path) -> None:
    public_path = tmp_path / "public.json"
    output_dir = tmp_path / "out"
    _write_json(public_path, _manifest())
    spec_path = tmp_path / "custom-spec.json"
    _write_json(
        spec_path,
        {
            "schemaVersion": 1,
            "arm": "custom",
            "publicPath": str(public_path),
            "outputDir": str(output_dir),
            "settings": {"model": "fixture-model", "threshold": 0.7},
            "runnerCommand": [
                sys.executable,
                "runner.py",
                "--public",
                "{publicPath}",
                "--output-dir",
                "{outputDir}",
                "--case-id",
                "{caseId}",
                "--model",
                "{model}",
                "--threshold",
                "{threshold}",
            ],
        },
    )

    spec = run_durable_benchmark.load_spec(spec_path)
    command = run_durable_benchmark.build_child_command(
        spec,
        "q2",
        {"model": "fixture-model-v2", "threshold": 0.8},
    )

    assert command[0] == sys.executable
    assert command[1] == "runner.py"
    assert command[command.index("--case-id") + 1] == "q2"
    assert command[command.index("--model") + 1] == "fixture-model-v2"
    assert command[command.index("--threshold") + 1] == "0.8"
    assert str(public_path) in command
    assert str(output_dir) in command


def test_completed_results_are_adopted_without_launching_a_child(tmp_path: Path) -> None:
    spec_path = _spec(tmp_path)
    output_dir = tmp_path / "out"
    originals = {}
    for case_id in ("q1", "q2"):
        path = output_dir / "results" / f"{case_id}.json"
        _write_json(path, {"id": case_id, "caseId": case_id, "prediction": "1", "error": ""})
        originals[case_id] = path.read_bytes()

    def forbidden_builder(*_args, **_kwargs):
        raise AssertionError("completed artifacts must not launch a child")

    status = run_durable_benchmark.run_supervisor(spec_path, command_builder=forbidden_builder)

    assert status["actualState"] == "completed"
    assert status["completedCases"] == 2
    assert status["completedArtifacts"] == 2
    assert status["launchedChildCount"] == 0
    assert status["adoptedArtifactCount"] == 2
    assert all((output_dir / "results" / f"{case_id}.json").read_bytes() == originals[case_id] for case_id in originals)


def test_database_attestation_rejects_wrong_snapshot_before_adoption_or_child_launch(tmp_path: Path) -> None:
    spec_path, output_dir = _attested_universal_spec(tmp_path, expected_sha256="0" * 64)
    for case_id in ("q1", "q2"):
        _write_json(
            output_dir / "results" / f"{case_id}.json",
            {"id": case_id, "caseId": case_id, "prediction": "1", "error": ""},
        )

    def forbidden_builder(*_args, **_kwargs):
        raise AssertionError("a DB mismatch must fail before artifact adoption or child launch")

    try:
        run_durable_benchmark.run_supervisor(spec_path, command_builder=forbidden_builder)
    except ValueError as exc:
        assert "database attestation failed" in str(exc)
    else:
        raise AssertionError("wrong DB snapshot was accepted")

    receipt = json.loads((output_dir / "runtime" / "database_attestation.json").read_text())
    assert receipt["passed"] is False
    assert receipt["expectedSha256"] == "0" * 64
    assert receipt["actualSha256"] != receipt["expectedSha256"]
    assert not (output_dir / "runtime" / "events.jsonl").exists()


def test_database_attestation_passes_and_reuses_same_file_receipt_on_resume(
    tmp_path: Path, monkeypatch
) -> None:
    spec_path, output_dir = _attested_universal_spec(tmp_path)
    originals = {}
    for case_id in ("q1", "q2"):
        path = output_dir / "results" / f"{case_id}.json"
        _write_json(path, {"id": case_id, "caseId": case_id, "prediction": "1", "error": ""})
        originals[case_id] = path.read_bytes()

    def forbidden_builder(*_args, **_kwargs):
        raise AssertionError("completed artifacts must not launch a child")

    first = run_durable_benchmark.run_supervisor(spec_path, command_builder=forbidden_builder)
    receipt_path = output_dir / "runtime" / "database_attestation.json"
    first_receipt = receipt_path.read_bytes()
    assert first["actualState"] == "completed"
    assert json.loads(first_receipt)["passed"] is True

    monkeypatch.setattr(
        run_durable_benchmark,
        "_sha256_file",
        lambda _path: (_ for _ in ()).throw(AssertionError("unchanged DB receipt should avoid rehash")),
    )
    second = run_durable_benchmark.run_supervisor(spec_path, command_builder=forbidden_builder)

    assert second["actualState"] == "completed"
    assert receipt_path.read_bytes() == first_receipt
    assert all((output_dir / "results" / f"{case_id}.json").read_bytes() == data for case_id, data in originals.items())


def test_sampled_database_attestation_rejects_mismatch_without_full_file_hash(
    tmp_path: Path, monkeypatch
) -> None:
    spec_path, output_dir = _attested_universal_spec(tmp_path)
    raw = json.loads(spec_path.read_text())
    raw["databaseAttestation"].update(
        {
            "mode": "sampled_sha256_v1",
            "expectedSampleSha256": "0" * 64,
        }
    )
    _write_json(spec_path, raw)
    monkeypatch.setattr(
        run_durable_benchmark,
        "_sha256_file",
        lambda _path: (_ for _ in ()).throw(AssertionError("sampled mode must not read the full DB")),
    )

    try:
        run_durable_benchmark.run_supervisor(spec_path)
    except ValueError as exc:
        assert "database attestation failed" in str(exc)
    else:
        raise AssertionError("wrong sampled DB fingerprint was accepted")

    receipt = json.loads((output_dir / "runtime" / "database_attestation.json").read_text())
    assert receipt["mode"] == "sampled_sha256_v1"
    assert receipt["passed"] is False
    assert receipt["actualSampleSha256"] != receipt["expectedSampleSha256"]
    assert receipt["snapshotSha256"] == raw["databaseAttestation"]["expectedSha256"]


def test_partial_json_is_archived_and_case_is_retried_without_losing_other_results(tmp_path: Path) -> None:
    spec_path = _spec(tmp_path)
    runner = _fake_runner(tmp_path)

    def builder(spec, case_id, _settings):
        fail_once = "1" if case_id == "q1" else "0"
        return [sys.executable, str(runner), str(spec.output_dir), case_id, "0.2", fail_once]

    status = run_durable_benchmark.run_supervisor(spec_path, command_builder=builder)

    assert status["actualState"] == "completed"
    assert status["completedCases"] == 2
    assert status["launchedChildCount"] == 3
    assert status["heartbeatCount"] > 0
    assert json.loads((tmp_path / "out" / "results" / "q1.json").read_text())["prediction"] == "1"
    archived = list((tmp_path / "out" / "runtime" / "failed_results").glob("q1.attempt-1*.json"))
    assert len(archived) == 1
    events = [json.loads(line) for line in (tmp_path / "out" / "runtime" / "events.jsonl").read_text().splitlines()]
    assert any(item["event"] == "artifact_invalid" for item in events)
    assert sum(item["event"] == "case_started" for item in events) == 3


def test_stop_then_resume_and_live_setting_change_apply_at_next_case_boundary(tmp_path: Path) -> None:
    spec_path = _spec(tmp_path)
    runner = _fake_runner(tmp_path)
    output_dir = tmp_path / "out"

    def builder(spec, case_id, settings):
        command_log = output_dir / "command-settings.jsonl"
        with command_log.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"caseId": case_id, "model": settings["model"]}) + "\n")
        return [sys.executable, str(runner), str(spec.output_dir), case_id, "0.5", "0"]

    holder: dict[str, dict] = {}

    def run_first() -> None:
        holder["first"] = run_durable_benchmark.run_supervisor(spec_path, command_builder=builder)

    thread = threading.Thread(target=run_first)
    thread.start()
    deadline = time.time() + 30
    while time.time() < deadline:
        status_path = output_dir / "runtime" / "status.json"
        if status_path.exists():
            current = json.loads(status_path.read_text())
            if current.get("currentCaseId") == "q1" and current.get("childPid"):
                break
        time.sleep(0.01)
    else:
        raise AssertionError("q1 never entered running state")

    run_durable_benchmark.update_control(
        output_dir,
        desired_state="stopped",
        settings_patch={"model": "fixture-model-v2"},
    )
    thread.join(timeout=30)
    assert not thread.is_alive()
    assert holder["first"]["actualState"] == "stopped"
    assert (output_dir / "results" / "q1.json").exists()
    assert not (output_dir / "results" / "q2.json").exists()

    run_durable_benchmark.update_control(output_dir, desired_state="running")
    resumed = run_durable_benchmark.run_supervisor(spec_path, command_builder=builder)

    assert resumed["actualState"] == "completed"
    assert resumed["completedCases"] == 2
    commands = [json.loads(line) for line in (output_dir / "command-settings.jsonl").read_text().splitlines()]
    assert commands == [
        {"caseId": "q1", "model": "fixture-model"},
        {"caseId": "q2", "model": "fixture-model-v2"},
    ]
    epochs = [json.loads(line) for line in (output_dir / "runtime" / "case_epochs.jsonl").read_text().splitlines()]
    by_case = {item["caseId"]: item for item in epochs}
    assert by_case["q1"]["configSha256"] != by_case["q2"]["configSha256"]
    assert by_case["q1"]["settings"]["model"] == "fixture-model"
    assert by_case["q2"]["settings"]["model"] == "fixture-model-v2"


def test_pause_with_current_case_cancel_then_resume_retries_only_unfinished_case(tmp_path: Path) -> None:
    spec_path = _spec(tmp_path, settings={"model": "fixture-model", "timeoutSeconds": 30})
    runner = _fake_runner(tmp_path)
    output_dir = tmp_path / "out"

    def builder(spec, case_id, _settings):
        sleep_seconds = "5" if case_id == "q1" and not (output_dir / "attempts" / "q1.txt").exists() else "0.1"
        return [sys.executable, str(runner), str(spec.output_dir), case_id, sleep_seconds, "0"]

    holder: dict[str, dict] = {}

    def run() -> None:
        holder["result"] = run_durable_benchmark.run_supervisor(spec_path, command_builder=builder)

    thread = threading.Thread(target=run)
    thread.start()
    deadline = time.time() + 30
    while time.time() < deadline:
        status = run_durable_benchmark.read_status(output_dir)
        if status.get("currentCaseId") == "q1" and status.get("childPid"):
            break
        time.sleep(0.02)
    else:
        raise AssertionError("q1 never entered running state")

    run_durable_benchmark.update_control(
        output_dir,
        desired_state="paused",
        cancel_current_case=True,
        operational_patch={"terminationGraceSeconds": 0.1},
    )
    deadline = time.time() + 30
    while time.time() < deadline:
        status = run_durable_benchmark.read_status(output_dir)
        if status.get("actualState") == "paused":
            break
        time.sleep(0.02)
    else:
        raise AssertionError("supervisor never reached paused state")
    assert not (output_dir / "results" / "q1.json").exists()

    run_durable_benchmark.update_control(output_dir, desired_state="running")
    thread.join(timeout=30)
    assert not thread.is_alive()
    assert holder["result"]["actualState"] == "completed"
    assert holder["result"]["completedCases"] == 2
    assert holder["result"]["launchedChildCount"] == 3
    events = [json.loads(line) for line in (output_dir / "runtime" / "events.jsonl").read_text().splitlines()]
    cancelled = [item for item in events if item["event"] == "case_process_exited" and item.get("cancelled")]
    assert len(cancelled) == 1
