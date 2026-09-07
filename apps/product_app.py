from __future__ import annotations

from pathlib import Path

from shared_platform.products import PRODUCT_PROFILES, ProductProfile
from shared_platform.server import create_app


PRODUCT_PORTS = {
    "islam": 8061,
    "tcm": 8062,
    "simli": 8063,
    "buddhist": 8064,
    "catholic": 8065,
    "hindu": 8066,
}

PRODUCT_PAGES = {
    "islam": frozenset({"islam", "islam-chat", "islam-bayyinah", "islam-bayyinah-chat", "islam-gallery", "islam-gallery-chat", "islam-merian-chat", "islam-buylow-chat"}),
    "tcm": frozenset({"tcm", "tcm-chat", "tcm-vertical", "tcm-gallery", "tcm-gallery-chat", "tcm-merian-chat"}),
    "simli": frozenset({"simli", "simli-chat"}),
    "buddhist": frozenset({"buddhist-gallery", "buddhist-gallery-chat", "buddhist-merian-chat", "buddhist-buylow-chat"}),
    "catholic": frozenset({"catholic-gallery", "catholic-gallery-chat", "catholic-merian-chat", "catholic-buylow-chat"}),
    "hindu": frozenset({"hindu-gallery", "hindu-gallery-chat", "hindu-merian-chat", "hindu-buylow-chat"}),
}

PRODUCT_LANDING_PAGES = {
    "islam": "islam-merian-chat.html",
    "tcm": "tcm-merian-chat.html",
    "simli": "simli.html",
    "buddhist": "buddhist-merian-chat.html",
    "catholic": "catholic-merian-chat.html",
    "hindu": "hindu-merian-chat.html",
}

PRODUCT_CHAT_PAGES = {
    "islam": "islam-merian-chat.html",
    "tcm": "tcm-merian-chat.html",
    "simli": "simli-chat.html",
    "buddhist": "buddhist-merian-chat.html",
    "catholic": "catholic-merian-chat.html",
    "hindu": "hindu-merian-chat.html",
}

PRODUCT_LANDING_ROUTES = {key: f"/{page}" for key, page in PRODUCT_LANDING_PAGES.items()}
PRODUCT_CHAT_ROUTES = {key: f"/{page}" for key, page in PRODUCT_CHAT_PAGES.items()}


def product_profile(product_key: str) -> ProductProfile:
    key = str(product_key or "").strip().lower()
    try:
        return PRODUCT_PROFILES[key]
    except KeyError as exc:
        raise KeyError(f"unknown product app: {product_key}") from exc


def product_port(product_key: str) -> int:
    key = str(product_key or "").strip().lower()
    try:
        return PRODUCT_PORTS[key]
    except KeyError as exc:
        raise KeyError(f"unknown product port: {product_key}") from exc


def create_product_app(product_key: str, *, web_dir: Path | None = None):
    key = str(product_key or "").strip().lower()
    profile = product_profile(key)
    return create_app(
        {key: profile},
        web_dir=web_dir,
        default_page=PRODUCT_LANDING_PAGES[key],
        exposed_pages=PRODUCT_PAGES[key],
    )
