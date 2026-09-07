import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "tools" / "verify_answer_quality_corpus.py"


def _run_verifier(*args):
    completed = subprocess.run(
        [sys.executable, str(VERIFIER), *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    return json.loads(completed.stdout)


def _write_result(path: Path, product: str, answer: str) -> None:
    if product == "simli" and "## 1. 가능 가설" not in answer:
        answer += "\n\n## 1. 가능 가설\n## 2. 왜 이 가설인가\n## 3. 추가 평가 필요\n## 4. 다음 세션 개입\n## 5. 약물 / 의뢰 고려\n## 6. 안전 계획\n## 7. 근거 한계\n## References\n"
    claim_cards = [
        {
            "claimId": "C1",
            "label": "C1",
            "sourceId": f"{product}-source-1",
            "citation": "Source 1",
            "quote": "verified quote one",
            "span": {"start": 0, "end": 18},
            "supportCount": 2,
            "supportingClaims": [
                {"label": "S1", "sourceId": f"{product}-source-1", "quote": "verified quote one", "span": {"start": 0, "end": 18}},
                {"label": "S2", "sourceId": f"{product}-source-2", "quote": "verified quote two", "span": {"start": 4, "end": 22}},
            ],
        }
    ]
    sources = [
        {"id": f"{product}-source-{index}", "sourceKind": kind, "citation": f"Source {index}"}
        for index, kind in enumerate(("canon", "commentary", "guideline", "research", "case"), start=1)
    ]
    result = {
        "product": product,
        "language": "ko",
        "answer": answer,
        "answerSections": [{"title": "section", "body": answer, "citations": ["C1"]}],
        "citationMap": {"C1": {"label": "C1", "sourceId": f"{product}-source-1"}},
        "sources": sources * 20,
        "claimCards": claim_cards * 100,
        "candidateClaimCards": claim_cards * 8,
        "citedClaimCards": claim_cards,
        "passageWindows": [
            {
                "claimId": "C1",
                "sourceId": f"{product}-source-1",
                "text": "verified quote one in surrounding text",
                "highlightStart": 0,
                "highlightEnd": 18,
            }
        ],
        "beta6": {
            "selectorStatus": "completed",
            "writerStatus": "completed",
            "selectedCount": 100,
            "claimCardCount": 100,
            "claimAnalyzer": {
                "status": "completed",
                "quoteGate": {"accepted": 1, "rejected": 0},
            },
            "answerPlanner": {"status": "completed"},
        },
    }
    path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


def test_answer_quality_corpus_verifier_checks_real_result_contracts(tmp_path):
    assert VERIFIER.exists()
    artifact = tmp_path / "islam-result.json"
    _write_result(
        artifact,
        "islam",
        "학파별 견해를 단정하지 않고 근거를 비교합니다. 파트와가 아니며 qualified scholar 확인이 필요합니다. [C1] "
        + "근거 설명 " * 260,
    )

    report = _run_verifier(
        "--json",
        "--case",
        f"islam={artifact}",
        "--min-answer-chars",
        "islam=1200",
        "--min-cited-claims",
        "islam=1",
        "--min-source-kinds",
        "islam=3",
    )

    assert report["passes"] is True
    assert report["cases"][0]["product"] == "islam"
    assert report["cases"][0]["checks"]["sourceCount"]["passes"] is True
    assert report["cases"][0]["checks"]["citedClaimCards"]["passes"] is True
    assert report["cases"][0]["checks"]["citationUse"]["passes"] is True
    assert report["cases"][0]["checks"]["passageWindowHighlight"]["passes"] is True
    assert report["cases"][0]["checks"]["domainBoundary"]["passes"] is True


def test_answer_quality_corpus_verifier_default_islam_case_guards_depth_floor_artifact():
    report = _run_verifier("--json")
    islam_case = next(case for case in report["cases"] if case["product"] == "islam")

    assert islam_case["path"].endswith("runs/actual_user_path_islam_depth_floor_20260507.json")
    assert islam_case["checks"]["answerChars"]["passes"] is True
    assert islam_case["checks"]["citedClaimCards"]["expected"] == ">=6"
    assert islam_case["metrics"]["citedClaimCardCount"] >= 6


def test_answer_quality_corpus_verifier_default_tcm_and_simli_cases_are_fresh_actual_artifacts():
    report = _run_verifier("--json")
    tcm_case = next(case for case in report["cases"] if case["product"] == "tcm")
    simli_case = next(case for case in report["cases"] if case["product"] == "simli")

    assert tcm_case["path"].endswith("runs/actual_user_path_tcm_depth_floor_20260507.json")
    assert tcm_case["checks"]["citedClaimCards"]["expected"] == ">=3"
    assert tcm_case["metrics"]["citedClaimCardCount"] >= 3
    assert tcm_case["checks"]["answerChars"]["passes"] is True

    assert simli_case["path"].endswith("runs/actual_user_path_simli_depth_floor_20260507.json")
    assert simli_case["checks"]["citedClaimCards"]["expected"] == ">=20"
    assert simli_case["metrics"]["citedClaimCardCount"] >= 20
    assert simli_case["checks"]["domainStructure"]["passes"] is True


def test_answer_quality_corpus_verifier_fails_weak_uncited_answers(tmp_path):
    artifact = tmp_path / "simli-result.json"
    _write_result(artifact, "simli", "짧은 답변입니다.")
    data = json.loads(artifact.read_text(encoding="utf-8"))
    data["citedClaimCards"] = []
    data["answer"] = "짧은 답변입니다."
    artifact.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(VERIFIER), "--json", "--case", f"simli={artifact}", "--min-answer-chars", "simli=1200"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
    )

    assert completed.returncode == 1
    report = json.loads(completed.stdout)
    assert report["passes"] is False
    case = report["cases"][0]
    assert case["checks"]["answerChars"]["passes"] is False
    assert case["checks"]["citedClaimCards"]["passes"] is False


def test_answer_quality_corpus_verifier_can_write_artifact(tmp_path):
    result_path = tmp_path / "tcm-result.json"
    report_path = tmp_path / "quality-report.json"
    _write_result(
        result_path,
        "tcm",
        "감초와 임신 중 사용에 대해 의학적 진단이나 처방이 아니며 한의사 또는 의사와 상담해야 합니다. 본초 금기와 문헌 차이를 비교합니다. [C1] "
        + "근거 설명 " * 260,
    )

    report = _run_verifier(
        "--json",
        "--case",
        f"tcm={result_path}",
        "--output",
        str(report_path),
        "--min-answer-chars",
        "tcm=1200",
        "--min-cited-claims",
        "tcm=1",
    )

    assert report_path.exists()
    assert json.loads(report_path.read_text(encoding="utf-8")) == report
    assert report["passes"] is True


def test_answer_quality_corpus_verifier_allows_rejected_unverified_quote_candidates(tmp_path):
    artifact = tmp_path / "simli-result.json"
    _write_result(
        artifact,
        "simli",
        "진단을 내리지 않고 전문가 상담과 안전 확인을 전제로 가능한 가설을 비교합니다. [C1] " + "근거 설명 " * 260,
    )
    data = json.loads(artifact.read_text(encoding="utf-8"))
    data["beta6"]["claimAnalyzer"]["quoteGate"] = {"accepted": 2, "forceMatched": 1, "recovered": 1, "rejected": 21}
    artifact.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    report = _run_verifier(
        "--json",
        "--case",
        f"simli={artifact}",
        "--min-answer-chars",
        "simli=1200",
        "--min-cited-claims",
        "simli=1",
    )

    assert report["passes"] is True
    assert report["cases"][0]["checks"]["quoteGateVerified"]["passes"] is True
    assert report["cases"][0]["metrics"]["quoteGate"]["rejected"] == 21
    assert report["cases"][0]["checks"]["domainStructure"]["passes"] is True


def test_answer_quality_corpus_verifier_allows_cited_claims_from_full_ledger(tmp_path):
    artifact = tmp_path / "simli-result.json"
    _write_result(
        artifact,
        "simli",
        "진단을 단정하지 않고 전문가 상담과 안전 확인을 전제로 근거를 비교합니다. [S11] [S17] " + "근거 설명 " * 260,
    )
    data = json.loads(artifact.read_text(encoding="utf-8"))
    claim = data["claimCards"][0]
    data["candidateClaimCards"] = [claim]
    data["citedClaimCards"] = [
        {**claim, "label": "S11", "claimId": "C11"},
        {**claim, "label": "S17", "claimId": "C17"},
    ]
    data["citationMap"] = {"S11": {"label": "S11"}, "S17": {"label": "S17"}}
    artifact.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    report = _run_verifier(
        "--json",
        "--case",
        f"simli={artifact}",
        "--min-answer-chars",
        "simli=1200",
        "--min-cited-claims",
        "simli=2",
    )

    assert report["passes"] is True
    assert report["cases"][0]["checks"]["candidateClaimCards"]["passes"] is True
    assert report["cases"][0]["metrics"]["candidateClaimCardCount"] == 1
    assert report["cases"][0]["metrics"]["citedClaimCardCount"] == 2
