# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper proposes Mini Artichokes, a test-available program-repair system that freezes complete passing task states as byte-exact anchors, repairs only unresolved tasks, and recursively promotes passing outputs from heterogeneous routes. It reports 59/90 on three complete Aider Polyglot tracks and 33/39 on a subsequently frozen Go track. The verified-preservation mechanism is clearly specified, but the evidence more strongly supports a useful five-call verified route union than a causal or general advantage from semantic-overlap reasoning.

## Strengths

- The anchoring rule is precise and has a valid scoped guarantee: “a complete verified task state is removed from model discretion,” and under A1–A5 the promoted output “passes every task in `A union (union_k S_k)`.”

- The evaluation retains complete tracks: “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” plus “all 39 official Go tasks.” The paper reports full denominators and per-track results.

- The end-to-end results are substantial within this setting: Mini Artichokes achieves “59/90 (65.6%)” versus “45/90 (50.0%) for ordinary repair,” and Go achieves “33/39” versus 25/39.

- The paper distinguishes effectiveness from causal attribution. It explicitly describes the main comparisons as “nested, additional-compute comparisons” and states that Go establishes “end-to-end value, not an overlap-only effect.”

- Reporting is unusually candid. The authors disclose that recursive composition “was chosen after the later crossovers,” that the Go Generic call was “transport-null,” and that Rust `fizzy` retained a harm caused by “an extra closing brace.”

- The repeated sessions reveal meaningful instability rather than hiding it: TOV-minus-control differences include “`+4,-2,+2,0,+2`” and “`+1,-1,0,+5,-3`.” The reported recursive union of “210/300 repeated task-session passes” also provides plausible evidence for verifier-backed route complementarity.

## Weaknesses

- The headline gains are not compute-matched algorithmic comparisons. Mini Artichokes uses “five calls,” compared with one for Plain and two for ordinary repair. The resulting “+48.9 percentage points” and “+15.6 points” therefore establish effectiveness with additional inference, not superiority at a fixed budget.

- The recursive route comparison is post hoc and does not isolate the proposed mechanism from generic route diversity. The paper says the recursive analysis was “specified only after these repetitions revealed large branch crossovers.” Thus 59/90 versus 54/90 shows that this selected pair of routes benefits from verified union, but not that Mini Artichokes would beat a pre-specified, equally expensive generic multi-route portfolio.

- The causal evidence for TOV is mixed. The original semantic-free control was frozen “only after all TOV outcomes and the MAC v9 critique were known,” while the replications have intervals crossing zero: `[-2.35,+8.24]` and `[-6.92,+11.54]` percentage points. The Go replacement sensitivity is likewise only 33/39 versus 31/39 with `p=.3125`.

- The TOV and semantic-free controls are not exactly compute-matched. TOV uses 59,551 output tokens and 1,422.3 seconds, versus 54,728 output tokens and 1,392.7 seconds for the semantic-free control. The authors acknowledge this, but the difference weakens mechanistic attribution.

- The semantic ablation does not uniquely identify semantic relations as the cause. The paper admits that it “matches named instructions, not latent reasoning or exact realized compute,” and that “trajectory variation is material.” The observed effect could therefore reflect prompt-induced attention or output behavior rather than the proposed ledger semantics.

- Statistical generalization is limited. “All task rows within one arm share one whole-track model call,” and “only three language clusters exist.” The task-level exact tests are consequently conditional on a few realized trajectories; five sessions on each of two fixed tracks provide useful variance information but remain insufficient for broad population claims.

- The formal preservation property depends on restrictive assumptions, including “no cross-task test dependency,” “isolated workspaces,” and a “stable verifier.” The paper does not establish how often these conditions hold in realistic repositories or how the method should be evaluated when they fail.

- The semantic ledger is not independently validated. “Ledger diagnoses were not independently annotated,” and the interface-ambiguity explanation was “formulated after the nine discordant tasks were known.” This makes it difficult to distinguish a genuine diagnostic representation from post hoc interpretation of successful trajectories.

## Questions for the Authors

1. How does Mini Artichokes compare with best-of-five execution-verified sampling or two generic final routes, with route count, promotion rule, and analysis fixed before observing crossovers?

2. What remains of the TOV effect under matched total tokens and wall-clock budget, rather than matched nominal call count?

3. Can a preregistered replication on several unseen tracks evaluate the recursive system and semantic-free control before any candidate or route outcomes are observed?

4. What are the factorial contributions of candidate diversity, immutable anchoring, the direct route, TOV, and recursive promotion?

5. Can independent annotators assess the four ledger fields and test prospectively whether ledger quality predicts rescues?

6. How does promotion behave with cross-task dependencies, coordinated repository-wide changes, nondeterministic tests, or weak test suites?

## Scores

Soundness: 3/4 — The preservation theorem and reported measurements are coherent, but causal attribution and generalization remain limited.

Presentation: 4/4 — The paper is exceptionally clear about chronology, denominators, failures, controls, and inferential boundaries.

Significance: 3/4 — Verified route preservation is practically relevant, although the demonstrated setting is narrow and compute-intensive.

Originality: 3/4 — The composition of immutable anchors and recursive verified promotion is useful, but several constituent ideas resemble best-of-multiple verified repair.

Overall recommendation: 3/6 — Borderline: promising systems evidence, but the central causal and compute-matched claims are not yet strong enough for clear acceptance.

Confidence: 4/5 — The paper is self-contained and sufficiently detailed for judgment, though the underlying experiments cannot be independently rerun here.

## Ethics and Limitations

The study uses public coding exercises and no human participants. The paper appropriately notes that failure output may reveal behavioral expectations, that finite suites establish benchmark passes rather than full correctness, and that the method increases inference compute. Its major limitations are candidly stated: one model and runtime, correlated whole-track calls, one benchmark family, few language clusters, post hoc route composition, non-token-matched controls, restrictive task-local verifier assumptions, and a transport-null primary Go comparator.

## Comment

I recommend borderline. The byte-exact anchoring and verifier-backed promotion rule are coherent contributions, and the end-to-end gains are credible on the reported tracks. The most important issue is to establish, prospectively and at matched compute, whether the improvement exceeds generic multi-route execution-verified redundancy rather than primarily reflecting additional calls and a post hoc choice of complementary routes.
