#!/usr/bin/env python3
"""Smoke queries against each religion DB to verify FTS + structure."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

QUERIES = {
    "islam": [
        "Bismillah",
        "Ayat al-Kursi OR throne",
        "five pillars",
        "Ramadan fasting",
        "zakat poor",
        "qibla direction prayer",
        "Bukhari intention deeds",
        "tafsir Quran 2:255",
        "salah times",
        "Prophet wife marriage",
        "halal forbidden food",
        "hadith friday prayer",
        "Iblis Satan refuse",
        "Yusuf Joseph dream",
        "Maryam Jesus birth",
        "Quran 1:1",
        "Quran 18 cave",
        "Khaybar battle",
        "interest riba forbidden",
        "Pickthall verily",
    ],
    "catholic": [
        "In the beginning God created",
        "Our Father who art in heaven",
        "Beatitudes blessed are",
        "Eucharist body of Christ",
        "Gospel John love",
        "1 Corinthians 13",
        "Romans 8:28",
        "Genesis 1:1",
        "Matthew 5:3",
        "Psalm 23",
        "John 3:16",
        "Wisdom Sirach justice",
        "Maccabees Antiochus",
        "Tobit angel Raphael",
        "Vulgate principio",
        "Mary mother grace",
        "Apostles creed faith",
        "Baptism Jordan John",
        "Ten Commandments",
        "Sermon mount mountain",
    ],
    "buddhist": [
        "satipatthana mindfulness",
        "four noble truths dukkha",
        "eightfold path",
        "anatta non-self",
        "anicca impermanence",
        "metta loving kindness",
        "nibbana liberation",
        "Buddha awakening",
        "Sariputta Moggallana",
        "Dhammapada verse",
        "MN 10",
        "DN 16",
        "AN 10.61",
        "Ananda elder",
        "vinaya precept",
        "Pali sutta",
        "right view samma",
        "jhana absorption",
        "kamma rebirth",
        "Mara temptation",
    ],
    "hindu": [
        "Bhagavad Gita 2:47",
        "Krishna Arjuna chariot",
        "atman brahman",
        "karma yoga",
        "bhakti devotion",
        "dharma duty",
        "moksha liberation",
        "tat tvam asi",
        "Om mantra",
        "Shiva destroyer",
        "Vishnu preserver",
        "Brahma creator",
        "Upanishad isha",
        "Rigveda hymn",
        "Ramayana Sita",
        "Mahabharata war",
        "Ganesha obstacles",
        "yoga meditation",
        "ahimsa non-violence",
        "guru teacher disciple",
    ],
}


import re as _re

def make_fts_query(q: str) -> str:
    """Convert free-text query to safe FTS5 expression.
    Each token is double-quoted (treated as phrase), joined with OR.
    Punctuation in tokens is stripped to avoid FTS5 syntax errors.
    """
    tokens = _re.findall(r"[\w؀-ۿ一-鿿가-힯]+", q)
    if not tokens:
        return q
    return " OR ".join(f'"{t}"' for t in tokens if t)


def fts_query(conn, q: str, limit: int = 5):
    fts_q = make_fts_query(q)
    try:
        rows = conn.execute("""
            SELECT p.canonical_id, p.title, p.case_number AS citation,
                   substr(p.full_text, 1, 200) AS snip,
                   bm25(precedents_fts) AS rank
            FROM precedents_fts
            JOIN precedents p ON p.canonical_id = precedents_fts.canonical_id
            WHERE precedents_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (fts_q, limit)).fetchall()
        return rows
    except sqlite3.OperationalError as e:
        return [("ERROR", str(e), "", "", 0)]


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    rels = list(QUERIES.keys()) if target == "all" else [target]
    for rel in rels:
        db = ROOT / "corpus" / rel / f"{rel}.sqlite3"
        if not db.exists():
            print(f"SKIP {rel}: db not built")
            continue
        print(f"\n========== {rel} ==========")
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        conn.execute("PRAGMA query_only = ON")
        for q in QUERIES[rel]:
            print(f"\n  Q: {q}")
            rows = fts_query(conn, q, limit=3)
            if not rows:
                print("    (no results)")
                continue
            for r in rows:
                cid, title, citation, snip, rank = r
                snip_one = (snip or "").replace("\n", " ")[:160]
                print(f"    [{rank:.2f}] {citation or cid} | {title[:50]} | {snip_one}")
        conn.close()


if __name__ == "__main__":
    main()
