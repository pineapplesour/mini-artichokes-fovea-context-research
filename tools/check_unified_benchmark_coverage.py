#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared_platform.domain_adapters import get_domain_adapter


CORPUS_ANSWER_TASK_TYPES = {"mcq", "short_answer"}


def check_unified_benchmark_coverage(manifest_path: Path, db_path: Path, *, min_rows: int = 1000) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("taskType") in CORPUS_ANSWER_TASK_TYPES:
        return check_mcq_corpus_readiness(manifest_path, db_path, min_rows=min_rows)
    return check_legal_private_manifest_coverage(manifest_path, db_path)


def check_mcq_corpus_readiness(public_path: Path, db_path: Path, *, min_rows: int = 1000) -> dict[str, Any]:
    manifest = json.loads(public_path.read_text(encoding="utf-8"))
    summary: dict[str, Any] = {
        "benchmarkId": manifest.get("benchmarkId", ""),
        "taskType": manifest.get("taskType", "mcq"),
        "product": manifest.get("product", ""),
        "dbPath": str(db_path),
        "dbExists": db_path.exists(),
        "caseCount": len([case for case in manifest.get("cases", []) if isinstance(case, dict)]),
        "corpusTable": "",
        "corpusRows": 0,
        "corpusRowsIsLowerBound": False,
        "minRows": int(min_rows),
        "readyForRetrievalBenchmark": False,
        "error": "",
    }
    if not db_path.exists():
        summary["error"] = f"database not found: {db_path}"
        return summary
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            table, rows, lower_bound = _largest_existing_corpus_table(
                conn,
                ("passages", "precedents", "documents", "search_documents"),
                min_rows=int(min_rows),
            )
            summary["corpusTable"] = table
            if not table:
                summary["error"] = "no supported corpus table found"
                return summary
            summary["corpusRows"] = rows
            summary["corpusRowsIsLowerBound"] = lower_bound
            if rows < int(min_rows):
                summary["error"] = f"corpus row count below minimum: {rows} < {int(min_rows)}"
                return summary
            topic_probe = _mcq_topic_probe(conn, manifest, table)
            summary["topicProbe"] = topic_probe
            if _mcq_topic_probe_low_coverage(topic_probe):
                summary["error"] = "topic probe found too few benchmark option/source terms in corpus"
                return summary
            summary["readyForRetrievalBenchmark"] = True
    except Exception as exc:
        summary["error"] = str(exc)
    return summary


def check_legal_private_manifest_coverage(private_path: Path, db_path: Path) -> dict[str, Any]:
    manifest = json.loads(private_path.read_text(encoding="utf-8"))
    summary: dict[str, Any] = {
        "benchmarkId": manifest.get("benchmarkId", ""),
        "taskType": "legal_retrieval_answer",
        "dbPath": str(db_path),
        "dbExists": db_path.exists(),
        "totalTargets": 0,
        "presentTargets": 0,
        "requiredAnswerTextTargets": 0,
        "requiredAnswerTextPresent": 0,
        "targets": [],
        "error": "",
    }
    targets = _legal_targets(manifest)
    summary["totalTargets"] = len(targets)
    if not db_path.exists():
        summary["error"] = f"database not found: {db_path}"
        return summary
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            columns = _precedents_columns(conn)
            for target in targets:
                result = _check_target(conn, columns, target)
                summary["targets"].append(result)
                if result["present"]:
                    summary["presentTargets"] += 1
                if result.get("requiredAnswerText"):
                    summary["requiredAnswerTextTargets"] += 1
                    if result.get("requiredAnswerTextPresent"):
                        summary["requiredAnswerTextPresent"] += 1
    except Exception as exc:
        summary["error"] = str(exc)
    return summary


def _legal_targets(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    for grader in manifest.get("graders", []) or []:
        if not isinstance(grader, dict):
            continue
        grader_id = str(grader.get("graderId") or "")
        for kind in ("primaryTargets", "diagnosticTargets"):
            for target in grader.get(kind, []) or []:
                if not isinstance(target, dict):
                    continue
                item = dict(target)
                item["graderId"] = grader_id
                item["targetKind"] = kind
                targets.append(item)
    return targets


def _precedents_columns(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("PRAGMA table_info(precedents)").fetchall()
    return {str(row["name"]) for row in rows}


def _largest_existing_corpus_table(
    conn: sqlite3.Connection,
    candidates: tuple[str, ...],
    *,
    min_rows: int,
) -> tuple[str, int, bool]:
    names = {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')").fetchall()
    }
    best_table = ""
    best_rows = -1
    best_lower_bound = False
    count_bound = max(1000, int(min_rows), 1)
    for candidate in candidates:
        if candidate not in names:
            continue
        rows, lower_bound = _bounded_table_count(conn, candidate, limit=count_bound)
        if rows > best_rows:
            best_table = candidate
            best_rows = rows
            best_lower_bound = lower_bound
    if not best_table:
        return "", 0, False
    return best_table, best_rows, best_lower_bound


def _bounded_table_count(conn: sqlite3.Connection, table: str, *, limit: int) -> tuple[int, bool]:
    bound = max(1, int(limit))
    rows = int(conn.execute(f"SELECT COUNT(*) FROM (SELECT 1 FROM {table} LIMIT ?)", (bound,)).fetchone()[0])
    return rows, rows >= bound


def _mcq_topic_probe(conn: sqlite3.Connection, manifest: dict[str, Any], table: str) -> dict[str, Any]:
    terms = _mcq_topic_probe_terms(manifest)
    matched: list[str] = []
    unmatched: list[str] = []
    for term in terms:
        if _corpus_term_present(conn, table, term):
            matched.append(term)
        else:
            unmatched.append(term)
    return {
        "sampledCaseCount": min(len([case for case in manifest.get("cases", []) if isinstance(case, dict)]), 30),
        "termCount": len(terms),
        "matchedTermCount": len(matched),
        "matchRatio": round((len(matched) / len(terms)) if terms else 0.0, 4),
        "lowCoverageThreshold": 0.05,
        "matchedTerms": matched[:20],
        "unmatchedTerms": unmatched[:20],
        "truncated": len(terms) > 64,
    }


def _mcq_topic_probe_low_coverage(topic_probe: dict[str, Any]) -> bool:
    term_count = int(topic_probe.get("termCount") or 0)
    if term_count <= 0:
        return False
    matched_count = int(topic_probe.get("matchedTermCount") or 0)
    if matched_count <= 0:
        return True
    if term_count < 10:
        return False
    try:
        ratio = float(topic_probe.get("matchRatio") or 0.0)
    except (TypeError, ValueError):
        ratio = 0.0
    return ratio < float(topic_probe.get("lowCoverageThreshold") or 0.05)


def _mcq_topic_probe_terms(manifest: dict[str, Any]) -> list[str]:
    product = str(manifest.get("product") or "")
    adapter = get_domain_adapter(product)
    terms: list[str] = []
    for case in [case for case in manifest.get("cases", []) if isinstance(case, dict)][:30]:
        prompt = str(case.get("prompt") or "")
        for term in adapter.multiple_choice_option_terms(prompt):
            cleaned = _clean_probe_term(term)
            if _is_probe_term(cleaned) and cleaned not in terms:
                terms.append(cleaned)
            if len(terms) >= 64:
                return terms
    return terms


def _clean_probe_term(term: str) -> str:
    return re.sub(r"\s+", " ", str(term or "").strip())


def _is_probe_term(term: str) -> bool:
    if len(term) < 4:
        return False
    if len(term) > 80:
        return False
    if len(re.findall(r"[\w\u0600-\u06ff]+", term, re.UNICODE)) > 6:
        return False
    if not re.search(r"[A-Za-z]", term):
        return False
    return not re.fullmatch(r"[A-Da-d]|\d{1,2}", term)


def _corpus_term_present(conn: sqlite3.Connection, table: str, term: str) -> bool:
    fts_tables = {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')").fetchall()
        if str(row[0]).endswith("_fts")
    }
    if "precedents_fts" in fts_tables:
        fts = _fts_probe_query(term)
        if fts:
            try:
                return (
                    conn.execute("SELECT 1 FROM precedents_fts WHERE precedents_fts MATCH ? LIMIT 1", (fts,)).fetchone()
                    is not None
                )
            except sqlite3.OperationalError:
                pass
    columns = _table_text_columns(conn, table)
    if not columns:
        return False
    where = " OR ".join(f"{column} LIKE ?" for column in columns)
    like = f"%{term}%"
    try:
        return conn.execute(f"SELECT 1 FROM {table} WHERE {where} LIMIT 1", [like] * len(columns)).fetchone() is not None
    except sqlite3.OperationalError:
        return False


def _fts_probe_query(term: str) -> str:
    tokens = [token for token in re.findall(r"[\w\u0600-\u06ff]+", str(term or ""), re.UNICODE) if len(token) >= 2]
    if not tokens:
        return ""
    return " AND ".join(f'"{token.replace(chr(34), chr(34) + chr(34))}"' for token in tokens[:6])


def _table_text_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    except sqlite3.OperationalError:
        return []
    preferred = {
        "full_text",
        "text",
        "normalized_text",
        "title",
        "case_name",
        "case_type",
        "source_dataset",
        "source_path",
    }
    return [str(row[1]) for row in rows if str(row[1]) in preferred]


def _check_target(conn: sqlite3.Connection, columns: set[str], target: dict[str, Any]) -> dict[str, Any]:
    row = _find_target_row(conn, columns, target)
    required_answer = str(target.get("requiredAnswerText") or "")
    result = {
        "graderId": target.get("graderId", ""),
        "targetKind": target.get("targetKind", ""),
        "caseNumber": target.get("caseNumber", ""),
        "fileName": target.get("fileName", ""),
        "court": target.get("court", ""),
        "decisionDate": target.get("decisionDate", ""),
        "requiredAnswerText": required_answer,
        "present": row is not None,
        "requiredAnswerTextPresent": False,
        "canonicalId": "",
        "title": "",
    }
    if row is None:
        return result
    row_dict = dict(row)
    text = "\n".join(str(row_dict.get(column) or "") for column in columns)
    result["canonicalId"] = str(row_dict.get("canonical_id") or "")
    result["title"] = str(row_dict.get("title") or row_dict.get("case_name") or "")
    result["requiredAnswerTextPresent"] = bool(required_answer and required_answer in text)
    return result


def _find_target_row(conn: sqlite3.Connection, columns: set[str], target: dict[str, Any]) -> sqlite3.Row | None:
    clauses: list[str] = []
    params: list[str] = []
    case_number = str(target.get("caseNumber") or "")
    if case_number and "case_number" in columns:
        clauses.append("case_number = ?")
        params.append(case_number)
    file_name = str(target.get("fileName") or "")
    if file_name:
        file_clauses: list[str] = []
        for column in ("source_path", "title", "case_name"):
            if column in columns:
                file_clauses.append(f"{column} LIKE ?")
                params.append(f"%{file_name}%")
        if file_clauses:
            clauses.append("(" + " OR ".join(file_clauses) + ")")
    if not clauses:
        return None
    sql = "SELECT * FROM precedents WHERE " + " OR ".join(clauses) + " LIMIT 1"
    return conn.execute(sql, params).fetchone()


def main() -> int:
    parser = argparse.ArgumentParser(description="Check unified benchmark target coverage in a local corpus DB.")
    parser.add_argument("--private", type=Path, default=None)
    parser.add_argument("--public", type=Path, default=None)
    parser.add_argument("--db-path", type=Path, required=True)
    parser.add_argument("--min-rows", type=int, default=1000, help="minimum corpus rows for MCQ retrieval benchmarks")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    manifest_path = args.private or args.public
    if manifest_path is None:
        raise SystemExit("one of --private or --public is required")
    summary = check_unified_benchmark_coverage(manifest_path, args.db_path, min_rows=args.min_rows)
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
