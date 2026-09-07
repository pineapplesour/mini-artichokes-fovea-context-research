from __future__ import annotations

import dataclasses
import json
import os
import re
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .config import (
    DEFAULT_ANALYZE_MODEL,
    DEFAULT_DRAFT_MODEL,
    DEFAULT_GLOBAL_MAX_INFLIGHT,
    DEFAULT_JOB_MAX_ATTEMPTS,
    DEFAULT_KEY_MAX_INFLIGHT,
    DEFAULT_KEY_MIN_GAP_MS,
    DEFAULT_KEY_RPM_LIMIT,
    DEFAULT_RETRY_BACKOFF_SECONDS,
    DEFAULT_KEY_TPM_LIMIT,
    DEFAULT_SELECT_MODEL,
    DEFAULT_TOP_K,
    DEFAULT_WORKER_COUNT,
    DOCUMENT_PRESETS,
    LEGAL_RAG_SCRIPT,
    QUESTION_VARIANT_NAME,
    RUNS_ROOT,
    WORKSPACE_SCRIPTS,
)
from .exporters import build_export_artifacts
from .models import build_result_payload, load_precedent_detail, project_live_status, strip_document_meta_leak
from .search import select_top_precedents

if str(WORKSPACE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_SCRIPTS))

import legal_evidence_rag as rag  # type: ignore


TERMINAL_JOB_STATES = {"completed", "failed", "cancelled", "interrupted"}
FINAL_ARTIFACT_COMPLETED_STATES = {"question_variant_completed"}
# Allow up to 2 non-Hangul filler chars between syllables to catch typos like
# `고1소장`, `고 소 장`, `고-소장` etc.
DOCUMENT_TYPE_PATTERN = re.compile(
    r"고[^가-힣]{0,2}소[^가-힣]{0,2}(?:장|작)"
    r"|고[^가-힣]{0,2}발[^가-힣]{0,2}장"
    r"|내[^가-힣]{0,2}용[^가-힣]{0,2}증[^가-힣]{0,2}명"
    r"|변호인\s*의견서|변호인의견서|의견서|준비서면|답변서|항소이유서|탄원서|진정서|계약서|합의서"
)
DOCUMENT_ACTION_PATTERN = re.compile(
    r"작성|써\s*줘|써줘|만들|초안|문서화|양식|정리해\s*줘|정리해줘|제출|작성해\s*줘|작성해줘|보내|보내야"
)


def _normalize_task_match_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _user_context_excluding_primary(conversation: list[dict[str, str]], primary_text: str) -> str:
    primary = _normalize_task_match_text(primary_text)
    extras: list[str] = []
    seen: set[str] = set()
    for row in conversation[-6:]:
        if row.get("role") != "user":
            continue
        text = str(row.get("text") or "").strip()
        normalized = _normalize_task_match_text(text)
        if not normalized or normalized in seen:
            continue
        if normalized == primary or (primary and normalized in primary):
            continue
        extras.append(text)
        seen.add(normalized)
    return " ".join(extras).strip()


def _effective_question_user_task(
    user_task: str,
    *,
    analysis_mode: str,
    selection_meta: dict[str, Any] | None,
) -> str:
    original = str(user_task or "").strip()
    meta = selection_meta or {}
    explicit = str(meta.get("downstream_user_task") or "").strip()
    if explicit:
        return explicit
    return original


def _clean_headline_text(value: str, *, limit: int = 140) -> str:
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
        if re.fullmatch(r"\d+\s*심", line, flags=re.IGNORECASE):
            continue
        if re.fullmatch(r"(취득세|소득세|법인세|부가가치세|양도소득세|상속세|증여세|지방세)", line, flags=re.IGNORECASE):
            continue
        if re.fullmatch(
            r"[가-힣A-Za-z0-9·()\s]+법원\s+\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*선고\s*[0-9가-힣()누구합단도재마나카허저]+\s*판결(?:\s*\[[^\]]+\])?",
            line,
            flags=re.IGNORECASE,
        ):
            continue
        filtered.append(line)
    text = " ".join(filtered)
    text = re.sub(r"\[판례\s*\d+\]\s*", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b판례\s*\d+\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"(제목|확정\s*날짜|항소\s*날짜|날짜|url)\s*:\s*", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"【[^】]+】", " ", text)
    text = re.sub(r"▣[^\n]+", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\[사건\s*정보\]", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(항소|확정)\b", " ", text)
    text = re.sub(r"^(?:(?:\d+\s*심)|(?:취득세|소득세|법인세|부가가치세|양도소득세|상속세|증여세|지방세))\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(?:(?:\d+\s*심)|(?:취득세|소득세|법인세|부가가치세|양도소득세|상속세|증여세|지방세))\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(?:주문|이유)\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\d+\.\s*", "", text)
    text = re.sub(r"\s+(?:주문|이유)\s+", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _is_document_drafting_request(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if re.search(r"문서화|문서로\s*(?:작성|만들|정리)|초안으로\s*(?:작성|만들)|양식으로\s*(?:작성|만들)", text):
        return True
    return bool(DOCUMENT_TYPE_PATTERN.search(text) and DOCUMENT_ACTION_PATTERN.search(text))


def _headline_excerpt_from_text(value: str, *, limit: int = 110) -> str:
    text = _clean_headline_text(value, limit=800)
    text = re.sub(r"-{6,}", " ", text)
    text = re.sub(r"^사\s*건\s*:?\s*", "", text)
    text = re.sub(r"^[가-힣A-Za-z0-9·\(\)\s]+법원\s+\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*선고\s*[0-9가-힣\(\)누구합단도재마나카허저]+판결\s*", "", text)
    text = re.sub(r"^\[[^\]]+\]\s*", "", text)
    text = re.sub(r"^사\s*건\s+\S+\s*", "", text)
    text = re.sub(r"^\S+\s+선고\s+", "", text)
    text = re.sub(r"\b(원고|피고|청구인|피청구인|항소인|피항소인|상고인|피상고인|변론종결|주문|이유)\b.*$", "", text)
    text = re.sub(r"^(주문|이유)\s*", "", text)
    text = re.sub(r"^\S+\s+판결\s*", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""
    sentence = re.split(r"(?<=[\.\?!다])\s+", text, maxsplit=1)[0].strip()
    cleaned = sentence or text
    return cleaned[:limit]


def _is_meaningful_headline_body(value: str) -> bool:
    text = _clean_headline_text(value, limit=160)
    if not text:
        return False
    bare = text.strip("[]()·-–—. ").strip()
    if not bare:
        return False
    if re.fullmatch(r"[0-9.]+", bare):
        return False
    if len(bare) <= 2 and bare.replace(" ", "").isalnum():
        return False
    return True


def _normalize_client_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return re.sub(r"[^A-Za-z0-9_.:-]", "", text)[:160]


def _token_count_for_runtime_text(text: str) -> int:
    try:
        return int(rag._count_tokens(str(text or "")))  # type: ignore[attr-defined]
    except Exception:
        return max(1, len(str(text or "")) // 4)


def _load_json_file(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def _load_jsonl_file(path: Path, *, limit: int = 120) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fp:
            for line in fp:
                if len(rows) >= limit:
                    break
                if not line.strip():
                    continue
                parsed = json.loads(line)
                if isinstance(parsed, dict):
                    rows.append(parsed)
    except Exception:
        return rows
    return rows


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


@dataclasses.dataclass
class JobRecord:
    job_id: str
    mode: str
    user_task: str
    run_dir: Path
    created_at: float
    status_path: Path
    selected_manifest_path: Path
    chunk_plan: list[dict[str, Any]]
    selected_count: int = 0
    process_pid: int | None = None
    finished_at: float | None = None
    error: str = ""
    document_preset_id: str = ""
    document_context: str = ""
    sample_path: str = ""
    runtime_control_path: Path | None = None
    cancel_requested: bool = False
    cancel_reason: str = ""
    client_id: str = ""
    analysis_mode: str = "precise"  # "precise" | "fast" | "beta2" ... | "beta8" (beta1은 레거시)


class LawkeyJobManager:
    UPLOAD_SAMPLE_PREFIX = "upload:"
    MAX_SAMPLE_REFERENCE_LENGTH = 260
    SAMPLE_TOKEN_RE = re.compile(r"^[A-Za-z0-9._\-가-힣]{1,220}$")

    def __init__(self, *, runs_root: Path = RUNS_ROOT) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.Lock()
        slot_limit = max(1, int(os.environ.get("LAWKEY_EXECUTION_SLOTS", "3")))
        self._execution_slot = threading.Semaphore(slot_limit)
        self._runs_root = runs_root
        self._runs_root.mkdir(parents=True, exist_ok=True)

    def resume_after_restart(self) -> None:
        """Called once at server startup to re-spawn workers for any jobs interrupted by a prior restart."""
        try:
            self._hydrate_jobs_from_disk()
        except Exception:
            pass

    def create_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        from .intent import decide_job_intent  # local import to avoid cycles

        user_task = str(payload.get("userTask") or "").strip()
        if not user_task:
            raise ValueError("userTask is required")
        intent = decide_job_intent(
            input_mode_chip=("document" if str(payload.get("mode") or "question") == "document" else "question"),
            prompt=user_task,
            is_follow_up=False,
            explicit_preset=str(payload.get("documentPresetId") or ""),
        )
        mode = intent.mode
        if mode == "question" and not payload.get("skipIntentCheck"):
            # LLM safety net for typos/unusual phrasing the rule-based
            # detector missed. Skip when payload explicitly says
            # `skipIntentCheck` (frontend already classified) to avoid double work.
            try:
                classification = self.classify_intent({"userTask": user_task})
                if classification.get("intent") == "document":
                    mode = "document"
            except Exception:
                pass
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        run_dir = self._runs_root / job_id
        run_dir.mkdir(parents=True, exist_ok=True)
        status_path = run_dir / "_runtime" / "status.json"
        selected_manifest_path = run_dir / "selected_precedents.json"
        status_path.parent.mkdir(parents=True, exist_ok=True)
        document_preset_id = str(payload.get("documentPresetId") or "").strip()
        document_context = str(payload.get("documentContext") or payload.get("document_context") or "").strip()
        if mode == "document":
            document_preset_id = self._infer_document_preset_id(f"{user_task}\n{document_context}", document_preset_id)
        sample_path = str(payload.get("samplePath") or "").strip()
        if mode == "document" and sample_path:
            sample_path = self._sample_reference_for_storage(self._resolve_sample_path_reference(sample_path))
        job = JobRecord(
            job_id=job_id,
            mode=mode,
            user_task=user_task,
            run_dir=run_dir,
            created_at=time.time(),
            status_path=status_path,
            selected_manifest_path=selected_manifest_path,
            chunk_plan=[],
            document_preset_id=document_preset_id,
            document_context=document_context,
            sample_path=sample_path,
            runtime_control_path=run_dir / "_runtime" / "control.json",
            client_id=_normalize_client_id(payload.get("clientId") or payload.get("client_id") or ""),
            analysis_mode=(lambda v: v if v in {"fast","beta1","beta2","beta3","beta4","beta5","beta6","beta7","beta8"} else "precise")(
                str(payload.get("analysisMode") or payload.get("analysis_mode") or "precise").lower()
            ),
        )
        with self._lock:
            self._jobs[job_id] = job
        self._write_job_meta(job)
        self._prepare_runtime_files(job)
        self._write_status(job, {"phase": "startup", "state": "queued", "selected_file_count": 0})
        thread = threading.Thread(target=self._run_job, args=(job,), daemon=True)
        thread.start()
        return {
            "jobId": job_id,
            "statusUrl": f"/api/jobs/{job_id}",
            "resultUrl": f"/api/jobs/{job_id}/result",
        }

    def list_jobs(self, client_id: str = "") -> list[dict[str, Any]]:
        normalized_client_id = _normalize_client_id(client_id)
        self._hydrate_jobs_from_disk()
        with self._lock:
            jobs = list(self._jobs.values())
        jobs.sort(key=lambda item: item.created_at, reverse=True)
        rows: list[dict[str, Any]] = []
        for job in jobs:
            if normalized_client_id and job.client_id != normalized_client_id:
                continue
            runtime = self._read_status(job)
            self._sync_job_with_runtime(job, runtime)
            runtime.setdefault("selected_file_count", job.selected_count)
            runtime["elapsed_seconds"] = int(time.time() - job.created_at)
            projected = project_live_status(runtime, chunk_plan=job.chunk_plan, worker_count=DEFAULT_WORKER_COUNT)
            projected.update(
                {
                    "jobId": job.job_id,
                    "clientId": job.client_id,
                    "mode": job.mode,
                    "userTask": job.user_task,
                    "error": job.error,
                    "createdAt": job.created_at,
                    "finishedAt": job.finished_at,
                    "queuePosition": self._queue_position(job.job_id),
                    "headlineFrames": self._headline_frames_for_job(job),
                    "analysisMode": job.analysis_mode,
                }
            )
            rows.append(projected)
        return rows

    def get_job_status(self, job_id: str) -> dict[str, Any]:
        job = self._require_job(job_id)
        runtime = self._read_status(job)
        self._sync_job_with_runtime(job, runtime)
        runtime.setdefault("selected_file_count", job.selected_count)
        elapsed = int(time.time() - job.created_at)
        runtime["elapsed_seconds"] = elapsed
        projected = project_live_status(runtime, chunk_plan=job.chunk_plan, worker_count=DEFAULT_WORKER_COUNT)
        projected.update(
            {
                "jobId": job.job_id,
                "mode": job.mode,
                "userTask": job.user_task,
                "error": job.error,
                "createdAt": job.created_at,
                "finishedAt": job.finished_at,
                "queuePosition": self._queue_position(job.job_id),
                "headlineFrames": self._headline_frames_for_job(job),
                "analysisMode": job.analysis_mode,
            }
        )
        return projected

    def _hydrate_jobs_from_disk(self, limit: int = 24) -> None:
        candidates = sorted(
            [path for path in self._runs_root.glob("job-*") if path.is_dir()],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )[:limit]
        if not candidates:
            return
        with self._lock:
            known_ids = set(self._jobs.keys())
        for run_dir in candidates:
            job_id = run_dir.name
            if job_id in known_ids:
                continue
            recovered = self._recover_job(job_id)
            if recovered is None:
                continue
            with self._lock:
                self._jobs.setdefault(job_id, recovered)
            # Re-spawn worker for jobs whose state was reset to queued
            # because of a server restart while running.
            try:
                runtime = json.loads(recovered.status_path.read_text(encoding="utf-8"))
            except Exception:
                runtime = {}
            if runtime.get("state") == "queued" and recovered.finished_at is None:
                thread = threading.Thread(target=self._run_job, args=(recovered,), daemon=True)
                thread.start()

    def _sync_job_with_runtime(self, job: JobRecord, runtime: dict[str, Any]) -> None:
        if self._promote_final_artifact_completion(job, runtime):
            return
        finished_at = runtime.get("finished_at")
        state = str(runtime.get("state") or "")
        if finished_at and job.finished_at is None:
            job.finished_at = float(finished_at)
        if state in TERMINAL_JOB_STATES and job.finished_at is None:
            job.finished_at = time.time()
        if state == "completed":
            job.error = ""
        if state and runtime.get("error") and not job.error:
            job.error = str(runtime.get("error") or "")
        if not job.selected_count:
            selected_count = runtime.get("selected_file_count")
            try:
                job.selected_count = int(selected_count or 0)
            except (TypeError, ValueError):
                job.selected_count = 0

    def _candidate_final_artifact_path(self, run_dir: Path, runtime: dict[str, Any], *, mode: str) -> Path | None:
        raw_path = str(runtime.get("final_draft_path") or "").strip()
        variant_dir = run_dir / QUESTION_VARIANT_NAME
        if mode == "document":
            candidates = [variant_dir / "final_document.md"]
            if raw_path and Path(raw_path).name == "final_document.md":
                candidates.insert(0, Path(raw_path))
        else:
            candidates: list[Path] = []
            if raw_path:
                candidates.append(Path(raw_path))
            candidates.extend([
                variant_dir / "final_answer.md",
                variant_dir / "final_answer_v2.md",
            ])
        for candidate in candidates:
            try:
                if candidate.exists() and candidate.is_file() and candidate.stat().st_size > 0:
                    return candidate
            except OSError:
                continue
        return None

    def _promote_final_artifact_completion(self, job: JobRecord, runtime: dict[str, Any]) -> bool:
        state = str(runtime.get("state") or "")
        has_completed_state = state == "completed"
        if state not in FINAL_ARTIFACT_COMPLETED_STATES and not has_completed_state:
            return False
        artifact_path = self._candidate_final_artifact_path(job.run_dir, runtime, mode=job.mode)
        if artifact_path is None:
            return False
        try:
            finished_at = float(runtime.get("finished_at") or artifact_path.stat().st_mtime)
        except (OSError, TypeError, ValueError):
            finished_at = time.time()
        try:
            total_chunks = int(runtime.get("chunk_count") or runtime.get("total_chunks") or len(job.chunk_plan) or 0)
        except (TypeError, ValueError):
            total_chunks = len(job.chunk_plan)
        try:
            completed_chunks = int(runtime.get("completed_chunks") or total_chunks)
        except (TypeError, ValueError):
            completed_chunks = total_chunks
        promoted = dict(runtime)
        promoted.update(
            {
                "phase": "done",
                "state": "completed",
                "error": "",
                "finished_at": finished_at,
                "final_draft_path": str(artifact_path),
            }
        )
        if job.selected_count:
            promoted["selected_file_count"] = job.selected_count
        if total_chunks:
            promoted["chunk_count"] = total_chunks
            promoted["completed_chunks"] = max(completed_chunks, total_chunks)
        if job.created_at:
            promoted["elapsed_seconds"] = max(0, int(finished_at - job.created_at))
        self._write_status(job, promoted)
        runtime.clear()
        runtime.update(promoted)
        job.finished_at = finished_at
        job.error = ""
        return True

    def _headline_frames_for_job(self, job: JobRecord) -> list[str]:
        if not job.selected_manifest_path.exists():
            return []
        try:
            rows = json.loads(job.selected_manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        frames: list[str] = []
        for row in rows[:100]:
            case_number = str(row.get("case_number") or "").strip()
            title = _clean_headline_text(str(row.get("case_name") or row.get("document_title") or row.get("title") or ""), limit=110)
            raw_text = str(row.get("extracted_text") or row.get("full_text") or row.get("text") or "").strip()
            excerpt = title if _is_meaningful_headline_body(title) else _headline_excerpt_from_text(raw_text)
            if not _is_meaningful_headline_body(excerpt):
                continue
            headline = " ".join(part for part in [f"[{case_number}]" if case_number else "", excerpt] if part).strip()
            if headline and headline not in frames:
                frames.append(headline)
        return frames

    def _queue_position(self, job_id: str) -> int:
        with self._lock:
            pending = [job for job in self._jobs.values() if job.finished_at is None]
        pending.sort(key=lambda item: item.created_at)
        for index, job in enumerate(pending, start=1):
            if job.job_id == job_id:
                return index
        return 0

    def get_job_result(self, job_id: str) -> dict[str, Any]:
        job = self._require_job(job_id)
        payload = build_result_payload(job.run_dir, variant_name=QUESTION_VARIANT_NAME, job_id=job.job_id, mode=job.mode, analysis_mode=job.analysis_mode)
        payload.update({"jobId": job.job_id, "mode": job.mode})
        return payload

    def cancel_job(self, job_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        job = self._require_job(job_id)
        raw_reason = str((payload or {}).get("reason") or "").strip()
        reason = raw_reason if raw_reason and raw_reason != "user_cancelled" else "사용자가 요청을 취소했습니다."
        job.cancel_requested = True
        job.cancel_reason = reason
        job.error = reason
        finished_at = time.time()
        if job.finished_at is None:
            job.finished_at = finished_at
        self._write_cancel_control(job, reason)
        self._terminate_job_process(job)
        try:
            current_status = self._read_status(job)
        except Exception:
            current_status = {}
        current_status.update(
            {
                "phase": "done",
                "state": "cancelled",
                "selected_file_count": job.selected_count,
                "completed_chunks": int(current_status.get("completed_chunks") or 0),
                "chunk_count": int(current_status.get("chunk_count") or len(job.chunk_plan) or 0),
                "elapsed_seconds": int(job.finished_at - job.created_at),
                "error": reason,
                "finished_at": job.finished_at,
            }
        )
        self._write_status(job, current_status)
        return self.get_job_status(job_id)

    def follow_up(self, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        job = self._require_job(job_id)
        user_task = str(payload.get("userTask") or "").strip()
        if not user_task:
            raise ValueError("userTask is required")
        client_id = _normalize_client_id(payload.get("clientId") or payload.get("client_id") or job.client_id)
        if payload.get("forceNewJob") or payload.get("force_new_job"):
            from .intent import decide_job_intent

            intent = decide_job_intent(
                input_mode_chip="question",
                prompt=user_task,
                is_follow_up=True,
            )
            is_document_request = intent.mode == "document"
            if not is_document_request:
                try:
                    classification = self.classify_intent({"userTask": user_task})
                    if classification.get("intent") == "document":
                        is_document_request = True
                except Exception:
                    pass
            if is_document_request:
                document_context = self._build_follow_up_document_context(job, user_task=user_task)
                created = self.create_job(
                    {
                        "mode": "document",
                        "userTask": self._build_follow_up_document_task(original_job=job, user_task=user_task),
                        "clientId": client_id,
                        "documentPresetId": self._infer_document_preset_id(user_task, ""),
                        "documentContext": document_context,
                        "skipIntentCheck": True,
                    }
                )
                return {
                    "mode": "new_job_started",
                    "sourceJobId": job.job_id,
                    "neededKeywords": [],
                    "missingInformation": [],
                    **created,
                }
            needed_keywords = self._fallback_follow_up_keywords(user_task)
            missing_information = ["브라우저 요청 시간초과를 피하기 위해 추가질문을 새 분석 작업으로 처리합니다."]
            created = self.create_job(
                {
                    "mode": "question",
                    "userTask": self._build_follow_up_search_task(
                        original_job=job,
                        user_task=user_task,
                        needed_keywords=needed_keywords,
                        missing_information=missing_information,
                    ),
                    "clientId": client_id,
                }
            )
            return {
                "mode": "new_job_started",
                "sourceJobId": job.job_id,
                "neededKeywords": needed_keywords,
                "missingInformation": missing_information,
                **created,
            }
        packs = self._build_follow_up_packs(job, user_task=user_task)
        missing_information: list[str] = []
        needed_keywords: list[str] = []
        if not packs:
            needed_keywords.extend(self._fallback_follow_up_keywords(user_task))
        for index, pack in enumerate(packs, start=1):
            parsed = self._ask_follow_up_pack(job, user_task=user_task, pack=pack, pack_index=index, pack_total=len(packs))
            missing_information.extend(str(item) for item in parsed.get("missing_information") or [])
            needed_keywords.extend(str(item) for item in parsed.get("needed_keywords") or [])
            answer = str(parsed.get("answer_markdown") or parsed.get("answerMarkdown") or "").strip()
            if parsed.get("answerable") and answer:
                return {
                    "mode": "answered_from_existing",
                    "sourceJobId": job.job_id,
                    "answerMarkdown": rag._strip_question_answer_meta_prefix(answer),  # type: ignore[attr-defined]
                    "neededKeywords": _dedupe_keep_order(needed_keywords),
                    "missingInformation": _dedupe_keep_order(missing_information),
                }
        needed_keywords = _dedupe_keep_order(needed_keywords or self._fallback_follow_up_keywords(user_task))
        missing_information = _dedupe_keep_order(missing_information)
        created = self.create_job(
            {
                "mode": "question",
                "userTask": self._build_follow_up_search_task(
                    original_job=job,
                    user_task=user_task,
                    needed_keywords=needed_keywords,
                    missing_information=missing_information,
                ),
                "clientId": client_id,
            }
        )
        return {
            "mode": "new_job_started",
            "sourceJobId": job.job_id,
            "neededKeywords": needed_keywords,
            "missingInformation": missing_information,
                **created,
            }

    def _build_follow_up_document_task(self, *, original_job: JobRecord, user_task: str) -> str:
        prior = original_job.user_task.strip()
        current = user_task.strip()
        if prior and prior != current:
            return f"{prior}\n\n[문서 작성 요청]\n{current}"
        return current

    def _build_follow_up_document_context(self, job: JobRecord, *, user_task: str) -> str:
        variant_dir = job.run_dir / QUESTION_VARIANT_NAME
        answer_path = variant_dir / ("final_document.md" if job.mode == "document" else "final_answer.md")
        if not answer_path.exists():
            fallback = variant_dir / "final_answer_v2.md"
            answer_path = fallback if fallback.exists() else answer_path
        answer = ""
        if answer_path.exists():
            answer = answer_path.read_text(encoding="utf-8", errors="ignore").strip()
        parts = [
            "[추가질문 문서화 맥락]",
            "아래 기존 질문과 답변을 배경으로 삼되, 새 판례검색 질문으로 오해하지 말고 현재 문서 작성 요청에 맞는 문서만 작성한다.",
            f"[이전 질문]\n{job.user_task.strip()}",
            f"[문서 작성 요청]\n{user_task.strip()}",
        ]
        if answer:
            parts.append(f"[이전 최종 답변]\n{answer[:10_000]}")
        return "\n\n".join(part for part in parts if part.strip())

    def get_precedent_detail(self, job_id: str, precedent_id: str) -> dict[str, Any]:
        job = self._require_job(job_id)
        return load_precedent_detail(job.run_dir, precedent_id, variant_name=QUESTION_VARIANT_NAME)

    def list_document_presets(self) -> list[dict[str, Any]]:
        return [dict(item) for item in DOCUMENT_PRESETS]

    ALLOWED_UPLOAD_EXTENSIONS = {".hwp", ".hwpx", ".txt", ".md", ".pdf"}

    def save_uploaded_sample(self, filename: str, content: bytes) -> dict[str, str]:
        original_name = filename or "sample.txt"
        ext = Path(original_name).suffix.lower()
        if ext not in self.ALLOWED_UPLOAD_EXTENSIONS:
            raise ValueError(
                f"unsupported file type {ext or '(unknown)'}. allowed: hwp, hwpx, txt, md, pdf"
            )
        safe_name = re.sub(r"[^A-Za-z0-9._\-가-힣]", "_", original_name).strip("._") or "sample.txt"
        upload_dir = self._runs_root / "_uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        stored = upload_dir / f"{uuid.uuid4().hex[:10]}_{safe_name}"
        stored.write_bytes(content)
        # Eagerly attempt text extraction so we surface errors early.
        try:
            preview = rag.extract_text(stored)[:5000]
        except Exception:
            preview = ""
        sample_id = stored.name
        return {
            "path": f"{self.UPLOAD_SAMPLE_PREFIX}{sample_id}",
            "sampleId": sample_id,
            "label": original_name,
            "extractedPreview": preview,
            "extractedChars": len(preview),
        }

    def document_preflight(self, payload: dict[str, Any]) -> dict[str, Any]:
        user_task = str(payload.get("userTask") or "").strip()
        if not user_task:
            raise ValueError("userTask is required")
        conversation_rows = payload.get("conversation") or []
        conversation: list[dict[str, str]] = []
        if isinstance(conversation_rows, list):
            for row in conversation_rows:
                if not isinstance(row, dict):
                    continue
                role = str(row.get("role") or "").strip()
                text = str(row.get("text") or "").strip()
                if role in {"user", "assistant"} and text:
                    conversation.append({"role": role, "text": text})
        requested_preset_id = str(payload.get("documentPresetId") or "").strip()
        resolved_preset_id = self._infer_document_preset_id(user_task, requested_preset_id)
        sample_paths = self._resolve_sample_paths(
            document_preset_id=resolved_preset_id,
            sample_path=str(payload.get("samplePath") or "").strip(),
            user_task=user_task,
        )
        sample_excerpt_parts: list[str] = []
        for index, sample_path in enumerate(sample_paths, start=1):
            try:
                excerpt = rag.extract_text(sample_path)[:5000]
            except Exception:
                excerpt = ""
            if excerpt.strip():
                sample_excerpt_parts.append(f"--- 예시 문서 {index}: {sample_path.name} ---\n{excerpt.strip()}")
        sample_excerpt = "\n\n".join(sample_excerpt_parts)
        source_job_context = ""
        source_job_id = str(payload.get("sourceJobId") or payload.get("previousJobId") or "").strip()
        if source_job_id:
            try:
                source_job_context = self._build_source_job_context(source_job_id)
            except KeyError:
                source_job_context = ""
        try:
            raw = rag.call_chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "법률 문서 초안 preflight planner다. JSON만 출력하라. "
                            "문서 작성 전 더 필요한 사실이 있으면 질문만 하고, 충분하면 판례 검색용 retrieval task를 만들어라."
                        ),
                    },
                    {
                        "role": "user",
                        "content": self._build_document_preflight_prompt(
                            user_task=user_task,
                            conversation=conversation,
                            sample_excerpt=sample_excerpt,
                            source_job_context=source_job_context,
                        ),
                    },
                ],
                model=DEFAULT_ANALYZE_MODEL,
                timeout=45,
            ).strip()
            parsed = self._extract_document_preflight(raw)
        except Exception:
            parsed = {
                "ready": False,
                "questions": [],
                "retrievalTask": "",
                "draftingGoal": "",
                "summary": "",
            }
        complaint_questions = self._complaint_missing_fact_questions(
            user_task=user_task,
            conversation=conversation,
            document_preset_id=resolved_preset_id,
        )
        if complaint_questions:
            parsed["ready"] = False
            parsed["questions"] = _dedupe_keep_order([*parsed.get("questions", []), *complaint_questions])[:3]
        if not parsed["ready"] and not parsed["questions"]:
            parsed["questions"] = self._fallback_document_questions(user_task, conversation)
        if not parsed["draftingGoal"]:
            parsed["draftingGoal"] = self._build_document_goal_text(user_task, conversation)
        if parsed["ready"] and not parsed["retrievalTask"]:
            parsed["retrievalTask"] = self._build_document_retrieval_task(parsed["draftingGoal"], conversation)
        if not parsed["summary"]:
            if parsed["ready"]:
                parsed["summary"] = "문서 초안 작성을 위한 사실관계와 목표가 정리되어 판례 수집을 시작합니다."
            else:
                parsed["summary"] = "초안 품질을 높이려면 아래 사실을 먼저 확인해야 합니다."
        return parsed

    def _build_follow_up_packs(self, job: JobRecord, *, user_task: str) -> list[list[tuple[str, str]]]:
        variant_dir = job.run_dir / QUESTION_VARIANT_NAME
        blocks: list[tuple[str, str]] = []
        answer_path = variant_dir / ("final_document.md" if job.mode == "document" else "final_answer.md")
        if not answer_path.exists():
            fallback = variant_dir / "final_answer_v2.md"
            answer_path = fallback if fallback.exists() else answer_path
        if answer_path.exists():
            blocks.append(("기존 최종 본문", answer_path.read_text(encoding="utf-8", errors="ignore")))
        answer_plan = _load_json_file(variant_dir / "answer_plan.json", {})
        if answer_plan:
            blocks.append(("기존 답변 설계", json.dumps(answer_plan, ensure_ascii=False, indent=2)))
        claim_ledger = _load_json_file(variant_dir / "claim_ledger.json", [])
        if claim_ledger:
            blocks.append(("선택 주장 ledger", json.dumps(claim_ledger, ensure_ascii=False, indent=2)))
        for index, output in enumerate(_load_jsonl_file(variant_dir / "chunk_outputs.jsonl"), start=1):
            blocks.append((f"청크 분석 결과 {index}", json.dumps(output, ensure_ascii=False, indent=2)))
        selected_rows = _load_json_file(variant_dir / "selected_files.json", [])
        if not selected_rows:
            selected_rows = _load_json_file(job.selected_manifest_path, [])
        if isinstance(selected_rows, list):
            for index, row in enumerate(selected_rows[:100], start=1):
                if not isinstance(row, dict):
                    continue
                text = str(row.get("extracted_text") or row.get("full_text") or row.get("text") or row.get("anchor_text") or "").strip()
                metadata = {
                    "file_id": row.get("file_id"),
                    "case_number": row.get("case_number"),
                    "court": row.get("court"),
                    "decision_date": row.get("decision_date"),
                    "case_name": row.get("case_name") or row.get("document_title") or row.get("title"),
                    "relative_path": row.get("relative_path"),
                }
                block_text = f"{json.dumps(metadata, ensure_ascii=False)}\n\n{text}".strip()
                if block_text:
                    blocks.append((f"선택 판례 본문 {index}", block_text))
        budget = max(10_000, int(getattr(rag, "DEFAULT_MAX_REQUEST_TOKENS", 50_000)) - _token_count_for_runtime_text(user_task) - 2_500)
        return self._pack_follow_up_blocks(blocks, max_tokens=budget)

    def _pack_follow_up_blocks(self, blocks: list[tuple[str, str]], *, max_tokens: int) -> list[list[tuple[str, str]]]:
        packs: list[list[tuple[str, str]]] = []
        current: list[tuple[str, str]] = []
        current_tokens = 0
        for key, text in blocks:
            rendered = f"[{key}]\n{text}".strip()
            tokens = _token_count_for_runtime_text(rendered)
            if current and current_tokens + tokens > max_tokens:
                packs.append(current)
                current = []
                current_tokens = 0
            if tokens > max_tokens:
                # 단일 원자 블록은 반으로 나누지 않는다. 모델 한도를 넘는 경우 단독 pack으로 보내고
                # Gemini 쪽 제한/재시도 계층이 처리하도록 둔다.
                packs.append([(key, text)])
                continue
            current.append((key, text))
            current_tokens += tokens
        if current:
            packs.append(current)
        return packs

    def _ask_follow_up_pack(
        self,
        job: JobRecord,
        *,
        user_task: str,
        pack: list[tuple[str, str]],
        pack_index: int,
        pack_total: int,
    ) -> dict[str, Any]:
        evidence = "\n\n".join(f"[{key}]\n{text}" for key, text in pack)
        prompt = (
            "기존 Lawkey 분석 산출물만 보고 추가 질문에 답할 수 있는지 판단하라.\n"
            "규칙:\n"
            "- JSON만 출력한다.\n"
            "- 기존 산출물만으로 답할 수 있으면 answerable=true와 answer_markdown을 쓴다.\n"
            "- answer_markdown에는 내부 사고, self-check, 영어 지시문, claim_id 나열을 넣지 않는다.\n"
            "- 답할 수 없으면 answerable=false, missing_information과 needed_keywords를 채운다.\n"
            "- needed_keywords는 새 판례 검색에 바로 쓸 한국어 키워드/쟁점어만 넣는다.\n\n"
            f"[원래 질문]\n{job.user_task}\n\n"
            f"[추가 질문]\n{user_task}\n\n"
            f"[산출물 묶음 {pack_index}/{pack_total}]\n{evidence}\n\n"
            '출력 JSON:\n{"answerable": true, "answer_markdown": "## 추가 답변\\n...", "missing_information": [], "needed_keywords": []}'
        )
        raw = rag.call_chat(
            [
                {"role": "system", "content": "기존 법률 분석 산출물의 추가 질문 답변 가능성을 엄격히 판단한다. JSON만 출력한다."},
                {"role": "user", "content": prompt},
            ],
            model=DEFAULT_ANALYZE_MODEL,
            timeout=600,
        )
        try:
            parsed = json.loads(rag._extract_json_block(raw))  # type: ignore[attr-defined]
        except Exception:
            parsed = {}
        return parsed if isinstance(parsed, dict) else {}

    def classify_intent(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Ask Gemma whether a user prompt is a legal-analysis question or a
        document-drafting request. For document, return 2-4 clarifying questions.
        Falls back to heuristics on error.
        """
        user_task = str(payload.get("userTask") or "").strip()
        if not user_task:
            raise ValueError("userTask is required")
        context = str(payload.get("context") or "").strip()
        prompt = (
            "사용자 입력이 (A) 법률 쟁점에 대한 분석·답변을 원하는 질문인지, "
            "(B) 실제 제출할 법률 문서(고소장·내용증명·답변서·진정서·변호인 의견서·탄원서 등) "
            "초안 작성을 원하는 요청인지 분류하라.\n"
            "출력은 JSON만. 스키마:\n"
            '{"intent":"question"|"document","document_type":"고소장|내용증명|...","questions":["...", "..."]}\n'
            "규칙:\n"
            "- intent=document 이면 document_type과 문서 작성에 꼭 필요한 사실관계 질문 2~4개를 넣는다.\n"
            "  질문은 한국어, 각 한 문장, 너무 장황하지 않게.\n"
            "- intent=question 이면 document_type=\"\", questions=[].\n"
            "- 확신이 서지 않으면 intent=question.\n\n"
        )
        if context:
            prompt += f"[이전 대화 맥락]\n{context[:4000]}\n\n"
        prompt += f"[사용자 입력]\n{user_task}\n"
        try:
            raw = rag.call_chat(
                [
                    {"role": "system", "content": "한국어 법률 요청 분류기다. JSON만 출력한다."},
                    {"role": "user", "content": prompt},
                ],
                model=DEFAULT_ANALYZE_MODEL,
                timeout=60,
            )
        except Exception:
            raw = ""
        intent = "question"
        document_type = ""
        questions: list[str] = []
        if raw:
            try:
                obj = json.loads(rag._extract_json_block(str(raw)))  # type: ignore[attr-defined]
                if isinstance(obj, dict):
                    intent = str(obj.get("intent") or "question").strip().lower()
                    if intent not in ("question", "document"):
                        intent = "question"
                    document_type = str(obj.get("document_type") or "").strip()
                    raw_questions = obj.get("questions") or []
                    if isinstance(raw_questions, list):
                        questions = [str(q).strip() for q in raw_questions if str(q).strip()][:4]
            except Exception:
                pass
        # Heuristic fallback: if intent came back empty/question but user prompt is
        # clearly a drafting request, flip to document with the old detector.
        if intent == "question" and _is_document_drafting_request(user_task):
            intent = "document"
            if not questions:
                questions = self._fallback_clarification_questions(user_task)
            if not document_type:
                document_type = "고소장" if "고소" in user_task else "법률 문서"
        return {
            "intent": intent,
            "documentType": document_type,
            "questions": questions,
        }

    def _fallback_clarification_questions(self, user_task: str) -> list[str]:
        base = [
            "사건이 발생한 날짜와 대략적인 시각을 알려주세요.",
            "피고소인(상대방)을 어떻게 표시할지, 알고 있는 인적사항이나 관계를 알려주세요.",
            "피고소인이 어떤 말이나 행동을 했는지, 문제된 표현을 가능한 한 그대로 알려주세요.",
        ]
        return base

    def summarize_judge(
        self,
        *,
        judge: dict[str, Any],
        canonical_ids: list[str],
    ) -> dict[str, Any]:
        """Produce a short tendency summary for a judge from a sample of their cases.

        Cached at the call site; called at most once per judge.
        """
        from .config import PRECEDENT_DB_PATH

        if not canonical_ids:
            return {
                "summary": "표본 판례가 부족하여 성향 요약을 생성할 수 없습니다.",
                "samplesUsed": 0,
            }
        conn = sqlite3.connect(str(PRECEDENT_DB_PATH))
        try:
            placeholders = ",".join("?" for _ in canonical_ids[:1000])
            rows = conn.execute(
                f"SELECT case_number, court, decision_date, case_name, substr(full_text, 1, 1200) "
                f"FROM precedents WHERE canonical_id IN ({placeholders})",
                canonical_ids[:1000],
            ).fetchall()
        finally:
            conn.close()
        # Stratified sample: take up to 20 cases across the time range
        rows.sort(key=lambda r: str(r[2] or ""), reverse=True)
        sample = rows[:20]
        samples_block = "\n\n".join(
            f"[{i+1}] {r[0]} | {r[1]} | {r[2]} | {r[3]}\n{r[4]}"
            for i, r in enumerate(sample)
        )
        judge_label = f"{judge.get('name', '')}{(' (' + judge.get('hanja') + ')') if judge.get('hanja') else ''}"
        courts = ", ".join((judge.get("courts") or [])[:6]) or "(미상)"
        prompt = (
            "다음은 한 판사의 판례 표본이다. 이 판사의 전반적 성향·패턴을 3~5문장으로 한국어로 요약하라.\n"
            "포함할 요소:\n"
            "- 주로 다루는 사건 유형 (형사/민사/행정/가사 중 비중)\n"
            "- 양형·인용 경향 (엄격/관대, 기각/인용 비율 등 표본에서 관찰되는 것만)\n"
            "- 눈에 띄는 법리 해석 스타일 (원칙주의 / 형식논리 / 증거중심 등)\n"
            "- 표본의 한계 (적거나 한 쪽에 쏠림 등)\n"
            "주의: 표본에 없는 사실 추측 금지. 단정 금지. 과장 금지.\n"
            "출력은 마크다운 없이 평문 문장들로. 3~5문장.\n\n"
            f"판사: {judge_label}\n"
            f"주요 근무 법원: {courts}\n"
            f"표본 {len(sample)}건 / 전체 {len(canonical_ids)}건\n\n"
            f"[표본]\n{samples_block}\n"
        )
        try:
            raw = rag.call_chat(
                [
                    {"role": "system", "content": "한국 법관의 판례 표본을 보고 성향을 간결히 요약하는 분석가다. 단정 금지, 표본 근거만."},
                    {"role": "user", "content": prompt},
                ],
                model=DEFAULT_ANALYZE_MODEL,
                timeout=300,
            )
        except Exception as exc:
            return {"summary": f"요약 생성 실패: {exc}", "samplesUsed": len(sample)}
        return {"summary": str(raw or "").strip(), "samplesUsed": len(sample)}

    def run_judge_prediction(
        self,
        *,
        judge: dict[str, Any],
        question: str,
        canonical_ids: list[str],
        client_id: str = "",
    ) -> dict[str, Any]:
        """Run a fast LLM pass over a judge's case sample to estimate likely outcome.

        We do not run the full chunked pipeline here; we sample summaries from the
        precedent DB and ask Gemma to estimate based on this judge's record.
        """
        from .config import PRECEDENT_DB_PATH

        if not canonical_ids:
            return {
                "judge": judge,
                "answerMarkdown": (
                    f"## {judge.get('name', '')} 판사 데이터 부족\n\n"
                    "이 판사가 다룬 판례가 데이터베이스에 충분치 않아 추정이 어렵습니다."
                ),
                "samplesUsed": 0,
            }
        conn = sqlite3.connect(str(PRECEDENT_DB_PATH))
        try:
            placeholders = ",".join("?" for _ in canonical_ids[:1000])
            rows = conn.execute(
                f"SELECT canonical_id, case_number, court, decision_date, case_name, substr(full_text, 1, 1500) "
                f"FROM precedents WHERE canonical_id IN ({placeholders})",
                canonical_ids[:1000],
            ).fetchall()
        finally:
            conn.close()
        # Score each by keyword overlap with question, take top 12
        question_tokens = set(re.findall(r"[가-힣A-Za-z0-9]{2,}", question))

        def score_row(row: tuple) -> int:
            text = " ".join(str(x or "") for x in row)
            return sum(1 for tok in question_tokens if tok in text)

        scored = sorted(rows, key=score_row, reverse=True)[:12]
        samples_block = "\n\n".join(
            f"[{i+1}] {r[1]} | {r[2]} | {r[3]} | {r[4]}\n{r[5]}"
            for i, r in enumerate(scored)
        )
        judge_label = f"{judge.get('name', '')}{(' (' + judge.get('hanja') + ')') if judge.get('hanja') else ''}"
        career_courts = ", ".join((judge.get("courts") or [])[:6]) or "(미상)"
        prompt = (
            "다음은 한 판사의 과거 판례 표본이다. "
            "이 판사가 새로 던져진 질문에 대해 어떤 결론을 내릴 가능성이 높은지 추정하라.\n"
            "규칙:\n"
            "- 표본 판례 안의 사실관계, 적용 법령, 양형 패턴, 인용/기각 경향만 근거로 사용한다.\n"
            "- 표본이 불충분하거나 질문과 동떨어졌다고 판단되면 그 점을 명시한다.\n"
            "- 단정적 예측이 아니라 \"이 판사의 과거 패턴상 ~할 가능성이 높다\" 식으로 표현한다.\n"
            "- 출력은 마크다운, 한국어. 다음 섹션 포함:\n"
            "  ## 추정 결론\n  ## 과거 패턴 근거 (인용 표본 번호 표시)\n  ## 표본 한계\n\n"
            f"판사: {judge_label}\n"
            f"주요 근무 법원: {career_courts}\n"
            f"표본 수: {len(scored)}건 / 전체 {len(canonical_ids)}건\n\n"
            f"질문:\n{question}\n\n"
            f"[판례 표본]\n{samples_block}\n"
        )
        try:
            raw = rag.call_chat(
                [
                    {"role": "system", "content": "한국 법관의 과거 판결 표본을 보고 추정 결론을 내는 판사 분석가다. 단정 금지, 패턴 근거 명시."},
                    {"role": "user", "content": prompt},
                ],
                model=DEFAULT_ANALYZE_MODEL,
                timeout=300,
            )
        except Exception as exc:
            return {
                "judge": judge,
                "answerMarkdown": f"## 추정 실패\n\n모델 호출 실패: {exc}",
                "samplesUsed": len(scored),
            }
        return {
            "judge": judge,
            "answerMarkdown": str(raw or "").strip(),
            "samplesUsed": len(scored),
            "totalCases": len(canonical_ids),
        }

    def _fallback_follow_up_keywords(self, user_task: str) -> list[str]:
        tokens = re.findall(r"[가-힣A-Za-z0-9]{2,}", user_task)
        return _dedupe_keep_order(tokens[:8])

    def _build_follow_up_search_task(
        self,
        *,
        original_job: JobRecord,
        user_task: str,
        needed_keywords: list[str],
        missing_information: list[str],
    ) -> str:
        keyword_line = ", ".join(needed_keywords) if needed_keywords else "(모델이 별도 키워드를 특정하지 못함)"
        missing_line = "; ".join(missing_information) if missing_information else "(기존 산출물만으로 답변 가능 판단이 나오지 않음)"
        return (
            f"{user_task}\n\n"
            "[이전 분석에서 이어진 새 판례검색 요청]\n"
            f"- 이전 질문: {original_job.user_task}\n"
            f"- 기존 산출물로 부족했던 이유: {missing_line}\n"
            f"- 새 검색 키워드: {keyword_line}\n"
            "- 위 추가 질문에 직접 답할 수 있는 판례를 다시 선별하고, 기존 분석과 충돌/보완되는 논리도 함께 정리한다."
        )

    def _require_job(self, job_id: str) -> JobRecord:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            job = self._recover_job(job_id)
            if job is not None:
                with self._lock:
                    self._jobs[job_id] = job
        if not job:
            raise KeyError(job_id)
        return job

    def _infer_document_preset_id(self, user_task: str, explicit_preset_id: str) -> str:
        explicit = str(explicit_preset_id or "").strip()
        if explicit:
            return explicit
        text = str(user_task or "").strip()
        if re.search(r"고\s*소\s*장|고소취지|고소인|피고소인|범죄사실|처벌하여\s*주시", text):
            return "complaint"
        if re.search(r"변호인\s*의견서|변호인의견서|피의자|피고인|양형|불송치|불기소|선처", text):
            return "defense_opinion"
        return ""

    def _sample_rejection(self) -> ValueError:
        return ValueError("samplePath is not allowlisted")

    def _path_is_relative_to(self, path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    def _uploads_root(self) -> Path:
        return self._runs_root / "_uploads"

    def _resolve_existing_path(self, path: Path) -> Path:
        try:
            return path.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise self._sample_rejection() from exc

    def _resolve_upload_sample_token(self, token: str) -> Path:
        if not self.SAMPLE_TOKEN_RE.fullmatch(token):
            raise self._sample_rejection()
        upload_root = self._uploads_root().resolve(strict=False)
        resolved = self._resolve_existing_path(upload_root / token)
        if not self._path_is_relative_to(resolved, upload_root) or not resolved.is_file():
            raise self._sample_rejection()
        return resolved

    def _resolve_sample_path_reference(self, sample_path: str) -> Path:
        reference = str(sample_path or "").strip()
        if not reference or len(reference) > self.MAX_SAMPLE_REFERENCE_LENGTH or "\x00" in reference:
            raise self._sample_rejection()
        if reference.startswith(self.UPLOAD_SAMPLE_PREFIX):
            return self._resolve_upload_sample_token(reference[len(self.UPLOAD_SAMPLE_PREFIX) :].strip())
        if self.SAMPLE_TOKEN_RE.fullmatch(reference) and (self._uploads_root() / reference).exists():
            return self._resolve_upload_sample_token(reference)
        raise self._sample_rejection()

    def _sample_reference_for_storage(self, resolved_path: Path) -> str:
        upload_root = self._uploads_root().resolve(strict=False)
        resolved = self._resolve_existing_path(resolved_path)
        if self._path_is_relative_to(resolved, upload_root):
            return f"{self.UPLOAD_SAMPLE_PREFIX}{resolved.name}"
        raise self._sample_rejection()

    def _preset_paths_for_id(self, document_preset_id: str) -> list[Path]:
        if not document_preset_id:
            return []
        for preset in DOCUMENT_PRESETS:
            preset_ids = {str(preset.get("id") or "").strip(), *[str(item).strip() for item in (preset.get("aliases") or [])]}
            if document_preset_id in preset_ids:
                raw_paths = preset.get("paths") or [preset.get("path")]
                paths: list[Path] = []
                for raw_path in raw_paths:
                    if not str(raw_path or "").strip():
                        continue
                    try:
                        path = Path(str(raw_path)).resolve(strict=True)
                    except (OSError, RuntimeError):
                        continue
                    paths.append(path)
                return paths
        return []

    def _resolve_sample_paths(self, *, document_preset_id: str, sample_path: str, user_task: str = "") -> list[Path]:
        if sample_path:
            return [self._resolve_sample_path_reference(sample_path)]
        document_preset_id = self._infer_document_preset_id(user_task, document_preset_id)
        return self._preset_paths_for_id(document_preset_id)

    def _build_document_preflight_prompt(
        self,
        *,
        user_task: str,
        conversation: list[dict[str, str]],
        sample_excerpt: str,
        source_job_context: str = "",
    ) -> str:
        transcript = "\n".join(
            f"- {row['role']}: {row['text']}" for row in conversation[-8:] if row.get("text")
        ) or "- (없음)"
        sample_block = sample_excerpt.strip() or "(예시 문서 없음)"
        source_block = source_job_context.strip() or "(이전 분석 산출물 없음)"
        user_turn_count = sum(1 for row in conversation if str(row.get("role") or "").strip() == "user")
        return (
            "다음 정보를 바탕으로 문서 초안 작성 preflight를 수행하라.\n"
            "규칙:\n"
            "- JSON만 출력한다.\n"
            "- 더 필요한 사실이 있으면 questions에 짧고 구체적인 질문만 넣고 ready=false로 둔다.\n"
            "- 충분하면 ready=true, retrieval_task에는 판례 검색용 한 문단 메시지를 만든다.\n"
            "- drafting_goal에는 사용자에게 보여줄 문서 작성 목표를 한 문단으로 적는다.\n"
            "- summary에는 현재 판단을 1~2문장으로 적는다.\n"
            "- 과도한 스키마를 만들지 말라.\n"
            "- 다음 경우에는 반드시 ready=true, questions=[]로 둬라:\n"
            "  · 사용자가 질문 그만두길 바라는 뉘앙스 (\"그냥 써\", \"이제 충분\", \"모르겠다\", "
            "\"대충 해줘\", \"바로 작성\", \"더 물어보지 마\", \"아는 것만으로\" 등)\n"
            f"  · 이미 사용자가 2회 이상 답변했다 (지금 user_turn_count={user_turn_count})\n"
            "  · 사용자가 이미 필요 최소 사실을 줬고 더 물으면 대화가 비효율적으로 길어질 것으로 판단\n\n"
            f"[현재 요청]\n{user_task}\n\n"
            f"[지금까지 대화]\n{transcript}\n\n"
            f"[이전 질문 분석 산출물]\n{source_block}\n\n"
            f"[예시 문서 발췌]\n{sample_block}\n\n"
            '출력 JSON:\n{"ready": true, "questions": [], "retrieval_task": "...", "drafting_goal": "...", "summary": "..."}'
        )

    def _build_source_job_context(self, job_id: str) -> str:
        job = self._require_job(job_id)
        payload = build_result_payload(job.run_dir, variant_name=QUESTION_VARIANT_NAME, job_id=job.job_id, mode=job.mode, analysis_mode=job.analysis_mode)
        parts: list[str] = []
        answer = str(payload.get("answerMarkdown") or "").strip()
        if answer:
            parts.append("[이전 최종 답변]\n" + answer[:10_000])
        answer_plan = payload.get("answerPlan") or {}
        if answer_plan:
            parts.append("[이전 답변 설계]\n" + json.dumps(answer_plan, ensure_ascii=False, indent=2)[:8_000])
        claims = payload.get("selectedClaims") or payload.get("claims") or []
        if claims:
            parts.append("[이전 선택 주장]\n" + json.dumps(claims[:30], ensure_ascii=False, indent=2)[:18_000])
        precedents = payload.get("selectedPrecedents") or []
        compact_precedents = []
        for row in precedents[:30]:
            if not isinstance(row, dict):
                continue
            compact_precedents.append(
                {
                    "caseNumber": row.get("caseNumber"),
                    "citation": row.get("citation"),
                    "title": row.get("title"),
                    "excerpt": row.get("excerpt"),
                }
            )
        if compact_precedents:
            parts.append("[이전 참고 판례]\n" + json.dumps(compact_precedents, ensure_ascii=False, indent=2)[:18_000])
        return "\n\n".join(parts).strip()

    def _extract_document_preflight(self, raw: str) -> dict[str, Any]:
        try:
            obj = json.loads(rag._extract_json_block(raw))
        except Exception:
            obj = {}
        questions = []
        for item in obj.get("questions") or []:
            text = str(item or "").strip()
            if text and text not in questions:
                questions.append(text)
        return {
            "ready": bool(obj.get("ready")) and not questions,
            "questions": questions[:3],
            "retrievalTask": str(obj.get("retrieval_task") or "").strip(),
            "draftingGoal": str(obj.get("drafting_goal") or "").strip(),
            "summary": str(obj.get("summary") or "").strip(),
        }

    def _fallback_document_questions(self, user_task: str, conversation: list[dict[str, str]]) -> list[str]:
        merged = " ".join(row.get("text") or "" for row in conversation[-6:]).strip()
        base = f"{user_task} {merged}".strip()
        questions: list[str] = []
        if len(base) < 80:
            questions.append("문서에서 가장 핵심적으로 주장하거나 요구할 결론을 한 문장으로 적어주세요.")
        if not re.search(r"(언제|일시|날짜|시각|\d{4}\.\s*\d{1,2}\.\s*\d{1,2})", base):
            questions.append("문제된 행위나 처분이 언제 있었는지 알 수 있는 날짜·시각을 적어주세요.")
        if not re.search(r"(누가|상대방|처분권자|피해자|학생|회사|학교|경찰|검찰|법원)", base):
            questions.append("문서의 당사자와 상대방이 누구인지, 관계가 무엇인지 적어주세요.")
        return questions[:3]

    def _complaint_missing_fact_questions(
        self,
        *,
        user_task: str,
        conversation: list[dict[str, str]],
        document_preset_id: str,
    ) -> list[str]:
        if self._infer_document_preset_id(user_task, document_preset_id) != "complaint":
            return []
        user_text = " ".join(row.get("text") or "" for row in conversation if row.get("role") == "user")
        base = f"{user_task} {user_text}".strip()
        if not base:
            return []
        questions: list[str] = []
        has_time = bool(
            re.search(
                r"\d{4}\s*[.\-/년]\s*\d{1,2}\s*[.\-/월]\s*\d{1,2}|오늘|어제|그제|지난\s*\d+일|오전|오후|시경|시\s*\d*분",
                base,
            )
        )
        has_accused = bool(re.search(r"피고소인|가해자|상대방|고소\s*대상|회사\s*동료|동료|지인|[A-Z]\s*(?:가|는|를|에게)", base))
        has_conduct = bool(
            re.search(r"['\"“‘][^'\"”’]{2,}['\"”’]|라고\s*(?:말|했|전송|게시)|말했|발언|욕설|메시지|사기꾼|쓰레기", base)
        )
        if not has_time:
            questions.append("사건이 발생한 날짜와 대략적인 시각을 알려주세요.")
        if not has_accused:
            questions.append("피고소인(상대방)을 어떻게 표시할지, 알고 있는 인적사항이나 관계를 알려주세요.")
        if not has_conduct:
            questions.append("피고소인이 어떤 말이나 행동을 했는지, 문제된 표현을 가능한 한 그대로 알려주세요.")
        return questions[:3]

    def _build_document_goal_text(self, user_task: str, conversation: list[dict[str, str]]) -> str:
        merged = _user_context_excluding_primary(conversation, user_task)
        if merged:
            return f"{user_task.strip()} / 추가 설명: {merged}".strip()
        return user_task.strip()

    def _build_document_retrieval_task(self, drafting_goal: str, conversation: list[dict[str, str]]) -> str:
        merged = _user_context_excluding_primary(conversation, drafting_goal)
        if merged and merged not in drafting_goal:
            return f"{drafting_goal}\n추가 사실관계: {merged}"
        return drafting_goal

    def _recover_job(self, job_id: str) -> JobRecord | None:
        run_dir = self._runs_root / job_id
        status_path = run_dir / "_runtime" / "status.json"
        selected_manifest_path = run_dir / "selected_precedents.json"
        if not run_dir.exists() or not status_path.exists():
            return None
        runtime_status = json.loads(status_path.read_text(encoding="utf-8"))
        meta = self._read_job_meta(run_dir)
        recovered_mode = str(meta.get("mode") or "question")
        if (
            runtime_status.get("state") in FINAL_ARTIFACT_COMPLETED_STATES
            and self._candidate_final_artifact_path(run_dir, runtime_status, mode=recovered_mode) is not None
        ):
            final_path = self._candidate_final_artifact_path(run_dir, runtime_status, mode=recovered_mode)
            finished_at = time.time()
            if final_path is not None:
                try:
                    finished_at = final_path.stat().st_mtime
                except OSError:
                    pass
            runtime_status.update(
                {
                    "phase": "done",
                    "state": "completed",
                    "error": "",
                    "finished_at": finished_at,
                }
            )
            status_path.write_text(json.dumps(runtime_status, ensure_ascii=False, indent=2), encoding="utf-8")
        elif runtime_status.get("state") not in TERMINAL_JOB_STATES and not runtime_status.get("finished_at"):
            # Server restart while job was in flight. Re-queue silently;
            # the worker thread will pick up from existing artifacts.
            runtime_status.update(
                {
                    "phase": "startup",
                    "state": "queued",
                    "error": "",
                    "finished_at": None,
                }
            )
            status_path.write_text(json.dumps(runtime_status, ensure_ascii=False, indent=2), encoding="utf-8")
        chunk_plan: list[dict[str, Any]] = []
        selected_count = 0
        if selected_manifest_path.exists():
            try:
                records = rag.load_selected_question_records(selected_manifest_path)
                selected_count = len(records)
                preview_chunks = rag.build_question_chunks_for_records(  # type: ignore[attr-defined]
                    records,
                    max_tokens=max(4000, rag.DEFAULT_QUESTION_CHUNK_TOKENS),  # type: ignore[attr-defined]
                    workers=1,
                )
                chunk_plan = []
                for chunk in preview_chunks:
                    first_segment = chunk.source_segments[0] if getattr(chunk, "source_segments", None) else {}
                    excerpt = str(first_segment.get("excerpt") or " ".join(chunk.text.split())[:220])
                    chunk_plan.append(
                        {
                            "chunk_id": chunk.chunk_id,
                            "file_id": chunk.file_id,
                            "case_number": str(first_segment.get("case_number") or chunk.case_number or ""),
                            "excerpt": _headline_excerpt_from_text(excerpt) or excerpt,
                        }
                    )
            except Exception:
                chunk_plan = []
                selected_count = 0
        created_at = float(meta.get("created_at") or run_dir.stat().st_mtime)
        return JobRecord(
            job_id=job_id,
            mode=str(meta.get("mode") or "question"),
            user_task=str(meta.get("user_task") or ""),
            run_dir=run_dir,
            created_at=created_at,
            status_path=status_path,
            selected_manifest_path=selected_manifest_path,
            chunk_plan=chunk_plan,
            selected_count=selected_count,
            finished_at=float(runtime_status.get("finished_at")) if runtime_status.get("finished_at") else None,
            error=str(runtime_status.get("error") or ""),
            document_preset_id=str(meta.get("document_preset_id") or ""),
            document_context=str(meta.get("document_context") or ""),
            sample_path=str(meta.get("sample_path") or ""),
            runtime_control_path=run_dir / "_runtime" / "control.json",
            client_id=str(meta.get("client_id") or ""),
            analysis_mode=(lambda v: v if v in {"fast","beta1","beta2","beta3","beta4","beta5","beta6","beta7","beta8"} else "precise")(
                str(meta.get("analysis_mode") or "precise").lower()
            ),
        )

    def _write_status(self, job: JobRecord, payload: dict[str, Any]) -> None:
        job.status_path.parent.mkdir(parents=True, exist_ok=True)
        merged = dict(payload)
        if "keywords" not in merged and job.status_path.exists():
            try:
                prior = json.loads(job.status_path.read_text(encoding="utf-8"))
            except Exception:
                prior = {}
            if isinstance(prior, dict) and prior.get("keywords"):
                merged["keywords"] = prior["keywords"]
        job.status_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_cancel_control(self, job: JobRecord, reason: str) -> None:
        if job.runtime_control_path is None:
            return
        control: dict[str, Any] = {}
        if job.runtime_control_path.exists():
            try:
                control = json.loads(job.runtime_control_path.read_text(encoding="utf-8"))
            except Exception:
                control = {}
        control.update({"cancel_requested": True, "cancel_reason": reason})
        job.runtime_control_path.parent.mkdir(parents=True, exist_ok=True)
        job.runtime_control_path.write_text(json.dumps(control, ensure_ascii=False, indent=2), encoding="utf-8")

    def _terminate_job_process(self, job: JobRecord) -> bool:
        pid = job.process_pid
        if not pid:
            return False
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            return True
        except ProcessLookupError:
            return False
        except Exception:
            try:
                os.kill(pid, signal.SIGTERM)
                return True
            except ProcessLookupError:
                return False
            except Exception:
                return False

    def _read_status(self, job: JobRecord) -> dict[str, Any]:
        if not job.status_path.exists():
            status: dict[str, Any] = {}
        else:
            status = json.loads(job.status_path.read_text(encoding="utf-8"))
        if "keywords" not in status or not status.get("keywords"):
            meta_path = job.run_dir / "selection_meta.json"
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    if isinstance(meta, dict) and meta.get("keywords"):
                        status["keywords"] = meta["keywords"]
                except Exception:
                    pass
        return status

    def _job_meta_path(self, job: JobRecord | Path) -> Path:
        run_dir = job.run_dir if isinstance(job, JobRecord) else job
        return run_dir / "_runtime" / "job_meta.json"

    def _write_job_meta(self, job: JobRecord) -> None:
        meta_path = self._job_meta_path(job)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "job_id": job.job_id,
            "mode": job.mode,
            "user_task": job.user_task,
            "created_at": job.created_at,
            "document_preset_id": job.document_preset_id,
            "document_context": job.document_context,
            "sample_path": job.sample_path,
            "client_id": job.client_id,
            "analysis_mode": job.analysis_mode,
        }
        meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_job_meta(self, run_dir: Path) -> dict[str, Any]:
        meta_path = self._job_meta_path(run_dir)
        if not meta_path.exists():
            return {}
        return json.loads(meta_path.read_text(encoding="utf-8"))

    def _resolve_sample_texts(self, job: JobRecord) -> list[str]:
        sample_paths = self._resolve_sample_paths(
            document_preset_id=job.document_preset_id,
            sample_path=job.sample_path,
            user_task=f"{job.user_task}\n{job.document_context}",
        )
        cache_dir = job.run_dir / "_runtime" / "sample_cache"
        return rag._read_sample_texts(sample_paths, cache_dir)  # type: ignore[attr-defined]

    def _build_document_writer_task(self, job: JobRecord) -> str:
        base = job.user_task.strip()
        context = job.document_context.strip()
        if context:
            return f"{base}\n\n{context}".strip()
        return base

    def _run_job(self, job: JobRecord) -> None:
        acquired_immediately = self._execution_slot.acquire(blocking=False)
        if not acquired_immediately:
            self._write_status(
                job,
                {
                    "phase": "queue",
                    "state": "waiting_for_capacity",
                    "selected_file_count": job.selected_count,
                },
            )
            self._execution_slot.acquire()
        try:
            if job.cancel_requested:
                job.finished_at = time.time()
                job.error = job.cancel_reason or "cancelled"
                self._write_status(
                    job,
                    {
                        "phase": "done",
                        "state": "cancelled",
                        "selected_file_count": job.selected_count,
                        "completed_chunks": 0,
                        "chunk_count": len(job.chunk_plan),
                        "elapsed_seconds": int(job.finished_at - job.created_at),
                        "error": job.error,
                        "finished_at": job.finished_at,
                    },
                )
                return
            self._bind_runtime(job)
            last_error = ""
            attempt = 0
            while True:
                if job.cancel_requested:
                    job.finished_at = time.time()
                    job.error = job.cancel_reason or "cancelled"
                    self._write_status(
                        job,
                        {
                            "phase": "done",
                            "state": "cancelled",
                            "selected_file_count": job.selected_count,
                            "completed_chunks": 0,
                            "chunk_count": len(job.chunk_plan),
                            "elapsed_seconds": int(job.finished_at - job.created_at),
                            "error": job.error,
                            "finished_at": job.finished_at,
                        },
                    )
                    return
                attempt += 1
                try:
                    self._ensure_selected_records(job)
                    self._raise_if_cancelled(job)
                    self._ensure_chunk_plan(job)
                    self._raise_if_cancelled(job)
                    self._run_question_subprocess(job)
                    self._raise_if_cancelled(job)
                    if job.mode == "document":
                        self._write_document_output(job)
                        self._raise_if_cancelled(job)
                        self._write_export_outputs(job)
                    job.finished_at = time.time()
                    job.error = ""
                    self._write_status(
                        job,
                        {
                            "phase": "done",
                            "state": "completed",
                            "selected_file_count": job.selected_count,
                            "completed_chunks": len(job.chunk_plan),
                            "chunk_count": len(job.chunk_plan),
                            "elapsed_seconds": int(job.finished_at - job.created_at),
                            "finished_at": job.finished_at,
                            "attempt_count": attempt,
                        },
                    )
                    return
                except Exception as exc:  # noqa: BLE001
                    if job.cancel_requested:
                        job.finished_at = time.time()
                        job.error = job.cancel_reason or "cancelled"
                        self._write_status(
                            job,
                            {
                                "phase": "done",
                                "state": "cancelled",
                                "selected_file_count": job.selected_count,
                                "completed_chunks": 0,
                                "chunk_count": len(job.chunk_plan),
                                "elapsed_seconds": int(job.finished_at - job.created_at),
                                "error": job.error,
                                "finished_at": job.finished_at,
                            },
                        )
                        return
                    last_error = str(exc)
                    if not self._is_retryable_job_error(exc):
                        raise
                    backoff_seconds = self._retry_backoff_seconds(attempt)
                    self._write_status(
                        job,
                        {
                            "phase": "retry",
                            "state": "retrying_after_transient_error",
                            "selected_file_count": job.selected_count,
                            "completed_chunks": 0,
                            "chunk_count": len(job.chunk_plan),
                            "attempt_count": attempt,
                            "max_attempts": None if DEFAULT_JOB_MAX_ATTEMPTS == 0 else DEFAULT_JOB_MAX_ATTEMPTS,
                            "retry_backoff_seconds": backoff_seconds,
                            "error": last_error,
                        },
                    )
                    time.sleep(backoff_seconds)
        except Exception as exc:  # noqa: BLE001
            job.finished_at = time.time()
            job.error = str(exc)
            self._write_status(
                job,
                {
                    "phase": "done",
                    "state": "failed",
                    "selected_file_count": job.selected_count,
                    "completed_chunks": 0,
                    "chunk_count": len(job.chunk_plan),
                    "elapsed_seconds": int(job.finished_at - job.created_at),
                    "error": job.error,
                    "finished_at": job.finished_at,
                },
            )
        finally:
            self._execution_slot.release()

    def _ensure_selected_records(self, job: JobRecord) -> None:
        if job.selected_manifest_path.exists():
            try:
                selected_records = json.loads(job.selected_manifest_path.read_text(encoding="utf-8"))
            except Exception:
                selected_records = []
            job.selected_count = len(selected_records)
            return
        self._write_status(job, {"phase": "selection", "state": "generating_keywords", "selected_file_count": 0})
        is_fast = job.analysis_mode == "fast"
        is_beta2 = job.analysis_mode == "beta2"
        is_beta3 = job.analysis_mode == "beta3"
        is_beta4 = job.analysis_mode == "beta4"
        is_beta5 = job.analysis_mode == "beta5"
        is_beta6 = job.analysis_mode == "beta6"
        is_beta7 = job.analysis_mode == "beta7"
        is_beta8 = job.analysis_mode == "beta8"
        is_beta1_legacy = job.analysis_mode == "beta1"  # 과거 작업 재진입용
        if is_beta7:
            # Beta-7 = Beta-4 selector base + (1) thinkingLevel="high" on
            # seed keyword generation so the LLM disambiguates homonyms
            # like "키" (height vs 열쇠) at the keyword stage itself and
            # (2) cumulative-token early-stop at 400k so the chunk packer
            # never needs to randomly drop candidates. No hardcoded
            # `_effective_question_user_task` rewrite — disambiguation
            # falls out of better seed keywords + token-bounded selection.
            from .search import select_top_precedents_beta7
            selected_records, selection_meta = select_top_precedents_beta7(
                job.user_task,
                select_model=DEFAULT_SELECT_MODEL,
            )
        elif is_beta6:
            from .search import select_top_precedents_beta6
            selected_records, selection_meta = select_top_precedents_beta6(
                job.user_task,
                select_model=DEFAULT_SELECT_MODEL,
            )
        elif is_beta8:
            from .search import select_top_precedents_beta6
            selected_records, selection_meta = select_top_precedents_beta6(
                job.user_task,
                select_model=DEFAULT_SELECT_MODEL,
            )
            selection_meta = {
                **selection_meta,
                "selection_mode": "beta8_legal_proposition_guard",
                "base_selection_mode": selection_meta.get("selection_mode") or "",
            }
        elif is_beta5:
            from .search import select_top_precedents_beta5
            selected_records, selection_meta = select_top_precedents_beta5(
                job.user_task,
                select_model=DEFAULT_SELECT_MODEL,
            )
        elif is_beta4:
            from .search import select_top_precedents_beta4
            selected_records, selection_meta = select_top_precedents_beta4(
                job.user_task,
                select_model=DEFAULT_SELECT_MODEL,
            )
        elif is_beta3:
            from .search import select_top_precedents_beta3
            selected_records, selection_meta = select_top_precedents_beta3(
                job.user_task,
                select_model=DEFAULT_SELECT_MODEL,
            )
        elif is_beta2:
            from .search import select_top_precedents_beta2
            selected_records, selection_meta = select_top_precedents_beta2(
                job.user_task,
                select_model=DEFAULT_SELECT_MODEL,
            )
        elif is_beta1_legacy:
            from .search import select_top_precedents_beta1
            selected_records, selection_meta = select_top_precedents_beta1(
                job.user_task,
                select_model=DEFAULT_SELECT_MODEL,
            )
        else:
            effective_top_k = 30 if is_fast else DEFAULT_TOP_K
            selected_records, selection_meta = select_top_precedents(
                job.user_task,
                top_k=effective_top_k,
                select_model=DEFAULT_SELECT_MODEL,
            )
        effective_user_task = _effective_question_user_task(
            job.user_task,
            analysis_mode=job.analysis_mode,
            selection_meta=selection_meta,
        )
        selection_meta = {
            **selection_meta,
            "original_user_task": job.user_task,
        }
        if effective_user_task != job.user_task:
            selection_meta = {
                **selection_meta,
                "downstream_user_task": effective_user_task,
            }
        self._raise_if_cancelled(job)
        if is_fast:
            selected_records = self._apply_keyword_windows(
                selected_records, selection_meta.get("keywords") or []
            )
        job.selected_count = len(selected_records)
        job.selected_manifest_path.write_text(json.dumps(selected_records, ensure_ascii=False, indent=2), encoding="utf-8")
        (job.run_dir / "selection_meta.json").write_text(
            json.dumps(selection_meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self._write_status(
            job,
            {
                "phase": "selection",
                "state": "building_chunk_plan",
                "selected_file_count": len(selected_records),
                "keywords": selection_meta.get("keywords") or [],
            },
        )

    def _ensure_chunk_plan(self, job: JobRecord) -> None:
        if job.chunk_plan:
            return
        rag_records = rag.load_selected_question_records(job.selected_manifest_path)
        chunk_tokens = self._question_chunk_tokens(job.analysis_mode)
        preview_chunks = rag.build_question_chunks_for_records(  # type: ignore[attr-defined]
            rag_records,
            max_tokens=chunk_tokens,
            workers=1,
        )
        job.chunk_plan = []
        for chunk in preview_chunks:
            first_segment = chunk.source_segments[0] if getattr(chunk, "source_segments", None) else {}
            excerpt = str(first_segment.get("excerpt") or " ".join(chunk.text.split())[:220])
            job.chunk_plan.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "file_id": chunk.file_id,
                    "case_number": str(first_segment.get("case_number") or chunk.case_number or ""),
                    "excerpt": _headline_excerpt_from_text(excerpt) or excerpt,
                }
            )

    def _question_chunk_tokens(self, analysis_mode: str) -> int:
        if analysis_mode == "fast":
            return 10_000
        if analysis_mode in {"beta6", "beta7", "beta8"}:
            return 100_000
        return max(4_000, rag.DEFAULT_QUESTION_CHUNK_TOKENS)  # type: ignore[attr-defined]

    def _apply_keyword_windows(
        self,
        records: list[dict[str, Any]],
        keywords: list[str],
        *,
        pad_chars: int = 400,
        max_windows_per_record: int = 8,
        max_chars_per_record: int = 6000,
    ) -> list[dict[str, Any]]:
        """Replace `extracted_text` of each selected record with the
        concatenated keyword windows (±pad_chars around each hit). Fast mode.
        """
        cleaned_keywords = [str(k).strip() for k in (keywords or []) if str(k).strip()]
        cleaned_keywords = [k for k in cleaned_keywords if len(k) >= 2]
        if not cleaned_keywords:
            return records
        out: list[dict[str, Any]] = []
        for record in records:
            text = str(record.get("extracted_text") or record.get("full_text") or "")
            if not text:
                out.append(record)
                continue
            windows: list[tuple[int, int]] = []
            lowered = text
            for kw in cleaned_keywords:
                start = 0
                while len(windows) < max_windows_per_record * 4:
                    idx = lowered.find(kw, start)
                    if idx < 0:
                        break
                    lo = max(0, idx - pad_chars)
                    hi = min(len(text), idx + len(kw) + pad_chars)
                    windows.append((lo, hi))
                    start = hi
            if not windows:
                # Fallback: keep the first chunk of the doc so we don't drop it entirely.
                out.append({**record, "extracted_text": text[:max_chars_per_record]})
                continue
            # Merge overlapping windows
            windows.sort()
            merged: list[list[int]] = []
            for lo, hi in windows:
                if merged and lo <= merged[-1][1]:
                    merged[-1][1] = max(merged[-1][1], hi)
                else:
                    merged.append([lo, hi])
                if len(merged) >= max_windows_per_record:
                    break
            assembled = "\n\n…\n\n".join(text[lo:hi] for lo, hi in merged)
            if len(assembled) > max_chars_per_record:
                assembled = assembled[:max_chars_per_record]
            out.append({**record, "extracted_text": assembled})
        return out

    def _retry_backoff_seconds(self, attempt: int) -> int:
        index = max(0, min(attempt - 1, len(DEFAULT_RETRY_BACKOFF_SECONDS) - 1))
        return int(DEFAULT_RETRY_BACKOFF_SECONDS[index])

    def _is_retryable_job_error(self, exc: Exception) -> bool:
        text = str(exc).lower()
        transient_markers = [
            "429",
            "rate limit",
            "timed out",
            "timeout",
            "connection aborted",
            "connection reset",
            "temporarily unavailable",
            "service unavailable",
            "internal server error",
            "bad gateway",
            "question subprocess failed with exit code",
        ]
        return any(marker in text for marker in transient_markers)

    def _raise_if_cancelled(self, job: JobRecord) -> None:
        if job.cancel_requested:
            raise RuntimeError(job.cancel_reason or "cancelled")

    def _run_question_subprocess(self, job: JobRecord) -> None:
        try:
            selection_meta = json.loads((job.run_dir / "selection_meta.json").read_text(encoding="utf-8"))
        except Exception:
            selection_meta = {}
        effective_user_task = _effective_question_user_task(
            job.user_task,
            analysis_mode=job.analysis_mode,
            selection_meta=selection_meta,
        )
        command = [
            sys.executable,
            str(LEGAL_RAG_SCRIPT),
            "--question-mode",
            "--selected-precedent-json",
            str(job.selected_manifest_path),
            "--user-task",
            effective_user_task,
            "--out-dir",
            str(job.run_dir),
            "--analyze-model",
            DEFAULT_ANALYZE_MODEL,
            "--draft-model",
            DEFAULT_DRAFT_MODEL,
            "--analyze-workers",
            str(DEFAULT_WORKER_COUNT),
            "--chunk-build-workers",
            str(DEFAULT_WORKER_COUNT),
            "--gemini-key-min-gap-ms",
            str(DEFAULT_KEY_MIN_GAP_MS),
            "--gemini-key-max-inflight",
            str(DEFAULT_KEY_MAX_INFLIGHT),
            "--gemini-key-rpm-limit",
            str(DEFAULT_KEY_RPM_LIMIT),
            "--gemini-key-tpm-limit",
            str(DEFAULT_KEY_TPM_LIMIT),
            "--gemini-global-max-inflight",
            str(DEFAULT_GLOBAL_MAX_INFLIGHT),
        ]
        if job.analysis_mode in {"fast", "beta6", "beta8"}:
            command.append("--skip-coverage-patch")
        # Pass through the analysis-mode tag so the legal_evidence_rag final
        # answer prompt can switch into the dual-layer (laypeople + jurist)
        # format for beta-4/5/6 while keeping the rest of the pipeline
        # unchanged.
        if job.analysis_mode:
            command.extend(["--analysis-mode", job.analysis_mode])
            if job.analysis_mode in {"beta6", "beta7", "beta8"}:
                # Larger chunks preserve the selected record set while cutting
                # the analyze_chunks_cached LLM call count, the dominant cost.
                command.extend(["--question-chunk-tokens", str(self._question_chunk_tokens(job.analysis_mode))])
        log_path = job.run_dir / "_runtime" / "process.log"
        with log_path.open("w", encoding="utf-8") as log_fp:
            process = subprocess.Popen(
                command,
                stdout=log_fp,
                stderr=subprocess.STDOUT,
                cwd=str(WORKSPACE_SCRIPTS.parent),
                start_new_session=True,
            )
            job.process_pid = process.pid
            return_code = process.wait()
        job.process_pid = None
        if return_code != 0 and job.cancel_requested:
            raise RuntimeError(job.cancel_reason or "cancelled")
        if return_code != 0:
            tail = ""
            if log_path.exists():
                try:
                    tail = log_path.read_text(encoding="utf-8", errors="ignore")[-2000:]
                except Exception:
                    tail = ""
            detail = f"question subprocess failed with exit code {return_code}"
            if tail.strip():
                detail += f"; tail={tail.strip()}"
            raise RuntimeError(detail)

    def _write_document_output(self, job: JobRecord) -> None:
        variant_dir = job.run_dir / QUESTION_VARIANT_NAME
        claim_path = variant_dir / "claim_ledger.json"
        if not claim_path.exists():
            raise FileNotFoundError(f"missing claim ledger: {claim_path}")
        claims = json.loads(claim_path.read_text(encoding="utf-8"))
        sample_texts = self._resolve_sample_texts(job)
        self._write_status(
            job,
            {
                "phase": "variant",
                "state": "writing_document",
                "selected_file_count": job.selected_count,
                "completed_chunks": len(job.chunk_plan),
                "chunk_count": len(job.chunk_plan),
            },
        )
        section_packets = rag.synthesize_section_packets(
            claims,
            model=DEFAULT_ANALYZE_MODEL,
            max_tokens=rag.DEFAULT_MAX_REQUEST_TOKENS,  # type: ignore[attr-defined]
        )
        final_document = rag.write_final_opinion(
            user_task=self._build_document_writer_task(job),
            sample_texts=sample_texts,
            claims=claims,
            section_packets=section_packets,
            model=DEFAULT_DRAFT_MODEL,
        )
        final_document = strip_document_meta_leak(rag.sanitize_document_output(final_document))
        (variant_dir / "final_document.md").write_text(final_document, encoding="utf-8")

    def _prepare_runtime_files(self, job: JobRecord) -> None:
        if job.runtime_control_path is None:
            return
        job.runtime_control_path.parent.mkdir(parents=True, exist_ok=True)
        job.runtime_control_path.write_text(
            json.dumps(
                {
                    "gemini_key_min_gap_ms": DEFAULT_KEY_MIN_GAP_MS,
                    "gemini_key_max_inflight": DEFAULT_KEY_MAX_INFLIGHT,
                    "gemini_key_rpm_limit": DEFAULT_KEY_RPM_LIMIT,
                    "gemini_key_tpm_limit": DEFAULT_KEY_TPM_LIMIT,
                    "gemini_global_max_inflight": DEFAULT_GLOBAL_MAX_INFLIGHT,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _bind_runtime(self, job: JobRecord) -> None:
        if job.runtime_control_path is not None:
            rag.set_runtime_control_file(job.runtime_control_path)
        rag.set_runtime_status_file(job.status_path)

    def _write_export_outputs(self, job: JobRecord) -> None:
        if job.mode != "document":
            return
        variant_dir = job.run_dir / QUESTION_VARIANT_NAME
        markdown_path = variant_dir / ("final_document.md" if job.mode == "document" else "final_answer.md")
        if not markdown_path.exists():
            markdown_path = variant_dir / "final_answer_v2.md"
        if not markdown_path.exists():
            return
        title = markdown_path.stem.replace("_", " ").strip() or "Lawkey AI 결과"
        markdown_text = markdown_path.read_text(encoding="utf-8")
        if job.mode == "document":
            sanitized_markdown = strip_document_meta_leak(rag.sanitize_document_output(markdown_text))
            if sanitized_markdown != markdown_text:
                markdown_path.write_text(sanitized_markdown, encoding="utf-8")
            markdown_text = sanitized_markdown
        export_payload = build_export_artifacts(
            markdown_text,
            variant_dir=variant_dir,
            title=title,
            mode=job.mode,
            stem="final_document" if job.mode == "document" else "final_answer",
        )
        self._write_status(
            job,
            {
                "phase": "variant",
                "state": "exporting_artifacts",
                "selected_file_count": job.selected_count,
                "completed_chunks": len(job.chunk_plan),
                "chunk_count": len(job.chunk_plan),
                "export_ready": bool(export_payload.get("pdf_path") or export_payload.get("hwpx_path")),
            },
        )
