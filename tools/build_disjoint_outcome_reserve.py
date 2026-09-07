#!/usr/bin/env python3
"""Build a sealed, source-disjoint candidate inventory for outcome prediction.

This tool does not call a model and does not score a solver.  It constructs an
oversampled public/private inventory that can subsequently be label-audited and
then deterministically reduced to a confirmatory reserve.

The closure is deliberately conservative.  Every historical outcome JSONL is
read, every historical private canonical ID is resolved against the precedent
database, and a new row is excluded when it overlaps any historical identity
key, normalized public prompt, or (by default) historical source dataset.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.build_outcome_prediction_benchmark import (  # noqa: E402
    CLASSES,
    FACTS_HEAD,
    FACTS_HEAD_TAX,
    PROMPT_TEMPLATE,
    TAX_NAME_SQL,
    extract_facts,
    label_from_holding,
    split_sections,
)


DEFAULT_PRIOR_DIR = REPO_ROOT / "benchmarks" / "outcome_prediction"
REQUIRED_DB_COLUMNS = (
    "canonical_id",
    "source_dataset",
    "court",
    "case_number",
    "decision_date",
    "case_name",
    "full_text",
    "text_hash",
    "source_record_id",
    "source_path",
    "dedupe_key",
    "dedupe_key_primary",
    "dedupe_key_fallback",
    "split_group_id",
)
PRIVATE_REQUIRED_KEYS = (
    "caseId",
    "label",
    "caseRef",
    "canonicalId",
    "decisionDate",
    "holding",
)
PUBLIC_REQUIRED_KEYS = (
    "id",
    "prompt",
)
IDENTITY_NAMES = (
    "canonicalId",
    "caseRef",
    "caseNumber",
    "sourceRecordId",
    "sourceDatasetRecordId",
    "sourcePathLocator",
    "dedupeKey",
    "dedupeKeyPrimary",
    "dedupeKeyFallback",
    "textHash",
    "splitGroupId",
    "promptSHA256",
    "sourcePromptSHA256",
    "claimContentSHA256",
    "factsContentSHA256",
    "claimFactsContentSHA256",
)
DB_TO_IDENTITY = {
    "canonical_id": "canonicalId",
    "dedupe_key": "dedupeKey",
    "dedupe_key_primary": "dedupeKeyPrimary",
    "dedupe_key_fallback": "dedupeKeyFallback",
    "text_hash": "textHash",
    "split_group_id": "splitGroupId",
}
PUBLIC_CONTENT_IDENTITY_NAMES = (
    "claimContentSHA256",
    "factsContentSHA256",
    "claimFactsContentSHA256",
)
LEDGER_HASH_NAMES = (
    "normalizedPromptSHA256",
    *PUBLIC_CONTENT_IDENTITY_NAMES,
)
PRIVATE_KIND_RE = re.compile(r"(?:^|[._-])private(?:[._-]|$)")
PUBLIC_KIND_RE = re.compile(r"(?:^|[._-])public(?:[._-]|$)")
CASE_REF_SEPARATOR = "|"
CASE_NUMBER_CIVIL = re.compile(r"(?:가단|가합|가소)")
CASE_NUMBER_TAX = re.compile(r"(?:구합|구단)")
CLAIM_HOLDING_POINTER = re.compile(
    r"주\s*문(?:\s*제\s*\d+(?:\s*의\s*[가-힣0-9]+)?\s*항)?\s*(?:과|기재와|내용과)?\s*같",
    re.IGNORECASE,
)
SECTION_HOLDING_MARKER = re.compile(r"(?:^|\n)\s*\[?\s*주\s*문\s*\]?\s*(?:\n|$)")
EVIDENCE_SEGMENTATION_VERSION = "normalized-line-sentence-bounded-v3"
# Keep a numbered evidence unit short enough that two generators can be
# required to cite the complete same unit.  This avoids treating two disjoint
# snippets from one long legal sentence as the same decisive evidence.
MAX_EVIDENCE_CLAUSE_CHARS = 240
SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?。！？])\s+")
ENUMERATOR_ONLY_RE = re.compile(r"^(?:\(?\d+\)?|[가-힣A-Za-z])[.)]$")
EVIDENCE_SEGMENTATION_SPEC = {
    "version": EVIDENCE_SEGMENTATION_VERSION,
    "unicodeNormalization": "NFKC",
    "primaryBoundary": "Python str.splitlines over the extracted source field",
    "sentenceBoundaryRegex": SENTENCE_BOUNDARY_RE.pattern,
    "enumeratorMergeRegex": ENUMERATOR_ONLY_RE.pattern,
    "maxClauseCharacters": MAX_EVIDENCE_CLAUSE_CHARS,
    "longClauseSplit": "prefer the last whitespace at or before maxClauseCharacters; hard split only when absent",
    "withinClauseWhitespace": "all whitespace collapsed to one ASCII space and stripped",
    "emptyLines": "omitted",
    "roundtripInvariant": "NFKC source and emitted clause texts are equal after removing all whitespace",
    "claimIds": "C followed by a one-based, zero-padded three-digit ordinal",
    "factsIds": "F followed by a one-based, zero-padded three-digit ordinal",
}

TARGET_METADATA_REDACTION_VERSION = "paired-target-metadata-redaction-v1"
TARGET_METADATA_PLACEHOLDERS = {
    "court": "【대상법원】",
    "caseNumber": "【대상사건번호】",
    "decisionDate": "【대상판결일】",
}
TARGET_METADATA_REDACTION_SPEC = {
    "version": TARGET_METADATA_REDACTION_VERSION,
    "scope": "paired target court, case number, and decision date in public claim/facts only",
    "goldIndependent": "uses only court, case_number, and decision_date source metadata",
    "unicodeNormalization": "NFKC",
    "courtMatching": (
        "full target court after whitespace/punctuation-flexible matching, with "
        "지법<->지방법원, 고법<->고등법원, 행법<->행정법원, and "
        "가법<->가정법원 aliases"
    ),
    "caseNumberMatching": (
        "validated YY-or-YYYY+Korean-case-code+numeric-serial components, including "
        "joined/participating case lists and inherited serials, with arbitrary whitespace "
        "or common punctuation between characters"
    ),
    "decisionDateMatching": (
        "validated YYYY-MM-DD metadata matched as Korean, ISO, slash, or dotted date "
        "with optional leading zeroes and whitespace"
    ),
    "placeholders": TARGET_METADATA_PLACEHOLDERS,
    "postcondition": "zero target-specific matches after public prompt rendering",
    "unredactedClosure": (
        "prior/internal prompt and claim/facts content hashes use the original extracted text"
    ),
}
TARGET_METADATA_REDACTION_SPEC_SHA256 = hashlib.sha256(
    json.dumps(
        TARGET_METADATA_REDACTION_SPEC,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
).hexdigest()
TARGET_SEPARATOR_PATTERN = r"[\s._,·ㆍ:;/\\-]*"
GENERIC_COURT_LOCATORS = {
    "법원",
    "지방법원",
    "고등법원",
    "행정법원",
    "가정법원",
    "지원",
}

CLAIM_HEADING_RE = re.compile(r"(?m)^\s*\[청구취지(?:\s+근거절)?\]\s*$")
FACTS_HEADING_RE = re.compile(
    r"(?m)^\s*\[(?:기초사실|처분의\s*경위)(?:\s+근거절)?\]\s*$"
)
GENERIC_HEADING_RE = re.compile(r"(?m)^\s*\[[^\]\n]{1,80}\]\s*$")
CONTENT_TAIL_RE = re.compile(
    r"(?m)^\s*(?:다음\s+두\s+가지\s+중|판단\s+절차|답변\s+형식|출력\s+형식)"
)
CLAUSE_ID_PREFIX_RE = re.compile(r"(?m)^\s*\[(?:C|F)\d{3}\]\s*")

TAX_FACTS_ONLY_SOURCE_TEMPLATE = """다음은 대한민국 조세 행정소송 제1심 사건의 처분 경위입니다.
법원의 최종 결론(주문)과 판단 부분은 제거되어 있습니다. 오직 아래 내용만 근거로,
납세자(원고)가 다투는 이 사건 부과처분에 대한 법원의 결론을 예측하십시오.

[처분의 경위]
{facts}

다음 두 가지 중 정확히 하나로 답하십시오.
- 인용됨: 처분이 전부 또는 일부라도 취소됨 (납세자 승소)
- 기각: 처분이 그대로 유지됨 (과세관청 승소)
첫 줄에 결론 한 단어(인용됨 또는 기각)만 쓰고, 둘째 줄부터 두세 문장으로 핵심 근거를 쓰십시오."""

TAX_FACTS_ONLY_CLAUSE_TEMPLATE = """다음은 대한민국 조세 행정소송 제1심 사건의 처분 경위입니다.
법원의 최종 결론(주문)과 판단 부분은 제거되어 있습니다. 오직 아래 번호가 붙은 근거절만 근거로,
납세자(원고)가 다투는 이 사건 부과처분에 대한 법원의 결론을 예측하십시오.

[처분의 경위 근거절]
{facts}

다음 두 가지 중 정확히 하나로 답하십시오.
- 인용됨: 처분이 전부 또는 일부라도 취소됨 (납세자 승소)
- 기각: 처분이 그대로 유지됨 (과세관청 승소)
첫 줄에 결론 한 단어(인용됨 또는 기각)만 쓰고, 둘째 줄부터 두세 문장으로 핵심 근거를 쓰십시오."""

CIVIL_CLAUSE_TEMPLATE = """다음은 대한민국 제1심 민사사건에서 법원이 확정한 청구취지와 기초사실입니다.
법원의 최종 결론(주문)과 판단 부분은 제거되어 있습니다. 오직 아래 번호가 붙은 근거절만 근거로,
이 사건 본소 청구에 대한 법원의 결론을 예측하십시오.

[청구취지 근거절]
{claim}

[기초사실 근거절]
{facts}

다음 두 가지 중 정확히 하나로 답하십시오.
- 인용됨: 청구가 전부 또는 일부라도 받아들여짐
- 기각: 청구가 전부 배척됨
첫 줄에 결론 한 단어(인용됨 또는 기각)만 쓰고, 둘째 줄부터 두세 문장으로 핵심 근거를 쓰십시오."""


class ReserveBuildError(RuntimeError):
    """A fail-closed validation or construction error."""


@dataclass(frozen=True)
class StratumQuota:
    target_per_label: int
    candidate_per_label: int


@dataclass(frozen=True)
class BuildConfig:
    seed_salt: str
    min_date: str
    max_date: str
    strict_dataset_disjoint: bool
    quotas: Mapping[str, StratumQuota]


@dataclass
class PriorInputs:
    files: list[dict[str, Any]]
    private_rows: list[dict[str, Any]]
    prompt_hashes: set[str]
    content_hashes: dict[str, set[str]]
    public_parse_counts: Counter[str]


@dataclass
class PriorExposure:
    keys: dict[str, set[str]]
    source_datasets: set[str]
    source_dataset_display: dict[str, str]
    source_dataset_exact_values: set[str]
    resolved_db_rows_missing_case_ref: int


@dataclass
class InventoryBuild:
    public_rows: list[dict[str, Any]]
    private_rows: list[dict[str, Any]]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class TargetMetadataPatterns:
    court: tuple[re.Pattern[str], ...]
    case_number: tuple[re.Pattern[str], ...]
    decision_date: re.Pattern[str]


@dataclass(frozen=True)
class TargetMetadataRedaction:
    claim: str
    facts: str
    counts: Mapping[str, Mapping[str, int]]


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path, *, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def normalize_identity_component(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return "".join(character for character in text if character.isalnum())


def _flexible_literal_pattern(compact: str) -> str:
    return TARGET_SEPARATOR_PATTERN.join(re.escape(character) for character in compact)


def target_metadata_patterns(
    *, court: Any, case_number: Any, decision_date: Any
) -> TargetMetadataPatterns:
    court_text = unicodedata.normalize("NFKC", str(court or "")).strip()
    court_compact = normalize_identity_component(court_text)
    if (
        (len(court_compact) < 4 and court_compact not in {"대법원"})
        or court_compact in GENERIC_COURT_LOCATORS
        or not any(
            marker in court_compact
            for marker in ("법원", "지법", "고법", "행법", "가법", "지원", "재판소")
        )
    ):
        raise ReserveBuildError("target court locator is unverifiable or too generic")
    court_variants = {court_compact}
    for short, long in (
        ("지법", "지방법원"),
        ("고법", "고등법원"),
        ("행법", "행정법원"),
        ("가법", "가정법원"),
    ):
        if short in court_compact:
            court_variants.add(court_compact.replace(short, long))
        if long in court_compact:
            court_variants.add(court_compact.replace(long, short))
    court_patterns = tuple(
        re.compile(
            rf"(?<![0-9A-Za-z가-힣]){_flexible_literal_pattern(variant)}"
            rf"(?![0-9A-Za-z])",
            re.IGNORECASE,
        )
        for variant in sorted(court_variants, key=lambda value: (-len(value), value))
    )

    case_text = unicodedata.normalize("NFKC", str(case_number or ""))
    explicit_case_re = re.compile(r"(?P<year>(?:\d{2}|\d{4}))\s*(?P<code>[가-힣]{1,6})\s*(?P<serial>\d{1,10})")
    explicit_matches = list(explicit_case_re.finditer(case_text))
    if not explicit_matches:
        raise ReserveBuildError("target case-number locator is unverifiable")
    recognized = explicit_case_re.sub(" ", case_text)
    recognized = re.sub(r"\d{1,10}(?=\s*(?:\([^)]*\))?\s*(?:,|$))", " ", recognized)
    recognized = re.sub(r"[\s,;:/._·ㆍ()\[\]{}-]+|병합|참가", "", recognized)
    if recognized:
        raise ReserveBuildError("target case-number locator is unverifiable")
    canonical_cases: set[str] = set()
    first_year = explicit_matches[0].group("year")
    first_code = explicit_matches[0].group("code")
    for match in explicit_matches:
        canonical_cases.add(
            match.group("year") + match.group("code") + match.group("serial")
        )
    for bare_match in re.finditer(r"(?:^|,)\s*(\d{1,10})\s*(?:\([^)]*\))?\s*(?=,|$)", case_text):
        canonical_cases.add(first_year + first_code + bare_match.group(1))
    case_patterns = tuple(
        re.compile(
            rf"(?<!\d){_flexible_literal_pattern(canonical)}(?!\d)",
            re.IGNORECASE,
        )
        for canonical in sorted(canonical_cases, key=lambda value: (-len(value), value))
    )

    date_text = normalize_text(decision_date)
    date_match = re.fullmatch(r"(18\d{2}|19\d{2}|20\d{2})-(\d{2})-(\d{2})", date_text)
    if date_match is None:
        raise ReserveBuildError("target decision date must use valid YYYY-MM-DD")
    year, month, day = date_match.groups()
    try:
        dt.date(int(year), int(month), int(day))
    except ValueError as error:
        raise ReserveBuildError("target decision date is not a real calendar date") from error
    month_number, day_number = str(int(month)), str(int(day))
    date_pattern = re.compile(
        rf"(?<!\d){year}\s*(?:년\s*0?{month_number}\s*월\s*0?{day_number}\s*일|"
        rf"[-/]\s*0?{month_number}\s*[-/]\s*0?{day_number}|"
        rf"\.\s*0?{month_number}\s*\.\s*0?{day_number}(?:\s*\.)?)"
        rf"(?!\d)"
    )
    return TargetMetadataPatterns(
        court=court_patterns,
        case_number=case_patterns,
        decision_date=date_pattern,
    )


def target_metadata_match_counts(
    text: str, patterns: TargetMetadataPatterns
) -> dict[str, int]:
    return {
        "court": sum(len(pattern.findall(text)) for pattern in patterns.court),
        "caseNumber": sum(len(pattern.findall(text)) for pattern in patterns.case_number),
        "decisionDate": len(patterns.decision_date.findall(text)),
    }


def redact_target_metadata(
    *, claim: str, facts: str, court: Any, case_number: Any, decision_date: Any
) -> TargetMetadataRedaction:
    patterns = target_metadata_patterns(
        court=court, case_number=case_number, decision_date=decision_date
    )

    def redact_field(text: str) -> tuple[str, dict[str, int]]:
        redacted = unicodedata.normalize("NFKC", str(text or ""))
        counts = {"court": 0, "caseNumber": 0, "decisionDate": 0}
        for pattern in patterns.court:
            redacted, count = pattern.subn(TARGET_METADATA_PLACEHOLDERS["court"], redacted)
            counts["court"] += count
        for pattern in patterns.case_number:
            redacted, count = pattern.subn(
                TARGET_METADATA_PLACEHOLDERS["caseNumber"], redacted
            )
            counts["caseNumber"] += count
        redacted, counts["decisionDate"] = patterns.decision_date.subn(
            TARGET_METADATA_PLACEHOLDERS["decisionDate"], redacted
        )
        residual = target_metadata_match_counts(redacted, patterns)
        if any(residual.values()):
            raise ReserveBuildError("target metadata remained after deterministic redaction")
        return redacted, counts

    redacted_claim, claim_counts = redact_field(claim)
    redacted_facts, facts_counts = redact_field(facts)
    return TargetMetadataRedaction(
        claim=redacted_claim,
        facts=redacted_facts,
        counts={"claim": claim_counts, "facts": facts_counts},
    )


def assert_no_target_metadata(
    text: str, *, court: Any, case_number: Any, decision_date: Any
) -> None:
    patterns = target_metadata_patterns(
        court=court, case_number=case_number, decision_date=decision_date
    )
    residual = target_metadata_match_counts(text, patterns)
    if any(residual.values()):
        raise ReserveBuildError(
            "post-render target-specific metadata check failed: "
            + ", ".join(f"{name}={count}" for name, count in residual.items() if count)
        )


def normalize_exact_key(value: Any) -> str:
    return normalize_text(value).casefold()


def normalize_case_ref(value: Any) -> str:
    raw = str(value or "")
    if raw.count(CASE_REF_SEPARATOR) != 1:
        raise ReserveBuildError(f"caseRef must contain exactly one '|': {raw!r}")
    court, case_number = raw.split(CASE_REF_SEPARATOR, 1)
    court_norm = normalize_identity_component(court)
    number_norm = normalize_identity_component(case_number)
    if not court_norm or not number_norm:
        raise ReserveBuildError(f"caseRef has an empty normalized component: {raw!r}")
    return f"{court_norm}|{number_norm}"


def case_ref(court: Any, case_number: Any) -> str:
    court_text = normalize_text(court)
    number_text = normalize_text(case_number)
    if not court_text or not number_text:
        raise ReserveBuildError("eligible DB row is missing court or case_number")
    return f"{court_text}|{number_text}"


def normalized_prompt_sha256(prompt: Any) -> str:
    normalized = normalize_text(prompt)
    if not normalized:
        raise ReserveBuildError("prompt is empty after normalization")
    return sha256_bytes(normalized.encode("utf-8"))


def normalize_source_path_locator(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
    text = text.replace("\\", "/")
    text = re.sub(r"/+", "/", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" /")


def content_sha256(value: Any) -> str:
    normalized = evidence_roundtrip_signature(value)
    if not normalized:
        raise ReserveBuildError("cannot fingerprint empty prompt content")
    return sha256_bytes(normalized.encode("utf-8"))


def _strip_numbered_clause_ids(value: str) -> str:
    return CLAUSE_ID_PREFIX_RE.sub("", value)


def _extract_heading_block(prompt: str, heading: re.Pattern[str]) -> str | None:
    match = heading.search(prompt)
    if not match:
        return None
    start = match.end()
    stops = []
    next_heading = GENERIC_HEADING_RE.search(prompt, start)
    if next_heading:
        stops.append(next_heading.start())
    tail = CONTENT_TAIL_RE.search(prompt, start)
    if tail:
        stops.append(tail.start())
    stop = min(stops) if stops else len(prompt)
    content = normalize_text(_strip_numbered_clause_ids(prompt[start:stop]))
    return content or None


def public_content_fingerprints(prompt: str) -> dict[str, str]:
    """Extract wrapper-independent claim/facts fingerprints from known prompts.

    Generic bracket headings delimit a recognized claim/facts block, allowing
    old prompt variants to add instructions, arguments, retrieved rules, or a
    different outer wrapper without changing the underlying content hash.
    """
    claim = _extract_heading_block(prompt, CLAIM_HEADING_RE)
    facts = _extract_heading_block(prompt, FACTS_HEADING_RE)
    result: dict[str, str] = {}
    if claim:
        result["claimContentSHA256"] = content_sha256(claim)
    if facts:
        result["factsContentSHA256"] = content_sha256(facts)
        combined = f"{claim}\n{facts}" if claim else facts
        result["claimFactsContentSHA256"] = content_sha256(combined)
    return result


def _validate_sha256(value: Any, *, location: str) -> str:
    digest = normalize_text(value).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ReserveBuildError(f"invalid SHA-256 at {location}: {value!r}")
    return digest


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> Any:
    raise ValueError(f"non-finite JSON value: {value}")


def load_jsonl_strict(path: Path) -> tuple[list[dict[str, Any]], str, int]:
    if path.is_symlink() or not path.is_file():
        raise ReserveBuildError(f"prior input must be a regular non-symlink file: {path}")
    before = path.stat()
    raw = path.read_bytes()
    digest = sha256_bytes(raw)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ReserveBuildError(f"prior input changed while being read: {path}")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ReserveBuildError(f"prior input is not UTF-8: {path}: {error}") from error
    rows: list[dict[str, Any]] = []
    if not text:
        raise ReserveBuildError(f"prior input is empty: {path}")
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            raise ReserveBuildError(f"blank JSONL row: {path}:{line_number}")
        try:
            row = json.loads(
                line,
                object_pairs_hook=_reject_duplicate_json_keys,
                parse_constant=_reject_json_constant,
            )
        except (json.JSONDecodeError, ValueError) as error:
            raise ReserveBuildError(f"malformed JSONL row: {path}:{line_number}: {error}") from error
        if not isinstance(row, dict):
            raise ReserveBuildError(f"JSONL row is not an object: {path}:{line_number}")
        rows.append(row)
    if sha256_file(path) != digest:
        raise ReserveBuildError(f"prior input hash changed after parsing: {path}")
    return rows, digest, len(raw)


def _require_nonempty_fields(
    row: Mapping[str, Any], required: Sequence[str], *, location: str
) -> None:
    missing = [key for key in required if key not in row]
    if missing:
        raise ReserveBuildError(f"missing keys at {location}: {', '.join(missing)}")
    empty = [key for key in required if not normalize_text(row[key])]
    if empty:
        raise ReserveBuildError(f"empty required values at {location}: {', '.join(empty)}")


def _load_exposure_ledger(path: Path) -> tuple[dict[str, set[str]], dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise ReserveBuildError(f"exposure ledger must be a regular non-symlink file: {path}")
    raw = path.read_bytes()
    digest = sha256_bytes(raw)
    try:
        ledger = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ReserveBuildError(f"malformed exposure ledger {path}: {error}") from error
    if not isinstance(ledger, dict):
        raise ReserveBuildError(f"exposure ledger is not an object: {path}")
    _require_nonempty_fields(
        ledger, ("protocol", "hashes", "selfHash"), location=str(path)
    )
    if ledger["protocol"] != "outcome-public-exposure-ledger-v1":
        raise ReserveBuildError(f"unsupported exposure ledger protocol: {ledger['protocol']!r}")
    if not isinstance(ledger["hashes"], dict):
        raise ReserveBuildError(f"exposure ledger hashes must be an object: {path}")
    unsigned = dict(ledger)
    claimed_self_hash = _validate_sha256(unsigned.pop("selfHash"), location=f"{path}:selfHash")
    computed_self_hash = sha256_bytes(canonical_json_bytes(unsigned))
    if claimed_self_hash != computed_self_hash:
        raise ReserveBuildError(f"exposure ledger self-hash mismatch: {path}")
    unknown = sorted(set(ledger["hashes"]) - set(LEDGER_HASH_NAMES))
    if unknown:
        raise ReserveBuildError(f"unknown exposure ledger hash collections: {', '.join(unknown)}")
    hashes: dict[str, set[str]] = {name: set() for name in LEDGER_HASH_NAMES}
    for name in LEDGER_HASH_NAMES:
        values = ledger["hashes"].get(name, [])
        if not isinstance(values, list):
            raise ReserveBuildError(f"exposure ledger {name} must be a list")
        for index, value in enumerate(values):
            hashes[name].add(
                _validate_sha256(value, location=f"{path}:{name}[{index}]")
            )
    if not any(hashes.values()):
        raise ReserveBuildError(f"exposure ledger contains no hashes: {path}")
    return hashes, {
        "name": path.name,
        "path": str(path.resolve()),
        "kind": "exposureLedger",
        "origin": "explicitLedger",
        "sha256": digest,
        "bytes": len(raw),
        "hashCounts": {name: len(values) for name, values in hashes.items()},
        "selfHash": claimed_self_hash,
    }


def discover_prior_inputs(
    prior_dir: Path,
    *,
    extra_public_paths: Sequence[Path] = (),
    exposure_ledger: Path | None = None,
) -> PriorInputs:
    if not prior_dir.is_dir():
        raise ReserveBuildError(f"prior outcome directory does not exist: {prior_dir}")
    paths = sorted(prior_dir.glob("outcome*.jsonl"), key=lambda item: item.name)
    if not paths:
        raise ReserveBuildError(f"no prior outcome JSONLs found in {prior_dir}")

    files: list[dict[str, Any]] = []
    private_rows: list[dict[str, Any]] = []
    prompt_hashes: set[str] = set()
    content_hashes: dict[str, set[str]] = {
        name: set() for name in PUBLIC_CONTENT_IDENTITY_NAMES
    }
    public_parse_counts: Counter[str] = Counter()
    kinds: Counter[str] = Counter()
    classified_paths: list[tuple[Path, str, str]] = []
    for path in paths:
        is_private = bool(PRIVATE_KIND_RE.search(path.stem))
        is_public = bool(PUBLIC_KIND_RE.search(path.stem))
        if is_private == is_public:
            raise ReserveBuildError(f"cannot classify prior outcome JSONL as public/private: {path}")
        kind = "private" if is_private else "public"
        classified_paths.append((path, kind, "priorDirectory"))

    seen_paths = {path.resolve() for path, _, _ in classified_paths}
    expanded_extra: list[Path] = []
    for supplied in extra_public_paths:
        if supplied.is_dir() and not supplied.is_symlink():
            discovered = sorted(supplied.glob("*.jsonl"), key=lambda item: item.name)
            if not discovered:
                raise ReserveBuildError(
                    f"extra public exposure directory contains no JSONLs: {supplied}"
                )
            expanded_extra.extend(discovered)
        else:
            expanded_extra.append(supplied)
    for path in expanded_extra:
        resolved = path.resolve()
        if resolved in seen_paths:
            raise ReserveBuildError(f"duplicate public exposure input path: {path}")
        seen_paths.add(resolved)
        classified_paths.append((path, "public", "extraPublic"))

    for path, kind, origin in classified_paths:
        rows, digest, byte_count = load_jsonl_strict(path)
        seen_ids: set[str] = set()
        file_parse_counts: Counter[str] = Counter()
        for index, row in enumerate(rows, 1):
            location = f"{path}:{index}"
            required = PRIVATE_REQUIRED_KEYS if kind == "private" else PUBLIC_REQUIRED_KEYS
            _require_nonempty_fields(row, required, location=location)
            row_id = normalize_text(row["caseId" if kind == "private" else "id"])
            if row_id in seen_ids:
                raise ReserveBuildError(f"duplicate row ID within {path}: {row_id}")
            seen_ids.add(row_id)
            if kind == "private":
                if normalize_text(row["label"]) not in CLASSES:
                    raise ReserveBuildError(f"invalid private label at {location}: {row['label']!r}")
                normalize_case_ref(row["caseRef"])
                private_rows.append(dict(row))
            else:
                prompt_hashes.add(normalized_prompt_sha256(row["prompt"]))
                parsed = public_content_fingerprints(str(row["prompt"]))
                public_parse_counts["publicRows"] += 1
                file_parse_counts["publicRows"] += 1
                for name, digest_value in parsed.items():
                    content_hashes[name].add(digest_value)
                if "factsContentSHA256" in parsed:
                    public_parse_counts["parsedFacts"] += 1
                    file_parse_counts["parsedFacts"] += 1
                else:
                    public_parse_counts["unparsedFacts"] += 1
                    file_parse_counts["unparsedFacts"] += 1
                if "claimContentSHA256" in parsed:
                    public_parse_counts["parsedClaim"] += 1
                    file_parse_counts["parsedClaim"] += 1
                else:
                    public_parse_counts["unparsedClaim"] += 1
                    file_parse_counts["unparsedClaim"] += 1
        kinds[kind] += 1
        file_record = {
            "name": path.name,
            "path": str(path.resolve()),
            "kind": kind,
            "origin": origin,
            "sha256": digest,
            "bytes": byte_count,
            "rows": len(rows),
        }
        if kind == "public":
            file_record["contentParseCounts"] = dict(sorted(file_parse_counts.items()))
        files.append(file_record)
    if not kinds["private"] or not kinds["public"]:
        raise ReserveBuildError("prior closure requires at least one public and one private JSONL")
    if exposure_ledger is not None:
        ledger_hashes, ledger_record = _load_exposure_ledger(exposure_ledger)
        prompt_hashes.update(ledger_hashes["normalizedPromptSHA256"])
        for name in PUBLIC_CONTENT_IDENTITY_NAMES:
            content_hashes[name].update(ledger_hashes[name])
        files.append(ledger_record)
    return PriorInputs(
        files=files,
        private_rows=private_rows,
        prompt_hashes=prompt_hashes,
        content_hashes=content_hashes,
        public_parse_counts=public_parse_counts,
    )


def open_readonly_database(db_path: Path) -> sqlite3.Connection:
    if db_path.is_symlink() or not db_path.is_file():
        raise ReserveBuildError(f"precedent DB must be a regular non-symlink file: {db_path}")
    uri = db_path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("BEGIN")
    return connection


def database_schema(connection: sqlite3.Connection) -> tuple[str, list[dict[str, Any]]]:
    table_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(precedents)").fetchall()
    }
    missing = sorted(set(REQUIRED_DB_COLUMNS) - table_columns)
    if missing:
        raise ReserveBuildError(f"precedents table is missing required columns: {', '.join(missing)}")
    rows = connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name"
    ).fetchall()
    schema = [
        {
            "type": normalize_text(row["type"]),
            "name": normalize_text(row["name"]),
            "table": normalize_text(row["tbl_name"]),
            "sql": normalize_text(row["sql"]),
        }
        for row in rows
    ]
    return sha256_bytes(canonical_json_bytes(schema)), schema


def _chunks(values: Sequence[str], size: int = 800) -> Iterator[Sequence[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def resolve_prior_exposure(
    connection: sqlite3.Connection, prior: PriorInputs
) -> PriorExposure:
    canonical_ids = sorted({normalize_text(row["canonicalId"]) for row in prior.private_rows})
    resolved: dict[str, sqlite3.Row] = {}
    select_columns = ", ".join(REQUIRED_DB_COLUMNS)
    for chunk in _chunks(canonical_ids):
        placeholders = ",".join("?" for _ in chunk)
        query = f"SELECT {select_columns} FROM precedents WHERE canonical_id IN ({placeholders})"
        for row in connection.execute(query, tuple(chunk)):
            canonical = normalize_text(row["canonical_id"])
            if canonical in resolved:
                raise ReserveBuildError(f"duplicate canonical_id in DB: {canonical}")
            resolved[canonical] = row
    missing = sorted(set(canonical_ids) - set(resolved))
    if missing:
        preview = ", ".join(missing[:5])
        raise ReserveBuildError(
            f"{len(missing)} prior private canonical IDs are absent from DB: {preview}"
        )

    keys: dict[str, set[str]] = {name: set() for name in IDENTITY_NAMES}
    source_datasets: set[str] = set()
    source_dataset_display: dict[str, str] = {}
    source_dataset_exact_values: set[str] = set()
    resolved_db_rows_missing_case_ref = 0
    for canonical in canonical_ids:
        row = resolved[canonical]
        dataset_display = normalize_text(row["source_dataset"])
        dataset = normalize_exact_key(dataset_display)
        if not dataset:
            raise ReserveBuildError(f"prior private DB row has empty source_dataset: {canonical}")
        source_datasets.add(dataset)
        source_dataset_display.setdefault(dataset, dataset_display)
        source_dataset_exact_values.add(str(row["source_dataset"]))
        keys["canonicalId"].add(canonical)
        court = normalize_text(row["court"])
        case_number = normalize_text(row["case_number"])
        if court and case_number:
            keys["caseRef"].add(normalize_case_ref(case_ref(court, case_number)))
        else:
            # Historical private manifests remain authoritative for their
            # already-frozen caseRef.  Some source DB rows have since been
            # found to lack one locator component; do not let that dirty
            # metadata abort closure over all other stable identity keys.
            resolved_db_rows_missing_case_ref += 1
        case_number_key = normalize_identity_component(row["case_number"])
        if case_number_key:
            keys["caseNumber"].add(case_number_key)
        source_record = normalize_exact_key(row["source_record_id"])
        if source_record:
            keys["sourceRecordId"].add(source_record)
            keys["sourceDatasetRecordId"].add(f"{dataset}|{source_record}")
        source_path = normalize_source_path_locator(row["source_path"])
        if source_path:
            keys["sourcePathLocator"].add(source_path)
        for db_name, identity_name in DB_TO_IDENTITY.items():
            value = normalize_exact_key(row[db_name])
            if value:
                keys[identity_name].add(value)

    for historical in prior.private_rows:
        canonical = normalize_text(historical["canonicalId"])
        private_ref = normalize_case_ref(historical["caseRef"])
        database_row = resolved[canonical]
        database_court = normalize_text(database_row["court"])
        database_case_number = normalize_text(database_row["case_number"])
        if database_court and database_case_number:
            database_ref = normalize_case_ref(
                case_ref(database_court, database_case_number)
            )
            if private_ref != database_ref:
                raise ReserveBuildError(
                    f"prior private caseRef disagrees with DB for {canonical}: "
                    f"{historical['caseRef']!r}"
                )
        keys["caseRef"].add(private_ref)
    keys["promptSHA256"].update(prior.prompt_hashes)
    # The source prompt is the exact unnumbered rendering used for historical
    # prompt closure.  It shares the historical set with the emitted numbered
    # prompt so adding citation IDs cannot evade an old prompt match.
    keys["sourcePromptSHA256"].update(prior.prompt_hashes)
    for name in PUBLIC_CONTENT_IDENTITY_NAMES:
        keys[name].update(prior.content_hashes[name])
    return PriorExposure(
        keys=keys,
        source_datasets=source_datasets,
        source_dataset_display=source_dataset_display,
        source_dataset_exact_values=source_dataset_exact_values,
        resolved_db_rows_missing_case_ref=resolved_db_rows_missing_case_ref,
    )


def evidence_roundtrip_signature(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(text or ""))
    return re.sub(r"\s+", "", normalized)


def _bounded_clause_parts(text: str) -> list[str]:
    remaining = normalize_text(text)
    parts: list[str] = []
    while len(remaining) > MAX_EVIDENCE_CLAUSE_CHARS:
        cut = remaining.rfind(" ", 0, MAX_EVIDENCE_CLAUSE_CHARS + 1)
        if cut <= 0:
            cut = MAX_EVIDENCE_CLAUSE_CHARS
        part = remaining[:cut].strip()
        if not part:
            raise ReserveBuildError("evidence clause splitter made no progress")
        parts.append(part)
        remaining = remaining[cut:].strip()
    if remaining:
        parts.append(remaining)
    return parts


def segment_evidence(text: str, *, prefix: str) -> list[dict[str, str]]:
    if prefix not in {"C", "F"}:
        raise ReserveBuildError(f"unsupported evidence-clause prefix: {prefix}")
    clauses: list[str] = []
    for source_line in str(text).splitlines():
        line = normalize_text(source_line)
        if not line:
            continue
        sentence_parts = [part for part in SENTENCE_BOUNDARY_RE.split(line) if part]
        merged: list[str] = []
        for part in sentence_parts:
            part = normalize_text(part)
            if merged and ENUMERATOR_ONLY_RE.fullmatch(merged[-1]):
                merged[-1] = normalize_text(f"{merged[-1]} {part}")
            else:
                merged.append(part)
        for part in merged:
            clauses.extend(_bounded_clause_parts(part))
    if not clauses:
        raise ReserveBuildError(f"no non-empty {prefix} evidence clauses")
    if len(clauses) > 999:
        raise ReserveBuildError(f"too many {prefix} evidence clauses: {len(clauses)}")
    if any(len(clause) > MAX_EVIDENCE_CLAUSE_CHARS for clause in clauses):
        raise ReserveBuildError("evidence clause exceeds the frozen maximum length")
    if evidence_roundtrip_signature(text) != evidence_roundtrip_signature(" ".join(clauses)):
        raise ReserveBuildError("evidence segmentation roundtrip invariant failed")
    return [
        {"id": f"{prefix}{index:03d}", "text": clause}
        for index, clause in enumerate(clauses, 1)
    ]


def format_evidence_clauses(clauses: Sequence[Mapping[str, str]]) -> str:
    return "\n".join(f"[{clause['id']}] {clause['text']}" for clause in clauses)


def render_source_prompt(*, domain: str, claim: str, facts: str) -> str:
    """Render the unnumbered prompt used solely for historical prompt closure."""
    if domain == "tax":
        prompt = TAX_FACTS_ONLY_SOURCE_TEMPLATE.format(facts=facts)
        if "None" in prompt:
            raise ReserveBuildError("literal None leaked into the facts-only tax prompt")
        return prompt
    if domain == "civil":
        return PROMPT_TEMPLATE.format(claim=claim, facts=facts)
    raise ReserveBuildError(f"unsupported domain: {domain}")


def render_prompt(
    *, domain: str, claim_clauses: Sequence[Mapping[str, str]],
    facts_clauses: Sequence[Mapping[str, str]]
) -> str:
    facts = format_evidence_clauses(facts_clauses)
    if domain == "tax":
        prompt = TAX_FACTS_ONLY_CLAUSE_TEMPLATE.format(facts=facts)
        if "None" in prompt:
            raise ReserveBuildError("literal None leaked into the numbered tax prompt")
        return prompt
    if domain == "civil":
        return CIVIL_CLAUSE_TEMPLATE.format(
            claim=format_evidence_clauses(claim_clauses), facts=facts
        )
    raise ReserveBuildError(f"unsupported domain: {domain}")


def holding_leak_reason(*, holding: str, claim: str, facts: str, prompt: str) -> str | None:
    if claim and CLAIM_HOLDING_POINTER.search(claim):
        return "claim_points_to_holding"
    if SECTION_HOLDING_MARKER.search(prompt):
        return "holding_section_marker"
    public_material = normalize_text(f"{claim}\n{facts}")
    holding_normalized = normalize_text(holding)
    if not holding_normalized:
        return "empty_holding"

    fragments: list[str] = []
    if len(holding_normalized) >= 20:
        fragments.append(holding_normalized[: min(100, len(holding_normalized))])
    for line in str(holding).splitlines():
        fragment = normalize_text(line)
        if len(fragment) >= 20:
            fragments.append(fragment[: min(100, len(fragment))])
    for fragment in dict.fromkeys(fragments):
        if fragment in public_material:
            return "holding_text_overlap"
    return None


def candidate_identity(
    row: Mapping[str, Any], *, prompt_hash: str, source_prompt_hash: str,
    claim: str, facts: str
) -> dict[str, str]:
    canonical = normalize_text(row["canonical_id"])
    if not canonical:
        raise ReserveBuildError("eligible DB row has empty canonical_id")
    dataset = normalize_exact_key(row["source_dataset"])
    source_record = normalize_exact_key(row["source_record_id"])
    result = {
        "canonicalId": canonical,
        "caseRef": normalize_case_ref(case_ref(row["court"], row["case_number"])),
        "caseNumber": normalize_identity_component(row["case_number"]),
        "sourceRecordId": source_record,
        "sourceDatasetRecordId": f"{dataset}|{source_record}" if dataset and source_record else "",
        "sourcePathLocator": normalize_source_path_locator(row["source_path"]),
        "promptSHA256": prompt_hash,
        "sourcePromptSHA256": source_prompt_hash,
        "claimContentSHA256": content_sha256(claim) if claim else "",
        "factsContentSHA256": content_sha256(facts),
        "claimFactsContentSHA256": content_sha256(
            f"{claim}\n{facts}" if claim else facts
        ),
    }
    for db_name, identity_name in DB_TO_IDENTITY.items():
        result[identity_name] = normalize_exact_key(row[db_name])
    return result


def _candidate_query(*, exact_dataset_exclusion_count: int = 0) -> str:
    civil_sql = "(case_number LIKE '%가단%' OR case_number LIKE '%가합%' OR case_number LIKE '%가소%')"
    tax_sql = (
        "(case_number LIKE '%구합%' OR case_number LIKE '%구단%') AND (("
        + TAX_NAME_SQL
        + ") OR case_name LIKE '%부과처분%' OR case_name LIKE '%경정%' OR case_name LIKE '%세액%')"
    )
    columns = ", ".join(REQUIRED_DB_COLUMNS)
    dataset_exclusion = ""
    if exact_dataset_exclusion_count:
        placeholders = ",".join("?" for _ in range(exact_dataset_exclusion_count))
        # This exact-value pushdown is only an I/O optimization.  The Python
        # normalized comparison remains authoritative and fail-closed.
        dataset_exclusion = f"AND source_dataset NOT IN ({placeholders})"
    return f"""
        SELECT {columns}
        FROM precedents
        WHERE decision_date BETWEEN ? AND ?
          {dataset_exclusion}
          AND length(full_text) BETWEEN 3000 AND 30000
          AND (({civil_sql}) OR ({tax_sql}))
    """


def _domain_for_row(row: Mapping[str, Any]) -> str:
    number = normalize_text(row["case_number"])
    if CASE_NUMBER_CIVIL.search(number):
        return "civil"
    if CASE_NUMBER_TAX.search(number):
        return "tax"
    raise ReserveBuildError(f"combined eligibility query returned an unknown docket: {number!r}")


def _scan_candidates(
    connection: sqlite3.Connection,
    exposure: PriorExposure,
    config: BuildConfig,
) -> tuple[list[dict[str, Any]], Counter[str]]:
    stats: Counter[str] = Counter()
    candidates: list[dict[str, Any]] = []
    exact_dataset_exclusions = (
        sorted(exposure.source_dataset_exact_values)
        if config.strict_dataset_disjoint
        else []
    )
    query = _candidate_query(
        exact_dataset_exclusion_count=len(exact_dataset_exclusions)
    )
    cursor = connection.execute(
        query,
        (config.min_date, config.max_date, *exact_dataset_exclusions),
    )
    stats["datasetFilter.sqlExactExclusionValues"] = len(exact_dataset_exclusions)
    for row in cursor:
        stats["dbRowsScanned"] += 1
        domain = _domain_for_row(row)
        stats[f"scanned.{domain}"] += 1
        # Court/case-number identity is mandatory for historical and internal
        # family closure.  A row that cannot supply both components is safely
        # ineligible; aborting the entire streaming scan would make one dirty
        # source record control the reserve while inventing a locator would
        # weaken deduplication.
        if not normalize_text(row["court"]) or not normalize_text(row["case_number"]):
            stats["extract.missingCourtOrCaseNumber"] += 1
            continue
        dataset_display = normalize_text(row["source_dataset"])
        dataset = normalize_exact_key(dataset_display)
        if not dataset:
            stats["extract.missingSourceDataset"] += 1
            continue
        # Dataset disjointness is source metadata, so enforce it before any
        # holding/label parsing.  This avoids consulting gold for rows already
        # known to be ineligible.
        if config.strict_dataset_disjoint and dataset in exposure.source_datasets:
            stats["priorExcluded.any"] += 1
            stats["priorExcluded.sourceDataset"] += 1
            stats["priorExcluded.sourceDatasetBeforeGold"] += 1
            continue
        sections = split_sections(row["full_text"], require_claim=(domain != "tax"))
        if not sections:
            stats["extract.noSections"] += 1
            continue
        holding = sections["주문"].strip()
        label = label_from_holding(holding)
        if label is None:
            stats["extract.noLabel"] += 1
            continue
        facts = extract_facts(
            sections["이유"], head=FACTS_HEAD_TAX if domain == "tax" else FACTS_HEAD
        )
        if facts is None:
            stats["extract.noFacts"] += 1
            continue
        if len(facts) > 8000:
            stats["extract.sizeFiltered"] += 1
            continue
        claim = "" if domain == "tax" else sections["청구취지"].strip()
        if domain == "civil" and not (50 <= len(claim) <= 2000):
            stats["extract.sizeFiltered"] += 1
            continue
        # Historical/internal closure and the exact holding-overlap gate always
        # use the original extracted source text.  Target metadata redaction is
        # a later, gold-independent public-transport transformation only.
        source_prompt = render_source_prompt(domain=domain, claim=claim, facts=facts)
        unredacted_claim_clauses = (
            segment_evidence(claim, prefix="C") if domain == "civil" else []
        )
        unredacted_facts_clauses = segment_evidence(facts, prefix="F")
        unredacted_prompt = render_prompt(
            domain=domain,
            claim_clauses=unredacted_claim_clauses,
            facts_clauses=unredacted_facts_clauses,
        )
        leak_reason = holding_leak_reason(
            holding=holding, claim=claim, facts=facts, prompt=unredacted_prompt
        )
        if leak_reason:
            stats[f"leak.{leak_reason}"] += 1
            continue

        try:
            redaction = redact_target_metadata(
                claim=claim,
                facts=facts,
                court=row["court"],
                case_number=row["case_number"],
                decision_date=row["decision_date"],
            )
            public_claim_clauses = (
                segment_evidence(redaction.claim, prefix="C")
                if domain == "civil"
                else []
            )
            public_facts_clauses = segment_evidence(redaction.facts, prefix="F")
            public_prompt = render_prompt(
                domain=domain,
                claim_clauses=public_claim_clauses,
                facts_clauses=public_facts_clauses,
            )
            assert_no_target_metadata(
                public_prompt,
                court=row["court"],
                case_number=row["case_number"],
                decision_date=row["decision_date"],
            )
        except ReserveBuildError:
            stats["redaction.invalidOrResidualTargetLocator"] += 1
            continue

        # `identity.promptSHA256` deliberately remains the unredacted numbered
        # prompt hash so prior/internal closure is invariant to this transport
        # redaction.  The public hash is carried separately.
        prompt_hash = normalized_prompt_sha256(unredacted_prompt)
        public_prompt_hash = normalized_prompt_sha256(public_prompt)
        source_prompt_hash = normalized_prompt_sha256(source_prompt)
        identity = candidate_identity(
            row,
            prompt_hash=prompt_hash,
            source_prompt_hash=source_prompt_hash,
            claim=claim,
            facts=facts,
        )

        matches = [
            name for name in IDENTITY_NAMES
            if identity.get(name) and identity[name] in exposure.keys[name]
        ]
        if matches:
            stats["priorExcluded.any"] += 1
            for name in matches:
                stats[f"priorExcluded.{name}"] += 1
            continue

        canonical = identity["canonicalId"]
        selection_rank = sha256_bytes(
            f"{config.seed_salt}|{canonical}|{identity['caseRef']}".encode("utf-8")
        )
        candidates.append(
            {
                "domain": domain,
                "label": label,
                "selectionRankSHA256": selection_rank,
                "caseRef": case_ref(row["court"], row["case_number"]),
                "canonicalId": canonical,
                "decisionDate": normalize_text(row["decision_date"]),
                "sourceDataset": dataset_display,
                "holding": holding,
                "claim": claim,
                "facts": facts,
                "publicClaim": redaction.claim,
                "publicFacts": redaction.facts,
                "publicPromptSHA256": public_prompt_hash,
                "targetMetadataRedactionCounts": redaction.counts,
                "identity": identity,
            }
        )
        stats[f"extracted.{domain}.{label}"] += 1

    # Close identity families transitively, then keep the lowest hash-ranked
    # member of each connected component.  A greedy first-seen filter is not
    # sufficient: A can share a dedupe key with B while B shares a text hash
    # with C, making A/B/C one family even when A and C have no direct match.
    # Component winners depend only on seed/canonical/case-ref hashes, never on
    # labels.
    candidates.sort(key=lambda item: (item["selectionRankSHA256"], item["canonicalId"]))
    parent = list(range(len(candidates)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    owners: dict[str, dict[str, int]] = {name: {} for name in IDENTITY_NAMES}
    frequencies: Counter[tuple[str, str]] = Counter()
    for index, item in enumerate(candidates):
        for name in IDENTITY_NAMES:
            value = item["identity"].get(name)
            if not value:
                continue
            frequencies[(name, value)] += 1
            owner = owners[name].setdefault(value, index)
            union(index, owner)
    components: dict[int, list[int]] = defaultdict(list)
    for index in range(len(candidates)):
        components[find(index)].append(index)
    winner_indices: set[int] = set()
    for members in components.values():
        winner_indices.add(
            min(
                members,
                key=lambda index: (
                    candidates[index]["selectionRankSHA256"],
                    candidates[index]["canonicalId"],
                ),
            )
        )
    unique: list[dict[str, Any]] = []
    for index, item in enumerate(candidates):
        if index not in winner_indices:
            stats["internalExcluded.any"] += 1
            for name in IDENTITY_NAMES:
                value = item["identity"].get(name)
                if value and frequencies[(name, value)] > 1:
                    stats[f"internalExcluded.{name}"] += 1
            continue
        unique.append(item)
        stats[f"unique.{item['domain']}.{item['label']}"] += 1
    return unique, stats


def _validate_config(config: BuildConfig) -> None:
    if not normalize_text(config.seed_salt):
        raise ReserveBuildError("seed_salt must be non-empty")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", config.min_date):
        raise ReserveBuildError("min_date must use YYYY-MM-DD")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", config.max_date):
        raise ReserveBuildError("max_date must use YYYY-MM-DD")
    if config.min_date > config.max_date:
        raise ReserveBuildError("min_date must not be after max_date")
    if set(config.quotas) != {"civil", "tax"}:
        raise ReserveBuildError("quotas must define exactly civil and tax")
    for domain, quota in config.quotas.items():
        if quota.target_per_label <= 0 or quota.candidate_per_label <= 0:
            raise ReserveBuildError(f"{domain} quotas must be positive")
        if quota.candidate_per_label < quota.target_per_label:
            raise ReserveBuildError(
                f"{domain} candidate_per_label must be >= target_per_label"
            )


def build_candidate_inventory(
    *, db_path: Path, prior_dir: Path, config: BuildConfig,
    extra_public_paths: Sequence[Path] = (),
    exposure_ledger: Path | None = None,
) -> InventoryBuild:
    _validate_config(config)
    prior = discover_prior_inputs(
        prior_dir,
        extra_public_paths=extra_public_paths,
        exposure_ledger=exposure_ledger,
    )
    db_before = db_path.stat() if db_path.exists() else None
    if db_before is None:
        raise ReserveBuildError(f"precedent DB does not exist: {db_path}")
    db_hash = sha256_file(db_path)
    builder_hash = sha256_file(Path(__file__))
    extractor_path = REPO_ROOT / "tools" / "build_outcome_prediction_benchmark.py"
    extractor_hash = sha256_file(extractor_path)

    connection = open_readonly_database(db_path)
    try:
        schema_hash, schema = database_schema(connection)
        exposure = resolve_prior_exposure(connection, prior)
        candidates, stats = _scan_candidates(connection, exposure, config)
    finally:
        connection.close()
    db_after = db_path.stat()
    if (db_before.st_size, db_before.st_mtime_ns) != (db_after.st_size, db_after.st_mtime_ns):
        raise ReserveBuildError("precedent DB changed during construction")
    if sha256_file(Path(__file__)) != builder_hash:
        raise ReserveBuildError("reserve builder changed during construction")
    if sha256_file(extractor_path) != extractor_hash:
        raise ReserveBuildError("upstream deterministic extractor changed during construction")

    strata: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        strata[(item["domain"], item["label"])].append(item)
    selected: list[dict[str, Any]] = []
    availability: dict[str, dict[str, int]] = {}
    buffer_selection: dict[str, dict[str, dict[str, int]]] = {}
    for domain in ("civil", "tax"):
        quota = config.quotas[domain]
        availability[domain] = {}
        buffer_selection[domain] = {}
        for label in CLASSES:
            pool = sorted(
                strata[(domain, label)],
                key=lambda item: (item["selectionRankSHA256"], item["canonicalId"]),
            )
            availability[domain][label] = len(pool)
            if len(pool) < quota.target_per_label:
                raise ReserveBuildError(
                    f"target quota infeasible for {domain}/{label}: "
                    f"{len(pool)} < {quota.target_per_label}"
                )
            selected_count = min(quota.candidate_per_label, len(pool))
            buffer_selection[domain][label] = {
                "targetPerLabel": quota.target_per_label,
                "requestedCandidateBuffer": quota.candidate_per_label,
                "available": len(pool),
                "selectedCandidateBuffer": selected_count,
                "candidateBufferShortfall": quota.candidate_per_label - selected_count,
            }
            selected.extend(pool[:selected_count])

    public_rows: list[dict[str, Any]] = []
    private_rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in selected:
        case_id = f"outcome-confirm-{item['selectionRankSHA256'][:20]}"
        if case_id in seen_ids:
            raise ReserveBuildError(f"case ID hash collision: {case_id}")
        seen_ids.add(case_id)
        claim_clauses = (
            segment_evidence(item["publicClaim"], prefix="C")
            if item["domain"] == "civil"
            else []
        )
        facts_clauses = segment_evidence(item["publicFacts"], prefix="F")
        prompt = render_prompt(
            domain=item["domain"],
            claim_clauses=claim_clauses,
            facts_clauses=facts_clauses,
        )
        if normalized_prompt_sha256(prompt) != item["publicPromptSHA256"]:
            raise ReserveBuildError(
                f"numbered prompt changed between scan and emission: {item['canonicalId']}"
            )
        court, case_number = item["caseRef"].split(CASE_REF_SEPARATOR, 1)
        assert_no_target_metadata(
            prompt,
            court=court,
            case_number=case_number,
            decision_date=item["decisionDate"],
        )
        private_identity_keys = dict(item["identity"])
        for sensitive_name in (
            "sourceRecordId",
            "sourceDatasetRecordId",
            "sourcePathLocator",
        ):
            value = private_identity_keys.pop(sensitive_name, "")
            private_identity_keys[f"{sensitive_name}SHA256"] = (
                sha256_bytes(value.encode("utf-8")) if value else ""
            )
        public_rows.append(
            {
                "id": case_id,
                "suite": "exam",
                "benchmarkId": "outcome.first_instance_prediction.v1",
                "responseFormat": "outcome_prediction",
                "language": "ko",
                "prompt": prompt,
            }
        )
        private_rows.append(
            {
                "caseId": case_id,
                "domain": item["domain"],
                "label": item["label"],
                "caseRef": item["caseRef"],
                "canonicalId": item["canonicalId"],
                "decisionDate": item["decisionDate"],
                "sourceDataset": item["sourceDataset"],
                "holding": item["holding"],
                "sourceFields": {
                    "claim": item["claim"],
                    "facts": item["facts"],
                },
                "evidenceClauses": {
                    "claim": claim_clauses,
                    "facts": facts_clauses,
                },
                "targetMetadataRedaction": {
                    "version": TARGET_METADATA_REDACTION_VERSION,
                    "specificationSHA256": TARGET_METADATA_REDACTION_SPEC_SHA256,
                    "replacementCounts": item["targetMetadataRedactionCounts"],
                    "postRenderTargetMatchCount": 0,
                },
                "selectionRankSHA256": item["selectionRankSHA256"],
                "promptSHA256": item["publicPromptSHA256"],
                "sourcePromptSHA256": item["identity"]["sourcePromptSHA256"],
                "identityKeys": private_identity_keys,
            }
        )

    paired = sorted(zip(public_rows, private_rows), key=lambda pair: pair[0]["id"])
    public_rows = [pair[0] for pair in paired]
    private_rows = [pair[1] for pair in paired]
    redaction_totals: Counter[str] = Counter()
    rows_with_redaction = 0
    for private_row in private_rows:
        row_total = 0
        counts = private_row["targetMetadataRedaction"]["replacementCounts"]
        for field_name in ("claim", "facts"):
            for locator_name in ("court", "caseNumber", "decisionDate"):
                count = counts[field_name][locator_name]
                redaction_totals[f"{field_name}.{locator_name}"] += count
                redaction_totals[f"locator.{locator_name}"] += count
                redaction_totals["all"] += count
                row_total += count
        if row_total:
            rows_with_redaction += 1
    metadata = {
        "protocol": "source-disjoint-outcome-candidate-inventory-v1",
        "hashConventions": {
            "normalizedText": "Unicode NFKC, all whitespace collapsed to one ASCII space, stripped",
            "promptSHA256": "SHA-256 of UTF-8 normalizedText(redacted public prompt)",
            "identityKeys.promptSHA256": (
                "SHA-256 of UTF-8 normalizedText(unredacted numbered prompt) for prior/internal closure"
            ),
            "contentSHA256": "SHA-256 of UTF-8 NFKC template-stripped content after removing all whitespace",
            "sourcePathLocator": "Unicode NFKC, casefold, backslash-to-slash, repeated-slash collapse, strip",
            "rowSHA256": "SHA-256 of UTF-8 canonical JSON object without trailing newline",
            "manifestSelfHash": "SHA-256 of canonical JSON manifest after removing selfHash",
            "selectionRankSHA256": "SHA-256(seedSalt|canonicalId|normalizedCaseRef)",
        },
        "evidenceSegmentation": {
            "version": EVIDENCE_SEGMENTATION_VERSION,
            "specification": EVIDENCE_SEGMENTATION_SPEC,
            "specificationSHA256": sha256_bytes(
                canonical_json_bytes(EVIDENCE_SEGMENTATION_SPEC)
            ),
        },
        "targetMetadataRedaction": {
            "version": TARGET_METADATA_REDACTION_VERSION,
            "specification": TARGET_METADATA_REDACTION_SPEC,
            "specificationSHA256": TARGET_METADATA_REDACTION_SPEC_SHA256,
            "selectedRowCount": len(private_rows),
            "rowsWithAtLeastOneReplacement": rows_with_redaction,
            "rowsWithNoReplacement": len(private_rows) - rows_with_redaction,
            "replacementCounts": dict(sorted(redaction_totals.items())),
            "postRenderTargetMatchCount": 0,
            "perRowMetadataLocation": "private JSONL targetMetadataRedaction",
        },
        "database": {
            "path": str(db_path.resolve()),
            "sha256": db_hash,
            "bytes": db_after.st_size,
            "schemaSHA256": schema_hash,
            "schemaObjectCount": len(schema),
        },
        "implementation": {
            "builder": str(Path(__file__).resolve()),
            "builderSHA256": builder_hash,
            "upstreamExtractor": str(extractor_path.resolve()),
            "upstreamExtractorSHA256": extractor_hash,
        },
        "priorInputs": prior.files,
        "priorClosure": {
            "privateRows": len(prior.private_rows),
            "uniquePrivateCanonicalIds": len(exposure.keys["canonicalId"]),
            "normalizedPublicPromptHashes": len(prior.prompt_hashes),
            "resolvedDbRowsMissingCourtOrCaseNumber": (
                exposure.resolved_db_rows_missing_case_ref
            ),
            "publicContentParseCounts": dict(sorted(prior.public_parse_counts.items())),
            "keyCardinalities": {
                name: len(exposure.keys[name]) for name in IDENTITY_NAMES
            },
            "strictDatasetDisjoint": config.strict_dataset_disjoint,
            "excludedSourceDatasets": sorted(exposure.source_dataset_display.values()),
            "datasetFiltering": {
                "sqlExactPushdown": config.strict_dataset_disjoint,
                "sqlExactValueCount": (
                    len(exposure.source_dataset_exact_values)
                    if config.strict_dataset_disjoint
                    else 0
                ),
                "sqlPlacement": "source_dataset NOT IN (...) before length(full_text)",
                "pythonNormalizedPreGoldRecheck": True,
                "normalization": "Unicode NFKC, whitespace collapse, strip, casefold",
            },
        },
        "configuration": {
            "seedSalt": config.seed_salt,
            "minDate": config.min_date,
            "maxDate": config.max_date,
            "quotas": {
                domain: {
                    "targetPerLabel": config.quotas[domain].target_per_label,
                    "candidatePerLabel": config.quotas[domain].candidate_per_label,
                }
                for domain in ("civil", "tax")
            },
        },
        "scanCounts": dict(sorted(stats.items())),
        "eligibleAvailability": availability,
        "candidateBufferSelection": buffer_selection,
        "candidateCounts": {
            domain: {
                label: sum(
                    1
                    for row in private_rows
                    if row["domain"] == domain and row["label"] == label
                )
                for label in CLASSES
            }
            for domain in ("civil", "tax")
        },
    }
    return InventoryBuild(
        public_rows=public_rows,
        private_rows=private_rows,
        metadata=metadata,
    )


def serialize_jsonl(rows: Iterable[Mapping[str, Any]]) -> bytes:
    return b"".join(canonical_json_bytes(row) + b"\n" for row in rows)


def manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    unsigned = dict(manifest)
    unsigned.pop("selfHash", None)
    return sha256_bytes(canonical_json_bytes(unsigned))


def verify_manifest_self_hash(manifest: Mapping[str, Any]) -> bool:
    claimed = manifest.get("selfHash")
    return isinstance(claimed, str) and claimed == manifest_self_hash(manifest)


def _write_exclusive(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as error:
        raise ReserveBuildError(f"refusing to overwrite existing output: {path}") from error


def write_inventory(
    build: InventoryBuild,
    *,
    public_out: Path,
    private_out: Path,
    manifest_out: Path,
) -> dict[str, Any]:
    targets = [public_out.resolve(), private_out.resolve(), manifest_out.resolve()]
    if len(set(targets)) != len(targets):
        raise ReserveBuildError("public, private, and manifest outputs must be distinct")
    existing = [path for path in targets if path.exists()]
    if existing:
        raise ReserveBuildError(
            "refusing to overwrite existing output(s): " + ", ".join(map(str, existing))
        )

    public_payload = serialize_jsonl(build.public_rows)
    private_payload = serialize_jsonl(build.private_rows)
    public_hash = sha256_bytes(public_payload)
    private_hash = sha256_bytes(private_payload)
    ordered = [
        {
            "id": public["id"],
            "promptSHA256": private["promptSHA256"],
            "publicRowSHA256": sha256_bytes(canonical_json_bytes(public)),
            "privateRowSHA256": sha256_bytes(canonical_json_bytes(private)),
        }
        for public, private in zip(build.public_rows, build.private_rows, strict=True)
    ]
    manifest = dict(build.metadata)
    manifest["artifacts"] = {
        "public": {
            "path": str(public_out.resolve()),
            "rows": len(build.public_rows),
            "bytes": len(public_payload),
            "sha256": public_hash,
        },
        "private": {
            "path": str(private_out.resolve()),
            "rows": len(build.private_rows),
            "bytes": len(private_payload),
            "sha256": private_hash,
        },
    }
    manifest["orderedCandidates"] = ordered
    manifest["selfHash"] = manifest_self_hash(manifest)
    manifest_payload = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
    ).encode("utf-8") + b"\n"

    _write_exclusive(public_out, public_payload)
    _write_exclusive(private_out, private_payload)
    if sha256_file(public_out) != public_hash or public_out.stat().st_size != len(public_payload):
        raise ReserveBuildError("public output hash/count verification failed")
    if sha256_file(private_out) != private_hash or private_out.stat().st_size != len(private_payload):
        raise ReserveBuildError("private output hash/count verification failed")
    if len(load_jsonl_strict(public_out)[0]) != len(build.public_rows):
        raise ReserveBuildError("public output row-count verification failed")
    if len(load_jsonl_strict(private_out)[0]) != len(build.private_rows):
        raise ReserveBuildError("private output row-count verification failed")
    _write_exclusive(manifest_out, manifest_payload)
    if sha256_file(manifest_out) != sha256_bytes(manifest_payload):
        raise ReserveBuildError("manifest output hash verification failed")
    try:
        loaded_manifest = json.loads(manifest_out.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReserveBuildError(f"cannot reload manifest: {error}") from error
    if not verify_manifest_self_hash(loaded_manifest):
        raise ReserveBuildError("manifest self-hash verification failed")
    if len(loaded_manifest.get("orderedCandidates", [])) != len(build.public_rows):
        raise ReserveBuildError("manifest ordered-candidate count verification failed")
    return manifest


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--prior-dir", type=Path, default=DEFAULT_PRIOR_DIR)
    parser.add_argument(
        "--extra-public-exposure",
        type=Path,
        action="append",
        default=[],
        help="Additional accepted model-mounted public JSONL (or directory); repeatable",
    )
    parser.add_argument(
        "--exposure-ledger",
        type=Path,
        help="Optional self-hashed outcome-public-exposure-ledger-v1 JSON",
    )
    parser.add_argument("--seed-salt", default="mini-artichokes-confirmatory-reserve-v1")
    parser.add_argument("--min-date", default="2005-01-01")
    parser.add_argument("--max-date", default="2021-12-31")
    parser.add_argument(
        "--strict-dataset-disjoint",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--civil-target-per-label", type=int, default=300)
    parser.add_argument("--civil-candidate-per-label", type=int, default=450)
    parser.add_argument("--tax-target-per-label", type=int, default=200)
    parser.add_argument("--tax-candidate-per-label", type=int, default=300)
    parser.add_argument("--public-out", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--manifest-out", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    config = BuildConfig(
        seed_salt=args.seed_salt,
        min_date=args.min_date,
        max_date=args.max_date,
        strict_dataset_disjoint=args.strict_dataset_disjoint,
        quotas={
            "civil": StratumQuota(
                target_per_label=args.civil_target_per_label,
                candidate_per_label=args.civil_candidate_per_label,
            ),
            "tax": StratumQuota(
                target_per_label=args.tax_target_per_label,
                candidate_per_label=args.tax_candidate_per_label,
            ),
        },
    )
    try:
        build = build_candidate_inventory(
            db_path=args.db,
            prior_dir=args.prior_dir,
            config=config,
            extra_public_paths=args.extra_public_exposure,
            exposure_ledger=args.exposure_ledger,
        )
        manifest = write_inventory(
            build,
            public_out=args.public_out,
            private_out=args.private_out,
            manifest_out=args.manifest_out,
        )
    except (OSError, sqlite3.Error, ReserveBuildError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": "BUILT",
                "rows": len(build.public_rows),
                "manifestSelfHash": manifest["selfHash"],
                "publicSHA256": manifest["artifacts"]["public"]["sha256"],
                "privateSHA256": manifest["artifacts"]["private"]["sha256"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
