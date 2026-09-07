import { describe, expect, it } from "vitest";

import {
  extractQuoteBlockCitationLabel,
  extractLeadingQuoteCitation,
  extractQuoteCitationMatch,
  extractStandaloneCitationLabel,
} from "../lib/markdown-citations";
import { parseMarkdownBlocks } from "../lib/markdown-blocks";
import { collectCitationLinkRanges, stripPrecedentIdTokensForDisplay } from "../lib/markdown-citation-links";

describe("MarkdownView parser", () => {
  it("keeps consecutive blockquote lines as one quote without merging with the previous paragraph", () => {
    const blocks = parseMarkdownBlocks("2017고합146 판결\n> 첫째 줄\n> 둘째 줄");

    expect(blocks).toEqual([
      { type: "paragraph", text: "2017고합146 판결" },
      { type: "quote", text: "첫째 줄\n둘째 줄" },
    ]);
  });

  it("treats escaped blockquote markers as quote lines", () => {
    expect(parseMarkdownBlocks("2017고합146 판결\n\\> 첫째 줄\n&gt; 둘째 줄")).toEqual([
      { type: "paragraph", text: "2017고합146 판결" },
      { type: "quote", text: "첫째 줄\n둘째 줄" },
    ]);
  });

  it("recognizes standalone citation paragraphs that should move into quote boxes", () => {
    expect(extractStandaloneCitationLabel("(2011노1493 판결)")).toBe("2011노1493 판결");
    expect(extractStandaloneCitationLabel("**(2022고단2030 판결)**")).toBe("2022고단2030 판결");
    expect(extractStandaloneCitationLabel("(2011노1493 판결).")).toBe("2011노1493 판결");
    expect(extractStandaloneCitationLabel("서울행정법원 2020. 08. 10. 선고 2020구합80325 판결")).toBe("2020구합80325 판결");
    expect(extractStandaloneCitationLabel("(대법원 2017. 11. 29. 선고 2017도9747 판결)")).toBe("2017도9747 판결");
    expect(extractStandaloneCitationLabel("참조 판례 [prd:abc123]")).toBe("참조 판례 [prd:abc123]");
    expect(extractStandaloneCitationLabel("실제 사례에서는 (2011노1493 판결) 이렇게 보았습니다.")).toBeNull();
  });

  it("extracts a quote-box citation from headings or trailing prose", () => {
    expect(extractQuoteCitationMatch("#### (2017고합146 판결)")).toEqual({
      label: "2017고합146 판결",
      leadingText: "",
    });
    expect(extractQuoteCitationMatch("이 묶음은 판단의 핵심입니다. (94다18003 판결)")).toEqual({
      label: "94다18003 판결",
      leadingText: "이 묶음은 판단의 핵심입니다.",
    });
    expect(extractQuoteCitationMatch("에 따르면, 추가로 (74도2314 판결)")).toEqual({
      label: "74도2314 판결",
      leadingText: "에 따르면, 추가로",
    });
    expect(extractQuoteCitationMatch("핵심 판례입니다. (서울행정법원 2020. 08. 10. 선고 2020구합80325 판결)")).toEqual({
      label: "2020구합80325 판결",
      leadingText: "핵심 판례입니다.",
    });
  });

  it("pulls a citation already inside the quote into the quote-box label", () => {
    expect(extractLeadingQuoteCitation("(2017고합146 판결)\n인용 본문입니다.")).toEqual({
      label: "2017고합146 판결",
      quoteText: "인용 본문입니다.",
    });
    expect(extractLeadingQuoteCitation("서울행정법원 2020. 08. 10. 선고 2020구합80325 판결\n인용 본문입니다.")).toEqual({
      label: "2020구합80325 판결",
      quoteText: "인용 본문입니다.",
    });
  });

  it("recognizes a citation-only quote block so the following quote can share one box", () => {
    expect(parseMarkdownBlocks("> (2017고합146 판결)\n\n> 인용 본문입니다.")).toEqual([
      { type: "quote", text: "(2017고합146 판결)" },
      { type: "quote", text: "인용 본문입니다." },
    ]);
    expect(extractQuoteBlockCitationLabel("(2017고합146 판결)")).toBe("2017고합146 판결");
    expect(extractQuoteBlockCitationLabel("(2017고합146 판결)\n인용 본문입니다.")).toBeNull();
  });

  it("hides actual prd-prefixed precedent id tokens while keeping anonymous citations linkable", () => {
    const text = "참조 판례 (LBOX 익명화 [prd:prd-1ff6fe8d3d3020c3])";

    expect(stripPrecedentIdTokensForDisplay(text)).toBe("참조 판례 (LBOX 익명화)");

    const ranges = collectCitationLinkRanges(text, new Map());
    expect(ranges).toEqual([
      {
        start: 0,
        end: text.length,
        precedentId: "prd-1ff6fe8d3d3020c3",
      },
    ]);
  });
});
