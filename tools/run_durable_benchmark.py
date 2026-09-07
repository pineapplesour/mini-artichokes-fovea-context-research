#!/usr/bin/env python3
"""Durable, content-neutral one-case supervisor for benchmark runners."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR_NAME = "runtime"
CONTROL_STATES = {"running", "paused", "stopped"}
ARMS = {"direct", "beta6", "universal", "custom"}
SAFE_ENVIRONMENT_KEYS = {
    "RELIGION_LLM_PROVIDER",
    "UNIVERSAL_EVAL_LLM_PROVIDER",
    "UNIVERSAL_EVAL_CODEX_EXECUTABLE",
    "UNIVERSAL_EVAL_CODEX_REASONING_EFFORT",
    "UNIVERSAL_EVAL_CODEX_VERBOSITY",
    "UNIVERSAL_EVAL_CODEX_MAX_ATTEMPTS",
    "UNIVERSAL_EVAL_CODEX_WORKER_THREADS",
    "UNIVERSAL_EVAL_CODEX_WEB_SEARCH",
    "UNIVERSAL_EVAL_CODEX_WEB_SEARCH_REQUIRED",
}
SETTING_KEYS = {
    "direct": {"model", "timeoutSeconds"},
    "beta6": {"model", "baselineRef", "limit", "analysisMode"},
    "universal": {"model", "candidateLimit", "evidenceLimit"},
}
DEFAULT_OPERATIONAL = {
    "pollSeconds": 1.0,
    "maxAttempts": 2,
    "childTimeoutSeconds": 0.0,
    "retryErrorArtifacts": True,
    "terminationGraceSeconds": 10.0,
}


@dataclass(frozen=True)
class DurableSpec:
    path: Path
    arm: str
    public_path: Path
    output_dir: Path
    db_path: Path | None
    settings: dict[str, Any]
    environment: dict[str, str]
    operational: dict[str, Any]
    database_attestation: dict[str, Any]
    runner_command: tuple[str, ...]


CommandBuilder = Callable[[DurableSpec, str, dict[str, Any]], list[str]]


def load_spec(path: Path) -> DurableSpec:
    path = Path(path).resolve()
    raw = _read_json(path)
    arm = str(raw.get("arm") or "").strip().lower().replace("frozen_beta6", "beta6")
    if arm not in ARMS:
        raise ValueError(f"unsupported durable benchmark arm: {arm!r}")
    public_path = _resolved_path(raw.get("publicPath"), relative_to=path.parent)
    output_dir = _resolved_path(raw.get("outputDir"), relative_to=path.parent)
    db_value = raw.get("dbPath")
    db_path = _resolved_path(db_value, relative_to=path.parent) if db_value else None
    if not public_path.is_file():
        raise FileNotFoundError(f"public manifest missing: {public_path}")
    if arm in {"beta6", "universal"} and db_path is None:
        raise ValueError(f"dbPath is required for arm={arm}")
    settings = dict(raw.get("settings") or {})
    environment = {str(key): str(value) for key, value in dict(raw.get("environment") or {}).items()}
    operational = {**DEFAULT_OPERATIONAL, **dict(raw.get("operational") or {})}
    database_attestation = dict(raw.get("databaseAttestation") or {})
    runner_command = tuple(str(item) for item in raw.get("runnerCommand") or [])
    if arm == "custom" and not runner_command:
        raise ValueError("runnerCommand is required for arm=custom")
    if arm != "custom" and runner_command:
        raise ValueError("runnerCommand is only allowed for arm=custom")
    _validate_settings(arm, settings)
    _validate_environment(environment)
    _validate_operational(operational)
    _validate_database_attestation(database_attestation, db_path=db_path)
    return DurableSpec(
        path=path,
        arm=arm,
        public_path=public_path,
        output_dir=output_dir,
        db_path=db_path,
        settings=settings,
        environment=environment,
        operational=operational,
        database_attestation=database_attestation,
        runner_command=runner_command,
    )


def case_units(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    task_type = str(manifest.get("taskType") or "")
    units: list[dict[str, Any]] = []
    for case in manifest.get("cases") or []:
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("id") or "").strip()
        if not case_id:
            continue
        artifact_ids: list[str] = []
        if task_type == "legal_retrieval_answer":
            variants = case.get("variants") if isinstance(case.get("variants"), list) else []
            if not variants and str(case.get("query") or "").strip():
                variants = [{"id": "v1", "query": str(case.get("query") or "")}]
            for variant in variants:
                if not isinstance(variant, dict) or not str(variant.get("query") or "").strip():
                    continue
                variant_id = str(variant.get("id") or "v1").strip() or "v1"
                artifact_ids.append(f"{case_id}__{variant_id}")
        else:
            artifact_ids.append(case_id)
        if artifact_ids:
            units.append({"caseId": case_id, "artifactIds": artifact_ids})
    return units


def update_control(
    output_dir: Path,
    *,
    desired_state: str | None = None,
    settings_patch: dict[str, Any] | None = None,
    environment_patch: dict[str, str] | None = None,
    operational_patch: dict[str, Any] | None = None,
    cancel_current_case: bool | None = None,
) -> dict[str, Any]:
    runtime_dir = Path(output_dir).resolve() / RUNTIME_DIR_NAME
    runtime_dir.mkdir(parents=True, exist_ok=True)
    path = runtime_dir / "control.json"
    control = _control(path)
    if desired_state is not None:
        if desired_state not in CONTROL_STATES:
            raise ValueError(f"invalid desired state: {desired_state}")
        control["desiredState"] = desired_state
    if settings_patch:
        control["settingsPatch"] = {**dict(control.get("settingsPatch") or {}), **settings_patch}
    if environment_patch:
        _validate_environment(environment_patch)
        control["environmentPatch"] = {
            **dict(control.get("environmentPatch") or {}),
            **{str(key): str(value) for key, value in environment_patch.items()},
        }
    if operational_patch:
        merged = {**dict(control.get("operationalPatch") or {}), **operational_patch}
        _validate_operational({**DEFAULT_OPERATIONAL, **merged})
        control["operationalPatch"] = merged
    if cancel_current_case is not None:
        control["cancelCurrentCase"] = bool(cancel_current_case)
    control["revision"] = int(control.get("revision") or 0) + 1
    control["updatedAt"] = _timestamp()
    _atomic_write_json(path, control)
    return control


def read_status(output_dir: Path) -> dict[str, Any]:
    path = Path(output_dir).resolve() / RUNTIME_DIR_NAME / "status.json"
    return _read_json(path) if path.exists() else {"actualState": "not_started", "statusPath": str(path)}


def run_supervisor(
    spec_path: Path,
    *,
    command_builder: CommandBuilder | None = None,
) -> dict[str, Any]:
    spec = load_spec(spec_path)
    manifest = _read_json(spec.public_path)
    units = case_units(manifest)
    if not units:
        raise ValueError(f"manifest has no runnable cases: {spec.public_path}")
    runtime_dir = spec.output_dir / RUNTIME_DIR_NAME
    runtime_dir.mkdir(parents=True, exist_ok=True)
    _persist_runtime_spec(runtime_dir, spec, manifest)
    _attest_database(spec, runtime_dir)
    (spec.output_dir / "results").mkdir(parents=True, exist_ok=True)
    control_path = runtime_dir / "control.json"
    if not control_path.exists():
        _atomic_write_json(control_path, _default_control())
    lock_path = runtime_dir / "supervisor.lock"
    with lock_path.open("a+", encoding="utf-8") as lock_stream:
        try:
            fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f"another supervisor already owns {spec.output_dir}") from exc
        return _run_locked(spec, units, command_builder=command_builder or build_child_command)


def _run_locked(spec: DurableSpec, units: list[dict[str, Any]], *, command_builder: CommandBuilder) -> dict[str, Any]:
    runtime_dir = spec.output_dir / RUNTIME_DIR_NAME
    status_path = runtime_dir / "status.json"
    previous = _read_json(status_path) if status_path.exists() else {}
    counters = {
        "launchedChildCount": int(previous.get("launchedChildCount") or 0),
        "heartbeatCount": int(previous.get("heartbeatCount") or 0),
        "adoptedArtifactCount": int(previous.get("adoptedArtifactCount") or 0),
    }
    _recover_recorded_child(previous, spec.output_dir, runtime_dir)
    builder = command_builder
    started_at = str(previous.get("startedAt") or _timestamp())

    def publish(actual_state: str, **current: Any) -> dict[str, Any]:
        control = _control(runtime_dir / "control.json")
        snapshot = _completion_snapshot(spec.output_dir, units)
        status = {
            "schemaVersion": 1,
            "actualState": actual_state,
            "desiredState": str(control.get("desiredState") or "running"),
            "controlRevision": int(control.get("revision") or 0),
            "arm": spec.arm,
            "benchmarkId": str(_read_json(spec.public_path).get("benchmarkId") or ""),
            "publicPath": str(spec.public_path),
            "outputDir": str(spec.output_dir),
            "startedAt": started_at,
            "updatedAt": _timestamp(),
            **snapshot,
            **counters,
            "currentCaseId": "",
            "currentArtifactIds": [],
            "currentStage": "idle",
            "currentAttempt": 0,
            "childPid": 0,
            "childPgid": 0,
            "childStartToken": "",
            **current,
        }
        # Status is a replaceable live view; durable recovery comes from the fsynced
        # event/attempt/epoch ledgers. Avoid an fsync on every heartbeat.
        _atomic_write_json(status_path, status, sync=False)
        return status

    publish("initializing", currentStage="adopting_existing_results")
    _adopt_preexisting_artifacts(spec, units, runtime_dir, counters)
    publish("initializing", currentStage="existing_results_adopted")
    while True:
        control = _control(runtime_dir / "control.json")
        desired = str(control.get("desiredState") or "running")
        if desired == "stopped":
            status = publish("stopped", currentStage="stopped_at_case_boundary")
            _event(runtime_dir, "supervisor_stopped", completedCases=status["completedCases"])
            return status
        if desired == "paused":
            publish("paused", currentStage="waiting_for_resume")
            time.sleep(_poll_seconds(spec, control))
            continue
        pending = _pending_units(spec.output_dir, units)
        if not pending:
            status = publish("completed", currentStage="all_results_durable", finishedAt=_timestamp())
            _write_durable_summary(spec, status)
            _event(runtime_dir, "supervisor_completed", completedCases=status["completedCases"])
            return status

        unit = pending[0]
        case_id = str(unit["caseId"])
        effective = _effective_configuration(spec, control)
        config_sha = _config_sha(effective)
        epoch = _ensure_config_epoch(runtime_dir, config_sha, effective)
        attempts = _attempts(runtime_dir)
        attempt_key = f"{case_id}\0{config_sha}"
        attempt = int(attempts.get(attempt_key) or 0) + 1
        max_attempts = int(effective["operational"]["maxAttempts"])
        if attempt > max_attempts:
            status = publish(
                "failed",
                currentCaseId=case_id,
                currentArtifactIds=list(unit["artifactIds"]),
                currentStage="attempt_limit_exhausted",
                currentAttempt=attempt - 1,
                configEpoch=epoch,
                configSha256=config_sha,
                failure=f"attempt limit exhausted for {case_id}",
            )
            _event(runtime_dir, "attempt_limit_exhausted", caseId=case_id, configSha256=config_sha)
            return status
        attempts[attempt_key] = attempt
        _atomic_write_json(runtime_dir / "attempts.json", attempts)
        command = builder(spec, case_id, dict(effective["settings"]))
        counters["launchedChildCount"] += 1
        attempt_slug = f"{_safe_name(case_id)}.epoch-{epoch}.attempt-{attempt}"
        stdout_path = runtime_dir / "logs" / f"{attempt_slug}.stdout.log"
        stderr_path = runtime_dir / "logs" / f"{attempt_slug}.stderr.log"
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        child_env = os.environ.copy()
        child_env.update(effective["environment"])
        with stdout_path.open("ab") as stdout_stream, stderr_path.open("ab") as stderr_stream:
            child = subprocess.Popen(
                command,
                cwd=str(REPO_ROOT),
                env=child_env,
                stdout=stdout_stream,
                stderr=stderr_stream,
                start_new_session=True,
            )
            child_pgid = os.getpgid(child.pid)
            child_start_token = _process_start_token(child.pid)
            case_started = time.monotonic()
            _event(
                runtime_dir,
                "case_started",
                caseId=case_id,
                artifactIds=list(unit["artifactIds"]),
                attempt=attempt,
                configEpoch=epoch,
                configSha256=config_sha,
                childPid=child.pid,
                command=_redacted_command(command),
            )
            return_code, cancelled, timed_out = _monitor_child(
                child,
                spec=spec,
                unit=unit,
                attempt=attempt,
                epoch=epoch,
                config_sha=config_sha,
                effective=effective,
                counters=counters,
                publish=publish,
                child_pgid=child_pgid,
                child_start_token=child_start_token,
                started=case_started,
            )
        inspection = _inspect_unit(spec.output_dir, unit)
        _event(
            runtime_dir,
            "case_process_exited",
            caseId=case_id,
            attempt=attempt,
            returnCode=return_code,
            cancelled=cancelled,
            timedOut=timed_out,
            inspection=inspection,
        )
        if inspection["valid"] and not inspection["errorArtifactIds"]:
            _record_case_epoch(runtime_dir, unit, epoch, config_sha, effective, attempt, "completed")
            continue
        if inspection["valid"] and inspection["errorArtifactIds"] and not effective["operational"]["retryErrorArtifacts"]:
            _record_case_epoch(runtime_dir, unit, epoch, config_sha, effective, attempt, "completed_with_error")
            continue
        if attempt < max_attempts:
            _archive_retry_artifacts(spec.output_dir, runtime_dir, unit, attempt, inspection)
            continue
        if inspection["valid"]:
            _record_case_epoch(runtime_dir, unit, epoch, config_sha, effective, attempt, "completed_with_error")
            continue
        status = publish(
            "failed",
            currentCaseId=case_id,
            currentArtifactIds=list(unit["artifactIds"]),
            currentStage="case_not_durable_after_retries",
            currentAttempt=attempt,
            configEpoch=epoch,
            configSha256=config_sha,
            failure=f"case {case_id} produced missing or invalid artifacts",
        )
        return status


def build_child_command(spec: DurableSpec, case_id: str, settings: dict[str, Any]) -> list[str]:
    if spec.arm == "custom":
        substitutions = {
            "publicPath": str(spec.public_path),
            "outputDir": str(spec.output_dir),
            "dbPath": str(spec.db_path or ""),
            "caseId": str(case_id),
            **{str(key): str(value) for key, value in settings.items()},
        }
        try:
            return [item.format_map(substitutions) for item in spec.runner_command]
        except KeyError as exc:
            raise ValueError(f"runnerCommand placeholder has no setting: {exc.args[0]}") from exc
    common = ["--public", str(spec.public_path), "--output-dir", str(spec.output_dir)]
    if spec.arm == "direct":
        return [
            sys.executable,
            str(REPO_ROOT / "tools" / "run_direct_benchmark.py"),
            *common,
            "--model",
            str(settings["model"]),
            "--timeout-seconds",
            str(settings.get("timeoutSeconds", 300)),
            "--case-id",
            case_id,
            "--resume",
        ]
    if spec.arm == "universal":
        return [
            sys.executable,
            str(REPO_ROOT / "tools" / "run_universal_benchmark.py"),
            *common,
            "--db-path",
            str(spec.db_path),
            "--model",
            str(settings["model"]),
            "--candidate-limit",
            str(settings.get("candidateLimit", 40)),
            "--evidence-limit",
            str(settings.get("evidenceLimit", 12)),
            "--case-id",
            case_id,
            "--resume",
        ]
    return [
        sys.executable,
        str(REPO_ROOT / "tools" / "run_frozen_beta6_benchmark.py"),
        *common,
        "--db-path",
        str(spec.db_path),
        "--model",
        str(settings["model"]),
        "--baseline-ref",
        str(settings.get("baselineRef") or "45af71ff7bc6efc0ae03727cdb043bcdec82006e"),
        "--limit",
        str(settings.get("limit", 40)),
        "--analysis-mode",
        str(settings.get("analysisMode", "fast")),
        "--case-id",
        case_id,
        "--resume",
    ]


def _monitor_child(
    child: subprocess.Popen[bytes],
    *,
    spec: DurableSpec,
    unit: dict[str, Any],
    attempt: int,
    epoch: int,
    config_sha: str,
    effective: dict[str, Any],
    counters: dict[str, int],
    publish: Callable[..., dict[str, Any]],
    child_pgid: int,
    child_start_token: str,
    started: float,
) -> tuple[int, bool, bool]:
    cancelled = False
    timed_out = False
    while child.poll() is None:
        control = _control(spec.output_dir / RUNTIME_DIR_NAME / "control.json")
        counters["heartbeatCount"] += 1
        desired = str(control.get("desiredState") or "running")
        state = "running" if desired == "running" else "pausing" if desired == "paused" else "stopping"
        publish(
            state,
            currentCaseId=str(unit["caseId"]),
            currentArtifactIds=list(unit["artifactIds"]),
            currentStage="child_running",
            currentAttempt=attempt,
            childPid=child.pid,
            childPgid=child_pgid,
            childStartToken=child_start_token,
            caseElapsedSeconds=round(time.monotonic() - started, 3),
            configEpoch=epoch,
            configSha256=config_sha,
            effectiveSettings=effective["settings"],
        )
        timeout = float(effective["operational"]["childTimeoutSeconds"])
        if timeout > 0 and time.monotonic() - started >= timeout:
            timed_out = True
            _terminate_process_group(child, child_pgid, float(effective["operational"]["terminationGraceSeconds"]))
            break
        if bool(control.get("cancelCurrentCase")):
            cancelled = True
            _terminate_process_group(child, child_pgid, float(effective["operational"]["terminationGraceSeconds"]))
            _clear_cancel(spec.output_dir / RUNTIME_DIR_NAME / "control.json")
            break
        time.sleep(float(effective["operational"]["pollSeconds"]))
    return int(child.wait()), cancelled, timed_out


def _effective_configuration(spec: DurableSpec, control: dict[str, Any]) -> dict[str, Any]:
    settings = {**spec.settings, **dict(control.get("settingsPatch") or {})}
    environment = {**spec.environment, **dict(control.get("environmentPatch") or {})}
    operational = {
        **spec.operational,
        **dict(control.get("operationalPatch") or {}),
    }
    _validate_settings(spec.arm, settings)
    _validate_environment(environment)
    _validate_operational(operational)
    return {"arm": spec.arm, "settings": settings, "environment": environment, "operational": operational}


def _completion_snapshot(output_dir: Path, units: list[dict[str, Any]]) -> dict[str, Any]:
    inspections = [_inspect_unit(output_dir, unit) for unit in units]
    total_artifacts = sum(len(unit["artifactIds"]) for unit in units)
    completed_artifacts = sum(len(item["validArtifactIds"]) for item in inspections)
    completed_cases = sum(bool(item["valid"]) for item in inspections)
    successful_cases = sum(bool(item["valid"] and not item["errorArtifactIds"]) for item in inspections)
    return {
        "totalCases": len(units),
        "completedCases": completed_cases,
        "successfulCases": successful_cases,
        "pendingCases": len(units) - completed_cases,
        "totalArtifacts": total_artifacts,
        "completedArtifacts": completed_artifacts,
        "errorArtifactCount": sum(len(item["errorArtifactIds"]) for item in inspections),
        "invalidArtifactCount": sum(len(item["invalidArtifactIds"]) for item in inspections),
    }


def _inspect_unit(output_dir: Path, unit: dict[str, Any]) -> dict[str, Any]:
    valid: list[str] = []
    invalid: list[str] = []
    missing: list[str] = []
    errors: list[str] = []
    for artifact_id in unit["artifactIds"]:
        path = output_dir / "results" / f"{artifact_id}.json"
        if not path.exists():
            missing.append(artifact_id)
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            invalid.append(artifact_id)
            continue
        if not isinstance(record, dict) or str(record.get("id") or record.get("caseId") or "") == "":
            invalid.append(artifact_id)
            continue
        valid.append(artifact_id)
        if str(record.get("error") or "").strip():
            errors.append(artifact_id)
    return {
        "valid": not missing and not invalid and len(valid) == len(unit["artifactIds"]),
        "validArtifactIds": valid,
        "invalidArtifactIds": invalid,
        "missingArtifactIds": missing,
        "errorArtifactIds": errors,
    }


def _pending_units(output_dir: Path, units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [unit for unit in units if not _inspect_unit(output_dir, unit)["valid"]]


def _adopt_preexisting_artifacts(
    spec: DurableSpec,
    units: list[dict[str, Any]],
    runtime_dir: Path,
    counters: dict[str, int],
) -> None:
    known_artifacts = {
        str(item.get("artifactId") or "")
        for item in _read_json_lines(runtime_dir / "artifact_epochs.jsonl")
    }
    known_cases = {
        str(item.get("caseId") or "")
        for item in _read_json_lines(runtime_dir / "case_epochs.jsonl")
    }
    artifact_records: list[dict[str, Any]] = []
    case_records: list[dict[str, Any]] = []
    event_records: list[dict[str, Any]] = []
    for unit in units:
        inspection = _inspect_unit(spec.output_dir, unit)
        for artifact_id in inspection["validArtifactIds"]:
            if artifact_id in known_artifacts:
                continue
            record = {
                "schemaVersion": 1,
                "artifactId": artifact_id,
                "caseId": unit["caseId"],
                "origin": "preexisting",
                "recordedAt": _timestamp(),
            }
            artifact_records.append(record)
            event_records.append(
                {
                    "schemaVersion": 1,
                    "event": "artifact_adopted",
                    "at": _timestamp(),
                    "artifactId": artifact_id,
                    "caseId": unit["caseId"],
                }
            )
            counters["adoptedArtifactCount"] += 1
        if inspection["valid"] and str(unit["caseId"]) not in known_cases:
            case_records.append(
                {
                    "schemaVersion": 1,
                    "caseId": unit["caseId"],
                    "artifactIds": list(unit["artifactIds"]),
                    "origin": "preexisting",
                    "configEpoch": 0,
                    "configSha256": "preexisting-untracked",
                    "settings": {},
                    "environment": {},
                    "attempt": 0,
                    "outcome": "adopted",
                    "recordedAt": _timestamp(),
                }
            )
    _append_json_lines(runtime_dir / "artifact_epochs.jsonl", artifact_records)
    _append_json_lines(runtime_dir / "case_epochs.jsonl", case_records)
    _append_json_lines(runtime_dir / "events.jsonl", event_records)


def _archive_retry_artifacts(
    output_dir: Path,
    runtime_dir: Path,
    unit: dict[str, Any],
    attempt: int,
    inspection: dict[str, Any],
) -> None:
    archive_dir = runtime_dir / "failed_results"
    archive_dir.mkdir(parents=True, exist_ok=True)
    for artifact_id in [*inspection["invalidArtifactIds"], *inspection["errorArtifactIds"]]:
        source = output_dir / "results" / f"{artifact_id}.json"
        if not source.exists():
            continue
        kind = "invalid" if artifact_id in inspection["invalidArtifactIds"] else "error"
        target = archive_dir / f"{_safe_name(artifact_id)}.attempt-{attempt}.{kind}.json"
        suffix = 1
        while target.exists():
            target = archive_dir / f"{_safe_name(artifact_id)}.attempt-{attempt}.{kind}-{suffix}.json"
            suffix += 1
        shutil.move(str(source), str(target))
        _event(runtime_dir, f"artifact_{kind}", artifactId=artifact_id, attempt=attempt, archivePath=str(target))


def _record_case_epoch(
    runtime_dir: Path,
    unit: dict[str, Any],
    epoch: int,
    config_sha: str,
    effective: dict[str, Any],
    attempt: int,
    outcome: str,
) -> None:
    if _has_case_epoch(runtime_dir, str(unit["caseId"])):
        return
    _append_json_line(
        runtime_dir / "case_epochs.jsonl",
        {
            "schemaVersion": 1,
            "caseId": unit["caseId"],
            "artifactIds": list(unit["artifactIds"]),
            "origin": "supervised",
            "configEpoch": epoch,
            "configSha256": config_sha,
            "settings": effective["settings"],
            "environment": effective["environment"],
            "attempt": attempt,
            "outcome": outcome,
            "recordedAt": _timestamp(),
        },
    )
    for artifact_id in unit["artifactIds"]:
        _append_json_line(
            runtime_dir / "artifact_epochs.jsonl",
            {
                "schemaVersion": 1,
                "artifactId": artifact_id,
                "caseId": unit["caseId"],
                "origin": "supervised",
                "configEpoch": epoch,
                "configSha256": config_sha,
                "recordedAt": _timestamp(),
            },
        )
    _event(runtime_dir, "case_durable", caseId=unit["caseId"], configEpoch=epoch, outcome=outcome)


def _ensure_config_epoch(runtime_dir: Path, config_sha: str, effective: dict[str, Any]) -> int:
    records = _read_json_lines(runtime_dir / "config_epochs.jsonl")
    for item in records:
        if item.get("configSha256") == config_sha:
            return int(item.get("configEpoch") or 0)
    epoch = max([int(item.get("configEpoch") or 0) for item in records] or [0]) + 1
    _append_json_line(
        runtime_dir / "config_epochs.jsonl",
        {
            "schemaVersion": 1,
            "configEpoch": epoch,
            "configSha256": config_sha,
            "settings": effective["settings"],
            "environment": effective["environment"],
            "operational": effective["operational"],
            "createdAt": _timestamp(),
        },
    )
    return epoch


def _config_sha(effective: dict[str, Any]) -> str:
    semantic = {
        "arm": effective["arm"],
        "settings": effective["settings"],
        "environment": effective["environment"],
    }
    encoded = json.dumps(semantic, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _write_durable_summary(spec: DurableSpec, status: dict[str, Any]) -> None:
    payload = {
        "schemaVersion": 1,
        "arm": spec.arm,
        "publicPath": str(spec.public_path),
        "outputDir": str(spec.output_dir),
        "actualState": status["actualState"],
        "totalCases": status["totalCases"],
        "completedCases": status["completedCases"],
        "totalArtifacts": status["totalArtifacts"],
        "completedArtifacts": status["completedArtifacts"],
        "errorArtifactCount": status["errorArtifactCount"],
        "launchedChildCount": status["launchedChildCount"],
        "adoptedArtifactCount": status["adoptedArtifactCount"],
        "finishedAt": status.get("finishedAt") or _timestamp(),
    }
    _atomic_write_json(spec.output_dir / RUNTIME_DIR_NAME / "durable_summary.json", payload)


def _persist_runtime_spec(runtime_dir: Path, spec: DurableSpec, manifest: dict[str, Any]) -> None:
    identity = {
        "schemaVersion": 1,
        "arm": spec.arm,
        "publicPath": str(spec.public_path),
        "publicSha256": hashlib.sha256(spec.public_path.read_bytes()).hexdigest(),
        "benchmarkId": str(manifest.get("benchmarkId") or ""),
        "outputDir": str(spec.output_dir),
        "dbPath": str(spec.db_path) if spec.db_path else "",
        "baseSettings": spec.settings,
        "baseEnvironment": spec.environment,
        "baseOperational": spec.operational,
        "runnerCommand": list(spec.runner_command),
        "sourceSpecPath": str(spec.path),
    }
    if spec.database_attestation:
        identity["databaseAttestation"] = spec.database_attestation
    path = runtime_dir / "spec.json"
    if path.exists():
        existing = _read_json(path)
        immutable = (
            "arm",
            "publicPath",
            "publicSha256",
            "benchmarkId",
            "outputDir",
            "dbPath",
            "runnerCommand",
        )
        if spec.database_attestation or "databaseAttestation" in existing:
            immutable = (*immutable, "databaseAttestation")
        mismatches = [key for key in immutable if existing.get(key) != identity.get(key)]
        if mismatches:
            raise ValueError(f"durable spec identity changed for existing output: {mismatches}")
        return
    _atomic_write_json(path, identity)


def _recover_recorded_child(previous: dict[str, Any], output_dir: Path, runtime_dir: Path) -> None:
    pid = int(previous.get("childPid") or 0)
    pgid = int(previous.get("childPgid") or 0)
    token = str(previous.get("childStartToken") or "")
    if pid <= 0 or pgid <= 0 or not token or _process_start_token(pid) != token:
        return
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
    except OSError:
        return
    if str(output_dir) not in cmdline:
        return
    _event(runtime_dir, "orphan_child_recovered", childPid=pid, childPgid=pgid)
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return


def _terminate_process_group(child: subprocess.Popen[bytes], pgid: int, grace_seconds: float) -> None:
    if child.poll() is not None:
        return
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + max(0.0, grace_seconds)
    while child.poll() is None and time.monotonic() < deadline:
        time.sleep(0.05)
    if child.poll() is None:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _process_start_token(pid: int) -> str:
    try:
        return Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()[21]
    except (OSError, IndexError):
        return ""


def _attempts(runtime_dir: Path) -> dict[str, int]:
    path = runtime_dir / "attempts.json"
    raw = _read_json(path) if path.exists() else {}
    return {str(key): int(value) for key, value in raw.items()}


def _has_case_epoch(runtime_dir: Path, case_id: str) -> bool:
    return any(str(item.get("caseId") or "") == case_id for item in _read_json_lines(runtime_dir / "case_epochs.jsonl"))


def _poll_seconds(spec: DurableSpec, control: dict[str, Any]) -> float:
    return float({**spec.operational, **dict(control.get("operationalPatch") or {})}["pollSeconds"])


def _clear_cancel(path: Path) -> None:
    control = _control(path)
    control["cancelCurrentCase"] = False
    control["revision"] = int(control.get("revision") or 0) + 1
    control["updatedAt"] = _timestamp()
    _atomic_write_json(path, control)


def _control(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _default_control()
    value = _read_json(path)
    if str(value.get("desiredState") or "") not in CONTROL_STATES:
        raise ValueError(f"invalid control file desiredState: {value.get('desiredState')!r}")
    return value


def _default_control() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "revision": 0,
        "desiredState": "running",
        "cancelCurrentCase": False,
        "settingsPatch": {},
        "environmentPatch": {},
        "operationalPatch": {},
        "updatedAt": _timestamp(),
    }


def _validate_settings(arm: str, settings: dict[str, Any]) -> None:
    if arm == "custom":
        invalid = sorted(
            key
            for key, value in settings.items()
            if not str(key).strip() or not isinstance(value, (str, int, float, bool))
        )
        if invalid:
            raise ValueError(f"custom settings must be named JSON scalars: {invalid}")
        return
    unknown = sorted(set(settings) - SETTING_KEYS[arm])
    if unknown:
        raise ValueError(f"unsupported settings for arm={arm}: {unknown}")
    if not str(settings.get("model") or "").strip():
        raise ValueError("settings.model is required")
    numeric = {
        "direct": ("timeoutSeconds",),
        "beta6": ("limit",),
        "universal": ("candidateLimit", "evidenceLimit"),
    }[arm]
    for key in numeric:
        if key in settings and float(settings[key]) <= 0:
            raise ValueError(f"settings.{key} must be positive")


def _validate_environment(environment: dict[str, Any]) -> None:
    unknown = sorted(set(environment) - SAFE_ENVIRONMENT_KEYS)
    if unknown:
        raise ValueError(f"environment keys are not safe to persist: {unknown}")


def _validate_operational(operational: dict[str, Any]) -> None:
    unknown = sorted(set(operational) - set(DEFAULT_OPERATIONAL))
    if unknown:
        raise ValueError(f"unsupported operational settings: {unknown}")
    if float(operational["pollSeconds"]) <= 0:
        raise ValueError("operational.pollSeconds must be positive")
    if int(operational["maxAttempts"]) <= 0:
        raise ValueError("operational.maxAttempts must be positive")
    if float(operational["childTimeoutSeconds"]) < 0:
        raise ValueError("operational.childTimeoutSeconds must be non-negative")
    if float(operational["terminationGraceSeconds"]) < 0:
        raise ValueError("operational.terminationGraceSeconds must be non-negative")


def _validate_database_attestation(attestation: dict[str, Any], *, db_path: Path | None) -> None:
    if not attestation:
        return
    unknown = sorted(
        set(attestation)
        - {"required", "mode", "expectedSha256", "expectedSizeBytes", "expectedSampleSha256"}
    )
    if unknown:
        raise ValueError(f"unsupported databaseAttestation fields: {unknown}")
    if db_path is None:
        raise ValueError("databaseAttestation requires dbPath")
    if not isinstance(attestation.get("required"), bool):
        raise ValueError("databaseAttestation.required must be boolean")
    if not attestation["required"]:
        return
    mode = str(attestation.get("mode") or "full_sha256")
    if mode not in {"full_sha256", "sampled_sha256_v1"}:
        raise ValueError(f"unsupported databaseAttestation.mode: {mode!r}")
    expected_sha = str(attestation.get("expectedSha256") or "").strip().lower()
    if len(expected_sha) != 64 or any(character not in "0123456789abcdef" for character in expected_sha):
        raise ValueError("databaseAttestation.expectedSha256 must be a 64-character SHA-256")
    try:
        expected_size = int(attestation.get("expectedSizeBytes"))
    except (TypeError, ValueError) as exc:
        raise ValueError("databaseAttestation.expectedSizeBytes must be a positive integer") from exc
    if expected_size <= 0:
        raise ValueError("databaseAttestation.expectedSizeBytes must be a positive integer")
    if mode == "sampled_sha256_v1":
        expected_sample_sha = str(attestation.get("expectedSampleSha256") or "").strip().lower()
        if len(expected_sample_sha) != 64 or any(
            character not in "0123456789abcdef" for character in expected_sample_sha
        ):
            raise ValueError(
                "databaseAttestation.expectedSampleSha256 must be a 64-character SHA-256"
            )


def _attest_database(spec: DurableSpec, runtime_dir: Path) -> dict[str, Any] | None:
    attestation = spec.database_attestation
    if not attestation or not attestation.get("required"):
        return None
    if spec.db_path is None or not spec.db_path.is_file():
        raise FileNotFoundError(f"database attestation target missing: {spec.db_path}")
    db_path = spec.db_path.resolve()
    stat = db_path.stat()
    mode = str(attestation.get("mode") or "full_sha256")
    expected_sha = str(attestation["expectedSha256"]).lower()
    expected_size = int(attestation["expectedSizeBytes"])
    receipt_path = runtime_dir / "database_attestation.json"
    file_identity = {
        "path": str(db_path),
        "actualSizeBytes": int(stat.st_size),
        "fileMtimeNs": int(stat.st_mtime_ns),
        "fileDevice": int(stat.st_dev),
        "fileInode": int(stat.st_ino),
        "expectedSha256": expected_sha,
        "expectedSizeBytes": expected_size,
        "mode": mode,
    }
    if mode == "sampled_sha256_v1":
        file_identity["expectedSampleSha256"] = str(attestation["expectedSampleSha256"]).lower()
    if receipt_path.exists():
        existing = _read_json(receipt_path)
        if existing.get("passed") is True and all(existing.get(key) == value for key, value in file_identity.items()):
            return existing
    receipt = {"schemaVersion": 1, "required": True, **file_identity, "validatedAt": _timestamp()}
    if mode == "sampled_sha256_v1":
        actual_sample_sha = _sampled_sha256_file(db_path)
        expected_sample_sha = str(attestation["expectedSampleSha256"]).lower()
        passed = stat.st_size == expected_size and actual_sample_sha == expected_sample_sha
        receipt.update(
            {
                "snapshotSha256": expected_sha,
                "actualSampleSha256": actual_sample_sha,
                "passed": passed,
            }
        )
        observed = f"expectedSampleSha256={expected_sample_sha} actualSampleSha256={actual_sample_sha}"
    else:
        actual_sha = _sha256_file(db_path)
        passed = stat.st_size == expected_size and actual_sha == expected_sha
        receipt.update({"actualSha256": actual_sha, "passed": passed})
        observed = f"expectedSha256={expected_sha} actualSha256={actual_sha}"
    _atomic_write_json(receipt_path, receipt)
    if not passed:
        raise ValueError(
            "database attestation failed: "
            f"path={db_path} expectedSize={expected_size} actualSize={stat.st_size} "
            f"mode={mode} {observed}"
        )
    return receipt


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sampled_sha256_file(path: Path) -> str:
    """Hash deterministic spans plus file size without reading a multi-GiB DB end to end."""

    path = Path(path)
    size = path.stat().st_size
    chunk_size = min(256 * 1024, max(1, size))
    max_offset = max(0, size - chunk_size)
    offsets = sorted({(max_offset * index) // 15 for index in range(16)})
    digest = hashlib.sha256()
    digest.update(b"durable-db-sampled-sha256-v1\0")
    digest.update(int(size).to_bytes(16, "big", signed=False))
    with path.open("rb") as stream:
        for offset in offsets:
            stream.seek(offset)
            chunk = stream.read(chunk_size)
            digest.update(int(offset).to_bytes(16, "big", signed=False))
            digest.update(len(chunk).to_bytes(8, "big", signed=False))
            digest.update(chunk)
    return digest.hexdigest()


def _event(runtime_dir: Path, event: str, **fields: Any) -> None:
    _append_json_line(runtime_dir / "events.jsonl", {"schemaVersion": 1, "event": event, "at": _timestamp(), **fields})


def _append_json_line(path: Path, value: dict[str, Any]) -> None:
    _append_json_lines(path, [value])


def _append_json_lines(path: Path, values: list[dict[str, Any]]) -> None:
    if not values:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = "".join(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for value in values
    )
    with path.open("a", encoding="utf-8") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def _atomic_write_json(path: Path, value: Any, *, sync: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        if sync:
            os.fsync(stream.fileno())
    os.replace(temporary, path)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _read_json_lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            records.append(value)
    return records


def _resolved_path(value: Any, *, relative_to: Path) -> Path:
    text = str(value or "").strip()
    if not text:
        raise ValueError("required path is empty")
    path = Path(text).expanduser()
    return (path if path.is_absolute() else relative_to / path).resolve()


def _safe_name(value: str) -> str:
    return "".join(character if character.isalnum() or character in {"-", "_", "."} else "_" for character in value)


def _redacted_command(command: list[str]) -> list[str]:
    return [str(item) for item in command]


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_assignment(value: str) -> tuple[str, Any]:
    if "=" not in value:
        raise ValueError(f"expected KEY=VALUE: {value!r}")
    key, raw = value.split("=", 1)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = raw
    return key, parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="Run or resume a durable benchmark arm.")
    run_parser.add_argument("--spec", type=Path, required=True)
    status_parser = subparsers.add_parser("status", help="Read live benchmark status.")
    status_parser.add_argument("--output-dir", type=Path, required=True)
    control_parser = subparsers.add_parser("control", help="Update live control at the next safe boundary.")
    control_parser.add_argument("--output-dir", type=Path, required=True)
    control_parser.add_argument("--state", choices=sorted(CONTROL_STATES))
    control_parser.add_argument("--set", action="append", default=[])
    control_parser.add_argument("--env", action="append", default=[])
    control_parser.add_argument("--operational", action="append", default=[])
    control_parser.add_argument("--cancel-current", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "run":
        result = run_supervisor(args.spec)
    elif args.command == "status":
        result = read_status(args.output_dir)
    else:
        settings = dict(_parse_assignment(item) for item in args.set)
        environment = {key: str(value) for key, value in (_parse_assignment(item) for item in args.env)}
        operational = dict(_parse_assignment(item) for item in args.operational)
        result = update_control(
            args.output_dir,
            desired_state=args.state,
            settings_patch=settings,
            environment_patch=environment,
            operational_patch=operational,
            cancel_current_case=True if args.cancel_current else None,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
