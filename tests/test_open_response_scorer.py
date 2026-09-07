from tools.score_open_responses import (
    JudgeBudget,
    grade_candidate,
    live_judge_required,
    normalize_answer,
    normalize_exact_formula_surface,
    SEMANTIC_JUDGE_POLICY_VERSION,
    semantic_judge_input_sha256,
    score_run,
    validate_single_case_judge_swap_override,
)


class FakeJudge:
    def __init__(self, decisions):
        self.decisions = list(decisions)
        self.prompts = []

    def complete(self, messages, *, model=""):
        self.prompts.append(messages[0]["content"])
        equivalent = self.decisions.pop(0)
        return (
            '{"equivalent":'
            + ("true" if equivalent else "false")
            + ',"contradiction":false,"missingCriticalFacts":[],"reason":"fixture"}'
        )

    def consume_last_call_trace(self):
        return _closed_trace()


def _closed_trace(**overrides):
    trace = {
        "provider": "codex_exec",
        "status": "completed",
        "codexJsonlEventCount": 3,
        "codexJsonlInvalidLineCount": 0,
        "webSearchEnabled": False,
        "domainEvidenceMcpEnabled": False,
        "agentWorkspaceEnabled": False,
        "webSearchEvents": [],
        "commandExecutionEvents": [],
        "mcpToolEvents": [],
        "skillEvents": [],
        "tokenUsage": {"totalTokens": 100},
    }
    trace.update(overrides)
    return trace


def _existing_attempt(*, repeat, equivalent, input_sha256, model="gpt-5.6-luna", reason="fixture"):
    return {
        "repeat": repeat,
        "equivalent": equivalent,
        "contradiction": False,
        "missingCriticalFacts": [],
        "reason": reason,
        "semanticInputSha256": input_sha256,
        "judgeModel": model,
        "policyVersion": SEMANTIC_JUDGE_POLICY_VERSION,
        "closedToolTraceAudit": {
            "policy": "closed_codex_jsonl_no_web_shell_mcp_skill_v1",
            "passed": True,
            "violations": [],
        },
    }


def test_zero_call_rescoring_does_not_require_a_live_judge_client():
    assert not live_judge_required(judge_model="gpt-5.6-luna", max_judge_calls=0)
    assert live_judge_required(judge_model="gpt-5.6-luna", max_judge_calls=1)


def _spec(**overrides):
    value = {
        "canonicalAnswer": "강수량이 증가한다",
        "aliases": ["비가 더 많이 온다"],
        "keywordRules": {"autoConfirm": False, "mustIncludeGroups": [], "mustNotIncludeAny": []},
    }
    value.update(overrides)
    return value


def test_normalized_exact_and_alias_confirm_without_judge():
    assert normalize_answer("  강수량이  증가한다. ") == "강수량이 증가한다"
    assert grade_candidate(question="효과는?", candidate="강수량이 증가한다.", answer_spec=_spec()).path == "normalized_exact"
    assert grade_candidate(question="효과는?", candidate="비가 더 많이 온다", answer_spec=_spec()).path == "declared_alias_exact"


def test_formula_surface_exact_confirms_only_presentation_differences():
    assert normalize_exact_formula_surface("(x - z) − (y - w)") == "(x-z)-(y-w)"
    decision = grade_candidate(
        question="산술식은?",
        candidate="(x-z)-(y-w)",
        answer_spec=_spec(canonicalAnswer="(x - z) - (y - w)", aliases=[]),
    )
    assert decision.verdict == "pass"
    assert decision.path == "formula_surface_exact"
    assert normalize_exact_formula_surface("not x") is None
    assert (
        grade_candidate(
            question="산술식은?",
            candidate="x-z-y+w",
            answer_spec=_spec(canonicalAnswer="(x - z) - (y - w)", aliases=[]),
        ).path
        == "semantic_judge_not_run"
    )


def test_exact_term_with_noncontradictory_parenthetical_annotation_confirms_without_judge():
    assert (
        grade_candidate(
            question="진단은?",
            candidate="돌발진(영아 장미진 / roseola infantum)",
            answer_spec=_spec(canonicalAnswer="돌발진", aliases=["영아 장미진", "roseola infantum"]),
        ).path
        == "canonical_with_parenthetical_annotation"
    )

    alias_annotation = grade_candidate(
        question="검사척도는?",
        candidate="치매임상평가척도(CDR, Clinical Dementia Rating)",
        answer_spec=_spec(
            canonicalAnswer="CDR(Clinical Dementia Rating)",
            aliases=["치매임상평가척도"],
        ),
    )
    assert alias_annotation.path == "canonical_with_parenthetical_annotation"
    assert (
        grade_candidate(
            question="치료법은?",
            candidate="혐오요법(aversive therapy)",
            answer_spec=_spec(canonicalAnswer="혐오요법", aliases=["aversive therapy"]),
        ).path
        == "canonical_with_parenthetical_annotation"
    )


def test_parenthetical_annotation_gate_rejects_undeclared_explanation_contradiction_and_nonexact_prefix():
    contradicted = grade_candidate(
        question="진단은?",
        candidate="돌발진(아님)",
        answer_spec=_spec(canonicalAnswer="돌발진", aliases=[]),
    )
    different = grade_candidate(
        question="진단은?",
        candidate="돌발진단(roseola)",
        answer_spec=_spec(canonicalAnswer="돌발진", aliases=[]),
    )
    undeclared = grade_candidate(
        question="진단은?",
        candidate="돌발진(HHV-6 감염)",
        answer_spec=_spec(canonicalAnswer="돌발진", aliases=["영아 장미진", "roseola infantum"]),
    )

    assert contradicted.path == "semantic_judge_not_run"
    assert different.path == "semantic_judge_not_run"
    assert undeclared.path == "semantic_judge_not_run"


def test_keywords_do_not_auto_confirm_without_curator_flag():
    decision = grade_candidate(
        question="효과는?",
        candidate="강수량은 증가하지 않는다",
        answer_spec=_spec(),
    )

    assert decision.verdict == "unresolved"
    assert decision.path == "semantic_judge_not_run"


def test_explicit_keyword_rule_requires_all_groups_and_no_forbidden_term():
    spec = _spec(
        keywordRules={
            "autoConfirm": True,
            "mustIncludeGroups": [["강수량", "비"], ["증가", "늘어"]],
            "mustNotIncludeAny": ["감소", "증가하지 않"],
        }
    )

    assert grade_candidate(question="효과는?", candidate="비의 양이 늘어난다", answer_spec=spec).path == "explicit_keyword_confirm"
    assert grade_candidate(question="효과는?", candidate="강수량이 증가하지 않는다", answer_spec=spec).verdict == "fail"


def test_semantic_judge_uses_two_agreeing_repeats_without_distractors():
    judge = FakeJudge([True, True])
    budget = JudgeBudget(2)

    decision = grade_candidate(
        question="효과는?",
        candidate="비의 총량이 늘어난다",
        answer_spec=_spec(),
        judge_client=judge,
        judge_model="gpt-5.6-luna",
        judge_budget=budget,
    )

    assert decision.verdict == "pass"
    assert decision.path == "semantic_judge_2of2"
    assert budget.used_calls == 2
    assert all("multiple-choice distractors" in prompt for prompt in judge.prompts)
    assert all("오답 선택지" not in prompt for prompt in judge.prompts)
    assert all(attempt["closedToolTraceAudit"]["passed"] for attempt in decision.judge_attempts)


def test_semantic_judge_fails_closed_when_tool_trace_is_not_closed():
    class UnsafeJudge(FakeJudge):
        def consume_last_call_trace(self):
            return _closed_trace(
                webSearchEnabled=True,
                webSearchEvents=[{"query": "answer key"}],
            )

    decision = grade_candidate(
        question="효과는?",
        candidate="비의 총량이 늘어난다",
        answer_spec=_spec(),
        judge_client=UnsafeJudge([True, True]),
        judge_model="gpt-5.6-luna",
        judge_budget=JudgeBudget(2),
    )

    assert decision.verdict == "unresolved"
    assert decision.path == "semantic_judge_unresolved"
    called_attempts = [attempt for attempt in decision.judge_attempts if attempt.get("error") != "judge_call_budget_exhausted"]
    assert len(called_attempts) == 2
    assert all("semantic_judge_closed_tool_trace_failed" in attempt["error"] for attempt in called_attempts)


def test_semantic_disagreement_runs_tie_breaker_and_budget_can_leave_unresolved():
    judge = FakeJudge([True, False, True])
    decision = grade_candidate(
        question="효과는?",
        candidate="비의 총량이 늘어난다",
        answer_spec=_spec(),
        judge_client=judge,
        judge_model="gpt-5.6-luna",
        judge_budget=JudgeBudget(3),
    )
    assert decision.verdict == "pass"
    assert decision.path == "semantic_judge_2of3"

    exhausted = grade_candidate(
        question="효과는?",
        candidate="비의 총량이 늘어난다",
        answer_spec=_spec(),
        judge_client=FakeJudge([True]),
        judge_model="gpt-5.6-luna",
        judge_budget=JudgeBudget(1),
    )
    assert exhausted.verdict == "unresolved"
    assert exhausted.path == "semantic_judge_unresolved"


def test_semantic_disagreement_resumes_with_only_one_tie_breaker_call():
    judge = FakeJudge([True])
    budget = JudgeBudget(1)
    input_sha256 = semantic_judge_input_sha256(
        case_id="",
        question="효과는?",
        candidate="비의 총량이 늘어난다",
        canonical="강수량이 증가한다",
        aliases=["비가 더 많이 온다"],
        judge_model="gpt-5.6-luna",
    )
    decision = grade_candidate(
        question="효과는?",
        candidate="비의 총량이 늘어난다",
        answer_spec=_spec(),
        judge_client=judge,
        judge_model="gpt-5.6-luna",
        judge_budget=budget,
        existing_judge_attempts=[
            _existing_attempt(repeat=1, equivalent=True, input_sha256=input_sha256, reason="first"),
            _existing_attempt(repeat=2, equivalent=False, input_sha256=input_sha256, reason="second"),
            {"repeat": 3, "error": "judge_call_budget_exhausted"},
        ],
    )

    assert decision.verdict == "pass"
    assert decision.path == "semantic_judge_2of3"
    assert budget.used_calls == 1
    assert len(judge.prompts) == 1


def test_complete_semantic_consensus_resumes_without_a_judge_client():
    input_sha256 = semantic_judge_input_sha256(
        case_id="",
        question="효과는?",
        candidate="비의 총량이 늘어난다",
        canonical="강수량이 증가한다",
        aliases=["비가 더 많이 온다"],
        judge_model="gpt-5.6-luna",
    )
    decision = grade_candidate(
        question="효과는?",
        candidate="비의 총량이 늘어난다",
        answer_spec=_spec(),
        judge_model="gpt-5.6-luna",
        existing_judge_attempts=[
            _existing_attempt(repeat=1, equivalent=True, input_sha256=input_sha256, reason="first"),
            _existing_attempt(repeat=2, equivalent=False, input_sha256=input_sha256, reason="second"),
            _existing_attempt(repeat=3, equivalent=True, input_sha256=input_sha256, reason="tie breaker"),
        ],
    )

    assert decision.verdict == "pass"
    assert decision.path == "semantic_judge_2of3_resumed"


def test_semantic_judge_rejects_internally_inconsistent_or_malformed_json():
    class RawJudge:
        def __init__(self, raw):
            self.raw = raw

        def complete(self, messages, *, model=""):
            return self.raw

    for raw in (
        '{"equivalent":true,"contradiction":true,"missingCriticalFacts":[],"reason":"conflict"}',
        '{"equivalent":true,"contradiction":false,"missingCriticalFacts":["조건"],"reason":"missing"}',
        '{"equivalent":true,"contradiction":"false","missingCriticalFacts":[],"reason":"wrong type"}',
        '{"equivalent":true,"contradiction":false,"missingCriticalFacts":[],"reason":"ok","extra":1}',
    ):
        decision = grade_candidate(
            question="효과는?",
            candidate="비의 총량이 늘어난다",
            answer_spec=_spec(),
            judge_client=RawJudge(raw),
            judge_model="gpt-5.6-luna",
            judge_budget=JudgeBudget(2),
        )
        assert decision.verdict == "unresolved"
        assert decision.path == "semantic_judge_unresolved"


def test_semantic_resume_rejects_attempts_bound_to_another_candidate_or_model():
    stale_sha256 = semantic_judge_input_sha256(
        case_id="q1",
        question="효과는?",
        candidate="비가 줄어든다",
        canonical="강수량이 증가한다",
        aliases=["비가 더 많이 온다"],
        judge_model="gpt-5.6-luna",
    )
    decision = grade_candidate(
        case_id="q1",
        question="효과는?",
        candidate="비의 총량이 늘어난다",
        answer_spec=_spec(),
        judge_model="gpt-5.6-luna",
        existing_judge_attempts=[
            _existing_attempt(repeat=1, equivalent=True, input_sha256=stale_sha256),
            _existing_attempt(repeat=2, equivalent=True, input_sha256=stale_sha256),
        ],
    )

    assert decision.verdict == "unresolved"
    assert decision.path == "semantic_judge_not_run"


def test_score_run_filters_exact_case_ids_before_case_limit(tmp_path):
    public = {
        "benchmarkId": "open.fixture.v2",
        "cases": [{"id": "q1", "prompt": "첫째"}, {"id": "q2", "prompt": "둘째"}, {"id": "q3", "prompt": "셋째"}],
    }
    private = {
        "benchmarkId": "open.fixture.v2",
        "answers": [
            {"caseId": "q1", "canonicalAnswer": "a", "aliases": []},
            {"caseId": "q2", "canonicalAnswer": "b", "aliases": []},
            {"caseId": "q3", "canonicalAnswer": "c", "aliases": []},
        ],
    }
    (tmp_path / "q3.json").write_text('{"prediction":"c"}', encoding="utf-8")

    report = score_run(
        public_manifest=public,
        private_manifest=private,
        results_dir=tmp_path,
        case_ids=["q3"],
        max_cases=1,
    )

    assert report["total"] == 1
    assert report["passed"] == 1
    assert report["cases"][0]["caseId"] == "q3"


def test_score_run_does_not_grade_a_quarantined_solver_artifact(tmp_path):
    public = {"benchmarkId": "open.fixture.v2", "cases": [{"id": "q1", "prompt": "답은?"}]}
    private = {
        "benchmarkId": "open.fixture.v2",
        "answers": [{"caseId": "q1", "canonicalAnswer": "정답", "aliases": []}],
    }
    (tmp_path / "q1.json").write_text(
        '{"prediction":"정답","error":"tool_boundary_audit_failed"}', encoding="utf-8"
    )

    report = score_run(public_manifest=public, private_manifest=private, results_dir=tmp_path)

    assert report["passed"] == 0
    assert report["unresolved"] == 1
    assert report["cases"][0]["gradingPath"] == "result_artifact_error"


def test_score_run_excludes_explicit_semantic_rewrite_cases_from_official_total(tmp_path):
    public = {
        "benchmarkId": "open.fixture.v2",
        "cases": [{"id": "ready", "prompt": "진단은?"}, {"id": "rewrite", "prompt": "적절한 것은?"}],
    }
    private = {
        "benchmarkId": "open.fixture.v2",
        "answers": [
            {
                "caseId": "ready",
                "canonicalAnswer": "정답",
                "aliases": [],
                "conversionStatus": "ready_hide_options",
            },
            {
                "caseId": "rewrite",
                "canonicalAnswer": "보기 상대 정답",
                "aliases": [],
                "conversionStatus": "needs_semantic_rewrite",
            },
        ],
    }
    (tmp_path / "ready.json").write_text('{"prediction":"정답"}', encoding="utf-8")
    (tmp_path / "rewrite.json").write_text('{"prediction":"보기 상대 정답"}', encoding="utf-8")

    report = score_run(public_manifest=public, private_manifest=private, results_dir=tmp_path)

    assert report["total"] == 1
    assert report["passed"] == 1
    assert report["excludedSemanticRewriteCases"] == 1
    assert [case["caseId"] for case in report["cases"]] == ["ready"]


def test_score_run_includes_independently_approved_semantic_rewrites(tmp_path):
    public = {
        "benchmarkId": "open.fixture.v2",
        "cases": [{"id": "rewritten", "prompt": "고유하게 다시 작성된 질문은?"}],
    }
    private = {
        "benchmarkId": "open.fixture.v2",
        "answers": [
            {
                "caseId": "rewritten",
                "canonicalAnswer": "정답",
                "aliases": [],
                "conversionStatus": "ready_semantic_rewrite",
            }
        ],
    }
    (tmp_path / "rewritten.json").write_text('{"prediction":"정답"}', encoding="utf-8")

    report = score_run(public_manifest=public, private_manifest=private, results_dir=tmp_path)

    assert report["total"] == 1
    assert report["passed"] == 1
    assert report["excludedSemanticRewriteCases"] == 0
    assert [case["caseId"] for case in report["cases"]] == ["rewritten"]


def test_score_run_combines_disjoint_result_directories_and_rejects_duplicates(tmp_path):
    public = {
        "benchmarkId": "open.fixture.v2",
        "cases": [{"id": "q1", "prompt": "첫째"}, {"id": "q2", "prompt": "둘째"}],
    }
    private = {
        "benchmarkId": "open.fixture.v2",
        "answers": [
            {"caseId": "q1", "canonicalAnswer": "a", "aliases": []},
            {"caseId": "q2", "canonicalAnswer": "b", "aliases": []},
        ],
    }
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "q1.json").write_text('{"prediction":"a"}', encoding="utf-8")
    (second / "q2.json").write_text('{"prediction":"b"}', encoding="utf-8")

    report = score_run(
        public_manifest=public,
        private_manifest=private,
        results_dir=first,
        additional_results_dirs=[second],
    )

    assert report["passed"] == 2
    assert [case["resultPath"] for case in report["cases"]] == [
        str(first / "q1.json"),
        str(second / "q2.json"),
    ]
    (second / "q1.json").write_text('{"prediction":"a"}', encoding="utf-8")
    with __import__("pytest").raises(ValueError, match="duplicate result artifact for q1"):
        score_run(
            public_manifest=public,
            private_manifest=private,
            results_dir=first,
            additional_results_dirs=[second],
        )


def test_existing_swap_judge_override_is_one_case_with_sequential_consensus_budget():
    valid = {
        "requested": True,
        "judge_model": "gpt-5.6-luna",
        "case_ids": ["q1"],
        "max_cases": 1,
        "max_judge_calls": 3,
    }

    validate_single_case_judge_swap_override(**valid)
    validate_single_case_judge_swap_override(
        **{**valid, "max_judge_calls": 1, "resume_judge_report": True}
    )

    for changed in (
        {"judge_model": ""},
        {"case_ids": []},
        {"case_ids": ["q1", "q2"]},
        {"max_cases": 2},
        {"max_judge_calls": 1},
        {"max_judge_calls": 4},
    ):
        with __import__("pytest").raises(ValueError):
            validate_single_case_judge_swap_override(**{**valid, **changed})
