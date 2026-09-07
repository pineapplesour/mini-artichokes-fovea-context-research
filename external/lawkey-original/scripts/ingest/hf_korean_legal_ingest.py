"""HuggingFace 한국 법률 데이터셋 일괄 ingest.

원칙:
- 본문이 비어 있는 row는 버린다.
- 식별 메타(case_number/court/decision_date/case_name)는 데이터셋의 명시 컬럼만 사용.
  본문 스캔 추론은 절대 사용하지 않는다 — 그게 lawkey 기존 DB 의 fabricated
  metadata 버그의 원인이었다.
- 기존 DB와 dedupe 는 text_hash(=sha1(full_text)) 우선 + (case_number,
  decision_date) 보조.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

DB_PATH_DEFAULT = "/srv/lawkey/work16/저장파일/unified_precedent_db_2026-04-10_run3/precedents.sqlite3"


def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8", errors="replace")).hexdigest()


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_case_number(doc_id: str) -> tuple[str, str]:
    """`부산지방법원-2016가단320650` → (`2016가단320650`, `부산지방법원`).
    `대법원-2025-두-34754` 처럼 분리된 경우도 처리.
    """
    raw = (doc_id or "").strip()
    if not raw:
        return "", ""
    parts = raw.split("-")
    court = parts[0]
    rest = "".join(parts[1:])
    return rest, court


def parse_announce_date(value: str) -> str:
    if not value:
        return ""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(value))
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""


def lawdata4_iter(root: Path):
    """Yield (info, full_text) per JSON file."""
    for path in root.rglob("*.json"):
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        info = d.get("info") or {}
        sentences = (d.get("taskinfo") or {}).get("sentences") or []
        body = "\n".join(str(s).strip() for s in sentences if isinstance(s, str) and s.strip())
        if not body or len(body) < 80:
            continue
        cn, court = parse_case_number(str(info.get("doc_id") or ""))
        case_name = normalize_space(info.get("casenames"))
        decision_date = parse_announce_date(info.get("announce_date"))
        case_type_raw = str(info.get("casetype") or "")
        case_type = {"civil": "민사", "criminal": "형사", "admin": "행정"}.get(case_type_raw, case_type_raw)
        normalized_court = normalize_space(info.get("normalized_court")) or court
        yield {
            "case_number": cn,
            "court": normalized_court,
            "decision_date": decision_date,
            "case_name": case_name,
            "case_type": case_type,
            "title": case_name or cn,
            "full_text": body,
            "doc_id": str(info.get("doc_id") or ""),
            "source_record_id": path.stem,
            "source_path": str(path),
        }


def lawdata1_iter(root: Path):
    """Yield (info, full_text) per CSV file (each file is one decision).

    CSV columns: 결정례일련번호,구분,문장번호,내용
    """
    for path in root.rglob("*.csv"):
        try:
            sentences: list[str] = []
            id_ = ""
            with path.open("r", encoding="utf-8", errors="replace") as f:
                rows = list(csv.DictReader(f))
            for row in rows:
                if row.get("구분") in ("전문", "본문") and row.get("내용"):
                    sentences.append(str(row["내용"]).strip())
                if not id_ and row.get("결정례일련번호"):
                    id_ = str(row["결정례일련번호"]).strip()
            body = "\n".join(s for s in sentences if s)
            if not body or len(body) < 80:
                continue
            cn = ""
            court = ""
            case_name = ""
            decision_date = ""
            for s in sentences[:30]:
                if not cn:
                    m = re.search(r"\b(\d{2,4}[가-힣]+\d+)\b", s)
                    if m:
                        cn = m.group(1)
                if not court:
                    m = re.search(r"(헌법재판소|대법원|[가-힣]{2,8}(?:행정|고등|지방)법원)", s)
                    if m:
                        court = m.group(1)
                if not decision_date:
                    m = re.search(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.", s)
                    if m:
                        decision_date = f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
            if not (cn and court and case_name):
                continue
            yield {
                "case_number": cn,
                "court": court,
                "decision_date": decision_date,
                "case_name": case_name,
                "case_type": "결정례",
                "title": case_name or cn,
                "full_text": body,
                "doc_id": id_,
                "source_record_id": id_ or path.stem,
                "source_path": str(path),
            }
        except Exception:
            continue


def load_existing_dedupe_keys(db_path: str) -> tuple[set[str], set[str]]:
    con = sqlite3.connect(db_path, timeout=120)
    cur = con.cursor()
    text_hashes: set[str] = set()
    cn_date: set[str] = set()
    cur.execute("SELECT text_hash FROM precedents")
    for (h,) in cur.fetchall():
        if h:
            text_hashes.add(h)
    cur.execute("SELECT case_number, decision_date FROM precedents")
    for cn, dd in cur.fetchall():
        if cn and dd:
            cn_date.add(f"{cn.strip()}|{dd.strip()}")
    con.close()
    return text_hashes, cn_date


def insert_records(db_path: str, source_dataset: str, records, *, batch: int = 500) -> dict:
    text_hashes, cn_date_keys = load_existing_dedupe_keys(db_path)
    print(f"[dedupe] existing text_hashes={len(text_hashes):,}, (cn,date)={len(cn_date_keys):,}", flush=True)

    con = sqlite3.connect(db_path, timeout=120)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    cur = con.cursor()

    cur.execute("PRAGMA table_info(precedents)")
    cols = [r[1] for r in cur.fetchall()]
    insert_cols = [c for c in cols if c != "rowid"]
    placeholders = ",".join(["?"] * len(insert_cols))
    insert_sql = f"INSERT OR IGNORE INTO precedents ({','.join(insert_cols)}) VALUES ({placeholders})"

    pending: list[tuple] = []
    stats = {"seen": 0, "skip_empty": 0, "skip_dup_hash": 0, "skip_dup_cnd": 0, "ingested": 0, "error": 0}
    for r in records:
        stats["seen"] += 1
        body = r.get("full_text") or ""
        if not body.strip():
            stats["skip_empty"] += 1
            continue
        th = sha1(body)
        if th in text_hashes:
            stats["skip_dup_hash"] += 1
            continue
        cn = (r.get("case_number") or "").strip()
        dd = (r.get("decision_date") or "").strip()
        if cn and dd:
            key = f"{cn}|{dd}"
            if key in cn_date_keys:
                stats["skip_dup_cnd"] += 1
                continue
            cn_date_keys.add(key)
        text_hashes.add(th)
        canonical_id = "prd-" + sha1(f"{source_dataset}|{r.get('doc_id') or r.get('source_path')}|{th}")[:16]
        dedupe_key_primary = f"{r.get('court')}|{cn}|{dd}".strip("|")
        dedupe_key_fallback = f"{r.get('source_record_id')}|{th[:16]}"
        row_dict = {
            "canonical_id": canonical_id,
            "dedupe_key": dedupe_key_primary or dedupe_key_fallback,
            "source_dataset": source_dataset,
            "source_path": r.get("source_path") or "",
            "source_record_id": r.get("source_record_id") or "",
            "source_kind": "huggingface",
            "title": r.get("title") or "",
            "case_number": cn,
            "court": r.get("court") or "",
            "decision_date": dd,
            "case_name": r.get("case_name") or "",
            "case_type": r.get("case_type") or "",
            "full_text": body,
            "text_hash": th,
            "dedupe_key_primary": dedupe_key_primary or None,
            "dedupe_key_fallback": dedupe_key_fallback,
            "split_group_id": None,
            "split_index": None,
            "split_reason": None,
            "validation_flags": json.dumps(["explicit_metadata"], ensure_ascii=False),
        }
        try:
            pending.append(tuple(row_dict.get(c) for c in insert_cols))
        except Exception:
            stats["error"] += 1
            continue
        if len(pending) >= batch:
            with con:
                cur.executemany(insert_sql, pending)
                stats["ingested"] += len(pending)
            pending = []
            if stats["seen"] % 5000 == 0:
                print(f"[progress] seen={stats['seen']:,} ingested={stats['ingested']:,} dup_hash={stats['skip_dup_hash']:,} dup_cnd={stats['skip_dup_cnd']:,} empty={stats['skip_empty']:,}", flush=True)
    if pending:
        with con:
            cur.executemany(insert_sql, pending)
            stats["ingested"] += len(pending)
    con.close()
    return stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["lawdata4", "lawdata1"], required=True)
    ap.add_argument("--root", required=True, help="local snapshot dir")
    ap.add_argument("--db", default=DB_PATH_DEFAULT)
    ap.add_argument("--source-dataset", default=None)
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists():
        print(f"ERROR: {root} not found", file=sys.stderr)
        return 2

    iter_map = {"lawdata4": lawdata4_iter, "lawdata1": lawdata1_iter}
    iterator = iter_map[args.dataset](root)
    label = args.source_dataset or {"lawdata4": "20_hf_rootpye_lawdata4_pansol_summary", "lawdata1": "21_hf_rootpye_lawdata1_decision"}[args.dataset]

    started = time.time()
    stats = insert_records(args.db, label, iterator)
    elapsed = time.time() - started
    print(f"[done] dataset={args.dataset} source_dataset={label} elapsed={elapsed:.1f}s stats={stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
