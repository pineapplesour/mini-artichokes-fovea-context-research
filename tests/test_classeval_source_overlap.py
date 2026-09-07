import ast

import pytest

from tools.classeval_source_overlap import proposals, source_space
from tools.run_classeval_source_overlap import DATA_SHA, load_data, sha, DATA, evaluation_source, source_scope


A = "class Example:\n def x(self): return 1\n def y(self): return -1\n"
B = "class Example:\n def x(self): return -1\n def y(self): return 2\n"
FEEDBACK = [{"cases": {"x": {"status": "passed", "methods": ["x"]},
                       "y": {"status": "failed", "methods": ["y"]}}},
            {"cases": {"x": {"status": "failed", "methods": ["x"]},
                       "y": {"status": "passed", "methods": ["y"]}}}]


def test_actual_composition_not_sum_of_test_outcomes():
    candidate = proposals([A, B], "Example", FEEDBACK, "overlap", "unit", limit=1)[0]
    namespace = {}
    exec(candidate["source"], namespace)
    instance = namespace["Example"]()
    assert (instance.x(), instance.y()) == (1, 2)
    assert candidate["predictedPassingCases"] == 2
    assert "passed" not in candidate


def test_overlapping_methods_require_consistent_donor():
    reports = [{"cases": {"one": {"status": "passed", "methods": ["x", "y"]}}},
               {"cases": {"two": {"status": "passed", "methods": ["x", "y"]}}}]
    candidates = proposals([A, B], "Example", reports, "overlap", "unit")
    assert all(c["predictedPassingCases"] == 0 for c in candidates)


def test_same_space_and_budget_and_deterministic_control():
    generic = proposals([A, B], "Example", FEEDBACK, "generic", "unit")
    overlap = proposals([A, B], "Example", FEEDBACK, "overlap", "unit")
    assert {c["source"] for c in generic} == {c["source"] for c in overlap}
    assert generic == proposals([A, B], "Example", FEEDBACK, "generic", "unit")
    assert len(generic) == 2
    assert proposals([A, A], "Example", FEEDBACK, "generic", "unit") == []


def test_missing_or_unknown_support_does_not_vote():
    unknown = [{"cases": {"x": {"status": "not_reported", "methods": ["x"]}}},
               {"cases": {"y": {"status": "passed", "methods": []}}}]
    assert all(c["predictedPassingCases"] == 0
               for c in proposals([A, B], "Example", unknown, "overlap", "unit"))


def test_duplicate_and_changed_inventories_rejected_without_dropping_task():
    with pytest.raises(ValueError, match="inventories"):
        source_space([A, B.replace("def y", "def z")], "Example")
    with pytest.raises(ValueError, match="duplicate"):
        source_space([A + " def x(self): return 3\n", B], "Example")


def test_official_inventory_is_complete_and_pinned():
    data = load_data()
    assert len(data) == 100
    assert sum(len(r["methods_info"]) for r in data) == 410
    assert sha(DATA) == DATA_SHA


def test_pro_full_inventory_and_author_preprocessing():
    assert len(load_data("classeval-pro")) == 300
    code = "class Example:\n    def f(x):\n        return x\n"
    normalized = evaluation_source({"_dataset": "classeval-pro"}, code)
    assert "    @staticmethod\n    def f(x)" in normalized
    assert evaluation_source({"_dataset": "classeval-pro"}, normalized) == normalized
    assert evaluation_source({"_dataset": "classeval"}, code) == code


def test_generated_cache_is_not_submitted_source(tmp_path):
    (tmp_path / "solution.py").write_text(A)
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "solution.cpython-312.pyc").write_bytes(b"not submitted")
    assert source_scope(tmp_path) == (True, ["__pycache__/solution.cpython-312.pyc"])
    (tmp_path / "helper.py").write_text("pass")
    assert not source_scope(tmp_path)[0]


def test_symlink_never_accepted_as_a_cache(tmp_path):
    (tmp_path / "solution.py").write_text(A)
    (tmp_path / "__pycache__").symlink_to(tmp_path, target_is_directory=True)
    assert not source_scope(tmp_path)[0]
