#!/usr/bin/env python3
"""Run one role-aware overlap verifier on exposed legal development conflicts."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

try:
    from tools import run_batched_structured_legal_dev as dev_runner
    from tools import score_batched_structured_legal_dev as scorer
except ImportError:  # Direct execution from the tools directory on sys.path.
    import run_batched_structured_legal_dev as dev_runner
    import score_batched_structured_legal_dev as scorer


def output_schema() -> dict[str, Any]:
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
                    "required": ["id", "gate", "action", "reason"],
                    "properties": {
                        "id": {"type": "string"},
                        "gate": {"type": "string", "enum": ["VALID", "INVALID", "ABSTAIN"]},
                        "action": {"type": "string", "enum": ["KEEP", "SWITCH"]},
                        "reason": {"type": "string", "minLength": 1, "maxLength": 900},
                    },
                },
            }
        },
    }


def packets_for(public_path: Path, draw_root: Path) -> list[dict[str, Any]]:
    public_rows = scorer.load_jsonl(public_path)
    public_by_id = {row["id"]: row for row in public_rows}
    draws = {name: scorer.load_draw(draw_root, name, public_by_id) for name in ("D1", "D2", "D3")}
    packets: list[dict[str, Any]] = []
    for row in public_rows:
        case_id = row["id"]
        base, aux1, aux2 = (draws[name][case_id] for name in ("D1", "D2", "D3"))
        base_outcome, aux1_outcome, aux2_outcome = map(scorer.outcome, (base, aux1, aux2))
        shared = sorted(scorer.atom_keys(aux1, "clause_direction") & scorer.atom_keys(aux2, "clause_direction"))
        if not (base_outcome and aux1_outcome and aux1_outcome == aux2_outcome != base_outcome and shared):
            continue
        packets.append(
            {
                "id": case_id,
                "case": row["prompt"],
                "base": base,
                "auxiliary1": aux1,
                "auxiliary2": aux2,
                "sharedClauseDirection": [list(key) for key in shared],
            }
        )
    return packets


def prompt_for(packets: list[dict[str, Any]]) -> str:
    return f"""당신은 Mini Artichokes의 보수적 오류 검증자입니다.
각 사건에서 base가 기본 답이고, auxiliary1/2는 서로 보지 못한 별도 Luna 표본입니다.
두 auxiliary가 같은 대안 결과와 같은 근거절 방향을 냈다는 사실은 검토 시작 조건일 뿐 정답 증거가 아닙니다.

기본 행동은 KEEP입니다. 공개 사건과 세 분석을 대조하여 다음을 모두 만족할 때만 VALID+SWITCH 하십시오.
1) auxiliary1과 auxiliary2가 base에서 동일한 하나의 중대한 원자 오류를 지적한다.
2) 그 오류가 실제 번호 근거절과 청구결과 정의에 의해 독립적으로 확인된다.
3) 그 오류를 고치면 대안 결과가 base보다 명백히 더 타당하다.
상관된 오답, 서로 다른 오류, 추측, 불충분한 손해·당사자·절차 연결, 단순 다수결이면 INVALID+KEEP입니다.
우열을 신뢰성 있게 판정할 수 없으면 ABSTAIN+KEEP입니다. 새 네 번째 답을 만들지 마십시오.
도구·웹·파일·정답 검색 없이 각 ID를 입력 순서대로 한 번씩 JSON schema로만 반환하십시오.

입력 사건 JSON:
{json.dumps(packets, ensure_ascii=False, separators=(",", ":"))}
"""


def validate(value: Any, packets: list[dict[str, Any]]) -> list[dict[str, str]]:
    if not isinstance(value, dict) or set(value) != {"decisions"} or not isinstance(value["decisions"], list):
        raise ValueError("invalid top-level response")
    decisions = value["decisions"]
    if [row.get("id") for row in decisions if isinstance(row, dict)] != [row["id"] for row in packets]:
        raise ValueError("decision IDs/order mismatch")
    for row in decisions:
        if set(row) != {"id", "gate", "action", "reason"}:
            raise ValueError(f"invalid decision schema: {row.get('id')}")
        if (row["gate"] == "VALID") != (row["action"] == "SWITCH"):
            raise ValueError(f"inconsistent gate/action: {row['id']}")
        if not isinstance(row["reason"], str) or not row["reason"]:
            raise ValueError(f"invalid reason: {row['id']}")
    return decisions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--draw-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", default=dev_runner.MODEL)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite nonempty output: {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    packets = packets_for(args.public, args.draw_root)
    prompt = prompt_for(packets)
    prompt_path, schema_path = args.output_dir / "prompt.txt", args.output_dir / "schema.json"
    response_path = args.output_dir / "response.json"
    prompt_path.write_text(prompt, encoding="utf-8")
    schema_path.write_bytes(dev_runner.canonical_bytes(output_schema()))
    with tempfile.TemporaryDirectory(prefix="mini-overlap-verifier-") as temporary:
        command = dev_runner.command(schema_path.resolve(), response_path.resolve(), Path(temporary))
        command[command.index("--model") + 1] = args.model
        result = subprocess.run(
            command,
            input=prompt.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={"PATH": os.environ["PATH"], "CODEX_HOME": str(dev_runner.CODEX_HOME)},
            timeout=args.timeout, check=False,
        )
    (args.output_dir / "trace.jsonl").write_bytes(result.stdout)
    (args.output_dir / "stderr.txt").write_bytes(result.stderr)
    if result.returncode != 0 or not response_path.is_file():
        raise RuntimeError(f"overlap verifier failed with return code {result.returncode}")
    decisions = validate(json.loads(response_path.read_text(encoding="utf-8")), packets)
    receipt = {
        "protocol": "mini_artichokes_legal_overlap_verifier_dev_v1",
        "developmentOnly": True,
        "model": args.model,
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
