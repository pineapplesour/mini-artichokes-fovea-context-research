#!/usr/bin/env python3
"""Verify repository-level collaboration and handoff contracts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT

BILINGUAL_SOURCE_FILES = [
    "README.md",
    "STRUCTURE_REQUIREMENTS.md",
    "docs/overall-structure-requirements.md",
    "docs/runtime-architecture-options.md",
    "docs/instruction-language-policy.md",
    "docs/memory-engine-requirements.md",
    "docs/repository-governance.md",
    "docs/standalone-maintenance-workflow.md",
    "docs/team-collaboration-workflow.md",
    "engine/ENGINE_REQUIREMENTS.md",
    "engine/references/README.md",
    "frontend/FRONTEND_REQUIREMENTS.md",
    "frontend/contracts/engine-connection-guide.md",
    "frontend/contracts/kernel-boundary.md",
    "db/DB_SHARING_GUIDE.md",
    "corpus/README.md",
    "corpus/islam/README.md",
    "corpus/tcm/README.md",
    "corpus/simli/README.md",
    "tasks/team-instructions/README.md",
    "tasks/team-instructions/week-2026-05-15/team-1-engine.md",
    "tasks/team-instructions/week-2026-05-15/team-2-existing-ui.md",
    "tasks/team-instructions/week-2026-05-15/team-3-new-designs.md",
]

REQUIRED_FILES = [
    "docs/README.md",
    "frontend/contracts/ui-state-machine.md",
    "db/db-manifest.example.json",
    "db/current-db-inventory.json",
    "db/releases/db-full-20260514.json",
    "db/publish-db-snapshot.ps1",
    "integrations/lawkey/original-app-contract.json",
    "tools/verify_lawkey_original_contract.py",
    "corpus/christian/README.md",
    "corpus/christian/fixture.sql",
    "corpus/christian/denomination_registry.sql",
    "shared_platform/gemma_keyring.py",
    "tools/verify_team1_gemma_access.py",
    "tools/run_with_team1_gemma_keys.py",
    "tools/split_large_file.py",
    "tools/assemble_large_file.py",
    "standalone_run.py",
    "run-standalone.sh",
    "run-standalone.ps1",
    "tools/__init__.py",
    "tools/standalone_apply_diff_and_run.py",
    ".github/CODEOWNERS",
    ".github/pull_request_template.md",
    ".github/workflows/contract-check.yml",
    ".gitattributes",
    ".gitignore",
    ".githooks/pre-commit",
    "tasks/todo.md",
    "tasks/lessons.md",
    "tasks/wins.md",
]

CORPUS_REFERENCE_STUBS = [
    "docs/collection-policy.md",
    "docs/religion-db-architecture.md",
    "docs/sources-catalog-buddhist.md",
    "docs/sources-catalog-catholic.md",
    "docs/sources-catalog-christian.md",
    "docs/sources-catalog-hindu.md",
    "docs/sources-catalog-islam.md",
]

CORPUS_REFERENCE_FILES = [
    "corpus/reference/collection-policy.md",
    "corpus/reference/religion-db-architecture.md",
    "corpus/reference/sources-catalog-buddhist.md",
    "corpus/reference/sources-catalog-catholic.md",
    "corpus/reference/sources-catalog-christian.md",
    "corpus/reference/sources-catalog-hindu.md",
    "corpus/reference/sources-catalog-islam.md",
]

FORBIDDEN_STALE_FILES = [
    "cs16.css",
    "islamic-ai.html",
    "docs/design-reference-brief.md",
    "docs/superpowers/plans/2026-05-05-split-product-apps.md",
    "docs/superpowers/plans/2026-05-08-selector-evidence-ledger.md",
]

EN_REQUIRED_TEXT = {
    "STRUCTURE_REQUIREMENTS.md": [
        "Universal Artichoke",
        "DB/corpus -> memory engine -> answer contract -> frontend/web/native shell",
        "source-grounded-v2",
        "docs/runtime-architecture-options.md",
    ],
    "docs/runtime-architecture-options.md": [
        "Runtime Architecture Options",
        "What Should Stay Lightweight JavaScript",
        "Where Rust Or C Can Help",
        "Svelte",
        "Flutter",
        "Tauri",
    ],
    "docs/instruction-language-policy.md": [
        "bilingual operating contracts",
        "the shared UI kernel owns behavior only",
    ],
    "docs/overall-structure-requirements.md": [
        "Runtime Implementation Policy",
        "The committed `corpus/` directory is only for small fixture databases",
        "Rust/C are allowed and encouraged for measured engine or tooling hot paths",
        "Flutter can share web/native code and supports web Wasm",
    ],
    "engine/ENGINE_REQUIREMENTS.md": [
        "source-grounded-v2",
        "claimCards",
        "passageWindows",
        "Deduplication and repetition ledger",
        "Hit-Thunder",
        "Team 1 Gemma Key Access",
        "UNIVERSAL_ARTICHOKE_GEMMA_KEYS_FILE",
        "tools/run_with_team1_gemma_keys.py",
    ],
    "docs/memory-engine-requirements.md": [
        "Preserved Product Intent And Context",
        "What Was Chosen From Prior Work",
        "Prior Trial Lessons And Failure Patterns",
        "Concrete Failure Modes To Eliminate",
        "Duplicate, Count, And Identity Policy",
        "Reference Resolution And Time Policy",
        "https://github.com/pineapplesour/Hit-Thunder",
        "https://github.com/pineapplesour/mini-artichokes",
    ],
    "frontend/FRONTEND_REQUIREMENTS.md": [
        "SUBMIT_QUESTION",
        "Non-Negotiable UI Invariants",
        "data-action",
        "engine-near frontend foundation",
        "The kernel controls behavior only",
    ],
    "frontend/contracts/kernel-boundary.md": [
        "Kernel Owns Behavior Only",
        "Skin Owns Design",
        "The shared kernel must not impose geometry",
        "not full shared-browser-runtime integration",
        "Lawkey Migration Rule",
    ],
    "db/DB_SHARING_GUIDE.md": [
        "Git LFS",
        "DB Manifest",
        "stable canonical IDs",
        "publish-db-snapshot.ps1",
        "99 MiB Chunk Option",
        "db-full-20260514",
    ],
    "corpus/README.md": [
        "small test fixtures only",
        "not production or research corpora",
        "db-full-20260514",
        "RELIGION_LAWKEY_DB_PATH",
    ],
    "docs/repository-governance.md": [
        "Target Permission Model",
        "Current GitHub Enforcement Status",
        "Required Hosted Setup",
        "block force pushes",
        "Repository Rename",
        "not fully enforceable",
    ],
    "docs/team-collaboration-workflow.md": [
        "Weekly Instruction Files",
        "Wednesday Review Cadence",
        "Team 1 Engine",
        "Team 3 New Designs",
    ],
    "engine/references/README.md": [
        "Why These Notes Exist",
        "Hit-Thunder Coverage Patch",
        "mini-artichokes Redundant Convergence",
        "Prior Beta-6 Lessons",
    ],
    "frontend/contracts/engine-connection-guide.md": [
        "Product Skin",
        "shared UI kernel",
        "POST /api/{product}/jobs",
    ],
    "docs/standalone-maintenance-workflow.md": [
        "fallback workflow",
        "standalone_run.py",
        "This does not mean all development should be done by diff.",
    ],
    "README.md": [
        "Universal Artichoke",
        "python3 tools/verify_repo_contracts.py",
    ],
}

JSON_REQUIRED_TEXT = {
    "integrations/lawkey/original-app-contract.json": [
        "external-original-app",
        "hook-level-capability-boundary-not-full-shared-browser-runtime",
        "apps.lawkey.server:app",
        "preserveOriginalDesign",
        "preserveOriginalEngine",
    ],
}

FORBIDDEN_TEXT = [
    "/home/" + "pineapple",
    "/Users/" + "pineapple",
    "/mnt/c/Users/" + "pineapple",
    "park" + "1004book",
    "hyeongbin" + "park",
    "@naver" + ".com",
]


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def split_path(language: str, rel_path: str) -> Path:
    return ROOT / "docs" / language / rel_path


def read(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def tracked_files() -> list[str]:
    output = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return [item.decode("utf-8") for item in output.split(b"\0") if item]


def check_required_files() -> None:
    all_required = list(REQUIRED_FILES) + BILINGUAL_SOURCE_FILES + CORPUS_REFERENCE_STUBS
    for rel in BILINGUAL_SOURCE_FILES:
        all_required.append(f"docs/ko/{rel}")
        all_required.append(f"docs/en/{rel}")
    for rel in CORPUS_REFERENCE_FILES:
        all_required.append(f"docs/ko/{rel}")
        all_required.append(f"docs/en/{rel}")
    missing = [path for path in all_required if not (ROOT / path).exists()]
    if missing:
        fail("missing required files: " + ", ".join(missing))

    stale = [path for path in FORBIDDEN_STALE_FILES if (ROOT / path).exists()]
    if stale:
        fail("stale experimental files must be removed: " + ", ".join(stale))


def check_language_split() -> None:
    docs_root = ROOT / "docs"
    allowed_root_docs = {"README.md"} | {Path(path).name for path in BILINGUAL_SOURCE_FILES if path.startswith("docs/")} | {Path(path).name for path in CORPUS_REFERENCE_STUBS}
    for path in docs_root.glob("*.md"):
        if path.name not in allowed_root_docs:
            fail(f"docs root may only contain README.md and compatibility stubs, found: docs/{path.name}")

    for rel in BILINGUAL_SOURCE_FILES:
        stub = ROOT / rel
        ko = split_path("ko", rel)
        en = split_path("en", rel)
        stub_text = read(stub)
        ko_text = read(ko)
        en_text = read(en)

        if f"docs/ko/{rel}" not in stub_text:
            fail(f"{rel} must point to docs/ko/{rel}")
        if f"docs/en/{rel}" not in stub_text:
            fail(f"{rel} must point to docs/en/{rel}")
        if "## 한국어 지침" in stub_text or "## English Version" in stub_text:
            fail(f"{rel} must be a language-split stub, not an inline bilingual document")

        en_lines = max(1, len(en_text.splitlines()))
        ko_lines = len(ko_text.splitlines())
        if ko_lines < int(en_lines * 0.85):
            fail(f"docs/ko/{rel} is too short compared with docs/en/{rel}: {ko_lines}/{en_lines}")
        if ko_text.count("```") != en_text.count("```"):
            fail(f"docs/ko/{rel} must preserve fenced code block count")

    for rel, needles in EN_REQUIRED_TEXT.items():
        text = read(split_path("en", rel))
        for needle in needles:
            if needle not in text:
                fail(f"docs/en/{rel} is missing required text: {needle!r}")

    for stub_rel in CORPUS_REFERENCE_STUBS:
        stub_text = read(ROOT / stub_rel)
        ko_path = f"docs/ko/corpus/reference/{Path(stub_rel).name}"
        en_path = f"docs/en/corpus/reference/{Path(stub_rel).name}"
        if ko_path not in stub_text:
            fail(f"{stub_rel} must point to {ko_path}")
        if en_path not in stub_text:
            fail(f"{stub_rel} must point to {en_path}")

    docs_map = read(ROOT / "docs/README.md")
    for needle in (
        "docs/ko/",
        "docs/en/",
        "docs/{ko,en}/corpus/reference/",
        "Root-level files under `docs/` are indexes or compatibility pointers only.",
    ):
        if needle not in docs_map:
            fail(f"docs/README.md is missing documentation hierarchy text: {needle!r}")

    ko_policy = read(split_path("ko", "docs/instruction-language-policy.md"))
    for needle in ("이중 언어", "공유 UI 커널", "동작"):
        if needle not in ko_policy:
            fail(f"docs/ko/docs/instruction-language-policy.md is missing Korean policy text: {needle!r}")


def check_required_text() -> None:
    for path, needles in JSON_REQUIRED_TEXT.items():
        text = read(ROOT / path)
        for needle in needles:
            if needle not in text:
                fail(f"{path} is missing required text: {needle!r}")


def check_db_contracts() -> None:
    manifest = json.loads(read(ROOT / "db/db-manifest.example.json"))
    required_manifest_keys = {"schemaVersion", "product", "dbShape", "fileName", "storage", "sizeBytes", "sha256", "compatibility"}
    missing_manifest_keys = required_manifest_keys - set(manifest)
    if missing_manifest_keys:
        fail("db/db-manifest.example.json missing keys: " + ", ".join(sorted(missing_manifest_keys)))

    inventory = json.loads(read(ROOT / "db/current-db-inventory.json"))
    fixtures = inventory.get("fixtures")
    if not isinstance(fixtures, list) or len(fixtures) < 3:
        fail("db/current-db-inventory.json must contain DB fixtures")
    for item in fixtures:
        for key in ("product", "localPath", "fileName", "sizeBytes", "dbShape"):
            if key not in item:
                fail(f"db/current-db-inventory.json fixture missing {key}")

    release = json.loads(read(ROOT / "db/releases/db-full-20260514.json"))
    if release.get("releaseTag") != "db-full-20260514":
        fail("db/releases/db-full-20260514.json has wrong releaseTag")
    products = release.get("products")
    if not isinstance(products, list) or len(products) != 7:
        fail("db/releases/db-full-20260514.json must contain 7 products")
    if release.get("assetCount") != 117:
        fail("db/releases/db-full-20260514.json must record 117 release assets")


def check_repo_policy() -> None:
    gitattributes = read(REPO_ROOT / ".gitattributes")
    for pattern in ("*.sqlite", "*.sqlite3", "*.db"):
        if pattern not in gitattributes or "filter=lfs" not in gitattributes:
            fail(f".gitattributes must configure Git LFS for {pattern}")

    codeowners = read(REPO_ROOT / ".github/CODEOWNERS")
    for owner_root in ("/engine/", "/frontend/", "/db/", "/web/", "/shared_platform/beta6.py"):
        if owner_root not in codeowners:
            fail(f"CODEOWNERS missing owner root {owner_root}")
    if "@pineapplesour" not in codeowners:
        fail("CODEOWNERS must use the current repository owner until organization teams exist")
    for placeholder_owner in ("@team-leads", "@engine-team", "@frontend-team", "@db-team"):
        if placeholder_owner in codeowners:
            fail(f"CODEOWNERS must not use placeholder team handle before organization setup: {placeholder_owner}")


def check_lawkey_contract() -> None:
    lawkey_contract = json.loads(read(ROOT / "integrations/lawkey/original-app-contract.json"))
    if lawkey_contract.get("mode") != "external-original-app":
        fail("Lawkey contract must remain external-original-app")
    for forbidden in ("web/lawkey.html", "web/lawkey-chat.html", "web/lawkey-chat.js"):
        if (ROOT / forbidden).exists():
            fail(f"fake Lawkey shared shell must not exist: {forbidden}")


def check_public_safety() -> None:
    tracked = tracked_files()
    if any(path.startswith("memory/") for path in tracked):
        fail("memory files must not be tracked")

    for path in tracked:
        if path.startswith(".git/"):
            continue
        full = ROOT / path
        if not full.exists() or not full.is_file():
            continue
        if full.suffix.lower() in {".hwp", ".hwpx", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".sqlite", ".sqlite3", ".db", ".zst"}:
            continue
        try:
            text = read(full)
        except UnicodeDecodeError:
            continue
        for forbidden in FORBIDDEN_TEXT:
            if forbidden.lower() in text.lower():
                fail(f"{path} contains forbidden personal/local text: {forbidden}")
        retired_root = "week" + "1"
        if retired_root in text.lower():
            fail(f"{path} contains retired legacy root reference")


def main() -> None:
    check_required_files()
    check_language_split()
    check_required_text()
    check_db_contracts()
    check_repo_policy()
    check_lawkey_contract()
    check_public_safety()
    print("repo contract verification passed")


if __name__ == "__main__":
    main()
