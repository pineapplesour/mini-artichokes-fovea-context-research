#!/usr/bin/env python3
"""Choose between a closed-book prior and evidence-conditioned answer without gold labels."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared_platform.beta6 import default_llm_client_from_env
from tools.benchmark_provider import create_benchmark_llm_client


def run_manifest(
    *,
    public_path: Path,
    output_dir: Path,
    model: str,
    llm_client: Any | None = None,
    timeout_seconds: float = 300.0,
    resume: bool = False,
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    manifest = json.loads(Path(public_path).read_text(encoding="utf-8"))
    if str(manifest.get("taskType") or "") != "evidence_intervention_arbitration":
        raise ValueError("manifest taskType must be evidence_intervention_arbitration")
    selected_ids = {str(item).strip().lower() for item in case_ids or [] if str(item).strip()}
    cases = [
        item
        for item in manifest.get("cases") or []
        if isinstance(item, dict)
        and (not selected_ids or str(item.get("id") or "").strip().lower() in selected_ids)
    ]
    client = llm_client
    if client is None and any(item.get("evidence") for item in cases):
        client = create_benchmark_llm_client(
            model=model,
            fallback_factory=default_llm_client_from_env,
            timeout_seconds=timeout_seconds,
        )
    result_dir = Path(output_dir) / "results"
    result_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    started = time.time()
    for case in cases:
        case_id = str(case.get("id") or "").strip()
        if not case_id:
            continue
        path = result_dir / f"{case_id}.json"
        if resume and path.exists():
            records.append(json.loads(path.read_text(encoding="utf-8")))
            continue
        record = _run_case(case, client=client, model=model, timeout_seconds=timeout_seconds)
        _atomic_write(path, record)
        records.append(record)
    summary = {
        "schemaVersion": 1,
        "benchmarkId": str(manifest.get("benchmarkId") or ""),
        "taskType": "evidence_intervention_arbitration",
        "mode": "evidence_arbitration",
        "total": {
            "total": len(records),
            "predicted": sum(bool(item.get("prediction")) for item in records),
            "errors": sum(bool(item.get("error")) for item in records),
        },
        "decisionCounts": {
            "direct": sum(item.get("decision") == "direct" for item in records),
            "universal": sum(item.get("decision") == "universal" for item in records),
        },
        "modelMetadata": _model_metadata(client, model) if client is not None else {},
        "elapsedSec": round(time.time() - started, 3),
    }
    _atomic_write(Path(output_dir) / "summary.json", summary)
    return summary


def _run_case(case: dict[str, Any], *, client: Any | None, model: str, timeout_seconds: float) -> dict[str, Any]:
    case_id = str(case.get("id") or "")
    direct_prediction = str(case.get("directPrediction") or "").strip()
    universal_prediction = str(case.get("universalPrediction") or "").strip()
    evidence = [dict(item) for item in case.get("evidence") or [] if isinstance(item, dict)]
    record: dict[str, Any] = {
        "id": case_id,
        "caseId": case_id,
        "mode": "evidence_arbitration",
        "decision": "direct",
        "prediction": direct_prediction,
        "directPrediction": direct_prediction,
        "universalPrediction": universal_prediction,
        "selectedEvidenceIds": [str(item.get("sourceId") or "") for item in evidence],
        "arbiterStatus": "structural_no_evidence" if not evidence else "running",
        "arbiter": {},
        "modelMetadata": _model_metadata(client, model) if client is not None else {},
        "error": "",
    }
    if not evidence:
        return record
    if client is None:
        record["error"] = "no LLM client configured"
        record["arbiterStatus"] = "error"
        return record
    try:
        raw = str(
            client.complete(
                _messages(case, evidence),
                model=model,
                timeout_seconds=timeout_seconds,
            )
            or ""
        ).strip()
        payload = _json_object(raw)
        allowed_source_ids = {str(item.get("sourceId") or "") for item in evidence if str(item.get("sourceId") or "")}
        supporting = [
            str(item)
            for item in payload.get("supportingSourceIds") or []
            if str(item) in allowed_source_ids
        ]
        universal_allowed = (
            payload.get("decision") == "universal"
            and payload.get("evidenceAnswerSupported") is True
            and payload.get("evidenceDiscriminates") is True
            and bool(supporting)
        )
        record["decision"] = "universal" if universal_allowed else "direct"
        record["prediction"] = universal_prediction if universal_allowed else direct_prediction
        record["arbiterStatus"] = "completed" if payload else "invalid_json_fallback"
        record["arbiter"] = {
            "decision": str(payload.get("decision") or ""),
            "confidence": str(payload.get("confidence") or ""),
            "priorSupported": payload.get("priorSupported"),
            "evidenceAnswerSupported": payload.get("evidenceAnswerSupported"),
            "evidenceDiscriminates": payload.get("evidenceDiscriminates"),
            "supportingSourceIds": supporting,
            "rationale": str(payload.get("rationale") or "")[:2000],
        }
        record["rawPreview"] = raw[:3000]
    except Exception as exc:  # noqa: BLE001 - the durable supervisor retries failed cases.
        record["error"] = str(exc)
        record["arbiterStatus"] = "error"
    return record


def _messages(case: dict[str, Any], evidence: list[dict[str, Any]]) -> list[dict[str, str]]:
    packets = [
        {
            "sourceId": str(item.get("sourceId") or ""),
            "title": str(item.get("title") or ""),
            "citation": str(item.get("citation") or ""),
            "exactQuote": str(item.get("exactQuote") or ""),
            "selectionReason": str(item.get("selectionReason") or ""),
        }
        for item in evidence
    ]
    return [
        {
            "role": "system",
            "content": (
                "You are the evidence-intervention arbiter of a general-purpose retrieval engine. Compare a "
                "closed-book prior answer with an evidence-conditioned answer using only the question and supplied "
                "evidence packets. Never use or infer a hidden answer key. Preserve the closed-book prior unless the "
                "packets clearly and directly justify changing it. Topical overlap, an ambiguous excerpt, incomplete "
                "coverage, or evidence consistent with multiple choices is insufficient. For a multiple-choice "
                "question, choose universal only when quoted evidence supports the universal option and materially "
                "discriminates it from the direct option. Do not trust either answer merely because it is labeled "
                "Direct or Universal. Return JSON only with schema: "
                '{"decision":"direct|universal","confidence":"low|medium|high",'
                '"priorSupported":true|false,"evidenceAnswerSupported":true|false,'
                '"evidenceDiscriminates":true|false,"supportingSourceIds":["..."],'
                '"rationale":"brief evidence-only explanation"}.'
            ),
        },
        {
            "role": "user",
            "content": (
                "Question:\n"
                + str(case.get("query") or "")
                + "\n\nClosed-book prior prediction: "
                + str(case.get("directPrediction") or "")
                + "\nClosed-book prior answer:\n"
                + str(case.get("directAnswer") or "")
                + "\n\nEvidence-conditioned prediction: "
                + str(case.get("universalPrediction") or "")
                + "\nEvidence-conditioned answer:\n"
                + str(case.get("universalAnswer") or "")
                + "\n\nEvidence packets (JSONL):\n"
                + "\n".join(json.dumps(item, ensure_ascii=False) for item in packets)
            ),
        },
    ]


def _json_object(text: str) -> dict[str, Any]:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].lstrip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            value = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return {}
    return value if isinstance(value, dict) else {}


def _model_metadata(client: Any | None, model: str) -> dict[str, Any]:
    if client is None:
        return {}
    decoding = getattr(client, "decoding", None)
    return {
        "provider": str(getattr(client, "provider", "custom_llm") or "custom_llm"),
        "model": str(model or getattr(client, "default_model", "") or ""),
        "decoding": dict(decoding) if isinstance(decoding, dict) else {},
    }


def _atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    summary = run_manifest(
        public_path=args.public,
        output_dir=args.output_dir,
        model=args.model,
        timeout_seconds=args.timeout_seconds,
        resume=args.resume,
        case_ids=args.case_id,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
