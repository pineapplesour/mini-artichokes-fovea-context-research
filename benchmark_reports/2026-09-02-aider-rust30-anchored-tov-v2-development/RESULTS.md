# Aider Rust30 anchored TOV-v2 development result

## Outcome

Anchored Try–Semantic-Overlap–Verify (TOV v2) solved 18/30 exercises on the
complete official Aider Rust track. It improved over direct Luna by 13 tasks
(+43.3 percentage points) with 13 rescues and no harms. It also improved over
the matched generic verified-union adjudicator by 2 tasks (+6.7 points), with
two rescues and no harms. All predeclared accuracy and integrity promotion
conditions were met.

This is a development result. The +2 matched-adjudicator contrast is positive
but not individually statistically decisive on 30 tasks; it requires
prospective confirmation on another complete official track.

| Arm | Correct | Accuracy | Agent seconds | Input / cached / output tokens |
|---|---:|---:|---:|---:|
| Plain | 5/30 | 16.7% | 532.755 | 1,641,254 / 1,561,600 / 21,058 |
| Graph | 8/30 | 26.7% | 546.156 | 1,974,747 / 1,890,816 / 20,778 |
| Ordinary repair | 15/30 | 50.0% | 582.179 | 2,852,900 / 2,747,648 / 22,915 |
| Generic verified union | 16/30 | 53.3% | 433.311 | 1,529,424 / 1,433,088 / 18,164 |
| **Anchored TOV v2** | **18/30** | **60.0%** | **543.510** | **2,371,164 / 2,267,136 / 23,136** |

The generic and TOV final arms used the same model and effort, one final call,
the same 30-minute cap, the same verified-union starting patch, and
byte-identical candidate patches, task outcomes, bounded failure traces, and
anchor map. Realized runtime and tokens were not identical: TOV spent 110.2
more agent seconds and 841,740 more input tokens, largely on the mandatory
14-row ledger and completion audits. The comparison is call- and cap-matched,
not exact-token-matched.

## Paired contrasts

| TOV comparison | Rescues / harms | Difference | Exact p, one/two-sided | Paired bootstrap 95% CI |
|---|---:|---:|---:|---:|
| Plain | 13 / 0 | +13/30 (+43.3 pp) | .000122 / .000244 | [+26.7,+60.0] pp |
| Graph | 11 / 1 | +10/30 (+33.3 pp) | .003174 / .006348 | [+13.3,+53.3] pp |
| Ordinary repair | 3 / 0 | +3/30 (+10.0 pp) | .125 / .250 | [0,+23.3] pp |
| Generic verified union | 2 / 0 | +2/30 (+6.7 pp) | .250 / .500 | [0,+16.7] pp |

Exact tests condition on discordant task outcomes. Bootstrap intervals use
200,000 paired whole-task resamples with seed `20260902`. These task-level
statistics are developmental because one official language track is one
realized benchmark suite.

The two matched-adjudicator rescues were `accumulate` and `ocr-numbers`.
Neither matched comparison contained a harm because all 16 task-level verified
anchors were byte-locked in both final arms.

## Mechanism and integrity checks

The three pre-adjudication candidates passed 5, 8, and 15 tasks. Their union
contained 16 distinct verified tasks. A deterministic priority rule
(`ordinary repair`, then `Graph`, then `Plain`) installed the full solution
files from a passing candidate for those tasks. Both final adjudicators began
from that identical union. The adapter restored all anchor bytes after the
model call and before evaluation.

Post-run verification found:

- 16 anchored tasks and 32 anchored solution files;
- zero byte mismatches between selected passing candidates and the evaluated
  TOV workspace;
- byte-identical candidate patches, outcome evidence, and anchor map between
  generic and TOV arms;
- exactly 14 ledger entries, in the same order as the 14 unresolved tasks;
- zero missing or extra ledger task IDs;
- zero forbidden changed paths in all five arms.

The ledger is a decision artifact, not the outcome. Its useful operation is to
compare four semantic fields—fault location, violated invariant,
counterexample class, and edit intent—then use disagreement to trigger
falsification rather than vetoing a repair. A second audit reconciles the
ledger with the final diff. This corrects Java47 v1's manual-merging failure
and the earlier strict-overlap rule that blocked useful repairs.

## Interpretation boundary

The complete TOV system includes multiple candidates, one execution-feedback
repair call, execution-verified anchor preservation, and one semantic-overlap
adjudication call. Therefore the full +43.3-point gain is an end-to-end system
effect, not an overlap-only effect. The isolated development estimate for the
semantic-overlap decision procedure is the +2/30 matched generic contrast.

The benchmark runner, masking, and byte restoration are not paper
contributions. The prospective scientific claim is that verified-anchor
preservation plus semantic-overlap/falsification adjudication can improve a
Codex-centered repair system while avoiding regression of already verified
work.

## Frozen receipts

- Protocol SHA-256:
  `36ec95ab51c64bf7534395015fcb34e13ab8eac0a589166f19ebda3eb54b414d`
- Benchmark freeze SHA-256:
  `0e53b43f5c68f48feb3f01c269de8094e480ffc653a474a0d16ff474e4207cce`
- Runner SHA-256:
  `b9336d6a8503b0c41f9303a3241b0cc039f9c387c9ca1060484e15f37cb2fb93`
- Plain result SHA-256:
  `7d843c32eb24de611d1ca8a66fb36ef2d253f85b98faf822457ea1031df95e8b`
- Graph result SHA-256:
  `54f32ad1e3c17349bc4f199fe06d4fa13b8b4ef8834fbc71057a926797a6b46b`
- Ordinary-repair result SHA-256:
  `3324a4b80925570b22481e5e8720e6bf11175c9f10db064270514619a1b2034c`
- Generic verified-union result SHA-256:
  `4b9445944f277d787a301cff45044973b75fd6aaff9c46de9cd5b9b83d6ba944`
- TOV-v2 result SHA-256:
  `d2dede77b0fe1a3882f8a4f4ddec9ccd78d5a69ecfa490f3ce2c9d9d53b53d72`
- Decision-ledger SHA-256:
  `2397192277d983d8482765d242c150421582ea096e2a4c5f38e4652a907be30a`

The official Java47 v1 result and this Rust30 v2 result remain separate. No
task or language result was deleted or pooled post hoc.
