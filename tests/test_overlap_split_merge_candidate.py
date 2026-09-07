"""Routing-only tests; toy labels are not performance evidence."""

from dataclasses import replace

import pytest

from tools.overlap_split_merge_candidate import (
    CONTRACT_LEDGER_FORMAT,
    build_independent_prompts,
    build_reconciliation_prompt,
    build_scope_plans,
    validate_scope_plan,
    validate_scope_plans,
)


def test_zero_stages_is_an_explicit_error():
    with pytest.raises(ValueError, match="n=0"):
        build_scope_plans([])


@pytest.mark.parametrize("count", [1, 2, 3, 4, 15])
def test_supported_sizes_cover_in_order_and_use_exact_fallback_or_cut(count):
    labels = tuple(f"s{i}" for i in range(count))
    plans = build_scope_plans(labels)
    validate_scope_plans(labels, plans)
    for plan in plans.values():
        assert set(plan.a_scope) | set(plan.b_scope) == set(labels)
    if count < 3:
        assert all(plan.fallback and plan.a_scope == labels == plan.b_scope for plan in plans.values())
        assert all(not plan.overlap for plan in plans.values())
    else:
        k = count // 2
        assert plans["D"].a_scope == labels[:k]
        assert plans["D"].b_scope == labels[k:]
        assert plans["D"].intersection == ()
        assert plans["O"].a_scope == labels[: k + 1]
        assert plans["O"].b_scope == labels[k:]
        assert plans["O"].intersection == (labels[k],)
        assert plans["O"].bridge == labels[k]
        assert plans["O"].overlap is True
        assert plans["D"].overlap is False


def test_validation_rejects_a_noncanonical_overlap():
    labels = tuple(f"s{i}" for i in range(4))
    plan = build_scope_plans(labels)["O"]
    bad = replace(plan, b_scope=labels[3:])
    with pytest.raises(ValueError, match="exactly the deterministic bridge"):
        validate_scope_plan(labels, bad)


def test_validation_rejects_plan_key_arm_mismatch():
    labels = ("s0", "s1", "s2")
    plans = build_scope_plans(labels)
    mismatched = dict(plans)
    mismatched["D"] = plans["E"]
    with pytest.raises(ValueError, match="does not match"):
        validate_scope_plans(labels, mismatched)


def test_manifest_exposes_bridge_and_both_exclusive_scopes():
    plan = build_scope_plans(tuple(f"s{i}" for i in range(15)))["O"]
    manifest = plan.manifest()
    assert manifest["intersection"] == ("s7",)
    assert manifest["a_exclusive"] and manifest["b_exclusive"]
    assert set(manifest["a_scope"]) | set(manifest["b_scope"]) == {f"s{i}" for i in range(15)}


def test_small_fallbacks_have_e_policy_and_byte_identical_arm_prompts():
    labels = ("s0", "s1")
    plans = build_scope_plans(labels)
    assert plans["D"].arm == "D" and plans["D"].effective_policy == "E"
    independent = {arm: build_independent_prompts("SPEC", plans[arm]) for arm in plans}
    assert independent["E"] == independent["D"] == independent["O"]
    reconciled = {
        arm: build_reconciliation_prompt("SPEC", plans[arm], "A", "B") for arm in plans
    }
    assert reconciled["E"] == reconciled["D"] == reconciled["O"]
    assert "arm=E" in independent["D"][0] and "arm=E" in reconciled["O"]


def test_independent_prompts_share_spec_and_ledger_without_peer_output():
    plan = build_scope_plans(("left", "bridge", "right"))["O"]
    spec = "caller-verified raw specification: unit contract"
    prompt_a, prompt_b = build_independent_prompts(spec, plan)
    assert prompt_a != prompt_b
    for prompt in (prompt_a, prompt_b):
        assert prompt.count(spec) == 1
        assert prompt.count(CONTRACT_LEDGER_FORMAT) == 1
        assert "Candidate A output" not in prompt
        assert "Candidate B output" not in prompt


def test_reconciliation_prompt_is_the_only_prompt_with_both_outputs():
    plan = build_scope_plans(("left", "bridge", "right"))["O"]
    spec, output_a, output_b = "SPEC_PAYLOAD_123", "A BODY", "B BODY"
    prompt = build_reconciliation_prompt(spec, plan, output_a, output_b)
    assert prompt.count(spec) == 1
    assert prompt.count(CONTRACT_LEDGER_FORMAT) == 1
    assert output_a in prompt and output_b in prompt
    assert "Candidate A output" in prompt and "Candidate B output" in prompt


def test_prompt_builders_reject_unverified_or_empty_text():
    plan = build_scope_plans(("s0", "s1", "s2"))["E"]
    with pytest.raises(TypeError):
        build_independent_prompts(42, plan)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        build_reconciliation_prompt("spec", plan, "", "B")
