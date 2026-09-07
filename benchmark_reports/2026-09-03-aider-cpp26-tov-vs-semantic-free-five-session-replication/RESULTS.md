# C++26 five-session TOV versus semantic-free replication

## Outcome

Across five predeclared new paired whole-track final sessions on the complete
official C++26 track, TOV-minus-semantic-free differences were
`[+1,-1,0,+5,-3]` tasks. TOV won two sessions, tied one, and lost two. Its mean
advantage was +0.4/26 tasks (+1.54 percentage points), with median zero and a
100,000-draw paired whole-session bootstrap 95% interval of
`[-6.92,+11.54]` points. The exact one-sided sign test over four nonzero
differences is `p=.6875`.

The primary five-session test therefore does not establish repeatable TOV
superiority at `.05`. The previously observed single-call C++ contrast
(17/26 versus 13/26) is not a stable estimate of session-level effect.

The sessions do reveal strong crossover. TOV led by five tasks in session 4,
whereas the control led by three in session 5. This is evidence for
trajectory-dependent complementary repairs, not a reliable positive average
effect of semantic-relation instructions.

## Frozen design

The protocol was frozen before any replication call and after the motivating
single-call outcomes were known. It reused immutable Plain, Graph, and
ordinary-repair candidate patches, identical candidate outcomes and bounded
failure traces, the same 13 verified anchors, and the same 13 unresolved
tasks. Exactly five new TOV calls and five new semantic-free calls used
`gpt-5.6-luna/medium`, one complete track per call, with alternating order:

1. TOV then control;
2. control then TOV;
3. TOV then control;
4. control then TOV;
5. TOV then control.

There were no retries, replacements, task deletions, or top-ups. The original
17-versus-13 call was excluded from the primary analysis.

## Session results

| Session | TOV | Semantic-free control | Difference | Full-denominator pp | TOV rescues / harms | Safety |
|---:|---:|---:|---:|---:|---:|:---|
| 1 | **16/26** | 15/26 | +1 | +3.85 | 1 / 0 | TOV generated forbidden `a.out`; control safe |
| 2 | 15/26 | **16/26** | -1 | -3.85 | 1 / 2 | both safe |
| 3 | 18/26 | 18/26 | 0 | 0.00 | 1 / 1 | both safe |
| 4 | **19/26** | 14/26 | +5 | +19.23 | 5 / 0 | both safe |
| 5 | 17/26 | **20/26** | -3 | -11.54 | 1 / 4 | both safe |
| **Mean** | **17.0/26** | **16.6/26** | **+0.4** | **+1.54** | -- | -- |

Across 130 repeated task-session outcomes, TOV scored 85 and control 83, with
9 rescues and 7 harms. The one-sided task-session exact p-value is `.4018`,
but this is descriptive because the same 26 tasks recur and outcomes within a
whole-track call share a trajectory.

A safety sensitivity that excludes the pair containing the TOV `a.out`
violation has differences `[-1,0,+5,-3]`, mean +0.25/26 (+0.96 points), one
win, one tie, and two losses. Its one-sided sign value is `.875` and paired
bootstrap interval is `[-8.65,+13.46]` points. This sensitivity does not alter
the conclusion.

A six-session sensitivity including the motivating call has differences
`[+4,+1,-1,0,+5,-3]`, mean +1.0/26 (+3.85 points), three wins, one tie, and two
losses. It is post hoc and not the primary test.

## Task-level crossover pattern

TOV-only passes across the five new pairs were:

- `yacht` twice;
- `clock`, `kindergarten-garden`, `queen-attack`, `circular-buffer`,
  `complex-numbers`, `crypto-square`, and `robot-name` once each.

Control-only passes were:

- `circular-buffer` twice;
- `yacht`, `clock`, `complex-numbers`, `crypto-square`, and `robot-name` once
  each.

Thus `clock`, `complex-numbers`, `crypto-square`, `robot-name`, and `yacht`
crossed between arms across sessions; `circular-buffer` favored the control
two-to-one; and only `kindergarten-garden` and `queen-attack` were TOV-only
without an observed reverse crossover, each in just one pair. The original
TOV-only set (`complex-numbers`, `kindergarten-garden`, `robot-name`, `yacht`)
was therefore only partly stable.

The per-pair hidden-test oracle union would score `[16,17,19,19,21]`, or
92/130 task-session passes, versus 85 for TOV and 83 for control. This is not a
deployable method score: it uses private outcomes to select between the two
final outputs. It quantifies seven-pass headroom over TOV and supports a future
learned or evidence-only selective verifier, rather than a claim that either
prompt uniformly dominates.

## Integrity and protocol verdict

All ten calls were agent-complete. Every evaluated workspace restored all 26
anchored solution files byte-exactly. All ten ledgers contained exactly the
same 13 unresolved IDs in the frozen order, every control semantic field was
`withheld-by-control`, and all eight within-pair evidence artifacts were
byte-identical in every pair.

TOV session 1 generated a forbidden workspace file, `a.out`, while compiling a
probe. It was neither removed nor excused, so that call is unsafe under the
frozen allowed-path rule. The score remains in the intention-to-treat analysis
and there is no rerun. Because the protocol required every call to pass all
integrity gates, the protocol's promotion condition fails independently of the
nonsignificant accuracy test.

## Compute

| Arm across five final calls | Input tokens | Cached input | Output tokens | Reasoning output | Agent seconds |
|---|---:|---:|---:|---:|---:|
| TOV | 9,104,298 | 8,573,952 | 95,153 | 16,537 | 2,283.360 |
| Semantic-free control | 7,460,079 | 6,950,656 | 95,171 | 16,050 | 2,268.891 |

Call count and caps were matched; realized compute was not exact. TOV used
substantially more input tokens while output, reasoning output, and aggregate
agent seconds were similar. The small mean score difference cannot be
attributed to a lower compute budget for TOV.

## Interpretation

The C++ replication reinforces the Python34 result: verified anchoring is a
stable deterministic floor, while the incremental semantic-relation advantage
is session-trajectory dependent. The complete original TOV system still has a
large realized advantage over one-call Plain and ordinary repair, but the
overlap-specific causal claim must be narrower than the original single-call
contrast suggested.

The most defensible next mechanism is selective rather than universal overlap:
preserve verified anchors, invoke semantic-disagreement falsification only on
unresolved tasks where candidate relations provide discriminative evidence,
and use a separately calibrated verifier to choose between overlap-aware and
direct specification-grounded repairs. The private oracle-union headroom shows
why selection may help; it does not itself validate such a selector.

## Frozen receipts

- Protocol SHA-256:
  `6887286920345430148ae09afc9a92efea4b969af43d9957cd01c014dfe433df`
- Runner SHA-256:
  `31e5077308b6bd7b8a4301d104e07c06863bf43aad87a7f6d1ed6b71cfba7134`
- TOV result SHA-256 values (sessions 1--5):
  `39983a95cb279fd69178f68c73174e68c68d664addd80ba0cd6c75cefd32f56f`,
  `96d95b8609470900dc55c8c35e45e6ad73bae8f114234f7ececc476d29107adc`,
  `02fa300f07717d346a1cce10244c555838cce64196ecc8d961e0d8366ab1a457`,
  `f7286904338164e2487245fa70f734dacff7a6566d062d325047da0dca2ea0be`,
  `1f41d6a55ed8a1d894f4cf0f5908095007aa17edc68508e1956adb051e921dff`.
- Control result SHA-256 values (sessions 1--5):
  `49808f6a3e8a6913bab5936516512b09b5102b2906ffb422d75d4ecda46e032b`,
  `7070c894ca43291b7841e9c7a2440cbb9f073ccfb1e17d0b4188f01ea842b06c`,
  `7a79fe806bf160707f6e3db1a786dd6a163e64e4a9997c8d636fc00cf8d135e4`,
  `3d782615ba38045f1a1c490fc17d850b0545ca62377427cfa93665dfff270bde`,
  `2a9cdc73c8a84fb36c23dd2504937bed2779f731c2c21088fab6137dba3ff241`.

The runner and integrity checks are provenance only, not contributions.
