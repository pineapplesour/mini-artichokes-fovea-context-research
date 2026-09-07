#!/usr/bin/env python3
"""Buddhist canonical/classical English texts from Gutenberg (PD)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _lib.jsonl_writer import JsonlWriter, text_hash, normalize_text

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw" / "buddhist" / "gutenberg"
CORPUS = ROOT / "corpus" / "buddhist"

GUTEN_START = re.compile(r"\*\*\*\s*START OF.*?GUTENBERG.*?\*\*\*", re.I | re.S)
GUTEN_END = re.compile(r"\*\*\*\s*END OF.*?GUTENBERG.*?\*\*\*", re.I | re.S)
HEADING = re.compile(
    r"^(?:SECTION|CHAPTER|BOOK|CANTO|SUTRA|SUTTA|VERSE|PSALM|PART)\s+[IVXLCDM\d][\w\.\-\s]*?$",
    re.M | re.I,
)


def split_into_chunks(text: str):
    m1 = GUTEN_START.search(text)
    if m1:
        text = text[m1.end():]
    m2 = GUTEN_END.search(text)
    if m2:
        text = text[:m2.start()]
    parts = []
    cur_label = "Preface"; cur_buf = []; cur_idx = 0
    for line in text.split("\n"):
        if HEADING.match(line.strip()):
            body = "\n".join(cur_buf).strip()
            if body and len(body) > 80:
                parts.append((cur_label, body, cur_idx)); cur_idx += 1
            cur_label = line.strip(); cur_buf = []
        else:
            cur_buf.append(line)
    body = "\n".join(cur_buf).strip()
    if body and len(body) > 80:
        parts.append((cur_label, body, cur_idx))
    out = []
    for label, body, idx in parts:
        if len(body) <= 12000:
            out.append((label, body, idx))
            continue
        sub = re.split(r"\n\s*\n", body)
        buf=[]; cur_len=0; sub_idx=0
        for p in sub:
            if cur_len + len(p) > 12000 and buf:
                out.append((f"{label} (cont.{sub_idx})", "\n\n".join(buf).strip(), idx*100 + sub_idx))
                buf=[p]; cur_len=len(p); sub_idx+=1
            else:
                buf.append(p); cur_len+=len(p)
        if buf:
            out.append((f"{label} (cont.{sub_idx})", "\n\n".join(buf).strip(), idx*100 + sub_idx))
    return out


BOOKS = [
    ("buddhist_2017",  "bud.thera.gutenberg.dhammapada",  "Dhammapada (Müller, SBE Vol 10)",                100, "scripture", "theravada", "dhammapada"),
    ("buddhist_51880", "bud.thera.gutenberg.jataka.vol1", "Buddhist Birth Stories (Jataka Tales) Vol 1 (Rhys Davids)", 90,  "scripture", "theravada", "jataka"),
    ("buddhist_46984", "bud.thera.gutenberg.gatakamala",  "Gatakamala (Garland of Birth-Stories, Speyer)", 80,  "commentary", "theravada", "gatakamala"),
    ("buddhist_12894", "bud.gutenberg.sbe.compilation",   "Sacred Books of the East — compilation",        70,  "commentary", "common",    "sbe"),
    ("buddhist_17956", "bud.gutenberg.misc.short",        "Short Buddhist text (PG#17956)",                70,  "scripture", "common",    "misc"),
]


def main():
    CORPUS.mkdir(parents=True, exist_ok=True)
    sources_w = JsonlWriter(CORPUS / "sources.jsonl")
    passages_w = JsonlWriter(CORPUS / "passages.jsonl")
    n_total = 0
    for fid, source_id, title, auth, kind, tradition, school in BOOKS:
        path = RAW / f"{fid}.txt"
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        sources_w.write({
            "source_id": source_id, "religion": "buddhist",
            "tradition": tradition, "school": school,
            "source_kind": kind, "authority_level": auth,
            "authority_label": "canonical_scripture" if auth >= 100 else (
                "official_core_doctrine" if auth >= 90 else "authoritative_commentary"),
            "title": title, "subtitle": "Project Gutenberg PD edition",
            "author_body": "", "edition": f"gutenberg pg{fid.split('_')[-1]}",
            "language": "en", "script": "latn",
            "source_url": f"https://www.gutenberg.org/ebooks/{fid.split('_')[-1]}",
            "license": "Public Domain (Project Gutenberg)",
            "license_notes": "PG header/footer stripped.",
            "valid_from": "", "valid_to": "", "text_hash": "",
        })
        chunks = split_into_chunks(raw)
        for label, body, srt in chunks:
            pid = f"{source_id}.{srt:06d}"
            passages_w.write({
                "passage_id": pid, "source_id": source_id,
                "canonical_ref": f"{title} :: {label}"[:200],
                "parent_ref": title[:60], "ref_sort": int(srt),
                "language": "en", "script": "latn",
                "text": body, "normalized_text": normalize_text(body),
                "heading": label[:120],
                "tags_json": json.dumps([school, "gutenberg"], ensure_ascii=False),
                "text_hash": text_hash(body),
            })
            n_total += 1
        print(f"  {source_id}: {len(chunks)} chunks")
    sources_w.close(); passages_w.close()
    print(f"[bud-gutenberg] passages: {n_total}")


if __name__ == "__main__":
    main()
