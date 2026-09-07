"""Polite per-domain HTTP client.

- Per-domain throttle: concurrency, random sleep, burst pause.
- Disk cache by URL hash (mirroring path under raw/<source>/).
- Browser-like headers, UA rotation.
- Default httpx (HTTP/2 if h2 installed) but falls back to aiohttp.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

try:
    import httpx
    HAVE_HTTPX = True
except Exception:
    HAVE_HTTPX = False

try:
    import aiohttp
except Exception:
    aiohttp = None  # type: ignore


# Per-domain politeness
DOMAIN_POLICY = {
    "tanzil.net":                  {"conc": 1, "sleep": (3, 7),  "burst": (50, 30)},
    "raw.githubusercontent.com":   {"conc": 4, "sleep": (0.2, 0.8), "burst": (500, 15)},
    "github.com":                  {"conc": 2, "sleep": (0.5, 1.5), "burst": (200, 30)},
    "codeload.github.com":         {"conc": 1, "sleep": (1.0, 2.0), "burst": (100, 30)},
    "api.quran.com":               {"conc": 1, "sleep": (2, 5),  "burst": (50, 60)},
    "api.alquran.cloud":           {"conc": 1, "sleep": (2, 5),  "burst": (50, 60)},
    "sunnah.com":                  {"conc": 1, "sleep": (4, 9),  "burst": (40, 180)},
    "vatican.va":                  {"conc": 1, "sleep": (3, 8),  "burst": (60, 120)},
    "www.vatican.va":              {"conc": 1, "sleep": (3, 8),  "burst": (60, 120)},
    "bible.usccb.org":             {"conc": 1, "sleep": (4, 9),  "burst": (40, 180)},
    "newadvent.org":               {"conc": 1, "sleep": (3, 7),  "burst": (60, 120)},
    "www.newadvent.org":           {"conc": 1, "sleep": (3, 7),  "burst": (60, 120)},
    "suttacentral.net":            {"conc": 1, "sleep": (3, 7),  "burst": (60, 120)},
    "84000.co":                    {"conc": 1, "sleep": (4, 10), "burst": (50, 180)},
    "read.84000.co":               {"conc": 1, "sleep": (4, 10), "burst": (50, 180)},
    "cbetaonline.dila.edu.tw":     {"conc": 1, "sleep": (4, 10), "burst": (40, 300)},
    "kabc.dongguk.edu":            {"conc": 1, "sleep": (5, 12), "burst": (30, 300)},
    "sacred-texts.com":            {"conc": 1, "sleep": (3, 7),  "burst": (60, 120)},
    "gretil.sub.uni-goettingen.de":{"conc": 1, "sleep": (3, 7),  "burst": (60, 120)},
    "vedabase.io":                 {"conc": 1, "sleep": (4, 9),  "burst": (40, 180)},
    "islamqa.info":                {"conc": 1, "sleep": (6, 15), "burst": (20, 600)},
    "sistani.org":                 {"conc": 1, "sleep": (6, 15), "burst": (20, 600)},
    "dar-alifta.org":              {"conc": 1, "sleep": (6, 15), "burst": (20, 600)},
    "drikpanchang.com":            {"conc": 1, "sleep": (5, 12), "burst": (30, 300)},
    "_default":                    {"conc": 1, "sleep": (4, 9),  "burst": (40, 180)},
}

UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

ACCEPT = ("text/html,application/xhtml+xml,application/xml;q=0.9,"
          "image/avif,image/webp,*/*;q=0.8")


def _domain_of(url: str) -> str:
    return urlparse(url).hostname or "_default"


def _policy(host: str) -> dict:
    return DOMAIN_POLICY.get(host, DOMAIN_POLICY["_default"])


class PoliteClient:
    def __init__(self, cache_root: Path, log=print):
        self.cache_root = Path(cache_root)
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.log = log
        # Per-host: {sem, counter, last_request_time, fail_streak}
        self._hosts: dict[str, dict] = {}
        # Failure cooldowns
        self._cooldowns: dict[str, float] = {}
        self._aio = None  # lazy
        if HAVE_HTTPX:
            limits = httpx.Limits(max_connections=10, max_keepalive_connections=10)
            self._client = httpx.AsyncClient(http2=True, limits=limits, follow_redirects=True,
                                             timeout=httpx.Timeout(30.0, connect=15.0))
        else:
            self._client = None

    async def aclose(self):
        if HAVE_HTTPX and self._client:
            await self._client.aclose()
        if self._aio:
            await self._aio.close()

    def _host_state(self, host: str) -> dict:
        st = self._hosts.get(host)
        if st is None:
            pol = _policy(host)
            st = {
                "sem": asyncio.Semaphore(pol["conc"]),
                "n": 0,
                "fail": 0,
                "next_burst": pol["burst"][0],
                "policy": pol,
            }
            self._hosts[host] = st
        return st

    def _cache_path_for(self, url: str, *, mirror: bool = True, suffix: str = "") -> Path:
        u = urlparse(url)
        host = u.hostname or "unknown"
        if mirror:
            path = u.path.lstrip("/") or "_root"
            if u.query:
                path = path + "_" + hashlib.sha1(u.query.encode()).hexdigest()[:10]
            full = self.cache_root / host / path
            if suffix and not full.suffix:
                full = full.with_suffix(suffix)
            full.parent.mkdir(parents=True, exist_ok=True)
            return full
        else:
            h = hashlib.sha1(url.encode()).hexdigest()
            sub = self.cache_root / host
            sub.mkdir(parents=True, exist_ok=True)
            return sub / (h + (suffix or ".html"))

    async def get(self, url: str, *, referer: Optional[str] = None,
                  cache_path: Optional[Path] = None, force: bool = False,
                  expect_min_size: int = 200, accept: Optional[str] = None,
                  binary: bool = False) -> Optional[bytes | str]:
        """Polite GET with cache, retry, per-domain backoff."""
        host = _domain_of(url)
        if cache_path is None:
            cache_path = self._cache_path_for(url, mirror=True,
                                              suffix=".bin" if binary else ".html")
        else:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
        if cache_path.exists() and cache_path.stat().st_size >= expect_min_size and not force:
            data = cache_path.read_bytes()
            return data if binary else data.decode("utf-8", errors="replace")

        # Cooldown check
        cd = self._cooldowns.get(host, 0)
        if cd > time.time():
            wait = cd - time.time()
            self.log(f"  [polite] {host} cooldown {wait:.0f}s")
            await asyncio.sleep(wait)

        st = self._host_state(host)
        pol = st["policy"]

        async with st["sem"]:
            # Random delay before request
            await asyncio.sleep(random.uniform(*pol["sleep"]))
            # Burst pause
            st["n"] += 1
            if st["n"] >= st["next_burst"]:
                br = pol["burst"][1] + random.randint(0, pol["burst"][1] // 2)
                self.log(f"  [polite] {host} burst pause {br}s after {st['n']} reqs")
                await asyncio.sleep(br)
                st["next_burst"] = st["n"] + pol["burst"][0]

            ua = random.choice(UAS)
            headers = {
                "User-Agent": ua,
                "Accept": accept or ACCEPT,
                "Accept-Language": random.choice([
                    "en-US,en;q=0.9", "ko-KR,ko;q=0.9,en;q=0.8",
                    "en-US,en;q=0.9,ko;q=0.7"
                ]),
                "Accept-Encoding": "gzip, deflate, br",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin" if referer else "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
                "Connection": "keep-alive",
            }
            if referer:
                headers["Referer"] = referer

            for attempt in range(5):
                try:
                    if HAVE_HTTPX:
                        r = await self._client.get(url, headers=headers)
                        status = r.status_code
                        body = r.content
                    else:
                        if self._aio is None:
                            self._aio = aiohttp.ClientSession()
                        async with self._aio.get(url, headers=headers,
                                                  timeout=aiohttp.ClientTimeout(total=30)) as r:
                            status = r.status
                            body = await r.read()

                    if status == 200:
                        if len(body) < expect_min_size:
                            self.log(f"  [polite] {url} too small ({len(body)})")
                        else:
                            cache_path.write_bytes(body)
                            st["fail"] = 0
                            return body if binary else body.decode("utf-8", errors="replace")
                    if status in (429, 503, 502, 504):
                        wait = min(60, 5 * (2 ** attempt) + random.uniform(0, 5))
                        self.log(f"  [polite] {url} {status}, sleep {wait:.0f}s")
                        await asyncio.sleep(wait)
                        continue
                    if status in (400, 403, 404):
                        self.log(f"  [polite] {url} {status} — abort")
                        return None
                    self.log(f"  [polite] {url} {status} unexpected")
                    return None
                except Exception as e:
                    wait = min(30, 3 * (2 ** attempt) + random.uniform(0, 3))
                    self.log(f"  [polite] {url} err {type(e).__name__}: {e}, retry in {wait:.0f}s")
                    await asyncio.sleep(wait)
            # All retries failed — cooldown the host
            st["fail"] += 1
            if st["fail"] >= 3:
                self._cooldowns[host] = time.time() + 30 * 60
                self.log(f"  [polite] {host} 3+ fails — 30min cooldown")
                st["fail"] = 0
            return None
