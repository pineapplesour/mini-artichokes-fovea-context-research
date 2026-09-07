from __future__ import annotations

import copy
import io
import json
import subprocess
from pathlib import Path

import pytest

from tools import compare_outcome_gold_audits as compare
from tools import build_disjoint_outcome_reserve as reserve_builder
from tools import finalize_outcome_gold_audit as finalize
from tools import outcome_gold_audit as audit
from tools import run_outcome_gold_auditor as runner


REAL_VERIFY_GIT_ANCHOR = runner.verify_git_anchor


CELL_PATTERN = (
    [("civil", "인용됨"), ("civil", "기각"), ("tax", "인용됨"), ("tax", "기각")]
    * 3
    + [("civil", "인용됨"), ("civil", "기각")] * 2
)


def test_direct_cli_resolves_repository_tools_package() -> None:
    completed = subprocess.run(
        ["python", str(Path(audit.__file__).resolve()), "--help"],
        cwd=audit.REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Prepare sealed A/B outcome-gold audit shards" in completed.stdout


def _identity_keys(
    index: int,
    prompt_hash: str,
    source_prompt_hash: str,
    *,
    canonical_id: str,
    case_ref: str,
) -> dict[str, str]:
    value = audit.sha256_bytes(f"identity-{index}".encode())
    result = {name: value for name in audit.IDENTITY_KEY_NAMES}
    result["promptSHA256"] = prompt_hash
    result["sourcePromptSHA256"] = source_prompt_hash
    result["canonicalId"] = canonical_id
    result["caseRef"] = case_ref
    return result


def make_source(
    tmp_path: Path, *, rows: int = 30
) -> tuple[Path, Path, Path, list[dict]]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    public_rows: list[dict] = []
    private_rows: list[dict] = []
    seed_salt = "synthetic-gold-audit-seed-v1"
    for index in range(rows):
        domain, label = CELL_PATTERN[index % len(CELL_PATTERN)]
        case_id = f"opaque-{index:04d}"
        facts = f"당사자 사이의 공개 사실관계 {index}가 존재한다."
        claim = f"원고는 피고에게 합성 채무 {index}의 이행을 청구한다." if domain == "civil" else ""
        case_number = f"2026가단{index + 1}"
        case_ref = f"서울중앙지방법원|{case_number}"
        canonical_id = f"canonical-{index}"
        decision_date = "2026-01-01"
        redacted = reserve_builder.redact_target_metadata(
            claim=claim,
            facts=facts,
            court="서울중앙지방법원",
            case_number=case_number,
            decision_date=decision_date,
        )
        claim_clauses = (
            reserve_builder.segment_evidence(redacted.claim, prefix="C")
            if domain == "civil"
            else []
        )
        facts_clauses = reserve_builder.segment_evidence(redacted.facts, prefix="F")
        prompt = reserve_builder.render_prompt(
            domain=domain,
            claim_clauses=claim_clauses,
            facts_clauses=facts_clauses,
        )
        prompt_hash = audit.normalized_prompt_sha256(prompt)
        source_prompt_hash = audit.normalized_prompt_sha256(
            reserve_builder.render_source_prompt(domain=domain, claim=claim, facts=facts)
        )
        holding = (
            f"1. 피고는 원고에게 합성 채무 {index}의 전부를 지급하라."
            if label == "인용됨"
            else f"1. 원고의 이 사건 합성 청구 {index}를 모두 기각한다."
        )
        normalized_case_ref = reserve_builder.normalize_case_ref(case_ref)
        selection_rank = audit.sha256_bytes(
            f"{seed_salt}|{canonical_id}|{normalized_case_ref}".encode("utf-8")
        )
        identity = _identity_keys(
            index,
            prompt_hash,
            source_prompt_hash,
            canonical_id=canonical_id,
            case_ref=normalized_case_ref,
        )
        identity.update(
            {
                "caseNumber": reserve_builder.normalize_identity_component(case_number),
                "claimContentSHA256": (
                    reserve_builder.content_sha256(claim) if claim else ""
                ),
                "factsContentSHA256": reserve_builder.content_sha256(facts),
                "claimFactsContentSHA256": reserve_builder.content_sha256(
                    f"{claim}\n{facts}" if claim else facts
                ),
            }
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
                "domain": domain,
                "label": label,
                "caseRef": case_ref,
                "canonicalId": canonical_id,
                "decisionDate": decision_date,
                "sourceDataset": "synthetic-unit-test",
                "holding": holding,
                "sourceFields": {"claim": claim, "facts": facts},
                "evidenceClauses": {"claim": claim_clauses, "facts": facts_clauses},
                "selectionRankSHA256": selection_rank,
                "promptSHA256": prompt_hash,
                "sourcePromptSHA256": source_prompt_hash,
                "identityKeys": identity,
                "targetMetadataRedaction": {
                    "version": "paired-target-metadata-redaction-v1",
                    "specificationSHA256": "__filled_below__",
                    "replacementCounts": redacted.counts,
                    "postRenderTargetMatchCount": 0,
                },
            }
        )
    redaction_specification = {
        "version": "paired-target-metadata-redaction-v1",
        "scope": "paired target court, case number, and decision date in public claim/facts only",
        "goldIndependent": "uses only court, case_number, and decision_date source metadata",
        "unicodeNormalization": "NFKC",
        "courtMatching": "synthetic exact court matching rule",
        "caseNumberMatching": "synthetic exact case-number matching rule",
        "decisionDateMatching": "synthetic exact decision-date matching rule",
        "placeholders": {
            "court": "【대상법원】",
            "caseNumber": "【대상사건번호】",
            "decisionDate": "【대상판결일】",
        },
        "postcondition": "zero target-specific matches after public prompt rendering",
        "unredactedClosure": "prior/internal hashes retain original synthetic text",
    }
    redaction_specification_hash = audit.canonical_digest(redaction_specification)
    for row in private_rows:
        row["targetMetadataRedaction"]["specificationSHA256"] = (
            redaction_specification_hash
        )
    public_path = tmp_path / "candidate.public.jsonl"
    private_path = tmp_path / "candidate.private.jsonl"
    public_payload = audit.serialize_jsonl(public_rows)
    private_payload = audit.serialize_jsonl(private_rows)
    public_path.write_bytes(public_payload)
    private_path.write_bytes(private_payload)
    ordered = [
        {
            "id": public["id"],
            "promptSHA256": private["promptSHA256"],
            "publicRowSHA256": audit.canonical_digest(public),
            "privateRowSHA256": audit.canonical_digest(private),
        }
        for public, private in zip(public_rows, private_rows, strict=True)
    ]
    manifest = {
        "protocol": audit.SOURCE_PROTOCOL,
        "configuration": {
            "seedSalt": seed_salt,
            "quotas": {
                "civil": {"targetPerLabel": 1, "candidatePerLabel": max(1, rows)},
                "tax": {"targetPerLabel": 1, "candidatePerLabel": max(1, rows)},
            }
        },
        "candidateBufferSelection": {
            domain: {
                label: {
                    "targetPerLabel": 1,
                    "requestedCandidateBuffer": max(1, rows),
                    "available": sum(
                        row["domain"] == domain and row["label"] == label
                        for row in private_rows
                    ),
                    "selectedCandidateBuffer": sum(
                        row["domain"] == domain and row["label"] == label
                        for row in private_rows
                    ),
                    "candidateBufferShortfall": max(1, rows)
                    - sum(
                        row["domain"] == domain and row["label"] == label
                        for row in private_rows
                    ),
                }
                for label in audit.PROVISIONAL_LABELS
            }
            for domain in ("civil", "tax")
        },
        "artifacts": {
            "public": {
                "path": str(public_path.resolve()),
                "rows": rows,
                "bytes": len(public_payload),
                "sha256": audit.sha256_bytes(public_payload),
            },
            "private": {
                "path": str(private_path.resolve()),
                "rows": rows,
                "bytes": len(private_payload),
                "sha256": audit.sha256_bytes(private_payload),
            },
        },
        "orderedCandidates": ordered,
        "targetMetadataRedaction": {
            "version": "paired-target-metadata-redaction-v1",
            "specification": redaction_specification,
            "specificationSHA256": redaction_specification_hash,
            "perRowMetadataLocation": "private JSONL targetMetadataRedaction",
            "selectedRowCount": rows,
            "rowsWithAtLeastOneReplacement": 0,
            "rowsWithNoReplacement": rows,
            "replacementCounts": {
                "all": 0,
                "claim.court": 0,
                "claim.caseNumber": 0,
                "claim.decisionDate": 0,
                "facts.court": 0,
                "facts.caseNumber": 0,
                "facts.decisionDate": 0,
                "locator.court": 0,
                "locator.caseNumber": 0,
                "locator.decisionDate": 0,
            },
            "postRenderTargetMatchCount": 0,
        },
    }
    manifest["selfHash"] = audit.source_manifest_self_hash(manifest)
    manifest_path = tmp_path / "candidate.manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return public_path, private_path, manifest_path, private_rows


def prepare(tmp_path: Path, *, rows: int = 30, shard_size: int = 40):
    public_path, private_path, manifest_path, private_rows = make_source(
        tmp_path / "source", rows=rows
    )
    campaign = tmp_path / "campaign"
    result = audit.prepare_campaign(
        private_path=private_path,
        manifest_path=manifest_path,
        campaign_dir=campaign,
        auditor_a_model="gpt-5.6-sol",
        auditor_b_model="gpt-5.6-terra",
        auditor_c_model="gpt-5.6-sol",
        shard_size=shard_size,
        timeout_seconds=audit.DEFAULT_TIMEOUT_SECONDS,
        codex_home=audit.DEFAULT_CODEX_HOME,
        order_seed="test-order-seed",
        c_sample_seed="test-c-sample-seed",
    )
    return campaign, public_path, private_path, manifest_path, private_rows, result


def mock_git_anchor(
    *,
    campaign_dir: Path,
    profile: str,
    shard_index: int,
    freeze: dict,
    commit: str,
) -> dict:
    _, anchor_path = audit.verify_anchor_binds_shard(
        campaign_dir=campaign_dir,
        profile=profile,
        shard_index=shard_index,
        freeze=freeze,
    )
    anchor = audit.load_json(anchor_path)
    return {
        "commit": commit,
        "anchorPath": anchor_path.name,
        "anchorFileSha256": audit.sha256_file(anchor_path),
        "anchorSha256": anchor["anchorSha256"],
        "implementationFilesVerified": len(freeze["implementationHashes"]),
    }


@pytest.fixture(autouse=True)
def _mock_external_git_anchor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "verify_git_anchor", mock_git_anchor)


def valid_judgment(packet: dict, label: str) -> dict:
    return {
        "id": packet["id"],
        "eligible": True,
        "label": label,
        "exactHoldingQuote": packet["holding"],
        "flags": [],
        "rationale": "주문의 완전한 결론 문장을 직접 확인했다.",
    }


def ineligible_judgment(packet: dict) -> dict:
    return {
        "id": packet["id"],
        "eligible": False,
        "label": "AMBIGUOUS",
        "exactHoldingQuote": packet["holding"],
        "flags": ["unclear"],
        "rationale": "주문만으로 대상 청구의 결론을 안전하게 확정할 수 없다.",
    }


def accept_profile(
    campaign: Path,
    profile: str,
    labels: dict[str, str],
    *,
    ineligible_ids: set[str] | None = None,
) -> None:
    profile = profile.upper()
    ineligible_ids = ineligible_ids or set()
    profile_freeze = audit.load_profile_freeze(campaign, profile)
    for shard_record in profile_freeze["shards"]:
        index = shard_record["index"]
        freeze, paths, packets, _ = audit.verify_shard_bundle(campaign, profile, index)
        judgments = [
            (
                ineligible_judgment(packet)
                if packet["id"] in ineligible_ids
                else valid_judgment(packet, labels[packet["id"]])
            )
            for packet in packets
        ]
        response = {"judgments": judgments}
        audit.write_json_exclusive(paths["modelResponse"], response)
        response_text = audit.canonical_json_bytes(response).decode("utf-8")
        audit.write_jsonl_exclusive(
            paths["trace"],
            [
                {
                    "type": "thread.started",
                    "thread_id": f"mock-{profile}-{index}",
                },
                {
                    "type": "item.completed",
                    "item": {
                        "id": "item_diag",
                        "type": "error",
                        "message": runner.EXPECTED_CODE_MODE_DISABLED_DIAGNOSTIC,
                    },
                },
                {"type": "turn.started"},
                {
                    "type": "item.completed",
                    "item": {
                        "id": "item_0",
                        "type": "agent_message",
                        "text": response_text,
                    },
                },
                {
                    "type": "turn.completed",
                    "usage": {
                        "input_tokens": 80 + index,
                        "cached_input_tokens": 0,
                        "cache_write_input_tokens": 0,
                        "output_tokens": 20,
                        "reasoning_output_tokens": 5,
                    },
                },
            ],
        )
        audit.write_bytes_exclusive(paths["stderr"], b"")
        git_anchor = mock_git_anchor(
            campaign_dir=campaign,
            profile=profile,
            shard_index=index,
            freeze=freeze,
            commit="mock-anchor-commit",
        )
        attempt_start = runner.write_attempt_start(
            paths=paths, freeze=freeze, git_anchor=git_anchor
        )
        validation = runner.validate_output(paths, packets, write_derived=True)
        policy = runner.audit_tool_free_trace(
            trace_path=paths["trace"],
            questions_path=paths["packet"],
            model_response_path=paths["modelResponse"],
            return_code=0,
        )
        assert validation["passed"]
        assert policy["passed"]
        audit.write_json_exclusive(paths["validation"], validation)
        runner.append_attempt_finish(
            paths=paths,
            freeze=freeze,
            status="accepted",
            trace_sha256=audit.sha256_file(paths["trace"]),
            model_response_sha256=audit.sha256_file(paths["modelResponse"]),
        )
        receipt = {
            "schemaVersion": 1,
            "status": "accepted",
            "protocol": audit.SHARD_PROTOCOL,
            "semanticModelInvocations": 1,
            "profile": profile,
            "shardIndex": index,
            "freezeSha256": freeze["freezeSha256"],
            "inputFileSha256": runner.input_hashes(paths),
            "executionConfig": freeze["executionConfig"],
            "implementationHashes": freeze["implementationHashes"],
            "codexCli": freeze["codexCli"],
            "preCallGitAnchor": git_anchor,
            "outerContainmentProbe": {
                "passed": True,
                "authMountedInCliNamespace": True,
                "authUnmountedClaim": False,
                "enumeratedModelToolSurfacesConfiguredDisabled": True,
                "modelToolSchemaAdvertisementIndependentlyAttested": False,
                "zeroToolEventsObservedInAcceptedRawTrace": True,
            },
            "attemptStart": attempt_start,
            "process": {"exitCode": 0, "timedOut": False, "elapsedSeconds": 1.25},
            "tokenUsage": runner._trace_token_usage(policy),
            "policyAudit": policy,
            "artifactValidation": validation,
            "artifacts": {
                "judgmentsSha256": audit.sha256_file(paths["judgments"]),
                "modelResponseSha256": audit.sha256_file(paths["modelResponse"]),
                "rawTraceSha256": audit.sha256_file(paths["trace"]),
                "stderrSha256": audit.sha256_file(paths["stderr"]),
                "validationSha256": audit.sha256_file(paths["validation"]),
                "attemptRegistrySha256": audit.sha256_file(paths["attemptRegistry"]),
                "threadIds": policy["threadIds"],
            },
            "acceptedArtifact": "output/model_response.json",
            "derivedArtifact": "output/judgments.jsonl",
        }
        receipt["receiptSha256"] = audit.receipt_digest(receipt)
        audit.write_json_exclusive(paths["receipt"], receipt)


def test_prepare_is_exactly_bound_tool_free_and_non_overwriting(tmp_path: Path) -> None:
    campaign, public_path, private_path, manifest_path, private_rows, result = prepare(
        tmp_path
    )
    assert result["semanticModelInvocations"] == 0
    assert result["preCallAnchorFile"] == "precall_anchor_ab.json"
    source = audit.load_source_freeze(campaign)
    assert source["shardSize"] == 40
    assert source["minimumABKappa"] == 0.90
    assert source["executionProfiles"]["A"]["codexHome"] == str(
        audit.DEFAULT_CODEX_HOME.resolve()
    )
    assert source["executionProfiles"]["A"]["localCode"] is False
    assert source["executionProfiles"]["A"]["shellTool"] is False
    assert source["executionProfiles"]["A"]["strictConfig"] is True
    assert source["codexCliBaseIdentity"]["version"] == audit.REQUIRED_CODEX_VERSION
    assert source["codexCliBaseIdentity"]["featureSnapshotSha256"] == (
        audit.canonical_digest(source["codexCliBaseIdentity"]["featureSnapshot"])
    )
    assert "unified_exec" in source["executionProfiles"]["A"]["disabledFeatures"]
    assert source["selectionSizeRule"]["civil"]["minimumPerAuditedLabel"] == 140
    anchor_text = (campaign / "precall_anchor_ab.json").read_text(encoding="utf-8")
    assert private_rows[0]["holding"] not in anchor_text

    orders: dict[str, list[str]] = {}
    for profile in ("A", "B"):
        observed: list[str] = []
        profile_freeze = audit.load_profile_freeze(campaign, profile)
        for shard in profile_freeze["shards"]:
            freeze, _, packet, ids = audit.verify_shard_bundle(
                campaign, profile, shard["index"]
            )
            assert all(set(row) == {"id", "holding"} for row in packet)
            assert freeze["outputSchemaCanonicalSha256"] == audit.canonical_digest(
                audit.output_schema()
            )
            command = audit.tool_free_codex_command(
                input_dir=audit.shard_paths(campaign, profile, shard["index"])["inputDir"],
                output_dir=audit.shard_paths(campaign, profile, shard["index"])["outputDir"],
                codex_home=audit.DEFAULT_CODEX_HOME,
                model=freeze["executionConfig"]["model"],
                reasoning_effort="high",
                verbosity="low",
            )
            assert "--strict-config" in command
            assert "features.shell_tool=false" in command
            assert "features.unified_exec=false" in command
            assert "features.code_mode=false" in command
            assert "features.code_mode_host=false" in command
            observed.extend(ids)
        orders[profile] = observed
    assert set(orders["A"]) == set(orders["B"])
    assert orders["A"] != orders["B"]

    with pytest.raises(audit.GoldAuditError, match="overwrite existing campaign"):
        audit.prepare_campaign(
            private_path=private_path,
            manifest_path=manifest_path,
            campaign_dir=campaign,
            auditor_a_model="gpt-5.6-sol",
            auditor_b_model="gpt-5.6-terra",
            auditor_c_model="gpt-5.6-sol",
            shard_size=40,
            timeout_seconds=audit.DEFAULT_TIMEOUT_SECONDS,
            codex_home=audit.DEFAULT_CODEX_HOME,
            order_seed="test-order-seed",
            c_sample_seed="test-c-sample-seed",
        )
    assert public_path.is_file()


def test_public_extra_gold_field_rejected_even_after_manifest_resigning(tmp_path: Path) -> None:
    public_path, private_path, manifest_path, _ = make_source(tmp_path / "source", rows=4)
    public_rows = audit.load_jsonl(public_path)
    public_rows[0]["label"] = "인용됨"
    payload = audit.serialize_jsonl(public_rows)
    public_path.write_bytes(payload)
    manifest = audit.load_json(manifest_path)
    manifest["artifacts"]["public"].update(
        bytes=len(payload), sha256=audit.sha256_bytes(payload)
    )
    manifest["orderedCandidates"][0]["publicRowSHA256"] = audit.canonical_digest(
        public_rows[0]
    )
    manifest["selfHash"] = audit.source_manifest_self_hash(manifest)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(audit.GoldAuditError, match="public reserve exact schema"):
        audit.prepare_campaign(
            private_path=private_path,
            manifest_path=manifest_path,
            campaign_dir=tmp_path / "campaign",
            auditor_a_model="gpt-5.6-sol",
            auditor_b_model="gpt-5.6-terra",
            auditor_c_model="gpt-5.6-sol",
            shard_size=40,
            timeout_seconds=audit.DEFAULT_TIMEOUT_SECONDS,
            codex_home=audit.DEFAULT_CODEX_HOME,
            order_seed="o",
            c_sample_seed="c",
        )


def test_full_anchor_reconstruction_rejects_other_shard_resigning(tmp_path: Path) -> None:
    campaign, *_ = prepare(tmp_path, rows=48, shard_size=40)
    anchor_path = campaign / "precall_anchor_ab.json"
    anchor = audit.load_json(anchor_path)
    anchor["profiles"][1]["shards"][0]["rows"] += 1
    anchor["anchorSha256"] = audit.self_hash(anchor, key="anchorSha256")
    anchor_path.write_text(
        json.dumps(anchor, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    freeze, _, _, _ = audit.verify_shard_bundle(campaign, "A", 0)
    with pytest.raises(audit.GoldAuditError, match="full live campaign stage"):
        audit.verify_anchor_binds_shard(
            campaign_dir=campaign,
            profile="A",
            shard_index=0,
            freeze=freeze,
        )


def test_source_semantic_and_selection_rank_resigning_are_rejected(tmp_path: Path) -> None:
    _, private_path, manifest_path, _ = make_source(tmp_path / "source", rows=4)
    private_rows = audit.load_jsonl(private_path)
    private_rows[0]["evidenceClauses"]["facts"][0]["text"] = "서로 다른 합성 사실"
    private_rows[1]["selectionRankSHA256"] = "f" * 64
    private_payload = audit.serialize_jsonl(private_rows)
    private_path.write_bytes(private_payload)
    manifest = audit.load_json(manifest_path)
    manifest["artifacts"]["private"].update(
        bytes=len(private_payload), sha256=audit.sha256_bytes(private_payload)
    )
    for index, row in enumerate(private_rows):
        manifest["orderedCandidates"][index]["privateRowSHA256"] = (
            audit.canonical_digest(row)
        )
    manifest["selfHash"] = audit.source_manifest_self_hash(manifest)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(
        audit.GoldAuditError,
        match="evidenceClauses/sourceFields|selectionRankSHA256 recomputation",
    ):
        audit.validate_source_inventory(
            private_path=private_path, manifest_path=manifest_path
        )

    _, rank_private, rank_manifest_path, _ = make_source(
        tmp_path / "rank-source", rows=4
    )
    rank_rows = audit.load_jsonl(rank_private)
    rank_rows[0]["selectionRankSHA256"] = "f" * 64
    rank_payload = audit.serialize_jsonl(rank_rows)
    rank_private.write_bytes(rank_payload)
    rank_manifest = audit.load_json(rank_manifest_path)
    rank_manifest["artifacts"]["private"].update(
        bytes=len(rank_payload), sha256=audit.sha256_bytes(rank_payload)
    )
    rank_manifest["orderedCandidates"][0]["privateRowSHA256"] = (
        audit.canonical_digest(rank_rows[0])
    )
    rank_manifest["selfHash"] = audit.source_manifest_self_hash(rank_manifest)
    rank_manifest_path.write_text(
        json.dumps(rank_manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(audit.GoldAuditError, match="selectionRankSHA256 recomputation"):
        audit.validate_source_inventory(
            private_path=rank_private, manifest_path=rank_manifest_path
        )

    _, quota_private, quota_manifest_path, _ = make_source(
        tmp_path / "quota-source", rows=4
    )
    quota_manifest = audit.load_json(quota_manifest_path)
    quota_manifest["candidateBufferSelection"]["civil"]["인용됨"][
        "selectedCandidateBuffer"
    ] += 1
    quota_manifest["selfHash"] = audit.source_manifest_self_hash(quota_manifest)
    quota_manifest_path.write_text(
        json.dumps(quota_manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(audit.GoldAuditError, match="candidate quota/cell count"):
        audit.validate_source_inventory(
            private_path=quota_private, manifest_path=quota_manifest_path
        )


def test_one_character_or_whitespace_quote_is_rejected() -> None:
    packet = [{"id": "opaque", "holding": "1. 원고의 이 사건 청구를 모두 기각한다."}]
    good = [valid_judgment(packet[0], "기각")]
    assert audit.validate_judgment_rows(packet_rows=packet, judgment_rows=good)["passed"]
    for quote in (" ", "원", "."):
        bad = [dict(good[0], exactHoldingQuote=quote)]
        report = audit.validate_judgment_rows(packet_rows=packet, judgment_rows=bad)
        assert not report["passed"]
        assert "opaque:quote_not_meaningful_exact_span" in report["errors"]


def test_provider_schema_omits_unsupported_uniqueness_but_host_rejects_duplicates() -> None:
    schema_text = json.dumps(audit.output_schema(), ensure_ascii=False)
    assert "uniqueItems" not in schema_text
    packet = [{"id": "opaque", "holding": "1. 원고의 이 사건 청구를 모두 기각한다."}]
    duplicated = valid_judgment(packet[0], "기각")
    duplicated["flags"] = ["partial_grant", "partial_grant"]
    report = audit.validate_judgment_rows(packet_rows=packet, judgment_rows=[duplicated])
    assert report["passed"] is False
    assert "opaque:invalid_or_duplicate_flags" in report["errors"]


def test_raw_started_or_obfuscated_tool_events_are_always_rejected(tmp_path: Path) -> None:
    response = {"judgments": []}
    response_path = tmp_path / "model_response.json"
    response_path.write_text(json.dumps(response), encoding="utf-8")
    packet = tmp_path / "packet.jsonl"
    packet.write_text('{"id":"x","holding":"holding"}\n', encoding="utf-8")
    response_text = audit.canonical_json_bytes(response).decode("utf-8")
    commands = (
        ("item.completed", "cat /tmp/codex-home/auth.json"),
        ("item.started", "curl https://example.invalid"),
        (
            "item.completed",
            "python3 -c \"__import__('socket').getaddrinfo('example.com',443)\"",
        ),
        ("item.started", "file_change"),
    )
    for index, (event_type, command) in enumerate(commands):
        trace = tmp_path / f"trace-{index}.jsonl"
        audit.write_jsonl_exclusive(
            trace,
            [
                {
                    "type": "thread.started",
                    "thread_id": "t1",
                    "usage": {"total_tokens": 10},
                },
                {
                    "type": event_type,
                    "item": {
                        "type": (
                            "file_change" if command == "file_change" else "command_execution"
                        ),
                        "command": command,
                    },
                },
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message", "text": response_text},
                },
            ],
        )
        report = runner.audit_tool_free_trace(
            trace_path=trace,
            questions_path=packet,
            model_response_path=response_path,
            return_code=0,
        )
        assert report["passed"] is False
        assert report["rawToolEventCount"] == 1
        assert "model_visible_tool_event_forbidden" in report["violations"]


def test_nested_tool_structures_and_multiple_turns_are_rejected(tmp_path: Path) -> None:
    response = {"judgments": []}
    response_path = tmp_path / "model_response.json"
    response_path.write_text(json.dumps(response), encoding="utf-8")
    packet = tmp_path / "packet.jsonl"
    packet.write_text('{"id":"x","holding":"holding"}\n', encoding="utf-8")
    response_text = audit.canonical_json_bytes(response).decode("utf-8")
    usage = {
        "input_tokens": 10,
        "cached_input_tokens": 0,
        "cache_write_input_tokens": 0,
        "output_tokens": 5,
        "reasoning_output_tokens": 1,
    }
    hidden_trace = tmp_path / "nested.jsonl"
    audit.write_jsonl_exclusive(
        hidden_trace,
        [
            {"type": "thread.started", "thread_id": "t1"},
            {"type": "turn.started"},
            {
                "type": "item.completed",
                "item": {
                    "id": "item_0",
                    "type": "agent_message",
                    "text": response_text,
                    "metadata": {"tool_calls": [{"name": "read_file"}]},
                },
            },
            {"type": "turn.completed", "usage": usage},
        ],
    )
    hidden_report = runner.audit_tool_free_trace(
        trace_path=hidden_trace,
        questions_path=packet,
        model_response_path=response_path,
        return_code=0,
    )
    assert hidden_report["passed"] is False
    assert hidden_report["hiddenToolStructureCount"] >= 1
    assert "nested_or_obfuscated_tool_structure_forbidden" in hidden_report["violations"]

    two_turn_trace = tmp_path / "two-turns.jsonl"
    audit.write_jsonl_exclusive(
        two_turn_trace,
        [
            {"type": "thread.started", "thread_id": "t1"},
            {"type": "turn.started"},
            {"type": "turn.completed", "usage": usage},
            {"type": "turn.started"},
            {
                "type": "item.completed",
                "item": {"id": "item_0", "type": "agent_message", "text": response_text},
            },
            {"type": "turn.completed", "usage": usage},
        ],
    )
    two_turn_report = runner.audit_tool_free_trace(
        trace_path=two_turn_trace,
        questions_path=packet,
        model_response_path=response_path,
        return_code=0,
    )
    assert two_turn_report["passed"] is False
    assert two_turn_report["turnStartedCount"] == 2
    assert two_turn_report["turnCompletedCount"] == 2
    assert "exactly_one_turn_started_required" in two_turn_report["violations"]
    assert "exactly_one_turn_completed_required" in two_turn_report["violations"]


def test_mock_thread_only_trace_is_rejected(tmp_path: Path) -> None:
    response_path = tmp_path / "model_response.json"
    response_path.write_text('{"judgments":[]}', encoding="utf-8")
    packet = tmp_path / "packet.jsonl"
    packet.write_text('{"id":"x","holding":"holding"}\n', encoding="utf-8")
    trace = tmp_path / "trace.jsonl"
    audit.write_jsonl_exclusive(
        trace,
        [{"type": "thread.started", "thread_id": "mock", "usage": {"total_tokens": 10}}],
    )
    report = runner.audit_tool_free_trace(
        trace_path=trace,
        questions_path=packet,
        model_response_path=response_path,
        return_code=0,
    )
    assert report["passed"] is False
    assert "exactly_one_completed_agent_message_required" in report["violations"]


def test_self_resigned_output_edit_fails_trace_response_binding(tmp_path: Path) -> None:
    campaign, _, _, _, private_rows, _ = prepare(tmp_path, rows=4, shard_size=4)
    case_id = private_rows[0]["caseId"]
    original = private_rows[0]["label"]
    labels = {row["caseId"]: row["label"] for row in private_rows}
    accept_profile(campaign, "A", labels)
    loaded, _, _ = audit.load_accepted_profile(campaign, "A")
    assert loaded[case_id]["label"] == original

    freeze, paths, packets, _ = audit.verify_shard_bundle(campaign, "A", 0)
    response = audit.load_json(paths["modelResponse"])
    response["judgments"][0]["label"] = "기각" if original == "인용됨" else "인용됨"
    paths["modelResponse"].write_text(
        json.dumps(response, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    paths["judgments"].write_bytes(audit.serialize_jsonl(response["judgments"]))
    validation = runner.validate_output(paths, packets, write_derived=False)
    assert validation["passed"]
    paths["validation"].write_text(
        json.dumps(validation, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    attempts = audit.load_jsonl(paths["attemptRegistry"])
    attempts[1]["modelResponseSha256"] = audit.sha256_file(paths["modelResponse"])
    paths["attemptRegistry"].write_bytes(audit.serialize_jsonl(attempts))
    receipt = audit.load_json(paths["receipt"])
    receipt["artifactValidation"] = validation
    receipt["artifacts"]["modelResponseSha256"] = audit.sha256_file(paths["modelResponse"])
    receipt["artifacts"]["judgmentsSha256"] = audit.sha256_file(paths["judgments"])
    receipt["artifacts"]["validationSha256"] = audit.sha256_file(paths["validation"])
    receipt["artifacts"]["attemptRegistrySha256"] = audit.sha256_file(
        paths["attemptRegistry"]
    )
    receipt["receiptSha256"] = audit.receipt_digest(receipt)
    paths["receipt"].write_text(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(audit.GoldAuditError, match="replayed trace policy rejected"):
        audit.load_accepted_profile(campaign, "A")


def test_wrong_codex_home_and_posthoc_kappa_override_are_rejected(tmp_path: Path) -> None:
    public, private, manifest, _ = make_source(tmp_path / "wrong-home", rows=4)
    assert public.is_file()
    with pytest.raises(audit.GoldAuditError, match="exact CODEX_HOME"):
        audit.prepare_campaign(
            private_path=private,
            manifest_path=manifest,
            campaign_dir=tmp_path / "wrong-home-campaign",
            auditor_a_model="gpt-5.6-sol",
            auditor_b_model="gpt-5.6-terra",
            auditor_c_model="gpt-5.6-sol",
            shard_size=40,
            timeout_seconds=audit.DEFAULT_TIMEOUT_SECONDS,
            codex_home=tmp_path / "other-codex-home",
            order_seed="o",
            c_sample_seed="c",
        )
    campaign, _, private, manifest, _, _ = prepare(tmp_path / "kappa", rows=4)
    with pytest.raises(audit.GoldAuditError, match="runtime kappa override is forbidden"):
        finalize.finalize(
            campaign_dir=campaign,
            private_path=private,
            manifest_path=manifest,
            kappa_threshold=0.0,
        )


def test_source_freeze_cannot_self_sign_weaker_reliability_or_size_gates(
    tmp_path: Path,
) -> None:
    campaign, _, _, _, _, _ = prepare(tmp_path, rows=4, shard_size=4)
    source_path = campaign / "source_freeze.json"
    original = audit.load_json(source_path)
    mutations = (
        lambda value: value.update(minimumABKappa=0.0),
        lambda value: value.update(
            bootstrap={**value["bootstrap"], "replicates": 1}
        ),
        lambda value: value["selectionSizeRule"]["civil"].update(
            minimumPerAuditedLabel=1
        ),
        lambda value: value.update(cAgreementAuditFraction=0.0),
    )
    for mutate in mutations:
        changed = copy.deepcopy(original)
        mutate(changed)
        changed["freezeSha256"] = audit.self_hash(changed, key="freezeSha256")
        source_path.write_text(
            json.dumps(changed, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        with pytest.raises(audit.GoldAuditError, match="canonical"):
            audit.load_source_freeze(campaign)
    source_path.write_text(
        json.dumps(original, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    assert audit.load_source_freeze(campaign) == original


def test_real_git_anchor_requires_exact_committed_live_bytes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    anchor_path = repo / "campaign/precall_anchor_ab.json"
    anchor_path.parent.mkdir()
    anchor_path.write_text('{"anchor":"exact"}\n', encoding="utf-8")
    implementation = repo / "implementation.py"
    implementation.write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=pineapplesour",
            "-c",
            "user.email=59020461+pineapplesour@users.noreply.github.com",
            "commit",
            "-q",
            "-m",
            "fixture anchor",
        ],
        check=True,
    )
    commit = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    freeze = {
        "implementationHashes": {
            str(implementation.resolve()): audit.sha256_file(implementation)
        }
    }
    anchor = {"anchorSha256": "a" * 64}
    monkeypatch.setattr(runner, "REPO_ROOT", repo)
    monkeypatch.setattr(
        audit,
        "verify_anchor_binds_shard",
        lambda **_kwargs: (anchor, anchor_path),
    )
    evidence = REAL_VERIFY_GIT_ANCHOR(
        campaign_dir=anchor_path.parent,
        profile="A",
        shard_index=0,
        freeze=freeze,
        commit=commit,
    )
    assert evidence["commit"] == commit
    assert evidence["implementationFilesVerified"] == 1
    anchor_path.write_text('{"anchor":"changed"}\n', encoding="utf-8")
    with pytest.raises(audit.GoldAuditError, match="exact live pre-call anchor"):
        REAL_VERIFY_GIT_ANCHOR(
            campaign_dir=anchor_path.parent,
            profile="A",
            shard_index=0,
            freeze=freeze,
            commit=commit,
        )


def test_parser_correction_is_kept_then_deterministically_restratified(
    tmp_path: Path,
) -> None:
    campaign, _, private_path, manifest_path, private_rows, _ = prepare(
        tmp_path, rows=480, shard_size=40
    )
    provisional = {row["caseId"]: row["label"] for row in private_rows}
    audited = dict(provisional)
    corrected_id = private_rows[0]["caseId"]
    audited[corrected_id] = "기각" if audited[corrected_id] == "인용됨" else "인용됨"
    accept_profile(campaign, "A", audited)
    accept_profile(campaign, "B", audited)
    comparison = compare.compare_and_prepare_c(campaign_dir=campaign)
    assert comparison["cohenKappa"] == 1.0
    selection = audit.load_jsonl(campaign / "comparison/c_selection.jsonl")
    accept_profile(campaign, "C", {row["id"]: audited[row["id"]] for row in selection})

    report = finalize.finalize(
        campaign_dir=campaign,
        private_path=private_path,
        manifest_path=manifest_path,
    )
    assert report["status"] == "accepted"
    assert report["selectedPerAuditedLabel"] == {"civil": 149, "tax": 90}
    assert report["acceptedCandidateRows"] == 478
    assert report["parserAgreementFullInventory"]["mismatches"] == 1
    consensus = {
        row["id"]: row
        for row in audit.load_jsonl(campaign / "final/private_consensus.jsonl")
    }
    assert consensus[corrected_id]["parserMatch"] is False
    assert consensus[corrected_id]["candidateAccepted"] is True
    assert consensus[corrected_id]["label"] == audited[corrected_id]
    assert report["domainAgreement"]["civil"]["cohenKappa"] == 1.0
    cell_audit = report["cAgreementAuditDomainByAuditedLabel"]
    assert sum(
        cell_audit[domain][label]["sampledRows"]
        for domain in ("civil", "tax")
        for label in audit.LABELS
    ) == report["cAgreementAuditRows"]
    assert all(
        cell_audit[domain][label]["errorRows"] == 0
        for domain in ("civil", "tax")
        for label in audit.LABELS
    )


def test_runner_is_tool_free_one_attempt_and_resume_never_calls_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    campaign, _, _, _, private_rows, _ = prepare(tmp_path, rows=4, shard_size=4)
    freeze, paths, packets, _ = audit.verify_shard_bundle(campaign, "A", 0)
    monkeypatch.setattr(
        runner.plain_runner,
        "isolation_probe",
        lambda **_kwargs: {"passed": True, "mocked": True},
    )
    monkeypatch.setattr(
        runner.trusted,
        "codex_cli_identity",
        lambda _command: freeze["codexCli"],
    )
    calls = {"popen": 0}

    class FakeProcess:
        pid = 999999

        def __init__(self, *_args, **kwargs):
            calls["popen"] += 1
            self.stdin = io.StringIO()
            labels = {row["caseId"]: row["label"] for row in private_rows}
            response = {
                "judgments": [
                    valid_judgment(packet, labels[packet["id"]]) for packet in packets
                ]
            }
            response_text = audit.canonical_json_bytes(response).decode("utf-8")
            kwargs["stdout"].write(
                json.dumps(
                    {
                        "type": "thread.started",
                        "thread_id": "mock-thread",
                    }
                )
                + "\n"
            )
            kwargs["stdout"].write(
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "id": "item_diag",
                            "type": "error",
                            "message": runner.EXPECTED_CODE_MODE_DISABLED_DIAGNOSTIC,
                        },
                    }
                )
                + "\n"
            )
            kwargs["stdout"].write(json.dumps({"type": "turn.started"}) + "\n")
            kwargs["stdout"].write(
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "id": "item_0",
                            "type": "agent_message",
                            "text": response_text,
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            kwargs["stdout"].write(
                json.dumps(
                    {
                        "type": "turn.completed",
                        "usage": {
                            "input_tokens": 300,
                            "cached_input_tokens": 0,
                            "cache_write_input_tokens": 0,
                            "output_tokens": 21,
                            "reasoning_output_tokens": 7,
                        },
                    }
                )
                + "\n"
            )
            paths["modelResponse"].write_text(response_text, encoding="utf-8")

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(runner.subprocess, "Popen", FakeProcess)
    accepted = runner.run_shard(
        campaign_dir=campaign,
        profile="A",
        shard_index=0,
        codex_home=audit.DEFAULT_CODEX_HOME,
        model="gpt-5.6-sol",
        reasoning_effort="high",
        verbosity="low",
        service_tier="default",
        timeout_seconds=audit.DEFAULT_TIMEOUT_SECONDS,
        pre_call_anchor_commit="mock-anchor-commit",
        resume=False,
    )
    assert accepted["status"] == "accepted"
    assert accepted["policyAudit"]["rawToolEventCount"] == 0
    assert accepted["outerContainmentProbe"]["authMountedInCliNamespace"] is True
    assert (
        accepted["outerContainmentProbe"][
            "modelToolSchemaAdvertisementIndependentlyAttested"
        ]
        is False
    )
    assert calls["popen"] == 1

    resumed = runner.run_shard(
        campaign_dir=campaign,
        profile="A",
        shard_index=0,
        codex_home=audit.DEFAULT_CODEX_HOME,
        model="gpt-5.6-sol",
        reasoning_effort="high",
        verbosity="low",
        service_tier="default",
        timeout_seconds=audit.DEFAULT_TIMEOUT_SECONDS,
        pre_call_anchor_commit="mock-anchor-commit",
        resume=True,
    )
    assert resumed["status"] == "resumed_complete_without_model_call"
    assert calls["popen"] == 1

    with pytest.raises(audit.GoldAuditError, match="runtime execution config"):
        runner.run_shard(
            campaign_dir=campaign,
            profile="B",
            shard_index=0,
            codex_home=audit.DEFAULT_CODEX_HOME,
            model="gpt-5.6-sol",
            reasoning_effort="high",
            verbosity="low",
            service_tier="default",
            timeout_seconds=audit.DEFAULT_TIMEOUT_SECONDS,
            pre_call_anchor_commit="mock-anchor-commit",
            resume=False,
        )
