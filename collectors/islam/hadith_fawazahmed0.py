#!/usr/bin/env python3
"""Hadith via fawazahmed0/hadith-api (CC0).

10 collections × multiple language editions. Single JSON file each.
We grab Arabic + English for each, plus 40 Nawawi/Qudsi/Dehlawi.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _lib.polite_client import PoliteClient
from _lib.jsonl_writer import JsonlWriter, text_hash, normalize_text

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw" / "islam"
CORPUS = ROOT / "corpus" / "islam"

BASE = "https://raw.githubusercontent.com/fawazahmed0/hadith-api/1/editions"

# (book_key, full_name, authority_level, source_kind, traditions_with_authority)
BOOKS = [
    ("bukhari",  "Sahih al-Bukhari", 90, "hadith"),
    ("muslim",   "Sahih Muslim",     90, "hadith"),
    ("abudawud", "Sunan Abi Dawud",  85, "hadith"),
    ("tirmidhi", "Jami at-Tirmidhi", 85, "hadith"),
    ("nasai",    "Sunan an-Nasa'i",  85, "hadith"),
    ("ibnmajah", "Sunan Ibn Majah",  85, "hadith"),
    ("malik",    "Muwatta Malik",    80, "hadith"),
    ("nawawi",   "40 Hadith Nawawi", 70, "hadith"),
    ("qudsi",    "40 Hadith Qudsi",  70, "hadith"),
    ("dehlawi",  "40 Hadith Dehlawi (Shah Waliullah)", 60, "hadith"),
]

# Languages to fetch per book
LANGS = [
    ("ara", "ar", "arab"),
    ("eng", "en", "latn"),
]


async def fetch_edition(client, book: str, lang_prefix: str) -> dict | None:
    fname = f"{lang_prefix}-{book}.json"
    url = f"{BASE}/{fname}"
    cache = RAW / "hadith" / fname
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.exists() and cache.stat().st_size > 1000:
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except Exception:
            pass
    data = await client.get(url, cache_path=cache, expect_min_size=1000, binary=True)
    if not data:
        return None
    try:
        return json.loads(data.decode("utf-8", errors="replace"))
    except Exception as e:
        print(f"  ! json {fname}: {e}")
        return None


async def main():
    CORPUS.mkdir(parents=True, exist_ok=True)
    client = PoliteClient(cache_root=RAW)
    sources_w = JsonlWriter(CORPUS / "sources.jsonl")
    passages_w = JsonlWriter(CORPUS / "passages.jsonl")
    links_w = JsonlWriter(CORPUS / "links.jsonl")

    arabic_pid: dict[tuple[str, int], str] = {}

    try:
        for book, fullname, auth, kind in BOOKS:
            for lang_prefix, lang, script in LANGS:
                source_id = f"islam.hadith.{book}.{lang_prefix}"
                print(f"[hadith] {source_id} ...", flush=True)
                d = await fetch_edition(client, book, lang_prefix)
                if not d or "hadiths" not in d:
                    print(f"  ! failed {source_id}")
                    continue
                meta = d.get("metadata", {})
                sections = meta.get("sections", {}) or {}

                sources_w.write({
                    "source_id": source_id,
                    "religion": "islam",
                    "tradition": "sunni",
                    "school": "",
                    "source_kind": kind,
                    "authority_level": auth,
                    "authority_label": "official_core_doctrine" if auth >= 90 else (
                        "official_liturgy_ritual" if auth >= 80 else "authoritative_commentary"),
                    "title": fullname + (f" — {meta.get('name','')}" if meta.get("name") else ""),
                    "subtitle": "fawazahmed0/hadith-api edition",
                    "author_body": "",
                    "edition": f"{lang_prefix}-{book}",
                    "language": lang,
                    "script": script,
                    "source_url": f"{BASE}/{lang_prefix}-{book}.json",
                    "license": "CC0",
                    "license_notes": "Distributed by fawazahmed0/hadith-api as CC0/public-domain compilation.",
                    "valid_from": "",
                    "valid_to": "",
                    "text_hash": "",
                })

                hadiths = d["hadiths"]
                print(f"  hadiths: {len(hadiths)}")

                primary_arabic = (lang_prefix == "ara")

                for h in hadiths:
                    num = h.get("hadithnumber")
                    if num is None:
                        continue
                    text = h.get("text", "").strip()
                    if not text:
                        continue
                    ref = h.get("reference", {}) or {}
                    book_no = ref.get("book", 0)
                    section_name = sections.get(str(book_no), "")
                    pid = f"{source_id}.{int(num):05d}"
                    canonical = f"{fullname} {num}"
                    if book_no:
                        canonical = f"{fullname} Book {book_no}, Hadith {num}"
                    grades = h.get("grades", []) or []
                    tags = []
                    for g in grades:
                        if isinstance(g, dict):
                            grad = g.get("grade", "")
                            if grad:
                                tags.append(f"grade:{grad.lower()}")
                    passages_w.write({
                        "passage_id": pid,
                        "source_id": source_id,
                        "canonical_ref": canonical,
                        "parent_ref": f"{fullname} Book {book_no}" if book_no else fullname,
                        "ref_sort": int(num),
                        "language": lang,
                        "script": script,
                        "text": text,
                        "normalized_text": normalize_text(text),
                        "heading": section_name,
                        "tags_json": json.dumps(tags, ensure_ascii=False),
                        "text_hash": text_hash(text),
                    })
                    if primary_arabic:
                        arabic_pid[(book, int(num))] = pid
                    else:
                        arab = arabic_pid.get((book, int(num)))
                        if arab:
                            links_w.write({
                                "from_passage_id": pid,
                                "to_passage_id": arab,
                                "link_type": "translation_of",
                                "confidence": 0.95,
                                "note": "english edition aligned by hadith number",
                                "text_hash": text_hash(f"{pid}->{arab}:translation_of"),
                            })

    finally:
        sources_w.close()
        passages_w.close()
        links_w.close()
        await client.aclose()

    print("[hadith] done.")


if __name__ == "__main__":
    asyncio.run(main())
