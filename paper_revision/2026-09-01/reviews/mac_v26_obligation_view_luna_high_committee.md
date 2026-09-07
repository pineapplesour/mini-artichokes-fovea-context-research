# Review: Mini Artichokes: Verifier-Gated Recursive Portfolios for Test-Available Program Repair

## Summary

This paper presents Mini Artichokes, a verifier-gated portfolio for modular, test-available program repair. Complete task states that pass the official verifier become immutable byte-level anchors, while unresolved tasks are processed by heterogeneous repair routes and promoted only after verification. The paper reports strong bounded-call results—“59/90” on the original Aider tracks, “33/39” on Go, and “47/49” on JavaScript—but the distinctive architectural advantage over equally resourced generic repair remains incompletely established.

## Strengths

- The preservation mechanism is a clear structural contribution. Under assumptions A1–A5, “the construction copies either its prior anchored state or one complete state already observed to pass,” yielding a meaningful test-label preservation property.

- The evaluation retains complete inventories. The paper states, “No task is ranked, screened, removed, replaced, or topped up,” and reports full denominators including all 39 Go and all 49 JavaScript tasks.

- The paper separates system effectiveness from component attribution. Its claim hierarchy labels the main result “End-to-end bounded-call effectiveness” while explicitly stating that stable standalone semantic superiority is “not established.”

- The empirical results are substantial within the stated regime: Mini reaches “59/90” versus “45/90” for ordinary repair and “15/90” for Plain, and reaches “33/39” on Go and “47/49” on JavaScript.

- The protocol and integrity reporting is unusually thorough. For example, the Go experiment reports “78/78 route-by-anchor file comparisons were exact,” exact unresolved-task ledgers, and zero forbidden-path changes.

- The authors report meaningful negative evidence rather than hiding it. The paper states that “one Java completion-lock result also does not repeat in five new whole-track pairs” and that the clean prospective JavaScript comparison is tied.

## Weaknesses

- The headline gains are confounded by substantially larger test-time computation. Mini uses “five whole-track model calls,” compared with one for Plain and two for ordinary repair. Thus “59/90 versus 45/90” establishes bounded-call effectiveness, but does not isolate the value of recursive promotion from allowing additional model executions.

- The strongest nominally equal-call comparison is mixed-stage and partly post hoc. Although Mini scores “139/178” versus “132/178” for Direct∪Generic, the paper acknowledges that this is “mixed-stage,” that Go uses a replacement sensitivity, and that “JavaScript is the only clean prospective equal-call track and is a tie.” This leaves the central architectural superiority claim suggestive rather than conclusive.

- The semantic-overlap component is not causally or consistently demonstrated. The original TOV comparison is “secondary because the stricter control was designed after the original outcomes,” while the five new Java pairs show “no wins, two losses, three ties.” The fresh Java comparison is especially concerning: “18/47 for P/G/R+A+O versus 22/47 for P/G/R+A+B.”

- The semantic-free control does not fully isolate the proposed relation operation. The paper concedes that the ablation “cannot make latent model trajectories identical,” and Table 7 reports different realized costs: TOV takes 1,422.3 seconds versus 1,392.7 for the structured control, with different input and output token totals. The observed route difference may therefore reflect prompt-induced trajectories or resource usage rather than semantic overlap itself.

- The formal result is narrow. The theorem guarantees only that the output passes “under the same verifier invocation used for promotion,” and the paper explicitly says this is “not a claim of semantic correctness, verifier completeness, or reliability under nondeterministic tests.” Its practical value therefore depends on verifier strength and task modularity.

- The statistical interpretation should remain conservative. The paper states that “each task vector is also produced inside one whole-track call” and that task-level tests “condition on realized calls.” The very small task-level p-values consequently do not provide broad population-level evidence; the more appropriate session-level evidence is limited and variable.

- Generalization is narrow. “All semantic calls use one model and runtime,” namely `gpt-5.6-luna`, while the method assumes “modular task ownership, isolated workspaces, and a stable task verifier.” HumanEvalFix reaches a ceiling of “164/164” for ordinary repair, and the paper itself notes that public QuixBugs “may occur in training data.” These are useful boundaries but not broad validation.

## Questions for the Authors

1. Can Mini be compared prospectively with a generic five-call portfolio under matched total tokens, latency, model, and evaluator budgets, with all prompts frozen before any outcomes are observed?

2. What remains of the result after analyzing whole tracks or sessions as the statistical unit rather than treating tasks within a single whole-track call as independent evidence?

3. Can recursive promotion, semantic overlap, and the number of final routes be separated through a pre-specified factorial ablation?

4. How does the system detect or handle violations of A1–A5, such as shared solution files, cross-task build state, flaky tests, or misleading failure traces?

5. Can the semantic ledgers be independently annotated to test whether overlap produces more accurate obligation diagnoses than the semantic-free control?

## Scores

Soundness: 3/4 — The preservation property is well specified, but the empirical architectural and causal claims remain resource-confounded and trajectory-dependent.

Presentation: 3/4 — The paper is exceptionally transparent, though its many evidence stages and caveats make the central claim difficult to isolate.

Significance: 3/4 — Verifier-backed preservation is practically useful in modular test-available repair, but fixed-resource superiority is not established.

Originality: 3/4 — Recursive promotion of complete verified task states is a plausible systems contribution, although its ingredients build on established verification and iterative-repair methods.

Overall recommendation: 3/6 — Borderline: the paper contains a real and carefully bounded contribution, but the strongest comparative claims are not yet cleanly supported.

Confidence: 3/5 — The manuscript provides enough detail for a substantive assessment, but the decisive executions and artifacts cannot be independently verified here.

## Ethics and Limitations

The paper uses “public open-source exercises and no human participants” and appropriately notes that failure output may reveal “behavioral expectations.” It discloses increased inference compute, licenses, runtime deviations, finite-test limitations, and the possibility that public QuixBugs appears in training data. The principal scientific risk is overextending test-label preservation into semantic correctness; the paper generally avoids that error. Its stated restrictions—one model/runtime, modular task ownership, stable verifiers, and limited session replication—materially constrain generalization.

## Comment

I recommend borderline consideration. The most convincing contribution is the fail-closed preservation and recursive composition rule, while the bounded-call results are substantial. The most important issue is a prospective, genuinely resource-matched comparison against a strong generic portfolio, together with repeated-session evaluation of semantic overlap. Until that evidence is available, the paper supports a useful verifier-gated repair system more strongly than it supports a decisive architectural or semantic-overlap advantage.
