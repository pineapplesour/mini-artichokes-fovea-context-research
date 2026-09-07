from tools.score_aider_hidden_campaigns import exact_mcnemar, paired_bootstrap_ci


def test_exact_mcnemar_matches_known_tail() -> None:
    result = exact_mcnemar(10, 2)
    assert result["oneSidedP"] == 79 / 4096
    assert result["twoSidedP"] == 158 / 4096


def test_paired_bootstrap_is_deterministic() -> None:
    first = paired_bootstrap_ci([1, 1, 0, -1], draws=1_000, seed=7)
    second = paired_bootstrap_ci([1, 1, 0, -1], draws=1_000, seed=7)
    assert first == second
