from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class EventFrame:
    actor_class: str = ""
    action_class: str = ""
    object_class: str = ""
    method_class: str = ""
    issue_tags: tuple[str, ...] = ()
    outcome: str = "NONE"


@dataclass(frozen=True)
class TaxonomyNode:
    node_id: str
    parent_id: str
    slot: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class StoredEventFrame:
    frame_id: str
    doc_id: str
    chunk_id: str
    frame: EventFrame
    text: str = ""


@dataclass(frozen=True)
class FrameMatch:
    frame: StoredEventFrame
    score: float
    edge_type: str
    path_reason: str


class LegalTaxonomy:
    def __init__(self, nodes: list[TaxonomyNode]):
        self.nodes = {node.node_id: node for node in nodes}
        self.aliases: list[tuple[str, str, str]] = []
        for node in nodes:
            for alias in node.aliases:
                cleaned = alias.strip().lower()
                if cleaned:
                    self.aliases.append((node.slot, cleaned, node.node_id))
        self.aliases.sort(key=lambda item: len(item[1]), reverse=True)

    @classmethod
    def default(cls) -> "LegalTaxonomy":
        return cls(
            [
                TaxonomyNode("LEGAL", "", "root"),
                TaxonomyNode("LEGAL/STATE_ACTOR", "LEGAL", "actor"),
                TaxonomyNode("LEGAL/STATE_ACTOR/INVESTIGATIVE", "LEGAL/STATE_ACTOR", "actor", ("수사기관",)),
                TaxonomyNode("LEGAL/STATE_ACTOR/INVESTIGATIVE/POLICE", "LEGAL/STATE_ACTOR/INVESTIGATIVE", "actor", ("경찰", "사법경찰관", "수사관")),
                TaxonomyNode("LEGAL/STATE_ACTOR/INVESTIGATIVE/PROSECUTOR", "LEGAL/STATE_ACTOR/INVESTIGATIVE", "actor", ("검찰", "검사", "검찰청")),
                TaxonomyNode("LEGAL/STATE_ACTOR/MILITARY", "LEGAL/STATE_ACTOR", "actor", ("군", "군대", "군부대")),
                TaxonomyNode("LEGAL/STATE_ACTOR/MILITARY/UNIT", "LEGAL/STATE_ACTOR/MILITARY", "actor", ("부대", "공군 부대", "군부대")),
                TaxonomyNode("LEGAL/PERSON", "LEGAL", "actor"),
                TaxonomyNode("LEGAL/PERSON/SOLDIER", "LEGAL/PERSON", "actor", ("군인", "장병")),
                TaxonomyNode("LEGAL/ACTION", "LEGAL", "action"),
                TaxonomyNode("LEGAL/ACTION/ELECTRONIC_ACCESS", "LEGAL/ACTION", "action", ("전자정보 접근", "계정 접근")),
                TaxonomyNode("LEGAL/ACTION/ELECTRONIC_ACCESS/SIM_CONTROL", "LEGAL/ACTION/ELECTRONIC_ACCESS", "action", ("유심 분리", "유심 제거", "유심 뽑음", "유심 압수", "가입자식별모듈 제거")),
                TaxonomyNode("LEGAL/ACTION/ELECTRONIC_ACCESS/ACCOUNT_LOGIN", "LEGAL/ACTION/ELECTRONIC_ACCESS", "action", ("로그인", "계정 접속", "메신저 접속")),
                TaxonomyNode("LEGAL/ACTION/ELECTRONIC_ACCESS/ACCOUNT_LOGIN/SIM_REINSERT_LOGIN", "LEGAL/ACTION/ELECTRONIC_ACCESS/ACCOUNT_LOGIN", "action", ("유심 공기계 로그인", "유심 로그인", "유심 재삽입 로그인", "가입자식별모듈 로그인")),
                TaxonomyNode("LEGAL/ACTION/ELECTRONIC_ACCESS/ACCOUNT_LOGIN/PASSWORD_BYPASS", "LEGAL/ACTION/ELECTRONIC_ACCESS/ACCOUNT_LOGIN", "action", ("비밀번호 해킹", "비밀번호 우회", "비번 우회", "패턴 우회", "잠금해제", "해킹")),
                TaxonomyNode("LEGAL/ACTION/SECURITY_MANAGEMENT", "LEGAL/ACTION", "action", ("보안 관리",)),
                TaxonomyNode("LEGAL/ACTION/SECURITY_MANAGEMENT/KEY_CUSTODY", "LEGAL/ACTION/SECURITY_MANAGEMENT", "action", ("열쇠 보관", "키 관리", "열쇠 관리", "인계 점검")),
                TaxonomyNode("LEGAL/ACTION/MEDICAL_BODY", "LEGAL/ACTION", "action", ("신체",)),
                TaxonomyNode("LEGAL/ACTION/MEDICAL_BODY/GROWTH", "LEGAL/ACTION/MEDICAL_BODY", "action", ("신체 성장", "키 성장", "성장")),
                TaxonomyNode("LEGAL/OBJECT", "LEGAL", "object"),
                TaxonomyNode("LEGAL/OBJECT/COMM", "LEGAL/OBJECT", "object", ("통신", "전자통신")),
                TaxonomyNode("LEGAL/OBJECT/COMM/MESSENGER", "LEGAL/OBJECT/COMM", "object", ("메신저", "대화방")),
                TaxonomyNode("LEGAL/OBJECT/COMM/MESSENGER/KAKAOTALK", "LEGAL/OBJECT/COMM/MESSENGER", "object", ("카카오톡", "카톡")),
                TaxonomyNode("LEGAL/OBJECT/COMM/MESSENGER/TELEGRAM", "LEGAL/OBJECT/COMM/MESSENGER", "object", ("텔레그램",)),
                TaxonomyNode("LEGAL/OBJECT/COMM/SIM", "LEGAL/OBJECT/COMM", "object", ("유심", "유심칩", "usim", "sim", "가입자식별모듈", "가입자 식별 모듈")),
                TaxonomyNode("LEGAL/OBJECT/SECURITY", "LEGAL/OBJECT", "object", ("보안구역",)),
                TaxonomyNode("LEGAL/OBJECT/SECURITY/KEY", "LEGAL/OBJECT/SECURITY", "object", ("열쇠", "출입키", "탄약고 열쇠", "무기고 열쇠")),
                TaxonomyNode("LEGAL/OBJECT/BODY", "LEGAL/OBJECT", "object", ("신체",)),
                TaxonomyNode("LEGAL/OBJECT/BODY/HEIGHT", "LEGAL/OBJECT/BODY", "object", ("신장", "키 성장", "체격", "height")),
                TaxonomyNode("LEGAL/OBJECT/BODY/KIDNEY", "LEGAL/OBJECT/BODY", "object", ("콩팥",)),
                TaxonomyNode("LEGAL/METHOD", "LEGAL", "method"),
                TaxonomyNode("LEGAL/METHOD/TECHNICAL_ACCESS", "LEGAL/METHOD", "method", ("기술적 접근",)),
                TaxonomyNode("LEGAL/METHOD/TECHNICAL_ACCESS/SIM_CONTROL", "LEGAL/METHOD/TECHNICAL_ACCESS", "method", ("유심 분리", "유심 제거", "유심 뽑음", "유심 압수", "가입자식별모듈 제거")),
                TaxonomyNode("LEGAL/METHOD/TECHNICAL_ACCESS/SIM_REINSERTION", "LEGAL/METHOD/TECHNICAL_ACCESS", "method", ("유심 재삽입", "공기계", "인증번호", "가입자식별모듈 재삽입")),
                TaxonomyNode("LEGAL/METHOD/TECHNICAL_ACCESS/PASSWORD_BYPASS", "LEGAL/METHOD/TECHNICAL_ACCESS", "method", ("비밀번호 우회", "비밀번호 해킹", "비번 우회", "패턴 우회", "잠금해제", "해킹")),
                TaxonomyNode("LEGAL/METHOD/SECURITY_CONTROL", "LEGAL/METHOD", "method", ("보안통제",)),
                TaxonomyNode("LEGAL/METHOD/SECURITY_CONTROL/SEPARATED_CUSTODY", "LEGAL/METHOD/SECURITY_CONTROL", "method", ("분리 관리", "이원화", "인계", "점검")),
            ]
        )

    def resolve(self, value: str, *, slot: str) -> str:
        haystack = str(value or "").strip().lower()
        if not haystack:
            return ""
        if haystack in self.nodes and self.nodes[haystack].slot == slot:
            return haystack
        for alias_slot, alias, node_id in self.aliases:
            if alias_slot == slot and alias in haystack:
                return node_id
        return ""

    def ancestors(self, node_id: str) -> list[str]:
        out: list[str] = []
        current = str(node_id or "")
        while current and current in self.nodes:
            out.append(current)
            current = self.nodes[current].parent_id
        return out

    def tax_sim(self, left: str, right: str) -> float:
        if not left or not right:
            return 0.0
        if left == right:
            return 1.0
        left_ancestors = self.ancestors(left)
        right_ancestors = self.ancestors(right)
        if not left_ancestors or not right_ancestors:
            return 0.0
        right_depth = {node_id: len(right_ancestors) - index for index, node_id in enumerate(right_ancestors)}
        best_depth = 0
        for index, node_id in enumerate(left_ancestors):
            if node_id in right_depth:
                best_depth = min(len(left_ancestors) - index, right_depth[node_id])
                break
        if best_depth <= 2:
            return 0.0
        left_depth = len(left_ancestors)
        right_depth_value = len(right_ancestors)
        return (2.0 * best_depth) / float(left_depth + right_depth_value)


def frame_sim(left: EventFrame, right: EventFrame, taxonomy: LegalTaxonomy) -> float:
    issue_score = _issue_sim(left.issue_tags, right.issue_tags)
    return (
        0.20 * taxonomy.tax_sim(left.actor_class, right.actor_class)
        + 0.25 * taxonomy.tax_sim(left.action_class, right.action_class)
        + 0.20 * taxonomy.tax_sim(left.object_class, right.object_class)
        + 0.10 * taxonomy.tax_sim(left.method_class, right.method_class)
        + 0.25 * issue_score
    )


def rank_analogous_frames(
    query: str,
    candidates: list[StoredEventFrame],
    *,
    taxonomy: LegalTaxonomy | None = None,
    threshold: float = 0.55,
    limit: int = 10,
) -> list[FrameMatch]:
    taxonomy = taxonomy or LegalTaxonomy.default()
    query_frames = extract_legal_event_frames(query, taxonomy)
    if not query_frames:
        return []
    matches: list[FrameMatch] = []
    for candidate in candidates:
        best = max(frame_sim(query_frame, candidate.frame, taxonomy) for query_frame in query_frames)
        if best < threshold:
            continue
        matches.append(
            FrameMatch(
                frame=candidate,
                score=best,
                edge_type="ANALOGOUS_FRAME",
                path_reason=f"frame_sim={best:.3f}; query_frame_count={len(query_frames)}",
            )
        )
    matches.sort(key=lambda item: (-item.score, item.frame.doc_id, item.frame.frame_id))
    return matches[:limit]


def ensure_event_frame_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS event_frames (
          frame_id TEXT PRIMARY KEY,
          doc_id TEXT NOT NULL,
          chunk_id TEXT NOT NULL,
          actor_class TEXT,
          action_class TEXT,
          object_class TEXT,
          method_class TEXT,
          issue_tags TEXT NOT NULL,
          outcome TEXT,
          text TEXT,
          extractor_ver TEXT NOT NULL DEFAULT 'context_frames_v0'
        );
        CREATE INDEX IF NOT EXISTS idx_event_frames_doc ON event_frames(doc_id);
        CREATE INDEX IF NOT EXISTS idx_event_frames_actor_action_object
          ON event_frames(actor_class, action_class, object_class);
        """
    )


def upsert_event_frames(conn: sqlite3.Connection, frames: list[StoredEventFrame]) -> None:
    ensure_event_frame_schema(conn)
    conn.executemany(
        """
        INSERT INTO event_frames (
          frame_id, doc_id, chunk_id, actor_class, action_class, object_class,
          method_class, issue_tags, outcome, text, extractor_ver
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'context_frames_v0')
        ON CONFLICT(frame_id) DO UPDATE SET
          doc_id=excluded.doc_id,
          chunk_id=excluded.chunk_id,
          actor_class=excluded.actor_class,
          action_class=excluded.action_class,
          object_class=excluded.object_class,
          method_class=excluded.method_class,
          issue_tags=excluded.issue_tags,
          outcome=excluded.outcome,
          text=excluded.text,
          extractor_ver=excluded.extractor_ver
        """,
        [
            (
                item.frame_id,
                item.doc_id,
                item.chunk_id,
                item.frame.actor_class,
                item.frame.action_class,
                item.frame.object_class,
                item.frame.method_class,
                json.dumps(list(item.frame.issue_tags), ensure_ascii=False),
                item.frame.outcome,
                item.text,
            )
            for item in frames
        ],
    )


def stored_event_frames_from_records(
    records: list[dict[str, object] | sqlite3.Row],
    *,
    taxonomy: LegalTaxonomy | None = None,
) -> list[StoredEventFrame]:
    taxonomy = taxonomy or LegalTaxonomy.default()
    out: list[StoredEventFrame] = []
    for record in records:
        doc_id = str(_record_get(record, "canonical_id") or _record_get(record, "doc_id") or "").strip()
        if not doc_id:
            continue
        text = str(_record_get(record, "full_text") or _record_get(record, "text") or "").strip()
        if not text:
            continue
        frames = extract_legal_event_frames(text, taxonomy)
        for index, frame in enumerate(frames, start=1):
            out.append(
                StoredEventFrame(
                    frame_id=f"{doc_id}#frame{index}",
                    doc_id=doc_id,
                    chunk_id=f"{doc_id}#full_text",
                    frame=frame,
                    text=text[:1200],
                )
            )
    return out


def load_event_frames(conn: sqlite3.Connection, *, limit: int | None = None, ensure_schema: bool = True) -> list[StoredEventFrame]:
    if ensure_schema:
        ensure_event_frame_schema(conn)
    sql = """
        SELECT frame_id, doc_id, chunk_id, actor_class, action_class, object_class,
               method_class, issue_tags, outcome, text
        FROM event_frames
        ORDER BY doc_id, frame_id
    """
    params: tuple[object, ...] = ()
    if limit is not None:
        sql += " LIMIT ?"
        params = (int(limit),)
    rows = conn.execute(sql, params).fetchall()
    return [_stored_frame_from_row(row) for row in rows]


def _stored_frame_from_row(row: sqlite3.Row | tuple[object, ...]) -> StoredEventFrame:
    if isinstance(row, sqlite3.Row):
        get = row.__getitem__
    else:
        keys = (
            "frame_id",
            "doc_id",
            "chunk_id",
            "actor_class",
            "action_class",
            "object_class",
            "method_class",
            "issue_tags",
            "outcome",
            "text",
        )
        data = dict(zip(keys, row))
        get = data.__getitem__
    try:
        issue_tags = tuple(str(item) for item in json.loads(str(get("issue_tags") or "[]")))
    except json.JSONDecodeError:
        issue_tags = ()
    return StoredEventFrame(
        frame_id=str(get("frame_id") or ""),
        doc_id=str(get("doc_id") or ""),
        chunk_id=str(get("chunk_id") or ""),
        frame=EventFrame(
            actor_class=str(get("actor_class") or ""),
            action_class=str(get("action_class") or ""),
            object_class=str(get("object_class") or ""),
            method_class=str(get("method_class") or ""),
            issue_tags=issue_tags,
            outcome=str(get("outcome") or "NONE"),
        ),
        text=str(get("text") or ""),
    )


def _record_get(record: dict[str, object] | sqlite3.Row, key: str) -> object:
    if isinstance(record, dict):
        return record.get(key)
    try:
        return record[key]
    except (KeyError, IndexError):
        return None


def extract_legal_event_frames(text: str, taxonomy: LegalTaxonomy | None = None) -> list[EventFrame]:
    taxonomy = taxonomy or LegalTaxonomy.default()
    raw = str(text or "")
    lowered = raw.lower()
    compact = lowered.replace(" ", "")
    actor = _extract_actor(raw, taxonomy)
    action = _extract_action(raw, taxonomy)
    obj = _extract_object(raw, taxonomy)
    method = _extract_method(raw, taxonomy)
    issues = _extract_issues(raw)
    outcome = _extract_outcome(raw)
    if not any((actor, action, obj, method, issues)):
        return []
    if "공기계" in compact and not method:
        method = "LEGAL/METHOD/TECHNICAL_ACCESS/SIM_REINSERTION"
    return [
        EventFrame(
            actor_class=actor,
            action_class=action,
            object_class=obj,
            method_class=method,
            issue_tags=tuple(sorted(issues)),
            outcome=outcome,
        )
    ]


def _extract_actor(text: str, taxonomy: LegalTaxonomy) -> str:
    if _contains_any(text, ("경찰", "사법경찰", "수사관")):
        return taxonomy.resolve("경찰", slot="actor")
    if _contains_any(text, ("검찰", "검사", "검찰청")):
        return taxonomy.resolve("검찰", slot="actor")
    if _contains_any(text, ("군부대", "부대", "공군 부대")):
        return taxonomy.resolve("군부대", slot="actor")
    if _contains_any(text, ("군인", "군 복무", "장병")):
        return taxonomy.resolve("군인", slot="actor")
    if _contains_any(text, ("수사기관",)):
        return "LEGAL/STATE_ACTOR/INVESTIGATIVE"
    if _contains_any(text, ("군대", "군")):
        return "LEGAL/STATE_ACTOR/MILITARY"
    return ""


def _extract_action(text: str, taxonomy: LegalTaxonomy) -> str:
    if _is_sim_reference(text) and _contains_any(text, ("로그인", "접속", "인증번호", "공기계")):
        return taxonomy.resolve("유심 공기계 로그인", slot="action")
    if _is_sim_control_context(text):
        return taxonomy.resolve("유심 분리", slot="action")
    if _is_password_bypass_context(text) and _contains_any(text, ("비밀번호", "비번", "패턴", "잠금", "해킹", "우회", "로그인", "접속", "계정", "메신저")):
        return taxonomy.resolve("비밀번호 해킹", slot="action")
    if _is_key_management_context(text):
        return taxonomy.resolve("열쇠 보관", slot="action")
    if _is_body_height_context(text):
        return taxonomy.resolve("신체 성장", slot="action")
    if _contains_any(text, ("로그인", "계정 접속", "메신저 접속")):
        return "LEGAL/ACTION/ELECTRONIC_ACCESS/ACCOUNT_LOGIN"
    return ""


def _extract_object(text: str, taxonomy: LegalTaxonomy) -> str:
    if _contains_any(text, ("카카오톡", "카톡")):
        return taxonomy.resolve("카카오톡", slot="object")
    if _contains_any(text, ("텔레그램",)):
        return taxonomy.resolve("텔레그램", slot="object")
    if _is_password_bypass_context(text):
        return "LEGAL/OBJECT/COMM"
    if _is_key_management_context(text):
        return "LEGAL/OBJECT/SECURITY/KEY"
    if _is_body_height_context(text):
        return "LEGAL/OBJECT/BODY/HEIGHT"
    if _is_sim_reference(text):
        return taxonomy.resolve("유심", slot="object")
    return ""


def _extract_method(text: str, taxonomy: LegalTaxonomy) -> str:
    if _contains_any(text, ("유심 재삽입", "공기계", "인증번호", "다른 휴대폰")):
        return taxonomy.resolve("유심 재삽입", slot="method")
    if _is_sim_control_context(text):
        return taxonomy.resolve("유심 분리", slot="method")
    if _is_password_bypass_context(text):
        return taxonomy.resolve("비밀번호 우회", slot="method")
    if _contains_any(text, ("이원화", "분리 관리", "분리", "인계", "점검", "시건")):
        return taxonomy.resolve("분리 관리", slot="method")
    return ""


def _extract_issues(text: str) -> set[str]:
    issues: set[str] = set()
    if _is_sim_reference(text) or _contains_any(text, ("카카오톡", "카톡", "텔레그램", "메신저", "계정", "전자정보", "비밀번호", "비번", "패턴", "잠금해제", "해킹")):
        issues.add("ELECTRONIC_EVIDENCE")
    if _contains_any(text, ("영장", "압수", "수색", "합법", "적법", "위법", "증거")) and "ELECTRONIC_EVIDENCE" in issues:
        issues.add("WARRANT_SCOPE")
    if _contains_any(text, ("경찰", "검찰", "검사", "수사기관")) and (
        _is_sim_control_context(text) or _is_password_bypass_context(text)
    ):
        issues.add("WARRANT_SCOPE")
    if _contains_any(text, ("증거능력", "위법수집", "위법", "합법", "적법")) and "ELECTRONIC_EVIDENCE" in issues:
        issues.add("EXCLUSIONARY_RULE")
    if _is_key_management_context(text):
        issues.update({"MILITARY_SECURITY", "KEY_MANAGEMENT"})
    if _is_body_height_context(text):
        issues.add("MEDICAL_BODY")
    return issues


def _extract_outcome(text: str) -> str:
    if _contains_any(text, ("위법", "위법수집")):
        return "UNLAWFUL"
    if _contains_any(text, ("적법", "합법")):
        return "LAWFUL"
    return "NONE"


def _is_key_management_context(text: str) -> bool:
    if _is_body_height_context(text):
        return False
    explicit_key = _contains_any(text, ("열쇠", "출입키", "탄약고", "무기고", "시건", "보안구역"))
    homograph_key = (
        _contains_any(text, ("키",))
        and _contains_any(text, ("군", "부대"))
        and _contains_any(text, ("탄약", "무기", "보안", "관리", "인계", "점검", "보관", "시건"))
    )
    return (explicit_key or homograph_key) and _contains_any(text, ("군", "부대", "탄약", "무기", "보안", "관리", "인계", "점검", "시건"))


def _is_sim_control_context(text: str) -> bool:
    return _is_sim_reference(text) and _contains_any(
        text,
        ("뽑", "빼", "분리", "제거", "압수", "보관"),
    )


def _is_sim_reference(text: str) -> bool:
    if _contains_any(text, ("유심", "유심칩", "가입자식별모듈", "가입자 식별 모듈")):
        return True
    return bool(re.search(r"(?<![a-z0-9])u?sim(?![a-z0-9])", str(text or "").lower()))


def _is_password_bypass_context(text: str) -> bool:
    return _contains_any(
        text,
        (
            "비밀번호",
            "비번",
            "패스코드",
            "암호",
            "패턴 우회",
            "패턴을 우회",
            "잠금해제",
            "잠금 해제",
            "해킹",
            "우회",
        ),
    )


def _is_body_height_context(text: str) -> bool:
    return _contains_any(text, ("신장", "키 성장", "체격", "cm", "백분위", "성장", "height"))


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    lowered = str(text or "").lower()
    return any(needle.lower() in lowered for needle in needles)


def _issue_sim(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    left_set = {str(item).strip() for item in left if str(item).strip()}
    right_set = {str(item).strip() for item in right if str(item).strip()}
    if not left_set or not right_set:
        return 0.0
    intersection = left_set & right_set
    union = left_set | right_set
    return len(intersection) / float(len(union))
