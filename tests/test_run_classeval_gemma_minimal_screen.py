from __future__ import annotations

from tools import run_classeval_dependency_separator_mixed as mixed
from tools import run_classeval_gemma_minimal_screen as minimal


def test_only_thinking_level_changes_from_frozen_screen():
    assert minimal.GEMMA_THINKING_LEVEL == "minimal"
    assert mixed.GEMMA_MODEL == "gemma-4-26b-a4b-it"
    assert mixed.GEMMA_TEMPERATURE == 0.6
    assert mixed.GEMMA_MAX_OUTPUT == 16_384
    assert mixed.GEMMA_TIMEOUT == 120
    assert mixed.GEMMA_KEY_COUNT == 10


def test_contract_wrapper_adds_variant_provenance(monkeypatch):
    monkeypatch.setattr(minimal, "_BASE_BUILD_CONTRACT", lambda *args, **kwargs:
                        {"protocolSha": "base-protocol", "model": "base-model"})
    monkeypatch.setattr(mixed.base, "sha", lambda path: "wrapper-sha")

    contract = minimal._build_contract("ignored")

    assert contract == {"protocolSha": "base-protocol", "model": "base-model",
                        "wrapperSha": "wrapper-sha",
                        "baseCommit": "212368e",
                        "variant": "gemma-minimal-screen"}


def test_main_restores_frozen_globals_after_success(monkeypatch):
    original = (mixed.GEMMA_THINKING_LEVEL, mixed.PROTOCOL, mixed._build_contract)
    observed = {}

    def fake_main(argv):
        observed["settings"] = (mixed.GEMMA_THINKING_LEVEL, mixed.PROTOCOL,
                                 mixed._build_contract)
        return 17

    monkeypatch.setattr(mixed, "main", fake_main)
    assert minimal.main(["--dry-run"]) == 17
    assert observed["settings"] == ("minimal", minimal.PROTOCOL, minimal._build_contract)
    assert (mixed.GEMMA_THINKING_LEVEL, mixed.PROTOCOL, mixed._build_contract) == original


def test_main_restores_frozen_globals_after_delegate_error(monkeypatch):
    original = (mixed.GEMMA_THINKING_LEVEL, mixed.PROTOCOL, mixed._build_contract)

    def fail(_argv):
        raise RuntimeError("mock delegate failure")

    monkeypatch.setattr(mixed, "main", fail)
    try:
        minimal.main([])
    except RuntimeError as exc:
        assert str(exc) == "mock delegate failure"
    else:
        raise AssertionError("delegate error was swallowed")
    assert (mixed.GEMMA_THINKING_LEVEL, mixed.PROTOCOL, mixed._build_contract) == original
