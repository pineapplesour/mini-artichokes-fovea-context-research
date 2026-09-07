#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
DEFAULT_CODEX_HOME = Path("/home/pineapple/.codex-6")
DEFAULT_MODEL = "gpt-5.6-luna"
DEFAULT_REASONING_EFFORT = "high"
DEFAULT_VERBOSITY = "low"
MASKED_HOST_ROOTS = ("/home", "/mnt", "/root", "/tmp", "/var/tmp")
DISABLED_FEATURES = (
    "apps",
    "browser_use",
    "computer_use",
    "goals",
    "image_generation",
    "memories",
    "multi_agent",
    "multi_agent_v2",
    "plugins",
    "skill_search",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            raise ValueError(f"blank JSONL line {line_number}: {path}")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError(f"non-object JSONL line {line_number}: {path}")
        rows.append(value)
    return rows


def verify_frozen_inputs(*, campaign_dir: Path, role: str) -> dict[str, Any]:
    """Fail closed if any prepared control, input, or implementation changed."""

    role_dir, input_dir, _, payload = role_paths(campaign_dir, role)
    freeze = load_json(role_dir / "freeze.json")

    stored_freeze_hash = str(freeze.get("freezeSha256") or "")
    observed_freeze_hash = canonical_digest({key: value for key, value in freeze.items() if key != "freezeSha256"})
    if not stored_freeze_hash or stored_freeze_hash != observed_freeze_hash:
        raise ValueError(f"{role} freeze self-hash mismatch")

    payload_key = "questionsSha256" if role == "solver" else "gradingPacketSha256"
    expected_payload_hash = str(freeze.get(payload_key) or "")
    if not expected_payload_hash or sha256_file(payload) != expected_payload_hash:
        raise ValueError(f"{role} frozen payload hash mismatch")

    instructions = input_dir / "RUN_INSTRUCTIONS.md"
    expected_instructions_hash = str(freeze.get("instructionsSha256") or "")
    if not expected_instructions_hash or sha256_file(instructions) != expected_instructions_hash:
        raise ValueError(f"{role} frozen instructions hash mismatch")

    expected_payload = load_json(input_dir / "expected_ids.json")
    expected_ids = expected_payload.get("ids")
    if not isinstance(expected_ids, list) or any(not isinstance(case_id, str) or not case_id for case_id in expected_ids):
        raise ValueError(f"{role} expected IDs must be non-empty strings")
    if len(expected_ids) != len(set(expected_ids)) or expected_payload.get("count") != len(expected_ids):
        raise ValueError(f"{role} expected IDs count/uniqueness mismatch")
    payload_rows = load_jsonl(payload)
    payload_ids = [row.get("id") for row in payload_rows]
    if payload_ids != expected_ids:
        raise ValueError(f"{role} expected IDs do not exactly match payload order")
    if canonical_digest(expected_ids) != str(freeze.get("expectedIdsSha256") or ""):
        raise ValueError(f"{role} frozen expected IDs hash mismatch")
    if "expectedIdsFileSha256" in freeze and sha256_file(input_dir / "expected_ids.json") != freeze.get(
        "expectedIdsFileSha256"
    ):
        raise ValueError(f"{role} frozen expected IDs file hash mismatch")

    overlap_path = input_dir / "overlap_manifest.jsonl"
    overlap_rows: list[dict[str, Any]] = []
    eligible_ids: list[str] = []
    eligible_mcq_ids: list[str] = []
    if "overlapManifestSha256" in freeze:
        if not overlap_path.is_file() or sha256_file(overlap_path) != freeze.get("overlapManifestSha256"):
            raise ValueError("solver frozen overlap manifest hash mismatch")
        overlap_rows = load_jsonl(overlap_path)
        overlap_ids = [row.get("id") for row in overlap_rows]
        if overlap_ids != expected_ids:
            raise ValueError("solver overlap manifest IDs do not exactly match payload order")
        eligible_ids = [str(row["id"]) for row in overlap_rows if row.get("eligible") is True]
        formats = {str(row.get("id")): str(row.get("responseFormat") or "") for row in overlap_rows}
        eligible_mcq_ids = [case_id for case_id in eligible_ids if formats.get(case_id) == "mcq"]
        if canonical_digest(eligible_ids) != str(freeze.get("eligibleIdsSha256") or ""):
            raise ValueError("solver frozen eligible IDs hash mismatch")
        if "eligibleMcqIdsSha256" in freeze and canonical_digest(eligible_mcq_ids) != freeze.get("eligibleMcqIdsSha256"):
            raise ValueError("solver frozen eligible MCQ IDs hash mismatch")

    candidate_hashes = freeze.get("candidateAnswersSha256")
    if candidate_hashes is not None:
        if not isinstance(candidate_hashes, dict) or not candidate_hashes:
            raise ValueError("solver candidate answer hashes are malformed")
        observed_candidates: dict[str, str] = {}
        for name, expected_hash in candidate_hashes.items():
            if name not in {"base", "auxiliary_1", "auxiliary_2"}:
                raise ValueError(f"unsupported frozen candidate name: {name!r}")
            candidate_path = input_dir / "candidates" / f"{name}.jsonl"
            if not candidate_path.is_file():
                raise ValueError(f"solver frozen candidate missing: {name}")
            observed_candidates[name] = sha256_file(candidate_path)
            if observed_candidates[name] != expected_hash:
                raise ValueError(f"solver frozen candidate hash mismatch: {name}")
            candidate_ids = [row.get("id") for row in load_jsonl(candidate_path)]
            if candidate_ids != expected_ids:
                raise ValueError(f"solver candidate IDs do not exactly match payload order: {name}")
        if canonical_digest(observed_candidates) != str(freeze.get("candidateBundleSha256") or ""):
            raise ValueError("solver frozen candidate bundle hash mismatch")

    inventory = freeze.get("inventory")
    if isinstance(inventory, dict) and role == "solver":
        observed_inventory = {
            "rows": len(expected_ids),
            "eligibleRows": len(eligible_ids),
            "ineligibleRows": len(expected_ids) - len(eligible_ids),
            "mcqRows": sum(str(row.get("responseFormat") or "") == "mcq" for row in payload_rows),
            "eligibleMcqRows": len(eligible_mcq_ids),
        }
        for key, value in observed_inventory.items():
            if key in inventory and inventory.get(key) != value:
                raise ValueError(f"solver frozen inventory mismatch for {key}")

    provenance = freeze.get("candidateProvenance")
    if freeze.get("protocol") == "mini_artichokes_candidate_overlap_adjudication_v2" and not isinstance(
        provenance, dict
    ):
        raise ValueError("solver v2 campaign requires frozen candidate provenance")
    if provenance is not None:
        if not isinstance(provenance, dict) or canonical_digest(provenance) != freeze.get("candidateProvenanceSha256"):
            raise ValueError("solver frozen candidate provenance digest mismatch")
        if freeze.get("protocol") == "mini_artichokes_candidate_overlap_adjudication_v2" and freeze.get(
            "candidateProvenanceComplete"
        ) is not True:
            raise ValueError("solver v2 campaign requires complete candidate provenance")
        campaign_root = campaign_dir.resolve()
        for name, evidence in provenance.items():
            if not isinstance(evidence, dict) or evidence.get("status") != "accepted":
                raise ValueError(f"solver candidate provenance is not accepted: {name}")
            artifacts = evidence.get("artifacts")
            if not isinstance(artifacts, dict) or not artifacts:
                raise ValueError(f"solver candidate provenance artifacts missing: {name}")
            for artifact_name, artifact in artifacts.items():
                if not isinstance(artifact, dict):
                    raise ValueError(f"solver candidate provenance artifact malformed: {name}/{artifact_name}")
                artifact_path = (campaign_root / str(artifact.get("path") or "")).resolve()
                try:
                    artifact_path.relative_to(campaign_root)
                except ValueError as exc:
                    raise ValueError(f"solver candidate provenance path escapes campaign: {name}/{artifact_name}") from exc
                if not artifact_path.is_file() or sha256_file(artifact_path) != artifact.get("sha256"):
                    raise ValueError(f"solver candidate provenance artifact hash mismatch: {name}/{artifact_name}")

    source_campaign = freeze.get("sourceCampaign")
    if isinstance(source_campaign, str) and source_campaign:
        source_root = Path(source_campaign)
        for field, relative in (
            ("sourceFreezeFileSha256", Path("solver/freeze.json")),
            ("sourceQuestionsSha256", Path("solver/input/questions.jsonl")),
            ("sourceExpectedIdsFileSha256", Path("solver/input/expected_ids.json")),
        ):
            if field in freeze:
                source_path = source_root / relative
                if not source_path.is_file() or sha256_file(source_path) != freeze.get(field):
                    raise ValueError(f"solver source campaign hash mismatch for {field}")

    implementation_hashes = freeze.get("implementationHashes")
    if not isinstance(implementation_hashes, dict) or not implementation_hashes:
        raise ValueError(f"{role} implementation hashes missing")
    for raw_path, expected_hash in implementation_hashes.items():
        implementation_path = Path(str(raw_path))
        if not implementation_path.is_file() or sha256_file(implementation_path) != expected_hash:
            raise ValueError(f"{role} frozen implementation hash mismatch: {implementation_path}")

    if role == "grader" and "answersSha256" in freeze:
        answers_path = campaign_dir / "solver/output/answers.jsonl"
        if not answers_path.is_file() or sha256_file(answers_path) != freeze.get("answersSha256"):
            raise ValueError("grader frozen solver answers hash mismatch")

    return {
        "freezeSha256": stored_freeze_hash,
        "payloadSha256": expected_payload_hash,
        "instructionsSha256": expected_instructions_hash,
        "expectedIdsSha256": freeze.get("expectedIdsSha256"),
        "rows": len(expected_ids),
        "protocol": freeze.get("protocol"),
        "passed": True,
    }


def codex_installation() -> tuple[Path, Path]:
    executable = shutil.which("codex")
    if not executable:
        raise FileNotFoundError("codex executable not found")
    link = Path(executable)
    node_root = link.parent.parent.resolve()
    codex_js = node_root / "lib/node_modules/@openai/codex/bin/codex.js"
    node = node_root / "bin/node"
    if not node.is_file() or not codex_js.is_file():
        raise FileNotFoundError(f"unexpected Codex installation below {node_root}")
    return node_root, codex_js


def role_paths(campaign_dir: Path, role: str) -> tuple[Path, Path, Path, Path]:
    role_dir = campaign_dir / role
    input_dir = role_dir / "input"
    output_dir = role_dir / "output"
    freeze_path = role_dir / "freeze.json"
    if not input_dir.is_dir() or not output_dir.is_dir() or not freeze_path.is_file():
        raise FileNotFoundError(f"prepared {role} bundle is incomplete: {role_dir}")
    instructions = input_dir / "RUN_INSTRUCTIONS.md"
    expected = input_dir / "expected_ids.json"
    if not instructions.is_file() or not expected.is_file():
        raise FileNotFoundError(f"prepared {role} control files are incomplete")
    payload = input_dir / ("questions.jsonl" if role == "solver" else "grading_packet.jsonl")
    if not payload.is_file():
        raise FileNotFoundError(payload)
    return role_dir, input_dir, output_dir, payload


def base_bwrap_command(
    *,
    input_dir: Path,
    output_dir: Path,
    codex_home: Path,
) -> tuple[list[str], Path]:
    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise FileNotFoundError("bubblewrap is required for the public/private visibility boundary")
    auth = codex_home.resolve() / "auth.json"
    if not auth.is_file():
        raise FileNotFoundError(f"Codex auth file missing: {auth}")
    node_root, codex_js = codex_installation()
    command = [
        bwrap,
        "--die-with-parent",
        "--new-session",
        "--unshare-pid",
        "--unshare-ipc",
        "--unshare-uts",
        "--ro-bind",
        "/",
        "/",
    ]
    for root in MASKED_HOST_ROOTS:
        command.extend(["--tmpfs", root])
    wsl_resolver = Path("/mnt/wsl/resolv.conf")
    if wsl_resolver.is_file():
        command.extend(
            [
                "--dir",
                "/mnt/wsl",
                "--ro-bind",
                str(wsl_resolver),
                "/mnt/wsl/resolv.conf",
            ]
        )
    command.extend(
        [
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--dir",
            "/tmp/codex-node",
            "--ro-bind",
            str(node_root),
            "/tmp/codex-node",
            "--dir",
            "/tmp/codex-home",
            "--ro-bind",
            str(auth),
            "/tmp/codex-home/auth.json",
            "--dir",
            "/tmp/work",
            "--dir",
            "/tmp/work/input",
            "--ro-bind",
            str(input_dir.resolve()),
            "/tmp/work/input",
            "--dir",
            "/tmp/work/output",
            "--bind",
            str(output_dir.resolve()),
            "/tmp/work/output",
            "--dir",
            "/tmp/home",
            "--clearenv",
            "--setenv",
            "HOME",
            "/tmp/home",
            "--setenv",
            "CODEX_HOME",
            "/tmp/codex-home",
            "--setenv",
            "PATH",
            "/tmp/codex-node/bin:/usr/local/bin:/usr/bin:/bin",
            "--setenv",
            "LANG",
            "C.UTF-8",
            "--setenv",
            "TMPDIR",
            "/tmp",
            "--setenv",
            "TOKIO_WORKER_THREADS",
            "1",
            "--setenv",
            "RAYON_NUM_THREADS",
            "1",
            "--setenv",
            "UV_THREADPOOL_SIZE",
            "1",
            "--chdir",
            "/tmp/work",
        ]
    )
    return command, codex_js


def codex_command(
    *,
    input_dir: Path,
    output_dir: Path,
    codex_home: Path,
    role: str,
    model: str,
    reasoning_effort: str,
    verbosity: str,
    native_web_search: bool,
) -> list[str]:
    command, codex_js = base_bwrap_command(input_dir=input_dir, output_dir=output_dir, codex_home=codex_home)
    command.extend(
        [
            "/tmp/codex-node/bin/node",
            "/tmp/codex-node/lib/node_modules/@openai/codex/bin/codex.js",
        ]
    )
    if codex_js.name != "codex.js":
        raise ValueError("unexpected Codex entry point")
    if role == "solver" and native_web_search:
        command.append("--search")
    command.extend(
        [
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--sandbox",
            "danger-full-access",
            "--cd",
            "/tmp/work",
            "--model",
            model,
            "--config",
            f'model_reasoning_effort="{reasoning_effort}"',
            "--config",
            f'model_verbosity="{verbosity}"',
            "--config",
            'service_tier="default"',
        ]
    )
    if role == "grader" or not native_web_search:
        command.extend(["--config", 'web_search="disabled"'])
    for feature in DISABLED_FEATURES:
        command.extend(["--config", f"features.{feature}=false"])
    command.extend(
        [
            "--config",
            "features.shell_tool=true",
            "--json",
            "--output-last-message",
            "/tmp/work/output/last_message.txt",
            "-",
        ]
    )
    return command


def isolation_probe(*, input_dir: Path, output_dir: Path, codex_home: Path) -> dict[str, Any]:
    command, _ = base_bwrap_command(input_dir=input_dir, output_dir=output_dir, codex_home=codex_home)
    probe = (
        "test -r /tmp/work/input/RUN_INSTRUCTIONS.md && "
        "test -w /tmp/work/output && "
        "test -r /tmp/codex-home/auth.json && "
        "test ! -e /home/pineapple/bunjum2 && "
        "test ! -e /mnt/d && "
        "test ! -e /root/.codex && "
        "test -s /etc/resolv.conf && "
        "/usr/bin/getent hosts chatgpt.com >/dev/null 2>&1 && "
        "/tmp/codex-node/bin/node /tmp/codex-node/lib/node_modules/@openai/codex/bin/codex.js login status >/dev/null 2>&1 && "
        "/tmp/codex-node/bin/node --version"
    )
    command.extend(["/bin/sh", "-c", probe])
    completed = subprocess.run(command, text=True, capture_output=True, timeout=30, check=False)
    return {
        "passed": completed.returncode == 0,
        "exitCode": completed.returncode,
        "nodeVersion": completed.stdout.strip(),
        "stderr": completed.stderr.strip()[-500:],
        "maskedHostRoots": list(MASKED_HOST_ROOTS),
        "dnsResolution": completed.returncode == 0,
        "publicInputReadOnly": True,
        "outputWritable": True,
    }


def normalize_search_text(text: str) -> str:
    return " ".join(re.findall(r"[0-9A-Za-z가-힣]+", str(text or "").lower()))


def audit_trace(*, trace_path: Path, questions_path: Path, role: str, return_code: int) -> dict[str, Any]:
    from tools.benchmark_provider import _parse_codex_jsonl_trace

    trace = _parse_codex_jsonl_trace(trace_path.read_text(encoding="utf-8"))
    violations: list[str] = []
    if return_code != 0:
        violations.append("codex_process_failed")
    if int(trace.get("codexJsonlEventCount") or 0) <= 0:
        violations.append("codex_trace_missing")
    if int(trace.get("codexJsonlInvalidLineCount") or 0) != 0:
        violations.append("codex_trace_invalid_jsonl")
    usage = trace.get("tokenUsage") if isinstance(trace.get("tokenUsage"), dict) else {}
    if int(usage.get("totalTokens") or 0) <= 0:
        violations.append("positive_token_usage_missing")
    if trace.get("mcpToolEvents"):
        violations.append("mcp_tool_used")
    if trace.get("skillEvents"):
        violations.append("skill_used")
    if role == "grader" and trace.get("webSearchEvents"):
        violations.append("grader_web_used")

    exam_prompts: list[str] = []
    if role == "solver":
        for raw in questions_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(raw)
            if row.get("suite") == "exam":
                exam_prompts.append(normalize_search_text(str(row.get("prompt") or "")))
    forbidden_names = (
        "answer key",
        "mark scheme",
        "quizlet",
        "coursehero",
        "aqa 8062",
        "cambridge 2068 specimen",
        "byu islam multiple choice quiz",
        "leet 2026 정답",
        "국시원 81회 정답",
        "benchmark answer",
    )
    for event in trace.get("webSearchEvents", []):
        query = normalize_search_text(str(event.get("query") or ""))
        if any(name in query for name in forbidden_names):
            violations.append("forbidden_exam_or_answer_search")
        if len(query) >= 24 and any(query in prompt for prompt in exam_prompts):
            violations.append("exact_or_near_exact_exam_text_search")
    command_events = trace.get("commandExecutionEvents") if isinstance(trace.get("commandExecutionEvents"), list) else []
    for event in command_events:
        command = str(event.get("command") or "")
        if re.search(r"(?:^|\s)(?:/home|/mnt|/root)(?:/|\s|$)", command) or "../" in command:
            violations.append("shell_attempted_masked_host_path")
    return {
        "policy": "isolated_one_agent_file_benchmark_v1",
        "passed": not violations,
        "violations": list(dict.fromkeys(violations)),
        "trace": trace,
    }


def validate_solver_artifact(
    campaign_dir: Path,
    *,
    freeze: dict[str, Any],
    write_report: bool = True,
) -> dict[str, Any]:
    protocol = str(freeze.get("protocol") or "")
    if protocol == "mini_artichokes_candidate_overlap_adjudication_v2":
        from tools.validate_overlap_adjudication import validate_overlap_adjudication

        return validate_overlap_adjudication(campaign_dir, write_report=write_report)
    from tools.prepare_plain_codex_file_benchmark import validate_answers

    return validate_answers(campaign_dir, write_report=write_report)


def existing_valid_result(campaign_dir: Path, role: str, *, freeze: dict[str, Any]) -> bool:
    receipt_path = campaign_dir / role / "run_receipt.json"
    if not receipt_path.is_file():
        return False
    receipt = load_json(receipt_path)
    if receipt.get("status") != "accepted" or receipt.get("freezeSha256") != freeze.get("freezeSha256"):
        return False
    stored_digest = str(receipt.get("receiptSha256") or "")
    digest_payload = {key: value for key, value in receipt.items() if key != "receiptSha256"}
    observed_digest = hashlib.sha256(
        json.dumps(digest_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if not stored_digest or stored_digest != observed_digest:
        return False
    if role == "solver":
        validation = validate_solver_artifact(campaign_dir, freeze=freeze, write_report=False)
        return bool(
            validation.get("passed")
            and validation.get("answersSha256") == receipt.get("artifactValidation", {}).get("answersSha256")
        )
    from tools.prepare_plain_codex_file_benchmark import validate_grades

    validation = validate_grades(campaign_dir, write_report=False)
    return bool(
        validation.get("passed")
        and validation.get("gradesSha256") == receipt.get("artifactValidation", {}).get("gradesSha256")
    )


def run_agent(
    *,
    campaign_dir: Path,
    role: str,
    codex_home: Path,
    model: str,
    reasoning_effort: str,
    verbosity: str,
    timeout_seconds: int,
    resume: bool,
) -> dict[str, Any]:
    role_dir, input_dir, output_dir, payload = role_paths(campaign_dir, role)
    integrity = verify_frozen_inputs(campaign_dir=campaign_dir, role=role)
    freeze = load_json(role_dir / "freeze.json")
    expected_payload_hash = integrity["payloadSha256"]
    expected_config = freeze.get("executionConfig") if isinstance(freeze.get("executionConfig"), dict) else {}
    observed_config = {"model": model, "reasoningEffort": reasoning_effort, "verbosity": verbosity}
    for key, value in observed_config.items():
        if expected_config.get(key) != value:
            raise ValueError(f"{role} execution config mismatch for {key}: expected {expected_config.get(key)!r}, got {value!r}")
    if expected_config.get("serviceTier") != "default":
        raise ValueError(f"{role} execution config must freeze serviceTier='default'")
    native_web_search = expected_config.get("nativeWebSearch")
    if not isinstance(native_web_search, bool):
        raise ValueError(f"{role} execution config must freeze nativeWebSearch as a boolean")
    if resume and existing_valid_result(campaign_dir, role, freeze=freeze):
        return {"status": "resumed_complete_without_model_call", "role": role, "modelCalls": 0}
    final_name = "answers.jsonl" if role == "solver" else "grades.jsonl"
    if any(output_dir.iterdir()):
        raise FileExistsError(
            f"refusing to overwrite existing {role} output; use --resume only for an already complete exact freeze "
            f"or prepare a new campaign directory: {output_dir}"
        )
    probe = isolation_probe(input_dir=input_dir, output_dir=output_dir, codex_home=codex_home)
    if not probe["passed"]:
        raise RuntimeError(f"isolation probe failed: {probe}")
    command = codex_command(
        input_dir=input_dir,
        output_dir=output_dir,
        codex_home=codex_home,
        role=role,
        model=model,
        reasoning_effort=reasoning_effort,
        verbosity=verbosity,
        native_web_search=native_web_search,
    )
    trace_path = role_dir / "codex_trace.jsonl"
    stderr_path = role_dir / "codex_stderr.txt"
    prompt = "Read input/RUN_INSTRUCTIONS.md completely, obey it, process the complete input file, and produce the required final output file."
    started = time.monotonic()
    timed_out = False
    with trace_path.open("w", encoding="utf-8") as trace_stream, stderr_path.open("w", encoding="utf-8") as stderr_stream:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=trace_stream,
            stderr=stderr_stream,
            text=True,
            start_new_session=True,
        )
        assert process.stdin is not None
        process.stdin.write(prompt)
        process.stdin.close()
        try:
            return_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                return_code = process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                return_code = process.wait(timeout=15)
    elapsed = round(time.monotonic() - started, 3)
    audit = audit_trace(trace_path=trace_path, questions_path=payload, role=role, return_code=return_code)
    if timed_out:
        audit["violations"].append("codex_process_timeout")
        audit["passed"] = False
    if role == "solver":
        artifact = validate_solver_artifact(campaign_dir, freeze=freeze)
    else:
        from tools.prepare_plain_codex_file_benchmark import validate_grades

        artifact = validate_grades(campaign_dir)
    receipt = {
        "schemaVersion": 1,
        "status": "accepted" if audit["passed"] and artifact["passed"] else "incomplete",
        "role": role,
        "semanticModelInvocations": 1,
        "model": model,
        "reasoningEffort": reasoning_effort,
        "verbosity": verbosity,
        "freezeSha256": freeze.get("freezeSha256"),
        "payloadSha256": expected_payload_hash,
        "inputIntegrity": integrity,
        "isolationProbe": probe,
        "process": {"exitCode": return_code, "timedOut": timed_out, "elapsedSec": elapsed},
        "policyAudit": audit,
        "artifactValidation": artifact,
        "acceptedArtifact": final_name if artifact["passed"] else None,
    }
    receipt["receiptSha256"] = hashlib.sha256(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    write_json(role_dir / "run_receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one isolated Codex agent over the complete file benchmark.")
    parser.add_argument("role", choices=["solver", "grader"])
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--codex-home", type=Path, default=DEFAULT_CODEX_HOME)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--reasoning-effort", default=DEFAULT_REASONING_EFFORT)
    parser.add_argument("--verbosity", default=DEFAULT_VERBOSITY)
    parser.add_argument("--timeout-seconds", type=int, default=21_600)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    campaign = args.campaign_dir.resolve()
    _, input_dir, output_dir, _ = role_paths(campaign, args.role)
    if args.dry_run:
        integrity = verify_frozen_inputs(campaign_dir=campaign, role=args.role)
        freeze = load_json(campaign / args.role / "freeze.json")
        expected_config = freeze.get("executionConfig") if isinstance(freeze.get("executionConfig"), dict) else {}
        native_web_search = expected_config.get("nativeWebSearch")
        if not isinstance(native_web_search, bool):
            raise ValueError(f"{args.role} execution config must freeze nativeWebSearch as a boolean")
        probe = isolation_probe(input_dir=input_dir, output_dir=output_dir, codex_home=args.codex_home)
        command = codex_command(
            input_dir=input_dir,
            output_dir=output_dir,
            codex_home=args.codex_home,
            role=args.role,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            verbosity=args.verbosity,
            native_web_search=native_web_search,
        )
        result = {
            "status": "dry_run_no_model_calls",
            "role": args.role,
            "isolationProbe": probe,
            "model": args.model,
            "reasoningEffort": args.reasoning_effort,
            "semanticModelInvocationsPlanned": 1,
            "commandArgumentCount": len(command),
            "inputIntegrity": integrity,
        }
    else:
        result = run_agent(
            campaign_dir=campaign,
            role=args.role,
            codex_home=args.codex_home,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            verbosity=args.verbosity,
            timeout_seconds=args.timeout_seconds,
            resume=args.resume,
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("status") not in {"incomplete", "unresolved"} and result.get("isolationProbe", {}).get("passed", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
