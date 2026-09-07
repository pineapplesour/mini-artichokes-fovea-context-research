#!/usr/bin/env python3
"""Score the frozen balanced singleton legal confirmation on all 464 cases."""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
from typing import Any

try:
    from tools import run_batched_structured_legal_dev as hashes
    from tools import score_batched_structured_legal_dev as structured
except ImportError:
    import run_batched_structured_legal_dev as hashes
    import score_batched_structured_legal_dev as structured


PROTOCOL = "mini_artichokes_singleton_legal_confirmation_score_v1"
LABELS = ("기각", "인용됨")


def load_judge(root: Path) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    selected: dict[str, str] = {}
    roles: dict[str, dict[str, str]] = {}
    for shard in sorted(root.glob("shard_*")):
        receipt = json.loads((shard / "receipt.json").read_text(encoding="utf-8"))
        case_id = receipt["id"]
        if case_id in roles:
            raise ValueError(f"duplicate judge case: {case_id}")
        role_rows = json.loads((shard / "hidden-role-map.json").read_text(encoding="utf-8"))
        if len(role_rows) != 1 or role_rows[0]["id"] != case_id:
            raise ValueError(f"invalid hidden role map: {shard}")
        roles[case_id] = role_rows[0]["candidateKeyToDraw"]
        decisions = json.loads((shard / "normalized.json").read_text(encoding="utf-8"))
        if len(decisions) == 1:
            if decisions[0]["id"] != case_id:
                raise ValueError(f"judge decision ID mismatch: {shard}")
            selected[case_id] = decisions[0]["selected"]
        elif decisions:
            raise ValueError(f"multiple normalized judge decisions: {shard}")
    return selected, roles


def judge_vector(
    ids: list[str],
    draws: dict[str, dict[str, dict[str, Any] | None]],
    selected: dict[str, str],
    roles: dict[str, dict[str, str]],
) -> list[str | None]:
    result: list[str | None] = []
    for case_id in ids:
        value = structured.outcome(draws["D1"][case_id])
        if case_id in selected:
            draw = roles[case_id].get(selected[case_id])
            if draw not in draws:
                raise ValueError(f"invalid anonymous role selection: {case_id}")
            value = structured.outcome(draws[draw][case_id])
        result.append(value)
    return result


def upper_tail(successes: int, trials: int) -> float:
    if trials == 0:
        return 1.0
    return sum(math.comb(trials, index) for index in range(successes, trials + 1)) / 2**trials


def two_sided_exact(rescues: int, harms: int) -> float:
    discordant = rescues + harms
    if discordant == 0:
        return 1.0
    smaller = min(rescues, harms)
    return min(1.0, 2 * sum(math.comb(discordant, index) for index in range(smaller + 1)) / 2**discordant)


def bootstrap_delta(
    candidate: list[bool],
    reference: list[bool],
    cells: list[str],
    *,
    samples: int = 20000,
) -> dict[str, float]:
    by_cell: dict[str, list[int]] = {}
    for index, cell in enumerate(cells):
        by_cell.setdefault(cell, []).append(index)
    rng = random.Random("mini-legal-confirmation-v1-paired-bootstrap")
    deltas: list[float] = []
    for _ in range(samples):
        total = 0
        for indices in by_cell.values():
            for _item in indices:
                chosen = indices[rng.randrange(len(indices))]
                total += int(candidate[chosen]) - int(reference[chosen])
        deltas.append(total / len(candidate))
    deltas.sort()
    return {
        "estimate": (sum(candidate) - sum(reference)) / len(candidate),
        "lower95": deltas[int(0.025 * samples)],
        "upper95": deltas[min(samples - 1, int(0.975 * samples))],
        "samples": samples,
    }


def metrics(values: list[str | None], gold: list[str], domains: list[str]) -> dict[str, Any]:
    correct = [value == truth for value, truth in zip(values, gold, strict=True)]
    report: dict[str, Any] = {
        "n": len(values),
        "correct": sum(correct),
        "accuracy": sum(correct) / len(values),
        "null": sum(value is None for value in values),
        "cells": {},
    }
    for domain in sorted(set(domains)):
        for label in LABELS:
            indices = [
                index
                for index, (item_domain, truth) in enumerate(zip(domains, gold, strict=True))
                if item_domain == domain and truth == label
            ]
            count = sum(correct[index] for index in indices)
            report["cells"][f"{domain}:{label}"] = {
                "n": len(indices),
                "correct": count,
                "accuracy": count / len(indices),
            }
    return report


def comparison(
    candidate: list[str | None],
    reference: list[str | None],
    gold: list[str],
    cells: list[str],
) -> dict[str, Any]:
    candidate_correct = [value == truth for value, truth in zip(candidate, gold, strict=True)]
    reference_correct = [value == truth for value, truth in zip(reference, gold, strict=True)]
    rescues = sum(left and not right for left, right in zip(candidate_correct, reference_correct, strict=True))
    harms = sum(right and not left for left, right in zip(candidate_correct, reference_correct, strict=True))
    return {
        "rescues": rescues,
        "harms": harms,
        "netCorrect": rescues - harms,
        "discordant": rescues + harms,
        "oneSidedExactMcNemarP": upper_tail(rescues, rescues + harms),
        "twoSidedExactMcNemarP": two_sided_exact(rescues, harms),
        "pairedAccuracyDifference": bootstrap_delta(candidate_correct, reference_correct, cells),
    }


def execution_summary(root: Path) -> dict[str, Any]:
    receipts = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(root.glob("**/receipt.json"))]
    tokens: dict[str, int] = {}
    for receipt in receipts:
        for key, value in (receipt.get("tokenUsage") or {}).items():
            if isinstance(value, int):
                tokens[key] = tokens.get(key, 0) + value
    return {
        "calls": len(receipts),
        "accepted": sum(receipt.get("status") == "accepted" for receipt in receipts),
        "rejected": sum(receipt.get("status") == "rejected" for receipt in receipts),
        "tokenTotals": tokens,
    }


def score(args: argparse.Namespace) -> dict[str, Any]:
    expected = {
        args.public: args.expected_public_sha256,
        args.private: args.expected_private_sha256,
        args.frozen_protocol: args.expected_protocol_sha256,
    }
    for path, digest in expected.items():
        if hashes.sha256_file(path) != digest:
            raise ValueError(f"hash mismatch: {path}")
    public_rows = structured.load_jsonl(args.public)
    private_rows = structured.load_jsonl(args.private)
    ids = [row["id"] for row in public_rows]
    if len(ids) != 464 or len(set(ids)) != 464:
        raise ValueError("public denominator is not 464 unique cases")
    gold_by_id = {row["caseId"]: row for row in private_rows}
    if set(ids) != set(gold_by_id):
        raise ValueError("public/private ID mismatch")
    public_by_id = {row["id"]: row for row in public_rows}
    gold = [gold_by_id[case_id]["label"] for case_id in ids]
    domains = [gold_by_id[case_id]["domain"] for case_id in ids]
    cells = [f"{domain}:{truth}" for domain, truth in zip(domains, gold, strict=True)]
    expected_cells = {"civil:기각": 136, "civil:인용됨": 136, "tax:기각": 96, "tax:인용됨": 96}
    if {cell: cells.count(cell) for cell in set(cells)} != expected_cells:
        raise ValueError("private domain-by-label balance mismatch")
    draws = {
        arm: structured.load_draw(args.base_root, arm, public_by_id)
        for arm in ("P1", "D1", "D2", "D3")
    }
    for arm, values in draws.items():
        if set(values) != set(ids):
            raise ValueError(f"incomplete base arm: {arm}")
    vectors: dict[str, list[str | None]] = {
        arm: [structured.outcome(draws[arm][case_id]) for case_id in ids]
        for arm in ("P1", "D1", "D2", "D3")
    }
    vectors["SC3"] = [
        structured.sc3(draws["D1"][case_id], draws["D2"][case_id], draws["D3"][case_id])
        for case_id in ids
    ]
    generic_selected, generic_roles = load_judge(args.generic_judge_root)
    overlap_selected, overlap_roles = load_judge(args.overlap_judge_root)
    if generic_roles != overlap_roles:
        raise ValueError("generic and overlap judges do not share conflict IDs and role rotation")
    vectors["GJ3"] = judge_vector(ids, draws, generic_selected, generic_roles)
    vectors["OJ3"] = judge_vector(ids, draws, overlap_selected, overlap_roles)
    report_metrics = {name: metrics(values, gold, domains) for name, values in vectors.items()}
    order = ("GJ3", "P1", "SC3", "D1")
    comparisons = {
        f"OJ3_vs_{reference}": comparison(vectors["OJ3"], vectors[reference], gold, cells)
        for reference in order
    }
    reached = True
    hypotheses: list[dict[str, Any]] = []
    for reference in order:
        value = comparisons[f"OJ3_vs_{reference}"]
        rejected = bool(reached and value["netCorrect"] > 0 and value["oneSidedExactMcNemarP"] < 0.05)
        hypotheses.append(
            {
                "candidate": "OJ3",
                "reference": reference,
                "confirmatoryReached": reached,
                "rejectedAtAlpha0.05": rejected,
            }
        )
        reached = reached and rejected
    return {
        "protocol": PROTOCOL,
        "frozenProtocolSha256": args.expected_protocol_sha256,
        "publicSha256": args.expected_public_sha256,
        "privateSha256": args.expected_private_sha256,
        "n": 464,
        "metrics": report_metrics,
        "comparisons": comparisons,
        "fixedSequenceHypotheses": hypotheses,
        "conflictCases": len(generic_roles),
        "execution": {
            "base": execution_summary(args.base_root),
            "genericJudge": execution_summary(args.generic_judge_root),
            "overlapJudge": execution_summary(args.overlap_judge_root),
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
    parser.add_argument("--base-root", type=Path, required=True)
    parser.add_argument("--generic-judge-root", type=Path, required=True)
    parser.add_argument("--overlap-judge-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = score(args)
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite score: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(hashes.canonical_bytes(report))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
