#!/usr/bin/env python3
"""Verify the current prompt-to-artifact completion audit.

This verifier is intentionally conservative: top-level ``passes`` means the
objective can be treated as achieved. As long as known blocking artifacts still
fail, the report remains ``not_achieved`` even if the audit files themselves are
current.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


AUDIT_FILES = (
    "tasks/completion-audit-2026-05-08.md",
    "tasks/requirements-audit.md",
)

LATEST_UI_PASS_ARTIFACTS = (
    "runs/low_end_runtime_i18n_language_shells_v43_20260508.json",
    "runs/app_parity_i18n_language_shells_v43_20260508.json",
    "runs/low_bandwidth_i18n_language_shells_v43_20260508.json",
    "runs/browser_runtime_i18n_language_shells_v43_20260508.json",
    "runs/tunnel_health_i18n_language_shells_v43_20260508.json",
)

LATEST_SECURITY_PASS_ARTIFACTS = (
    "runs/account_auth_readiness_20260508.json",
    "runs/app_parity_account_subject_binding_20260508.json",
    "runs/low_end_runtime_account_subject_binding_20260508.json",
    "runs/low_bandwidth_account_subject_binding_20260508.json",
)

LATEST_NATIVE_ANDROID_BUILD_ARTIFACT = "runs/native_build_smoke_android_debug_webview_20260508.json"
LATEST_NATIVE_ANDROID_WEBVIEW_PRODUCTS = (
    (
        "islam",
        "runs/20260508_android_webview_final_answer_islam_runtime.json",
        "runs/20260508_android_webview_final_answer_islam.json",
    ),
    (
        "tcm",
        "runs/20260508_android_webview_final_answer_tcm_retry2_runtime.json",
        "runs/20260508_android_webview_final_answer_tcm_retry2.json",
    ),
    (
        "simli",
        "runs/20260509_android_webview_final_answer_simli_runtime.json",
        "runs/20260509_android_webview_final_answer_simli.json",
    ),
)

LATEST_NATIVE_ANDROID_SOURCE_WINDOW_PRODUCTS = (
    (
        "islam",
        "runs/20260509_android_webview_source_window_islam_runtime.json",
        "runs/20260509_android_webview_source_window_islam_retry.json",
    ),
    (
        "tcm",
        "runs/20260509_android_webview_source_window_tcm_runtime.json",
        "runs/20260509_android_webview_source_window_tcm_retry.json",
    ),
    (
        "simli",
        "runs/20260509_android_webview_source_window_simli_runtime.json",
        "runs/20260509_android_webview_source_window_simli.json",
    ),
)

LATEST_NATIVE_ANDROID_PASS_ARTIFACTS = (
    LATEST_NATIVE_ANDROID_BUILD_ARTIFACT,
    *(
        artifact
        for _product, runtime_artifact, webview_artifact in LATEST_NATIVE_ANDROID_WEBVIEW_PRODUCTS
        for artifact in (runtime_artifact, webview_artifact)
    ),
    *(
        artifact
        for _product, runtime_artifact, source_window_artifact in LATEST_NATIVE_ANDROID_SOURCE_WINDOW_PRODUCTS
        for artifact in (runtime_artifact, source_window_artifact)
    ),
)

LATEST_WAYDROID_FOUR_APK_ARTIFACT = "runs/waydroid-four-apks-20260520-current/report.json"
LATEST_WAYDROID_REQUIRED_APP_KEYS = ("islam", "psykey", "tcm", "lawkey")
WAYDROID_FOUR_APK_BLOCKER = "Waydroid four-APK install/runtime/user-path"
LATEST_FOUR_ANDROID_APK_VERIFY_ARTIFACT = "runs/apk/four-android-apks-20260520-current-verify.json"
FOUR_ANDROID_APK_VERIFY_BLOCKER = "four Android APK artifact/signature/stamp verification"
FOUR_ANDROID_APK_REQUIRED_APPS = (
    ("islam", "ai.bunjum.hikmah", "islam"),
    ("psykey", "ai.bunjum.psykey", "simli"),
    ("tcm", "ai.bunjum.hanui", "tcm"),
    ("lawkey", "ai.bunjum.lawkey", "lawkey"),
)
FOUR_ANDROID_APK_REQUIRED_CHECKS = ("zipEntries", "dexStamps", "apksigner", "aaptPackage")

KNOWN_BLOCKING_ARTIFACTS = {
    "runs/app_path_budget_matrix_browser_submit_120s_required_20260508.json": "full-answer latency",
    "runs/app_path_budget_matrix_engine_stage_fresh_islam_simli_120s_30s_20260508.json": "engine-stage/source-selection latency",
    "runs/app_path_budget_matrix_islam_selector_recovery_parallel_cold_120s_30s_20260509.json": "engine-stage/source-selection latency",
    "runs/native_build_smoke_android_debug_webview_20260508.json": "native build/runtime",
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _artifact_status(root: Path, relative_path: str) -> dict[str, Any]:
    path = root / relative_path
    if not path.exists():
        return {"path": relative_path, "exists": False, "passes": False, "error": "missing artifact"}
    try:
        data = _read_json(path)
    except json.JSONDecodeError as exc:
        return {"path": relative_path, "exists": True, "passes": False, "error": f"invalid json: {exc}"}
    return {"path": relative_path, "exists": True, "passes": data.get("passes"), "error": ""}


def _android_runtime_artifact_status(root: Path, relative_path: str) -> dict[str, Any]:
    path = root / relative_path
    if not path.exists():
        return {"path": relative_path, "exists": False, "passes": False, "error": "missing artifact", "runtimeFieldsPass": False}
    try:
        data = _read_json(path)
    except json.JSONDecodeError as exc:
        return {"path": relative_path, "exists": True, "passes": False, "error": f"invalid json: {exc}", "runtimeFieldsPass": False}
    runtime_fields_pass = _android_runtime_fields_pass(data)
    return {
        "path": relative_path,
        "exists": True,
        "passes": bool(data.get("passes") is True and runtime_fields_pass),
        "rawPasses": data.get("passes"),
        "runtimeFieldsPass": runtime_fields_pass,
        "error": "" if runtime_fields_pass else "missing android runtime proof fields",
    }


def _android_runtime_fields_pass(data: dict[str, Any]) -> bool:
    if data.get("passes") is not True:
        return False
    if isinstance(data.get("device"), dict):
        return bool(
            data.get("apk", {}).get("exists") is True
            and data.get("apk", {}).get("sizeBytes", 0) > 0
            and data.get("device", {}).get("passes") is True
            and data.get("install", {}).get("passes") is True
            and data.get("launch", {}).get("passes") is True
            and data.get("process", {}).get("passes") is True
            and data.get("activity", {}).get("passes") is True
            and data.get("screenshot", {}).get("passes") is True
        )
    # Backward-compatible support for the first manually captured smoke artifact.
    return bool(
        data.get("booted") is True
        and data.get("installStatus") == "ok"
        and data.get("startStatus") == "ok"
        and data.get("appPid")
        and "ai.bunjum.beta6/.NativeShellActivity" in str(data.get("resumedActivity", ""))
        and data.get("screenshot", {}).get("captured") is True
    )


def _android_build_artifact_status(root: Path, relative_path: str) -> dict[str, Any]:
    path = root / relative_path
    if not path.exists():
        return {"path": relative_path, "exists": False, "passes": False, "error": "missing artifact", "androidBuildFieldsPass": False}
    try:
        data = _read_json(path)
    except json.JSONDecodeError as exc:
        return {
            "path": relative_path,
            "exists": True,
            "passes": False,
            "error": f"invalid json: {exc}",
            "androidBuildFieldsPass": False,
        }
    android_build_pass = _android_build_fields_pass(data)
    return {
        "path": relative_path,
        "exists": True,
        "passes": android_build_pass,
        "rawPasses": data.get("passes"),
        "androidBuildFieldsPass": android_build_pass,
        "error": "" if android_build_pass else "missing android build/APK proof fields",
    }


def _android_build_fields_pass(data: dict[str, Any]) -> bool:
    android = data.get("android") if isinstance(data.get("android"), dict) else {}
    build = android.get("build") if isinstance(android.get("build"), dict) else {}
    apk = build.get("apk") if isinstance(build.get("apk"), dict) else {}
    return bool(
        build.get("passes") is True
        and apk.get("exists") is True
        and apk.get("sizeBytes", 0) > 0
        and apk.get("manifestAssetSynced") is True
    )


def _android_webview_submit_artifact_status(root: Path, relative_path: str) -> dict[str, Any]:
    path = root / relative_path
    if not path.exists():
        return {"path": relative_path, "exists": False, "passes": False, "error": "missing artifact", "webviewFieldsPass": False}
    try:
        data = _read_json(path)
    except json.JSONDecodeError as exc:
        return {
            "path": relative_path,
            "exists": True,
            "passes": False,
            "error": f"invalid json: {exc}",
            "webviewFieldsPass": False,
        }
    webview_fields_pass = _android_webview_submit_fields_pass(data)
    return {
        "path": relative_path,
        "exists": True,
        "passes": bool(data.get("passes") is True and webview_fields_pass),
        "rawPasses": data.get("passes"),
        "webviewFieldsPass": webview_fields_pass,
        "error": "" if webview_fields_pass else "missing Android WebView submit/completed-chat proof fields",
    }


def _android_webview_source_window_artifact_status(root: Path, relative_path: str) -> dict[str, Any]:
    path = root / relative_path
    if not path.exists():
        return {
            "path": relative_path,
            "exists": False,
            "passes": False,
            "error": "missing artifact",
            "webviewFieldsPass": False,
            "sourceWindowFieldsPass": False,
        }
    try:
        data = _read_json(path)
    except json.JSONDecodeError as exc:
        return {
            "path": relative_path,
            "exists": True,
            "passes": False,
            "error": f"invalid json: {exc}",
            "webviewFieldsPass": False,
            "sourceWindowFieldsPass": False,
        }
    webview_fields_pass = _android_webview_submit_fields_pass(data)
    source_window_fields_pass = _android_webview_source_window_fields_pass(data)
    return {
        "path": relative_path,
        "exists": True,
        "passes": bool(data.get("passes") is True and webview_fields_pass and source_window_fields_pass),
        "rawPasses": data.get("passes"),
        "webviewFieldsPass": webview_fields_pass,
        "sourceWindowFieldsPass": source_window_fields_pass,
        "error": "" if source_window_fields_pass else "missing Android WebView source-window/highlight/more-context proof fields",
    }


def _android_webview_submit_fields_pass(data: dict[str, Any]) -> bool:
    checks = data.get("checks") if isinstance(data.get("checks"), dict) else {}
    required_checks = (
        "runtime",
        "devtoolsSocket",
        "devtoolsForward",
        "devtoolsTarget",
        "domReady",
        "domSubmit",
        "chatCompleted",
        "localChatStored",
        "finalAnswerReadiness",
    )
    final_state = data.get("finalState") if isinstance(data.get("finalState"), dict) else {}
    return bool(
        all(isinstance(checks.get(name), dict) and checks[name].get("passes") is True for name in required_checks)
        and final_state.get("sessionStatus") == "completed"
        and final_state.get("answerTextLength", 0) > 0
        and final_state.get("answerReadiness") == "final_answer"
        and final_state.get("writerStatus") == "completed"
    )


def _android_webview_source_window_fields_pass(data: dict[str, Any]) -> bool:
    checks = data.get("checks") if isinstance(data.get("checks"), dict) else {}
    source_window = checks.get("sourceWindow") if isinstance(checks.get("sourceWindow"), dict) else {}
    result = source_window.get("result") if isinstance(source_window.get("result"), dict) else {}
    return bool(
        source_window.get("passes") is True
        and result.get("clicked") is True
        and result.get("dialogOpen") is True
        and result.get("textLength", 0) > 0
        and result.get("highlightTextLength", 0) > 0
        and result.get("moreButtonCount", 0) >= 1
    )


def _waydroid_four_apk_artifact_status(root: Path, relative_path: str) -> dict[str, Any]:
    path = root / relative_path
    if not path.exists():
        return {
            "path": relative_path,
            "exists": False,
            "passes": False,
            "error": "missing artifact",
            "blocked": True,
            "apps": [],
        }
    try:
        data = _read_json(path)
    except json.JSONDecodeError as exc:
        return {
            "path": relative_path,
            "exists": True,
            "passes": False,
            "error": f"invalid json: {exc}",
            "blocked": True,
            "apps": [],
        }
    apps = data.get("apps") if isinstance(data.get("apps"), list) else []
    by_key = {str(item.get("key")): item for item in apps if isinstance(item, dict)}
    app_statuses = []
    missing = []
    for key in LATEST_WAYDROID_REQUIRED_APP_KEYS:
        app = by_key.get(key)
        if not app:
            missing.append(key)
            app_statuses.append({"key": key, "passes": False, "error": "missing app report"})
            continue
        runtime = app.get("runtime") if isinstance(app.get("runtime"), dict) else {}
        runtime_passes = runtime.get("passes") is True
        runtime_visual_passes = _waydroid_runtime_visual_passes(runtime)
        ui_xml = app.get("uiXml") if isinstance(app.get("uiXml"), dict) else {}
        ui_xml_passes = ui_xml.get("passes") is True
        ui_xml_content_passes = _waydroid_ui_xml_content_passes(ui_xml)
        user_path = app.get("userPath") if isinstance(app.get("userPath"), dict) else {}
        user_path_passes = user_path.get("passes") is True
        user_path_evidence_passes = _waydroid_user_path_evidence_passes(key, user_path)
        app_statuses.append(
            {
                "key": key,
                "passes": runtime_passes
                and runtime_visual_passes
                and ui_xml_passes
                and ui_xml_content_passes
                and user_path_passes
                and user_path_evidence_passes,
                "runtimePasses": runtime_passes,
                "runtimeVisualPasses": runtime_visual_passes,
                "uiXmlPasses": ui_xml_passes,
                "uiXmlContentPasses": ui_xml_content_passes,
                "userPathPasses": user_path_passes,
                "userPathEvidencePasses": user_path_evidence_passes,
            }
        )
    preflight = data.get("preflight") if isinstance(data.get("preflight"), dict) else {}
    origin_health = preflight.get("originHealth") if isinstance(preflight.get("originHealth"), dict) else {}
    origin_health_passes = origin_health.get("passes") is True
    corpus_databases = preflight.get("corpusDatabases") if isinstance(preflight.get("corpusDatabases"), dict) else {}
    corpus_databases_passes = _waydroid_corpus_databases_passes(corpus_databases)
    blocked = data.get("blocked") is True or preflight.get("blocked") is True
    preflight_ready = preflight.get("ready") is True
    fields_pass = bool(
        data.get("passes") is True
        and not blocked
        and preflight_ready
        and origin_health_passes
        and corpus_databases_passes
        and not missing
        and all(item["passes"] for item in app_statuses)
    )
    errors = []
    if data.get("passes") is not True:
        errors.append("report did not pass")
    if blocked:
        errors.append("Waydroid preflight blocked")
    if not preflight_ready:
        errors.append("Waydroid preflight not ready")
    if not origin_health_passes:
        errors.append("APK-stamped base origin health failed or missing")
    if not corpus_databases_passes:
        errors.append("shared corpus database proof failed or missing")
    if missing:
        errors.append("missing app reports: " + ", ".join(missing))
    for item in app_statuses:
        if not item["passes"]:
            errors.append(f"{item['key']} runtime/ui/user-path proof incomplete")
        if item.get("runtimeVisualPasses") is False:
            errors.append(f"{item['key']} visual screenshot proof incomplete")
        if item.get("uiXmlContentPasses") is False:
            errors.append(f"{item['key']} UI XML content proof incomplete")
        if item.get("userPathEvidencePasses") is False:
            errors.append(f"{item['key']} user-path DB/engine/citation proof incomplete")
    return {
        "path": relative_path,
        "exists": True,
        "passes": fields_pass,
        "rawPasses": data.get("passes"),
        "blocked": blocked,
        "preflightReady": preflight_ready,
        "originHealthPasses": origin_health_passes,
        "corpusDatabasesPasses": corpus_databases_passes,
        "requiredApps": list(LATEST_WAYDROID_REQUIRED_APP_KEYS),
        "apps": app_statuses,
        "error": "; ".join(errors),
    }


def _four_android_apk_verify_artifact_status(root: Path, relative_path: str) -> dict[str, Any]:
    path = root / relative_path
    if not path.exists():
        return {
            "path": relative_path,
            "exists": False,
            "passes": False,
            "error": "missing artifact",
            "apps": [],
        }
    try:
        data = _read_json(path)
    except json.JSONDecodeError as exc:
        return {
            "path": relative_path,
            "exists": True,
            "passes": False,
            "error": f"invalid json: {exc}",
            "apps": [],
        }

    apps = data.get("apps") if isinstance(data.get("apps"), list) else []
    by_key = {str(item.get("key")): item for item in apps if isinstance(item, dict)}
    app_statuses: list[dict[str, Any]] = []
    missing: list[str] = []
    shared_origins: set[str] = set()
    errors: list[str] = []
    for key, expected_application_id, expected_product in FOUR_ANDROID_APK_REQUIRED_APPS:
        app = by_key.get(key)
        if not app:
            missing.append(key)
            app_statuses.append({"key": key, "passes": False, "error": "missing APK verifier app report"})
            continue
        base_origin = str(app.get("baseOrigin") or "")
        if key != "lawkey":
            shared_origins.add(base_origin)
        checks = app.get("checks") if isinstance(app.get("checks"), dict) else {}
        check_passes = {
            name: isinstance(checks.get(name), dict) and checks[name].get("passes") is True
            for name in FOUR_ANDROID_APK_REQUIRED_CHECKS
        }
        sha256 = str(app.get("sha256") or "")
        sha256_passes = len(sha256) == 64 and all(char in "0123456789abcdef" for char in sha256.lower())
        app_passes = bool(
            app.get("passes") is True
            and app.get("applicationId") == expected_application_id
            and app.get("product") == expected_product
            and str(app.get("apkPath") or "")
            and _origin_string_passes(base_origin)
            and sha256_passes
            and all(check_passes.values())
        )
        if key == "lawkey" and base_origin.rstrip("/") != "https://lawkey.ai.kr":
            app_passes = False
            check_passes["lawkeyOrigin"] = False
        app_statuses.append(
            {
                "key": key,
                "passes": app_passes,
                "applicationId": app.get("applicationId"),
                "expectedApplicationId": expected_application_id,
                "product": app.get("product"),
                "expectedProduct": expected_product,
                "baseOrigin": base_origin,
                "sha256Passes": sha256_passes,
                "checkPasses": check_passes,
            }
        )
    shared_origin_passes = len(shared_origins) == 1 and all(_origin_string_passes(origin) for origin in shared_origins)
    fields_pass = bool(
        data.get("checked") is True
        and data.get("passes") is True
        and not missing
        and shared_origin_passes
        and all(item["passes"] for item in app_statuses)
    )
    if data.get("checked") is not True:
        errors.append("APK verifier did not mark checked=true")
    if data.get("passes") is not True:
        errors.append("APK verifier report did not pass")
    if missing:
        errors.append("missing APK app reports: " + ", ".join(missing))
    if not shared_origin_passes:
        errors.append("Islam/PsyKey/TCM APKs do not share one valid stamped origin")
    for item in app_statuses:
        if not item["passes"]:
            errors.append(f"{item['key']} APK package/signature/stamp proof incomplete")
    return {
        "path": relative_path,
        "exists": True,
        "passes": fields_pass,
        "rawPasses": data.get("passes"),
        "checked": data.get("checked"),
        "requiredApps": [item[0] for item in FOUR_ANDROID_APK_REQUIRED_APPS],
        "sharedBaseOrigin": next(iter(shared_origins)) if len(shared_origins) == 1 else "",
        "apps": app_statuses,
        "error": "; ".join(errors),
    }


def _origin_string_passes(value: str) -> bool:
    return bool(value and (value.startswith("https://") or value.startswith("http://")))


def _waydroid_runtime_visual_passes(runtime: dict[str, Any]) -> bool:
    screenshot = runtime.get("screenshot") if isinstance(runtime.get("screenshot"), dict) else {}
    visual = screenshot.get("visual") if isinstance(screenshot.get("visual"), dict) else {}
    return bool(
        screenshot.get("passes") is True
        and visual.get("passes") is True
        and visual.get("validImage") is True
        and visual.get("width", 0) > 0
        and visual.get("height", 0) > 0
        and visual.get("distinctColorCount", 0) > 1
    )


def _waydroid_ui_xml_content_passes(ui_xml: dict[str, Any]) -> bool:
    content = ui_xml.get("content") if isinstance(ui_xml.get("content"), dict) else {}
    return bool(
        ui_xml.get("passes") is True
        and content.get("passes") is True
        and content.get("validXml") is True
        and content.get("nodeCount", 0) > 0
        and content.get("crashTextDetected") is not True
    )


def _waydroid_corpus_databases_passes(corpus_databases: dict[str, Any]) -> bool:
    if corpus_databases.get("checked") is not True or corpus_databases.get("passes") is not True:
        return False
    databases = corpus_databases.get("databases") if isinstance(corpus_databases.get("databases"), list) else []
    by_product = {str(item.get("product")): item for item in databases if isinstance(item, dict)}
    for product in ("islam", "tcm", "simli"):
        item = by_product.get(product)
        if not item or item.get("passes") is not True or item.get("exists") is not True:
            return False
        checks = item.get("checks") if isinstance(item.get("checks"), dict) else {}
        if checks.get("sizeBytesPasses") is not True:
            return False
        if product in {"islam", "tcm"}:
            if (
                item.get("dbShape") != "precedents"
                or checks.get("sourceCountPasses") is not True
                or checks.get("passageMaxRowidPasses") is not True
                or checks.get("precedentMaxRowidPasses") is not True
            ):
                return False
        if product == "simli":
            if item.get("dbShape") != "documents" or checks.get("documentMaxRowidPasses") is not True:
                return False
    return True


def _waydroid_user_path_evidence_passes(key: str, user_path: dict[str, Any]) -> bool:
    if user_path.get("passes") is not True:
        return False
    if key == "lawkey":
        if user_path.get("checked") is not True:
            return False
        return _waydroid_lawkey_user_path_passes(user_path)
    return _waydroid_beta6_user_path_passes(user_path)


def _waydroid_beta6_user_path_passes(user_path: dict[str, Any]) -> bool:
    checks = user_path.get("checks") if isinstance(user_path.get("checks"), dict) else {}
    final_answer = checks.get("finalAnswerReadiness") if isinstance(checks.get("finalAnswerReadiness"), dict) else {}
    source_window = checks.get("sourceWindow") if isinstance(checks.get("sourceWindow"), dict) else {}
    source_result = source_window.get("result") if isinstance(source_window.get("result"), dict) else {}
    final_state = user_path.get("finalState") if isinstance(user_path.get("finalState"), dict) else {}
    provider = str(final_state.get("writerProvider") or "").lower()
    model = str(final_state.get("writerModel") or "").lower()
    return bool(
        final_state.get("sessionStatus") == "completed"
        and final_state.get("answerTextLength", 0) > 0
        and final_state.get("answerReadiness") == "final_answer"
        and final_state.get("writerStatus") == "completed"
        and final_state.get("writerMode") == "llm_writer"
        and provider
        and ("lawkey" in provider or "gemini" in provider)
        and "gemma" in model
        and final_state.get("writerCacheHit") is False
        and final_state.get("sourceCount", 0) > 0
        and final_state.get("claimCardCount", 0) > 0
        and final_state.get("citedClaimCardCount", 0) > 0
        and final_state.get("passageWindowCount", 0) > 0
        and final_answer.get("passes") is True
        and final_answer.get("answerReadiness") == "final_answer"
        and final_answer.get("writerStatus") == "completed"
        and source_window.get("passes") is True
        and source_result.get("clicked") is True
        and source_result.get("dialogOpen") is True
        and source_result.get("textLength", 0) > 0
        and source_result.get("highlightTextLength", 0) > 0
        and source_result.get("moreButtonCount", 0) >= 1
    )


def _waydroid_lawkey_user_path_passes(user_path: dict[str, Any]) -> bool:
    submit = user_path.get("submit") if isinstance(user_path.get("submit"), dict) else {}
    final_state = user_path.get("finalState") if isinstance(user_path.get("finalState"), dict) else {}
    source_detail = user_path.get("sourceDetail") if isinstance(user_path.get("sourceDetail"), dict) else {}
    selected_count = max(
        int(final_state.get("selectedPrecedents") or 0),
        int(final_state.get("selectedPrecedentCount") or 0),
    )
    return bool(
        submit.get("submitted") is True
        and final_state.get("state") == "completed"
        and final_state.get("answerLength", 0) > 1000
        and selected_count > 0
        and final_state.get("hasCaseCitation") is True
        and source_detail.get("clicked") is True
        and source_detail.get("hasDetail") is True
        and source_detail.get("hasQuote") is True
        and source_detail.get("hasHighlight") is True
    )


def _audit_file_status(root: Path) -> dict[str, Any]:
    files = []
    for relative_path in AUDIT_FILES:
        path = root / relative_path
        files.append({"path": relative_path, "exists": path.exists()})
    return {
        "passes": all(item["exists"] for item in files),
        "files": files,
        "message": "Completion and requirements audit files must exist.",
    }


def _docs_reference_artifacts(root: Path, artifacts: tuple[str, ...]) -> dict[str, Any]:
    docs = {relative_path: (root / relative_path).read_text(encoding="utf-8") if (root / relative_path).exists() else "" for relative_path in AUDIT_FILES}
    missing = []
    for artifact in artifacts:
        for doc_path, text in docs.items():
            if artifact not in text:
                missing.append({"artifact": artifact, "doc": doc_path})
    return {
        "passes": not missing,
        "missing": missing,
        "message": "Audit documents must explicitly reference every artifact used by the completion verdict.",
    }


def _latest_ui_status(root: Path) -> dict[str, Any]:
    artifacts = [_artifact_status(root, path) for path in LATEST_UI_PASS_ARTIFACTS]
    bad = [item for item in artifacts if item["passes"] is not True]
    return {
        "passes": not bad,
        "artifacts": artifacts,
        "message": "Latest UI language/design/app-shell tranche must remain green.",
    }


def _latest_security_status(root: Path) -> dict[str, Any]:
    artifacts = [_artifact_status(root, path) for path in LATEST_SECURITY_PASS_ARTIFACTS]
    bad = [item for item in artifacts if item["passes"] is not True]
    return {
        "passes": not bad,
        "artifacts": artifacts,
        "message": "Latest account-grade job ownership tranche must remain green.",
    }


def _latest_native_android_status(root: Path) -> dict[str, Any]:
    artifacts = [
        _android_build_artifact_status(root, LATEST_NATIVE_ANDROID_BUILD_ARTIFACT),
    ]
    for product, runtime_artifact, webview_artifact in LATEST_NATIVE_ANDROID_WEBVIEW_PRODUCTS:
        runtime_status = _android_runtime_artifact_status(root, runtime_artifact)
        runtime_status["product"] = product
        webview_status = _android_webview_submit_artifact_status(root, webview_artifact)
        webview_status["product"] = product
        webview_status["proof"] = "final-answer"
        artifacts.extend([runtime_status, webview_status])
    for product, runtime_artifact, source_window_artifact in LATEST_NATIVE_ANDROID_SOURCE_WINDOW_PRODUCTS:
        runtime_status = _android_runtime_artifact_status(root, runtime_artifact)
        runtime_status["product"] = product
        runtime_status["proof"] = "source-window-runtime"
        source_window_status = _android_webview_source_window_artifact_status(root, source_window_artifact)
        source_window_status["product"] = product
        source_window_status["proof"] = "source-window"
        artifacts.extend([runtime_status, source_window_status])
    bad = [item for item in artifacts if item["passes"] is not True]
    return {
        "passes": not bad,
        "artifacts": artifacts,
        "message": "Latest Android build/runtime/WebView final-answer and source-window matrix artifacts must remain green.",
    }


def _latest_waydroid_four_apk_status(root: Path) -> dict[str, Any]:
    artifact = _waydroid_four_apk_artifact_status(root, LATEST_WAYDROID_FOUR_APK_ARTIFACT)
    return {
        "passes": artifact["passes"] is True,
        "artifact": artifact,
        "message": "Latest Waydroid four-APK install/runtime/UI XML/user-path proof must pass for Lawkey, PsyKey, Islam, and TCM.",
    }


def _latest_four_android_apk_preflight_status(root: Path, relative_path: str = LATEST_FOUR_ANDROID_APK_VERIFY_ARTIFACT) -> dict[str, Any]:
    artifact = _four_android_apk_verify_artifact_status(root, relative_path)
    return {
        "passes": artifact["passes"] is True,
        "artifact": artifact,
        "apps": artifact.get("apps", []),
        "message": "Latest four Android APK package/signature/product/origin pre-install proof must pass.",
    }


def _known_blocker_status(root: Path) -> dict[str, Any]:
    artifacts = [_artifact_status(root, path) for path in KNOWN_BLOCKING_ARTIFACTS]
    unresolved = []
    for item in artifacts:
        reason = KNOWN_BLOCKING_ARTIFACTS[item["path"]]
        if item["passes"] is not True:
            unresolved.append({"path": item["path"], "reason": reason, "passes": item["passes"], "exists": item["exists"]})
    return {
        "passes": not unresolved,
        "artifacts": artifacts,
        "unresolved": unresolved,
        "message": "Known blocker artifacts must pass before the active objective can be marked achieved.",
    }


def build_report(repo_root: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    checked_artifacts = (
        *LATEST_UI_PASS_ARTIFACTS,
        *LATEST_SECURITY_PASS_ARTIFACTS,
        *LATEST_NATIVE_ANDROID_PASS_ARTIFACTS,
        LATEST_WAYDROID_FOUR_APK_ARTIFACT,
        *KNOWN_BLOCKING_ARTIFACTS.keys(),
    )
    checks = {
        "auditFilesExist": _audit_file_status(root),
        "latestUiLanguageTranche": _latest_ui_status(root),
        "latestAccountAuthTranche": _latest_security_status(root),
        "latestAndroidNativeTranche": _latest_native_android_status(root),
        "latestWaydroidFourApkTranche": _latest_waydroid_four_apk_status(root),
        "knownBlockingArtifacts": _known_blocker_status(root),
        "auditDocsReferenceArtifacts": _docs_reference_artifacts(root, checked_artifacts),
    }
    remaining_blockers = [item["reason"] for item in checks["knownBlockingArtifacts"]["unresolved"]]
    if checks["latestWaydroidFourApkTranche"]["passes"] is not True:
        remaining_blockers.append(WAYDROID_FOUR_APK_BLOCKER)
    passes = all(check["passes"] for check in checks.values())
    return {
        "passes": passes,
        "verdict": "achieved" if passes else "not_achieved",
        "repoRoot": str(root),
        "checkedArtifacts": list(checked_artifacts),
        "remainingBlockers": remaining_blockers,
        "checks": checks,
    }


def build_waydroid_four_apk_goal_report(
    repo_root: Path,
    *,
    apk_verify_report: str = LATEST_FOUR_ANDROID_APK_VERIFY_ARTIFACT,
    waydroid_report: str = LATEST_WAYDROID_FOUR_APK_ARTIFACT,
) -> dict[str, Any]:
    root = repo_root.resolve()
    checks = {
        "fourAndroidApkPreflight": _latest_four_android_apk_preflight_status(root, apk_verify_report),
        "latestWaydroidFourApkTranche": {
            **_latest_waydroid_four_apk_status(root),
            "artifact": _waydroid_four_apk_artifact_status(root, waydroid_report),
        },
    }
    checks["latestWaydroidFourApkTranche"]["passes"] = checks["latestWaydroidFourApkTranche"]["artifact"]["passes"] is True

    remaining_blockers: list[str] = []
    if checks["fourAndroidApkPreflight"]["passes"] is not True:
        remaining_blockers.append(FOUR_ANDROID_APK_VERIFY_BLOCKER)
    if checks["latestWaydroidFourApkTranche"]["passes"] is not True:
        remaining_blockers.append(WAYDROID_FOUR_APK_BLOCKER)
    passes = all(check["passes"] for check in checks.values())
    return {
        "scope": "waydroid-four-apk-goal",
        "passes": passes,
        "verdict": "achieved" if passes else "not_achieved",
        "repoRoot": str(root),
        "checkedArtifacts": [apk_verify_report, waydroid_report],
        "remainingBlockers": remaining_blockers,
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--scope", choices=("full", "waydroid-four-apk-goal"), default="full")
    parser.add_argument("--apk-verify-report", default=LATEST_FOUR_ANDROID_APK_VERIFY_ARTIFACT)
    parser.add_argument("--waydroid-report", default=LATEST_WAYDROID_FOUR_APK_ARTIFACT)
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    parser.add_argument("--output", type=Path, help="Write JSON report to this file.")
    args = parser.parse_args(argv)
    if args.scope == "waydroid-four-apk-goal":
        report = build_waydroid_four_apk_goal_report(
            args.repo_root,
            apk_verify_report=args.apk_verify_report,
            waydroid_report=args.waydroid_report,
        )
    else:
        report = build_report(args.repo_root)
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    if args.json:
        print(encoded)
    else:
        print(("PASS" if report["passes"] else "FAIL") + " completion audit")
        for blocker in report["remainingBlockers"]:
            print(f"blocker: {blocker}")
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
