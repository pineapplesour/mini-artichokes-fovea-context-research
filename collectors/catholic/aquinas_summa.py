#!/usr/bin/env python3
"""Aquinas Summa Theologiae from newadvent.org (PD).

Structure:
  /summa/index.html → list of parts (FP, FS, SS, TP, XP, Suppl)
  Each part has questions /summa/X###.htm
  Each question has articles /summa/X###NNN.htm or article-numbered urls

We keep it simple: walk the index → fetch each question page → extract Article body.
"""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _lib.polite_client import PoliteClient
from _lib.jsonl_writer import JsonlWriter, text_hash, normalize_text

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw" / "christian" / "catholic" / "newadvent" / "summa"
CORPUS = ROOT / "corpus" / "christian"

INDEX = "https://www.newadvent.org/summa/"

PART_LABELS = {
    "FP":   ("Prima Pars",                "Pt. I",   100),
    "FS":   ("Prima Secundae",            "Pt. I-II", 200),
    "SS":   ("Secunda Secundae",          "Pt. II-II", 300),
    "TP":   ("Tertia Pars",               "Pt. III", 400),
    "XP":   ("Supplementum (post-mortem)","Suppl.", 500),
}


async def fetch(client, url, ref=None) -> str | None:
    cache = RAW / url.replace(INDEX, "").replace("/", "_")
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.suffix:
        cache = cache.with_suffix(".html")
    return await client.get(url, cache_path=cache, referer=ref or INDEX,
                             expect_min_size=300)


async def main():
    CORPUS.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    client = PoliteClient(cache_root=ROOT / "raw" / "christian" / "catholic" / "newadvent")
    sources_w = JsonlWriter(CORPUS / "sources.jsonl")
    passages_w = JsonlWriter(CORPUS / "passages.jsonl")

    # 1) main index
    html = await fetch(client, INDEX)
    if not html:
        await client.aclose()
        raise SystemExit("summa index fetch failed")

    from bs4 import BeautifulSoup
    s = BeautifulSoup(html, "html.parser")
    # find links to question pages
    candidates = set()
    for a in s.find_all("a", href=True):
        h = a.get("href", "")
        # patterns: /summa/1.htm /summa/2001.htm /summa/3000.htm etc
        if re.fullmatch(r"\d{4}\.htm", h):
            candidates.add(h)
    print(f"[summa] candidate question pages from main index: {len(candidates)}")

    # We need to go deeper — newadvent main page just lists ToC. Question pages list articles.
    # Easier: fetch each XPYYY.htm page (X=part code 1-5, YYY=question number). Question pages
    # link to articles X-Q-Article. Use brute-force question loop with cache.
    # Question numbering in Aquinas (per newadvent URL convention is 1-119 for FP, 1-114 for FS, etc.)
    QUESTION_RANGES = {
        "1": (1, 119),    # FP
        "2": (1, 114),    # FS (URL prefix 2 covers Q1-114 of FS)
        "3": (1, 189),    # SS
        "4": (1, 90),     # TP
        "5": (1, 99),     # XP/Suppl
    }
    # Each URL: /summa/{part}{qnum:03d}{art:01d}.htm — too many combinations.
    # Instead, extract via question page itself. Newadvent puts each Q on its own URL like
    # /summa/1001.htm = FP Q1, /summa/2001.htm = FS Q1, etc.

    source_id = "christian.catholic.aquinas.summa.en"
    sources_w.write({
        "source_id": source_id,
        "religion": "christian",
        "tradition": "catholic",
        "school": "thomism",
        "source_kind": "commentary",
        "authority_level": 70,
        "authority_label": "authoritative_commentary",
        "title": "Summa Theologiae (Thomas Aquinas)",
        "subtitle": "English translation by Fathers of the English Dominican Province",
        "author_body": "Thomas Aquinas (Doctor Angelicus)",
        "edition": "newadvent.org",
        "language": "en",
        "script": "latn",
        "source_url": INDEX,
        "license": "Public Domain (1947 translation)",
        "license_notes": "newadvent.org transcription.",
        "valid_from": "1265",
        "valid_to": "1274",
        "text_hash": "",
    })

    n_pages = 0
    n_passages = 0
    for part, (qmin, qmax) in QUESTION_RANGES.items():
        for q in range(qmin, qmax + 1):
            url = f"{INDEX}{part}{q:03d}.htm"
            html = await fetch(client, url)
            if not html:
                continue
            n_pages += 1
            qs = BeautifulSoup(html, "html.parser")
            for nav in qs.find_all(["nav", "header", "footer"]):
                nav.decompose()
            text = qs.get_text("\n", strip=True)
            # Newadvent question pages list multiple articles "Article X. Whether..."
            # Split by 'Article ' headers
            parts_split = re.split(r"\n(?=Article\s+\d+\.)", text)
            for chunk in parts_split:
                m = re.match(r"Article\s+(\d+)\.\s*(.*?)(?:\n|$)", chunk, re.S)
                if m:
                    art_n = int(m.group(1))
                    body = chunk.strip()
                else:
                    # the question intro / objections segment
                    art_n = 0
                    body = chunk.strip()
                if len(body) < 80:
                    continue
                # cap individual passage to 12k chars to avoid massive single records
                if len(body) > 12000:
                    body = body[:12000]
                pid = f"{source_id}.{part}.{q:03d}.{art_n:02d}"
                passages_w.write({
                    "passage_id": pid,
                    "source_id": source_id,
                    "canonical_ref": f"ST {part}, Q{q}, Art.{art_n}",
                    "parent_ref": f"ST {part}, Q{q}",
                    "ref_sort": (int(part) * 1000 + q) * 100 + art_n,
                    "language": "en",
                    "script": "latn",
                    "text": body,
                    "normalized_text": normalize_text(body),
                    "heading": f"{PART_LABELS.get('FP' if part=='1' else 'FS' if part=='2' else 'SS' if part=='3' else 'TP' if part=='4' else 'XP', ('','',0))[1]} Q{q}",
                    "tags_json": "[\"summa\",\"aquinas\"]",
                    "text_hash": text_hash(body),
                })
                n_passages += 1
            if n_pages % 30 == 0:
                print(f"  pages {n_pages} passages {n_passages}", flush=True)

    sources_w.close()
    passages_w.close()
    await client.aclose()
    print(f"[summa] pages: {n_pages}, passages: {n_passages}")


if __name__ == "__main__":
    from bs4 import BeautifulSoup  # ensure import here too
    asyncio.run(main())
