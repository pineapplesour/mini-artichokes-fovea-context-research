from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
LAWKEY_ORIGINAL = ROOT / "external" / "lawkey-original"


def test_lawkey_original_source_snapshot_contains_ui_engine_and_dist():
    assert (LAWKEY_ORIGINAL / "components/lawkey/workspace.tsx").exists()
    assert (LAWKEY_ORIGINAL / "components/lawkey/progress-strip.tsx").exists()
    assert (LAWKEY_ORIGINAL / "lib/use-lawkey-job.ts").exists()
    assert (LAWKEY_ORIGINAL / "lib/universal-ui-kernel.ts").exists()
    assert (LAWKEY_ORIGINAL / "backend/server.py").exists()
    assert (LAWKEY_ORIGINAL / "backend/jobs.py").exists()
    assert (LAWKEY_ORIGINAL / "dist/index.html").exists()

    assert not (ROOT / "web/lawkey.html").exists()
    assert not (ROOT / "web/lawkey-chat.html").exists()
    assert not (ROOT / "web/lawkey-chat.js").exists()


def test_lawkey_original_contract_records_only_adapter_boundaries():
    contract = json.loads((ROOT / "integrations/lawkey/original-app-contract.json").read_text(encoding="utf-8"))

    assert contract["productKey"] == "lawkey"
    assert contract["mode"] == "external-original-app"
    assert contract["sourceRoot"] == "external/lawkey-original"
    assert contract["serverModule"] == "apps.lawkey.server:app"
    assert contract["defaultPort"] == 8037
    assert contract["frontend"]["kind"] == "original-expo-dist"
    assert contract["frontend"]["kernelIntegrationStatus"] == "hook-level-capability-boundary-not-full-shared-browser-runtime"
    assert contract["frontend"]["route"] == "/"
    assert contract["frontend"]["universalKernelAdapter"] == "external/lawkey-original/lib/universal-ui-kernel.ts"
    assert contract["backend"]["module"] == "backend.server:app"
    assert contract["engine"]["module"] == "backend.jobs.LawkeyJobManager"
    assert contract["db"]["canonicalEnv"] == "LAWKEY_PRECEDENT_DB_PATH"
    assert contract["db"]["universalAliasEnv"] == "RELIGION_LAWKEY_DB_PATH"
    assert contract["invariants"]["doNotCreateUniversalHtmlShells"] is True
    assert contract["invariants"]["preserveOriginalDesign"] is True
    assert contract["invariants"]["preserveOriginalEngine"] is True


def test_lawkey_hook_uses_universal_kernel_boundary_without_changing_original_workspace():
    hook = (LAWKEY_ORIGINAL / "lib/use-lawkey-job.ts").read_text(encoding="utf-8")
    workspace = (LAWKEY_ORIGINAL / "components/lawkey/workspace.tsx").read_text(encoding="utf-8")

    assert 'from "./universal-ui-kernel"' in hook
    assert "lawkeyUniversalKernel.createJob" in hook
    assert "lawkeyUniversalKernel.getJobStatus" in hook
    assert "lawkeyUniversalKernel.getJobResult" in hook
    assert "lawkeyUniversalKernel.cancelJob" in hook
    assert "lawkeyUniversalKernel.getPrecedentDetail" in hook
    assert "useLawkeyJob" in workspace
    assert "universal-ui-kernel" not in workspace


def test_lawkey_universal_adapter_serves_original_app_without_rewriting_ui(monkeypatch, tmp_path):
    db_path = tmp_path / "precedents.sqlite3"
    db_path.write_bytes(b"sqlite placeholder")
    runs_root = tmp_path / "runs"
    monkeypatch.setenv("RELIGION_LAWKEY_DB_PATH", str(db_path))
    monkeypatch.setenv("LAWKEY_RUNS_ROOT", str(runs_root))
    sys.modules.pop("apps.lawkey.server", None)
    server = importlib.import_module("apps.lawkey.server")

    assert server.PRODUCT_KEY == "lawkey"
    assert server.PORT == 8037
    assert server.LAWKEY_SOURCE_ROOT == LAWKEY_ORIGINAL.resolve()
    assert server.LAWKEY_FRONTEND_DIST == (LAWKEY_ORIGINAL / "dist").resolve()
    assert server.ORIGINAL_BACKEND_MODULE == "backend.server"

    client = TestClient(server.app)
    health = client.get("/api/health")
    root = client.get("/")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert root.status_code == 200
    assert root.text == (LAWKEY_ORIGINAL / "dist/index.html").read_text(encoding="utf-8")


def test_lawkey_original_contract_verifier_passes():
    completed = subprocess.run(
        [sys.executable, "tools/verify_lawkey_original_contract.py", "--json"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    report = json.loads(completed.stdout)

    assert report["passes"] is True
    assert report["productKey"] == "lawkey"
    assert report["defaultPort"] == 8037
    assert report["preservesOriginalDesign"] is True
    assert report["preservesOriginalEngine"] is True
