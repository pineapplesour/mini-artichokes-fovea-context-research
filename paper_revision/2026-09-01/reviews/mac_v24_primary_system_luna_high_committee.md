# Review: Mini Artichokes: Verifier-Gated Recursive Portfolios for Test-Available Program Repair

## Summary

This paper presents Mini Artichokes, a verifier-gated program-repair portfolio that freezes passing task states, edits only unresolved tasks, and recursively promotes passing outputs from heterogeneous repair routes. The preservation property is clearly formalized, and the system shows strong bounded-call improvements over Plain and ordinary repair. However, the incremental contribution of recursive promotion and semantic overlap is difficult to isolate because the main comparisons involve additional compute, post-hoc design, and a single model/runtime.

## Strengths

- The preservation mechanism is precise and meaningful: “the construction copies either its prior anchored state or one complete state already observed to pass; no unverified merged state is created.”

- The paper clearly separates system-level and component-level claims, stating that “RQ1 and the preservation part of RQ2 define the primary system claim” while “RQ3 is a secondary component analysis.”

- The experiments retain complete tracks. Table 1 reports Mini at 59/90 versus ordinary repair at 45/90 and Plain at 15/90, and the protocol explicitly states “No task is ranked, screened, removed, replaced, or topped up.”

- The results include useful prospective and negative evidence. In particular, JavaScript49 is an exact tie between Mini and the comparison portfolio at 47/49, and the paper reports that the Java completion-lock result “does not repeat in five new whole-track pairs.”

- The operational contract is unusually auditable, including “prompt hashes,” “anchor maps,” byte comparisons, ledger completeness checks, and repeated verifier runs. The fail-closed promotion rule is substantially clearer than a model-voting ensemble.

## Weaknesses

- The core algorithmic novelty is limited by the paper’s own characterization: “Given the same stored route outputs and task tests, a minimal task-wise verifier union is algebraically identical to this promotion rule.” Thus, the main gain appears to come from adding heterogeneous routes and taking their verifier-certified union, rather than from a distinct recursive selection algorithm.

- The headline comparisons are confounded by test-time compute. Mini uses five whole-track model calls, compared with one for Plain and two for ordinary repair. The paper correctly describes these as “effectiveness comparisons between nested one-, two-, and five-call systems, not efficiency,” but this prevents attributing the gains specifically to Mini’s structure.

- The strongest equal-call comparison is not cleanly confirmatory. The paper calls the 139/178 versus 132/178 result “mixed-stage,” uses a replacement Go run after TOV outcomes were known, and acknowledges that “the clean prospective JavaScript comparison is a tie.” Consequently, the evidence for superiority over a generic same-call portfolio remains limited.

- Semantic overlap is not causally isolated. The stricter control “was designed after the original outcomes,” and the paper admits that it “cannot equalize latent trajectories or realized compute.” Table 7 also shows TOV taking 1,422.3 seconds with 59,551 output tokens versus 1,233.6 seconds and 48,179 output tokens for Generic. The seven-task original advantage therefore cannot be confidently attributed to semantic relations.

- The preservation theorem depends on a narrow modularity contract. Assumption A1 requires that “the benchmark is partitioned into task units whose declared solution files and verifier do not cross task boundaries,” while the paper acknowledges that shared files, cross-task build state, flaky tests, or unavailable tests require “a coarser unit or a different method.” The selected benchmarks do not systematically stress these assumptions.

- The verifier certifies only finite supplied behavior. The authors explicitly state that “Anchors preserve observed test labels, not correctness beyond those tests,” and note that failure output may reveal behavioral expectations. The paper therefore demonstrates test-suite effectiveness rather than general program correctness or robust hidden-test generalization.

- Generalization is limited by the statement that “All semantic calls use one model and runtime.” The five repeated pairs on Python34 and C++26 provide useful trajectory evidence, but they do not establish robustness across models, reasoning settings, or broader benchmark populations.

## Questions for the Authors

1. Can Mini be compared prospectively with a generic portfolio using matched total tokens, latency, model calls, and evaluator cost across multiple untouched complete tracks?

2. What is the incremental contribution of recursive promotion relative to an offline verifier union of the same final-route outputs?

3. Can semantic-overlap and semantic-free routes be evaluated prospectively across multiple models or independent sessions with matched realized output budgets?

4. How does the method behave when solution files or build state are shared across tasks, or when tests are flaky, weak, or unavailable?

5. Do promoted patches transfer to independent held-out tests or behavioral specifications, rather than only the supplied official suites?

## Scores

Soundness: 3/4 — The preservation property is coherent under explicit assumptions, but causal attribution is weakened by post-hoc stages, unmatched compute, and single-model evaluation.

Presentation: 3/4 — The paper is careful and transparent, though its many evidence stages and comparison labels make the main empirical claim difficult to isolate.

Significance: 3/4 — Verifier-gated composition is practically relevant for test-available repair, but its advantage over a generic multi-route union is not established.

Originality: 3/4 — The immutable-anchor and unresolved-only composition is a useful formulation, although the promotion operation itself is acknowledged to reduce to a task-wise maximum.

Overall recommendation: 3/6 — Borderline; the bounded-call system results are promising, but stronger prospective and resource-matched evidence is needed.

Confidence: 3/5 — The manuscript is sufficiently detailed to judge, but the reported execution artifacts and numerical results cannot be independently verified here.

## Ethics and Limitations

The study uses public programming tasks and no human participants. It appropriately discusses test-feedback leakage, finite verifier coverage, licensing, benchmark contamination, runtime deviations, and increased inference cost. The authors are also candid that the method preserves “observed test labels, not correctness beyond those tests” and makes no efficiency claim. These limitations substantially constrain claims about general program correctness and broad deployment.

## Comment

I recommend borderline acceptance/revision. The strongest contribution is the fail-closed, byte-exact preservation contract, together with evidence that additional verified repair routes can retain complementary successes. The most important missing result is a prospectively frozen, genuinely resource-matched comparison that separates the value of recursive promotion and semantic-overlap guidance from simply running more heterogeneous repair attempts and taking their verifier-certified union.
