"""Executable crossover inside methods, aligned by common AST subtrees.

Both policies use the same source space. Overlap ranks observed test-support
constraints; only the unchanged external evaluator may declare a program solved.
"""
from __future__ import annotations

import ast
import copy
from dataclasses import dataclass
import difflib
import hashlib
import itertools
import random

from tools import classeval_source_overlap as original
from tools.classeval_source_overlap_union import enrich


@dataclass
class Choice:
    a: object
    b: object
    owner: str
    index: int = -1


@dataclass
class Node:
    original: ast.AST
    fields: dict


@dataclass
class Sequence:
    parts: list


def identity(value):
    return original.dump(value) if isinstance(value, ast.AST) else repr(value)


def align(a, b, owner):
    if identity(a) == identity(b):
        return a
    if isinstance(a, ast.AST) and type(a) is type(b):
        return Node(a, {name: align(value, getattr(b, name), owner)
                        for name, value in ast.iter_fields(a)})
    if isinstance(a, list) and isinstance(b, list):
        parts = []
        matcher = difflib.SequenceMatcher(None, [identity(x) for x in a],
                                         [identity(x) for x in b], autojunk=False)
        for operation, a0, a1, b0, b1 in matcher.get_opcodes():
            if operation == "equal":
                parts.append(a[a0:a1])
            elif operation == "replace" and a1 - a0 == b1 - b0:
                parts.append([align(x, y, owner) for x, y in zip(a[a0:a1], b[b0:b1])])
            else:
                parts.append(Choice(a[a0:a1], b[b0:b1], owner))
        return Sequence(parts)
    return Choice(a, b, owner)


def choices(plan):
    if isinstance(plan, Choice):
        return [plan]
    if isinstance(plan, Node):
        return [c for value in plan.fields.values() for c in choices(value)]
    if isinstance(plan, Sequence):
        return [c for part in plan.parts for c in choices(part)]
    if isinstance(plan, list):
        return [c for part in plan for c in choices(part)]
    return []


def render(plan, bits):
    if isinstance(plan, Choice):
        return copy.deepcopy(plan.b if bits[plan.index] else plan.a)
    if isinstance(plan, Node):
        result = copy.copy(plan.original)
        for name, value in plan.fields.items():
            setattr(result, name, render(value, bits))
        return result
    if isinstance(plan, Sequence):
        return [item for part in plan.parts for item in render(part, bits)]
    if isinstance(plan, list):
        return [render(item, bits) for item in plan]
    return copy.deepcopy(plan)


def source_space(sources, class_name, max_slots=14):
    parsed = [original.parse(source, class_name) for source in enrich(sources, class_name)]
    names = sorted(parsed[0][2])
    plans = {name: align(parsed[0][2][name], parsed[1][2][name], name) for name in names}
    context = Choice(0, 1, "<context>") if parsed[0][3] != parsed[1][3] else 0
    # Coarsen the most fragmented methods first under the shared fixed bound.
    # Never truncate a method or remove a benchmark task to fit the search.
    for name in sorted(names, key=lambda n: (-len(choices(plans[n])), n)):
        count = len(choices(context)) + sum(len(choices(p)) for p in plans.values())
        if count <= max_slots:
            break
        if len(choices(plans[name])) > 1:
            plans[name] = Choice(parsed[0][2][name], parsed[1][2][name], name)
    slots = choices(context) + [c for plan in plans.values() for c in choices(plan)]
    if len(slots) > max_slots:
        raise ValueError("more than14 differing slots after common-anchor coarsening")
    for index, slot in enumerate(slots):
        slot.index = index
    return parsed, plans, context, slots


def materialize(parsed, plans, context, class_name, bits):
    tree = copy.deepcopy(parsed[render(context, bits)][0])
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    cls.body = [render(plans[n.name], bits) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                else n for n in cls.body]
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + "\n"


def proposals(sources, class_name, feedback, policy, seed, limit=16):
    if policy not in {"generic", "overlap"} or len(sources) != 2 or len(feedback) != 2:
        raise ValueError("invalid source-composition request")
    if limit < 1:
        return []
    parsed, plans, context, slots = source_space(sources, class_name)
    owners = {name: sum(1 << c.index for c in slots if c.owner == name)
              for name in ["<context>", *plans]}
    support = []
    for donor, report in enumerate(feedback):
        for case_id, case in report.get("cases", {}).items():
            if case.get("status") != "passed" or not case.get("methods"):
                continue
            required = owners["<context>"]
            for method in case["methods"]:
                required |= owners.get(method, 0)
            support.append((case_id, donor, required))
    edges = original.field_edges(parsed, list(plans))
    masks = list(itertools.product((0, 1), repeat=len(slots)))

    def rank(bits):
        mask = sum(bit << index for index, bit in enumerate(bits))
        covered = {case_id for case_id, donor, required in support
                   if mask & required == (required if donor else 0)}
        conflicts = sum(bool(mask & (owners[a] | owners[b])) and
                        bool((~mask) & (owners[a] | owners[b])) for a, b in edges)
        return (-len(covered), conflicts, min(sum(bits), len(bits) - sum(bits)), bits)

    if policy == "generic":
        random.Random(int(hashlib.sha256(seed.encode()).hexdigest(), 16)).shuffle(masks)
    else:
        masks.sort(key=rank)
    result, seen = [], {original.dump(ast.parse(source)) for source in sources}
    for bits in masks:
        try:
            source = materialize(parsed, plans, context, class_name, bits)
            key = original.dump(ast.parse(source))
        except (SyntaxError, ValueError, TypeError, IndexError):
            # A syntactically invalid mixture has no executable candidate.
            continue
        if key in seen:
            continue
        seen.add(key)
        result.append({"source": source, "assignment": {
            f"{slot.owner}:{slot.index}": bits[slot.index] for slot in slots},
            "predictedPassingCases": -rank(bits)[0], "sourceSpace": "common-subtree-overlap-v1"})
        if len(result) == limit:
            break
    return result
