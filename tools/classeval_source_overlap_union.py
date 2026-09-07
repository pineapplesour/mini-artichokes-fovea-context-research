"""Distinct developmental source space retaining candidate-exclusive helpers.

The original source-overlap module remains unchanged for its live experiment.
Enriched parents are NEW programs, never assigned their original test scores.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import itertools
import random

from tools import classeval_source_overlap as original


def enrich(sources: list[str], class_name: str) -> list[str]:
    parsed = [original.parse(source, class_name) for source in sources]
    names = set(parsed[0][2]) | set(parsed[1][2])
    enriched = []
    for side in (0, 1):
        tree = copy.deepcopy(parsed[side][0])
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
        missing = names - set(parsed[side][2])
        for name in sorted(missing):
            cls.body.append(copy.deepcopy(parsed[1 - side][2][name]))
        enriched.append(ast.unparse(ast.fix_missing_locations(tree)) + "\n")
    return enriched


def proposals(sources: list[str], class_name: str, feedback: list[dict],
              policy: str, seed: str, limit: int = 16) -> list[dict]:
    if policy not in {"generic", "overlap"} or len(sources) != 2 or len(feedback) != 2:
        raise ValueError("invalid source-composition request")
    if limit < 1:
        return []
    enriched = enrich(sources, class_name)
    parsed, names, slots = original.source_space(enriched, class_name)
    edges = original.field_edges(parsed, names)
    masks = list(itertools.product((0, 1), repeat=len(slots)))
    slot_set = set(slots)

    def prediction(bits):
        assignment = dict(zip(slots, bits))
        covered = set()
        for donor, report in enumerate(feedback):
            for case_id, case in report.get("cases", {}).items():
                if case.get("status") != "passed" or not case.get("methods"):
                    continue
                required = set(case["methods"]) & slot_set
                if "<context>" in slot_set:
                    required.add("<context>")
                if all(assignment[name] == donor for name in required):
                    covered.add(case_id)
        conflicts = sum(assignment.get(a, 0) != assignment.get(b, 0)
                        for a, b in edges if a in slot_set and b in slot_set)
        return (-len(covered), conflicts, min(sum(bits), len(bits) - sum(bits)), bits)

    if policy == "generic":
        random.Random(int(hashlib.sha256(seed.encode()).hexdigest(), 16)).shuffle(masks)
    else:
        masks.sort(key=prediction)
    # Corner masks may now add formerly absent methods. They are not original
    # parents and must consume a real evaluation, just like all other mixtures.
    seen = {original.dump(ast.parse(source)) for source in sources}
    result = []
    for bits in masks:
        source = original.materialize(parsed, class_name, slots, bits)
        identity = original.dump(ast.parse(source))
        if identity in seen:
            continue
        seen.add(identity)
        result.append({"source": source, "assignment": dict(zip(slots, bits)),
                       "predictedPassingCases": -prediction(bits)[0],
                       "sourceSpace": "exclusive-helper-union-v1"})
        if len(result) == limit:
            break
    return result
