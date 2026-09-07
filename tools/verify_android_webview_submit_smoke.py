#!/usr/bin/env python3
"""Verify Android WebView chat submit through Chrome DevTools Protocol."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable

import websocket


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_REPORT = ROOT / "runs" / "android_runtime_smoke_verifier_20260508.json"
DEFAULT_DEVTOOLS_PORT = 9222


class CommandResult:
    def __init__(
        self,
        command: list[str],
        cwd: str,
        returncode: int,
        stdout: str = "",
        stderr: str = "",
        durationMs: int = 0,
    ) -> None:
        self.command = command
        self.cwd = cwd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.durationMs = durationMs


CommandRunner = Callable[[list[str], Path, int], CommandResult]
TargetFetcher = Callable[[int], list[dict[str, Any]]]
CdpClientFactory = Callable[[str], Any]


class CdpClient:
    def __init__(self, websocket_url: str) -> None:
        self.websocket_url = websocket_url
        self.socket = websocket.create_connection(websocket_url, timeout=10, suppress_origin=True)
        self.next_id = 1

    def evaluate(self, expression: str, *, await_promise: bool = False) -> Any:
        payload = {
            "id": self.next_id,
            "method": "Runtime.evaluate",
            "params": {
                "expression": expression,
                "awaitPromise": await_promise,
                "returnByValue": True,
            },
        }
        self.next_id += 1
        self.socket.send(json.dumps(payload))
        while True:
            message = json.loads(self.socket.recv())
            if message.get("id") != payload["id"]:
                continue
            if "error" in message:
                raise RuntimeError(json.dumps(message["error"], ensure_ascii=False))
            result = message.get("result", {}).get("result", {})
            if "exceptionDetails" in message.get("result", {}):
                raise RuntimeError(json.dumps(message["result"]["exceptionDetails"], ensure_ascii=False))
            return result.get("value")

    def close(self) -> None:
        self.socket.close()


def build_report(
    *,
    runtime_report: dict[str, Any] | None = None,
    runtime_report_path: str | Path = DEFAULT_RUNTIME_REPORT,
    product: str = "islam",
    query: str = "기도는 몇 번 하나요?",
    base_origin: str = "",
    runner: CommandRunner | None = None,
    cdp_client_factory: CdpClientFactory | None = None,
    target_fetcher: TargetFetcher | None = None,
    devtools_port: int = DEFAULT_DEVTOOLS_PORT,
    timeout_seconds: int = 30,
    require_final_answer: bool = False,
    require_source_window: bool = False,
) -> dict[str, Any]:
    runner = runner or _run_command
    cdp_client_factory = cdp_client_factory or CdpClient
    target_fetcher = target_fetcher or _fetch_devtools_targets
    runtime = runtime_report if runtime_report is not None else _read_json(Path(runtime_report_path))
    runtime_check = _runtime_check(runtime)
    checks: dict[str, dict[str, Any]] = {"runtime": runtime_check}
    if not runtime_check["passes"]:
        for name in _remaining_check_names(require_final_answer, require_source_window):
            checks[name] = _unchecked(name)
        return _report(False, runtime, checks, {}, product, query, base_origin, devtools_port)

    pid = str(runtime.get("process", {}).get("pid") or "")
    base_origin = base_origin or str(runtime.get("launch", {}).get("baseOrigin") or "")
    socket = _find_devtools_socket(pid, runner, timeout_seconds)
    checks["devtoolsSocket"] = {
        "checked": True,
        "passes": bool(socket),
        "socket": socket,
        "message": "webview_devtools_remote socket found" if socket else "webview_devtools_remote socket missing; debug APK must enable WebView debugging",
    }
    if not socket:
        for name in ("devtoolsForward", *_remaining_check_names(require_final_answer, require_source_window, after_forward=True)):
            checks[name] = _unchecked(name)
        return _report(False, runtime, checks, {}, product, query, base_origin, devtools_port)

    forward_result = runner(["adb", "forward", f"tcp:{devtools_port}", f"localabstract:{socket}"], ROOT, timeout_seconds)
    checks["devtoolsForward"] = {
        "checked": True,
        "passes": forward_result.returncode == 0,
        "result": _command_result_to_json(forward_result),
    }
    cdp = None
    final_state: dict[str, Any] = {}
    try:
        if not checks["devtoolsForward"]["passes"]:
            for name in _remaining_check_names(require_final_answer, require_source_window, after_forward=True):
                checks[name] = _unchecked(name)
            return _report(False, runtime, checks, final_state, product, query, base_origin, devtools_port)
        targets = target_fetcher(devtools_port)
        target = _choose_target(targets, base_origin)
        checks["devtoolsTarget"] = {
            "checked": True,
            "passes": bool(target and target.get("webSocketDebuggerUrl")),
            "targetUrl": target.get("url") if target else "",
        }
        if not checks["devtoolsTarget"]["passes"]:
            for name in _remaining_check_names(require_final_answer, require_source_window, after_target=True):
                checks[name] = _unchecked(name)
            return _report(False, runtime, checks, final_state, product, query, base_origin, devtools_port)
        cdp = cdp_client_factory(str(target["webSocketDebuggerUrl"]))
        try:
            ready = cdp.evaluate("document.readyState")
        except Exception as exc:  # noqa: BLE001 - verifier must report CDP failures as data.
            checks["domReady"] = _failed_check("domReady", exc)
            for name in ("domSubmit", "chatCompleted", "localChatStored"):
                checks[name] = _unchecked(name)
            if require_final_answer:
                checks["finalAnswerReadiness"] = _unchecked("finalAnswerReadiness")
            if require_source_window:
                checks["sourceWindow"] = _unchecked("sourceWindow")
            return _report(False, runtime, checks, final_state, product, query, base_origin, devtools_port)
        checks["domReady"] = {"checked": True, "passes": ready in {"interactive", "complete"}, "readyState": ready}
        try:
            submit_result = cdp.evaluate(_submit_expression(query), await_promise=True)
        except Exception as exc:  # noqa: BLE001 - verifier must report CDP failures as data.
            checks["domSubmit"] = _failed_check("domSubmit", exc)
            for name in ("chatCompleted", "localChatStored"):
                checks[name] = _unchecked(name)
            if require_final_answer:
                checks["finalAnswerReadiness"] = _unchecked("finalAnswerReadiness")
            if require_source_window:
                checks["sourceWindow"] = _unchecked("sourceWindow")
            return _report(False, runtime, checks, final_state, product, query, base_origin, devtools_port)
        checks["domSubmit"] = {
            "checked": True,
            "passes": bool(isinstance(submit_result, dict) and submit_result.get("submitted")),
            "result": submit_result,
        }
        try:
            final_state = _wait_for_final_state(cdp, product, timeout_seconds)
        except Exception as exc:  # noqa: BLE001 - verifier must report CDP failures as data.
            checks["chatCompleted"] = _failed_check("chatCompleted", exc)
            checks["localChatStored"] = _unchecked("localChatStored")
            if require_final_answer:
                checks["finalAnswerReadiness"] = _unchecked("finalAnswerReadiness")
            if require_source_window:
                checks["sourceWindow"] = _unchecked("sourceWindow")
            return _report(False, runtime, checks, final_state, product, query, base_origin, devtools_port)
        checks["chatCompleted"] = {
            "checked": True,
            "passes": final_state.get("sessionStatus") == "completed" and final_state.get("answerTextLength", 0) > 0,
            "message": "chat completed in WebView" if final_state.get("sessionStatus") == "completed" else "chat did not complete",
        }
        checks["localChatStored"] = {
            "checked": True,
            "passes": final_state.get("sessionStatus") == "completed" and final_state.get("answerTextLength", 0) > 0,
            "message": "completed chat persisted in localStorage",
        }
        if require_final_answer:
            checks["finalAnswerReadiness"] = {
                "checked": True,
                "passes": final_state.get("answerReadiness") == "final_answer" and final_state.get("writerStatus") == "completed",
                "answerReadiness": final_state.get("answerReadiness") or "",
                "writerStatus": final_state.get("writerStatus") or "",
                "writerMode": final_state.get("writerMode") or "",
                "message": "LLM final answer rendered in WebView"
                if final_state.get("answerReadiness") == "final_answer" and final_state.get("writerStatus") == "completed"
                else "completed chat is not a final LLM writer answer",
        }
        if require_source_window:
            try:
                source_window = cdp.evaluate(_source_window_expression(), await_promise=True)
            except Exception as exc:  # noqa: BLE001 - verifier must report CDP failures as data.
                checks["sourceWindow"] = _failed_check("sourceWindow", exc)
                return _report(False, runtime, checks, final_state, product, query, base_origin, devtools_port)
            source_window_passes = bool(
                isinstance(source_window, dict)
                and source_window.get("clicked") is True
                and source_window.get("dialogOpen") is True
                and source_window.get("textLength", 0) > 0
                and source_window.get("highlightTextLength", 0) > 0
                and source_window.get("badVisible") is not True
            )
            checks["sourceWindow"] = {
                "checked": True,
                "passes": source_window_passes,
                "result": source_window,
                "message": "citation/source-window opened with highlighted source text and no raw source markers"
                if source_window_passes
                else "citation/source-window did not open cleanly with highlighted source text",
            }
    finally:
        if cdp is not None:
            cdp.close()
        runner(["adb", "forward", "--remove", f"tcp:{devtools_port}"], ROOT, timeout_seconds)
    passes = all(check.get("passes") is True for check in checks.values())
    return _report(passes, runtime, checks, final_state, product, query, base_origin, devtools_port)


def _runtime_check(runtime: dict[str, Any]) -> dict[str, Any]:
    return {
        "checked": True,
        "passes": bool(
            runtime.get("passes") is True
            and runtime.get("process", {}).get("passes") is True
            and runtime.get("process", {}).get("pid")
            and runtime.get("launch", {}).get("passes") is True
        ),
        "pid": str(runtime.get("process", {}).get("pid") or ""),
        "message": "runtime launch proof present",
    }


def _remaining_check_names(
    require_final_answer: bool,
    require_source_window: bool = False,
    *,
    after_forward: bool = False,
    after_target: bool = False,
) -> tuple[str, ...]:
    names = ("devtoolsSocket", "devtoolsForward", "devtoolsTarget", "domReady", "domSubmit", "chatCompleted", "localChatStored")
    if after_forward:
        names = ("devtoolsTarget", "domReady", "domSubmit", "chatCompleted", "localChatStored")
    if after_target:
        names = ("domReady", "domSubmit", "chatCompleted", "localChatStored")
    if require_final_answer:
        names = (*names, "finalAnswerReadiness")
    if require_source_window:
        names = (*names, "sourceWindow")
    return names


def _find_devtools_socket(pid: str, runner: CommandRunner, timeout_seconds: int) -> str:
    deadline = time.monotonic() + max(timeout_seconds, 1)
    while True:
        result = runner(["adb", "shell", "cat", "/proc/net/unix"], ROOT, min(timeout_seconds, 10))
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if "webview_devtools_remote" not in line:
                    continue
                name = line.split()[-1].lstrip("@")
                if pid and name.endswith(f"_{pid}"):
                    return name
                if not pid:
                    return name
        if time.monotonic() >= deadline:
            return ""
        time.sleep(1)


def _choose_target(targets: list[dict[str, Any]], base_origin: str) -> dict[str, Any]:
    origin = str(base_origin or "").rstrip("/")
    for target in targets:
        if (
            origin
            and str(target.get("url") or "").startswith(origin)
            and target.get("type") == "page"
            and target.get("webSocketDebuggerUrl")
        ):
            return target
    for target in targets:
        if origin and str(target.get("url") or "").startswith(origin) and target.get("webSocketDebuggerUrl"):
            return target
    for target in targets:
        if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
            return target
    for target in targets:
        if target.get("webSocketDebuggerUrl"):
            return target
    return {}


def _submit_expression(query: str) -> str:
    encoded = json.dumps(query, ensure_ascii=False)
    return f"""(async () => {{
      const input = document.querySelector('[data-chat-input], [data-query-input]');
      const form = document.querySelector('[data-islam-chat-form], [data-tcm-chat-form], [data-simli-chat-form], [data-chat-form], form[data-chat-entry]') || (input ? input.closest('form') : null);
      if (!input || !form) return {{submitted:false, error:'missing input or form'}};
      input.value = {encoded};
      input.dispatchEvent(new Event('input', {{bubbles:true}}));
      form.requestSubmit();
      return {{submitted:true, value: input.value}};
    }})()"""


def _wait_for_final_state(cdp: Any, product: str, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.monotonic() + max(timeout_seconds, 1)
    last: dict[str, Any] = {}
    while True:
        state = cdp.evaluate(_state_expression(product))
        last = state if isinstance(state, dict) else {}
        if last.get("sessionStatus") == "completed" and last.get("answerTextLength", 0) > 0:
            return last
        if time.monotonic() >= deadline:
            return last
        time.sleep(1)


def _state_expression(product: str) -> str:
    key = json.dumps(f"beta6.chat.1.{product}")
    return f"""(() => {{
      const sessions = JSON.parse(localStorage.getItem({key}) || '[]');
      const session = sessions[0] || {{}};
      const result = session.result || {{}};
      const writer = result.writer || {{}};
      const claimCards = Array.isArray(result.claimCards) ? result.claimCards : [];
      const passageWindows = Array.isArray(result.passageWindows) ? result.passageWindows : [];
      const answer = document.querySelector('[data-answer-sections]');
      const progress = document.querySelector('[data-query-state]');
      const domCitationCount = document.querySelectorAll('[data-answer-sections] button.cite, [data-evidence-list] button.source-open, button.cite, button.source-open').length;
      return {{
        url: location.href,
        jobId: session.jobId || '',
        sessionStatus: session.status || '',
        answerTextLength: (answer && answer.textContent || '').trim().length,
        answerReadiness: result.answerReadiness || '',
        writerStatus: writer.status || '',
        writerMode: writer.mode || '',
        writerProvider: writer.provider || '',
        writerModel: writer.model || '',
        writerCacheHit: writer.cacheHit === true,
        sourceCount: Number(session.sourceCount || 0),
        claimCardCount: claimCards.length,
        citedClaimCardCount: Math.max(claimCards.filter((card) => !!card.citationId).length, domCitationCount),
        domCitationCount,
        passageWindowCount: passageWindows.length,
        progressText: (progress && progress.textContent || '').trim()
      }};
    }})()"""


def _source_window_expression() -> str:
    return """(async () => {
      const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
      const sourceWindowClicked = true;
      const button = document.querySelector('[data-answer-sections] button.cite, [data-evidence-list] button.source-open, button.cite, button.source-open');
      if (!button) {
        return {sourceWindowClicked, clicked:false, dialogOpen:false, textLength:0, highlightTextLength:0, moreButtonCount:0, error:'missing citation or source button'};
      }
      button.click();
      const badPattern = /(\\[(?:META|PRIMARY TEXT|BOUNDARIES|CONTEXT WINDOW)(?:[^\\]]*)?\\]|\\bnull\\b)/i;
      let last = {sourceWindowClicked, clicked:true, dialogOpen:false, textLength:0, highlightTextLength:0, moreButtonCount:0, badVisible:false, dialogText:''};
      for (let i = 0; i < 60; i += 1) {
        await delay(200);
        const dialog = document.querySelector('.source-window-backdrop .source-window');
        const text = document.querySelector('.source-window-text');
        const mark = document.querySelector('.source-window-mark');
        const moreButtons = document.querySelectorAll('.window-more');
        const dialogText = (text && text.textContent || '').trim();
        const highlightText = (mark && mark.textContent || '').trim();
        last = {
          sourceWindowClicked,
          clicked:true,
          dialogOpen:!!dialog,
          textLength:dialogText.length,
          highlightTextLength:highlightText.length,
          moreButtonCount:moreButtons.length,
          badVisible:badPattern.test(dialogText),
          dialogText:dialogText.slice(0, 800),
          highlightText:highlightText.slice(0, 240)
        };
        if (last.dialogOpen && last.textLength > 0 && last.highlightTextLength > 0) return last;
      }
      return last;
    })()"""


def _fetch_devtools_targets(port: int) -> list[dict[str, Any]]:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=10) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data if isinstance(data, list) else []


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _unchecked(name: str) -> dict[str, Any]:
    return {"checked": False, "passes": False, "name": name}


def _failed_check(name: str, exc: Exception) -> dict[str, Any]:
    return {
        "checked": True,
        "passes": False,
        "name": name,
        "error": str(exc),
        "exceptionType": type(exc).__name__,
    }


def _report(
    passes: bool,
    runtime: dict[str, Any],
    checks: dict[str, dict[str, Any]],
    final_state: dict[str, Any],
    product: str,
    query: str,
    base_origin: str,
    devtools_port: int,
) -> dict[str, Any]:
    return {
        "checked": True,
        "passes": passes,
        "product": product,
        "query": query,
        "baseOrigin": base_origin,
        "devtoolsPort": devtools_port,
        "runtimePid": str(runtime.get("process", {}).get("pid") or ""),
        "finalState": final_state,
        "checks": checks,
    }


def _run_command(command: list[str], cwd: Path, timeout_seconds: int) -> CommandResult:
    started = time.monotonic()
    try:
        completed = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True, timeout=timeout_seconds)
        return CommandResult(
            command=command,
            cwd=str(cwd),
            returncode=completed.returncode,
            stdout=completed.stdout[-8000:],
            stderr=completed.stderr[-8000:],
            durationMs=int((time.monotonic() - started) * 1000),
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            command=command,
            cwd=str(cwd),
            returncode=124,
            stdout=(exc.stdout or "")[-8000:] if isinstance(exc.stdout, str) else "",
            stderr=((exc.stderr or "")[-8000:] if isinstance(exc.stderr, str) else "") + "\ntimeout",
            durationMs=int((time.monotonic() - started) * 1000),
        )


def _command_result_to_json(result: CommandResult) -> dict[str, Any]:
    return {
        "command": result.command,
        "cwd": result.cwd,
        "returncode": result.returncode,
        "stdout": result.stdout[-2000:],
        "stderr": result.stderr[-2000:],
        "durationMs": result.durationMs,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-report", type=Path, default=DEFAULT_RUNTIME_REPORT)
    parser.add_argument("--product", default="islam")
    parser.add_argument("--query", default="기도는 몇 번 하나요?")
    parser.add_argument("--base-origin", default="")
    parser.add_argument("--devtools-port", type=int, default=DEFAULT_DEVTOOLS_PORT)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--require-final-answer", action="store_true")
    parser.add_argument("--require-source-window", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = build_report(
        runtime_report_path=args.runtime_report,
        product=args.product,
        query=args.query,
        base_origin=args.base_origin,
        devtools_port=args.devtools_port,
        timeout_seconds=args.timeout_seconds,
        require_final_answer=args.require_final_answer,
        require_source_window=args.require_source_window,
    )
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    if args.json:
        print(encoded)
    else:
        print(("PASS" if report["passes"] else "FAIL") + " android webview submit smoke")
        for key, check in report["checks"].items():
            print(f"{key}: checked={check.get('checked')} pass={check.get('passes')}")
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
