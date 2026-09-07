from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "external/lawkey-original/scripts/precedent_search_index.py"


def _load_fallback_module():
    spec = importlib.util.spec_from_file_location("lawkey_fallback_precedent_search_index", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_fallback_precedent_search_refuses_unindexed_like_scan() -> None:
    module = _load_fallback_module()
    conn = sqlite3.connect(":memory:")
    conn.execute("create table precedents (canonical_id text primary key, text text)")
    conn.execute("insert into precedents values ('case-1', 'common term in a large table')")
    statements: list[str] = []
    conn.set_trace_callback(statements.append)

    assert module.search_precedents(conn, "common", limit=10) == []

    assert not any(" like " in statement.lower() for statement in statements)


def test_fallback_precedent_search_uses_bounded_fts_query() -> None:
    module = _load_fallback_module()
    conn = sqlite3.connect(":memory:")
    conn.execute("create table precedents (canonical_id text primary key, title text, text text)")
    conn.execute("create virtual table precedents_fts using fts5(canonical_id UNINDEXED, text)")
    conn.execute("insert into precedents values ('case-1', 'Relevant', '징계 처분 본문')")
    conn.execute("insert into precedents_fts values ('case-1', '징계 처분 본문')")

    rows = module.search_precedents(conn, "징계 처분", limit=200)

    assert [row["canonical_id"] for row in rows] == ["case-1"]
    assert rows[0]["title"] == "Relevant"
