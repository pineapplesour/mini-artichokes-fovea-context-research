"""Minimal, auditable execution core for Trace-gated Mini.

The selector is intentionally deterministic. It never sees gold patches or the
evaluation-only command, and therefore cannot select a candidate using hidden
answers. Model calls operate on isolated local clones of the same frozen base.
"""

from __future__ import annotations

import dataclasses
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Protocol, Sequence

from .prompts import build_counterexample_prompt, build_prompt, build_repair_prompt


@dataclasses.dataclass(frozen=True)
class TaskSpec:
    task_id: str
    instruction: str
    base_ref: str
    public_test_command: str
    evaluation_test_command: str | None = None
    allowed_path_globs: tuple[str, ...] = ()
    forbidden_path_globs: tuple[str, ...] = (".git/*", ".mini_evaluation/*")

    @classmethod
    def from_json(cls, path: Path) -> "TaskSpec":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            task_id=payload["task_id"],
            instruction=payload["instruction"],
            base_ref=payload["base_ref"],
            public_test_command=payload["public_test_command"],
            evaluation_test_command=payload.get("evaluation_test_command"),
            allowed_path_globs=tuple(payload.get("allowed_path_globs", ())),
            forbidden_path_globs=tuple(payload.get("forbidden_path_globs", (".git/*", ".mini_evaluation/*"))),
        )


@dataclasses.dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    exit_code: int | None
    timed_out: bool
    duration_seconds: float
    stdout: str
    stderr: str


@dataclasses.dataclass(frozen=True)
class AttemptResult:
    candidate_id: str
    policy: str
    workspace: str
    agent: CommandResult
    public_test: CommandResult
    changed_files: tuple[str, ...]
    forbidden_files: tuple[str, ...]
    patch_sha256: str
    patch_lines: int
    patch_text: str
    parsed_passed: int = 0
    parsed_failed: int = 0
    claim_test: CommandResult | None = None

    @property
    def agent_complete(self) -> bool:
        return self.agent.exit_code == 0 and not self.agent.timed_out

    @property
    def public_pass(self) -> bool:
        return self.public_test.exit_code == 0 and not self.public_test.timed_out

    @property
    def safe(self) -> bool:
        return not self.forbidden_files

    @property
    def claim_pass(self) -> bool:
        return self.claim_test is None or (
            self.claim_test.exit_code == 0 and not self.claim_test.timed_out
        )

    @property
    def eligible(self) -> bool:
        return self.agent_complete and self.safe and self.public_pass and self.claim_pass


@dataclasses.dataclass(frozen=True)
class CritiqueResult:
    workspace: str
    agent: CommandResult
    last_message: str
    changed_files: tuple[str, ...]
    patch_sha256: str
    patch_lines: int
    seed_patch_sha256: str
    workspace_mutated: bool
    oracle_text: str | None
    oracle_sha256: str | None


class AgentAdapter(Protocol):
    def run(self, workspace: Path, prompt: str, artifact_dir: Path, candidate_id: str) -> CommandResult:
        ...


@dataclasses.dataclass(frozen=True)
class CodexAdapter:
    codex_home: Path
    model: str = "gpt-5.6-luna"
    reasoning_effort: str = "medium"
    timeout_seconds: int = 600
    executable: str = "codex"

    def run(self, workspace: Path, prompt: str, artifact_dir: Path, candidate_id: str) -> CommandResult:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        last_message = artifact_dir / "last_message.txt"
        argv = (
            self.executable,
            "exec",
            "--ignore-user-config",
            "--ephemeral",
            "--json",
            "--color",
            "never",
            "--model",
            self.model,
            "--config",
            f'model_reasoning_effort="{self.reasoning_effort}"',
            "--approve-for-me",
            "--cd",
            str(workspace),
            "--output-last-message",
            str(last_message),
            "-",
        )
        env = os.environ.copy()
        env["CODEX_HOME"] = str(self.codex_home)
        env["MINI_CANDIDATE_ID"] = candidate_id
        result = run_process(argv, cwd=workspace, timeout_seconds=self.timeout_seconds, env=env, stdin=prompt)
        (artifact_dir / "events.jsonl").write_text(result.stdout, encoding="utf-8")
        (artifact_dir / "stderr.txt").write_text(result.stderr, encoding="utf-8")
        return result


def run_process(
    argv: Sequence[str],
    *,
    cwd: Path,
    timeout_seconds: int,
    env: dict[str, str] | None = None,
    stdin: str | None = None,
) -> CommandResult:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            list(argv),
            cwd=cwd,
            env=env,
            input=stdin,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        return CommandResult(
            argv=tuple(argv),
            exit_code=completed.returncode,
            timed_out=False,
            duration_seconds=time.monotonic() - started,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            argv=tuple(argv),
            exit_code=None,
            timed_out=True,
            duration_seconds=time.monotonic() - started,
            stdout=_decode_timeout_stream(exc.stdout),
            stderr=_decode_timeout_stream(exc.stderr),
        )


def _decode_timeout_stream(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def prepare_workspace(source_repo: Path, base_ref: str, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    clone = run_process(
        ("git", "clone", "--quiet", "--shared", "--no-hardlinks", str(source_repo), str(destination)),
        cwd=destination.parent,
        timeout_seconds=180,
    )
    if clone.exit_code != 0:
        raise RuntimeError(f"git clone failed: {clone.stderr}")
    checkout = run_process(("git", "checkout", "--quiet", "--detach", base_ref), cwd=destination, timeout_seconds=60)
    if checkout.exit_code != 0:
        raise RuntimeError(f"git checkout failed: {checkout.stderr}")


def run_shell(command: str, workspace: Path, timeout_seconds: int) -> CommandResult:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return run_process(("bash", "-lc", command), cwd=workspace, timeout_seconds=timeout_seconds, env=env)


def _git_status_paths(workspace: Path) -> tuple[str, ...]:
    result = run_process(
        ("git", "status", "--porcelain=v1", "-z", "--untracked-files=all"),
        cwd=workspace,
        timeout_seconds=30,
    )
    if result.exit_code != 0:
        raise RuntimeError(result.stderr)
    paths: list[str] = []
    records = result.stdout.split("\0")
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        status = record[:2]
        path = record[3:]
        if status[0] in {"R", "C"} and index < len(records):
            path = records[index]
            index += 1
        paths.append(path)
    return tuple(sorted(set(paths)))


def collect_patch(workspace: Path) -> tuple[tuple[str, ...], str, str, int]:
    changed = _git_status_paths(workspace)
    untracked_result = run_process(
        ("git", "ls-files", "--others", "--exclude-standard", "-z"),
        cwd=workspace,
        timeout_seconds=30,
    )
    if untracked_result.exit_code != 0:
        raise RuntimeError(untracked_result.stderr)
    untracked = tuple(path for path in untracked_result.stdout.split("\0") if path)
    if untracked:
        intent = run_process(("git", "add", "--intent-to-add", "--", *untracked), cwd=workspace, timeout_seconds=30)
        if intent.exit_code != 0:
            raise RuntimeError(intent.stderr)
    diff = run_process(("git", "diff", "--binary", "--no-ext-diff", "HEAD", "--"), cwd=workspace, timeout_seconds=60)
    if diff.exit_code != 0:
        raise RuntimeError(diff.stderr)
    digest = hashlib.sha256(diff.stdout.encode("utf-8")).hexdigest()
    lines = sum(1 for line in diff.stdout.splitlines() if line.startswith(("+", "-")) and not line.startswith(("+++", "---")))
    return changed, diff.stdout, digest, lines


_PYTEST_COUNTS = re.compile(r"(?:(?P<passed>\d+) passed)?(?:,?\s*)?(?:(?P<failed>\d+) failed)?")


def parse_test_counts(output: str) -> tuple[int, int]:
    passed = failed = 0
    for match in _PYTEST_COUNTS.finditer(output):
        if match.group("passed") is not None:
            passed = max(passed, int(match.group("passed")))
        if match.group("failed") is not None:
            failed = max(failed, int(match.group("failed")))
    return passed, failed


def _matches_any(path: str, patterns: Sequence[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def execute_attempt(
    *,
    source_repo: Path,
    task: TaskSpec,
    output_dir: Path,
    candidate_id: str,
    policy: str,
    adapter: AgentAdapter,
    public_test_timeout_seconds: int,
    prompt_override: str | None = None,
    seed_patch: str | None = None,
) -> AttemptResult:
    workspace = output_dir / "workspaces" / candidate_id
    artifact_dir = output_dir / "attempts" / candidate_id
    prepare_workspace(source_repo, task.base_ref, workspace)
    if seed_patch:
        seed_path = artifact_dir / "seed.patch"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        seed_path.write_text(seed_patch, encoding="utf-8")
        applied = run_process(
            ("git", "apply", "--binary", str(seed_path)),
            cwd=workspace,
            timeout_seconds=60,
        )
        if applied.exit_code != 0:
            raise RuntimeError(f"failed to seed repair workspace: {applied.stderr}")
    prompt = prompt_override or build_prompt(task.instruction, policy, candidate_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    agent_result = adapter.run(workspace, prompt, artifact_dir, candidate_id)
    public_test = run_shell(task.public_test_command, workspace, public_test_timeout_seconds)
    changed, patch, patch_sha, patch_lines = collect_patch(workspace)
    forbidden = tuple(
        path
        for path in changed
        if _matches_any(path, task.forbidden_path_globs)
        or (task.allowed_path_globs and not _matches_any(path, task.allowed_path_globs))
    )
    passed, failed = parse_test_counts(public_test.stdout + "\n" + public_test.stderr)
    result = AttemptResult(
        candidate_id=candidate_id,
        policy=policy,
        workspace=str(workspace),
        agent=agent_result,
        public_test=public_test,
        changed_files=changed,
        forbidden_files=forbidden,
        patch_sha256=patch_sha,
        patch_lines=patch_lines,
        patch_text=patch,
        parsed_passed=passed,
        parsed_failed=failed,
        claim_test=None,
    )
    (artifact_dir / "result.json").write_text(json.dumps(to_jsonable(result), indent=2), encoding="utf-8")
    (artifact_dir / "patch.diff").write_text(patch, encoding="utf-8")
    return result


def execute_critique(
    *,
    source_repo: Path,
    task: TaskSpec,
    output_dir: Path,
    adapter: AgentAdapter,
    seed_patch: str,
    evidence: str,
    critic_id: str = "critic",
    perspective: str = "balanced",
) -> CritiqueResult:
    """Run a read-only-intended critic; discard any workspace mutation it makes."""

    workspace = output_dir / "workspaces" / critic_id
    artifact_dir = output_dir / "attempts" / critic_id
    prepare_workspace(source_repo, task.base_ref, workspace)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    seed_path = artifact_dir / "seed.patch"
    seed_path.write_text(seed_patch, encoding="utf-8")
    applied = run_process(("git", "apply", "--binary", str(seed_path)), cwd=workspace, timeout_seconds=60)
    if applied.exit_code != 0:
        raise RuntimeError(f"failed to seed critic workspace: {applied.stderr}")
    prompt = build_counterexample_prompt(task.instruction, evidence, perspective)
    (artifact_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    agent_result = adapter.run(workspace, prompt, artifact_dir, critic_id)
    oracle_path = workspace / ".mini_claim_oracle.sh"
    oracle_text = None
    oracle_sha = None
    if oracle_path.is_file() and not oracle_path.is_symlink():
        if oracle_path.stat().st_size > 200_000:
            raise ValueError("critic claim oracle exceeds 200KB")
        oracle_text = oracle_path.read_text(encoding="utf-8")
        oracle_sha = hashlib.sha256(oracle_text.encode("utf-8")).hexdigest()
        (artifact_dir / "claim_oracle.sh").write_text(oracle_text, encoding="utf-8")
        oracle_path.unlink()
    changed, patch, patch_sha, patch_lines = collect_patch(workspace)
    seed_sha = hashlib.sha256(seed_patch.encode("utf-8")).hexdigest()
    last_message_path = artifact_dir / "last_message.txt"
    if last_message_path.exists():
        last_message = last_message_path.read_text(encoding="utf-8")
    elif agent_result.timed_out:
        last_message = "Critic timed out without a completed claim certificate."
    elif agent_result.exit_code != 0:
        last_message = f"Critic exited with code {agent_result.exit_code} without a completed claim certificate."
    else:
        last_message = agent_result.stdout[-12000:]
    result = CritiqueResult(
        workspace=str(workspace),
        agent=agent_result,
        last_message=last_message,
        changed_files=changed,
        patch_sha256=patch_sha,
        patch_lines=patch_lines,
        seed_patch_sha256=seed_sha,
        workspace_mutated=patch_sha != seed_sha,
        oracle_text=oracle_text,
        oracle_sha256=oracle_sha,
    )
    (artifact_dir / "result.json").write_text(json.dumps(to_jsonable(result), indent=2), encoding="utf-8")
    (artifact_dir / "observed.patch").write_text(patch, encoding="utf-8")
    return result


def run_claim_oracle_for_attempt(
    *,
    source_repo: Path,
    task: TaskSpec,
    output_dir: Path,
    attempt: AttemptResult,
    oracle_text: str | Sequence[str],
    timeout_seconds: int,
) -> AttemptResult:
    """Run a frozen public claim oracle on a candidate in a fresh workspace."""

    check_dir = output_dir / "claim_checks" / attempt.candidate_id
    workspace = check_dir / "workspace"
    prepare_workspace(source_repo, task.base_ref, workspace)
    patch_path = check_dir / "candidate.patch"
    patch_path.write_text(attempt.patch_text, encoding="utf-8")
    applied = run_process(("git", "apply", "--binary", str(patch_path.resolve())), cwd=workspace, timeout_seconds=60)
    if applied.exit_code != 0:
        raise RuntimeError(f"failed to apply candidate for claim check: {applied.stderr}")
    oracle_texts = (oracle_text,) if isinstance(oracle_text, str) else tuple(oracle_text)
    if not oracle_texts:
        raise ValueError("at least one claim oracle is required")
    oracle_paths = []
    for index, item in enumerate(oracle_texts):
        oracle_path = check_dir / f"claim_oracle_{index}.sh"
        oracle_path.write_text(item, encoding="utf-8")
        oracle_paths.append(oracle_path)
    wrapper_path = check_dir / "run_claim_oracles.sh"
    wrapper_lines = ["#!/usr/bin/env bash", "status=0"]
    for oracle_path in oracle_paths:
        wrapper_lines.append(
            f"bash {json.dumps(str(oracle_path.resolve()))} || status=1"
        )
    wrapper_lines.extend(("exit $status", ""))
    wrapper_path.write_text("\n".join(wrapper_lines), encoding="utf-8")
    claim_test = run_process(
        ("bash", str(wrapper_path.resolve())),
        cwd=workspace,
        timeout_seconds=timeout_seconds,
        env=os.environ.copy(),
    )
    changed, observed_patch, observed_sha, _ = collect_patch(workspace)
    patch_unchanged = observed_sha == attempt.patch_sha256
    if not patch_unchanged:
        claim_test = dataclasses.replace(
            claim_test,
            exit_code=1,
            stderr=(
                claim_test.stderr
                + "\nclaim oracle mutated the candidate workspace; check invalidated"
            ),
        )
    receipt = {
        "candidate_id": attempt.candidate_id,
        "oracle_sha256": [
            hashlib.sha256(item.encode("utf-8")).hexdigest() for item in oracle_texts
        ],
        "expected_patch_sha256": attempt.patch_sha256,
        "observed_patch_sha256": observed_sha,
        "patch_unchanged": patch_unchanged,
        "changed_files": list(changed),
        "result": to_jsonable(claim_test),
    }
    (check_dir / "observed.patch").write_text(observed_patch, encoding="utf-8")
    (check_dir / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return dataclasses.replace(attempt, claim_test=claim_test)


def selection_key(attempt: AttemptResult, base_candidate_id: str = "a") -> tuple[object, ...]:
    """Order by public evidence, then conservative scope, then fixed identity."""

    return (
        0 if attempt.agent_complete else 1,
        0 if attempt.safe else 1,
        0 if attempt.public_pass else 1,
        0 if attempt.claim_pass else 1,
        attempt.parsed_failed,
        -attempt.parsed_passed,
        len(attempt.changed_files),
        attempt.patch_lines,
        0 if attempt.candidate_id == base_candidate_id else 1,
        attempt.candidate_id,
    )


def select_attempt(attempts: Sequence[AttemptResult], base_candidate_id: str = "a") -> AttemptResult:
    if not attempts:
        raise ValueError("at least one attempt is required")
    return min(attempts, key=lambda item: selection_key(item, base_candidate_id))


def _compact_evidence(attempts: Sequence[AttemptResult], max_patch_chars: int = 8000) -> str:
    blocks: list[str] = []
    for attempt in attempts:
        test_tail = (attempt.public_test.stdout + "\n" + attempt.public_test.stderr)[-4000:]
        claim_tail = ""
        if attempt.claim_test is not None:
            claim_tail = (
                attempt.claim_test.stdout + "\n" + attempt.claim_test.stderr
            )[-4000:]
        patch = attempt.patch_text[:max_patch_chars]
        blocks.append(
            f"Candidate {attempt.candidate_id}: agent_complete={attempt.agent_complete}; "
            f"public_pass={attempt.public_pass}; claim_pass={attempt.claim_pass}; "
            f"passed={attempt.parsed_passed}; failed={attempt.parsed_failed}; "
            f"changed={list(attempt.changed_files)}; forbidden={list(attempt.forbidden_files)}\n"
            f"Public test tail:\n{test_tail}\nClaim-oracle tail:\n{claim_tail}\nPatch:\n{patch}"
        )
    return "\n\n---\n\n".join(blocks)


def run_arm(
    *,
    source_repo: Path,
    task: TaskSpec,
    output_dir: Path,
    arm: str,
    adapter: AgentAdapter,
    critic_adapter: AgentAdapter | None = None,
    repair_adapter: AgentAdapter | None = None,
    public_test_timeout_seconds: int = 300,
    repair_on_all_fail: bool = True,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=False)
    if arm not in {"direct", "kira", "mini"}:
        raise ValueError(f"unsupported arm: {arm}")
    candidate_ids = ("a",) if arm in {"direct", "kira"} else ("a", "b", "c")
    attempts = [
        execute_attempt(
            source_repo=source_repo,
            task=task,
            output_dir=output_dir,
            candidate_id=candidate_id,
            policy=arm,
            adapter=adapter,
            public_test_timeout_seconds=public_test_timeout_seconds,
        )
        for candidate_id in candidate_ids
    ]
    selected = select_attempt(attempts)
    repair_triggered = False
    repair_trigger_reason = None
    critique = None
    safe_public_passes = [item for item in attempts if item.eligible]
    distinct_passing_patches = {item.patch_sha256 for item in safe_public_passes}
    if arm == "mini" and repair_on_all_fail:
        if not safe_public_passes:
            repair_trigger_reason = "all_public_fail"
        elif len(distinct_passing_patches) > 1:
            repair_trigger_reason = "patch_disagreement"
    if repair_trigger_reason:
        repair_triggered = True
        evidence = _compact_evidence(attempts)
        claim_oracle_text = None
        if critic_adapter is not None:
            critique = execute_critique(
                source_repo=source_repo,
                task=task,
                output_dir=output_dir,
                adapter=critic_adapter,
                seed_patch=selected.patch_text,
                evidence=evidence,
            )
            claim_oracle_text = critique.oracle_text or (
                "#!/usr/bin/env bash\n"
                "echo 'critic did not produce a completed claim oracle' >&2\n"
                "exit 2\n"
            )
            attempts = [
                run_claim_oracle_for_attempt(
                    source_repo=source_repo,
                    task=task,
                    output_dir=output_dir,
                    attempt=item,
                    oracle_text=claim_oracle_text,
                    timeout_seconds=public_test_timeout_seconds,
                )
                for item in attempts
            ]
            selected = select_attempt(attempts)
            evidence = _compact_evidence(attempts)
        repair_prompt = build_repair_prompt(
            task.instruction,
            selected.candidate_id,
            evidence,
            repair_trigger_reason,
            critic_memo=critique.last_message if critique else None,
        )
        repair = execute_attempt(
            source_repo=source_repo,
            task=task,
            output_dir=output_dir,
            candidate_id="repair",
            policy="mini",
            adapter=repair_adapter or adapter,
            public_test_timeout_seconds=public_test_timeout_seconds,
            prompt_override=repair_prompt,
            seed_patch=selected.patch_text,
        )
        if claim_oracle_text is not None:
            repair = run_claim_oracle_for_attempt(
                source_repo=source_repo,
                task=task,
                output_dir=output_dir,
                attempt=repair,
                oracle_text=claim_oracle_text,
                timeout_seconds=public_test_timeout_seconds,
            )
        attempts.append(repair)
        if repair.eligible:
            selected = repair
        else:
            selected = select_attempt(attempts)

    evaluation = None
    if task.evaluation_test_command:
        evaluation = run_shell(task.evaluation_test_command, Path(selected.workspace), public_test_timeout_seconds)
    payload = {
        "schema_version": 1,
        "task_id": task.task_id,
        "arm": arm,
        "repair_triggered": repair_triggered,
        "repair_trigger_reason": repair_trigger_reason,
        "critic": to_jsonable(critique) if critique else None,
        "selected_candidate_id": selected.candidate_id,
        "selected_patch_sha256": selected.patch_sha256,
        "selected_eligible": selected.eligible,
        "attempts": [to_jsonable(item) for item in attempts],
        "evaluation": to_jsonable(evaluation) if evaluation else None,
    }
    (output_dir / "result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def to_jsonable(value: object) -> object:
    if dataclasses.is_dataclass(value):
        return {field.name: to_jsonable(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    return value


def attempt_from_payload(payload: dict[str, object]) -> AttemptResult:
    def command_from_payload(value: object) -> CommandResult:
        assert isinstance(value, dict)
        return CommandResult(
            argv=tuple(value["argv"]),
            exit_code=value["exit_code"],
            timed_out=bool(value["timed_out"]),
            duration_seconds=float(value["duration_seconds"]),
            stdout=str(value["stdout"]),
            stderr=str(value["stderr"]),
        )

    claim_payload = payload.get("claim_test")
    result = AttemptResult(
        candidate_id=str(payload["candidate_id"]),
        policy=str(payload["policy"]),
        workspace=str(payload["workspace"]),
        agent=command_from_payload(payload["agent"]),
        public_test=command_from_payload(payload["public_test"]),
        changed_files=tuple(payload["changed_files"]),
        forbidden_files=tuple(payload["forbidden_files"]),
        patch_sha256=str(payload["patch_sha256"]),
        patch_lines=int(payload["patch_lines"]),
        patch_text=str(payload["patch_text"]),
        parsed_passed=int(payload.get("parsed_passed", 0)),
        parsed_failed=int(payload.get("parsed_failed", 0)),
        claim_test=command_from_payload(claim_payload) if isinstance(claim_payload, dict) else None,
    )
    observed_patch_sha256 = hashlib.sha256(result.patch_text.encode("utf-8")).hexdigest()
    if observed_patch_sha256 != result.patch_sha256:
        raise ValueError(
            f"candidate {result.candidate_id} patch digest mismatch: "
            f"recorded={result.patch_sha256}, observed={observed_patch_sha256}"
        )
    return result
