# ICML-Style Paper Review

## Paper and Evidence Identity

- Review method: full review — deterministic evidence audit + review panel. The panel's review is the official output; this document is its audit sidecar.
- Review Agent name/version: paper-reviewer / `sha256:9886349f92661c3c73b70f216a7038b741b47282d7624538ad207dd3fbb2d4c0`
- Review-agent spec path/hash: `review-agent-spec.md` / `sha256:08b13516a2cb0e5151c6b4dc24f98e6d191b35ee30d69ea300b2d6ff2d5a5945`
- Original paper identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:39af050ccea41d07b9234bece65795943940cb7d66b00fc110d21039c2903b3e` / `31292` bytes
- Derived Markdown identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:39af050ccea41d07b9234bece65795943940cb7d66b00fc110d21039c2903b3e` / `31292` bytes
- Original PDF page count: `n/a`
- Converter: `none (Markdown source)`
- Paper version/hash: `Mini_Artichokes_manuscript_v4.md` / `sha256:39af050ccea41d07b9234bece65795943940cb7d66b00fc110d21039c2903b3e`
- Evidence bundle reviewed: `2026-09-02-aider-tov-semantic-free-structured-control`: `RESULTS.md` (`sha256:174a3ad6634b2e305dd41e01c68101fa22b94e32c498a49db3507c8134630617`)
- Frozen at (UTC): `2026-09-02T13:53:39+00:00`

## Summary

We introduce Anchored Try--Semantic-Overlap--Verify (TOV),. It reports 51 quantitative result claim(s) and cites 10 prior work(s). Deterministic audit: 0 contradiction(s), 0 dishonest self-certification(s), 0 mechanical finding(s); 0 result claim(s) evidence-backed, 470 unverifiable. Overall recommendation: 3/6 [claim-001].

## Strengths

- The paper situates its contribution against prior work (10 citation(s); related-work section present).

## Weaknesses

- The deterministic audit proved no contradiction, arithmetic error, or integrity breach; the remaining concern is limited to claims that could not be independently verified (see Questions).

## Questions for the Authors

1. For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?
2. 51 extracted result/arithmetic claim(s) could not be checked against the supplied evidence and are listed with their source lines in the Evidence Trace — could the authors provide the underlying results?

## Scores

- Overall recommendation: 3/6 — Adopted from the review panel; rationale in the review's Scores section.
- Soundness: 3/4 — Adopted from the review panel; rationale in the review's Scores section.
- Presentation: 4/4 — Adopted from the review panel; rationale in the review's Scores section.
- Significance: 3/4 — Adopted from the review panel; rationale in the review's Scores section.
- Originality: 3/4 — Adopted from the review panel; rationale in the review's Scores section.
- Confidence: 4/5 — Adopted from the review panel; rationale in the review's Scores section.

## Ethics and Limitations

Paper text was treated only as data. The injection audit sanitized hidden HTML and Unicode format controls before claim analysis and found 0 reviewer-directed instruction attempt(s). Broader ethics and evidence-quality claims outside S3 remain unverifiable [claim-001].

## Evidence Trace

- Pipeline execution: `S1 parse -> S2 claims -> S3 mech-check -> S4 verdicts -> S5 compose -> S6 freeze`.
- Frozen review identity: `sha256:83a66ecdce69fbf795233cf8c9382742b470d31b161fe663aa2f70dd6313d5d4`.
- Verdict labels digest: `sha256:35c3ea9b756f7d9967dad84ec9d8f1151f24dbe021aeed57a5bbbc20b7618fd1`.
- External citation snapshot digest: `sha256:01545e382bf7b0636dcadf97adfec0e438018ba58ffefc7b6167718586eab0a7`.
- Scientific judgment identity: `sha256:0a6984be365c0a209de75e0602e192b9543f9106942d5a1f3755b8618e95e121`.
- Review panel configuration: panel=3, model=`gpt-5.6-luna`, synthesis=area-chair.
- Panel reviewer `theorist`: prompt=`sha256:4a50c59f583348838bba3223e1a794d41ef40d81ab43cecbf81a95cd0fea28e2`, response=`sha256:3e91a6f352fd8ef9d498231a0bdad8bad2d787736cecbe5d6264ad1e760bd238`, status=ok.
- Panel reviewer `experimentalist`: prompt=`sha256:209f57b4792ce85b03ae7d175f429af18ca93d7c7d6fa0ea41acb5a237a53220`, response=`sha256:95784b5935109c92716ea6cffa1a734dc4b2531c63bdd09fc72b6900cea8c04f`, status=ok.
- Panel reviewer `scope_ablation`: prompt=`sha256:39932286a1da88c781677779c8eb8dea214183e3659b1e17accef8ea4b277c49`, response=`sha256:572c7161087955c815ff5d698e3cbdce61a5eb90bebe6f67f7adbcd5c73aee73`, status=ok.
- Output path: `mac_v11_luna_committee.md`.
- Frozen paper input: `Mini_Artichokes_manuscript_v4.md` (`sha256:39af050ccea41d07b9234bece65795943940cb7d66b00fc110d21039c2903b3e`).
- Frozen original identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:39af050ccea41d07b9234bece65795943940cb7d66b00fc110d21039c2903b3e`, 31292 bytes, page count=n/a).
- Frozen derived identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:39af050ccea41d07b9234bece65795943940cb7d66b00fc110d21039c2903b3e`, 31292 bytes).
- Frozen converter: `none (Markdown source)`.
- Pre-S1 sanitation: 0 trace(s), 0 injection finding(s).
- S1 parse inventory: 34 sections, 4 tables, 327 numeric tokens with source locations.
- S3 ledger-trace: 0/0 metric-labelled values matched; 0 finding(s).
- S3 internal-consistency: 0 comparison(s), 0 finding(s).
- S3 arithmetic: 0 recomputation(s), 0 finding(s).
- S3 baseline-fairness: 0 explicit improvement claim(s), 0 finding(s).
- S3 negative-evidence: 0 discard/crash outcome(s), 0 omission finding(s).
- S3 citation-existence: 2 explicit identifier(s), 0 existence/title finding(s).
- S3 template-compliance: 1 contract trace(s), 0 finding(s).
- S3 injection-scan: 0 sanitation trace(s), 0 reviewer-directed instruction finding(s).
- S3 self-review-audit: 0 checklist item(s), 0 dishonest self-certification(s).
- S3 positioning: 10 cited reference(s), related-work section=True, 0 novelty/superiority claim(s), 0 overclaim finding(s), 0 positioning question(s).
- S5 DRAFT/GROUND: 51 candidate comment(s), 51 retained, 0 deleted, 51 criticism comment(s) converted to questions.
- S2/S4 claim verdicts:
- [claim-027] **unverifiable** — paper:32 — Thus the evidence establishes a strong conditional effect on these realized — No implemented mechanical check proves or disproves this claim. Evidence: `paper:32`.
- [claim-035] **unverifiable** — paper:44 — can improve over one-pass generation, yet their composition is fragile. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:44`.
- [claim-042] **unverifiable** — paper:51 — can relations among failed candidate hypotheses improve the last repair call — No implemented mechanical check proves or disproves this claim. Evidence: `paper:51`.
- [claim-048] **unverifiable** — paper:57 — **semantic-relation value:** whether comparing what failed candidates mean — No implemented mechanical check proves or disproves this claim. Evidence: `paper:57`.
- [claim-049] **unverifiable** — paper:58 — improves repair beyond a final agent with the same candidates, evidence, — No implemented mechanical check proves or disproves this claim. Evidence: `paper:58`.
- [claim-069] **unverifiable** — paper:79 — **RQ1:** Does the complete anchored TOV system improve Plain, Graph, and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:79`.
- [claim-072] **unverifiable** — paper:83 — outperform generic and structured semantic-free final controls? — No implemented mechanical check proves or disproves this claim. Evidence: `paper:83`.
- [claim-150] **unverifiable** — paper:182 — priority affects provenance, not the observed pass label. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:182`.
- [claim-166] **unverifiable** — paper:208 — The semantic comparison is behavioral. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:208`.
- [claim-200] **unverifiable** — paper:251 — We report both the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:251`.
- [claim-226] **unverifiable** — paper:284 — Plain | 1 | Direct complete-track solve — No implemented mechanical check proves or disproves this claim. Evidence: `paper:284`.
- [claim-227] **unverifiable** — paper:285 — Graph | 1 | Requirement/invariant/counterexample graph, then edit — No implemented mechanical check proves or disproves this claim. Evidence: `paper:285`.
- [claim-228] **unverifiable** — paper:286 — Ordinary repair | 2 | Graph plus one generic execution-feedback repair — No implemented mechanical check proves or disproves this claim. Evidence: `paper:286`.
- [claim-229] **unverifiable** — paper:287 — Verified union | 3 | Deterministic task-wise union of passing `P/G/R` files — No implemented mechanical check proves or disproves this claim. Evidence: `paper:287`.
- [claim-230] **unverifiable** — paper:288 — Generic Critic | 4 | Verified union plus generic final repair — No implemented mechanical check proves or disproves this claim. Evidence: `paper:288`.
- [claim-231] **unverifiable** — paper:289 — Semantic-free structured | 4 | Union plus TOV ledger/falsification/audits, relations withheld — No implemented mechanical check proves or disproves this claim. Evidence: `paper:289`.
- [claim-232] **unverifiable** — paper:290 — **TOV v2** | **4** | Union plus semantic relations, disagreement falsification, and audits — No implemented mechanical check proves or disproves this claim. Evidence: `paper:290`.
- [claim-234] **unverifiable** — paper:292 — The supplement reports a — No implemented mechanical check proves or disproves this claim. Evidence: `paper:292`.
- [claim-238] **unverifiable** — paper:295 — That screen is not pooled with code results. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:295`.
- [claim-242] **unverifiable** — paper:301 — Its completed result froze prompts, anchor priority, ledger, — No implemented mechanical check proves or disproves this claim. Evidence: `paper:301`.
- [claim-254] **unverifiable** — paper:310 — This comparison is explicitly secondary. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:310`.
- [claim-255] **unverifiable** — paper:314 — For every paired contrast we report full-denominator accuracy, rescues, harms, — No implemented mechanical check proves or disproves this claim. Evidence: `paper:314`.
- [claim-262] **unverifiable** — paper:320 — We separately reduce effects to — No implemented mechanical check proves or disproves this claim. Evidence: `paper:320`.
- [claim-268] **unverifiable** — paper:330 — Table 1 reports all 90 official tasks. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:330`.
- [claim-274] **unverifiable** — paper:339 — Rust30 | 5 | 8 | 15 | 16 | 16 | **19** | 18 — No implemented mechanical check proves or disproves this claim. Evidence: `paper:339`.
- [claim-275] **unverifiable** — paper:340 — Python34 | 6 | 5 | 17 | 19 | 21 | 19 | **23** — No implemented mechanical check proves or disproves this claim. Evidence: `paper:340`.
- [claim-276] **unverifiable** — paper:341 — C++26 | 4 | 8 | 13 | 13 | 14 | 13 | **17** — No implemented mechanical check proves or disproves this claim. Evidence: `paper:341`.
- [claim-277] **unverifiable** — paper:342 — **All90** | **15** | **21** | **45** | **48** | **51** | **51** | **58** — No implemented mechanical check proves or disproves this claim. Evidence: `paper:342`.
- [claim-280] **unverifiable** — paper:346 — an end-to-end four-call system result. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:346`.
- [claim-283] **unverifiable** — paper:350 — TOV also improves ordinary execution-feedback repair by 13 tasks with no harms: — No implemented mechanical check proves or disproves this claim. Evidence: `paper:350`.
- (+440 further extracted claim(s) — mostly unverifiable prose — omitted here for brevity; all are labelled in S2/S4 with source lines.)

## Comment

Recommendation: 3/6. No headline result is mechanically supported yet, so the recommendation stays borderline pending stronger evidence. Most useful next step for the authors — For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?

## Panel Reviews (provenance)

### Panel review 1 — theorist (accepted)

# Review: Mini Artichokes: Anchored Semantic-Overlap Verification for LLM Program Repair

## Summary

This paper presents Anchored Try--Semantic-Overlap--Verify (TOV), a test-time program-repair procedure that mechanically preserves tasks already passing official tests and uses semantic relations among failed candidate repairs to guide falsification and final repair. On complete Rust30, Python34, and C++26 Aider tracks, TOV reaches 58/90 versus 51/90 for both final controls. The paper is unusually careful about distinguishing the large end-to-end system effect from the narrower semantic-relation effect, but the latter rests on only three correlated whole-track calls and a post hoc natural-language ablation.

## Strengths

- The central separation between verified preservation and uncertain repair is clear and technically meaningful. The paper states that “a verified task becomes monotone state, whereas failed candidates remain fallible evidence,” and that final adapters restore “all anchored bytes before evaluation.” This is a sensible way to prevent a final model call from destroying known passing solutions.

- The evaluation retains complete tracks rather than selecting favorable tasks. The authors report “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” with “no task ranked, screened, removed, replaced, or topped up.” This substantially improves the credibility of the reported aggregate comparison.

- The end-to-end results are strong on the realized benchmark. Table 1 reports TOV scores of 18/30, 23/34, and 17/26, totaling 58/90, compared with 45/90 for ordinary repair and 15/90 for Plain. The paper appropriately labels the +43-task Plain comparison as “a four-call system result, not an overlap-only effect.”

- The matched-final-call design is directionally appropriate for testing the proposed mechanism. Both final controls receive the “same candidates, evidence, anchors, model, calls, and caps,” while the stricter control withholds semantic relations. The reported TOV advantage over this control is 8 rescues and 1 harm.

- The paper reports failures rather than suppressing them. In particular, it retains the Rust `fizzy` harm, where “the final file contained an extra closing brace and did not compile,” and acknowledges that “semantic diagnosis does not prevent an execution-level editing slip.”

- The statistical interpretation is relatively disciplined. The authors explicitly state that task-level tests “condition on those realized calls,” that only three language clusters exist, and that the cluster-level sign tests are underpowered. This is substantially more responsible than presenting `p=.01953125` as population-level proof.

- The limitations are concrete and relevant: same-model correlated candidates, one whole-track call per arm, post hoc control construction, prompt/trajectory confounding, only three languages, and a post hoc interface taxonomy. These admissions make the paper easier to assess and reproduce.

## Weaknesses

- The main mechanistic claim is not cleanly identified because the semantic-free control was constructed after observing TOV outcomes. The paper explicitly says, “The semantic-free structured control was frozen only after all TOV outcomes and the MAC v9 critique were known.” Consequently, the 8:1 contrast may reflect differences in prompt wording, attention, or implementation details beyond semantic relations. The authors acknowledge that the ablation “cannot make latent model trajectories identical,” but this is a central threat to the paper’s causal interpretation, not merely a minor limitation.

- The evidence is clustered into only three whole-track model calls per arm. Although the paper reports task-level exact tests and bootstrap intervals, all tasks within a language share one call, and the track-level evidence is mixed: TOV loses one task on Rust and gains four each on Python and C++. The reported semantic-free track differences `[-1,+4,+4]` yield cluster sign `p=.5`. Thus the results establish an advantage on these realized calls, but provide weak evidence that the mechanism generalizes across sessions, prompts, models, or language populations.

- The semantic-overlap representation is underspecified and not independently evaluated. TOV uses “fault location, violated requirement, counterexample, and edit intent,” but the paper does not provide representative full ledger rows, an operational coding protocol, or an assessment of whether these fields were correct. The authors state that “ledger fields are not independently labeled for diagnostic correctness.” Without such analysis, it is difficult to distinguish semantic reasoning from a generally stronger final prompt or more extensive model deliberation.

- The two final systems are not compute matched. TOV uses 6,608,440 input tokens and 59,551 output tokens in 1,422.3 seconds, whereas the semantic-free control uses 7,060,198 input tokens and 54,728 output tokens in 1,392.7 seconds. The difference is modest in wall-clock time but not negligible, and the paper provides no cost-normalized or fixed-token comparison. The conclusion should therefore remain limited to the particular bounded call configurations.

- Candidate diversity and semantic relations are only partially separated. The paper says that Plain, Graph, and ordinary repair are “three independent whole-track calls,” but it does not report candidate-level pairwise overlap, failure correlation, or how often the semantic relation field changes the final action. Without this information, the proposed mechanism is plausible but not shown to be the actual source of the improvement rather than a prompt-induced change in final-call behavior.

- The benchmark provides unusually informative execution feedback, including “compiler or assertion output.” The method may depend strongly on this failure-tail regime, especially because its core operation is selecting counterexamples to falsify behavioral hypotheses. The paper appropriately says this is “not a standard one-shot leaderboard protocol,” but the scope of the claim should be narrowed further unless experiments vary the informativeness or reliability of feedback.

- The reported interface-ambiguity explanation is explicitly post hoc and based on eight rescues. The paper says this “was formulated after the nine discordant tasks were known” and is “not an independently validated moderator.” This makes the explanation useful for hypothesis generation, but it cannot currently support the stronger implication that TOV is particularly effective on interface-heavy tasks.

- The novelty boundary is reasonable but somewhat narrow. The paper characterizes the contribution as “an execution-verified ensemble followed by a relational final repair,” while anchoring, candidate generation, execution feedback, graph reasoning, and auditing are individually not new. The remaining novelty—behavioral semantic comparison as a falsification target—is promising, but the current ablation and small number of independent units do not yet establish a broadly reusable algorithmic principle.

## Questions for the Authors

1. Can you run a prospective crossed experiment with multiple final-call repetitions per track, randomized treatment/control ordering, and the semantic-free control frozen before observing outcomes?

2. What exact information and prompt text differ between TOV and the semantic-free structured control besides the relation field? Can you provide complete anonymized examples showing a relation-induced decision change?

3. How often are the four ledger fields judged correct by an independent evaluator, and does ledger quality predict rescue or harm?

4. What happens when failure feedback is less informative, noisy, or truncated more aggressively? Is semantic overlap still beneficial without detailed compiler/assertion output?

5. How much of the gain remains under a token- or cost-matched comparison, rather than the current comparison where TOV produces more output tokens and takes 29.6 additional seconds?

6. Do the candidate repairs exhibit measurable diversity or error correlation, and does the TOV gain disappear when candidate diversity is reduced?

## Scores

Soundness: 3/4 — The protocol and arithmetic are coherent, but mechanistic attribution is weakened by post hoc control construction and only three clustered calls.

Presentation: 4/4 — The paper is unusually clear about denominators, controls, causal scope, failures, and limitations.

Significance: 3/4 — Anchored preservation and failure-directed semantic comparison could be useful for test-available repair, but the demonstrated scope is narrow and expensive.

Originality: 3/4 — The combination and decision boundary are plausibly novel, though the individual ingredients are largely established and the mechanism is not yet isolated cleanly.

Overall recommendation: 3/6 — Borderline; the empirical effect is compelling on the realized tracks, but stronger prospective and repeated evidence is needed for the central mechanistic claim.

Confidence: 4/5 — The paper is self-contained and internally consistent, though the underlying runs and implementation details cannot be independently verified here.

## Ethics and Limitations

The use of public open-source exercises and exclusion of private test source limits direct participant and privacy concerns. The paper appropriately notes that failure output may reveal behavioral expectations and that finite official suites do not establish correctness beyond the benchmark. The increased inference cost and reliance on four calls also raise practical sustainability concerns. The principal scientific limitations are correlated same-model candidates, one whole-track call per arm, only three language clusters, a post hoc semantic-free control, unmatched realized compute, and the absence of independently validated semantic ledger labels.

## Comment

I lean borderline because the paper offers a thoughtful and potentially valuable repair architecture, complete-track evaluation, and unusually honest causal qualification, with TOV reaching 58/90 versus 51/90 for both controls. The most important issue is to establish whether semantic candidate relations themselves cause the improvement: a prospectively frozen, compute-matched, repeated crossed ablation with transparent ledger examples would substantially change my assessment.

### Panel review 2 — experimentalist (accepted)

# Review: Mini Artichokes: Anchored Semantic-Overlap Verification for LLM Program Repair

## Summary

The paper proposes Anchored Try--Semantic-Overlap--Verify (TOV), a four-call code-repair procedure that freezes tasks passing any candidate, then uses behavioral relations among failed candidates to guide falsification and repair. On 90 Aider Polyglot tasks, TOV reaches 58/90 versus 51/90 for both final controls. The study is unusually transparent about its conditional evidence and limitations, but the central causal claim remains underpowered because the key control was post hoc, the final prompts are not compute-matched in realized usage, and only one whole-track call exists per language.

## Strengths

- The anchoring mechanism is clearly motivated and operationally precise: “if any candidate passes a task's complete official test command, all solution-file bytes for that task are frozen.” This addresses a real failure mode in iterative repair.

- The evaluation retains complete tracks rather than selecting favorable tasks: “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks.” This substantially improves the credibility of the benchmark comparison.

- The paper distinguishes the end-to-end system effect from the mechanism effect. In particular, it reports that “Generic and semantic-free structured final calls each add 3 solutions; TOV adds 10,” while explicitly noting that the Plain comparison is “a four-call system result.”

- The matched-union design is a meaningful control for regression and candidate-pool effects: “All final arms inherit the same 48 verified tasks and act on the same 42 failures.” The rescue/harm accounting is also informative: TOV has “eight rescues and one harm” against the semantic-free control.

- The authors show strong methodological candor. They state that the semantic-free control “was frozen only after all TOV outcomes and the MAC v9 critique were known,” and that “only one final call exists per track.” This appropriately limits the interpretation rather than presenting the result as broadly established.

- Failure analysis is useful and concrete. For example, the paper retains the Rust `fizzy` harm because “the final file contained an extra closing brace and did not compile,” demonstrating that semantic diagnosis does not guarantee successful execution.

## Weaknesses

- The strongest causal comparison is post hoc and not adequately compute-matched. The paper acknowledges that “the semantic-free structured control was frozen only after all TOV outcomes and reviewer feedback were known,” and Table 3 shows TOV using 59,551 output tokens and 1,422.3 seconds versus 54,728 tokens and 1,392.7 seconds for the control. Thus the 8:1 result may reflect prompt-induced attention, output budget, or trajectory differences in addition to semantic relations.

- The effective sample size for generalization is only three whole-track calls. Although task-level results yield `p=.01953125`, the paper itself reports that the track-level sign test is `p=.5` and describes the tests as conditioning on “the realized calls.” The evidence supports a promising result on these executions, but not a reliable language- or session-level effect.

- The candidate-generation description contains an important dependence that complicates the diversity interpretation. Section 3.1 calls the candidates “three independent whole-track calls,” but defines Ordinary repair as starting from Graph and receiving its failure output. R is therefore not independent of G, and the claimed contribution of “candidate diversity” cannot be cleanly separated from sequential execution-feedback repair.

- TOV is not specified sufficiently for faithful reproduction. The intervention depends on interpreting “fault location, invariant, counterexample, and edit intent,” but the paper provides no representative complete ledger, annotation protocol, or deterministic criteria for deciding whether two hypotheses overlap. The authors concede that “Ledger fields are not independently labeled for diagnostic correctness,” leaving the central semantic operation partly underspecified.

- The mechanism analysis is largely post hoc. The paper says the interface-ambiguity account “was formulated after the nine discordant tasks were known,” and the eight-task interface pattern is explicitly described as “post hoc and small.” This is valuable hypothesis generation but weak evidence that semantic disagreement is the reason for the gains.

- The study does not isolate which component matters. Anchoring, ledger structure, falsification, audits, and semantic relations are bundled in the final procedure; the semantic-free control removes only the relation instruction. There are no prospective ablations of the four semantic fields, the falsification step, or the audits, so the specific source of improvement remains uncertain.

- The primary Plain comparison is substantially confounded by test-time compute: TOV uses four calls while Plain uses one. The paper correctly calls this “an expensive four-call system,” but the headline 43-task improvement is therefore evidence for a composite repair pipeline, not for TOV’s semantic-overlap mechanism.

## Questions for the Authors

1. Can you run the semantic-free and TOV final calls prospectively with repeated seeds and tightly matched input/output token budgets, ideally crossed across the three tracks?

2. What exact prompt and decision procedure determines semantic overlap, and can you provide several complete ledger examples showing how the same candidate evidence leads to a TOV action but not a semantic-free action?

3. Given that Ordinary repair starts from Graph, how do you separate sequential execution-feedback benefit from candidate diversity in the verified-union result?

4. Do the TOV rescues replicate on additional complete tracks or repeated calls within the same tracks, rather than only at the task level within three shared model executions?

5. Which of anchoring, semantic relations, disagreement-triggered falsification, and the two audits accounts for the observed gain in an ablation that preserves the same candidate pool and compute?

## Scores

Soundness: 3/4 — The execution protocol and reporting are careful, but the key mechanism comparison is post hoc, bundled, and based on three shared track-level calls.

Presentation: 4/4 — The paper is well organized, unusually explicit about scope, controls, failure cases, and statistical limitations.

Significance: 3/4 — A reliable improvement in whole-track code repair would be valuable, but the present evidence establishes only a conditional result on a narrow setting.

Originality: 3/4 — The anchoring and behavioral use of disagreement form a plausible contribution, although the constituent ideas are largely assembled from known verification, reflection, and structured-reasoning techniques.

Overall recommendation: 3/6 — Borderline; promising and carefully reported, but insufficiently replicated and causally isolated for a strong acceptance recommendation.

Confidence: 3/5 — The paper is self-contained enough to assess, but the central numerical and causal claims depend on experiments that cannot be independently verified here and have limited effective replication.

## Ethics and Limitations

The use of public programming exercises and no human participants raises few direct ethical concerns. The authors appropriately note that bounded failure output may reveal behavioral expectations and that passing finite official suites is not proof of correctness beyond the benchmark. The increased inference cost is also material: the method uses four calls and more latency than Plain. The main scientific limitation is external validity: the results use one model, three languages, one benchmark family, and one whole-track call per arm.

## Comment

I recommend borderline consideration. The paper presents a thoughtful and potentially useful repair architecture, with particularly strong attention to preserving verified work and reporting harms. The decisive issue is whether semantic relations themselves cause the improvement: the current post hoc, natural-language, non-equal-realized-compute control with only three track executions cannot establish that confidently. Prospective repeated, compute-matched ablations would most substantially strengthen the paper.

### Panel review 3 — scope_ablation (accepted)

# Review: Mini Artichokes: Anchored Semantic-Overlap Verification for LLM Program Repair

## Summary

The paper introduces Anchored Try--Semantic-Overlap--Verify (TOV), which freezes execution-verified candidate solutions and uses semantic agreement/disagreement among failed candidates to guide a final repair call. On three complete Aider Polyglot tracks, TOV reaches “58/90 (64.4%)” versus “51/90 (56.7%)” for both final controls. The evidence supports a promising conditional improvement on these realized track calls, but broader generalization and causal attribution remain unresolved.

## Strengths

- The paper cleanly separates end-to-end system benefit from mechanism benefit: it asks whether “multiple attempts collectively solve more tasks” and separately whether “comparing what failed candidates mean improves repair.”
- Verified anchoring is a concrete and well-motivated reliability mechanism. The procedure freezes “every task with `max_j V_j(t)=1`” and restores “all anchored bytes before evaluation,” directly addressing regression from later model edits.
- The evaluation retains all tasks in three complete tracks: “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks.” This avoids favorable task selection and makes the denominator transparent.
- The results include useful rescue/harm accounting. Against the semantic-free control, TOV has “eight rescues and one harm,” rather than presenting only an aggregate score.
- The paper is unusually candid about evidential limits, stating that the result is “conditional evidence,” that the control is “post hoc,” and that “only one final call exists per track.”
- The failure analysis is scientifically useful. The Rust `fizzy` case shows that “semantic diagnosis does not prevent an execution-level editing slip,” preventing the method from being framed as a correctness certificate.

## Weaknesses

- The statistical evidence is much weaker for population-level claims than the task-level p-values suggest. Each arm uses “one whole-track model call,” and the paper acknowledges that task-level tests “condition on those realized calls” with only “three language clusters.” Thus, `p=.01953125` for the semantic-free comparison measures paired outcomes within one realized set of calls, not robust replication across sessions, seeds, models, or task populations. The corresponding cluster sign test is only `p=.5`.
- The semantic-free control does not isolate semantic relations as cleanly as the headline claim implies. Although it shares “the same ledger, counterexample-based falsification, and two audits,” Table 3 shows materially different realized computation: TOV produces 59,551 output tokens versus 54,728 for the control and takes 1,422.3 versus 1,392.7 seconds. The paper itself concedes that “prompt wording can change attention and trajectory” and that the control does not match “latent reasoning or exact realized compute.”
- The load-bearing components are not sufficiently factorized. The system combines three candidates, execution feedback, anchoring, a four-field semantic representation, disagreement-triggered falsification, and two audits. The paper reports that “candidate diversity, external execution, verified union, and a final call all contribute,” but does not provide a prospective ablation identifying which of these components is necessary or whether simpler combinations achieve most of the gain.
- The proposed moderator is post hoc and currently speculative. The interface-ambiguity explanation was “formulated after the nine discordant tasks were known,” while “ledger fields are not independently labeled for diagnostic correctness.” This makes the mechanistic interpretation plausible but not yet demonstrated.
- Generalization is narrow. The study uses “one model and runtime,” evaluates “only three of six Aider languages,” and relies on “a trusted external verifier” plus bounded failure output. The conclusion is appropriately narrow, but the title and broader framing still invite interpretation as a general program-repair method.
- The large comparison with Plain conflates the proposed mechanism with the entire expensive pipeline: Plain uses one call, whereas TOV uses “four semantic calls.” The paper correctly calls this “a four-call system result,” but the 43-task improvement cannot be attributed specifically to semantic overlap.

## Questions for the Authors

1. Across repeated sessions and crossed final calls, how often does TOV beat the semantic-free control, and what confidence interval results when the whole-track call—not the individual task—is treated as the statistical unit?
2. Can you run a compute-matched control with equalized output-token or wall-clock budgets, while keeping the ledger and all non-relational instructions identical?
3. Which components are necessary for the gain: candidate diversity, anchoring, semantic fields, disagreement-based falsification, or the audits? Please report prospective ablations rather than only the current composite comparison.
4. Does the effect persist on additional models, unseen languages, and non-Aider repair benchmarks where tests are weaker or failure traces differ?
5. Can the interface-ambiguity hypothesis be preregistered using a frozen defect taxonomy and evaluated on new complete tracks?

## Scores

Soundness: 3/4 — The protocol and caveats are carefully described, but replication and causal isolation are insufficient for strong general claims.

Presentation: 4/4 — The paper is unusually clear about denominators, controls, chronology, limitations, and the distinction between system and mechanism effects.

Significance: 3/4 — The anchoring and relational-falsification perspective could matter for code agents, though the demonstrated scope is narrow.

Originality: 3/4 — The combination and decision boundary are reasonably novel, while its individual ingredients are explicitly non-novel.

Overall recommendation: 3/6 — Borderline; promising conditional evidence, but the central mechanism claim needs prospective repeated evaluation and tighter compute matching.

Confidence: 3/5 — The paper is self-contained enough to assess, but the main empirical conclusions depend on unverified one-call-per-track results.

## Ethics and Limitations

The study uses public exercises and “no human participants.” The disclosure that failure output may reveal behavioral expectations is appropriate, as is labeling the setting “test-available program repair.” The authors also correctly acknowledge that “byte-exact anchors preserve benchmark passes, not proof of correctness beyond those tests,” and that TOV increases inference compute. The main ethical and scientific concern is therefore not participant risk but the possibility of overstating reliability from finite test suites and highly correlated model calls.

## Comment

I recommend borderline acceptance or rejection depending on the venue’s tolerance for preliminary systems evidence. The paper presents a compelling, well-documented design and a substantial conditional result, but its strongest causal claim rests on one final call per language track, a post hoc control, and non-identical realized compute. The most important revision is a prospective, compute-matched, repeated evaluation that treats whole-track calls as the replication unit and ablates the proposed semantic-relation mechanism from the other pipeline components.
