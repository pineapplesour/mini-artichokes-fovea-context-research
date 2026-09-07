import { describe, expect, it } from "vitest";

import { normalizeDisplayMarkdown } from "../lib/markdown-normalize";

describe("normalizeDisplayMarkdown", () => {
  it("repairs split Lawkey headings and bullet-only lines before markdown rendering", () => {
    const broken = [
      "##",
      "가장 같은 사실관계 판례",
      "•",
      "대법원 1985. 12. 24. 선고 85누792 판결: 열쇠 관리 판례",
      "•",
      "대법원 1998. 02. 10. 선고 97다49534 판결: 탄약고 열쇠 판례",
    ].join("\n");

    expect(normalizeDisplayMarkdown(broken)).toBe(
      [
        "## 가장 같은 사실관계 판례",
        "- 대법원 1985. 12. 24. 선고 85누792 판결: 열쇠 관리 판례",
        "- 대법원 1998. 02. 10. 선고 97다49534 판결: 탄약고 열쇠 판례",
      ].join("\n"),
    );
  });

  it("adds a markdown heading marker when a known Lawkey section title arrives without hashes", () => {
    expect(normalizeDisplayMarkdown("가장 같은 사실관계 판례\n• 85누792")).toBe("### 가장 같은 사실관계 판례\n- 85누792");
  });

  it("collapses duplicated heading markers such as '### ## title'", () => {
    expect(normalizeDisplayMarkdown("### ## 유리하게 만들 요소\n*   규정 준수")).toBe("### 유리하게 만들 요소\n*   규정 준수");
  });

  it("renames public Lawkey answer headings defensively at render time", () => {
    expect(normalizeDisplayMarkdown("## 한눈에 보는 결론\n\n내용\n\n## 법조인용 상세 분석")).toBe(
      "## 어렵지 않아요\n\n내용\n\n## 상세 분석",
    );
  });
});
