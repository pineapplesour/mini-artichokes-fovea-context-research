#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any


DEFAULT_DB = Path("/var/lib/universal-artichoke/lawkey/precedents.sqlite3")
DEFAULT_SOURCE_DATASET = "lawkey_pdf_precedents"
DEFAULT_FTS_TEXT_CHARS = 120_000


def _require_fitz():
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise SystemExit("PyMuPDF is required. Install repository requirements first: pip install -r requirements.txt") from exc
    return fitz


def normalize_ws(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_case_number(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").replace("(춘천)", ""))


def normalize_decision_date(value: str) -> str:
    match = re.search(r"(\d{4})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})", value or "")
    if not match:
        return ""
    year, month, day = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    if 1948 <= year <= 2035 and 1 <= month <= 12 and 1 <= day <= 31:
        return f"{year:04d}-{month:02d}-{day:02d}"
    return ""


def stable_id(source_dataset: str, file_name: str, case_number: str, decision_date: str) -> str:
    blob = "|".join([source_dataset, file_name, case_number, decision_date])
    return "prd-" + hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def dedupe_key(case_number: str, court: str, decision_date: str) -> str:
    blob = "|".join(normalize_ws(x) for x in (case_number, court, decision_date)).strip("|")
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:24] if blob else ""


def extract_text(pdf_path: Path) -> str:
    fitz = _require_fitz()
    doc = fitz.open(str(pdf_path))
    try:
        return "\n".join(page.get_text("text") for page in doc)
    finally:
        doc.close()


def display_source_path(pdf_path: Path, source_path_prefix: str) -> str:
    prefix = str(source_path_prefix or "").strip()
    if not prefix:
        return str(pdf_path.resolve())
    separator = "\\" if "\\" in prefix or ":" in prefix else "/"
    return prefix.rstrip("\\/") + separator + pdf_path.name


def parse_metadata(pdf_path: Path, full_text: str, *, source_dataset: str, alias: str, source_path_prefix: str = "") -> dict[str, Any]:
    stem = pdf_path.stem
    if "-" in stem:
        court, case_number = stem.rsplit("-", 1)
    else:
        court, case_number = "", stem
    court = normalize_ws(court)
    case_number = normalize_case_number(case_number)

    decision_date = ""
    for pattern in (
        r"판결선고\s*(\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.)",
        r"(\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.)\s*선고",
    ):
        match = re.search(pattern, full_text)
        if match:
            decision_date = normalize_decision_date(match.group(1))
            break

    alias = normalize_ws(alias)
    title = stem if not alias else f"{stem} | {alias}"
    case_name = alias or stem
    text_hash = hashlib.sha1(full_text.encode("utf-8")).hexdigest()
    canonical_id = stable_id(source_dataset, pdf_path.name, case_number, decision_date)
    fallback_key = f"{pdf_path.name}|{text_hash[:16]}"
    primary_key = dedupe_key(case_number, court, decision_date)
    return {
        "canonical_id": canonical_id,
        "dedupe_key": primary_key or fallback_key,
        "source_dataset": source_dataset,
        "source_path": display_source_path(pdf_path, source_path_prefix),
        "source_record_id": pdf_path.name,
        "source_kind": "pdf",
        "title": title,
        "case_number": case_number,
        "court": court,
        "decision_date": decision_date,
        "case_name": case_name,
        "case_type": "형사",
        "full_text": full_text,
        "text_hash": text_hash,
        "dedupe_key_primary": primary_key or None,
        "dedupe_key_fallback": fallback_key,
        "validation_flags": json.dumps(["explicit_metadata", "pdf_text_extracted"], ensure_ascii=False),
    }


def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def row_exists(conn: sqlite3.Connection, canonical_id: str) -> bool:
    found = conn.execute("SELECT 1 FROM precedents WHERE canonical_id = ? LIMIT 1", (canonical_id,)).fetchone()
    return found is not None


def upsert_precedent(conn: sqlite3.Connection, row: dict[str, Any]) -> tuple[str, bool]:
    columns = table_columns(conn, "precedents")
    if not columns:
        raise RuntimeError("DB does not contain a precedents table")

    exists = row_exists(conn, str(row["canonical_id"]))
    writable = [column for column in columns if column in row]
    if exists:
        updates = [column for column in writable if column != "canonical_id"]
        assignments = ", ".join(f"{column}=?" for column in updates)
        values = [row[column] for column in updates]
        values.append(row["canonical_id"])
        conn.execute(f"UPDATE precedents SET {assignments} WHERE canonical_id=?", values)
        return str(row["canonical_id"]), False

    placeholders = ", ".join("?" for _ in writable)
    col_sql = ", ".join(writable)
    conn.execute(f"INSERT INTO precedents ({col_sql}) VALUES ({placeholders})", [row[column] for column in writable])
    return str(row["canonical_id"]), True


def insert_fts_if_needed(conn: sqlite3.Connection, row: dict[str, Any], *, inserted: bool, fts_text_chars: int) -> None:
    fts_columns = table_columns(conn, "precedents_fts")
    if not fts_columns or not inserted:
        return
    values: dict[str, Any] = {
        "canonical_id": row["canonical_id"],
        "title": row["title"],
        "case_name": row["case_name"],
        "case_number": row["case_number"],
        "court": row["court"],
        "case_type": row["case_type"],
        "full_text": row["full_text"],
        "full_text_head": str(row["full_text"])[:fts_text_chars],
    }
    writable = [column for column in fts_columns if column in values]
    placeholders = ", ".join("?" for _ in writable)
    conn.execute(
        f"INSERT INTO precedents_fts ({', '.join(writable)}) VALUES ({placeholders})",
        [values[column] for column in writable],
    )

    if "precedent_search_docs" in {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
        conn.execute(
            "INSERT OR REPLACE INTO precedent_search_docs (canonical_id, excerpt_chars) VALUES (?, ?)",
            (row["canonical_id"], int(fts_text_chars)),
        )


def iter_pdf_paths(args: argparse.Namespace) -> list[Path]:
    paths = [Path(value) for value in args.pdf]
    if args.pdf_dir:
        paths.extend(sorted(Path(args.pdf_dir).glob("*.pdf")))
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.expanduser().resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest local PDF judgments into a Lawkey precedents SQLite DB.")
    parser.add_argument("--db", type=Path, default=Path(os.getenv("RELIGION_LAWKEY_DB_PATH") or os.getenv("LAWKEY_PRECEDENT_DB_PATH") or DEFAULT_DB))
    parser.add_argument("--pdf-dir", type=Path)
    parser.add_argument("--pdf", action="append", default=[])
    parser.add_argument("--source-dataset", default=DEFAULT_SOURCE_DATASET)
    parser.add_argument("--alias", default="")
    parser.add_argument("--source-path-prefix", default="", help="Optional stable display root for source_path, for example a Google Drive folder.")
    parser.add_argument("--fts-text-chars", type=int, default=DEFAULT_FTS_TEXT_CHARS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pdf_paths = iter_pdf_paths(args)
    if not pdf_paths:
        raise SystemExit("No PDF files were provided. Use --pdf-dir or --pdf.")
    if not args.db.exists():
        raise SystemExit(f"DB not found: {args.db}")

    rows: list[dict[str, Any]] = []
    for pdf_path in pdf_paths:
        if not pdf_path.exists():
            raise SystemExit(f"PDF not found: {pdf_path}")
        full_text = extract_text(pdf_path)
        if not full_text.strip():
            raise SystemExit(f"No extractable text found in PDF: {pdf_path}")
        rows.append(
            parse_metadata(
                pdf_path,
                full_text,
                source_dataset=args.source_dataset,
                alias=args.alias,
                source_path_prefix=args.source_path_prefix,
            )
        )

    if args.dry_run:
        payload = {
            "db": str(args.db),
            "rows": [
                {
                    key: row[key]
                    for key in ("canonical_id", "title", "case_number", "court", "decision_date", "source_path")
                }
                for row in rows
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    results = []
    try:
        for row in rows:
            canonical_id, inserted = upsert_precedent(conn, row)
            insert_fts_if_needed(conn, row, inserted=inserted, fts_text_chars=max(1000, int(args.fts_text_chars)))
            results.append({"canonical_id": canonical_id, "inserted": inserted, "case_number": row["case_number"], "court": row["court"]})
        conn.commit()
    finally:
        conn.close()

    if args.json:
        print(json.dumps({"db": str(args.db), "rows": results}, ensure_ascii=False, indent=2))
    else:
        for item in results:
            action = "inserted" if item["inserted"] else "updated"
            print(f"{action}: {item['canonical_id']} {item['court']} {item['case_number']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
