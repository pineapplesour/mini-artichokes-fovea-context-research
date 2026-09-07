"""Thin minimal-thinking wrapper around the frozen Gemma screen runner."""
from __future__ import annotations

from pathlib import Path

from tools import run_classeval_dependency_separator_mixed as mixed


ROOT = mixed.ROOT
PROTOCOL = ROOT / "experiment_protocols/2026-09-06-classeval-gemma-minimal-screen.md"
VARIANT = "gemma-minimal-screen"
BASE_COMMIT = "212368e"
GEMMA_THINKING_LEVEL = "minimal"
_BASE_BUILD_CONTRACT = mixed._build_contract


def _build_contract(*args, **kwargs):
    contract = dict(_BASE_BUILD_CONTRACT(*args, **kwargs))
    contract.update({"wrapperSha": mixed.base.sha(Path(__file__)),
                     "baseCommit": BASE_COMMIT, "variant": VARIANT})
    return contract


def main(argv=None) -> int:
    saved = (mixed.GEMMA_THINKING_LEVEL, mixed.PROTOCOL, mixed._build_contract)
    try:
        mixed.GEMMA_THINKING_LEVEL = GEMMA_THINKING_LEVEL
        mixed.PROTOCOL = PROTOCOL
        mixed._build_contract = _build_contract
        return mixed.main(argv)
    finally:
        (mixed.GEMMA_THINKING_LEVEL, mixed.PROTOCOL,
         mixed._build_contract) = saved


if __name__ == "__main__":
    raise SystemExit(main())
