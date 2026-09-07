# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper presents Mini Artichokes, a five-call program-repair system that preserves complete task solutions passing an external verifier, edits only unresolved tasks, and recursively unions passing outputs from heterogeneous repair routes. It reports substantial effectiveness gains on complete Aider tracks—139/178 tasks versus 112/178 for ordinary repair and 59/178 for Plain—but the strongest evidence supports the broader verified multi-route system, not a reliable standalone causal effect from semantic overlap.

## Strengths

- The paper gives a clear structural preservation guarantee. Under assumptions A1–A5, promotion “copies either its prior anchored state or one complete state already observed to pass,” ensuring that verified task labels are not lost during later repair.

- The evaluation retains complete official denominators. It includes “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” followed by all 39 Go and 49 JavaScript tasks, rather than selecting favorable examples.

- The end-to-end results are substantial in the stated test-available setting. Mini Artichokes reaches 59/90 versus 45/90 for ordinary repair, 33/39 versus 25/39 on Go, and 47/49 versus 42/49 on JavaScript.

- The paper is unusually candid about null results and protocol failures. It reports an “exact 47/49 tie” on JavaScript, a HumanEvalFix ceiling where “ordinary repair also reaches 164/164,” and a Go Generic call that was “transport-null.”

- The evidential hierarchy is appropriately qualified. The paper explicitly states that the “supported conclusion” is verified preservation plus “semantic disagreement as one heterogeneous falsification route,” rather than a universal semantic-overlap certificate.

- The formal contribution is carefully bounded. The authors acknowledge that “a minimal task-wise verifier union is algebraically identical to this promotion rule” and do not claim that the union itself is a novel selector.

## Weaknesses

- The central semantic-overlap mechanism is not established prospectively. The original 58/90 versus 51/90 comparison used a control “frozen only after all TOV outcomes and the MAC v9 critique were known,” while the later five-pair replications have wide intervals, including `[-6.92,+11.54]` percentage points for C++.

- The strongest system comparison is not compute-matched against simpler baselines. Mini Artichokes uses five calls, compared with one for Plain and two for ordinary repair; the paper itself characterizes these as “nested system comparisons with additional calls.” The gains therefore establish effectiveness under additional test-time computation, not superiority over a comparable generic compute budget.

- The equal-call recursive result is partly post hoc. The recursive dual-route analysis was “specified only after these repetitions revealed large branch crossovers.” Although Go was later frozen prospectively, its replacement Generic arm was run “after TOV outcomes were known,” and JavaScript produced an exact tie.

- The proposed components remain bundled. The paper states that “candidate diversity, external execution, the verified floor, and both final routes contribute,” but does not provide a clean factorial ablation isolating immutable anchoring, unresolved-only branching, route multiplicity, and semantic-relational prompting.

- The semantic-free control does not isolate semantics from prompt-induced trajectory changes. It matches named fields and operations, but the paper concedes that the ablation “cannot make latent model trajectories identical.” The observed session differences—Python `+4,-2,+2,0,+2` and C++ `+1,-1,0,+5,-3`—show that this confound is consequential.

- The very small effective number of whole-track calls limits generalization of task-level significance. Although the paper reports values such as `p=5.68e-14`, it also acknowledges that “all task rows within one arm share one whole-track model call.” The track-level checks and replications are much less decisive, so the task-level p-values should not be read as broad population evidence.

- The ledger does not demonstrate that semantic overlap is actually being measured correctly. Integrity checks “do not score the natural-language diagnoses for semantic correctness,” and “ledger diagnoses were not independently annotated.” The improvement could therefore reflect additional prompt context or deliberation rather than meaningful overlap analysis.

- The applicability contract is materially narrower than general program repair. The theorem assumes “task-local declared files,” isolated workspaces, and stable verifiers, while many real repositories contain shared build state, generated files, integration tests, or nondeterministic tests. The guarantee is consequently test-label preservation under A1–A5, not correctness beyond the supplied suites.

## Questions for the Authors

1. What is the result under a prospective comparison matched on total tokens, latency, and evaluator cost against a generic multi-call verifier portfolio?

2. How much gain remains when anchoring, unresolved-only branching, the second route, and semantic-overlap instructions are ablated separately?

3. Can candidate disagreement be independently labeled and shown to predict successful TOV rescues?

4. Can the main system and component comparisons be repeated across multiple models or model versions with the harness held fixed?

5. How should promotion be modified for shared files, cross-task dependencies, nondeterministic tests, or repositories with global build state?

## Scores

Soundness: 3/4 — The preservation property is well specified and the reporting is careful, but causal attribution and generalization remain limited.

Presentation: 4/4 — The paper is exceptionally transparent about chronology, failures, null results, and claim boundaries.

Significance: 3/4 — Verified multi-route repair is practically useful, but the demonstrated benefit is confined to a test-available setting with additional computation.

Originality: 3/4 — The composition of immutable anchors, unresolved-only repair, and recursive verified union is a useful systems formulation, though several ingredients are established or mechanically implied.

Overall recommendation: 3/6 — Borderline; the system evidence is promising, but the principal mechanism is not yet supported by a clean prospective compute-matched evaluation.

Confidence: 4/5 — The paper is sufficiently self-contained for a reasoned assessment, though the underlying executions and artifacts cannot be independently verified here.

## Ethics and Limitations

The paper uses public programming exercises and no human participants. It appropriately discusses bounded test-output leakage, increased inference compute, licensing, runtime deviations, finite test specifications, and the distinction between benchmark passes and semantic correctness. The main scientific limitations are the use of one model and runtime, correlated candidates, whole-track call dependence, limited session replication, post hoc component controls, and the narrow A1–A5 applicability conditions. No hidden reviewer-directed text is present.

## Comment

I recommend borderline acceptance/rejection depending on the venue’s novelty threshold. The most important revision is a prospective, compute-matched evaluation against a generic multi-call verifier portfolio, with independently assessed semantic diagnoses and multiple whole-track sessions. This would clarify whether Mini Artichokes provides a substantive algorithmic advantage or primarily offers a well-engineered way to spend additional test-time computation while preserving observed passes.
