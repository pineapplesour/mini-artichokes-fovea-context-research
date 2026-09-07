#!/usr/bin/env python3
"""Re-render an exposed outcome benchmark with frozen evidence-clause IDs.

This is a development-only adapter.  It reads public prompts, never opens a
private label file, and preserves source IDs.  Its output lets the structured
overlap rule be tuned on already-exposed cases before a fresh reserve is ever
mounted to a solver.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import build_disjoint_outcome_reserve as reserve


PROTOCOL = "numbered-outcome-development-public-v1"
PUBLIC_KEYS = {
    "id",
    "suite",
    "benchmarkId",
    "responseFormat",
    "language",
    "prompt",
}


class DevelopmentBuildError(RuntimeError):
    pass


def extract_civil_content(prompt: str) -> tuple[str, str]:
    """Extract the outer claim/facts blocks while retaining nested headings."""

    claim_head = reserve.CLAIM_HEADING_RE.search(prompt)
    if not claim_head:
        raise DevelopmentBuildError("source prompt has no civil claim heading")
    facts_head = reserve.FACTS_HEADING_RE.search(prompt, claim_head.end())
    if not facts_head:
        raise DevelopmentBuildError("source prompt has no facts heading after the claim")
    claim = reserve.normalize_text(
        reserve._strip_numbered_clause_ids(prompt[claim_head.end() : facts_head.start()])
    )
    tail = reserve.CONTENT_TAIL_RE.search(prompt, facts_head.end())
    facts_stop = tail.start() if tail else len(prompt)
    facts = reserve.normalize_text(
        reserve._strip_numbered_clause_ids(prompt[facts_head.end() : facts_stop])
    )
    if not claim or not facts:
        raise DevelopmentBuildError("source civil claim or facts block is empty")
    return claim, facts


def build_rows(source_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows, source_hash, source_bytes = reserve.load_jsonl_strict(source_path)
    output: list[dict[str, Any]] = []
    bindings: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, row in enumerate(source_rows):
        case_id = row.get("id")
        prompt = row.get("prompt")
        if not isinstance(case_id, str) or not case_id.strip():
            raise DevelopmentBuildError(f"invalid source ID at row {index}")
        if case_id in seen:
            raise DevelopmentBuildError(f"duplicate source ID: {case_id}")
        seen.add(case_id)
        if not isinstance(prompt, str) or not prompt.strip():
            raise DevelopmentBuildError(f"empty source prompt: {case_id}")
        try:
            claim, facts = extract_civil_content(prompt)
        except DevelopmentBuildError as error:
            raise DevelopmentBuildError(
                f"development adapter requires civil claim and facts: {case_id}"
            ) from error
        claim_clauses = reserve.segment_evidence(claim, prefix="C")
        facts_clauses = reserve.segment_evidence(facts, prefix="F")
        rendered = reserve.render_prompt(
            domain="civil",
            claim_clauses=claim_clauses,
            facts_clauses=facts_clauses,
        )
        rendered_fingerprints = reserve.public_content_fingerprints(rendered)
        expected_fingerprints = {
            "claimContentSHA256": reserve.content_sha256(claim),
            "factsContentSHA256": reserve.content_sha256(facts),
            "claimFactsContentSHA256": reserve.content_sha256(f"{claim}\n{facts}"),
        }
        if expected_fingerprints != rendered_fingerprints:
            raise DevelopmentBuildError(
                f"numbering changed wrapper-independent content: {case_id}"
            )
        public = {
            "id": case_id,
            "suite": "exam",
            "benchmarkId": "outcome.first_instance_prediction.v1",
            "responseFormat": "outcome_prediction",
            "language": "ko",
            "prompt": rendered,
        }
        if set(public) != PUBLIC_KEYS:
            raise AssertionError("development public schema drifted")
        output.append(public)
        bindings.append(
            {
                "id": case_id,
                "sourceRowSHA256": reserve.sha256_bytes(
                    reserve.canonical_json_bytes(row)
                ),
                "publicRowSHA256": reserve.sha256_bytes(
                    reserve.canonical_json_bytes(public)
                ),
                "sourcePromptSHA256": reserve.normalized_prompt_sha256(prompt),
                "numberedPromptSHA256": reserve.normalized_prompt_sha256(rendered),
            }
        )
    metadata: dict[str, Any] = {
        "protocol": PROTOCOL,
        "status": "DEVELOPMENT_ONLY_ALREADY_EXPOSED_NO_GOLD_READ",
        "source": {
            "path": str(source_path.resolve()),
            "rows": len(source_rows),
            "bytes": source_bytes,
            "sha256": source_hash,
        },
        "implementation": {
            "adapterPath": str(Path(__file__).resolve()),
            "adapterSHA256": reserve.sha256_file(Path(__file__)),
            "reserveBuilderPath": str(Path(reserve.__file__).resolve()),
            "reserveBuilderSHA256": reserve.sha256_file(Path(reserve.__file__)),
        },
        "evidenceSegmentation": {
            "version": reserve.EVIDENCE_SEGMENTATION_VERSION,
            "specification": reserve.EVIDENCE_SEGMENTATION_SPEC,
            "specificationSHA256": reserve.sha256_bytes(
                reserve.canonical_json_bytes(reserve.EVIDENCE_SEGMENTATION_SPEC)
            ),
        },
        "rows": len(output),
        "orderedRows": bindings,
        "goldAccess": False,
    }
    return output, metadata


def write_build(
    rows: list[dict[str, Any]], metadata: dict[str, Any], *, public_out: Path,
    manifest_out: Path
) -> dict[str, Any]:
    targets = [public_out.resolve(), manifest_out.resolve()]
    if len(set(targets)) != 2:
        raise DevelopmentBuildError("public and manifest outputs must be distinct")
    existing = [path for path in targets if path.exists()]
    if existing:
        raise DevelopmentBuildError(
            "refusing to overwrite existing output(s): "
            + ", ".join(str(path) for path in existing)
        )
    public_payload = reserve.serialize_jsonl(rows)
    manifest = dict(metadata)
    manifest["artifact"] = {
        "path": str(public_out.resolve()),
        "rows": len(rows),
        "bytes": len(public_payload),
        "sha256": reserve.sha256_bytes(public_payload),
    }
    manifest["selfHash"] = reserve.manifest_self_hash(manifest)
    manifest_payload = (
        json.dumps(
            manifest,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )
    reserve._write_exclusive(public_out, public_payload)
    reserve._write_exclusive(manifest_out, manifest_payload)
    if reserve.sha256_file(public_out) != manifest["artifact"]["sha256"]:
        raise DevelopmentBuildError("public artifact failed post-write hash check")
    loaded = json.loads(manifest_out.read_text(encoding="utf-8"))
    if not reserve.verify_manifest_self_hash(loaded):
        raise DevelopmentBuildError("development manifest self-hash failed")
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-public", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    parser.add_argument("--manifest-out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        rows, metadata = build_rows(args.source_public)
        manifest = write_build(
            rows,
            metadata,
            public_out=args.public_out,
            manifest_out=args.manifest_out,
        )
    except (OSError, json.JSONDecodeError, reserve.ReserveBuildError, DevelopmentBuildError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": "BUILT_DEVELOPMENT_ONLY",
                "rows": len(rows),
                "publicSHA256": manifest["artifact"]["sha256"],
                "manifestSelfHash": manifest["selfHash"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
