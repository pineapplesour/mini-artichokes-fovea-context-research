#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared_platform.domain_adapters import get_domain_adapter
from tools.build_unified_benchmark_manifests import _correct_option_text


OPTION_MARKER_RE = re.compile(
    r"^\s*(?:[①②③④⑤⑥⑦⑧⑨⑩❶❷❸❹❺❻❼❽❾⓵⓶⓷⓸⓹]|[([]?[A-Ea-e][)\].、:：]|[([]?[1-9]\d?[)\]、:：])\s*\S"
)
CIRCLED_OPTION_RE = re.compile(r"^\s*[①②③④⑤⑥⑦⑧⑨⑩❶❷❸❹❺❻❼❽❾⓵⓶⓷⓸⓹]\s*\S")
OPEN_SET_RISK_RE = re.compile(
    r"(?:"
    r"다음\s*중|다음\s+[^?？\n]{1,24}\s+중|(?:가장\s+)?(?:좋은|적절한)\s+(?:예|사례)|"
    r"다음(?:이|을)?\s*포함(?:됩니다|된다)|다음과\s*같은\s*이유|"
    r"옳(?:지)?\s*않|옳은\s*것|옳게\s*[^?？\n]{0,24}(?:것|나열)|적절(?:하지)?\s*않|적절한\s*것|"
    r"적절한\s*(?:치료(?:법)?|처치|약물?|외용제|중재|관리)(?:은|는|인가)?|"
    r"일치(?:하지)?\s*않|일치하는\s*것|타당(?:하지)?\s*않|바르(?:지)?\s*않|"
    r"아닌\s*(?:것|사람|경우|항목|대상)|(?:포함|해당|속하|일치하)(?:되)?지\s*않|맞지\s*않|예외|"
    r"좋은\s*(?:경우|것)|주의(?:해야\s*)?할\s*것|유의(?:해야\s*)?할\s*것|"
    r"잘못\s*[^?？\n]{0,24}(?:경우|것)|"
    r"(?:관찰|나타날)\s*(?:할\s*수\s*있는|되는)\s*(?:특징|소견|증상)|"
    r"생활\s*관리|(?:환자\s*)?(?:교육|지도)(?:해야|할)?\s*(?:내용|사항|것)|"
    r"(?:쓸|사용할|시행할|적용할)\s*수\s*있는\s*(?:경우|사람)|"
    r"어떤\s*상황에서[^?？\n]{0,48}(?:수\s*없|않)|"
    r"which\s+(?:of\s+(?:the\s+following|these)|one\s+of\s+the|answer\s+below|statement)|"
    r"which\s+other\b|"
    r"(?:which|what)\s+(?:is|are|was|were)\s+(?:not\s+)?(?:true|false|correct|incorrect)|"
    r"which\s+is\s+(?:an?\s+example|the\s+best\s+description)|not\s+true\b|true\s+of\b|"
    r"(?:in)?correct\s+(?:statement|answer)|true\s+(?:statement|answer)|false\s+(?:statement|answer)|"
    r"choose\s+(?:the|an)|except\b|"
    r"assinale|marque\b|alternativa\b|op(?:ç|c)[aã]o\b|(?:é|e)\s+correto\s+(?:dizer|afirmar)|"
    r"afirma(?:ção|cao)\s+(?:correta|incorreta)"
    r")",
    re.IGNORECASE,
)
OPTION_ONLY_ANSWER_RE = re.compile(
    r"^\s*(?:[A-Ea-e]|\d{1,2}|[①②③④⑤⑥⑦⑧⑨⑩]|[ㄱ-ㅎ](?:\s*[,·]\s*[ㄱ-ㅎ])*)\s*$"
)
EXTRACTIVE_REFERENCE_RE = re.compile(
    r"(?:refere-se\s+a|refers?\s+to|가리키는|지칭하는|밑줄.*의미|문맥.*의미)",
    re.IGNORECASE,
)
EXPLICIT_QUESTION_CUE_RE = re.compile(
    r"(?:[?？]|(?:^|\n)\s*(?:\[?문제\]?|\d+[.)]?\s*문제)\s*:|"
    r"(?:무엇|누구|어디|언제|어느|몇)(?:인가|입니까|이냐|인지)?|"
    r"(?:구|쓰|기술|설명|제시|서술|답)하시오|"
    r"\b(?:what|which|who|when|where|how)\b)",
    re.IGNORECASE,
)
DECLARATIVE_LIST_INTRO_RE = re.compile(
    r"(?:다음과\s*(?:같습니다|같다)|as\s+follows)\s*[.:：]?\s*$",
    re.IGNORECASE,
)
CORRUPT_REFERENCE_RE = re.compile(r"^[A-Z]{2,8}[\)\]\}]+$")
TCM_PRIVATE_STIMULUS_RE = re.compile(r"<\s*자료\s*\(\s*비공개\s*\)\s*>")
TCM_PRESCRIPTION_SELECTION_RE = re.compile(r"(?:처방|치방)(?:은|이|을|를)?(?:\s*(?:무엇|어느|인가))?\s*[?？]?")
TCM_OCR_PRESCRIPTION_SELECTION_RE = re.compile(r"지방(?:은|이|을|를)?\s*[?？]?\s*$")
TCM_FORMULA_REFERENCE_RE = re.compile(r"(?:탕|산|환|음|고|단|원)(?:\s*\([^)]*\))?\s*$")
TCM_SUSPICIOUS_ASCII_TOKEN_RE = re.compile(r"(?<![A-Za-z])[A-Z]{2,8}(?![A-Za-z])")
TCM_ALLOWED_ASCII_TOKENS = {
    "ALT",
    "AST",
    "BP",
    "BUN",
    "CBC",
    "CDR",
    "COPD",
    "CRP",
    "CT",
    "ECG",
    "EKG",
    "ESR",
    "GCS",
    "HB",
    "HCT",
    "HR",
    "MRI",
    "RBC",
    "WBC",
}
TCM_CURATED_REFERENCE_ALIASES = {
    "지류(脂瘤)": ("표피낭종", "표피양 낭종", "epidermal cyst", "epidermoid cyst"),
    "CDR(Clinical Dementia Rating)": (
        "치매임상평가척도",
        "치매 임상 평가 척도",
        "임상치매평가척도",
        "임상 치매 평가 척도",
        "CDR",
    ),
}
CURATED_REFERENCE_ALIASES_BY_PRODUCT = {
    "simli": {
        "(a) anchoring; (b) representativeness; (c) availability": (
            "anchoring, representativeness, and availability",
            "anchoring and adjustment; representativeness; availability",
        ),
    },
}


@dataclass(frozen=True)
class PromptSplit:
    stem: str
    option_count: int
    method: str


def convert_mcq_split(
    public_manifest: dict[str, Any],
    private_manifest: dict[str, Any],
    *,
    benchmark_id: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    if public_manifest.get("taskType") != "mcq":
        raise ValueError("open-response conversion requires taskType=mcq")
    source_benchmark_id = str(public_manifest.get("benchmarkId") or "").strip()
    if not source_benchmark_id or source_benchmark_id != str(private_manifest.get("benchmarkId") or "").strip():
        raise ValueError("public/private benchmark IDs must match")
    active_benchmark_id = benchmark_id.strip() or _default_open_response_id(source_benchmark_id)
    product = str(public_manifest.get("product") or "").strip()
    answer_by_id = {
        str(item.get("caseId") or ""): str(item.get("correctOptionId") or "")
        for item in private_manifest.get("answers", [])
        if isinstance(item, dict) and item.get("caseId")
    }

    public_cases: list[dict[str, Any]] = []
    private_answers: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    method_counts: Counter[str] = Counter()
    seen_case_ids: set[str] = set()
    for case in public_manifest.get("cases", []):
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("id") or "").strip()
        if not case_id or case_id in seen_case_ids:
            raise ValueError(f"invalid or duplicate case id: {case_id!r}")
        seen_case_ids.add(case_id)
        correct_option_id = answer_by_id.get(case_id, "")
        if not correct_option_id:
            raise ValueError(f"missing private answer for {case_id}")
        original_prompt = str(case.get("prompt") or "").strip()
        reference_answer = _correct_option_text(original_prompt, correct_option_id).strip()
        if not reference_answer:
            raise ValueError(f"could not recover correct option text for {case_id}")
        split = split_mcq_prompt(original_prompt, product=product)
        if not split.stem or split.option_count < 2:
            raise ValueError(f"could not remove answer choices for {case_id}")
        status, risk_reasons = classify_conversion(split.stem, reference_answer, product=product)
        aliases = _reference_aliases(reference_answer, product=product)
        metadata = dict(case.get("metadata") or {})
        metadata["openResponseConversion"] = {
            "sourceTaskType": "mcq",
            "status": status,
            "riskReasons": risk_reasons,
            "optionCountRemoved": split.option_count,
            "splitMethod": split.method,
        }
        public_cases.append(
            {
                "id": case_id,
                "prompt": split.stem,
                "metadata": metadata,
                "graderRef": str(case.get("graderRef") or case_id),
            }
        )
        private_answers.append(
            {
                "caseId": case_id,
                "canonicalAnswer": reference_answer,
                "aliases": aliases,
                "sourceCorrectOptionId": correct_option_id,
                "conversionStatus": status,
                "keywordRules": {
                    "autoConfirm": False,
                    "mustIncludeGroups": [],
                    "mustNotIncludeAny": [],
                },
            }
        )
        status_counts[status] += 1
        method_counts[split.method] += 1

    if len(public_cases) != len(answer_by_id):
        missing_public = sorted(set(answer_by_id) - seen_case_ids)
        raise ValueError(f"public/private case count mismatch; missing public cases: {missing_public[:10]}")
    audit = {
        "sourceCases": len(public_cases),
        "convertedCases": len(public_cases),
        "statusCounts": dict(sorted(status_counts.items())),
        "splitMethodCounts": dict(sorted(method_counts.items())),
        "officialRunDefault": "ready_hide_options_only",
    }
    public = {
        "schemaVersion": 2,
        "benchmarkId": active_benchmark_id,
        "sourceBenchmarkId": source_benchmark_id,
        "taskType": "open_response",
        "product": product,
        "language": public_manifest.get("language", ""),
        "conversionAudit": audit,
        "cases": public_cases,
    }
    private = {
        "schemaVersion": 2,
        "benchmarkId": active_benchmark_id,
        "sourceBenchmarkId": source_benchmark_id,
        "answers": private_answers,
        "scoring": {
            "version": "open_response_semantic_v1",
            "deterministicOrder": ["normalized_exact", "declared_alias_exact", "explicit_keyword_rule"],
            "semanticJudge": {
                "defaultModel": "gpt-5.6-luna",
                "wrongChoicesVisibleToJudge": False,
                "initialIndependentRepeats": 2,
                "tieBreakRepeatOnDisagreement": True,
            },
            "invalidPrediction": "wrong",
            "unresolvedJudgeDecision": "unresolved_not_correct",
        },
        "conversionAudit": audit,
    }
    return public, private


def split_mcq_prompt(prompt: str, *, product: str) -> PromptSplit:
    parsed = get_domain_adapter(product).parse_multiple_choice(prompt)
    if parsed is not None and len(parsed.options) >= 2 and parsed.stem.strip():
        return PromptSplit(stem=parsed.stem.strip(), option_count=len(parsed.options), method="domain_adapter")
    lines = str(prompt or "").splitlines()
    circled_indexes = [index for index, line in enumerate(lines) if CIRCLED_OPTION_RE.match(line)]
    if len(circled_indexes) >= 2:
        first = circled_indexes[0]
        stem = "\n".join(lines[:first]).strip()
        if stem:
            return PromptSplit(stem=stem, option_count=len(circled_indexes), method="circled_fallback")
    option_indexes = [index for index, line in enumerate(lines) if OPTION_MARKER_RE.match(line)]
    if len(option_indexes) >= 2:
        first = option_indexes[0]
        if first == 0 and len(option_indexes) >= 3:
            first = option_indexes[1]
        stem = "\n".join(lines[:first]).strip()
        if stem:
            return PromptSplit(stem=stem, option_count=len(option_indexes) - (1 if option_indexes[0] == 0 else 0), method="generic_fallback")
    return PromptSplit(stem="", option_count=0, method="failed")


def classify_conversion(stem: str, reference_answer: str, *, product: str = "") -> tuple[str, list[str]]:
    reasons: list[str] = []
    normalized_product = str(product or "").strip().lower()
    question_scope = _conversion_question_scope(stem)
    if OPEN_SET_RISK_RE.search(question_scope):
        reasons.append("open_set_or_choice_dependent_stem")
    if (
        normalized_product == "lawkey"
        or DECLARATIVE_LIST_INTRO_RE.search(str(stem or ""))
    ) and not EXPLICIT_QUESTION_CUE_RE.search(str(stem or "")):
        reasons.append("missing_explicit_open_response_question")
    if OPTION_ONLY_ANSWER_RE.fullmatch(str(reference_answer or "")):
        reasons.append("reference_is_option_label_or_combination_only")
    if CORRUPT_REFERENCE_RE.fullmatch(str(reference_answer or "").strip()) or (
        normalized_product == "tcm" and _looks_like_tcm_reference_corruption(reference_answer)
    ):
        reasons.append("reference_looks_ocr_corrupted")
    if normalized_product == "tcm":
        if _looks_like_tcm_ocr_corruption(stem):
            reasons.append("source_text_looks_ocr_corrupted_or_missing_stimulus")
        if TCM_PRESCRIPTION_SELECTION_RE.search(question_scope) or (
            TCM_OCR_PRESCRIPTION_SELECTION_RE.search(question_scope)
            and TCM_FORMULA_REFERENCE_RE.search(str(reference_answer or ""))
        ):
            reasons.append("tcm_prescription_not_unique_without_choices")
    compact_stem = _compact_text(stem)
    compact_answer = _compact_text(reference_answer)
    if len(compact_answer) >= 2 and compact_answer in compact_stem and not EXTRACTIVE_REFERENCE_RE.search(stem):
        reasons.append("reference_answer_text_present_in_stem")
    if reasons:
        return "needs_semantic_rewrite", reasons
    return "ready_hide_options", []


def _conversion_question_scope(stem: str) -> str:
    lines = str(stem or "").splitlines()
    if len(lines) <= 16:
        return "\n".join(lines)
    indexes = set(range(min(8, len(lines))))
    indexes.update(range(max(0, len(lines) - 8), len(lines)))
    for index, line in enumerate(lines):
        if "?" in line or "？" in line or re.search(r"(?:\[?문제\]?|문항)\s*:?", line):
            indexes.update(range(max(0, index - 1), min(len(lines), index + 3)))
    return "\n".join(lines[index] for index in sorted(indexes))


def _looks_like_tcm_ocr_corruption(stem: str) -> bool:
    value = str(stem or "")
    if TCM_PRIVATE_STIMULUS_RE.search(value):
        return True
    if re.search(r"\b[A-Z]{2,8}\s*[?？]", value):
        return True
    if re.search(r"\b[A-Z]{2,8}\s+(?:한다|하고|하며|이다|있다|된다)\b", value):
        return True
    if re.search(r"[A-Za-z]{2,8}[\]\}]", value):
        return True
    tokens = TCM_SUSPICIOUS_ASCII_TOKEN_RE.findall(value)
    unknown = [token for token in tokens if token not in TCM_ALLOWED_ASCII_TOKENS]
    if any(re.search(rf"\b{re.escape(token)}\s+[가-힣]", value) for token in unknown):
        return True
    return len(unknown) >= 2


def _looks_like_tcm_reference_corruption(reference_answer: str) -> bool:
    value = str(reference_answer or "").strip()
    return bool(re.search(r"[{}\[\]]", value))


def _compact_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return "".join(character for character in normalized if character.isalnum())


def _reference_aliases(reference_answer: str, *, product: str) -> list[str]:
    canonical = " ".join(str(reference_answer or "").split())
    values = get_domain_adapter(product).option_aliases(canonical)
    aliases: list[str] = []
    for value in values:
        cleaned = " ".join(str(value or "").split())
        if cleaned and cleaned != canonical and cleaned not in aliases:
            aliases.append(cleaned)
    if str(product or "").strip().lower() == "tcm":
        for value in TCM_CURATED_REFERENCE_ALIASES.get(canonical, ()):
            cleaned = " ".join(str(value or "").split())
            if cleaned and cleaned != canonical and cleaned not in aliases:
                aliases.append(cleaned)
    for value in CURATED_REFERENCE_ALIASES_BY_PRODUCT.get(
        str(product or "").strip().lower(), {}
    ).get(canonical, ()):
        cleaned = " ".join(str(value or "").split())
        if cleaned and cleaned != canonical and cleaned not in aliases:
            aliases.append(cleaned)
    return aliases


def _default_open_response_id(source_benchmark_id: str) -> str:
    value = source_benchmark_id
    if value.startswith("mcq."):
        value = "open_response." + value[len("mcq.") :]
    else:
        value = "open_response." + value
    if value.endswith(".v1"):
        value = value[:-3] + ".v2"
    elif not value.endswith(".v2"):
        value += ".v2"
    return value


def build_registry(registry_path: Path, output_dir: Path) -> dict[str, Any]:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    benchmark_root = registry_path.parent
    pending: list[tuple[Path, dict[str, Any]]] = []
    entries: list[dict[str, Any]] = []
    total = 0
    ready = 0
    rewrite = 0
    for entry in registry.get("canonicalExamAggregate", {}).get("entries", []):
        public_path = benchmark_root / str(entry.get("publicManifest") or "")
        private_path = benchmark_root / str(entry.get("privateManifest") or "")
        public_source = json.loads(public_path.read_text(encoding="utf-8"))
        if public_source.get("taskType") != "mcq":
            continue
        private_source = json.loads(private_path.read_text(encoding="utf-8"))
        public, private = convert_mcq_split(public_source, private_source)
        public_name = "open_response_" + public_path.name.removeprefix("mcq_")
        private_name = "open_response_" + private_path.name.removeprefix("mcq_")
        public_out = output_dir / public_name
        private_out = output_dir / private_name
        pending.extend(((public_out, public), (private_out, private)))
        counts = public["conversionAudit"]["statusCounts"]
        case_count = len(public["cases"])
        total += case_count
        ready += int(counts.get("ready_hide_options", 0))
        rewrite += int(counts.get("needs_semantic_rewrite", 0))
        entries.append(
            {
                "benchmarkId": public["benchmarkId"],
                "sourceBenchmarkId": public["sourceBenchmarkId"],
                "publicManifest": public_name,
                "privateManifest": private_name,
                "cases": case_count,
                "statusCounts": counts,
            }
        )
    output_registry = {
        "schemaVersion": 2,
        "registryId": "universal-engine-open-response-v2",
        "sourceRegistryId": registry.get("registryId", ""),
        "totalConvertedMcqCases": total,
        "readyHideOptionsCases": ready,
        "needsSemanticRewriteCases": rewrite,
        "entries": entries,
    }
    pending.append((output_dir / "evaluation_registry.open_response.json", output_registry))
    output_dir.mkdir(parents=True, exist_ok=True)
    for path, payload in pending:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_registry


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert answer-separated MCQ manifests to choice-hidden open-response candidates.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    pair = subparsers.add_parser("pair")
    pair.add_argument("--public", type=Path, required=True)
    pair.add_argument("--private", type=Path, required=True)
    pair.add_argument("--public-out", type=Path, required=True)
    pair.add_argument("--private-out", type=Path, required=True)
    pair.add_argument("--benchmark-id", default="")
    registry = subparsers.add_parser("registry")
    registry.add_argument("--registry", type=Path, required=True)
    registry.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "registry":
        result = build_registry(args.registry, args.output_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    public_source = json.loads(args.public.read_text(encoding="utf-8"))
    private_source = json.loads(args.private.read_text(encoding="utf-8"))
    public, private = convert_mcq_split(public_source, private_source, benchmark_id=args.benchmark_id)
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    args.private_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_out.write_text(json.dumps(public, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.private_out.write_text(json.dumps(private, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(public["conversionAudit"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
