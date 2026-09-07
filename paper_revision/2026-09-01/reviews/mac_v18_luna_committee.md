# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper presents Mini Artichokes, a five-call program-repair system that preserves complete task solutions passing an external verifier as byte-exact anchors, applies heterogeneous repair routes only to unresolved tasks, and recursively promotes newly verified solutions. It also introduces TOV, an overlap-aware route that uses behavioral agreement and disagreement to guide falsification. The system shows substantial gains over one- and two-call baselines on complete Aider tracks, but the evidence does not cleanly establish that recursive verification or semantic overlap provides a causal advantage over simpler, equally resourced generic multi-attempt strategies.

## Strengths

- The paper articulates a clear and practically relevant systems principle: “a complete verified task state is removed from model discretion, only unresolved units are branched, and passing states from heterogeneous routes are recursively promoted.”

- The preservation mechanism is formally precise. Under assumptions A1–A5, the construction copies complete passing file tuples, so “no unverified merged state is created.” The paper appropriately distinguishes test-label preservation from semantic correctness beyond the supplied tests.

- The evaluation retains complete benchmark tracks. It reports “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” followed by complete Go, JavaScript, and HumanEvalFixDocs evaluations rather than selected or topped-up subsets.

- The end-to-end results are substantial in the stated test-available setting. Mini Artichokes reaches “59/90 (65.6%)” versus “15/90 (16.7%) for Plain” and “45/90 (50.0%) for ordinary repair.” On the cleanly frozen JavaScript track it reaches “47/49” versus 42/49 for ordinary repair and 27/49 for Plain.

- The paper includes meaningful controls and negative evidence. It reports that the earlier strict agreement rule “solved 5/20 tasks versus 7/20,” that QuixBugs was already at “40/40,” and that HumanEvalFixDocs reached “164/164” with ordinary repair.

- The authors are unusually candid about claim scope. The claim table marks a “repeatable standalone semantic-relation effect” as “Not established,” while the conclusion characterizes semantic overlap as “a productive heterogeneous falsification route, not a universal or 20-point causal gate.”

- Integrity and failure handling are treated seriously. The paper retains the Rust `fizzy` harm, reports a forbidden `a.out` in one C++ call, and states that the Go transport-null invocation “does not retroactively restore confirmation.”

## Weaknesses

- The main gains over Plain and ordinary repair are confounded by additional test-time computation. Mini Artichokes uses five calls, compared with one for Plain and two for ordinary repair; the paper itself calls these “nested one-, two-, and five-call systems.” Thus the large improvements establish bounded-compute effectiveness, but not superiority of the proposed structure at matched resources.

- The strongest same-call comparison is post hoc. The 59/90 versus 54/90 result was “chosen after final-route crossovers were observed,” and the paper explicitly labels it “a post-hoc equal-call system contrast.” The recursive composition was likewise chosen after observing crossovers, while the Go Generic replacement was run only after TOV outcomes were known.

- Prospective evidence does not establish a reliable TOV advantage. The new replications produce only “+3.53 pp” and “+1.54 pp,” with intervals `[-2.35,+8.24]` and `[-6.92,+11.54]`. Go yields 33/39 versus 31/39 with `p=.3125`, while JavaScript and HumanEvalFix are ties. This supports possible route complementarity, but not a stable semantic-overlap effect.

- Recursive union is mechanically a best-of-included-routes construction: `V_rec(t)=max(V_F(t),V_D(t))`. Its advantage can therefore arise from adding another route and verifier-selecting complementary successes, rather than from the correctness of TOV’s semantic reasoning. The paper acknowledges that this dominance “uses an additional direct route.”

- The semantic ablation is not a clean causal intervention. The control “cannot make latent model trajectories identical,” and the authors state that ledger integrity checks “do not score the natural-language diagnoses for semantic correctness” and that “ledger diagnoses were not independently annotated.” Improvements may therefore reflect prompt-induced trajectory changes, structured reasoning, or compute differences rather than semantic overlap itself.

- Statistical precision is limited by the whole-track call structure. “Each task vector is generated inside one whole-track call,” so task-level tests condition on correlated realized trajectories. The paper’s own cluster checks over three tracks are underpowered (`p=.125` and `p=.5`), and five sessions in each of two fixed tracks do not support broad population-level claims.

- Generality is narrow. The applicability contract requires “task-local declared files,” “isolated workspaces,” and a “stable verifier,” while the experiments use one model/runtime and primarily modular, test-available benchmark tasks. The paper explicitly says this is “not a standard one-shot leaderboard protocol,” and the results do not yet establish transfer to larger repositories, weaker or noisy tests, cross-task dependencies, or test-unavailable repair.

## Questions for the Authors

1. Can you evaluate Mini Artichokes against a prospectively frozen generic five-call verifier-based baseline with matched total token/reasoning budget and the same evaluator access?

2. What are the separate contributions of candidate diversity, anchoring, TOV, the second final route, and recursive promotion under a precommitted factorial or sequential ablation?

3. Can blinded independent annotators assess TOV ledger diagnoses, and do diagnosis quality or falsification success predict verified repair outcomes?

4. How sensitive are results to the fixed priority rule, failure-tail length, file allowlist, task partition, and verifier nondeterminism?

5. Can the method be tested on cross-task repositories, weaker tests, larger real-world repair tasks, or additional models and independent sessions?

## Scores

Soundness: 3/4 — The preservation property and experimental reporting are coherent, but causal attribution is limited by post-hoc design, correlated whole-track calls, and unmatched realized compute.

Presentation: 4/4 — The paper is exceptionally transparent about chronology, claim scope, controls, failures, and limitations, although the many evaluation stages make the evidence hierarchy somewhat difficult to parse.

Significance: 3/4 — Verifier-backed task preservation is practically useful in test-available repair, but the demonstrated scope and advantage over simpler multi-attempt methods remain limited.

Originality: 3/4 — The composition of immutable task anchors, unresolved-task branching, and recursive verifier promotion is a credible systems contribution, although its ingredients are individually familiar.

Overall recommendation: 3/6 — Borderline; the system results are promising, but stronger prospective and compute-matched evidence is needed to establish a general architectural advantage.

Confidence: 4/5 — The paper is sufficiently self-contained for a substantive assessment, although the underlying runs and artifacts cannot be independently verified here.

## Ethics and Limitations

The work uses public programming benchmarks and involves no human participants. It appropriately notes that failure output may reveal behavioral expectations and that passing finite test suites does not establish correctness beyond those tests. Important limitations include the single model and runtime, few independent sessions, cumulative and partly post-hoc evaluation, unmatched realized compute, possible weakness of benchmark tests, and dependence on modular task boundaries and stable verifiers. The increased inference cost is disclosed, but no efficiency advantage is claimed.

## Comment

I find the paper’s strongest contribution to be a well-specified and auditable verifier-backed preservation and route-union procedure for modular, test-available repair. The central issue is attribution: a prospectively frozen, resource-matched generic multi-attempt baseline with repeated independent sessions and mechanism-level ablations is needed to determine whether Mini Artichokes contributes beyond additional calls, route diversity, and mechanical best-of-route verification.
