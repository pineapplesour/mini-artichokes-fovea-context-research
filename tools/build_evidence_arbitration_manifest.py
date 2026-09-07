#!/usr/bin/env python3
"""Build a gold-free Direct-vs-evidence disagreement manifest from arm artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


def build_manifest(
    *,
    direct_results_dir: Path,
    universal_results_dir: Path,
    benchmark_id: str,
) -> dict[str, Any]:
    direct = _load_results(direct_results_dir)
    universal = _load_results(universal_results_dir)
    if set(direct) != set(universal):
        raise ValueError("Direct and Universal result IDs do not match")
    cases: list[dict[str, Any]] = []
    for case_id in sorted(direct):
        prior = direct[case_id]
        augmented = universal[case_id]
        direct_prediction = str(prior.get("prediction") or "").strip()
        universal_prediction = str(augmented.get("prediction") or "").strip()
        if not direct_prediction or not universal_prediction or direct_prediction == universal_prediction:
            continue
        query = str(augmented.get("query") or prior.get("query") or "").strip()
        evidence = [
            _public_evidence_packet(item)
            for item in augmented.get("selectedEvidence") or []
            if isinstance(item, dict)
        ]
        cases.append(
            {
                "id": case_id,
                "query": query,
                "directPrediction": direct_prediction,
                "universalPrediction": universal_prediction,
                "directAnswer": str(prior.get("answer") or prior.get("answerMarkdown") or "")[:2000],
                "universalAnswer": str(augmented.get("answer") or augmented.get("answerMarkdown") or "")[:2000],
                "evidence": evidence,
                "candidateCount": int(augmented.get("candidateCount") or 0),
                "selectedCount": len(evidence),
            }
        )
    return {
        "schemaVersion": 1,
        "benchmarkId": str(benchmark_id),
        "taskType": "evidence_intervention_arbitration",
        "goldAvailableToRunner": False,
        "source": {
            "directResultsDir": str(Path(direct_results_dir).resolve()),
            "universalResultsDir": str(Path(universal_results_dir).resolve()),
            "directPortableDigest": _portable_digest(Path(direct_results_dir)),
            "universalPortableDigest": _portable_digest(Path(universal_results_dir)),
        },
        "cases": cases,
    }


def _public_evidence_packet(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": str(item.get("label") or ""),
        "sourceId": str(item.get("sourceId") or ""),
        "title": str(item.get("title") or "")[:500],
        "citation": str(item.get("citation") or "")[:500],
        "exactQuote": str(item.get("exactQuote") or "")[:2400],
        "selectionReason": str(item.get("selectionReason") or "")[:800],
    }


def _load_results(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for artifact in sorted(Path(path).glob("*.json"), key=lambda item: item.name):
        value = json.loads(artifact.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            continue
        case_id = str(value.get("caseId") or value.get("id") or artifact.stem).strip()
        if case_id in records:
            raise ValueError(f"duplicate case ID: {case_id}")
        records[case_id] = value
    return records


def _portable_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for artifact in sorted(Path(path).glob("*.json"), key=lambda item: item.name):
        digest.update(artifact.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(artifact.read_bytes()).hexdigest().encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--direct-results-dir", type=Path, required=True)
    parser.add_argument("--universal-results-dir", type=Path, required=True)
    parser.add_argument("--benchmark-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_manifest(
        direct_results_dir=args.direct_results_dir,
        universal_results_dir=args.universal_results_dir,
        benchmark_id=args.benchmark_id,
    )
    _atomic_write(args.output, manifest)
    print(json.dumps({"output": str(args.output), "caseCount": len(manifest["cases"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
