#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared_platform.domain_adapters import get_domain_adapter


def build_mcq_split(
    questions: list[dict[str, Any]],
    *,
    benchmark_id: str,
    product: str,
    language: str,
    max_cases: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    answers: list[dict[str, str]] = []
    retrieval_targets: list[dict[str, Any]] = []
    for item in questions:
        if not bool(item.get("include", True)):
            continue
        case_id = str(item.get("id") or "").strip()
        prompt = str(item.get("question_text") or "").strip()
        answer = item.get("answer")
        if not case_id or not prompt or answer in (None, ""):
            continue
        metadata = dict(item.get("metadata") or {})
        metadata.setdefault("period", item.get("period"))
        metadata.setdefault("questionNumber", item.get("question_number"))
        cases.append(
            {
                "id": case_id,
                "prompt": prompt,
                "metadata": metadata,
                "graderRef": case_id,
            }
        )
        answer_id = str(answer).strip()
        answers.append({"caseId": case_id, "correctOptionId": answer_id})
        retrieval_target = build_mcq_retrieval_target(case_id=case_id, prompt=prompt, answer_id=answer_id, product=product)
        if retrieval_target:
            retrieval_targets.append(retrieval_target)
        if max_cases is not None and len(cases) >= max_cases:
            break
    public = {
        "schemaVersion": 1,
        "benchmarkId": benchmark_id,
        "taskType": "mcq",
        "product": product,
        "language": language,
        "cases": cases,
    }
    private = {
        "schemaVersion": 1,
        "benchmarkId": benchmark_id,
        "answers": answers,
        "retrievalTargetPolicy": {
            "version": "option_text_alias_v0",
            "claimability": "diagnostic_only",
            "blockers": ["text_target_option_only"],
        },
        "retrievalTargets": retrieval_targets,
        "scoring": {"invalidPrediction": "wrong"},
        "ablations": [
            {"name": "default_structure_on_heuristics_off", "env": {}},
            {"name": "mcq_heuristics_on", "env": {"RELIGION_MCQ_HEURISTICS_ENABLED": "1"}},
            {"name": "mcq_heuristics_off", "env": {"RELIGION_MCQ_HEURISTICS_ENABLED": "0"}},
            {"name": "mcq_structure_off", "env": {"RELIGION_MCQ_STRUCTURE_ENABLED": "0"}},
        ],
    }
    return public, private


def build_short_answer_split(
    questions: list[dict[str, Any]],
    *,
    benchmark_id: str,
    product: str,
    language: str,
    max_cases: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    answers: list[dict[str, str]] = []
    for item in questions:
        if not bool(item.get("include", True)):
            continue
        case_id = str(item.get("id") or "").strip()
        prompt = str(item.get("question_text") or "").strip()
        answer = str(item.get("answer") or "")
        if not case_id or not prompt or not answer:
            continue
        cases.append(
            {
                "id": case_id,
                "prompt": prompt,
                "metadata": {
                    "period": item.get("period"),
                    "questionNumber": item.get("question_number"),
                },
                "graderRef": case_id,
            }
        )
        answers.append({"caseId": case_id, "correctAnswer": answer})
        if max_cases is not None and len(cases) >= max_cases:
            break
    public = {
        "schemaVersion": 1,
        "benchmarkId": benchmark_id,
        "taskType": "short_answer",
        "product": product,
        "language": language,
        "cases": cases,
    }
    private = {
        "schemaVersion": 1,
        "benchmarkId": benchmark_id,
        "answers": answers,
        "scoring": {
            "comparison": "exact_unicode_string",
            "invalidPrediction": "wrong",
            "partialCredit": False,
        },
    }
    return public, private


def build_mcq_retrieval_target(*, case_id: str, prompt: str, answer_id: str, product: str = "") -> dict[str, Any]:
    target_text = _correct_option_text(prompt, answer_id)
    if not target_text:
        return {}
    target_texts = _target_text_aliases(target_text, product=product)
    return {
        "caseId": case_id,
        "targets": [{"textContains": text} for text in target_texts],
        "rankRules": {"primaryMustAppearWithin": 50},
    }


def _target_text_aliases(target_text: str, *, product: str = "") -> list[str]:
    texts = [str(target_text or "").strip()]
    adapter = get_domain_adapter(str(product or ""))
    texts.extend(adapter.option_aliases(target_text))
    out: list[str] = []
    for text in texts:
        cleaned = " ".join(str(text or "").split())
        if cleaned and cleaned not in out:
            out.append(cleaned)
    return out


def parse_cisi_misanswered_corpus(text: str) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    for block in re.split(r"\[오답 판정\]", str(text or "")):
        header = re.search(r"(\d{3})번\s*\|\s*AI:\s*[^|]+\|\s*정답:\s*([A-D])", block)
        if not header:
            continue
        number, answer = header.group(1), header.group(2)
        body = re.search(r"\n\s*(\d{3}\..*?)(?:\n\s*AI\s*[:：])", block, re.DOTALL)
        if not body:
            continue
        question_text = "\n".join(line.rstrip() for line in body.group(1).strip().splitlines()).strip()
        questions.append(
            {
                "id": f"islam-cisi-q{number}",
                "question_number": int(number),
                "question_text": question_text,
                "answer": answer,
                "include": True,
                "metadata": {"sourceQuestionNumber": number},
            }
        )
    return questions


ANSWER_LABEL_RE = re.compile(
    r"^\s*(?:정답|답)\s*[:：]\s*([A-Za-z]|\d{1,2}|[①②③④⑤⑥⑦⑧⑨⑩❶❷❸❹❺❻❼❽❾⓵⓶⓷⓸⓹])",
    re.MULTILINE,
)
AI_LABEL_RE = re.compile(r"^\s*AI\s*[:：].*$", re.MULTILINE)
QUESTION_START_RE = re.compile(r"(?m)^\s*(\d{1,4})[.)]\s+\S")
SHORT_ANSWER_QUESTION_START_RE = re.compile(r"(?m)^\s*(\d{1,4})[.)]\s*문제\s*[:：]\s*")
SHORT_ANSWER_AI_LABEL_RE = re.compile(r"(?m)^\s*AI\s*답변\s*[:：]")
SHORT_ANSWER_GOLD_RE = re.compile(r"(?m)^\s*정답\s*[:：]\s*(.*?)\s*$")
LEET_QUESTION_START_RE = re.compile(r"(?m)^\s*(\d{1,3})\s*\.\s*문제\s*:\s*")
LEET_AI_LABEL_RE = re.compile(r"(?m)^\s*AI\s*[:：]\s*(.*?)\s*$")
LEET_GOLD_RE = re.compile(
    r"(?m)^\s*정답\s*[:：]\s*([A-Za-z]|\d{1,2}|[①②③④⑤⑥⑦⑧⑨⑩❶❷❸❹❺❻❼❽❾⓵⓶⓷⓸⓹])"
)
LEET_PASSAGE_HEADER_RE = re.compile(
    r"(?m)^\s*\[(\d{1,3})(?:\s*[~～-]\s*(\d{1,3}))?번\s*제시문\]\s*$"
)
CIRCLED_OPTION_IDS = {
    "①": "1",
    "②": "2",
    "③": "3",
    "④": "4",
    "⑤": "5",
    "⑥": "6",
    "⑦": "7",
    "⑧": "8",
    "⑨": "9",
    "⑩": "10",
    "❶": "1",
    "❷": "2",
    "❸": "3",
    "❹": "4",
    "❺": "5",
    "❻": "6",
    "❼": "7",
    "❽": "8",
    "❾": "9",
    "⓵": "1",
    "⓶": "2",
    "⓷": "3",
    "⓸": "4",
    "⓹": "5",
}
MCQ_LETTER_OPTION_RE = re.compile(r"^\s*([A-Ea-e])[\.)、:：]\s+(.+?)\s*$")
MCQ_NUMERIC_OPTION_RE = re.compile(r"^\s*[\[(]?([1-9]\d?)[)\]、:：]\s+(.+?)\s*$")
MCQ_CIRCLED_OPTION_RE = re.compile(
    r"^\s*([①②③④⑤⑥⑦⑧⑨⑩❶❷❸❹❺❻❼❽❾⓵⓶⓷⓸⓹])\s*(.+?)\s*$"
)
MCQ_BARE_CIRCLED_OPTION_RE = re.compile(
    r"^\s*([①②③④⑤⑥⑦⑧⑨⑩❶❷❸❹❺❻❼❽❾⓵⓶⓷⓸⓹])\s*$"
)
MCQ_OCR_SEQUENCE_OPTION_RE = re.compile(
    r"^\s*(?:0[0-9]?\)?|0:|03|09\)|\([1-9]\d?|[1-9]\d?(?=\s)|Q@|OF|[@Q©®D])\s+(.+?)\s*$"
)


def parse_answer_labeled_mcq_text(
    text: str,
    *,
    id_prefix: str,
    source_name: str = "",
    period: int | str | None = None,
) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    starts = list(QUESTION_START_RE.finditer(str(text or "")))
    for index, match in enumerate(starts):
        block_start = match.start()
        block_end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        block = str(text[block_start:block_end]).strip()
        answer_match = ANSWER_LABEL_RE.search(block)
        if not answer_match:
            continue
        answer = _normalize_answer_id(answer_match.group(1))
        prompt_region = block[: answer_match.start()]
        prompt_region = AI_LABEL_RE.sub("", prompt_region)
        prompt = "\n".join(line.rstrip() for line in prompt_region.strip().splitlines()).strip()
        question_number = int(match.group(1))
        if not prompt or not answer:
            continue
        metadata = {"questionNumber": question_number}
        if source_name:
            metadata["sourceFile"] = source_name
        if period is not None:
            metadata["period"] = period
        questions.append(
            {
                "id": f"{id_prefix}-q{question_number:03d}",
                "question_number": question_number,
                "question_text": prompt,
                "answer": answer,
                "include": True,
                "period": period,
                "metadata": metadata,
            }
        )
    return questions


def parse_answer_labeled_short_answer_text(
    text: str,
    *,
    id_prefix: str,
    source_name: str = "",
    period: int | str | None = None,
) -> list[dict[str, Any]]:
    source = str(text or "")
    starts = list(SHORT_ANSWER_QUESTION_START_RE.finditer(source))
    questions: list[dict[str, Any]] = []
    for index, match in enumerate(starts):
        block_end = starts[index + 1].start() if index + 1 < len(starts) else len(source)
        block = source[match.start():block_end].strip()
        ai_match = SHORT_ANSWER_AI_LABEL_RE.search(block)
        answer_match = SHORT_ANSWER_GOLD_RE.search(block)
        if not ai_match or not answer_match or answer_match.start() < ai_match.start():
            continue
        question_number = int(match.group(1))
        question_body = block[match.end() - match.start():ai_match.start()].strip()
        answer = answer_match.group(1)
        if not question_body or not answer:
            continue
        metadata: dict[str, Any] = {"questionNumber": question_number}
        if source_name:
            metadata["sourceFile"] = source_name
        if period is not None:
            metadata["period"] = period
        questions.append(
            {
                "id": f"{id_prefix}-q{question_number:03d}",
                "question_number": question_number,
                "question_text": question_body,
                "answer": answer,
                "include": True,
                "period": period,
                "metadata": metadata,
            }
        )
    return questions


def parse_leet_mcq_text(
    text: str,
    *,
    id_prefix: str,
    source_name: str = "",
    section: str = "",
) -> list[dict[str, Any]]:
    source = str(text or "").lstrip("\ufeff")
    starts = list(LEET_QUESTION_START_RE.finditer(source))
    passages = _leet_passages_by_question(source, starts)
    questions: list[dict[str, Any]] = []
    for index, match in enumerate(starts):
        block_end = starts[index + 1].start() if index + 1 < len(starts) else len(source)
        block = source[match.start():block_end].strip()
        ai_match = LEET_AI_LABEL_RE.search(block)
        answer_match = LEET_GOLD_RE.search(block)
        if not ai_match or not answer_match or answer_match.start() < ai_match.start():
            continue
        question_number = int(match.group(1))
        question_body = block[:ai_match.start()].strip()
        passage = passages.get(question_number, "")
        prompt = f"[제시문]\n{passage}\n\n[문제]\n{question_body}" if passage else question_body
        answer = _normalize_answer_id(answer_match.group(1))
        historical_ai_answer = _leading_answer_id(ai_match.group(1))
        if not prompt or not answer:
            continue
        metadata: dict[str, Any] = {"questionNumber": question_number}
        if source_name:
            metadata["sourceFile"] = source_name
        if section:
            metadata["section"] = section
        questions.append(
            {
                "id": f"{id_prefix}-q{question_number:03d}",
                "question_number": question_number,
                "question_text": prompt,
                "answer": answer,
                "historical_ai_answer": historical_ai_answer,
                "include": True,
                "metadata": metadata,
            }
        )
    return questions


def _leading_answer_id(value: str) -> str:
    match = re.match(
        r"\s*([A-Za-z]|\d{1,2}|[①②③④⑤⑥⑦⑧⑨⑩❶❷❸❹❺❻❼❽❾⓵⓶⓷⓸⓹])",
        str(value or ""),
    )
    return _normalize_answer_id(match.group(1)) if match else ""


def _leet_passages_by_question(
    source: str,
    question_starts: list[re.Match[str]],
) -> dict[int, str]:
    passages: dict[int, str] = {}
    for header in LEET_PASSAGE_HEADER_RE.finditer(source):
        first_question = next((item for item in question_starts if item.start() > header.end()), None)
        if first_question is None:
            continue
        start_number = int(header.group(1))
        end_number = int(header.group(2) or start_number)
        if int(first_question.group(1)) != start_number:
            continue
        passage = source[header.end():first_question.start()].strip()
        if not passage:
            continue
        for question_number in range(start_number, end_number + 1):
            passages[question_number] = passage
    return passages


def parse_leet_mcq_zip(path: Path, *, id_prefix: str) -> list[dict[str, Any]]:
    section_specs = (
        ("언어이해", "language", "language_comprehension"),
        ("추론논증", "reasoning", "logical_reasoning"),
    )
    questions: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as archive:
        text_names = [name for name in archive.namelist() if name.endswith(".txt")]
        for filename_token, id_suffix, section in section_specs:
            matches = [
                name
                for name in text_names
                if filename_token in Path(name).name and "오답" not in Path(name).name
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"expected one {filename_token} source in {path}, found {len(matches)}: {matches}"
                )
            name = matches[0]
            raw = archive.read(name).decode("utf-8-sig")
            questions.extend(
                parse_leet_mcq_text(
                    raw,
                    id_prefix=f"{id_prefix}-{id_suffix}",
                    source_name=Path(name).name,
                    section=section,
                )
            )
    return questions


def parse_answer_labeled_mcq_zip(path: Path, *, id_prefix: str) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as archive:
        names = [
            name
            for name in archive.namelist()
            if name.endswith(".txt") and "문제_정답" in Path(name).name
        ]
        for name in sorted(names):
            raw = archive.read(name).decode("utf-8-sig")
            stem = _safe_id_part(Path(name).stem)
            questions.extend(
                parse_answer_labeled_mcq_text(
                    raw,
                    id_prefix=f"{id_prefix}-{stem}",
                    source_name=name,
                )
            )
    return questions


def _normalize_answer_id(value: str) -> str:
    raw = str(value or "").strip()
    if raw in CIRCLED_OPTION_IDS:
        return CIRCLED_OPTION_IDS[raw]
    return raw.upper() if re.fullmatch(r"[A-Za-z]", raw) else raw


def _correct_option_text(prompt: str, answer_id: str) -> str:
    option_texts = _option_texts_by_id(prompt)
    normalized = _normalize_answer_id(answer_id)
    if normalized in option_texts:
        return option_texts[normalized]
    if re.fullmatch(r"\d{1,2}", normalized) and option_texts:
        numeric_ids = sorted(int(option_id) for option_id in option_texts if re.fullmatch(r"\d{1,2}", option_id))
        if numeric_ids and int(normalized) > numeric_ids[-1]:
            return option_texts[str(numeric_ids[-1])]
    return ""


def _option_texts_by_id(prompt: str) -> dict[str, str]:
    option_texts: dict[str, str] = {}
    sequence_id = 0
    current_option_id = ""
    collect_wrapped_text = False
    for line in str(prompt or "").splitlines():
        parsed = _parse_explicit_option_line(line)
        if parsed is not None:
            option_id, text = parsed
            option_texts.setdefault(option_id, text)
            current_option_id = option_id
            collect_wrapped_text = False
            if re.fullmatch(r"\d{1,2}", option_id):
                sequence_id = max(sequence_id, int(option_id))
            continue
        bare_circled = MCQ_BARE_CIRCLED_OPTION_RE.match(line)
        if bare_circled:
            current_option_id = _normalize_answer_id(bare_circled.group(1))
            option_texts.setdefault(current_option_id, "")
            collect_wrapped_text = True
            continue
        sequence_text = _parse_ocr_sequence_option_line(line)
        if sequence_text:
            sequence_id += 1
            current_option_id = str(sequence_id)
            option_texts.setdefault(current_option_id, sequence_text)
            collect_wrapped_text = False
            continue
        continuation = _normalize_target_text(line)
        if collect_wrapped_text and current_option_id and continuation:
            option_texts[current_option_id] = _normalize_target_text(
                f"{option_texts.get(current_option_id, '')} {continuation}"
            )
    return option_texts


def _parse_explicit_option_line(line: str) -> tuple[str, str] | None:
    for pattern in (MCQ_CIRCLED_OPTION_RE, MCQ_NUMERIC_OPTION_RE, MCQ_LETTER_OPTION_RE):
        match = pattern.match(str(line or ""))
        if not match:
            continue
        option_id = _normalize_answer_id(match.group(1))
        text = _normalize_target_text(match.group(2))
        if option_id and text:
            return option_id, text
    return None


def _parse_ocr_sequence_option_line(line: str) -> str:
    match = MCQ_OCR_SEQUENCE_OPTION_RE.match(str(line or ""))
    if not match:
        return ""
    return _normalize_target_text(match.group(1))


def _normalize_target_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _safe_id_part(value: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z가-힣_-]+", "-", str(value or "").strip())
    safe = re.sub(r"-+", "-", safe).strip("-_")
    return safe or "source"


def build_legal_split(raw: dict[str, Any], *, benchmark_id: str, product: str) -> tuple[dict[str, Any], dict[str, Any]]:
    public_cases: list[dict[str, Any]] = []
    private_graders: list[dict[str, Any]] = []
    for case in raw.get("cases", []):
        case_id = str(case.get("id") or "").strip()
        if not case_id:
            continue
        rules = dict(case.get("rankRules") or {})
        queries = [str(query).strip() for query in case.get("queries", []) if str(query).strip()]
        public_cases.append(
            {
                "id": case_id,
                "language": "ko",
                "variants": [{"id": f"v{index}", "query": query} for index, query in enumerate(queries, start=1)],
                "runtime": {"candidateLimit": int(rules.get("candidateLimit") or 50)},
                "graderRef": case_id,
            }
        )
        primary_targets = list(case.get("primaryTargets") or [])
        if not primary_targets and case.get("primaryTarget"):
            primary_targets = [dict(case.get("primaryTarget") or {})]
        leakage_guards = {
            "forbiddenSearchMetadataTerms": list(case.get("forbiddenSearchMetadataTerms") or []),
            "forbiddenRuntimeFields": [
                "primaryTargets",
                "diagnosticTargets",
                "answerRules",
                "requiredAnswerText",
            ],
        }
        if leakage_guards["forbiddenSearchMetadataTerms"]:
            leakage_guards["forbiddenSearchMetadataTermsApplyTo"] = ["retrievedMetadata"]
        grader = {
            "graderId": case_id,
            "primaryTargets": primary_targets,
            "diagnosticTargets": list(case.get("relatedTargets") or case.get("diagnosticTargets") or []),
            "rankRules": rules,
            "leakageGuards": leakage_guards,
        }
        if case.get("answerRules"):
            grader["answerRules"] = dict(case.get("answerRules") or {})
        private_graders.append(grader)
    public = {
        "schemaVersion": 1,
        "benchmarkId": benchmark_id,
        "taskType": "legal_retrieval_answer",
        "product": product,
        "cases": public_cases,
    }
    private = {
        "schemaVersion": 1,
        "benchmarkId": benchmark_id,
        "graders": private_graders,
    }
    return public, private


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build public/private unified benchmark manifests.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    mcq = subparsers.add_parser("mcq")
    mcq.add_argument("--questions", type=Path, required=True)
    mcq.add_argument("--benchmark-id", required=True)
    mcq.add_argument("--product", required=True)
    mcq.add_argument("--language", default="ko")
    mcq.add_argument("--max-cases", type=int, default=None)
    mcq.add_argument("--public-out", type=Path, required=True)
    mcq.add_argument("--private-out", type=Path, required=True)

    cisi = subparsers.add_parser("cisi-islam")
    cisi.add_argument("--input", type=Path, required=True)
    cisi.add_argument("--benchmark-id", required=True)
    cisi.add_argument("--public-out", type=Path, required=True)
    cisi.add_argument("--private-out", type=Path, required=True)

    qa_text = subparsers.add_parser("qa-text")
    qa_text.add_argument("--input", type=Path, required=True)
    qa_text.add_argument("--id-prefix", required=True)
    qa_text.add_argument("--benchmark-id", required=True)
    qa_text.add_argument("--product", required=True)
    qa_text.add_argument("--language", default="ko")
    qa_text.add_argument("--max-cases", type=int, default=None)
    qa_text.add_argument("--public-out", type=Path, required=True)
    qa_text.add_argument("--private-out", type=Path, required=True)

    qa_zip = subparsers.add_parser("qa-zip")
    qa_zip.add_argument("--input", type=Path, required=True)
    qa_zip.add_argument("--id-prefix", required=True)
    qa_zip.add_argument("--benchmark-id", required=True)
    qa_zip.add_argument("--product", required=True)
    qa_zip.add_argument("--language", default="ko")
    qa_zip.add_argument("--max-cases", type=int, default=None)
    qa_zip.add_argument("--public-out", type=Path, required=True)
    qa_zip.add_argument("--private-out", type=Path, required=True)

    short_answer_text = subparsers.add_parser("short-answer-text")
    short_answer_text.add_argument("--input", type=Path, required=True)
    short_answer_text.add_argument("--id-prefix", required=True)
    short_answer_text.add_argument("--benchmark-id", required=True)
    short_answer_text.add_argument("--product", required=True)
    short_answer_text.add_argument("--language", default="ko")
    short_answer_text.add_argument("--max-cases", type=int, default=None)
    short_answer_text.add_argument("--public-out", type=Path, required=True)
    short_answer_text.add_argument("--private-out", type=Path, required=True)

    leet_zip = subparsers.add_parser("leet-zip")
    leet_zip.add_argument("--input", type=Path, required=True)
    leet_zip.add_argument("--id-prefix", required=True)
    leet_zip.add_argument("--benchmark-id", required=True)
    leet_zip.add_argument("--product", default="lawkey")
    leet_zip.add_argument("--language", default="ko")
    leet_zip.add_argument("--max-cases", type=int, default=None)
    leet_zip.add_argument("--public-out", type=Path, required=True)
    leet_zip.add_argument("--private-out", type=Path, required=True)

    legal = subparsers.add_parser("legal")
    legal.add_argument("--input", type=Path, required=True)
    legal.add_argument("--benchmark-id", required=True)
    legal.add_argument("--product", required=True)
    legal.add_argument("--public-out", type=Path, required=True)
    legal.add_argument("--private-out", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "mcq":
        questions = json.loads(args.questions.read_text(encoding="utf-8"))
        public, private = build_mcq_split(
            questions,
            benchmark_id=args.benchmark_id,
            product=args.product,
            language=args.language,
            max_cases=args.max_cases,
        )
    elif args.command == "cisi-islam":
        questions = parse_cisi_misanswered_corpus(args.input.read_text(encoding="utf-8-sig"))
        public, private = build_mcq_split(
            questions,
            benchmark_id=args.benchmark_id,
            product="islam",
            language="ko",
        )
    elif args.command == "qa-text":
        questions = parse_answer_labeled_mcq_text(
            args.input.read_text(encoding="utf-8-sig"),
            id_prefix=args.id_prefix,
            source_name=args.input.name,
        )
        public, private = build_mcq_split(
            questions,
            benchmark_id=args.benchmark_id,
            product=args.product,
            language=args.language,
            max_cases=args.max_cases,
        )
    elif args.command == "qa-zip":
        questions = parse_answer_labeled_mcq_zip(args.input, id_prefix=args.id_prefix)
        public, private = build_mcq_split(
            questions,
            benchmark_id=args.benchmark_id,
            product=args.product,
            language=args.language,
            max_cases=args.max_cases,
        )
    elif args.command == "short-answer-text":
        questions = parse_answer_labeled_short_answer_text(
            args.input.read_text(encoding="utf-8-sig"),
            id_prefix=args.id_prefix,
            source_name=args.input.name,
        )
        public, private = build_short_answer_split(
            questions,
            benchmark_id=args.benchmark_id,
            product=args.product,
            language=args.language,
            max_cases=args.max_cases,
        )
    elif args.command == "leet-zip":
        questions = parse_leet_mcq_zip(args.input, id_prefix=args.id_prefix)
        public, private = build_mcq_split(
            questions,
            benchmark_id=args.benchmark_id,
            product=args.product,
            language=args.language,
            max_cases=args.max_cases,
        )
    else:
        raw = json.loads(args.input.read_text(encoding="utf-8"))
        public, private = build_legal_split(raw, benchmark_id=args.benchmark_id, product=args.product)
    _write_json(args.public_out, public)
    _write_json(args.private_out, private)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
