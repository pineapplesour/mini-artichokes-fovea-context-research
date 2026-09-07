#!/usr/bin/env python3
"""Finalize a balanced legal reserve with an audit-calibrated holding parser."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


APPELLATE = re.compile(
    r"(?:제1심|원심)판결(?:을| 중)[\s\S]{0,100}?(?:변경|취소)|항소|상고|파기|환송"
)
POSITIVE_DISPOSITION = re.compile(
    r"(?:"
    r"(?:강제|가압류)집행[\s\S]{0,140}?불허|"
    r"배당표[\s\S]{0,220}?(?:변경|경정)|"
    r"하여서는\s*아니\s*된|"
    r"(?:폐기|삭제|제거|제공|인도|지급)하라|"
    r"하도록\s*하여야\s*한다|"
    r"(?:계약|처분|결의)[\s\S]{0,100}?취소|"
    r"(?:지위|통행권|채무|의무|결의|처분)[\s\S]{0,100}?"
    r"(?:있음을|없음을|무효임을|존재하지\s*아니함을)\s*확인|"
    r"말소(?:등기)?절차[\s\S]{0,50}?이행하라"
    r")"
)


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def refined_label(row: dict[str, Any]) -> str | None:
    holding = str(row.get("holding") or "")
    if APPELLATE.search(holding):
        return None
    provisional = row.get("label")
    if provisional == "인용됨" or POSITIVE_DISPOSITION.search(holding):
        return "인용됨"
    if provisional == "기각":
        return "기각"
    raise ValueError(f"unsupported provisional label: {row.get('caseId')} {provisional!r}")


def load_audits(root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    per_auditor: dict[str, int] = {}
    for auditor in ("auditor_a", "auditor_b"):
        count = 0
        for path in sorted((root / auditor).glob("shard_*/output/judgments.jsonl")):
            for row in load_jsonl(path):
                by_id[row["id"]].append(row)
                count += 1
        per_auditor[auditor] = count
    resolved: dict[str, dict[str, Any]] = {}
    common = 0
    for case_id, rows in by_id.items():
        labels = {row["label"] for row in rows}
        eligibility = {row["eligible"] for row in rows}
        if len(rows) > 1:
            common += 1
        if len(labels) != 1 or len(eligibility) != 1:
            raise ValueError(f"audit disagreement: {case_id}")
        resolved[case_id] = {"label": next(iter(labels)), "eligible": next(iter(eligibility))}
    return resolved, {**per_auditor, "union": len(resolved), "common": common}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite nonempty output: {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    private_path = args.candidate_dir / "candidates.private.jsonl"
    public_path = args.candidate_dir / "candidates.public.jsonl"
    private_rows = load_jsonl(private_path)
    public_rows = load_jsonl(public_path)
    public_by_id = {row["id"]: row for row in public_rows}
    if len(private_rows) != len(public_rows) or {row["caseId"] for row in private_rows} != set(public_by_id):
        raise ValueError("candidate public/private IDs do not match")

    audits, audit_counts = load_audits(args.audit_dir)
    if audit_counts != {"auditor_a": 280, "auditor_b": 240, "union": 393, "common": 127}:
        raise ValueError(f"unexpected audit coverage: {audit_counts}")
    excluded: list[str] = []
    eligible: list[dict[str, Any]] = []
    for row in private_rows:
        case_id = row["caseId"]
        label = refined_label(row)
        audit = audits.get(case_id)
        if audit is not None:
            if audit["eligible"] is False or audit["label"] == "AMBIGUOUS":
                if label is not None:
                    raise ValueError(f"parser retained audit-excluded row: {case_id}")
            elif audit != {"label": label, "eligible": True}:
                raise ValueError(f"parser disagrees with accepted audit: {case_id}")
        if label is None:
            excluded.append(case_id)
            continue
        normalized = dict(row)
        normalized["label"] = label
        normalized["labelProtocol"] = "audit-calibrated-holding-parser-v2"
        eligible.append(normalized)

    cells: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in eligible:
        cells[(row["domain"], row["label"])].append(row)
    for rows in cells.values():
        rows.sort(key=lambda row: (row["selectionRankSHA256"], row["caseId"]))
    civil_quota = min(len(cells[("civil", "인용됨")]), len(cells[("civil", "기각")]))
    tax_quota = min(len(cells[("tax", "인용됨")]), len(cells[("tax", "기각")]))
    selected = (
        cells[("civil", "인용됨")][:civil_quota]
        + cells[("civil", "기각")][:civil_quota]
        + cells[("tax", "인용됨")][:tax_quota]
        + cells[("tax", "기각")][:tax_quota]
    )
    selected.sort(key=lambda row: (row["selectionRankSHA256"], row["caseId"]))
    selected_ids = [row["caseId"] for row in selected]
    public_out = [public_by_id[case_id] for case_id in selected_ids]
    private_out = [
        {
            "caseId": row["caseId"],
            "label": row["label"],
            "domain": row["domain"],
            "caseRef": row["caseRef"],
            "canonicalId": row["canonicalId"],
            "decisionDate": row["decisionDate"],
            "holding": row["holding"],
            "labelProtocol": row["labelProtocol"],
        }
        for row in selected
    ]
    public_out_path = args.output_dir / "confirmation.public.jsonl"
    private_out_path = args.output_dir / "confirmation.private.jsonl"
    write_jsonl(public_out_path, public_out)
    write_jsonl(private_out_path, private_out)
    available_counts = Counter((row["domain"], row["label"]) for row in eligible)
    selected_counts = Counter((row["domain"], row["label"]) for row in selected)
    manifest = {
        "protocol": "mini_artichokes_balanced_legal_confirmation_v1",
        "labelProtocol": "audit-calibrated-holding-parser-v2",
        "source": {
            "publicSha256": sha256_file(public_path),
            "privateSha256": sha256_file(private_path),
            "rows": len(private_rows),
        },
        "auditValidation": {
            **audit_counts,
            "acceptedLabelsMatched": sum(
                audit["eligible"] is True and audit["label"] in {"인용됨", "기각"}
                for audit in audits.values()
            ),
            "excludedAmbiguousOrIneligible": sum(
                audit["eligible"] is False or audit["label"] == "AMBIGUOUS"
                for audit in audits.values()
            ),
        },
        "availableCounts": {f"{domain}:{label}": count for (domain, label), count in sorted(available_counts.items())},
        "selectedCounts": {f"{domain}:{label}": count for (domain, label), count in sorted(selected_counts.items())},
        "quotas": {"civilPerLabel": civil_quota, "taxPerLabel": tax_quota},
        "rows": len(selected),
        "excludedIds": excluded,
        "artifacts": {
            "public": {"path": str(public_out_path.resolve()), "sha256": sha256_file(public_out_path)},
            "private": {"path": str(private_out_path.resolve()), "sha256": sha256_file(private_out_path)},
        },
    }
    manifest_path = args.output_dir / "confirmation.manifest.json"
    manifest_path.write_bytes(canonical_bytes(manifest))
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
