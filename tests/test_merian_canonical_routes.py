import json
from pathlib import Path

from fastapi.testclient import TestClient

from shared_platform.server import create_app


WEB = Path("web")

CANONICAL_MERIAN_ROUTES = {
    "islam": ("islam", "islam-merian-chat.html"),
    "buddhist": ("buddhist", "buddhist-merian-chat.html"),
    "christian": ("catholic", "catholic-merian-chat.html"),
    "catholic": ("catholic", "catholic-merian-chat.html"),
    "hindu": ("hindu", "hindu-merian-chat.html"),
    "tcm": ("tcm", "tcm-merian-chat.html"),
}


def test_short_public_routes_serve_canonical_merian_pages():
    client = TestClient(create_app(web_dir=WEB))

    for public_route, (product, page) in CANONICAL_MERIAN_ROUTES.items():
        response = client.get(f"/{public_route}")

        assert response.status_code == 200
        assert f'data-product="{product}"' in response.text
        assert 'src="/static/merian-chat.js' in response.text
        assert response.text == (WEB / page).read_text(encoding="utf-8")


def test_manifest_marks_religion_and_tcm_canonical_routes_as_merian():
    manifest = json.loads((WEB / "app-shell-manifest.json").read_text(encoding="utf-8"))

    expected = {
        "islam": "/islam-merian-chat.html",
        "buddhist": "/buddhist-merian-chat.html",
        "catholic": "/catholic-merian-chat.html",
        "hindu": "/hindu-merian-chat.html",
        "tcm": "/tcm-merian-chat.html",
    }
    for product, route in expected.items():
        profile = manifest["products"][product]
        assert profile["theme"] == "merian"
        assert profile["landingRoute"] == route
        assert profile["chatRoute"] == route
        assert profile["clientScript"] == "/static/merian-chat.js"
        assert profile["native"]["entryRoute"] == route
        assert profile["native"]["chatRoute"] == route
