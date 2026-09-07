from tools.score_mmlu_pro_cumulative import compare_correctness, fixed_sequence


def test_pooled_direct_luna_counts_and_exact_tail() -> None:
    candidate = [True] * 33 + [False] * 6
    reference = [False] * 33 + [True] * 6
    result = compare_correctness(candidate, reference, ["s"] * 39, samples=200)
    assert result["rescues"] == 33
    assert result["harms"] == 6
    assert result["netCorrect"] == 27
    assert result["oneSidedExactMcNemarP"] < 0.025


def test_fixed_sequence_stops_after_second_comparison() -> None:
    comparisons = {
        "OJ3_vs_D1": {"netCorrect": 27, "oneSidedExactMcNemarP": 0.001},
        "OJ3_vs_SC3": {"netCorrect": 5, "oneSidedExactMcNemarP": 0.09},
        "OJ3_vs_GJ3": {"netCorrect": 3, "oneSidedExactMcNemarP": 0.25},
    }
    result = fixed_sequence(comparisons)
    assert result[0]["confirmatoryReached"] is True
    assert result[0]["rejectedAtAlpha0.025"] is True
    assert result[1]["confirmatoryReached"] is True
    assert result[1]["rejectedAtAlpha0.025"] is False
    assert result[2]["confirmatoryReached"] is False
    assert result[2]["rejectedAtAlpha0.025"] is False
