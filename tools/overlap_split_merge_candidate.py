"""UNAPPROVED pure routing/prompt helpers; model experiments remain on hold.

Approval covers only this operator and its tests. The caller supplies one
verified raw-spec string and excludes gold/tests/reference material; no other
source, runtime service, model, or output cap is encoded here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

ARMS = ("E", "D", "O")
CONTRACT_LEDGER_FORMAT = "signature/API; input-output shape/type; state transition/invariants; units/scale"

@dataclass(frozen=True)
class ScopePlan:
    """Ordered scopes for independent calls A and B."""
    arm: str
    a_scope: tuple[str, ...]
    b_scope: tuple[str, ...]
    bridge: str | None
    fallback: bool = False
    overlap: bool = False

    @property
    def effective_policy(self) -> str:
        """Use E prompt policy for every small-n fallback, retaining arm metadata."""
        return "E" if self.fallback else self.arm

    @property
    def intersection(self) -> tuple[str, ...]:
        b_labels = set(self.b_scope)
        return tuple(label for label in self.a_scope if label in b_labels)

    def manifest(self) -> dict[str, object]:
        """Expose scope evidence for mechanical inspection only."""
        shared = self.intersection
        return {
            "arm": self.arm, "a_scope": self.a_scope, "b_scope": self.b_scope,
            "bridge": self.bridge, "intersection": shared,
            "a_exclusive": tuple(x for x in self.a_scope if x not in shared),
            "b_exclusive": tuple(x for x in self.b_scope if x not in shared),
            "fallback": self.fallback, "overlap": self.overlap,
        }

def _labels(stage_labels: Sequence[str]) -> tuple[str, ...]:
    if isinstance(stage_labels, (str, bytes)):
        raise TypeError("stage_labels must be an ordered sequence, not text")
    labels = tuple(stage_labels)
    if not labels:
        raise ValueError("stage_labels must contain at least one stage (n=0)")
    if any(not isinstance(x, str) for x in labels):
        raise TypeError("every stage label must be a string")
    if any(not x.strip() for x in labels) or len(set(labels)) != len(labels):
        raise ValueError("stage labels must be non-empty and unique")
    return labels

def _check_members(labels: tuple[str, ...], scope: tuple[str, ...], name: str) -> None:
    if len(scope) != len(set(scope)) or not set(scope).issubset(labels):
        raise ValueError(f"{name} must contain unique input stages")

def validate_scope_plan(stage_labels: Sequence[str], plan: ScopePlan) -> None:
    """Validate full coverage and exact E/D/O routing semantics."""
    labels = _labels(stage_labels)
    if not isinstance(plan, ScopePlan) or plan.arm not in ARMS:
        raise TypeError("plan must be a ScopePlan for arm E, D, or O")
    a, b = tuple(plan.a_scope), tuple(plan.b_scope)
    _check_members(labels, a, "a_scope")
    _check_members(labels, b, "b_scope")
    if set(a) | set(b) != set(labels):
        raise ValueError("A/B scopes do not cover every input stage")
    if len(labels) < 3:
        if (not plan.fallback) or plan.bridge is not None or plan.overlap:
            raise ValueError("n<3 plans must be whole-program fallback with no bridge")
        if a != labels or b != labels:
            raise ValueError("n<3 fallback assigns all stages to both calls")
        return
    k = len(labels) // 2
    if plan.fallback:
        raise ValueError("n>=3 plans cannot be fallback")
    if plan.arm == "E":
        if a != labels or b != labels or plan.bridge is not None or plan.overlap:
            raise ValueError("E must assign the whole program to both calls")
        return
    if plan.arm == "D":
        if a != labels[:k] or b != labels[k:] or plan.bridge is not None or plan.overlap:
            raise ValueError("D must use the disjoint deterministic cut")
        if set(a) & set(b):
            raise ValueError("D scopes must be disjoint")
        return
    bridge = labels[k]
    if a != labels[: k + 1] or b != labels[k:] or plan.bridge != bridge or not plan.overlap:
        raise ValueError("O must share exactly the deterministic bridge stage")
    shared = set(a) & set(b)
    if shared != {bridge}:
        raise ValueError("O must have exactly one shared bridge")
    if not (set(a) - {bridge}) or not (set(b) - {bridge}):
        raise ValueError("O needs exclusive internal stages on both sides")

def validate_scope_plans(stage_labels: Sequence[str], plans: Mapping[str, ScopePlan]) -> None:
    """Validate the complete three-arm plan set."""
    labels = _labels(stage_labels)
    if set(plans) != set(ARMS):
        raise ValueError("plans must contain exactly E, D, and O")
    for arm in ARMS:
        if plans[arm].arm != arm:
            raise ValueError(f"plan key {arm} does not match plan.arm {plans[arm].arm}")
        validate_scope_plan(labels, plans[arm])

def build_scope_plans(stage_labels: Sequence[str]) -> dict[str, ScopePlan]:
    """Create deterministic scopes; no favorable problem selection occurs."""
    labels = _labels(stage_labels)  # n=0 deliberately raises above.
    if len(labels) < 3:
        plans = {arm: ScopePlan(arm, labels, labels, None, True, False) for arm in ARMS}
    else:
        k = len(labels) // 2
        plans = {
            "E": ScopePlan("E", labels, labels, None),
            "D": ScopePlan("D", labels[:k], labels[k:], None),
            "O": ScopePlan("O", labels[: k + 1], labels[k:], labels[k], False, True),
        }
    validate_scope_plans(labels, plans)
    return plans

def _raw_spec(raw_spec: str) -> str:
    if not isinstance(raw_spec, str):
        raise TypeError("raw_spec must be a caller-verified string")
    if not raw_spec.strip():
        raise ValueError("raw_spec must not be empty")
    return raw_spec

def _independent_prompt(agent: str, spec: str, plan: ScopePlan, scope: tuple[str, ...]) -> str:
    return (
        f"Independent implementation call {agent}; arm={plan.effective_policy}.\n"
        "Use only the caller-verified raw specification and assigned ordered stages; "
        "do not seek peer output or hidden artifacts.\n"
        f"Raw specification:\n{spec}\nAssigned stages:\n{', '.join(scope)}\n"
        "Contract ledger format (identical for E, D, and O):\n"
        f"{CONTRACT_LEDGER_FORMAT}\n"
        "Return implementation plus ledger. Caller contract: this verified spec is "
        "the sole supplied source and excludes gold answers, reference code, and final tests."
    )

def build_independent_prompts(raw_spec: str, plan: ScopePlan) -> tuple[str, str]:
    """Build A/B prompts; neither accepts or includes the other output."""
    spec = _raw_spec(raw_spec)
    if not isinstance(plan, ScopePlan):
        raise TypeError("plan must be a ScopePlan")
    return (_independent_prompt("A", spec, plan, plan.a_scope),
            _independent_prompt("B", spec, plan, plan.b_scope))

def build_reconciliation_prompt(raw_spec: str, plan: ScopePlan, output_a: str, output_b: str) -> str:
    """Build the only prompt that receives both independent outputs."""
    spec = _raw_spec(raw_spec)
    if not isinstance(plan, ScopePlan):
        raise TypeError("plan must be a ScopePlan")
    if not isinstance(output_a, str) or not output_a.strip():
        raise ValueError("output_a must be non-empty text")
    if not isinstance(output_b, str) or not output_b.strip():
        raise ValueError("output_b must be non-empty text")
    return (
        f"Reconciliation call C; arm={plan.effective_policy}.\n"
        "Use the same caller-verified specification and ledger format to resolve "
        "contract contradictions into final executable whole-program code with "
        "coverage of all stages.\n"
        f"Raw specification:\n{spec}\n"
        "Contract ledger format (identical for E, D, and O):\n"
        f"{CONTRACT_LEDGER_FORMAT}\n"
        f"Candidate A output:\n---\n{output_a}\n---\n"
        f"Candidate B output:\n---\n{output_b}\n---\n"
        "Caller contract: the verified specification is the sole supplied source "
        "and excludes gold answers, reference code, and final tests."
    )
