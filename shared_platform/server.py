from __future__ import annotations

import json
import os
import threading
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic, sleep
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .beta6 import Beta6JobManager, Beta6QueueFullError
from .gemini_chat import GEMMA4_26B_MODEL, GeminiChatMessage, GeminiDirectChatClient, gemini_api_key_from_env
from .products import PRODUCT_PROFILES, ProductProfile
from .search import SearchResult, get_source_by_id, search_documents

CANONICAL_MERIAN_PAGE_ALIASES = {
    "islam": ("islam", "islam-merian-chat.html"),
    "buddhist": ("buddhist", "buddhist-merian-chat.html"),
    "christian": ("catholic", "catholic-merian-chat.html"),
    "catholic": ("catholic", "catholic-merian-chat.html"),
    "hindu": ("hindu", "hindu-merian-chat.html"),
    "tcm": ("tcm", "tcm-merian-chat.html"),
}


class AnswerRequest(BaseModel):
    query: str
    language: str = ""
    limit: int = 8
    analysisMode: str = ""
    fastMode: bool = False


class GemmaChatMessageRequest(BaseModel):
    role: str
    text: str


class GemmaChatRequest(BaseModel):
    messages: list[GemmaChatMessageRequest]
    systemInstruction: str = ""
    model: str = GEMMA4_26B_MODEL
    temperature: float = 0.6
    maxOutputTokens: int = 1024


def create_app(
    profiles: dict[str, ProductProfile] | None = None,
    *,
    web_dir: Path | None = None,
    default_page: str = "index.html",
    exposed_pages: set[str] | frozenset[str] | None = None,
    allowed_origins: list[str] | None = None,
    rate_limit_per_minute: int | None = None,
    runtime: Beta6JobManager | None = None,
) -> FastAPI:
    active_profiles = profiles or PRODUCT_PROFILES
    beta6_runtime = runtime or Beta6JobManager(active_profiles, defer_resume_pending_jobs=True)
    title = _app_title(active_profiles, default_page=default_page, exposed_pages=exposed_pages)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        beta6_runtime.resume_pending_jobs()
        embedded_worker = _start_embedded_queue_worker_if_enabled(beta6_runtime, active_profiles)
        try:
            yield
        finally:
            if embedded_worker is not None:
                embedded_worker.stop()
            beta6_runtime.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(title=title, lifespan=lifespan)
    app.state.beta6_runtime = beta6_runtime
    origins = _allowed_origins(allowed_origins)
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=[
                "Content-Type",
                "Authorization",
                "X-Beta6-Job-Token",
                "X-Beta6-Session-Token",
                "X-Beta6-Account-Subject",
            ],
        )
    _install_rate_limit(app, rate_limit_per_minute)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/products")
    def products() -> dict[str, Any]:
        return {
            "products": [
                {
                    "key": profile.key,
                    "name": profile.name,
                    "languages": list(profile.languages),
                    "defaultLanguage": profile.default_language,
                    "theme": profile.theme,
                    "safetyNotice": profile.safety_notice,
                }
                for profile in active_profiles.values()
            ]
        }

    @app.post("/api/gemma/chat")
    def gemma_chat(payload: GemmaChatRequest) -> dict[str, Any]:
        api_key = gemini_api_key_from_env()
        if not api_key:
            raise HTTPException(status_code=503, detail="Gemini API key is not configured")
        try:
            client = GeminiDirectChatClient(
                api_key=api_key,
                timeout_seconds=float(os.getenv("RELIGION_GEMMA_CHAT_TIMEOUT_SECONDS", "120")),
            )
            return client.generate(
                [GeminiChatMessage(role=message.role, text=message.text) for message in payload.messages],
                system_instruction=payload.systemInstruction,
                model=payload.model,
                temperature=payload.temperature,
                max_output_tokens=payload.maxOutputTokens,
                thinking_level=os.getenv("RELIGION_GEMMA_CHAT_THINKING_LEVEL", "").strip(),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    def require_profile(product: str) -> ProductProfile:
        key = str(product or "").strip().lower()
        profile = active_profiles.get(key)
        if profile is None:
            raise HTTPException(status_code=404, detail="unknown product")
        if not profile.db_path.exists():
            raise HTTPException(status_code=503, detail="corpus database unavailable")
        return profile

    @app.get("/api/{product}/search")
    def search(product: str, q: str, limit: int = 8, language: str = "") -> dict[str, Any]:
        if not q.strip():
            raise HTTPException(status_code=400, detail="q is required")
        profile = require_profile(product)
        resolved_language = _resolve_language(profile, language)
        rows = search_documents(profile, q, limit=limit, language=resolved_language)
        return {
            "product": profile.key,
            "query": q,
            "results": [_result_payload(row) for row in rows],
        }

    @app.post("/api/{product}/answer")
    def answer(product: str, payload: AnswerRequest) -> dict[str, Any]:
        query = payload.query.strip()
        if not query:
            raise HTTPException(status_code=400, detail="query is required")
        profile = require_profile(product)
        language = _resolve_language(profile, payload.language)
        return beta6_runtime.answer_sync(
            product=profile.key,
            query=query,
            language=language,
            limit=payload.limit,
            analysis_mode=_analysis_mode_from_payload(payload),
        )

    @app.get("/api/{product}/source-window")
    def source_window(
        product: str,
        sourceId: str,
        start: int = 0,
        end: int = 0,
        radius: int = 900,
        before: int | None = None,
        after: int | None = None,
    ) -> dict[str, Any]:
        profile = require_profile(product)
        row = get_source_by_id(profile, sourceId)
        if row is None:
            raise HTTPException(status_code=404, detail="source not found")
        return _source_window_payload(profile, row, start=start, end=end, radius=radius, before=before, after=after)

    @app.post("/api/{product}/jobs")
    def create_job(product: str, payload: AnswerRequest, request: Request) -> dict[str, Any]:
        query = payload.query.strip()
        if not query:
            raise HTTPException(status_code=400, detail="query is required")
        profile = require_profile(product)
        language = _resolve_language(profile, payload.language)
        try:
            return beta6_runtime.create_job(
                product=profile.key,
                query=query,
                language=language,
                limit=payload.limit,
                analysis_mode=_analysis_mode_from_payload(payload),
                session_token=_job_session_token(request),
                account_subject=_job_account_subject(request),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Beta6QueueFullError as exc:
            return JSONResponse(
                status_code=503,
                headers={"Retry-After": str(exc.retry_after_seconds)},
                content={
                    "detail": {
                        "code": exc.code,
                        "message": str(exc),
                        "retryAfterSeconds": exc.retry_after_seconds,
                        "capacity": exc.capacity,
                    }
                },
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str, request: Request, token: str = "", session: str = "", account: str = "") -> dict[str, Any]:
        try:
            _require_job_access(
                beta6_runtime,
                job_id,
                _job_access_token(request, token),
                _job_session_token(request, session),
                _job_account_subject(request, account),
            )
            return beta6_runtime.get_status(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc

    @app.get("/api/{product}/jobs/{job_id}")
    def get_product_job(product: str, job_id: str, request: Request, token: str = "", session: str = "", account: str = "") -> dict[str, Any]:
        profile = require_profile(product)
        status = get_job(job_id, request, token=token, session=session, account=account)
        if status.get("product") != profile.key:
            raise HTTPException(status_code=404, detail="job not found")
        return status

    @app.get("/api/jobs/{job_id}/events")
    def get_job_events(
        job_id: str,
        request: Request,
        token: str = "",
        session: str = "",
        account: str = "",
    ) -> StreamingResponse:
        try:
            _require_job_access(
                beta6_runtime,
                job_id,
                _job_access_token(request, token),
                _job_session_token(request, session),
                _job_account_subject(request, account),
            )
            beta6_runtime.get_status(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc
        return StreamingResponse(
            _job_status_event_stream(beta6_runtime, job_id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/{product}/jobs/{job_id}/events")
    def get_product_job_events(
        product: str,
        job_id: str,
        request: Request,
        token: str = "",
        session: str = "",
        account: str = "",
    ) -> StreamingResponse:
        profile = require_profile(product)
        try:
            _require_job_access(
                beta6_runtime,
                job_id,
                _job_access_token(request, token),
                _job_session_token(request, session),
                _job_account_subject(request, account),
            )
            status = beta6_runtime.get_status(job_id)
            if status.get("product") != profile.key:
                raise KeyError("job not found")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc
        return StreamingResponse(
            _job_status_event_stream(beta6_runtime, job_id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str, request: Request, token: str = "", session: str = "", account: str = "") -> dict[str, Any]:
        try:
            _require_job_access(
                beta6_runtime,
                job_id,
                _job_access_token(request, token),
                _job_session_token(request, session),
                _job_account_subject(request, account),
            )
            return beta6_runtime.cancel_job(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc

    @app.post("/api/{product}/jobs/{job_id}/cancel")
    def cancel_product_job(product: str, job_id: str, request: Request, token: str = "", session: str = "", account: str = "") -> dict[str, Any]:
        profile = require_profile(product)
        status = get_job(job_id, request, token=token, session=session, account=account)
        if status.get("product") != profile.key:
            raise HTTPException(status_code=404, detail="job not found")
        return cancel_job(job_id, request, token=token, session=session, account=account)

    @app.get("/api/jobs/{job_id}/result")
    def get_job_result(job_id: str, request: Request, token: str = "", session: str = "", account: str = "") -> dict[str, Any]:
        try:
            _require_job_access(
                beta6_runtime,
                job_id,
                _job_access_token(request, token),
                _job_session_token(request, session),
                _job_account_subject(request, account),
            )
            return beta6_runtime.get_result(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=425, detail=str(exc)) from exc

    @app.get("/api/{product}/jobs/{job_id}/result")
    def get_product_job_result(product: str, job_id: str, request: Request, token: str = "", session: str = "", account: str = "") -> dict[str, Any]:
        profile = require_profile(product)
        status = get_job(job_id, request, token=token, session=session, account=account)
        if status.get("product") != profile.key:
            raise HTTPException(status_code=404, detail="job not found")
        return get_job_result(job_id, request, token=token, session=session, account=account)

    static_dir = web_dir or Path(__file__).resolve().parents[1] / "web"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

        @app.get("/")
        def root() -> FileResponse:
            candidate = static_dir / default_page
            if candidate.exists():
                return FileResponse(candidate)
            return FileResponse(static_dir / "index.html")

        @app.get("/{page_name}.html")
        def product_page(page_name: str) -> FileResponse:
            if exposed_pages is not None and page_name not in exposed_pages:
                raise HTTPException(status_code=404, detail="page not found")
            candidate = static_dir / f"{page_name}.html"
            if candidate.exists():
                return FileResponse(candidate)
            if exposed_pages is not None:
                raise HTTPException(status_code=404, detail="page not found")
            return FileResponse(static_dir / "index.html")

        @app.get("/sw.js")
        def service_worker() -> FileResponse:
            return FileResponse(static_dir / "sw.js", media_type="application/javascript")

        @app.get("/{public_route}")
        def canonical_merian_page(public_route: str) -> FileResponse:
            alias = _canonical_merian_page_alias(public_route, active_profiles, exposed_pages)
            if alias is None:
                raise HTTPException(status_code=404, detail="page not found")
            candidate = static_dir / alias
            if not candidate.exists():
                raise HTTPException(status_code=404, detail="page not found")
            return FileResponse(candidate)

    return app


def _canonical_merian_page_alias(
    public_route: str,
    active_profiles: dict[str, ProductProfile],
    exposed_pages: set[str] | frozenset[str] | None,
) -> str | None:
    route = str(public_route or "").strip().lower()
    product_and_page = CANONICAL_MERIAN_PAGE_ALIASES.get(route)
    if product_and_page is None:
        return None
    product, page = product_and_page
    if product not in active_profiles:
        return None
    if exposed_pages is not None and page.removesuffix(".html") not in exposed_pages:
        return None
    return page


def _allowed_origins(explicit: list[str] | None) -> list[str]:
    if explicit is not None:
        origins = explicit
    else:
        origins = [origin.strip() for origin in os.getenv("RELIGION_ALLOWED_ORIGINS", "").split(",")]
    cleaned = [origin for origin in origins if origin]
    if "*" in cleaned and os.getenv("RELIGION_ALLOW_WILDCARD_CORS") != "1":
        cleaned = [origin for origin in cleaned if origin != "*"]
    return cleaned


def _app_title(
    active_profiles: dict[str, ProductProfile],
    *,
    default_page: str,
    exposed_pages: set[str] | frozenset[str] | None,
) -> str:
    if exposed_pages is not None and len(active_profiles) == 1:
        key = next(iter(active_profiles))
        return f"{key} App"
    if default_page != "index.html" and len(active_profiles) == 1:
        key = next(iter(active_profiles))
        return f"{key} App"
    return "Shared Beta6 Product Platform"


def _install_rate_limit(app: FastAPI, explicit_limit: int | None) -> None:
    if explicit_limit is None:
        try:
            limit = int(os.getenv("RELIGION_RATE_LIMIT_PER_MINUTE", "120"))
        except ValueError:
            limit = 120
    else:
        limit = explicit_limit
    if limit <= 0:
        return

    buckets: dict[str, deque[float]] = defaultdict(deque)
    window_seconds = 60.0

    @app.middleware("http")
    async def rate_limit(request: Request, call_next):
        if not _is_rate_limited_api_path(request.url.path):
            return await call_next(request)
        host = request.client.host if request.client else "unknown"
        now = monotonic()
        bucket = buckets[host]
        while bucket and bucket[0] <= now - window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
        bucket.append(now)
        return await call_next(request)


def _is_rate_limited_api_path(path: str) -> bool:
    if not path.startswith("/api/"):
        return False
    if path == "/api/health" or path.startswith("/api/jobs/"):
        return False
    return True


class _EmbeddedQueueWorkerHandle:
    def __init__(self, runtime: Beta6JobManager, stop_event: threading.Event, thread: threading.Thread) -> None:
        self.runtime = runtime
        self.stop_event = stop_event
        self.thread = thread

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join(timeout=2.0)
        self.runtime.shutdown(wait=False, cancel_futures=True)


def _start_embedded_queue_worker_if_enabled(
    api_runtime: Beta6JobManager,
    active_profiles: dict[str, ProductProfile],
) -> _EmbeddedQueueWorkerHandle | None:
    if not _embedded_queue_worker_enabled(api_runtime):
        return None
    from .queue_worker import Beta6DurableQueueWorker

    worker_runtime = Beta6JobManager(
        dict(active_profiles),
        runs_root=api_runtime._runs_root,
        llm_client=api_runtime._llm_client,
        model=api_runtime._model,
        max_workers=api_runtime._max_workers,
        max_pending_jobs=api_runtime._max_pending_jobs,
        resume_pending_jobs=False,
        local_execution_enabled=True,
    )
    worker = Beta6DurableQueueWorker(
        worker_runtime,
        batch_limit=_queue_worker_batch_limit(),
        poll_interval_seconds=_queue_worker_poll_seconds(),
    )
    stop_event = threading.Event()
    thread = threading.Thread(
        target=worker.run_forever,
        kwargs={"stop_event": stop_event},
        name="beta6-embedded-queue-worker",
        daemon=True,
    )
    thread.start()
    return _EmbeddedQueueWorkerHandle(worker_runtime, stop_event, thread)


def _embedded_queue_worker_enabled(api_runtime: Beta6JobManager) -> bool:
    raw = os.getenv("RELIGION_EMBEDDED_QUEUE_WORKER", "auto").strip().lower()
    if raw in {"0", "false", "no", "off", "disabled"}:
        return False
    if raw in {"1", "true", "yes", "on", "enabled"}:
        return True
    return not bool(api_runtime._local_execution_enabled)


def _queue_worker_batch_limit() -> int:
    return _env_int(
        "RELIGION_EMBEDDED_QUEUE_WORKER_BATCH_LIMIT",
        _env_int("RELIGION_QUEUE_WORKER_BATCH_LIMIT", 8, minimum=1, maximum=128),
        minimum=1,
        maximum=128,
    )


def _queue_worker_poll_seconds() -> float:
    return _env_float(
        "RELIGION_EMBEDDED_QUEUE_WORKER_POLL_SECONDS",
        _env_float("RELIGION_QUEUE_WORKER_POLL_SECONDS", 1.0, minimum=0.01, maximum=60.0),
        minimum=0.01,
        maximum=60.0,
    )


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = int(default)
    return max(minimum, min(maximum, value))


def _env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = float(default)
    return max(minimum, min(maximum, value))


def _job_status_event_stream(runtime: Beta6JobManager, job_id: str):
    yield _sse_open_prelude()
    started = monotonic()
    max_seconds = max(30.0, float(os.getenv("RELIGION_JOB_EVENT_STREAM_MAX_SECONDS", "3600")))
    interval = max(0.25, min(float(os.getenv("RELIGION_JOB_EVENT_INTERVAL_SECONDS", "1.0")), 5.0))
    while True:
        status = runtime.get_status(job_id)
        yield _sse_event("status", status)
        if status.get("status") in {"completed", "failed", "interrupted"}:
            break
        if monotonic() - started >= max_seconds:
            yield _sse_event(
                "status",
                {
                    **status,
                    "status": "interrupted",
                    "error": "job event stream time limit reached; resume with polling",
                    "canRetry": True,
                },
            )
            break
        sleep(interval)


def _job_access_token(request: Request, query_token: str = "") -> str:
    if query_token:
        return str(query_token)
    header = request.headers.get("x-beta6-job-token", "")
    if header:
        return header.strip()
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def _job_session_token(request: Request, query_session: str = "") -> str:
    if query_session:
        return str(query_session)
    header = request.headers.get("x-beta6-session-token", "")
    return header.strip()


def _job_account_subject(request: Request, query_account: str = "") -> str:
    if query_account:
        return str(query_account).strip()
    header = request.headers.get("x-beta6-account-subject", "")
    return header.strip()


def _require_job_access(
    runtime: Beta6JobManager,
    job_id: str,
    token: str,
    session_token: str = "",
    account_subject: str = "",
) -> None:
    try:
        allowed = runtime.authorize_job_access(job_id, token, session_token, account_subject)
    except KeyError:
        raise
    if not allowed:
        raise HTTPException(status_code=403, detail="job access token, session token, and account subject required")


def _sse_event(event: str, payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {data}\n\n"


def _sse_open_prelude() -> str:
    # Some tunnels/proxies buffer very small initial SSE chunks; a comment line keeps
    # browsers spec-compliant while forcing an early flush before the first status.
    return f": beta6-stream-open {' ' * 2048}\nretry: 2000\n\n"


def _resolve_language(profile: ProductProfile, language: str) -> str:
    resolved = (language or profile.default_language).strip().lower()
    if resolved not in profile.languages:
        raise HTTPException(status_code=400, detail="unsupported language")
    return resolved


def _analysis_mode_from_payload(payload: AnswerRequest) -> str:
    explicit = str(payload.analysisMode or "").strip()
    if explicit:
        return explicit
    return "fast" if payload.fastMode else ""


def _result_payload(row: SearchResult) -> dict[str, Any]:
    return {
        "id": row.canonical_id,
        "title": row.title,
        "citation": row.citation,
        "authorityBody": row.authority_body,
        "date": row.source_date,
        "topic": row.case_name,
        "type": row.case_type,
        "dataset": row.source_dataset,
        "path": row.source_path,
        "url": row.source_url,
        "score": row.score,
        "excerpt": " ".join(row.full_text.split())[:520],
    }


def _source_window_payload(
    profile: ProductProfile,
    row: SearchResult,
    *,
    start: int,
    end: int,
    radius: int,
    before: int | None = None,
    after: int | None = None,
) -> dict[str, Any]:
    text = str(row.full_text or "")
    source_length = len(text)
    safe_radius = max(10, min(int(radius or 900), 4000))
    safe_before = safe_radius if before is None else max(10, min(int(before or 0), 4000))
    safe_after = safe_radius if after is None else max(10, min(int(after or 0), 4000))
    safe_start = max(0, min(int(start or 0), source_length))
    safe_end = max(0, min(int(end or 0), source_length))
    if safe_end < safe_start:
        safe_end = safe_start
    window_start = max(0, safe_start - safe_before)
    window_end = min(source_length, max(safe_end, safe_start) + safe_after)
    return {
        "product": profile.key,
        "sourceId": row.canonical_id,
        "title": row.title,
        "citation": row.citation,
        "authorityBody": row.authority_body,
        "dataset": row.source_dataset,
        "path": row.source_path,
        "url": row.source_url,
        "type": row.case_type,
        "sourceKind": row.source_kind,
        "tradition": row.tradition,
        "school": row.school,
        "authorityLevel": row.authority_level,
        "authorityLabel": row.authority_label,
        "sourceLength": source_length,
        "windowStart": window_start,
        "windowEnd": window_end,
        "beforeChars": safe_before,
        "afterChars": safe_after,
        "highlightStart": safe_start - window_start,
        "highlightEnd": safe_end - window_start,
        "hasBefore": window_start > 0,
        "hasAfter": window_end < source_length,
        "text": text[window_start:window_end],
    }

app = create_app()
