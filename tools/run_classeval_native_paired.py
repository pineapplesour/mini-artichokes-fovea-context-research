"""Native paired-probe Luna experiment over the fixed ClassEval-Pro tail.

The runner is deliberately thin.  It reuses the ordinary-prefix loader, the
frozen full-view/selector, the official evaluator, and the dependency
separator only for static ``S`` metadata.  Dry-run is the default and has no
model/evaluator/auth effect; ``--execute`` is the sole switch that enables the
fresh O/G Codex calls and their evaluator calls.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
from pathlib import Path
import re
import shlex
import shutil
import sys
import time
from typing import Any, Callable, Iterable

# Direct ``python tools/run_...py`` invocation otherwise places ``tools/``
# ahead of the repository root and can resolve an unrelated site-package.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import classeval_ordinary_prefix as prefix_loader
from tools import dependency_separator_overlap as separator
from tools import overlap_split_merge_candidate as scope_operator
from tools import run_aider_hidden20_arm as isolated
from tools import run_classeval_overlap_repair_tail as frozen_tail
from tools import run_classeval_source_overlap as base
from tools import run_classeval_text_overlap as text_runner


ROOT = base.ROOT
PROTOCOL = ROOT / "experiment_protocols/2026-09-06-classeval-native-paired-development.md"
TOTAL_TASKS = 300
EXPECTED_PASSED = 268
EXPECTED_FAILURES = 32
ARMS = ("G", "O")
MODEL, EFFORT, TIMEOUT = "gpt-5.6-luna", "medium", 120
TAIL_CALLS = 1
FRESH_SOLVER_SESSIONS = EXPECTED_FAILURES * len(ARMS)
SUITE_EVAL_CAP = 6
HELPER_ROOT = Path("/opt/paired")
HELPER_NAME = "paired_probe.py"
HELPER_COMMAND = "/tmp/native-venv/bin/python /opt/paired/paired_probe.py --probe /tmp/work/probe_name.py"


def _json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _failure(message: str) -> dict[str, Any]:
    return {"passed": False, "cases": {}, "fatal": message}


def _inside(root: Path, path: Path) -> Path:
    root, resolved = Path(root).resolve(), Path(path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("artifact path escapes its bound root") from exc
    return resolved


def _ordered_ids(rows: list[dict]) -> list[str]:
    return [str(row["task_id"]) for row in rows]


def _validate_parent(parent_root: Path, rows: list[dict],
                     prefixes: dict[str, dict]) -> None:
    parent_root = Path(parent_root).resolve()
    result = _json(parent_root / "result.json")
    ids = _ordered_ids(rows)
    if (result.get("completed") != TOTAL_TASKS or result.get("total") != TOTAL_TASKS
            or list(result.get("tasks", {})) != ids or list(prefixes) != ids):
        raise ValueError("terminal full-300 ordinary prefix required")
    passed = sum(bool(prefixes[task_id]["report"].get("passed")) for task_id in ids)
    if passed != EXPECTED_PASSED or TOTAL_TASKS - passed != EXPECTED_FAILURES:
        raise ValueError("ordinary prefix must contain exactly 268 passed and U32")


def _e_context(row: dict, prefix: dict) -> tuple[tuple[str, ...], tuple[str, ...], dict, dict | None]:
    labels = frozen_tail.target_method_labels(row, prefix["source"]) or ("whole_program",)
    ordered, anchor_hint = frozen_tail.choose_failure_anchor(labels, prefix["report"])
    feedback = frozen_tail.observed_feedback(prefix["report"], ordered)
    feedback["bridgeHint"] = anchor_hint
    return labels, ordered, feedback, anchor_hint


def _load_old_e_ab(e_root: Path, parent_root: Path, rows: list[dict],
                   prefixes: dict[str, dict]) -> dict[str, dict[str, dict]]:
    """Validate frozen E A/B receipts and return read-only candidates.

    The loader intentionally validates each cached prompt against the frozen
    independent prompt.  It never invokes a model or evaluator.
    """
    root = Path(e_root).resolve()
    contract = _json(root / "contract.json")
    result = _json(root / "result.json")
    expected = frozen_tail._build_contract(root, parent_root, rows, prefixes)
    if contract != expected:
        raise ValueError("old E cache contract differs from frozen tail")
    ids = _ordered_ids(rows)
    if (result.get("status") != "complete" or result.get("completed") != TOTAL_TASKS
            or result.get("total") != TOTAL_TASKS or list(result.get("tasks", {})) != ids):
        raise ValueError("completed full-300 E cache required")
    by_id = {row["task_id"]: row for row in rows}
    loaded: dict[str, dict[str, dict]] = {}
    for task_id in ids:
        prefix = prefixes[task_id]
        if prefix["report"].get("passed"):
            continue
        row = by_id[task_id]
        _, ordered, feedback, _ = _e_context(row, prefix)
        plan = scope_operator.build_scope_plans(ordered)["E"]
        expected_a = root / task_id / "E" / "a"
        expected_b = root / task_id / "E" / "b"
        state = result["tasks"][task_id].get("E")
        if not isinstance(state, dict) or state.get("status") != "executed":
            raise ValueError(f"missing old E state: {task_id}")
        paths = state.get("callPaths") or {}
        if "A" in paths and _inside(root, Path(paths["A"])) != expected_a.resolve():
            raise ValueError(f"old E/A path mismatch: {task_id}")
        prompt_a = frozen_tail._independent_prompt(row, prefix, plan, "A", ordered, feedback)
        prompt_b = frozen_tail._independent_prompt(row, prefix, plan, "B", ordered, feedback)
        a = prefix_loader._call(row, expected_a, "tail-E-A", prompt_a)
        b = prefix_loader._call(row, expected_b, "tail-E-B", prompt_b)
        if a.get("valid") is not True or b.get("valid") is not True:
            raise ValueError(f"old E A/B must both be valid: {task_id}")
        loaded[task_id] = {"A": a, "B": b}
    if len(loaded) != EXPECTED_FAILURES:
        raise ValueError("old E A/B cache must cover exactly U32")
    return loaded


def _full_ab(row: dict, prefix: dict, cached: dict[str, dict],
             evaluate_fn: Callable) -> dict[str, dict]:
    """Canonicalize/evaluate cached A and B once, with no scope projection."""
    result: dict[str, dict] = {}
    for label in ("A", "B"):
        source, report, valid, calls, _, _ = frozen_tail._full_view(
            row, prefix, cached[label], evaluate_fn)
        result[label] = {"source": source, "report": report, "valid": valid,
                         "canonicalEvalCalls": calls, "cached": True,
                         "path": cached[label].get("path")}
    return result


def _common_prompt(row: dict, prefix: dict, plan: separator.SeparatorPlan,
                   labels: tuple[str, ...], feedback: dict,
                   full_ab: dict[str, dict]) -> str:
    """Common prompt bytes shared by G and O, excluding policy instruction."""
    a, b = full_ab["A"], full_ab["B"]
    return (
        "Native paired Luna repair. Use only the caller-verified original "
        "skeleton, common ordinary source, full canonical candidate A/B, and "
        "bounded observed evaluator feedback below. Tests, gold/reference "
        "solutions, raw test source, network, web search, and external files "
        "are unavailable and forbidden. Do not expose or reconstruct them.\n"
        f"class_name: {row['class_name']}\n"
        f"Skeleton:\n{row['skeleton']}\n"
        f"Common ordinary source:\n{prefix['source']}\n"
        f"Candidate A full canonical source:\n---\n{a['source']}\n---\n"
        f"Candidate A bounded observed feedback:\n"
        f"{json.dumps(frozen_tail.observed_feedback(a['report'], labels), ensure_ascii=False, sort_keys=True)}\n"
        f"Candidate B full canonical source:\n---\n{b['source']}\n---\n"
        f"Candidate B bounded observed feedback:\n"
        f"{json.dumps(frozen_tail.observed_feedback(b['report'], labels), ensure_ascii=False, sort_keys=True)}\n"
        f"Common prefix feedback:\n{json.dumps(feedback, ensure_ascii=False, sort_keys=True)}\n"
        f"Ordered target methods: {', '.join(labels)}\n"
        f"Dependency-separator metadata (context only; do not change scopes): "
        f"S={list(plan.shared)!r}; A-exclusive={list(plan.a_exclusive)!r}; "
        f"B-exclusive={list(plan.b_exclusive)!r}; fallback={plan.fallback}\n"
        "The same native helper opportunity is available in both policies. "
        "If you use it, create a probe under /tmp/work and invoke exactly "
        f"`{HELPER_COMMAND}`. The helper accepts `def probe(candidate_module)` and "
        "returns JSON; it exposes only the two supplied candidates and no tests. "
        "Do not trust a prose claim without the command event and JSON output.\n"
        "Write one complete executable class to /tmp/work/solution.py and return "
        "one Python code block containing the same complete source. Put every def "
        "signature on one line. Finish within the 120-second wall limit.\n"
    )


def _policy_prompt(common: str, policy: str, plan: separator.SeparatorPlan) -> str:
    if policy == "O":
        if plan.fallback or not plan.shared:
            return common + (
                "Policy O uses the common E-style fallback for this small or "
                "empty-boundary task: repair generally and do not claim an active "
                "paired-overlap probe.\n"
            )
        return common + (
            "Policy O — active paired-boundary probe. Before finalizing, execute "
            "at least two actual probe scripts. Each probe must run the same newly "
            "chosen input/state sequence on both candidate A and candidate B, in "
            "fresh helper processes, targeting S or an explicitly shared invariant. "
            "Use adaptive, specification-grounded probes; do not use canned inputs "
            "or a host-generated ledger. The command events and helper JSON are the "
            "only compliance evidence. Missing or malformed probes are recorded as "
            "noncompliance, not a reason to exclude this task.\n"
            f"Required shared target metadata: {list(plan.shared)!r}.\n"
        )
    return common + (
        "Policy G — strong generic critic/refine control. Independently inspect "
        "the specification, both complete candidates and bounded feedback, then "
        "repair the general behavior. You have the same native helper opportunity "
        "and time/tool permissions, but do not route by S or require paired probes. "
        "Use whatever generic verification is justified and report actual usage.\n"
    )


def _native_command(argv: Iterable[str], helper_host: Path) -> list[str]:
    """Replace the legacy dangerous profile with workspace-only native policy.

    The adapter still supplies the isolated bwrap filesystem; this transform
    only changes its Codex CLI flags and adds a read-only helper bind.
    """
    command = list(argv)
    if "--sandbox" not in command:
        raise ValueError("adapter command missing sandbox flag")
    sandbox_index = command.index("--sandbox")
    del command[sandbox_index:sandbox_index + 2]
    if "--unshare-net" not in command:
        command.insert(command.index("--proc") if "--proc" in command else 0,
                       "--unshare-net")
    # Keep shell enabled for the paired helper but make all other runtime
    # permissions explicit and noninteractive.
    for index in range(len(command) - 1, -1, -1):
        if command[index] == "--ask-for-approval":
            del command[index:index + 2]
    insert_at = command.index("--cd")
    command[insert_at:insert_at] = ["--ask-for-approval", "never",
        "--config", 'sandbox_mode="workspace-write"',
        "--config", 'approval_policy="never"',
        "--config", 'shell_environment_policy.inherit="none"',
        "--config", "features.network_proxy=false",
        "--config", "features.remote_plugin=false",
        "--config", "features.skill_mcp_dependency_install=false",
    ]
    try:
        helper_host = Path(helper_host).resolve()
        bind_index = command.index("--proc")
    except (ValueError, OSError) as exc:
        raise ValueError("adapter command cannot receive helper bind") from exc
    if (not helper_host.is_dir()
            or any(not (helper_host / name).is_file()
                   or (helper_host / name).is_symlink()
                   for name in (HELPER_NAME, "context.json", "a.py", "b.py"))):
        raise FileNotFoundError(f"paired helper directory is incomplete: {helper_host}")
    runtime_binds = ["--dir", "/opt/paired",
                     "--ro-bind", str(helper_host), "/opt/paired"]
    # The helper's own isolated child process needs the same native Python
    # installation and evaluator data roots.  Bind them at private /tmp paths;
    # no host home, credentials, or network are exposed to the model.
    for host, target in ((base.PYTHON_BASE, "/tmp/native-python"),
                         (base.VENV, "/tmp/native-venv"),
                         (base.NLTK_DATA, "/tmp/native-nltk")):
        host = Path(host).resolve()
        if not host.exists():
            raise FileNotFoundError(host)
        runtime_binds.extend(["--dir", target, "--ro-bind", str(host), target])
    command[bind_index:bind_index] = runtime_binds
    return command


def _event_dicts(value: Any) -> Iterable[dict]:
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _event_dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _event_dicts(item)


def _read_events(path: Path) -> list[dict]:
    events: list[dict] = []
    if not Path(path).is_file():
        return events
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            events.append(item)
    return events


def _command_events(events: Iterable[dict]) -> list[dict]:
    found: list[dict] = []
    by_id: dict[str, dict] = {}
    without_id: list[dict] = []
    for event in events:
        for item in _event_dicts(event):
            kind = str(item.get("type", "")).lower()
            if "command_execution" not in kind and kind != "command_execution":
                continue
            command = next((value for value in _text_fields(item)
                            if "/opt/paired/paired_probe.py" in value), "")
            exit_code = item.get("exit_code", item.get("exitCode"))
            has_output = any(key in item for key in ("aggregated_output", "output", "stdout", "result"))
            # Codex emits item.started and item.completed.  A started item has
            # neither exit status nor command output and is not an invocation
            # receipt; keeping it would double-count every helper call.
            if exit_code is None and not has_output:
                continue
            key_id = item.get("id")
            if isinstance(key_id, str) and key_id:
                current = by_id.get(key_id)
                # item.started and item.completed share an id; retain the
                # completed copy with exit/output evidence.
                if current is None or len(_text_fields(item)) > len(_text_fields(current)):
                    by_id[key_id] = item
            else:
                # Started events were removed above, so every no-id item left
                # here represents a completed invocation.  Preserve repeated
                # identical probes as two real calls.
                without_id.append(item)
    found.extend(by_id.values())
    found.extend(without_id)
    return found


def _text_fields(item: dict) -> list[str]:
    values: list[str] = []
    for key in ("command", "cmd", "aggregated_output", "output", "stdout", "result"):
        value = item.get(key)
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, (dict, list)):
            values.append(json.dumps(value, ensure_ascii=False))
    return values


def _exact_probe_command(command: str) -> bool:
    """Accept only the fixed parent helper invocation, never ``--child``."""
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    if "--child" in parts or "/opt/paired/paired_probe.py" not in parts:
        return False
    index = parts.index("/opt/paired/paired_probe.py")
    if index < 1 or parts[index - 1] != "/tmp/native-venv/bin/python":
        return False
    if index + 2 >= len(parts) or parts[index + 1] != "--probe":
        return False
    if not re.fullmatch(r"/tmp/work/probe_[A-Za-z0-9_.-]+\.py", parts[index + 2]):
        return False
    if "--context" in parts:
        context_index = parts.index("--context")
        if (context_index + 1 >= len(parts)
                or parts[context_index + 1] != "/opt/paired/context.json"):
            return False
    return True


def _json_objects(text: str) -> list[dict]:
    found: list[dict] = []
    candidates = [text.strip(), *[line.strip() for line in text.splitlines()]]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            item = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            found.append(item)
    return found


def _probe_evidence(events: list[dict], source_a: str, source_b: str) -> dict:
    """Trust only command events and their emitted helper JSON, never a ledger."""
    commands: list[dict] = []
    records: list[dict] = []
    expected_a, expected_b = _sha_text(source_a), _sha_text(source_b)
    for event in _command_events(events):
        fields = _text_fields(event)
        command = next((value for value in fields
                        if "/opt/paired/paired_probe.py" in value
                        and "--probe /tmp/work/" in value), None)
        if command is None or not _exact_probe_command(command):
            continue
        emitted = []
        emitted_keys: set[str] = set()
        for field in fields:
            for item in _json_objects(field):
                key = json.dumps(item, sort_keys=True, ensure_ascii=False)
                if key not in emitted_keys:
                    emitted_keys.add(key)
                    emitted.append(item)
        exit_code = event.get("exit_code", event.get("exitCode"))
        commands.append({"command": command, "exitCode": exit_code,
                         "eventId": event.get("id"),
                         "outputSha": _sha_text("\n".join(fields[1:]))})
        for item in emitted:
            # The helper's parent record proves both immutable source hashes;
            # its child records prove the per-candidate source hash and shared
            # probe hash.  A prose/model ledger is never inspected here.
            if not (item.get("schemaVersion") == 1
                    and item.get("probeSHA256")
                    and item.get("sourceSHA256A") == expected_a
                    and item.get("sourceSHA256B") == expected_b
                    and item.get("contextPath") == "/opt/paired/context.json"
                    and re.fullmatch(r"/tmp/work/probe_[A-Za-z0-9_.-]+\.py",
                                     str(item.get("probePath", "")))
                    and item.get("separateProcesses") is True
                    and isinstance(item.get("candidates"), dict)):
                continue
            candidates = item["candidates"]
            if not all(isinstance(candidates.get(label), dict) for label in ("A", "B")):
                continue
            child_ok = True
            for label, expected in (("A", expected_a), ("B", expected_b)):
                child = candidates[label]
                child_ok &= (child.get("candidate") == label
                             and child.get("sourceSha256") == expected
                             and child.get("probeSHA256") == item.get("probeSHA256")
                             and "output" in child and "exception" in child
                             and (child.get("exception") is None
                                  or isinstance(child.get("exception"), dict))
                             and isinstance(child.get("visitedMethods"), list)
                             and isinstance(child.get("durationSeconds"), (int, float)))
            if child_ok:
                records.append(item)
    successful = [item for item in commands if item.get("exitCode") == 0]
    distinct_probe_shas = {str(record.get("probeSHA256")) for record in records}
    compliant = (len(successful) >= 2 and len(records) >= 2
                 and len(distinct_probe_shas) >= 2)
    reason = None if compliant else "fewer than two verified distinct paired helper events"
    visited_a = {name for record in records
                 for name in record["candidates"]["A"].get("visitedMethods", [])}
    visited_b = {name for record in records
                 for name in record["candidates"]["B"].get("visitedMethods", [])}
    return {"helperCommandCount": len(commands),
            "verifiedProbeCount": len(records), "distinctProbeCount": len(distinct_probe_shas),
            "probeCompliant": compliant,
            "probeNoncomplianceReason": reason,
            "visitedSharedMethodsA": sorted(visited_a),
            "visitedSharedMethodsB": sorted(visited_b),
            "probeRecords": records[:8], "commands": commands[:8]}


def _source_safe(workspace: Path) -> tuple[bool, list[str]]:
    """Require a regular solution.py; scratch files are not submitted."""
    unexpected: list[str] = []
    for path in Path(workspace).rglob("*"):
        if path.is_symlink():
            unexpected.append(path.relative_to(workspace).as_posix())
    solution = Path(workspace) / "solution.py"
    if not solution.is_file() or solution.is_symlink():
        unexpected.append("solution.py (missing or non-regular)")
    # The model may use ordinary local scratch files while debugging.  Only
    # solution.py is copied to evaluation; all scratch paths remain in this
    # isolated, non-submitted workspace.
    return solution.is_file() and not solution.is_symlink(), sorted(unexpected)


def _stage_pair(helper_source: Path, destination: Path,
                full_ab: dict[str, dict], *, task_id: str,
                plan: separator.SeparatorPlan) -> Path:
    """Stage one read-only helper snapshot plus the canonical A/B modules."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    source = Path(helper_source).resolve()
    if source.is_symlink() or not source.is_file():
        raise ValueError("helper source must be a regular paired-probe file")
    shutil.copyfile(source, destination / HELPER_NAME)
    (destination / HELPER_NAME).chmod(0o444)
    a_source, b_source = full_ab["A"]["source"], full_ab["B"]["source"]
    (destination / "a.py").write_text(a_source, encoding="utf-8")
    (destination / "b.py").write_text(b_source, encoding="utf-8")
    for name in ("a.py", "b.py"):
        (destination / name).chmod(0o444)
    base.write_json(destination / "context.json", {
        "schemaVersion": 1, "taskId": task_id,
        "sharedMethods": list(plan.shared),
        "sourceA": "/opt/paired/a.py",
        "sourceB": "/opt/paired/b.py", "sourceSha256A": _sha_text(a_source),
        "sourceSha256B": _sha_text(b_source), "python": "/tmp/native-venv/bin/python",
        "pythonBase": "/tmp/native-python", "venv": "/tmp/native-venv",
        "nltkData": "/tmp/native-nltk", "timeoutSeconds": 8,
    })
    (destination / "context.json").chmod(0o444)
    return destination


def _resolve_helper_source(value: Path) -> Path:
    """Resolve the approved helper without reading credentials or launching it."""
    value = Path(value).expanduser()
    if value.is_file() and value.name == HELPER_NAME:
        return value.resolve()
    candidate = value / HELPER_NAME
    if candidate.is_file():
        return candidate.resolve()
    # The repository helper is the source snapshot; it is copied into each
    # run's /opt/paired mount and never imported by the host runner.
    fallback = ROOT / "tools" / "classeval_native_pair_probe.py"
    if value == HELPER_ROOT and fallback.is_file():
        return fallback.resolve()
    raise FileNotFoundError(f"approved paired helper is missing: {value}")


def _native_call(row: dict, out: Path, label: str, prompt: str,
                 *, helper_host: Path, codex_home: Path,
                 source_a: str = "", source_b: str = "",
                 run_process: Callable | None = None) -> dict:
    """One fresh native C session; evaluator is intentionally separate."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    work, artifact = out / "work", out / "artifact"
    work.mkdir()
    artifact.mkdir()
    (out / "prompt.txt").write_text(prompt, encoding="utf-8")
    base.write_json(out / "contract.json", {
        "taskId": row["task_id"], "label": label, "dataSha": base.PRO_SHA,
        "promptSha": _sha_text(prompt), "model": MODEL, "effort": EFFORT,
        "timeoutSeconds": TIMEOUT, "solverTools": True,
        "helperRoot": str(HELPER_ROOT), "helperName": HELPER_NAME,
        "permissionProfile": "workspace-write/network-off/approval-never",
    })
    base.write_json(out / "input.json", {
        "taskId": row["task_id"], "label": label, "promptSha": _sha_text(prompt),
        "sourceShaA": _sha_text(source_a), "sourceShaB": _sha_text(source_b),
        "helperRoot": str(HELPER_ROOT), "model": MODEL, "effort": EFFORT,
        "timeoutSeconds": TIMEOUT,
    })
    adapter = isolated.IsolatedCodexAdapter(Path(codex_home), MODEL, EFFORT, TIMEOUT)
    real_process = isolated.run_process if run_process is None else run_process

    def invoke(argv, **kwargs):
        return real_process(_native_command(argv, helper_host), **kwargs)

    previous = isolated.run_process
    try:
        isolated.run_process = invoke
        result = adapter.run(work, prompt, artifact, label)
    finally:
        isolated.run_process = previous
    receipt = dataclasses.asdict(result)
    stdout, stderr = receipt.pop("stdout", ""), receipt.pop("stderr", "")
    events = _read_events(artifact / "events.jsonl")
    turns = [item for event in events for item in _event_dicts(event)
             if item.get("type") == "turn.completed"]
    raw = ((artifact / "last_message.txt").read_text(encoding="utf-8")
           if (artifact / "last_message.txt").is_file() else "")
    try:
        code = text_runner.extract_code(raw)
        parse_error = None
    except (ValueError, SyntaxError) as exc:
        code, parse_error = "", type(exc).__name__
    safe, unexpected = _source_safe(work)
    # Only event output binding both immutable A/B hashes counts as probe
    # evidence.  ``context.json`` or a model-written side ledger is not used.
    probe = _probe_evidence(events, source_a, source_b)
    workspace_source = ((work / "solution.py").read_text(encoding="utf-8")
                        if (work / "solution.py").is_file() else "")
    try:
        file_code = text_runner.extract_code(workspace_source)
        file_parse_error = None
    except (ValueError, SyntaxError) as exc:
        file_code, file_parse_error = "", type(exc).__name__
    response_is_code = "```" in raw or bool(re.search(r"\bclass\s+[A-Za-z_]", code))
    response_mismatch = response_is_code and bool(file_code.strip()) and code != file_code
    code = file_code
    duration = float(result.duration_seconds)
    over_budget = duration > TIMEOUT
    valid = bool(result.exit_code == 0 and not result.timed_out and turns
                 and safe and file_parse_error is None and not over_budget
                 and not response_mismatch)
    source = base.evaluation_source(row, code)
    receipt.update({
        "valid": valid, "sourceSafe": safe, "unexpectedWorkspaceFiles": unexpected,
        "nonTextItems": [], "parseError": file_parse_error,
        "responseParseError": parse_error,
        "responseFileMismatch": response_mismatch, "overBudget": over_budget,
        "usage": turns[-1].get("usage") if turns else None,
        "turnCount": len(turns), "commandExecutionCount": len(_command_events(events)),
        "actualApiRequestCount": None, "actualApiRequestCountStatus": "unknown",
        "sourceSha": _sha_text(code), "permissionProfile": "workspace-write/network-off/approval-never",
        "helperRoot": str(HELPER_ROOT), "helperHostSha": base.sha(helper_host / HELPER_NAME)
            if (helper_host / HELPER_NAME).is_file() else None,
        "probeEvidence": probe,
    })
    base.write_json(out / "receipt.json", receipt)
    (out / "candidate.py").write_text(source, encoding="utf-8")
    return {"source": source, "rawSource": code, "valid": valid,
            "path": out, "receipt": receipt, "events": events,
            "stdoutSha": _sha_text(stdout), "stderrSha": _sha_text(stderr)}


def _score(report: dict) -> tuple[bool, int]:
    cases = report.get("cases")
    if not isinstance(cases, dict):
        cases = {}
    return bool(report.get("passed")), sum(
        item.get("status") == "passed" for item in cases.values() if isinstance(item, dict))


def _mc_nemar(count_a: int, count_b: int) -> float | None:
    n = count_a + count_b
    if n == 0:
        return 1.0
    denominator = 2 ** n
    tail = sum(math.comb(n, i) for i in range(min(count_a, count_b) + 1)) / denominator
    return min(1.0, 2 * tail)


def _paired_stats(left: dict[str, bool], right: dict[str, bool], ids: list[str]) -> dict:
    left_wins = [task_id for task_id in ids if left.get(task_id, False) and not right.get(task_id, False)]
    right_wins = [task_id for task_id in ids if right.get(task_id, False) and not left.get(task_id, False)]
    return {"leftWins": len(left_wins), "rightWins": len(right_wins),
            "netLeft": len(left_wins) - len(right_wins),
            "discordant": len(left_wins) + len(right_wins),
            "leftWinTaskIds": left_wins, "rightWinTaskIds": right_wins,
            "exactTwoSidedP": _mc_nemar(len(left_wins), len(right_wins))}


def _holm_two(p_values: dict[str, float | None]) -> dict[str, float | None]:
    usable = sorted(((key, value) for key, value in p_values.items() if value is not None),
                    key=lambda pair: (pair[1], pair[0]))
    adjusted: dict[str, float | None] = {key: None for key in p_values}
    running = 0.0
    for rank, (key, value) in enumerate(usable):
        running = max(running, min(1.0, value * (len(usable) - rank)))
        adjusted[key] = running
    return adjusted


def _base_state(prefix: dict, plan: separator.SeparatorPlan, status: str,
                policy_arm: str = "O") -> dict:
    state = {
        "status": status, "source": prefix["source"], "report": prefix["report"],
        "selected": "prefix", "logicalPrefixCalls": prefix["logicalPrefixCalls"],
        "tailModelCalls": 0, "freshSolverSessions": 0,
        "totalLogicalCalls": prefix["logicalPrefixCalls"],
        "rawEvalCalls": 0, "canonicalEvalCalls": 0, "suiteEvalCalls": 0,
        "sharedCanonicalABEvalCalls": 0, "freshRawCEvalCalls": 0,
        "freshCanonicalCEvalCalls": 0, "actualApiRequestCount": None,
        "callPaths": {}, "probeCompliant": None,
    }
    static_plan = plan.to_dict()
    static_plan.pop("arm", None)  # ``arm`` below identifies G or O policy.
    state.update(static_plan)
    state["arm"] = policy_arm
    state["separatorArm"] = "O"
    state["plannedOverlap"] = list(plan.shared)
    state["activeOverlap"] = False
    state["activeOverlapMethods"] = []
    state["sharedMethodBodyShas"] = {arm: {name: None for name in plan.shared}
                                      for arm in ("A", "B", "C")}
    return state


def _execute_task(row: dict, prefix: dict, cached: dict[str, dict],
                  output_root: Path, *, helper_host: Path, codex_home: Path,
                  evaluate_fn: Callable) -> dict[str, dict]:
    labels, ordered, feedback, _ = _e_context(row, prefix)
    plan = separator.build_separator_plan(prefix["source"], row["class_name"], ordered)
    if prefix["report"].get("passed"):
        return {arm: _base_state(prefix, plan, "stopped", arm) for arm in ARMS}
    full_ab = _full_ab(row, prefix, cached, evaluate_fn)
    shared_root = Path(output_root) / "shared-canonical"
    shared_root.mkdir(parents=True, exist_ok=False)
    shared_paths: dict[str, str] = {}
    for label in ("A", "B"):
        candidate_root = shared_root / label
        candidate_root.mkdir()
        (candidate_root / "candidate.py").write_text(
            full_ab[label]["source"], encoding="utf-8")
        base.write_json(candidate_root / "evaluation.json", full_ab[label]["report"])
        base.write_json(candidate_root / "receipt.json", {
            "cached": True, "valid": full_ab[label]["valid"],
            "canonical": True, "sourceSha": _sha_text(full_ab[label]["source"]),
            "sourcePath": str((candidate_root / "candidate.py").resolve()),
        })
        shared_paths[label] = str(candidate_root.resolve())
    result: dict[str, dict] = {}
    for arm in ARMS:
        arm_root = Path(output_root) / arm
        arm_root.mkdir(parents=True, exist_ok=False)
        staged_helper = _stage_pair(helper_host, arm_root / "paired", full_ab,
                                    task_id=row["task_id"], plan=plan)
        # ``ordered`` is the deterministic anchor-reordered cut used to build
        # S; keep the prompt's method order and feedback allowlist identical to
        # that cut for both policies.
        common = _common_prompt(row, prefix, plan, ordered, feedback, full_ab)
        prompt = _policy_prompt(common, arm, plan)
        call = _native_call(row, arm_root / "C", f"native-{arm}-C", prompt,
                            helper_host=staged_helper, codex_home=codex_home,
                            source_a=full_ab["A"]["source"],
                            source_b=full_ab["B"]["source"])
        c_source = c_report = None
        c_valid = bool(call.get("valid"))
        c_evals = 0
        raw_report = None
        if c_valid:
            # Raw candidate evaluation and canonical candidate evaluation are
            # deliberately separate and both are counted.
            raw_report = evaluate_fn(row, call["rawSource"])
            base.write_json(Path(call["path"]) / "raw-evaluation.json", raw_report)
            c_source, c_report, c_valid, c_evals, _, _ = frozen_tail._full_view(
                row, prefix, call, evaluate_fn)
            base.write_json(Path(call["path"]) / "evaluation.json", c_report)
        else:
            c_source, c_report = prefix["source"], _failure("invalid native C")
            base.write_json(Path(call["path"]) / "evaluation.json", c_report)
        candidates = [("prefix", prefix["source"], prefix["report"]),
                      ("A", full_ab["A"]["source"], full_ab["A"]["report"]),
                      ("B", full_ab["B"]["source"], full_ab["B"]["report"]),
                      ("C", c_source, c_report)]
        selected, source, report = frozen_tail._select(candidates)
        canonical_ab = sum(int(full_ab[arm].get("canonicalEvalCalls", 0)) for arm in ("A", "B"))
        canonical = canonical_ab + c_evals
        raw = int(raw_report is not None)
        suite = canonical + raw
        if suite > SUITE_EVAL_CAP:
            raise ValueError("per-arm raw plus canonical evaluation cap exceeded")
        state = {
            "status": "executed", "arm": arm, "separatorArm": "O",
            "source": source, "report": report,
            "selected": selected, "logicalPrefixCalls": prefix["logicalPrefixCalls"],
            "tailModelCalls": 1, "freshSolverSessions": 1,
            "totalLogicalCalls": prefix["logicalPrefixCalls"] + 1,
            "rawEvalCalls": raw, "canonicalEvalCalls": canonical,
            "suiteEvalCalls": suite, "sharedCanonicalABEvalCalls": canonical_ab,
            "sharedCanonicalABCountScope": "task-shared-across-G-and-O",
            "freshRawCEvalCalls": raw, "freshCanonicalCEvalCalls": c_evals,
            "rawCEvaluationPath": str(Path(call["path"]) / "raw-evaluation.json")
                if raw_report is not None else None,
            "reportedABCanonicalEvalCalls": canonical_ab,
            "actualApiRequestCount": call["receipt"].get("actualApiRequestCount"),
            "actualCommandCount": call["receipt"].get("commandExecutionCount", 0),
            "turnCount": call["receipt"].get("turnCount", 0),
            "durationSeconds": call["receipt"].get("duration_seconds"),
            "usage": call["receipt"].get("usage"),
            "callPaths": {"C": str(Path(call["path"]).resolve())},
            "sharedCanonicalPaths": shared_paths,
            "probeCompliant": call["receipt"].get("probeEvidence", {}).get("probeCompliant")
                if arm == "O" else None,
            "probeTargetedSharedMethods": None,
            "probeEvidence": call["receipt"].get("probeEvidence", {}),
            "scopeA": list(plan.a_scope), "scopeB": list(plan.b_scope),
            "sharedSeparatorMethods": list(plan.shared), "separatorCover": list(plan.cover),
            "crossEdges": [list(edge) for edge in plan.cross_edges],
            "matchingSize": plan.matching_size, "fallback": plan.fallback,
            "overlap": plan.overlap, "separatorValid": plan.valid,
            "separatorReason": plan.reason, "plannedOverlap": list(plan.shared),
            "activeOverlap": False, "activeOverlapMethods": [],
            "projectedMethodsA": [], "projectedMethodsB": [],
            "changedMethodsA": [], "changedMethodsB": [],
            "fullCanonicalCandidateSources": ["A", "B", "C"],
            "rawCandidateReportsUsedForSelection": False,
        }
        shas = {name: separator.method_body_shas(full_ab[name]["source"],
                                                 row["class_name"], plan.shared,
                                                 full_ab[name]["valid"])
                for name in ("A", "B")}
        shas["C"] = separator.method_body_shas(c_source, row["class_name"],
                                                plan.shared, c_valid)
        state["sharedMethodBodyShas"] = shas
        if arm == "O":
            evidence = call["receipt"].get("probeEvidence", {})
            visited_a = set(evidence.get("visitedSharedMethodsA", ()))
            visited_b = set(evidence.get("visitedSharedMethodsB", ()))
            active_methods = [name for name in plan.shared
                              if name in visited_a and name in visited_b]
            state["probeTargetedSharedMethods"] = bool(active_methods)
            state["activeOverlapMethods"] = active_methods
            state["activeOverlap"] = bool(
                plan.overlap and c_valid and evidence.get("probeCompliant")
                and active_methods
                and all(shas["C"].get(name) is not None for name in active_methods))
        result[arm] = state
    return result


def _build_contract(run_root: Path, parent_root: Path, e_root: Path,
                    rows: list[dict], prefixes: dict[str, dict],
                    helper_source: Path) -> dict:
    ids = _ordered_ids(rows)
    return {
        "dataset": "classeval-pro", "taskIds": ids, "dataSha": base.PRO_SHA,
        "runnerSha": base.sha(Path(__file__)), "protocolSha": base.sha(PROTOCOL),
        "evaluatorSha": base.sha(ROOT / "tools/classeval_isolated_evaluator.py"),
        "prefixLoaderSha": base.sha(Path(prefix_loader.__file__)),
        "separatorSha": base.sha(Path(separator.__file__)),
        "frozenTailSha": base.sha(Path(frozen_tail.__file__)),
        "baseRunnerSha": base.sha(Path(base.__file__)),
        "parentRoot": str(Path(parent_root).resolve()),
        "parentContractSha": base.sha(Path(parent_root) / "contract.json"),
        "parentResultSha": base.sha(Path(parent_root) / "result.json"),
        "oldECacheRoot": str(Path(e_root).resolve()),
        "oldECacheContractSha": base.sha(Path(e_root) / "contract.json"),
        "oldECacheResultSha": base.sha(Path(e_root) / "result.json"),
        "runRoot": str(Path(run_root).resolve()), "model": MODEL, "effort": EFFORT,
        "timeoutSeconds": TIMEOUT, "arms": list(ARMS), "ordinaryPassed": EXPECTED_PASSED,
        "fixedOrdinaryFailures": EXPECTED_FAILURES, "freshSolverSessions": FRESH_SOLVER_SESSIONS,
        "logicalTailCallsPerArm": 1, "logicalCallCap": 6, "suiteEvalCap": SUITE_EVAL_CAP,
        "projection": "none; full canonical A/B/C for both policies",
        "helper": {"hostRoot": str(HELPER_ROOT),
                   "hostSource": str(Path(helper_source).resolve()),
                   "containerRoot": str(HELPER_ROOT), "name": HELPER_NAME,
                   "command": HELPER_COMMAND, "readOnly": True,
                   "sourceSha": base.sha(Path(helper_source))},
        "permissionProfile": "workspace-write/network-off/approval-never",
        "freshApiRequestCount": "unknown; report event/turn/usage counters",
        "primaryGate": "O net >= 4 vs G and old LL_E=278; paired exact McNemar with Holm-2",
        "oldLLReference": "old E full-300 result; not tool-matched",
        "prefixMap": {task_id: {"sourceSha": prefixes[task_id]["sourceSha"],
                                 "logicalPrefixCalls": prefixes[task_id]["logicalPrefixCalls"]}
                      for task_id in ids},
    }


def _claim_run_root(run_root: Path, *immutable_roots: Path) -> Path:
    run = Path(run_root).resolve()
    for root in immutable_roots:
        root = Path(root).resolve()
        if run == root or run in root.parents or root in run.parents:
            raise ValueError("native run root overlaps immutable input")
    run.mkdir(parents=True, exist_ok=False)
    return run


def _sum_usage(states: Iterable[dict]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for state in states:
        usage = state.get("usage")
        if not isinstance(usage, dict):
            continue
        for key, value in usage.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                totals[key] = totals.get(key, 0) + int(value)
    return totals


def _write_result(run_root: Path, rows: list[dict], prefixes: dict[str, dict],
                  results: dict[str, dict], old_e_result: dict) -> dict:
    ids = _ordered_ids(rows)
    g = {task_id: bool(results[task_id]["G"]["report"].get("passed")) for task_id in ids}
    o = {task_id: bool(results[task_id]["O"]["report"].get("passed")) for task_id in ids}
    old = {task_id: bool((old_e_result.get("tasks", {}).get(task_id, {}).get("E", {})
                          .get("report") or prefixes[task_id]["report"]).get("passed"))
           for task_id in ids}
    og = _paired_stats(o, g, ids)
    oe = _paired_stats(o, old, ids)
    holm = _holm_two({"O_vs_G": og["exactTwoSidedP"], "O_vs_old_LL_E": oe["exactTwoSidedP"]})
    unresolved_states = [results[task_id] for task_id in ids
                         if not prefixes[task_id]["report"].get("passed")]
    g_states = [state["G"] for state in unresolved_states]
    o_states = [state["O"] for state in unresolved_states]
    shared_ab = sum(int(state.get("sharedCanonicalABEvalCalls", 0)) for state in g_states)
    raw_c = sum(int(state.get("freshRawCEvalCalls", 0)) for state in g_states + o_states)
    canonical_c = sum(int(state.get("freshCanonicalCEvalCalls", 0)) for state in g_states + o_states)
    solver_states = g_states + o_states
    result = {
        "status": "complete", "completed": len(results), "total": TOTAL_TASKS,
        "ordinaryPassed": EXPECTED_PASSED, "unresolved": EXPECTED_FAILURES,
        "freshSolverSessions": FRESH_SOLVER_SESSIONS,
        "actualApiRequestCount": None, "actualApiRequestCountStatus": "unknown",
        "arms": {"G": {"freshSolverSessions": EXPECTED_FAILURES},
                 "O": {"freshSolverSessions": EXPECTED_FAILURES}},
        "solverAccounting": {
            "freshSolverSessions": sum(int(state.get("freshSolverSessions", 0))
                                        for state in solver_states),
            "actualCommandCount": sum(int(state.get("actualCommandCount", 0))
                                       for state in solver_states),
            "turnCount": sum(int(state.get("turnCount", 0)) for state in solver_states),
            "durationSeconds": sum(float(state.get("durationSeconds") or 0)
                                    for state in solver_states),
            "usage": _sum_usage(solver_states),
            "apiRequests": "unknown",
            "durationMeaning": "sum of isolated solver process receipts; not end-to-end",
        },
        "evaluatorAccounting": {
            "sharedCanonicalABEvalCalls": shared_ab,
            "freshRawCEvalCalls": raw_c,
            "freshCanonicalCEvalCalls": canonical_c,
            "totalEvaluatorCalls": shared_ab + raw_c + canonical_c,
            "sharedABCountedOnceAcrossArms": True,
        },
        "pairedStats": {"O_vs_G": og, "O_vs_old_LL_E": oe,
                         "holm2AdjustedP": holm},
        "advancement": {"oNetVsG": og["netLeft"], "oNetVsOldLL_E": oe["netLeft"],
                         "oldLL_EPassed": sum(old.values()),
                         "required": "O net >=4 vs G AND old LL_E=278",
                         "eligible": bool(og["netLeft"] >= 4 and oe["netLeft"] >= 4
                                           and sum(old.values()) == 278)},
        "tasks": results,
    }
    base.write_json(run_root / "result.json", result)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-root", required=True, type=Path)
    parser.add_argument("--e-cache-root", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--helper-root", type=Path, default=HELPER_ROOT)
    parser.add_argument("--codex-home", type=Path,
                        default=Path("/home/pineapple/.codex-new-account"))
    parser.add_argument("--execute", action="store_true",
                        help="explicitly enable fresh native G/O C calls and evaluation")
    args = parser.parse_args(argv)
    rows = base.load_data("classeval-pro")
    if len(rows) != TOTAL_TASKS:
        raise ValueError("official full-300 inventory required")
    prefixes = prefix_loader.load_ordinary_prefix(args.parent_root.resolve())
    _validate_parent(args.parent_root, rows, prefixes)
    old_e = _load_old_e_ab(args.e_cache_root, args.parent_root.resolve(), rows, prefixes)
    if not args.execute:
        plans = {}
        for row in rows:
            if prefixes[row["task_id"]]["report"].get("passed"):
                continue
            _, ordered, _, _ = _e_context(row, prefixes[row["task_id"]])
            plans[row["task_id"]] = separator.build_separator_plan(
                prefixes[row["task_id"]]["source"], row["class_name"], ordered).to_dict()
        print(json.dumps({"mode": "dry-run", "dataset": "classeval-pro",
                          "total": TOTAL_TASKS, "ordinaryPassed": EXPECTED_PASSED,
                          "unresolved": EXPECTED_FAILURES, "oldECacheValidated": True,
                          "plannedFreshSolverSessions": FRESH_SOLVER_SESSIONS,
                          "plannedNewModelCalls": FRESH_SOLVER_SESSIONS,
                          "plans": plans, "executeRequired": True}, ensure_ascii=False))
        return 0
    helper_source = _resolve_helper_source(args.helper_root)
    run_root = _claim_run_root(args.run_root, args.parent_root, args.e_cache_root)
    contract = _build_contract(run_root, args.parent_root, args.e_cache_root,
                               rows, prefixes, helper_source)
    base.write_json(run_root / "contract.json", contract)
    results: dict[str, dict] = {}
    by_id = {row["task_id"]: row for row in rows}
    try:
        for row in rows:
            task_id = row["task_id"]
            if prefixes[task_id]["report"].get("passed"):
                results[task_id] = {arm: _base_state(prefixes[task_id],
                                                      separator.build_separator_plan(
                                                          prefixes[task_id]["source"], row["class_name"],
                                                          _e_context(row, prefixes[task_id])[1]),
                                                      "stopped", arm) for arm in ARMS}
            else:
                results[task_id] = _execute_task(
                    row, prefixes[task_id], old_e[task_id], run_root / task_id,
                    helper_host=helper_source, codex_home=args.codex_home,
                    evaluate_fn=base.evaluate)
            base.write_json(run_root / "progress.json", {
                "status": "running", "completed": len(results), "total": TOTAL_TASKS,
                "tasks": results})
            print(json.dumps({"taskId": task_id, "completed": len(results)}, ensure_ascii=False),
                  flush=True)
        _write_result(run_root, rows, prefixes,
                      results, _json(Path(args.e_cache_root).resolve() / "result.json"))
        return 0
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)[:2000],
                 "completed": len(results)}
        base.write_json(run_root / "error.json", error)
        base.write_json(run_root / "progress.json", {"status": "incomplete",
                                                        **error, "tasks": results})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
