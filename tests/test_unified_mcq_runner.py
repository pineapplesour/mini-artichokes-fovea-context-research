import json
import sqlite3
from pathlib import Path

from shared_platform.products import ProductProfile
from tools.run_unified_mcq_benchmark import (
    build_mcq_query,
    build_short_answer_query,
    extract_option_ids,
    case_option_ids,
    parse_mcq_prediction,
    parse_short_answer_prediction,
    run_direct_manifest,
    run_engine_manifest,
)


class FakeLLMClient:
    def __init__(self, answer: str, *, provider: str = "fixture_provider", default_model: str = "fixture-model"):
        self.answer = answer
        self.calls = []
        self.provider = provider
        self.default_model = default_model

    def complete(self, messages, *, model="", timeout_seconds=None):
        self.calls.append({"messages": messages, "model": model, "timeout_seconds": timeout_seconds})
        return self.answer


def test_extract_option_ids_supports_numeric_circled_and_letter_markers():
    assert extract_option_ids("문제\n① 갑\n② 을\n③ 병") == ["1", "2", "3"]
    assert extract_option_ids("문제\n① 갑\n② 을\n③\n셋째 보기\n④ 정\n⑤ 무") == ["1", "2", "3", "4", "5"]
    assert extract_option_ids("문제\n1) 갑\n2) 을\n3) 병\n4) 정") == ["1", "2", "3", "4"]
    assert extract_option_ids("Question\nA. alpha\nB. beta\nC. gamma") == ["A", "B", "C"]


def test_case_option_ids_uses_product_mcq_parser_for_ocr_tcm_markers(tmp_path):
    product = ProductProfile(
        key="tcm",
        name="Hanui AI",
        db_path=tmp_path / "unused.sqlite3",
        db_shape="precedents",
        languages=("ko",),
        default_language="ko",
        theme="",
        safety_notice="test",
    )
    case = {
        "prompt": """치방은?
© 목향순기산
Q 목향파기산
@ 소자강기탕
® 익위승양탕
© 조중익기탕"""
    }

    assert extract_option_ids(case["prompt"]) == ["1", "2", "3", "4", "5"]
    assert case_option_ids(case, product) == ["1", "2", "3", "4", "5"]


def test_case_option_ids_prefers_parser_over_leading_question_number(tmp_path):
    product = ProductProfile(
        key="catholic",
        name="Catholic AI",
        db_path=tmp_path / "unused.sqlite3",
        db_shape="precedents",
        languages=("ko",),
        default_language="ko",
        theme="",
        safety_notice="test",
    )
    prompt = """2. 창 42:21에서 아우는 누구인가?

① 레위
② 베냐민
③ 르우벤
④ 요셉"""

    assert extract_option_ids(prompt) == ["1", "2", "3", "4"]
    assert case_option_ids({"prompt": prompt}, product) == ["1", "2", "3", "4"]


def test_parse_mcq_prediction_prefers_answer_line_and_allowed_options():
    assert parse_mcq_prediction("정답: ④\n설명", allowed_ids=["1", "2", "3", "4", "5"]) == "4"
    assert parse_mcq_prediction("Answer: B because...", allowed_ids=["A", "B", "C", "D"]) == "B"
    assert parse_mcq_prediction("정답: 7", allowed_ids=["1", "2", "3", "4", "5"]) is None


def test_build_mcq_query_adds_format_instruction_without_answer_leak():
    query = build_mcq_query("문제\n1) 갑\n2) 을", language="ko", option_ids=["1", "2"])

    assert "정답: <보기ID>" in query
    assert "1, 2" in query
    assert "correctOptionId" not in query
    assert "gold" not in query


def test_short_answer_query_and_parser_preserve_exact_answer_string():
    query = build_short_answer_query("대승불교의 이상적 인간상은?", language="ko")

    assert '"finalAnswer"' in query
    assert "정답이나 해설" not in query
    assert parse_short_answer_prediction('{"finalAnswer":"보살(菩薩)"}') == "보살(菩薩)"
    assert parse_short_answer_prediction('정답: 고집성제=집성제') == "고집성제=집성제"
    assert parse_short_answer_prediction('{"finalAnswer":" 보살(菩薩)"}') == " 보살(菩薩)"


def test_run_direct_manifest_supports_short_answer_without_private_gold(tmp_path):
    public = {
        "schemaVersion": 1,
        "benchmarkId": "short_answer.buddhist.test",
        "taskType": "short_answer",
        "product": "buddhist",
        "language": "ko",
        "cases": [{"id": "q1", "prompt": "대승불교의 이상적 인간상은?"}],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
    product = ProductProfile(
        key="buddhist",
        name="Test Buddhist",
        db_path=Path("missing.sqlite3"),
        db_shape="precedents",
        languages=("ko",),
        default_language="ko",
        theme="",
        safety_notice="test",
    )
    fake = FakeLLMClient('{"finalAnswer":"보살(菩薩)"}')

    summary = run_direct_manifest(
        public_path=public_path,
        output_dir=tmp_path / "run",
        products={"buddhist": product},
        llm_client=fake,
    )

    record = json.loads((tmp_path / "run" / "results" / "q1.json").read_text(encoding="utf-8"))
    assert summary["taskType"] == "short_answer"
    assert record["prediction"] == "보살(菩薩)"
    assert record["gold"] is None
    prompt = "\n".join(message["content"] for message in fake.calls[0]["messages"])
    assert '"finalAnswer"' in prompt


def test_run_direct_manifest_records_prediction_without_private_answers(tmp_path):
    public = {
        "schemaVersion": 1,
        "benchmarkId": "mcq.generic.test",
        "taskType": "mcq",
        "product": "islam",
        "language": "ko",
        "cases": [
            {
                "id": "q1",
                "prompt": "다음 중 맞는 것은?\n1) 갑\n2) 을\n3) 병",
                "metadata": {"topic": "smoke"},
            }
        ],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
    output_dir = tmp_path / "run"
    product = ProductProfile(
        key="islam",
        name="Test Islam",
        db_path=Path("missing.sqlite3"),
        db_shape="precedents",
        languages=("ko",),
        default_language="ko",
        theme="",
        safety_notice="test",
    )
    fake = FakeLLMClient("정답: 2\n근거 설명")

    summary = run_direct_manifest(
        public_path=public_path,
        output_dir=output_dir,
        products={"islam": product},
        llm_client=fake,
        resume=False,
    )

    record = json.loads((output_dir / "results" / "q1.json").read_text(encoding="utf-8"))
    assert summary["total"]["correct"] is None
    assert summary["total"]["predicted"] == 1
    assert record["prediction"] == "2"
    assert record["gold"] is None
    prompt = "\n".join(message["content"] for message in fake.calls[0]["messages"])
    assert "정답: <보기ID>" in prompt
    assert "correctOptionId" not in prompt


def test_run_direct_manifest_can_limit_public_cases(tmp_path):
    public = {
        "schemaVersion": 1,
        "benchmarkId": "mcq.generic.limit.test",
        "taskType": "mcq",
        "product": "islam",
        "language": "en",
        "cases": [
            {"id": "q1", "prompt": "Question?\nA. alpha\nB. beta"},
            {"id": "q2", "prompt": "Question?\nA. alpha\nB. beta"},
        ],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
    output_dir = tmp_path / "run"
    product = ProductProfile(
        key="islam",
        name="Test Islam",
        db_path=Path("missing.sqlite3"),
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="",
        safety_notice="test",
    )

    summary = run_direct_manifest(
        public_path=public_path,
        output_dir=output_dir,
        products={"islam": product},
        llm_client=FakeLLMClient("Answer: A"),
        resume=False,
        max_cases=1,
    )

    assert summary["total"]["total"] == 1
    assert sorted(path.name for path in (output_dir / "results").glob("*.json")) == ["q1.json"]


def test_run_direct_manifest_can_filter_public_cases_by_id(tmp_path):
    public = {
        "schemaVersion": 1,
        "benchmarkId": "mcq.generic.case_id.test",
        "taskType": "mcq",
        "product": "islam",
        "language": "en",
        "cases": [
            {"id": "q1", "prompt": "Question?\nA. alpha\nB. beta"},
            {"id": "q2", "prompt": "Question?\nA. alpha\nB. beta"},
        ],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
    output_dir = tmp_path / "run"
    product = ProductProfile(
        key="islam",
        name="Test Islam",
        db_path=Path("missing.sqlite3"),
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="",
        safety_notice="test",
    )

    summary = run_direct_manifest(
        public_path=public_path,
        output_dir=output_dir,
        products={"islam": product},
        llm_client=FakeLLMClient("Answer: A"),
        resume=False,
        case_ids=["q2"],
    )

    assert summary["total"]["total"] == 1
    assert sorted(path.name for path in (output_dir / "results").glob("*.json")) == ["q2.json"]


def test_run_direct_manifest_can_filter_public_cases_by_short_suffix_id(tmp_path):
    public = {
        "schemaVersion": 1,
        "benchmarkId": "mcq.generic.case_id_suffix.test",
        "taskType": "mcq",
        "product": "islam",
        "language": "en",
        "cases": [
            {"id": "tcm81-p1-q002", "prompt": "Question?\nA. alpha\nB. beta"},
            {"id": "tcm81-p1-q003", "prompt": "Question?\nA. alpha\nB. beta"},
        ],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
    product = ProductProfile(
        key="islam",
        name="Test Islam",
        db_path=Path("missing.sqlite3"),
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="",
        safety_notice="test",
    )

    summary = run_direct_manifest(
        public_path=public_path,
        output_dir=tmp_path / "run",
        products={"islam": product},
        llm_client=FakeLLMClient("Answer: A"),
        case_ids=["q003"],
    )

    assert summary["total"]["total"] == 1
    assert sorted(path.name for path in (tmp_path / "run" / "results").glob("*.json")) == ["tcm81-p1-q003.json"]


def test_run_direct_manifest_passes_model_to_llm_client(tmp_path):
    public = {
        "schemaVersion": 1,
        "benchmarkId": "mcq.generic.model.test",
        "taskType": "mcq",
        "product": "islam",
        "language": "en",
        "cases": [{"id": "q1", "prompt": "Question?\nA. alpha\nB. beta"}],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
    product = ProductProfile(
        key="islam",
        name="Test Islam",
        db_path=Path("missing.sqlite3"),
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="",
        safety_notice="test",
    )
    fake = FakeLLMClient("Answer: A")

    run_direct_manifest(
        public_path=public_path,
        output_dir=tmp_path / "run",
        products={"islam": product},
        llm_client=fake,
        model="gemma-direct-test",
    )

    assert fake.calls[0]["model"] == "gemma-direct-test"


def test_run_direct_manifest_records_model_metadata_in_artifacts_and_summary(tmp_path):
    public = {
        "schemaVersion": 1,
        "benchmarkId": "mcq.generic.model_metadata.test",
        "taskType": "mcq",
        "product": "islam",
        "language": "en",
        "cases": [{"id": "q1", "prompt": "Question?\nA. alpha\nB. beta"}],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
    product = ProductProfile(
        key="islam",
        name="Test Islam",
        db_path=Path("missing.sqlite3"),
        db_shape="precedents",
        languages=("en",),
        default_language="en",
        theme="",
        safety_notice="test",
    )

    summary = run_direct_manifest(
        public_path=public_path,
        output_dir=tmp_path / "run",
        products={"islam": product},
        llm_client=FakeLLMClient(
            "Answer: A",
            provider="direct_fixture_provider",
            default_model="gemma-default-test",
        ),
    )

    record = json.loads((tmp_path / "run" / "results" / "q1.json").read_text(encoding="utf-8"))
    expected = {"provider": "direct_fixture_provider", "model": "gemma-default-test", "decoding": {}}
    assert record["modelMetadata"] == expected
    assert record["llmProvider"] == "direct_fixture_provider"
    assert record["llmModel"] == "gemma-default-test"
    assert summary["modelMetadata"] == expected


def test_run_engine_manifest_records_candidate_coverage_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIGION_SELECTOR_EVIDENCE_CAPSULES", "1")

    class LowCoverageLLMClient:
        provider = "engine_fixture_provider"
        default_model = "gemma-engine-test"

        def complete(self, messages, *, model="", timeout_seconds=None):
            system = messages[0]["content"]
            if "keyword generator" in system:
                return '{"keywords":["sharedterm"]}'
            if "source selector" in system:
                return "<selection>\ndoc-generic\n</selection>"
            if "chunk-level claim-card analyzer" in system:
                return json.dumps(
                    {
                        "claim_cards": [
                            {
                                "source_label": "S1",
                                "source_id": "doc-generic",
                                "chunk_id": "question_selected_manual_0001",
                                "claim_axis": "generic low coverage",
                                "stance": "support",
                                "context_summary": "generic source selected despite low surface coverage",
                                "claim_summary": "generic religious source only",
                                "quote": "sharedterm generic religious source only.",
                            }
                        ]
                    }
                )
            if "answer planner" in system:
                return '{"body_claim_ids":["C1"],"coverage_required_claim_ids":["C1"],"answer_outline":["selected"],"citation_policy":"cite"}'
            if "source-grounded answer engine" in system:
                return "Answer: B [C1]"
            return "unused"

    db_path = tmp_path / "islam.sqlite3"
    conn = sqlite3.connect(db_path)
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
          ('doc-generic','islam/test','test','Generic source','Generic','fixture','','generic','fiqh_unit','sharedterm generic religious source only.','hash');
        INSERT INTO precedents_fts(canonical_id, full_text) VALUES ('doc-generic','sharedterm generic religious source only.');
        """
    )
    conn.commit()
    conn.close()
    public = {
        "schemaVersion": 1,
        "benchmarkId": "mcq.engine.coverage.test",
        "taskType": "mcq",
        "product": "islam",
        "language": "en",
        "cases": [
            {
                "id": "q1",
                "prompt": "Which CISI Islamic finance screening threshold is correct?\nA. 5%\nB. 30%\nC. 70%\nD. 90%",
            }
        ],
    }
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(public, ensure_ascii=False), encoding="utf-8")
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

    summary = run_engine_manifest(
        public_path=public_path,
        output_dir=tmp_path / "run",
        products={"islam": product},
        llm_client=LowCoverageLLMClient(),
        limit=5,
        analysis_mode="fast",
    )

    record = json.loads((tmp_path / "run" / "results" / "q1.json").read_text(encoding="utf-8"))
    assert record["selectorStatus"] == "completed"
    assert record["candidateCoverage"]["lowCoverage"] is True
    assert record["candidateIds"] == ["doc-generic"]
    assert record["candidateSetDigest"].startswith("sha256:")
    assert record["selectedCount"] > 0
    assert record["citedClaimCount"] == 1
    assert record["citedClaimSourceIds"] == ["doc-generic"]
    assert record["contextPacketCount"] == 1
    assert record["contextPacketIds"] == ["S1:doc-generic"]
    assert record["contextPacketArtifact"].endswith("context_packets.json")
    expected = {"provider": "engine_fixture_provider", "model": "gemma-engine-test", "decoding": {}}
    assert record["writerProvider"] == "engine_fixture_provider"
    assert record["writerModel"] == "gemma-engine-test"
    assert record["modelMetadata"] == expected
    assert summary["modelMetadata"] == expected
