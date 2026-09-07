from tools.build_mmlu_pro_confirmation import (
    format_prompt,
    largest_remainder_counts,
    select_rows,
)


def test_largest_remainder_is_exact_and_proportional() -> None:
    counts = largest_remainder_counts({"a": 7, "b": 2, "c": 1}, 6)
    assert counts == {"a": 4, "b": 1, "c": 1}
    assert sum(counts.values()) == 6


def test_selection_is_deterministic_and_gold_independent() -> None:
    rows = [
        {
            "question_id": index,
            "question": f"Question {index} with a sufficiently distinctive stem for testing?",
            "options": ["left", "right"],
            "answer": "A" if index % 2 else "B",
            "answer_index": index % 2,
            "category": "a" if index < 6 else "b",
            "src": "unit",
        }
        for index in range(10)
    ]
    selected_a, counts_a, excluded_a = select_rows(rows, 5, [])
    changed_gold = [{**row, "answer": "B", "answer_index": 1} for row in rows]
    selected_b, counts_b, excluded_b = select_rows(changed_gold, 5, [])
    assert [row["question_id"] for row in selected_a] == [row["question_id"] for row in selected_b]
    assert counts_a == counts_b == {"a": 3, "b": 2}
    assert excluded_a == excluded_b == 0


def test_offset_cohorts_are_disjoint_and_exact() -> None:
    rows = [
        {
            "question_id": index,
            "question": f"Distinctive offset question {index} with enough text for stable selection?",
            "options": ["left", "right"],
            "answer": "A",
            "answer_index": 0,
            "category": "a" if index < 12 else "b",
            "src": "unit",
        }
        for index in range(20)
    ]
    first, _, _ = select_rows(rows, 10, [], offset=0)
    second, _, _ = select_rows(rows, 10, [], offset=10)
    first_ids = {row["question_id"] for row in first}
    second_ids = {row["question_id"] for row in second}
    assert len(first_ids) == len(second_ids) == 10
    assert first_ids.isdisjoint(second_ids)


def test_prompt_supports_ten_choices() -> None:
    prompt = format_prompt("Pick one", [f"option {index}" for index in range(10)])
    assert "A. option 0" in prompt
    assert "J. option 9" in prompt
