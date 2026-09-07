#!/usr/bin/env python3
"""Qur'an via fawazahmed0/quran-api (CC0).

One JSON file per edition (full 6236 ayat). Single low-cost fetch each.
Branch is `1`. Filenames use HYPHEN (e.g., ara-quranuthmanihaf.json).
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

BASE = "https://raw.githubusercontent.com/fawazahmed0/quran-api/1/editions"

# Each edition is one JSON. Order: Arabic first (so translation links can resolve to Uthmani).
EDITIONS = [
    # source_id, file_name, lang, script, kind, title, license, authority_level
    ("islam.quran.fawaz.uthmani-haf",     "ara-quranuthmanihaf.json", "ar", "arab", "scripture",   "Qur'an Arabic Uthmani Hafs",          "CC0", 100),
    ("islam.quran.fawaz.simple",          "ara-quransimple.json",     "ar", "arab", "scripture",   "Qur'an Arabic Simple (search)",       "CC0", 100),
    ("islam.quran.fawaz.indopak",         "ara-quranindopak.json",    "ar", "arab", "scripture",   "Qur'an Arabic IndoPak script",        "CC0", 100),
    ("islam.quran.fawaz.tr.yusufali",     "eng-abdullahyusufal.json", "en", "latn", "translation", "Qur'an English — Yusuf Ali",          "CC0/PD", 80),
    ("islam.quran.fawaz.tr.pickthall",    "eng-mohammedmarmadu.json", "en", "latn", "translation", "Qur'an English — Pickthall",          "CC0/PD", 80),
    ("islam.quran.fawaz.tr.hilali-khan",  "eng-muhammadtaqiudd.json", "en", "latn", "translation", "Qur'an English — Hilali & Khan",      "CC0", 80),
    ("islam.quran.fawaz.tr.itani",        "eng-talalitani.json",      "en", "latn", "translation", "Qur'an English — Clear Quran (Talal Itani)", "CC0", 80),
    ("islam.quran.fawaz.tr.khattab",      "eng-mustafakhattaba.json", "en", "latn", "translation", "Qur'an English — Mustafa Khattab (Clear Qur'an)", "CC0", 80),
    ("islam.quran.fawaz.tr.asad",         "eng-muhammadasad.json",    "en", "latn", "translation", "Qur'an English — Muhammad Asad (Message of the Qur'an)", "CC0", 80),
    ("islam.quran.fawaz.tr.usmani",       "eng-muftitaqiusmani.json", "en", "latn", "translation", "Qur'an English — Mufti Taqi Usmani",  "CC0", 80),
    ("islam.quran.fawaz.tr.korean.choi",  "kor-hamidchoi.json",       "ko", "hang", "translation", "Qur'an Korean — Choi Young-Gil (한국이슬람교)", "CC0", 80),
    ("islam.quran.fawaz.tr.korean.alt",   "kor-unknown.json",         "ko", "hang", "translation", "Qur'an Korean — alternate edition",   "CC0", 70),
]

# Sura name lookup (for canonical_ref labels)
SURA_NAMES_EN = [None, "Al-Fatihah", "Al-Baqarah", "Aal-i-Imran", "An-Nisa", "Al-Maidah", "Al-Anam", "Al-Araf", "Al-Anfal", "At-Tawbah", "Yunus",
"Hud", "Yusuf", "Ar-Rad", "Ibrahim", "Al-Hijr", "An-Nahl", "Al-Isra", "Al-Kahf", "Maryam", "Ta-Ha",
"Al-Anbiya", "Al-Hajj", "Al-Muminun", "An-Nur", "Al-Furqan", "Ash-Shuara", "An-Naml", "Al-Qasas", "Al-Ankabut", "Ar-Rum",
"Luqman", "As-Sajdah", "Al-Ahzab", "Saba", "Fatir", "Ya-Sin", "As-Saffat", "Sad", "Az-Zumar", "Ghafir",
"Fussilat", "Ash-Shura", "Az-Zukhruf", "Ad-Dukhan", "Al-Jathiyah", "Al-Ahqaf", "Muhammad", "Al-Fath", "Al-Hujurat", "Qaf",
"Adh-Dhariyat", "At-Tur", "An-Najm", "Al-Qamar", "Ar-Rahman", "Al-Waqiah", "Al-Hadid", "Al-Mujadilah", "Al-Hashr", "Al-Mumtahanah",
"As-Saff", "Al-Jumuah", "Al-Munafiqun", "At-Taghabun", "At-Talaq", "At-Tahrim", "Al-Mulk", "Al-Qalam", "Al-Haqqah", "Al-Maarij",
"Nuh", "Al-Jinn", "Al-Muzzammil", "Al-Muddathir", "Al-Qiyamah", "Al-Insan", "Al-Mursalat", "An-Naba", "An-Naziat", "Abasa",
"At-Takwir", "Al-Infitar", "Al-Mutaffifin", "Al-Inshiqaq", "Al-Buruj", "At-Tariq", "Al-Ala", "Al-Ghashiyah", "Al-Fajr", "Al-Balad",
"Ash-Shams", "Al-Layl", "Ad-Duha", "Ash-Sharh", "At-Tin", "Al-Alaq", "Al-Qadr", "Al-Bayyinah", "Az-Zalzalah", "Al-Adiyat",
"Al-Qariah", "At-Takathur", "Al-Asr", "Al-Humazah", "Al-Fil", "Quraysh", "Al-Maun", "Al-Kawthar", "Al-Kafirun", "An-Nasr",
"Al-Masad", "Al-Ikhlas", "Al-Falaq", "An-Nas"]


async def fetch_edition(client: PoliteClient, source_id: str, fname: str) -> dict | None:
    url = f"{BASE}/{fname}"
    cache = RAW / "fawaz" / fname
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.exists() and cache.stat().st_size > 100000:
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except Exception:
            pass
    data = await client.get(url, cache_path=cache, expect_min_size=100000, binary=True)
    if not data:
        return None
    try:
        return json.loads(data.decode("utf-8", errors="replace"))
    except Exception as e:
        print(f"  ! json decode {fname}: {e}")
        return None


async def main():
    CORPUS.mkdir(parents=True, exist_ok=True)
    client = PoliteClient(cache_root=RAW)

    sources_w = JsonlWriter(CORPUS / "sources.jsonl")
    passages_w = JsonlWriter(CORPUS / "passages.jsonl")
    links_w = JsonlWriter(CORPUS / "links.jsonl")

    arabic_pid: dict[tuple[int, int], str] = {}

    try:
        # Use the canonical Uthmani ed for cross-translation linkage
        primary_arabic = "islam.quran.fawaz.uthmani-haf"

        for source_id, fname, lang, script, kind, title, lic, auth in EDITIONS:
            print(f"[fawaz] {source_id} ...", flush=True)
            d = await fetch_edition(client, source_id, fname)
            if not d or "quran" not in d:
                print(f"  ! failed {source_id}")
                continue
            ayat = d["quran"]
            print(f"  ayat: {len(ayat)}")

            sources_w.write({
                "source_id": source_id,
                "religion": "islam",
                "tradition": "all",
                "school": "",
                "source_kind": kind,
                "authority_level": auth,
                "authority_label": "canonical_scripture" if kind == "scripture" else "official_liturgy_ritual",
                "title": title,
                "subtitle": "via fawazahmed0/quran-api",
                "author_body": "",
                "edition": fname.replace(".json",""),
                "language": lang,
                "script": script,
                "source_url": f"{BASE}/{fname}",
                "license": lic,
                "license_notes": "Distributed by fawazahmed0/quran-api as CC0/public domain mirror.",
                "valid_from": "",
                "valid_to": "",
                "text_hash": "",
            })

            for a in ayat:
                s = int(a["chapter"])
                v = int(a["verse"])
                t = a["text"]
                pid = f"{source_id}.{s:03d}.{v:03d}"
                norm = normalize_text(t)
                h = text_hash(t)
                heading = SURA_NAMES_EN[s] if 1 <= s < len(SURA_NAMES_EN) else ""
                passages_w.write({
                    "passage_id": pid,
                    "source_id": source_id,
                    "canonical_ref": f"Quran {s}:{v}",
                    "parent_ref": f"Quran {s}",
                    "ref_sort": s * 10000 + v,
                    "language": lang,
                    "script": script,
                    "text": t,
                    "normalized_text": norm,
                    "heading": heading if v == 1 else "",
                    "tags_json": "[]",
                    "text_hash": h,
                })
                if source_id == primary_arabic:
                    arabic_pid[(s, v)] = pid
                elif kind == "translation":
                    arab = arabic_pid.get((s, v))
                    if arab:
                        links_w.write({
                            "from_passage_id": pid,
                            "to_passage_id": arab,
                            "link_type": "translation_of",
                            "confidence": 1.0,
                            "note": "approved meaning translation; do_not_machine_retranslate",
                            "text_hash": text_hash(f"{pid}->{arab}:translation_of"),
                        })

    finally:
        sources_w.close()
        passages_w.close()
        links_w.close()
        await client.aclose()

    print("[fawaz] done.")


if __name__ == "__main__":
    asyncio.run(main())
