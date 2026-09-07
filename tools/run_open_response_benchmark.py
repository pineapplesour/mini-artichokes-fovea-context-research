#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared_platform.beta6 import default_llm_client_from_env
from tools.benchmark_provider import create_benchmark_llm_client
from tools.prompt_identity import prompt_identity
from tools.resource_gate import heavy_cli_allowed
from tools.run_unified_mcq_benchmark import parse_short_answer_prediction


MAX_REALTIME_SECONDS = 600.0
OFFICIAL_READY_STATUSES = frozenset({"ready_hide_options", "ready_semantic_rewrite"})
PUBLIC_PRODUCT_LABELS = {
    "tcm": {"ko": "한의학", "en": "traditional Chinese/Korean medicine"},
    "lawkey": {"ko": "법률", "en": "law"},
    "psych": {"ko": "심리학·정신건강", "en": "psychology and mental health"},
    "islam": {"ko": "이슬람학", "en": "Islamic studies"},
    "buddhist": {"ko": "불교학", "en": "Buddhist studies"},
    "catholic": {"ko": "가톨릭·기독교학", "en": "Catholic and Christian studies"},
    "christian": {"ko": "기독교학", "en": "Christian studies"},
    "hindu": {"ko": "힌두교학", "en": "Hindu studies"},
}
SINGLE_PASS_SELF_VERIFY_SKILL_V1 = {
    "ko": (
        "답을 쓰기 전에 비공개로 서로 다른 후보 답 세 개를 세우고, 문제의 각 사실 및 가능한 반례 하나와 "
        "대조해 완전히 일치하는 답만 선택하세요. 후보·검토 과정은 출력하지 마세요.\n"
    ),
    "en": (
        "Before answering, privately form three distinct candidate answers, test each against every stated fact and "
        "one plausible counterexample, and select only the fully consistent answer. Do not reveal the candidates or checks.\n"
    ),
}
REQUIRED_GENERAL_WEB_SEARCH_V1 = {
    "ko": (
        "최종 답 전에 일반 개념·제도명에 대한 실시간 웹검색을 최소 한 번 사용하세요. 문제 문장, 시험명, "
        "문항, 보기, 정답 또는 답안 사이트를 검색하지 마세요.\n"
    ),
    "en": (
        "Before the final answer, use live web search at least once for general concepts or institutional terms. "
        "Do not search the question wording, exam name, item, choices, answer, or answer sites.\n"
    ),
}
DOMAIN_CLASSIFICATION_SKILL_PATH = (
    REPO_ROOT / ".agents/skills/preserve-domain-classification/references/prompt-v1.json"
)
DOMAIN_CLASSIFICATION_SKILL_PAYLOAD = json.loads(
    DOMAIN_CLASSIFICATION_SKILL_PATH.read_text(encoding="utf-8")
)
DOMAIN_CLASSIFICATION_SKILL_VERSION = str(DOMAIN_CLASSIFICATION_SKILL_PAYLOAD["version"])
DOMAIN_CLASSIFICATION_SKILL_SHA256 = hashlib.sha256(DOMAIN_CLASSIFICATION_SKILL_PATH.read_bytes()).hexdigest()
DOMAIN_CLASSIFICATION_ROUTE_PATH = (
    REPO_ROOT / ".agents/skills/preserve-domain-classification/references/routing-v1.json"
)
DOMAIN_CLASSIFICATION_ROUTE_PAYLOAD = json.loads(
    DOMAIN_CLASSIFICATION_ROUTE_PATH.read_text(encoding="utf-8")
)
DOMAIN_CLASSIFICATION_ROUTE_VERSION = str(DOMAIN_CLASSIFICATION_ROUTE_PAYLOAD["version"])
DOMAIN_CLASSIFICATION_ROUTE_SHA256 = hashlib.sha256(DOMAIN_CLASSIFICATION_ROUTE_PATH.read_bytes()).hexdigest()
TCM_DOMAIN_CLASSIFICATION_ROUTE_PATH = (
    REPO_ROOT / ".agents/skills/preserve-domain-classification/references/routing-tcm-v1.json"
)
TCM_DOMAIN_CLASSIFICATION_ROUTE_PAYLOAD = json.loads(
    TCM_DOMAIN_CLASSIFICATION_ROUTE_PATH.read_text(encoding="utf-8")
)
TCM_DOMAIN_CLASSIFICATION_ROUTE_VERSION = str(TCM_DOMAIN_CLASSIFICATION_ROUTE_PAYLOAD["version"])
TCM_DOMAIN_CLASSIFICATION_ROUTE_SHA256 = hashlib.sha256(TCM_DOMAIN_CLASSIFICATION_ROUTE_PATH.read_bytes()).hexdigest()


def promoted_domain_classification_route_identity(*, product: str) -> dict[str, str]:
    normalized_product = str(product or "").strip().casefold()
    if normalized_product == "islam":
        return {"version": DOMAIN_CLASSIFICATION_ROUTE_VERSION, "sha256": DOMAIN_CLASSIFICATION_ROUTE_SHA256}
    if normalized_product == "tcm":
        return {"version": TCM_DOMAIN_CLASSIFICATION_ROUTE_VERSION, "sha256": TCM_DOMAIN_CLASSIFICATION_ROUTE_SHA256}
    return {"version": "", "sha256": ""}


def should_use_promoted_domain_classification(*, prompt: str, product: str) -> bool:
    normalized_product = str(product or "").strip().casefold()
    tcm_products = {
        str(value).strip().casefold()
        for value in TCM_DOMAIN_CLASSIFICATION_ROUTE_PAYLOAD.get("eligibleProducts", [])
        if str(value).strip()
    }
    if normalized_product in tcm_products:
        return True
    eligible_products = {
        str(value).strip().casefold()
        for value in DOMAIN_CLASSIFICATION_ROUTE_PAYLOAD.get("eligibleProducts", [])
        if str(value).strip()
    }
    if normalized_product not in eligible_products:
        return False
    text = str(prompt or "").casefold()
    markers = [
        str(value).casefold()
        for value in DOMAIN_CLASSIFICATION_ROUTE_PAYLOAD.get("explicitDomainMarkers", [])
        if str(value)
    ]
    return not any(marker in text for marker in markers)


def build_open_response_query(
    prompt: str,
    *,
    language: str = "",
    product: str = "",
    include_public_product_context: bool = False,
    single_pass_self_verify: bool = False,
    require_general_web_search: bool = False,
    preserve_domain_classification: bool = False,
) -> str:
    normalized_product = str(product or "").strip().lower()
    labels = PUBLIC_PRODUCT_LABELS.get(normalized_product, {})
    if str(language or "").lower().startswith("ko"):
        domain_context = (
            f"공개 분야: {labels.get('ko', normalized_product)}. 이 분야의 표준 용어와 분류로 답하세요.\n"
            if include_public_product_context and normalized_product
            else ""
        )
        self_verify = SINGLE_PASS_SELF_VERIFY_SKILL_V1["ko"] if single_pass_self_verify else ""
        web_search = REQUIRED_GENERAL_WEB_SEARCH_V1["ko"] if require_general_web_search else ""
        classification = (
            str(DOMAIN_CLASSIFICATION_SKILL_PAYLOAD["ko"])
            if preserve_domain_classification
            else ""
        )
        instruction = domain_context + classification + self_verify + web_search + (
            "선택지는 제공되지 않습니다. 보기 번호나 문자가 아니라 문제에서 요구한 답의 내용을 직접 쓰세요.\n"
            "핵심 사실을 빠뜨리지 않되 간결하게 답하세요.\n"
            '반드시 JSON 객체 `{"finalAnswer":"답 내용"}` 하나만 출력하세요.'
        )
    else:
        domain_context = (
            f"Public domain: {labels.get('en', normalized_product)}. Answer using this domain's standard terminology and classifications.\n"
            if include_public_product_context and normalized_product
            else ""
        )
        self_verify = SINGLE_PASS_SELF_VERIFY_SKILL_V1["en"] if single_pass_self_verify else ""
        web_search = REQUIRED_GENERAL_WEB_SEARCH_V1["en"] if require_general_web_search else ""
        classification = (
            str(DOMAIN_CLASSIFICATION_SKILL_PAYLOAD["en"])
            if preserve_domain_classification
            else ""
        )
        instruction = domain_context + classification + self_verify + web_search + (
            "No answer choices are provided. Give the requested answer itself, not an option number or letter.\n"
            "Be concise while preserving every critical fact.\n"
            'Return only one JSON object: `{"finalAnswer":"answer content"}`.'
        )
    return f"{str(prompt or '').strip()}\n\n{instruction}".strip()


def infer_open_response_language(prompt: str, declared_language: str = "") -> str:
    text = str(prompt or "")
    hangul_count = len(re.findall(r"[가-힣]", text))
    latin_count = len(re.findall(r"[A-Za-z]", text))
    if hangul_count >= 2:
        return "ko"
    if latin_count >= 20 and hangul_count == 0:
        return "en"
    return str(declared_language or "").strip().lower()


def run_manifest(
    *,
    public_path: Path,
    output_dir: Path,
    llm_client: Any,
    model: str,
    resume: bool = False,
    max_cases: int = 0,
    case_ids: list[str] | None = None,
    include_needs_rewrite: bool = False,
    include_public_product_context: bool = False,
    single_pass_self_verify: bool = False,
    preserve_domain_classification: bool = False,
) -> dict[str, Any]:
    manifest = json.loads(public_path.read_text(encoding="utf-8"))
    if manifest.get("taskType") != "open_response":
        raise ValueError("expected taskType=open_response")
    if preserve_domain_classification and not include_public_product_context:
        raise ValueError("domain-classification skill requires public product context")
    if preserve_domain_classification and single_pass_self_verify:
        raise ValueError("domain-classification skill cannot be combined with single-pass self-verify")
    allowed = {str(value) for value in case_ids or [] if str(value)}
    cases = [case for case in manifest.get("cases", []) if isinstance(case, dict)]
    if allowed:
        cases = [case for case in cases if str(case.get("id") or "") in allowed]
    if not include_needs_rewrite:
        cases = [case for case in cases if is_official_ready(case)]
    if max_cases > 0:
        cases = cases[:max_cases]
    result_dir = output_dir / "results"
    result_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    started = time.monotonic()
    for case in cases:
        case_id = str(case.get("id") or "").strip()
        record_path = result_dir / f"{case_id}.json"
        if resume and record_path.exists():
            records.append(json.loads(record_path.read_text(encoding="utf-8")))
            continue
        case_started = time.monotonic()
        record: dict[str, Any] = {
            "id": case_id,
            "caseId": case_id,
            "benchmarkId": manifest.get("benchmarkId", ""),
            "sourceBenchmarkId": manifest.get("sourceBenchmarkId", ""),
            "mode": "codex_native_open_response",
            "prediction": None,
            "gold": None,
            "correct": None,
            "publicProductContextEnabled": bool(include_public_product_context),
            "singlePassSelfVerifyEnabled": bool(single_pass_self_verify),
            "domainClassificationSkillEnabled": bool(preserve_domain_classification),
            "domainClassificationSkillVersion": (
                DOMAIN_CLASSIFICATION_SKILL_VERSION if preserve_domain_classification else ""
            ),
            "domainClassificationSkillSha256": (
                DOMAIN_CLASSIFICATION_SKILL_SHA256 if preserve_domain_classification else ""
            ),
            "publicProduct": str(manifest.get("product") or ""),
            "conversionStatus": _conversion_status(case),
            "error": "",
        }
        try:
            effective_language = infer_open_response_language(
                str(case.get("prompt") or ""),
                str(case.get("language") or manifest.get("language") or ""),
            )
            record["effectiveLanguage"] = effective_language
            query = build_open_response_query(
                str(case.get("prompt") or ""),
                language=effective_language,
                product=str(manifest.get("product") or ""),
                include_public_product_context=include_public_product_context,
                single_pass_self_verify=single_pass_self_verify,
                preserve_domain_classification=preserve_domain_classification,
            )
            record["promptIdentity"] = prompt_identity(
                manifest=manifest,
                case=case,
                model_input=query,
                builder_id="open_response_query_v1",
                builder_source=Path(__file__),
            )
            answer = str(llm_client.complete([{"role": "user", "content": query}], model=model) or "")
            record["prediction"] = parse_short_answer_prediction(answer)
            record["answerPreview"] = answer[:2000]
            if not record["prediction"]:
                record["error"] = "invalid_open_response_json"
            consume_trace = getattr(llm_client, "consume_last_call_trace", None)
            if callable(consume_trace):
                record["modelTrace"] = consume_trace() or {}
        except Exception as exc:
            record["error"] = str(exc)[:1000]
        record["elapsedSec"] = round(time.monotonic() - case_started, 3)
        record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        records.append(record)
    durations = [float(record.get("elapsedSec") or 0.0) for record in records]
    summary = {
        "benchmarkId": manifest.get("benchmarkId", ""),
        "sourceBenchmarkId": manifest.get("sourceBenchmarkId", ""),
        "taskType": "open_response",
        "mode": "codex_native_open_response",
        "model": model,
        "publicProductContextEnabled": bool(include_public_product_context),
        "singlePassSelfVerifyEnabled": bool(single_pass_self_verify),
        "domainClassificationSkillEnabled": bool(preserve_domain_classification),
        "domainClassificationSkillVersion": (
            DOMAIN_CLASSIFICATION_SKILL_VERSION if preserve_domain_classification else ""
        ),
        "domainClassificationSkillSha256": (
            DOMAIN_CLASSIFICATION_SKILL_SHA256 if preserve_domain_classification else ""
        ),
        "selectionPolicy": "all_conversion_statuses" if include_needs_rewrite else "official_ready_only",
        "total": {
            "total": len(records),
            "predicted": sum(1 for record in records if record.get("prediction")),
            "errors": sum(1 for record in records if record.get("error")),
        },
        "latencySec": {
            "median": round(statistics.median(durations), 3) if durations else 0.0,
            "p95": round(_percentile(durations, 0.95), 3) if durations else 0.0,
            "maximum": round(max(durations), 3) if durations else 0.0,
            "perCaseHardLimit": MAX_REALTIME_SECONDS,
        },
        "elapsedSec": round(time.monotonic() - started, 3),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def _conversion_status(case: dict[str, Any]) -> str:
    metadata = case.get("metadata") if isinstance(case.get("metadata"), dict) else {}
    conversion = metadata.get("openResponseConversion") if isinstance(metadata.get("openResponseConversion"), dict) else {}
    return str(conversion.get("status") or "")


def is_official_ready(case: dict[str, Any]) -> bool:
    return _conversion_status(case) in OFFICIAL_READY_STATUSES


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * fraction + 0.999999)))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a choice-hidden open-response benchmark through a native model client.")
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--include-needs-rewrite", action="store_true")
    parser.add_argument("--public-product-context", action="store_true")
    parser.add_argument("--single-pass-self-verify", action="store_true")
    parser.add_argument("--preserve-domain-classification", action="store_true")
    args = parser.parse_args()
    if not heavy_cli_allowed():
        return 2
    timeout = min(MAX_REALTIME_SECONDS, max(1.0, float(args.timeout_seconds)))
    client = create_benchmark_llm_client(
        model=args.model,
        fallback_factory=default_llm_client_from_env,
        timeout_seconds=timeout,
    )
    if client is None:
        print(json.dumps({"status": "blocked", "reason": "no LLM client configured"}, ensure_ascii=False, indent=2))
        return 2
    summary = run_manifest(
        public_path=args.public,
        output_dir=args.output_dir,
        llm_client=client,
        model=args.model,
        resume=args.resume,
        max_cases=args.max_cases,
        case_ids=args.case_id,
        include_needs_rewrite=args.include_needs_rewrite,
        include_public_product_context=args.public_product_context,
        single_pass_self_verify=args.single_pass_self_verify,
        preserve_domain_classification=args.preserve_domain_classification,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
