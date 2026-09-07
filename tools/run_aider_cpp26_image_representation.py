"""Aider C++26 text/image initial-view representation development assay.

This thin runner keeps workspace preparation, attempts, and official scoring in
the existing core.  Dry-run is the default; --execute is intentionally the
only path that can make the twelve fresh model/evaluator sessions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
from typing import Any, Iterable

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness_research.trace_gated_mini.core import (  # noqa: E402
    TaskSpec, collect_patch, execute_attempt, prepare_workspace,
)
from tools import run_aider_hidden20_arm as aider  # noqa: E402
from tools.run_classeval_image_text_smoke import render_text_pages  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
# The public snapshot stores the frozen source as a bare repository so the
# outer publication repository does not contain a nested `.git` directory.
DEFAULT_FREEZE = REPO / "fixtures/aider_cpp26"
DEFAULT_CODEX_HOME = Path("/home/pineapple/.codex-new-account")
FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
EVALUATOR_PATH = REPO / "tools/evaluate_aider_hidden_cpp_full.py"
OFFICIAL_SOURCE_COMMIT = "7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f"
MODEL, EFFORT = "gpt-5.6-luna", "medium"
AGENT_TIMEOUT, EVALUATOR_TIMEOUT = 900, 1800
PROFILE_NAME = "paired"
PROFILE_TEXT = '''approval_policy = "never"
default_permissions = "paired"

[permissions.paired]
extends = ":workspace"
filesystem = {"/tmp/codex-home" = "deny"}
network = {enabled = false}
'''

BASELINE_PLAN = (("T1", "text"), ("T2", "text"), ("I1", "image"), ("I2", "image"))
PAIR_PLAN = (
    ("TT", ("T1", "T2")), ("II", ("I1", "I2")),
    ("TIa", ("T1", "I1")), ("TIb", ("I2", "T2")),
)


def _json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")[:100] or "item"


def _load_freeze(freeze_root: Path) -> tuple[Path, TaskSpec, dict[str, Any]]:
    freeze_root = Path(freeze_root).resolve()
    source = freeze_root / "source"
    freeze_path = freeze_root / "freeze.json"
    task_path = freeze_root / "public/task.json"
    manifest_path = source / "benchmark_manifest.json"
    if not manifest_path.is_file():
        # Public layout: `source` is a bare Git repository and the manifest is
        # kept next to it. The historical run layout kept it in the checkout.
        manifest_path = freeze_root / "benchmark_manifest.json"
    freeze = _json(freeze_path)
    task_bytes = task_path.read_bytes()
    manifest_bytes = manifest_path.read_bytes()
    if freeze.get("sourceCommit") != OFFICIAL_SOURCE_COMMIT:
        raise ValueError("freeze source commit is not the pinned official commit")
    if freeze.get("manifestSha256") != _sha(manifest_bytes):
        raise ValueError("freeze manifest hash mismatch")
    if freeze.get("taskSha256") != _sha(task_bytes):
        raise ValueError("freeze public task hash mismatch")
    if not EVALUATOR_PATH.is_file() or freeze.get("evaluatorSha256") != _sha(EVALUATOR_PATH.read_bytes()):
        raise ValueError("freeze evaluator hash mismatch")
    task = TaskSpec.from_json(task_path)
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    if manifest.get("officialCommit") != OFFICIAL_SOURCE_COMMIT:
        raise ValueError("manifest official commit is not pinned")
    if len(manifest.get("tasks", [])) != 26 or len({x["taskId"] for x in manifest["tasks"]}) != 26:
        raise ValueError("Aider C++26 manifest is required")
    selected_ids = freeze.get("selectedTaskIds")
    manifest_ids = [item.get("taskId") for item in manifest["tasks"]]
    if manifest_ids != selected_ids:
        raise ValueError("freeze selected task IDs do not match the manifest")
    for item in manifest["tasks"]:
        if _sha(item["instruction"].encode()) != item["instructionSha256"]:
            raise ValueError("canonical instruction hash mismatch")
    if task.base_ref != freeze["baseRef"]:
        raise ValueError("public task base ref differs from freeze")
    return source, task, manifest


def _task_index(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"index": n, "taskId": item["taskId"], "name": item["name"],
             "relativePath": item["relativePath"], "solutionFiles": item["solutionFiles"],
             "sourceId": _safe(item["taskId"])}
            for n, item in enumerate(manifest["tasks"], 1)]


def _protected_rules(task: TaskSpec, manifest: dict[str, Any]) -> str:
    return (
        "Protected rules (keep this text visible in both arms): solve all 26; "
        "tests and gold implementations are unavailable; use C++17; edit only "
        "the listed solution files; never edit tests, CMakeLists, .docs, the "
        "benchmark manifest, or repository metadata. Preserve public names/signatures "
        "and use only the standard library or declared dependencies. Do not search "
        "for exercise solutions. Put temporary probes/builds under /tmp/probes, "
        "outside the submitted workspace.\n"
        "Use the initial view to locate relevant requirements, then read precise "
        "original text where needed. Full requirements are available in "
        "benchmark_manifest.json, tasks[].instruction (lookup by taskId), and "
        "starter source at each relativePath. Prefer targeted source reads; "
        "full rereads are permitted and recorded.\n"
        "Allowed paths:\n" + "\n".join(f"- {p}" for p in task.allowed_path_globs) +
        "\nForbidden path globs:\n" + "\n".join(f"- {p}" for p in task.forbidden_path_globs) +
        "\nTask index (IDs and output files only):\n" +
        json.dumps(_task_index(manifest), ensure_ascii=False, sort_keys=True) + "\n"
    )


def build_text_prompt(task: TaskSpec, manifest: dict[str, Any]) -> str:
    packet = "\n\n".join(f"## {_safe(item['taskId'])}\n{item['instruction']}"
                           for item in manifest["tasks"])
    return (_protected_rules(task, manifest) +
            "\nInitial requirement view: exact text; process the complete batch.\n\n" + packet)


def build_image_prompt(task: TaskSpec, manifest: dict[str, Any]) -> str:
    return (
        _protected_rules(task, manifest) +
        "\nInitial requirement view: attached images; process the complete batch. "
        "Read the exact task "
        "requirements from the attached readable image pages; page headers carry "
        "the task IDs. Do not assume that this prompt contains the requirements. "
        "Use the same original-source lookup described above for precise evidence.\n"
    )


def render_representations(manifest: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    if not FONT.is_file():
        raise FileNotFoundError("The verified C++ source font is required; no silent fallback")
    output_dir = Path(output_dir)
    images_root = output_dir / "images"
    images_root.mkdir(parents=True, exist_ok=False)
    records = []
    for index, item in enumerate(manifest["tasks"], 1):
        source_id = _safe(item["taskId"])
        page_dir = images_root / f"{index:02d}-{_safe(item['name'])}"
        rendered = render_text_pages(item["instruction"], source_id, page_dir,
                                     font_path=FONT, width=1800, rows_per_page=42)
        records.append({
            "index": index, "taskId": item["taskId"], "sourceId": source_id,
            "instructionSha256": item["instructionSha256"],
            "sourceSha256": rendered["textSha256"], "textChars": rendered["textChars"],
            "pages": [{"path": p["path"], "sha256": p["sha256"]} for p in rendered["pages"]],
        })
    result = {"schemaVersion": 1, "renderer": "tools.run_classeval_image_text_smoke.render_text_pages",
              "font": str(FONT), "fontSha256": _sha(FONT.read_bytes()),
              "width": 1800, "rowsPerPage": 42, "tasks": records,
              "pageCount": sum(len(item["pages"]) for item in records),
              "textChars": sum(item["textChars"] for item in records)}
    _write_json(output_dir / "representation_manifest.json", result)
    return result


def write_permission_profile(output_dir: Path) -> tuple[Path, str]:
    profile_dir = Path(output_dir) / "profile"
    profile_dir.mkdir(parents=True, exist_ok=False)
    path = profile_dir / f"{PROFILE_NAME}.config.toml"
    path.write_text(PROFILE_TEXT, encoding="utf-8")
    path.chmod(0o444)
    return path, _sha(PROFILE_TEXT.encode())


def _native_command(argv: Iterable[str], profile_host: Path,
                    image_paths: Iterable[Path] = (), pair_host: Path | None = None) -> list[str]:
    """Apply the named permission profile to the native Codex invocation.

    ``IsolatedCodexAdapter`` still supplies the outer bubblewrap boundary and
    the authentication file.  The profile is therefore mounted as the active
    ``$CODEX_HOME/config.toml`` (a ``<name>.config.toml`` file is only a legacy
    config profile), while Codex's ``exec`` process selects the permission
    profile through explicit config values.  This keeps auth available to the
    client while the profile's deny rule applies to model-spawned commands.
    """
    command = list(argv)
    if "--sandbox" not in command:
        raise ValueError("legacy adapter command has no sandbox flag")
    sandbox = command.index("--sandbox")
    del command[sandbox:sandbox + 2]
    if any(flag in command for flag in ("--dangerously-bypass-approvals-and-sandbox", "--approve-for-me")):
        raise ValueError("unsafe approval bypass in adapter command")
    if any("sandbox_mode" in str(value) for value in command):
        raise ValueError("legacy sandbox_mode override in adapter command")
    if "--profile" in command or "-p" in command:
        raise ValueError("config profile is not a permission profile")
    # The outer adapter's --ignore-user-config would also hide the config.toml
    # bind below.  The profile is intentionally the only user config visible
    # inside the outer filesystem namespace.
    command = [value for value in command if value != "--ignore-user-config"]
    # Keep approval behavior deterministic and select the named permission
    # profile without using the legacy sandbox_mode/--sandbox controls.
    model_at = command.index("--model")
    command[model_at:model_at] = [
        "--config", 'approval_policy="never"',
        "--config", f'default_permissions="{PROFILE_NAME}"',
    ]
    proc = command.index("--proc")
    profile_host = Path(profile_host).resolve(strict=True)
    if profile_host.is_symlink() or not profile_host.is_file():
        raise ValueError("permission profile must be a regular file")
    binds = ["--ro-bind", str(profile_host), "/tmp/codex-home/config.toml"]
    image_targets = []
    paths = [Path(path).resolve(strict=True) for path in image_paths]
    if paths:
        binds += ["--dir", "/tmp/representation-images"]
        for n, path in enumerate(paths):
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"image is not a regular file: {path}")
            target = f"/tmp/representation-images/{n:03d}-{_safe(path.name)}"
            binds += ["--ro-bind", str(path), target]
            image_targets.append(target)
    if pair_host is not None:
        pair_host = Path(pair_host).resolve(strict=True)
        if not pair_host.is_dir() or pair_host.is_symlink():
            raise ValueError("pair input must be a regular directory")
        binds += ["--dir", "/tmp/pair-inputs", "--ro-bind", str(pair_host), "/tmp/pair-inputs"]
    command[proc:proc] = binds
    stdin_index = len(command) - 1 - command[::-1].index("-")
    attachments = [value for target in image_targets for value in ("--image", target)]
    command[stdin_index:stdin_index] = attachments
    if ("--sandbox" in command or any("sandbox_mode" in str(value) for value in command)
            or "features.shell_tool=true" not in command
            or "--config" not in command
            or f'default_permissions="{PROFILE_NAME}"' not in command):
        raise ValueError("native command contract failed")
    return command


class RepresentationAdapter:
    def __init__(self, codex_home: Path, profile_host: Path, *, images: list[Path] | None = None,
                 pair_host: Path | None = None):
        self.inner = aider.IsolatedCodexAdapter(codex_home.resolve(), MODEL, EFFORT, AGENT_TIMEOUT)
        self.profile_host, self.images, self.pair_host = Path(profile_host), images or [], pair_host

    def run(self, workspace: Path, prompt: str, artifact_dir: Path, candidate_id: str):
        real_process = aider.run_process

        def wrapped(argv, **kwargs):
            transformed = _native_command(argv, self.profile_host, self.images, self.pair_host)
            redacted = ["<redacted-auth-path>" if "auth.json" in str(value) else value
                        for value in transformed]
            _write_json(artifact_dir / "representation_command.json", {
                "argv": redacted, "profile": PROFILE_NAME, "imagesReadonly": bool(self.images),
                "nativeToolsEnabled": "features.shell_tool=true" in transformed,
                "pairInputsReadonly": self.pair_host is not None,
                "profileConfigTarget": "/tmp/codex-home/config.toml",
                "legacySandboxPresent": "--sandbox" in transformed,
                "legacySandboxModePresent": any("sandbox_mode" in str(value) for value in transformed),
                "userConfigIgnored": "--ignore-user-config" in transformed,
            })
            return real_process(transformed, **kwargs)

        aider.run_process = wrapped
        try:
            return self.inner.run(workspace, prompt, artifact_dir, candidate_id)
        finally:
            aider.run_process = real_process


def _event_items(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _event_items(child)
    elif isinstance(value, list):
        for child in value:
            yield from _event_items(child)


def record_source_reads(artifact_dir: Path) -> None:
    paths, command_count = set(), 0
    events = Path(artifact_dir) / "events.jsonl"
    if events.is_file():
        for line in events.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            for item in _event_items(event):
                if item.get("type") != "command_execution":
                    continue
                command_count += 1
                text = str(item.get("command", ""))
                paths.update(re.findall(r"tasks/cpp/[A-Za-z0-9_.-]+/(?:\.docs/)?[A-Za-z0-9_./*-]+", text))
    _write_json(Path(artifact_dir) / "source-read-ledger.json", {
        "bestEffort": True, "commandExecutionEvents": command_count,
        "observedPaths": sorted(paths),
        "note": "Only shell command events are observable; direct API reads are not claimed.",
    })


def _turn_usage(artifact_dir: Path) -> dict[str, Any] | None:
    events = Path(artifact_dir) / "events.jsonl"
    if not events.is_file():
        return None
    for line in events.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        for item in _event_items(event):
            if item.get("type") == "turn.completed" and isinstance(item.get("usage"), dict):
                return item["usage"]
    return None


def _evaluator_inventory(attempt: Any, expected_ids: Iterable[str]) -> dict[str, Any]:
    observed = []
    for line in attempt.public_test.stdout.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("taskId") and not item.get("summary"):
            observed.append(str(item["taskId"]))
    expected = list(expected_ids)
    return {"orderedTaskIds": observed, "expectedTaskIds": expected,
            "count": len(observed), "unique": len(observed) == len(set(observed)),
            "complete": observed == expected}


def _attempt_vector(attempt: Any, expected_ids: Iterable[str]) -> list[int | None]:
    outcomes = aider.task_outcomes(attempt)
    return [int(outcomes[task_id]) if task_id in outcomes else None for task_id in expected_ids]


def _valid_parent(attempt: Any, expected_ids: Iterable[str],
                  integrity: dict[str, Any] | None = None) -> bool:
    """Return whether a complete, scoped baseline may seed reconciliation.

    Exit code 1 from the official evaluator is a normal completed track with
    failing tasks, so it remains eligible for per-task passing rows.  The
    whole parent is rejected only for execution/evaluator failure, incomplete
    inventory, forbidden edits, or failed integrity checks.
    """
    if attempt.agent.timed_out or attempt.agent.exit_code != 0:
        return False
    if attempt.public_test.timed_out or attempt.public_test.exit_code not in (0, 1):
        return False
    if attempt.forbidden_files or not _evaluator_inventory(attempt, expected_ids)["complete"]:
        return False
    if integrity is not None and (
        not integrity.get("valid", False)
        or integrity.get("agentFailure", False)
        or integrity.get("evaluatorFailure", False)
    ):
        return False
    return True


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(Path(root).rglob("*")):
        if path.is_file() and path.name != "package.sha256":
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _readonly_tree(root: Path) -> None:
    for path in sorted(Path(root).rglob("*"), reverse=True):
        if path.is_symlink():
            raise ValueError(f"unexpected symlink in pair input: {path}")
        path.chmod(0o555 if path.is_dir() else 0o444)


def stage_pair_inputs(source_repo: Path, task: TaskSpec, manifest: dict[str, Any], pair_root: Path,
                      pair_id: str, labels: tuple[str, str], attempts: dict[str, Any],
                      parent_integrities: dict[str, dict[str, Any]] | None = None) -> tuple[Path, str, dict[str, Any], dict[str, bytes]]:
    expected_ids = tuple(item["taskId"] for item in manifest["tasks"])
    parent_inventories = {label: _evaluator_inventory(attempts[label], expected_ids) for label in labels}
    for label in labels:
        if not _valid_parent(attempts[label], expected_ids,
                             (parent_integrities or {}).get(label)):
            raise ValueError(f"invalid baseline parent for pair {pair_id}: {label}")
    pair_root = Path(pair_root) / pair_id
    pair_root.mkdir(parents=True, exist_ok=False)
    candidates = pair_root / "candidates"
    outcomes = {label: aider.task_outcomes(attempts[label]) for label in labels}
    source_files = {}
    for label in labels:
        candidate_root = candidates / label
        candidate_root.mkdir(parents=True)
        attempt = attempts[label]
        (pair_root / f"{label}.patch").write_text(attempt.patch_text, encoding="utf-8")
        _write_json(pair_root / f"{label}.test-evidence.json", aider.compact_test_evidence(attempt))
        source = Path(attempt.workspace)
        source_files[label] = {}
        for item in manifest["tasks"]:
            relative_dir = Path(item["relativePath"])
            for name in item["solutionFiles"]:
                relative = relative_dir / name
                payload = (source / relative).read_bytes()
                target = candidate_root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
                source_files[label][relative.as_posix()] = _sha(payload)
    decisions = []
    anchors: dict[str, bytes] = {}
    with tempfile.TemporaryDirectory(prefix=f"aider-pair-{pair_id}-") as temp:
        workspace = Path(temp) / "workspace"
        prepare_workspace(source_repo, task.base_ref, workspace)
        for item in manifest["tasks"]:
            task_id = item["taskId"]
            selected = next((label for label in labels if outcomes[label].get(task_id, False)), None)
            decisions.append({"taskId": task_id, "selected": selected,
                              "outcomes": {label: outcomes[label].get(task_id, False) for label in labels}})
            if selected:
                for name in item["solutionFiles"]:
                    relative = Path(item["relativePath"]) / name
                    destination = workspace / relative
                    payload = (candidates / selected / relative).read_bytes()
                    destination.write_bytes(payload)
                    anchors[relative.as_posix()] = payload
        _, seed_patch, seed_sha, seed_lines = collect_patch(workspace)
    (pair_root / "seed.patch").write_text(seed_patch, encoding="utf-8")
    context = {"schemaVersion": 1, "pairId": pair_id, "labels": list(labels),
               "tieRule": "first listed candidate wins among passing candidates",
               "outcomes": outcomes, "decisions": decisions, "seedPatchSha256": seed_sha,
               "candidatePatchSha256": {label: _sha((pair_root / f"{label}.patch").read_bytes()) for label in labels},
               "candidateSourceSha256": source_files, "anchorSha256": {
                   relative: _sha(payload) for relative, payload in sorted(anchors.items())
               }, "seedPatchLines": seed_lines, "parentInventories": parent_inventories,
               "parentsValid": True}
    _write_json(pair_root / "context.json", context)
    package_sha = _tree_hash(pair_root)
    (pair_root / "package.sha256").write_text(package_sha + "\n", encoding="utf-8")
    _readonly_tree(pair_root)
    return pair_root, package_sha, context, anchors


def _session(root: Path, source_repo: Path, task: TaskSpec, label: str, prompt: str,
             profile: Path, *, images: list[Path] | None = None, pair_host: Path | None = None,
             pair_package_sha: str | None = None, anchors: dict[str, bytes] | None = None,
             seed_patch: str | None = None, expected_ids: tuple[str, ...] = (),
             progress_path: Path | None = None, immutable_files: dict[str, str] | None = None) -> tuple[Any, dict[str, Any]]:
    output = Path(root) / "sessions" / label
    output.mkdir(parents=True, exist_ok=False)
    adapter: Any = RepresentationAdapter(DEFAULT_CODEX_HOME, profile, images=images, pair_host=pair_host)
    if anchors:
        adapter = aider.VerifiedAnchorAdapter(adapter, anchors)
    immutable_files = immutable_files or {}

    def file_checks() -> dict[str, dict[str, Any]]:
        checks = {}
        for raw_path, expected in immutable_files.items():
            path = Path(raw_path)
            observed = _sha(path.read_bytes()) if path.is_file() and not path.is_symlink() else None
            checks[raw_path] = {"expected": expected, "observed": observed, "match": observed == expected}
        return checks

    def pair_hash() -> str | None:
        return _tree_hash(pair_host) if pair_host is not None else None

    pre_files = file_checks()
    pre_pair = pair_hash()
    pre_pair_match = pair_package_sha is None or pre_pair == pair_package_sha
    if not pre_pair_match or not all(item["match"] for item in pre_files.values()):
        raise ValueError(f"immutable session inputs changed before {label}")
    attempt = execute_attempt(source_repo=source_repo, task=task, output_dir=output,
                               candidate_id=label, policy=label,
                               adapter=adapter, public_test_timeout_seconds=EVALUATOR_TIMEOUT,
                               prompt_override=prompt, seed_patch=seed_patch)
    artifact = output / "attempts" / label
    record_source_reads(artifact)
    inventory = _evaluator_inventory(attempt, expected_ids)
    anchor_checks = {}
    for relative, payload in (anchors or {}).items():
        path = Path(attempt.workspace) / relative
        observed = _sha(path.read_bytes()) if path.is_file() else None
        anchor_checks[relative] = {"expected": _sha(payload), "observed": observed,
                                   "match": observed == _sha(payload)}
    pair_observed = pair_hash()
    post_files = file_checks()
    agent_failure = bool(attempt.agent.timed_out or attempt.agent.exit_code != 0)
    evaluator_failure = bool(attempt.public_test.timed_out or attempt.public_test.exit_code not in (0, 1))
    integrity = {
        "evaluatorInventory": inventory,
        "pairPackage": {"expected": pair_package_sha, "before": pre_pair, "observed": pair_observed,
                         "beforeMatch": pre_pair_match,
                         "match": pair_package_sha is None or pair_observed == pair_package_sha},
        "anchors": anchor_checks,
        "anchorsMatch": all(item["match"] for item in anchor_checks.values()),
        "immutableFiles": post_files,
        "immutableFilesBefore": pre_files,
        "immutableFilesMatch": all(item["match"] for item in post_files.values()),
        "immutableFilesBeforeMatch": all(item["match"] for item in pre_files.values()),
        "forbiddenFiles": list(attempt.forbidden_files),
        "scopeValid": not attempt.forbidden_files,
        "agentFailure": agent_failure,
        "evaluatorFailure": evaluator_failure,
    }
    integrity["valid"] = bool(
        inventory["complete"] and integrity["pairPackage"]["beforeMatch"]
        and integrity["pairPackage"]["match"] and integrity["anchorsMatch"]
        and integrity["immutableFilesBeforeMatch"] and integrity["immutableFilesMatch"]
        and integrity["scopeValid"]
    )
    _write_json(artifact / "integrity.json", integrity)
    if progress_path is not None:
        progress_path = Path(progress_path)
        progress = _json(progress_path) if progress_path.is_file() else {
            "schemaVersion": 1, "plannedSessions": 12, "completedSessions": 0, "sessions": {}
        }
        attempt_result_path = artifact / "result.json"
        progress["sessions"][label] = {
            "agentExitCode": attempt.agent.exit_code, "agentTimedOut": attempt.agent.timed_out,
            "agentDurationSeconds": attempt.agent.duration_seconds,
            "evaluatorExitCode": attempt.public_test.exit_code,
            "evaluatorTimedOut": attempt.public_test.timed_out,
            "evaluatorDurationSeconds": attempt.public_test.duration_seconds,
            "usage": _turn_usage(artifact),
            "usageStatus": "observed" if _turn_usage(artifact) is not None else "unknown",
            "patchSha256": attempt.patch_sha256,
            "resultSha256": _sha(attempt_result_path.read_bytes()) if attempt_result_path.is_file() else None,
            "inventory": inventory, "integrity": integrity,
        }
        progress["completedSessions"] = len(progress["sessions"])
        _write_json(progress_path, progress)
    return attempt, integrity


def _gate(attempts: dict[str, Any], expected_ids: tuple[str, ...]) -> dict[str, Any]:
    vectors = {label: _attempt_vector(attempt, expected_ids) for label, attempt in attempts.items()}
    def score_count(label: str) -> int | None:
        vector = vectors.get(label)
        return None if vector is None or any(x is None for x in vector) else sum(vector)

    def delta_count(left: str, right: str) -> int | None:
        left_count, right_count = score_count(left), score_count(right)
        return None if left_count is None or right_count is None else left_count - right_count

    def delta(left: str, right: str) -> float | None:
        a, b = vectors.get(left), vectors.get(right)
        if a is None or b is None or any(x is None or y is None for x, y in zip(a, b)):
            return None
        return sum(x - y for x, y in zip(a, b)) / len(expected_ids)
    def score(label: str) -> float | None:
        vector = vectors.get(label)
        return None if vector is None or any(x is None for x in vector) else sum(vector) / len(vector)
    d = {pair: delta(f"{pair}_O", f"{pair}_G") for pair in ("TT", "II", "TIa", "TIb")}
    d_counts = {pair: delta_count(f"{pair}_O", f"{pair}_G") for pair in ("TT", "II", "TIa", "TIb")}
    d_ti = None if d["TIa"] is None or d["TIb"] is None else (d["TIa"] + d["TIb"]) / 2
    d_h = None if d["TT"] is None or d["II"] is None else (d["TT"] + d["II"]) / 2
    interaction = None if d_ti is None or d_h is None else d_ti - d_h
    o_ti = None if score("TIa_O") is None or score("TIb_O") is None else (score("TIa_O") + score("TIb_O")) / 2
    o_tt, o_ii = score("TT_O"), score("II_O")
    full = all(score(label) is not None for label in ("TT_G", "TT_O", "II_G", "II_O", "TIa_G", "TIa_O", "TIb_G", "TIb_O"))
    ti_count = None if d_counts["TIa"] is None or d_counts["TIb"] is None else d_counts["TIa"] + d_counts["TIb"]
    homogeneous_count = None if d_counts["TT"] is None or d_counts["II"] is None else d_counts["TT"] + d_counts["II"]
    interaction_count = None if ti_count is None or homogeneous_count is None else ti_count - homogeneous_count
    mixed_o_count = None if score_count("TIa_O") is None or score_count("TIb_O") is None else score_count("TIa_O") + score_count("TIb_O")
    criteria = {"dTIAtLeast2Over26": ti_count is not None and ti_count >= 4,
                "interactionAtLeast1Over26": interaction_count is not None and interaction_count >= 2,
                "mixedONotBelowHomogeneous": mixed_o_count is not None and score_count("TT_O") is not None
                and score_count("II_O") is not None and mixed_o_count >= 2 * score_count("TT_O")
                and mixed_o_count >= 2 * score_count("II_O")}
    score_labels = ("TT_G", "TT_O", "II_G", "II_O", "TIa_G", "TIa_O", "TIb_G", "TIb_O")
    return {"primaryDeltas": d, "dTI": d_ti, "dHomogeneous": d_h, "interaction": interaction,
            "scores": {label: score(label) for label in score_labels},
            "increments": d, "incrementCounts": d_counts,
            "integerGateCounts": {"mixedInteractionNumerator": interaction_count,
                                   "mixedONumerator": mixed_o_count},
            "oMeans": {"TI": o_ti, "TT": o_tt, "II": o_ii},
            "fullVectors": full, "criteria": criteria,
            "advanceGate": {"criteria": criteria, "eligible": full and all(criteria.values())},
            "eligible": full and all(criteria.values())}


def _write_results(run_root: Path, attempts: dict[str, Any], expected_ids: tuple[str, ...],
                   *, status: str = "running", pair_inputs: dict[str, Any] | None = None) -> dict[str, Any]:
    sessions = {}
    for label, attempt in attempts.items():
        artifact = Path(run_root) / "sessions" / label / "attempts" / label
        inventory = _evaluator_inventory(attempt, expected_ids)
        integrity = _json(artifact / "integrity.json") if (artifact / "integrity.json").is_file() else None
        vector = _attempt_vector(attempt, expected_ids)
        usage = _turn_usage(artifact)
        sessions[label] = {
            "vector": vector,
            "passedCount": sum(value or 0 for value in vector),
            "missingCount": sum(value is None for value in vector),
            "agent": {"exitCode": attempt.agent.exit_code, "timedOut": attempt.agent.timed_out,
                      "durationSeconds": attempt.agent.duration_seconds},
            "evaluator": {"exitCode": attempt.public_test.exit_code, "timedOut": attempt.public_test.timed_out,
                          "durationSeconds": attempt.public_test.duration_seconds},
            "usage": usage, "usageStatus": "observed" if usage is not None else "unknown",
            "patchSha256": attempt.patch_sha256,
            "resultSha256": _sha((artifact / "result.json").read_bytes()) if (artifact / "result.json").is_file() else None,
            "failureAccounting": {
                "agentFailure": bool(attempt.agent.timed_out or attempt.agent.exit_code != 0),
                "evaluatorFailure": bool(attempt.public_test.timed_out or attempt.public_test.exit_code not in (0, 1)),
                "inventoryInvalid": not inventory["complete"],
                "scopeInvalid": bool(attempt.forbidden_files),
            },
            "inventory": inventory, "integrity": integrity,
        }
    planned_labels = [label for label, _ in BASELINE_PLAN]
    for pair_id, policies in (("TT", ("G", "O")), ("II", ("O", "G")),
                              ("TIa", ("O", "G")), ("TIb", ("G", "O"))):
        planned_labels.extend(f"{pair_id}_{policy}" for policy in policies)
    operational_complete = len(attempts) == len(planned_labels) and all(
        not item["failureAccounting"]["agentFailure"]
        and not item["failureAccounting"]["evaluatorFailure"]
        for item in sessions.values()
    )
    inventory_complete = bool(sessions) and all(item["inventory"]["complete"] for item in sessions.values())
    integrity_valid = bool(sessions) and all(item["integrity"] and item["integrity"].get("valid", False)
                                            for item in sessions.values())
    if status == "complete":
        if not operational_complete:
            status = "incomplete"
        elif not inventory_complete:
            status = "complete-invalid-inventory"
        elif not integrity_valid:
            status = "complete-invalid-integrity"
    result = {"schemaVersion": 1, "status": status, "tasks": len(expected_ids),
              "orderedTaskIds": list(expected_ids), "sessions": sessions,
              "plannedSessionOrder": planned_labels,
              "completion": {"plannedSessions": len(planned_labels), "recordedSessions": len(attempts),
                              "operationalComplete": operational_complete,
                              "inventoryComplete": inventory_complete,
                              "integrityValid": integrity_valid},
              "pairInputs": pair_inputs or {}, "vectors": {label: item["vector"] for label, item in sessions.items()},
              "gate": _gate(attempts, expected_ids) if all(label in attempts for label in
                  ("TT_G", "TT_O", "II_G", "II_O", "TIa_G", "TIa_O", "TIb_G", "TIb_O")) else None}
    if result["gate"] is not None:
        result["gate"]["operationalComplete"] = operational_complete
        result["gate"]["inventoryComplete"] = inventory_complete
        result["gate"]["integrityValid"] = integrity_valid
        result["gate"]["eligible"] = bool(result["gate"]["eligible"] and operational_complete
                                            and inventory_complete and integrity_valid)
        result["gate"]["advanceGate"]["eligible"] = result["gate"]["eligible"]
    _write_json(Path(run_root) / "result.json", result)
    return result


def run_experiment(freeze_root: Path, run_root: Path) -> dict[str, Any]:
    source_repo, task, manifest = _load_freeze(freeze_root)
    freeze_root = Path(freeze_root).resolve()
    run_root = Path(run_root).resolve()
    run_root.mkdir(parents=True, exist_ok=False)
    profile, profile_sha = write_permission_profile(run_root)
    representations = render_representations(manifest, run_root / "representations")
    image_paths = [Path(page["path"]) for item in representations["tasks"] for page in item["pages"]]
    policy_orders = {"TT": ("G", "O"), "II": ("O", "G"),
                     "TIa": ("O", "G"), "TIb": ("G", "O")}
    freeze_path = freeze_root / "freeze.json"
    freeze_metadata = _json(freeze_path)
    task_path = freeze_root / "public" / "task.json"
    source_manifest_path = source_repo / "benchmark_manifest.json"
    source_manifest_sha = _sha(source_manifest_path.read_bytes())
    source_code_path = Path(__file__).resolve()
    source_code_sha = _sha(source_code_path.read_bytes())
    source_sha = _sha(task.instruction.encode())
    evaluator_sha = _sha(EVALUATOR_PATH.read_bytes())
    immutable_base = {str(freeze_path): _sha(freeze_path.read_bytes()),
                      str(task_path): _sha(task_path.read_bytes()),
                      str(source_manifest_path.resolve()): source_manifest_sha,
                      str(EVALUATOR_PATH.resolve()): evaluator_sha,
                      str(profile.resolve()): profile_sha,
                      str(source_code_path): source_code_sha}
    expected_ids = tuple(item["taskId"] for item in manifest["tasks"])
    contract = {"schemaVersion": 1, "status": "development", "freezeRoot": str(Path(freeze_root).resolve()),
                "tasks": 26, "model": MODEL, "effort": EFFORT,
                "agentTimeoutSeconds": AGENT_TIMEOUT, "evaluatorTimeoutSeconds": EVALUATOR_TIMEOUT,
                "permissionProfile": PROFILE_NAME, "permissionProfileSha256": profile_sha,
                "baselinePlan": [{"label": x, "view": y} for x, y in BASELINE_PLAN],
                "pairPlan": [{"pair": x, "labels": list(y), "policies": list(policy_orders[x])}
                             for x, y in PAIR_PLAN],
                "noTaskSelection": True, "officialTestFeedbackDevelopmentAssay": True,
                "imagePageCount": representations["pageCount"], "imageTextChars": representations["textChars"],
                "taskInstructionSha256": source_sha, "sourceManifestSha256": source_manifest_sha,
                "runnerSourceSha256": source_code_sha, "freezeMetadataSha256": _sha(freeze_path.read_bytes()),
                "taskFileSha256": freeze_metadata["taskSha256"],
                "evaluatorSha256": freeze_metadata["evaluatorSha256"],
                "sourceCommit": freeze_metadata["sourceCommit"],
                "selectedTaskIds": list(expected_ids),
                "reconciliationOrder": ["TT_G", "TT_O", "II_O", "II_G", "TIa_O", "TIa_G", "TIb_G", "TIb_O"]}
    _write_json(run_root / "experiment_contract.json", contract)
    attempts: dict[str, Any] = {}
    baseline_integrities: dict[str, dict[str, Any]] = {}
    progress_path = run_root / "progress.json"
    image_hashes = {str(path.resolve()): _sha(path.read_bytes()) for path in image_paths}
    for label, view in BASELINE_PLAN:
        prompt = build_text_prompt(task, manifest) if view == "text" else build_image_prompt(task, manifest)
        attempts[label], baseline_integrities[label] = _session(
            run_root, source_repo, task, label, prompt, profile,
            images=image_paths if view == "image" else None,
            expected_ids=expected_ids, progress_path=progress_path,
            immutable_files=immutable_base | (image_hashes if view == "image" else {}))
        _write_results(run_root, attempts, expected_ids)
        if not _valid_parent(attempts[label], expected_ids, baseline_integrities[label]):
            result = _write_results(run_root, attempts, expected_ids, status="incomplete")
            return {"runRoot": str(run_root), "sessions": list(attempts), "contract": contract,
                    "status": result["status"], "resultPath": str(run_root / "result.json")}
    summaries, staged = {}, {}
    for pair_id, labels in PAIR_PLAN:
        pair_root, package_sha, context, anchors = stage_pair_inputs(source_repo, task, manifest,
                                                                      run_root / "pairs", pair_id, labels, attempts,
                                                                      parent_integrities=baseline_integrities)
        staged[pair_id] = (pair_root, package_sha, context, anchors)
        summaries[pair_id] = {"packageSha256": package_sha, "candidateLabels": list(labels),
                              "seedPatchSha256": context["seedPatchSha256"],
                              "anchorSha256": context["anchorSha256"]}
    _write_json(run_root / "session_inputs.json", summaries)
    if all(context.get("parentsValid", False) and
           all(decision["selected"] is not None for decision in context["decisions"])
           for _, _, context, _ in staged.values()):
        result = _write_results(run_root, attempts, expected_ids, status="ceiling", pair_inputs=summaries)
        result["ceilingReason"] = "all four pair verified-unions cover all 26 tasks"
        _write_json(run_root / "result.json", result)
        return {"runRoot": str(run_root), "sessions": list(attempts), "contract": contract, "status": "ceiling"}
    for pair_id, labels in PAIR_PLAN:
        pair_root, package_sha, context, anchors = staged[pair_id]
        common = ("Continue the complete frozen C++26 repair from the identical pair seed. "
                  "The frozen benchmark_manifest.json and official evaluator feedback remain available. "
                  "Read /tmp/pair-inputs/context.json and the immutable candidate patches/sources; "
                  "tasks with a selected passing parent are verified anchors and their exact "
                  "solution bytes will be restored after this session in both policies. "
                  "Focus repair on unresolved tasks. A passing test or agreement is not a "
                  "proof of general semantic correctness. "
                  "tests and gold are unavailable.\n" + _protected_rules(task, manifest) +
                  f"Pair={pair_id}; packageSha256={package_sha}.\n")
        for policy in policy_orders[pair_id]:
            policy_text = ("Policy G: use a strong generic repair/adjudication of both candidates and "
                           "bounded feedback, with the same tools and opportunity to inspect/test "
                           "counterexamples; freely compare the original sources and failures and "
                           "make any justified repair.\n" if policy == "G" else
                           "Policy O: use the same-source locator to identify shared premises and "
                           "boundaries in both candidates, test a concrete counterexample/boundary, "
                           "then make an original-source-grounded repair. Agreement between candidates "
                           "is evidence to check, never truth by itself.\n")
            label = f"{pair_id}_{policy}"
            attempts[label], _ = _session(run_root, source_repo, task, label, common + policy_text,
                                          profile, pair_host=pair_root, pair_package_sha=package_sha,
                                          anchors=anchors, expected_ids=expected_ids,
                                          progress_path=progress_path,
                                          immutable_files=immutable_base,
                                          seed_patch=(pair_root / "seed.patch").read_text(encoding="utf-8"))
            summaries[label] = {"packageSha256": package_sha, "candidateLabels": list(labels),
                                "policy": policy, "seedPatchSha256": context["seedPatchSha256"],
                                "anchorSha256": context["anchorSha256"]}
            _write_json(run_root / "session_inputs.json", summaries)
            _write_results(run_root, attempts, expected_ids, pair_inputs=summaries)
    result = _write_results(run_root, attempts, expected_ids, status="complete", pair_inputs=summaries)
    return {"runRoot": str(run_root), "sessions": list(attempts), "contract": contract,
            "status": result["status"], "resultPath": str(run_root / "result.json")}


def dry_run(freeze_root: Path) -> dict[str, Any]:
    source_repo, task, manifest = _load_freeze(freeze_root)
    with tempfile.TemporaryDirectory(prefix="aider-cpp26-image-dry-") as temp:
        root = Path(temp)
        profile, profile_sha = write_permission_profile(root)
        representations = render_representations(manifest, root / "representations")
        images = [Path(page["path"]) for item in representations["tasks"] for page in item["pages"]]
        fake = ["bwrap", "--dir", "/tmp/codex-home", "--ro-bind", "/host/auth", "/tmp/codex-home/auth.json",
                "--proc", "/proc", "node", "codex.js", "exec", "--sandbox", "danger-full-access",
                "--model", MODEL, "--config", "features.shell_tool=true", "-"]
        transformed = _native_command(fake, profile, images[:1])
        return {"mode": "dry-run", "tasks": len(manifest["tasks"]), "sessions": 12,
                "imagePageCount": representations["pageCount"], "imageTextChars": representations["textChars"],
                "profile": PROFILE_NAME, "profileSha256": profile_sha,
                "legacySandboxPresent": "--sandbox" in transformed,
                "nativeToolsEnabled": "features.shell_tool=true" in transformed,
                "textPromptSha256": _sha(build_text_prompt(task, manifest).encode()),
                "imagePromptSha256": _sha(build_image_prompt(task, manifest).encode()),
                "baselinePlan": BASELINE_PLAN, "pairPlan": PAIR_PLAN,
                "reconciliationOrder": ("TT_G", "TT_O", "II_O", "II_G",
                                         "TIa_O", "TIa_G", "TIb_G", "TIb_O"),
                "agentTimeoutSeconds": AGENT_TIMEOUT, "evaluatorTimeoutSeconds": EVALUATOR_TIMEOUT}


def _record_incomplete(run_root: Path, error: BaseException) -> None:
    """Attach a terminal error to a run created by this invocation.

    A pre-existing run root is never touched by the caller on a
    ``FileExistsError``.  If a newly-created root already has a partial result,
    retain all of its fields and only change its terminal status/metadata.
    """
    run_root = Path(run_root)
    metadata = {"type": type(error).__name__, "message": str(error)}
    error_path = run_root / "error.json"
    result_path = run_root / "result.json"
    if not run_root.is_dir():
        return
    try:
        if result_path.is_file():
            result = _json(result_path)
            if not isinstance(result, dict):
                raise ValueError("partial result is not an object")
        else:
            result = {"schemaVersion": 1, "runRoot": str(run_root)}
        result["status"] = "incomplete"
        result["error"] = metadata
        _write_json(result_path, result)
        _write_json(error_path, metadata)
    except Exception as persist_error:
        # Preserve a malformed/locked partial result and leave a best-effort
        # diagnostic beside it without masking the original failure.
        try:
            _write_json(error_path, metadata | {"persistenceError": str(persist_error)})
        except Exception:
            pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-root", type=Path, default=DEFAULT_FREEZE)
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        print(json.dumps(dry_run(args.freeze_root), ensure_ascii=False))
        return 0
    if args.run_root is None:
        parser.error("--run-root is required with --execute")
    run_root = Path(args.run_root).resolve()
    preexisting = run_root.exists()
    try:
        result = run_experiment(args.freeze_root, run_root)
    except Exception as error:
        if not preexisting:
            _record_incomplete(run_root, error)
        print(json.dumps({"status": "incomplete", "error": {
            "type": type(error).__name__, "message": str(error)
        }}, ensure_ascii=False), file=sys.stderr, flush=True)
        return 1
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
