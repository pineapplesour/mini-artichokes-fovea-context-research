from tools.judge_legal_end_to_end import judge_legal_artifacts


class QueueJudge:
    provider = "fixture_judge"
    default_model = "judge-model"
    decoding = {"temperature": 0}

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def complete(self, messages, *, model="", timeout_seconds=None):
        self.calls.append(messages)
        return self.outputs.pop(0)


def _private():
    return {
        "benchmarkId": "legal.strict.v1",
        "graders": [
            {
                "graderId": "strict-case",
                "primaryTargets": [
                    {"caseNumber": "2024구합1"},
                    {"caseNumber": "2021노2"},
                ],
                "semanticJudge": {
                    "authorityPolicy": "all_primary",
                    "requiredChecks": ["issue", "procedure"],
                    "rubric": ["각 판례 법리를 실질적으로 사용", "사실관계에 적용"],
                },
            }
        ],
    }


def _passing_json():
    return """{
      "overallPass": true,
      "checks": {"issue": true, "procedure": true},
      "authorityUse": [
        {"targetId":"2024구합1","substantivelyUsed":true,"ruleAccurate":true,"factApplied":true},
        {"targetId":"2021노2","substantivelyUsed":true,"ruleAccurate":true,"factApplied":true}
      ],
      "equivalentAuthorityUsed": false,
      "equivalentAuthorityCitation": "",
      "reason": "all requirements met"
    }"""


def test_legal_judge_requires_unanimous_repeated_semantic_passes():
    client = QueueJudge([_passing_json(), _passing_json()])
    artifacts = [{"caseId": "strict-case", "answer": "두 판례 법리를 적용한 답변"}]

    report = judge_legal_artifacts(_private(), artifacts, llm_client=client, model="judge-model", repetitions=2)

    assert report["passed"] == 1
    assert report["cases"][0]["passed"] is True
    assert len(report["cases"][0]["judgments"]) == 2
    assert all("mode" not in str(call).lower() for call in client.calls)


def test_legal_judge_rejects_name_dropping_even_when_model_overall_pass_is_true():
    invalid = """{
      "overallPass": true,
      "checks": {"issue": true, "procedure": true},
      "authorityUse": [
        {"targetId":"2024구합1","substantivelyUsed":true,"ruleAccurate":true,"factApplied":true},
        {"targetId":"2021노2","substantivelyUsed":false,"ruleAccurate":false,"factApplied":false}
      ],
      "reason": "second authority was merely listed"
    }"""
    client = QueueJudge([invalid, invalid])

    report = judge_legal_artifacts(
        _private(),
        [{"caseId": "strict-case", "answer": "2024구합1, 2021노2"}],
        llm_client=client,
        model="judge-model",
        repetitions=2,
    )

    assert report["passed"] == 0
    assert report["cases"][0]["passed"] is False
    assert "authority_not_substantively_used:2021노2" in report["cases"][0]["failures"]
