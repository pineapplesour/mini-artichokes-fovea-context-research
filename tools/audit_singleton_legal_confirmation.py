#!/usr/bin/env python3
"""Read-only cost/fairness and domain-NI audit for the legal confirmation run.

This module is intentionally downstream of the singleton runner and scorer.
It never starts a model process and never writes an artifact.  A phase-A
contract fixes the cost arithmetic and the domain noninferiority rule.  A
separately hash-pinned, gold-free evidence file fixes deployable-arm call
attribution and the SC-prefix selection before private gold is opened.

The auditor then revalidates the complete runner tree, rebuilds the score
report with the frozen scorer, and derives claim eligibility.  Missing cost
units, hidden physical calls, incomplete ledgers, rounded-window decisions,
an absent NI margin, or a score/runner mismatch all fail closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import subprocess
import sys
from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import run_singleton_legal_campaign as runner  # noqa: E402
from tools import score_singleton_legal_campaign as scorer  # noqa: E402


PROTOCOL = "singleton-legal-confirmation-fairness-audit-v1"
CONTRACT_PROTOCOL = "singleton-legal-confirmation-fairness-contract-v1"
EVIDENCE_PROTOCOL = "singleton-legal-confirmation-gold-free-cost-evidence-v1"
CONTRACT_STATUS = "FROZEN_BEFORE_ANY_FRESH_SOLVER_CALL"
EVIDENCE_STATUS = "FROZEN_AFTER_GOLD_FREE_OUTPUTS_BEFORE_GOLD_OPEN"

CANDIDATE = scorer.PRIMARY_CANDIDATE
PRIMARY_COMPARATORS = scorer.PRIMARY_COMPARATORS
PRIMARY_ARMS = (CANDIDATE, *PRIMARY_COMPARATORS)
SC_PREFIXES = tuple(f"SC-{index}" for index in range(1, 9))
REQUIRED_COST_ARMS = PRIMARY_ARMS + tuple(
    arm for arm in SC_PREFIXES if arm not in PRIMARY_ARMS
)
PRIMARY_RESPONSE_CAPS = {
    "Mini-4": 4,
    "Plain-Luna-1": 1,
    "Structured-Direct-1": 1,
    "SC-4": 4,
    "Bo3+J": 4,
    "CR-4": 4,
    "task-adapted-ICR-4": 4,
    "answer-only-veto-4": 4,
}
PRIMARY_RESPONSE_MINIMUMS = {
    "Mini-4": 3,
    "Plain-Luna-1": 1,
    "Structured-Direct-1": 1,
    "SC-4": 4,
    "Bo3+J": 4,
    "CR-4": 4,
    "task-adapted-ICR-4": 4,
    "answer-only-veto-4": 3,
}

COST_FORMULA = (
    "uncachedInputWeight*(inputTokens-cachedInputTokens)"
    "+cachedInputWeight*cachedInputTokens+outputWeight*outputTokens"
)
COST_ARITHMETIC = "exact_finite_decimal_to_rational_no_rounding_v1"
SC_SELECTOR = "minimum_exact_abs_log_cost_ratio_equivalent_distortion_tie_smaller_k_v1"
CRITICAL_PATH_METHOD = "per_case_longest_attributed_dependency_path_sum_milliseconds_v1"
NI_INTERVAL_METHOD = (
    "paired_nonparametric_within_four_fixed_cells_empirical_alpha_quantile_v1"
)
NI_RULE = "strict_lower_bound_greater_than_negative_common_margin_v1"
WEIGHT_SOURCE_KIND = "frozen_token_equivalent_weights"
SELECTION_SCOPE = "exposed_development_only_before_fresh_calls"

MATCH_LOWER = Decimal("0.80")
MATCH_UPPER = Decimal("1.25")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
ARM_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9+._:-]{0,127}\Z")

CONTRACT_KEYS = {
    "schemaVersion",
    "protocol",
    "status",
    "campaignId",
    "candidateArm",
    "primaryComparatorArms",
    "requiredCostArms",
    "supplementaryCostArms",
    "costPolicy",
    "domainNoninferiority",
    "implementation",
    "selfHash",
}
COST_POLICY_KEYS = {
    "matchingLowerBound",
    "matchingUpperBound",
    "arithmetic",
    "roundingTolerance",
    "formula",
    "criticalPathMethod",
    "scPrefixSelector",
    "costWeights",
    "weightSource",
    "attributionPolicySource",
    "stageTokenLimits",
}
COST_WEIGHT_KEYS = {
    "uncachedInputWeight",
    "cachedInputWeight",
    "outputWeight",
}
WEIGHT_SOURCE_KEYS = {"kind", "version", "path", "sha256"}
WEIGHT_SOURCE_DOCUMENT_KEYS = {
    "schemaVersion",
    "kind",
    "version",
    "costWeights",
    "rationale",
    "selfHash",
}
ATTRIBUTION_POLICY_SOURCE_KEYS = {"version", "path", "sha256"}
ATTRIBUTION_POLICY_DOCUMENT_KEYS = {
    "schemaVersion",
    "protocol",
    "version",
    "primaryResponseMinimums",
    "primaryResponseCaps",
    "scPrefixRule",
    "miniCallRule",
    "answerOnlyVetoCallRule",
    "sharedCallChargingRule",
    "selfHash",
}
ATTRIBUTION_POLICY_PROTOCOL = "singleton-legal-physical-call-attribution-policy-v1"
SC_PREFIX_RULE = "SC-k is exact nested physical DRAW_D1..DRAW_Dk prefix"
MINI_CALL_RULE = "DRAW_D1+DRAW_D2+DRAW_D3+conditional_BLIND_CERT_on_answer_conflict"
AOV_CALL_RULE = "DRAW_D1+DRAW_D2+DRAW_D3+same_conditional_BLIND_CERT_inventory_as_Mini"
SHARED_CHARGING_RULE = "physical_call_counted_once_in_full_per_deployable_arm"
STAGE_TOKEN_LIMIT_KEYS = {"maxOutputTokens", "maxTotalTokens"}
NI_KEYS = {
    "margin",
    "rationale",
    "rationaleEvidencePath",
    "rationaleEvidenceSha256",
    "selectionEvidenceScope",
    "alpha",
    "confidenceLevel",
    "intervalMethod",
    "bootstrapSeed",
    "bootstrapReplicates",
    "numericalTolerance",
    "rule",
}
NI_RATIONALE_DOCUMENT_KEYS = {
    "schemaVersion",
    "margin",
    "rationale",
    "selectionEvidenceScope",
    "selfHash",
}
IMPLEMENTATION_KEYS = {"auditorSha256", "runnerSha256", "scorerSha256"}

EVIDENCE_KEYS = {
    "schemaVersion",
    "protocol",
    "status",
    "campaignId",
    "contractPath",
    "contractFileSha256",
    "contractSelfHash",
    "runnerCampaign",
    "armAttribution",
    "claimedSelectedScPrefix",
    "selfHash",
}
RUNNER_BINDING_KEYS = {
    "unitManifestPath",
    "unitManifestFileSha256",
    "schedulePath",
    "scheduleFileSha256",
    "campaignGitCommit",
    "outputDirectory",
    "campaignReceiptFileSha256",
    "campaignReceiptSha256",
    "scientificPredictionsFileSha256",
}
ARM_ATTRIBUTION_KEYS = {"arm", "cases"}
CASE_ATTRIBUTION_KEYS = {"id", "unitIds"}


class ConfirmationAuditError(RuntimeError):
    """A frozen input, ledger, statistic, or claim gate failed closed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConfirmationAuditError(message)


def canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ConfirmationAuditError("value is not canonical JSON") from error


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _strict_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ConfirmationAuditError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_json_constant(value: str) -> None:
    raise ConfirmationAuditError(f"non-finite JSON constant: {value}")


def _read_regular_bytes(path: Path, expected_sha256: str, *, label: str) -> bytes:
    _sha256(expected_sha256, label=f"expected {label} hash")
    try:
        _require(not path.is_symlink(), f"{label} must not be a symlink")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as error:
        raise ConfirmationAuditError(f"cannot open regular {label}") from error
    try:
        metadata = os.fstat(descriptor)
        _require(stat.S_ISREG(metadata.st_mode), f"{label} must be a regular file")
        blocks: list[bytes] = []
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            blocks.append(block)
    finally:
        os.close(descriptor)
    raw = b"".join(blocks)
    _require(hashlib.sha256(raw).hexdigest() == expected_sha256, f"{label} file hash mismatch")
    return raw


def _exact_keys(value: Mapping[str, Any], expected: set[str], *, label: str) -> None:
    _require(set(value) == expected, f"{label} schema mismatch")


def _sha256(value: Any, *, label: str) -> str:
    _require(
        isinstance(value, str) and SHA256_RE.fullmatch(value) is not None,
        f"{label} must be a lowercase SHA-256",
    )
    return value


def _verify_self_hash(value: Mapping[str, Any], field: str, *, label: str) -> str:
    claimed = _sha256(value.get(field), label=f"{label} {field}")
    observed = canonical_digest({key: item for key, item in value.items() if key != field})
    _require(claimed == observed, f"{label} self-hash mismatch")
    return claimed


def _regular_file(path: Path, expected_sha256: str, *, label: str) -> Path:
    _read_regular_bytes(path, expected_sha256, label=label)
    return path.resolve()


def _load_json(path: Path, expected_sha256: str, *, label: str) -> dict[str, Any]:
    raw = _read_regular_bytes(path, expected_sha256, label=label)
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_strict_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConfirmationAuditError(f"invalid {label} JSON") from error
    _require(isinstance(value, dict), f"{label} must be an object")
    return value


def _safe_bound_file(root: Path, raw: Any, expected_sha256: str, *, label: str) -> Path:
    _require(isinstance(raw, str) and bool(raw), f"{label} path must be nonempty")
    relative = Path(raw)
    _require(not relative.is_absolute(), f"{label} path must be relative")
    _require(relative.as_posix() == raw, f"{label} path must use normalized POSIX form")
    _require(".." not in relative.parts and "." not in relative.parts, f"{label} path is unsafe")
    unresolved = root / relative
    _require(not unresolved.is_symlink(), f"{label} path must not be a symlink")
    try:
        resolved = unresolved.resolve(strict=True)
        resolved.relative_to(root.resolve())
    except (OSError, ValueError) as error:
        raise ConfirmationAuditError(f"{label} path escapes its frozen root") from error
    return _regular_file(resolved, expected_sha256, label=label)


def _safe_bound_directory(root: Path, raw: Any, *, label: str) -> Path:
    _require(isinstance(raw, str) and bool(raw), f"{label} path must be nonempty")
    relative = Path(raw)
    _require(not relative.is_absolute(), f"{label} path must be relative")
    _require(relative.as_posix() == raw, f"{label} path must use normalized POSIX form")
    _require(".." not in relative.parts and "." not in relative.parts, f"{label} path is unsafe")
    unresolved = root / relative
    try:
        resolved = unresolved.resolve(strict=True)
        resolved.relative_to(root.resolve())
    except (OSError, ValueError) as error:
        raise ConfirmationAuditError(f"{label} path escapes its frozen root") from error
    _require(not unresolved.is_symlink() and resolved.is_dir(), f"{label} must be a directory")
    return resolved


def verify_freeze_chronology(
    *,
    phase_a_commit: str,
    cost_evidence_path: Path,
    expected_pre_gold_cost_git_commit: str,
    score_manifest_path: Path,
    expected_score_freeze_git_commit: str,
) -> dict[str, str]:
    """Prove phase-A -> gold-free-cost -> score-freeze Git ancestry and bytes."""

    commits = (
        phase_a_commit,
        expected_pre_gold_cost_git_commit,
        expected_score_freeze_git_commit,
    )
    _require(
        all(isinstance(commit, str) and runner.HEX40.fullmatch(commit) for commit in commits),
        "freeze chronology Git commit format",
    )
    _require(
        len(set(commits)) == 3,
        "phase-A, pre-gold cost, and score-freeze commits must be distinct",
    )
    try:
        roots = {
            Path(
                subprocess.run(
                    ["git", "-C", str(path.parent), "rev-parse", "--show-toplevel"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                ).stdout.decode("utf-8").strip()
            ).resolve()
            for path in (cost_evidence_path, score_manifest_path)
        }
    except (OSError, UnicodeDecodeError, subprocess.CalledProcessError) as error:
        raise ConfirmationAuditError("freeze chronology repository discovery failed") from error
    _require(len(roots) == 1, "freeze chronology artifacts are in different repositories")
    root = roots.pop()

    def relative(path: Path) -> str:
        try:
            return path.resolve(strict=True).relative_to(root).as_posix()
        except (OSError, ValueError) as error:
            raise ConfirmationAuditError("freeze chronology artifact escapes repository") from error

    for commit, path, label in (
        (
            expected_pre_gold_cost_git_commit,
            cost_evidence_path,
            "gold-free cost evidence",
        ),
        (expected_score_freeze_git_commit, score_manifest_path, "score manifest"),
    ):
        try:
            anchored = subprocess.run(
                ["git", "-C", str(root), "show", f"{commit}:{relative(path)}"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            ).stdout
        except subprocess.CalledProcessError as error:
            raise ConfirmationAuditError(f"{label} is absent from its claimed Git freeze") from error
        live = _read_regular_bytes(path, sha256_file(path), label=label)
        _require(anchored == live, f"live {label} differs from its Git freeze")

    for older, newer, label in (
        (phase_a_commit, expected_pre_gold_cost_git_commit, "phase-A to pre-gold cost"),
        (
            expected_pre_gold_cost_git_commit,
            expected_score_freeze_git_commit,
            "pre-gold cost to score freeze",
        ),
    ):
        ancestry = subprocess.run(
            ["git", "-C", str(root), "merge-base", "--is-ancestor", older, newer],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=False,
        )
        _require(ancestry.returncode == 0, f"freeze chronology ancestry failed: {label}")
    return {
        "repositoryRoot": str(root),
        "phaseACommit": phase_a_commit,
        "preGoldCostCommit": expected_pre_gold_cost_git_commit,
        "scoreFreezeCommit": expected_score_freeze_git_commit,
    }


def _decimal_string(value: Any, *, label: str, positive: bool = False) -> Decimal:
    _require(isinstance(value, str) and bool(value), f"{label} must be a decimal string")
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise ConfirmationAuditError(f"{label} is not a finite decimal") from error
    _require(parsed.is_finite(), f"{label} is not finite")
    _require(parsed > 0 if positive else parsed >= 0, f"{label} has an invalid sign")
    _require(value == _finite_decimal(parsed), f"{label} is not canonical decimal text")
    return parsed


def _finite_decimal(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in {"", "-0"}:
        return "0"
    return text


def _finite_fraction_decimal(value: Fraction) -> str:
    denominator = value.denominator
    while denominator % 2 == 0:
        denominator //= 2
    while denominator % 5 == 0:
        denominator //= 5
    _require(denominator == 1, "attributed cost is not a finite decimal")
    required_precision = (
        len(str(abs(value.numerator))) + len(str(value.denominator)) + 8
    )
    with localcontext() as context:
        context.prec = required_precision
        decimal = Decimal(value.numerator) / Decimal(value.denominator)
    return _finite_decimal(decimal)


def _fraction_text(value: Fraction) -> dict[str, str]:
    return {"numerator": str(value.numerator), "denominator": str(value.denominator)}


def _ratio_display(value: Fraction) -> str:
    with localcontext() as context:
        context.prec = 24
        decimal = Decimal(value.numerator) / Decimal(value.denominator)
    return format(decimal, ".18g")


def _load_contract(path: Path, expected_sha256: str) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    path = _regular_file(path, expected_sha256, label="fairness contract")
    contract = _load_json(path, expected_sha256, label="fairness contract")
    _exact_keys(contract, CONTRACT_KEYS, label="fairness contract")
    _verify_self_hash(contract, "selfHash", label="fairness contract")
    _require(
        contract["schemaVersion"] == 1
        and contract["protocol"] == CONTRACT_PROTOCOL
        and contract["status"] == CONTRACT_STATUS,
        "fairness contract identity mismatch",
    )
    _require(isinstance(contract["campaignId"], str) and bool(contract["campaignId"]), "contract campaignId")
    _require(contract["candidateArm"] == CANDIDATE, "contract candidate is not Mini-4")
    _require(
        contract["primaryComparatorArms"] == list(PRIMARY_COMPARATORS),
        "contract primary comparator order mismatch",
    )
    _require(
        contract["requiredCostArms"] == list(REQUIRED_COST_ARMS),
        "contract required cost-arm order mismatch",
    )
    supplementary = contract["supplementaryCostArms"]
    _require(
        isinstance(supplementary, list)
        and all(isinstance(arm, str) and ARM_RE.fullmatch(arm) is not None for arm in supplementary)
        and len(supplementary) == len(set(supplementary))
        and not (set(supplementary) & set(REQUIRED_COST_ARMS)),
        "contract supplementary cost arms are invalid",
    )

    cost = contract["costPolicy"]
    _require(isinstance(cost, dict), "costPolicy must be an object")
    _exact_keys(cost, COST_POLICY_KEYS, label="costPolicy")
    _require(
        cost["matchingLowerBound"] == "0.80"
        and cost["matchingUpperBound"] == "1.25"
        and cost["arithmetic"] == COST_ARITHMETIC
        and cost["roundingTolerance"] == "0"
        and cost["formula"] == COST_FORMULA
        and cost["criticalPathMethod"] == CRITICAL_PATH_METHOD
        and cost["scPrefixSelector"] == SC_SELECTOR,
        "costPolicy fixed arithmetic/window mismatch",
    )
    weights = cost["costWeights"]
    _require(isinstance(weights, dict), "costWeights must be an object")
    _exact_keys(weights, COST_WEIGHT_KEYS, label="costWeights")
    parsed_weight_decimals = {
        "uncachedInputWeight": _decimal_string(
            weights["uncachedInputWeight"], label="uncachedInputWeight", positive=True
        ),
        "cachedInputWeight": _decimal_string(
            weights["cachedInputWeight"], label="cachedInputWeight"
        ),
        "outputWeight": _decimal_string(
            weights["outputWeight"], label="outputWeight", positive=True
        ),
    }
    parsed_weights = {
        key: Fraction(value) for key, value in parsed_weight_decimals.items()
    }
    source = cost["weightSource"]
    _require(isinstance(source, dict), "weightSource must be an object")
    _exact_keys(source, WEIGHT_SOURCE_KEYS, label="weightSource")
    _require(
        source["kind"] == WEIGHT_SOURCE_KIND
        and isinstance(source["version"], str)
        and bool(source["version"]),
        "weightSource identity mismatch",
    )
    source_path = _safe_bound_file(
        path.parent, source["path"], source["sha256"], label="weight source"
    )
    source_document = _load_json(source_path, source["sha256"], label="weight source")
    _exact_keys(source_document, WEIGHT_SOURCE_DOCUMENT_KEYS, label="weight source")
    _verify_self_hash(source_document, "selfHash", label="weight source")
    _require(
        source_document["schemaVersion"] == 1
        and source_document["kind"] == source["kind"]
        and source_document["version"] == source["version"]
        and source_document["costWeights"] == weights
        and isinstance(source_document["rationale"], str)
        and bool(source_document["rationale"].strip()),
        "weight source does not attest the embedded cost weights",
    )
    attribution_source = cost["attributionPolicySource"]
    _require(isinstance(attribution_source, dict), "attributionPolicySource must be an object")
    _exact_keys(
        attribution_source,
        ATTRIBUTION_POLICY_SOURCE_KEYS,
        label="attributionPolicySource",
    )
    _require(
        isinstance(attribution_source["version"], str)
        and bool(attribution_source["version"]),
        "attributionPolicySource version",
    )
    attribution_policy_path = _safe_bound_file(
        path.parent,
        attribution_source["path"],
        attribution_source["sha256"],
        label="attribution policy source",
    )
    attribution_document = _load_json(
        attribution_policy_path,
        attribution_source["sha256"],
        label="attribution policy source",
    )
    _exact_keys(
        attribution_document,
        ATTRIBUTION_POLICY_DOCUMENT_KEYS,
        label="attribution policy source",
    )
    _verify_self_hash(
        attribution_document,
        "selfHash",
        label="attribution policy source",
    )
    _require(
        attribution_document["schemaVersion"] == 1
        and attribution_document["protocol"] == ATTRIBUTION_POLICY_PROTOCOL
        and attribution_document["version"] == attribution_source["version"]
        and attribution_document["primaryResponseMinimums"]
        == PRIMARY_RESPONSE_MINIMUMS
        and attribution_document["primaryResponseCaps"] == PRIMARY_RESPONSE_CAPS
        and attribution_document["scPrefixRule"] == SC_PREFIX_RULE
        and attribution_document["miniCallRule"] == MINI_CALL_RULE
        and attribution_document["answerOnlyVetoCallRule"] == AOV_CALL_RULE
        and attribution_document["sharedCallChargingRule"] == SHARED_CHARGING_RULE,
        "attribution policy source does not attest the frozen call rules",
    )
    stage_limits = cost["stageTokenLimits"]
    _require(isinstance(stage_limits, dict) and bool(stage_limits), "stageTokenLimits must be a nonempty object")
    for stage_id, limits in stage_limits.items():
        _require(
            isinstance(stage_id, str)
            and runner.ID_RE.fullmatch(stage_id) is not None
            and isinstance(limits, dict),
            "stageTokenLimits stage/schema",
        )
        _exact_keys(limits, STAGE_TOKEN_LIMIT_KEYS, label=f"stageTokenLimits.{stage_id}")
        _require(
            type(limits["maxOutputTokens"]) is int
            and limits["maxOutputTokens"] > 0
            and type(limits["maxTotalTokens"]) is int
            and limits["maxTotalTokens"] >= limits["maxOutputTokens"],
            f"stageTokenLimits.{stage_id} values",
        )

    ni = contract["domainNoninferiority"]
    _require(isinstance(ni, dict), "domainNoninferiority must be an object")
    _exact_keys(ni, NI_KEYS, label="domainNoninferiority")
    margin = _decimal_string(ni["margin"], label="domain NI margin", positive=True)
    _require(margin < 1, "domain NI margin must be below one")
    _require(
        isinstance(ni["rationale"], str)
        and bool(ni["rationale"].strip())
        and ni["selectionEvidenceScope"] == SELECTION_SCOPE
        and ni["alpha"] == "0.05"
        and ni["confidenceLevel"] == "0.95"
        and ni["intervalMethod"] == NI_INTERVAL_METHOD
        and isinstance(ni["bootstrapSeed"], str)
        and bool(ni["bootstrapSeed"])
        and type(ni["bootstrapReplicates"]) is int
        and ni["bootstrapReplicates"] >= 99
        and ni["numericalTolerance"] == "0"
        and ni["rule"] == NI_RULE,
        "domain NI rule is incomplete or not phase-A fixed",
    )
    rationale_path = _safe_bound_file(
        path.parent,
        ni["rationaleEvidencePath"],
        ni["rationaleEvidenceSha256"],
        label="domain NI rationale evidence",
    )
    rationale_document = _load_json(
        rationale_path,
        ni["rationaleEvidenceSha256"],
        label="domain NI rationale evidence",
    )
    _exact_keys(
        rationale_document,
        NI_RATIONALE_DOCUMENT_KEYS,
        label="domain NI rationale evidence",
    )
    _verify_self_hash(
        rationale_document,
        "selfHash",
        label="domain NI rationale evidence",
    )
    _require(
        rationale_document["schemaVersion"] == 1
        and rationale_document["margin"] == ni["margin"]
        and rationale_document["rationale"] == ni["rationale"]
        and rationale_document["selectionEvidenceScope"]
        == ni["selectionEvidenceScope"],
        "domain NI rationale evidence does not attest the frozen margin",
    )

    implementation = contract["implementation"]
    _require(isinstance(implementation, dict), "implementation must be an object")
    _exact_keys(implementation, IMPLEMENTATION_KEYS, label="implementation")
    expected_hashes = {
        "auditorSha256": sha256_file(Path(__file__).resolve()),
        "runnerSha256": sha256_file(Path(runner.__file__).resolve()),
        "scorerSha256": sha256_file(Path(scorer.__file__).resolve()),
    }
    _require(implementation == expected_hashes, "frozen implementation hashes mismatch")
    return contract, path, {**parsed_weights, "margin": margin}


def _load_evidence(
    path: Path,
    expected_sha256: str,
    *,
    contract: Mapping[str, Any],
    contract_path: Path,
    contract_file_sha256: str,
) -> tuple[dict[str, Any], Path]:
    path = _regular_file(path, expected_sha256, label="gold-free cost evidence")
    evidence = _load_json(path, expected_sha256, label="gold-free cost evidence")
    _exact_keys(evidence, EVIDENCE_KEYS, label="gold-free cost evidence")
    _verify_self_hash(evidence, "selfHash", label="gold-free cost evidence")
    _require(
        evidence["schemaVersion"] == 1
        and evidence["protocol"] == EVIDENCE_PROTOCOL
        and evidence["status"] == EVIDENCE_STATUS
        and evidence["campaignId"] == contract["campaignId"],
        "gold-free cost evidence identity mismatch",
    )
    bound_contract = _safe_bound_file(
        path.parent,
        evidence["contractPath"],
        evidence["contractFileSha256"],
        label="evidence-bound fairness contract",
    )
    _require(
        bound_contract == contract_path
        and evidence["contractFileSha256"] == contract_file_sha256
        and evidence["contractSelfHash"] == contract["selfHash"],
        "gold-free evidence fairness-contract binding mismatch",
    )
    return evidence, path


def _runner_paths(root: Path, binding: Mapping[str, Any]) -> tuple[Path, Path, Path, Path]:
    _exact_keys(binding, RUNNER_BINDING_KEYS, label="runnerCampaign")
    for key in (
        "unitManifestFileSha256",
        "scheduleFileSha256",
        "campaignReceiptFileSha256",
        "campaignReceiptSha256",
        "scientificPredictionsFileSha256",
    ):
        _sha256(binding[key], label=f"runnerCampaign.{key}")
    _require(
        isinstance(binding["campaignGitCommit"], str)
        and runner.HEX40.fullmatch(binding["campaignGitCommit"]) is not None,
        "runner campaign Git commit format",
    )
    unit_manifest = _safe_bound_file(
        root,
        binding["unitManifestPath"],
        binding["unitManifestFileSha256"],
        label="runner unit manifest",
    )
    schedule = _safe_bound_file(
        root,
        binding["schedulePath"],
        binding["scheduleFileSha256"],
        label="runner schedule",
    )
    output = _safe_bound_directory(root, binding["outputDirectory"], label="runner output")
    campaign_receipt = _safe_bound_file(
        output,
        "campaign_receipt.json",
        binding["campaignReceiptFileSha256"],
        label="runner campaign receipt",
    )
    predictions = _safe_bound_file(
        output,
        "scientific_predictions.jsonl",
        binding["scientificPredictionsFileSha256"],
        label="runner scientific predictions",
    )
    return unit_manifest, schedule, campaign_receipt, predictions


def _validated_runner(
    *,
    evidence: Mapping[str, Any],
    evidence_root: Path,
    runner_validator: Callable[..., Mapping[str, Any]],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    binding = evidence["runnerCampaign"]
    _require(isinstance(binding, dict), "runnerCampaign must be an object")
    unit_manifest, schedule, _receipt_path, _predictions_path = _runner_paths(
        evidence_root, binding
    )
    try:
        validated = runner_validator(
            unit_manifest_path=unit_manifest,
            expected_unit_manifest_file_sha256=binding["unitManifestFileSha256"],
            schedule_path=schedule,
            expected_schedule_file_sha256=binding["scheduleFileSha256"],
            expected_campaign_git_commit=binding["campaignGitCommit"],
            output_dir=(evidence_root / binding["outputDirectory"]).resolve(),
        )
    except runner.SingletonCampaignError as error:
        raise ConfirmationAuditError(f"runner campaign validation failed: {error}") from error
    _require(isinstance(validated, Mapping), "runner validator did not return a mapping")
    receipt = validated.get("campaignReceipt")
    _require(isinstance(receipt, Mapping), "runner validator omitted campaign receipt")
    _require(
        receipt.get("campaignId") == evidence["campaignId"]
        and receipt.get("campaignGitCommit") == binding["campaignGitCommit"]
        and receipt.get("receiptSha256") == binding["campaignReceiptSha256"]
        and receipt.get("scientificPredictionsSha256")
        == binding["scientificPredictionsFileSha256"],
        "runner validation/evidence binding mismatch",
    )
    return validated, binding


def _validate_physical_ledgers(
    validated: Mapping[str, Any],
    *,
    stage_token_limits: Mapping[str, Mapping[str, int]],
) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]], list[str]]:
    manifest = validated.get("manifest")
    schedule = validated.get("schedule")
    receipts = validated.get("unitReceipts")
    campaign_receipt = validated.get("campaignReceipt")
    _require(isinstance(manifest, Mapping) and isinstance(schedule, Mapping), "runner manifest/schedule evidence")
    _require(isinstance(receipts, list) and bool(receipts), "runner unit receipt evidence")
    units = manifest.get("units")
    ordered = schedule.get("orderedUnitIds")
    _require(isinstance(units, list) and isinstance(ordered, list), "runner unit/schedule inventory")
    unit_by_id: dict[str, Mapping[str, Any]] = {}
    for position, unit in enumerate(units):
        _require(isinstance(unit, Mapping) and set(unit) == runner.UNIT_KEYS, f"runner unit {position} schema")
        unit_id = unit["unitId"]
        _require(isinstance(unit_id, str) and unit_id not in unit_by_id, f"runner unit {position} ID")
        unit_by_id[unit_id] = unit
    _require(ordered == [receipt.get("unitId") for receipt in receipts], "unit receipts are not in exact schedule order")
    _require(set(ordered) == set(unit_by_id) and len(ordered) == len(unit_by_id), "schedule/unit coverage mismatch")

    receipt_by_id: dict[str, Mapping[str, Any]] = {}
    aggregate_tokens = {key: 0 for key in runner.TOKEN_KEYS}
    process_total = 0
    wall_total = 0
    for receipt in receipts:
        _require(isinstance(receipt, Mapping), "unit receipt must be an object")
        _require(set(receipt) == runner.UNIT_RECEIPT_KEYS, f"unit receipt {receipt.get('unitId')} schema")
        unit_id = receipt["unitId"]
        _require(unit_id in unit_by_id and unit_id not in receipt_by_id, f"unit receipt {unit_id} coverage")
        unit = unit_by_id[unit_id]
        _require(
            receipt["caseId"] == unit["caseId"]
            and receipt["armId"] == unit["armId"]
            and receipt["stageId"] == unit["stageId"],
            f"unit receipt {unit_id} coordinate mismatch",
        )
        usage = receipt["tokenUsage"]
        _require(isinstance(usage, Mapping) and set(usage) == runner.TOKEN_KEYS, f"unit {unit_id} token schema")
        _require(
            all(type(usage[key]) is int and usage[key] >= 0 for key in runner.TOKEN_KEYS),
            f"unit {unit_id} token values",
        )
        _require(
            usage["cachedInputTokens"] <= usage["inputTokens"]
            and usage["cacheWriteInputTokens"] <= usage["inputTokens"]
            and usage["reasoningTokens"] <= usage["outputTokens"]
            and usage["totalTokens"] == usage["inputTokens"] + usage["outputTokens"],
            f"unit {unit_id} token arithmetic",
        )
        _require(
            receipt["processInvocationCount"] == 1
            and receipt["semanticRetryCount"] == 0
            and receipt["transportRetryCount"] == 0
            and type(receipt["wallTimeMilliseconds"]) is int
            and receipt["wallTimeMilliseconds"] >= 0,
            f"unit {unit_id} invocation/wall ledger",
        )
        stage_id = unit["stageId"]
        _require(stage_id in stage_token_limits, f"unit {unit_id} has no phase-A stage token ceiling")
        limits = stage_token_limits[stage_id]
        _require(
            usage["outputTokens"] <= limits["maxOutputTokens"]
            and usage["totalTokens"] <= limits["maxTotalTokens"],
            f"unit {unit_id} exceeds its phase-A token ceiling",
        )
        for key in runner.TOKEN_KEYS:
            aggregate_tokens[key] += usage[key]
        process_total += receipt["processInvocationCount"]
        wall_total += receipt["wallTimeMilliseconds"]
        receipt_by_id[unit_id] = receipt

    _require(
        isinstance(campaign_receipt, Mapping)
        and campaign_receipt.get("tokenTotals") == aggregate_tokens
        and campaign_receipt.get("campaignProcessInvocationCount") == process_total
        and campaign_receipt.get("semanticRetryCount") == 0
        and campaign_receipt.get("transportRetryCount") == 0
        and campaign_receipt.get("unitWallTimeMillisecondsTotal") == wall_total,
        "campaign aggregate cost ledger mismatch",
    )
    return unit_by_id, receipt_by_id, list(ordered)


def _case_ids(validated: Mapping[str, Any]) -> list[str]:
    rows = validated.get("scientificRows")
    _require(isinstance(rows, list) and bool(rows), "runner scientific rows")
    ids = sorted({row.get("id") for row in rows if isinstance(row, Mapping)})
    _require(all(isinstance(case_id, str) for case_id in ids), "runner scientific case IDs")
    expected = {
        (case_id, runner_arm)
        for case_id in ids
        for runner_arm in scorer.RUNNER_ARM_ORDER
    }
    observed = {
        (row.get("id"), row.get("armId"))
        for row in rows
        if isinstance(row, Mapping)
    }
    _require(observed == expected and len(rows) == len(expected), "runner scientific case x arm matrix mismatch")
    return ids


def _longest_path_milliseconds(
    unit_ids: Sequence[str],
    unit_by_id: Mapping[str, Mapping[str, Any]],
    receipt_by_id: Mapping[str, Mapping[str, Any]],
) -> int:
    allowed = set(unit_ids)
    memo: dict[str, int] = {}

    def visit(unit_id: str, active: set[str]) -> int:
        _require(unit_id not in active, "attributed dependency cycle")
        if unit_id in memo:
            return memo[unit_id]
        dependencies = unit_by_id[unit_id]["dependencies"]
        _require(set(dependencies) <= allowed, f"attribution for {unit_id} is not dependency-closed")
        prior = max((visit(dep, active | {unit_id}) for dep in dependencies), default=0)
        value = prior + receipt_by_id[unit_id]["wallTimeMilliseconds"]
        memo[unit_id] = value
        return value

    return max((visit(unit_id, set()) for unit_id in unit_ids), default=0)


def _unit_cost(usage: Mapping[str, int], weights: Mapping[str, Fraction]) -> Fraction:
    uncached = usage["inputTokens"] - usage["cachedInputTokens"]
    return (
        weights["uncachedInputWeight"] * uncached
        + weights["cachedInputWeight"] * usage["cachedInputTokens"]
        + weights["outputWeight"] * usage["outputTokens"]
    )


def _audit_arm_attribution(
    *,
    evidence: Mapping[str, Any],
    contract: Mapping[str, Any],
    validated: Mapping[str, Any],
    weights: Mapping[str, Fraction],
) -> tuple[dict[str, Any], dict[str, Fraction], list[str], str | None]:
    unit_by_id, receipt_by_id, ordered_units = _validate_physical_ledgers(
        validated,
        stage_token_limits=contract["costPolicy"]["stageTokenLimits"],
    )
    case_ids = _case_ids(validated)
    schedule_position = {unit_id: index for index, unit_id in enumerate(ordered_units)}
    arms = list(REQUIRED_COST_ARMS) + list(contract["supplementaryCostArms"])
    attribution = evidence["armAttribution"]
    _require(isinstance(attribution, list), "armAttribution must be a list")
    _require(
        [entry.get("arm") if isinstance(entry, Mapping) else None for entry in attribution] == arms,
        "armAttribution order/coverage mismatch",
    )

    report: dict[str, Any] = {}
    costs: dict[str, Fraction] = {}
    globally_attributed: set[str] = set()
    attributed_by_arm_case: dict[tuple[str, str], tuple[str, ...]] = {}
    for entry in attribution:
        _require(isinstance(entry, Mapping), "arm attribution entry must be an object")
        _exact_keys(entry, ARM_ATTRIBUTION_KEYS, label=f"arm attribution {entry.get('arm')}")
        arm = entry["arm"]
        cases = entry["cases"]
        _require(isinstance(cases, list), f"{arm} case attribution must be a list")
        _require(
            [case.get("id") if isinstance(case, Mapping) else None for case in cases] == case_ids,
            f"{arm} attribution does not cover exact ordered cases",
        )
        arm_units: list[str] = []
        case_critical: dict[str, int] = {}
        for case in cases:
            _require(isinstance(case, Mapping), f"{arm} case attribution entry")
            _exact_keys(case, CASE_ATTRIBUTION_KEYS, label=f"{arm}/{case.get('id')} attribution")
            case_id = case["id"]
            unit_ids = case["unitIds"]
            _require(
                isinstance(unit_ids, list)
                and bool(unit_ids)
                and all(isinstance(unit_id, str) for unit_id in unit_ids)
                and len(unit_ids) == len(set(unit_ids)),
                f"{arm}/{case_id} attributed units",
            )
            _require(
                all(unit_id in unit_by_id for unit_id in unit_ids),
                f"{arm}/{case_id} references an unknown unit",
            )
            _require(
                all(unit_by_id[unit_id]["caseId"] == case_id for unit_id in unit_ids),
                f"{arm}/{case_id} references another case",
            )
            _require(
                unit_ids == sorted(unit_ids, key=schedule_position.__getitem__),
                f"{arm}/{case_id} units are not in frozen schedule order",
            )
            if arm in PRIMARY_RESPONSE_CAPS:
                _require(
                    PRIMARY_RESPONSE_MINIMUMS[arm]
                    <= len(unit_ids)
                    <= PRIMARY_RESPONSE_CAPS[arm],
                    f"{arm}/{case_id} violates its frozen response-count bounds",
                )
            if arm in PRIMARY_ARMS:
                runner_arm = scorer.RUNNER_ARM_BY_PAPER_ARM[arm]
                answer_units = [
                    unit_id
                    for unit_id, unit in unit_by_id.items()
                    if unit["caseId"] == case_id
                    and unit["armId"] == runner_arm
                    and unit["stageId"] == "answer"
                    and unit["producesScientificOutcome"] is True
                ]
                _require(
                    len(answer_units) == 1 and answer_units[0] in unit_ids,
                    f"{arm}/{case_id} omits its scientific answer unit",
                )
            case_critical[case_id] = _longest_path_milliseconds(
                unit_ids, unit_by_id, receipt_by_id
            )
            attributed_by_arm_case[(arm, case_id)] = tuple(unit_ids)
            arm_units.extend(unit_ids)
            globally_attributed.update(unit_ids)
        _require(len(arm_units) == len(set(arm_units)), f"{arm} attributes a unit more than once")

        token_totals = {key: 0 for key in runner.TOKEN_KEYS}
        unit_ledger: list[dict[str, Any]] = []
        total_cost = Fraction(0)
        process_invocations = 0
        wall_total = 0
        for unit_id in arm_units:
            unit = unit_by_id[unit_id]
            receipt = receipt_by_id[unit_id]
            usage = receipt["tokenUsage"]
            uncached = usage["inputTokens"] - usage["cachedInputTokens"]
            cost = _unit_cost(usage, weights)
            for key in runner.TOKEN_KEYS:
                token_totals[key] += usage[key]
            total_cost += cost
            process_invocations += receipt["processInvocationCount"]
            wall_total += receipt["wallTimeMilliseconds"]
            unit_ledger.append(
                {
                    "unitId": unit_id,
                    "caseId": unit["caseId"],
                    "physicalArmId": unit["armId"],
                    "stageId": unit["stageId"],
                    "receiptSha256": receipt["receiptSha256"],
                    "semanticResponses": 1,
                    "processInvocations": receipt["processInvocationCount"],
                    "modelInvocations": 1,
                    "preModelTransportAttempts": receipt["transportRetryCount"],
                    "inputTokens": usage["inputTokens"],
                    "cachedInputTokens": usage["cachedInputTokens"],
                    "uncachedInputTokens": uncached,
                    "cacheWriteInputTokens": usage["cacheWriteInputTokens"],
                    "outputTokens": usage["outputTokens"],
                    "reasoningTokens": usage["reasoningTokens"],
                    "totalTokens": usage["totalTokens"],
                    "wallTimeMilliseconds": receipt["wallTimeMilliseconds"],
                    "attributedCostUnits": _finite_fraction_decimal(cost),
                }
            )
        _require(total_cost > 0, f"{arm} attributed cost must be positive")
        report[arm] = {
            "cases": len(case_ids),
            "attributedPhysicalUnits": len(arm_units),
            "semanticResponses": len(arm_units),
            "processInvocations": process_invocations,
            "modelInvocations": len(arm_units),
            "preModelTransportAttempts": 0,
            "semanticRetryCount": 0,
            "transportRetryCount": 0,
            "tokenTotals": {
                **token_totals,
                "uncachedInputTokens": token_totals["inputTokens"]
                - token_totals["cachedInputTokens"],
            },
            "wallTimeMillisecondsTotal": wall_total,
            "criticalPath": {
                "method": CRITICAL_PATH_METHOD,
                "perCaseMilliseconds": case_critical,
                "sumCaseCriticalPathMilliseconds": sum(case_critical.values()),
                "maxCaseCriticalPathMilliseconds": max(case_critical.values()),
            },
            "attributedCostUnits": _finite_fraction_decimal(total_cost),
            "unitLedger": unit_ledger,
        }
        costs[arm] = total_cost

    missing_physical = set(unit_by_id) - globally_attributed
    _require(not missing_physical, f"physical model units are absent from every deployable ledger: {sorted(missing_physical)}")

    for case_id in case_ids:
        previous: tuple[str, ...] = ()
        for index, arm in enumerate(SC_PREFIXES, 1):
            current = attributed_by_arm_case[(arm, case_id)]
            _require(
                len(current) == index and current[: index - 1] == previous,
                f"{arm}/{case_id} is not the exact nested D1-D{index} prefix",
            )
            previous = current

    mini = costs[CANDIDATE]
    matched_sc: list[tuple[int, Fraction]] = []
    for index, arm in enumerate(SC_PREFIXES, 1):
        cost = costs[arm]
        ratio = cost / mini
        if Fraction(MATCH_LOWER) <= ratio <= Fraction(MATCH_UPPER):
            distortion = max(ratio, 1 / ratio)
            matched_sc.append((index, distortion))
    selected: str | None = None
    if matched_sc:
        selected_index = min(matched_sc, key=lambda item: (item[1], item[0]))[0]
        selected = f"SC-{selected_index}"
    _require(
        evidence["claimedSelectedScPrefix"] == selected,
        "gold-free evidence claimed SC prefix differs from exact selector",
    )
    return report, costs, case_ids, selected


def _cost_comparisons(costs: Mapping[str, Fraction]) -> dict[str, Any]:
    mini = costs[CANDIDATE]
    comparisons: dict[str, Any] = {}
    for arm in (*PRIMARY_COMPARATORS, *SC_PREFIXES):
        comparator = costs[arm]
        ratio = comparator / mini
        if ratio < Fraction(MATCH_LOWER):
            classification = "lower_cost"
        elif ratio > Fraction(MATCH_UPPER):
            classification = "higher_cost"
        else:
            classification = "measured_cost_matched"
        comparisons[arm] = {
            "candidateArm": CANDIDATE,
            "comparatorArm": arm,
            "costRatioComparatorOverMiniExact": _fraction_text(ratio),
            "costRatioComparatorOverMiniDisplay": _ratio_display(ratio),
            "matchingWindow": {"lowerInclusive": "0.80", "upperInclusive": "1.25"},
            "roundingTolerance": "0",
            "classification": classification,
            "measuredCostMatched": classification == "measured_cost_matched",
        }
    return comparisons


def _score_report(
    *,
    score_manifest_path: Path,
    expected_score_manifest_file_sha256: str,
    score_report_path: Path,
    expected_score_report_file_sha256: str,
    contract: Mapping[str, Any],
    score_builder: Callable[..., Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = _load_json(
        score_manifest_path,
        expected_score_manifest_file_sha256,
        label="score manifest",
    )
    report = _load_json(
        score_report_path,
        expected_score_report_file_sha256,
        label="score report",
    )
    try:
        rebuilt = score_builder(
            manifest_path=score_manifest_path.resolve(),
            expected_manifest_file_sha256=expected_score_manifest_file_sha256,
        )
    except scorer.CampaignScoreError as error:
        raise ConfirmationAuditError(f"score report rebuild failed: {error}") from error
    _require(isinstance(rebuilt, Mapping) and dict(rebuilt) == report, "stored score report differs from frozen scorer rebuild")
    _verify_self_hash(report, "reportSha256", label="score report")
    _require(
        report.get("protocol") == scorer.PROTOCOL
        and report.get("status") == "SCORED_FULL_DENOMINATOR"
        and report.get("campaignId") == contract["campaignId"]
        and report.get("candidateArm") == CANDIDATE
        and report.get("comparatorArms") == list(PRIMARY_COMPARATORS),
        "score report identity/family mismatch",
    )
    statistics = manifest.get("statistics")
    ni = contract["domainNoninferiority"]
    _require(isinstance(statistics, Mapping), "score manifest statistics missing")
    _require(
        statistics.get("alpha") == 0.05
        and statistics.get("confidenceLevel") == 0.95
        and statistics.get("bootstrapMethod") == ni["intervalMethod"]
        and statistics.get("bootstrapSeed") == ni["bootstrapSeed"]
        and statistics.get("bootstrapReplicates") == ni["bootstrapReplicates"],
        "score statistics differ from phase-A domain-NI contract",
    )
    _require(
        manifest.get("implementation", {}).get("scorerSha256")
        == contract["implementation"]["scorerSha256"],
        "score manifest scorer hash differs from fairness contract",
    )
    return report, manifest


def _domain_ni_gates(
    report: Mapping[str, Any], margin: Decimal, selected_sc: str | None
) -> tuple[dict[str, Any], bool, dict[str, Any] | None]:
    comparisons = report.get("comparisons")
    _require(isinstance(comparisons, Mapping), "score report comparisons missing")
    primary: dict[str, Any] = {}
    for comparator in PRIMARY_COMPARATORS:
        comparison = comparisons.get(comparator)
        _require(isinstance(comparison, Mapping), f"score report comparison missing: {comparator}")
        bootstrap = comparison.get("stratifiedPairedBootstrap")
        _require(isinstance(bootstrap, Mapping), f"bootstrap evidence missing: {comparator}")
        _require(
            bootstrap.get("method") == NI_INTERVAL_METHOD
            and bootstrap.get("oneSidedConfidenceLevel") == 0.95,
            f"domain NI interval mismatch: {comparator}",
        )
        lower_bounds = bootstrap.get("domainLabelBalancedRiskDifferenceLowerBounds")
        _require(
            isinstance(lower_bounds, Mapping) and set(lower_bounds) == set(scorer.DOMAINS),
            f"domain NI lower bounds missing: {comparator}",
        )
        domains: dict[str, Any] = {}
        for domain in scorer.DOMAINS:
            raw = lower_bounds[domain]
            _require(
                isinstance(raw, (int, float))
                and not isinstance(raw, bool)
                and math.isfinite(float(raw)),
                f"invalid domain NI lower bound: {comparator}/{domain}",
            )
            lower = Decimal(str(raw))
            passed = lower > -margin
            domains[domain] = {
                "oneSided95PercentLowerBound": str(raw),
                "strictThreshold": _finite_decimal(-margin),
                "passed": passed,
            }
        primary[comparator] = {
            "domains": domains,
            "passed": all(item["passed"] for item in domains.values()),
        }
    primary_passed = all(item["passed"] for item in primary.values())

    selected_gate: dict[str, Any] | None = None
    if selected_sc is not None:
        if selected_sc in primary:
            iut = report.get("primaryFixedIntersectionUnionTest")
            components = iut.get("components") if isinstance(iut, Mapping) else None
            _require(
                isinstance(components, Mapping)
                and isinstance(components.get(selected_sc), Mapping)
                and type(components[selected_sc].get("passed")) is bool,
                "selected SC superiority component evidence is missing",
            )
            selected_gate = {
                "selectedScPrefix": selected_sc,
                "scoreEvidencePresent": True,
                "domainNoninferiorityPassed": primary[selected_sc]["passed"],
                "superiorityComponentPassed": components[selected_sc]["passed"],
            }
        else:
            selected_gate = {
                "selectedScPrefix": selected_sc,
                "scoreEvidencePresent": False,
                "domainNoninferiorityPassed": False,
                "superiorityComponentPassed": False,
            }
        selected_gate["additionalSelectedScGatePassed"] = (
            selected_gate["scoreEvidencePresent"]
            and selected_gate["domainNoninferiorityPassed"]
            and selected_gate["superiorityComponentPassed"]
        )
    return primary, primary_passed, selected_gate


def _reserve_scope_gate(report: Mapping[str, Any]) -> dict[str, Any]:
    denominator = report.get("denominator")
    _require(isinstance(denominator, Mapping), "score report denominator missing")
    counts = denominator.get("cellCounts")
    expected_keys = {
        f"{domain}|{label}" for domain in scorer.DOMAINS for label in scorer.LABELS
    }
    _require(
        isinstance(counts, Mapping)
        and set(counts) == expected_keys
        and all(type(value) is int and value >= 0 for value in counts.values()),
        "score report four-cell counts are invalid",
    )
    civil_grant = counts["civil|인용됨"]
    civil_dismiss = counts["civil|기각"]
    tax_grant = counts["tax|인용됨"]
    tax_dismiss = counts["tax|기각"]
    n = denominator.get("n")
    balanced = civil_grant == civil_dismiss and tax_grant == tax_dismiss
    quotas = (
        140 <= civil_grant <= 150
        and 80 <= tax_grant <= 90
        and type(n) is int
        and n == sum(counts.values())
        and n == 2 * civil_grant + 2 * tax_grant
        and 440 <= n <= 480
    )
    _require(
        balanced and quotas,
        "reserve scope is not the predeclared balanced 440-480 design",
    )
    return {
        "civilPerLabel": civil_grant,
        "taxPerLabel": tax_grant,
        "n": n,
        "balancedWithinDomain": True,
        "protocolQuotaPassed": True,
    }


def build_audit(
    *,
    contract_path: Path,
    expected_contract_file_sha256: str,
    cost_evidence_path: Path,
    expected_cost_evidence_file_sha256: str,
    score_manifest_path: Path,
    expected_score_manifest_file_sha256: str,
    expected_pre_gold_cost_git_commit: str,
    expected_score_freeze_git_commit: str,
    score_report_path: Path,
    expected_score_report_file_sha256: str,
    runner_validator: Callable[..., Mapping[str, Any]] = runner.validate_completed_campaign,
    score_builder: Callable[..., Mapping[str, Any]] = scorer.build_report,
    chronology_verifier: Callable[..., Mapping[str, str]] = verify_freeze_chronology,
) -> dict[str, Any]:
    """Revalidate all evidence and return an in-memory claim audit."""

    contract, resolved_contract, parsed = _load_contract(
        contract_path, expected_contract_file_sha256
    )
    evidence, resolved_evidence = _load_evidence(
        cost_evidence_path,
        expected_cost_evidence_file_sha256,
        contract=contract,
        contract_path=resolved_contract,
        contract_file_sha256=expected_contract_file_sha256,
    )
    validated, runner_binding = _validated_runner(
        evidence=evidence,
        evidence_root=resolved_evidence.parent,
        runner_validator=runner_validator,
    )
    runner_code_hashes = validated.get("manifest", {}).get("codeHashes")
    _require(
        isinstance(runner_code_hashes, Mapping)
        and runner_code_hashes.get(str(resolved_contract))
        == expected_contract_file_sha256,
        "phase-A runner manifest does not source-bind the fairness contract",
    )
    phase_a_anchor = validated.get("manifest", {}).get("gitAnchor")
    _require(
        isinstance(phase_a_anchor, Mapping)
        and isinstance(phase_a_anchor.get("commit"), str)
        and runner.HEX40.fullmatch(phase_a_anchor["commit"]) is not None,
        "runner phase-A Git anchor is missing",
    )
    arm_ledgers, costs, case_ids, selected_sc = _audit_arm_attribution(
        evidence=evidence,
        contract=contract,
        validated=validated,
        weights=parsed,
    )
    cost_comparisons = _cost_comparisons(costs)
    score_report, _score_manifest = _score_report(
        score_manifest_path=score_manifest_path,
        expected_score_manifest_file_sha256=expected_score_manifest_file_sha256,
        score_report_path=score_report_path,
        expected_score_report_file_sha256=expected_score_report_file_sha256,
        contract=contract,
        score_builder=score_builder,
    )
    try:
        chronology = chronology_verifier(
            phase_a_commit=phase_a_anchor["commit"],
            cost_evidence_path=resolved_evidence,
            expected_pre_gold_cost_git_commit=expected_pre_gold_cost_git_commit,
            score_manifest_path=score_manifest_path.resolve(),
            expected_score_freeze_git_commit=expected_score_freeze_git_commit,
        )
    except ConfirmationAuditError:
        raise
    except Exception as error:
        raise ConfirmationAuditError("freeze chronology verifier failed") from error
    _require(isinstance(chronology, Mapping), "freeze chronology verifier result")
    score_runner = score_report.get("bindings", {}).get("runnerCampaign")
    _require(isinstance(score_runner, Mapping), "score report runner binding missing")
    _require(
        score_runner.get("campaignReceiptSha256")
        == runner_binding["campaignReceiptSha256"]
        and score_runner.get("scientificPredictionsFileSha256")
        == runner_binding["scientificPredictionsFileSha256"]
        and score_runner.get("unitManifestFileSha256")
        == runner_binding["unitManifestFileSha256"]
        and score_runner.get("scheduleFileSha256")
        == runner_binding["scheduleFileSha256"],
        "score report and cost audit do not bind the same runner campaign",
    )
    _require(
        score_report.get("denominator", {}).get("n") == len(case_ids)
        and score_report.get("denominator", {}).get("orderedIdsSha256")
        == canonical_digest(case_ids),
        "score report denominator differs from cost-attribution cases",
    )
    reserve_scope = _reserve_scope_gate(score_report)

    domain_gates, domain_passed, selected_sc_gate = _domain_ni_gates(
        score_report, parsed["margin"], selected_sc
    )
    iut = score_report.get("primaryFixedIntersectionUnionTest")
    _require(
        isinstance(iut, Mapping)
        and iut.get("membership") == list(PRIMARY_COMPARATORS),
        "score report primary IUT membership mismatch",
    )
    primary_superiority = iut.get("passed") is True
    measured_sc_component_passed = bool(
        selected_sc_gate is not None
        and selected_sc_gate["additionalSelectedScGatePassed"]
    )
    measured_sc_authorized = (
        primary_superiority and domain_passed and measured_sc_component_passed
    )

    report: dict[str, Any] = {
        "schemaVersion": 1,
        "protocol": PROTOCOL,
        "status": "AUDITED_READ_ONLY",
        "campaignId": contract["campaignId"],
        "bindings": {
            "contractFileSha256": expected_contract_file_sha256,
            "contractSelfHash": contract["selfHash"],
            "goldFreeCostEvidenceFileSha256": expected_cost_evidence_file_sha256,
            "goldFreeCostEvidenceSelfHash": evidence["selfHash"],
            "runnerCampaignReceiptSha256": runner_binding["campaignReceiptSha256"],
            "scoreManifestFileSha256": expected_score_manifest_file_sha256,
            "scoreReportFileSha256": expected_score_report_file_sha256,
            "scoreReportSelfHash": score_report["reportSha256"],
            "auditorSha256": contract["implementation"]["auditorSha256"],
            "freezeChronology": dict(chronology),
        },
        "costPolicy": {
            "costUnit": "frozen_token_equivalent_unit",
            "billableCurrencyClaimed": False,
            "formula": COST_FORMULA,
            "reasoningTokensChargedSeparately": False,
            "sharedPhysicalUnitChargedInFullOncePerDeployableArm": True,
            "researchCampaignMarginalCostUsed": False,
            "matchingWindow": {"lowerInclusive": "0.80", "upperInclusive": "1.25"},
            "roundingTolerance": "0",
            "scPrefixSelector": SC_SELECTOR,
        },
        "armLedgers": arm_ledgers,
        "perComparatorCostEligibility": cost_comparisons,
        "selectedScPrefix": {
            "value": selected_sc,
            "locallyGitOrderedBeforeScoreFreeze": True,
            "chronologyVerifiedByDistinctGitAncestryAndFrozenBytes": True,
            "independentlyTimestamped": False,
            "claimRequiresAdditionalScoreAndDomainGates": True,
        },
        "domainNoninferiority": {
            "commonMargin": contract["domainNoninferiority"]["margin"],
            "rule": NI_RULE,
            "intervalMethod": NI_INTERVAL_METHOD,
            "primaryComparatorGates": domain_gates,
            "allPrimaryComparatorDomainsPassed": domain_passed,
            "selectedScGate": selected_sc_gate,
        },
        "reserveScope": reserve_scope,
        "claimAuthorization": {
            "primaryAllComparatorSuperiorityIutPassed": primary_superiority,
            "allPrimaryComparatorDomainNoninferiorityPassed": domain_passed,
            "aggregateSuperiorityWithDomainNoHarmAuthorized": primary_superiority
            and domain_passed,
            "measuredCostMatchedScPrefixClaimAuthorized": measured_sc_authorized,
        },
        "limitations": [
            "The common domain noninferiority margin is supplied by the phase-A contract; this auditor does not choose or justify its scientific magnitude.",
            "Token-equivalent weights support exact within-model cost matching but are not a claim about currency spend.",
            "A selected SC-k prefix other than SC-4 is not present in the current fixed score family; its measured-cost superiority claim remains unauthorized until separately frozen score evidence exists.",
            "Critical path is reconstructed from frozen per-case unit dependencies and receipt wall times, not provider-signed telemetry.",
            "Local Git ancestry orders the gold-free cost evidence before the score freeze but is not an independently timestamped public commitment.",
            "Stage token ceilings are fail-closed acceptance limits checked against authenticated receipts; the current runner does not attest provider-side token cutoff enforcement.",
        ],
    }
    report["reportSha256"] = canonical_digest(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--contract-file-sha256", required=True)
    parser.add_argument("--cost-evidence", type=Path, required=True)
    parser.add_argument("--cost-evidence-file-sha256", required=True)
    parser.add_argument("--score-manifest", type=Path, required=True)
    parser.add_argument("--score-manifest-file-sha256", required=True)
    parser.add_argument("--pre-gold-cost-git-commit", required=True)
    parser.add_argument("--score-freeze-git-commit", required=True)
    parser.add_argument("--score-report", type=Path, required=True)
    parser.add_argument("--score-report-file-sha256", required=True)
    args = parser.parse_args()
    try:
        report = build_audit(
            contract_path=args.contract,
            expected_contract_file_sha256=args.contract_file_sha256,
            cost_evidence_path=args.cost_evidence,
            expected_cost_evidence_file_sha256=args.cost_evidence_file_sha256,
            score_manifest_path=args.score_manifest,
            expected_score_manifest_file_sha256=args.score_manifest_file_sha256,
            expected_pre_gold_cost_git_commit=args.pre_gold_cost_git_commit,
            expected_score_freeze_git_commit=args.score_freeze_git_commit,
            score_report_path=args.score_report,
            expected_score_report_file_sha256=args.score_report_file_sha256,
        )
    except ConfirmationAuditError as error:
        print(json.dumps({"status": "REJECTED", "error": str(error)}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
