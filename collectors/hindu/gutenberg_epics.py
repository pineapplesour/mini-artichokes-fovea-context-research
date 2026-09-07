#!/usr/bin/env python3
"""Hindu epics from Project Gutenberg (PD).

KMG Mahabharata (multiple parts), Valmiki Ramayana (Griffith verse), Vishnu Purana (Wilson),
Upanishads (Müller), Hindu Literature anthology (Kalidasa, Valmiki, Toru Dutt).

Pre-downloaded txts in raw/hindu/gutenberg/. Strip Gutenberg headers, split by SECTION/CHAPTER.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _lib.jsonl_writer import JsonlWriter, text_hash, normalize_text

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw" / "hindu" / "gutenberg"
CORPUS = ROOT / "corpus" / "hindu"

GUTEN_START = re.compile(r"\*\*\*\s*START OF.*?GUTENBERG.*?\*\*\*", re.I | re.S)
GUTEN_END = re.compile(r"\*\*\*\s*END OF.*?GUTENBERG.*?\*\*\*", re.I | re.S)

# (file_id, source_id, title, authority, kind, school)
BOOKS = [
    ("mb_15474", "hindu.gutenberg.kmg.mb.vol1",  "Mahabharata KMG Vol 1 (Adi Parva)",       100, "scripture", "itihasa"),
    ("mb_15475", "hindu.gutenberg.kmg.mb.vol2",  "Mahabharata KMG Vol 2 (Sabha–Vana Parvas)", 100, "scripture", "itihasa"),
    ("mb_15476", "hindu.gutenberg.kmg.mb.vol3",  "Mahabharata KMG Vol 3 (Vana–Drona)",      100, "scripture", "itihasa"),
    ("mb_15477", "hindu.gutenberg.kmg.mb.vol4",  "Mahabharata KMG Vol 4 (Drona–Karna)",     100, "scripture", "itihasa"),
    ("mb_7864",  "hindu.gutenberg.kmg.mb.adi",   "Mahabharata KMG Adi Parva (KM Ganguli orig.)", 100, "scripture", "itihasa"),
    ("mb_11894", "hindu.gutenberg.kmg.mb.book1", "Mahabharata KMG (Pratapa Chandra Roy ed.) part",100, "scripture", "itihasa"),
    ("mb_12058", "hindu.gutenberg.kmg.mb.book2", "Mahabharata KMG (Pratapa Chandra Roy ed.) part",100, "scripture", "itihasa"),
    ("mb_12333", "hindu.gutenberg.kmg.mb.book3", "Mahabharata KMG (Pratapa Chandra Roy ed.) part",100, "scripture", "itihasa"),
    ("mb_7965",  "hindu.gutenberg.kmg.mb.book7", "Mahabharata KMG (Pratapa Chandra Roy ed.) part",100, "scripture", "itihasa"),
    ("hindu_24869","hindu.gutenberg.ramayana.griffith", "Ramayana of Valmiki (Griffith verse, 1870-74)", 100, "scripture", "itihasa"),
    ("hindu_66208","hindu.gutenberg.vishnu-purana.wilson", "Vishnu Purana (Wilson translation)",80, "scripture", "purana"),
    ("hindu_3283", "hindu.gutenberg.upanishads.muller",  "Upanishads (Max Müller SBE Vol 1, 15)", 100, "scripture", "upanishad"),
    ("hindu_13268","hindu.gutenberg.hindu-literature.anthology","Hindu Literature anthology (Kalidasa, Valmiki, Toru Dutt)", 80, "scripture", "literature"),
]


def split_into_chunks(text: str, source_id: str) -> list[tuple[str, str, int]]:
    """Split body text into (section_label, body, ref_sort) chunks.

    Heuristic: split on "SECTION", "CHAPTER", "BOOK", or numbered roman headings on their own line.
    Each chunk capped at 12k chars.
    """
    # Cut Gutenberg boilerplate
    m1 = GUTEN_START.search(text)
    if m1:
        text = text[m1.end():]
    m2 = GUTEN_END.search(text)
    if m2:
        text = text[:m2.start()]

    # Split on standalone heading lines
    HEADING = re.compile(
        r"^(?:SECTION|CHAPTER|BOOK|CANTO|PARVA|HYMN|MANDALA)\s+[IVXLCDM\d][\w\.\-]*[A-Z\.\s]*?$",
        re.M | re.I,
    )
    parts = []
    cur_label = "Preface"
    cur_buf = []
    cur_idx = 0
    for line in text.split("\n"):
        if HEADING.match(line.strip()):
            body = "\n".join(cur_buf).strip()
            if body and len(body) > 80:
                parts.append((cur_label, body, cur_idx))
                cur_idx += 1
            cur_label = line.strip()
            cur_buf = []
        else:
            cur_buf.append(line)
    body = "\n".join(cur_buf).strip()
    if body and len(body) > 80:
        parts.append((cur_label, body, cur_idx))

    # Cap chunks to ~12k chars; split larger ones by paragraph blank lines
    out = []
    for label, body, idx in parts:
        if len(body) <= 12000:
            out.append((label, body, idx))
            continue
        sub_paras = re.split(r"\n\s*\n", body)
        buf = []
        cur_len = 0
        sub_idx = 0
        for p in sub_paras:
            if cur_len + len(p) > 12000 and buf:
                out.append((f"{label} (cont.{sub_idx})", "\n\n".join(buf).strip(), idx + sub_idx * 0.001))
                buf = [p]; cur_len = len(p); sub_idx += 1
            else:
                buf.append(p); cur_len += len(p)
        if buf:
            out.append((f"{label} (cont.{sub_idx})", "\n\n".join(buf).strip(), idx + sub_idx * 0.001))
    return [(l, b, int(i*1000)) for l, b, i in out]


def main():
    CORPUS.mkdir(parents=True, exist_ok=True)
    sources_w = JsonlWriter(CORPUS / "sources.jsonl")
    passages_w = JsonlWriter(CORPUS / "passages.jsonl")

    n_total = 0
    for fid, source_id, title, auth, kind, school in BOOKS:
        path = RAW / f"{fid}.txt"
        if not path.exists():
            print(f"  skip {fid}: not found")
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        sources_w.write({
            "source_id": source_id,
            "religion": "hindu",
            "tradition": "all",
            "school": school,
            "source_kind": kind,
            "authority_level": auth,
            "authority_label": "canonical_scripture" if auth >= 100 else "official_liturgy_ritual",
            "title": title,
            "subtitle": "Project Gutenberg PD edition",
            "author_body": "Vyasa (trad.)" if "kmg" in source_id else ("Valmiki (trad.)" if "ramayana" in source_id else ""),
            "edition": f"gutenberg pg{fid.split('_')[-1]}",
            "language": "en",
            "script": "latn",
            "source_url": f"https://www.gutenberg.org/ebooks/{fid.split('_')[-1]}",
            "license": "Public Domain (Project Gutenberg)",
            "license_notes": "PG header/footer stripped.",
            "valid_from": "",
            "valid_to": "",
            "text_hash": "",
        })
        chunks = split_into_chunks(raw, source_id)
        for label, body, srt in chunks:
            pid = f"{source_id}.{srt:06d}"
            passages_w.write({
                "passage_id": pid,
                "source_id": source_id,
                "canonical_ref": f"{title} :: {label}"[:200],
                "parent_ref": title[:60],
                "ref_sort": srt,
                "language": "en",
                "script": "latn",
                "text": body,
                "normalized_text": normalize_text(body),
                "heading": label[:120],
                "tags_json": json.dumps([school, "gutenberg"], ensure_ascii=False),
                "text_hash": text_hash(body),
            })
            n_total += 1
        print(f"  {source_id}: {len(chunks)} chunks")
    sources_w.close()
    passages_w.close()
    print(f"[gutenberg] passages: {n_total}")


if __name__ == "__main__":
    main()
