# Mini Artichokes: fresh MMLU-Pro confirmation and replication

## Result in one sentence

On two disjoint, category-proportional 1,000-row samples from the official
MMLU-Pro test set, the unchanged support-aware selective arbitration policy
(OJ3) scored 1,214/2,000 (60.70%) versus 1,187/2,000 (59.35%) for a direct
one-call Luna draw (D1): +27 correct, +1.35 percentage points, 33 rescues and
6 harms, one-sided exact McNemar p=7.15e-6, with a 20,000-sample paired
bootstrap 95% interval of [+0.75, +1.95] percentage points. This rejects the
pre-frozen headline null at the conservative two-look alpha=.025.

## Frozen arms

- D1: one complete-file `gpt-5.6-luna/high` draw.
- D2 and D3: two additional independent complete-file draws.
- SC3: canonical three-draw majority, with D1 fallback.
- Conflict trigger: mapped `D2 = D3 != D1`, computed without gold.
- GJ3: an anonymous judge sees the two existing candidates on conflicts.
- OJ3: the same anonymous judge arm, IDs, candidates, role rotation, model,
  effort, and call budget as GJ3, plus only the mechanical 1-versus-2 support
  count and an explicit warning that consensus is not proof.
- Non-conflicts and invalid judge choices retain D1. Judges cannot synthesize
  a third answer.

The first cohort was scored before replication 2 was generated. Replication 2
used the next disjoint category-proportional SHA ranks, with no policy or
prompt change. The public ID intersection is zero.

## Accuracy and paired comparisons

| Arm | Cohort 1 | Replication 2 | Pooled 2,000 |
|---|---:|---:|---:|
| D1 direct Luna | 597 | 590 | 1,187 (59.35%) |
| D2 | 145 | 607 | 752 (37.60%) |
| D3 | 587 | 586 | 1,173 (58.65%) |
| SC3 | 596 | 613 | 1,209 (60.45%) |
| GJ3 matched generic judge | 600 | 611 | 1,211 (60.55%) |
| OJ3 support-aware judge | **601** | **613** | **1,214 (60.70%)** |

| Pooled comparison | Rescue / harm | Difference | One-sided exact p | Paired bootstrap 95% CI |
|---|---:|---:|---:|---:|
| OJ3 vs D1 | 33 / 6 | +27 (+1.35 pp) | **7.15e-6** | **[+0.75, +1.95] pp** |
| OJ3 vs SC3 | 7 / 2 | +5 (+0.25 pp) | .08984 | [-0.05, +0.55] pp |
| OJ3 vs GJ3 | 6 / 3 | +3 (+0.15 pp) | .25391 | [-0.15, +0.45] pp |
| SC3 vs D1 | 35 / 13 | +22 (+1.10 pp) | .001044 | [+0.45, +1.80] pp |
| GJ3 vs D1 | 29 / 5 | +24 (+1.20 pp) | 1.93e-5 | [+0.65, +1.80] pp |

The frozen fixed sequence at alpha=.025 rejects OJ3>D1, reaches but does not
reject OJ3>SC3, and therefore does not formally reach OJ3>GJ3. Accordingly,
the confirmatory claim is a statistically significant improvement over direct
Luna. OJ3 has the highest pooled point estimate, but its incremental advantage
over the strong three-call majority and matched four-call generic judge is not
statistically established.

Replication 2 independently supports the direct-Luna effect: OJ3 613/1,000
versus D1 590/1,000, 28 rescues and 5 harms, p=3.31e-5, paired bootstrap 95%
CI [+1.2, +3.5] pp. Cohort 1 was directionally consistent but underpowered
because only 14 conflicts were eligible: +4, 5 rescues and 1 harm, p=.1094.

## Descriptive mechanism diagnostic

Across the 68 gold-free conflicts (3.4% of 2,000 rows):

- D1/base was correct on 13/68; the two-draw consensus was correct on 35/68;
  both were wrong on the remaining 20.
- SC3 therefore gained 22 net correct over D1 on conflicts.
- OJ3 selected consensus 52 times and base 16 times, scoring 40/68. Relative
  to always following consensus, the 16 base-retention decisions contained 7
  base wins, 2 consensus wins, and 7 cases where both candidates were wrong:
  +5 net correct.
- GJ3 selected consensus 47 times and base 21 times, scoring 37/68.
- OJ3 and GJ3 chose different candidates on 13 cases. OJ3 won 6, GJ3 won 3,
  and both candidates were wrong on 4, yielding OJ3's +3 net point estimate.

These are descriptive, not a separate confirmatory test. They support a
limited mechanism: independent agreement is useful on this benchmark, while
anonymous arbitration can retain the base answer on a small subset that
reduces consensus harms. They do not support treating overlap as truth or
claiming a significant advantage of the support annotation over a matched
generic judge.

## Compute disclosure

| System | Semantic calls per cohort | Total tokens across both cohorts | Relative to D1 |
|---|---:|---:|---:|
| D1 | 1 | 13,009,321 | 1.00x |
| SC3 | 3 | 45,056,433 | 3.46x |
| GJ3 | 4 | 45,787,649 | 3.52x |
| OJ3 | 4 | 45,973,780 | 3.53x |

The selective OJ3 stage itself consumed 917,347 tokens across 68 conflict
cases, 2.04% beyond the three-draw SC3 total. OJ3 is compute-matched to GJ3,
not to D1. With D1-D3 parallelized, observed OJ3 critical paths were 1,820.7 s
and 1,935.3 s for the two cohorts, versus 1,375.1 s and 1,101.9 s for D1.
These costs must accompany the accuracy result; infrastructure is not a
scientific contribution.

## Evidence boundary

- The prior 941-row Universal development set remains development evidence:
  strict V3 improved 566 to 587 (+21; 30 rescues, 9 harms; one-sided exact
  McNemar p=.0005325).
- The fresh balanced Korean legal outcome reserve is a negative boundary
  condition: overlap-aware judgment underperformed direct Luna there. Partial
  fact patterns did not make mechanical answer agreement informative.
- Neither prior result enters the fresh 2,000-row MMLU-Pro pooled test.
- All primary accuracy claims must remain on the full denominator with
  unmapped outputs counted wrong. No row deletion, category exception,
  post-score remapping, or additional cohort is permitted.

Canonical pooled artifact: `score.json`, SHA-256
`bdf7e36abcf05b8a05d921a259590b919f54da2b7a1658dcc4057acabc905fec`.
