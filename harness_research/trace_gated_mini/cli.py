"""Command-line entry point for one frozen harness arm."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import CodexAdapter, TaskSpec, run_arm


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-repo", required=True, type=Path)
    parser.add_argument("--task", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--arm", choices=("direct", "kira", "mini"), required=True)
    parser.add_argument("--codex-home", required=True, type=Path)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--reasoning-effort", default="medium")
    parser.add_argument("--arbiter-model")
    parser.add_argument("--arbiter-reasoning-effort", default="high")
    parser.add_argument("--critic-model")
    parser.add_argument("--critic-reasoning-effort", default="high")
    parser.add_argument("--agent-timeout-seconds", type=int, default=600)
    parser.add_argument("--test-timeout-seconds", type=int, default=300)
    parser.add_argument("--no-repair", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    task = TaskSpec.from_json(args.task)
    adapter = CodexAdapter(
        codex_home=args.codex_home.resolve(),
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        timeout_seconds=args.agent_timeout_seconds,
    )
    repair_adapter = None
    if args.arbiter_model:
        repair_adapter = CodexAdapter(
            codex_home=args.codex_home.resolve(),
            model=args.arbiter_model,
            reasoning_effort=args.arbiter_reasoning_effort,
            timeout_seconds=args.agent_timeout_seconds,
        )
    critic_adapter = None
    if args.critic_model:
        critic_adapter = CodexAdapter(
            codex_home=args.codex_home.resolve(),
            model=args.critic_model,
            reasoning_effort=args.critic_reasoning_effort,
            timeout_seconds=args.agent_timeout_seconds,
        )
    result = run_arm(
        source_repo=args.source_repo.resolve(),
        task=task,
        output_dir=args.output_dir.resolve(),
        arm=args.arm,
        adapter=adapter,
        critic_adapter=critic_adapter,
        repair_adapter=repair_adapter,
        public_test_timeout_seconds=args.test_timeout_seconds,
        repair_on_all_fail=not args.no_repair,
    )
    print(json.dumps({
        "task_id": result["task_id"],
        "arm": result["arm"],
        "selected_candidate_id": result["selected_candidate_id"],
        "selected_eligible": result["selected_eligible"],
        "repair_triggered": result["repair_triggered"],
        "evaluation_exit_code": (result["evaluation"] or {}).get("exit_code"),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
