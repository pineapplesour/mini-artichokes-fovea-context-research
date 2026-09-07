from __future__ import annotations

from harness_research.trace_gated_mini.swe_rebench import build_python_public_test_command, sha256_text


def test_sha256_text_is_stable() -> None:
    assert sha256_text("opaque test patch\n") == "d6cd19a5bf7d1f13977284bf147d55e67a5473e1514381ac16d89bfecdb3c245"


def test_public_command_uses_only_pass_to_pass_ids() -> None:
    command = build_python_public_test_command(
        ["tests/test_a.py::test_ok", "tests/test_b.py::test_param[value with space]"],
        fallback="pytest -q tests/test_a.py tests/test_b.py",
    )
    assert "tests/test_a.py::test_ok" in command
    assert "'tests/test_b.py::test_param[value with space]'" in command
    assert command.startswith("python -m pytest")
