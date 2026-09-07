#!/usr/bin/env python3
"""Gold-safe, deterministic pre-solver audit of an outcome reserve.

The public pass validates the transport contract, records conservative generic
leak-sensitivity counts, and joins lexically near-duplicate evidence.  The
bound pass projects only non-gold structure from the paired private rows
(``caseId``, case/source identity, and prompt hashes); it never accesses,
compares, or emits the ``label`` or ``holding`` values.  It checks target-
specific metadata absence and binds the candidate artifact to the builder's
pre-selection exact-holding-overlap checks.  No prompt text, matched substring,
label, or holding is emitted.  IDs are confined to a separate mode-0600 file.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import math
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import build_disjoint_outcome_reserve as reserve_builder  # noqa: E402
from tools.build_disjoint_outcome_reserve import (  # noqa: E402
    CIVIL_CLAUSE_TEMPLATE,
    TAX_FACTS_ONLY_CLAUSE_TEMPLATE,
    normalize_text,
)


AUDIT_SCHEMA_VERSION = "public-outcome-reserve-presolver-audit-v1"
EXPECTED_PUBLIC_KEYS = frozenset(
    {"id", "suite", "benchmarkId", "responseFormat", "language", "prompt"}
)
EXPECTED_CONSTANTS = {
    "suite": "exam",
    "benchmarkId": "outcome.first_instance_prediction.v1",
    "responseFormat": "outcome_prediction",
    "language": "ko",
}
OPAQUE_ID_RE = re.compile(r"^outcome-confirm-[0-9a-f]{20}$")
CLAUSE_RE = {
    "claim": re.compile(r"^\[C(?P<ordinal>\d{3})\] (?P<text>\S.*)$"),
    "facts": re.compile(r"^\[F(?P<ordinal>\d{3})\] (?P<text>\S.*)$"),
}

# The fixed response instructions are excluded before these are applied.  The
# patterns are intentionally conservative: a hit means "requires exclusion or
# human source-redaction review", not that the answer is certainly leaked.
LEAK_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "holding_or_result",
        "holding_pointer",
        re.compile(
            r"주\s*문\s*(?:제\s*\d+(?:\s*의\s*[가-힣0-9]+)?\s*항)?"
            r"\s*(?:과|및|기재|내용|같|대로|에\s*의하)",
            re.IGNORECASE,
        ),
    ),
    (
        "holding_or_result",
        "holding_section_heading",
        re.compile(r"(?m)^\s*(?:\d+[.)]\s*)?(?:주\s*문|판단|법원의\s*판단|이\s*유)\s*[:：]?\s*$"),
    ),
    (
        "holding_or_result",
        "dispositive_language",
        re.compile(
            r"(?:원고|피고|청구|소|항소|상고|처분).{0,36}"
            r"(?:인용(?:한다|하였다|되었다|됨)?|기각(?:한다|하였다|되었다|됨)?|"
            r"각하(?:한다|하였다|되었다|됨)?|배척(?:한다|하였다|되었다|됨)?|"
            r"취소(?:한다|하였다|되었다)|유지(?:한다|하였다|되었다))",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "holding_or_result",
        "holding_formula",
        re.compile(r"소송비용은|가집행할\s*수\s*있다|나머지\s+청구를\s+기각|(?:^|\s)(?:인용됨|기각)(?:\s|$)"),
    ),
    (
        "source_locator",
        "url_or_filesystem_path",
        re.compile(
            r"(?:https?://|www\.|file://|(?:^|\s)[A-Za-z]:[\\/]|/(?:home|mnt|data|tmp)/)",
            re.IGNORECASE,
        ),
    ),
    (
        "source_locator",
        "dataset_or_record_locator",
        re.compile(
            r"(?:canonical[_ -]?id|source[_ -]?(?:dataset|record|path)|"
            r"record[_ -]?id|dedupe[_ -]?key|joonhok|lbox|lawlaw|precedents?\.sqlite)",
            re.IGNORECASE,
        ),
    ),
    (
        "source_locator",
        "named_court",
        re.compile(
            r"(?:대법원|헌법재판소|(?:서울|부산|대구|광주|대전|수원|인천|울산|"
            r"창원|전주|청주|춘천|제주|의정부)?\s*(?:고등|지방|행정|가정)법원)"
        ),
    ),
    (
        "case_number",
        "korean_case_number",
        re.compile(
            r"(?<!\d)(?:18|19|20)\d{2}\s*(?:가단|가합|가소|구단|구합|나|누|"
            r"다|두|마|카단|카합|카기|고단|고합|노|도|헌가|헌나|헌다|헌라|"
            r"헌마|헌바)\s*\d{1,9}(?!\d)"
        ),
    ),
    (
        "case_number",
        "labeled_case_number",
        re.compile(r"(?:사건\s*번호|사건번호)\s*[:：]?\s*(?:제\s*)?[0-9가-힣 -]{4,40}", re.IGNORECASE),
    ),
    (
        "date",
        "calendar_date",
        re.compile(
            r"(?<!\d)(?:18|19|20)\d{2}\s*(?:년\s*\d{1,2}\s*월(?:\s*\d{1,2}\s*일)?|"
            r"[./-]\s*\d{1,2}(?:\s*[./-]\s*\d{1,2})?\s*\.?)"
        ),
    ),
)

NEAR_DUPLICATE_SPEC: dict[str, Any] = {
    "version": "template-stripped-char-shingle-exact-jaccard-v1",
    "scope": ["claim_plus_facts", "facts_only"],
    "unicodeNormalization": "NFKC then casefold",
    "digitNormalization": "each maximal Unicode decimal-digit run becomes ASCII 0",
    "characterFilter": "retain Hangul syllables, ASCII a-z, and ASCII digits; discard all else",
    "shingleLength": 9,
    "minimumFilteredShingles": 64,
    "corpusCommonShingleFilter": {
        "maximumDocumentFraction": 0.20,
        "minimumDocumentCutoff": 10,
        "rule": "discard a shingle when document frequency is greater than max(floor(N*0.20),10)",
    },
    "thresholds": {
        "claimPlusFactsExactJaccard": 0.82,
        "factsOnlyExactJaccard": 0.86,
    },
    "candidateGeneration": (
        "exact inverted index over every retained shingle; all shared-shingle pairs are counted; "
        "cardinality-ratio pruning is a necessary Jaccard condition"
    ),
    "familyConstruction": "connected components of all pairs meeting either threshold",
}


class PublicAuditError(RuntimeError):
    """Invalid invocation or unreadable public inventory."""


@dataclass(frozen=True)
class ParsedPublicRow:
    case_id: str
    domain: str
    claim: tuple[str, ...]
    facts: tuple[str, ...]


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def self_hash(value: Mapping[str, Any]) -> str:
    unsigned = dict(value)
    unsigned.pop("selfHash", None)
    return sha256_bytes(canonical_json_bytes(unsigned))


def verify_self_hash(value: Mapping[str, Any]) -> bool:
    claimed = value.get("selfHash")
    return isinstance(claimed, str) and claimed == self_hash(value)


def _template_regex(template: str, fields: Sequence[str]) -> re.Pattern[str]:
    pattern = re.escape(template)
    for field in fields:
        pattern = pattern.replace(re.escape("{" + field + "}"), f"(?P<{field}>.+?)")
    return re.compile(r"\A" + pattern + r"\Z", re.DOTALL)


CIVIL_PROMPT_RE = _template_regex(CIVIL_CLAUSE_TEMPLATE, ("claim", "facts"))
TAX_PROMPT_RE = _template_regex(TAX_FACTS_ONLY_CLAUSE_TEMPLATE, ("facts",))


def _parse_clause_block(block: str, kind: str) -> tuple[str, ...]:
    lines = block.splitlines()
    if not lines:
        raise ValueError(f"empty_{kind}_clause_block")
    texts: list[str] = []
    for expected_ordinal, line in enumerate(lines, 1):
        match = CLAUSE_RE[kind].fullmatch(line)
        if match is None:
            raise ValueError(f"malformed_{kind}_clause")
        if int(match.group("ordinal")) != expected_ordinal:
            raise ValueError(f"nonsequential_{kind}_clause")
        texts.append(match.group("text"))
    return tuple(texts)


def parse_public_prompt(prompt: str) -> ParsedPublicRow:
    civil = CIVIL_PROMPT_RE.fullmatch(prompt)
    if civil is not None:
        claim = _parse_clause_block(civil.group("claim"), "claim")
        facts = _parse_clause_block(civil.group("facts"), "facts")
        return ParsedPublicRow("", "civil", claim, facts)
    tax = TAX_PROMPT_RE.fullmatch(prompt)
    if tax is not None:
        facts = _parse_clause_block(tax.group("facts"), "facts")
        return ParsedPublicRow("", "tax", (), facts)
    raise ValueError("prompt_not_exactly_a_frozen_public_template")


def _load_public_jsonl(path: Path) -> tuple[bytes, list[Any], list[str]]:
    # One explicit path is the only data read.  No directory scan or companion
    # private-file discovery occurs anywhere in this module.
    if re.search(r"(?:^|[._-])(?:private|gold|labels?)(?:[._-]|$)", path.name, re.I):
        raise PublicAuditError("refusing a path whose basename indicates private/gold data")
    payload = path.read_bytes()
    rows: list[Any] = []
    read_errors: list[str] = []
    for line_number, raw_line in enumerate(payload.splitlines(), 1):
        if not raw_line.strip():
            read_errors.append(f"line_{line_number}:blank_line")
            continue
        try:
            rows.append(json.loads(raw_line))
        except (UnicodeDecodeError, json.JSONDecodeError):
            read_errors.append(f"line_{line_number}:invalid_utf8_or_json")
    return payload, rows, read_errors


PRIVATE_STRUCTURE_FIELDS = (
    "caseId",
    "domain",
    "caseRef",
    "decisionDate",
    "canonicalId",
    "sourceDataset",
    "promptSHA256",
    "identityKeys",
)


def _load_private_structure_jsonl(path: Path) -> tuple[bytes, list[dict[str, Any]], list[str]]:
    """Load an explicitly projected non-gold view of the paired private rows.

    JSON decoding necessarily materializes each row as a container, but only
    the eight allowlisted fields above are selected or retained.  In
    particular, this function contains no lookup of either forbidden gold
    field.
    """
    payload = path.read_bytes()
    projected: list[dict[str, Any]] = []
    errors: list[str] = []
    for line_number, raw_line in enumerate(payload.splitlines(), 1):
        if not raw_line.strip():
            errors.append(f"line_{line_number}:blank_line")
            continue
        try:
            container = json.loads(raw_line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            errors.append(f"line_{line_number}:invalid_utf8_or_json")
            continue
        if not isinstance(container, dict):
            errors.append(f"line_{line_number}:row_not_object")
            continue
        projected.append({field: container.get(field) for field in PRIVATE_STRUCTURE_FIELDS})
    return payload, projected, errors


def _compact_locator(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return "".join(character for character in text if character.isalnum())


def _court_variants(court: str) -> set[str]:
    variants = {_compact_locator(court)}
    replacements = (
        ("지법", "지방법원"),
        ("고법", "고등법원"),
        ("행법", "행정법원"),
        ("가법", "가정법원"),
    )
    for short, long in replacements:
        if short in court:
            variants.add(_compact_locator(court.replace(short, long)))
        if long in court:
            variants.add(_compact_locator(court.replace(long, short)))
    return {value for value in variants if len(value) >= 4}


def _decision_date_pattern(value: Any) -> re.Pattern[str] | None:
    match = re.fullmatch(r"(18\d{2}|19\d{2}|20\d{2})-(\d{2})-(\d{2})", str(value or ""))
    if match is None:
        return None
    year, month, day = match.groups()
    month_number, day_number = str(int(month)), str(int(day))
    return re.compile(
        rf"(?<!\d){year}\s*(?:년\s*0?{month_number}\s*월\s*0?{day_number}\s*일|"
        rf"[./-]\s*0?{month_number}\s*[./-]\s*0?{day_number}\s*\.?)"
    )


def _safe_identity_values(identity_keys: Any) -> list[str]:
    if not isinstance(identity_keys, dict):
        return []
    values: list[str] = []
    for key, value in identity_keys.items():
        if not isinstance(key, str) or not isinstance(value, str) or not value:
            continue
        # Case/court are checked with their own normalization.  Public-content
        # hashes describe the prompt rather than a forbidden source locator.
        if key in {
            "caseRef",
            "caseNumber",
            "claimContentSHA256",
            "factsContentSHA256",
            "claimFactsContentSHA256",
            "promptSHA256",
            "sourcePromptSHA256",
        }:
            continue
        compact = _compact_locator(value)
        if len(compact) >= 8:
            values.append(compact)
    return sorted(set(values))


def _normalized_content(parts: Iterable[str]) -> str:
    text = unicodedata.normalize("NFKC", "\n".join(parts)).casefold()
    text = re.sub(r"\d+", "0", text)
    return "".join(character for character in text if character == "0" or "a" <= character <= "z" or "가" <= character <= "힣")


def _character_shingles(text: str, width: int) -> set[str]:
    if len(text) < width:
        return set()
    return {text[index : index + width] for index in range(len(text) - width + 1)}


def _filtered_shingle_sets(texts: Sequence[str]) -> tuple[list[set[str]], dict[str, int]]:
    width = int(NEAR_DUPLICATE_SPEC["shingleLength"])
    raw_sets = [_character_shingles(text, width) for text in texts]
    document_frequency: Counter[str] = Counter()
    for shingles in raw_sets:
        document_frequency.update(shingles)
    filter_spec = NEAR_DUPLICATE_SPEC["corpusCommonShingleFilter"]
    cutoff = max(
        math.floor(len(texts) * float(filter_spec["maximumDocumentFraction"])),
        int(filter_spec["minimumDocumentCutoff"]),
    )
    common = {shingle for shingle, count in document_frequency.items() if count > cutoff}
    return (
        [shingles - common for shingles in raw_sets],
        {
            "documentCount": len(texts),
            "documentFrequencyCutoff": cutoff,
            "discardedCommonShingleCount": len(common),
            "retainedDistinctShingleCount": len(document_frequency) - len(common),
        },
    )


def _exact_jaccard_pairs(
    shingle_sets: Sequence[set[str]], threshold: float
) -> tuple[dict[tuple[int, int], float], dict[str, int]]:
    postings: dict[str, list[int]] = defaultdict(list)
    minimum = int(NEAR_DUPLICATE_SPEC["minimumFilteredShingles"])
    eligible = 0
    for index, shingles in enumerate(shingle_sets):
        if len(shingles) < minimum:
            continue
        eligible += 1
        for shingle in shingles:
            postings[shingle].append(index)

    intersections: Counter[tuple[int, int]] = Counter()
    posting_pair_increments = 0
    for indices in postings.values():
        if len(indices) < 2:
            continue
        for left, right in combinations(indices, 2):
            intersections[(left, right)] += 1
            posting_pair_increments += 1

    result: dict[tuple[int, int], float] = {}
    cardinality_pruned = 0
    exact_compared = 0
    for pair, intersection in intersections.items():
        left, right = pair
        left_size = len(shingle_sets[left])
        right_size = len(shingle_sets[right])
        if min(left_size, right_size) / max(left_size, right_size) < threshold:
            cardinality_pruned += 1
            continue
        exact_compared += 1
        similarity = intersection / (left_size + right_size - intersection)
        if similarity >= threshold:
            result[pair] = similarity
    return result, {
        "eligibleDocumentCount": eligible,
        "postingListCount": len(postings),
        "pairsSharingAtLeastOneShingle": len(intersections),
        "postingPairIncrements": posting_pair_increments,
        "cardinalityPrunedPairCount": cardinality_pruned,
        "exactComparedPairCount": exact_compared,
        "thresholdPairCount": len(result),
    }


def _near_duplicate_audit(parsed_rows: Sequence[ParsedPublicRow]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    combined_texts = [
        _normalized_content((*row.claim, *row.facts)) for row in parsed_rows
    ]
    facts_texts = [_normalized_content(row.facts) for row in parsed_rows]
    combined_sets, combined_filter = _filtered_shingle_sets(combined_texts)
    facts_sets, facts_filter = _filtered_shingle_sets(facts_texts)
    thresholds = NEAR_DUPLICATE_SPEC["thresholds"]
    combined_pairs, combined_stats = _exact_jaccard_pairs(
        combined_sets, float(thresholds["claimPlusFactsExactJaccard"])
    )
    facts_pairs, facts_stats = _exact_jaccard_pairs(
        facts_sets, float(thresholds["factsOnlyExactJaccard"])
    )

    all_pairs = sorted(set(combined_pairs) | set(facts_pairs))
    parent = list(range(len(parsed_rows)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left, right in all_pairs:
        union(left, right)

    components: dict[int, list[int]] = defaultdict(list)
    for index in sorted({member for pair in all_pairs for member in pair}):
        components[find(index)].append(index)

    private_families: list[dict[str, Any]] = []
    for members in sorted(components.values(), key=lambda item: tuple(parsed_rows[i].case_id for i in item)):
        member_ids = sorted(parsed_rows[index].case_id for index in members)
        family_id = "near-duplicate-" + sha256_bytes("\n".join(member_ids).encode("utf-8"))[:16]
        member_set = set(members)
        family_pairs: list[dict[str, Any]] = []
        for pair in all_pairs:
            if pair[0] not in member_set or pair[1] not in member_set:
                continue
            family_pairs.append(
                {
                    "leftId": parsed_rows[pair[0]].case_id,
                    "rightId": parsed_rows[pair[1]].case_id,
                    "claimPlusFactsJaccard": (
                        round(combined_pairs[pair], 12) if pair in combined_pairs else None
                    ),
                    "factsOnlyJaccard": (
                        round(facts_pairs[pair], 12) if pair in facts_pairs else None
                    ),
                }
            )
        private_families.append(
            {
                "familyId": family_id,
                "memberIds": member_ids,
                "qualifyingPairs": family_pairs,
            }
        )

    pair_scores = [
        max(combined_pairs.get(pair, 0.0), facts_pairs.get(pair, 0.0))
        for pair in all_pairs
    ]
    aggregate = {
        "specification": NEAR_DUPLICATE_SPEC,
        "specificationSHA256": sha256_bytes(canonical_json_bytes(NEAR_DUPLICATE_SPEC)),
        "exhaustivePossiblePairCount": len(parsed_rows) * (len(parsed_rows) - 1) // 2,
        "filters": {
            "claimPlusFacts": combined_filter,
            "factsOnly": facts_filter,
        },
        "joinStatistics": {
            "claimPlusFacts": combined_stats,
            "factsOnly": facts_stats,
        },
        "qualifyingPairCount": len(all_pairs),
        "familyCount": len(private_families),
        "implicatedRowCount": len({member for pair in all_pairs for member in pair}),
        "largestFamilySize": max((len(family["memberIds"]) for family in private_families), default=0),
        "maximumQualifyingJaccard": round(max(pair_scores), 12) if pair_scores else None,
    }
    return aggregate, private_families


def _target_specific_structure_audit(
    *,
    public_rows: Sequence[ParsedPublicRow],
    public_prompts: Mapping[str, str],
    private_rows: Sequence[Mapping[str, Any]],
    private_read_errors: Sequence[str],
) -> tuple[dict[str, Any], dict[str, list[str]], list[str]]:
    public_by_id = {row.case_id: row for row in public_rows}
    private_by_id: dict[str, Mapping[str, Any]] = {}
    binding_errors = list(private_read_errors)
    detector_ids: dict[str, set[str]] = defaultdict(set)

    for ordinal, row in enumerate(private_rows, 1):
        case_id = row.get("caseId")
        if not isinstance(case_id, str) or OPAQUE_ID_RE.fullmatch(case_id) is None:
            binding_errors.append(f"private_row_{ordinal}:invalid_case_id")
            continue
        if case_id in private_by_id:
            binding_errors.append(f"private_row_{ordinal}:duplicate_case_id")
            continue
        private_by_id[case_id] = row

    missing_private = sorted(set(public_by_id) - set(private_by_id))
    extra_private = sorted(set(private_by_id) - set(public_by_id))
    if missing_private:
        binding_errors.append(f"missing_private_rows:{len(missing_private)}")
    if extra_private:
        binding_errors.append(f"extra_private_rows:{len(extra_private)}")

    for case_id in sorted(set(public_by_id) & set(private_by_id)):
        public_row = public_by_id[case_id]
        private_row = private_by_id[case_id]
        prompt = public_prompts[case_id]
        evidence = "\n".join((*public_row.claim, *public_row.facts))
        compact_evidence = _compact_locator(evidence)

        if private_row.get("domain") != public_row.domain:
            binding_errors.append(f"{case_id}:domain_mismatch")
        expected_prompt_hash = sha256_bytes(normalize_text(prompt).encode("utf-8"))
        if private_row.get("promptSHA256") != expected_prompt_hash:
            binding_errors.append(f"{case_id}:prompt_hash_mismatch")

        case_ref = private_row.get("caseRef")
        if not isinstance(case_ref, str) or case_ref.count("|") != 1:
            binding_errors.append(f"{case_id}:invalid_case_ref")
            court, case_number = "", ""
        else:
            court, case_number = case_ref.split("|", 1)
        try:
            authoritative_patterns = reserve_builder.target_metadata_patterns(
                court=court,
                case_number=case_number,
                decision_date=private_row.get("decisionDate"),
            )
        except reserve_builder.ReserveBuildError:
            binding_errors.append(f"{case_id}:invalid_target_metadata_pattern")
            authoritative_counts = {}
        else:
            authoritative_counts = reserve_builder.target_metadata_match_counts(
                evidence, authoritative_patterns
            )
        compact_case_number = _compact_locator(case_number)
        if (
            authoritative_counts.get("caseNumber", 0)
            or (len(compact_case_number) >= 6 and compact_case_number in compact_evidence)
        ):
            detector_ids["target_case_number"].add(case_id)
        if authoritative_counts.get("court", 0) or any(
            variant in compact_evidence for variant in _court_variants(court)
        ):
            detector_ids["target_court"].add(case_id)

        date_pattern = _decision_date_pattern(private_row.get("decisionDate"))
        if date_pattern is None:
            binding_errors.append(f"{case_id}:invalid_decision_date")
        elif (
            authoritative_counts.get("decisionDate", 0)
            or date_pattern.search(evidence) is not None
        ):
            detector_ids["target_decision_date"].add(case_id)

        for detector, field in (
            ("target_canonical_id", "canonicalId"),
            ("target_source_dataset", "sourceDataset"),
        ):
            compact_value = _compact_locator(private_row.get(field))
            if len(compact_value) >= 8 and compact_value in compact_evidence:
                detector_ids[detector].add(case_id)

        if any(
            value in compact_evidence
            for value in _safe_identity_values(private_row.get("identityKeys"))
        ):
            detector_ids["target_source_identity_key"].add(case_id)

    implicated = sorted(set().union(*detector_ids.values())) if detector_ids else []
    aggregate = {
        "method": {
            "version": "paired-nongold-target-identity-screen-v1",
            "privateFieldsAccessed": list(PRIVATE_STRUCTURE_FIELDS),
            "forbiddenGoldFieldsAccessed": [],
            "comparisonScope": "each private structure row only against its same-case public evidence",
            "normalization": "NFKC, casefold, retain Unicode alphanumeric characters",
            "courtAliases": [
                "지법<->지방법원",
                "고법<->고등법원",
                "행법<->행정법원",
                "가법<->가정법원",
            ],
            "compoundCaseNumbers": "explicit and inherited joined/participating docket components",
            "dateForms": ["YYYY.M.D", "YYYY-M-D", "YYYY/M/D", "YYYY년 M월 D일"],
        },
        "pairedRowCount": len(set(public_by_id) & set(private_by_id)),
        "privateStructureReadErrorCount": len(private_read_errors),
        "bindingErrorCount": len(binding_errors),
        "rowsWithTargetMetadata": len(implicated),
        "rowsByDetector": {
            detector: len(ids) for detector, ids in sorted(detector_ids.items())
        },
        "pass": not binding_errors and not implicated,
    }
    aggregate["method"]["specificationSHA256"] = sha256_bytes(
        canonical_json_bytes({key: value for key, value in aggregate["method"].items() if key != "specificationSHA256"})
    )
    return aggregate, {name: sorted(ids) for name, ids in detector_ids.items()}, binding_errors


def _construction_binding_audit(
    *,
    manifest_path: Path,
    public_path: Path,
    private_path: Path,
    public_row_count: int,
    private_row_count: int,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    try:
        manifest_payload = manifest_path.read_bytes()
        manifest = json.loads(manifest_payload)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return {
            "pass": False,
            "bindingErrorCount": 1,
            "manifestReadable": False,
        }, [f"manifest_unreadable:{type(error).__name__}"]
    if not isinstance(manifest, dict):
        return {
            "pass": False,
            "bindingErrorCount": 1,
            "manifestReadable": True,
        }, ["manifest_not_object"]

    if not verify_self_hash(manifest):
        errors.append("manifest_self_hash_mismatch")
    if manifest.get("protocol") != "source-disjoint-outcome-candidate-inventory-v1":
        errors.append("manifest_protocol_mismatch")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        artifacts = {}
        errors.append("manifest_artifacts_missing")
    for kind, path, row_count in (
        ("public", public_path, public_row_count),
        ("private", private_path, private_row_count),
    ):
        receipt = artifacts.get(kind)
        if not isinstance(receipt, dict):
            errors.append(f"manifest_{kind}_receipt_missing")
            continue
        if receipt.get("sha256") != sha256_file(path):
            errors.append(f"manifest_{kind}_sha256_mismatch")
        if receipt.get("bytes") != path.stat().st_size:
            errors.append(f"manifest_{kind}_byte_count_mismatch")
        if receipt.get("rows") != row_count:
            errors.append(f"manifest_{kind}_row_count_mismatch")

    implementation = manifest.get("implementation")
    if not isinstance(implementation, dict):
        implementation = {}
        errors.append("manifest_implementation_missing")
    builder_path = REPO_ROOT / "tools" / "build_disjoint_outcome_reserve.py"
    extractor_path = REPO_ROOT / "tools" / "build_outcome_prediction_benchmark.py"
    if implementation.get("builderSHA256") != sha256_file(builder_path):
        errors.append("builder_sha256_mismatch")
    if implementation.get("upstreamExtractorSHA256") != sha256_file(extractor_path):
        errors.append("upstream_extractor_sha256_mismatch")

    scan_counts = manifest.get("scanCounts")
    if not isinstance(scan_counts, dict):
        scan_counts = {}
        errors.append("manifest_scan_counts_missing")
    exclusion_counts = {
        reason: int(scan_counts.get("leak." + reason, 0))
        for reason in (
            "claim_points_to_holding",
            "holding_section_marker",
            "holding_text_overlap",
        )
        if isinstance(scan_counts.get("leak." + reason, 0), int)
    }
    if len(exclusion_counts) != 3:
        errors.append("invalid_holding_exclusion_counts")

    holding_policy_source = inspect.getsource(reserve_builder.holding_leak_reason).encode("utf-8")
    aggregate = {
        "pass": not errors,
        "bindingErrorCount": len(errors),
        "manifestReadable": True,
        "manifestSHA256": sha256_bytes(manifest_payload),
        "manifestSelfHash": manifest.get("selfHash"),
        "builderSHA256": sha256_file(builder_path),
        "upstreamExtractorSHA256": sha256_file(extractor_path),
        "holdingLeakPolicyFunctionSHA256": sha256_bytes(holding_policy_source),
        "boundPreselectionExclusionCounts": exclusion_counts,
        "policyMeaning": (
            "the hash-bound builder rejects claim pointers to the holding, holding-section markers, "
            "and exact normalized holding-text overlap before candidate selection"
        ),
    }
    return aggregate, errors


def audit_public_inventory(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    path = path.resolve()
    payload, loaded_rows, read_errors = _load_public_jsonl(path)
    structural_counts: Counter[str] = Counter(read_errors)
    structural_ids: dict[str, set[str]] = defaultdict(set)
    parsed_rows: list[ParsedPublicRow] = []
    seen_ids: set[str] = set()

    for ordinal, raw_row in enumerate(loaded_rows, 1):
        fallback_id = f"invalid-row-{ordinal:06d}"
        if not isinstance(raw_row, dict):
            structural_counts["row_not_object"] += 1
            structural_ids["row_not_object"].add(fallback_id)
            continue
        raw_id = raw_row.get("id")
        case_id = raw_id if isinstance(raw_id, str) else fallback_id
        if set(raw_row) != EXPECTED_PUBLIC_KEYS:
            structural_counts["nonexact_public_schema"] += 1
            structural_ids["nonexact_public_schema"].add(case_id)
        if not isinstance(raw_id, str) or OPAQUE_ID_RE.fullmatch(raw_id) is None:
            structural_counts["invalid_opaque_id"] += 1
            structural_ids["invalid_opaque_id"].add(case_id)
        elif raw_id in seen_ids:
            structural_counts["duplicate_id"] += 1
            structural_ids["duplicate_id"].add(case_id)
        else:
            seen_ids.add(raw_id)
        for key, expected in EXPECTED_CONSTANTS.items():
            if raw_row.get(key) != expected:
                structural_counts[f"constant_mismatch.{key}"] += 1
                structural_ids[f"constant_mismatch.{key}"].add(case_id)
        prompt = raw_row.get("prompt")
        if not isinstance(prompt, str):
            structural_counts["prompt_not_string"] += 1
            structural_ids["prompt_not_string"].add(case_id)
            continue
        if isinstance(raw_id, str) and raw_id in prompt:
            structural_counts["opaque_id_embedded_in_prompt"] += 1
            structural_ids["opaque_id_embedded_in_prompt"].add(case_id)
        try:
            parsed = parse_public_prompt(prompt)
        except ValueError as error:
            structural_counts[str(error)] += 1
            structural_ids[str(error)].add(case_id)
            continue
        parsed_rows.append(
            ParsedPublicRow(case_id, parsed.domain, parsed.claim, parsed.facts)
        )

    leak_detector_rows: dict[str, set[str]] = defaultdict(set)
    leak_category_rows: dict[str, set[str]] = defaultdict(set)
    per_id_leaks: dict[str, set[str]] = defaultdict(set)
    for row in parsed_rows:
        evidence = "\n".join((*row.claim, *row.facts))
        for category, detector, pattern in LEAK_PATTERNS:
            if pattern.search(evidence) is not None:
                leak_detector_rows[detector].add(row.case_id)
                leak_category_rows[category].add(row.case_id)
                per_id_leaks[row.case_id].add(detector)

    near_duplicate, private_families = _near_duplicate_audit(parsed_rows)
    family_ids_by_case: dict[str, list[str]] = defaultdict(list)
    for family in private_families:
        for case_id in family["memberIds"]:
            family_ids_by_case[case_id].append(family["familyId"])

    all_implicated_ids = sorted(
        set(per_id_leaks)
        | set(family_ids_by_case)
        | {case_id for values in structural_ids.values() for case_id in values}
    )
    private_findings = []
    for case_id in all_implicated_ids:
        private_findings.append(
            {
                "id": case_id,
                "structuralFindings": sorted(
                    name for name, ids in structural_ids.items() if case_id in ids
                ),
                "leakDetectors": sorted(per_id_leaks.get(case_id, ())),
                "nearDuplicateFamilyIds": sorted(family_ids_by_case.get(case_id, ())),
            }
        )

    private_artifact: dict[str, Any] = {
        "schemaVersion": AUDIT_SCHEMA_VERSION + ".implicated-ids",
        "containsGoldOrLabels": False,
        "sourcePublicSHA256": sha256_bytes(payload),
        "findingCount": len(private_findings),
        "findings": private_findings,
        "nearDuplicateFamilies": private_families,
    }
    private_artifact["selfHash"] = self_hash(private_artifact)

    structural_violation_count = sum(structural_counts.values())
    rows_with_leak = set().union(*leak_category_rows.values()) if leak_category_rows else set()
    public_screen_reasons: list[str] = []
    if structural_violation_count:
        public_screen_reasons.append("public_contract_violation")
    if near_duplicate["qualifyingPairCount"]:
        public_screen_reasons.append("lexical_near_duplicate_family")

    leak_spec = [
        {"category": category, "detector": detector, "regex": pattern.pattern, "flags": pattern.flags}
        for category, detector, pattern in LEAK_PATTERNS
    ]
    report: dict[str, Any] = {
        "schemaVersion": AUDIT_SCHEMA_VERSION,
        "input": {
            "basename": path.name,
            "bytes": len(payload),
            "sha256": sha256_bytes(payload),
            "jsonRowCount": len(loaded_rows),
        },
        "implementation": {
            "basename": Path(__file__).name,
            "sha256": sha256_file(Path(__file__).resolve()),
        },
        "goldSafety": {
            "inputArity": 1,
            "readsCompanionFiles": False,
            "acceptsPrivateOrGoldInput": False,
            "readsOrInfersLabels": False,
            "emitsPromptTextOrMatchedSubstrings": False,
        },
        "publicContract": {
            "expectedExactKeys": sorted(EXPECTED_PUBLIC_KEYS),
            "expectedConstants": EXPECTED_CONSTANTS,
            "opaqueIdRegex": OPAQUE_ID_RE.pattern,
            "inputReadErrorCount": len(read_errors),
            "parsedPromptCount": len(parsed_rows),
            "structuralViolationCount": structural_violation_count,
            "findingsByType": dict(sorted(structural_counts.items())),
            "uniqueIdCount": len(seen_ids),
        },
        "leakAudit": {
            "scope": "template-stripped evidence clauses only; fixed task instructions excluded",
            "interpretation": (
                "informational conservative sensitivity flags; dates, courts, related case numbers, "
                "and procedural outcome words can be legitimate predictive facts"
            ),
            "affectsFinalGate": False,
            "specification": leak_spec,
            "specificationSHA256": sha256_bytes(canonical_json_bytes(leak_spec)),
            "rowsWithAnyFinding": len(rows_with_leak),
            "rowsByCategory": {
                category: len(ids) for category, ids in sorted(leak_category_rows.items())
            },
            "rowsByDetector": {
                detector: len(ids) for detector, ids in sorted(leak_detector_rows.items())
            },
        },
        "nearDuplicateAudit": near_duplicate,
        "implicatedIdsArtifact": {
            "findingCount": len(private_findings),
            "sha256": sha256_bytes(canonical_json_bytes(private_artifact) + b"\n"),
            "selfHash": private_artifact["selfHash"],
            "containsGoldOrLabels": False,
        },
        "gates": {
            "publicContract": {"pass": structural_violation_count == 0},
            "lexicalNearDuplicate": {
                "pass": near_duplicate["qualifyingPairCount"] == 0
            },
            "genericRegexSensitivity": {
                "passFailApplicable": False,
                "rowsWithAnyFinding": len(rows_with_leak),
            },
            "constructionConclusionLeakage": {"status": "NOT_RUN"},
            "targetSpecificMetadata": {"status": "NOT_RUN"},
            "finalPreSolver": {
                "pass": False,
                "reasons": ["bound_private_structure_and_manifest_not_provided"],
            },
        },
        "publicOnlyScreen": {
            "pass": not public_screen_reasons,
            "reasons": public_screen_reasons,
        },
        "limitations": [
            "The public-only audit cannot test correlation between opaque IDs and sealed labels.",
            "Lexical shingles do not detect semantically equivalent cases with little surface overlap.",
            "Generic regex findings can be legitimate dates, procedural-history references, or predictive facts and are informational only.",
            "A target-specific string screen cannot detect a semantically paraphrased procedural outcome or source identity.",
            "No claim of model-unseen or contamination-free status follows from this audit.",
        ],
    }
    report["gate"] = report["gates"]["finalPreSolver"]
    report["selfHash"] = self_hash(report)
    return report, private_artifact


def audit_bound_inventory(
    public_path: Path,
    private_structure_path: Path,
    manifest_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run the final gate while projecting no label or holding values."""
    public_path = public_path.resolve()
    private_structure_path = private_structure_path.resolve()
    manifest_path = manifest_path.resolve()
    report, private_artifact = audit_public_inventory(public_path)

    _public_payload, loaded_public, _public_errors = _load_public_jsonl(public_path)
    parsed_public: list[ParsedPublicRow] = []
    public_prompts: dict[str, str] = {}
    for raw_row in loaded_public:
        if not isinstance(raw_row, dict):
            continue
        case_id, prompt = raw_row.get("id"), raw_row.get("prompt")
        if not isinstance(case_id, str) or not isinstance(prompt, str):
            continue
        try:
            parsed = parse_public_prompt(prompt)
        except ValueError:
            continue
        parsed_public.append(
            ParsedPublicRow(case_id, parsed.domain, parsed.claim, parsed.facts)
        )
        public_prompts[case_id] = prompt

    private_payload, projected_private, private_errors = _load_private_structure_jsonl(
        private_structure_path
    )
    target_gate, target_detector_ids, target_binding_errors = (
        _target_specific_structure_audit(
            public_rows=parsed_public,
            public_prompts=public_prompts,
            private_rows=projected_private,
            private_read_errors=private_errors,
        )
    )
    construction_gate, construction_errors = _construction_binding_audit(
        manifest_path=manifest_path,
        public_path=public_path,
        private_path=private_structure_path,
        public_row_count=len(loaded_public),
        private_row_count=len(projected_private),
    )

    findings_by_id = {
        finding["id"]: dict(finding) for finding in private_artifact["findings"]
    }
    target_ids = sorted(
        {case_id for ids in target_detector_ids.values() for case_id in ids}
    )
    for case_id in target_ids:
        finding = findings_by_id.setdefault(
            case_id,
            {
                "id": case_id,
                "structuralFindings": [],
                "leakDetectors": [],
                "nearDuplicateFamilyIds": [],
            },
        )
        finding["targetMetadataDetectors"] = sorted(
            detector for detector, ids in target_detector_ids.items() if case_id in ids
        )
    for finding in findings_by_id.values():
        finding.setdefault("targetMetadataDetectors", [])

    private_artifact.pop("selfHash", None)
    private_artifact.update(
        {
            "sourcePrivateStructureSHA256": sha256_bytes(private_payload),
            "sourceManifestSHA256": sha256_file(manifest_path),
            "findingCount": len(findings_by_id),
            "findings": [findings_by_id[key] for key in sorted(findings_by_id)],
            "targetSpecificMetadata": {
                "detectorIds": target_detector_ids,
                "bindingErrors": target_binding_errors,
            },
            "constructionBindingErrors": construction_errors,
        }
    )
    private_artifact["selfHash"] = self_hash(private_artifact)

    final_reasons: list[str] = []
    if not report["gates"]["publicContract"]["pass"]:
        final_reasons.append("public_contract_violation")
    if not report["gates"]["lexicalNearDuplicate"]["pass"]:
        final_reasons.append("lexical_near_duplicate_family")
    if not construction_gate["pass"]:
        final_reasons.append("construction_conclusion_leakage_binding_failed")
    if not target_gate["pass"]:
        final_reasons.append("target_specific_metadata_or_pair_binding_failed")

    report.pop("selfHash", None)
    report["input"]["privateStructure"] = {
        "basename": private_structure_path.name,
        "bytes": len(private_payload),
        "sha256": sha256_bytes(private_payload),
        "jsonRowCount": len(projected_private),
    }
    report["input"]["manifest"] = {
        "basename": manifest_path.name,
        "bytes": manifest_path.stat().st_size,
        "sha256": sha256_file(manifest_path),
    }
    report["goldSafety"] = {
        "inputArity": 3,
        "readsCompanionFiles": True,
        "privateInputProjection": list(PRIVATE_STRUCTURE_FIELDS),
        "privateGoldFieldsAccessed": [],
        "readsOrInfersLabels": False,
        "usesHoldingText": False,
        "emitsPromptTextOrMatchedSubstrings": False,
    }
    report["targetSpecificMetadataAudit"] = target_gate
    report["constructionConclusionLeakageAudit"] = construction_gate
    report["gates"]["constructionConclusionLeakage"] = {
        "status": "PASS" if construction_gate["pass"] else "FAIL",
        "pass": construction_gate["pass"],
    }
    report["gates"]["targetSpecificMetadata"] = {
        "status": "PASS" if target_gate["pass"] else "FAIL",
        "pass": target_gate["pass"],
    }
    report["gates"]["finalPreSolver"] = {
        "pass": not final_reasons,
        "reasons": final_reasons,
    }
    report["gate"] = report["gates"]["finalPreSolver"]
    report["implicatedIdsArtifact"] = {
        "findingCount": private_artifact["findingCount"],
        "sha256": sha256_bytes(canonical_json_bytes(private_artifact) + b"\n"),
        "selfHash": private_artifact["selfHash"],
        "containsGoldOrLabels": False,
    }
    report["selfHash"] = self_hash(report)
    return report, private_artifact


def _write_exclusive(path: Path, payload: bytes, *, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def write_audit_outputs(
    report: Mapping[str, Any],
    private_artifact: Mapping[str, Any],
    *,
    report_path: Path,
    implicated_ids_path: Path,
) -> None:
    if report_path.resolve() == implicated_ids_path.resolve():
        raise PublicAuditError("report and implicated-ID paths must differ")
    # Write the private ID artifact first so a public report never points to a
    # nonexistent details file.  Both operations are exclusive/no-overwrite.
    _write_exclusive(
        implicated_ids_path.resolve(), canonical_json_bytes(private_artifact) + b"\n", mode=0o600
    )
    try:
        _write_exclusive(report_path.resolve(), canonical_json_bytes(report) + b"\n", mode=0o600)
    except Exception:
        # Preserve the already-created details artifact as an auditable partial
        # output; never delete or overwrite it implicitly.
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-public", required=True, type=Path)
    parser.add_argument("--input-private-structure", required=True, type=Path)
    parser.add_argument("--input-manifest", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--implicated-ids-private", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report, private_artifact = audit_bound_inventory(
            args.input_public,
            args.input_private_structure,
            args.input_manifest,
        )
        write_audit_outputs(
            report,
            private_artifact,
            report_path=args.report,
            implicated_ids_path=args.implicated_ids_private,
        )
    except (OSError, PublicAuditError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "gatePass": report["gate"]["pass"],
                "report": str(args.report),
                "reportSelfHash": report["selfHash"],
                "implicatedIds": str(args.implicated_ids_private),
                "implicatedIdsSelfHash": private_artifact["selfHash"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report["gate"]["pass"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
