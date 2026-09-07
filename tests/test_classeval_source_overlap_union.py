import ast

from tools.classeval_source_overlap_union import proposals


A = """class Example:
    def x(self): return self.left_helper()
    def y(self): return -1
    def left_helper(self): return 1
"""
B = """class Example:
    def x(self): return -1
    def y(self): return self.right_helper()
    def right_helper(self): return 2
"""
FEEDBACK = [{"cases": {"x": {"status": "passed", "methods": ["x", "left_helper"]},
                       "y": {"status": "failed", "methods": ["y"]}}},
            {"cases": {"x": {"status": "failed", "methods": ["x"]},
                       "y": {"status": "passed", "methods": ["y", "right_helper"]}}}]


def test_exclusive_helpers_are_transferred_with_actual_method_combination():
    proposal = proposals([A, B], "Example", FEEDBACK, "overlap", "unit", 1)[0]
    namespace = {}
    exec(proposal["source"], namespace)
    instance = namespace["Example"]()
    assert (instance.x(), instance.y()) == (1, 2)
    assert instance.left_helper() == 1 and instance.right_helper() == 2
    assert "passed" not in proposal


def test_enriched_corner_program_is_not_treated_as_original_verified_parent():
    left = "class Example:\n def x(self): return 1\n"
    right = "class Example:\n def y(self): return 2\n"
    candidates = proposals([left, right], "Example", [{"cases": {}}, {"cases": {}}], "overlap", "unit")
    assert len(candidates) == 1
    assert candidates[0]["predictedPassingCases"] == 0
    assert "passed" not in candidates[0]
    namespace = {}
    exec(candidates[0]["source"], namespace)
    assert namespace["Example"]().y() == 2


def test_generic_has_the_same_space_and_no_hidden_enrichment_evaluations():
    generic = proposals([A, B], "Example", FEEDBACK, "generic", "unit")
    overlap = proposals([A, B], "Example", FEEDBACK, "overlap", "unit")
    assert len(generic) == len(overlap) == 4
    assert {ast.dump(ast.parse(x["source"])) for x in generic} == {
        ast.dump(ast.parse(x["source"])) for x in overlap}
    assert len(proposals([A, B], "Example", FEEDBACK, "generic", "unit", 1)) == 1
