#!/usr/bin/env python3
"""Verify that the current public Cloudflare tunnel URLs are healthy."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PRODUCTS = (
    ("islam", 8061),
    ("tcm", 8062),
    ("simli", 8063),
)

TRYCLOUDFLARE_RE = re.compile(r"https://[A-Za-z0-9.-]+\.trycloudflare\.com")


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def _latest_trycloudflare_url(text: str) -> str:
    matches = TRYCLOUDFLARE_RE.findall(text)
    return matches[-1] if matches else ""


def _default_fetch(url: str, timeout: float) -> tuple[int, str]:
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(16_384).decode("utf-8", errors="replace")
            return int(response.status), body
    except HTTPError as exc:
        body = exc.read(16_384).decode("utf-8", errors="replace")
        return int(exc.code), body
    except (OSError, URLError) as exc:
        return 0, str(exc)


def _health_body_looks_ok(body: str) -> bool:
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return "ok" in body.lower()
    if isinstance(parsed, dict):
        return parsed.get("status") == "ok" or parsed.get("ok") is True
    return False


def build_report(
    *,
    runtime_dir: Path | str = Path(".runtime"),
    fetch: Callable[[str, float], tuple[int, str]] = _default_fetch,
    timeout: float = 8.0,
) -> dict:
    runtime_path = Path(runtime_dir)
    products = []

    for product, port in PRODUCTS:
        log_path = runtime_path / f"{product}-{port}-tunnel.log"
        public_url = _latest_trycloudflare_url(_read_text(log_path))
        health_url = f"{public_url.rstrip('/')}/api/health" if public_url else ""
        status_code = 0
        body = ""
        if health_url:
            status_code, body = fetch(health_url, timeout)
        public_health_passes = bool(
            health_url and status_code == 200 and _health_body_looks_ok(body)
        )
        products.append(
            {
                "product": product,
                "port": port,
                "logPath": str(log_path),
                "publicUrl": public_url,
                "healthUrl": health_url,
                "checks": {
                    "urlFound": {
                        "passes": bool(public_url),
                        "detail": "latest trycloudflare URL found"
                        if public_url
                        else "no trycloudflare URL found in tunnel log",
                    },
                },
                "publicHealth": {
                    "passes": public_health_passes,
                    "statusCode": status_code,
                    "bodyPreview": body[:500],
                },
            }
        )

    telegram_token = bool(os.environ.get("TELEGRAM_BOT_TOKEN"))
    telegram_chat = bool(os.environ.get("TELEGRAM_CHAT_ID"))
    return {
        "passes": all(
            item["checks"]["urlFound"]["passes"] and item["publicHealth"]["passes"]
            for item in products
        ),
        "products": products,
        "telegramConfigured": {
            "botTokenEnvPresent": telegram_token,
            "chatIdEnvPresent": telegram_chat,
            "passes": telegram_token and telegram_chat,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-dir", default=".runtime")
    parser.add_argument("--output")
    parser.add_argument("--timeout", type=float, default=8.0)
    args = parser.parse_args(argv)

    report = build_report(runtime_dir=Path(args.runtime_dir), timeout=args.timeout)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
