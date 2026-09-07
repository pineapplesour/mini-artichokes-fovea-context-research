"""Minimal import fallback for Lawkey original snapshot.

Production Lawkey deployments should set `LAWKEY_WORKSPACE_SCRIPTS` to the
real legal engine scripts. This fallback only keeps the original app importable
for repository contract tests and disabled-LLM smoke runs.
"""

from __future__ import annotations

import re


def generate_search_keywords(user_task: str, *, model: str = "", keyword_count: int = 10) -> list[str]:
    tokens = re.findall(r"[0-9A-Za-z가-힣]+", user_task or "")
    out: list[str] = []
    for token in tokens:
        if token not in out:
            out.append(token)
        if len(out) >= keyword_count:
            break
    return out
