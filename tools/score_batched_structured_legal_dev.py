#!/usr/bin/env python3
"""Score development draws and a small, fixed overlap-policy family."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Callable

try:
    from tools import run_batched_structured_legal_dev as dev_runner
except ImportError:  # Direct `python tools/score_...py` execution.
    import run_batched_structured_legal_dev as dev_runner


LABELS = {"인용됨", "기각"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def load_gold(paths: list[Path]) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in paths:
        for row in load_jsonl(path):
            case_id = row["caseId"]
            if case_id in result:
                raise ValueError(f"duplicate gold ID: {case_id}")
            result[case_id] = row["label"]
    return result


def load_draw(
    root: Path,
    draw: str,
    public_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any] | None]:
    result: dict[str, dict[str, Any] | None] = {}
    shard_dirs = sorted((root / draw).glob("shard_*"))
    if not shard_dirs:
        raise ValueError(f"missing draw: {draw}")
    for shard in shard_dirs:
        receipt = json.loads((shard / "receipt.json").read_text(encoding="utf-8"))
        if receipt["status"] not in {"accepted", "rejected"}:
            raise ValueError(f"unfinalized receipt: {shard}")
        rows = json.loads((shard / "normalized.json").read_text(encoding="utf-8"))
        raw_by_id: dict[str, dict[str, Any]] = {}
        response_path = shard / "response.json"
        if response_path.is_file():
            response = json.loads(response_path.read_text(encoding="utf-8"))
            for item in response.get("predictions", []) if isinstance(response, dict) else []:
                if isinstance(item, dict) and isinstance(item.get("id"), str):
                    if item["id"] in raw_by_id:
                        raw_by_id[item["id"]] = {}
                    else:
                        raw_by_id[item["id"]] = item
        for row in rows:
            if row["id"] in result:
                raise ValueError(f"duplicate draw ID: {row['id']}")
            prediction = row["prediction"]
            if prediction is None:
                raw = raw_by_id.get(row["id"])
                if isinstance(raw, dict) and public_by_id is not None and row["id"] in public_by_id:
                    recovered, _errors = dev_runner.validate_response(
                        {"predictions": [raw]}, [public_by_id[row["id"]]]
                    )
                    if recovered[0] is not None:
                        prediction = recovered[0]
                # Development scoring separates answer validity from overlap
                # evidence validity.  A malformed atom disables overlap but
                # does not erase an otherwise parseable binary answer.
                if prediction is None and isinstance(raw, dict) and raw.get("outcome") in LABELS:
                    prediction = {
                        "outcome": raw["outcome"],
                        "rationale": raw.get("rationale", ""),
                        "evidenceAtoms": [],
                        "structuredEvidenceValid": False,
                    }
            result[row["id"]] = prediction
    return result


def outcome(prediction: dict[str, Any] | None) -> str | None:
    if not isinstance(prediction, dict):
        return None
    value = prediction.get("outcome")
    return value if value in LABELS else None


def atom_keys(prediction: dict[str, Any] | None, mode: str) -> set[tuple[str, ...]]:
    if not isinstance(prediction, dict):
        return set()
    result: set[tuple[str, ...]] = set()
    for atom in prediction.get("evidenceAtoms", []):
        if mode == "strict":
            result.add((atom["issueCode"], atom["clauseId"], atom["direction"]))
        elif mode == "clause_direction":
            result.add((atom["clauseId"], atom["direction"]))
        elif mode == "clause":
            result.add((atom["clauseId"],))
        else:
            raise ValueError(f"unknown overlap mode: {mode}")
    return result


def sc3(d1: dict[str, Any] | None, d2: dict[str, Any] | None, d3: dict[str, Any] | None) -> str | None:
    values = [outcome(d1), outcome(d2), outcome(d3)]
    for label in sorted(LABELS):
        if values.count(label) >= 2:
            return label
    return values[0]


def answer_only(d1: dict[str, Any] | None, d2: dict[str, Any] | None, d3: dict[str, Any] | None) -> str | None:
    first, second, third = outcome(d1), outcome(d2), outcome(d3)
    return second if second in LABELS and second == third else first


def overlap_policy(
    d1: dict[str, Any] | None,
    d2: dict[str, Any] | None,
    d3: dict[str, Any] | None,
    *,
    mode: str,
) -> str | None:
    first, second, third = outcome(d1), outcome(d2), outcome(d3)
    if second not in LABELS or second != third:
        return first
    return second if atom_keys(d2, mode) & atom_keys(d3, mode) else first


def binomial_upper_tail(successes: int, trials: int) -> float:
    if trials == 0:
        return 1.0
    return sum(math.comb(trials, k) for k in range(successes, trials + 1)) / 2**trials


def compare(candidate: list[bool], reference: list[bool]) -> dict[str, Any]:
    rescues = sum(left and not right for left, right in zip(candidate, reference, strict=True))
    harms = sum(right and not left for left, right in zip(candidate, reference, strict=True))
    return {
        "rescues": rescues,
        "harms": harms,
        "net": rescues - harms,
        "discordant": rescues + harms,
        "oneSidedExactMcNemarP": binomial_upper_tail(rescues, rescues + harms),
    }


def metrics(predictions: list[str | None], ids: list[str], gold: dict[str, str]) -> tuple[dict[str, Any], list[bool]]:
    correct = [prediction == gold[case_id] for case_id, prediction in zip(ids, predictions, strict=True)]
    by_domain: dict[str, dict[str, Any]] = {}
    domains = [
        domain
        for domain in ("civil", "tax")
        if any(case_id.startswith(f"outcome-{domain}-") for case_id in ids)
    ]
    for domain in domains:
        indices = [index for index, case_id in enumerate(ids) if case_id.startswith(f"outcome-{domain}-")]
        count = sum(correct[index] for index in indices)
        by_domain[domain] = {"n": len(indices), "correct": count, "accuracy": count / len(indices)}
    count = sum(correct)
    return {
        "n": len(ids),
        "correct": count,
        "accuracy": count / len(ids),
        "null": sum(value is None for value in predictions),
        "domains": by_domain,
    }, correct


def score(public_path: Path, draw_root: Path, gold_paths: list[Path]) -> dict[str, Any]:
    public_rows = load_jsonl(public_path)
    ids = [row["id"] for row in public_rows]
    if len(ids) != 180 or len(set(ids)) != 180:
        raise ValueError("public development set must contain 180 unique IDs")
    gold = load_gold(gold_paths)
    if any(case_id not in gold for case_id in ids):
        raise ValueError("gold does not cover public development IDs")
    public_by_id = {row["id"]: row for row in public_rows}
    draws = {
        name: load_draw(draw_root, name, public_by_id)
        for name in ("D1", "D2", "D3")
    }
    for name, values in draws.items():
        if set(values) != set(ids):
            raise ValueError(f"{name} does not exactly cover public IDs")
    policies: dict[str, Callable[[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None], str | None]] = {
        "D1": lambda a, _b, _c: outcome(a),
        "D2": lambda _a, b, _c: outcome(b),
        "D3": lambda _a, _b, c: outcome(c),
        "SC3": sc3,
        "answer-only": answer_only,
        "overlap-strict": lambda a, b, c: overlap_policy(a, b, c, mode="strict"),
        "overlap-clause-direction": lambda a, b, c: overlap_policy(a, b, c, mode="clause_direction"),
        "overlap-clause": lambda a, b, c: overlap_policy(a, b, c, mode="clause"),
    }
    vectors: dict[str, list[str | None]] = {}
    correctness: dict[str, list[bool]] = {}
    report_metrics: dict[str, Any] = {}
    for name, policy in policies.items():
        vector = [policy(draws["D1"][case_id], draws["D2"][case_id], draws["D3"][case_id]) for case_id in ids]
        vectors[name] = vector
        report_metrics[name], correctness[name] = metrics(vector, ids, gold)
    comparisons = {
        name: {
            "vsD1": compare(correctness[name], correctness["D1"]),
            "vsSC3": compare(correctness[name], correctness["SC3"]),
        }
        for name in ("answer-only", "overlap-strict", "overlap-clause-direction", "overlap-clause")
    }
    triggers: dict[str, Any] = {}
    for mode in ("strict", "clause_direction", "clause"):
        ids_triggered = []
        for case_id in ids:
            a, b, c = draws["D1"][case_id], draws["D2"][case_id], draws["D3"][case_id]
            if outcome(b) in LABELS and outcome(b) == outcome(c) != outcome(a) and atom_keys(b, mode) & atom_keys(c, mode):
                ids_triggered.append(case_id)
        rescues = sum(vectors[f"overlap-{mode.replace('_', '-')}"][ids.index(case_id)] == gold[case_id] and outcome(draws["D1"][case_id]) != gold[case_id] for case_id in ids_triggered)
        harms = sum(vectors[f"overlap-{mode.replace('_', '-')}"][ids.index(case_id)] != gold[case_id] and outcome(draws["D1"][case_id]) == gold[case_id] for case_id in ids_triggered)
        triggers[mode] = {"n": len(ids_triggered), "rescues": rescues, "harms": harms, "precision": rescues / len(ids_triggered) if ids_triggered else None}
    return {
        "protocol": "mini_artichokes_batched_structured_legal_dev_score_v1",
        "developmentOnly": True,
        "n": len(ids),
        "metrics": report_metrics,
        "comparisons": comparisons,
        "overlapTriggers": triggers,
        "selectionRule": "choose one overlap mode on development only; fresh confirmation freezes it before calls",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--draw-root", type=Path, required=True)
    parser.add_argument("--gold", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = score(args.public, args.draw_root, args.gold)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
