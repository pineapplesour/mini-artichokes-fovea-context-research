import { describe, expect, it } from "vitest";

import {
  getAnalysisModeLabel,
  getVisibleAnalysisModeOptions,
  normalizeAnalysisModeForRole,
} from "../lib/analysis-mode";

describe("analysis mode visibility", () => {
  it("maps ordinary users to beta6 while labeling it as precise analysis", () => {
    expect(normalizeAnalysisModeForRole("beta7", false)).toBe("beta6");
    expect(normalizeAnalysisModeForRole("beta8", false)).toBe("beta6");
    expect(getAnalysisModeLabel("beta6", false)).toBe("정밀 분석");
    expect(getVisibleAnalysisModeOptions(false)).toEqual([
      {
        mode: "beta6",
        title: "정밀 분석",
        description: "판례를 정밀하게 선별해 분석합니다.",
      },
    ]);
  });

  it("keeps beta modes visible only for admin users", () => {
    const options = getVisibleAnalysisModeOptions(true).map((item) => item.mode);

    expect(options).toContain("beta6");
    expect(options).toContain("beta7");
    expect(options).toContain("beta8");
    expect(getAnalysisModeLabel("beta6", true)).toBe("분석 BETA-6");
    expect(getAnalysisModeLabel("beta8", true)).toBe("분석 BETA-8");
  });
});
