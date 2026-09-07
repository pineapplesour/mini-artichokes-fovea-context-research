#!/usr/bin/env python3
"""Verify source-grounded answer quality artifacts for the beta6 products."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
PRODUCTS = ("islam", "tcm", "simli")
DEFAULT_MIN_ANSWER_CHARS = {"islam": 2200, "tcm": 2400, "simli": 1500}
DEFAULT_MIN_CITED_CLAIMS = {"islam": 6, "tcm": 3, "simli": 20}
DEFAULT_MIN_SOURCE_KINDS = {"islam": 2, "tcm": 3, "simli": 2}
DEFAULT_CASES = {
    "islam": RUNS / "actual_user_path_islam_depth_floor_20260507.json",
    "tcm": RUNS / "actual_user_path_tcm_depth_floor_20260507.json",
    "simli": RUNS / "actual_user_path_simli_depth_floor_20260507.json",
}


@dataclass(frozen=True)
class CaseSpec:
    product: str
    path: Path


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_product_int(values: list[str], defaults: dict[str, int]) -> dict[str, int]:
    out = dict(defaults)
    for value in values:
        if "=" not in value:
            raise SystemExit(f"expected product=value, got {value!r}")
        product, raw = value.split("=", 1)
        if product not in PRODUCTS:
            raise SystemExit(f"unknown product {product!r}")
        out[product] = int(raw)
    return out


def parse_cases(values: list[str]) -> list[CaseSpec]:
    if not values:
        return [CaseSpec(product, path) for product, path in DEFAULT_CASES.items()]
    cases = []
    for value in values:
        if "=" not in value:
            raise SystemExit(f"expected product=path, got {value!r}")
        product, raw_path = value.split("=", 1)
        if product not in PRODUCTS:
            raise SystemExit(f"unknown product {product!r}")
        path = Path(raw_path)
        if not path.is_absolute():
            path = ROOT / path
        cases.append(CaseSpec(product, path))
    return cases


def load_result(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    wrapper = read_json(path)
    if "answer" in wrapper and "sources" in wrapper:
        return wrapper, {"artifact": str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path)}
    if isinstance(wrapper.get("result"), dict):
        return wrapper["result"], wrapper
    job_id = wrapper.get("jobId")
    if job_id:
        result_path = RUNS / str(job_id) / "result.json"
        if result_path.exists():
            return read_json(result_path), wrapper
    raise ValueError(f"could not locate result payload for {path}")


def check(name: str, passes: bool, value: Any, expected: Any) -> dict[str, Any]:
    return {"name": name, "passes": bool(passes), "value": value, "expected": expected}


def answer_text(result: dict[str, Any]) -> str:
    return str(result.get("answer") or result.get("answerMarkdown") or "")


def citation_labels(answer: str) -> list[str]:
    return sorted(set(re.findall(r"\[(?:C|S)\d+\]", answer)))


def source_kind_set(result: dict[str, Any]) -> set[str]:
    kinds = set()
    for source in result.get("sources") or []:
        for key in ("sourceKind", "source_kind", "dataset", "authorityBody", "role"):
            value = source.get(key)
            if value:
                kinds.add(str(value))
                break
    return kinds


def quote_gate(result: dict[str, Any]) -> dict[str, Any]:
    beta6 = result.get("beta6") or {}
    analyzer = beta6.get("claimAnalyzer") or {}
    return analyzer.get("quoteGate") or {}


def quote_gate_verified_count(qgate: dict[str, Any]) -> int:
    return sum(int(qgate.get(key) or 0) for key in ("accepted", "forceMatched", "recovered"))


def passage_highlights_are_valid(result: dict[str, Any]) -> bool:
    windows = result.get("passageWindows") or []
    if not windows:
        return False
    valid = 0
    for item in windows:
        text = str(item.get("text") or "")
        start = item.get("highlightStart")
        end = item.get("highlightEnd")
        if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(text):
            valid += 1
    return valid > 0


def domain_boundary_passes(product: str, answer: str) -> bool:
    lowered = answer.lower()
    if product == "islam":
        return any(token in answer for token in ("학파", "종파", "파트와", "단정")) or "fatwa" in lowered
    if product == "tcm":
        return any(token in answer for token in ("진단", "처방", "한의사", "의사", "전문"))
    if product == "simli":
        return any(token in answer for token in ("진단", "전문가", "안전", "의뢰", "상담"))
    return False


def domain_structure_passes(product: str, answer: str) -> bool:
    if product == "simli":
        return all(
            heading in answer
            for heading in (
                "## 1. 가능 가설",
                "## 2. 왜 이 가설인가",
                "## 3. 추가 평가 필요",
                "## 4. 다음 세션 개입",
                "## 5. 약물 / 의뢰 고려",
                "## 6. 안전 계획",
                "## 7. 근거 한계",
                "## References",
            )
        )
    if product == "tcm":
        return all(token in answer for token in ("감초", "임신")) and any(token in answer for token in ("금기", "주의", "상담"))
    if product == "islam":
        return any(token in answer for token in ("학파", "종파", "견해", "입장"))
    return False


def beta6_status(result: dict[str, Any], key: str) -> Any:
    beta6 = result.get("beta6") or {}
    value = beta6.get(key)
    if value is not None:
        return value
    nested = beta6.get(key.removesuffix("Status")) or {}
    return nested.get("status") if isinstance(nested, dict) else None


def case_report(
    spec: CaseSpec,
    min_answer_chars: dict[str, int],
    min_cited_claims: dict[str, int],
    min_source_kinds: dict[str, int],
) -> dict[str, Any]:
    if not spec.path.exists():
        return {
            "product": spec.product,
            "path": str(spec.path),
            "passes": False,
            "error": "artifact missing",
            "checks": {"artifactExists": check("artifactExists", False, False, True)},
        }
    try:
        result, wrapper = load_result(spec.path)
    except Exception as exc:  # pragma: no cover - surfaced in JSON report
        return {
            "product": spec.product,
            "path": str(spec.path),
            "passes": False,
            "error": str(exc),
            "checks": {"loadResult": check("loadResult", False, "error", "result payload")},
        }

    answer = answer_text(result)
    labels = citation_labels(answer)
    sources = result.get("sources") or []
    claim_cards = result.get("claimCards") or []
    cited = result.get("citedClaimCards") or []
    candidate = result.get("candidateClaimCards") or []
    kinds = source_kind_set(result)
    qgate = quote_gate(result)
    selector_status = beta6_status(result, "selectorStatus")
    writer_status = beta6_status(result, "writerStatus")
    planner_status = ((result.get("beta6") or {}).get("answerPlanner") or {}).get("status")
    checks = {
        "artifactExists": check("artifactExists", True, True, True),
        "product": check("product", (result.get("product") or spec.product) == spec.product, result.get("product") or spec.product, spec.product),
        "sourceCount": check("sourceCount", len(sources) >= 100, len(sources), ">=100"),
        "claimCards": check("claimCards", len(claim_cards) >= 80, len(claim_cards), ">=80"),
        "candidateClaimCards": check("candidateClaimCards", len(candidate) > 0, len(candidate), ">0"),
        "citedClaimCards": check(
            "citedClaimCards",
            len(cited) >= min_cited_claims[spec.product],
            len(cited),
            f">={min_cited_claims[spec.product]}",
        ),
        "answerChars": check(
            "answerChars",
            len(answer) >= min_answer_chars[spec.product],
            len(answer),
            f">={min_answer_chars[spec.product]}",
        ),
        "citationUse": check("citationUse", bool(labels) and bool(result.get("citationMap")), labels, "answer contains [C#]/[S#] and citationMap"),
        "passageWindowHighlight": check("passageWindowHighlight", passage_highlights_are_valid(result), len(result.get("passageWindows") or []), ">=1 valid highlight"),
        "sourceKindDiversity": check(
            "sourceKindDiversity",
            len(kinds) >= min_source_kinds[spec.product],
            sorted(kinds)[:12],
            f">={min_source_kinds[spec.product]} kinds",
        ),
        "selectorCompleted": check("selectorCompleted", selector_status == "completed", selector_status, "completed"),
        "writerCompleted": check("writerCompleted", writer_status == "completed", writer_status, "completed"),
        "answerPlannerCompleted": check("answerPlannerCompleted", planner_status == "completed", planner_status, "completed"),
        "quoteGateVerified": check("quoteGateVerified", quote_gate_verified_count(qgate) > 0, quote_gate_verified_count(qgate), ">0 accepted/forceMatched/recovered"),
        "domainBoundary": check("domainBoundary", domain_boundary_passes(spec.product, answer), "present" if domain_boundary_passes(spec.product, answer) else "missing", "domain safety/boundary wording"),
        "domainStructure": check("domainStructure", domain_structure_passes(spec.product, answer), "present" if domain_structure_passes(spec.product, answer) else "missing", "product-specific answer structure"),
    }
    passes = all(item["passes"] for item in checks.values())
    return {
        "product": spec.product,
        "path": str(spec.path.relative_to(ROOT) if spec.path.is_relative_to(ROOT) else spec.path),
        "passes": passes,
        "jobId": wrapper.get("jobId") or result.get("jobId"),
        "query": wrapper.get("query") or result.get("query") or (wrapper.get("summary") or {}).get("query"),
        "metrics": {
            "answerChars": len(answer),
            "sourceCount": len(sources),
            "claimCardCount": len(claim_cards),
            "candidateClaimCardCount": len(candidate),
            "citedClaimCardCount": len(cited),
            "citationLabels": labels[:20],
            "sourceKinds": sorted(kinds)[:20],
            "quoteGate": qgate,
        },
        "checks": checks,
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    min_answer_chars = parse_product_int(args.min_answer_chars, DEFAULT_MIN_ANSWER_CHARS)
    min_cited_claims = parse_product_int(args.min_cited_claims, DEFAULT_MIN_CITED_CLAIMS)
    min_source_kinds = parse_product_int(args.min_source_kinds, DEFAULT_MIN_SOURCE_KINDS)
    cases = parse_cases(args.case)
    reports = [case_report(spec, min_answer_chars, min_cited_claims, min_source_kinds) for spec in cases]
    return {
        "passes": all(item["passes"] for item in reports),
        "caseCount": len(reports),
        "thresholds": {
            "minAnswerChars": min_answer_chars,
            "minCitedClaims": min_cited_claims,
            "minSourceKinds": min_source_kinds,
        },
        "cases": reports,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="write JSON to stdout")
    parser.add_argument("--output", help="write JSON report to this file")
    parser.add_argument("--case", action="append", default=[], help="product=artifact path; defaults to the current corpus")
    parser.add_argument("--min-answer-chars", action="append", default=[], help="override product minimum answer chars")
    parser.add_argument("--min-cited-claims", action="append", default=[], help="override product minimum cited claim count")
    parser.add_argument("--min-source-kinds", action="append", default=[], help="override product minimum source kind diversity")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(args)
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded + "\n", encoding="utf-8")
    if args.json:
        print(encoded)
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
