const LAWKEY_SECTION_TITLES = new Set([
  "가장 같은 사실관계 판례",
  "가장 가능성 높은 결론",
  "어렵지 않아요",
  "상세 분석",
  "결론 근거",
  "종합 판단",
  "유리하게 만들 요소",
  "불리하게 만들 요소",
  "관련 참고 판례",
  "참고 판례 목록",
  "선택된 주장",
]);

const LAWKEY_HEADING_RENAMES = new Map([
  ["한눈에 보는 결론", "어렵지 않아요"],
  ["법조인용 상세 분석", "상세 분석"],
]);

function nextNonEmptyLine(lines: string[], startIndex: number): number {
  let index = startIndex;
  while (index < lines.length && !lines[index].trim()) {
    index += 1;
  }
  return index;
}

export function normalizeDisplayMarkdown(markdown: string): string {
  // The Lawkey writer prompt uses `__용어__ = 풀이` underscore-bold to mark
  // glossary terms in the conclusion, but our inline parser only recognizes
  // `**bold**`. Convert `__X__` to `**X**` here so the user sees emphasized
  // terms instead of literal underscores.
  const source = String(markdown || "")
    .replace(/\r\n/g, "\n")
    .replace(/__([^_\n]{1,40})__/g, "**$1**");
  const lines = source.split("\n");
  const normalized: string[] = [];

  for (let index = 0; index < lines.length; index += 1) {
    const original = lines[index] ?? "";
    const line = original.trim();

    const duplicatedHeading = line.match(/^(#{1,6})\s+#{1,6}\s+(.+)$/);
    if (duplicatedHeading) {
      const title = duplicatedHeading[2].trim();
      normalized.push(`${duplicatedHeading[1]} ${LAWKEY_HEADING_RENAMES.get(title) || title}`);
      continue;
    }

    const renamedHeading = line.match(/^(#{1,6})\s+(.+)$/);
    if (renamedHeading) {
      const title = renamedHeading[2].trim();
      const renamed = LAWKEY_HEADING_RENAMES.get(title);
      if (renamed) {
        normalized.push(`${renamedHeading[1]} ${renamed}`);
        continue;
      }
    }

    const headingOnly = line.match(/^(#{1,6})$/);
    if (headingOnly) {
      const nextIndex = nextNonEmptyLine(lines, index + 1);
      if (nextIndex < lines.length) {
        normalized.push(`${headingOnly[1]} ${String(lines[nextIndex] || "").trim()}`);
        index = nextIndex;
        continue;
      }
    }

    const renamedSectionTitle = LAWKEY_HEADING_RENAMES.get(line);
    if (renamedSectionTitle || LAWKEY_SECTION_TITLES.has(line)) {
      normalized.push(`### ${renamedSectionTitle || line}`);
      continue;
    }

    const bullet = line.match(/^•\s*(.*)$/);
    if (bullet) {
      const inlineItem = bullet[1].trim();
      if (inlineItem) {
        normalized.push(`- ${inlineItem}`);
        continue;
      }
      const nextIndex = nextNonEmptyLine(lines, index + 1);
      if (nextIndex < lines.length) {
        normalized.push(`- ${String(lines[nextIndex] || "").trim()}`);
        index = nextIndex;
        continue;
      }
      normalized.push("-");
      continue;
    }

    normalized.push(original);
  }

  return normalized.join("\n").replace(/^\n+|\n+$/g, "");
}
