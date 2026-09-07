# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

The paper proposes Mini Artichokes, a five-call program-repair system that freezes verified task states, repairs only unresolved tasks, and recursively promotes passing outputs from heterogeneous routes. The mechanism is clearly specified and yields substantial gains over Plain and ordinary repair, but the stronger claim of superiority over a same-call generic portfolio is not prospectively established, and the causal contribution of semantic overlap remains underidentified.

## Strengths

- The preservation mechanism is concrete and formally scoped. Under A1–A5, “no unverified merged state is created,” and the paper explicitly distinguishes test-label preservation from “semantic correctness, verifier completeness, or reliability under nondeterministic tests.”
- The evaluation retains complete inventories: “No task is ranked, screened, removed, replaced, or topped up,” including all 90 original Aider tasks, 39 Go tasks, 49 JavaScript tasks, and 164 HumanEvalFixDocs tasks.
- The reported bounded-call effectiveness is substantial. Mini reaches “59/90 (65.6%)” versus “15/90 (16.7%)” for Plain and “45/90 (50.0%)” for ordinary repair.
- The paper provides useful integrity safeguards. It reports that “every final workspace matched its selected anchor bytes,” that forbidden changed paths were zero, and that JavaScript passed “all 126 route-by-anchor byte checks.”
- The authors are unusually candid about scope. They state that the five-track comparison is “mixed-stage,” that the clean prospective JavaScript result is a tie, and that semantic overlap is “not a universally superior final policy.”

## Weaknesses

- The main same-call superiority claim is not established prospectively. The headline result is “139/178 versus 132/178,” but this aggregation is explicitly “mixed-stage”; Go uses a replacement after the original failure, and “JavaScript is the only clean prospective equal-call track and is a tie.” On that clean comparison, both portfolios reach “47/49.”
- The semantic-overlap effect is not causally isolated. The semantic-free control “cannot equalize latent trajectories or realized compute,” while TOV takes “1,422.3 seconds” versus “1,392.7 seconds” and produces 59,551 versus 54,728 output tokens. The seven-task original advantage may therefore reflect additional trajectory, prompt, or compute differences rather than semantic relations specifically.
- The formal guarantee is largely a consequence of task-wise verifier union. The paper itself says that “a minimal task-wise verifier union is algebraically identical to this promotion rule” and claims “no new selector beyond that max operation.” The practical composition may still be valuable, but its scientific novelty and significance require stronger evidence that the composition choices improve outcomes beyond simpler unions.
- Several important mechanisms are not factorially separated. The paper does not independently isolate immutable anchoring, unresolved-only branching, route heterogeneity, completion locking, and recursive promotion while holding candidate outputs fixed. This is particularly important because the stated system contribution combines all of them.
- Generalization is conditional and narrow. The method assumes “task units whose declared solution files and verifier do not cross task boundaries,” while shared files, cross-task build state, flaky tests, and unavailable tests are not substantially evaluated. The paper also states that “all semantic calls use one model and runtime.”
- The statistical evidence supports realized-call descriptions more than broad population claims. “All task rows within one arm share one whole-track model call,” and the five-track sign test is only `p=.125`. The ten repeated sessions cover only Python34 and C++26, so the results do not establish robustness across models, runtimes, or repository populations.
- The practical efficiency tradeoff is unresolved. The authors explicitly describe Mini as “an effectiveness system, not an efficiency result,” and report unequal realized tokens and latency. Its gains therefore come with a meaningful, incompletely normalized compute cost.

## Questions for the Authors

1. Can you run Mini and Direct∪Generic on several untouched complete tracks with both policies frozen before any calls and matched realized token, time, and output budgets?
2. What are the results of a factorial ablation removing anchoring, unresolved-only branching, semantic relations, completion locking, and recursive promotion separately?
3. How much of the TOV advantage remains after matching output tokens and wall-clock time?
4. Can independent annotators label TOV’s semantic relations and test whether their accuracy predicts successful repairs?
5. How does the method behave when solution files, build state, or tests cross task boundaries, and can the system automatically detect when A1–A5 are invalid?
6. Can the released artifact provide a public location and complete per-task vectors sufficient to audit the reported `139/178`, `132/178`, and `210/300` results?

## Scores

Soundness: 3/4 — The preservation construction is well specified and the claims are carefully qualified, but causal attribution and prospective comparative evidence remain incomplete.

Presentation: 4/4 — The paper is exceptionally transparent about chronology, assumptions, deviations, denominators, and claim boundaries, although technically dense.

Significance: 3/4 — Verifier-gated preservation is practically useful for test-available repair, but its advantage over simpler matched alternatives and its broader applicability are not established.

Originality: 3/4 — The combination of immutable anchors, unresolved-only repair, and recursive heterogeneous promotion is meaningful, although the core union operation is acknowledged to be algebraically simple.

Overall recommendation: 3/6 — Borderline; promising and carefully documented bounded-system evidence, but the principal comparative and semantic claims require stronger prospective validation.

Confidence: 4/5 — The paper is sufficiently self-contained for a well-grounded assessment, though the underlying runs and artifacts cannot be independently verified from the manuscript alone.

## Ethics and Limitations

The study uses public programming tasks and no human participants. It appropriately withholds private tests and gold implementations, while acknowledging that failure output may reveal behavioral expectations. It discloses increased inference compute and licensing obligations. The principal limitations are the single model/runtime, correlated candidate errors, finite and potentially weak tests, task-level dependence within whole-track calls, unequal realized compute, limited replication, and the absence of evaluation on genuinely non-modular repositories. The QuixBugs transfer result is also weakened by the authors’ note that it “may occur in training data.”

## Comment

The paper presents a well-engineered and mechanically sound preservation mechanism with promising bounded-call effectiveness. I recommend borderline acceptance/rejection territory, with the decisive issue being whether Mini improves reproducibly over a same-call generic verified portfolio rather than merely benefiting from additional trajectories and post-hoc composition. A prospectively frozen, compute-matched factorial evaluation across multiple untouched repositories would most substantially change the assessment.
