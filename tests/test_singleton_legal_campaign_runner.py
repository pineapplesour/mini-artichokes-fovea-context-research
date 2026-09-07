from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Callable

import pytest

from tools import run_singleton_legal_campaign as runner


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def frozen(value: dict[str, Any], field: str) -> dict[str, Any]:
    value[field] = runner.canonical_digest(value)
    return value


SYNTHETIC_CAMPAIGN_GIT_COMMIT = "c" * 40


def accept_source_anchor(**kwargs: Any) -> dict[str, str]:
    assert kwargs["anchor"]["commit"] == "a" * 40
    assert kwargs["bound_paths"]
    return {"repositoryRoot": "/synthetic", "commit": "a" * 40, "tree": "b" * 40}


def accept_campaign_anchor(**kwargs: Any) -> dict[str, str]:
    assert kwargs["source_commit"] == "a" * 40
    assert kwargs["expected_campaign_commit"] == SYNTHETIC_CAMPAIGN_GIT_COMMIT
    return {
        "repositoryRoot": "/synthetic",
        "commit": SYNTHETIC_CAMPAIGN_GIT_COMMIT,
        "tree": "d" * 40,
    }


def accept_runtime_identity(config: dict[str, Any]) -> dict[str, Any]:
    identity = {
        "codexVersion": runner.CODEX_VERSION,
        "executableSha256": config["codexExecutableSha256"],
        "featureCount": runner.FEATURE_COUNT,
        "featureSnapshotSha256": runner.FEATURE_SNAPSHOT_SHA256,
        "featureListStdoutSha256": runner.FEATURE_LIST_STDOUT_SHA256,
    }
    identity["identitySha256"] = runner.canonical_digest(identity)
    return identity


def synthetic_build_schedule(**kwargs: Any) -> dict[str, Any]:
    return runner.build_schedule_manifest(
        **kwargs, source_anchor_verifier=accept_source_anchor
    )


def synthetic_run(**kwargs: Any) -> dict[str, Any]:
    return runner.run_campaign(
        **kwargs,
        expected_campaign_git_commit=SYNTHETIC_CAMPAIGN_GIT_COMMIT,
        source_anchor_verifier=accept_source_anchor,
        campaign_anchor_verifier=accept_campaign_anchor,
        runtime_identity_verifier=accept_runtime_identity,
    )


def scientific_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "outcome"],
        "properties": {
            "id": {"type": "string"},
            "outcome": {"enum": sorted(runner.OUTCOMES)},
        },
    }


def execution_config(executable: Path) -> dict[str, Any]:
    return {
        "codexHome": runner.CODEX_HOME,
        "model": runner.CODEX_MODEL,
        "reasoningEffort": "high",
        "verbosity": "low",
        "serviceTier": "default",
        "timeoutSeconds": 30,
        "codexVersion": runner.CODEX_VERSION,
        "codexExecutablePath": str(executable.resolve()),
        "codexExecutableSha256": runner.sha256_file(executable),
        "codexExecutableBytes": executable.stat().st_size,
        "featureCount": runner.FEATURE_COUNT,
        "featureSnapshotSha256": runner.FEATURE_SNAPSHOT_SHA256,
        "featureListStdoutSha256": runner.FEATURE_LIST_STDOUT_SHA256,
        "disabledFeatures": list(runner.DISABLED_FEATURES),
        "disabledFeaturesSha256": runner.DISABLED_FEATURES_SHA256,
        "strictConfigArgv": list(runner.STRICT_CONFIG_ARGV),
        "strictConfigArgvSha256": runner.STRICT_CONFIG_ARGV_SHA256,
        "stdinOnly": True,
        "outputSchemaCliArg": "--output-schema",
        "semanticRetryCount": 0,
        "transportRetryCount": 0,
    }


def make_campaign(
    root: Path,
    *,
    cases: tuple[str, ...] = ("case-01", "case-02"),
    arms: tuple[str, ...] = ("mini", "base"),
    dependencies: dict[str, list[str]] | None = None,
    schema_mutator: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[Path, str, dict[str, dict[str, Any]]]:
    root.mkdir(parents=True, exist_ok=True)
    executable = root / "frozen-codex"
    executable.write_bytes(b"synthetic executable identity\n")
    executable.chmod(0o700)
    schema = scientific_schema()
    if schema_mutator is not None:
        schema_mutator(schema)
    schema_path = root / "answer-schema.json"
    write_json(schema_path, schema)
    units: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for case in cases:
        for arm in arms:
            unit_id = f"{case}--{arm}--answer"
            prompt_path = root / "packets" / f"{unit_id}.txt"
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            prompt_path.write_text(
                f"Public packet for {case}; requested arm is {arm}.\n",
                encoding="utf-8",
            )
            unit = {
                "unitId": unit_id,
                "caseId": case,
                "armId": arm,
                "stageId": "answer",
                "dependencies": list((dependencies or {}).get(unit_id, [])),
                "promptPath": str(prompt_path.relative_to(root)),
                "promptSha256": runner.sha256_file(prompt_path),
                "outputSchemaPath": str(schema_path.relative_to(root)),
                "outputSchemaSha256": runner.sha256_file(schema_path),
                "producesScientificOutcome": True,
            }
            units.append(unit)
            by_id[unit_id] = unit
    runner_path = Path(runner.__file__).resolve()
    manifest = {
        "schemaVersion": 1,
        "protocol": runner.PROTOCOL,
        "status": "frozen_before_calls",
        "campaignId": "synthetic-campaign-v1",
        "scheduleSeed": "synthetic-interleave-seed-v1",
        "gitAnchor": {
            "status": "committed_before_calls",
            "commit": "a" * 40,
            "tree": "b" * 40,
            "dirty": False,
        },
        "executionConfig": execution_config(executable),
        "codeHashes": {str(runner_path): runner.sha256_file(runner_path)},
        "units": units,
    }
    frozen(manifest, "manifestSha256")
    manifest_path = root / "unit-manifest.json"
    write_json(manifest_path, manifest)
    return manifest_path, runner.sha256_file(manifest_path), by_id


def build_schedule(
    manifest_path: Path, manifest_file_sha: str, *, name: str = "schedule.json"
) -> tuple[Path, str, dict[str, Any]]:
    schedule_path = manifest_path.parent / name
    schedule = synthetic_build_schedule(
        unit_manifest_path=manifest_path,
        expected_unit_manifest_file_sha256=manifest_file_sha,
        output_path=schedule_path,
    )
    return schedule_path, runner.sha256_file(schedule_path), schedule


def trace_bytes(
    unit_id: str,
    case_id: str,
    *,
    outcome: str = "인용됨",
    raw_message: str | None | object = ...,
    thread_id: str | None = None,
) -> bytes:
    if raw_message is ...:
        raw_message = json.dumps(
            {"id": case_id, "outcome": outcome}, ensure_ascii=False
        )
    item: dict[str, Any] = {"id": f"message-{unit_id}", "type": "agent_message"}
    if raw_message is not None:
        item["text"] = raw_message
    rows = [
        {"type": "thread.started", "thread_id": thread_id or f"thread-{unit_id}"},
        {
            "type": "item.completed",
            "item": {
                "id": f"containment-{unit_id}",
                "type": "error",
                "message": runner.EXPECTED_CODE_MODE_DISABLED_DIAGNOSTIC,
            },
        },
        {"type": "turn.started"},
        {"type": "item.completed", "item": item},
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 10,
                "cached_input_tokens": 2,
                "cache_write_input_tokens": 0,
                "output_tokens": 5,
                "reasoning_output_tokens": 1,
            },
        },
    ]
    return b"".join(runner.canonical_json_bytes(row) + b"\n" for row in rows)


class FakeProcess:
    def __init__(self, trace: bytes, *, returncode: int = 0) -> None:
        self.trace = trace
        self.returncode = returncode
        self.input: bytes | None = None

    def communicate(self, *, input: bytes, timeout: int) -> tuple[bytes, bytes]:
        assert timeout == 30
        self.input = input
        return self.trace, b""


class FakeFactory:
    def __init__(
        self,
        units: dict[str, dict[str, Any]],
        *,
        traces: dict[str, bytes] | None = None,
        duplicate_thread: bool = False,
    ) -> None:
        self.units = units
        self.traces = traces or {}
        self.duplicate_thread = duplicate_thread
        self.calls: list[tuple[list[str], dict[str, Any], FakeProcess]] = []

    def __call__(self, command: list[str], **kwargs: Any) -> FakeProcess:
        unit_id = Path(kwargs["cwd"]).name
        # This assertion is the first-attempt-before-Popen contract.
        assert (Path(kwargs["cwd"]) / "attempt_started.json").is_file()
        assert kwargs["env"] == {
            "CODEX_HOME": runner.CODEX_HOME,
            "PATH": runner.os.environ.get("PATH", ""),
            "LANG": "C.UTF-8",
        }
        unit = self.units[unit_id]
        trace = self.traces.get(
            unit_id,
            trace_bytes(
                unit_id,
                unit["caseId"],
                thread_id="thread-shared" if self.duplicate_thread else None,
            ),
        )
        process = FakeProcess(trace)
        self.calls.append((command, kwargs, process))
        return process


def ticking_clock() -> Callable[[], float]:
    state = {"value": 100.0}

    def tick() -> float:
        state["value"] += 0.125
        return state["value"]

    return tick


def execute(
    tmp_path: Path,
    *,
    factory: FakeFactory | None = None,
    cases: tuple[str, ...] = ("case-01", "case-02"),
    arms: tuple[str, ...] = ("mini", "base"),
) -> tuple[dict[str, Any], FakeFactory, Path, Path, str, str]:
    manifest_path, manifest_sha, units = make_campaign(
        tmp_path / "frozen", cases=cases, arms=arms
    )
    schedule_path, schedule_sha, _ = build_schedule(manifest_path, manifest_sha)
    used_factory = factory or FakeFactory(units)
    output = tmp_path / "run"
    receipt = synthetic_run(
        unit_manifest_path=manifest_path,
        expected_unit_manifest_file_sha256=manifest_sha,
        schedule_path=schedule_path,
        expected_schedule_file_sha256=schedule_sha,
        output_dir=output,
        process_factory=used_factory,
        monotonic=ticking_clock(),
    )
    return (
        receipt,
        used_factory,
        output,
        manifest_path,
        manifest_sha,
        schedule_sha,
    )


def test_schedule_is_deterministic_dependency_ready_and_interleaved(
    tmp_path: Path,
) -> None:
    dependency = "case-01--mini--answer"
    dependent = "case-02--mini--answer"
    manifest_path, manifest_sha, _ = make_campaign(
        tmp_path,
        dependencies={dependent: [dependency]},
    )
    first_path, _, first = build_schedule(manifest_path, manifest_sha, name="one.json")
    second_path, _, second = build_schedule(manifest_path, manifest_sha, name="two.json")
    assert first == second
    assert first_path.read_bytes() == second_path.read_bytes()
    order = first["orderedUnitIds"]
    assert order.index(dependency) < order.index(dependent)
    assert set(order) == {
        "case-01--mini--answer",
        "case-01--base--answer",
        "case-02--mini--answer",
        "case-02--base--answer",
    }
    for prefix_length in range(1, len(order) + 1):
        prefix = order[:prefix_length]
        arm_counts = [
            sum(f"--{arm}--" in unit_id for unit_id in prefix)
            for arm in ("mini", "base")
        ]
        assert max(arm_counts) - min(arm_counts) <= 1


def test_dependency_cycle_rejects_before_schedule_file(tmp_path: Path) -> None:
    left = "case-01--mini--answer"
    right = "case-01--base--answer"
    manifest_path, manifest_sha, _ = make_campaign(
        tmp_path,
        cases=("case-01",),
        dependencies={left: [right], right: [left]},
    )
    output = tmp_path / "schedule.json"
    with pytest.raises(runner.CampaignIntegrityError, match="cycle"):
        synthetic_build_schedule(
            unit_manifest_path=manifest_path,
            expected_unit_manifest_file_sha256=manifest_sha,
            output_path=output,
        )
    assert not output.exists()


def test_duplicate_case_arm_stage_coordinate_rejects(tmp_path: Path) -> None:
    manifest_path, _, _ = make_campaign(
        tmp_path, cases=("case-01",), arms=("mini",)
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    duplicate = copy.deepcopy(manifest["units"][0])
    duplicate["unitId"] = "different-id-same-coordinate"
    manifest["units"].append(duplicate)
    manifest["manifestSha256"] = runner.canonical_digest(
        {key: value for key, value in manifest.items() if key != "manifestSha256"}
    )
    write_json(manifest_path, manifest)
    with pytest.raises(runner.CampaignIntegrityError, match="case/arm/stage"):
        synthetic_build_schedule(
            unit_manifest_path=manifest_path,
            expected_unit_manifest_file_sha256=runner.sha256_file(manifest_path),
            output_path=tmp_path / "schedule.json",
        )


def test_happy_campaign_is_one_process_per_unit_with_strict_stdin_contract(
    tmp_path: Path,
) -> None:
    receipt, factory, output, _, _, _ = execute(tmp_path)
    assert receipt["status"] == "accepted_complete"
    assert receipt["scientificRows"] == 4
    assert receipt["nullScientificRows"] == 0
    assert receipt["campaignProcessInvocationCount"] == 4
    assert receipt["semanticRetryCount"] == 0
    assert receipt["transportRetryCount"] == 0
    assert len(factory.calls) == 4
    assert len(set(receipt["threadIds"])) == 4
    assert receipt["tokenTotals"] == {
        "inputTokens": 40,
        "cachedInputTokens": 8,
        "cacheWriteInputTokens": 0,
        "outputTokens": 20,
        "reasoningTokens": 4,
        "totalTokens": 60,
    }
    for command, kwargs, process in factory.calls:
        assert command[-1] == "-"
        assert command.count("-") == 1
        assert command.count("--output-schema") == 1
        assert "--strict-config" in command
        assert "--ignore-user-config" in command
        assert "--ignore-rules" in command
        assert "--ephemeral" in command
        for feature in runner.DISABLED_FEATURES:
            assert f"features.{feature}=false" in command
        assert kwargs["stdin"] is runner.subprocess.PIPE
        assert kwargs["stdout"] is runner.subprocess.PIPE
        assert process.input and process.input.startswith(b"Public packet")
    rows = [
        json.loads(line)
        for line in (output / "scientific_predictions.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert len(rows) == 4
    assert all(set(row) == {"id", "armId", "unitId", "outcome"} for row in rows)


def test_accepted_complete_resume_revalidates_and_never_calls(tmp_path: Path) -> None:
    receipt, _, output, manifest_path, manifest_sha, schedule_sha = execute(tmp_path)
    schedule_path = manifest_path.parent / "schedule.json"

    def forbidden_factory(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("accepted unit was re-invoked")

    resumed = synthetic_run(
        unit_manifest_path=manifest_path,
        expected_unit_manifest_file_sha256=manifest_sha,
        schedule_path=schedule_path,
        expected_schedule_file_sha256=schedule_sha,
        output_dir=output,
        process_factory=forbidden_factory,
    )
    assert resumed == receipt


def test_public_completed_validator_is_read_only_and_returns_ordered_artifacts(
    tmp_path: Path,
) -> None:
    receipt, _, output, manifest_path, manifest_sha, schedule_sha = execute(
        tmp_path, cases=("case-01",), arms=("mini", "base")
    )
    before = {
        str(path.relative_to(output)): runner.sha256_file(path)
        for path in output.rglob("*")
        if path.is_file()
    }
    validated = runner.validate_completed_campaign(
        unit_manifest_path=manifest_path,
        expected_unit_manifest_file_sha256=manifest_sha,
        schedule_path=manifest_path.parent / "schedule.json",
        expected_schedule_file_sha256=schedule_sha,
        expected_campaign_git_commit=SYNTHETIC_CAMPAIGN_GIT_COMMIT,
        output_dir=output,
        source_anchor_verifier=accept_source_anchor,
        campaign_anchor_verifier=accept_campaign_anchor,
        runtime_identity_verifier=accept_runtime_identity,
    )
    after = {
        str(path.relative_to(output)): runner.sha256_file(path)
        for path in output.rglob("*")
        if path.is_file()
    }
    assert before == after
    assert validated["campaignReceipt"] == receipt
    assert len(validated["scientificRows"]) == 2
    assert [row["unitId"] for row in validated["scientificRows"]] == [
        result["unitId"]
        for result in validated["unitResults"]
        if result["stageId"] == "answer"
    ]


def test_started_attempt_is_never_recalled_after_process_failure(tmp_path: Path) -> None:
    manifest_path, manifest_sha, units = make_campaign(
        tmp_path / "frozen", cases=("case-01",), arms=("mini",)
    )
    schedule_path, schedule_sha, _ = build_schedule(manifest_path, manifest_sha)
    output = tmp_path / "run"
    calls = {"count": 0}

    def exploding_factory(*args: Any, **kwargs: Any) -> Any:
        calls["count"] += 1
        assert (Path(kwargs["cwd"]) / "attempt_started.json").is_file()
        raise OSError("synthetic transport loss")

    with pytest.raises(OSError, match="transport loss"):
        synthetic_run(
            unit_manifest_path=manifest_path,
            expected_unit_manifest_file_sha256=manifest_sha,
            schedule_path=schedule_path,
            expected_schedule_file_sha256=schedule_sha,
            output_dir=output,
            process_factory=exploding_factory,
        )
    assert calls["count"] == 1
    assert (output / "units" / next(iter(units)) / "attempt_started.json").is_file()
    with pytest.raises(runner.StartedUnitError, match="never be re-invoked"):
        synthetic_run(
            unit_manifest_path=manifest_path,
            expected_unit_manifest_file_sha256=manifest_sha,
            schedule_path=schedule_path,
            expected_schedule_file_sha256=schedule_sha,
            output_dir=output,
            process_factory=exploding_factory,
        )
    assert calls["count"] == 1


def test_timeout_kills_and_reaps_child_then_started_registry_blocks_recall(
    tmp_path: Path,
) -> None:
    manifest_path, manifest_sha, units = make_campaign(
        tmp_path / "frozen", cases=("case-01",), arms=("mini",)
    )
    schedule_path, schedule_sha, _ = build_schedule(manifest_path, manifest_sha)
    output = tmp_path / "run"

    class TimeoutProcess:
        returncode = None

        def __init__(self) -> None:
            self.communications = 0
            self.killed = False

        def communicate(self, **kwargs: Any) -> tuple[bytes, bytes]:
            self.communications += 1
            if self.communications == 1:
                raise runner.subprocess.TimeoutExpired("synthetic", 30)
            return b"", b""

        def kill(self) -> None:
            self.killed = True

    process = TimeoutProcess()
    calls = {"count": 0}

    def timeout_factory(*args: Any, **kwargs: Any) -> TimeoutProcess:
        calls["count"] += 1
        assert kwargs["start_new_session"] is True
        return process

    with pytest.raises(runner.subprocess.TimeoutExpired):
        synthetic_run(
            unit_manifest_path=manifest_path,
            expected_unit_manifest_file_sha256=manifest_sha,
            schedule_path=schedule_path,
            expected_schedule_file_sha256=schedule_sha,
            output_dir=output,
            process_factory=timeout_factory,
        )
    assert calls["count"] == 1
    assert process.killed is True
    assert process.communications == 2
    assert (output / "units" / next(iter(units)) / "attempt_started.json").is_file()
    with pytest.raises(runner.StartedUnitError):
        synthetic_run(
            unit_manifest_path=manifest_path,
            expected_unit_manifest_file_sha256=manifest_sha,
            schedule_path=schedule_path,
            expected_schedule_file_sha256=schedule_sha,
            output_dir=output,
            process_factory=lambda *args, **kwargs: pytest.fail("must not call"),
        )
    assert calls["count"] == 1


def test_invalid_first_attempt_trace_is_preserved_byte_exact_and_never_recalled(
    tmp_path: Path,
) -> None:
    manifest_path, manifest_sha, units = make_campaign(
        tmp_path / "frozen", cases=("case-01",), arms=("mini",)
    )
    schedule_path, schedule_sha, _ = build_schedule(manifest_path, manifest_sha)
    unit_id = next(iter(units))
    invalid_raw = b"not-json-at-all\n"
    factory = FakeFactory(units, traces={unit_id: invalid_raw})
    output = tmp_path / "run"
    with pytest.raises(runner.CampaignIntegrityError, match="invalid"):
        synthetic_run(
            unit_manifest_path=manifest_path,
            expected_unit_manifest_file_sha256=manifest_sha,
            schedule_path=schedule_path,
            expected_schedule_file_sha256=schedule_sha,
            output_dir=output,
            process_factory=factory,
        )
    unit_root = output / "units" / unit_id
    assert (unit_root / "raw_trace.jsonl").read_bytes() == invalid_raw
    assert (unit_root / "raw_stderr.bin").read_bytes() == b""
    assert not (unit_root / "unit_receipt.json").exists()
    with pytest.raises(runner.StartedUnitError):
        synthetic_run(
            unit_manifest_path=manifest_path,
            expected_unit_manifest_file_sha256=manifest_sha,
            schedule_path=schedule_path,
            expected_schedule_file_sha256=schedule_sha,
            output_dir=output,
            process_factory=lambda *args, **kwargs: pytest.fail("must not call"),
        )
    assert len(factory.calls) == 1


def test_cli_timeout_is_normalized_as_rejected_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def timeout(**kwargs: Any) -> dict[str, Any]:
        raise runner.subprocess.TimeoutExpired("synthetic", 30)

    monkeypatch.setattr(runner, "run_campaign", timeout)
    code = runner.main(
        [
            "run",
            "--unit-manifest",
            "manifest.json",
            "--unit-manifest-file-sha256",
            "0" * 64,
            "--schedule",
            "schedule.json",
            "--schedule-file-sha256",
            "1" * 64,
            "--campaign-git-commit",
            "2" * 40,
            "--output-dir",
            "output",
            "--execute-live",
        ]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert json.loads(captured.err)["status"] == "rejected"


def test_malformed_and_missing_message_payloads_are_full_denominator_nulls(
    tmp_path: Path,
) -> None:
    manifest_path, manifest_sha, units = make_campaign(
        tmp_path / "frozen",
        cases=("case-01", "case-02"),
        arms=("mini",),
    )
    traces = {
        "case-01--mini--answer": trace_bytes(
            "case-01--mini--answer", "case-01", raw_message="{not-json"
        ),
        "case-02--mini--answer": trace_bytes(
            "case-02--mini--answer", "case-02", raw_message=""
        ),
    }
    schedule_path, schedule_sha, _ = build_schedule(manifest_path, manifest_sha)
    receipt = synthetic_run(
        unit_manifest_path=manifest_path,
        expected_unit_manifest_file_sha256=manifest_sha,
        schedule_path=schedule_path,
        expected_schedule_file_sha256=schedule_sha,
        output_dir=tmp_path / "run",
        process_factory=FakeFactory(units, traces=traces),
        monotonic=ticking_clock(),
    )
    assert receipt["status"] == "accepted_complete"
    assert receipt["scientificRows"] == 2
    assert receipt["nullScientificRows"] == 2
    rows = [
        json.loads(line)
        for line in (tmp_path / "run" / "scientific_predictions.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [row["outcome"] for row in rows] == [None, None]
    reasons = {
        json.loads(path.read_text(encoding="utf-8"))["invalidResponseReason"]
        for path in (tmp_path / "run" / "units").glob("*/normalized_result.json")
    }
    assert reasons == {"malformed_agent_response", "missing_completed_agent_message"}


def test_abstain_is_preserved_as_valid_scientific_output(tmp_path: Path) -> None:
    manifest_path, manifest_sha, units = make_campaign(
        tmp_path / "frozen", cases=("case-01",), arms=("mini",)
    )
    unit_id = next(iter(units))
    traces = {
        unit_id: trace_bytes(unit_id, "case-01", outcome="ABSTAIN")
    }
    schedule_path, schedule_sha, _ = build_schedule(manifest_path, manifest_sha)
    receipt = synthetic_run(
        unit_manifest_path=manifest_path,
        expected_unit_manifest_file_sha256=manifest_sha,
        schedule_path=schedule_path,
        expected_schedule_file_sha256=schedule_sha,
        output_dir=tmp_path / "run",
        process_factory=FakeFactory(units, traces=traces),
        monotonic=ticking_clock(),
    )
    assert receipt["nullScientificRows"] == 0
    row = json.loads(
        (tmp_path / "run" / "scientific_predictions.jsonl")
        .read_text(encoding="utf-8")
        .strip()
    )
    assert row["outcome"] == "ABSTAIN"


def test_nested_forbidden_response_key_is_invalid_content_not_campaign_drop() -> None:
    unit = {
        "unitId": "unit",
        "caseId": "case-01",
        "armId": "mini",
        "stageId": "analysis",
        "producesScientificOutcome": False,
    }
    normalized = runner._normalize_response(
        unit=unit,
        trace_audit={"agentMessage": '{"safe":{"goldLabel":"forbidden"}}'},
    )
    assert normalized["responseValid"] is False
    assert normalized["invalidResponseReason"] == "forbidden_response_key"
    assert normalized["outcome"] is None


@pytest.mark.parametrize(
    "rows,match",
    [
        (
            [
                {"type": "thread.started", "thread_id": "t"},
                {"type": "turn.started"},
                {
                    "type": "item.completed",
                    "item": {"id": "bad", "type": "file_change"},
                },
                {
                    "type": "turn.completed",
                    "usage": {
                        "input_tokens": 1,
                        "cached_input_tokens": 0,
                        "cache_write_input_tokens": 0,
                        "output_tokens": 1,
                        "reasoning_output_tokens": 0,
                    },
                },
            ],
            "item type not allowlisted",
        ),
        ([{"type": "future.event"}], "event not allowlisted"),
        (
            [
                {"type": "thread.started", "thread_id": "t"},
                {"type": "turn.started", "toolReceipt": {}},
            ],
            "forbidden key",
        ),
    ],
)
def test_trace_allowlist_and_recursive_forbidden_keys_fail_closed(
    rows: list[dict[str, Any]], match: str
) -> None:
    raw = b"".join(runner.canonical_json_bytes(row) + b"\n" for row in rows)
    with pytest.raises(runner.CampaignIntegrityError, match=match):
        runner.audit_trace(raw, unit_id="unit")


def test_trace_requires_exactly_one_completed_agent_message() -> None:
    rows = [
        {"type": "thread.started", "thread_id": "t"},
        {
            "type": "item.completed",
            "item": {
                "id": "containment",
                "type": "error",
                "message": runner.EXPECTED_CODE_MODE_DISABLED_DIAGNOSTIC,
            },
        },
        {"type": "turn.started"},
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 1,
                "cached_input_tokens": 0,
                "cache_write_input_tokens": 0,
                "output_tokens": 1,
                "reasoning_output_tokens": 0,
            },
        },
    ]
    raw = b"".join(runner.canonical_json_bytes(row) + b"\n" for row in rows)
    with pytest.raises(runner.CampaignIntegrityError, match="exactly one"):
        runner.audit_trace(raw, unit_id="unit")


@pytest.mark.parametrize(
    "event",
    [
        {
            "type": "item.completed",
            "item": {"id": "d", "type": "error", "message": "some other error"},
        },
        {
            "type": "item.started",
            "item": {
                "id": "d",
                "type": "error",
                "message": runner.EXPECTED_CODE_MODE_DISABLED_DIAGNOSTIC,
            },
        },
    ],
)
def test_only_exact_completed_containment_diagnostic_is_allowed(
    event: dict[str, Any],
) -> None:
    rows = [
        {"type": "thread.started", "thread_id": "t"},
        event,
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {"id": "m", "type": "agent_message", "text": "{}"},
        },
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 1,
                "cached_input_tokens": 0,
                "cache_write_input_tokens": 0,
                "output_tokens": 1,
                "reasoning_output_tokens": 0,
            },
        },
    ]
    raw = b"".join(runner.canonical_json_bytes(row) + b"\n" for row in rows)
    with pytest.raises(runner.CampaignIntegrityError, match="unexpected error"):
        runner.audit_trace(raw, unit_id="unit")


def test_jsonl_is_split_only_on_ascii_lf_not_unicode_line_separator() -> None:
    rows = [
        {"type": "thread.started", "thread_id": "thread-unicode"},
        {
            "type": "item.completed",
            "item": {
                "id": "containment",
                "type": "error",
                "message": runner.EXPECTED_CODE_MODE_DISABLED_DIAGNOSTIC,
            },
        },
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {"id": "reasoning", "type": "reasoning", "text": "a\u2028b"},
        },
        {
            "type": "item.completed",
            "item": {
                "id": "message",
                "type": "agent_message",
                "text": '{"id":"case-01","outcome":"인용됨"}',
            },
        },
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 1,
                "cached_input_tokens": 0,
                "cache_write_input_tokens": 0,
                "output_tokens": 1,
                "reasoning_output_tokens": 0,
            },
        },
    ]
    raw = b"".join(runner.canonical_json_bytes(row) + b"\n" for row in rows)
    assert runner.audit_trace(raw, unit_id="unit")["threadId"] == "thread-unicode"


def test_trace_tamper_on_resume_invalidates_without_call(tmp_path: Path) -> None:
    _, _, output, manifest_path, manifest_sha, schedule_sha = execute(
        tmp_path, cases=("case-01",), arms=("mini",)
    )
    trace_path = next((output / "units").glob("*/raw_trace.jsonl"))
    trace_path.write_bytes(trace_path.read_bytes() + b"\n")

    def forbidden_factory(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("tampered unit must not be invoked")

    with pytest.raises(runner.CampaignIntegrityError):
        synthetic_run(
            unit_manifest_path=manifest_path,
            expected_unit_manifest_file_sha256=manifest_sha,
            schedule_path=manifest_path.parent / "schedule.json",
            expected_schedule_file_sha256=schedule_sha,
            output_dir=output,
            process_factory=forbidden_factory,
        )


def test_resigned_unit_and_campaign_receipt_tamper_still_fails_closed(
    tmp_path: Path,
) -> None:
    _, _, output, manifest_path, manifest_sha, schedule_sha = execute(
        tmp_path, cases=("case-01",), arms=("mini",)
    )
    unit_receipt_path = next((output / "units").glob("*/unit_receipt.json"))
    unit_receipt = json.loads(unit_receipt_path.read_text(encoding="utf-8"))
    unit_receipt["caseId"] = "case-attacker"
    unit_receipt["receiptSha256"] = runner.canonical_digest(
        {
            key: value
            for key, value in unit_receipt.items()
            if key != "receiptSha256"
        }
    )
    write_json(unit_receipt_path, unit_receipt)
    with pytest.raises(runner.CampaignIntegrityError, match="artifact tamper"):
        synthetic_run(
            unit_manifest_path=manifest_path,
            expected_unit_manifest_file_sha256=manifest_sha,
            schedule_path=manifest_path.parent / "schedule.json",
            expected_schedule_file_sha256=schedule_sha,
            output_dir=output,
            process_factory=lambda *args, **kwargs: pytest.fail("must not call"),
        )

    second = tmp_path / "second"
    _, _, output, manifest_path, manifest_sha, schedule_sha = execute(
        second, cases=("case-01",), arms=("mini",)
    )
    campaign_path = output / "campaign_receipt.json"
    campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
    campaign["scientificRows"] = 999
    campaign["receiptSha256"] = runner.canonical_digest(
        {key: value for key, value in campaign.items() if key != "receiptSha256"}
    )
    write_json(campaign_path, campaign)
    with pytest.raises(runner.CampaignIntegrityError, match="aggregate tamper"):
        synthetic_run(
            unit_manifest_path=manifest_path,
            expected_unit_manifest_file_sha256=manifest_sha,
            schedule_path=manifest_path.parent / "schedule.json",
            expected_schedule_file_sha256=schedule_sha,
            output_dir=output,
            process_factory=lambda *args, **kwargs: pytest.fail("must not call"),
        )


def test_duplicate_thread_across_singletons_invalidates_campaign(tmp_path: Path) -> None:
    manifest_path, manifest_sha, units = make_campaign(tmp_path / "frozen")
    schedule_path, schedule_sha, _ = build_schedule(manifest_path, manifest_sha)
    with pytest.raises(runner.CampaignIntegrityError, match="thread IDs"):
        synthetic_run(
            unit_manifest_path=manifest_path,
            expected_unit_manifest_file_sha256=manifest_sha,
            schedule_path=schedule_path,
            expected_schedule_file_sha256=schedule_sha,
            output_dir=tmp_path / "run",
            process_factory=FakeFactory(units, duplicate_thread=True),
            monotonic=ticking_clock(),
        )
    assert not (tmp_path / "run" / "campaign_receipt.json").exists()


@pytest.mark.parametrize("link_level", ["units", "unit"])
def test_output_descendant_symlinks_reject_before_process_or_outside_write(
    tmp_path: Path, link_level: str
) -> None:
    manifest_path, manifest_sha, units = make_campaign(
        tmp_path / "frozen", cases=("case-01",), arms=("mini",)
    )
    schedule_path, schedule_sha, _ = build_schedule(manifest_path, manifest_sha)
    output = tmp_path / "run"
    output.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    if link_level == "units":
        (output / "units").symlink_to(outside, target_is_directory=True)
    else:
        (output / "units").mkdir()
        (output / "units" / next(iter(units))).symlink_to(
            outside, target_is_directory=True
        )
    with pytest.raises(runner.CampaignIntegrityError, match="output directory integrity"):
        synthetic_run(
            unit_manifest_path=manifest_path,
            expected_unit_manifest_file_sha256=manifest_sha,
            schedule_path=schedule_path,
            expected_schedule_file_sha256=schedule_sha,
            output_dir=output,
            process_factory=lambda *args, **kwargs: pytest.fail("must not call"),
        )
    assert list(outside.iterdir()) == []


def test_orphan_unit_artifact_rejects_before_registry_or_process(tmp_path: Path) -> None:
    manifest_path, manifest_sha, units = make_campaign(
        tmp_path / "frozen", cases=("case-01",), arms=("mini",)
    )
    schedule_path, schedule_sha, _ = build_schedule(manifest_path, manifest_sha)
    output = tmp_path / "run"
    unit_root = output / "units" / next(iter(units))
    unit_root.mkdir(parents=True)
    orphan = unit_root / "raw_trace.jsonl"
    orphan.write_bytes(b"preexisting-tamper\n")
    calls = {"count": 0}

    def forbidden_factory(*args: Any, **kwargs: Any) -> Any:
        calls["count"] += 1
        raise AssertionError("must reject before process")

    with pytest.raises(runner.CampaignIntegrityError, match="orphan artifact"):
        synthetic_run(
            unit_manifest_path=manifest_path,
            expected_unit_manifest_file_sha256=manifest_sha,
            schedule_path=schedule_path,
            expected_schedule_file_sha256=schedule_sha,
            output_dir=output,
            process_factory=forbidden_factory,
        )
    assert calls["count"] == 0
    assert orphan.read_bytes() == b"preexisting-tamper\n"
    assert not (unit_root / "attempt_started.json").exists()


def test_external_manifest_and_schedule_hashes_reject_tamper(tmp_path: Path) -> None:
    manifest_path, manifest_sha, _ = make_campaign(tmp_path)
    schedule_path, schedule_sha, _ = build_schedule(manifest_path, manifest_sha)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["scheduleSeed"] = "attacker-resigned-seed"
    manifest["manifestSha256"] = runner.canonical_digest(
        {key: value for key, value in manifest.items() if key != "manifestSha256"}
    )
    write_json(manifest_path, manifest)
    with pytest.raises(runner.CampaignIntegrityError, match="external Git hash"):
        synthetic_run(
            unit_manifest_path=manifest_path,
            expected_unit_manifest_file_sha256=manifest_sha,
            schedule_path=schedule_path,
            expected_schedule_file_sha256=schedule_sha,
            output_dir=tmp_path / "run",
            process_factory=lambda *args, **kwargs: pytest.fail("must not call"),
        )

    # Restore the manifest, then independently corrupt the frozen schedule.
    manifest_path, manifest_sha, _ = make_campaign(tmp_path / "restored")
    schedule_path, schedule_sha, _ = build_schedule(manifest_path, manifest_sha)
    schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
    schedule["orderedUnitIds"] = list(reversed(schedule["orderedUnitIds"]))
    schedule["orderedUnitIdsSha256"] = runner.canonical_digest(
        schedule["orderedUnitIds"]
    )
    schedule["scheduleSha256"] = runner.canonical_digest(
        {key: value for key, value in schedule.items() if key != "scheduleSha256"}
    )
    write_json(schedule_path, schedule)
    with pytest.raises(runner.CampaignIntegrityError, match="external Git hash"):
        synthetic_run(
            unit_manifest_path=manifest_path,
            expected_unit_manifest_file_sha256=manifest_sha,
            schedule_path=schedule_path,
            expected_schedule_file_sha256=schedule_sha,
            output_dir=tmp_path / "run-2",
            process_factory=lambda *args, **kwargs: pytest.fail("must not call"),
        )


def test_output_schema_forbids_recursive_gold_or_label_fields(tmp_path: Path) -> None:
    def add_forbidden(schema: dict[str, Any]) -> None:
        schema["properties"]["goldLabel"] = {"type": "string"}

    manifest_path, manifest_sha, _ = make_campaign(
        tmp_path, schema_mutator=add_forbidden
    )
    with pytest.raises(runner.CampaignIntegrityError, match="forbidden key"):
        synthetic_build_schedule(
            unit_manifest_path=manifest_path,
            expected_unit_manifest_file_sha256=manifest_sha,
            output_path=tmp_path / "schedule.json",
        )


@pytest.mark.parametrize("keyword", ["$ref", "$dynamicRef", "$recursiveRef"])
def test_output_schema_forbids_unbound_refs(tmp_path: Path, keyword: str) -> None:
    def add_ref(schema: dict[str, Any]) -> None:
        schema[keyword] = "unfrozen-other-schema.json"

    manifest_path, manifest_sha, _ = make_campaign(
        tmp_path, schema_mutator=add_ref
    )
    with pytest.raises(runner.CampaignIntegrityError, match="references"):
        synthetic_build_schedule(
            unit_manifest_path=manifest_path,
            expected_unit_manifest_file_sha256=manifest_sha,
            output_path=tmp_path / "schedule.json",
        )


@pytest.mark.parametrize(
    "forced_outcome_schema",
    [{"const": "인용됨"}, {"enum": ["인용됨"]}],
)
def test_scientific_schema_cannot_force_a_single_outcome(
    tmp_path: Path, forced_outcome_schema: dict[str, Any]
) -> None:
    def force(schema: dict[str, Any]) -> None:
        schema["properties"]["outcome"] = forced_outcome_schema

    manifest_path, manifest_sha, _ = make_campaign(tmp_path, schema_mutator=force)
    with pytest.raises(runner.CampaignIntegrityError, match="scientific output schema"):
        synthetic_build_schedule(
            unit_manifest_path=manifest_path,
            expected_unit_manifest_file_sha256=manifest_sha,
            output_path=tmp_path / "schedule.json",
        )


def test_each_case_arm_has_exactly_one_scientific_output_stage(tmp_path: Path) -> None:
    manifest_path, _, _ = make_campaign(
        tmp_path, cases=("case-01",), arms=("mini",)
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    second = copy.deepcopy(manifest["units"][0])
    second["unitId"] = "case-01--mini--second-answer"
    second["stageId"] = "second-answer"
    manifest["units"].append(second)
    manifest["manifestSha256"] = runner.canonical_digest(
        {key: value for key, value in manifest.items() if key != "manifestSha256"}
    )
    write_json(manifest_path, manifest)
    with pytest.raises(runner.CampaignIntegrityError, match="scientific case/arm"):
        synthetic_build_schedule(
            unit_manifest_path=manifest_path,
            expected_unit_manifest_file_sha256=runner.sha256_file(manifest_path),
            output_path=tmp_path / "schedule.json",
        )


def test_execution_identity_or_retry_setting_cannot_be_resigned(
    tmp_path: Path,
) -> None:
    manifest_path, _, _ = make_campaign(tmp_path)
    for field, value in (
        ("codexVersion", "codex-cli 999.0.0"),
        ("transportRetryCount", 1),
        ("strictConfigArgv", ["--unsafe"]),
    ):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["executionConfig"][field] = value
        manifest["manifestSha256"] = runner.canonical_digest(
            {key: item for key, item in manifest.items() if key != "manifestSha256"}
        )
        changed = tmp_path / f"changed-{field}.json"
        write_json(changed, manifest)
        with pytest.raises(runner.CampaignIntegrityError, match="execution config"):
            synthetic_build_schedule(
                unit_manifest_path=changed,
                expected_unit_manifest_file_sha256=runner.sha256_file(changed),
                output_path=tmp_path / f"schedule-{field}.json",
            )


def test_no_model_runtime_preflight_checks_exact_version_and_feature_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = tmp_path / "codex"
    executable.write_bytes(b"synthetic identity probe executable\n")
    executable.chmod(0o700)
    feature_stdout = b"alpha stable true\nbeta experimental false\n"
    snapshot = [
        {"name": "alpha", "stage": "stable", "enabled": True},
        {"name": "beta", "stage": "experimental", "enabled": False},
    ]
    monkeypatch.setattr(runner, "FEATURE_COUNT", 2)
    monkeypatch.setattr(
        runner, "FEATURE_LIST_STDOUT_SHA256", runner.sha256_bytes(feature_stdout)
    )
    monkeypatch.setattr(
        runner, "FEATURE_SNAPSHOT_SHA256", runner.canonical_digest(snapshot)
    )
    config = execution_config(executable)
    observed_commands: list[list[str]] = []

    class Completed:
        returncode = 0
        stderr = b""

        def __init__(self, stdout: bytes) -> None:
            self.stdout = stdout

    def fake_run(command: list[str], **kwargs: Any) -> Completed:
        observed_commands.append(command)
        assert kwargs["env"]["CODEX_HOME"] == runner.CODEX_HOME
        if command[-1] == "--version":
            return Completed((runner.CODEX_VERSION + "\n").encode())
        assert command[-2:] == ["features", "list"]
        return Completed(feature_stdout)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    identity = runner.verify_runtime_identity(config)
    assert identity["featureCount"] == 2
    assert identity["featureSnapshotSha256"] == runner.canonical_digest(snapshot)
    assert observed_commands == [
        [str(executable), "--version"],
        [str(executable), "features", "list"],
    ]


def test_manifest_requires_live_runner_code_hash(tmp_path: Path) -> None:
    manifest_path, _, _ = make_campaign(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["codeHashes"][str(Path(runner.__file__).resolve())] = "0" * 64
    manifest["manifestSha256"] = runner.canonical_digest(
        {key: value for key, value in manifest.items() if key != "manifestSha256"}
    )
    write_json(manifest_path, manifest)
    with pytest.raises(runner.CampaignIntegrityError, match="runner code binding"):
        synthetic_build_schedule(
            unit_manifest_path=manifest_path,
            expected_unit_manifest_file_sha256=runner.sha256_file(manifest_path),
            output_path=tmp_path / "schedule.json",
        )


def test_campaign_receipt_and_unit_registry_are_exact_minimal_schemas(
    tmp_path: Path,
) -> None:
    receipt, _, output, _, _, _ = execute(
        tmp_path, cases=("case-01",), arms=("mini",)
    )
    assert set(receipt) == runner.CAMPAIGN_RECEIPT_KEYS
    unit_root = next((output / "units").iterdir())
    registry = json.loads(
        (unit_root / "attempt_started.json").read_text(encoding="utf-8")
    )
    unit_receipt = json.loads(
        (unit_root / "unit_receipt.json").read_text(encoding="utf-8")
    )
    assert set(registry) == runner.REGISTRY_KEYS
    assert set(unit_receipt) == runner.UNIT_RECEIPT_KEYS
    assert registry["semanticAttemptOrdinal"] == 1
    assert registry["semanticRetryCount"] == 0
    assert registry["transportRetryCount"] == 0
    assert unit_receipt["processInvocationCount"] == 1
    assert unit_receipt["completedAgentMessageCount"] == 1


def git(repo: Path, *arguments: str) -> str:
    completed = runner.subprocess.run(
        ["git", "-C", str(repo), *arguments],
        stdout=runner.subprocess.PIPE,
        stderr=runner.subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr.decode(errors="replace")
    return completed.stdout.decode().strip()


def test_real_two_phase_git_anchor_binds_source_and_campaign_before_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "campaign-repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "Synthetic Test")
    git(repo, "config", "user.email", "synthetic@example.invalid")

    fake_runner = repo / "tools" / "run_singleton_legal_campaign.py"
    fake_runner.parent.mkdir(parents=True)
    fake_runner.write_bytes(Path(runner.__file__).read_bytes())
    monkeypatch.setattr(runner, "__file__", str(fake_runner))
    manifest_path, _, units = make_campaign(
        repo / "campaign", cases=("case-01",), arms=("mini",)
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_path.unlink()
    git(repo, "add", "tools", "campaign/answer-schema.json", "campaign/packets", "campaign/frozen-codex")
    git(repo, "commit", "-q", "-m", "source freeze")
    source_commit = git(repo, "rev-parse", "HEAD")
    source_tree = git(repo, "rev-parse", "HEAD^{tree}")
    manifest["gitAnchor"] = {
        "status": "committed_before_calls",
        "commit": source_commit,
        "tree": source_tree,
        "dirty": False,
    }
    manifest["manifestSha256"] = runner.canonical_digest(
        {key: value for key, value in manifest.items() if key != "manifestSha256"}
    )
    write_json(manifest_path, manifest)
    manifest_file_sha = runner.sha256_file(manifest_path)
    schedule_path = repo / "campaign" / "schedule.json"
    runner.build_schedule_manifest(
        unit_manifest_path=manifest_path,
        expected_unit_manifest_file_sha256=manifest_file_sha,
        output_path=schedule_path,
    )
    schedule_file_sha = runner.sha256_file(schedule_path)
    git(repo, "add", "campaign/unit-manifest.json", "campaign/schedule.json")
    git(repo, "commit", "-q", "-m", "pre-call campaign freeze")
    campaign_commit = git(repo, "rev-parse", "HEAD")
    assert git(repo, "status", "--porcelain=v1", "--untracked-files=all") == ""

    factory = FakeFactory(units)
    receipt = runner.run_campaign(
        unit_manifest_path=manifest_path,
        expected_unit_manifest_file_sha256=manifest_file_sha,
        schedule_path=schedule_path,
        expected_schedule_file_sha256=schedule_file_sha,
        expected_campaign_git_commit=campaign_commit,
        output_dir=tmp_path / "outside-repo-output",
        process_factory=factory,
        monotonic=ticking_clock(),
        runtime_identity_verifier=accept_runtime_identity,
    )
    assert len(factory.calls) == 1
    assert receipt["sourceGitCommit"] == source_commit
    assert receipt["sourceGitTree"] == source_tree
    assert receipt["campaignGitCommit"] == campaign_commit

    with pytest.raises(runner.CampaignIntegrityError, match="HEAD mismatch"):
        runner.run_campaign(
            unit_manifest_path=manifest_path,
            expected_unit_manifest_file_sha256=manifest_file_sha,
            schedule_path=schedule_path,
            expected_schedule_file_sha256=schedule_file_sha,
            expected_campaign_git_commit="d" * 40,
            output_dir=tmp_path / "must-not-exist",
            process_factory=lambda *args, **kwargs: pytest.fail("must not call"),
            runtime_identity_verifier=accept_runtime_identity,
        )
