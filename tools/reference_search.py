#!/usr/bin/env python3
"""Generic content search helper over a reference corpus (ships with solver input).

Usage:
  python3 search.py QUERY [--limit 20] [--since YYYY] [--snippet-terms t1,t2]

QUERY is an FTS5 expression over the FULL body text. Korean is agglutinative
and the tokenizer is unicode61, so ALWAYS use prefix wildcards for Korean
stems: `군수*`, `추행*`, `뇌물*`. Combine with AND/OR/NEAR:
  "군수* AND 민원*"        both stems anywhere in one document
  "NEAR(군수* 추행*, 30)"  stems within 30 tokens of each other

Named entities (people, places) are usually MASKED in court documents —
search by roles, acts, statutes, and relations instead of proper nouns.

Prints one result per line: canonical_id | court | case_number | date | title,
then a short snippet around the first matching term from the document body.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FTS_DB = HERE / "precedents_fulltext_fts.sqlite3"
MAIN_DB = HERE / "precedents.sqlite3"


def snippet(text: str, terms: list[str], width: int = 160) -> str:
    for term in terms:
        stem = term.rstrip("*")
        index = text.find(stem)
        if index >= 0:
            start = max(0, index - width // 2)
            return text[start : start + width].replace("\n", " ")
    return text[:width].replace("\n", " ")


def question_stems(question: str, connection: sqlite3.Connection, max_stems: int = 6) -> list[str]:
    """Extract searchable Korean stems from a free-form question.

    Takes 2-char prefixes of Korean tokens (agglutination-safe), dedups, and
    keeps the stems that actually occur in the corpus, ordered by document
    frequency descending (common role/act words first; masked entity names
    still pass through — the subset ladder below makes them harmless).
    """
    tokens = re.findall(r"[가-힣]{2,}", question)
    seen: list[str] = []
    for token in tokens:
        stem = token[:2]
        if stem not in seen:
            seen.append(stem)
    scored: list[tuple[int, str]] = []
    for stem in seen:
        try:
            df = connection.execute(
                "SELECT count(*) FROM fts WHERE fts MATCH ?", (f'"{stem}"*',)
            ).fetchone()[0]
        except sqlite3.OperationalError:
            continue
        if df > 0:
            scored.append((df, stem))
    scored.sort(reverse=True)
    return [stem for _, stem in scored[:max_stems]]


def ladder_search(question: str, *, limit: int = 20, case_filter: str = "") -> list[tuple]:
    """Deterministic query ladder: try every 3- and 2-stem AND combination of
    the question's corpus stems, fuse ranks, and return merged candidates.

    A masked document cannot match combinations containing the masked entity
    stems, but it surfaces through the combinations of the surviving role/act
    stems — no manual query crafting needed.
    """
    from itertools import combinations

    fts = sqlite3.connect(f"file:{FTS_DB}?mode=ro", uri=True)
    stems = question_stems(question, fts)
    best: dict[int, tuple[float, tuple, tuple]] = {}
    for size in (3, 2):
        for combo in combinations(stems, size):
            match = " AND ".join(f'"{stem}"*' for stem in combo)
            try:
                rows = fts.execute(
                    f"""SELECT d.rowid, d.canonical_id, d.court, d.case_number,
                              d.decision_date, d.title, bm25(fts)
                       FROM fts JOIN docs d ON fts.rowid=d.rowid
                       WHERE fts MATCH ?{(' AND (' + case_filter + ')') if case_filter else ''}
                       ORDER BY bm25(fts) LIMIT 12""",
                    (match,),
                ).fetchall()
            except sqlite3.OperationalError:
                continue
            for rank, row in enumerate(rows):
                # Reward specific (larger) combos and better ranks.
                score = size * 10 - rank
                current = best.get(row[0])
                if current is None or score > current[0]:
                    best[row[0]] = (score, row, combo)
    fused = sorted(best.values(), key=lambda item: -item[0])[:limit]
    return [(score, row, combo) for score, row, combo in fused]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--since", default="")
    parser.add_argument("--snippet-terms", default="")
    parser.add_argument(
        "--question",
        action="store_true",
        help="treat the argument as a free-form question: extract stems, run the combination ladder, fuse ranks",
    )
    args = parser.parse_args()
    if args.question:
        main_db = sqlite3.connect(f"file:{MAIN_DB}?mode=ro", uri=True) if MAIN_DB.is_file() else None
        for score, row, combo in ladder_search(args.query, limit=args.limit):
            _, canonical_id, court, case_number, date, title, _ = row
            print(f"[{score}] {'+'.join(combo)} | {canonical_id} | {court or '?'} | {case_number or '?'} | {date or '?'} | {(title or '')[:50]}")
            if main_db is not None:
                body = main_db.execute("SELECT full_text FROM precedents WHERE rowid=?", (row[0],)).fetchone()
                if body and body[0]:
                    print("   …", snippet(body[0], [stem for stem in combo]))
        return 0
    if not FTS_DB.is_file():
        print("full-text index missing; fall back to main DB LIKE scans", file=sys.stderr)
        return 2
    fts = sqlite3.connect(f"file:{FTS_DB}?mode=ro", uri=True)
    main_db = sqlite3.connect(f"file:{MAIN_DB}?mode=ro", uri=True) if MAIN_DB.is_file() else None
    where = "fts MATCH ?"
    params: list = [args.query]
    if args.since:
        where += " AND d.decision_date >= ?"
        params.append(args.since)
    rows = fts.execute(
        f"""SELECT d.rowid, d.canonical_id, d.court, d.case_number, d.decision_date, d.title
            FROM fts JOIN docs d ON fts.rowid = d.rowid
            WHERE {where} ORDER BY d.decision_date DESC LIMIT ?""",
        (*params, args.limit),
    ).fetchall()
    terms = [t for t in re.split(r"[,\s]+", args.snippet_terms or args.query) if t and t.upper() not in ("AND", "OR", "NOT") and not t.startswith("NEAR")]
    for rowid, canonical_id, court, case_number, date, title in rows:
        print(f"{canonical_id} | {court or '?'} | {case_number or '?'} | {date or '?'} | {(title or '')[:60]}")
        if main_db is not None:
            body = main_db.execute(
                "SELECT full_text FROM precedents WHERE rowid=?", (rowid,)
            ).fetchone()
            if body and body[0]:
                print("   …", snippet(body[0], terms))
    print(f"[{len(rows)} hits]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
