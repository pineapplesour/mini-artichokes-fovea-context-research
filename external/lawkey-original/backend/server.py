from __future__ import annotations

import hashlib
import hmac
import os
import posixpath
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import PROJECT_ROOT
from .domain_routes import install_domain_routes
from .jobs import LawkeyJobManager
from .judges import JudgeStore, hash_anon_token

JUDGES_DB_PATH = Path(os.environ.get("LAWKEY_JUDGES_DB", "/srv/lawkey/shared/judges.sqlite3"))
JUDGES_PASSWORD = os.environ.get("LAWKEY_JUDGES_PASSWORD", "13579")
JUDGES_REVIEW_SALT = os.environ.get("LAWKEY_JUDGES_REVIEW_SALT", "lawkey-judges-2026")
LAWKEY_SITE_ACCESS_CODE_ENV = "LAWKEY_SITE_ACCESS_CODE"
LAWKEY_SITE_ACCESS_COOKIE = "lawkey_site_access"
LAWKEY_SITE_ACCESS_HEADER = "x-lawkey-site-access-code"
LAWKEY_SITE_ACCESS_SALT = b"lawkey-site-access-v1"
LAWKEY_SITE_ACCESS_MAX_AGE_SECONDS = 60 * 60 * 24 * 30


ENCODED_SEPARATOR_RE = re.compile(r"%(?:2f|5c)", re.IGNORECASE)
WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:")


def _configured_site_access_code(site_access_code: str | None = None) -> str:
    if site_access_code is None:
        site_access_code = os.environ.get(LAWKEY_SITE_ACCESS_CODE_ENV, "")
    return str(site_access_code or "").strip()


def _site_access_cookie_value(access_code: str) -> str:
    return hmac.new(access_code.encode("utf-8"), LAWKEY_SITE_ACCESS_SALT, hashlib.sha256).hexdigest()


def _secure_site_access_cookie() -> bool:
    value = os.environ.get("LAWKEY_SECURE_COOKIES", "")
    return value.lower() in {"1", "true", "yes", "on"}


def _site_access_exempt(path: str) -> bool:
    return path in {"/api/health", "/api/site-access", "/api/site-access/login", "/api/site-access/logout"}


def _request_has_site_access(request: Request, access_code: str) -> bool:
    if not access_code:
        return True
    expected_cookie = _site_access_cookie_value(access_code)
    cookie_value = request.cookies.get(LAWKEY_SITE_ACCESS_COOKIE, "")
    if cookie_value and hmac.compare_digest(cookie_value, expected_cookie):
        return True
    header_value = request.headers.get(LAWKEY_SITE_ACCESS_HEADER, "")
    if header_value and hmac.compare_digest(header_value.strip(), access_code):
        return True
    auth_value = request.headers.get("authorization", "")
    if auth_value.lower().startswith("bearer "):
        token = auth_value.split(" ", 1)[1].strip()
        if token and hmac.compare_digest(token, access_code):
            return True
    return False


def _site_access_login_html(product_name: str) -> str:
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{product_name} access</title>
  <style>
    :root {{ color-scheme: light dark; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; background: #f6f7f8; color: #16181d; }}
    main {{ width: min(420px, calc(100vw - 32px)); }}
    h1 {{ margin: 0 0 10px; font-size: 24px; line-height: 1.2; }}
    p {{ margin: 0 0 18px; color: #5d6470; line-height: 1.5; }}
    form {{ display: grid; gap: 10px; }}
    input, button {{ width: 100%; box-sizing: border-box; border-radius: 8px; font: inherit; }}
    input {{ border: 1px solid #cfd4dc; padding: 12px 13px; background: #fff; color: #111827; }}
    button {{ border: 0; padding: 12px 14px; background: #111827; color: #fff; cursor: pointer; }}
    #error {{ min-height: 20px; margin-top: 12px; color: #b42318; font-size: 14px; }}
    @media (prefers-color-scheme: dark) {{
      body {{ background: #0e1116; color: #f8fafc; }}
      p {{ color: #a7b0bd; }}
      input {{ background: #171b22; border-color: #343b46; color: #f8fafc; }}
      button {{ background: #f8fafc; color: #111827; }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>{product_name}</h1>
    <p>Enter the team access code to continue.</p>
    <form id="access-form">
      <input id="access-code" name="accessCode" type="password" autocomplete="current-password" autofocus />
      <button type="submit">Continue</button>
    </form>
    <div id="error" role="alert"></div>
  </main>
  <script>
    document.getElementById("access-form").addEventListener("submit", async (event) => {{
      event.preventDefault();
      const error = document.getElementById("error");
      error.textContent = "";
      const accessCode = document.getElementById("access-code").value;
      const response = await fetch("/api/site-access/login", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ accessCode }})
      }});
      if (response.ok) {{
        window.location.reload();
        return;
      }}
      error.textContent = "Access code was not accepted.";
    }});
  </script>
</body>
</html>"""


def _resolve_frontend_static_path(dist_dir: Path, full_path: str, raw_path: bytes | str = b"") -> Path | None:
    root = dist_dir.resolve()
    raw_value = raw_path.decode("ascii", errors="ignore") if isinstance(raw_path, bytes) else str(raw_path or "")
    raw_without_query = raw_value.split("?", 1)[0]
    decoded_raw = unquote(raw_without_query).lstrip("/")
    decoded_full = unquote(str(full_path or ""))
    if ENCODED_SEPARATOR_RE.search(raw_without_query):
        raise HTTPException(status_code=404, detail="static file not found")
    if _is_unsafe_frontend_path(decoded_raw) or _is_unsafe_frontend_path(decoded_full):
        raise HTTPException(status_code=404, detail="static file not found")
    normalized = posixpath.normpath(decoded_full)
    if normalized in {"", "."}:
        return root / "index.html"
    candidate = (root / normalized).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="static file not found") from exc
    if candidate.exists():
        resolved = candidate.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="static file not found") from exc
        if resolved.is_file():
            return resolved
        raise HTTPException(status_code=404, detail="static file not found")
    return None


def _is_unsafe_frontend_path(path_value: str) -> bool:
    value = str(path_value or "")
    if "\x00" in value or "\\" in value or value.startswith(("/", "\\")) or WINDOWS_ABSOLUTE_RE.match(value):
        return True
    parts = [part for part in value.split("/") if part not in {"", "."}]
    return any(part == ".." for part in parts)


def create_app(
    manager: Any | None = None,
    *,
    frontend_dist: Path | None = None,
    domain_manager: Any | None = None,
    domain_profiles: dict[str, Any] | None = None,
    site_access_code: str | None = None,
) -> FastAPI:
    app = FastAPI(title="Lawkey AI Backend")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    runtime = manager or LawkeyJobManager()
    judges = JudgeStore(JUDGES_DB_PATH) if JUDGES_DB_PATH.parent.exists() else None
    configured_site_access_code = _configured_site_access_code(site_access_code)

    @app.middleware("http")
    async def _require_site_access(request: Request, call_next):
        if (
            not configured_site_access_code
            or request.method == "OPTIONS"
            or _site_access_exempt(request.url.path)
            or _request_has_site_access(request, configured_site_access_code)
        ):
            return await call_next(request)
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "site access required"}, status_code=401)
        if request.method in {"GET", "HEAD"}:
            return HTMLResponse(_site_access_login_html("Lawkey AI"), status_code=200)
        return JSONResponse({"detail": "site access required"}, status_code=401)

    @app.on_event("startup")
    def _resume_jobs_after_restart() -> None:
        import threading

        if hasattr(runtime, "resume_after_restart"):
            threading.Thread(target=runtime.resume_after_restart, daemon=True).start()

    def _require_password(payload: dict[str, Any] | None) -> None:
        provided = ""
        if isinstance(payload, dict):
            provided = str(payload.get("password") or "").strip()
        if provided != JUDGES_PASSWORD:
            raise HTTPException(status_code=401, detail="invalid password")

    def _require_judges() -> JudgeStore:
        if judges is None:
            raise HTTPException(status_code=503, detail="judges database unavailable")
        return judges

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/site-access")
    def site_access_status(request: Request) -> dict[str, bool]:
        return {
            "required": bool(configured_site_access_code),
            "authenticated": _request_has_site_access(request, configured_site_access_code),
        }

    @app.post("/api/site-access/login")
    async def site_access_login(request: Request) -> JSONResponse:
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        access_code = str((payload or {}).get("accessCode") or (payload or {}).get("code") or "").strip()
        if not configured_site_access_code or not hmac.compare_digest(access_code, configured_site_access_code):
            return JSONResponse({"detail": "invalid access code"}, status_code=401)
        response = JSONResponse({"ok": True})
        response.set_cookie(
            LAWKEY_SITE_ACCESS_COOKIE,
            _site_access_cookie_value(configured_site_access_code),
            max_age=LAWKEY_SITE_ACCESS_MAX_AGE_SECONDS,
            httponly=True,
            secure=_secure_site_access_cookie(),
            samesite="strict",
        )
        return response

    @app.post("/api/site-access/logout")
    def site_access_logout() -> JSONResponse:
        response = JSONResponse({"ok": True})
        response.delete_cookie(LAWKEY_SITE_ACCESS_COOKIE)
        return response

    install_domain_routes(app, domain_manager=domain_manager, domain_profiles=domain_profiles)

    @app.get("/api/document-presets")
    def document_presets() -> list[dict[str, Any]]:
        return runtime.list_document_presets()

    @app.post("/api/uploads")
    async def upload_sample(file: UploadFile = File(...)) -> dict[str, Any]:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="empty upload")
        try:
            return runtime.save_uploaded_sample(file.filename or "sample.txt", content)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/jobs")
    def list_jobs(clientId: str = "") -> list[dict[str, Any]]:
        return runtime.list_jobs(client_id=clientId)

    @app.post("/api/jobs")
    def create_job(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return runtime.create_job(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/document-preflight")
    def document_preflight(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return runtime.document_preflight(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/intent-classify")
    def intent_classify(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return runtime.classify_intent(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        try:
            return runtime.get_job_status(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc

    @app.get("/api/jobs/{job_id}/result")
    def get_job_result(job_id: str) -> dict[str, Any]:
        try:
            return runtime.get_job_result(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc

    @app.post("/api/jobs/{job_id}/follow-up")
    def follow_up_job(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return runtime.follow_up(job_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            return runtime.cancel_job(job_id, payload or {})
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc

    @app.get("/api/jobs/{job_id}/precedents/{precedent_id}")
    def get_precedent_detail(job_id: str, precedent_id: str) -> dict[str, Any]:
        try:
            return runtime.get_precedent_detail(job_id, precedent_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="precedent not found") from exc

    @app.get("/api/jobs/{job_id}/artifacts/{artifact_path:path}")
    def get_job_artifact(job_id: str, artifact_path: str) -> FileResponse:
        try:
            job = runtime._require_job(job_id)  # type: ignore[attr-defined]
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="job not found") from exc
        run_dir = job.run_dir.resolve()
        runs_root = getattr(runtime, "_runs_root", None)
        if runs_root is not None:
            try:
                run_dir.relative_to(Path(runs_root).resolve())
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="invalid artifact path") from exc
        candidate = (run_dir / artifact_path).resolve()
        try:
            candidate.relative_to(run_dir)
            if runs_root is not None:
                candidate.relative_to(Path(runs_root).resolve())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid artifact path") from exc
        if not candidate.exists() or not candidate.is_file():
            raise HTTPException(status_code=404, detail="artifact not found")
        return FileResponse(candidate)

    @app.post("/api/judges/auth")
    def judges_auth(payload: dict[str, Any]) -> dict[str, Any]:
        _require_password(payload)
        return {"ok": True}

    @app.post("/api/judges/search")
    def judges_search(payload: dict[str, Any]) -> dict[str, Any]:
        _require_password(payload)
        store = _require_judges()
        return {"results": store.search_judges(query=str(payload.get("q") or ""), limit=int(payload.get("limit") or 30))}

    @app.post("/api/judges/{judge_id}")
    def judges_profile(judge_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        _require_password(payload)
        store = _require_judges()
        judge = store.get_judge(judge_id)
        if not judge:
            raise HTTPException(status_code=404, detail="judge not found")
        return {
            "judge": judge,
            "career": store.list_career(judge_id),
            "casesPage": store.list_cases(judge_id, limit=int(payload.get("caseLimit") or 20), offset=int(payload.get("caseOffset") or 0)),
            "reviews": store.list_reviews(judge_id),
            "summary": store.get_summary(judge_id),
        }

    @app.post("/api/judges/{judge_id}/cases")
    def judges_cases(judge_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        _require_password(payload)
        store = _require_judges()
        return store.list_cases(
            judge_id,
            limit=int(payload.get("limit") or 20),
            offset=int(payload.get("offset") or 0),
        )

    @app.post("/api/judges/{judge_id}/summarize")
    def judges_summarize(judge_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        _require_password(payload)
        store = _require_judges()
        judge = store.get_judge(judge_id)
        if not judge:
            raise HTTPException(status_code=404, detail="judge not found")
        cached = store.get_summary(judge_id)
        if cached:
            return {"judge": judge, "summary": cached, "fromCache": True}
        canonical_ids = store.case_canonical_ids(judge_id, limit=2000)
        try:
            result = runtime.summarize_judge(  # type: ignore[attr-defined]
                judge=judge,
                canonical_ids=canonical_ids,
            )
        except AttributeError:
            raise HTTPException(status_code=503, detail="summarizer not available")
        summary_text = result.get("summary", "")
        store.save_summary(
            judge_id=judge_id,
            summary=summary_text,
            samples_used=int(result.get("samplesUsed") or 0),
            total_cases=len(canonical_ids),
            generated_by=str(payload.get("clientId") or ""),
        )
        saved = store.get_summary(judge_id)
        return {"judge": judge, "summary": saved, "fromCache": False}

    @app.post("/api/judges/precedent/{canonical_id}")
    def judges_precedent_text(canonical_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        _require_password(payload)
        import sqlite3
        from .config import PRECEDENT_DB_PATH

        conn = sqlite3.connect(str(PRECEDENT_DB_PATH))
        try:
            row = conn.execute(
                "SELECT canonical_id, case_number, case_name, court, decision_date, full_text FROM precedents WHERE canonical_id = ?",
                (canonical_id,),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="precedent not found")
        return {
            "canonicalId": row[0],
            "caseNumber": row[1] or "",
            "caseName": row[2] or "",
            "court": row[3] or "",
            "decisionDate": row[4] or "",
            "fullText": row[5] or "",
        }

    @app.post("/api/judges/{judge_id}/predict")
    def judges_predict(judge_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        _require_password(payload)
        store = _require_judges()
        judge = store.get_judge(judge_id)
        if not judge:
            raise HTTPException(status_code=404, detail="judge not found")
        question = str(payload.get("question") or "").strip()
        if not question:
            raise HTTPException(status_code=400, detail="question required")
        canonical_ids = store.case_canonical_ids(judge_id, limit=2000)
        try:
            result = runtime.run_judge_prediction(  # type: ignore[attr-defined]
                judge=judge,
                question=question,
                canonical_ids=canonical_ids,
                client_id=str(payload.get("clientId") or ""),
            )
        except AttributeError:
            return {"error": "prediction backend not available"}
        return result

    @app.post("/api/judges/{judge_id}/reviews")
    def judges_add_review(judge_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        _require_password(payload)
        store = _require_judges()
        client_id = str(payload.get("clientId") or "").strip()
        if not client_id:
            raise HTTPException(status_code=400, detail="clientId required")
        anon_token = hash_anon_token(client_id, judge_id, JUDGES_REVIEW_SALT)
        try:
            review = store.add_review(
                judge_id=judge_id,
                rating=int(payload.get("rating") or 0),
                body=str(payload.get("body") or ""),
                anon_token=anon_token,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"review": review, **store.list_reviews(judge_id)}

    dist_dir = frontend_dist or (PROJECT_ROOT / "dist")
    if dist_dir.exists():
        expo_asset_dir = dist_dir / "_expo"
        if expo_asset_dir.exists():
            app.mount("/_expo", StaticFiles(directory=expo_asset_dir), name="expo-assets")

        @app.get("/", include_in_schema=False)
        def frontend_root() -> FileResponse:
            return FileResponse(dist_dir / "index.html")

        @app.get("/{full_path:path}", include_in_schema=False)
        def frontend_fallback(full_path: str, request: Request) -> FileResponse:
            candidate = _resolve_frontend_static_path(dist_dir, full_path, request.scope.get("raw_path", b""))
            if candidate is not None:
                return FileResponse(candidate)
            return FileResponse(dist_dir / "index.html")

    return app


app = create_app()
