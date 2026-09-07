#!/usr/bin/env python3
"""Framing-immunization arm for the outcome-prediction benchmark (v1n).

Problem: v1's [당사자 주장] section is the *judge's own summary* of the
parties' contentions, written inside a document that argues toward its
conclusion. A style probe found no lexical leak (function-ngram CV accuracy
~chance) but a real STRUCTURAL leak: a classifier using only the relative
lengths of the plaintiff-side vs defendant-side argument summaries reaches
~62.5% CV accuracy — judges give more space to the side they engage with.

Fix under test (law-bench neutral-rewrite technique): a rewriter model sees
ONLY the argument section (never the holding), and must re-express it as a
symmetric, equal-length, non-evaluative summary of both sides. Deterministic
gates then verify the rewrite leaked nothing:

  gate 1  no conclusion vocabulary (기각/인용/이유 없다/타당하다/...)
  gate 2  both sides present (원고 and 피고 argument segments)
  gate 3  length symmetry: side-length ratio <= 1.6
  gate 4  size sanity: 200-4500 chars

Rows failing gates go to a retry file; rows failing twice are dropped from
the neutral arm (reported, never silently). Prediction accuracy on v1n vs v1
then separates substance (+args signal survives) from framing (signal dies).

Commands:
  prepare  — build the rewrite campaign input from the v1 bench
  apply    — gate the rewrite answers and emit the v1n public bench
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BENCH = REPO_ROOT / "benchmarks" / "outcome_prediction"

REWRITE_INSTRUCTIONS = """# Neutral argument rewrite run

`input/questions.jsonl` has one JSON row per case: fields `id` and `args`
(a Korean court-document section summarizing both parties' contentions).

For EVERY row, rewrite `args` into a neutral, symmetric form. Hard rules:
1. Two paragraphs, each 3-6 sentences: first `원고 측 주장: ...`, then
   `피고 측 주장: ...`. Give the two paragraphs approximately EQUAL length.
2. Present each side's contentions in their strongest good-faith form, from
   that side's own perspective.
3. Remove every evaluative, skeptical or predictive expression. Never hint
   which side should win. Forbidden words include: 기각, 인용, 각하,
   이유 없다, 이유 있다, 타당, 부당, 봄이 상당, 인정된다, 인정되지.
4. Do not add facts that are not in the input; do not drop a distinct
   contention either side raised.
5. Output MUST be plain Korean prose (no markdown, no lists).

Write progress to `output/answers.partial.jsonl`. When every input ID has an
answer, atomically write `output/answers.jsonl` in input order: one JSON
object per line, exactly the fields `id` and `finalAnswer` (the rewritten
text). The final chat message is only a completion notice.
"""

CONCLUSION_VOCAB = re.compile(
    r"(기각|인용|각하|이유\s*없|이유\s*있|타당|부당|봄이\s*상당|인정된다|인정되지|"
    r"배척|받아들이|받아들일)"
)


def extract_args_section(prompt: str) -> str | None:
    m = re.search(r"\[당사자 주장\]\n(.*?)\n\n다음 두 가지", prompt, re.S)
    return m.group(1).strip() if m else None


def side_lengths(text: str) -> tuple[int, int] | None:
    pm = re.search(r"원고\s*측?\s*주장\s*[::]?", text)
    dm = re.search(r"피고\s*측?\s*주장\s*[::]?", text)
    if not pm or not dm or dm.start() <= pm.start():
        return None
    return dm.start() - pm.end(), len(text) - dm.end()


def longest_common_run(a: str, b: str) -> int:
    """Length of the longest run of characters shared verbatim (whitespace-
    normalized) — detects copy-paste 'rewrites'."""
    a = re.sub(r"\s+", "", a)
    b = re.sub(r"\s+", "", b)
    if not a or not b:
        return 0
    best = 0
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        ai = a[i - 1]
        for j in range(1, len(b) + 1):
            if ai == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best:
                    best = cur[j]
        prev = cur
    return best


def gate(text: str, source: str | None = None) -> str | None:
    """Return a rejection reason or None if the rewrite passes."""
    if not (200 <= len(text) <= 4500):
        return "size"
    if source is not None and longest_common_run(text, source) >= 30:
        return "verbatim_copy"
    if CONCLUSION_VOCAB.search(text):
        return "conclusion_vocab"
    sides = side_lengths(text)
    if sides is None:
        return "missing_side"
    plaintiff, defendant = sides
    if min(plaintiff, defendant) < 80:
        return "side_too_short"
    ratio = max(plaintiff, defendant) / max(1, min(plaintiff, defendant))
    if ratio > 1.6:
        return "asymmetric"
    return None


def cmd_prepare(args: argparse.Namespace) -> int:
    rows = [json.loads(l) for l in args.public.read_text(encoding="utf-8").splitlines() if l.strip()]
    only = set(json.loads(args.only_ids.read_text())) if args.only_ids else None
    out = []
    for row in rows:
        if only and row["id"] not in only:
            continue
        section = extract_args_section(row["prompt"])
        if section is None:
            raise SystemExit(f"no args section in {row['id']}")
        out.append({"id": row["id"], "args": section})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for row in out:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    (args.out.parent / "RUN_INSTRUCTIONS.md").write_text(REWRITE_INSTRUCTIONS, encoding="utf-8")
    print(json.dumps({"rows": len(out)}))
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    public = [json.loads(l) for l in args.public.read_text(encoding="utf-8").splitlines() if l.strip()]
    rewrites: dict[str, str] = {}
    for path in args.answers:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            rewrites[row["id"]] = str(row.get("finalAnswer") or "")
    kept, rejected = [], {}
    for row in public:
        text = rewrites.get(row["id"])
        if text is None:
            rejected[row["id"]] = "missing"
            continue
        text = text.strip()
        reason = gate(text, source=extract_args_section(row["prompt"]))
        if reason:
            rejected[row["id"]] = reason
            continue
        new_prompt = re.sub(
            r"(\[당사자 주장\]\n).*?(\n\n다음 두 가지)",
            lambda m: m.group(1) + text + m.group(2),
            row["prompt"],
            flags=re.S,
        )
        kept.append({**row, "benchmarkId": "outcome.civil_first_instance.v1n_neutral", "prompt": new_prompt})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for row in kept:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    if args.rejects_out:
        args.rejects_out.write_text(json.dumps(rejected, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print(json.dumps({"kept": len(kept), "rejected": dict(Counter(rejected.values())),
                      "reject_ids": sorted(rejected)}, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--public", type=Path, default=BENCH / "outcome_civil_v1_args.public.jsonl")
    p.add_argument("--only-ids", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(func=cmd_prepare)
    p = sub.add_parser("apply")
    p.add_argument("--public", type=Path, default=BENCH / "outcome_civil_v1_args.public.jsonl")
    p.add_argument("--answers", type=Path, nargs="+", required=True)
    p.add_argument("--out", type=Path, default=BENCH / "outcome_civil_v1n_neutral.public.jsonl")
    p.add_argument("--rejects-out", type=Path)
    p.set_defaults(func=cmd_apply)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
