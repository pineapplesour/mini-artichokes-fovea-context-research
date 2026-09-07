from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal


VerificationStatus = Literal["supported", "contradicted", "ambiguous", "unsupported"]
AuthorityRelation = Literal["direct", "broad", "contradict"]
PropositionKind = Literal["mcq-pair", "advice-claim"]


@dataclass(frozen=True)
class McqTextItem:
    label: str
    text: str


@dataclass(frozen=True)
class McqPair:
    view: str
    explanation: str


@dataclass(frozen=True)
class McqChoice:
    index: int
    text: str
    pairs: tuple[McqPair, ...]


@dataclass(frozen=True)
class KoreanLegalMcq:
    views: tuple[McqTextItem, ...]
    explanations: tuple[McqTextItem, ...]
    choices: tuple[McqChoice, ...]


@dataclass(frozen=True)
class LegalAuthorityStatement:
    id: str
    title: str
    text: str
    concepts: tuple[str, ...]
    relation: AuthorityRelation


@dataclass(frozen=True)
class LegalProposition:
    key: str
    text: str
    concepts: tuple[str, ...]
    kind: PropositionKind


@dataclass(frozen=True)
class LegalPropositionVerdict:
    key: str
    proposition: LegalProposition
    status: VerificationStatus
    authority_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class ChoiceVerdict:
    choice: McqChoice
    supported: bool
    score: int
    verdicts: tuple[LegalPropositionVerdict, ...]


@dataclass(frozen=True)
class LegalPropositionVerification:
    propositions: tuple[LegalProposition, ...]
    proposition_verdicts: tuple[LegalPropositionVerdict, ...]
    choice_verdicts: tuple[ChoiceVerdict, ...]
    recommended_choice: McqChoice | None


@dataclass(frozen=True)
class LegalAnswerRewrite:
    rewritten: bool
    answer_markdown: str


CIRCLED_LABELS = ("Ⓐ", "Ⓑ", "Ⓒ", "Ⓓ", "Ⓔ")
STATUS_SCORE: dict[VerificationStatus, int] = {
    "supported": 3,
    "ambiguous": -1,
    "unsupported": -2,
    "contradicted": -3,
}

DEFAULT_AUTHORITY_STATEMENTS: tuple[LegalAuthorityStatement, ...] = (
    LegalAuthorityStatement(
        id="strict-culpability-art16",
        title="위법성조각사유 전제사실 착오 엄격책임설",
        text="위법성조각사유의 객관적 전제사실 착오를 위법성의 착오 또는 금지착오로 보면 형법 제16조에 따라 정당한 이유가 있을 때 책임이 조각된다.",
        concepts=("putative-defense-justification", "art16-prohibition-error"),
        relation="direct",
    ),
    LegalAuthorityStatement(
        id="negative-elements",
        title="소극적 구성요건표지 이론",
        text="소극적 구성요건표지 이론은 위법성조각사유를 구성요건의 소극적 표지로 보아 구성요건적 고의의 인식대상 사실과 위법성조각사유 전제사실을 구별하지 않는다.",
        concepts=("no-distinction-justification-facts", "negative-elements-theory"),
        relation="direct",
    ),
    LegalAuthorityStatement(
        id="legal-effect-broad-only",
        title="법효과제한설과 고의 이중지위의 관계",
        text="법효과제한설은 구성요건적 고의를 인정하면서 고의범 법효과를 제한한다. 고의의 이중적 지위와 관련될 수는 있으나 직접 대응은 별도로 확인해야 한다.",
        concepts=("legal-effect-limiting", "dual-intent"),
        relation="broad",
    ),
)


def rewrite_answer_with_legal_proposition_guard(
    *,
    source_task: str,
    answer_markdown: str,
    authorities: tuple[LegalAuthorityStatement, ...] = DEFAULT_AUTHORITY_STATEMENTS,
) -> LegalAnswerRewrite:
    """Self-check a user-visible draft when the prompt is a proposition MCQ.

    This is deliberately a final guard, not a replacement for retrieval/writing:
    if the prompt cannot be parsed or no choice has direct support, the original
    answer is returned unchanged.
    """
    if not is_view_explanation_mcq(source_task):
        return LegalAnswerRewrite(rewritten=False, answer_markdown=answer_markdown)
    verification = build_legal_proposition_verification(source_task, authorities)
    recommended = verification.recommended_choice
    if recommended is None:
        return LegalAnswerRewrite(rewritten=False, answer_markdown=answer_markdown)
    supported_choice = next((row for row in verification.choice_verdicts if row.supported), None)
    if supported_choice is None:
        return LegalAnswerRewrite(rewritten=False, answer_markdown=answer_markdown)
    if _draft_already_matches_supported_choice(answer_markdown, supported_choice.choice):
        return LegalAnswerRewrite(rewritten=False, answer_markdown=answer_markdown)
    return LegalAnswerRewrite(
        rewritten=True,
        answer_markdown=render_verification_answer(verification),
    )


def is_view_explanation_mcq(source: str) -> bool:
    text = str(source or "")
    return all(marker in text for marker in ("〈견해〉", "〈설명〉", "선지")) and bool(_PAIR_RE.search(text))


def build_legal_proposition_verification(
    source: str,
    authorities: tuple[LegalAuthorityStatement, ...] = DEFAULT_AUTHORITY_STATEMENTS,
) -> LegalPropositionVerification:
    parsed = parse_korean_legal_mcq(source)
    propositions = _extract_mcq_pair_propositions(parsed)
    verdict_by_key: dict[str, LegalPropositionVerdict] = {
        proposition.key: verify_legal_proposition(proposition, authorities)
        for proposition in propositions
    }
    choice_verdicts: list[ChoiceVerdict] = []
    for choice in parsed.choices:
        verdicts = tuple(verdict_by_key[key] for key in (_pair_key(pair) for pair in choice.pairs) if key in verdict_by_key)
        score = sum(STATUS_SCORE[verdict.status] for verdict in verdicts)
        choice_verdicts.append(
            ChoiceVerdict(
                choice=choice,
                supported=len(verdicts) == len(choice.pairs) and all(verdict.status == "supported" for verdict in verdicts),
                score=score,
                verdicts=verdicts,
            )
        )
    supported_choice = next((row.choice for row in choice_verdicts if row.supported), None)
    recommended_choice = supported_choice
    if recommended_choice is None and choice_verdicts:
        recommended_choice = sorted(choice_verdicts, key=lambda row: (-row.score, row.choice.index))[0].choice
    return LegalPropositionVerification(
        propositions=tuple(propositions),
        proposition_verdicts=tuple(verdict_by_key.values()),
        choice_verdicts=tuple(choice_verdicts),
        recommended_choice=recommended_choice,
    )


def verify_legal_proposition(
    proposition: LegalProposition,
    authorities: tuple[LegalAuthorityStatement, ...],
) -> LegalPropositionVerdict:
    polarity_contradictions = [
        authority for authority in authorities if _contradicts_by_polarity(authority.concepts, proposition.concepts)
    ]
    if polarity_contradictions:
        return LegalPropositionVerdict(
            key=proposition.key,
            proposition=proposition,
            status="contradicted",
            authority_ids=tuple(authority.id for authority in polarity_contradictions),
            reason="같은 법률 쟁점에 대해 반대 결론의 근거가 있다: "
            + ", ".join(authority.title for authority in polarity_contradictions),
        )

    matching = [authority for authority in authorities if _covers_concepts(authority.concepts, proposition.concepts)]
    contradictory = [authority for authority in matching if authority.relation == "contradict"]
    if contradictory:
        return LegalPropositionVerdict(
            key=proposition.key,
            proposition=proposition,
            status="contradicted",
            authority_ids=tuple(authority.id for authority in contradictory),
            reason="근거가 명제와 충돌한다: " + ", ".join(authority.title for authority in contradictory),
        )
    direct = [authority for authority in matching if authority.relation == "direct"]
    if direct:
        return LegalPropositionVerdict(
            key=proposition.key,
            proposition=proposition,
            status="supported",
            authority_ids=tuple(authority.id for authority in direct),
            reason="직접 지지: " + ", ".join(authority.title for authority in direct),
        )
    broad = [authority for authority in matching if authority.relation == "broad"]
    if broad:
        return LegalPropositionVerdict(
            key=proposition.key,
            proposition=proposition,
            status="ambiguous",
            authority_ids=tuple(authority.id for authority in broad),
            reason="관련 근거는 있으나 직접 지지로 확정하지 않음: "
            + ", ".join(authority.title for authority in broad),
        )
    return LegalPropositionVerdict(
        key=proposition.key,
        proposition=proposition,
        status="unsupported",
        authority_ids=(),
        reason="검색된 근거가 이 명제를 직접 지지하지 않는다.",
    )


def render_verification_answer(verification: LegalPropositionVerification) -> str:
    choice = verification.recommended_choice
    if choice is None:
        return ""
    lines = [
        "## 정답",
        "",
        f"정답: {choice.index}번 ({choice.text})",
        "",
        "## 검토",
    ]
    for row in verification.choice_verdicts:
        verdict_text = ", ".join(_render_verdict(verdict) for verdict in row.verdicts)
        if not verdict_text:
            verdict_text = "검증할 명제를 찾지 못했습니다."
        marker = "정답 선택지" if row.choice.index == choice.index else "제외"
        lines.append(f"- {row.choice.index}번 {row.choice.text}: {marker}. {verdict_text}")
    return "\n".join(lines).strip()


def parse_korean_legal_mcq(source: str) -> KoreanLegalMcq:
    views_section = _section_between(source, "〈견해〉", "〈설명〉") or source
    explanations_section = _section_between(source, "〈설명〉", "선지") or source
    choices_section = _section_after(source, "선지") or source
    return KoreanLegalMcq(
        views=tuple(_parse_views(views_section)),
        explanations=tuple(_parse_explanations(explanations_section)),
        choices=tuple(_parse_choices(choices_section)),
    )


def verify_advice_draft_claims(
    draft: str,
    authorities: tuple[LegalAuthorityStatement, ...],
) -> tuple[LegalPropositionVerdict, ...]:
    return tuple(
        verify_legal_proposition(proposition, authorities)
        for proposition in _extract_advice_propositions(draft)
    )


def _extract_mcq_pair_propositions(parsed: KoreanLegalMcq) -> list[LegalProposition]:
    view_map = {item.label: item for item in parsed.views}
    explanation_map = {item.label: item for item in parsed.explanations}
    seen: set[str] = set()
    propositions: list[LegalProposition] = []
    for choice in parsed.choices:
        for pair in choice.pairs:
            key = _pair_key(pair)
            if key in seen:
                continue
            seen.add(key)
            view = view_map.get(pair.view)
            explanation = explanation_map.get(pair.explanation)
            concepts = tuple(
                concept
                for concept in (_classify_mcq_side(view.text if view else ""), _classify_mcq_side(explanation.text if explanation else ""))
                if concept != "unknown"
            )
            propositions.append(
                LegalProposition(
                    key=key,
                    text=f"{pair.view} 견해와 {pair.explanation} 설명이 직접 대응한다.",
                    concepts=concepts,
                    kind="mcq-pair",
                )
            )
    return propositions


def _extract_advice_propositions(draft: str) -> list[LegalProposition]:
    compact = re.sub(r"\s+", "", str(draft or ""))
    mentions_self_evidence = bool(re.search(r"자기|자신|본인", compact)) and bool(re.search(r"증거.*(인멸|없애|없)", compact))
    says_not_punishable = bool(re.search(r"성립하지않|처벌되지않|불가벌|죄가아니", compact))
    says_punishable = bool(re.search(r"죄.*성립|처벌|범죄|유죄", compact)) and not says_not_punishable
    if mentions_self_evidence and says_punishable:
        return [
            LegalProposition(
                key="self-evidence-destruction-punishable",
                text="자기 형사사건 증거를 직접 인멸하면 증거인멸죄가 성립한다.",
                concepts=("self-evidence-destruction", "punishable"),
                kind="advice-claim",
            )
        ]
    if mentions_self_evidence and says_not_punishable:
        return [
            LegalProposition(
                key="self-evidence-destruction-not-punishable",
                text="자기 형사사건 증거를 직접 인멸하는 행위는 원칙적으로 증거인멸죄가 성립하지 않는다.",
                concepts=("self-evidence-destruction", "not-punishable"),
                kind="advice-claim",
            )
        ]
    return []


def _parse_views(section: str) -> list[McqTextItem]:
    return [
        McqTextItem(label=match.group(1), text=_clean_text(match.group(2)))
        for match in re.finditer(r"^\s*([가-힣])\.\s*(.*?)(?=^\s*[가-힣]\.\s*|\Z)", section, flags=re.M | re.S)
        if _clean_text(match.group(2))
    ]


def _parse_explanations(section: str) -> list[McqTextItem]:
    labels = "".join(re.escape(label) for label in CIRCLED_LABELS)
    pattern = rf"^\s*([{labels}])\s*(.*?)(?=^\s*[{labels}]\s*|\Z)"
    return [
        McqTextItem(label=match.group(1), text=_clean_text(match.group(2)))
        for match in re.finditer(pattern, section, flags=re.M | re.S)
        if _clean_text(match.group(2))
    ]


_PAIR_RE = re.compile(r"([가-힣])\s*[-－–]\s*([ⒶⒷⒸⒹⒺA-E])")


def _parse_choices(section: str) -> list[McqChoice]:
    choices: list[McqChoice] = []
    for line in section.splitlines():
        text = line.strip()
        if not text or not _PAIR_RE.search(text):
            continue
        cleaned = re.sub(r"^\s*(?:[0-9]+[.)]|[①②③④⑤])\s*", "", text).strip()
        pairs = tuple(
            McqPair(view=match.group(1), explanation=_normalize_explanation_label(match.group(2)))
            for match in _PAIR_RE.finditer(cleaned)
        )
        if pairs:
            choices.append(McqChoice(index=len(choices) + 1, text=cleaned, pairs=pairs))
    return choices


def _classify_mcq_side(text: str) -> str:
    if re.search(r"정당방위상황", text) and re.search(r"정당한\s*이유", text) and re.search(r"책임을?\s*조각", text):
        return "putative-defense-justification"
    if re.search(r"위법성조각사유", text) and (re.search(r"형법\s*제16조", text) or re.search(r"위법성의\s*착오", text)):
        return "art16-prohibition-error"
    if re.search(r"구성요건적\s*고의", text) and re.search(r"법효과", text) and re.search(r"제한", text):
        return "legal-effect-limiting"
    if re.search(r"고의의\s*이중적\s*지위", text) or re.search(r"책임고의", text):
        return "dual-intent"
    if re.search(r"형법\s*제15조\s*제1항", text) or re.search(r"사실의\s*착오.*유추", text):
        return "article15-analogy"
    if re.search(r"구별하지\s*아니", text) or (
        re.search(r"구성요건적\s*고의의\s*인식\s*대상", text) and re.search(r"위법성조각사유의\s*전제", text)
    ):
        return "no-distinction-justification-facts"
    if re.search(r"소극적\s*구성요건표지", text):
        return "negative-elements-theory"
    return "unknown"


def _render_verdict(verdict: LegalPropositionVerdict) -> str:
    return f"{verdict.key}: {_status_label(verdict.status)} ({verdict.reason})"


def _status_label(status: VerificationStatus) -> str:
    return {
        "supported": "직접 지지",
        "ambiguous": "직접 지지로 확정하지 않음",
        "unsupported": "직접 지지 없음",
        "contradicted": "충돌",
    }[status]


def _draft_already_matches_supported_choice(draft: str, choice: McqChoice) -> bool:
    compact = re.sub(r"\s+", "", str(draft or ""))
    expected = re.sub(r"\s+", "", choice.text)
    has_choice_number = bool(re.search(rf"(정답|답)\s*(?:은|:)?\s*{choice.index}\s*번", draft))
    return expected in compact and has_choice_number


def _covers_concepts(authority_concepts: tuple[str, ...], proposition_concepts: tuple[str, ...]) -> bool:
    if not proposition_concepts:
        return False
    return all(concept in authority_concepts for concept in proposition_concepts)


def _contradicts_by_polarity(authority_concepts: tuple[str, ...], proposition_concepts: tuple[str, ...]) -> bool:
    shared_subject = any(
        concept in authority_concepts
        for concept in proposition_concepts
        if concept not in {"punishable", "not-punishable"}
    )
    if not shared_subject:
        return False
    return (
        "punishable" in proposition_concepts and "not-punishable" in authority_concepts
    ) or (
        "not-punishable" in proposition_concepts and "punishable" in authority_concepts
    )


def _section_between(source: str, start_marker: str, end_marker: str) -> str:
    start = source.find(start_marker)
    if start < 0:
        return ""
    start += len(start_marker)
    end = source.find(end_marker, start)
    if end < 0:
        return source[start:]
    return source[start:end]


def _section_after(source: str, marker: str) -> str:
    found = source.find(marker)
    if found < 0:
        return ""
    return source[found + len(marker):]


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_explanation_label(label: str) -> str:
    if re.fullmatch(r"[A-E]", label):
        index = ord(label) - ord("A")
        return CIRCLED_LABELS[index]
    return label


def _pair_key(pair: McqPair) -> str:
    return f"{pair.view}-{pair.explanation}"
