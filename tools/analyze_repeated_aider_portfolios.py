"""Exhaustive, post-hoc two-route portfolios from the five frozen final draws.

No new calls or scores: combine saved complete official task-outcome vectors.
Pair combinations reuse calls and MUST NOT be counted as independent sessions.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRACKS = {
    "python34": ("aider-python34-tov-v2-confirmation-20260902", 34,
                 [24, 21, 23, 23, 22], [20, 23, 21, 23, 20]),
    "cpp26": ("aider-cpp26-tov-v2-extension-20260902", 26,
              [16, 15, 18, 19, 17], [15, 16, 18, 14, 20]),
}
ARMS = {"overlap": "semantic_overlap_verified_union",
        "direct": "semantic_free_structured_verified_union"}


def read(path):
    return json.loads(path.read_text())


def load_draw(directory, ids):
    result_path = directory / "result.json"
    result, contract = read(result_path)["attempt"], read(directory / "contract.json")
    if (contract["model"] != "gpt-5.6-luna" or contract["reasoningEffort"] != "medium"
        or result["agent"]["exit_code"] != 0 or result["agent"]["timed_out"]
        or result["public_test"]["timed_out"]):
        raise ValueError("unexpected model, effort, or incomplete execution")
    rows = []
    for line in result["public_test"]["stdout"].splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and "taskId" in row:
            rows.append(row)
    if (len(rows) != len(ids) or {r["taskId"] for r in rows} != set(ids)
        or any(type(r.get("passed")) is not bool for r in rows)):
        raise ValueError("incomplete, duplicate, or malformed full-track outcome vector")
    outcomes = {r["taskId"]: r["passed"] for r in rows}
    return {"id": directory.name, "vector": [outcomes[i] for i in ids],
            "resultSha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
            "seedSha256": contract["seedPatchSha256"],
            "agentSeconds": result["agent"]["duration_seconds"],
            "verifierSeconds": result["public_test"]["duration_seconds"],
            "forbiddenFiles": result["forbidden_files"]}


def portfolio(a, b):
    if a["id"] == b["id"] or len(a["vector"]) != len(b["vector"]):
        raise ValueError("two distinct complete draws required")
    return {"draws": [a["id"], b["id"]],
            "solved": sum(x or y for x, y in zip(a["vector"], b["vector"])),
            "finalAgentSeconds": a["agentSeconds"] + b["agentSeconds"],
            "finalVerifierSeconds": a["verifierSeconds"] + b["verifierSeconds"]}


def summarize(overlap, direct):
    pairs = {"overlapPlusDirect": itertools.product(overlap, direct),
             "directPlusDirect": itertools.combinations(direct, 2),
             "overlapPlusOverlap": itertools.combinations(overlap, 2)}
    groups = {}
    for label, combinations in pairs.items():
        rows = [portfolio(a, b) for a, b in combinations]
        groups[label] = {"combinations": len(rows),
                         "meanSolved": sum(r["solved"] for r in rows) / len(rows),
                         "minimumSolved": min(r["solved"] for r in rows),
                         "maximumSolved": max(r["solved"] for r in rows),
                         "meanFinalAgentSeconds": sum(r["finalAgentSeconds"] for r in rows) / len(rows),
                         "meanFinalVerifierSeconds": sum(r["finalVerifierSeconds"] for r in rows) / len(rows),
                         "pairs": rows}
    return groups


def analyze():
    tracks = {}
    for label, (run_name, count, expected_overlap, expected_direct) in TRACKS.items():
        root = ROOT / "runs" / run_name
        ids = read(root / "freeze/freeze.json")["selectedTaskIds"]
        if len(ids) != count or len(set(ids)) != count:
            raise ValueError("official complete-track inventory mismatch")
        draws = {arm: [load_draw(root / "arms" / f"{prefix}_rep{i}", ids)
                       for i in range(1, 6)] for arm, prefix in ARMS.items()}
        prior_report = (ROOT / "benchmark_reports" /
                        f"2026-09-03-aider-{label}-tov-vs-semantic-free-five-session-replication" /
                        "RESULTS.md").read_text()
        if any(d["resultSha256"] not in prior_report for group in draws.values() for d in group):
            raise ValueError("result hash differs from the historical replication report")
        if len({d["seedSha256"] for group in draws.values() for d in group}) != 1:
            raise ValueError("shared anchored seed mismatch")
        for arm, expected in [("overlap", expected_overlap), ("direct", expected_direct)]:
            if [sum(d["vector"]) for d in draws[arm]] != expected:
                raise ValueError("saved vectors do not reproduce the prior five-session report")
        groups = summarize(draws["overlap"], draws["direct"])
        leave_one_pair_out = []
        for i in range(5):
            reduced = summarize(draws["overlap"][:i] + draws["overlap"][i + 1:],
                                draws["direct"][:i] + draws["direct"][i + 1:])
            leave_one_pair_out.append(reduced["overlapPlusDirect"]["meanSolved"]
                                      - reduced["directPlusDirect"]["meanSolved"])
        tracks[label] = {"taskIds": ids, "taskCount": count, "draws": draws, "portfolios": groups,
                         "leaveOneOriginalPairOutMeanDifference": leave_one_pair_out}
    return {"scope": "exhaustive post-hoc finite-draw sensitivity, not prospective replication",
            "newModelCalls": 0, "freshlyExecutedMergedWorkspaces": 0,
            "independentSessionsAreNotPairCombinations": True,
            "modelCallsPerDerivedSystem": {"sharedHistoricalPrefix": 3, "finalRoutes": 2},
            "knownDeviations": ["Python: prior ledger-order deviations remain included",
                                "C++ overlap rep1: forbidden a.out remains included, not excused"],
            "tracks": tracks}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyze()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    for track, item in result["tracks"].items():
        print(json.dumps({"track": track, "total": item["taskCount"],
              "portfolios": {k: {a: b for a, b in v.items() if a != "pairs"}
                             for k, v in item["portfolios"].items()},
              "leaveOnePairOutDifference": item["leaveOneOriginalPairOutMeanDifference"]}))


if __name__ == "__main__":
    main()
