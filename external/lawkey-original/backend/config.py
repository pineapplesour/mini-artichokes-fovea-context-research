from __future__ import annotations

import os
from pathlib import Path


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def _env_path(name: str, default: str | Path) -> Path:
    value = _env_str(name, str(default))
    return Path(value).expanduser()


def _env_int(name: str, default: int, *, minimum: int | None = None) -> int:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value.strip())
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return parsed


def _env_int_tuple(name: str, default: tuple[int, ...]) -> tuple[int, ...]:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if not parts:
        return default
    try:
        return tuple(int(part) for part in parts)
    except ValueError as exc:
        raise ValueError(f"{name} must be a comma-separated integer list") from exc


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRESETS_ROOT = PROJECT_ROOT / "data" / "presets"
WORKSPACE_ROOT = _env_path("LAWKEY_WORKSPACE_ROOT", "/var/lib/lawkey")
WORKSPACE_SCRIPTS = _env_path("LAWKEY_WORKSPACE_SCRIPTS", WORKSPACE_ROOT / "scripts")
LEGAL_RAG_SCRIPT = _env_path("LAWKEY_LEGAL_RAG_SCRIPT", WORKSPACE_SCRIPTS / "legal_evidence_rag.py")
PRECEDENT_DB_PATH = _env_path(
    "LAWKEY_PRECEDENT_DB_PATH",
    WORKSPACE_ROOT / "저장파일" / "unified_precedent_db_2026-04-10_run3" / "precedents.sqlite3",
)
RUNS_ROOT = _env_path("LAWKEY_RUNS_ROOT", WORKSPACE_ROOT / "저장파일" / "lawkey_ai_runtime")
QUESTION_VARIANT_NAME = _env_str("LAWKEY_QUESTION_VARIANT_NAME", "question_selected_manual")
DEFAULT_SELECT_MODEL = _env_str("LAWKEY_SELECT_MODEL", "gemma-4-26b-a4b-it")
DEFAULT_ANALYZE_MODEL = _env_str("LAWKEY_ANALYZE_MODEL", "gemma-4-26b-a4b-it")
DEFAULT_DRAFT_MODEL = _env_str("LAWKEY_DRAFT_MODEL", "gemma-4-26b-a4b-it")
DEFAULT_KEYWORD_COUNT = _env_int("LAWKEY_KEYWORD_COUNT", 10, minimum=1)
DEFAULT_PER_KEYWORD_LIMIT = _env_int("LAWKEY_PER_KEYWORD_LIMIT", 80, minimum=1)
DEFAULT_TOP_K = _env_int("LAWKEY_TOP_K", 100, minimum=1)
DEFAULT_WORKER_COUNT = _env_int("LAWKEY_WORKER_COUNT", 10, minimum=1)
DEFAULT_KEY_MIN_GAP_MS = _env_int("LAWKEY_KEY_MIN_GAP_MS", 2000, minimum=0)
DEFAULT_KEY_MAX_INFLIGHT = _env_int("LAWKEY_KEY_MAX_INFLIGHT", 1, minimum=1)
DEFAULT_KEY_RPM_LIMIT = _env_int("LAWKEY_KEY_RPM_LIMIT", 20, minimum=1)
DEFAULT_KEY_TPM_LIMIT = _env_int("LAWKEY_KEY_TPM_LIMIT", 100000, minimum=0)
DEFAULT_GLOBAL_MAX_INFLIGHT = _env_int("LAWKEY_GLOBAL_MAX_INFLIGHT", 10, minimum=1)
DEFAULT_JOB_MAX_ATTEMPTS = _env_int("LAWKEY_JOB_MAX_ATTEMPTS", 0, minimum=0)
DEFAULT_RETRY_BACKOFF_SECONDS = _env_int_tuple("LAWKEY_RETRY_BACKOFF_SECONDS", (5, 15, 30))

DOCUMENT_PRESETS = [
    {
        "id": "defense_opinion",
        "label": "변호인의견서 프리셋",
        "path": str(PRESETS_ROOT / "defense_opinion_assault_anonymized.md"),
        "paths": [
            str(PRESETS_ROOT / "defense_opinion_assault_anonymized.md"),
            str(PRESETS_ROOT / "defense_opinion_insult_anonymized.md"),
        ],
        "aliases": ["defense_opinion_assault", "defense_opinion_insult"],
    },
    {
        "id": "complaint",
        "label": "고소장 프리셋",
        "path": str(PRESETS_ROOT / "complaint_template.md"),
        "paths": [
            str(PRESETS_ROOT / "complaint_template.md"),
            str(PRESETS_ROOT / "complaint_example_anonymized.md"),
            str(PRESETS_ROOT / "official_police_simple_complaint_defamation.hwp"),
            str(PRESETS_ROOT / "official_police_simple_complaint_attachment.hwp"),
        ],
        "aliases": ["complaint_template", "complaint_example"],
    },
]
