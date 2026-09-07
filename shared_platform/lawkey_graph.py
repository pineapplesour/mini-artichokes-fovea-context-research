from __future__ import annotations

import hashlib
import re
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import PurePath
from typing import Any, Iterable

from .context_frames import LegalTaxonomy, load_event_frames, rank_analogous_frames


ACTIVE_STATUS = "active"
DEFAULT_GRAPH_VERSION_PREFIX = "lawkey_graph"
EDGE_GROUP_LIMITS = {
    "case_number": 120,
    "case_year_serial": 120,
    "source_path": 500,
    "source_parent": 120,
    "file_stem_token": 80,
    "case_name": 80,
    "court": 40,
}
EDGE_NEIGHBOR_WINDOWS = {
    "case_number": 20,
    "case_year_serial": 12,
    "source_path": 12,
    "source_parent": 10,
    "file_stem_token": 8,
    "case_name": 8,
    "court": 6,
}
EDGE_BATCH_SIZE = 100_000
FETCH_BATCH_SIZE = 500


@dataclass(frozen=True)
class LawkeyGraphBuildReport:
    graph_version: str
    source_count: int
    entity_count: int
    edge_count: int
    activated: bool


def ensure_lawkey_graph_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS lawkey_graph_versions (
          graph_version TEXT PRIMARY KEY,
          source_snapshot_hash TEXT NOT NULL,
          status TEXT NOT NULL,
          source_count INTEGER NOT NULL,
          entity_count INTEGER NOT NULL,
          edge_count INTEGER NOT NULL,
          created_at REAL NOT NULL,
          activated_at REAL
        );
        CREATE TABLE IF NOT EXISTS lawkey_source_entities (
          graph_version TEXT NOT NULL,
          source_id TEXT NOT NULL,
          entity TEXT NOT NULL,
          entity_type TEXT NOT NULL,
          confidence REAL NOT NULL,
          evidence TEXT NOT NULL DEFAULT '',
          PRIMARY KEY (graph_version, source_id, entity, entity_type)
        );
        CREATE TABLE IF NOT EXISTS lawkey_source_edges (
          graph_version TEXT NOT NULL,
          source_id TEXT NOT NULL,
          target_source_id TEXT NOT NULL,
          relation_type TEXT NOT NULL,
          weight REAL NOT NULL,
          reason TEXT NOT NULL DEFAULT '',
          evidence TEXT NOT NULL DEFAULT '',
          PRIMARY KEY (graph_version, source_id, target_source_id, relation_type)
        );
        CREATE INDEX IF NOT EXISTS idx_lawkey_edges_source
          ON lawkey_source_edges(graph_version, source_id, weight DESC);
        CREATE INDEX IF NOT EXISTS idx_lawkey_edges_target
          ON lawkey_source_edges(graph_version, target_source_id);
        CREATE INDEX IF NOT EXISTS idx_lawkey_entities_lookup
          ON lawkey_source_entities(graph_version, entity_type, entity, confidence DESC);
        """
    )


def active_lawkey_graph_version(conn: sqlite3.Connection) -> str:
    try:
        row = conn.execute(
            """
            SELECT graph_version
            FROM lawkey_graph_versions
            WHERE status = ?
            ORDER BY COALESCE(activated_at, created_at) DESC
            LIMIT 1
            """,
            (ACTIVE_STATUS,),
        ).fetchone()
    except sqlite3.OperationalError:
        return ""
    return str(row["graph_version"] if _has_key(row, "graph_version") else row[0]) if row else ""


def expand_lawkey_precedent_rows(
    conn: sqlite3.Connection,
    seed_rows: list[sqlite3.Row],
    *,
    seed_scores: dict[str, float],
    max_neighbors: int = 24,
    max_expanded: int = 120,
) -> tuple[list[sqlite3.Row], dict[str, float]]:
    graph_version = active_lawkey_graph_version(conn)
    if not graph_version or not seed_rows:
        return [], {}
    seed_ids = [str(row["canonical_id"] or "") for row in seed_rows if str(row["canonical_id"] or "")]
    if not seed_ids:
        return [], {}
    seed_ids = sorted(seed_ids, key=lambda source_id: (-seed_scores.get(source_id, 0.0), source_id))[:80]

    relation_scores: dict[str, float] = {}
    target_ids: list[str] = []
    seed_rank_weight = {source_id: max(0.25, 1.0 - (index * 0.015)) for index, source_id in enumerate(seed_ids)}
    try:
        for source_id in seed_ids:
            edge_rows = conn.execute(
                """
                SELECT source_id, target_source_id, relation_type, weight
                FROM lawkey_source_edges
                WHERE graph_version = ?
                  AND source_id = ?
                ORDER BY weight DESC
                LIMIT ?
                """,
                (graph_version, source_id, max(1, max_neighbors)),
            ).fetchall()
            for edge in edge_rows:
                target_id = str(edge["target_source_id"] or "")
                if not target_id or target_id in seed_ids:
                    continue
                seed_score = max(1.0, float(seed_scores.get(source_id) or 1.0))
                weight = max(0.0, min(float(edge["weight"] or 0.0), 1.0))
                score = seed_score * weight * seed_rank_weight.get(source_id, 0.25)
                if score <= 0:
                    continue
                if target_id not in relation_scores:
                    target_ids.append(target_id)
                relation_scores[target_id] = max(relation_scores.get(target_id, 0.0), score)
                if len(target_ids) >= max_expanded:
                    break
            if len(target_ids) >= max_expanded:
                break
    except sqlite3.OperationalError:
        return [], {}

    if not target_ids:
        return [], {}
    rows_by_id = _fetch_precedent_rows_by_ids(conn, target_ids)
    ordered = sorted(
        (row for row in rows_by_id.values()),
        key=lambda row: (-relation_scores.get(str(row["canonical_id"] or ""), 0.0), str(row["canonical_id"] or "")),
    )
    return ordered[:max_expanded], relation_scores


def expand_lawkey_event_frame_rows(
    conn: sqlite3.Connection,
    query: str,
    seed_rows: list[sqlite3.Row],
    *,
    max_expanded: int = 80,
) -> tuple[list[sqlite3.Row], dict[str, float]]:
    if not query or not _table_exists(conn, "event_frames"):
        return [], {}
    try:
        frames = load_event_frames(conn, ensure_schema=False)
    except sqlite3.OperationalError:
        return [], {}
    if not frames:
        return [], {}
    seed_ids = {str(row["canonical_id"] or "") for row in seed_rows if str(row["canonical_id"] or "")}
    matches = rank_analogous_frames(
        query,
        frames,
        taxonomy=LegalTaxonomy.default(),
        threshold=0.55,
        limit=max_expanded,
    )
    target_ids: list[str] = []
    relation_scores: dict[str, float] = {}
    for match in matches:
        target_id = match.frame.doc_id
        if not target_id or target_id in seed_ids:
            continue
        if target_id not in relation_scores:
            target_ids.append(target_id)
        relation_scores[target_id] = max(relation_scores.get(target_id, 0.0), 250.0 + (match.score * 750.0))
        if len(target_ids) >= max_expanded:
            break
    if not target_ids:
        return [], {}
    rows_by_id = _fetch_precedent_rows_by_ids(conn, target_ids)
    ordered = sorted(
        rows_by_id.values(),
        key=lambda row: (-relation_scores.get(str(row["canonical_id"] or ""), 0.0), str(row["canonical_id"] or "")),
    )
    return ordered[:max_expanded], relation_scores


def rebuild_lawkey_source_graph(
    conn: sqlite3.Connection,
    *,
    graph_version: str = "",
    activate: bool = True,
) -> LawkeyGraphBuildReport:
    ensure_lawkey_graph_schema(conn)
    rows = conn.execute(
        """
        SELECT canonical_id, source_dataset, source_path, title, case_number, court,
               decision_date, case_name, case_type, text_hash
        FROM precedents
        ORDER BY canonical_id
        """
    ).fetchall()
    source_count = len(rows)
    snapshot_hash = _snapshot_hash(rows)
    version = graph_version or f"{DEFAULT_GRAPH_VERSION_PREFIX}_{snapshot_hash[:12]}"

    conn.execute("DELETE FROM lawkey_source_entities WHERE graph_version = ?", (version,))
    conn.execute("DELETE FROM lawkey_source_edges WHERE graph_version = ?", (version,))
    conn.execute("DELETE FROM lawkey_graph_versions WHERE graph_version = ?", (version,))

    entity_rows: list[tuple[str, str, str, str, float, str]] = []
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in rows:
        source_id = str(row["canonical_id"] or "")
        if not source_id:
            continue
        for entity_type, entity, confidence, evidence in _row_entities(row):
            entity_rows.append((version, source_id, entity, entity_type, confidence, evidence))
            groups[(entity_type, entity)].append(source_id)

    if entity_rows:
        conn.executemany(
            """
            INSERT OR REPLACE INTO lawkey_source_entities
              (graph_version, source_id, entity, entity_type, confidence, evidence)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            entity_rows,
        )

    edge_batch: list[tuple[str, str, str, str, float, str, str]] = []
    for (entity_type, entity), source_ids in groups.items():
        if len(source_ids) < 2:
            continue
        group_limit = EDGE_GROUP_LIMITS.get(entity_type)
        if group_limit is None or len(source_ids) > group_limit:
            continue
        relation_type, base_weight = _relation_for_entity_type(entity_type)
        neighbor_window = EDGE_NEIGHBOR_WINDOWS.get(entity_type, 8)
        reason = f"{relation_type} via {entity_type}:{entity}"
        for source_id, target_id in _iter_neighbor_pairs(source_ids, neighbor_window):
            edge_batch.append((version, source_id, target_id, relation_type, base_weight, reason, entity))
            if len(edge_batch) >= EDGE_BATCH_SIZE:
                _flush_edge_batch(conn, edge_batch)
                edge_batch.clear()
    if edge_batch:
        _flush_edge_batch(conn, edge_batch)
        edge_batch.clear()

    edge_count = conn.execute(
        "SELECT COUNT(*) FROM lawkey_source_edges WHERE graph_version = ?",
        (version,),
    ).fetchone()[0]

    now = time.time()
    if activate:
        conn.execute("UPDATE lawkey_graph_versions SET status = 'inactive' WHERE status = ?", (ACTIVE_STATUS,))
    conn.execute(
        """
        INSERT INTO lawkey_graph_versions
          (graph_version, source_snapshot_hash, status, source_count, entity_count, edge_count, created_at, activated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            version,
            snapshot_hash,
            ACTIVE_STATUS if activate else "built",
            source_count,
            len(entity_rows),
            edge_count,
            now,
            now if activate else None,
        ),
    )
    conn.commit()
    return LawkeyGraphBuildReport(
        graph_version=version,
        source_count=source_count,
        entity_count=len(entity_rows),
        edge_count=edge_count,
        activated=activate,
    )


def _fetch_precedent_rows_by_ids(conn: sqlite3.Connection, ids: list[str]) -> dict[str, sqlite3.Row]:
    if not ids:
        return {}
    rows: list[sqlite3.Row] = []
    try:
        for offset in range(0, len(ids), FETCH_BATCH_SIZE):
            batch = ids[offset : offset + FETCH_BATCH_SIZE]
            placeholders = ",".join("?" for _ in batch)
            rows.extend(
                conn.execute(
                    f"""
                    SELECT canonical_id, source_dataset, source_path, title, case_number, court,
                           decision_date, case_name, case_type, full_text
                    FROM precedents
                    WHERE canonical_id IN ({placeholders})
                    """,
                    batch,
                ).fetchall()
            )
    except sqlite3.OperationalError:
        return {}
    return {str(row["canonical_id"] or ""): row for row in rows}


def _row_entities(row: sqlite3.Row) -> Iterable[tuple[str, str, float, str]]:
    source_path = str(row["source_path"] or "")
    source_dataset = str(row["source_dataset"] or "")
    case_number = str(row["case_number"] or "")
    court = _normalize_label(str(row["court"] or ""))
    case_name = _normalize_label(str(row["case_name"] or ""))
    case_type = _normalize_label(str(row["case_type"] or ""))

    if source_dataset:
        yield "source_dataset", source_dataset, 0.45, source_dataset
    normalized_path = _normalize_path(source_path)
    if normalized_path:
        yield "source_path", normalized_path, 0.90, source_path
    parent = _path_parent_key(source_path)
    if parent:
        yield "source_parent", parent, 0.82, source_path
    file_stem = _path_stem_key(source_path)
    if file_stem:
        for token in _file_stem_tokens(file_stem):
            yield "file_stem_token", token, 0.55, file_stem
    normalized_case = _normalize_case_number(case_number)
    if normalized_case:
        yield "case_number", normalized_case, 0.95, case_number
        year = normalized_case[:4]
        serial = re.sub(r"\D+", "", normalized_case[4:])
        if year and serial:
            yield "case_year_serial", f"{year}:{serial}", 0.70, case_number
    if court:
        yield "court", court, 0.50, str(row["court"] or "")
    if case_name:
        yield "case_name", case_name, 0.50, str(row["case_name"] or "")
    if case_type:
        yield "case_type", case_type, 0.25, str(row["case_type"] or "")


def _relation_for_entity_type(entity_type: str) -> tuple[str, float]:
    if entity_type == "case_number":
        return "same_case_number", 0.98
    if entity_type == "case_year_serial":
        return "same_case_serial", 0.78
    if entity_type == "source_path":
        return "same_source_path", 0.92
    if entity_type == "source_parent":
        return "same_source_parent", 0.86
    if entity_type == "file_stem_token":
        return "shared_file_stem_token", 0.60
    if entity_type == "case_name":
        return "same_case_name", 0.58
    if entity_type == "court":
        return "same_court", 0.35
    if entity_type == "source_dataset":
        return "same_source_dataset", 0.30
    return "same_metadata", 0.20


def _iter_neighbor_pairs(source_ids: list[str], neighbor_window: int) -> Iterable[tuple[str, str]]:
    if neighbor_window <= 0:
        return
    ordered = sorted(dict.fromkeys(source_ids))
    for index, source_id in enumerate(ordered):
        start = max(0, index - neighbor_window)
        end = min(len(ordered), index + neighbor_window + 1)
        for target_id in ordered[start:index]:
            yield source_id, target_id
        for target_id in ordered[index + 1 : end]:
            yield source_id, target_id


def _flush_edge_batch(conn: sqlite3.Connection, rows: list[tuple[str, str, str, str, float, str, str]]) -> None:
    conn.executemany(
        """
        INSERT INTO lawkey_source_edges
          (graph_version, source_id, target_source_id, relation_type, weight, reason, evidence)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(graph_version, source_id, target_source_id, relation_type) DO UPDATE SET
          weight = CASE
            WHEN excluded.weight > lawkey_source_edges.weight THEN excluded.weight
            ELSE lawkey_source_edges.weight
          END,
          reason = CASE
            WHEN excluded.weight > lawkey_source_edges.weight THEN excluded.reason
            ELSE lawkey_source_edges.reason
          END,
          evidence = CASE
            WHEN excluded.weight > lawkey_source_edges.weight THEN excluded.evidence
            ELSE lawkey_source_edges.evidence
          END
        """,
        rows,
    )


def _snapshot_hash(rows: list[sqlite3.Row]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(str(row["canonical_id"] or "").encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(row["text_hash"] if _has_key(row, "text_hash") else "").encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _path_parent_key(value: str) -> str:
    normalized = _normalize_path(value)
    if not normalized:
        return ""
    parent = normalized.rsplit("/", 1)[0] if "/" in normalized else ""
    return parent[-160:]


def _path_stem_key(value: str) -> str:
    normalized = _normalize_path(value)
    if not normalized:
        return ""
    name = normalized.rsplit("/", 1)[-1]
    return PurePath(name).stem.lower()


def _normalize_path(value: str) -> str:
    return str(value or "").replace("\\", "/").strip().strip("/")


def _file_stem_tokens(stem: str) -> list[str]:
    tokens: list[str] = []
    for token in re.findall(r"[\w가-힣]+", stem.lower()):
        if len(token) < 3:
            continue
        if re.fullmatch(r"\d{4}", token):
            continue
        if token not in tokens:
            tokens.append(token)
    return tokens[:8]


def _normalize_case_number(value: str) -> str:
    normalized = re.sub(r"\s+", "", str(value or ""))
    return normalized.lower()


def _normalize_label(value: str) -> str:
    normalized = re.sub(r"\s+", "", str(value or "")).lower()
    return normalized[:120]


def _has_key(row: Any, key: str) -> bool:
    try:
        return key in row.keys()
    except AttributeError:
        return False


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
            (table_name,),
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    return row is not None
