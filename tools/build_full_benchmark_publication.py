#!/usr/bin/env python3
"""Build the private GitHub benchmark publication from manifests and run artifacts.

The generated bundle intentionally contains private answer keys and verbatim model
answers. It is suitable for the repository's current PRIVATE visibility. Do not
publish the generated bundle publicly without a separate rights and privacy review.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


PUBLICATION_DATE = "2026-07-17"
SCHEMA_VERSION = 1

CIRCLED = {
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
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_answer(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    first = raw[0]
    if first in CIRCLED:
        return CIRCLED[first]
    match = re.match(r"\s*([A-Ea-e]|\d{1,2})", raw)
    if not match:
        return ""
    token = match.group(1)
    return token.upper() if token.isalpha() else token


def option_texts(prompt: str) -> dict[str, str]:
    options: dict[str, str] = {}
    patterns = (
        re.compile(r"^\s*([A-Ea-e])[.)、:：]\s*(.+?)\s*$"),
        re.compile(r"^\s*([1-9]\d?)[.)、:：]\s*(.+?)\s*$"),
        re.compile(r"^\s*([①②③④⑤⑥⑦⑧⑨⑩❶❷❸❹❺])\s*(.+?)\s*$"),
    )
    for line in str(prompt or "").splitlines():
        for pattern in patterns:
            match = pattern.match(line)
            if not match:
                continue
            key = normalize_answer(match.group(1))
            if key:
                options[key] = re.sub(r"\s+", " ", match.group(2).strip())
            break
    return options


def evidence_summary(record: dict[str, Any]) -> list[dict[str, Any]]:
    summarized: list[dict[str, Any]] = []
    for item in list(record.get("selectedEvidence") or []):
        if not isinstance(item, dict):
            continue
        summarized.append(
            {
                key: item.get(key)
                for key in (
                    "id",
                    "sourceId",
                    "recordId",
                    "citation",
                    "title",
                    "sourceKind",
                    "authorityLevel",
                    "score",
                    "verdict",
                )
                if item.get(key) not in (None, "")
            }
        )
    return summarized


def model_metadata(record: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(record.get("modelMetadata") or {})
    if not metadata and record.get("llmModel"):
        metadata = {
            "provider": record.get("llmProvider"),
            "model": record.get("llmModel"),
        }
    return metadata


def protocols() -> list[dict[str, Any]]:
    common_luna = {
        "provider": "codex_exec",
        "model": "gpt-5.6-luna",
        "reasoningEffort": "low",
        "verbosity": "low",
        "transportMaxAttempts": 2,
        "transportWorkerThreads": 1,
        "batching": "one_case_per_model_call",
        "sandbox": "read-only",
    }
    return [
        {
            "id": "source.tcm.beta6.20260606",
            "kind": "source_provided_historical_run",
            "model": "unknown",
            "internet": "unknown",
            "modelCodeTools": "unknown",
            "structure": "The Wikia post explicitly identifies the run as beta6; exact model and tool policy are absent.",
            "notWikiaBuiltInAI": True,
        },
        {
            "id": "source.islam.answer_fields.20260613",
            "kind": "source_provided_historical_run",
            "model": "unknown",
            "internet": "unknown",
            "modelCodeTools": "unknown",
            "structure": "Answers were recorded in source files. Eight abstentions refer to supplied religious texts, but the exact engine receipt is absent.",
            "notWikiaBuiltInAI": True,
        },
        {
            "id": "source.leet.lawkey_ai.20260717",
            "kind": "source_provided_historical_run",
            "model": "unknown",
            "internet": "unknown",
            "modelCodeTools": "unknown",
            "structure": "The post title says LawKey AI; analysis mode, model, retrieval, web, and code settings were not recorded.",
            "notWikiaBuiltInAI": True,
        },
        {
            "id": "luna.direct.closed_book.per_case",
            **common_luna,
            "internet": "forbidden",
            "modelCodeTools": "forbidden",
            "localFileInspection": "forbidden",
            "databaseRetrieval": False,
            "structure": "Question-only stateless completion; no evidence packet.",
        },
        {
            "id": "luna.frozen_beta6.db.per_case",
            **common_luna,
            "internet": "forbidden",
            "modelCodeTools": "forbidden",
            "localFileInspection": "forbidden",
            "databaseRetrieval": True,
            "baselineCommit": "45af71ff7bc6efc0ae03727cdb043bcdec82006e",
            "baselineTree": "84d670dd1914f77d7c323c89d01e4502b30500c1",
            "structure": "Frozen beta6 engine searches the mounted SQLite corpus, selects evidence, and gives it to Luna. Luna itself cannot call tools.",
        },
        {
            "id": "luna.universal.db.per_case",
            **common_luna,
            "internet": "forbidden",
            "modelCodeTools": "forbidden",
            "localFileInspection": "forbidden",
            "databaseRetrieval": True,
            "structure": "Shared domain-independent query planning, SQLite candidate retrieval, evidence selection, and evidence-grounded answer writing.",
        },
        {
            "id": "luna.direct.web_optional.wrong_only",
            **common_luna,
            "internet": "allowed_optional",
            "modelCodeTools": "read-only calculation shell allowed",
            "localFileInspection": "forbidden",
            "problemSheetSearch": "forbidden",
            "structure": "Gold-informed wrong-only retry. General concept search was optional; exact stems, choices, exam, benchmark, and answer-key searches were blocked and audited.",
        },
        {
            "id": "luna.direct.web_required.wrong_only",
            **common_luna,
            "internet": "required",
            "modelCodeTools": "read-only calculation shell allowed",
            "localFileInspection": "forbidden",
            "problemSheetSearch": "forbidden",
            "structure": "Twice-selected wrong-only retry. Every accepted response required a completed generalized web search and a nonempty search-evidence line.",
        },
        {
            "id": "luna.evidence_arbiter.tcm_disagreements",
            **common_luna,
            "internet": "forbidden",
            "modelCodeTools": "forbidden",
            "databaseRetrieval": "uses already-selected Universal evidence",
            "structure": "Gold-free post-hoc choice between Direct and Universal only on their 22 disagreements. Rejected after no net gain.",
        },
        {
            "id": "solpro.direct.closed_book.legal10.batch",
            "provider": "chatgpt_browser",
            "model": "gpt-5-6-pro",
            "reasoningEffort": "Pro",
            "internet": "forbidden",
            "modelCodeTools": "forbidden",
            "databaseRetrieval": False,
            "batching": "10_variants_one_conversation",
            "structure": "One public-only legal packet attached to one closed-book ChatGPT conversation.",
        },
        {
            "id": "solpro.direct.closed_book.tcm92.batch",
            "provider": "chatgpt_browser",
            "model": "gpt-5-6-pro",
            "reasoningEffort": "Pro",
            "internet": "forbidden",
            "modelCodeTools": "forbidden",
            "databaseRetrieval": False,
            "batching": "92_mcqs_one_conversation",
            "structure": "One public-only 92-item packet attached to one closed-book ChatGPT conversation.",
        },
        {
            "id": "luna.semantic_judge.legal.two_repetitions",
            **common_luna,
            "internet": "forbidden",
            "modelCodeTools": "forbidden",
            "batching": "two_independent_judgments_per_artifact",
            "structure": "Private rubric and required authorities judge substantive use, legal application, and grounding. This is a grader, not an answer arm.",
        },
    ]


def run_definitions() -> list[dict[str, Any]]:
    return [
        {"id": "source.tcm.beta6.43of64", "benchmark": "tcm92", "protocolId": "source.tcm.beta6.20260606", "status": "historical", "scope": 64, "official": False, "ourExecution": False},
        {"id": "source.islam.answers.78of104", "benchmark": "islam104", "protocolId": "source.islam.answer_fields.20260613", "status": "historical", "scope": 104, "official": False, "ourExecution": False},
        {"id": "source.leet.lawkey_ai.34of70", "benchmark": "leet70", "protocolId": "source.leet.lawkey_ai.20260717", "status": "historical", "scope": 70, "official": False, "ourExecution": False},
        {"id": "legal.direct.luna", "benchmark": "legal10", "protocolId": "luna.direct.closed_book.per_case", "status": "completed", "scope": 10, "official": True, "ourExecution": True},
        {"id": "legal.frozen_beta6.luna", "benchmark": "legal10", "protocolId": "luna.frozen_beta6.db.per_case", "status": "completed", "scope": 10, "official": True, "ourExecution": True},
        {"id": "legal.universal.luna", "benchmark": "legal10", "protocolId": "luna.universal.db.per_case", "status": "completed", "scope": 10, "official": True, "ourExecution": True},
        {"id": "legal.solpro.closed_book", "benchmark": "legal10", "protocolId": "solpro.direct.closed_book.legal10.batch", "status": "completed", "scope": 10, "official": True, "ourExecution": True},
        {"id": "tcm92.direct.luna", "benchmark": "tcm92", "protocolId": "luna.direct.closed_book.per_case", "status": "completed", "scope": 92, "official": True, "ourExecution": True},
        {"id": "tcm92.frozen_beta6.luna.corrected", "benchmark": "tcm92", "protocolId": "luna.frozen_beta6.db.per_case", "status": "completed", "scope": 92, "official": True, "ourExecution": True},
        {"id": "tcm92.universal.luna.real_db", "benchmark": "tcm92", "protocolId": "luna.universal.db.per_case", "status": "completed", "scope": 92, "official": True, "ourExecution": True},
        {"id": "tcm92.solpro.closed_book", "benchmark": "tcm92", "protocolId": "solpro.direct.closed_book.tcm92.batch", "status": "completed", "scope": 92, "official": True, "ourExecution": True},
        {"id": "tcm16.direct.luna.smoke", "benchmark": "tcm92", "protocolId": "luna.direct.closed_book.per_case", "status": "diagnostic", "scope": 16, "official": False, "ourExecution": True},
        {"id": "tcm16.frozen_beta6.luna.smoke", "benchmark": "tcm92", "protocolId": "luna.frozen_beta6.db.per_case", "status": "diagnostic", "scope": 16, "official": False, "ourExecution": True},
        {"id": "tcm16.universal.luna.smoke", "benchmark": "tcm92", "protocolId": "luna.universal.db.per_case", "status": "diagnostic", "scope": 16, "official": False, "ourExecution": True},
        {"id": "tcm92.universal.luna.v45", "benchmark": "tcm92", "protocolId": "luna.universal.db.per_case", "status": "superseded", "scope": 92, "official": False, "ourExecution": True},
        {"id": "tcm22.evidence_arbiter", "benchmark": "tcm92", "protocolId": "luna.evidence_arbiter.tcm_disagreements", "status": "rejected", "scope": 22, "official": False, "ourExecution": True},
        {"id": "tcm92.frozen_beta6.provider_fallback_contaminated", "benchmark": "tcm92", "protocolId": "luna.frozen_beta6.db.per_case", "status": "invalid_provider_fallback", "scope": 92, "official": False, "ourExecution": True},
        {"id": "tcm27.frozen_beta6.fixture_db_mixed", "benchmark": "tcm92", "protocolId": "luna.frozen_beta6.db.per_case", "status": "invalid_database_binding", "scope": 27, "official": False, "ourExecution": True},
        {"id": "islam104.direct.luna", "benchmark": "islam104", "protocolId": "luna.direct.closed_book.per_case", "status": "completed", "scope": 104, "official": True, "ourExecution": True},
        {"id": "islam104.frozen_beta6.luna", "benchmark": "islam104", "protocolId": "luna.frozen_beta6.db.per_case", "status": "completed", "scope": 104, "official": True, "ourExecution": True},
        {"id": "islam104.universal.luna", "benchmark": "islam104", "protocolId": "luna.universal.db.per_case", "status": "completed", "scope": 104, "official": True, "ourExecution": True},
        {"id": "islam.web_optional.partial29", "benchmark": "islam104", "protocolId": "luna.direct.web_optional.wrong_only", "status": "stopped_at_case_boundary", "scope": 29, "official": False, "ourExecution": True},
        {"id": "islam.web_optional.wrong21", "benchmark": "islam104", "protocolId": "luna.direct.web_optional.wrong_only", "status": "gold_informed_retry", "scope": 21, "official": False, "ourExecution": True},
        {"id": "islam.web_required.wrong16", "benchmark": "islam104", "protocolId": "luna.direct.web_required.wrong_only", "status": "gold_informed_second_retry", "scope": 16, "official": False, "ourExecution": True},
    ]


class PublicationBuilder:
    def __init__(self, repo: Path, oracle_root: Path, output: Path) -> None:
        self.repo = repo
        self.oracle_root = oracle_root
        self.output = output
        self.cases: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        self.runs = {item["id"]: dict(item) for item in run_definitions()}
        self.warnings: list[str] = []

    def add_manifest_group(self, slug: str, pairs: Iterable[tuple[Path, Path]]) -> None:
        for public_path, private_path in pairs:
            public = read_json(public_path)
            private = read_json(private_path)
            task_type = str(public.get("taskType") or "")
            answer_map = {
                str(item.get("caseId")): str(item.get("correctOptionId") or item.get("correctAnswer") or "")
                for item in list(private.get("answers") or [])
            }
            if task_type == "legal_retrieval_answer":
                graders = {str(item.get("graderId")): item for item in list(private.get("graders") or [])}
                for case in list(public.get("cases") or []):
                    grader = graders.get(str(case.get("graderRef") or case.get("id")), {})
                    for variant in list(case.get("variants") or []):
                        artifact_id = f"{case['id']}__{variant['id']}"
                        self.cases[slug][artifact_id] = {
                            "schemaVersion": SCHEMA_VERSION,
                            "benchmarkGroup": slug,
                            "benchmarkId": public.get("benchmarkId"),
                            "taskType": task_type,
                            "caseId": case.get("id"),
                            "variantId": variant.get("id"),
                            "artifactId": artifact_id,
                            "question": variant.get("query"),
                            "goldStandard": {
                                "primaryTargets": grader.get("primaryTargets", []),
                                "answerRules": grader.get("answerRules", {}),
                                "semanticJudge": grader.get("semanticJudge", {}),
                            },
                            "runs": [],
                        }
                continue
            for case in list(public.get("cases") or []):
                case_id = str(case.get("id") or "")
                prompt = str(case.get("prompt") or "")
                gold = answer_map.get(case_id, "")
                options = option_texts(prompt)
                self.cases[slug][case_id] = {
                    "schemaVersion": SCHEMA_VERSION,
                    "benchmarkGroup": slug,
                    "benchmarkId": public.get("benchmarkId"),
                    "taskType": task_type,
                    "caseId": case_id,
                    "question": prompt,
                    "options": options,
                    "goldAnswer": gold,
                    "goldAnswerText": options.get(gold, ""),
                    "metadata": case.get("metadata", {}),
                    "runs": [],
                }

    def attach_artifact(
        self,
        slug: str,
        run_id: str,
        artifact_path: Path,
        *,
        judge_case: dict[str, Any] | None = None,
        source_label: str = "run_artifact",
    ) -> None:
        record = read_json(artifact_path)
        artifact_id = str(record.get("id") or record.get("artifactId") or artifact_path.stem)
        key = artifact_id if artifact_id in self.cases[slug] else str(record.get("caseId") or artifact_id)
        case = self.cases[slug].get(key)
        if case is None:
            self.warnings.append(f"unmatched artifact: {artifact_path}")
            return
        prediction = normalize_answer(record.get("prediction"))
        result: dict[str, Any] = {
            "runId": run_id,
            "protocolId": self.runs[run_id]["protocolId"],
            "runStatus": self.runs[run_id]["status"],
            "prediction": prediction,
            "predictionText": (case.get("options") or {}).get(prediction, ""),
            "response": str(record.get("answerMarkdown") or record.get("answer") or ""),
            "error": str(record.get("error") or ""),
            "modelMetadata": model_metadata(record),
            "llmUsed": record.get("llmUsed"),
            "sourceType": source_label,
            "sourceArtifact": self._display_path(artifact_path),
            "sourceArtifactSha256": sha256_file(artifact_path),
            "retrieval": {
                "candidateCount": record.get("candidateCount"),
                "selectedCount": record.get("selectedCount", len(record.get("selectedEvidence") or [])),
                "selectorStatus": record.get("selectorStatus"),
                "selectionSource": record.get("selectionSource"),
                "writerStatus": record.get("writerStatus"),
                "writerMode": record.get("writerMode"),
                "selectedEvidence": evidence_summary(record),
            },
        }
        if record.get("modelTrace"):
            result["modelTrace"] = record.get("modelTrace")
        if record.get("modelTraceAttempts"):
            result["modelTraceAttempts"] = record.get("modelTraceAttempts")
        if record.get("webSearchRequirement"):
            result["webSearchRequirement"] = record.get("webSearchRequirement")
        if record.get("decision"):
            result["arbiter"] = {
                "decision": record.get("decision"),
                "directPrediction": record.get("directPrediction"),
                "universalPrediction": record.get("universalPrediction"),
                "status": record.get("arbiterStatus"),
                "details": record.get("arbiter"),
            }
        if judge_case is not None:
            result["correct"] = bool(judge_case.get("passed"))
            result["groundingPassed"] = bool(judge_case.get("groundingPassed"))
            result["judgeFailures"] = judge_case.get("failures", [])
            result["judgeReasons"] = [
                str((item.get("judgment") or {}).get("reason") or "")
                for item in list(judge_case.get("judgments") or [])
            ]
        else:
            gold = str(case.get("goldAnswer") or "")
            result["correct"] = bool(prediction) and prediction == gold
        case["runs"].append(result)

    def attach_result_dir(
        self,
        slug: str,
        run_id: str,
        result_dir: Path,
        *,
        judge_path: Path | None = None,
    ) -> None:
        if not result_dir.is_dir():
            self.warnings.append(f"missing result directory: {result_dir}")
            return
        judge_map: dict[str, dict[str, Any]] = {}
        if judge_path is not None and judge_path.is_file():
            judge_map = {
                str(item.get("artifactId")): item
                for item in list(read_json(judge_path).get("cases") or [])
            }
        for artifact_path in sorted(result_dir.glob("*.json")):
            self.attach_artifact(
                slug,
                run_id,
                artifact_path,
                judge_case=judge_map.get(artifact_path.stem) if judge_map else None,
            )

    def attach_source_result(
        self,
        slug: str,
        run_id: str,
        case_id: str,
        *,
        prediction: str,
        response: str,
        source: str,
    ) -> None:
        case = self.cases[slug].get(case_id)
        if case is None:
            self.warnings.append(f"unmatched source answer: {slug}/{case_id}")
            return
        normalized = normalize_answer(prediction)
        case["runs"].append(
            {
                "runId": run_id,
                "protocolId": self.runs[run_id]["protocolId"],
                "runStatus": self.runs[run_id]["status"],
                "prediction": normalized,
                "predictionText": (case.get("options") or {}).get(normalized, ""),
                "response": response,
                "error": "",
                "correct": bool(normalized) and normalized == str(case.get("goldAnswer") or ""),
                "modelMetadata": {"provider": "unknown", "model": "unknown"},
                "sourceType": "source_provided_historical_answer",
                "sourceArtifact": source,
                "retrieval": {},
            }
        )

    def _display_path(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.repo.resolve()))
        except ValueError:
            return str(path.resolve())

    def attach_legal_runs(self) -> None:
        v40 = self.repo / "runs/universal-engine-eval-20260714-luna-low-v40/legal-spotchecks"
        v41 = self.repo / "runs/universal-engine-eval-20260714-luna-low-v41/legal-spotchecks"
        specs = [
            ("legal.direct.luna", v40 / "kakao-direct-current", "semantic-judge.json"),
            ("legal.frozen_beta6.luna", v40 / "kakao-beta6-current", "semantic-judge.json"),
            ("legal.universal.luna", v40 / "kakao-universal", "semantic-judge.latest-current.json"),
            ("legal.direct.luna", v41 / "military-direct", "semantic-judge.json"),
            ("legal.frozen_beta6.luna", v41 / "military-beta6", "semantic-judge.json"),
            ("legal.universal.luna", v40 / "military-universal-current", "semantic-judge.json"),
            ("legal.direct.luna", v41 / "yangyang-direct", "semantic-judge.json"),
            ("legal.frozen_beta6.luna", v41 / "yangyang-beta6", "semantic-judge.json"),
            ("legal.universal.luna", v41 / "yangyang-universal", "semantic-judge.json"),
        ]
        for run_id, root, judge_name in specs:
            self.attach_result_dir("legal10", run_id, root / "results", judge_path=root / judge_name)

        sol_root = self.oracle_root / "legal"
        judge_paths = {
            "kakao": sol_root / "judge-kakao-v1.json",
            "military": sol_root / "judge-military-v1.json",
            "yangyang": sol_root / "judge-yangyang-v1.json",
        }
        judge_map: dict[str, dict[str, Any]] = {}
        for path in judge_paths.values():
            if path.is_file():
                judge_map.update({str(item.get("artifactId")): item for item in read_json(path).get("cases", [])})
        result_dir = sol_root / "parsed-results-v1"
        for path in sorted(result_dir.glob("*.json")):
            self.attach_artifact("legal10", "legal.solpro.closed_book", path, judge_case=judge_map.get(path.stem))

    def attach_tcm_runs(self) -> None:
        v44 = self.repo / "runs/universal-engine-eval-20260714-luna-low-v44-tcm16"
        v45 = self.repo / "runs/universal-engine-eval-20260714-luna-low-v45-tcm92"
        v46 = self.repo / "runs/universal-engine-eval-20260714-luna-low-v46-no-evidence-fallback-tcm92"
        specs = [
            ("tcm92.direct.luna", v45 / "direct/results"),
            ("tcm92.frozen_beta6.luna.corrected", v46 / "frozen-beta6-real-tcmdb-codex6-retry/results"),
            ("tcm92.universal.luna.real_db", v46 / "universal-real-tcmdb/results"),
            ("tcm16.direct.luna.smoke", v44 / "direct/results"),
            ("tcm16.frozen_beta6.luna.smoke", v44 / "frozen-beta6/results"),
            ("tcm16.universal.luna.smoke", v44 / "universal/results"),
            ("tcm92.universal.luna.v45", v45 / "universal/results"),
            ("tcm22.evidence_arbiter", v45 / "evidence-arbitration-v1/results"),
            ("tcm92.frozen_beta6.provider_fallback_contaminated", v46 / "frozen-beta6-real-tcmdb/results"),
            ("tcm27.frozen_beta6.fixture_db_mixed", v46 / "frozen-beta6/results"),
        ]
        for run_id, path in specs:
            self.attach_result_dir("tcm92", run_id, path)
        self.attach_result_dir(
            "tcm92",
            "tcm92.solpro.closed_book",
            self.oracle_root / "tcm/parsed-results-v1",
        )

    def attach_islam_runs(self) -> None:
        v47 = self.repo / "runs/universal-engine-eval-20260715-luna-low-v47-islam104-codex6"
        for benchmark_id in ("mcq.islam.cisi100.v1", "mcq.islam.aqa4.v1"):
            root = v47 / benchmark_id
            self.attach_result_dir("islam104", "islam104.direct.luna", root / "direct/results")
            self.attach_result_dir("islam104", "islam104.frozen_beta6.luna", root / "beta6/results")
            self.attach_result_dir("islam104", "islam104.universal.luna", root / "universal/results")

        v48 = self.repo / "runs/universal-engine-eval-20260715-luna-low-v48-islam104-web-direct-codex6"
        partial = v48 / "mcq.islam.cisi100.v1/web-direct/results"
        self.attach_result_dir("islam104", "islam.web_optional.partial29", partial)
        receipt = read_json(v48 / "wrong-only/RUN_RECEIPT.json")
        reuse_ids = set(receipt["reuse"]["caseIds"])
        remaining_ids = set(receipt["remainingRun"]["caseIds"])
        for path in sorted(partial.glob("*.json")):
            if path.stem in reuse_ids:
                self.attach_artifact("islam104", "islam.web_optional.wrong21", path)
        remaining_dir = v48 / "wrong-only/remaining14/results"
        for path in sorted(remaining_dir.glob("*.json")):
            if path.stem in remaining_ids:
                self.attach_artifact("islam104", "islam.web_optional.wrong21", path)

        v49 = self.repo / "runs/universal-engine-eval-20260715-luna-low-v49-islam-mandatory-search-wrong16"
        self.attach_result_dir("islam104", "islam.web_required.wrong16", v49 / "results")

    def attach_tcm_source(self, zip_path: Path) -> None:
        if not zip_path.is_file():
            self.warnings.append(f"missing TCM historical source: {zip_path}")
            return
        with zipfile.ZipFile(zip_path) as archive:
            for name in archive.namelist():
                if not name.endswith(".txt") or not name.startswith("정리/") or "참고" in name or "문제점" in name:
                    continue
                period_match = re.search(r"(\d)교시", Path(name).name)
                if not period_match:
                    continue
                period = int(period_match.group(1))
                text = archive.read(name).decode("utf-8-sig")
                starts = list(re.finditer(r"(?m)^\s*(\d{1,3})\.\s+", text))
                for index, start in enumerate(starts):
                    end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
                    block = text[start.start():end]
                    ai = re.search(r"(?ms)^\s*AI\s*[:：]\s*(.*?)\s*^\s*정답\s*[:：]", block)
                    if not ai:
                        continue
                    number = int(start.group(1))
                    response = ai.group(1).strip()
                    self.attach_source_result(
                        "tcm92",
                        "source.tcm.beta6.43of64",
                        f"tcm81-p{period}-q{number:03d}",
                        prediction=response,
                        response=response,
                        source=f"{zip_path.name}:{name}",
                    )

    def attach_islam_source(self, source_dir: Path) -> None:
        specs = [
            (source_dir / "CISI_이슬람금융_공식샘플_100문항.txt", "islam-cisi-q", r"정답"),
            (source_dir / "AQA_객관식만_문제_정답_한국어번역.txt", "islam-aqa-q", r"답"),
        ]
        for path, prefix, gold_label in specs:
            if not path.is_file():
                self.warnings.append(f"missing Islam historical source: {path}")
                continue
            text = path.read_text(encoding="utf-8-sig")
            starts = list(re.finditer(r"(?m)^\s*(\d{2,3})\.\s+", text))
            for index, start in enumerate(starts):
                end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
                block = text[start.start():end]
                ai = re.search(rf"(?ms)^\s*AI\s*[:：]\s*(.*?)\s*^\s*{gold_label}\s*[:：]", block)
                if not ai:
                    continue
                number = int(start.group(1))
                response = ai.group(1).strip()
                self.attach_source_result(
                    "islam104",
                    "source.islam.answers.78of104",
                    f"{prefix}{number:03d}",
                    prediction=response,
                    response=response,
                    source=str(path),
                )

    def attach_leet_source(self, zip_path: Path) -> None:
        if not zip_path.is_file():
            self.warnings.append(f"missing LEET historical source: {zip_path}")
            return
        with zipfile.ZipFile(zip_path) as archive:
            for token, suffix in (("언어이해", "language"), ("추론논증", "reasoning")):
                names = [
                    name
                    for name in archive.namelist()
                    if token in Path(name).name and name.endswith(".txt") and "오답" not in Path(name).name
                ]
                if len(names) != 1:
                    self.warnings.append(f"LEET source match failure for {token}: {names}")
                    continue
                name = names[0]
                text = archive.read(name).decode("utf-8-sig")
                starts = list(re.finditer(r"(?m)^\s*(\d{1,3})\s*\.\s*문제\s*:\s*", text))
                for index, start in enumerate(starts):
                    end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
                    block = text[start.start():end]
                    ai = re.search(r"(?m)^\s*AI\s*[:：]\s*(.*?)\s*$", block)
                    number = int(start.group(1))
                    response = ai.group(1).strip() if ai else ""
                    self.attach_source_result(
                        "leet70",
                        "source.leet.lawkey_ai.34of70",
                        f"lawkey-leet2026-{suffix}-q{number:03d}",
                        prediction=response,
                        response=response,
                        source=f"{zip_path.name}:{name}",
                    )

    def finalize_run_scores(self) -> None:
        rows_by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for group in self.cases.values():
            for case in group.values():
                for result in case["runs"]:
                    rows_by_run[result["runId"]].append(result)
        for run_id, run in self.runs.items():
            rows = rows_by_run.get(run_id, [])
            correct = sum(1 for row in rows if row.get("correct") is True)
            predicted = sum(1 for row in rows if row.get("prediction"))
            errors = sum(1 for row in rows if row.get("error"))
            trace_rows = [row for row in rows if isinstance(row.get("modelTrace"), dict)]
            search_counts = [
                len(list((row.get("modelTrace") or {}).get("webSearchEvents") or []))
                for row in trace_rows
            ]
            command_counts = [
                len(list((row.get("modelTrace") or {}).get("commandExecutionEvents") or []))
                for row in trace_rows
            ]
            unique_search_queries = {
                str(event.get("query") or "").strip()
                for row in trace_rows
                for event in list((row.get("modelTrace") or {}).get("webSearchEvents") or [])
                if isinstance(event, dict) and str(event.get("query") or "").strip()
            }
            run["observed"] = {
                "artifacts": len(rows),
                "predicted": predicted,
                "correct": correct,
                "wrongOrInvalid": len(rows) - correct,
                "errors": errors,
                "accuracy": correct / len(rows) if rows else None,
            }
            run["observedToolUsage"] = {
                "traceArtifacts": len(trace_rows),
                "webSearchCases": sum(1 for count in search_counts if count),
                "webSearchEventCount": sum(search_counts),
                "uniqueWebSearchQueryCount": len(unique_search_queries),
                "commandExecutionCases": sum(1 for count in command_counts if count),
                "commandExecutionEventCount": sum(command_counts),
            }

    def validate(self) -> None:
        expected_counts = {
            "legal10": 10,
            "tcm92": 92,
            "islam104": 104,
            "christian192": 192,
            "psychology487": 487,
            "buddhist290": 290,
            "leet70": 70,
        }
        for slug, expected in expected_counts.items():
            actual = len(self.cases.get(slug, {}))
            if actual != expected:
                raise RuntimeError(f"{slug}: expected {expected} cases, found {actual}")
        expected_scores = {
            "source.tcm.beta6.43of64": (64, 43),
            "source.islam.answers.78of104": (104, 78),
            "source.leet.lawkey_ai.34of70": (70, 34),
            "legal.direct.luna": (10, 0),
            "legal.frozen_beta6.luna": (10, 0),
            "legal.universal.luna": (10, 10),
            "legal.solpro.closed_book": (10, 0),
            "tcm92.direct.luna": (92, 68),
            "tcm92.frozen_beta6.luna.corrected": (92, 69),
            "tcm92.universal.luna.real_db": (92, 71),
            "tcm92.solpro.closed_book": (92, 81),
            "tcm16.direct.luna.smoke": (16, 14),
            "tcm16.universal.luna.smoke": (16, 15),
            "tcm92.universal.luna.v45": (92, 68),
            "tcm22.evidence_arbiter": (22, 8),
            "tcm92.frozen_beta6.provider_fallback_contaminated": (92, 35),
            "islam104.direct.luna": (104, 83),
            "islam104.frozen_beta6.luna": (104, 78),
            "islam104.universal.luna": (104, 78),
            "islam.web_optional.wrong21": (21, 5),
            "islam.web_required.wrong16": (16, 7),
        }
        for run_id, (total, correct) in expected_scores.items():
            observed = self.runs[run_id]["observed"]
            if observed["artifacts"] != total or observed["correct"] != correct:
                raise RuntimeError(
                    f"{run_id}: expected {correct}/{total}, found "
                    f"{observed['correct']}/{observed['artifacts']}"
                )
        expected_tool_usage = {
            "islam.web_optional.wrong21": (21, 1, 2, 2, 0),
            "islam.web_required.wrong16": (16, 16, 23, 22, 0),
        }
        for run_id, (trace_artifacts, search_cases, search_events, unique_queries, command_events) in expected_tool_usage.items():
            observed = self.runs[run_id]["observedToolUsage"]
            actual = (
                observed["traceArtifacts"],
                observed["webSearchCases"],
                observed["webSearchEventCount"],
                observed["uniqueWebSearchQueryCount"],
                observed["commandExecutionEventCount"],
            )
            expected = (trace_artifacts, search_cases, search_events, unique_queries, command_events)
            if actual != expected:
                raise RuntimeError(f"{run_id}: expected tool usage {expected}, found {actual}")
        if any("Wikia built-in AI" in json.dumps(case, ensure_ascii=False) for group in self.cases.values() for case in group.values()):
            raise RuntimeError("misleading Wikia built-in AI label found")

    def write_outputs(self) -> None:
        self.output.mkdir(parents=True, exist_ok=True)
        case_dir = self.output / "cases"
        wrong_dir = self.output / "wrong_answers"
        case_dir.mkdir(exist_ok=True)
        wrong_dir.mkdir(exist_ok=True)
        catalog: list[dict[str, Any]] = []
        all_result_rows: list[dict[str, Any]] = []
        for slug in sorted(self.cases):
            records = list(self.cases[slug].values())
            records.sort(key=lambda item: str(item.get("artifactId") or item.get("caseId")))
            out = case_dir / f"{slug}.jsonl"
            with out.open("w", encoding="utf-8", newline="\n") as stream:
                for record in records:
                    stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
                    for result in record["runs"]:
                        all_result_rows.append({"case": record, "result": result})
            catalog.append(
                {
                    "id": slug,
                    "caseCount": len(records),
                    "executedCaseCount": sum(1 for item in records if item["runs"]),
                    "resultRecordCount": sum(len(item["runs"]) for item in records),
                    "caseFile": str(out.relative_to(self.output)),
                }
            )
            self._write_wrong_markdown(slug, records, wrong_dir / f"{slug}.md")

        write_json(self.output / "catalog.json", {"schemaVersion": 1, "generatedFor": PUBLICATION_DATE, "benchmarks": catalog})
        write_json(self.output / "protocols.json", {"schemaVersion": 1, "protocols": protocols()})
        write_json(self.output / "runs.json", {"schemaVersion": 1, "runs": list(self.runs.values()), "warnings": self.warnings})
        self._write_csv(all_result_rows)
        self._write_readme(catalog)
        self._write_checksums()

    def _write_csv(self, rows: list[dict[str, Any]]) -> None:
        path = self.output / "all_case_results.csv"
        fields = [
            "benchmark_group",
            "benchmark_id",
            "case_id",
            "variant_id",
            "run_id",
            "protocol_id",
            "run_status",
            "question",
            "gold_answer",
            "gold_answer_text",
            "prediction",
            "prediction_text",
            "correct",
            "response",
            "error",
            "source_artifact",
            "source_artifact_sha256",
        ]

        def clean_multiline(value: Any) -> Any:
            if not isinstance(value, str):
                return value
            return "\n".join(line.rstrip() for line in value.splitlines())

        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            for item in rows:
                case, result = item["case"], item["result"]
                writer.writerow(
                    {
                        "benchmark_group": case.get("benchmarkGroup"),
                        "benchmark_id": case.get("benchmarkId"),
                        "case_id": case.get("caseId"),
                        "variant_id": case.get("variantId", ""),
                        "run_id": result.get("runId"),
                        "protocol_id": result.get("protocolId"),
                        "run_status": result.get("runStatus"),
                        "question": clean_multiline(case.get("question")),
                        "gold_answer": case.get("goldAnswer", "semantic_rubric"),
                        "gold_answer_text": clean_multiline(
                            case.get("goldAnswerText", json.dumps(case.get("goldStandard", {}), ensure_ascii=False))
                        ),
                        "prediction": result.get("prediction"),
                        "prediction_text": clean_multiline(result.get("predictionText")),
                        "correct": result.get("correct"),
                        "response": clean_multiline(result.get("response")),
                        "error": clean_multiline(result.get("error")),
                        "source_artifact": result.get("sourceArtifact"),
                        "source_artifact_sha256": result.get("sourceArtifactSha256"),
                    }
                )

    def _write_wrong_markdown(self, slug: str, records: list[dict[str, Any]], path: Path) -> None:
        wrong: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
        for case in records:
            for result in case["runs"]:
                if result.get("correct") is not True:
                    wrong[result["runId"]].append((case, result))
        lines = [f"# {slug} 오답·실패 전문", "", "각 항목은 문제, 정답 기준, 실제 예측과 원응답 전문을 보존한다.", ""]
        for run_id in sorted(wrong):
            run = self.runs[run_id]
            lines.extend(
                [
                    f"## {run_id}",
                    "",
                    f"- 상태: `{run['status']}`",
                    f"- 프로토콜: `{run['protocolId']}`",
                    f"- 관측 점수: `{run['observed']['correct']}/{run['observed']['artifacts']}`",
                    "",
                ]
            )
            for case, result in wrong[run_id]:
                label = str(case.get("artifactId") or case.get("caseId"))
                lines.extend([f"### {label}", "", "문제:", "", "```text", str(case.get("question") or ""), "```", ""])
                if case.get("taskType") == "legal_retrieval_answer":
                    lines.extend(["정답 기준:", "", "```json", json.dumps(case.get("goldStandard", {}), ensure_ascii=False, indent=2), "```", ""])
                else:
                    lines.extend(
                        [
                            f"- 정답: `{case.get('goldAnswer')}` {case.get('goldAnswerText') or ''}",
                            f"- 실제 예측: `{result.get('prediction') or '무응답/파싱 실패'}` {result.get('predictionText') or ''}",
                            "",
                        ]
                    )
                if result.get("judgeReasons"):
                    lines.append("판정 사유:")
                    lines.append("")
                    lines.extend([f"- {reason}" for reason in result["judgeReasons"] if reason])
                    lines.append("")
                lines.extend(["원응답:", "", "```text", str(result.get("response") or "(empty)"), "```", ""])
        rendered = "\n".join(lines)
        rendered = "\n".join(line.rstrip() for line in rendered.splitlines())
        path.write_text(rendered.rstrip() + "\n", encoding="utf-8")

    def _write_readme(self, catalog: list[dict[str, Any]]) -> None:
        official = [run for run in self.runs.values() if run.get("official")]
        historical = [run for run in self.runs.values() if run.get("status") == "historical"]
        diagnostics = [run for run in self.runs.values() if not run.get("official") and run.get("status") != "historical"]
        lines = [
            "# 전체 벤치마크 및 실행 결과 공개 패키지",
            "",
            f"생성 기준일: {PUBLICATION_DATE}",
            "",
            "> 이 디렉터리는 정답키와 문제 전문을 포함한다. 현재 GitHub 저장소가 PRIVATE인 것을 전제로 하며, 공개 전환 전에는 별도의 저작권·개인정보 검토가 필요하다.",
            "",
            "## 용어 교정",
            "",
            "`Wikia 내장 AI`라는 기능이나 실행 주체는 없다. Wikia는 공유 저장소일 뿐이다. 이 패키지는 기존 파일의 답을 `source-provided historical run`으로 표기하며, TCM만 게시글에서 beta6 실행임이 확인된다.",
            "",
            "## 파일 구성",
            "",
            "- `catalog.json`: 전체 벤치마크와 문항 수",
            "- `protocols.json`: 모델, 인터넷·코드 허용, DB 검색, batching, 구조",
            "- `runs.json`: 공식·과거·진단·무효 실행의 점수와 상태",
            "- `cases/*.jsonl`: 모든 문제·정답과 실행별 예측·원응답·정오·검색 trace·artifact 해시",
            "- `wrong_answers/*.md`: 실행별로 틀린 문제와 정답, 실제 답변 전문",
            "- `all_case_results.csv`: 전체 실행 레코드의 스프레드시트용 평면 테이블",
            "- `SHA256SUMS`: 생성 파일 무결성",
            "",
            "## 벤치마크 목록",
            "",
            "| ID | 문항/variant | 실행된 문항 | 실행 레코드 |",
            "|---|---:|---:|---:|",
        ]
        for item in catalog:
            lines.append(f"| `{item['id']}` | {item['caseCount']} | {item['executedCaseCount']} | {item['resultRecordCount']} |")
        lines.extend(["", "객관식·단답형 고유 시험은 총 1,235문항이며, 법률 E2E 10 variants는 별도다.", "", "## 공식 실행 결과", "", "| Run | 상태 | 프로토콜 | 점수 |", "|---|---|---|---:|"])
        for run in official:
            observed = run["observed"]
            lines.append(f"| `{run['id']}` | `{run['status']}` | `{run['protocolId']}` | {observed['correct']}/{observed['artifacts']} |")
        lines.extend(["", "## 공유 파일의 선행 결과", "", "| Run | 확인된 구조 | 점수 |", "|---|---|---:|"])
        protocol_map = {item["id"]: item for item in protocols()}
        for run in historical:
            observed = run["observed"]
            lines.append(f"| `{run['id']}` | {protocol_map[run['protocolId']]['structure']} | {observed['correct']}/{observed['artifacts']} |")
        lines.extend(["", "## 진단·중단·무효 실행", "", "이 결과는 공식 점수와 합치지 않는다.", "", "| Run | 상태 | 관측 |", "|---|---|---:|"])
        for run in diagnostics:
            observed = run["observed"]
            lines.append(f"| `{run['id']}` | `{run['status']}` | {observed['correct']}/{observed['artifacts']} |")
        lines.extend(
            [
                "",
                "## 핵심 실행 조건",
                "",
                "- 정식 Luna 3-arm은 `gpt-5.6-luna`, low reasoning/verbosity, 문항별 독립 호출, 최대 2회 전송, worker 1이다.",
                "- Direct는 질문만 사용하며 인터넷·코드·파일·DB가 모두 금지된다.",
                "- frozen beta6와 Universal은 엔진 코드가 로컬 SQLite를 검색하지만 Luna 자체의 인터넷·코드 도구 호출은 금지된다.",
                "- 이슬람 web retry만 일반 인터넷 검색과 파일 I/O 없는 계산용 read-only shell을 허용했다. 실제 command 실행은 0회였다.",
                "- Sol Pro는 `gpt-5-6-pro`, closed-book/no-web/no-tools이며 법률10과 TCM92를 각각 한 대화의 batch로 실행했다.",
                "- 법률 정오는 Luna low semantic judge가 artifact당 독립 2회 판정했다.",
                "",
                "세부 조건과 예외는 반드시 `protocols.json` 및 `runs.json`을 함께 본다.",
            ]
        )
        (self.output / "README.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_checksums(self) -> None:
        checksum_path = self.output / "SHA256SUMS"
        paths = sorted(path for path in self.output.rglob("*") if path.is_file() and path != checksum_path)
        lines = [f"{sha256_file(path)}  {path.relative_to(self.output)}" for path in paths]
        checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build(args: argparse.Namespace) -> None:
    repo = args.repo.resolve()
    output = (repo / args.output).resolve() if not args.output.is_absolute() else args.output.resolve()
    builder = PublicationBuilder(repo, args.oracle_root.resolve(), output)
    unified = repo / "benchmarks/unified"
    builder.add_manifest_group(
        "legal10",
        [
            (unified / "legal_kakao_sim_access.public.json", unified / "legal_kakao_sim_access.private.json"),
            (unified / "legal_military_key_management.public.json", unified / "legal_military_key_management.private.json"),
            (unified / "legal_yangyang_complainant_age.public.json", unified / "legal_yangyang_complainant_age.private.json"),
        ],
    )
    builder.add_manifest_group("tcm92", [(unified / "mcq_tcm_kuksiwon81_unique92.public.json", unified / "mcq_tcm_kuksiwon81_unique92.private.json")])
    builder.add_manifest_group(
        "islam104",
        [
            (unified / "mcq_islam_cisi100.public.json", unified / "mcq_islam_cisi100.private.json"),
            (unified / "mcq_islam_aqa4.public.json", unified / "mcq_islam_aqa4.private.json"),
        ],
    )
    builder.add_manifest_group(
        "christian192",
        [
            (unified / "mcq_christian_bible100.public.json", unified / "mcq_christian_bible100.private.json"),
            (unified / "mcq_christian_provao2012.public.json", unified / "mcq_christian_provao2012.private.json"),
        ],
    )
    builder.add_manifest_group("psychology487", [(unified / "mcq_psych_mit_sangmyung.public.json", unified / "mcq_psych_mit_sangmyung.private.json")])
    builder.add_manifest_group("buddhist290", [(unified / "short_answer_buddhist_sangha3_290.public.json", unified / "short_answer_buddhist_sangha3_290.private.json")])
    builder.add_manifest_group("leet70", [(unified / "mcq_lawkey_leet2026_70.public.json", unified / "mcq_lawkey_leet2026_70.private.json")])

    builder.attach_legal_runs()
    builder.attach_tcm_runs()
    builder.attach_islam_runs()
    builder.attach_tcm_source(args.tcm_source_zip.resolve())
    builder.attach_islam_source(args.islam_source_dir.resolve())
    builder.attach_leet_source(args.leet_source_zip.resolve())
    builder.finalize_run_scores()
    builder.validate()
    builder.write_outputs()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path("benchmark_reports/2026-07-17-full"))
    parser.add_argument(
        "--oracle-root",
        type=Path,
        default=Path("/home/pineapple/bunjum2/religion/runs/oracle-sol-pro-legal-tcm-20260716"),
    )
    parser.add_argument("--tcm-source-zip", type=Path, default=Path("/tmp/wikia-tcm-benchmark.zip"))
    parser.add_argument("--leet-source-zip", type=Path, default=Path("/tmp/wikia-2026-leet-law-benchmark.zip"))
    parser.add_argument(
        "--islam-source-dir",
        type=Path,
        default=Path("/mnt/d/Downloads/이슬람 벤치마크/공식 문제집"),
    )
    return parser.parse_args()


if __name__ == "__main__":
    build(parse_args())
