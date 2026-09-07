# Review: Mini Artichokes: Evidence-Overlap Gates for Selective LLM Arbitration and Repair

## Summary

This paper proposes a conservative inference-time update rule: preserve a base answer unless two auxiliary draws agree against it, then let an anonymous judge choose between the existing candidates. A related coding system uses requirement, implementation, and test-output overlap to localize repairs. On two 1,000-question MMLU-Pro cohorts, the support-aware system improves direct Luna by 1.35 percentage points, but not compute-matched generic judging or majority voting. The coding transfer improves Plain Luna, but not ordinary same-budget repair. Thus, the paper provides credible evidence for additional inference and bounded repair, while its central claim about overlap-specific benefit remains unresolved.

## Strengths

- The arbitration policy is precise and conservative. It defines the trigger as “`D1, D2, and D3 are all valid and D2=D3≠D1`” and otherwise returns the base answer.

- The primary evaluation uses full-denominator, paired comparisons on “two disjoint, category-proportional 1,000-question samples,” with fixed draw roles and an explicit two-look alpha boundary.

- The main result is quantitatively meaningful against the direct baseline: OJ3 obtains “1,214/2,000 (60.70%) versus 1,187/2,000 (59.35%),” with “33 rescues and 6 harms” and a bootstrap interval of “+0.75 to +1.95 percentage points.”

- The paper appropriately distinguishes end-to-end utility from mechanism attribution. It explicitly states that “the supported superiority claim is OJ3 over direct Luna, not over either strong multi-call control.”

- Negative results and costs are reported candidly. The legal reserve produced “30 rescues but 59 harms,” while Table 4 reports “45,973,780” OJ3 tokens versus “13,009,321” for D1.

- The coding study includes an important same-budget control: ordinary repair receives “the same Graph state, failures, model, and second-call budget,” and the proposal scores only 22/40 versus 21/40.

## Weaknesses

- The central mechanism is not established. OJ3 exceeds GJ3 by only “+3” answers with `p=.25391`, and the paper itself says that “the support annotation's incremental causal effect is unresolved.” In coding, overlap repair scores 22/40 versus 21/40 for ordinary repair with “`p=1.0` two-sided.” The evidence therefore supports selective arbitration or a second repair pass, not overlap metadata specifically.

- The confirmatory continuation raises an unresolved inferential concern. The second cohort was run “because the direction was favorable but underpowered,” after the first cohort had been scored. The stated “conservative one-sided alpha=.025” does not by itself establish validity of the pooled p-value when continuation depends on the first result; the authors should provide a formal pre-specification or valid alpha-spending/combination argument.

- The complete-file session design limits repeatability claims. Each draw “processed all 1,000 public rows in one isolated complete-file session,” while D2 scored “145/1,000” in confirmation 1 and “607/1,000” in replication 2. The paper acknowledges that its tests quantify uncertainty “conditional on the realized sessions, not between-session variance.” This is adequate for describing these realized outputs, but it is weak evidence that the complete pipeline will reproduce the gain across independent executions.

- The coding intervention does not isolate overlap from broader prompt changes. The proposed arm “reconstructs three views,” derives a “minimal counterexample,” and performs “two completion audits,” whereas ordinary repair “simply fixes the failures.” Equal call counts do not make these interventions causally comparable.

- The theoretical basis for the support record is underdeveloped. The paper shows that “both candidates were wrong on 20/68 conflicts” and concedes that same-model sessions “can share systematic errors,” but gives no calibration or error-correlation condition under which a 1-versus-2 support count should improve a judge’s decision. The method remains a plausible heuristic rather than a theoretically grounded selective rule.

- The practical accuracy-cost tradeoff is not compellingly characterized. OJ3 uses “3.53 times the direct tokens” for a “+1.35 percentage point” gain, yet there is no cost-normalized frontier comparing it with alternative allocations of the same budget, such as additional direct draws or repeated generic judging.

- Generalization is limited. The paper evaluates “one model, one runtime, and one primary benchmark,” while the coding transfer covers “40 tasks from only Python and Rust” and only “two independent batch calls per arm.” The legal negative result is useful but changes “domain, task, prompt, and label structure” simultaneously, so it does not identify the conditions governing transfer.

## Questions for the Authors

1. Was the decision to collect replication 2 and the pooled analysis specified before confirmation 1 was scored? If continuation was conditional, what valid sequential-testing argument supports the reported pooled p-value?

2. What caused D2’s “145/1,000” result, and does the OJ3 gain persist across repeated complete-pipeline executions on the same frozen questions?

3. Can OJ3 and GJ3 be rerun repeatedly on an identical conflict set, with byte-identical prompts except for the support record, to estimate the support annotation’s effect?

4. Can the coding ablation equalize all reasoning, counterexample, and completion-audit instructions while varying only explicit overlap information?

5. How does OJ3 compare with alternative strategies using the same token or latency budget, including additional direct samples and repeated generic judging?

6. How sensitive is the result to which draw is designated as the base, and to randomized or misleading support counts?

## Scores

Soundness: 3/4 — The protocol is careful and transparent, but adaptive continuation, whole-session instability, and unresolved mechanism attribution limit the strength of the conclusions.

Presentation: 4/4 — The paper is exceptionally clear, well organized, and detailed about controls, costs, statistical boundaries, and limitations.

Significance: 2/4 — The direct-baseline gain is potentially useful, but it is modest, expensive, and not shown to arise from the proposed overlap mechanism.

Originality: 3/4 — The bounded update contract and cross-regime framing are interesting, although their ingredients draw substantially on established sampling, judging, and repair methods.

Overall recommendation: 3/6 — Borderline; the paper presents a credible and unusually honest empirical result, but its principal mechanism and repeatability claims require stronger evidence.

Confidence: 4/5 — The manuscript is sufficiently self-contained for substantive evaluation, although the execution artifacts and repeated-run behavior cannot be independently verified here.

## Ethics and Limitations

The paper appropriately reports that it uses no human participants and withholds potentially re-identifiable legal records and outputs. Its admission that metadata minimization “is not a claim of comprehensive de-identification” is important, as is the governance review for the five records with unrecoverable reuse metadata. The reported 45.97 million-token cost also makes the environmental and economic tradeoff relevant. The stated limitations concerning same-model correlated errors, whole-file session dependence, one-model evaluation, limited coding coverage, and two-call-cluster inference materially constrain generalization and should remain central to the claims.

## Comment

I recommend borderline acceptance or rejection depending on the venue threshold. The strongest contribution is a disciplined, base-preserving framework for deciding when additional inference may modify an existing answer or artifact, not a validated overlap mechanism. The single most important issue is mechanism attribution: repeated frozen-session evaluations and tightly matched placebo or permutation controls are needed to determine whether overlap itself helps beyond extra sampling, generic judging, and ordinary feedback repair.
