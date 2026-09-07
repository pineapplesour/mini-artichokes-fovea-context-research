#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


FALLBACK_SELECTOR_STATUSES = {"fallback_no_selection", "fallback_low_coverage", "fallback_selector_error"}


def audit_results_dir(results_dir: Path) -> dict[str, Any]:
    artifacts = load_artifacts(results_dir)
    selector_counts = Counter(_selector_status(item) for item in artifacts)
    delta_counts = Counter(_delta(item) for item in artifacts)
    selected_count_buckets = Counter(_selected_count_bucket(_selected_count(item)) for item in artifacts)
    cited_count_buckets = Counter(_selected_count_bucket(_cited_count(item)) for item in artifacts)
    context_packet_buckets = Counter(_selected_count_bucket(_context_packet_count(item)) for item in artifacts)
    source_grounded = [_artifact_id(item) for item in artifacts if _is_source_grounded(item)]
    retrieval_valid = [_artifact_id(item) for item in artifacts if _is_retrieval_valid(item)]

    fallback_with_selected = [
        _artifact_id(item)
        for item in artifacts
        if _selector_status(item) in FALLBACK_SELECTOR_STATUSES and _selected_count(item) > 0
    ]
    direct_writer_fallback = [_artifact_id(item) for item in artifacts if _direct_writer_fallback(item)]
    zero_selected = [_artifact_id(item) for item in artifacts if _selected_count(item) <= 0]
    no_cited_claims = [_artifact_id(item) for item in artifacts if _cited_count(item) <= 0]
    selected_without_citations = [
        _artifact_id(item)
        for item in artifacts
        if _selected_count(item) > 0 and _cited_count(item) == 0
    ]
    missing_context_packet_provenance = [
        _artifact_id(item)
        for item in artifacts
        if _selector_status(item) == "completed"
        and not _direct_writer_fallback(item)
        and _selected_count(item) > 0
        and _cited_count(item) > 0
        and _context_packet_count(item) <= 0
    ]
    improvement_without_completed = [
        _artifact_id(item)
        for item in artifacts
        if _delta(item) == "improved" and _selector_status(item) != "completed"
    ]
    regression_without_completed = [
        _artifact_id(item)
        for item in artifacts
        if _delta(item) == "regressed" and _selector_status(item) != "completed"
    ]
    credible_improvements = [
        _artifact_id(item)
        for item in artifacts
        if _delta(item) == "improved" and _is_retrieval_valid(item)
    ]
    noisy_improvements = [
        _artifact_id(item)
        for item in artifacts
        if _delta(item) == "improved" and _artifact_id(item) not in set(credible_improvements)
    ]

    return {
        "resultsDir": str(results_dir),
        "totalArtifacts": len(artifacts),
        "selectorStatusCounts": dict(sorted(selector_counts.items())),
        "deltaCounts": dict(sorted(delta_counts.items())),
        "selectedCountBuckets": dict(sorted(selected_count_buckets.items())),
        "citedClaimCountBuckets": dict(sorted(cited_count_buckets.items())),
        "contextPacketCountBuckets": dict(sorted(context_packet_buckets.items())),
        "sourceGroundedArtifactCount": len(source_grounded),
        "nonSourceGroundedArtifactCount": max(0, len(artifacts) - len(source_grounded)),
        "retrievalValidArtifactCount": len(retrieval_valid),
        "nonRetrievalValidArtifactCount": max(0, len(artifacts) - len(retrieval_valid)),
        "credibleImprovementCount": len(credible_improvements),
        "noisyImprovementCount": len(noisy_improvements),
        "redFlags": {
            "fallbackWithSelectedEvidence": _case_list(fallback_with_selected),
            "directWriterFallback": _case_list(direct_writer_fallback),
            "zeroSelectedEvidence": _case_list(zero_selected),
            "noCitedClaims": _case_list(no_cited_claims),
            "missingContextPacketProvenance": _case_list(missing_context_packet_provenance),
            "selectedEvidenceWithoutCitations": _case_list(selected_without_citations),
            "improvementWithoutCompletedSelector": _case_list(improvement_without_completed),
            "regressionWithoutCompletedSelector": _case_list(regression_without_completed),
        },
    }


def load_artifacts(results_dir: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for path in sorted(results_dir.glob("*.json")):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(item, dict):
            item.setdefault("_artifactPathStem", path.stem)
            artifacts.append(item)
    return artifacts


def _artifact_id(item: dict[str, Any]) -> str:
    return str(item.get("caseId") or item.get("id") or item.get("_artifactPathStem") or "")


def _selector_status(item: dict[str, Any]) -> str:
    beta6 = item.get("beta6") if isinstance(item.get("beta6"), dict) else {}
    selector = item.get("selector") if isinstance(item.get("selector"), dict) else {}
    return str(item.get("selectorStatus") or beta6.get("selectorStatus") or selector.get("status") or "")


def _writer_mode(item: dict[str, Any]) -> str:
    beta6 = item.get("beta6") if isinstance(item.get("beta6"), dict) else {}
    writer = item.get("writer") if isinstance(item.get("writer"), dict) else {}
    return str(item.get("writerMode") or beta6.get("writerMode") or writer.get("mode") or "")


def _selection_source(item: dict[str, Any]) -> str:
    beta6 = item.get("beta6") if isinstance(item.get("beta6"), dict) else {}
    selector = item.get("selector") if isinstance(item.get("selector"), dict) else {}
    return str(item.get("selectionSource") or beta6.get("selectionSource") or selector.get("selectionSource") or "")


def _direct_writer_fallback(item: dict[str, Any]) -> bool:
    writer_mode = _writer_mode(item)
    selection_source = _selection_source(item)
    return (
        "_direct_after_" in writer_mode
        or writer_mode.startswith("direct_after_")
        or selection_source.startswith("direct_after_")
    )


def _is_source_grounded(item: dict[str, Any]) -> bool:
    return (
        _selector_status(item) == "completed"
        and not _direct_writer_fallback(item)
        and _selected_count(item) > 0
        and _cited_count(item) > 0
    )


def _is_retrieval_valid(item: dict[str, Any]) -> bool:
    return _is_source_grounded(item) and _context_packet_count(item) > 0


def _delta(item: dict[str, Any]) -> str:
    comparison = item.get("comparison") if isinstance(item.get("comparison"), dict) else {}
    return str(item.get("delta") or comparison.get("delta") or "")


def _selected_count(item: dict[str, Any]) -> int:
    beta6 = item.get("beta6") if isinstance(item.get("beta6"), dict) else {}
    raw = item.get("selectedCount", beta6.get("selectedCount"))
    if raw is None:
        for key in ("selectedEvidence", "sources", "retrievedCases", "beta6SelectedRecords"):
            value = item.get(key)
            if isinstance(value, list):
                return len(value)
        return 0
    return _safe_int(raw)


def _cited_count(item: dict[str, Any]) -> int:
    raw = item.get("citedClaimCount")
    if raw is None:
        value = item.get("citedClaimCards")
        if isinstance(value, list):
            return len(value)
        return 0
    return _safe_int(raw)


def _context_packet_count(item: dict[str, Any]) -> int:
    beta6 = item.get("beta6") if isinstance(item.get("beta6"), dict) else {}
    raw = item.get("contextPacketCount", beta6.get("contextPacketCount"))
    if raw is not None:
        return _safe_int(raw)
    for key in ("contextPacketIds", "contextPackets"):
        value = item.get(key)
        if isinstance(value, list):
            return len(value)
    return 0


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _selected_count_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value <= 3:
        return "1-3"
    if value <= 10:
        return "4-10"
    return "11+"


def _case_list(case_ids: list[str]) -> dict[str, Any]:
    return {"count": len(case_ids), "caseIds": sorted(case_ids)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit benchmark artifacts for noisy source-grounding lift.")
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    report = audit_results_dir(args.results_dir)
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
