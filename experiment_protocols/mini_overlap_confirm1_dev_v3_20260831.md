# Mini/Universal Artichoke strict-overlap development experiment v3

## Status and scientific scope

This is a frozen, result-aware **development** experiment. It reuses questions
and candidates whose private benchmark performance is already known. It may
promote or reject this mechanism for a genuinely disjoint confirmatory run,
but its p-values and effect estimates are not publication-confirmatory.

The exact claim tested is:

> Given a historically strong Luna base answer and two separately sampled
> Luna auxiliaries that agree on a different canonical MCQ option, can a
> fail-closed Luna verifier validate only high-precision corrections and
> improve the fixed-denominator score over both the base and the existing
> Universal adjudicator?

This is an answer-agreement routing experiment, not yet a clean test of two
independently generated structured error diagnoses. No diagnostic-overlap
claim may be made from this run alone.

The prompt and implementation were committed as `6180d7c` before the private
aggregate eligibility headroom below was recomputed. They will not be changed
after observing the verifier output.

## Immutable public/runtime inputs

- Campaign: `runs/mini-overlap-confirm1-dev-v3-20260831`
- Protocol: `mini_artichokes_candidate_overlap_adjudication_v2`
- Solver freeze SHA-256: `45d03ecb89c67242e0f98bf522afb524dd758b04f57bd0ab00e71b8909b39ae7`
- Questions SHA-256: `f2d92bbdd6f0ea30693dcd70ff1846f5c0b2fe50e42f1e71705a398cc0ad9d5e`
- Instructions SHA-256: `315803c7777cfd2c7237acca1cee1ae33949b067671cc4e3f5836dc54722656e`
- Overlap manifest SHA-256: `cc3f6130dfcec8326562b1cb3a3f6137502b9bb583a6c8e1965c5906823db5ca`
- Eligible IDs SHA-256: `c5fe505dde1c2422dbc9eefc2c71859fe7ccbb801eb372ca1d9e0f789dc69f29`
- Candidate bundle SHA-256: `f5cca7ed0b8315d8b914743ac84a801e41e1fbd474ac5bb3e3f9fdf80736db5a`
- Base d1 answers: `6f4e50d3e9901b10fbb4cd8db0d7d5e835a234bf63196efe303d8163e6536c95`
- Auxiliary d3 answers: `64b6ac1eda02333ed53f2c3e3c15928533e8af559dde18411697e03937d4bd48`
- Auxiliary d4 answers: `954ba0407d86fa0dc307271b62b45c635409cc78dc995fd225208c5a2459dd1e`
- Candidate provenance digest: `d1d660905ade70783ab8e49ec09defb25b96cd9bad576cee7aca5cadd9809631`
- Existing Universal adjudicator answers: `7c2476d87536d016bb6e1d0189047eb1c390b6b1791bd4baddf56f63635d6518`

All three candidate receipts are accepted one-call `gpt-5.6-luna`, high
reasoning, low verbosity artifacts over the identical question freeze.

The verifier invocation is exactly one complete-file call using:

- `CODEX_HOME=/home/pineapple/.codex-new-account`
- model `gpt-5.6-luna`
- reasoning effort `high`
- verbosity `low`
- service tier `default`
- native web search enabled, matching the source candidate policy
- database, skills, MCP, apps, memory, and multi-agent access disabled
- bubblewrap isolation from private labels and host project files
- timeout `680` seconds

It must process all 1,309 public rows in one invocation. Only 247 MCQ rows are
eligible; all other rows must be copied byte-for-byte from the base. Search
for exam text, answer keys, benchmark IDs, or historical answers is forbidden
and audited.

## Frozen action and acceptance contract

Eligibility is gold-free and requires all three candidates to map
unambiguously to canonical MCQ option IDs, with d3=d4 and d3!=d1.
Free-text/constructed responses and ambiguous option mappings are excluded.

- `VALID + SWITCH`: copy d3 exactly.
- `INVALID + KEEP`: copy d1 exactly.
- `ABSTAIN + KEEP`: copy d1 exactly.
- Any other gate/action pair, missing/duplicate/out-of-order decision, change
  to an ineligible row, synthesized answer, or input/hash mismatch makes the
  artifact incomplete and scientifically unusable.

Only the first accepted verifier artifact is analyzed. An incomplete timeout
or transport artifact is preserved; it is not silently repaired or scored.
Any later challenger must use a new campaign and a new preregistration.

## Frozen private evaluation cohort

The primary denominator is the sorted set of all public MCQ IDs with a
nonempty private `correctOptionId`. Unmapped output is wrong and is never
dropped.

- Fixed cohort M: `941` rows
- Sorted M IDs SHA-256: `2e46b0c759c185ed743d1109da1095f17643ebdd3c45bc4a30b08edbeb2b4047`
- Eligible rows within M: `247`
- Sorted eligible-M IDs SHA-256: `7d3f5a01306fd7e89ba009bc5ea24259aa91f915e57128584a2c503941757bb2`

Known, result-aware development baselines on M:

- base d1: `566/941`
- auxiliary d3: `378/941`
- auxiliary d4: `273/941`
- existing Universal adjudicator: `503/941`
- mechanically switch every eligible row: `484/941` (`39` rescues, `121` harms)

Within the 247 eligible rows, the base is correct on 121, d3 is correct on 39,
at least one of base/d3 is correct on 160, and both are wrong on 87. Thus the
verifier cannot win by treating agreement as truth; it must identify a small,
high-precision subset of the 39 possible rescues while preserving the base.

## Primary paired metrics

Against base d1:

- R: base wrong, strict verifier system correct
- H: base correct, strict verifier system wrong
- delta_base = `(R-H)/941`
- one-sided exact McNemar: `P[Binomial(R+H, .5) >= R]`

Against the existing Universal adjudicator:

- W: strict correct, Universal wrong
- L: strict wrong, Universal correct
- delta_UA = `(W-L)/941`
- the analogous one-sided exact McNemar test

Also report switch count, rescue precision, harm rate, unmapped counts,
eligible-set accuracies, oracle headroom, both-wrong count, invalid/abstain
counts, and per-benchmark rescues/harms.

## Development promotion gate

The mechanism advances to fresh disjoint confirmation only if every condition
below holds:

1. All freeze, provenance, isolation, policy-audit, strict-ledger, and output
   integrity checks pass.
2. Eligible M rows are at least 30 (frozen observed value: 247).
3. Against d1, `R-H >= 5`.
4. `H <= floor(R/4)` and `H <= 4`.
5. One-sided exact McNemar against d1 is `p <= .10`.
6. Against existing Universal, `W-L >= 5` and one-sided `p <= .10`.
7. For every frozen benchmark d,
   `H_d-R_d <= max(1, ceil(.01*n_d))`.
8. Verifier wall time is at most `682.207` seconds. The enforced timeout is
   680 seconds. Combined with the longest source draft (`1117.793` seconds),
   the solver critical path remains below 30 minutes.

These thresholds are development-screening thresholds. A non-promoted arm is
preserved and decomposed into headroom, correlated-agreement, selector
precision, and latency diagnostics; the broader research goal continues with
the next frozen challenger.

## Required confirmatory successor

Even if promoted, this arm requires a new disjoint benchmark, ex-ante base and
auxiliary role assignment, structured independent error diagnoses, a blinded
claim validator, and equal-budget controls (plain Luna, repeated sampling plus
ordinary adjudication, self-consistency, critique-revise, single-auxiliary,
agreement-hidden/placebo, and full overlap gate). Publication claims require
paired 95% confidence intervals above zero, two co-primary one-sided tests at
`p <= .05`, and concordant direction in at least two task families.
