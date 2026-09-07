"""Deterministic dependency-separator routing for the ClassEval tail candidate.

This module is intentionally pure: it parses the caller-supplied ordinary
source, builds a static ``self``/``cls`` call graph across the fixed ordered
cut, and returns a minimum vertex-cover overlap plan.  It never loads data,
tests, gold answers, a model, or an evaluator.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
from typing import Iterable

from tools import overlap_split_merge_candidate as scope_operator


@dataclass(frozen=True)
class SeparatorPlan:
    """A validated O plan, or an explicit E-style fallback."""

    labels: tuple[str, ...]
    a_scope: tuple[str, ...]
    b_scope: tuple[str, ...]
    shared: tuple[str, ...]
    cover: tuple[str, ...]
    cross_edges: tuple[tuple[str, str], ...]
    matching_size: int
    fallback: bool
    overlap: bool
    valid: bool
    reason: str
    arm: str = "O"

    @property
    def intersection(self) -> tuple[str, ...]:
        return self.shared

    @property
    def effective_policy(self) -> str:
        if self.fallback:
            return "E"
        return "O" if self.shared else "D"

    @property
    def bridge(self) -> tuple[str, ...] | str | None:
        """Compatibility metadata only; a separator may contain many methods."""

        if not self.shared:
            return None
        return self.shared[0] if len(self.shared) == 1 else self.shared

    @property
    def a_exclusive(self) -> tuple[str, ...]:
        shared = set(self.shared)
        return tuple(name for name in self.a_scope if name not in shared)

    @property
    def b_exclusive(self) -> tuple[str, ...]:
        shared = set(self.shared)
        return tuple(name for name in self.b_scope if name not in shared)

    def to_dict(self) -> dict:
        return {
            "arm": self.arm,
            "labels": list(self.labels),
            "scopeA": list(self.a_scope),
            "scopeB": list(self.b_scope),
            "shared": list(self.shared),
            "cover": list(self.cover),
            "crossEdges": [list(edge) for edge in self.cross_edges],
            "matchingSize": self.matching_size,
            "fallback": self.fallback,
            "overlap": self.overlap,
            "valid": self.valid,
            "reason": self.reason,
        }


def _ordered_union(labels: tuple[str, ...], *parts: Iterable[str]) -> tuple[str, ...]:
    wanted = set().union(*(set(part) for part in parts))
    return tuple(name for name in labels if name in wanted)


def _fallback(labels: tuple[str, ...], reason: str, edges: tuple[tuple[str, str], ...] = ()) -> SeparatorPlan:
    return SeparatorPlan(labels, labels, labels, (), (), edges, 0, True, False, False, reason)


def _class_methods(source: str, class_name: str) -> dict[str, ast.AST]:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            methods: dict[str, ast.AST] = {}
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if child.name in methods:
                        raise ValueError(f"duplicate method: {child.name}")
                    methods[child.name] = child
            return methods
    return {}


def direct_cross_edges(source: str, class_name: str, left: Iterable[str],
                       right: Iterable[str]) -> tuple[tuple[str, str], ...]:
    """Return unique left/right edges from direct ``self``/``cls`` calls.

    The result is ordered by the supplied method order and then callee order;
    syntactic direct ``self``/``cls`` calls (including nested method bodies)
    are included; dynamic dispatch forms remain outside this static relation.
    """

    methods = _class_methods(source, class_name)
    left_order, right_order = tuple(left), tuple(right)
    left_set, right_set = set(left_order), set(right_order)
    found: set[tuple[str, str]] = set()
    for caller in left_order:
        node = methods.get(caller)
        if node is None:
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Call) or not isinstance(child.func, ast.Attribute):
                continue
            value = child.func.value
            if not isinstance(value, ast.Name) or value.id not in {"self", "cls"}:
                continue
            callee = child.func.attr
            if caller in left_set and callee in right_set:
                found.add((caller, callee))
    for caller in right_order:
        node = methods.get(caller)
        if node is None:
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Call) or not isinstance(child.func, ast.Attribute):
                continue
            value = child.func.value
            if not isinstance(value, ast.Name) or value.id not in {"self", "cls"}:
                continue
            callee = child.func.attr
            if caller in right_set and callee in left_set:
                found.add((callee, caller))
    return tuple((caller, callee) for caller in left_order for callee in right_order
                 if (caller, callee) in found)


def minimum_vertex_cover(left: Iterable[str], right: Iterable[str],
                          edges: Iterable[tuple[str, str]]) -> tuple[tuple[str, ...], int]:
    """Compute a deterministic maximum matching and its Konig cover."""

    left_order, right_order = tuple(left), tuple(right)
    left_set, right_set = set(left_order), set(right_order)
    adjacency = {name: [] for name in left_order}
    seen_edges: set[tuple[str, str]] = set()
    for u, v in edges:
        if u not in left_set or v not in right_set or (u, v) in seen_edges:
            continue
        seen_edges.add((u, v))
        adjacency[u].append(v)

    pair_left: dict[str, str] = {}
    pair_right: dict[str, str] = {}

    def augment(u: str, seen: set[str]) -> bool:
        for v in adjacency[u]:
            if v in seen:
                continue
            seen.add(v)
            other = pair_right.get(v)
            if other is None or augment(other, seen):
                pair_left[u], pair_right[v] = v, u
                return True
        return False

    for u in left_order:
        augment(u, set())

    reachable_left = {u for u in left_order if u not in pair_left}
    reachable_right: set[str] = set()
    pending = list(reachable_left)
    while pending:
        u = pending.pop(0)
        for v in adjacency[u]:
            if pair_left.get(u) == v or v in reachable_right:
                continue
            reachable_right.add(v)
            matched_left = pair_right.get(v)
            if matched_left is not None and matched_left not in reachable_left:
                reachable_left.add(matched_left)
                pending.append(matched_left)
    cover_set = (set(left_order) - reachable_left) | reachable_right
    cover = tuple(name for name in (*left_order, *right_order) if name in cover_set)
    if len(cover) != len(pair_left):
        raise AssertionError("matching/cover invariant failed")
    return cover, len(pair_left)


def validate_separator_plan(plan: SeparatorPlan) -> None:
    """Check coverage, ordered scopes, and the nonempty exclusive sides."""

    labels = plan.labels
    if len(labels) != len(set(labels)):
        raise ValueError("separator labels must be unique")
    if tuple(name for name in labels if name in set(plan.a_scope)) != plan.a_scope:
        raise ValueError("A scope is not an ordered subset")
    if tuple(name for name in labels if name in set(plan.b_scope)) != plan.b_scope:
        raise ValueError("B scope is not an ordered subset")
    if set(plan.a_scope) | set(plan.b_scope) != set(labels):
        raise ValueError("scopes do not cover all stages")
    actual_shared = tuple(name for name in labels if name in set(plan.a_scope) & set(plan.b_scope))
    if not plan.fallback and actual_shared != plan.shared:
        raise ValueError("shared scope is not the exact intersection")
    if any(left not in plan.shared and right not in plan.shared for left, right in plan.cross_edges):
        raise ValueError("cross edge is not covered by the separator")
    if not plan.fallback and (not plan.a_exclusive or not plan.b_exclusive):
        raise ValueError("valid separator must retain both exclusive sides")
    if not plan.fallback and not plan.shared and plan.overlap:
        raise ValueError("empty separator cannot be marked overlapping")
    if plan.fallback and (plan.overlap or plan.shared or plan.cover):
        raise ValueError("fallback must be E-style and non-overlapping")


def build_separator_plan(source: str, class_name: str,
                         labels: Iterable[str]) -> SeparatorPlan:
    """Build O from the existing ordered D cut, or return common E fallback."""

    ordered = tuple(labels)
    if not ordered:
        raise ValueError("at least one stage label is required")
    if len(ordered) < 3:
        plan = _fallback(ordered, "small-n fallback")
        validate_separator_plan(plan)
        return plan
    try:
        methods = _class_methods(source, class_name)
        if any(name not in methods for name in ordered):
            raise ValueError("target method is absent from source")
        base_plans = scope_operator.build_scope_plans(ordered)
        d_plan = base_plans["D"]
        edges = direct_cross_edges(source, class_name, d_plan.a_scope, d_plan.b_scope)
        cover, matching_size = minimum_vertex_cover(d_plan.a_scope, d_plan.b_scope, edges)
        shared = tuple(name for name in ordered if name in set(cover))
        a_scope = _ordered_union(ordered, d_plan.a_scope, shared)
        b_scope = _ordered_union(ordered, d_plan.b_scope, shared)
        plan = SeparatorPlan(ordered, a_scope, b_scope, shared, cover, edges,
                             matching_size, False, bool(shared), True,
                             "minimum vertex cover")
        validate_separator_plan(plan)
        return plan
    except (SyntaxError, ValueError, TypeError, KeyError, IndexError, AssertionError) as exc:
        plan = _fallback(ordered, f"static separator fallback: {type(exc).__name__}")
        validate_separator_plan(plan)
        return plan


def method_body_shas(source: str, class_name: str, methods: Iterable[str],
                     valid: bool = True) -> dict[str, str | None]:
    """Hash present method bodies for provenance; equality is not causal proof."""

    names = tuple(methods)
    if not valid:
        return {name: None for name in names}
    try:
        definitions = _class_methods(source, class_name)
    except (SyntaxError, ValueError, TypeError):
        return {name: None for name in names}
    result: dict[str, str | None] = {}
    for name in names:
        node = definitions.get(name)
        if node is None:
            result[name] = None
            continue
        body = ast.Module(body=list(getattr(node, "body", ())), type_ignores=[])
        result[name] = hashlib.sha256(
            ast.dump(body, include_attributes=False).encode()).hexdigest()
    return result
