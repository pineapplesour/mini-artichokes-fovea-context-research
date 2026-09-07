#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared_platform.lawkey_graph import rebuild_lawkey_source_graph  # noqa: E402


DEFAULT_DB = Path("/var/lib/universal-artichoke/lawkey/precedents.sqlite3")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the precomputed Lawkey source graph inside a precedents DB.")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(os.getenv("RELIGION_LAWKEY_DB_PATH") or os.getenv("LAWKEY_PRECEDENT_DB_PATH") or DEFAULT_DB),
    )
    parser.add_argument("--graph-version", default="")
    parser.add_argument("--no-activate", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.db.exists():
        raise SystemExit(f"DB not found: {args.db}")
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        report = rebuild_lawkey_source_graph(
            conn,
            graph_version=args.graph_version,
            activate=not args.no_activate,
        )
    finally:
        conn.close()
    payload = asdict(report)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            "built Lawkey graph "
            f"{report.graph_version}: sources={report.source_count} "
            f"entities={report.entity_count} edges={report.edge_count} "
            f"activated={report.activated}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
