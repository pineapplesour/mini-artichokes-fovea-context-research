#!/usr/bin/env python3
"""Bhagavad Gita: Sanskrit text + 4907 translations/commentaries (gita/gita).

Single-shot fetch of 5 small JSONs.
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
RAW = ROOT / "raw" / "hindu" / "gita-data"
CORPUS = ROOT / "corpus" / "hindu"
BASE = "https://raw.githubusercontent.com/gita/gita/main/data"

FILES = ["chapters.json", "verse.json", "translation.json",
         "commentary.json", "languages.json", "authors.json"]


# Authority by author / sampradaya. Swamis classed as commentary, classical bhāṣyās higher.
CLASSIC_BHASYAKARS = {
    "Sri Shankaracharya":     ("advaita",   90, "official_core_doctrine"),
    "Sri Ramanujacharya":     ("vishishtadvaita", 90, "official_core_doctrine"),
    "Sri Madhavacharya":      ("dvaita",    90, "official_core_doctrine"),
    "Sri Madhusudan Saraswati": ("advaita",  80, "authoritative_commentary"),
    "Sri Sridhara Swami":     ("advaita",   80, "authoritative_commentary"),
    "Sri Abhinavgupta":       ("kashmir-shaivism", 80, "authoritative_commentary"),
    "Sri Vedantadeshikacharya Venkatanatha": ("vishishtadvaita", 80, "authoritative_commentary"),
    "Sri Jayatritha":         ("dvaita",    80, "authoritative_commentary"),
    "Sri Anandgiri":          ("advaita",   70, "authoritative_commentary"),
    "Sri Dhanpati":           ("advaita",   70, "authoritative_commentary"),
    "Sri Neelkanth":          ("various",   70, "authoritative_commentary"),
    "Sri Purushottamji":      ("shuddhadvaita", 70, "authoritative_commentary"),
    "Swami Ramsukhdas":       ("modern",    60, "school_treatise"),
    "Swami Chinmayananda":    ("modern",    60, "school_treatise"),
}


async def fetch_files(client):
    out = {}
    for f in FILES:
        cache = RAW / f
        cache.parent.mkdir(parents=True, exist_ok=True)
        if cache.exists() and cache.stat().st_size > 100:
            out[f] = json.loads(cache.read_text(encoding="utf-8"))
            continue
        data = await client.get(f"{BASE}/{f}", cache_path=cache,
                                 expect_min_size=100, binary=True)
        if not data:
            print(f"  ! failed {f}")
            continue
        out[f] = json.loads(data.decode("utf-8", errors="replace"))
    return out


async def main():
    CORPUS.mkdir(parents=True, exist_ok=True)
    client = PoliteClient(cache_root=ROOT / "raw" / "hindu")
    sources_w = JsonlWriter(CORPUS / "sources.jsonl")
    passages_w = JsonlWriter(CORPUS / "passages.jsonl")
    links_w = JsonlWriter(CORPUS / "links.jsonl")

    try:
        data = await fetch_files(client)

        chapters = {c["chapter_number"]: c for c in data.get("chapters.json", [])}
        languages = {l["id"]: l["language"] for l in data.get("languages.json", [])}
        authors = {a["id"]: a["name"] for a in data.get("authors.json", [])}
        verses = data.get("verse.json", [])
        translations = data.get("translation.json", [])
        commentaries = data.get("commentary.json", [])

        # 1) Sanskrit verses (canonical)
        sk_source = "hindu.gita.sanskrit"
        sources_w.write({
            "source_id": sk_source,
            "religion": "hindu",
            "tradition": "all",
            "school": "",
            "source_kind": "scripture",
            "authority_level": 100,
            "authority_label": "canonical_scripture",
            "title": "Bhagavad Gita (Sanskrit)",
            "subtitle": "śloka with transliteration",
            "author_body": "Vyasa (traditionally) — within Mahabharata, Bhishma Parva 23–40",
            "edition": "gita/gita data dump",
            "language": "sa",
            "script": "deva",
            "source_url": f"{BASE}/verse.json",
            "license": "Open data (project license)",
            "license_notes": "Source: gita/gita repo (community contributed).",
            "valid_from": "",
            "valid_to": "",
            "text_hash": "",
        })
        verse_pid: dict[int, str] = {}
        for v in verses:
            cnum = v["chapter_number"]
            vnum = v["verse_number"]
            text = v.get("text", "").strip()
            if not text:
                continue
            pid = f"{sk_source}.{cnum:02d}.{vnum:03d}"
            ch_obj = chapters.get(cnum, {})
            heading = ch_obj.get("name") or ch_obj.get("name_translated") or ""
            passages_w.write({
                "passage_id": pid,
                "source_id": sk_source,
                "canonical_ref": f"BG {cnum}.{vnum}",
                "parent_ref": f"BG {cnum}",
                "ref_sort": cnum * 1000 + vnum,
                "language": "sa",
                "script": "deva",
                "text": text,
                "normalized_text": normalize_text(text),
                "heading": heading if vnum == 1 else "",
                "tags_json": json.dumps([], ensure_ascii=False),
                "text_hash": text_hash(text),
            })
            verse_pid[v["id"]] = pid

            # transliteration as a separate (latn) passage linked
            tr_lit = v.get("transliteration", "").strip()
            if tr_lit:
                pid_lit = f"{sk_source}.lit.{cnum:02d}.{vnum:03d}"
                passages_w.write({
                    "passage_id": pid_lit,
                    "source_id": sk_source,
                    "canonical_ref": f"BG {cnum}.{vnum} (transliteration)",
                    "parent_ref": f"BG {cnum}",
                    "ref_sort": cnum * 1000 + vnum,
                    "language": "sa",
                    "script": "latn",
                    "text": tr_lit,
                    "normalized_text": normalize_text(tr_lit),
                    "heading": "",
                    "tags_json": '["transliteration"]',
                    "text_hash": text_hash(tr_lit),
                })
                links_w.write({
                    "from_passage_id": pid_lit,
                    "to_passage_id": pid,
                    "link_type": "transliteration_of",
                    "confidence": 1.0,
                    "note": "IAST/Devanagari aligned",
                    "text_hash": text_hash(f"{pid_lit}->{pid}:transliteration_of"),
                })

        # 2) Translations & 3) Commentaries grouped by (lang, author) -> single source
        def emit(records: list[dict], kind_label: str, default_authority: int, default_label: str):
            grouped: dict[tuple[str, str], list[dict]] = {}
            for r in records:
                lang = languages.get(r.get("language_id"), "unknown")
                author = authors.get(r.get("author_id"), "Unknown")
                grouped.setdefault((lang, author), []).append(r)
            for (lang, author), recs in grouped.items():
                school, auth, alabel = CLASSIC_BHASYAKARS.get(author,
                    ("modern" if author.lower().startswith("swami") else "various",
                     default_authority, default_label))
                lang_iso = {"english":"en","hindi":"hi","sanskrit":"sa"}.get(lang, lang)
                script = {"en":"latn","hi":"deva","sa":"deva"}.get(lang_iso, "")
                src_id = f"hindu.gita.{kind_label}.{lang_iso}.{author.lower().replace(' ','_').replace('.','')}"
                sources_w.write({
                    "source_id": src_id,
                    "religion": "hindu",
                    "tradition": "all" if school in ("modern","various") else school,
                    "school": school,
                    "source_kind": kind_label,
                    "authority_level": auth,
                    "authority_label": alabel,
                    "title": f"Bhagavad Gita {kind_label} ({author}, {lang})",
                    "subtitle": "",
                    "author_body": author,
                    "edition": "gita/gita data dump",
                    "language": lang_iso,
                    "script": script,
                    "source_url": f"{BASE}/{kind_label}.json",
                    "license": "Open data (project license)",
                    "license_notes": "Source: gita/gita.",
                    "valid_from": "",
                    "valid_to": "",
                    "text_hash": "",
                })
                for r in recs:
                    text = (r.get("description") or r.get("text") or "").strip()
                    if not text:
                        continue
                    vid = r.get("verse_id")
                    par = verse_pid.get(vid)
                    if not par:
                        continue
                    par_parts = par.split(".")
                    cnum = int(par_parts[-2])
                    vnum = int(par_parts[-1])
                    pid = f"{src_id}.{cnum:02d}.{vnum:03d}"
                    passages_w.write({
                        "passage_id": pid,
                        "source_id": src_id,
                        "canonical_ref": f"BG {cnum}.{vnum} ({kind_label}, {author})",
                        "parent_ref": f"BG {cnum}",
                        "ref_sort": cnum * 1000 + vnum,
                        "language": lang_iso,
                        "script": script,
                        "text": text,
                        "normalized_text": normalize_text(text),
                        "heading": "",
                        "tags_json": json.dumps([kind_label, author, school], ensure_ascii=False),
                        "text_hash": text_hash(text),
                    })
                    link_type = "translation_of" if kind_label == "translation" else "commentary_on"
                    links_w.write({
                        "from_passage_id": pid,
                        "to_passage_id": par,
                        "link_type": link_type,
                        "confidence": 1.0,
                        "note": f"verse-aligned {kind_label} by {author}",
                        "text_hash": text_hash(f"{pid}->{par}:{link_type}"),
                    })

        emit(translations, "translation", default_authority=70, default_label="authoritative_commentary")
        emit(commentaries, "commentary", default_authority=70, default_label="authoritative_commentary")

    finally:
        sources_w.close()
        passages_w.close()
        links_w.close()
        await client.aclose()
    print("[gita] done.")


if __name__ == "__main__":
    asyncio.run(main())
