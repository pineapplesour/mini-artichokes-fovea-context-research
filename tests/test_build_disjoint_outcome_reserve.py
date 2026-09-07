import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from tools import build_disjoint_outcome_reserve as reserve


SCHEMA = """
CREATE TABLE precedents (
    canonical_id TEXT PRIMARY KEY,
    source_dataset TEXT,
    court TEXT,
    case_number TEXT,
    decision_date TEXT,
    case_name TEXT,
    full_text TEXT,
    text_hash TEXT,
    source_record_id TEXT,
    source_path TEXT,
    dedupe_key TEXT,
    dedupe_key_primary TEXT,
    dedupe_key_fallback TEXT,
    split_group_id TEXT
)
"""


def _claim(tag: str) -> str:
    return f"피고는 원고에게 {tag} 계약에 따른 원금과 지연손해금을 지급하라. " + ("청구 내용 " * 8)


def _facts(tag: str, domain: str) -> str:
    heading = "1. 처분의 경위" if domain == "tax" else "1. 기초사실"
    lines = [heading]
    for index in range(50):
        lines.append(
            f"{tag} 관련 사실 {index:02d}: 당사자 사이의 문서와 거래 경위가 확인되었고 "
            "각 자료의 작성 시점과 이행 과정이 기록되어 있다."
        )
    return "\n".join(lines)


def _holding(label: str) -> str:
    if label == "인용됨":
        return "1. 피고는 원고에게 100원을 지급하라.\n2. 소송비용은 피고가 부담한다."
    return "1. 원고의 청구를 모두 기각한다.\n2. 소송비용은 원고가 부담한다."


def _row(
    canonical: str,
    *,
    domain: str,
    label: str,
    tag: str | None = None,
    dataset: str | None = None,
    court: str | None = None,
    case_number: str | None = None,
    dedupe_key: str | None = None,
    dedupe_primary: str | None = None,
    dedupe_fallback: str | None = None,
    text_hash: str | None = None,
    split_group: str | None = None,
    source_record_id: str | None = None,
    source_path: str | None = None,
    claim: str | None = None,
    facts: str | None = None,
) -> dict:
    tag = tag or canonical
    claim = _claim(tag) if claim is None else claim
    facts = _facts(tag, domain) if facts is None else facts
    holding = _holding(label)
    if domain == "tax":
        full_text = f"주 문\n{holding}\n이 유\n{facts}\n2. 판단\n판단 내용"
    else:
        full_text = (
            f"주 문\n{holding}\n청 구 취 지\n{claim}\n이 유\n{facts}\n2. 판단\n판단 내용"
        )
    suffix = canonical.replace("-", "")
    case_serial = (
        int(hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:8], 16)
        % 900000
        + 100000
    )
    return {
        "canonical_id": canonical,
        "source_dataset": dataset or f"dataset-{suffix}",
        "court": court or "서울중앙지방법원",
        "case_number": case_number
        or (f"2020구합{case_serial}" if domain == "tax" else f"2020가합{case_serial}"),
        "decision_date": "2020-06-01",
        "case_name": "부가가치세부과처분취소" if domain == "tax" else "대여금",
        "full_text": full_text,
        "text_hash": text_hash or f"text-{suffix}",
        "source_record_id": source_record_id or f"record-{suffix}",
        "source_path": source_path or f"sources/{suffix}/judgment.json",
        "dedupe_key": dedupe_key or f"dedupe-{suffix}",
        "dedupe_key_primary": dedupe_primary or f"primary-{suffix}",
        "dedupe_key_fallback": dedupe_fallback or f"fallback-{suffix}",
        "split_group_id": split_group or f"split-{suffix}",
    }


def _create_db(path: Path, rows: list[dict]) -> None:
    connection = sqlite3.connect(path)
    connection.execute(SCHEMA)
    columns = tuple(rows[0])
    placeholders = ",".join("?" for _ in columns)
    connection.executemany(
        f"INSERT INTO precedents ({','.join(columns)}) VALUES ({placeholders})",
        [tuple(row[column] for column in columns) for row in rows],
    )
    connection.commit()
    connection.close()


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _make_prior(prior_dir: Path, historical: dict, *, public_prompt: str = "과거 공개 프롬프트") -> None:
    prior_dir.mkdir()
    _write_jsonl(
        prior_dir / "outcome_old.private.jsonl",
        [
            {
                "caseId": "old-1",
                "label": "인용됨",
                "caseRef": f"{historical['court']}|{historical['case_number']}",
                "canonicalId": historical["canonical_id"],
                "decisionDate": historical["decision_date"],
                "holding": _holding("인용됨"),
            }
        ],
    )
    _write_jsonl(
        prior_dir / "outcome_old.public.jsonl",
        [{"id": "old-1", "prompt": public_prompt}],
    )


def _config(*, strict: bool = False, target: int = 1, candidate: int = 1) -> reserve.BuildConfig:
    return reserve.BuildConfig(
        seed_salt="synthetic-confirmation",
        min_date="2005-01-01",
        max_date="2021-12-31",
        strict_dataset_disjoint=strict,
        quotas={
            "civil": reserve.StratumQuota(target, candidate),
            "tax": reserve.StratumQuota(target, candidate),
        },
    )


def _clean_quota_rows() -> list[dict]:
    return [
        _row("clean-cg", domain="civil", label="인용됨"),
        _row("clean-cd", domain="civil", label="기각"),
        _row("clean-tg", domain="tax", label="인용됨"),
        _row("clean-td", domain="tax", label="기각"),
    ]


def test_closes_every_historical_identity_key_and_normalized_prompt(tmp_path):
    historical = _row("historical", domain="civil", label="인용됨", dataset="old-dataset")
    prompt_claim = _claim("prompt-match")
    prompt_facts = _facts("prompt-match", "civil")
    wrapper_facts = _facts("wrapper-facts-match", "civil")
    prompt_match = reserve.render_prompt(
        domain="civil",
        claim_clauses=reserve.segment_evidence(prompt_claim, prefix="C"),
        facts_clauses=reserve.segment_evidence(prompt_facts, prefix="F"),
    )
    rows = [
        historical,
        _row(
            "match-ref",
            domain="civil",
            label="인용됨",
            court="  " + historical["court"].upper() + "  ",
            case_number=historical["case_number"].replace("가합", " 가합 "),
        ),
        _row(
            "match-number", domain="civil", label="인용됨",
            case_number=historical["case_number"].replace("가합", " 가합 "),
        ),
        _row(
            "match-source-record", domain="civil", label="인용됨",
            source_record_id=historical["source_record_id"],
        ),
        _row(
            "match-dataset-record", domain="civil", label="인용됨",
            dataset=historical["source_dataset"],
            source_record_id=historical["source_record_id"],
        ),
        _row(
            "match-source-path", domain="civil", label="인용됨",
            source_path="  SOURCES\\historical\\judgment.json  ",
        ),
        _row(
            "match-dedupe", domain="civil", label="인용됨",
            dedupe_key=historical["dedupe_key"],
        ),
        _row(
            "match-primary", domain="civil", label="인용됨",
            dedupe_primary=historical["dedupe_key_primary"],
        ),
        _row(
            "match-fallback", domain="civil", label="인용됨",
            dedupe_fallback=historical["dedupe_key_fallback"],
        ),
        _row(
            "match-text", domain="civil", label="인용됨",
            text_hash=historical["text_hash"],
        ),
        _row(
            "match-split", domain="civil", label="인용됨",
            split_group=historical["split_group_id"],
        ),
        _row(
            "match-prompt", domain="civil", label="인용됨", tag="prompt-match",
            claim=prompt_claim, facts=prompt_facts,
        ),
        _row(
            "match-facts-wrapper", domain="civil", label="인용됨",
            facts=wrapper_facts,
        ),
        *_clean_quota_rows(),
    ]
    db = tmp_path / "precedents.sqlite3"
    _create_db(db, rows)
    prior = tmp_path / "prior"
    _make_prior(prior, historical, public_prompt=" \n" + prompt_match + "\n ")
    _write_jsonl(
        prior / "outcome_old.public.jsonl",
        [
            {"id": "old-1", "prompt": " \n" + prompt_match + "\n "},
            {
                "id": "public-only-wrapper",
                "prompt": (
                    "완전히 다른 외부 설명입니다.\n\n[기초사실]\n"
                    + wrapper_facts
                    + "\n\n[응답 지침]\n별도의 형식으로 답하십시오."
                ),
            },
        ],
    )

    built = reserve.build_candidate_inventory(db_path=db, prior_dir=prior, config=_config())
    surviving = {row["canonicalId"] for row in built.private_rows}
    assert "historical" not in surviving
    assert not {
        "match-ref", "match-number", "match-source-record", "match-dataset-record",
        "match-source-path", "match-dedupe", "match-primary", "match-fallback",
        "match-text", "match-split", "match-prompt", "match-facts-wrapper",
    } & surviving
    counts = built.metadata["scanCounts"]
    assert counts["priorExcluded.canonicalId"] >= 1
    assert counts["priorExcluded.caseRef"] >= 2
    assert counts["priorExcluded.caseNumber"] >= 3
    assert counts["priorExcluded.sourceRecordId"] >= 3
    assert counts["priorExcluded.sourceDatasetRecordId"] >= 2
    assert counts["priorExcluded.sourcePathLocator"] >= 2
    assert counts["priorExcluded.dedupeKey"] >= 2
    assert counts["priorExcluded.dedupeKeyPrimary"] >= 2
    assert counts["priorExcluded.dedupeKeyFallback"] >= 2
    assert counts["priorExcluded.textHash"] >= 2
    assert counts["priorExcluded.splitGroupId"] >= 2
    assert counts["priorExcluded.promptSHA256"] >= 1
    assert counts["priorExcluded.factsContentSHA256"] >= 1
    parse_counts = built.metadata["priorClosure"]["publicContentParseCounts"]
    assert parse_counts["parsedFacts"] == 2
    assert parse_counts.get("unparsedFacts", 0) == 0


def test_default_strict_mode_excludes_entire_historical_source_dataset(tmp_path):
    historical = _row("historical", domain="civil", label="인용됨", dataset="shared-source")
    same_source = _row(
        "same-source", domain="civil", label="인용됨", dataset=" SHARED-SOURCE "
    )
    same_source["full_text"] = "이 행은 gold parsing 전에 제외되어야 한다. " * 120
    db = tmp_path / "precedents.sqlite3"
    _create_db(db, [historical, same_source, *_clean_quota_rows()])
    prior = tmp_path / "prior"
    _make_prior(prior, historical)

    built = reserve.build_candidate_inventory(
        db_path=db, prior_dir=prior, config=_config(strict=True)
    )
    assert "same-source" not in {row["canonicalId"] for row in built.private_rows}
    assert built.metadata["scanCounts"]["priorExcluded.sourceDataset"] >= 1
    assert built.metadata["scanCounts"]["priorExcluded.sourceDatasetBeforeGold"] >= 1
    assert built.metadata["scanCounts"]["datasetFilter.sqlExactExclusionValues"] == 1
    assert built.metadata["scanCounts"].get("extract.noSections", 0) == 0
    assert built.metadata["priorClosure"]["strictDatasetDisjoint"] is True
    assert built.metadata["priorClosure"]["excludedSourceDatasets"] == ["shared-source"]
    dataset_filter = built.metadata["priorClosure"]["datasetFiltering"]
    assert dataset_filter["sqlExactPushdown"] is True
    assert dataset_filter["pythonNormalizedPreGoldRecheck"] is True
    query = reserve._candidate_query(exact_dataset_exclusion_count=1)
    assert query.index("source_dataset NOT IN") < query.index("length(full_text)")


def test_missing_court_is_deterministically_excluded_not_fabricated(tmp_path):
    historical = _row("historical", domain="civil", label="인용됨")
    dirty = _row("missing-court", domain="civil", label="인용됨")
    dirty["court"] = ""
    db = tmp_path / "precedents.sqlite3"
    _create_db(db, [historical, dirty, *_clean_quota_rows()])
    prior = tmp_path / "prior"
    _make_prior(prior, historical)

    built = reserve.build_candidate_inventory(db_path=db, prior_dir=prior, config=_config())

    assert "missing-court" not in {row["canonicalId"] for row in built.private_rows}
    assert built.metadata["scanCounts"]["extract.missingCourtOrCaseNumber"] == 1


def test_prior_db_missing_court_uses_frozen_private_case_ref(tmp_path):
    historical = _row("historical", domain="civil", label="인용됨")
    prior = tmp_path / "prior"
    _make_prior(prior, historical)
    historical_db = dict(historical)
    historical_db["court"] = ""
    db = tmp_path / "precedents.sqlite3"
    _create_db(db, [historical_db, *_clean_quota_rows()])

    built = reserve.build_candidate_inventory(db_path=db, prior_dir=prior, config=_config())

    closure = built.metadata["priorClosure"]
    assert closure["resolvedDbRowsMissingCourtOrCaseNumber"] == 1
    assert closure["keyCardinalities"]["caseRef"] == 1


def test_deterministic_numbered_evidence_and_facts_only_tax_prompt(tmp_path):
    historical = _row("historical", domain="civil", label="인용됨")
    db = tmp_path / "precedents.sqlite3"
    _create_db(db, [historical, *_clean_quota_rows()])
    prior = tmp_path / "prior"
    _make_prior(prior, historical)

    first = reserve.build_candidate_inventory(db_path=db, prior_dir=prior, config=_config())
    second = reserve.build_candidate_inventory(db_path=db, prior_dir=prior, config=_config())
    assert first.public_rows == second.public_rows
    assert first.private_rows == second.private_rows
    assert first.metadata == second.metadata
    tax_private = next(row for row in first.private_rows if row["domain"] == "tax")
    tax_public = next(row for row in first.public_rows if row["id"] == tax_private["caseId"])
    assert "None" not in tax_public["prompt"]
    assert "[당사자 주장]" not in tax_public["prompt"]
    assert "[F001]" in tax_public["prompt"]
    assert tax_private["sourceFields"]["claim"] == ""
    assert tax_private["sourceFields"]["facts"].startswith("1. 처분의 경위")
    spec = first.metadata["evidenceSegmentation"]
    assert spec["version"] == reserve.EVIDENCE_SEGMENTATION_VERSION
    assert spec["specificationSHA256"] == hashlib.sha256(
        reserve.canonical_json_bytes(spec["specification"])
    ).hexdigest()


def test_builder_redacts_only_public_transport_and_preserves_unredacted_closure(tmp_path):
    historical = _row("historical", domain="civil", label="인용됨")
    court = "서울중앙지법"
    case_number = "2020가합12345"
    decision_date = "2020-06-01"
    claim = _claim("redaction-target") + f" {court} {case_number} 기록에 따른 청구이다."
    facts = _facts("redaction-target", "civil") + (
        f"\n{court}의 {case_number} 사건은 {decision_date} 기록되었다."
    )
    target = _row(
        "redaction-target",
        domain="civil",
        label="인용됨",
        court=court,
        case_number=case_number,
        claim=claim,
        facts=facts,
    )
    target["decision_date"] = decision_date
    rows = [
        historical,
        target,
        _row("only-cd", domain="civil", label="기각"),
        _row("only-tg", domain="tax", label="인용됨"),
        _row("only-td", domain="tax", label="기각"),
    ]
    db = tmp_path / "precedents.sqlite3"
    _create_db(db, rows)
    prior = tmp_path / "prior"
    _make_prior(prior, historical)

    built = reserve.build_candidate_inventory(db_path=db, prior_dir=prior, config=_config())
    private = next(row for row in built.private_rows if row["canonicalId"] == "redaction-target")
    public = next(row for row in built.public_rows if row["id"] == private["caseId"])

    assert court in private["sourceFields"]["facts"]
    assert case_number in private["sourceFields"]["facts"]
    assert decision_date in private["sourceFields"]["facts"]
    assert court not in public["prompt"]
    assert case_number not in public["prompt"]
    assert decision_date not in public["prompt"]
    assert "【대상법원】" in public["prompt"]
    assert "【대상사건번호】" in public["prompt"]
    assert "【대상판결일】" in public["prompt"]
    assert private["promptSHA256"] == reserve.normalized_prompt_sha256(public["prompt"])
    assert private["identityKeys"]["factsContentSHA256"] == reserve.content_sha256(facts)
    unredacted_prompt = reserve.render_prompt(
        domain="civil",
        claim_clauses=reserve.segment_evidence(claim, prefix="C"),
        facts_clauses=reserve.segment_evidence(facts, prefix="F"),
    )
    assert private["identityKeys"]["promptSHA256"] == reserve.normalized_prompt_sha256(
        unredacted_prompt
    )
    redaction_manifest = built.metadata["targetMetadataRedaction"]
    assert redaction_manifest["specificationSHA256"] == (
        reserve.TARGET_METADATA_REDACTION_SPEC_SHA256
    )
    assert redaction_manifest["postRenderTargetMatchCount"] == 0
    assert private["targetMetadataRedaction"]["postRenderTargetMatchCount"] == 0


def test_sentence_line_segmentation_is_bounded_and_content_roundtrips():
    one_line = (
        "1. 첫 문장입니다. 두 번째 문장입니다! "
        + ("공백없는매우긴토큰" * 90)
        + " 마지막 문장입니다?"
    )
    source = one_line + "\n가. 다음 줄의 독립 사실입니다."
    clauses = reserve.segment_evidence(source, prefix="F")

    assert len(clauses) > 4
    assert [row["id"] for row in clauses] == [
        f"F{index:03d}" for index in range(1, len(clauses) + 1)
    ]
    assert max(len(row["text"]) for row in clauses) <= reserve.MAX_EVIDENCE_CLAUSE_CHARS
    assert reserve.evidence_roundtrip_signature(source) == reserve.evidence_roundtrip_signature(
        " ".join(row["text"] for row in clauses)
    )


def test_target_metadata_redaction_handles_aliases_punctuation_and_date_variants():
    redacted = reserve.redact_target_metadata(
        claim=(
            "서울중앙지방법원 2020 가합-12,345 사건에 관하여 "
            "2020년 6월 1일 기록된 금원을 지급하라."
        ),
        facts=(
            "서울중앙지법의 2020.가합.1.2.3.4.5 기록은 2020. 06. 01. 작성되었다. "
            "같은 자료에는 2020/6/1 표기도 있다."
        ),
        court="서울중앙지법",
        case_number="2020가합12345",
        decision_date="2020-06-01",
    )

    assert "서울중앙지법" not in redacted.facts
    assert "서울중앙지방법원" not in redacted.claim
    assert "2020 가합" not in redacted.claim
    assert "2020.가합" not in redacted.facts
    assert redacted.counts == {
        "claim": {"court": 1, "caseNumber": 1, "decisionDate": 1},
        "facts": {"court": 1, "caseNumber": 1, "decisionDate": 2},
    }
    rendered = reserve.render_prompt(
        domain="civil",
        claim_clauses=reserve.segment_evidence(redacted.claim, prefix="C"),
        facts_clauses=reserve.segment_evidence(redacted.facts, prefix="F"),
    )
    reserve.assert_no_target_metadata(
        rendered,
        court="서울중앙지법",
        case_number="2020가합12345",
        decision_date="2020-06-01",
    )


@pytest.mark.parametrize(
    "court,case_number,decision_date,error_text",
    [
        ("법원", "2020가합123", "2020-06-01", "court locator"),
        ("서울중앙지법", "2020가합ABC", "2020-06-01", "case-number locator"),
        ("서울중앙지법", "2020가합123", "2020-02-31", "calendar date"),
    ],
)
def test_target_metadata_redaction_rejects_unverifiable_locators(
    court, case_number, decision_date, error_text
):
    with pytest.raises(reserve.ReserveBuildError, match=error_text):
        reserve.redact_target_metadata(
            claim="피고는 금원을 지급하라.",
            facts="당사자 사이의 사실관계이다.",
            court=court,
            case_number=case_number,
            decision_date=decision_date,
        )


@pytest.mark.parametrize(
    "bad_private,bad_public,error_text",
    [
        (None, "{not-json}\n", "malformed JSONL row"),
        (None, json.dumps({"id": "old-1"}) + "\n", "missing keys"),
        (
            json.dumps(
                {
                    "caseId": "old-1", "label": "인용됨", "caseRef": "법원|2020가합1",
                    "decisionDate": "2020-01-01", "holding": "기각한다",
                },
                ensure_ascii=False,
            ) + "\n",
            None,
            "missing keys",
        ),
    ],
)
def test_malformed_prior_inputs_fail_closed(tmp_path, bad_private, bad_public, error_text):
    historical = _row("historical", domain="civil", label="인용됨")
    db = tmp_path / "precedents.sqlite3"
    _create_db(db, [historical, *_clean_quota_rows()])
    prior = tmp_path / "prior"
    _make_prior(prior, historical)
    if bad_private is not None:
        (prior / "outcome_old.private.jsonl").write_text(bad_private, encoding="utf-8")
    if bad_public is not None:
        (prior / "outcome_old.public.jsonl").write_text(bad_public, encoding="utf-8")

    with pytest.raises(reserve.ReserveBuildError, match=error_text):
        reserve.build_candidate_inventory(db_path=db, prior_dir=prior, config=_config())


def test_prior_private_id_absent_from_database_fails_closed(tmp_path):
    historical = _row("historical", domain="civil", label="인용됨")
    db = tmp_path / "precedents.sqlite3"
    _create_db(db, [historical, *_clean_quota_rows()])
    prior = tmp_path / "prior"
    _make_prior(prior, historical)
    private_path = prior / "outcome_old.private.jsonl"
    row = json.loads(private_path.read_text(encoding="utf-8"))
    row["canonicalId"] = "missing-canonical"
    _write_jsonl(private_path, [row])

    with pytest.raises(reserve.ReserveBuildError, match="absent from DB"):
        reserve.build_candidate_inventory(db_path=db, prior_dir=prior, config=_config())


def test_holding_leakage_and_claim_pointer_are_rejected(tmp_path):
    historical = _row("historical", domain="civil", label="인용됨")
    pointer_claim = "주문과 같다. " + ("청구 보충 내용 " * 10)
    leaked_facts = _facts("leaked", "civil") + "\n" + _holding("인용됨").splitlines()[0]
    rows = [
        historical,
        _row(
            "claim-pointer", domain="civil", label="인용됨", claim=pointer_claim
        ),
        _row(
            "holding-leak", domain="civil", label="인용됨", facts=leaked_facts
        ),
        *_clean_quota_rows(),
    ]
    db = tmp_path / "precedents.sqlite3"
    _create_db(db, rows)
    prior = tmp_path / "prior"
    _make_prior(prior, historical)

    built = reserve.build_candidate_inventory(db_path=db, prior_dir=prior, config=_config())
    surviving = {row["canonicalId"] for row in built.private_rows}
    assert "claim-pointer" not in surviving
    assert "holding-leak" not in surviving
    assert built.metadata["scanCounts"]["leak.claim_points_to_holding"] == 1
    assert built.metadata["scanCounts"]["leak.holding_text_overlap"] == 1


def test_internal_family_key_uniqueness_uses_gold_independent_rank(tmp_path):
    historical = _row("historical", domain="civil", label="인용됨")
    family_a = _row(
        "family-a", domain="civil", label="인용됨", dedupe_key="shared-family-ab"
    )
    family_b = _row(
        "family-b", domain="civil", label="인용됨",
        dedupe_key="shared-family-ab", text_hash="shared-family-bc",
    )
    family_c = _row(
        "family-c", domain="civil", label="인용됨", text_hash="shared-family-bc"
    )
    rows = [historical, family_a, family_b, family_c, *_clean_quota_rows()]
    db = tmp_path / "precedents.sqlite3"
    _create_db(db, rows)
    prior = tmp_path / "prior"
    _make_prior(prior, historical)

    built = reserve.build_candidate_inventory(db_path=db, prior_dir=prior, config=_config())
    expected = min(
        (family_a, family_b, family_c),
        key=lambda row: hashlib.sha256(
            (
                "synthetic-confirmation|"
                + row["canonical_id"]
                + "|"
                + reserve.normalize_case_ref(
                    f"{row['court']}|{row['case_number']}"
                )
            ).encode("utf-8")
        ).hexdigest(),
    )["canonical_id"]
    all_candidates = {
        row["canonicalId"]
        for row in built.private_rows
    }
    # The lower-ranked family member survives deduplication (it need not be the
    # final quota member when another clean row has an even lower rank).
    assert built.metadata["scanCounts"]["internalExcluded.dedupeKey"] >= 1
    assert built.metadata["scanCounts"]["internalExcluded.textHash"] >= 1
    connection = reserve.open_readonly_database(db)
    try:
        exposure = reserve.resolve_prior_exposure(
            connection, reserve.discover_prior_inputs(prior)
        )
        unique_candidates, _ = reserve._scan_candidates(connection, exposure, _config())
    finally:
        connection.close()
    unique_ids = {row["canonicalId"] for row in unique_candidates}
    assert expected in unique_ids
    assert ({"family-a", "family-b", "family-c"} - {expected}).isdisjoint(unique_ids)
    assert len(all_candidates) == 4


def test_new_lineage_keys_participate_in_internal_family_closure(tmp_path):
    historical = _row("historical", domain="civil", label="인용됨")
    rows = [
        historical,
        _row(
            "number-a", domain="civil", label="인용됨",
            court="서로다른법원A", case_number="2020가합7777",
        ),
        _row(
            "number-b", domain="civil", label="인용됨",
            court="서로다른법원B", case_number="2020 가합 7777",
        ),
        _row(
            "record-a", domain="civil", label="인용됨",
            dataset="record-dataset-a", source_record_id="shared-record-alone",
        ),
        _row(
            "record-b", domain="civil", label="인용됨",
            dataset="record-dataset-b", source_record_id=" SHARED-RECORD-ALONE ",
        ),
        _row(
            "locator-a", domain="civil", label="인용됨",
            dataset="shared-locator-dataset", source_record_id="shared-locator-record",
        ),
        _row(
            "locator-b", domain="civil", label="인용됨",
            dataset=" SHARED-LOCATOR-DATASET ", source_record_id=" SHARED-LOCATOR-RECORD ",
        ),
        _row(
            "path-a", domain="civil", label="인용됨",
            source_path="Archive/Case-42/Judgment.JSON",
        ),
        _row(
            "path-b", domain="civil", label="인용됨",
            source_path=" archive\\case-42\\judgment.json ",
        ),
        *_clean_quota_rows(),
    ]
    db = tmp_path / "precedents.sqlite3"
    _create_db(db, rows)
    prior = tmp_path / "prior"
    _make_prior(prior, historical)

    built = reserve.build_candidate_inventory(db_path=db, prior_dir=prior, config=_config())
    counts = built.metadata["scanCounts"]
    assert counts["internalExcluded.caseNumber"] >= 1
    assert counts["internalExcluded.sourceRecordId"] >= 2
    assert counts["internalExcluded.sourceDatasetRecordId"] >= 1
    assert counts["internalExcluded.sourcePathLocator"] >= 1


def test_infeasible_target_quota_fails_closed(tmp_path):
    historical = _row("historical", domain="civil", label="인용됨")
    db = tmp_path / "precedents.sqlite3"
    _create_db(db, [historical, *_clean_quota_rows()])
    prior = tmp_path / "prior"
    _make_prior(prior, historical)

    with pytest.raises(reserve.ReserveBuildError, match="target quota infeasible"):
        reserve.build_candidate_inventory(
            db_path=db, prior_dir=prior, config=_config(target=2, candidate=2)
        )


def test_candidate_buffer_shortfall_keeps_usable_target_inventory(tmp_path):
    historical = _row("historical", domain="civil", label="인용됨")
    db = tmp_path / "precedents.sqlite3"
    _create_db(db, [historical, *_clean_quota_rows()])
    prior = tmp_path / "prior"
    _make_prior(prior, historical)

    built = reserve.build_candidate_inventory(
        db_path=db, prior_dir=prior, config=_config(target=1, candidate=3)
    )
    assert len(built.public_rows) == 4
    for domain in ("civil", "tax"):
        for label in reserve.CLASSES:
            selection = built.metadata["candidateBufferSelection"][domain][label]
            assert selection == {
                "targetPerLabel": 1,
                "requestedCandidateBuffer": 3,
                "available": 1,
                "selectedCandidateBuffer": 1,
                "candidateBufferShortfall": 2,
            }


def test_extra_public_paths_and_self_hashed_ledger_extend_exposure_closure(tmp_path):
    historical = _row("historical", domain="civil", label="인용됨")
    extra_facts = _facts("accepted-extra", "civil")
    ledger_facts = _facts("accepted-ledger", "civil")
    extra_candidate = _row(
        "accepted-extra", domain="civil", label="인용됨", facts=extra_facts
    )
    ledger_candidate = _row(
        "accepted-ledger", domain="civil", label="인용됨", facts=ledger_facts
    )
    db = tmp_path / "precedents.sqlite3"
    _create_db(
        db,
        [historical, extra_candidate, ledger_candidate, *_clean_quota_rows()],
    )
    prior = tmp_path / "prior"
    _make_prior(prior, historical)

    extra_public = tmp_path / "accepted_model_mount.jsonl"
    _write_jsonl(
        extra_public,
        [
            {
                "id": "accepted-extra-output",
                "prompt": (
                    "accepted model-mounted wrapper\n[기초사실]\n"
                    + extra_facts
                    + "\n[응답 지침]\n답하십시오."
                ),
            }
        ],
    )
    ledger_unsigned = {
        "protocol": "outcome-public-exposure-ledger-v1",
        "hashes": {
            "normalizedPromptSHA256": [],
            "claimContentSHA256": [],
            "factsContentSHA256": [reserve.content_sha256(ledger_facts)],
            "claimFactsContentSHA256": [],
        },
    }
    ledger = dict(ledger_unsigned)
    ledger["selfHash"] = hashlib.sha256(
        reserve.canonical_json_bytes(ledger_unsigned)
    ).hexdigest()
    ledger_path = tmp_path / "exposure-ledger.json"
    ledger_path.write_text(
        json.dumps(ledger, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )

    built = reserve.build_candidate_inventory(
        db_path=db,
        prior_dir=prior,
        config=_config(),
        extra_public_paths=[extra_public],
        exposure_ledger=ledger_path,
    )
    surviving = {row["canonicalId"] for row in built.private_rows}
    assert "accepted-extra" not in surviving
    assert "accepted-ledger" not in surviving
    assert built.metadata["scanCounts"]["priorExcluded.factsContentSHA256"] >= 2
    origins = {row["origin"] for row in built.metadata["priorInputs"]}
    assert {"priorDirectory", "extraPublic", "explicitLedger"} <= origins


def test_outputs_are_separate_self_hashed_verified_and_never_overwritten(tmp_path):
    historical = _row("historical", domain="civil", label="인용됨")
    db = tmp_path / "precedents.sqlite3"
    _create_db(db, [historical, *_clean_quota_rows()])
    prior = tmp_path / "prior"
    _make_prior(prior, historical)
    built = reserve.build_candidate_inventory(db_path=db, prior_dir=prior, config=_config())
    public = tmp_path / "out" / "reserve.public.jsonl"
    private = tmp_path / "out" / "reserve.private.jsonl"
    manifest_path = tmp_path / "out" / "reserve.manifest.json"

    manifest = reserve.write_inventory(
        built, public_out=public, private_out=private, manifest_out=manifest_path
    )
    assert reserve.verify_manifest_self_hash(manifest)
    assert manifest["artifacts"]["public"]["sha256"] == reserve.sha256_file(public)
    assert manifest["artifacts"]["private"]["sha256"] == reserve.sha256_file(private)
    assert len(manifest["orderedCandidates"]) == len(built.public_rows)
    assert "holding" not in public.read_text(encoding="utf-8")
    assert "label" not in public.read_text(encoding="utf-8")
    expected_public_keys = {
        "id", "suite", "benchmarkId", "responseFormat", "language", "prompt"
    }
    assert all(set(row) == expected_public_keys for row in built.public_rows)
    assert all(
        row["benchmarkId"] == "outcome.first_instance_prediction.v1"
        for row in built.public_rows
    )
    for row in built.private_rows:
        identity = row["identityKeys"]
        assert "sourceRecordId" not in identity
        assert "sourceDatasetRecordId" not in identity
        assert "sourcePathLocator" not in identity
        assert len(identity["sourceRecordIdSHA256"]) == 64
        assert len(identity["sourceDatasetRecordIdSHA256"]) == 64
        assert len(identity["sourcePathLocatorSHA256"]) == 64
    tampered = dict(manifest)
    tampered["configuration"] = dict(tampered["configuration"], minDate="2006-01-01")
    assert not reserve.verify_manifest_self_hash(tampered)
    with pytest.raises(reserve.ReserveBuildError, match="refusing to overwrite"):
        reserve.write_inventory(
            built, public_out=public, private_out=private, manifest_out=manifest_path
        )
