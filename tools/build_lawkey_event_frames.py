#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared_platform.context_frames import ensure_event_frame_schema, stored_event_frames_from_records, upsert_event_frames


def build_lawkey_event_frames(db_path: Path, *, limit: int | None = None) -> dict[str, Any]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_event_frame_schema(conn)
        sql = "SELECT canonical_id, full_text FROM precedents ORDER BY canonical_id"
        params: tuple[object, ...] = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (int(limit),)
        rows = conn.execute(sql, params).fetchall()
        frames = stored_event_frames_from_records(list(rows))
        upsert_event_frames(conn, frames)
        conn.commit()
        return {
            "dbPath": str(db_path),
            "sourceCount": len(rows),
            "frameCount": len(frames),
            "extractor": "context_frames_v0",
        }
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic v0 Lawkey event frames.")
    parser.add_argument("--db-path", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--report-out", type=Path, default=None)
    args = parser.parse_args()
    report = build_lawkey_event_frames(args.db_path, limit=args.limit)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
