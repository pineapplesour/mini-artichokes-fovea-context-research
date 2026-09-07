#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared_platform.products import ProductProfile  # noqa: E402
from shared_platform.search import SearchResult, search_documents  # noqa: E402


DEFAULT_DB = Path("/var/lib/universal-artichoke/lawkey/precedents.sqlite3")
DEFAULT_BENCH = ROOT / "benchmarks" / "lawkey_hard_retrieval" / "yangyang-complainant-age.json"


@dataclass
class QueryVerdict:
    query: str
    ok: bool
    primary_rank: int | None
    primary_window: int
    candidate_limit: int
    answer_span_found_in_primary: bool
    search_metadata_leaks: list[str]
    related_ranks: dict[str, int | None]
    failures: list[str]


def normalize_id(value: str) -> str:
    return re.sub(r"[\s()]+", "", str(value or "")).lower()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def result_to_dict(result: SearchResult | dict[str, Any]) -> dict[str, Any]:
    if isinstance(result, SearchResult):
        return asdict(result)
    return dict(result)


def source_file_name(source_path: str) -> str:
    normalized = str(source_path or "").replace("\\", "/").rstrip("/")
    return normalized.rsplit("/", 1)[-1]


def matches_target(result: dict[str, Any], target: dict[str, Any]) -> bool:
    case_number = normalize_id(str(result.get("citation") or result.get("case_number") or ""))
    target_case = normalize_id(str(target.get("caseNumber") or ""))
    if target_case and case_number != target_case:
        return False

    expected_file = str(target.get("fileName") or "").strip()
    source_path = str(result.get("source_path") or "")
    if expected_file and source_path and source_file_name(source_path) == expected_file:
        return True

    court = normalize_id(str(result.get("authority_body") or result.get("court") or ""))
    target_court = normalize_id(str(target.get("court") or ""))
    return bool(target_court and target_court in court)


def find_rank(results: list[dict[str, Any]], target: dict[str, Any]) -> int | None:
    for index, result in enumerate(results, start=1):
        if matches_target(result, target):
            return index
    return None


def find_result(results: list[dict[str, Any]], target: dict[str, Any]) -> dict[str, Any] | None:
    for result in results:
        if matches_target(result, target):
            return result
    return None


def run_lawkey_search(db_path: Path, query: str, *, limit: int, candidate_multiplier: int) -> list[dict[str, Any]]:
    profile = ProductProfile(
        key="lawkey",
        name="Lawkey",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko",),
        default_language="ko",
        theme="lawkey",
        safety_notice="",
    )
    rows = search_documents(
        profile,
        query,
        limit=limit,
        language="ko",
        max_results=limit,
        candidate_multiplier=candidate_multiplier,
    )
    return [result_to_dict(row) for row in rows]


def load_results_json(path: Path) -> dict[str, list[dict[str, Any]]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return {"": [result_to_dict(row) for row in raw]}
    if isinstance(raw, dict) and "queries" in raw:
        return {
            str(item.get("query") or ""): [result_to_dict(row) for row in item.get("results", [])]
            for item in raw.get("queries", [])
        }
    if isinstance(raw, dict):
        return {str(key): [result_to_dict(row) for row in value] for key, value in raw.items()}
    raise ValueError(f"unsupported results JSON shape: {path}")


def lookup_target_by_fts(db_path: Path, target: dict[str, Any]) -> dict[str, Any] | None:
    case_number = str(target.get("caseNumber") or "").strip()
    if not case_number or not db_path.exists():
        return None
    query = f'"{case_number}"'
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
              p.canonical_id,
              p.source_path,
              p.title,
              p.case_number,
              p.court,
              p.decision_date,
              p.case_name,
              p.case_type,
              p.full_text
            FROM precedents_fts
            JOIN precedents p ON p.canonical_id = precedents_fts.canonical_id
            WHERE precedents_fts MATCH ?
            LIMIT 20
            """,
            (query,),
        ).fetchall()
    except sqlite3.Error:
        return None
    finally:
        conn.close()
    for row in rows:
        candidate = {
            "canonical_id": row["canonical_id"],
            "source_path": row["source_path"],
            "title": row["title"],
            "citation": row["case_number"],
            "authority_body": row["court"],
            "source_date": row["decision_date"],
            "case_name": row["case_name"],
            "case_type": row["case_type"],
            "full_text": row["full_text"],
        }
        if matches_target(candidate, target):
            return candidate
    return None


def validate_query(case: dict[str, Any], query: str, results: list[dict[str, Any]], *, db_path: Path | None = None) -> QueryVerdict:
    rules = case.get("rankRules", {})
    primary = case["primaryTarget"]
    candidate_limit = int(rules.get("candidateLimit") or len(results) or 50)
    primary_window = int(rules.get("primaryMustAppearWithin") or 5)
    required_text = str(primary.get("requiredAnswerText") or "")

    failures: list[str] = []
    primary_rank = find_rank(results, primary)
    if primary_rank is None:
        failures.append(f"primary target not returned in top {min(candidate_limit, len(results))} candidates")
    elif primary_rank > primary_window:
        failures.append(f"primary target rank {primary_rank} exceeds allowed window {primary_window}")

    primary_result = find_result(results, primary)
    if primary_result is None and db_path is not None:
        primary_result = lookup_target_by_fts(db_path, primary)

    answer_span_found = bool(primary_result and required_text and required_text in str(primary_result.get("full_text") or ""))
    if rules.get("requiredAnswerMustAppearInPrimary", True) and not answer_span_found:
        failures.append(f"required answer span not found in primary full_text: {required_text}")

    metadata_leaks: list[str] = []
    if primary_result is not None and rules.get("forbidSearchMetadataLeakTerms"):
        metadata_text = normalize_text(
            " ".join(str(primary_result.get(field) or "") for field in ("title", "case_name"))
        )
        full_text = normalize_text(str(primary_result.get("full_text") or ""))
        for term in case.get("forbiddenSearchMetadataTerms", []):
            normalized_term = normalize_text(str(term or ""))
            if not normalized_term:
                continue
            if normalized_term in metadata_text and normalized_term not in full_text:
                metadata_leaks.append(str(term))
        if metadata_leaks:
            failures.append(
                "search metadata contains benchmark alias terms not present in primary full_text: "
                + ", ".join(metadata_leaks)
            )

    related_ranks: dict[str, int | None] = {}
    for related in case.get("relatedTargets", []):
        label = str(related.get("caseNumber") or related.get("fileName") or "related")
        related_ranks[label] = find_rank(results, related)

    return QueryVerdict(
        query=query,
        ok=not failures,
        primary_rank=primary_rank,
        primary_window=primary_window,
        candidate_limit=candidate_limit,
        answer_span_found_in_primary=answer_span_found,
        search_metadata_leaks=metadata_leaks,
        related_ranks=related_ranks,
        failures=failures,
    )


def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    bench = json.loads(args.bench.read_text(encoding="utf-8"))
    db_path = args.db
    results_by_query = load_results_json(args.results_json) if args.results_json else {}

    case_payloads: list[dict[str, Any]] = []
    failures: list[str] = []
    for case in bench.get("cases", []):
        query_payloads: list[dict[str, Any]] = []
        for query in case.get("queries", []):
            rules = case.get("rankRules", {})
            limit = int(args.limit or rules.get("candidateLimit") or 50)
            if args.results_json:
                results = results_by_query.get(query) or results_by_query.get("") or []
            else:
                results = run_lawkey_search(db_path, query, limit=limit, candidate_multiplier=args.candidate_multiplier)
            verdict = validate_query(case, query, results, db_path=db_path if not args.results_json else None)
            query_payload = asdict(verdict)
            query_payload["topResults"] = [
                {
                    "rank": index,
                    "canonical_id": result.get("canonical_id"),
                    "title": result.get("title"),
                    "case_number": result.get("citation") or result.get("case_number"),
                    "court": result.get("authority_body") or result.get("court"),
                    "source_path": result.get("source_path"),
                }
                for index, result in enumerate(results[: min(10, len(results))], start=1)
            ]
            query_payloads.append(query_payload)
            failures.extend(f"{case.get('id')} / {query}: {failure}" for failure in verdict.failures)
        case_payloads.append({"id": case.get("id"), "queries": query_payloads})

    return {
        "ok": not failures,
        "benchmarkVersion": bench.get("benchmarkVersion"),
        "bench": str(args.bench),
        "db": str(db_path) if db_path else "",
        "cases": case_payloads,
        "failures": failures,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Lawkey hard-retrieval benchmark cases.")
    parser.add_argument("--bench", type=Path, default=DEFAULT_BENCH)
    parser.add_argument("--db", type=Path, default=Path(os.getenv("RELIGION_LAWKEY_DB_PATH") or os.getenv("LAWKEY_PRECEDENT_DB_PATH") or DEFAULT_DB))
    parser.add_argument("--results-json", type=Path, help="Validate precomputed search results instead of querying a DB.")
    parser.add_argument("--limit", type=int, help="Override benchmark candidateLimit.")
    parser.add_argument("--candidate-multiplier", type=int, default=1)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.bench.exists():
        raise SystemExit(f"benchmark file not found: {args.bench}")
    if not args.results_json and not args.db.exists():
        raise SystemExit(f"DB not found: {args.db}")
    payload = run_benchmark(args)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for failure in payload["failures"]:
            print(f"FAIL {failure}")
        print("PASS" if payload["ok"] else "FAIL")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
