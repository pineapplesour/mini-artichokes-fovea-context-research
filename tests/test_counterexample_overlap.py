from tools.run_aider_counterexample_overlap import choose_sources, make_prompt


def test_full_five_candidate_fallback_preserves_early_success():
    candidates = [("fifth", {"a": False, "b": False}), ("fourth", {"a": False, "b": False}),
                  ("ordinary", {"a": False, "b": False}), ("graph", {"a": True, "b": False}),
                  ("plain", {"a": False, "b": False})]
    assert choose_sources(candidates, {"a", "b"}) == {"a": "graph", "b": "fifth"}


def test_identical_seed_and_ledger_requirements():
    for policy in ["generic", "overlap"]:
        for feedback in [True, False]:
            prompt = make_prompt("FULL TASK", policy, feedback)
            assert "exactly the fourth candidate" in prompt
            assert "taskId, hypothesis, check, observation, action" in prompt
            assert prompt.endswith("FULL TASK\n")


def test_generic_is_not_forbidden_from_candidate_comparison():
    assert "freely compare any candidates" in make_prompt("x", "generic", True)


def test_feedback_manipulation_is_explicit():
    assert "No official outcome of the fourth" in make_prompt("x", "overlap", False)
    assert "new feedback" in make_prompt("x", "overlap", True)
