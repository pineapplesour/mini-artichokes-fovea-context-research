#!/usr/bin/env python3
"""Prepare matched generic and overlap-aware whole-file MMLU-Pro judges."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.run_ensemble_file_agent import match_answer_to_option, parse_mcq_options


PROTOCOL = "mini_artichokes_mmlu_pro_matched_judges_v1"
ROLE_SEED = b"mini-artichokes-mmlu-pro-role-rotation-v1"
MODEL = "gpt-5.6-luna"


COMMON_INSTRUCTIONS = """# Matched MMLU-Pro candidate judge

This is one invocation over the complete supplied conflict file. Do not spawn
agents, call another model, browse the web, or inspect paths outside this
isolated workspace. Each row contains one original MCQ and two anonymous
candidate answers. Choose the candidate that is actually correct. You may use
short local calculations, but you may not synthesize a third answer.

For every row, `finalAnswer` must copy exactly one supplied candidate answer,
with no label, explanation, or rewriting. Write progress to
`output/answers.partial.jsonl`, then atomically finish
`output/answers.jsonl` in input order. Every line must have exactly:

`{"id":"exact input id","finalAnswer":"exact candidate answer"}`

Include every supplied ID exactly once. The final chat message is only a
completion notice.
"""


GENERIC_NOTE = """
Candidate order is deterministically randomized and carries no provenance or
support information. Judge only correctness against the public question.
"""


OVERLAP_NOTE = """
Each row also states the mechanical independent support count for each
candidate: one candidate came from one complete-file draw, and the other is
the common canonical option from two other independent complete-file draws.
This count is not proof of correctness; correlated solvers can agree on the
same wrong answer. Use it only after checking the public question.
"""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"non-object JSONL row: {path}")
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(canonical_bytes(row) + b"\n" for row in rows))


def answer_map(path: Path, expected_ids: list[str]) -> dict[str, str]:
    rows = load_jsonl(path)
    if [row.get("id") for row in rows] != expected_ids:
        raise ValueError(f"candidate ID/order mismatch: {path}")
    if any(set(row) != {"id", "finalAnswer"} or not str(row.get("finalAnswer") or "").strip() for row in rows):
        raise ValueError(f"candidate schema/answer invalid: {path}")
    return {str(row["id"]): str(row["finalAnswer"]) for row in rows}


def role_order(case_id: str) -> tuple[str, str]:
    digest = hashlib.sha256(ROLE_SEED + b"\0" + case_id.encode()).digest()
    return ("base", "consensus") if digest[0] % 2 == 0 else ("consensus", "base")


def build_packets(
    questions: list[dict[str, Any]],
    answers: dict[str, dict[str, str]],
    mode: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    packets: list[dict[str, Any]] = []
    roles: list[dict[str, Any]] = []
    for row in questions:
        case_id = str(row["id"])
        options = parse_mcq_options(str(row["prompt"]))
        keys = {
            draw: match_answer_to_option(answers[draw][case_id], options)
            for draw in ("D1", "D2", "D3")
        }
        if not all(keys.values()) or not (keys["D2"] == keys["D3"] != keys["D1"]):
            continue
        order = role_order(case_id)
        role_answers = {"base": answers["D1"][case_id], "consensus": answers["D2"][case_id]}
        candidates = [
            {"candidateKey": f"C{index}", "answer": role_answers[role]}
            for index, role in enumerate(order, 1)
        ]
        packet: dict[str, Any] = {
            "id": case_id,
            "question": row["prompt"],
            "candidates": candidates,
        }
        if mode == "overlap":
            packet["mechanicalIndependentSupport"] = [
                {"candidateKey": f"C{index}", "completeFileDraws": 1 if role == "base" else 2}
                for index, role in enumerate(order, 1)
            ]
        packets.append(
            {
                "benchmarkId": "mcq.mmlu_pro.stratified1000.matched_judge.v1",
                "id": case_id,
                "language": "en",
                "prompt": json.dumps(packet, ensure_ascii=False, separators=(",", ":")),
                "responseFormat": "candidate_choice",
                "suite": "exam",
            }
        )
        roles.append(
            {
                "id": case_id,
                "candidateKeyToRole": {f"C{index}": role for index, role in enumerate(order, 1)},
                "candidateKeyToAnswer": {f"C{index}": role_answers[role] for index, role in enumerate(order, 1)},
            }
        )
    return packets, roles


def ensure_empty(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty directory: {path}")
    path.mkdir(parents=True, exist_ok=True)


def prepare_campaign(
    campaign: Path,
    *,
    packets: list[dict[str, Any]],
    roles: list[dict[str, Any]],
    mode: str,
    source_freeze: dict[str, Any],
    candidate_hashes: dict[str, str],
) -> dict[str, Any]:
    ensure_empty(campaign / "solver")
    input_dir = campaign / "solver/input"
    output_dir = campaign / "solver/output"
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(input_dir / "questions.jsonl", packets)
    instructions = COMMON_INSTRUCTIONS + (GENERIC_NOTE if mode == "generic" else OVERLAP_NOTE)
    (input_dir / "RUN_INSTRUCTIONS.md").write_text(instructions, encoding="utf-8")
    ids = [row["id"] for row in packets]
    write_json(input_dir / "expected_ids.json", {"count": len(ids), "ids": ids})
    write_jsonl(campaign / "hidden-role-map.jsonl", roles)
    implementations = [Path(__file__).resolve(), REPO_ROOT / "tools/run_plain_codex_file_agent.py"]
    freeze = {
        "schemaVersion": 1,
        "status": "prepared_no_model_calls",
        "protocol": PROTOCOL,
        "mode": mode,
        "sourceFreezeSha256": source_freeze["freezeSha256"],
        "sourceQuestionsSha256": source_freeze["questionsSha256"],
        "sourceCandidateAnswersSha256": candidate_hashes,
        "questionsPath": "input/questions.jsonl",
        "questionsSha256": sha256_file(input_dir / "questions.jsonl"),
        "instructionsSha256": sha256_file(input_dir / "RUN_INSTRUCTIONS.md"),
        "expectedIdsFileSha256": sha256_file(input_dir / "expected_ids.json"),
        "expectedIdsSha256": canonical_digest(ids),
        "conflictIdsSha256": canonical_digest(ids),
        "hiddenRoleMapSha256": sha256_file(campaign / "hidden-role-map.jsonl"),
        "inventory": {"rows": len(ids)},
        "executionConfig": {
            "model": MODEL,
            "reasoningEffort": "high",
            "verbosity": "low",
            "serviceTier": "default",
            "nativeWebSearch": False,
            "localCode": True,
            "database": False,
            "skills": False,
            "multiAgent": False,
        },
        "implementationHashes": {str(path): sha256_file(path) for path in implementations},
    }
    freeze["freezeSha256"] = canonical_digest(freeze)
    write_json(campaign / "solver/freeze.json", freeze)
    return freeze


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    source = args.source_campaign
    questions_path = source / "solver/input/questions.jsonl"
    questions = load_jsonl(questions_path)
    ids = [str(row["id"]) for row in questions]
    source_freeze = load_json(source / "solver/freeze.json")
    if sha256_file(questions_path) != source_freeze.get("questionsSha256"):
        raise ValueError("source questions freeze mismatch")
    answers: dict[str, dict[str, str]] = {}
    candidate_hashes: dict[str, str] = {}
    for draw in ("D1", "D2", "D3"):
        index = int(draw[1:])
        path = source / f"drafts/d{index}/solver/output/answers.jsonl"
        answers[draw] = answer_map(path, ids)
        candidate_hashes[draw] = sha256_file(path)
    generic_packets, generic_roles = build_packets(questions, answers, "generic")
    overlap_packets, overlap_roles = build_packets(questions, answers, "overlap")
    if [row["id"] for row in generic_packets] != [row["id"] for row in overlap_packets]:
        raise AssertionError("matched judge conflict sets differ")
    if generic_roles != overlap_roles:
        raise AssertionError("matched judge role maps differ")
    generic_freeze = prepare_campaign(
        args.generic_campaign,
        packets=generic_packets,
        roles=generic_roles,
        mode="generic",
        source_freeze=source_freeze,
        candidate_hashes=candidate_hashes,
    )
    overlap_freeze = prepare_campaign(
        args.overlap_campaign,
        packets=overlap_packets,
        roles=overlap_roles,
        mode="overlap",
        source_freeze=source_freeze,
        candidate_hashes=candidate_hashes,
    )
    report = {
        "protocol": PROTOCOL,
        "conflicts": len(generic_packets),
        "conflictIdsSha256": generic_freeze["conflictIdsSha256"],
        "hiddenRoleMapSha256": generic_freeze["hiddenRoleMapSha256"],
        "candidateAnswersSha256": candidate_hashes,
        "genericFreezeSha256": generic_freeze["freezeSha256"],
        "overlapFreezeSha256": overlap_freeze["freezeSha256"],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-campaign", type=Path, required=True)
    parser.add_argument("--generic-campaign", type=Path, required=True)
    parser.add_argument("--overlap-campaign", type=Path, required=True)
    args = parser.parse_args()
    prepare(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
