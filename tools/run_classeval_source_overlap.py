"""Full ClassEval100 isolated parent generation and executable source composition."""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time

from tools.classeval_source_overlap import proposals
from tools.run_aider_hidden20_arm import IsolatedCodexAdapter
from tools.run_plain_codex_file_agent import MASKED_HOST_ROOTS


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "benchmarks/classeval-v1.0.0/ClassEval_data.json"
DATA_SHA = "d13f5e3bac96f57c1cc9bfa282cf6c0cca4605d4748d621b83a0dae72d08ed2f"
PYTHON_BASE = Path("/home/pineapple/miniconda3")
VENV = ROOT / ".runtime/classeval-v1-env"
NLTK_DATA = ROOT / ".runtime/classeval-nltk-data"
PROTOCOL = ROOT / "experiment_protocols/2026-09-05-classeval-source-overlap-v1.md"
PRO_DATA = ROOT / "benchmarks/classeval-pro/data.json"
PRO_SHA = "f6bcb748819f6f2e39f3d6635c76a8310f5cbee55f08154f9dd726522decb2e3"
PRO_PROTOCOL = ROOT / "experiment_protocols/2026-09-05-classeval-pro-source-overlap-v2.md"
PROMPT = """Implement the single Python class specified below in /tmp/work/solution.py.
Return a complete coherent implementation, preserving the documented class,
method signatures, provided constructor behavior and imports. Interpret the
requirements generally, not as hard-coded examples. Use only the declared
dependencies. Tests and reference answers are unavailable. Do not search for
this benchmark or answers; no web/network or external files. Only solution.py
may be changed in the workspace; temporary checks belong elsewhere under /tmp.
Check the final source for missing methods, state consistency and edge cases.
There is no decision ledger. Finish the code and your response within100seconds
of starting; the hard cap is120seconds. The final chat can be brief.

Specification:
{skeleton}
"""


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def source_scope(work: Path) -> tuple[bool, list[str]]:
    paths = list(work.rglob("*"))
    if any(p.is_symlink() for p in paths):
        return False, []
    files = {p.relative_to(work).as_posix() for p in paths if p.is_file()}
    caches = sorted(p for p in files if re.fullmatch(r"__pycache__/solution\.cpython-\d+\.pyc", p))
    # Only solution.py is copied to evaluation. Explicit py_compile ignores
    # PYTHONDONTWRITEBYTECODE; its non-submitted cache is not a source edit.
    return files - set(caches) == {"solution.py"}, caches


def load_data(dataset: str = "classeval") -> list[dict]:
    path, digest, count = (PRO_DATA, PRO_SHA, 300) if dataset == "classeval-pro" else (DATA, DATA_SHA, 100)
    if sha(path) != digest:
        raise ValueError("official data hash mismatch")
    rows = json.loads(path.read_text())
    if len(rows) != count or len({r["task_id"] for r in rows}) != count:
        raise ValueError(f"full{count}-task inventory required")
    for row in rows:
        if not row["task_id"].startswith("ClassEval_") or not row["task_id"][10:].isdigit():
            raise ValueError("unsafe task ID")
        row["_dataset"] = dataset
        row["_data_sha"] = digest
    return rows


def evaluation_source(row: dict, source: str) -> str:
    if row.get("_dataset") != "classeval-pro":
        return source
    # Exact author evaluator add_static_statement convention, applied equally
    # to references, parents, generic mixtures and overlap mixtures.
    lines = [line for line in source.split("\n") if "@staticmethod" not in line]
    result = []
    for line in lines:
        if (line.strip().startswith("def ") and "self" not in line and "cls" not in line
                and len(line) - len(line.lstrip()) == 4):
            result.append("    @staticmethod")
        result.append(line)
    return "\n".join(result)


def evaluate(row: dict, source: str) -> dict:
    payload = {"source": evaluation_source(row, source), "test": row["test"],
               "test_classes": row["test_classes"], "module_name": row["task_id"] + "_0",
               "reload_each_class": row.get("_dataset") == "classeval-pro"}
    with tempfile.TemporaryDirectory(prefix="mini-classeval-eval-") as temp:
        command = ["bwrap", "--die-with-parent", "--new-session", "--unshare-all",
                   "--ro-bind", "/", "/"]
        for root in MASKED_HOST_ROOTS:
            command.extend(["--tmpfs", root])
        for path in (PYTHON_BASE, VENV):
            command.extend(["--ro-bind", str(path), str(path)])
        command.extend(["--ro-bind", str(ROOT / "tools/classeval_isolated_evaluator.py"), "/tmp/evaluate.py",
                        "--ro-bind", str(NLTK_DATA), "/tmp/nltk-data", "--bind", temp, "/tmp/work",
                        "--proc", "/proc", "--dev", "/dev", "--clearenv",
                        "--setenv", "PATH", "/usr/bin:/bin", "--setenv", "HOME", "/tmp/work",
                        "--setenv", "NLTK_DATA", "/tmp/nltk-data", "--setenv", "OPENBLAS_NUM_THREADS", "1",
                        "--setenv", "OMP_NUM_THREADS", "1", "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
                        "--setenv", "LANG", "C.UTF-8", "--chdir", "/tmp/work",
                        str(VENV / "bin/python"), "/tmp/evaluate.py"])
        started = time.monotonic()
        try:
            done = subprocess.run(command, input=json.dumps(payload), text=True, capture_output=True,
                                  timeout=15 + 5 * len(row["test_classes"]), check=False)
            if done.returncode:
                return {"passed": False, "cases": {}, "fatal": done.stderr[-2000:], "exitCode": done.returncode,
                        "wallSeconds": time.monotonic() - started}
            result = json.loads(done.stdout)
            result["wallSeconds"] = time.monotonic() - started
            return result
        except (subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            return {"passed": False, "cases": {}, "fatal": type(exc).__name__,
                    "wallSeconds": time.monotonic() - started}


def parent(row: dict, directory: Path, name: str) -> dict:
    directory.mkdir(parents=True, exist_ok=False)
    work, artifact = directory / "work", directory / "artifact"
    work.mkdir()
    artifact.mkdir()
    original = row["skeleton"]
    (work / "solution.py").write_text(original)
    prompt = PROMPT.format(skeleton=original)
    (directory / "prompt.txt").write_text(prompt)
    adapter = IsolatedCodexAdapter(Path("/home/pineapple/.codex-new-account"), "gpt-5.6-luna", "medium", 120)
    write_json(directory / "contract.json", {"taskId": row["task_id"], "parent": name,
        "dataSha": row.get("_data_sha", DATA_SHA), "promptSha": hashlib.sha256(prompt.encode()).hexdigest(),
        "model": adapter.model, "effort": adapter.reasoning_effort, "timeoutSeconds": 120,
        "startedEpoch": time.time(), "allowedFiles": ["solution.py"]})
    result = adapter.run(work, prompt, artifact, name)
    record = dataclasses.asdict(result)
    record.pop("stdout")
    record.pop("stderr")
    events = []
    for line in result.stdout.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    completed = [e for e in events if e.get("type") == "turn.completed"]
    safe, ignored_caches = source_scope(work)
    valid = result.exit_code == 0 and not result.timed_out and bool(completed) and safe
    source = (work / "solution.py").read_text() if (work / "solution.py").is_file() else ""
    record.update({"valid": valid, "sourceSafe": safe, "nonSubmittedCaches": ignored_caches,
                   "usage": completed[-1].get("usage") if completed else None,
                   "sourceSha": hashlib.sha256(source.encode()).hexdigest()})
    write_json(directory / "receipt.json", record)
    # Prefixing imports is the author's evaluation convention, not a repair.
    executable = evaluation_source(row, "\n".join(row.get("import_statement", [])) + "\n" + source)
    (directory / "candidate.py").write_text(executable)
    report = evaluate(row, executable) if valid else {"passed": False, "cases": {}, "fatal": "invalid model execution"}
    write_json(directory / "evaluation.json", report)
    return {"source": executable, "report": report, "valid": valid}


def search(row: dict, parents: list[dict], policy: str, directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=False)
    def score(item):
        return (item["report"]["passed"], sum(c["status"] == "passed" for c in item["report"]["cases"].values()))
    best = max(parents, key=score)
    records, reason = [], None
    if not best["report"]["passed"] and all(p["valid"] for p in parents):
        try:
            candidates = proposals([p["source"] for p in parents], row["class_name"],
                                   [p["report"] for p in parents], policy, row["task_id"])
        except (SyntaxError, ValueError) as exc:
            candidates, reason = [], str(exc)
        for index, item in enumerate(candidates):
            code_path = directory / f"candidate-{index:02d}.py"
            code_path.write_text(item["source"])
            report = evaluate(row, item["source"])
            write_json(directory / f"evaluation-{index:02d}.json", report)
            records.append({k: v for k, v in item.items() if k != "source"} | {"passed": report["passed"]})
            candidate = {"source": item["source"], "report": report, "valid": True}
            if score(candidate) > score(best):
                best = candidate
            if best["report"]["passed"]:
                break
    (directory / "selected.py").write_text(best["source"])
    write_json(directory / "selected-evaluation.json", best["report"])
    summary = {"passed": best["report"]["passed"], "trials": records, "nonComposableReason": reason}
    write_json(directory / "result.json", summary)
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--reference-check", action="store_true")
    parser.add_argument("--dataset", choices=["classeval", "classeval-pro"], default="classeval")
    args = parser.parse_args(argv)
    rows, out = load_data(args.dataset), args.run_root.resolve()
    count = len(rows)
    protocol = PRO_PROTOCOL if args.dataset == "classeval-pro" else PROTOCOL
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "contract.json", {"dataSha": rows[0]["_data_sha"], "taskIds": [r["task_id"] for r in rows],
        "dataset": args.dataset, "protocolSha": sha(protocol), "runnerSha": sha(Path(__file__)),
        "operatorSha": sha(ROOT / "tools/classeval_source_overlap.py"),
        "evaluatorSha": sha(ROOT / "tools/classeval_isolated_evaluator.py"),
        "referenceCheck": args.reference_check, "startedEpoch": time.time()})
    results = {}
    for row in rows:
        task_id = row["task_id"]
        if args.reference_check:
            source = "\n".join(row.get("import_statement", [])) + "\n" + row["solution_code"]
            result = evaluate(row, source)
            write_json(out / task_id / "evaluation.json", result)
            results[task_id] = {"passed": result["passed"], "fatal": result.get("fatal"),
                                "caseCount": len(result["cases"])}
        else:
            parents = [parent(row, out / task_id / "a", "a")]
            if args.dataset != "classeval-pro" or not parents[0]["report"]["passed"]:
                parents.append(parent(row, out / task_id / "b", "b"))
            result = {"plain": parents[0]["report"]["passed"],
                      "bestOfTwo": any(p["report"]["passed"] for p in parents),
                      "modelCalls": len(parents), "bSkippedVerified": len(parents) == 1}
            for policy in ("generic", "overlap"):
                result[policy] = search(row, parents, policy, out / task_id / policy)["passed"]
            results[task_id] = result
        write_json(out / "progress.json", {"completed": len(results), "total": count, "tasks": results})
        print(json.dumps({"taskId": task_id, "completed": len(results), **results[task_id]}), flush=True)
    write_json(out / "result.json", {"completed": count, "total": count, "tasks": results})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
