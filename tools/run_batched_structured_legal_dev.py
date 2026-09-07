#!/usr/bin/env python3
"""Run the exposed 180-case legal development set in small Luna batches.

This is deliberately a development-only runner.  It reduces call overhead while
keeping D1/D2/D3 in separate Codex processes.  Fresh confirmation remains
case-singleton.  A completed shard is never called again; invalid rows remain
null for full-denominator scoring.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
CODEX_HOME = Path("/home/pineapple/.codex-new-account")
MODEL = "gpt-5.6-luna"
OUTCOMES = {"인용됨", "기각", "ABSTAIN"}
ISSUE_CODES = {
    "REQUIRED_ELEMENT_PRESENT",
    "REQUIRED_ELEMENT_ABSENT",
    "RULE_OR_EXCEPTION_APPLIES",
    "BURDEN_OR_STANDARD_MET",
    "BURDEN_OR_STANDARD_NOT_MET",
    "REMEDY_OR_PROCEDURE_CONTROLS",
    "RECORD_CONTRADICTION",
    "UNSUPPORTED_INFERENCE",
}
DIRECTIONS = {"FAVORS_GRANT", "FAVORS_DISMISS"}
CLAUSE_RE = re.compile(r"^\[([CF]\d{3})\]\s+(.+)$", re.MULTILINE)


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{number}: row is not an object")
        rows.append(value)
    return rows


def make_shards(rows: list[dict[str, Any]], *, max_items: int, max_chars: int) -> list[list[dict[str, Any]]]:
    shards: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_chars = 0
    for row in rows:
        size = len(str(row.get("prompt", "")))
        if current and (len(current) >= max_items or current_chars + size > max_chars):
            shards.append(current)
            current = []
            current_chars = 0
        current.append(row)
        current_chars += size
    if current:
        shards.append(current)
    return shards


def output_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["predictions"],
        "properties": {
            "predictions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["id", "outcome", "rationale", "evidenceAtoms"],
                    "properties": {
                        "id": {"type": "string"},
                        "outcome": {"type": "string", "enum": sorted(OUTCOMES)},
                        "rationale": {"type": "string", "minLength": 1, "maxLength": 700},
                        "evidenceAtoms": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 2,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["issueCode", "clauseId", "direction"],
                                "properties": {
                                    "issueCode": {"type": "string", "enum": sorted(ISSUE_CODES)},
                                    "clauseId": {"type": "string", "pattern": "^[CF][0-9]{3}$"},
                                    "direction": {"type": "string", "enum": sorted(DIRECTIONS)},
                                },
                            },
                        },
                    },
                },
            }
        },
    }


def prompt_for(rows: list[dict[str, Any]], draw: str) -> str:
    packets = [{"id": row["id"], "case": row["prompt"]} for row in rows]
    return f"""당신은 대한민국 제1심 사건 결과를 예측하는 독립 분석자 {draw}입니다.
각 사건은 다른 사건과 독립적으로 판단하십시오. 정답, 주문, 다른 분석자의 답은 제공되지 않습니다.
각 사건마다 인용됨/기각/ABSTAIN 중 하나를 고르고, 가장 결정적인 번호 근거절 1~2개를 선택하십시오.
근거절 ID는 사건 본문에 실제 존재하는 [Cnnn] 또는 [Fnnn]만 사용할 수 있습니다.
인용됨이면 모든 atom direction은 FAVORS_GRANT, 기각이면 FAVORS_DISMISS여야 합니다.
ABSTAIN은 자료만으로 어느 쪽도 지지할 수 없을 때만 쓰고, 가장 중요한 결여 절을 고르십시오.
issueCode는 허용 enum 중 의미가 가장 가까운 하나를 고르십시오. 다른 사건의 사실을 섞지 마십시오.
도구·웹·파일을 사용하지 말고 JSON schema만 정확히 반환하십시오.

입력 사건 JSON:
{json.dumps(packets, ensure_ascii=False, separators=(",", ":"))}
"""


def command(schema_path: Path, response_path: Path, work_dir: Path) -> list[str]:
    disabled = (
        "apps", "browser_use", "browser_use_external", "browser_use_full_cdp_access",
        "code_mode", "code_mode_host", "computer_use", "enable_mcp_apps", "image_generation",
        "mcp_2026_07_28", "multi_agent", "multi_agent_v2", "plugins", "remote_plugin",
        "shell_tool", "skill_search", "tool_suggest", "unified_exec", "view_image",
    )
    args = [
        "codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
        "--strict-config", "--skip-git-repo-check", "--sandbox", "read-only",
        "--cd", str(work_dir), "--model", MODEL,
        "--config", 'model_reasoning_effort="high"',
        "--config", 'model_verbosity="low"',
        "--config", 'service_tier="default"',
        "--config", 'web_search="disabled"',
    ]
    for feature in disabled:
        args.extend(("--config", f"features.{feature}=false"))
    args.extend(("--json", "--output-schema", str(schema_path), "--output-last-message", str(response_path), "-"))
    return args


def validate_response(value: Any, rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any] | None], list[str]]:
    errors: list[str] = []
    if not isinstance(value, dict) or set(value) != {"predictions"} or not isinstance(value["predictions"], list):
        return [None] * len(rows), ["invalid_top_level_schema"]
    predictions = value["predictions"]
    expected = [str(row["id"]) for row in rows]
    observed = [item.get("id") if isinstance(item, dict) else None for item in predictions]
    if observed != expected:
        return [None] * len(rows), ["id_or_order_mismatch"]
    normalized: list[dict[str, Any] | None] = []
    for row, item in zip(rows, predictions, strict=True):
        item_errors: list[str] = []
        if not isinstance(item, dict) or set(item) != {"id", "outcome", "rationale", "evidenceAtoms"}:
            normalized.append(None)
            errors.append(f"{row['id']}:invalid_row_schema")
            continue
        outcome = item["outcome"]
        atoms = item["evidenceAtoms"]
        rationale = item["rationale"]
        clauses = {match.group(1) for match in CLAUSE_RE.finditer(str(row["prompt"]))}
        if outcome not in OUTCOMES:
            item_errors.append("invalid_outcome")
        if not isinstance(rationale, str) or not (1 <= len(rationale) <= 700):
            item_errors.append("invalid_rationale")
        if not isinstance(atoms, list) or not (1 <= len(atoms) <= 2):
            item_errors.append("invalid_atom_count")
            atoms = []
        seen: set[tuple[str, str, str]] = set()
        for atom in atoms:
            if not isinstance(atom, dict) or set(atom) != {"issueCode", "clauseId", "direction"}:
                item_errors.append("invalid_atom_schema")
                continue
            key = (atom["issueCode"], atom["clauseId"], atom["direction"])
            if atom["issueCode"] not in ISSUE_CODES or atom["clauseId"] not in clauses or atom["direction"] not in DIRECTIONS:
                item_errors.append("invalid_atom_value")
            if key in seen:
                item_errors.append("duplicate_atom")
            seen.add(key)
            if outcome == "인용됨" and atom["direction"] != "FAVORS_GRANT":
                item_errors.append("direction_outcome_mismatch")
            if outcome == "기각" and atom["direction"] != "FAVORS_DISMISS":
                item_errors.append("direction_outcome_mismatch")
        if item_errors:
            errors.extend(f"{row['id']}:{error}" for error in sorted(set(item_errors)))
            normalized.append(None)
        else:
            normalized.append(item)
    return normalized, errors


def token_usage(trace: bytes) -> dict[str, int] | None:
    usage = None
    for line in trace.splitlines():
        try:
            event = json.loads(line)
        except Exception:
            continue
        if isinstance(event, dict) and event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            usage = event["usage"]
    return usage


def write_exclusive(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(payload)


def run_draw(*, rows: list[dict[str, Any]], output_dir: Path, draw: str, max_items: int, max_chars: int, timeout: int) -> None:
    shards = make_shards(rows, max_items=max_items, max_chars=max_chars)
    output_dir.mkdir(parents=True, exist_ok=True)
    for index, shard in enumerate(shards):
        shard_dir = output_dir / draw / f"shard_{index:04d}"
        receipt_path = shard_dir / "receipt.json"
        if receipt_path.exists():
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            if receipt.get("status") in {"accepted", "rejected"}:
                print(json.dumps({"draw": draw, "shard": index, "status": "resume_no_call"}, sort_keys=True), flush=True)
                continue
            raise RuntimeError(f"unrecognized existing receipt: {receipt_path}")
        shard_dir.mkdir(parents=True, exist_ok=True)
        prompt = prompt_for(shard, draw)
        prompt_path = shard_dir / "prompt.txt"
        schema_path = shard_dir / "schema.json"
        response_path = shard_dir / "response.json"
        trace_path = shard_dir / "trace.jsonl"
        write_exclusive(prompt_path, prompt.encode("utf-8"))
        write_exclusive(schema_path, canonical_bytes(output_schema()))
        with tempfile.TemporaryDirectory(prefix="mini-dev-") as temporary:
            work_dir = Path(temporary)
            env = {"PATH": os.environ["PATH"], "CODEX_HOME": str(CODEX_HOME)}
            result = subprocess.run(
                command(schema_path.resolve(), response_path.resolve(), work_dir),
                input=prompt.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=env, timeout=timeout, check=False,
            )
        write_exclusive(trace_path, result.stdout)
        write_exclusive(shard_dir / "stderr.txt", result.stderr)
        errors: list[str] = []
        normalized: list[dict[str, Any] | None] = [None] * len(shard)
        if result.returncode != 0:
            errors.append(f"returncode_{result.returncode}")
        elif not response_path.is_file():
            errors.append("missing_response")
        else:
            try:
                value = json.loads(response_path.read_text(encoding="utf-8"))
                normalized, errors = validate_response(value, shard)
            except Exception as exc:
                errors.append(f"response_parse:{type(exc).__name__}")
        normalized_rows = [
            {"id": row["id"], "prediction": prediction}
            for row, prediction in zip(shard, normalized, strict=True)
        ]
        write_exclusive(shard_dir / "normalized.json", canonical_bytes(normalized_rows))
        receipt = {
            "protocol": "mini_artichokes_batched_structured_legal_dev_v1",
            "developmentOnly": True,
            "draw": draw,
            "shard": index,
            "ids": [row["id"] for row in shard],
            "promptSha256": sha256_file(prompt_path),
            "responseSha256": sha256_file(response_path) if response_path.is_file() else None,
            "traceSha256": sha256_file(trace_path),
            "normalizedSha256": sha256_file(shard_dir / "normalized.json"),
            "status": "accepted" if not errors else "rejected",
            "validRows": sum(item is not None for item in normalized),
            "errors": errors,
            "tokenUsage": token_usage(result.stdout),
            "semanticAttempts": 1,
        }
        receipt["receiptSha256"] = sha256_bytes(canonical_bytes(receipt))
        write_exclusive(receipt_path, canonical_bytes(receipt))
        print(json.dumps({"draw": draw, "shard": index, "status": receipt["status"], "validRows": receipt["validRows"], "tokens": receipt["tokenUsage"]}, ensure_ascii=False, sort_keys=True), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--draw", action="append", choices=("D1", "D2", "D3", "D4"), required=True)
    parser.add_argument("--max-items", type=int, default=8)
    parser.add_argument("--max-chars", type=int, default=80000)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    rows = load_jsonl(args.public)
    if len(rows) != 180 or len({row.get("id") for row in rows}) != 180:
        raise ValueError("development public input must contain exactly 180 unique IDs")
    for draw in args.draw:
        run_draw(rows=rows, output_dir=args.output_dir, draw=draw, max_items=args.max_items, max_chars=args.max_chars, timeout=args.timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
