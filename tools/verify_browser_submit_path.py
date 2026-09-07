#!/usr/bin/env python3
"""Verify a real browser landing-to-chat submit path with source grounding."""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


PRODUCTS = ("islam", "tcm", "simli")
PRODUCT_PORTS = {"islam": 8061, "tcm": 8062, "simli": 8063}
PRODUCT_QUERIES = {
    "islam": "사회주의는 하람임? 학파와 원칙별로 근거를 정리해줘",
    "tcm": "감초를 임신 중 써도 되는지 본초 금기 근거로 정리해줘",
    "simli": "요즘 잠이 안 오고 계속 불안합니다. 가능한 가설과 다음 상담에서 볼 점을 근거로 정리해줘",
}
CHROME = "/usr/local/bin/chromium-headless-playwright"
NETWORK_BPS = 1_000_000
NETWORK_LATENCY_MS = 300
CPU_THROTTLING_RATE = 4
VIEWPORTS = {
    "mobile": {"width": 360, "height": 740},
    "desktop": {"width": 1280, "height": 720},
}
EXPECTED_PROVIDER = "lawkey_gemini_generate_content"
EXPECTED_MODEL = "gemma-4-26b-a4b-it"


def default_base_url(product: str) -> str:
    return f"http://127.0.0.1:{PRODUCT_PORTS[product]}"


def route(base_url: str, product: str, kind: str) -> str:
    suffix = "" if kind == "landing" else "-chat"
    return urllib.parse.urljoin(base_url.rstrip("/") + "/", f"{product}{suffix}.html")


def dry_report(product: str, base_url: str, query: str, viewport: str, timeout_seconds: float) -> dict[str, Any]:
    return {
        "passes": True,
        "dryRun": True,
        "product": product,
        "query": query,
        "baseUrl": base_url.rstrip("/"),
        "routes": {"landing": route(base_url, product, "landing"), "chat": route(base_url, product, "chat")},
        "browser": {"engine": "chromium", "executablePath": CHROME},
        "deviceProfile": {
            "name": f"third-world-legacy-phone-{viewport}",
            "viewport": VIEWPORTS[viewport],
            "cpuThrottlingRate": CPU_THROTTLING_RATE,
            "memoryBudgetMb": 512,
        },
        "network": {"bps": NETWORK_BPS, "label": "1Mbps", "latencyMs": NETWORK_LATENCY_MS},
        "timeoutSeconds": timeout_seconds,
        "checks": _dry_checks(),
    }


def _dry_checks() -> dict[str, dict[str, Any]]:
    names = (
        "landingSubmit",
        "chatNavigation",
        "progressVisible",
        "finalRendered",
        "sourceWindow",
        "localChatStored",
        "resultGemma4",
        "sourceGrounding",
        "browserClean",
        "layout",
    )
    return {name: {"passes": True, "dryRun": True} for name in names}


def run_live(
    *,
    product: str,
    base_url: str,
    query: str,
    language: str,
    viewport: str,
    timeout_seconds: float,
    min_answer_chars: int,
    min_sources: int,
    min_cited_claims: int,
) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    clean_base = base_url.rstrip("/")
    landing_url = route(clean_base, product, "landing")
    chat_url = route(clean_base, product, "chat")
    timeout_ms = int(max(5, timeout_seconds) * 1000)
    console_errors: list[str] = []
    page_errors: list[str] = []
    progress_samples: list[dict[str, Any]] = []
    error = ""
    source_window: dict[str, Any] = {
        "opened": False,
        "highlightTextLength": 0,
        "moreButtonCount": 0,
        "error": "",
    }
    ui: dict[str, Any] = {}
    result: dict[str, Any] = {}
    started = time.monotonic()
    shell_dom_content_loaded_ms = 0

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=CHROME,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            viewport=VIEWPORTS[viewport],
            java_script_enabled=True,
            ignore_https_errors=True,
        )
        page = context.new_page()
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        client = context.new_cdp_session(page)
        client.send("Network.enable")
        client.send(
            "Network.emulateNetworkConditions",
            {
                "offline": False,
                "latency": NETWORK_LATENCY_MS,
                "downloadThroughput": NETWORK_BPS / 8,
                "uploadThroughput": NETWORK_BPS / 8,
            },
        )
        client.send("Emulation.setCPUThrottlingRate", {"rate": CPU_THROTTLING_RATE})
        try:
            nav_started = time.monotonic()
            response = page.goto(landing_url, wait_until="domcontentloaded", timeout=timeout_ms)
            shell_dom_content_loaded_ms = int(round((time.monotonic() - nav_started) * 1000))
            if not response or response.status >= 400:
                raise RuntimeError(f"landing returned status {response.status if response else 0}")
            page.locator(
                "[data-chat-entry] [data-query-input], "
                "[data-chat-entry] [data-chat-input], "
                "[data-query-input], "
                "[data-chat-input]"
            ).first.fill(query)
            language_select = page.locator("[data-language]").first
            if language_select.count():
                language_select.select_option(language)
            page.locator("[data-chat-entry]").evaluate("form => form.requestSubmit()")
            page.wait_for_url(f"**/{product}-chat.html**", timeout=timeout_ms)
            page.wait_for_selector("[data-query-state]", state="attached", timeout=timeout_ms)
            ui, progress_samples = wait_for_final_ui(
                page=page,
                product=product,
                timeout_seconds=timeout_seconds,
            )
            source_window = verify_source_window(page, timeout_ms)
            result = fetch_result_from_session(clean_base, ui.get("session") or {}, ui.get("sessionToken") or "")
        except Exception as exc:  # noqa: BLE001 - verifier reports failures as data.
            error = str(exc)
            try:
                ui = read_ui_state(page, product)
            except Exception:  # noqa: BLE001
                ui = {}
        finally:
            context.close()
            browser.close()

    wall_clock_seconds = round(time.monotonic() - started, 3)
    checks = build_checks(
        error=error,
        product=product,
        landing_url=landing_url,
        chat_url=chat_url,
        page_url=ui.get("url", ""),
        progress_samples=progress_samples,
        ui=ui,
        result=result,
        source_window=source_window,
        console_errors=console_errors,
        page_errors=page_errors,
        min_answer_chars=min_answer_chars,
        min_sources=min_sources,
        min_cited_claims=min_cited_claims,
    )
    return {
        "passes": all(check["passes"] for check in checks.values()),
        "dryRun": False,
        "product": product,
        "query": query,
        "language": language,
        "baseUrl": clean_base,
        "routes": {"landing": landing_url, "chat": chat_url},
        "browser": {"engine": "chromium", "executablePath": CHROME},
        "deviceProfile": {
            "name": f"third-world-legacy-phone-{viewport}",
            "viewport": VIEWPORTS[viewport],
            "cpuThrottlingRate": CPU_THROTTLING_RATE,
            "memoryBudgetMb": 512,
        },
        "network": {"bps": NETWORK_BPS, "label": "1Mbps", "latencyMs": NETWORK_LATENCY_MS},
        "timeoutSeconds": timeout_seconds,
        "wallClockSeconds": wall_clock_seconds,
        "shellDomContentLoadedMs": shell_dom_content_loaded_ms,
        "error": error,
        "consoleErrors": console_errors,
        "pageErrors": page_errors,
        "progressSamples": progress_samples[-20:],
        "ui": compact_ui(ui),
        "metrics": result_metrics(result),
        "stageTimings": compact_stage_timings(result.get("beta6")),
        "writer": compact_llm_stage(result.get("writer")),
        "selector": compact_llm_stage(result.get("selector")),
        "sourceWindow": source_window,
        "checks": checks,
    }


def wait_for_final_ui(*, page: Any, product: str, timeout_seconds: float) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    deadline = time.monotonic() + timeout_seconds
    samples: list[dict[str, Any]] = []
    last_ui: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last_ui = read_ui_state(page, product)
        sample = {
            "elapsedSeconds": round(time.monotonic() - (deadline - timeout_seconds), 1),
            "stage": last_ui.get("progressStage", ""),
            "stateText": last_ui.get("stateText", ""),
            "sessionStatus": (last_ui.get("session") or {}).get("status", ""),
            "jobId": (last_ui.get("session") or {}).get("jobId", ""),
            "citeCount": last_ui.get("citeCount", 0),
            "sourceOpenCount": last_ui.get("sourceOpenCount", 0),
            "answerTextLength": last_ui.get("answerTextLength", 0),
        }
        if not samples or samples[-1] != sample:
            samples.append(sample)
        if is_final_ui(last_ui):
            return last_ui, samples
        page.wait_for_timeout(1000)
    raise TimeoutError("timed out waiting for final rendered browser answer")


def read_ui_state(page: Any, product: str) -> dict[str, Any]:
    return page.evaluate(
        """product => {
          const state = document.querySelector("[data-query-state]");
          const answer = document.querySelector("[data-answer-sections]");
          const evidence = document.querySelector("[data-evidence-list]");
          const sourceCount = document.querySelector("[data-source-count]");
          const sessions = JSON.parse(localStorage.getItem(`beta6.chat.1.${product}`) || "[]");
          const session = sessions[0] || null;
          const sessionToken = localStorage.getItem(`beta6.sessionToken.${product}`) || "";
          const stateStyle = state ? getComputedStyle(state) : null;
          const stateVisible = !!(state && stateStyle && stateStyle.display !== "none" && stateStyle.visibility !== "hidden" && state.getClientRects().length > 0);
          return {
            url: location.href,
            progressStage: state ? state.getAttribute("data-progress-stage") || "" : "",
            progressPercent: state ? state.getAttribute("data-progress-percent") || "" : "",
            stateText: state ? state.innerText || state.textContent || "" : "",
            stateVisible,
            answerTextLength: answer ? (answer.innerText || "").length : 0,
            evidenceTextLength: evidence ? (evidence.innerText || "").length : 0,
            sourceCountText: sourceCount ? sourceCount.innerText || sourceCount.textContent || "" : "",
            citeCount: document.querySelectorAll(".cite").length,
            sourceOpenCount: document.querySelectorAll(".source-open").length,
            sourceCardCount: document.querySelectorAll(".source-card").length,
            scrollWidth: Math.max(document.documentElement.scrollWidth, document.body ? document.body.scrollWidth : 0),
            innerWidth: window.innerWidth,
            session,
            sessionToken
          };
        }""",
        product,
    )


def is_final_ui(ui: dict[str, Any]) -> bool:
    session = ui.get("session") or {}
    return (
        session.get("status") == "completed"
        and bool(session.get("jobId"))
        and (bool(session.get("result")) or ui.get("answerTextLength", 0) > 500)
        and int(ui.get("citeCount") or 0) > 0
        and int(ui.get("sourceOpenCount") or 0) > 0
    )


def fetch_result_from_session(base_url: str, session: dict[str, Any], session_token: str = "") -> dict[str, Any]:
    job_id = str(session.get("jobId") or "")
    access_token = str(session.get("accessToken") or session.get("jobAccessToken") or "")
    if not job_id:
        return session.get("result") if isinstance(session.get("result"), dict) else {}
    if not access_token:
        return session.get("result") if isinstance(session.get("result"), dict) else {}
    params = urllib.parse.urlencode({"token": access_token, "session": session_token})
    url = f"{base_url.rstrip('/')}/api/jobs/{urllib.parse.quote(job_id)}/result?{params}"
    request = urllib.request.Request(url, headers={"X-Beta6-Session-Token": session_token})
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - local/tunnel verifier URL is explicit.
        body = response.read().decode("utf-8")
    return json.loads(body)


def verify_source_window(page: Any, timeout_ms: int) -> dict[str, Any]:
    report = {"opened": False, "highlightTextLength": 0, "moreButtonCount": 0, "error": ""}
    try:
        first_citation = page.locator(".cite").first
        if first_citation.count():
            first_citation.click(timeout=timeout_ms)
        else:
            page.locator(".source-open").first.click(timeout=timeout_ms)
        page.wait_for_selector(".source-window-mark", timeout=timeout_ms)
        mark = page.locator(".source-window-mark").first.inner_text(timeout=timeout_ms)
        report["opened"] = True
        report["highlightTextLength"] = len(mark)
        report["moreButtonCount"] = page.locator(".window-more").count()
    except Exception as exc:  # noqa: BLE001
        report["error"] = str(exc)
    return report


def build_checks(
    *,
    error: str,
    product: str,
    landing_url: str,
    chat_url: str,
    page_url: str,
    progress_samples: list[dict[str, Any]],
    ui: dict[str, Any],
    result: dict[str, Any],
    source_window: dict[str, Any],
    console_errors: list[str],
    page_errors: list[str],
    min_answer_chars: int,
    min_sources: int,
    min_cited_claims: int,
) -> dict[str, dict[str, Any]]:
    session = ui.get("session") or {}
    metrics = result_metrics(result)
    writer = compact_llm_stage(result.get("writer"))
    selector = compact_llm_stage(result.get("selector"))
    progress_seen = [
        item
        for item in progress_samples
        if item.get("stage") or item.get("sessionStatus") in {"queued", "running"} or "%" in str(item.get("stateText") or "")
    ]
    no_overflow = int(ui.get("scrollWidth") or 0) <= int(ui.get("innerWidth") or 0) + 1 if ui else False
    final_answer_rendered = int(ui.get("answerTextLength") or 0) >= min(500, min_answer_chars)
    source_grounding_ok = (
        metrics["sourceCount"] >= min_sources
        and metrics["claimCardCount"] >= min_cited_claims
        and metrics["citedClaimCount"] >= min_cited_claims
        and metrics["citationMapCount"] > 0
    )
    return {
        "landingSubmit": {
            "passes": not error and page_url.startswith(chat_url),
            "landingUrl": landing_url,
            "pageUrl": page_url,
        },
        "chatNavigation": {
            "passes": f"/{product}-chat.html" in page_url,
            "expected": chat_url,
            "actual": page_url,
        },
        "progressVisible": {
            "passes": bool(progress_seen) and bool(ui.get("stateVisible")),
            "sampleCount": len(progress_samples),
            "stateVisible": bool(ui.get("stateVisible")),
            "stages": sorted({str(item.get("stage") or "") for item in progress_samples if item.get("stage")}),
        },
        "finalRendered": {
            "passes": final_answer_rendered and int(ui.get("citeCount") or 0) >= min_cited_claims,
            "answerTextLength": ui.get("answerTextLength", 0),
            "citeCount": ui.get("citeCount", 0),
            "sourceOpenCount": ui.get("sourceOpenCount", 0),
        },
        "sourceWindow": {
            "passes": source_window.get("opened") is True
            and int(source_window.get("highlightTextLength") or 0) > 0
            and int(source_window.get("moreButtonCount") or 0) >= 2,
            **source_window,
        },
        "localChatStored": {
            "passes": session.get("status") == "completed" and bool(session.get("jobId")) and bool(session.get("result")),
            "status": session.get("status", ""),
            "jobId": session.get("jobId", ""),
            "hasResult": bool(session.get("result")),
        },
        "resultGemma4": {
            "passes": writer.get("status") == "completed"
            and writer.get("provider") == EXPECTED_PROVIDER
            and writer.get("model") == EXPECTED_MODEL
            and selector.get("status") == "completed"
            and selector.get("provider") == EXPECTED_PROVIDER
            and selector.get("model") == EXPECTED_MODEL,
            "writer": writer,
            "selector": selector,
        },
        "sourceGrounding": {
            "passes": source_grounding_ok and metrics["answerChars"] >= min_answer_chars,
            **metrics,
        },
        "browserClean": {
            "passes": not error and not console_errors and not page_errors,
            "error": error,
            "consoleErrors": console_errors,
            "pageErrors": page_errors,
        },
        "layout": {
            "passes": no_overflow,
            "scrollWidth": ui.get("scrollWidth", 0),
            "innerWidth": ui.get("innerWidth", 0),
        },
    }


def result_metrics(result: dict[str, Any]) -> dict[str, int]:
    beta6 = result.get("beta6") if isinstance(result.get("beta6"), dict) else {}
    sources = result.get("sources") if isinstance(result.get("sources"), list) else []
    claim_cards = result.get("claimCards") if isinstance(result.get("claimCards"), list) else []
    cited_claims = result.get("citedClaimCards") if isinstance(result.get("citedClaimCards"), list) else []
    citation_map = result.get("citationMap") if isinstance(result.get("citationMap"), dict) else {}
    return {
        "answerChars": len(str(result.get("answer") or result.get("answerMarkdown") or "")),
        "sourceCount": len(sources),
        "claimCardCount": len(claim_cards) or int(beta6.get("claimCardCount") or 0),
        "citedClaimCount": len(cited_claims) or int(beta6.get("citedClaimCount") or 0),
        "citationMapCount": len(citation_map),
        "candidateCount": int(beta6.get("candidateCount") or 0),
        "selectedCount": int(beta6.get("selectedCount") or len(sources)),
    }


def compact_llm_stage(stage: Any) -> dict[str, Any]:
    if not isinstance(stage, dict):
        return {"status": "", "provider": "", "model": ""}
    return {
        "status": stage.get("status", ""),
        "provider": stage.get("provider", ""),
        "model": stage.get("model", ""),
        "promptInputBytes": int(stage.get("promptInputBytes") or 0),
    }


def compact_stage_timings(beta6: Any) -> dict[str, Any]:
    if not isinstance(beta6, dict):
        return {"totals": {}, "totalSec": 0.0, "slowest": []}
    raw_totals = beta6.get("stageTimingTotals")
    totals: dict[str, float] = {}
    if isinstance(raw_totals, dict):
        for key, value in raw_totals.items():
            try:
                totals[str(key)] = round(float(value), 3)
            except (TypeError, ValueError):
                continue
    try:
        total_sec = round(float(beta6.get("stageTimingTotalSec") or sum(totals.values())), 3)
    except (TypeError, ValueError):
        total_sec = round(sum(totals.values()), 3)
    return {"totals": totals, "totalSec": total_sec, "slowest": slowest_stages(totals)}


def slowest_stages(totals: dict[str, float], *, limit: int = 5) -> list[dict[str, Any]]:
    return [
        {"stage": stage, "seconds": seconds}
        for stage, seconds in sorted(totals.items(), key=lambda item: item[1], reverse=True)[:limit]
    ]


def compact_ui(ui: dict[str, Any]) -> dict[str, Any]:
    session = ui.get("session") if isinstance(ui.get("session"), dict) else {}
    return {
        "url": ui.get("url", ""),
        "progressStage": ui.get("progressStage", ""),
        "stateText": ui.get("stateText", ""),
        "stateVisible": bool(ui.get("stateVisible")),
        "answerTextLength": ui.get("answerTextLength", 0),
        "citeCount": ui.get("citeCount", 0),
        "sourceOpenCount": ui.get("sourceOpenCount", 0),
        "sourceCardCount": ui.get("sourceCardCount", 0),
        "sourceCountText": ui.get("sourceCountText", ""),
        "scrollWidth": ui.get("scrollWidth", 0),
        "innerWidth": ui.get("innerWidth", 0),
        "session": {
            "sessionId": session.get("sessionId", ""),
            "status": session.get("status", ""),
            "jobId": session.get("jobId", ""),
            "hasAccessToken": bool(session.get("accessToken") or session.get("jobAccessToken")),
            "hasResult": bool(session.get("result")),
            "sourceCount": session.get("sourceCount", 0),
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="write JSON to stdout")
    parser.add_argument("--dry-run", action="store_true", help="emit the submit-path contract without launching Chromium")
    parser.add_argument("--product", choices=PRODUCTS, default="islam")
    parser.add_argument("--base-url", default="", help="split app or tunnel base URL")
    parser.add_argument("--query", default="", help="question to submit through the landing page")
    parser.add_argument("--language", default="ko")
    parser.add_argument("--viewport", choices=tuple(VIEWPORTS), default="mobile")
    parser.add_argument("--timeout", type=float, default=900)
    parser.add_argument("--min-answer-chars", type=int, default=800)
    parser.add_argument("--min-sources", type=int, default=20)
    parser.add_argument("--min-cited-claims", type=int, default=1)
    parser.add_argument("--output", default="", help="write JSON report to this file")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    product = args.product
    base_url = (args.base_url or default_base_url(product)).rstrip("/")
    query = args.query or PRODUCT_QUERIES[product]
    if args.dry_run:
        report = dry_report(product, base_url, query, args.viewport, args.timeout)
    else:
        report = run_live(
            product=product,
            base_url=base_url,
            query=query,
            language=args.language,
            viewport=args.viewport,
            timeout_seconds=args.timeout,
            min_answer_chars=args.min_answer_chars,
            min_sources=args.min_sources,
            min_cited_claims=args.min_cited_claims,
        )
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded + "\n", encoding="utf-8")
    if args.json:
        print(encoded)
    else:
        print("PASS browser submit path" if report["passes"] else "FAIL browser submit path")
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
