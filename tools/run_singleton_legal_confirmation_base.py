#!/usr/bin/env python3
"""Run the frozen legal-confirmation base arms, one case per Codex process.

This execution-only runner has no gold-loading path.  It reuses the selected
development structured prompt without batching, adds one minimal direct-Luna
control, permits one semantic attempt, and makes completed receipts resumable
without another model call.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

try:
    from tools import run_batched_structured_legal_dev as base
except ImportError:
    import run_batched_structured_legal_dev as base


PROTOCOL = "mini_artichokes_singleton_legal_confirmation_base_v1"
ARMS = ("P1", "D1", "D2", "D3")


def direct_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["predictions"],
        "properties": {
            "predictions": {
                "type": "array",
                "minItems": 1,
                "maxItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["id", "outcome", "rationale"],
                    "properties": {
                        "id": {"type": "string"},
                        "outcome": {
                            "type": "string",
                            "enum": ["ABSTAIN", "기각", "인용됨"],
                        },
                        "rationale": {"type": "string", "minLength": 1, "maxLength": 700},
                    },
                },
            }
        },
    }


def direct_prompt(row: dict[str, Any]) -> str:
    packet = {"id": row["id"], "case": row["prompt"]}
    return f"""당신은 대한민국 제1심 사건 결과를 예측하는 독립 분석자입니다.
아래 한 사건만 판단하십시오. 정답, 주문, 다른 분석자의 답은 제공되지 않습니다.
인용됨/기각/ABSTAIN 중 하나를 고르고 짧은 핵심 근거를 쓰십시오.
인용됨은 청구가 일부라도 받아들여지는 경우, 기각은 청구가 전부 배척되는 경우입니다.
ABSTAIN은 공개 자료만으로 어느 쪽도 지지할 수 없을 때만 사용하십시오.
도구·웹·파일을 사용하지 말고 JSON schema만 정확히 반환하십시오.

입력 사건 JSON:
{json.dumps(packet, ensure_ascii=False, separators=(",", ":"))}
"""


def validate_direct(value: Any, row: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    if not isinstance(value, dict) or set(value) != {"predictions"}:
        return None, ["invalid_top_level_schema"]
    predictions = value["predictions"]
    if not isinstance(predictions, list) or len(predictions) != 1:
        return None, ["invalid_prediction_count"]
    item = predictions[0]
    if not isinstance(item, dict) or set(item) != {"id", "outcome", "rationale"}:
        return None, ["invalid_row_schema"]
    errors: list[str] = []
    if item.get("id") != row["id"]:
        errors.append("id_mismatch")
    if item.get("outcome") not in base.OUTCOMES:
        errors.append("invalid_outcome")
    rationale = item.get("rationale")
    if not isinstance(rationale, str) or not (1 <= len(rationale) <= 700):
        errors.append("invalid_rationale")
    return (None, errors) if errors else (item, [])


def verify_resume(receipt_path: Path, *, arm: str, case_id: str, public_sha: str, protocol_sha: str) -> None:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    identity = (
        receipt.get("protocol") == PROTOCOL
        and receipt.get("arm") == arm
        and receipt.get("id") == case_id
        and receipt.get("publicSha256") == public_sha
        and receipt.get("frozenProtocolSha256") == protocol_sha
        and receipt.get("semanticAttempts") == 1
        and receipt.get("status") in {"accepted", "rejected"}
    )
    if not identity:
        raise RuntimeError(f"resume receipt identity mismatch: {receipt_path}")


def run_arm(
    rows: list[dict[str, Any]],
    *,
    arm: str,
    output_dir: Path,
    public_sha: str,
    protocol_sha: str,
    timeout: int,
) -> None:
    for index, row in enumerate(rows):
        shard_dir = output_dir / arm / f"shard_{index:04d}"
        receipt_path = shard_dir / "receipt.json"
        if receipt_path.is_file():
            verify_resume(
                receipt_path,
                arm=arm,
                case_id=str(row["id"]),
                public_sha=public_sha,
                protocol_sha=protocol_sha,
            )
            print(json.dumps({"arm": arm, "index": index, "status": "resume_no_call"}), flush=True)
            continue
        if shard_dir.exists() and any(shard_dir.iterdir()):
            raise RuntimeError(f"started singleton has no final receipt; refusing recall: {shard_dir}")
        shard_dir.mkdir(parents=True, exist_ok=True)
        if arm == "P1":
            prompt = direct_prompt(row)
            schema = direct_schema()
        else:
            prompt = base.prompt_for([row], arm)
            schema = base.output_schema()
        prompt_path = shard_dir / "prompt.txt"
        schema_path = shard_dir / "schema.json"
        response_path = shard_dir / "response.json"
        trace_path = shard_dir / "trace.jsonl"
        base.write_exclusive(prompt_path, prompt.encode("utf-8"))
        base.write_exclusive(schema_path, base.canonical_bytes(schema))
        with tempfile.TemporaryDirectory(prefix="mini-confirm-base-") as temporary:
            result = subprocess.run(
                base.command(schema_path.resolve(), response_path.resolve(), Path(temporary)),
                input=prompt.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={"PATH": os.environ["PATH"], "CODEX_HOME": str(base.CODEX_HOME)},
                timeout=timeout,
                check=False,
            )
        base.write_exclusive(trace_path, result.stdout)
        base.write_exclusive(shard_dir / "stderr.txt", result.stderr)
        errors: list[str] = []
        prediction: dict[str, Any] | None = None
        if result.returncode != 0:
            errors.append(f"returncode_{result.returncode}")
        elif not response_path.is_file():
            errors.append("missing_response")
        else:
            try:
                value = json.loads(response_path.read_text(encoding="utf-8"))
                if arm == "P1":
                    prediction, errors = validate_direct(value, row)
                else:
                    validated, errors = base.validate_response(value, [row])
                    prediction = validated[0]
            except Exception as exc:
                errors.append(f"response_parse:{type(exc).__name__}")
        normalized_path = shard_dir / "normalized.json"
        base.write_exclusive(
            normalized_path,
            base.canonical_bytes([{"id": row["id"], "prediction": prediction}]),
        )
        receipt: dict[str, Any] = {
            "protocol": PROTOCOL,
            "frozenProtocolSha256": protocol_sha,
            "publicSha256": public_sha,
            "model": base.MODEL,
            "arm": arm,
            "index": index,
            "id": row["id"],
            "promptSha256": base.sha256_file(prompt_path),
            "responseSha256": base.sha256_file(response_path) if response_path.is_file() else None,
            "traceSha256": base.sha256_file(trace_path),
            "normalizedSha256": base.sha256_file(normalized_path),
            "status": "accepted" if not errors else "rejected",
            "validRows": int(prediction is not None),
            "errors": errors,
            "tokenUsage": base.token_usage(result.stdout),
            "semanticAttempts": 1,
        }
        receipt["receiptSha256"] = base.sha256_bytes(base.canonical_bytes(receipt))
        base.write_exclusive(receipt_path, base.canonical_bytes(receipt))
        print(
            json.dumps(
                {
                    "arm": arm,
                    "index": index,
                    "status": receipt["status"],
                    "validRows": receipt["validRows"],
                    "tokens": receipt["tokenUsage"],
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            flush=True,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--expected-public-sha256", required=True)
    parser.add_argument("--frozen-protocol", type=Path, required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--arm", action="append", choices=ARMS, required=True)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    public_sha = base.sha256_file(args.public)
    protocol_sha = base.sha256_file(args.frozen_protocol)
    if public_sha != args.expected_public_sha256:
        raise ValueError("public input hash mismatch")
    if protocol_sha != args.expected_protocol_sha256:
        raise ValueError("frozen protocol hash mismatch")
    rows = base.load_jsonl(args.public)
    ids = [row.get("id") for row in rows]
    if len(rows) != 464 or len(set(ids)) != 464 or not all(isinstance(value, str) for value in ids):
        raise ValueError("confirmation public input must contain 464 unique string IDs")
    for arm in args.arm:
        run_arm(
            rows,
            arm=arm,
            output_dir=args.output_dir,
            public_sha=public_sha,
            protocol_sha=protocol_sha,
            timeout=args.timeout,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
