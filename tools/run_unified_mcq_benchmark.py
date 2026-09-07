#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared_platform.beta6 import Beta6JobManager, build_beta6_direct_messages, default_llm_client_from_env
from shared_platform.domain_adapters import get_domain_adapter
from shared_platform.products import PRODUCT_PROFILES, ProductProfile


CIRCLED_DIGITS = {
    "①": "1",
    "②": "2",
    "③": "3",
    "④": "4",
    "⑤": "5",
    "⑥": "6",
    "⑦": "7",
    "⑧": "8",
    "⑨": "9",
    "⑩": "10",
    "❶": "1",
    "❷": "2",
    "❸": "3",
    "❹": "4",
    "❺": "5",
    "❻": "6",
    "❼": "7",
    "❽": "8",
    "❾": "9",
    "⓵": "1",
    "⓶": "2",
    "⓷": "3",
    "⓸": "4",
    "⓹": "5",
}

ANSWER_LINE_RE = re.compile(
    r"(?:정답|답|answer|correct\s+answer)\s*[:：]?\s*([A-Za-z]|\d{1,2}|[①②③④⑤⑥⑦⑧⑨⑩❶❷❸❹❺❻❼❽❾⓵⓶⓷⓸⓹])",
    re.IGNORECASE,
)
CIRCLED_OPTION_LINE_RE = re.compile(
    r"^\s*([①②③④⑤⑥⑦⑧⑨⑩❶❷❸❹❺❻❼❽❾⓵⓶⓷⓸⓹])(?:\s*\S.*)?\s*$"
)
LETTER_OPTION_LINE_RE = re.compile(r"^\s*[([]?([A-Ea-e])[)\].、:：]\s+\S")
NUMERIC_OPTION_LINE_RE = re.compile(r"^\s*[([]?([1-9]\d?)[)\].、:：]\s+\S")
OCR_OPTION_MARKER_PATTERN = (
    r"@®|Q@|@@|@\)|@[1-9]|①|②|③|④|⑤|❶|❷|❸|❹|❺|⓵|⓶|⓷|⓸|⓹|"
    r"0[1-9]|69|63|\(0[1-9]\)?|\([1-9]\)?|OF|0|[1-9]|@|®|©|D|Q|O"
)
OCR_OPTION_LINE_RE = re.compile(
    rf"^\s*(?:{OCR_OPTION_MARKER_PATTERN})(?:\s*[\)\.\:]|\s+)\s*\S"
)


def extract_option_ids(prompt: str, explicit_options: list[Any] | None = None) -> list[str]:
    option_ids: list[str] = []
    for option in explicit_options or []:
        if isinstance(option, dict):
            raw = option.get("id") or option.get("label") or option.get("optionId")
        else:
            raw = option
        normalized = _normalize_option_id(str(raw or ""))
        if normalized:
            option_ids.append(normalized)
    explicit = _unique([item for item in option_ids if item])
    if len(explicit) >= 2:
        return explicit

    lines = str(prompt or "").splitlines()
    circled = _matched_option_ids(lines, CIRCLED_OPTION_LINE_RE)
    if len(circled) >= 2:
        return circled
    letters = _matched_option_ids(lines, LETTER_OPTION_LINE_RE)
    if len(letters) >= 2:
        return letters
    numeric = _longest_numeric_option_run(_matched_option_ids(lines, NUMERIC_OPTION_LINE_RE))
    if len(numeric) >= 2:
        return numeric

    ocr_count = sum(1 for line in lines if OCR_OPTION_LINE_RE.match(line))
    if ocr_count >= 2:
        return [str(index) for index in range(1, ocr_count + 1)]
    return explicit


def _matched_option_ids(lines: list[str], pattern: re.Pattern[str]) -> list[str]:
    values: list[str] = []
    for line in lines:
        match = pattern.match(line)
        if not match:
            continue
        normalized = _normalize_option_id(match.group(1))
        if normalized:
            values.append(normalized)
    return _unique(values)


def _longest_numeric_option_run(values: list[str]) -> list[str]:
    best: list[str] = []
    current: list[str] = []
    for value in values:
        if value == "1":
            current = [value]
        elif current and value == str(len(current) + 1):
            current.append(value)
        else:
            current = []
        if len(current) > len(best):
            best = list(current)
    return best


def build_mcq_query(prompt: str, *, language: str = "", option_ids: list[str] | None = None) -> str:
    ids = [item for item in _unique(option_ids or []) if item]
    if str(language or "").lower().startswith("ko"):
        candidate_line = f"보기ID 후보: {', '.join(ids)}" if ids else "보기ID 후보: 문제에 표시된 보기 라벨"
        instruction = (
            "위 객관식 문제의 정답 보기ID 하나만 고르세요.\n"
            f"{candidate_line}\n"
            "OCR로 보기 기호가 깨졌거나 반복되면 보기ID는 본문에 나열된 보기를 위에서 아래 순서로 센 값입니다.\n"
            "답변 첫 줄은 반드시 `정답: <보기ID>` 형식으로 시작하세요."
        )
    else:
        candidate_line = f"Allowed option IDs: {', '.join(ids)}" if ids else "Allowed option IDs: the option labels shown in the question"
        instruction = (
            "Choose exactly one option ID for the multiple-choice question above.\n"
            f"{candidate_line}\n"
            "If printed or OCR option markers are corrupted or repeated, option IDs follow the choices in top-to-bottom order.\n"
            "The first line must start with `Answer: <option ID>`."
        )
    return f"{str(prompt or '').strip()}\n\n{instruction}".strip()


def build_short_answer_query(prompt: str, *, language: str = "") -> str:
    if str(language or "").lower().startswith("ko"):
        instruction = (
            "위 단답형 문제에 답하세요. 설명이나 동의어를 덧붙이지 마세요.\n"
            '반드시 JSON 객체 `{\"finalAnswer\":\"정확한 답 문자열\"}` 하나만 출력하세요.'
        )
    else:
        instruction = (
            "Answer the short-answer question without explanation or synonyms.\n"
            'Return only one JSON object: `{\"finalAnswer\":\"exact answer string\"}`.'
        )
    return f"{str(prompt or '').strip()}\n\n{instruction}".strip()


def parse_mcq_prediction(answer: str, *, allowed_ids: list[str] | None = None) -> str | None:
    allowed = [_normalize_option_id(item) for item in allowed_ids or [] if _normalize_option_id(item)]
    allowed_set = set(allowed)
    text = str(answer or "").strip()
    if not text:
        return None

    match = ANSWER_LINE_RE.search(text)
    if match:
        normalized = _normalize_option_id(match.group(1))
        if _allowed(normalized, allowed_set):
            return normalized

    first_line = text.splitlines()[0].strip()
    first_match = re.search(r"^\s*([A-Za-z]|\d{1,2}|[①②③④⑤⑥⑦⑧⑨⑩❶❷❸❹❺❻❼❽❾⓵⓶⓷⓸⓹])(?:\b|[)\].:：、])", first_line)
    if first_match:
        normalized = _normalize_option_id(first_match.group(1))
        if _allowed(normalized, allowed_set):
            return normalized

    for candidate in allowed:
        if _candidate_appears(candidate, first_line):
            return candidate
    return None


def parse_short_answer_prediction(answer: str) -> str | None:
    text = str(answer or "").strip()
    if not text:
        return None
    json_text = text
    if json_text.startswith("```") and json_text.endswith("```"):
        lines = json_text.splitlines()
        json_text = "\n".join(lines[1:-1])
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict) and isinstance(payload.get("finalAnswer"), str):
        return payload["finalAnswer"]
    for line in text.splitlines():
        match = re.match(r"^\s*(?:finalAnswer|정답|답|answer)\s*[:：]\s*(.*?)\s*$", line, re.IGNORECASE)
        if match and match.group(1):
            return match.group(1)
    return None


def run_direct_manifest(
    *,
    public_path: Path,
    output_dir: Path,
    products: dict[str, ProductProfile] | None = None,
    llm_client: Any | None = None,
    resume: bool = False,
    model: str = "",
    max_cases: int = 0,
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    manifest = _load_public_manifest(public_path)
    profiles = products or PRODUCT_PROFILES
    product_key = str(manifest.get("product") or "").strip()
    product = profiles[product_key]
    client = llm_client if llm_client is not None else default_llm_client_from_env()
    if client is None:
        raise RuntimeError("no LLM client configured")
    model_metadata = _client_model_metadata(client, model=model)

    records: list[dict[str, Any]] = []
    result_dir = output_dir / "results"
    result_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    for case in _limited_cases(manifest, max_cases=max_cases, case_ids=case_ids):
        case_id = str(case.get("id") or "").strip()
        if not case_id:
            continue
        record_path = result_dir / f"{case_id}.json"
        if resume and record_path.exists():
            records.append(json.loads(record_path.read_text(encoding="utf-8")))
            continue
        record = _base_record(manifest, case, mode="direct")
        try:
            language = _case_language(manifest, case, product)
            short_answer = manifest.get("taskType") == "short_answer"
            option_ids = [] if short_answer else case_option_ids(case, product)
            query = (
                build_short_answer_query(str(case.get("prompt") or ""), language=language)
                if short_answer
                else build_mcq_query(str(case.get("prompt") or ""), language=language, option_ids=option_ids)
            )
            answer = str(client.complete(build_beta6_direct_messages(product, query, language), model=model) or "")
            record.update(
                {
                    "prediction": (
                        parse_short_answer_prediction(answer)
                        if short_answer
                        else parse_mcq_prediction(answer, allowed_ids=option_ids)
                    ),
                    "answerPreview": answer[:1200],
                    "llmUsed": True,
                    "llmProvider": model_metadata["provider"],
                    "llmModel": model_metadata["model"],
                    "modelMetadata": model_metadata,
                    "optionIds": option_ids,
                }
            )
        except Exception as exc:
            record["error"] = str(exc)
        record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        records.append(record)
    return _write_summary(output_dir, manifest=manifest, records=records, mode="direct", started=started)


def run_engine_manifest(
    *,
    public_path: Path,
    output_dir: Path,
    products: dict[str, ProductProfile] | None = None,
    llm_client: Any | None = None,
    resume: bool = False,
    limit: int = 50,
    analysis_mode: str = "fast",
    max_cases: int = 0,
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    manifest = _load_public_manifest(public_path)
    profiles = products or PRODUCT_PROFILES
    product_key = str(manifest.get("product") or "").strip()
    product = profiles[product_key]
    records: list[dict[str, Any]] = []
    result_dir = output_dir / "results"
    result_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    client = llm_client if llm_client is not None else default_llm_client_from_env()
    runtime = Beta6JobManager(
        {product_key: product},
        runs_root=output_dir / "beta6_jobs",
        llm_client=client,
        resume_pending_jobs=False,
    )
    try:
        for case in _limited_cases(manifest, max_cases=max_cases, case_ids=case_ids):
            case_id = str(case.get("id") or "").strip()
            if not case_id:
                continue
            record_path = result_dir / f"{case_id}.json"
            if resume and record_path.exists():
                records.append(json.loads(record_path.read_text(encoding="utf-8")))
                continue
            record = _base_record(manifest, case, mode="engine")
            try:
                language = _case_language(manifest, case, product)
                short_answer = manifest.get("taskType") == "short_answer"
                option_ids = [] if short_answer else case_option_ids(case, product)
                query = (
                    build_short_answer_query(str(case.get("prompt") or ""), language=language)
                    if short_answer
                    else build_mcq_query(str(case.get("prompt") or ""), language=language, option_ids=option_ids)
                )
                result = runtime.answer_sync(
                    product=product_key,
                    query=query,
                    language=language,
                    limit=limit,
                    analysis_mode=analysis_mode,
                )
                answer = str(result.get("answer") or result.get("answerMarkdown") or "")
                beta6 = result.get("beta6") if isinstance(result.get("beta6"), dict) else {}
                selector = result.get("selector") if isinstance(result.get("selector"), dict) else {}
                writer = result.get("writer") if isinstance(result.get("writer"), dict) else {}
                artifacts = result.get("artifacts") if isinstance(result.get("artifacts"), dict) else {}
                selected_evidence = result.get("selectedEvidence") if isinstance(result.get("selectedEvidence"), list) else []
                cited_claim_cards = result.get("citedClaimCards") if isinstance(result.get("citedClaimCards"), list) else []
                context_packets = result.get("contextPackets") if isinstance(result.get("contextPackets"), list) else []
                writer_provider = str(beta6.get("writerProvider", writer.get("provider", "")) or "")
                writer_model = str(beta6.get("writerModel", writer.get("model", "")) or "")
                model_metadata = _model_metadata(
                    provider=writer_provider,
                    model=writer_model,
                    decoding=_client_decoding_metadata(client),
                )
                record.update(
                    {
                        "prediction": (
                            parse_short_answer_prediction(answer)
                            if short_answer
                            else parse_mcq_prediction(answer, allowed_ids=option_ids)
                        ),
                        "answerPreview": answer[:1200],
                        "answerReadiness": result.get("answerReadiness", ""),
                        "selectedCount": beta6.get("selectedCount", len(selected_evidence or result.get("sources") or [])),
                        "selectedEvidenceIds": _selected_evidence_ids(selected_evidence),
                        "citedClaimCount": beta6.get("citedClaimCount", len(cited_claim_cards)),
                        "citedClaimSourceIds": _cited_claim_source_ids(cited_claim_cards),
                        "candidateCount": beta6.get("candidateCount", 0),
                        "candidateIds": selector.get("candidateIds", []),
                        "candidateSetDigest": selector.get("candidateSetDigest", ""),
                        "contextPacketCount": beta6.get("contextPacketCount", len(context_packets)),
                        "contextPacketIds": _context_packet_ids(context_packets),
                        "contextPacketArtifact": artifacts.get("contextPackets", ""),
                        "selectorStatus": beta6.get("selectorStatus", selector.get("status", "")),
                        "selectionSource": beta6.get("selectionSource", selector.get("selectionSource", "")),
                        "candidateCoverage": selector.get("candidateCoverage", {}),
                        "writerStatus": beta6.get("writerStatus", writer.get("status", "")),
                        "writerMode": writer.get("mode", ""),
                        "writerProvider": writer_provider,
                        "writerModel": writer_model,
                        "modelMetadata": model_metadata,
                        "llmUsed": bool(result.get("llmUsed")),
                        "jobId": result.get("jobId", ""),
                        "optionIds": option_ids,
                    }
                )
            except Exception as exc:
                record["error"] = str(exc)
            record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            records.append(record)
    finally:
        runtime.shutdown(wait=False)
    return _write_summary(output_dir, manifest=manifest, records=records, mode="engine", started=started)


def _load_public_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("taskType") not in {"mcq", "short_answer"}:
        raise ValueError(f"expected taskType=mcq or short_answer: {path}")
    return manifest


def case_option_ids(case: dict[str, Any], product: ProductProfile) -> list[str]:
    ids: list[str] = []
    parsed = get_domain_adapter(product).parse_multiple_choice(str(case.get("prompt") or ""))
    if parsed is not None:
        for option in parsed.options:
            marker = str(option.marker or "").strip()
            option_id = (
                str(option.number or "").strip()
                if product.key == "tcm"
                else marker if re.fullmatch(r"[A-Za-z]|\d{1,2}", marker) else str(option.number or "").strip()
            )
            if option_id and option_id not in ids:
                ids.append(option_id)
    if len(ids) >= 2:
        return ids

    explicit = extract_option_ids(str(case.get("prompt") or ""), case.get("options") if isinstance(case.get("options"), list) else None)
    if len(explicit) >= 2:
        return explicit
    return ids or explicit


def _limited_cases(
    manifest: dict[str, Any],
    *,
    max_cases: int = 0,
    case_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    cases = [case for case in manifest.get("cases", []) if isinstance(case, dict)]
    allowed = {str(case_id) for case_id in case_ids or [] if str(case_id)}
    if allowed:
        cases = [case for case in cases if _case_id_selected(str(case.get("id") or ""), allowed)]
    if max_cases and max_cases > 0:
        return cases[:max_cases]
    return cases


def _case_id_selected(case_id: str, allowed: set[str]) -> bool:
    normalized = str(case_id or "").strip()
    if not normalized:
        return False
    lowered = normalized.lower()
    allowed_lower = {item.strip().lower() for item in allowed if item.strip()}
    if lowered in allowed_lower:
        return True
    return any(
        lowered.endswith(f"{separator}{candidate}")
        for candidate in allowed_lower
        for separator in ("-", "_", ".")
    )


def _case_language(manifest: dict[str, Any], case: dict[str, Any], product: ProductProfile) -> str:
    return str(case.get("language") or manifest.get("language") or product.default_language or "ko")


def _base_record(manifest: dict[str, Any], case: dict[str, Any], *, mode: str) -> dict[str, Any]:
    case_id = str(case.get("id") or "").strip()
    return {
        "id": case_id,
        "caseId": case_id,
        "benchmarkId": manifest.get("benchmarkId", ""),
        "product": manifest.get("product", ""),
        "mode": mode,
        "gold": None,
        "prediction": None,
        "correct": None,
        "metadata": case.get("metadata") if isinstance(case.get("metadata"), dict) else {},
        "error": "",
    }


def _write_summary(
    output_dir: Path,
    *,
    manifest: dict[str, Any],
    records: list[dict[str, Any]],
    mode: str,
    started: float,
) -> dict[str, Any]:
    total = {
        "total": len(records),
        "predicted": sum(1 for item in records if item.get("prediction")),
        "correct": None,
        "errors": sum(1 for item in records if item.get("error")),
        "accuracy": None,
    }
    summary = {
        "benchmarkId": manifest.get("benchmarkId", ""),
        "taskType": manifest.get("taskType", ""),
        "product": manifest.get("product", ""),
        "mode": mode,
        "total": total,
        "modelMetadata": _summary_model_metadata(records),
        "elapsedSec": round(time.time() - started, 3),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def _context_packet_ids(context_packets: list[Any]) -> list[str]:
    ids: list[str] = []
    for item in context_packets:
        if not isinstance(item, dict):
            continue
        packet_id = str(item.get("packetId") or "").strip()
        if packet_id:
            ids.append(packet_id)
    return ids


def _client_model_metadata(client: Any, *, model: str) -> dict[str, Any]:
    return _model_metadata(
        provider=str(getattr(client, "provider", "custom_llm") or "custom_llm"),
        model=str(model or getattr(client, "default_model", "") or ""),
        decoding=_client_decoding_metadata(client),
    )


def _client_decoding_metadata(client: Any | None) -> dict[str, Any]:
    if client is None:
        return {}
    explicit = getattr(client, "decoding", None)
    if explicit is None:
        explicit = getattr(client, "decoding_config", None)
    if isinstance(explicit, dict):
        return {str(key): value for key, value in sorted(explicit.items()) if value is not None}
    decoding: dict[str, Any] = {}
    for name in ("temperature", "top_p", "top_k", "max_tokens"):
        if hasattr(client, name):
            value = getattr(client, name)
            if value is not None:
                decoding[name] = value
    return decoding


def _model_metadata(*, provider: str, model: str, decoding: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "provider": str(provider or ""),
        "model": str(model or ""),
        "decoding": decoding if isinstance(decoding, dict) else {},
    }


def _summary_model_metadata(records: list[dict[str, Any]]) -> dict[str, Any]:
    values = [
        _normalize_model_metadata(record.get("modelMetadata"))
        for record in records
        if isinstance(record, dict) and isinstance(record.get("modelMetadata"), dict)
    ]
    if not values:
        return {}
    unique = {_stable_model_metadata_key(value) for value in values}
    if len(unique) == 1:
        return values[0]
    providers = sorted({value.get("provider", "") for value in values if value.get("provider")})
    models = sorted({value.get("model", "") for value in values if value.get("model")})
    return {
        "provider": providers[0] if len(providers) == 1 else "",
        "model": models[0] if len(models) == 1 else "",
        "decoding": {},
        "mixed": True,
        "providers": providers,
        "models": models,
    }


def _normalize_model_metadata(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    decoding = value.get("decoding")
    return _model_metadata(
        provider=str(value.get("provider") or ""),
        model=str(value.get("model") or ""),
        decoding=decoding if isinstance(decoding, dict) else {},
    )


def _stable_model_metadata_key(value: dict[str, Any]) -> str:
    return json.dumps(_normalize_model_metadata(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _normalize_option_id(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw in CIRCLED_DIGITS:
        return CIRCLED_DIGITS[raw]
    if re.fullmatch(r"\d{1,2}", raw):
        return str(int(raw))
    if re.fullmatch(r"[A-Za-z]", raw):
        return raw.upper()
    return raw


def _allowed(value: str, allowed_set: set[str]) -> bool:
    return bool(value and (not allowed_set or value in allowed_set))


def _candidate_appears(candidate: str, text: str) -> bool:
    if re.fullmatch(r"\d{1,2}", candidate):
        return bool(re.search(rf"(?<!\d){re.escape(candidate)}(?!\d)", text))
    if re.fullmatch(r"[A-Z]", candidate):
        return bool(re.search(rf"(?<![A-Za-z]){re.escape(candidate)}(?![A-Za-z])", text, re.IGNORECASE))
    return candidate in text


def _selected_evidence_ids(items: list[Any]) -> list[str]:
    ids: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("id") or item.get("sourceId") or item.get("file_id") or "").strip()
        if source_id and source_id not in ids:
            ids.append(source_id)
    return ids


def _cited_claim_source_ids(items: list[Any]) -> list[str]:
    ids: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("sourceId") or item.get("source_id") or item.get("id") or "").strip()
        if source_id and source_id not in ids:
            ids.append(source_id)
    return ids


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a public unified MCQ benchmark manifest.")
    parser.add_argument("--public", type=Path, required=True, help="Public MCQ manifest path.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=("direct", "engine"), default="engine")
    parser.add_argument("--product", default="", help="Override manifest product key.")
    parser.add_argument("--db-path", type=Path, default=None, help="Override DB path for the selected product.")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--analysis-mode", default="fast")
    parser.add_argument("--model", default="", help="Model override for direct mode.")
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--case-id", action="append", default=[], help="Run only the matching public case id. Repeatable.")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(args.public.read_text(encoding="utf-8"))
    product_key = str(args.product or manifest.get("product") or "").strip()
    if product_key not in PRODUCT_PROFILES:
        print(json.dumps({"status": "blocked", "reason": "unknown_product", "product": product_key}, ensure_ascii=False, indent=2))
        return 2
    product = PRODUCT_PROFILES[product_key]
    if args.db_path is not None:
        product = replace(product, db_path=args.db_path.resolve())
    products = dict(PRODUCT_PROFILES)
    products[product_key] = product
    if args.product:
        manifest["product"] = product_key
        patched_public = args.output_dir / "_public.effective.json"
        patched_public.parent.mkdir(parents=True, exist_ok=True)
        patched_public.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        public_path = patched_public
    else:
        public_path = args.public

    try:
        if args.mode == "direct":
            summary = run_direct_manifest(
                public_path=public_path,
                output_dir=args.output_dir,
                products=products,
                resume=args.resume,
                model=args.model,
                max_cases=args.max_cases,
                case_ids=args.case_id,
            )
        else:
            summary = run_engine_manifest(
                public_path=public_path,
                output_dir=args.output_dir,
                products=products,
                resume=args.resume,
                limit=args.limit,
                analysis_mode=args.analysis_mode,
                max_cases=args.max_cases,
                case_ids=args.case_id,
            )
    except RuntimeError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
