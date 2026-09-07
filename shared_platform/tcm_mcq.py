from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TcmMcqOption:
    number: int
    text: str
    marker: str = ""


@dataclass(frozen=True)
class TcmMcq:
    stem: str
    options: tuple[TcmMcqOption, ...]


_OPTION_MARKER_PATTERN = (
    r"@®|Q@|@@|@\)|@[1-9]|①|②|③|④|⑤|❶|❷|❸|❹|❺|⓵|⓶|⓷|⓸|⓹|"
    r"0[1-9]|69|63|\(0[1-9]\)?|\([1-9]\)?|OF|0|[1-9]|@|®|©|D|Q|O"
)

_OPTION_LINE_RE = re.compile(
    rf"^\s*(?P<marker>{_OPTION_MARKER_PATTERN})(?:\s*[\)\.\:]|\s+)\s*(?P<text>.+?)\s*$",
    flags=re.UNICODE,
)

_INLINE_OPTION_RE = re.compile(
    rf"(?:(?<=\s)|^)(?P<marker>{_OPTION_MARKER_PATTERN})(?:\s*[\)\.\:]|\s+)\s*"
    rf"(?P<text>.+?)(?=(?:(?<=\s)(?:{_OPTION_MARKER_PATTERN})(?:\s*[\)\.\:]|\s+))|$)",
    flags=re.UNICODE,
)

_ANSWER_VALUE_RE = re.compile(
    rf"(?:정답|답|answer)\s*[:：]?\s*(?P<value>{_OPTION_MARKER_PATTERN}|[1-5])(?:\s*[\)\.\:])?",
    flags=re.IGNORECASE | re.UNICODE,
)
_STANDALONE_ANSWER_RE = re.compile(
    rf"^\s*(?P<value>{_OPTION_MARKER_PATTERN}|[1-5])(?:\s*[\)\.\:]|\s+|$)",
    flags=re.IGNORECASE | re.UNICODE,
)
_DIRECT_ANSWER_MARKER_MAP = {
    "①": 1,
    "❶": 1,
    "⓵": 1,
    "②": 2,
    "❷": 2,
    "⓶": 2,
    "③": 3,
    "❸": 3,
    "⓷": 3,
    "④": 4,
    "❹": 4,
    "⓸": 4,
    "⑤": 5,
    "❺": 5,
    "⓹": 5,
}
_EXAM_INSTRUCTION_SUFFIX_RE = re.compile(
    r"(?:\s*\|\s*|\s+|^)"
    r"(?:"
    r"위\s+한의사\s+국가시험\s+객관식\s+문제|"
    r"답변\s+첫\s+줄|"
    r"정답\s*번호(?:를|는)?|"
    r"Valid\s+answer\s+numbers|"
    r"Return\s+the\s+first\s+line"
    r").*$",
    flags=re.IGNORECASE | re.UNICODE | re.DOTALL,
)

_FORMULA_ALIASES: dict[str, tuple[str, ...]] = {
    "육미지황환": ("육미지황원", "六味地黃丸", "六味地黃元"),
    "육미지황탕": ("육미지황원", "六味地黃湯", "六味地黃元"),
    "팔미지황환": ("팔미지황원", "八味地黃丸", "八味地黃元"),
    "귀비탕": ("歸脾湯",),
    "비원전": ("秘元煎",),
    "소요산": ("逍遙散",),
    "내소산": ("內消散",),
    "육울탕": ("六鬱湯",),
    "좌귀환": ("左歸丸",),
    "목향순기산": ("木香順氣散",),
    "목향파기산": ("木香破氣散",),
    "소자강기탕": ("蘇子降氣湯",),
    "익위승양탕": ("益胃升陽湯",),
    "조중익기탕": ("調中益氣湯",),
    "사군자탕": ("四君子湯",),
    "수비전": ("壽脾煎",),
    "대보음환": ("大補陰丸",),
    "보심건비탕": ("補心健脾湯",),
    "보양환오탕": ("補陽還五湯",),
    "보익양위탕": ("補益養胃湯",),
    "천왕보심단": ("天王補心丹",),
    "신출환": ("神朮丸", "神出丸"),
    "난간전": ("暖肝煎",),
    "온담탕": ("溫膽湯",),
    "온청음": ("溫淸飮", "温清饮"),
    "용담사간탕": ("龍膽瀉肝湯",),
    "익기보혈탕": ("益氣補血湯",),
    "양위탕": ("養胃湯",),
    "청위산": ("淸胃散", "清胃散"),
    "가미단삼음": ("加味丹蔘飮",),
    "조위승기탕": ("調胃承氣湯",),
}


def parse_tcm_mcq(text: str) -> TcmMcq | None:
    raw_text = strip_tcm_exam_instruction_text(str(text or "").replace("\u3000", " "))
    if not raw_text.strip():
        return None
    return _parse_tcm_mcq_lines(raw_text) or _parse_tcm_mcq_inline(raw_text)


def strip_tcm_exam_instruction_text(text: str) -> str:
    raw = str(text or "").replace("\u3000", " ")
    return _EXAM_INSTRUCTION_SUFFIX_RE.sub("", raw).strip()


def tcm_mcq_search_text(text: str) -> str:
    raw = strip_tcm_exam_instruction_text(text)
    parsed = parse_tcm_mcq(raw)
    if parsed is None:
        return raw
    parts = [parsed.stem, *(option.text for option in parsed.options)]
    return "\n".join(part for part in parts if part).strip()


def _parse_tcm_mcq_lines(raw_text: str) -> TcmMcq | None:
    stem_lines: list[str] = []
    option_entries: list[tuple[str, str]] = []
    for raw_line in raw_text.splitlines():
        line = " ".join(raw_line.split())
        if not line:
            continue
        match = _OPTION_LINE_RE.match(line)
        if match and not _looks_like_problem_stem_line(match.group("marker"), match.group("text"), line):
            option_text = _clean_option_text(match.group("text"))
            if option_text:
                option_entries.append((match.group("marker"), option_text))
            continue
        if option_entries:
            option_entries[-1] = (
                option_entries[-1][0],
                _clean_option_text(f"{option_entries[-1][1]} {line}"),
            )
        else:
            stem_lines.append(_strip_problem_number_line(line))
    if len(option_entries) < 3:
        return None
    return TcmMcq(stem=" ".join(stem_lines).strip(), options=_number_options_by_order(option_entries))


def _parse_tcm_mcq_inline(raw_text: str) -> TcmMcq | None:
    raw = " ".join(raw_text.split())
    if not raw:
        return None
    split_at = _inline_option_start(raw)
    stem_source = raw[:split_at] if split_at > 0 else ""
    option_source = raw[split_at:] if split_at > 0 else re.sub(r"^\s*\d{1,3}\s*[\.)]\s*", "", raw)
    matches = list(_INLINE_OPTION_RE.finditer(option_source))
    option_entries = [
        (match.group("marker"), _clean_option_text(match.group("text")))
        for match in matches
        if _clean_option_text(match.group("text"))
    ]
    if len(option_entries) < 3:
        return None
    stem = _strip_problem_number_line(stem_source.strip()) if stem_source else option_source[: matches[0].start()].strip()
    return TcmMcq(stem=stem, options=_number_options_by_order(option_entries))


def _inline_option_start(raw: str) -> int:
    cue_patterns = (
        r"치방은\?",
        r"처방은\?",
        r"방제는\?",
        r"무엇인가\?",
        r"어느\s*것인가\?",
    )
    for pattern in cue_patterns:
        match = re.search(pattern, raw)
        if match:
            return match.end()
    return 0


def _number_options_by_order(option_entries: list[tuple[str, str]]) -> tuple[TcmMcqOption, ...]:
    return tuple(
        TcmMcqOption(number=index, text=text, marker=marker)
        for index, (marker, text) in enumerate(option_entries[:5], start=1)
    )


def _looks_like_problem_stem_line(marker: str, text: str, line: str) -> bool:
    if marker == "0" or not re.fullmatch(r"[1-9]", marker or ""):
        return False
    if not re.match(r"^\s*\d{1,3}\s*[\.)]\s+", line):
        return False
    return bool(
        re.search(
            r"(세|남자|여자|환자|병원|왔다|호소|치방|처방|무엇|어느|한다|하였다|되었다|않다|\?)",
            text,
        )
    )


def _strip_problem_number_line(line: str) -> str:
    return re.sub(r"^\s*\d{1,3}\s*[\.)]\s+", "", line).strip()


def canonicalize_tcm_answer_number(answer: str, question_text: str) -> int | None:
    parsed = parse_tcm_mcq(question_text)
    if not parsed:
        return _direct_answer_number(answer)
    first_line = (answer or "").strip().splitlines()[0] if (answer or "").strip() else ""
    match = _ANSWER_VALUE_RE.search(answer or "") or _STANDALONE_ANSWER_RE.search(first_line)
    if match:
        value = match.group("value")
        direct = _direct_answer_number(value)
        if direct is not None:
            return direct
        marker_number = _option_number_for_marker(parsed, value)
        if marker_number is not None:
            return marker_number
    return _option_number_for_answer_text(parsed, first_line or answer)


def _direct_answer_number(value: str) -> int | None:
    for marker, number in _DIRECT_ANSWER_MARKER_MAP.items():
        if marker in (value or ""):
            return number
    match = re.search(r"(?<!\d)([1-5])(?!\d)", value or "")
    if not match:
        return None
    return int(match.group(1))


def _option_number_for_marker(parsed: TcmMcq, marker: str) -> int | None:
    normalized = _normalize_marker(marker)
    if not normalized:
        return None
    matches = [option.number for option in parsed.options if _normalize_marker(option.marker) == normalized]
    return matches[0] if len(matches) == 1 else None


def _option_number_for_answer_text(parsed: TcmMcq, answer: str) -> int | None:
    normalized_answer = _compact_text(answer)
    if not normalized_answer:
        return None
    matches: list[int] = []
    for option in parsed.options:
        for term in tcm_option_aliases(option.text):
            normalized_term = _compact_text(term)
            if normalized_term and normalized_term in normalized_answer:
                matches.append(option.number)
                break
    return matches[0] if len(matches) == 1 else None


def _normalize_marker(value: str) -> str:
    marker = str(value or "").strip()
    marker = re.sub(r"[\s\)\.\:]+$", "", marker)
    marker = re.sub(r"^\(", "", marker)
    return marker


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def tcm_mcq_option_terms(text: str) -> list[str]:
    parsed = parse_tcm_mcq(text)
    if not parsed:
        return []
    terms: list[str] = []
    for option in parsed.options:
        for term in tcm_option_aliases(option.text):
            if term not in terms:
                terms.append(term)
    return terms


def tcm_option_aliases(option_text: str) -> list[str]:
    cleaned = _clean_option_text(option_text)
    if not cleaned:
        return []
    aliases = [cleaned]
    normalized_key = re.sub(r"\s+", "", cleaned)
    for key, values in _FORMULA_ALIASES.items():
        if key in normalized_key or normalized_key in key:
            aliases.extend(values)
    out: list[str] = []
    for value in aliases:
        term = _clean_option_text(value)
        if term and term not in out:
            out.append(term)
    return out


def tcm_mcq_prompt_block(text: str) -> str:
    parsed = parse_tcm_mcq(text)
    if not parsed:
        return ""
    lines = ["[TCM MCQ STRUCTURE]", f"stem: {parsed.stem}"]
    for option in parsed.options:
        aliases = [term for term in tcm_option_aliases(option.text) if term != option.text]
        alias_text = f" aliases={', '.join(aliases)}" if aliases else ""
        lines.append(f"{option.number}) {option.text}{alias_text}")
    lines.append(
        "When source records include distractor option names, choose the option whose evidence matches the stem condition; "
        "a source that merely names a formula without matching the stem is weak evidence."
    )
    lines.append(
        "Valid answer numbers are only the canonical option order numbers 1, 2, 3, 4, and 5. "
        "Return the first line exactly as: 정답: <number>) <option text>. "
        "Do not output OCR markers such as 0), 6, @, ®, ©, D, Q, or Q@ as the answer number."
    )
    return "\n".join(lines)


def _clean_option_text(value: str) -> str:
    text = " ".join(str(value or "").split())
    text = strip_tcm_exam_instruction_text(text)
    text = re.sub(r"^\(?\d+/?\s*$", "", text)
    text = re.sub(r"\s*\(\d+/\s*$", "", text)
    text = text.strip(" `\"'[]{}|")
    return text[:80]
