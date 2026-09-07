"""Read-only full-inventory analysis of frozen post-repair overlap replays.

These are development, task-conditional summaries, not fresh-session proof.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from tools import run_classeval_source_overlap as base


BUDGETS = (1, 2, 4, 8, 16)


def paired(candidate, control):
    if len(candidate) != len(control) or not candidate:
        raise ValueError("nonempty aligned vectors required")
    wins = sum(a and not b for a, b in zip(candidate, control))
    losses = sum(b and not a for a, b in zip(candidate, control))
    discordant = wins + losses
    p = sum(math.comb(discordant, k) for k in range(wins, discordant + 1)) / 2 ** discordant
    tail = sum(math.comb(discordant, k) for k in range(min(wins, losses) + 1)) / 2 ** discordant
    return {"rescues": wins, "harms": losses, "net": wins - losses,
            "differencePercentagePoints": 100 * (wins - losses) / len(candidate),
            "conditionalOneSidedP": p, "conditionalTwoSidedP": min(1.0, 2 * tail)}


def holm(values):
    adjusted, previous = [0.0] * len(values), 0.0
    for rank, index in enumerate(sorted(range(len(values)), key=values.__getitem__)):
        previous = max(previous, min(1.0, values[index] * (len(values) - rank)))
        adjusted[index] = previous
    return adjusted


def read(path):
    return json.loads(path.read_text())


def check_report(report):
    if report["passed"] and (report.get("fatal") is not None or not report["cases"]
        or report.get("expectedCount") != len(report["cases"])
        or any(case["status"] != "passed" for case in report["cases"].values())):
        raise ValueError("passing report lacks complete successful test inventory")
    return report["passed"]


def analyze(root, allow_diagnostic=False):
    contract, result = read(root / "contract.json"), read(root / "result.json")
    ids = contract["taskIds"]
    expected = [r["task_id"] for r in base.load_data("classeval-pro")]
    complete = (ids == expected and result["completed"] == 300
                and not contract["diagnosticOnly"])
    if (contract["dataSha"] != base.PRO_SHA or result["total"] != 300
        or len(ids) != result["completed"] or set(result["tasks"]) != set(ids)
        or ids != expected[:len(ids)] or contract["parentStage"] != "ordinary-feedback-repair"):
        raise ValueError("replay inventory or parent stage mismatch")
    if not complete and not allow_diagnostic:
        raise ValueError("full300 result required; diagnostic output needs explicit flag")
    parent = Path(contract["parentRoot"])
    snapshot = contract["statusSnapshot"]["tasks"]
    ordinary = [snapshot[i]["ordinaryFinal"] for i in ids]
    vectors = {b: {p: [] for p in ("generic", "overlap")} for b in BUDGETS}
    costs = {b: {p: {"programTrials": 0, "trialWallSeconds": 0.0} for p in ("generic", "overlap")}
             for b in BUDGETS}
    model_cost = {"logicalCalls": 0, "durationSeconds": 0.0, "availableInputTokens": 0,
                  "availableOutputTokens": 0, "receiptsMissingUsage": 0}
    physical_calls = 0
    for task_id in ids:
        original_final = parent / task_id / "ordinary-final"
        if check_report(read(original_final / "evaluation.json")) != snapshot[task_id]["ordinaryFinal"]:
            raise ValueError("ordinary baseline report mismatch")
        selected = read(original_final / "result.json")
        call_names = ["a"] + (["b"] if snapshot[task_id]["parentCalls"] == 2 else [])
        if selected["repairFrom"] is not None:
            call_names.append(selected["repairFrom"])
        for name in call_names:
            receipt = read(parent / task_id / name / "receipt.json")
            model_cost["logicalCalls"] += 1
            model_cost["durationSeconds"] += receipt["duration_seconds"]
            usage = receipt.get("usage")
            model_cost["receiptsMissingUsage"] += usage is None
            model_cost["availableInputTokens"] += (usage or {}).get("input_tokens", 0)
            model_cost["availableOutputTokens"] += (usage or {}).get("output_tokens", 0)
        physical_calls += sum((p / "receipt.json").is_file() for p in (parent / task_id).iterdir() if p.is_dir())
        for policy in ("generic", "overlap"):
            directory = root / task_id / policy
            trials = result["tasks"][task_id][policy]["trials"]
            if len(trials) > 16:
                raise ValueError("frozen trial cap exceeded")
            observed, seconds = [], []
            for index, trial in enumerate(trials):
                report = read(directory / f"evaluation-{index:02d}.json")
                if check_report(report) != trial["passed"]:
                    raise ValueError("trial summary disagrees with actual evaluation")
                if not (directory / f"candidate-{index:02d}.py").read_text().strip():
                    raise ValueError("missing executable trial source")
                observed.append(report["passed"])
                seconds.append(report["wallSeconds"])
            actual_final = check_report(read(directory / "selected-evaluation.json"))
            if actual_final != result["tasks"][task_id][policy]["passed"]:
                raise ValueError("selected final summary mismatch")
            if actual_final != (snapshot[task_id]["ordinaryFinal"] or any(observed)):
                raise ValueError("final result is not supported by observed candidates")
            for budget in BUDGETS:
                vectors[budget][policy].append(snapshot[task_id]["ordinaryFinal"] or any(observed[:budget]))
                costs[budget][policy]["programTrials"] += min(budget, len(observed))
                costs[budget][policy]["trialWallSeconds"] += sum(seconds[:budget])
    curve, family = [], []
    for budget in BUDGETS:
        v = vectors[budget]
        comparisons = {"versusRandom": paired(v["overlap"], v["generic"]),
                       "versusOrdinary": paired(v["overlap"], ordinary)}
        for comparison in comparisons.values():
            family.append(comparison)
        curve.append({"maximumProgramTrials": budget, "ordinarySolved": sum(ordinary),
                      "genericSolved": sum(v["generic"]), "overlapSolved": sum(v["overlap"]),
                      "comparisons": comparisons, "addedVerifierCosts": costs[budget],
                      "overlapOnlyVsRandom": [i for i, a, b in zip(ids, v["overlap"], v["generic"]) if a and not b],
                      "randomOnlyVsOverlap": [i for i, a, b in zip(ids, v["overlap"], v["generic"]) if b and not a]})
    for comparison, adjusted in zip(family, holm([x["conditionalOneSidedP"] for x in family])):
        comparison["holmOneSidedPAllTenComparisons"] = adjusted
    return {"completed": len(ids), "benchmarkTotal": 300, "completeInventory": complete,
            "diagnosticOnly": not complete,
            "inferenceScope": "exposed development; task-conditional summaries, not fresh-session confirmation",
            "modelCostPerComparedSystem": model_cost,
            "parentCampaignPhysicalCallsForTheseTasks": physical_calls,
            "otherParentCampaignCallsNotUsedByTheseSystems": physical_calls - model_cost["logicalCalls"],
            "curve": curve}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--allow-diagnostic", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyze(args.run_root, args.allow_diagnostic)
    if args.output:
        base.write_json(args.output, result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
