# Mini Artichokes overlap development evidence — 2026-08-31

## Executive result

On the reused Universal Artichoke keyed-MCQ development cohort, a strict,
fail-closed Luna overlap verifier improved the frozen base from 566/941 to
587/941: 30 rescues, 9 harms, net +21 (+2.232 percentage points), one-sided
exact McNemar p=0.0005325. It also exceeded the prior Universal adjudicator
(503/941) by 84 items.

This is a strong mechanism-development signal, not confirmatory evidence. The
questions, candidate roles, and candidate performance were already known.
The effect was concentrated in psychology (24/30 rescues), and the candidate
trigger was canonical answer agreement rather than independently generated
structured diagnostic overlap.

## Evidence boundary

- Scientific target: improve actual full-denominator problem solving.
- Non-contribution: iteration-51 claim-certificate and infrastructure work.
  Hashing, isolation, receipts, and fail-closed validators are evidence QA,
  not claimed scientific performance.
- Development source: Universal Artichoke CONFIRM-1 questions and d1/d3/d4
  Luna candidates.
- Fixed objective cohort M: 941 keyed MCQs; unmapped outputs count wrong.
- M IDs SHA-256:
  `2e46b0c759c185ed743d1109da1095f17643ebdd3c45bc4a30b08edbeb2b4047`.
- All p-values in this report are development diagnostics.

## Input and mechanism audit

The old normalization path could treat empty/punctuation-only answers and
mathematically opposite free text as equal. The corrected protocol permits a
trigger only when A, B, and C all map unambiguously to canonical MCQ option
IDs and d3=d4!=d1. Free-text rows and ambiguous mappings are excluded.

This reduced the trigger count from 271 to 247:

- 11 non-MCQ/free-text rows removed;
- 13 ambiguous MCQ mappings removed;
- final eligible ID SHA-256:
  `c5fe505dde1c2422dbc9eefc2c71859fe7ccbb801eb372ca1d9e0f789dc69f29`.

All d1/d3/d4 source receipts are accepted, distinct one-call Luna/high
artifacts over the identical question freeze. Candidate, instruction,
manifest, implementation, provenance, and expected-ID hashes are enforced at
dry-run, real-run, and resume time. A dedicated validator rejects synthesis,
ineligible edits, inconsistent gates, and missing/duplicate/out-of-order
ledgers.

## Development arm V3: single strict verifier

Pre-registration:
`experiment_protocols/mini_overlap_confirm1_dev_v3_20260831.md`

| Quantity | Value |
|---|---:|
| Base d1 | 566/941 (60.149%) |
| Strict V3 | 587/941 (62.380%) |
| Net gain | +21 (+2.232 pp) |
| Rescue / harm / wrong-to-wrong | 30 / 9 / 15 |
| SWITCH rows | 54 |
| One-sided exact McNemar vs base | 0.0005325 |
| Existing Universal adjudicator | 503/941 (53.454%) |
| Strict vs Universal net | +84 (+8.927 pp) |
| Elapsed verifier time | 528.584 s |
| Verifier total tokens | 1,623,761 |
| Web searches | 0 |

Hashes:

- freeze: `45d03ecb89c67242e0f98bf522afb524dd758b04f57bd0ab00e71b8909b39ae7`
- receipt: `8d52c3082c313cae26516b6faf38553a636bdffea708c9e3a2365e843a0ac99e`
- answers: `c03291e2fe58a365306433059e0201298a7b4faf25f652b113f0361ad5c03c84`
- decisions: `59e217ebeae26fe4d0e3ce5faa75a2c4282cbf8d62f75abdc11263779b8b1eff`
- trace: `84450113ed71b50641045b3e020d0e35a65872360a7b5ee260accc4baf821ae4`
- thread: `01a05349-32f4-7bb1-96e5-9d95163c522f`

V3 passed integrity, latency, significance, existing-Universal, and
per-benchmark harm guards. It did not pass the deliberately stricter
development safety ceilings H<=4 and H<=floor(R/4). It remains the accuracy
development champion while a more precise selector is developed.

## Development arm V5: two-verifier intersection

Pre-registration:
`experiment_protocols/mini_overlap_2x2_dev_v1_20260831.md`

Validator 2 was a fresh, mutually blinded invocation over the identical
frozen input. It independently switched 25 rows. The mechanical primary
system switched only the intersection of V1 and V2.

| Quantity | V2 alone | V1 ∩ V2 |
|---|---:|---:|
| Score | 579/941 | 579/941 |
| Rescue / harm | 16 / 3 | 15 / 2 |
| Wrong-to-wrong | 6 | 6 |
| Net gain vs base | +13 | +13 |
| One-sided exact McNemar vs base | 0.002213 | 0.001175 |
| SWITCH rows | 25 | 23 |

Agreement over 247 trigger rows:

- both switch 23;
- V1 only 31;
- V2 only 2;
- both keep 191;
- Jaccard 0.4107;
- positive agreement 0.5823;
- Cohen kappa 0.5152.

V5 reduced V1 harm from 9 to 2, but removed 15 rescues while removing 7 harms,
so accuracy fell from 587 to 579. It passed every preregistered safety and
integrity condition but not the precommitted net>=22 / score>=588 accuracy
gate. It is retained as a safety ablation, not selected as the accuracy
winner.

Validator-2 provenance:

- receipt: `74863bf887f6c2d61899da01be416c663ab0e1ba351a78ccb8fb82059f352b81`
- decisions: `feceabb53d4ab3536c91a85ad7319be3070cd2d7e464cf43ed8f4f4139966f2f`
- answers: `dbba16accb0b44a7b1b4ea65aea82abffaa70f9d4494d355b7ef6813d5356724`
- trace: `dadea0e09e358d70ea351e39bdddb8ee39c6f6a352a9177e7c1ce02b7e32f54c`
- thread: `01a05355-fc7d-7e83-ac14-d9d6d3444673`
- elapsed: 580.164 s;
- total tokens: 2,272,468;
- audited general-source searches: 4;
- policy violations: 0.

Combination:

- receipt: `175a930e08218616dba85f6efd1fbb02c67d0eed80de4b46348a91b3cf2e4c87`
- answers: `ec0c22d66d1050a982a5c1117fee504b1696cf0589c1c8c00071c90044188d5d`
- intersection IDs:
  `4bb064f61c68a501eb06acd6f7eb1842f54351505637cb103a4fdb14c6bca6fc`.

## Development arm V7: provenance-blind pairwise falsification

Pre-registration:
`experiment_protocols/mini_overlap_blind_pairwise_dev_v2_20260831.md`

V6 completed its one invocation but was not scored because an ambiguous TIE
contract and a Unicode trace-parser defect prevented protocol acceptance.  V6
remains immutable.  V7 used a new hidden rotation, an explicit unresolved-TIE
contract, and LF-only JSONL trace handling; it received no V6 output.

V7 produced 247/247 structurally valid certificates in one
`gpt-5.6-luna/high` invocation.  The trace contained one thread, zero web
searches, zero network-capable shell commands, and no malformed events.  Its
594.678-second runtime passed the frozen 650-second development ceiling.

The gold-free combiner fixed all policies before private scoring:

| Policy | Switches | Score | Rescue / harm / wrong-to-wrong | Net vs base | One-sided exact McNemar |
|---|---:|---:|---:|---:|---:|
| Base | 0 | 566/941 | 0 / 0 / 0 | 0 | 1.000000 |
| Blind only | 49 | 566/941 | 18 / 18 / 13 | 0 | 0.566030 |
| V3 ∩ blind | 24 | 577/941 | 14 / 3 / 7 | +11 | 0.006363 |
| V3 ∪ blind | 79 | 576/941 | 34 / 24 / 21 | +10 | 0.118524 |
| V3 strict reference | 54 | 587/941 | 30 / 9 / 15 | +21 | 0.000533 |

The intersection is a useful safety result: it reduced harm from 9 to 3 and
improved the base by 1.169 percentage points with a paired exact p=.00636.
However, it removed 16 V3 rescues while removing only 6 V3 harms, leaving it
10 correct answers below V3.  It also lost one point in the Provao domain.
Consequently it did not meet the frozen score>=588, net>=22, and
no-negative-domain gates and was not promoted.  Blind-only proposals outside
V3 were especially unreliable; the union incurred 24 harms.  The supported
mechanistic direction is therefore to use blind falsification only as a veto
on an independently justified V3 switch, not as a source of new switches and
not as a requirement that every valid switch receive a second positive vote.
That veto rule was not among the frozen V7 policies and is posthoc hypothesis
generation only until tested on fresh data.

V7 evidence bindings:

- freeze: `48e6db7da53a7333f63556d700a19b83b70a0f3ba694a3e9c2e320231f86f1e5`
- receipt: `7a79a7e5429428ceec3c0d960f175aa5b2b1b6d8278e311b89533ef86a9b17bf`
- certificates: `50d18f45c0472b9a084a12f9d0d04e081ab3d707cca4612564835c4c3d9fd2ab`
- trace: `032644bcbbd66e87a53afb5f07eab497be11dca71f56b20db490d3c03b5320dc`
- gold-free combination receipt self-hash:
  `063bc390b95ae0520a94e794d0da640a247004625caeb34d517c87d2c4c4bc94`
- private analysis file SHA-256:
  `52bf44acb00cfc31cc97a3639ff7112df8214237b00321780f3af1d8fabfcd28`
- thread: `01a05395-f0b9-7f32-9c0e-ca5837827885`

## Posthoc mechanism diagnosis

Among V3's 54 switches, B and C were byte-identical on all 54 and 53 copied
the option text exactly. This is answer-label agreement routing, not yet
diagnostic overlap.

Manual harm decomposition found:

- 3 reason/action or question-polarity incoherences;
- 5 unsupported factual-memory assertions;
- 1 failure to refute the incumbent and establish challenger uniqueness.

The provenance-blinded, hash-rotated A/B certificate tested in V7 successfully
reduced V3 harm under intersection, but a second positive vote was too
conservative and blind-only additions were unsafe.  The next challenger should
therefore preserve V3 switches by default and remove one only when the blind
certificate explicitly prefers the incumbent.  Any development replay of that
rule is posthoc and can only choose the fixed rule for a fresh reserve; it
cannot become confirmatory evidence itself.

An explicitly posthoc, five-policy diagnostic replay was then run without
writing policy answers.  Its purpose was to select exactly one rule for one
future fresh-holdout test, not to add another development result to the main
comparison:

| Posthoc policy | Switches | Score | Rescue / harm / wrong-to-wrong | Net vs base |
|---|---:|---:|---:|---:|
| V3 strict | 54 | 587/941 | 30 / 9 / 15 | +21 |
| Veto every explicit incumbent preference | 37 | 585/941 | 22 / 3 / 12 | +19 |
| Veto incumbent preference on `SELECT_CORRECT` | 44 | 589/941 | 27 / 4 / 13 | +23 |
| Veto incumbent preference on `SELECT_INCORRECT` | 49 | 584/941 | 26 / 8 / 15 | +18 |
| Veto incumbent preference on `MULTI_SELECT` | 52 | 586/941 | 29 / 9 / 14 | +20 |

The `SELECT_CORRECT`-conditioned veto is therefore frozen as the sole new
holdout hypothesis.  Its two-point development advantage over V3 is not
evidence of superiority: only eight items were discordant between the two
policies (5 versus 3), with two-sided exact McNemar p=.7266.  On the planned
legal outcome prompts, which positively ask for the correct conclusion, this
rule is expected to reduce to an explicit-incumbent veto; that equivalence
must be documented before any outcomes are opened and must not be re-tuned.

Posthoc report self-hash:
`7155de595c0b6dfa53048149e0622a65aeacac219d0f2e995592918942c50bfb`.

## Disjoint confirmatory reserve feasibility

Read-only DB audit shows two complementary reserves are feasible after global
exclusion by canonical ID, normalized court/case number, dedupe keys,
text_hash, split_group, and normalized prompt fingerprints:

1. Main prior-project-disjoint reserve: 1,000 no-arguments cases
   - civil 300 grant + 300 dismissal;
   - tax 200 grant + 200 dismissal.
2. Distribution-matched auxiliary reserve: maximum 414 with-arguments cases.

The 1,000 cases are artifact-disjoint from all seven previous outcome private
sets but date from 2005–2021. They are not a post-training temporal holdout.
Before model calls, the builder must add global semantic-near-duplicate
screening, blind double gold audit, a sealed manifest, and a retrieval
denylist covering the entire test reserve.

## Required confirmatory comparisons

Fresh candidates and structured diagnoses must be generated ex ante. Primary
comparisons must use the same model snapshot, effort, search policy, five-call
and token/cost ceiling:

- plain Luna;
- self-consistency-5;
- four generators plus a blind judge;
- two-cycle critique-revise;
- dual critique without overlap plus blind veto;
- independent retries plus blind aggregate selection;
- proposed diagnostic overlap plus blind falsification.

Report full-denominator accuracy first, then rescue/harm, paired confidence
intervals and exact tests, domain guards, calls/tokens/cost, and end-to-end
wall time. Selective accuracy and oracle pass@k remain secondary diagnostics.
