"""Post-selection evaluator for test patches hidden during agent execution."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import collect_patch, prepare_workspace, run_process, run_shell, to_jsonable


def evaluate_selected(
    *,
    source_repo: Path,
    base_ref: str,
    arm_result_path: Path,
    evaluation_patch_path: Path,
    evaluation_command: str,
    output_dir: Path,
    timeout_seconds: int,
) -> dict[str, object]:
    """Evaluate only after the generating agent processes have terminated."""

    output_dir.mkdir(parents=True, exist_ok=False)
    arm_result = json.loads(arm_result_path.read_text(encoding="utf-8"))
    selected_id = arm_result["selected_candidate_id"]
    selected = next(item for item in arm_result["attempts"] if item["candidate_id"] == selected_id)
    selected_eligible = bool(arm_result.get("selected_eligible", True))
    solution_patch = selected["patch_text"]
    workspace = output_dir / "workspace"
    prepare_workspace(source_repo, base_ref, workspace)

    solution_path = output_dir / "selected.patch"
    solution_path.write_text(solution_patch, encoding="utf-8")
    applied_solution = run_process(
        ("git", "apply", "--binary", str(solution_path)),
        cwd=workspace,
        timeout_seconds=60,
    )
    failure_stage = None
    applied_tests = None
    evaluation = None
    if applied_solution.exit_code != 0:
        failure_stage = "selected_patch_apply"
    else:
        applied_tests = run_process(
            ("git", "apply", "--binary", str(evaluation_patch_path.resolve())),
            cwd=workspace,
            timeout_seconds=60,
        )
        if applied_tests.exit_code != 0:
            failure_stage = "evaluation_patch_apply"
        else:
            evaluation = run_shell(evaluation_command, workspace, timeout_seconds)
    changed, combined_patch, combined_sha, combined_lines = collect_patch(workspace)
    payload = {
        "schema_version": 1,
        "task_id": arm_result["task_id"],
        "arm": arm_result["arm"],
        "selected_candidate_id": selected_id,
        "selected_patch_sha256": selected["patch_sha256"],
        "selected_eligible": selected_eligible,
        "evaluation_patch_sha256": _sha256(evaluation_patch_path),
        "selected_patch_apply": to_jsonable(applied_solution),
        "evaluation_patch_apply": to_jsonable(applied_tests) if applied_tests else None,
        "evaluation": to_jsonable(evaluation) if evaluation else None,
        "failure_stage": failure_stage,
        "resolved": bool(
            selected_eligible and evaluation and evaluation.exit_code == 0 and not evaluation.timed_out
        ),
        "workspace": str(workspace),
        "combined_changed_files": list(changed),
        "combined_patch_sha256": combined_sha,
        "combined_patch_lines": combined_lines,
    }
    (output_dir / "combined.patch").write_text(combined_patch, encoding="utf-8")
    (output_dir / "evaluation.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-repo", required=True, type=Path)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--arm-result", required=True, type=Path)
    parser.add_argument("--evaluation-patch", required=True, type=Path)
    parser.add_argument("--evaluation-command", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = evaluate_selected(
        source_repo=args.source_repo.resolve(),
        base_ref=args.base_ref,
        arm_result_path=args.arm_result.resolve(),
        evaluation_patch_path=args.evaluation_patch.resolve(),
        evaluation_command=args.evaluation_command,
        output_dir=args.output_dir.resolve(),
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps({
        "task_id": result["task_id"],
        "arm": result["arm"],
        "resolved": result["resolved"],
        "evaluation_exit_code": (result["evaluation"] or {}).get("exit_code"),
        "failure_stage": result["failure_stage"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
