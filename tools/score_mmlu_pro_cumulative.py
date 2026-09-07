#!/usr/bin/env python3
"""Audit and pool the two frozen Mini Artichokes MMLU-Pro cohorts."""
from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.score_mmlu_pro_confirmation import (
    answer_rows,
    canonical_bytes,
    load_json,
    load_jsonl,
    sha256_file,
    two_sided,
    upper_tail,
)
from tools.run_ensemble_file_agent import match_answer_to_option, parse_mcq_options


PROTOCOL = "mini_artichokes_mmlu_pro_cumulative_2000_v1"
BOOTSTRAP_SEED = "mini-mmlu-pro-cumulative-2000-paired-bootstrap-v1"
ALPHA = 0.025


@dataclass(frozen=True)
class CohortSpec:
    name: str
    public: Path
    private: Path
    source_campaign: Path
    generic_campaign: Path
    overlap_campaign: Path
    score: Path
    expected_score_sha256: str


COHORTS = (
    CohortSpec(
        name="confirmation1",
        public=REPO_ROOT / "benchmarks/mmlu_pro_confirmation_v1/mmlu_pro_stratified1000.public.jsonl",
        private=REPO_ROOT / "benchmarks/mmlu_pro_confirmation_v1/mmlu_pro_stratified1000.private.jsonl",
        source_campaign=REPO_ROOT / "runs/mini-mmlu-pro-confirmation-v1-20260901",
        generic_campaign=REPO_ROOT / "runs/mini-mmlu-pro-generic-judge-v1-20260901",
        overlap_campaign=REPO_ROOT / "runs/mini-mmlu-pro-overlap-judge-v1-20260901",
        score=REPO_ROOT / "benchmark_reports/2026-09-01-mini-mmlu-pro-confirmation/score.json",
        expected_score_sha256="5ba78d945aff95e5c3b7d93b0a44d592bbe16b2587d4d2228d179f5e1339128f",
    ),
    CohortSpec(
        name="replication2",
        public=REPO_ROOT / "benchmarks/mmlu_pro_confirmation_replication2_v1/mmlu_pro_stratified1000.public.jsonl",
        private=REPO_ROOT / "benchmarks/mmlu_pro_confirmation_replication2_v1/mmlu_pro_stratified1000.private.jsonl",
        source_campaign=REPO_ROOT / "runs/mini-mmlu-pro-confirmation-replication2-v1-20260901",
        generic_campaign=REPO_ROOT / "runs/mini-mmlu-pro-generic-judge-replication2-v1-20260901",
        overlap_campaign=REPO_ROOT / "runs/mini-mmlu-pro-overlap-judge-replication2-v1-20260901",
        score=REPO_ROOT / "benchmark_reports/2026-09-01-mini-mmlu-pro-confirmation-replication2/score.json",
        expected_score_sha256="2442d9018a0241e203500f85e859d76c78cda52f74277090856f5b40d3ca7685",
    ),
)


def bootstrap_difference(
    candidate: list[bool],
    reference: list[bool],
    strata: list[str],
    samples: int = 20_000,
) -> dict[str, Any]:
    by_stratum: dict[str, list[int]] = {}
    for index, stratum in enumerate(strata):
        by_stratum.setdefault(stratum, []).append(index)
    rng = random.Random(BOOTSTRAP_SEED)
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
        "stratification": "cohort_x_category",
    }


def compare_correctness(
    candidate: list[bool],
    reference: list[bool],
    strata: list[str],
    samples: int = 20_000,
) -> dict[str, Any]:
    rescues = sum(a and not b for a, b in zip(candidate, reference, strict=True))
    harms = sum(b and not a for a, b in zip(candidate, reference, strict=True))
    return {
        "rescues": rescues,
        "harms": harms,
        "netCorrect": rescues - harms,
        "discordant": rescues + harms,
        "oneSidedExactMcNemarP": upper_tail(rescues, rescues + harms),
        "twoSidedExactMcNemarP": two_sided(rescues, harms),
        "pairedAccuracyDifference": bootstrap_difference(candidate, reference, strata, samples),
    }


def fixed_sequence(comparisons: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    reached = True
    result: list[dict[str, Any]] = []
    for reference in ("D1", "SC3", "GJ3"):
        comparison = comparisons[f"OJ3_vs_{reference}"]
        rejected = bool(
            reached
            and comparison["netCorrect"] > 0
            and comparison["oneSidedExactMcNemarP"] < ALPHA
        )
        result.append(
            {
                "candidate": "OJ3",
                "reference": reference,
                "confirmatoryReached": reached,
                "rejectedAtAlpha0.025": rejected,
            }
        )
        reached = reached and rejected
    return result


def mapped_vector(
    ids: list[str],
    questions: dict[str, dict[str, Any]],
    answers: dict[str, str],
) -> list[int | None]:
    result: list[int | None] = []
    for case_id in ids:
        value = match_answer_to_option(answers[case_id], parse_mcq_options(questions[case_id]["prompt"]))
        result.append(int(value) if value else None)
    return result


def load_cohort(spec: CohortSpec) -> dict[str, Any]:
    if sha256_file(spec.score) != spec.expected_score_sha256:
        raise ValueError(f"score hash mismatch: {spec.score}")
    prior = load_json(spec.score)
    if sha256_file(spec.public) != prior["publicSha256"]:
        raise ValueError(f"public hash mismatch: {spec.name}")
    if sha256_file(spec.private) != prior["privateSha256"]:
        raise ValueError(f"private hash mismatch: {spec.name}")

    public = load_jsonl(spec.public)
    private = load_jsonl(spec.private)
    ids = [str(row["id"]) for row in public]
    if len(ids) != 1000 or len(set(ids)) != 1000:
        raise ValueError(f"invalid denominator: {spec.name}")
    private_by_id = {str(row["caseId"]): row for row in private}
    if set(ids) != set(private_by_id):
        raise ValueError(f"public/private ID mismatch: {spec.name}")
    questions = {str(row["id"]): row for row in public}
    gold = [int(private_by_id[case_id]["correctOptionIndex"]) for case_id in ids]
    categories = [str(private_by_id[case_id]["category"]) for case_id in ids]

    raw: dict[str, dict[str, str]] = {}
    vectors: dict[str, list[int | None]] = {}
    for draw in ("D1", "D2", "D3"):
        answers_path = spec.source_campaign / f"drafts/d{draw[1:]}/solver/output/answers.jsonl"
        raw[draw] = answer_rows(answers_path, ids)
        vectors[draw] = mapped_vector(ids, questions, raw[draw])
    vectors["SC3"] = []
    for index in range(len(ids)):
        values = [vectors[draw][index] for draw in ("D1", "D2", "D3")]
        majority = next((value for value in values if value is not None and values.count(value) >= 2), values[0])
        vectors["SC3"].append(majority)

    conflict_ids: list[str] | None = None
    for arm, campaign in (("GJ3", spec.generic_campaign), ("OJ3", spec.overlap_campaign)):
        roles = load_jsonl(campaign / "hidden-role-map.jsonl")
        this_ids = [str(row["id"]) for row in roles]
        if conflict_ids is None:
            conflict_ids = this_ids
        elif this_ids != conflict_ids:
            raise ValueError(f"judge conflict mismatch: {spec.name}")
        judged = answer_rows(campaign / "solver/output/answers.jsonl", this_ids)
        selected: dict[str, str] = {}
        for row in roles:
            case_id = str(row["id"])
            matches = [
                key
                for key, answer in row["candidateKeyToAnswer"].items()
                if judged[case_id].strip() == str(answer).strip()
            ]
            if len(matches) == 1:
                role = row["candidateKeyToRole"][matches[0]]
                selected[case_id] = raw["D1"][case_id] if role == "base" else raw["D2"][case_id]
        answers = {case_id: selected.get(case_id, raw["D1"][case_id]) for case_id in ids}
        vectors[arm] = mapped_vector(ids, questions, answers)

    correctness = {
        arm: [value == truth for value, truth in zip(values, gold, strict=True)]
        for arm, values in vectors.items()
    }
    for arm in ("D1", "SC3", "GJ3", "OJ3"):
        if sum(correctness[arm]) != prior["metrics"][arm]["correct"]:
            raise ValueError(f"reconstruction mismatch for {spec.name}/{arm}")
    return {
        "name": spec.name,
        "ids": ids,
        "categories": categories,
        "correctness": correctness,
        "conflictCases": len(conflict_ids or []),
        "scoreSha256": spec.expected_score_sha256,
        "publicSha256": prior["publicSha256"],
        "privateSha256": prior["privateSha256"],
    }


def build_report() -> dict[str, Any]:
    cohorts = [load_cohort(spec) for spec in COHORTS]
    if set(cohorts[0]["ids"]) & set(cohorts[1]["ids"]):
        raise ValueError("cohort IDs are not disjoint")
    arms = ("D1", "D2", "D3", "SC3", "GJ3", "OJ3")
    correctness = {
        arm: [value for cohort in cohorts for value in cohort["correctness"][arm]]
        for arm in arms
    }
    strata = [
        f"{cohort['name']}::{category}"
        for cohort in cohorts
        for category in cohort["categories"]
    ]
    comparisons = {
        f"OJ3_vs_{reference}": compare_correctness(correctness["OJ3"], correctness[reference], strata)
        for reference in ("D1", "SC3", "GJ3")
    }
    comparisons.update(
        {
            "SC3_vs_D1": compare_correctness(correctness["SC3"], correctness["D1"], strata),
            "GJ3_vs_D1": compare_correctness(correctness["GJ3"], correctness["D1"], strata),
        }
    )
    return {
        "protocol": PROTOCOL,
        "n": 2000,
        "alpha": ALPHA,
        "cohorts": [
            {
                key: cohort[key]
                for key in ("name", "conflictCases", "scoreSha256", "publicSha256", "privateSha256")
            }
            for cohort in cohorts
        ],
        "disjointIdIntersection": 0,
        "metrics": {
            arm: {
                "n": len(correctness[arm]),
                "correct": sum(correctness[arm]),
                "accuracy": sum(correctness[arm]) / len(correctness[arm]),
            }
            for arm in arms
        },
        "comparisons": comparisons,
        "fixedSequenceHypotheses": fixed_sequence(comparisons),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite cumulative score: {args.output}")
    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_bytes(report))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
