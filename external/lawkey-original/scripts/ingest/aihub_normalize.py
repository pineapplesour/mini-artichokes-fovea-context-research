#!/usr/bin/env python3
"""AI Hub "법률 규정 텍스트 분석 데이터" 다운로드 후 정규화 → staging.

사용법:
  1. https://www.aihub.or.kr/aihubdata/data/view.do?dataSetSn=71723 에서 신청·승인·다운로드
     (내국인 가입자만 가능. 사용자가 직접 받아 AWS 원본에 업로드)
  2. 압축 해제 → /srv/lawkey/ingest/09_aihub_legal_qa/raw/ 에 배치
  3. python3 scripts/ingest/aihub_normalize.py

스캐너가 *.json / *.txt 를 재귀 탐색해 판례-스타일 row로 정규화합니다.
필드는 AI Hub 스키마에 맞춰 best-effort 매핑; 누락된 것은 빈 문자열.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.ingest._common import (  # noqa: E402
    append_staging,
    normalize_decision_date,
    normalize_text,
    raw_dir,
    stable_canonical_id,
    staging_path,
)

SOURCE = "09_aihub_legal_qa"


def iter_json_rows(root: Path):
    for p in root.rglob("*.json"):
        try:
            with p.open(encoding="utf-8") as f:
                obj = json.load(f)
        except Exception:
            continue
        if isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict):
                    yield p, item
        elif isinstance(obj, dict):
            yield p, obj


def extract(row: dict):
    # AI Hub 71723 schema guesses:
    # 기초정보 / 판례일련번호 / 사건번호 / 법원 / 선고일자 / 사건명 / 판시사항 / 본문 / QA 등
    base = row.get("기초정보") or row.get("base") or {}
    if not isinstance(base, dict):
        base = row
    candidates = {
        "case_number": base.get("사건번호") or row.get("사건번호") or row.get("case_number"),
        "case_name": base.get("사건명") or row.get("사건명") or row.get("case_name"),
        "court": base.get("법원명") or base.get("법원") or row.get("법원") or row.get("court"),
        "decision_date": base.get("선고일자") or row.get("선고일자") or row.get("decision_date"),
        "case_type": base.get("사건종류") or row.get("case_type"),
        "record_id": base.get("판례일련번호") or row.get("판례일련번호") or row.get("id"),
    }
    body_parts = []
    for key in ("본문", "판결문", "판시사항", "판결요지", "판결이유", "body", "full_text"):
        v = row.get(key) or (base.get(key) if isinstance(base, dict) else "")
        if v:
            body_parts.append(str(v))
    return candidates, "\n\n".join(body_parts).strip()


def main() -> None:
    root = raw_dir(SOURCE)
    if not root.exists() or not any(root.iterdir()):
        sys.stderr.write(f"ERROR: place AI Hub files under {root}/ and retry.\n")
        sys.exit(2)
    staging_path(SOURCE).unlink(missing_ok=True)
    collected = 0
    seen_keys: set[str] = set()
    for path, row in iter_json_rows(root):
        info, body = extract(row)
        rec_id = normalize_text(info.get("record_id") or path.stem)
        case_no = normalize_text(info.get("case_number") or "")
        court = normalize_text(info.get("court") or "")
        dd = normalize_decision_date(info.get("decision_date") or "")
        # Dedup key (same case can appear in multiple QA entries).
        k = f"{rec_id}|{case_no}|{dd}"
        if k in seen_keys:
            continue
        seen_keys.add(k)
        out = {
            "source_dataset": SOURCE,
            "source_path": str(path),
            "source_record_id": rec_id,
            "source_kind": "json",
            "title": normalize_text(info.get("case_name") or case_no or rec_id),
            "case_number": case_no,
            "court": court,
            "decision_date": dd,
            "case_name": normalize_text(info.get("case_name") or ""),
            "case_type": normalize_text(info.get("case_type") or ""),
            "full_text": body,
            "canonical_id": stable_canonical_id(SOURCE, rec_id, case_no, dd),
        }
        append_staging(SOURCE, out)
        collected += 1
    sys.stderr.write(f"done. collected={collected} rows into {staging_path(SOURCE)}\n")


if __name__ == "__main__":
    main()
