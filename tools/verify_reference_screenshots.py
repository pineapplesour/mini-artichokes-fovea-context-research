#!/usr/bin/env python3
"""Capture reference/product screenshots and compute pixel drift evidence."""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from PIL import Image, ImageChops, ImageStat


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = Path("/mnt/d/Downloads/레퍼런스")
CHROME = "/usr/local/bin/chromium-headless-playwright"
PRODUCTS = ("islam", "tcm", "simli")
PRODUCT_PORTS = {"islam": 8061, "tcm": 8062, "simli": 8063}
VIEWPORTS = {
    "mobile": {"width": 360, "height": 740},
    "desktop": {"width": 1280, "height": 720},
}
DEFAULT_SCREENSHOT_DIR = ROOT / "runs" / "reference-screenshot-captures"


@dataclass(frozen=True)
class PixelTarget:
    name: str
    product_selector: str
    reference_selector: str = ""
    compare: bool = True
    required_viewports: tuple[str, ...] = ("mobile", "desktop")


@dataclass(frozen=True)
class ScreenshotSpec:
    product: str
    route_path: str
    reference_file: str
    comparison_mode: str
    selectors: tuple[PixelTarget, ...]
    reference_anchors: tuple[str, ...] = ()
    thresholds: dict[str, float] | None = None
    reference_artboard_anchor: str = ""
    reference_artboard_ancestor_depth: int = 0
    artboard_compare_viewports: tuple[str, ...] = ()


SPECS = {
    "islam": ScreenshotSpec(
        product="islam",
        route_path="/islam.html",
        reference_file="이슬람 참조.html",
        comparison_mode="selector-pixel",
        selectors=(
            PixelTarget("hero", ".hero", ".hero"),
            PixelTarget("queryFrame", ".query-frame", ".query-frame"),
            PixelTarget("corpus", ".corpus", ".corpus", required_viewports=("desktop",)),
        ),
        thresholds={
            "meanAbsoluteError": 35,
            "rmsError": 62,
            "pixelDifferenceRatio": 0.34,
            "perceptualHashDistance": 34,
        },
    ),
    "tcm": ScreenshotSpec(
        product="tcm",
        route_path="/tcm.html",
        reference_file="한의학참조1.html",
        comparison_mode="selector-pixel",
        selectors=(
            PixelTarget("topbar", ".topbar", ".topbar"),
            PixelTarget("askCard", ".ask-card", ".ask-card"),
            PixelTarget("herbBoard", ".herb-board", ".herb-board", required_viewports=("desktop",)),
        ),
        thresholds={
            "meanAbsoluteError": 40,
            "rmsError": 90,
            "pixelDifferenceRatio": 0.26,
            "perceptualHashDistance": 32,
        },
    ),
    "simli": ScreenshotSpec(
        product="simli",
        route_path="/simli.html",
        reference_file="심리참조 이중 B · Therapeutic Aurora 사용.html",
        comparison_mode="artboard-pixel",
        selectors=(
            PixelTarget("hero", ".b-hero", compare=False),
            PixelTarget("heroCard", ".aurora-hero-card", compare=False),
            PixelTarget("weather", ".aurora-weather", compare=False),
        ),
        reference_anchors=("B · Therapeutic Aurora", "가만히 머무는", "오늘의 마음 날씨"),
        reference_artboard_anchor="B · Therapeutic Aurora",
        reference_artboard_ancestor_depth=3,
        artboard_compare_viewports=("desktop",),
        thresholds={
            "meanAbsoluteError": 24,
            "rmsError": 48,
            "pixelDifferenceRatio": 0.32,
            "perceptualHashDistance": 18,
        },
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


def product_url(base_urls: dict[str, str], spec: ScreenshotSpec) -> str:
    return urljoin(base_urls[spec.product].rstrip("/") + "/", spec.route_path.lstrip("/"))


def reference_url(spec: ScreenshotSpec) -> str:
    return (REFERENCE_ROOT / spec.reference_file).resolve().as_uri()


def route_slug(product: str, viewport: str) -> str:
    return f"{product}-{viewport}"


def safe_slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")[:64]


def dry_route(product: str, viewport: str, base_urls: dict[str, str]) -> dict[str, Any]:
    spec = SPECS[product]
    return {
        "product": product,
        "viewport": viewport,
        "productUrl": product_url(base_urls, spec),
        "referenceUrl": reference_url(spec),
        "comparisonMode": spec.comparison_mode,
        "passes": True,
        "dryRun": True,
    }


def image_nonblank(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        extrema = rgb.getextrema()
        ranges = [channel_max - channel_min for channel_min, channel_max in extrema]
        stat = ImageStat.Stat(rgb)
        return {
            "passes": max(ranges) >= 8 and max(stat.rms) >= 8,
            "size": list(rgb.size),
            "channelRanges": ranges,
            "rms": [round(float(value), 3) for value in stat.rms],
        }


def normalized_image(path: Path, size: tuple[int, int] = (320, 220)) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGB").resize(size)


def difference_ratio(diff: Image.Image, threshold: int = 24) -> float:
    data = diff.convert("RGB").tobytes()
    pixel_count = max(len(data) // 3, 1)
    changed = 0
    for index in range(0, len(data), 3):
        if max(data[index], data[index + 1], data[index + 2]) > threshold:
            changed += 1
    return changed / pixel_count


def dhash(image: Image.Image) -> int:
    small = image.convert("L").resize((9, 8))
    pixels = small.tobytes()
    value = 0
    for row in range(8):
        for col in range(8):
            left = pixels[row * 9 + col]
            right = pixels[row * 9 + col + 1]
            value = (value << 1) | (1 if left > right else 0)
    return value


def hamming_distance(left: int, right: int) -> int:
    return int((left ^ right).bit_count())


def pixel_metrics(product_path: Path, reference_path: Path) -> dict[str, Any]:
    product = normalized_image(product_path)
    reference = normalized_image(reference_path)
    diff = ImageChops.difference(product, reference)
    stat = ImageStat.Stat(diff)
    mean_absolute_error = sum(float(value) for value in stat.mean) / 3
    rms_error = math.sqrt(sum(float(value) ** 2 for value in stat.rms) / 3)
    return {
        "meanAbsoluteError": round(mean_absolute_error, 3),
        "rmsError": round(rms_error, 3),
        "pixelDifferenceRatio": round(difference_ratio(diff), 4),
        "perceptualHashDistance": hamming_distance(dhash(product), dhash(reference)),
    }


def metrics_pass(metrics: dict[str, Any], thresholds: dict[str, float]) -> bool:
    return all(float(metrics[name]) <= float(limit) for name, limit in thresholds.items())


def screenshot_locator(page: Any, selector: str, path: Path) -> tuple[bool, str]:
    try:
        locator = page.locator(selector).first
        if locator.count() < 1:
            return False, "selector not found"
        locator.screenshot(path=str(path), timeout=3000)
        return True, ""
    except Exception as exc:  # noqa: BLE001 - report browser screenshot failure as data.
        return False, str(exc)


def screenshot_text_anchor(page: Any, text: str, path: Path) -> tuple[bool, str]:
    try:
        locator = page.get_by_text(text).first
        if locator.count() < 1:
            return False, "anchor not found"
        locator.screenshot(path=str(path), timeout=3000)
        return True, ""
    except Exception as exc:  # noqa: BLE001 - report browser screenshot failure as data.
        return False, str(exc)


def screenshot_anchor_ancestor(page: Any, text: str, ancestor_depth: int, path: Path) -> tuple[bool, str]:
    try:
        locator = page.get_by_text(text).first
        if locator.count() < 1:
            return False, "anchor not found"
        handle = locator.evaluate_handle(
            """(element, depth) => {
              let node = element;
              for (let index = 0; node && index < depth; index += 1) {
                node = node.parentElement;
              }
              return node;
            }""",
            ancestor_depth,
        )
        element = handle.as_element()
        if not element:
            return False, "ancestor not found"
        element.screenshot(path=str(path), timeout=5000)
        return True, ""
    except Exception as exc:  # noqa: BLE001 - report browser screenshot failure as data.
        return False, str(exc)


def crop_image_to_size(source: Path, target: Path, size: tuple[int, int]) -> bool:
    if not source.exists():
        return False
    with Image.open(source) as image:
        width = min(size[0], image.width)
        height = min(size[1], image.height)
        if width <= 0 or height <= 0:
            return False
        cropped = image.convert("RGB").crop((0, 0, width, height))
        if cropped.size != size:
            canvas = Image.new("RGB", size, cropped.getpixel((0, 0)))
            canvas.paste(cropped, (0, 0))
            cropped = canvas
        cropped.save(target)
    return True


def run_route(browser: Any, spec: ScreenshotSpec, viewport: str, base_urls: dict[str, str], screenshot_dir: Path, timeout_ms: int) -> dict[str, Any]:
    viewport_spec = VIEWPORTS[viewport]
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    context = browser.new_context(viewport=viewport_spec, java_script_enabled=True, ignore_https_errors=True)
    product_page = context.new_page()
    reference_page = context.new_page()
    console_errors: list[str] = []
    page_errors: list[str] = []
    product_page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
    product_page.on("pageerror", lambda error: page_errors.append(str(error)))
    product_target_url = product_url(base_urls, spec)
    reference_target_url = reference_url(spec)
    status = 0
    reference_status = 0
    error = ""
    try:
        response = product_page.goto(product_target_url, wait_until="networkidle", timeout=timeout_ms)
        status = response.status if response else 0
        reference_response = reference_page.goto(reference_target_url, wait_until="networkidle", timeout=timeout_ms)
        reference_status = reference_response.status if reference_response else 200
    except Exception as exc:  # noqa: BLE001 - report browser failure as data.
        error = str(exc)
    slug = route_slug(spec.product, viewport)
    product_viewport_path = screenshot_dir / f"{slug}-product-viewport.png"
    reference_viewport_path = screenshot_dir / f"{slug}-reference-viewport.png"
    try:
        product_page.screenshot(path=str(product_viewport_path), full_page=False)
        reference_page.screenshot(path=str(reference_viewport_path), full_page=False)
    except Exception as exc:  # noqa: BLE001
        error = error or str(exc)
    screenshots: dict[str, Any] = {
        "productViewport": str(product_viewport_path),
        "referenceViewport": str(reference_viewport_path),
    }
    nonblank = {
        "productViewport": image_nonblank(product_viewport_path) if product_viewport_path.exists() else {"passes": False},
        "referenceViewport": image_nonblank(reference_viewport_path) if reference_viewport_path.exists() else {"passes": False},
    }
    comparisons: list[dict[str, Any]] = []
    captures: list[dict[str, Any]] = []
    thresholds = spec.thresholds or {}
    for target in spec.selectors:
        required = viewport in target.required_viewports
        product_selector_path = screenshot_dir / f"{slug}-product-{target.name}.png"
        product_found, product_error = screenshot_locator(product_page, target.product_selector, product_selector_path)
        capture = {
            "name": target.name,
            "required": required,
            "productSelector": target.product_selector,
            "productPath": str(product_selector_path),
            "productFound": product_found,
            "productError": product_error,
        }
        if target.reference_selector:
            reference_selector_path = screenshot_dir / f"{slug}-reference-{target.name}.png"
            reference_found, reference_error = screenshot_locator(reference_page, target.reference_selector, reference_selector_path)
            capture.update(
                {
                    "referenceSelector": target.reference_selector,
                    "referencePath": str(reference_selector_path),
                    "referenceFound": reference_found,
                    "referenceError": reference_error,
                }
            )
            if target.compare and required and product_found and reference_found:
                metrics = pixel_metrics(product_selector_path, reference_selector_path)
                comparison_passes = metrics_pass(metrics, thresholds)
                comparisons.append(
                    {
                        "name": target.name,
                        "passes": comparison_passes,
                        "metrics": metrics,
                        "thresholds": thresholds,
                        "productPath": str(product_selector_path),
                        "referencePath": str(reference_selector_path),
                    }
                )
        captures.append(capture)
    anchors: list[dict[str, Any]] = []
    for anchor in spec.reference_anchors:
        required = viewport == "desktop" and not spec.reference_artboard_anchor
        anchor_path = screenshot_dir / f"{slug}-reference-anchor-{safe_slug(anchor)}.png"
        found, anchor_error = screenshot_text_anchor(reference_page, anchor, anchor_path)
        anchors.append(
            {
                "text": anchor,
                "required": required,
                "found": found,
                "path": str(anchor_path),
                "error": anchor_error,
            }
        )
    artboard_capture: dict[str, Any] | None = None
    if spec.reference_artboard_anchor and viewport in spec.artboard_compare_viewports:
        reference_artboard_path = screenshot_dir / f"{slug}-reference-artboard.png"
        reference_artboard_viewport_path = screenshot_dir / f"{slug}-reference-artboard-viewport.png"
        found, artboard_error = screenshot_anchor_ancestor(
            reference_page,
            spec.reference_artboard_anchor,
            spec.reference_artboard_ancestor_depth,
            reference_artboard_path,
        )
        cropped = False
        if found:
            cropped = crop_image_to_size(
                reference_artboard_path,
                reference_artboard_viewport_path,
                (viewport_spec["width"], viewport_spec["height"]),
            )
        artboard_capture = {
            "referenceArtboardAnchor": spec.reference_artboard_anchor,
            "referenceArtboardAncestorDepth": spec.reference_artboard_ancestor_depth,
            "required": True,
            "found": found,
            "cropped": cropped,
            "referencePath": str(reference_artboard_path),
            "referenceViewportPath": str(reference_artboard_viewport_path),
            "productViewportPath": str(product_viewport_path),
            "error": artboard_error,
        }
        if found and cropped:
            metrics = pixel_metrics(product_viewport_path, reference_artboard_viewport_path)
            comparison_passes = metrics_pass(metrics, thresholds)
            comparisons.append(
                {
                    "name": "referenceArtboard",
                    "passes": comparison_passes,
                    "metrics": metrics,
                    "thresholds": thresholds,
                    "productPath": str(product_viewport_path),
                    "referencePath": str(reference_artboard_viewport_path),
                    "referenceFullArtboardPath": str(reference_artboard_path),
                }
            )
    required_captures_pass = all(
        (not item["required"]) or item.get("productFound") for item in captures
    ) and all(
        (not item["required"]) or item.get("referenceFound", True) for item in captures
    )
    required_anchors_pass = all((not item["required"]) or item["found"] for item in anchors)
    artboard_pass = not artboard_capture or (
        bool(artboard_capture["found"]) and bool(artboard_capture["cropped"])
    )
    comparisons_pass = all(item["passes"] for item in comparisons)
    reference_viewport_required = not spec.reference_artboard_anchor
    passes = (
        not error
        and 200 <= status < 400
        and reference_status in (0, 200)
        and not console_errors
        and not page_errors
        and nonblank["productViewport"]["passes"]
        and (nonblank["referenceViewport"]["passes"] or not reference_viewport_required)
        and required_captures_pass
        and required_anchors_pass
        and artboard_pass
        and comparisons_pass
    )
    context.close()
    return {
        "product": spec.product,
        "viewport": viewport,
        "productUrl": product_target_url,
        "referenceUrl": reference_target_url,
        "comparisonMode": spec.comparison_mode,
        "passes": passes,
        "status": status,
        "referenceStatus": reference_status,
        "error": error,
        "consoleErrors": console_errors,
        "pageErrors": page_errors,
        "screenshotPaths": screenshots,
        "nonblank": nonblank,
        "captures": captures,
        "referenceAnchors": anchors,
        "referenceArtboard": artboard_capture,
        "pixelComparisons": comparisons,
    }


def run_browser_routes(base_urls: dict[str, str], screenshot_dir: Path, timeout_ms: int) -> list[dict[str, Any]]:
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
                    reports.append(run_route(browser, spec, viewport, base_urls, screenshot_dir, timeout_ms))
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
                "referenceFiles": [spec.reference_file],
                "comparisonMode": spec.comparison_mode,
                "selectors": [target.product_selector for target in spec.selectors],
                "referenceSelectors": [target.reference_selector for target in spec.selectors if target.reference_selector],
                "referenceAnchors": list(spec.reference_anchors),
                "referenceArtboardAnchor": spec.reference_artboard_anchor,
                "referenceArtboardAncestorDepth": spec.reference_artboard_ancestor_depth,
                "artboardCompareViewports": list(spec.artboard_compare_viewports),
                "thresholds": spec.thresholds or {},
            }
        )
    return products


def build_report(base_urls: dict[str, str], dry_run: bool, screenshot_dir: Path, timeout_ms: int) -> dict[str, Any]:
    routes = (
        [dry_route(product, viewport, base_urls) for product in PRODUCTS for viewport in ("mobile", "desktop")]
        if dry_run
        else run_browser_routes(base_urls, screenshot_dir, timeout_ms)
    )
    passes = all(route["passes"] for route in routes)
    return {
        "passes": passes,
        "dryRun": dry_run,
        "browser": {"engine": "chromium", "executablePath": CHROME},
        "referenceRoot": str(REFERENCE_ROOT),
        "screenshotDir": str(screenshot_dir),
        "viewports": VIEWPORTS,
        "baseUrls": base_urls,
        "contract": {
            "scope": "browser screenshot drift gate",
            "checks": [
                "product/reference viewport screenshots",
                "nonblank screenshot checks",
                "selector screenshots for comparable regions",
                "PIL pixel metrics on normalized selector crops",
                "Simli B-board artboard pixel comparison",
            ],
            "limits": "Pixel metrics are drift evidence, not a pixel-perfect approval.",
        },
        "products": product_contracts(),
        "routes": routes,
        "generatedAt": int(time.time()),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="write JSON to stdout")
    parser.add_argument("--dry-run", action="store_true", help="emit contract without launching Chromium")
    parser.add_argument("--output", help="write JSON report to this file")
    parser.add_argument("--screenshot-dir", default=str(DEFAULT_SCREENSHOT_DIR), help="write screenshots to this directory")
    parser.add_argument("--base-url", action="append", default=[], help="override product base URL, format product=url")
    parser.add_argument("--timeout-ms", type=int, default=15_000, help="per-route navigation timeout")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(parse_base_urls(args.base_url), args.dry_run, Path(args.screenshot_dir), args.timeout_ms)
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded + "\n", encoding="utf-8")
    if args.json:
        print(encoded)
    else:
        print(("PASS" if report["passes"] else "FAIL") + " reference screenshots")
        for route in report["routes"]:
            print(f"{'PASS' if route['passes'] else 'FAIL'} {route['product']} {route['viewport']}: {route['comparisonMode']}")
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
