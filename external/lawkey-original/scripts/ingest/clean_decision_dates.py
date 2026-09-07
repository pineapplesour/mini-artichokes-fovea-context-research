#!/usr/bin/env python3
"""precedents.sqlite3 의 decision_date 중 OCR 오염(예: 4281, 9997, 2079) 을 정제.

- 본문에서 실제 선고일 재추출 (`선고일자:`/`판결선고` 근처)
- 단기(檀紀, 4281~4290)는 +1777 로 변환하여 서기 환산 (4281 → 1948 등)
- 1948~2030 범위 벗어난 값은 빈 문자열로 대체

사용법:
  python3 scripts/ingest/clean_decision_dates.py --db <path>                   # dry run
  python3 scripts/ingest/clean_decision_dates.py --db <path> --apply           # 적용
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

YEAR_VALID_MIN = 1948
YEAR_VALID_MAX = 2030
DANGI_DIFF = 1777  # 檀紀 4281 == 서기 1948 (4281 - 2333 = 1948 but often encoded +1777)

# `선고 YYYY. M. D.` 형태
BODY_DATE_RE = re.compile(r"(?:선고|판결선고)[^\n]{0,30}?(\d{4})\s*[.년]\s*(\d{1,2})\s*[.월]\s*(\d{1,2})")


def fix_date_from_body(full_text: str) -> str:
    if not full_text:
        return ""
    m = BODY_DATE_RE.search(full_text[:5000])
    if not m:
        return ""
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if YEAR_VALID_MIN <= y <= YEAR_VALID_MAX and 1 <= mo <= 12 and 1 <= d <= 31:
        return f"{y:04d}-{mo:02d}-{d:02d}"
    return ""


def try_parse(date_str: str) -> tuple[int, int, int] | None:
    m = re.match(r"(\d{4})[.\-/]?(\d{1,2})[.\-/]?(\d{1,2})", str(date_str or ""))
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return y, mo, d


def cleaned(date_str: str, full_text: str) -> str:
    parsed = try_parse(date_str)
    if parsed:
        y, mo, d = parsed
        if YEAR_VALID_MIN <= y <= YEAR_VALID_MAX and 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{mo:02d}-{d:02d}"
        # Dangi range 4280~4293 → western 2003~2016 etc. 단기 - 2333 = 서기
        if 4281 <= y <= 4363:
            converted = y - 2333
            if YEAR_VALID_MIN <= converted <= YEAR_VALID_MAX:
                return f"{converted:04d}-{mo:02d}-{d:02d}"
    # fallback to body extraction
    return fix_date_from_body(full_text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/srv/lawkey/work16/저장파일/unified_precedent_db_2026-04-10_run3/precedents.sqlite3")
    ap.add_argument("--apply", action="store_true", help="실제 DB 업데이트")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.cursor()
    # Find invalid rows
    rows = cur.execute(
        """SELECT canonical_id, decision_date, full_text FROM precedents
           WHERE decision_date IS NOT NULL AND decision_date != ''"""
    ).fetchall()
    total = len(rows)
    invalid = 0
    fixed = 0
    cleared = 0
    updates: list[tuple[str, str]] = []
    for cid, dd, ft in rows:
        parsed = try_parse(dd)
        if parsed:
            y, mo, d = parsed
            if YEAR_VALID_MIN <= y <= YEAR_VALID_MAX and 1 <= mo <= 12 and 1 <= d <= 31:
                continue  # already valid
        invalid += 1
        new_date = cleaned(dd, ft or "")
        if new_date:
            fixed += 1
        else:
            cleared += 1
        if new_date != dd:
            updates.append((new_date, cid))
    print(f"total={total} invalid={invalid} fixable={fixed} to_clear={cleared}")
    if args.apply and updates:
        cur.executemany("UPDATE precedents SET decision_date = ? WHERE canonical_id = ?", updates)
        conn.commit()
        print(f"applied {len(updates)} updates")
    conn.close()


if __name__ == "__main__":
    main()
