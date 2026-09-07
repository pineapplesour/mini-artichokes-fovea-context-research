from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path
from typing import Any

from .config import QUESTION_VARIANT_NAME
from .legal_proposition_verifier import rewrite_answer_with_legal_proposition_guard

CASE_CITATION_PATTERN = re.compile(
    r"(?P<court>[가-힣A-Za-z0-9·()\s]+법원)\s+"
    r"(?P<date>\d{4}[.\-]\s*\d{1,2}[.\-]\s*\d{1,2}\.?)\s*"
    r"선고\s*"
    r"(?P<case>[0-9가-힣()누구합단도재마나카허저]+)"
)
COMPACT_CASE_PATTERN = re.compile(
    r"(?P<case>[0-9가-힣()누구합단도재마나카허저]+)\s+"
    r"(?P<date>\d{8})\s+선고\s+"
    r"(?P<court>[가-힣A-Za-z0-9·()\s]+법원)"
)
REVERSE_COMPACT_CASE_PATTERN = re.compile(
    r"(?P<court>[가-힣A-Za-z0-9·()\s]+법원)\s+"
    r"(?P<date>\d{8})\s+선고\s+"
    r"(?P<case>[0-9가-힣()누구합단도재마나카허저]+)"
)

GENERIC_CASE_NAME_MARKERS = (
    "묶음",
    "정확도순",
    "selected",
    "summaries",
    "판례집",
    "최근",
    "기간[",
    "종류[",
    "제외[",
    "선정",
    "리스트",
)


def aggregate_selected_rows(keyword_hits: dict[str, list[dict[str, Any]]], limit: int = 100) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for keyword, rows in keyword_hits.items():
        for row in rows:
            canonical_id = str(row.get("canonical_id") or "").strip()
            if not canonical_id:
                continue
            entry = merged.setdefault(
                canonical_id,
                {
                    **row,
                    "matched_keywords": set(),
                    "_raw_scores": [],
                },
            )
            entry["matched_keywords"].add(keyword)
            try:
                entry["_raw_scores"].append(float(row.get("score") or 0.0))
            except (TypeError, ValueError):
                entry["_raw_scores"].append(0.0)
            for key, value in row.items():
                if entry.get(key) in (None, "", []):
                    entry[key] = value
    ranked: list[dict[str, Any]] = []
    for entry in merged.values():
        scores = entry.pop("_raw_scores", [])
        matched_keywords = sorted(entry.pop("matched_keywords", []))
        best_score = min(scores) if scores else 0.0
        keyword_hit_count = len(matched_keywords)
        ranked.append(
            {
                **entry,
                "matched_keywords": matched_keywords,
                "keyword_hit_count": keyword_hit_count,
                "best_score": best_score,
            }
        )
    ranked.sort(
        key=lambda item: (
            -int(item.get("keyword_hit_count") or 0),
            float(item.get("best_score") or 0.0),
            str(item.get("decision_date") or ""),
            str(item.get("canonical_id") or ""),
        )
    )
    return ranked[:limit]


TAIL_ETA_SECONDS_BY_STATE = {
    "queued": 8,
    "waiting_for_capacity": 8,
    "generating_keywords": 14,
    "building_chunk_plan": 20,
    "packing_chunks": 20,
    "chunking_records": 20,
    "analyzing_chunks": 24,
    "writing_final_draft": 18,
    "writing_document": 18,
    "applying_coverage_patch": 3,
    "exporting_artifacts": 5,
}


def _positive_int(value: Any) -> int:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def _estimate_chunk_eta_seconds(
    runtime_status: dict[str, Any],
    *,
    completed: int,
    total: int,
    remaining: int,
    elapsed_seconds: int,
    worker_count: int,
) -> int:
    if remaining <= 0:
        return 0

    runtime_limits = runtime_status.get("runtime_limits") or {}
    parallelism = max(1, worker_count)
    for key in ("gemini_global_max_inflight",):
        hard_limit = _positive_int(runtime_limits.get(key) or runtime_status.get(key))
        if hard_limit > 0:
            parallelism = min(parallelism, hard_limit)
    if total > 0:
        parallelism = min(parallelism, total)

    # The backend injects elapsed_seconds as whole-job time, not chunk-phase time.
    # Clamp observed wave time so a slow selector/finalizer cannot inflate chunk ETA
    # into 30-minute spikes while the 10-key chunk workers are actually active.
    wave_seconds = 18.0
    completed_waves = completed / parallelism if parallelism > 0 else 0.0
    if completed_waves >= 1.0 and elapsed_seconds > 0:
        observed_wave_seconds = elapsed_seconds / completed_waves
        wave_seconds = max(10.0, min(35.0, observed_wave_seconds))

    remaining_waves = max(1, math.ceil(remaining / max(1, parallelism)))
    return int(round(remaining_waves * wave_seconds))


def project_live_status(runtime_status: dict[str, Any], *, chunk_plan: list[dict[str, Any]], worker_count: int) -> dict[str, Any]:
    state = str(runtime_status.get("state") or "queued")
    completed = _positive_int(runtime_status.get("completed_chunks"))
    total = _positive_int(
        runtime_status.get("chunk_count")
        or runtime_status.get("estimated_chunk_count")
        or runtime_status.get("total_chunks")
        or len(chunk_plan)
        or 0
    )
    elapsed_seconds = _positive_int(runtime_status.get("elapsed_seconds"))
    remaining = max(total - completed, 0)
    eta_seconds = 0
    if state == "analyzing_chunks" and remaining > 0:
        eta_seconds = _estimate_chunk_eta_seconds(
            runtime_status,
            completed=completed,
            total=total,
            remaining=remaining,
            elapsed_seconds=elapsed_seconds,
            worker_count=worker_count,
        )
    elif completed > 0 and elapsed_seconds > 0 and remaining > 0:
        eta_seconds = round((elapsed_seconds / completed) * remaining)
    tail_eta = TAIL_ETA_SECONDS_BY_STATE.get(state, 0)
    if state == "analyzing_chunks" and remaining > 0:
        eta_seconds += tail_eta
    elif eta_seconds <= 0:
        eta_seconds = tail_eta
    current_index = min(completed, max(len(chunk_plan) - 1, 0)) if chunk_plan else None
    current_case_number = ""
    current_excerpt = ""
    if current_index is not None and chunk_plan:
        current = chunk_plan[current_index]
        current_case_number = str(current.get("case_number") or "")
        current_excerpt = str(current.get("excerpt") or "")
    runtime_limits = runtime_status.get("runtime_limits") or {}
    raw_keywords = runtime_status.get("keywords") or runtime_status.get("selection_keywords") or []
    selection_keywords = [str(item) for item in raw_keywords if str(item).strip()]
    return {
        "phase": runtime_status.get("phase") or "startup",
        "state": state,
        "selectedPrecedentCount": int(runtime_status.get("selected_file_count") or 0),
        "completedChunks": completed,
        "totalChunks": total,
        "workerCount": worker_count,
        "elapsedSeconds": elapsed_seconds,
        "etaSeconds": eta_seconds,
        "currentCaseNumber": current_case_number,
        "currentExcerpt": current_excerpt,
        "selectionKeywords": selection_keywords,
        "scheduler": {
            "keyCount": int(runtime_status.get("gemini_keys_total") or 0),
            "coolingKeys": int(runtime_status.get("gemini_keys_cooling_down") or 0),
            "inflight": int(runtime_status.get("gemini_scheduler_inflight") or 0),
            "nextReadyInMs": int(runtime_status.get("gemini_next_ready_in_ms") or 0),
            "minGapMs": int(runtime_limits.get("gemini_key_min_gap_ms") or 0),
            "maxInflightPerKey": int(runtime_limits.get("gemini_key_max_inflight") or 0),
            "rpmLimit": int(runtime_limits.get("gemini_key_rpm_limit") or 0),
            "tpmLimit": int(runtime_limits.get("gemini_key_tpm_limit") or 0),
            "globalMaxInflight": int(runtime_limits.get("gemini_global_max_inflight") or 0),
        },
        "lastApiActivityAt": str(runtime_status.get("last_api_activity_at") or ""),
        "lastApiEvent": str(runtime_status.get("last_api_event") or ""),
        "lastApiResult": str(runtime_status.get("last_api_result") or ""),
    }


def _load_json(path: Path, default: Any) -> Any:
    """Read JSON with retry on partial-write race.

    work16 subprocess writes status.json with `path.write_text(...)`, which
    truncates the file before writing. If the API server reads at that
    millisecond it sees an empty file and `json.loads("")` raises
    `JSONDecodeError`, surfacing as 500 to the polling client.

    We retry up to 3 times with 30ms backoff. The truncate→write window
    is sub-millisecond on local fs; one retry catches it.
    """
    if not path.exists():
        return default
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return default
        if not raw.strip():
            # Empty mid-write — wait for the writer to finish.
            time.sleep(0.03)
            continue
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            last_exc = exc
            time.sleep(0.03)
    if last_exc is not None:
        # All retries failed — treat as if the file is missing rather than
        # 500ing the polling client. The next poll (5s later) will retry.
        return default
    return default


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    # Skip a partial line mid-write rather than fail the
                    # entire request — chunk_outputs.jsonl is appended line
                    # by line during analysis.
                    continue
    except FileNotFoundError:
        return []
    return rows


def _clean_display_text(value: str, *, limit: int = 220) -> str:
    raw = str(value or "").replace("<br/>", "\n").replace("<br />", "\n").replace("<br>", "\n")
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    filtered: list[str] = []
    for line in lines:
        if re.fullmatch(r"\[판례\s*\d+\]", line, flags=re.IGNORECASE):
            continue
        if re.match(r"^(제목|확정\s*날짜|항소\s*날짜|날짜|url)\s*:", line, flags=re.IGNORECASE):
            continue
        if re.fullmatch(r"\[사건\s*정보\]", line, flags=re.IGNORECASE):
            continue
        if re.fullmatch(
            r"[가-힣A-Za-z0-9·()\s]+법원\s+\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*선고\s*[0-9가-힣()누구합단도재마나카허저]+\s*판결(?:\s*\[[^\]]+\])?",
            line,
            flags=re.IGNORECASE,
        ):
            continue
        filtered.append(line)
    text = " ".join(filtered)
    text = text.replace("【주문】", " ").replace("【이유】", " ")
    text = text.replace("제목:", " ").replace("확정 날짜:", " ")
    text = re.sub(r"【[^】]+】", " ", text)
    text = re.sub(r"\[[^\]]*사건\s*정보[^\]]*\]", " ", text)
    text = re.sub(r"▣[^\\n]+", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\[판례\s*\d+\]", " ", text)
    text = re.sub(r"(항소\s*날짜|확정\s*날짜|날짜|url|사건\s*정보|사\s*건)\s*:\s*", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"^(?:주문|이유)\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+(?:주문|이유)\s+", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"-{6,}", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _is_meaningful_label(value: str) -> bool:
    text = _clean_display_text(value, limit=200)
    if not text:
        return False
    if text.isdigit():
        return False
    if len(text) <= 2 and text.isalnum():
        return False
    return True


def _is_generic_case_name(value: str) -> bool:
    text = _clean_display_text(value, limit=200)
    if not text:
        return True
    lowered = text.lower()
    return any(marker in lowered for marker in GENERIC_CASE_NAME_MARKERS)


def _normalize_case_name(value: str) -> str:
    text = _clean_display_text(value, limit=120)
    if not _is_meaningful_label(text):
        return ""
    if _is_generic_case_name(text):
        return ""
    return text


def _format_decision_date(value: str) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) >= 8:
        return f"{digits[:4]}. {digits[4:6]}. {digits[6:8]}."
    return _clean_display_text(str(value or ""), limit=32)


def _normalize_court_label(value: str) -> str:
    text = _clean_display_text(str(value or ""), limit=80)
    if not text:
        return ""
    if text.endswith("행법"):
        return f"{text[:-2]}행정법원"
    if text.endswith("고법"):
        return f"{text[:-2]}고등법원"
    if text.endswith("지법"):
        return f"{text[:-2]}지방법원"
    return text


def _case_number_year(value: str) -> int:
    matched = re.match(r"\s*(\d{2,4})", str(value or ""))
    if not matched:
        return 0
    digits = matched.group(1)
    year = int(digits)
    if len(digits) == 2:
        return 1900 + year if year >= 50 else 2000 + year
    return year


def _decision_date_year(value: str) -> int:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) < 4:
        return 0
    try:
        return int(digits[:4])
    except ValueError:
        return 0


def _row_source_path(row: dict[str, Any]) -> str:
    return " ".join(
        str(row.get(key) or "")
        for key in ("sourcePath", "source_path", "relativePath", "relative_path", "absolute_path")
    ).lower()


def _extract_compact_source_citation_parts(full_text: str, explicit_case_number: str = "") -> dict[str, str]:
    lines = [
        _clean_display_text(line, limit=160)
        for line in str(full_text or "").splitlines()[:16]
        if _clean_display_text(line, limit=160)
    ]
    if not lines:
        return {"court": "", "decision_date": "", "case_number": "", "case_name": ""}
    target_case = _clean_display_text(str(explicit_case_number or ""), limit=60)
    for index, line in enumerate(lines):
        if target_case:
            if line != target_case:
                continue
            case_number = target_case
        else:
            matched = re.fullmatch(r"\d{2,4}[가-힣]+[0-9]+", line)
            if not matched:
                continue
            case_number = matched.group(0)
        if index + 3 >= len(lines):
            continue
        date = _format_decision_date(lines[index + 1])
        if not re.fullmatch(r"\d{4}\. \d{2}\. \d{2}\.", date):
            continue
        if "선고" not in lines[index + 2]:
            continue
        court = _normalize_court_label(lines[index + 3])
        if not court:
            continue
        case_name = lines[index - 1] if index > 0 else ""
        return {
            "court": court,
            "decision_date": date,
            "case_number": case_number,
            "case_name": _normalize_case_name(case_name),
        }
    return {"court": "", "decision_date": "", "case_number": "", "case_name": ""}


def _decision_date_is_untrusted(
    *,
    decision_date: str,
    case_number: str,
    source_path: str,
    has_compact_source_header: bool,
) -> bool:
    if has_compact_source_header:
        return False
    if "07_lawgokr_fulltext" in source_path or "lawgokr_fulltext" in source_path:
        return True
    if not decision_date:
        return False
    case_year = _case_number_year(case_number)
    decision_year = _decision_date_year(decision_date)
    if case_year and decision_year and decision_year < case_year:
        return True
    # The law.go.kr full-text dump often has `선고일자=00010101`; our upstream
    # ingest previously fell back to the first body date, which is frequently
    # a 처분일 in administrative/san재 cases. Without a compact source header,
    # render only the case number.
    return False


def _inferred_matches_explicit_identity(
    inferred: dict[str, str],
    explicit_case_number: str,
    case_name: str,
) -> bool:
    """When DB rows lack explicit metadata we sometimes parse the title for a
    citation pattern. But the parsed citation MUST match the row's own
    case identifiers — otherwise we'd be stamping a stranger's case number
    onto our row. If explicit_case_number is set and inferred mismatches,
    or no co-occurring case_name signal exists, reject the inferred set.
    """
    inf_case = _clean_display_text(str(inferred.get("case_number") or ""), limit=60)
    if not inf_case:
        return True  # nothing to validate — caller will keep explicit values
    if explicit_case_number and explicit_case_number != inf_case:
        return False
    if explicit_case_number and explicit_case_number == inf_case:
        return True
    # No explicit case_number — only trust the inferred set if some textual
    # corroboration exists (case_name overlap with the inferred case identifier).
    name = _clean_display_text(str(case_name or ""), limit=160)
    return bool(name) and inf_case in name


def _extract_citation_parts(*values: str) -> dict[str, str]:
    for value in values:
        text = str(value or "")
        if not text.strip():
            continue
        compact = COMPACT_CASE_PATTERN.search(text) or REVERSE_COMPACT_CASE_PATTERN.search(text)
        if compact:
            return {
                "court": _clean_display_text(compact.group("court"), limit=80),
                "decision_date": _format_decision_date(compact.group("date")),
                "case_number": _clean_display_text(compact.group("case"), limit=60),
            }
        matched = CASE_CITATION_PATTERN.search(text)
        if not matched:
            continue
        return {
            "court": _clean_display_text(matched.group("court"), limit=80),
            "decision_date": _format_decision_date(matched.group("date")),
            "case_number": _clean_display_text(matched.group("case"), limit=60),
        }
    return {"court": "", "decision_date": "", "case_number": ""}


def _normalize_markdown_dates(text: str) -> str:
    raw = str(text or "")
    # Convert `YYYY-MM-DD` followed by `선고` → `YYYY. MM. DD.`.
    raw = re.sub(r"(\d{4})-(\d{2})-(\d{2})(?=\s*선고)", r"\1. \2. \3.", raw)
    # Convert citation-shape `(법원 YYYY-MM-DD 사건번호)` (no `선고` token,
    # which the LLM omits when it picks the format from chunk source headers)
    # into the standard `(법원 YYYY. MM. DD. 선고 사건번호 판결)` form.
    citation_with_hyphen = re.compile(
        r"(\*\*\(\s*[가-힣A-Za-z]{1,30}(?:법원|법|지법|지원|재판소)\s+)(\d{4})-(\d{2})-(\d{2})(\s+[\w가-힣]+\s*판결\s*\)\*\*)"
    )
    raw = citation_with_hyphen.sub(lambda m: f"{m.group(1)}{m.group(2)}. {m.group(3)}. {m.group(4)}. 선고 {m.group(5).lstrip()}", raw)
    bare_citation_with_hyphen = re.compile(
        r"(\(\s*[가-힣A-Za-z]{1,30}(?:법원|법|지법|지원|재판소)\s+)(\d{4})-(\d{2})-(\d{2})(\s+[\w가-힣]+\s*판결\s*\))"
    )
    raw = bare_citation_with_hyphen.sub(lambda m: f"{m.group(1)}{m.group(2)}. {m.group(3)}. {m.group(4)}. 선고 {m.group(5).lstrip()}", raw)
    return raw


# Match the `<term1>: **<def1> ... <term2>:**` scrambled-term anti-pattern
# the LLM occasionally produces in the conclusion glossary block. The bold
# envelope wrongly straddles a definition + the next term, instead of
# wrapping each term individually. Restructure into the standard
# `**term**: definition` shape on separate lines.
_SCRAMBLED_TERM_BOLD = re.compile(
    r"([가-힣A-Za-z][가-힣A-Za-z\s]{0,18}[가-힣A-Za-z])"
    r"\s*[:：]\s*\*\*\s*"
    r"(.+?[다요까]\s*[.。]?)\s*"
    r"([가-힣A-Za-z][가-힣A-Za-z\s]{0,18}[가-힣A-Za-z])"
    r"\s*[:：]\s*\*\*",
    re.DOTALL,
)


def _normalize_orphan_bold(text: str) -> str:
    """Repair two distinct LLM bold-formatting anti-patterns:

    1. `<term1>: **<def1> ... <term2>:**` — paired `**` placed in scrambled
       positions so the bold envelope covers a definition plus the next
       term. Restructure into per-line `**term**: definition` pairs.
    2. Lines with odd-count `**` (orphan opener or closer). Strip the last
       lone `**` on the line so MarkdownView doesn't render a runaway bold
       across paragraph boundaries.
    """
    if not text:
        return text
    out = str(text)

    def _scramble_repl(match: re.Match[str]) -> str:
        term1 = match.group(1).strip()
        def1 = match.group(2).strip()
        term2 = match.group(3).strip()
        # Newline between the two glossary entries gives the parser a clean
        # paragraph break. The trailing colon on term2 is preserved by the
        # following text in the source.
        return f"**{term1}**: {def1}\n\n**{term2}**: "

    # Apply repeatedly — multiple scrambled blocks may chain.
    for _ in range(4):
        new_out = _SCRAMBLED_TERM_BOLD.sub(_scramble_repl, out)
        if new_out == out:
            break
        out = new_out

    # Also collapse over-greedy bold spans that contain a `:` and span >50
    # chars — these are uncertain term/definition mixes; safer to remove
    # the bold than render a giant bold paragraph.
    def _overgreedy_repl(match: re.Match[str]) -> str:
        content = match.group(1)
        if ":" in content and len(content) > 50 and "\n" not in content:
            return content
        return match.group(0)

    out = re.sub(r"\*\*([^*\n]{1,400}?)\*\*", _overgreedy_repl, out)

    # Strip orphan `**` (odd-count per line) — runaway opener/closer.
    fixed: list[str] = []
    for line in out.splitlines():
        if line.count("**") % 2 == 1:
            line = line[::-1].replace("**"[::-1], "", 1)[::-1]
        fixed.append(line)
    return "\n".join(fixed)


ANSWER_META_LEAK_PATTERNS = (
    re.compile(r"Input:\s*A draft", re.IGNORECASE),
    re.compile(r"Goal:\s*Rewrite", re.IGNORECASE),
    re.compile(r"Constraints:", re.IGNORECASE),
    re.compile(r"Self[-\s]?Correction", re.IGNORECASE),
    re.compile(r"Final check", re.IGNORECASE),
    re.compile(r"Drafting the final response", re.IGNORECASE),
    re.compile(r"Wait,\s*the prompt", re.IGNORECASE),
    re.compile(r"Wait,\s*the instruction", re.IGNORECASE),
    re.compile(r"the prompt says", re.IGNORECASE),
    re.compile(r"Let's go", re.IGNORECASE),
    re.compile(r"claim_id lists?", re.IGNORECASE),
)

DOCUMENT_META_LEAK_PATTERNS = (
    re.compile(r"Legal Professional", re.IGNORECASE),
    re.compile(r"Legal Opinion Writer", re.IGNORECASE),
    re.compile(r"Complaint\s*\(\s*고\s*소\s*장\s*\)", re.IGNORECASE),
    re.compile(r"Write a\s+\"?(?:Complaint|Legal Opinion)", re.IGNORECASE),
    re.compile(r"Use\s+\*?only\*?\s+the provided ledger", re.IGNORECASE),
    re.compile(r"The user provided", re.IGNORECASE),
    re.compile(r"The user'?s task", re.IGNORECASE),
    re.compile(r"though the user'?s task", re.IGNORECASE),
    re.compile(r"Wait,\s*let'?s re-read", re.IGNORECASE),
    re.compile(r"Wait,\s*looking at the prompt", re.IGNORECASE),
    re.compile(r"Wait,\s*let'?s look", re.IGNORECASE),
    re.compile(r"Contradiction Check\s*:", re.IGNORECASE),
    re.compile(r"Resolution\s*:", re.IGNORECASE),
    re.compile(r"Problem\s*:", re.IGNORECASE),
    re.compile(r"Re-evaluating the", re.IGNORECASE),
    re.compile(r"Hypothesis\s*:", re.IGNORECASE),
    re.compile(r"Decision\s*:", re.IGNORECASE),
    re.compile(r"Crucial Realization\s*:", re.IGNORECASE),
    re.compile(r"Targeting the", re.IGNORECASE),
    re.compile(r"Strategy\s*:", re.IGNORECASE),
    re.compile(r"Subject Matter\s*:", re.IGNORECASE),
    re.compile(r"\bClaim\s+\d+\s*:", re.IGNORECASE),
    re.compile(r"\bStructure\s*:", re.IGNORECASE),
    re.compile(r"\bTone\s*:", re.IGNORECASE),
    re.compile(r"Drafting Content\s*:", re.IGNORECASE),
    re.compile(r"Refining the", re.IGNORECASE),
    re.compile(r"Check against constraints", re.IGNORECASE),
    re.compile(r"Constraint Check\s*:", re.IGNORECASE),
    re.compile(r"Final Review of the Ledger usage", re.IGNORECASE),
    re.compile(r"Final Polish", re.IGNORECASE),
    re.compile(r"Final Plan\s*:", re.IGNORECASE),
    re.compile(r"Final Text Construction\s*:", re.IGNORECASE),
    re.compile(r"Mental Draft\s*:", re.IGNORECASE),
    re.compile(r"Final check", re.IGNORECASE),
    re.compile(r"\*?\s*Check\s*:\s*", re.IGNORECASE),
    re.compile(r"Formatting\s*:\s*Plain text", re.IGNORECASE),
    re.compile(r"Drafting the final response", re.IGNORECASE),
    re.compile(r"Proceeding to generate", re.IGNORECASE),
)

DOCUMENT_TITLE_PATTERN = (
    r"법률\s*검토\s*의견서|"
    r"변호인\s*의견서|"
    r"변호인의견서|"
    r"내용증명|"
    r"고\s*소\s*장|"
    r"고발장|"
    r"준비서면|"
    r"답변서|"
    r"항소이유서|"
    r"탄원서|"
    r"진정서"
)

DOCUMENT_STRUCTURAL_OUTPUT_START_PATTERNS = (
    re.compile(r"(?im)(?P<start>^\s*(?:#+\s*)?고\s*소\s*장\s*$)"),
    re.compile(r"(?im)(?P<start>^\s*(?:#+\s*)?1\.\s*고소인\b)"),
)

DOCUMENT_OUTPUT_START_PATTERNS = (
    re.compile(
        rf"(?im)^\s*(?:#+\s*)?(?:\*\*)?(?P<start>{DOCUMENT_TITLE_PATTERN})(?=$|[\s:：])"
    ),
    re.compile(
        rf"(?is)let'?s go\.?\*?\s*(?P<start>{DOCUMENT_TITLE_PATTERN})(?=$|[\s:：])"
    ),
    re.compile(
        rf"(?is)generate[^\n]{{0,160}}?(?P<start>{DOCUMENT_TITLE_PATTERN})(?=$|[\s:：])"
    ),
    re.compile(
        rf"(?is)\)[\.\s]*(?P<start>{DOCUMENT_TITLE_PATTERN})(?=$|[\s:：])"
    ),
    re.compile(r"(?m)(?P<start>^사\s*건\s+.+$)"),
    re.compile(r"(?m)(?P<start>^수\s*신(?:인)?\s*[:：]?\s*.+$)"),
    re.compile(r"(?m)(?P<start>^발\s*신(?:인)?\s*[:：]?\s*.+$)"),
    re.compile(r"(?m)(?P<start>^제\s*목\s*[:：]?\s*.+$)"),
)


def _find_document_output_start(raw: str, *, after: int) -> int | None:
    search_area = raw[max(0, after) :]
    for pattern in DOCUMENT_STRUCTURAL_OUTPUT_START_PATTERNS:
        match = pattern.search(search_area)
        if match:
            return max(0, after) + match.start("start")
    candidates: list[int] = []
    for pattern in DOCUMENT_OUTPUT_START_PATTERNS:
        match = pattern.search(search_area)
        if match:
            candidates.append(max(0, after) + match.start("start"))
    return min(candidates) if candidates else None


def _ensure_document_heading(markdown: str) -> str:
    cleaned = str(markdown or "").strip()
    if re.match(r"(?im)^(?:#+\s*)?1\.\s*고소인\b", cleaned):
        return f"고    소    장\n\n{cleaned}"
    return cleaned


def _strip_answer_meta_leak(markdown: str) -> str:
    raw = str(markdown or "").strip()
    if not raw:
        return ""
    all_patterns = ANSWER_META_LEAK_PATTERNS + DOCUMENT_META_LEAK_PATTERNS
    if not any(pattern.search(raw) for pattern in all_patterns):
        return raw
    final_answer_matches = list(re.finditer(r"##\s*종합\s*판단", raw))
    if final_answer_matches:
        return re.sub(r"^\*?\s*let'?s go\.?\s*\*?", "", raw[final_answer_matches[-1].start() :], flags=re.IGNORECASE).strip() or raw
    summary_matches = list(re.finditer(r"###\s*가장\s*가능성\s*높은\s*결론", raw))
    if summary_matches:
        return re.sub(r"^\*?\s*let'?s go\.?\s*\*?", "", raw[summary_matches[-1].start() :], flags=re.IGNORECASE).strip() or raw
    marker_ends = [
        match.end()
        for pattern in all_patterns
        for match in pattern.finditer(raw)
    ]
    document_start = _find_document_output_start(raw, after=max(marker_ends) if marker_ends else 0)
    if document_start is not None:
        return _ensure_document_heading(raw[document_start:].strip() or raw)
    cleaned_lines = [
        line
        for line in raw.splitlines()
        if not any(pattern.search(line) for pattern in all_patterns)
    ]
    return "\n".join(cleaned_lines).strip()


def strip_document_meta_leak(markdown: str) -> str:
    raw = str(markdown or "").strip()
    if not raw:
        return ""
    if not any(pattern.search(raw) for pattern in DOCUMENT_META_LEAK_PATTERNS):
        return raw
    marker_ends = [
        match.end()
        for pattern in DOCUMENT_META_LEAK_PATTERNS
        for match in pattern.finditer(raw)
    ]
    document_start = _find_document_output_start(raw, after=max(marker_ends) if marker_ends else 0)
    if document_start is not None:
        return _ensure_document_heading(raw[document_start:].strip() or raw)
    return _strip_answer_meta_leak(raw)


def _claim_group_label(axis: str) -> str:
    normalized = _clean_display_text(axis, limit=120)
    if not normalized:
        return "기타 주장"
    rules = [
        ("징계시효", ("징계시효", "기산점", "계속적 위반", "시효")),
        ("이중징계", ("이중징계",)),
        ("신뢰보호", ("신뢰보호", "신의칙")),
        ("재량권 남용", ("재량권", "재량권남용", "양정", "과중", "비례")),
        ("절차적 하자 및 권한", ("절차", "정족수", "추인", "방어권", "권한", "특정", "의결")),
        ("확인의 이익", ("확인의 이익", "소송 요건")),
    ]
    for label, keywords in rules:
        if any(keyword in normalized for keyword in keywords):
            return label
    return normalized


def _is_placeholder_case_name(case_name: str) -> bool:
    """Treat short numeric/alphanumeric strings as placeholder case_name.
    Such rows in our SQLite DB had their case_number/court/decision_date
    stamped from body-text scanning at upstream ingest time, so all three
    are typically misaligned (different real cases sharing one case_number
    string). We refuse to render them as identified citations.
    """
    name = (case_name or "").strip()
    if not name:
        return True
    if name.isdigit():
        return True
    if len(name) <= 2 and name.isalnum():
        return True
    return False


def _build_precedent_citation(row: dict[str, Any]) -> str:
    # User-facing precedent labels must not synthesize court/date/case-name
    # identity from body text, titles, or upstream fallback metadata. A sparse
    # but verified case-number label is safer than a polished wrong citation.
    case_number = _clean_display_text(str(row.get("caseNumber") or row.get("case_number") or ""), limit=60)
    return f"{case_number} 판결" if case_number else "참조 판례"


def _first_supporting_case_citation(claim: dict[str, Any]) -> str:
    for supporting_case in claim.get("supporting_cases") or []:
        citation = _build_precedent_citation(
            {
                "court": supporting_case.get("court"),
                "decision_date": supporting_case.get("decision_date"),
                "case_number": supporting_case.get("case_number"),
                "case_name": supporting_case.get("case_name"),
            }
        )
        if citation:
            return citation
    return ""


def _simplify_precedent(row: dict[str, Any]) -> dict[str, Any]:
    raw_full_text = str(row.get("extracted_text") or "")
    # Strip source-attribution watermarks and unify section-bracket styles
    # so all rows render with the same look + no traceability fingerprint.
    full_text = _strip_source_markers(_normalize_html_breaks(raw_full_text))
    raw_case_name = str(row.get("case_name") or "")
    case_name = _normalize_case_name(raw_case_name)
    title = case_name if case_name else str(row.get("document_title") or row.get("title") or "")
    title = _clean_display_text(title, limit=160)
    excerpt = _clean_display_text(full_text, limit=220)
    case_number = _clean_display_text(str(row.get("case_number") or ""), limit=60)
    court = ""
    decision_date = ""
    if not case_name and _is_meaningful_label(title) and not _is_generic_case_name(title):
        case_name = title
    simplified = {
        "precedentId": str(row.get("file_id") or row.get("canonical_id") or ""),
        "caseNumber": case_number,
        "caseName": case_name,
        "title": title,
        "court": court,
        "decisionDate": decision_date,
        "sourcePath": str(row.get("absolute_path") or row.get("source_path") or ""),
        "relativePath": str(row.get("relative_path") or ""),
        "fullText": full_text,
        "excerpt": excerpt,
    }
    simplified["citation"] = _build_precedent_citation(simplified)
    if not _is_meaningful_label(title):
        title = simplified["citation"] or excerpt[:80] or "판례"
    simplified["title"] = title
    return simplified


def _precedent_quality_score(precedent: dict[str, Any]) -> tuple[int, int, int, int]:
    inferred = _extract_citation_parts(
        str(precedent.get("title") or ""),
        str(precedent.get("fullText") or ""),
        str(precedent.get("excerpt") or ""),
    )
    case_number = str(precedent.get("caseNumber") or "").strip()
    court = str(precedent.get("court") or "").strip()
    decision_date = _format_decision_date(str(precedent.get("decisionDate") or ""))
    case_name = _normalize_case_name(str(precedent.get("caseName") or ""))
    source_path = str(precedent.get("sourcePath") or "")
    title = _clean_display_text(str(precedent.get("title") or ""), limit=160)

    score = 0
    if case_number:
        score += 120
    if court:
        score += 40
    if decision_date:
        score += 40
    if case_name:
        score += 35
    if title and not _is_generic_case_name(title):
        score += 15
    if precedent.get("summary"):
        score += 8
    if "::part-" in source_path:
        score += 12
    if "lawlaw" in source_path.lower():
        score += 8
    if "07_lawgokr_fulltext" in source_path:
        score -= 12

    inferred_case = _clean_display_text(str(inferred.get("case_number") or ""), limit=60)
    inferred_date = _format_decision_date(str(inferred.get("decision_date") or ""))
    if case_number and inferred_case:
        if case_number == inferred_case:
            score += 18
        else:
            score -= 30
    if decision_date and inferred_date:
        if decision_date == inferred_date:
            score += 12
        else:
            score -= 35

    return (
        score,
        len(case_name),
        len(str(precedent.get("summary") or "")),
        len(str(precedent.get("fullText") or "")),
    )


_LEGAL_SUBTYPE_TERMS = (
    "위반",
    "치상",
    "치사",
    "상해",
    "손해",
    "사고",
    "미조치",
    "사기",
    "업무",
    "처분",
    "취소",
    "무효",
    "급여",
    "장해",
    "보상",
    "기",
    "등",
    "법",
)


def _precedent_identity_name(precedent: dict[str, Any]) -> str:
    raw = _normalize_case_name(str(precedent.get("caseName") or precedent.get("title") or ""))
    if not raw or _is_generic_case_name(raw):
        return ""

    def drop_nonlegal_parenthetical(match: re.Match[str]) -> str:
        inner = re.sub(r"\s+", "", match.group(1) or "")
        if 2 <= len(inner) <= 5 and not any(term in inner for term in _LEGAL_SUBTYPE_TERMS):
            return ""
        return inner

    normalized = re.sub(r"\(([^()]*)\)", drop_nonlegal_parenthetical, raw)
    normalized = re.sub(r"[\s\[\]{}()·,._-]+", "", normalized)
    return normalized[:80]


def _precedent_dedupe_key(precedent: dict[str, Any]) -> str:
    case_number = str(precedent.get("caseNumber") or "").strip()
    precedent_id = str(precedent.get("precedentId") or "").strip()
    identity_name = _precedent_identity_name(precedent)
    if case_number and identity_name:
        return f"case:{case_number}|name:{identity_name}"
    if case_number:
        return f"case:{case_number}|id:{precedent_id}"
    return f"id:{precedent_id}"


def _dedupe_selected_precedents(precedents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best_by_key: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    def merge_aliases(target: dict[str, Any], source: dict[str, Any]) -> None:
        target_id = str(target.get("precedentId") or "").strip()
        aliases = [str(item).strip() for item in (target.get("alternatePrecedentIds") or []) if str(item).strip()]
        for alias in [source.get("precedentId"), *(source.get("alternatePrecedentIds") or [])]:
            alias_id = str(alias or "").strip()
            if alias_id and alias_id != target_id and alias_id not in aliases:
                aliases.append(alias_id)
        if aliases:
            target["alternatePrecedentIds"] = aliases

    for precedent in precedents:
        key = _precedent_dedupe_key(precedent)
        if not key:
            continue
        if key not in order:
            order.append(key)
        current = best_by_key.get(key)
        if current is None:
            best_by_key[key] = precedent
        elif _precedent_quality_score(precedent) > _precedent_quality_score(current):
            merge_aliases(precedent, current)
            best_by_key[key] = precedent
        else:
            merge_aliases(current, precedent)
    return [best_by_key[key] for key in order if key in best_by_key]


def _selected_precedents_by_id(selected_precedents: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for item in selected_precedents:
        ids = [item.get("precedentId"), *(item.get("alternatePrecedentIds") or [])]
        for raw_id in ids:
            precedent_id = str(raw_id or "").strip()
            if precedent_id:
                by_id[precedent_id] = item
    return by_id


_HTML_BREAK_PATTERN = re.compile(r"<br\s*/?>", re.IGNORECASE)


def _normalize_html_breaks(text: str) -> str:
    """Convert literal HTML <br/>, <br>, <br /> tags in precedent text to newlines.

    The DB contains ~140k precedents with <br> tags that render as literals in
    the React Native Text component. We normalize at detail build time so both
    the displayed body and quote-matching use the same text.
    """
    if not text:
        return text
    return _HTML_BREAK_PATTERN.sub("\n", text)


# Source attribution markers (casenote / lbox / law-n / kasan / lawnb / 로앤비
# 등) that some upstream ingestions leave at the head/foot or interspersed in
# precedent body. They expose where the row was ingested from and create an
# obvious traceability fingerprint. We strip them at display time only — the
# underlying SQLite DB is untouched, so this is fully reversible.
_SOURCE_MARKER_PATTERNS = [
    re.compile(r"\b(?:casenote\.kr|casenote\.com|casenote)\b", re.IGNORECASE),
    # Match `lbox`/`lbox.kr` BUT NOT `LBOX 익명화` — that suffix is our own
    # display label for anonymized LBOX rows and must survive stripping.
    re.compile(r"\b(?:lbox\.kr|lbox\.co\.kr|lbox(?!\s*익명화))\b", re.IGNORECASE),
    re.compile(r"\b(?:law-n\.com|lawnb\.com|lawnb|로앤비)\b", re.IGNORECASE),
    re.compile(r"\b(?:kasan\.kr|kasan)\b", re.IGNORECASE),
    re.compile(r"\b(?:scourt\.go\.kr|국가법령정보센터|law\.go\.kr)\b", re.IGNORECASE),
    # `[판례 172]`, `[판례172]`, `(판례 172)` annotation markers used by some
    # ingest pipelines. They are not part of the original ruling body.
    re.compile(r"[\[\(]\s*판례\s*\d+\s*[\]\)]"),
    # `URL: https://...` (and triple-slash `https:///<URL-encoded>` variant)
    # leaks from `lawlaw` and similar source headers. The path may be
    # %-encoded Korean court names — strip the entire URL token.
    re.compile(r"\bURL\s*[:：]?\s*https?://\S+", re.IGNORECASE),
    re.compile(r"https?:///\S+"),
    # Standalone source attribution lines like `제목: …` / `날짜: …` /
    # `--------` that some ingestions prepend before the actual judgment
    # body. They expose the ingestion shape, not the case content.
    re.compile(r"^\s*제목\s*[:：][^\n]+$", re.MULTILINE),
    re.compile(r"^\s*날짜\s*[:：][^\n]+$", re.MULTILINE),
    re.compile(r"^\s*-{4,}\s*$", re.MULTILINE),
    # Footer-style "© ... 판례 N" or "출처: ..." lines.
    re.compile(r"^\s*(?:출처|Source|Provided by|Copyright|©|\(c\))\s*[:：].*$", re.IGNORECASE | re.MULTILINE),
]

# Common Korean section headers wrapped in 【...】, ===...===, ---...--- styles.
# Different ingestions wrap them differently — that itself is a fingerprint.
# Display-time we unify to a simple `[제목]` form so all rows look the same
# without losing the section semantics.
_SECTION_BRACKET_PATTERN = re.compile(r"【\s*([^】\n]{1,30}?)\s*】")
_SECTION_DIVIDER_PATTERN = re.compile(
    r"^[ \t]*[=\-]{3,}[ \t]*([가-힣A-Za-z][^\n]{0,28}?)[ \t]*[=\-]{3,}[ \t]*$",
    re.MULTILINE,
)


def _strip_source_markers(text: str) -> str:
    """Remove ingestion-source watermarks + section-style fingerprints from
    displayed precedent text. Strictly textual, runs after html-break
    normalization, never touches stored DB data.
    """
    if not text:
        return text
    out = text
    for pattern in _SOURCE_MARKER_PATTERNS:
        out = pattern.sub("", out)
    # Unify `【주 문】`, `【주  문】`, `【  이유  】` → `[주문]`, `[이유]`.
    out = _SECTION_BRACKET_PATTERN.sub(lambda m: f"[{re.sub(r"\s+", "", m.group(1))}]", out)
    # Unify `--- 주문 ---`, `=== 이유 ===` etc. → `[주문]`, `[이유]`.
    out = _SECTION_DIVIDER_PATTERN.sub(lambda m: f"[{re.sub(r"\s+", "", m.group(1))}]", out)
    # Collapse 3+ blank lines that result from header/footer removal so the
    # body doesn't suddenly look gappy.
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def _find_quote_range(full_text: str, quote: str) -> tuple[int | None, int | None]:
    if not full_text or not quote:
        return None, None
    idx = full_text.find(quote)
    if idx >= 0:
        return idx, idx + len(quote)
    normalized_quote = " ".join(quote.split())
    if not normalized_quote:
        return None, None
    normalized_text, original_indices = _normalized_index(full_text)
    idx = normalized_text.find(normalized_quote)
    if idx >= 0:
        end_idx = min(idx + len(normalized_quote) - 1, len(original_indices) - 1)
        return original_indices[idx], original_indices[end_idx] + 1
    # 사용자 요구: "글자 몇개 띄어쓰기 몇개 차이" 인용을 가장 비슷한 문장으로
    # 강제 매칭. 직접/정규화 매칭이 실패해도 trigram 유사도 기반으로 가장
    # 가까운 문장 단위 후보를 잡아 highlight charStart/charEnd를 채워준다.
    fuzzy = _fuzzy_locate_quote_in_full_text(full_text, normalized_quote)
    if fuzzy is not None:
        return fuzzy
    return None, None


def _split_full_text_sentences(full_text: str) -> list[tuple[str, int, int]]:
    """Split precedent text into sentence-ish chunks with offsets."""
    if not full_text:
        return []
    out: list[tuple[str, int, int]] = []
    cursor = 0
    length = len(full_text)
    i = 0
    while i < length:
        ch = full_text[i]
        terminator = ch in (".", "?", "!", "\n")
        if not terminator and ch == "다":
            nxt = full_text[i + 1] if i + 1 < length else ""
            terminator = bool(nxt) and nxt in " \t\n.?!,;:、。)」』”’"
        if terminator:
            end = i + 1
            while end < length and full_text[end] in " \t\n.?!":
                end += 1
            segment = full_text[cursor:end]
            if len(segment.strip()) >= 8:
                out.append((segment, cursor, end))
            cursor = end
            i = end
            continue
        i += 1
    if cursor < length:
        tail = full_text[cursor:]
        if len(tail.strip()) >= 8:
            out.append((tail, cursor, length))
    return out


def _trigrams(value: str) -> set[str]:
    compact = re.sub(r"\s+", "", value)
    return {compact[i : i + 3] for i in range(len(compact) - 2)}


def _fuzzy_locate_quote_in_full_text(full_text: str, normalized_quote: str) -> tuple[int, int] | None:
    candidates = _split_full_text_sentences(full_text)
    if not candidates or len(normalized_quote) < 6:
        return None
    needle_grams = _trigrams(normalized_quote)
    if not needle_grams:
        return None
    best_score = 0.0
    best_range: tuple[int, int] | None = None
    best_sentence: str = ""
    for sentence, start, end in candidates:
        cand_grams = _trigrams(sentence)
        if not cand_grams:
            continue
        common = len(needle_grams & cand_grams)
        score = common / min(len(needle_grams), len(cand_grams))
        if score > best_score:
            best_score = score
            best_range = (start, end)
            best_sentence = sentence
    if best_range is None or best_score < 0.18:
        return None
    # Tighten highlight bounds to where the quote actually begins/ends inside
    # the matched sentence. The sentence-level range often spans connector
    # text before the quote (e.g. `"할 것이며, "` prefix) — trimming to the
    # quote start gives the user a precise highlight, not the whole sentence.
    sent_start, sent_end = best_range
    refined_start, refined_end = _refine_quote_offsets_in_sentence(best_sentence, normalized_quote, sent_start, sent_end)
    return refined_start, refined_end


def _refine_quote_offsets_in_sentence(sentence: str, normalized_quote: str, sent_start: int, sent_end: int) -> tuple[int, int]:
    if not sentence or not normalized_quote:
        return sent_start, sent_end
    # Try to find the first ~10 chars of the quote (with whitespace tolerance)
    # inside the matched sentence; if found, shift start to that index.
    head = normalized_quote[: min(12, len(normalized_quote))].strip()
    if head:
        head_compact = re.sub(r"\s+", "", head)
        sentence_compact = re.sub(r"\s+", "", sentence)
        idx = sentence_compact.find(head_compact)
        if idx > 0:
            # Map compact-index back to original sentence offset by walking
            # through the sentence and counting non-space characters.
            mapped = 0
            seen_non_space = 0
            for offset, ch in enumerate(sentence):
                if seen_non_space == idx:
                    mapped = offset
                    break
                if not ch.isspace():
                    seen_non_space += 1
            else:
                mapped = 0
            # Skip leading whitespace so the highlight begins on the first
            # actual quote character, not the space-after-connector.
            while mapped < len(sentence) and sentence[mapped].isspace():
                mapped += 1
            return sent_start + mapped, sent_end
    return sent_start, sent_end


def _normalized_index(text: str) -> tuple[str, list[int]]:
    chars: list[str] = []
    indices: list[int] = []
    previous_space = False
    for index, char in enumerate(text):
        if char.isspace():
            if chars and not previous_space:
                chars.append(" ")
                indices.append(index)
            previous_space = True
            continue
        chars.append(char)
        indices.append(index)
        previous_space = False
    if chars and chars[-1] == " ":
        chars.pop()
        indices.pop()
    return "".join(chars), indices


def _normalize_overlay_body(text: str) -> str:
    cleaned = _clean_display_text(text, limit=260)
    cleaned = re.sub(r"^(판례\s*요약)\s*", "", cleaned)
    cleaned = re.sub(r"(판례\s*요약)\s*", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _dedupe_sentences(text: str) -> str:
    chunks = [chunk.strip() for chunk in re.split(r"(?<=[\.\?!다])\s+", str(text or "").strip()) if chunk.strip()]
    seen: set[str] = set()
    ordered: list[str] = []
    for chunk in chunks:
        normalized = re.sub(r"\s+", " ", chunk).strip()
        if normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(chunk)
    return " ".join(ordered).strip()


def _truncate_clean_text(text: str, *, limit: int = 140) -> str:
    cleaned = _clean_display_text(text, limit=max(limit * 2, 320))
    if len(cleaned) <= limit:
        return cleaned
    clipped = cleaned[:limit].rsplit(" ", 1)[0].strip()
    return f"{clipped or cleaned[:limit].strip()}…"


def _rewrite_beta7_answer_markdown(markdown: str, claim_ledger: list[dict[str, Any]]) -> str:
    """Minimal Beta-7 post-pass.

    1) Substitute writer-emitted citation tokens (`[3]`, `[3-S2]`).
    2) Strip CLAIM-NNN debug echoes the writer sometimes copies from prompt.
    3) Strip orphan `**` (odd count per line).
    4) Annotate `(LBOX 익명화)` with `[prd:XXX]` so it hyperlinks.
    5) Final whitespace tidy.

    Compare with `_rewrite_answer_markdown_citations` which runs 14 passes
    for older modes (most of which the DB sweep + new prompt obviated).
    """
    if not markdown:
        return markdown
    rewritten = _substitute_writer_citation_tokens(markdown, claim_ledger)
    # Strip CLAIM-NNN id leaks (writer occasionally echoes from the ledger).
    rewritten = re.sub(r"\s*\(\s*(?:CLAIM-\d+\s*[,;]\s*)*CLAIM-\d+\s*\)", "", rewritten)
    rewritten = re.sub(r"\bCLAIM-\d+\b", "", rewritten)
    rewritten = re.sub(r"\(\s*[,;\s]*\)", "", rewritten)
    # Drop runaway `**` openers/closers without scrambled-term repositioning.
    fixed: list[str] = []
    for line in rewritten.splitlines():
        if line.count("**") % 2 == 1:
            line = line[::-1].replace("**"[::-1], "", 1)[::-1]
        fixed.append(line)
    rewritten = "\n".join(fixed)
    rewritten = _fix_glossary_literal_term_label(rewritten)
    rewritten = _split_glossary_paragraphs(rewritten)
    rewritten = _unbold_citation_parens(rewritten)
    rewritten = _flatten_nested_case_name_parens(rewritten)
    rewritten = _collapse_identified_citations_to_case_number(rewritten)
    rewritten = _collapse_identified_citation_text_to_case_number(rewritten)
    rewritten = _drop_sparse_citation_case_name_suffix(rewritten)
    rewritten = _remove_orphan_reference_notes(rewritten)
    rewritten = _split_inline_citation_quotes(rewritten)
    rewritten = _remove_adjacent_duplicate_quotes(rewritten)
    rewritten = _annotate_lbox_citations_with_precedent_id(rewritten, claim_ledger)
    rewritten = _normalize_public_answer_sections(rewritten)
    rewritten = re.sub(r"\n{3,}", "\n\n", rewritten)
    return rewritten.strip()


_GLOSSARY_LINE = re.compile(r"^\s*\*\*[^*\n]{1,40}\*\*\s*[:：]")


# `**(서울지법 ... 판결 (손해배상(기)))**` → `(서울지법 ... 판결 (손해배상(기)))`.
# Bolding parenthetical citations adds no information and produces visual
# noise like `)))` because the case_name itself is parenthesized.
_BOLD_PAREN_GROUP = re.compile(r"\*\*\s*(\([^*\n]{1,300}\))\s*\*\*")


def _unbold_citation_parens(markdown: str) -> str:
    if not markdown:
        return markdown
    return _BOLD_PAREN_GROUP.sub(lambda m: m.group(1), markdown)


# Citation form `(법원 ... 판결 (case_name(stat)))` produces `)))` because the
# case_name itself often contains a parenthesized statute reference like
# `손해배상(기)`. Convert the inner case_name wrapper parens to brackets so
# the visible form becomes `(법원 ... 판결 [case_name(stat)])`.
_NESTED_CASE_NAME_IN_CITATION = re.compile(
    r"(\([^()\n]{6,160}판결)\s*\(([^()\n]{0,80}(?:\([^()\n]{0,40}\)[^()\n]{0,80})?)\)\)"
)


def _flatten_nested_case_name_parens(markdown: str) -> str:
    if not markdown:
        return markdown
    return _NESTED_CASE_NAME_IN_CITATION.sub(lambda m: f"{m.group(1)} [{m.group(2)}])", markdown)


# Matches `(citation) "quote"` and accepts arbitrary nesting inside the
# citation parens (case_names like `손해배상(기)` produce two-level nesting).
# The `\)` anchors the last close-paren immediately before the opening
# quote, and the citation body excludes only quotes/newlines so nested
# parens are tolerated. Splits the quote onto its own blockquote paragraph
# for readability.
_INLINE_CITATION_QUOTE = re.compile(
    r"(\([^\"”\n]{4,400}\))\s*[\"“]([^\"”\n]{8,1200})[\"”]\s*([.,;:!?。、，；：！？]?)"
)


def _split_inline_citation_quotes(markdown: str) -> str:
    """Move inline `(cite) "quote"` quotes onto their own `> quote` blockquote
    paragraph. The writer prompt now forbids inline quotes, but legacy data
    and occasional regressions still emit them — this normalizes them so the
    final answer always reads with quotes visually separated. Trailing
    sentence punctuation (`.`, `,` …) is folded into the citation line so a
    bare `.` does not end up alone on its own paragraph.
    """
    if not markdown:
        return markdown

    def _sub(match: re.Match[str]) -> str:
        citation = match.group(1)
        quote = match.group(2).strip()
        tail = match.group(3) or ""
        return f"{citation}{tail}\n\n> {quote}\n\n"

    return _INLINE_CITATION_QUOTE.sub(_sub, markdown)


def _split_glossary_paragraphs(markdown: str) -> str:
    """Insert a blank line between consecutive `**term**: 정의` lines.

    The writer occasionally emits multiple glossary entries on consecutive
    lines without a blank separator. CommonMark renders single `\\n` as a
    soft break, so the frontend paragraph buffer joins them with a space and
    the glossary collapses into one run-on paragraph. Forcing a blank line
    between adjacent glossary lines keeps each term as its own paragraph
    without otherwise touching the content.
    """
    if not markdown:
        return markdown
    lines = markdown.split("\n")
    out: list[str] = []
    for index, line in enumerate(lines):
        out.append(line)
        if _GLOSSARY_LINE.match(line):
            nxt = lines[index + 1] if index + 1 < len(lines) else ""
            if _GLOSSARY_LINE.match(nxt):
                out.append("")
    return "\n".join(out)


_FULL_IDENTIFIED_CITATION = re.compile(
    r"\(\s*"
    r"(?:[가-힣A-Za-z0-9·\s]{0,80}?(?:법원|법|지법|지원|재판소)\s+)?"
    r"(?:\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.?\s+)?"
    r"(?:선고\s*)?"
    r"(?P<case>\d{2,4}\s*[가-힣]{1,4}\s*\d{1,6}(?:\s*,\s*\d{1,6})*)"
    r"\s*판결"
    r"(?:\s*\[[^\]\n]{1,120}\])?"
    r"(?P<anchor>\s*\[prd:[a-f0-9-]+\])?"
    r"\s*\)"
)


def _collapse_identified_citations_to_case_number(markdown: str) -> str:
    """Render user-facing identified citations as `사건번호 판결` only.

    The upstream DB may contain court/date/case-name fields inferred from
    body text. Even when the case number is useful for hyperlinking, the
    polished court/date wrapper can be wrong, so the display layer refuses to
    preserve it.
    """
    if not markdown:
        return markdown

    def _replace(match: re.Match[str]) -> str:
        case_number = _clean_display_text(match.group("case") or "", limit=60)
        anchor = match.group("anchor") or ""
        return f"({case_number} 판결{anchor})" if case_number else "(참조 판례)"

    return _FULL_IDENTIFIED_CITATION.sub(_replace, markdown)


_IDENTIFIED_CITATION_TEXT = re.compile(
    r"(?P<court>(?:대법원|헌법재판소|[가-힣]{2,12}(?:고등|지방|행정|가정|회생)?법원|[가-힣]{2,12}행법|[가-힣]{2,12}지법(?:[ \t]+[가-힣]{2,12}지원)?|[가-힣]{2,12}지원))[ \t]+"
    r"(?:\d{4}\.[ \t]*\d{1,2}\.[ \t]*\d{1,2}\.?[ \t]+)?"
    r"(?:선고[ \t]*)?"
    r"(?P<case>\d{2,4}\s*[가-힣]{1,4}\s*\d{1,6}(?:\s*,\s*\d{1,6})*)"
    r"\s*판결"
    r"(?:\s*\([^()\n]{1,160}\))?"
)


def _collapse_identified_citation_text_to_case_number(markdown: str) -> str:
    """Collapse bare full citation text outside parentheses too.

    Upstream date/court/case-name fields may come from rule-based extraction,
    so even when the case number is useful for lookup the polished envelope is
    not safe to display.
    """
    if not markdown:
        return markdown

    def _replace(match: re.Match[str]) -> str:
        case_number = _clean_display_text(match.group("case") or "", limit=60)
        return f"{case_number} 판결" if case_number else "참조 판례"

    return _IDENTIFIED_CITATION_TEXT.sub(_replace, markdown)


_SPARSE_CITATION_CASE_NAME_SUFFIX = re.compile(
    r"(?P<cite>\b\d{2,4}\s*[가-힣]{1,4}\s*\d{1,6}(?:\s*,\s*\d{1,6})*\s*판결)"
    r"\s*\([^()\n]{1,160}(?:\([^()\n]{1,80}\)[^()\n]{0,80})?\)"
)


def _drop_sparse_citation_case_name_suffix(markdown: str) -> str:
    if not markdown:
        return markdown
    return _SPARSE_CITATION_CASE_NAME_SUFFIX.sub(lambda m: m.group("cite"), markdown)


_CLAIM_DEBUG_PAREN = re.compile(r"\s*\(\s*(?:CLAIM-\d+\s*[,;]\s*)*CLAIM-\d+\s*\)")


def _strip_claim_debug_ids(text: str) -> str:
    if not text:
        return ""
    cleaned = _CLAIM_DEBUG_PAREN.sub("", str(text))
    cleaned = re.sub(r"\bCLAIM-\d+\b", "", cleaned)
    cleaned = re.sub(r"\(\s*[,;\s]*\)", "", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,.。])", r"\1", cleaned)
    return cleaned.strip()


_ORPHAN_REFERENCE_NOTE = re.compile(
    r"(?m)^\s*(?:또한|더불어|아울러)\s+\*{0,2}\(\s*참조\s*판례\s*\)\*{0,2}\s*역시[^\n]*(?:\n+|$)"
)


def _remove_orphan_reference_notes(markdown: str) -> str:
    """Drop generic `(참조 판례)` filler lines that cannot hyperlink.

    This is not case-specific. If a row cannot expose a verified case number
    or a `[prd:...]` token, it should stay in the drawer/list as an anonymous
    source, not be injected into body prose as an unclickable pseudo-citation.
    """
    if not markdown:
        return markdown
    return _ORPHAN_REFERENCE_NOTE.sub("", markdown)


def _quote_dedupe_key(text: str) -> str:
    cleaned = _normalize_space(text)
    cleaned = cleaned.strip("\"'“”‘’")
    cleaned = re.sub(r"^[>\\s]+", "", cleaned).strip()
    cleaned = cleaned.strip("\"'“”‘’")
    cleaned = re.sub(r"[\"'“”‘’]", "", cleaned)
    cleaned = re.sub(r"\s+", "", cleaned)
    return cleaned


def _remove_adjacent_duplicate_quotes(markdown: str) -> str:
    if not markdown:
        return markdown
    lines = markdown.splitlines()
    out: list[str] = []
    recent_quote_key = ""
    blank_after_quote = 99
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(">"):
            current_quote_key = _quote_dedupe_key(stripped.lstrip(">").strip())
            is_duplicate_quote = (
                recent_quote_key
                and blank_after_quote <= 2
                and current_quote_key
                and (
                    current_quote_key == recent_quote_key
                    or (
                        min(len(current_quote_key), len(recent_quote_key)) >= 16
                        and (current_quote_key in recent_quote_key or recent_quote_key in current_quote_key)
                    )
                )
            )
            if is_duplicate_quote:
                continue
            recent_quote_key = current_quote_key
            blank_after_quote = 0
            out.append(line)
            continue
        if recent_quote_key:
            if not stripped:
                blank_after_quote = min(blank_after_quote + 1, 2)
                out.append(line)
                continue
            current_key = _quote_dedupe_key(stripped)
            is_duplicate_quote = (
                blank_after_quote <= 2
                and current_key
                and (
                    current_key == recent_quote_key
                    or (
                        min(len(current_key), len(recent_quote_key)) >= 16
                        and (current_key in recent_quote_key or recent_quote_key in current_key)
                    )
                )
            )
            if is_duplicate_quote:
                continue
            recent_quote_key = ""
            blank_after_quote = 99
        out.append(line)
    return "\n".join(out)


def _collapse_blank_runs(lines: list[str]) -> list[str]:
    out: list[str] = []
    previous_blank = False
    for line in lines:
        blank = not line.strip()
        if blank and previous_blank:
            continue
        out.append(line)
        previous_blank = blank
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return out


def _move_glossary_lines_to_overview_end(markdown: str) -> str:
    """Keep glossary terms at the bottom of the easy overview section."""
    if not markdown:
        return markdown
    lines = markdown.split("\n")
    start = -1
    for index, line in enumerate(lines):
        if re.match(r"^\s*##\s*(?:한눈에 보는 결론|어렵지 않아요)\s*$", line):
            start = index
            break
    if start < 0:
        return markdown
    end = len(lines)
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if stripped == "---" or re.match(r"^##\s+", stripped):
            end = index
            break
    body = lines[start + 1 : end]
    glossary = [line.strip() for line in body if _GLOSSARY_LINE.match(line.strip())]
    if not glossary:
        return markdown
    main = _collapse_blank_runs([line for line in body if not _GLOSSARY_LINE.match(line.strip())])
    rebuilt = main[:]
    if rebuilt:
        rebuilt.append("")
    rebuilt.extend(glossary)
    return "\n".join(lines[: start + 1] + rebuilt + lines[end:])


def _normalize_public_answer_sections(markdown: str) -> str:
    if not markdown:
        return markdown
    rewritten = _move_glossary_lines_to_overview_end(markdown)
    rewritten = re.sub(r"(?m)^##\s*한눈에 보는 결론\s*$", "## 어렵지 않아요", rewritten)
    rewritten = re.sub(r"(?m)^##\s*법조인용 상세 분석\s*$", "## 상세 분석", rewritten)
    return rewritten


def _rewrite_answer_markdown_citations(markdown: str, claim_ledger: list[dict[str, Any]]) -> str:
    rewritten = str(markdown or "")
    evidence_map: dict[str, str] = {}
    evidence_prefix_map: dict[str, str] = {}
    claim_id_map: dict[str, str] = {}
    for claim in claim_ledger:
        citation = str(claim.get("citation") or "").strip() or _first_supporting_case_citation(claim)
        if not citation:
            citation = _build_precedent_citation(
                {
                    "court": claim.get("court"),
                    "decision_date": claim.get("decision_date"),
                    "case_number": claim.get("case_number"),
                    "case_name": claim.get("case_name"),
                }
            )
        claim_id_raw = str(claim.get("claim_id") or "").strip()
        if claim_id_raw and citation:
            claim_id_map[claim_id_raw] = citation
        for span in claim.get("support_spans") or []:
            evidence_id = str(span.get("evidence_id") or "").strip()
            if evidence_id and citation:
                evidence_map[evidence_id] = citation
                evidence_prefix_map[evidence_id.split("-근거", 1)[0]] = citation
    for evidence_id, citation in evidence_map.items():
        rewritten = re.sub(rf"\[\s*{re.escape(evidence_id)}\s*\]", f"**({citation})**", rewritten)
        rewritten = re.sub(rf"(?<!\\S){re.escape(evidence_id)}(?!\\S)", citation, rewritten)
    for prefix, citation in evidence_prefix_map.items():
        rewritten = re.sub(rf"\[\s*{re.escape(prefix)}-근거\d+\s*\]", f"**({citation})**", rewritten)
        rewritten = re.sub(rf"\[\s*prd-[A-Za-z0-9-]+-근거\d+\s*\]", "", rewritten)
    rewritten = re.sub(r"근거\s*인용\s*", "", rewritten)
    rewritten = re.sub(r"\(\s*출처\s*미상\s*\)", "", rewritten)
    rewritten = re.sub(r"출처\s*미상", "", rewritten)
    rewritten = re.sub(r"\*\*\s*\*\*", "", rewritten)
    rewritten = re.sub(r"\[\s*(?:prd-[A-Za-z0-9-]+|[0-9가-힣()누구합단도재마나카허저]+-근거\d+)\s*\]", "", rewritten)
    rewritten = re.sub(r"prd-[A-Za-z0-9-]+-근거\d+", "", rewritten)
    rewritten = re.sub(r"[0-9가-힣()누구합단도재마나카허저]+-근거\d+", "", rewritten)
    # Replace CLAIM-NNN tokens with their citation when possible, then strip any remnants.
    for claim_id, citation in claim_id_map.items():
        rewritten = re.sub(rf"\[\s*{re.escape(claim_id)}\s*\]", f"**({citation})**", rewritten)
        rewritten = re.sub(rf"\*\*\s*{re.escape(claim_id)}\s*\*\*", f"**({citation})**", rewritten)
        rewritten = re.sub(rf"\b{re.escape(claim_id)}\b", citation, rewritten)
    rewritten = re.sub(r"\[\s*CLAIM-\d+\s*\]", "", rewritten)
    rewritten = re.sub(r"\*\*\s*CLAIM-\d+\s*\*\*", "", rewritten)
    # Also strip parens-wrapped lists of CLAIM-IDs that the LLM occasionally
    # appends to bullet sentences as "(CLAIM-008, CLAIM-010, CLAIM-004)".
    # We remove the entire suffix-paren block when its contents are nothing
    # but CLAIM-IDs (and commas/spaces). Run BEFORE the single-token strip.
    rewritten = re.sub(r"\s*\(\s*(?:CLAIM-\d+\s*[,;]\s*)*CLAIM-\d+\s*\)", "", rewritten)
    rewritten = re.sub(r"\bCLAIM-\d+\b", "", rewritten)
    # Cleanup leftover empty/comma-only parens after CLAIM token removal.
    rewritten = re.sub(r"\(\s*[,;\s]*\)", "", rewritten)
    rewritten = re.sub(r",\s*,", ",", rewritten)
    rewritten = re.sub(r"\(\s*,", "(", rewritten)
    rewritten = re.sub(r",\s*\)", ")", rewritten)
    rewritten = re.sub(r"[ \t]+([,.、。·…])", r"\1", rewritten)
    rewritten = re.sub(r"\(\s*\)", "", rewritten)
    rewritten = re.sub(r"\*\*\s*\*\*", "", rewritten)
    rewritten = re.sub(r"\n{3,}", "\n\n", rewritten)
    # Token substitution must run BEFORE date/citation normalization so
    # the substituted citations get the same downstream cleanup as
    # LLM-emitted ones.
    rewritten = _substitute_writer_citation_tokens(rewritten, claim_ledger)
    rewritten = _normalize_markdown_dates(rewritten)
    rewritten = _scrub_unreliable_inline_citations(rewritten, claim_ledger)
    rewritten = _collapse_lbox_anonymized_citations(rewritten)
    rewritten = _collapse_redundant_relation_suffix(rewritten)
    rewritten = _fix_glossary_literal_term_label(rewritten)
    rewritten = _split_glossary_paragraphs(rewritten)
    rewritten = _normalize_orphan_bold(rewritten)
    rewritten = _strip_body_citations_outside_claim_ledger(rewritten, claim_ledger)
    rewritten = _unbold_citation_parens(rewritten)
    rewritten = _flatten_nested_case_name_parens(rewritten)
    rewritten = _collapse_identified_citations_to_case_number(rewritten)
    rewritten = _collapse_identified_citation_text_to_case_number(rewritten)
    rewritten = _drop_sparse_citation_case_name_suffix(rewritten)
    rewritten = _remove_orphan_reference_notes(rewritten)
    rewritten = _split_inline_citation_quotes(rewritten)
    rewritten = _remove_adjacent_duplicate_quotes(rewritten)
    rewritten = _annotate_lbox_citations_with_precedent_id(rewritten, claim_ledger)
    rewritten = _normalize_public_answer_sections(rewritten)
    return rewritten.strip()


_WRITER_CITATION_TOKEN_RE = re.compile(r"\[(\d{1,3})(?:-([SO])(\d{1,3}))?\]")


def _build_writer_claim_token_map(
    claim_ledger: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    """Build the lookup the body-rewrite step uses to translate writer
    tokens like `[3]` / `[3-S2]` / `[5-O1]` into full citations + quotes.
    The 1-based index matches `_writer_claim_index` assigned at claim-id
    assignment time in work16.
    """
    out: dict[str, dict[str, str]] = {}
    for claim in claim_ledger or []:
        idx = claim.get("_writer_claim_index") or 0
        if not idx:
            continue
        case_number = _normalize_space(str(claim.get("case_number") or ""))
        court = _normalize_space(str(claim.get("court") or ""))
        decision_date = _normalize_space(str(claim.get("decision_date") or ""))
        case_name = _normalize_space(str(claim.get("case_name") or ""))
        precedent_id = str(claim.get("source_file_id") or "")
        # Use the same citation builder so LBOX rows collapse to the
        # standard `참조 판례 (LBOX 익명화)` shape.
        citation = _build_precedent_citation(
            {
                "case_number": case_number,
                "court": court,
                "decision_date": decision_date,
                "case_name": case_name,
            }
        )
        anchor = f" [prd:{precedent_id}]" if precedent_id and (case_name == "LBOX 익명화" or citation == "참조 판례") else ""
        primary = f"**({citation}{anchor})**"
        out[f"{idx}"] = {"citation": primary, "quote": ""}
        for span_kind, key_letter in (("support_spans", "S"), ("oppose_spans", "O")):
            for span_idx, span in enumerate(claim.get(span_kind) or [], start=1):
                quote = _normalize_space(str(span.get("quote") or ""))
                out[f"{idx}-{key_letter}{span_idx}"] = {"citation": primary, "quote": quote}
    return out


def _substitute_writer_citation_tokens(
    markdown: str,
    claim_ledger: list[dict[str, Any]],
) -> str:
    """Replace writer-emitted tokens like `[3-S2]` with the full citation
    (and quote, if a span is referenced). Tokens whose key isn't in the
    ledger are stripped entirely so the user never sees raw `[3-S2]`.
    """
    if not markdown:
        return markdown
    token_map = _build_writer_claim_token_map(claim_ledger)
    if not token_map:
        return markdown

    def _replace(match: re.Match[str]) -> str:
        n = match.group(1)
        kind = match.group(2)
        m = match.group(3)
        key = f"{n}-{kind}{m}" if kind else n
        entry = token_map.get(key)
        if not entry:
            return ""  # silently drop unknown tokens
        quote = str(entry.get("quote") or "").strip()
        if quote:
            # Move the quote to its own blockquote paragraph so it doesn't
            # run into surrounding prose. The leading/trailing newlines force
            # CommonMark to start a new paragraph for the blockquote and a
            # new paragraph for whatever follows.
            return f'{entry["citation"]}\n\n> {quote}\n\n'
        return entry["citation"]

    return _WRITER_CITATION_TOKEN_RE.sub(_replace, markdown)


def _annotate_lbox_citations_with_precedent_id(
    markdown: str,
    claim_ledger: list[dict[str, Any]],
) -> str:
    """Append a `[prd-XXXX]` precedent-id token after `(LBOX 익명화)` citations
    in the markdown, so the frontend's hyperlink resolver can link the
    citation to the actual precedent body. LBOX rows have empty
    case_number, so the case-number-based lookup never fires for them.

    Strategy: build a quote-prefix → precedent_id map from claim_ledger's
    LBOX entries (case_name == "LBOX 익명화"), then for each
    `**(LBOX 익명화)**` followed by a quoted sentence in the markdown,
    look up the quote prefix in the map and inject the token.
    """
    if not markdown or not claim_ledger:
        return markdown
    quote_prefix_map: dict[str, str] = {}
    for claim in claim_ledger:
        case_name = _normalize_case_name(str(claim.get("case_name") or ""))
        case_number = _normalize_space(str(claim.get("case_number") or ""))
        precedent_id = str(claim.get("source_file_id") or "")
        # Only inject for genuinely-anonymized rows (LBOX label) — concrete
        # case_number rows already get linked via the standard regex path.
        if not precedent_id or (case_name != "LBOX 익명화" and case_number):
            continue
        for span in claim.get("support_spans") or []:
            quote = _normalize_space(str(span.get("quote") or ""))
            if len(quote) >= 12:
                key = re.sub(r"\s+", "", quote)[:30]
                quote_prefix_map.setdefault(key, precedent_id)
        for span in claim.get("oppose_spans") or []:
            quote = _normalize_space(str(span.get("quote") or ""))
            if len(quote) >= 12:
                key = re.sub(r"\s+", "", quote)[:30]
                quote_prefix_map.setdefault(key, precedent_id)

    if not quote_prefix_map:
        return markdown

    pattern = re.compile(
        r"(\*\*\(\s*(?:참조\s*판례\s*\(\s*)?LBOX\s*익명화\s*\)?\s*\)\*\*)\s*[\"“”]([^\"“”\n]{8,400}?)[\"“”]"
    )

    def _replace(match: re.Match[str]) -> str:
        citation = match.group(1)
        quote = match.group(2).strip()
        compact_prefix = re.sub(r"\s+", "", quote)[:30]
        precedent_id = quote_prefix_map.get(compact_prefix)
        if not precedent_id:
            # Try a longer prefix in case a 30-char window collides.
            for key, pid in quote_prefix_map.items():
                if compact_prefix.startswith(key[:20]) or key.startswith(compact_prefix[:20]):
                    precedent_id = pid
                    break
        if not precedent_id:
            return match.group(0)
        # Inject the precedent_id token inside the parens. Frontend's
        # citation regex picks it up and routes the click to that prd.
        annotated = citation.replace(")**", f" [prd:{precedent_id}])**", 1)
        return f"{annotated}\n\n> {quote}\n\n"

    return pattern.sub(_replace, markdown)


_REFERENCE_LIST_HEADER = re.compile(r"^##\s*참고\s*판례\s*목록\s*$", re.MULTILINE)


def _strip_body_citations_outside_claim_ledger(
    markdown: str,
    claim_ledger: list[dict[str, Any]],
) -> str:
    """In the BODY section (everything before `## 참고 판례 목록`), replace
    any inline citation whose case_number is NOT in `claim_ledger` with
    `**(참조 판례)**`. The writer prompt forbids citing non-claim precedents
    in body, but the LLM occasionally pulls them from `precedent_buckets`
    anyway. Stripping here prevents the user from clicking a body citation
    and landing on an empty drawer.
    """
    if not markdown:
        return markdown
    valid_case_numbers: set[str] = set()
    for claim in claim_ledger or []:
        case_number = re.sub(r"\s+", "", str(claim.get("case_number") or ""))
        if case_number:
            valid_case_numbers.add(case_number)
        for supporting in claim.get("supporting_cases") or []:
            sc_number = re.sub(r"\s+", "", str((supporting or {}).get("case_number") or ""))
            if sc_number:
                valid_case_numbers.add(sc_number)
    # Locate the body/reference-list split — keep the reference list
    # untouched so the writer can still list bucket-only precedents at the
    # closing `## 참고 판례 목록` section.
    split_match = _REFERENCE_LIST_HEADER.search(markdown)
    body_part = markdown[: split_match.start()] if split_match else markdown
    tail_part = markdown[split_match.start():] if split_match else ""

    def _replace(match: re.Match[str]) -> str:
        case = (match.group("case") or "").strip()
        case_clean = re.sub(r"\s+", "", case)
        if case_clean in valid_case_numbers:
            return match.group(0)
        return "**(참조 판례)**"

    body_part = _INLINE_CITATION_PATTERN.sub(_replace, body_part)
    return body_part + tail_part


# Patterns the LLM produces when it interprets the glossary-format
# instruction `**용어**: 일상 풀이` literally — emitting the placeholder string
# `**용어**` instead of substituting the actual term.
_LITERAL_TERM_LABEL = re.compile(
    r"\*\*\s*용어\s*\*\*\s*[:：]\s*([가-힣A-Za-z][가-힣A-Za-z\s·]{0,15}[가-힣A-Za-z])\s*[:：]\s*"
)


def _fix_glossary_literal_term_label(markdown: str) -> str:
    """Rewrite `**용어**: 과실상계: <def>` → `**과실상계**: <def>`.

    The prompt names the glossary format using `**용어**` as a schema
    placeholder; the LLM occasionally copies the placeholder verbatim and
    appends the real term + colon afterwards. This collapses the duplication
    into the intended `**term**: definition` shape.
    """
    if not markdown:
        return markdown
    return _LITERAL_TERM_LABEL.sub(lambda m: f"**{m.group(1).strip()}**: ", markdown)


# Match reference-list lines like
#   `*   참조 판례 (LBOX 익명화) (참조 판례 (LBOX 익명화) 관련)`
# where the LLM repeats the citation inside an `(... 관련)` suffix. The suffix
# adds no information — strip it down to `*   참조 판례 (LBOX 익명화)`.
_REDUNDANT_RELATION_PATTERN = re.compile(
    r"(\([^()\n]{1,80}\))\s*\((?P<inner>[^()\n]{1,160}(?:\([^()\n]{1,40}\))?[^()\n]{0,40})\s*관련\)"
)
_BARE_RELATION_PATTERN = re.compile(
    r"(참조\s*판례)\s*\((?P<inner>[^()\n]{1,80})\s*관련\)"
)


def _collapse_redundant_relation_suffix(markdown: str) -> str:
    """Drop `(... 관련)` parenthetical suffixes when they merely repeat the
    main citation. The LLM emits this in the reference list when it cannot
    identify a distinct related axis (typical for placeholder/anonymized
    rows). Keeping the suffix bloats the list with `참조 판례 (참조 판례 관련)`
    style noise.
    """
    if not markdown:
        return markdown

    def _replace_outer(match: re.Match[str]) -> str:
        # match.group(1) = "(citation parts)"  -- the canonical citation
        # match.group("inner") = the content before "관련" inside the second parens
        canonical = match.group(1)
        inner = (match.group("inner") or "").strip()
        # Strip leading "**" and outer parens from each side, then compare.
        canonical_norm = re.sub(r"\s+", "", canonical.strip("()"))
        inner_norm = re.sub(r"\s+", "", inner)
        # Drop the suffix when the inner text is contained in the canonical
        # citation, OR vice versa (LBOX rows often have inner == canonical).
        if canonical_norm and (inner_norm in canonical_norm or canonical_norm in inner_norm):
            return canonical
        return match.group(0)

    out = _REDUNDANT_RELATION_PATTERN.sub(_replace_outer, markdown)

    def _replace_bare(match: re.Match[str]) -> str:
        inner = (match.group("inner") or "").strip()
        if "참조 판례" in inner or "참조판례" in inner.replace(" ", ""):
            return match.group(1)
        return match.group(0)

    return _BARE_RELATION_PATTERN.sub(_replace_bare, out)


# Match `(<court> <date-or-tokens> <case_number> LBOX 익명화)` patterns the LLM
# composes by reading the source-segment header inside chunk text. The
# `(LBOX 익명화)` suffix is our own anonymization tag, so anything that
# precedes it inside the same parens is fabricated identifying metadata that
# must be stripped to avoid spreading wrong (court|date|case_number) triples.
_LBOX_ANON_CITATION_PATTERN = re.compile(
    r"\(\s*(?P<lead>[^()\n]{1,200}?)\s+LBOX\s*익명화\s*\)"
)


def _collapse_lbox_anonymized_citations(markdown: str) -> str:
    if not markdown:
        return markdown

    def _replace(match: re.Match[str]) -> str:
        lead = (match.group("lead") or "").strip()
        # Only collapse when there's actual identifying content before `LBOX
        # 익명화` — i.e. fabricated court/date/case_number tokens. The bare
        # `(LBOX 익명화)` marker (no lead text) is left untouched.
        if not lead:
            return match.group(0)
        return "(LBOX 익명화)"

    return _LBOX_ANON_CITATION_PATTERN.sub(_replace, markdown)


# Pattern for inline citations like `**(대법원 2019. 1. 13. 선고 2005다24318 판결)**`
# (court, optional date, "선고 case_number 판결", optional case_name parens).
_INLINE_CITATION_PATTERN = re.compile(
    r"\*\*\(\s*(?P<court>[^()]+?)\s+"
    r"(?:\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.?\s+)?"
    r"선고\s*(?P<case>[\w가-힣()]+(?:\s*[-,~]\s*\d+)?)\s*판결"
    r"(?:\s*\([^()]*\))?\s*\)\*\*"
)


def _scrub_unreliable_inline_citations(markdown: str, claim_ledger: list[dict[str, Any]]) -> str:
    """Find inline `**(법원 ... 선고 NNN 판결)**` markers in the markdown and
    drop them down to `**(참조 판례)**` whenever the LLM-emitted citation
    references a case_number whose claim_ledger entry is identified as a
    placeholder row (case_name = '0','1','2', etc.). The LLM saw wrong DB
    metadata at draft time and baked it in; this post-pass scrubs the
    output.
    """
    if not markdown:
        return markdown
    bad_case_numbers: set[str] = set()
    for claim in claim_ledger or []:
        case_name = _normalize_case_name(str(claim.get("case_name") or ""))
        case_number = _normalize_space(str(claim.get("case_number") or ""))
        if case_number and _is_placeholder_case_name(case_name):
            bad_case_numbers.add(case_number)
        for supporting in claim.get("supporting_cases") or []:
            sc_name = _normalize_case_name(str((supporting or {}).get("case_name") or ""))
            sc_number = _normalize_space(str((supporting or {}).get("case_number") or ""))
            if sc_number and _is_placeholder_case_name(sc_name):
                bad_case_numbers.add(sc_number)
    if not bad_case_numbers:
        return markdown

    def _replace(match: re.Match[str]) -> str:
        case = (match.group("case") or "").strip()
        # Strip any trailing whitespace/non-case characters from the matched
        # case identifier before comparing.
        case_clean = re.sub(r"\s+", "", case)
        if case_clean in bad_case_numbers:
            return "**(참조 판례)**"
        return match.group(0)

    return _INLINE_CITATION_PATTERN.sub(_replace, markdown)


def _normalize_space(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def build_precedent_detail(
    precedent: dict[str, Any],
    chunk_outputs: list[dict[str, Any]],
    *,
    precedent_summaries: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    precedent_id = str(precedent.get("precedentId") or "")
    accepted_precedent_ids = {
        item.strip()
        for item in [precedent_id, *(precedent.get("alternatePrecedentIds") or [])]
        if isinstance(item, str) and item.strip()
    }

    def claim_belongs_to_precedent(claim: dict[str, Any], output_file_id: str) -> bool:
        source_file_id = str(claim.get("source_file_id") or output_file_id).strip()
        output_id = str(output_file_id or "").strip()
        return source_file_id in accepted_precedent_ids or output_id in accepted_precedent_ids

    full_text = _strip_source_markers(_normalize_html_breaks(str(precedent.get("fullText") or "")))
    used_quotes: list[dict[str, Any]] = []
    summaries: list[str] = []
    contexts: list[str] = []
    for output in chunk_outputs:
        file_id = str(output.get("file_id") or "")
        claims = output.get("claims_proposed") or []
        for claim in claims:
            if not claim_belongs_to_precedent(claim, file_id):
                continue
            if claim.get("case_summary"):
                summaries.append(str(claim["case_summary"]))
            if claim.get("context_summary"):
                contexts.append(str(claim["context_summary"]))
            for role_key, role_name in (("support_spans", "support"), ("oppose_spans", "oppose")):
                for span in claim.get(role_key) or []:
                    quote = _strip_source_markers(_normalize_html_breaks(str(span.get("quote") or "")))
                    char_start, char_end = _find_quote_range(full_text, quote)
                    used_quotes.append(
                        {
                            "quoteRole": role_name,
                            "quote": quote,
                            "charStart": char_start,
                            "charEnd": char_end,
                            "claimAxis": str(claim.get("claim_axis") or ""),
                            "whyItMatters": str(claim.get("claim_text") or ""),
                            "evidenceId": str(span.get("evidence_id") or ""),
                        }
                    )
    primary_claim: dict[str, Any] | None = None
    for output in chunk_outputs:
        file_id = str(output.get("file_id") or "")
        for claim in output.get("claims_proposed") or []:
            if not claim_belongs_to_precedent(claim, file_id):
                continue
            if primary_claim is None:
                primary_claim = claim
            else:
                if int(claim.get("supporting_case_count") or 0) > int(primary_claim.get("supporting_case_count") or 0):
                    primary_claim = claim

    summary_overlay = next((_normalize_overlay_body(text) for text in summaries if text.strip()), "")
    context_overlay = next((_normalize_overlay_body(text) for text in contexts if text.strip()), "")
    if primary_claim:
        composed = _compose_claim_summary(primary_claim)
        if composed:
            summary_overlay = _normalize_overlay_body(composed)
    if not summary_overlay:
        summary_overlay = next(
            (
                _normalize_overlay_body(
                    f"{claim.get('claim_text') or ''} 결론적으로 {claim.get('context_summary') or ''}",
                )
                for output in chunk_outputs
                for claim in (output.get("claims_proposed") or [])
                if claim_belongs_to_precedent(claim, str(output.get("file_id") or ""))
                and (claim.get("claim_text") or claim.get("context_summary"))
            ),
            "",
        )
    if not context_overlay:
        context_overlay = next(
            (
                _normalize_overlay_body(str(claim.get("context_summary") or claim.get("claim_text") or ""))
                for output in chunk_outputs
                for claim in (output.get("claims_proposed") or [])
                if claim_belongs_to_precedent(claim, str(output.get("file_id") or ""))
                and (claim.get("context_summary") or claim.get("claim_text"))
            ),
            "",
        )
    # Prefer LLM-generated per-precedent summaries from
    # `precedent_summaries.json`. These are produced for EVERY selected
    # precedent (including those without any claims_proposed), so the
    # drawer no longer falls back to raw body header for unclaimed rows.
    if precedent_summaries:
        llm_summary = next(
            (
                precedent_summaries[item]
                for item in [precedent_id, *(precedent.get("alternatePrecedentIds") or [])]
                if isinstance(item, str) and item in precedent_summaries
            ),
            {},
        )
        if not summary_overlay and llm_summary.get("case_summary"):
            summary_overlay = _normalize_overlay_body(str(llm_summary["case_summary"]))
        if not context_overlay and llm_summary.get("context_summary"):
            context_overlay = _normalize_overlay_body(str(llm_summary["context_summary"]))
    # Final fallback: when no claim-derived OR LLM summary exist for this
    # precedent, derive a short snippet from the precedent body so the
    # drawer never shows an empty placeholder. Prefer the precedent's own
    # `excerpt` (already bounded ~220 chars) when present, otherwise scan
    # the full text past structured `[주문]`/`[이유]` markers.
    if not summary_overlay:
        summary_overlay = _derive_full_text_snippet(precedent.get("excerpt"), full_text)
    if not context_overlay:
        context_overlay = _derive_full_text_snippet(precedent.get("excerpt"), full_text)
    return {
        **precedent,
        "fullText": full_text,
        "usedQuotes": used_quotes,
        "summaryOverlay": summary_overlay,
        "contextOverlay": context_overlay,
    }


def _derive_full_text_snippet(excerpt: Any, full_text: str) -> str:
    # Try to derive a clean snippet that skips structured legal headers
    # (`[피고인]`, `[검사]`, `[변호인]`, `[주문]`, `[이유]`, `[범죄사실]`).
    # We need text from after these markers — a useful first paragraph.
    sources = [str(excerpt or ""), str(full_text or "")]
    for source in sources:
        if not source.strip():
            continue
        snippet = _clean_legal_snippet(source)
        if snippet:
            return snippet
    return ""


def _clean_legal_snippet(text: str) -> str:
    if not text:
        return ""
    # Replace inline `[X]` legal markers with spaces so the marker itself
    # doesn't dominate the snippet, then collapse whitespace.
    cleaned = re.sub(r"\[\s*[^\]]{1,30}\s*\]", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return ""
    # Walk through sentences and SKIP boilerplate that has no analytical
    # value (당사자 명단, 주문, 청구취지, 소송비용 등 — these always appear at
    # the head of a Korean ruling but tell the reader nothing about why
    # the case matters). We start collecting once we hit substantive
    # reasoning — typically `이유 / 가. / 1. 사실관계 / 인정사실 / 살피건대 /
    # 따라서 / 그러나 / 결론적으로` or any sentence ≥ 25 chars that does NOT
    # match the boilerplate prefixes.
    boilerplate_prefixes = (
        "원고", "피고", "변호인", "검사", "당사자", "소송대리인", "선정당사자",
        "주 문", "주문", "1. ", "2. ", "3. ", "4. ", "5. ",
        "청구취지", "청 구 취 지", "항소취지", "부대항소취지", "변론종결",
        "소송비용", "원심판결", "이 사건", "위 각 금원",
    )
    sentences = re.split(r"(?<=[。.!?\n])\s+", cleaned)
    out: list[str] = []
    found_substance = False
    for sentence in sentences:
        s = sentence.strip()
        if not s:
            continue
        # Skip pure-numeric/legal-header lines (e.g. "1. 원고들의 청구를 모두
        # 기각한다." 처럼 짧고 정보가 적은 주문 항목).
        if not found_substance:
            is_boilerplate = any(s.startswith(p) for p in boilerplate_prefixes)
            # Money amounts list (원고 1에게 금 95,420,723원 …) is also boilerplate.
            if re.match(r"^[가-힣\s\d,.]*(?:원|금|일|평\d|호)\s*$", s):
                is_boilerplate = True
            if is_boilerplate and len(s) < 80:
                continue
            found_substance = True
        out.append(s)
        if sum(len(t) for t in out) > 200:
            break
    snippet = " ".join(out).strip()
    if not snippet:
        # Fall back to the original cleaned text if every sentence got
        # filtered. Better to show *something* than an empty drawer.
        snippet = cleaned[:300]
    return snippet[:297] + "…" if len(snippet) > 300 else snippet


def _compose_claim_summary(claim: dict[str, Any]) -> str:
    case_summary = _clean_display_text(str(claim.get("case_summary") or ""), limit=220)
    claim_text = _clean_display_text(str(claim.get("claim_text") or ""), limit=180)
    stance = _clean_display_text(str(claim.get("stance_to_user_goal") or ""), limit=20)
    supporting_case_count = int(claim.get("supporting_case_count") or 0)
    joined = case_summary or claim_text or ""
    if not joined:
        return ""
    if not joined.startswith("결론적으로"):
        joined = f"결론적으로 {joined}"
    if stance == "유리":
        joined = f"{joined} 현재 자료상 질문자에게 유리한 방향으로 작용할 가능성이 높다."
    elif stance == "불리":
        joined = f"{joined} 현재 자료상 질문자에게 불리하게 작용할 가능성이 높다."
    if supporting_case_count >= 2:
        examples: list[str] = []
        for supporting_case in claim.get("supporting_cases") or []:
            case_number = str(supporting_case.get("case_number") or "").strip()
            if case_number and case_number not in examples:
                examples.append(case_number)
            if len(examples) >= 2:
                break
        if examples:
            joined = f"{joined} 특히 {', '.join(examples)} 등 {supporting_case_count}건 안팎의 판례가 같은 방향으로 반복적으로 뒷받침하므로 신뢰도가 높다."
        else:
            joined = f"{joined} 이 논리는 복수 판례가 같은 방향으로 반복적으로 뒷받침하므로 신뢰도가 높다."
    return _dedupe_sentences(joined)


def _strip_user_direction_sentence(text: str) -> str:
    stripped = re.sub(
        r"\s*현재\s+자료상\s+질문자에게\s+(?:유리한\s+방향으로|불리하게)(?:\s+작용할\s+가능성이\s+높다)?[\.…]*",
        "",
        str(text or ""),
    ).strip()
    return re.sub(r"\s{2,}", " ", stripped)


def _compose_precedent_card_summary(claim: dict[str, Any]) -> str:
    lead = _truncate_clean_text(
        str(claim.get("case_summary") or claim.get("claim_text") or claim.get("context_summary") or ""),
        limit=130,
    )
    if not lead:
        return ""
    tags: list[str] = []
    stance = _clean_display_text(str(claim.get("stance_to_user_goal") or ""), limit=20)
    if stance == "유리":
        tags.append("유리 근거")
    elif stance == "불리":
        tags.append("불리 근거")
    if tags:
        return f"{lead} ({' · '.join(tags)})"
    return lead


def _build_case_summary_map(claim_ledger: list[dict[str, Any]]) -> dict[str, str]:
    summary_by_case: dict[str, str] = {}
    for claim in claim_ledger:
        joined = _compose_claim_summary(claim)
        if not joined:
            continue
        top_case = str(claim.get("case_number") or "").strip()
        if top_case and top_case not in summary_by_case:
            summary_by_case[top_case] = joined
        for supporting_case in claim.get("supporting_cases") or []:
            case_number = str(supporting_case.get("case_number") or "").strip()
            if case_number and case_number not in summary_by_case:
                summary_by_case[case_number] = joined
    return summary_by_case


def _build_source_summary_map(claim_ledger: list[dict[str, Any]]) -> dict[str, str]:
    summary_by_source: dict[str, str] = {}
    for claim in claim_ledger:
        source_file_id = str(claim.get("source_file_id") or "").strip()
        summary = _compose_claim_summary(claim)
        if source_file_id and summary and source_file_id not in summary_by_source:
            summary_by_source[source_file_id] = summary
    return summary_by_source


def _build_used_precedents(
    *,
    selected_claims: list[dict[str, Any]],
    selected_precedents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_case_number = {
        str(item.get("caseNumber") or "").strip(): item
        for item in selected_precedents
        if str(item.get("caseNumber") or "").strip()
    }
    by_precedent_id = _selected_precedents_by_id(selected_precedents)
    rows: dict[str, dict[str, Any]] = {}
    for claim in selected_claims:
        summary = _compose_precedent_card_summary(claim)
        quote = _clean_display_text(str(((claim.get("support_spans") or [{}])[0] or {}).get("quote") or ""), limit=220)
        claim_axis = _clean_display_text(str(claim.get("claim_axis") or ""), limit=120)
        source_precedent_id = str(claim.get("source_file_id") or "").strip()
        supporting_cases = claim.get("supporting_cases") or []
        if not supporting_cases and source_precedent_id:
            selected = by_precedent_id.get(source_precedent_id, {})
            supporting_cases = [
                {
                    "case_number": selected.get("caseNumber") or claim.get("case_number") or "",
                    "court": selected.get("court") or claim.get("court") or "",
                    "decision_date": selected.get("decisionDate") or claim.get("decision_date") or "",
                    "case_name": selected.get("caseName") or claim.get("case_name") or "",
                }
            ]
        for supporting_case in supporting_cases:
            case_number = _clean_display_text(str(supporting_case.get("case_number") or ""), limit=60)
            selected = by_precedent_id.get(source_precedent_id, {}) or by_case_number.get(case_number, {})
            citation = _build_precedent_citation(
                {
                    "case_number": case_number or selected.get("caseNumber") or "",
                    "court": supporting_case.get("court") or selected.get("court") or "",
                    "decision_date": supporting_case.get("decision_date") or selected.get("decisionDate") or "",
                    "case_name": supporting_case.get("case_name") or selected.get("caseName") or selected.get("title") or "",
                }
            )
            key = source_precedent_id or str(selected.get("precedentId") or "").strip() or case_number or citation
            if not key:
                continue
            row = rows.setdefault(
                key,
                {
                    "precedentId": str(selected.get("precedentId") or "").strip(),
                    "caseNumber": case_number or str(selected.get("caseNumber") or "").strip(),
                    "caseName": _normalize_case_name(
                        str(supporting_case.get("case_name") or selected.get("caseName") or selected.get("title") or "")
                    ),
                    "title": _clean_display_text(str(selected.get("title") or citation or ""), limit=160),
                    "court": _clean_display_text(str(supporting_case.get("court") or selected.get("court") or ""), limit=80),
                    "decisionDate": _format_decision_date(str(supporting_case.get("decision_date") or selected.get("decisionDate") or "")),
                    "sourcePath": str(selected.get("sourcePath") or ""),
                    "relativePath": str(selected.get("relativePath") or ""),
                    "fullText": str(selected.get("fullText") or ""),
                    "excerpt": _clean_display_text(str(selected.get("excerpt") or quote or ""), limit=220),
                    "citation": citation,
                    "summary": summary,
                    "supportedClaimAxes": [],
                    "useCount": 0,
                },
            )
            row["useCount"] = int(row.get("useCount") or 0) + 1
            if claim_axis and claim_axis not in row["supportedClaimAxes"]:
                row["supportedClaimAxes"].append(claim_axis)
            if summary and not row.get("summary"):
                row["summary"] = summary
            if quote and not row.get("excerpt"):
                row["excerpt"] = quote
    ranked = sorted(
        rows.values(),
        key=lambda item: (
            -int(item.get("useCount") or 0),
            -len(item.get("supportedClaimAxes") or []),
            str(item.get("citation") or ""),
        ),
    )
    return [
        {
            "precedentId": row.get("precedentId") or "",
            "caseNumber": row.get("caseNumber") or "",
            "caseName": row.get("caseName") or "",
            "title": row.get("title") or row.get("citation") or "",
            "court": row.get("court") or "",
            "decisionDate": row.get("decisionDate") or "",
            "sourcePath": row.get("sourcePath") or "",
            "relativePath": row.get("relativePath") or "",
            "fullText": row.get("fullText") or "",
            "excerpt": row.get("excerpt") or "",
            "citation": row.get("citation") or "",
            "summary": row.get("summary") or "",
        }
        for row in ranked
    ]


def _select_body_claims(claim_ledger: list[dict[str, Any]], answer_plan: dict[str, Any]) -> list[dict[str, Any]]:
    body_ids = [str(item).strip() for item in (answer_plan.get("body_claim_ids") or []) if str(item).strip()]
    if not body_ids:
        return claim_ledger
    by_id = {str(claim.get("claim_id") or "").strip(): claim for claim in claim_ledger}
    selected = [by_id[claim_id] for claim_id in body_ids if claim_id in by_id]
    return selected or claim_ledger


def _build_claim_groups(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for claim in claims:
        claim_id = str(claim.get("claim_id") or "").strip()
        if not claim_id:
            continue
        axis = _claim_group_label(str(claim.get("claim_axis") or claim.get("claim_text") or "기타 주장"))
        entry = buckets.setdefault(axis, {"label": axis, "claim_ids": [], "support": 0})
        if claim_id not in entry["claim_ids"]:
            entry["claim_ids"].append(claim_id)
        entry["support"] = max(
            int(entry.get("support") or 0),
            int(claim.get("supporting_case_count") or claim.get("support_count") or 0),
        )
    grouped = sorted(
        buckets.values(),
        key=lambda item: (-int(item.get("support") or 0), -len(item.get("claim_ids") or []), str(item.get("label") or "")),
    )
    return [{"label": str(item["label"]), "claim_ids": list(item["claim_ids"])} for item in grouped]


def _normalize_answer_plan_claim_groups(
    raw_groups: list[dict[str, Any]] | None,
    *,
    selected_claims: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not raw_groups:
        return _build_claim_groups(selected_claims)
    seen: dict[str, list[str]] = {}
    valid_ids = {str(claim.get("claim_id") or "").strip() for claim in selected_claims if str(claim.get("claim_id") or "").strip()}
    for group in raw_groups:
        label = _claim_group_label(str(group.get("label") or ""))
        if not label:
            continue
        bucket = seen.setdefault(label, [])
        for claim_id in group.get("claim_ids") or []:
            normalized_id = str(claim_id or "").strip()
            if normalized_id and normalized_id in valid_ids and normalized_id not in bucket:
                bucket.append(normalized_id)
    rows = [{"label": label, "claim_ids": claim_ids} for label, claim_ids in seen.items() if claim_ids]
    return rows or _build_claim_groups(selected_claims)


def _collect_used_precedent_ids_from_claims(claims: list[dict[str, Any]]) -> list[str]:
    used_ids: list[str] = []
    for claim in claims:
        source_file_id = str(claim.get("source_file_id") or "").strip()
        if source_file_id and source_file_id not in used_ids:
            used_ids.append(source_file_id)
    return used_ids


def _collect_used_precedent_ids_from_chunk_outputs(chunk_outputs: list[dict[str, Any]]) -> list[str]:
    used_ids: list[str] = []
    for output in chunk_outputs:
        for claim in output.get("claims_proposed") or []:
            file_id = str(claim.get("source_file_id") or output.get("file_id") or "").strip()
            if file_id and file_id not in used_ids:
                used_ids.append(file_id)
    return used_ids


def _enrich_claim_ledger(
    claim_ledger: list[dict[str, Any]],
    *,
    selected_precedents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    precedent_by_case = {
        str(item.get("caseNumber") or "").strip(): item
        for item in selected_precedents
        if str(item.get("caseNumber") or "").strip()
    }
    precedent_by_id = _selected_precedents_by_id(selected_precedents)
    enriched: list[dict[str, Any]] = []
    for claim in claim_ledger:
        copied = dict(claim)
        primary_case = next(
            (
                row
                for row in (claim.get("supporting_cases") or [])
                if str(row.get("case_number") or "").strip()
            ),
            {},
        )
        case_number = str(copied.get("case_number") or primary_case.get("case_number") or "").strip()
        source_file_id = str(copied.get("source_file_id") or "").strip()
        selected = precedent_by_id.get(source_file_id, {}) or precedent_by_case.get(case_number, {})
        selected_case_number = str(selected.get("caseNumber") or "").strip()
        if not case_number and selected_case_number:
            case_number = selected_case_number
        copied["case_number"] = case_number
        copied["court"] = str(copied.get("court") or primary_case.get("court") or selected.get("court") or "").strip()
        copied["decision_date"] = str(copied.get("decision_date") or primary_case.get("decision_date") or selected.get("decisionDate") or "").strip()
        copied["case_name"] = str(copied.get("case_name") or primary_case.get("case_name") or selected.get("title") or "").strip()
        selected_precedent_id = str(selected.get("precedentId") or "").strip()
        copied["source_file_id"] = selected_precedent_id or source_file_id
        copied["citation"] = str(selected.get("citation") or "").strip() or _build_precedent_citation(
            {
                "court": copied.get("court"),
                "decision_date": copied.get("decision_date"),
                "case_number": copied.get("case_number"),
                "case_name": copied.get("case_name"),
                "title": selected.get("title"),
                "fullText": selected.get("fullText"),
                "sourcePath": selected.get("sourcePath"),
                "relativePath": selected.get("relativePath"),
            }
        )
        enriched.append(copied)
    return enriched


def _enrich_answer_plan(
    answer_plan: dict[str, Any],
    *,
    selected_precedents: list[dict[str, Any]],
    claim_ledger: list[dict[str, Any]],
) -> dict[str, Any]:
    raw_buckets = answer_plan.get("precedent_buckets") or {}
    by_case_number = {str(item.get("caseNumber") or "").strip(): item for item in selected_precedents if str(item.get("caseNumber") or "").strip()}
    by_precedent_id = _selected_precedents_by_id(selected_precedents)
    claim_by_id = {str(item.get("claim_id") or "").strip(): item for item in claim_ledger if str(item.get("claim_id") or "").strip()}
    summary_by_case = _build_case_summary_map(claim_ledger)
    summary_by_source = _build_source_summary_map(claim_ledger)
    buckets: dict[str, list[dict[str, Any]]] = {}
    for key in ("very_similar", "similar", "usable", "other"):
        rows: list[dict[str, Any]] = []
        for row in raw_buckets.get(key) or []:
            case_number = str(row.get("case_number") or "").strip()
            supported_claim_ids = list(row.get("supported_claim_ids") or [])
            supported_claim = next((claim_by_id.get(str(claim_id).strip()) for claim_id in supported_claim_ids if claim_by_id.get(str(claim_id).strip())), {})
            fallback_precedent_id = str((supported_claim or {}).get("source_file_id") or "").strip()
            case_precedent = by_case_number.get(case_number, {}) if case_number else {}
            fallback_precedent = by_precedent_id.get(fallback_precedent_id, {}) if fallback_precedent_id else {}
            fallback_case_number = str(fallback_precedent.get("caseNumber") or "").strip()
            if fallback_precedent and (not fallback_case_number or fallback_case_number == case_number):
                precedent = fallback_precedent
            else:
                # If the supported claim source points at a different explicit
                # case, the planner's bucket case_number is the better row id.
                precedent = case_precedent or fallback_precedent
            resolved_case_number = case_number or str(precedent.get("caseNumber") or "").strip()
            enriched = {
                **row,
                "precedentId": precedent.get("precedentId") or "",
                "title": precedent.get("title") or _clean_display_text(str(row.get("case_name") or ""), limit=160),
                "citation": _build_precedent_citation(
                    {
                        "case_number": resolved_case_number,
                        "court": row.get("court") or precedent.get("court"),
                        "decision_date": row.get("decision_date") or precedent.get("decisionDate"),
                        "case_name": row.get("case_name") or precedent.get("title"),
                        "title": precedent.get("title"),
                        "fullText": precedent.get("fullText"),
                        "sourcePath": precedent.get("sourcePath"),
                        "relativePath": precedent.get("relativePath"),
                    }
                ),
                "excerpt": precedent.get("excerpt") or "",
                "summary": summary_by_source.get(fallback_precedent_id, "")
                or summary_by_case.get(resolved_case_number, "")
                or _clean_display_text(str((supported_claim or {}).get("case_summary") or ""), limit=220)
                or _clean_display_text(str(row.get("why") or ""), limit=220),
            }
            rows.append(enriched)
        buckets[key] = rows
    if not any(buckets.get(key) for key in ("very_similar", "similar", "usable")):
        buckets = _fallback_precedent_buckets_from_claims(
            answer_plan=answer_plan,
            selected_precedents=selected_precedents,
            claim_ledger=claim_ledger,
        )
    selected_claims = _select_body_claims(claim_ledger, answer_plan)
    claim_groups = _normalize_answer_plan_claim_groups(answer_plan.get("claim_groups"), selected_claims=selected_claims)
    sanitized = {key: value for key, value in answer_plan.items() if key != "raw"}
    sanitized["likely_outcome"] = _strip_claim_debug_ids(str(sanitized.get("likely_outcome") or ""))
    for field in ("confidence_basis", "helpful_facts", "harmful_facts"):
        sanitized[field] = [
            cleaned
            for cleaned in (_strip_claim_debug_ids(str(item)) for item in (sanitized.get(field) or []))
            if cleaned
        ]
    for bucket_rows in buckets.values():
        for row in bucket_rows:
            row["court"] = ""
            row["decision_date"] = ""
            row["case_name"] = ""
            row["citation"] = _build_precedent_citation({"case_number": row.get("case_number")})
            row["why"] = _strip_claim_debug_ids(str(row.get("why") or ""))
    return {
        **sanitized,
        "claim_groups": claim_groups,
        "precedent_buckets": buckets,
    }


def _anonymous_reference_precedent_ids(answer_plan: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    buckets = answer_plan.get("precedent_buckets") or {}
    for bucket_key in ("very_similar", "similar", "usable", "other"):
        for row in buckets.get(bucket_key) or []:
            if str(row.get("case_number") or "").strip():
                continue
            precedent_id = str(row.get("precedentId") or "").strip()
            title = _normalize_case_name(str(row.get("title") or row.get("case_name") or ""))
            citation = str(row.get("citation") or "").strip()
            if precedent_id and (title == "LBOX 익명화" or citation == "참조 판례"):
                ids.append(precedent_id)
    return ids


_PRD_TOKEN_PATTERN = re.compile(r"\[prd:([A-Za-z0-9-]+)\]")


def _anonymous_reference_precedent_ids_from_body_tokens(markdown: str) -> list[str]:
    if not markdown:
        return []
    split_match = _REFERENCE_LIST_HEADER.search(markdown)
    body_part = markdown[: split_match.start()] if split_match else markdown
    ids: list[str] = []
    for match in _PRD_TOKEN_PATTERN.finditer(body_part):
        precedent_id = (match.group(1) or "").strip()
        if precedent_id and precedent_id not in ids:
            ids.append(precedent_id)
    return ids


def _annotate_anonymous_reference_list_citations(markdown: str, answer_plan: dict[str, Any]) -> str:
    """Attach hidden precedent ids to anonymous LBOX reference-list rows.

    Case-number lookup cannot work for anonymized rows. The stable identity is
    the selected precedent id, derived upstream from the source body/quote and
    carried through `precedent_buckets`.
    """
    if not markdown:
        return markdown
    precedent_ids = _anonymous_reference_precedent_ids(answer_plan)
    for precedent_id in _anonymous_reference_precedent_ids_from_body_tokens(markdown):
        if precedent_id not in precedent_ids:
            precedent_ids.append(precedent_id)
    if not precedent_ids:
        return markdown
    split_match = _REFERENCE_LIST_HEADER.search(markdown)
    if not split_match:
        return markdown
    body_part = markdown[: split_match.start()]
    tail_part = markdown[split_match.start():]
    pattern = re.compile(r"참조\s*판례\s*\(\s*LBOX\s*익명화\s*(?![^)]*\[prd:)[^)]*\)")
    cursor = 0

    def _replace(match: re.Match[str]) -> str:
        nonlocal cursor
        if cursor >= len(precedent_ids):
            precedent_id = precedent_ids[-1]
        else:
            precedent_id = precedent_ids[cursor]
        cursor += 1
        return f"참조 판례 (LBOX 익명화 [prd:{precedent_id}])"

    return body_part + pattern.sub(_replace, tail_part)


def _fallback_precedent_buckets_from_claims(
    *,
    answer_plan: dict[str, Any],
    selected_precedents: list[dict[str, Any]],
    claim_ledger: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    by_case_number = {
        str(item.get("caseNumber") or "").strip(): item
        for item in selected_precedents
        if str(item.get("caseNumber") or "").strip()
    }
    by_precedent_id = _selected_precedents_by_id(selected_precedents)
    selected_ids = [str(item).strip() for item in (answer_plan.get("body_claim_ids") or []) if str(item).strip()]
    chosen_claims = [
        claim
        for claim in claim_ledger
        if not selected_ids or str(claim.get("claim_id") or "").strip() in selected_ids
    ]
    rows_by_key: dict[str, dict[str, Any]] = {}
    for claim in chosen_claims:
        source_file_id = str(claim.get("source_file_id") or "").strip()
        support_hits = int(claim.get("supporting_case_count") or 0)
        same_situation = bool(claim.get("same_situation_case_exists"))
        summary_text = _compose_precedent_card_summary(claim) or _compose_claim_summary(claim)
        for supporting_case in claim.get("supporting_cases") or []:
            case_number = str(supporting_case.get("case_number") or "").strip()
            precedent = by_precedent_id.get(source_file_id, {}) or by_case_number.get(case_number, {})
            key = source_file_id or str(precedent.get("precedentId") or "").strip() or case_number
            if not key:
                continue
            row = rows_by_key.setdefault(
                key,
                {
                    "precedentId": precedent.get("precedentId") or source_file_id or "",
                    "case_number": case_number or str(precedent.get("caseNumber") or "").strip(),
                    "court": supporting_case.get("court") or precedent.get("court") or "",
                    "decision_date": supporting_case.get("decision_date") or precedent.get("decisionDate") or "",
                    "case_name": supporting_case.get("case_name") or precedent.get("title") or "",
                    "citation": precedent.get("citation")
                    or _build_precedent_citation(
                        {
                            "case_number": case_number or precedent.get("caseNumber"),
                            "court": supporting_case.get("court") or precedent.get("court"),
                            "decision_date": supporting_case.get("decision_date") or precedent.get("decisionDate"),
                            "case_name": supporting_case.get("case_name") or precedent.get("title"),
                        }
                    ),
                    "summary": precedent.get("summary") or summary_text,
                    "excerpt": precedent.get("excerpt") or "",
                    "supported_claim_ids": [],
                    "supported_claim_axes": [],
                    "score": 0,
                    "same_situation": False,
                    "why": "",
                },
            )
            claim_id = str(claim.get("claim_id") or "").strip()
            claim_axis = str(claim.get("claim_axis") or "").strip()
            if claim_id and claim_id not in row["supported_claim_ids"]:
                row["supported_claim_ids"].append(claim_id)
            if claim_axis and claim_axis not in row["supported_claim_axes"]:
                row["supported_claim_axes"].append(claim_axis)
            row["score"] = max(int(row["score"] or 0), support_hits)
            row["same_situation"] = bool(row["same_situation"]) or same_situation
            if not row["summary"] and summary_text:
                row["summary"] = summary_text
    ranked = sorted(
        rows_by_key.values(),
        key=lambda item: (
            not bool(item.get("same_situation")),
            -len(item.get("supported_claim_ids") or []),
            -int(item.get("score") or 0),
            str(item.get("case_number") or ""),
        ),
    )
    buckets: dict[str, list[dict[str, Any]]] = {"very_similar": [], "similar": [], "usable": [], "other": []}
    for index, row in enumerate(ranked):
        clean = {
            "precedentId": row.get("precedentId") or "",
            "case_number": row.get("case_number") or "",
            "court": row.get("court") or "",
            "decision_date": row.get("decision_date") or "",
            "case_name": row.get("case_name") or "",
            "citation": row.get("citation") or "",
            "summary": row.get("summary") or "",
            "excerpt": row.get("excerpt") or "",
            "supported_claim_ids": row.get("supported_claim_ids") or [],
            "supported_claim_axes": row.get("supported_claim_axes") or [],
            "why": "",
        }
        if bool(row.get("same_situation")) or index < 3:
            clean["why"] = "현재 선택된 주장과 사실관계·법리 축이 직접 맞닿는 판례입니다."
            buckets["very_similar"].append(clean)
        elif index < 8:
            clean["why"] = "같은 유형의 쟁점을 다루며 유불리 조건을 뽑아낼 수 있는 판례입니다."
            buckets["similar"].append(clean)
        elif index < 14:
            clean["why"] = "유형은 다르지만 내부 논리를 원용할 수 있는 판례입니다."
            buckets["usable"].append(clean)
        else:
            clean["why"] = "직접적 관련성은 낮지만 보조 참고가 가능한 판례입니다."
            buckets["other"].append(clean)
    return buckets


def _build_analysis_summary(
    answer_plan: dict[str, Any],
    claims: list[dict[str, Any]],
) -> dict[str, Any]:
    planned_likely_outcome = _truncate_clean_text(_strip_claim_debug_ids(str(answer_plan.get("likely_outcome") or "")), limit=360)
    if planned_likely_outcome:
        return {
            "likely_outcome": planned_likely_outcome,
            "confidence_basis": [
                _truncate_clean_text(_strip_claim_debug_ids(str(item)), limit=180)
                for item in (answer_plan.get("confidence_basis") or [])
                if _strip_claim_debug_ids(str(item))
            ][:3],
            "helpful_facts": [
                _truncate_clean_text(_strip_claim_debug_ids(str(item)), limit=160)
                for item in (answer_plan.get("helpful_facts") or [])
                if _strip_claim_debug_ids(str(item))
            ][:4],
            "harmful_facts": [
                _truncate_clean_text(_strip_claim_debug_ids(str(item)), limit=160)
                for item in (answer_plan.get("harmful_facts") or [])
                if _strip_claim_debug_ids(str(item))
            ][:4],
        }
    if not claims:
        return {
            "likely_outcome": "",
            "confidence_basis": [],
            "helpful_facts": [],
            "harmful_facts": [],
        }
    claim_by_id = {
        str(claim.get("claim_id") or "").strip(): claim
        for claim in claims
        if str(claim.get("claim_id") or "").strip()
    }
    raw_groups = answer_plan.get("claim_groups") or _build_claim_groups(claims)
    grouped_rows: list[dict[str, Any]] = []
    if raw_groups:
        for group in raw_groups:
            label = _claim_group_label(str(group.get("label") or ""))
            grouped_claims = [
                claim_by_id[str(claim_id).strip()]
                for claim_id in (group.get("claim_ids") or [])
                if str(claim_id).strip() in claim_by_id
            ]
            if not grouped_claims:
                continue
            grouped_rows.append(
                {
                    "label": label,
                    "claims": grouped_claims,
                    "support": max(int(claim.get("supporting_case_count") or 0) for claim in grouped_claims),
                    "favorable_count": sum(
                        1 for claim in grouped_claims if "유리" in str(claim.get("stance_to_user_goal") or "")
                    ),
                    "same_situation_count": sum(
                        1 for claim in grouped_claims if bool(claim.get("same_situation_case_exists"))
                    ),
                }
            )
    if not grouped_rows:
        for claim in claims:
            grouped_rows.append(
                {
                    "label": _claim_group_label(str(claim.get("claim_axis") or claim.get("claim_text") or "기타 주장")),
                    "claims": [claim],
                    "support": int(claim.get("supporting_case_count") or 0),
                    "favorable_count": 1 if "유리" in str(claim.get("stance_to_user_goal") or "") else 0,
                    "same_situation_count": 1 if bool(claim.get("same_situation_case_exists")) else 0,
                }
            )
    grouped_rows.sort(
        key=lambda item: (
            -int(item.get("same_situation_count") or 0),
            -int(item.get("support") or 0),
            -int(item.get("favorable_count") or 0),
            str(item.get("label") or ""),
        )
    )
    top = grouped_rows[0]
    runner_up = grouped_rows[1] if len(grouped_rows) > 1 else None
    top_claim = sorted(
        top["claims"],
        key=lambda claim: (bool(claim.get("same_situation_case_exists")), int(claim.get("supporting_case_count") or 0)),
        reverse=True,
    )[0]
    lead_support = max(int(top.get("support") or 0), int(top_claim.get("supporting_case_count") or 0))
    runner_support = max(int(runner_up.get("support") or 0), 0) if runner_up else 0
    favorable_strength = sum(
        max(int(claim.get("supporting_case_count") or 0), 1)
        for claim in claims
        if "유리" in str(claim.get("stance_to_user_goal") or "")
    )
    harmful_strength = sum(
        max(int(claim.get("supporting_case_count") or 0), 1)
        for claim in claims
        if "불리" in str(claim.get("stance_to_user_goal") or "")
    )
    if favorable_strength > harmful_strength * 1.15:
        direction = "질문자에게 유리한 방향의 결론"
    elif harmful_strength > favorable_strength * 1.15:
        direction = "질문자에게 불리한 방향의 결론"
    else:
        direction = "핵심 사실관계에 따라 결론이 갈릴 가능성"
    claim_line = _truncate_clean_text(
        str(top_claim.get("claim_text") or top_claim.get("context_summary") or ""),
        limit=180,
    )
    examples: list[str] = []
    for supporting_case in top_claim.get("supporting_cases") or []:
        case_number = str(supporting_case.get("case_number") or "").strip()
        if case_number and case_number not in examples:
            examples.append(case_number)
        if len(examples) >= 3:
            break
    support_line = (
        f"{top['label']} 묶음은 별개 판례 {lead_support}건 안팎이 같은 방향으로 반복적으로 뒷받침하므로, 현재 가장 신뢰도가 높은 판단축입니다."
        if lead_support >= 2
        else f"{top['label']} 묶음이 현재 가장 직접적으로 맞닿는 판단축입니다."
    )
    if lead_support >= 2 and lead_support > runner_support:
        support_line = f"{support_line} 다음 축보다 {max(lead_support - runner_support, 1)}건 이상 더 반복되어 우선순위가 높습니다."
    if examples:
        support_line = f"{support_line} 특히 {', '.join(examples)} 등이 같은 방향으로 반복됩니다."
    likely_outcome = (
        f"현재 자료상 {direction}이 가장 높습니다. 핵심은 {top['label']} 묶음이고, {support_line} "
        f"{claim_line or '이 축을 중심으로 결론을 정리해야 합니다.'}"
    ).strip()
    helpful_facts = _dedupe_sentences(
        " ".join(
            _truncate_clean_text(item, limit=120)
            for item in [
                *[
                    value
                    for claim in claims
                    for value in [
                        *(claim.get("favorable_factors") or []),
                        *(claim.get("required_facts") or []),
                        *(claim.get("favorable_basis") or []),
                    ]
                    if value
                ],
            ]
        )
    )
    harmful_facts = _dedupe_sentences(
        " ".join(
            _truncate_clean_text(item, limit=120)
            for item in [
                *[
                    value
                    for claim in claims
                    for value in [
                        *(claim.get("unfavorable_factors") or []),
                        *(claim.get("missing_facts") or []),
                        *(claim.get("cautions") or []),
                        *(claim.get("counter_evidence") or []),
                    ]
                    if value
                ],
            ]
        )
    )
    helpful_rows = [row.strip() for row in re.split(r"(?<=[\.\?!다])\s+", helpful_facts) if row.strip()][:4]
    harmful_rows = [row.strip() for row in re.split(r"(?<=[\.\?!다])\s+", harmful_facts) if row.strip()][:4]
    return {
        "likely_outcome": likely_outcome,
        "confidence_basis": [support_line],
        "helpful_facts": helpful_rows,
        "harmful_facts": harmful_rows,
    }


def _selector_verified_same_fact_rows(
    *,
    selection_meta: dict[str, Any],
    selected_precedents: list[dict[str, Any]],
) -> list[dict[str, str]]:
    if str(selection_meta.get("selection_mode") or "") != "beta6_loop_r133_port":
        return []
    by_id = {
        str(item.get("precedentId") or "").strip(): item
        for item in selected_precedents
        if str(item.get("precedentId") or "").strip()
    }
    rows: list[dict[str, str]] = []
    seen_cases: set[str] = set()
    for debug in selection_meta.get("top_debug") or []:
        if str(debug.get("verifier") or "") != "accept":
            continue
        precedent = by_id.get(str(debug.get("canonical_id") or "").strip())
        if not precedent:
            continue
        case_number = str(precedent.get("caseNumber") or "").strip()
        key = case_number or str(precedent.get("precedentId") or "").strip()
        if key in seen_cases:
            continue
        seen_cases.add(key)
        reasons = [str(item) for item in (debug.get("reasons") or []) if str(item)]
        factual_hits = [
            item
            for item in reasons
            if any(token in item for token in ["account_access_bridge", "actor:", "platform:", "purpose:", "usim:", "physical", "military", "key", "management"])
        ][:5]
        summary = _truncate_clean_text(
            _strip_user_direction_sentence(str(precedent.get("summary") or precedent.get("excerpt") or precedent.get("title") or "")),
            limit=210,
        )
        if factual_hits:
            summary = _dedupe_sentences(f"{summary} 선택기 검증 신호: {', '.join(factual_hits)}")
        rows.append(
            {
                "citation": str(precedent.get("citation") or "").strip()
                or _build_precedent_citation(
                    {
                        "court": precedent.get("court"),
                        "decision_date": precedent.get("decisionDate"),
                        "case_number": precedent.get("caseNumber"),
                        "case_name": precedent.get("title") or precedent.get("caseName"),
                    }
                ),
                "claim_axis": "선택기가 같은 사실관계로 검증한 판례",
                "summary": summary,
                "quote": _truncate_clean_text(str(precedent.get("excerpt") or ""), limit=180),
                "supporting_case_count": str(int(float(debug.get("score") or 0))),
            }
        )
        if len(rows) >= 3:
            break
    return rows


def _same_fact_claim_rows(claims: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for claim in claims:
        if not bool(claim.get("same_situation_case_exists")):
            continue
        citation = str(claim.get("citation") or "").strip() or _first_supporting_case_citation(claim)
        if not citation:
            citation = _build_precedent_citation(
                {
                    "court": claim.get("court"),
                    "decision_date": claim.get("decision_date"),
                    "case_number": claim.get("case_number"),
                    "case_name": claim.get("case_name"),
                }
            )
        claim_axis = _claim_group_label(str(claim.get("claim_axis") or claim.get("claim_text") or ""))
        summary = _truncate_clean_text(
            str(claim.get("case_summary") or claim.get("claim_text") or claim.get("context_summary") or ""),
            limit=190,
        )
        quote = _truncate_clean_text(str(((claim.get("support_spans") or [{}])[0] or {}).get("quote") or ""), limit=180)
        key = citation or claim_axis or summary
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "citation": citation,
                "claim_axis": claim_axis,
                "summary": summary,
                "quote": quote,
                "supporting_case_count": str(int(claim.get("supporting_case_count") or 0)),
            }
        )
    rows.sort(
        key=lambda item: (
            -int(item.get("supporting_case_count") or "0"),
            item.get("citation") or "",
        )
    )
    return rows


def _fallback_likely_outcome_from_selection(
    *,
    selected_precedents: list[dict[str, Any]],
    selection_meta: dict[str, Any],
) -> str:
    rows = _selector_verified_same_fact_rows(
        selection_meta=selection_meta,
        selected_precedents=selected_precedents,
    )
    if rows:
        top = rows[0]
        citation = str(top.get("citation") or "주된 판례").strip() or "주된 판례"
        body = _truncate_clean_text(str(top.get("summary") or top.get("claim_axis") or ""), limit=180)
        if body:
            return (
                f"현재 자료상 {citation} 사실관계가 가장 가깝게 잡혔고, 이 판례 흐름이 곧 결론의 출발점이 됩니다. {body}"
            ).strip()
        return (
            f"현재 자료상 {citation} 사실관계가 가장 가깝게 잡혔고, 이 판례 흐름이 곧 결론의 출발점이 됩니다."
        ).strip()
    if selected_precedents:
        top = selected_precedents[0]
        citation = str(top.get("citation") or top.get("caseNumber") or top.get("title") or "").strip()
        if citation:
            return (
                f"현재 자료상 {citation} 판례가 가장 비중 있게 선별되었고, 이 흐름이 결론의 출발점이 됩니다."
            ).strip()
    return ""


def _prepend_same_fact_precedent_section(
    markdown: str,
    *,
    claims: list[dict[str, Any]],
    selected_precedents: list[dict[str, Any]],
    selection_meta: dict[str, Any],
) -> str:
    stripped = str(markdown or "").lstrip()
    if "### 가장 같은 사실관계 판례" in stripped:
        return stripped
    rows = _selector_verified_same_fact_rows(selection_meta=selection_meta, selected_precedents=selected_precedents)
    if not rows:
        rows = _same_fact_claim_rows(claims)
    if not rows:
        return stripped
    lines = ["### 가장 같은 사실관계 판례"]
    for row in rows[:3]:
        body_parts = [row.get("claim_axis") or "", row.get("summary") or ""]
        if row.get("quote"):
            body_parts.append(f"핵심 문구: {row['quote']}")
        body = _dedupe_sentences(" ".join(part for part in body_parts if part).strip())
        citation = row.get("citation") or "인용 판례"
        lines.append(f"- **{citation}**: {body}".rstrip())
    prefix = "\n".join(lines).strip()
    if not stripped:
        return prefix
    return f"{prefix}\n\n---\n\n{stripped}"


def _prepend_analysis_summary(
    markdown: str,
    *,
    answer_plan: dict[str, Any],
    claims: list[dict[str, Any]],
    selected_precedents: list[dict[str, Any]] | None = None,
    selection_meta: dict[str, Any] | None = None,
) -> str:
    summary = _build_analysis_summary(answer_plan, claims)
    # Beta-4/5/6 occasionally yield sparse/empty `claims` and `answer_plan`,
    # which previously suppressed the entire 최상단 요약. Synthesize a minimal
    # likely_outcome from the top same-fact-verified precedent so the summary
    # header always shows up when the selector returned anything usable.
    if not summary.get("likely_outcome"):
        fallback_likely = _fallback_likely_outcome_from_selection(
            selected_precedents=selected_precedents or [],
            selection_meta=selection_meta or {},
        )
        if fallback_likely:
            summary = {
                **summary,
                "likely_outcome": fallback_likely,
            }
    if not summary.get("likely_outcome"):
        return markdown
    stripped = str(markdown or "").lstrip()
    if "### 가장 가능성 높은 결론" in stripped:
        return stripped
    sections = [
        "### 가장 가능성 높은 결론",
        str(summary.get("likely_outcome") or "").strip(),
    ]
    confidence_basis = [str(item).strip() for item in (summary.get("confidence_basis") or []) if str(item).strip()]
    if confidence_basis:
        sections.append("### 결론 근거")
        sections.extend(f"- {item}" for item in confidence_basis[:3])
    helpful_facts = [str(item).strip() for item in (summary.get("helpful_facts") or []) if str(item).strip()]
    harmful_facts = [str(item).strip() for item in (summary.get("harmful_facts") or []) if str(item).strip()]
    if helpful_facts:
        sections.append("### 나에게 유리하게 만들 요소")
        sections.extend(f"- {item}" for item in helpful_facts[:4])
    if harmful_facts:
        sections.append("### 나에게 불리하게 만들 요소")
        sections.extend(f"- {item}" for item in harmful_facts[:4])
    prefix = "\n".join(sections).strip()
    if not stripped:
        return prefix
    return f"{prefix}\n\n---\n\n{stripped}"


def _relative_to_run(run_dir: Path, target: Path) -> str:
    try:
        return str(target.relative_to(run_dir)).replace("\\", "/")
    except ValueError:
        return str(target)


def _artifact_url(job_id: str | None, relative_path: str) -> str:
    if not job_id or not relative_path:
        return ""
    return f"/api/jobs/{job_id}/artifacts/{relative_path}"


def _collect_export_artifacts(run_dir: Path, variant_dir: Path, *, job_id: str | None = None) -> dict[str, Any]:
    exports_dir = variant_dir / "exports"
    payload = {
        "markdownPath": "",
        "markdownUrl": "",
        "htmlPath": "",
        "htmlUrl": "",
        "hwpxPath": "",
        "hwpxUrl": "",
        "pdfPath": "",
        "pdfUrl": "",
        "previewImagePaths": [],
        "previewImageUrls": [],
    }
    if not exports_dir.exists():
        return payload

    def attach(name: str, key_path: str, key_url: str) -> None:
        path = exports_dir / name
        if path.exists():
            relative = _relative_to_run(run_dir, path)
            payload[key_path] = str(path)
            payload[key_url] = _artifact_url(job_id, relative)

    attach("final_document.md", "markdownPath", "markdownUrl")
    attach("final_document.html", "htmlPath", "htmlUrl")
    attach("final_document.hwpx", "hwpxPath", "hwpxUrl")
    attach("final_document.pdf", "pdfPath", "pdfUrl")
    if not payload["markdownPath"]:
        attach("final_answer.md", "markdownPath", "markdownUrl")
    if not payload["htmlPath"]:
        attach("final_answer.html", "htmlPath", "htmlUrl")
    if not payload["hwpxPath"]:
        attach("final_answer.hwpx", "hwpxPath", "hwpxUrl")
    if not payload["pdfPath"]:
        attach("final_answer.pdf", "pdfPath", "pdfUrl")

    preview_dir = exports_dir / "preview"
    if preview_dir.exists():
        preview_paths = sorted(path for path in preview_dir.glob("*.png") if path.is_file())
        payload["previewImagePaths"] = [str(path) for path in preview_paths]
        payload["previewImageUrls"] = [_artifact_url(job_id, _relative_to_run(run_dir, path)) for path in preview_paths]
    return payload


def build_result_payload(
    run_dir: Path,
    *,
    variant_name: str = QUESTION_VARIANT_NAME,
    job_id: str | None = None,
    mode: str = "",
    analysis_mode: str = "",
) -> dict[str, Any]:
    variant_dir = run_dir / variant_name
    is_document_mode = mode == "document" or (not mode and (variant_dir / "final_document.md").exists())
    is_beta7 = (analysis_mode or "").lower() == "beta7"
    selected_files = _load_json(variant_dir / "selected_files.json", [])
    claim_ledger = _load_json(variant_dir / "claim_ledger.json", [])
    answer_plan = _load_json(variant_dir / "answer_plan.json", {})
    selection_meta = _load_json(run_dir / "selection_meta.json", {})
    comparison_summary = _load_json(variant_dir / "comparison_summary.json", {})
    chunk_outputs = _load_jsonl(variant_dir / "chunk_outputs.jsonl")

    answer_path = variant_dir / "final_document.md"
    if not answer_path.exists():
        answer_path = variant_dir / "final_answer.md"
    if not answer_path.exists():
        answer_path = variant_dir / "final_answer_v2.md"
    answer_markdown = answer_path.read_text(encoding="utf-8") if answer_path.exists() else ""
    # Capture writer-emitted citation token indices NOW, before any rewrite
    # erases them. Used downstream for citedClaims separation in Beta-7+.
    cited_token_indices = _extract_writer_cited_claim_indices(answer_markdown)
    # Also capture direct case-number citations the writer emitted (Gemma
    # often falls back to writing `(법원 ... 사건번호 판결)` directly even when
    # the prompt requested tokens). Map these case_numbers back to claim
    # `_writer_claim_index` via the raw claim_ledger before any rewrite
    # mutates the markdown.
    cited_case_numbers_raw = _extract_cited_case_numbers_in_body(answer_markdown)
    answer_markdown = strip_document_meta_leak(answer_markdown) if is_document_mode else _strip_answer_meta_leak(answer_markdown)
    if not is_beta7:
        # Beta-1..6: strip ingestion-source watermarks (`casenote.kr`,
        # `[판례 172]`, `URL: https://`, etc.) and normalize `<br/>` that may
        # have leaked into LLM-quoted excerpts. Beta-7 skips this — the DB
        # sweep already cleaned bodies and the writer never touches `<br/>`.
        answer_markdown = _normalize_html_breaks(answer_markdown)
        answer_markdown = _strip_source_markers(answer_markdown)

    selected_precedents = _dedupe_selected_precedents([_simplify_precedent(row) for row in selected_files])
    case_summary_map = _build_case_summary_map(claim_ledger)
    source_summary_map = _build_source_summary_map(claim_ledger)
    case_number_counts: dict[str, int] = {}
    for precedent in selected_precedents:
        case_number = str(precedent.get("caseNumber") or "").strip()
        if case_number:
            case_number_counts[case_number] = case_number_counts.get(case_number, 0) + 1
    case_source_ids: dict[str, set[str]] = {}
    for claim in claim_ledger:
        source_file_id = str(claim.get("source_file_id") or "").strip()
        if not source_file_id:
            continue
        for supporting_case in claim.get("supporting_cases") or []:
            case_number = str(supporting_case.get("case_number") or "").strip()
            if case_number:
                case_source_ids.setdefault(case_number, set()).add(source_file_id)
    for precedent in selected_precedents:
        case_number = str(precedent.get("caseNumber") or "").strip()
        precedent_id = str(precedent.get("precedentId") or "").strip()
        precedent_ids = {precedent_id, *(str(item).strip() for item in (precedent.get("alternatePrecedentIds") or []) if str(item).strip())}
        if precedent_id and precedent_id in source_summary_map:
            precedent["summary"] = source_summary_map[precedent_id]
            continue
        source_ids_for_case = case_source_ids.get(case_number, set())
        case_summary_safe = not source_ids_for_case or bool(precedent_ids & source_ids_for_case)
        if case_number and case_number_counts.get(case_number, 0) == 1 and case_number in case_summary_map and case_summary_safe:
            precedent["summary"] = case_summary_map[case_number]
    claim_ledger = _enrich_claim_ledger(claim_ledger, selected_precedents=selected_precedents)
    if is_beta7:
        answer_markdown = _rewrite_beta7_answer_markdown(answer_markdown, claim_ledger)
    else:
        answer_markdown = _rewrite_answer_markdown_citations(answer_markdown, claim_ledger)
    enriched_answer_plan = _enrich_answer_plan(answer_plan, selected_precedents=selected_precedents, claim_ledger=claim_ledger)
    answer_markdown = _annotate_anonymous_reference_list_citations(answer_markdown, enriched_answer_plan)
    proposition_source_task = str(
        selection_meta.get("original_user_task")
        or selection_meta.get("downstream_user_task")
        or selection_meta.get("userTask")
        or ""
    ).strip()
    if (analysis_mode or "").lower() == "beta8":
        proposition_rewrite = rewrite_answer_with_legal_proposition_guard(
            source_task=proposition_source_task,
            answer_markdown=answer_markdown,
        )
    else:
        proposition_rewrite = None
    if proposition_rewrite is not None:
        answer_markdown = proposition_rewrite.answer_markdown
    selected_claims = _select_body_claims(claim_ledger, enriched_answer_plan)
    if not is_document_mode and not claim_ledger and len(chunk_outputs) > 0:
        answer_markdown = (
            "## 관련 판례를 찾지 못했습니다\n\n"
            "제공된 판례 DB에서 이 질문과 직접 관련된 사례를 식별하지 못했습니다. "
            "다음 중 한 가지로 다시 시도해 주세요.\n\n"
            "- 문제가 되는 **행위를 구체적으로** 적어 주세요 (누가, 언제, 어디서, 어떤 방식으로).\n"
            "- 염두에 두고 있는 **법령·죄명**이 있다면 함께 적어 주세요 "
            "(예: 변호사법 위반, 명예훼손, 업무방해 등).\n"
            "- 상대방의 대응이나 손해가 있다면 그 내용을 포함해 주세요.\n\n"
            "질문을 다시 보내 주시면 해당 쟁점에 맞는 판례로 다시 분석합니다."
        )
        enriched_answer_plan = {
            "likely_outcome": "제공된 판례 DB에서 이 질문과 직접 관련된 판례를 찾지 못했습니다.",
            "confidence_basis": [],
            "helpful_facts": [],
            "harmful_facts": [],
            "body_claim_ids": [],
            "claim_groups": [],
            "precedent_buckets": {"very_similar": [], "similar": [], "usable": [], "other": []},
        }
        selected_claims = []
    elif not is_document_mode and not is_beta7 and not (proposition_rewrite and proposition_rewrite.rewritten):
        # Beta-4/5/6 emit a self-contained easy-overview 1층 already
        # written by the LLM. Prepending the heuristic 가장 같은 사실관계 +
        # 결론 요약 blocks above it would push the laypeople layer out of the
        # first viewport and duplicate content. Skip both prepends in that
        # case and let the LLM-authored layers stand on their own.
        # Beta-7 writes its own conclusion + structure in the minimal prompt,
        # so we always skip these heuristic prepends for Beta-7.
        if "## 한눈에 보는 결론" not in answer_markdown and "## 어렵지 않아요" not in answer_markdown:
            answer_markdown = _prepend_analysis_summary(
                answer_markdown,
                answer_plan=enriched_answer_plan,
                claims=selected_claims,
                selected_precedents=selected_precedents,
                selection_meta=selection_meta,
            )
            answer_markdown = _prepend_same_fact_precedent_section(
                answer_markdown,
                claims=selected_claims,
                selected_precedents=selected_precedents,
                selection_meta=selection_meta,
            )
    answer_markdown = _normalize_public_answer_sections(answer_markdown)
    # Beta-7: separate the writer's actual citations from planner candidates.
    # `citedClaims` = claims the writer's body markdown explicitly references
    # via `[N]`/`[N-S/Om]` tokens (captured pre-substitution as
    # `cited_token_indices`). `candidateClaims` = planner-selected claims.
    cited_claims: list[dict[str, Any]] = []
    if cited_token_indices or cited_case_numbers_raw:
        cited_claims = [
            claim for claim in claim_ledger
            if (
                int(claim.get("_writer_claim_index") or 0) in cited_token_indices
                or re.sub(r"\s+", "", str(claim.get("case_number") or "")) in cited_case_numbers_raw
            )
        ]
    used_precedents = _build_used_precedents(selected_claims=selected_claims, selected_precedents=selected_precedents)
    used_ids = _collect_used_precedent_ids_from_claims(selected_claims)
    if not used_ids:
        used_ids = _collect_used_precedent_ids_from_chunk_outputs(chunk_outputs)
    if used_precedents:
        used_ids = [str(item.get("precedentId") or "") for item in used_precedents if str(item.get("precedentId") or "").strip()] or used_ids
    artifact_paths = _collect_export_artifacts(run_dir, variant_dir, job_id=job_id) if is_document_mode else {
        "markdownPath": "",
        "markdownUrl": "",
        "htmlPath": "",
        "htmlUrl": "",
        "hwpxPath": "",
        "hwpxUrl": "",
        "pdfPath": "",
        "pdfUrl": "",
        "previewImagePaths": [],
        "previewImageUrls": [],
    }
    return {
        "answerMarkdown": answer_markdown,
        "selectedPrecedents": selected_precedents,
        "usedPrecedents": used_precedents,
        "claims": claim_ledger,
        "selectedClaims": selected_claims,
        # Beta-7+: writer's actual citations vs planner candidates.
        # Older modes leave `citedClaims` empty (UI falls back to selectedClaims).
        "citedClaims": cited_claims,
        "candidateClaims": selected_claims,
        "answerPlan": enriched_answer_plan,
        "usedPrecedentIds": used_ids,
        "summary": comparison_summary,
        "outputPaths": {
            "runDir": str(run_dir),
            "variantDir": str(variant_dir),
            "answerPath": str(answer_path),
            **artifact_paths,
        },
    }


_WRITER_CITED_TOKEN_RE = re.compile(r"\[(\d{1,3})(?:-[SO]\d{1,3})?\]")
_REFERENCE_LIST_HEADER_INSPECT = re.compile(r"^##\s*참고\s*판례\s*목록\s*$", re.MULTILINE)
# Korean case_number shape: 2~4 digit year + 1~4 Hangul filing-class +
# 1~6 digit case num. Compound forms like `2017가단5078, 5079` allowed.
_CASE_NUMBER_IN_BODY = re.compile(
    r"(?<![\w\d])(\d{2,4}[가-힣]{1,4}\d{1,6}(?:\s*,\s*\d{1,6})*)(?![\w\d])"
)


def _extract_cited_case_numbers_in_body(markdown: str) -> set[str]:
    """Walk the answer markdown's BODY (everything before `## 참고 판례 목록`)
    and collect every case_number the writer cited directly. The writer
    sometimes emits `(법원 ... 사건번호 판결)` without using the `[N-Sm]`
    token, so token-only extraction misses these citations.

    Returns a set of compact (whitespace-stripped) case_numbers. Caller
    intersects with claim_ledger to populate `citedClaims`.
    """
    if not markdown:
        return set()
    split_match = _REFERENCE_LIST_HEADER_INSPECT.search(markdown)
    body_part = markdown[: split_match.start()] if split_match else markdown
    out: set[str] = set()
    for m in _CASE_NUMBER_IN_BODY.finditer(body_part):
        out.add(re.sub(r"\s+", "", m.group(1)))
    return out


def _extract_writer_cited_claim_indices(markdown: str) -> set[int]:
    """Walk the answer markdown and collect 1-based claim indices the writer
    referenced via `[N]` / `[N-Sm]` / `[N-Om]` tokens. After token
    substitution the actual `[N-Sm]` markers are gone, so this scan must
    happen BEFORE substitution OR we leave a parallel marker. Currently we
    extract from raw markdown — the substitution stash isn't reachable here
    from build_result_payload. Implementations note: token substitution
    runs in `_rewrite_beta7_answer_markdown` BEFORE this function reads the
    output, so this returns empty for Beta-7 unless we also stash indices.
    For now use a citation-shape heuristic on the substituted output: match
    case_numbers in body sections and look them up in claim_ledger.
    Beta-7's output IS post-substitution, so this gathers indices the
    indirect way.
    """
    if not markdown:
        return set()
    indices: set[int] = set()
    for m in _WRITER_CITED_TOKEN_RE.finditer(markdown):
        try:
            indices.add(int(m.group(1)))
        except (TypeError, ValueError):
            continue
    return indices


def load_precedent_detail(run_dir: Path, precedent_id: str, *, variant_name: str = QUESTION_VARIANT_NAME) -> dict[str, Any]:
    payload = build_result_payload(run_dir, variant_name=variant_name)
    selected_precedents = payload.get("selectedPrecedents") or []
    chunk_outputs = _load_jsonl(run_dir / variant_name / "chunk_outputs.jsonl")
    # Load LLM-generated per-precedent summaries (work16 writes these out
    # during the question variant pipeline). Pass them through so the drawer
    # always shows a real summary instead of falling back to a regex-cleaned
    # body snippet for precedents that didn't surface in claim_ledger.
    summaries_path = run_dir / variant_name / "precedent_summaries.json"
    precedent_summaries: dict[str, dict[str, str]] = {}
    if summaries_path.exists():
        try:
            raw = json.loads(summaries_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                precedent_summaries = raw
        except Exception:
            precedent_summaries = {}
    for precedent in selected_precedents:
        if precedent.get("precedentId") == precedent_id or precedent_id in (precedent.get("alternatePrecedentIds") or []):
            return build_precedent_detail(precedent, chunk_outputs, precedent_summaries=precedent_summaries)
    raise KeyError(precedent_id)
