#!/usr/bin/env python3
"""Prepare a gold-free, role-blind pairwise veto campaign.

The model-mounted input contains the complete public question file and only
the two answers that must be compared for each frozen canonical conflict.
Per-item LEFT/RIGHT orientation is deterministic from a frozen seed.  The
orientation-to-source-role mapping is kept outside the mounted input and is
hash-bound by the campaign freeze so a later deterministic consumer can
interpret preferences without revealing those roles to the verifier.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.prepare_plain_codex_file_benchmark import canonical_digest, sha256_file
from tools.run_ensemble_file_agent import match_answer_to_option, parse_mcq_options


PROTOCOL = "mini_artichokes_blind_pairwise_veto_v2"
EXPECTED_QUESTION_ROWS = 1309
EXPECTED_CONFLICT_ROWS = 247
ROTATION_SCHEME = "sha256-domain-seed-nul-id-low-bit-v1"
PAIR_NAMES = ("left", "right")
SOURCE_ROLES = ("INCUMBENT", "PROPOSED")
FROZEN_MODEL = "gpt-5.6-luna"
FROZEN_REASONING_EFFORT = "high"
FROZEN_VERBOSITY = "low"
IMPLEMENTATION_RELATIVE_PATHS = (
    "tools/prepare_blind_pairwise_veto.py",
    "tools/validate_blind_pairwise_veto.py",
    "tools/run_blind_pairwise_veto_agent.py",
    "tools/run_ensemble_file_agent.py",
)


INSTRUCTIONS = """# Blind pairwise falsification certificate contract v2

Read all 1,309 public rows in `input/questions.jsonl`.  The 247 rows requiring
comparison are listed, in public-question order, in
`input/candidate_pairs.jsonl`.  Each comparison contains a LEFT answer and a
RIGHT answer.  Treat the two sides symmetrically.  Their order varies by row.
Do not infer provenance, use item identifiers or cross-row option frequencies,
or favor either side because of its position.

For every comparison, try to falsify LEFT and RIGHT separately before making
a preference.  Agreement, confidence, familiarity, and a bare assertion are
not evidence.  First identify what the question asks: a correct statement, an
incorrect/exception statement, the best/most suitable answer, the least
suitable answer, a multi-selection, or an unresolved target.  Then provide:

- an exact prompt quote showing the requested polarity;
- each side's exact candidate answer and its atomic claim;
- a candidate-specific falsification test and its outcome;
- the strongest countercase against choosing that candidate and whether the
  countercase stands;
- evidence that is either an exact prompt quote, a derivation whose premises
  are exact prompt quotes, an explicit MODEL_KNOWLEDGE receipt, or NONE;
- whether exactly one side remains uniquely suitable under the target.

This is a tool-free comparison.  Do not use web search, retrieval, databases,
skills, calculation code, or external knowledge tools.  Local file operations
are permitted only to read the staged input and write the required output.
MODEL_KNOWLEDGE must state one atomic supported claim and the concrete basis on
which that claim could be falsified; it is a transparent record of internal
knowledge, not independently verified external evidence.  If evidence is
missing, ambiguous, or dependent on guessing, mark the affected side
UNRESOLVED and return TIE.

Write exactly one JSON object for every comparison to
`output/certificates.partial.jsonl`, preserving input order.  After all 247
records are complete, atomically write `output/certificates.jsonl`.  Each
record must have exactly this shape:

```
{
  "id": "exact id",
  "targetPolarity": "SELECT_CORRECT|SELECT_INCORRECT|SELECT_BEST|SELECT_LEAST|MULTI_SELECT|UNRESOLVED",
  "polarityQuote": "exact quote from the public prompt",
  "leftAssessment": {
    "candidateAnswer": "exact LEFT answer",
    "atomicClaim": "one falsifiable claim",
    "falsificationTest": "specific attempted test",
    "testOutcome": "SURVIVED|FAILED|INCONCLUSIVE",
    "status": "SUPPORTED|REFUTED|UNRESOLVED",
    "strongestCountercase": "strongest reason this candidate could be wrong",
    "countercaseOutcome": "DEFEATED|STANDS|UNRESOLVED",
    "evidence": {"type": "PROMPT_QUOTE|DERIVATION|MODEL_KNOWLEDGE|NONE", "receipt": null_or_tagged_receipt}
  },
  "rightAssessment": {"same keys as leftAssessment": "same meanings"},
  "uniqueness": "LEFT_ONLY|RIGHT_ONLY|BOTH_PLAUSIBLE|NEITHER_PLAUSIBLE|UNRESOLVED",
  "preference": "PREFER_LEFT|PREFER_RIGHT|TIE",
  "comparativeReason": "why the structured tests entail this preference"
}
```

Receipt shapes are strict:

- PROMPT_QUOTE: `{"quote":"exact prompt substring"}`
- DERIVATION: `{"premises":["exact prompt substring", ...],"steps":["nonempty step", ...],"conclusion":"nonempty"}`
- MODEL_KNOWLEDGE: `{"supportedClaim":"one atomic claim","falsificationBasis":"concrete nonempty basis"}`
- NONE: `null`

SUPPORTED requires SURVIVED, a DEFEATED countercase, and non-NONE evidence.
REFUTED requires FAILED, a STANDS countercase, and non-NONE evidence.
UNRESOLVED requires INCONCLUSIVE, an UNRESOLVED countercase, and NONE evidence.
PREFER_LEFT requires LEFT_ONLY, supported LEFT, and refuted RIGHT; PREFER_RIGHT
is symmetric.  BOTH_PLAUSIBLE requires both sides SUPPORTED;
NEITHER_PLAUSIBLE requires both sides REFUTED.  If either side is UNRESOLVED,
uniqueness must be UNRESOLVED and preference must be TIE.  Every other
consistent outcome is TIE.  The final chat response must only state whether
the complete certificate file was produced.
"""


def lf_jsonl_lines(path: Path) -> list[str]:
    """Return JSONL records using LF, not Unicode text line boundaries."""

    lines = path.read_text(encoding="utf-8").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(lf_jsonl_lines(path), 1):
        if not raw.strip():
            raise ValueError(f"blank JSONL line {line_number}: {path}")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError(f"non-object JSONL line {line_number}: {path}")
        rows.append(value)
    return rows


def load_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def verify_self_hash(value: dict[str, Any], field: str, label: str) -> str:
    claimed = value.get(field)
    if not isinstance(claimed, str) or not claimed:
        raise ValueError(f"{label} missing {field}")
    observed = canonical_digest({key: item for key, item in value.items() if key != field})
    if claimed != observed:
        raise ValueError(f"{label} {field} mismatch; claimed={claimed}, observed={observed}")
    return claimed


def rotation_bit(seed: str, case_id: str) -> int:
    payload = b"mini-artichokes-blind-veto-v1\0" + seed.encode("utf-8") + b"\0" + case_id.encode("utf-8")
    return hashlib.sha256(payload).digest()[0] & 1


def canonical_option_key(answer: str, prompt: str) -> str:
    options = parse_mcq_options(prompt)
    if len(options) < 2 or any(not str(option).strip() for option in options.values()):
        return ""
    option_id = match_answer_to_option(answer, options)
    return f"option:{option_id}" if option_id and option_id in options else ""


def validate_questions(rows: list[dict[str, Any]]) -> list[str]:
    if len(rows) != EXPECTED_QUESTION_ROWS:
        raise ValueError(f"expected {EXPECTED_QUESTION_ROWS} public questions, found {len(rows)}")
    ids: list[str] = []
    for position, row in enumerate(rows, 1):
        for field in ("id", "prompt", "responseFormat"):
            value = row.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"question {position} requires nonempty string {field}")
        ids.append(row["id"])
    if len(ids) != len(set(ids)):
        raise ValueError("public question IDs must be unique")
    return ids


def validate_expected_ids(path: Path, ids: list[str]) -> None:
    value = load_json_object(path)
    if value.get("count") != len(ids) or value.get("ids") != ids:
        raise ValueError("source expected IDs do not exactly match public question order")


def answer_map(path: Path, ids: list[str]) -> dict[str, str]:
    rows = load_jsonl(path)
    observed: list[str] = []
    answers: dict[str, str] = {}
    for position, row in enumerate(rows, 1):
        if set(row) != {"id", "finalAnswer"}:
            raise ValueError(f"candidate row {position} has invalid schema: {path}")
        case_id = row.get("id")
        answer = row.get("finalAnswer")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"candidate row {position} has invalid ID: {path}")
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError(f"candidate row {position} has empty answer: {path}")
        observed.append(case_id)
        answers[case_id] = answer
    if observed != ids or len(observed) != len(set(observed)):
        raise ValueError(f"candidate IDs/order mismatch: {path}")
    return answers


def source_bundle(source_campaign: Path) -> dict[str, Any]:
    solver = source_campaign / "solver"
    questions_path = solver / "input/questions.jsonl"
    expected_path = solver / "input/expected_ids.json"
    overlap_path = solver / "input/overlap_manifest.jsonl"
    freeze_path = solver / "freeze.json"
    candidate_paths = {
        "base": solver / "input/candidates/base.jsonl",
        "auxiliary_1": solver / "input/candidates/auxiliary_1.jsonl",
        "auxiliary_2": solver / "input/candidates/auxiliary_2.jsonl",
    }
    for path in (questions_path, expected_path, overlap_path, freeze_path, *candidate_paths.values()):
        if not path.is_file():
            raise FileNotFoundError(path)

    questions = load_jsonl(questions_path)
    ids = validate_questions(questions)
    validate_expected_ids(expected_path, ids)
    freeze = load_json_object(freeze_path)
    freeze_sha256 = verify_self_hash(freeze, "freezeSha256", "source freeze")
    if freeze.get("protocol") != "mini_artichokes_candidate_overlap_adjudication_v2":
        raise ValueError("source campaign must use canonical overlap protocol v2")
    expected_hashes = {
        "questionsSha256": sha256_file(questions_path),
        "overlapManifestSha256": sha256_file(overlap_path),
    }
    for field, observed in expected_hashes.items():
        if freeze.get(field) != observed:
            raise ValueError(f"source freeze {field} mismatch")
    if freeze.get("expectedIdsSha256") != canonical_digest(ids):
        raise ValueError("source freeze expected IDs hash mismatch")

    candidates = {name: answer_map(path, ids) for name, path in candidate_paths.items()}
    candidate_hashes = {name: sha256_file(path) for name, path in candidate_paths.items()}
    if freeze.get("candidateAnswersSha256") != candidate_hashes:
        raise ValueError("source candidate hashes do not match source freeze")

    overlap = load_jsonl(overlap_path)
    if [row.get("id") for row in overlap] != ids:
        raise ValueError("source overlap IDs/order mismatch")
    eligible_ids: list[str] = []
    question_by_id = {row["id"]: row for row in questions}
    for position, manifest in enumerate(overlap, 1):
        case_id = ids[position - 1]
        question = question_by_id[case_id]
        keys = [
            canonical_option_key(candidates[name][case_id], question["prompt"])
            for name in ("base", "auxiliary_1", "auxiliary_2")
        ]
        recomputed = bool(
            question["responseFormat"] == "mcq"
            and all(keys)
            and keys[1] == keys[2]
            and keys[1] != keys[0]
        )
        if manifest.get("eligible") is not recomputed:
            raise ValueError(f"source overlap eligibility mismatch at row {position}")
        if recomputed:
            eligible_ids.append(case_id)
    if len(eligible_ids) != EXPECTED_CONFLICT_ROWS:
        raise ValueError(f"expected {EXPECTED_CONFLICT_ROWS} canonical conflicts, found {len(eligible_ids)}")
    if freeze.get("eligibleIdsSha256") != canonical_digest(eligible_ids):
        raise ValueError("source frozen eligible IDs hash mismatch")
    return {
        "questions": questions,
        "ids": ids,
        "eligibleIds": eligible_ids,
        "candidates": candidates,
        "candidateHashes": candidate_hashes,
        "questionsPath": questions_path,
        "expectedPath": expected_path,
        "overlapPath": overlap_path,
        "freezePath": freeze_path,
        "freezeSha256": freeze_sha256,
    }


def prepare(
    *,
    source_campaign: Path,
    campaign_dir: Path,
    rotation_seed: str,
    model: str,
    reasoning_effort: str,
    verbosity: str,
) -> dict[str, Any]:
    if not isinstance(rotation_seed, str) or len(rotation_seed.strip()) < 16:
        raise ValueError("rotation seed must be an explicit nonempty string of at least 16 characters")
    if (model, reasoning_effort, verbosity) != (
        FROZEN_MODEL,
        FROZEN_REASONING_EFFORT,
        FROZEN_VERBOSITY,
    ):
        raise ValueError(
            "blind-veto execution is fixed to "
            f"{FROZEN_MODEL}/{FROZEN_REASONING_EFFORT}/{FROZEN_VERBOSITY}"
        )
    if campaign_dir.exists() and any(campaign_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty campaign: {campaign_dir}")
    source = source_bundle(source_campaign)

    veto_dir = campaign_dir / "veto"
    input_dir = veto_dir / "input"
    output_dir = veto_dir / "output"
    control_dir = campaign_dir / "control"
    output_dir.mkdir(parents=True, exist_ok=True)
    input_dir.mkdir(parents=True, exist_ok=True)
    control_dir.mkdir(parents=True, exist_ok=True)

    public_questions = [
        {
            "id": row["id"],
            "responseFormat": row["responseFormat"],
            "language": str(row.get("language") or ""),
            "prompt": row["prompt"],
        }
        for row in source["questions"]
    ]
    questions_path = input_dir / "questions.jsonl"
    write_jsonl(questions_path, public_questions)

    pairs: list[dict[str, str]] = []
    role_mapping: list[dict[str, Any]] = []
    incumbent = source["candidates"]["base"]
    proposed = source["candidates"]["auxiliary_1"]
    for case_id in source["eligibleIds"]:
        bit = rotation_bit(rotation_seed, case_id)
        if bit == 0:
            left_answer, right_answer = incumbent[case_id], proposed[case_id]
            left_role, right_role = SOURCE_ROLES
        else:
            left_answer, right_answer = proposed[case_id], incumbent[case_id]
            left_role, right_role = reversed(SOURCE_ROLES)
        pairs.append({"id": case_id, "leftAnswer": left_answer, "rightAnswer": right_answer})
        role_mapping.append(
            {
                "id": case_id,
                "rotationBit": bit,
                "leftRole": left_role,
                "rightRole": right_role,
                "leftAnswerSha256": text_sha256(left_answer),
                "rightAnswerSha256": text_sha256(right_answer),
            }
        )
    pairs_path = input_dir / "candidate_pairs.jsonl"
    write_jsonl(pairs_path, pairs)
    expected_path = input_dir / "expected_certificate_ids.json"
    write_json(expected_path, {"count": len(pairs), "ids": source["eligibleIds"]})
    instructions_path = input_dir / "RUN_INSTRUCTIONS.md"
    instructions_path.write_text(INSTRUCTIONS, encoding="utf-8")

    mapping_path = control_dir / "role_mapping.jsonl"
    write_jsonl(mapping_path, role_mapping)
    rotation_control = {
        "schemaVersion": 1,
        "scheme": ROTATION_SCHEME,
        "seed": rotation_seed,
        "seedSha256": text_sha256(rotation_seed),
        "eligibleIdsSha256": canonical_digest(source["eligibleIds"]),
        "roleMappingSha256": sha256_file(mapping_path),
    }
    rotation_path = control_dir / "rotation.json"
    write_json(rotation_path, rotation_control)

    implementation_paths = [REPO_ROOT / relative for relative in IMPLEMENTATION_RELATIVE_PATHS]
    for path in implementation_paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    freeze: dict[str, Any] = {
        "schemaVersion": 1,
        "status": "prepared_no_model_calls",
        "protocol": PROTOCOL,
        "sourceCampaign": str(source_campaign.resolve()),
        "sourceFreezeSha256": source["freezeSha256"],
        "sourceFreezeFileSha256": sha256_file(source["freezePath"]),
        "sourceQuestionsSha256": sha256_file(source["questionsPath"]),
        "sourceOverlapManifestSha256": sha256_file(source["overlapPath"]),
        "sourceCandidateAnswersSha256": source["candidateHashes"],
        "questionsPath": "input/questions.jsonl",
        "questionsSha256": sha256_file(questions_path),
        "pairsPath": "input/candidate_pairs.jsonl",
        "pairsSha256": sha256_file(pairs_path),
        "expectedCertificateIdsPath": "input/expected_certificate_ids.json",
        "expectedCertificateIdsFileSha256": sha256_file(expected_path),
        "expectedCertificateIdsSha256": canonical_digest(source["eligibleIds"]),
        "instructionsSha256": sha256_file(instructions_path),
        "roleMappingPath": "control/role_mapping.jsonl",
        "roleMappingSha256": sha256_file(mapping_path),
        "rotationControlPath": "control/rotation.json",
        "rotationControlSha256": sha256_file(rotation_path),
        "rotationScheme": ROTATION_SCHEME,
        "rotationSeedSha256": text_sha256(rotation_seed),
        "inventory": {
            "questionRows": len(public_questions),
            "conflictRows": len(pairs),
            "leftIncumbentRows": sum(row["leftRole"] == "INCUMBENT" for row in role_mapping),
            "rightIncumbentRows": sum(row["rightRole"] == "INCUMBENT" for row in role_mapping),
        },
        "executionConfig": {
            "model": model,
            "reasoningEffort": reasoning_effort,
            "verbosity": verbosity,
            "serviceTier": "default",
            "nativeWebSearch": False,
            "localCode": True,
            "database": False,
            "skills": False,
            "multiAgent": False,
        },
        "implementationHashes": {str(path.resolve()): sha256_file(path) for path in implementation_paths},
    }
    freeze["freezeSha256"] = canonical_digest(freeze)
    write_json(veto_dir / "freeze.json", freeze)
    return freeze


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-campaign", type=Path, required=True)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--rotation-seed", required=True)
    parser.add_argument("--model", default=FROZEN_MODEL)
    parser.add_argument("--reasoning-effort", default=FROZEN_REASONING_EFFORT)
    parser.add_argument("--verbosity", default=FROZEN_VERBOSITY)
    args = parser.parse_args()
    freeze = prepare(
        source_campaign=args.source_campaign.resolve(),
        campaign_dir=args.campaign_dir.resolve(),
        rotation_seed=args.rotation_seed,
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        verbosity=args.verbosity,
    )
    print(json.dumps(freeze, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
