from __future__ import annotations

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
    path_allowlist: tuple[Path, ...]
    language_script_groups: tuple[tuple[str, tuple[str, ...]], ...] = ()


ISLAM_DB = Path("/var/lib/universal-artichoke/corpus/islam/islam.sqlite3")
CATHOLIC_DB = Path("/var/lib/universal-artichoke/corpus/catholic/catholic.sqlite3")
BUDDHIST_DB = Path("/var/lib/universal-artichoke/corpus/buddhist/buddhist.sqlite3")
HINDU_DB = Path("/var/lib/universal-artichoke/corpus/hindu/hindu.sqlite3")
TCM_DB = Path("/var/lib/universal-artichoke/corpus/tcm/tcm.sqlite3")
PSYCHOLOGY_DB = Path("/var/lib/universal-artichoke/corpus/simli/psych.sqlite")

ISLAM_LANGUAGE_SCRIPT_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("hangul", ("ko",)),
    ("gurmukhi", ("pa",)),
    ("bengali", ("bn",)),
    ("arabic", ("ar", "ur", "fa")),
    ("latin", ("en", "id", "ms", "tr", "sw")),
)

KO_EN_LANGUAGE_SCRIPT_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("hangul", ("ko",)),
    ("latin", ("en",)),
)


PRODUCT_PROFILES: dict[str, ProductProfile] = {
    "islam": ProductProfile(
        key="islam",
        name="Hikmah",
        db_path=ISLAM_DB,
        db_shape="precedents",
        languages=("en", "ko", "ar", "pa", "ur", "bn", "id", "ms", "fa", "tr", "sw"),
        default_language="en",
        theme="islam",
        safety_notice=(
            "Grounded religious-study aid only. It is not a binding fatwa, and machine output must not be treated "
            "as an authoritative Qur'an translation."
        ),
        path_allowlist=(ISLAM_DB,),
        language_script_groups=ISLAM_LANGUAGE_SCRIPT_GROUPS,
    ),
    "catholic": ProductProfile(
        key="catholic",
        name="Veritas",
        db_path=CATHOLIC_DB,
        db_shape="precedents",
        languages=("en", "ko"),
        default_language="en",
        theme="religion",
        safety_notice=(
            "Grounded religious-study aid only. It is not ecclesial authority, pastoral care, or a substitute "
            "for a qualified clergy or scholar."
        ),
        path_allowlist=(CATHOLIC_DB,),
        language_script_groups=KO_EN_LANGUAGE_SCRIPT_GROUPS,
    ),
    "buddhist": ProductProfile(
        key="buddhist",
        name="Bodhi",
        db_path=BUDDHIST_DB,
        db_shape="precedents",
        languages=("en", "ko"),
        default_language="en",
        theme="religion",
        safety_notice=(
            "Grounded religious-study aid only. It is not monastic instruction, pastoral care, or a substitute "
            "for a qualified teacher."
        ),
        path_allowlist=(BUDDHIST_DB,),
        language_script_groups=KO_EN_LANGUAGE_SCRIPT_GROUPS,
    ),
    "hindu": ProductProfile(
        key="hindu",
        name="Dharma",
        db_path=HINDU_DB,
        db_shape="precedents",
        languages=("en", "ko"),
        default_language="en",
        theme="religion",
        safety_notice=(
            "Grounded religious-study aid only. It is not ritual authority, pastoral care, or a substitute "
            "for a qualified teacher."
        ),
        path_allowlist=(HINDU_DB,),
        language_script_groups=KO_EN_LANGUAGE_SCRIPT_GROUPS,
    ),
    "tcm": ProductProfile(
        key="tcm",
        name="Uiwon",
        db_path=TCM_DB,
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="tcm",
        safety_notice=(
            "Classical-text and corpus search aid only. It is not diagnosis, prescription, or emergency care; "
            "consult a qualified clinician for symptoms, pregnancy, medication, or urgent issues."
        ),
        path_allowlist=(TCM_DB,),
        language_script_groups=KO_EN_LANGUAGE_SCRIPT_GROUPS,
    ),
    "psychology": ProductProfile(
        key="psychology",
        name="Maeumgyeol",
        db_path=PSYCHOLOGY_DB,
        db_shape="documents",
        languages=("ko", "en"),
        default_language="ko",
        theme="psychology",
        safety_notice=(
            "Evidence-based mental-health information only, not diagnosis. If there is self-harm, harm-to-others, "
            "or immediate danger risk, contact local emergency support now."
        ),
        path_allowlist=(PSYCHOLOGY_DB,),
        language_script_groups=KO_EN_LANGUAGE_SCRIPT_GROUPS,
    ),
}


def get_domain_product(key: str) -> ProductProfile:
    normalized = str(key or "").strip().lower()
    if normalized == "simli":
        normalized = "psychology"
    try:
        return PRODUCT_PROFILES[normalized]
    except KeyError as exc:
        raise KeyError(f"unknown product: {key}") from exc


def public_product_payload(profile: ProductProfile) -> dict[str, object]:
    return {
        "key": profile.key,
        "name": profile.name,
        "theme": profile.theme,
        "languages": list(profile.languages),
        "defaultLanguage": profile.default_language,
        "safetyNotice": profile.safety_notice,
    }
