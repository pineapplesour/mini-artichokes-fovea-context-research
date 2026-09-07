#!/usr/bin/env python3
"""Verify browser offline submit outbox and active follow behavior."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin


PRODUCTS = ("islam", "tcm", "simli")
PRODUCT_PORTS = {"islam": 8061, "tcm": 8062, "simli": 8063}
CHROME = "/usr/local/bin/chromium-headless-playwright"
NETWORK_BPS = 1_000_000
CPU_THROTTLING_RATE = 4
VIEWPORT = {"width": 360, "height": 740}


def default_base_urls() -> dict[str, str]:
    return {product: f"http://127.0.0.1:{PRODUCT_PORTS[product]}" for product in PRODUCTS}


def parse_base_urls(values: list[str]) -> dict[str, str]:
    result = default_base_urls()
    for value in values:
        if "=" not in value:
            raise SystemExit(f"--base-url must be product=url, got: {value}")
        product, url = value.split("=", 1)
        if product not in PRODUCTS:
            raise SystemExit(f"unknown product for --base-url: {product}")
        result[product] = url
    return result


def chat_url(product: str, base_url: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", f"{product}-chat.html")


def dry_product(product: str, base_url: str) -> dict[str, Any]:
    return {
        "passes": True,
        "dryRun": True,
        "product": product,
        "chatRoute": chat_url(product, base_url),
        "offlineQueued": True,
        "indexedDbOutbox": True,
        "onlineDrained": True,
        "activeSessionFollowed": True,
    }


def local_storage_session(product: str) -> str:
    return f"""() => {{
      const items = JSON.parse(localStorage.getItem("beta6.chat.1.{product}") || "[]");
      return items[0] || null;
    }}"""


def indexed_outbox_count() -> str:
    return """async () => new Promise(resolve => {
      const request = indexedDB.open("beta6-chat-durable-store", 1);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains("sessions")) db.createObjectStore("sessions", {keyPath: "product"});
        if (!db.objectStoreNames.contains("outbox")) db.createObjectStore("outbox", {keyPath: "sessionId"});
      };
      request.onerror = () => resolve(-1);
      request.onsuccess = () => {
        const db = request.result;
        const tx = db.transaction("outbox", "readonly");
        const count = tx.objectStore("outbox").count();
        count.onsuccess = () => resolve(count.result);
        count.onerror = () => resolve(-1);
        tx.oncomplete = () => db.close();
        tx.onerror = () => db.close();
      };
    })"""


def run_product(browser: Any, product: str, base_url: str, timeout_ms: int) -> dict[str, Any]:
    context = browser.new_context(viewport=VIEWPORT, java_script_enabled=True, ignore_https_errors=True)
    context.add_init_script("Object.defineProperty(window, 'EventSource', {value: undefined, configurable: true});")
    page = context.new_page()
    console_errors: list[str] = []
    page_errors: list[str] = []
    page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    client = context.new_cdp_session(page)
    client.send("Network.enable")
    client.send(
        "Network.emulateNetworkConditions",
        {
            "offline": False,
            "latency": 300,
            "downloadThroughput": NETWORK_BPS / 8,
            "uploadThroughput": NETWORK_BPS / 8,
        },
    )
    client.send("Emulation.setCPUThrottlingRate", {"rate": CPU_THROTTLING_RATE})
    state = {"phase": "offline"}
    job_id = f"offline-smoke-{product}"
    access_token = f"access-{product}-offline-smoke"

    def jobs_handler(route: Any, request: Any) -> None:
        if request.method.upper() != "POST":
            route.continue_()
            return
        if state["phase"] == "offline":
            route.abort("internetdisconnected")
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"jobId": job_id, "accessToken": access_token}),
        )

    def status_handler(route: Any, request: Any) -> None:
        if request.method.upper() != "GET":
            route.continue_()
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "jobId": job_id,
                    "status": "running",
                    "elapsedSeconds": 7,
                    "selectedCount": 0,
                    "progress": {
                        "stage": "candidate_search",
                        "label": "후보 검색",
                        "percent": 38,
                        "elapsedSeconds": 7,
                    },
                }
            ),
        )

    context.route(f"**/api/{product}/jobs", jobs_handler)
    context.route(f"**/api/jobs/{job_id}**", status_handler)
    started = time.perf_counter()
    error = ""
    try:
        page.goto(chat_url(product, base_url), wait_until="domcontentloaded", timeout=timeout_ms)
        query = f"offline outbox verifier {product}"
        page.locator("[data-chat-input]").fill(query)
        page.locator(f"[data-{product}-chat-form]").evaluate("form => form.requestSubmit()")
        page.wait_for_function(
            f"""() => {{
              const items = JSON.parse(localStorage.getItem("beta6.chat.1.{product}") || "[]");
              return items[0] && items[0].status === "offline" && items[0].outboxRequest && !items[0].jobId;
            }}""",
            timeout=timeout_ms,
        )
        offline_session = page.evaluate(local_storage_session(product))
        offline_outbox_count = page.evaluate(indexed_outbox_count())
        state["phase"] = "online"
        page.evaluate('window.dispatchEvent(new Event("online"))')
        page.wait_for_function(
            f"""() => {{
              const items = JSON.parse(localStorage.getItem("beta6.chat.1.{product}") || "[]");
              return items[0] && items[0].jobId === "{job_id}" && items[0].status === "running" && !items[0].outboxRequest;
            }}""",
            timeout=timeout_ms,
        )
        page.wait_for_function(
            """() => {
              const state = document.querySelector("[data-query-state]");
              return state && state.getAttribute("data-progress-stage") === "candidate_search";
            }""",
            timeout=timeout_ms,
        )
        online_session = page.evaluate(local_storage_session(product))
        online_outbox_count = page.evaluate(indexed_outbox_count())
        progress_text = page.locator("[data-query-state]").inner_text(timeout=timeout_ms)
    except Exception as exc:  # noqa: BLE001 - report verifier failure as data.
        error = str(exc)
        offline_session = page.evaluate(local_storage_session(product)) if not page.is_closed() else None
        online_session = offline_session
        offline_outbox_count = -1
        online_outbox_count = -1
        progress_text = ""
    wall_ms = int(round((time.perf_counter() - started) * 1000))
    offline_queued = bool(offline_session and offline_session.get("status") == "offline" and offline_session.get("outboxRequest"))
    indexed_db_outbox = offline_outbox_count == 1
    online_drained = bool(online_session and online_session.get("jobId") == job_id and not online_session.get("outboxRequest") and online_outbox_count == 0)
    active_followed = "후보 검색" in progress_text or "Candidate search" in progress_text
    expected_abort_errors = [item for item in console_errors if "ERR_INTERNET_DISCONNECTED" in item]
    unexpected_console_errors = [item for item in console_errors if "ERR_INTERNET_DISCONNECTED" not in item]
    passes = (
        not error
        and not unexpected_console_errors
        and not page_errors
        and offline_queued
        and indexed_db_outbox
        and online_drained
        and active_followed
    )
    context.close()
    return {
        "passes": passes,
        "dryRun": False,
        "product": product,
        "chatRoute": chat_url(product, base_url),
        "wallClockMs": wall_ms,
        "error": error,
        "consoleErrors": console_errors,
        "expectedNetworkAbortErrors": expected_abort_errors,
        "unexpectedConsoleErrors": unexpected_console_errors,
        "pageErrors": page_errors,
        "offlineQueued": offline_queued,
        "indexedDbOutbox": indexed_db_outbox,
        "onlineDrained": online_drained,
        "activeSessionFollowed": active_followed,
        "offlineOutboxCount": offline_outbox_count,
        "onlineOutboxCount": online_outbox_count,
        "jobId": job_id if online_drained else "",
        "progressText": progress_text,
    }


def run_browser(base_urls: dict[str, str], timeout_ms: int) -> dict[str, dict[str, Any]]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=CHROME,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            return {product: run_product(browser, product, base_urls[product], timeout_ms) for product in PRODUCTS}
        finally:
            browser.close()


def build_report(base_urls: dict[str, str], dry_run: bool, timeout_ms: int) -> dict[str, Any]:
    products = (
        {product: dry_product(product, base_urls[product]) for product in PRODUCTS}
        if dry_run
        else run_browser(base_urls, timeout_ms)
    )
    return {
        "passes": all(item["passes"] for item in products.values()),
        "dryRun": dry_run,
        "browser": {"engine": "chromium", "executablePath": CHROME},
        "deviceProfile": {"name": "third-world-legacy-phone-offline", "cpuThrottlingRate": CPU_THROTTLING_RATE},
        "network": {"bps": NETWORK_BPS, "label": "1Mbps", "latencyMs": 300},
        "products": products,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="write JSON to stdout")
    parser.add_argument("--dry-run", action="store_true", help="emit product contract without launching Chromium")
    parser.add_argument("--output", help="write JSON report to this file")
    parser.add_argument("--base-url", action="append", default=[], help="live check, format product=url")
    parser.add_argument("--timeout-ms", type=int, default=15_000, help="per-product timeout")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(parse_base_urls(args.base_url), args.dry_run, args.timeout_ms)
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded + "\n", encoding="utf-8")
    if args.json:
        print(encoded)
    else:
        print(("PASS" if report["passes"] else "FAIL") + " browser offline outbox")
        for product, item in report["products"].items():
            print(
                f"{product}: offline={item['offlineQueued']} idb={item['indexedDbOutbox']} "
                f"drain={item['onlineDrained']} follow={item['activeSessionFollowed']}"
            )
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
