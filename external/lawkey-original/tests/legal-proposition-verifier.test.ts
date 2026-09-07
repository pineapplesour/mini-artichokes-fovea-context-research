import { describe, expect, it } from "vitest";

import {
  buildLegalPropositionVerification,
  selfCheckLegalAnswerDraft,
  verifyAdviceDraftClaims,
  type LegalAuthorityStatement,
} from "../lib/legal-proposition-verifier";

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

const DOCTRINE_AUTHORITY: LegalAuthorityStatement[] = [
  {
    id: "strict-culpability-art16",
    title: "위법성조각사유 전제사실 착오 엄격책임설",
    text: "위법성조각사유의 객관적 전제사실 착오를 위법성의 착오 또는 금지착오로 보면 형법 제16조에 따라 정당한 이유가 있을 때 책임이 조각된다.",
    concepts: ["putative-defense-justification", "art16-prohibition-error"],
    relation: "direct",
  },
  {
    id: "negative-elements",
    title: "소극적 구성요건표지 이론",
    text: "소극적 구성요건표지 이론은 위법성조각사유를 구성요건의 소극적 표지로 보아 구성요건적 고의의 인식대상 사실과 위법성조각사유 전제사실을 구별하지 않는다.",
    concepts: ["no-distinction-justification-facts", "negative-elements-theory"],
    relation: "direct",
  },
  {
    id: "legal-effect-broad-only",
    title: "법효과제한설과 고의 이중지위의 관계",
    text: "법효과제한설은 구성요건적 고의를 인정하면서 고의범 법효과를 제한한다. 고의의 이중적 지위와 관련될 수는 있으나, 문제 문언상 직접 대응은 별도로 확인해야 한다.",
    concepts: ["legal-effect-limiting", "dual-intent"],
    relation: "broad",
  },
];

describe("legal proposition verifier", () => {
  it("self-checks an exam-style answer by verifying propositions against retrieved authority statements", () => {
    const verification = buildLegalPropositionVerification(MISTAKEN_DEFENSE_PROBLEM, DOCTRINE_AUTHORITY);

    expect(verification.recommendedAnswerText).toBe("가-Ⓑ, 라-Ⓐ");
    expect(verification.propositionVerdicts.find((item) => item.key === "가-Ⓑ")?.status).toBe("supported");
    expect(verification.propositionVerdicts.find((item) => item.key === "라-Ⓐ")?.status).toBe("supported");
    expect(verification.propositionVerdicts.find((item) => item.key === "나-Ⓒ")?.status).toBe("ambiguous");

    const check = selfCheckLegalAnswerDraft(
      "정답은 3번입니다. 나-Ⓒ은 직접 대응하고 라-Ⓐ도 직접 대응합니다.",
      verification,
    );

    expect(check.ok).toBe(false);
    expect(check.issues).toContainEqual(
      expect.objectContaining({
        propositionKey: "나-Ⓒ",
        status: "ambiguous",
      }),
    );
    expect(check.recommendedAnswerText).toBe("가-Ⓑ, 라-Ⓐ");
  });

  it("uses the same support/contradiction gate for ordinary precedent-advice conclusions", () => {
    const authority: LegalAuthorityStatement[] = [
      {
        id: "self-evidence-not-punishable",
        title: "자기 형사사건 증거인멸",
        text: "증거인멸죄는 타인의 형사사건 또는 징계사건에 관한 증거를 인멸하는 경우를 말하므로, 자기의 형사사건에 관한 증거를 직접 인멸한 행위는 원칙적으로 증거인멸죄가 성립하지 않는다.",
        concepts: ["self-evidence-destruction", "not-punishable"],
        relation: "direct",
      },
      {
        id: "third-party-instigation-risk",
        title: "증거인멸교사 위험",
        text: "자기의 형사사건에 관한 증거를 인멸하기 위하여 타인을 교사하면 증거인멸교사죄가 성립할 수 있다.",
        concepts: ["third-party-instigation", "punishable"],
        relation: "direct",
      },
    ];

    const check = verifyAdviceDraftClaims(
      "자기 사건 증거라도 없애면 증거인멸죄가 바로 성립합니다.",
      authority,
    );

    expect(check.ok).toBe(false);
    expect(check.issues).toContainEqual(
      expect.objectContaining({
        propositionKey: "self-evidence-destruction-punishable",
        status: "contradicted",
      }),
    );
  });
});
