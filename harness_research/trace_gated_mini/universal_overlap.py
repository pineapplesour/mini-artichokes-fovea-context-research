"""Universal selective escalation over frozen whole-task Codex candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Sequence

from .core import (
    AgentAdapter,
    CodexAdapter,
    CritiqueResult,
    TaskSpec,
    _compact_evidence,
    attempt_from_payload,
    execute_attempt,
    execute_critique,
    run_claim_oracle_for_attempt,
    select_attempt,
    to_jsonable,
)
from .prompts import build_repair_prompt


_MISSING_ORACLE = (
    "#!/usr/bin/env bash\n"
    "echo 'critic did not produce a completed claim oracle' >&2\n"
    "exit 2\n"
)


def run_universal_overlap(
    *,
    source_repo: Path,
    task: TaskSpec,
    frozen_result_path: Path,
    output_dir: Path,
    critics: Sequence[tuple[str, str, AgentAdapter]],
    repair_adapter: AgentAdapter,
    public_test_timeout_seconds: int,
) -> dict[str, object]:
    """Escalate only a frozen Mini disagreement through independent critics."""

    if len(critics) < 2:
        raise ValueError("Universal overlap requires at least two independent critics")
    output_dir.mkdir(parents=True, exist_ok=False)
    frozen_bytes = frozen_result_path.read_bytes()
    frozen = json.loads(frozen_bytes)
    if frozen.get("task_id") != task.task_id or frozen.get("arm") != "mini":
        raise ValueError("frozen result is not the matching Mini candidate run")
    attempts = [
        attempt_from_payload(item)
        for item in frozen["attempts"]
        if item["candidate_id"] in {"a", "b", "c"}
    ]
    if len(attempts) != 3:
        raise ValueError("exactly three frozen independent candidates are required")

    selected = select_attempt(attempts)
    initial_evidence = _compact_evidence(attempts)
    critique_results: list[CritiqueResult] = []
    oracle_texts: list[str] = []
    for critic_id, perspective, adapter in critics:
        critique = execute_critique(
            source_repo=source_repo,
            task=task,
            output_dir=output_dir,
            adapter=adapter,
            seed_patch=selected.patch_text,
            evidence=initial_evidence,
            critic_id=critic_id,
            perspective=perspective,
        )
        critique_results.append(critique)
        oracle_texts.append(critique.oracle_text or _MISSING_ORACLE)

    attempts = [
        run_claim_oracle_for_attempt(
            source_repo=source_repo,
            task=task,
            output_dir=output_dir,
            attempt=item,
            oracle_text=oracle_texts,
            timeout_seconds=public_test_timeout_seconds,
        )
        for item in attempts
    ]
    selected = select_attempt(attempts)
    evidence = _compact_evidence(attempts)
    critic_memo = "\n\n===== INDEPENDENT CRITIC =====\n\n".join(
        f"[{critic_id} / {perspective}]\n{critique.last_message}"
        for (critic_id, perspective, _), critique in zip(critics, critique_results)
    )
    repair_prompt = build_repair_prompt(
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
        adapter=repair_adapter,
        public_test_timeout_seconds=public_test_timeout_seconds,
        prompt_override=repair_prompt,
        seed_patch=selected.patch_text,
    )
    repair = run_claim_oracle_for_attempt(
        source_repo=source_repo,
        task=task,
        output_dir=output_dir,
        attempt=repair,
        oracle_text=oracle_texts,
        timeout_seconds=public_test_timeout_seconds,
    )
    all_attempts = [*attempts, repair]
    selected = repair if repair.eligible else select_attempt(all_attempts)
    payload = {
        "schema_version": 1,
        "task_id": task.task_id,
        "arm": "universal_overlap",
        "candidate_model_result_sha256": hashlib.sha256(frozen_bytes).hexdigest(),
        "candidate_count": 3,
        "critic_count": len(critique_results),
        "selective_policy": "accept only complete+safe+public+all-claim-oracles; otherwise escalate",
        "repair_triggered": True,
        "repair_trigger_reason": "patch_disagreement",
        "critics": [to_jsonable(item) for item in critique_results],
        "oracle_sha256": [
            hashlib.sha256(item.encode("utf-8")).hexdigest() for item in oracle_texts
        ],
        "selected_candidate_id": selected.candidate_id,
        "selected_patch_sha256": selected.patch_sha256,
        "selected_eligible": selected.eligible,
        "attempts": [to_jsonable(item) for item in all_attempts],
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
    parser.add_argument("--spec-model", default="gpt-5.6-sol")
    parser.add_argument("--spec-reasoning-effort", default="high")
    parser.add_argument("--regression-model", default="gpt-5.6-terra")
    parser.add_argument("--regression-reasoning-effort", default="high")
    parser.add_argument("--repair-model", default="gpt-5.6-sol")
    parser.add_argument("--repair-reasoning-effort", default="high")
    parser.add_argument("--agent-timeout-seconds", type=int, default=600)
    parser.add_argument("--test-timeout-seconds", type=int, default=300)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    common = {
        "codex_home": args.codex_home.resolve(),
        "timeout_seconds": args.agent_timeout_seconds,
    }
    result = run_universal_overlap(
        source_repo=args.source_repo.resolve(),
        task=TaskSpec.from_json(args.task),
        frozen_result_path=args.frozen_result.resolve(),
        output_dir=args.output_dir.resolve(),
        critics=(
            (
                "critic-spec",
                "spec_first",
                CodexAdapter(
                    **common,
                    model=args.spec_model,
                    reasoning_effort=args.spec_reasoning_effort,
                ),
            ),
            (
                "critic-regression",
                "regression_first",
                CodexAdapter(
                    **common,
                    model=args.regression_model,
                    reasoning_effort=args.regression_reasoning_effort,
                ),
            ),
        ),
        repair_adapter=CodexAdapter(
            **common,
            model=args.repair_model,
            reasoning_effort=args.repair_reasoning_effort,
        ),
        public_test_timeout_seconds=args.test_timeout_seconds,
    )
    print(json.dumps({
        "task_id": result["task_id"],
        "arm": result["arm"],
        "selected_candidate_id": result["selected_candidate_id"],
        "selected_eligible": result["selected_eligible"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
