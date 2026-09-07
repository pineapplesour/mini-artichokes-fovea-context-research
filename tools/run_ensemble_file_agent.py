#!/usr/bin/env python3
"""Candidate engine: N independent whole-file Plain Codex drafts + deterministic majority merge.

Mechanism (whole-artifact, no item splitting):
  1. `draft`: N isolated solver invocations, each receiving the complete frozen
     public suite under the exact baseline solver protocol (same model, effort,
     verbosity, tool policy, transport, bwrap boundary). Drafts run in parallel.
  2. `merge`: deterministic local voting over the N complete answer files.
     No model call. Majority key per row:
       - extracted MCQ option marker (①-⑩, 1-10, A-E) when present, else
       - normalized answer text (lowercased, punctuation/whitespace stripped).
     Ties fall back to the first draft's answer. The merged file is written to
     the campaign's own solver/output/answers.jsonl so the standard
     validate-answers / prepare-grader / grader pipeline applies unchanged.

Every draft receives and answers the complete 1,309-row suite; no call solves
a subset. Extra calls are reported in ensemble_receipt.json.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import os
import shutil
import subprocess
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

RUNNER = REPO_ROOT / "tools/run_plain_codex_file_agent.py"

CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def normalize_answer_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or ""))
    value = value.casefold()
    value = re.sub(r"[\s ]+", " ", value)
    value = re.sub(r"[^0-9a-z가-힣ⓐ-ⓩ①-⑩ ]+", "", value)
    return value.strip()


def extract_option_marker(text: str) -> str:
    """Extract an MCQ option index from an answer's leading marker, if any.

    Circled digits, plain digits, and Latin letters denoting the same option
    position map to one canonical index string so `③`, `3)`, and `C.` vote
    together.
    """
    value = str(text or "").strip()
    if not value:
        return ""
    head = value[:8]
    for ch in head:
        if ch in CIRCLED:
            return str(CIRCLED.index(ch) + 1)
    match = re.match(r"^\(?([1-9]|10)\)?[.)\s]", value)
    if match:
        return match.group(1)
    # A bare letter followed only by whitespace is a real word in English and
    # Portuguese ("A lei…", "E o…"), so letter markers require punctuation.
    # MMLU-Pro uses as many as ten choices, hence A-J rather than the legacy
    # A-E ceiling.
    match = re.match(r"^\(([A-Ja-j])\)|^([A-Ja-j])[.)]", value)
    if match:
        letter = (match.group(1) or match.group(2)).lower()
        return str(ord(letter) - ord("a") + 1)
    return ""


def parse_mcq_options(prompt: str) -> dict[str, str]:
    """Extract option index -> option text from a public MCQ prompt.

    Handles the two observed public styles uniformly across every benchmark:
    circled digits (①-⑩) and line-leading Latin letters (`A.`/`B)`）. Returns
    an empty mapping when no coherent option block is found (e.g. OCR-damaged
    markers); voting then falls back to normalized answer text.
    """
    text = str(prompt or "")
    positions: list[tuple[int, int]] = []
    for index, ch in enumerate(CIRCLED):
        found = text.rfind(ch)
        if found >= 0:
            positions.append((found, index + 1))
    positions.sort()
    if len(positions) >= 2 and all(
        positions[i][1] == i + 1 for i in range(len(positions))
    ):
        options: dict[str, str] = {}
        for i, (start, number) in enumerate(positions):
            end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
            options[str(number)] = text[start + 1 : end].strip()
        return options
    matches = list(re.finditer(r"(?m)^\s*([A-J])[.)]\s+", text))
    if len(matches) >= 2:
        options = {}
        for i, match in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            number = str(ord(match.group(1)) - ord("A") + 1)
            options[number] = text[match.end() : end].strip()
        return options
    return {}


def match_answer_to_option(answer: str, options: dict[str, str]) -> str:
    """Deterministically map an answer to an option index, or '' if unclear."""
    if not options:
        return ""
    marker = extract_option_marker(answer)
    if marker and marker in options:
        return marker
    normalized_answer = normalize_answer_text(answer)
    if not normalized_answer:
        return ""
    scores: list[tuple[float, str]] = []
    answer_tokens = set(normalized_answer.split())
    for number, option_text in options.items():
        normalized_option = normalize_answer_text(option_text)
        if not normalized_option:
            continue
        if normalized_answer == normalized_option:
            scores.append((1.0, number))
            continue
        if normalized_answer in normalized_option or normalized_option in normalized_answer:
            scores.append((0.9, number))
            continue
        option_tokens = set(normalized_option.split())
        union = answer_tokens | option_tokens
        jaccard = len(answer_tokens & option_tokens) / len(union) if union else 0.0
        scores.append((jaccard, number))
    scores.sort(reverse=True)
    if not scores:
        return ""
    best_score, best_number = scores[0]
    second_score = scores[1][0] if len(scores) > 1 else 0.0
    if best_score >= 0.5 and best_score - second_score >= 0.1:
        return best_number
    return ""


def vote_key(answer: str, response_format: str, prompt: str = "") -> str:
    if response_format == "mcq":
        if prompt:
            option = match_answer_to_option(answer, parse_mcq_options(prompt))
            if option:
                return f"option:{option}"
        marker = extract_option_marker(answer)
        if marker:
            return f"marker:{marker}"
    return f"text:{normalize_answer_text(answer)}"


def draft_dir(campaign_dir: Path, index: int) -> Path:
    return campaign_dir / "drafts" / f"d{index}"


def prepare_draft(campaign_dir: Path, index: int) -> Path:
    src_solver = campaign_dir / "solver"
    dst = draft_dir(campaign_dir, index) / "solver"
    if dst.exists():
        return dst.parent
    (dst / "output").mkdir(parents=True, exist_ok=True)
    shutil.copytree(src_solver / "input", dst / "input", copy_function=os.link)
    shutil.copy2(src_solver / "freeze.json", dst / "freeze.json")
    return dst.parent


def run_draft(
    *,
    campaign_dir: Path,
    index: int,
    codex_home: Path,
    model: str,
    reasoning_effort: str,
    verbosity: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    target = prepare_draft(campaign_dir, index)
    started = time.monotonic()
    completed = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "solver",
            "--campaign-dir",
            str(target),
            "--codex-home",
            str(codex_home),
            "--model",
            model,
            "--reasoning-effort",
            reasoning_effort,
            "--verbosity",
            verbosity,
            "--timeout-seconds",
            str(timeout_seconds),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    elapsed = round(time.monotonic() - started, 3)
    receipt_path = target / "solver" / "run_receipt.json"
    receipt: dict[str, Any] = {}
    if receipt_path.is_file():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    return {
        "draft": index,
        "elapsedSec": elapsed,
        "runnerExitCode": completed.returncode,
        "runnerStdoutTail": completed.stdout.strip()[-400:],
        "runnerStderrTail": completed.stderr.strip()[-400:],
        "receiptStatus": receipt.get("status"),
        "answersSha256": receipt.get("artifactValidation", {}).get("answersSha256"),
    }


BOILERPLATE_MIN_REPEATS = 4
BOILERPLATE_MIN_LENGTH = 40


def merge_drafts(campaign_dir: Path, draft_indices: list[int]) -> dict[str, Any]:
    questions = load_jsonl(campaign_dir / "solver/input/questions.jsonl")
    formats = {row["id"]: row.get("responseFormat", "") for row in questions}
    prompts = {row["id"]: str(row.get("prompt", "")) for row in questions}
    order = [row["id"] for row in questions]

    draft_answers: dict[int, dict[str, str]] = {}
    duplication: dict[int, Counter] = {}
    for index in draft_indices:
        path = draft_dir(campaign_dir, index) / "solver/output/answers.jsonl"
        rows = load_jsonl(path)
        draft_answers[index] = {row["id"]: str(row.get("finalAnswer", "")) for row in rows}
        duplication[index] = Counter(
            normalize_answer_text(answer) for answer in draft_answers[index].values()
        )

    def dup_count(index: int, answer: str) -> int:
        return duplication[index][normalize_answer_text(answer)]

    merged_rows: list[dict[str, Any]] = []
    stats = Counter()
    disputed_ids: list[str] = []
    for case_id in order:
        response_format = formats.get(case_id, "")
        candidates: list[tuple[int, str, str]] = []
        for index in draft_indices:
            answer = draft_answers[index].get(case_id, "")
            if answer.strip():
                candidates.append(
                    (index, answer, vote_key(answer, response_format, prompts.get(case_id, "")))
                )
        if not candidates:
            merged_rows.append({"id": case_id, "finalAnswer": ""})
            stats["empty"] += 1
            disputed_ids.append(case_id)
            continue
        # A draft that emitted the same LONG normalized answer for many
        # different rows is boilerplating; such candidates lose voting rights
        # whenever a non-boilerplate candidate exists for the row. Short
        # repeated answers (legitimate across exam rows) are never flagged.
        # Content-blind and uniform across every row and benchmark.
        def is_boilerplate(candidate: tuple[int, str, str]) -> bool:
            normalized = normalize_answer_text(candidate[1])
            return (
                len(normalized) >= BOILERPLATE_MIN_LENGTH
                and dup_count(candidate[0], candidate[1]) >= BOILERPLATE_MIN_REPEATS
            )

        flagged = [candidate for candidate in candidates if is_boilerplate(candidate)]
        effective = [c for c in candidates if c not in flagged] or candidates
        if len(effective) < len(candidates):
            stats["boilerplate_excluded_rows"] += 1
        counts = Counter(key for _, _, key in effective)
        top_key, top_count = counts.most_common(1)[0]
        if top_count >= 2:
            chosen = next(answer for _, answer, key in effective if key == top_key)
            stats["majority"] += 1
        else:
            # Tie: lowest draft index among non-boilerplate candidates.
            chosen = min(effective, key=lambda c: c[0])[1]
            stats["tie_first_effective_draft"] += 1
            disputed_ids.append(case_id)
        merged_rows.append({"id": case_id, "finalAnswer": chosen})

    out_path = campaign_dir / "solver/output/answers.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as stream:
        for row in merged_rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")

    report = {
        "schemaVersion": 1,
        "mechanism": "independent_whole_file_drafts_majority_v3_lengthgated_antiboilerplate",
        "draftIndices": draft_indices,
        "rowCount": len(merged_rows),
        "voteStats": dict(stats),
        "disputedCount": len(disputed_ids),
        "disputedIds": disputed_ids,
        "draftAnswersSha256": {
            str(index): sha256_file(draft_dir(campaign_dir, index) / "solver/output/answers.jsonl")
            for index in draft_indices
        },
        "mergedAnswersSha256": sha256_file(out_path),
        "semanticModelInvocationsInMerge": 0,
    }
    report_path = campaign_dir / "merge_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


ADJUDICATION_INSTRUCTIONS = """# Adjudication run

`input/questions.jsonl` contains the complete public suite, one JSON row per
question with fields `id`, `prompt`, `responseFormat`.

`input/candidates/candidate_a.jsonl`, `candidate_b.jsonl`, and
`candidate_c.jsonl` are three independent complete answer attempts over the
same suite. Their quality varies by row; none is reliable everywhere.

Your job is to VERIFY, not to re-solve from scratch. For every question row:

1. Read the question and the three candidate answers for that `id`.
2. Judge which candidate answer is actually correct and substantive for this
   specific question. Checking a proposed answer is cheaper than solving
   fresh — use that advantage.
3. If one candidate is clearly best, output it (you may minimally clean it).
   If all are wrong and you are confident of the correct answer, output your
   corrected answer instead.
4. Never output an answer that is a generic template sentence repeated across
   many rows: an answer must be specific to its question.
5. For multiple-choice questions, the answer must be the content of the
   selected option, not only its label.
6. When a question asks for grounded, evidence-backed analysis (for example a
   request to find, apply, or predict from real sources), prefer the candidate
   that cites specific verifiable sources (case numbers, document identifiers,
   named authorities) over an uncited paraphrase, unless the citation is
   plainly fabricated or irrelevant. Concreteness that can be checked beats
   fluent generality.

Mandatory decision ledger: process rows in slices of about 40. For every row,
BEFORE finalizing its answer, append exactly one line to
`output/decisions.log`:
`<id> | chosen=<a|b|c|self> | <one short clause naming the decisive reason>`
Never finalize a slice whose rows lack ledger lines. A row decided without
reading its candidates is invalid.

Write progress to `output/answers.partial.jsonl` as you go. When every input
ID has exactly one final answer, atomically write the complete
`output/answers.jsonl` preserving input order: one JSON object per line with
exactly the fields `id` and `finalAnswer`. Every row must be present exactly
once. The final chat message is only a completion notice.
"""


def prepare_adjudication(campaign_dir: Path, draft_indices: list[int]) -> Path:
    source_solver = campaign_dir / "solver"
    target = campaign_dir / "adjudication" / "solver"
    if target.exists():
        return target.parent
    (target / "output").mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_solver / "input", target / "input", copy_function=os.link)
    shutil.copy2(source_solver / "freeze.json", target / "freeze.json")
    (target / "input/RUN_INSTRUCTIONS.md").write_text(ADJUDICATION_INSTRUCTIONS, encoding="utf-8")
    candidates_dir = target / "input/candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    for letter, index in zip("abc", draft_indices):
        shutil.copy2(
            draft_dir(campaign_dir, index) / "solver/output/answers.jsonl",
            candidates_dir / f"candidate_{letter}.jsonl",
        )
    return target.parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["draft", "merge", "adjudicate"])
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--codex-home", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument("--verbosity", default="low")
    parser.add_argument("--num-drafts", type=int, default=3)
    parser.add_argument("--draft-indices", type=str, default="")
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument("--sequential", action="store_true")
    args = parser.parse_args()
    campaign = args.campaign_dir.resolve()
    indices = (
        [int(part) for part in args.draft_indices.split(",") if part.strip()]
        if args.draft_indices
        else list(range(1, args.num_drafts + 1))
    )

    if args.command == "draft":
        results: list[dict[str, Any]] = []
        if args.sequential:
            for index in indices:
                results.append(
                    run_draft(
                        campaign_dir=campaign,
                        index=index,
                        codex_home=args.codex_home,
                        model=args.model,
                        reasoning_effort=args.reasoning_effort,
                        verbosity=args.verbosity,
                        timeout_seconds=args.timeout_seconds,
                    )
                )
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(indices)) as pool:
                futures = [
                    pool.submit(
                        run_draft,
                        campaign_dir=campaign,
                        index=index,
                        codex_home=args.codex_home,
                        model=args.model,
                        reasoning_effort=args.reasoning_effort,
                        verbosity=args.verbosity,
                        timeout_seconds=args.timeout_seconds,
                    )
                    for index in indices
                ]
                results = [future.result() for future in futures]
        accepted = [row for row in results if row.get("receiptStatus") == "accepted"]
        summary = {
            "command": "draft",
            "drafts": results,
            "acceptedCount": len(accepted),
            "requestedCount": len(indices),
        }
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0 if len(accepted) == len(indices) else 1

    if args.command == "merge":
        report = merge_drafts(campaign, indices)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0

    target = prepare_adjudication(campaign, indices)
    completed = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "solver",
            "--campaign-dir",
            str(target),
            "--codex-home",
            str(args.codex_home),
            "--model",
            args.model,
            "--reasoning-effort",
            args.reasoning_effort,
            "--verbosity",
            args.verbosity,
            "--timeout-seconds",
            str(args.timeout_seconds),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    print(completed.stdout.strip()[-600:])
    if completed.returncode != 0:
        print(completed.stderr.strip()[-400:], file=sys.stderr)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
