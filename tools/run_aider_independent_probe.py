#!/usr/bin/env python3
"""Independent specification probes; reuse the existing isolated Codex adapter."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from harness_research.trace_gated_mini.core import TaskSpec, prepare_workspace, collect_patch, to_jsonable
from tools.run_aider_hidden20_arm import IsolatedCodexAdapter


PROBE_AUTHOR = """Create independent executable specification probes for ALL tasks in
the complete official track. This call does NOT solve or edit implementations.
You see only original documentation and source/API stubs, never candidate
repairs or official test outcomes. Keep that independence: no benchmark lookup,
hidden tests, gold, internet access, or external answer sources.

Write /tmp/artifacts/probes.json as a JSON array with exactly one row per task:
taskId, status (executable or unavailable), basis, java, reason.
For executable rows java is a complete Java class named Probe with public static
void main(String[] args), compiled alongside that task's ACTUAL solution source.
Use plain Java assertions (executed with -ea) or throw AssertionError on mismatch.
Use the supplied API, not a reimplementation of the solution under test. Prefer
one clear documentation example and one small boundary, transition, or
metamorphic check whose expected behavior follows the specification. Give the
short supporting quotation/derivation in basis. Expected results must not be
invented from familiar benchmark conventions, error-message guesses, or a
candidate's behavior. For external-dependency or ambiguous APIs that cannot
be probed with standard Java, mark unavailable and explain briefly; do not
remove the row. Such cases still count in the final official benchmark.

Keep probes small and inexpensive. Do not create standalone solvers, duplicate
implementation bodies, excessive fuzzing, network/filesystem access, or hidden
test reconstructions. You may use scratch calculators and inspect supplied
source declarations to ensure correct APIs and expected arithmetic. Never
mutate /tmp/work; all scratch files belong under /tmp, all final output in the
one probes.json. The source stubs are not candidate solutions, so they need not
pass the probes. Before finishing validate unique complete task IDs, JSON
syntax, Probe/main structure, basis, and unavailable reasons. Return promptly
after writing the complete packet. Budget: 900 seconds for the whole track.

Original public task (implementation-edit instructions below describe the
later solver; this probe-author call MUST leave source files unchanged):
"""


def validate_probes(rows: object, ids: set[str]) -> None:
    if not isinstance(rows, list) or len(rows) != len(ids):
        raise ValueError("incomplete probe inventory")
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("non-object probe row")
    if {row.get("taskId") for row in rows} != ids:
        raise ValueError("probe IDs differ")
    for row in rows:
        if row.get("status") not in {"executable", "unavailable"}:
            raise ValueError("invalid probe status")
        if not {"taskId", "status", "basis", "java", "reason"}.issubset(row):
            raise ValueError("missing probe fields")
        if any(not isinstance(row[key], str) for key in row):
            raise ValueError("probe fields must be strings")
        if row["status"] == "executable" and not (row["java"].strip() and row["basis"].strip()):
            raise ValueError("executable probe lacks code or basis")
        if row["status"] == "unavailable" and not row["reason"].strip():
            raise ValueError("unavailable probe lacks reason")


def canonicalize_ids(rows: list[dict], ids: set[str]) -> list[dict]:
    aliases = {value.rsplit("/", 1)[-1]: value for value in ids}
    if len(aliases) != len(ids) or any(row.get("taskId") not in aliases for row in rows):
        raise ValueError("ambiguous or missing alias")
    canonical = [{**row, "taskId": aliases[row["taskId"]]} for row in rows]
    validate_probes(canonical, ids)
    return canonical


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--canonicalize-existing", action="store_true",
                        help="Apply the separately frozen pre-scoring ID-only amendment; no model call.")
    args = parser.parse_args()
    root = args.run_root.resolve()
    source = root / "freeze/source"
    task = TaskSpec.from_json(root / "freeze/public/task.json")
    manifest = json.loads((source / "benchmark_manifest.json").read_text())
    ids = {row["taskId"] for row in manifest["tasks"]}
    if len(ids) != len(manifest["tasks"]):
        raise ValueError("duplicate original task IDs")
    out = root / "arms/probe_v1_author"
    if args.canonicalize_existing:
        if (out / "receipt.json").exists():
            raise FileExistsError(out / "receipt.json")
        result = json.loads((out / "result.json").read_text())
        if result["agent"]["exit_code"] != 0 or result["agent"]["timed_out"] or result["changedFiles"]:
            raise ValueError("original probe author did not finish safely")
        raw = out / "artifacts/probes.json"
        rows = json.loads(raw.read_text())
        canonical = canonicalize_ids(rows, ids)
        target = out / "artifacts/probes.canonical.json"
        with target.open("x") as stream:
            stream.write(json.dumps(canonical, ensure_ascii=False, indent=2) + "\n")
        receipt = {"valid": True, "taskCount": len(ids),
            "executable": sum(r["status"] == "executable" for r in canonical),
            "probeFile": target.name, "probeSha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "rawProbeSha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
            "idMapping": {a["taskId"]: b["taskId"] for a, b in zip(rows, canonical)},
            "amendment": "experiment_protocols/2026-09-05-java47-probe-prescore-id-amendment.md"}
        (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps(receipt), flush=True)
        return 0
    out.mkdir(exist_ok=False)
    workspace = out / "workspace"
    artifact = out / "artifacts"
    artifact.mkdir()
    prompt = PROBE_AUTHOR + task.instruction
    (artifact / "prompt.txt").write_text(prompt)
    contract = {"taskIds": sorted(ids), "model": "gpt-5.6-luna", "effort": "medium",
                "agentTimeoutSeconds": 900, "candidateEvidence": "withheld",
                "runnerSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "promptSha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "javaRoot": "/home/pineapple/miniconda3/lib/jvm"}
    (out / "contract.json").write_text(json.dumps(contract, indent=2) + "\n")
    prepare_workspace(source, task.base_ref, workspace)
    adapter = IsolatedCodexAdapter(
        codex_home=Path("/home/pineapple/.codex-new-account"), model="gpt-5.6-luna",
        reasoning_effort="medium", timeout_seconds=900,
        java_root=Path("/home/pineapple/miniconda3/lib/jvm"))
    result = adapter.run(workspace, prompt, artifact, "probe_v1_author")
    changed, _, patch_sha, _ = collect_patch(workspace)
    (out / "result.json").write_text(json.dumps({"agent": to_jsonable(result),
        "changedFiles": changed, "patchSha256": patch_sha}, indent=2) + "\n")
    if result.exit_code != 0 or result.timed_out or changed:
        raise ValueError("probe author incomplete or mutated original source")
    path = artifact / "probes.json"
    rows = json.loads(path.read_text())
    validate_probes(rows, ids)
    receipt = {"taskCount": len(ids), "executable": sum(r["status"] == "executable" for r in rows),
               "probeSha256": hashlib.sha256(path.read_bytes()).hexdigest(), "valid": True}
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
