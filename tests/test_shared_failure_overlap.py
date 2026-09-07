from tools.run_aider_shared_failure_overlap import COMMON, GENERIC, OVERLAP, LABELS, make_feedback, make_prompt


def test_failed_same_lineage_is_not_cross_lineage_support():
    captures = {}
    for label, status in zip(LABELS, ["passed", "failed", "failed"]):
        captures[label] = {"tasks": {"task": {"passed": False, "outputHead": "",
            "cases": {"case": {"status": status, "message": "bad\n\tat Frame"}}}}}
    row = make_feedback(captures)["task"]
    assert row["crossLineageSharedFailures"] == []
    assert row["caseStatus"]["case"] == ["passed", "failed", "failed"]
    captures["plain"]["tasks"]["task"]["cases"]["case"]["status"] = "failed"
    row = make_feedback(captures)["task"]
    assert row["crossLineageSharedFailures"] == ["case"]
    assert row["failures"]["case"] == [{"candidates": LABELS, "message": "bad"}]


def test_both_policies_receive_same_unrestricted_feedback_and_scope():
    for policy in [GENERIC, OVERLAP]:
        prompt = COMMON.replace("{policy}", policy).replace("{instruction}", "all tasks")
        assert "Both policies may use ALL of this data" in prompt
        assert "Only listed solution\nfiles are writable" in prompt
        assert "budget is900seconds" in prompt
        assert "taskId, hypothesis, check, observation, action" in prompt
    assert "derived overlap fields" in GENERIC
    assert "not two\nindependent votes" in OVERLAP


def test_original_prompt_is_unchanged_without_reserve():
    for policy, text in [("generic", GENERIC), ("overlap", OVERLAP)]:
        expected = COMMON.replace("{policy}", text).replace("{instruction}", "task")
        assert make_prompt("task", policy) == expected
        reserved = make_prompt("task", policy, 180, 1000)
        assert reserved.startswith(expected)
        assert "editing by epoch 1720" in reserved
        assert "response by epoch 1840" in reserved
        assert "unchanged900-second hard cap" in reserved


def test_five_pair_test_and_frozen_call_order():
    from tools.run_shared_failure_replication import randomization_p, ORDERS
    assert len(ORDERS) == 5
    assert all(set(order) == {"generic", "overlap"} for order in ORDERS)
    assert randomization_p([1, 1, 1, 1, 1]) == 1 / 32
    assert randomization_p([0, 0, 0, 0, 0]) == 1.0
