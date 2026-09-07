#!/usr/bin/env python3
"""84000.co Tibetan Buddhist canon English translations.

Each /translation/toh{N}.html is a single full HTML page with the entire translation
(intro + chapters + colophon). Read.84000.co also serves the same content.
~438 top-level translations available. Polite throttle.
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
RAW = ROOT / "raw" / "buddhist" / "84000"
CORPUS = ROOT / "corpus" / "buddhist"

SITEMAP = "https://84000.co/translation-sitemap.xml"
PAGE_BASE = "https://read.84000.co/translation"


async def get_toh_list(client: PoliteClient) -> list[str]:
    cache = RAW / "_sitemap.xml"
    cache.parent.mkdir(parents=True, exist_ok=True)
    data = await client.get(SITEMAP, cache_path=cache, expect_min_size=1000, binary=True)
    if not data:
        return []
    xml = data.decode("utf-8", errors="replace")
    out = []
    for m in re.finditer(r"<loc>([^<]+)</loc>", xml):
        u = m.group(1)
        m2 = re.match(r"https://84000\.co/translation/(toh[\d\-]+)$", u)
        if m2:
            out.append(m2.group(1))
    return sorted(set(out))


def parse_84000_page(html: str) -> tuple[str, str, list[tuple[str, str]]]:
    from bs4 import BeautifulSoup
    s = BeautifulSoup(html, "html.parser")
    title_el = s.find("title")
    title = title_el.get_text(strip=True) if title_el else ""
    desc_el = s.find("meta", attrs={"name": "description"})
    desc = desc_el.get("content", "").strip() if desc_el else ""
    # Strip nav/header/footer
    for x in s.find_all(["script", "style", "nav", "header", "footer"]):
        x.decompose()
    # 84000 main content is in <article> or main translation-section divs
    main = s.find("article") or s.find("main") or s.body
    if not main:
        return title, desc, []
    text = main.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Split by H2/H3 headings → already lost in text. Use heuristic: page has section
    # markers like "1." "2." in headings. Just split into chunks of ~6000 chars at \n\n.
    parts = []
    paras = re.split(r"\n\s*\n", text)
    buf = []; cur_len = 0; idx = 0
    for p in paras:
        if cur_len + len(p) > 6000 and buf:
            parts.append((f"section {idx}", "\n\n".join(buf).strip()))
            idx += 1; buf = [p]; cur_len = len(p)
        else:
            buf.append(p); cur_len += len(p)
    if buf:
        parts.append((f"section {idx}", "\n\n".join(buf).strip()))
    return title, desc, parts


async def main():
    CORPUS.mkdir(parents=True, exist_ok=True)
    client = PoliteClient(cache_root=ROOT / "raw" / "buddhist")
    sw = JsonlWriter(CORPUS / "sources.jsonl")
    pw = JsonlWriter(CORPUS / "passages.jsonl")
    try:
        tohs = await get_toh_list(client)
        print(f"[84000] {len(tohs)} translations to fetch", flush=True)
        for i, toh in enumerate(tohs):
            url = f"{PAGE_BASE}/{toh}.html"
            cache = RAW / "translations" / f"{toh}.html"
            html = await client.get(url, cache_path=cache, referer="https://84000.co/", expect_min_size=2000)
            if not html:
                continue
            title, desc, chunks = parse_84000_page(html)
            if not chunks:
                continue
            source_id = f"bud.vajra.84000.{toh}"
            sw.write({
                "source_id": source_id, "religion": "buddhist",
                "tradition": "vajrayana", "school": "kangyur",
                "source_kind": "scripture", "authority_level": 100,
                "authority_label": "canonical_scripture",
                "title": title or f"84000.co {toh}",
                "subtitle": desc[:300],
                "author_body": "84000: Translating the Words of the Buddha",
                "edition": f"84000.co {toh}",
                "language": "en", "script": "latn",
                "source_url": url,
                "license": "CC-BY-NC 4.0",
                "license_notes": "Per 84000.co terms; non-commercial reuse with attribution.",
                "valid_from": "", "valid_to": "", "text_hash": "",
            })
            for j, (lab, body) in enumerate(chunks):
                pid = f"{source_id}.{j:03d}"
                pw.write({
                    "passage_id": pid, "source_id": source_id,
                    "canonical_ref": f"{toh} :: {lab}",
                    "parent_ref": toh, "ref_sort": j,
                    "language": "en", "script": "latn",
                    "text": body, "normalized_text": normalize_text(body),
                    "heading": title if j == 0 else "",
                    "tags_json": json.dumps(["kangyur", "84000"], ensure_ascii=False),
                    "text_hash": text_hash(body),
                })
            if (i + 1) % 20 == 0:
                print(f"  {i+1}/{len(tohs)} done", flush=True)
    finally:
        sw.close(); pw.close()
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
