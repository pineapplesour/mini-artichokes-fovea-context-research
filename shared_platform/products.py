from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProductProfile:
    key: str
    name: str
    db_path: Path
    db_shape: str
    languages: tuple[str, ...]
    default_language: str
    theme: str
    safety_notice: str


ROOT = Path(__file__).resolve().parents[1]


def _path_from_env(env_name: str) -> Path | None:
    value = os.getenv(env_name, "").strip()
    return Path(value) if value else None


def _db_path(env_name: str, deploy_path: str, local_relative: str) -> Path:
    override = _path_from_env(env_name)
    if override:
        return override
    local = ROOT / local_relative
    if local.exists():
        return local
    return Path(deploy_path)


PRODUCT_PROFILES: dict[str, ProductProfile] = {
    "islam": ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=_db_path(
            "RELIGION_ISLAM_DB_PATH",
            "/var/lib/universal-artichoke/corpus/islam/islam.sqlite3",
            "corpus/islam/islam.sqlite3",
        ),
        db_shape="precedents",
        languages=("en", "ko", "ar", "pa", "ur", "bn", "id", "ms", "fa", "tr", "sw"),
        default_language="en",
        theme="merian",
        safety_notice=(
            "This answer is grounded in retrieved religious texts. For Qur'an passages, "
            "machine output must not be treated as Qur'an translation; consult qualified scholars."
        ),
    ),
    "tcm": ProductProfile(
        key="tcm",
        name="Hanui AI",
        db_path=_db_path(
            "RELIGION_TCM_DB_PATH",
            "/var/lib/universal-artichoke/corpus/tcm/tcm.sqlite3",
            "corpus/tcm/tcm.sqlite3",
        ),
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="merian",
        safety_notice=(
            "This is a classical-text search aid, not a diagnosis or treatment plan. "
            "Use qualified medical care for symptoms, medication, pregnancy, or urgent issues."
        ),
    ),
    "buddhist": ProductProfile(
        key="buddhist",
        name="Buddhist AI",
        db_path=_db_path(
            "RELIGION_BUDDHIST_DB_PATH",
            "/var/lib/universal-artichoke/corpus/buddhist/buddhist.sqlite3",
            "corpus/buddhist/buddhist.sqlite3",
        ),
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="merian",
        safety_notice=(
            "This is a source-grounded study aid for Buddhist texts. "
            "Do not treat generated output as a doctrinal ruling or a substitute for qualified teachers."
        ),
    ),
    "catholic": ProductProfile(
        key="catholic",
        name="Christian AI",
        db_path=_db_path(
            "RELIGION_CATHOLIC_DB_PATH",
            "/var/lib/universal-artichoke/corpus/catholic/catholic.sqlite3",
            "corpus/catholic/catholic.sqlite3",
        ),
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="merian",
        safety_notice=(
            "This is a source-grounded study aid for Catholic texts. "
            "Consult qualified clergy or authoritative documents for pastoral or doctrinal decisions."
        ),
    ),
    "hindu": ProductProfile(
        key="hindu",
        name="Hindu AI",
        db_path=_db_path(
            "RELIGION_HINDU_DB_PATH",
            "/var/lib/universal-artichoke/corpus/hindu/hindu.sqlite3",
            "corpus/hindu/hindu.sqlite3",
        ),
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="merian",
        safety_notice=(
            "This is a source-grounded study aid for Hindu texts. "
            "Use it for reading and comparison, not as a substitute for a living tradition or teacher."
        ),
    ),
    "simli": ProductProfile(
        key="simli",
        name="PsyKey AI",
        db_path=_db_path(
            "RELIGION_SIMLI_DB_PATH",
            "/var/lib/universal-artichoke/corpus/simli/psych.sqlite",
            "corpus/simli/psych.sqlite",
        ),
        db_shape="documents",
        languages=("ko", "en"),
        default_language="ko",
        theme="simli",
        safety_notice=(
            "This is evidence-based mental-health information, not a diagnosis. "
            "If there is risk of self-harm, harm to others, or immediate danger, contact local emergency help now."
        ),
    ),
}


def get_product(key: str) -> ProductProfile:
    normalized = str(key or "").strip().lower()
    try:
        return PRODUCT_PROFILES[normalized]
    except KeyError as exc:
        raise KeyError(f"unknown product: {key}") from exc
