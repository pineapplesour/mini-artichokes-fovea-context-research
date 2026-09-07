#!/usr/bin/env python3
"""Verify low-bandwidth shell budgets and route parity for split products."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
NETWORK_BPS = 1_000_000
VIEWPORTS = {
    "mobile": {"width": 360, "height": 740},
    "desktop": {"width": 1280, "height": 720},
}
PRODUCT_ORDER = ("islam", "tcm", "simli")
PRODUCT_BUDGETS = {
    "islam": {"bytes": 220_000, "seconds": 1.8},
    "tcm": {"bytes": 95_000, "seconds": 0.9},
    "simli": {"bytes": 95_000, "seconds": 0.9},
}
SW_CACHE_VERSION = "shared-platform-shell-reference-v47"
WOFF2_ASSET = "/static/fonts/NotoNaskhArabic-Regular.woff2"
TTF_ASSET = "/static/fonts/NotoNaskhArabic-Regular.ttf"


@dataclass(frozen=True)
class Route:
    product: str
    kind: str
    path: str
    file_path: Path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def asset_file_path(asset: str) -> Path:
    if asset.startswith("/static/"):
        return WEB / asset.removeprefix("/static/")
    return WEB / asset.lstrip("/")


def quoted_assets(block: str) -> list[str]:
    return re.findall(r'"([^"]+)"', block)


def service_worker_text() -> str:
    return read_text(WEB / "sw.js")


def service_worker_cache_name(sw: str) -> str:
    match = re.search(r'const\s+CACHE_NAME\s*=\s*"([^"]+)"', sw)
    return match.group(1) if match else ""


def core_assets(sw: str) -> list[str]:
    block = sw.split("const CORE_ASSETS = [", 1)[1].split("];", 1)[0]
    return quoted_assets(block)


def product_assets(sw: str, product: str) -> list[str]:
    product_index = PRODUCT_ORDER.index(product)
    next_product = PRODUCT_ORDER[product_index + 1] if product_index + 1 < len(PRODUCT_ORDER) else None
    block = sw.split(f"{product}:", 1)[1]
    block = block.split(f"{next_product}:", 1)[0] if next_product else block.split("};", 1)[0]
    return quoted_assets(block)


def route_for(product: str, kind: str) -> Route:
    suffix = "" if kind == "landing" else "-chat"
    path = f"/{product}{suffix}.html"
    return Route(product=product, kind=kind, path=path, file_path=WEB / f"{product}{suffix}.html")


def route_report(route: Route) -> dict[str, Any]:
    exists = route.file_path.exists()
    text = read_text(route.file_path) if exists else ""
    return {
        "path": route.path,
        "exists": exists,
        "bytes": route.file_path.stat().st_size if exists else 0,
        "viewportMeta": 'name="viewport"' in text,
        "productMarker": f'data-product="{route.product}"' in text,
        "localOnly": "https://" not in text and "http://" not in text,
    }


def viewport_report(route: Route, width: int, height: int) -> dict[str, Any]:
    exists = route.file_path.exists()
    text = read_text(route.file_path) if exists else ""
    responsive = "@media" in text or 'name="viewport"' in text
    return {
        "width": width,
        "height": height,
        "route": route.path,
        "responsiveContract": responsive,
        "fitsKnownShell": exists and responsive and f'data-product="{route.product}"' in text,
    }


def product_report(product: str, sw: str) -> dict[str, Any]:
    assets = sorted(set(core_assets(sw) + product_assets(sw, product)))
    shell_bytes = sum(asset_file_path(asset).stat().st_size for asset in assets)
    estimated_seconds = round((shell_bytes * 8) / NETWORK_BPS, 3)
    landing = route_report(route_for(product, "landing"))
    chat = route_report(route_for(product, "chat"))
    viewport_checks = {
        name: viewport_report(route_for(product, "landing"), spec["width"], spec["height"])
        for name, spec in VIEWPORTS.items()
    }
    budget = PRODUCT_BUDGETS[product]
    routes_pass = all(
        item["exists"] and item["viewportMeta"] and item["productMarker"] and item["localOnly"]
        for item in (landing, chat)
    )
    passes = routes_pass and shell_bytes <= budget["bytes"] and estimated_seconds <= budget["seconds"]
    return {
        "passes": passes,
        "assets": assets,
        "shellBytes": shell_bytes,
        "budgetBytes": budget["bytes"],
        "estimated1MbpsSeconds": estimated_seconds,
        "budgetSeconds": budget["seconds"],
        "landing": landing,
        "chat": chat,
        "viewports": viewport_checks,
    }


def font_report(sw: str) -> dict[str, Any]:
    woff2 = asset_file_path(WOFF2_ASSET)
    ttf = asset_file_path(TTF_ASSET)
    return {
        "woff2Asset": WOFF2_ASSET,
        "woff2Exists": woff2.exists(),
        "woff2Bytes": woff2.stat().st_size if woff2.exists() else 0,
        "ttfFallbackAsset": TTF_ASSET,
        "ttfFallbackExists": ttf.exists(),
        "ttfFallbackBytes": ttf.stat().st_size if ttf.exists() else 0,
        "woff2InServiceWorker": WOFF2_ASSET in sw,
        "ttfFallbackInServiceWorker": TTF_ASSET in sw,
    }


def fetch_status(base_url: str, path: str, timeout: float) -> dict[str, Any]:
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    request = Request(url, headers={"User-Agent": "beta6-low-bandwidth-verifier/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(256)
            return {
                "url": url,
                "ok": 200 <= response.status < 400,
                "status": response.status,
                "contentType": response.headers.get("content-type", ""),
                "contentLength": int(response.headers.get("content-length") or 0),
                "sampleBytes": len(body),
            }
    except (OSError, URLError) as exc:
        return {"url": url, "ok": False, "status": 0, "error": str(exc)}


def live_report(base_urls: dict[str, str], timeout: float) -> dict[str, Any]:
    report: dict[str, Any] = {}
    for product, base_url in sorted(base_urls.items()):
        checks = {
            "landing": fetch_status(base_url, f"/{product}.html", timeout),
            "chat": fetch_status(base_url, f"/{product}-chat.html", timeout),
            "serviceWorker": fetch_status(base_url, "/sw.js", timeout),
        }
        if product == "islam":
            checks["woff2"] = fetch_status(base_url, WOFF2_ASSET, timeout)
        checks["passes"] = all(item.get("ok") for item in checks.values() if isinstance(item, dict))
        report[product] = checks
    return report


def build_report(base_urls: dict[str, str] | None = None, timeout: float = 10.0) -> dict[str, Any]:
    sw = service_worker_text()
    cache_name = service_worker_cache_name(sw)
    font = font_report(sw)
    products = {product: product_report(product, sw) for product in PRODUCT_ORDER}
    service_worker = {
        "path": "/sw.js",
        "cacheName": cache_name,
        "expectedCacheName": SW_CACHE_VERSION,
        "cacheVersionPasses": cache_name == SW_CACHE_VERSION,
        "preCachesWoff2": font["woff2InServiceWorker"],
        "preCachesTtfFallback": font["ttfFallbackInServiceWorker"],
    }
    live = live_report(base_urls or {}, timeout) if base_urls else {}
    passes = (
        service_worker["cacheVersionPasses"]
        and service_worker["preCachesWoff2"]
        and not service_worker["preCachesTtfFallback"]
        and font["woff2Exists"]
        and font["woff2Bytes"] <= 80_000
        and all(item["passes"] for item in products.values())
        and all(item["passes"] for item in live.values())
    )
    return {
        "passes": passes,
        "network": {"bps": NETWORK_BPS, "label": "1Mbps"},
        "viewports": VIEWPORTS,
        "serviceWorker": service_worker,
        "font": font,
        "products": products,
        "live": live,
    }


def parse_base_urls(values: list[str]) -> dict[str, str]:
    result = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"--base-url must be product=url, got: {value}")
        product, url = value.split("=", 1)
        if product not in PRODUCT_ORDER:
            raise SystemExit(f"unknown product for --base-url: {product}")
        result[product] = url
    return result


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="write JSON to stdout")
    parser.add_argument("--output", help="write JSON report to this file")
    parser.add_argument("--base-url", action="append", default=[], help="live check, format product=url")
    parser.add_argument("--timeout", type=float, default=10.0, help="live HTTP timeout seconds")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    report = build_report(parse_base_urls(args.base_url), timeout=args.timeout)
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded + "\n", encoding="utf-8")
    if args.json:
        print(encoded)
    else:
        status = "PASS" if report["passes"] else "FAIL"
        print(f"{status} low-bandwidth route matrix")
        for product, item in report["products"].items():
            print(f"{product}: {item['shellBytes']} bytes, {item['estimated1MbpsSeconds']}s at 1Mbps")
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
