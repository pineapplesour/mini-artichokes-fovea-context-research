#!/usr/bin/env python3
"""Run a frozen legal-confirmation judge, one disagreement per process.

The generic and overlap modes share the same D1-D3 singleton artifacts and
anonymous role rotation.  This runner has no gold-loading path, performs one
semantic attempt, and never recalls a started singleton without a final
receipt.
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
    from tools import run_batched_multiway_legal_judge_dev as selected
    from tools import run_batched_structured_legal_dev as base
except ImportError:
    import run_batched_multiway_legal_judge_dev as selected
    import run_batched_structured_legal_dev as base


PROTOCOL = "mini_artichokes_singleton_multiway_legal_confirmation_judge_v1"


def verify_resume(
    receipt_path: Path,
    *,
    mode: str,
    case_id: str,
    public_sha: str,
    protocol_sha: str,
) -> None:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    identity = (
        receipt.get("protocol") == PROTOCOL
        and receipt.get("mode") == mode
        and receipt.get("id") == case_id
        and receipt.get("publicSha256") == public_sha
        and receipt.get("frozenProtocolSha256") == protocol_sha
        and receipt.get("semanticAttempts") == 1
        and receipt.get("status") in {"accepted", "rejected"}
    )
    if not identity:
        raise RuntimeError(f"resume receipt identity mismatch: {receipt_path}")


def run(
    packets: list[dict[str, Any]],
    role_map: list[dict[str, Any]],
    *,
    output_dir: Path,
    mode: str,
    model: str,
    public_sha: str,
    protocol_sha: str,
    timeout: int,
) -> None:
    role_by_id = {row["id"]: row for row in role_map}
    for index, packet in enumerate(packets):
        case_id = str(packet["id"])
        shard_dir = output_dir / f"shard_{index:04d}"
        receipt_path = shard_dir / "receipt.json"
        if receipt_path.is_file():
            verify_resume(
                receipt_path,
                mode=mode,
                case_id=case_id,
                public_sha=public_sha,
                protocol_sha=protocol_sha,
            )
            print(json.dumps({"mode": mode, "index": index, "status": "resume_no_call"}), flush=True)
            continue
        if shard_dir.exists() and any(shard_dir.iterdir()):
            raise RuntimeError(f"started singleton has no final receipt; refusing recall: {shard_dir}")
        shard_dir.mkdir(parents=True, exist_ok=True)
        prompt = selected.prompt_for([packet], mode)
        prompt_path = shard_dir / "prompt.txt"
        schema_path = shard_dir / "schema.json"
        response_path = shard_dir / "response.json"
        trace_path = shard_dir / "trace.jsonl"
        base.write_exclusive(prompt_path, prompt.encode("utf-8"))
        base.write_exclusive(schema_path, base.canonical_bytes(selected.schema()))
        with tempfile.TemporaryDirectory(prefix="mini-confirm-judge-") as temporary:
            command = base.command(schema_path.resolve(), response_path.resolve(), Path(temporary))
            command[command.index("--model") + 1] = model
            result = subprocess.run(
                command,
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
        valid: list[dict[str, Any]] = []
        if result.returncode != 0:
            errors.append(f"returncode_{result.returncode}")
        elif not response_path.is_file():
            errors.append("missing_response")
        else:
            try:
                value = json.loads(response_path.read_text(encoding="utf-8"))
                valid, errors = selected.validate_by_id(value, [packet])
            except Exception as exc:
                errors.append(f"response_parse:{type(exc).__name__}")
        normalized_path = shard_dir / "normalized.json"
        role_path = shard_dir / "hidden-role-map.json"
        base.write_exclusive(normalized_path, base.canonical_bytes(valid))
        base.write_exclusive(role_path, base.canonical_bytes([role_by_id[case_id]]))
        receipt: dict[str, Any] = {
            "protocol": PROTOCOL,
            "frozenProtocolSha256": protocol_sha,
            "publicSha256": public_sha,
            "model": model,
            "mode": mode,
            "index": index,
            "id": case_id,
            "packetSha256": base.sha256_bytes(base.canonical_bytes(packet)),
            "promptSha256": base.sha256_file(prompt_path),
            "responseSha256": base.sha256_file(response_path) if response_path.is_file() else None,
            "traceSha256": base.sha256_file(trace_path),
            "normalizedSha256": base.sha256_file(normalized_path),
            "roleMapSha256": base.sha256_file(role_path),
            "status": "accepted" if not errors else "rejected",
            "validRows": len(valid),
            "errors": errors,
            "tokenUsage": base.token_usage(result.stdout),
            "semanticAttempts": 1,
        }
        receipt["receiptSha256"] = base.sha256_bytes(base.canonical_bytes(receipt))
        base.write_exclusive(receipt_path, base.canonical_bytes(receipt))
        print(
            json.dumps(
                {
                    "mode": mode,
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
    parser.add_argument("--draw-root", type=Path, required=True)
    parser.add_argument("--frozen-protocol", type=Path, required=True)
    parser.add_argument("--expected-protocol-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=("generic", "overlap"), required=True)
    parser.add_argument("--model", default=base.MODEL)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    public_sha = base.sha256_file(args.public)
    protocol_sha = base.sha256_file(args.frozen_protocol)
    if public_sha != args.expected_public_sha256:
        raise ValueError("public input hash mismatch")
    if protocol_sha != args.expected_protocol_sha256:
        raise ValueError("frozen protocol hash mismatch")
    packets, role_map = selected.build_packets(
        args.public,
        args.draw_root,
        args.mode,
        ("D1", "D2", "D3"),
    )
    if [row["id"] for row in packets] != [row["id"] for row in role_map]:
        raise ValueError("packet and hidden-role order mismatch")
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    run(
        packets,
        role_map,
        output_dir=output_dir,
        mode=args.mode,
        model=args.model,
        public_sha=public_sha,
        protocol_sha=protocol_sha,
        timeout=args.timeout,
    )
    print(
        json.dumps(
            {"mode": args.mode, "model": args.model, "conflicts": len(packets)},
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
