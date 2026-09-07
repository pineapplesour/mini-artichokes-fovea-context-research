#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from pypdf import PdfReader


SOURCE_HASHES = {
    "AQA_원본_AQA-806215-QP-JUN22.PDF": "83a930600ffe91ae1a8321b1cbc0c5af3c49e616656cf93de269887994a3b3f4",
    "AQA_원본_AQA-806215-MS-JUN22.PDF": "303360b22016709337dfaade6169c4540359447a97f37d31272ba692e63cdca0",
    "AQA_원본_AQA-806215-QP-JUN23.PDF": "6f05cc90088f8b5f0ec6c465412d5994647f224df134a1f8d63b3485e2b32fd0",
    "AQA_원본_AQA-806215-MS-JUN23.PDF": "fa0715930877f449607df88bb02419861b841f379ee805b31114017803cb7bc2",
    "해외공식_BYU_Official_Islam_Multiple_Choice_Quiz.pdf": "07faac9365d97cfd0e580529a03bbd901d105eabbf65fa82e83e4648b0a3f92b",
    "해외공식_Cambridge_2068_2025_Specimen_Paper_1.pdf": "e1549be5512c25cbb7a299f8cb50be6074253099b670633fb14f7c19877f8355",
    "해외공식_Cambridge_2068_2025_Specimen_Paper_1_Mark_Scheme.pdf": "7c689fae82ebaca8a6cb37d0af6ba0e60a5f58d755d9bb74e8683c147164c022",
    "해외공식_Cambridge_2068_2025_Specimen_Paper_2.pdf": "225e9fb45ca8010e158363c60e268abf949dde188e9d4af9373ce431e6bd971f",
    "해외공식_Cambridge_2068_2025_Specimen_Paper_2_Mark_Scheme.pdf": "166cd306c7d0fce8f5e9b1d1d4f0f3effd5aa5ad16e43b372547503c3cea2c74",
}

AQA_MARKER = re.compile(r"(?m)^\s*0\s*([12])\s*\.\s*([1-5])\s+")
CAMBRIDGE_MARKER = re.compile(r"(?m)^\s*([1-6])\(([a-c])\)\s+")

CAMBRIDGE_P1_Q5_SOURCE = (
    "Source: Surah 63:9–11 (Yusuf Ali). O you who believe, do not let your riches or children "
    "divert you from the remembrance of God; those who do so are the losers. Spend in charity "
    "from what God has bestowed before death comes and a person asks for a short respite to give "
    "charity and do good. God grants no soul respite once its appointed time has come and knows "
    "all that people do."
)
CAMBRIDGE_P1_Q6_SOURCE = (
    "Source: Hadith No. 12, 'Not interfering with others' (An-Nawawi's Forty Hadith): "
    "'Part of someone's being a good Muslim is his leaving alone that which does not concern him.'"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pdf_text(path: Path, *, start_page: int = 0, end_page: int | None = None) -> str:
    pages = PdfReader(path).pages[start_page:end_page]
    return "\n".join(page.extract_text() or "" for page in pages)


def compact(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def clean_aqa_segment(text: str, *, year: int) -> str:
    text = re.sub(
        rf"MARK SCHEME\s*[–-]\s*GCSE RELIGIOUS STUDIES A\s*[–-]\s*8062/15\s*[–-]\s*JUNE {year}\s+\d+",
        " ",
        text,
        flags=re.I,
    )
    return compact(text)


def clean_cambridge_segment(text: str, *, paper: int) -> str:
    text = re.sub(
        rf"2068/0{paper}\s+Cambridge O Level\s*[–-]\s*Mark Scheme\s+For examination\s+SPECIMEN\s+from 2025",
        " ",
        text,
        flags=re.I,
    )
    text = re.sub(r"Page\s+\d+\s+of\s+14", " ", text, flags=re.I)
    text = re.sub(r"© Cambridge University Press & Assessment 2022", " ", text)
    text = re.sub(r"Question\s+Answer\s+Marks", " ", text, flags=re.I)
    return compact(text)


def split_segments(text: str, marker: re.Pattern[str]) -> list[tuple[re.Match[str], str]]:
    matches = list(marker.finditer(text))
    return [
        (match, text[match.start() : matches[index + 1].start() if index + 1 < len(matches) else len(text)])
        for index, match in enumerate(matches)
    ]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_aqa(source_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    public_cases: list[dict[str, Any]] = []
    private_answers: list[dict[str, Any]] = []
    for year in (2022, 2023):
        path = source_root / f"AQA_원본_AQA-806215-MS-JUN{str(year)[-2:]}.PDF"
        segments = split_segments(pdf_text(path, start_page=6), AQA_MARKER)
        if [(m.group(1), m.group(2)) for m, _ in segments] != [
            (section, part) for section in ("1", "2") for part in ("1", "2", "3", "4", "5")
        ]:
            raise ValueError(f"unexpected AQA question structure: {path}")
        for match, raw_segment in segments:
            section, part = match.group(1), match.group(2)
            segment = clean_aqa_segment(raw_segment, year=year)
            before_target, separator, _ = segment.partition("Target:")
            if not separator:
                raise ValueError(f"AQA target marker missing: {year} {section}.{part}")
            body = re.sub(r"^0\s*([12])\s*\.\s*([1-5])\s+", "", before_target).strip()
            max_match = re.search(r"\[(\d+)\s+marks?\]", body, flags=re.I)
            if not max_match:
                raise ValueError(f"AQA mark value missing: {year} {section}.{part}")
            content_marks = int(max_match.group(1))
            spag_match = re.search(r"(?:Plus\s+)?SPaG\s+(\d+)\s+marks?", body, flags=re.I)
            spag_marks = int(spag_match.group(1)) if spag_match else 0
            max_marks = content_marks + spag_marks
            case_id = f"islam-aqa-{year}-{section}{part}"
            response_format = "mcq" if part == "1" else "constructed_response"
            if response_format == "mcq":
                question, _, option_text = body.partition(max_match.group(0))
                options = re.findall(r"\b([A-D])\s+(.+?)(?=\s+[A-D]\s+|$)", option_text.strip())
                if len(options) != 4:
                    raise ValueError(f"AQA options did not parse: {year} {section}.{part}")
                prompt = question.strip() + "\n\n" + "\n".join(f"{label}. {value.strip()}" for label, value in options)
                answer_match = re.search(r"\bAnswer:\s*([A-D])\b", segment)
                if not answer_match:
                    raise ValueError(f"AQA answer missing: {year} {section}.{part}")
                private_row: dict[str, Any] = {
                    "caseId": case_id,
                    "responseFormat": response_format,
                    "maxMarks": max_marks,
                    "correctOptionIds": [answer_match.group(1)],
                }
            else:
                prompt = body
                private_row = {
                    "caseId": case_id,
                    "responseFormat": response_format,
                    "maxMarks": max_marks,
                    "officialMarkScheme": segment,
                }
            public_cases.append(
                {
                    "id": case_id,
                    "prompt": prompt,
                    "metadata": {
                        "sourceFamily": "AQA GCSE Religious Studies A 8062/15 Islam",
                        "year": year,
                        "questionPart": f"0{section}.{part}",
                        "responseFormat": response_format,
                        "maxMarks": max_marks,
                        "contentMarks": content_marks,
                        "spagMarks": spag_marks,
                    },
                    "graderRef": case_id,
                }
            )
            private_answers.append(private_row)
    if len(public_cases) != 20 or len(private_answers) != 20:
        raise ValueError("AQA20 count mismatch")
    return (
        {
            "schemaVersion": 1,
            "benchmarkId": "official.islam.aqa8062_15.2022_2023.v1",
            "taskType": "mixed_official_assessment",
            "product": "islam",
            "language": "en",
            "cases": public_cases,
        },
        {
            "schemaVersion": 1,
            "benchmarkId": "official.islam.aqa8062_15.2022_2023.v1",
            "answers": private_answers,
            "sourcePolicy": "official AQA final mark schemes; all valid material permitted where stated",
        },
    )


def build_byu(source_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    text = pdf_text(source_root / "해외공식_BYU_Official_Islam_Multiple_Choice_Quiz.pdf")
    question_text, separator, answer_text = text.partition("Answers:")
    if not separator:
        raise ValueError("BYU printed answer key missing")
    question_matches = list(re.finditer(r"(?m)^\s*(\d{1,2})\.\s+", question_text))
    if [int(match.group(1)) for match in question_matches] != list(range(1, 17)):
        raise ValueError("unexpected BYU question structure")
    answer_pairs = re.findall(r"(\d{1,2})\s+([^;]+)(?:;|$)", compact(answer_text))
    answer_map = {
        int(number): [label.upper() for label in re.findall(r"[a-e]", labels, flags=re.I)]
        for number, labels in answer_pairs
    }
    if sorted(answer_map) != list(range(1, 17)) or any(not labels for labels in answer_map.values()):
        raise ValueError("BYU answer key did not parse")
    public_cases: list[dict[str, Any]] = []
    private_answers: list[dict[str, Any]] = []
    for index, match in enumerate(question_matches):
        number = int(match.group(1))
        end = question_matches[index + 1].start() if index + 1 < len(question_matches) else len(question_text)
        block = question_text[match.end() : end].strip()
        option_matches = list(re.finditer(r"(?m)^\s*([a-e])\.\s+", block, flags=re.I))
        if len(option_matches) < 4:
            raise ValueError(f"BYU options missing for question {number}")
        question = compact(block[: option_matches[0].start()])
        options: list[tuple[str, str]] = []
        for option_index, option_match in enumerate(option_matches):
            option_end = option_matches[option_index + 1].start() if option_index + 1 < len(option_matches) else len(block)
            options.append((option_match.group(1).upper(), compact(block[option_match.end() : option_end])))
        case_id = f"islam-byu-q{number:03d}"
        public_cases.append(
            {
                "id": case_id,
                "prompt": question + "\n\n" + "\n".join(f"{label}. {value}" for label, value in options),
                "metadata": {
                    "sourceFamily": "BYU official Islam multiple-choice quiz",
                    "questionNumber": number,
                    "responseFormat": "mcq",
                    "multipleSelection": len(answer_map[number]) > 1,
                    "maxMarks": 1,
                },
                "graderRef": case_id,
            }
        )
        private_answers.append(
            {
                "caseId": case_id,
                "responseFormat": "mcq",
                "maxMarks": 1,
                "correctOptionIds": answer_map[number],
            }
        )
    return (
        {
            "schemaVersion": 1,
            "benchmarkId": "official.islam.byu_mcq16.v1",
            "taskType": "mcq",
            "product": "islam",
            "language": "en",
            "cases": public_cases,
        },
        {
            "schemaVersion": 1,
            "benchmarkId": "official.islam.byu_mcq16.v1",
            "answers": private_answers,
            "sourcePolicy": "printed answer key in the official source PDF",
        },
    )


def cambridge_shared_instructions(source_root: Path, *, paper: int) -> str:
    path = source_root / f"해외공식_Cambridge_2068_2025_Specimen_Paper_{paper}_Mark_Scheme.pdf"
    text = pdf_text(path, start_page=2, end_page=4)
    return clean_cambridge_segment(text, paper=paper)


def build_cambridge(source_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    public_cases: list[dict[str, Any]] = []
    private_answers: list[dict[str, Any]] = []
    shared: dict[str, str] = {}
    for paper in (1, 2):
        path = source_root / f"해외공식_Cambridge_2068_2025_Specimen_Paper_{paper}_Mark_Scheme.pdf"
        segments = split_segments(pdf_text(path), CAMBRIDGE_MARKER)
        expected = [
            (str(question), part)
            for question in range(1, 7)
            for part in (("a", "b", "c") if question <= 4 else ("a", "b"))
        ]
        if [(m.group(1), m.group(2)) for m, _ in segments] != expected:
            raise ValueError(f"unexpected Cambridge question structure: paper {paper}")
        shared[str(paper)] = cambridge_shared_instructions(source_root, paper=paper)
        for match, raw_segment in segments:
            question, part = int(match.group(1)), match.group(2)
            segment = clean_cambridge_segment(raw_segment, paper=paper)
            body = re.sub(rf"^{question}\({part}\)\s+", "", segment).strip()
            boundary = re.search(r"\b(?:Award one mark|Use Table [AB])\b", body)
            if not boundary:
                raise ValueError(f"Cambridge rubric boundary missing: paper {paper} {question}{part}")
            prompt = body[: boundary.start()].strip()
            max_marks = {"a": 4, "b": 10, "c": 6}[part] if question <= 4 else {"a": 12, "b": 8}[part]
            if paper == 1 and question == 5:
                prompt = CAMBRIDGE_P1_Q5_SOURCE + "\n\n" + prompt
            elif paper == 1 and question == 6:
                prompt = CAMBRIDGE_P1_Q6_SOURCE + "\n\n" + prompt
            prompt = f"{prompt} [{max_marks} marks]"
            case_id = f"islam-cambridge-2068-p{paper}-q{question}{part}"
            public_cases.append(
                {
                    "id": case_id,
                    "prompt": prompt,
                    "metadata": {
                        "sourceFamily": "Cambridge O Level Islamic Studies 2068 2025 specimen",
                        "paper": paper,
                        "questionPart": f"{question}({part})",
                        "responseFormat": "constructed_response",
                        "maxMarks": max_marks,
                    },
                    "graderRef": case_id,
                }
            )
            private_answers.append(
                {
                    "caseId": case_id,
                    "responseFormat": "constructed_response",
                    "maxMarks": max_marks,
                    "sharedMarkingInstructionsRef": f"paper{paper}",
                    "officialMarkScheme": segment,
                }
            )
    if len(public_cases) != 32 or len(private_answers) != 32:
        raise ValueError("Cambridge32 count mismatch")
    return (
        {
            "schemaVersion": 1,
            "benchmarkId": "official.islam.cambridge2068.2025_specimen.v1",
            "taskType": "constructed_response",
            "product": "islam",
            "language": "en",
            "cases": public_cases,
        },
        {
            "schemaVersion": 1,
            "benchmarkId": "official.islam.cambridge2068.2025_specimen.v1",
            "answers": private_answers,
            "sharedMarkingInstructions": {f"paper{paper}": value for paper, value in shared.items()},
            "sourcePolicy": "official Cambridge specimen mark schemes; all valid material permitted where stated",
        },
    )


def verify_sources(source_root: Path) -> None:
    missing = [name for name in SOURCE_HASHES if not (source_root / name).is_file()]
    if missing:
        raise FileNotFoundError(f"missing official source files: {missing}")
    mismatches = {
        name: sha256_file(source_root / name)
        for name, expected in SOURCE_HASHES.items()
        if sha256_file(source_root / name) != expected
    }
    if mismatches:
        raise ValueError(f"official source hash mismatch: {mismatches}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the missing keyed Islam official-source manifests.")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("benchmarks/unified"))
    args = parser.parse_args()
    source_root = args.source_root.resolve()
    verify_sources(source_root)
    aqa_public, aqa_private = build_aqa(source_root)
    byu_public, byu_private = build_byu(source_root)
    cambridge_public, cambridge_private = build_cambridge(source_root)
    outputs = {
        "official_islam_aqa20.public.json": aqa_public,
        "official_islam_aqa20.private.json": aqa_private,
        "official_islam_byu16.public.json": byu_public,
        "official_islam_byu16.private.json": byu_private,
        "official_islam_cambridge32.public.json": cambridge_public,
        "official_islam_cambridge32.private.json": cambridge_private,
    }
    for name, payload in outputs.items():
        write_json(args.output_dir / name, payload)
    print(json.dumps({"status": "ok", "counts": {"aqa": 20, "byu": 16, "cambridge": 32}}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
