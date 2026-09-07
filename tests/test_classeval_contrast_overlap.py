from tools import classeval_contrast_overlap as contrast
from tools import classeval_source_overlap_union as union


A = "class X:\n    def first(self): return 1\n    def second(self): return -1\n"
B = "class X:\n    def first(self): return -1\n    def second(self): return 2\n"
REPORTS = [
    {"cases": {"first": {"status": "passed", "methods": ["first"]},
               "second": {"status": "failed", "methods": ["second"]}}},
    {"cases": {"first": {"status": "failed", "methods": ["first"]},
               "second": {"status": "passed", "methods": ["second"]}}}]


def test_actual_first_contrast_transplant_repairs_and_preserves():
    candidate = contrast.proposals([A, B], "X", REPORTS, "overlap", "unit", 1)[0]
    namespace = {}
    exec(candidate["source"], namespace)
    obj = namespace["X"]()
    assert (obj.first(), obj.second()) == (1, 2)
    assert candidate["contrastWitness"] is not None
    assert "passed" not in candidate


def test_generic_control_and_complete_candidate_universe_unchanged():
    old = union.proposals([A, B], "X", REPORTS, "generic", "unit")
    control = contrast.proposals([A, B], "X", REPORTS, "generic", "unit")
    candidate = contrast.proposals([A, B], "X", REPORTS, "overlap", "unit")
    assert old == control
    assert {x["source"] for x in old} == {x["source"] for x in candidate}


def test_unknown_or_nonoverlapping_traces_do_not_create_witnesses():
    reports = [{"cases": {"a": {"status": "error", "methods": ["first"]}}},
               {"cases": {"a": {"status": "passed", "methods": ["second"]}}}]
    assert all(x["contrastWitness"] is None
               for x in contrast.proposals([A, B], "X", reports, "overlap", "unit"))
