#!/usr/bin/env python3
"""One entry point for the whole capability set.

The product claim is not "we have four benchmarks"; it is "one engine solves
tax-consequence prediction, judgment-outcome prediction and legal question
answering, and the same mechanism explains every number". This runner is that
claim made checkable: it takes a manifest of benchmarks, routes each to the
universal engine (or to a named baseline arm for comparison), scores each
deterministically, and emits one report with per-domain results, the shared
confidence operating points, and the cost.

  run_unified_suite.py --manifest suites/unified.json --out runs/unified-<date>
  run_unified_suite.py --report runs/unified-<date>

Manifest shape:
{
  "suites": [
    {"id": "tax", "bench": "...public.jsonl", "private": "...private.jsonl",
     "profile": "outcome_tax", "engine": true,
     "baseline": "runs/outcome-tax-v0-opus/answers.jsonl"},
    ...
  ],
  "model": "anthropic/claude-opus-5", "backend": "openrouter", "jobs": 5
}

Every suite entry is scored the same way, so a domain cannot quietly get a
softer grader than another.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE = REPO_ROOT / "tools" / "universal_engine.py"

CLASS_RE = re.compile(r"(인용됨|기각)")
CONF_RE = re.compile(r"확신도\s*[::]?\s*([01](?:\.\d+)?)")


def read_answers(path: Path) -> dict[str, tuple[str | None, float | None]]:
    out: dict[str, tuple[str | None, float | None]] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("answer"):
            answer = row["answer"]
            conf = row.get("confidence")
        else:
            text = (row.get("finalAnswer") or "").strip()
            match = CLASS_RE.search(text[:80])
            conf_match = CONF_RE.search(text)
            answer = match.group(1) if match else None
            conf = float(conf_match.group(1)) if conf_match else None
        out[row["id"]] = (answer, float(conf) if conf is not None else None)
    return out


def score(answers: dict, private: Path) -> dict:
    gold = {r["caseId"]: r["label"] for r in
            map(json.loads, private.read_text(encoding="utf-8").splitlines())}
    ids = [i for i in answers if i in gold]
    if not ids:
        return {"n": 0}
    correct = sum(1 for i in ids if answers[i][0] == gold[i])
    per_class: dict[str, list[int]] = {}
    for i in ids:
        bucket = per_class.setdefault(gold[i], [0, 0])
        bucket[1] += 1
        bucket[0] += answers[i][0] == gold[i]
    report = {
        "n": len(ids),
        "accuracy": round(correct / len(ids), 4),
        "balancedAccuracy": round(sum(v[0] / v[1] for v in per_class.values()) / len(per_class), 4),
        "byClass": {k: f"{v[0]}/{v[1]}" for k, v in per_class.items()},
        "operatingPoints": {},
    }
    for threshold in (0.7, 0.8, 0.9):
        picked = [i for i in ids if (answers[i][1] or 0) >= threshold]
        if picked:
            hits = sum(1 for i in picked if answers[i][0] == gold[i])
            report["operatingPoints"][str(threshold)] = {
                "coverage": round(len(picked) / len(ids), 3),
                "accuracy": round(hits / len(picked), 4),
                "n": len(picked),
            }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--report", type=Path, help="score an existing suite dir without running")
    args = parser.parse_args()

    if args.report:
        manifest = json.loads((args.report / "manifest.json").read_text(encoding="utf-8"))
        out_dir = args.report
        run_engine = False
    else:
        if not (args.manifest and args.out):
            raise SystemExit("--manifest and --out are required unless --report is used")
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        out_dir = args.out
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
        run_engine = True

    results = {}
    for suite in manifest["suites"]:
        suite_dir = out_dir / suite["id"]
        if run_engine and suite.get("engine", True):
            command = [
                sys.executable, str(ENGINE), "run",
                "--bench", str(REPO_ROOT / suite["bench"]),
                "--out", str(suite_dir),
                "--profile", suite.get("profile", "auto"),
                "--jobs", str(manifest.get("jobs", 5)),
                "--backend", manifest.get("backend", "openrouter"),
                "--model", manifest.get("model", "anthropic/claude-opus-5"),
            ]
            if suite.get("limit"):
                command += ["--limit", str(suite["limit"])]
            print("+", " ".join(command[-10:]), flush=True)
            subprocess.run(command, check=False)
        entry = {"engine": score(read_answers(suite_dir / "answers.jsonl"),
                                REPO_ROOT / suite["private"])}
        if suite.get("baseline"):
            entry["baseline"] = score(read_answers(REPO_ROOT / suite["baseline"]),
                                      REPO_ROOT / suite["private"])
        results[suite["id"]] = entry

    (out_dir / "report.json").write_text(json.dumps(results, ensure_ascii=False, indent=1))
    print(json.dumps(results, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
