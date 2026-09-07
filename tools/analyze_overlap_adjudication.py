#!/usr/bin/env python3
"""Private, paired analysis for a frozen overlap-adjudication development run."""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.prepare_plain_codex_file_benchmark import DEFAULT_REGISTRY, canonical_digest, private_exam_rows
from tools.run_ensemble_file_agent import match_answer_to_option, parse_mcq_options


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            raise ValueError(f"blank JSONL line {line_number}: {path}")
        row = json.loads(raw)
        if not isinstance(row, dict):
            raise ValueError(f"non-object JSONL line {line_number}: {path}")
        rows.append(row)
    return rows


def answer_map(path: Path) -> dict[str, str]:
    rows = load_jsonl(path)
    result = {str(row.get("id") or ""): str(row.get("finalAnswer") or "") for row in rows}
    if "" in result or len(result) != len(rows):
        raise ValueError(f"invalid or duplicate answer IDs: {path}")
    return result


def normalize_correct_option(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) == 1 and text.upper() in "ABCDEFGHIJ":
        return str(ord(text.upper()) - ord("A") + 1)
    return text


def one_sided_exact_mcnemar(rescues: int, harms: int) -> float:
    discordant = rescues + harms
    if discordant == 0:
        return 1.0
    numerator = sum(math.comb(discordant, k) for k in range(rescues, discordant + 1))
    return numerator / (2**discordant)


def paired(candidate: dict[str, bool], reference: dict[str, bool], ids: list[str]) -> dict[str, Any]:
    rescues = sum(not reference[case_id] and candidate[case_id] for case_id in ids)
    harms = sum(reference[case_id] and not candidate[case_id] for case_id in ids)
    return {
        "rescues": rescues,
        "harms": harms,
        "net": rescues - harms,
        "delta": (rescues - harms) / len(ids),
        "discordant": rescues + harms,
        "oneSidedExactMcNemarP": one_sided_exact_mcnemar(rescues, harms),
    }


def analyze(campaign_dir: Path, existing_universal: Path, registry_path: Path) -> dict[str, Any]:
    input_dir = campaign_dir / "solver/input"
    question_rows = load_jsonl(input_dir / "questions.jsonl")
    question_by_id = {str(row["id"]): row for row in question_rows}
    gold = private_exam_rows(registry_path)
    fixed_ids = sorted(
        case_id
        for case_id, question in question_by_id.items()
        if question.get("responseFormat") == "mcq"
        and case_id in gold
        and normalize_correct_option((gold[case_id].get("privateGold") or {}).get("correctOptionId"))
    )
    if not fixed_ids:
        raise ValueError("fixed keyed-MCQ cohort is empty")

    manifest_rows = load_jsonl(input_dir / "overlap_manifest.jsonl")
    manifest = {str(row["id"]): row for row in manifest_rows}
    eligible_ids = [case_id for case_id in fixed_ids if (manifest.get(case_id) or {}).get("eligible") is True]

    systems = {
        "base": answer_map(input_dir / "candidates/base.jsonl"),
        "auxiliary1": answer_map(input_dir / "candidates/auxiliary_1.jsonl"),
        "auxiliary2": answer_map(input_dir / "candidates/auxiliary_2.jsonl"),
        "strict": answer_map(campaign_dir / "solver/output/answers.jsonl"),
        "existingUniversal": answer_map(existing_universal),
    }
    systems["auxConsensus"] = {
        case_id: (systems["auxiliary1"][case_id] if case_id in set(eligible_ids) else systems["base"][case_id])
        for case_id in question_by_id
    }

    correctness: dict[str, dict[str, bool]] = {}
    mapped: dict[str, dict[str, str | None]] = {}
    for name, answers in systems.items():
        correctness[name] = {}
        mapped[name] = {}
        for case_id in fixed_ids:
            question = question_by_id[case_id]
            option = match_answer_to_option(answers.get(case_id, ""), parse_mcq_options(str(question.get("prompt") or "")))
            correct = normalize_correct_option((gold[case_id].get("privateGold") or {}).get("correctOptionId"))
            mapped[name][case_id] = option
            correctness[name][case_id] = bool(option and option == correct)

    scores = {
        name: {
            "pass": sum(values.values()),
            "fail": len(fixed_ids) - sum(values.values()),
            "total": len(fixed_ids),
            "accuracy": sum(values.values()) / len(fixed_ids),
            "unmapped": sum(not mapped[name][case_id] for case_id in fixed_ids),
        }
        for name, values in correctness.items()
    }
    vs_base = paired(correctness["strict"], correctness["base"], fixed_ids)
    vs_universal = paired(correctness["strict"], correctness["existingUniversal"], fixed_ids)

    switched_ids = [
        case_id
        for case_id in fixed_ids
        if systems["strict"][case_id] == systems["auxiliary1"][case_id]
        and systems["strict"][case_id] != systems["base"][case_id]
    ]
    switch_count = len(switched_ids)

    per_benchmark: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for case_id in fixed_ids:
        benchmark = str(question_by_id[case_id].get("benchmarkId") or "unknown")
        per_benchmark[benchmark]["n"] += 1
        if not correctness["base"][case_id] and correctness["strict"][case_id]:
            per_benchmark[benchmark]["rescues"] += 1
        if correctness["base"][case_id] and not correctness["strict"][case_id]:
            per_benchmark[benchmark]["harms"] += 1

    domain_guard = all(
        values["harms"] - values["rescues"] <= max(1, math.ceil(0.01 * values["n"]))
        for values in per_benchmark.values()
    )
    eligible = {
        "n": len(eligible_ids),
        "idsSha256": canonical_digest(eligible_ids),
        "basePass": sum(correctness["base"][case_id] for case_id in eligible_ids),
        "auxConsensusPass": sum(correctness["auxConsensus"][case_id] for case_id in eligible_ids),
        "strictPass": sum(correctness["strict"][case_id] for case_id in eligible_ids),
        "existingUniversalPass": sum(correctness["existingUniversal"][case_id] for case_id in eligible_ids),
        "baseOrAuxOraclePass": sum(
            correctness["base"][case_id] or correctness["auxConsensus"][case_id] for case_id in eligible_ids
        ),
        "bothBaseAndAuxWrong": sum(
            not correctness["base"][case_id] and not correctness["auxConsensus"][case_id] for case_id in eligible_ids
        ),
    }

    receipt_path = campaign_dir / "solver/run_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.is_file() else {}
    strict_report_path = campaign_dir / "solver/overlap_validation.json"
    strict_report = json.loads(strict_report_path.read_text(encoding="utf-8")) if strict_report_path.is_file() else {}
    elapsed = float(((receipt.get("process") or {}).get("elapsedSec") or math.inf))
    integrity_ok = bool(receipt.get("status") == "accepted" and (receipt.get("inputIntegrity") or {}).get("passed"))
    strict_ok = bool(strict_report.get("passed"))
    promotion = {
        "developmentOnly": True,
        "integrity": integrity_ok and strict_ok,
        "eligibleAtLeast30": len(eligible_ids) >= 30,
        "baseNetAtLeast5": vs_base["net"] >= 5,
        "baseHarmRatio": vs_base["harms"] <= vs_base["rescues"] // 4,
        "baseAbsoluteHarmsAtMost4": vs_base["harms"] <= 4,
        "baseOneSidedPAtMostPoint10": vs_base["oneSidedExactMcNemarP"] <= 0.10,
        "universalNetAtLeast5": vs_universal["net"] >= 5,
        "universalOneSidedPAtMostPoint10": vs_universal["oneSidedExactMcNemarP"] <= 0.10,
        "perBenchmarkHarmGuard": domain_guard,
        "verifierElapsedAtMost682Point207Sec": elapsed <= 682.207,
    }
    promotion["allPassed"] = all(value is True for key, value in promotion.items() if key != "developmentOnly")

    return {
        "analysisType": "result_aware_development_only",
        "fixedCohort": {
            "definition": "all public MCQ rows with a nonempty private correctOptionId; unmapped system outputs count wrong",
            "n": len(fixed_ids),
            "sortedIdsSha256": canonical_digest(fixed_ids),
        },
        "scores": scores,
        "strictVsBase": vs_base,
        "strictVsExistingUniversal": vs_universal,
        "eligible": eligible,
        "switches": {
            "n": switch_count,
            "rescuePrecision": vs_base["rescues"] / switch_count if switch_count else None,
            "harmRate": vs_base["harms"] / switch_count if switch_count else None,
        },
        "perBenchmark": {name: dict(values) for name, values in sorted(per_benchmark.items())},
        "promotionGate": promotion,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--existing-universal", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyze(args.campaign_dir.resolve(), args.existing_universal.resolve(), args.registry.resolve())
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
