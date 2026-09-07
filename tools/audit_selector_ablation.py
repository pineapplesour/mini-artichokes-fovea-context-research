#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


EXPECTED_ARM_MODES = ("raw", "context_packets_v1")


def audit_selector_ablation_report(report: dict[str, Any]) -> dict[str, Any]:
    report_blockers: list[str] = []
    improvement_blockers: list[str] = []
    arm_modes = [str(item) for item in report.get("arms", []) if str(item)]
    if sorted(arm_modes) != sorted(EXPECTED_ARM_MODES):
        report_blockers.append("selector_ablation_arms_missing")
    if len(set(arm_modes)) != len(arm_modes):
        report_blockers.append("selector_ablation_arms_not_distinct")

    case_reports: list[dict[str, Any]] = []
    target_relations: Counter[str] = Counter()
    structural_relations: Counter[str] = Counter()
    for case in report.get("cases", []) or []:
        if not isinstance(case, dict):
            continue
        case_report = _audit_case(case)
        case_reports.append(case_report)
        report_blockers.extend(case_report["reportBlockers"])
        target_relations[case_report["targetRelation"]] += 1
        structural_relations[case_report["structuralRelation"]] += 1

    target_regressions = target_relations.get("context_worse", 0)
    structural_regressions = structural_relations.get("raw_only_valid", 0)
    if target_regressions > 0:
        improvement_blockers.append("context_target_regression_present")
    if structural_regressions > 0:
        improvement_blockers.append("context_structural_regression_present")
    if not case_reports:
        report_blockers.append("no_comparable_cases")

    report_blockers = _unique(report_blockers)
    target_eval_aggregate = _aggregate_target_eval(case_reports)
    if not report_blockers:
        improvement_blockers.extend(_promotion_blockers(report, case_reports, target_eval_aggregate))
    else:
        improvement_blockers.append("ablation_report_invalid")
    improvement_blockers = _unique(improvement_blockers)
    improvement_claimable = not report_blockers and not improvement_blockers
    return {
        "status": "completed",
        "ablationId": str(report.get("ablationId") or ""),
        "schemaVersion": str(report.get("schemaVersion") or ""),
        "promotionPolicyVersion": "context_packet_retrieval_promotion_v1",
        "ablationReportValid": not report_blockers,
        "contextPacketRetrievalImprovementClaimable": improvement_claimable,
        "reportBlockers": report_blockers,
        "improvementClaimBlockers": improvement_blockers,
        "claimBlockers": _unique(report_blockers + improvement_blockers),
        "caseCount": len(case_reports),
        "aggregate": {
            "targetComparison": {
                "contextTargetImprovementCount": target_relations.get("context_better", 0),
                "contextTargetRegressionCount": target_regressions,
                "targetTieCount": target_relations.get("tie", 0),
                "notTargetedCount": target_relations.get("not_targeted", 0),
            },
            "targetEval": target_eval_aggregate,
            "structuralComparison": {
                "bothRetrievalValidCount": structural_relations.get("both_valid", 0),
                "rawOnlyRetrievalValidCount": structural_regressions,
                "contextOnlyRetrievalValidCount": structural_relations.get("context_only_valid", 0),
                "neitherRetrievalValidCount": structural_relations.get("neither_valid", 0),
            },
        },
        "cases": case_reports,
    }


def audit_selector_ablation_path(path: Path) -> dict[str, Any]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "status": "failed",
            "ablationReportValid": False,
            "contextPacketRetrievalImprovementClaimable": False,
            "reportBlockers": ["selector_ablation_schema_invalid"],
            "improvementClaimBlockers": [],
            "claimBlockers": ["selector_ablation_schema_invalid"],
            "reason": str(exc),
        }
    if not isinstance(report, dict):
        return {
            "status": "failed",
            "ablationReportValid": False,
            "contextPacketRetrievalImprovementClaimable": False,
            "reportBlockers": ["selector_ablation_schema_invalid"],
            "improvementClaimBlockers": [],
            "claimBlockers": ["selector_ablation_schema_invalid"],
        }
    return audit_selector_ablation_report(report)


def _audit_case(case: dict[str, Any]) -> dict[str, Any]:
    arms = case.get("arms") if isinstance(case.get("arms"), dict) else {}
    raw = arms.get("raw") if isinstance(arms.get("raw"), dict) else {}
    context = arms.get("context_packets_v1") if isinstance(arms.get("context_packets_v1"), dict) else {}
    blockers: list[str] = []
    if not raw or not context:
        blockers.append("selector_ablation_arms_missing")
    if _mode(raw) != "raw" or _mode(context) != "context_packets_v1":
        blockers.append("selector_input_mode_not_as_declared")
    if raw and context and _candidate_digest(raw) != _candidate_digest(context):
        blockers.append("candidate_set_digest_mismatch")
    if raw and context and _selector_model_key(raw) != _selector_model_key(context):
        blockers.append("selector_provider_model_decoding_mismatch")
    for arm in (raw, context):
        if not arm:
            continue
        if bool(arm.get("selectorFallback")):
            blockers.append("selector_fallback_used")
        if bool(arm.get("directWriterFallback")):
            blockers.append("direct_writer_fallback_used")
        if bool(arm.get("writerRan")):
            blockers.append("writer_ran_in_selector_ablation")
        if bool(arm.get("answerQualityScorePresent")) or "answerScore" in arm:
            blockers.append("answer_quality_score_present_in_selector_ablation")
        if "selectedEvidenceCount" not in arm:
            blockers.append("selected_evidence_fields_missing")
        if _selected_count(arm) > 0 and not _selected_backing_ids(arm):
            blockers.append("provenance_fields_missing")
    if context:
        if _safe_int(context.get("contextPacketCount")) <= 0:
            blockers.append("context_packet_arm_zero_packets")
        if _safe_int(context.get("contextPacketProvenanceCount")) <= 0:
            blockers.append("context_packet_arm_missing_provenance")

    raw_valid = _arm_retrieval_valid(raw)
    context_valid = _arm_retrieval_valid(context) and _safe_int(context.get("contextPacketCount")) > 0
    structural_relation = _structural_relation(raw_valid, context_valid)
    target_relation = _target_relation(raw, context)
    target_eval = _case_target_eval(raw, context)
    return {
        "caseId": str(case.get("caseId") or case.get("id") or ""),
        "comparable": not blockers,
        "reportBlockers": _unique(blockers),
        "rawRetrievalValid": raw_valid,
        "contextRetrievalValid": context_valid,
        "structuralRelation": structural_relation,
        "targetRelation": target_relation,
        "targetEval": target_eval,
    }


def _mode(arm: dict[str, Any]) -> str:
    return str(arm.get("selectorInputMode") or arm.get("armId") or "")


def _candidate_digest(arm: dict[str, Any]) -> str:
    return str(arm.get("candidateSetDigest") or "")


def _selector_model_key(arm: dict[str, Any]) -> str:
    return json.dumps(
        {
            "provider": str(arm.get("selectorProvider") or ""),
            "model": str(arm.get("selectorModel") or ""),
            "decoding": arm.get("selectorDecoding") if isinstance(arm.get("selectorDecoding"), dict) else {},
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _arm_retrieval_valid(arm: dict[str, Any]) -> bool:
    return (
        bool(arm)
        and not bool(arm.get("selectorFallback"))
        and not bool(arm.get("directWriterFallback"))
        and not bool(arm.get("writerRan"))
        and _selected_count(arm) > 0
        and bool(_selected_backing_ids(arm))
    )


def _selected_count(arm: dict[str, Any]) -> int:
    if "selectedEvidenceCount" in arm:
        return _safe_int(arm.get("selectedEvidenceCount"))
    selected = arm.get("selectedEvidenceIds")
    if isinstance(selected, list):
        return len(selected)
    return 0


def _selected_backing_ids(arm: dict[str, Any]) -> list[str]:
    for key in ("selectedBackingEvidenceIds", "selectedSourceIds", "selectedChunkIds", "selectedEvidenceIds"):
        value = arm.get(key)
        if isinstance(value, list):
            ids = [str(item) for item in value if str(item)]
            if ids:
                return ids
    return []


def _structural_relation(raw_valid: bool, context_valid: bool) -> str:
    if raw_valid and context_valid:
        return "both_valid"
    if raw_valid and not context_valid:
        return "raw_only_valid"
    if context_valid and not raw_valid:
        return "context_only_valid"
    return "neither_valid"


def _target_relation(raw: dict[str, Any], context: dict[str, Any]) -> str:
    raw_eval = raw.get("targetEval") if isinstance(raw.get("targetEval"), dict) else {}
    context_eval = context.get("targetEval") if isinstance(context.get("targetEval"), dict) else {}
    if not raw_eval and not context_eval:
        return "not_targeted"
    raw_pass = bool(raw_eval.get("pass"))
    context_pass = bool(context_eval.get("pass"))
    if context_pass and not raw_pass:
        return "context_better"
    if raw_pass and not context_pass:
        return "context_worse"
    return "tie"


def _case_target_eval(raw: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    raw_eval = raw.get("targetEval") if isinstance(raw.get("targetEval"), dict) else {}
    context_eval = context.get("targetEval") if isinstance(context.get("targetEval"), dict) else {}
    raw_target_ids = _target_ids(raw_eval)
    context_target_ids = _target_ids(context_eval)
    target_ids = _sorted_ids(set(raw_target_ids) | set(context_target_ids))
    raw_covered = set(_covered_target_ids(raw_eval)) & set(target_ids)
    context_covered = set(_covered_target_ids(context_eval)) & set(target_ids)
    raw_only = raw_covered - context_covered
    context_only = context_covered - raw_covered
    target_bearing = bool(raw_eval or context_eval or target_ids)
    target_identity_complete = bool(target_ids) and set(raw_target_ids) == set(context_target_ids)
    return {
        "targetBearing": target_bearing,
        "evaluable": bool(target_bearing and target_identity_complete),
        "targetIds": target_ids,
        "rawTargetIds": raw_target_ids,
        "contextTargetIds": context_target_ids,
        "rawCoveredTargetIds": _sorted_ids(raw_covered),
        "contextCoveredTargetIds": _sorted_ids(context_covered),
        "rawOnlyTargetIds": _sorted_ids(raw_only),
        "contextOnlyTargetIds": _sorted_ids(context_only),
        "rawTargetHitSource": str(raw_eval.get("targetHitSource") or ""),
        "contextTargetHitSource": str(context_eval.get("targetHitSource") or ""),
        "rawSelectedEvidenceCount": _selected_count(raw),
        "contextSelectedEvidenceCount": _selected_count(context),
    }


def _target_ids(target_eval: dict[str, Any]) -> list[str]:
    value = target_eval.get("targetIds")
    if isinstance(value, list):
        return _sorted_ids(str(item) for item in value if str(item))
    covered = target_eval.get("coveredTargetIds")
    missed = target_eval.get("missedTargetIds")
    if isinstance(covered, list) or isinstance(missed, list):
        return _sorted_ids(
            str(item)
            for values in (covered if isinstance(covered, list) else [], missed if isinstance(missed, list) else [])
            for item in values
            if str(item)
        )
    return []


def _covered_target_ids(target_eval: dict[str, Any]) -> list[str]:
    value = target_eval.get("coveredTargetIds")
    if isinstance(value, list):
        return _sorted_ids(str(item) for item in value if str(item))
    return []


def _aggregate_target_eval(case_reports: list[dict[str, Any]]) -> dict[str, Any]:
    target_bearing_cases = [case for case in case_reports if case.get("targetEval", {}).get("targetBearing")]
    evaluable_cases = [case for case in target_bearing_cases if case.get("targetEval", {}).get("evaluable")]
    target_count_total = 0
    raw_covered_total = 0
    context_covered_total = 0
    context_only_total = 0
    raw_only_total = 0
    both_covered_total = 0
    neither_covered_total = 0
    improved_cases = 0
    regressed_cases = 0
    tied_cases = 0
    unmappable_target_count = 0
    raw_recalls: list[float] = []
    context_recalls: list[float] = []
    for case in target_bearing_cases:
        target_eval = case.get("targetEval", {})
        target_ids = set(target_eval.get("targetIds") or [])
        raw_covered = set(target_eval.get("rawCoveredTargetIds") or [])
        context_covered = set(target_eval.get("contextCoveredTargetIds") or [])
        if not target_eval.get("evaluable"):
            unmappable_target_count += max(1, len(target_ids))
            continue
        target_count = len(target_ids)
        target_count_total += target_count
        raw_covered_total += len(raw_covered)
        context_covered_total += len(context_covered)
        context_only = context_covered - raw_covered
        raw_only = raw_covered - context_covered
        both = raw_covered & context_covered
        neither = target_ids - (raw_covered | context_covered)
        context_only_total += len(context_only)
        raw_only_total += len(raw_only)
        both_covered_total += len(both)
        neither_covered_total += len(neither)
        if raw_only:
            regressed_cases += 1
        elif context_only:
            improved_cases += 1
        else:
            tied_cases += 1
        if target_count:
            raw_recalls.append(len(raw_covered) / target_count)
            context_recalls.append(len(context_covered) / target_count)
    raw_micro = (raw_covered_total / target_count_total) if target_count_total else 0.0
    context_micro = (context_covered_total / target_count_total) if target_count_total else 0.0
    raw_mean = (sum(raw_recalls) / len(raw_recalls)) if raw_recalls else 0.0
    context_mean = (sum(context_recalls) / len(context_recalls)) if context_recalls else 0.0
    strict_dominance = bool(target_count_total and context_only_total > 0 and raw_only_total == 0)
    return {
        "privateRetrievalTargetsPresent": bool(target_bearing_cases),
        "targetEvalPresent": bool(target_bearing_cases),
        "targetHitSource": "selected_backing_evidence_only",
        "caseCount": len(case_reports),
        "targetBearingCaseCount": len(target_bearing_cases),
        "evaluableTargetBearingCaseCount": len(evaluable_cases),
        "excludedTargetBearingCaseCount": len(target_bearing_cases) - len(evaluable_cases),
        "targetCountTotal": target_count_total,
        "unmappableTargetCount": unmappable_target_count,
        "raw": {
            "coveredTargetCount": raw_covered_total,
            "missedTargetCount": max(0, target_count_total - raw_covered_total),
            "microTargetRecall": raw_micro,
            "meanCaseTargetRecall": raw_mean,
        },
        "context_packets_v1": {
            "coveredTargetCount": context_covered_total,
            "missedTargetCount": max(0, target_count_total - context_covered_total),
            "microTargetRecall": context_micro,
            "meanCaseTargetRecall": context_mean,
        },
        "pairedDelta": {
            "contextOnlyTargetCount": context_only_total,
            "rawOnlyTargetCount": raw_only_total,
            "bothCoveredTargetCount": both_covered_total,
            "neitherCoveredTargetCount": neither_covered_total,
            "coveredTargetDelta": context_covered_total - raw_covered_total,
            "microTargetRecallDelta": context_micro - raw_micro,
            "meanCaseTargetRecallDelta": context_mean - raw_mean,
            "improvedTargetCaseCount": improved_cases,
            "regressedTargetCaseCount": regressed_cases,
            "tiedTargetCaseCount": tied_cases,
            "strictTargetDominance": strict_dominance,
        },
    }


def _promotion_blockers(
    report: dict[str, Any],
    case_reports: list[dict[str, Any]],
    target_eval: dict[str, Any],
) -> list[str]:
    blockers: list[str] = []
    suite = report.get("suite") if isinstance(report.get("suite"), dict) else {}
    if suite.get("targetManifestLocked") is not True:
        blockers.append("target_manifest_not_locked")
    if suite.get("targetsVisibleToEngine") is not False:
        blockers.append("targets_visible_to_engine")

    if not target_eval.get("privateRetrievalTargetsPresent"):
        blockers.append("private_retrieval_targets_absent")
        return blockers
    if not target_eval.get("targetEvalPresent"):
        blockers.append("target_eval_missing")
    if target_eval.get("evaluableTargetBearingCaseCount") != target_eval.get("targetBearingCaseCount"):
        blockers.append("target_eval_not_complete")
    if _safe_int(target_eval.get("excludedTargetBearingCaseCount")):
        blockers.append("target_bearing_cases_excluded")
    if _safe_int(target_eval.get("unmappableTargetCount")):
        blockers.append("unmappable_targets")
    if _safe_int(target_eval.get("targetCountTotal")) <= 0:
        blockers.append("no_private_retrieval_targets")
    if _safe_int(target_eval.get("targetBearingCaseCount")) <= 0:
        blockers.append("no_target_bearing_cases")

    for case in case_reports:
        case_target = case.get("targetEval") if isinstance(case.get("targetEval"), dict) else {}
        if not case_target.get("targetBearing"):
            continue
        if case_target.get("rawTargetHitSource") != "selected_backing_evidence_only":
            blockers.append("target_hits_not_from_selected_backing_evidence")
        if case_target.get("contextTargetHitSource") != "selected_backing_evidence_only":
            blockers.append("target_hits_not_from_selected_backing_evidence")
        if _safe_int(case_target.get("rawSelectedEvidenceCount")) <= 0:
            blockers.append("zero_selected_evidence_on_target_bearing_cases")
        if _safe_int(case_target.get("contextSelectedEvidenceCount")) <= 0:
            blockers.append("zero_selected_evidence_on_target_bearing_cases")

    delta = target_eval.get("pairedDelta") if isinstance(target_eval.get("pairedDelta"), dict) else {}
    context_only = _safe_int(delta.get("contextOnlyTargetCount"))
    raw_only = _safe_int(delta.get("rawOnlyTargetCount"))
    if context_only <= 0:
        raw_summary = target_eval.get("raw") if isinstance(target_eval.get("raw"), dict) else {}
        context_summary = target_eval.get("context_packets_v1") if isinstance(target_eval.get("context_packets_v1"), dict) else {}
        target_count = _safe_int(target_eval.get("targetCountTotal"))
        if (
            target_count > 0
            and _safe_int(raw_summary.get("coveredTargetCount")) == target_count
            and _safe_int(context_summary.get("coveredTargetCount")) == target_count
        ):
            blockers.append("target_metric_saturated_no_strict_improvement")
        else:
            blockers.append("no_context_only_target_gain")
    if raw_only != 0:
        blockers.append("raw_only_targets_lost_by_context_packets")
    if _safe_int(delta.get("coveredTargetDelta")) <= 0:
        blockers.append("covered_target_delta_not_positive")
    if float(delta.get("microTargetRecallDelta") or 0.0) <= 0.0:
        blockers.append("micro_target_recall_delta_not_positive")
    if float(delta.get("meanCaseTargetRecallDelta") or 0.0) <= 0.0:
        blockers.append("mean_case_target_recall_delta_not_positive")
    if _safe_int(delta.get("improvedTargetCaseCount")) <= 0:
        blockers.append("no_improved_target_cases")
    if _safe_int(delta.get("regressedTargetCaseCount")) != 0:
        blockers.append("regressed_target_cases")
    if delta.get("strictTargetDominance") is not True:
        blockers.append("strict_target_dominance_false")
    return blockers


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _sorted_ids(values: Any) -> list[str]:
    return sorted({str(value) for value in values if str(value)})


def _unique(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        if value and value not in out:
            out.append(value)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit raw-vs-context-packet selector ablation reports.")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    audit = audit_selector_ablation_path(args.report)
    text = json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
