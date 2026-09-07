#!/usr/bin/env python3
"""Religion corpus loader.

JSONL → corpus/<rel>/<rel>.sqlite3 with:
  - sources, passages, passage_links (per spec)
  - search_documents (bundle layer; passage_window or full doc)
  - precedents + precedents_fts (beta6 compatible surface)

Usage:
  python3 scripts/loader.py islam
  python3 scripts/loader.py all
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RELIGIONS = ["islam", "catholic", "buddhist", "hindu"]


SCHEMA_SOURCES = """
CREATE TABLE sources (
  source_id        TEXT PRIMARY KEY,
  religion         TEXT NOT NULL,
  tradition        TEXT NOT NULL DEFAULT '',
  school           TEXT NOT NULL DEFAULT '',
  source_kind      TEXT NOT NULL,
  authority_level  INTEGER NOT NULL,
  authority_label  TEXT NOT NULL,
  title            TEXT NOT NULL,
  subtitle         TEXT NOT NULL DEFAULT '',
  author_body      TEXT NOT NULL DEFAULT '',
  edition          TEXT NOT NULL DEFAULT '',
  language         TEXT NOT NULL,
  script           TEXT NOT NULL DEFAULT '',
  source_url       TEXT NOT NULL DEFAULT '',
  license          TEXT NOT NULL DEFAULT '',
  license_notes    TEXT NOT NULL DEFAULT '',
  valid_from       TEXT NOT NULL DEFAULT '',
  valid_to         TEXT NOT NULL DEFAULT '',
  created_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_sources_scope ON sources(religion, tradition, school, source_kind, authority_level);
"""

SCHEMA_PASSAGES = """
CREATE TABLE passages (
  passage_id       TEXT PRIMARY KEY,
  source_id        TEXT NOT NULL,
  canonical_ref    TEXT NOT NULL,
  parent_ref       TEXT NOT NULL DEFAULT '',
  ref_sort         INTEGER NOT NULL DEFAULT 0,
  language         TEXT NOT NULL,
  script           TEXT NOT NULL DEFAULT '',
  text             TEXT NOT NULL,
  normalized_text  TEXT NOT NULL,
  heading          TEXT NOT NULL DEFAULT '',
  tags_json        TEXT NOT NULL DEFAULT '[]',
  text_hash        TEXT NOT NULL
);
CREATE INDEX idx_passages_source_sort ON passages(source_id, ref_sort);
CREATE INDEX idx_passages_ref ON passages(canonical_ref);
"""

SCHEMA_LINKS = """
CREATE TABLE passage_links (
  from_passage_id  TEXT NOT NULL,
  to_passage_id    TEXT NOT NULL,
  link_type        TEXT NOT NULL,
  confidence       REAL NOT NULL DEFAULT 1.0,
  note             TEXT NOT NULL DEFAULT '',
  PRIMARY KEY(from_passage_id, to_passage_id, link_type)
);
CREATE INDEX idx_passage_links_to ON passage_links(to_passage_id, link_type);
"""

SCHEMA_SEARCH = """
CREATE TABLE search_documents (
  doc_id           TEXT PRIMARY KEY,
  religion         TEXT NOT NULL,
  tradition        TEXT NOT NULL DEFAULT '',
  school           TEXT NOT NULL DEFAULT '',
  source_kind      TEXT NOT NULL,
  authority_level  INTEGER NOT NULL,
  authority_label  TEXT NOT NULL,
  title            TEXT NOT NULL,
  citation_key     TEXT NOT NULL,
  authority_body   TEXT NOT NULL DEFAULT '',
  source_date      TEXT NOT NULL DEFAULT '',
  topic_key        TEXT NOT NULL DEFAULT '',
  bundle_kind      TEXT NOT NULL,
  passage_ids_json TEXT NOT NULL DEFAULT '[]',
  full_text        TEXT NOT NULL,
  display_text     TEXT NOT NULL DEFAULT '',
  search_text      TEXT NOT NULL,
  tags_json        TEXT NOT NULL DEFAULT '[]',
  token_count      INTEGER NOT NULL DEFAULT 0,
  text_hash        TEXT NOT NULL
);
CREATE INDEX idx_search_scope ON search_documents(religion, tradition, school, source_kind, authority_level);
CREATE INDEX idx_search_topic ON search_documents(topic_key);
CREATE INDEX idx_search_authority ON search_documents(authority_level DESC);
"""

SCHEMA_PRECEDENTS = """
CREATE TABLE precedents (
  canonical_id    TEXT PRIMARY KEY,
  source_dataset  TEXT,
  source_path     TEXT,
  title           TEXT,
  case_number     TEXT,
  court           TEXT,
  decision_date   TEXT,
  case_name       TEXT,
  case_type       TEXT,
  full_text       TEXT NOT NULL,
  text_hash       TEXT NOT NULL
);

CREATE VIRTUAL TABLE precedents_fts
USING fts5(canonical_id UNINDEXED, full_text, tokenize='unicode61');
"""

PRAGMAS = [
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous = NORMAL",
    "PRAGMA temp_store = MEMORY",
    "PRAGMA mmap_size = 1073741824",
    "PRAGMA cache_size = -200000",
]


def open_db(path: Path) -> sqlite3.Connection:
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    for p in PRAGMAS:
        conn.execute(p)
    conn.executescript(SCHEMA_SOURCES + SCHEMA_PASSAGES + SCHEMA_LINKS + SCHEMA_SEARCH + SCHEMA_PRECEDENTS)
    return conn


def text_hash(text: str) -> str:
    n = re.sub(r"\s+", " ", unicodedata.normalize("NFC", text).strip())
    return "sha256:" + hashlib.sha256(n.encode("utf-8")).hexdigest()


def estimate_tokens(text: str) -> int:
    """rough — ~4 chars per token. Good enough for budgeting."""
    return max(1, len(text) // 4)


def load_jsonl(p: Path):
    if not p.exists():
        return
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


def insert_sources(conn, sources_path: Path):
    n = 0
    rows = []
    for s in load_jsonl(sources_path):
        rows.append((
            s.get("source_id"), s.get("religion",""), s.get("tradition",""),
            s.get("school",""), s.get("source_kind",""), int(s.get("authority_level",0)),
            s.get("authority_label",""), s.get("title",""), s.get("subtitle",""),
            s.get("author_body",""), s.get("edition",""), s.get("language",""),
            s.get("script",""), s.get("source_url",""), s.get("license",""),
            s.get("license_notes",""), s.get("valid_from",""), s.get("valid_to",""),
        ))
        if len(rows) >= 1000:
            conn.executemany("""INSERT OR REPLACE INTO sources
              (source_id,religion,tradition,school,source_kind,authority_level,authority_label,
               title,subtitle,author_body,edition,language,script,source_url,license,license_notes,
               valid_from,valid_to) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
            n += len(rows); rows.clear()
    if rows:
        conn.executemany("""INSERT OR REPLACE INTO sources
          (source_id,religion,tradition,school,source_kind,authority_level,authority_label,
           title,subtitle,author_body,edition,language,script,source_url,license,license_notes,
           valid_from,valid_to) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
        n += len(rows)
    conn.commit()
    print(f"  sources: {n}")


def insert_passages(conn, passages_path: Path):
    n = 0; rows = []
    for p in load_jsonl(passages_path):
        rows.append((
            p.get("passage_id"), p.get("source_id"), p.get("canonical_ref",""),
            p.get("parent_ref",""), int(p.get("ref_sort",0)),
            p.get("language",""), p.get("script",""), p.get("text",""),
            p.get("normalized_text",""), p.get("heading",""),
            p.get("tags_json","[]"), p.get("text_hash",""),
        ))
        if len(rows) >= 5000:
            conn.executemany("""INSERT OR REPLACE INTO passages
              (passage_id,source_id,canonical_ref,parent_ref,ref_sort,language,script,
               text,normalized_text,heading,tags_json,text_hash) VALUES
              (?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
            n += len(rows); rows.clear()
    if rows:
        conn.executemany("""INSERT OR REPLACE INTO passages
          (passage_id,source_id,canonical_ref,parent_ref,ref_sort,language,script,
           text,normalized_text,heading,tags_json,text_hash) VALUES
          (?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
        n += len(rows)
    conn.commit()
    print(f"  passages: {n}")


def insert_links(conn, links_path: Path):
    n = 0; rows = []
    for l in load_jsonl(links_path):
        rows.append((
            l.get("from_passage_id"), l.get("to_passage_id"),
            l.get("link_type",""), float(l.get("confidence",1.0)), l.get("note",""),
        ))
        if len(rows) >= 5000:
            conn.executemany("""INSERT OR REPLACE INTO passage_links
              (from_passage_id,to_passage_id,link_type,confidence,note) VALUES (?,?,?,?,?)""", rows)
            n += len(rows); rows.clear()
    if rows:
        conn.executemany("""INSERT OR REPLACE INTO passage_links
          (from_passage_id,to_passage_id,link_type,confidence,note) VALUES (?,?,?,?,?)""", rows)
        n += len(rows)
    conn.commit()
    print(f"  links: {n}")


def build_search_documents(conn):
    """Auto-generate per-passage bundles with adjacent-passage windows + translation/commentary aggregation.

    Memory-conservative: for each source, load only that source's passages into RAM,
    then emit docs and free. Avoids OOM on large religions (e.g., 1.3M Buddhist passages).
    """
    cur = conn.cursor()

    # Map: source_id -> source_meta (small)
    src = {}
    for r in cur.execute("SELECT source_id, religion, tradition, school, source_kind, authority_level, authority_label, title, language, script FROM sources"):
        src[r[0]] = {
            "religion": r[1], "tradition": r[2], "school": r[3],
            "source_kind": r[4], "authority_level": r[5], "authority_label": r[6],
            "title": r[7], "language": r[8], "script": r[9],
        }

    # Incoming links: to_pid -> [(from_pid, link_type)]. Needed globally so we can
    # cross-reference (e.g., Quran ayah → its translation). For very large databases
    # (>1M links) we fall back to a SQL lookup per call. Threshold: 2M.
    n_links = cur.execute("SELECT COUNT(*) FROM passage_links").fetchone()[0]
    if n_links < 2_000_000:
        incoming: dict[str, list[tuple[str, str]]] = {}
        for r in cur.execute("SELECT from_passage_id, to_passage_id, link_type FROM passage_links"):
            incoming.setdefault(r[1], []).append((r[0], r[2]))
        get_incoming = lambda pid: incoming.get(pid, [])
    else:
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pl_to ON passage_links(to_passage_id)")
        def get_incoming(pid):
            return list(cur.execute("SELECT from_passage_id, link_type FROM passage_links WHERE to_passage_id=?", (pid,)))

    rows = []
    seen = set()

    def emit_doc(doc_id, religion, tradition, school, source_kind, auth, alabel, title,
                 citation, body, search_text, passage_ids, bundle_kind, tags):
        if doc_id in seen:
            return
        seen.add(doc_id)
        h = text_hash(body)
        tk = estimate_tokens(body)
        rows.append((doc_id, religion, tradition or "", school or "",
                     source_kind, auth, alabel, title, citation,
                     "", "", "", bundle_kind, json.dumps(passage_ids, ensure_ascii=False),
                     body, body, search_text, json.dumps(tags, ensure_ascii=False),
                     tk, h))
        if len(rows) >= 2000:
            cur.executemany("""INSERT OR REPLACE INTO search_documents
              (doc_id,religion,tradition,school,source_kind,authority_level,authority_label,
               title,citation_key,authority_body,source_date,topic_key,bundle_kind,passage_ids_json,
               full_text,display_text,search_text,tags_json,token_count,text_hash)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
            rows.clear()

    # Iterate sources, load that source's passages on demand (memory-conservative).
    cur.execute("CREATE INDEX IF NOT EXISTS idx_p_src ON passages(source_id, ref_sort)")
    cur2 = conn.cursor()
    n_emitted = 0
    for sid, s in src.items():
        # Load only this source's passages
        plist = list(cur2.execute(
            "SELECT passage_id, text, ref_sort, canonical_ref FROM passages WHERE source_id=? ORDER BY ref_sort",
            (sid,)))
        if not plist:
            continue
        kind = s["source_kind"]
        auth = s["authority_level"]
        alabel = s["authority_label"]
        title = s["title"]
        for idx, (pid, text, rs, cref) in enumerate(plist):

            # Header
            meta_block = (f"[META]\nreligion: {s['religion']}\ntradition: {s['tradition']}\n"
                          f"school: {s['school']}\nauthority_level: {auth}\nsource_kind: {kind}\n"
                          f"citation: {cref}\ntitle: {title}\n")

            primary_block = f"\n[PRIMARY TEXT — {s['language']}]\n{text}\n"

            # Neighbors (prev, next) within this source's passage list (already loaded)
            neighbors_block = ""
            if kind in ("scripture", "official_core_doctrine", "official_liturgy_ritual", "vinaya", "sutta", "abhidhamma", "agama", "ritual"):
                ctx_lines = []
                if idx > 0:
                    _p_pid, p_text, _, p_ref = plist[idx-1]
                    ctx_lines.append(f"prev ({p_ref}): {p_text}")
                if idx + 1 < len(plist):
                    _n_pid, n_text, _, n_ref = plist[idx+1]
                    ctx_lines.append(f"next ({n_ref}): {n_text}")
                if ctx_lines:
                    neighbors_block = "\n[CONTEXT WINDOW]\n" + "\n".join(ctx_lines) + "\n"

            # Translations / commentaries pointing INTO this passage
            tr_block = ""
            tr_passages = []
            cm_passages = []
            for from_pid, ltype in get_incoming(pid):
                # Look up the from-passage on demand (avoid global pass_meta dict)
                row = cur2.execute("SELECT source_id, text FROM passages WHERE passage_id=?", (from_pid,)).fetchone()
                if not row:
                    continue
                from_sid, from_text = row
                from_src = src.get(from_sid, {})
                lang = from_src.get("language", "?")
                if ltype == "translation_of":
                    tr_passages.append((lang, from_text, from_sid))
                elif ltype in ("commentary_on", "explains", "applies", "cites"):
                    cm_passages.append((lang, from_text, from_sid, ltype))

            if tr_passages:
                tr_block = "\n[APPROVED TRANSLATIONS / MEANINGS]\n"
                # cap to 5 translations to avoid bloat
                for lang, t, sid_t in tr_passages[:5]:
                    src_t = src.get(sid_t, {}).get("title", sid_t)
                    tr_block += f"({lang}, {src_t}): {t}\n"

            cm_block = ""
            if cm_passages:
                cm_block = "\n[COMMENTARY / APPLICATION]\n"
                for lang, t, sid_c, ltype in cm_passages[:3]:
                    src_c = src.get(sid_c, {}).get("title", sid_c)
                    cm_block += f"({ltype}, {lang}, {src_c}): {t[:1200]}\n"

            boundaries = "\n[BOUNDARIES]\nscope: " + ("scripture+context" if neighbors_block else kind) + "\n"
            if "quran" in sid.lower():
                boundaries += "translation_policy: do_not_machine_retranslate_quran\n"

            full = meta_block + primary_block + neighbors_block + tr_block + cm_block + boundaries
            search_text = " ".join([text] + [t for _, t, _ in tr_passages[:5]] +
                                    [t for _, t, _, _ in cm_passages[:2]])
            doc_id = f"doc.{pid}"
            tags = [kind, s["tradition"], s["school"]]
            tags = [t for t in tags if t]
            emit_doc(doc_id, s["religion"], s["tradition"], s["school"],
                     kind, auth, alabel, title, cref, full, search_text,
                     [pid] + [fp for fp, _ in get_incoming(pid)][:5],
                     "scripture_window" if kind == "scripture" else f"{kind}_unit", tags)
            n_emitted += 1

    if rows:
        cur.executemany("""INSERT OR REPLACE INTO search_documents
          (doc_id,religion,tradition,school,source_kind,authority_level,authority_label,
           title,citation_key,authority_body,source_date,topic_key,bundle_kind,passage_ids_json,
           full_text,display_text,search_text,tags_json,token_count,text_hash)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
    conn.commit()
    print(f"  search_documents: {n_emitted}")


def build_precedents(conn):
    cur = conn.cursor()
    n = cur.execute("""
      INSERT OR REPLACE INTO precedents
        (canonical_id, source_dataset, source_path, title, case_number, court,
         decision_date, case_name, case_type, full_text, text_hash)
      SELECT
        doc_id,
        religion || '/' || tradition || '/' || school || '/' || source_kind,
        title,
        title,
        citation_key,
        authority_body,
        source_date,
        COALESCE(NULLIF(topic_key, ''), title),
        bundle_kind,
        full_text,
        text_hash
      FROM search_documents
    """).rowcount
    conn.commit()
    print(f"  precedents: {n}")
    n2 = cur.execute("""
      INSERT INTO precedents_fts(canonical_id, full_text)
      SELECT doc_id, search_text FROM search_documents
    """).rowcount
    conn.commit()
    print(f"  precedents_fts: {n2}")


def build_one(rel: str):
    src_dir = ROOT / "corpus" / rel
    db_path = src_dir / f"{rel}.sqlite3"
    print(f"\n=== {rel} → {db_path}")
    conn = open_db(db_path)
    try:
        insert_sources(conn, src_dir / "sources.jsonl")
        insert_passages(conn, src_dir / "passages.jsonl")
        insert_links(conn, src_dir / "links.jsonl")
        build_search_documents(conn)
        build_precedents(conn)
        # Stats
        for tbl in ("sources", "passages", "passage_links", "search_documents", "precedents"):
            n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            print(f"  {tbl}: {n}")
        size = db_path.stat().st_size
        print(f"  db size: {size/1024/1024:.1f} MB")
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("religion", choices=RELIGIONS + ["all"])
    args = ap.parse_args()
    targets = RELIGIONS if args.religion == "all" else [args.religion]
    for r in targets:
        if not (ROOT / "corpus" / r / "sources.jsonl").exists():
            print(f"  skip {r}: no sources.jsonl")
            continue
        build_one(r)


if __name__ == "__main__":
    main()
