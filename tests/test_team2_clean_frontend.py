from pathlib import Path
import re


WEB = Path("web")
CHAT_PRODUCTS = ("islam", "tcm", "simli")


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


def test_team2_progress_renderer_updates_visible_detail_and_batch_slots():
    progress = (WEB / "job-progress.js").read_text(encoding="utf-8")
    compact = _compact(progress)

    assert '"[data-progress-detail]"' in progress
    assert '"[data-progress-batch]"' in progress
    assert ".textContent=" in compact
    assert ".detail&&" in compact
    assert ".index&&" in compact
    assert ".count?" in compact
    assert "innerHTML" not in progress


def test_team2_chat_textareas_submit_on_enter_without_breaking_multiline_or_ime():
    progress = (WEB / "job-progress.js").read_text(encoding="utf-8")

    assert "__beta6ComposerEnterShortcut" in progress
    assert 'addEventListener("keydown"' in progress
    assert ".isComposing" in progress
    assert ".shiftKey" in progress
    assert ".ctrlKey" in progress
    assert ".altKey" in progress
    assert ".metaKey" in progress
    assert ".preventDefault()" in progress
    assert ".requestSubmit" in progress
    assert "[data-chat-input]" in progress
    assert "innerHTML" not in progress

    for product in CHAT_PRODUCTS:
        js = (WEB / f"{product}-chat.js").read_text(encoding="utf-8")

        assert f'fetch("/api/{product}/jobs"' in js
        assert "/translate" not in js
        assert "innerHTML" not in js


def test_team2_clean_branch_does_not_add_frontend_translation_or_key_pool_surface():
    server = Path("shared_platform/server.py").read_text(encoding="utf-8")
    combined = "\n".join((WEB / f"{product}-chat.js").read_text(encoding="utf-8") for product in CHAT_PRODUCTS)
    tcm_html = (WEB / "tcm-chat.html").read_text(encoding="utf-8")

    assert "/api/{product}/translate" not in server
    assert "TranslateRequest" not in server
    assert "GEMINI_API_KEYS" not in server
    assert "GOOGLE_API_KEYS" not in server
    assert "/api/islam/translate" not in combined
    assert "/api/tcm/translate" not in combined
    assert "/api/simli/translate" not in combined
    assert "gemma-api.js" not in tcm_html
    assert "tcm-gemma-chat.js" not in tcm_html
    assert "config.defaults.js" not in tcm_html


def test_team2_background_jobs_cannot_overwrite_the_active_chat_view():
    for product in ("tcm", "simli"):
        js = (WEB / f"{product}-chat.js").read_text(encoding="utf-8")

        assert "function isCurrentJob" in js
        assert "activeSession&&t&&(activeSession.jobId=t)" in js
        assert "i&&renderResult" in js
        assert "o&&renderResult" in js
        assert "isCurrentJob(e,t)&&renderJobStatus(n)" in js
        assert "isCurrentJob(e,t)&&renderJobStatus(a)" in js
        assert "a=!n||!n.jobId||isCurrentJob(n.jobId,n)" in js


def test_team2_tcm_evidence_panel_pushes_layout_without_direct_gemma_ui_branch():
    progress = (WEB / "job-progress.js").read_text(encoding="utf-8")
    compact = _compact(progress)

    assert "team2-salvage" in progress
    assert "@media(min-width:761px)and(max-width:1250px)" in compact
    assert 'body[data-product="tcm"] .hanui-chat .evidence-board' in progress
    assert "position:static" in compact
    assert "width:0" in compact
    assert 'body[data-product="tcm"] .hanui-chat.show-evidence .evidence-board' in progress


def test_team2_source_window_wraps_long_mobile_titles():
    progress = (WEB / "job-progress.js").read_text(encoding="utf-8")
    compact = _compact(progress)

    assert ".source-window h2" in progress
    assert ".source-window-head>div" in compact
    assert "overflow-wrap:anywhere" in compact
    assert "word-break:break-word" in compact
    assert "max-width:100%" in compact


def test_team2_islam_group_ui_is_ported_without_translate_or_old_evidence_column():
    html = (WEB / "islam-bayyinah-chat.html").read_text(encoding="utf-8")

    assert '<html lang="ar" dir="rtl">' in html
    assert "grid-template-columns:280px minmax(0,1fr)" in html
    assert ".evidence,[data-toggle-evidence]{display:none!important}" in html
    assert "data-source-query" not in html
    assert 'data-i18n="quran"' not in html
    assert 'data-i18n="hadith"' not in html
    assert 'data-i18n="fiqh"' not in html
    assert "chat-ux-v47" in html
    assert "/api/islam/translate" not in html
