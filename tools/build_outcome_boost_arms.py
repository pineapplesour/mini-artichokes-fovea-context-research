#!/usr/bin/env python3
"""Build accuracy-boost arms for the Korean outcome-prediction benchmark.

Both arms reuse the SAME 112-row subset that passed the v1n gates, so every
comparison stays paired against v1 (72.3%) and v1n (71.4%).

Arm `issues` — law-bench issue-decomposition protocol (their largest lift,
BA 0.775→0.865 on the Supreme-Court task): the model must identify the 2-4
dispositive issues, judge each independently from facts+arguments, and derive
the conclusion from the per-issue judgments.

Arm `refs` — retrieval augmentation from the 315k-precedent DB using the
deterministic question-ladder search. Leakage gates (fail-closed, per
candidate):
  - candidate rowid/canonical_id != target case;
  - candidate case_number != target case_number, and candidate text must not
    cite the target case_number (an appellate judgment OF this case would
    contain the first-instance outcome);
  - near-duplicate screen: none of 6 sampled 60-char windows of the target
    facts may appear verbatim in the candidate text;
  - candidate must expose a 주문/판단 snippet to be useful.
The prompt lists up to 3 surviving references with their actual outcomes,
clearly labeled as OTHER cases.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from tools.reference_search import ladder_search, MAIN_DB  # noqa: E402
from tools.build_outcome_prediction_benchmark import (  # noqa: E402
    label_from_holding,
    split_sections,
)

BENCH = REPO_ROOT / "benchmarks" / "outcome_prediction"

TAIL_RE = re.compile(r"다음 두 가지 중 정확히 하나로 답하십시오\.[\s\S]*$")

ISSUES_TAIL = """판단 절차 (반드시 이 순서로 분석하십시오):
1. 법원이 반드시 판단해야 할 결정적 쟁점을 2-4개 식별하십시오 (예: 의무·권리의 존부, 다툼 있는 사실의 증명 여부, 항변·소멸시효의 성립 여부, 손해액).
2. 각 쟁점을 기초사실과 양측 주장에 비추어 독립적으로 판단하고, 어느 쪽에 유리한지 정하십시오.
3. 처분적(dispositive) 쟁점 하나라도 원고에게 결정적으로 불리하면 청구 전부가 배척됨을 유의하며, 쟁점별 판단으로부터 전체 결론을 도출하십시오.

다음 두 가지 중 정확히 하나로 답하십시오.
- 인용됨: 청구가 전부 또는 일부라도 받아들여짐
- 기각: 청구가 전부 배척됨
첫 줄에 결론 한 단어(인용됨 또는 기각)만 쓰고, 둘째 줄에 `확신도: 0.xx`, 셋째 줄부터 쟁점별 판단을 한 줄씩 `쟁점: <요지> → <원고/피고> 유리` 형식으로 쓰십시오."""

REFS_HEADER = """[유사 1심 사건 검색 결과]
아래는 판례 데이터베이스에서 검색된, 이 사건과 유사한 쟁점을 다룬 **다른** 제1심 민사사건들과
그 실제 결론입니다 (본 사건이 아니며, 그대로 따라야 하는 것도 아닙니다). 유사 분쟁에서 법원이
실제로 어느 쪽 손을 들어주었는지의 경향으로만 참고하십시오:
"""

FIRST_INSTANCE = re.compile(r"\d{2,4}\s*(가단|가합|가소)")


def facts_and_claim(prompt: str) -> tuple[str, str]:
    claim = re.search(r"\[청구취지\]\n(.*?)\n\n\[", prompt, re.S)
    facts = re.search(r"\[기초사실\]\n(.*?)\n\n\[", prompt, re.S) or re.search(
        r"\[기초사실\]\n(.*?)\n\n다음 두 가지", prompt, re.S
    )
    return (claim.group(1).strip() if claim else ""), (facts.group(1).strip() if facts else "")


def sample_windows(text: str, count: int = 6, width: int = 60) -> list[str]:
    clean = re.sub(r"\s+", " ", text)
    if len(clean) <= width:
        return [clean]
    step = max(1, (len(clean) - width) // max(1, count - 1))
    return [clean[i : i + width] for i in range(0, len(clean) - width + 1, step)][:count]


def outcome_snippet(full_text: str) -> str | None:
    m = re.search(r"(?m)^\s*(?:【\s*)?주\s*문(?:\s*】)?\s*$", full_text)
    if not m:
        m = re.search(r"주\s*문", full_text[:3000])
        if not m:
            return None
    seg = re.sub(r"\s+", " ", full_text[m.end() : m.end() + 400]).strip()
    return seg[:220] if len(seg) >= 20 else None


def build_refs_block(prompt: str, target_case_number: str, target_canonical: str) -> tuple[str, int]:
    """Retrieve up to 3 comparable FIRST-INSTANCE civil judgments and state their
    deterministic outcome label.

    Restricting to 가단/가합/가소 matters: an appellate or Supreme Court 주문
    ("원심판결을 파기하고 환송한다") says nothing about whether a claim was
    granted, so higher-court hits are noise for this task. The reference's
    outcome is derived with the SAME labeller that builds the benchmark, so a
    reference either yields 인용됨/기각 or is dropped — never a raw holding
    string the model has to interpret.
    """
    claim, facts = facts_and_claim(prompt)
    query = (claim + " " + facts[:400]).strip()
    windows = sample_windows(facts)
    main_db = sqlite3.connect(f"file:{MAIN_DB}?mode=ro", uri=True)
    picked = []
    # push the first-instance requirement INTO the search, not after it: the
    # unrestricted ladder returns mostly appellate/Supreme hits, so post-filtering
    # left 18 of 30 cases with no reference at all.
    first_instance_sql = ("d.case_number LIKE '%가단%' OR d.case_number LIKE '%가합%' "
                          "OR d.case_number LIKE '%가소%'")
    for score, row, combo in ladder_search(query, limit=40, case_filter=first_instance_sql):
        rowid, canonical_id, court, case_number, date, title, _ = row
        if canonical_id == target_canonical:
            continue
        if not case_number or not FIRST_INSTANCE.search(case_number):
            continue
        if target_case_number and case_number.strip() == target_case_number:
            continue
        got = main_db.execute("SELECT full_text FROM precedents WHERE rowid=?", (rowid,)).fetchone()
        if not got or not got[0]:
            continue
        body = got[0]
        norm = re.sub(r"\s+", " ", body)
        if target_case_number and target_case_number in norm:
            continue
        if any(w in norm for w in windows):
            continue
        sections = split_sections(body)
        if not sections:
            continue
        outcome = label_from_holding(sections["주문"])
        if outcome is None:
            continue
        gist = re.sub(r"\s+", " ", (title or "") + " " + sections["주문"])[:120]
        picked.append((court or "?", case_number, date or "?", outcome, gist))
        if len(picked) == 3:
            break
    main_db.close()
    if not picked:
        return "", 0
    lines = [REFS_HEADER]
    for i, (court, cno, date, outcome, gist) in enumerate(picked, 1):
        lines.append(f"{i}. {court} {cno} ({date}) — 실제 결론: **{outcome}**")
        lines.append(f"   사건 개요: {gist}")
    granted = sum(1 for item in picked if item[3] == "인용됨")
    lines.append(f"(검색된 {len(picked)}건 중 인용 {granted}건 / 기각 {len(picked) - granted}건)")
    return "\n".join(lines) + "\n\n", len(picked)



RULES_HEADER = """[유사 사건에서 법원이 적용한 법리]
아래는 판례 데이터베이스에서 검색된, 유사한 쟁점의 제1심 판결들이 적시한 **법리 문장**입니다.
개별 사건의 결론은 의도적으로 제외했습니다 (다른 사건의 승패는 이 사건의 결론과 무관하며,
결과만 보여주면 잘못된 기준점이 되기 때문입니다). 적용 법리만 참고하십시오:
"""

# A rule sentence states a general legal proposition; a case-specific sentence
# names the parties or this-case demonstratives. The filter below keeps the
# former and drops the latter, so the block cannot leak another case's outcome.
RULE_SENT = re.compile(
    r"[^.]{25,300}?(?:라고 할 것이다|라 할 것이다|봄이 상당하다|보아야 한다|"
    r"해석함이 타당하다|하여야 한다|할 수 있다고 보아야|법리|민법 제\d+조|"
    r"상법 제\d+조|민사소송법 제\d+조)[^.]{0,120}\."
)
CASE_SPECIFIC = re.compile(r"(원고|피고|이 사건|위 인정사실|갑 제|을 제|소외)")


def rule_sentences(full_text: str, limit: int = 3) -> list[str]:
    sections = split_sections(full_text)
    body = sections["이유"] if sections else full_text
    body = re.sub(r"\s+", " ", body)
    picked: list[str] = []
    for match in RULE_SENT.finditer(body):
        sentence = match.group(0).strip()
        if CASE_SPECIFIC.search(sentence):
            continue
        if any(sentence[:40] == existing[:40] for existing in picked):
            continue
        picked.append(sentence)
        if len(picked) >= limit:
            break
    return picked


def build_rules_block(prompt: str, target_case_number: str, target_canonical: str) -> tuple[str, int]:
    """Retrieve the RULES other courts applied, never their outcomes.

    Measured motivation: an outcome-carrying reference block dropped accuracy
    from 80.0% to 73.3%, because the retrieved 주문 for a dismissal is content
    free ("원고의 청구를 기각한다") while still anchoring the model — it
    followed the reference majority 67% of the time and that majority was only
    67% correct. Rules carry the transferable part of a precedent; outcomes do
    not.
    """
    claim, facts = facts_and_claim(prompt)
    query = (claim + " " + facts[:400]).strip()
    windows = sample_windows(facts)
    first_instance_sql = ("d.case_number LIKE '%가단%' OR d.case_number LIKE '%가합%' "
                          "OR d.case_number LIKE '%가소%'")
    main_db = sqlite3.connect(f"file:{MAIN_DB}?mode=ro", uri=True)
    picked: list[tuple[str, str, str]] = []
    for score, row, combo in ladder_search(query, limit=40, case_filter=first_instance_sql):
        rowid, canonical_id, court, case_number, date, title, _ = row
        if canonical_id == target_canonical or not case_number:
            continue
        if target_case_number and case_number.strip() == target_case_number:
            continue
        got = main_db.execute("SELECT full_text FROM precedents WHERE rowid=?", (rowid,)).fetchone()
        if not got or not got[0]:
            continue
        body = got[0]
        norm = re.sub(r"\s+", " ", body)
        if target_case_number and target_case_number in norm:
            continue
        if any(w in norm for w in windows):
            continue
        for sentence in rule_sentences(body):
            picked.append((court or "?", case_number, sentence))
        if len(picked) >= 6:
            break
    main_db.close()
    if not picked:
        return "", 0
    lines = [RULES_HEADER]
    for i, (court, cno, sentence) in enumerate(picked[:6], 1):
        lines.append(f"{i}. {sentence} (출처: {court} {cno})")
    return "\n".join(lines) + "\n\n", len(picked[:6])



HOLDINGS_HEADER = """[같은 유형 분쟁에서 법원이 결론을 가른 지점]
아래는 판례 데이터베이스에서 검색된, **같은 청구 유형**의 다른 제1심 사건들에서 법원이
결론을 가른 판단 대목입니다. 각 항목은 그 사건의 실제 결론과 함께 제시됩니다.
다른 사건의 결론을 그대로 따르지 말고, **어떤 사실이 결론을 갈랐는지**를 이 사건에
대입해 보십시오:
"""

CLAIM_TYPES = (
    ("대여금", ("대여금", "차용", "대여하였")),
    ("손해배상", ("손해배상", "불법행위", "위자료")),
    ("부당이득", ("부당이득",)),
    ("사해행위취소", ("사해행위", "채권자취소")),
    ("공사대금", ("공사대금", "기성고", "도급")),
    ("임대차", ("임대차보증금", "차임", "임대차")),
    ("매매대금", ("매매대금", "매매계약")),
    ("보험금", ("보험금", "보험계약")),
    ("임금", ("임금", "퇴직금")),
    ("소유권이전", ("소유권이전등기", "말소등기")),
)

# Korean judgments write dates as "2018. 5. 1." so any sentence splitter based
# on the period character produces fragments; the passage extractor therefore
# anchors on the decisive phrase and takes a character window around it, the
# same technique that made the de-identified identity annotation findable.
DECISIVE = re.compile(
    r"(증거가 없다|인정하기(?:에)? 부족|인정할 증거가|증명되었다|증명되지 아니|"
    r"넉넉히 인정|받아들이기 어렵다|인정하기 어렵다|인정된다)"
)


def claim_type(text: str) -> tuple[str, tuple[str, ...]] | None:
    for name, keywords in CLAIM_TYPES:
        if any(k in text for k in keywords):
            return name, keywords
    return None


def decisive_passages(full_text: str, limit: int = 2) -> list[str]:
    sections = split_sections(full_text)
    if sections:
        body = sections["이유"]
    else:
        # many published judgments do not carry the canonical headings; the
        # court's assessment still sits in the last part of the document.
        body = full_text[int(len(full_text) * 0.4):]
    body = re.sub(r"\s+", " ", body)
    picked: list[str] = []
    for match in DECISIVE.finditer(body):
        window = body[max(0, match.start() - 230): match.end() + 90].strip()
        if len(window) < 80:
            continue
        if any(window[:60] == existing[:60] for existing in picked):
            continue
        picked.append(window)
        if len(picked) >= limit:
            break
    return picked


def build_holdings_block(prompt: str, target_case_number: str, target_canonical: str) -> tuple[str, int]:
    """Retrieve, from the SAME claim type, the passages where a court said what
    tipped the case — paired with that case's outcome.

    The earlier `refs` arm showed a bare outcome ("원고의 청구를 기각한다") is a
    harmful anchor. The hypothesis here is that an outcome becomes useful when
    it arrives attached to the fact that produced it, because that is what a
    lawyer actually transfers between cases.
    """
    claim, facts = facts_and_claim(prompt)
    kind = claim_type(claim + " " + facts[:1500])
    query = (claim + " " + facts[:400]).strip()
    windows = sample_windows(facts)
    first_instance_sql = ("d.case_number LIKE '%가단%' OR d.case_number LIKE '%가합%' "
                          "OR d.case_number LIKE '%가소%'")
    main_db = sqlite3.connect(f"file:{MAIN_DB}?mode=ro", uri=True)
    picked = []
    for score, row, combo in ladder_search(query, limit=40, case_filter=first_instance_sql):
        rowid, canonical_id, court, case_number, date, title, _ = row
        if canonical_id == target_canonical or not case_number:
            continue
        if target_case_number and case_number.strip() == target_case_number:
            continue
        got = main_db.execute("SELECT full_text FROM precedents WHERE rowid=?", (rowid,)).fetchone()
        if not got or not got[0]:
            continue
        body = got[0]
        norm = re.sub(r"\s+", " ", body)
        if target_case_number and target_case_number in norm:
            continue
        if any(w in norm for w in windows):
            continue
        if kind and not any(k in norm[:4000] for k in kind[1]):
            continue
        sections = split_sections(body)
        if not sections:
            continue
        outcome = label_from_holding(sections["주문"])
        if outcome is None:
            continue
        passages = decisive_passages(body)
        if not passages:
            continue
        picked.append((court or "?", case_number, outcome, passages))
        if len(picked) >= 3:
            break
    main_db.close()
    if not picked:
        return "", 0
    lines = [HOLDINGS_HEADER]
    if kind:
        lines.append(f"(이 사건 청구 유형: {kind[0]})")
    for i, (court, cno, outcome, passages) in enumerate(picked, 1):
        lines.append(f"{i}. {court} {cno} — 결론: **{outcome}**")
        for passage in passages:
            lines.append(f"   결정적 판단: {passage}")
    return "\n".join(lines) + "\n\n", len(picked)


def _holdings_worker(payload: tuple) -> tuple:
    case_id, prompt, case_number, canonical = payload
    try:
        return case_id, build_holdings_block(prompt, case_number, canonical)
    except Exception:
        return case_id, ("", 0)


def _rules_worker(payload: tuple) -> tuple:
    case_id, prompt, case_number, canonical = payload
    try:
        return case_id, build_rules_block(prompt, case_number, canonical)
    except Exception:
        return case_id, ("", 0)


def _refs_worker(payload: tuple) -> tuple:
    case_id, prompt, case_number, canonical = payload
    try:
        return case_id, build_refs_block(prompt, case_number, canonical)
    except Exception:
        return case_id, ("", 0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("arm", choices=["issues", "refs", "rules", "holdings"])
    parser.add_argument("--public", type=Path, default=BENCH / "outcome_civil_v1_args.public.jsonl")
    parser.add_argument("--private", type=Path, default=BENCH / "outcome_civil_v1_args.private.jsonl")
    parser.add_argument("--subset", type=Path, default=BENCH / "outcome_civil_v1n_neutral.public.jsonl",
                        help="jsonl whose ids define the paired subset")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=6)
    args = parser.parse_args()

    keep = {json.loads(l)["id"] for l in args.subset.read_text(encoding="utf-8").splitlines() if l.strip()}
    jobs = args.jobs
    priv = {r["caseId"]: r for r in map(json.loads, args.private.read_text(encoding="utf-8").splitlines())}
    rows = [json.loads(l) for l in args.public.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = [r for r in rows if r["id"] in keep]
    out_rows = []
    ref_counts = []
    if args.arm in ("refs", "rules", "holdings") and jobs > 1:
        import multiprocessing
        payload = [
            (r["id"], r["prompt"], priv[r["id"]]["caseRef"].split("|", 1)[1].strip(), priv[r["id"]]["canonicalId"])
            for r in rows
        ]
        worker = {"rules": _rules_worker, "holdings": _holdings_worker}.get(args.arm, _refs_worker)
        with multiprocessing.Pool(jobs) as pool:
            blocks = pool.map(worker, payload)
        block_map = dict(blocks)
        for row in rows:
            block, n_refs = block_map[row["id"]]
            ref_counts.append(n_refs)
            out_rows.append({**row,
                             "benchmarkId": {
                                 "rules": "outcome.civil_first_instance.v1rule_rules",
                                 "holdings": "outcome.civil_first_instance.v1h_holdings",
                             }.get(args.arm, "outcome.civil_first_instance.v1r_refs"),
                             "prompt": TAIL_RE.sub(lambda m: block + m.group(0), row["prompt"], count=1)})
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8") as fh:
            for row in out_rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        from collections import Counter
        print(json.dumps({"rows": len(out_rows), "refCounts": dict(Counter(ref_counts))}, ensure_ascii=False))
        return 0
    for row in rows:
        prompt = row["prompt"]
        if args.arm == "issues":
            new_prompt, n = TAIL_RE.subn(ISSUES_TAIL, prompt)
            if n != 1:
                raise SystemExit(f"tail not found in {row['id']}")
            bench_id = "outcome.civil_first_instance.v1i_issues"
        else:
            meta = priv[row["id"]]
            case_number = meta["caseRef"].split("|", 1)[1].strip()
            block, n_refs = build_refs_block(prompt, case_number, meta["canonicalId"])
            ref_counts.append(n_refs)
            new_prompt = TAIL_RE.sub(lambda m: block + m.group(0), prompt, count=1)
            bench_id = "outcome.civil_first_instance.v1r_refs"
        out_rows.append({**row, "benchmarkId": bench_id, "prompt": new_prompt})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for row in out_rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    report = {"rows": len(out_rows)}
    if ref_counts:
        from collections import Counter
        report["refCounts"] = dict(Counter(ref_counts))
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
