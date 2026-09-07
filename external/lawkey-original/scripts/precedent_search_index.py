"""Minimal SQLite FTS search fallback for Lawkey original snapshot.

Production Lawkey deployments should set `LAWKEY_WORKSPACE_SCRIPTS` to the
real legal search scripts. This fallback is intentionally small and exists so
the preserved original app can be imported without private local paths.

The fallback only uses an existing SQLite FTS index. It deliberately refuses to
fall back to leading-wildcard LIKE scans because Lawkey job creation can reach
this function repeatedly for each generated query.
"""

from __future__ import annotations

import os
import re
import sqlite3
import time
from typing import Any

_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")
_DEFAULT_LIMIT = 80
_MAX_LIMIT = 80
_MAX_TERMS = 12
_PROGRESS_OPS = 1_000
_DEFAULT_DEADLINE_MS = 100


def search_precedents(conn: sqlite3.Connection, query: str, *, limit: int = _DEFAULT_LIMIT) -> list[dict[str, Any]]:
    """Search precedents using the database's FTS table, if one is available.

    This bundled adapter is a safe import-time fallback, not the production
    search engine. Returning no matches is preferable to scanning the full
    precedents table on unauthenticated job requests.
    """

    fts_query = _fts_query(query)
    if not fts_query:
        return []

    try:
        bounded_limit = max(1, min(int(limit), _max_limit()))
    except (TypeError, ValueError):
        bounded_limit = _DEFAULT_LIMIT

    try:
        sql = _fts_sql(conn)
        if sql is None:
            return []
        return _execute_with_deadline(conn, sql, (fts_query, bounded_limit))
    except sqlite3.Error:
        return []


def _fts_query(query: str) -> str:
    tokens: list[str] = []
    for token in _TOKEN_RE.findall(query or ""):
        cleaned = token.strip().lower()
        if len(cleaned) >= 2 and cleaned not in tokens:
            tokens.append(cleaned)
        if len(tokens) >= _MAX_TERMS:
            break
    return " OR ".join(f'"{token}"' for token in tokens)


def _fts_sql(conn: sqlite3.Connection) -> str | None:
    tables = {
        str(row[0])
        for row in conn.execute(
            "select name from sqlite_master where type = 'table' and name in ('precedents', 'precedents_fts')"
        )
    }
    if {"precedents", "precedents_fts"} - tables:
        return None

    precedent_columns = _table_columns(conn, "precedents")
    fts_columns = _table_columns(conn, "precedents_fts")
    if "canonical_id" in precedent_columns and "canonical_id" in fts_columns:
        join_clause = "p.canonical_id = precedents_fts.canonical_id"
    else:
        join_clause = "p.rowid = precedents_fts.rowid"

    return f"""
        SELECT p.*
        FROM precedents_fts
        JOIN precedents p ON {join_clause}
        WHERE precedents_fts MATCH ?
        LIMIT ?
        """


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}


def _execute_with_deadline(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple[str, int],
) -> list[dict[str, Any]]:
    deadline = time.monotonic() + (_deadline_ms() / 1000)

    def stop_if_expired() -> int:
        return 1 if time.monotonic() >= deadline else 0

    previous_row_factory = conn.row_factory
    conn.row_factory = sqlite3.Row
    conn.set_progress_handler(stop_if_expired, _PROGRESS_OPS)
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.set_progress_handler(None, 0)
        conn.row_factory = previous_row_factory
    return [dict(row) for row in rows]


def _deadline_ms() -> int:
    return _env_int("LAWKEY_FALLBACK_SEARCH_DEADLINE_MS", _DEFAULT_DEADLINE_MS, minimum=1)


def _max_limit() -> int:
    return _env_int("LAWKEY_FALLBACK_SEARCH_LIMIT", _MAX_LIMIT, minimum=1, maximum=_MAX_LIMIT)


def _env_int(name: str, default: int, *, minimum: int, maximum: int | None = None) -> int:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value.strip())
    except ValueError:
        return default
    parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed
