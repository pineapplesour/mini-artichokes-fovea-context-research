#!/usr/bin/env python3
"""Run an anonymous multiway judge on exposed legal-development disagreements."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

try:
    from tools import run_batched_structured_legal_dev as dev_runner
    from tools import score_batched_structured_legal_dev as scorer
except ImportError:
    import run_batched_structured_legal_dev as dev_runner
    import score_batched_structured_legal_dev as scorer


ORDER_DOMAIN = b"mini-legal-multiway-judge-dev-v1\0"
ORDER_SEED = b"fixed-anonymous-order-2026-09-01"


def schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["decisions"],
        "properties": {
            "decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["id", "selected", "reason"],
                    "properties": {
                        "id": {"type": "string"},
                        "selected": {"type": "string", "enum": ["C1", "C2", "C3", "C4"]},
                        "reason": {"type": "string", "minLength": 1, "maxLength": 900},
                    },
                },
            }
        },
    }


def anonymous_order(case_id: str, names: list[str]) -> list[str]:
    return sorted(
        names,
        key=lambda name: hashlib.sha256(
            ORDER_DOMAIN + ORDER_SEED + b"\0" + case_id.encode() + b"\0" + name.encode()
        ).digest(),
    )


def build_packets(
    public_path: Path,
    draw_root: Path,
    mode: str,
    draw_names: tuple[str, ...] = ("D1", "D2", "D3"),
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    public_rows = scorer.load_jsonl(public_path)
    public_by_id = {row["id"]: row for row in public_rows}
    draws = {name: scorer.load_draw(draw_root, name, public_by_id) for name in draw_names}
    packets: list[dict[str, Any]] = []
    role_map: list[dict[str, Any]] = []
    for row in public_rows:
        case_id = row["id"]
        available = [name for name in draw_names if scorer.outcome(draws[name][case_id])]
        if len({scorer.outcome(draws[name][case_id]) for name in available}) < 2:
            continue
        ordered = anonymous_order(case_id, available)
        candidates = []
        key_to_draw: dict[str, str] = {}
        for index, name in enumerate(ordered, 1):
            key = f"C{index}"
            prediction = draws[name][case_id]
            candidates.append(
                {
                    "candidateKey": key,
                    "outcome": prediction["outcome"],
                    "rationale": prediction.get("rationale", ""),
                    "evidenceAtoms": prediction.get("evidenceAtoms", []),
                }
            )
            key_to_draw[key] = name
        packet: dict[str, Any] = {"id": case_id, "case": row["prompt"], "candidates": candidates}
        if mode == "overlap":
            signals = []
            for left_index, left in enumerate(candidates):
                left_prediction = draws[key_to_draw[left["candidateKey"]]][case_id]
                for right in candidates[left_index + 1 :]:
                    right_prediction = draws[key_to_draw[right["candidateKey"]]][case_id]
                    shared = sorted(
                        scorer.atom_keys(left_prediction, "clause_direction")
                        & scorer.atom_keys(right_prediction, "clause_direction")
                    )
                    if left["outcome"] == right["outcome"] and shared:
                        signals.append(
                            {
                                "candidateKeys": [left["candidateKey"], right["candidateKey"]],
                                "outcome": left["outcome"],
                                "sharedClauseDirection": [list(key) for key in shared],
                            }
                        )
            packet["mechanicalOverlapSignals"] = signals
        packets.append(packet)
        role_map.append({"id": case_id, "candidateKeyToDraw": key_to_draw})
    return packets, role_map


def prompt_for(packets: list[dict[str, Any]], mode: str) -> str:
    extra = ""
    if mode == "overlap":
        extra = """
각 mechanicalOverlapSignals는 두 익명 후보가 같은 결과와 같은 번호 근거절 방향을 낸 경우만 기계적으로 표시합니다.
이는 상관된 오답일 수 있으므로 독립 증명이 아니며, 실제 사건 내용이 지지할 때만 판단 보조로 사용하십시오.
신호가 없거나 잘못된 경우에도 가장 타당한 기존 후보를 고르십시오.
"""
    return f"""당신은 대한민국 제1심 사건 결과를 비교하는 출처 맹검 판정자입니다.
각 사건의 익명 후보 C1~C3 중 공개된 청구취지·기초사실과 가장 잘 맞는 정확히 하나를 선택하십시오.
후보 순서와 생성 역할은 무작위로 숨겨졌습니다. 다수결이나 순서를 정답으로 간주하지 마십시오.
청구가 일부라도 받아들여지면 인용됨, 전부 배척되면 기각입니다.
각 후보의 논거와 번호 근거절을 실제 사건에 대조하고, 당사자·청구원인·손해·절차 연결의 누락과 허구를 확인하십시오.
새 답을 만들지 말고 반드시 제공된 candidateKey 하나를 선택하십시오.{extra}
도구·웹·파일·정답 검색 없이 각 ID를 입력 순서대로 한 번씩 JSON schema로만 반환하십시오.

입력 사건 JSON:
{json.dumps(packets, ensure_ascii=False, separators=(",", ":"))}
"""


def validate_by_id(value: Any, packets: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    expected = {row["id"]: {candidate["candidateKey"] for candidate in row["candidates"]} for row in packets}
    valid: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    decisions = value.get("decisions", []) if isinstance(value, dict) else []
    if not isinstance(decisions, list):
        return [], ["invalid_top_level"]
    for row in decisions:
        if not isinstance(row, dict) or set(row) != {"id", "selected", "reason"}:
            errors.append("invalid_row_schema")
            continue
        case_id = row["id"]
        if case_id not in expected or case_id in valid:
            errors.append(f"unexpected_or_duplicate:{case_id}")
            continue
        if row["selected"] not in expected[case_id] or not isinstance(row["reason"], str) or not row["reason"]:
            errors.append(f"invalid_value:{case_id}")
            continue
        valid[case_id] = row
    missing = [row["id"] for row in packets if row["id"] not in valid]
    errors.extend(f"missing:{case_id}" for case_id in missing)
    return [valid[row["id"]] for row in packets if row["id"] in valid], errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--draw-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=("generic", "overlap"), required=True)
    parser.add_argument("--model", default=dev_runner.MODEL)
    parser.add_argument("--draw-count", type=int, choices=(3, 4), default=3)
    parser.add_argument("--max-items", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    draw_names = tuple(f"D{index}" for index in range(1, args.draw_count + 1))
    packets, role_map = build_packets(args.public, args.draw_root, args.mode, draw_names)
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite nonempty output: {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    role_by_id = {row["id"]: row for row in role_map}
    for shard_index, start in enumerate(range(0, len(packets), args.max_items)):
        shard = packets[start : start + args.max_items]
        shard_dir = args.output_dir / f"shard_{shard_index:04d}"
        shard_dir.mkdir(parents=True)
        prompt = prompt_for(shard, args.mode)
        prompt_path, schema_path = shard_dir / "prompt.txt", shard_dir / "schema.json"
        response_path = shard_dir / "response.json"
        prompt_path.write_text(prompt, encoding="utf-8")
        schema_path.write_bytes(dev_runner.canonical_bytes(schema()))
        with tempfile.TemporaryDirectory(prefix="mini-multiway-judge-") as temporary:
            command = dev_runner.command(schema_path.resolve(), response_path.resolve(), Path(temporary))
            command[command.index("--model") + 1] = args.model
            result = subprocess.run(
                command, input=prompt.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env={"PATH": os.environ["PATH"], "CODEX_HOME": str(dev_runner.CODEX_HOME)},
                timeout=args.timeout, check=False,
            )
        (shard_dir / "trace.jsonl").write_bytes(result.stdout)
        (shard_dir / "stderr.txt").write_bytes(result.stderr)
        value: Any = {}
        if result.returncode == 0 and response_path.is_file():
            value = json.loads(response_path.read_text(encoding="utf-8"))
        valid, errors = validate_by_id(value, shard)
        (shard_dir / "normalized.json").write_bytes(dev_runner.canonical_bytes(valid))
        (shard_dir / "hidden-role-map.json").write_bytes(
            dev_runner.canonical_bytes([role_by_id[row["id"]] for row in shard])
        )
        receipt = {
            "protocol": "mini_artichokes_multiway_legal_judge_dev_v1",
            "developmentOnly": True,
            "mode": args.mode,
            "model": args.model,
            "drawCount": args.draw_count,
            "shard": shard_index,
            "ids": [row["id"] for row in shard],
            "validRows": len(valid),
            "errors": errors,
            "semanticAttempts": 1,
            "tokenUsage": dev_runner.token_usage(result.stdout),
        }
        (shard_dir / "receipt.json").write_bytes(dev_runner.canonical_bytes(receipt))
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True), flush=True)
    print(json.dumps({"mode": args.mode, "model": args.model, "drawCount": args.draw_count, "conflicts": len(packets)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
