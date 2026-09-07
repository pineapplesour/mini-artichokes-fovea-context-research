"""Prioritize minimal donor transplants from contrasting test-method traces."""
from __future__ import annotations

import ast
import itertools
from pathlib import Path

from tools import classeval_source_overlap as original
from tools import classeval_source_overlap_union as union


PROTOCOL = Path(__file__).resolve().parents[1] / "experiment_protocols/2026-09-05-classeval-contrast-overlap-development.md"


def proposals(sources, class_name, feedback, policy, seed, limit=16):
    if policy == "generic":
        return union.proposals(sources, class_name, feedback, policy, seed, limit)
    if policy != "overlap" or len(sources) != 2 or len(feedback) != 2:
        raise ValueError("invalid source-composition request")
    if limit < 1:
        return []
    parsed, names, slots = original.source_space(union.enrich(sources, class_name), class_name)
    indices = {name: i for i, name in enumerate(slots)}
    edges = original.field_edges(parsed, names)
    witnesses = []
    for anchor in (0, 1):
        donor = 1 - anchor
        for case_id, case in feedback[anchor].get("cases", {}).items():
            other = feedback[donor].get("cases", {}).get(case_id, {})
            if case.get("status") not in {"failed", "error"} or other.get("status") != "passed":
                continue
            shared = set(case.get("methods", [])) & set(other.get("methods", []))
            relevant = sorted(shared & set(indices))
            if relevant:
                witnesses.append((len(relevant), case_id, anchor, relevant))
    ordered, explanations = [], {}
    for _, case_id, anchor, relevant in sorted(witnesses):
        groups = [relevant] + [[name] for name in relevant] if len(relevant) > 1 else [relevant]
        for group in groups:
            mask = [anchor] * len(slots)
            for name in group:
                mask[indices[name]] = 1 - anchor
            variants = [tuple(mask)]
            if "<context>" in indices:
                mask[indices["<context>"]] = 1 - anchor
                variants.append(tuple(mask))
            for bits in variants:
                if bits not in explanations:
                    explanations[bits] = {"case": case_id, "anchor": anchor, "donor": 1 - anchor,
                                          "sharedMethods": relevant, "transplantedMethods": group}
                    ordered.append(bits)

    def rank(bits):
        assignment, covered = dict(zip(slots, bits)), set()
        for donor, report in enumerate(feedback):
            for case_id, case in report.get("cases", {}).items():
                if case.get("status") != "passed" or not case.get("methods"):
                    continue
                required = set(case["methods"]) & set(slots)
                if "<context>" in indices:
                    required.add("<context>")
                if all(assignment[name] == donor for name in required):
                    covered.add(case_id)
        conflicts = sum(assignment.get(a, 0) != assignment.get(b, 0)
                        for a, b in edges if a in indices and b in indices)
        return (-len(covered), conflicts, min(sum(bits), len(bits) - sum(bits)), bits)

    masks = sorted(itertools.product((0, 1), repeat=len(slots)), key=rank)
    ordered.extend(bits for bits in masks if bits not in explanations)
    seen = {original.dump(ast.parse(source)) for source in sources}
    results = []
    for bits in ordered:
        source = original.materialize(parsed, class_name, slots, bits)
        key = original.dump(ast.parse(source))
        if key in seen:
            continue
        seen.add(key)
        results.append({"source": source, "assignment": dict(zip(slots, bits)),
            "predictedPassingCases": -rank(bits)[0], "sourceSpace": "exclusive-helper-union-v1",
            "ranking": "contrasting-test-method-overlap-v1", "contrastWitness": explanations.get(bits)})
        if len(results) == limit:
            break
    return results
