#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared_platform.beta6 import Beta6JobManager, default_llm_client_from_env
from shared_platform.products import PRODUCT_PROFILES
from shared_platform.tcm_mcq import canonicalize_tcm_answer_number


ROOT = Path(__file__).resolve().parent
QUESTIONS_PATH = ROOT / "parsed" / "questions.json"
DEFAULT_OUTPUT_DIR = ROOT / "runs" / "beta6_baseline"

ANSWER_RE = re.compile(r"(?:정답|답|answer)\s*[:：]?\s*([1-5])", re.IGNORECASE)
STANDALONE_RE = re.compile(r"(?<!\d)([1-5])(?!\d)")


def _load_questions(path: Path) -> list[dict]:
    return [item for item in json.loads(path.read_text(encoding="utf-8")) if item.get("include")]


def _query_for_exam(question_text: str) -> str:
    return (
        f"{question_text}\n\n"
        "위 한의사 국가시험 객관식 문제의 정답 번호를 1~5 중 하나로 고르세요. "
        "답변 첫 줄은 반드시 `정답: <번호>` 형식으로 시작하세요."
    )


def _parse_prediction(answer: str, question_text: str) -> int | None:
    canonical = canonicalize_tcm_answer_number(answer, question_text)
    if canonical is not None:
        return canonical
    match = ANSWER_RE.search(answer or "")
    if match:
        return int(match.group(1))
    first_line = (answer or "").strip().splitlines()[0] if (answer or "").strip() else ""
    match = STANDALONE_RE.search(first_line)
    if match:
        return int(match.group(1))
    return None


def _summarize(records: list[dict]) -> dict:
    by_period: dict[str, dict] = {}
    for record in records:
        key = str(record["period"])
        bucket = by_period.setdefault(
            key,
            {"total": 0, "completed": 0, "predicted": 0, "correct": 0, "errors": 0},
        )
        bucket["total"] += 1
        if record.get("error"):
            bucket["errors"] += 1
        if record.get("answerReadiness") == "final_answer":
            bucket["completed"] += 1
        if record.get("prediction") is not None:
            bucket["predicted"] += 1
        if record.get("correct"):
            bucket["correct"] += 1
    total = {"total": 0, "completed": 0, "predicted": 0, "correct": 0, "errors": 0}
    for bucket in by_period.values():
        for key in total:
            total[key] += int(bucket.get(key) or 0)
        bucket["accuracy"] = bucket["correct"] / bucket["predicted"] if bucket["predicted"] else None
    total["accuracy"] = total["correct"] / total["predicted"] if total["predicted"] else None
    return {"total": total, "byPeriod": by_period}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the existing beta-6 engine on Kuksiwon TCM 81 questions.")
    parser.add_argument("--questions", type=Path, default=QUESTIONS_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--db-path", type=Path, default=Path("db-download/tcm/tcm.sqlite3"))
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--analysis-mode", default="fast")
    parser.add_argument("--max-questions", type=int, default=0)
    parser.add_argument("--start-index", type=int, default=1, help="1-based included-question start index.")
    parser.add_argument("--end-index", type=int, default=0, help="1-based included-question end index, inclusive; 0 means no end cap.")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--allow-no-llm", action="store_true")
    args = parser.parse_args()

    llm_client = default_llm_client_from_env()
    if llm_client is None and not args.allow_no_llm:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reason": "no_llm_client",
                    "detail": (
                        "Set RELIGION_LLM_PROVIDER/RELIGION_CHAT_API_URL or Gemini key env vars, "
                        "or pass --allow-no-llm for wiring smoke tests without answer accuracy."
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    db_path = args.db_path.resolve()
    profile = replace(PRODUCT_PROFILES["tcm"], db_path=db_path)
    all_questions = _load_questions(args.questions)
    start_index = max(1, int(args.start_index or 1))
    end_index = int(args.end_index or 0)
    questions = all_questions[start_index - 1 : end_index if end_index > 0 else None]
    if args.max_questions > 0:
        questions = questions[: args.max_questions]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    result_dir = args.output_dir / "results"
    result_dir.mkdir(parents=True, exist_ok=True)
    runtime = Beta6JobManager(
        {"tcm": profile},
        runs_root=args.output_dir / "beta6_jobs",
        llm_client=llm_client,
        resume_pending_jobs=False,
    )
    records: list[dict] = []
    started = time.time()
    try:
        for index, question in enumerate(questions, start=1):
            record_path = result_dir / f"{question['id']}.json"
            if args.resume and record_path.exists():
                existing = json.loads(record_path.read_text(encoding="utf-8"))
                if not existing.get("error") and existing.get("prediction") is not None:
                    records.append(existing)
                    continue
            record = {
                "id": question["id"],
                "period": question["period"],
                "questionNumber": question["question_number"],
                "gold": question["answer"],
                "prediction": None,
                "correct": False,
                "answerReadiness": "",
                "selectedCount": 0,
                "candidateCount": 0,
                "error": "",
            }
            try:
                result = runtime.answer_sync(
                    product="tcm",
                    query=_query_for_exam(question["question_text"]),
                    language="ko",
                    limit=args.limit,
                    analysis_mode=args.analysis_mode,
                )
                answer = str(result.get("answer") or "")
                prediction = _parse_prediction(answer, question["question_text"])
                beta6 = result.get("beta6") or {}
                record.update(
                    {
                        "prediction": prediction,
                        "correct": prediction == question["answer"],
                        "answerReadiness": result.get("answerReadiness", ""),
                        "selectedCount": beta6.get("selectedCount", 0),
                        "candidateCount": beta6.get("candidateCount", 0),
                        "selectorStatus": beta6.get("selectorStatus", ""),
                        "writerStatus": beta6.get("writerStatus", ""),
                        "llmUsed": bool(result.get("llmUsed")),
                        "jobId": result.get("jobId", ""),
                    }
                )
            except Exception as exc:
                record["error"] = str(exc)
            record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            records.append(record)
            if index % 10 == 0 or index == len(questions):
                summary = _summarize(records)["total"]
                print(
                    json.dumps(
                        {
                            "processed": index,
                            "total": len(questions),
                            "predicted": summary["predicted"],
                            "correct": summary["correct"],
                            "accuracy": summary["accuracy"],
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
    finally:
        runtime.shutdown(wait=False)

    summary = _summarize(records)
    summary["elapsedSec"] = round(time.time() - started, 3)
    summary["questionCount"] = len(questions)
    summary["questionStartIndex"] = start_index
    summary["questionEndIndex"] = start_index + len(questions) - 1 if questions else start_index - 1
    summary["dbPath"] = str(db_path)
    summary_path = args.output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
