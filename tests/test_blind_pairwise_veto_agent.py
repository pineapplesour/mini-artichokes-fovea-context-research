from __future__ import annotations

import json
from pathlib import Path
from types import ModuleType

import pytest

from tools import run_blind_pairwise_veto_agent as runner


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def prepared_bundle(tmp_path: Path) -> Path:
    campaign = tmp_path / "campaign"
    input_dir = campaign / "veto/input"
    output_dir = campaign / "veto/output"
    output_dir.mkdir(parents=True)
    questions = [
        {"id": "q1", "responseFormat": "mcq", "language": "en", "prompt": "Select the correct answer."},
        {"id": "q2", "responseFormat": "mcq", "language": "en", "prompt": "Select the best answer."},
        {"id": "q3", "responseFormat": "mcq", "language": "en", "prompt": "Select the least suitable answer."},
    ]
    pairs = [
        {"id": "q1", "leftAnswer": "alpha", "rightAnswer": "beta"},
        {"id": "q3", "leftAnswer": "gamma", "rightAnswer": "delta"},
    ]
    ids = [row["id"] for row in pairs]
    write_jsonl(input_dir / "questions.jsonl", questions)
    write_jsonl(input_dir / "candidate_pairs.jsonl", pairs)
    write_json(input_dir / "expected_certificate_ids.json", {"count": len(ids), "ids": ids})
    (input_dir / "RUN_INSTRUCTIONS.md").write_text("Read every row and write certificates.jsonl.\n", encoding="utf-8")

    implementation_hashes = {
        str(path.resolve()): runner.sha256_file(path.resolve()) for path in runner.FROZEN_IMPLEMENTATION_PATHS
    }
    freeze = {
        "schemaVersion": 1,
        "status": "prepared_no_model_calls",
        "protocol": runner.PROTOCOL,
        "sourceCampaign": str((tmp_path / "source").resolve()),
        "sourceFreezeSha256": "1" * 64,
        "sourceFreezeFileSha256": "2" * 64,
        "sourceQuestionsSha256": "3" * 64,
        "sourceOverlapManifestSha256": "4" * 64,
        "sourceCandidateAnswersSha256": {"base": "5" * 64, "auxiliary_1": "6" * 64, "auxiliary_2": "7" * 64},
        "questionsPath": "input/questions.jsonl",
        "questionsSha256": runner.sha256_file(input_dir / "questions.jsonl"),
        "pairsPath": "input/candidate_pairs.jsonl",
        "pairsSha256": runner.sha256_file(input_dir / "candidate_pairs.jsonl"),
        "expectedCertificateIdsPath": "input/expected_certificate_ids.json",
        "expectedCertificateIdsFileSha256": runner.sha256_file(input_dir / "expected_certificate_ids.json"),
        "expectedCertificateIdsSha256": runner.canonical_digest(ids),
        "instructionsSha256": runner.sha256_file(input_dir / "RUN_INSTRUCTIONS.md"),
        "roleMappingPath": "control/role_mapping.jsonl",
        "roleMappingSha256": "8" * 64,
        "rotationControlPath": "control/rotation.json",
        "rotationControlSha256": "9" * 64,
        "rotationScheme": "sha256-domain-seed-nul-id-low-bit-v1",
        "rotationSeedSha256": "a" * 64,
        "inventory": {
            "questionRows": len(questions),
            "conflictRows": len(pairs),
            "leftIncumbentRows": 1,
            "rightIncumbentRows": 1,
        },
        "executionConfig": {
            "model": runner.DEFAULT_MODEL,
            "reasoningEffort": runner.DEFAULT_REASONING_EFFORT,
            "verbosity": runner.DEFAULT_VERBOSITY,
            "serviceTier": runner.SERVICE_TIER,
            "nativeWebSearch": False,
            "localCode": True,
            "database": False,
            "skills": False,
            "multiAgent": False,
        },
        "implementationHashes": implementation_hashes,
    }
    freeze["freezeSha256"] = runner.canonical_digest(freeze)
    write_json(campaign / "veto/freeze.json", freeze)
    return campaign


def test_frozen_bundle_verifies_exact_public_hashes_and_implementation_key_format(tmp_path: Path) -> None:
    campaign = prepared_bundle(tmp_path)
    freeze, paths, hashes = runner.verify_frozen_bundle(campaign)

    assert hashes == {
        "questions": runner.sha256_file(paths["questions"]),
        "candidatePairs": runner.sha256_file(paths["candidatePairs"]),
        "expectedCertificateIds": runner.sha256_file(paths["expectedCertificateIds"]),
        "instructions": runner.sha256_file(paths["instructions"]),
    }
    assert set(freeze["implementationHashes"]) == {
        str(path.resolve()) for path in runner.FROZEN_IMPLEMENTATION_PATHS
    }
    assert freeze["implementationHashes"][str(Path(runner.__file__).resolve())] == runner.sha256_file(
        Path(runner.__file__).resolve()
    )

    freeze_path = campaign / "veto/freeze.json"
    tampered = json.loads(freeze_path.read_text(encoding="utf-8"))
    tampered["implementationHashes"] = {
        str(Path(runner.__file__).resolve()): runner.sha256_file(Path(runner.__file__).resolve())
    }
    tampered["freezeSha256"] = runner.canonical_digest(
        {key: value for key, value in tampered.items() if key != "freezeSha256"}
    )
    write_json(freeze_path, tampered)
    with pytest.raises(ValueError, match="exact protocol implementation paths"):
        runner.verify_frozen_bundle(campaign)


def test_frozen_bundle_rejects_public_input_tamper_and_wrong_protocol(tmp_path: Path) -> None:
    campaign = prepared_bundle(tmp_path)
    pairs_path = campaign / "veto/input/candidate_pairs.jsonl"
    pairs_path.write_text(pairs_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="pairsSha256"):
        runner.verify_frozen_bundle(campaign)

    campaign = prepared_bundle(tmp_path / "second")
    freeze_path = campaign / "veto/freeze.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    freeze["protocol"] = "some_other_protocol"
    freeze["freezeSha256"] = runner.canonical_digest(
        {key: value for key, value in freeze.items() if key != "freezeSha256"}
    )
    write_json(freeze_path, freeze)
    with pytest.raises(ValueError, match="unsupported blind-veto protocol"):
        runner.verify_frozen_bundle(campaign)


def test_command_uses_stable_helper_and_native_web_policy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    observed: list[str] = []

    def fake_command(
        *,
        input_dir: Path,
        output_dir: Path,
        codex_home: Path,
        role: str,
        model: str,
        reasoning_effort: str,
        verbosity: str,
        native_web_search: bool,
    ) -> list[str]:
        assert input_dir == common["input_dir"]
        assert output_dir == common["output_dir"]
        assert codex_home == common["codex_home"]
        assert model == runner.DEFAULT_MODEL
        assert reasoning_effort == runner.DEFAULT_REASONING_EFFORT
        assert verbosity == runner.DEFAULT_VERBOSITY
        observed.append(f"{role}:{native_web_search}")
        return ["sealed", role]

    monkeypatch.setattr(runner.plain_runner, "codex_command", fake_command)
    common = {
        "input_dir": tmp_path / "input",
        "output_dir": tmp_path / "output",
        "codex_home": tmp_path / "codex-home",
        "model": runner.DEFAULT_MODEL,
        "reasoning_effort": runner.DEFAULT_REASONING_EFFORT,
        "verbosity": runner.DEFAULT_VERBOSITY,
    }
    assert runner.build_codex_command(**common, native_web_search=True) == ["sealed", "solver"]
    assert runner.build_codex_command(**common, native_web_search=False) == ["sealed", "grader"]
    assert observed == ["solver:True", "grader:False"]
    runner.verify_tool_free_command(["codex", "--config", 'web_search="disabled"'])
    with pytest.raises(ValueError, match="enables native web"):
        runner.verify_tool_free_command(["codex", "--search", "exec", 'web_search="disabled"'])

    campaign = prepared_bundle(tmp_path / "bundle")
    freeze, _, _ = runner.verify_frozen_bundle(campaign)
    config = runner.verify_execution_config(
        freeze,
        model=runner.DEFAULT_MODEL,
        reasoning_effort=runner.DEFAULT_REASONING_EFFORT,
        verbosity=runner.DEFAULT_VERBOSITY,
    )
    assert config["nativeWebSearch"] is False
    freeze["executionConfig"]["nativeWebSearch"] = True
    with pytest.raises(ValueError, match="tool-free protocol"):
        runner.verify_execution_config(
            freeze,
            model=runner.DEFAULT_MODEL,
            reasoning_effort=runner.DEFAULT_REASONING_EFFORT,
            verbosity=runner.DEFAULT_VERBOSITY,
        )


def test_trace_requires_one_well_formed_thread_and_obeys_web_freeze(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    trace = tmp_path / "trace.jsonl"
    write_jsonl(trace, [{"type": "thread.started", "thread_id": "thread-1"}])
    monkeypatch.setattr(
        runner.plain_runner,
        "audit_trace",
        lambda **_kwargs: {"passed": True, "violations": [], "trace": {"webSearchEvents": []}},
    )
    accepted = runner.audit_veto_trace(
        trace_path=trace,
        questions_path=tmp_path / "questions.jsonl",
        return_code=0,
        native_web_search=False,
    )
    assert accepted["passed"] is True
    assert accepted["threadIds"] == ["thread-1"]

    write_jsonl(
        trace,
        [
            {"type": "thread.started", "thread_id": "thread-1"},
            {"type": "thread.started", "thread_id": "thread-2"},
        ],
    )
    rejected = runner.audit_veto_trace(
        trace_path=trace,
        questions_path=tmp_path / "questions.jsonl",
        return_code=0,
        native_web_search=False,
    )
    assert rejected["passed"] is False
    assert "exactly_one_codex_thread_required" in rejected["violations"]

    write_jsonl(
        trace,
        [
            {"type": "thread.started", "thread_id": "thread-1"},
            {"type": "item.started", "item": {"type": "web_search", "query": "general proposition"}},
        ],
    )
    monkeypatch.setattr(
        runner.plain_runner,
        "audit_trace",
        lambda **_kwargs: {"passed": True, "violations": [], "trace": {"webSearchEvents": []}},
    )
    web_rejected = runner.audit_veto_trace(
        trace_path=trace,
        questions_path=tmp_path / "questions.jsonl",
        return_code=0,
        native_web_search=False,
    )
    assert "native_web_used_while_frozen_disabled" in web_rejected["violations"]
    assert web_rejected["rawWebSearchEventCount"] == 1

    write_jsonl(trace, [{"type": "thread.started", "thread_id": "thread-1"}])
    monkeypatch.setattr(
        runner.plain_runner,
        "audit_trace",
        lambda **_kwargs: {
            "passed": True,
            "violations": [],
            "trace": {
                "webSearchEvents": [],
                "commandExecutionEvents": [
                    {"command": "curl https://example.org/general-fact"},
                ],
            },
        },
    )
    shell_network_rejected = runner.audit_veto_trace(
        trace_path=trace,
        questions_path=tmp_path / "questions.jsonl",
        return_code=0,
        native_web_search=False,
    )
    assert shell_network_rejected["passed"] is False
    assert "network_capable_shell_command" in shell_network_rejected["violations"]
    assert shell_network_rejected["networkCapableShellCommandCount"] == 1


def test_jsonl_parser_escapes_valid_unicode_line_separators_without_hiding_lf_records() -> None:
    raw = (
        '{"type":"thread.started","thread_id":"thread-1"}\n'
        '{"type":"item.completed","item":{"type":"agent_message","text":"a'
        + "\u0085"
        + 'b'
        + "\u2028"
        + 'c'
        + "\u2029"
        + 'd"}}\n'
    )
    normalized, counts = runner.parser_safe_jsonl_text(raw)

    assert counts == {"U+0085": 1, "U+2028": 1, "U+2029": 1}
    assert normalized.count("\n") == raw.count("\n") == 2
    assert "\u0085" not in normalized
    assert "\u2028" not in normalized
    assert "\u2029" not in normalized
    assert "\\u0085" in normalized
    assert "\\u2028" in normalized
    assert "\\u2029" in normalized


def test_trace_audit_normalizes_unicode_separators_end_to_end(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    trace = tmp_path / "trace.jsonl"
    trace.write_text(
        '{"type":"thread.started","thread_id":"thread-1"}\n'
        '{"type":"item.completed","item":{"type":"agent_message","text":"a'
        + "\u0085"
        + "b"
        + "\u2028"
        + "c"
        + "\u2029"
        + 'd"}}\n',
        encoding="utf-8",
    )
    observed: dict[str, str] = {}

    def fake_audit_trace(**kwargs: object) -> dict:
        audit_path = Path(str(kwargs["trace_path"]))
        observed["raw"] = audit_path.read_text(encoding="utf-8")
        events = [json.loads(raw) for raw in observed["raw"].split("\n") if raw]
        assert len(events) == 2
        return {"passed": True, "violations": [], "trace": {"webSearchEvents": []}}

    monkeypatch.setattr(runner.plain_runner, "audit_trace", fake_audit_trace)
    report = runner.audit_veto_trace(
        trace_path=trace,
        questions_path=tmp_path / "questions.jsonl",
        return_code=0,
        native_web_search=False,
    )

    assert report["passed"] is True
    assert report["threadIds"] == ["thread-1"]
    assert report["jsonlEscapedUnicodeSeparatorCounts"] == {
        "U+0085": 1,
        "U+2028": 1,
        "U+2029": 1,
    }
    assert "\u0085" not in observed["raw"]
    assert "\\u0085" in observed["raw"]


def test_runtime_receipt_hashes_bind_runner_validator_preparer_and_transitive_parser() -> None:
    validator_module, validator = runner.strict_validator()
    hashes = runner.implementation_hashes(validator_module)

    assert callable(validator)
    for required_path in (
        "tools/run_blind_pairwise_veto_agent.py",
        "tools/run_plain_codex_file_agent.py",
        "tools/benchmark_provider.py",
        "tools/validate_blind_pairwise_veto.py",
        "tools/prepare_blind_pairwise_veto.py",
        "tools/prepare_plain_codex_file_benchmark.py",
        "tools/run_ensemble_file_agent.py",
    ):
        assert any(key.endswith(f"|{required_path}") for key in hashes), required_path


def make_accepted_resume_receipt(
    *,
    campaign: Path,
    paths: dict[str, Path],
    freeze: dict,
    input_hashes: dict[str, str],
    execution_config: dict,
    implementations: dict[str, str],
    cli: dict,
) -> dict:
    write_jsonl(paths["trace"], [{"type": "thread.started", "thread_id": "thread-1"}])
    paths["stderr"].write_text("", encoding="utf-8")
    write_jsonl(paths["certificates"], [{"id": "q1"}])
    paths["lastMessage"].write_text("complete\n", encoding="utf-8")
    write_json(paths["validationReport"], {"passed": True})
    receipt = {
        "schemaVersion": 1,
        "status": "accepted",
        "protocol": runner.PROTOCOL,
        "semanticModelInvocations": 1,
        "freezeSha256": freeze["freezeSha256"],
        "inputFileSha256": input_hashes,
        "executionConfig": execution_config,
        "implementationHashes": implementations,
        "codexCli": cli,
        "process": {"exitCode": 0, "timedOut": False},
        "policyAudit": {"passed": True},
        "artifactValidation": {"passed": True},
        "artifacts": {
            "rawTraceSha256": runner.sha256_file(paths["trace"]),
            "stderrSha256": runner.sha256_file(paths["stderr"]),
            "certificatesSha256": runner.sha256_file(paths["certificates"]),
            "lastMessageSha256": runner.sha256_file(paths["lastMessage"]),
            "validationReportSha256": runner.sha256_file(paths["validationReport"]),
            "threadIds": ["thread-1"],
        },
        "acceptedArtifact": "output/certificates.jsonl",
    }
    receipt["receiptSha256"] = runner.receipt_digest(receipt)
    write_json(paths["receipt"], receipt)
    return receipt


def test_resume_revalidates_and_fails_closed_on_receipt_trace_or_certificate_tamper(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    campaign = prepared_bundle(tmp_path)
    freeze, paths, input_hashes = runner.verify_frozen_bundle(campaign)
    execution = runner.verify_execution_config(
        freeze,
        model=runner.DEFAULT_MODEL,
        reasoning_effort=runner.DEFAULT_REASONING_EFFORT,
        verbosity=runner.DEFAULT_VERBOSITY,
    )
    implementations = {"test|tools/test.py": "f" * 64}
    cli = {"version": "test", "commandSha256": "c" * 64}
    receipt = make_accepted_resume_receipt(
        campaign=campaign,
        paths=paths,
        freeze=freeze,
        input_hashes=input_hashes,
        execution_config=execution,
        implementations=implementations,
        cli=cli,
    )
    monkeypatch.setattr(
        runner,
        "audit_veto_trace",
        lambda **_kwargs: {"passed": True, "threadIds": ["thread-1"], "violations": []},
    )

    def validator(_campaign: Path, *, write_report: bool = True) -> dict:
        return {"passed": True, "certificatesSha256": runner.sha256_file(paths["certificates"])}

    resumed = runner.verify_resume(
        campaign_dir=campaign,
        paths=paths,
        freeze=freeze,
        input_hashes=input_hashes,
        execution_config=execution,
        implementations=implementations,
        cli_identity=cli,
        validator=validator,
    )
    assert resumed["status"] == "resumed_complete_without_model_call"
    assert resumed["semanticModelInvocations"] == 0

    paths["certificates"].write_text(paths["certificates"].read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(RuntimeError, match="resume_certificates_hash_mismatch"):
        runner.verify_resume(
            campaign_dir=campaign,
            paths=paths,
            freeze=freeze,
            input_hashes=input_hashes,
            execution_config=execution,
            implementations=implementations,
            cli_identity=cli,
            validator=validator,
        )

    write_jsonl(paths["certificates"], [{"id": "q1"}])
    paths["trace"].write_text(paths["trace"].read_text(encoding="utf-8") + "{}\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="resume_trace_hash_mismatch"):
        runner.verify_resume(
            campaign_dir=campaign,
            paths=paths,
            freeze=freeze,
            input_hashes=input_hashes,
            execution_config=execution,
            implementations=implementations,
            cli_identity=cli,
            validator=validator,
        )

    paths["trace"].write_text('{"type":"thread.started","thread_id":"thread-1"}\n', encoding="utf-8")
    receipt["status"] = "incomplete"
    write_json(paths["receipt"], receipt)
    with pytest.raises(RuntimeError, match="receipt_self_hash_mismatch"):
        runner.verify_resume(
            campaign_dir=campaign,
            paths=paths,
            freeze=freeze,
            input_hashes=input_hashes,
            execution_config=execution,
            implementations=implementations,
            cli_identity=cli,
            validator=validator,
        )


def test_fresh_run_invokes_one_process_and_binds_trace_thread_certificate_and_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    campaign = prepared_bundle(tmp_path)
    paths = runner.campaign_paths(campaign)
    calls = {"count": 0}
    validator_module = ModuleType("tools.validate_blind_pairwise_veto")
    validator_module.__file__ = str(runner.REPO_ROOT / "tools/validate_blind_pairwise_veto.py")

    def validator(_campaign: Path, *, write_report: bool = True) -> dict:
        report = {"passed": True, "certificatesSha256": runner.sha256_file(paths["certificates"])}
        if write_report:
            write_json(paths["validationReport"], report)
        return report

    monkeypatch.setattr(runner, "strict_validator", lambda: (validator_module, validator))
    monkeypatch.setattr(runner, "implementation_hashes", lambda _module: {"runner": "r" * 64})
    monkeypatch.setattr(
        runner,
        "build_codex_command",
        lambda **_kwargs: ["fake-codex", "exec", "--config", 'web_search="disabled"'],
    )
    monkeypatch.setattr(
        runner,
        "codex_cli_identity",
        lambda command: {
            "version": "codex-test",
            "commandSha256": runner.canonical_digest(command),
            "commandArgumentCount": len(command),
        },
    )
    monkeypatch.setattr(runner.plain_runner, "isolation_probe", lambda **_kwargs: {"passed": True})
    monkeypatch.setattr(
        runner,
        "audit_veto_trace",
        lambda **_kwargs: {
            "policy": "test",
            "passed": True,
            "violations": [],
            "threadStartedEventCount": 1,
            "threadIds": ["thread-fresh"],
            "malformedThreadStartedEvents": 0,
        },
    )

    class FakeStdin:
        def __init__(self) -> None:
            self.value = ""

        def write(self, value: str) -> None:
            self.value += value

        def close(self) -> None:
            return None

    class FakeProcess:
        pid = 12345

        def __init__(self, _command: list[str], **kwargs: object) -> None:
            calls["count"] += 1
            self.stdin = FakeStdin()
            trace_stream = kwargs["stdout"]
            assert hasattr(trace_stream, "write")
            trace_stream.write('{"type":"thread.started","thread_id":"thread-fresh"}\n')
            trace_stream.flush()
            write_jsonl(paths["certificates"], [{"id": "q1"}])
            paths["lastMessage"].write_text("complete\n", encoding="utf-8")

        def wait(self, timeout: int) -> int:
            assert timeout > 0
            return 0

    monkeypatch.setattr(runner.subprocess, "Popen", FakeProcess)
    receipt = runner.run_agent(
        campaign_dir=campaign,
        codex_home=tmp_path / "codex-home",
        model=runner.DEFAULT_MODEL,
        reasoning_effort=runner.DEFAULT_REASONING_EFFORT,
        verbosity=runner.DEFAULT_VERBOSITY,
        timeout_seconds=60,
        resume=False,
    )

    assert calls["count"] == 1
    assert receipt["status"] == "accepted"
    assert receipt["semanticModelInvocations"] == 1
    assert receipt["executionConfig"]["serviceTier"] == "default"
    assert receipt["executionConfig"]["nativeWebSearch"] is False
    assert receipt["artifacts"]["rawTraceSha256"] == runner.sha256_file(paths["trace"])
    assert receipt["artifacts"]["certificatesSha256"] == runner.sha256_file(paths["certificates"])
    assert receipt["artifacts"]["threadIds"] == ["thread-fresh"]
    assert receipt["process"]["startedAtUtc"].endswith("Z")
    assert receipt["process"]["endedAtUtc"].endswith("Z")
    assert receipt["receiptSha256"] == runner.receipt_digest(receipt)
    assert json.loads(paths["receipt"].read_text(encoding="utf-8")) == receipt
