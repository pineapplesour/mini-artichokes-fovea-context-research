# Aider Go39 recursive-TOV prospective run and transport-replacement sensitivity

## Executive result

On the complete official 39-task Aider Go track, the recursive TOV system was
the highest-scoring tested method at **33/39**. It exceeded Plain Luna by
**16/39 (+41.03 percentage points)** and ordinary execution-feedback repair by
**8/39 (+20.51 points)**. Both comparisons had zero task losses because the
system preserves every evaluator-passing shared anchor: one-sided exact values
are `1.526e-5` and `.003906`, respectively. The paired bootstrap intervals are
`[+25.64,+56.41]` and `[+7.69,+33.33]` points.

This is strong system-level evidence, not evidence that overlap alone adds 20
points. Against the strongest equal-call non-overlap system, the separately
labelled transport-replacement sensitivity was **33/39 versus 31/39**, a net
**+2/39 (+5.13 points)** with three rescues and one harm (`p_one-sided=.3125`,
bootstrap `[-5.13,+15.38]`). The preregistered primary endpoint is not
confirmatory because the original Generic call received no model response and
failed the six-call integrity-promotion gate.

## Benchmark and frozen design

- Source: `Aider-AI/polyglot-benchmark` commit
  `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`.
- Denominator: all 39 official Go exercises; no task selection or removal.
- Model: `gpt-5.6-luna`, medium reasoning, low verbosity.
- Every arm is one whole-track call; no per-task model calls.
- Model workspace contains no private `*_test.go` files or gold `.meta` /
  `.approaches` content. The evaluator has 61 official test files.
- Freeze SHA-256:
  `ebbb01078961617728451d80d4837ef98be4a022184952fb965575784779d061`.
- Original protocol:
  `experiment_protocols/2026-09-03-aider-go39-recursive-tov-prospective-confirmation.md`.
- Transport-replacement sensitivity protocol SHA-256:
  `59ebe70d94af3720ca8403a15f09e21ab679b07101dd857f0687dd86bb503706`.

The candidate floor is the task-wise official-test verified union of Plain,
Graph, and ordinary repair, with fixed priority `ordinary > Graph > Plain`.
Direct, Generic, and TOV start from the same 26 verified byte-locked anchors
and the same 13 unresolved tasks. The non-overlap system is
`candidate floor + Direct + Generic`; the recursive TOV system replaces
Generic with TOV. Both compared systems therefore contain five nominal model
calls and share four calls.

## Complete-track scores

| Arm/system | Passes | Accuracy | Gain over Plain |
|:---|---:|---:|---:|
| Starter | 3/39 | 7.69% | -14 |
| Plain Luna | 17/39 | 43.59% | -- |
| Graph | 16/39 | 41.03% | -1 |
| Ordinary execution-feedback repair | 25/39 | 64.10% | +8 |
| Candidate verified union (Plain/Graph/ordinary) | 26/39 | 66.67% | +9 |
| Semantic-free Direct route | 29/39 | 74.36% | +12 |
| Generic Critic route, valid replacement sensitivity | 29/39 | 74.36% | +12 |
| TOV overlap route | **32/39** | **82.05%** | **+15** |
| Non-overlap Direct∪Generic system | 31/39 | 79.49% | +14 |
| Recursive Direct∪TOV system | **33/39** | **84.62%** | **+16** |

All denominators are 39. `publicPass=false` in raw result objects means that
not every task passed; it does not mean the per-task score is missing.

## What each final route added above the 26-anchor floor

- Direct added three tasks: `matrix`, `octal`, `protein-translation`.
- Generic added three tasks: `matrix`, `react`, `scale-generator`.
- TOV added six tasks: `bottle-song`, `matrix`, `poker`,
  `protein-translation`, `scale-generator`, `two-bucket`.
- Direct∪Generic added five tasks: `matrix`, `octal`,
  `protein-translation`, `react`, `scale-generator`.
- Direct∪TOV added seven tasks: `bottle-song`, `matrix`, `octal`, `poker`,
  `protein-translation`, `scale-generator`, `two-bucket`.

Thus the overlap route produced the largest unresolved-task yield while the
recursive Direct branch preserved `octal`, which TOV alone missed. This is the
intended stabilization mechanism: heterogeneous routes generate complementary
solutions, and the official verifier promotes only passing task bytes.

## Paired comparisons

| Comparison | Scores | Rescues / harms | Net | Exact one-sided | Exact two-sided | Paired bootstrap 95% CI |
|:---|---:|---:|---:|---:|---:|---:|
| TOV vs Direct | 32 vs 29 | 4 / 1 | +3 (+7.69 pp) | .1875 | .3750 | [-2.56,+17.95] pp |
| TOV vs valid Generic replacement | 32 vs 29 | 4 / 1 | +3 (+7.69 pp) | .1875 | .3750 | [-2.56,+17.95] pp |
| Recursive TOV vs non-overlap system | 33 vs 31 | 3 / 1 | +2 (+5.13 pp) | .3125 | .6250 | [-5.13,+15.38] pp |
| Recursive TOV vs Plain | 33 vs 17 | 16 / 0 | +16 (+41.03 pp) | 1.526e-5 | 3.052e-5 | [+25.64,+56.41] pp |
| Recursive TOV vs ordinary repair | 33 vs 25 | 8 / 0 | +8 (+20.51 pp) | .003906 | .007812 | [+7.69,+33.33] pp |

Bootstrap values use 50,000 paired task resamples and seed 20260903. They are
conditional on the realized whole-track calls; there is only one new language
track.

TOV rescued `bottle-song`, `poker`, `protein-translation`, and `two-bucket`
relative to Generic and lost `react`. Relative to Direct it rescued
`bottle-song`, `poker`, `scale-generator`, and `two-bucket` and lost `octal`.
At system level, recursive TOV rescued `bottle-song`, `poker`, and
`two-bucket` relative to Direct∪Generic and lost `react`.

The system comparisons against Plain and ordinary repair are deliberately
reported as system-level outcomes. They are nested, use additional calls, and
therefore do not identify an overlap-specific causal effect. The equal-call
Direct∪TOV versus Direct∪Generic contrast is the relevant component-level
sensitivity and did not meet either `p<.05` or the preregistered +8/39 strong
effect gate.

## The original Generic transport-null event

The fifth preregistered invocation failed after 15.403 seconds with HTTP 404
at both WebSocket and HTTPS Codex endpoints. Its complete event stream has only
`thread.started`, `turn.started`, connection retries, one transport error item,
and `turn.failed`. It contains no model message, reasoning item, tool call,
usage record, or final message. Its apparent 26/39 score is exactly the
deterministic anchor seed, not a Generic model result.

Per the frozen protocol, this makes the original six-call prospective
confirmation fail its integrity-promotion gate. The call was not overwritten
or silently rerun. After TOV results were known, a separate protocol froze one
same-input replacement under candidate ID
`generic_verified_union_transport_replacement_01`. This replacement is useful
only as post-primary sensitivity evidence; it cannot retroactively restore
confirmatory status.

## Integrity audit

- Plain, Graph, ordinary, Direct, replacement Generic, and TOV valid calls all
  exited zero without timeout or forbidden paths.
- Every changed path in the three final routes is a declared Go solution file;
  no test, module, documentation, manifest, or repository file changed.
- The three final routes have byte-identical evidence index, Plain/Graph/
  ordinary patches, all three bounded test-evidence files, seed patch, and
  verified-anchor map.
- Seed patch SHA-256 is
  `6e7ce9080f8b402bce5bbf3ab6cfc20d0d24d2b6acf7a2d7dc12581616ed6e57`.
- Evidence-index SHA-256 is
  `d14301db8b6479467d7c4eea794d3f2850b452b97cd467cf2ec5a2392227f84f`.
- The valid replacement Generic prompt SHA-256 exactly matches the failed
  Generic prompt:
  `8a72a48f567a19b311f3c18d7b13c0a27cf3d47f164ed4bf55535f31e3a24b08`.
- All 26 anchored solution files are byte-exact in Direct, replacement Generic,
  and TOV: 78/78 comparisons pass.
- Direct and TOV ledgers contain exactly the 13 frozen unresolved IDs in frozen
  order. All 13 Direct semantic fields equal `withheld-by-control`.

The official track has a known limitation retained without selection:
`counter` reports `no tests to run`. It remains in all denominators because it
is part of the complete official track.

### Test-covered Go38 sensitivity

Treating `counter` as unverified and excluding it from every arm subtracts the
same one pass from every score. The key scores become Plain 16/38, ordinary
24/38, Direct 28/38, Generic 28/38, TOV 31/38, Direct∪Generic 30/38, and
Direct∪TOV 32/38. Discordant task counts and exact tests are unchanged. Mini
versus Plain is +16/38 (+42.11 pp; bootstrap `[+26.32,+57.89]`), Mini versus
ordinary is +8/38 (+21.05 pp; `[+7.89,+34.21]`), and the equal-call
sensitivity is +2/38 (+5.26 pp; `[-5.26,+15.79]`). Thus the no-test row inflates
absolute scores but does not create any reported between-arm advantage.

## Realized compute

| Arm/system | Input | Cached input | Output | Reasoning output | Agent seconds |
|:---|---:|---:|---:|---:|---:|
| Plain | 1,876,878 | 1,793,280 | 24,160 | 2,179 | 580.4 |
| Graph | 2,705,128 | 2,612,736 | 25,677 | 3,372 | 610.7 |
| Ordinary | 2,312,559 | 2,213,120 | 16,326 | 5,514 | 422.2 |
| Direct | 3,187,198 | 3,066,368 | 20,199 | 3,252 | 529.9 |
| Generic replacement | 2,401,990 | 2,294,528 | 17,214 | 2,930 | 397.8 |
| TOV | 3,883,660 | 3,751,424 | 23,396 | 4,580 | 632.7 |
| Non-overlap five-call system | 12,483,753 | 11,980,032 | 103,576 | 17,247 | 2,541.0 |
| Recursive-TOV five-call system | 13,965,423 | 13,436,928 | 109,758 | 18,897 | 2,775.9 |

The systems are nominal-call matched, not token- or latency-matched. TOV used
1,481,670 more total input tokens than Generic, mostly cached input, 6,182 more
output tokens, and 234.9 more agent seconds. Any efficiency claim would require
a separately frozen compute-matched study.

## Scientific interpretation

The new complete track supports three bounded conclusions:

1. recursive verifier-backed redundancy is highly effective as a system on
   this track and is the top observed method;
2. overlap-aware reasoning is a productive heterogeneous branch, adding six
   tasks above the same anchor floor versus three for either Direct or Generic;
3. the strongest equal-call evidence for overlap-specific superiority remains
   positive but modest and uncertain: +2/39 at system level in the post-primary
   replacement sensitivity.

The paper may truthfully claim a large system advantage over Plain Luna and
ordinary repair, including a +20.5-point full-denominator result on Go39. It
must not claim a 20-point causal effect of semantic overlap, a successful
prospective primary endpoint, a language-population effect, or compute-matched
superiority. Infrastructure and toolchain work are provenance only, not the
scientific contribution.
