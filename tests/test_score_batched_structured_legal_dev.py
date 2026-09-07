import json

from tools import score_batched_structured_legal_dev as subject


def pred(outcome: str, clause: str = "F001", issue: str = "REQUIRED_ELEMENT_PRESENT") -> dict:
    return {
        "outcome": outcome,
        "evidenceAtoms": [
            {"issueCode": issue, "clauseId": clause, "direction": "FAVORS_GRANT" if outcome == "인용됨" else "FAVORS_DISMISS"}
        ],
    }


def test_sc3_uses_binary_majority() -> None:
    assert subject.sc3(pred("기각"), pred("인용됨"), pred("인용됨")) == "인용됨"


def test_answer_only_switches_on_d2_d3_consensus() -> None:
    assert subject.answer_only(pred("기각"), pred("인용됨"), pred("인용됨")) == "인용됨"
    assert subject.answer_only(pred("기각"), pred("인용됨"), pred("기각")) == "기각"


def test_strict_overlap_requires_issue_and_clause_match() -> None:
    d1 = pred("기각")
    d2 = pred("인용됨", "F002", "BURDEN_OR_STANDARD_MET")
    d3 = pred("인용됨", "F002", "REQUIRED_ELEMENT_PRESENT")
    assert subject.overlap_policy(d1, d2, d3, mode="strict") == "기각"
    assert subject.overlap_policy(d1, d2, d3, mode="clause_direction") == "인용됨"


def test_overlap_does_not_switch_without_answer_consensus() -> None:
    d1 = pred("기각")
    assert subject.overlap_policy(d1, pred("인용됨"), pred("기각"), mode="strict") == "기각"


def test_one_sided_mcnemar_direction() -> None:
    result = subject.compare([True, True, True, False], [False, False, True, False])
    assert result["rescues"] == 2
    assert result["harms"] == 0
    assert result["oneSidedExactMcNemarP"] == 0.25


def test_metrics_supports_single_domain_development_set() -> None:
    values, correct = subject.metrics(
        ["인용됨", "기각"],
        ["outcome-civil-a", "outcome-civil-b"],
        {"outcome-civil-a": "인용됨", "outcome-civil-b": "인용됨"},
    )
    assert correct == [True, False]
    assert values["domains"] == {"civil": {"n": 2, "correct": 1, "accuracy": 0.5}}


def test_load_draw_preserves_binary_answer_but_disables_invalid_atoms(tmp_path) -> None:
    shard = tmp_path / "D1" / "shard_0000"
    shard.mkdir(parents=True)
    (shard / "receipt.json").write_text(json.dumps({"status": "rejected"}))
    (shard / "normalized.json").write_text(json.dumps([{"id": "a", "prediction": None}]))
    (shard / "response.json").write_text(
        json.dumps({"predictions": [{"id": "a", "outcome": "기각", "rationale": "x", "evidenceAtoms": [{"clauseId": "F999"}]}]})
    )
    loaded = subject.load_draw(tmp_path, "D1", {"a": {"id": "a", "prompt": "[F001] 사실"}})
    assert subject.outcome(loaded["a"]) == "기각"
    assert loaded["a"]["evidenceAtoms"] == []


def test_load_draw_recovers_valid_id_keyed_row_after_batch_order_rejection(tmp_path) -> None:
    shard = tmp_path / "D1" / "shard_0000"
    shard.mkdir(parents=True)
    (shard / "receipt.json").write_text(json.dumps({"status": "rejected"}))
    (shard / "normalized.json").write_text(json.dumps([{"id": "a", "prediction": None}]))
    raw = {
        "id": "a",
        "outcome": "인용됨",
        "rationale": "사실이 인정된다.",
        "evidenceAtoms": [
            {"issueCode": "REQUIRED_ELEMENT_PRESENT", "clauseId": "F001", "direction": "FAVORS_GRANT"}
        ],
    }
    (shard / "response.json").write_text(json.dumps({"predictions": [raw]}))
    loaded = subject.load_draw(tmp_path, "D1", {"a": {"id": "a", "prompt": "[F001] 사실"}})
    assert loaded["a"] == raw
