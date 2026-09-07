"""Executable method-source mixtures ranked by overlapping observed test support.

No benchmark references or test bodies enter this operator. It consumes two
candidate sources and observed per-test statuses/method traces only.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import itertools
import random


def dump(node: ast.AST) -> str:
    return ast.dump(node, include_attributes=False)


def parse(source: str, class_name: str):
    tree = ast.parse(source)
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name]
    if len(classes) != 1:
        raise ValueError("expected one target class")
    cls = classes[0]
    methods = {n.name: n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    if len(methods) != sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in cls.body):
        raise ValueError("duplicate method definitions")
    context = copy.deepcopy(tree)
    target = next(n for n in context.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    target.body = [n for n in target.body if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return tree, cls, methods, dump(context)


def source_space(sources: list[str], class_name: str):
    parsed = [parse(s, class_name) for s in sources]
    if set(parsed[0][2]) != set(parsed[1][2]):
        raise ValueError("different method inventories")
    names = sorted(parsed[0][2])
    differing = [n for n in names if dump(parsed[0][2][n]) != dump(parsed[1][2][n])]
    context_differs = parsed[0][3] != parsed[1][3]
    slots = (["<context>"] if context_differs else []) + differing
    if len(slots) > 14:
        raise ValueError("more than14 differing slots")
    return parsed, names, slots


def materialize(parsed, class_name: str, slots: list[str], bits: tuple[int, ...]) -> str:
    assignment = dict(zip(slots, bits))
    base = assignment.get("<context>", 0)
    tree = copy.deepcopy(parsed[base][0])
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    cls.body = [copy.deepcopy(parsed[assignment.get(n.name, 0)][2][n.name])
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) else n for n in cls.body]
    return ast.unparse(ast.fix_missing_locations(tree)) + "\n"


def field_edges(parsed, names: list[str]) -> set[tuple[str, str]]:
    attributes = {name: set() for name in names}
    for _, _, methods, _ in parsed:
        for name, method in methods.items():
            attributes[name].update(n.attr for n in ast.walk(method)
                if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "self")
    return {(left, right) for left, right in itertools.combinations(names, 2)
            if attributes[left] & attributes[right]}


def proposals(sources: list[str], class_name: str, feedback: list[dict],
              policy: str, seed: str, limit: int = 16) -> list[dict]:
    if policy not in {"generic", "overlap"} or len(sources) != 2 or len(feedback) != 2:
        raise ValueError("invalid source-composition request")
    parsed, names, slots = source_space(sources, class_name)
    if not slots:
        return []
    edges = field_edges(parsed, names)
    masks = list(itertools.product((0, 1), repeat=len(slots)))
    # Exact parents remain available to every selector, without spending a
    # new evaluation on a syntactically equivalent copy.
    masks = [b for b in masks if any(b) and not all(b)]

    def prediction(bits):
        assignment = dict(zip(slots, bits))
        covered = set()
        for donor, report in enumerate(feedback):
            for case_id, case in report.get("cases", {}).items():
                if case.get("status") != "passed" or not case.get("methods"):
                    continue
                required = set(case["methods"]) & set(slots)
                if "<context>" in slots:
                    required.add("<context>")
                if all(assignment[n] == donor for n in required):
                    covered.add(case_id)
        conflicts = sum(assignment.get(a, 0) != assignment.get(b, 0)
                        for a, b in edges if a in slots and b in slots)
        return (-len(covered), conflicts, min(sum(bits), len(bits) - sum(bits)), bits)

    if policy == "generic":
        random.Random(int(hashlib.sha256(seed.encode()).hexdigest(), 16)).shuffle(masks)
    else:
        masks.sort(key=prediction)
    result, seen = [], {dump(ast.parse(s)) for s in sources}
    for bits in masks:
        code = materialize(parsed, class_name, slots, bits)
        identity = dump(ast.parse(code))
        if identity in seen:
            continue
        seen.add(identity)
        result.append({"source": code, "assignment": dict(zip(slots, bits)),
                       "predictedPassingCases": -prediction(bits)[0]})
        if len(result) == limit:
            break
    return result
