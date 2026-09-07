import pytest
import sqlite3
import threading
import time
from fastapi.testclient import TestClient

from shared_platform.beta6 import Beta6JobManager
from shared_platform.products import ProductProfile
from shared_platform.server import create_app
from tests.test_search_adapters import _make_documents_db, _make_precedents_db, _make_tcm_domain_db


SESSION_TOKEN = "test-local-session-token-abcdefghijklmnopqrstuvwxyz"
SESSION_HEADERS = {"X-Beta6-Session-Token": SESSION_TOKEN}


@pytest.fixture(autouse=True)
def _disable_default_lawkey_llm(monkeypatch):
    monkeypatch.setenv("RELIGION_LLM_DISABLED", "1")


def test_products_endpoint_returns_i18n_metadata(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    profile = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en", "ko", "ar"),
        default_language="en",
        theme="islam",
        safety_notice="notice",
    )
    client = TestClient(create_app({"islam": profile}))

    response = client.get("/api/products")

    assert response.status_code == 200
    assert response.json()["products"][0]["key"] == "islam"
    assert response.json()["products"][0]["languages"] == ["en", "ko", "ar"]


def test_search_endpoint_returns_sources(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    profile = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="islam",
        safety_notice="notice",
    )
    client = TestClient(create_app({"islam": profile}))

    response = client.get("/api/islam/search", params={"q": "qibla prayer"})

    assert response.status_code == 200
    body = response.json()
    assert body["product"] == "islam"
    assert body["results"][0]["id"] == "doc-fiqh-1"
    assert body["results"][0]["citation"] == "Prayer"


def test_answer_endpoint_returns_grounded_draft_and_beta6_records(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    profile = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="islam",
        safety_notice="notice",
    )
    client = TestClient(create_app({"islam": profile}))

    response = client.post("/api/islam/answer", json={"query": "qibla prayer", "language": "en"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"].startswith("## Evidence selected - writer required")
    assert body["writer"]["status"] == "requires_llm"
    assert body["answerReadiness"] == "evidence_selected_writer_required"
    assert body["sources"][0]["id"] == "doc-fiqh-1"
    assert body["beta6SelectedRecords"][0]["file_id"] == "doc-fiqh-1"


def test_answer_endpoint_accepts_fast_analysis_mode(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    profile = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="islam",
        safety_notice="notice",
    )
    runtime = Beta6JobManager({"islam": profile}, runs_root=tmp_path / "runs", llm_client=None, resume_pending_jobs=False)
    client = TestClient(create_app({"islam": profile}, runtime=runtime, rate_limit_per_minute=20))

    response = client.post("/api/islam/answer", json={"query": "qibla prayer", "language": "en", "limit": 30, "analysisMode": "fast"})

    assert response.status_code == 200
    body = response.json()
    assert body["analysisMode"] == "beta6_fast"
    assert body["fastMode"] is True
    assert body["beta6"]["fastMode"] is True
    assert body["beta6"]["selectedCount"] <= 30


def test_cors_does_not_allow_every_origin_by_default(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    profile = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="islam",
        safety_notice="notice",
    )
    client = TestClient(create_app({"islam": profile}))

    response = client.get("/api/health", headers={"Origin": "https://evil.example"})

    assert response.headers.get("access-control-allow-origin") != "*"


def test_answer_rejects_unsupported_language(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    profile = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="islam",
        safety_notice="notice",
    )
    client = TestClient(create_app({"islam": profile}))

    response = client.post("/api/islam/answer", json={"query": "qibla prayer", "language": "xx"})

    assert response.status_code == 400
    assert response.json()["detail"] == "unsupported language"


def test_rate_limit_can_reject_excess_requests(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    profile = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="islam",
        safety_notice="notice",
    )
    client = TestClient(create_app({"islam": profile}, rate_limit_per_minute=1))

    assert client.get("/api/products").status_code == 200
    response = client.get("/api/products")

    assert response.status_code == 429
    assert response.json()["detail"] == "rate limit exceeded"


def test_job_polling_does_not_spend_creation_rate_limit(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    profile = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="islam",
        safety_notice="notice",
    )
    client = TestClient(create_app({"islam": profile}, rate_limit_per_minute=1))

    created = client.post("/api/islam/jobs", headers=SESSION_HEADERS, json={"query": "qibla prayer", "language": "en"})
    assert created.status_code == 200
    job_id = created.json()["jobId"]
    token = created.json()["accessToken"]

    status = client.get(f"/api/jobs/{job_id}", headers=SESSION_HEADERS, params={"token": token})
    result = client.get(f"/api/jobs/{job_id}/result", headers=SESSION_HEADERS, params={"token": token})
    second_create = client.post("/api/islam/jobs", headers=SESSION_HEADERS, json={"query": "zakat", "language": "en"})

    assert status.status_code != 429
    assert result.status_code in (200, 425)
    assert second_create.status_code == 429


def test_job_events_endpoint_streams_sse_status_without_rate_limit(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    profile = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="islam",
        safety_notice="notice",
    )
    app = create_app({"islam": profile}, rate_limit_per_minute=1)
    client = TestClient(app)
    result = app.state.beta6_runtime.answer_sync(product="islam", query="qibla prayer", language="en", limit=3)

    with client.stream("GET", f"/api/jobs/{result['jobId']}/events") as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert body.startswith(": beta6-stream-open")
    assert len(body.split("\n", 1)[0]) >= 1024
    assert "event: status" in body
    assert '"status":"completed"' in body
    assert '"progress"' in body
    second_create = client.post("/api/islam/jobs", headers=SESSION_HEADERS, json={"query": "zakat", "language": "en"})
    assert second_create.status_code == 200


def test_created_jobs_return_access_token_and_protect_job_status_result_and_events(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    profile = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="islam",
        safety_notice="notice",
    )
    client = TestClient(create_app({"islam": profile}))

    created = client.post("/api/islam/jobs", headers=SESSION_HEADERS, json={"query": "qibla prayer", "language": "en"})
    assert created.status_code == 200
    body = created.json()
    job_id = body["jobId"]
    token = body["accessToken"]

    assert len(token) >= 24
    assert "accessTokenHash" not in body
    assert "sessionTokenHash" not in body
    assert client.get(f"/api/jobs/{job_id}").status_code == 403
    assert client.get(f"/api/jobs/{job_id}", params={"token": "wrong"}).status_code == 403
    assert client.get(f"/api/jobs/{job_id}", params={"token": token}).status_code == 403
    assert client.get(f"/api/jobs/{job_id}", headers={"X-Beta6-Session-Token": "wrong"}, params={"token": token}).status_code == 403

    status = client.get(f"/api/jobs/{job_id}", headers=SESSION_HEADERS, params={"token": token})
    result = client.get(f"/api/jobs/{job_id}/result", headers=SESSION_HEADERS, params={"token": token})
    query_session_status = client.get(f"/api/jobs/{job_id}", params={"token": token, "session": SESSION_TOKEN})
    with client.stream("GET", f"/api/jobs/{job_id}/events", params={"token": token, "session": SESSION_TOKEN}) as event_response:
        event_body = "".join(event_response.iter_text())

    assert status.status_code == 200
    assert "accessTokenHash" not in status.json()
    assert "sessionTokenHash" not in status.json()
    assert result.status_code in (200, 425)
    assert client.get(f"/api/jobs/{job_id}/result").status_code == 403
    assert query_session_status.status_code == 200
    assert event_response.status_code == 200
    assert "event: status" in event_body


def test_product_scoped_job_routes_match_generic_job_routes_without_cross_product_leak(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    islam = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="islam",
        safety_notice="notice",
    )
    tcm = ProductProfile(
        key="tcm",
        name="Hanui AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="tcm",
        safety_notice="notice",
    )
    client = TestClient(create_app({"islam": islam, "tcm": tcm}))
    created = client.post("/api/islam/jobs", headers=SESSION_HEADERS, json={"query": "qibla prayer", "language": "en"})
    assert created.status_code == 200
    job_id = created.json()["jobId"]
    token = created.json()["accessToken"]

    generic_status = client.get(f"/api/jobs/{job_id}", headers=SESSION_HEADERS, params={"token": token})
    product_status = client.get(f"/api/islam/jobs/{job_id}", headers=SESSION_HEADERS, params={"token": token})
    wrong_product = client.get(f"/api/tcm/jobs/{job_id}", headers=SESSION_HEADERS, params={"token": token})
    product_result = client.get(f"/api/islam/jobs/{job_id}/result", headers=SESSION_HEADERS, params={"token": token})
    with client.stream("GET", f"/api/islam/jobs/{job_id}/events", params={"token": token, "session": SESSION_TOKEN}) as event_response:
        event_body = "".join(event_response.iter_text())

    assert generic_status.status_code == 200
    assert product_status.status_code == 200
    assert product_status.json()["jobId"] == generic_status.json()["jobId"]
    assert product_status.json()["product"] == "islam"
    assert wrong_product.status_code == 404
    assert product_result.status_code in (200, 425)
    assert event_response.status_code == 200
    assert "event: status" in event_body


def test_account_bound_jobs_require_same_account_subject(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    profile = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="islam",
        safety_notice="notice",
    )
    client = TestClient(create_app({"islam": profile}))
    account_headers = {**SESSION_HEADERS, "X-Beta6-Account-Subject": "user-123"}

    created = client.post(
        "/api/islam/jobs",
        headers=account_headers,
        json={"query": "qibla prayer", "language": "en"},
    )
    assert created.status_code == 200
    body = created.json()
    job_id = body["jobId"]
    token = body["accessToken"]

    assert "accountSubjectHash" not in body
    assert client.get(f"/api/jobs/{job_id}", headers=SESSION_HEADERS, params={"token": token}).status_code == 403
    assert (
        client.get(
            f"/api/jobs/{job_id}",
            headers={**SESSION_HEADERS, "X-Beta6-Account-Subject": "user-456"},
            params={"token": token},
        ).status_code
        == 403
    )

    status = client.get(f"/api/jobs/{job_id}", headers=account_headers, params={"token": token})
    result = client.get(f"/api/jobs/{job_id}/result", headers=account_headers, params={"token": token})
    query_account_status = client.get(
        f"/api/jobs/{job_id}",
        params={"token": token, "session": SESSION_TOKEN, "account": "user-123"},
    )

    assert status.status_code == 200
    assert "accountSubjectHash" not in status.json()
    assert result.status_code in (200, 425)
    assert query_account_status.status_code == 200


def test_async_job_creation_requires_anonymous_session_token(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    profile = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="islam",
        safety_notice="notice",
    )
    client = TestClient(create_app({"islam": profile}))

    missing = client.post("/api/islam/jobs", json={"query": "qibla prayer", "language": "en"})
    short = client.post(
        "/api/islam/jobs",
        headers={"X-Beta6-Session-Token": "short"},
        json={"query": "qibla prayer", "language": "en"},
    )
    created = client.post("/api/islam/jobs", headers=SESSION_HEADERS, json={"query": "qibla prayer", "language": "en"})

    assert missing.status_code == 400
    assert "session token" in missing.json()["detail"]
    assert short.status_code == 400
    assert created.status_code == 200
    assert created.json()["jobId"]
    assert created.json()["accessToken"]


def test_queue_only_api_status_refreshes_completed_external_worker_job(tmp_path, monkeypatch):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    runs_root = tmp_path / "runs"
    profile = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="islam",
        safety_notice="notice",
    )
    api_runtime = Beta6JobManager(
        {"islam": profile},
        runs_root=runs_root,
        local_execution_enabled=False,
        resume_pending_jobs=False,
        max_pending_jobs=10,
    )

    with TestClient(create_app({"islam": profile}, runtime=api_runtime, rate_limit_per_minute=20)) as client:
        created = client.post(
            "/api/islam/jobs",
            headers=SESSION_HEADERS,
            json={"query": "qibla prayer", "language": "en"},
        )
        body = created.json()
        job_id = body["jobId"]
        token = body["accessToken"]
        assert body["status"] == "queued"
        assert body["externalWorkerRequired"] is True

        worker_runtime = Beta6JobManager(
            {"islam": profile},
            runs_root=runs_root,
            max_workers=1,
            resume_pending_jobs=False,
        )
        original_run_context = worker_runtime._run_context
        entered_worker = threading.Event()
        release_worker = threading.Event()

        def blocking_run_context(context):
            entered_worker.set()
            release_worker.wait(timeout=5)
            return original_run_context(context)

        monkeypatch.setattr(worker_runtime, "_run_context", blocking_run_context)
        try:
            assert worker_runtime.resume_durable_queue_once(limit=1) == 1
            assert entered_worker.wait(timeout=2)
            api_running = client.get(f"/api/jobs/{job_id}", headers=SESSION_HEADERS, params={"token": token})
            assert api_running.status_code == 200
            assert api_running.json()["status"] == "running"
            release_worker.set()
            for _ in range(80):
                worker_status = worker_runtime.get_status(job_id)
                if worker_status["status"] == "completed":
                    break
                time.sleep(0.05)
            assert worker_runtime.get_status(job_id)["status"] == "completed"

            api_status = client.get(f"/api/jobs/{job_id}", headers=SESSION_HEADERS, params={"token": token})

            assert api_status.status_code == 200
            assert api_status.json()["status"] == "completed"
            assert api_status.json()["selectedCount"] > 0
        finally:
            worker_runtime.shutdown(wait=False, cancel_futures=True)


def test_embedded_queue_worker_drains_queue_only_app_jobs(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIGION_EMBEDDED_QUEUE_WORKER", "1")
    monkeypatch.setenv("RELIGION_EMBEDDED_QUEUE_WORKER_POLL_SECONDS", "0.01")
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    profile = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="islam",
        safety_notice="notice",
    )
    runtime = Beta6JobManager(
        {"islam": profile},
        runs_root=tmp_path / "runs",
        local_execution_enabled=False,
        resume_pending_jobs=False,
        max_pending_jobs=10,
    )

    with TestClient(create_app({"islam": profile}, runtime=runtime, rate_limit_per_minute=20)) as client:
        created = client.post(
            "/api/islam/jobs",
            headers=SESSION_HEADERS,
            json={"query": "qibla prayer", "language": "en"},
        )
        body = created.json()
        job_id = body["jobId"]
        token = body["accessToken"]
        assert body["externalWorkerRequired"] is True

        for _ in range(240):
            status = client.get(f"/api/jobs/{job_id}", headers=SESSION_HEADERS, params={"token": token})
            if status.json()["status"] == "completed":
                break
            time.sleep(0.05)

        assert status.status_code == 200
        assert status.json()["status"] == "completed"
        result = client.get(f"/api/jobs/{job_id}/result", headers=SESSION_HEADERS, params={"token": token})
        assert result.status_code == 200
        assert result.json()["answerReadiness"] in {"final_answer", "evidence_selected_writer_required"}


def test_async_job_queue_full_returns_structured_retryable_503(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIGION_QUEUE_RETRY_AFTER_SECONDS", "23")
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    profile = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="islam",
        safety_notice="notice",
    )
    runtime = Beta6JobManager(
        {"islam": profile},
        runs_root=tmp_path / "runs",
        max_workers=1,
        max_pending_jobs=1,
    )
    release = threading.Event()

    def blocking_run_context(context):
        release.wait(timeout=5)
        return {}

    monkeypatch.setattr(runtime, "_run_context", blocking_run_context)
    client = TestClient(create_app({"islam": profile}, runtime=runtime, rate_limit_per_minute=20))

    try:
        accepted = client.post(
            "/api/islam/jobs",
            headers=SESSION_HEADERS,
            json={"query": "qibla prayer", "language": "en"},
        )
        rejected = client.post(
            "/api/islam/jobs",
            headers=SESSION_HEADERS,
            json={"query": "zakat", "language": "en"},
        )

        assert accepted.status_code == 200
        assert rejected.status_code == 503
        assert rejected.headers["retry-after"] == "23"
        detail = rejected.json()["detail"]
        assert detail["code"] == "beta6_queue_full"
        assert detail["message"] == "job queue full"
        assert detail["retryAfterSeconds"] == 23
        assert detail["capacity"] == {
            "maxWorkers": 1,
            "maxPendingJobs": 1,
            "pendingJobs": 1,
            "availablePendingSlots": 0,
            "saturated": True,
            "retryAfterSeconds": 23,
        }
    finally:
        release.set()


def test_async_job_cancel_requires_job_and_session_token_and_returns_cancelled_status(tmp_path, monkeypatch):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    profile = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="islam",
        safety_notice="notice",
    )
    runtime = Beta6JobManager({"islam": profile}, runs_root=tmp_path / "runs", max_workers=1)
    entered = threading.Event()
    release = threading.Event()

    def blocking_run_context(context):
        entered.set()
        release.wait(timeout=5)
        return {}

    monkeypatch.setattr(runtime, "_run_context", blocking_run_context)
    client = TestClient(create_app({"islam": profile}, runtime=runtime, rate_limit_per_minute=20))

    try:
        created = client.post(
            "/api/islam/jobs",
            headers=SESSION_HEADERS,
            json={"query": "qibla prayer", "language": "en"},
        )
        body = created.json()
        job_id = body["jobId"]
        token = body["accessToken"]
        assert entered.wait(timeout=1)

        missing_token = client.post(f"/api/jobs/{job_id}/cancel", headers=SESSION_HEADERS)
        wrong_session = client.post(
            f"/api/jobs/{job_id}/cancel",
            headers={"X-Beta6-Session-Token": "wrong"},
            params={"token": token},
        )
        cancelled = client.post(f"/api/jobs/{job_id}/cancel", headers=SESSION_HEADERS, params={"token": token})
        status = client.get(f"/api/jobs/{job_id}", headers=SESSION_HEADERS, params={"token": token})
        result = client.get(f"/api/jobs/{job_id}/result", headers=SESSION_HEADERS, params={"token": token})

        assert missing_token.status_code == 403
        assert wrong_session.status_code == 403
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"
        assert cancelled.json()["cancelRequested"] is True
        assert status.json()["status"] == "cancelled"
        assert result.status_code == 425
        assert "cancel" in result.json()["detail"].lower()
    finally:
        release.set()


def test_service_worker_served_from_root_scope(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    profile = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="islam",
        safety_notice="notice",
    )
    client = TestClient(create_app({"islam": profile}))

    response = client.get("/sw.js")

    assert response.status_code == 200
    assert "shared-platform-shell" in response.text


def test_source_window_endpoint_returns_bounded_text_and_exact_highlight(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    profile = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="islam",
        safety_notice="notice",
    )
    client = TestClient(create_app({"islam": profile}))

    response = client.get(
        "/api/islam/source-window",
        params={"sourceId": "doc-fiqh-1", "start": 13, "end": 18, "radius": 10},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sourceId"] == "doc-fiqh-1"
    assert body["citation"] == "Prayer"
    assert body["windowStart"] > 0
    assert body["windowEnd"] < body["sourceLength"]
    assert body["hasBefore"] is True
    assert body["hasAfter"] is True
    assert body["text"][body["highlightStart"]:body["highlightEnd"]] == "qibla"
    assert len(body["text"]) <= 60


def test_source_window_endpoint_returns_404_for_unknown_source(tmp_path):
    db_path = tmp_path / "islam.sqlite3"
    _make_precedents_db(db_path)
    profile = ProductProfile(
        key="islam",
        name="Hikmah AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="islam",
        safety_notice="notice",
    )
    client = TestClient(create_app({"islam": profile}))

    response = client.get("/api/islam/source-window", params={"sourceId": "missing"})

    assert response.status_code == 404
    assert response.json()["detail"] == "source not found"


def test_tcm_source_window_endpoint_uses_same_bounded_highlight_contract(tmp_path):
    db_path = tmp_path / "tcm.sqlite3"
    _make_tcm_domain_db(db_path)
    profile = ProductProfile(
        key="tcm",
        name="Hanui AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="tcm",
        safety_notice="notice",
    )
    client = TestClient(create_app({"tcm": profile}))
    text = "[META]\nreligion: tcm-kmm\ntradition: kmm\nschool: korean-classic\nauthority_level: 100\nsource_kind: classic_canon\nauthority_label: classic canon\n\n甘草 감초 licorice 조화제약 諸藥을 조화시키는 본초 고문헌 근거."
    start = text.index("甘草")
    end = start + len("甘草")

    response = client.get(
        "/api/tcm/source-window",
        params={"sourceId": "doc-gamcho-classic", "start": start, "end": end, "radius": 18},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["product"] == "tcm"
    assert body["sourceId"] == "doc-gamcho-classic"
    assert body["sourceKind"] == "classic_canon"
    assert body["text"][body["highlightStart"]:body["highlightEnd"]] == "甘草"
    assert len(body["text"]) <= 80


def test_tcm_source_window_endpoint_can_open_passage_table_sources(tmp_path):
    db_path = tmp_path / "tcm-passages.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(
          canonical_id UNINDEXED,
          full_text,
          tokenize='unicode61'
        );
        CREATE TABLE sources (
          source_id TEXT PRIMARY KEY,
          title TEXT,
          author_body TEXT,
          tradition TEXT,
          school TEXT,
          source_kind TEXT,
          authority_level INTEGER,
          authority_label TEXT,
          source_url TEXT
        );
        CREATE TABLE passages (
          passage_id TEXT PRIMARY KEY,
          source_id TEXT,
          canonical_ref TEXT,
          language TEXT,
          heading TEXT,
          text TEXT
        );
        INSERT INTO sources VALUES
          ('src-bencao','本草綱目','Li Shizhen','kmm','bencao','materia_medica',86,'materia medica','');
        INSERT INTO passages VALUES
          ('passage-gamcho','src-bencao','本草綱目 #甘草','hanmun','補劑','甘草 감초 補中益氣 본초 원문');
        """
    )
    conn.commit()
    conn.close()
    profile = ProductProfile(
        key="tcm",
        name="Hanui AI",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="tcm",
        safety_notice="notice",
    )
    client = TestClient(create_app({"tcm": profile}))

    response = client.get(
        "/api/tcm/source-window",
        params={"sourceId": "passage-gamcho", "start": 0, "end": 6, "radius": 40},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sourceId"] == "passage-gamcho"
    assert body["sourceKind"] == "materia_medica"
    assert body["citation"] == "本草綱目 #甘草"
    assert body["text"][body["highlightStart"]:body["highlightEnd"]] == "[META]"


def test_simli_source_window_endpoint_uses_document_sources_with_exact_highlight(tmp_path):
    db_path = tmp_path / "psych.sqlite3"
    _make_documents_db(db_path)
    profile = ProductProfile(
        key="simli",
        name="Mental Health AI",
        db_path=db_path,
        db_shape="documents",
        languages=("ko", "en"),
        default_language="ko",
        theme="simli",
        safety_notice="notice",
    )
    client = TestClient(create_app({"simli": profile}))
    text = "Anxiety symptoms, panic, worry and functional impairment."
    start = text.index("panic")
    end = start + len("panic")

    response = client.get(
        "/api/simli/source-window",
        params={"sourceId": "doc-psych-1", "start": start, "end": end, "radius": 16},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["product"] == "simli"
    assert body["sourceId"] == "doc-psych-1"
    assert body["type"] == "guideline"
    assert body["text"][body["highlightStart"]:body["highlightEnd"]] == "panic"
    assert len(body["text"]) <= 80
