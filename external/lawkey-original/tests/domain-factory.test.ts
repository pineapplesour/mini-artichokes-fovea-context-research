import { describe, expect, it } from "vitest";

import {
  DOMAIN_PRODUCTS,
  buildDomainAnswerEndpoint,
  buildDomainJobEndpoint,
  buildDomainPalette,
  getDomainProduct,
  getDomainLocaleCopy,
  normalizeDomainLanguage,
} from "../lib/domain-factory";

describe("domain factory metadata", () => {
  it("declares required products and language sets from data", () => {
    expect(Object.keys(DOMAIN_PRODUCTS).sort()).toEqual(["islam", "psychology", "tcm"]);
    expect(getDomainProduct("psychology").languages).toEqual(["ko", "en"]);
    expect(getDomainProduct("tcm").languages).toEqual(["ko", "en"]);
    expect(getDomainProduct("islam").languages).toEqual([
      "en",
      "ko",
      "ar",
      "pa",
      "ur",
      "bn",
      "id",
      "ms",
      "fa",
      "tr",
      "sw",
    ]);
  });

  it("normalizes unsupported languages to product defaults", () => {
    expect(normalizeDomainLanguage("islam", "ar")).toBe("ar");
    expect(normalizeDomainLanguage("islam", "xx")).toBe("en");
    expect(normalizeDomainLanguage("tcm", "")).toBe("ko");
  });

  it("keeps reference visual languages distinct and lightweight", () => {
    expect(getDomainProduct("islam").referenceLayout).toBe("islam-centered-thread");
    expect(getDomainProduct("tcm").referenceLayout).toBe("hanji-consult");
    expect(getDomainProduct("psychology").referenceLayout).toBe("therapeutic-aurora");
    expect(buildDomainPalette("islam")).toMatchObject({
      surface: "#0d2b34",
      accent: "#c9a86b",
      motif: "mihrab-arabesque",
    });
    expect(buildDomainPalette("tcm")).toMatchObject({
      surface: "#fffdf6",
      accent: "#b6543a",
      motif: "paper-grain-celadon",
    });
    expect(buildDomainPalette("psychology")).toMatchObject({
      surface: "#fffdf8",
      accent: "#a14a2b",
      motif: "therapeutic-rings",
    });
  });

  it("declares distinct post-query chat/history chrome per reference layout", () => {
    expect(getDomainProduct("islam")).toMatchObject({
      postQueryWorkspace: {
        mode: "isnad-chat-history",
        railLabel: "Archive",
        evidenceLabel: "Evidence",
      },
    });
    expect(getDomainProduct("tcm")).toMatchObject({
      postQueryWorkspace: {
        mode: "isnad-chat-history",
        railLabel: "문진 기록",
        evidenceLabel: "문헌 근거",
      },
    });
    expect(getDomainProduct("psychology")).toMatchObject({
      postQueryWorkspace: {
        mode: "isnad-chat-history",
        railLabel: "Sessions",
        evidenceLabel: "Evidence",
      },
    });
  });

  it("builds domain endpoints without exposing DB paths to the client", () => {
    expect(buildDomainJobEndpoint("islam")).toBe("/api/domain/islam/jobs");
    expect(buildDomainAnswerEndpoint("psychology")).toBe("/api/domain/psychology/answer");
    const serialized = JSON.stringify(DOMAIN_PRODUCTS);
    expect(serialized).not.toContain("sqlite");
    expect(serialized).not.toContain("/workspace");
  });

  it("localizes workspace labels from data instead of fixed English copy", () => {
    expect(getDomainLocaleCopy("islam", "ar")).toMatchObject({
      direction: "rtl",
      askLabel: "اسأل",
      answerLabel: "إجابة موثقة",
      sourcesLabel: "المصادر",
    });
    for (const language of ["ko", "ar", "pa", "ur", "bn", "id", "ms", "fa", "tr", "sw"]) {
      const copy = getDomainLocaleCopy("islam", language);
      expect(copy.answerLabel).not.toBe("Grounded answer");
      expect(copy.emptyAnswer).not.toBe("Source-grounded response will appear here.");
      expect(copy.queryPlaceholder).not.toBe("Ask a source-grounded question.");
    }
    expect(getDomainLocaleCopy("tcm", "ko").askLabel).toBe("묻기");
    expect(getDomainLocaleCopy("psychology", "en").safetyLabel).toBe("Safety boundary");
  });
});
