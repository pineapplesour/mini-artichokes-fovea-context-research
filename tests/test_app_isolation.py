import importlib

import pytest
from fastapi.testclient import TestClient

from shared_platform.products import ProductProfile
from shared_platform.server import create_app
from tests.test_search_adapters import _make_precedents_db


@pytest.fixture(autouse=True)
def _disable_default_lawkey_llm(monkeypatch):
    monkeypatch.setenv("RELIGION_LLM_DISABLED", "1")


def _profile(db_path, key="islam"):
    return ProductProfile(
        key=key,
        name=f"{key.title()} App",
        db_path=db_path,
        db_shape="precedents",
        languages=("en", "ko", "ar") if key == "islam" else ("ko", "en"),
        default_language="en" if key == "islam" else "ko",
        theme=key,
        safety_notice=f"{key} safety",
    )


def test_single_product_app_serves_only_its_page_and_profile(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    client = TestClient(
        create_app(
            {"islam": _profile(db_path, "islam")},
            default_page="islam.html",
            exposed_pages={"islam", "islam-chat"},
        )
    )

    root = client.get("/")
    islam_page = client.get("/islam.html")
    islam_chat = client.get("/islam-chat.html")
    tcm_page = client.get("/tcm.html")
    products = client.get("/api/products").json()["products"]
    tcm_search = client.get("/api/tcm/search", params={"q": "감초"})

    assert root.status_code == 200
    assert "HIKMAH" in root.text
    assert islam_page.status_code == 200
    assert islam_chat.status_code == 200
    assert tcm_page.status_code == 404
    assert [item["key"] for item in products] == ["islam"]
    assert tcm_search.status_code == 404


def test_existing_shared_app_still_serves_all_product_pages(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    profile = _profile(db_path, "islam")
    client = TestClient(create_app({"islam": profile}))

    assert client.get("/").status_code == 200
    assert client.get("/islam.html").status_code == 200
    assert client.get("/simli.html").status_code == 200


def test_product_server_entrypoints_are_separate_importable_apps(monkeypatch):
    monkeypatch.setenv("RELIGION_LLM_DISABLED", "1")
    expected = {
        "apps.islam.server": ("islam", 8061),
        "apps.tcm.server": ("tcm", 8062),
        "apps.simli.server": ("simli", 8063),
    }

    for module_name, (product_key, port) in expected.items():
        module = importlib.import_module(module_name)

        assert module.PRODUCT_KEY == product_key
        assert module.PORT == port
        assert module.app.title == f"{product_key} App"


def test_simli_single_product_app_serves_dedicated_chat_page(tmp_path):
    db_path = tmp_path / "simli.sqlite3"
    _make_precedents_db(db_path)
    client = TestClient(
        create_app(
            {"simli": _profile(db_path, "simli")},
            default_page="simli.html",
            exposed_pages={"simli", "simli-chat"},
        )
    )

    response = client.get("/simli-chat.html")
    sibling = client.get("/islam-chat.html")

    assert response.status_code == 200
    assert 'data-product="simli"' in response.text
    assert "/static/simli-chat.js" in response.text
    assert sibling.status_code == 404


def test_tcm_single_product_app_serves_reference2_vertical_landing(tmp_path):
    db_path = tmp_path / "tcm.sqlite3"
    _make_precedents_db(db_path)
    client = TestClient(
        create_app(
            {"tcm": _profile(db_path, "tcm")},
            default_page="tcm.html",
            exposed_pages={"tcm", "tcm-chat", "tcm-vertical"},
        )
    )

    vertical = client.get("/tcm-vertical.html")
    sibling = client.get("/islam.html")

    assert vertical.status_code == 200
    assert 'data-product="tcm"' in vertical.text
    assert "問而知之" in vertical.text
    assert "/tcm-chat.html" in vertical.text
    assert sibling.status_code == 404
