#!/usr/bin/env python3
"""One-command fallback entrypoint for zip/non-Codex maintenance."""

from __future__ import annotations

from tools.standalone_apply_diff_and_run import main


if __name__ == "__main__":
    raise SystemExit(main())
