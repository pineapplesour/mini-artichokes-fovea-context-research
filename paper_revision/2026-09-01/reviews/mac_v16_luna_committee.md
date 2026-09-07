# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper proposes a five-call program-repair system that preserves complete task solutions passing an external verifier, restricts later edits to unresolved tasks, and recursively promotes passing outputs from complementary repair routes. Its strongest evidence is system-level: 59/90 tasks on three complete Aider Polyglot tracks and 33/39 on a subsequently frozen Go track. The narrower semantic-overlap component, TOV, is presented more cautiously as a potentially useful heterogeneous route rather than a reliably superior causal intervention.

## Strengths

- The central mechanism is clear and practically motivated: “a complete verified task state is removed from model discretion, only unresolved units are branched, and passing states from heterogeneous routes are recursively promoted.”

- The preservation argument is explicit and appropriately conditional. Under A1–A5, “no unverified merged state is created,” and the construction copies complete task states rather than intersecting speculative edits.

- The evaluation retains complete benchmark tracks: “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” followed by “all 39 official Go tasks.” This avoids favorable task selection within the reported tracks.

- The empirical accounting is unusually transparent. The paper reports 59/90 versus 45/90 for ordinary repair and 15/90 for Plain, while also identifying a 48/90 verified floor and reporting rescue/harm counts.

- The paper distinguishes effectiveness from causal attribution. It explicitly states that “the supported result is verified redundancy” and that semantic overlap is “a productive conditional route, not a universal or 20-point causal gate.”

- Negative and integrity-related outcomes are retained. The Go Generic call was “transport-null,” the Rust `fizzy` repair had “an extra closing brace,” and one C++ replication generated forbidden `a.out`.

- The replication results appropriately expose instability: Python differences were “`+4,-2,+2,0,+2`” and C++ differences were “`+1,-1,0,+5,-3`,” with both session-level intervals crossing zero.

## Weaknesses

- The main system comparisons are not compute-matched. Mini Artichokes uses “five calls: `P/G/R`, TOV, and the direct structured route,” whereas Plain uses one call and ordinary repair uses two. Thus 59/90 versus 15/90 or 45/90 establishes effectiveness with additional test-time computation, not an algorithmic advantage at a fixed resource budget.

- The recursive dual-route policy was selected after observing route crossovers. The paper states that “the recursive composition was chosen after the later crossovers,” making the 59/90 versus 54/90 comparison exploratory and vulnerable to selection effects.

- The semantic-overlap component is not robustly isolated. The semantic-free control “was frozen only after all TOV outcomes and the MAC v9 critique were known,” while the later replications yielded wide intervals of `[-2.35,+8.24]` and `[-6.92,+11.54]` percentage points. This supports a possible benefit, but not a stable standalone effect.

- The Go evaluation lacks a clean prospective equal-call comparator. The original Generic invocation was “transport-null,” and its replacement was run “after TOV outcomes were known.” The resulting 33/39 versus 31/39 sensitivity comparison is informative but not confirmatory.

- Task-level significance values can be overinterpreted because “all tasks within one arm share one whole-track model call.” The reported `p=5.68e-14` and similar values quantify realized task discordance more directly than independent evidence across language populations or benchmark families; the three-track cluster checks are necessarily underpowered.

- TOV is not fully operationalized in the paper. Fields such as “fault location,” “smallest counterexample class,” and “selected evidence” are described as natural-language ledger components without complete prompts, schemas, parsing rules, or deterministic failure handling.

- The formal guarantee is valuable but narrow: it preserves “benchmark passes, not proof of correctness beyond those tests.” The empirical contribution therefore depends on route complementarity, which is precisely the aspect most affected by post hoc design and session variance.

- Generality is limited by the setting: “one model and runtime,” one benchmark family, task-local files, informative test feedback, and a stable external verifier. The paper acknowledges these assumptions but does not stress-test them on cross-task dependencies, noisy tests, weak coverage, or unavailable verification.

- TOV also uses more realized resources: it takes “29.6 more seconds” than the stricter control and produces more output tokens. The lack of token- or latency-matched comparisons leaves the practical value of its modest component advantage unresolved.

## Questions for the Authors

1. Can you evaluate Mini Artichokes against strong generic five-call portfolios under preregistered, matched token, wall-clock, and verifier-call budgets?

2. What exact prompts, schemas, parsing rules, and fail-closed procedures define TOV and the direct structured route?

3. Can you independently and blindly assess ledger quality, testing whether correct semantic diagnoses predict rescues?

4. How much does each component—candidate diversity, anchoring, execution feedback, TOV, direct repair, and recursive promotion—contribute in a controlled ablation?

5. How does recursive promotion behave with cross-task dependencies, nondeterministic or weak tests, and settings without an executable verifier?

## Scores

Soundness: 3/4 — The preservation construction is coherent and the measurements are candid, but causal attribution and compute-matched superiority remain unestablished.

Presentation: 3/4 — The paper is unusually transparent and well organized, although the many nested comparisons make the evidential hierarchy difficult to reconstruct.

Significance: 3/4 — Verified task-state preservation is a useful systems idea, but the demonstrated scope is a narrow and compute-intensive repair regime.

Originality: 3/4 — The composition of immutable anchors, unresolved-set branching, and recursive verifier promotion is plausibly novel despite relying on familiar ingredients.

Overall recommendation: 3/6 — Borderline; promising system evidence, but insufficient isolation and generalization evidence for a strong acceptance recommendation.

Confidence: 4/5 — The paper is sufficiently self-contained to assess its claims, though the underlying executions and exact prompts cannot be independently verified here.

## Ethics and Limitations

The paper uses public programming exercises and no human participants. It appropriately notes that failure output may reveal behavioral expectations and therefore labels the setting “test-available program repair.” Important limitations include one model and runtime, correlated candidates, one benchmark family, few language clusters, additional inference cost, finite test specifications, post hoc recursive composition, and the transport-null Go comparator. The A1–A5 guarantee also depends on task-local files, isolated workspaces, and a stable verifier. The authors are commendably candid that passing anchors do not establish correctness beyond the supplied tests.

## Comment

I recommend borderline. The preservation mechanism is coherent and the full-track results suggest that verifier-backed route complementarity can be practically useful, but the paper does not yet establish a reproducible advantage over strong compute-matched generic portfolios or a reliable causal effect of semantic overlap. The most important next step is a preregistered, independently reproducible evaluation with precise method specification, matched resource budgets, and component ablations.
