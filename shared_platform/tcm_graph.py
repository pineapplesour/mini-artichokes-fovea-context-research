from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any


FETCH_BATCH_SIZE = 500
SEED_LIMIT = 80
MAX_NEIGHBOR_RADIUS = 8


@dataclass(frozen=True)
class TcmPassageLocation:
    passage_id: str
    source_id: str
    parent_ref: str
    ref_sort: int


def expand_tcm_passage_graph_rows(
    conn: sqlite3.Connection,
    seed_rows: list[sqlite3.Row],
    *,
    seed_scores: dict[str, float],
    max_neighbors: int = 24,
    max_expanded: int = 120,
) -> tuple[list[sqlite3.Row], dict[str, float]]:
    """Expand TCM precedent chunks through adjacent passage graph edges.

    The TCM corpus stores one precedent row per passage chunk, plus a richer
    passages table keyed by source_id/ref_sort. Adjacent chunks often carry the
    missing context needed by beta6, while metadata equality groups are too large
    to materialize safely for this corpus.
    """

    if not seed_rows:
        return [], {}
    seed_ids = _ordered_seed_ids(seed_rows, seed_scores)
    if not seed_ids:
        return [], {}
    try:
        locations = _fetch_tcm_passage_locations(conn, seed_ids)
    except sqlite3.OperationalError:
        return [], {}
    if not locations:
        return [], {}

    seed_keys = set(seed_ids)
    seed_keys.update(_passage_id_from_canonical_id(source_id) for source_id in seed_ids)
    relation_scores: dict[str, float] = {}
    target_ids: list[str] = []
    radius = _neighbor_radius(max_neighbors)
    per_seed_limit = max(1, min(max_neighbors, radius * 2, 16))
    seed_rank_weight = {source_id: max(0.25, 1.0 - (index * 0.015)) for index, source_id in enumerate(seed_ids)}

    try:
        for source_id in seed_ids:
            location = locations.get(source_id) or locations.get(_passage_id_from_canonical_id(source_id))
            if location is None:
                continue
            for neighbor in _fetch_tcm_neighbors(conn, location, radius=radius, limit=per_seed_limit):
                passage_id = str(neighbor["passage_id"] or "")
                target_id = _canonical_id_for_passage_id(passage_id)
                if not passage_id or target_id in seed_keys or passage_id in seed_keys:
                    continue
                distance = abs(int(neighbor["ref_sort"] or 0) - location.ref_sort)
                weight = _neighbor_weight(distance, location.parent_ref, str(neighbor["parent_ref"] or ""))
                seed_score = max(1.0, float(seed_scores.get(source_id) or 1.0))
                score = seed_score * weight * seed_rank_weight.get(source_id, 0.25)
                if score <= 0:
                    continue
                if target_id not in relation_scores:
                    target_ids.append(target_id)
                relation_scores[target_id] = max(relation_scores.get(target_id, 0.0), score)
                relation_scores[passage_id] = max(relation_scores.get(passage_id, 0.0), score)
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
        rows_by_id.values(),
        key=lambda row: (-_relation_score_for_row(row, relation_scores), str(row["canonical_id"] or "")),
    )
    return ordered[:max_expanded], relation_scores


def _ordered_seed_ids(seed_rows: list[sqlite3.Row], seed_scores: dict[str, float]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for row in seed_rows:
        canonical_id = str(row["canonical_id"] or "")
        if canonical_id and canonical_id not in seen:
            seen.add(canonical_id)
            ids.append(canonical_id)
    return sorted(ids, key=lambda source_id: (-seed_scores.get(source_id, 0.0), source_id))[:SEED_LIMIT]


def _fetch_tcm_passage_locations(
    conn: sqlite3.Connection,
    canonical_ids: list[str],
) -> dict[str, TcmPassageLocation]:
    passage_ids = list(dict.fromkeys(_passage_id_from_canonical_id(source_id) for source_id in canonical_ids))
    out: dict[str, TcmPassageLocation] = {}
    for offset in range(0, len(passage_ids), FETCH_BATCH_SIZE):
        batch = passage_ids[offset : offset + FETCH_BATCH_SIZE]
        if not batch:
            continue
        placeholders = ",".join("?" for _ in batch)
        rows = conn.execute(
            f"""
            SELECT passage_id, source_id, parent_ref, ref_sort
            FROM passages
            WHERE passage_id IN ({placeholders})
            """,
            batch,
        ).fetchall()
        for row in rows:
            location = TcmPassageLocation(
                passage_id=str(row["passage_id"] or ""),
                source_id=str(row["source_id"] or ""),
                parent_ref=str(row["parent_ref"] or ""),
                ref_sort=int(row["ref_sort"] or 0),
            )
            if not location.passage_id or not location.source_id:
                continue
            out[location.passage_id] = location
            out[_canonical_id_for_passage_id(location.passage_id)] = location
    return out


def _fetch_tcm_neighbors(
    conn: sqlite3.Connection,
    location: TcmPassageLocation,
    *,
    radius: int,
    limit: int,
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT passage_id, source_id, parent_ref, ref_sort
        FROM passages
        WHERE source_id = ?
          AND ref_sort BETWEEN ? AND ?
          AND passage_id != ?
        ORDER BY ABS(ref_sort - ?), ref_sort
        LIMIT ?
        """,
        (
            location.source_id,
            location.ref_sort - radius,
            location.ref_sort + radius,
            location.passage_id,
            location.ref_sort,
            max(1, limit),
        ),
    ).fetchall()


def _fetch_precedent_rows_by_ids(conn: sqlite3.Connection, ids: list[str]) -> dict[str, sqlite3.Row]:
    candidate_ids: list[str] = []
    for source_id in ids:
        _append_unique(candidate_ids, source_id)
        passage_id = _passage_id_from_canonical_id(source_id)
        _append_unique(candidate_ids, passage_id)
        _append_unique(candidate_ids, _canonical_id_for_passage_id(passage_id))
    rows: list[sqlite3.Row] = []
    try:
        for offset in range(0, len(candidate_ids), FETCH_BATCH_SIZE):
            batch = candidate_ids[offset : offset + FETCH_BATCH_SIZE]
            if not batch:
                continue
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


def _relation_score_for_row(row: sqlite3.Row, relation_scores: dict[str, float]) -> float:
    canonical_id = str(row["canonical_id"] or "")
    return max(
        relation_scores.get(canonical_id, 0.0),
        relation_scores.get(_passage_id_from_canonical_id(canonical_id), 0.0),
    )


def _neighbor_radius(max_neighbors: int) -> int:
    return max(1, min(MAX_NEIGHBOR_RADIUS, max(2, int(max_neighbors or 1) // 4)))


def _neighbor_weight(distance: int, parent_ref: str, target_parent_ref: str) -> float:
    bounded_distance = max(1, int(distance or 1))
    weight = 0.78 - (bounded_distance * 0.055)
    if parent_ref and parent_ref == target_parent_ref:
        weight += 0.08
    return max(0.35, min(weight, 0.86))


def _passage_id_from_canonical_id(canonical_id: str) -> str:
    value = str(canonical_id or "").strip()
    return value[4:] if value.startswith("doc.") else value


def _canonical_id_for_passage_id(passage_id: str) -> str:
    value = str(passage_id or "").strip()
    if not value or value.startswith("doc."):
        return value
    return f"doc.{value}"


def _append_unique(values: list[str], value: Any) -> None:
    normalized = str(value or "").strip()
    if normalized and normalized not in values:
        values.append(normalized)
