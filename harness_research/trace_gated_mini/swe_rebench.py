"""Materialize history-free SWE-rebench V2 instances.

Only the issue, base tree, and public regression command enter the agent-facing
snapshot. The dataset's test patch is written under a separate private runtime
directory for post-selection evaluation. The gold solution patch is never
persisted by this tool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path


DATASET = "nebius/SWE-rebench-V2"
DATASET_SERVER = "https://datasets-server.huggingface.co/filter"


def fetch_instance(instance_id: str, retries: int = 5) -> dict[str, object]:
    where = f'"instance_id"=\'{instance_id}\''
    params = urllib.parse.urlencode(
        {"dataset": DATASET, "config": "default", "split": "train", "where": where, "offset": 0, "length": 2}
    )
    error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(f"{DATASET_SERVER}?{params}", timeout=45) as response:
                payload = json.load(response)
            rows = [entry["row"] for entry in payload.get("rows", [])]
            if len(rows) != 1:
                raise RuntimeError(f"expected one row for {instance_id}, received {len(rows)}")
            return rows[0]
        except Exception as exc:  # the public dataset index is intermittently slow
            error = exc
            if attempt + 1 < retries:
                time.sleep(min(2 ** attempt, 8))
    raise RuntimeError(f"failed to fetch {instance_id}: {error}")


def run(argv: list[str], *, cwd: Path | None = None, stdin: bytes | None = None, timeout: int = 300) -> bytes:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"command failed ({completed.returncode}): {argv}\n{completed.stderr.decode(errors='replace')}")
    return completed.stdout


def ensure_upstream(repo: str, cache_root: Path) -> Path:
    destination = cache_root / repo.replace("/", "__")
    if not (destination / ".git").is_dir():
        destination.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--filter=blob:none", "--no-checkout", f"https://github.com/{repo}.git", str(destination)], timeout=900)
    return destination


def materialize(instance_id: str, output_dir: Path, cache_root: Path) -> dict[str, object]:
    if output_dir.exists():
        raise FileExistsError(output_dir)
    row = fetch_instance(instance_id)
    repo = str(row["repo"])
    base_commit = str(row["base_commit"])
    upstream = ensure_upstream(repo, cache_root)
    run(["git", "fetch", "--quiet", "origin", base_commit], cwd=upstream, timeout=900)

    source = output_dir / "source"
    public = output_dir / "public"
    private = output_dir / "private"
    source.mkdir(parents=True)
    public.mkdir()
    private.mkdir()
    archive = run(["git", "archive", "--format=tar", base_commit], cwd=upstream, timeout=300)
    run(["tar", "-xf", "-", "-C", str(source)], stdin=archive, timeout=300)
    run(["git", "init", "--quiet"], cwd=source)
    run(["git", "config", "user.name", "pineapple-benchmark"], cwd=source)
    run(["git", "config", "user.email", "benchmark@invalid.local"], cwd=source)
    run(["git", "add", "."], cwd=source)
    run(["git", "commit", "--quiet", "-m", f"History-free snapshot for {instance_id}"], cwd=source)
    snapshot_commit = run(["git", "rev-parse", "HEAD"], cwd=source).decode().strip()
    snapshot_tree = run(["git", "rev-parse", "HEAD^{tree}"], cwd=source).decode().strip()

    install_config = row.get("install_config") or {}
    evaluation_test_command = str(install_config.get("test_cmd") or "").strip()
    if not evaluation_test_command:
        raise RuntimeError(f"missing test command for {instance_id}")
    public_test_command = build_python_public_test_command(
        row.get("PASS_TO_PASS") or [],
        fallback=evaluation_test_command,
    )
    problem = str(row.get("problem_statement") or "").strip()
    instruction = (
        f"{problem}\n\n"
        "Work only from the checked-out repository and this issue. Do not look up the issue, pull request, benchmark "
        "instance, or a solution on the web. Preserve compatibility and make the smallest complete repair. "
        "Test files are evaluator-owned: do not create, delete, or modify tests. "
        f"The public regression command is:\n{public_test_command}"
    )
    task = {
        "task_id": instance_id,
        "instruction": instruction,
        "base_ref": snapshot_commit,
        "public_test_command": public_test_command,
        "forbidden_path_globs": [
            ".git/*",
            ".mini_evaluation/*",
            "test_*.py",
            "*_test.py",
            "tests/*",
            "**/tests/*",
            "**/test_*.py",
            "**/*_test.py"
        ],
    }
    (public / "task.json").write_text(json.dumps(task, indent=2), encoding="utf-8")

    evaluation_patch = str(row.get("test_patch") or "")
    if not evaluation_patch:
        raise RuntimeError(f"missing evaluation patch for {instance_id}")
    evaluation_path = private / "evaluation.patch"
    evaluation_path.write_text(evaluation_patch, encoding="utf-8")

    llm_meta = ((row.get("meta") or {}).get("llm_metadata") or {})
    metadata = {
        "schema_version": 1,
        "dataset": DATASET,
        "instance_id": instance_id,
        "repo": repo,
        "original_base_commit": base_commit,
        "history_free_snapshot_commit": snapshot_commit,
        "history_free_snapshot_tree": snapshot_tree,
        "created_at": row.get("created_at"),
        "license": row.get("license"),
        "fail_to_pass": row.get("FAIL_TO_PASS"),
        "pass_to_pass_count": len(row.get("PASS_TO_PASS") or []),
        "install_commands": install_config.get("install"),
        "public_test_command": public_test_command,
        "evaluation_test_command": evaluation_test_command,
        "difficulty": llm_meta.get("difficulty"),
        "quality_code": llm_meta.get("code"),
        "quality_confidence": llm_meta.get("confidence"),
        "evaluation_patch_sha256": sha256_text(evaluation_patch),
        "gold_solution_persisted": False,
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def build_python_public_test_command(pass_to_pass: list[str], fallback: str) -> str:
    """Build a verifier from tests guaranteed not to encode the new behavior.

    SWE-rebench test patches sometimes modify an existing test whose old
    expectation conflicts with the issue. Running the whole pre-patch file can
    therefore reject a correct candidate. PASS_TO_PASS IDs are the proper
    agent-visible regression set; FAIL_TO_PASS remains evaluation-only.
    """

    if not pass_to_pass or not fallback.lstrip().startswith(("pytest ", "python -m pytest ")):
        return fallback
    prefix = (
        "python -m pytest --no-header -q --tb=line --color=no "
        "-p no:cacheprovider -W ignore::DeprecationWarning"
    )
    return prefix + " " + " ".join(shlex.quote(test_id) for test_id in pass_to_pass)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--cache-root", required=True, type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    metadata = materialize(args.instance_id, args.output_dir.resolve(), args.cache_root.resolve())
    print(json.dumps(metadata))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
