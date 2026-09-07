#!/usr/bin/env python3
"""Catechism of the Catholic Church (CCC) from vatican.va.

374 HTML pages. Polite client (3-8s/req). Each page contains numbered paragraphs
(CCC §1 to §2865). We extract paragraph by number.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _lib.polite_client import PoliteClient
from _lib.jsonl_writer import JsonlWriter, text_hash, normalize_text

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw" / "christian" / "catholic" / "vatican" / "ccc"
CORPUS = ROOT / "corpus" / "christian"

INDEX_URL = "https://www.vatican.va/archive/ENG0015/_INDEX.HTM"
PAGE_BASE = "https://www.vatican.va/archive/ENG0015"

# Pattern: a number on its own (often as <a name="numXX">) followed by paragraph
PARA_RE = re.compile(r"\b(\d{1,4})\s*\n\s*(.+?)(?=\n\s*\d{1,4}\s*\n|\Z)", re.S)


def parse_ccc_page(html: str) -> list[tuple[int, str]]:
    """Extract (paragraph_number, text) pairs from one CCC HTML page."""
    from bs4 import BeautifulSoup
    s = BeautifulSoup(html, "html.parser")
    # Look for the main text body — IntraText pages use <div> + plain text after links
    # Strategy: find all <a name="numXX"> markers and collect text until next marker
    out = []
    # vatican.va markup pattern: paragraph numbers wrapped in superscript or just inline
    # Easier: get full text then regex
    for nav in s.find_all(["nav", "table", "head"]):
        nav.decompose()
    text = s.get_text("\n", strip=True)
    # Find markers: standalone digit lines that look like CCC paragraph numbers (1-2865)
    lines = text.split("\n")
    cur_num = None
    cur_buf = []
    for ln in lines:
        ln_strip = ln.strip()
        if re.fullmatch(r"\d{1,4}", ln_strip):
            n = int(ln_strip)
            if 1 <= n <= 2865:
                # commit previous
                if cur_num is not None and cur_buf:
                    body = " ".join(cur_buf).strip()
                    if body:
                        out.append((cur_num, body))
                cur_num = n
                cur_buf = []
                continue
        if cur_num is not None:
            cur_buf.append(ln_strip)
    if cur_num is not None and cur_buf:
        body = " ".join(cur_buf).strip()
        if body:
            out.append((cur_num, body))
    return out


async def main():
    CORPUS.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    client = PoliteClient(cache_root=ROOT / "raw" / "christian" / "catholic" / "vatican")

    # 1) fetch index
    idx_cache = RAW / "_INDEX.HTM"
    if not idx_cache.exists():
        data = await client.get(INDEX_URL, cache_path=idx_cache, expect_min_size=5000, binary=True)
        if not data:
            await client.aclose()
            raise SystemExit("CCC index fetch failed")

    from bs4 import BeautifulSoup
    s = BeautifulSoup(idx_cache.read_text(encoding="utf-8", errors="replace"), "html.parser")
    pages = []
    for a in s.find_all("a", href=True):
        h = a.get("href", "")
        if h.startswith("__P") and h.endswith(".HTM"):
            pages.append(h)
    pages = sorted(set(pages))
    print(f"[ccc] {len(pages)} pages")

    sources_w = JsonlWriter(CORPUS / "sources.jsonl")
    passages_w = JsonlWriter(CORPUS / "passages.jsonl")

    source_id = "christian.catholic.ccc.en"
    sources_w.write({
        "source_id": source_id,
        "religion": "christian",
        "tradition": "catholic",
        "school": "",
        "source_kind": "catechism",
        "authority_level": 90,
        "authority_label": "official_core_doctrine",
        "title": "Catechism of the Catholic Church (CCC)",
        "subtitle": "Vatican English edition",
        "author_body": "Holy See — Catechism of the Catholic Church",
        "edition": "vatican.va archive ENG0015",
        "language": "en",
        "script": "latn",
        "source_url": INDEX_URL,
        "license": "Vatican copyright (educational/non-commercial use OK with attribution)",
        "license_notes": "Vatican Copyright Office Standard.",
        "valid_from": "1992",
        "valid_to": "",
        "text_hash": "",
    })

    seen_paras: dict[int, str] = {}
    n_pages = 0
    n_paras = 0
    try:
        for h in pages:
            url = f"{PAGE_BASE}/{h}"
            cache = RAW / h
            html = await client.get(url, cache_path=cache, referer=INDEX_URL,
                                     expect_min_size=500)
            if not html:
                print(f"  ! fail {h}")
                continue
            paras = parse_ccc_page(html)
            for n, body in paras:
                if n in seen_paras:
                    continue
                seen_paras[n] = body
                pid = f"{source_id}.{n:04d}"
                passages_w.write({
                    "passage_id": pid,
                    "source_id": source_id,
                    "canonical_ref": f"CCC §{n}",
                    "parent_ref": f"CCC",
                    "ref_sort": n,
                    "language": "en",
                    "script": "latn",
                    "text": body,
                    "normalized_text": normalize_text(body),
                    "heading": "",
                    "tags_json": "[]",
                    "text_hash": text_hash(body),
                })
                n_paras += 1
            n_pages += 1
            if n_pages % 20 == 0:
                print(f"  pages {n_pages}/{len(pages)} paras {n_paras}")
    finally:
        sources_w.close()
        passages_w.close()
        await client.aclose()
    print(f"[ccc] pages: {n_pages}/{len(pages)}, paragraphs: {n_paras}")


if __name__ == "__main__":
    asyncio.run(main())
