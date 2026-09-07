#!/usr/bin/env python3
"""Tafsir per-ayah from api.quran.com (Ibn Kathir, Tabari, Khattab).

6236 ayat × 3 tafsirs = 18,708 polite calls. ~5s/call → ~26 hours.
Resumable via cache. Run as long-term background.
"""
from __future__ import annotations

import asyncio, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _lib.polite_client import PoliteClient
from _lib.jsonl_writer import JsonlWriter, text_hash, normalize_text

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw" / "islam" / "tafsir"
CORPUS = ROOT / "corpus" / "islam"

API = "https://api.quran.com/api/v4/tafsirs"

TAFSIRS = [
    (169, "islam.tafsir.ibn-kathir.en",  "en", "latn", "Tafsir Ibn Kathir (English Abridged)", "sunni", 70),
    (15,  "islam.tafsir.tabari.ar",      "ar", "arab", "Tafsir al-Tabari Jami' al-Bayan",   "sunni", 80),
]


async def fetch_one(client, tid: int, key: str) -> str | None:
    url = f"{API}/{tid}/by_ayah/{key}"
    cache = RAW / f"{tid}" / f"{key}.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.exists() and cache.stat().st_size > 50:
        return cache.read_text(encoding="utf-8")
    txt = await client.get(url, cache_path=cache, expect_min_size=50)
    return txt


async def main():
    CORPUS.mkdir(parents=True, exist_ok=True)
    client = PoliteClient(cache_root=ROOT / "raw" / "islam")
    sources_w = JsonlWriter(CORPUS / "sources.jsonl")
    passages_w = JsonlWriter(CORPUS / "passages.jsonl")
    links_w = JsonlWriter(CORPUS / "links.jsonl")

    # 6236 ayat: build (chapter, verse) list
    ayat = []
    SURA_LEN = [0,7,286,200,176,120,165,206,75,129,109,123,111,43,52,99,128,111,110,98,135,
                112,78,118,64,77,227,93,88,69,60,34,30,73,54,45,83,182,88,75,85,54,53,89,
                59,37,35,38,29,18,45,60,49,62,55,78,96,29,22,24,13,14,11,11,18,12,12,30,
                52,52,44,28,28,20,56,40,31,50,40,46,42,29,19,36,25,22,17,19,26,30,20,15,21,
                11,8,8,19,5,8,8,11,11,8,3,9,5,4,7,3,6,3,5,4,5,6]
    for s in range(1,115):
        for v in range(1, SURA_LEN[s]+1):
            ayat.append((s,v))

    try:
        for tid, source_id, lang, script, title, school, auth in TAFSIRS:
            print(f"[tafsir] {source_id} ({title}) ...", flush=True)
            sources_w.write({
                "source_id": source_id, "religion": "islam",
                "tradition": "sunni", "school": school,
                "source_kind": "commentary",
                "authority_level": auth,
                "authority_label": "authoritative_commentary",
                "title": title,
                "subtitle": "via api.quran.com",
                "author_body": "",
                "edition": f"qurancom tafsir id={tid}",
                "language": lang, "script": script,
                "source_url": f"{API}/{tid}",
                "license": "Quran.com Public API (educational use)",
                "license_notes": "Per quran.com terms of use.",
                "valid_from": "", "valid_to": "", "text_hash": "",
            })
            n = 0
            for s, v in ayat:
                key = f"{s}:{v}"
                raw = await fetch_one(client, tid, key)
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except Exception:
                    continue
                t = obj.get("tafsir", {})
                txt = t.get("text", "")
                if not txt:
                    continue
                # strip basic html
                import re
                cleaned = re.sub(r"<[^>]+>", " ", txt)
                cleaned = re.sub(r"\s+", " ", cleaned).strip()
                if not cleaned:
                    continue
                pid = f"{source_id}.{s:03d}.{v:03d}"
                passages_w.write({
                    "passage_id": pid, "source_id": source_id,
                    "canonical_ref": f"{title} on Quran {s}:{v}",
                    "parent_ref": f"Quran {s}",
                    "ref_sort": s*10000+v,
                    "language": lang, "script": script,
                    "text": cleaned[:8000],
                    "normalized_text": normalize_text(cleaned[:8000]),
                    "heading": "",
                    "tags_json": "[\"tafsir\"]",
                    "text_hash": text_hash(cleaned[:8000]),
                })
                # link to Arabic Uthmani primary
                arab_pid = f"islam.quran.fawaz.uthmani-haf.{s:03d}.{v:03d}"
                links_w.write({
                    "from_passage_id": pid, "to_passage_id": arab_pid,
                    "link_type": "commentary_on", "confidence": 1.0,
                    "note": "tafsir on this ayah",
                    "text_hash": text_hash(f"{pid}->{arab_pid}:commentary_on"),
                })
                n += 1
                if n % 200 == 0:
                    print(f"  {source_id}: {n}/{len(ayat)}", flush=True)
            print(f"  {source_id}: {n} passages")
    finally:
        sources_w.close(); passages_w.close(); links_w.close()
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
