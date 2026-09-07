#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parent
PAGES_DIR = ROOT / "ocr" / "pages"
COLUMN_DIR = ROOT / "ocr" / "question_columns"
PARSED_DIR = ROOT / "parsed"
ANSWER_KEY_PATH = PARSED_DIR / "answer_key.json"
QUESTIONS_PATH = PARSED_DIR / "questions.json"

EXPECTED_COUNTS = {1: 80, 2: 100, 3: 80, 4: 80}
COLUMN_BOXES = {
    "left": (245, 500, 1510, 3980),
    "right": (1595, 500, 2905, 3980),
}
QUESTION_START_RE = re.compile(r"^\s*[/|]?\s*(\d{1,3})\s*[.．,，](?:\s+(.*)|\s*$)")


@dataclass(frozen=True)
class ColumnTask:
    period: int
    page_number: int
    side: str
    image_path: Path
    crop_path: Path
    text_path: Path


def _page_paths(period: int) -> list[Path]:
    return sorted(PAGES_DIR.glob(f"p{period}-*.png"))


def _make_tasks() -> list[ColumnTask]:
    tasks: list[ColumnTask] = []
    for period in sorted(EXPECTED_COUNTS):
        for page_path in _page_paths(period):
            page_number = int(page_path.stem.split("-")[1])
            if page_number == 1:
                continue
            for side in ("left", "right"):
                stem = f"p{period}-{page_number:02d}-{side}"
                tasks.append(
                    ColumnTask(
                        period=period,
                        page_number=page_number,
                        side=side,
                        image_path=page_path,
                        crop_path=COLUMN_DIR / f"{stem}.png",
                        text_path=COLUMN_DIR / f"{stem}.txt",
                    )
                )
    return tasks


def _crop_column(task: ColumnTask) -> None:
    COLUMN_DIR.mkdir(parents=True, exist_ok=True)
    image = Image.open(task.image_path).convert("L")
    crop = ImageOps.autocontrast(image.crop(COLUMN_BOXES[task.side]))
    crop.save(task.crop_path)


def _ocr_column(task: ColumnTask, *, force: bool) -> None:
    if task.text_path.exists() and task.text_path.stat().st_size > 0 and not force:
        return
    _crop_column(task)
    completed = subprocess.run(
        [
            "tesseract",
            str(task.crop_path),
            "stdout",
            "-l",
            "kor+eng",
            "--psm",
            "6",
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    task.text_path.write_text(completed.stdout, encoding="utf-8")


def _normalize_text(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        if "제81회 한의사 국가시험" in line:
            continue
        if "각 문제에서 가장 적합한 답" in line:
            continue
        lines.append(line)
    return "\n".join(lines)


def _split_questions(period: int, tasks: list[ColumnTask]) -> dict[int, str]:
    ordered = [
        task
        for task in sorted(tasks, key=lambda item: (item.page_number, 0 if item.side == "left" else 1))
        if task.period == period
    ]
    current_number: int | None = None
    current_lines: list[str] = []
    chunks: list[tuple[int, list[str]]] = []

    def flush() -> None:
        nonlocal current_number, current_lines
        if current_number is None:
            current_lines = []
            return
        chunks.append((current_number, current_lines))
        current_number = None
        current_lines = []

    for task in ordered:
        text = task.text_path.read_text(encoding="utf-8", errors="replace")
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            match = QUESTION_START_RE.match(line)
            if match:
                number = int(match.group(1))
                flush()
                current_number = number
                remainder = (match.group(2) or "").strip()
                current_lines = [remainder] if remainder else []
                continue
            if current_number is not None:
                current_lines.append(line)
    flush()

    parsed: dict[int, str] = {}
    expected_next = 1
    for ocr_number, lines in chunks:
        if expected_next > EXPECTED_COUNTS[period]:
            break
        if ocr_number == expected_next:
            assigned_number = expected_next
        elif expected_next < ocr_number <= expected_next + 3:
            assigned_number = ocr_number
        else:
            assigned_number = expected_next
        text = _normalize_text("\n".join(lines))
        parsed[assigned_number] = f"{assigned_number}. {text}" if text else f"{assigned_number}."
        expected_next = assigned_number + 1
    return parsed


def _load_answer_key() -> list[dict]:
    return json.loads(ANSWER_KEY_PATH.read_text(encoding="utf-8"))


def _build_questions(tasks: list[ColumnTask]) -> tuple[list[dict], dict]:
    answer_records = _load_answer_key()
    by_period = {period: _split_questions(period, tasks) for period in EXPECTED_COUNTS}
    questions: list[dict] = []
    diagnostics: dict[str, object] = {"periods": {}}

    for period, expected_count in EXPECTED_COUNTS.items():
        found_numbers = set(by_period[period])
        diagnostics["periods"][str(period)] = {
            "expected": expected_count,
            "found": len(found_numbers),
            "missing": [number for number in range(1, expected_count + 1) if number not in found_numbers],
            "extra": sorted(number for number in found_numbers if number > expected_count),
        }

    answer_by_key = {(item["period"], item["question_number"]): item for item in answer_records}
    for period, expected_count in EXPECTED_COUNTS.items():
        for number in range(1, expected_count + 1):
            answer = answer_by_key.get((period, number), {})
            answer_kind = answer.get("answer_kind", "")
            question_text = by_period[period].get(number, "")
            if answer_kind != "numeric":
                include = False
                skip_reason = answer_kind or "non_numeric_answer"
            elif not question_text:
                include = False
                skip_reason = "missing_ocr_text"
            else:
                include = True
                skip_reason = ""
            questions.append(
                {
                    "id": f"tcm81-p{period}-q{number:03d}",
                    "period": period,
                    "question_number": number,
                    "question_text": question_text,
                    "answer": answer.get("answer"),
                    "answer_kind": answer_kind,
                    "include": include,
                    "skip_reason": skip_reason,
                    "ocr_char_count": len(question_text),
                }
            )

    diagnostics["total"] = len(questions)
    diagnostics["included"] = sum(1 for item in questions if item["include"])
    diagnostics["skipped"] = sum(1 for item in questions if not item["include"])
    return questions, diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract OCR question records for Kuksiwon TCM 81 benchmark.")
    parser.add_argument("--force-ocr", action="store_true", help="Re-run Tesseract even when column OCR files exist.")
    parser.add_argument("--jobs", type=int, default=4, help="Parallel Tesseract workers.")
    args = parser.parse_args()

    tasks = _make_tasks()
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as executor:
        futures = [executor.submit(_ocr_column, task, force=args.force_ocr) for task in tasks]
        for future in as_completed(futures):
            future.result()

    PARSED_DIR.mkdir(parents=True, exist_ok=True)
    questions, diagnostics = _build_questions(tasks)
    QUESTIONS_PATH.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")
    (PARSED_DIR / "question_extraction_diagnostics.json").write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(diagnostics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
