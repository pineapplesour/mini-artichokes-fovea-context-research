from __future__ import annotations

import json
from pathlib import Path

from tools.prepare_blind_pairwise_veto import (
    EXPECTED_CONFLICT_ROWS,
    EXPECTED_QUESTION_ROWS,
    prepare,
)
from tools.prepare_plain_codex_file_benchmark import canonical_digest, sha256_file
from tools.validate_blind_pairwise_veto import validate_blind_pairwise_veto


SEED = "blind-pairwise-veto-test-seed-20260831"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def source_campaign(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    solver = source / "solver"
    questions = [
        {
            "id": f"q{index:04d}",
            "suite": "exam",
            "benchmarkId": "synthetic.test",
            "responseFormat": "mcq",
            "language": "en",
            "prompt": (
                f"Question {index}: select the correct answer.\n"
                f"A. alpha-{index}\nB. beta-{index}\nC. gamma-{index}"
            ),
        }
        for index in range(EXPECTED_QUESTION_ROWS)
    ]
    ids = [row["id"] for row in questions]
    questions_path = solver / "input/questions.jsonl"
    write_jsonl(questions_path, questions)
    write_json(solver / "input/expected_ids.json", {"count": len(ids), "ids": ids})

    answers = {"base": [], "auxiliary_1": [], "auxiliary_2": []}
    overlap: list[dict] = []
    eligible_ids: list[str] = []
    for index, question in enumerate(questions):
        case_id = question["id"]
        eligible = index < EXPECTED_CONFLICT_ROWS
        base = f"alpha-{index}"
        alternative = f"beta-{index}" if eligible else base
        answers["base"].append({"id": case_id, "finalAnswer": base})
        answers["auxiliary_1"].append({"id": case_id, "finalAnswer": alternative})
        answers["auxiliary_2"].append({"id": case_id, "finalAnswer": alternative})
        overlap.append({"id": case_id, "eligible": eligible})
        if eligible:
            eligible_ids.append(case_id)

    candidate_hashes: dict[str, str] = {}
    for name, rows in answers.items():
        path = solver / f"input/candidates/{name}.jsonl"
        write_jsonl(path, rows)
        candidate_hashes[name] = sha256_file(path)
    overlap_path = solver / "input/overlap_manifest.jsonl"
    write_jsonl(overlap_path, overlap)
    freeze = {
        "schemaVersion": 1,
        "status": "prepared_no_model_calls",
        "protocol": "mini_artichokes_candidate_overlap_adjudication_v2",
        "questionsSha256": sha256_file(questions_path),
        "overlapManifestSha256": sha256_file(overlap_path),
        "expectedIdsSha256": canonical_digest(ids),
        "eligibleIdsSha256": canonical_digest(eligible_ids),
        "candidateAnswersSha256": candidate_hashes,
    }
    freeze["freezeSha256"] = canonical_digest(freeze)
    write_json(solver / "freeze.json", freeze)
    return source


def prepare_campaign(tmp_path: Path, name: str = "campaign") -> Path:
    source = source_campaign(tmp_path)
    campaign = tmp_path / name
    prepare(
        source_campaign=source,
        campaign_dir=campaign,
        rotation_seed=SEED,
        model="gpt-5.6-luna",
        reasoning_effort="high",
        verbosity="low",
    )
    return campaign


def assessment(answer: str, status: str) -> dict:
    if status == "SUPPORTED":
        test_outcome = "SURVIVED"
        countercase_outcome = "DEFEATED"
    elif status == "REFUTED":
        test_outcome = "FAILED"
        countercase_outcome = "STANDS"
    else:
        test_outcome = "INCONCLUSIVE"
        countercase_outcome = "UNRESOLVED"
    evidence = (
        {"type": "PROMPT_QUOTE", "receipt": {"quote": answer}}
        if status != "UNRESOLVED"
        else {"type": "NONE", "receipt": None}
    )
    return {
        "candidateAnswer": answer,
        "atomicClaim": f"The candidate selects {answer}.",
        "falsificationTest": "Compare the candidate with the supplied prompt evidence.",
        "testOutcome": test_outcome,
        "status": status,
        "strongestCountercase": "The competing candidate could fit the requested polarity.",
        "countercaseOutcome": countercase_outcome,
        "evidence": evidence,
    }


def valid_certificates(campaign: Path) -> list[dict]:
    pairs = load_jsonl(campaign / "veto/input/candidate_pairs.jsonl")
    certificates = []
    for index, pair in enumerate(pairs):
        certificates.append(
            {
                "id": pair["id"],
                "targetPolarity": "SELECT_CORRECT",
                "polarityQuote": f"Question {index}: select the correct answer.",
                "leftAssessment": assessment(pair["leftAnswer"], "SUPPORTED"),
                "rightAssessment": assessment(pair["rightAnswer"], "REFUTED"),
                "uniqueness": "LEFT_ONLY",
                "preference": "PREFER_LEFT",
                "comparativeReason": "LEFT survives the symmetric tests while RIGHT does not.",
            }
        )
    return certificates


def test_prepare_hides_roles_and_freezes_deterministic_rotation(tmp_path: Path) -> None:
    campaign = prepare_campaign(tmp_path)
    veto = campaign / "veto"
    pairs = load_jsonl(veto / "input/candidate_pairs.jsonl")
    questions = load_jsonl(veto / "input/questions.jsonl")
    mapping = load_jsonl(campaign / "control/role_mapping.jsonl")
    freeze = json.loads((veto / "freeze.json").read_text(encoding="utf-8"))

    assert len(questions) == EXPECTED_QUESTION_ROWS
    assert len(pairs) == len(mapping) == EXPECTED_CONFLICT_ROWS
    assert set(questions[0]) == {"id", "responseFormat", "language", "prompt"}
    assert all(set(row) == {"id", "leftAnswer", "rightAnswer"} for row in pairs)
    assert all(row["leftAnswer"] != row["rightAnswer"] for row in pairs)
    assert freeze["inventory"]["leftIncumbentRows"] > 0
    assert freeze["inventory"]["rightIncumbentRows"] > 0
    assert freeze["inventory"]["leftIncumbentRows"] + freeze["inventory"]["rightIncumbentRows"] == 247
    assert freeze["executionConfig"]["nativeWebSearch"] is False
    assert freeze["freezeSha256"] == canonical_digest(
        {key: value for key, value in freeze.items() if key != "freezeSha256"}
    )
    repo_root = Path(__file__).resolve().parents[1]
    expected_implementation_paths = {
        str((repo_root / relative).resolve())
        for relative in (
            "tools/prepare_blind_pairwise_veto.py",
            "tools/validate_blind_pairwise_veto.py",
            "tools/run_blind_pairwise_veto_agent.py",
            "tools/run_ensemble_file_agent.py",
        )
    }
    assert set(freeze["implementationHashes"]) == expected_implementation_paths
    assert freeze["implementationHashes"] == {
        path: sha256_file(Path(path)) for path in freeze["implementationHashes"]
    }
    model_input = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((veto / "input").iterdir())
        if path.is_file()
    ).casefold()
    for hidden_term in ("incumbent", "proposed", "auxiliary", "consensus", "validator1"):
        assert hidden_term not in model_input
    assert "seed" not in model_input
    assert "public_source" not in model_input
    assert "https://" not in model_input
    assert not (veto / "input/role_mapping.jsonl").exists()

    second = tmp_path / "campaign-second"
    prepare(
        source_campaign=tmp_path / "source",
        campaign_dir=second,
        rotation_seed=SEED,
        model="gpt-5.6-luna",
        reasoning_effort="high",
        verbosity="low",
    )
    assert (veto / "input/candidate_pairs.jsonl").read_bytes() == (
        second / "veto/input/candidate_pairs.jsonl"
    ).read_bytes()
    assert (campaign / "control/role_mapping.jsonl").read_bytes() == (
        second / "control/role_mapping.jsonl"
    ).read_bytes()


def test_validator_accepts_complete_consistent_certificates(tmp_path: Path) -> None:
    campaign = prepare_campaign(tmp_path)
    certificates = valid_certificates(campaign)
    write_jsonl(campaign / "veto/output/certificates.jsonl", certificates)

    report = validate_blind_pairwise_veto(campaign)

    assert report["passed"] is True
    assert report["status"] == "accepted"
    assert report["certificateRows"] == EXPECTED_CONFLICT_ROWS
    assert report["preferenceCounts"] == {"PREFER_LEFT": EXPECTED_CONFLICT_ROWS}
    assert report["evidenceTypeCounts"] == {"PROMPT_QUOTE": EXPECTED_CONFLICT_ROWS * 2}
    assert report["modelKnowledgeReceiptsExternallyVerified"] is False


def test_validator_accepts_exact_model_knowledge_receipts(tmp_path: Path) -> None:
    campaign = prepare_campaign(tmp_path)
    certificates = valid_certificates(campaign)
    for side in ("leftAssessment", "rightAssessment"):
        certificates[0][side]["evidence"] = {
            "type": "MODEL_KNOWLEDGE",
            "receipt": {
                "supportedClaim": certificates[0][side]["atomicClaim"],
                "falsificationBasis": "The competing option would have to satisfy the stated selection rule.",
            },
        }
    write_jsonl(campaign / "veto/output/certificates.jsonl", certificates)

    report = validate_blind_pairwise_veto(campaign, write_report=False)

    assert report["passed"] is True
    assert report["evidenceTypeCounts"] == {
        "MODEL_KNOWLEDGE": 2,
        "PROMPT_QUOTE": EXPECTED_CONFLICT_ROWS * 2 - 2,
    }


def test_validator_rejects_web_enabled_freeze_even_with_recomputed_self_hash(tmp_path: Path) -> None:
    campaign = prepare_campaign(tmp_path)
    write_jsonl(campaign / "veto/output/certificates.jsonl", valid_certificates(campaign))
    freeze_path = campaign / "veto/freeze.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    freeze["executionConfig"]["nativeWebSearch"] = True
    freeze["freezeSha256"] = canonical_digest(
        {key: value for key, value in freeze.items() if key != "freezeSha256"}
    )
    write_json(freeze_path, freeze)

    report = validate_blind_pairwise_veto(campaign, write_report=False)

    assert report["passed"] is False
    assert "execution_config_mismatch" in report["errors"]


def test_validator_rejects_unbound_quote(tmp_path: Path) -> None:
    campaign = prepare_campaign(tmp_path)
    certificates = valid_certificates(campaign)
    certificates[0]["leftAssessment"]["evidence"]["receipt"]["quote"] = "not in the prompt"
    write_jsonl(campaign / "veto/output/certificates.jsonl", certificates)

    report = validate_blind_pairwise_veto(campaign, write_report=False)

    assert report["passed"] is False
    assert "certificate_0_left_prompt_quote_not_found" in report["errors"]


def test_validator_rejects_role_mapping_tamper(tmp_path: Path) -> None:
    campaign = prepare_campaign(tmp_path)
    certificates = valid_certificates(campaign)
    write_jsonl(campaign / "veto/output/certificates.jsonl", certificates)
    mapping_path = campaign / "control/role_mapping.jsonl"
    mapping = load_jsonl(mapping_path)
    mapping[0]["rotationBit"] = 1 - mapping[0]["rotationBit"]
    write_jsonl(mapping_path, mapping)

    report = validate_blind_pairwise_veto(campaign, write_report=False)

    assert report["passed"] is False
    assert "role_mapping_hash_mismatch" in report["errors"]


def test_validator_rejects_rotation_control_tamper(tmp_path: Path) -> None:
    campaign = prepare_campaign(tmp_path)
    write_jsonl(campaign / "veto/output/certificates.jsonl", valid_certificates(campaign))
    rotation_path = campaign / "control/rotation.json"
    rotation = json.loads(rotation_path.read_text(encoding="utf-8"))
    rotation["seed"] += "-tampered"
    write_json(rotation_path, rotation)

    report = validate_blind_pairwise_veto(campaign, write_report=False)

    assert report["passed"] is False
    assert "rotation_control_hash_mismatch" in report["errors"]
    assert "rotation_seed_hash_mismatch" in report["errors"]


def test_validator_rejects_candidate_pair_order_tamper(tmp_path: Path) -> None:
    campaign = prepare_campaign(tmp_path)
    write_jsonl(campaign / "veto/output/certificates.jsonl", valid_certificates(campaign))
    pairs_path = campaign / "veto/input/candidate_pairs.jsonl"
    pairs = load_jsonl(pairs_path)
    pairs[0], pairs[1] = pairs[1], pairs[0]
    write_jsonl(pairs_path, pairs)

    report = validate_blind_pairwise_veto(campaign, write_report=False)

    assert report["passed"] is False
    assert "pairs_hash_mismatch" in report["errors"]
    assert "expected_ids_pair_order_mismatch" in report["errors"]
    assert "role_mapping_ids_order_mismatch" in report["errors"]


def test_validator_rejects_candidate_pair_answer_tamper(tmp_path: Path) -> None:
    campaign = prepare_campaign(tmp_path)
    write_jsonl(campaign / "veto/output/certificates.jsonl", valid_certificates(campaign))
    pairs_path = campaign / "veto/input/candidate_pairs.jsonl"
    pairs = load_jsonl(pairs_path)
    pairs[0]["leftAnswer"] = "gamma-0"
    write_jsonl(pairs_path, pairs)

    report = validate_blind_pairwise_veto(campaign, write_report=False)

    assert report["passed"] is False
    assert "pairs_hash_mismatch" in report["errors"]
    assert "role_mapping_0_left_hash" in report["errors"]
    assert "role_mapping_0_source_answer_mismatch" in report["errors"]


def test_validator_rejects_certificate_candidate_answer_tamper(tmp_path: Path) -> None:
    campaign = prepare_campaign(tmp_path)
    certificates = valid_certificates(campaign)
    certificates[0]["leftAssessment"]["candidateAnswer"] = "gamma-0"
    write_jsonl(campaign / "veto/output/certificates.jsonl", certificates)

    report = validate_blind_pairwise_veto(campaign, write_report=False)

    assert report["passed"] is False
    assert "certificate_0_left_candidate_answer_mismatch" in report["errors"]


def test_validator_rejects_malformed_receipt(tmp_path: Path) -> None:
    campaign = prepare_campaign(tmp_path)
    certificates = valid_certificates(campaign)
    certificates[0]["leftAssessment"]["evidence"] = {
        "type": "MODEL_KNOWLEDGE",
        "receipt": {"supportedClaim": "alpha-0 is the correct choice"},
    }
    write_jsonl(campaign / "veto/output/certificates.jsonl", certificates)

    report = validate_blind_pairwise_veto(campaign, write_report=False)

    assert report["passed"] is False
    assert "certificate_0_left_model_knowledge_receipt_schema" in report["errors"]


def test_validator_rejects_invalid_polarity(tmp_path: Path) -> None:
    campaign = prepare_campaign(tmp_path)
    certificates = valid_certificates(campaign)
    certificates[0]["targetPolarity"] = "SELECT_WHATEVER"
    write_jsonl(campaign / "veto/output/certificates.jsonl", certificates)

    report = validate_blind_pairwise_veto(campaign, write_report=False)

    assert report["passed"] is False
    assert "certificate_0_target_polarity" in report["errors"]


def test_validator_rejects_inconsistent_preference(tmp_path: Path) -> None:
    campaign = prepare_campaign(tmp_path)
    certificates = valid_certificates(campaign)
    certificates[0]["preference"] = "PREFER_RIGHT"
    write_jsonl(campaign / "veto/output/certificates.jsonl", certificates)

    report = validate_blind_pairwise_veto(campaign, write_report=False)

    assert report["passed"] is False
    assert "certificate_0_prefer_right_inconsistent" in report["errors"]


def test_unresolved_tie_requires_explicit_unresolved_uniqueness(tmp_path: Path) -> None:
    campaign = prepare_campaign(tmp_path)
    certificates = valid_certificates(campaign)
    for side in ("leftAssessment", "rightAssessment"):
        answer = certificates[0][side]["candidateAnswer"]
        certificates[0][side] = assessment(answer, "UNRESOLVED")
    certificates[0]["uniqueness"] = "UNRESOLVED"
    certificates[0]["preference"] = "TIE"
    certificates[0]["comparativeReason"] = "Neither side is resolved by the available evidence."
    write_jsonl(campaign / "veto/output/certificates.jsonl", certificates)

    accepted = validate_blind_pairwise_veto(campaign, write_report=False)
    assert accepted["passed"] is True

    certificates[0]["uniqueness"] = "BOTH_PLAUSIBLE"
    write_jsonl(campaign / "veto/output/certificates.jsonl", certificates)
    rejected = validate_blind_pairwise_veto(campaign, write_report=False)
    assert rejected["passed"] is False
    assert "certificate_0_tie_inconsistent" in rejected["errors"]


def test_certificate_jsonl_uses_lf_not_unicode_line_boundaries(tmp_path: Path) -> None:
    campaign = prepare_campaign(tmp_path)
    certificates = valid_certificates(campaign)
    certificates[0]["comparativeReason"] += " valid separators: \u0085 \u2028 \u2029"
    write_jsonl(campaign / "veto/output/certificates.jsonl", certificates)

    report = validate_blind_pairwise_veto(campaign, write_report=False)

    assert report["passed"] is True
    assert report["certificateRows"] == EXPECTED_CONFLICT_ROWS


def test_validator_rejects_partial_certificates(tmp_path: Path) -> None:
    campaign = prepare_campaign(tmp_path)
    certificates = valid_certificates(campaign)[:-1]
    write_jsonl(campaign / "veto/output/certificates.jsonl", certificates)

    report = validate_blind_pairwise_veto(campaign, write_report=False)

    assert report["passed"] is False
    assert "certificate_ids_order_or_coverage_mismatch" in report["errors"]


def test_validator_rejects_misordered_certificates(tmp_path: Path) -> None:
    campaign = prepare_campaign(tmp_path)
    certificates = valid_certificates(campaign)
    certificates[0], certificates[1] = certificates[1], certificates[0]
    write_jsonl(campaign / "veto/output/certificates.jsonl", certificates)

    report = validate_blind_pairwise_veto(campaign, write_report=False)

    assert report["passed"] is False
    assert "certificate_ids_order_or_coverage_mismatch" in report["errors"]
