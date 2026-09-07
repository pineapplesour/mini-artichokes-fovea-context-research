from tools import run_batched_structured_legal_dev as subject


def row(case_id: str, clause: str = "[F001] 사실이다.") -> dict[str, str]:
    return {"id": case_id, "prompt": clause}


def prediction(case_id: str, *, clause_id: str = "F001", outcome: str = "인용됨") -> dict:
    return {
        "id": case_id,
        "outcome": outcome,
        "rationale": "결정적 사실이 충족된다.",
        "evidenceAtoms": [
            {
                "issueCode": "REQUIRED_ELEMENT_PRESENT",
                "clauseId": clause_id,
                "direction": "FAVORS_GRANT" if outcome == "인용됨" else "FAVORS_DISMISS",
            }
        ],
    }


def test_make_shards_respects_item_and_character_limits() -> None:
    rows = [row(f"c{i}", "x" * 6) for i in range(5)]
    shards = subject.make_shards(rows, max_items=3, max_chars=12)
    assert [[item["id"] for item in shard] for shard in shards] == [["c0", "c1"], ["c2", "c3"], ["c4"]]


def test_validate_response_accepts_exact_ordered_grounded_rows() -> None:
    rows = [row("a"), row("b", "[C001] 청구한다.\n[F001] 사실이다.")]
    value = {"predictions": [prediction("a"), prediction("b", outcome="기각")]}
    normalized, errors = subject.validate_response(value, rows)
    assert errors == []
    assert normalized == value["predictions"]


def test_validate_response_fails_entire_batch_on_id_order_mismatch() -> None:
    rows = [row("a"), row("b")]
    value = {"predictions": [prediction("b"), prediction("a")]}
    normalized, errors = subject.validate_response(value, rows)
    assert normalized == [None, None]
    assert errors == ["id_or_order_mismatch"]


def test_validate_response_nulls_only_semantically_invalid_row() -> None:
    rows = [row("a"), row("b")]
    bad = prediction("b", clause_id="F999")
    normalized, errors = subject.validate_response(
        {"predictions": [prediction("a"), bad]}, rows
    )
    assert normalized[0] is not None
    assert normalized[1] is None
    assert errors == ["b:invalid_atom_value"]


def test_validate_response_rejects_direction_outcome_mismatch() -> None:
    rows = [row("a")]
    bad = prediction("a", outcome="기각")
    bad["evidenceAtoms"][0]["direction"] = "FAVORS_GRANT"
    normalized, errors = subject.validate_response({"predictions": [bad]}, rows)
    assert normalized == [None]
    assert errors == ["a:direction_outcome_mismatch"]
