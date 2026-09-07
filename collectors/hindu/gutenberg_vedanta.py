#!/usr/bin/env python3
"""Vedanta Sutras with Sankara (Advaita) and Ramanuja (Vishishtadvaita) commentaries."""
from __future__ import annotations
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _lib.jsonl_writer import JsonlWriter, text_hash, normalize_text

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw" / "hindu" / "gutenberg"
CORPUS = ROOT / "corpus" / "hindu"

GUTEN_START = re.compile(r"\*\*\*\s*START OF.*?GUTENBERG.*?\*\*\*", re.I | re.S)
GUTEN_END = re.compile(r"\*\*\*\s*END OF.*?GUTENBERG.*?\*\*\*", re.I | re.S)
HEADING = re.compile(r"^(?:CHAPTER|SECTION|BOOK|PADA|ADHYAYA|SUTRA|FIRST|SECOND|THIRD|FOURTH)[\s\.\-A-Z\d]*$", re.M | re.I)


def split_into_chunks(text: str):
    m1 = GUTEN_START.search(text);  text = text[m1.end():] if m1 else text
    m2 = GUTEN_END.search(text);    text = text[:m2.start()] if m2 else text
    parts=[]; cur_label="Preface"; cur_buf=[]; cur_idx=0
    for line in text.split("\n"):
        if HEADING.match(line.strip()):
            body="\n".join(cur_buf).strip()
            if body and len(body)>80:
                parts.append((cur_label, body, cur_idx)); cur_idx+=1
            cur_label = line.strip(); cur_buf=[]
        else:
            cur_buf.append(line)
    body="\n".join(cur_buf).strip()
    if body and len(body)>80:
        parts.append((cur_label, body, cur_idx))
    out=[]
    for label, body, idx in parts:
        if len(body)<=12000:
            out.append((label, body, idx)); continue
        sub = re.split(r"\n\s*\n", body)
        buf=[]; cur_len=0; sub_idx=0
        for p in sub:
            if cur_len+len(p)>12000 and buf:
                out.append((f"{label} (cont.{sub_idx})", "\n\n".join(buf).strip(), idx*100+sub_idx))
                buf=[p]; cur_len=len(p); sub_idx+=1
            else:
                buf.append(p); cur_len+=len(p)
        if buf:
            out.append((f"{label} (cont.{sub_idx})", "\n\n".join(buf).strip(), idx*100+sub_idx))
    return out


BOOKS = [
    ("hindu_16295", "hindu.gutenberg.vedanta-sutras.sankara",  "Vedanta-Sutras with Sankara Bhāṣya (Thibaut)",  90, "commentary", "advaita",         "vedanta"),
    ("hindu_7297",  "hindu.gutenberg.vedanta-sutras.ramanuja", "Vedanta-Sutras with Ramanuja Sri Bhāṣya (Thibaut)", 90, "commentary", "vishishtadvaita", "vedanta"),
]


def main():
    CORPUS.mkdir(parents=True, exist_ok=True)
    sw = JsonlWriter(CORPUS / "sources.jsonl")
    pw = JsonlWriter(CORPUS / "passages.jsonl")
    n_total = 0
    for fid, source_id, title, auth, kind, school, label_kind in BOOKS:
        path = RAW / f"{fid}.txt"
        if not path.exists(): continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        sw.write({
            "source_id": source_id, "religion":"hindu",
            "tradition":"vedanta", "school": school,
            "source_kind": kind, "authority_level": auth,
            "authority_label":"official_core_doctrine",
            "title": title, "subtitle":"Project Gutenberg PD edition",
            "author_body":"Adi Shankara" if "sankara" in source_id else "Ramanuja",
            "edition":f"gutenberg pg{fid.split('_')[-1]}",
            "language":"en","script":"latn",
            "source_url":f"https://www.gutenberg.org/ebooks/{fid.split('_')[-1]}",
            "license":"Public Domain","license_notes":"PG header stripped.",
            "valid_from":"","valid_to":"","text_hash":"",
        })
        chunks = split_into_chunks(raw)
        for lab, body, srt in chunks:
            pid = f"{source_id}.{srt:06d}"
            pw.write({
                "passage_id":pid, "source_id":source_id,
                "canonical_ref": f"{title} :: {lab}"[:200],
                "parent_ref": title[:60], "ref_sort": int(srt),
                "language":"en","script":"latn","text":body,
                "normalized_text": normalize_text(body),
                "heading": lab[:120],
                "tags_json": json.dumps([school, label_kind], ensure_ascii=False),
                "text_hash": text_hash(body),
            })
            n_total+=1
        print(f"  {source_id}: {len(chunks)} chunks")
    sw.close(); pw.close()
    print(f"[vedanta-sutras] passages: {n_total}")


if __name__ == "__main__":
    main()
