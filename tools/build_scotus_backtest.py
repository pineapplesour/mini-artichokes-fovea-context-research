#!/usr/bin/env python3
"""Build the SCOTUS 2024-term BACKTEST benchmark (three contamination arms).

Motivation: the post-cutoff 2025-term result (86.2%, BA 0.827) cannot be
memorized because the decisions post-date the model cutoff. The 2024 term
(decided by 2025-06, i.e. inside the training window) is used to *measure
memorization inflation* — per law-bench leak-control practice, the same
prediction task is run in three arms:

  asis  — full transcript, unmodified (memorization + signal)
  anon  — transcript with docket numbers, party-name tokens and arguing
          counsel surnames deterministically redacted (signal, reduced
          surface identifiers; deep facts still identify famous cases,
          which is a stated limitation, not a bug)
  probe — NO transcript; only the caption/docket/term, asking the model to
          recall the decided outcome (pure memorization channel)

If asis >> anon and probe >> chance, the backtest is inflated by memory and
only the post-cutoff figure should be trusted. If asis ~ anon ~ post-cutoff,
transcript signal dominates and backtesting on archived terms is usable.

Labels come from bound-volume preliminary-print PDFs parsed with the
fi-ligature-tolerant disposition pattern (affirm may extract as 'affrmed').
Sampling is class-balanced (all AFFIRMs + hash-sampled REVERSEs), chance=50%.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import time
import urllib.request
from pathlib import Path

import fitz

REPO_ROOT = Path(__file__).resolve().parents[1]
BENCH_DIR = REPO_ROOT / "benchmarks" / "scotus_prediction"

PROMPT = """Below is the complete official oral argument transcript of a United States Supreme Court case. The decision has NOT been shown to you. Based ONLY on this transcript — the advocates' arguments and the Justices' questions and reactions — predict the outcome.

Answer with exactly one word on the first line: REVERSE (the Court reverses or vacates the judgment below) or AFFIRM (the Court affirms).
On the second line write `confidence: 0.xx`.
Then two or three sentences of reasoning citing specific moments from the argument.

[TRANSCRIPT]
{transcript}"""

PROBE_PROMPT = """The following United States Supreme Court case was argued in October Term 2024 and decided in 2025.

Case: {name}
Docket No.: {docket}

Without being shown any transcript or opinion, state from your own knowledge what the Court decided.
Answer with exactly one word on the first line: REVERSE (the Court reversed or vacated the judgment below) or AFFIRM (the Court affirmed).
On the second line write `confidence: 0.xx`.
Then one sentence: if you genuinely do not recall this specific decision, say so explicitly."""


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 research-bench"})
    return urllib.request.urlopen(req, timeout=180).read()


def transcript_text(pdf_bytes: bytes) -> str | None:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    raw = "\n".join(page.get_text() for page in doc)
    # strip reporter boilerplate, line numbers, page headers
    lines = []
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        if re.fullmatch(r"\d{1,4}", s):
            continue
        if re.search(r"Official\s*-\s*Subject to Final Review|Heritage Reporting|Alderson|www\.|\(202\)", s, re.I):
            continue
        lines.append(s)
    text = " ".join(lines)
    start = re.search(r"CHIEF JUSTICE ROBERTS:", text)
    if not start:
        return None
    end = re.search(r"\(Whereupon, at .{0,120}?adjourned", text)
    body = text[start.start(): end.start() if end else len(text)]
    body = re.sub(r"\s+", " ", body).strip()
    return body if len(body) > 20000 else None


PARTY_STOP = {
    "inc", "llc", "co", "corp", "company", "corporation", "of", "the", "and",
    "et", "al", "v", "vs", "on", "for", "a", "in", "united", "states", "state",
    "u.s", "us", "commission", "committee", "association", "county", "city",
    "department", "district", "board", "national", "america", "american",
    "group", "services", "service", "international", "attorney", "general",
    "secretary", "acting", "warden", "governor", "commissioner", "director",
}


def redact(text: str, case: dict) -> str:
    out = text.replace(case["docket"], "XX-XXXX")
    # arguing counsel surnames from the argument headings
    for m in re.finditer(r"(?:ORAL|REBUTTAL) ARGUMENT OF ([A-Z][A-Z .,'\-]{3,50}?) ON BEHALF OF", out):
        toks = [t for t in re.findall(r"[A-Z][A-Za-z'\-]{2,}", m.group(1)) if t.lower() not in ("jr", "sr", "iii", "esq")]
        if toks:
            out = re.sub(r"\b" + re.escape(toks[-1]) + r"\b", "COUNSEL", out)
    first, second = case.get("first_party"), case.get("second_party")
    if not first or not second:
        halves = re.split(r"\s+v\.?\s+", case.get("name") or "", maxsplit=1)
        first = first or (halves[0] if halves else "")
        second = second or (halves[1] if len(halves) > 1 else "")
    pairs = [(first, "PETITIONER"), (second, "RESPONDENT")]
    for field, repl in pairs:
        for tok in re.findall(r"[A-Za-z][A-Za-z'\-\.]{2,}", field):
            if tok.lower().strip(".") in PARTY_STOP:
                continue
            out = re.sub(r"\b" + re.escape(tok) + r"\b", repl, out, flags=re.I)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labeled", type=Path, default=BENCH_DIR / "labeled_cases_2024.json")
    parser.add_argument("--per-class", type=int, default=15)
    parser.add_argument("--seed-salt", default="scotus-bt24")
    parser.add_argument("--max-chars", type=int, default=200000)
    args = parser.parse_args()

    cases = json.load(open(args.labeled))
    by_label: dict[str, list[dict]] = {"AFFIRM": [], "REVERSE": []}
    for c in cases:
        by_label[c["label"]].append(c)
    for lab in by_label:
        by_label[lab].sort(key=lambda c: hashlib.sha256(f"{args.seed_salt}|{c['docket']}".encode()).hexdigest())
    picked: list[dict] = []
    for lab in ("AFFIRM", "REVERSE"):
        pool = by_label[lab][: args.per_class]
        if len(pool) < args.per_class:
            raise SystemExit(f"not enough {lab}: {len(pool)}")
        picked.extend(pool)

    arms = {"asis": [], "anon": [], "probe": []}
    private: list[dict] = []
    skipped = 0
    for c in picked:
        try:
            body = transcript_text(fetch(c["transcript"]))
        except Exception as exc:
            print("fetch-fail", c["docket"], str(exc)[:60])
            body = None
        if not body:
            skipped += 1
            print("skip", c["docket"], c["name"][:40])
            continue
        body = body[: args.max_chars]
        cid = f"scotus-bt24-{c['docket'].replace('-', '_')}"
        base = {"suite": "exam", "responseFormat": "outcome_prediction", "language": "en"}
        arms["asis"].append({"id": cid, "benchmarkId": "scotus.backtest24.asis", **base,
                             "prompt": PROMPT.format(transcript=body)})
        arms["anon"].append({"id": cid, "benchmarkId": "scotus.backtest24.anon", **base,
                             "prompt": PROMPT.format(transcript=redact(body, c))})
        arms["probe"].append({"id": cid, "benchmarkId": "scotus.backtest24.probe", **base,
                              "prompt": PROBE_PROMPT.format(name=c["name"], docket=c["docket"])})
        private.append({"caseId": cid, "label": c["label"], "docket": c["docket"], "name": c["name"]})
        time.sleep(0.3)

    for arm, rows in arms.items():
        path = BENCH_DIR / f"scotus_bt24_{arm}.public.jsonl"
        with path.open("w") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (BENCH_DIR / "scotus_bt24.private.jsonl").open("w") as fh:
        for row in private:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    from collections import Counter
    print(json.dumps({"rows": len(private), "skipped": skipped,
                      "labels": dict(Counter(r["label"] for r in private))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
