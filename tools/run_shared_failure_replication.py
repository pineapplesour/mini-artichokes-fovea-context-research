#!/usr/bin/env python3
"""Fixed maximum-five-pair study with a first-pair futility gate, never early success."""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
import subprocess
import sys

from tools.analyze_aider_online_offline_portfolio import compare


# Five independent choice draws from random.Random(20260905), fixed before calls.
ORDERS = [("overlap", "generic"), ("generic", "overlap"), ("overlap", "generic"),
          ("overlap", "generic"), ("generic", "overlap")]


def randomization_p(deltas: list[int]) -> float:
    observed = sum(deltas)
    values = [sum(d * sign for d, sign in zip(deltas, signs))
              for signs in itertools.product([-1, 1], repeat=len(deltas))]
    return sum(value >= observed for value in values) / len(values)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True, type=Path)
    args = parser.parse_args()
    root = args.run_root.resolve()
    out = root / "replications/shared-failure-v2"
    if out.exists():
        raise FileExistsError(out)
    out.mkdir(parents=True)
    pairs = []
    for number, order in enumerate(ORDERS, 1):
        reports, contracts, exits = {}, {}, {}
        for policy in order:
            name = f"shared_failure_v2_b{number}_{policy}"
            completed = subprocess.run([sys.executable, "-m", "tools.run_aider_shared_failure_overlap",
                "--run-root", str(root), "--policy", policy, "--candidate-id", name,
                "--completion-reserve-seconds", "180"], check=False)
            exits[policy] = completed.returncode
            file = root / "arms" / name / "system-result.json"
            if completed.returncode == 0 and file.exists():
                reports[policy] = json.loads(file.read_text())
                contracts[policy] = json.loads((file.parent / "contract.json").read_text())
        if len(reports) != 2:
            (out / "status.json").write_text(json.dumps({"status": "stopped_after_invalid_pair",
                "pair": number, "completedValidPairs": pairs, "exitCodes": exits,
                "inference": "No five-pair primary conclusion; all original attempts retained."}, indent=2) + "\n")
            return 2
        for field in ["taskIds", "model", "effort", "agentTimeoutSeconds", "completionReserveSeconds",
                      "seedPatchSha256", "evidenceHashes", "captureHashes", "runnerSha256"]:
            if contracts["generic"][field] != contracts["overlap"][field]:
                raise ValueError(f"unmatched pair input: {field}")
        paired = compare(reports["generic"]["systemTaskOutcomes"], reports["overlap"]["systemTaskOutcomes"])
        row = {"pair": number, "order": list(order), "comparison": paired,
               "scores": {policy: reports[policy]["systemPassed"] for policy in reports}}
        pairs.append(row)
        (out / f"pair-{number}.json").write_text(json.dumps(row, indent=2) + "\n")
        print(json.dumps(row), flush=True)
        if number == 1 and paired["netTasks"] < 4:
            (out / "status.json").write_text(json.dumps({"status": "stopped_for_futility",
                "completedValidPairs": pairs, "inference": "No superiority/equivalence declaration from the first pair."}, indent=2) + "\n")
            return 0
    deltas = [row["comparison"]["netTasks"] for row in pairs]
    summary = {"status": "all_five_pairs_complete", "pairs": pairs, "netTaskDifferences": deltas,
               "meanNetTasks": sum(deltas) / 5, "meanPercentagePointDifference": 100 * sum(deltas) / (5 * 47),
               "oneSidedPairedLabelSwapP": randomization_p(deltas),
               "interpretation": "Five fresh final-execution pairs conditional on the same fixed P/G/R prefix and47 tasks. "
                    "Not235 independent tasks or full-prefix replications. No early success test was used."}
    (out / "status.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
