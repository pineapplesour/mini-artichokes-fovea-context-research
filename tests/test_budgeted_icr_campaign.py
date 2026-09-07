from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from tools import run_budgeted_icr_campaign as icr


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def rewrite_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def public_file(tmp_path: Path) -> Path:
    path = tmp_path / "public.jsonl"
    write_jsonl(
        path,
        [
            {"id": "case-b", "prompt": "주어진 사실만으로 청구가 인용되는지 기각되는지 예측하라."},
            {"id": "case-a", "prompt": "증거와 항변을 비교해 결과를 예측하라.", "extra": "public"},
        ],
    )
    return path


def codex_home(tmp_path: Path) -> Path:
    path = tmp_path / "codex-home"
    path.mkdir()
    (path / "auth.json").write_text("{}\n", encoding="utf-8")
    return path


class FakeProcess:
    def __init__(self, return_code: int):
        self.return_code = return_code
        self.stdin = io.StringIO()
        self.pid = 987654

    def wait(self, timeout: int) -> int:
        return self.return_code


class FakeCodex:
    def __init__(
        self,
        *,
        first_transport_failure: bool = False,
        invalid_conclusion: bool = False,
        mark_stage_nine: bool = False,
    ):
        self.calls = 0
        self.first_transport_failure = first_transport_failure
        self.invalid_conclusion = invalid_conclusion
        self.mark_stage_nine = mark_stage_nine

    def command(self, **kwargs) -> list[str]:
        return [
            "mock-codex",
            str(kwargs["input_dir"]),
            str(kwargs["output_dir"]),
            'web_search="disabled"',
        ]

    def popen(self, command, *, stdin, stdout, stderr, text, start_new_session):
        del stdin, stderr, text, start_new_session
        self.calls += 1
        input_dir = Path(command[1])
        output_dir = Path(command[2])
        request = json.loads((input_dir / "stage_request.json").read_text(encoding="utf-8"))
        expected = json.loads((input_dir / "expected_ids.json").read_text(encoding="utf-8"))["ids"]
        fail = self.first_transport_failure and self.calls == 1
        stdout.write(json.dumps({"type": "thread.started", "thread_id": f"thread-{self.calls}"}) + "\n")
        stdout.write(
            json.dumps(
                {
                    "type": "turn.completed",
                    "usage": {
                        "input_tokens": 100,
                        "cached_input_tokens": 10,
                        "output_tokens": 20,
                        "reasoning_output_tokens": 5,
                        "total_tokens": 120,
                    },
                }
            )
            + "\n"
        )
        stdout.flush()
        if not fail:
            kind = request["stage"]["outputKind"]
            if kind == "candidate":
                rows = [
                    {
                        "id": case_id,
                        "conclusion": (
                            "미정"
                            if self.invalid_conclusion
                            else (
                                "인용됨"
                                if self.mark_stage_nine and request["stageNumber"] == 9
                                else ("인용됨" if case_id.endswith("a") else "기각")
                            )
                        ),
                        "reasoning": f"{request['stage']['name']} reasoning for {case_id}",
                    }
                    for case_id in expected
                ]
            elif kind == "suggestions":
                rows = [{"id": case_id, "suggestions": f"check {case_id}"} for case_id in expected]
            else:
                rows = [{"id": case_id, "memory": f"remember {case_id}"} for case_id in expected]
            write_jsonl(output_dir / request["outputFile"], rows)
            (output_dir / "last_message.txt").write_text("complete\n", encoding="utf-8")
        return FakeProcess(1 if fail else 0)


def install_fake_runtime(monkeypatch: pytest.MonkeyPatch, fake: FakeCodex) -> None:
    monkeypatch.setattr(icr.sealed_runner, "build_codex_command", fake.command)
    monkeypatch.setattr(icr.sealed_runner, "verify_tool_free_command", lambda _command: None)


def test_profiles_freeze_exact_call_structures() -> None:
    icr4 = icr.PROFILES["budgeted_icr4_memory_revision"]
    icr5 = icr.PROFILES["icr5_one_cycle_self_improve"]
    test37 = icr.PROFILES["test37_architecture_icr10"]
    assert [stage["name"] for stage in icr4["stages"]] == [
        "initial",
        "suggest-1",
        "memory-1",
        "final-revise",
    ]
    assert icr4["stages"][2]["dependencies"] == {"candidate": 1, "suggestions": 2}
    assert icr4["stages"][3]["dependencies"] == {"candidate": 1, "suggestions": 2, "memory": 3}
    assert icr4["terminalCandidateStage"] == 4
    assert [stage["name"] for stage in icr5["stages"]] == [
        "initial",
        "suggest-1",
        "revise-1",
        "memory-1",
        "self-improve",
    ]
    assert icr5["terminalCandidateStage"] == 5
    assert len(test37["stages"]) == 10
    assert test37["terminalCandidateStage"] == 9
    assert (test37["callGraphExact"], test37["promptsTaskAdapted"], test37["runtimeExact"]) == (
        True,
        True,
        False,
    )
    assert [stage["dependencies"] for stage in test37["stages"]] == [
        {},
        {"candidate": 1},
        {"candidate": 1, "suggestions": 2},
        {"candidate": 3, "suggestions": 2},
        {"candidate": 3, "memory": 4},
        {"candidate": 3, "suggestions": 5, "memory": 4},
        {"candidate": 6, "suggestions": 5, "memory": 4},
        {"candidate": 6, "memory": 7},
        {"candidate": 6, "suggestions": 8, "memory": 7},
        {"candidate": 9, "suggestions": 8, "memory": 7},
    ]


def test_prepare_is_deterministic_hash_bound_and_rejects_tamper(tmp_path: Path) -> None:
    public = public_file(tmp_path)
    first = tmp_path / "first"
    second = tmp_path / "second"
    freeze1 = icr.prepare_campaign(
        public_path=public,
        campaign_dir=first,
        profile="icr5_one_cycle_self_improve",
        shard_size=1,
        shard_seed="seed",
        timeout_seconds=30,
        max_transport_attempts=2,
    )
    freeze2 = icr.prepare_campaign(
        public_path=public,
        campaign_dir=second,
        profile="icr5_one_cycle_self_improve",
        shard_size=1,
        shard_seed="seed",
        timeout_seconds=30,
        max_transport_attempts=2,
    )
    assert freeze1["sharding"]["manifest"] == freeze2["sharding"]["manifest"]
    assert freeze1["freezeSha256"] == freeze2["freezeSha256"]
    assert freeze1["runPolicy"] == {"timeoutSeconds": 30, "maxTransportAttempts": 2}
    assert icr.verify_freeze(first)["inventory"] == {"rows": 2, "shards": 2, "stagesPerShard": 5}

    with pytest.raises(ValueError, match="differ from frozen runPolicy"):
        icr.run_campaign(
            campaign_dir=first,
            codex_home=codex_home(tmp_path),
            timeout_seconds=31,
            max_transport_attempts=2,
            resume=False,
        )

    shard_path = first / "shards" / freeze1["sharding"]["manifest"][0]["shardId"] / "questions.jsonl"
    shard_path.write_text(shard_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="questions_hash_mismatch"):
        icr.verify_freeze(first)


def test_mocked_icr5_run_validates_and_resume_makes_zero_calls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    campaign = tmp_path / "campaign"
    icr.prepare_campaign(
        public_path=public_file(tmp_path),
        campaign_dir=campaign,
        profile="icr5_one_cycle_self_improve",
        shard_size=2,
        shard_seed="seed",
        timeout_seconds=30,
        max_transport_attempts=2,
    )
    fake = FakeCodex()
    install_fake_runtime(monkeypatch, fake)
    receipt = icr.run_campaign(
        campaign_dir=campaign,
        codex_home=codex_home(tmp_path),
        timeout_seconds=30,
        max_transport_attempts=2,
        resume=False,
        popen_factory=fake.popen,
        isolation_probe=lambda **_kwargs: {"passed": True},
    )
    assert fake.calls == 5
    assert receipt["semanticAcceptedResponses"] == 5
    assert receipt["actualModelInvocations"] == 5
    assert receipt["tokenUsageAllAttempts"]["totalTokens"] == 600
    answers = icr.load_jsonl(campaign / "final/answers.jsonl")
    assert answers == [
        {"id": "case-b", "finalAnswer": "기각"},
        {"id": "case-a", "finalAnswer": "인용됨"},
    ]
    assert icr.validate_campaign(campaign)["answersRows"] == 2

    with pytest.raises(ValueError, match="differ from frozen runPolicy"):
        icr.run_campaign(
            campaign_dir=campaign,
            codex_home=tmp_path / "codex-home",
            timeout_seconds=30,
            max_transport_attempts=1,
            resume=True,
            popen_factory=fake.popen,
            isolation_probe=lambda **_kwargs: {"passed": True},
        )
    assert fake.calls == 5

    resumed = icr.run_campaign(
        campaign_dir=campaign,
        codex_home=tmp_path / "codex-home",
        timeout_seconds=30,
        max_transport_attempts=2,
        resume=True,
        popen_factory=fake.popen,
        isolation_probe=lambda **_kwargs: {"passed": True},
    )
    assert resumed["status"] == "resumed_complete_without_model_call"
    assert fake.calls == 5


def test_mocked_test37_runs_ten_stages_and_finalizes_stage_nine(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    campaign = tmp_path / "campaign"
    freeze = icr.prepare_campaign(
        public_path=public_file(tmp_path),
        campaign_dir=campaign,
        profile="test37_architecture_icr10",
        shard_size=2,
        shard_seed="seed",
        timeout_seconds=30,
        max_transport_attempts=1,
    )
    fake = FakeCodex(mark_stage_nine=True)
    install_fake_runtime(monkeypatch, fake)
    receipt = icr.run_campaign(
        campaign_dir=campaign,
        codex_home=codex_home(tmp_path),
        timeout_seconds=30,
        max_transport_attempts=1,
        resume=False,
        popen_factory=fake.popen,
        isolation_probe=lambda **_kwargs: {"passed": True},
    )
    assert fake.calls == 10
    assert receipt["semanticAcceptedResponses"] == 10
    shard = freeze["sharding"]["manifest"][0]["shardId"]
    assert (campaign / "shards" / shard / "stages/10-memory-3/stage_receipt.json").is_file()
    stage9 = campaign / "shards" / shard / "stages/09-revise-3/stage_receipt.json"
    assert icr.load_json(stage9)["status"] == "accepted"
    assert receipt["tokenUsageAllAttempts"]["totalTokens"] == 1_200
    assert icr.load_jsonl(campaign / "final/answers.jsonl") == [
        {"id": "case-b", "finalAnswer": "인용됨"},
        {"id": "case-a", "finalAnswer": "인용됨"},
    ]
    assert icr.validate_campaign(campaign)["profile"] == "test37_architecture_icr10"


def test_transport_retry_is_accounted_but_semantic_rejection_is_not_retried(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    campaign = tmp_path / "retry"
    icr.prepare_campaign(
        public_path=public_file(tmp_path),
        campaign_dir=campaign,
        profile="icr5_one_cycle_self_improve",
        shard_size=2,
        shard_seed="seed",
        timeout_seconds=30,
        max_transport_attempts=2,
    )
    retry_fake = FakeCodex(first_transport_failure=True)
    install_fake_runtime(monkeypatch, retry_fake)
    receipt = icr.run_campaign(
        campaign_dir=campaign,
        codex_home=codex_home(tmp_path),
        timeout_seconds=30,
        max_transport_attempts=2,
        resume=False,
        popen_factory=retry_fake.popen,
        isolation_probe=lambda **_kwargs: {"passed": True},
    )
    assert receipt["semanticAcceptedResponses"] == 5
    assert receipt["actualModelInvocations"] == 6
    assert receipt["transportRetryCount"] == 1
    assert receipt["tokenUsageAllAttempts"]["totalTokens"] == 720

    bad_campaign = tmp_path / "bad"
    icr.prepare_campaign(
        public_path=public_file(tmp_path),
        campaign_dir=bad_campaign,
        profile="icr5_one_cycle_self_improve",
        shard_size=2,
        shard_seed="seed",
        timeout_seconds=30,
        max_transport_attempts=2,
    )
    bad_fake = FakeCodex(invalid_conclusion=True)
    install_fake_runtime(monkeypatch, bad_fake)
    with pytest.raises(RuntimeError, match="did not produce an accepted response"):
        icr.run_campaign(
            campaign_dir=bad_campaign,
            codex_home=tmp_path / "codex-home",
            timeout_seconds=30,
            max_transport_attempts=2,
            resume=False,
            popen_factory=bad_fake.popen,
            isolation_probe=lambda **_kwargs: {"passed": True},
        )
    assert bad_fake.calls == 1


def test_resume_rejects_prior_stage_output_tamper(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    campaign = tmp_path / "campaign"
    freeze = icr.prepare_campaign(
        public_path=public_file(tmp_path),
        campaign_dir=campaign,
        profile="icr5_one_cycle_self_improve",
        shard_size=2,
        shard_seed="seed",
        timeout_seconds=30,
        max_transport_attempts=1,
    )
    fake = FakeCodex()
    install_fake_runtime(monkeypatch, fake)
    icr.run_campaign(
        campaign_dir=campaign,
        codex_home=codex_home(tmp_path),
        timeout_seconds=30,
        max_transport_attempts=1,
        resume=False,
        popen_factory=fake.popen,
        isolation_probe=lambda **_kwargs: {"passed": True},
    )
    shard = freeze["sharding"]["manifest"][0]["shardId"]
    stage1 = campaign / "shards" / shard / "stages/01-initial"
    receipt = icr.load_json(stage1 / "stage_receipt.json")
    output = stage1 / receipt["acceptedOutputPath"]
    output.write_text(output.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="attempt_1_artifacts_mismatch"):
        icr.run_campaign(
            campaign_dir=campaign,
            codex_home=tmp_path / "codex-home",
            timeout_seconds=30,
            max_transport_attempts=1,
            resume=True,
            popen_factory=fake.popen,
            isolation_probe=lambda **_kwargs: {"passed": True},
        )


def test_validation_recomputes_attempt_evidence_and_campaign_totals(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    campaign = tmp_path / "campaign"
    freeze = icr.prepare_campaign(
        public_path=public_file(tmp_path),
        campaign_dir=campaign,
        profile="budgeted_icr4_memory_revision",
        shard_size=2,
        shard_seed="seed",
        timeout_seconds=30,
        max_transport_attempts=1,
    )
    fake = FakeCodex()
    install_fake_runtime(monkeypatch, fake)
    icr.run_campaign(
        campaign_dir=campaign,
        codex_home=codex_home(tmp_path),
        timeout_seconds=30,
        max_transport_attempts=1,
        resume=False,
        popen_factory=fake.popen,
        isolation_probe=lambda **_kwargs: {"passed": True},
    )
    assert fake.calls == 4

    campaign_receipt_path = campaign / "campaign_receipt.json"
    original_campaign_receipt = icr.load_json(campaign_receipt_path)
    changed_campaign_receipt = dict(original_campaign_receipt)
    changed_campaign_receipt["actualModelInvocations"] = 999
    changed_campaign_receipt["campaignReceiptSha256"] = icr.self_hash(
        changed_campaign_receipt, "campaignReceiptSha256"
    )
    rewrite_json(campaign_receipt_path, changed_campaign_receipt)
    with pytest.raises(ValueError, match="campaign_actualModelInvocations_mismatch"):
        icr.validate_campaign(campaign)
    rewrite_json(campaign_receipt_path, original_campaign_receipt)

    shard = freeze["sharding"]["manifest"][0]["shardId"]
    stage_receipt_path = campaign / "shards" / shard / "stages/01-initial/stage_receipt.json"
    changed_stage_receipt = icr.load_json(stage_receipt_path)
    changed_stage_receipt["attempts"][0]["tokenUsage"]["totalTokens"] = 999
    changed_stage_receipt["tokenUsageAllAttempts"]["totalTokens"] = 999
    changed_stage_receipt["receiptSha256"] = icr.self_hash(changed_stage_receipt, "receiptSha256")
    rewrite_json(stage_receipt_path, changed_stage_receipt)
    with pytest.raises(ValueError, match="attempt_1_tokenUsage_mismatch"):
        icr.validate_campaign(campaign)
