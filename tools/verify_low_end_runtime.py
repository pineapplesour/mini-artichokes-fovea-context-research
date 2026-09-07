#!/usr/bin/env python3
"""Verify low-end runtime budgets for the shared product shells."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PRODUCTS = ("islam", "tcm", "simli")
NETWORK_BPS = 1_000_000
DEVICE_PROFILE = {
    "name": "third-world-legacy-phone",
    "cpu": "slow-single-core-budget",
    "memoryMb": 512,
    "network": "1Mbps",
}
SHARED_JS = (
    "ui-i18n.js",
    "shared-client.js",
    "chat-store.js",
    "job-events.js",
    "job-progress.js",
    "job-cancel.js",
)
PRODUCT_BUDGETS = {
    "islam": {"runtimeJsBytes": 65_000, "staticHtmlTags": 420, "estimatedParseMs": 120},
    "tcm": {"runtimeJsBytes": 65_000, "staticHtmlTags": 420, "estimatedParseMs": 120},
    "simli": {"runtimeJsBytes": 65_000, "staticHtmlTags": 420, "estimatedParseMs": 120},
}
FORBIDDEN_RUNTIME_TOKENS = (
    ".innerHTML",
    "eval(",
    "new Function",
    "document.write",
    "setInterval(",
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def web_file(name: str) -> Path:
    return WEB / name


def js_asset_names(product: str) -> list[str]:
    return [*SHARED_JS, f"{product}-chat.js"]


def byte_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def html_routes(product: str) -> list[Path]:
    return [web_file(f"{product}.html"), web_file(f"{product}-chat.html")]


def count_static_tags(paths: list[Path]) -> int:
    return sum(len(re.findall(r"<[a-zA-Z][^>]*", read_text(path))) for path in paths if path.exists())


def estimated_parse_ms(js_bytes: int) -> int:
    # Conservative static estimate for old Android WebView class devices.
    return int(round(js_bytes / 650))


def forbidden_report(text_by_asset: dict[str, str]) -> dict[str, Any]:
    hits = []
    for asset, text in text_by_asset.items():
        for token in FORBIDDEN_RUNTIME_TOKENS:
            if token in text:
                hits.append({"asset": asset, "token": token})
    return {"passes": not hits, "hits": hits}


def local_chat_store_report(text: str) -> dict[str, Any]:
    max_sessions_match = re.search(r"DEFAULT_MAX_STORED_SESSIONS\s*=\s*(\d+)", text) or re.search(
        r"maxStoredSessions\s*\|\|\s*(\d+)", text
    )
    max_sources_match = (
        re.search(r"MAX_RESULT_SOURCES\s*=\s*(\d+)", text)
        or re.search(r"sources\|\|[^)]*selectedEvidence[^)]*\.slice\(0,(\d+)\)", text)
        or re.search(r"\.slice\(0,(\d+)\)\.map", text)
    )
    max_text_match = re.search(r"MAX_TEXT\s*=\s*(\d+)", text) or re.search(r"const\s+\w+\s*=\s*(900)\s*;", text)
    if not (max_sessions_match and max_sources_match and max_text_match):
        return {
            "maxStoredSessions": 0,
            "maxResultSources": 0,
            "maxTextChars": 0,
            "bounded": False,
            "parseError": "missing bounded storage constants",
        }
    max_sessions = int(max_sessions_match.group(1))
    max_sources = int(max_sources_match.group(1))
    max_text = int(max_text_match.group(1))
    return {
        "maxStoredSessions": max_sessions,
        "maxResultSources": max_sources,
        "maxTextChars": max_text,
        "bounded": max_sessions <= 24 and max_sources <= 18 and max_text <= 900,
    }


def shared_runtime_report() -> dict[str, Any]:
    texts = {name: read_text(web_file(name)) for name in SHARED_JS}
    chat_store = texts["chat-store.js"]
    events = texts["job-events.js"]
    progress = texts["job-progress.js"]
    cancel = texts["job-cancel.js"]
    forbidden = forbidden_report(texts)
    local_store = local_chat_store_report(chat_store)
    offline_outbox = all(token in chat_store for token in ("indexedDB.open", "outbox", "online", "__beta6ChatOutboxFetch"))
    anonymous_session = all(token in chat_store for token in ("beta6.sessionToken", "X-Beta6-Session-Token", "crypto.getRandomValues"))
    progress_fallback = (
        all(token in events for token in ("EventSource", "pollFallback", "SSE_HANDSHAKE_TIMEOUT_MS"))
        and "window.Beta6JobProgress" in progress
        and "render" in progress
    )
    job_cancel = (
        "Beta6JobCancel" in cancel
        and "jobBasePath(jobId, product)" in cancel
        and "/cancel" in cancel
        and 'method: "POST"' in cancel
    )
    passes = forbidden["passes"] and local_store["bounded"] and offline_outbox and anonymous_session and progress_fallback and job_cancel
    return {
        "passes": passes,
        "bytes": {name: byte_size(web_file(name)) for name in SHARED_JS},
        "localChatStore": local_store,
        "offlineOutbox": offline_outbox,
        "anonymousSessionToken": anonymous_session,
        "progressFallback": progress_fallback,
        "jobCancel": job_cancel,
        "forbiddenApis": forbidden,
    }


def route_safety_report(paths: list[Path]) -> dict[str, Any]:
    texts = [read_text(path) for path in paths if path.exists()]
    joined = "\n".join(texts)
    return {
        "localOnly": "https://" not in joined and "http://" not in joined,
        "noDataImages": "data:image" not in joined,
        "viewportMeta": all('name="viewport"' in text for text in texts),
    }


def source_window_report(product: str, text: str) -> dict[str, Any]:
    bounded = (
        f"/api/{product}/source-window" in text
        and "radius" in text
        and "before" in text
        and "after" in text
        and "source-window-mark" in text
    )
    incremental = all(token in text for token in ("위로 더 보기", "아래로 더 보기", "expandPassageWindow"))
    return {"bounded": bounded, "incrementalContext": incremental}


def chat_runtime_report(text: str) -> dict[str, Any]:
    compact = "".join(text.split())
    return {
        "jobEvents": "Beta6JobEvents.follow" in text,
        "jobProgress": "Beta6JobProgress.render" in text,
        "jobCancel": "Beta6JobCancel.cancel" in text,
        "storedSessions": all(token in text for token in ("chatStore.start", "chatStore.complete", "restoreStoredSession")),
        "sessionTokenUrl": "chatStore.jobUrl(path,token)" in compact or "chatStore.jobUrl" in text,
    }


def product_report(product: str) -> dict[str, Any]:
    js_assets = js_asset_names(product)
    js_paths = [web_file(name) for name in js_assets]
    js_bytes = sum(byte_size(path) for path in js_paths)
    parse_ms = estimated_parse_ms(js_bytes)
    chat_text = read_text(web_file(f"{product}-chat.js"))
    html_paths = html_routes(product)
    tags = count_static_tags(html_paths)
    budget = PRODUCT_BUDGETS[product]
    route_safety = route_safety_report(html_paths)
    source_window = source_window_report(product, chat_text)
    chat_runtime = chat_runtime_report(chat_text)
    forbidden = forbidden_report({name: read_text(web_file(name)) for name in js_assets})
    passes = (
        js_bytes <= budget["runtimeJsBytes"]
        and tags <= budget["staticHtmlTags"]
        and parse_ms <= budget["estimatedParseMs"]
        and all(route_safety.values())
        and all(source_window.values())
        and all(chat_runtime.values())
        and forbidden["passes"]
    )
    return {
        "passes": passes,
        "jsAssets": js_assets,
        "runtimeJsBytes": js_bytes,
        "staticHtmlTags": tags,
        "estimatedParseMs": parse_ms,
        "budgets": budget,
        "routeSafety": route_safety,
        "sourceWindow": source_window,
        "chatRuntime": chat_runtime,
        "forbiddenApis": forbidden,
    }


def build_report() -> dict[str, Any]:
    shared = shared_runtime_report()
    products = {product: product_report(product) for product in PRODUCTS}
    passes = shared["passes"] and all(item["passes"] for item in products.values())
    return {
        "passes": passes,
        "deviceProfile": DEVICE_PROFILE,
        "network": {"bps": NETWORK_BPS, "label": "1Mbps"},
        "sharedRuntime": shared,
        "products": products,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="write JSON to stdout")
    parser.add_argument("--output", help="write JSON report to this file")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report()
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded + "\n", encoding="utf-8")
    if args.json:
        print(encoded)
    else:
        print(("PASS" if report["passes"] else "FAIL") + " low-end runtime budgets")
        for product, item in report["products"].items():
            print(f"{product}: js={item['runtimeJsBytes']} bytes, tags={item['staticHtmlTags']}, parse={item['estimatedParseMs']}ms")
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
