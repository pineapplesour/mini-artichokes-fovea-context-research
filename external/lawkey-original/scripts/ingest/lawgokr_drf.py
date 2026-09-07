#!/usr/bin/env python3
"""법제처 OPEN API (DRF) 판례 자동 수집.

선결조건:
  1. https://open.law.go.kr 회원가입
  2. "OpenAPI 활용신청" → 도메인 또는 IP 등록 (서버: lawkey.ai.kr / 43.200.191.87)
  3. 발급받은 사용자ID (영문 4자) 를 LAWGOKR_OC 환경변수에 설정

사용법:
  LAWGOKR_OC=yourID python3 scripts/ingest/lawgokr_drf.py --since 2024-01-01 --max 5000

이 스크립트는 다음을 수행합니다:
  - 검색 API로 신규 판례 ID 목록 수집
  - 본문 API로 개별 판례 XML/HTML 다운로드 → raw/
  - 정규화 → staging.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import requests  # type: ignore

from scripts.ingest._common import (  # noqa: E402
    append_staging,
    normalize_decision_date,
    normalize_text,
    raw_dir,
    sleep_with_jitter,
    stable_canonical_id,
    staging_path,
)

SOURCE = "08_lawgokr_drf"
SEARCH_URL = "https://www.law.go.kr/DRF/lawSearch.do"
DETAIL_URL = "https://www.law.go.kr/DRF/lawService.do"


def search_ids(oc: str, query: str, *, page: int = 1, display: int = 100) -> list[dict]:
    params = {
        "OC": oc,
        "target": "prec",
        "type": "JSON",
        "query": query,
        "page": page,
        "display": display,
    }
    r = requests.get(SEARCH_URL, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    out = []
    rows = (data.get("PrecSearch") or {}).get("prec") or []
    for row in rows:
        out.append({
            "id": str(row.get("판례일련번호") or "").strip(),
            "case_number": str(row.get("사건번호") or "").strip(),
            "case_name": str(row.get("사건명") or "").strip(),
            "court": str(row.get("법원명") or "").strip(),
            "decision_date": str(row.get("선고일자") or "").strip(),
            "case_type": str(row.get("사건종류명") or "").strip(),
        })
    return out


def fetch_detail(oc: str, prec_id: str) -> str:
    params = {
        "OC": oc,
        "target": "prec",
        "type": "HTML",
        "ID": prec_id,
    }
    r = requests.get(DETAIL_URL, params=params, timeout=30)
    r.raise_for_status()
    return r.text


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2023-01-01", help="kept for future use; DRF doesn't filter date directly")
    ap.add_argument("--query", default="*", help="검색어 (기본 * = 전체)")
    ap.add_argument("--max", type=int, default=1000, help="최대 수집 건수")
    ap.add_argument("--start-page", type=int, default=1)
    args = ap.parse_args()

    oc = os.environ.get("LAWGOKR_OC", "").strip()
    if not oc:
        sys.stderr.write("ERROR: LAWGOKR_OC env var required (registered IP/domain on open.law.go.kr).\n")
        sys.exit(2)

    raw = raw_dir(SOURCE)
    staging_path(SOURCE).unlink(missing_ok=True)
    collected = 0
    page = args.start_page
    while collected < args.max:
        try:
            ids = search_ids(oc, args.query, page=page, display=100)
        except Exception as exc:
            sys.stderr.write(f"search page={page} failed: {exc}\n")
            break
        if not ids:
            break
        for hit in ids:
            if collected >= args.max:
                break
            prec_id = hit.get("id")
            if not prec_id:
                continue
            cache_path = raw / f"{prec_id}.html"
            if not cache_path.exists():
                try:
                    text = fetch_detail(oc, prec_id)
                except Exception as exc:
                    sys.stderr.write(f"detail {prec_id} failed: {exc}\n")
                    sleep_with_jitter(2.0)
                    continue
                cache_path.write_text(text, encoding="utf-8")
                sleep_with_jitter(0.6)
            full_text = cache_path.read_text(encoding="utf-8")
            row = {
                "source_dataset": SOURCE,
                "source_path": f"{DETAIL_URL}?ID={prec_id}",
                "source_record_id": prec_id,
                "source_kind": "html",
                "title": hit.get("case_name") or hit.get("case_number") or "",
                "case_number": normalize_text(hit.get("case_number")),
                "court": normalize_text(hit.get("court")),
                "decision_date": normalize_decision_date(hit.get("decision_date")),
                "case_name": normalize_text(hit.get("case_name")),
                "case_type": normalize_text(hit.get("case_type")),
                "full_text": full_text,
                "canonical_id": stable_canonical_id(SOURCE, prec_id, hit.get("case_number") or "", normalize_decision_date(hit.get("decision_date"))),
            }
            append_staging(SOURCE, row)
            collected += 1
        page += 1
        sleep_with_jitter(0.4)
    sys.stderr.write(f"done. collected={collected} into {staging_path(SOURCE)}\n")


if __name__ == "__main__":
    main()
