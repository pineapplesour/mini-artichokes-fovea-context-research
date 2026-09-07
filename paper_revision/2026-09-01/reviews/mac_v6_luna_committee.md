# Review: Mini Artichokes: Bounded Verification for Selective LLM Arbitration and Program Repair

## Summary

This paper proposes a bounded-update framework for LLM inference: preserve a frozen answer or program patch, invoke a second stage only after an observable conflict or failure, restrict the update, and audit rescues and harms. It reports improved direct-Luna performance on a 1,000-question MMLU-Pro replication and improved structured repair on five sessions over the same 20 Java tasks. The evidence is carefully qualified, but does not establish support metadata as causal or demonstrate broad task generalization.

## Strengths

- The arbitration policy is operationally precise: the trigger is “`D2=D3≠D1`,” the judge may select only “one of the two existing answers,” and invalid or non-conflict cases “return D1.” This makes the intervention auditable and conservative.

- The evaluation reports full-denominator results and paired rescue/harm accounting. On replication 2, OJ3 achieved “28 rescues, 5 harms, +23 correct,” with exact one-sided `p=3.31e-5` and a bootstrap interval of “[+1.2,+3.5] points.”

- The paper includes important controls and negative findings. OJ3 “tied SC3 at 613/1,000,” while its advantage over GJ3 was only descriptive (`p=.3633`); the legal reserve also showed “30 rescues but 59 harms.”

- The authors distinguish end-to-end evidence from mechanism attribution. They explicitly state that “support annotation did not beat a generic judge” and that “strict overlap authorization lost to matched Java repair.”

- The paper is unusually transparent about dependence and scope, acknowledging that the Java result “establishes session repeatability on that fixed set, not new-task generality” and that the coding study is “not a full 225-task Aider leaderboard evaluation.”

## Weaknesses

- The central support-aware mechanism remains unresolved. OJ3 improves over D1, but “tied SC3 at 613/1,000” and exceeded GJ3 by only two answers (`p=.3633`). Thus, the demonstrated benefit may come from additional sampling and judging rather than support counts specifically.

- The MMLU-Pro significance result is conditional on one realized whole-file session per draw. The paper concedes that its tests “do not estimate between-session repeatability,” while D2 changed from “145/1,000” to “607/1,000” across cohorts. This instability makes the very small item-level p-value insufficient evidence for repeatability of the complete pipeline.

- The confirmatory status of replication 2 is not entirely straightforward. It was authorized after confirmation 1 showed a favorable direction, even though the paper appropriately avoids pooling the cohorts for confirmation. A prespecified multi-stage design or independent same-task replication would provide stronger protection against selection effects.

- The coding improvement is confounded with a bundled second pass and privileged execution feedback. Matched repair combines “failure feedback, counterexamples, preservation, and double audit,” and uses two calls versus one for Plain. The strict-overlap comparison tests only one component; it does not identify which parts of the bundle cause the gain.

- Coding generality is narrow. The strongest result reuses “the same 20 Java tasks” across five sessions, and the cross-language result has “only three whole-batch call clusters.” The evidence supports repeatability on this fixed set, not performance on unseen tasks.

- The accuracy gains are expensive: OJ3 consumed “45,973,780 tokens versus 13,009,321 for D1,” a 3.53-fold ratio, for a 2.3-point replication improvement. The paper reports this honestly, but does not establish when the trade-off is preferable to simpler compute-matched alternatives.

## Questions for the Authors

1. Can you estimate between-session variance through repeated runs on the same MMLU-Pro questions, using the whole-file session as the inferential unit?

2. How would the MMLU-Pro conclusion change under a fully prespecified sequential or two-stage testing protocol that accounts for authorizing replication after the first cohort?

3. Can matched repair be compared with a generic second-pass repair receiving the identical Graph patch and failure output?

4. Which components—failure feedback, requirement reconstruction, counterexamples, preservation, or double audit—are necessary for the coding improvement?

5. What is the performance and cost of an unconditional compute-matched generic judge or additional-draw baseline without the proposed conflict trigger?

## Scores

Soundness: 3/4 — The protocols, controls, and limitations are carefully reported, but whole-file dependence and unresolved mechanism attribution limit the strength of the main claims.

Presentation: 4/4 — The paper is clear, well organized, and consistently separates confirmatory, descriptive, and unsupported conclusions.

Significance: 3/4 — The bounded-update framing and measured gains are useful, but the improvements are narrow and costly.

Originality: 3/4 — The common contract is a plausible empirical synthesis, although its individual ingredients draw on established sampling, judging, reasoning, and repair methods.

Overall recommendation: 3/6 — Borderline; the paper provides credible evidence for specific two-pass policies but not yet for a distinct support-aware mechanism or broadly general principle.

Confidence: 3/5 — The paper is sufficiently self-contained to assess, but the numerical results and execution artifacts cannot be independently rerun here, and the unusual session-level design complicates inference.

## Ethics and Limitations

The paper appropriately reports its substantial compute cost and warns against using same-model agreement in high-stakes settings. The legal data may remain re-identifiable; the authors state that they did not establish “full de-identification” and withhold item texts pending governance review. The stated limitations concerning single-model evaluation, whole-file context effects, fixed Java tasks, missing local compilation, approximate compute matching, bundled repair components, and limited cross-domain evidence are all scientifically material.

## Comment

I recommend borderline consideration. The strongest contribution is the disciplined separation of end-to-end improvement from mechanism attribution, supported by full-denominator evaluation and candid null and negative results. The most important revision is to establish whether bounded verification contributes beyond extra compute and bundled feedback-based repair, through repeated fixed-protocol runs, compute-matched generic controls, and component-level ablations.

## Area-chair mode

> Soundness capped at 2/4: 22 proven integrity breach(es). Overall recommendation capped at 2/6: 22 proven integrity breach(es).
