from __future__ import annotations

import sys
import types
import os
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
LAWKEY_ROOT = REPO_ROOT / "external" / "lawkey-original"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
os.environ.setdefault("LAWKEY_RUNS_ROOT", str(Path("/tmp/ua-lawkey-site-access-test-runs")))
for import_root in (LAWKEY_ROOT, SCRIPTS_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

rag_stub = types.ModuleType("legal_evidence_rag")
rag_stub.DEFAULT_QUESTION_CHUNK_TOKENS = 4000
rag_stub._strip_question_answer_meta_prefix = lambda value: value
rag_stub._count_tokens = lambda value: max(1, len(str(value)) // 4)
rag_stub.generate_search_keywords = lambda *args, **kwargs: []
sys.modules.setdefault("legal_evidence_rag", rag_stub)
sys.modules.setdefault("precedent_search_index", types.ModuleType("precedent_search_index"))
python_multipart_stub = types.ModuleType("python_multipart")
python_multipart_stub.__version__ = "0.0.99"
sys.modules.setdefault("python_multipart", python_multipart_stub)

from backend.server import create_app  # noqa: E402


class FakeLawkeyManager:
    def list_document_presets(self) -> list[dict[str, Any]]:
        return []

    def create_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"jobId": "job-site", "statusUrl": "/api/jobs/job-site", "resultUrl": "/api/jobs/job-site/result"}

    def list_jobs(self, client_id: str = "") -> list[dict[str, Any]]:
        return [{"jobId": "job-site", "clientId": client_id}]


def test_site_access_code_gate_blocks_api_until_login_cookie_is_set(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><title>Lawkey AI</title><body>app</body></html>", encoding="utf-8")
    client = TestClient(create_app(manager=FakeLawkeyManager(), frontend_dist=dist, site_access_code="team-code"))

    assert client.get("/api/health").status_code == 200
    gated_home = client.get("/")
    assert gated_home.status_code == 200
    assert "Enter the team access code" in gated_home.text

    blocked = client.post("/api/jobs", json={"userTask": "질문"})
    assert blocked.status_code == 401
    assert blocked.json()["detail"] == "site access required"

    login = client.post("/api/site-access/login", json={"accessCode": "team-code"})
    assert login.status_code == 200
    assert "lawkey_site_access=" in login.headers["set-cookie"]
    assert "HttpOnly" in login.headers["set-cookie"]

    created = client.post("/api/jobs", json={"userTask": "질문"})
    assert created.status_code == 200
    assert created.json()["jobId"] == "job-site"

    app_home = client.get("/")
    assert app_home.status_code == 200
    assert "<body>app</body>" in app_home.text


def test_site_access_code_gate_allows_team_header_for_non_browser_clients(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><title>Lawkey AI</title><body>app</body></html>", encoding="utf-8")
    client = TestClient(create_app(manager=FakeLawkeyManager(), frontend_dist=dist, site_access_code="team-code"))

    response = client.post(
        "/api/jobs",
        json={"userTask": "질문"},
        headers={"X-Lawkey-Site-Access-Code": "team-code"},
    )

    assert response.status_code == 200
    assert response.json()["jobId"] == "job-site"
