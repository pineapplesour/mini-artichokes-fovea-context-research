import { describe, expect, it } from "vitest";

import {
  parseKoreanLegalMcq,
  runKoreanLegalMcqExperimentSuite,
  solveKoreanLegalMcq,
} from "../lib/exam-mcq-solver";

const MISTAKEN_DEFENSE_PROBLEM = `【문제】 (다툼이 있는 경우 판례에 의함)
甲은 야간에 자신을 계속 뒤따라오다 갑자기 손을 내뻗는 A를 강제추행범으로 오인하고, 이를 막고자 A를 폭행하여 상해를 가하였다. 그런데 실제로 A는 甲의 친구로서 장난을 치기 위해 위와 같은 행동을 한 것이었다. 이 사례의 해결방식에 관한 다음 견해들과 그 설명의 연결로 옳은 것은?
〈견해〉

가. 甲이 정당방위상황으로 잘못 판단한 데에 정당한 이유가 있으면 책임을 조각하려는 견해
나. 甲 행위의 구성요건적 고의를 인정하면서 고의범으로서의 법효과만을 제한하려는 견해
다. 사실의 착오 근거규정(형법 제15조 제1항)을 유추적용하려는 견해
라. 구성요건적 고의의 인식 대상이 되는 사실과 위법성조각사유의 전제되는 사실을 구별하지 아니하는 견해

〈설명〉

Ⓐ '불법'과 '책임'의 두 단계로 범죄체계를 구성한다면, 형법상 위법성조각사유는 소극적 구성요건표지이다.
Ⓑ 위법성조각사유의 객관적 전제사실에 대한 착오는 위법성의 착오(형법 제16조)에 해당한다.
Ⓒ 고의의 이중적 지위를 인정하여 구성요건적 고의와 책임고의를 구분한다.


선지:

가-Ⓑ, 라-Ⓐ
가-Ⓒ, 다-Ⓑ
나-Ⓒ, 라-Ⓐ
나-Ⓑ, 다-Ⓐ
다-Ⓒ, 라-Ⓑ`;

const MISTAKEN_DEFENSE_REORDERED_CHOICES = `【문제】 (다툼이 있는 경우 판례에 의함)
甲은 야간에 자신을 계속 뒤따라오다 갑자기 손을 내뻗는 A를 강제추행범으로 오인하고, 이를 막고자 A를 폭행하여 상해를 가하였다. 그런데 실제로 A는 甲의 친구로서 장난을 치기 위해 위와 같은 행동을 한 것이었다. 이 사례의 해결방식에 관한 다음 견해들과 그 설명의 연결로 옳은 것은?
〈견해〉

가. 甲이 정당방위상황으로 잘못 판단한 데에 정당한 이유가 있으면 책임을 조각하려는 견해
나. 甲 행위의 구성요건적 고의를 인정하면서 고의범으로서의 법효과만을 제한하려는 견해
다. 사실의 착오 근거규정(형법 제15조 제1항)을 유추적용하려는 견해
라. 구성요건적 고의의 인식 대상이 되는 사실과 위법성조각사유의 전제되는 사실을 구별하지 아니하는 견해

〈설명〉

Ⓐ '불법'과 '책임'의 두 단계로 범죄체계를 구성한다면, 형법상 위법성조각사유는 소극적 구성요건표지이다.
Ⓑ 위법성조각사유의 객관적 전제사실에 대한 착오는 위법성의 착오(형법 제16조)에 해당한다.
Ⓒ 고의의 이중적 지위를 인정하여 구성요건적 고의와 책임고의를 구분한다.

선지:

나-Ⓒ, 라-Ⓐ
가-Ⓑ, 라-Ⓐ
가-Ⓒ, 다-Ⓑ
나-Ⓑ, 다-Ⓐ
다-Ⓒ, 라-Ⓑ`;

describe("experimental Korean legal MCQ solver", () => {
  it("parses views, explanations, and choices from a bar-exam style prompt", () => {
    const parsed = parseKoreanLegalMcq(MISTAKEN_DEFENSE_PROBLEM);

    expect(parsed.views.map((item) => item.label)).toEqual(["가", "나", "다", "라"]);
    expect(parsed.explanations.map((item) => item.label)).toEqual(["Ⓐ", "Ⓑ", "Ⓒ"]);
    expect(parsed.choices).toHaveLength(5);
    expect(parsed.choices[0].pairs).toEqual([
      { view: "가", explanation: "Ⓑ" },
      { view: "라", explanation: "Ⓐ" },
    ]);
  });

  it("selects option 1 by requiring direct doctrinal support for each pair", () => {
    const result = solveKoreanLegalMcq(MISTAKEN_DEFENSE_PROBLEM);

    expect(result.answerIndex).toBe(1);
    expect(result.answerText).toBe("가-Ⓑ, 라-Ⓐ");
    expect(result.selectedChoice.pairs).toEqual([
      { view: "가", explanation: "Ⓑ" },
      { view: "라", explanation: "Ⓐ" },
    ]);

    expect(result.pairVerdicts.find((item) => item.key === "가-Ⓑ")?.status).toBe("supported");
    expect(result.pairVerdicts.find((item) => item.key === "라-Ⓐ")?.status).toBe("supported");
    expect(result.pairVerdicts.find((item) => item.key === "나-Ⓒ")?.status).toBe("ambiguous");
  });

  it("compares candidate structures and recommends the stable ambiguity-aware verifier", () => {
    const suite = runKoreanLegalMcqExperimentSuite([
      {
        id: "reported",
        source: MISTAKEN_DEFENSE_PROBLEM,
        expectedAnswerText: "가-Ⓑ, 라-Ⓐ",
      },
      {
        id: "choice-reordered",
        source: MISTAKEN_DEFENSE_REORDERED_CHOICES,
        expectedAnswerText: "가-Ⓑ, 라-Ⓐ",
      },
    ]);

    expect(suite.caseResults).toHaveLength(2);
    expect(suite.recommendedStrategyId).toBe("direct-support-ambiguity");
    expect(suite.stableStrategyIds).toContain("direct-support-ambiguity");

    const semanticAdjacent = suite.strategySummaries.find((item) => item.strategyId === "semantic-adjacent");
    expect(semanticAdjacent?.passed).toBe(0);
    expect(semanticAdjacent?.wrongCases.map((item) => item.answerText)).toEqual(["나-Ⓒ, 라-Ⓐ", "나-Ⓒ, 라-Ⓐ"]);

    const recommended = suite.strategySummaries.find((item) => item.strategyId === "direct-support-ambiguity");
    expect(recommended?.passed).toBe(2);
    expect(recommended?.wrongCases).toEqual([]);
  });
});
