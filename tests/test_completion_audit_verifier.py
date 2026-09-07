import importlib.util
import json
from pathlib import Path


def _load_verifier():
    path = Path("tools/verify_completion_audit.py")
    spec = importlib.util.spec_from_file_location("verify_completion_audit", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


ANDROID_FINAL_ANSWER_ARTIFACTS = [
    "20260508_android_webview_final_answer_islam_runtime.json",
    "20260508_android_webview_final_answer_islam.json",
    "20260508_android_webview_final_answer_tcm_retry2_runtime.json",
    "20260508_android_webview_final_answer_tcm_retry2.json",
    "20260509_android_webview_final_answer_simli_runtime.json",
    "20260509_android_webview_final_answer_simli.json",
]

ANDROID_SOURCE_WINDOW_ARTIFACTS = [
    "20260509_android_webview_source_window_islam_runtime.json",
    "20260509_android_webview_source_window_islam_retry.json",
    "20260509_android_webview_source_window_tcm_runtime.json",
    "20260509_android_webview_source_window_tcm_retry.json",
    "20260509_android_webview_source_window_simli_runtime.json",
    "20260509_android_webview_source_window_simli.json",
]

COLD_ISLAM_BUDGET_ARTIFACT = "app_path_budget_matrix_islam_selector_recovery_parallel_cold_120s_30s_20260509.json"
WAYDROID_FOUR_APK_ARTIFACT = "waydroid-four-apks-20260520-current/report.json"
FOUR_ANDROID_APK_VERIFY_ARTIFACT = "apk/four-android-apks-20260520-current-verify.json"


def _write_run_json(root: Path, name: str, data: dict) -> None:
    path = root / "runs" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) + "\n", encoding="utf-8")


def _write_android_runtime(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "passes": True,
                "apk": {"exists": True, "sizeBytes": 12},
                "device": {"passes": True},
                "install": {"passes": True},
                "launch": {"passes": True},
                "process": {"passes": True},
                "activity": {"passes": True},
                "screenshot": {"passes": True},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_android_webview(path: Path, *, final_answer: bool = True, completed: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "passes": True,
                "checks": {
                    "runtime": {"passes": True},
                    "devtoolsSocket": {"passes": True},
                    "devtoolsForward": {"passes": True},
                    "devtoolsTarget": {"passes": True},
                    "domReady": {"passes": True},
                    "domSubmit": {"passes": True},
                    "chatCompleted": {"passes": completed},
                    "localChatStored": {"passes": True},
                    "finalAnswerReadiness": {"passes": final_answer},
                },
                "finalState": {
                    "sessionStatus": "completed" if completed else "running",
                    "answerTextLength": 100 if completed else 0,
                    "sourceCount": 4 if completed else 0,
                    "answerReadiness": "final_answer" if final_answer else "evidence_selected_writer_required",
                    "writerStatus": "completed" if final_answer else "requires_llm",
                    "writerMode": "llm_writer" if final_answer else "",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_android_source_window(path: Path, *, source_window: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "passes": True,
        "checks": {
            "runtime": {"passes": True},
            "devtoolsSocket": {"passes": True},
            "devtoolsForward": {"passes": True},
            "devtoolsTarget": {"passes": True},
            "domReady": {"passes": True},
            "domSubmit": {"passes": True},
            "chatCompleted": {"passes": True},
            "localChatStored": {"passes": True},
            "finalAnswerReadiness": {"passes": True},
            "sourceWindow": {
                "passes": source_window,
                "result": {
                    "clicked": True,
                    "dialogOpen": True,
                    "textLength": 120,
                    "highlightTextLength": 12 if source_window else 0,
                    "moreButtonCount": 2,
                },
            },
        },
        "finalState": {
            "sessionStatus": "completed",
            "answerTextLength": 100,
            "sourceCount": 4,
            "answerReadiness": "final_answer",
            "writerStatus": "completed",
            "writerMode": "llm_writer",
        },
    }
    path.write_text(json.dumps(data) + "\n", encoding="utf-8")


def _write_waydroid_four_apk_report(
    path: Path,
    *,
    blocked: bool = False,
    missing_app: str = "",
    origin_health: bool = True,
    missing_visual: bool = False,
    missing_ui_content: bool = False,
    missing_user_path_evidence: bool = False,
    missing_corpus_db_evidence: bool = False,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    apps = []
    for key in ("islam", "psykey", "tcm", "lawkey"):
        if key == missing_app:
            continue
        user_path = {"checked": True, "passes": True} if missing_user_path_evidence else _waydroid_user_path_fixture(key)
        apps.append(
            {
                "key": key,
                "runtime": {
                    "passes": True,
                    "screenshot": {}
                    if missing_visual
                    else {
                        "passes": True,
                        "visual": {
                            "passes": True,
                            "validImage": True,
                            "width": 360,
                            "height": 740,
                            "distinctColorCount": 24,
                        },
                    },
                },
                "uiXml": {"passes": True}
                if missing_ui_content
                else {
                    "passes": True,
                    "content": {
                        "passes": True,
                        "validXml": True,
                        "nodeCount": 5,
                        "hasTextOrDescription": True,
                        "crashTextDetected": False,
                    },
                },
                "userPath": user_path,
            }
        )
    path.write_text(
        json.dumps(
            {
                "passes": not blocked and not missing_app,
                "blocked": blocked,
                "preflight": {
                    "ready": not blocked,
                    "blocked": blocked,
                    "blockedReasons": ["host setup"] if blocked else [],
                    "originHealth": {
                        "checked": True,
                        "passes": origin_health,
                        "origins": [
                            {"baseOrigin": "https://certificates-van-eve-knowledge.trycloudflare.com", "passes": origin_health},
                            {"baseOrigin": "https://lawkey.ai.kr", "passes": origin_health},
                        ],
                    },
                    "corpusDatabases": {}
                    if missing_corpus_db_evidence
                    else {
                        "checked": True,
                        "passes": True,
                        "databases": [
                            {
                                "product": "islam",
                                "exists": True,
                                "passes": True,
                                "dbShape": "precedents",
                                "sizeBytes": 2_000_000_000,
                                "checks": {
                                    "sizeBytesPasses": True,
                                    "sourceCount": 41,
                                    "sourceCountPasses": True,
                                    "passageMaxRowid": 178293,
                                    "passageMaxRowidPasses": True,
                                    "precedentMaxRowid": 178163,
                                    "precedentMaxRowidPasses": True,
                                },
                            },
                            {
                                "product": "tcm",
                                "exists": True,
                                "passes": True,
                                "dbShape": "precedents",
                                "sizeBytes": 17_000_000_000,
                                "checks": {
                                    "sizeBytesPasses": True,
                                    "sourceCount": 52,
                                    "sourceCountPasses": True,
                                    "passageMaxRowid": 2_286_869,
                                    "passageMaxRowidPasses": True,
                                    "precedentMaxRowid": 2_286_869,
                                    "precedentMaxRowidPasses": True,
                                },
                            },
                            {
                                "product": "simli",
                                "exists": True,
                                "passes": True,
                                "dbShape": "documents",
                                "sizeBytes": 12_000_000_000,
                                "checks": {
                                    "sizeBytesPasses": True,
                                    "documentMaxRowid": 690770,
                                    "documentMaxRowidPasses": True,
                                },
                            },
                        ],
                        "externalProducts": [{"key": "lawkey", "product": "lawkey", "reason": "external verifier"}],
                    },
                },
                "apps": apps,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_four_android_apk_verify_report(
    path: Path,
    *,
    missing_app: str = "",
    failing_app: str = "",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    specs = {
        "islam": ("ai.bunjum.hikmah", "islam", "https://fresh.example", "a"),
        "psykey": ("ai.bunjum.psykey", "simli", "https://fresh.example", "b"),
        "tcm": ("ai.bunjum.hanui", "tcm", "https://fresh.example", "c"),
        "lawkey": ("ai.bunjum.lawkey", "lawkey", "https://lawkey.ai.kr", "d"),
    }
    apps = []
    for key, (application_id, product, base_origin, sha_char) in specs.items():
        if key == missing_app:
            continue
        passes = key != failing_app
        apps.append(
            {
                "key": key,
                "applicationId": application_id,
                "product": product,
                "baseOrigin": base_origin,
                "apkPath": f"/tmp/{key}.apk",
                "sha256": sha_char * 64,
                "passes": passes,
                "checks": {
                    "zipEntries": {"passes": passes, "exists": True, "size": 1234},
                    "dexStamps": {"passes": passes, "missing": [] if passes else ["baseOrigin"]},
                    "apksigner": {"passes": passes},
                    "aaptPackage": {"passes": passes, "matched": passes},
                },
            }
        )
    path.write_text(
        json.dumps({"checked": True, "passes": not missing_app and not failing_app, "apps": apps}) + "\n",
        encoding="utf-8",
    )


def _waydroid_user_path_fixture(key: str) -> dict:
    if key == "lawkey":
        return {
            "checked": True,
            "passes": True,
            "submit": {"submitted": True, "jobId": "job-lawkey"},
            "finalState": {
                "state": "completed",
                "answerLength": 5205,
                "selectedPrecedents": 61,
                "selectedPrecedentCount": 100,
                "completedChunks": 6,
                "totalChunks": 6,
                "hasCaseCitation": True,
            },
            "sourceDetail": {
                "clicked": True,
                "hasDetail": True,
                "hasQuote": True,
                "hasHighlight": True,
            },
        }
    return {
        "checked": True,
        "passes": True,
        "checks": {
            "finalAnswerReadiness": {
                "passes": True,
                "answerReadiness": "final_answer",
                "writerStatus": "completed",
                "writerMode": "llm_writer",
            },
            "sourceWindow": {
                "passes": True,
                "result": {
                    "clicked": True,
                    "dialogOpen": True,
                    "textLength": 700,
                    "highlightTextLength": 55,
                    "moreButtonCount": 2,
                },
            },
        },
        "finalState": {
            "sessionStatus": "completed",
            "answerTextLength": 3200,
            "answerReadiness": "final_answer",
            "writerStatus": "completed",
            "writerMode": "llm_writer",
            "writerProvider": "lawkey_gemini_generate_content",
            "writerModel": "gemma-4-26b-a4b-it",
            "writerCacheHit": False,
            "sourceCount": 100,
            "claimCardCount": 18,
            "citedClaimCardCount": 8,
            "passageWindowCount": 18,
        },
    }


def test_waydroid_beta6_user_path_evidence_accepts_detailed_checked_subproof_without_top_level_checked():
    verifier = _load_verifier()
    user_path = _waydroid_user_path_fixture("islam")
    user_path.pop("checked")

    assert verifier._waydroid_user_path_evidence_passes("islam", user_path) is True


def test_completion_audit_verifier_reports_current_goal_not_achieved_but_evidence_current():
    verifier = _load_verifier()

    report = verifier.build_report(Path("."))

    assert report["passes"] is False
    assert report["verdict"] == "not_achieved"
    assert report["checks"]["auditFilesExist"]["passes"] is True
    assert report["checks"]["latestUiLanguageTranche"]["passes"] is True
    assert report["checks"]["latestAccountAuthTranche"]["passes"] is True
    assert report["checks"]["latestAndroidNativeTranche"]["passes"] is True
    assert report["checks"]["latestWaydroidFourApkTranche"]["passes"] is True
    assert "Waydroid four-APK install/runtime/user-path" not in report["remainingBlockers"]
    android_paths = " ".join(item["path"] for item in report["checks"]["latestAndroidNativeTranche"]["artifacts"])
    assert "native_build_smoke_android_debug_webview_20260508.json" in android_paths
    assert "20260508_android_webview_final_answer_islam.json" in android_paths
    assert "20260508_android_webview_final_answer_tcm_retry2.json" in android_paths
    assert "20260509_android_webview_final_answer_simli.json" in android_paths
    assert "20260509_android_webview_source_window_islam_retry.json" in android_paths
    assert "20260509_android_webview_source_window_tcm_retry.json" in android_paths
    assert "20260509_android_webview_source_window_simli.json" in android_paths
    assert f"runs/{COLD_ISLAM_BUDGET_ARTIFACT}" in report["checkedArtifacts"]
    assert f"runs/{WAYDROID_FOUR_APK_ARTIFACT}" in report["checkedArtifacts"]
    assert report["checks"]["knownBlockingArtifacts"]["passes"] is False
    assert report["checks"]["auditDocsReferenceArtifacts"]["passes"] is True
    assert "full-answer latency" in " ".join(report["remainingBlockers"])
    assert "account-grade auth" not in " ".join(report["remainingBlockers"])


def test_completion_audit_verifier_accepts_fixture_when_no_blocking_artifacts_remain(tmp_path):
    verifier = _load_verifier()
    (tmp_path / "tasks").mkdir()
    (tmp_path / "runs").mkdir()
    pass_artifacts = [
        "low_end_runtime_i18n_language_shells_v43_20260508.json",
        "app_parity_i18n_language_shells_v43_20260508.json",
        "low_bandwidth_i18n_language_shells_v43_20260508.json",
        "browser_runtime_i18n_language_shells_v43_20260508.json",
        "tunnel_health_i18n_language_shells_v43_20260508.json",
        "account_auth_readiness_20260508.json",
        "app_parity_account_subject_binding_20260508.json",
        "low_end_runtime_account_subject_binding_20260508.json",
        "low_bandwidth_account_subject_binding_20260508.json",
        "native_build_smoke_android_debug_webview_20260508.json",
        *ANDROID_FINAL_ANSWER_ARTIFACTS,
        *ANDROID_SOURCE_WINDOW_ARTIFACTS,
        WAYDROID_FOUR_APK_ARTIFACT,
    ]
    blocker_artifacts = [
        "app_path_budget_matrix_browser_submit_120s_required_20260508.json",
        "app_path_budget_matrix_engine_stage_fresh_islam_simli_120s_30s_20260508.json",
        COLD_ISLAM_BUDGET_ARTIFACT,
        "native_build_smoke_android_debug_webview_20260508.json",
    ]
    for name in pass_artifacts + blocker_artifacts:
        _write_run_json(tmp_path, name, {"passes": True})
    (tmp_path / "runs" / "native_build_smoke_android_debug_webview_20260508.json").write_text(
        json.dumps(
            {
                "passes": True,
                "android": {"build": {"passes": True, "apk": {"exists": True, "sizeBytes": 12, "manifestAssetSynced": True}}},
                "ios": {"build": {"passes": True}},
                "nativeParity": {"passes": True},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    for name in ANDROID_FINAL_ANSWER_ARTIFACTS + ANDROID_SOURCE_WINDOW_ARTIFACTS:
        if name.endswith("_runtime.json"):
            _write_android_runtime(tmp_path / "runs" / name)
        elif "source_window" in name:
            _write_android_source_window(tmp_path / "runs" / name)
        else:
            _write_android_webview(tmp_path / "runs" / name)
    _write_waydroid_four_apk_report(tmp_path / "runs" / WAYDROID_FOUR_APK_ARTIFACT)
    audit_text = "\n".join(f"runs/{name}" for name in pass_artifacts + blocker_artifacts)
    (tmp_path / "tasks" / "completion-audit-2026-05-08.md").write_text(audit_text, encoding="utf-8")
    (tmp_path / "tasks" / "requirements-audit.md").write_text(audit_text, encoding="utf-8")

    report = verifier.build_report(tmp_path)

    assert report["passes"] is True, json.dumps(report, indent=2)
    assert report["verdict"] == "achieved"
    assert report["checks"]["latestWaydroidFourApkTranche"]["passes"] is True
    assert report["remainingBlockers"] == []


def test_completion_audit_verifier_rejects_blocked_waydroid_four_apk_report(tmp_path):
    verifier = _load_verifier()
    (tmp_path / "tasks").mkdir()
    (tmp_path / "runs").mkdir()
    pass_artifacts = [
        "low_end_runtime_i18n_language_shells_v43_20260508.json",
        "app_parity_i18n_language_shells_v43_20260508.json",
        "low_bandwidth_i18n_language_shells_v43_20260508.json",
        "browser_runtime_i18n_language_shells_v43_20260508.json",
        "tunnel_health_i18n_language_shells_v43_20260508.json",
        "account_auth_readiness_20260508.json",
        "app_parity_account_subject_binding_20260508.json",
        "low_end_runtime_account_subject_binding_20260508.json",
        "low_bandwidth_account_subject_binding_20260508.json",
        "native_build_smoke_android_debug_webview_20260508.json",
        *ANDROID_FINAL_ANSWER_ARTIFACTS,
        *ANDROID_SOURCE_WINDOW_ARTIFACTS,
        WAYDROID_FOUR_APK_ARTIFACT,
    ]
    blocker_artifacts = [
        "app_path_budget_matrix_browser_submit_120s_required_20260508.json",
        "app_path_budget_matrix_engine_stage_fresh_islam_simli_120s_30s_20260508.json",
        COLD_ISLAM_BUDGET_ARTIFACT,
        "native_build_smoke_android_debug_webview_20260508.json",
    ]
    for name in pass_artifacts + blocker_artifacts:
        _write_run_json(tmp_path, name, {"passes": True})
    (tmp_path / "runs" / "native_build_smoke_android_debug_webview_20260508.json").write_text(
        json.dumps({"android": {"build": {"passes": True, "apk": {"exists": True, "sizeBytes": 12, "manifestAssetSynced": True}}}, "passes": True})
        + "\n",
        encoding="utf-8",
    )
    for name in ANDROID_FINAL_ANSWER_ARTIFACTS + ANDROID_SOURCE_WINDOW_ARTIFACTS:
        if name.endswith("_runtime.json"):
            _write_android_runtime(tmp_path / "runs" / name)
        elif "source_window" in name:
            _write_android_source_window(tmp_path / "runs" / name)
        else:
            _write_android_webview(tmp_path / "runs" / name)
    _write_waydroid_four_apk_report(tmp_path / "runs" / WAYDROID_FOUR_APK_ARTIFACT, blocked=True)
    audit_text = "\n".join(f"runs/{name}" for name in pass_artifacts + blocker_artifacts)
    (tmp_path / "tasks" / "completion-audit-2026-05-08.md").write_text(audit_text, encoding="utf-8")
    (tmp_path / "tasks" / "requirements-audit.md").write_text(audit_text, encoding="utf-8")

    report = verifier.build_report(tmp_path)

    assert report["passes"] is False
    assert report["checks"]["latestWaydroidFourApkTranche"]["passes"] is False
    assert "Waydroid four-APK install/runtime/user-path" in report["remainingBlockers"]


def test_completion_audit_verifier_rejects_waydroid_report_without_origin_health(tmp_path):
    verifier = _load_verifier()
    (tmp_path / "tasks").mkdir()
    (tmp_path / "runs").mkdir()
    pass_artifacts = [
        "low_end_runtime_i18n_language_shells_v43_20260508.json",
        "app_parity_i18n_language_shells_v43_20260508.json",
        "low_bandwidth_i18n_language_shells_v43_20260508.json",
        "browser_runtime_i18n_language_shells_v43_20260508.json",
        "tunnel_health_i18n_language_shells_v43_20260508.json",
        "account_auth_readiness_20260508.json",
        "app_parity_account_subject_binding_20260508.json",
        "low_end_runtime_account_subject_binding_20260508.json",
        "low_bandwidth_account_subject_binding_20260508.json",
        "native_build_smoke_android_debug_webview_20260508.json",
        *ANDROID_FINAL_ANSWER_ARTIFACTS,
        *ANDROID_SOURCE_WINDOW_ARTIFACTS,
        WAYDROID_FOUR_APK_ARTIFACT,
    ]
    blocker_artifacts = [
        "app_path_budget_matrix_browser_submit_120s_required_20260508.json",
        "app_path_budget_matrix_engine_stage_fresh_islam_simli_120s_30s_20260508.json",
        COLD_ISLAM_BUDGET_ARTIFACT,
        "native_build_smoke_android_debug_webview_20260508.json",
    ]
    for name in pass_artifacts + blocker_artifacts:
        _write_run_json(tmp_path, name, {"passes": True})
    _write_run_json(
        tmp_path,
        "native_build_smoke_android_debug_webview_20260508.json",
        {
            "passes": True,
            "android": {"build": {"passes": True, "apk": {"exists": True, "sizeBytes": 12, "manifestAssetSynced": True}}},
        },
    )
    for name in ANDROID_FINAL_ANSWER_ARTIFACTS + ANDROID_SOURCE_WINDOW_ARTIFACTS:
        if name.endswith("_runtime.json"):
            _write_android_runtime(tmp_path / "runs" / name)
        elif "source_window" in name:
            _write_android_source_window(tmp_path / "runs" / name)
        else:
            _write_android_webview(tmp_path / "runs" / name)
    _write_waydroid_four_apk_report(tmp_path / "runs" / WAYDROID_FOUR_APK_ARTIFACT, origin_health=False)
    audit_text = "\n".join(f"runs/{name}" for name in pass_artifacts + blocker_artifacts)
    (tmp_path / "tasks" / "completion-audit-2026-05-08.md").write_text(audit_text, encoding="utf-8")
    (tmp_path / "tasks" / "requirements-audit.md").write_text(audit_text, encoding="utf-8")

    report = verifier.build_report(tmp_path)

    assert report["passes"] is False
    waydroid = report["checks"]["latestWaydroidFourApkTranche"]["artifact"]
    assert waydroid["originHealthPasses"] is False


def test_completion_audit_verifier_rejects_waydroid_report_without_visual_screenshot_proof(tmp_path):
    verifier = _load_verifier()
    (tmp_path / "tasks").mkdir()
    (tmp_path / "runs").mkdir()
    pass_artifacts = [
        "low_end_runtime_i18n_language_shells_v43_20260508.json",
        "app_parity_i18n_language_shells_v43_20260508.json",
        "low_bandwidth_i18n_language_shells_v43_20260508.json",
        "browser_runtime_i18n_language_shells_v43_20260508.json",
        "tunnel_health_i18n_language_shells_v43_20260508.json",
        "account_auth_readiness_20260508.json",
        "app_parity_account_subject_binding_20260508.json",
        "low_end_runtime_account_subject_binding_20260508.json",
        "low_bandwidth_account_subject_binding_20260508.json",
        "native_build_smoke_android_debug_webview_20260508.json",
        *ANDROID_FINAL_ANSWER_ARTIFACTS,
        *ANDROID_SOURCE_WINDOW_ARTIFACTS,
        WAYDROID_FOUR_APK_ARTIFACT,
    ]
    blocker_artifacts = [
        "app_path_budget_matrix_browser_submit_120s_required_20260508.json",
        "app_path_budget_matrix_engine_stage_fresh_islam_simli_120s_30s_20260508.json",
        COLD_ISLAM_BUDGET_ARTIFACT,
        "native_build_smoke_android_debug_webview_20260508.json",
    ]
    for name in pass_artifacts + blocker_artifacts:
        _write_run_json(tmp_path, name, {"passes": True})
    _write_run_json(
        tmp_path,
        "native_build_smoke_android_debug_webview_20260508.json",
        {
            "passes": True,
            "android": {"build": {"passes": True, "apk": {"exists": True, "sizeBytes": 12, "manifestAssetSynced": True}}},
        },
    )
    for name in ANDROID_FINAL_ANSWER_ARTIFACTS + ANDROID_SOURCE_WINDOW_ARTIFACTS:
        if name.endswith("_runtime.json"):
            _write_android_runtime(tmp_path / "runs" / name)
        elif "source_window" in name:
            _write_android_source_window(tmp_path / "runs" / name)
        else:
            _write_android_webview(tmp_path / "runs" / name)
    _write_waydroid_four_apk_report(tmp_path / "runs" / WAYDROID_FOUR_APK_ARTIFACT, missing_visual=True)
    audit_text = "\n".join(f"runs/{name}" for name in pass_artifacts + blocker_artifacts)
    (tmp_path / "tasks" / "completion-audit-2026-05-08.md").write_text(audit_text, encoding="utf-8")
    (tmp_path / "tasks" / "requirements-audit.md").write_text(audit_text, encoding="utf-8")

    report = verifier.build_report(tmp_path)

    waydroid = report["checks"]["latestWaydroidFourApkTranche"]["artifact"]
    assert report["checks"]["latestWaydroidFourApkTranche"]["passes"] is False
    assert waydroid["apps"][0]["runtimeVisualPasses"] is False
    assert "visual screenshot proof incomplete" in waydroid["error"]


def test_completion_audit_verifier_rejects_waydroid_report_without_ui_xml_content_proof(tmp_path):
    verifier = _load_verifier()
    (tmp_path / "tasks").mkdir()
    (tmp_path / "runs").mkdir()
    pass_artifacts = [
        "low_end_runtime_i18n_language_shells_v43_20260508.json",
        "app_parity_i18n_language_shells_v43_20260508.json",
        "low_bandwidth_i18n_language_shells_v43_20260508.json",
        "browser_runtime_i18n_language_shells_v43_20260508.json",
        "tunnel_health_i18n_language_shells_v43_20260508.json",
        "account_auth_readiness_20260508.json",
        "app_parity_account_subject_binding_20260508.json",
        "low_end_runtime_account_subject_binding_20260508.json",
        "low_bandwidth_account_subject_binding_20260508.json",
        "native_build_smoke_android_debug_webview_20260508.json",
        *ANDROID_FINAL_ANSWER_ARTIFACTS,
        *ANDROID_SOURCE_WINDOW_ARTIFACTS,
        WAYDROID_FOUR_APK_ARTIFACT,
    ]
    blocker_artifacts = [
        "app_path_budget_matrix_browser_submit_120s_required_20260508.json",
        "app_path_budget_matrix_engine_stage_fresh_islam_simli_120s_30s_20260508.json",
        COLD_ISLAM_BUDGET_ARTIFACT,
        "native_build_smoke_android_debug_webview_20260508.json",
    ]
    for name in pass_artifacts + blocker_artifacts:
        _write_run_json(tmp_path, name, {"passes": True})
    _write_run_json(
        tmp_path,
        "native_build_smoke_android_debug_webview_20260508.json",
        {
            "passes": True,
            "android": {"build": {"passes": True, "apk": {"exists": True, "sizeBytes": 12, "manifestAssetSynced": True}}},
        },
    )
    for name in ANDROID_FINAL_ANSWER_ARTIFACTS + ANDROID_SOURCE_WINDOW_ARTIFACTS:
        if name.endswith("_runtime.json"):
            _write_android_runtime(tmp_path / "runs" / name)
        elif "source_window" in name:
            _write_android_source_window(tmp_path / "runs" / name)
        else:
            _write_android_webview(tmp_path / "runs" / name)
    _write_waydroid_four_apk_report(tmp_path / "runs" / WAYDROID_FOUR_APK_ARTIFACT, missing_ui_content=True)
    audit_text = "\n".join(f"runs/{name}" for name in pass_artifacts + blocker_artifacts)
    (tmp_path / "tasks" / "completion-audit-2026-05-08.md").write_text(audit_text, encoding="utf-8")
    (tmp_path / "tasks" / "requirements-audit.md").write_text(audit_text, encoding="utf-8")

    report = verifier.build_report(tmp_path)

    waydroid = report["checks"]["latestWaydroidFourApkTranche"]["artifact"]
    assert report["checks"]["latestWaydroidFourApkTranche"]["passes"] is False
    assert waydroid["apps"][0]["uiXmlContentPasses"] is False
    assert "UI XML content proof incomplete" in waydroid["error"]


def test_completion_audit_verifier_rejects_waydroid_report_without_user_path_db_engine_citation_proof(tmp_path):
    verifier = _load_verifier()
    (tmp_path / "tasks").mkdir()
    (tmp_path / "runs").mkdir()
    pass_artifacts = [
        "low_end_runtime_i18n_language_shells_v43_20260508.json",
        "app_parity_i18n_language_shells_v43_20260508.json",
        "low_bandwidth_i18n_language_shells_v43_20260508.json",
        "browser_runtime_i18n_language_shells_v43_20260508.json",
        "tunnel_health_i18n_language_shells_v43_20260508.json",
        "account_auth_readiness_20260508.json",
        "app_parity_account_subject_binding_20260508.json",
        "low_end_runtime_account_subject_binding_20260508.json",
        "low_bandwidth_account_subject_binding_20260508.json",
        "native_build_smoke_android_debug_webview_20260508.json",
        *ANDROID_FINAL_ANSWER_ARTIFACTS,
        *ANDROID_SOURCE_WINDOW_ARTIFACTS,
        WAYDROID_FOUR_APK_ARTIFACT,
    ]
    blocker_artifacts = [
        "app_path_budget_matrix_browser_submit_120s_required_20260508.json",
        "app_path_budget_matrix_engine_stage_fresh_islam_simli_120s_30s_20260508.json",
        COLD_ISLAM_BUDGET_ARTIFACT,
        "native_build_smoke_android_debug_webview_20260508.json",
    ]
    for name in pass_artifacts + blocker_artifacts:
        _write_run_json(tmp_path, name, {"passes": True})
    _write_run_json(
        tmp_path,
        "native_build_smoke_android_debug_webview_20260508.json",
        {
            "passes": True,
            "android": {"build": {"passes": True, "apk": {"exists": True, "sizeBytes": 12, "manifestAssetSynced": True}}},
        },
    )
    for name in ANDROID_FINAL_ANSWER_ARTIFACTS + ANDROID_SOURCE_WINDOW_ARTIFACTS:
        if name.endswith("_runtime.json"):
            _write_android_runtime(tmp_path / "runs" / name)
        elif "source_window" in name:
            _write_android_source_window(tmp_path / "runs" / name)
        else:
            _write_android_webview(tmp_path / "runs" / name)
    _write_waydroid_four_apk_report(tmp_path / "runs" / WAYDROID_FOUR_APK_ARTIFACT, missing_user_path_evidence=True)
    audit_text = "\n".join(f"runs/{name}" for name in pass_artifacts + blocker_artifacts)
    (tmp_path / "tasks" / "completion-audit-2026-05-08.md").write_text(audit_text, encoding="utf-8")
    (tmp_path / "tasks" / "requirements-audit.md").write_text(audit_text, encoding="utf-8")

    report = verifier.build_report(tmp_path)

    waydroid = report["checks"]["latestWaydroidFourApkTranche"]["artifact"]
    assert report["checks"]["latestWaydroidFourApkTranche"]["passes"] is False
    assert waydroid["apps"][0]["userPathEvidencePasses"] is False
    assert "user-path DB/engine/citation proof incomplete" in waydroid["error"]


def test_completion_audit_verifier_rejects_waydroid_report_without_real_corpus_db_preflight(tmp_path):
    verifier = _load_verifier()
    (tmp_path / "tasks").mkdir()
    (tmp_path / "runs").mkdir()
    pass_artifacts = [
        "low_end_runtime_i18n_language_shells_v43_20260508.json",
        "app_parity_i18n_language_shells_v43_20260508.json",
        "low_bandwidth_i18n_language_shells_v43_20260508.json",
        "browser_runtime_i18n_language_shells_v43_20260508.json",
        "tunnel_health_i18n_language_shells_v43_20260508.json",
        "account_auth_readiness_20260508.json",
        "app_parity_account_subject_binding_20260508.json",
        "low_end_runtime_account_subject_binding_20260508.json",
        "low_bandwidth_account_subject_binding_20260508.json",
        "native_build_smoke_android_debug_webview_20260508.json",
        *ANDROID_FINAL_ANSWER_ARTIFACTS,
        *ANDROID_SOURCE_WINDOW_ARTIFACTS,
        WAYDROID_FOUR_APK_ARTIFACT,
    ]
    blocker_artifacts = [
        "app_path_budget_matrix_browser_submit_120s_required_20260508.json",
        "app_path_budget_matrix_engine_stage_fresh_islam_simli_120s_30s_20260508.json",
        COLD_ISLAM_BUDGET_ARTIFACT,
        "native_build_smoke_android_debug_webview_20260508.json",
    ]
    for name in pass_artifacts + blocker_artifacts:
        _write_run_json(tmp_path, name, {"passes": True})
    _write_run_json(
        tmp_path,
        "native_build_smoke_android_debug_webview_20260508.json",
        {
            "passes": True,
            "android": {"build": {"passes": True, "apk": {"exists": True, "sizeBytes": 12, "manifestAssetSynced": True}}},
        },
    )
    for name in ANDROID_FINAL_ANSWER_ARTIFACTS + ANDROID_SOURCE_WINDOW_ARTIFACTS:
        if name.endswith("_runtime.json"):
            _write_android_runtime(tmp_path / "runs" / name)
        elif "source_window" in name:
            _write_android_source_window(tmp_path / "runs" / name)
        else:
            _write_android_webview(tmp_path / "runs" / name)
    _write_waydroid_four_apk_report(tmp_path / "runs" / WAYDROID_FOUR_APK_ARTIFACT, missing_corpus_db_evidence=True)
    audit_text = "\n".join(f"runs/{name}" for name in pass_artifacts + blocker_artifacts)
    (tmp_path / "tasks" / "completion-audit-2026-05-08.md").write_text(audit_text, encoding="utf-8")
    (tmp_path / "tasks" / "requirements-audit.md").write_text(audit_text, encoding="utf-8")

    report = verifier.build_report(tmp_path)

    waydroid = report["checks"]["latestWaydroidFourApkTranche"]["artifact"]
    assert report["checks"]["latestWaydroidFourApkTranche"]["passes"] is False
    assert waydroid["corpusDatabasesPasses"] is False
    assert "shared corpus database proof failed or missing" in waydroid["error"]


def test_waydroid_goal_scope_accepts_only_current_four_apk_evidence(tmp_path):
    verifier = _load_verifier()
    (tmp_path / "runs").mkdir()
    _write_four_android_apk_verify_report(tmp_path / "runs" / FOUR_ANDROID_APK_VERIFY_ARTIFACT)
    _write_waydroid_four_apk_report(tmp_path / "runs" / WAYDROID_FOUR_APK_ARTIFACT)
    for name in [
        "app_path_budget_matrix_browser_submit_120s_required_20260508.json",
        "app_path_budget_matrix_engine_stage_fresh_islam_simli_120s_30s_20260508.json",
        COLD_ISLAM_BUDGET_ARTIFACT,
        "native_build_smoke_android_debug_webview_20260508.json",
    ]:
        _write_run_json(tmp_path, name, {"passes": False})

    report = verifier.build_waydroid_four_apk_goal_report(tmp_path)

    assert report["scope"] == "waydroid-four-apk-goal"
    assert report["passes"] is True, json.dumps(report, indent=2)
    assert report["verdict"] == "achieved"
    assert report["checks"]["fourAndroidApkPreflight"]["passes"] is True
    assert report["checks"]["latestWaydroidFourApkTranche"]["passes"] is True
    assert "full-answer latency" not in " ".join(report["remainingBlockers"])


def test_waydroid_goal_scope_rejects_missing_or_bad_apk_preflight(tmp_path):
    verifier = _load_verifier()
    (tmp_path / "runs").mkdir()
    _write_waydroid_four_apk_report(tmp_path / "runs" / WAYDROID_FOUR_APK_ARTIFACT)

    missing_report = verifier.build_waydroid_four_apk_goal_report(tmp_path)

    assert missing_report["passes"] is False
    assert missing_report["checks"]["fourAndroidApkPreflight"]["passes"] is False
    assert "four Android APK artifact/signature/stamp verification" in missing_report["remainingBlockers"]

    _write_four_android_apk_verify_report(tmp_path / "runs" / FOUR_ANDROID_APK_VERIFY_ARTIFACT, failing_app="tcm")
    bad_report = verifier.build_waydroid_four_apk_goal_report(tmp_path)

    assert bad_report["passes"] is False
    assert bad_report["checks"]["fourAndroidApkPreflight"]["apps"][2]["passes"] is False
    assert "four Android APK artifact/signature/stamp verification" in bad_report["remainingBlockers"]


def test_completion_audit_cli_can_run_waydroid_goal_scope(tmp_path):
    verifier = _load_verifier()
    (tmp_path / "runs").mkdir()
    output = tmp_path / "goal-report.json"
    _write_four_android_apk_verify_report(tmp_path / "runs" / FOUR_ANDROID_APK_VERIFY_ARTIFACT)
    _write_waydroid_four_apk_report(tmp_path / "runs" / WAYDROID_FOUR_APK_ARTIFACT)

    exit_code = verifier.main(
        [
            "--repo-root",
            str(tmp_path),
            "--scope",
            "waydroid-four-apk-goal",
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["scope"] == "waydroid-four-apk-goal"
    assert report["passes"] is True


def test_completion_audit_verifier_rejects_android_runtime_artifact_without_runtime_fields(tmp_path):
    verifier = _load_verifier()
    (tmp_path / "tasks").mkdir()
    (tmp_path / "runs").mkdir()
    pass_artifacts = [
        "low_end_runtime_i18n_language_shells_v43_20260508.json",
        "app_parity_i18n_language_shells_v43_20260508.json",
        "low_bandwidth_i18n_language_shells_v43_20260508.json",
        "browser_runtime_i18n_language_shells_v43_20260508.json",
        "tunnel_health_i18n_language_shells_v43_20260508.json",
        "account_auth_readiness_20260508.json",
        "app_parity_account_subject_binding_20260508.json",
        "low_end_runtime_account_subject_binding_20260508.json",
        "low_bandwidth_account_subject_binding_20260508.json",
        "native_build_smoke_android_debug_webview_20260508.json",
        *[name for name in ANDROID_FINAL_ANSWER_ARTIFACTS if name != "20260508_android_webview_final_answer_islam_runtime.json"],
        *ANDROID_SOURCE_WINDOW_ARTIFACTS,
        WAYDROID_FOUR_APK_ARTIFACT,
    ]
    blocker_artifacts = [
        "app_path_budget_matrix_browser_submit_120s_required_20260508.json",
        "app_path_budget_matrix_engine_stage_fresh_islam_simli_120s_30s_20260508.json",
        COLD_ISLAM_BUDGET_ARTIFACT,
        "native_build_smoke_android_debug_webview_20260508.json",
    ]
    for name in pass_artifacts + blocker_artifacts:
        _write_run_json(tmp_path, name, {"passes": True})
    for name in ANDROID_FINAL_ANSWER_ARTIFACTS + ANDROID_SOURCE_WINDOW_ARTIFACTS:
        if name == "20260508_android_webview_final_answer_islam_runtime.json":
            (tmp_path / "runs" / name).write_text(json.dumps({"passes": True}) + "\n", encoding="utf-8")
        elif name.endswith("_runtime.json"):
            _write_android_runtime(tmp_path / "runs" / name)
        elif "source_window" in name:
            _write_android_source_window(tmp_path / "runs" / name)
        else:
            _write_android_webview(tmp_path / "runs" / name)
    _write_waydroid_four_apk_report(tmp_path / "runs" / WAYDROID_FOUR_APK_ARTIFACT)
    audit_text = "\n".join(f"runs/{name}" for name in pass_artifacts + blocker_artifacts + ["20260508_android_webview_final_answer_islam_runtime.json"])
    (tmp_path / "tasks" / "completion-audit-2026-05-08.md").write_text(audit_text, encoding="utf-8")
    (tmp_path / "tasks" / "requirements-audit.md").write_text(audit_text, encoding="utf-8")

    report = verifier.build_report(tmp_path)

    assert report["passes"] is False
    assert report["checks"]["latestAndroidNativeTranche"]["passes"] is False


def test_completion_audit_verifier_rejects_android_webview_submit_artifact_without_completed_chat(tmp_path):
    verifier = _load_verifier()
    (tmp_path / "tasks").mkdir()
    (tmp_path / "runs").mkdir()
    pass_artifacts = [
        "low_end_runtime_i18n_language_shells_v43_20260508.json",
        "app_parity_i18n_language_shells_v43_20260508.json",
        "low_bandwidth_i18n_language_shells_v43_20260508.json",
        "browser_runtime_i18n_language_shells_v43_20260508.json",
        "tunnel_health_i18n_language_shells_v43_20260508.json",
        "account_auth_readiness_20260508.json",
        "app_parity_account_subject_binding_20260508.json",
        "low_end_runtime_account_subject_binding_20260508.json",
        "low_bandwidth_account_subject_binding_20260508.json",
        "native_build_smoke_android_debug_webview_20260508.json",
        *[name for name in ANDROID_FINAL_ANSWER_ARTIFACTS if name != "20260508_android_webview_final_answer_islam.json"],
        *ANDROID_SOURCE_WINDOW_ARTIFACTS,
        WAYDROID_FOUR_APK_ARTIFACT,
    ]
    blocker_artifacts = [
        "app_path_budget_matrix_browser_submit_120s_required_20260508.json",
        "app_path_budget_matrix_engine_stage_fresh_islam_simli_120s_30s_20260508.json",
        COLD_ISLAM_BUDGET_ARTIFACT,
        "native_build_smoke_android_debug_webview_20260508.json",
    ]
    for name in pass_artifacts + blocker_artifacts:
        _write_run_json(tmp_path, name, {"passes": True})
    (tmp_path / "runs" / "native_build_smoke_android_debug_webview_20260508.json").write_text(
        json.dumps({"android": {"build": {"passes": True, "apk": {"exists": True, "sizeBytes": 12, "manifestAssetSynced": True}}}, "passes": True})
        + "\n",
        encoding="utf-8",
    )
    for name in ANDROID_FINAL_ANSWER_ARTIFACTS + ANDROID_SOURCE_WINDOW_ARTIFACTS:
        if name.endswith("_runtime.json"):
            _write_android_runtime(tmp_path / "runs" / name)
        elif name == "20260508_android_webview_final_answer_islam.json":
            _write_android_webview(tmp_path / "runs" / name, completed=False)
        elif "source_window" in name:
            _write_android_source_window(tmp_path / "runs" / name)
        else:
            _write_android_webview(tmp_path / "runs" / name)
    _write_waydroid_four_apk_report(tmp_path / "runs" / WAYDROID_FOUR_APK_ARTIFACT)
    audit_text = "\n".join(
        f"runs/{name}"
        for name in pass_artifacts + blocker_artifacts + ["20260508_android_webview_final_answer_islam.json"]
    )
    (tmp_path / "tasks" / "completion-audit-2026-05-08.md").write_text(audit_text, encoding="utf-8")
    (tmp_path / "tasks" / "requirements-audit.md").write_text(audit_text, encoding="utf-8")

    report = verifier.build_report(tmp_path)

    assert report["passes"] is False
    assert report["checks"]["latestAndroidNativeTranche"]["passes"] is False


def test_completion_audit_verifier_rejects_android_webview_submit_without_final_llm_answer(tmp_path):
    verifier = _load_verifier()
    (tmp_path / "tasks").mkdir()
    (tmp_path / "runs").mkdir()
    pass_artifacts = [
        "low_end_runtime_i18n_language_shells_v43_20260508.json",
        "app_parity_i18n_language_shells_v43_20260508.json",
        "low_bandwidth_i18n_language_shells_v43_20260508.json",
        "browser_runtime_i18n_language_shells_v43_20260508.json",
        "tunnel_health_i18n_language_shells_v43_20260508.json",
        "account_auth_readiness_20260508.json",
        "app_parity_account_subject_binding_20260508.json",
        "low_end_runtime_account_subject_binding_20260508.json",
        "low_bandwidth_account_subject_binding_20260508.json",
        "native_build_smoke_android_debug_webview_20260508.json",
        *[name for name in ANDROID_FINAL_ANSWER_ARTIFACTS if name != "20260508_android_webview_final_answer_islam.json"],
        *ANDROID_SOURCE_WINDOW_ARTIFACTS,
        WAYDROID_FOUR_APK_ARTIFACT,
    ]
    blocker_artifacts = [
        "app_path_budget_matrix_browser_submit_120s_required_20260508.json",
        "app_path_budget_matrix_engine_stage_fresh_islam_simli_120s_30s_20260508.json",
        COLD_ISLAM_BUDGET_ARTIFACT,
        "native_build_smoke_android_debug_webview_20260508.json",
    ]
    for name in pass_artifacts + blocker_artifacts:
        _write_run_json(tmp_path, name, {"passes": True})
    (tmp_path / "runs" / "native_build_smoke_android_debug_webview_20260508.json").write_text(
        json.dumps({"android": {"build": {"passes": True, "apk": {"exists": True, "sizeBytes": 12, "manifestAssetSynced": True}}}, "passes": True})
        + "\n",
        encoding="utf-8",
    )
    for name in ANDROID_FINAL_ANSWER_ARTIFACTS + ANDROID_SOURCE_WINDOW_ARTIFACTS:
        if name.endswith("_runtime.json"):
            _write_android_runtime(tmp_path / "runs" / name)
        elif name == "20260508_android_webview_final_answer_islam.json":
            _write_android_webview(tmp_path / "runs" / name, final_answer=False)
        elif "source_window" in name:
            _write_android_source_window(tmp_path / "runs" / name)
        else:
            _write_android_webview(tmp_path / "runs" / name)
    _write_waydroid_four_apk_report(tmp_path / "runs" / WAYDROID_FOUR_APK_ARTIFACT)
    audit_text = "\n".join(
        f"runs/{name}"
        for name in pass_artifacts + blocker_artifacts + ["20260508_android_webview_final_answer_islam.json"]
    )
    (tmp_path / "tasks" / "completion-audit-2026-05-08.md").write_text(audit_text, encoding="utf-8")
    (tmp_path / "tasks" / "requirements-audit.md").write_text(audit_text, encoding="utf-8")

    report = verifier.build_report(tmp_path)

    assert report["passes"] is False
    assert report["checks"]["latestAndroidNativeTranche"]["passes"] is False


def test_completion_audit_verifier_rejects_android_source_window_artifact_without_highlight(tmp_path):
    verifier = _load_verifier()
    (tmp_path / "tasks").mkdir()
    (tmp_path / "runs").mkdir()
    pass_artifacts = [
        "low_end_runtime_i18n_language_shells_v43_20260508.json",
        "app_parity_i18n_language_shells_v43_20260508.json",
        "low_bandwidth_i18n_language_shells_v43_20260508.json",
        "browser_runtime_i18n_language_shells_v43_20260508.json",
        "tunnel_health_i18n_language_shells_v43_20260508.json",
        "account_auth_readiness_20260508.json",
        "app_parity_account_subject_binding_20260508.json",
        "low_end_runtime_account_subject_binding_20260508.json",
        "low_bandwidth_account_subject_binding_20260508.json",
        "native_build_smoke_android_debug_webview_20260508.json",
        *ANDROID_FINAL_ANSWER_ARTIFACTS,
        *[name for name in ANDROID_SOURCE_WINDOW_ARTIFACTS if name != "20260509_android_webview_source_window_tcm_retry.json"],
        WAYDROID_FOUR_APK_ARTIFACT,
    ]
    blocker_artifacts = [
        "app_path_budget_matrix_browser_submit_120s_required_20260508.json",
        "app_path_budget_matrix_engine_stage_fresh_islam_simli_120s_30s_20260508.json",
        COLD_ISLAM_BUDGET_ARTIFACT,
        "native_build_smoke_android_debug_webview_20260508.json",
    ]
    for name in pass_artifacts + blocker_artifacts:
        _write_run_json(tmp_path, name, {"passes": True})
    (tmp_path / "runs" / "native_build_smoke_android_debug_webview_20260508.json").write_text(
        json.dumps({"android": {"build": {"passes": True, "apk": {"exists": True, "sizeBytes": 12, "manifestAssetSynced": True}}}, "passes": True})
        + "\n",
        encoding="utf-8",
    )
    for name in ANDROID_FINAL_ANSWER_ARTIFACTS + ANDROID_SOURCE_WINDOW_ARTIFACTS:
        if name.endswith("_runtime.json"):
            _write_android_runtime(tmp_path / "runs" / name)
        elif name == "20260509_android_webview_source_window_tcm_retry.json":
            _write_android_source_window(tmp_path / "runs" / name, source_window=False)
        elif "source_window" in name:
            _write_android_source_window(tmp_path / "runs" / name)
        else:
            _write_android_webview(tmp_path / "runs" / name)
    _write_waydroid_four_apk_report(tmp_path / "runs" / WAYDROID_FOUR_APK_ARTIFACT)
    audit_text = "\n".join(
        f"runs/{name}"
        for name in pass_artifacts + blocker_artifacts + ["20260509_android_webview_source_window_tcm_retry.json"]
    )
    (tmp_path / "tasks" / "completion-audit-2026-05-08.md").write_text(audit_text, encoding="utf-8")
    (tmp_path / "tasks" / "requirements-audit.md").write_text(audit_text, encoding="utf-8")

    report = verifier.build_report(tmp_path)

    assert report["passes"] is False
    assert report["checks"]["latestAndroidNativeTranche"]["passes"] is False
    tcm_source_window = [
        item
        for item in report["checks"]["latestAndroidNativeTranche"]["artifacts"]
        if item["path"] == "runs/20260509_android_webview_source_window_tcm_retry.json"
    ][0]
    assert tcm_source_window["sourceWindowFieldsPass"] is False
