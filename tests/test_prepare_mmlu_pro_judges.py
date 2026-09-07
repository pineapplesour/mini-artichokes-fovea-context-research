from tools.prepare_mmlu_pro_judges import build_packets


def test_matched_packets_share_conflicts_and_roles() -> None:
    questions = [
        {
            "id": "q1",
            "prompt": "Pick one\nA. alpha\nB. beta\nC. gamma",
            "responseFormat": "mcq",
        },
        {
            "id": "q2",
            "prompt": "Pick one\nA. alpha\nB. beta\nC. gamma",
            "responseFormat": "mcq",
        },
    ]
    answers = {
        "D1": {"q1": "alpha", "q2": "alpha"},
        "D2": {"q1": "beta", "q2": "beta"},
        "D3": {"q1": "beta", "q2": "gamma"},
    }
    generic, generic_roles = build_packets(questions, answers, "generic")
    overlap, overlap_roles = build_packets(questions, answers, "overlap")
    assert [row["id"] for row in generic] == ["q1"]
    assert [row["id"] for row in overlap] == ["q1"]
    assert generic_roles == overlap_roles
    assert "mechanicalIndependentSupport" not in generic[0]["prompt"]
    assert "mechanicalIndependentSupport" in overlap[0]["prompt"]
