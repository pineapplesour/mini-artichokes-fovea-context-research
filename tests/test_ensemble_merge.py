import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.run_ensemble_file_agent import (  # noqa: E402
    extract_option_marker,
    merge_drafts,
    normalize_answer_text,
    vote_key,
)


def test_extract_option_marker_variants():
    assert extract_option_marker("③ 단계 2의 결과…") == "3"
    assert extract_option_marker("(2) 위험도 5") == "2"
    assert extract_option_marker("B. riba is forbidden") == "2"
    assert extract_option_marker("3) 옳다") == "3"
    assert extract_option_marker("J. tenth option") == "10"
    assert extract_option_marker("자연은 소유 대상이 아니다") == ""


def test_vote_key_prefers_marker_for_mcq_only():
    assert vote_key("④ 어떤 선지", "mcq") == "marker:4"
    assert vote_key("④ 어떤 선지", "short_answer").startswith("text:")


def test_normalize_answer_text_collapses_format_noise():
    assert normalize_answer_text("  사성제(四聖諦)!  ") == normalize_answer_text("사성제")


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def test_merge_majority_tie_and_empty(tmp_path):
    campaign = tmp_path / "campaign"
    questions = [
        {"id": "q1", "responseFormat": "mcq", "prompt": "?"},
        {"id": "q2", "responseFormat": "short_answer", "prompt": "?"},
        {"id": "q3", "responseFormat": "short_answer", "prompt": "?"},
        {"id": "q4", "responseFormat": "mcq", "prompt": "?"},
    ]
    _write_jsonl(campaign / "solver/input/questions.jsonl", questions)
    drafts = {
        1: {"q1": "③ 옳다", "q2": "사성제", "q3": "무상", "q4": ""},
        2: {"q1": "3) 옳다", "q2": "사성제(四聖諦)", "q3": "연기", "q4": ""},
        3: {"q1": "① 아니다", "q2": "고집멸도", "q3": "열반", "q4": ""},
    }
    for index, answers in drafts.items():
        _write_jsonl(
            campaign / f"drafts/d{index}/solver/output/answers.jsonl",
            [{"id": qid, "finalAnswer": answer} for qid, answer in answers.items()],
        )

    report = merge_drafts(campaign, [1, 2, 3])
    merged = {
        json.loads(line)["id"]: json.loads(line)["finalAnswer"]
        for line in (campaign / "solver/output/answers.jsonl").read_text(encoding="utf-8").splitlines()
    }
    # q1: option-3 marker wins 2-1 across circled/plain digit forms.
    assert merged["q1"] == "③ 옳다"
    # q2: normalized text majority survives parenthetical hanja noise.
    assert merged["q2"] == "사성제"
    # q3: three-way tie falls back to the first draft.
    assert merged["q3"] == "무상"
    # q4: all drafts empty -> empty answer recorded and counted.
    assert merged["q4"] == ""
    assert report["voteStats"]["majority"] == 2
    assert report["voteStats"]["tie_first_effective_draft"] == 1
    assert report["voteStats"]["empty"] == 1
    assert report["rowCount"] == 4
    assert report["disputedCount"] == 2


def test_merge_excludes_boilerplate_drafts(tmp_path):
    campaign = tmp_path / "campaign"
    questions = [
        {"id": f"q{i}", "responseFormat": "constructed_response", "prompt": "?"} for i in range(1, 6)
    ]
    _write_jsonl(campaign / "solver/input/questions.jsonl", questions)
    boiler = "A complete answer should state the relevant belief."
    drafts = {
        1: {f"q{i}": boiler for i in range(1, 6)},  # 5x identical -> flagged
        2: {f"q{i}": boiler for i in range(1, 6)},  # 5x identical -> flagged
        3: {
            "q1": "무역과 대상로가 핵심 답",
            "q2": "라마단 금식의 의미 서술",
            "q3": "자카트 계산 원리 설명",
            "q4": "하지 순례 절차 서술",
            "q5": "수니-시아 분화 배경",
        },
    }
    for index, answers in drafts.items():
        _write_jsonl(
            campaign / f"drafts/d{index}/solver/output/answers.jsonl",
            [{"id": qid, "finalAnswer": answer} for qid, answer in answers.items()],
        )
    report = merge_drafts(campaign, [1, 2, 3])
    merged = {
        json.loads(line)["id"]: json.loads(line)["finalAnswer"]
        for line in (campaign / "solver/output/answers.jsonl").read_text(encoding="utf-8").splitlines()
    }
    # Even a 2-vote boilerplate majority loses to the one substantive draft.
    assert merged["q1"] == "무역과 대상로가 핵심 답"
    assert merged["q5"] == "수니-시아 분화 배경"
    assert report["voteStats"]["boilerplate_excluded_rows"] == 5


CIRCLED_PROMPT = (
    "[제시문] 어떤 지문 내용.\n[질문] 다음 중 옳은 것은?\n"
    "① 자연은 소유 대상이다\n② 자연은 권리 주체이다\n"
    "③ 보전주의는 인간중심적이다\n④ 지구법학은 보수적이다\n⑤ 배리는 법실증주의자다"
)
LETTER_PROMPT = (
    "Which of the following is riba?\n"
    "A. Profit from trade\nB. Interest on a loan\nC. Rent from property\nD. Zakat payment"
)


def test_parse_mcq_options_circled_and_letter():
    from tools.run_ensemble_file_agent import parse_mcq_options

    circled = parse_mcq_options(CIRCLED_PROMPT)
    assert circled["3"].startswith("보전주의")
    assert len(circled) == 5
    letter = parse_mcq_options(LETTER_PROMPT)
    assert letter["2"].startswith("Interest")
    assert len(letter) == 4
    ten_choice = "Pick one\n" + "\n".join(
        f"{letter}. option {index}" for index, letter in enumerate("ABCDEFGHIJ", 1)
    )
    parsed_ten = parse_mcq_options(ten_choice)
    assert parsed_ten["10"] == "option 10"
    assert len(parsed_ten) == 10


def test_match_answer_to_option_content_and_marker():
    from tools.run_ensemble_file_agent import match_answer_to_option, parse_mcq_options

    options = parse_mcq_options(CIRCLED_PROMPT)
    # verbatim option content maps to its index
    assert match_answer_to_option("보전주의는 인간중심적이다", options) == "3"
    # answer with trailing rationale still contains the option content
    assert match_answer_to_option("보전주의는 인간중심적이다 (지문 둘째 단락)", options) == "3"
    # leading marker wins even with reworded content
    assert match_answer_to_option("② 자연도 권리의 주체가 될 수 있다", options) == "2"
    # unrelated text refuses to map
    assert match_answer_to_option("정답 없음", options) == ""


def test_vote_key_unifies_same_option_different_wording():
    from tools.run_ensemble_file_agent import vote_key

    a = vote_key("보전주의는 인간중심적이다", "mcq", CIRCLED_PROMPT)
    b = vote_key("③ 보전주의는 인간중심적이다", "mcq", CIRCLED_PROMPT)
    assert a == b == "option:3"
