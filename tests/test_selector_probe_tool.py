import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from shared_platform.products import ProductProfile
from shared_platform.search import SearchResult


def _load_probe():
    path = Path("tools/probe_beta6_selector.py")
    spec = importlib.util.spec_from_file_location("probe_beta6_selector", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _row(source_id: str, *, kind: str = "classic_canon") -> SearchResult:
    return SearchResult(
        canonical_id=source_id,
        title=source_id,
        citation=source_id,
        authority_body="fixture",
        source_date="",
        case_name="",
        case_type="",
        full_text="fixture source text",
        source_dataset="",
        source_path="",
        score=1.0,
        source_kind=kind,
    )


def test_selector_probe_tool_writes_comparator_ready_artifact(tmp_path):
    probe = _load_probe()
    product = ProductProfile(
        key="tcm",
        name="Hanui AI",
        db_path=tmp_path / "tcm.sqlite3",
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="tcm",
        safety_notice="fixture",
    )
    rows = [
        _row("doc-a", kind="classic_canon"),
        _row("doc-b", kind="materia_medica"),
        _row("doc-c", kind="formulary"),
    ]

    def selector_fn(*args, **kwargs):
        return rows, {
            "status": "completed",
            "mode": "llm_keyword_search_and_batched_selector",
            "selectionSource": "gemma4_llm_batched_selector",
            "candidateCount": 1200,
            "topK": 3,
            "frontierTarget": 1200,
            "selectorInputMode": "raw_excerpt_v1+evidence_ledger_v1",
            "selectorEvidenceLedgerCount": 3,
            "selectorLocalRecoveryCount": 0,
            "selectorBatchSize": 100,
            "selectorBatchWorkers": 6,
            "selectorCandidateLimit": 1200,
            "selectorAuditedCandidateCount": 1200,
            "selectorBatchTrace": [
                {
                    "batch": 1,
                    "elapsedSec": 12.5,
                    "maxPreHttpWaitSec": 0.1,
                    "maxLlmElapsedSec": 12.0,
                    "maxPromptBytes": 58000,
                    "primaryMaxPromptBytes": 58000,
                    "recoveryMaxPromptBytes": 0,
                },
                {
                    "batch": 2,
                    "elapsedSec": 8.0,
                    "maxPreHttpWaitSec": 0.2,
                    "maxLlmElapsedSec": 7.5,
                    "maxPromptBytes": 15000,
                    "primaryMaxPromptBytes": 15000,
                    "recoveryMaxPromptBytes": 6000,
                },
            ],
        }

    ticks = iter([100.0, 105.0])
    report = probe.build_report(
        product=product,
        query="임신 오심과 부종",
        language="ko",
        limit=3,
        llm_client=object(),
        model="gemma",
        provider="fixture",
        cache_root=tmp_path / "cache",
        selector_fn=selector_fn,
        monotonic=lambda: next(ticks),
    )

    assert report["passes"] is True
    assert report["product"] == "tcm"
    assert report["candidateCount"] == 1200
    assert report["selectedCount"] == 3
    assert report["selectedIds"] == ["doc-a", "doc-b", "doc-c"]
    assert report["selectedSourceKinds"] == {"classic_canon": 1, "materia_medica": 1, "formulary": 1}
    assert report["selectorInputMode"] == "raw_excerpt_v1+evidence_ledger_v1"
    assert report["selectorEvidenceLedgerCount"] == 3
    assert report["selectorBatchSize"] == 100
    assert report["selectorBatchWorkers"] == 6
    assert report["selectorCandidateLimit"] == 1200
    assert report["selectorAuditedCandidateCount"] == 1200
    assert report["elapsedSec"] == 5.0
    assert report["selectorElapsedSec"] == 5.0
    assert report["selectorBatchElapsedSumSec"] == 20.5
    assert report["maxPreHttpWaitSec"] == 0.2
    assert report["maxLlmElapsedSec"] == 12.0
    assert report["maxPromptBytes"] == 58000
    assert report["maxPrimaryPromptBytes"] == 58000
    assert report["maxRecoveryPromptBytes"] == 6000


def test_selector_probe_tool_can_require_cold_selector_batches(tmp_path):
    probe = _load_probe()
    product = ProductProfile(
        key="tcm",
        name="Hanui AI",
        db_path=tmp_path / "tcm.sqlite3",
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="tcm",
        safety_notice="fixture",
    )

    def selector_fn(*args, **kwargs):
        return [_row("doc-a", kind="classic_canon")], {
            "status": "completed",
            "candidateCount": 1200,
            "selectorBatchCacheHits": 12,
            "selectorBatchCacheMisses": 0,
            "selectorBatchTrace": [{"batch": 1, "elapsedSec": 0.001, "cacheHit": True}],
        }

    ticks = iter([100.0, 100.1])
    report = probe.build_report(
        product=product,
        query="fixture",
        language="ko",
        limit=1,
        llm_client=object(),
        model="gemma",
        provider="fixture",
        cache_root=tmp_path / "cache",
        selector_fn=selector_fn,
        require_cold_selector=True,
        monotonic=lambda: next(ticks),
    )

    assert report["passes"] is False
    assert report["coldSelector"]["passes"] is False
    assert report["coldSelector"]["cacheHits"] == 12
    assert report["coldSelector"]["cacheMisses"] == 0


def test_selector_probe_tool_main_writes_output_json(tmp_path, monkeypatch):
    probe = _load_probe()
    product = ProductProfile(
        key="tcm",
        name="Hanui AI",
        db_path=tmp_path / "tcm.sqlite3",
        db_shape="precedents",
        languages=("ko", "en"),
        default_language="ko",
        theme="tcm",
        safety_notice="fixture",
    )
    monkeypatch.setitem(probe.PRODUCT_PROFILES, "tcm", product)
    monkeypatch.setattr(probe, "default_llm_client_from_env", lambda: object())
    monkeypatch.setattr(
        probe,
        "select_rows_with_beta6_llm",
        lambda *args, **kwargs: (
            [_row("doc-a", kind="classic_canon")],
            {"status": "completed", "candidateCount": 1200, "topK": 1, "selectorBatchTrace": []},
        ),
    )
    output = tmp_path / "probe.json"

    code = probe.main(
        [
            "--product",
            "tcm",
            "--query",
            "fixture",
            "--language",
            "ko",
            "--limit",
            "1",
            "--output",
            str(output),
        ]
    )

    assert code == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["passes"] is True
    assert data["selectedIds"] == ["doc-a"]


def test_selector_probe_tool_can_run_as_direct_script():
    result = subprocess.run(
        [sys.executable, "tools/probe_beta6_selector.py", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "selector-only probe" in result.stdout
