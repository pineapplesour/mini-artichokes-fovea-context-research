"""Lossless failure views: case-local feedback or cross-candidate expectations.

Only the organization of already supplied feedback changes. No assertion is
inferred, no task is selected, and an unparsed diagnostic stays unparsed.
"""
from __future__ import annotations

import json
import re


ACTUAL = re.compile(r"\n[ \t]*but was:[ \t]*(?:\n)?")
EXPECTED = re.compile(r"(?:Expecting message to be:|\bexpected:)")
LABELS = ("plain", "graph", "ordinary_repair")


def split_failure(message: str) -> dict:
    """Separate displayed expectations from observations, preserving every byte."""
    markers = list(ACTUAL.finditer(message))
    marker = markers[0] if len(markers) == 1 else None
    if marker and EXPECTED.search(message[:marker.start()]):
        return {"kind": "displayed_expectation", "expected": message[:marker.start()],
                "separator": marker.group(), "observed": message[marker.end():]}
    return {"kind": "unparsed_diagnostic", "message": message}


def restore_failure(row: dict) -> str:
    if row["kind"] == "unparsed_diagnostic":
        return row["message"]
    return row["expected"] + row["separator"] + row["observed"]


def make_view(feedback: dict, mode: str) -> dict:
    if mode not in {"case_local", "obligation_overlap"}:
        raise ValueError(mode)
    tasks = {}
    for task_id, task in sorted(feedback.items()):
        if tuple(task["candidateOrder"]) != LABELS:
            raise ValueError("unexpected candidate order")
        common = {"wholeTaskPassed": task["wholeTaskPassed"],
                  "noCaseReport": task["noCaseReport"],
                  "reportedCaseCounts": {
                      label: {status: sum(values[index] == status for values in task["caseStatus"].values())
                              for status in ("passed", "failed", "error", "not_reported")}
                      for index, label in enumerate(LABELS)}}
        local = [{"caseId": case_id, "failures": [
                    {"candidates": row["candidates"], **split_failure(row["message"])}
                    for row in rows]}
                 for case_id, rows in sorted(task["failures"].items())]
        if mode == "case_local":
            common["caseFailures"] = local
        else:
            groups = {}
            for case in local:
                for row in case["failures"]:
                    definition = {k: v for k, v in row.items() if k not in {"candidates", "observed"}}
                    key = json.dumps(definition, sort_keys=True, ensure_ascii=False)
                    group = groups.setdefault(key, {**definition, "observations": []})
                    group["observations"].append({"caseId": case["caseId"],
                        "candidates": row["candidates"],
                        **({"observed": row["observed"]} if "observed" in row else {})})
            cards = []
            for group in groups.values():
                support = {}
                for row in group["observations"]:
                    support.setdefault(row["caseId"], set()).update(row["candidates"])
                group["crossLineageCaseIds"] = sorted(case_id for case_id, labels in support.items()
                    if "plain" in labels and labels.intersection({"graph", "ordinary_repair"}))
                cards.append(group)
            common["requirementGroups"] = cards
        tasks[task_id] = common
    return {"format": mode, "taskCount": len(tasks),
            "interpretation": "Displayed expectations are authoritative feedback, not complete specifications. "
                "Identical displayed expectations suggest a shared obligation, not a proved shared cause. "
                "Unparsed diagnostics remain unknown. Graph and ordinary repair share one lineage. "
                "Full case statuses, raw messages and public sources remain available in the original evidence.",
            "tasks": tasks}


def failure_records(view: dict) -> list[tuple[str, str, str, str]]:
    """Canonical evidence records used to verify equal information in both views."""
    records = []
    for task_id, task in view["tasks"].items():
        if view["format"] == "case_local":
            rows = [(case["caseId"], row) for case in task["caseFailures"] for row in case["failures"]]
        else:
            rows = [(row["caseId"], {**group, **row})
                    for group in task["requirementGroups"] for row in group["observations"]]
        for case_id, row in rows:
            for candidate in row["candidates"]:
                records.append((task_id, case_id, candidate, restore_failure(row)))
    return sorted(records)
