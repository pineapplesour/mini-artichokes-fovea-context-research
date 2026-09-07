import importlib.util
from pathlib import Path


def _load_verifier():
    path = Path("tools/verify_tunnel_health.py")
    spec = importlib.util.spec_from_file_location("verify_tunnel_health", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_tunnel_health_verifier_extracts_urls_and_checks_all_products(tmp_path):
    runtime = tmp_path / ".runtime"
    runtime.mkdir()
    (runtime / "islam-8061-tunnel.log").write_text(
        "INF |  https://islam.trycloudflare.com                    |\n",
        encoding="utf-8",
    )
    (runtime / "tcm-8062-tunnel.log").write_text(
        "INF |  https://tcm.trycloudflare.com                    |\n",
        encoding="utf-8",
    )
    (runtime / "simli-8063-tunnel.log").write_text(
        "INF |  https://simli.trycloudflare.com                    |\n",
        encoding="utf-8",
    )
    calls = []

    def fake_fetch(url, timeout):
        calls.append((url, timeout))
        return 200, '{"status":"ok"}'

    verifier = _load_verifier()
    report = verifier.build_report(runtime_dir=runtime, fetch=fake_fetch)

    assert report["passes"] is True
    assert [item["product"] for item in report["products"]] == ["islam", "tcm", "simli"]
    assert all(item["publicHealth"]["statusCode"] == 200 for item in report["products"])
    assert calls[0][0] == "https://islam.trycloudflare.com/api/health"


def test_tunnel_health_verifier_fails_missing_or_unhealthy_product(tmp_path):
    runtime = tmp_path / ".runtime"
    runtime.mkdir()
    (runtime / "islam-8061-tunnel.log").write_text(
        "INF |  https://islam.trycloudflare.com                    |\n",
        encoding="utf-8",
    )

    def fake_fetch(url, timeout):
        return 502, "bad gateway"

    verifier = _load_verifier()
    report = verifier.build_report(runtime_dir=runtime, fetch=fake_fetch)

    assert report["passes"] is False
    assert report["products"][0]["publicHealth"]["passes"] is False
    assert report["products"][1]["checks"]["urlFound"]["passes"] is False
    assert report["products"][2]["checks"]["urlFound"]["passes"] is False
