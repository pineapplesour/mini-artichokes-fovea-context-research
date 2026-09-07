#!/usr/bin/env python3
"""sa.wikisource (Sanskrit Wikisource) full dump → passages.

Stream-parses the MediaWiki XML dump. Filters to ns=0 (main content) only.
Each <page> becomes one source. Long pages get split per heading.
"""
from __future__ import annotations

import json
import re
import sys
import xml.sax
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _lib.jsonl_writer import JsonlWriter, text_hash, normalize_text

ROOT = Path(__file__).resolve().parents[2]
DUMP = ROOT / "raw" / "hindu" / "wikisource" / "sa.xml"
CORPUS = ROOT / "corpus" / "hindu"

NS = "http://www.mediawiki.org/xml/export-0.11/"


# Strip wikitext to plain text (best effort)
RE_REF = re.compile(r"<ref[^>]*>.*?</ref>", re.S | re.I)
RE_REF_SELF = re.compile(r"<ref[^/]*/>", re.I)
RE_TEMPLATE = re.compile(r"\{\{[^}]+\}\}")
RE_LINK_PIPE = re.compile(r"\[\[[^\]\|]+\|([^\]]+)\]\]")
RE_LINK = re.compile(r"\[\[([^\]\|]+)\]\]")
RE_BOLD_IT = re.compile(r"'{2,5}")
RE_HTML = re.compile(r"<[^>]+>")
RE_HEADING = re.compile(r"^(=+)\s*(.*?)\s*\1$", re.M)
RE_TABLE = re.compile(r"\{\|.*?\|\}", re.S)


def clean_wikitext(t: str) -> str:
    t = RE_REF.sub("", t)
    t = RE_REF_SELF.sub("", t)
    t = RE_TABLE.sub("", t)
    # Templates - many cycles
    for _ in range(3):
        t2 = RE_TEMPLATE.sub("", t)
        if t2 == t:
            break
        t = t2
    t = RE_LINK_PIPE.sub(r"\1", t)
    t = RE_LINK.sub(r"\1", t)
    t = RE_BOLD_IT.sub("", t)
    t = RE_HTML.sub("", t)
    # collapse whitespace
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def split_by_headings(text: str, base_title: str) -> list[tuple[str, str]]:
    """Split a wiki article into (heading, body) chunks via == headings."""
    if not RE_HEADING.search(text):
        return [(base_title, text)]
    parts = []
    cur_h = base_title
    cur_buf = []
    for line in text.split("\n"):
        m = re.match(r"^(=+)\s*(.*?)\s*\1\s*$", line)
        if m:
            if cur_buf:
                body = "\n".join(cur_buf).strip()
                if body:
                    parts.append((cur_h, body))
            cur_h = m.group(2).strip()
            cur_buf = []
        else:
            cur_buf.append(line)
    if cur_buf:
        body = "\n".join(cur_buf).strip()
        if body:
            parts.append((cur_h, body))
    return parts


# Heuristics: classify by title
RELIGIOUS_KEYWORDS = [
    "उपनिषद्", "वेद", "रामायण", "महाभारत", "गीता", "पुराण",
    "ब्राह्मण", "आरण्यक", "संहिता", "धर्म", "स्मृति", "तन्त्र",
    "श्रीमद्", "भगवद्", "मनु", "योग", "ब्रह्म", "शिव", "विष्णु",
    "देवी", "स्तोत्र",
]

CATEGORY_FROM_TITLE = [
    (r"वेद", ("vaidika", "samhita", "scripture", 100, "canonical_scripture")),
    (r"उपनिषद्", ("vaidika", "upanishad", "scripture", 100, "canonical_scripture")),
    (r"ब्राह्मण", ("vaidika", "brahmana", "scripture", 100, "canonical_scripture")),
    (r"आरण्यक", ("vaidika", "aranyaka", "scripture", 100, "canonical_scripture")),
    (r"रामायण", ("all", "itihasa", "scripture", 100, "canonical_scripture")),
    (r"महाभारत", ("all", "itihasa", "scripture", 100, "canonical_scripture")),
    (r"गीता|भगवद्", ("all", "itihasa", "scripture", 100, "canonical_scripture")),
    (r"पुराण", ("all", "purana", "scripture", 80, "official_liturgy_ritual")),
    (r"मनुस्मृति|स्मृति", ("smarta", "dharmasastra", "scripture", 90, "official_core_doctrine")),
    (r"तन्त्र", ("tantric", "tantra", "ritual", 80, "official_liturgy_ritual")),
    (r"स्तोत्र|सूक्त|मन्त्र", ("all", "stotra", "ritual", 70, "authoritative_commentary")),
    (r"भाष्य|वार्तिक|टीका", ("all", "commentary", "commentary", 70, "authoritative_commentary")),
]


def classify(title: str):
    for pat, meta in CATEGORY_FROM_TITLE:
        if re.search(pat, title):
            return meta
    return ("all", "misc", "scripture", 60, "school_treatise")


class WikiHandler(xml.sax.ContentHandler):
    def __init__(self, sources_w, passages_w):
        self.sources_w = sources_w
        self.passages_w = passages_w
        self.in_page = False
        self.in_title = False
        self.in_text = False
        self.in_ns = False
        self.cur_title = []
        self.cur_text = []
        self.cur_ns = []
        self.n_sources = 0
        self.n_passages = 0
        self.n_total = 0

    def startElement(self, name, attrs):
        if name == "page":
            self.in_page = True
            self.cur_title = []; self.cur_text = []; self.cur_ns = []
        elif name == "title" and self.in_page:
            self.in_title = True
        elif name == "text" and self.in_page:
            self.in_text = True
        elif name == "ns" and self.in_page:
            self.in_ns = True

    def endElement(self, name):
        if name == "page":
            self.in_page = False
            title = "".join(self.cur_title).strip()
            text = "".join(self.cur_text)
            ns = "".join(self.cur_ns).strip()
            self.n_total += 1
            if ns != "0":
                return
            # filter: must contain at least 1 religious keyword OR be sufficiently long
            if not any(k in title for k in RELIGIOUS_KEYWORDS) and len(text) < 1000:
                return
            cleaned = clean_wikitext(text)
            if len(cleaned) < 200:
                return
            tradition, school, kind, auth, label = classify(title)
            slug = re.sub(r"[^\w]+", "_", title)[:80].strip("_")
            source_id = f"hindu.sawiki.{slug}"
            self.sources_w.write({
                "source_id": source_id,
                "religion": "hindu",
                "tradition": tradition,
                "school": school,
                "source_kind": kind,
                "authority_level": auth,
                "authority_label": label,
                "title": title,
                "subtitle": "Sanskrit Wikisource (sa.wikisource.org)",
                "author_body": "",
                "edition": "Wikimedia dump",
                "language": "sa",
                "script": "deva",
                "source_url": f"https://sa.wikisource.org/wiki/{title.replace(' ','_')}",
                "license": "CC-BY-SA-4.0",
                "license_notes": "Wikimedia content; see source page for individual contributions.",
                "valid_from": "",
                "valid_to": "",
                "text_hash": "",
            })
            self.n_sources += 1
            chunks = split_by_headings(cleaned, title)
            for i, (h, body) in enumerate(chunks):
                if len(body) < 60:
                    continue
                if len(body) > 12000:
                    body = body[:12000]
                pid = f"{source_id}.{i:04d}"
                self.passages_w.write({
                    "passage_id": pid,
                    "source_id": source_id,
                    "canonical_ref": f"{title} :: {h}" if h != title else title,
                    "parent_ref": title,
                    "ref_sort": i,
                    "language": "sa",
                    "script": "deva",
                    "text": body,
                    "normalized_text": normalize_text(body),
                    "heading": h,
                    "tags_json": json.dumps([school, "wikisource"], ensure_ascii=False),
                    "text_hash": text_hash(body),
                })
                self.n_passages += 1
            if self.n_sources % 100 == 0:
                print(f"  scanned={self.n_total} sources={self.n_sources} passages={self.n_passages}", flush=True)
        elif name == "title":
            self.in_title = False
        elif name == "text":
            self.in_text = False
        elif name == "ns":
            self.in_ns = False

    def characters(self, content):
        if self.in_title:
            self.cur_title.append(content)
        elif self.in_text:
            self.cur_text.append(content)
        elif self.in_ns:
            self.cur_ns.append(content)


def main():
    if not DUMP.exists():
        raise SystemExit(f"dump not found: {DUMP}")
    CORPUS.mkdir(parents=True, exist_ok=True)
    sources_w = JsonlWriter(CORPUS / "sources.jsonl")
    passages_w = JsonlWriter(CORPUS / "passages.jsonl")
    handler = WikiHandler(sources_w, passages_w)
    parser = xml.sax.make_parser()
    parser.setContentHandler(handler)
    parser.parse(str(DUMP))
    sources_w.close()
    passages_w.close()
    print(f"[sawiki] total scanned={handler.n_total} sources={handler.n_sources} passages={handler.n_passages}")


if __name__ == "__main__":
    main()
