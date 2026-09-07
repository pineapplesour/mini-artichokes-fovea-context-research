import json
import re
from pathlib import Path


WEB = Path("web")


def _static_asset_path(asset: str) -> Path:
    if asset.startswith("/static/"):
        return WEB / asset.removeprefix("/static/")
    return WEB / asset.lstrip("/")


def _html_references_static_script(html: str, asset: str) -> bool:
    return f'src="/static/{asset}"' in html or f'"/static/{asset}"' in html


def _compact_js(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _i18n_catalog(html: str) -> dict:
    match = re.search(r'<script[^>]+id="beta6-i18n"[^>]*>(.*?)</script>', html, flags=re.S)
    assert match, "missing beta6 i18n catalog"
    return json.loads(match.group(1))


def _flatten_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _flatten_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _flatten_strings(item)


def _service_worker_asset_bytes(product: str) -> int:
    sw = (WEB / "sw.js").read_text(encoding="utf-8")
    manifest = json.loads((WEB / "app-shell-manifest.json").read_text(encoding="utf-8"))
    product_order = tuple(manifest["products"])
    product_index = product_order.index(product)
    next_product = product_order[product_index + 1] if product_index + 1 < len(product_order) else None
    core_block = sw.split("const CORE_ASSETS = [", 1)[1].split("];", 1)[0]
    product_block = sw.split(f"{product}:", 1)[1].split(f"{next_product}:", 1)[0] if next_product else sw.split(f"{product}:", 1)[1].split("};", 1)[0]
    assets = set(re.findall(r'"([^"]+)"', core_block + product_block))
    return sum(_static_asset_path(asset).stat().st_size for asset in assets)


def test_three_product_pages_exist_and_share_shell():
    for name in ("islam", "tcm", "simli"):
        html = WEB / f"{name}.html"
        assert html.exists()
        text = html.read_text(encoding="utf-8")
        assert 'name="viewport"' in text
        assert f'data-product="{name}"' in text
        assert 'src="/static/shared-client.js"' in text
        assert 'href="/static/styles.css"' not in text
        assert 'src="/static/app.js"' not in text


def test_frontend_assets_are_lightweight_and_local_only():
    for path in (WEB / "shared-client.js", WEB / "islam.html", WEB / "tcm.html", WEB / "simli.html"):
        assert path.exists()
        assert path.stat().st_size < 180_000
        text = path.read_text(encoding="utf-8")
        assert "https://" not in text
        assert "http://" not in text


def test_gemma_direct_chat_shell_keeps_api_key_server_side():
    html_path = WEB / "gemma-chat.html"
    js_path = WEB / "gemma-chat.js"
    assert html_path.exists()
    assert js_path.exists()
    assert html_path.stat().st_size < 90_000
    assert js_path.stat().st_size < 45_000

    html = html_path.read_text(encoding="utf-8")
    js = js_path.read_text(encoding="utf-8")
    index = (WEB / "index.html").read_text(encoding="utf-8")

    assert 'data-gemma-chat="direct"' in html
    assert 'src="/static/gemma-chat.js"' in html
    assert 'href="/gemma-chat.html"' in index
    assert "gemma-4-26b-a4b-it" in html
    assert "gemma-4-26b-a4b-it" in js
    assert 'fetch("/api/gemma/chat"' in js
    assert "replaceChildren" in js
    assert "textContent" in js
    assert "innerHTML" not in js
    forbidden = (
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "AIza",
        "generativelanguage.googleapis.com",
        "https://",
        "http://",
    )
    for token in forbidden:
        assert token not in html
        assert token not in js


def test_app_js_declares_required_language_sets():
    js = (WEB / "shared-client.js").read_text(encoding="utf-8")
    pages = "\n".join((WEB / f"{name}.html").read_text(encoding="utf-8") for name in ("islam", "tcm", "simli"))
    assert '"islam"' in js
    for lang in ("en", "ko", "ar", "pa", "ur", "bn", "id", "ms", "fa", "tr", "sw"):
        assert f'value="{lang}"' in pages
    assert '"tcm"' in js and '"simli"' in js


def test_default_product_shells_have_complete_forced_i18n_catalogs():
    manifest = json.loads((WEB / "app-shell-manifest.json").read_text(encoding="utf-8"))
    for product, profile in manifest["products"].items():
        for route_key in ("landingRoute", "chatRoute"):
            path = WEB / profile[route_key].lstrip("/")
            text = path.read_text(encoding="utf-8")
            if 'id="beta6-i18n"' not in text:
                assert profile["theme"] == "merian"
                assert 'src="/static/merian-chat.js' in text
                assert f'data-product="{product}"' in text
                continue
            catalog = _i18n_catalog(text)
            languages = profile["languages"]
            default_language = profile["defaultLanguage"]
            assert catalog["product"] == product
            assert catalog["defaultLanguage"] == default_language
            assert catalog["languages"] == languages
            assert 'src="/static/ui-i18n.js"' in text
            for lang in languages:
                assert lang in catalog["messages"], f"{path} missing {lang}"
            default_keys = set(catalog["messages"][default_language])
            assert default_keys
            for lang in languages:
                messages = catalog["messages"][lang]
                missing = sorted(default_keys - set(messages))
                empty = sorted(key for key in default_keys if not str(messages.get(key, "")).strip())
                assert not missing, f"{path} {lang} missing keys: {missing}"
                assert not empty, f"{path} {lang} empty keys: {empty}"
            dom_keys = set(re.findall(r'data-i18n(?:-[a-z]+)?="([^"]+)"', text))
            assert dom_keys
            assert dom_keys <= default_keys
            language_select = re.search(r"<select[^>]+data-language[^>]*>(.*?)</select>", text, flags=re.S)
            assert language_select, f"{path} missing language select"
            options = re.findall(r'<option[^>]+value="([^"]+)"', language_select.group(1))
            assert options == languages


def test_merian_products_are_registered_as_canonical_with_real_db_routes():
    manifest = json.loads((WEB / "app-shell-manifest.json").read_text(encoding="utf-8"))
    expected = {"islam", "buddhist", "catholic", "hindu", "tcm"}

    assert expected.issubset(manifest["products"])
    for key in expected:
        profile = manifest["products"][key]
        assert profile["theme"] == "merian"
        assert profile["landingRoute"] == f"/{key}-merian-chat.html"
        assert profile["chatRoute"] == f"/{key}-merian-chat.html"
        assert profile["native"]["entryRoute"] == profile["landingRoute"]
        assert profile["native"]["chatRoute"] == profile["chatRoute"]
        assert profile["api"]["jobs"] == f"/api/{key}/jobs"
        assert profile["api"]["sourceWindow"] == f"/api/{key}/source-window"
        assert profile["clientScript"] == "/static/merian-chat.js"
        assert (WEB / f"{key}-gallery.html").exists()
        assert (WEB / f"{key}-gallery-chat.html").exists()
        assert (WEB / f"{key}-merian-chat.html").exists()


def test_ui_i18n_runtime_applies_text_attributes_and_fails_missing_keys_safely():
    js = (WEB / "ui-i18n.js").read_text(encoding="utf-8")

    for token in (
        "Beta6I18n",
        "beta6.uiLanguage.",
        "data-i18n",
        "data-i18n-placeholder",
        "data-i18n-label",
        "validateCatalog",
        "missingTranslations",
        "document.documentElement.dir",
        "beta6:languagechange",
        "localStorage.setItem",
    ):
        assert token in js
    assert "language:()=>" in js
    assert "t:function" in js
    assert "innerHTML" not in js


def test_source_cards_use_concise_accessibility_labels():
    js = (WEB / "shared-client.js").read_text(encoding="utf-8")

    assert "Open source:" in js
    assert "aria-label" in js


def test_answer_markdown_is_rendered_without_inner_html_injection():
    js = (WEB / "shared-client.js").read_text(encoding="utf-8")

    assert "renderAnswerText" in js
    assert "renderWriterGate" in js
    assert "line.replace" in js
    assert 'class: "answer-text"' in js


def test_frontend_uses_beta6_job_polling_api():
    js = (WEB / "shared-client.js").read_text(encoding="utf-8")

    assert "pollJob" in js
    assert "`/api/${state.product}/jobs`" in js
    assert "`/api/jobs/${jobId}`" in js
    assert "`/api/jobs/${jobId}/result`" in js
    assert 'status.status === "completed"' in js
    assert "res.status !== 425" not in js


def test_chat_clients_poll_status_before_fetching_result_to_avoid_425_noise():
    for name in ("shared-client.js", "islam-chat.js", "tcm-chat.js", "simli-chat.js"):
        js = (WEB / name).read_text(encoding="utf-8")
        compact = _compact_js(js)

        assert "`/api/jobs/${jobId}`" in js or "/api/jobs/" in js or "/jobs/${" in js
        assert "`/api/jobs/${jobId}/result`" in js or "/result" in js
        assert 'status.status==="completed"' in compact or '"completed"===status.status' in compact or '"completed"===' in compact
        assert 'status.status==="failed"' in compact or '"failed"===status.status' in compact or '"failed"===' in compact
        assert "res.status !== 425" not in js


def test_chat_clients_do_not_timeout_before_long_beta6_jobs_finish():
    for name in ("shared-client.js", "islam-chat.js", "tcm-chat.js", "simli-chat.js"):
        js = (WEB / name).read_text(encoding="utf-8")

        assert "MAX_JOB_POLL_ATTEMPTS" in js
        assert "attempt < 90" not in js
        assert "Timed out waiting for source-grounded answer" not in js


def test_chat_clients_use_shared_durable_local_chat_store():
    store = WEB / "chat-store.js"
    assert store.exists()
    text = store.read_text(encoding="utf-8")
    compact = _compact_js(text)

    for token in (
        "Beta6ChatStore",
        "localStorage",
        "sessionToken",
        "beta6.sessionToken",
        "crypto.getRandomValues",
        "jobCreateHeaders",
        "jobUrl",
        '"X-Beta6-Session-Token"',
        'set("session"',
        "maxStoredSessions",
        "trimStoredResult",
        "sessionId",
        "jobId",
        "accessToken",
        "updatedAt",
        "JSON.stringify",
    ):
        assert token in text or token in compact
    assert "beta6.chat.1." in text
    assert "Beta6I18n" in text
    assert 'window.addEventListener("beta6:languagechange"' in text
    for key in (
        "noStoredChats",
        "chatMetaLocal",
        "chatMetaOffline",
        "chatMetaRunning",
        "chatMetaQueued",
        "chatMetaCancelled",
        "chatMetaError",
        "chatMetaFetch",
        "chatMetaSaved",
    ):
        assert key in text
    assert "innerHTML" not in text

    sw = (WEB / "sw.js").read_text(encoding="utf-8")
    assert "/static/chat-store.js" in sw
    for name in ("islam", "tcm", "simli"):
        html = (WEB / f"{name}-chat.html").read_text(encoding="utf-8")
        js = (WEB / f"{name}-chat.js").read_text(encoding="utf-8")
        assert _html_references_static_script(html, "chat-store.js")
        assert "data-chat-history" in html
        assert "Beta6ChatStore" in js
        assert "chatStore.start" in js
        assert "chatStore.sessionToken()" in js
        assert "chatStore.jobCreateHeaders()" in js
        assert "chatStore.jobUrl(path,token)" in _compact_js(js) or "chatStore.jobUrl" in js
        assert "chatStore.attachJob" in js
        assert "chatStore.complete" in js
        assert "chatStore.fail" in js
        assert "restoreStoredSession" in js


def test_landing_handoff_and_chat_auto_start_preserve_selected_language():
    shared = (WEB / "shared-client.js").read_text(encoding="utf-8")
    compact_shared = _compact_js(shared)
    assert 'document.querySelector("[data-language]")' in shared
    assert 'url.searchParams.set("language",language.value)' in compact_shared

    for name in ("islam", "tcm", "simli"):
        js = (WEB / f"{name}-chat.js").read_text(encoding="utf-8")
        compact = _compact_js(js)
        assert 'params.get("language")||""' in compact or 'get("language")' in compact
        assert "language&&urlLanguage" in compact or "language.value" in compact
        assert "language.value=urlLanguage" in compact or "language.value=" in compact
        assert f'fetch("/api/{name}/jobs"' in js


def test_chat_generated_summary_labels_use_i18n_runtime_not_fixed_korean():
    simli_html = (WEB / "simli-chat.html").read_text(encoding="utf-8")
    simli_js = (WEB / "simli-chat.js").read_text(encoding="utf-8")
    tcm_js = (WEB / "tcm-chat.js").read_text(encoding="utf-8")

    assert '<div data-i18n="summarySymptom">증상</div>' in simli_html
    for key in (
        "summaryQuestion",
        "summarySymptom",
        "summarySafety",
        "summaryEvidence",
        "summaryBoundary",
        "summaryNotDiagnosis",
    ):
        assert key in simli_html or key in simli_js
    for key in (
        "summaryQuestion",
        "summarySource",
        "summaryBoundary",
        "summaryNotDiagnosis",
        "herbSourceText",
        "herbContraCheck",
        "herbSupportEvidence",
    ):
        assert key in tcm_js
    assert "Beta6I18n" in simli_js
    assert "Beta6I18n" in tcm_js


def test_chat_clients_resume_saved_running_jobs_instead_of_creating_duplicates():
    store = (WEB / "chat-store.js").read_text(encoding="utf-8")
    compact = _compact_js(store)
    assert "findRecoverable" in store
    assert "progress:function(sessionId,status)" in compact or "progress(sessionId,status)" in compact or "progress:function" in compact
    assert '"queued"!==' in compact
    assert '"running"!==' in compact
    assert "progress:" in store or "progress:function" in compact

    for name in ("islam", "tcm", "simli"):
        js = (WEB / f"{name}-chat.js").read_text(encoding="utf-8")
        assert "pageIsUnloading" in js
        assert "pagehide" in js
        assert "chatStore.findRecoverable(query)" in js or "chatStore.findRecoverable" in js
        assert "followStoredJob" in js
        assert "session.jobId" in js or "jobId" in js
        compact = _compact_js(js)
        assert "chatStore.progress(session.sessionId,status)" in compact or "chatStore.progress" in js
        assert "followJob(job.jobId,session)" in compact or "followJob" in js
        assert "pollFallback" in js


def test_chat_store_uses_indexeddb_offline_outbox_and_online_retry():
    store = (WEB / "chat-store.js").read_text(encoding="utf-8")
    compact = _compact_js(store)

    for token in (
        "indexedDB.open",
        'createObjectStore("sessions"',
        'createObjectStore("outbox"',
        "queueOutbox",
        "outbox",
        'window.addEventListener("online"',
            "__beta6ChatOutboxFetch",
        "outboxRequest",
        "accessToken",
    ):
        assert token in store or token in compact
    assert 'transaction("sessions","readwrite")' in store
    assert 'transaction("sessions","readonly")' in store
    assert 'transaction("outbox","readwrite")' in store
    assert "`/api/${product}/jobs`" in store or "/jobs" in store

    sw = (WEB / "sw.js").read_text(encoding="utf-8")
    assert "shared-platform-shell-reference-v55" in sw


def test_chat_store_reselects_active_drained_outbox_job_without_product_js_duplication():
    store = (WEB / "chat-store.js").read_text(encoding="utf-8")
    compact = _compact_js(store)

    assert "outboxRequest:null" in store
    assert "localStorage.getItem" in store
    assert "onSelect" in store
    assert "onSelect" in store and "sessionId" in store

    for name in ("islam-chat.js", "tcm-chat.js", "simli-chat.js"):
        js = (WEB / name).read_text(encoding="utf-8")
        assert "beta6-chat-outbox-job" not in js
        assert "addEventListener(\"online\"" not in js


def test_chat_clients_use_shared_job_progress_contract():
    progress = WEB / "job-progress.js"
    assert progress.exists()
    text = progress.read_text(encoding="utf-8")
    compact = _compact_js(text)

    for token in (
        "Beta6JobProgress",
        "data-progress-stage",
        "data-progress-detail",
        "elapsedSeconds",
        "percent",
        "formatElapsed",
        "replaceChildren",
        "textContent",
    ):
        assert token in text
    assert "innerHTML" not in text


def test_landing_chat_entry_uses_shared_transition_before_chat_route():
    shared = (WEB / "shared-client.js").read_text(encoding="utf-8")

    for token in (
        "initChatEntryTransitions",
        "[data-chat-entry]",
        "beta6-chat-transitioning",
        "requestAnimationFrame",
        "new URL(form.getAttribute(\"action\")",
        "url.searchParams.set(\"q\"",
        "window.location.assign(url.toString())",
    ):
        assert token in shared

    for name in ("islam", "tcm", "simli"):
        html = (WEB / f"{name}.html").read_text(encoding="utf-8")
        assert 'data-chat-entry' in html
        assert f'action="/{name}-chat.html"' in html
        assert 'name="q"' in html
        assert 'src="/static/shared-client.js"' in html
        assert "beta6-chat-transitioning" in html
        assert "transition:" in html


def test_chat_shells_expose_visible_session_progress_and_chunk_detail_slots():
    progress = (WEB / "job-progress.js").read_text(encoding="utf-8")
    compact = _compact_js(progress)

    for token in (
        "data-progress-batch",
        "data-progress-detail",
    ):
        assert token in progress
    assert ".batch||" in compact
    assert ".index&&" in compact
    assert ".count?" in compact

    for name in ("islam", "tcm", "simli"):
        html = (WEB / f"{name}-chat.html").read_text(encoding="utf-8")
        js = (WEB / f"{name}-chat.js").read_text(encoding="utf-8")
        assert "data-query-state" in html
        assert "data-progress-detail" in html
        assert "data-progress-batch" in html
        assert "Beta6JobProgress.render" in js
        assert "queryState" in js


def test_user_facing_static_copy_hides_internal_engine_names():
    manifest = json.loads((WEB / "app-shell-manifest.json").read_text(encoding="utf-8"))
    pages = {
        "islam-chat.html",
        "islam-bayyinah.html",
        "islam-bayyinah-chat.html",
        "tcm-atelier-preview.html",
    }
    for profile in manifest["products"].values():
        pages.add(profile["landingRoute"].lstrip("/"))
        pages.add(profile["chatRoute"].lstrip("/"))

    for page in sorted(pages):
        html = (WEB / page).read_text(encoding="utf-8")
        without_code = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
        without_code = re.sub(r"<style\b[^>]*>.*?</style>", " ", without_code, flags=re.S | re.I)
        visible_text = re.sub(r"<[^>]+>", " ", without_code).lower()
        assert "beta-6" not in visible_text, page
        assert "beta6" not in visible_text, page

        if 'id="beta6-i18n"' in html:
            catalog_text = "\n".join(_flatten_strings(_i18n_catalog(html))).lower()
            assert "beta-6" not in catalog_text, page
            assert "beta6" not in catalog_text, page

    for script in ("shared-client.js", "islam-chat.js", "simli-chat.js", "tcm-chat.js"):
        text = (WEB / script).read_text(encoding="utf-8").lower()
        assert "beta-6" not in text, script
        assert '||"beta6"' not in text, script


def test_chat_shells_persist_unsent_drafts_through_shared_runtime():
    progress = (WEB / "job-progress.js").read_text(encoding="utf-8")

    for token in (
        "Beta6DraftStore",
        "__beta6DraftPersistence",
        "beta6.chatDraft.1",
        'addEventListener("input"',
        'addEventListener("pagehide"',
        "saveDraft",
        "loadDraft",
        "clearDraft",
    ):
        assert token in progress

    for name in ("islam", "tcm", "simli"):
        html = (WEB / f"{name}-chat.html").read_text(encoding="utf-8")
        js = (WEB / f"{name}-chat.js").read_text(encoding="utf-8")
        assert "data-chat-input" in html
        assert "chatStore.start" in js
        assert "chatStore.complete" in js
        assert "findRecoverable" in js


def test_job_progress_renderer_uses_structured_loading_bar_not_dot_line():
    progress = (WEB / "job-progress.js").read_text(encoding="utf-8")
    compact = _compact_js(progress)

    for token in (
        "beta6-progress-card",
        "beta6-progress-bar",
        "beta6-progress-fill",
        "aria-valuenow",
        "progressbar",
        ".message",
    ):
        assert token in progress

    assert "lightFor" not in progress
    assert "target.textContent=`" not in compact
    assert "·${formatElapsed" not in compact


def test_chat_answer_renderers_strip_raw_footnote_artifacts():
    progress = (WEB / "job-progress.js").read_text(encoding="utf-8")
    for token in (
        "Beta6AnswerText",
        "stripFootnoteArtifacts",
        r"replace(/\[\^[^\]]+\]/g",
        r"replace(/^\s*\[\^[^\]]+\]:.*$/gm",
        r"replace(/\[(?:footnote|note)\s*\d+\]/gi",
        "__beta6AnswerTextSanitizer",
        "MutationObserver",
        "[data-answer-sections], [data-evidence-list], .source-window",
    ):
        assert token in progress

    for name in ("islam", "tcm", "simli"):
        html = (WEB / f"{name}-chat.html").read_text(encoding="utf-8")
        assert "/static/job-progress.js" in html


def test_mobile_chat_rails_have_common_dismissal_controls():
    progress = (WEB / "job-progress.js").read_text(encoding="utf-8")
    compact = _compact_js(progress)

    for token in (
        "__beta6RailDismissal",
        "data-beta6-rail-backdrop",
        "closeRail",
        "show-rail",
        "show-evidence",
    ):
        assert token in progress
    assert '"Escape"===' in compact
    assert 'addEventListener("keydown"' in progress

    for name in ("islam", "tcm", "simli"):
        html = (WEB / f"{name}-chat.html").read_text(encoding="utf-8")
        assert "data-toggle-rail" in html
        assert "/static/job-progress.js" in html


def test_shared_runtime_keeps_focused_composer_above_mobile_keyboard():
    progress = (WEB / "job-progress.js").read_text(encoding="utf-8")

    for token in (
        "__beta6MobileKeyboard",
        "visualViewport",
        "--beta6-keyboard-inset",
        "beta6-keyboard-open",
        "focusin",
        "scrollIntoView",
        "data-chat-input",
        "input-floating-wrapper",
        "composer-wrap",
        "bottom-fade",
    ):
        assert token in progress
    assert "innerHTML" not in progress

    for page in (
        "islam-merian-chat.html",
        "buddhist-merian-chat.html",
        "catholic-merian-chat.html",
        "hindu-merian-chat.html",
        "tcm-merian-chat.html",
    ):
        html = (WEB / page).read_text(encoding="utf-8")
        assert "/static/job-progress.js" in html
        assert html.index("/static/job-progress.js") < html.index("/static/merian-chat.js")


def test_chat_viewports_allow_safe_area_and_keyboard_resize():
    manifest = json.loads((WEB / "app-shell-manifest.json").read_text(encoding="utf-8"))
    chat_pages = {profile["chatRoute"].lstrip("/") for profile in manifest["products"].values()}
    chat_pages.update({"islam-bayyinah-chat.html", "islam-merian-chat.html", "tcm-chat.html"})

    for page in sorted(chat_pages):
        html = (WEB / page).read_text(encoding="utf-8")
        viewport = re.search(r'<meta\s+name="viewport"\s+content="([^"]+)"', html)
        assert viewport, page
        content = viewport.group(1)
        assert "width=device-width" in content, page
        assert "initial-scale=1" in content, page
        assert "viewport-fit=cover" in content, page
        assert "maximum-scale" not in content, page


def test_islam_bayyinah_chat_removes_meaningless_source_shortcut_buttons():
    html = (WEB / "islam-bayyinah-chat.html").read_text(encoding="utf-8")

    assert "data-source-query" not in html
    assert 'data-i18n="quran"' not in html
    assert 'data-i18n="hadith"' not in html
    assert 'data-i18n="fiqh"' not in html


def test_psykey_chat_shell_uses_warm_reference_identity_not_old_maeumgyeol_chat():
    text = (WEB / "simli-chat.html").read_text(encoding="utf-8")

    assert "PsyKey AI" in text
    assert "싸이키 AI" not in text
    assert "싸이키</em>" not in text
    assert "CLINICA AI" not in text
    assert "마음결" not in text
    for token in (
        "--psy-bg:#f6d6c7",
        "--psy-accent:#9d77f5",
        "--psy-coral:#ff9b79",
        "--psy-mint:#90dac5",
        'class="psykey-chat-app"',
        'class="psykey-rail"',
        'class="psykey-thread"',
        'class="psykey-evidence"',
    ):
        assert token in text


def test_islam_reference_variants_are_available_without_replacing_current_shells():
    for name in ("islam-bayyinah.html", "islam-bayyinah-chat.html"):
        text = (WEB / name).read_text(encoding="utf-8")
        assert 'data-product="islam"' in text
        assert "Bayyinah" in text
        assert "data-chat-entry" in text or "data-islam-chat-form" in text
        assert "https://" not in text
        assert "http://" not in text
        assert "data:image" not in text

    main = (WEB / "islam.html").read_text(encoding="utf-8")
    chat = (WEB / "islam-chat.html").read_text(encoding="utf-8")
    assert "/islam-bayyinah.html" in main
    assert "/islam-bayyinah-chat.html" in chat


def test_mobile_chat_progress_status_is_not_hidden_by_product_css():
    for name in ("tcm", "simli"):
        html = (WEB / f"{name}-chat.html").read_text(encoding="utf-8")

        assert "data-query-state" in html
        assert ".thread-head span{display:none}" not in html

    sw = (WEB / "sw.js").read_text(encoding="utf-8")
    assert "/static/job-progress.js" in sw
    assert "shared-platform-shell-reference-v55" in sw
    for name in ("islam", "tcm", "simli"):
        html = (WEB / f"{name}-chat.html").read_text(encoding="utf-8")
        js = (WEB / f"{name}-chat.js").read_text(encoding="utf-8")
        assert _html_references_static_script(html, "job-progress.js")
        assert "Beta6JobProgress.render" in js


def test_chat_shells_lazy_load_runtime_scripts_after_initial_dom_ready_for_dcl_budget():
    for name in ("islam", "tcm", "simli"):
        html = (WEB / f"{name}-chat.html").read_text(encoding="utf-8")
        compact = _compact_js(html)

        assert "loadBeta6ChatScripts" in html
        assert "DOMContentLoaded" in html
        assert any(token in compact for token in ("script.async=false", "script.async=!1", ".async=!1"))
        assert f'"/static/{name}-chat.js"' in html
        for asset in ("job-progress.js", "job-events.js", "job-cancel.js", "chat-store.js"):
            assert f'"/static/{asset}"' in html
            assert f'src="/static/{asset}" defer' not in html
        assert f'src="/static/{name}-chat.js" defer' not in html


def test_lazy_loaded_product_chat_clients_init_when_dom_is_already_ready():
    for name in ("islam", "tcm", "simli"):
        js = (WEB / f"{name}-chat.js").read_text(encoding="utf-8")

        compact = _compact_js(js)
        assert 'document.readyState==="loading"' in compact or '"loading"===document.readyState' in compact
        assert 'window.addEventListener("DOMContentLoaded",init)' in compact
        assert "else{init();}" in compact or "else{init()}" in compact or ":init()" in compact


def test_chat_clients_use_shared_eventsource_progress_stream_with_polling_fallback():
    events = WEB / "job-events.js"
    assert events.exists()
    text = events.read_text(encoding="utf-8")

    for token in (
        "Beta6JobEvents",
        "EventSource",
        "jobBasePath",
        "accessToken",
        "sessionToken",
        "URLSearchParams",
        "pollFallback",
        "onStatus",
        "JSON.parse",
        "SSE_HANDSHAKE_TIMEOUT_MS",
        "setTimeout",
        "clearTimeout",
    ):
        assert token in text
    assert "innerHTML" not in text

    sw = (WEB / "sw.js").read_text(encoding="utf-8")
    assert "/static/job-events.js" in sw
    assert "shared-platform-shell-reference-v55" in sw
    for name in ("islam", "tcm", "simli"):
        html = (WEB / f"{name}-chat.html").read_text(encoding="utf-8")
        js = (WEB / f"{name}-chat.js").read_text(encoding="utf-8")
        compact = _compact_js(js)
        assert _html_references_static_script(html, "job-events.js")
        assert "Beta6JobEvents.follow" in js
        assert "followJob(job.jobId,session)" in compact or "followJob" in js
        assert "job.accessToken" in js or "accessToken" in js
        assert "chatStore.sessionToken()" in js
        assert "chatStore.attachJob(session.sessionId,job.jobId,job.accessToken)" in compact or "chatStore.attachJob" in js
        assert "jobUrl(`/api/jobs/${jobId}`" in js or "/api/jobs/" in js or "/jobs/${" in js
        assert "pollFallback" in js


def test_chat_clients_expose_shared_cancel_job_contract():
    cancel = WEB / "job-cancel.js"
    assert cancel.exists()
    cancel_text = cancel.read_text(encoding="utf-8")

    for token in (
        "Beta6JobCancel",
        "cancel(jobId",
        "jobBasePath",
        "chatStore.jobUrl(path, token)",
        'method: "POST"',
        "cancelled",
    ):
        assert token in cancel_text
    assert "innerHTML" not in cancel_text

    events = (WEB / "job-events.js").read_text(encoding="utf-8")
    assert 'status.status === "cancelled"' in events
    assert "error.cancelled = true" in events

    store = (WEB / "chat-store.js").read_text(encoding="utf-8")
    compact = _compact_js(store)
    assert "cancel:function(sessionId,status)" in compact or "cancel(sessionId,status)" in compact or "cancel:function" in compact
    assert 'status:"cancelled"' in compact
    assert 'item.status==="cancelled"' in compact or '"cancelled"===item.status' in compact or "chatMetaCancelled" in store
    assert "chatMetaCancelled" in store

    sw = (WEB / "sw.js").read_text(encoding="utf-8")
    assert "/static/job-cancel.js" in sw
    assert "shared-platform-shell-reference-v55" in sw

    for name in ("islam", "tcm", "simli"):
        html = (WEB / f"{name}-chat.html").read_text(encoding="utf-8")
        js = (WEB / f"{name}-chat.js").read_text(encoding="utf-8")
        compact = _compact_js(js)
        assert _html_references_static_script(html, "job-cancel.js")
        assert "data-cancel-job" in html
        assert "cancelCurrentJob" in js
        assert "Beta6JobCancel.cancel" in js
        assert "setActiveJob(session,job.jobId)" in compact or "setActiveJob" in js
        assert "clearActiveJob" in js
        assert "renderCancelledStatus" in js
        assert 'status.status==="cancelled"' in compact or '"cancelled"===status.status' in compact or 'status:"cancelled"' in compact
        assert "chatStore.cancel(session.sessionId,status)" in compact or "chatStore.cancel" in js


def test_pwa_shell_assets_exist_for_low_bandwidth_app_install():
    manifest = WEB / "manifest.webmanifest"
    sw = WEB / "sw.js"

    assert manifest.exists()
    assert sw.exists()
    for name in ("islam", "tcm", "simli"):
        text = (WEB / f"{name}.html").read_text(encoding="utf-8")
        assert 'rel="manifest"' in text
        assert 'name="theme-color"' in text
    for name in ("islam", "tcm", "simli"):
        text = (WEB / f"{name}.html").read_text(encoding="utf-8")
        assert "navigator.serviceWorker.register('/sw.js')" in text or 'navigator.serviceWorker.register("/sw.js")' in text
    assert "/static/chat-store.js" in sw.read_text(encoding="utf-8")


def test_service_worker_fetches_html_network_first_to_prevent_stale_cross_browser_shell():
    sw = (WEB / "sw.js").read_text(encoding="utf-8")

    assert 'request.mode === "navigate"' in sw
    assert '"text/html"' in sw
    assert "fetch(request).then(response" in sw
    assert "caches.match(url.pathname)" in sw
    assert "shared-platform-shell-reference-v55" in sw


def test_service_worker_install_tolerates_missing_cross_product_pages_in_split_apps():
    sw = (WEB / "sw.js").read_text(encoding="utf-8")

    assert "cache.addAll(SHELL_ASSETS)" not in sw
    assert "Promise.allSettled" in sw
    assert "cacheShellAsset" in sw
    assert "response.ok" in sw


def test_service_worker_caches_only_active_product_shells_when_split():
    sw = (WEB / "sw.js").read_text(encoding="utf-8")

    assert 'fetch("/api/products"' in sw
    assert "PRODUCT_SHELL_ASSETS" in sw
    assert "activeShellAssets" in sw
    assert "product.key" in sw


def test_service_worker_avoids_duplicate_root_precache_for_low_bandwidth_split_apps():
    sw = (WEB / "sw.js").read_text(encoding="utf-8")
    core_block = sw.split("const PRODUCT_SHELL_ASSETS", 1)[0]

    assert '"/",' not in core_block
    assert "FALLBACK_SHELLS" in sw
    assert "fallbackProductShell" in sw
    assert "for (const shell of FALLBACK_SHELLS)" in sw
    for shell in ('"/islam-gallery.html"', '"/tcm-gallery.html"', '"/simli.html"'):
        assert shell in sw


def test_islam_chat_page_follows_isnad_reference_shell():
    html = WEB / "islam-chat.html"
    js = WEB / "islam-chat.js"
    assert html.exists()
    assert js.exists()
    text = html.read_text(encoding="utf-8")

    assert 'data-product="islam"' in text
    assert 'class="isnad-app"' in text
    for token in (
        'class="isnad-rail"',
        'class="isnad-thread"',
        'class="isnad-evidence"',
        'class="composer"',
        'class="cite"',
        'class="verse"',
        'class="source-card"',
        'data-islam-chat-form',
        '"/static/islam-chat.js"',
    ):
        assert token in text
    assert "근거 자료" in text
    assert "사슬" in text
    assert "문헌 안에서 질문하세요" in text
    assert "출처 계보" in text
    assert "학문적 경계" in text
    for token in ("Source lineage", "Scholarly boundary", ">strict<", ">safe<"):
        assert token not in text


def test_islam_landing_can_handoff_to_chat_page():
    text = (WEB / "islam.html").read_text(encoding="utf-8")

    assert 'action="/islam-chat.html"' in text
    assert 'name="q"' in text
    assert 'data-chat-entry' in text
    assert 'class="query-box"' in text
    assert "Grounded answer" not in text


def test_tcm_landing_matches_reference_flow_and_hands_off_to_chat_page():
    text = (WEB / "tcm.html").read_text(encoding="utf-8")

    assert 'action="/tcm-chat.html"' in text
    assert 'name="q"' in text
    assert 'data-chat-entry' in text
    for token in (
        'class="suggest"',
        'class="hero-meta"',
        'id="sasang"',
        'id="herbs"',
        'class="saje-grid"',
        'class="herb-board"',
        'class="pattern-band"',
        'class="footer"',
    ):
        assert token in text
    assert "요즘 손발이 차고" in text
    assert "東醫寶鑑" in text
    assert "太陰" in text
    assert "甘草" in text
    assert "Grounded answer" not in text


def test_tcm_mobile_ask_card_preserves_reference_controls():
    text = (WEB / "tcm.html").read_text(encoding="utf-8")

    assert '<span class="dot"></span><span data-i18n="askLabel">지금 한의학 AI에게 묻기</span>' in text
    assert '<span class="latin">No. 0427</span>' in text
    for label in ("소화가 잘 안 돼요", "불면증이 심합니다", "손발이 차요", "사상체질이 궁금해요"):
        assert label in text

    assert ".hero>div{min-width:0}" in text
    assert ".ask-card{width:100%" in text
    mobile_block = text.split("@media(max-width:620px)", 1)[1]
    assert ".suggest{display:none}" not in mobile_block
    assert ".ask-row{grid-template-columns:1fr}" not in mobile_block
    assert ".ask-send{width:100%" not in mobile_block


def test_tcm_reference2_vertical_landing_is_lightweight_app_route():
    text = (WEB / "tcm-vertical.html").read_text(encoding="utf-8")
    main = (WEB / "tcm.html").read_text(encoding="utf-8")

    assert (WEB / "tcm-vertical.html").stat().st_size < 70_000
    assert 'data-product="tcm"' in text
    assert 'action="/tcm-chat.html"' in text
    assert 'name="q"' in text
    assert 'data-chat-entry' in text
    assert 'src="/static/shared-client.js"' in text
    assert "/tcm-vertical.html" in main
    for token in (
        "韓醫硏 · HANUI",
        "EST. 2024 · 韓醫學 INTELLIGENCE",
        "問而知之",
        "謂之工",
        "連辰",
        "丙午年 · 立夏",
        "임상 사례 24,000건",
    ):
        assert token in text
    for forbidden in ("__bundler", "Design Exploration", "Unpacking", "ReactDOM", "type=\"text/babel\"", "https://", "http://", "data:image"):
        assert forbidden not in text


def test_tcm_landing_harmonizes_ref1_and_ref2_as_one_app_surface():
    text = (WEB / "tcm.html").read_text(encoding="utf-8")

    for token in (
        'class="hanji-grid"',
        'class="five-phase-board"',
        'class="brush-orbit"',
        'class="diagnostic-editorial"',
        'class="source-ledger"',
        'class="pulse-card"',
        "診而察",
        "問而知",
        "임상가의 사유",
        "五行",
        "BALANCE",
    ):
        assert token in text
    for token in (
        "01 · 랜딩 / 홈",
        "A · Hanji Editorial",
        "Design Exploration",
        "__bundler",
        "Unpacking",
    ):
        assert token not in text


def test_tcm_chat_page_follows_hanui_reference_shell_without_bug_prone_patterns():
    html = WEB / "tcm-chat.html"
    js = WEB / "tcm-chat.js"
    assert html.exists()
    assert js.exists()
    text = html.read_text(encoding="utf-8")

    assert 'data-product="tcm"' in text
    assert 'class="hanui-chat"' in text
    for token in (
        'class="clinic-rail"',
        'class="consult-thread"',
        'class="evidence-board"',
        'class="composer"',
        'class="diag-card"',
        'class="herb-grid"',
        'data-tcm-chat-form',
        'data-answer-sections',
        'data-evidence-list',
        '"/static/tcm-chat.js"',
    ):
        assert token in text
    assert "문진" in text
    assert "변증" in text
    assert "본초" in text
    assert "근거 원문" in text
    assert "overflow-x:hidden" in text
    assert "@media(max-width:760px)" in text
    assert "minmax(0,1fr)" in text
    assert html.stat().st_size < 90_000
    assert js.stat().st_size < 28_000
    for path in (html, js):
        source = path.read_text(encoding="utf-8")
        assert "https://" not in source
        assert "http://" not in source
        assert "data:image" not in source


def test_tcm_chat_client_uses_structured_citation_contract_without_inner_html():
    js = (WEB / "tcm-chat.js").read_text(encoding="utf-8")

    for token in (
        "answerSections",
        "citationMap",
        "passages",
        "sources",
        "writer",
        "answerReadiness",
        "markdownToSections",
        "renderWriterRequired",
        "renderCitationChip",
        "renderPassage",
    ):
        assert token in js
    compact = _compact_js(js)
    assert 'answerReadiness==="final_answer"' in compact or ':"final_answer"' in compact
    assert "/api/tcm/jobs" in js
    assert "innerHTML" not in js


def test_tcm_chat_supports_clickable_citation_source_windows():
    js = (WEB / "tcm-chat.js").read_text(encoding="utf-8")
    html = (WEB / "tcm-chat.html").read_text(encoding="utf-8")

    for token in (
        "claimCards",
        "passageWindows",
        "appendBodyWithCitationChips",
        "citationLabelsFromText",
        "openPassageWindow",
        "fetchPassageWindow",
        "renderHighlightedText",
        "highlightStart",
        "highlightEnd",
        "/api/tcm/source-window",
        "전체 원문 보기",
        "위로 더 보기",
        "아래로 더 보기",
    ):
        assert token in js
    for token in ("source-window", "source-window-backdrop", "source-window-mark"):
        assert token in html
    assert "innerHTML" not in js


def test_chat_clients_prefer_cited_claim_cards_over_full_candidate_ledger():
    for name in ("islam", "tcm", "simli"):
        js = (WEB / f"{name}-chat.js").read_text(encoding="utf-8")

        for token in (
            "citedClaimCards",
            "candidateClaimCards",
            "claimCollectionsForLabel",
        ):
            assert token in js
        assert "result.citedClaimCards" in js or "citedClaimCards" in js
        assert "result.candidateClaimCards" in js or "candidateClaimCards" in js


def test_chat_clients_can_open_merged_claim_supporting_source_windows():
    for name in ("islam", "tcm", "simli"):
        js = (WEB / f"{name}-chat.js").read_text(encoding="utf-8")

        for token in (
            "supportingClaims",
            "renderSupportButtons",
            "openSupportWindow",
            "openClaimWindow",
            "supportingClaim",
        ):
            assert token in js
        assert "innerHTML" not in js


def test_chat_clients_do_not_reuse_primary_passage_window_for_supporting_claims():
    for name in ("islam", "tcm", "simli"):
        js = (WEB / f"{name}-chat.js").read_text(encoding="utf-8")

        assert "items.map((item,index)" in js or "items.map(((item,index)" in js or ".map((" in js
        assert 'const c=item.claimId&&item.claimId!==passage.claimId' in js or "claimId&&" in js
        assert '${item.label||"S"}${c}' in js or re.search(r'\$\{[^}]+\.label\|\|"S"\}\$\{[^}]+\}', js)
        assert (
            "if(claim.supportingClaim)return null" in js
            or "return claim.supportingClaim?null" in js
            or re.search(r"if\(\w+\.supportingClaim\)return null", js)
            or re.search(r"return \w+\.supportingClaim\?null", js)
        )
        assert "claim.supportingClaim&&item.sourceId" not in js


def test_tcm_chat_assets_are_cached_for_web_and_app_shell():
    sw = (WEB / "sw.js").read_text(encoding="utf-8")

    assert "/tcm-gallery-chat.html" in sw
    assert "/static/gallery-chat.js" in sw


def test_simli_landing_hands_off_to_chat_page_instead_of_inline_answer():
    text = (WEB / "simli.html").read_text(encoding="utf-8")

    assert 'action="/simli-chat.html"' in text
    assert 'name="q"' in text
    assert 'data-chat-entry' in text
    assert 'data-query-form' not in text
    assert 'data-answer' not in text
    assert "Retrieved source cards will appear here" not in text


def test_simli_chat_page_follows_therapeutic_aurora_shell_without_bug_prone_patterns():
    html = WEB / "simli-chat.html"
    js = WEB / "simli-chat.js"
    assert html.exists()
    assert js.exists()
    text = html.read_text(encoding="utf-8")

    assert 'data-product="simli"' in text
    assert 'class="psykey-chat-app"' in text
    for token in (
        'class="psykey-rail"',
        'class="psykey-thread"',
        'class="psykey-evidence"',
        'class="composer"',
        'class="clinical-card"',
        'class="source-card"',
        'data-simli-chat-form',
        'data-answer-sections',
        'data-evidence-list',
        '"/static/simli-chat.js"',
    ):
        assert token in text
    assert "안전 경계" in text
    assert "근거 원문" in text
    assert "상담 기록" in text
    assert "overflow-x:hidden" in text
    assert "@media(max-width:760px)" in text
    assert "minmax(0,1fr)" in text
    assert html.stat().st_size < 90_000
    assert js.stat().st_size < 28_000
    for path in (html, js):
        source = path.read_text(encoding="utf-8")
        assert "https://" not in source
        assert "http://" not in source
        assert "data:image" not in source


def test_simli_chat_client_uses_structured_citation_contract_without_inner_html():
    js = (WEB / "simli-chat.js").read_text(encoding="utf-8")

    for token in (
        "answerSections",
        "citationMap",
        "passages",
        "sources",
        "writer",
        "answerReadiness",
        "markdownToSections",
        "renderWriterRequired",
        "renderCitationChip",
        "renderPassage",
    ):
        assert token in js
    compact = _compact_js(js)
    assert 'answerReadiness==="final_answer"' in compact or ':"final_answer"' in compact
    assert "/api/simli/jobs" in js
    assert "innerHTML" not in js


def test_gallery_and_simli_submit_fast_beta6_payloads():
    gallery = (WEB / "gallery-chat.js").read_text(encoding="utf-8")
    simli = _compact_js((WEB / "simli-chat.js").read_text(encoding="utf-8"))

    assert "limit: 50" in gallery
    assert 'analysisMode: "fast"' in gallery
    assert "limit:50" in simli
    assert 'analysisMode:"fast"' in simli


def test_simli_chat_supports_clickable_citation_source_windows():
    js = (WEB / "simli-chat.js").read_text(encoding="utf-8")
    html = (WEB / "simli-chat.html").read_text(encoding="utf-8")

    for token in (
        "claimCards",
        "passageWindows",
        "appendBodyWithCitationChips",
        "citationLabelsFromText",
        "openPassageWindow",
        "fetchPassageWindow",
        "renderHighlightedText",
        "highlightStart",
        "highlightEnd",
        "/api/simli/source-window",
        "전체 원문 보기",
        "위로 더 보기",
        "아래로 더 보기",
    ):
        assert token in js
    for token in ("source-window", "source-window-backdrop", "source-window-mark"):
        assert token in html
    assert "innerHTML" not in js


def test_simli_chat_assets_are_cached_for_web_and_app_shell():
    sw = (WEB / "sw.js").read_text(encoding="utf-8")

    assert "/simli-chat.html" in sw
    assert "/static/simli-chat.js" in sw


def test_islam_landing_keeps_reference_lower_sections_visible():
    text = (WEB / "islam.html").read_text(encoding="utf-8")

    assert 'class="thread-preview"' in text
    assert 'class="features"' in text
    assert 'class="corpus-grid"' in text
    assert 'class="adab"' in text
    assert "예시 대화" in text
    assert "출처 추적" in text
    assert "학문 전통" in text
    assert "Hikmah는 학자가" in text
    assert "min-height:calc(100vh - 96px)" not in text
    assert "min-height:min(720px,calc(100vh - 190px))" in text
    assert "@media(max-width:520px)" in text
    assert ".links{display:none}" in text
    assert ".mode-row{display:none}" in text


def test_islam_chat_uses_hikmah_landing_palette():
    landing = (WEB / "islam.html").read_text(encoding="utf-8")
    chat = (WEB / "islam-chat.html").read_text(encoding="utf-8")

    for token in ("--bg:#0a1320", "--gold:#c9a86b", "--jade:#4a8a7b", "--ink:#f1e9d6"):
        assert token in landing
        assert token in chat
    assert '<meta name="theme-color" content="#0a1320">' in chat
    assert "--paper:#fbf8ef" not in chat
    assert "--paper2:#f1eadb" not in chat


def test_islam_chat_assets_are_small_local_and_cached():
    html = WEB / "islam-chat.html"
    js = WEB / "islam-chat.js"
    sw = (WEB / "sw.js").read_text(encoding="utf-8")

    assert html.stat().st_size < 70_000
    assert js.stat().st_size < 28_000
    for path in (html, js):
        text = path.read_text(encoding="utf-8")
        assert "https://" not in text
        assert "http://" not in text
        assert "data:image" not in text
    assert "/islam-gallery-chat.html" in sw
    assert "/static/gallery-chat.js" in sw


def test_islam_chat_client_uses_structured_citation_contract_without_inner_html():
    js = (WEB / "islam-chat.js").read_text(encoding="utf-8")

    for token in ("answerSections", "citationMap", "passages", "sources", "answerReadiness", "markdownToSections", "renderCitationChip", "renderPassage"):
        assert token in js
    assert 'answerReadiness === "final_answer"' in js
    assert "Primary text" not in js
    assert "Cross-check" not in js
    assert "No src." not in js
    assert "innerHTML" not in js


def test_islam_chat_supports_clickable_citation_source_windows():
    js = (WEB / "islam-chat.js").read_text(encoding="utf-8")
    html = (WEB / "islam-chat.html").read_text(encoding="utf-8")

    for token in (
        "claimCards",
        "passageWindows",
        "appendBodyWithCitationChips",
        "citationLabelsFromText",
        "openPassageWindow",
        "fetchPassageWindow",
        "renderHighlightedText",
        "highlightStart",
        "highlightEnd",
        "/api/islam/source-window",
        "전체구절 보기",
        "위로 더 보기",
        "아래로 더 보기",
    ):
        assert token in js
    for token in ("source-window", "source-window-backdrop", "source-window-mark"):
        assert token in html
    assert "innerHTML" not in js


def test_arabic_font_is_local_and_bounded():
    font = WEB / "fonts" / "NotoNaskhArabic-Regular.woff2"
    fallback_font = WEB / "fonts" / "NotoNaskhArabic-Regular.ttf"
    css = (WEB / "styles.css").read_text(encoding="utf-8")
    islam_html = (WEB / "islam.html").read_text(encoding="utf-8")
    islam_chat_html = (WEB / "islam-chat.html").read_text(encoding="utf-8")
    sw = (WEB / "sw.js").read_text(encoding="utf-8")

    assert font.exists()
    assert fallback_font.exists()
    assert font.stat().st_size < 180_000
    for text in (css, islam_html, islam_chat_html):
        assert "/static/fonts/NotoNaskhArabic-Regular.woff2" in text
        assert "/static/fonts/NotoNaskhArabic-Regular.ttf" in text
    assert css.find("/static/fonts/NotoNaskhArabic-Regular.woff2") < css.find("/static/fonts/NotoNaskhArabic-Regular.ttf")
    assert islam_html.find("/static/fonts/NotoNaskhArabic-Regular.woff2") < islam_html.find("/static/fonts/NotoNaskhArabic-Regular.ttf")
    assert islam_chat_html.find("/static/fonts/NotoNaskhArabic-Regular.woff2") < islam_chat_html.find("/static/fonts/NotoNaskhArabic-Regular.ttf")
    assert "/static/fonts/NotoNaskhArabic-Regular.woff2" in sw
    assert "/static/fonts/NotoNaskhArabic-Regular.ttf" not in sw


def test_service_worker_caches_compressed_arabic_font_only_for_islam_low_bandwidth_shell():
    sw = (WEB / "sw.js").read_text(encoding="utf-8")
    font_asset = '"/static/fonts/NotoNaskhArabic-Regular.woff2"'
    fallback_asset = '"/static/fonts/NotoNaskhArabic-Regular.ttf"'
    core_block = sw.split("const PRODUCT_SHELL_ASSETS", 1)[0]
    islam_block = sw.split("islam:", 1)[1].split("tcm:", 1)[0]
    tcm_block = sw.split("tcm:", 1)[1].split("simli:", 1)[0]
    simli_block = sw.split("simli:", 1)[1].split("};", 1)[0]

    assert font_asset not in core_block
    assert font_asset in islam_block
    assert font_asset not in tcm_block
    assert font_asset not in simli_block
    assert fallback_asset not in sw


def test_split_app_precache_payloads_stay_inside_low_bandwidth_budgets():
    assert _service_worker_asset_bytes("islam") < 220_000
    assert _service_worker_asset_bytes("tcm") < 95_000
    assert _service_worker_asset_bytes("simli") < 95_000


def test_frontend_carries_reference_visual_language_without_heavy_assets():
    css = "\n".join((WEB / f"{name}.html").read_text(encoding="utf-8") for name in ("islam", "tcm", "simli"))
    js = (WEB / "shared-client.js").read_text(encoding="utf-8")

    for token in ("mihrab", "arabesque", "paper-grain", "celadon", "aurora", "therapeutic-rings"):
        assert token in css or token in js
    assert "data:image" not in css
    assert "<svg" not in js


def test_frontend_exposes_product_specific_tool_surfaces():
    js = "\n".join((WEB / f"{name}.html").read_text(encoding="utf-8") for name in ("islam", "tcm", "simli"))

    for label in ("Qibla", "Prayer time", "Pattern", "Formula", "Crisis", "Safety plan"):
        assert label in js


def test_product_pages_follow_provided_reference_copy_and_structure():
    islam = (WEB / "islam.html").read_text(encoding="utf-8")
    tcm = (WEB / "tcm.html").read_text(encoding="utf-8")
    simli = (WEB / "simli.html").read_text(encoding="utf-8")

    assert "HIKMAH" in islam
    assert "ASK · LEARN · REFLECT" in islam
    assert "ٱلْعِلْمُ نُور" in islam
    assert "지혜는 신실한 이의" in islam

    assert "醫源 · 의원" in tcm
    assert "韓醫學 · KOREAN MEDICINE AI · MMXXVI" in tcm
    assert "오래된 지혜를" in tcm
    assert "새로운 방식으로" in tcm

    assert "PsyKey AI — 심리·정신 AI 탐색" in simli
    assert "PsyKey AI aurora" in simli
    assert "지금 1,247명이 마음을 정리하고 있어요" in simli
    assert "가만히 머무는" in simli
    assert "그 마음의 빛깔을" in simli
    assert "함께 들여다봐요." in simli
    assert "오늘의 마음 날씨" in simli
    assert "AI의 한 줄" in simli
    assert "김지윤 ⌄" in simli
    assert "마음결" not in simli
    assert "마음결 — 4가지 디자인 방향" not in simli
    assert "B · Therapeutic Aurora" not in simli
    assert "오로라처럼 번지는 신호" not in simli
    assert "A · Quiet Editorial" not in simli


def test_simli_reference_b_therapeutic_aurora_has_bug_resistant_responsive_layout():
    simli = (WEB / "simli.html").read_text(encoding="utf-8")

    for token in (
        "aurora-app",
        "aurora-hero-card",
        "aurora-weather",
        "aurora-quick",
        "aurora-chat",
        "b-nav",
        "b-hero",
        "overflow-x:hidden",
        "minmax(0,1fr)",
        "@media(max-width:760px)",
        "word-break:keep-all",
    ):
        assert token in simli
    for draft_token in ("dc-labelrow", "dc-labeltext", "dc-card", "design-canvas"):
        assert draft_token not in simli
    assert "font-size:clamp" not in simli
    assert "letter-spacing:-" not in simli
