#!/usr/bin/env python3
"""Catholic Bible via scrollmapper/bible_databases (PD).

DRC (Douay-Rheims-Challoner), CPDV (Catholic Public Domain Version),
VulgClementine (Clementine Vulgate), KorRV (Korean Revised) — all single JSON files.
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
RAW = ROOT / "raw" / "christian" / "catholic"
CORPUS = ROOT / "corpus" / "christian"

BASE = "https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json"

# (source_id, file, lang, script, kind, title, authority, license, primary_or_translation)
EDITIONS = [
    ("christian.catholic.bible.drc",          "DRC.json",            "en", "latn", "scripture", "Douay-Rheims Bible (Challoner Revision)",       100, "Public Domain", "primary"),
    ("christian.catholic.bible.cpdv",         "CPDV.json",           "en", "latn", "scripture", "Catholic Public Domain Version",                100, "Public Domain", "primary"),
    ("christian.catholic.bible.vulgclem",     "VulgClementine.json", "la", "latn", "scripture", "Clementine Vulgate (Sixto-Clementine, 1592)",   100, "Public Domain", "primary"),
    ("christian.catholic.bible.vulgsistine",  "VulgSistine.json",    "la", "latn", "scripture", "Sistine Vulgate (1590)",                        100, "Public Domain", "primary"),
    ("christian.catholic.bible.kor.korrv",    "KorRV.json",          "ko", "hang", "scripture", "Korean Revised Version (개역) — Protestant 66 books", 90,  "Public Domain", "primary"),
]

BOOK_ORDER = {  # canonical Catholic ordering for ref_sort
    "Genesis": 1, "Exodus": 2, "Leviticus": 3, "Numbers": 4, "Deuteronomy": 5,
    "Joshua": 6, "Judges": 7, "Ruth": 8,
    "I Samuel": 9, "1 Samuel": 9, "II Samuel": 10, "2 Samuel": 10,
    "I Kings": 11, "1 Kings": 11, "II Kings": 12, "2 Kings": 12,
    "I Chronicles": 13, "1 Chronicles": 13, "II Chronicles": 14, "2 Chronicles": 14,
    "Ezra": 15, "Nehemiah": 16, "Tobit": 17, "Judith": 18, "Esther": 19,
    "Job": 20, "Psalms": 21, "Proverbs": 22, "Ecclesiastes": 23,
    "Song of Solomon": 24, "Song of Songs": 24, "Canticles": 24,
    "Wisdom": 25, "Sirach": 26, "Ecclesiasticus": 26,
    "Isaiah": 27, "Jeremiah": 28, "Lamentations": 29, "Baruch": 30, "Ezekiel": 31,
    "Daniel": 32, "Hosea": 33, "Joel": 34, "Amos": 35, "Obadiah": 36,
    "Jonah": 37, "Micah": 38, "Nahum": 39, "Habakkuk": 40, "Zephaniah": 41,
    "Haggai": 42, "Zechariah": 43, "Malachi": 44,
    "I Maccabees": 45, "1 Maccabees": 45, "II Maccabees": 46, "2 Maccabees": 46,
    "Matthew": 47, "Mark": 48, "Luke": 49, "John": 50,
    "Acts": 51, "Romans": 52,
    "I Corinthians": 53, "1 Corinthians": 53, "II Corinthians": 54, "2 Corinthians": 54,
    "Galatians": 55, "Ephesians": 56, "Philippians": 57, "Colossians": 58,
    "I Thessalonians": 59, "1 Thessalonians": 59, "II Thessalonians": 60, "2 Thessalonians": 60,
    "I Timothy": 61, "1 Timothy": 61, "II Timothy": 62, "2 Timothy": 62,
    "Titus": 63, "Philemon": 64, "Hebrews": 65, "James": 66,
    "I Peter": 67, "1 Peter": 67, "II Peter": 68, "2 Peter": 68,
    "I John": 69, "1 John": 69, "II John": 70, "2 John": 70, "III John": 71, "3 John": 71,
    "Jude": 72, "Revelation": 73, "Revelation of John": 73,
    # apocrypha (after canonical)
    "Prayer of Manasses": 80, "I Esdras": 81, "1 Esdras": 81,
    "II Esdras": 82, "2 Esdras": 82, "Additional Psalm": 83, "Laodiceans": 84,
}

# Book name → standard short name for canonical_ref
BOOK_SHORT = {
    "I Samuel": "1Sam", "II Samuel": "2Sam", "I Kings": "1Kgs", "II Kings": "2Kgs",
    "I Chronicles": "1Chr", "II Chronicles": "2Chr",
    "I Maccabees": "1Macc", "II Maccabees": "2Macc",
    "I Corinthians": "1Cor", "II Corinthians": "2Cor",
    "I Thessalonians": "1Thess", "II Thessalonians": "2Thess",
    "I Timothy": "1Tim", "II Timothy": "2Tim",
    "I Peter": "1Pet", "II Peter": "2Pet",
    "I John": "1Jn", "II John": "2Jn", "III John": "3Jn",
    "Song of Solomon": "Song", "Song of Songs": "Song",
    "Revelation of John": "Rev",
    "Genesis": "Gen", "Exodus": "Exod", "Leviticus": "Lev", "Numbers": "Num",
    "Deuteronomy": "Deut", "Joshua": "Josh", "Judges": "Judg", "Ruth": "Ruth",
    "Ezra": "Ezra", "Nehemiah": "Neh", "Tobit": "Tob", "Judith": "Jdt",
    "Esther": "Esth", "Job": "Job", "Psalms": "Ps", "Proverbs": "Prov",
    "Ecclesiastes": "Eccl", "Wisdom": "Wis", "Sirach": "Sir",
    "Isaiah": "Isa", "Jeremiah": "Jer", "Lamentations": "Lam",
    "Baruch": "Bar", "Ezekiel": "Ezek", "Daniel": "Dan", "Hosea": "Hos",
    "Joel": "Joel", "Amos": "Amos", "Obadiah": "Obad", "Jonah": "Jonah",
    "Micah": "Mic", "Nahum": "Nah", "Habakkuk": "Hab", "Zephaniah": "Zeph",
    "Haggai": "Hag", "Zechariah": "Zech", "Malachi": "Mal",
    "Matthew": "Matt", "Mark": "Mark", "Luke": "Luke", "John": "John",
    "Acts": "Acts", "Romans": "Rom",
    "Galatians": "Gal", "Ephesians": "Eph", "Philippians": "Phil",
    "Colossians": "Col", "Titus": "Titus", "Philemon": "Phlm",
    "Hebrews": "Heb", "James": "Jas", "Jude": "Jude",
}


def short_book(name: str) -> str:
    return BOOK_SHORT.get(name, name.replace(" ", ""))


async def fetch_one(client, fname: str) -> dict | None:
    url = f"{BASE}/{fname}"
    cache = RAW / "scrollmapper" / fname
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
        print(f"  ! json {fname}: {e}")
        return None


async def main():
    CORPUS.mkdir(parents=True, exist_ok=True)
    client = PoliteClient(cache_root=RAW)
    sources_w = JsonlWriter(CORPUS / "sources.jsonl")
    passages_w = JsonlWriter(CORPUS / "passages.jsonl")
    links_w = JsonlWriter(CORPUS / "links.jsonl")

    # primary (Latin Vulgate Clementine) is canonical reference for translation_of links
    primary_id = "christian.catholic.bible.vulgclem"
    primary_pid: dict[tuple[str, int, int], str] = {}

    try:
        # Order: vulgclem first (so others can link to it), then DRC, CPDV, sistine, korrv
        ordering = sorted(EDITIONS, key=lambda e: 0 if e[0] == primary_id else 1)
        for source_id, fname, lang, script, kind, title, auth, lic, primary in ordering:
            print(f"[bible] {source_id} ...", flush=True)
            d = await fetch_one(client, fname)
            if not d or "books" not in d:
                print(f"  ! failed {source_id}")
                continue

            sources_w.write({
                "source_id": source_id,
                "religion": "christian",
                "tradition": "catholic",
                "school": "latin" if lang == "la" else "",
                "source_kind": kind,
                "authority_level": auth,
                "authority_label": "canonical_scripture",
                "title": title,
                "subtitle": d.get("translation", ""),
                "author_body": "",
                "edition": fname.replace(".json", ""),
                "language": lang,
                "script": script,
                "source_url": f"{BASE}/{fname}",
                "license": lic,
                "license_notes": "scrollmapper/bible_databases mirror",
                "valid_from": "",
                "valid_to": "",
                "text_hash": "",
            })

            n_verses = 0
            for book in d["books"]:
                bname = book.get("name", "")
                bord = BOOK_ORDER.get(bname, 99)
                for chap in book.get("chapters", []):
                    cnum = int(chap.get("chapter", 0))
                    for v in chap.get("verses", []):
                        vnum = int(v.get("verse", 0))
                        text = v.get("text", "").strip()
                        if not text:
                            continue
                        sb = short_book(bname)
                        canonical = f"{sb} {cnum}:{vnum}"
                        pid = f"{source_id}.{bord:03d}.{cnum:03d}.{vnum:03d}"
                        passages_w.write({
                            "passage_id": pid,
                            "source_id": source_id,
                            "canonical_ref": canonical,
                            "parent_ref": f"{sb} {cnum}",
                            "ref_sort": bord * 1000000 + cnum * 1000 + vnum,
                            "language": lang,
                            "script": script,
                            "text": text,
                            "normalized_text": normalize_text(text),
                            "heading": bname if cnum == 1 and vnum == 1 else "",
                            "tags_json": "[]",
                            "text_hash": text_hash(text),
                        })
                        n_verses += 1
                        key = (bname, cnum, vnum)
                        if source_id == primary_id:
                            primary_pid[key] = pid
                        else:
                            par = primary_pid.get(key)
                            if par:
                                links_w.write({
                                    "from_passage_id": pid,
                                    "to_passage_id": par,
                                    "link_type": "translation_of",
                                    "confidence": 0.9,
                                    "note": f"verse-aligned with {primary_id}",
                                    "text_hash": text_hash(f"{pid}->{par}:translation_of"),
                                })
            print(f"  verses: {n_verses}")

    finally:
        sources_w.close()
        passages_w.close()
        links_w.close()
        await client.aclose()

    print("[bible] done.")


if __name__ == "__main__":
    asyncio.run(main())
