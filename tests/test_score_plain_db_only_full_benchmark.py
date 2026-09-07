from tools.score_plain_db_only_full_benchmark import SCORER_ID, group_id


def test_database_arm_judge_group_identity_is_stable_and_separate():
    first = group_id(benchmark_id="fixture", case_ids=["q1", "q2"], judge_model="judge")
    second = group_id(benchmark_id="fixture", case_ids=["q1", "q2"], judge_model="judge")
    assert first == second
    assert first.startswith("judgedb-")
    assert "db-only" in SCORER_ID
