#!/usr/bin/env python3
"""Pick a selective-prediction policy honestly, and report held-out numbers.

Why this exists: scanning dozens of (arm, threshold, agreement) combinations on
one 111-row set and reporting the winner is selection bias — "100% accuracy at
15% coverage" is what you get by chance when you try 60 policies. This tool
does the scan INSIDE a cross-validation loop: the policy is chosen on the
training half only, then measured on the held-out half, and the reported number
is the average of held-out folds. The chosen policy is also printed per fold so
instability is visible rather than hidden.

Policy space (all deterministic):
  * single arm with a confidence floor
  * unanimity across a subset of arms, optionally with a confidence floor

Objective: maximize coverage subject to accuracy >= target (default 0.90) on
the training half. If no policy clears the target on training, the fold reports
the best-accuracy policy instead and flags it.

usage:
  select_operating_point.py --private P.jsonl --arm NAME=path.jsonl [...] \
      [--target 0.9] [--folds 2] [--min-coverage-n 8]
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
from pathlib import Path

CLASS_RE = re.compile(r"(인용됨|기각)")
CONF_RE = re.compile(r"확신도\s*[::]?\s*([01](?:\.\d+)?)")


def read_arm(path: Path) -> dict[str, tuple[str | None, float | None]]:
    out: dict[str, tuple[str | None, float | None]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("answer"):
            out[row["id"]] = (row["answer"], row.get("confidence"))
            continue
        text = (row.get("finalAnswer") or "").strip()
        cls = CLASS_RE.search(text[:120])
        conf = CONF_RE.search(text)
        out[row["id"]] = (cls.group(1) if cls else None,
                          float(conf.group(1)) if conf else None)
    return out


def policies(arm_names: list[str], thresholds: tuple[float, ...]):
    for name in arm_names:
        for threshold in thresholds:
            yield ("single", (name,), threshold)
    for size in (2, 3):
        for combo in itertools.combinations(arm_names, size):
            for threshold in (0.0,) + thresholds:
                yield ("unanimous", combo, threshold)


def apply_policy(policy, arms, ids):
    kind, names, threshold = policy
    selected = []
    for case_id in ids:
        votes = [arms[n][case_id] for n in names]
        if any(v[0] is None for v in votes):
            continue
        if kind == "unanimous" and len({v[0] for v in votes}) != 1:
            continue
        if threshold and any((v[1] or 0) < threshold for v in votes):
            continue
        selected.append((case_id, votes[0][0]))
    return selected


def evaluate(selected, gold):
    if not selected:
        return 0.0, 0
    hits = sum(1 for case_id, answer in selected if answer == gold[case_id])
    return hits / len(selected), len(selected)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--arm", action="append", required=True,
                        help="NAME=path/to/answers.jsonl")
    parser.add_argument("--target", type=float, default=0.90)
    parser.add_argument("--folds", type=int, default=2)
    parser.add_argument("--min-coverage-n", type=int, default=8)
    parser.add_argument("--salt", default="opsel")
    args = parser.parse_args()

    gold = {r["caseId"]: r["label"] for r in
            map(json.loads, args.private.read_text(encoding="utf-8").splitlines())}
    arms = {}
    for spec in args.arm:
        name, path = spec.split("=", 1)
        arms[name] = read_arm(Path(path))
    ids = [i for i in gold if all(i in a and a[i][0] for a in arms.values())]
    folds: dict[int, list[str]] = {k: [] for k in range(args.folds)}
    for case_id in ids:
        digest = hashlib.sha256(f"{args.salt}|{case_id}".encode()).hexdigest()
        folds[int(digest, 16) % args.folds].append(case_id)

    thresholds = (0.7, 0.75, 0.8, 0.85, 0.9, 0.95)
    all_policies = list(policies(sorted(arms), thresholds))
    held_hits = held_total = 0
    covered = 0
    report = []
    for k in range(args.folds):
        test = folds[k]
        train = [i for j in range(args.folds) if j != k for i in folds[j]]
        best = None
        for policy in all_policies:
            selected = apply_policy(policy, arms, train)
            accuracy, n = evaluate(selected, gold)
            if n < args.min_coverage_n:
                continue
            clears = accuracy >= args.target
            key = (clears, n if clears else 0, accuracy)
            if best is None or key > best[0]:
                best = (key, policy, accuracy, n)
        if best is None:
            report.append({"fold": k, "policy": None})
            continue
        _, policy, train_acc, train_n = best
        selected = apply_policy(policy, arms, test)
        accuracy, n = evaluate(selected, gold)
        held_hits += round(accuracy * n)
        held_total += n
        covered += len(test)
        report.append({
            "fold": k,
            "policy": f"{policy[0]}({'+'.join(policy[1])}) conf>={policy[2]}",
            "trainAccuracy": round(train_acc, 3),
            "trainCoverage": round(train_n / len(train), 3),
            "heldOutAccuracy": round(accuracy, 3),
            "heldOutCoverage": round(n / len(test), 3),
            "heldOutN": n,
            "clearedTargetOnTrain": train_acc >= args.target,
        })
    summary = {
        "n": len(ids),
        "target": args.target,
        "folds": report,
        "heldOutOverall": {
            "accuracy": round(held_hits / held_total, 4) if held_total else None,
            "coverage": round(held_total / covered, 3) if covered else None,
            "n": held_total,
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
