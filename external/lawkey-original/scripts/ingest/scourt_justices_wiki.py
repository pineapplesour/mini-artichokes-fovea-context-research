#!/usr/bin/env python3
"""위키피디아 "대한민국의 대법관" 페이지에서 역대 대법원장·대법관 명단 스크레이핑.

출력: /srv/lawkey/ingest/10_wiki_justices/staging.jsonl
후속: judges.py에서 이 명단을 검증용 마스터로 사용 (임명일 ± 6년 이내 판례 cluster 매칭 시
      over-merge/under-merge 자동 점검).

라이선스: 위키피디아는 CC BY-SA. 출처 표기: "Wikipedia contributors, <url>"
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import requests  # type: ignore

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.ingest._common import append_staging, raw_dir, staging_path  # noqa: E402

SOURCE = "10_wiki_justices"
URL = "https://ko.wikipedia.org/api/rest_v1/page/html/대한민국의_대법관"
DATE_RE = re.compile(r"(\d{4})년\s*(\d{1,2})월")

# Infobox label / header text that accidentally parses as a Korean name.
NON_NAME_WORDS = {
    "지명자", "임명자", "임기", "형성", "웹사이트", "구분", "대법관", "대법원장",
    "이름", "취임일", "임명", "제청", "자격", "국적", "연봉", "설립", "소속",
    "전직", "후임", "현직", "주소", "전화", "기관장", "소재지", "행정부", "사법부",
    "회계연도", "국내총생산", "인구", "수도",
}


def fetch() -> str:
    headers = {
        "User-Agent": "LawkeyAI-ingest/1.0 (https://lawkey.ai.kr; contact contact@lawkey.ai.kr)",
        "Accept": "text/html",
    }
    r = requests.get(URL, timeout=30, headers=headers)
    r.raise_for_status()
    return r.text


def parse_rows(html: str) -> list[dict]:
    row_re = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
    cell_re = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
    name_re = re.compile(r"^[가-힣]{2,4}(\([^)]+\))?$")
    out = []
    current_role = ""
    for r in row_re.findall(html):
        cells_raw = cell_re.findall(r)
        cells = [re.sub(r"<[^>]+>", " ", c) for c in cells_raw]
        cells = [re.sub(r"\s+", " ", c).strip() for c in cells]
        if not cells:
            continue
        # Role header rows like "대법원장 / 이름 / 취임일 / 임명 / 제청"
        if cells[0] in ("구분", "대법관") and len(cells) >= 2 and cells[1] == "이름":
            current_role = "대법관"
            continue
        if cells[0] == "대법원장" and len(cells) == 5:
            # (role=대법원장, name, date, ...)
            current_role = "대법원장"
            # first row for 대법원장 could have the fields inline
            if name_re.match(cells[1] or ""):
                out.append({"role": "대법원장", "name": cells[1], "start": cells[2] or ""})
            continue
        if len(cells) >= 2 and name_re.match(cells[0]):
            # Regular row: [name, ...] (대법원장 already absorbed above)
            name = cells[0].split()[0]
            if name in NON_NAME_WORDS:
                continue
            # Require at least a year or role context to reduce false positives
            period = ""
            for c in cells:
                if "~" in c and re.search(r"\d{4}", c):
                    period = c
                    break
            if not period and not current_role:
                continue
            out.append({"role": current_role or "대법관", "name": name, "period": period})
    return out


def main() -> None:
    html = fetch()
    cache = raw_dir(SOURCE) / "대한민국의_대법관.html"
    cache.write_text(html, encoding="utf-8")
    staging_path(SOURCE).unlink(missing_ok=True)
    rows = parse_rows(html)
    seen: set[str] = set()
    n = 0
    for rec in rows:
        key = f"{rec.get('role','')}|{rec.get('name','')}|{rec.get('period','')}"
        if key in seen:
            continue
        seen.add(key)
        append_staging(SOURCE, {
            "source_dataset": SOURCE,
            "source_path": URL,
            "source_record_id": key,
            "source_kind": "wiki",
            **rec,
        })
        n += 1
    print(f"parsed {n} justices → {staging_path(SOURCE)}")


if __name__ == "__main__":
    main()
