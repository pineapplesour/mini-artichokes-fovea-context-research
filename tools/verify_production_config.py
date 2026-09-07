#!/usr/bin/env python3
"""Verify production-facing beta6 LLM configuration."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_ENV_PATH = ROOT / "ops" / "supervisor" / "beta6.env"
EXPECTED_PROVIDER = "lawkey"
EXPECTED_MODEL = "gemma-4-26b-a4b-it"
DISABLED_FLAGS = ("RELIGION_LLM_DISABLED", "RELIGION_DISABLE_LLM")
OPENAI_OVERRIDE_KEYS = ("RELIGION_CHAT_API_URL",)
SECRET_KEY_FRAGMENTS = ("API_KEY", "TOKEN", "SECRET", "PASSWORD")
RUNTIME_CONFIG_KEYS = (
    "RELIGION_LLM_PROVIDER",
    "RELIGION_ANSWER_MODEL",
    "RELIGION_LLM_DISABLED",
    "RELIGION_DISABLE_LLM",
    "RELIGION_CHAT_API_URL",
    "RELIGION_CHAT_API_KEY",
    "RELIGION_CHAT_TIMEOUT_SECONDS",
    "RELIGION_GEMINI_THINKING_LEVEL",
)
RuntimeProbe = Callable[[dict[str, str]], dict[str, Any]]
CompletionProbe = Callable[[dict[str, str]], dict[str, Any]]


def build_report(
    *,
    env_path: str | Path | None = None,
    check_runtime: bool = False,
    runtime_probe: RuntimeProbe | None = None,
    check_completion: bool = False,
    completion_probe: CompletionProbe | None = None,
) -> dict[str, Any]:
    path = Path(env_path) if env_path is not None else DEFAULT_ENV_PATH
    env = _read_env(path)
    runtime_constants = _runtime_constants_report()
    runtime_readiness = _runtime_readiness_report(env, check_runtime=check_runtime, runtime_probe=runtime_probe)
    completion_smoke = _completion_smoke_report(env, check_completion=check_completion, completion_probe=completion_probe)
    provider_report = _expected_value_report(env, "RELIGION_LLM_PROVIDER", EXPECTED_PROVIDER)
    model_report = _expected_value_report(env, "RELIGION_ANSWER_MODEL", EXPECTED_MODEL)
    disabled_report = _forbidden_keys_report(env, DISABLED_FLAGS)
    openai_report = _forbidden_keys_report(env, OPENAI_OVERRIDE_KEYS)
    secrets_report = _secrets_report(env)
    supervisor_report = _supervisor_contract_report()
    passes = all(
        item["passes"]
        for item in (
            {"passes": path.exists()},
            provider_report,
            model_report,
            disabled_report,
            openai_report,
            secrets_report,
            runtime_constants,
            runtime_readiness,
            completion_smoke,
            supervisor_report,
        )
    )
    return {
        "passes": passes,
        "envPath": str(path),
        "envExists": path.exists(),
        "expectedProvider": EXPECTED_PROVIDER,
        "expectedModel": EXPECTED_MODEL,
        "llmProvider": provider_report,
        "answerModel": model_report,
        "disabledFlags": disabled_report,
        "openAIOverride": openai_report,
        "secrets": secrets_report,
        "runtimeConstants": runtime_constants,
        "runtimeReadiness": runtime_readiness,
        "completionSmoke": completion_smoke,
        "supervisorContract": supervisor_report,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", default="", help="Path to production env file.")
    parser.add_argument("--check-runtime", action="store_true", help="Verify non-network LLM client readiness using local keys.")
    parser.add_argument("--check-completion", action="store_true", help="Run a short real Gemma4 completion smoke.")
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    parser.add_argument("--output", default="", help="Write JSON report to this path.")
    args = parser.parse_args(argv)
    report = build_report(
        env_path=args.env or None,
        check_runtime=args.check_runtime,
        check_completion=args.check_completion,
    )
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("PASS production config" if report["passes"] else "FAIL production config")
    return 0 if report["passes"] else 1


def _read_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _expected_value_report(env: dict[str, str], key: str, expected: str) -> dict[str, Any]:
    configured = env.get(key, "")
    return {
        "key": key,
        "expected": expected,
        "configured": configured,
        "passes": configured == expected,
    }


def _forbidden_keys_report(env: dict[str, str], keys: tuple[str, ...]) -> dict[str, Any]:
    present = sorted(key for key in keys if env.get(key, "").strip())
    return {
        "keys": list(keys),
        "present": present,
        "passes": not present,
    }


def _secrets_report(env: dict[str, str]) -> dict[str, Any]:
    present = sorted(key for key, value in env.items() if value and any(fragment in key for fragment in SECRET_KEY_FRAGMENTS))
    return {
        "present": present,
        "passes": not present,
        "policy": "production env file must contain non-secret defaults only",
    }


def _runtime_constants_report() -> dict[str, Any]:
    beta6 = importlib.import_module("shared_platform.beta6")
    gemini_chat = importlib.import_module("shared_platform.gemini_chat")
    beta6_model = getattr(beta6, "DEFAULT_LAWKEY_WRITER_MODEL", "")
    gemini_model = getattr(gemini_chat, "GEMMA4_26B_MODEL", "")
    return {
        "beta6DefaultModel": beta6_model,
        "geminiChatModel": gemini_model,
        "passes": beta6_model == EXPECTED_MODEL and gemini_model == EXPECTED_MODEL,
    }


def _supervisor_contract_report() -> dict[str, Any]:
    path = ROOT / "tools" / "verify_supervisor_contract.py"
    spec = importlib.util.spec_from_file_location("verify_supervisor_contract_for_production_config", path)
    module = importlib.util.module_from_spec(spec)
    if spec is None or spec.loader is None:
        return {"passes": False, "serviceCount": 0, "environmentPass": False}
    spec.loader.exec_module(module)
    verifier = module
    report = verifier.build_report()
    return {
        "passes": report.get("passes") is True and report.get("environmentPass") is True,
        "serviceCount": report.get("serviceCount", 0),
        "environmentPass": report.get("environmentPass") is True,
    }


def _runtime_readiness_report(
    env: dict[str, str],
    *,
    check_runtime: bool,
    runtime_probe: RuntimeProbe | None,
) -> dict[str, Any]:
    if not check_runtime:
        return {
            "checked": False,
            "passes": True,
            "available": None,
            "provider": "",
            "model": "",
            "error": "",
        }
    if runtime_probe is not None:
        report = dict(runtime_probe(dict(env)))
        report.setdefault("checked", True)
        report.setdefault("passes", bool(report.get("available")))
        return report
    previous = {key: os.environ.get(key) for key in RUNTIME_CONFIG_KEYS}
    try:
        for key in RUNTIME_CONFIG_KEYS:
            if key in env:
                os.environ[key] = env[key]
            elif key in {"RELIGION_LLM_PROVIDER", "RELIGION_ANSWER_MODEL", *DISABLED_FLAGS, *OPENAI_OVERRIDE_KEYS}:
                os.environ.pop(key, None)
        beta6 = importlib.import_module("shared_platform.beta6")
        client = beta6.default_llm_client_from_env()
        if client is None:
            return {
                "checked": True,
                "passes": False,
                "available": False,
                "provider": "",
                "model": "",
                "error": "default_llm_client_from_env returned None",
            }
        provider = str(getattr(client, "provider", ""))
        model = str(getattr(client, "default_model", ""))
        passes = provider == "lawkey_gemini_generate_content" and model == EXPECTED_MODEL
        return {
            "checked": True,
            "passes": passes,
            "available": True,
            "provider": provider,
            "model": model,
            "error": "" if passes else "unexpected runtime client",
        }
    except Exception as exc:
        return {
            "checked": True,
            "passes": False,
            "available": False,
            "provider": "",
            "model": "",
            "error": str(exc),
        }
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _completion_smoke_report(
    env: dict[str, str],
    *,
    check_completion: bool,
    completion_probe: CompletionProbe | None,
) -> dict[str, Any]:
    if not check_completion:
        return {
            "checked": False,
            "passes": True,
            "provider": "",
            "model": "",
            "responsePreview": "",
            "responseChars": 0,
            "error": "",
        }
    if completion_probe is not None:
        report = dict(completion_probe(dict(env)))
        report.setdefault("checked", True)
        report.setdefault("passes", bool(report.get("responseChars")))
        return report
    previous = {key: os.environ.get(key) for key in RUNTIME_CONFIG_KEYS}
    try:
        for key in RUNTIME_CONFIG_KEYS:
            if key in env:
                os.environ[key] = env[key]
            elif key in {"RELIGION_LLM_PROVIDER", "RELIGION_ANSWER_MODEL", *DISABLED_FLAGS, *OPENAI_OVERRIDE_KEYS}:
                os.environ.pop(key, None)
        beta6 = importlib.import_module("shared_platform.beta6")
        client = beta6.default_llm_client_from_env()
        if client is None:
            return {
                "checked": True,
                "passes": False,
                "provider": "",
                "model": "",
                "responsePreview": "",
                "responseChars": 0,
                "error": "default_llm_client_from_env returned None",
            }
        timeout = float(os.getenv("RELIGION_PRODUCTION_CONFIG_COMPLETION_TIMEOUT_SECONDS", "45"))
        response = client.complete(
            [
                {"role": "system", "content": "Return only this exact token: beta6-gemma4-ok"},
                {"role": "user", "content": "production Gemma4 smoke"},
            ],
            model=EXPECTED_MODEL,
            timeout_seconds=timeout,
        )
        text = str(response or "").strip()
        provider = str(getattr(client, "provider", ""))
        model = str(getattr(client, "default_model", EXPECTED_MODEL) or EXPECTED_MODEL)
        passes = bool(text) and provider == "lawkey_gemini_generate_content" and model == EXPECTED_MODEL
        return {
            "checked": True,
            "passes": passes,
            "provider": provider,
            "model": model,
            "responsePreview": text[:120],
            "responseChars": len(text),
            "error": "" if passes else "empty response or unexpected runtime client",
        }
    except Exception as exc:
        return {
            "checked": True,
            "passes": False,
            "provider": "",
            "model": EXPECTED_MODEL,
            "responsePreview": "",
            "responseChars": 0,
            "error": str(exc),
        }
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    raise SystemExit(main())
