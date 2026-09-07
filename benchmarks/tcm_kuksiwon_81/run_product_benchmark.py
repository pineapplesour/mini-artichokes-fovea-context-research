#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared_platform.tcm_mcq import canonicalize_tcm_answer_number


ROOT = Path(__file__).resolve().parent
QUESTIONS_PATH = ROOT / "parsed" / "questions.json"
DEFAULT_OUTPUT_DIR = ROOT / "runs" / "product_tcm"

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


def _json_request(
    url: str,
    *,
    method: str = "GET",
    body: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 60.0,
) -> dict:
    payload = None
    request_headers = dict(headers or {})
    if body is not None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=payload, headers=request_headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def _text_from_http_error(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read().decode("utf-8", errors="replace")
    except Exception:
        return str(exc)
    return body or str(exc)


def _with_job_params(path: str, *, base_url: str, access_token: str, session_token: str) -> str:
    params = urllib.parse.urlencode({"token": access_token, "session": session_token})
    return f"{base_url.rstrip('/')}{path}?{params}"


def _summarize(records: list[dict]) -> dict:
    total = {
        "total": len(records),
        "completed": sum(1 for item in records if item.get("answerReadiness") == "final_answer"),
        "predicted": sum(1 for item in records if item.get("prediction") is not None),
        "correct": sum(1 for item in records if item.get("correct")),
        "errors": sum(1 for item in records if item.get("error")),
    }
    total["accuracy"] = total["correct"] / total["predicted"] if total["predicted"] else None
    return {"total": total}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run TCM questions through the deployed psykey.ai.kr product API.")
    parser.add_argument("--base-url", default="https://psykey.ai.kr")
    parser.add_argument("--product", default="tcm")
    parser.add_argument("--questions", type=Path, default=QUESTIONS_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-questions", type=int, default=35)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--poll-timeout", type=float, default=1200.0)
    args = parser.parse_args()

    questions = _load_questions(args.questions)
    if args.max_questions > 0:
        questions = questions[: args.max_questions]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    result_dir = args.output_dir / "results"
    result_dir.mkdir(parents=True, exist_ok=True)

    session_token = secrets.token_hex(32)
    base_url = args.base_url.rstrip("/")
    product = args.product.strip("/")
    headers = {
        "Content-Type": "application/json",
        "X-Beta6-Session-Token": session_token,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36",
        "Origin": base_url,
        "Referer": f"{base_url}/{product}",
        "Accept": "application/json",
    }
    records: list[dict] = []
    started = time.time()

    for index, question in enumerate(questions, start=1):
        record_path = result_dir / f"{question['id']}.json"
        if args.resume and record_path.exists():
            existing = json.loads(record_path.read_text(encoding="utf-8"))
            if existing.get("answerReadiness") == "final_answer" or existing.get("prediction") is not None:
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
            "jobId": "",
            "accessToken": "",
            "sessionToken": session_token,
            "productBaseUrl": base_url,
        }
        try:
            created = _json_request(
                f"{base_url}/api/{product}/jobs",
                method="POST",
                body={
                    "query": _query_for_exam(question["question_text"]),
                    "language": "ko",
                    "limit": 50,
                    "analysisMode": "fast",
                },
                headers=headers,
                timeout=args.timeout,
            )
            job_id = str(created.get("jobId") or "")
            access_token = str(created.get("accessToken") or "")
            if not job_id:
                raise RuntimeError(f"product did not return jobId: {created}")
            record["jobId"] = job_id
            record["accessToken"] = access_token

            deadline = time.time() + args.poll_timeout
            status: dict = {}
            while time.time() < deadline:
                status = _json_request(
                    _with_job_params(f"/api/{product}/jobs/{job_id}", base_url=base_url, access_token=access_token, session_token=session_token),
                    headers=headers,
                    timeout=args.timeout,
                )
                if status.get("status") == "completed":
                    break
                if status.get("status") in {"cancelled", "failed", "interrupted"}:
                    raise RuntimeError(str(status.get("error") or status.get("status")))
                time.sleep(1.5)
            else:
                raise TimeoutError(f"product job did not complete within {args.poll_timeout:.0f}s")

            result = _json_request(
                _with_job_params(f"/api/{product}/jobs/{job_id}/result", base_url=base_url, access_token=access_token, session_token=session_token),
                headers=headers,
                timeout=args.timeout,
            )
            answer = str(result.get("answer") or result.get("answerMarkdown") or result.get("text") or "")
            prediction = _parse_prediction(answer, question["question_text"])
            beta6 = result.get("beta6") or {}
            record.update(
                {
                    "prediction": prediction,
                    "correct": prediction == question["answer"],
                    "answerReadiness": result.get("answerReadiness", ""),
                    "selectedCount": beta6.get("selectedCount", len(result.get("sources") or result.get("selectedEvidence") or [])),
                    "candidateCount": beta6.get("candidateCount", 0),
                    "selectorStatus": beta6.get("selectorStatus", ""),
                    "writerStatus": beta6.get("writerStatus", ""),
                    "writerProvider": beta6.get("writerProvider", ""),
                    "llmUsed": bool(result.get("llmUsed")),
                    "answerPreview": answer[:500],
                    "status": status,
                }
            )
        except urllib.error.HTTPError as exc:
            record["error"] = _text_from_http_error(exc)
        except Exception as exc:
            record["error"] = str(exc)

        record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        records.append(record)
        if index % 5 == 0 or index == len(questions):
            summary = _summarize(records)["total"]
            print(
                json.dumps(
                    {
                        "processed": index,
                        "total": len(questions),
                        "predicted": summary["predicted"],
                        "correct": summary["correct"],
                        "accuracy": summary["accuracy"],
                        "errors": summary["errors"],
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )

    summary = _summarize(records)
    summary["elapsedSec"] = round(time.time() - started, 3)
    summary["questionCount"] = len(questions)
    summary["baseUrl"] = base_url
    summary["product"] = product
    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
