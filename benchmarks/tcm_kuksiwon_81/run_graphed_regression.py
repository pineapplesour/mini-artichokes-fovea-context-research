#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared_platform.beta6 import Beta6JobManager, default_llm_client_from_env
from shared_platform.products import PRODUCT_PROFILES
from shared_platform.tcm_mcq import canonicalize_tcm_answer_number


ROOT = Path(__file__).resolve().parent
QUESTIONS_PATH = ROOT / "parsed" / "questions.json"
DEFAULT_DB_PATH = REPO_ROOT / "db-download" / "tcm" / "tcm.sqlite3"
RUNS_ROOT = ROOT / "runs"

ANSWER_RE = re.compile(r"(?:정답|답|answer)\s*[:：]?\s*([1-5])", re.IGNORECASE)
STANDALONE_RE = re.compile(r"(?<!\d)([1-5])(?!\d)")


def _load_questions(path: Path) -> list[dict[str, Any]]:
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
    return int(match.group(1)) if match else None


def _run_output_dir(prefix: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return RUNS_ROOT / f"{prefix}_{timestamp}"


def _question_slice(questions: list[dict[str, Any]], *, start_index: int, end_index: int, max_questions: int) -> list[dict[str, Any]]:
    start = max(1, int(start_index or 1))
    end = int(end_index or 0)
    sliced = questions[start - 1 : end if end > 0 else None]
    if max_questions > 0:
        sliced = sliced[:max_questions]
    return sliced


def _load_baseline_records(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    result_dir = path / "results" if (path / "results").exists() else path
    if not result_dir.exists():
        return {}
    records: dict[str, dict[str, Any]] = {}
    for record_path in sorted(result_dir.glob("*.json")):
        if record_path.name.endswith(".result.json"):
            continue
        try:
            data = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        question_id = str(data.get("id") or record_path.stem)
        if question_id:
            records[question_id] = data
    return records


def _comparison(record: dict[str, Any], baseline: dict[str, Any] | None) -> dict[str, Any]:
    if not baseline:
        return {"baselinePrediction": None, "baselineCorrect": None, "delta": "no_baseline"}
    current_correct = bool(record.get("correct"))
    baseline_correct = bool(baseline.get("correct"))
    if current_correct and not baseline_correct:
        delta = "improved"
    elif baseline_correct and not current_correct:
        delta = "regressed"
    elif current_correct and baseline_correct:
        delta = "same_correct"
    else:
        delta = "same_wrong"
    return {
        "baselinePrediction": baseline.get("prediction"),
        "baselineCorrect": baseline.get("correct"),
        "delta": delta,
    }


def _compact_sources(result: dict[str, Any], limit: int = 8) -> list[dict[str, str]]:
    sources = result.get("selectedEvidence") or result.get("sources") or []
    compact: list[dict[str, str]] = []
    if not isinstance(sources, list):
        return compact
    for source in sources[:limit]:
        if not isinstance(source, dict):
            continue
        compact.append(
            {
                "label": str(source.get("label") or source.get("source_label") or ""),
                "citation": str(source.get("citation") or source.get("title") or source.get("file_id") or "")[:240],
                "role": str(source.get("role") or source.get("sourceRole") or ""),
            }
        )
    return compact


def _record_from_result(question: dict[str, Any], result: dict[str, Any], *, elapsed_sec: float) -> dict[str, Any]:
    answer = str(result.get("answer") or result.get("answerMarkdown") or "")
    prediction = _parse_prediction(answer, str(question["question_text"]))
    beta6 = result.get("beta6") if isinstance(result.get("beta6"), dict) else {}
    writer = result.get("writer") if isinstance(result.get("writer"), dict) else {}
    selector = result.get("selector") if isinstance(result.get("selector"), dict) else {}
    return {
        "id": question["id"],
        "period": question["period"],
        "questionNumber": question["question_number"],
        "gold": question["answer"],
        "prediction": prediction,
        "correct": prediction == question["answer"],
        "elapsedSec": round(elapsed_sec, 3),
        "answerReadiness": result.get("answerReadiness", ""),
        "selectedCount": beta6.get("selectedCount", len(result.get("selectedEvidence") or result.get("sources") or [])),
        "candidateCount": beta6.get("candidateCount", 0),
        "claimCardCount": beta6.get("claimCardCount", len(result.get("claimCards") or [])),
        "candidateClaimCount": beta6.get("candidateClaimCount", len(result.get("candidateClaimCards") or [])),
        "citedClaimCount": beta6.get("citedClaimCount", len(result.get("citedClaimCards") or [])),
        "selectorStatus": beta6.get("selectorStatus", selector.get("status", "")),
        "selectorProvider": beta6.get("selectorProvider", selector.get("provider", "")),
        "selectionSource": beta6.get("selectionSource", selector.get("selectionSource", "")),
        "selectorLocalRecoveryCount": beta6.get("selectorLocalRecoveryCount", 0),
        "writerStatus": beta6.get("writerStatus", writer.get("status", "")),
        "writerProvider": beta6.get("writerProvider", writer.get("provider", "")),
        "writerCacheHit": bool(beta6.get("writerCacheHit")),
        "llmUsed": bool(result.get("llmUsed")),
        "jobId": result.get("jobId", ""),
        "stageTimingTotalSec": beta6.get("stageTimingTotalSec"),
        "stageTimingTotals": beta6.get("stageTimingTotals", {}),
        "answerPreview": answer[:900],
        "selectedSources": _compact_sources(result),
        "candidateClaimIds": result.get("candidateClaimIds", []),
        "citedClaimIds": result.get("citedClaimIds", []),
        "artifacts": result.get("artifacts", {}),
        "error": "",
    }


def _error_record(question: dict[str, Any], *, elapsed_sec: float, error: str) -> dict[str, Any]:
    return {
        "id": question["id"],
        "period": question["period"],
        "questionNumber": question["question_number"],
        "gold": question["answer"],
        "prediction": None,
        "correct": False,
        "elapsedSec": round(elapsed_sec, 3),
        "answerReadiness": "",
        "selectedCount": 0,
        "candidateCount": 0,
        "claimCardCount": 0,
        "candidateClaimCount": 0,
        "citedClaimCount": 0,
        "selectorStatus": "",
        "selectorProvider": "",
        "selectionSource": "",
        "selectorLocalRecoveryCount": 0,
        "writerStatus": "",
        "writerProvider": "",
        "writerCacheHit": False,
        "llmUsed": False,
        "jobId": "",
        "stageTimingTotalSec": None,
        "stageTimingTotals": {},
        "answerPreview": "",
        "selectedSources": [],
        "candidateClaimIds": [],
        "citedClaimIds": [],
        "artifacts": {},
        "error": error,
    }


def _summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = {
        "total": len(records),
        "completed": sum(1 for item in records if item.get("answerReadiness") == "final_answer"),
        "predicted": sum(1 for item in records if item.get("prediction") is not None),
        "correct": sum(1 for item in records if item.get("correct")),
        "errors": sum(1 for item in records if item.get("error")),
        "elapsedSec": round(sum(float(item.get("elapsedSec") or 0.0) for item in records), 3),
    }
    total["accuracy"] = total["correct"] / total["predicted"] if total["predicted"] else None
    deltas: dict[str, int] = {}
    for item in records:
        delta = str(item.get("comparison", {}).get("delta") or "no_baseline")
        deltas[delta] = deltas.get(delta, 0) + 1
    by_period: dict[str, dict[str, Any]] = {}
    for item in records:
        key = str(item.get("period") or "")
        bucket = by_period.setdefault(key, {"total": 0, "completed": 0, "predicted": 0, "correct": 0, "errors": 0})
        bucket["total"] += 1
        bucket["completed"] += 1 if item.get("answerReadiness") == "final_answer" else 0
        bucket["predicted"] += 1 if item.get("prediction") is not None else 0
        bucket["correct"] += 1 if item.get("correct") else 0
        bucket["errors"] += 1 if item.get("error") else 0
    for bucket in by_period.values():
        bucket["accuracy"] = bucket["correct"] / bucket["predicted"] if bucket["predicted"] else None
    return {"total": total, "byPeriod": by_period, "comparison": deltas}


def _write_markdown_report(path: Path, *, summary: dict[str, Any], records: list[dict[str, Any]], args: argparse.Namespace) -> None:
    total = summary["total"]
    lines = [
        "# TCM Graphed Regression",
        "",
        f"- Questions: {summary.get('questionStartIndex')}..{summary.get('questionEndIndex')}",
        f"- DB: `{summary.get('dbPath')}`",
        f"- Limit: {summary.get('limit')}",
        f"- Completed: {total['completed']}/{total['total']}",
        f"- Predicted: {total['predicted']}/{total['total']}",
        f"- Correct: {total['correct']}/{total['predicted']}",
        f"- Accuracy: {_format_accuracy(total.get('accuracy'))}",
        f"- Elapsed: {total['elapsedSec']} sec",
        f"- Baseline: `{args.baseline_dir}`" if args.baseline_dir else "- Baseline: none",
        "",
        "| # | id | gold | pred | ok | sec | base | delta | selected | claims | selector | writer |",
        "|---:|---|---:|---:|:---:|---:|---:|---|---:|---:|---|---|",
    ]
    for index, record in enumerate(records, start=int(summary.get("questionStartIndex") or 1)):
        comparison = record.get("comparison") if isinstance(record.get("comparison"), dict) else {}
        lines.append(
            "| "
            + " | ".join(
                [
                    str(index),
                    str(record.get("id") or ""),
                    str(record.get("gold") or ""),
                    str(record.get("prediction") if record.get("prediction") is not None else ""),
                    "Y" if record.get("correct") else "N",
                    str(record.get("elapsedSec") or ""),
                    str(comparison.get("baselinePrediction") if comparison.get("baselinePrediction") is not None else ""),
                    str(comparison.get("delta") or ""),
                    str(record.get("selectedCount") or 0),
                    str(record.get("claimCardCount") or 0),
                    str(record.get("selectorStatus") or ""),
                    str(record.get("writerStatus") or ""),
                ]
            )
            + " |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _format_accuracy(value: Any) -> str:
    return "n/a" if value is None else f"{float(value) * 100:.1f}%"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the current graphed beta-6 TCM engine on Kuksiwon questions.")
    parser.add_argument("--questions", type=Path, default=QUESTIONS_PATH)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--baseline-dir", type=Path, default=None)
    parser.add_argument("--start-index", type=int, default=1, help="1-based included-question start index.")
    parser.add_argument("--end-index", type=int, default=0, help="1-based included-question end index, inclusive; 0 means no cap.")
    parser.add_argument("--max-questions", type=int, default=0)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--analysis-mode", default="fast")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--allow-no-llm", action="store_true")
    parser.add_argument("--run-prefix", default="graphed_tcm_regression")
    args = parser.parse_args()

    llm_client = default_llm_client_from_env()
    if llm_client is None and not args.allow_no_llm:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reason": "no_llm_client",
                    "detail": "Set the Mint/Gemini gateway env vars or pass --allow-no-llm.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    db_path = args.db_path.resolve()
    if not db_path.exists():
        print(json.dumps({"status": "blocked", "reason": "missing_db", "dbPath": str(db_path)}, ensure_ascii=False, indent=2))
        return 2

    questions = _question_slice(
        _load_questions(args.questions),
        start_index=args.start_index,
        end_index=args.end_index,
        max_questions=args.max_questions,
    )
    if not questions:
        print(json.dumps({"status": "blocked", "reason": "no_questions"}, ensure_ascii=False, indent=2))
        return 2

    output_dir = args.output_dir or _run_output_dir(args.run_prefix)
    output_dir.mkdir(parents=True, exist_ok=True)
    result_dir = output_dir / "results"
    result_dir.mkdir(parents=True, exist_ok=True)
    baseline_records = _load_baseline_records(args.baseline_dir)
    profile = replace(PRODUCT_PROFILES["tcm"], db_path=db_path)
    runtime = Beta6JobManager(
        {"tcm": profile},
        runs_root=output_dir / "beta6_jobs",
        llm_client=llm_client,
        resume_pending_jobs=False,
    )

    records: list[dict[str, Any]] = []
    started = time.time()
    question_start_index = max(1, int(args.start_index or 1))
    try:
        for offset, question in enumerate(questions):
            question_index = question_start_index + offset
            record_path = result_dir / f"{question['id']}.json"
            if args.resume and record_path.exists():
                record = json.loads(record_path.read_text(encoding="utf-8"))
            else:
                item_started = time.time()
                try:
                    result = runtime.answer_sync(
                        product="tcm",
                        query=_query_for_exam(str(question["question_text"])),
                        language="ko",
                        limit=args.limit,
                        analysis_mode=args.analysis_mode,
                    )
                    record = _record_from_result(question, result, elapsed_sec=time.time() - item_started)
                except Exception as exc:
                    record = _error_record(question, elapsed_sec=time.time() - item_started, error=str(exc))
                record["questionIndex"] = question_index
                record["comparison"] = _comparison(record, baseline_records.get(str(question["id"])))
                record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            records.append(record)
            partial = _summarize(records)["total"]
            print(
                json.dumps(
                    {
                        "processed": len(records),
                        "total": len(questions),
                        "id": record.get("id"),
                        "gold": record.get("gold"),
                        "prediction": record.get("prediction"),
                        "correct": record.get("correct"),
                        "accuracy": partial["accuracy"],
                        "elapsedSec": record.get("elapsedSec"),
                        "delta": record.get("comparison", {}).get("delta"),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
    finally:
        runtime.shutdown(wait=False)

    summary = _summarize(records)
    summary.update(
        {
            "elapsedSec": round(time.time() - started, 3),
            "questionCount": len(questions),
            "questionStartIndex": question_start_index,
            "questionEndIndex": question_start_index + len(questions) - 1,
            "dbPath": str(db_path),
            "limit": args.limit,
            "analysisMode": args.analysis_mode,
            "writerProvider": str(getattr(llm_client, "provider", "") or ""),
            "baselineDir": str(args.baseline_dir) if args.baseline_dir else "",
            "outputDir": str(output_dir),
        }
    )
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "records.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown_report(output_dir / "report.md", summary=summary, records=records, args=args)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
