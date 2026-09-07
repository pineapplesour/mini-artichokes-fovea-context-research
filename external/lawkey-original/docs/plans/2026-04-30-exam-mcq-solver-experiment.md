# 2026-04-30 Exam MCQ Solver Experiment

## Goal

Create a local-only experimental clone path for Korean legal multiple-choice questions. The production Lawkey service and public BETA-6 flow remain untouched.

## Problem

The reported bar-exam style criminal-law question asks for the correct connection between four doctrinal views and three explanations. Production answered like a legal-advice workflow and model-only probes preferred option 3, while the asserted answer key is option 1: `가-Ⓑ, 라-Ⓐ`.

The failure mode is not only retrieval. Even with legal text available, the solver accepts attractive but contested doctrinal associations without checking the exam's exact view/explanation mapping.

## Approach

Add a pure TypeScript experiment module, not wired into any backend route or UI:

- Parse Korean MCQ prompts into views, explanations, and answer choices.
- Use small doctrine cards that encode identifiable legal principles and exact matching constraints.
- Verify each choice pair as `supported`, `contradicted`, or `ambiguous`.
- Score options by supported pairs, penalizing ambiguous pairs unless there is direct support.
- Return the selected option plus a verification table so future prompt/model experiments can see why an answer won.

## Experiment Matrix

The local harness now compares candidate structures on the reported prompt and on a choice-order variant where the same correct mapping is no longer option 1.

| Strategy | Structure | Result |
| --- | --- | --- |
| `semantic-adjacent` | Treat doctrinally adjacent phrases as direct support. This simulates the model-only failure that overweights `나-Ⓒ`. | Failed both cases, choosing `나-Ⓒ, 라-Ⓐ`. |
| `family-direct` | Use direct family classification and reject different doctrine families. | Passed the current cases, but does not preserve the ambiguity reason for the attractive trap. |
| `direct-support-ambiguity` | Require direct pair support and keep attractive but not directly proven links as `ambiguous`. | Passed both cases and is the recommended structure. |

Recommended production structure, if this is later wired in:

1. Detect exam/MCQ prompt shape before the legal-advice RAG writer.
2. Parse views, explanations, and choices into a structured answer contract.
3. Verify each pair independently against doctrine cards/retrieved legal principles.
4. Score choices from the pair-verdict table, with `ambiguous` separated from `supported`.
5. Render the chosen option plus the verification table, instead of asking the ordinary final writer to produce a consultation answer.

## Corrected Experiment Scope

Do not run or optimize against the whole bar-exam corpus for this task. Lawkey is a legal AI, not a dedicated test-taking product.

The useful experiment loop is narrower:

1. Pick a small number of real failures from the current `정밀 분석` path.
2. Ask the model in natural language, not JSON/test-runner format.
3. Grade the natural-language answer by legal reasoning: did it use the right legal authority/context and distinguish direct support from broad relevance?
4. If a structure finally fixes the legal reasoning failure, then run the focused precedent/legal-RAG gates such as 카톡/유심, 군대 열쇠, 자기증거인멸, and self-fault 교통.

For `job-e7406c6e4439`, natural-language prompting without retrieved doctrine context still failed or treated both 1번 and 3번 as plausible. The working structure was:

- provide a short retrieved legal-doctrine memo as context;
- tell the model to trust that context over its memory;
- have it naturally compare the memo with the problem text;
- grade each connection as directly supported or merely broadly related.

With that structure, the model selected `1번` and explained why `가-Ⓑ` and `라-Ⓐ` directly match, while `나-Ⓒ` is not a direct match under the provided legal memo.

## Unified Verifier Prototype

The current local prototype now separates the common legal-reasoning unit from the exam-specific parser:

- `lib/legal-proposition-verifier.ts`

This module treats both exam choices and ordinary legal-advice conclusions as legal propositions:

- exam proposition example: `가 견해와 Ⓑ 설명이 직접 대응한다`;
- advice proposition example: `자기 형사사건 증거를 직접 인멸하면 증거인멸죄가 성립한다`.

It then compares those propositions with retrieved/extracted authority statements expressed as concept bundles. The authority statements do not name an answer number or choice mapping. They only say which legal concepts are directly supported, broadly related, or contradicted by the retrieved law/precedent/doctrine.

The same verifier currently proves two invariants:

- A draft answer asserting `3번` for `job-e7406c6e4439` is self-checked as unsafe because `나-Ⓒ` is only `ambiguous`, while the verifier recommends `가-Ⓑ, 라-Ⓐ`.
- An ordinary advice draft saying direct self-evidence destruction is punishable is self-checked as contradicted when the authority says direct self-evidence destruction is generally not punishable.

This is the intended product direction: not a separate test-taking AI, but one legal proposition verifier used by both precedent answers and exam-looking legal questions.

## Success Criteria

- The exact reported question returns answer index `1`.
- The selected mapping is `가-Ⓑ, 라-Ⓐ`.
- The tempting `나-Ⓒ` pair is not treated as a supported answer without direct mapping support.
- `npm test -- --run tests/exam-mcq-solver.test.ts` passes.
- Full `npm test` and `npx tsc --noEmit` pass.
- The experiment suite shows at least one failed candidate structure and a stable recommended structure, so the result is not a single hard-coded success.

## Non-Goals

- No production deployment.
- No route/UI integration.
- No replacement of the main RAG/legal-advice pipeline in this step.
