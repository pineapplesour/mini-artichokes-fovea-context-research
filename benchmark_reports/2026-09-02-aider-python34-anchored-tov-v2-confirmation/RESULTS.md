# Aider Python34 anchored TOV-v2 confirmation

## Confirmatory outcome

The unchanged anchored TOV-v2 policy solved 23/34 exercises on the complete
official Aider Python track. It beat Plain Luna by 17 tasks (+50.0 percentage
points) and the matched generic verified-union adjudicator by 2 tasks (+5.9
points), with no harms in either contrast. It met every predeclared
confirmation gate.

| Arm | Correct | Accuracy | Agent seconds | Input / cached / output tokens |
|---|---:|---:|---:|---:|
| Plain | 6/34 | 17.6% | 393.120 | 919,491 / 856,832 / 17,470 |
| Graph | 5/34 | 14.7% | 464.070 | 1,451,606 / 1,382,656 / 19,178 |
| Ordinary repair | 17/34 | 50.0% | 465.083 | 2,797,376 / 2,694,144 / 18,744 |
| Generic verified union | 21/34 | 61.8% | 395.808 | 2,212,142 / 2,099,968 / 16,322 |
| **Anchored TOV v2** | **23/34** | **67.6%** | **439.273** | **1,821,481 / 1,681,152 / 18,608** |

Generic and TOV received byte-identical candidate patches, test outcomes,
bounded failure traces, verified union, anchor map, model, effort, call cap,
and one final call. TOV used 43.5 more agent seconds but 390,661 fewer input
tokens in this realized run. As in Rust30, this is call- and cap-matched, not an
exact-token equality claim.

## Frozen paired analysis

| TOV comparison | Rescues / harms | Difference | Exact p, one/two-sided | Paired bootstrap 95% CI |
|---|---:|---:|---:|---:|
| Plain | 17 / 0 | +17/34 (+50.0 pp) | .00000763 / .00001526 | [+32.4,+67.6] pp |
| Graph | 18 / 0 | +18/34 (+52.9 pp) | .00000381 / .00000763 | [+35.3,+70.6] pp |
| Ordinary repair | 6 / 0 | +6/34 (+17.6 pp) | .015625 / .03125 | [+5.9,+32.4] pp |
| Generic verified union | 2 / 0 | +2/34 (+5.9 pp) | .250 / .500 | [0,+14.7] pp |

Bootstrap intervals use 200,000 paired whole-task resamples with seed
`20260902`. The matched generic contrast reproduces the Rust30 effect exactly
in rescue count and direction, but is not individually significant at 34
tasks. The pre-specified cumulative Rust30+Python34 matched comparison is 4
rescues and 0 harms over 64 disjoint tasks, exact one-sided `p=.0625`. This is
reported as cumulative evidence because Rust30 was developmental; it is not
misrepresented as a pure confirmatory p-value.

The two new matched rescues were `forth` and `go-counting`. The ordinary-repair
comparison was independently significant and contained six rescues with no
harms.

## Integrity and mechanism checks

Plain, Graph, and ordinary repair passed 6, 5, and 17 tasks. Their verified
union contained 19 distinct tasks. Both final arms began with those same 19
anchors and 15 unresolved tasks.

Post-run checks found:

- 19 anchored tasks and 19 anchored solution files;
- zero anchor byte mismatches at evaluation;
- byte-identical candidate patches, outcome evidence, and anchor map across
  generic and TOV;
- exactly 15 decision-ledger rows in exactly the unresolved-task order;
- zero missing or extra ledger IDs;
- zero forbidden changed paths in all five arms.

The v2 result therefore confirms the end-to-end mechanism on a second complete
official language track. The total Plain advantage is a bundled system effect.
The narrower evidence for semantic-overlap adjudication is a replicated +2
task matched advantage on each of Rust30 and Python34. A third unchanged
complete track with at least one additional matched rescue and no harms would
move the cumulative exact directional test below .05.

## Receipts

- Protocol SHA-256:
  `c3be8eac9a5f5591a744e2f8a1720ab20904fb4955c41d9e1ea594d93618b291`
- Freeze SHA-256:
  `2f0a2c7fabcbfe33a8f91235c3ea135db4e9c38bf496a934e79dac5deebb5c8a`
- Unchanged v2 runner SHA-256:
  `b9336d6a8503b0c41f9303a3241b0cc039f9c387c9ca1060484e15f37cb2fb93`
- Plain result SHA-256:
  `969222e9d8a69b3821769b19bbfe9af01c0f5af16596a9ab71330323477ed3c3`
- Graph result SHA-256:
  `a7055df476042b667cbf9f8bb8573032529215a9d7468156e1a0958143b107f5`
- Ordinary-repair result SHA-256:
  `a7f50428dd160c74bac30a2fb0a3beaa825369b078884566d587d48873e69fee`
- Generic result SHA-256:
  `2d860508fb12e35c7c8635c85d24e0733da6082f1fb3deed4971f2ff837b995b`
- TOV result SHA-256:
  `c245e50de3f9c3187fa0f2e0b25f9a48b8cc71ed7a34d4a751cf869fa1614dfc`
- Decision ledger SHA-256:
  `309cf87caa9e873eb9b789822124ebaef575742bdf33432a7f8d099f0d5296f2`
