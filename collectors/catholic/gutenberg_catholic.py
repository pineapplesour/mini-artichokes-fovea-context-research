#!/usr/bin/env python3
"""Catholic PD classics from Gutenberg.

- Aquinas Summa Theologica (4 volumes, English transl.)
- Augustine: Confessions, City of God Vol I/II
- Imitation of Christ (Thomas à Kempis)
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _lib.jsonl_writer import JsonlWriter, text_hash, normalize_text

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw" / "christian" / "catholic" / "gutenberg"
CORPUS = ROOT / "corpus" / "christian"

GUTEN_START = re.compile(r"\*\*\*\s*START OF.*?GUTENBERG.*?\*\*\*", re.I | re.S)
GUTEN_END = re.compile(r"\*\*\*\s*END OF.*?GUTENBERG.*?\*\*\*", re.I | re.S)
HEADING = re.compile(
    r"^(?:QUESTION|ARTICLE|CHAPTER|BOOK|PART|TREATISE|FIRST|SECOND|THIRD|FOURTH|SECTION|PROLOGUE)\b[\s\.\-A-Z\d:]*$",
    re.M | re.I,
)


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
    ("cath_17611", "christian.catholic.aquinas.summa.gutenberg.pt1",   "Summa Theologica Part I (Prima Pars) — English transl.",  70, "commentary", "thomism", "summa"),
    ("cath_17897", "christian.catholic.aquinas.summa.gutenberg.pt12",  "Summa Theologica Part I-II (Prima Secundae) — English",   70, "commentary", "thomism", "summa"),
    ("cath_18755", "christian.catholic.aquinas.summa.gutenberg.pt22",  "Summa Theologica Part II-II (Secunda Secundae) — English",70, "commentary", "thomism", "summa"),
    ("cath_19950", "christian.catholic.aquinas.summa.gutenberg.pt3",   "Summa Theologica Part III (Tertia Pars) — English",       70, "commentary", "thomism", "summa"),
    ("cath_3296",  "christian.catholic.augustine.confessions.gutenberg","Augustine — Confessions",                                70, "commentary", "patristic","augustine"),
    ("cath_45304", "christian.catholic.augustine.civitate-dei.vol1.gutenberg","Augustine — City of God Vol I",                    70, "commentary", "patristic","augustine"),
    ("cath_45305", "christian.catholic.augustine.civitate-dei.vol2.gutenberg","Augustine — City of God Vol II",                   70, "commentary", "patristic","augustine"),
    ("cath_1653",  "christian.catholic.kempis.imitation.gutenberg",    "Imitation of Christ (Thomas à Kempis)",                  60, "commentary", "spirituality","kempis"),
]


def main():
    CORPUS.mkdir(parents=True, exist_ok=True)
    sw = JsonlWriter(CORPUS / "sources.jsonl")
    pw = JsonlWriter(CORPUS / "passages.jsonl")
    n_total = 0
    for fid, source_id, title, auth, kind, school, label_kind in BOOKS:
        path = RAW / f"{fid}.txt"
        if not path.exists():
            print(f"  skip {fid}: not found")
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        sw.write({
            "source_id": source_id, "religion": "christian",
            "tradition": "catholic", "school": school,
            "source_kind": kind, "authority_level": auth,
            "authority_label": "authoritative_commentary",
            "title": title, "subtitle": "Project Gutenberg PD edition",
            "author_body": "Thomas Aquinas" if "summa" in source_id else "Augustine of Hippo" if "augustine" in source_id else "Thomas à Kempis" if "kempis" in source_id else "",
            "edition": f"gutenberg pg{fid.split('_')[-1]}",
            "language": "en", "script": "latn",
            "source_url": f"https://www.gutenberg.org/ebooks/{fid.split('_')[-1]}",
            "license": "Public Domain (Project Gutenberg)",
            "license_notes": "PG header/footer stripped.",
            "valid_from": "", "valid_to": "", "text_hash": "",
        })
        chunks = split_into_chunks(raw)
        for lab, body, srt in chunks:
            pid = f"{source_id}.{srt:06d}"
            pw.write({
                "passage_id": pid, "source_id": source_id,
                "canonical_ref": f"{title} :: {lab}"[:200],
                "parent_ref": title[:60], "ref_sort": int(srt),
                "language": "en", "script": "latn",
                "text": body, "normalized_text": normalize_text(body),
                "heading": lab[:120],
                "tags_json": json.dumps([school, label_kind, "gutenberg"], ensure_ascii=False),
                "text_hash": text_hash(body),
            })
            n_total += 1
        print(f"  {source_id}: {len(chunks)} chunks")
    sw.close(); pw.close()
    print(f"[christian-catholic-gutenberg] passages: {n_total}")


if __name__ == "__main__":
    main()
