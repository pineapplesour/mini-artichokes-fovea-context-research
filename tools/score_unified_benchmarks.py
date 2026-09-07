#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


CASE_NUMBER_RE = re.compile(r"\d{4}[가-힣]{1,4}\d+")
TARGET_SOURCE_ID_KEYS = (
    "sourceId",
    "source_id",
    "canonicalId",
    "canonical_id",
    "fileId",
    "file_id",
    "id",
    "caseNumber",
    "fileName",
    "title",
)


def load_graphed_regression_predictions(results_dir: Path) -> list[dict[str, str]]:
    predictions: list[dict[str, str]] = []
    for path in sorted(results_dir.glob("*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        case_id = str(item.get("id") or path.stem)
        prediction = item.get("prediction")
        predictions.append({"caseId": case_id, "prediction": "" if prediction is None else str(prediction)})
    return predictions


def load_json_artifacts(results_dir: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for path in sorted(results_dir.glob("*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(item, dict):
            continue
        item.setdefault("caseId", str(item.get("id") or path.stem))
        artifacts.append(item)
    return artifacts


def score_mcq_predictions(
    private_manifest: dict[str, Any],
    predictions: list[dict[str, str]],
    *,
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    answer_items = [item for item in private_manifest.get("answers", []) if isinstance(item, dict) and item.get("caseId")]
    answer_by_id = {str(item.get("caseId") or ""): str(item.get("correctOptionId") or "") for item in answer_items}
    allowed = {str(case_id) for case_id in case_ids or [] if str(case_id)}
    if allowed:
        answer_by_id = {
            case_id: answer
            for case_id, answer in answer_by_id.items()
            if _case_id_selected(case_id, allowed)
        }
        answer_items = [
            item
            for item in answer_items
            if _case_id_selected(str(item.get("caseId") or ""), allowed)
        ]
    prediction_by_id = {str(item.get("caseId") or ""): str(item.get("prediction") or "") for item in predictions}
    artifact_by_id = {str(item.get("caseId") or item.get("id") or ""): item for item in predictions if isinstance(item, dict)}
    retrieval_targets_by_id = _mcq_retrieval_targets_by_case(private_manifest, answer_items)
    if allowed:
        retrieval_targets_by_id = {
            case_id: entry
            for case_id, entry in retrieval_targets_by_id.items()
            if _case_id_selected(case_id, allowed)
        }
    target_policy = _mcq_retrieval_target_policy(private_manifest, retrieval_targets_by_id)
    total = len(answer_by_id)
    correct = 0
    retrieval_passed = 0
    invalid_case_ids: list[str] = []
    wrong_case_ids: list[str] = []
    missing_target_case_ids: list[str] = []
    cases: list[dict[str, Any]] = []
    for case_id, gold in answer_by_id.items():
        pred = prediction_by_id.get(case_id, "")
        answer_passed = bool(pred and pred == gold)
        if not pred:
            invalid_case_ids.append(case_id)
            wrong_case_ids.append(case_id)
        elif answer_passed:
            correct += 1
        else:
            wrong_case_ids.append(case_id)
        retrieval_entry = retrieval_targets_by_id.get(case_id)
        retrieval_failures = _mcq_retrieval_failures(retrieval_entry, artifact_by_id.get(case_id, {}))
        retrieval_case_passed = not retrieval_failures
        if retrieval_case_passed:
            retrieval_passed += 1
        if "retrieval_targets_missing" in retrieval_failures:
            missing_target_case_ids.append(case_id)
        cases.append(
            {
                "caseId": case_id,
                "answerPassed": answer_passed,
                "retrievalPassed": retrieval_case_passed,
                "retrievalFailures": retrieval_failures,
            }
        )
    targeted = len(retrieval_targets_by_id)
    return {
        "benchmarkId": private_manifest.get("benchmarkId", ""),
        "taskType": "mcq",
        "total": total,
        "predicted": total - len(invalid_case_ids),
        "correct": correct,
        "accuracy": (correct / total) if total else 0.0,
        "invalidCaseIds": invalid_case_ids,
        "wrongCaseIds": wrong_case_ids,
        "retrieval": {
            "total": total,
            "targeted": targeted,
            "passed": retrieval_passed,
            "accuracy": (retrieval_passed / total) if total else 0.0,
            "failedCaseIds": [case["caseId"] for case in cases if not case.get("retrievalPassed")],
            "missingTargetCaseIds": missing_target_case_ids,
            "targetPolicy": target_policy,
        },
        "cases": cases,
    }


def score_short_answer_predictions(
    private_manifest: dict[str, Any],
    predictions: list[dict[str, Any]],
    *,
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    answer_items = [
        item
        for item in private_manifest.get("answers", [])
        if isinstance(item, dict) and item.get("caseId") and "correctAnswer" in item
    ]
    allowed = {str(case_id) for case_id in case_ids or [] if str(case_id)}
    if allowed:
        answer_items = [
            item
            for item in answer_items
            if _case_id_selected(str(item.get("caseId") or ""), allowed)
        ]
    answer_by_id = {
        str(item.get("caseId") or ""): str(item.get("correctAnswer") or "")
        for item in answer_items
    }
    prediction_by_id = {
        str(item.get("caseId") or item.get("id") or ""): str(item.get("prediction") or "")
        for item in predictions
        if isinstance(item, dict)
    }
    correct = 0
    invalid_case_ids: list[str] = []
    wrong_case_ids: list[str] = []
    cases: list[dict[str, Any]] = []
    for case_id, gold in answer_by_id.items():
        prediction = prediction_by_id.get(case_id, "")
        passed = bool(prediction) and prediction == gold
        if not prediction:
            invalid_case_ids.append(case_id)
            wrong_case_ids.append(case_id)
        elif passed:
            correct += 1
        else:
            wrong_case_ids.append(case_id)
        cases.append({"caseId": case_id, "answerPassed": passed})
    total = len(answer_by_id)
    return {
        "benchmarkId": private_manifest.get("benchmarkId", ""),
        "taskType": "short_answer",
        "total": total,
        "predicted": total - len(invalid_case_ids),
        "correct": correct,
        "accuracy": (correct / total) if total else 0.0,
        "invalidCaseIds": invalid_case_ids,
        "wrongCaseIds": wrong_case_ids,
        "comparison": "exact_unicode_string",
        "cases": cases,
    }


def score_predictions(
    private_manifest: dict[str, Any],
    predictions_or_artifacts: list[dict[str, Any]],
    *,
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    if private_manifest.get("graders"):
        return score_legal_predictions(private_manifest, predictions_or_artifacts, case_ids=case_ids)
    if any(
        isinstance(item, dict) and "correctAnswer" in item
        for item in private_manifest.get("answers", [])
    ):
        return score_short_answer_predictions(private_manifest, predictions_or_artifacts, case_ids=case_ids)
    return score_mcq_predictions(private_manifest, predictions_or_artifacts, case_ids=case_ids)


def score_legal_predictions(
    private_manifest: dict[str, Any],
    artifacts: list[dict[str, Any]],
    *,
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    graders = [grader for grader in private_manifest.get("graders", []) if isinstance(grader, dict)]
    allowed = {str(case_id) for case_id in case_ids or [] if str(case_id)}
    if allowed:
        graders = [
            grader
            for grader in graders
            if _case_id_selected(str(grader.get("graderId") or ""), allowed)
        ]
    grader_by_id = {str(grader.get("graderId") or ""): grader for grader in graders if str(grader.get("graderId") or "")}
    cases: list[dict[str, Any]] = []
    passed = 0
    retrieval_passed = 0
    answer_passed = 0
    legal_artifacts = [artifact for artifact in artifacts if isinstance(artifact, dict)]
    if legal_artifacts:
        for artifact in legal_artifacts:
            grader_id = str(artifact.get("graderId") or artifact.get("caseId") or artifact.get("id") or "")
            grader = grader_by_id.get(grader_id)
            case_id = _artifact_score_case_id(artifact)
            retrieval_failures: list[str] = []
            answer_failures: list[str] = []
            if grader is None:
                failures = [f"missing_grader:{grader_id or case_id}"]
                retrieval_failures = failures
            else:
                retrieval_failures = _legal_retrieval_failures(grader, artifact)
                answer_failures = _legal_answer_failures(grader, artifact)
                failures = retrieval_failures + answer_failures
            case_passed = not failures
            retrieval_case_passed = not retrieval_failures
            if case_passed:
                passed += 1
            if retrieval_case_passed:
                retrieval_passed += 1
            if not answer_failures:
                answer_passed += 1
            cases.append(
                {
                    "caseId": case_id,
                    "passed": case_passed,
                    "failures": failures,
                    "retrievalPassed": retrieval_case_passed,
                    "retrievalFailures": retrieval_failures,
                    "answerFailures": answer_failures,
                }
            )
    else:
        for grader in graders:
            case_id = str(grader.get("graderId") or "")
            retrieval_failures = _legal_retrieval_failures(grader, {})
            answer_failures = _legal_answer_failures(grader, {})
            failures = retrieval_failures + answer_failures
            if not answer_failures:
                answer_passed += 1
            cases.append(
                {
                    "caseId": case_id,
                    "passed": False,
                    "failures": failures,
                    "retrievalPassed": False,
                    "retrievalFailures": retrieval_failures,
                    "answerFailures": answer_failures,
                }
            )
    total = len(cases)
    return {
        "benchmarkId": private_manifest.get("benchmarkId", ""),
        "taskType": "legal_retrieval_answer",
        "total": total,
        "passed": passed,
        "accuracy": (passed / total) if total else 0.0,
        "retrieval": {
            "total": total,
            "passed": retrieval_passed,
            "accuracy": (retrieval_passed / total) if total else 0.0,
            "failedCaseIds": [case["caseId"] for case in cases if not case.get("retrievalPassed")],
        },
        "answer": {
            "total": total,
            "passed": answer_passed,
            "accuracy": (answer_passed / total) if total else 0.0,
            "failedCaseIds": [case["caseId"] for case in cases if case.get("answerFailures")],
        },
        "cases": cases,
    }


def _case_id_selected(case_id: str, allowed: set[str]) -> bool:
    normalized = str(case_id or "").strip()
    if not normalized:
        return False
    lowered = normalized.lower()
    allowed_lower = {item.strip().lower() for item in allowed if item.strip()}
    if lowered in allowed_lower:
        return True
    return any(
        lowered.endswith(f"{separator}{candidate}")
        for candidate in allowed_lower
        for separator in ("-", "_", ".")
    )


def _score_legal_artifact(grader: dict[str, Any], artifact: dict[str, Any]) -> list[str]:
    return _legal_retrieval_failures(grader, artifact) + _legal_answer_failures(grader, artifact)


def _mcq_retrieval_targets_by_case(
    private_manifest: dict[str, Any],
    answer_items: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    by_case: dict[str, dict[str, Any]] = {}
    for answer in answer_items:
        case_id = str(answer.get("caseId") or "")
        if not case_id:
            continue
        entry = _mcq_retrieval_target_entry(answer)
        if entry:
            by_case[case_id] = entry
    for item in private_manifest.get("retrievalTargets", []) or []:
        if not isinstance(item, dict):
            continue
        case_id = str(item.get("caseId") or "")
        if not case_id:
            continue
        entry = _mcq_retrieval_target_entry(item)
        if entry:
            by_case[case_id] = entry
    return by_case


def _mcq_retrieval_target_entry(value: dict[str, Any]) -> dict[str, Any]:
    targets_value = value.get("targets")
    if not isinstance(targets_value, list):
        targets_value = value.get("primaryTargets")
    targets = [target for target in targets_value or [] if isinstance(target, dict)]
    if not targets:
        target = _target_from_inline_fields(value)
        if target:
            targets = [target]
    if not targets:
        return {}
    rank_rules = value.get("rankRules") if isinstance(value.get("rankRules"), dict) else {}
    return {"targets": targets, "rankRules": rank_rules}


def _mcq_retrieval_target_policy(
    private_manifest: dict[str, Any],
    retrieval_targets_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    explicit = private_manifest.get("retrievalTargetPolicy") if isinstance(private_manifest.get("retrievalTargetPolicy"), dict) else {}
    version = str(explicit.get("version") or "inferred_v1")
    blockers = [str(item) for item in explicit.get("blockers", []) or [] if str(item)]
    claimability = str(explicit.get("claimability") or "").strip().lower()
    if claimability in {"diagnostic_only", "diagnostic-only", "not_claimable"}:
        return {
            "claimable": False,
            "blockers": _unique_strings(blockers or ["retrieval_target_policy_diagnostic_only"]),
            "version": version,
        }

    inferred_blockers: list[str] = []
    if not retrieval_targets_by_id:
        inferred_blockers.append("retrieval_targets_missing")
    for entry in retrieval_targets_by_id.values():
        targets = [target for target in entry.get("targets", []) if isinstance(target, dict)]
        if not targets:
            inferred_blockers.append("retrieval_targets_missing")
            continue
        for target in targets:
            has_source_identifier = any(str(target.get(key) or "").strip() for key in TARGET_SOURCE_ID_KEYS)
            has_text_only = bool(str(target.get("textContains") or "").strip()) and not has_source_identifier
            if has_text_only:
                inferred_blockers.append("text_target_option_only")
            elif not has_source_identifier:
                inferred_blockers.append("target_without_source_identifier")
    blocker_list = _unique_strings(blockers + inferred_blockers)
    return {"claimable": not blocker_list, "blockers": blocker_list, "version": version}


def _target_from_inline_fields(value: dict[str, Any]) -> dict[str, Any]:
    target_keys = TARGET_SOURCE_ID_KEYS + ("textContains", "textContainsAll", "textContainsAny")
    return {key: value[key] for key in target_keys if value.get(key)}


def _mcq_retrieval_failures(entry: dict[str, Any] | None, artifact: dict[str, Any]) -> list[str]:
    if not entry:
        return ["retrieval_targets_missing"]
    targets = [target for target in entry.get("targets", []) if isinstance(target, dict)]
    if not targets:
        return ["retrieval_targets_missing"]
    if not artifact:
        return ["missing_artifact"]
    rank_rules = entry.get("rankRules") if isinstance(entry.get("rankRules"), dict) else {}
    matches = _target_rank_matches(targets, artifact)
    ranks = {index: rank for index, (rank, _record) in matches.items()}
    failures: list[str] = []

    within = rank_rules.get("primaryMustAppearWithin")
    if within is not None:
        limit = int(within)
        if not any(rank <= limit for rank in ranks.values()):
            failures.append(f"rank:primary_not_within:{limit}")

    required_count = rank_rules.get("atLeastTargetsWithinTopK")
    if required_count is None and within is None:
        required_count = len(targets) if rank_rules.get("mustMatchAllTargets") else 1
    if required_count is not None:
        top_k = int(rank_rules.get("targetTopK") or rank_rules.get("candidateLimit") or max([rank for rank, _record in _retrieved_records(artifact)] or [0]) or 50)
        matched = sum(1 for rank in ranks.values() if rank <= top_k)
        if matched < int(required_count):
            failures.append(f"rank:targets_within_top_k:{matched}<{int(required_count)}@{top_k}")
    return _unique_strings(failures)


def _legal_retrieval_failures(grader: dict[str, Any], artifact: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if not artifact:
        failures.append("missing_artifact")
    else:
        failures.extend(_legal_leakage_failures(grader, artifact))
        failures.extend(_legal_rank_failures(grader, artifact))
    return failures


def _artifact_score_case_id(artifact: dict[str, Any]) -> str:
    case_id = str(artifact.get("caseId") or artifact.get("id") or artifact.get("graderId") or "")
    variant_id = str(artifact.get("variantId") or "")
    if case_id and variant_id:
        return f"{case_id}__{variant_id}"
    return case_id


def _legal_leakage_failures(grader: dict[str, Any], artifact: dict[str, Any]) -> list[str]:
    guards = grader.get("leakageGuards") if isinstance(grader.get("leakageGuards"), dict) else {}
    failures: list[str] = []
    forbidden_fields = {str(field) for field in guards.get("forbiddenRuntimeFields", []) if str(field)}
    leaked_fields = sorted(_runtime_field_hits(artifact, forbidden_fields))
    failures.extend(f"leakage:forbidden_runtime_field:{field}" for field in leaked_fields)

    terms = [str(term) for term in guards.get("forbiddenSearchMetadataTerms", []) if str(term)]
    if terms:
        metadata_text = "\n".join(_retrieved_metadata_fragments(artifact))
        for term in terms:
            if term in metadata_text:
                failures.append(f"leakage:forbidden_search_metadata_term:{term}")
    return failures


def _runtime_field_hits(value: Any, forbidden_fields: set[str]) -> set[str]:
    hits: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if key_text in forbidden_fields:
                hits.add(key_text)
            hits.update(_runtime_field_hits(child, forbidden_fields))
    elif isinstance(value, list):
        for child in value:
            hits.update(_runtime_field_hits(child, forbidden_fields))
    return hits


def _retrieved_metadata_fragments(artifact: dict[str, Any]) -> list[str]:
    fragments: list[str] = []
    for key in ("searchResults", "retrievedCases", "selectedEvidence", "sources", "passages", "candidates"):
        value = artifact.get(key)
        if isinstance(value, list):
            for item in value:
                fragments.extend(_metadata_value_fragments(item))
        elif isinstance(value, dict):
            fragments.extend(_metadata_value_fragments(value))
    return fragments


def _metadata_value_fragments(value: Any, *, key_name: str = "") -> list[str]:
    content_keys = {
        "answer",
        "query",
        "prompt",
        "body",
        "text",
        "full_text",
        "fullText",
        "anchor_text",
        "extracted_text",
        "quote",
        "claimSummary",
    }
    fragments: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in content_keys:
                continue
            fragments.extend(_metadata_value_fragments(child, key_name=str(key)))
    elif isinstance(value, list):
        for child in value:
            fragments.extend(_metadata_value_fragments(child, key_name=key_name))
    elif isinstance(value, (str, int, float)):
        fragments.append(str(value))
    return fragments


def _legal_rank_failures(grader: dict[str, Any], artifact: dict[str, Any]) -> list[str]:
    rank_rules = grader.get("rankRules") if isinstance(grader.get("rankRules"), dict) else {}
    primary_targets = [target for target in grader.get("primaryTargets", []) if isinstance(target, dict)]
    matches = _target_rank_matches(primary_targets, artifact)
    ranks = {index: rank for index, (rank, _record) in matches.items()}
    failures: list[str] = []

    within = rank_rules.get("primaryMustAppearWithin")
    if within is not None:
        limit = int(within)
        if not any(rank <= limit for rank in ranks.values()):
            failures.append(f"rank:primary_not_within:{limit}")

    required_count = rank_rules.get("atLeastTargetsWithinTopK")
    if required_count is not None:
        top_k = int(rank_rules.get("targetTopK") or rank_rules.get("candidateLimit") or 50)
        matched = sum(1 for rank in ranks.values() if rank <= top_k)
        if matched < int(required_count):
            failures.append(f"rank:targets_within_top_k:{matched}<{int(required_count)}@{top_k}")
    if rank_rules.get("requiredAnswerMustAppearInPrimary"):
        for target_index, target in enumerate(primary_targets):
            required_answer = str(target.get("requiredAnswerText") or "")
            if not required_answer:
                continue
            _rank, record = matches.get(target_index, (0, {}))
            if required_answer not in json.dumps(record, ensure_ascii=False):
                failures.append("rank:required_answer_missing_in_primary")
    return failures


def _target_ranks(targets: list[dict[str, Any]], artifact: dict[str, Any]) -> dict[int, int]:
    return {index: rank for index, (rank, _record) in _target_rank_matches(targets, artifact).items()}


def _target_rank_matches(targets: list[dict[str, Any]], artifact: dict[str, Any]) -> dict[int, tuple[int, dict[str, Any]]]:
    records = _retrieved_records(artifact)
    matches: dict[int, tuple[int, dict[str, Any]]] = {}
    for target_index, target in enumerate(targets):
        for rank, record in records:
            if _target_matches_record(target, record):
                matches[target_index] = (rank, record)
                break
    return matches


def _retrieved_records(artifact: dict[str, Any]) -> list[tuple[int, dict[str, Any]]]:
    records: list[tuple[int, dict[str, Any]]] = []
    for key in ("retrievedCases", "searchResults", "selectedEvidence", "sources", "candidates", "contextPackets"):
        value = artifact.get(key)
        if not isinstance(value, list):
            continue
        for offset, item in enumerate(value, start=1):
            if isinstance(item, dict):
                rank = int(item.get("rank") or offset)
                records.append((rank, item))
    for key in ("selectedEvidenceIds", "contextPacketIds"):
        value = artifact.get(key)
        if not isinstance(value, list):
            continue
        for offset, item in enumerate(value, start=1):
            if item:
                records.append((offset, {"id": str(item), "sourceId": str(item)}))
    return records


def _target_matches_record(target: dict[str, Any], record: dict[str, Any]) -> bool:
    text = json.dumps(record, ensure_ascii=False)
    primary_identifiers = [
        str(target.get(key) or "")
        for key in TARGET_SOURCE_ID_KEYS
        if str(target.get(key) or "")
    ]
    if primary_identifiers:
        return any(identifier in text for identifier in primary_identifiers) and _target_anchor_constraints_match(target, text)
    if _target_has_anchor_constraints(target):
        return _target_anchor_constraints_match(target, text)
    text_contains = str(target.get("textContains") or "")
    if text_contains:
        return text_contains in text
    decision_date = str(target.get("decisionDate") or "")
    if decision_date:
        return decision_date in text
    court = str(target.get("court") or "")
    return bool(court and court in text)


def _target_has_anchor_constraints(target: dict[str, Any]) -> bool:
    return bool(
        str(target.get("textContains") or "").strip()
        or _target_text_list(target.get("textContainsAll"))
        or _target_text_list(target.get("textContainsAny"))
    )


def _target_anchor_constraints_match(target: dict[str, Any], text: str) -> bool:
    required = _target_text_list(target.get("textContainsAll"))
    single = str(target.get("textContains") or "").strip()
    if single:
        required.append(single)
    if any(value not in text for value in required):
        return False
    any_values = _target_text_list(target.get("textContainsAny"))
    if any_values and not any(value in text for value in any_values):
        return False
    return True


def _target_text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _unique_strings(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        if value and value not in out:
            out.append(value)
    return out


def _legal_answer_failures(grader: dict[str, Any], artifact: dict[str, Any]) -> list[str]:
    answer = str(artifact.get("answer") or artifact.get("answerMarkdown") or "")
    answer_rules = grader.get("answerRules") if isinstance(grader.get("answerRules"), dict) else {}
    failures: list[str] = []

    for phrase in answer_rules.get("mustDiscuss", []) or []:
        phrase_text = str(phrase)
        if phrase_text and phrase_text not in answer:
            failures.append(f"answer:missing_must_discuss:{phrase_text}")

    any_phrases = [str(phrase) for phrase in answer_rules.get("mustDiscussAny", []) or [] if str(phrase)]
    if any_phrases and not any(phrase in answer for phrase in any_phrases):
        failures.append("answer:missing_must_discuss_any")

    for concept in answer_rules.get("forbiddenConcepts", []) or []:
        concept_text = str(concept)
        if concept_text and concept_text in answer:
            failures.append(f"answer:forbidden_concept:{concept_text}")

    for target in grader.get("primaryTargets", []) or []:
        if isinstance(target, dict) and target.get("requiredAnswerText"):
            required = str(target.get("requiredAnswerText"))
            if required not in answer:
                failures.append(f"answer:missing_required_answer_text:{required}")

    required_target_count = answer_rules.get("mustUseAtLeastTargetCount")
    if required_target_count is not None:
        count = _answer_target_reference_count(grader, answer)
        if count < int(required_target_count):
            failures.append(f"answer:target_reference_count:{count}<{int(required_target_count)}")

    if answer_rules.get("forbidFakeCitations"):
        known_case_numbers = {
            str(target.get("caseNumber"))
            for target in grader.get("primaryTargets", []) or []
            if isinstance(target, dict) and target.get("caseNumber")
        }
        fake = sorted({case for case in CASE_NUMBER_RE.findall(answer) if case not in known_case_numbers})
        failures.extend(f"answer:fake_citation:{case}" for case in fake)
    return failures


def _answer_target_reference_count(grader: dict[str, Any], answer: str) -> int:
    count = 0
    for target in grader.get("primaryTargets", []) or []:
        if not isinstance(target, dict):
            continue
        identifiers = [str(target.get(key) or "") for key in ("caseNumber", "fileName") if str(target.get(key) or "")]
        if any(identifier in answer for identifier in identifiers):
            count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Score unified benchmark predictions.")
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--graphed-results-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--case-id", action="append", default=[])
    args = parser.parse_args()
    private = json.loads(args.private.read_text(encoding="utf-8"))
    artifacts = (
        load_json_artifacts(args.graphed_results_dir)
        if private.get("graders")
        else load_graphed_regression_predictions(args.graphed_results_dir)
    )
    summary = score_predictions(private, artifacts, case_ids=args.case_id)
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
