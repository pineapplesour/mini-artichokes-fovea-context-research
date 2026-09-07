import hashlib
import json
from pathlib import Path

from tools.build_open_response_benchmarks import (
    EXTRACTIVE_REFERENCE_RE,
    _compact_text,
    build_registry,
    classify_conversion,
    convert_mcq_split,
    split_mcq_prompt,
)
from tools.run_open_response_benchmark import (
    DOMAIN_CLASSIFICATION_ROUTE_PAYLOAD,
    DOMAIN_CLASSIFICATION_ROUTE_SHA256,
    DOMAIN_CLASSIFICATION_ROUTE_VERSION,
    DOMAIN_CLASSIFICATION_SKILL_PAYLOAD,
    DOMAIN_CLASSIFICATION_SKILL_SHA256,
    DOMAIN_CLASSIFICATION_SKILL_VERSION,
    TCM_DOMAIN_CLASSIFICATION_ROUTE_PAYLOAD,
    TCM_DOMAIN_CLASSIFICATION_ROUTE_SHA256,
    TCM_DOMAIN_CLASSIFICATION_ROUTE_VERSION,
    build_open_response_query,
    infer_open_response_language,
    promoted_domain_classification_route_identity,
    run_manifest,
    should_use_promoted_domain_classification,
)


class FakeClient:
    provider = "fixture"
    default_model = "fixture-model"

    def __init__(self, answer='{"finalAnswer":"직접 효과"}'):
        self.answer = answer
        self.calls = []

    def complete(self, messages, *, model="", timeout_seconds=None):
        self.calls.append({"messages": messages, "model": model})
        return self.answer


def _pair(prompt="A를 하면 일어나는 일은?\n① 다른 효과\n② 직접 효과"):
    public = {
        "schemaVersion": 1,
        "benchmarkId": "mcq.fixture.v1",
        "taskType": "mcq",
        "product": "tcm",
        "language": "ko",
        "cases": [{"id": "q1", "prompt": prompt, "graderRef": "q1"}],
    }
    private = {
        "schemaVersion": 1,
        "benchmarkId": "mcq.fixture.v1",
        "answers": [{"caseId": "q1", "correctOptionId": "2"}],
    }
    return public, private


def test_conversion_removes_choices_and_keeps_gold_private():
    public, private = convert_mcq_split(*_pair())

    assert public["benchmarkId"] == "open_response.fixture.v2"
    assert public["taskType"] == "open_response"
    assert public["cases"][0]["prompt"] == "A를 하면 일어나는 일은?"
    assert "직접 효과" not in json.dumps(public, ensure_ascii=False)
    assert private["answers"][0]["canonicalAnswer"] == "직접 효과"
    assert private["answers"][0]["sourceCorrectOptionId"] == "2"
    assert public["cases"][0]["metadata"]["openResponseConversion"]["status"] == "ready_hide_options"


def test_registered_public_private_conversion_statuses_align_exactly():
    repo_root = Path(__file__).resolve().parents[1]
    manifest_root = repo_root / "benchmarks/open_response_v2"
    registry = json.loads(
        (manifest_root / "evaluation_registry.open_response.json").read_text(encoding="utf-8")
    )

    for entry in registry["entries"]:
        public = json.loads((manifest_root / entry["publicManifest"]).read_text(encoding="utf-8"))
        private = json.loads((manifest_root / entry["privateManifest"]).read_text(encoding="utf-8"))
        public_status = {
            case["id"]: case["metadata"]["openResponseConversion"]["status"]
            for case in public["cases"]
        }
        private_status = {
            answer["caseId"]: answer["conversionStatus"]
            for answer in private["answers"]
        }

        assert public_status == private_status


def test_choice_dependent_stem_is_gated_for_rewrite():
    public, _private = convert_mcq_split(*_pair("다음 중 옳은 것은?\n① 다른 효과\n② 직접 효과"))

    conversion = public["cases"][0]["metadata"]["openResponseConversion"]
    assert conversion["status"] == "needs_semantic_rewrite"
    assert conversion["riskReasons"] == ["open_set_or_choice_dependent_stem"]


def test_multilingual_choice_dependent_stems_are_gated_for_rewrite():
    assert classify_conversion("사회민주주의 복지국가의 핵심가치로 맞지 않는 것은?", "민주주의")[0] == "needs_semantic_rewrite"
    assert classify_conversion("Marque a única alternativa correta.", "Pessoa")[0] == "needs_semantic_rewrite"
    assert classify_conversion("요양병원의 입원 대상이 아닌 사람은?", "조현병 환자")[0] == "needs_semantic_rewrite"
    assert classify_conversion("진단서 등을 잘못 발급한 경우는?", "사망 환자를 다시 진료하지 않은 경우")[0] == "needs_semantic_rewrite"
    assert classify_conversion("3기 욕창 환자에서 예후가 좋은 경우는?", "부육이 쉽게 분리된다")[0] == "needs_semantic_rewrite"
    assert classify_conversion("옴 환아에게 적절한 외용제는?", "유황")[0] == "needs_semantic_rewrite"
    assert classify_conversion("미숙아에게서 관찰할 수 있는 특징은?", "피부가 얇다")[0] == "needs_semantic_rewrite"
    assert classify_conversion("㉠과 ㉡에 들어갈 적절한 내용을 옳게 나열한 것은?", "ㄱ, ㄴ")[0] == "needs_semantic_rewrite"
    assert classify_conversion("Which is NOT true about conceptual prototypes", "They summarize a category")[0] == "needs_semantic_rewrite"
    assert classify_conversion("Which of these is TRUE of social support", "It can buffer stress")[0] == "needs_semantic_rewrite"
    assert classify_conversion(
        "Which other brain imaging technologies also offer good temporal and spatial resolution",
        "EEG = good temporal resolution, fMRI = good spatial resolution",
    )[0] == "needs_semantic_rewrite"
    assert classify_conversion("다음 시나리오 중 Wa'd의 가장 좋은 예는 무엇입니까?", "일방적 약속")[0] == "needs_semantic_rewrite"


def test_choice_dependent_question_at_start_of_long_passage_is_not_hidden_by_tail_window():
    stem = "\n".join(
        [
            "문제:",
            "다음으로부터 추론한 것으로 옳은 것은?",
            *[f"긴 제시문 {index}" for index in range(20)],
        ]
    )

    status, reasons = classify_conversion(stem, "가능한 추론", product="lawkey")

    assert status == "needs_semantic_rewrite"
    assert "open_set_or_choice_dependent_stem" in reasons


def test_lawkey_passage_without_an_explicit_question_is_gated_for_rewrite():
    status, reasons = classify_conversion(
        "[제시문]\n행위와 무위의 책임 차이를 논한다.\n철학자는 논변을 다음과 같이 정리한다.",
        "사례 1과 사례 2의 책임은 다르다.",
        product="lawkey",
    )

    assert status == "needs_semantic_rewrite"
    assert reasons == ["missing_explicit_open_response_question"]


def test_any_domain_declarative_fragment_without_a_question_is_gated():
    status, reasons = classify_conversion(
        "이슬람법의 계약에 적용되는 일반 원칙은 다음과 같습니다.",
        "계약의 자유",
        product="islam",
    )

    assert status == "needs_semantic_rewrite"
    assert reasons == ["missing_explicit_open_response_question"]


def test_promoted_domain_classification_route_is_hash_bound_to_closed_heldout_scope():
    assert DOMAIN_CLASSIFICATION_ROUTE_VERSION == "implicit-islam-domain-v1"
    assert len(DOMAIN_CLASSIFICATION_ROUTE_SHA256) == 64
    assert should_use_promoted_domain_classification(
        prompt="계약 당사자의 약속은 어떤 법적 효과를 갖습니까?",
        product="islam",
    ) is True
    assert should_use_promoted_domain_classification(
        prompt="무라바하 계약의 효과는 무엇입니까?",
        product="islam",
    ) is False
    for explicit_prompt in (
        "Arboon의 주요 목적은 무엇입니까?",
        "Ijtihad를 기반으로 문제를 해결한다는 의미는 무엇입니까?",
        "Medina Sale 계약은 어떻게 됩니까?",
    ):
        assert should_use_promoted_domain_classification(prompt=explicit_prompt, product="islam") is False
    assert should_use_promoted_domain_classification(
        prompt="계약 당사자의 약속은 어떤 법적 효과를 갖습니까?",
        product="lawkey",
    ) is False

    evidence = DOMAIN_CLASSIFICATION_ROUTE_PAYLOAD["evidence"]
    heldout = Path(evidence["heldoutGate"])
    decision = Path(evidence["finalDecision"])
    repo_root = Path(__file__).resolve().parents[1]
    assert hashlib.sha256((repo_root / heldout).read_bytes()).hexdigest() == evidence["heldoutGateSha256"]
    assert hashlib.sha256((repo_root / decision).read_bytes()).hexdigest() == evidence["finalDecisionSha256"]
    assert evidence["decision"] == "promote_domain_classification_skill"
    heldout_spec = json.loads((repo_root / heldout).read_text(encoding="utf-8"))
    assert set(DOMAIN_CLASSIFICATION_ROUTE_PAYLOAD["explicitDomainMarkers"]) >= set(
        heldout_spec["selection"]["explicitDomainMarkers"]
    )
    assert DOMAIN_CLASSIFICATION_ROUTE_PAYLOAD["eligibleProducts"] == ["islam"]


def test_tcm_promoted_domain_route_is_bound_to_fresh_closed_heldout_evidence():
    assert TCM_DOMAIN_CLASSIFICATION_ROUTE_VERSION == "tcm-product-domain-v1"
    assert len(TCM_DOMAIN_CLASSIFICATION_ROUTE_SHA256) == 64
    assert should_use_promoted_domain_classification(prompt="어떤 분류에 해당합니까?", product="tcm") is True
    assert promoted_domain_classification_route_identity(product="tcm") == {
        "version": TCM_DOMAIN_CLASSIFICATION_ROUTE_VERSION,
        "sha256": TCM_DOMAIN_CLASSIFICATION_ROUTE_SHA256,
    }

    evidence = TCM_DOMAIN_CLASSIFICATION_ROUTE_PAYLOAD["evidence"]
    repo_root = Path(__file__).resolve().parents[1]
    assert hashlib.sha256((repo_root / evidence["heldoutGate"]).read_bytes()).hexdigest() == evidence["heldoutGateSha256"]
    assert hashlib.sha256((repo_root / evidence["finalDecision"]).read_bytes()).hexdigest() == evidence["finalDecisionSha256"]
    assert evidence["decision"] == "promote_tcm_domain_classification_skill"


def test_negative_membership_selection_is_not_treated_as_unique_open_response():
    status, reasons = classify_conversion(
        "사도행전 15장에서 네 가지에 포함되지 않는 것은?",
        "성전세",
        product="catholic",
    )

    assert status == "needs_semantic_rewrite"
    assert reasons == ["open_set_or_choice_dependent_stem"]


def test_declarative_inclusion_reason_and_open_cancellation_scenarios_are_rewrite_gated():
    for stem, answer in (
        ("부채에 대한 부채에는 다음이 포함됩니다.", "기존 부채를 늘리기 위해 새로운 부채를 발행하는 것"),
        ("다음과 같은 이유로 트윈 판매가 금지됩니다.", "가격 불확실성 조장"),
        ("어떤 상황에서 판매자가 특정 판매와 관련하여 취소 옵션을 사용할 수 없습니까?", "금 매매에 관한 계약"),
    ):
        assert classify_conversion(stem, answer, product="islam") == (
            "needs_semantic_rewrite",
            ["open_set_or_choice_dependent_stem"],
        )


def test_reference_text_overlap_is_gated_except_for_explicit_extractive_question():
    status, reasons = classify_conversion("복토는 위경의 혈위이다. 이 혈위명은?", "복토")
    assert status == "needs_semantic_rewrite"
    assert "reference_answer_text_present_in_stem" in reasons
    assert classify_conversion('“A outra alma”에서 대명사 a refere-se a 무엇인가?', "outra alma")[0] == "ready_hide_options"


def test_broad_safety_question_is_gated_when_choices_are_hidden():
    status, reasons = classify_conversion(
        "노인에게 한약을 처방할 때 주의할 것은?",
        "보음약에는 택사나 목단피를 가한다.",
    )

    assert status == "needs_semantic_rewrite"
    assert reasons == ["open_set_or_choice_dependent_stem"]


def test_broad_lifestyle_guidance_is_gated_when_choices_are_hidden():
    status, reasons = classify_conversion(
        "복압성 요실금 환자에게 지도할 생활관리는?",
        "케겔운동을 1일 3회 시행한다.",
        product="tcm",
    )

    assert status == "needs_semantic_rewrite"
    assert reasons == ["open_set_or_choice_dependent_stem"]


def test_open_ended_treatment_eligibility_is_gated_when_choices_are_hidden():
    status, reasons = classify_conversion(
        "오한, 발열, 두통 환자 중 발한법을 쓸 수 있는 경우는?",
        "숨을 헐떡이며 흉중이 그득한 사람",
        product="tcm",
    )

    assert status == "needs_semantic_rewrite"
    assert reasons == ["open_set_or_choice_dependent_stem"]


def test_tcm_ocr_corruption_and_missing_stimulus_are_gated():
    status, reasons = classify_conversion(
        "방문진료한 환자의 SYS 다음과 같다. 사물이 FRO] 보이고 AP AOL} PRS 한다.",
        "DSR)",
        product="tcm",
    )
    assert status == "needs_semantic_rewrite"
    assert "reference_looks_ocr_corrupted" in reasons
    assert "source_text_looks_ocr_corrupted_or_missing_stimulus" in reasons

    status, reasons = classify_conversion(
        "딕스-홀파이크 검사와 뇌 MRI 결과이다. 진단은? <자료(비공개)>",
        "양성돌발체위현훈",
        product="tcm",
    )
    assert status == "needs_semantic_rewrite"
    assert reasons == ["source_text_looks_ocr_corrupted_or_missing_stimulus"]

    status, reasons = classify_conversion(
        "오랜 투병 생활로 몸이 쇠약해진 상태이다. BSL?",
        "건협통",
        product="tcm",
    )
    assert status == "needs_semantic_rewrite"
    assert reasons == ["source_text_looks_ocr_corrupted_or_missing_stimulus"]

    status, reasons = classify_conversion(
        "보행 시 좌측으로 몸이 SEL, 좌측 통각이 감소하고 SHAS 한다. 손상 부위는?",
        "연수 후외측",
        product="tcm",
    )
    assert status == "needs_semantic_rewrite"
    assert reasons == ["source_text_looks_ocr_corrupted_or_missing_stimulus"]

    status, reasons = classify_conversion(
        "얼굴과 손발이 노랗고 SAS 흰색이며 빌리루빈은 정상이다. 원인은?",
        "7}2 Ela S(carotenemia)",
        product="tcm",
    )
    assert status == "needs_semantic_rewrite"
    assert reasons == [
        "reference_looks_ocr_corrupted",
        "source_text_looks_ocr_corrupted_or_missing_stimulus",
    ]


def test_tcm_prescription_selection_is_gated_because_valid_alternatives_can_be_absent_from_choices():
    status, reasons = classify_conversion(
        "기운이 없고 손발이 차며 소변이 적고 대변이 무르다. 치방은?",
        "보중치습탕",
        product="tcm",
    )

    assert status == "needs_semantic_rewrite"
    assert reasons == ["tcm_prescription_not_unique_without_choices"]


def test_tcm_ocr_corrupted_chibang_selection_is_gated_when_reference_is_formula():
    status, reasons = classify_conversion("갑상선 종괴 환자의 지방은?", "시호청간탕(柴胡淸肝湯)", product="tcm")
    assert status == "needs_semantic_rewrite"
    assert reasons == ["tcm_prescription_not_unique_without_choices"]


def test_tcm_curated_modern_diagnosis_alias_is_private_and_deterministic():
    public, private = convert_mcq_split(*_pair("병변이 표피로 둘러싸인 각질을 함유한다. 병증은?\n① 지방종\n② 지류(脂瘤)"))

    assert "표피낭종" not in json.dumps(public, ensure_ascii=False)
    assert "표피낭종" in private["answers"][0]["aliases"]


def test_tcm_cdr_korean_word_order_aliases_remain_private():
    public, private = convert_mcq_split(
        {
            "schemaVersion": 1,
            "benchmarkId": "mcq.tcm.fixture.v1",
            "taskType": "mcq",
            "product": "tcm",
            "cases": [{"id": "q1", "prompt": "치매 중증도 척도는?\n① MMSE\n② CDR(Clinical Dementia Rating)"}],
        },
        {"benchmarkId": "mcq.tcm.fixture.v1", "answers": [{"caseId": "q1", "correctOptionId": "2"}]},
    )

    assert "임상치매평가척도" not in json.dumps(public, ensure_ascii=False)
    assert "임상치매평가척도" in private["answers"][0]["aliases"]


def test_corrected_psych_heuristics_gold_and_ordered_aliases_are_private():
    repo_root = Path(__file__).resolve().parents[1]
    public_source = json.loads(
        (repo_root / "benchmarks/unified/mcq_psych_mit_sangmyung.public.json").read_text(encoding="utf-8")
    )
    private_source = json.loads(
        (repo_root / "benchmarks/unified/mcq_psych_mit_sangmyung.private.json").read_text(encoding="utf-8")
    )
    case_id = "psych-mit-sangmyung-MIT_IntroPsych_2009_Practice_Exam2_문제_정답-q009"
    public, private = convert_mcq_split(public_source, private_source)
    answer = next(item for item in private["answers"] if item["caseId"] == case_id)
    public_case = next(item for item in public["cases"] if item["id"] == case_id)

    assert answer["sourceCorrectOptionId"] == "4"
    assert answer["canonicalAnswer"] == "(a) anchoring; (b) representativeness; (c) availability"
    assert "anchoring, representativeness, and availability" in answer["aliases"]
    assert "anchoring and adjustment; representativeness; availability" in answer["aliases"]
    assert "anchoring and adjustment" not in json.dumps(public_case, ensure_ascii=False)


def test_fallback_handles_numbered_question_that_looks_like_option():
    prompt = "1. Com respeito à santificação é correto dizer que:\n\n① primeira\n② segunda\n③ terceira"

    split = split_mcq_prompt(prompt, product="catholic")

    assert split.method == "circled_fallback"
    assert split.stem.startswith("1. Com respeito")
    assert split.option_count == 3


def test_native_runner_defaults_to_ready_cases_and_never_reads_private_gold(tmp_path):
    ready_public, _private = convert_mcq_split(*_pair())
    risky_public, _ = convert_mcq_split(*_pair("다음 중 옳은 것은?\n① 다른 효과\n② 직접 효과"))
    ready_public["cases"].append({**risky_public["cases"][0], "id": "q2"})
    public_path = tmp_path / "public.json"
    public_path.write_text(json.dumps(ready_public, ensure_ascii=False), encoding="utf-8")
    client = FakeClient()

    summary = run_manifest(
        public_path=public_path,
        output_dir=tmp_path / "run",
        llm_client=client,
        model="fixture-model",
    )

    assert summary["total"] == {"total": 1, "predicted": 1, "errors": 0}
    artifact = json.loads((tmp_path / "run" / "results" / "q1.json").read_text(encoding="utf-8"))
    assert artifact["prediction"] == "직접 효과"
    assert artifact["promptIdentity"]["sourceItemId"] == "q1"
    assert artifact["promptIdentity"]["publicPromptSha256"] == hashlib.sha256(
        ready_public["cases"][0]["prompt"].encode("utf-8")
    ).hexdigest()
    assert artifact["promptIdentity"]["modelInputSha256"] == hashlib.sha256(
        client.calls[0]["messages"][0]["content"].encode("utf-8")
    ).hexdigest()
    assert artifact["promptIdentity"]["builderId"] == "open_response_query_v1"
    sent = json.dumps(client.calls, ensure_ascii=False)
    assert "직접 효과" not in sent
    assert "보기 번호나 문자가 아니라" in sent


def test_registry_conversion_recovers_all_945_current_mcqs(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    report = build_registry(repo_root / "benchmarks" / "evaluation_registry.json", tmp_path / "open")

    assert report["totalConvertedMcqCases"] == 945
    assert report["readyHideOptionsCases"] == 472
    assert report["needsSemanticRewriteCases"] == 473
    assert len(report["entries"]) == 7
    for entry in report["entries"]:
        public = json.loads((tmp_path / "open" / entry["publicManifest"]).read_text(encoding="utf-8"))
        private = json.loads((tmp_path / "open" / entry["privateManifest"]).read_text(encoding="utf-8"))
        assert len(public["cases"]) == len(private["answers"]) == entry["cases"]
        answers = {answer["caseId"]: answer for answer in private["answers"]}
        for case in public["cases"]:
            if case["metadata"]["openResponseConversion"]["status"] != "ready_hide_options":
                continue
            compact_answer = _compact_text(answers[case["id"]]["canonicalAnswer"])
            if len(compact_answer) >= 2 and compact_answer in _compact_text(case["prompt"]):
                assert EXTRACTIVE_REFERENCE_RE.search(case["prompt"])


def test_luna_pilot_v2_tcm_gate_matches_all_current_ready_cases():
    repo_root = Path(__file__).resolve().parents[1]
    pilot = json.loads((repo_root / "benchmarks/pilot_gates/luna_pilot_v2.json").read_text(encoding="utf-8"))
    public = json.loads(
        (repo_root / "benchmarks/open_response_v2/open_response_tcm_kuksiwon81_unique92.public.json").read_text(
            encoding="utf-8"
        )
    )
    tcm_gate = next(item for item in pilot["gates"] if item["id"] == "tcm17")
    ready_ids = [
        case["id"]
        for case in public["cases"]
        if case["metadata"]["openResponseConversion"]["status"] == "ready_hide_options"
    ]

    assert tcm_gate["caseIds"] == ready_ids
    assert tcm_gate["expectedCases"] == len(ready_ids) == 17
    assert tcm_gate["excludedRewriteCases"] == 75


def test_open_response_query_requires_answer_content_json():
    query = build_open_response_query("A의 효과는?", language="ko")

    assert "보기 번호나 문자가 아니라" in query
    assert '"finalAnswer"' in query


def test_open_response_query_can_include_only_declared_public_product_context():
    query = build_open_response_query(
        "병증은?",
        language="ko",
        product="tcm",
        include_public_product_context=True,
    )

    assert "공개 분야: 한의학" in query
    assert "표준 용어와 분류" in query
    assert "정답" not in query


def test_open_response_query_can_apply_single_pass_self_verify_without_revealing_checks():
    query = build_open_response_query(
        "Which heuristics explain the three examples?",
        language="en",
        product="psych",
        single_pass_self_verify=True,
    )

    assert "privately form three distinct candidate answers" in query
    assert "one plausible counterexample" in query
    assert "Do not reveal the candidates or checks" in query
    assert '"finalAnswer"' in query


def test_open_response_query_can_apply_hash_bound_domain_classification_skill():
    query = build_open_response_query(
        "대리인의 계약 효력은?",
        language="ko",
        product="islam",
        include_public_product_context=True,
        preserve_domain_classification=True,
    )

    assert "공개 분야: 이슬람학" in query
    assert DOMAIN_CLASSIFICATION_SKILL_PAYLOAD["ko"] in query
    assert "유효·무효" in query
    assert "시행 가능·불가능" in query
    assert DOMAIN_CLASSIFICATION_SKILL_VERSION == "preserve-domain-classification-v1"
    assert len(DOMAIN_CLASSIFICATION_SKILL_SHA256) == 64


def test_mixed_manifest_language_is_inferred_from_each_prompt():
    assert infer_open_response_language("Which heuristics explain these examples", "ko") == "en"
    assert infer_open_response_language("이 사례들을 설명하는 휴리스틱은?", "en") == "ko"
    assert infer_open_response_language("123", "pt") == "pt"


def test_open_response_query_can_require_safe_general_web_search():
    query = build_open_response_query(
        "후인도 계약 유형은?",
        language="ko",
        product="islam",
        require_general_web_search=True,
    )

    assert "일반 개념·제도명" in query
    assert "최소 한 번" in query
    assert "문제 문장" in query
    assert "답안 사이트" in query
