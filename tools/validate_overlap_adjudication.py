#!/usr/bin/env python3
"""Strictly validate a candidate-overlap adjudication artifact.

The ordinary full-file answer validator only checks schema and coverage.  That
is insufficient for the overlap experiment because the adjudicator is not a
fourth solver: every accepted answer must be an exact copy of either the
frozen base or, after a valid switch decision, auxiliary candidate 1.

This validator is deliberately fail closed.  Malformed or inconsistent
decisions never authorize a change from the base answer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.run_ensemble_file_agent import match_answer_to_option, parse_mcq_options


DECISION_RE = re.compile(
    r"^(?P<id>[^|\r\n]+?)\s*\|\s*"
    r"gate=(?P<gate>VALID|INVALID|ABSTAIN)\s*\|\s*"
    r"action=(?P<action>KEEP|SWITCH)\s*\|\s*"
    r"(?P<reason>\S(?:.*\S)?)\s*$"
)
SUPPORTED_PROTOCOLS = {"mini_artichokes_candidate_overlap_adjudication_v2"}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl_strict(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            raise ValueError(f"blank_jsonl_line:{path.name}:{line_number}")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError(f"non_object_jsonl_line:{path.name}:{line_number}")
        rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _append_once(errors: list[str], error: str) -> None:
    if error not in errors:
        errors.append(error)


def _read_answer_rows(
    path: Path,
    *,
    label: str,
    expected_ids: list[str],
    errors: list[str],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    if not path.is_file():
        _append_once(errors, f"{label}_file_missing")
        return [], {}
    try:
        rows = load_jsonl_strict(path)
    except Exception as exc:
        _append_once(errors, f"{label}_jsonl_invalid:{exc}")
        return [], {}

    observed_ids: list[str] = []
    answers: dict[str, str] = {}
    for index, row in enumerate(rows):
        if set(row) != {"id", "finalAnswer"}:
            _append_once(errors, f"{label}_row_{index}_schema")
            continue
        case_id = row.get("id")
        answer = row.get("finalAnswer")
        if not isinstance(case_id, str) or not case_id:
            _append_once(errors, f"{label}_row_{index}_invalid_id")
            continue
        observed_ids.append(case_id)
        if case_id in answers:
            _append_once(errors, f"{label}_duplicate_id")
        if not isinstance(answer, str) or not answer:
            _append_once(errors, f"{label}_row_{index}_invalid_answer")
            continue
        answers[case_id] = answer
    if observed_ids != expected_ids:
        _append_once(errors, f"{label}_ids_or_order_mismatch")
    return rows, answers


def _read_decisions(
    path: Path,
    *,
    eligible_ids: list[str],
    errors: list[str],
) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    if not path.is_file():
        _append_once(errors, "decisions_file_missing")
        return [], {}

    decisions: list[dict[str, str]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            _append_once(errors, f"decisions_line_{line_number}_blank")
            continue
        match = DECISION_RE.fullmatch(raw)
        if not match:
            _append_once(errors, f"decisions_line_{line_number}_invalid")
            continue
        decision = {key: value.strip() for key, value in match.groupdict().items()}
        decisions.append(decision)

    decision_ids = [row["id"] for row in decisions]
    if len(decision_ids) != len(set(decision_ids)):
        _append_once(errors, "decisions_duplicate_id")
    eligible_set = set(eligible_ids)
    if any(case_id not in eligible_set for case_id in decision_ids):
        _append_once(errors, "decisions_ineligible_id")
    if any(case_id not in set(decision_ids) for case_id in eligible_ids):
        _append_once(errors, "decisions_missing_eligible_id")
    if decision_ids != eligible_ids:
        _append_once(errors, "decisions_ids_or_order_mismatch")

    by_id: dict[str, dict[str, str]] = {}
    for decision in decisions:
        case_id = decision["id"]
        if case_id not in by_id:
            by_id[case_id] = decision
        gate = decision["gate"]
        action = decision["action"]
        if (gate, action) not in {
            ("VALID", "SWITCH"),
            ("INVALID", "KEEP"),
            ("ABSTAIN", "KEEP"),
        }:
            _append_once(errors, f"decision_{case_id}_gate_action_mismatch")
    return decisions, by_id


def validate_overlap_adjudication(
    campaign_dir: Path,
    *,
    write_report: bool = True,
) -> dict[str, Any]:
    """Validate an overlap campaign without reading any private gold data."""

    campaign_dir = campaign_dir.resolve()
    solver_dir = campaign_dir / "solver"
    input_dir = solver_dir / "input"
    output_dir = solver_dir / "output"
    errors: list[str] = []

    freeze_path = solver_dir / "freeze.json"
    freeze: dict[str, Any] = {}
    if not freeze_path.is_file():
        _append_once(errors, "freeze_file_missing")
    else:
        try:
            value = load_json(freeze_path)
            if not isinstance(value, dict):
                raise ValueError("freeze_not_object")
            freeze = value
        except Exception as exc:
            _append_once(errors, f"freeze_invalid:{exc}")
    if freeze and freeze.get("protocol") not in SUPPORTED_PROTOCOLS:
        _append_once(errors, "unsupported_overlap_protocol")

    expected_path = input_dir / "expected_ids.json"
    expected_ids: list[str] = []
    if not expected_path.is_file():
        _append_once(errors, "expected_ids_file_missing")
    else:
        try:
            expected_payload = load_json(expected_path)
            raw_ids = expected_payload.get("ids") if isinstance(expected_payload, dict) else None
            if not isinstance(raw_ids, list) or any(not isinstance(value, str) or not value for value in raw_ids):
                raise ValueError("expected_ids_missing_or_invalid")
            expected_ids = list(raw_ids)
            if len(expected_ids) != len(set(expected_ids)):
                _append_once(errors, "expected_ids_duplicate")
            if expected_payload.get("count") not in (None, len(expected_ids)):
                _append_once(errors, "expected_ids_count_mismatch")
        except Exception as exc:
            _append_once(errors, f"expected_ids_invalid:{exc}")

    questions_path = input_dir / "questions.jsonl"
    questions: list[dict[str, Any]] = []
    if not questions_path.is_file():
        _append_once(errors, "questions_file_missing")
    else:
        try:
            questions = load_jsonl_strict(questions_path)
        except Exception as exc:
            _append_once(errors, f"questions_jsonl_invalid:{exc}")
    question_ids = [row.get("id") for row in questions]
    if question_ids != expected_ids:
        _append_once(errors, "question_ids_or_order_mismatch")
    question_by_id = {
        str(row["id"]): row
        for row in questions
        if isinstance(row.get("id"), str) and row.get("id")
    }

    candidate_dir = input_dir / "candidates"
    _, base = _read_answer_rows(
        candidate_dir / "base.jsonl", label="base", expected_ids=expected_ids, errors=errors
    )
    _, auxiliary_1 = _read_answer_rows(
        candidate_dir / "auxiliary_1.jsonl",
        label="auxiliary_1",
        expected_ids=expected_ids,
        errors=errors,
    )
    _, auxiliary_2 = _read_answer_rows(
        candidate_dir / "auxiliary_2.jsonl",
        label="auxiliary_2",
        expected_ids=expected_ids,
        errors=errors,
    )

    manifest_path = input_dir / "overlap_manifest.jsonl"
    manifest_rows: list[dict[str, Any]] = []
    if not manifest_path.is_file():
        _append_once(errors, "overlap_manifest_file_missing")
    else:
        try:
            manifest_rows = load_jsonl_strict(manifest_path)
        except Exception as exc:
            _append_once(errors, f"overlap_manifest_jsonl_invalid:{exc}")
    manifest_ids = [row.get("id") for row in manifest_rows]
    if manifest_ids != expected_ids:
        _append_once(errors, "overlap_manifest_ids_or_order_mismatch")

    eligible_ids: list[str] = []
    eligible_by_id: dict[str, bool] = {}
    for index, row in enumerate(manifest_rows):
        if not {"id", "eligible"}.issubset(row):
            _append_once(errors, f"overlap_manifest_row_{index}_schema")
        case_id = row.get("id")
        if not isinstance(case_id, str) or case_id not in question_by_id:
            continue
        question = question_by_id[case_id]
        if case_id not in base or case_id not in auxiliary_1 or case_id not in auxiliary_2:
            continue
        response_format = str(question.get("responseFormat") or "")
        prompt = str(question.get("prompt") or "")
        options = parse_mcq_options(prompt) if response_format == "mcq" else {}
        option_ids = [
            match_answer_to_option(answer, options) if options else ""
            for answer in (base[case_id], auxiliary_1[case_id], auxiliary_2[case_id])
        ]
        keys = [f"option:{option_id}" if option_id else "" for option_id in option_ids]
        canonical_mapping_complete = bool(options and all(keys))
        auxiliary_agreement = bool(canonical_mapping_complete and keys[1] == keys[2])
        different_from_base = bool(auxiliary_agreement and keys[1] != keys[0])
        recomputed_eligible = bool(response_format == "mcq" and different_from_base)
        if response_format != "mcq":
            eligibility_reason = "non_mcq_excluded"
        elif not options:
            eligibility_reason = "mcq_options_unparseable"
        elif not canonical_mapping_complete:
            eligibility_reason = "candidate_option_mapping_incomplete"
        elif not auxiliary_agreement:
            eligibility_reason = "auxiliary_option_ids_disagree"
        elif not different_from_base:
            eligibility_reason = "auxiliaries_agree_with_base"
        else:
            eligibility_reason = "canonical_auxiliary_overlap_differs_from_base"
        optional_expected_values = {
            "responseFormat": response_format,
            "baseKey": keys[0],
            "auxiliary1Key": keys[1],
            "auxiliary2Key": keys[2],
            "keyType": "canonical_mcq_option_id",
            "canonicalMappingComplete": canonical_mapping_complete,
            "auxiliaryAgreement": auxiliary_agreement,
            "differentFromBase": different_from_base,
            "eligible": recomputed_eligible,
            "eligibilityReason": eligibility_reason,
        }
        if not isinstance(row.get("eligible"), bool) or any(
            key in row and row.get(key) != value
            for key, value in optional_expected_values.items()
        ):
            _append_once(errors, f"overlap_manifest_row_{index}_recompute_mismatch")
        eligible_by_id[case_id] = recomputed_eligible
        if recomputed_eligible:
            eligible_ids.append(case_id)

    decisions, decision_by_id = _read_decisions(
        output_dir / "decisions.log", eligible_ids=eligible_ids, errors=errors
    )
    answer_rows, final_answers = _read_answer_rows(
        output_dir / "answers.jsonl", label="answers", expected_ids=expected_ids, errors=errors
    )

    switch_ids: list[str] = []
    changed_ids: list[str] = []
    for case_id in expected_ids:
        if case_id not in base or case_id not in final_answers:
            continue
        decision = decision_by_id.get(case_id)
        is_valid_switch = bool(
            eligible_by_id.get(case_id)
            and decision
            and decision.get("gate") == "VALID"
            and decision.get("action") == "SWITCH"
        )
        if is_valid_switch:
            switch_ids.append(case_id)
            expected_answer = auxiliary_1.get(case_id)
        else:
            expected_answer = base[case_id]
        if final_answers[case_id] != base[case_id]:
            changed_ids.append(case_id)
        if expected_answer is None or final_answers[case_id] != expected_answer:
            if not eligible_by_id.get(case_id):
                _append_once(errors, f"answer_{case_id}_ineligible_changed")
            elif is_valid_switch:
                _append_once(errors, f"answer_{case_id}_switch_not_exact_auxiliary_1")
            else:
                _append_once(errors, f"answer_{case_id}_keep_not_exact_base")

    if changed_ids != switch_ids:
        _append_once(errors, "decisions_output_change_set_mismatch")

    report = {
        "schemaVersion": 1,
        "status": "accepted" if not errors else "incomplete",
        "passed": not errors,
        "errors": errors,
        "expectedRows": len(expected_ids),
        "observedRows": len(answer_rows),
        "eligibleRows": len(eligible_ids),
        "decisionRows": len(decisions),
        "switchRows": len(switch_ids),
        "changedRows": len(changed_ids),
        "answersSha256": sha256_file(output_dir / "answers.jsonl")
        if (output_dir / "answers.jsonl").is_file()
        else None,
        "decisionsSha256": sha256_file(output_dir / "decisions.log")
        if (output_dir / "decisions.log").is_file()
        else None,
    }
    if write_report:
        write_json(solver_dir / "overlap_validation.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--no-write-report", action="store_true")
    args = parser.parse_args()
    report = validate_overlap_adjudication(
        args.campaign_dir,
        write_report=not args.no_write_report,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
