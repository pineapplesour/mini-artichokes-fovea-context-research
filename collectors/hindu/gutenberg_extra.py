#!/usr/bin/env python3
"""Additional Hindu Gutenberg PD: Bhagavad Gita Edwin Arnold, Bhagavata Study, Yoga Sutras, Jnana Yoga."""
from __future__ import annotations
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _lib.jsonl_writer import JsonlWriter, text_hash, normalize_text
sys.path.insert(0, str(Path(__file__).resolve().parent / ""))
from gutenberg_epics import split_into_chunks

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw" / "hindu" / "gutenberg"
CORPUS = ROOT / "corpus" / "hindu"

BOOKS = [
    ("hindu_2388",  "hindu.gutenberg.gita.arnold",          "Bhagavad-Gita (Edwin Arnold — Song Celestial)",  90, "scripture",  "all", "gita"),
    ("hindu_39442", "hindu.gutenberg.bhagavata-study",      "Study of the Bhagavata Purana (esoteric)",        70, "commentary", "all", "purana"),
    ("hindu_2526",  "hindu.gutenberg.yoga-sutras.patanjali","Yoga Sutras of Patanjali (Spiritual Man)",        90, "scripture",  "yoga","yoga"),
    ("hindu_72368", "hindu.gutenberg.jnana-yoga.vivekananda","Jnana Yoga Part II — Vivekananda Lectures",      60, "commentary", "advaita","modern"),
]


def main():
    CORPUS.mkdir(parents=True, exist_ok=True)
    sw = JsonlWriter(CORPUS / "sources.jsonl")
    pw = JsonlWriter(CORPUS / "passages.jsonl")
    n=0
    for fid, source_id, title, auth, kind, school, label in BOOKS:
        path = RAW / f"{fid}.txt"
        if not path.exists(): continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        sw.write({
            "source_id": source_id, "religion":"hindu",
            "tradition":"all", "school": school,
            "source_kind": kind, "authority_level": auth,
            "authority_label": "canonical_scripture" if auth >= 100 else (
                "official_core_doctrine" if auth >= 90 else "authoritative_commentary"),
            "title": title,
            "subtitle":"Project Gutenberg PD edition",
            "author_body": "", "edition":f"gutenberg pg{fid.split('_')[-1]}",
            "language":"en","script":"latn",
            "source_url":f"https://www.gutenberg.org/ebooks/{fid.split('_')[-1]}",
            "license":"Public Domain",
            "license_notes":"PG header stripped.","valid_from":"","valid_to":"","text_hash":"",
        })
        for lab, body, srt in split_into_chunks(raw, source_id):
            pid = f"{source_id}.{srt:06d}"
            pw.write({
                "passage_id":pid, "source_id": source_id,
                "canonical_ref": f"{title} :: {lab}"[:200],
                "parent_ref": title[:60],
                "ref_sort": int(srt),
                "language":"en","script":"latn","text":body,
                "normalized_text": normalize_text(body),
                "heading": lab[:120],
                "tags_json": json.dumps([school, label, "gutenberg"], ensure_ascii=False),
                "text_hash": text_hash(body),
            })
            n+=1
        print(f"  {source_id}: passages={n}")
    sw.close(); pw.close()
    print(f"[hindu-gutenberg-extra] passages: {n}")


if __name__ == "__main__":
    main()
