import json
import re
from pathlib import Path

from tools.build_unified_benchmark_manifests import (
    build_legal_split,
    build_mcq_split,
    build_mcq_retrieval_target,
    build_short_answer_split,
    parse_answer_labeled_mcq_text,
    parse_answer_labeled_short_answer_text,
    parse_cisi_misanswered_corpus,
    parse_leet_mcq_text,
)
from tools.score_unified_benchmarks import (
    load_graphed_regression_predictions,
    load_json_artifacts,
    score_legal_predictions,
    score_mcq_predictions,
    score_predictions,
    score_short_answer_predictions,
)
from tools.run_frozen_beta6_benchmark import build_tasks


ROOT = Path(__file__).resolve().parents[1]


def test_build_mcq_split_removes_answers_from_public_manifest():
    questions = [
        {
            "id": "tcm81-p1-q001",
            "period": 1,
            "question_number": 1,
            "question_text": "1. 문제?\n1) 보기 A\n2) 보기 B",
            "answer": 2,
            "answer_kind": "numeric",
            "include": True,
            "skip_reason": "",
        },
        {
            "id": "tcm81-p1-q002",
            "period": 1,
            "question_number": 2,
            "question_text": "2. 제외 문제?",
            "answer": 1,
            "include": False,
            "skip_reason": "bad OCR",
        },
    ]

    public, private = build_mcq_split(
        questions,
        benchmark_id="mcq.tcm.kuksiwon81.v1",
        product="tcm",
        language="ko",
        max_cases=50,
    )

    assert public["benchmarkId"] == "mcq.tcm.kuksiwon81.v1"
    assert public["taskType"] == "mcq"
    assert len(public["cases"]) == 1
    case = public["cases"][0]
    assert case["id"] == "tcm81-p1-q001"
    assert case["prompt"] == "1. 문제?\n1) 보기 A\n2) 보기 B"
    assert case["graderRef"] == "tcm81-p1-q001"
    assert "answer" not in json.dumps(public, ensure_ascii=False)
    assert "correctOptionId" not in json.dumps(public, ensure_ascii=False)

    assert private == {
        "schemaVersion": 1,
        "benchmarkId": "mcq.tcm.kuksiwon81.v1",
        "answers": [{"caseId": "tcm81-p1-q001", "correctOptionId": "2"}],
        "retrievalTargetPolicy": {
            "version": "option_text_alias_v0",
            "claimability": "diagnostic_only",
            "blockers": ["text_target_option_only"],
        },
        "retrievalTargets": [
            {
                "caseId": "tcm81-p1-q001",
                "targets": [{"textContains": "보기 B"}],
                "rankRules": {"primaryMustAppearWithin": 50},
            }
        ],
        "scoring": {"invalidPrediction": "wrong"},
        "ablations": [
            {"name": "default_structure_on_heuristics_off", "env": {}},
            {"name": "mcq_heuristics_on", "env": {"RELIGION_MCQ_HEURISTICS_ENABLED": "1"}},
            {"name": "mcq_heuristics_off", "env": {"RELIGION_MCQ_HEURISTICS_ENABLED": "0"}},
            {"name": "mcq_structure_off", "env": {"RELIGION_MCQ_STRUCTURE_ENABLED": "0"}},
        ],
    }


def test_build_mcq_split_adds_private_retrieval_targets_without_public_leak():
    questions = [
        {
            "id": "bible-q1",
            "question_number": 1,
            "question_text": "누구인가?\n\n① 레위\n② 베냐민\n③ 르우벤\n④ 요셉",
            "answer": "4",
            "include": True,
        },
        {
            "id": "cisi-q1",
            "question_number": 1,
            "question_text": "Which is correct?\nA. fund commingling\nB. confidentiality",
            "answer": "A",
            "include": True,
        },
    ]

    public, private = build_mcq_split(
        questions,
        benchmark_id="mcq.retrieval.targets.v1",
        product="islam",
        language="ko",
    )

    assert "retrievalTargets" not in json.dumps(public, ensure_ascii=False)
    target_by_id = {item["caseId"]: item for item in private["retrievalTargets"]}
    assert target_by_id["bible-q1"]["targets"] == [{"textContains": "요셉"}]
    assert {"textContains": "fund commingling"} in target_by_id["cisi-q1"]["targets"]
    assert target_by_id["bible-q1"]["rankRules"] == {"primaryMustAppearWithin": 50}
    assert target_by_id["cisi-q1"]["rankRules"] == {"primaryMustAppearWithin": 50}
    assert private["retrievalTargetPolicy"] == {
        "version": "option_text_alias_v0",
        "claimability": "diagnostic_only",
        "blockers": ["text_target_option_only"],
    }


def test_build_mcq_split_adds_product_aliases_to_private_retrieval_targets():
    questions = [
        {
            "id": "islam-cisi-q006",
            "question_number": 6,
            "question_text": "006. 제한된 투자 계좌 보유자에게 제공되는 것은?\n\nA. 자금 혼합\nB. 고객의 기밀 유지",
            "answer": "A",
            "include": True,
        }
    ]

    _public, private = build_mcq_split(
        questions,
        benchmark_id="mcq.islam.alias.targets.v1",
        product="islam",
        language="ko",
    )

    targets = private["retrievalTargets"][0]["targets"]
    assert {"textContains": "자금 혼합"} in targets
    assert {"textContains": "fund commingling"} in targets
    assert {"textContains": "commingling of funds"} in targets


def test_build_mcq_retrieval_target_handles_tcm_ocr_option_markers():
    prompt = """치방은?
D 생맥산
(2 정천탕
@ 마행감석탕
© 삼자양친탕
© 소자강기탕"""

    target = build_mcq_retrieval_target(case_id="tcm-q044", prompt=prompt, answer_id="5")

    assert target["targets"] == [{"textContains": "소자강기탕"}]

    malformed_prompt = """치방은?
@ WSa(S AS)
YS At AS AY)
® SHS (Bey)
© 황토탕(호그)
(3/"""

    fallback_target = build_mcq_retrieval_target(case_id="tcm-q019", prompt=malformed_prompt, answer_id="5")

    assert fallback_target["targets"] == [{"textContains": "황토탕(호그)"}]


def test_build_mcq_retrieval_target_handles_bare_option_marker_before_wrapped_text():
    prompt = """무엇이 옳은가?
① 첫째
② 둘째
③ 셋째
④
넷째 선택지의 줄바꿈된 본문
⑤ 다섯째"""

    target = build_mcq_retrieval_target(case_id="leet-q018", prompt=prompt, answer_id="4")

    assert target["targets"] == [{"textContains": "넷째 선택지의 줄바꿈된 본문"}]


def test_checked_in_mcq_private_manifests_have_retrieval_targets_for_each_answer():
    for private_path in sorted((ROOT / "benchmarks" / "unified").glob("mcq_*.private.json")):
        private = json.loads(private_path.read_text(encoding="utf-8"))
        answer_case_ids = {str(item.get("caseId") or "") for item in private.get("answers", [])}
        retrieval_targets = private.get("retrievalTargets", [])
        target_case_ids = {str(item.get("caseId") or "") for item in retrieval_targets if isinstance(item, dict)}
        assert answer_case_ids == target_case_ids, private_path.name
        for item in retrieval_targets:
            targets = item.get("targets") if isinstance(item, dict) else None
            assert isinstance(targets, list) and targets, private_path.name
            assert any(str(target.get("textContains") or "").strip() for target in targets if isinstance(target, dict)), (
                private_path.name,
                item.get("caseId") if isinstance(item, dict) else item,
            )
            assert item.get("rankRules") == {"primaryMustAppearWithin": 50}
        assert private.get("retrievalTargetPolicy") == {
            "version": "option_text_alias_v0",
            "claimability": "diagnostic_only",
            "blockers": ["text_target_option_only"],
        }, private_path.name


def test_checked_in_canonical_exam_inventory_has_1235_unique_cases():
    expected_counts = {
        "mcq_lawkey_leet2026_70.public.json": 70,
        "mcq_tcm_kuksiwon81_unique92.public.json": 92,
        "mcq_christian_bible100.public.json": 100,
        "mcq_christian_provao2012.public.json": 92,
        "mcq_islam_cisi100.public.json": 100,
        "mcq_islam_aqa4.public.json": 4,
        "mcq_psych_mit_sangmyung.public.json": 487,
        "short_answer_buddhist_sangha3_290.public.json": 290,
    }

    total = 0
    for filename, expected in expected_counts.items():
        manifest = json.loads((ROOT / "benchmarks" / "unified" / filename).read_text(encoding="utf-8"))
        case_ids = [str(case.get("id") or "") for case in manifest.get("cases", [])]
        assert len(case_ids) == expected, filename
        assert len(set(case_ids)) == expected, filename
        total += expected

    assert total == 1235


def test_checked_in_lawkey_leet_manifest_is_runner_ready_and_answer_free():
    public_path = ROOT / "benchmarks" / "unified" / "mcq_lawkey_leet2026_70.public.json"
    manifest = json.loads(public_path.read_text(encoding="utf-8"))

    tasks = build_tasks(manifest, max_cases=0, case_ids=None)

    assert len(tasks) == 70
    assert all(task["optionIds"] == ["1", "2", "3", "4", "5"] for task in tasks)
    assert all("AI :" not in task["query"] and "정답 :" not in task["query"] for task in tasks)


def test_checked_in_islam_wrong26_is_exact_subset_of_official_cisi100():
    cisi = json.loads(
        (ROOT / "benchmarks" / "unified" / "mcq_islam_cisi100.public.json").read_text(encoding="utf-8")
    )
    wrong = json.loads(
        (ROOT / "benchmarks" / "unified" / "mcq_islam_cisi_wrong26.public.json").read_text(encoding="utf-8")
    )
    cisi_prompts = {str(case["id"]): str(case["prompt"]) for case in cisi["cases"]}
    wrong_prompts = {str(case["id"]): str(case["prompt"]) for case in wrong["cases"]}

    assert len(wrong_prompts) == 26
    assert set(wrong_prompts) < set(cisi_prompts)
    assert all(cisi_prompts[case_id] == prompt for case_id, prompt in wrong_prompts.items())


def test_checked_in_tcm_suites_preserve_overlap_and_unique_union():
    def ids(filename: str) -> set[str]:
        manifest = json.loads((ROOT / "benchmarks" / "unified" / filename).read_text(encoding="utf-8"))
        return {str(case.get("id") or "") for case in manifest.get("cases", [])}

    p1 = ids("mcq_tcm_kuksiwon81_p1_50.public.json")
    wikia = ids("mcq_tcm_kuksiwon81_wikia64.public.json")
    unique = ids("mcq_tcm_kuksiwon81_unique92.public.json")

    assert len(p1) == 50
    assert len(wikia) == 64
    assert len(p1 & wikia) == 22
    assert unique == p1 | wikia
    assert len(unique) == 92


def test_checked_in_tcm_overlap_reuses_the_same_clean_public_prompts():
    def prompts(filename: str) -> dict[str, str]:
        manifest = json.loads((ROOT / "benchmarks" / "unified" / filename).read_text(encoding="utf-8"))
        return {
            str(case.get("id") or ""): str(case.get("prompt") or "")
            for case in manifest.get("cases", [])
        }

    p1 = prompts("mcq_tcm_kuksiwon81_p1_50.public.json")
    wikia = prompts("mcq_tcm_kuksiwon81_wikia64.public.json")
    overlap = set(p1) & set(wikia)

    assert len(overlap) == 22
    assert {case_id: (p1[case_id], wikia[case_id]) for case_id in overlap if p1[case_id] != wikia[case_id]} == {}


def test_checked_in_public_exam_prompts_never_contain_answer_labels():
    answer_label = re.compile(r"(?mi)^\s*(?:AI|AI\s*답변|정답|답)\s*[:：]")
    for public_path in sorted((ROOT / "benchmarks" / "unified").glob("*.public.json")):
        manifest = json.loads(public_path.read_text(encoding="utf-8"))
        if manifest.get("taskType") not in {"mcq", "short_answer"}:
            continue
        leaked = [
            str(case.get("id") or "")
            for case in manifest.get("cases", [])
            if answer_label.search(str(case.get("prompt") or ""))
        ]
        assert leaked == [], public_path.name


def test_parse_cisi_misanswered_corpus_splits_public_prompt_from_private_answer():
    raw = """
===== SOURCE FILE: CISI_이슬람금융_공식샘플_100문항 틀린 문제.txt =====
[오답 판정] 006번 | AI: B | 정답: A
006. 제한된 투자 계좌 보유자에게 제공되는 것은?

A. 자금 혼합
B. 고객의 기밀 유지
C. 상업적 위험
D. 기업 지배구조

AI : B. 고객의 기밀 유지

정답 : A. 자금 혼합
------------------------------------------------------------------------
"""

    questions = parse_cisi_misanswered_corpus(raw)
    public, private = build_mcq_split(
        questions,
        benchmark_id="mcq.islam.cisi.wrong26.v1",
        product="islam",
        language="ko",
    )

    assert questions == [
        {
            "id": "islam-cisi-q006",
            "question_number": 6,
            "question_text": (
                "006. 제한된 투자 계좌 보유자에게 제공되는 것은?\n\n"
                "A. 자금 혼합\n"
                "B. 고객의 기밀 유지\n"
                "C. 상업적 위험\n"
                "D. 기업 지배구조"
            ),
            "answer": "A",
            "include": True,
            "metadata": {"sourceQuestionNumber": "006"},
        }
    ]
    public_text = json.dumps(public, ensure_ascii=False)
    assert "정답" not in public_text
    assert "AI :" not in public_text
    assert private["answers"] == [{"caseId": "islam-cisi-q006", "correctOptionId": "A"}]


def test_parse_answer_labeled_mcq_text_splits_prompt_from_ai_and_answer_labels():
    raw = """
1. 창세기 1장의 천지창조 일정 가운데 광명체들은 몇째 날 창조되었는가?

① 둘째 날
② 셋째 날
③ 넷째 날
④ 다섯째 날

AI : ③
정답: ③

2. Sobre o Espírito Santo é correto afirmar que:

① É a segunda pessoa da Trindade.
② É um poder que emana do Pai e do Filho.
③ Ele procede apenas do Pai.
④ Sua função é regenerar o ser humano.
⑤ Os principais símbolos são: fogo, água, pomba e nuvem.

AI : ②
정답: ④
"""

    questions = parse_answer_labeled_mcq_text(raw, id_prefix="christian-test")
    public, private = build_mcq_split(
        questions,
        benchmark_id="mcq.christian.test.v1",
        product="catholic",
        language="ko",
    )

    assert [item["id"] for item in questions] == ["christian-test-q001", "christian-test-q002"]
    assert [item["answer"] for item in questions] == ["3", "4"]
    public_text = json.dumps(public, ensure_ascii=False)
    assert "AI :" not in public_text
    assert "정답" not in public_text
    assert "셋째 날" in public_text
    assert private["answers"] == [
        {"caseId": "christian-test-q001", "correctOptionId": "3"},
        {"caseId": "christian-test-q002", "correctOptionId": "4"},
    ]


def test_parse_answer_labeled_mcq_text_accepts_generic_answer_label_and_period():
    raw = """
01. 다음 중 이슬람에서 거룩한 책에 해당하지 않는 것은?

A. 지브릴
B. 쿠란
C. 이브라힘의 두루마리
D. 토라

AI : A. 지브릴
답: A. 지브릴
"""

    questions = parse_answer_labeled_mcq_text(
        raw,
        id_prefix="islam-aqa",
        source_name="AQA.txt",
        period=2022,
    )

    assert questions == [
        {
            "id": "islam-aqa-q001",
            "question_number": 1,
            "question_text": (
                "01. 다음 중 이슬람에서 거룩한 책에 해당하지 않는 것은?\n\n"
                "A. 지브릴\n"
                "B. 쿠란\n"
                "C. 이브라힘의 두루마리\n"
                "D. 토라"
            ),
            "answer": "A",
            "include": True,
            "period": 2022,
            "metadata": {"questionNumber": 1, "sourceFile": "AQA.txt", "period": 2022},
        }
    ]


def test_parse_leet_mcq_text_reuses_shared_passage_and_keeps_labels_private():
    raw = """
2026년도 법학적성시험 언어이해

[1~2번 제시문]
법적 인격만을 권리와 의무의 주체로 보는 견해와 자연의 권리를 인정하는 견해가 대립한다.

1.문제:
윗글의 내용과 일치하는 것은?

① 첫째 보기
② 둘째 보기
③ 셋째 보기
④ 넷째 보기
⑤ 다섯째 보기

AI : ②
정답 : ④

2.문제:
윗글에서 추론한 것으로 적절하지 않은 것은?

① 하나
② 둘
③ 셋
④ 넷
⑤ 다섯

AI : ⑤
정답 : ③
"""

    questions = parse_leet_mcq_text(
        raw,
        id_prefix="lawkey-leet2026-language",
        source_name="2026년도 법학적성시험 언어이해.txt",
        section="language_comprehension",
    )
    public, private = build_mcq_split(
        questions,
        benchmark_id="mcq.lawkey.leet2026.v1",
        product="lawkey",
        language="ko",
    )

    assert [item["id"] for item in questions] == [
        "lawkey-leet2026-language-q001",
        "lawkey-leet2026-language-q002",
    ]
    assert [item["answer"] for item in questions] == ["4", "3"]
    assert [item["historical_ai_answer"] for item in questions] == ["2", "5"]
    assert all("법적 인격만을" in item["question_text"] for item in questions)
    assert "1.문제:" not in questions[1]["question_text"]
    assert "2.문제:" in questions[1]["question_text"]
    public_text = json.dumps(public, ensure_ascii=False)
    assert "AI :" not in public_text
    assert "정답 :" not in public_text
    assert private["answers"] == [
        {"caseId": "lawkey-leet2026-language-q001", "correctOptionId": "4"},
        {"caseId": "lawkey-leet2026-language-q002", "correctOptionId": "3"},
    ]


def test_short_answer_parser_and_split_keep_exact_gold_private():
    raw = """
불교 3급 객관식 — AI 답변 및 정답 정리본

1.문제: 대승불교에서 깨달음을 구하면서 중생을 제도하는 이상적 인간상은?

AI 답변: 보살
정답: 보살(菩薩)

2.문제: 사성제 중 괴로움의 원인을 밝히는 진리는?

AI 답변: 집성제
정답: 고집성제=집성제
"""

    questions = parse_answer_labeled_short_answer_text(
        raw,
        id_prefix="buddhist-sangha3",
        source_name="buddhist.txt",
    )
    public, private = build_short_answer_split(
        questions,
        benchmark_id="short_answer.buddhist.sangha3.v1",
        product="buddhist",
        language="ko",
    )

    assert [item["id"] for item in questions] == ["buddhist-sangha3-q001", "buddhist-sangha3-q002"]
    assert [item["answer"] for item in questions] == ["보살(菩薩)", "고집성제=집성제"]
    public_text = json.dumps(public, ensure_ascii=False)
    assert public["taskType"] == "short_answer"
    assert "AI 답변" not in public_text
    assert "보살(菩薩)" not in public_text
    assert private == {
        "schemaVersion": 1,
        "benchmarkId": "short_answer.buddhist.sangha3.v1",
        "answers": [
            {"caseId": "buddhist-sangha3-q001", "correctAnswer": "보살(菩薩)"},
            {"caseId": "buddhist-sangha3-q002", "correctAnswer": "고집성제=집성제"},
        ],
        "scoring": {
            "comparison": "exact_unicode_string",
            "invalidPrediction": "wrong",
            "partialCredit": False,
        },
    }


def test_build_legal_split_keeps_targets_private():
    raw = {
        "benchmarkVersion": "lawkey-hard-retrieval-v1",
        "cases": [
            {
                "id": "yangyang-complainant-age",
                "description": "answer span is private",
                "queries": ["김진하 양양 군수 사건 민원인 나이"],
                "primaryTarget": {
                    "fileName": "춘천지방법원속초지원-2025고합5.pdf",
                    "court": "춘천지방법원속초지원",
                    "caseNumber": "2025고합5",
                    "requiredAnswerText": "D(여, 64세)",
                },
                "relatedTargets": [{"caseNumber": "2025노158"}],
                "rankRules": {"candidateLimit": 50, "primaryMustAppearWithin": 5},
                "forbiddenSearchMetadataTerms": ["김진하", "양양"],
            }
        ],
    }

    public, private = build_legal_split(raw, benchmark_id="legal.yangyang.v1", product="lawkey")

    assert public["benchmarkId"] == "legal.yangyang.v1"
    assert public["cases"] == [
        {
            "id": "yangyang-complainant-age",
            "language": "ko",
            "variants": [{"id": "v1", "query": "김진하 양양 군수 사건 민원인 나이"}],
            "runtime": {"candidateLimit": 50},
            "graderRef": "yangyang-complainant-age",
        }
    ]
    public_text = json.dumps(public, ensure_ascii=False)
    assert "2025고합5" not in public_text
    assert "D(여, 64세)" not in public_text
    assert "춘천지방법원속초지원-2025고합5.pdf" not in public_text

    assert private["graders"][0]["graderId"] == "yangyang-complainant-age"
    assert private["graders"][0]["primaryTargets"][0]["caseNumber"] == "2025고합5"
    assert private["graders"][0]["leakageGuards"]["forbiddenSearchMetadataTerms"] == ["김진하", "양양"]
    assert private["graders"][0]["leakageGuards"]["forbiddenSearchMetadataTermsApplyTo"] == ["retrievedMetadata"]


def test_build_legal_split_preserves_plural_targets_and_answer_rules_private():
    raw = {
        "cases": [
            {
                "id": "kakao-sim",
                "queries": ["경찰 유심 카톡"],
                "primaryTargets": [{"caseNumber": "2024구합65355"}, {"caseNumber": "2021노1520"}],
                "rankRules": {"candidateLimit": 50, "atLeastTargetsWithinTopK": 2},
                "answerRules": {"mustUseAtLeastTargetCount": 2, "forbidFakeCitations": True},
            }
        ]
    }

    public, private = build_legal_split(raw, benchmark_id="legal.kakao.v1", product="lawkey")

    assert "2024구합65355" not in json.dumps(public, ensure_ascii=False)
    grader = private["graders"][0]
    assert [target["caseNumber"] for target in grader["primaryTargets"]] == ["2024구합65355", "2021노1520"]
    assert grader["answerRules"]["mustUseAtLeastTargetCount"] == 2
    assert "answerRules" in grader["leakageGuards"]["forbiddenRuntimeFields"]


def test_checked_in_legal_public_manifests_do_not_expose_private_targets():
    checks = {
        "legal_kakao_sim_access.public.json": [
            "2024구합65355",
            "2020고합886",
            "2021노1520",
            "2025-01-21",
            "mustDiscuss",
        ],
        "legal_military_key_management.public.json": [
            "2023구합75301",
            "2025-01-16",
            "mustDiscussAny",
            "forbiddenConcepts",
        ],
        "legal_yangyang_complainant_age.public.json": [
            "2025고합5",
            "D(여, 64세)",
            "춘천지방법원속초지원-2025고합5.pdf",
        ],
    }

    for filename, forbidden in checks.items():
        text = (ROOT / "benchmarks" / "unified" / filename).read_text(encoding="utf-8")
        assert not [needle for needle in forbidden if needle in text], filename


def test_ambiguous_military_key_v1_is_not_officially_runnable_without_clarification():
    manifest = json.loads(
        (ROOT / "benchmarks/unified/legal_military_key_management.public.json").read_text(encoding="utf-8")
    )
    variants = {row["id"]: row for row in manifest["cases"][0]["variants"]}

    assert variants["v1"]["evaluationStatus"] == "needs_clarification_rewrite"
    assert variants["v1"]["riskReasons"] == ["lexically_ambiguous_physical_key_vs_height"]
    assert all("evaluationStatus" not in variants[key] for key in ("v2", "v3", "v4"))


def test_checked_in_public_private_manifests_do_not_expose_private_target_values():
    for public_path in sorted((ROOT / "benchmarks" / "unified").glob("legal_*.public.json")):
        private_path = public_path.with_name(public_path.name.replace(".public.json", ".private.json"))
        public_text = json.dumps(json.loads(public_path.read_text(encoding="utf-8")), ensure_ascii=False)
        private = json.loads(private_path.read_text(encoding="utf-8"))
        leaked: list[str] = []
        for grader in private.get("graders", []):
            for target_group in ("primaryTargets", "diagnosticTargets"):
                for target in grader.get(target_group, []):
                    for key in ("caseNumber", "decisionDate", "fileName", "requiredAnswerText"):
                        value = target.get(key)
                        if isinstance(value, str) and len(value) >= 3 and value in public_text:
                            leaked.append(value)
        assert leaked == [], public_path.name


def test_checked_in_forbidden_search_metadata_terms_have_retrieval_only_scope_when_public_query_uses_them():
    for public_path in sorted((ROOT / "benchmarks" / "unified").glob("legal_*.public.json")):
        private_path = public_path.with_name(public_path.name.replace(".public.json", ".private.json"))
        public_text = json.dumps(json.loads(public_path.read_text(encoding="utf-8")), ensure_ascii=False)
        private = json.loads(private_path.read_text(encoding="utf-8"))
        for grader in private.get("graders", []):
            guards = grader.get("leakageGuards", {})
            overlap = [
                term
                for term in guards.get("forbiddenSearchMetadataTerms", [])
                if isinstance(term, str) and term and term in public_text
            ]
            if overlap:
                assert guards.get("forbiddenSearchMetadataTermsApplyTo") == ["retrievedMetadata"], (
                    private_path.name,
                    overlap,
                )


def test_score_mcq_predictions_uses_private_answers_only(tmp_path):
    private = {
        "benchmarkId": "mcq.test.v1",
        "answers": [
            {"caseId": "q1", "correctOptionId": "2"},
            {"caseId": "q2", "correctOptionId": "4"},
        ],
    }
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    (results_dir / "q1.json").write_text(json.dumps({"id": "q1", "prediction": 2}), encoding="utf-8")
    (results_dir / "q2.json").write_text(json.dumps({"id": "q2", "prediction": 3}), encoding="utf-8")

    predictions = load_graphed_regression_predictions(results_dir)
    summary = score_mcq_predictions(private, predictions)

    assert predictions == [{"caseId": "q1", "prediction": "2"}, {"caseId": "q2", "prediction": "3"}]
    assert summary["total"] == 2
    assert summary["correct"] == 1
    assert summary["accuracy"] == 0.5
    assert summary["wrongCaseIds"] == ["q2"]


def test_score_short_answer_predictions_requires_exact_unicode_string():
    private = {
        "benchmarkId": "short_answer.buddhist.test.v1",
        "answers": [
            {"caseId": "q1", "correctAnswer": "보살(菩薩)"},
            {"caseId": "q2", "correctAnswer": "고집성제=집성제"},
            {"caseId": "q3", "correctAnswer": "죽림정사"},
        ],
        "scoring": {"comparison": "exact_unicode_string"},
    }
    predictions = [
        {"caseId": "q1", "prediction": "보살(菩薩)"},
        {"caseId": "q2", "prediction": "집성제"},
        {"caseId": "q3", "prediction": ""},
    ]

    summary = score_short_answer_predictions(private, predictions)

    assert summary["taskType"] == "short_answer"
    assert summary["total"] == 3
    assert summary["predicted"] == 2
    assert summary["correct"] == 1
    assert summary["accuracy"] == 1 / 3
    assert summary["invalidCaseIds"] == ["q3"]
    assert summary["wrongCaseIds"] == ["q2", "q3"]
    assert score_predictions(private, predictions) == summary


def test_score_mcq_predictions_reports_retrieval_separately_from_answer_accuracy():
    private = {
        "benchmarkId": "mcq.retrieval.split.v1",
        "answers": [
            {"caseId": "q1", "correctOptionId": "A"},
            {"caseId": "q2", "correctOptionId": "B"},
        ],
        "retrievalTargets": [
            {
                "caseId": "q1",
                "targets": [{"sourceId": "doc-target"}],
                "rankRules": {"primaryMustAppearWithin": 3},
            },
            {
                "caseId": "q2",
                "targets": [{"sourceId": "doc-missing"}],
                "rankRules": {"primaryMustAppearWithin": 3},
            },
        ],
    }
    artifacts = [
        {
            "caseId": "q1",
            "prediction": "B",
            "selectedEvidence": [{"rank": 1, "sourceId": "doc-target"}],
        },
        {
            "caseId": "q2",
            "prediction": "B",
            "selectedEvidence": [{"rank": 1, "sourceId": "doc-other"}],
        },
    ]

    summary = score_mcq_predictions(private, artifacts)

    assert summary["correct"] == 1
    assert summary["accuracy"] == 0.5
    assert summary["retrieval"] == {
        "total": 2,
        "targeted": 2,
        "passed": 1,
        "accuracy": 0.5,
        "failedCaseIds": ["q2"],
        "missingTargetCaseIds": [],
        "targetPolicy": {"claimable": True, "blockers": [], "version": "inferred_v1"},
    }
    by_id = {case["caseId"]: case for case in summary["cases"]}
    assert by_id["q1"]["answerPassed"] is False
    assert by_id["q1"]["retrievalPassed"] is True
    assert by_id["q1"]["retrievalFailures"] == []
    assert by_id["q2"]["answerPassed"] is True
    assert by_id["q2"]["retrievalPassed"] is False
    assert by_id["q2"]["retrievalFailures"] == ["rank:primary_not_within:3"]


def test_score_mcq_predictions_filters_top_level_retrieval_targets_by_case_ids():
    private = {
        "benchmarkId": "mcq.retrieval.subset.v1",
        "answers": [
            {"caseId": "q1", "correctOptionId": "A"},
            {"caseId": "q2", "correctOptionId": "B"},
            {"caseId": "q3", "correctOptionId": "C"},
        ],
        "retrievalTargets": [
            {
                "caseId": "q1",
                "targets": [{"sourceId": "doc-q1"}],
                "rankRules": {"primaryMustAppearWithin": 3},
            },
            {
                "caseId": "q2",
                "targets": [{"sourceId": "doc-q2"}],
                "rankRules": {"primaryMustAppearWithin": 3},
            },
            {
                "caseId": "q3",
                "targets": [{"sourceId": "doc-q3"}],
                "rankRules": {"primaryMustAppearWithin": 3},
            },
        ],
    }
    artifacts = [
        {
            "caseId": "q1",
            "prediction": "A",
            "selectedEvidence": [{"rank": 1, "sourceId": "doc-q1"}],
        }
    ]

    summary = score_mcq_predictions(private, artifacts, case_ids=["q1"])

    assert summary["total"] == 1
    assert summary["retrieval"] == {
        "total": 1,
        "targeted": 1,
        "passed": 1,
        "accuracy": 1.0,
        "failedCaseIds": [],
        "missingTargetCaseIds": [],
        "targetPolicy": {"claimable": True, "blockers": [], "version": "inferred_v1"},
    }
    assert [case["caseId"] for case in summary["cases"]] == ["q1"]


def test_score_mcq_predictions_marks_text_only_retrieval_targets_diagnostic_only():
    private = {
        "benchmarkId": "mcq.retrieval.text_only.v1",
        "answers": [{"caseId": "q1", "correctOptionId": "A"}],
        "retrievalTargets": [
            {
                "caseId": "q1",
                "targets": [{"textContains": "갑"}],
                "rankRules": {"primaryMustAppearWithin": 3},
            }
        ],
    }
    artifacts = [
        {
            "caseId": "q1",
            "prediction": "A",
            "selectedEvidence": [{"rank": 1, "text": "갑 근거"}],
        }
    ]

    summary = score_mcq_predictions(private, artifacts)

    assert summary["retrieval"]["passed"] == 1
    assert summary["retrieval"]["targetPolicy"] == {
        "claimable": False,
        "blockers": ["text_target_option_only"],
        "version": "inferred_v1",
    }


def test_score_mcq_predictions_requires_source_id_and_anchor_when_both_are_present():
    private = {
        "benchmarkId": "mcq.retrieval.source_anchor.v1",
        "answers": [
            {"caseId": "missing-anchor", "correctOptionId": "A"},
            {"caseId": "has-anchor", "correctOptionId": "A"},
        ],
        "retrievalTargets": [
            {
                "caseId": "missing-anchor",
                "targets": [{"sourceId": "doc-target", "textContains": "정답 근거"}],
                "rankRules": {"primaryMustAppearWithin": 3},
            },
            {
                "caseId": "has-anchor",
                "targets": [{"sourceId": "doc-target", "textContains": "정답 근거"}],
                "rankRules": {"primaryMustAppearWithin": 3},
            },
        ],
    }
    artifacts = [
        {
            "caseId": "missing-anchor",
            "prediction": "A",
            "selectedEvidence": [{"rank": 1, "sourceId": "doc-target", "text": "관련은 있지만 다른 문장"}],
        },
        {
            "caseId": "has-anchor",
            "prediction": "A",
            "selectedEvidence": [{"rank": 1, "sourceId": "doc-target", "text": "정답 근거가 있는 문장"}],
        },
    ]

    summary = score_mcq_predictions(private, artifacts)

    assert summary["retrieval"]["passed"] == 1
    by_id = {case["caseId"]: case for case in summary["cases"]}
    assert by_id["missing-anchor"]["retrievalPassed"] is False
    assert by_id["missing-anchor"]["retrievalFailures"] == ["rank:primary_not_within:3"]
    assert by_id["has-anchor"]["retrievalPassed"] is True
    assert summary["retrieval"]["targetPolicy"] == {
        "claimable": True,
        "blockers": [],
        "version": "inferred_v1",
    }


def test_score_mcq_predictions_supports_source_id_with_all_and_any_anchors():
    private = {
        "benchmarkId": "mcq.retrieval.source_anchor_groups.v1",
        "answers": [
            {"caseId": "all-and-any-pass", "correctOptionId": "A"},
            {"caseId": "missing-required-anchor", "correctOptionId": "A"},
            {"caseId": "missing-any-anchor", "correctOptionId": "A"},
        ],
        "retrievalTargets": [
            {
                "caseId": "all-and-any-pass",
                "targets": [
                    {
                        "sourceId": "doc-target",
                        "textContainsAll": ["문제 맥락", "정답 근거"],
                        "textContainsAny": ["동의어 A", "동의어 B"],
                    }
                ],
                "rankRules": {"primaryMustAppearWithin": 3},
            },
            {
                "caseId": "missing-required-anchor",
                "targets": [
                    {
                        "sourceId": "doc-target",
                        "textContainsAll": ["문제 맥락", "정답 근거"],
                        "textContainsAny": ["동의어 A", "동의어 B"],
                    }
                ],
                "rankRules": {"primaryMustAppearWithin": 3},
            },
            {
                "caseId": "missing-any-anchor",
                "targets": [
                    {
                        "sourceId": "doc-target",
                        "textContainsAll": ["문제 맥락", "정답 근거"],
                        "textContainsAny": ["동의어 A", "동의어 B"],
                    }
                ],
                "rankRules": {"primaryMustAppearWithin": 3},
            },
        ],
    }
    artifacts = [
        {
            "caseId": "all-and-any-pass",
            "prediction": "A",
            "selectedEvidence": [{"rank": 1, "sourceId": "doc-target", "text": "문제 맥락과 정답 근거 및 동의어 B"}],
        },
        {
            "caseId": "missing-required-anchor",
            "prediction": "A",
            "selectedEvidence": [{"rank": 1, "sourceId": "doc-target", "text": "문제 맥락과 동의어 A"}],
        },
        {
            "caseId": "missing-any-anchor",
            "prediction": "A",
            "selectedEvidence": [{"rank": 1, "sourceId": "doc-target", "text": "문제 맥락과 정답 근거"}],
        },
    ]

    summary = score_mcq_predictions(private, artifacts)

    assert summary["retrieval"]["passed"] == 1
    by_id = {case["caseId"]: case for case in summary["cases"]}
    assert by_id["all-and-any-pass"]["retrievalPassed"] is True
    assert by_id["missing-required-anchor"]["retrievalPassed"] is False
    assert by_id["missing-any-anchor"]["retrievalPassed"] is False


def test_score_predictions_routes_legal_manifests_to_legal_scorer():
    private = {
        "benchmarkId": "legal.test.v1",
        "graders": [
            {
                "graderId": "case-a",
                "primaryTargets": [{"caseNumber": "2025구합1"}],
                "rankRules": {"primaryMustAppearWithin": 3},
            }
        ],
    }
    artifacts = [
        {
            "caseId": "case-a",
            "answer": "2025구합1 판례를 근거로 답변합니다.",
            "retrievedCases": [{"caseNumber": "2025구합1"}],
        }
    ]

    summary = score_predictions(private, artifacts)

    assert summary["taskType"] == "legal_retrieval_answer"
    assert summary["passed"] == 1


def test_score_legal_predictions_reports_retrieval_separately_from_answer_rules():
    private = {
        "benchmarkId": "legal.retrieval.split.v1",
        "graders": [
            {
                "graderId": "case-a",
                "primaryTargets": [{"caseNumber": "2024구합65355"}],
                "rankRules": {"primaryMustAppearWithin": 3},
                "answerRules": {"mustDiscuss": ["유심 분리"]},
            },
            {
                "graderId": "case-b",
                "primaryTargets": [{"caseNumber": "2025고합5"}],
                "rankRules": {"primaryMustAppearWithin": 3},
            },
        ],
    }
    artifacts = [
        {
            "caseId": "case-a",
            "answer": "관련 판례는 언급하지만 필수 논점은 빠졌다.",
            "selectedEvidence": [{"rank": 1, "caseNumber": "2024구합65355"}],
        },
        {
            "caseId": "case-b",
            "answer": "2025고합5 판례를 근거로 답변합니다.",
            "selectedEvidence": [{"rank": 1, "caseNumber": "2024구합99999"}],
        },
    ]

    summary = score_legal_predictions(private, artifacts)

    assert summary["passed"] == 0
    assert summary["retrieval"] == {
        "total": 2,
        "passed": 1,
        "accuracy": 0.5,
        "failedCaseIds": ["case-b"],
    }
    assert summary["cases"][0]["passed"] is False
    assert summary["cases"][0]["retrievalPassed"] is True
    assert summary["cases"][0]["retrievalFailures"] == []
    assert summary["cases"][0]["answerFailures"] == ["answer:missing_must_discuss:유심 분리"]
    assert summary["cases"][1]["passed"] is False
    assert summary["cases"][1]["retrievalPassed"] is False
    assert summary["cases"][1]["retrievalFailures"] == ["rank:primary_not_within:3"]


def test_score_legal_predictions_enforces_targets_answer_rules_and_leakage_guards():
    private = {
        "benchmarkId": "legal.test.v1",
        "graders": [
            {
                "graderId": "kakao",
                "primaryTargets": [{"caseNumber": "2024구합65355"}, {"caseNumber": "2021노1520"}],
                "rankRules": {"atLeastTargetsWithinTopK": 2, "targetTopK": 5},
                "answerRules": {
                    "mustDiscuss": ["유심 분리", "메신저 계정 접근"],
                    "mustUseAtLeastTargetCount": 2,
                    "forbidFakeCitations": True,
                },
                "leakageGuards": {
                    "forbiddenSearchMetadataTerms": ["김진하"],
                    "forbiddenSearchMetadataTermsApplyTo": ["retrievedMetadata"],
                    "forbiddenRuntimeFields": ["primaryTargets", "answerRules"],
                },
            },
            {
                "graderId": "yangyang",
                "primaryTargets": [{"caseNumber": "2025고합5", "requiredAnswerText": "D(여, 64세)"}],
                "rankRules": {"primaryMustAppearWithin": 5, "requiredAnswerMustAppearInPrimary": True},
                "leakageGuards": {
                    "forbiddenSearchMetadataTerms": ["김진하"],
                    "forbiddenSearchMetadataTermsApplyTo": ["retrievedMetadata"],
                    "forbiddenRuntimeFields": ["primaryTargets", "requiredAnswerText"],
                },
            },
        ],
    }
    artifacts = [
        {
            "caseId": "kakao",
            "query": "김진하라는 단어가 query에 있어도 retrieved metadata leak는 아님",
            "answer": "유심 분리 뒤 메신저 계정 접근을 한 사안이다. 2024구합65355 및 2021노1520을 근거로 본다.",
            "retrievedCases": [{"caseNumber": "2024구합65355"}, {"caseNumber": "2021노1520"}],
            "searchResults": [
                {"metadata": {"caseNumber": "2024구합65355", "title": "정상 판례"}},
                {"metadata": {"caseNumber": "2021노1520", "title": "정상 판례"}},
            ],
        },
        {
            "caseId": "yangyang",
            "answer": "민원인은 D(여, 64세)로 확인된다.",
            "retrievedCases": [{"caseNumber": "2025고합5"}],
            "searchResults": [{"metadata": {"caseNumber": "2025고합5", "title": "김진하 메타데이터 누출"}}],
        },
    ]

    summary = score_legal_predictions(private, artifacts)

    assert summary["total"] == 2
    assert summary["passed"] == 1
    by_id = {case["caseId"]: case for case in summary["cases"]}
    assert by_id["kakao"]["passed"] is True
    assert by_id["yangyang"]["passed"] is False
    assert "leakage:forbidden_search_metadata_term:김진하" in by_id["yangyang"]["failures"]


def test_score_legal_predictions_requires_answer_span_in_primary_record_when_configured():
    private = {
        "benchmarkId": "legal.yangyang.test",
        "graders": [
            {
                "graderId": "yangyang",
                "primaryTargets": [{"caseNumber": "2025고합5", "requiredAnswerText": "D(여, 64세)"}],
                "rankRules": {"primaryMustAppearWithin": 5, "requiredAnswerMustAppearInPrimary": True},
            }
        ],
    }
    artifacts = [
        {
            "caseId": "yangyang",
            "answer": "민원인은 D(여, 64세)입니다.",
            "retrievedCases": [{"caseNumber": "2025고합5", "text": "이 판결문 조각에는 나이 표현이 없다."}],
        }
    ]

    summary = score_legal_predictions(private, artifacts)

    case = summary["cases"][0]
    assert case["passed"] is False
    assert "rank:required_answer_missing_in_primary" in case["failures"]


def test_score_legal_predictions_does_not_match_target_by_decision_date_only():
    private = {
        "benchmarkId": "legal.date.test",
        "graders": [
            {
                "graderId": "case-a",
                "primaryTargets": [{"caseNumber": "2024구합65355", "decisionDate": "2025-01-21"}],
                "rankRules": {"primaryMustAppearWithin": 5},
            }
        ],
    }
    artifacts = [
        {
            "caseId": "case-a",
            "answer": "다른 사건입니다.",
            "retrievedCases": [{"caseNumber": "2024구합99999", "decisionDate": "2025-01-21"}],
        }
    ]

    summary = score_legal_predictions(private, artifacts)

    case = summary["cases"][0]
    assert case["passed"] is False
    assert "rank:primary_not_within:5" in case["failures"]


def test_load_json_artifacts_preserves_legal_runtime_artifact_fields(tmp_path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    payload = {
        "caseId": "legal-a",
        "answer": "2025구합1 판례를 근거로 답변합니다.",
        "retrievedCases": [{"caseNumber": "2025구합1"}],
        "searchResults": [{"metadata": {"caseNumber": "2025구합1"}}],
    }
    (artifacts_dir / "legal-a.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    assert load_json_artifacts(artifacts_dir) == [payload]


def test_official_evaluation_registry_counts_unique_cases_without_slices():
    registry_path = ROOT / "benchmarks" / "evaluation_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    entries = registry["canonicalExamAggregate"]["entries"]
    counts = []
    public_paths = []
    for entry in entries:
        public_path = registry_path.parent / entry["publicManifest"]
        manifest = json.loads(public_path.read_text(encoding="utf-8"))
        count = len(manifest["cases"])
        assert count == entry["expectedCases"]
        counts.append(count)
        public_paths.append(public_path.name)

    assert sum(counts) == registry["canonicalExamAggregate"]["expectedUniqueCases"] == 1235
    assert "mcq_lawkey_leet2026_70.public.json" in public_paths
    assert "mcq_islam_cisi_wrong26.public.json" not in public_paths
    assert "mcq_tcm_kuksiwon81_p1_50.public.json" not in public_paths
    assert "mcq_tcm_kuksiwon81_wikia64.public.json" not in public_paths
    assert registry["legalEndToEnd"]["expectedTasks"] == len(registry["legalEndToEnd"]["entries"]) == 3
    assert registry["legalEndToEnd"]["expectedVariants"] == 10
    public_variant_count = 0
    for entry in registry["legalEndToEnd"]["entries"]:
        public_path = registry_path.parent / entry["publicManifest"]
        manifest = json.loads(public_path.read_text(encoding="utf-8"))
        public_variant_count += sum(
            len(case.get("variants", []))
            for case in manifest.get("cases", [])
            if isinstance(case, dict)
        )
    assert public_variant_count == registry["legalEndToEnd"]["expectedVariants"]
    assert registry["comparisonArms"] == ["direct", "beta6", "universal"]
