#!/usr/bin/env python3
"""Fail-closed private scoring for the frozen singleton legal campaign.

This is the first component in this experiment that is allowed to join a
scientific prediction to its private outcome label.  It does not repair,
impute, reorder, or retry a prediction.  ``null`` and ``ABSTAIN`` are retained
on the full denominator and are wrong.

The scorer deliberately has a small input surface: one externally hash-pinned
score manifest, the runner's completed campaign artifact tree, and one exact
three-field private scoring projection.  There is no per-arm prediction or
receipt adapter.  The runner's read-only validator checks the combined
prediction JSONL, campaign receipt, and every unit registry/result/trace/receipt
before this scorer enforces the exact case-by-eight-arm answer matrix.  The
projection must be
created, frozen, and hash-pinned by a solver-inaccessible upstream supervisor;
this core intentionally does not consume the richer private-consensus artifact
directly.  Operational runner/trace validation is likewise upstream: this
program checks frozen receipt claims and their cryptographic bindings rather
than reinterpreting raw model traces.  All prediction/receipt artifacts are
validated before the private projection is opened.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import run_singleton_legal_campaign as runner  # noqa: E402


PROTOCOL = "singleton-legal-campaign-score-v1"
MANIFEST_PROTOCOL = "singleton-legal-campaign-freeze-v1"
PRIMARY_CANDIDATE = "Mini-4"
PRIMARY_COMPARATORS = (
    "Plain-Luna-1",
    "Structured-Direct-1",
    "SC-4",
    "Bo3+J",
    "CR-4",
    "task-adapted-ICR-4",
    "answer-only-veto-4",
)
ARM_ORDER = (PRIMARY_CANDIDATE, *PRIMARY_COMPARATORS)
RUNNER_ARM_BY_PAPER_ARM = {
    "Mini-4": "mini-4",
    "Plain-Luna-1": "plain-luna-1",
    "Structured-Direct-1": "structured-direct-1",
    "SC-4": "sc-4",
    "Bo3+J": "bo3-j",
    "CR-4": "cr-4",
    "task-adapted-ICR-4": "task-adapted-icr-4",
    "answer-only-veto-4": "answer-only-veto-4",
}
RUNNER_ARM_ORDER = tuple(RUNNER_ARM_BY_PAPER_ARM[arm] for arm in ARM_ORDER)
PAPER_ARM_BY_RUNNER_ARM = {
    runner_arm: paper_arm for paper_arm, runner_arm in RUNNER_ARM_BY_PAPER_ARM.items()
}
DOMAINS = ("civil", "tax")
LABELS = ("인용됨", "기각")
CELLS = tuple((domain, label) for domain in DOMAINS for label in LABELS)
OUTCOMES = {*LABELS, "ABSTAIN"}
OPAQUE_ID_RE = re.compile(r"outcome-confirm-[0-9a-f]{20}\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")

BOOTSTRAP_METHOD = (
    "paired_nonparametric_within_four_fixed_cells_empirical_alpha_quantile_v1"
)
PERMUTATION_METHOD = (
    "paired_sign_flip_four_cell_mba_exact_or_seeded_monte_carlo_plus_one_v1"
)
HOLM_METHOD = "holm_step_down_over_all_primary_mba_permutation_p_values_v1"

MANIFEST_KEYS = {
    "schemaVersion",
    "protocol",
    "status",
    "campaignId",
    "candidateArm",
    "comparatorArms",
    "runnerCampaign",
    "privateGold",
    "statistics",
    "implementation",
    "selfHash",
}
RUNNER_CAMPAIGN_KEYS = {
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
GOLD_BINDING_KEYS = {"path", "sha256", "rows", "orderedIdsSha256"}
STATISTICS_KEYS = {
    "alpha",
    "confidenceLevel",
    "bootstrapSeed",
    "bootstrapReplicates",
    "bootstrapMethod",
    "permutationSeed",
    "permutationReplicates",
    "permutationMethod",
    "exactPermutationMaxDiscordances",
    "holmMethod",
}
IMPLEMENTATION_KEYS = {"scorerSha256", "runnerSha256"}
COMBINED_PREDICTION_KEYS = {"id", "armId", "unitId", "outcome"}
GOLD_KEYS = {"id", "domain", "label"}


class CampaignScoreError(RuntimeError):
    """A fail-closed campaign validation or scoring error."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CampaignScoreError(message)


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
        raise CampaignScoreError(f"value is not canonical JSON: {error}") from error


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as error:
        raise CampaignScoreError(f"cannot hash {path}: {error}") from error
    return digest.hexdigest()


def _reject_constant(raw: str) -> Any:
    raise CampaignScoreError(f"non-finite JSON constant is forbidden: {raw}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise CampaignScoreError(f"duplicate JSON object key: {key}")
        value[key] = item
    return value


def _parse_json(raw: str, *, label: str) -> Any:
    try:
        return json.loads(
            raw,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except CampaignScoreError:
        raise
    except (json.JSONDecodeError, UnicodeError) as error:
        raise CampaignScoreError(f"invalid JSON in {label}: {error}") from error


def load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = path.read_bytes()
        raw = payload.decode("utf-8")
    except (OSError, UnicodeError) as error:
        raise CampaignScoreError(f"cannot read {label}: {error}") from error
    _require("\r" not in raw, f"{label} must use LF newlines")
    value = _parse_json(raw, label=label)
    _require(isinstance(value, dict), f"{label} must be a JSON object")
    return value


def load_jsonl(path: Path, *, label: str) -> list[dict[str, Any]]:
    try:
        payload = path.read_bytes()
        raw = payload.decode("utf-8")
    except (OSError, UnicodeError) as error:
        raise CampaignScoreError(f"cannot read {label}: {error}") from error
    _require(payload.endswith(b"\n"), f"{label} must end with LF")
    _require(b"\r" not in payload, f"{label} must use LF newlines")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(raw.split("\n")[:-1], 1):
        _require(bool(line), f"blank JSONL line in {label} at {line_number}")
        value = _parse_json(line, label=f"{label} row {line_number}")
        _require(
            isinstance(value, dict),
            f"{label} row {line_number} must be a JSON object",
        )
        rows.append(value)
    _require(bool(rows), f"{label} must not be empty")
    return rows


def _exact_keys(value: Mapping[str, Any], expected: set[str], *, label: str) -> None:
    observed = set(value)
    _require(
        observed == expected,
        f"{label} schema mismatch: missing={sorted(expected - observed)}, "
        f"extra={sorted(observed - expected)}",
    )


def _sha256(value: Any, *, label: str) -> str:
    _require(
        isinstance(value, str) and SHA256_RE.fullmatch(value) is not None,
        f"{label} must be a lowercase SHA-256",
    )
    return value


def _verify_self_hash(value: Mapping[str, Any], field: str, *, label: str) -> str:
    claimed = _sha256(value.get(field), label=f"{label}.{field}")
    unsigned = dict(value)
    unsigned.pop(field, None)
    _require(claimed == canonical_digest(unsigned), f"{label} self-hash mismatch")
    return claimed


def _safe_bound_path(root: Path, raw: Any, *, label: str) -> Path:
    _require(isinstance(raw, str) and bool(raw), f"{label} path must be nonempty")
    relative = Path(raw)
    _require(not relative.is_absolute(), f"{label} path must be relative")
    _require(relative.as_posix() == raw, f"{label} path must use normalized POSIX form")
    _require(".." not in relative.parts and "." not in relative.parts, f"{label} path is unsafe")
    unresolved = root / relative
    resolved = unresolved.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as error:
        raise CampaignScoreError(f"{label} path escapes campaign root") from error
    _require(not unresolved.is_symlink(), f"{label} path must not be a symlink")
    _require(resolved.is_file(), f"{label} path is not a regular file")
    return resolved


def _safe_bound_directory(root: Path, raw: Any, *, label: str) -> Path:
    _require(isinstance(raw, str) and bool(raw), f"{label} path must be nonempty")
    relative = Path(raw)
    _require(not relative.is_absolute(), f"{label} path must be relative")
    _require(relative.as_posix() == raw, f"{label} path must use normalized POSIX form")
    _require(".." not in relative.parts and "." not in relative.parts, f"{label} path is unsafe")
    unresolved = root / relative
    resolved = unresolved.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as error:
        raise CampaignScoreError(f"{label} path escapes campaign root") from error
    _require(not unresolved.is_symlink(), f"{label} path must not be a symlink")
    _require(resolved.is_dir(), f"{label} path is not a directory")
    return resolved


def _stable_rng(seed: str, *parts: str) -> random.Random:
    material = "\0".join((seed, *parts)).encode("utf-8")
    return random.Random(int.from_bytes(hashlib.sha256(material).digest(), "big"))


def _load_manifest(path: Path, expected_file_sha256: str) -> dict[str, Any]:
    _sha256(expected_file_sha256, label="expected campaign manifest file SHA-256")
    _require(path.is_file() and not path.is_symlink(), "campaign manifest must be a regular file")
    _require(
        sha256_file(path) == expected_file_sha256,
        "campaign manifest file hash mismatch",
    )
    manifest = load_json_object(path, label="campaign manifest")
    _exact_keys(manifest, MANIFEST_KEYS, label="campaign manifest")
    _verify_self_hash(manifest, "selfHash", label="campaign manifest")
    _require(
        type(manifest["schemaVersion"]) is int and manifest["schemaVersion"] == 1,
        "campaign manifest schemaVersion mismatch",
    )
    _require(manifest["protocol"] == MANIFEST_PROTOCOL, "campaign manifest protocol mismatch")
    _require(
        manifest["status"] == "FROZEN_FOR_ONE_TIME_PRIVATE_GOLD_OPEN",
        "campaign manifest is not frozen for private-gold opening",
    )
    campaign_id = manifest["campaignId"]
    _require(isinstance(campaign_id, str) and bool(campaign_id), "invalid campaignId")
    _require(manifest["candidateArm"] == PRIMARY_CANDIDATE, "candidate arm is not frozen Mini-4")
    _require(
        manifest["comparatorArms"] == list(PRIMARY_COMPARATORS),
        "fixed all-comparator IUT membership/order mismatch",
    )

    runner_campaign = manifest["runnerCampaign"]
    _require(isinstance(runner_campaign, dict), "runnerCampaign must be an object")
    _exact_keys(runner_campaign, RUNNER_CAMPAIGN_KEYS, label="runnerCampaign")
    for name in (
        "unitManifestFileSha256",
        "scheduleFileSha256",
        "campaignReceiptFileSha256",
        "campaignReceiptSha256",
        "scientificPredictionsFileSha256",
    ):
        _sha256(runner_campaign[name], label=f"runnerCampaign.{name}")
    _require(
        isinstance(runner_campaign["campaignGitCommit"], str)
        and runner.HEX40.fullmatch(runner_campaign["campaignGitCommit"]) is not None,
        "runnerCampaign.campaignGitCommit must be a lowercase Git commit",
    )
    for name in ("unitManifestPath", "schedulePath", "outputDirectory"):
        _require(
            isinstance(runner_campaign[name], str) and bool(runner_campaign[name]),
            f"runnerCampaign.{name} must be a nonempty relative path",
        )

    gold = manifest["privateGold"]
    _require(isinstance(gold, dict), "privateGold must be an object")
    _exact_keys(gold, GOLD_BINDING_KEYS, label="privateGold binding")
    _sha256(gold["sha256"], label="privateGold hash")
    _sha256(gold["orderedIdsSha256"], label="privateGold ordered IDs hash")
    _require(
        isinstance(gold["rows"], int)
        and not isinstance(gold["rows"], bool)
        and gold["rows"] > 0,
        "privateGold rows must be a positive integer",
    )

    statistics = manifest["statistics"]
    _require(isinstance(statistics, dict), "statistics must be an object")
    _exact_keys(statistics, STATISTICS_KEYS, label="statistics")
    _require(statistics["alpha"] == 0.05, "alpha must be frozen at 0.05")
    _require(statistics["confidenceLevel"] == 0.95, "confidenceLevel must be 0.95")
    for name in ("bootstrapSeed", "permutationSeed"):
        _require(
            isinstance(statistics[name], str) and bool(statistics[name]),
            f"{name} must be nonempty",
        )
    for name in ("bootstrapReplicates", "permutationReplicates"):
        _require(
            isinstance(statistics[name], int)
            and not isinstance(statistics[name], bool)
            and statistics[name] >= 99,
            f"{name} must be an integer >= 99",
        )
    _require(statistics["bootstrapMethod"] == BOOTSTRAP_METHOD, "bootstrap method mismatch")
    _require(statistics["permutationMethod"] == PERMUTATION_METHOD, "permutation method mismatch")
    _require(statistics["holmMethod"] == HOLM_METHOD, "Holm method mismatch")
    exact_max = statistics["exactPermutationMaxDiscordances"]
    _require(
        isinstance(exact_max, int)
        and not isinstance(exact_max, bool)
        and 0 <= exact_max <= 20,
        "exactPermutationMaxDiscordances must be an integer in [0,20]",
    )

    implementation = manifest["implementation"]
    _require(isinstance(implementation, dict), "implementation must be an object")
    _exact_keys(implementation, IMPLEMENTATION_KEYS, label="implementation")
    scorer_sha = sha256_file(Path(__file__).resolve())
    _require(
        _sha256(implementation["scorerSha256"], label="frozen scorer hash") == scorer_sha,
        "frozen scorer implementation hash mismatch",
    )
    _require(
        _sha256(implementation["runnerSha256"], label="frozen runner hash")
        == sha256_file(Path(runner.__file__).resolve()),
        "frozen runner implementation hash mismatch",
    )
    return manifest


def _load_gold(
    campaign_root: Path, binding: Mapping[str, Any]
) -> tuple[list[dict[str, str]], list[str], str]:
    path = _safe_bound_path(campaign_root, binding["path"], label="privateGold")
    observed_sha = sha256_file(path)
    _require(observed_sha == binding["sha256"], "privateGold file hash mismatch")
    raw_rows = load_jsonl(path, label="privateGold")
    _require(sha256_file(path) == observed_sha, "privateGold changed while being read")
    _require(len(raw_rows) == binding["rows"], "privateGold row count mismatch")
    rows: list[dict[str, str]] = []
    ids: list[str] = []
    seen: set[str] = set()
    for position, row in enumerate(raw_rows):
        _exact_keys(row, GOLD_KEYS, label=f"privateGold row {position}")
        case_id = row["id"]
        _require(
            isinstance(case_id, str) and OPAQUE_ID_RE.fullmatch(case_id) is not None,
            f"privateGold row {position} has invalid opaque ID",
        )
        _require(case_id not in seen, f"duplicate privateGold ID: {case_id}")
        seen.add(case_id)
        _require(row["domain"] in DOMAINS, f"invalid domain for {case_id}")
        _require(row["label"] in LABELS, f"invalid gold label for {case_id}")
        ids.append(case_id)
        rows.append({"id": case_id, "domain": row["domain"], "label": row["label"]})
    ids_sha = canonical_digest(ids)
    _require(ids_sha == binding["orderedIdsSha256"], "privateGold ordered IDs hash mismatch")
    counts = {(domain, label): 0 for domain, label in CELLS}
    for row in rows:
        counts[(row["domain"], row["label"])] += 1
    _require(all(counts[cell] > 0 for cell in CELLS), "all four domain/label cells must be nonempty")
    return rows, ids, observed_sha


def _validate_runner_matrix(
    validated: Mapping[str, Any],
    *,
    campaign_id: str,
) -> tuple[dict[str, list[str | None]], list[str], dict[str, Any]]:
    expected_validated_keys = {
        "manifest",
        "schedule",
        "campaignReceipt",
        "unitReceipts",
        "unitResults",
        "scientificRows",
        "runtimeIdentity",
    }
    _require(set(validated) == expected_validated_keys, "runner validator return schema mismatch")
    manifest = validated["manifest"]
    schedule = validated["schedule"]
    campaign_receipt = validated["campaignReceipt"]
    unit_receipts = validated["unitReceipts"]
    unit_results = validated["unitResults"]
    scientific_rows = validated["scientificRows"]
    runtime_identity = validated["runtimeIdentity"]
    _require(isinstance(manifest, dict), "runner validator manifest must be an object")
    _require(isinstance(schedule, dict), "runner validator schedule must be an object")
    _require(isinstance(campaign_receipt, dict), "runner validator campaign receipt must be an object")
    _require(isinstance(runtime_identity, dict), "runner validator runtime identity must be an object")
    _require(manifest.get("campaignId") == campaign_id, "runner/scorer campaignId mismatch")
    _require(campaign_receipt.get("campaignId") == campaign_id, "runner receipt campaignId mismatch")
    units = manifest.get("units")
    ordered_unit_ids = schedule.get("orderedUnitIds")
    _require(isinstance(units, list) and bool(units), "runner manifest unit inventory missing")
    _require(
        isinstance(ordered_unit_ids, list) and len(ordered_unit_ids) == len(units),
        "runner schedule/unit inventory mismatch",
    )
    _require(
        isinstance(unit_receipts, list)
        and isinstance(unit_results, list)
        and len(unit_receipts) == len(unit_results) == len(ordered_unit_ids),
        "runner per-unit validation coverage mismatch",
    )
    _require(
        [row.get("unitId") if isinstance(row, dict) else None for row in unit_receipts]
        == ordered_unit_ids,
        "runner unit receipts do not cover exact schedule order",
    )
    _require(
        [row.get("unitId") if isinstance(row, dict) else None for row in unit_results]
        == ordered_unit_ids,
        "runner unit results do not cover exact schedule order",
    )
    unit_by_id: dict[str, Mapping[str, Any]] = {}
    for position, unit in enumerate(units):
        _require(
            isinstance(unit, dict) and set(unit) == runner.UNIT_KEYS,
            f"runner unit {position} schema",
        )
        unit_id = unit["unitId"]
        _require(
            isinstance(unit_id, str) and unit_id not in unit_by_id,
            f"runner unit {position} ID",
        )
        unit_by_id[unit_id] = unit
    _require(set(unit_by_id) == set(ordered_unit_ids), "runner schedule does not cover every unit")

    scientific_units = {
        unit_id: unit
        for unit_id, unit in unit_by_id.items()
        if unit["producesScientificOutcome"] is True
    }
    _require(isinstance(scientific_rows, list), "runner scientificRows must be a list")
    _require(
        len(scientific_rows) == len(scientific_units),
        "runner scientific row/unit coverage mismatch",
    )
    matrix: dict[tuple[str, str], str | None] = {}
    combined_rows: list[dict[str, Any]] = []
    for position, row in enumerate(scientific_rows):
        _require(isinstance(row, dict), f"runner scientific row {position} must be an object")
        _exact_keys(row, COMBINED_PREDICTION_KEYS, label=f"runner scientific row {position}")
        unit_id = row["unitId"]
        _require(unit_id in scientific_units, f"runner scientific row {position} has unknown unit")
        unit = scientific_units[unit_id]
        _require(
            unit["caseId"] == row["id"]
            and unit["armId"] == row["armId"]
            and unit["stageId"] == "answer",
            f"runner scientific row {position} is not its exact answer-stage coordinate",
        )
        case_id = row["id"]
        arm_id = row["armId"]
        outcome = row["outcome"]
        _require(
            isinstance(case_id, str) and OPAQUE_ID_RE.fullmatch(case_id) is not None,
            f"runner scientific row {position} has invalid opaque ID",
        )
        _require(
            arm_id in RUNNER_ARM_ORDER,
            f"runner scientific row {position} has non-frozen arm",
        )
        _require(
            outcome is None or (isinstance(outcome, str) and outcome in OUTCOMES),
            f"runner scientific row {position} has invalid outcome",
        )
        coordinate = (case_id, arm_id)
        _require(coordinate not in matrix, f"duplicate runner answer coordinate: {coordinate}")
        matrix[coordinate] = outcome
        combined_rows.append(dict(row))

    case_ids = sorted({case_id for case_id, _arm in matrix})
    _require(bool(case_ids), "runner campaign has no scientific cases")
    expected_coordinates = {
        (case_id, arm) for case_id in case_ids for arm in RUNNER_ARM_ORDER
    }
    missing = expected_coordinates - set(matrix)
    extra = set(matrix) - expected_coordinates
    _require(
        not missing
        and not extra
        and len(matrix) == len(case_ids) * len(RUNNER_ARM_ORDER),
        f"runner answer matrix is not exact case x 8-arm coverage: missing={len(missing)}, extra={len(extra)}",
    )
    all_outcomes = {
        paper_arm: [matrix[(case_id, runner_arm)] for case_id in case_ids]
        for paper_arm, runner_arm in RUNNER_ARM_BY_PAPER_ARM.items()
    }
    evidence = {
        "unitManifestSha256": manifest["manifestSha256"],
        "scheduleSha256": schedule["scheduleSha256"],
        "campaignReceiptSha256": campaign_receipt["receiptSha256"],
        "scientificPredictionsSha256": campaign_receipt["scientificPredictionsSha256"],
        "combinedScientificRows": len(scientific_rows),
        "combinedScientificRowsSha256": canonical_digest(combined_rows),
        "validatedSingletonUnits": len(unit_receipts),
        "answerStageUnits": len(scientific_units),
        "caseOrder": "lexicographic_opaque_id_v1",
        "caseIdsSha256": canonical_digest(case_ids),
        "runnerArmByPaperArm": dict(RUNNER_ARM_BY_PAPER_ARM),
        "runtimeIdentitySha256": runtime_identity["identitySha256"],
    }
    return all_outcomes, case_ids, evidence


def _cell_indices(gold_rows: Sequence[Mapping[str, str]]) -> dict[tuple[str, str], list[int]]:
    result: dict[tuple[str, str], list[int]] = {cell: [] for cell in CELLS}
    for index, row in enumerate(gold_rows):
        result[(row["domain"], row["label"])].append(index)
    return result


def _arm_metrics(
    outcomes: Sequence[str | None], gold_rows: Sequence[Mapping[str, str]]
) -> tuple[dict[str, Any], list[bool]]:
    correctness = [outcome == gold["label"] for outcome, gold in zip(outcomes, gold_rows, strict=True)]
    indices = _cell_indices(gold_rows)
    cells: dict[str, Any] = {}
    cell_accuracies: list[float] = []
    for domain, label in CELLS:
        cohort = indices[(domain, label)]
        correct = sum(correctness[index] for index in cohort)
        accuracy = correct / len(cohort)
        key = f"{domain}|{label}"
        cells[key] = {"n": len(cohort), "correct": correct, "accuracy": accuracy}
        cell_accuracies.append(accuracy)
    domains: dict[str, Any] = {}
    for domain in DOMAINS:
        accuracies = [cells[f"{domain}|{label}"]["accuracy"] for label in LABELS]
        domains[domain] = {
            "n": sum(cells[f"{domain}|{label}"]["n"] for label in LABELS),
            "labelBalancedAccuracy": sum(accuracies) / 2,
        }
    correct_total = sum(correctness)
    metrics = {
        "n": len(gold_rows),
        "correct": correct_total,
        "wrong": len(gold_rows) - correct_total,
        "nullPredictionsScoredWrong": sum(outcome is None for outcome in outcomes),
        "abstainPredictionsScoredWrong": sum(outcome == "ABSTAIN" for outcome in outcomes),
        "rawAccuracy": correct_total / len(gold_rows),
        "macroBalancedAccuracy": sum(cell_accuracies) / 4,
        "cells": cells,
        "domains": domains,
    }
    return metrics, correctness


def _binomial_upper_tail(successes: int, trials: int) -> float:
    if trials == 0:
        return 1.0
    numerator = sum(math.comb(trials, k) for k in range(successes, trials + 1))
    return numerator / (2**trials)


def one_sided_exact_mcnemar(rescues: int, harms: int) -> float:
    return _binomial_upper_tail(rescues, rescues + harms)


def two_sided_exact_mcnemar(rescues: int, harms: int) -> float:
    discordant = rescues + harms
    if discordant == 0:
        return 1.0
    return min(
        1.0,
        2.0 * _binomial_upper_tail(max(rescues, harms), discordant),
    )


def _observed_deltas(
    differences: Sequence[int], cell_indices: Mapping[tuple[str, str], Sequence[int]]
) -> tuple[float, float, dict[str, float]]:
    cell_deltas = {
        f"{domain}|{label}": sum(differences[index] for index in cell_indices[(domain, label)])
        / len(cell_indices[(domain, label)])
        for domain, label in CELLS
    }
    mba = sum(cell_deltas.values()) / 4
    raw = sum(differences) / len(differences)
    domain_deltas = {
        domain: sum(cell_deltas[f"{domain}|{label}"] for label in LABELS) / 2
        for domain in DOMAINS
    }
    return mba, raw, domain_deltas


def _lower_quantile(samples: Sequence[float], alpha: float) -> float:
    _require(bool(samples), "cannot take a quantile of no samples")
    ordered = sorted(samples)
    index = math.floor(alpha * (len(ordered) - 1))
    return ordered[index]


def stratified_paired_bootstrap(
    differences: Sequence[int],
    cell_indices: Mapping[tuple[str, str], Sequence[int]],
    *,
    seed: str,
    replicates: int,
    alpha: float,
    candidate_arm: str,
    comparator_arm: str,
) -> dict[str, Any]:
    rng = _stable_rng(seed, candidate_arm, comparator_arm, "bootstrap")
    mba_samples: list[float] = []
    raw_samples: list[float] = []
    domain_samples: dict[str, list[float]] = {domain: [] for domain in DOMAINS}
    cohorts = {cell: tuple(cell_indices[cell]) for cell in CELLS}
    for _ in range(replicates):
        cell_means: dict[tuple[str, str], float] = {}
        sampled_sum = 0
        sampled_n = 0
        for cell in CELLS:
            cohort = cohorts[cell]
            total = 0
            for _position in cohort:
                total += differences[cohort[rng.randrange(len(cohort))]]
            cell_means[cell] = total / len(cohort)
            sampled_sum += total
            sampled_n += len(cohort)
        mba_samples.append(sum(cell_means.values()) / 4)
        raw_samples.append(sampled_sum / sampled_n)
        for domain in DOMAINS:
            domain_samples[domain].append(
                sum(cell_means[(domain, label)] for label in LABELS) / 2
            )
    return {
        "method": BOOTSTRAP_METHOD,
        "replicates": replicates,
        "oneSidedConfidenceLevel": 1 - alpha,
        "macroBalancedRiskDifferenceLowerBound": _lower_quantile(mba_samples, alpha),
        "rawRiskDifferenceLowerBound": _lower_quantile(raw_samples, alpha),
        "domainLabelBalancedRiskDifferenceLowerBounds": {
            domain: _lower_quantile(domain_samples[domain], alpha) for domain in DOMAINS
        },
    }


def stratified_paired_permutation(
    differences: Sequence[int],
    cell_indices: Mapping[tuple[str, str], Sequence[int]],
    *,
    observed_mba: float,
    seed: str,
    replicates: int,
    exact_max_discordances: int,
    candidate_arm: str,
    comparator_arm: str,
) -> dict[str, Any]:
    weights_by_cell: list[tuple[int, float]] = []
    flat_weights: list[float] = []
    for cell in CELLS:
        cohort = cell_indices[cell]
        discordant = sum(differences[index] != 0 for index in cohort)
        weight = 1.0 / (4 * len(cohort))
        weights_by_cell.append((discordant, weight))
        flat_weights.extend([weight] * discordant)
    discordant_total = len(flat_weights)
    tolerance = 1e-15
    if discordant_total == 0:
        return {
            "method": PERMUTATION_METHOD,
            "mode": "degenerate_no_discordance",
            "discordant": 0,
            "evaluations": 1,
            "plusOneCorrection": False,
            "oneSidedPValue": 1.0,
        }
    if discordant_total <= exact_max_discordances:
        evaluations = 1 << discordant_total
        extreme = 0
        for bits in range(evaluations):
            statistic = 0.0
            for index, weight in enumerate(flat_weights):
                statistic += weight if bits & (1 << index) else -weight
            if statistic + tolerance >= observed_mba:
                extreme += 1
        return {
            "method": PERMUTATION_METHOD,
            "mode": "exact_conditional_enumeration",
            "discordant": discordant_total,
            "evaluations": evaluations,
            "plusOneCorrection": False,
            "oneSidedPValue": extreme / evaluations,
        }

    rng = _stable_rng(seed, candidate_arm, comparator_arm, "permutation")
    extreme = 0
    for _ in range(replicates):
        statistic = 0.0
        for count, weight in weights_by_cell:
            if count:
                positives = rng.getrandbits(count).bit_count()
                statistic += (2 * positives - count) * weight
        if statistic + tolerance >= observed_mba:
            extreme += 1
    return {
        "method": PERMUTATION_METHOD,
        "mode": "seeded_monte_carlo",
        "discordant": discordant_total,
        "evaluations": replicates,
        "plusOneCorrection": True,
        "oneSidedPValue": (extreme + 1) / (replicates + 1),
    }


def _comparison(
    candidate: Sequence[bool],
    reference: Sequence[bool],
    gold_rows: Sequence[Mapping[str, str]],
    *,
    candidate_arm: str,
    comparator_arm: str,
    statistics: Mapping[str, Any],
) -> dict[str, Any]:
    differences = [int(left) - int(right) for left, right in zip(candidate, reference, strict=True)]
    rescues = sum(value == 1 for value in differences)
    harms = sum(value == -1 for value in differences)
    both_correct = sum(left and right for left, right in zip(candidate, reference, strict=True))
    both_wrong = len(differences) - rescues - harms - both_correct
    cells = _cell_indices(gold_rows)
    mba_delta, raw_delta, domain_deltas = _observed_deltas(differences, cells)
    bootstrap = stratified_paired_bootstrap(
        differences,
        cells,
        seed=statistics["bootstrapSeed"],
        replicates=statistics["bootstrapReplicates"],
        alpha=statistics["alpha"],
        candidate_arm=candidate_arm,
        comparator_arm=comparator_arm,
    )
    permutation = stratified_paired_permutation(
        differences,
        cells,
        observed_mba=mba_delta,
        seed=statistics["permutationSeed"],
        replicates=statistics["permutationReplicates"],
        exact_max_discordances=statistics["exactPermutationMaxDiscordances"],
        candidate_arm=candidate_arm,
        comparator_arm=comparator_arm,
    )
    cell_deltas = {
        f"{domain}|{label}": sum(differences[index] for index in cells[(domain, label)])
        / len(cells[(domain, label)])
        for domain, label in CELLS
    }
    return {
        "candidateArm": candidate_arm,
        "comparatorArm": comparator_arm,
        "macroBalancedRiskDifference": mba_delta,
        "rawRiskDifference": raw_delta,
        "cellRiskDifferences": cell_deltas,
        "domainLabelBalancedRiskDifferences": domain_deltas,
        "pairedDiscordances": {
            "rescues": rescues,
            "harms": harms,
            "net": rescues - harms,
            "discordant": rescues + harms,
            "bothCorrect": both_correct,
            "bothWrong": both_wrong,
        },
        "secondaryRawExactMcNemar": {
            "oneSidedPValue": one_sided_exact_mcnemar(rescues, harms),
            "twoSidedPValue": two_sided_exact_mcnemar(rescues, harms),
        },
        "stratifiedPairedBootstrap": bootstrap,
        "primaryMbaPermutation": permutation,
    }


def holm_adjust(p_values: Mapping[str, float], alpha: float) -> dict[str, dict[str, Any]]:
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    total = len(ordered)
    running = 0.0
    adjusted: dict[str, dict[str, Any]] = {}
    for zero_rank, (name, p_value) in enumerate(ordered):
        rank = zero_rank + 1
        running = max(running, min(1.0, (total - zero_rank) * p_value))
        adjusted[name] = {
            "rank": rank,
            "rawPValue": p_value,
            "adjustedPValue": running,
            "rejectAtAlpha": running <= alpha,
        }
    return {name: adjusted[name] for name in p_values}


def build_report(
    *,
    manifest_path: Path,
    expected_manifest_file_sha256: str,
    runner_validator: Callable[..., Mapping[str, Any]] = runner.validate_completed_campaign,
    source_anchor_verifier: Callable[..., Any] = runner.verify_source_git_anchor,
    campaign_anchor_verifier: Callable[..., Any] = runner.verify_campaign_git_anchor,
    runtime_identity_verifier: Callable[..., Any] = runner.frozen_runtime_identity,
) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    manifest = _load_manifest(manifest_path, expected_manifest_file_sha256)
    campaign_root = manifest_path.parent
    runner_binding = manifest["runnerCampaign"]
    unit_manifest_path = _safe_bound_path(
        campaign_root,
        runner_binding["unitManifestPath"],
        label="runner unit manifest",
    )
    schedule_path = _safe_bound_path(
        campaign_root,
        runner_binding["schedulePath"],
        label="runner schedule",
    )
    output_directory = _safe_bound_directory(
        campaign_root,
        runner_binding["outputDirectory"],
        label="runner output directory",
    )
    campaign_receipt_path = _safe_bound_path(
        output_directory,
        "campaign_receipt.json",
        label="runner campaign receipt",
    )
    combined_predictions_path = _safe_bound_path(
        output_directory,
        "scientific_predictions.jsonl",
        label="runner combined predictions",
    )
    _require(
        sha256_file(campaign_receipt_path)
        == runner_binding["campaignReceiptFileSha256"],
        "runner campaign receipt file hash mismatch",
    )
    _require(
        sha256_file(combined_predictions_path)
        == runner_binding["scientificPredictionsFileSha256"],
        "runner combined prediction file hash mismatch",
    )
    try:
        validated_runner = runner_validator(
            unit_manifest_path=unit_manifest_path,
            expected_unit_manifest_file_sha256=runner_binding[
                "unitManifestFileSha256"
            ],
            schedule_path=schedule_path,
            expected_schedule_file_sha256=runner_binding["scheduleFileSha256"],
            expected_campaign_git_commit=runner_binding["campaignGitCommit"],
            output_dir=output_directory,
            source_anchor_verifier=source_anchor_verifier,
            campaign_anchor_verifier=campaign_anchor_verifier,
            runtime_identity_verifier=runtime_identity_verifier,
        )
    except runner.SingletonCampaignError as error:
        raise CampaignScoreError(f"runner campaign validation failed: {error}") from error
    _require(
        isinstance(validated_runner, Mapping),
        "runner validator did not return a mapping",
    )
    all_outcomes, expected_ids, runner_evidence = _validate_runner_matrix(
        validated_runner,
        campaign_id=manifest["campaignId"],
    )
    campaign_receipt = validated_runner["campaignReceipt"]
    _require(
        campaign_receipt["receiptSha256"] == runner_binding["campaignReceiptSha256"],
        "runner campaign receipt self-hash binding mismatch",
    )
    _require(
        campaign_receipt["scientificPredictionsSha256"]
        == runner_binding["scientificPredictionsFileSha256"],
        "runner combined prediction receipt binding mismatch",
    )
    _require(
        campaign_receipt["campaignGitCommit"] == runner_binding["campaignGitCommit"],
        "runner campaign Git binding mismatch",
    )
    _require(
        sha256_file(campaign_receipt_path)
        == runner_binding["campaignReceiptFileSha256"]
        and sha256_file(combined_predictions_path)
        == runner_binding["scientificPredictionsFileSha256"],
        "runner campaign artifacts changed during validation",
    )
    _require(
        sha256_file(unit_manifest_path) == runner_binding["unitManifestFileSha256"]
        and sha256_file(schedule_path) == runner_binding["scheduleFileSha256"]
        and sha256_file(Path(runner.__file__).resolve())
        == manifest["implementation"]["runnerSha256"],
        "runner source artifacts changed during validation",
    )
    expected_ids_sha = canonical_digest(expected_ids)
    _require(
        len(expected_ids) == manifest["privateGold"]["rows"],
        "runner case count differs from frozen privateGold denominator",
    )
    _require(
        expected_ids_sha == manifest["privateGold"]["orderedIdsSha256"],
        "runner case order does not match frozen privateGold binding",
    )
    # This is deliberately the first read of the private scoring projection.
    # The runner validator has already checked every singleton unit and
    # the exact combined prediction bytes, and the scorer has closed the full
    # case-by-eight-arm answer-stage matrix.
    gold_rows, gold_ids, gold_sha = _load_gold(campaign_root, manifest["privateGold"])
    _require(gold_ids == expected_ids, "privateGold ID/order differs from runner case order")

    arm_metrics: dict[str, Any] = {}
    correctness: dict[str, list[bool]] = {}
    for arm in ARM_ORDER:
        metrics, vector = _arm_metrics(all_outcomes[arm], gold_rows)
        arm_metrics[arm] = metrics
        correctness[arm] = vector

    comparisons: dict[str, Any] = {}
    for comparator in PRIMARY_COMPARATORS:
        comparisons[comparator] = _comparison(
            correctness[PRIMARY_CANDIDATE],
            correctness[comparator],
            gold_rows,
            candidate_arm=PRIMARY_CANDIDATE,
            comparator_arm=comparator,
            statistics=manifest["statistics"],
        )

    alpha = manifest["statistics"]["alpha"]
    component_gates: dict[str, Any] = {}
    for comparator in PRIMARY_COMPARATORS:
        comparison = comparisons[comparator]
        p_value = comparison["primaryMbaPermutation"]["oneSidedPValue"]
        lower_bound = comparison["stratifiedPairedBootstrap"][
            "macroBalancedRiskDifferenceLowerBound"
        ]
        component_gates[comparator] = {
            "oneSidedPermutationPValue": p_value,
            "oneSidedBootstrapLowerBound": lower_bound,
            "pBelowAlpha": p_value < alpha,
            "lowerBoundAboveZero": lower_bound > 0,
            "passed": p_value < alpha and lower_bound > 0,
        }
    iut_passed = all(component_gates[name]["passed"] for name in PRIMARY_COMPARATORS)
    p_values = {
        name: comparisons[name]["primaryMbaPermutation"]["oneSidedPValue"]
        for name in PRIMARY_COMPARATORS
    }
    holm = holm_adjust(p_values, alpha)

    report: dict[str, Any] = {
        "schemaVersion": 1,
        "protocol": PROTOCOL,
        "status": "SCORED_FULL_DENOMINATOR",
        "campaignId": manifest["campaignId"],
        "goldJoinLocation": "this_scorer_only",
        "candidateArm": PRIMARY_CANDIDATE,
        "comparatorArms": list(PRIMARY_COMPARATORS),
        "bindings": {
            "campaignManifestPath": str(manifest_path),
            "campaignManifestFileSha256": expected_manifest_file_sha256,
            "campaignManifestSelfHash": manifest["selfHash"],
            "privateGoldPath": manifest["privateGold"]["path"],
            "privateGoldSha256": gold_sha,
            "runnerCampaign": {
                **dict(runner_binding),
                **runner_evidence,
                "validatedReadOnlyBeforeGoldOpen": True,
                "perArmPredictionAdapterUsed": False,
            },
            "scorerSha256": sha256_file(Path(__file__).resolve()),
            "runnerSha256": sha256_file(Path(runner.__file__).resolve()),
        },
        "denominator": {
            "n": len(gold_rows),
            "orderedIdsSha256": expected_ids_sha,
            "cellCounts": {
                f"{domain}|{label}": sum(
                    row["domain"] == domain and row["label"] == label for row in gold_rows
                )
                for domain, label in CELLS
            },
            "missingRowsDropped": 0,
            "nullAndAbstainRule": "retained_on_full_denominator_and_scored_wrong",
        },
        "primaryEndpoint": {
            "name": "four_cell_macro_balanced_accuracy",
            "cells": [f"{domain}|{label}" for domain, label in CELLS],
            "cellWeight": 0.25,
        },
        "arms": arm_metrics,
        "comparisons": comparisons,
        "primaryFixedIntersectionUnionTest": {
            "alpha": alpha,
            "membership": list(PRIMARY_COMPARATORS),
            "rule": "every MBA permutation p < alpha AND every one-sided MBA bootstrap lower bound > 0",
            "components": component_gates,
            "passed": iut_passed,
            "primarySuperiorityClaimAuthorized": iut_passed,
        },
        "secondaryHolm": {
            "method": HOLM_METHOD,
            "family": list(PRIMARY_COMPARATORS),
            "alpha": alpha,
            "components": holm,
            "doesNotReplacePrimaryIut": True,
        },
        "scopeLimitations": [
            "Private gold is an exact three-field scoring projection produced and frozen by a solver-inaccessible upstream supervisor; richer private consensus is not consumed directly.",
            "The imported read-only runner validator checks every registry, raw trace, normalized result, unit receipt, combined prediction byte, and campaign receipt; these are local structural/hash records, not provider-signed attestations.",
            "The percentile bootstrap lower bound is deterministic but is not an exact finite-sample confidence procedure.",
            "Singleton execution is the analysis-unit assumption; this scorer does not establish population representativeness.",
            "This core does not implement cost matching, domain noninferiority guards, or broader deployment claims.",
        ],
    }
    report["reportSha256"] = canonical_digest(report)
    return report


def write_report(path: Path, report: Mapping[str, Any]) -> None:
    unresolved = path
    _require(
        not unresolved.exists() and not unresolved.is_symlink(),
        f"refusing to overwrite output: {unresolved}",
    )
    path = unresolved.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        report,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        allow_nan=False,
    ).encode("utf-8") + b"\n"
    try:
        with path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as error:
        raise CampaignScoreError(f"refusing to overwrite output: {path}") from error
    reloaded = load_json_object(path, label="score report")
    _verify_self_hash(reloaded, "reportSha256", label="score report")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-manifest", type=Path, required=True)
    parser.add_argument("--expected-campaign-manifest-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = build_report(
            manifest_path=args.campaign_manifest,
            expected_manifest_file_sha256=args.expected_campaign_manifest_sha256,
        )
        write_report(args.output, report)
    except (CampaignScoreError, KeyError, TypeError, ValueError, IndexError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": report["status"],
                "n": report["denominator"]["n"],
                "iutPassed": report["primaryFixedIntersectionUnionTest"]["passed"],
                "reportSha256": report["reportSha256"],
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
