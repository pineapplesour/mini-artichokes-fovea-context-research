"""Read-only analysis of a terminal ClassEval-Pro overlap-repair tail.

The analyzer never calls a model or evaluator and never writes inside either
the parent or tail run.  Secondary replay uses the grouped-max equivalence:
the primary winner represents prefix/usable A/B/C, so only cached valid raw
A/B/C receipts need to be compared.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from tools import classeval_ordinary_prefix as prefix_loader
from tools import run_classeval_overlap_repair_tail as tail_runner
from tools import run_classeval_source_overlap as base
from tools import run_classeval_text_overlap as text_runner

ARMS = ("E", "D", "O")
CALLS = ("a", "b", "c")
SECONDARY_ORDER = (
    "prefix", "usableA", "usableB", "usableC", "validrawA", "validrawB", "validrawC"
)
USAGE_FIELDS = ("input_tokens", "output_tokens", "reasoning_output_tokens",
                "cached_input_tokens", "cache_write_input_tokens")


def _json(path: Path) -> dict:
    return json.loads(path.read_text())


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def paired_exact(candidate: list[bool], control: list[bool]) -> dict:
    """Return a two-sided exact paired-binomial comparison."""

    if len(candidate) != len(control) or not candidate:
        raise ValueError("nonempty aligned vectors required")
    rescues = sum(a and not b for a, b in zip(candidate, control))
    harms = sum(b and not a for a, b in zip(candidate, control))
    discordant = rescues + harms
    if discordant == 0:
        p = 1.0
    else:
        tail = sum(math.comb(discordant, k)
                   for k in range(min(rescues, harms) + 1)) / 2 ** discordant
        p = min(1.0, 2 * tail)
    return {"rescues": rescues, "harms": harms, "net": rescues - harms,
            "absolutePercentagePoints": 100 * (rescues - harms) / len(candidate),
            "discordant": discordant, "exactTwoSidedP": p}


def holm_two(comparisons: dict[str, dict]) -> dict[str, float]:
    """Holm-adjust the two predeclared two-sided comparison p-values."""

    names = list(comparisons)
    values = [float(comparisons[name]["exactTwoSidedP"]) for name in names]
    adjusted, previous = {}, 0.0
    for rank, index in enumerate(sorted(range(len(values)), key=values.__getitem__)):
        previous = max(previous, min(1.0, values[index] * (len(values) - rank)))
        adjusted[names[index]] = previous
    return adjusted


def _check_report(report: dict) -> bool:
    if not isinstance(report, dict) or not isinstance(report.get("passed"), bool):
        raise ValueError("report lacks boolean passed")
    cases = report.get("cases")
    if not isinstance(cases, dict):
        raise ValueError("report lacks cases")
    if report["passed"] and (report.get("fatal") is not None
                              or report.get("expectedCount") != len(cases)
                              or any(not isinstance(case, dict) or case.get("status") != "passed"
                                     for case in cases.values())):
        raise ValueError("passing report lacks complete successful test inventory")
    return report["passed"]


def _ordered_ids(rows: list[dict]) -> list[str]:
    ids = [row["task_id"] for row in rows]
    if len(ids) != 300 or len(ids) != len(set(ids)):
        raise ValueError("exact official 300-task inventory required")
    return ids


def _inside(path: Path, root: Path) -> Path:
    path, root = path.resolve(), root.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"artifact escapes its run root: {path}") from exc
    return path


def _expected_contract(ids: list[str]) -> dict:
    helpers = {
        "prefixLoaderSha": base.sha(Path(prefix_loader.__file__)),
        "scopeOperatorSha": base.sha(Path(tail_runner.scope_operator.__file__)),
        "baseRunnerSha": base.sha(Path(base.__file__)),
        "textRunnerSha": base.sha(Path(text_runner.__file__)),
    }
    return {
        "dataset": "classeval-pro", "taskIds": ids, "dataSha": base.PRO_SHA,
        "runnerSha": base.sha(Path(tail_runner.__file__)),
        "protocolSha": base.sha(tail_runner.PROTOCOL),
        "textRunnerSha": helpers["textRunnerSha"],
        "evaluatorSha": base.sha(base.ROOT / "tools/classeval_isolated_evaluator.py"),
        "helperShas": helpers, "prefixLoaderSha": helpers["prefixLoaderSha"],
        "scopeOperatorSha": helpers["scopeOperatorSha"],
        "baseRunnerSha": helpers["baseRunnerSha"], "model": tail_runner.MODEL,
        "effort": tail_runner.EFFORT, "timeoutSeconds": tail_runner.TIMEOUT,
        "tailModelCallsOnFailure": 3, "logicalCallCap": 6, "suiteEvalCap": 6,
        "rawAutoEvaluation": "discarded",
    }


def _validate_contract(run_root: Path, contract: dict, ids: list[str]) -> Path:
    expected = _expected_contract(ids)
    for key, value in expected.items():
        if contract.get(key) != value:
            raise ValueError(f"tail contract mismatch: {key}")
    if Path(contract.get("runRoot", "")).resolve() != run_root.resolve():
        raise ValueError("tail runRoot mismatch")
    parent = Path(contract.get("parentRoot", "")).resolve()
    if not parent.is_dir():
        raise ValueError("parent root is missing")
    for key, name in (("parentContractPath", "contract.json"), ("parentResultPath", "result.json")):
        if Path(contract.get(key, "")).resolve() != parent / name:
            raise ValueError(f"{key} mismatch")
        if not (parent / name).is_file():
            raise ValueError(f"missing parent {name}")
    if contract.get("parentContractSha") != base.sha(parent / "contract.json"):
        raise ValueError("parent contract SHA mismatch")
    if contract.get("parentResultSha") != base.sha(parent / "result.json"):
        raise ValueError("parent result SHA mismatch")
    return parent


def _validate_prefix_map(contract: dict, prefixes: dict[str, dict], ids: list[str]) -> None:
    prefix_map = contract.get("prefixMap")
    if not isinstance(prefix_map, dict) or list(prefix_map) != ids:
        raise ValueError("prefix map inventory mismatch")
    for task_id in ids:
        expected = {key: prefixes[task_id][key]
                    for key in ("callPaths", "sourceSha", "logicalPrefixCalls")}
        if prefix_map.get(task_id) != expected:
            raise ValueError(f"prefix map mismatch: {task_id}")


def _empty_cost() -> dict:
    return {"physicalReceipts": 0, "durationSeconds": 0.0,
            "missingDurationReceipts": 0, "missingUsageReceipts": 0,
            **{field: 0 for field in USAGE_FIELDS}}


def _add_cost(total: dict, receipt_path: Path) -> None:
    receipt = _json(receipt_path)
    if not isinstance(receipt, dict):
        raise ValueError(f"receipt is not an object: {receipt_path}")
    total["physicalReceipts"] += 1
    duration = receipt.get("duration_seconds")
    if isinstance(duration, (int, float)) and not isinstance(duration, bool):
        total["durationSeconds"] += float(duration)
    else:
        total["missingDurationReceipts"] += 1
    usage = receipt.get("usage")
    if not isinstance(usage, dict):
        total["missingUsageReceipts"] += 1
        return
    for field in USAGE_FIELDS:
        value = usage.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            total[field] += value


def _read_tail_call(row: dict, directory: Path, label: str) -> tuple[dict, dict]:
    """Validate one cached tail receipt/source/report without evaluating it."""

    item = prefix_loader._call(row, directory, label)
    receipt = _json(directory / "receipt.json")
    item.update({"rawSourceSha": receipt.get("sourceSha"),
                 "candidateSourceSha": _sha_text(item["source"]),
                 "artifactPath": str((directory / "artifact" / "last_message.txt").resolve())})
    cost = _empty_cost()
    _add_cost(cost, directory / "receipt.json")
    return item, cost


def _counter(state: dict, key: str) -> int:
    value = state.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"invalid arm counter: {key}")
    return value


def _evaluation_breakdown(state: dict, arm: str) -> dict[str, int]:
    reported = _counter(state, "projectedEvalCalls")
    canonical = _counter(state, "canonicalEvalCalls")
    fallback = state.get("fallback")
    if arm not in ARMS or not isinstance(fallback, bool):
        raise ValueError("invalid arm fallback marker")
    scoped = reported if arm != "E" and not fallback else 0
    if scoped > canonical:
        raise ValueError("scoped projection exceeds canonical evaluation count")
    return {"reportedABCanonicalEvalCalls": reported,
            "scopedProjectedEvalCalls": scoped,
            "fullCanonicalEvalCalls": canonical - scoped}


def _validate_arm(row: dict, prefix: dict, task_root: Path, arm: str,
                  state: dict) -> tuple[bool, dict, dict[str, dict]]:
    if not isinstance(state, dict) or not isinstance(state.get("report"), dict):
        raise ValueError(f"missing arm result: {arm}")
    passed = _check_report(state["report"])
    if state.get("logicalPrefixCalls") != prefix["logicalPrefixCalls"]:
        raise ValueError("arm/prefix logical call mismatch")
    selected = state.get("selected")
    if selected not in {"prefix", "A", "B", "C"}:
        raise ValueError("invalid arm selector")
    if selected == "prefix" and (state.get("source") != prefix["source"]
                                  or state["report"] != prefix["report"]):
        raise ValueError("prefix selector does not preserve prefix source/report")
    for key in ("rawEvalCalls", "canonicalEvalCalls", "suiteEvalCalls", "projectedEvalCalls"):
        _counter(state, key)
    if state["suiteEvalCalls"] != state["rawEvalCalls"] + state["canonicalEvalCalls"]:
        raise ValueError("raw/canonical suite counter mismatch")
    if state["suiteEvalCalls"] > 6 or state["projectedEvalCalls"] > state["canonicalEvalCalls"]:
        raise ValueError("suite evaluation cap mismatch")

    status = state.get("status")
    raw_calls: dict[str, dict] = {}
    cost = _empty_cost()
    if status == "stopped":
        if state.get("tailModelCalls") != 0 or state.get("totalLogicalCalls") != prefix["logicalPrefixCalls"]:
            raise ValueError("stopped arm call counters mismatch")
        if any(state[key] for key in ("rawEvalCalls", "canonicalEvalCalls", "suiteEvalCalls",
                                      "projectedEvalCalls")):
            raise ValueError("stopped arm has evaluation calls")
        if (task_root / arm).exists():
            raise ValueError("stopped arm has tail artifacts")
    elif status == "executed":
        if state.get("tailModelCalls") != 3 or state.get("totalLogicalCalls") != prefix["logicalPrefixCalls"] + 3:
            raise ValueError("executed arm call counters mismatch")
        arm_root = task_root / arm
        for suffix in CALLS:
            directory = _inside(arm_root / suffix, task_root)
            if not directory.is_dir():
                raise ValueError(f"missing tail call directory: {directory}")
            item, item_cost = _read_tail_call(row, directory, f"tail-{arm}-{suffix.upper()}")
            raw_calls[suffix.upper()] = item
            for key, value in item_cost.items():
                cost[key] += value
        if cost["physicalReceipts"] != 3:
            raise ValueError("executed arm must have three receipts")
        if state["rawEvalCalls"] != sum(item["valid"] is True for item in raw_calls.values()):
            raise ValueError("raw evaluation counter disagrees with receipts")
        if selected != "prefix" and raw_calls[selected.upper()]["valid"] is not True:
            raise ValueError("selected tail candidate has an invalid model receipt")
    else:
        raise ValueError(f"nonterminal arm status: {status}")
    return passed, cost, raw_calls


def _score(candidate: dict) -> tuple[bool, int]:
    report = candidate.get("report")
    if not isinstance(report, dict):
        raise ValueError("secondary candidate lacks report")
    passed = _check_report(report)
    return passed, sum(case.get("status") == "passed"
                       for case in report["cases"].values() if isinstance(case, dict))


def select_secondary(candidates: dict[str, dict]) -> tuple[str, str]:
    """Select the fixed cached candidate order and return label/route."""

    selected = None
    for label in SECONDARY_ORDER:
        candidate = candidates.get(label)
        if candidate is None:
            continue
        if label.startswith("validraw") and candidate.get("valid") is not True:
            continue
        if label.startswith("usable") and candidate.get("valid") is not True:
            continue
        _score(candidate)
        if selected is None or _score(candidate) > _score(selected[1]):
            selected = (label, candidate)
    if selected is None:
        raise ValueError("secondary candidate set is empty")
    label = selected[0]
    return label, "raw-global" if label.startswith("validraw") else "canonical-usable"


_PRIMARY_LABEL = {"prefix": "prefix", "A": "usableA", "B": "usableB", "C": "usableC"}


def grouped_secondary(primary: dict, raw_calls: dict[str, dict]) -> dict:
    """Apply the seven-candidate selector without needing usable A/B/C storage.

    ``primary`` is the already selected tail result (source/report/selected).
    Since its selector considered prefix and usable A/B/C in this order, it is
    exactly their grouped maximum; only valid cached raw calls can change it.
    """

    primary_label = _PRIMARY_LABEL.get(primary.get("selected"))
    if primary_label is None:
        raise ValueError("primary result has an invalid selector")
    _check_report(primary.get("report"))
    if not isinstance(primary.get("source"), str):
        raise ValueError("primary result lacks source")
    primary_candidate = {"source": primary["source"], "report": primary["report"],
                         "valid": True, "provenance": "primary"}
    candidates = {primary_label: primary_candidate}
    for letter in ("A", "B", "C"):
        item = raw_calls.get(letter)
        if item is not None:
            candidates[f"validraw{letter}"] = item
    label, route = select_secondary(candidates)
    chosen = candidates[label]
    output = {"label": label, "route": route, "passed": _score(chosen)[0],
              "passedCases": _score(chosen)[1], "source": chosen["source"],
              "report": chosen["report"], "primaryLabel": primary_label,
              "primarySelected": primary["selected"]}
    if route == "raw-global":
        output.update({"artifactPath": chosen.get("artifactPath"),
                       "rawSourceSha": chosen.get("rawSourceSha"),
                       "candidateSourceSha": chosen.get("candidateSourceSha")})
    else:
        output["primarySourceSha"] = _sha_text(primary["source"])
    return output


def analyze(run_root: Path) -> dict:
    """Analyze one terminal full-300 tail, reading only existing artifacts."""

    run_root = Path(run_root).resolve()
    contract = _json(run_root / "contract.json")
    rows = base.load_data("classeval-pro")
    ids = _ordered_ids(rows)
    parent_root = _validate_contract(run_root, contract, ids)
    prefixes = prefix_loader.load_ordinary_prefix(parent_root)
    if list(prefixes) != ids:
        raise ValueError("ordinary prefix inventory is not in official order")
    _validate_prefix_map(contract, prefixes, ids)
    result = _json(run_root / "result.json")
    if (result.get("status") != "complete" or result.get("completed") != 300
            or result.get("total") != 300 or list(result.get("tasks", {})) != ids):
        raise ValueError("terminal complete full300 tail result required")

    pass_vectors = {arm: [] for arm in ARMS}
    eval_counts = {arm: {"rawAutoEvalCalls": 0, "canonicalEvalCalls": 0,
                         "suiteEvalCalls": 0,
                         "reportedABCanonicalEvalCalls": 0,
                         "scopedProjectedEvalCalls": 0,
                         "fullCanonicalEvalCalls": 0} for arm in ARMS}
    tail_cost = {arm: _empty_cost() for arm in ARMS}
    common_cost = _empty_cost()
    secondary_vectors = {arm: [] for arm in ARMS}
    secondary_raw_selections = []
    secondary_route_counts = {arm: {"primary": 0, "raw-global": 0} for arm in ARMS}
    for row in rows:
        task_id = row["task_id"]
        prefix = prefixes[task_id]
        paths = prefix.get("callPaths", {})
        if not isinstance(paths, dict):  # pragma: no cover - production loader normally guarantees this
            raise ValueError("invalid prefix call paths")
        seen = set()
        for raw_path in paths.values():
            path = _inside(Path(raw_path), parent_root)
            if path in seen or not (path / "receipt.json").is_file():
                raise ValueError("duplicate or missing common prefix receipt")
            seen.add(path)
            _add_cost(common_cost, path / "receipt.json")
        if len(seen) != prefix["logicalPrefixCalls"]:
            raise ValueError("common prefix physical/logical call mismatch")
        task_state = result["tasks"].get(task_id)
        if not isinstance(task_state, dict) or set(task_state) != set(ARMS):
            raise ValueError(f"arm inventory mismatch: {task_id}")
        for arm in ARMS:
            passed, cost, raw_calls = _validate_arm(row, prefix, run_root / task_id,
                                                    arm, task_state[arm])
            pass_vectors[arm].append(passed)
            secondary = grouped_secondary(task_state[arm], raw_calls)
            secondary_vectors[arm].append(secondary["passed"])
            route = "raw-global" if secondary["route"] == "raw-global" else "primary"
            secondary_route_counts[arm][route] += 1
            if route == "raw-global":
                secondary_raw_selections.append({
                    "taskId": task_id, "arm": arm, "label": secondary["label"],
                    "passed": secondary["passed"], "passedCases": secondary["passedCases"],
                    "artifactPath": secondary["artifactPath"],
                    "rawSourceSha": secondary["rawSourceSha"],
                    "candidateSourceSha": secondary["candidateSourceSha"],
                })
            for key in tail_cost[arm]:
                tail_cost[arm][key] += cost[key]
            state = task_state[arm]
            breakdown = _evaluation_breakdown(state, arm)
            eval_counts[arm]["rawAutoEvalCalls"] += state["rawEvalCalls"]
            eval_counts[arm]["canonicalEvalCalls"] += state["canonicalEvalCalls"]
            eval_counts[arm]["suiteEvalCalls"] += state["suiteEvalCalls"]
            for key, value in breakdown.items():
                eval_counts[arm][key] += value

    comparisons = {
        "O-minus-E": paired_exact(pass_vectors["O"], pass_vectors["E"]),
        "O-minus-D": paired_exact(pass_vectors["O"], pass_vectors["D"]),
    }
    adjusted = holm_two(comparisons)
    for name, value in adjusted.items():
        comparisons[name]["holmTwoSidedPComparisons2"] = value
    campaign_physical = common_cost["physicalReceipts"] + sum(
        cost["physicalReceipts"] for cost in tail_cost.values())
    secondary = {
        "status": "available", "method": "grouped-max-equivalent",
        "candidateOrder": list(SECONDARY_ORDER),
        "passCounts": {arm: sum(secondary_vectors[arm]) for arm in ARMS},
        "routeCounts": secondary_route_counts,
        "rawGlobalSelections": secondary_raw_selections,
        "additionalModelCalls": 0, "additionalEvaluatorCalls": 0,
        "rawGlobalSeparate": True, "cInputUnchanged": True,
        "primaryUnchanged": True,
        "equivalence": "max(primaryWinner,validrawA,validrawB,validrawC)",
        "primaryWinnerRepresents": ["prefix", "usableA", "usableB", "usableC"],
    }
    return {
        "status": "complete", "analysis": "primary_tail_full300",
        "benchmarkTotal": 300, "taskIdsInOrder": ids,
        "passCounts": {arm: sum(pass_vectors[arm]) for arm in ARMS},
        "comparisons": comparisons, "holmFamily": list(comparisons),
        "evaluationAccounting": eval_counts,
        "callAccounting": {
            "commonPrefix": common_cost,
            "tailPhysicalReceiptsByArm": {arm: tail_cost[arm]["physicalReceipts"] for arm in ARMS},
            "tailLogicalCallsByArm": {arm: sum(result["tasks"][task][arm]["tailModelCalls"]
                                               for task in ids) for arm in ARMS},
            "perArmLogicalCallsIncludingCommonPrefix": {
                arm: sum(result["tasks"][task][arm]["totalLogicalCalls"] for task in ids)
                for arm in ARMS},
            "campaignPhysicalReceipts": campaign_physical,
            "logicalCommonPrefixIsCountedOnce": True,
            "physicalSpendIsNotPerSystemLogicalBudget": True,
        },
        "modelUsage": {"commonPrefix": common_cost,
                       "tailByArm": tail_cost},
        "secondaryCachedReplay": secondary,
        "provenance": {
            "runRoot": str(run_root), "parentRoot": str(parent_root),
            "tailContractSha": base.sha(run_root / "contract.json"),
            "tailResultSha": base.sha(run_root / "result.json"),
            "parentContractSha": base.sha(parent_root / "contract.json"),
            "parentResultSha": base.sha(parent_root / "result.json"),
            "dataSha": contract["dataSha"], "rawAutoEvaluation": "discarded",
        },
    }


def render_markdown(summary: dict) -> str:
    comparisons = summary["comparisons"]
    lines = ["# ClassEval-Pro overlap-repair tail analysis", "",
             "Read-only terminal full-300 analysis; no model/evaluator calls.", "",
             f"Pass counts (E/D/O): {summary['passCounts']['E']}/{summary['passCounts']['D']}/{summary['passCounts']['O']}."]
    for name in ("O-minus-E", "O-minus-D"):
        item = comparisons[name]
        lines.append(f"{name}: rescue={item['rescues']}, harm={item['harms']}, "
                     f"absolute pp={item['absolutePercentagePoints']:.6g}, "
                     f"two-sided p={item['exactTwoSidedP']:.6g}, "
                     f"Holm-2={item['holmTwoSidedPComparisons2']:.6g}.")
    calls = summary["callAccounting"]
    lines += [f"Common prefix logical calls are counted once; physical campaign receipts={calls['campaignPhysicalReceipts']}.",
              f"Tail physical receipts by arm: {calls['tailPhysicalReceiptsByArm']}; raw/canonical evaluation counts remain separate (reported AB vs scoped projection are distinct).",
              f"Secondary cached replay: {summary['secondaryCachedReplay']['status']} (posthoc, raw-global separate, C input unchanged)."]
    return "\n".join(lines) + "\n"


def _output_outside(path: Path, *roots: Path) -> Path:
    path = path.resolve()
    for root in roots:
        try:
            path.relative_to(root.resolve())
        except ValueError:
            continue
        raise ValueError("analysis output must be outside source run roots")
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    args = parser.parse_args(argv)
    summary = analyze(args.run_root)
    parent = Path(summary["provenance"]["parentRoot"])
    output_json = _output_outside(args.output_json, args.run_root, parent)
    output_md = _output_outside(args.output_md, args.run_root, parent)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    output_md.write_text(render_markdown(summary))
    print(render_markdown(summary), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
