#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import shared_platform.queue_worker as queue_worker  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(queue_worker.main())
