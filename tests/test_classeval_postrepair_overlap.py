import pytest

from tools import run_classeval_source_overlap as base
from tools.replay_classeval_helper_union import postrepair_parents


def report(count, passed=False):
    return {"passed": passed, "cases": {str(i): {"status": "passed"} for i in range(count)}}


def setup_final(root, score, repair_from=None):
    final = root / "ordinary-final"
    final.mkdir()
    (final / "selected.py").write_text("class X: pass\n")
    base.write_json(final / "evaluation.json", score)
    base.write_json(final / "result.json", {"passed": score["passed"], "repairFrom": repair_from})


def test_verified_ordinary_final_does_not_require_or_run_repair(tmp_path):
    setup_final(tmp_path, report(3, True))
    hashes = {}
    parents = postrepair_parents(tmp_path, [], hashes, True)
    assert len(parents) == 1 and parents[0]["report"]["passed"]
    assert "ordinary-final" in hashes


def test_uses_exact_ordinary_repair_and_strongest_original_parent(tmp_path):
    setup_final(tmp_path, report(2), "repair-2")
    repair = tmp_path / "repair-2"
    repair.mkdir()
    (repair / "candidate.py").write_text("class X: pass\n")
    base.write_json(repair / "receipt.json", {"valid": True})
    base.write_json(repair / "evaluation.json", report(1))
    a = {"source": "A", "valid": True, "report": report(1)}
    b = {"source": "B", "valid": True, "report": report(2)}
    hashes = {}
    pair = postrepair_parents(tmp_path, [a, b], hashes, False)
    assert pair[0] == b and len(pair) == 2
    assert set(hashes) == {"ordinary-final", "repair-2"}


def test_missing_or_unsafe_repair_identity_is_not_guessed(tmp_path):
    setup_final(tmp_path, report(1), "../other-policy")
    with pytest.raises(ValueError, match="exact ordinary"):
        postrepair_parents(tmp_path, [], {}, False)


def test_declared_outcome_must_match_materialized_result(tmp_path):
    setup_final(tmp_path, report(2, True))
    with pytest.raises(ValueError, match="outcome mismatch"):
        postrepair_parents(tmp_path, [], {}, False)
