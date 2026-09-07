from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path

import pytest

from tools import audit_public_outcome_reserve as audit
from tools.build_disjoint_outcome_reserve import render_prompt, segment_evidence


def _public_row(case_id: str, *, claim: str, facts: str, domain: str = "civil") -> dict:
    claim_clauses = segment_evidence(claim, prefix="C") if domain == "civil" else []
    facts_clauses = segment_evidence(facts, prefix="F")
    return {
        "id": case_id,
        "suite": "exam",
        "benchmarkId": "outcome.first_instance_prediction.v1",
        "responseFormat": "outcome_prediction",
        "language": "ko",
        "prompt": render_prompt(
            domain=domain, claim_clauses=claim_clauses, facts_clauses=facts_clauses
        ),
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_bound_inputs(
    tmp_path: Path, public_rows: list[dict], private_rows: list[dict]
) -> tuple[Path, Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    public = tmp_path / "bound.public.jsonl"
    private = tmp_path / "bound.private.jsonl"
    manifest = tmp_path / "bound.manifest.json"
    _write_jsonl(public, public_rows)
    _write_jsonl(private, private_rows)
    builder = audit.REPO_ROOT / "tools" / "build_disjoint_outcome_reserve.py"
    extractor = audit.REPO_ROOT / "tools" / "build_outcome_prediction_benchmark.py"
    receipt = {
        "protocol": "source-disjoint-outcome-candidate-inventory-v1",
        "implementation": {
            "builderSHA256": audit.sha256_file(builder),
            "upstreamExtractorSHA256": audit.sha256_file(extractor),
        },
        "artifacts": {
            "public": {
                "sha256": audit.sha256_file(public),
                "bytes": public.stat().st_size,
                "rows": len(public_rows),
            },
            "private": {
                "sha256": audit.sha256_file(private),
                "bytes": private.stat().st_size,
                "rows": len(private_rows),
            },
        },
        "scanCounts": {},
    }
    receipt["selfHash"] = audit.self_hash(receipt)
    manifest.write_bytes(audit.canonical_json_bytes(receipt) + b"\n")
    return public, private, manifest


def _private_structure(public_row: dict, *, case_ref: str, decision_date: str) -> dict:
    return {
        "caseId": public_row["id"],
        "domain": "civil",
        "caseRef": case_ref,
        "decisionDate": decision_date,
        "canonicalId": "private-canonical-target-abc",
        "sourceDataset": "private-source-dataset-xyz",
        "promptSHA256": hashlib.sha256(
            audit.normalize_text(public_row["prompt"]).encode("utf-8")
        ).hexdigest(),
        "identityKeys": {},
        "label": "VALUE_MUST_NOT_BE_ACCESSED",
        "holding": {"value": "VALUE_MUST_NOT_BE_ACCESSED"},
    }


def test_clean_public_rows_pass_without_touching_companion_private_file(tmp_path):
    public = tmp_path / "reserve.public.jsonl"
    private = tmp_path / "reserve.private.jsonl"
    private.write_text('{"label":"DO_NOT_READ"}\n', encoding="utf-8")
    rows = [
        _public_row(
            "outcome-confirm-00000000000000000001",
            claim="피고는 원고에게 약정금과 지연손해금을 지급하라.",
            facts="원고와 피고는 계약을 체결하였다. 원고는 의무를 이행하였고 피고는 대금을 지급하지 않았다.",
        ),
        _public_row(
            "outcome-confirm-00000000000000000002",
            claim="피고는 목적물을 인도하라.",
            facts="당사자들은 별개의 매매계약을 체결하였다. 목적물은 특정되었고 인도기한이 지났으나 아직 인도되지 않았다.",
        ),
    ]
    _write_jsonl(public, rows)

    report, details = audit.audit_public_inventory(public)

    assert report["publicOnlyScreen"]["pass"] is True
    assert report["gate"]["pass"] is False
    assert report["publicContract"]["parsedPromptCount"] == 2
    assert report["leakAudit"]["rowsWithAnyFinding"] == 0
    assert details["containsGoldOrLabels"] is False
    assert audit.verify_self_hash(report)
    assert audit.verify_self_hash(details)
    assert private.read_text(encoding="utf-8") == '{"label":"DO_NOT_READ"}\n'


def test_exact_schema_constants_and_opaque_ids_are_fail_closed(tmp_path):
    public = tmp_path / "bad.public.jsonl"
    row = _public_row(
        "not-opaque",
        claim="피고는 금원을 지급하라.",
        facts="당사자는 계약을 맺었다. 채무가 남아 있다.",
    )
    row["language"] = "en"
    row["unexpected"] = True
    _write_jsonl(public, [row])

    report, details = audit.audit_public_inventory(public)

    findings = report["publicContract"]["findingsByType"]
    assert findings["nonexact_public_schema"] == 1
    assert findings["invalid_opaque_id"] == 1
    assert findings["constant_mismatch.language"] == 1
    assert report["publicOnlyScreen"] == {
        "pass": False,
        "reasons": ["public_contract_violation"],
    }
    assert details["findingCount"] == 1


def test_template_stripped_leak_detectors_do_not_count_fixed_answer_instructions(tmp_path):
    public = tmp_path / "leaked.public.jsonl"
    clean = _public_row(
        "outcome-confirm-00000000000000000003",
        claim="피고는 원고에게 손해를 배상하라.",
        facts="피고의 행위로 손해가 발생했고 당사자 사이에 책임 범위가 다투어졌다.",
    )
    leaked = _public_row(
        "outcome-confirm-00000000000000000004",
        claim="주문 제1항과 같이 피고는 원고에게 금원을 지급하라.",
        facts=(
            "서울지방법원 2019가합12345 사건은 2019. 3. 4. 선고되었다. "
            "원고의 청구를 기각하였다. 출처는 https://example.invalid/record 이다."
        ),
    )
    _write_jsonl(public, [clean, leaked])

    report, details = audit.audit_public_inventory(public)

    assert report["leakAudit"]["rowsWithAnyFinding"] == 1
    categories = report["leakAudit"]["rowsByCategory"]
    assert categories == {
        "case_number": 1,
        "date": 1,
        "holding_or_result": 1,
        "source_locator": 1,
    }
    detail = next(item for item in details["findings"] if item["id"].endswith("04"))
    assert "holding_pointer" in detail["leakDetectors"]
    assert "korean_case_number" in detail["leakDetectors"]
    assert "calendar_date" in detail["leakDetectors"]
    assert "url_or_filesystem_path" in detail["leakDetectors"]


def test_slight_paraphrase_is_joined_by_exact_jaccard_and_unrelated_case_is_not(tmp_path):
    public = tmp_path / "duplicates.public.jsonl"
    suffixes = [chr(97 + first) + chr(97 + second) for first in range(6) for second in range(6)]
    common_sentences = [
        f"당사자들은 물품 공급 약정을 체결하고 원고가 품목{suffix} 물품을 순서대로 인도하였다"
        for suffix in suffixes
    ]
    base_facts = ". ".join(common_sentences) + ". 피고는 약정 대금 전부를 아직 지급하지 않았다."
    paraphrase = base_facts.replace("순서대로 인도하였다", "차례로 인도하였다", 2)
    unrelated = (
        "임차인은 건물을 사용하던 중 누수가 발생하자 수선을 요청하였다. " * 30
    )
    rows = [
        _public_row(
            "outcome-confirm-00000000000000000005",
            claim="피고는 미지급 물품대금을 지급하라.",
            facts=base_facts,
        ),
        _public_row(
            "outcome-confirm-00000000000000000006",
            claim="피고는 지급하지 않은 공급대금을 지급하라.",
            facts=paraphrase,
        ),
        _public_row(
            "outcome-confirm-00000000000000000007",
            claim="피고는 수선비를 지급하라.",
            facts=unrelated,
        ),
    ]
    _write_jsonl(public, rows)

    report, details = audit.audit_public_inventory(public)

    near = report["nearDuplicateAudit"]
    assert near["qualifyingPairCount"] == 1
    assert near["familyCount"] == 1
    assert near["implicatedRowCount"] == 2
    assert near["maximumQualifyingJaccard"] >= 0.86
    assert details["nearDuplicateFamilies"][0]["memberIds"] == [
        "outcome-confirm-00000000000000000005",
        "outcome-confirm-00000000000000000006",
    ]


def test_outputs_are_self_hashed_mode_0600_and_never_overwritten(tmp_path):
    public = tmp_path / "reserve.public.jsonl"
    _write_jsonl(
        public,
        [
            _public_row(
                "outcome-confirm-00000000000000000008",
                claim="피고는 계약금을 반환하라.",
                facts="계약은 합의로 종료되었고 정산할 계약금이 남아 있다.",
            )
        ],
    )
    report, details = audit.audit_public_inventory(public)
    report_path = tmp_path / "audit.report.json"
    details_path = tmp_path / "audit.implicated_ids.private.json"

    audit.write_audit_outputs(
        report,
        details,
        report_path=report_path,
        implicated_ids_path=details_path,
    )

    loaded_report = json.loads(report_path.read_text(encoding="utf-8"))
    loaded_details = json.loads(details_path.read_text(encoding="utf-8"))
    assert audit.verify_self_hash(loaded_report)
    assert audit.verify_self_hash(loaded_details)
    assert loaded_report["implicatedIdsArtifact"]["sha256"] == audit.sha256_file(
        details_path
    )
    assert os.stat(report_path).st_mode & 0o777 == 0o600
    assert os.stat(details_path).st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        audit.write_audit_outputs(
            report,
            details,
            report_path=report_path,
            implicated_ids_path=details_path,
        )


def test_refuses_private_or_gold_named_input(tmp_path):
    path = tmp_path / "reserve.private.jsonl"
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(audit.PublicAuditError, match="private/gold"):
        audit.audit_public_inventory(path)


def test_bound_gate_ignores_generic_dates_but_rejects_paired_target_metadata(tmp_path):
    clean = _public_row(
        "outcome-confirm-00000000000000000009",
        claim="피고는 원고에게 대금을 지급하라.",
        facts="당사자들은 2015. 1. 1. 계약을 체결했고 약정 의무를 이행하였다.",
    )
    clean_private = _private_structure(
        clean, case_ref="서울지법|2020가합12345", decision_date="2020-12-31"
    )
    public, private, manifest = _write_bound_inputs(
        tmp_path / "clean", [clean], [clean_private]
    )
    clean_report, _ = audit.audit_bound_inventory(public, private, manifest)
    assert clean_report["leakAudit"]["rowsByCategory"]["date"] == 1
    assert clean_report["leakAudit"]["affectsFinalGate"] is False
    assert clean_report["constructionConclusionLeakageAudit"]["pass"] is True
    assert clean_report["targetSpecificMetadataAudit"]["pass"] is True
    assert clean_report["gate"] == {"pass": True, "reasons": []}

    leaked = _public_row(
        "outcome-confirm-00000000000000000010",
        claim="피고는 원고에게 대금을 지급하라.",
        facts="서울지방법원 2020가합12345 사건은 2020. 12. 31. 기록이 정리되었다.",
    )
    leaked_private = _private_structure(
        leaked, case_ref="서울지법|2020가합12345", decision_date="2020-12-31"
    )
    public, private, manifest = _write_bound_inputs(
        tmp_path / "leaked", [leaked], [leaked_private]
    )
    leaked_report, details = audit.audit_bound_inventory(public, private, manifest)
    target = leaked_report["targetSpecificMetadataAudit"]
    assert target["bindingErrorCount"] == 0
    assert target["rowsWithTargetMetadata"] == 1
    assert target["rowsByDetector"] == {
        "target_case_number": 1,
        "target_court": 1,
        "target_decision_date": 1,
    }
    assert leaked_report["gate"]["pass"] is False
    assert details["targetSpecificMetadata"]["detectorIds"]


def test_module_never_accesses_private_label_or_holding_fields():
    tree = ast.parse(Path(audit.__file__).read_text(encoding="utf-8"))
    forbidden_accesses: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            if node.slice.value in {"label", "holding"}:
                forbidden_accesses.append((str(node.slice.value), node.lineno))
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value in {"label", "holding"}
        ):
            forbidden_accesses.append((str(node.args[0].value), node.lineno))
    assert forbidden_accesses == []
