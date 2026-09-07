import { normalizeDisplayMarkdown } from "./markdown-normalize";

export type MarkdownBlock =
  | { type: "heading"; level: 1 | 2 | 3; text: string }
  | { type: "paragraph"; text: string }
  | { type: "list"; items: string[] }
  | { type: "quote"; text: string }
  | { type: "rule" };

const GLOSSARY_LINE = /^\*\*[^*\n]{1,40}\*\*\s*[:：]/;

export function parseMarkdownBlocks(markdown: string): MarkdownBlock[] {
  const sanitized = normalizeDisplayMarkdown(markdown)
    .replace(/\*\*(\s*\*\*)+/g, "**");
  const lines = sanitized.split(/\n/);
  const blocks: MarkdownBlock[] = [];
  let paragraphBuffer: string[] = [];
  let listBuffer: string[] = [];
  let quoteBuffer: string[] = [];

  const flushParagraph = () => {
    if (!paragraphBuffer.length) return;
    blocks.push({ type: "paragraph", text: paragraphBuffer.join(" ").trim() });
    paragraphBuffer = [];
  };

  const flushList = () => {
    if (!listBuffer.length) return;
    blocks.push({ type: "list", items: [...listBuffer] });
    listBuffer = [];
  };

  const flushQuote = () => {
    if (!quoteBuffer.length) return;
    blocks.push({ type: "quote", text: quoteBuffer.join("\n").trim() });
    quoteBuffer = [];
  };

  for (const rawLine of lines) {
    const line = rawLine
      .trim()
      .replace(/^\\>\s?/, "> ")
      .replace(/^&gt;\s?/i, "> ")
      .replace(/^＞\s?/, "> ");
    if (!line) {
      flushParagraph();
      flushList();
      flushQuote();
      continue;
    }
    if (line === "---") {
      flushParagraph();
      flushList();
      flushQuote();
      blocks.push({ type: "rule" });
      continue;
    }
    if (line.startsWith("#### ")) {
      flushParagraph();
      flushList();
      flushQuote();
      blocks.push({ type: "heading", level: 3, text: line.slice(5).trim() });
      continue;
    }
    if (line.startsWith("### ")) {
      flushParagraph();
      flushList();
      flushQuote();
      blocks.push({ type: "heading", level: 3, text: line.slice(4).trim() });
      continue;
    }
    if (line.startsWith("## ")) {
      flushParagraph();
      flushList();
      flushQuote();
      blocks.push({ type: "heading", level: 2, text: line.slice(3).trim() });
      continue;
    }
    if (line.startsWith("# ")) {
      flushParagraph();
      flushList();
      flushQuote();
      blocks.push({ type: "heading", level: 1, text: line.slice(2).trim() });
      continue;
    }
    if (line.startsWith("* ") || line.startsWith("- ")) {
      flushParagraph();
      flushQuote();
      listBuffer.push(line.slice(2).trim());
      continue;
    }
    if (line.startsWith(">")) {
      flushParagraph();
      flushList();
      quoteBuffer.push(line.slice(1).replace(/^\s+/, ""));
      continue;
    }
    if (GLOSSARY_LINE.test(line)) {
      flushParagraph();
      flushList();
      flushQuote();
      blocks.push({ type: "paragraph", text: line });
      continue;
    }
    flushList();
    flushQuote();
    paragraphBuffer.push(line);
  }

  flushParagraph();
  flushList();
  flushQuote();

  return blocks;
}
