import json
import re
import sqlite3
from pathlib import Path

from shared_platform.products import ProductProfile
from tools.audit_selector_ablation import audit_selector_ablation_report
from tools.run_selector_ablation import run_selector_ablation_manifest


class SelectorOnlyLLMClient:
    provider = "fixture_provider"
    default_model = "fixture-model"

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        if "keyword generator" in system:
            return '{"keywords":["sharedterm"]}'
        if "source selector" in system:
            ids = re.findall(r"file_id:\s*(doc-[a-z]+)", prompt)
            return "selector-only\n<selection>\n" + "\n".join(ids[:2]) + "\n</selection>"
        raise AssertionError(f"writer or non-selector stage should not run: {system}")


class DistractorOnlyLLMClient:
    provider = "fixture_provider"
    default_model = "fixture-model"

    def complete(self, messages, *, model="", timeout_seconds=None):
        system = messages[0]["content"]
        if "keyword generator" in system:
            return '{"keywords":["sharedterm"]}'
        if "source selector" in system:
            return "selector-only\n<selection>\ndoc-other\n</selection>"
        raise AssertionError(f"writer or non-selector stage should not run: {system}")


class RawSelectorErrorContextSelectorLLMClient:
    provider = "fixture_provider"
    default_model = "fixture-model"

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        if "keyword generator" in system:
            return '{"keywords":["sharedterm"]}'
        if "source selector" in system:
            if "packet_id:" in prompt:
                return "selector-only\n<selection>\ndoc-other\n</selection>"
            raise RuntimeError("raw selector unavailable")
        raise AssertionError(f"writer or non-selector stage should not run: {system}")


class DivergentKeywordLLMClient:
    provider = "fixture_provider"
    default_model = "fixture-model"

    def __init__(self):
        self.keyword_calls = 0

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        if "keyword generator" in system:
            self.keyword_calls += 1
            keyword = "rawterm" if self.keyword_calls == 1 else "contextterm"
            return json.dumps({"keywords": [keyword]})
        if "source selector" in system:
            ids = re.findall(r"file_id:\s*(doc-[a-z]+)", prompt)
            return "selector-only\n<selection>\n" + "\n".join(ids[:1]) + "\n</selection>"
        raise AssertionError(f"writer or non-selector stage should not run: {system}")


class AlternativeTargetLLMClient:
    provider = "fixture_provider"
    default_model = "fixture-model"

    def complete(self, messages, *, model="", timeout_seconds=None):
        prompt = "\n".join(message["content"] for message in messages)
        system = messages[0]["content"]
        if "keyword generator" in system:
            return json.dumps({"keywords": ["sharedterm"]})
        if "source selector" in system:
            if "packet_id:" in prompt:
                return "selector-only\n<selection>\ndoc-target-a\n</selection>"
            return "selector-only\n<selection>\ndoc-target-a\ndoc-target-b\n</selection>"
        raise AssertionError(f"writer or non-selector stage should not run: {system}")


def _write_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_db(path: Path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(
          canonical_id UNINDEXED,
          full_text,
          tokenize='unicode61'
        );
        INSERT INTO precedents VALUES
          ('doc-target','fixture','target','Target','T','fixture','','target','fiqh_unit','sharedterm target evidence','hash1'),
          ('doc-other','fixture','other','Other','O','fixture','','other','fiqh_unit','sharedterm distractor evidence','hash2');
        INSERT INTO precedents_fts(canonical_id, full_text) VALUES
          ('doc-target','sharedterm target evidence'),
          ('doc-other','sharedterm distractor evidence');
        """
    )
    conn.commit()
    conn.close()


def _make_divergent_keyword_db(path: Path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(
          canonical_id UNINDEXED,
          full_text,
          tokenize='unicode61'
        );
        INSERT INTO precedents VALUES
          ('doc-raw','fixture','raw','Raw','R','fixture','','raw','fiqh_unit','rawterm evidence','hash1'),
          ('doc-context','fixture','context','Context','C','fixture','','context','fiqh_unit','contextterm evidence','hash2');
        INSERT INTO precedents_fts(canonical_id, full_text) VALUES
          ('doc-raw','rawterm evidence'),
          ('doc-context','contextterm evidence');
        """
    )
    conn.commit()
    conn.close()


def _make_alternative_target_db(path: Path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE precedents (
          canonical_id TEXT PRIMARY KEY,
          source_dataset TEXT,
          source_path TEXT,
          title TEXT,
          case_number TEXT,
          court TEXT,
          decision_date TEXT,
          case_name TEXT,
          case_type TEXT,
          full_text TEXT NOT NULL,
          text_hash TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE precedents_fts USING fts5(
          canonical_id UNINDEXED,
          full_text,
          tokenize='unicode61'
        );
        INSERT INTO precedents VALUES
          ('doc-target-a','fixture','a','Target A','A','fixture','','a','fiqh_unit','sharedterm alpha evidence','hash1'),
          ('doc-target-b','fixture','b','Target B','B','fixture','','b','fiqh_unit','sharedterm beta evidence','hash2');
        INSERT INTO precedents_fts(canonical_id, full_text) VALUES
          ('doc-target-a','sharedterm alpha evidence'),
          ('doc-target-b','sharedterm beta evidence');
        """
    )
    conn.commit()
    conn.close()


def test_selector_ablation_runner_writes_valid_raw_vs_context_report(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIGION_BETA6_KEYWORD_ROUNDS", "1")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_SIZE", "100")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")
    public_path = tmp_path / "mcq.public.json"
    private_path = tmp_path / "mcq.private.json"
    _write_json(
        public_path,
        {
            "schemaVersion": 1,
            "benchmarkId": "mcq.selector.ablation.test",
            "taskType": "mcq",
            "product": "islam",
            "language": "en",
            "cases": [{"id": "q1", "prompt": "Question?\nA. one\nB. two"}],
        },
    )
    _write_json(
        private_path,
        {
            "schemaVersion": 1,
            "benchmarkId": "mcq.selector.ablation.test",
            "taskType": "mcq",
            "answers": [{"caseId": "q1", "correctOptionId": "A"}],
            "retrievalTargets": [
                {
                    "caseId": "q1",
                    "targets": [{"textContains": "target evidence"}],
                    "rankRules": {"primaryMustAppearWithin": 2},
                }
            ],
        },
    )
    db_path = tmp_path / "islam.sqlite3"
    _make_db(db_path)
    product = ProductProfile(
        key="islam",
        name="Test Islam",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="",
        safety_notice="test",
    )

    report = run_selector_ablation_manifest(
        public_path=public_path,
        private_path=private_path,
        output_dir=tmp_path / "out",
        products={"islam": product},
        llm_client=SelectorOnlyLLMClient(),
        model="fixture-model",
        limit=5,
    )

    report_path = tmp_path / "out" / "selector_ablation.raw_vs_context_packets_v1.json"
    assert report_path.exists()
    case = report["cases"][0]
    raw = case["arms"]["raw"]
    context = case["arms"]["context_packets_v1"]
    assert raw["writerRan"] is False
    assert context["writerRan"] is False
    assert raw["candidateSetDigest"] == context["candidateSetDigest"]
    assert raw["selectorInputMode"] == "raw"
    assert context["selectorInputMode"] == "context_packets_v1"
    assert context["runtimeSelectorInputMode"] == "context_packets_v1"
    assert context["contextPacketCount"] > 0
    assert context["contextPacketProvenanceCount"] > 0
    assert raw["targetEval"]["targetHitSource"] == "selected_backing_evidence_only"
    assert raw["targetEval"]["targetsTotal"] == 1
    assert raw["targetEval"]["targetsPassed"] == 1
    assert raw["targetEval"]["coveredTargetIds"]
    assert context["targetEval"]["coveredTargetIds"] == raw["targetEval"]["coveredTargetIds"]
    audit = audit_selector_ablation_report(report)
    assert audit["ablationReportValid"] is True


def test_selector_ablation_runner_reuses_raw_candidate_universe_for_context_arm(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIGION_BETA6_KEYWORD_ROUNDS", "1")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_SIZE", "100")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")
    public_path = tmp_path / "mcq.public.json"
    private_path = tmp_path / "mcq.private.json"
    _write_json(
        public_path,
        {
            "schemaVersion": 1,
            "benchmarkId": "mcq.selector.ablation.shared.candidates.test",
            "taskType": "mcq",
            "product": "islam",
            "language": "en",
            "cases": [{"id": "q1", "prompt": "Question?\nA. one\nB. two"}],
        },
    )
    _write_json(
        private_path,
        {
            "schemaVersion": 1,
            "benchmarkId": "mcq.selector.ablation.shared.candidates.test",
            "taskType": "mcq",
            "answers": [{"caseId": "q1", "correctOptionId": "A"}],
        },
    )
    db_path = tmp_path / "islam.sqlite3"
    _make_divergent_keyword_db(db_path)
    product = ProductProfile(
        key="islam",
        name="Test Islam",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="",
        safety_notice="test",
    )

    client = DivergentKeywordLLMClient()
    report = run_selector_ablation_manifest(
        public_path=public_path,
        private_path=private_path,
        output_dir=tmp_path / "out",
        products={"islam": product},
        llm_client=client,
        model="fixture-model",
        limit=5,
    )

    raw = report["cases"][0]["arms"]["raw"]
    context = report["cases"][0]["arms"]["context_packets_v1"]
    assert raw["candidateIds"] == context["candidateIds"]
    assert raw["candidateSetDigest"] == context["candidateSetDigest"]
    assert context["candidateReuseSource"] == "raw_candidate_universe"
    assert client.keyword_calls == 1


def test_selector_ablation_runner_groups_default_mcq_targets_as_alternatives(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIGION_BETA6_KEYWORD_ROUNDS", "1")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_SIZE", "100")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")
    public_path = tmp_path / "mcq.public.json"
    private_path = tmp_path / "mcq.private.json"
    _write_json(
        public_path,
        {
            "schemaVersion": 1,
            "benchmarkId": "mcq.selector.ablation.alternatives.test",
            "taskType": "mcq",
            "product": "islam",
            "language": "en",
            "cases": [{"id": "q1", "prompt": "Question?\nA. one\nB. two"}],
        },
    )
    _write_json(
        private_path,
        {
            "schemaVersion": 1,
            "benchmarkId": "mcq.selector.ablation.alternatives.test",
            "taskType": "mcq",
            "answers": [{"caseId": "q1", "correctOptionId": "A"}],
            "retrievalTargets": [
                {
                    "caseId": "q1",
                    "targets": [
                        {"sourceId": "doc-target-a", "textContains": "alpha evidence"},
                        {"sourceId": "doc-target-b", "textContains": "beta evidence"},
                    ],
                    "rankRules": {"primaryMustAppearWithin": 2},
                }
            ],
        },
    )
    db_path = tmp_path / "islam.sqlite3"
    _make_alternative_target_db(db_path)
    product = ProductProfile(
        key="islam",
        name="Test Islam",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="",
        safety_notice="test",
    )

    report = run_selector_ablation_manifest(
        public_path=public_path,
        private_path=private_path,
        output_dir=tmp_path / "out",
        products={"islam": product},
        llm_client=AlternativeTargetLLMClient(),
        model="fixture-model",
        limit=5,
    )

    raw_eval = report["cases"][0]["arms"]["raw"]["targetEval"]
    context_eval = report["cases"][0]["arms"]["context_packets_v1"]["targetEval"]
    assert raw_eval["targetsTotal"] == 1
    assert context_eval["targetsTotal"] == 1
    assert raw_eval["coveredTargetIds"] == context_eval["coveredTargetIds"]
    audit = audit_selector_ablation_report(report)
    assert audit["aggregate"]["targetEval"]["pairedDelta"]["rawOnlyTargetCount"] == 0


def test_selector_ablation_runner_target_eval_requires_source_id_and_anchor(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIGION_BETA6_KEYWORD_ROUNDS", "1")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_SIZE", "100")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")
    public_path = tmp_path / "mcq.public.json"
    private_path = tmp_path / "mcq.private.json"
    _write_json(
        public_path,
        {
            "schemaVersion": 1,
            "benchmarkId": "mcq.selector.ablation.source_anchor.test",
            "taskType": "mcq",
            "product": "islam",
            "language": "en",
            "cases": [{"id": "q1", "prompt": "Question?\nA. one\nB. two"}],
        },
    )
    _write_json(
        private_path,
        {
            "schemaVersion": 1,
            "benchmarkId": "mcq.selector.ablation.source_anchor.test",
            "taskType": "mcq",
            "answers": [{"caseId": "q1", "correctOptionId": "A"}],
            "retrievalTargets": [
                {
                    "caseId": "q1",
                    "targets": [{"sourceId": "doc-target", "textContains": "missing anchor"}],
                    "rankRules": {"primaryMustAppearWithin": 2},
                }
            ],
        },
    )
    db_path = tmp_path / "islam.sqlite3"
    _make_db(db_path)
    product = ProductProfile(
        key="islam",
        name="Test Islam",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="",
        safety_notice="test",
    )

    report = run_selector_ablation_manifest(
        public_path=public_path,
        private_path=private_path,
        output_dir=tmp_path / "out",
        products={"islam": product},
        llm_client=SelectorOnlyLLMClient(),
        model="fixture-model",
        limit=5,
    )

    raw_eval = report["cases"][0]["arms"]["raw"]["targetEval"]
    assert raw_eval["targetsTotal"] == 1
    assert raw_eval["targetsPassed"] == 0
    assert raw_eval["coveredTargetIds"] == []
    assert raw_eval["missedTargetIds"]


def test_selector_ablation_runner_target_eval_ignores_filled_non_selector_rows(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIGION_BETA6_KEYWORD_ROUNDS", "1")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_SIZE", "100")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")
    public_path = tmp_path / "mcq.public.json"
    private_path = tmp_path / "mcq.private.json"
    _write_json(
        public_path,
        {
            "schemaVersion": 1,
            "benchmarkId": "mcq.selector.ablation.no_fill_target.test",
            "taskType": "mcq",
            "product": "islam",
            "language": "en",
            "cases": [{"id": "q1", "prompt": "Question?\nA. one\nB. two"}],
        },
    )
    _write_json(
        private_path,
        {
            "schemaVersion": 1,
            "benchmarkId": "mcq.selector.ablation.no_fill_target.test",
            "taskType": "mcq",
            "answers": [{"caseId": "q1", "correctOptionId": "A"}],
            "retrievalTargets": [
                {
                    "caseId": "q1",
                    "targets": [{"sourceId": "doc-target", "textContains": "target evidence"}],
                    "rankRules": {"primaryMustAppearWithin": 2},
                }
            ],
        },
    )
    db_path = tmp_path / "islam.sqlite3"
    _make_db(db_path)
    product = ProductProfile(
        key="islam",
        name="Test Islam",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="",
        safety_notice="test",
    )

    report = run_selector_ablation_manifest(
        public_path=public_path,
        private_path=private_path,
        output_dir=tmp_path / "out",
        products={"islam": product},
        llm_client=DistractorOnlyLLMClient(),
        model="fixture-model",
        limit=5,
    )

    raw_arm = report["cases"][0]["arms"]["raw"]
    assert raw_arm["selectedEvidenceIds"] == ["doc-other"]
    assert raw_arm["targetEval"]["targetsPassed"] == 0
    assert raw_arm["targetEval"]["coveredTargetIds"] == []
    assert raw_arm["targetEval"]["missedTargetIds"]


def test_selector_ablation_runner_target_eval_ignores_fallback_filled_rows(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIGION_BETA6_KEYWORD_ROUNDS", "1")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_SIZE", "100")
    monkeypatch.setenv("RELIGION_SELECTOR_BATCH_WORKERS", "1")
    public_path = tmp_path / "mcq.public.json"
    private_path = tmp_path / "mcq.private.json"
    _write_json(
        public_path,
        {
            "schemaVersion": 1,
            "benchmarkId": "mcq.selector.ablation.no_fallback_target.test",
            "taskType": "mcq",
            "product": "islam",
            "language": "en",
            "cases": [{"id": "q1", "prompt": "Question?\nA. one\nB. two"}],
        },
    )
    _write_json(
        private_path,
        {
            "schemaVersion": 1,
            "benchmarkId": "mcq.selector.ablation.no_fallback_target.test",
            "taskType": "mcq",
            "answers": [{"caseId": "q1", "correctOptionId": "A"}],
            "retrievalTargets": [
                {
                    "caseId": "q1",
                    "targets": [{"sourceId": "doc-target", "textContains": "target evidence"}],
                    "rankRules": {"primaryMustAppearWithin": 2},
                }
            ],
        },
    )
    db_path = tmp_path / "islam.sqlite3"
    _make_db(db_path)
    product = ProductProfile(
        key="islam",
        name="Test Islam",
        db_path=db_path,
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="",
        safety_notice="test",
    )

    report = run_selector_ablation_manifest(
        public_path=public_path,
        private_path=private_path,
        output_dir=tmp_path / "out",
        products={"islam": product},
        llm_client=RawSelectorErrorContextSelectorLLMClient(),
        model="fixture-model",
        limit=5,
    )

    raw_arm = report["cases"][0]["arms"]["raw"]
    assert raw_arm["selectorFallback"] is True
    assert "doc-target" in raw_arm["filledEvidenceIds"]
    assert raw_arm["targetEval"]["targetsPassed"] == 0
    assert raw_arm["targetEval"]["coveredTargetIds"] == []
    assert raw_arm["targetEval"]["missedTargetIds"]
