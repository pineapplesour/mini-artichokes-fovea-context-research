#!/usr/bin/env python3
"""통합된 staging.jsonl들을 메인 precedents DB에 UPSERT.

사용법:
  python3 scripts/ingest/merge_into_main_db.py                 # 모든 staging 병합
  python3 scripts/ingest/merge_into_main_db.py --source 08_lawgokr_drf

병합 규칙:
  - canonical_id (안정 해시) 기준으로 UPSERT
  - dedupe_key(case_number,court,decision_date) 로 중복 검사
  - FTS 테이블 `precedents_fts` 재인덱싱
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.ingest._common import (  # noqa: E402
    INGEST_ROOT,
    MAIN_DB,
    dedupe_key,
    normalize_text,
)

FTS_COLS = ("canonical_id", "title", "case_name", "case_number", "court", "case_type", "full_text_head")


def upsert(conn: sqlite3.Connection, row: dict) -> bool:
    canonical_id = row.get("canonical_id")
    if not canonical_id:
        return False
    dk = dedupe_key(row.get("case_number") or "", row.get("court") or "", row.get("decision_date") or "")
    source_dataset = row.get("source_dataset") or ""
    source_path = row.get("source_path") or ""
    source_record_id = row.get("source_record_id") or ""
    source_kind = row.get("source_kind") or "html"
    title = row.get("title") or ""
    case_number = row.get("case_number") or ""
    court = row.get("court") or ""
    decision_date = row.get("decision_date") or ""
    case_name = row.get("case_name") or ""
    case_type = row.get("case_type") or ""
    full_text = row.get("full_text") or ""
    text_hash = hashlib.sha1(full_text.encode("utf-8")).hexdigest()

    cur = conn.cursor()
    existing = cur.execute("SELECT canonical_id FROM precedents WHERE canonical_id = ?", (canonical_id,)).fetchone()
    if existing:
        cur.execute(
            """UPDATE precedents
               SET source_path=?, title=?, case_number=?, court=?, decision_date=?,
                   case_name=?, case_type=?, full_text=?, text_hash=?
               WHERE canonical_id=?""",
            (source_path, title, case_number, court, decision_date, case_name, case_type, full_text, text_hash, canonical_id),
        )
        # FTS DELETE is O(N_fts) on `canonical_id unindexed` → only do it on
        # update path where there might actually be a stale FTS row.
        cur.execute("DELETE FROM precedents_fts WHERE canonical_id = ?", (canonical_id,))
    else:
        # `dedupe_key_fallback` is NOT NULL in the schema. Fall back to a
        # stable per-row hash so re-runs upsert idempotently even when the
        # primary (court|case_number|date) triple is missing.
        dedupe_key_primary = dk or None
        dedupe_key_fallback_value = f"{source_record_id}|{text_hash[:16]}" if source_record_id else f"{canonical_id}|{text_hash[:16]}"
        cur.execute(
            """INSERT INTO precedents (canonical_id, dedupe_key, source_dataset, source_path,
                                       source_record_id, source_kind, title, case_number, court,
                                       decision_date, case_name, case_type, full_text, text_hash,
                                       dedupe_key_primary, dedupe_key_fallback, validation_flags)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (canonical_id, dk or dedupe_key_fallback_value, source_dataset, source_path,
             source_record_id, source_kind, title, case_number, court, decision_date,
             case_name, case_type, full_text, text_hash, dedupe_key_primary, dedupe_key_fallback_value,
             '["explicit_metadata"]'),
        )
    cur.execute(
        "INSERT INTO precedents_fts (canonical_id, title, case_name, case_number, court, case_type, full_text_head) VALUES (?,?,?,?,?,?,?)",
        (canonical_id, title, case_name, case_number, court, case_type, full_text[:20000]),
    )
    return not existing  # True = inserted, False = updated


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", help="Only merge this source (e.g. 08_lawgokr_drf)")
    ap.add_argument("--db", default=str(MAIN_DB))
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    total_new = 0
    total_updated = 0
    sources = []
    if args.source:
        sources = [INGEST_ROOT / args.source]
    else:
        sources = [p for p in INGEST_ROOT.glob("*") if p.is_dir()]
    BATCH = 1000
    for source_dir in sources:
        staging = source_dir / "staging.jsonl"
        if not staging.exists():
            continue
        source = source_dir.name
        print(f"merging {staging} …", flush=True)
        n_src_new, n_src_upd = 0, 0
        rows_processed = 0
        with staging.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                try:
                    inserted = upsert(conn, row)
                except Exception as exc:
                    print(f"  row failed: {exc}", flush=True)
                    continue
                if inserted:
                    n_src_new += 1
                else:
                    n_src_upd += 1
                rows_processed += 1
                if rows_processed % BATCH == 0:
                    conn.commit()
                    print(f"  {source}: {rows_processed} processed (+{n_src_new}/~{n_src_upd})", flush=True)
        conn.commit()
        print(f"  {source}: +{n_src_new} new, ~{n_src_upd} updated", flush=True)
        total_new += n_src_new
        total_updated += n_src_upd
    conn.close()
    print(f"TOTAL: +{total_new} new, ~{total_updated} updated")


if __name__ == "__main__":
    main()
