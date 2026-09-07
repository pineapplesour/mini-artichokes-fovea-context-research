#!/usr/bin/env python3
"""Run MAC-n-CHEESE's frozen committee through the approved Codex CLI account.

This is a review-only provider adapter. It does not alter MAC's prompts, panel,
area-chair synthesis, deterministic audit, or score gates, and it is not a
scientific contribution or manuscript artifact.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any


DEFAULT_MAC_ROOT = Path(
    "/mnt/d/Downloads/Telegram Desktop/"
    "ralphthon-review-agent-repositories-20260826/"
    "ralphthon-review-agent-repositories-20260826/MAC-n-CHEESE"
)
DEFAULT_CODEX_HOME = Path("/home/pineapple/.codex-new-account")


class SerialCodexClient:
    """Synchronous MAC client that serializes heavy Codex model calls."""

    def __init__(
        self,
        *,
        model: str,
        effort: str,
        codex_home: Path,
        runtime_root: Path,
        timeout_seconds: int,
    ) -> None:
        executable = shutil.which("codex")
        if executable is None:
            raise RuntimeError("codex executable is unavailable")
        if not (codex_home / "auth.json").is_file():
            raise RuntimeError(f"approved Codex auth is unavailable under {codex_home}")
        self.executable = executable
        self.model = model
        self.effort = effort
        self.codex_home = codex_home.resolve()
        self.runtime_root = runtime_root.resolve()
        self.timeout_seconds = timeout_seconds
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._counter = 0

    def __call__(self, messages: list[dict[str, str]]) -> str:
        with self._lock:
            self._counter += 1
            call_root = self.runtime_root / f"call-{self._counter:03d}"
            work_dir = call_root / "work"
            work_dir.mkdir(parents=True, exist_ok=False)
            prompt_path = call_root / "prompt.json"
            response_path = call_root / "response.md"
            stdout_path = call_root / "stdout.log"
            stderr_path = call_root / "stderr.log"
            prompt = json.dumps(
                {
                    "review_runtime": "MAC-n-CHEESE committee",
                    "instruction": (
                        "Follow the supplied messages exactly. Return only the requested "
                        "review Markdown or strict JSON. Do not use tools."
                    ),
                    "messages": messages,
                },
                ensure_ascii=False,
            )
            prompt_path.write_text(prompt, encoding="utf-8")
            command = [
                self.executable,
                "exec",
                "-",
                "--ephemeral",
                "--ignore-user-config",
                "--ignore-rules",
                "--skip-git-repo-check",
                "--sandbox",
                "read-only",
                "--model",
                self.model,
                "-c",
                f'model_reasoning_effort="{self.effort}"',
                "-c",
                "features.shell_tool=false",
                "-c",
                'web_search="disabled"',
                "-c",
                "features.multi_agent=false",
                "-c",
                "features.remote_plugin=false",
                "-c",
                "features.skill_mcp_dependency_install=false",
                "-c",
                "features.network_proxy=false",
                "-c",
                'shell_environment_policy.inherit="none"',
                "-c",
                'approval_policy="never"',
                "-C",
                str(work_dir),
                "--output-last-message",
                str(response_path),
            ]
            environment = dict(os.environ)
            environment["CODEX_HOME"] = str(self.codex_home)
            environment["NO_COLOR"] = "1"
            completed = subprocess.run(
                command,
                input=prompt,
                text=True,
                capture_output=True,
                env=environment,
                timeout=self.timeout_seconds,
                check=False,
            )
            stdout_path.write_text(completed.stdout, encoding="utf-8")
            stderr_path.write_text(completed.stderr, encoding="utf-8")
            if completed.returncode != 0 or not response_path.is_file():
                detail = completed.stderr.strip() or completed.stdout.strip()
                raise RuntimeError(
                    f"Codex committee call {self._counter} failed with exit "
                    f"{completed.returncode}: {detail[-1000:]}"
                )
            response = response_path.read_text(encoding="utf-8").strip()
            if not response:
                raise RuntimeError(f"Codex committee call {self._counter} returned no text")
            return response


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("paper", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--mac-root", type=Path, default=DEFAULT_MAC_ROOT)
    parser.add_argument("--codex-home", type=Path, default=DEFAULT_CODEX_HOME)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--effort", default="high", choices=("medium", "high", "xhigh"))
    parser.add_argument("--panel", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mac_root = args.mac_root.resolve()
    if not (mac_root / "run_review.py").is_file():
        raise RuntimeError(f"MAC-n-CHEESE checkout unavailable: {mac_root}")
    sys.path.insert(0, str(mac_root))

    from reviewer import model_critique  # type: ignore[import-not-found]

    client = SerialCodexClient(
        model=args.model,
        effort=args.effort,
        codex_home=args.codex_home,
        runtime_root=args.runtime_root,
        timeout_seconds=args.timeout_seconds,
    )

    def injected_client(*_args: Any, **_kwargs: Any) -> SerialCodexClient:
        return client

    model_critique._default_client = injected_client
    os.environ["OPENAI_API_KEY"] = "codex-cli-review-adapter"
    os.environ["OPENAI_MODEL"] = args.model
    os.environ["REVIEWER_PANEL"] = str(args.panel)
    os.environ["REVIEWER_COMMITTEE_EFFORT"] = args.effort
    os.environ["REVIEWER_COMMITTEE_TIMEOUT"] = str(args.timeout_seconds)
    os.environ["REVIEWER_PROGRESS"] = "1"

    import run_review  # type: ignore[import-not-found]

    argv = ["run_review.py", str(args.paper)]
    if args.evidence_dir is not None:
        argv.append(str(args.evidence_dir))
    argv.extend(["--out", str(args.out)])
    old_argv = sys.argv
    try:
        sys.argv = argv
        return int(run_review.main())
    finally:
        sys.argv = old_argv


if __name__ == "__main__":
    raise SystemExit(main())
