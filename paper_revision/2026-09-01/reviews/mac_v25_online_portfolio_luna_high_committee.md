# Review: Mini Artichokes: Verifier-Gated Recursive Portfolios for Test-Available Program Repair

## Summary

This paper presents Mini Artichokes, a verifier-gated portfolio that preserves complete task states passing an external test suite, limits later edits to unresolved tasks, and recursively promotes passing outputs from complementary repair routes. The system achieves strong bounded-call results on complete code-repair tracks, but the evidence does not cleanly establish that its distinctive recursive or semantic-overlap mechanisms outperform simply allocating more model calls and computation.

## Strengths

- The preservation mechanism is clearly specified and has a meaningful conditional guarantee. The paper states that “a complete verified task state is removed from model discretion” and that “only unresolved units are branched.” Under assumptions A1–A5, promotion copies “one complete state already observed to pass; no unverified merged state is created.”

- The bounded-call system results are substantial. On the original tracks, Mini solves “59/90,” compared with “45/90 for ordinary repair” and “15/90 for Plain.” It also reaches “33/39” on Go and “47/49” on JavaScript.

- The evaluation retains complete inventories rather than selecting favorable examples. Table 3 reports all 39 Go tasks and Table 5 all 49 JavaScript tasks, while the paper explicitly says that “No task is ranked, screened, removed, replaced, or topped up.”

- The paper is unusually candid about claim boundaries. It identifies “Mini Artichokes as a five-call effectiveness system, not semantic overlap as an isolated causal treatment,” and acknowledges that the clean prospective equal-call JavaScript comparison is tied at “47/49.”

- Recursive promotion has a plausible systems rationale. Across repeated sessions, the recursive union reaches “210/300 task-session passes,” versus “198 for TOV alone and 190 for the semantic-free route,” illustrating how route-specific successes can be retained.

- The artifact and integrity procedures are concrete. The paper reports “byte-identical” route inputs, exact ledger task IDs, forbidden-path checks, prompt hashes, and reproduced outcome hashes, making the preservation protocol more auditable.

## Weaknesses

- The headline improvements are confounded by model-call count and compute. Mini uses five whole-track calls, versus one for Plain and two for ordinary repair. As the paper itself states, these are “effectiveness comparisons between nested one-, two-, and five-call systems.” They demonstrate value under a larger bounded test-time budget, but do not show that the proposed architecture causes the gain.

- The strongest equal-call comparison is not a clean prospective experiment. The reported aggregate is “139/178 for Mini and 132/178 for Direct∪Generic,” but the paper concedes that it is “mixed-stage,” with the original contrast post hoc and Go using a replacement sensitivity. The “only clean prospective equal-call track,” JavaScript49, is a tie.

- The semantic-overlap contribution is not convincingly isolated. The stricter control was “designed after the original outcomes,” and the paper admits that it cannot equalize “latent model trajectories or realized compute.” Further, the five new Java pairs show “no wins, two losses, three ties.” This supports overlap as a potentially useful route, but not as a reliable causal improvement.

- The statistical evidence is less independent than the task-level p-values suggest. “All task rows within one arm share one whole-track model call,” and the task-level tests “condition on realized calls.” Thus values such as `p=5.68e-14` quantify realized task discordance, not broad inference over independent runs, models, or language populations. The more relevant track/session evidence remains limited.

- Applicability is narrower than the general framing. The preservation property requires “task units whose declared solution files and verifier do not cross task boundaries,” isolated workspaces, and stable tests. The method explicitly “does not guarantee correctness beyond those tests,” and no substantial evaluation is provided for shared files, cross-task build state, flaky tests, or weak/incomplete verification.

- Generalization is limited by the experimental scope. “All semantic calls use one model and runtime,” and the main evidence concerns modular, test-available code repair. HumanEvalFix Python reaches an ordinary-repair ceiling of “164/164,” while QuixBugs reaches “40/40” for several routes, leaving little room to assess the proposed mechanism.

- The semantic ledger is not independently validated. The authors acknowledge that “Ledger diagnoses are not independently labelled.” Consequently, it is unclear whether semantic overlap contributes information beyond a longer structured prompt, additional output, or a different model trajectory.

## Questions for the Authors

1. Can you run a prospective comparison across multiple untouched complete tracks with Mini and a generic verifier portfolio matched by tokens, latency, and model settings?

2. What gain remains from recursive promotion alone, holding the final repair route fixed and comparing it with and without the intermediate verified-union floor?

3. Can you evaluate the semantic-overlap route with matched output budgets and realized compute across multiple models or independent sessions?

4. How sensitive are results to the fixed priorities `R > G > P` and direct-route-first promotion when both routes pass?

5. Can you test the preservation protocol on repositories with shared files, cross-task dependencies, flaky tests, or partial verification?

## Scores

Soundness: 3/4 — The preservation construction is sound under explicit assumptions, but empirical attribution and independent replication are limited.

Presentation: 3/4 — The paper is transparent and well organized, although the many staged comparisons make the central claim difficult to isolate.

Significance: 3/4 — Verifier-gated preservation is useful for test-available repair, but demonstrated applicability remains narrow.

Originality: 3/4 — The composition of immutable anchors, unresolved-task branching, and recursive promotion is a meaningful systems contribution, though its components relate to established ideas.

Overall recommendation: 3/6 — Borderline: the bounded-call system results are promising, but a clean resource-matched advantage over generic portfolios is not established.

Confidence: 4/5 — The paper provides sufficient detail for assessing its logic and reported evidence, although the underlying runs cannot be independently verified here.

## Ethics and Limitations

The work uses public programming tasks and no human participants. It appropriately discusses licensing, possible information leakage through failure output, and increased inference compute. Its key limitations are finite test coverage, dependence on modular task boundaries and stable verifiers, correlated whole-track calls, one-model evaluation, unequal realized compute, post-hoc experimental stages, and limited replication. No hidden reviewer-directed text is present.

## Comment

The paper presents a carefully engineered and potentially useful verifier-gated preservation rule, supported by strong bounded-call effectiveness results. However, its central scientific advantage remains difficult to attribute: the primary comparison gives Mini substantially more calls, the aggregate equal-call comparison is mixed-stage, and the clean prospective equal-call result is tied. The most important revision is a prospective resource-matched evaluation that separately isolates recursive promotion and semantic-overlap guidance.
