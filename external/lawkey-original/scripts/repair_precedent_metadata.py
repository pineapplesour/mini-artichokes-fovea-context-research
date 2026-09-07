#!/usr/bin/env python3
"""Repair unsafe precedent identity metadata in the SQLite DB.

This migration is deliberately conservative:

* If the original full_text has the common header
  `<record-id> / <title> / <case_number> / <YYYYMMDD> / 선고 / <court>`,
  use that header for case_number, decision_date, and court.
* If no such header exists, do not invent identity fields. Only clear a
  decision_date that is impossible against the case-number year.

The judgment body is never changed.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path


CASE_RE = re.compile(r"^\d{2,4}\s*[가-힣]{1,4}\s*\d{1,6}(?:\s*,\s*\d{1,6})*$")
DATE8_RE = re.compile(r"^\d{8}$")


def norm(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def compact_case(value: object) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def is_placeholder(value: str) -> bool:
    text = norm(value)
    return not text or text.isdigit() or (len(text) <= 2 and text.isalnum())


def append_flag(existing: str, flag: str) -> str:
    raw = norm(existing)
    try:
        parsed = json.loads(raw) if raw else []
    except Exception:
        parsed = []
    if isinstance(parsed, list):
        parts = [str(part) for part in parsed if str(part)]
    else:
        parts = [part for part in raw.split("|") if part]
    if flag not in parts:
        parts.append(flag)
    return json.dumps(parts, ensure_ascii=False)


def case_year(case_number: str) -> int | None:
    match = re.match(r"^(\d{2,4})", compact_case(case_number))
    if not match:
        return None
    raw = match.group(1)
    if len(raw) == 4:
        return int(raw)
    year = int(raw)
    return 1900 + year if year >= 50 else 2000 + year


def date_year(decision_date: str) -> int | None:
    digits = re.sub(r"\D", "", decision_date or "")
    if len(digits) < 4:
        return None
    return int(digits[:4])


def extract_header(full_text: str) -> dict[str, str] | None:
    lines = [norm(line) for line in str(full_text or "").splitlines()[:20]]
    lines = [line for line in lines if line]
    for idx in range(0, max(0, min(len(lines) - 4, 8))):
        case = compact_case(lines[idx])
        date = re.sub(r"\D", "", lines[idx + 1])
        marker = lines[idx + 2]
        court = lines[idx + 3]
        if CASE_RE.match(case) and DATE8_RE.match(date) and marker == "선고" and court:
            title = lines[idx - 1] if idx >= 1 else ""
            return {"case_number": case, "decision_date": date, "court": court, "case_name": title}
    return None


def compute_update(row: sqlite3.Row) -> dict[str, str] | None:
    current_case = compact_case(row["case_number"])
    current_date = norm(row["decision_date"])
    current_court = norm(row["court"])
    current_name = norm(row["case_name"])
    flags = norm(row["validation_flags"])
    header = extract_header(row["full_text"])

    updates: dict[str, str] = {}
    if header and (not current_case or current_case == header["case_number"]):
        if current_case != header["case_number"]:
            updates["case_number"] = header["case_number"]
        if re.sub(r"\D", "", current_date) != header["decision_date"]:
            updates["decision_date"] = header["decision_date"]
        if current_court != header["court"]:
            updates["court"] = header["court"]
        if is_placeholder(current_name) and header["case_name"]:
            updates["case_name"] = header["case_name"]
        if updates:
            flags = append_flag(flags, "metadata_repaired_from_full_text_header")

    check_case = updates.get("case_number", current_case)
    check_date = updates.get("decision_date", current_date)
    cy = case_year(check_case)
    dy = date_year(check_date)
    if cy and dy and (dy < cy or dy > cy + 6):
        updates["decision_date"] = ""
        flags = append_flag(flags, "decision_date_cleared_year_mismatch")

    if updates:
        updates["validation_flags"] = flags
        return updates
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("db", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=30000")
    if not args.apply:
        con.execute("PRAGMA query_only=ON")

    cursor = con.execute(
        "SELECT canonical_id, case_number, court, decision_date, case_name, full_text, validation_flags FROM precedents"
    )
    scanned = changed = header_repairs = mismatch_clears = 0
    samples: list[tuple[str, dict[str, str]]] = []
    updates_batch: list[tuple[str, str, str, str, str, str]] = []

    while True:
        rows = cursor.fetchmany(500)
        if not rows:
            break
        for row in rows:
            scanned += 1
            update = compute_update(row)
            if update:
                changed += 1
                if "metadata_repaired_from_full_text_header" in update.get("validation_flags", ""):
                    header_repairs += 1
                if "decision_date_cleared_year_mismatch" in update.get("validation_flags", ""):
                    mismatch_clears += 1
                if len(samples) < 10:
                    samples.append((row["canonical_id"], update))
                if args.apply:
                    updates_batch.append(
                        (
                            update.get("case_number", row["case_number"]),
                            update.get("court", row["court"]),
                            update.get("decision_date", row["decision_date"]),
                            update.get("case_name", row["case_name"]),
                            update.get("validation_flags", row["validation_flags"]),
                            row["canonical_id"],
                        )
                    )
            if args.limit and scanned >= args.limit:
                rows = []
                break
        if args.apply and updates_batch:
            con.executemany(
                "UPDATE precedents SET case_number=?, court=?, decision_date=?, case_name=?, validation_flags=? WHERE canonical_id=?",
                updates_batch,
            )
            updates_batch.clear()
        if args.limit and scanned >= args.limit:
            break

    if args.apply:
        con.commit()
    print(
        f"scanned={scanned} changed={changed} header_repairs={header_repairs} "
        f"mismatch_clears={mismatch_clears} applied={args.apply}"
    )
    for canonical_id, update in samples:
        preview = {key: update[key] for key in ("case_number", "court", "decision_date", "case_name", "validation_flags") if key in update}
        print(canonical_id, preview)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
