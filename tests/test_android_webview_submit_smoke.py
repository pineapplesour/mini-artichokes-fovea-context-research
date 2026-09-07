import importlib.util
from pathlib import Path

import websocket


def _load_verifier():
    path = Path("tools/verify_android_webview_submit_smoke.py")
    spec = importlib.util.spec_from_file_location("verify_android_webview_submit_smoke", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class FakeCdpClient:
    def __init__(self, *, answer_readiness="", writer_status="", source_window=None):
        self.expressions = []
        self.polls = 0
        self.closed = False
        self.answer_readiness = answer_readiness
        self.writer_status = writer_status
        self.source_window = source_window

    def evaluate(self, expression, *, await_promise=False):
        self.expressions.append(expression)
        if "document.readyState" in expression:
            return "complete"
        if "requestSubmit" in expression:
            return {"submitted": True}
        if "sourceWindowClicked" in expression:
            return self.source_window or {
                "clicked": False,
                "dialogOpen": False,
                "textLength": 0,
                "highlightTextLength": 0,
                "moreButtonCount": 0,
                "error": "no source window in fake",
            }
        if "beta6.chat.1.islam" in expression:
            self.polls += 1
            if self.polls == 1:
                return {
                    "sessionStatus": "running",
                    "answerTextLength": 0,
                    "sourceCount": 0,
                    "progressText": "근거 선택 · 1/12",
                    "url": "http://10.0.2.2:8071/islam-bayyinah-chat.html",
                }
            return {
                "sessionStatus": "completed",
                "answerTextLength": 96,
                "sourceCount": 3,
                "answerReadiness": self.answer_readiness,
                "writerStatus": self.writer_status,
                "progressText": "완료",
                "url": "http://10.0.2.2:8071/islam-bayyinah-chat.html",
            }
        return None

    def close(self):
        self.closed = True


def test_android_webview_submit_smoke_uses_cdp_to_submit_and_observe_completed_chat():
    verifier = _load_verifier()
    cdp = FakeCdpClient()
    calls = []

    def runner(command, cwd, timeout_seconds):
        calls.append(command)
        text = " ".join(command)
        if "/proc/net/unix" in text:
            return verifier.CommandResult(
                command,
                str(cwd),
                0,
                "00000000: 00000002 00000000 00010000 0001 01 12345 @webview_devtools_remote_3410\n",
                "",
            )
        if command[:3] == ["adb", "forward", "tcp:9222"]:
            return verifier.CommandResult(command, str(cwd), 0, "", "")
        if command[:3] == ["adb", "forward", "--remove"]:
            return verifier.CommandResult(command, str(cwd), 0, "", "")
        return verifier.CommandResult(command, str(cwd), 0, "", "")

    report = verifier.build_report(
        runtime_report={
            "passes": True,
            "process": {"pid": "3410", "passes": True},
            "launch": {"baseOrigin": "http://10.0.2.2:8071", "product": "islam", "passes": True},
        },
        product="islam",
        query="기도는 몇 번 하나요?",
        base_origin="http://10.0.2.2:8071",
        runner=runner,
        cdp_client_factory=lambda url: cdp,
        target_fetcher=lambda port: [{"url": "http://10.0.2.2:8071/islam-bayyinah-chat.html", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/1"}],
        timeout_seconds=3,
    )

    assert report["checked"] is True
    assert report["passes"] is True
    assert report["checks"]["runtime"]["passes"] is True
    assert report["checks"]["devtoolsSocket"]["passes"] is True
    assert report["checks"]["domSubmit"]["passes"] is True
    assert report["checks"]["chatCompleted"]["passes"] is True
    assert report["checks"]["localChatStored"]["passes"] is True
    assert report["finalState"]["sessionStatus"] == "completed"
    assert cdp.closed is True
    assert any(command[:3] == ["adb", "forward", "tcp:9222"] for command in calls)
    assert calls[-1][:3] == ["adb", "forward", "--remove"]


def test_android_webview_submit_smoke_fails_when_debug_socket_is_missing():
    verifier = _load_verifier()

    def runner(command, cwd, timeout_seconds):
        if "cat /proc/net/unix" in " ".join(command):
            return verifier.CommandResult(command, str(cwd), 0, "", "")
        return verifier.CommandResult(command, str(cwd), 0, "", "")

    report = verifier.build_report(
        runtime_report={
            "passes": True,
            "process": {"pid": "3410", "passes": True},
            "launch": {"baseOrigin": "http://10.0.2.2:8071", "product": "islam", "passes": True},
        },
        product="islam",
        query="기도는 몇 번 하나요?",
        base_origin="http://10.0.2.2:8071",
        runner=runner,
        cdp_client_factory=lambda url: FakeCdpClient(),
        target_fetcher=lambda port: [],
        timeout_seconds=1,
    )

    assert report["passes"] is False
    assert report["checks"]["devtoolsSocket"]["passes"] is False
    assert "webview_devtools_remote" in report["checks"]["devtoolsSocket"]["message"]


def test_android_webview_submit_smoke_fails_when_runtime_launch_is_not_proven():
    verifier = _load_verifier()

    report = verifier.build_report(
        runtime_report={"passes": False, "process": {"pid": ""}},
        product="islam",
        query="기도는 몇 번 하나요?",
        base_origin="http://10.0.2.2:8071",
        runner=lambda command, cwd, timeout_seconds: verifier.CommandResult(command, str(cwd), 0),
        cdp_client_factory=lambda url: FakeCdpClient(),
        target_fetcher=lambda port: [],
    )

    assert report["passes"] is False
    assert report["checks"]["runtime"]["passes"] is False
    assert report["checks"]["domSubmit"]["checked"] is False


def test_cdp_client_suppresses_websocket_origin_for_android_webview(monkeypatch):
    verifier = _load_verifier()
    captured = {}

    class FakeSocket:
        def close(self):
            pass

    def fake_create_connection(url, timeout=0, **kwargs):
        captured["url"] = url
        captured["timeout"] = timeout
        captured["kwargs"] = kwargs
        return FakeSocket()

    monkeypatch.setattr(verifier.websocket, "create_connection", fake_create_connection)

    client = verifier.CdpClient("ws://127.0.0.1:9222/devtools/page/1")
    client.close()

    assert captured["url"] == "ws://127.0.0.1:9222/devtools/page/1"
    assert captured["timeout"] == 10
    assert captured["kwargs"].get("suppress_origin") is True


def test_choose_target_prefers_page_over_service_worker_for_same_origin():
    verifier = _load_verifier()

    target = verifier._choose_target(
        [
            {
                "url": "https://example.trycloudflare.com/sw.js",
                "type": "service_worker",
                "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/sw",
            },
            {
                "url": "https://example.trycloudflare.com/islam-bayyinah-chat.html",
                "type": "page",
                "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/chat",
            },
        ],
        "https://example.trycloudflare.com",
    )

    assert target["type"] == "page"
    assert target["url"].endswith("islam-bayyinah-chat.html")


def test_submit_expression_supports_all_product_chat_forms():
    verifier = _load_verifier()

    expression = verifier._submit_expression("질문")

    assert "data-islam-chat-form" in expression
    assert "data-tcm-chat-form" in expression
    assert "data-simli-chat-form" in expression
    assert "closest('form')" in expression


def test_state_expression_counts_dom_citation_buttons_when_claim_cards_lack_ids():
    verifier = _load_verifier()

    expression = verifier._state_expression("islam")

    assert "button.cite" in expression
    assert "source-open" in expression
    assert "Math.max" in expression
    assert "domCitationCount" in expression


def test_android_webview_submit_smoke_can_require_final_llm_answer():
    verifier = _load_verifier()
    cdp = FakeCdpClient(answer_readiness="final_answer", writer_status="completed")

    def runner(command, cwd, timeout_seconds):
        text = " ".join(command)
        if "/proc/net/unix" in text:
            return verifier.CommandResult(
                command,
                str(cwd),
                0,
                "00000000: 00000002 00000000 00010000 0001 01 12345 @webview_devtools_remote_3410\n",
                "",
            )
        return verifier.CommandResult(command, str(cwd), 0, "9222\n" if command[:2] == ["adb", "forward"] else "", "")

    report = verifier.build_report(
        runtime_report={
            "passes": True,
            "process": {"pid": "3410", "passes": True},
            "launch": {"baseOrigin": "http://10.0.2.2:8071", "product": "islam", "passes": True},
        },
        product="islam",
        query="기도는 몇 번 하나요?",
        base_origin="http://10.0.2.2:8071",
        require_final_answer=True,
        runner=runner,
        cdp_client_factory=lambda url: cdp,
        target_fetcher=lambda port: [{"url": "http://10.0.2.2:8071/islam-bayyinah-chat.html", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/1"}],
        timeout_seconds=3,
    )

    assert report["passes"] is True
    assert report["checks"]["finalAnswerReadiness"]["passes"] is True
    assert report["finalState"]["answerReadiness"] == "final_answer"
    assert report["finalState"]["writerStatus"] == "completed"


def test_android_webview_submit_smoke_rejects_writer_required_when_final_answer_required():
    verifier = _load_verifier()
    cdp = FakeCdpClient(answer_readiness="evidence_selected_writer_required", writer_status="requires_llm")

    def runner(command, cwd, timeout_seconds):
        text = " ".join(command)
        if "/proc/net/unix" in text:
            return verifier.CommandResult(
                command,
                str(cwd),
                0,
                "00000000: 00000002 00000000 00010000 0001 01 12345 @webview_devtools_remote_3410\n",
                "",
            )
        return verifier.CommandResult(command, str(cwd), 0, "9222\n" if command[:2] == ["adb", "forward"] else "", "")

    report = verifier.build_report(
        runtime_report={
            "passes": True,
            "process": {"pid": "3410", "passes": True},
            "launch": {"baseOrigin": "http://10.0.2.2:8071", "product": "islam", "passes": True},
        },
        product="islam",
        query="기도는 몇 번 하나요?",
        base_origin="http://10.0.2.2:8071",
        require_final_answer=True,
        runner=runner,
        cdp_client_factory=lambda url: cdp,
        target_fetcher=lambda port: [{"url": "http://10.0.2.2:8071/islam-bayyinah-chat.html", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/1"}],
        timeout_seconds=3,
    )

    assert report["passes"] is False
    assert report["checks"]["finalAnswerReadiness"]["passes"] is False


def test_android_webview_submit_smoke_can_require_source_window_after_final_answer():
    verifier = _load_verifier()
    cdp = FakeCdpClient(
        answer_readiness="final_answer",
        writer_status="completed",
        source_window={
            "clicked": True,
            "dialogOpen": True,
            "textLength": 220,
            "highlightTextLength": 18,
            "moreButtonCount": 2,
        },
    )

    def runner(command, cwd, timeout_seconds):
        text = " ".join(command)
        if "/proc/net/unix" in text:
            return verifier.CommandResult(
                command,
                str(cwd),
                0,
                "00000000: 00000002 00000000 00010000 0001 01 12345 @webview_devtools_remote_3410\n",
                "",
            )
        return verifier.CommandResult(command, str(cwd), 0, "9222\n" if command[:2] == ["adb", "forward"] else "", "")

    report = verifier.build_report(
        runtime_report={
            "passes": True,
            "process": {"pid": "3410", "passes": True},
            "launch": {"baseOrigin": "http://10.0.2.2:8071", "product": "islam", "passes": True},
        },
        product="islam",
        query="기도는 몇 번 하나요?",
        base_origin="http://10.0.2.2:8071",
        require_final_answer=True,
        require_source_window=True,
        runner=runner,
        cdp_client_factory=lambda url: cdp,
        target_fetcher=lambda port: [{"url": "http://10.0.2.2:8071/islam-bayyinah-chat.html", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/1"}],
        timeout_seconds=3,
    )

    assert report["passes"] is True
    assert report["checks"]["sourceWindow"]["passes"] is True
    assert report["checks"]["sourceWindow"]["result"]["highlightTextLength"] == 18
    assert any("sourceWindowClicked" in expression for expression in cdp.expressions)


def test_android_webview_submit_smoke_rejects_missing_source_window_when_required():
    verifier = _load_verifier()
    cdp = FakeCdpClient(
        answer_readiness="final_answer",
        writer_status="completed",
        source_window={
            "clicked": True,
            "dialogOpen": True,
            "textLength": 220,
            "highlightTextLength": 0,
            "moreButtonCount": 2,
        },
    )

    def runner(command, cwd, timeout_seconds):
        text = " ".join(command)
        if "/proc/net/unix" in text:
            return verifier.CommandResult(
                command,
                str(cwd),
                0,
                "00000000: 00000002 00000000 00010000 0001 01 12345 @webview_devtools_remote_3410\n",
                "",
            )
        return verifier.CommandResult(command, str(cwd), 0, "9222\n" if command[:2] == ["adb", "forward"] else "", "")

    report = verifier.build_report(
        runtime_report={
            "passes": True,
            "process": {"pid": "3410", "passes": True},
            "launch": {"baseOrigin": "http://10.0.2.2:8071", "product": "islam", "passes": True},
        },
        product="islam",
        query="기도는 몇 번 하나요?",
        base_origin="http://10.0.2.2:8071",
        require_final_answer=True,
        require_source_window=True,
        runner=runner,
        cdp_client_factory=lambda url: cdp,
        target_fetcher=lambda port: [{"url": "http://10.0.2.2:8071/islam-bayyinah-chat.html", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/1"}],
        timeout_seconds=3,
    )

    assert report["passes"] is False
    assert report["checks"]["sourceWindow"]["passes"] is False


def test_android_webview_submit_smoke_reports_cdp_timeout_instead_of_raising():
    verifier = _load_verifier()
    runtime = {
        "passes": True,
        "process": {"pid": "3410", "passes": True},
        "launch": {"baseOrigin": "https://example.trycloudflare.com", "product": "islam", "passes": True},
    }

    class TimeoutCdp:
        def __init__(self, websocket_url):
            self.websocket_url = websocket_url

        def evaluate(self, expression, *, await_promise=False):
            raise websocket.WebSocketTimeoutException("Connection timed out")

        def close(self):
            pass

    def runner(command, cwd, timeout_seconds):
        text = " ".join(command)
        if "/proc/net/unix" in text:
            return verifier.CommandResult(
                command,
                str(cwd),
                0,
                "00000000: 00000002 00000000 00010000 0001 01 12345 @webview_devtools_remote_3410\n",
                "",
            )
        if command[:2] == ["adb", "forward"]:
            return verifier.CommandResult(command, str(cwd), 0, "", "")
        return verifier.CommandResult(command, str(cwd), 0, "", "")

    report = verifier.build_report(
        runtime_report=runtime,
        product="islam",
        query="기도는 몇 번 하나요?",
        base_origin="https://example.trycloudflare.com",
        runner=runner,
        cdp_client_factory=TimeoutCdp,
        target_fetcher=lambda port: [
            {
                "type": "page",
                "url": "https://example.trycloudflare.com/islam-bayyinah-chat.html",
                "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/1",
            }
        ],
        timeout_seconds=1,
    )

    assert report["passes"] is False
    assert report["checks"]["domReady"]["checked"] is True
    assert report["checks"]["domReady"]["passes"] is False
    assert "Connection timed out" in report["checks"]["domReady"]["error"]
    assert report["checks"]["domSubmit"]["checked"] is False
