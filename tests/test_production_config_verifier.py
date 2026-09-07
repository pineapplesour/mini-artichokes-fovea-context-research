import importlib.util
from pathlib import Path

import pytest


def load_production_config_verifier():
    path = Path("tools/verify_production_config.py")
    if not path.exists():
        pytest.fail("tools/verify_production_config.py is missing")
    spec = importlib.util.spec_from_file_location("verify_production_config", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_production_config_requires_lawkey_gemma4_and_no_disabled_flags():
    verify_production_config = load_production_config_verifier()

    report = verify_production_config.build_report()

    assert report["passes"] is True
    assert report["llmProvider"]["passes"] is True
    assert report["llmProvider"]["configured"] == "lawkey"
    assert report["answerModel"]["passes"] is True
    assert report["answerModel"]["configured"] == "gemma-4-26b-a4b-it"
    assert report["disabledFlags"]["passes"] is True
    assert report["disabledFlags"]["present"] == []
    assert report["openAIOverride"]["passes"] is True
    assert report["secrets"]["passes"] is True


def test_production_config_allows_private_key_file_pointer_without_raw_keys():
    verify_production_config = load_production_config_verifier()

    report = verify_production_config.build_report()

    assert report["passes"] is True
    assert report["secrets"]["passes"] is True
    assert "UNIVERSAL_ARTICHOKE_GEMMA_KEYS_FILE" not in report["secrets"]["present"]


def test_production_config_checks_runtime_constants_match_deployment_model():
    verify_production_config = load_production_config_verifier()

    report = verify_production_config.build_report()

    assert report["runtimeConstants"]["passes"] is True
    assert report["runtimeConstants"]["beta6DefaultModel"] == "gemma-4-26b-a4b-it"
    assert report["runtimeConstants"]["geminiChatModel"] == "gemma-4-26b-a4b-it"


def test_production_config_fails_when_supervisor_env_disables_llm(tmp_path):
    verify_production_config = load_production_config_verifier()
    env_path = tmp_path / "beta6.env"
    env_path.write_text(
        "\n".join(
            [
                "RELIGION_LLM_PROVIDER=lawkey",
                "RELIGION_ANSWER_MODEL=gemma-4-26b-a4b-it",
                "RELIGION_LLM_DISABLED=1",
            ]
        ),
        encoding="utf-8",
    )

    report = verify_production_config.build_report(env_path=env_path)

    assert report["passes"] is False
    assert report["disabledFlags"]["passes"] is False
    assert report["disabledFlags"]["present"] == ["RELIGION_LLM_DISABLED"]


def test_production_config_optional_runtime_readiness_probe():
    verify_production_config = load_production_config_verifier()

    def probe(env):
        assert env["RELIGION_LLM_PROVIDER"] == "lawkey"
        assert env["RELIGION_ANSWER_MODEL"] == "gemma-4-26b-a4b-it"
        return {
            "checked": True,
            "passes": True,
            "available": True,
            "provider": "lawkey_gemini_generate_content",
            "model": "gemma-4-26b-a4b-it",
        }

    report = verify_production_config.build_report(check_runtime=True, runtime_probe=probe)

    assert report["passes"] is True
    assert report["runtimeReadiness"]["checked"] is True
    assert report["runtimeReadiness"]["available"] is True
    assert report["runtimeReadiness"]["provider"] == "lawkey_gemini_generate_content"
    assert report["runtimeReadiness"]["model"] == "gemma-4-26b-a4b-it"


def test_production_config_runtime_readiness_failure_fails_report():
    verify_production_config = load_production_config_verifier()

    def probe(env):
        return {
            "checked": True,
            "passes": False,
            "available": False,
            "provider": "",
            "model": "",
            "error": "missing keys",
        }

    report = verify_production_config.build_report(check_runtime=True, runtime_probe=probe)

    assert report["passes"] is False
    assert report["runtimeReadiness"]["passes"] is False
    assert report["runtimeReadiness"]["error"] == "missing keys"


def test_production_config_optional_completion_smoke_probe():
    verify_production_config = load_production_config_verifier()

    def probe(env):
        assert env["RELIGION_LLM_PROVIDER"] == "lawkey"
        return {
            "checked": True,
            "passes": True,
            "provider": "lawkey_gemini_generate_content",
            "model": "gemma-4-26b-a4b-it",
            "responsePreview": "beta6-gemma4-ok",
            "responseChars": 16,
        }

    report = verify_production_config.build_report(check_completion=True, completion_probe=probe)

    assert report["passes"] is True
    assert report["completionSmoke"]["checked"] is True
    assert report["completionSmoke"]["passes"] is True
    assert report["completionSmoke"]["provider"] == "lawkey_gemini_generate_content"
    assert report["completionSmoke"]["model"] == "gemma-4-26b-a4b-it"


def test_production_config_completion_smoke_failure_fails_report():
    verify_production_config = load_production_config_verifier()

    def probe(env):
        return {
            "checked": True,
            "passes": False,
            "provider": "lawkey_gemini_generate_content",
            "model": "gemma-4-26b-a4b-it",
            "error": "timeout",
        }

    report = verify_production_config.build_report(check_completion=True, completion_probe=probe)

    assert report["passes"] is False
    assert report["completionSmoke"]["passes"] is False
    assert report["completionSmoke"]["error"] == "timeout"


def test_production_config_completion_smoke_redacts_api_key_from_errors(monkeypatch):
    verify_production_config = load_production_config_verifier()
    leaked_key = "UA-LEAK-SECRET-12345"

    class FailingClient:
        provider = "lawkey_gemini_generate_content"
        default_model = "gemma-4-26b-a4b-it"

        def complete(self, *args, **kwargs):
            raise RuntimeError(
                "400 Client Error: Bad Request for url: "
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemma-4-26b-a4b-it:generateContent?key={leaked_key}"
            )

    class FakeBeta6:
        @staticmethod
        def default_llm_client_from_env():
            return FailingClient()

    monkeypatch.setattr(verify_production_config.importlib, "import_module", lambda name: FakeBeta6)

    report = verify_production_config.build_report(check_completion=True)

    assert report["passes"] is False
    assert report["completionSmoke"]["passes"] is False
    assert leaked_key not in report["completionSmoke"]["error"]
    assert "key=[REDACTED]" in report["completionSmoke"]["error"]
