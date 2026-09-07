import json

from tools.rewrite_open_response_prompts import (
    _artifact_digest,
    _text_sha256,
    build_author_prompt,
    build_reviewer_prompt,
    rewrite_manifests,
    validate_rewritten_prompt,
    validate_single_case_swap_override,
)


def _manifests():
    public = {
        "schemaVersion": 2,
        "benchmarkId": "open.fixture.v2",
        "taskType": "open_response",
        "product": "tcm",
        "language": "ko",
        "conversionAudit": {"statusCounts": {"needs_semantic_rewrite": 1}},
        "cases": [
            {
                "id": "q1",
                "prompt": "다음 중 특정 경혈군에 해당하는 것은?",
                "metadata": {
                    "openResponseConversion": {
                        "status": "needs_semantic_rewrite",
                        "riskReasons": ["open_set_or_choice_dependent_stem"],
                    }
                },
                "graderRef": "q1",
            }
        ],
    }
    private = {
        "schemaVersion": 2,
        "benchmarkId": "open.fixture.v2",
        "answers": [
            {
                "caseId": "q1",
                "canonicalAnswer": "복토",
                "aliases": ["伏兔"],
                "conversionStatus": "needs_semantic_rewrite",
            }
        ],
    }
    return public, private


def _closed_trace():
    return {
        "provider": "codex_exec",
        "status": "completed",
        "codexJsonlInvalidLineCount": 0,
        "webSearchEvents": [],
        "commandExecutionEvents": [],
        "mcpToolEvents": [],
        "tokenUsage": {"totalTokens": 10},
    }


def test_rewrite_prompts_require_complete_canonical_scope_and_preserve_underlying_knowledge():
    public, private = _manifests()
    case = public["cases"][0]
    answer = private["answers"][0]

    author_prompt = build_author_prompt(manifest=public, case=case, answer_spec=answer)
    reviewer_prompt = build_reviewer_prompt(
        manifest=public,
        case=case,
        answer_spec=answer,
        rewritten_prompt="위치 단서로 특정되는 혈위명은 무엇인가?",
        repeat=1,
    )

    assert "directly and completely answer every slot" in author_prompt
    assert "never give two symbols the same description" in author_prompt
    assert "minimal stem-only rewrite" in author_prompt
    assert "retain the complete source body verbatim" in author_prompt
    assert "does NOT by itself change the knowledge target" in reviewer_prompt
    assert "underlying fact, rule, concept, or inference" in reviewer_prompt
    assert "become indistinguishable" in reviewer_prompt
    assert "making a minimal stem-only conversion" in reviewer_prompt


def test_deterministic_validator_rejects_choice_wording_and_answer_leakage():
    answer = {"canonicalAnswer": "복토", "aliases": ["伏兔"]}
    assert "choice_dependent_wording_remains" in validate_rewritten_prompt("다음 중 복토에 해당하는 것을 고르시오?", answer)
    assert "answer_text_leakage" in validate_rewritten_prompt("대퇴부의 복토 혈위는 무엇인가?", answer)
    assert validate_rewritten_prompt("위경의 혈위로, 슬개골 위쪽 대퇴 전외측에 위치한 혈위명은 무엇인가?", answer) == []


def test_deterministic_validator_rejects_standalone_single_character_answer_leakage_only():
    answer = {"canonicalAnswer": "갑", "aliases": []}

    assert "answer_text_leakage" in validate_rewritten_prompt("정답은 갑이라고 쓰면 되는가?", answer)
    assert "answer_text_leakage" not in validate_rewritten_prompt("갑상선 기능과 무관한 계약 당사자의 지위는 무엇인가?", answer)


def test_rewrite_promotes_only_after_strict_private_review(tmp_path):
    public, private = _manifests()
    responses = iter(
        [
            json.dumps(
                {
                    "status": "ok",
                    "rewrittenPrompt": "위경에 속하며 슬개골 위쪽 대퇴 전외측에 위치한 혈위명은 무엇인가?",
                    "expectedAnswerType": "혈위명",
                    "uniquenessBasis": "경락과 해부학적 위치",
                    "reason": "고유 위치로 식별",
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "verdict": "pass",
                    "answerableWithoutChoices": True,
                    "uniquelyTargetsCanonical": True,
                    "canonicalDirectlyAnswers": True,
                    "sameKnowledgeTarget": True,
                    "factuallyPlausible": True,
                    "noAnswerLeakage": True,
                    "reason": "고유 단서가 충분함",
                },
                ensure_ascii=False,
            ),
        ]
    )

    class FakeClient:
        def complete(self, messages, *, model):
            return next(responses)

        def consume_last_call_trace(self):
            return _closed_trace()

    report = rewrite_manifests(
        public_manifest=public,
        private_manifest=private,
        output_dir=tmp_path,
        llm_client=FakeClient(),
        max_model_calls=2,
    )

    assert report["approved"] == 1
    promoted_public = json.loads((tmp_path / "open.fixture.v2.rewritten.public.json").read_text(encoding="utf-8"))
    promoted_private = json.loads((tmp_path / "open.fixture.v2.rewritten.private.json").read_text(encoding="utf-8"))
    assert promoted_public["cases"][0]["metadata"]["openResponseConversion"]["status"] == "ready_semantic_rewrite"
    assert promoted_private["answers"][0]["conversionStatus"] == "ready_semantic_rewrite"
    assert "복토" not in promoted_public["cases"][0]["prompt"]
    assert "복토" in (tmp_path / "drafts-private" / "q1.private.json").read_text(encoding="utf-8")


def test_rewrite_does_not_promote_when_review_rejects_uniqueness(tmp_path):
    public, private = _manifests()
    responses = iter(
        [
            json.dumps(
                {
                    "status": "ok",
                    "rewrittenPrompt": "각기팔처혈에 포함되는 혈위 하나를 쓰시오.",
                    "expectedAnswerType": "혈위명",
                    "uniquenessBasis": "없음",
                    "reason": "범주 구성원을 요구",
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "verdict": "reject",
                    "answerableWithoutChoices": True,
                    "uniquelyTargetsCanonical": False,
                    "canonicalDirectlyAnswers": True,
                    "sameKnowledgeTarget": True,
                    "factuallyPlausible": True,
                    "noAnswerLeakage": True,
                    "reason": "복수 정답 가능",
                },
                ensure_ascii=False,
            ),
        ]
    )

    class FakeClient:
        def complete(self, messages, *, model):
            return next(responses)

        def consume_last_call_trace(self):
            return _closed_trace()

    report = rewrite_manifests(
        public_manifest=public,
        private_manifest=private,
        output_dir=tmp_path,
        llm_client=FakeClient(),
        max_model_calls=2,
    )

    assert report["approved"] == 0
    promoted = json.loads((tmp_path / "open.fixture.v2.rewritten.public.json").read_text(encoding="utf-8"))
    assert promoted["cases"][0]["metadata"]["openResponseConversion"]["status"] == "needs_semantic_rewrite"


def test_sequential_single_case_rewrites_accumulate_verified_private_drafts(tmp_path):
    public, private = _manifests()
    public["cases"].append({
        "id": "q2",
        "prompt": "다음 중 특정 경혈에 해당하는 것은?",
        "metadata": {"openResponseConversion": {"status": "needs_semantic_rewrite", "riskReasons": ["choice"]}},
    })
    private["answers"].append({
        "caseId": "q2",
        "canonicalAnswer": "족삼리",
        "aliases": ["足三里"],
        "conversionStatus": "needs_semantic_rewrite",
    })
    responses = iter([
        json.dumps({
            "status": "ok",
            "rewrittenPrompt": "위경에 속하며 슬개골 위쪽 대퇴 전외측에 위치한 혈위명은 무엇인가?",
            "expectedAnswerType": "혈위명",
            "uniquenessBasis": "위치",
            "reason": "고유함",
        }, ensure_ascii=False),
        json.dumps({
            "verdict": "pass",
            "answerableWithoutChoices": True,
            "uniquelyTargetsCanonical": True,
            "canonicalDirectlyAnswers": True,
            "sameKnowledgeTarget": True,
            "factuallyPlausible": True,
            "noAnswerLeakage": True,
            "reason": "통과",
        }, ensure_ascii=False),
        json.dumps({
            "status": "ok",
            "rewrittenPrompt": "위경의 합혈로 독비 아래 세 촌, 경골 앞모서리 가쪽에 위치한 혈위명은 무엇인가?",
            "expectedAnswerType": "혈위명",
            "uniquenessBasis": "경락과 위치",
            "reason": "고유함",
        }, ensure_ascii=False),
        json.dumps({
            "verdict": "pass",
            "answerableWithoutChoices": True,
            "uniquelyTargetsCanonical": True,
            "canonicalDirectlyAnswers": True,
            "sameKnowledgeTarget": True,
            "factuallyPlausible": True,
            "noAnswerLeakage": True,
            "reason": "통과",
        }, ensure_ascii=False),
    ])

    class FakeClient:
        def complete(self, messages, *, model):
            return next(responses)

        def consume_last_call_trace(self):
            return _closed_trace()

    first = rewrite_manifests(
        public_manifest=public,
        private_manifest=private,
        output_dir=tmp_path,
        llm_client=FakeClient(),
        case_ids=["q1"],
        max_cases=1,
        max_model_calls=2,
    )
    second = rewrite_manifests(
        public_manifest=public,
        private_manifest=private,
        output_dir=tmp_path,
        llm_client=FakeClient(),
        case_ids=["q2"],
        max_cases=1,
        max_model_calls=2,
        resume=True,
    )

    assert first["approved"] == 1
    assert second["approved"] == 2
    promoted = json.loads((tmp_path / "open.fixture.v2.rewritten.public.json").read_text(encoding="utf-8"))
    assert [case["metadata"]["openResponseConversion"]["status"] for case in promoted["cases"]] == [
        "ready_semantic_rewrite",
        "ready_semantic_rewrite",
    ]


def test_rewrite_zero_budget_makes_no_model_call(tmp_path):
    public, private = _manifests()

    class FailingClient:
        def complete(self, messages, *, model):
            raise AssertionError("zero budget must not call the model")

    report = rewrite_manifests(
        public_manifest=public,
        private_manifest=private,
        output_dir=tmp_path,
        llm_client=FailingClient(),
        max_model_calls=0,
    )

    assert report["modelCallsUsed"] == 0
    assert report["approved"] == 0


def test_rewrite_does_not_review_or_promote_an_author_with_tool_activity(tmp_path):
    public, private = _manifests()

    class ToolUsingClient:
        def __init__(self):
            self.calls = 0

        def complete(self, messages, *, model):
            self.calls += 1
            return json.dumps({
                "status": "ok",
                "rewrittenPrompt": "위경에 속하며 슬개골 위쪽 대퇴 전외측에 위치한 혈위명은 무엇인가?",
                "expectedAnswerType": "혈위명",
                "uniquenessBasis": "경락과 위치",
                "reason": "고유함",
            }, ensure_ascii=False)

        def consume_last_call_trace(self):
            trace = _closed_trace()
            trace["webSearchEvents"] = [{"query": "private answer lookup"}]
            return trace

    client = ToolUsingClient()
    report = rewrite_manifests(
        public_manifest=public,
        private_manifest=private,
        output_dir=tmp_path,
        llm_client=client,
        max_model_calls=2,
    )

    assert client.calls == 1
    assert report["approved"] == 0
    artifact = json.loads((tmp_path / "drafts-private" / "q1.private.json").read_text(encoding="utf-8"))
    assert artifact["traceErrors"] == ["author:web_search_used"]
    assert artifact["reviews"] == []


def test_rewrite_resume_fails_closed_after_approved_draft_tampering(tmp_path):
    public, private = _manifests()
    responses = iter([
        json.dumps({
            "status": "ok",
            "rewrittenPrompt": "위경에 속하며 슬개골 위쪽 대퇴 전외측에 위치한 혈위명은 무엇인가?",
            "expectedAnswerType": "혈위명",
            "uniquenessBasis": "경락과 위치",
            "reason": "고유함",
        }, ensure_ascii=False),
        json.dumps({
            "verdict": "pass",
            "answerableWithoutChoices": True,
            "uniquelyTargetsCanonical": True,
            "canonicalDirectlyAnswers": True,
            "sameKnowledgeTarget": True,
            "factuallyPlausible": True,
            "noAnswerLeakage": True,
            "reason": "통과",
        }, ensure_ascii=False),
    ])

    class FakeClient:
        def complete(self, messages, *, model):
            return next(responses)

        def consume_last_call_trace(self):
            return _closed_trace()

    rewrite_manifests(
        public_manifest=public,
        private_manifest=private,
        output_dir=tmp_path,
        llm_client=FakeClient(),
        max_model_calls=2,
    )
    draft = tmp_path / "drafts-private" / "q1.private.json"
    payload = json.loads(draft.read_text(encoding="utf-8"))
    payload["author"]["rewrittenPrompt"] = "보기 없이도 복토가 정답이라고 쓰시오."
    draft.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with __import__("pytest").raises(ValueError, match="artifact digest mismatch"):
        rewrite_manifests(
            public_manifest=public,
            private_manifest=private,
            output_dir=tmp_path,
            llm_client=FakeClient(),
            max_model_calls=2,
            resume=True,
        )


def test_rewrite_resume_revalidates_content_even_if_tampered_digest_is_recomputed(tmp_path):
    public, private = _manifests()
    responses = iter([
        json.dumps({
            "status": "ok",
            "rewrittenPrompt": "위경에 속하며 슬개골 위쪽 대퇴 전외측에 위치한 혈위명은 무엇인가?",
            "expectedAnswerType": "혈위명",
            "uniquenessBasis": "경락과 위치",
            "reason": "고유함",
        }, ensure_ascii=False),
        json.dumps({
            "verdict": "pass",
            "answerableWithoutChoices": True,
            "uniquelyTargetsCanonical": True,
            "canonicalDirectlyAnswers": True,
            "sameKnowledgeTarget": True,
            "factuallyPlausible": True,
            "noAnswerLeakage": True,
            "reason": "통과",
        }, ensure_ascii=False),
    ])

    class FakeClient:
        def complete(self, messages, *, model):
            return next(responses)

        def consume_last_call_trace(self):
            return _closed_trace()

    rewrite_manifests(
        public_manifest=public,
        private_manifest=private,
        output_dir=tmp_path,
        llm_client=FakeClient(),
        max_model_calls=2,
    )
    draft = tmp_path / "drafts-private" / "q1.private.json"
    payload = json.loads(draft.read_text(encoding="utf-8"))
    payload["author"]["rewrittenPrompt"] = "보기 없이도 복토가 정답이라고 쓰시오."
    payload["authorRawResponse"] = json.dumps(payload["author"], ensure_ascii=False)
    payload["authorRawResponseSha256"] = _text_sha256(payload["authorRawResponse"])
    payload["artifactDigest"] = _artifact_digest(payload)
    draft.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with __import__("pytest").raises(ValueError, match="fails current deterministic validation"):
        rewrite_manifests(
            public_manifest=public,
            private_manifest=private,
            output_dir=tmp_path,
            llm_client=FakeClient(),
            max_model_calls=2,
            resume=True,
        )


def test_rewrite_existing_swap_override_is_one_author_review_sequence():
    valid = {
        "requested": True,
        "case_ids": ["q1"],
        "max_cases": 1,
        "max_model_calls": 2,
        "review_repeats": 1,
    }
    validate_single_case_swap_override(**valid)
    validate_single_case_swap_override(**{**valid, "max_model_calls": 3, "review_repeats": 2})
    for changed in (
        {"case_ids": []},
        {"case_ids": ["q1", "q2"]},
        {"max_cases": 2},
        {"max_model_calls": 1},
        {"max_model_calls": 3},
        {"review_repeats": 3, "max_model_calls": 4},
        {"review_repeats": 2, "max_model_calls": 2},
    ):
        with __import__("pytest").raises(ValueError):
            validate_single_case_swap_override(**{**valid, **changed})
