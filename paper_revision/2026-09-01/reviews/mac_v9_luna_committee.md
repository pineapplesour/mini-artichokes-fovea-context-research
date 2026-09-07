# Review: Mini Artichokes: Anchored Semantic-Overlap Verification for LLM Program Repair

## Summary

This paper proposes Anchored Try--Semantic-Overlap--Verify (TOV), a code-repair pipeline that preserves test-verified patches and uses structured semantic comparison and falsification to repair unresolved tasks. On 90 complete Rust, Python, and C++ Aider tasks, TOV achieves 58/90 versus 51/90 for a matched generic critic and 15/90 for Plain. The results are promising but remain conditional on a small number of whole-track executions and an unablated final-stage bundle.

## Strengths

- The paper provides a concrete preservation mechanism: “all full solution-file bytes for these tasks become anchors,” and reports that “all verified anchors survived byte-exactly.”

- The matched comparison controls many important confounds. TOV and the generic critic share “all three candidate calls, per-task outcomes, bounded failure traces, evidence serialization, verified union, byte-restoration adapter, model, reasoning effort, one final call, and budget cap.”

- The evaluation avoids task selection within the reported tracks. Table 5 includes “Rust, all 30,” “Python, all 34,” and “C++, all 26,” while the protocol states: “No task is ranked, screened, dropped, or added after scoring.”

- The distinction between behavioral and textual overlap is well articulated: “Semantic overlap means convergence on the same behavioral obligation, not textual intersection of edited lines.”

- The paper reports a meaningful matched result: TOV obtains “58/90 versus 51/90 for a generic final Critic,” with “seven correct tasks with no losses.”

- The authors are unusually transparent about limitations, explicitly stating that “a cluster-level one-sided sign test is `.125`” and that task-level inference is conditional on “one realized whole-track call per shared candidate.”

## Weaknesses

- The main mechanism is not isolated. TOV requires “one ledger row per unresolved task” with seven fields, an explicit “falsification attempt,” a “requirement-to-diff audit,” and a “separate completion audit,” whereas the generic critic is “instructed only to preserve anchors, inspect the supplied evidence, and fix unresolved tasks.” The resulting 7-task gain supports the bundled TOV procedure, but not semantic overlap specifically. The paper itself concedes that “it does not separately identify the ledger, semantic fields, falsification step, or two audits.”

- The coding result has only three independent whole-track clusters and one realized final call per arm. Although the task-level comparison is `58/90` versus `51/90` with `p=.0078125`, the paper also reports that the three-cluster sign test is `.125`. Thus, the evidence supports a conditional observation on these realized calls, but not a precise estimate of repeatable performance across sessions, languages, or model instances.

- The large comparison with Plain is heavily confounded by inference budget and candidate generation. TOV uses “four semantic calls versus one for Plain,” and the paper reports a “3.53-fold ratio” in tokens for OJ3 relative to D1. The 43-task improvement therefore primarily establishes an expensive end-to-end system effect; the scientifically central incremental result is the much smaller 7-task matched difference.

- TOV and the generic critic are matched in nominal calls and caps but not exactly in realized computation. The paper states that “actual cached/uncached tokens and time were not identical,” and reports final-call times of 543.5 versus 433.3 seconds on Rust, 439.3 versus 395.8 on Python, and 439.5 versus 404.5 on C++. The comparison therefore does not establish a cost- or wall-clock-matched accuracy advantage.

- Generality is limited. The paper acknowledges that “the primary coding evidence covers three complete official language tracks, not the complete six-language Aider benchmark,” uses only `gpt-5.6-luna`, and has no repeated same-track runs. The positive results across Rust, Python, and C++ are encouraging but insufficient for a broad program-repair claim.

- The semantic ledger is not independently evaluated. The paper requires exactly `|U|` ledger rows, but reports neither examples of successful or failed ledger reasoning nor an analysis showing that ledger quality predicts repair success. The ledger may be a useful structured prompt, but its semantic-overlap content is not demonstrated to be the active ingredient.

- The negative legal result is informative as a caution but weak as a boundary test. The paper reports “30 rescues but 59 harms,” while also admitting that the setup “simultaneously changes domain, task, prompt, and label structure.” It therefore cannot determine whether the failure arises from underdetermined evidence, domain difficulty, prompting, or binary labeling.

## Questions for the Authors

1. What are the results of ablations separating the ledger, semantic-overlap fields, falsification requirement, requirement-to-diff audit, and completion audit?

2. How often does the 7:0 matched advantage persist when the same frozen candidate and evidence artifacts are processed by repeated independently initialized final calls?

3. Can the generic critic be given the same output schema, audit obligations, and effective token budget while withholding only the semantic-overlap decision rule?

4. How many tasks are solved by the verified union before final adjudication, and how many unresolved tasks are successfully changed by TOV versus the generic critic?

5. Can the authors evaluate additional complete language tracks or repeated complete-track sessions to estimate session-level variance?

## Scores

Soundness: 3/4 — The preservation contract and matched artifact-sharing design are strong, but the treatment is bundled and inference rests on three correlated whole-track executions.

Presentation: 3/4 — The paper is clear and unusually transparent, though the many regimes and extensive result hierarchy make the central contribution less focused.

Significance: 3/4 — A repeatable 7.8-point gain over a matched final procedure would be valuable, but its robustness and scope are not yet established.

Originality: 3/4 — The anchored preservation and disagreement-as-falsification composition is plausible and well motivated, although its ingredients largely derive from existing methods.

Overall recommendation: 3/6 — Borderline; promising evidence for a bounded coding procedure, but insufficient replication and component ablation for a strong acceptance recommendation.

Confidence: 3/5 — The paper is sufficiently self-contained to assess, but the decisive execution artifacts and stochastic behavior cannot be independently verified here.

## Ethics and Limitations

The paper responsibly reports its computational cost, including “45.97 million tokens across the two OJ3 cohorts,” and explicitly states that official tests “are not a proof of semantic correctness beyond the benchmark.” Its treatment of legal data is appropriately cautious: it notes that “full de-identification” was not established and withholds item texts and outputs pending governance review.

The main scientific limitations are the single model and runtime, whole-file session dependence, correlated same-model candidates, approximate compute matching, sparse MMLU arbitration conflicts, incomplete language coverage, and the inability to attribute the coding gain to individual TOV components.

## Comment

I recommend borderline consideration. The strongest evidence is the 58-versus-51 comparison against a matched generic critic, not the much larger compute-confounded improvement over Plain. The most important revision is to establish, through repeated frozen-artifact executions and component-level ablations, whether the observed gain comes from semantic-overlap adjudication itself or from the broader structured prompting, falsification, and audit bundle.
