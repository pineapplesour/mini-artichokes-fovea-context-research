import json
import sqlite3
from pathlib import Path

from shared_platform.products import ProductProfile
from tools import run_universal_benchmark


def _write(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _profile(db_path: Path) -> ProductProfile:
    return ProductProfile(
        key="fixture",
        name="Fixture",
        db_path=db_path,
        db_shape="precedents",
        languages=("ko",),
        default_language="ko",
        theme="fixture",
        safety_notice="fixture",
    )


class FakeEngine:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.queries = []

    def answer(self, query, *, language=""):
        self.queries.append((query, language))
        return {
            "answer": '{"finalAnswer":"2"}',
            "selectedEvidence": [
                {
                    "label": "S1",
                    "packetId": "S1:doc-1",
                    "sourceId": "doc-1",
                    "title": "Fixture source",
                    "citation": "ref-1",
                    "exactQuote": "support text",
                }
            ],
            "candidateCount": 2,
            "candidateIds": ["doc-1", "doc-2"],
            "modelMetadata": {
                "provider": "fixture_provider",
                "model": "shared-model",
                "decoding": {"temperature": 0.2},
            },
        }


def test_run_universal_manifest_runs_mcq_without_private_answers(tmp_path):
    public_path = tmp_path / "mcq.public.json"
    _write(
        public_path,
        {
            "benchmarkId": "mcq.fixture.v1",
            "taskType": "mcq",
            "product": "fixture",
            "language": "ko",
            "cases": [{"id": "q1", "prompt": "문제\n1. 갑\n2. 을"}],
        },
    )
    db_path = tmp_path / "db.sqlite3"
    sqlite3.connect(db_path).close()
    made = []

    def factory(**kwargs):
        engine = FakeEngine(**kwargs)
        made.append(engine)
        return engine

    summary = run_universal_benchmark.run_manifest(
        public_path=public_path,
        output_dir=tmp_path / "out",
        products={"fixture": _profile(db_path)},
        llm_client=object(),
        model="shared-model",
        engine_factory=factory,
    )

    artifact = json.loads((tmp_path / "out" / "results" / "q1.json").read_text(encoding="utf-8"))
    assert summary["mode"] == "universal"
    assert summary["total"] == {"total": 1, "predicted": 1, "errors": 0}
    assert artifact["prediction"] == "2"
    assert artifact["selectedEvidenceIds"] == ["doc-1"]
    assert artifact["contextPacketIds"] == ["S1:doc-1"]
    assert artifact["modelMetadata"]["model"] == "shared-model"
    assert "correctOptionId" not in json.dumps(artifact, ensure_ascii=False)
    assert "정답: <보기ID>" in made[0].queries[0][0]


def test_run_universal_manifest_runs_every_legal_variant(tmp_path):
    public_path = tmp_path / "legal.public.json"
    _write(
        public_path,
        {
            "benchmarkId": "legal.fixture.v1",
            "taskType": "legal_retrieval_answer",
            "product": "fixture",
            "language": "ko",
            "cases": [
                {
                    "id": "case1",
                    "graderRef": "grader1",
                    "variants": [
                        {"id": "v1", "query": "첫 질문"},
                        {"id": "v2", "query": "같은 뜻의 둘째 질문"},
                    ],
                }
            ],
        },
    )
    db_path = tmp_path / "db.sqlite3"
    sqlite3.connect(db_path).close()

    summary = run_universal_benchmark.run_manifest(
        public_path=public_path,
        output_dir=tmp_path / "out",
        products={"fixture": _profile(db_path)},
        llm_client=object(),
        model="shared-model",
        engine_factory=FakeEngine,
    )

    assert summary["total"] == {"total": 2, "predicted": 2, "errors": 0}
    first = json.loads((tmp_path / "out" / "results" / "case1__v1.json").read_text(encoding="utf-8"))
    second = json.loads((tmp_path / "out" / "results" / "case1__v2.json").read_text(encoding="utf-8"))
    assert first["graderId"] == "grader1"
    assert first["answer"] == '{"finalAnswer":"2"}'
    assert second["query"] == "같은 뜻의 둘째 질문"
