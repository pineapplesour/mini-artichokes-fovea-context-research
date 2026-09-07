#!/usr/bin/env python3
"""Build a civil-complaint drafting benchmark from real loan-case fact patterns.

The practical capability: given the facts a client can state, produce a filing
document (소장) for a money claim. Inputs are the fact-finding sections of
real 대여금/양수금/구상금 first-instance judgments (holding and reasoning
hidden). The task asks for a complete 소장 draft.

v0 scoring is a deterministic completeness checklist (no model grader):
required structural elements of a Korean civil complaint that a court would
demand under 민사소송법 제249조 practice:
  1. 당사자 표시 (원고/피고 지칭)
  2. '청구취지' 섹션과 지급 청구 문장
  3. 지연손해금/이자 구문
  4. '청구원인' 섹션
  5. 입증방법 또는 첨부서류 섹션
  6. 관할/법원 표시
  7. 금액 일치: 청구취지의 주요 금액이 사실관계에 실제로 등장
Each item is one point; the score is points/7 averaged over cases.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.build_outcome_prediction_benchmark import extract_facts, split_sections

PROMPT_TEMPLATE = """당신은 원고를 대리하는 변호사입니다. 아래는 의뢰인 사건의 사실관계입니다.
이 사실관계에 근거하여 대한민국 전자소송에 제출할 수 있는 완결된 민사 소장을 작성하십시오.

[사실관계]
{facts}

요구사항: 실제 소장의 구조를 갖출 것 — 당사자 표시, 청구취지(구체적 금액과
지연손해금 포함), 청구원인(사실관계를 법적 요건에 맞게 구성), 입증방법,
첨부서류, 관할법원 표시. 사실관계에 없는 사실을 지어내지 말 것. 이름 등
알 수 없는 정보는 '원고', '피고', 'OOO' 표기를 유지할 것."""


def build(db_path: Path, *, count: int, min_year: str, seed_salt: str) -> tuple[list[dict], list[dict], Counter]:
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT canonical_id, court, case_number, decision_date, case_name, full_text
        FROM precedents
        WHERE (case_number LIKE '%가단%' OR case_number LIKE '%가합%' OR case_number LIKE '%가소%')
          AND (case_name LIKE '%대여금%' OR case_name LIKE '%양수금%' OR case_name LIKE '%구상금%')
          AND decision_date >= ?
          AND length(full_text) BETWEEN 3000 AND 30000
        """,
        (min_year,),
    ).fetchall()
    stats: Counter = Counter()
    candidates: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        stats["scanned"] += 1
        dedupe = f"{row['court']}|{row['case_number']}"
        if dedupe in seen:
            continue
        sections = split_sections(row["full_text"])
        if not sections:
            stats["no_sections"] += 1
            continue
        facts = extract_facts(sections["이유"])
        if facts is None or len(facts) > 6000:
            stats["no_facts"] += 1
            continue
        amounts = re.findall(r"([0-9,]{7,})\s*원", facts)
        if not amounts:
            stats["no_amount"] += 1
            continue
        seen.add(dedupe)
        digest = hashlib.sha256(f"{seed_salt}|{dedupe}".encode()).hexdigest()
        candidates.append(
            {
                "sortKey": digest,
                "caseRef": dedupe,
                "canonicalId": row["canonical_id"],
                "caseName": row["case_name"],
                "facts": facts,
                "amounts": sorted(set(amounts), key=len, reverse=True)[:5],
            }
        )
        stats["eligible"] += 1
    connection.close()
    chosen = sorted(candidates, key=lambda item: item["sortKey"])[:count]
    if len(chosen) < count:
        raise SystemExit(f"not enough cases: {len(chosen)} < {count}")
    public: list[dict] = []
    private: list[dict] = []
    for item in chosen:
        case_id = f"drafting-loan-{item['sortKey'][:12]}"
        public.append(
            {
                "id": case_id,
                "suite": "exam",
                "benchmarkId": "drafting.civil_complaint.v0",
                "responseFormat": "document_draft",
                "language": "ko",
                "prompt": PROMPT_TEMPLATE.format(facts=item["facts"]),
            }
        )
        private.append(
            {
                "caseId": case_id,
                "caseRef": item["caseRef"],
                "canonicalId": item["canonicalId"],
                "caseName": item["caseName"],
                "factAmounts": item["amounts"],
            }
        )
    order = sorted(range(len(public)), key=lambda i: public[i]["id"])
    return [public[i] for i in order], [private[i] for i in order], stats


CHECKS = (
    ("parties", lambda t, p: ("원고" in t and "피고" in t)),
    ("relief_section", lambda t, p: bool(re.search(r"청\s*구\s*취\s*지", t))),
    ("payment_demand", lambda t, p: bool(re.search(r"(지급하라|지급할 것을|지급을 구합니다)", t))),
    ("interest_clause", lambda t, p: bool(re.search(r"(지연손해금|연\s*\d{1,2}\s*%|이자)", t))),
    ("cause_section", lambda t, p: bool(re.search(r"청\s*구\s*원\s*인", t))),
    ("evidence_section", lambda t, p: bool(re.search(r"(입\s*증\s*방\s*법|첨\s*부\s*서\s*류|갑\s*제?\s*\d*\s*호증)", t))),
    ("court_line", lambda t, p: bool(re.search(r"(지방법원|법원\s*귀중)", t))),
    ("amount_grounded", lambda t, p: any(a in t.replace(" ", "") for a in (x.replace(" ", "") for x in p.get("factAmounts", [])))),
)


def score_document(text: str, private_row: dict) -> dict:
    results = {name: bool(check(text or "", private_row)) for name, check in CHECKS}
    return {"points": sum(results.values()), "max": len(CHECKS), "checks": results}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["build", "score"])
    parser.add_argument("--db", type=Path)
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--min-year", default="2005")
    parser.add_argument("--seed-salt", default="drafting-v0")
    parser.add_argument("--public-out", type=Path)
    parser.add_argument("--private-out", type=Path)
    parser.add_argument("--answers", type=Path)
    parser.add_argument("--private", type=Path)
    args = parser.parse_args()
    if args.command == "build":
        public, private, stats = build(args.db, count=args.count, min_year=args.min_year, seed_salt=args.seed_salt)
        for path, rows in ((args.public_out, public), (args.private_out, private)):
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as stream:
                for row in rows:
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(json.dumps({"rows": len(public), "stats": dict(stats)}, ensure_ascii=False))
        return 0
    answers = {row["id"]: str(row.get("finalAnswer", "")) for row in
               (json.loads(l) for l in args.answers.read_text(encoding="utf-8").splitlines() if l.strip())}
    gold = {row["caseId"]: row for row in
            (json.loads(l) for l in args.private.read_text(encoding="utf-8").splitlines() if l.strip())}
    per_check = Counter()
    total_points = 0
    for case_id, private_row in gold.items():
        result = score_document(answers.get(case_id, ""), private_row)
        total_points += result["points"]
        for name, passed in result["checks"].items():
            per_check[name] += int(passed)
    n = len(gold)
    print(json.dumps({
        "cases": n,
        "meanPoints": round(total_points / n, 3) if n else 0,
        "maxPoints": len(CHECKS),
        "perCheckPassCounts": dict(per_check),
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
