"""Shared helpers for precedent ingestion scripts.

All ingestion sources land here:
  raw → /srv/lawkey/ingest/<source>/raw/   (downloaded files, unchanged)
  staging → /srv/lawkey/ingest/<source>/staging.jsonl  (normalized rows)

Then `merge_into_main_db.py` upserts staging rows into the main precedents DB.

Row schema (normalized):
  {
    "source_dataset": "08_lawgokr_drf",
    "source_path": "<original location>",
    "source_record_id": "<stable id from source>",
    "source_kind": "json|html|xml|...",
    "title": str,
    "case_number": str,
    "court": str,
    "decision_date": "YYYY-MM-DD",
    "case_name": str,
    "case_type": str,
    "full_text": str,
  }
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
from pathlib import Path
from typing import Any, Iterable

INGEST_ROOT = Path("/srv/lawkey/ingest")
MAIN_DB = Path("/srv/lawkey/work16/저장파일/unified_precedent_db_2026-04-10_run3/precedents.sqlite3")


def staging_path(source: str) -> Path:
    p = INGEST_ROOT / source
    p.mkdir(parents=True, exist_ok=True)
    return p / "staging.jsonl"


def raw_dir(source: str) -> Path:
    p = INGEST_ROOT / source / "raw"
    p.mkdir(parents=True, exist_ok=True)
    return p


def append_staging(source: str, row: dict[str, Any]) -> None:
    with staging_path(source).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFC", str(value or ""))
    text = re.sub(r"[\s\u3000]+", " ", text)
    return text.strip()


def normalize_decision_date(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    m = re.search(r"(\d{4})[.\-/년\s]+(\d{1,2})[.\-/월\s]+(\d{1,2})", raw)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1948 <= y <= 2030 and 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{mo:02d}-{d:02d}"
    m = re.match(r"(\d{4})[.\-]?(\d{2})[.\-]?(\d{2})", raw)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1948 <= y <= 2030 and 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{mo:02d}-{d:02d}"
    return ""


def stable_canonical_id(source: str, source_record_id: str, case_number: str = "", decision_date: str = "") -> str:
    """Build a deterministic ID so re-runs upsert instead of duplicating."""
    parts = [source, source_record_id, case_number, decision_date]
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"prd-{digest}"


def dedupe_key(case_number: str, court: str, decision_date: str) -> str:
    blob = "|".join(normalize_text(x) for x in (case_number, court, decision_date)).strip("|")
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:24] if blob else ""


def sleep_with_jitter(seconds: float, jitter: float = 0.3) -> None:
    time.sleep(max(0.0, seconds + jitter * (hash(time.time()) % 100) / 100.0))
