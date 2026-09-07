#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


SOURCE_LEAK_RE = re.compile(
    r"(?:\bcisi\b|\baqa\b|\bifq\b|islamic\s+finance\s+qualification|"
    r"official\s+sample|sample\s+questions?|past\s+papers?|question\s+papers?|"
    r"answer\s+keys?|mark\s+schemes?|quizlet|coursehero|studocu|"
    r"공식\s*샘플|기출\s*문제|문제집|정답지|답안지)",
    re.IGNORECASE,
)
URL_LEAK_RE = re.compile(
    r"(?:cisi|/aqa|sample[-_]?question|question[-_]?paper|past[-_]?paper|"
    r"answer[-_]?key|mark[-_]?scheme|quizlet|coursehero|studocu)",
    re.IGNORECASE,
)
LOCAL_READ_RE = re.compile(
    r"(?:^|[;&|]\s*|\s)(?:cat|sed|rg|grep|find|ls|head|tail|awk|cut|strings|"
    r"curl|wget|git)\s|(?:benchmarks|runs|artifacts|/home/|/mnt/|\.json\b|\.txt\b)",
    re.IGNORECASE,
)
CALCULATION_RE = re.compile(r"^\s*(?:python3?|node|bc)\b", re.IGNORECASE)
OPTION_LINE_RE = re.compile(r"(?m)^\s*(?:[A-E]|[1-5]|[①②③④⑤])[.、):：]?\s+(.+?)\s*$")


def audit(
    *,
    public_path: Path,
    results_dir: Path,
    case_ids: list[str] | None = None,
    require_search_evidence: bool = False,
) -> dict[str, Any]:
    manifest = json.loads(public_path.read_text(encoding="utf-8"))
    cases = {str(item.get("id") or ""): item for item in manifest.get("cases") or []}
    if case_ids:
        requested = {str(item) for item in case_ids}
        missing = sorted(requested - set(cases))
        if missing:
            raise ValueError(f"case IDs are absent from public manifest: {missing}")
        cases = {case_id: case for case_id, case in cases.items() if case_id in requested}
    violations: list[dict[str, str]] = []
    per_case: list[dict[str, Any]] = []
    trace_cases = 0
    search_cases = 0
    query_count = 0
    command_cases = 0
    command_count = 0
    for case_id, case in cases.items():
        artifact_path = results_dir / f"{case_id}.json"
        if not artifact_path.is_file():
            violations.append({"caseId": case_id, "kind": "missing_artifact", "detail": str(artifact_path)})
            continue
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        trace = artifact.get("modelTrace")
        trace_attempts = artifact.get("modelTraceAttempts")
        traces = (
            [item for item in trace_attempts if isinstance(item, dict)]
            if isinstance(trace_attempts, list) and trace_attempts
            else [trace] if isinstance(trace, dict) else []
        )
        if not traces:
            violations.append({"caseId": case_id, "kind": "missing_trace", "detail": "modelTrace absent"})
            continue
        trace_cases += 1
        if any(item.get("webSearchEnabled") is not True for item in traces):
            violations.append({"caseId": case_id, "kind": "search_not_enabled", "detail": "one or more traces"})
        web_events = [
            event
            for item in traces
            for event in (item.get("webSearchEvents") if isinstance(item.get("webSearchEvents"), list) else [])
        ]
        command_events = [
            event
            for item in traces
            for event in (
                item.get("commandExecutionEvents")
                if isinstance(item.get("commandExecutionEvents"), list)
                else []
            )
        ]
        queries: list[str] = []
        opened_urls: list[str] = []
        for event in web_events:
            if not isinstance(event, dict):
                continue
            query = str(event.get("query") or "").strip()
            action = event.get("action") if isinstance(event.get("action"), dict) else {}
            if query and query not in queries:
                queries.append(query)
            for key in ("url", "link"):
                value = str(action.get(key) or "").strip()
                if value and value not in opened_urls:
                    opened_urls.append(value)
        commands = [
            str(event.get("command") or "").strip()
            for event in command_events
            if isinstance(event, dict) and str(event.get("command") or "").strip()
        ]
        if queries:
            search_cases += 1
            query_count += len(queries)
        if require_search_evidence:
            requirement = artifact.get("webSearchRequirement")
            if not queries:
                violations.append(
                    {"caseId": case_id, "kind": "required_web_search_missing", "detail": "zero search queries"}
                )
            if not isinstance(requirement, dict) or requirement.get("satisfied") is not True:
                violations.append(
                    {
                        "caseId": case_id,
                        "kind": "search_evidence_requirement_unsatisfied",
                        "detail": str(requirement),
                    }
                )
            elif not str(requirement.get("searchEvidence") or "").strip():
                violations.append(
                    {"caseId": case_id, "kind": "missing_search_evidence", "detail": "empty evidence summary"}
                )
        if commands:
            command_cases += 1
            command_count += len(commands)
        prompt = str(case.get("prompt") or "")
        for query in queries:
            for kind, detail in _query_violations(query, prompt):
                violations.append({"caseId": case_id, "kind": kind, "detail": detail})
        for url in opened_urls:
            if URL_LEAK_RE.search(url):
                violations.append({"caseId": case_id, "kind": "prohibited_url", "detail": url[:500]})
        for command in commands:
            if LOCAL_READ_RE.search(command):
                violations.append({"caseId": case_id, "kind": "local_file_access_command", "detail": command[:500]})
            elif not CALCULATION_RE.match(command):
                violations.append({"caseId": case_id, "kind": "non_calculation_command", "detail": command[:500]})
        per_case.append(
            {
                "caseId": case_id,
                "queries": queries,
                "openedUrls": opened_urls,
                "commands": commands,
            }
        )
    return {
        "schemaVersion": 1,
        "benchmarkId": str(manifest.get("benchmarkId") or ""),
        "cases": len(cases),
        "traceCases": trace_cases,
        "webSearchCases": search_cases,
        "webSearchQueryCount": query_count,
        "commandExecutionCases": command_cases,
        "commandExecutionCount": command_count,
        "searchEvidenceRequired": require_search_evidence,
        "violationCount": len(violations),
        "passed": not violations and trace_cases == len(cases),
        "violations": violations,
        "perCase": per_case,
    }


def _query_violations(query: str, prompt: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if SOURCE_LEAK_RE.search(query):
        found.append(("source_or_answer_search", query[:500]))
    query_normalized = _normalize(query)
    prompt_lines = [line.strip() for line in prompt.splitlines() if line.strip()]
    stem = prompt_lines[0] if prompt_lines else prompt
    stem = re.sub(r"^\s*\d+[.)]\s*", "", stem)
    stem_normalized = _normalize(stem)
    if len(query_normalized) >= 28 and stem_normalized:
        if query_normalized in stem_normalized or SequenceMatcher(None, query_normalized, stem_normalized).ratio() >= 0.82:
            found.append(("near_exact_stem_search", query[:500]))
    query_tokens = _tokens(query)
    prompt_tokens = _tokens(prompt)
    if len(query_tokens) >= 7 and _contains_consecutive_ngram(prompt_tokens, query_tokens, width=7):
        found.append(("long_prompt_phrase_search", query[:500]))
    for option in OPTION_LINE_RE.findall(prompt):
        normalized = _normalize(option)
        if len(normalized) >= 12 and normalized in query_normalized:
            found.append(("exact_option_search", query[:500]))
            break
    if re.search(r"(?:^|\s)[A-E][.):]\s|(?:①|②|③|④|⑤)", query):
        found.append(("answer_choice_marker_search", query[:500]))
    return found


def _normalize(value: str) -> str:
    return " ".join(re.findall(r"[0-9A-Za-z가-힣%$]+", str(value or "").lower()))


def _tokens(value: str) -> list[str]:
    return re.findall(r"[0-9A-Za-z가-힣%$]+", str(value or "").lower())


def _contains_consecutive_ngram(haystack: list[str], needle: list[str], *, width: int) -> bool:
    if len(needle) < width or len(haystack) < width:
        return False
    haystack_ngrams = {tuple(haystack[index : index + width]) for index in range(len(haystack) - width + 1)}
    return any(
        tuple(needle[index : index + width]) in haystack_ngrams
        for index in range(len(needle) - width + 1)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit web-enabled Direct benchmark traces for question leakage.")
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--require-search-evidence", action="store_true")
    args = parser.parse_args()
    report = audit(
        public_path=args.public,
        results_dir=args.results_dir,
        case_ids=args.case_id,
        require_search_evidence=args.require_search_evidence,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
