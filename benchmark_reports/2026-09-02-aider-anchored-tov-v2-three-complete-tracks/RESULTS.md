# Anchored TOV-v2 across three complete official Aider tracks

## Headline result

Across the complete official Rust30, Python34, and C++26 tracks (90 tasks,
none selected), anchored TOV v2 solved 58/90 tasks (64.4%) versus 15/90
(16.7%) for Plain Luna. The improvement was 43 tasks and +47.8 percentage
points, with 43 paired rescues and no harms.

Against the strongest matched control—generic adjudication over the same
byte-locked verified union, candidate patches, execution outcomes, bounded
failure traces, model, effort, and call cap—TOV solved 58/90 versus 51/90
(56.7%). The matched improvement was 7 tasks and +7.8 points, with seven
rescues and no harms; exact one-sided `p=.0078125`, two-sided `p=.015625`.

| Complete official track | Plain | Ordinary repair | Generic verified union | **TOV v2** | TOV - Plain | TOV - generic |
|---|---:|---:|---:|---:|---:|---:|
| Rust, all 30 | 5 | 15 | 16 | **18** | +13 (+43.3 pp) | +2 (+6.7 pp) |
| Python, all 34 | 6 | 17 | 21 | **23** | +17 (+50.0 pp) | +2 (+5.9 pp) |
| C++, all 26 | 4 | 13 | 14 | **17** | +13 (+50.0 pp) | +3 (+11.5 pp) |
| **All 90** | **15** | **45** | **51** | **58** | **+43 (+47.8 pp)** | **+7 (+7.8 pp)** |

TOV also beat ordinary execution-feedback repair by 13/90 tasks (+14.4
points), 13 rescues and no harms, exact one-sided `p=.000122`. The
track-stratified paired bootstrap 95% intervals were [+37.8,+57.8] points
versus Plain, [+7.8,+22.2] versus ordinary repair, and [+3.3,+13.3] versus
matched generic adjudication (50,000 resamples, seed `20260902`).

## Replication pattern and inferential boundary

The matched TOV effect was positive on every complete track: +2 Rust, +2
Python, and +3 C++. The exact task-level comparison over the 90 disjoint tasks
is significant. The stricter track-level sign test has only three independent
track clusters and is not significant (`3/3`, one-sided `p=.125`). Therefore
the paper should claim a consistent three-track task-level advantage with a
clear cluster-count limitation, not a fully established language-population
effect.

Rust30 was development, Python34 was prospective confirmation, and C++26 was
an unchanged-policy extension frozen after the first two results. The 90-task
aggregation is cumulative evidence, not a single pure confirmatory experiment.
Each component result and protocol remains separately archived.

## What the result identifies

The full +47.8-point Plain advantage belongs to the end-to-end four-call TOV
system: independent Plain and Graph attempts, Graph execution-feedback repair,
byte-exact verified-anchor preservation, and semantic-overlap adjudication.
It is not an overlap-only estimate.

The matched +7.8-point contrast isolates the final decision procedure more
closely. Both final arms receive the same verified anchors and evidence. TOV
adds a mandatory unresolved-task ledger over fault location, violated
invariant, counterexample class, and edit intent; disagreement triggers
falsification rather than a veto, followed by two completion audits. This
produced seven additional repairs with no matched harm across all three
tracks.

The realized final-call cost was not identical: TOV sometimes spent more
runtime or tokens on the ledger and audits. The arms are matched in calls,
model, effort, evidence, starting patch, and budget cap, not exact token count.
Costs must accompany accuracy in the paper.

## Complete-suite and integrity guarantees

- All 30 Rust, 34 Python, and 26 C++ official exercises remained in their
  denominators.
- There were no task-level calls, selective top-ups, result-led exclusions, or
  replacement candidates.
- All final-arm evidence packets and anchor maps were byte-identical within
  each track.
- All evaluated anchors were byte-identical to a candidate that passed the
  complete official task test command.
- Ledger rows exactly matched unresolved tasks: 14 Rust, 15 Python, 13 C++.
- Every arm changed only declared solution files.

The benchmark preparation and evaluation code is provenance. The scientific
claim is the accuracy effect of the anchored TOV decision mechanism.

## Source reports

- `benchmark_reports/2026-09-02-aider-rust30-anchored-tov-v2-development/RESULTS.md`
- `benchmark_reports/2026-09-02-aider-python34-anchored-tov-v2-confirmation/RESULTS.md`
- `benchmark_reports/2026-09-02-aider-cpp26-anchored-tov-v2-extension/RESULTS.md`
