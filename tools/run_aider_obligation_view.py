#!/usr/bin/env python3
"""Same repair instruction with case-local or obligation-aligned evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from tools import run_aider_shared_failure_overlap as base
from tools.obligation_overlap_view import failure_records, make_view


REPAIR = """Use strong general execution-feedback repair. Read the normalized failure
view in /tmp/artifacts/repair-view.json. It explicitly separates authoritative
displayed expectations from the candidates' wrong observations where parsing is
safe. Use ALL failures, not only identical diagnostic messages shared by every
candidate: different wrong observations can violate the same required behavior.
Inspect remaining requirements task by task. Compare their displayed expected
behavior with the actual current source before deciding what to retain or edit.
Use all public candidate states, specifications and original feedback freely.
Repair general causes, not just the printed examples. Unknown or truncated
diagnostics require source/specification reasoning rather than invented facts.
Use actual-source checks for consequential ambiguity, prioritize complete task
repairs, and preserve working behavior. Before the final response, recheck the
expected fields against the changed source so that replacing one known wrong
response with another candidate's wrong response does not count as repair."""


def transform_prompt(prompt: str) -> str:
    if base.GENERIC not in prompt:
        raise ValueError("unexpected base prompt")
    return prompt.replace(base.GENERIC, REPAIR)


def stage_view(artifact: Path, mode: str) -> dict:
    feedback = json.loads((artifact / "case-feedback.json").read_text())
    view = make_view(feedback, mode)
    alternate = make_view(feedback, "obligation_overlap" if mode == "case_local" else "case_local")
    expected = sorted((task_id, case_id, candidate, row["message"])
        for task_id, task in feedback.items() for case_id, rows in task["failures"].items()
        for row in rows for candidate in row["candidates"])
    if failure_records(view) != expected or failure_records(alternate) != expected:
        raise ValueError("failure records changed")
    encoded = (json.dumps(view, ensure_ascii=False) + "\n").encode()
    (artifact / "repair-view.json").write_bytes(encoded)
    return {"representation": mode, "viewBytes": len(encoded), "failureRecords": len(expected),
        "canonicalFailureRecordsSha256": hashlib.sha256(json.dumps(expected, ensure_ascii=False).encode()).hexdigest(),
        "normalizerSha256": base.digest(Path(__file__).with_name("obligation_overlap_view.py")),
        "experimentRunnerSha256": base.digest(Path(__file__))}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--representation", required=True, choices=["case_local", "obligation_overlap"])
    args = parser.parse_args()
    candidate = "obligation_view_v1_" + args.representation
    return base.main(["--run-root", str(args.run_root), "--policy", "generic",
        "--candidate-id", candidate, "--completion-reserve-seconds", "180"],
        artifact_transform=lambda artifact: stage_view(artifact, args.representation),
        prompt_transform=transform_prompt)


if __name__ == "__main__":
    raise SystemExit(main())
