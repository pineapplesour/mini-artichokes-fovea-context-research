#!/usr/bin/env python3
"""Run and score the outcome-prediction benchmark with web search disabled.

Arms:
  direct  — one isolated no-web Codex call over the whole 180-row file
            (Plain Codex baseline for this benchmark).
  draft   — N independent no-web whole-file drafts (same protocol).
  adjudicate — one no-web whole-file adjudication over the draft candidates
            (the same universal try-then-verify mechanism as the exam gate).
  score   — deterministic class comparison against the private labels; no
            model grader. Reports accuracy, per-class recall, and an exact
            binomial p-value against the 50% chance rate.

Web search is disabled for every arm because the underlying judgments are
published documents; retrieving them would measure lookup, not prediction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.run_plain_codex_file_agent import base_bwrap_command, DISABLED_FEATURES

DEFAULT_PUBLIC = REPO_ROOT / "benchmarks/outcome_prediction/outcome_civil_v0.public.jsonl"
DEFAULT_PRIVATE = REPO_ROOT / "benchmarks/outcome_prediction/outcome_civil_v0.private.jsonl"

SOLVER_INSTRUCTIONS = """# Outcome prediction run

`input/questions.jsonl` contains one JSON row per case with fields `id` and
`prompt`. Answer every row's question exactly as the prompt instructs.

Write progress to `output/answers.partial.jsonl`. When every input ID has one
answer, atomically write the complete `output/answers.jsonl` in input order:
one JSON object per line with exactly the fields `id` and `finalAnswer`.
`finalAnswer` must begin with the single-word conclusion on its first line.
The final chat message is only a completion notice.
"""

DRAFT_INSTRUCTIONS = SOLVER_INSTRUCTIONS + """
Mandatory work protocol: process the cases in slices of about 20. For every
case, BEFORE finalizing its answer, append exactly one line to
`output/worklog.txt` containing the case id, the two or three decisive
factual points you relied on, and your conclusion. Never finalize a slice
whose cases lack worklog lines. Do not answer from surface impressions;
identify the legally decisive facts first.
"""

DRAFT_INSTRUCTIONS_ISSUES = SOLVER_INSTRUCTIONS + """
Mandatory work protocol (issue decomposition): process the cases in slices of
about 15. For every case, BEFORE finalizing its answer:

1. Identify the 2-4 legally decisive issues the court must resolve (e.g.
   whether a duty existed, whether the evidence establishes the disputed fact,
   whether a defense applies, quantum).
2. For each issue, judge from the given facts alone which party that issue
   favors.
3. Derive the overall conclusion from the per-issue judgments — the claim
   fails only if a dispositive issue goes against the plaintiff.
4. Append one line to `output/worklog.txt`:
   `<id> | issue1=<leaning>; issue2=<leaning>; ... | <conclusion> | conf=<0.00-1.00>`

Never finalize a slice whose cases lack worklog lines.

Answer format per row: first line the single-word conclusion; second line
`확신도: <0.00-1.00>` reflecting how strongly the issues point one way; then
two or three sentences of rationale referencing your decisive issues.
"""

ADJUDICATION_INSTRUCTIONS = """# Outcome prediction adjudication

`input/questions.jsonl` contains one JSON row per case (`id`, `prompt`).
`input/candidates/candidate_a.jsonl`, `candidate_b.jsonl`, `candidate_c.jsonl`
are independent complete answer attempts. For every row, examine the question
and the candidate conclusions with their stated reasons, judge which
conclusion the evidence actually supports, and output the best-supported
answer (or your own corrected answer if all candidates are unconvincing).
Checking a proposed conclusion against the facts is cheaper than deciding
fresh — use that advantage.

Write `output/answers.jsonl` with every input ID exactly once, in input
order: `{"id": ..., "finalAnswer": ...}` per line, first line of finalAnswer
being the single-word conclusion. The final chat message is only a completion
notice.
"""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def prepare_dir(role_dir: Path, public: Path, instructions: str) -> None:
    input_dir = role_dir / "input"
    (role_dir / "output").mkdir(parents=True, exist_ok=True)
    input_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(public, input_dir / "questions.jsonl")
    (input_dir / "RUN_INSTRUCTIONS.md").write_text(instructions, encoding="utf-8")
    ids = [row["id"] for row in load_jsonl(public)]
    (input_dir / "expected_ids.json").write_text(json.dumps(ids, ensure_ascii=False), encoding="utf-8")


def codex_no_web_command(*, input_dir: Path, output_dir: Path, codex_home: Path, model: str, effort: str) -> list[str]:
    command, _ = base_bwrap_command(input_dir=input_dir, output_dir=output_dir, codex_home=codex_home)
    command.extend(
        [
            "/tmp/codex-node/bin/node",
            "/tmp/codex-node/lib/node_modules/@openai/codex/bin/codex.js",
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--sandbox",
            "danger-full-access",
            "--cd",
            "/tmp/work",
            "--model",
            model,
            "--config",
            f'model_reasoning_effort="{effort}"',
            "--config",
            'model_verbosity="low"',
            "--config",
            'service_tier="default"',
            "--config",
            'web_search="disabled"',
        ]
    )
    for feature in DISABLED_FEATURES:
        command.extend(["--config", f"features.{feature}=false"])
    command.extend(
        [
            "--config",
            "features.shell_tool=true",
            "--json",
            "--output-last-message",
            "/tmp/work/output/last_message.txt",
            "-",
        ]
    )
    return command


def run_role(role_dir: Path, *, codex_home: Path, model: str, effort: str, timeout_seconds: int) -> dict:
    input_dir = role_dir / "input"
    output_dir = role_dir / "output"
    command = codex_no_web_command(
        input_dir=input_dir, output_dir=output_dir, codex_home=codex_home, model=model, effort=effort
    )
    trace_path = role_dir / "codex_trace.jsonl"
    stderr_path = role_dir / "codex_stderr.txt"
    prompt = "Read input/RUN_INSTRUCTIONS.md completely, obey it, process the complete input file, and produce the required final output file."
    started = time.monotonic()
    timed_out = False
    with trace_path.open("w", encoding="utf-8") as trace, stderr_path.open("w", encoding="utf-8") as err:
        process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=trace, stderr=err, text=True, start_new_session=True
        )
        assert process.stdin
        process.stdin.write(prompt)
        process.stdin.close()
        try:
            code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            code = process.wait(timeout=20)
    elapsed = round(time.monotonic() - started, 3)
    expected = set(json.loads((input_dir / "expected_ids.json").read_text(encoding="utf-8")))
    answers_path = output_dir / "answers.jsonl"
    rows = load_jsonl(answers_path) if answers_path.is_file() else []
    observed = [row.get("id") for row in rows]
    complete = (
        not timed_out
        and code == 0
        and len(observed) == len(expected)
        and set(observed) == expected
        and all(str(row.get("finalAnswer", "")).strip() for row in rows)
    )
    web_events = trace_path.read_text(encoding="utf-8").count('"web_search"')
    from tools.benchmark_provider import _parse_codex_jsonl_trace

    usage = _parse_codex_jsonl_trace(trace_path.read_text(encoding="utf-8")).get("tokenUsage", {})
    receipt = {
        "status": "accepted" if complete else "incomplete",
        "exitCode": code,
        "timedOut": timed_out,
        "elapsedSec": elapsed,
        "rows": len(observed),
        "webSearchMarkers": web_events,
        "tokenUsage": usage,
        "answersSha256": sha256_file(answers_path) if answers_path.is_file() else None,
    }
    (role_dir / "run_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=1), encoding="utf-8")
    return receipt


def parse_conclusion(answer: str) -> str:
    first = str(answer or "").strip().splitlines()[0] if str(answer or "").strip() else ""
    head = first[:20]
    if "기각" in head:
        return "기각"
    if "인용" in head:
        return "인용됨"
    return ""


CONFIDENCE = re.compile(r"(?:확신도|conf(?:idence)?)\s*[:=：]?\s*(1(?:\.0+)?|0?\.\d+)")


def parse_confidence(answer: str) -> float | None:
    lines = str(answer or "").strip().splitlines()[:3]
    for line in lines:
        match = CONFIDENCE.search(line)
        if match:
            try:
                value = float(match.group(1))
            except ValueError:
                continue
            if 0.0 <= value <= 1.0:
                return value
    return None


def score(answers_path: Path, private_path: Path) -> dict:
    answers = {row["id"]: str(row.get("finalAnswer", "")) for row in load_jsonl(answers_path)}
    gold = {row["caseId"]: row["label"] for row in load_jsonl(private_path)}
    per_class: dict[str, Counter] = {label: Counter() for label in ("인용됨", "기각")}
    unparsed = 0
    correct = 0
    for case_id, label in gold.items():
        predicted = parse_conclusion(answers.get(case_id, ""))
        if not predicted:
            unparsed += 1
            per_class[label]["unparsed"] += 1
            continue
        if predicted == label:
            correct += 1
            per_class[label]["correct"] += 1
        else:
            per_class[label]["wrong"] += 1
    total = len(gold)
    # Exact binomial tail P(X >= correct | n=answered, p=0.5); unparsed counts
    # as wrong in the headline accuracy but is excluded from the tail test.
    answered = total - unparsed
    tail = sum(
        math.comb(answered, k) for k in range(correct, answered + 1)
    ) / (2 ** answered) if answered else 1.0
    confidence_points = {}
    for threshold in (0.7, 0.8, 0.9):
        covered = 0
        hits = 0
        for case_id, label in gold.items():
            answer = answers.get(case_id, "")
            conf = parse_confidence(answer)
            if conf is None or conf < threshold:
                continue
            predicted = parse_conclusion(answer)
            if not predicted:
                continue
            covered += 1
            if predicted == label:
                hits += 1
        confidence_points[f"conf>={threshold}"] = {
            "coverage": covered,
            "precision": round(hits / covered, 4) if covered else None,
        }
    return {
        "total": total,
        "correct": correct,
        "unparsed": unparsed,
        "accuracy": round(correct / total, 4) if total else 0.0,
        "answeredAccuracy": round(correct / answered, 4) if answered else 0.0,
        "binomialTailVsChance": tail,
        "perClass": {k: dict(v) for k, v in per_class.items()},
        "confidenceOperatingPoints": confidence_points,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["direct", "draft", "adjudicate", "score"])
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--public", type=Path, default=DEFAULT_PUBLIC)
    parser.add_argument("--private", type=Path, default=DEFAULT_PRIVATE)
    parser.add_argument("--codex-home", type=Path)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument("--num-drafts", type=int, default=3)
    parser.add_argument("--draft-indices", type=str, default="")
    parser.add_argument("--timeout-seconds", type=int, default=2700)
    parser.add_argument("--answers", type=Path)
    parser.add_argument("--protocol", choices=["worklog", "issues"], default="worklog")
    args = parser.parse_args()
    campaign = args.campaign_dir.resolve()

    if args.command == "score":
        answers = args.answers or (campaign / "adjudication/output/answers.jsonl")
        print(json.dumps(score(answers, args.private), ensure_ascii=False, indent=1))
        return 0

    if not args.codex_home:
        raise SystemExit("--codex-home is required for model arms")

    if args.command == "direct":
        role_dir = campaign / "direct"
        prepare_dir(role_dir, args.public, SOLVER_INSTRUCTIONS)
        receipt = run_role(
            role_dir,
            codex_home=args.codex_home,
            model=args.model,
            effort=args.reasoning_effort,
            timeout_seconds=args.timeout_seconds,
        )
        print(json.dumps(receipt, ensure_ascii=False))
        return 0 if receipt["status"] == "accepted" else 1

    if args.command == "draft":
        indices = (
            [int(part) for part in args.draft_indices.split(",") if part.strip()]
            if args.draft_indices
            else list(range(1, args.num_drafts + 1))
        )
        import concurrent.futures

        instructions = DRAFT_INSTRUCTIONS_ISSUES if args.protocol == "issues" else DRAFT_INSTRUCTIONS

        def one(index: int) -> dict:
            role_dir = campaign / f"drafts/d{index}"
            prepare_dir(role_dir, args.public, instructions)
            return {
                "draft": index,
                **run_role(
                    role_dir,
                    codex_home=args.codex_home,
                    model=args.model,
                    effort=args.reasoning_effort,
                    timeout_seconds=args.timeout_seconds,
                ),
            }

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(indices)) as pool:
            results = list(pool.map(one, indices))
        print(json.dumps(results, ensure_ascii=False))
        return 0 if all(r["status"] == "accepted" for r in results) else 1

    indices = [int(part) for part in args.draft_indices.split(",") if part.strip()] or [1, 2, 3]

    def reasoning_tokens(index: int) -> int:
        receipt_path = campaign / f"drafts/d{index}/run_receipt.json"
        usage = json.loads(receipt_path.read_text(encoding="utf-8")).get("tokenUsage") or {}
        return int(usage.get("reasoningOutputTokens") or 0)

    ordered = sorted(indices, key=reasoning_tokens, reverse=True)
    role_dir = campaign / "adjudication"
    prepare_dir(role_dir, args.public, ADJUDICATION_INSTRUCTIONS)
    candidates = role_dir / "input/candidates"
    candidates.mkdir(parents=True, exist_ok=True)
    for letter, index in zip("abc", ordered):
        shutil.copy2(campaign / f"drafts/d{index}/output/answers.jsonl", candidates / f"candidate_{letter}.jsonl")
    (role_dir / "candidate_order.json").write_text(
        json.dumps({"orderedDraftIndices": ordered}, ensure_ascii=False), encoding="utf-8"
    )
    receipt = run_role(
        role_dir,
        codex_home=args.codex_home,
        model=args.model,
        effort=args.reasoning_effort,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(receipt, ensure_ascii=False))
    return 0 if receipt["status"] == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
