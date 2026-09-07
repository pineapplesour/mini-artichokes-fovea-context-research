#!/usr/bin/env python3
"""GRETIL Sanskrit/Pali HTM corpus → passages.

Already cloned (sparse) under raw/hindu/gretil. Walk known dirs, parse each .htm
into shloka-level passages.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _lib.jsonl_writer import JsonlWriter, text_hash, normalize_text

ROOT = Path(__file__).resolve().parents[2]
GRETIL = ROOT / "raw" / "hindu" / "gretil" / "gretil.sub.uni-goettingen.de" / "gretil"
CORPUS = ROOT / "corpus" / "hindu"

# Map dirs → metadata
DIR_META = {
    "1_sanskr/1_veda/1_sam":      {"kind": "scripture", "auth": 100, "label": "canonical_scripture", "tradition": "vaidika", "school": "samhita",  "title_prefix": "Veda Samhita"},
    "1_sanskr/1_veda/2_bra":      {"kind": "scripture", "auth": 100, "label": "canonical_scripture", "tradition": "vaidika", "school": "brahmana",  "title_prefix": "Brahmana"},
    "1_sanskr/1_veda/3_ara":      {"kind": "scripture", "auth": 100, "label": "canonical_scripture", "tradition": "vaidika", "school": "aranyaka",  "title_prefix": "Aranyaka"},
    "1_sanskr/1_veda/4_upa":      {"kind": "scripture", "auth": 100, "label": "canonical_scripture", "tradition": "vaidika", "school": "upanishad", "title_prefix": "Upanishad"},
    "1_sanskr/1_veda/5_vedang":   {"kind": "scripture", "auth": 90,  "label": "official_core_doctrine", "tradition": "vaidika", "school": "vedanga", "title_prefix": "Vedanga"},
    "1_sanskr/2_epic":            {"kind": "scripture", "auth": 100, "label": "canonical_scripture", "tradition": "all", "school": "itihasa",   "title_prefix": "Epic"},
    "1_sanskr/3_purana":          {"kind": "scripture", "auth": 80,  "label": "official_liturgy_ritual", "tradition": "all", "school": "purana", "title_prefix": "Purana"},
}


VERSE_END = re.compile(r"\|\|\s*([A-Za-z][\w_\.]*?)\s*\|\|")


def strip_html(html: str) -> str:
    # Replace br/p with newline
    html = re.sub(r"<\s*br\s*/?\s*>", "\n", html, flags=re.I)
    html = re.sub(r"<\s*/?p\s*[^>]*>", "\n", html, flags=re.I)
    # Replace td/tr with space/newline so tables flatten
    html = re.sub(r"<\s*/?(td|tr|table)[^>]*>", " ", html, flags=re.I)
    # strip remaining tags
    html = re.sub(r"<[^>]+>", "", html)
    # decode entities
    html = (html.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">"))
    # collapse whitespace per line, keep paragraph breaks
    lines = []
    for ln in html.split("\n"):
        ln = re.sub(r"[ \t]+", " ", ln).strip()
        lines.append(ln)
    return "\n".join(lines)


def split_into_verses(text: str, base_ref: str) -> list[tuple[str, str]]:
    """Split text on verse markers like '|| RV_1,1.1 ||' or '|| 1.1 ||'."""
    out = []
    cur_lines = []
    last_end = 0
    pos = 0
    matches = list(VERSE_END.finditer(text))
    if not matches:
        # whole text is one passage
        body = text.strip()
        if body:
            out.append((base_ref + ".all", body))
        return out
    for m in matches:
        body = text[pos:m.start()].strip()
        ref = m.group(1)
        if body:
            out.append((ref, body + " || " + ref + " ||"))
        pos = m.end()
    return out


def parse_file(htm_path: Path) -> tuple[str, list[tuple[str, str]]]:
    raw = htm_path.read_text(encoding="utf-8", errors="replace")
    # Get title
    m = re.search(r"<title>([^<]+)</title>", raw, re.I)
    title = m.group(1).strip() if m else htm_path.stem
    # strip head/style blocks first
    raw = re.sub(r"<style[^>]*>.*?</style>", "", raw, flags=re.S | re.I)
    raw = re.sub(r"<script[^>]*>.*?</script>", "", raw, flags=re.S | re.I)
    text = strip_html(raw)
    # Find body start (after the standard GRETIL header)
    # Marker often "STRUCTURE OF REFERENCES" or last "<hr>"
    parts = text.split("\n")
    # locate first occurrence of '||' verse marker line
    start_i = 0
    for i, ln in enumerate(parts):
        if "||" in ln and re.search(r"\|\|\s*\w", ln):
            # back up a few lines to capture pre-verse content
            start_i = max(0, i - 1)
            break
    body = "\n".join(parts[start_i:])
    base_ref = htm_path.stem
    verses = split_into_verses(body, base_ref)
    return title, verses


def main():
    if not GRETIL.exists():
        raise SystemExit(f"GRETIL not found at {GRETIL}. Run sparse-checkout first.")
    CORPUS.mkdir(parents=True, exist_ok=True)
    sources_w = JsonlWriter(CORPUS / "sources.jsonl")
    passages_w = JsonlWriter(CORPUS / "passages.jsonl")

    n_files = 0
    n_passages = 0
    for sub, meta in DIR_META.items():
        d = GRETIL / sub
        if not d.exists():
            continue
        for htm in sorted(d.rglob("*.htm")):
            n_files += 1
            try:
                title, verses = parse_file(htm)
            except Exception as e:
                print(f"  ! parse {htm.name}: {e}")
                continue
            if not verses:
                continue
            stem = htm.stem
            source_id = f"hindu.gretil.{sub.replace('/','.').replace('1_sanskr.','')}.{stem}"
            sources_w.write({
                "source_id": source_id,
                "religion": "hindu",
                "tradition": meta["tradition"],
                "school": meta["school"],
                "source_kind": meta["kind"],
                "authority_level": meta["auth"],
                "authority_label": meta["label"],
                "title": title,
                "subtitle": meta["title_prefix"],
                "author_body": "",
                "edition": "GRETIL Göttingen e-text",
                "language": "sa",
                "script": "latn",   # IAST diacritical
                "source_url": f"http://gretil.sub.uni-goettingen.de/gretil/{sub}/{htm.name}",
                "license": "GRETIL terms (academic use, non-commercial)",
                "license_notes": "GRETIL — see gretil.sub.uni-goettingen.de/gretil.htm",
                "valid_from": "",
                "valid_to": "",
                "text_hash": "",
            })
            for i, (ref, body) in enumerate(verses):
                pid = f"{source_id}.{i:05d}"
                passages_w.write({
                    "passage_id": pid,
                    "source_id": source_id,
                    "canonical_ref": ref,
                    "parent_ref": stem,
                    "ref_sort": i,
                    "language": "sa",
                    "script": "latn",
                    "text": body,
                    "normalized_text": normalize_text(body),
                    "heading": title if i == 0 else "",
                    "tags_json": json.dumps([meta["school"]], ensure_ascii=False),
                    "text_hash": text_hash(body),
                })
                n_passages += 1
    sources_w.close()
    passages_w.close()
    print(f"[gretil] files: {n_files}, passages: {n_passages}")


if __name__ == "__main__":
    main()
