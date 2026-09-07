# Review Court and MAC-n-CHEESE synthesis for manuscript v8

## Scope

This synthesis uses the three valid Review Court v5 specialist reviews and the
MAC-n-CHEESE v5--v8 area-chair reviews to decide scientific revisions. It does
not treat evaluator execution, artifact packaging, a benchmark harness, or a
review-agent runtime as a paper contribution. Those facilities are provenance
and quality-control machinery only.

## Review records used

- Review Court v5 produced valid contribution/communication,
  experiments/reproducibility, and soundness/method specialist batches. Its
  final aggregation stage ended with `STAGE_DRIVER_FAILED`, so it produced no
  valid product score. The specialist findings remain usable; the terminal
  runtime failure is not evidence about manuscript quality.
- MAC-n-CHEESE v5: soundness 3/4, presentation 4/4, significance 2/4,
  originality 3/4, overall 3/6, confidence 3/5.
- MAC-n-CHEESE v6: 3/4, 4/4, 3/4, 3/4, overall 3/6, confidence 3/5.
- MAC-n-CHEESE v7 and v8: 3/4, 4/4, 3/4, 3/4, overall 3/6, confidence 4/5.
- The deterministic audit suffix that claims 22 integrity breaches is not a
  scientific score. Inspection showed that it compares unrelated metric names
  across experiments and therefore emits false contradictions. The prose
  area-chair scores above are the valid advisory judgments.

## Findings and dispositions

| Review finding | Disposition in v8 |
|---|---|
| Coding task outcomes shared a whole-batch call, so task-level tests were not cluster-robust. | Added five independently initialized, frozen 20-task Java sessions and made the session the inferential unit. Matched repair beat Plain and Graph in all five sessions; each one-sided exact sign test is `p=.03125`. |
| Coding prompts and batches changed across the earlier 60-task study. | The five-session result uses one frozen task set, prompt, scorer, and stopping rule. The earlier 60-task result remains descriptive. |
| The coding gain might be only a generic second repair call. | Added a review-triggered same-evidence ordinary-repair control. It scored 27/100 repeated task-session outcomes versus 25/100 for structured matched repair. The manuscript now rejects structured/overlap-specific superiority and attributes the supported effect at this resolution to a separate pass conditioned on real failure output. |
| Support counts were not isolated from generic judging. | OJ3's tie with SC3 and non-significant `+2/1000` over GJ3 remain prominent in the abstract, results, discussion, claim hierarchy, and conclusion. No causal benefit from support counts is claimed. |
| The first MMLU-Pro cohort contained an extreme D2 session. | Added the full 1,000-ID/order/schema audit: 1,000 complete records, no missing IDs, no constant label offset, and no parser or off-by-one explanation. The session is retained as unresolved semantic/session-trajectory instability, not silently repaired or discarded. |
| The paper needed a formal account of when a bounded update helps. | Added the exact identity `Delta = tau (q01 s01 - q10 s10)`, with no independence assumption, and mapped trigger prevalence, candidate quality/correlation, and switch behavior to rescue and harm. It is explicitly described as an accounting condition, not a validated universal predictor. |
| The cross-regime story risked implying one proven mechanism. | Narrowed the contribution to a bounded-update design pattern and rescue/harm accounting. Multiple-choice arbitration and program repair are presented as distinct realizations, not one causally unified algorithm. |
| Workflow and arm names were hard to follow. | Added a compact freeze--inspect--update--preserve workflow table, coding-arm glossary, claim hierarchy, and explicit confirmatory/descriptive/secondary labels. |
| Legal-item release and governance were underspecified. | States that full factual de-identification was not established and withholds item texts/outputs pending governance review. The negative legal result is retained. |
| Cost and practical value were unclear. | Reports token and latency totals and the 3.53x MMLU token ratio. No efficiency or fixed-budget superiority is claimed. |

## Current evidence-supported claim

The strongest coding result is session-repeatable on one frozen official Java
20-task set: structured matched repair improved over Plain by a mean 13
percentage points and over Graph by 14 points, with positive differences in
all five independent sessions. However, the short ordinary repair control did
not lose to the structured prompt (`27/100` versus `25/100`). The supported
coding claim is therefore that a separate bounded repair pass using concrete
execution failure feedback can improve a frozen first patch in this setting;
the evidence does not identify overlap metadata or elaborate structured
operations as the cause.

On MMLU-Pro, the preassigned replication-2 OJ3 comparison improved over D1 by
23/1,000, with 28 rescues and 5 harms (`p=3.309e-5` conditional on the realized
sessions). OJ3 tied SC3 and did not significantly beat GJ3. The result supports
selective second-pass arbitration over the realized direct baseline, not a
support-count-specific mechanism.

## Remaining evidence-only gaps

Further prose revision cannot resolve the following points:

1. Run OJ3, GJ3, and SC3 prospectively on a disjoint MMLU-Pro cohort with enough
   triggered conflicts and a stopping rule frozen before outcomes.
2. Repeat the complete MMLU pipeline on identical frozen items across
   independently initialized whole-file sessions to estimate session variance.
3. Evaluate new official coding tasks, languages, or repositories with Plain,
   Graph, ordinary repair, and structured repair all frozen before any outcome.
4. Add a genuinely fixed-budget or monetary-cost comparison if an efficiency
   claim is desired.

Until such evidence exists, v8 should preserve its current narrow claim. Raising
the headline beyond it would reduce, rather than improve, scientific quality.

## Deliverables reviewed

- `../output/Mini_Artichokes_Main_Revised_v8.docx`
- `../output/Mini_Artichokes_Main_Revised_v8.pdf`
- `../output/Mini_Artichokes_Supplementary_Revised_v8.docx`
- `../output/Mini_Artichokes_Supplementary_Revised_v8.pdf`
- `../evidence/aider_java20_session_replication_results.json`
- `../evidence/aider_java20_ordinary_control_results.json`
- `../../../benchmark_reports/2026-09-02-aider-java20-session-replication/RESULTS.md`
