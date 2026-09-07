import ast

from tools import classeval_subtree_overlap as subtree


A = "class X:\n    def f(self, x):\n        if x < 0:\n            return 0\n        return -1\n"
B = "class X:\n    def f(self, x):\n        if x < 0:\n            return -1\n        return x + 1\n"
REPORTS = [{"cases": {"negative": {"status": "passed", "methods": ["f"]}}},
           {"cases": {"positive": {"status": "passed", "methods": ["f"]}}}]


def test_common_subtrees_can_combine_repairs_inside_one_method():
    outputs = subtree.proposals([A, B], "X", REPORTS, "overlap", "unit")
    solved = []
    for candidate in outputs:
        namespace = {}
        exec(candidate["source"], namespace)
        instance = namespace["X"]()
        solved.append(instance.f(-1) == 0 and instance.f(3) == 4)
        assert "passed" not in candidate
    assert any(solved)
    # Neither intact method can solve both obligations.
    for source in (A, B):
        namespace = {}
        exec(source, namespace)
        x = namespace["X"]()
        assert not (x.f(-1) == 0 and x.f(3) == 4)


def test_both_policies_get_same_fine_grained_space_and_cap():
    generic = subtree.proposals([A, B], "X", REPORTS, "generic", "unit")
    overlap = subtree.proposals([A, B], "X", REPORTS, "overlap", "unit")
    assert {c["source"] for c in generic} == {c["source"] for c in overlap}
    assert len(subtree.proposals([A, B], "X", REPORTS, "generic", "unit", limit=1)) == 1
    assert all(c["predictedPassingCases"] < 2 for c in overlap)


def test_list_insert_delete_and_empty_space_remain_valid_python():
    sources = ["class X:\n    def f(self):\n        x = 1\n        return x\n",
               "class X:\n    def f(self):\n        x = 2\n        y = 3\n        return x + y\n"]
    for c in subtree.proposals(sources, "X", REPORTS, "generic", "unit"):
        ast.parse(c["source"])
    assert subtree.proposals([A, A], "X", REPORTS, "generic", "unit") == []


def test_coarsening_preserves_exact_parent_corners():
    parsed, plans, context, slots = subtree.source_space([A, B], "X", max_slots=1)
    assert len(slots) == 1
    for bit, source in enumerate((A, B)):
        restored = subtree.materialize(parsed, plans, context, "X", (bit,))
        assert ast.dump(ast.parse(restored)) == ast.dump(ast.parse(source))
