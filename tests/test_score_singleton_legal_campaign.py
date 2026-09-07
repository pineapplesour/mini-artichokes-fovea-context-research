from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import run_singleton_legal_campaign as runner
from tools import score_singleton_legal_campaign as scorer


def _write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"".join(scorer.canonical_json_bytes(dict(row)) + b"\n" for row in rows)
    )


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _id(index: int) -> str:
    return f"outcome-confirm-{index:020x}"


def _default_gold() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    index = 0
    for domain in scorer.DOMAINS:
        for label in scorer.LABELS:
            for _ in range(2):
                rows.append({"id": _id(index), "domain": domain, "label": label})
                index += 1
    return rows


def _opposite(label: str) -> str:
    return "기각" if label == "인용됨" else "인용됨"


def _unit(case_id: str, runner_arm: str) -> dict[str, Any]:
    unit_id = f"u-{case_id.removeprefix('outcome-confirm-')}-{runner_arm}-answer"
    return {
        "unitId": unit_id,
        "caseId": case_id,
        "armId": runner_arm,
        "stageId": "answer",
        "dependencies": [],
        "promptPath": f"packets/{unit_id}.txt",
        "promptSha256": scorer.canonical_digest({"prompt": unit_id}),
        "outputSchemaPath": "schemas/answer.json",
        "outputSchemaSha256": scorer.canonical_digest({"schema": "answer"}),
        "producesScientificOutcome": True,
    }


def _resign_score_manifest(bundle: dict[str, Any]) -> None:
    manifest = json.loads(bundle["manifest"].read_text(encoding="utf-8"))
    manifest.pop("selfHash", None)
    manifest["selfHash"] = scorer.canonical_digest(manifest)
    _write_json(bundle["manifest"], manifest)
    bundle["expectedManifestSha256"] = scorer.sha256_file(bundle["manifest"])


def _build_bundle(
    tmp_path: Path,
    *,
    gold: list[dict[str, str]] | None = None,
    outcomes: Mapping[str, list[str | None]] | None = None,
    exact_max: int = 12,
) -> dict[str, Any]:
    root = tmp_path / "campaign"
    root.mkdir()
    campaign_id = "synthetic-singleton-legal-campaign"
    gold_rows = list(gold or _default_gold())
    gold_path = root / "private_gold.jsonl"
    _write_jsonl(gold_path, gold_rows)
    ids = [row["id"] for row in gold_rows]
    labels = [row["label"] for row in gold_rows]

    units: list[dict[str, Any]] = []
    row_by_unit: dict[str, dict[str, Any]] = {}
    for paper_arm, runner_arm in scorer.RUNNER_ARM_BY_PAPER_ARM.items():
        arm_outcomes = (
            list(outcomes[paper_arm])
            if outcomes is not None and paper_arm in outcomes
            else labels
            if paper_arm == scorer.PRIMARY_CANDIDATE
            else [_opposite(label) for label in labels]
        )
        assert len(arm_outcomes) == len(ids)
        for case_id, outcome in zip(ids, arm_outcomes, strict=True):
            unit = _unit(case_id, runner_arm)
            units.append(unit)
            row_by_unit[unit["unitId"]] = {
                "id": case_id,
                "armId": runner_arm,
                "unitId": unit["unitId"],
                "outcome": outcome,
            }

    # Runner output is schedule order, deliberately not case or arm order.
    ordered_unit_ids = sorted(row_by_unit, reverse=True)
    scientific_rows = [row_by_unit[unit_id] for unit_id in ordered_unit_ids]
    runner_root = root / "runner"
    output_root = root / "run"
    unit_manifest_path = runner_root / "unit_manifest.json"
    schedule_path = runner_root / "schedule.json"
    predictions_path = output_root / "scientific_predictions.jsonl"
    campaign_receipt_path = output_root / "campaign_receipt.json"
    unit_manifest = {
        "campaignId": campaign_id,
        "units": units,
        "manifestSha256": scorer.canonical_digest({"campaign": campaign_id, "units": units}),
    }
    schedule = {
        "orderedUnitIds": ordered_unit_ids,
        "scheduleSha256": scorer.canonical_digest(ordered_unit_ids),
    }
    _write_json(unit_manifest_path, unit_manifest)
    _write_json(schedule_path, schedule)
    _write_jsonl(predictions_path, scientific_rows)
    predictions_sha = scorer.sha256_file(predictions_path)
    campaign_receipt: dict[str, Any] = {
        "campaignId": campaign_id,
        "campaignGitCommit": "c" * 40,
        "scientificPredictionsSha256": predictions_sha,
    }
    campaign_receipt["receiptSha256"] = scorer.canonical_digest(campaign_receipt)
    _write_json(campaign_receipt_path, campaign_receipt)
    unit_receipts = [
        {"unitId": unit_id, "receiptSha256": scorer.canonical_digest({"receipt": unit_id})}
        for unit_id in ordered_unit_ids
    ]
    unit_results = [
        {
            "unitId": unit_id,
            "caseId": row_by_unit[unit_id]["id"],
            "armId": row_by_unit[unit_id]["armId"],
            "stageId": "answer",
            "outcome": row_by_unit[unit_id]["outcome"],
        }
        for unit_id in ordered_unit_ids
    ]
    runtime_identity = {
        "identitySha256": scorer.canonical_digest({"runtime": "synthetic"})
    }
    validated = {
        "manifest": unit_manifest,
        "schedule": schedule,
        "campaignReceipt": campaign_receipt,
        "unitReceipts": unit_receipts,
        "unitResults": unit_results,
        "scientificRows": scientific_rows,
        "runtimeIdentity": runtime_identity,
    }
    manifest: dict[str, Any] = {
        "schemaVersion": 1,
        "protocol": scorer.MANIFEST_PROTOCOL,
        "status": "FROZEN_FOR_ONE_TIME_PRIVATE_GOLD_OPEN",
        "campaignId": campaign_id,
        "candidateArm": scorer.PRIMARY_CANDIDATE,
        "comparatorArms": list(scorer.PRIMARY_COMPARATORS),
        "runnerCampaign": {
            "unitManifestPath": unit_manifest_path.relative_to(root).as_posix(),
            "unitManifestFileSha256": scorer.sha256_file(unit_manifest_path),
            "schedulePath": schedule_path.relative_to(root).as_posix(),
            "scheduleFileSha256": scorer.sha256_file(schedule_path),
            "campaignGitCommit": "c" * 40,
            "outputDirectory": output_root.relative_to(root).as_posix(),
            "campaignReceiptFileSha256": scorer.sha256_file(campaign_receipt_path),
            "campaignReceiptSha256": campaign_receipt["receiptSha256"],
            "scientificPredictionsFileSha256": predictions_sha,
        },
        "privateGold": {
            "path": gold_path.relative_to(root).as_posix(),
            "sha256": scorer.sha256_file(gold_path),
            "rows": len(gold_rows),
            "orderedIdsSha256": scorer.canonical_digest(ids),
        },
        "statistics": {
            "alpha": 0.05,
            "confidenceLevel": 0.95,
            "bootstrapSeed": "synthetic-bootstrap-seed-v1",
            "bootstrapReplicates": 99,
            "bootstrapMethod": scorer.BOOTSTRAP_METHOD,
            "permutationSeed": "synthetic-permutation-seed-v1",
            "permutationReplicates": 199,
            "permutationMethod": scorer.PERMUTATION_METHOD,
            "exactPermutationMaxDiscordances": exact_max,
            "holmMethod": scorer.HOLM_METHOD,
        },
        "implementation": {
            "scorerSha256": scorer.sha256_file(Path(scorer.__file__).resolve()),
            "runnerSha256": scorer.sha256_file(Path(runner.__file__).resolve()),
        },
    }
    manifest["selfHash"] = scorer.canonical_digest(manifest)
    manifest_path = root / "score_manifest.json"
    _write_json(manifest_path, manifest)
    calls: list[dict[str, Any]] = []

    def validate(**kwargs: Any) -> Mapping[str, Any]:
        calls.append(kwargs)
        assert kwargs["unit_manifest_path"] == unit_manifest_path.resolve()
        assert kwargs["schedule_path"] == schedule_path.resolve()
        assert kwargs["output_dir"] == output_root.resolve()
        assert kwargs["expected_unit_manifest_file_sha256"] == scorer.sha256_file(
            unit_manifest_path
        )
        assert kwargs["expected_schedule_file_sha256"] == scorer.sha256_file(
            schedule_path
        )
        assert kwargs["expected_campaign_git_commit"] == "c" * 40
        assert "process_factory" not in kwargs
        return validated

    return {
        "root": root,
        "manifest": manifest_path,
        "expectedManifestSha256": scorer.sha256_file(manifest_path),
        "gold": gold_path,
        "predictions": predictions_path,
        "campaignReceipt": campaign_receipt_path,
        "validated": validated,
        "validator": validate,
        "validatorCalls": calls,
    }


def _score(bundle: Mapping[str, Any]) -> dict[str, Any]:
    return scorer.build_report(
        manifest_path=bundle["manifest"],
        expected_manifest_file_sha256=bundle["expectedManifestSha256"],
        runner_validator=bundle["validator"],
        source_anchor_verifier=lambda **_kwargs: {},
        campaign_anchor_verifier=lambda **_kwargs: {},
        runtime_identity_verifier=lambda _config: {},
    )


def test_directly_consumes_combined_runner_campaign_and_fixed_matrix(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)

    report = _score(bundle)

    assert len(bundle["validatorCalls"]) == 1
    assert report["status"] == "SCORED_FULL_DENOMINATOR"
    assert report["goldJoinLocation"] == "this_scorer_only"
    assert report["denominator"]["n"] == 8
    assert report["arms"]["Mini-4"]["macroBalancedAccuracy"] == 1.0
    assert report["bindings"]["runnerCampaign"]["combinedScientificRows"] == 64
    assert report["bindings"]["runnerCampaign"]["validatedSingletonUnits"] == 64
    assert report["bindings"]["runnerCampaign"]["answerStageUnits"] == 64
    assert report["bindings"]["runnerCampaign"]["perArmPredictionAdapterUsed"] is False
    assert report["bindings"]["runnerCampaign"]["runnerArmByPaperArm"] == dict(
        scorer.RUNNER_ARM_BY_PAPER_ARM
    )
    assert report["primaryFixedIntersectionUnionTest"]["passed"] is True
    for comparator in scorer.PRIMARY_COMPARATORS:
        comparison = report["comparisons"][comparator]
        assert comparison["pairedDiscordances"]["rescues"] == 8
        assert comparison["pairedDiscordances"]["harms"] == 0
        assert comparison["secondaryRawExactMcNemar"]["oneSidedPValue"] == 1 / 256
        assert comparison["primaryMbaPermutation"]["oneSidedPValue"] == 1 / 256
    assert report["reportSha256"] == scorer.canonical_digest(
        {key: value for key, value in report.items() if key != "reportSha256"}
    )


def test_runner_safe_arm_ids_have_exact_paper_display_mapping() -> None:
    assert tuple(scorer.RUNNER_ARM_BY_PAPER_ARM) == scorer.ARM_ORDER
    assert scorer.RUNNER_ARM_ORDER == (
        "mini-4",
        "plain-luna-1",
        "structured-direct-1",
        "sc-4",
        "bo3-j",
        "cr-4",
        "task-adapted-icr-4",
        "answer-only-veto-4",
    )
    assert scorer.PAPER_ARM_BY_RUNNER_ARM["bo3-j"] == "Bo3+J"
    assert all(runner.ID_RE.fullmatch(arm) is not None for arm in scorer.RUNNER_ARM_ORDER)


def test_null_and_abstain_are_wrong_and_mba_is_not_raw_accuracy(tmp_path: Path) -> None:
    gold = [
        *(
            {"id": _id(index), "domain": "civil", "label": "인용됨"}
            for index in range(4)
        ),
        {"id": _id(4), "domain": "civil", "label": "기각"},
        {"id": _id(5), "domain": "tax", "label": "인용됨"},
        {"id": _id(6), "domain": "tax", "label": "기각"},
    ]
    candidate = [None, "ABSTAIN", "기각", None, "기각", "인용됨", "기각"]
    bundle = _build_bundle(
        tmp_path,
        gold=gold,
        outcomes={scorer.PRIMARY_CANDIDATE: candidate},
    )

    metrics = _score(bundle)["arms"][scorer.PRIMARY_CANDIDATE]

    assert metrics["nullPredictionsScoredWrong"] == 2
    assert metrics["abstainPredictionsScoredWrong"] == 1
    assert metrics["correct"] == 3
    assert metrics["rawAccuracy"] == 3 / 7
    assert metrics["macroBalancedAccuracy"] == 0.75


def test_unfavorable_frozen_comparator_cannot_be_dropped(tmp_path: Path) -> None:
    gold = _default_gold()
    labels = [row["label"] for row in gold]
    bundle = _build_bundle(
        tmp_path,
        outcomes={
            scorer.PRIMARY_CANDIDATE: labels,
            scorer.PRIMARY_COMPARATORS[-1]: labels,
        },
    )

    report = _score(bundle)

    last = scorer.PRIMARY_COMPARATORS[-1]
    assert report["comparisons"][last]["macroBalancedRiskDifference"] == 0.0
    assert report["primaryFixedIntersectionUnionTest"]["passed"] is False
    manifest = json.loads(bundle["manifest"].read_text(encoding="utf-8"))
    manifest["comparatorArms"].pop()
    manifest.pop("selfHash")
    manifest["selfHash"] = scorer.canonical_digest(manifest)
    _write_json(bundle["manifest"], manifest)
    bundle["expectedManifestSha256"] = scorer.sha256_file(bundle["manifest"])
    with pytest.raises(scorer.CampaignScoreError, match="IUT membership/order"):
        _score(bundle)


def test_combined_prediction_file_tamper_fails_before_runner_validation(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    with bundle["predictions"].open("ab") as stream:
        stream.write(b"\n")

    with pytest.raises(scorer.CampaignScoreError, match="combined prediction file hash"):
        _score(bundle)
    assert bundle["validatorCalls"] == []


def test_missing_case_arm_answer_fails_closed(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    bundle["validated"]["scientificRows"].pop()

    with pytest.raises(scorer.CampaignScoreError, match="scientific row/unit coverage"):
        _score(bundle)


def test_duplicate_case_arm_answer_fails_closed(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    validated = bundle["validated"]
    original_row = validated["scientificRows"][0]
    original_unit = next(
        unit
        for unit in validated["manifest"]["units"]
        if unit["unitId"] == original_row["unitId"]
    )
    duplicate_unit = copy.deepcopy(original_unit)
    duplicate_unit["unitId"] = "attacker-duplicate-answer-unit"
    duplicate_row = dict(original_row)
    duplicate_row["unitId"] = duplicate_unit["unitId"]
    validated["manifest"]["units"].append(duplicate_unit)
    validated["schedule"]["orderedUnitIds"].append(duplicate_unit["unitId"])
    validated["unitReceipts"].append({"unitId": duplicate_unit["unitId"]})
    validated["unitResults"].append({"unitId": duplicate_unit["unitId"]})
    validated["scientificRows"].append(duplicate_row)

    with pytest.raises(scorer.CampaignScoreError, match="duplicate runner answer coordinate"):
        _score(bundle)


def test_non_answer_scientific_stage_fails_closed(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    bundle["validated"]["manifest"]["units"][0]["stageId"] = "revision"

    with pytest.raises(scorer.CampaignScoreError, match="not its exact answer-stage"):
        _score(bundle)


def test_unfrozen_runner_arm_id_fails_closed(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    validated = bundle["validated"]
    unit_id = validated["scientificRows"][0]["unitId"]
    unit = next(row for row in validated["manifest"]["units"] if row["unitId"] == unit_id)
    unit["armId"] = "attacker-arm"
    validated["scientificRows"][0]["armId"] = "attacker-arm"

    with pytest.raises(scorer.CampaignScoreError, match="non-frozen arm"):
        _score(bundle)


def test_missing_runner_unit_receipt_fails_before_gold(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    bundle["validated"]["unitReceipts"].pop()

    with pytest.raises(scorer.CampaignScoreError, match="per-unit validation coverage"):
        _score(bundle)


def test_runner_validation_error_precedes_invalid_private_gold(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    gold_rows = scorer.load_jsonl(bundle["gold"], label="test gold")
    gold_rows[0]["privateConsensusExtra"] = True
    _write_jsonl(bundle["gold"], gold_rows)
    manifest = json.loads(bundle["manifest"].read_text(encoding="utf-8"))
    manifest["privateGold"]["sha256"] = scorer.sha256_file(bundle["gold"])
    manifest.pop("selfHash")
    manifest["selfHash"] = scorer.canonical_digest(manifest)
    _write_json(bundle["manifest"], manifest)
    bundle["expectedManifestSha256"] = scorer.sha256_file(bundle["manifest"])

    def reject(**_kwargs: Any) -> Mapping[str, Any]:
        raise runner.CampaignIntegrityError("synthetic runner receipt rejection")

    bundle["validator"] = reject
    with pytest.raises(scorer.CampaignScoreError, match="runner receipt rejection"):
        _score(bundle)


def test_private_gold_requires_exact_three_field_projection(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    rows = scorer.load_jsonl(bundle["gold"], label="test gold")
    rows[0]["holding"] = "private extra field"
    _write_jsonl(bundle["gold"], rows)
    manifest = json.loads(bundle["manifest"].read_text(encoding="utf-8"))
    manifest["privateGold"]["sha256"] = scorer.sha256_file(bundle["gold"])
    manifest.pop("selfHash")
    manifest["selfHash"] = scorer.canonical_digest(manifest)
    _write_json(bundle["manifest"], manifest)
    bundle["expectedManifestSha256"] = scorer.sha256_file(bundle["manifest"])

    with pytest.raises(scorer.CampaignScoreError, match="privateGold row 0 schema mismatch"):
        _score(bundle)


def test_seeded_monte_carlo_report_is_deterministic(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path, exact_max=0)

    first = _score(bundle)
    second = _score(bundle)

    assert first == second
    for comparator in scorer.PRIMARY_COMPARATORS:
        permutation = first["comparisons"][comparator]["primaryMbaPermutation"]
        assert permutation["mode"] == "seeded_monte_carlo"
        assert permutation["plusOneCorrection"] is True
        assert permutation["evaluations"] == 199


def test_exact_mcnemar_and_holm_calculations() -> None:
    assert scorer.one_sided_exact_mcnemar(2, 0) == 0.25
    assert scorer.one_sided_exact_mcnemar(1, 1) == 0.75
    assert scorer.one_sided_exact_mcnemar(0, 0) == 1.0
    adjusted = scorer.holm_adjust({"a": 0.01, "b": 0.03, "c": 0.20}, 0.05)
    assert adjusted["a"]["adjustedPValue"] == 0.03
    assert adjusted["b"]["adjustedPValue"] == 0.06
    assert adjusted["c"]["adjustedPValue"] == 0.20
    assert adjusted["a"]["rejectAtAlpha"] is True
    assert adjusted["b"]["rejectAtAlpha"] is False


def test_output_is_self_hashed_and_never_overwritten(tmp_path: Path) -> None:
    bundle = _build_bundle(tmp_path)
    report = _score(bundle)
    output = tmp_path / "private_score_report.json"

    scorer.write_report(output, report)
    assert scorer.load_json_object(output, label="test report") == report
    with pytest.raises(scorer.CampaignScoreError, match="refusing to overwrite"):
        scorer.write_report(output, report)
