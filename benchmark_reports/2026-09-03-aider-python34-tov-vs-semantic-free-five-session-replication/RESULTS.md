# Python34 five-session TOV versus semantic-free replication

## Outcome

Across five predeclared new paired whole-track final sessions on the same
complete official Python34 track, TOV-minus-semantic-free differences were
`[+4,-2,+2,0,+2]` tasks. TOV won three sessions, tied one, and lost one. Its
mean advantage was +1.2/34 tasks (+3.53 percentage points), median +2/34
(+5.88 points), with a 100,000-draw paired whole-session bootstrap 95% interval
of `[-2.35,+8.24]` points. The exact one-sided sign test over four nonzero
differences is `p=.3125`.

The primary five-session test therefore does not establish repeatable TOV
superiority at `.05`. The previously observed single-call Python contrast
(23/34 versus 19/34) is not a stable estimate of session-level effect.

This is not a failure of the end-to-end anchored system: every final arm starts
from the same 19/34 verified floor. It is direct evidence that the incremental
semantic-relation advantage on the 15 unresolved tasks varies materially by
final-session trajectory.

## Frozen design

The protocol was frozen before any replication call and after the motivating
single-call outcomes were known. It reused immutable Plain, Graph, and ordinary
candidate patches, identical task outcomes and bounded failure traces, the same
19 verified anchors, and the same 15 unresolved tasks. Exactly five new TOV
calls and five new semantic-free calls used `gpt-5.6-luna/medium`, one whole
track per call, with alternating order:

1. TOV then control;
2. control then TOV;
3. TOV then control;
4. control then TOV;
5. TOV then control.

There were no retries, replacements, task deletions, or top-ups. The original
23-versus-19 call was excluded from the primary analysis.

## Session results

| Session | TOV | Semantic-free control | Difference | Full-denominator pp | TOV rescues / harms |
|---:|---:|---:|---:|---:|---:|
| 1 | **24/34** | 20/34 | +4 | +11.76 | 4 / 0 |
| 2 | 21/34 | **23/34** | -2 | -5.88 | 1 / 3 |
| 3 | **23/34** | 21/34 | +2 | +5.88 | 3 / 1 |
| 4 | 23/34 | 23/34 | 0 | 0.00 | 1 / 1 |
| 5 | **22/34** | 20/34 | +2 | +5.88 | 2 / 0 |
| **Mean** | **22.6/34** | **21.4/34** | **+1.2** | **+3.53** | -- |

Across 170 repeated task-session outcomes, TOV scored 113 and control 107,
with 11 rescues and 5 harms. The one-sided task-session exact p-value is
`.1051`, but this is descriptive because the same 34 tasks recur and outcomes
within a whole-track call share a trajectory.

A six-session sensitivity including the motivating call gives differences
`[+4,+4,-2,+2,0,+2]`, four wins, one tie, and one loss. It is not the primary
test and does not rescue the predeclared result.

## Task-level repeat pattern

The original TOV-only tasks were not uniformly stable. Across the five new
sessions, the most repeated TOV rescues were `sgf-parsing` (3), `rest-api` (3),
and `grade-school` (2). `food-chain`, `go-counting`, and `list-ops` contributed
one rescue each. Control-only passes occurred for `go-counting` (2) and once
each for `sgf-parsing`, `list-ops`, and `rest-api`.

This supports a narrower interpretation than the first-call post hoc taxonomy:
interface and semantic-contract tasks are a recurring opportunity, but the
specific task repaired by either final prompt is trajectory dependent.

## Integrity and protocol deviation

All ten calls were agent-complete and safe. Every evaluated workspace restored
all 19 anchored files byte-exactly, all ledgers contained the exact set of 15
unresolved IDs, every control semantic field was `withheld-by-control`, all
within-pair evidence packets were byte-identical, and forbidden changed paths
were zero.

The protocol also required ledger IDs in the frozen unresolved order. Eight of
ten calls met this exact order. TOV session 3 swapped the positions of
`list-ops` relative to `dot-dsl/sgf-parsing` and placed `book-store` after
`hangman`; control session 5 placed `sgf-parsing/list-ops` before `dot-dsl`.
No ID was missing or duplicated, and order has no scoring role, but the strict
manipulation gate was not fully met. All predeclared calls remain in the
intention-to-treat analysis; none is rerun or excluded. Consequently, the
protocol's integrity promotion condition also fails independently of the
nonsignificant sign test.

## Compute

| Arm across five final calls | Input tokens | Cached input | Output tokens | Reasoning output | Agent seconds |
|---|---:|---:|---:|---:|---:|
| TOV | 9,331,229 | 8,803,328 | 96,052 | 19,242 | 2,322.317 |
| Semantic-free control | 8,446,558 | 7,917,312 | 98,411 | 18,509 | 2,357.817 |

Call count and caps are matched; realized compute is not exact. TOV used more
input but fewer output tokens and 35.5 fewer aggregate seconds. No arm dominates
all cost dimensions.

## Interpretation

The repeated study answers the main limitation identified by MAC v11 for one
fixed context: final-stage calls are not stable enough to support a claim that
semantic relations reliably outperform the structured control on Python34.
The positive mean and 3/5 wins are compatible with a modest advantage, but the
interval includes material harm and benefit.

The strongest supported statements remain:

- verified anchoring provides a deterministic 19/34 floor in every final call;
- the complete four-call TOV system substantially exceeds one-call Plain in the
  original full-track study;
- the original 90-task matched TOV gains are conditional on realized calls; and
- overlap-specific session repeatability is unresolved rather than established.

## Frozen receipts

- Protocol SHA-256:
  `9c4623e39a628698c6a61683c1740975823fb301a2792f00bb4c4dc1c672b126`
- Runner SHA-256:
  `31e5077308b6bd7b8a4301d104e07c06863bf43aad87a7f6d1ed6b71cfba7134`
- TOV result SHA-256 values (sessions 1--5):
  `2a342edf8fbfa3ceec719a62d2a28b91143a8c83bc0333134c61ecdde149b239`,
  `9636ed67cf4f6cc6720642523c9611411a1b9cae3ed01f0cfd363a18d5fca95f`,
  `b9ed22dfa77d6e5364d210471252161a002d923f9ea361ec40fe6165d913d6b5`,
  `d436f117d8a3c0cacda091de0147f58ffbd3e126579c0df9d162370664b00771`,
  `341bc0ce78f7aa6ac1cbbc7c9a2dc84724e866bd24f360bf80df9e5a2b6d1b25`.
- Control result SHA-256 values (sessions 1--5):
  `f0a3f3130d7caead779c459afbfc8d2ed11e309b9bb000ba53f15bb9172f0466`,
  `75c80fde324ec0eee912e8f55f960cc0321b9faa4b93149bfd6b36505369d5e4`,
  `08602396e0de9844a3b40f3e06c236b90802bace8e1b872f1a4d18287157bd24`,
  `5759fb5d102cdd01d5db18a8fd0a7ea04a6f2be203e0a316b57e73f8d7e192be`,
  `19463a14904a83f1ca2dfb4d4a980fac1dfdd02ba2085a4f70f6d31a92b5fac4`.

The runner and integrity checks are provenance only, not contributions.
