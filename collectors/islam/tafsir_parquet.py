#!/usr/bin/env python3
"""Tafsir from M-AI-C HuggingFace parquet dumps (no API needed).

Three high-quality English tafsirs:
  - en-tafsir-ibn-kathir (Ibn Kathir abridged)
  - en-tafsir-maarif (Mufti Shafi)
  - en-tafsir-mokhtasar (Tafsir al-Mukhtasar)
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
import pyarrow.parquet as pq
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _lib.jsonl_writer import JsonlWriter, text_hash, normalize_text

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw" / "islam" / "tafsir-dump"
CORPUS = ROOT / "corpus" / "islam"

DATASETS = [
    ("en-tafsir-ibn-kathir.parquet",
     "islam.tafsir.ibn-kathir.en.dump",
     "Tafsir Ibn Kathir (English Abridged) — M-AI-C HF dump",
     "en-tafsir-ibn-kathir-text", "ibn-kathir", 75),
    ("en-tafsir-maarif.parquet",
     "islam.tafsir.maarif.en.dump",
     "Maarif al-Quran (Mufti Shafi, English) — M-AI-C HF dump",
     "en-tafsir-maarif-text", "maarif", 70),
    ("en-tafsir-mokhtasar.parquet",
     "islam.tafsir.mokhtasar.en.dump",
     "Tafsir al-Mukhtasar (English) — M-AI-C HF dump",
     "en-tafsir-mokhtasar-text", "mokhtasar", 75),
]


def main():
    CORPUS.mkdir(parents=True, exist_ok=True)
    sw = JsonlWriter(CORPUS / "sources.jsonl")
    pw = JsonlWriter(CORPUS / "passages.jsonl")
    lw = JsonlWriter(CORPUS / "links.jsonl")
    n_total = 0
    for fname, source_id, title, text_col, school, auth in DATASETS:
        path = RAW / fname
        if not path.exists():
            print(f"  skip {fname}"); continue
        sw.write({
            "source_id": source_id, "religion": "islam",
            "tradition": "sunni", "school": school,
            "source_kind": "commentary", "authority_level": auth,
            "authority_label": "authoritative_commentary",
            "title": title, "subtitle": "M-AI-C HuggingFace dump",
            "author_body": "", "edition": fname.replace(".parquet",""),
            "language": "en", "script": "latn",
            "source_url": f"https://huggingface.co/datasets/M-AI-C/{fname.replace('.parquet','')}",
            "license":"Open data (per HF dataset card)",
            "license_notes":"Tafsir text from public domain or fair-use abridged transcripts.",
            "valid_from":"","valid_to":"","text_hash":"",
        })
        df = pq.read_table(str(path)).to_pandas()
        n = 0
        for _, row in df.iterrows():
            try:
                s = int(row.get("sorah") or row.get("surah") or 0)
                v = int(row.get("ayah") or 0)
            except Exception:
                continue
            txt = (row.get(text_col) or "").strip()
            if not txt or s == 0 or v == 0:
                continue
            cleaned = re.sub(r"\s+", " ", txt).strip()[:8000]
            pid = f"{source_id}.{s:03d}.{v:03d}"
            pw.write({
                "passage_id": pid, "source_id": source_id,
                "canonical_ref": f"{title} on Quran {s}:{v}",
                "parent_ref": f"Quran {s}",
                "ref_sort": s*10000+v,
                "language": "en", "script": "latn",
                "text": cleaned, "normalized_text": normalize_text(cleaned),
                "heading":"", "tags_json":'["tafsir"]',
                "text_hash": text_hash(cleaned),
            })
            arab = f"islam.quran.fawaz.uthmani-haf.{s:03d}.{v:03d}"
            lw.write({
                "from_passage_id": pid, "to_passage_id": arab,
                "link_type":"commentary_on", "confidence":1.0,
                "note":"tafsir on this ayah",
                "text_hash": text_hash(f"{pid}->{arab}:commentary_on"),
            })
            n += 1
        print(f"  {source_id}: {n} passages")
        n_total += n
    sw.close(); pw.close(); lw.close()
    print(f"[tafsir-parquet] total: {n_total}")


if __name__ == "__main__":
    main()
