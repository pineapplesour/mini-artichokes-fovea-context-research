#!/usr/bin/env python3
"""Build a civil-judgment outcome-prediction benchmark from the precedent DB.

Motivation: exam benchmarks measure recall of settled answers; the product
capability the engine actually needs is *prediction* — given only what was
before the court (claims and established facts), forecast the outcome. A
judgment document is written toward its own conclusion, so the benchmark shows
the model only the claim (청구취지) and the fact-finding section (기초사실/
인정사실) and hides the holding (주문) and the court's reasoning (판단).

Deterministic, fail-closed construction:
  - modern (default >=2015) first-instance civil cases (가단/가합/가소);
  - the judgment must contain 주문 / 청구취지 / 이유 and a facts subsection;
  - counterclaims (반소), dismissals-without-prejudice (각하), settlements and
    ambiguous holdings are skipped entirely;
  - the gold label is derived from the 주문 by explicit textual rules into
    two classes: 인용됨 (any performance ordered or formative relief granted,
    i.e. the claim succeeded at least in part) versus 기각 (claim rejected
    outright). The full/partial grant boundary is legally noisy (interest
    trims count as partial), so v0 deliberately evaluates the binary outcome;
  - the facts text must not textually contain the holding sentence.

Output: public/private JSONL pairs in the unified benchmark shape
(responseFormat 'outcome_prediction'; answers are one of the two classes).
Grading is deterministic string-class comparison — no model grader. Sampling
is exactly class-balanced, so chance accuracy is 50%.
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

CLASSES = ("인용됨", "기각")


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def split_sections(full_text: str, *, require_claim: bool = True) -> dict[str, str] | None:
    text = str(full_text or "")
    heading = re.compile(
        r"(?m)^\s*(?:【\s*)?(주\s*문|청\s*구\s*취\s*지|이\s*유)(?:\s*】)?\s*$"
    )
    found: list[tuple[str, int, int]] = []
    for match in heading.finditer(text):
        name = re.sub(r"\s+", "", match.group(1))
        found.append((name, match.start(), match.end()))
    names = [name for name, _, _ in found]
    if "주문" not in names or "이유" not in names:
        return None
    if require_claim and "청구취지" not in names:
        return None
    if names.index("주문") > 1:
        return None
    sections: dict[str, str] = {}
    for i, (name, _, end) in enumerate(found):
        stop = found[i + 1][1] if i + 1 < len(found) else len(text)
        if name not in sections:
            sections[name] = text[end:stop].strip()
    return sections


FACTS_HEAD = re.compile(r"(?m)^\s*1\.\s*(기초\s*사실|인정\s*사실|인정\s*되는\s*사실)")
FACTS_HEAD_TAX = re.compile(
    r"(?m)^\s*1\.\s*(처분의?\s*경위|기초\s*사실|인정\s*사실|인정\s*되는\s*사실)"
)
NEXT_TOP = re.compile(r"(?m)^\s*2\.\s")


def extract_facts(reason_text: str, *, head: re.Pattern = FACTS_HEAD) -> str | None:
    match = head.search(reason_text)
    if not match:
        return None
    rest = reason_text[match.start():]
    nxt = NEXT_TOP.search(rest)
    if not nxt:
        return None
    facts = rest[: nxt.start()].strip()
    return facts if len(facts) >= 300 else None


# Korean holdings put the parties in either order:
#   "피고는 원고에게 … 지급하라"           (defendant-first)
#   "원고에게, 가. 피고 1은 … 지급하고"     (plaintiff-first, itemised per defendant)
# The second form appears whenever there are multiple defendants or itemised
# amounts, and missing it silently mislabels a partial grant as a dismissal
# (measured: 4 of 60 dismissal labels in v1 were actually grants).
_ORDER_VERB = r"(지급하라|지급하고|배상하라|반환하라|인도하라|명도하라|말소[\s\S]{0,30}절차를 이행하라|이행하라)"
ORDER_PAY = re.compile(
    r"(?:피고(?:들)?[\s\S]{0,160}?원고(?:들)?|원고(?:들)?에게[\s\S]{0,200}?피고(?:들)?)"
    r"[\s\S]{0,400}?" + _ORDER_VERB
)
GRANT_FORMATIVE = re.compile(
    r"(취소한다|무효로 한다|무효임을 확인한다|존재하지 아니함을 확인한다|"
    r"임을 확인한다|말소하라|허가한다)"
)
DISMISS = re.compile(r"청구(?:를|는)?\s*(?:모두\s*)?(?:각\s*)?기각한다")


def label_from_holding(holding: str) -> str | None:
    text = normalize(holding)
    if any(bad in text for bad in ("반소", "각하", "화해", "조정", "소를 취하", "항소", "상고", "파기", "환송")):
        return None
    granted = bool(ORDER_PAY.search(text)) or bool(GRANT_FORMATIVE.search(text))
    dismissed = bool(DISMISS.search(text))
    if granted:
        return "인용됨"
    if dismissed:
        return "기각"
    return None


ARG_HEAD = re.compile(
    r"(?m)^\s*(?:\d+|[가나다라])?\.?\s*(당사자(?:들)?의?\s*주장(?:\s*요지)?|원고(?:의)?\s*주장|주장\s*(?:및|과)|당사자의 주장 요지)"
)
JUDGMENT_HEAD = re.compile(r"(?m)^\s*(?:\d+|[가나다라])?\.?\s*(판\s*단|살피건대|본다|검토)")


def extract_arguments(reason_text: str) -> str | None:
    """Extract the parties'-contentions section, stopping before any judicial
    assessment so no conclusion language leaks."""
    match = ARG_HEAD.search(reason_text)
    if not match:
        return None
    rest = reason_text[match.start():]
    stop = JUDGMENT_HEAD.search(rest, 10)
    body = rest[: stop.start()] if stop else rest
    body = body.strip()
    if len(body) < 150 or len(body) > 6000:
        return None
    if re.search(r"(이유 없다|이유 있다|기각한다|인용한다|인정된다고 봄이 상당하다)", body):
        return None
    return body


PROMPT_TEMPLATE_ARGS = """다음은 대한민국 제1심 민사사건의 청구취지, 기초사실, 그리고 양측 당사자의 주장입니다.
법원의 최종 결론(주문)과 판단 부분은 제거되어 있습니다. 오직 아래 내용만 근거로,
이 사건 본소 청구에 대한 법원의 결론을 예측하십시오.

[청구취지]
{claim}

[기초사실]
{facts}

[당사자 주장]
{arguments}

다음 두 가지 중 정확히 하나로 답하십시오.
- 인용됨: 청구가 전부 또는 일부라도 받아들여짐
- 기각: 청구가 전부 배척됨
첫 줄에 결론 한 단어(인용됨 또는 기각)만 쓰고, 둘째 줄에 `확신도: 0.xx`, 셋째 줄부터 두세 문장으로 핵심 근거를 쓰십시오."""

PROMPT_TEMPLATE_TAX = """다음은 대한민국 조세 행정소송 제1심 사건의 처분 경위와 양측 당사자의 주장입니다.
법원의 최종 결론(주문)과 판단 부분은 제거되어 있습니다. 오직 아래 내용만 근거로,
납세자(원고)가 다투는 이 사건 부과처분에 대한 법원의 결론을 예측하십시오.

[처분의 경위]
{facts}

[당사자 주장]
{arguments}

다음 두 가지 중 정확히 하나로 답하십시오.
- 인용됨: 처분이 전부 또는 일부라도 취소됨 (납세자 승소)
- 기각: 처분이 그대로 유지됨 (과세관청 승소)
첫 줄에 결론 한 단어(인용됨 또는 기각)만 쓰고, 둘째 줄에 `확신도: 0.xx`, 셋째 줄부터 두세 문장으로 핵심 근거를 쓰십시오."""

PROMPT_TEMPLATE = """다음은 대한민국 제1심 민사사건에서 법원이 확정한 청구취지와 기초사실입니다.
법원의 최종 결론(주문)과 판단 부분은 제거되어 있습니다. 오직 아래 내용만 근거로,
이 사건 본소 청구에 대한 법원의 결론을 예측하십시오.

[청구취지]
{claim}

[기초사실]
{facts}

다음 두 가지 중 정확히 하나로 답하십시오.
- 인용됨: 청구가 전부 또는 일부라도 받아들여짐
- 기각: 청구가 전부 배척됨
첫 줄에 결론 한 단어(인용됨 또는 기각)만 쓰고, 둘째 줄부터 두세 문장으로 핵심 근거를 쓰십시오."""


TAX_NAME_SQL = " OR ".join(
    f"case_name LIKE '%{word}%'"
    for word in (
        "부가가치세", "종합소득세", "소득세", "법인세", "양도소득세", "상속세",
        "증여세", "취득세", "재산세", "종합부동산세", "관세", "지방세", "과세",
    )
)


def build(db_path: Path, *, per_class: int, min_year: str, seed_salt: str,
          with_arguments: bool = False, domain: str = "civil") -> tuple[list[dict], list[dict], Counter]:
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    if domain == "tax":
        # Administrative first-instance dockets (구합/구단) whose caption names a
        # tax assessment/correction dispute, or whose body names a tax authority
        # as respondent. Both conditions are outcome-independent.
        case_sql = (
            "(case_number LIKE '%구합%' OR case_number LIKE '%구단%') AND (("
            f"{TAX_NAME_SQL}"
            ") OR case_name LIKE '%부과처분%' OR case_name LIKE '%경정%' OR case_name LIKE '%세액%')"
        )
    else:
        case_sql = (
            "(case_number LIKE '%가단%' OR case_number LIKE '%가합%' OR case_number LIKE '%가소%')"
        )
    rows = connection.execute(
        f"""
        SELECT canonical_id, court, case_number, decision_date, case_name, full_text
        FROM precedents
        WHERE {case_sql}
          AND decision_date >= ?
          AND length(full_text) BETWEEN 3000 AND 30000
        """,
        (min_year,),
    ).fetchall()
    stats: Counter = Counter()
    candidates: dict[str, list[dict]] = {label: [] for label in CLASSES}
    seen_cases: set[str] = set()
    for row in rows:
        stats["scanned"] += 1
        dedupe = f"{row['court']}|{row['case_number']}"
        if dedupe in seen_cases:
            stats["duplicate_case"] += 1
            continue
        sections = split_sections(row["full_text"], require_claim=(domain != "tax"))
        if not sections:
            stats["no_sections"] += 1
            continue
        label = label_from_holding(sections["주문"])
        if label is None:
            stats["no_label"] += 1
            continue
        facts = extract_facts(sections["이유"], head=FACTS_HEAD_TAX if domain == "tax" else FACTS_HEAD)
        if facts is None:
            stats["no_facts"] += 1
            continue
        if domain == "tax":
            # The tax arm deliberately drops 청구취지: it is frequently written as
            # "주문과 같다" (a verbatim pointer to the holding) and its very
            # presence correlates with a full grant. The disposition history
            # already states what assessment is being challenged.
            claim = ""
            if len(facts) > 8000:
                stats["size_filtered"] += 1
                continue
        else:
            claim = sections["청구취지"].strip()
            if not (50 <= len(claim) <= 2000) or len(facts) > 8000:
                stats["size_filtered"] += 1
                continue
        arguments = extract_arguments(sections["이유"]) if with_arguments else None
        if with_arguments and arguments is None:
            stats["no_arguments"] += 1
            continue
        holding_norm = normalize(sections["주문"])[:120]
        if holding_norm and holding_norm[:60] in normalize(facts):
            stats["holding_leak"] += 1
            continue
        seen_cases.add(dedupe)
        digest = hashlib.sha256(f"{seed_salt}|{dedupe}".encode()).hexdigest()
        candidates[label].append(
            {
                "sortKey": digest,
                "caseRef": dedupe,
                "canonicalId": row["canonical_id"],
                "decisionDate": row["decision_date"],
                "claim": claim,
                "arguments": arguments,
                "facts": facts,
                "holding": sections["주문"].strip(),
                "label": label,
            }
        )
        stats[f"label_{label}"] += 1
    connection.close()

    public: list[dict] = []
    private: list[dict] = []
    for label in CLASSES:
        pool = sorted(candidates[label], key=lambda item: item["sortKey"])[:per_class]
        if len(pool) < per_class:
            raise SystemExit(f"not enough cases for class {label}: {len(pool)} < {per_class}")
        domain_word = "조세 행정사건" if domain == "tax" else "민사사건"
        for item in pool:
            case_id = f"outcome-{domain}-{item['sortKey'][:12]}"
            public.append(
                {
                    "id": case_id,
                    "suite": "exam",
                    "benchmarkId": f"outcome.{domain}_first_instance.v0",
                    "responseFormat": "outcome_prediction",
                    "language": "ko",
                    "prompt": (
                        PROMPT_TEMPLATE_TAX.format(facts=item["facts"], arguments=item["arguments"])
                        if domain == "tax"
                        else (
                            PROMPT_TEMPLATE_ARGS.format(
                                claim=item["claim"], facts=item["facts"], arguments=item["arguments"]
                            )
                            if item.get("arguments")
                            else PROMPT_TEMPLATE.format(claim=item["claim"], facts=item["facts"])
                        )
                    ),
                }
            )
            private.append(
                {
                    "caseId": case_id,
                    "label": item["label"],
                    "caseRef": item["caseRef"],
                    "canonicalId": item["canonicalId"],
                    "decisionDate": item["decisionDate"],
                    "holding": item["holding"],
                }
            )
    order = sorted(range(len(public)), key=lambda i: public[i]["id"])
    public = [public[i] for i in order]
    private = [private[i] for i in order]
    return public, private, stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--per-class", type=int, default=60)
    parser.add_argument("--min-year", default="2015")
    parser.add_argument("--seed-salt", default="outcome-v0")
    parser.add_argument("--with-arguments", action="store_true")
    parser.add_argument("--domain", choices=["civil", "tax"], default="civil")
    parser.add_argument("--public-out", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    args = parser.parse_args()
    public, private, stats = build(
        args.db, per_class=args.per_class, min_year=args.min_year,
        seed_salt=args.seed_salt, with_arguments=args.with_arguments, domain=args.domain
    )
    for path, rows in ((args.public_out, public), (args.private_out, private)):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"rows": len(public), "stats": dict(stats)}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
