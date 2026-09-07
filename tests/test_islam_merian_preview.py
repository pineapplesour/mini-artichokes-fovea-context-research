import json
from pathlib import Path

from fastapi.testclient import TestClient

from apps.product_app import PRODUCT_PAGES, create_product_app


WEB = Path("web")

MERIAN_PRODUCT_PAGES = {
    "islam": ("HIKMAH", "en"),
    "buddhist": ("Buddhist AI", "ko"),
    "catholic": ("Christian AI", "ko"),
    "hindu": ("Hindu AI", "ko"),
    "tcm": ("Hanui AI", "ko"),
}

BUYLOW_PRODUCT_PAGES = {
    "buddhist": ("Buddhist", "Buddhist source chat", "Ask a source-grounded Buddhist question."),
    "catholic": ("Christian", "Christian source chat", "Ask a source-grounded Christian question."),
    "hindu": ("Hindu", "Hindu source chat", "Ask a source-grounded Hindu question."),
}


def test_islam_merian_chat_matches_reference_shell_and_stays_local():
    html_path = WEB / "islam-merian-chat.html"
    css_path = WEB / "merian-chat.css"
    js_path = WEB / "merian-chat.js"

    html = html_path.read_text(encoding="utf-8")
    css = css_path.read_text(encoding="utf-8")
    js = js_path.read_text(encoding="utf-8")

    assert 'data-product="islam"' in html
    assert "HIKMAH" in html
    assert 'id="app-wrapper"' in html
    assert 'id="sidebar"' in html
    assert 'id="room-list"' in html
    assert 'class="brand-dot"' in html
    assert 'class="welcome-mark"' in html
    assert 'id="conversation"' in html
    assert 'id="messages"' in html
    assert 'id="input"' in html
    assert 'id="btn-send"' in html
    assert 'id="source-modal"' in html
    assert 'id="source-modal-body"' in html
    assert 'data-legal-footer' in html
    assert 'data-legal-open="terms"' in html
    assert 'data-legal-open="privacy"' in html
    assert 'id="legal-modal"' in html
    assert 'id="legal-modal-body"' in html
    assert 'href="/static/merian-chat.css?v=20260701-mobile-send-icon-1"' in html
    assert 'src="/static/chat-store.js"' in html
    assert 'src="/static/job-events.js"' in html
    assert 'src="/static/job-cancel.js"' in html
    assert 'src="/static/merian-chat.js?v=20260701-mobile-send-icon-1"' in html
    assert html.index('data-legal-footer') < html.index("</aside>")
    assert html.index('data-legal-footer') < html.index('id="app"')

    for text in (html, css, js):
        assert "https://" not in text
        assert "http://" not in text
        assert "fonts.googleapis.com" not in text
        assert "DEMO_MODE" not in text
        assert "mockJobs" not in text
        assert "innerHTML" not in text

    assert "--bg:" in css
    assert ".job-step.active .job-step-icon" in css
    assert "@keyframes active-dot-blink" in css
    assert "animation: active-dot-blink" in css
    assert ".modal-body mark" in css

    assert 'const product = document.body.dataset.product || "islam";' in js
    assert "Beta6ChatStore.create" in js
    assert "Beta6JobEvents.follow" in js
    assert "Beta6JobCancel.cancel" in js
    assert "limit: 50" in js
    assert 'analysisMode: "fast"' in js
    assert "`/api/${product}/jobs`" in js
    assert "`/api/${product}/source-window?${params.toString()}`" in js
    assert "highlightStart" in js
    assert "highlightEnd" in js
    assert "citation-btn" in js
    assert "replaceChildren(title, status, textBlock)" not in js
    assert "const modalChildren = status" in js


def test_islam_merian_fixes_composer_markdown_and_source_window_contract():
    js = (WEB / "merian-chat.js").read_text(encoding="utf-8")
    css = (WEB / "merian-chat.css").read_text(encoding="utf-8")

    assert "clearComposerAfterSubmit();" in js
    assert "function clearComposerAfterSubmit()" in js
    assert 'ui.input.value = "";' in js
    assert 'ui.input.style.height = "auto";' in js

    assert "renderMarkdownLine" in js
    assert r"^#{1,4}\s+" in js
    assert 'node("h3"' in js
    assert "answerParagraph" in js

    assert "cleanSourceText" in js
    assert r"\[META\]" in js
    assert r"\[PRIMARY TEXT" in js
    assert r"\[BOUNDARIES\]" in js
    assert "renderClaimContext" in js
    assert "claim-summary-card" in js
    assert "claim-context-card" in js
    assert "renderHighlightList" in js
    assert "highlight-list" in js
    assert "expandSourceWindow" in js
    assert 'expandSourceWindow("before")' in js
    assert 'expandSourceWindow("after")' in js
    assert "fetchSourceWindow(source, claim, beforeChars, afterChars)" in js
    assert "hasBefore" in js
    assert "hasAfter" in js
    assert "source-more" in js
    assert "No source id" not in js
    assert "buildCompleteCitationMap" in js
    assert "parseCitationLabels" in js
    assert "sourceIdForWindow" in js
    assert "context window" in js.lower()
    assert "source-more--before" in js
    assert "source-more--after" in js

    assert ".claim-summary-card" in css
    assert ".claim-context-card" in css
    assert ".highlight-list" in css
    assert ".source-more" in css
    assert ".source-more--before" in css
    assert ".source-more--after" in css


def test_merian_final_answer_replaces_progress_entry_and_busts_cached_assets():
    js = (WEB / "merian-chat.js").read_text(encoding="utf-8")
    sw = (WEB / "sw.js").read_text(encoding="utf-8")
    render_result = js.split("function renderResult(result) {", 1)[1].split("\n  function answerEntry", 1)[0]

    assert "const answer = answerEntry(result);" in render_result
    assert 'progressRoot.closest(".entry")' in render_result
    assert "ui.messages.replaceChild(answer, progressEntry)" in render_result
    assert "progressRoot = null;" in render_result
    assert "ui.messages.append(answerEntry(result))" not in render_result

    version = "20260701-mobile-send-icon-1"
    assert "shared-platform-shell-reference-v55" in sw
    assert f'const MERIAN_VERSION = "{version}";' in sw
    for product in MERIAN_PRODUCT_PAGES:
        html = (WEB / f"{product}-merian-chat.html").read_text(encoding="utf-8")
        assert f"v={version}" in html
        assert "v=20260630-design-progress-5" not in html


def test_merian_chat_includes_low_profile_legal_notices_for_app_stores():
    js = (WEB / "merian-chat.js").read_text(encoding="utf-8")
    css = (WEB / "merian-chat.css").read_text(encoding="utf-8")

    assert "LEGAL_COPY" in js
    assert "openLegalModal" in js
    for region in ("Korea", "United States", "EEA / UK", "Japan"):
        assert region in js
    for token in (
        "Terms of Use",
        "Privacy Policy",
        "개인정보",
        "retention",
        "third-party",
        "cross-border",
        "delete",
    ):
        assert token in js

    assert ".legal-footer" in css
    assert ".legal-modal" in css
    assert ".legal-region-grid" in css
    assert "position: static" in css
    assert ".sidebar .legal-footer" in css


def test_islam_merian_route_is_exposed_as_current_default():
    assert "islam-merian-chat" in PRODUCT_PAGES["islam"]

    manifest = json.loads((WEB / "app-shell-manifest.json").read_text(encoding="utf-8"))
    islam = manifest["products"]["islam"]
    assert "islam-merian-chat" in islam["exposedPages"]
    assert islam["landingRoute"] == "/islam-merian-chat.html"
    assert islam["chatRoute"] == "/islam-merian-chat.html"

    client = TestClient(create_product_app("islam"))
    response = client.get("/")

    assert response.status_code == 200
    assert "HIKMAH" in response.text
    assert 'src="/static/merian-chat.js?v=20260701-mobile-send-icon-1"' in response.text


def test_islam_buylow_chat_clones_merian_contract_and_is_exposed():
    page_name = "islam-buylow-chat"
    html_path = WEB / f"{page_name}.html"
    html = html_path.read_text(encoding="utf-8")

    assert 'data-product="islam"' in html
    assert 'class="buylow-shell"' in html
    assert "bl-phone" in html
    assert "bl-desktop-header" in html
    assert "bl-bottomnav" in html
    assert "BUYLOW" in html
    assert 'href="/static/buylow.css"' in html
    assert 'id="beta6-i18n"' in html
    assert 'src="/static/ui-i18n.js"' in html

    catalog = json.loads(html.split('<script id="beta6-i18n" type="application/json">', 1)[1].split("</script>", 1)[0])
    assert catalog["product"] == "islam"
    assert catalog["defaultLanguage"] == "en"
    assert catalog["languages"] == ["en", "ko", "ar", "pa", "ur", "bn", "id", "ms", "fa", "tr", "sw"]

    for token in (
        'id="header"',
        'id="composer"',
        'id="input"',
        'id="btn-send"',
        'id="messages"',
        'id="conversation"',
        'id="welcome"',
        'id="room-list"',
        'id="sidebar"',
        'id="sidebar-backdrop"',
        'id="btn-menu"',
        'id="btn-new"',
        'id="btn-theme"',
        'id="source-modal"',
        'id="source-modal-body"',
        'id="legal-modal"',
        'id="legal-modal-body"',
        'id="btn-close-modal"',
        'id="btn-close-legal"',
        'id="btn-close-sidebar"',
        "data-language",
        "job-bar-fill",
        "job-step",
        "citation-btn",
    ):
        assert token in html

    scripts = [
        'src="/static/chat-store.js"',
        'src="/static/job-events.js"',
        'src="/static/job-cancel.js"',
        'src="/static/job-progress.js"',
        'src="/static/merian-chat.js"',
    ]
    positions = [html.index(script) for script in scripts]
    assert positions == sorted(positions)

    assert page_name in PRODUCT_PAGES["islam"]

    manifest = json.loads((WEB / "app-shell-manifest.json").read_text(encoding="utf-8"))
    islam = manifest["products"]["islam"]
    assert page_name in islam["exposedPages"]
    assert islam["landingRoute"] == "/islam-merian-chat.html"
    assert islam["chatRoute"] == "/islam-merian-chat.html"

    response = TestClient(create_product_app("islam")).get(f"/{page_name}.html")
    assert response.status_code == 200
    assert 'href="/static/buylow.css"' in response.text
    assert 'id="composer"' in response.text


def test_buylow_chat_pages_exist_for_other_merian_products_and_are_exposed():
    manifest = json.loads((WEB / "app-shell-manifest.json").read_text(encoding="utf-8"))

    for product, (display_label, i18n_title, welcome_text) in BUYLOW_PRODUCT_PAGES.items():
        page_name = f"{product}-buylow-chat"
        html = (WEB / f"{page_name}.html").read_text(encoding="utf-8")

        assert f'data-product="{product}"' in html
        assert 'class="buylow-shell"' in html
        assert "bl-phone" in html
        assert "bl-desktop-header" in html
        assert "bl-bottomnav" in html
        assert "BUYLOW" in html
        assert display_label in html
        assert welcome_text in html
        assert 'href="/static/buylow.css"' in html
        assert 'id="beta6-i18n"' in html
        assert 'src="/static/ui-i18n.js"' in html
        assert 'value="ko"' in html

        catalog = json.loads(html.split('<script id="beta6-i18n" type="application/json">', 1)[1].split("</script>", 1)[0])
        assert catalog["product"] == product
        assert catalog["defaultLanguage"] == "ko"
        assert catalog["languages"] == ["ko", "en"]
        assert catalog["messages"]["en"]["chatTitle"] == f"BUYLOW {i18n_title}"

        for token in (
            'id="header"',
            'id="composer"',
            'id="input"',
            'id="btn-send"',
            'id="messages"',
            'id="conversation"',
            'id="welcome"',
            'id="room-list"',
            'id="sidebar"',
            'id="sidebar-backdrop"',
            'id="btn-menu"',
            'id="btn-new"',
            'id="btn-theme"',
            'id="source-modal"',
            'id="source-modal-body"',
            'id="legal-modal"',
            'id="legal-modal-body"',
            'id="btn-close-modal"',
            'id="btn-close-legal"',
            'id="btn-close-sidebar"',
            "data-language",
            "data-merian-chat-form",
            "data-chat-input",
            "job-bar-fill",
            "job-step",
            "citation-btn",
        ):
            assert token in html

        scripts = [
            'src="/static/chat-store.js"',
            'src="/static/job-events.js"',
            'src="/static/job-cancel.js"',
            'src="/static/job-progress.js"',
            'src="/static/merian-chat.js"',
        ]
        positions = [html.index(script) for script in scripts]
        assert positions == sorted(positions)

        assert page_name in PRODUCT_PAGES[product]
        assert page_name in manifest["products"][product]["exposedPages"]

        response = TestClient(create_product_app(product)).get(f"/{page_name}.html")
        assert response.status_code == 200
        assert 'href="/static/buylow.css"' in response.text
        assert 'id="composer"' in response.text


def test_merian_reference_chat_pages_are_exposed_for_non_external_products():
    manifest = json.loads((WEB / "app-shell-manifest.json").read_text(encoding="utf-8"))
    sw = (WEB / "sw.js").read_text(encoding="utf-8")

    for product, (display_name, language) in MERIAN_PRODUCT_PAGES.items():
        page_name = f"{product}-merian-chat"
        page = WEB / f"{page_name}.html"
        assert page.exists()
        html = page.read_text(encoding="utf-8")

        assert f'data-product="{product}"' in html
        assert f'value="{language}"' in html
        assert display_name in html
        assert 'data-legal-footer' in html
        assert 'data-legal-open="terms"' in html
        assert 'data-legal-open="privacy"' in html
        assert 'id="legal-modal"' in html
        assert 'id="legal-modal-body"' in html
        assert 'href="/static/merian-chat.css?v=20260701-mobile-send-icon-1"' in html
        assert 'src="/static/merian-chat.js?v=20260701-mobile-send-icon-1"' in html
        assert html.index('data-legal-footer') < html.index("</aside>")
        assert html.index('data-legal-footer') < html.index('id="app"')
        assert "https://" not in html
        assert "http://" not in html
        assert "innerHTML" not in html

        assert page_name in PRODUCT_PAGES[product]
        assert page_name in manifest["products"][product]["exposedPages"]
        assert f"/{page_name}.html" in sw

        response = TestClient(create_product_app(product)).get(f"/{page_name}.html")
        assert response.status_code == 200
        assert display_name in response.text


def test_merian_new_submit_does_not_auto_reuse_recoverable_phrase_jobs():
    js = (WEB / "merian-chat.js").read_text(encoding="utf-8")
    run_question = js[js.index("async function runQuestion(query)") : js.index("function startConversation(query)")]

    assert "chatStore.start(query)" in run_question
    assert "fetch(`/api/${product}/jobs`" in run_question
    assert "findRecoverable(query)" not in run_question
    assert "followStoredJob(recoverable)" not in run_question
    assert "function restoreStoredSession(session)" in js
    assert "if (session.jobId) followStoredJob(session);" in js


def test_merian_progress_detail_hides_internal_engine_names():
    js = (WEB / "merian-chat.js").read_text(encoding="utf-8")

    assert "function publicProgressDetail" in js
    assert "beta[-\\s]?6" in js
    assert "return publicProgressDetail(" in js


def test_merian_progress_clock_resume_and_bar_are_monotonic():
    js = (WEB / "merian-chat.js").read_text(encoding="utf-8")

    for token in (
        "restoreMostRecentRunningSession",
        "startProgressClock",
        "stopProgressClock",
        "displayElapsedSeconds",
        "lastProgressPercent",
        "Math.max(lastProgressPercent",
        "setInterval(updateProgressClock, 1000)",
    ):
        assert token in js
    assert "restoreMostRecentRunningSession();" in js


def test_merian_progress_phase_and_source_details_are_monotonic_public_state():
    js = (WEB / "merian-chat.js").read_text(encoding="utf-8")

    for token in (
        "SERVER_STAGE_TO_PHASE",
        "lastProgressPhaseIndex",
        "phaseIndexFromStatus",
        "Math.max(lastProgressPhaseIndex",
        "selectedSourceCount(status)",
        "detailForPhase(status, phase)",
        "Reading ${sourceCount} selected sources.",
    ):
        assert token in js

    phase_from_status = js[js.index("function phaseFromStatus(status)") : js.index("function progressDetail(status, phase)")]
    assert 'normalized.includes("SOURCE")' not in phase_from_status
    assert 'normalized.includes("SEARCH")' not in phase_from_status
    assert '"source_selection": "SEARCHING"' in js
    assert '"claim_cards": "READING"' in js
    assert '"answer_plan": "READING"' in js
    assert '"writer": "SYNTHESIZING"' in js


def test_merian_default_theme_prevents_white_first_paint_and_uses_roomier_shell():
    css = (WEB / "merian-chat.css").read_text(encoding="utf-8")
    js = (WEB / "merian-chat.js").read_text(encoding="utf-8")
    sw = (WEB / "sw.js").read_text(encoding="utf-8")

    assert "--bg: #1E211C;" in css
    assert "--bg-raised: #272A24;" in css
    assert "--surface: #30332C;" in css
    assert "--text-dim: #C4BAAA;" in css
    assert "width: min(960px, 100%);" in css
    assert "calc(104px + env(safe-area-inset-bottom, 0px))" in css
    assert "calc(68px + env(safe-area-inset-bottom, 0px))" in css
    assert "#app-wrapper {\n  visibility: visible;" in css
    assert "transition: background 0.4s ease, color 0.4s ease;" not in css
    assert "body.merian-shell.merian-booting::before" in css
    assert "body.merian-shell.merian-booting #app-wrapper { visibility: hidden; }" in css
    assert "body.merian-shell:not(.merian-booting)::before { content: none; }" in css
    assert "function releaseBootShield()" in js
    assert 'document.body.classList.remove("merian-booting")' in js
    assert "window.requestAnimationFrame" in js
    assert "releaseBootShield();" in js
    assert 'shared-platform-shell-reference-v55' in sw
    assert 'const MERIAN_VERSION = "20260701-mobile-send-icon-1";' in sw
    assert '`/static/merian-chat.css?v=${MERIAN_VERSION}`' in sw
    assert '`/static/merian-chat.js?v=${MERIAN_VERSION}`' in sw

    for product in MERIAN_PRODUCT_PAGES:
        html = (WEB / f"{product}-merian-chat.html").read_text(encoding="utf-8")
        assert '<meta name="theme-color" content="#1E211C">' in html
        assert '<body class="merian-shell merian-booting"' in html
        assert "merian-first-paint" in html
        assert html.index("merian-first-paint") < html.index("/static/merian-chat.css")
        assert "body.merian-shell.merian-booting #app-wrapper{visibility:hidden}" in html
        assert 'body.merian-shell.merian-booting::before{content:"";position:fixed;inset:0;background:#1E211C;z-index:2147483647;pointer-events:none}' in html
        assert "v=20260701-mobile-send-icon-1" in html
        assert "v=20260630-design-progress-4" not in html


def test_merian_composer_input_text_is_vertically_centered():
    css = (WEB / "merian-chat.css").read_text(encoding="utf-8")

    composer_block = css[css.index(".composer {\n") : css.index(".composer:focus-within")]
    textarea_block = css[css.index(".composer textarea {\n") : css.index(".composer textarea::placeholder")]
    mobile_block = css[css.index("@media (max-width: 600px)") :]

    assert "align-items: center;" in composer_block
    assert "height: 32px;" in textarea_block
    assert "min-height: 32px;" in textarea_block
    assert "line-height: 20px;" in textarea_block
    assert "padding: 6px 0;" in textarea_block
    assert ".composer textarea { height: 36px; min-height: 36px; padding: 8px 0; }" in mobile_block


def test_merian_mobile_send_button_reads_as_icon_not_solid_orange_tile():
    css = (WEB / "merian-chat.css").read_text(encoding="utf-8")
    sw = (WEB / "sw.js").read_text(encoding="utf-8")

    send_block = css[css.index(".send-btn {\n") : css.index(".send-btn.active")]
    active_block = css[css.index(".send-btn.active {") : css.index(".send-btn.active:hover")]
    hover_start = css.index(".send-btn.active:hover")
    hover_block = css[hover_start : css.index(".legal-footer", hover_start)]
    mobile_block = css[css.index("@media (max-width: 600px)") :]

    assert "background: var(--accent-glow);" in send_block
    assert "border: 1px solid rgba(214, 106, 66, 0.32);" in send_block
    assert "padding: 0;" in send_block
    assert ".send-btn svg" in css
    assert "width: 18px;" in css
    assert "height: 18px;" in css
    assert "background: rgba(214, 106, 66, 0.18);" in active_block
    assert "background: rgba(214, 106, 66, 0.26);" in hover_block
    assert "background: #D4643F" not in hover_block
    assert ".send-btn { width: 36px; height: 36px; }" in mobile_block

    version = "20260701-mobile-send-icon-1"
    assert "shared-platform-shell-reference-v55" in sw
    assert f'const MERIAN_VERSION = "{version}";' in sw
    for product in MERIAN_PRODUCT_PAGES:
        html = (WEB / f"{product}-merian-chat.html").read_text(encoding="utf-8")
        assert f"v={version}" in html
        assert "v=20260701-final-answer-progress-1" not in html


def test_merian_sidebar_history_opens_without_delayed_transition_or_blur():
    css = (WEB / "merian-chat.css").read_text(encoding="utf-8")

    assert ".sidebar-backdrop {\n  position: fixed;" in css
    assert "backdrop-filter: blur(2px)" not in css
    assert "transition: opacity 0.3s var(--ease-out), visibility 0.3s var(--ease-out);" not in css
    assert "transform 0.35s var(--ease-out)" not in css
    assert "transform: translate3d(-100%, 0, 0);" in css
    assert ".sidebar.open { transform: translate3d(0, 0, 0); }" in css
    assert "contain: layout paint style;" in css


def test_merian_claim_context_cards_use_korean_user_facing_meanings():
    js = (WEB / "merian-chat.js").read_text(encoding="utf-8")

    assert "function claimContextLabels" in js
    assert "이 인용문의 맥락" in js
    assert "전체 맥락" in js
    assert "원문 안에서 어떤 의미로 쓰였는지" in js
    assert "이 인용문이 속한 원문" in js
    assert "인용 사용 맥락" not in js
    assert "질문 답변에 사용된 구체적 맥락" not in js


def test_merian_mobile_viewport_and_composer_use_dynamic_safe_area():
    css = (WEB / "merian-chat.css").read_text(encoding="utf-8")

    assert "height: 100dvh" in css
    assert "min-height: 100svh" in css
    assert "env(safe-area-inset-bottom" in css
    assert "env(safe-area-inset-top" in css
    assert "#app { flex: 1; display: flex; flex-direction: column; min-width: 0; min-height: 0;" in css
    assert ".app-container { display: flex; flex-direction: column; width: min(960px, 100%); min-height: 0;" in css
    assert ".conversation { flex: 1; min-height: 0; overflow-y: auto;" in css
    assert "max-height: min(160px, 28dvh)" in css
    assert "@media (max-height: 700px) and (max-width: 600px)" in css

    for product in MERIAN_PRODUCT_PAGES:
        html = (WEB / f"{product}-merian-chat.html").read_text(encoding="utf-8")
        assert 'viewport-fit=cover' in html
        assert "maximum-scale=1" not in html
