import { Fragment, useMemo } from "react";
import { StyleSheet, Text, View } from "react-native";

import { theme } from "../../constants/theme";
import { parseMarkdownBlocks, type MarkdownBlock } from "../../lib/markdown-blocks";
import {
  buildPrecedentLookup,
  collectCitationLinkRanges,
  stripPrecedentIdTokensForDisplay,
} from "../../lib/markdown-citation-links";
import { extractLeadingQuoteCitation, extractQuoteBlockCitationLabel, extractQuoteCitationMatch } from "../../lib/markdown-citations";
import { normalizeInlineMarkdownSource, splitBoldSegments } from "../../lib/markdown-inline";
import { LawkeyLogo } from "./lawkey-logo";

type PrecedentRef = {
  precedentId: string;
  caseNumber?: string;
  alternatePrecedentIds?: string[];
};

type MarkdownViewProps = {
  markdown: string;
  mode?: "question" | "document" | "plain";
  precedents?: PrecedentRef[];
  onOpenPrecedent?: (precedentId: string, quoteText?: string) => void;
  hideHeader?: boolean;
  title?: string;
};

// Build a stable DOM-anchor id from a heading text. The demo controller
// scrolls to specific headings by mapping anchor strings → slugs and looking
// the element up via document.getElementById on web.
export function slugifyHeading(text: string): string {
  return String(text || "")
    .normalize("NFKD")
    .replace(/[#`*_~]/g, "")
    .replace(/[\s ]+/g, "-")
    .replace(/[^\p{L}\p{N}\-]/gu, "")
    .toLowerCase()
    .slice(0, 80);
}

export function MarkdownView({ markdown, mode = "question", precedents, onOpenPrecedent, hideHeader, title }: MarkdownViewProps) {
  const blocks = parseMarkdownBlocks(markdown);
  const precedentLookup = useMemo(() => buildPrecedentLookup(precedents), [precedents]);
  const inline = (text: string, keyPrefix: string, targetQuoteText?: string) =>
    renderInline(text, keyPrefix, precedentLookup, onOpenPrecedent, targetQuoteText);
  const quoteCitationFor = (block: MarkdownBlock | undefined) => {
    if (block?.type === "paragraph" || block?.type === "heading") {
      return extractQuoteCitationMatch(block.text)?.label || null;
    }
    if (block?.type === "quote") {
      return extractQuoteBlockCitationLabel(block.text);
    }
    return null;
  };

  return (
    <View style={styles.shell}>
      <View style={styles.page}>
        {hideHeader ? null : (
          <View style={styles.docHeader}>
            <View>
              <Text style={styles.docEyebrow}>Lawkey AI</Text>
              <Text style={styles.docTitle}>
                {title || (mode === "document" ? "문서 초안" : "분석 결과")}
              </Text>
            </View>
            <LawkeyLogo compact />
          </View>
        )}
        {blocks.map((block, index) => {
          if (block.type === "rule") {
            return <View key={`rule-${index}`} style={styles.rule} />;
          }
          if (block.type === "heading") {
            const nextBlock = blocks[index + 1];
            const nextQuote = nextBlock?.type === "quote" ? nextBlock.text : undefined;
            const quoteCitation = nextQuote ? extractQuoteCitationMatch(block.text) : null;
            const headingText = quoteCitation ? quoteCitation.leadingText : block.text;
            if (quoteCitation && !headingText) {
              return null;
            }
            const headingStyles: Array<object> = [styles.headingBase];
            if (block.level === 1) headingStyles.push(styles.headingOne);
            if (block.level === 2) headingStyles.push(styles.headingTwo);
            if (block.level === 3) headingStyles.push(styles.headingThree);
            const anchorId = `lk-h${block.level}-${slugifyHeading(headingText)}`;
            return (
              <Text key={`heading-${index}`} nativeID={anchorId} style={headingStyles}>
                {inline(headingText, `heading-${index}`)}
              </Text>
            );
          }
          if (block.type === "list") {
            return (
              <View key={`list-${index}`} style={styles.list}>
                {block.items.map((item, itemIndex) => (
                  <View key={`item-${itemIndex}`} style={styles.listItem}>
                    <Text style={styles.listBullet}>•</Text>
                    <Text style={styles.listText}>{inline(item, `item-${index}-${itemIndex}`)}</Text>
                  </View>
                ))}
              </View>
            );
          }
          if (block.type === "quote") {
            const previousBlock = blocks[index - 1];
            const nextBlock = blocks[index + 1];
            if (extractQuoteBlockCitationLabel(block.text) && nextBlock?.type === "quote") {
              return null;
            }
            const citationLabel = quoteCitationFor(previousBlock);
            const leadingQuoteCitation = citationLabel ? null : extractLeadingQuoteCitation(block.text);
            const displayCitationLabel = citationLabel || leadingQuoteCitation?.label || null;
            const quoteText = leadingQuoteCitation?.quoteText || block.text;
            return (
              <View key={`quote-${index}`} style={styles.quote}>
                {displayCitationLabel ? (
                  <Text style={styles.quoteCitation}>
                    {inline(displayCitationLabel, `quote-citation-${index}`, quoteText)}
                  </Text>
                ) : null}
                <Text style={styles.quoteText}>{inline(quoteText, `quote-${index}`)}</Text>
              </View>
            );
          }
          const nextBlock = blocks[index + 1];
          const nextQuote = nextBlock?.type === "quote" ? nextBlock.text : undefined;
          const quoteCitation = nextQuote ? extractQuoteCitationMatch(block.text) : null;
          if (quoteCitation && !quoteCitation.leadingText) return null;
          const paragraphText = quoteCitation ? quoteCitation.leadingText : block.text;
          return (
            <Fragment key={`paragraph-${index}`}>
              <Text style={styles.paragraph}>{inline(paragraphText, `paragraph-${index}`)}</Text>
            </Fragment>
          );
        })}
      </View>
    </View>
  );
}

function renderInline(
  text: string,
  keyPrefix: string,
  precedentLookup: Map<string, string>,
  onOpenPrecedent?: (precedentId: string, quoteText?: string) => void,
  targetQuoteText?: string,
) {
  const source = normalizeInlineMarkdownSource(String(text || ""));
  const segments = splitBoldSegments(source).filter((s) => s.text.length > 0);

  const nodes: React.ReactNode[] = [];
  let nodeIndex = 0;
  for (const segment of segments) {
    const baseStyle = segment.bold ? styles.boldInline : undefined;
    const cleanText = segment.text.replace(/\*\*/g, "");
    if (!cleanText) continue;
    if (precedentLookup.size === 0) {
      nodes.push(
        <Text key={`${keyPrefix}-n-${nodeIndex++}`} style={baseStyle}>
          {cleanText}
        </Text>,
      );
      continue;
    }
    // Detect full citation envelopes `(법원 ... 사건번호 판결)` and link
    // the ENTIRE envelope (parens included) to the precedent — not just
    // the bare case number. This makes the clickable area more discoverable
    // and matches user expectation of "the whole citation is the link".
    const linkRanges = collectCitationLinkRanges(cleanText, precedentLookup);
    let cursor = 0;
    for (const range of linkRanges) {
      if (range.start > cursor) {
        nodes.push(
          <Text key={`${keyPrefix}-n-${nodeIndex++}`} style={baseStyle}>
            {stripPrecedentIdTokensForDisplay(cleanText.slice(cursor, range.start))}
          </Text>,
        );
      }
      // Strip `[prd:xxx]` token from displayed link text (the token is
      // metadata used to resolve the precedent_id, never user-visible).
      const linkText = stripPrecedentIdTokensForDisplay(cleanText.slice(range.start, range.end));
      if (range.precedentId && onOpenPrecedent) {
        nodes.push(
          <Text
            key={`${keyPrefix}-n-${nodeIndex++}`}
            style={[baseStyle, styles.linkInline]}
            onPress={() => onOpenPrecedent(range.precedentId!, targetQuoteText)}
            accessibilityRole="link"
          >
            {linkText}
          </Text>,
        );
      } else {
        nodes.push(
          <Text key={`${keyPrefix}-n-${nodeIndex++}`} style={baseStyle}>
            {linkText}
          </Text>,
        );
      }
      cursor = range.end;
    }
    if (cursor < cleanText.length) {
      nodes.push(
        <Text key={`${keyPrefix}-n-${nodeIndex++}`} style={baseStyle}>
          {stripPrecedentIdTokensForDisplay(cleanText.slice(cursor))}
        </Text>,
      );
    }
  }
  return nodes;
}

const styles = StyleSheet.create({
  shell: {
    borderWidth: 0,
    borderColor: "transparent",
    borderRadius: 0,
    backgroundColor: "#ffffff",
    padding: 0,
  },
  page: {
    borderWidth: 0,
    borderColor: "transparent",
    borderRadius: 0,
    backgroundColor: "#ffffff",
    paddingHorizontal: 0,
    paddingVertical: 0,
    gap: 10,
    shadowOpacity: 0,
  },
  docHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingBottom: 18,
    marginBottom: 8,
    borderBottomWidth: 1,
    borderBottomColor: "#efefef",
  },
  docEyebrow: {
    color: "#667085",
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 1.1,
    textTransform: "uppercase",
    marginBottom: 4,
  },
  docTitle: {
    color: theme.colors.text,
    fontFamily: theme.fonts.serif,
    fontSize: 18,
    fontWeight: "700",
  },
  rule: {
    height: 1,
    backgroundColor: theme.colors.line,
    marginVertical: 10,
  },
  headingBase: {
    color: theme.colors.text,
    fontFamily: theme.fonts.serif,
    fontWeight: "700",
  },
  headingOne: {
    fontSize: 30,
    lineHeight: 40,
    marginTop: 4,
    marginBottom: 6,
  },
  headingTwo: {
    fontSize: 23,
    lineHeight: 32,
    marginTop: 22,
    marginBottom: 4,
  },
  headingThree: {
    fontSize: 19,
    lineHeight: 28,
    marginTop: 18,
    marginBottom: 2,
  },
  paragraph: {
    color: theme.colors.text,
    fontSize: 15,
    lineHeight: 27,
  },
  boldInline: {
    fontWeight: "800",
  },
  linkInline: {
    color: "#0a4ea0",
    textDecorationLine: "underline",
  },
  list: {
    gap: 8,
    marginVertical: 4,
  },
  listItem: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 10,
  },
  listBullet: {
    color: theme.colors.text,
    fontSize: 15,
    lineHeight: 24,
  },
  listText: {
    flex: 1,
    color: theme.colors.text,
    fontSize: 15,
    lineHeight: 24,
  },
  quote: {
    borderWidth: 1,
    borderColor: "#ead9b9",
    borderLeftWidth: 4,
    borderLeftColor: "#9f6a12",
    borderRadius: 8,
    backgroundColor: "#fffaf0",
    paddingHorizontal: 13,
    paddingVertical: 11,
    marginVertical: 7,
  },
  quoteCitation: {
    color: "#61410f",
    fontSize: 13,
    lineHeight: 20,
    fontWeight: "800",
    marginBottom: 6,
  },
  quoteText: {
    color: "#1f1b14",
    fontSize: 14,
    lineHeight: 24,
  },
});
