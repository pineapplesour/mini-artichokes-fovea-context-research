from pathlib import Path

from tools.sealed_candidate_identity import (
    REQUIRED_SEALED_RUNTIME_FILES,
    build_runtime_identity,
    validate_development_invocation,
    validate_runtime_identity,
)


SEALED_AT = "2026-07-19T15:00:00+09:00"


def _fixture(tmp_path: Path) -> tuple[dict, list[Path], dict]:
    for relative in REQUIRED_SEALED_RUNTIME_FILES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {relative}\n", encoding="utf-8")
    skills = [tmp_path / ".agents/skills/consult", tmp_path / ".agents/skills/search"]
    for index, skill in enumerate(skills):
        skill.mkdir(parents=True, exist_ok=True)
        (skill / "SKILL.md").write_text(f"skill {index}\n", encoding="utf-8")
    identity = build_runtime_identity(
        repo_root=tmp_path,
        sealed_at=SEALED_AT,
        approved_skill_paths=skills,
    )
    declared = [path.relative_to(tmp_path).as_posix() for path in skills]
    spec = {
        "schemaVersion": 2,
        "gateId": "fixture.v2",
        "status": "frozen_unrun",
        "frozenAt": SEALED_AT,
        "task": {"caseId": "q1", "publicManifest": "public.json"},
        "candidate": {
            "approvedSkillPaths": declared,
            "outputDir": "candidate",
            "model": "gpt-5.6-luna",
            "reasoningEffort": "low",
            "maxCaseSeconds": 180,
            "maximumQuotaFailoverAttemptsAcrossResumes": 8,
            "maxCaseTokens": 300,
            "codexHomeDiscoveryRoot": str(tmp_path / "homes"),
            "domainDatabase": str(tmp_path / "db.sqlite3"),
        },
        "sealedRuntimeIdentity": identity,
    }
    invocation = {
        "publicPath": str((tmp_path / "public.json").resolve()),
        "outputDir": str((tmp_path / "candidate").resolve()),
        "model": "gpt-5.6-luna",
        "reasoningEffort": "low",
        "timeoutSeconds": 180.0,
        "caseIds": ["q1"],
        "maxCases": 1,
        "maxTotalCalls": 8,
        "maxCallsThisInvocation": 1,
        "maxCaseTokens": 300,
        "discoverCodexHomeRoot": str((tmp_path / "homes").resolve()),
        "explicitCodexHomes": [],
        "domainDbPath": str((tmp_path / "db.sqlite3").resolve()),
        "nativeAgent": True,
        "evidenceGatedVerification": True,
        "compactNativeSkillBriefing": False,
        "domainEvidenceMcp": True,
        "webSearch": False,
        "hostDomainPrefetch": False,
        "reviewPass": False,
        "hypothesisAdjudication": False,
        "publicProductContext": False,
        "singlePassSelfVerify": False,
        "preserveDomainClassification": False,
        "promotedDomainClassificationRoute": False,
        "includeNeedsRewrite": False,
        "allowFixtureDb": False,
        "calculationTools": None,
        "allowExistingSwapSingleNativeEvidenceTask": True,
        "otherExistingSwapOverrides": False,
        "resume": False,
    }
    return spec, skills, invocation


def test_runtime_identity_binds_exact_files_skills_and_invocation(tmp_path):
    spec, skills, invocation = _fixture(tmp_path)

    assert validate_runtime_identity(
        spec=spec,
        repo_root=tmp_path,
        actual_approved_skill_paths=skills,
    ) == []
    assert validate_development_invocation(
        spec=spec,
        repo_root=tmp_path,
        invocation=invocation,
    ) == []


def test_runtime_or_skill_mutation_fails_closed(tmp_path):
    spec, skills, _ = _fixture(tmp_path)
    (tmp_path / "tools/run_codex_home_pool.py").write_text("mutated\n", encoding="utf-8")

    blockers = validate_runtime_identity(
        spec=spec,
        repo_root=tmp_path,
        actual_approved_skill_paths=skills,
    )
    assert "sealed_runtime_file_hash_mismatch" in blockers

    spec, skills, _ = _fixture(tmp_path)
    (skills[0] / "SKILL.md").write_text("mutated skill\n", encoding="utf-8")
    blockers = validate_runtime_identity(
        spec=spec,
        repo_root=tmp_path,
        actual_approved_skill_paths=skills,
    )
    assert "sealed_skill_tree_hash_mismatch" in blockers


def test_skill_list_or_invocation_drift_fails_closed(tmp_path):
    spec, skills, invocation = _fixture(tmp_path)
    blockers = validate_runtime_identity(
        spec=spec,
        repo_root=tmp_path,
        actual_approved_skill_paths=list(reversed(skills)),
    )
    assert "runtime_approved_skill_paths_mismatch" in blockers

    invocation["webSearch"] = True
    invocation["maxCaseTokens"] = 301
    blockers = validate_development_invocation(
        spec=spec,
        repo_root=tmp_path,
        invocation=invocation,
    )
    assert "sealed_invocation_webSearch_mismatch" in blockers
    assert "sealed_invocation_maxCaseTokens_mismatch" in blockers


def test_schema_v2_requires_sealed_identity(tmp_path):
    blockers = validate_runtime_identity(
        spec={"schemaVersion": 2},
        repo_root=tmp_path,
        actual_approved_skill_paths=[],
    )
    assert blockers == ["sealed_runtime_identity_missing"]
