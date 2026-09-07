# TOV v2 versus semantic-free structured control on 90 complete Aider tasks

## Outcome

Anchored TOV v2 solved 58/90 official tasks (64.4%) versus 51/90 (56.7%)
for a new semantic-free structured control: +7 tasks and +7.8 percentage
points. The paired comparison contains eight TOV rescues and one TOV harm,
one-sided exact `p=.01953125`, two-sided `p=.0390625`, and a 50,000-draw
track-stratified paired-bootstrap 95% interval of `[+2.22,+14.44]` percentage
points.

This is a review-triggered secondary mechanism control. Existing TOV outcomes
were known before the control was commissioned. It is stronger than the earlier
generic verified-union control because it matches TOV's unresolved-task ledger
schema, counterexample-based falsification, and two completion audits while
withholding only the use of candidate semantic convergence/disagreement as a
decision signal.

## Complete-track results

| Complete official track | Semantic-free structured control | TOV v2 | TOV - control | TOV rescues / harms | Exact p, one/two-sided |
|---|---:|---:|---:|---:|---:|
| Rust, all 30 | **19/30** | 18/30 | -1 (-3.3 pp) | 0 / 1 | 1.0 / 1.0 |
| Python, all 34 | 19/34 | **23/34** | +4 (+11.8 pp) | 4 / 0 | .0625 / .125 |
| C++, all 26 | 13/26 | **17/26** | +4 (+15.4 pp) | 4 / 0 | .0625 / .125 |
| **Cumulative 90** | **51/90** | **58/90** | **+7 (+7.8 pp)** | **8 / 1** | **.01953125 / .0390625** |

No task was selected inside any track. All 90 existing candidate/evidence rows
were reused and exactly three new whole-track control calls were run in the
pre-frozen order Rust, Python, C++. No candidate, TOV, or control call was
rerun.

The language-cluster differences are `[-1,+4,+4]`. Only two of three tracks
are positive, giving a one-sided cluster sign `p=.5`. The task-level result is
therefore conditional on these realized whole-track calls and does not establish
repeatability across model sessions or a population-level language effect.

## What the stricter control isolates

Both final arms had:

- the same deterministic verified union and passing-candidate priority;
- byte-identical Plain, Graph, and ordinary-repair patches;
- byte-identical task outcomes, bounded failure traces, and anchor map;
- one final `gpt-5.6-luna/medium` whole-track call with the same caps;
- one ledger row for each unresolved task;
- fault location, invariant, counterexample, edit-intent, falsification,
  selected-evidence, and final-action fields;
- the same two completion audits; and
- the same post-call byte restoration for verified anchors.

TOV used the remaining ledger field to compare semantic agreements and
disagreements and to route disagreement into falsification. The control wrote
the constant `withheld-by-control` in that field and was explicitly prohibited
from using convergence or disagreement as confidence, routing, or authorization
evidence. Thus the 8:1 result is evidence for the semantic-relation instruction
conditional on the realized candidates, not merely for structured output,
falsification, repeated audit, anchors, or more final calls.

The contrast still does not isolate every micro-operation. Model trajectories
are stochastic, and natural-language instructions cannot guarantee identical
reasoning outside the named treatment. The control was post hoc, and nominal
call/cap matching is not exact-token matching.

## Discordant tasks and exploratory boundary

TOV-only passes were:

- Python: `forth`, `go-counting`, `grade-school`, `list-ops`;
- C++: `complex-numbers`, `kindergarten-garden`, `robot-name`, `yacht`.

These eight tasks disproportionately involve interface or semantic-contract
ambiguity that different candidates expose in different ways: definition
lifetime, required exported constants, result-history semantics, noncommutative
fold order, namespace/API aliases, roster indexing and enum spelling,
const/uniqueness API behavior, and string-versus-enum scoring interfaces. In
the corresponding TOV ledgers, cross-candidate disagreement plus failure traces
identified the obligation that the semantic-free control missed. This pattern
is exploratory because it was identified after observing nine discordant rows.

The control-only Rust pass was `fizzy`. TOV's ledger identified the correct
genericity obligation, but its final file contained an extra closing brace and
failed compilation. This harm is counted. It cautions that semantic diagnosis
does not prevent an execution-level editing slip and motivates repeated final
calls or local compilation in future work.

## Integrity checks

| Track | Expected / observed ledger rows | Semantic field withheld on all rows | Restored anchor files | Byte mismatches | Forbidden paths |
|---|---:|---:|---:|---:|---:|
| Rust30 | 14 / 14 | 14/14 | 32 | 0 | 0 |
| Python34 | 15 / 15 | 15/15 | 19 | 0 | 0 |
| C++26 | 13 / 13 | 13/13 | 26 | 0 | 0 |

Ledger ID order exactly matched the unresolved-task list in all tracks. All
eight evidence files compared between TOV and the new control were byte
identical within each track.

## Realized final-call cost

| Track | Control seconds | TOV seconds | Control input / cached / output tokens | TOV input / cached / output tokens |
|---|---:|---:|---:|---:|
| Rust30 | 524.577 | 543.510 | 3,505,454 / 3,371,264 / 19,241 | 2,371,164 / 2,267,136 / 23,136 |
| Python34 | 440.206 | 439.273 | 1,988,129 / 1,878,272 / 17,946 | 1,821,481 / 1,681,152 / 18,608 |
| C++26 | 427.892 | 439.527 | 1,566,615 / 1,478,912 / 17,541 | 2,415,795 / 2,284,288 / 17,807 |
| **Total** | **1,392.675** | **1,422.310** | **7,060,198 / 6,728,448 / 54,728** | **6,608,440 / 6,232,576 / 59,551** |

The control used more aggregate input tokens; TOV used more output tokens and
29.6 more seconds. Neither dominates on all realized compute dimensions. The
claim is a paired accuracy result at matched semantic-call and cap budgets, not
an efficiency claim.

## Frozen receipts

- Protocol SHA-256:
  `41eb09f2e2c2018b1fd4438c025f345431a79c26365f8804e606d0aff4c9e9ca`
- Runner SHA-256:
  `2431af17962f6b6b657d0d9a2341d859905b1ac3c41448d9d64d3a5099499950`
- Rust result / ledger:
  `f35107c0d52b1020dfa60ac66914dbfa6537c38a0e892beb999cc86f5a1f2a71` /
  `67ae3e31182befbe9b8e48a4d3388a71a5667924e157e1935abf6b1cbff4884f`
- Python result / ledger:
  `ec3d3c275a516ff6fbe78c8328cb1d2df21f21e2effa3d11c8f78107f5f15460` /
  `3e596238ab84f9bfc44e082b6aa368d605e4b08326027615923372730f5ad35c`
- C++ result / ledger:
  `8d582796c334a74fbca81a447c44cd0f9a4ef2ea3472d04c85d394b257aa15b4` /
  `89d77ac4a719055cdf84adcc05035f5d76f53bafc2a3d23249a9d814b0a8dc59`

Runner and integrity machinery are provenance only. The scientific result is
the secondary matched comparison between semantic-overlap routing and the
same structured falsification/audit procedure with semantic relations withheld.
