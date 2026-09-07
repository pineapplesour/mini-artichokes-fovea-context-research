"""Judge extraction, disambiguation, and profile API.

Pipeline:
  1) Extract `(name, hanja, role, prefix)` from each precedent's tail text.
  2) Cluster appearances into instances using
       (name, court, decision_date_window) → judge_instance_id
     and merge instances across adjacent periods that look like rotations.
  3) Serve API: judge search, profile, "predict ruling" RAG-restricted, reviews.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

NON_NAME_TOKENS = {
    "재판장", "주심", "대법관", "판사", "대리판사", "판사장", "대법원판사",
    "고등판사", "지방판사", "변호인", "변호사", "검사", "피고인", "원고",
    "피고", "관여", "담당변호사", "주임검사", "재판부", "판결선고", "담당부장",
    "대법원장", "법원장", "부장판사", "수석부장판사", "소장", "의장",
    "서기관", "서기", "주사", "실무관", "주사보", "법무사", "담당", "주임",
    "집행관", "간사", "서명", "날인", "심리원", "회의원", "청구인", "신청인",
    "항고인", "상고인", "항소인", "심판원", "재판부원", "법원사무관",
    "법원주사", "법원주사보", "법무관",
}
NAME_TOKEN_RE = re.compile(r"^([가-힣]{2,4})(?:\(([^)]{0,50})\))?$")
HEADER_RE = re.compile(
    r"(?:^|[\n\r]|<br/>|<br />)\s*"
    r"(대법관|대법원판사|판사|재판장\s*판사|재판장\s*대법관|판사장|고등판사|지방판사)"
    r"\s+([가-힣()\s,，·]{2,400})"
)


def _parse_name_block(prefix: str, blob: str) -> list[dict[str, str]]:
    blob = re.sub(r"[,，·]", " ", blob)
    tokens = blob.split()
    out: list[dict[str, str]] = []
    current_role: str | None = None
    if "재판장" in prefix:
        current_role = "재판장"
    expecting_first = True
    for raw in tokens:
        raw = raw.strip(".,;:·")
        if not raw:
            continue
        if raw in ("재판장", "주심"):
            current_role = raw
            continue
        if raw in ("대법관", "판사", "대리판사", "판사장", "대법원판사", "고등판사", "지방판사"):
            prefix = raw
            if raw == "대리판사":
                current_role = "대리판사"
            continue
        m = NAME_TOKEN_RE.match(raw)
        if not m:
            break
        name = m.group(1)
        paren = m.group(2) or ""
        if name in NON_NAME_TOKENS:
            continue
        role = current_role
        if not role and paren:
            if "재판장" in paren:
                role = "재판장"
            elif "주심" in paren:
                role = "주심"
        if not role:
            role = "재판장" if expecting_first else "판사"
        hanja = ""
        if paren and re.match(r"^[\u4e00-\u9fff]{1,6}$", paren.strip()):
            hanja = paren.strip()
        out.append({"name": name, "hanja": hanja, "role": role, "prefix": prefix})
        expecting_first = False
        current_role = None
    return out


def extract_judges(full_text: str) -> list[dict[str, str]]:
    """Return list of {name, hanja, role, prefix} extracted from a precedent."""
    text = full_text or ""
    tail = text[-5000:]
    found: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for m in HEADER_RE.finditer(tail):
        prefix = m.group(1).strip()
        blob = m.group(2)
        for entry in _parse_name_block(prefix, blob):
            key = (entry["name"], entry["hanja"])
            if key in seen:
                continue
            seen.add(key)
            found.append(entry)
    return found


# ---------------------------------------------------------------------------
# Database schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS judge_appearances (
    appearance_id TEXT PRIMARY KEY,
    canonical_id  TEXT NOT NULL,
    case_number   TEXT,
    court         TEXT NOT NULL,
    decision_date TEXT,
    decision_year INTEGER,
    name          TEXT NOT NULL,
    hanja         TEXT,
    role          TEXT,
    prefix        TEXT,
    judge_id      TEXT
);
CREATE INDEX IF NOT EXISTS idx_app_name        ON judge_appearances(name);
CREATE INDEX IF NOT EXISTS idx_app_court_year  ON judge_appearances(court, decision_year);
CREATE INDEX IF NOT EXISTS idx_app_judge       ON judge_appearances(judge_id);
CREATE INDEX IF NOT EXISTS idx_app_canonical   ON judge_appearances(canonical_id);

CREATE TABLE IF NOT EXISTS judges (
    judge_id      TEXT PRIMARY KEY,
    primary_name  TEXT NOT NULL,
    hanja_name    TEXT,
    cluster_method TEXT NOT NULL,
    appearance_count INTEGER NOT NULL,
    first_seen    TEXT,
    last_seen     TEXT,
    courts        TEXT,
    created_at    REAL
);
CREATE INDEX IF NOT EXISTS idx_judges_name ON judges(primary_name);

CREATE TABLE IF NOT EXISTS judge_summaries (
    judge_id      TEXT PRIMARY KEY,
    summary       TEXT NOT NULL,
    samples_used  INTEGER NOT NULL,
    total_cases   INTEGER NOT NULL,
    generated_by  TEXT,
    created_at    REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS judge_reviews (
    review_id     TEXT PRIMARY KEY,
    judge_id      TEXT NOT NULL,
    rating        INTEGER NOT NULL,
    body          TEXT NOT NULL,
    anon_token    TEXT NOT NULL,
    created_at    REAL NOT NULL,
    status        TEXT NOT NULL DEFAULT 'approved',
    UNIQUE(judge_id, anon_token)
);
CREATE INDEX IF NOT EXISTS idx_reviews_judge ON judge_reviews(judge_id);
"""


def open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Build pipeline
# ---------------------------------------------------------------------------

def _decision_year(value: str) -> int:
    if not value:
        return 0
    m = re.search(r"(19|20)\d{2}", value)
    if not m:
        return 0
    year = int(m.group(0))
    # Guard against OCR garbage (e.g. 2079, 9997) and pre-modern dates.
    if year < 1948 or year > 2030:
        return 0
    return year


# Court name normalization to merge spelling variants.
COURT_ALIASES: dict[str, str] = {
    "서울중앙지법": "서울중앙지방법원",
    "서울지법": "서울지방법원",
    "서울남부지법": "서울남부지방법원",
    "서울동부지법": "서울동부지방법원",
    "서울북부지법": "서울북부지방법원",
    "서울서부지법": "서울서부지방법원",
    "서울민사지법": "서울중앙지방법원",
    "서울형사지법": "서울중앙지방법원",
    "서울고법": "서울고등법원",
    "부산지법": "부산지방법원",
    "부산고법": "부산고등법원",
    "대구지법": "대구지방법원",
    "대구고법": "대구고등법원",
    "광주지법": "광주지방법원",
    "광주고법": "광주고등법원",
    "대전지법": "대전지방법원",
    "대전고법": "대전고등법원",
    "수원지법": "수원지방법원",
    "수원고법": "수원고등법원",
    "인천지법": "인천지방법원",
    "의정부지법": "의정부지방법원",
    "춘천지법": "춘천지방법원",
    "전주지법": "전주지방법원",
    "청주지법": "청주지방법원",
    "창원지법": "창원지방법원",
    "울산지법": "울산지방법원",
    "제주지법": "제주지방법원",
    "마산지법": "창원지방법원",  # historical (마산지법 → 창원지법 통합 2010)
    "서울가법": "서울가정법원",
    "서울행법": "서울행정법원",
    "특허법원": "특허법원",
}


def _normalize_court(name: str) -> str:
    """Normalize court spelling AND strip 지원/시기 details so the same physical
    court (e.g. 의정부지방법원 vs 의정부지방법원 고양지원) groups together for the
    purposes of judge-instance merging. The original full string is still saved
    on each appearance row; this normalization is only used as a disambiguation
    key when clustering."""
    raw = (name or "").strip()
    if raw in COURT_ALIASES:
        return COURT_ALIASES[raw]
    return raw


def _court_root(name: str) -> str:
    """Strip "OO지원", "제O민사부" etc. so a judge moving between the head court
    and one of its branches doesn't get split into two instances."""
    raw = _normalize_court(name)
    for sep in (" ", "  "):
        idx = raw.find(sep)
        if idx > 0:
            return raw[:idx]
    return raw


def populate_appearances(judges_db: sqlite3.Connection, precedents_db_path: Path, *, batch_size: int = 5000) -> dict[str, int]:
    """Scan precedents.sqlite3 and write judge_appearances rows."""
    src = sqlite3.connect(str(precedents_db_path))
    cur = judges_db.cursor()
    cur.execute("DELETE FROM judge_appearances")
    judges_db.commit()
    n_total = 0
    n_with_judge = 0
    n_appearances = 0
    rows_buffer: list[tuple] = []
    for canonical_id, case_number, court, decision_date, full_text in src.execute(
        "SELECT canonical_id, case_number, court, decision_date, full_text FROM precedents"
    ):
        n_total += 1
        if not court:
            continue
        appearances = extract_judges(full_text or "")
        if not appearances:
            continue
        n_with_judge += 1
        year = _decision_year(decision_date or case_number or "")
        normalized_court = _normalize_court(court)
        for entry in appearances:
            n_appearances += 1
            rows_buffer.append((
                f"app-{uuid.uuid4().hex[:14]}",
                canonical_id,
                case_number or "",
                normalized_court,
                decision_date or "",
                year,
                entry["name"],
                entry["hanja"],
                entry["role"],
                entry["prefix"],
                None,  # judge_id assigned in clustering pass
            ))
            if len(rows_buffer) >= batch_size:
                cur.executemany(
                    "INSERT INTO judge_appearances VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    rows_buffer,
                )
                judges_db.commit()
                rows_buffer.clear()
    if rows_buffer:
        cur.executemany(
            "INSERT INTO judge_appearances VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            rows_buffer,
        )
        judges_db.commit()
    src.close()
    return {"precedents_scanned": n_total, "with_judge": n_with_judge, "appearances": n_appearances}


def cluster_judges(judges_db: sqlite3.Connection) -> dict[str, int]:
    """Group appearances into judge instances.

    Algorithm (heuristic for Korean judiciary):
      Group all appearances by `name`. Within a name group, sort by
      `decision_year`. Walk through years; for each year, partition appearances
      by `court`. Two same-name appearances belong to the same judge instance
      iff:
        - same court within ±2 years, OR
        - different courts but year_b - year_a <= 1 (likely transfer at the
          Feb rotation; only one instance can move that fast).
      If two distinct courts appear in the *same* year, treat as separate
      judge instances (impossible for one person to sit in two courts).
    """
    cur = judges_db.cursor()
    cur.execute("DELETE FROM judges")
    cur.execute("UPDATE judge_appearances SET judge_id = NULL")
    judges_db.commit()

    rows = cur.execute(
        "SELECT appearance_id, name, hanja, court, decision_year FROM judge_appearances ORDER BY name, decision_year"
    ).fetchall()
    by_name: dict[str, list[tuple]] = defaultdict(list)
    for row in rows:
        by_name[row[1]].append(row)

    assignments: list[tuple[str, str]] = []  # (appearance_id, judge_id)
    judge_records: list[tuple] = []
    now = time.time()

    for name, items in by_name.items():
        # Sort by year then court for deterministic clustering
        items.sort(key=lambda r: (r[4] or 0, r[3] or ""))
        clusters: list[list[tuple]] = []
        for row in items:
            year = row[4] or 0
            court_root = _court_root(row[3] or "")
            placed = False
            for cluster in clusters:
                last = cluster[-1]
                last_year = last[4] or 0
                last_court_root = _court_root(last[3] or "")
                year_gap = year - last_year if year and last_year else 999
                # Career cap relaxed to 45 years (covers 대법관 long careers).
                first_year = cluster[0][4] or 0
                if year and first_year and (year - first_year) > 45:
                    continue
                # Same court root → same person; allow up to 40y gap (covers
                # full career returns). When either year is missing (year_gap = 999)
                # also absorb because we have no signal to split on.
                if court_root and court_root == last_court_root and (year_gap <= 40 or year_gap == 999):
                    cluster.append(row)
                    placed = True
                    break
                # Different court same year → impossible for one person to sit at two
                # courts simultaneously; treat as separate.
                if court_root and last_court_root and court_root != last_court_root and year_gap == 0:
                    continue
                # Different court within 6 years → rotation/leave (covers 휴직 + 복귀).
                if court_root and last_court_root and court_root != last_court_root and 1 <= year_gap <= 6:
                    cluster.append(row)
                    placed = True
                    break
                # Different court but big gap (career return) — still likely same.
                if court_root and last_court_root and court_root != last_court_root and 7 <= year_gap <= 15:
                    cluster.append(row)
                    placed = True
                    break
            if not placed:
                clusters.append([row])

        # Second pass: merge clusters whose hanja matches and time-spans are adjacent.
        merged_clusters: list[list[tuple]] = []
        for cluster in clusters:
            absorbed = False
            cluster_hanjas = {r[2] for r in cluster if r[2]}
            cluster_min = min((r[4] or 0) for r in cluster)
            cluster_max = max((r[4] or 0) for r in cluster)
            for existing in merged_clusters:
                existing_hanjas = {r[2] for r in existing if r[2]}
                # If both clusters specify hanja and they conflict, skip.
                if cluster_hanjas and existing_hanjas and cluster_hanjas.isdisjoint(existing_hanjas):
                    continue
                ex_min = min((r[4] or 0) for r in existing)
                ex_max = max((r[4] or 0) for r in existing)
                # Combined time range must still be <= 45 years.
                combined_min = min(cluster_min, ex_min) if cluster_min and ex_min else max(cluster_min, ex_min)
                combined_max = max(cluster_max, ex_max)
                if combined_min and combined_max and (combined_max - combined_min) > 45:
                    continue
                # Time spans overlap or are within 8 years apart.
                gap = max(0, max(cluster_min, ex_min) - min(cluster_max, ex_max)) if cluster_min and ex_min and cluster_max and ex_max else 999
                if gap <= 8:
                    existing.extend(cluster)
                    absorbed = True
                    break
            if not absorbed:
                merged_clusters.append(cluster)
        clusters = merged_clusters

        for cluster in clusters:
            judge_id = f"j-{hashlib.sha1(f'{name}|{cluster[0][0]}'.encode()).hexdigest()[:14]}"
            hanja_candidates = [r[2] for r in cluster if r[2]]
            hanja = max(set(hanja_candidates), key=hanja_candidates.count) if hanja_candidates else ""
            courts = sorted({r[3] for r in cluster if r[3]})
            years = [r[4] for r in cluster if r[4]]
            first_seen = str(min(years)) if years else ""
            last_seen = str(max(years)) if years else ""
            judge_records.append((
                judge_id, name, hanja, "auto_temporal_court",
                len(cluster), first_seen, last_seen,
                json.dumps(courts, ensure_ascii=False), now,
            ))
            for row in cluster:
                assignments.append((row[0], judge_id))

    cur.executemany("INSERT INTO judges VALUES (?,?,?,?,?,?,?,?,?)", judge_records)
    cur.executemany("UPDATE judge_appearances SET judge_id = ? WHERE appearance_id = ?",
                    [(jid, aid) for aid, jid in assignments])
    judges_db.commit()
    return {"unique_judges": len(judge_records), "assigned_appearances": len(assignments)}


# ---------------------------------------------------------------------------
# Query API
# ---------------------------------------------------------------------------

class JudgeStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn = open_db(db_path)
        self._lock = threading.Lock()

    def conn(self) -> sqlite3.Connection:
        return self._conn

    def search_judges(self, query: str = "", limit: int = 30) -> list[dict[str, Any]]:
        q = (query or "").strip()
        with self._lock:
            cur = self._conn.cursor()
            if q:
                rows = cur.execute(
                    """
                    SELECT judge_id, primary_name, hanja_name, appearance_count,
                           first_seen, last_seen, courts
                    FROM judges
                    WHERE primary_name LIKE ? OR hanja_name LIKE ?
                    ORDER BY appearance_count DESC
                    LIMIT ?
                    """,
                    (f"%{q}%", f"%{q}%", int(limit)),
                ).fetchall()
            else:
                rows = cur.execute(
                    """
                    SELECT judge_id, primary_name, hanja_name, appearance_count,
                           first_seen, last_seen, courts
                    FROM judges
                    ORDER BY appearance_count DESC
                    LIMIT ?
                    """,
                    (int(limit),),
                ).fetchall()
        return [
            {
                "judgeId": r[0],
                "name": r[1],
                "hanja": r[2] or "",
                "appearanceCount": r[3],
                "firstSeen": r[4],
                "lastSeen": r[5],
                "courts": json.loads(r[6] or "[]"),
            }
            for r in rows
        ]

    def get_judge(self, judge_id: str) -> dict[str, Any] | None:
        with self._lock:
            cur = self._conn.cursor()
            row = cur.execute(
                """
                SELECT judge_id, primary_name, hanja_name, appearance_count,
                       first_seen, last_seen, courts, cluster_method
                FROM judges WHERE judge_id = ?
                """,
                (judge_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "judgeId": row[0],
            "name": row[1],
            "hanja": row[2] or "",
            "appearanceCount": row[3],
            "firstSeen": row[4],
            "lastSeen": row[5],
            "courts": json.loads(row[6] or "[]"),
            "clusterMethod": row[7],
        }

    def list_career(self, judge_id: str) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            rows = cur.execute(
                """
                SELECT court, decision_year, COUNT(*) as n, role
                FROM judge_appearances WHERE judge_id = ?
                GROUP BY court, decision_year, role
                ORDER BY decision_year DESC, court
                """,
                (judge_id,),
            ).fetchall()
        return [
            {"court": r[0], "year": r[1], "count": r[2], "role": r[3]}
            for r in rows
        ]

    def list_cases(self, judge_id: str, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self._lock:
            cur = self._conn.cursor()
            total = cur.execute(
                "SELECT COUNT(*) FROM judge_appearances WHERE judge_id = ?",
                (judge_id,),
            ).fetchone()[0]
            rows = cur.execute(
                """
                SELECT canonical_id, case_number, court, decision_date, role
                FROM judge_appearances
                WHERE judge_id = ?
                ORDER BY decision_year DESC, decision_date DESC
                LIMIT ? OFFSET ?
                """,
                (judge_id, int(limit), int(offset)),
            ).fetchall()
        return {
            "total": int(total),
            "offset": int(offset),
            "limit": int(limit),
            "cases": [
                {
                    "canonicalId": r[0],
                    "caseNumber": r[1],
                    "court": r[2],
                    "decisionDate": r[3],
                    "role": r[4],
                }
                for r in rows
            ],
        }

    def get_summary(self, judge_id: str) -> dict[str, Any] | None:
        with self._lock:
            cur = self._conn.cursor()
            row = cur.execute(
                "SELECT summary, samples_used, total_cases, created_at, generated_by FROM judge_summaries WHERE judge_id = ?",
                (judge_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "summary": row[0],
            "samplesUsed": row[1],
            "totalCases": row[2],
            "createdAt": row[3],
            "generatedBy": row[4] or "",
        }

    def save_summary(self, judge_id: str, summary: str, samples_used: int, total_cases: int, generated_by: str = "") -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "INSERT OR REPLACE INTO judge_summaries (judge_id, summary, samples_used, total_cases, generated_by, created_at) VALUES (?,?,?,?,?,?)",
                (judge_id, summary, int(samples_used), int(total_cases), generated_by or "", time.time()),
            )
            self._conn.commit()

    def case_canonical_ids(self, judge_id: str, limit: int = 1000) -> list[str]:
        with self._lock:
            cur = self._conn.cursor()
            rows = cur.execute(
                "SELECT DISTINCT canonical_id FROM judge_appearances WHERE judge_id = ? LIMIT ?",
                (judge_id, int(limit)),
            ).fetchall()
        return [r[0] for r in rows if r[0]]

    # Reviews ------------------------------------------------------------
    def add_review(self, judge_id: str, rating: int, body: str, anon_token: str) -> dict[str, Any]:
        rating = max(1, min(5, int(rating)))
        body = (body or "").strip()
        if len(body) < 5:
            raise ValueError("review body too short")
        if len(body) > 2000:
            raise ValueError("review body too long")
        review_id = f"rv-{uuid.uuid4().hex[:14]}"
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "INSERT OR REPLACE INTO judge_reviews (review_id, judge_id, rating, body, anon_token, created_at, status) "
                "VALUES (?,?,?,?,?,?,?)",
                (review_id, judge_id, rating, body, anon_token, time.time(), "approved"),
            )
            self._conn.commit()
        return {"reviewId": review_id, "judgeId": judge_id, "rating": rating, "body": body}

    def list_reviews(self, judge_id: str, limit: int = 50) -> dict[str, Any]:
        with self._lock:
            cur = self._conn.cursor()
            rows = cur.execute(
                "SELECT review_id, rating, body, created_at FROM judge_reviews "
                "WHERE judge_id = ? AND status = 'approved' ORDER BY created_at DESC LIMIT ?",
                (judge_id, int(limit)),
            ).fetchall()
            agg = cur.execute(
                "SELECT AVG(rating), COUNT(*) FROM judge_reviews WHERE judge_id = ? AND status = 'approved'",
                (judge_id,),
            ).fetchone()
        return {
            "reviews": [
                {"reviewId": r[0], "rating": r[1], "body": r[2], "createdAt": r[3]}
                for r in rows
            ],
            "averageRating": float(agg[0]) if agg and agg[0] is not None else 0.0,
            "reviewCount": int(agg[1] or 0),
        }


def hash_anon_token(client_id: str, judge_id: str, salt: str) -> str:
    digest = hashlib.sha256(f"{client_id}|{judge_id}|{salt}".encode("utf-8")).hexdigest()
    return digest[:32]
