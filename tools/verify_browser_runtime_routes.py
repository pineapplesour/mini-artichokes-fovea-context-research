#!/usr/bin/env python3
"""Run browser-level low-end route timing checks for split product shells."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PRODUCTS = ("islam", "tcm", "simli")
PRODUCT_PORTS = {"islam": 8061, "tcm": 8062, "simli": 8063}
VIEWPORTS = {
    "mobile": {"width": 360, "height": 740},
    "desktop": {"width": 1280, "height": 720},
}
CHROME = "/usr/local/bin/chromium-headless-playwright"
CPU_THROTTLING_RATE = 4
NETWORK_BPS = 1_000_000
BUDGETS = {
    "domContentLoadedMs": 3500,
    "wallClockMs": 6000,
    "jsHeapUsedBytes": 18_000_000,
}


@dataclass(frozen=True)
class RouteSpec:
    product: str
    route_kind: str
    viewport: str
    url: str


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


def manifest_product(product: str) -> dict[str, Any]:
    try:
        manifest = json.loads((WEB / "app-shell-manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    item = (manifest.get("products") or {}).get(product) if isinstance(manifest, dict) else {}
    return item if isinstance(item, dict) else {}


def route_path(product: str, route_kind: str) -> str:
    item = manifest_product(product)
    if route_kind == "landing":
        return str(item.get("landingRoute") or f"/{product}.html")
    if route_kind == "chat":
        route = str(item.get("chatRoute") or f"/{product}-chat.html")
        return f"{route}?q=browser%20runtime%20smoke"
    return f"/{route_kind}.html"


def exposed_extra_pages(product: str) -> list[str]:
    item = manifest_product(product)
    pages = item.get("exposedPages") if isinstance(item, dict) else []
    landing_stem = Path(str(item.get("landingRoute") or f"/{product}.html")).stem
    chat_stem = Path(str(item.get("chatRoute") or f"/{product}-chat.html")).stem
    default_pages = {landing_stem, chat_stem}
    return [page for page in pages if isinstance(page, str) and page not in default_pages]


def route_specs(base_urls: dict[str, str]) -> list[RouteSpec]:
    routes: list[RouteSpec] = []
    for product in PRODUCTS:
        for route_kind in ("landing", "chat"):
            for viewport in ("mobile", "desktop"):
                url = urljoin(base_urls[product].rstrip("/") + "/", route_path(product, route_kind).lstrip("/"))
                routes.append(RouteSpec(product=product, route_kind=route_kind, viewport=viewport, url=url))
        for page in exposed_extra_pages(product):
            for viewport in ("mobile", "desktop"):
                url = urljoin(base_urls[product].rstrip("/") + "/", f"/{page}.html")
                routes.append(RouteSpec(product=product, route_kind=page, viewport=viewport, url=url))
    return routes


def dry_route_report(spec: RouteSpec) -> dict[str, Any]:
    return {
        "product": spec.product,
        "routeKind": spec.route_kind,
        "viewport": spec.viewport,
        "url": spec.url,
        "passes": True,
        "dryRun": True,
    }


def metric_value(metrics: dict[str, Any], name: str) -> float:
    for item in metrics.get("metrics", []):
        if item.get("name") == name:
            return float(item.get("value") or 0)
    return 0.0


def run_route(browser: Any, spec: RouteSpec, timeout_ms: int) -> dict[str, Any]:
    viewport_spec = VIEWPORTS[spec.viewport]
    context = browser.new_context(viewport=viewport_spec, java_script_enabled=True, ignore_https_errors=True)
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
    client.send("Performance.enable")
    started = time.perf_counter()
    status = 0
    error = ""
    try:
        response = page.goto(spec.url, wait_until="domcontentloaded", timeout=timeout_ms)
        status = response.status if response else 0
        page.wait_for_timeout(300)
    except Exception as exc:  # noqa: BLE001 - report browser failure as data.
        error = str(exc)
    wall_clock_ms = int(round((time.perf_counter() - started) * 1000))
    metrics = client.send("Performance.getMetrics")
    nav = page.evaluate(
        """() => {
          const entry = performance.getEntriesByType('navigation')[0];
          return entry ? {
            domContentLoadedEventEnd: entry.domContentLoadedEventEnd,
            startTime: entry.startTime
          } : {domContentLoadedEventEnd: 0, startTime: 0};
        }"""
    )
    layout = page.evaluate(
        """() => ({
          scrollWidth: Math.max(document.documentElement.scrollWidth, document.body ? document.body.scrollWidth : 0),
          innerWidth: window.innerWidth,
          textLength: document.body ? document.body.innerText.length : 0,
          title: document.title
        })"""
    )
    dom_content_loaded_ms = int(round(float(nav.get("domContentLoadedEventEnd") or 0) - float(nav.get("startTime") or 0)))
    js_heap_used = int(metric_value(metrics, "JSHeapUsedSize"))
    no_overflow = int(layout["scrollWidth"]) <= int(layout["innerWidth"]) + 1
    nonblank = int(layout["textLength"]) > 40
    passes = (
        not error
        and 200 <= status < 400
        and not console_errors
        and not page_errors
        and no_overflow
        and nonblank
        and dom_content_loaded_ms <= BUDGETS["domContentLoadedMs"]
        and wall_clock_ms <= BUDGETS["wallClockMs"]
        and js_heap_used <= BUDGETS["jsHeapUsedBytes"]
    )
    context.close()
    return {
        "product": spec.product,
        "routeKind": spec.route_kind,
        "viewport": spec.viewport,
        "url": spec.url,
        "passes": passes,
        "status": status,
        "error": error,
        "consoleErrors": console_errors,
        "pageErrors": page_errors,
        "domContentLoadedMs": dom_content_loaded_ms,
        "wallClockMs": wall_clock_ms,
        "jsHeapUsedBytes": js_heap_used,
        "scrollWidth": int(layout["scrollWidth"]),
        "innerWidth": int(layout["innerWidth"]),
        "noHorizontalOverflow": no_overflow,
        "nonBlank": nonblank,
        "title": layout["title"],
    }


def run_browser_routes(routes: list[RouteSpec], timeout_ms: int) -> list[dict[str, Any]]:
    from playwright.sync_api import sync_playwright

    reports: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=CHROME,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            for spec in routes:
                reports.append(run_route(browser, spec, timeout_ms))
        finally:
            browser.close()
    return reports


def build_report(base_urls: dict[str, str], dry_run: bool, timeout_ms: int) -> dict[str, Any]:
    specs = route_specs(base_urls)
    route_reports = [dry_route_report(spec) for spec in specs] if dry_run else run_browser_routes(specs, timeout_ms)
    passes = all(item["passes"] for item in route_reports)
    return {
        "passes": passes,
        "dryRun": dry_run,
        "browser": {"engine": "chromium", "executablePath": CHROME},
        "deviceProfile": {
            "name": "third-world-legacy-phone-browser",
            "cpuThrottlingRate": CPU_THROTTLING_RATE,
            "memoryBudgetMb": 512,
        },
        "network": {"bps": NETWORK_BPS, "label": "1Mbps", "latencyMs": 300},
        "viewports": VIEWPORTS,
        "budgets": BUDGETS,
        "baseUrls": base_urls,
        "routes": route_reports,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="write JSON to stdout")
    parser.add_argument("--dry-run", action="store_true", help="emit route matrix without launching Chromium")
    parser.add_argument("--output", help="write JSON report to this file")
    parser.add_argument("--base-url", action="append", default=[], help="live check, format product=url")
    parser.add_argument("--timeout-ms", type=int, default=15_000, help="per-route navigation timeout")
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
        print(("PASS" if report["passes"] else "FAIL") + " browser runtime route matrix")
        for item in report["routes"]:
            suffix = "dry" if item.get("dryRun") else f"{item.get('domContentLoadedMs', 0)}ms heap={item.get('jsHeapUsedBytes', 0)}"
            print(f"{item['product']} {item['routeKind']} {item['viewport']}: {suffix}")
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
