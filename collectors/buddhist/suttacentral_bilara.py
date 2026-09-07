#!/usr/bin/env python3
"""SuttaCentral bilara-data: Pali Canon (Tipitaka) + aligned translations.

Repo cloned at raw/buddhist/bilara-data. Each sutta has:
  root/<lang>/ms/<basket>/<nikaya>/<sutta_uid>_root-<lang>-ms.json
  translation/<lang>/<author>/<basket>/<nikaya>/<sutta_uid>_translation-<lang>-<author>.json

Each JSON is keyed by segment id (e.g., "dn1:1.1.1") with text values.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _lib.jsonl_writer import JsonlWriter, text_hash, normalize_text

ROOT = Path(__file__).resolve().parents[2]
BILARA = ROOT / "raw" / "buddhist" / "bilara-data"
CORPUS = ROOT / "corpus" / "buddhist"

LANG_MAP = {  # bilara dir -> ISO
    "pli": ("pi", "latn"),       # Pali (romanized)
    "lzh": ("lzh", "hant"),      # Classical Chinese (Mahayana parallels)
    "san": ("sa", "deva"),       # Sanskrit
    "pra": ("pra", "deva"),      # Prakrit
    "en":  ("en", "latn"),
    "de":  ("de", "latn"),
    "fr":  ("fr", "latn"),
    "es":  ("es", "latn"),
    "ja":  ("ja", "jpan"),
    "ko":  ("ko", "hang"),
    "zh":  ("zh", "hans"),
    "vi":  ("vi", "latn"),
    "id":  ("id", "latn"),
    "hi":  ("hi", "deva"),
    "th":  ("th", "thai"),
    "my":  ("my", "mymr"),
    "si":  ("si", "sinh"),
    "ru":  ("ru", "cyrl"),
}

BASKET_MAP = {
    "vinaya": ("vinaya", "official_liturgy_ritual"),
    "sutta":  ("sutta",  "canonical_scripture"),
    "abhidhamma": ("abhidhamma", "canonical_scripture"),
}

# Selected (high-priority) translation authors per language
PRIMARY_TRANSLATORS = {
    "en": {"sujato", "brahmali", "anandajoti", "soma", "thanissaro"},
    # other langs: take all
}


def basket_from_path(p: Path) -> str:
    parts = p.parts
    for b in ("vinaya", "sutta", "abhidhamma"):
        if b in parts:
            return b
    return "misc"


def parse_uid_from_filename(p: Path) -> str | None:
    """e.g. 'dn10_root-pli-ms.json' -> 'dn10', 'mn10_translation-en-sujato.json' -> 'mn10'."""
    m = re.match(r"([a-z0-9.\-]+?)_(root|translation|comment|variant|reference|html)-", p.name)
    return m.group(1) if m else None


def normalize_segments(d: dict) -> list[tuple[str, str]]:
    """Yield (segment_id, text) pairs in order."""
    if not isinstance(d, dict):
        return []
    out = []
    for k, v in d.items():
        if isinstance(v, str) and v.strip():
            out.append((k, v.strip()))
    return out


async def main():
    if not BILARA.exists():
        raise SystemExit(f"bilara-data not found at {BILARA}. Run: git clone --depth 1 -b published https://github.com/suttacentral/bilara-data.git {BILARA}")

    CORPUS.mkdir(parents=True, exist_ok=True)
    sources_w = JsonlWriter(CORPUS / "sources.jsonl")
    passages_w = JsonlWriter(CORPUS / "passages.jsonl")
    links_w = JsonlWriter(CORPUS / "links.jsonl")

    # Track sutta uid → primary (root pali) passage_ids by segment id
    pli_seg_pid: dict[tuple[str, str], str] = {}

    # Phase 1: roots (canonical_scripture)
    print("[bilara] Phase 1: roots ...", flush=True)
    n_root_sources = 0
    n_root_passages = 0
    for root_lang_dir in sorted((BILARA / "root").iterdir()):
        if not root_lang_dir.is_dir():
            continue
        lang_key = root_lang_dir.name
        lang, script = LANG_MAP.get(lang_key, (lang_key, ""))
        for jf in root_lang_dir.rglob("*.json"):
            uid = parse_uid_from_filename(jf)
            if not uid:
                continue
            basket = basket_from_path(jf)
            kind, label = BASKET_MAP.get(basket, ("misc", "canonical_scripture"))
            try:
                d = json.loads(jf.read_text(encoding="utf-8"))
            except Exception:
                continue
            segs = normalize_segments(d)
            if not segs:
                continue
            source_id = f"bud.thera.bilara.root.{lang_key}.{uid}"
            tradition = "theravada" if lang_key == "pli" else ("mahayana" if lang_key in ("lzh", "san") else "common")
            sources_w.write({
                "source_id": source_id,
                "religion": "buddhist",
                "tradition": tradition,
                "school": "",
                "source_kind": kind,
                "authority_level": 100,
                "authority_label": "canonical_scripture",
                "title": f"SuttaCentral {uid} ({basket}, {lang_key} root)",
                "subtitle": "",
                "author_body": "",
                "edition": "bilara-data published branch",
                "language": lang,
                "script": script,
                "source_url": f"https://suttacentral.net/{uid}/{lang_key}",
                "license": "CC0" if lang_key == "pli" else "CC0/CC-BY",
                "license_notes": "Mahasangiti edition (pli-ms) is CC0; other roots vary.",
                "valid_from": "",
                "valid_to": "",
                "text_hash": "",
            })
            n_root_sources += 1
            for i, (seg_id, text) in enumerate(segs):
                pid = f"{source_id}.{i:05d}"
                passages_w.write({
                    "passage_id": pid,
                    "source_id": source_id,
                    "canonical_ref": f"{seg_id}",
                    "parent_ref": uid,
                    "ref_sort": i,
                    "language": lang,
                    "script": script,
                    "text": text,
                    "normalized_text": normalize_text(text),
                    "heading": "" if i else uid,
                    "tags_json": json.dumps([basket, "root"], ensure_ascii=False),
                    "text_hash": text_hash(text),
                })
                if lang_key == "pli":
                    pli_seg_pid[(uid, seg_id)] = pid
                n_root_passages += 1

    print(f"  root sources: {n_root_sources}, passages: {n_root_passages}")

    # Phase 2: translations
    print("[bilara] Phase 2: translations ...", flush=True)
    n_tr_sources = 0
    n_tr_passages = 0
    n_links = 0
    for tr_lang_dir in sorted((BILARA / "translation").iterdir()):
        if not tr_lang_dir.is_dir():
            continue
        lang_key = tr_lang_dir.name
        lang, script = LANG_MAP.get(lang_key, (lang_key, ""))
        primary_authors = PRIMARY_TRANSLATORS.get(lang_key)
        for author_dir in sorted(tr_lang_dir.iterdir()):
            if not author_dir.is_dir():
                continue
            author = author_dir.name
            if primary_authors and author not in primary_authors:
                continue
            for jf in author_dir.rglob("*.json"):
                uid = parse_uid_from_filename(jf)
                if not uid:
                    continue
                basket = basket_from_path(jf)
                kind, label = BASKET_MAP.get(basket, ("misc", "canonical_scripture"))
                try:
                    d = json.loads(jf.read_text(encoding="utf-8"))
                except Exception:
                    continue
                segs = normalize_segments(d)
                if not segs:
                    continue
                source_id = f"bud.thera.bilara.tr.{lang_key}.{author}.{uid}"
                sources_w.write({
                    "source_id": source_id,
                    "religion": "buddhist",
                    "tradition": "theravada" if uid.startswith(("dn","mn","sn","an","kn","pli")) else "common",
                    "school": "",
                    "source_kind": "translation",
                    "authority_level": 80,
                    "authority_label": "official_liturgy_ritual",
                    "title": f"SuttaCentral {uid} translation ({lang_key}, {author})",
                    "subtitle": "",
                    "author_body": author,
                    "edition": f"bilara translation/{lang_key}/{author}",
                    "language": lang,
                    "script": script,
                    "source_url": f"https://suttacentral.net/{uid}/{lang_key}/{author}",
                    "license": "CC-BY-NC",
                    "license_notes": "SuttaCentral translations: see suttacentral.net/licensing.",
                    "valid_from": "",
                    "valid_to": "",
                    "text_hash": "",
                })
                n_tr_sources += 1
                for i, (seg_id, text) in enumerate(segs):
                    pid = f"{source_id}.{i:05d}"
                    passages_w.write({
                        "passage_id": pid,
                        "source_id": source_id,
                        "canonical_ref": f"{seg_id}",
                        "parent_ref": uid,
                        "ref_sort": i,
                        "language": lang,
                        "script": script,
                        "text": text,
                        "normalized_text": normalize_text(text),
                        "heading": "" if i else uid,
                        "tags_json": json.dumps([basket, "translation", author], ensure_ascii=False),
                        "text_hash": text_hash(text),
                    })
                    n_tr_passages += 1
                    par = pli_seg_pid.get((uid, seg_id))
                    if par:
                        if links_w.write({
                            "from_passage_id": pid,
                            "to_passage_id": par,
                            "link_type": "translation_of",
                            "confidence": 1.0,
                            "note": f"segment-aligned via bilara",
                            "text_hash": text_hash(f"{pid}->{par}:translation_of"),
                        }):
                            n_links += 1

    print(f"  tr sources: {n_tr_sources}, passages: {n_tr_passages}, links: {n_links}")
    sources_w.close()
    passages_w.close()
    links_w.close()
    print("[bilara] done.")


if __name__ == "__main__":
    asyncio.run(main())
