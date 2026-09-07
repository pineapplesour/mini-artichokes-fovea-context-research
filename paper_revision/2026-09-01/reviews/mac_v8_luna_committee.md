# Review: Mini Artichokes: Bounded Verification for Selective LLM Arbitration and Program Repair

## Summary

This paper studies bounded second-pass inference: freeze a base answer or code patch, trigger review only on an observable conflict or failure, constrain the update, and preserve unaffected work. It reports a +2.3-point gain over direct Luna on a 1,000-question MMLU-Pro replication and repeatable improvement on one fixed 20-task Java set. However, support-aware arbitration does not beat a generic judge, and structured repair does not beat ordinary failure-feedback repair, substantially narrowing the demonstrated contribution.

## Strengths

- The arbitration policy is precise and reproducible: “D1 is the base, and D2/D3 are auxiliary draws,” with review only when “D2=D3≠D1.”

- The evaluation reports full-denominator outcomes and rescue/harm accounting. On replication 2, OJ3 achieved “28 rescues, 5 harms, +23 correct.”

- The paper uses strong controls and avoids overstating mechanism attribution: OJ3 “tied SC3 at 613/1,000” and its “+2 point estimate over GJ3” was explicitly described as non-conclusive.

- The expected-gain identity, “Δ = τ (q01 s01 - q10 s10),” is a useful formalization of why bounded updates can help or hurt without assuming independent model errors.

- The authors are unusually candid about negative evidence, including that the legal reserve produced “30 rescues but 59 harms” and that strict overlap repair scored “5/20 versus 7/20.”

- The coding analysis appropriately treats the “independently initialized 20-task whole-batch session as its inferential unit,” rather than treating the 20 tasks in one call as independent observations.

- Provenance and reproducibility are well documented through benchmark commits, frozen protocols, accepted outputs, scorer hashes, and explicit artifact descriptions.

## Weaknesses

- The MMLU replication is outcome-informed at the study-design level. The paper states, “Because the direction was favorable but underpowered, we froze exactly one disjoint 1,000-question replication.” Although replication 2 was frozen before scoring and analyzed separately, the decision to run it and the choice to run exactly one follow-up were motivated by the first result. The nominal `p=3.31e-5` is therefore not equivalent to evidence from a fully prospective confirmatory plan.

- The central support-aware mechanism is not established. OJ3 improved over D1, but “tied SC3 at 613/1,000” and was not significantly better than GJ3 (`p=.3633`). Since GJ3 receives the same trigger, candidates, model calls, and near-matched compute, the evidence supports additional candidate judgment after sampling, not a causal benefit from displaying support counts.

- The theoretical contribution is primarily an accounting identity. The equation “Δ = τ (q01 s01 - q10 s10)” correctly decomposes observed gains, but the paper gives no validated, domain-general criterion for predicting when agreement will be informative rather than a correlated shared error. The negative legal result, where the supported outcome was correct only “49.2%” of the time, underscores this unresolved issue.

- The coding evidence is narrow. The strongest result uses “the same 20 Java tasks” across five sessions and therefore demonstrates same-task session repeatability, not new-task generalization. The earlier 60-task study has only “three whole-batch call clusters,” making its task-level inferential statistics vulnerable to within-call dependence.

- The coding mechanism control was added after the main outcomes were known. The ordinary arm was commissioned “after the five-session matched results ... were known,” and it scored 27/100 versus 25/100 for matched repair. This is useful exploratory evidence, but it cannot cleanly establish that generic failure feedback, rather than the proposed structured operations, is the causal ingredient.

- The two experimental regimes share a broad behavioral analogy but materially different mechanisms. Multiple-choice arbitration selects between two fixed answers, whereas repair edits code using private execution feedback. The paper appropriately calls this “a transfer of the bounded-update contract,” but freeze/inspect/update/preserve alone is too general to establish a unified algorithmic contribution.

- Whole-file execution creates unresolved system variance. One D2 session scored “145/1,000,” while another scored 607/1,000, and “no MMLU-Pro pipeline was rerun on identical items.” The reported item-level tests condition on realized sessions and do not quantify repeatability across initialization, ordering, or context effects.

- The practical cost is substantial relative to the demonstrated gain. OJ3 consumed “45,973,780 tokens versus 13,009,321 for D1,” a 3.53-fold ratio, for a 2.3-point improvement. The paper reports this honestly, but does not provide monetary cost or a sufficiently normalized quality-at-fixed-budget comparison.

## Questions for the Authors

1. What was fixed or registered before confirmation 1 was scored regarding the decision to run replication 2, its size, and its primary hypothesis? What inferential status should `p=3.31e-5` have under this outcome-informed sampling decision?

2. Can OJ3 and GJ3 be compared prospectively on a disjoint cohort with enough triggered conflicts to estimate the support-count effect rather than merely the value of generic judging?

3. Can the MMLU protocol be rerun across independent complete-file sessions on the same items, or otherwise provide an estimate of whole-file session variance?

4. Why was a prospective Plain-plus-ordinary-repair arm not included in the original coding design, and how would its results change the interpretation of the Graph-plus-repair path?

5. Can the coding method be evaluated on newly sampled tasks, languages, or repositories with the ordinary control and all repair prompts frozen before outcomes are observed?

6. What are the monetary costs and quality trade-offs against simpler alternatives such as one additional direct draw or a compute-matched generic judge?

## Scores

Soundness: 3/4 — The protocols, controls, and limitations are carefully presented, but outcome-informed replication, whole-session dependence, and unresolved mechanism attribution limit the evidential strength.

Presentation: 4/4 — The paper is clear, well organized, and unusually disciplined about separating established results from exploratory or unsupported claims.

Significance: 3/4 — The evidence supports a potentially useful failure-feedback second pass, but the gains are costly and demonstrated only in narrow settings.

Originality: 3/4 — The bounded-update framing and cross-regime analysis are coherent and useful, although the tested components do not outperform simpler compute-matched alternatives.

Overall recommendation: 3/6 — Borderline: the paper offers careful and valuable empirical evidence, but its generality and central mechanism claims are not yet sufficiently supported.

Confidence: 4/5 — The paper is self-contained and detailed enough for a substantive assessment, though the underlying executions and artifacts cannot be independently verified here.

## Ethics and Limitations

The paper appropriately discusses the risk of treating same-model agreement as reliability evidence, especially given the negative legal result. Its handling of legal data is cautious: it states that it “did not establish full de-identification of facts” and withholds item texts and outputs pending governance review. It also reports the substantial compute burden of “45.97 million tokens across the two OJ3 cohorts.”

The main limitations are the single-model evaluation, possible benchmark contamination, whole-file context dependence, same-model correlated errors, small trigger set, fixed-task Java replication, incomplete coding coverage, approximate compute matching, and post-outcome commissioning of the ordinary repair control. The authors acknowledge these limitations candidly, but they materially constrain the claims to narrow end-to-end improvements.

## Comment

I recommend borderline. The paper’s strongest contribution is a careful demonstration that a separate pass using concrete execution failures can improve a frozen coding artifact in a particular regime, alongside credible negative evidence against overlap metadata and elaborate repair instructions as established mechanisms. The most important issue is prospective generalization: new tasks and models, with compute-matched controls fixed before outcomes, are needed to determine whether the observed gains exceed the generic benefit of additional failure-informed inference.

> Soundness capped at 2/4: 22 proven integrity breach(es). Overall recommendation capped at 2/6: 22 proven integrity breach(es).
