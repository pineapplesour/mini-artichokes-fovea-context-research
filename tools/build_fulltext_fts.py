#!/usr/bin/env python3
"""Build a full-body FTS5 index for the precedent corpus in a separate file.

The production precedents DB indexes only `full_text_head` with a unicode61
tokenizer, so deep-body content search is impossible and Korean agglutinative
forms need prefix queries. This builds a contentless FTS5 index over the
COMPLETE `full_text` of every row into a separate SQLite file, leaving the
source DB byte-identical (it is hardlinked into frozen campaign inputs).

Layout of the output DB:
  fts(text)            — contentless FTS5, tokenize='unicode61', rowid = doc id
  docs(rowid, canonical_id, court, case_number, decision_date, title)

Query pattern (also implemented in tools/reference_search.py):
  SELECT d.* FROM fts JOIN docs d ON fts.rowid=d.rowid
  WHERE fts MATCH '군수* AND 추행*' LIMIT 20;
"""
from __future__ import annotations

import argparse
import sqlite3
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch", type=int, default=2000)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    src = sqlite3.connect(f"file:{args.source}?mode=ro", uri=True)
    out = sqlite3.connect(args.output)
    out.executescript(
        """
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        CREATE VIRTUAL TABLE fts USING fts5(text, content='', tokenize='unicode61');
        CREATE TABLE docs(
          rowid INTEGER PRIMARY KEY,
          canonical_id TEXT, court TEXT, case_number TEXT,
          decision_date TEXT, title TEXT
        );
        """
    )
    cursor = src.execute(
        "SELECT rowid, canonical_id, court, case_number, decision_date, title, full_text FROM precedents"
    )
    started = time.time()
    count = 0
    while True:
        rows = cursor.fetchmany(args.batch)
        if not rows:
            break
        out.executemany(
            "INSERT INTO fts(rowid, text) VALUES (?, ?)",
            [(r[0], r[6] or "") for r in rows],
        )
        out.executemany(
            "INSERT INTO docs VALUES (?,?,?,?,?,?)",
            [(r[0], r[1], r[2], r[3], r[4], r[5]) for r in rows],
        )
        count += len(rows)
        if count % 20000 == 0:
            out.commit()
            print(f"{count} rows, {time.time()-started:.0f}s", flush=True)
    out.commit()
    out.execute("INSERT INTO fts(fts) VALUES('optimize')")
    out.commit()
    print(f"DONE {count} rows in {time.time()-started:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
