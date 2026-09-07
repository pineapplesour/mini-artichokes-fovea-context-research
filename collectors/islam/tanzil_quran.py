#!/usr/bin/env python3
"""Tanzil Qur'an: Arabic Uthmani + Simple + 4 English translations.

Tanzil distributes single .txt files. One small wget per file. No risk of WAF.

Each line: "sura|ayah|text"
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
RAW = ROOT / "raw" / "islam" / "tanzil"
CORPUS = ROOT / "corpus" / "islam"

# Tanzil official simple/full URLs use HTTP at tanzil.net but mirrored CC at tanzil.net/pub/download
TANZIL_FILES = [
    # source_id, url, language, script, label, title, license_label
    ("islam.quran.tanzil.uthmani", "https://tanzil.net/pub/download/index.php?quranType=uthmani&outType=txt&lang=ar&format=quran-uthmani.txt", "ar", "arab", "scripture", "Qur'an Arabic Uthmani (Hafs)", "CC-BY-ND-3.0"),
    ("islam.quran.tanzil.simple",  "https://tanzil.net/pub/download/index.php?quranType=simple&outType=txt&lang=ar&format=quran-simple-clean.txt", "ar", "arab", "scripture", "Qur'an Arabic Simple Clean", "CC-BY-ND-3.0"),
    ("islam.quran.tr.saheeh",      "https://tanzil.net/trans/?transID=en.sahih&type=txt", "en", "latn", "translation", "Qur'an English — Saheeh International", "Translation by Saheeh Int'l"),
    ("islam.quran.tr.yusufali",    "https://tanzil.net/trans/?transID=en.yusufali&type=txt", "en", "latn", "translation", "Qur'an English — Yusuf Ali", "Public Domain"),
    ("islam.quran.tr.pickthall",   "https://tanzil.net/trans/?transID=en.pickthall&type=txt", "en", "latn", "translation", "Qur'an English — Pickthall", "Public Domain"),
    ("islam.quran.tr.hilali",      "https://tanzil.net/trans/?transID=en.hilali&type=txt", "en", "latn", "translation", "Qur'an English — Hilali & Khan", "Translation © distributors"),
]

# Fallback mirrors (raw github)
FALLBACKS = {
    "islam.quran.tanzil.uthmani": [
        "https://raw.githubusercontent.com/risan/quran-json/main/dist/quran.json",  # different format - skip
        "https://raw.githubusercontent.com/risan/quran-json/main/data/quran-uthmani.txt",  # may not exist
    ],
}


async def download_one(client: PoliteClient, source_id: str, url: str) -> bytes | None:
    cache = RAW / f"{source_id}.txt"
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.exists() and cache.stat().st_size > 100000:
        return cache.read_bytes()
    data = await client.get(url, cache_path=cache, expect_min_size=100000, binary=True,
                             accept="text/plain,*/*;q=0.8")
    if not data:
        return None
    return data


def parse_tanzil_lines(text: str) -> list[tuple[int, int, str]]:
    """Tanzil format: 'sura|ayah|text'. Skip comments/blank."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        try:
            s = int(parts[0]); a = int(parts[1])
        except ValueError:
            continue
        out.append((s, a, parts[2].strip()))
    return out


async def main():
    CORPUS.mkdir(parents=True, exist_ok=True)
    sources_path = CORPUS / "sources.jsonl"
    passages_path = CORPUS / "passages.jsonl"
    links_path = CORPUS / "links.jsonl"

    client = PoliteClient(cache_root=ROOT / "raw" / "islam")

    sources_w = JsonlWriter(sources_path)
    passages_w = JsonlWriter(passages_path)
    links_w = JsonlWriter(links_path)

    arabic_passage_ids: dict[tuple[int, int], str] = {}

    try:
        for source_id, url, lang, script, kind, title, lic in TANZIL_FILES:
            print(f"[tanzil] {source_id} ...", flush=True)
            data = await download_one(client, source_id, url)
            if not data:
                print(f"  ! failed: {source_id}")
                continue

            authority_level = 100 if kind == "scripture" else 80
            authority_label = "canonical_scripture" if kind == "scripture" else "official_liturgy_ritual"
            sources_w.write({
                "source_id": source_id,
                "religion": "islam",
                "tradition": "all",
                "school": "",
                "source_kind": kind,
                "authority_level": authority_level,
                "authority_label": authority_label,
                "title": title,
                "subtitle": "",
                "author_body": "",
                "edition": "Tanzil distribution",
                "language": lang,
                "script": script,
                "source_url": url,
                "license": lic,
                "license_notes": "Tanzil project — see tanzil.net for redistribution terms.",
                "valid_from": "",
                "valid_to": "",
                "text_hash": "",
            })

            text = data.decode("utf-8", errors="replace")
            triples = parse_tanzil_lines(text)
            print(f"  parsed {len(triples)} ayat")

            for s, a, ayah_text in triples:
                ref_sort = s * 10000 + a
                pid = f"{source_id}.{s:03d}.{a:03d}"
                norm = normalize_text(ayah_text)
                h = text_hash(ayah_text)
                passages_w.write({
                    "passage_id": pid,
                    "source_id": source_id,
                    "canonical_ref": f"Quran {s}:{a}",
                    "parent_ref": f"Quran {s}",
                    "ref_sort": ref_sort,
                    "language": lang,
                    "script": script,
                    "text": ayah_text,
                    "normalized_text": norm,
                    "heading": "",
                    "tags_json": "[]",
                    "text_hash": h,
                })
                if kind == "scripture" and source_id == "islam.quran.tanzil.uthmani":
                    arabic_passage_ids[(s, a)] = pid
                elif kind == "translation":
                    arab_pid = arabic_passage_ids.get((s, a))
                    if arab_pid:
                        links_w.write({
                            "from_passage_id": pid,
                            "to_passage_id": arab_pid,
                            "link_type": "translation_of",
                            "confidence": 1.0,
                            "note": "approved meaning translation; do_not_machine_retranslate",
                            "text_hash": text_hash(f"{pid}->{arab_pid}:translation_of"),
                        })

    finally:
        sources_w.close()
        passages_w.close()
        links_w.close()
        await client.aclose()

    print(f"\n[tanzil] done.")
    print(f"  sources: {sources_path}")
    print(f"  passages: {passages_path}")
    print(f"  links: {links_path}")


if __name__ == "__main__":
    asyncio.run(main())
