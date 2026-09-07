#!/usr/bin/env python3
"""Verify web/PWA/native shell parity from the shared app-shell manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
MANIFEST_PATH = WEB / "app-shell-manifest.json"
ANDROID_ACTIVITY = ROOT / "native" / "android" / "app" / "src" / "main" / "java" / "ai" / "bunjum" / "beta6" / "NativeShellActivity.kt"
ANDROID_ASSET = ROOT / "native" / "android" / "app" / "src" / "main" / "assets" / "app-shell-manifest.json"
IOS_CONTROLLER = ROOT / "native" / "ios" / "Sources" / "NativeShellViewController.swift"
IOS_ASSET = ROOT / "native" / "ios" / "Resources" / "app-shell-manifest.json"
ANDROID_SETTINGS = ROOT / "native" / "android" / "settings.gradle.kts"
ANDROID_ROOT_BUILD = ROOT / "native" / "android" / "build.gradle.kts"
ANDROID_APP_BUILD = ROOT / "native" / "android" / "app" / "build.gradle.kts"
ANDROID_GRADLEW = ROOT / "native" / "android" / "gradlew"
ANDROID_MANIFEST = ROOT / "native" / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
IOS_PACKAGE = ROOT / "native" / "ios" / "Package.swift"
IOS_APP = ROOT / "native" / "ios" / "App" / "NativeShellApp.swift"
IOS_INFO = ROOT / "native" / "ios" / "App" / "Info.plist"
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

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.product_app import PRODUCT_CHAT_ROUTES, PRODUCT_LANDING_ROUTES, PRODUCT_PAGES, PRODUCT_PORTS  # noqa: E402
from shared_platform.products import PRODUCT_PROFILES  # noqa: E402


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def compact_js(text: str) -> str:
    return "".join(text.split())


def static_asset_path(asset: str) -> Path:
    if asset.startswith("/static/"):
        return WEB / asset.removeprefix("/static/")
    return WEB / asset.lstrip("/")


def client_supports_job_progress(js_text: str) -> bool:
    """Accept either the shared compact renderer or a client-native renderer fed by job status events."""
    return (
        "Beta6JobProgress.render" in js_text
        or (
            "renderJobStatus" in js_text
            and "phaseFromStatus" in js_text
            and "progressPercent" in js_text
            and "Beta6JobEvents.follow" in js_text
        )
    )


def product_report(key: str, item: dict[str, Any], sw: str, pwa_shortcuts: set[str]) -> dict[str, Any]:
    profile = PRODUCT_PROFILES.get(key)
    landing_route = str(item.get("landingRoute") or "")
    chat_route = str(item.get("chatRoute") or "")
    landing_path = WEB / landing_route.lstrip("/")
    chat_path = WEB / chat_route.lstrip("/")
    client_script = str(item.get("clientScript") or f"/static/{key}-chat.js")
    js_path = static_asset_path(client_script)
    landing_text = read_text(landing_path) if landing_path.exists() else ""
    chat_text = read_text(chat_path) if chat_path.exists() else ""
    js_text = read_text(js_path) if js_path.exists() else ""
    js_compact = compact_js(js_text)
    expected_pages = set(PRODUCT_PAGES.get(key, ()))
    expected_capabilities = REQUIRED_CAPABILITIES
    routes_match = (
        profile is not None
        and item.get("serverPort") == PRODUCT_PORTS.get(key)
        and item.get("name") == profile.name
        and item.get("theme") == profile.theme
        and item.get("defaultLanguage") == profile.default_language
        and item.get("languages") == list(profile.languages)
        and landing_route == PRODUCT_LANDING_ROUTES.get(key)
        and chat_route == PRODUCT_CHAT_ROUTES.get(key)
        and set(item.get("exposedPages") or []) == expected_pages
    )
    web_assets_pass = (
        landing_path.exists()
        and chat_path.exists()
        and js_path.exists()
        and all((WEB / f"{page}.html").exists() for page in item.get("exposedPages") or [])
        and f'data-product="{key}"' in landing_text
        and f'data-product="{key}"' in chat_text
        and landing_route in sw
        and chat_route in sw
        and client_script in sw
        and landing_route in pwa_shortcuts
        and chat_route in pwa_shortcuts
        and "jobCreateHeaders" in js_text
        and ("chatStore.jobUrl(path,token)" in js_compact or "chatStore.jobUrl" in js_text)
        and "Beta6JobEvents.follow" in js_text
        and client_supports_job_progress(js_text)
        and "Beta6JobCancel.cancel" in js_text
    )
    native = item.get("native") if isinstance(item.get("native"), dict) else {}
    native_uses_manifest_routes = (
        native.get("entryRoute") == landing_route
        and native.get("chatRoute") == chat_route
        and native.get("offlineStore") == "indexeddb-outbox-compatible"
        and native.get("sessionTokenStore") == "product-local-secret"
        and native.get("accountSubjectStore") == "product-account-subject"
    )
    api = item.get("api") if isinstance(item.get("api"), dict) else {}
    api_pass = (
        api.get("jobs") == f"/api/{key}/jobs"
        and api.get("sourceWindow") == f"/api/{key}/source-window"
        and api.get("jobStatus") == f"/api/{key}/jobs/{{jobId}}"
        and api.get("jobEvents") == f"/api/{key}/jobs/{{jobId}}/events"
        and api.get("jobResult") == f"/api/{key}/jobs/{{jobId}}/result"
        and api.get("jobCancel") == f"/api/{key}/jobs/{{jobId}}/cancel"
    )
    capabilities_match = set(item.get("capabilities") or []) == expected_capabilities
    passes = routes_match and web_assets_pass and native_uses_manifest_routes and api_pass and capabilities_match
    return {
        "passes": passes,
        "routesMatch": routes_match,
        "webAssetsPass": web_assets_pass,
        "nativeUsesManifestRoutes": native_uses_manifest_routes,
        "apiPass": api_pass,
        "capabilitiesMatch": capabilities_match,
        "landingRoute": landing_route,
        "chatRoute": chat_route,
    }


def build_report() -> dict[str, Any]:
    manifest_exists = MANIFEST_PATH.exists()
    manifest = read_json(MANIFEST_PATH) if manifest_exists else {}
    sw = read_text(WEB / "sw.js") if (WEB / "sw.js").exists() else ""
    pwa = read_json(WEB / "manifest.webmanifest") if (WEB / "manifest.webmanifest").exists() else {}
    pwa_shortcuts = {str(item.get("url") or "") for item in pwa.get("shortcuts") or [] if isinstance(item, dict)}
    shared_assets = list(manifest.get("sharedAssets") or [])
    pwa_manifest_asset = str(manifest.get("web", {}).get("pwaManifest") or "")
    sw_required_shared_assets = [asset for asset in shared_assets if asset != pwa_manifest_asset]
    shared_assets_pass = (
        bool(shared_assets)
        and all(static_asset_path(asset).exists() for asset in shared_assets)
        and all(asset in sw for asset in sw_required_shared_assets)
    )
    native_shell = manifest.get("nativeShell") if isinstance(manifest.get("nativeShell"), dict) else {}
    products = {
        key: product_report(key, item, sw, pwa_shortcuts)
        for key, item in sorted((manifest.get("products") or {}).items())
        if isinstance(item, dict)
    }
    manifest_pass = (
        manifest_exists
        and manifest.get("schemaVersion") == 1
        and manifest.get("contract") == "shared-beta6-app-shell"
        and set(products) == set(PRODUCT_PORTS)
        and native_shell.get("mode") == "thin-webview"
        and native_shell.get("routesSource") == "app-shell-manifest.json"
        and native_shell.get("featureSource") == "app-shell-manifest.json"
        and manifest.get("web", {}).get("serviceWorker") == "/sw.js"
        and manifest.get("web", {}).get("pwaManifest") == "/static/manifest.webmanifest"
    )
    native_source = native_source_report(manifest if isinstance(manifest, dict) else {})
    passes = manifest_pass and shared_assets_pass and native_source["passes"] and all(item["passes"] for item in products.values())
    return {
        "passes": passes,
        "manifest": {
            "path": "web/app-shell-manifest.json",
            "exists": manifest_exists,
            "contract": manifest.get("contract", ""),
            "schemaVersion": manifest.get("schemaVersion", 0),
        },
        "nativeShell": native_shell,
        "nativeSource": native_source,
        "sharedAssetsPass": shared_assets_pass,
        "products": products,
    }


def native_source_report(manifest: dict[str, Any]) -> dict[str, Any]:
    android_text = read_text(ANDROID_ACTIVITY) if ANDROID_ACTIVITY.exists() else ""
    ios_text = read_text(IOS_CONTROLLER) if IOS_CONTROLLER.exists() else ""
    android_settings = read_text(ANDROID_SETTINGS) if ANDROID_SETTINGS.exists() else ""
    android_root_build = read_text(ANDROID_ROOT_BUILD) if ANDROID_ROOT_BUILD.exists() else ""
    android_app_build = read_text(ANDROID_APP_BUILD) if ANDROID_APP_BUILD.exists() else ""
    android_gradlew = read_text(ANDROID_GRADLEW) if ANDROID_GRADLEW.exists() else ""
    android_manifest = read_text(ANDROID_MANIFEST) if ANDROID_MANIFEST.exists() else ""
    ios_package = read_text(IOS_PACKAGE) if IOS_PACKAGE.exists() else ""
    ios_app = read_text(IOS_APP) if IOS_APP.exists() else ""
    ios_info = read_text(IOS_INFO) if IOS_INFO.exists() else ""
    manifest_encoded = json.dumps(manifest, ensure_ascii=False, sort_keys=True)
    android_asset_synced = ANDROID_ASSET.exists() and json.dumps(read_json(ANDROID_ASSET), ensure_ascii=False, sort_keys=True) == manifest_encoded
    ios_asset_synced = IOS_ASSET.exists() and json.dumps(read_json(IOS_ASSET), ensure_ascii=False, sort_keys=True) == manifest_encoded
    android_source_pass = (
        ANDROID_ACTIVITY.exists()
        and "ApplicationInfo.FLAG_DEBUGGABLE" in android_text
        and "WebView.setWebContentsDebuggingEnabled(true)" in android_text
        and "app-shell-manifest.json" in android_text
        and "entryRoute" in android_text
        and "chatRoute" in android_text
        and "offlineStore" in android_text
        and "sessionTokenStore" in android_text
        and "accountSubjectStore" in android_text
        and "domStorageEnabled = true" in android_text
        and "databaseEnabled = true" in android_text
        and "javaScriptEnabled = true" in android_text
        and "shouldOverrideUrlLoading" in android_text
        and "allowedOrigin" in android_text
    )
    ios_source_pass = (
        IOS_CONTROLLER.exists()
        and "app-shell-manifest" in ios_text
        and "WKWebView" in ios_text
        and "entryRoute" in ios_text
        and "chatRoute" in ios_text
        and "offlineStore" in ios_text
        and "sessionTokenStore" in ios_text
        and "accountSubjectStore" in ios_text
        and "websiteDataStore" in ios_text
        and "allowedOrigin" in ios_text
        and "decidePolicyFor" in ios_text
    )
    android_project_pass = (
        ANDROID_SETTINGS.exists()
        and ANDROID_ROOT_BUILD.exists()
        and ANDROID_APP_BUILD.exists()
        and ANDROID_GRADLEW.exists()
        and ANDROID_MANIFEST.exists()
        and 'include(":app")' in android_settings
        and 'id("com.android.application")' in android_root_build
        and 'id("org.jetbrains.kotlin.android")' in android_root_build
        and 'namespace = "ai.bunjum.beta6"' in android_app_build
        and "minSdk = 23" in android_app_build
        and "targetSdk = 35" in android_app_build
        and "sourceCompatibility = JavaVersion.VERSION_17" in android_app_build
        and "targetCompatibility = JavaVersion.VERSION_17" in android_app_build
        and "jvmToolchain(17)" in android_app_build
        and "gradle-8.10.2-bin.zip" in android_gradlew
        and "NativeShellActivity" in android_manifest
        and "android.permission.INTERNET" in android_manifest
        and 'android:usesCleartextTraffic="false"' in android_manifest
        and 'android:exported="true"' in android_manifest
        and '"/islam.html"' not in android_app_build + android_manifest
        and '"/tcm.html"' not in android_app_build + android_manifest
        and '"/simli.html"' not in android_app_build + android_manifest
    )
    ios_project_pass = (
        IOS_PACKAGE.exists()
        and IOS_APP.exists()
        and IOS_INFO.exists()
        and "platforms: [.iOS(.v15)]" in ios_package
        and "executableTarget" in ios_package
        and 'resources: [.process("Resources")]' in ios_package
        and "NativeShellViewController" in ios_app
        and "UIApplicationSceneManifest" in ios_info
        and "NSAppTransportSecurity" in ios_info
        and "NSAllowsArbitraryLoads" not in ios_info
        and '"/islam.html"' not in ios_package + ios_app + ios_info
        and '"/tcm.html"' not in ios_package + ios_app + ios_info
        and '"/simli.html"' not in ios_package + ios_app + ios_info
    )
    assets_synced = android_asset_synced and ios_asset_synced
    return {
        "passes": android_source_pass and ios_source_pass and android_project_pass and ios_project_pass and assets_synced,
        "androidSourcePass": android_source_pass,
        "iosSourcePass": ios_source_pass,
        "androidProjectPass": android_project_pass,
        "iosProjectPass": ios_project_pass,
        "assetsSynced": assets_synced,
        "androidAssetSynced": android_asset_synced,
        "iosAssetSynced": ios_asset_synced,
        "androidGradleRunnerPass": ANDROID_GRADLEW.exists() and "gradle-8.10.2-bin.zip" in android_gradlew,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="write JSON to stdout")
    parser.add_argument("--output", help="write JSON report to this file")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    report = build_report()
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded + "\n", encoding="utf-8")
    if args.json:
        print(encoded)
    else:
        print(("PASS" if report["passes"] else "FAIL") + " app shell parity")
        for key, item in report["products"].items():
            print(f"{key}: routes={item['routesMatch']} web={item['webAssetsPass']} native={item['nativeUsesManifestRoutes']}")
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
