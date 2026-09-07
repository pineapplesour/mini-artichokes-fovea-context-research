import json
from pathlib import Path

import pytest

from tools import build_disjoint_outcome_reserve as reserve
from tools import build_numbered_outcome_development_set as dev


def _write_source(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _source_row(case_id: str = "old-dev-1") -> dict:
    prompt = reserve.PROMPT_TEMPLATE.format(
        claim="피고는 원고에게 대여금 100원을 지급하라.",
        facts=(
            "1. 원고는 피고에게 100원을 송금하였다. "
            "2. 피고는 변제기가 지났으나 이를 반환하지 않았다."
        ),
    )
    return {"id": case_id, "prompt": prompt, "legacyField": "ignored wrapper"}


def test_build_is_gold_free_deterministic_and_content_preserving(tmp_path):
    source = tmp_path / "source.public.jsonl"
    _write_source(source, [_source_row()])

    first_rows, first_meta = dev.build_rows(source)
    second_rows, second_meta = dev.build_rows(source)

    assert first_rows == second_rows
    assert first_meta == second_meta
    assert first_meta["goldAccess"] is False
    assert set(first_rows[0]) == dev.PUBLIC_KEYS
    assert "[C001]" in first_rows[0]["prompt"]
    assert "[F001]" in first_rows[0]["prompt"]
    assert reserve.public_content_fingerprints(first_rows[0]["prompt"]) == (
        reserve.public_content_fingerprints(_source_row()["prompt"])
    )


def test_nested_claim_headings_are_retained_not_mistaken_for_empty_block(tmp_path):
    source = tmp_path / "nested.public.jsonl"
    row = _source_row("nested")
    row["prompt"] = row["prompt"].replace(
        "[청구취지]\n",
        "[청구취지]\n[주위적 청구취지]\n",
    )
    _write_source(source, [row])

    rows, _ = dev.build_rows(source)

    assert "주위적 청구취지" in rows[0]["prompt"]
    assert "[C001]" in rows[0]["prompt"]


def test_rejects_duplicate_ids_and_missing_civil_content(tmp_path):
    duplicate = tmp_path / "duplicate.jsonl"
    _write_source(duplicate, [_source_row(), _source_row()])
    with pytest.raises(dev.DevelopmentBuildError, match="duplicate"):
        dev.build_rows(duplicate)

    missing = tmp_path / "missing.jsonl"
    _write_source(missing, [{"id": "x", "prompt": "[기초사실]\n사실만 있음"}])
    with pytest.raises(dev.DevelopmentBuildError, match="requires civil claim and facts"):
        dev.build_rows(missing)


def test_exclusive_write_and_self_hash(tmp_path):
    source = tmp_path / "source.jsonl"
    _write_source(source, [_source_row()])
    rows, metadata = dev.build_rows(source)
    public = tmp_path / "numbered.public.jsonl"
    manifest = tmp_path / "numbered.manifest.json"

    written = dev.write_build(rows, metadata, public_out=public, manifest_out=manifest)

    assert reserve.sha256_file(public) == written["artifact"]["sha256"]
    assert reserve.verify_manifest_self_hash(json.loads(manifest.read_text(encoding="utf-8")))
    with pytest.raises(dev.DevelopmentBuildError, match="overwrite"):
        dev.write_build(rows, metadata, public_out=public, manifest_out=tmp_path / "other.json")
