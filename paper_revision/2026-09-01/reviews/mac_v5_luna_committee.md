# Review: Mini Artichokes: Bounded Verification for Selective LLM Arbitration and Program Repair

## Summary

This paper proposes a bounded-update framework for inference-time correction: freeze a base answer or artifact, trigger a separate stage only on observable conflict or failure, restrict the update, and preserve unaffected work. Support-aware arbitration improves one direct Luna run on a pre-frozen MMLU-Pro replication, while structured repair improves Plain Luna on three small Aider batches. However, the evidence does not establish support metadata or overlap authorization as the causal mechanism, nor does it yet demonstrate broad repeatability or generality.

## Strengths

- The paper clearly separates routing from evidence: “agreement identifies cases worth re-examining,” while “the judge may use the number of supporting draws.” This is a useful and testable conceptual distinction.

- The arbitration protocol is concrete and conservative. It fixes D1 as the base, defines conflicts as “D2=D3≠D1,” anonymizes candidate provenance, forbids synthesis of a third answer, and uses a “base-preserving fallback.”

- The primary MMLU-Pro result is reported on the full denominator with paired accounting: “OJ3 scored 613/1,000 versus D1's 590/1,000,” with “28 rescues, 5 harms” and a bootstrap interval of “[+1.2,+3.5] points.”

- The authors are unusually candid about what the experiments do not show. They state that “support annotation did not beat a generic judge,” that OJ3 “tied SC3,” and that “the support annotation's incremental causal effect is unresolved.”

- The coding study uses meaningful external evidence rather than purely intrinsic critique. The repair stage receives “complete failure stdout,” derives counterexamples, preserves passing work, and audits completion against the original task.

- The paper reports informative negative results, including the legal reserve where OJ3 produced “30 rescues but 59 harms,” and the Java ablation where strict overlap authorization scored “5/20” versus “7/20” for matched repair.

- The presentation is strong. The explicit claim hierarchy, rescue/harm accounting, cost reporting, and separation of confirmatory from descriptive evidence make the empirical claims relatively easy to audit.

## Weaknesses

- The confirmatory interpretation is weakened by execution-level dependence. Each draw processes 1,000 questions in “one complete-file agent session,” while the paper admits that the results “do not estimate between-session repeatability.” The extreme D2 variation—from “145/1,000” to “607/1,000”—suggests that item-level McNemar tests and bootstraps may understate uncertainty for the realized pipeline.

- The primary replication was authorized after the first cohort had been scored. Although the authors transparently designate replication 2 as primary and avoid pooling it for confirmation, the decision to run one additional cohort was informed by a favorable first-cohort direction: confirmation 1 showed OJ3 at “601 versus D1 597.” This makes the nominal confirmatory interpretation less clean than a fully pre-registered multi-cohort design.

- The distinctive support-aware mechanism is not established. OJ3’s advantage over GJ3 is only “5 rescues, 3 harms” with `p=.3633`, and OJ3 ties SC3 at 613/1,000. The evidence supports an expensive multi-call system with generic arbitration more clearly than it supports support counts specifically.

- The D2 anomaly is not sufficiently diagnosed. Calling it an “extreme low outlier” does not explain whether it arose from malformed outputs, mapping failures, context effects, ordering, or runtime degradation. Because candidate agreement and arbitration depend on these sessions, the missing invalid-output and trace analysis is scientifically important.

- The coding transfer is not a clean fixed-method replication. The paper acknowledges that “batch 2 corrected one language-specific packaging sentence” and that “the Java repair lead was strengthened before its sample was frozen.” Thus, the 29/60 aggregate is appropriately described as a family summary, but it cannot provide strong evidence for one frozen method.

- Coding inference is limited by whole-batch dependence. Each batch shares “one whole-batch model invocation,” leaving only three call clusters per arm; correspondingly, the cluster-level sign test is only `p=.125`, despite the much smaller task-level `p=.00418`. The latter should not be interpreted as broad population-level evidence.

- The common framework remains more a design principle than a demonstrated unified algorithm. Multiple-choice arbitration selects between two fixed answers, whereas coding uses “actual execution feedback,” requirement reconstruction, counterexample generation, preservation, and double audits. The paper itself calls this “a transfer of the bounded-update contract, not the same algorithm,” but does not show that the abstraction predicts when updates will help.

- The coding gain is bundled across several components. The Java experiment isolates strict overlap authorization, but does not separately test “requirement reconstruction,” “counterexample” generation, preservation, or the “two completion audits.” Consequently, the evidence supports a bundled repair recipe rather than a sharply characterized mechanism.

- Generality is limited. The study uses “one model, one runtime, and one primary benchmark,” while the coding evidence covers only “a 60-task subset of three languages.” The negative legal result further shows that the trigger can fail under partial evidence, so the broader framing should remain explicitly bounded.

## Questions for the Authors

1. Across repeated independent sessions on the same frozen MMLU-Pro questions, how often does OJ3 outperform D1 and GJ3, and what specifically caused the D2 result of “145/1,000”?

2. What were the invalid, malformed, and unmapped-output rates for D1–D3, especially D2, and how did output ordering or within-file context affect performance?

3. Can the coding study be repeated with one fully frozen repair prompt and multiple independent batches or call clusters, rather than the evolving “method-family summary” currently reported?

4. Which of requirement reconstruction, counterexample generation, preservation, and double auditing accounts for the coding improvement?

5. What accuracy-per-token or accuracy-per-second trade-off makes OJ3 preferable to SC3 or GJ3, given that it uses “3.53 times D1's tokens” without significantly outperforming GJ3?

## Scores

Soundness: 3/4 — The protocols and reporting are careful, but whole-file dependence, post-cohort replication authorization, and limited coding clusters weaken the statistical claims.

Presentation: 4/4 — The paper is exceptionally clear about protocols, costs, claim boundaries, and negative results.

Significance: 2/4 — The observed gains are modest or narrowly scoped, expensive, and not superior to the strongest compute-matched arbitration control.

Originality: 3/4 — The bounded-update contract and its explicit rescue/harm analysis are useful, although the underlying sampling, judging, and repair components are established.

Overall recommendation: 3/6 — Borderline; the paper presents a careful empirical observation and valuable negative evidence, but does not yet establish a repeatable, mechanism-specific, general contribution.

Confidence: 3/5 — The paper is sufficiently self-contained for substantive judgment, but the decisive execution artifacts and between-session variability cannot be independently assessed here.

## Ethics and Limitations

The paper responsibly reports the resource burden of “45.97 million tokens across the two OJ3 cohorts” and warns against deploying same-model agreement in high-stakes settings. Its treatment of the legal data is appropriately cautious: it “did not establish full de-identification of facts,” and withholding item texts pending governance review is prudent. The main limitations are the single-model setting, whole-file session dependence, anomalous D2 run, small number of coding call clusters, evolving coding prompts, limited benchmark coverage, and lack of causal isolation for the proposed mechanisms.

## Comment

I recommend borderline consideration. The paper’s strongest contribution is its disciplined distinction between an end-to-end benefit from additional structured inference and a mechanism-specific benefit from overlap metadata; the evidence supports the former only in bounded settings and does not support the latter. The most important revision is a fully frozen, independently repeated evaluation—especially for the MMLU-Pro sessions and coding call clusters—that diagnoses the D2 anomaly and isolates which repair or arbitration components produce repeatable gains.

> Soundness capped at 2/4: 25 proven integrity breach(es). Overall recommendation capped at 2/6: 25 proven integrity breach(es).
