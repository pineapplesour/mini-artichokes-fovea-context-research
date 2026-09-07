#!/usr/bin/env python3
"""Run one provenance-blind veto call on exposed legal development conflicts."""
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
except ImportError:  # Direct `python tools/run_...py` execution.
    import run_batched_structured_legal_dev as dev_runner
    import score_batched_structured_legal_dev as scorer


ROTATION_DOMAIN = b"mini-legal-overlap-blind-veto-dev-v1\0"
ROTATION_SEED = b"exposed-development-2026-09-01"
PREFERENCES = {"LEFT", "RIGHT", "TIE"}


def rotate(case_id: str, incumbent: str, proposal: str) -> tuple[str, str, str]:
    bit = hashlib.sha256(ROTATION_DOMAIN + ROTATION_SEED + b"\0" + case_id.encode()).digest()[0] & 1
    if bit == 0:
        return incumbent, proposal, "LEFT"
    return proposal, incumbent, "RIGHT"


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
                    "required": ["id", "preference", "reason"],
                    "properties": {
                        "id": {"type": "string"},
                        "preference": {"type": "string", "enum": sorted(PREFERENCES)},
                        "reason": {"type": "string", "minLength": 1, "maxLength": 700},
                    },
                },
            }
        },
    }


def build_packets(public_path: Path, draw_root: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    public_rows = scorer.load_jsonl(public_path)
    public_by_id = {row["id"]: row for row in public_rows}
    draws = {
        name: scorer.load_draw(draw_root, name, public_by_id)
        for name in ("D1", "D2", "D3")
    }
    packets: list[dict[str, str]] = []
    hidden: list[dict[str, str]] = []
    for row in public_rows:
        case_id = row["id"]
        incumbent = scorer.outcome(draws["D1"][case_id])
        second = scorer.outcome(draws["D2"][case_id])
        third = scorer.outcome(draws["D3"][case_id])
        if not (incumbent and second and second == third and second != incumbent):
            continue
        left, right, incumbent_side = rotate(case_id, incumbent, second)
        packets.append({"id": case_id, "case": row["prompt"], "LEFT": left, "RIGHT": right})
        hidden.append(
            {
                "id": case_id,
                "incumbent": incumbent,
                "proposal": second,
                "incumbentSide": incumbent_side,
            }
        )
    return packets, hidden


def prompt_for(packets: list[dict[str, str]]) -> str:
    return f"""당신은 대한민국 제1심 사건 결과에 대한 출처 맹검 비교판정자입니다.
각 사건마다 LEFT와 RIGHT 중 어느 결과가 공개된 청구취지·기초사실에 더 잘 뒷받침되는지 판단하십시오.
LEFT/RIGHT의 생성 순서, 표본 수, 기존 답 여부는 숨겨져 있고 추론해서도 안 됩니다.
청구가 조금이라도 받아들여지면 '인용됨', 전부 배척되면 '기각'이라는 정의를 엄격히 적용하십시오.
한쪽이 명백히 더 잘 뒷받침될 때만 LEFT 또는 RIGHT를 고르십시오.
공개 사실만으로 우열을 신뢰성 있게 정할 수 없으면 TIE를 고르십시오.
다른 사건을 섞거나 정답·주문을 검색하지 말고, 도구·웹·파일을 사용하지 마십시오.
각 ID를 입력 순서 그대로 한 번씩 반환하고 JSON schema만 정확히 출력하십시오.

입력 사건 JSON:
{json.dumps(packets, ensure_ascii=False, separators=(",", ":"))}
"""


def validate(value: Any, packets: list[dict[str, str]]) -> list[dict[str, str]]:
    if not isinstance(value, dict) or set(value) != {"decisions"} or not isinstance(value["decisions"], list):
        raise ValueError("invalid top-level response")
    decisions = value["decisions"]
    expected = [row["id"] for row in packets]
    observed = [row.get("id") if isinstance(row, dict) else None for row in decisions]
    if observed != expected:
        raise ValueError("decision IDs/order mismatch")
    for row in decisions:
        if set(row) != {"id", "preference", "reason"}:
            raise ValueError(f"invalid decision schema: {row.get('id')}")
        if row["preference"] not in PREFERENCES or not isinstance(row["reason"], str) or not row["reason"]:
            raise ValueError(f"invalid decision value: {row.get('id')}")
    return decisions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--draw-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite nonempty output: {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    packets, hidden = build_packets(args.public, args.draw_root)
    prompt = prompt_for(packets)
    prompt_path = args.output_dir / "prompt.txt"
    schema_path = args.output_dir / "schema.json"
    response_path = args.output_dir / "response.json"
    prompt_path.write_text(prompt, encoding="utf-8")
    schema_path.write_bytes(dev_runner.canonical_bytes(schema()))
    with tempfile.TemporaryDirectory(prefix="mini-blind-veto-") as temporary:
        command = dev_runner.command(schema_path.resolve(), response_path.resolve(), Path(temporary))
        result = subprocess.run(
            command,
            input=prompt.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={"PATH": os.environ["PATH"], "CODEX_HOME": str(dev_runner.CODEX_HOME)},
            timeout=args.timeout,
            check=False,
        )
    (args.output_dir / "trace.jsonl").write_bytes(result.stdout)
    (args.output_dir / "stderr.txt").write_bytes(result.stderr)
    if result.returncode != 0 or not response_path.is_file():
        raise RuntimeError(f"blind veto call failed with return code {result.returncode}")
    decisions = validate(json.loads(response_path.read_text(encoding="utf-8")), packets)
    (args.output_dir / "hidden-role-map.json").write_bytes(dev_runner.canonical_bytes(hidden))
    receipt = {
        "protocol": "mini_artichokes_legal_blind_veto_dev_v1",
        "developmentOnly": True,
        "model": dev_runner.MODEL,
        "reasoningEffort": "high",
        "eligible": len(packets),
        "ids": [row["id"] for row in packets],
        "promptSha256": dev_runner.sha256_file(prompt_path),
        "schemaSha256": dev_runner.sha256_file(schema_path),
        "responseSha256": dev_runner.sha256_file(response_path),
        "semanticAttempts": 1,
        "tokenUsage": dev_runner.token_usage(result.stdout),
    }
    (args.output_dir / "receipt.json").write_bytes(dev_runner.canonical_bytes(receipt))
    print(json.dumps({"receipt": receipt, "decisions": decisions}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
