# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper proposes Mini Artichokes, a test-available program-repair system that preserves complete task solutions passing an external verifier as byte-exact anchors, repairs only unresolved tasks, and recursively promotes passing outputs from direct and semantic-overlap routes. It reports 59/90 passes on three complete Aider Polyglot tracks versus 45/90 for ordinary repair and 15/90 for Plain, plus 33/39 on a subsequently frozen Go39 track. The paper’s strongest claim is system-level effectiveness under additional bounded compute; its narrower claim that semantic overlap itself provides a reliable causal advantage remains unresolved.

## Strengths

- The anchoring mechanism is clearly specified and formally justified. Under A1–A5, “no unverified merged state is created,” since promotion copies “the complete allowlisted solution-file tuple for a task.”

- The evaluation uses complete denominators: “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” followed by “all 39 official Go tasks.” The paper states that no task was “ranked, screened, removed, replaced, or topped up.”

- The paper distinguishes test-label preservation from semantic correctness. It explicitly states that recursive promotion “does not guarantee correctness beyond those tests.”

- The system-level results are substantial within the stated setting. Mini Artichokes achieves “59/90 (65.6%)” versus “45/90 (50.0%)” for ordinary repair, and 33/39 versus 25/39 on Go39.

- The resource and inferential limitations are unusually candid. The authors state that these are “effectiveness comparisons between nested one-, two-, and five-call systems,” not efficiency results, and report that TOV takes “29.6 more seconds” than the semantic-free control.

- The failure and boundary evidence improves credibility. The paper retains the Rust `fizzy` harm caused by “an extra closing brace,” reports the earlier agreement-gate failure (“5/20 versus 7/20”), and notes that Plain reaches “40/40” on QuixBugs.

## Weaknesses

- The principal system comparison does not isolate recursive verified redundancy from extra computation and multiple candidate routes. The paper itself acknowledges that “Candidate diversity, external execution, the verified floor, and both final routes contribute.” Thus 59/90 versus 15/90 or 45/90 demonstrates an effective larger system, but not the incremental contribution of the proposed composition.

- The most relevant equal-call comparison is post hoc. The recursive analysis was “specified only after these repetitions revealed large branch crossovers,” and the 59/90 versus 54/90 result is explicitly “a post-hoc equal-call system contrast.” The Go comparator is not a full remedy because the preregistered Generic call was “transport-null,” while its replacement was run “after TOV outcomes were known.”

- The semantic-overlap mechanism is not convincingly established. The ten paired replications yield Python differences of `+4,-2,+2,0,+2` and C++ differences of `+1,-1,0,+5,-3`; their intervals are `[-2.35,+8.24]` and `[-6.92,+11.54]` percentage points. These results support a sometimes productive route, but not a stable standalone advantage.

- The statistical evidence is based on highly correlated task outcomes. “Each task vector is generated inside one whole-track call,” and task-level tests “condition on the realized calls.” The three-track sign checks (`p=.125` and `p=.5`) appropriately reveal how limited the independent experimental evidence is.

- The semantic-free control is not a clean causal intervention. Although it matches named fields and audits, it “cannot make latent model trajectories identical,” and realized compute differs: TOV uses 59,551 output tokens versus 54,728 and takes 1,422.3 versus 1,392.7 seconds.

- The formal generality is limited by the modularity assumptions. A1 requires task-local solution files and verifiers, while the paper also assumes “no cross-task test dependency,” “isolated workspaces,” and a “stable verifier.” These conditions exclude many realistic repository-level repair settings.

- The semantic explanation is post hoc and unvalidated. The interface-ambiguity pattern was “formulated after the nine discordant tasks were known,” and “ledger diagnoses were not independently annotated.” The paper therefore demonstrates a prompt-and-route effect, not a validated semantic mediator.

- Practical significance is uncertain without cost-normalized comparisons. Mini Artichokes uses five calls and intermediate evaluation, and is “intended for quality-sensitive repair, not cheap default completion.” No matched-token, latency, or monetary-cost comparison establishes whether its gains are attractive at a fixed deployment budget.

## Questions for the Authors

1. Can you run a prospective, call- and compute-matched comparison against a generic multi-route verifier union, with the route and analysis frozen before execution?

2. What are the separate contributions of candidate diversity, anchoring, recursive promotion, TOV, and the second final route under a factorial ablation?

3. Can the method be evaluated on more independent tracks, models, or runtimes, with model-call/session-level inference rather than primarily task-level tests?

4. Can independent annotators validate the TOV ledger fields and test prospectively whether their correctness predicts successful repair?

5. How does promotion behave with shared files, integration tests, nondeterministic tests, cross-task dependencies, weak tests, or unavailable test feedback?

## Scores

Soundness: 3/4 — The preservation construction is sound under explicit assumptions, but mechanism-specific causal evidence and independent experimental support are limited.

Presentation: 4/4 — The paper is clear about protocols, chronology, resource asymmetry, failures, and evidential boundaries.

Significance: 3/4 — Verifier-backed task-level promotion is useful, but demonstrated significance is confined to a narrow test-available repair regime.

Originality: 3/4 — The composition of immutable anchors, unresolved-set branching, and recursive promotion is interesting, although its ingredients draw on familiar verification and iterative-repair ideas.

Overall recommendation: 3/6 — Borderline; the system result is promising, but the central mechanism is not isolated strongly enough for confident acceptance.

Confidence: 4/5 — The paper is sufficiently self-contained to assess its logic and reported evidence, though the underlying experiments and artifacts cannot be independently rerun here.

## Ethics and Limitations

The paper uses public programming exercises and no human participants. It appropriately notes that failure output may reveal behavioral expectations and characterizes the setting as “test-available program repair.” Its substantive limitations include one model and runtime, correlated whole-track calls, few language clusters, post hoc control and recursive-route design, unvalidated semantic annotations, finite test suites, narrow task-modularity assumptions, and substantial additional inference compute. Passing tests certify only benchmark behavior, not correctness beyond the supplied suites.

## Comment

I recommend borderline. The clearest contribution is the well-defined verifier-backed preservation rule, which provides a credible way to retain complementary task-level successes without destructive patch merging. The authors should most urgently separate that structural benefit from extra calls, candidate diversity, and TOV by conducting a prospective, compute-matched ablation with more independent evaluation units.
