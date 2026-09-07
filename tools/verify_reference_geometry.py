#!/usr/bin/env python3
"""Compare product pages against reference files with browser geometry checks."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = Path("/mnt/d/Downloads/레퍼런스")
CHROME = "/usr/local/bin/chromium-headless-playwright"
PRODUCTS = ("islam", "tcm", "simli")
PRODUCT_PORTS = {"islam": 8061, "tcm": 8062, "simli": 8063}
VIEWPORTS = {
    "mobile": {"width": 360, "height": 740},
    "desktop": {"width": 1280, "height": 720},
}


@dataclass(frozen=True)
class GeometryTarget:
    name: str
    selector: str = ""
    text: str = ""
    required: bool = True
    required_viewports: tuple[str, ...] = ("mobile", "desktop")


@dataclass(frozen=True)
class GeometrySpec:
    product: str
    route_path: str
    reference_files: tuple[str, ...]
    product_selectors: tuple[GeometryTarget, ...]
    reference_selectors: tuple[GeometryTarget, ...]
    order_selectors: tuple[str, ...]
    viewport_anchor: str
    comparable_widths: tuple[tuple[str, str, float], ...] = ()


SPECS = {
    "islam": GeometrySpec(
        product="islam",
        route_path="/islam.html",
        reference_files=("이슬람 참조.html",),
        product_selectors=(
            GeometryTarget("nav", ".nav"),
            GeometryTarget("hero", ".hero"),
            GeometryTarget("queryFrame", ".query-frame"),
            GeometryTarget("sourceBand", ".source-band"),
            GeometryTarget("corpus", ".corpus"),
        ),
        reference_selectors=(
            GeometryTarget("nav", ".nav"),
            GeometryTarget("hero", ".hero"),
            GeometryTarget("queryFrame", ".query-frame"),
            GeometryTarget("corpus", ".corpus"),
        ),
        order_selectors=(".nav", ".hero", ".query-frame", ".source-band", ".corpus"),
        viewport_anchor=".query-frame",
        comparable_widths=(("nav", "nav", 0.08), ("queryFrame", "queryFrame", 0.18), ("corpus", "corpus", 0.12)),
    ),
    "tcm": GeometrySpec(
        product="tcm",
        route_path="/tcm.html",
        reference_files=("한의학참조1.html",),
        product_selectors=(
            GeometryTarget("topbar", ".topbar"),
            GeometryTarget("hero", ".hero"),
            GeometryTarget("askCard", ".ask-card"),
            GeometryTarget("fivePhaseBoard", ".five-phase-board"),
            GeometryTarget("herbBoard", ".herb-board"),
        ),
        reference_selectors=(
            GeometryTarget("topbar", ".topbar"),
            GeometryTarget("hero", ".hero"),
            GeometryTarget("askCard", ".ask-card"),
            GeometryTarget("herbBoard", ".herb-board"),
        ),
        order_selectors=(".topbar", ".hero", ".ask-card", ".herb-board"),
        viewport_anchor=".ask-card",
        comparable_widths=(("topbar", "topbar", 0.08), ("askCard", "askCard", 0.18), ("herbBoard", "herbBoard", 0.24)),
    ),
    "simli": GeometrySpec(
        product="simli",
        route_path="/simli.html",
        reference_files=("심리참조 이중 B · Therapeutic Aurora 사용.html",),
        product_selectors=(
            GeometryTarget("nav", ".b-nav"),
            GeometryTarget("hero", ".b-hero"),
            GeometryTarget("heroCard", ".aurora-hero-card"),
            GeometryTarget("weather", ".aurora-weather"),
            GeometryTarget("quick", ".aurora-quick"),
            GeometryTarget("work", ".aurora-work"),
        ),
        reference_selectors=(
            GeometryTarget("variantLabel", text="B · Therapeutic Aurora", required=False),
            GeometryTarget("heroHeadline", text="가만히 머무는", required=False),
            GeometryTarget("weatherTitle", text="오늘의 마음 날씨", required=False),
        ),
        order_selectors=(".b-nav", ".b-hero", ".aurora-quick", ".aurora-work"),
        viewport_anchor=".b-hero",
    ),
}


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


def product_url(base_urls: dict[str, str], spec: GeometrySpec) -> str:
    return urljoin(base_urls[spec.product].rstrip("/") + "/", spec.route_path.lstrip("/"))


def reference_url(spec: GeometrySpec) -> str:
    return (REFERENCE_ROOT / spec.reference_files[0]).resolve().as_uri()


def box_to_json(box: dict[str, float] | None) -> dict[str, float] | None:
    if not box:
        return None
    return {key: round(float(box[key]), 3) for key in ("x", "y", "width", "height")}


def find_text_box(page: Any, text: str) -> dict[str, float] | None:
    return page.evaluate(
        """needle => {
          const candidates = [];
          const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
          while (walker.nextNode()) {
            const node = walker.currentNode;
            if (!node.textContent || !node.textContent.includes(needle)) continue;
            const rect = node.getBoundingClientRect();
            if (rect.width <= 0 || rect.height <= 0) continue;
            candidates.push({
              x: rect.x,
              y: rect.y,
              width: rect.width,
              height: rect.height,
              area: rect.width * rect.height
            });
          }
          candidates.sort((left, right) => left.area - right.area);
          const best = candidates[0];
          return best ? {x: best.x, y: best.y, width: best.width, height: best.height} : null;
        }""",
        text,
    )


def dry_route(product: str, viewport: str, base_urls: dict[str, str]) -> dict[str, Any]:
    spec = SPECS[product]
    return {
        "product": product,
        "viewport": viewport,
        "productUrl": product_url(base_urls, spec),
        "referenceUrl": reference_url(spec),
        "passes": True,
        "dryRun": True,
    }


def collect_target_geometry(page: Any, targets: tuple[GeometryTarget, ...], viewport: str) -> dict[str, Any]:
    geometry: dict[str, Any] = {}
    for target in targets:
        required = target.required and viewport in target.required_viewports
        found = True
        error = ""
        box = None
        try:
            if target.selector:
                locator = page.locator(target.selector).first
                if locator.count() < 1:
                    found = False
                else:
                    box = locator.bounding_box(timeout=1500)
                    found = bool(box and box.get("width", 0) > 0 and box.get("height", 0) > 0)
            else:
                box = find_text_box(page, target.text)
                found = bool(box and box.get("width", 0) > 0 and box.get("height", 0) > 0)
        except Exception as exc:  # noqa: BLE001 - verifier returns browser errors as data.
            found = False
            error = str(exc)
        geometry[target.name] = {
            "selector": target.selector or None,
            "text": target.text or None,
            "required": required,
            "found": found,
            "box": box_to_json(box),
            "error": error,
        }
    return geometry


def selector_order(page: Any, selectors: tuple[str, ...]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    previous_y = -1.0
    ordered = True
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            box = locator.bounding_box(timeout=1000) if locator.count() else None
        except Exception:
            box = None
        if not box:
            entries.append({"selector": selector, "found": False, "y": None})
            ordered = False
            continue
        y_value = float(box["y"])
        if y_value + 1 < previous_y:
            ordered = False
        previous_y = max(previous_y, y_value)
        entries.append({"selector": selector, "found": True, "y": round(y_value, 3)})
    return {"passes": ordered, "entries": entries}


def no_horizontal_overflow(page: Any) -> dict[str, Any]:
    layout = page.evaluate(
        """() => ({
          scrollWidth: Math.max(document.documentElement.scrollWidth, document.body ? document.body.scrollWidth : 0),
          innerWidth: window.innerWidth
        })"""
    )
    scroll_width = int(layout["scrollWidth"])
    inner_width = int(layout["innerWidth"])
    return {"passes": scroll_width <= inner_width + 1, "scrollWidth": scroll_width, "innerWidth": inner_width}


def viewport_coverage(page: Any, selector: str, reference_box: dict[str, float] | None = None) -> dict[str, Any]:
    try:
        box = page.locator(selector).first.bounding_box(timeout=1200)
    except Exception:
        box = None
    height = int(page.evaluate("() => window.innerHeight"))
    if not box:
        return {"passes": False, "selector": selector, "box": None, "viewportHeight": height}
    top = float(box["y"])
    bottom = top + float(box["height"])
    visible = bottom >= 0 and top <= height
    meaningfully_visible = top < height * 0.92
    reference_matched_below_fold = False
    if reference_box and float(reference_box.get("y", 0)) > height:
        reference_matched_below_fold = top <= float(reference_box["y"]) + 40
    return {
        "passes": bool((visible and meaningfully_visible) or reference_matched_below_fold),
        "selector": selector,
        "box": box_to_json(box),
        "referenceBox": reference_box,
        "referenceMatchedBelowFold": reference_matched_below_fold,
        "viewportHeight": height,
    }


def required_geometry_passes(geometry: dict[str, Any]) -> bool:
    return all((not item["required"]) or item["found"] for item in geometry.values())


def reference_anchor_box(reference_geometry: dict[str, Any], selector: str) -> dict[str, float] | None:
    for item in reference_geometry.values():
        if item.get("selector") == selector and item.get("box"):
            return item["box"]
    return None


def width_comparisons(product_geometry: dict[str, Any], reference_geometry: dict[str, Any], spec: GeometrySpec, viewport: str) -> list[dict[str, Any]]:
    if viewport != "desktop":
        return []
    comparisons: list[dict[str, Any]] = []
    for product_name, reference_name, tolerance in spec.comparable_widths:
        product_box = (product_geometry.get(product_name) or {}).get("box")
        reference_box = (reference_geometry.get(reference_name) or {}).get("box")
        if not product_box or not reference_box:
            comparisons.append(
                {
                    "productTarget": product_name,
                    "referenceTarget": reference_name,
                    "passes": False,
                    "reason": "missing box",
                }
            )
            continue
        reference_width = max(float(reference_box["width"]), 1.0)
        product_width = float(product_box["width"])
        delta_ratio = abs(product_width - reference_width) / reference_width
        comparisons.append(
            {
                "productTarget": product_name,
                "referenceTarget": reference_name,
                "productWidth": round(product_width, 3),
                "referenceWidth": round(reference_width, 3),
                "deltaRatio": round(delta_ratio, 4),
                "tolerance": tolerance,
                "passes": delta_ratio <= tolerance,
            }
        )
    return comparisons


def run_route(browser: Any, spec: GeometrySpec, viewport: str, base_urls: dict[str, str], timeout_ms: int) -> dict[str, Any]:
    viewport_spec = VIEWPORTS[viewport]
    context = browser.new_context(viewport=viewport_spec, java_script_enabled=True, ignore_https_errors=True)
    product_page = context.new_page()
    reference_page = context.new_page()
    console_errors: list[str] = []
    page_errors: list[str] = []
    product_page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    product_page.on("pageerror", lambda error: page_errors.append(str(error)))
    status = 0
    reference_status = 0
    error = ""
    product_target_url = product_url(base_urls, spec)
    reference_target_url = reference_url(spec)
    try:
        response = product_page.goto(product_target_url, wait_until="domcontentloaded", timeout=timeout_ms)
        status = response.status if response else 0
        product_page.wait_for_timeout(250)
        reference_response = reference_page.goto(reference_target_url, wait_until="domcontentloaded", timeout=timeout_ms)
        reference_status = reference_response.status if reference_response else 200
        reference_page.wait_for_timeout(250)
    except Exception as exc:  # noqa: BLE001 - keep failing route observable.
        error = str(exc)
    product_geometry = collect_target_geometry(product_page, spec.product_selectors, viewport)
    reference_geometry = collect_target_geometry(reference_page, spec.reference_selectors, viewport)
    overflow = no_horizontal_overflow(product_page)
    coverage = viewport_coverage(product_page, spec.viewport_anchor, reference_anchor_box(reference_geometry, spec.viewport_anchor))
    order = selector_order(product_page, spec.order_selectors)
    comparisons = width_comparisons(product_geometry, reference_geometry, spec, viewport)
    comparisons_pass = all(item["passes"] for item in comparisons)
    product_geometry_passes = required_geometry_passes(product_geometry)
    reference_geometry_passes = required_geometry_passes(reference_geometry)
    passes = (
        not error
        and 200 <= status < 400
        and reference_status in (0, 200)
        and not console_errors
        and not page_errors
        and product_geometry_passes
        and reference_geometry_passes
        and overflow["passes"]
        and coverage["passes"]
        and order["passes"]
        and comparisons_pass
    )
    context.close()
    return {
        "product": spec.product,
        "viewport": viewport,
        "productUrl": product_target_url,
        "referenceUrl": reference_target_url,
        "passes": passes,
        "status": status,
        "referenceStatus": reference_status,
        "error": error,
        "consoleErrors": console_errors,
        "pageErrors": page_errors,
        "productGeometry": product_geometry,
        "referenceGeometry": reference_geometry,
        "noHorizontalOverflow": overflow,
        "viewportCoverage": coverage,
        "selectorOrder": order,
        "widthComparisons": comparisons,
    }


def run_browser_routes(base_urls: dict[str, str], timeout_ms: int) -> list[dict[str, Any]]:
    from playwright.sync_api import sync_playwright

    reports: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=CHROME,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            for product in PRODUCTS:
                spec = SPECS[product]
                for viewport in ("mobile", "desktop"):
                    reports.append(run_route(browser, spec, viewport, base_urls, timeout_ms))
        finally:
            browser.close()
    return reports


def product_contracts() -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    for product in PRODUCTS:
        spec = SPECS[product]
        products.append(
            {
                "product": product,
                "routePath": spec.route_path,
                "referenceFiles": list(spec.reference_files),
                "productSelectors": [target.selector for target in spec.product_selectors if target.selector],
                "referenceSelectors": [
                    target.selector if target.selector else f"text:{target.text}" for target in spec.reference_selectors
                ],
                "orderSelectors": list(spec.order_selectors),
                "viewportAnchor": spec.viewport_anchor,
            }
        )
    return products


def build_report(base_urls: dict[str, str], dry_run: bool, timeout_ms: int) -> dict[str, Any]:
    routes = (
        [dry_route(product, viewport, base_urls) for product in PRODUCTS for viewport in ("mobile", "desktop")]
        if dry_run
        else run_browser_routes(base_urls, timeout_ms)
    )
    passes = all(route["passes"] for route in routes)
    return {
        "passes": passes,
        "dryRun": dry_run,
        "browser": {"engine": "chromium", "executablePath": CHROME},
        "referenceRoot": str(REFERENCE_ROOT),
        "viewports": VIEWPORTS,
        "baseUrls": base_urls,
        "contract": {
            "scope": "browser geometry drift gate",
            "checks": [
                "reference file opens",
                "required product bounding boxes exist",
                "required reference bounding boxes exist",
                "no horizontal overflow",
                "viewport anchor visible",
                "selector vertical order",
                "desktop width drift for comparable elements",
            ],
            "limits": "This is geometry drift detection, not pixel-perfect visual diff.",
        },
        "products": product_contracts(),
        "routes": routes,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="write JSON to stdout")
    parser.add_argument("--dry-run", action="store_true", help="emit contract without launching Chromium")
    parser.add_argument("--output", help="write JSON report to this file")
    parser.add_argument("--base-url", action="append", default=[], help="override product base URL, format product=url")
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
        print(("PASS" if report["passes"] else "FAIL") + " reference browser geometry")
        for route in report["routes"]:
            state = "PASS" if route["passes"] else "FAIL"
            print(f"{state} {route['product']} {route['viewport']}: {route['productUrl']}")
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
