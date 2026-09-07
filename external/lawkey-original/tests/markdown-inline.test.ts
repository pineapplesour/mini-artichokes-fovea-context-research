import { describe, expect, it } from "vitest";

import { normalizeInlineMarkdownSource, splitBoldSegments } from "../lib/markdown-inline";

describe("markdown inline parsing", () => {
  it("keeps bold markers when the closing marker is followed by whitespace", () => {
    const source = normalizeInlineMarkdownSource("정리하면 **본인이 직접 증거를 없애는 것** 은 다릅니다.");

    expect(splitBoldSegments(source)).toEqual([
      { text: "정리하면 ", bold: false },
      { text: "본인이 직접 증거를 없애는 것", bold: true },
      { text: " 은 다릅니다.", bold: false },
    ]);
  });

  it("keeps glossary terms bold when followed by a colon", () => {
    const source = normalizeInlineMarkdownSource("**증거인멸**: 범죄의 증거를 없애는 것.");

    expect(splitBoldSegments(source)).toEqual([
      { text: "증거인멸", bold: true },
      { text: ": 범죄의 증거를 없애는 것.", bold: false },
    ]);
  });
});
