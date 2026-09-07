#!/usr/bin/env python3
"""HuggingFace 한국 법률 데이터셋 수집기.

각 소스를 staging.jsonl 로 정규화한다. 본문이 비어있는 row 는 즉시 버린다.
식별 메타(case_number/court/decision_date/case_name)는 데이터셋의 명시
컬럼에서만 가져온다 — 본문 텍스트 스캔으로 추론하지 않는다 (DB 의 기존
fabricated-metadata 버그를 재현하지 않기 위해).

지원 소스:
  - lawdata4: Rootpye/korean-lawdata4 (판결문 요약, info+sentences 구조)
  - lawdata1: Rootpye/korean-lawdata1 (결정례 CSV)

사용법:
  python3 scripts/ingest/hf_korean_legal_collect.py --dataset lawdata4
  python3 scripts/ingest/hf_korean_legal_collect.py --dataset lawdata1
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

# Some CSVs (e.g. ducut91 court judgments) embed full case bodies (>100KB)
# inside a single CSV cell. Default csv field limit is 131072 bytes which
# truncates them mid-row.
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

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


def parse_doc_id(doc_id: str) -> tuple[str, str]:
    """`부산지방법원-2016가단320650` → (court, case_number).
    `대법원-2025-두-34754` 등 분절도 대응.
    """
    raw = (doc_id or "").strip()
    if not raw:
        return "", ""
    parts = raw.split("-")
    if len(parts) == 1:
        return "", parts[0]
    court = parts[0]
    rest = "".join(parts[1:])
    return court, rest


def collect_lawdata4(out_source: str = "20_hf_lawdata4_pansol_summary") -> int:
    """Rootpye/korean-lawdata4: TL_*/판결문_요약_*.json — 판결문 요약."""
    from huggingface_hub import snapshot_download

    repo_id = "Rootpye/korean-lawdata4"
    print(f"[lawdata4] snapshot_download {repo_id} …", flush=True)
    local_dir = Path(snapshot_download(repo_id=repo_id, repo_type="dataset"))
    print(f"[lawdata4] local_dir = {local_dir}", flush=True)

    staging_path(out_source).unlink(missing_ok=True)
    n_total = n_kept = 0
    started = time.time()
    for path in local_dir.rglob("*.json"):
        n_total += 1
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        info = d.get("info") or {}
        sentences = (d.get("taskinfo") or {}).get("sentences") or []
        body = "\n".join(str(s).strip() for s in sentences if isinstance(s, str) and s.strip())
        if not body or len(body) < 80:
            continue
        court, case_number = parse_doc_id(str(info.get("doc_id") or ""))
        court = normalize_text(info.get("normalized_court")) or court
        case_name = normalize_text(info.get("casenames"))
        decision_date = normalize_decision_date(info.get("announce_date"))
        case_type_raw = str(info.get("casetype") or "")
        case_type = {"civil": "민사", "criminal": "형사", "admin": "행정"}.get(case_type_raw, case_type_raw)
        record_id = str(info.get("doc_id") or path.stem)
        canonical = stable_canonical_id(out_source, record_id, case_number, decision_date)
        row = {
            "canonical_id": canonical,
            "source_dataset": out_source,
            "source_path": f"{repo_id}::{path.relative_to(local_dir)}",
            "source_record_id": record_id,
            "source_kind": "json",
            "title": case_name or case_number,
            "case_number": case_number,
            "court": court,
            "decision_date": decision_date,
            "case_name": case_name,
            "case_type": case_type,
            "full_text": body,
        }
        append_staging(out_source, row)
        n_kept += 1
        if n_kept % 1000 == 0:
            print(f"  [lawdata4] kept={n_kept:,}/{n_total:,}  elapsed={time.time()-started:.0f}s", flush=True)
    print(f"[lawdata4] DONE total={n_total:,} kept={n_kept:,} elapsed={time.time()-started:.0f}s")
    return n_kept


def collect_lawdata1(out_source: str = "21_hf_lawdata1_decision") -> int:
    """Rootpye/korean-lawdata1: TS_결정례/HS_K_*.csv — 결정례.

    CSV 컬럼: 결정례일련번호,구분,문장번호,내용
    한 파일이 한 결정례. 식별 메타는 본문 첫 30줄에서 정규식으로만 추출
    (case_number/court/decision_date 패턴이 명시적으로 등장하면 사용,
    없으면 그 행은 버린다 — 임의 추정 금지).
    """
    from huggingface_hub import snapshot_download

    repo_id = "Rootpye/korean-lawdata1"
    print(f"[lawdata1] snapshot_download {repo_id} …", flush=True)
    local_dir = Path(snapshot_download(repo_id=repo_id, repo_type="dataset"))
    print(f"[lawdata1] local_dir = {local_dir}", flush=True)

    staging_path(out_source).unlink(missing_ok=True)
    n_total = n_kept = n_meta_short = 0
    started = time.time()

    case_re = re.compile(r"\b(\d{2,4}[가-힣]+\d+)\b")
    court_re = re.compile(r"(헌법재판소|대법원|[가-힣]{2,8}(?:행정|고등|지방)법원)")
    date_re = re.compile(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.")
    case_name_re = re.compile(r"사\s*건[:\s]+\d{2,4}[가-힣]+\d+\s+(.+?)(?:$|【)")

    for path in local_dir.rglob("*.csv"):
        n_total += 1
        try:
            sentences: list[str] = []
            id_ = ""
            with path.open("r", encoding="utf-8", errors="replace") as f:
                rows = list(csv.DictReader(f))
            for row in rows:
                guess = (row.get("구분") or "").strip()
                if guess in ("전문", "본문", "주문", "이유", "결정") and row.get("내용"):
                    sentences.append(str(row["내용"]).strip())
                if not id_ and row.get("결정례일련번호"):
                    id_ = str(row["결정례일련번호"]).strip()
            body = "\n".join(s for s in sentences if s)
            if not body or len(body) < 200:
                continue
            head = "\n".join(sentences[:30])
            cn_match = case_re.search(head)
            court_match = court_re.search(head)
            date_match = date_re.search(head)
            name_match = case_name_re.search(head)
            if not (cn_match and court_match and date_match):
                n_meta_short += 1
                continue
            cn = cn_match.group(1)
            court = court_match.group(1)
            decision_date = f"{int(date_match.group(1)):04d}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}"
            case_name = normalize_text(name_match.group(1)) if name_match else ""
            record_id = id_ or path.stem
            canonical = stable_canonical_id(out_source, record_id, cn, decision_date)
            row_out = {
                "canonical_id": canonical,
                "source_dataset": out_source,
                "source_path": f"{repo_id}::{path.relative_to(local_dir)}",
                "source_record_id": record_id,
                "source_kind": "csv",
                "title": case_name or cn,
                "case_number": cn,
                "court": court,
                "decision_date": decision_date,
                "case_name": case_name,
                "case_type": "결정례",
                "full_text": body,
            }
            append_staging(out_source, row_out)
            n_kept += 1
            if n_kept % 1000 == 0:
                print(f"  [lawdata1] kept={n_kept:,}/{n_total:,}  meta_short={n_meta_short:,}", flush=True)
        except Exception:
            continue
    print(f"[lawdata1] DONE total={n_total:,} kept={n_kept:,} meta_short={n_meta_short:,}")
    return n_kept


def collect_ducut91_judgments(out_source: str = "22_hf_ducut91_court_judgments") -> int:
    """ducut91/korean-court-judgments — 단일 CSV with case_content body."""
    from huggingface_hub import hf_hub_download

    repo_id = "ducut91/korean-court-judgments"
    print(f"[ducut91 judgments] downloading single CSV …", flush=True)
    p = Path(hf_hub_download(repo_id=repo_id, filename="court_judgments_standardized.csv", repo_type="dataset"))
    print(f"[ducut91 judgments] file = {p}", flush=True)

    staging_path(out_source).unlink(missing_ok=True)
    n_total = n_kept = 0
    started = time.time()
    with p.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            n_total += 1
            body = (row.get("case_content") or "").strip()
            if not body or len(body) < 80:
                continue
            cn = (row.get("case_number") or "").strip()
            decision_date = normalize_decision_date(row.get("decision_date"))
            court = (row.get("court_name") or "").strip()
            case_name = (row.get("case_name") or "").strip()
            case_type = (row.get("case_type") or "").strip()
            record_id = (row.get("case_id") or "").strip() or f"{cn}_{decision_date}"
            canonical = stable_canonical_id(out_source, record_id, cn, decision_date)
            row_out = {
                "canonical_id": canonical,
                "source_dataset": out_source,
                "source_path": f"{repo_id}::row-{record_id}",
                "source_record_id": record_id,
                "source_kind": "csv",
                "title": case_name or cn,
                "case_number": cn,
                "court": court,
                "decision_date": decision_date,
                "case_name": case_name,
                "case_type": case_type,
                "full_text": body,
            }
            append_staging(out_source, row_out)
            n_kept += 1
            if n_kept % 5000 == 0:
                print(f"  [ducut91 judgments] kept={n_kept:,}/{n_total:,}", flush=True)
    print(f"[ducut91 judgments] DONE total={n_total:,} kept={n_kept:,} elapsed={time.time()-started:.0f}s")
    return n_kept


def collect_ducut91_constitutional(out_source: str = "23_hf_ducut91_constitutional") -> int:
    """ducut91/korean-constitutional-court-decisions — 헌재 결정 단일 CSV."""
    from huggingface_hub import hf_hub_download

    repo_id = "ducut91/korean-constitutional-court-decisions"
    print(f"[ducut91 ccourt] downloading …", flush=True)
    p = Path(hf_hub_download(repo_id=repo_id, filename="korean_constitutional_court_decisions.csv", repo_type="dataset"))
    print(f"[ducut91 ccourt] file = {p}", flush=True)

    staging_path(out_source).unlink(missing_ok=True)
    n_total = n_kept = 0
    started = time.time()
    with p.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            n_total += 1
            body = (row.get("full_text") or "").strip()
            if not body or len(body) < 80:
                continue
            cn = (row.get("case_number") or "").strip()
            decision_date = normalize_decision_date(row.get("decision_date"))
            court = "헌법재판소"
            case_name = (row.get("case_name") or "").strip()
            case_type = (row.get("case_type") or "").strip()
            record_id = (row.get("case_id") or "").strip() or f"{cn}_{decision_date}"
            canonical = stable_canonical_id(out_source, record_id, cn, decision_date)
            row_out = {
                "canonical_id": canonical,
                "source_dataset": out_source,
                "source_path": f"{repo_id}::row-{record_id}",
                "source_record_id": record_id,
                "source_kind": "csv",
                "title": case_name or cn,
                "case_number": cn,
                "court": court,
                "decision_date": decision_date,
                "case_name": case_name,
                "case_type": case_type,
                "full_text": body,
            }
            append_staging(out_source, row_out)
            n_kept += 1
            if n_kept % 5000 == 0:
                print(f"  [ducut91 ccourt] kept={n_kept:,}/{n_total:,}", flush=True)
    print(f"[ducut91 ccourt] DONE total={n_total:,} kept={n_kept:,} elapsed={time.time()-started:.0f}s")
    return n_kept


def collect_joonhok_full(out_source: str = "24_hf_joonhok_full_precedents") -> int:
    """joonhok-exo-ai/korean_law_open_data_precedents — 법제처 국가법령정보센터
    판례 전체 (2023.6 기준) 85,830건. `전문` 컬럼이 판결문 풀텍스트.

    스키마:
      판례정보일련번호 (canonical id), 사건명, 사건번호, 선고일자, 선고,
      법원명, 사건종류명, 판결유형, 판시사항, 판결요지, 참조조문, 참조판례, 전문
    """
    from datasets import load_dataset

    repo_id = "joonhok-exo-ai/korean_law_open_data_precedents"
    print(f"[joonhok full] streaming {repo_id} …", flush=True)
    ds = load_dataset(repo_id, split="train", streaming=True)

    staging_path(out_source).unlink(missing_ok=True)
    n_total = n_kept = 0
    started = time.time()
    for row in ds:
        n_total += 1
        body = (row.get("전문") or "").strip()
        if not body or len(body) < 80:
            continue
        record_id = str(row.get("판례정보일련번호") or "").strip()
        case_number = (row.get("사건번호") or "").strip()
        decision_date = normalize_decision_date(row.get("선고일자"))
        court = (row.get("법원명") or "").strip()
        case_name = (row.get("사건명") or "").strip()
        case_type = (row.get("사건종류명") or "").strip()
        # `판시사항` + `판결요지` is rich pre-summarized content. Prepend before
        # 전문 so FTS5 indexing surfaces these high-value snippets early.
        prefix_parts: list[str] = []
        if (row.get("판시사항") or "").strip():
            prefix_parts.append(f"[판시사항]\n{row['판시사항'].strip()}")
        if (row.get("판결요지") or "").strip():
            prefix_parts.append(f"[판결요지]\n{row['판결요지'].strip()}")
        full_text = ("\n\n".join(prefix_parts) + "\n\n" + body) if prefix_parts else body
        canonical = stable_canonical_id(out_source, record_id, case_number, decision_date)
        row_out = {
            "canonical_id": canonical,
            "source_dataset": out_source,
            "source_path": f"{repo_id}::row-{record_id}",
            "source_record_id": record_id,
            "source_kind": "hf_dataset",
            "title": case_name or case_number,
            "case_number": case_number,
            "court": court,
            "decision_date": decision_date,
            "case_name": case_name,
            "case_type": case_type,
            "full_text": full_text,
        }
        append_staging(out_source, row_out)
        n_kept += 1
        if n_kept % 5000 == 0:
            print(f"  [joonhok full] kept={n_kept:,}/{n_total:,}", flush=True)
    print(f"[joonhok full] DONE total={n_total:,} kept={n_kept:,} elapsed={time.time()-started:.0f}s")
    return n_kept


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--dataset",
        choices=["lawdata4", "lawdata1", "ducut91_judgments", "ducut91_ccourt", "joonhok_full", "all"],
        required=True,
    )
    args = ap.parse_args()
    if args.dataset == "lawdata4":
        collect_lawdata4()
    elif args.dataset == "lawdata1":
        collect_lawdata1()
    elif args.dataset == "ducut91_judgments":
        collect_ducut91_judgments()
    elif args.dataset == "ducut91_ccourt":
        collect_ducut91_constitutional()
    elif args.dataset == "joonhok_full":
        collect_joonhok_full()
    elif args.dataset == "all":
        collect_ducut91_judgments()
        collect_ducut91_constitutional()
        collect_lawdata4()
        collect_lawdata1()
    return 0


if __name__ == "__main__":
    sys.exit(main())
