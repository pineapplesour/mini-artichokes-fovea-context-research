import pytest

from tools.analyze_classeval_contrast import paired, holm, check_report


def test_exact_paired_rescues_and_harms():
    result = paired([True] * 5, [False] * 5)
    assert result["rescues"] == 5 and result["harms"] == 0
    assert result["conditionalOneSidedP"] == 1 / 32
    assert result["conditionalTwoSidedP"] == 1 / 16


def test_identical_vectors_do_not_claim_significance():
    result = paired([True, False], [True, False])
    assert result["net"] == 0
    assert result["conditionalOneSidedP"] == result["conditionalTwoSidedP"] == 1


def test_holm_family_preserves_input_order_and_monotonicity():
    assert holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])


def test_passing_boolean_requires_actual_complete_case_evidence():
    with pytest.raises(ValueError):
        check_report({"passed": True, "cases": {}, "expectedCount": 0})
    assert check_report({"passed": True, "cases": {"t": {"status": "passed"}}, "expectedCount": 1})
