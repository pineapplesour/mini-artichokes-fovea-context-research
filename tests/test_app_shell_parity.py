import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from apps.product_app import (
    PRODUCT_CHAT_ROUTES,
    PRODUCT_LANDING_ROUTES,
    PRODUCT_PAGES,
    PRODUCT_PORTS,
    create_product_app,
)
from shared_platform.products import PRODUCT_PROFILES
from shared_platform.server import create_app


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
MANIFEST = WEB / "app-shell-manifest.json"
VERIFIER = ROOT / "tools" / "verify_app_parity.py"
REQUIRED_CAPABILITIES = {
    "landing",
    "chat",
    "jobs",
    "jobEvents",
    "jobProgress",
    "jobCancel",
    "sourceWindow",
    "citationSourceWindow",
    "localChatStore",
    "offlineOutbox",
    "anonymousSessionToken",
    "accountSubjectBinding",
}


def _load_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _compact_js(text: str) -> str:
    return "".join(text.split())


def test_app_shell_manifest_defines_single_web_pwa_native_contract():
    assert MANIFEST.exists()
    manifest = _load_manifest()

    assert manifest["schemaVersion"] == 1
    assert manifest["contract"] == "shared-beta6-app-shell"
    assert manifest["nativeShell"]["mode"] == "thin-webview"
    assert manifest["nativeShell"]["routesSource"] == "app-shell-manifest.json"
    assert manifest["nativeShell"]["featureSource"] == "app-shell-manifest.json"
    assert manifest["web"]["serviceWorker"] == "/sw.js"
    assert manifest["web"]["pwaManifest"] == "/static/manifest.webmanifest"
    assert "/static/chat-store.js" in manifest["sharedAssets"]
    assert "/static/job-events.js" in manifest["sharedAssets"]
    assert "/static/job-progress.js" in manifest["sharedAssets"]
    assert "/static/job-cancel.js" in manifest["sharedAssets"]

    products = manifest["products"]
    assert set(products) == set(PRODUCT_PORTS)
    for key, item in products.items():
        profile = PRODUCT_PROFILES[key]
        assert item["key"] == key
        assert item["name"] == profile.name
        assert item["theme"] == profile.theme
        assert item["serverPort"] == PRODUCT_PORTS[key]
        assert item["defaultLanguage"] == profile.default_language
        assert item["languages"] == list(profile.languages)
        assert item["landingRoute"] == PRODUCT_LANDING_ROUTES[key]
        assert item["chatRoute"] == PRODUCT_CHAT_ROUTES[key]
        assert set(item["exposedPages"]) == PRODUCT_PAGES[key]
        if key == "tcm":
            assert "tcm-vertical" in item["exposedPages"]
        assert set(item["capabilities"]) == REQUIRED_CAPABILITIES
        assert item["native"]["entryRoute"] == item["landingRoute"]
        assert item["native"]["chatRoute"] == item["chatRoute"]
        assert item["native"]["offlineStore"] == "indexeddb-outbox-compatible"
        assert item["native"]["sessionTokenStore"] == "product-local-secret"
        assert item["native"]["accountSubjectStore"] == "product-account-subject"
        assert item["api"]["jobs"] == f"/api/{key}/jobs"
        assert item["api"]["sourceWindow"] == f"/api/{key}/source-window"
        assert item["api"]["jobStatus"] == f"/api/{key}/jobs/{{jobId}}"
        assert item["api"]["jobEvents"] == f"/api/{key}/jobs/{{jobId}}/events"
        assert item["api"]["jobResult"] == f"/api/{key}/jobs/{{jobId}}/result"
        assert item["api"]["jobCancel"] == f"/api/{key}/jobs/{{jobId}}/cancel"


def test_default_product_routes_use_requested_design_shells():
    islam = TestClient(create_product_app("islam"))
    islam_home = islam.get("/")
    islam_chat = islam.get("/islam-merian-chat.html")

    assert islam_home.status_code == 200
    assert islam_chat.status_code == 200
    assert "HIKMAH" in islam_home.text
    assert 'class="merian-shell merian-booting"' in islam_home.text
    assert 'href="/static/merian-chat.css?v=20260701-mobile-send-icon-1"' in islam_home.text
    assert "HIKMAH Merian Preview" in islam_chat.text
    assert 'src="/static/merian-chat.js?v=20260701-mobile-send-icon-1"' in islam_chat.text

    manifest = _load_manifest()
    assert manifest["products"]["islam"]["landingRoute"] == PRODUCT_LANDING_ROUTES["islam"]
    assert manifest["products"]["islam"]["chatRoute"] == PRODUCT_CHAT_ROUTES["islam"]
    assert manifest["products"]["islam"]["native"]["entryRoute"] == PRODUCT_LANDING_ROUTES["islam"]
    assert manifest["products"]["islam"]["native"]["chatRoute"] == PRODUCT_CHAT_ROUTES["islam"]
    assert manifest["products"]["simli"]["name"] == "PsyKey AI"
    assert manifest["products"]["simli"]["native"]["displayName"] == "PsyKey AI"


def test_default_chat_shells_merge_gdrive_reference_design_without_losing_beta6_contract():
    islam = TestClient(create_product_app("islam"))
    tcm = TestClient(create_product_app("tcm"))
    simli = TestClient(create_product_app("simli"))

    islam_home = islam.get("/")
    islam_chat = islam.get(PRODUCT_CHAT_ROUTES["islam"])
    tcm_chat = tcm.get(PRODUCT_CHAT_ROUTES["tcm"])
    simli_chat = simli.get(PRODUCT_CHAT_ROUTES["simli"])

    assert islam_home.status_code == 200
    assert islam_chat.status_code == 200
    assert tcm_chat.status_code == 200
    assert simli_chat.status_code == 200

    assert "HIKMAH" in islam_home.text
    assert "HIKMAH Merian Preview" in islam_home.text
    assert 'id="composer"' in islam_home.text
    assert 'id="room-list"' in islam_home.text
    assert 'id="source-modal"' in islam_home.text
    assert 'data-legal-footer' in islam_home.text
    assert "/static/merian-chat.js" in islam_home.text

    assert "HIKMAH" in islam_chat.text
    assert 'class="merian-shell merian-booting"' in islam_chat.text
    assert 'id="messages"' in islam_chat.text
    assert 'id="input"' in islam_chat.text
    assert "/static/merian-chat.js" in islam_chat.text

    assert "Hanui AI" in tcm_chat.text
    assert "Hanui AI Merian Preview" in tcm_chat.text
    assert 'class="merian-shell merian-booting"' in tcm_chat.text
    assert 'id="composer"' in tcm_chat.text
    assert 'id="source-modal"' in tcm_chat.text
    assert "/static/merian-chat.js" in tcm_chat.text

    # G:\내 드라이브\ㅇㅇㅇㅇㅇㅇ\심리AI_UI_따뜻한버전.html
    assert "PsyKey AI" in simli_chat.text
    assert "현재 세션 로그" in simli_chat.text
    assert "참고 문헌 및 근거" in simli_chat.text
    assert "heatmap-container" in simli_chat.text
    assert "bottom-fade" in simli_chat.text
    assert "/static/simli-chat.js" in simli_chat.text
    assert "data-chat-history" in simli_chat.text
    assert "data-progress-detail" in simli_chat.text


def test_app_shell_manifest_routes_assets_and_pwa_shortcuts_match_files():
    manifest = _load_manifest()
    pwa = json.loads((WEB / "manifest.webmanifest").read_text(encoding="utf-8"))
    shortcut_urls = {item["url"] for item in pwa["shortcuts"]}
    sw = (WEB / "sw.js").read_text(encoding="utf-8")

    assert "/static/app-shell-manifest.json" in sw
    for asset in manifest["sharedAssets"]:
        assert asset in sw
        if asset.startswith("/static/"):
            assert (WEB / asset.removeprefix("/static/")).exists()

    for key, item in manifest["products"].items():
        landing = WEB / item["landingRoute"].lstrip("/")
        chat = WEB / item["chatRoute"].lstrip("/")
        chat_js = item.get("clientScript") or f"/static/{key}-chat.js"
        assert landing.exists()
        assert chat.exists()
        assert item["landingRoute"] in shortcut_urls
        assert item["chatRoute"] in shortcut_urls
        assert item["landingRoute"] in sw
        assert item["chatRoute"] in sw
        assert chat_js in sw
        for page in item["exposedPages"]:
            page_path = WEB / f"{page}.html"
            assert page_path.exists()
        assert item["landingRoute"] in sw
        assert item["chatRoute"] in sw
        for path in (landing, chat):
            text = path.read_text(encoding="utf-8")
            assert f'data-product="{key}"' in text
            assert "https://" not in text
            assert "http://" not in text
            assert "data:image" not in text
        js_path = WEB / chat_js.removeprefix("/static/") if chat_js.startswith("/static/") else WEB / chat_js.lstrip("/")
        assert js_path.exists()
        js = js_path.read_text(encoding="utf-8")
        compact = _compact_js(js)
        assert "jobCreateHeaders" in js
        assert "chatStore.jobUrl(path,token)" in compact or "chatStore.jobUrl" in js
        assert "Beta6JobEvents.follow" in js
        if chat_js == "/static/merian-chat.js":
            assert "PHASE_SEQUENCE" in js
            assert "progressEntry" in js
            assert "renderJobStatus" in js
        else:
            assert "Beta6JobProgress.render" in js
        assert "Beta6JobCancel.cancel" in js


def test_app_shell_manifest_is_available_to_split_servers_and_native_wrappers():
    client = TestClient(create_app({"islam": PRODUCT_PROFILES["islam"]}, default_page="islam.html", exposed_pages={"islam", "islam-chat"}))

    response = client.get("/static/app-shell-manifest.json")

    assert response.status_code == 200
    manifest = response.json()
    assert set(manifest["products"]) == set(PRODUCT_PORTS)
    assert manifest["products"]["islam"]["chatRoute"] == PRODUCT_CHAT_ROUTES["islam"]


def test_app_parity_verifier_reports_manifest_route_and_runtime_contract():
    assert VERIFIER.exists()
    completed = subprocess.run(
        [sys.executable, str(VERIFIER), "--json"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    report = json.loads(completed.stdout)

    assert report["passes"] is True
    assert report["manifest"]["path"] == "web/app-shell-manifest.json"
    assert report["nativeShell"]["mode"] == "thin-webview"
    assert set(report["products"]) == set(PRODUCT_PORTS)
    for key, item in report["products"].items():
        assert item["passes"] is True, key
        assert item["routesMatch"] is True
        assert item["capabilitiesMatch"] is True
        assert item["webAssetsPass"] is True
        assert item["nativeUsesManifestRoutes"] is True
