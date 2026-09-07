#!/usr/bin/env python3
"""A matched fourth repair from exact test-case feedback and candidate overlap."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

from harness_research.trace_gated_mini.core import TaskSpec, execute_attempt, to_jsonable
from tools.run_aider_hidden20_arm import IsolatedCodexAdapter, stage_adjudication_evidence, compact_test_evidence
from tools.run_aider_counterexample_overlap import choose_sources, validate_attempt, usage, read_attempt
from tools.analyze_aider_online_offline_portfolio import run_evaluator


LABELS = ["plain", "graph", "ordinary_repair"]
GENERIC = """Use strong general execution-feedback repair. Freely inspect and compare all
candidate implementations, the full case-status matrix, failure messages and
derived overlap fields. Choose your own strategy to localize and fix remaining
defects. Consider alternative repairs, reconstruct the required behavior from
the specification and feedback, and preserve working behavior. Prioritize
changes likely to close complete tasks. Use actual source execution when useful,
and fix general causes rather than hard-coding the displayed test examples."""
OVERLAP = """Use cross-candidate overlap of failed requirements as the repair structure.
For each unresolved task, first align actual failing test cases across Plain
and the Graph/ordinary lineage. Group repeated failures into the underlying
requirement or assumption violated by different implementations. Agreement
between failing programs is evidence of a possible common mistake, not truth.
Resolve each shared failure class against the original specification and the
authoritative assertion feedback; repair its general cause across relevant
branches instead of patching only the first displayed example. Retain the
already supported requirements indicated by shared passes. Then use exclusive
partial successes as donors where they genuinely resolve a remaining obligation.
Missing execution reports are unknown and Graph plus its repair are not two
independent votes. Use a small actual-source check for consequential ambiguous
repairs. Finish by checking that every identified shared failure class has a
concrete code response or a stated unresolved reason; do not substitute a vote,
prose simulation or passing auxiliary example for full task correctness."""
COMMON = """Repair ALL tasks in this complete official Java track. The workspace starts
from the same ordinary-repair candidate for both policies. P/G/R patches and
bounded prior outcomes are in /tmp/artifacts/evidence-index.json; complete public
source snapshots are in /tmp/artifacts/candidates/{plain,graph,ordinary_repair}.
The identical /tmp/artifacts/case-feedback.json supplies the official test-case
status matrix, grouped assertion messages, unavailable-report flags and
cross-lineage shared failure/pass IDs. Both policies may use ALL of this data.
The cases were replayed against the original candidates and the complete task
outcome vectors matched. Test source and reference solutions remain hidden.

{policy}

The terminal selector preserves the same previously passing complete task
snapshots for both policies. Focus on unresolved tasks. Only listed solution
files are writable: do not add constructors or overloads to unlisted supporting
classes. Work with their existing APIs. Put temporary checks, build products and
source copies under /tmp, outside the repository. Keep supplied evidence intact.
No network, benchmark/answer lookup, hidden test source, or external answers.
Use only the declared exercise dependencies and available local tools.

Write /tmp/artifacts/decision_ledger.json with exactly one short row per task:
taskId, hypothesis, check, observation, action. Cite concrete failure/check IDs
when applicable, and distinguish executed checks from untested hypotheses.
Before finishing, inspect the actual final diff and then independently recheck
the original requirements against final code. Correct concrete contradictions
found by either audit. Do not write a long certificate. The budget is900seconds
for the entire47-task track, not per task.

Original task:
{instruction}
"""


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_prompt(instruction: str, policy: str, reserve: int = 0, start_epoch: int = 0) -> str:
    if policy not in {"generic", "overlap"} or reserve not in {0, 180}:
        raise ValueError("unsupported policy or completion reserve")
    prompt = COMMON.replace("{policy}", GENERIC if policy == "generic" else OVERLAP).replace("{instruction}", instruction)
    if reserve:
        prompt += (f"\nTime management for BOTH policies: approximate start UTC epoch {start_epoch}. "
                   f"Check the current UTC epoch with date +%s. Finish substantive editing by epoch {start_epoch + 720}; "
                   f"reserve the remaining time for final source checks and the complete ledger. Finish the response by "
                   f"epoch {start_epoch + 840}, before the unchanged900-second hard cap. "
                   "Do not start optional or long-running checks after the editing cutoff. "
                   "The original full47-task scope and source/evidence rules remain unchanged.\n")
    return prompt


def make_feedback(captures: dict, labels: list[str] | None = None) -> dict:
    labels = LABELS if labels is None else labels
    if not labels or len(set(labels)) != len(labels) or set(labels) != set(captures):
        raise ValueError("candidate inventory differs")
    ids = set(captures[labels[0]]["tasks"])
    if any(set(c["tasks"]) != ids for c in captures.values()):
        raise ValueError("feedback inventories differ")
    packed = {}
    for task_id in sorted(ids):
        rows = {label: captures[label]["tasks"][task_id] for label in labels}
        keys = sorted(set().union(*(set(r["cases"]) for r in rows.values())))
        matrix, failures = {}, {}
        for key in keys:
            matrix[key] = [rows[label]["cases"].get(key, {}).get("status", "not_reported") for label in labels]
            messages = {}
            for label in labels:
                case = rows[label]["cases"].get(key, {})
                if case.get("status") in {"failed", "error"}:
                    raw = case.get("message", "")
                    message = raw.split("Throwable that failed the check:")[0].split("\n\tat ")[0].strip()[:1600]
                    messages.setdefault(message, []).append(label)
            if messages:
                failures[key] = [{"candidates": names, "message": message} for message, names in messages.items()]
        bad = {"failed", "error"}
        packed[task_id] = {"candidateOrder": labels, "caseStatus": matrix, "failures": failures,
            "wholeTaskPassed": {label: row["passed"] for label, row in rows.items()},
            "noCaseReport": {label: row["outputHead"] for label, row in rows.items() if not row["cases"]},
            "crossLineageSharedFailures": [key for key, s in matrix.items() if s[0] in bad and any(v in bad for v in s[1:])],
            "crossLineageSharedPasses": [key for key, s in matrix.items() if s[0] == "passed" and "passed" in s[1:]]}
    return packed


def main(argv: list[str] | None = None, *, artifact_transform=None, prompt_transform=None,
         extra_parents: dict[str, Path] | None = None, seed_directory: Path | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--policy", required=True, choices=["generic", "overlap"])
    parser.add_argument("--candidate-id", help="Unique ID for a separately frozen fresh execution.")
    parser.add_argument("--completion-reserve-seconds", type=int, choices=[0, 180], default=0)
    args = parser.parse_args(argv)
    root = args.run_root.resolve()
    source, arms = root / "freeze/source", root / "arms"
    task = TaskSpec.from_json(root / "freeze/public/task.json")
    manifest = json.loads((source / "benchmark_manifest.json").read_text())
    ids = {item["taskId"] for item in manifest["tasks"]}
    if len(ids) != len(manifest["tasks"]):
        raise ValueError("duplicate task IDs")
    name = args.candidate_id or "shared_failure_v1_" + args.policy
    if not name or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_" for c in name):
        raise ValueError("invalid artifact ID")
    out = arms / name
    if out.exists():
        raise FileExistsError(out)
    staged = stage_adjudication_evidence(arms, name)
    attempts = staged["attempts"]
    artifact = out / "attempts" / name
    extra_parents = {} if extra_parents is None else extra_parents
    for label in extra_parents:
        if (not label or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_" for c in label)
                or label in attempts):
            raise ValueError("invalid or duplicate extra parent")
        attempt = read_attempt(arms, label)
        attempts[label] = attempt
        (artifact / f"{label}.patch").write_text(attempt.patch_text)
        (artifact / f"{label}.test-evidence.json").write_text(
            json.dumps(compact_test_evidence(attempt), indent=2, ensure_ascii=False) + "\n")
        staged["index"]["candidates"][label] = {
            "patch": f"/tmp/artifacts/{label}.patch",
            "testEvidence": f"/tmp/artifacts/{label}.test-evidence.json",
            "patchSha256": attempt.patch_sha256}
    if extra_parents:
        (artifact / "evidence-index.json").write_text(json.dumps(staged["index"], indent=2) + "\n")
    labels = list(attempts)
    maps = {label: validate_attempt(attempt, ids) for label, attempt in attempts.items()}
    diagnostic = root / "diagnostics/partial-repairs-v1"
    capture_paths = {label: diagnostic / (label + ".json") for label in LABELS}
    capture_paths.update(extra_parents)
    captures = {label: json.loads(path.read_text()) for label, path in capture_paths.items()}
    for label, capture in captures.items():
        if (not capture["taskVectorMatchesOriginal"] or capture["patchSha256"] != attempts[label].patch_sha256
                or {i: r["passed"] for i, r in capture["tasks"].items()} != maps[label]):
            raise ValueError("capture identity or official outcome drift")
    (artifact / "case-feedback.json").write_text(json.dumps(make_feedback(captures, labels), ensure_ascii=False) + "\n")
    for label, attempt in attempts.items():
        for item in manifest["tasks"]:
            java = Path(item["relativePath"]) / "src/main/java"
            for path in (Path(attempt.workspace) / java).rglob("*.java"):
                target = artifact / "candidates" / label / path.relative_to(attempt.workspace)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
    experiment = artifact_transform(artifact) if artifact_transform else None
    hashes = {str(p.relative_to(artifact)): digest(p) for p in sorted(artifact.rglob("*")) if p.is_file()}
    start_epoch = int(time.time())
    prompt = make_prompt(task.instruction, args.policy, args.completion_reserve_seconds, start_epoch)
    template = make_prompt(task.instruction, args.policy, args.completion_reserve_seconds, 0)
    if prompt_transform:
        prompt, template = prompt_transform(prompt), prompt_transform(template)
    seed = attempts["ordinary_repair"]
    seed_patch = seed.patch_text
    if seed_directory is not None:
        seed_patch = subprocess.run(["git", "diff", "--binary", "--no-ext-diff", "HEAD", "--"],
            cwd=seed_directory, text=True, capture_output=True, check=True).stdout
    contract = {"policy": args.policy, "taskIds": sorted(ids), "model": "gpt-5.6-luna", "effort": "medium",
        "agentTimeoutSeconds": 900, "seedPatchSha256": hashlib.sha256(seed_patch.encode()).hexdigest(), "evidenceHashes": hashes,
        "completionReserveSeconds": args.completion_reserve_seconds, "approximateStartEpoch": start_epoch,
        "promptTemplateSha256": hashlib.sha256(template.encode()).hexdigest(),
        "promptSha256": hashlib.sha256(prompt.encode()).hexdigest(), "runnerSha256": digest(Path(__file__)),
        "captureHashes": {label: digest(path) for label, path in capture_paths.items()},
        "interpretation": ("exposed-task shared-failure development; four logical executions per system"
            if not extra_parents else f"exposed-task repair development; {len(attempts) + 1} logical executions per system")}
    if extra_parents or seed_directory is not None:
        contract["parentIds"] = labels
        contract["logicalExecutionsPerSystem"] = len(attempts) + 1
    if experiment is not None:
        contract["experiment"] = experiment
    (out / "contract.json").write_text(json.dumps(contract, indent=2) + "\n")
    result = execute_attempt(source_repo=source, task=task, output_dir=out, candidate_id=name,
        policy=name, seed_patch=seed_patch, prompt_override=prompt, public_test_timeout_seconds=1800,
        adapter=IsolatedCodexAdapter(codex_home=Path("/home/pineapple/.codex-new-account"),
            model="gpt-5.6-luna", reasoning_effort="medium", timeout_seconds=900,
            java_root=Path("/home/pineapple/miniconda3/lib/jvm")))
    (out / "result.json").write_text(json.dumps({"attempt": to_jsonable(result)}, indent=2) + "\n")
    maps[name] = validate_attempt(result, ids)
    if any(not (artifact / rel).is_file() or digest(artifact / rel) != sha for rel, sha in hashes.items()):
        raise ValueError("input evidence changed")
    ledger = json.loads((artifact / "decision_ledger.json").read_text())
    required = {"taskId", "hypothesis", "check", "observation", "action"}
    if (not isinstance(ledger, list) or len(ledger) != len(ids)
            or any(not isinstance(r, dict) or not required.issubset(r) for r in ledger)
            or {r["taskId"] for r in ledger} != ids):
        raise ValueError("incomplete ledger")
    attempts[name] = result
    order = [name, *reversed(labels)]
    selected = choose_sources([(label, maps[label]) for label in order], ids)
    vector = {i: any(maps[label][i] for label in order) for i in ids}
    destination = out / "terminal-union"
    shutil.copytree(source, destination)
    for item in manifest["tasks"]:
        for file in item["solutionFiles"]:
            relative = Path(item["relativePath"]) / file
            (destination / relative).write_bytes((Path(attempts[selected[item["taskId"]]].workspace) / relative).read_bytes())
    evaluated = run_evaluator(task.public_test_command, destination)
    if evaluated["taskOutcomes"] != vector:
        raise ValueError("materialized outcomes differ")
    report = {"policy": args.policy, "taskCount": len(ids), "candidatePassed": sum(maps[name].values()),
        "systemPassed": sum(vector.values()), "candidateTaskOutcomes": maps[name], "systemTaskOutcomes": vector,
        "selectedSources": selected, "materializedEvaluation": evaluated,
        "compute": {label: usage(attempt) for label, attempt in attempts.items()}}
    (out / "system-result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ["policy", "taskCount", "candidatePassed", "systemPassed"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
