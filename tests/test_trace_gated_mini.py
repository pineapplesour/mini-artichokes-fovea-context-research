from __future__ import annotations

import dataclasses
import subprocess
from pathlib import Path
from unittest.mock import patch

from harness_research.trace_gated_mini.core import (
    AttemptResult,
    CommandResult,
    TaskSpec,
    attempt_from_payload,
    collect_patch,
    parse_test_counts,
    run_arm,
    select_attempt,
)
from harness_research.trace_gated_mini.evaluate import evaluate_selected
from harness_research.trace_gated_mini.prompts import (
    INDEPENDENT_VARIANTS,
    build_counterexample_prompt,
    build_repair_prompt,
)
from harness_research.trace_gated_mini.universal_overlap import run_universal_overlap


def command(exit_code: int = 0, stdout: str = "") -> CommandResult:
    return CommandResult(("fake",), exit_code, False, 0.01, stdout, "")


def attempt(
    candidate_id: str,
    *,
    public_exit: int,
    passed: int,
    failed: int,
    patch_lines: int,
    forbidden: tuple[str, ...] = (),
) -> AttemptResult:
    return AttemptResult(
        candidate_id=candidate_id,
        policy="mini",
        workspace="/tmp/fake",
        agent=command(),
        public_test=command(public_exit),
        changed_files=("solution.py",),
        forbidden_files=forbidden,
        patch_sha256=candidate_id,
        patch_lines=patch_lines,
        patch_text=f"patch {candidate_id}",
        parsed_passed=passed,
        parsed_failed=failed,
    )


def test_selector_prefers_safe_public_pass_over_smaller_failure() -> None:
    selected = select_attempt(
        [
            attempt("a", public_exit=1, passed=9, failed=1, patch_lines=1),
            attempt("b", public_exit=0, passed=10, failed=0, patch_lines=4),
        ]
    )
    assert selected.candidate_id == "b"


def test_selector_rejects_forbidden_public_pass() -> None:
    selected = select_attempt(
        [
            attempt("a", public_exit=1, passed=9, failed=1, patch_lines=2),
            attempt("b", public_exit=0, passed=10, failed=0, patch_lines=1, forbidden=("gold.patch",)),
        ]
    )
    assert selected.candidate_id == "a"


def test_selector_keeps_base_on_evidence_tie() -> None:
    a = attempt("a", public_exit=0, passed=10, failed=0, patch_lines=2)
    b = dataclasses.replace(a, candidate_id="b", patch_sha256="b")
    assert select_attempt([b, a]).candidate_id == "a"


def test_selector_rejects_timed_out_partial_patch() -> None:
    timed_out = dataclasses.replace(
        attempt("a", public_exit=0, passed=10, failed=0, patch_lines=1),
        agent=CommandResult(("fake",), None, True, 600.0, "", ""),
    )
    completed = attempt("b", public_exit=0, passed=10, failed=0, patch_lines=2)
    assert timed_out.eligible is False
    assert select_attempt([timed_out, completed]).candidate_id == "b"


def test_parse_pytest_counts() -> None:
    assert parse_test_counts("================ 17 passed, 2 failed in 0.4s ================") == (17, 2)


def test_adversarial_prompts_require_non_exhaustive_boundary_reasoning() -> None:
    assert "illustrative rather than exhaustive" in INDEPENDENT_VARIANTS["c"]
    prompt = build_repair_prompt("generic issue", "a", "generic evidence", "patch_disagreement")
    assert "potentially illustrative" in prompt
    assert "Tornado" not in prompt
    closure_prompt = build_repair_prompt(
        "generic issue",
        "a",
        "generic evidence",
        "patch_disagreement",
        critic_memo="one false accept",
    )
    assert "zero unexplained mismatches" in closure_prompt
    assert "source-defined language" in closure_prompt
    critic_prompt = build_counterexample_prompt("generic issue", "generic evidence")
    assert "finite projection" in critic_prompt
    assert "shared by all candidates" in critic_prompt
    assert "full valid-input language" in critic_prompt
    assert "false accepts and false rejects" in critic_prompt
    assert "claim certificate" in critic_prompt
    assert "Tornado" not in critic_prompt
    assert "SPEC-FIRST" in build_counterexample_prompt(
        "generic issue", "generic evidence", "spec_first"
    )
    assert "REGRESSION-FIRST" in build_counterexample_prompt(
        "generic issue", "generic evidence", "regression_first"
    )


def test_codex_adapter_uses_supported_automatic_review_mode(tmp_path: Path) -> None:
    from harness_research.trace_gated_mini.core import CodexAdapter

    with patch("harness_research.trace_gated_mini.core.run_process", return_value=command()) as mocked:
        CodexAdapter(codex_home=Path("/tmp/codex-home")).run(
            tmp_path,
            "prompt",
            tmp_path / "artifacts",
            "a",
        )
    argv = mocked.call_args.args[0]
    assert "--approve-for-me" in argv
    assert "--sandbox" not in argv


def test_collect_patch_includes_untracked_text_file(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "tester"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "tester@example.com"], check=True)
    (tmp_path / "base.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "base.txt"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "base"], check=True)
    (tmp_path / "new.txt").write_text("new\n", encoding="utf-8")
    changed, patch, digest, lines = collect_patch(tmp_path)
    assert changed == ("new.txt",)
    assert "new.txt" in patch
    assert len(digest) == 64
    assert lines >= 1


class FakeAdapter:
    def run(self, workspace: Path, prompt: str, artifact_dir: Path, candidate_id: str) -> CommandResult:
        target = workspace / "solution.txt"
        if candidate_id == "b":
            target.write_text("correct\n", encoding="utf-8")
        else:
            target.write_text(f"wrong-{candidate_id}\n", encoding="utf-8")
        return command(stdout=prompt)


class RepairSeedAdapter:
    def run(self, workspace: Path, prompt: str, artifact_dir: Path, candidate_id: str) -> CommandResult:
        target = workspace / "solution.txt"
        if candidate_id == "a":
            target.write_text("nearly-correct\n", encoding="utf-8")
        elif candidate_id in {"b", "c"}:
            target.write_text(f"wrong-{candidate_id}\n", encoding="utf-8")
        elif candidate_id == "repair" and target.read_text(encoding="utf-8") == "nearly-correct\n":
            target.write_text("correct\n", encoding="utf-8")
        return command(stdout=prompt)


class DisagreementAdapter:
    def run(self, workspace: Path, prompt: str, artifact_dir: Path, candidate_id: str) -> CommandResult:
        target = workspace / "solution.txt"
        if candidate_id in {"a", "b", "c"}:
            target.write_text(f"public-{candidate_id}\n", encoding="utf-8")
        elif candidate_id == "repair":
            target.write_text("robust\n", encoding="utf-8")
        return command(stdout=prompt)


class CandidateOnlyAdapter:
    def run(self, workspace: Path, prompt: str, artifact_dir: Path, candidate_id: str) -> CommandResult:
        assert candidate_id in {"a", "b", "c"}
        (workspace / "solution.txt").write_text(f"public-{candidate_id}\n", encoding="utf-8")
        return command(stdout="candidate model")


class ArbiterOnlyAdapter:
    def run(self, workspace: Path, prompt: str, artifact_dir: Path, candidate_id: str) -> CommandResult:
        assert candidate_id == "repair"
        (workspace / "solution.txt").write_text("robust\n", encoding="utf-8")
        return command(stdout="arbiter model")


class CriticOnlyAdapter:
    def run(self, workspace: Path, prompt: str, artifact_dir: Path, candidate_id: str) -> CommandResult:
        assert candidate_id == "critic"
        assert (workspace / "solution.txt").read_text(encoding="utf-8").startswith("public-")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "last_message.txt").write_text(
            "Enumerate the complete finite domain; counterexample: boundary-z.",
            encoding="utf-8",
        )
        (workspace / ".mini_claim_oracle.sh").write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\ntest \"$(cat solution.txt)\" = robust\n",
            encoding="utf-8",
        )
        return command(stdout="critic events")


class PerspectiveCriticAdapter:
    def __init__(self, expected_id: str, oracle: str) -> None:
        self.expected_id = expected_id
        self.oracle = oracle

    def run(self, workspace: Path, prompt: str, artifact_dir: Path, candidate_id: str) -> CommandResult:
        assert candidate_id == self.expected_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "last_message.txt").write_text(
            f"{candidate_id} independent certificate",
            encoding="utf-8",
        )
        (workspace / ".mini_claim_oracle.sh").write_text(self.oracle, encoding="utf-8")
        return command(stdout=f"{candidate_id} events")


def test_mini_runs_independent_workspaces_and_selects_verified_candidate(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.name", "tester"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=source, check=True)
    (source / "solution.txt").write_text("buggy\n", encoding="utf-8")
    subprocess.run(["git", "add", "solution.txt"], cwd=source, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=source, check=True)
    task = TaskSpec(
        task_id="fixture-1",
        instruction="Make solution.txt contain correct.",
        base_ref="HEAD",
        public_test_command="test \"$(cat solution.txt)\" = correct",
        evaluation_test_command="test \"$(cat solution.txt)\" = correct",
        allowed_path_globs=("solution.txt",),
    )
    result = run_arm(
        source_repo=source,
        task=task,
        output_dir=tmp_path / "result",
        arm="mini",
        adapter=FakeAdapter(),
        repair_on_all_fail=False,
    )
    assert result["selected_candidate_id"] == "b"
    assert result["evaluation"]["exit_code"] == 0
    assert len({item["workspace"] for item in result["attempts"]}) == 3


def test_bounded_repair_inherits_selected_uncommitted_patch(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.name", "tester"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=source, check=True)
    (source / "solution.txt").write_text("buggy\n", encoding="utf-8")
    subprocess.run(["git", "add", "solution.txt"], cwd=source, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=source, check=True)
    task = TaskSpec(
        task_id="fixture-repair",
        instruction="Make solution.txt contain correct.",
        base_ref="HEAD",
        public_test_command="test \"$(cat solution.txt)\" = correct",
        evaluation_test_command="test \"$(cat solution.txt)\" = correct",
        allowed_path_globs=("solution.txt",),
    )
    result = run_arm(
        source_repo=source,
        task=task,
        output_dir=tmp_path / "result",
        arm="mini",
        adapter=RepairSeedAdapter(),
    )
    assert result["repair_triggered"] is True
    assert result["selected_candidate_id"] == "repair"
    assert result["evaluation"]["exit_code"] == 0


def test_public_passing_patch_disagreement_triggers_bounded_arbitration(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.name", "tester"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=source, check=True)
    (source / "solution.txt").write_text("buggy\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=source, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=source, check=True)
    task = TaskSpec(
        task_id="disagreement-fixture",
        instruction="Produce a robust implementation.",
        base_ref="HEAD",
        public_test_command="grep -qE '^(public-|robust)' solution.txt",
        evaluation_test_command="test \"$(cat solution.txt)\" = robust",
        allowed_path_globs=("solution.txt",),
    )
    result = run_arm(
        source_repo=source,
        task=task,
        output_dir=tmp_path / "result",
        arm="mini",
        adapter=DisagreementAdapter(),
    )
    assert result["repair_triggered"] is True
    assert result["repair_trigger_reason"] == "patch_disagreement"
    assert result["selected_candidate_id"] == "repair"
    assert result["evaluation"]["exit_code"] == 0


def test_mini_can_use_separate_candidate_and_arbiter_adapters(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.name", "tester"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=source, check=True)
    (source / "solution.txt").write_text("buggy\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=source, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=source, check=True)
    task = TaskSpec(
        task_id="asymmetric-fixture",
        instruction="Produce a robust implementation.",
        base_ref="HEAD",
        public_test_command="grep -qE '^(public-|robust)' solution.txt",
        evaluation_test_command="test \"$(cat solution.txt)\" = robust",
        allowed_path_globs=("solution.txt",),
    )
    result = run_arm(
        source_repo=source,
        task=task,
        output_dir=tmp_path / "result",
        arm="mini",
        adapter=CandidateOnlyAdapter(),
        critic_adapter=CriticOnlyAdapter(),
        repair_adapter=ArbiterOnlyAdapter(),
    )
    assert result["selected_candidate_id"] == "repair"
    assert result["critic"]["workspace_mutated"] is False
    assert "boundary-z" in result["critic"]["last_message"]
    assert result["critic"]["oracle_sha256"]
    assert result["attempts"][-1]["agent"]["stdout"] == "arbiter model"
    assert all(item["claim_test"]["exit_code"] == 1 for item in result["attempts"][:3])
    assert result["attempts"][-1]["claim_test"]["exit_code"] == 0
    assert result["selected_eligible"] is True
    assert result["evaluation"]["exit_code"] == 0


def test_attempt_payload_round_trip_checks_patch_digest() -> None:
    original = attempt("a", public_exit=0, passed=10, failed=0, patch_lines=2)
    payload = dataclasses.asdict(original)
    payload["patch_sha256"] = __import__("hashlib").sha256(
        original.patch_text.encode("utf-8")
    ).hexdigest()
    restored = attempt_from_payload(payload)
    assert restored.patch_text == original.patch_text
    payload["patch_text"] = "tampered"
    try:
        attempt_from_payload(payload)
    except ValueError as error:
        assert "digest mismatch" in str(error)
    else:
        raise AssertionError("tampered patch must be rejected")


def test_universal_overlap_requires_all_independent_claim_oracles(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.name", "tester"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=source, check=True)
    (source / "solution.txt").write_text("buggy\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=source, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=source, check=True)
    task = TaskSpec(
        task_id="universal-overlap-fixture",
        instruction="Produce a robust implementation.",
        base_ref="HEAD",
        public_test_command="grep -qE '^(public-|robust)' solution.txt",
        evaluation_test_command=None,
        allowed_path_globs=("solution.txt",),
    )
    frozen_dir = tmp_path / "frozen"
    run_arm(
        source_repo=source,
        task=task,
        output_dir=frozen_dir,
        arm="mini",
        adapter=CandidateOnlyAdapter(),
        repair_on_all_fail=False,
    )
    script = "#!/usr/bin/env bash\nset -euo pipefail\ntest \"$(cat solution.txt)\" = robust\n"
    result = run_universal_overlap(
        source_repo=source,
        task=task,
        frozen_result_path=frozen_dir / "result.json",
        output_dir=tmp_path / "overlap",
        critics=(
            ("critic-spec", "spec_first", PerspectiveCriticAdapter("critic-spec", script)),
            (
                "critic-regression",
                "regression_first",
                PerspectiveCriticAdapter("critic-regression", script),
            ),
        ),
        repair_adapter=ArbiterOnlyAdapter(),
        public_test_timeout_seconds=30,
    )
    assert result["critic_count"] == 2
    assert all(item["claim_test"]["exit_code"] == 1 for item in result["attempts"][:3])
    assert result["attempts"][-1]["claim_test"]["exit_code"] == 0
    assert result["selected_candidate_id"] == "repair"
    assert result["selected_eligible"] is True


def test_post_selection_evaluator_applies_hidden_tests_after_selection(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.name", "tester"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=source, check=True)
    (source / "solution.txt").write_text("buggy\n", encoding="utf-8")
    subprocess.run(["git", "add", "solution.txt"], cwd=source, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=source, check=True)

    candidate = tmp_path / "candidate"
    subprocess.run(["git", "clone", "-q", str(source), str(candidate)], check=True)
    (candidate / "solution.txt").write_text("correct\n", encoding="utf-8")
    _, solution_patch, solution_sha, solution_lines = collect_patch(candidate)
    arm_payload = {
        "task_id": "hidden-fixture",
        "arm": "mini",
        "selected_candidate_id": "a",
        "attempts": [{
            "candidate_id": "a",
            "patch_text": solution_patch,
            "patch_sha256": solution_sha,
            "patch_lines": solution_lines,
        }],
    }
    arm_result = tmp_path / "arm-result.json"
    arm_result.write_text(__import__("json").dumps(arm_payload), encoding="utf-8")

    test_author = tmp_path / "test-author"
    subprocess.run(["git", "clone", "-q", str(source), str(test_author)], check=True)
    (test_author / "hidden_test.sh").write_text(
        '#!/bin/sh\ntest "$(cat solution.txt)" = correct\n', encoding="utf-8"
    )
    _, hidden_patch, _, _ = collect_patch(test_author)
    hidden_patch_path = tmp_path / "opaque-eval.patch"
    hidden_patch_path.write_text(hidden_patch, encoding="utf-8")

    result = evaluate_selected(
        source_repo=source,
        base_ref="HEAD",
        arm_result_path=arm_result,
        evaluation_patch_path=hidden_patch_path,
        evaluation_command="sh hidden_test.sh",
        output_dir=tmp_path / "evaluation",
        timeout_seconds=30,
    )
    assert result["resolved"] is True
    assert result["evaluation_patch_sha256"]


def test_post_selection_evaluator_records_test_patch_conflict(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.name", "tester"], cwd=source, check=True)
    subprocess.run(["git", "config", "user.email", "tester@example.com"], cwd=source, check=True)
    (source / "test_solution.py").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=source, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=source, check=True)

    candidate = tmp_path / "candidate"
    subprocess.run(["git", "clone", "-q", str(source), str(candidate)], check=True)
    (candidate / "test_solution.py").write_text("candidate\n", encoding="utf-8")
    _, solution_patch, solution_sha, _ = collect_patch(candidate)
    arm_result = tmp_path / "arm.json"
    arm_result.write_text(
        __import__("json").dumps({
            "task_id": "conflict-fixture",
            "arm": "direct",
            "selected_candidate_id": "a",
            "attempts": [{"candidate_id": "a", "patch_text": solution_patch, "patch_sha256": solution_sha}],
        }),
        encoding="utf-8",
    )

    evaluator = tmp_path / "evaluator"
    subprocess.run(["git", "clone", "-q", str(source), str(evaluator)], check=True)
    (evaluator / "test_solution.py").write_text("hidden\n", encoding="utf-8")
    _, evaluation_patch, _, _ = collect_patch(evaluator)
    evaluation_patch_path = tmp_path / "evaluation.patch"
    evaluation_patch_path.write_text(evaluation_patch, encoding="utf-8")

    result = evaluate_selected(
        source_repo=source,
        base_ref="HEAD",
        arm_result_path=arm_result,
        evaluation_patch_path=evaluation_patch_path,
        evaluation_command="true",
        output_dir=tmp_path / "evaluation",
        timeout_seconds=30,
    )
    assert result["resolved"] is False
    assert result["failure_stage"] == "evaluation_patch_apply"
    assert result["evaluation"] is None
