"""Re-arbitrate frozen Mini candidates with a separately specified model."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .core import (
    CodexAdapter,
    TaskSpec,
    _compact_evidence,
    attempt_from_payload,
    execute_critique,
    execute_attempt,
    run_claim_oracle_for_attempt,
    select_attempt,
    to_jsonable,
)
from .prompts import build_repair_prompt


def rearbitrate(
    *,
    source_repo: Path,
    task: TaskSpec,
    frozen_result_path: Path,
    output_dir: Path,
    adapter: CodexAdapter,
    critic_adapter: CodexAdapter | None,
    reuse_frozen_critic: bool,
    public_test_timeout_seconds: int,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=False)
    frozen_bytes = frozen_result_path.read_bytes()
    frozen = json.loads(frozen_bytes)
    if frozen["task_id"] != task.task_id or frozen["arm"] != "mini":
        raise ValueError("frozen result is not the matching Mini task")
    original_attempts = [
        attempt_from_payload(item)
        for item in frozen["attempts"]
        if item["candidate_id"] in {"a", "b", "c"}
    ]
    if len(original_attempts) != 3:
        raise ValueError("exactly three frozen independent candidates are required")
    selected = select_attempt(original_attempts)
    evidence = _compact_evidence(original_attempts)
    critique: object | None = None
    critic_memo = None
    critic_oracle = None
    if reuse_frozen_critic:
        if critic_adapter is not None:
            raise ValueError("cannot both reuse and rerun a critic")
        critique = frozen.get("critic")
        if not isinstance(critique, dict) or not isinstance(critique.get("last_message"), str):
            raise ValueError("frozen result has no completed critic memo")
        critic_memo = critique["last_message"]
        if isinstance(critique.get("oracle_text"), str):
            critic_oracle = critique["oracle_text"]
    elif critic_adapter is not None:
        critique = execute_critique(
            source_repo=source_repo,
            task=task,
            output_dir=output_dir,
            adapter=critic_adapter,
            seed_patch=selected.patch_text,
            evidence=evidence,
        )
        critic_memo = critique.last_message
        critic_oracle = critique.oracle_text
    if critique is not None:
        critic_oracle = critic_oracle or (
            "#!/usr/bin/env bash\n"
            "echo 'critic did not produce a completed claim oracle' >&2\n"
            "exit 2\n"
        )
        original_attempts = [
            run_claim_oracle_for_attempt(
                source_repo=source_repo,
                task=task,
                output_dir=output_dir,
                attempt=item,
                oracle_text=critic_oracle,
                timeout_seconds=public_test_timeout_seconds,
            )
            for item in original_attempts
        ]
        selected = select_attempt(original_attempts)
        evidence = _compact_evidence(original_attempts)
    prompt = build_repair_prompt(
        task.instruction,
        selected.candidate_id,
        evidence,
        "patch_disagreement",
        critic_memo=critic_memo,
    )
    repair = execute_attempt(
        source_repo=source_repo,
        task=task,
        output_dir=output_dir,
        candidate_id="repair",
        policy="mini",
        adapter=adapter,
        public_test_timeout_seconds=public_test_timeout_seconds,
        prompt_override=prompt,
        seed_patch=selected.patch_text,
    )
    if critic_oracle is not None:
        repair = run_claim_oracle_for_attempt(
            source_repo=source_repo,
            task=task,
            output_dir=output_dir,
            attempt=repair,
            oracle_text=critic_oracle,
            timeout_seconds=public_test_timeout_seconds,
        )
    if repair.eligible:
        selected = repair
    payload = {
        "schema_version": 1,
        "task_id": task.task_id,
        "arm": "mini",
        "candidate_model_result_sha256": hashlib.sha256(frozen_bytes).hexdigest(),
        "rearbitrated": True,
        "repair_triggered": True,
        "repair_trigger_reason": "patch_disagreement",
        "critic": to_jsonable(critique) if critique else None,
        "selected_candidate_id": selected.candidate_id,
        "selected_patch_sha256": selected.patch_sha256,
        "selected_eligible": selected.eligible,
        "attempts": [to_jsonable(item) for item in [*original_attempts, repair]],
        "evaluation": None,
    }
    (output_dir / "result.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-repo", required=True, type=Path)
    parser.add_argument("--task", required=True, type=Path)
    parser.add_argument("--frozen-result", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--codex-home", required=True, type=Path)
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument("--critic-model")
    parser.add_argument("--critic-reasoning-effort", default="high")
    parser.add_argument("--reuse-frozen-critic", action="store_true")
    parser.add_argument("--agent-timeout-seconds", type=int, default=600)
    parser.add_argument("--test-timeout-seconds", type=int, default=300)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = rearbitrate(
        source_repo=args.source_repo.resolve(),
        task=TaskSpec.from_json(args.task),
        frozen_result_path=args.frozen_result.resolve(),
        output_dir=args.output_dir.resolve(),
        adapter=CodexAdapter(
            codex_home=args.codex_home.resolve(),
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            timeout_seconds=args.agent_timeout_seconds,
        ),
        critic_adapter=(
            CodexAdapter(
                codex_home=args.codex_home.resolve(),
                model=args.critic_model,
                reasoning_effort=args.critic_reasoning_effort,
                timeout_seconds=args.agent_timeout_seconds,
            )
            if args.critic_model
            else None
        ),
        reuse_frozen_critic=args.reuse_frozen_critic,
        public_test_timeout_seconds=args.test_timeout_seconds,
    )
    print(json.dumps({
        "task_id": result["task_id"],
        "selected_candidate_id": result["selected_candidate_id"],
        "selected_eligible": result["selected_eligible"],
        "rearbitrated": result["rearbitrated"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
