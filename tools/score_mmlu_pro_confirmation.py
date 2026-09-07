#!/usr/bin/env python3
"""Open MMLU-Pro gold once and score the frozen matched confirmation arms."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.run_ensemble_file_agent import match_answer_to_option, parse_mcq_options


PROTOCOL = "mini_artichokes_mmlu_pro_confirmation_score_v1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def answer_rows(path: Path, ids: list[str]) -> dict[str, str]:
    rows = load_jsonl(path)
    if [row.get("id") for row in rows] != ids:
        raise ValueError(f"answer ID/order mismatch: {path}")
    return {str(row["id"]): str(row.get("finalAnswer") or "") for row in rows}


def upper_tail(successes: int, trials: int) -> float:
    if trials == 0:
        return 1.0
    return sum(math.comb(trials, index) for index in range(successes, trials + 1)) / 2**trials


def two_sided(rescues: int, harms: int) -> float:
    n = rescues + harms
    if n == 0:
        return 1.0
    smaller = min(rescues, harms)
    return min(1.0, 2 * sum(math.comb(n, index) for index in range(smaller + 1)) / 2**n)


def bootstrap(candidate: list[bool], reference: list[bool], strata: list[str], samples: int = 20000) -> dict[str, Any]:
    by_stratum: dict[str, list[int]] = {}
    for index, stratum in enumerate(strata):
        by_stratum.setdefault(stratum, []).append(index)
    rng = random.Random("mini-mmlu-pro-confirmation-paired-bootstrap-v1")
    values: list[float] = []
    for _ in range(samples):
        total = 0
        for indices in by_stratum.values():
            for _item in indices:
                chosen = indices[rng.randrange(len(indices))]
                total += int(candidate[chosen]) - int(reference[chosen])
        values.append(total / len(candidate))
    values.sort()
    return {
        "estimate": (sum(candidate) - sum(reference)) / len(candidate),
        "lower95": values[int(0.025 * samples)],
        "upper95": values[min(samples - 1, int(0.975 * samples))],
        "samples": samples,
    }


def compare(candidate: list[int | None], reference: list[int | None], gold: list[int], strata: list[str]) -> dict[str, Any]:
    left = [value == truth for value, truth in zip(candidate, gold, strict=True)]
    right = [value == truth for value, truth in zip(reference, gold, strict=True)]
    rescues = sum(a and not b for a, b in zip(left, right, strict=True))
    harms = sum(b and not a for a, b in zip(left, right, strict=True))
    return {
        "rescues": rescues,
        "harms": harms,
        "netCorrect": rescues - harms,
        "discordant": rescues + harms,
        "oneSidedExactMcNemarP": upper_tail(rescues, rescues + harms),
        "twoSidedExactMcNemarP": two_sided(rescues, harms),
        "pairedAccuracyDifference": bootstrap(left, right, strata),
    }


def metrics(values: list[int | None], gold: list[int], categories: list[str]) -> dict[str, Any]:
    correct = [value == truth for value, truth in zip(values, gold, strict=True)]
    result: dict[str, Any] = {
        "n": len(values),
        "correct": sum(correct),
        "accuracy": sum(correct) / len(values),
        "unmapped": sum(value is None for value in values),
        "categories": {},
    }
    for category in sorted(set(categories)):
        indices = [index for index, value in enumerate(categories) if value == category]
        count = sum(correct[index] for index in indices)
        result["categories"][category] = {"n": len(indices), "correct": count, "accuracy": count / len(indices)}
    return result


def execution(root: Path) -> dict[str, Any]:
    receipt = load_json(root / "solver/run_receipt.json")
    trace = receipt.get("policyAudit", {}).get("trace", {})
    return {
        "status": receipt.get("status"),
        "model": receipt.get("model"),
        "reasoningEffort": receipt.get("reasoningEffort"),
        "semanticModelInvocations": receipt.get("semanticModelInvocations"),
        "elapsedSec": receipt.get("process", {}).get("elapsedSec"),
        "tokenUsage": trace.get("tokenUsage", {}),
        "receiptSha256": receipt.get("receiptSha256"),
    }


def score(args: argparse.Namespace) -> dict[str, Any]:
    for path, expected in (
        (args.public, args.expected_public_sha256),
        (args.private, args.expected_private_sha256),
        (args.frozen_protocol, args.expected_protocol_sha256),
    ):
        if sha256_file(path) != expected:
            raise ValueError(f"hash mismatch: {path}")
    public = load_jsonl(args.public)
    private = load_jsonl(args.private)
    ids = [str(row["id"]) for row in public]
    if len(ids) != 1000 or len(set(ids)) != 1000:
        raise ValueError("public denominator is not 1,000 unique rows")
    private_by_id = {str(row["caseId"]): row for row in private}
    if set(ids) != set(private_by_id):
        raise ValueError("public/private IDs differ")
    questions = {str(row["id"]): row for row in public}
    gold = [int(private_by_id[case_id]["correctOptionIndex"]) for case_id in ids]
    categories = [str(private_by_id[case_id]["category"]) for case_id in ids]
    raw: dict[str, dict[str, str]] = {}
    vectors: dict[str, list[int | None]] = {}
    for draw in ("D1", "D2", "D3"):
        path = args.source_campaign / f"drafts/d{draw[1:]}/solver/output/answers.jsonl"
        raw[draw] = answer_rows(path, ids)
        vectors[draw] = [
            int(value) if (value := match_answer_to_option(raw[draw][case_id], parse_mcq_options(questions[case_id]["prompt"]))) else None
            for case_id in ids
        ]
    vectors["SC3"] = []
    for index in range(len(ids)):
        values = [vectors[draw][index] for draw in ("D1", "D2", "D3")]
        majority = next((value for value in values if value is not None and values.count(value) >= 2), values[0])
        vectors["SC3"].append(majority)

    conflict_ids: list[str] | None = None
    for arm, campaign in (("GJ3", args.generic_campaign), ("OJ3", args.overlap_campaign)):
        freeze = load_json(campaign / "solver/freeze.json")
        roles = load_jsonl(campaign / "hidden-role-map.jsonl")
        this_ids = [str(row["id"]) for row in roles]
        if conflict_ids is None:
            conflict_ids = this_ids
        elif this_ids != conflict_ids:
            raise ValueError("judge conflict IDs differ")
        judged = answer_rows(campaign / "solver/output/answers.jsonl", this_ids)
        selected: dict[str, str] = {}
        for row in roles:
            case_id = str(row["id"])
            matches = [key for key, answer in row["candidateKeyToAnswer"].items() if judged[case_id].strip() == str(answer).strip()]
            if len(matches) == 1:
                role = row["candidateKeyToRole"][matches[0]]
                selected[case_id] = raw["D1"][case_id] if role == "base" else raw["D2"][case_id]
        values: list[int | None] = []
        for case_id in ids:
            answer = selected.get(case_id, raw["D1"][case_id])
            option = match_answer_to_option(answer, parse_mcq_options(questions[case_id]["prompt"]))
            values.append(int(option) if option else None)
        vectors[arm] = values
        if freeze.get("conflictIdsSha256") != hashlib.sha256(canonical_bytes(this_ids)).hexdigest():
            raise ValueError(f"{arm} conflict hash mismatch")

    report_metrics = {name: metrics(values, gold, categories) for name, values in vectors.items()}
    primary_order = ("D1", "SC3", "GJ3")
    comparisons = {f"OJ3_vs_{reference}": compare(vectors["OJ3"], vectors[reference], gold, categories) for reference in primary_order}
    comparisons.update({
        "SC3_vs_D1": compare(vectors["SC3"], vectors["D1"], gold, categories),
        "GJ3_vs_D1": compare(vectors["GJ3"], vectors["D1"], gold, categories),
    })
    reached = True
    hypotheses = []
    for reference in primary_order:
        item = comparisons[f"OJ3_vs_{reference}"]
        rejected = bool(reached and item["netCorrect"] > 0 and item["oneSidedExactMcNemarP"] < 0.05)
        hypotheses.append({"candidate": "OJ3", "reference": reference, "confirmatoryReached": reached, "rejectedAtAlpha0.05": rejected})
        reached = reached and rejected
    return {
        "protocol": PROTOCOL,
        "n": len(ids),
        "publicSha256": args.expected_public_sha256,
        "privateSha256": args.expected_private_sha256,
        "frozenProtocolSha256": args.expected_protocol_sha256,
        "conflictCases": len(conflict_ids or []),
        "metrics": report_metrics,
        "comparisons": comparisons,
        "fixedSequenceHypotheses": hypotheses,
        "execution": {
            "D1": execution(args.source_campaign / "drafts/d1"),
            "D2": execution(args.source_campaign / "drafts/d2"),
            "D3": execution(args.source_campaign / "drafts/d3"),
            "GJ3": execution(args.generic_campaign),
            "OJ3": execution(args.overlap_campaign),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--expected-public-sha256", required=True)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--expected-private-sha256", required=True)
    parser.add_argument("--frozen-protocol", type=Path, required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--source-campaign", type=Path, required=True)
    parser.add_argument("--generic-campaign", type=Path, required=True)
    parser.add_argument("--overlap-campaign", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = score(args)
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite score: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_bytes(report))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
