# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper introduces Mini Artichokes, a test-available program-repair system that preserves complete task states passing an external verifier, edits only unresolved tasks, and recursively promotes passing outputs from heterogeneous repair routes. Across five Aider tracks, it reports 139/178 solved tasks versus 132/178 for a nominally equal-call Direct∪Generic portfolio, with larger gains over Plain and ordinary repair. The evidence supports verified multi-route redundancy as a useful bounded-compute system design, but does not establish semantic overlap as a causal or consistently superior component.

## Strengths

- The preservation mechanism is clearly specified and formally motivated. The paper states that “a complete verified task state is removed from model discretion” and defines assumptions A1–A5 under which promotion copies “either its prior anchored state or one complete state already observed to pass.”

- The evaluation retains complete official tracks rather than selecting tasks: “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” followed by all 39 Go and 49 JavaScript tasks.

- The system shows substantial within-setting effectiveness. Mini reaches “59/90,” “33/39,” and “47/49” on the reported Aider subsets, versus Plain’s 15/90, 17/39, and 27/49, respectively.

- The paper distinguishes system effectiveness from component causality. It explicitly says the “best-supported object is Mini Artichokes as a five-call effectiveness system, not semantic overlap as an isolated causal treatment.”

- The study includes valuable negative and integrity evidence, including the retained Rust `fizzy` harm, the “transport-null” Go invocation, the exact JavaScript tie, and the statement that “no call was rerun.”

- The authors are unusually candid about limitations, stating that the equal-call aggregate is “mixed-stage and not token-matched” and that a “repeatable standalone semantic-relation effect” is “not established.”

## Weaknesses

- The headline equal-call advantage is not a clean prospective causal result. The 139/178 versus 132/178 comparison combines “development, prospective, extension, and sensitivity stages”; the Go Generic result uses a replacement run conducted after TOV outcomes were known; and “JavaScript is the only clean prospective equal-call track and is a tie.”

- The semantic-overlap effect is weakly identified. The semantic-free control “was frozen only after all TOV outcomes and the MAC v9 critique were known,” and the paper acknowledges that it matches “named instructions, not latent reasoning or exact realized compute.” The observed +7-task original difference may therefore reflect prompt-induced trajectories, output length, or stochastic variation rather than semantic relations specifically.

- The main system gain is inseparable from additional routes and verifier selection. The paper admits that “a minimal task-wise verifier union is algebraically identical to this promotion rule.” Thus the mechanical preservation property is useful, but the empirical incremental value of the particular Mini composition over simpler verifier-selected portfolios remains insufficiently isolated.

- Equal call counts do not imply matched resources. Table 8 reports 1,422.3 seconds for TOV versus 1,233.6 seconds for Generic and 1,392.7 seconds for the semantic-free control. The paper appropriately makes no efficiency claim, but the nominally matched comparison is still substantially confounded by realized compute and latency.

- The apparent task-level statistical precision is limited by whole-track generation. “Each task vector is generated inside one whole-track call,” so the 178 task observations are not independent model trajectories. The relevant track-level evidence is only three positive and two tied outcomes, with sign value `.125`; the replication means also have wide intervals.

- The semantic ledger is not validated as a scientific measurement. Integrity checks “do not score the natural-language diagnoses for semantic correctness,” and “ledger diagnoses were not independently annotated.” The post hoc interface-ambiguity explanation is plausible but remains an unvalidated interpretation.

- Generality is narrower than the title and broad framing imply. The experiments use “one model and runtime,” modular test-available tasks, and mostly prompt-level internal baselines. The paper explicitly makes no comparison with a full contemporary repair system such as KIRA, and it does not test other models, noisy verifiers, or repositories with cross-task dependencies.

## Questions for the Authors

1. Can Mini and Direct∪Generic be compared prospectively across multiple fresh complete tracks with fixed token, latency, and monetary budgets, rather than equal nominal call counts?

2. What is the minimal factorial configuration that produces the gain: candidate diversity, anchoring, TOV, the direct route, or recursive promotion?

3. Can the semantic-free control be matched for prompt length, output schema, deliberation requirements, and realized tokens so that semantic relations are the principal intervention?

4. How sensitive are results to model randomness, route order, fixed priority, and newly generated candidate repositories?

5. Can independent annotators evaluate the TOV ledger fields, and can ledger quality predict rescues or harms?

## Scores

Soundness: 3/4 — The construction and measurements are coherent, but causal attribution and independent generalization remain limited.

Presentation: 4/4 — The paper is exceptionally transparent about protocols, chronology, failures, denominators, and claim boundaries.

Significance: 3/4 — Verified multi-route repair is practically relevant, but the demonstrated setting and resource requirements constrain broader significance.

Originality: 3/4 — The combination of immutable anchors, unresolved-only branching, and recursive promotion is distinctive, although its core union operation is mechanically simple.

Overall recommendation: 3/6 — Borderline; the system result is promising, but its comparative advantage is not yet prospectively or resource-normalized established.

Confidence: 4/5 — The paper is sufficiently self-contained for a substantive assessment, though the underlying artifacts and runs cannot be independently verified here.

## Ethics and Limitations

The paper uses public coding benchmarks and no human participants. It appropriately discusses test-feedback leakage, licensing, increased inference compute, finite-test correctness, runtime deviations, and nondeterministic or cross-task verifiers. The principal limitations are one-model evaluation, whole-track call clustering, post hoc stages in several comparisons, unequal realized resources, limited independent sessions, unvalidated semantic diagnoses, and the restricted test-available setting. These limitations are generally disclosed candidly.

## Comment

I recommend a borderline decision. The paper convincingly demonstrates that verified preservation combined with multiple heterogeneous repair routes can improve benchmark scores under additional bounded compute. The most important issue is to determine whether the reported advantage over simpler same-call portfolios is reproducible under a prospectively frozen, token- and latency-matched protocol, and whether semantic overlap contributes beyond generic prompt-induced trajectory diversity.
