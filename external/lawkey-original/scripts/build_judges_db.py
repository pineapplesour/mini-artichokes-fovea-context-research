#!/usr/bin/env python3
"""Build /srv/lawkey/shared/judges.sqlite3 from precedents.sqlite3.

Usage:
  python3 scripts/build_judges_db.py \
      --precedents /srv/lawkey/work16/저장파일/.../precedents.sqlite3 \
      --out /srv/lawkey/shared/judges.sqlite3
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Make backend importable when run as a script
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.judges import open_db, populate_appearances, cluster_judges  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--precedents", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    print(f"opening output db at {args.out}", flush=True)
    db = open_db(args.out)
    t0 = time.time()
    print("populating appearances ...", flush=True)
    stats = populate_appearances(db, args.precedents)
    print(f"  stats: {stats}", flush=True)
    print(f"  elapsed: {time.time() - t0:.1f}s", flush=True)
    t1 = time.time()
    print("clustering judges ...", flush=True)
    cluster_stats = cluster_judges(db)
    print(f"  cluster_stats: {cluster_stats}", flush=True)
    print(f"  elapsed: {time.time() - t1:.1f}s", flush=True)
    db.close()


if __name__ == "__main__":
    main()
