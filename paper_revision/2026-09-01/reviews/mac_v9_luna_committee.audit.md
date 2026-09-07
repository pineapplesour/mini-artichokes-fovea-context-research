# ICML-Style Paper Review

## Paper and Evidence Identity

- Review method: full review — deterministic evidence audit + review panel. The panel's review is the official output; this document is its audit sidecar.
- Review Agent name/version: paper-reviewer / `sha256:9886349f92661c3c73b70f216a7038b741b47282d7624538ad207dd3fbb2d4c0`
- Review-agent spec path/hash: `review-agent-spec.md` / `sha256:08b13516a2cb0e5151c6b4dc24f98e6d191b35ee30d69ea300b2d6ff2d5a5945`
- Original paper identity: `Mini_Artichokes_manuscript_v3.md` / `text/markdown` / `sha256:bbf8e82b3d6cf03805fb8ceaff12dbeb10a1e9106c898ddcaabda7941e969b28` / `66898` bytes
- Derived Markdown identity: `Mini_Artichokes_manuscript_v3.md` / `text/markdown` / `sha256:bbf8e82b3d6cf03805fb8ceaff12dbeb10a1e9106c898ddcaabda7941e969b28` / `66898` bytes
- Original PDF page count: `n/a`
- Converter: `none (Markdown source)`
- Paper version/hash: `Mini_Artichokes_manuscript_v3.md` / `sha256:bbf8e82b3d6cf03805fb8ceaff12dbeb10a1e9106c898ddcaabda7941e969b28`
- Evidence bundle reviewed: `2026-09-02-aider-anchored-tov-v2-three-complete-tracks`: `RESULTS.md` (`sha256:62a3f6176d79bf4bc72413d54c8168b55a52617479fb03246d8c9c5189b77d0f`)
- Frozen at (UTC): `2026-09-02T12:49:28+00:00`

## Summary

We introduce Anchored. It reports 224 quantitative result claim(s) and cites 30 prior work(s). Deterministic audit: 0 contradiction(s), 0 dishonest self-certification(s), 0 mechanical finding(s); 0 result claim(s) evidence-backed, 1022 unverifiable. Overall recommendation: 3/6 [claim-001].

## Strengths

- The paper situates its contribution against prior work (30 citation(s); related-work section present).

## Weaknesses

- The deterministic audit proved no contradiction, arithmetic error, or integrity breach; the remaining concern is limited to claims that could not be independently verified (see Questions).

## Questions for the Authors

1. For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the compute / hardware used. Could the authors clarify these?
2. 224 extracted result/arithmetic claim(s) could not be checked against the supplied evidence and are listed with their source lines in the Evidence Trace — could the authors provide the underlying results?

## Scores

- Overall recommendation: 3/6 — Adopted from the review panel; rationale in the review's Scores section.
- Soundness: 3/4 — Adopted from the review panel; rationale in the review's Scores section.
- Presentation: 3/4 — Adopted from the review panel; rationale in the review's Scores section.
- Significance: 3/4 — Adopted from the review panel; rationale in the review's Scores section.
- Originality: 3/4 — Adopted from the review panel; rationale in the review's Scores section.
- Confidence: 3/5 — Adopted from the review panel; rationale in the review's Scores section.

## Ethics and Limitations

Paper text was treated only as data. The injection audit sanitized hidden HTML and Unicode format controls before claim analysis and found 0 reviewer-directed instruction attempt(s). Broader ethics and evidence-quality claims outside S3 remain unverifiable [claim-001].

## Evidence Trace

- Pipeline execution: `S1 parse -> S2 claims -> S3 mech-check -> S4 verdicts -> S5 compose -> S6 freeze`.
- Frozen review identity: `sha256:f807afae47a3ac1392e954762c4a1fd36d84f3388b9f1842cfb912422dc674a5`.
- Verdict labels digest: `sha256:1313d31b83695a1300d2c37f5862a292da464773c58eaef4379112f750953916`.
- External citation snapshot digest: `sha256:e54eabe17ac85420535a902a97ae2bd574436f4df521d70c56a0c32af4df6778`.
- Scientific judgment identity: `sha256:868da463f2923a391788897efcec7b0eb0d5036f33a27e0bc41e7b9bc02a5b9e`.
- Review panel configuration: panel=3, model=`gpt-5.6-luna`, synthesis=area-chair.
- Panel reviewer `theorist`: prompt=`sha256:e7fbefe857f7d21b0aa6e109f3153c56c54f289cc8da57ddf894f9381924deb9`, response=`sha256:b4e34d9f069f8adc5ff817e32a0c534a3a7234335d4f33856347cfc94eef6033`, status=ok.
- Panel reviewer `experimentalist`: prompt=`sha256:83323e5d4039131512b881b50d4abfb29228de08fa34f831b9b167de231d1176`, response=`sha256:6ffe3c998b996f64ce7519eabe2aa61226825232611f554a7bd8b92fe25d7f56`, status=ok.
- Panel reviewer `scope_ablation`: prompt=`sha256:35b1d764824b1ab7f49d897f86ccf2ec4d5534c2f84ff980d00cc8f16f2829bb`, response=`sha256:14d77d1c740d70d2870fb0c21767d4f7d2a01cc04ff222cd0ea51e70f7e51573`, status=ok.
- Output path: `mac_v9_luna_committee.md`.
- Frozen paper input: `Mini_Artichokes_manuscript_v3.md` (`sha256:bbf8e82b3d6cf03805fb8ceaff12dbeb10a1e9106c898ddcaabda7941e969b28`).
- Frozen original identity: `Mini_Artichokes_manuscript_v3.md` (`text/markdown`, `sha256:bbf8e82b3d6cf03805fb8ceaff12dbeb10a1e9106c898ddcaabda7941e969b28`, 66898 bytes, page count=n/a).
- Frozen derived identity: `Mini_Artichokes_manuscript_v3.md` (`text/markdown`, `sha256:bbf8e82b3d6cf03805fb8ceaff12dbeb10a1e9106c898ddcaabda7941e969b28`, 66898 bytes).
- Frozen converter: `none (Markdown source)`.
- Pre-S1 sanitation: 0 trace(s), 0 injection finding(s).
- S1 parse inventory: 43 sections, 10 tables, 852 numeric tokens with source locations.
- S3 ledger-trace: 0/3 metric-labelled values matched; 0 finding(s).
- S3 internal-consistency: 0 comparison(s), 0 finding(s).
- S3 arithmetic: 0 recomputation(s), 0 finding(s).
- S3 baseline-fairness: 0 explicit improvement claim(s), 0 finding(s).
- S3 negative-evidence: 0 discard/crash outcome(s), 0 omission finding(s).
- S3 citation-existence: 5 explicit identifier(s), 0 existence/title finding(s).
- S3 template-compliance: 1 contract trace(s), 0 finding(s).
- S3 injection-scan: 0 sanitation trace(s), 0 reviewer-directed instruction finding(s).
- S3 self-review-audit: 0 checklist item(s), 0 dishonest self-certification(s).
- S3 positioning: 30 cited reference(s), related-work section=True, 0 novelty/superiority claim(s), 0 overclaim finding(s), 0 positioning question(s).
- S5 DRAFT/GROUND: 224 candidate comment(s), 224 retained, 0 deleted, 224 criticism comment(s) converted to questions.
- S2/S4 claim verdicts:
- [claim-001] **unverifiable** — paper:5 — Repeated inference can improve large-language-model (LLM) code, but naive — No implemented mechanical check proves or disproves this claim. Evidence: `paper:5`.
- [claim-031] **unverifiable** — paper:32 — answer arbitration improves direct Luna by 2.3 points but ties majority voting — No implemented mechanical check proves or disproves this claim. Evidence: `paper:32`.
- [claim-033] **unverifiable** — paper:33 — Together, the results reject — No implemented mechanical check proves or disproves this claim. Evidence: `paper:33`.
- [claim-053] **unverifiable** — paper:58 — methods show that diversity and selection can outperform a single trajectory. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:58`.
- [claim-062] **unverifiable** — paper:66 — support-aware arbitration improved direct inference but not a compute-matched — No implemented mechanical check proves or disproves this claim. Evidence: `paper:66`.
- [claim-065] **unverifiable** — paper:69 — These results motivate a different question: can overlap be — No implemented mechanical check proves or disproves this claim. Evidence: `paper:69`.
- [claim-081] **unverifiable** — paper:84 — This distinction permits a clean mechanism comparison. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:84`.
- [claim-093] **unverifiable** — paper:95 — **RQ1:** Does unchanged anchored TOV improve Plain Luna on complete official — No implemented mechanical check proves or disproves this claim. Evidence: `paper:95`.
- [claim-096] **unverifiable** — paper:98 — and budget held fixed, does semantic-overlap adjudication outperform a — No implemented mechanical check proves or disproves this claim. Evidence: `paper:98`.
- [claim-100] **unverifiable** — paper:102 — **RQ4:** Does the earlier support-aware answer-arbitration result transfer as — No implemented mechanical check proves or disproves this claim. Evidence: `paper:102`.
- [claim-106] **unverifiable** — paper:108 — semantic hypothesis comparison, disagreement-driven falsification, and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:108`.
- [claim-110] **unverifiable** — paper:112 — tasks rather than selected subsets--and report paired rescues, harms, exact — No implemented mechanical check proves or disproves this claim. Evidence: `paper:112`.
- [claim-116] **unverifiable** — paper:116 — Receipts, runners, and hashes establish provenance; — No implemented mechanical check proves or disproves this claim. Evidence: `paper:116`.
- [claim-121] **unverifiable** — paper:126 — Cumulative complete-track system evidence | TOV v2 vs Plain on Rust30 + Python34 + C++26 | 58/90 vs 15/90; +47.8 points; 43 rescues, 0 harms; `p=1.14e-13` | The four-call anchored TOV system substantially improved the realized Plain baseline on all three complete tracks | Exact-compute efficiency; other-model or all-language generality; independence of tasks within a call — No implemented mechanical check proves or disproves this claim. Evidence: `paper:126`.
- [claim-122] **unverifiable** — paper:127 — Matched mechanism contrast | TOV v2 vs generic verified-union Critic | 58/90 vs 51/90; +7.8 points; 7 rescues, 0 harms; `p=.0078125` | Given the realized candidates and evidence, the semantic-overlap decision procedure added accuracy beyond anchors and generic repair | Independent track-population significance: only 3/3 track gains, sign `p=.125` — No implemented mechanical check proves or disproves this claim. Evidence: `paper:127`.
- [claim-123] **unverifiable** — paper:128 — Prospective confirmation | Unchanged TOV v2 vs Plain / ordinary / generic on complete Python34 | +50.0 / +17.6 / +5.9 points; 17:0 / 6:0 / 2:0 rescue:harm | The development-frozen policy transferred unchanged to a complete held-out language track | Precise incremental estimate versus generic from one call cluster — No implemented mechanical check proves or disproves this claim. Evidence: `paper:128`.
- [claim-124] **unverifiable** — paper:129 — Unchanged-policy extension | TOV v2 vs Plain / generic on complete C++26 | +50.0 / +11.5 points; 13:0 / 3:0 | Positive matched effect recurred under a new language and toolchain | A pre-registered second confirmation; all Aider languages — No implemented mechanical check proves or disproves this claim. Evidence: `paper:129`.
- [claim-125] **unverifiable** — paper:130 — Earlier failure-driven development | Strict overlap vs matched repair on Java20 | 5/20 vs 7/20 | Literal/two-of-three overlap is too brittle; disagreement must trigger falsification rather than veto | Evidence for the later TOV v2 effect — No implemented mechanical check proves or disproves this claim. Evidence: `paper:130`.
- [claim-126] **unverifiable** — paper:131 — Answer-arbitration boundary | OJ3 vs D1 and matched GJ3 on MMLU-Pro replication | +2.3 vs D1; tied SC3; +0.2 vs GJ3, not significant | Same-model agreement can route review | Support counts as a general causal mechanism — No implemented mechanical check proves or disproves this claim. Evidence: `paper:131`.
- [claim-129] **unverifiable** — paper:139 — positive result motivated many inference-time feedback loops. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:139`.
- [claim-133] **unverifiable** — paper:141 — not improve reasoning through intrinsic self-correction without external — No implemented mechanical check proves or disproves this claim. Evidence: `paper:141`.
- [claim-138] **unverifiable** — paper:144 — found that LLM self-critique could reduce planning performance relative to — No implemented mechanical check proves or disproves this claim. Evidence: `paper:144`.
- [claim-156] **unverifiable** — paper:165 — solutions can also improve mathematical reasoning [8]. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:165`.
- [claim-158] **unverifiable** — paper:166 — trained reward model, debate transcript, external execution result, or gold — No implemented mechanical check proves or disproves this claim. Evidence: `paper:166`.
- [claim-161] **unverifiable** — paper:168 — The matched GJ3/OJ3 comparison is intended to — No implemented mechanical check proves or disproves this claim. Evidence: `paper:168`.
- [claim-195] **unverifiable** — paper:206 — The draw roles are fixed before any answer is scored: — No implemented mechanical check proves or disproves this claim. Evidence: `paper:206`.
- [claim-215] **unverifiable** — paper:227 — every reported score and comparison unchanged. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:227`.
- [claim-225] **unverifiable** — paper:239 — support record stating that one anonymous candidate has one complete-file draw — No implemented mechanical check proves or disproves this claim. Evidence: `paper:239`.
- [claim-242] **unverifiable** — paper:262 — the judge improve an answer by synthesizing new content. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:262`.
- [claim-253] **unverifiable** — paper:277 — The private evaluator restores untouched official tests and records — No implemented mechanical check proves or disproves this claim. Evidence: `paper:277`.
- (+992 further extracted claim(s) — mostly unverifiable prose — omitted here for brevity; all are labelled in S2/S4 with source lines.)

## Comment

Recommendation: 3/6. No headline result is mechanically supported yet, so the recommendation stays borderline pending stronger evidence. Most useful next step for the authors — For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the compute / hardware used. Could the authors clarify these?

## Panel Reviews (provenance)

### Panel review 1 — theorist (accepted)

# Review: Mini Artichokes: Anchored Semantic-Overlap Verification for LLM Program Repair

## Summary

This paper proposes Anchored Try--Semantic-Overlap--Verify (TOV), a conservative LLM program-repair pipeline that preserves externally verified patches, compares unresolved candidate hypotheses semantically, and uses falsification before editing. On 90 complete Rust, Python, and C++ Aider tasks, TOV improves over both Plain and a matched generic critic, but the evidence is conditioned on only one whole-track call per arm and three language clusters.

## Strengths

- The paper clearly separates end-to-end performance from mechanism attribution: “The largest result is an end-to-end system effect,” while the matched comparison holds “candidate generation, execution evidence, verified anchors, call count, and budget” fixed.

- The immutable-anchor design is concrete and technically meaningful. The method states that “every task already verified by official tests” is preserved and that “all full solution-file bytes for these tasks become anchors,” addressing the common failure mode where iterative repair damages already-correct code.

- The coding evaluation avoids task selection within the reported tracks. Table 5 includes “Rust, all 30,” “Python, all 34,” and “C++, all 26,” and the paper explicitly states that “No task is ranked, screened, dropped, or added after scoring.”

- The paper reports an informative matched result: TOV achieves “58/90 versus 51/90 for the matched generic final procedure,” with “seven rescues and no losses.” This is substantially more persuasive than comparison only against Plain.

- The authors are unusually candid about inferential limitations. They state that “a 3/3 cluster sign has `p=.125`” and that task-level results “condition on the realized calls,” rather than presenting the 90 tasks as fully independent replications.

- The negative legal result and null MMLU-Pro mechanism comparison provide useful boundary evidence. In particular, the paper reports that support-aware arbitration “does not significantly beat a matched generic judge,” which appropriately weakens any claim that agreement counts alone are generally causal.

## Weaknesses

- The central TOV mechanism is not cleanly isolated. TOV adds a seven-field ledger, an explicit falsification attempt, a requirement-to-diff audit, and a completion audit, whereas the generic critic receives only a generic repair instruction. Thus the `58/90` versus `51/90` contrast identifies the bundled TOV final procedure, not semantic overlap specifically. The paper acknowledges this directly: “It does not separately identify the ledger, semantic fields, falsification step, or two audits.” A factorial or staged ablation is needed before attributing the gain to semantic overlap.

- The coding evidence has only three independent whole-track clusters, making the apparent significance highly dependent on treating tasks within a single model call as independent. The paper itself notes that “task-level exact results and intervals condition on the realized calls” and that the cluster-level sign test is `.125`. Consequently, the result is credible as a promising conditional observation, but insufficient to support a strong general claim about program repair.

- The final-stage comparison has no repeated executions of either final arm on the same candidate artifacts. Seven rescues and zero harms could therefore reflect stochastic variation between two single final calls, despite identical inputs and nominal budgets. Repeated final adjudications, ideally over multiple independently generated candidate sets, are necessary to estimate robustness.

- The method is a large bundle relative to Plain: TOV uses “four semantic calls versus one for Plain,” and the MMLU arbitration system uses “3.53 times D1's tokens.” The paper reports this honestly, but the practical significance of a 7.8-point matched gain is difficult to assess without a clearer cost-quality comparison against equally expensive alternatives and without showing whether a simpler prompt or additional generic repair call obtains similar gains.

- The coding track selection remains consequential. Although every task within the selected tracks is included, “the primary coding evidence covers three complete official language tracks, not the complete six-language Aider benchmark.” Rust is development, Python is prospective confirmation, and C++ is an extension, so the aggregate should not be treated as a single prespecified confirmatory experiment.

- The semantic ledger may be difficult to validate independently. The paper requires “one ledger row per unresolved task” and describes its fields, but it does not report examples of correct versus incorrect ledgers, inter-rater checks, or an analysis showing that ledger content predicts successful repairs. As presented, the ledger is an imposed reasoning format whose causal value is not directly demonstrated.

- The paper's strongest coding comparison depends on a particular candidate-generation regime. TOV only has unresolved tasks after Plain, Graph, and execution-feedback repair have already produced a useful verified union. The authors appropriately state that the result is “conditional on a useful candidate/evidence set,” but this substantially narrows the claimed generality and leaves open how often the required regime occurs outside this benchmark.

## Questions for the Authors

1. Can you provide ablations separating the semantic ledger, explicit falsification, requirement-to-diff audit, and completion audits? Which component accounts for the seven-task advantage over the generic critic?

2. How stable is the `7:0` matched result across repeated final calls using the identical frozen candidate/evidence artifacts? If repeated calls are unavailable, what evidence supports interpreting the difference as a policy effect rather than final-call stochasticity?

3. Were the generic critic and TOV given equivalent output space, reasoning effort, and opportunity to inspect or modify every unresolved task? Please provide the exact prompts and output/token statistics, including whether TOV's structured ledger consumed materially more context.

4. How many tasks were independently verified by each candidate, and how does TOV compare with a simpler policy that merely preserves the verified union and applies an additional generic repair call?

5. Can the authors evaluate the frozen policy on additional complete language tracks or independently initialized whole-track sessions to address the acknowledged `p=.125` cluster-level limitation?

## Scores

Soundness: 3/4 — The matched artifact-sharing design and explicit limitations are strong, but the causal claim is bundled and the coding inference rests on three dependent call clusters.

Presentation: 4/4 — The paper is exceptionally clear about protocols, claim boundaries, costs, and limitations.

Significance: 3/4 — A conditional 7.8-point gain over a matched critic is potentially useful, but its scope and repeatability are not yet established.

Originality: 3/4 — The anchor-preservation and disagreement-as-falsification composition is thoughtful, though its individual ingredients are largely drawn from existing inference-time methods.

Overall recommendation: 3/6 — Borderline; promising empirical evidence, but additional ablations and repeated independent coding evaluations are needed for a convincing mechanism claim.

Confidence: 3/5 — The argument and reported evidence are sufficiently detailed to assess, but the key experimental artifacts and execution results cannot be independently verified here.

## Ethics and Limitations

The paper appropriately discusses increased inference cost, reporting “45.97 million tokens across the two OJ3 cohorts,” and cautions against using same-model agreement in high-stakes settings. Its handling of the legal reserve is responsible: item texts and outputs are withheld because “full de-identification” was not established and some records may remain re-identifiable. The main scientific limitations are the single model and runtime, whole-file session dependence, correlated same-model candidates, sparse arbitration conflicts, approximate compute matching, bundled TOV components, and only three independent coding-track clusters. These limitations materially constrain generalization but are stated candidly.

## Comment

I recommend borderline consideration. The paper presents a carefully bounded and potentially valuable design, especially the matched verified-union comparison and immutable-anchor contract. The most important revision is to establish whether the observed coding gain comes from semantic-overlap adjudication itself or from the broader bundle of structured prompting, falsification, and audits, using component ablations and repeated independent final executions on frozen candidate artifacts.

### Panel review 2 — experimentalist (accepted)

# Review: Mini Artichokes: Anchored Semantic-Overlap Verification for LLM Program Repair

## Summary

The paper proposes Anchored Try--Semantic-Overlap--Verify (TOV), a conservative code-repair pipeline that preserves externally verified patches and uses structured semantic comparison plus falsification for unresolved tasks. On three complete Aider tracks, TOV achieves 58/90 versus 51/90 for a matched generic critic and 15/90 for Plain. The central empirical result is promising, but its mechanism and generality remain insufficiently established because the coding study has only three whole-track experimental clusters and bundles several interventions into the TOV treatment.

## Strengths

- The paper clearly separates end-to-end performance from mechanism attribution. It explicitly states that “TOV versus the matched generic Critic measures the incremental value of structured semantic-overlap adjudication on the realized candidate set,” which is a useful experimental distinction.

- The preservation contract is concrete and testable. The method states that “all full solution-file bytes for these tasks become anchors,” and the results report that “all verified anchors survived byte-exactly.” This is a meaningful safeguard against regressions in iterative repair.

- The coding evaluation avoids task selection within the chosen tracks. Table 5 reports “Rust, all 30,” “Python, all 34,” and “C++, all 26,” and the paper states, “No task is ranked, screened, dropped, or added after scoring.”

- The matched coding comparison is materially stronger than the Plain comparison. TOV and the generic critic share “all three candidate calls, per-task outcomes, bounded failure traces, evidence serialization, verified union, byte-restoration adapter, model, reasoning effort, one final call, and budget cap,” while TOV obtains 58/90 versus 51/90, with “7 rescues, 0 harms.”

- The paper is unusually candid about inferential boundaries. It reports that “a cluster-level one-sided sign test is `.125`” and repeatedly states that task-level results are conditional on realized whole-track calls rather than evidence of broad language-population generality.

- The negative results are useful and appropriately incorporated into the argument. The paper reports that legal OJ3 suffered “30 rescues but 59 harms,” and that strict two-of-three overlap scored “5/20 versus 7/20 for matched repair,” providing evidence against simplistic consensus or intersection rules.

## Weaknesses

- The matched control does not isolate semantic overlap as a causal component. TOV adds a seven-field ledger, falsification, requirement-to-diff auditing, and a separate completion audit, whereas the generic critic is “instructed only to preserve anchors, inspect the supplied evidence, and fix unresolved tasks.” The paper itself concedes, “TOV v2 is a bundle” and “does not separately identify the ledger, semantic fields, falsification step, or two audits.” Thus, the result supports the bundled TOV prompt/procedure over this generic prompt, but not semantic overlap specifically.

- The effective number of independent coding experiments is extremely small. Each result is based on “one whole-track call per arm,” and the study has only three language clusters. Although the task-level comparison is 58/90 versus 51/90 with `p=.0078125`, the paper also reports that the three-cluster sign test is `.125`. Without repeated independent executions of complete tracks, it is unclear whether the seven-task gain is robust to session-level variation, ordering effects, or stochastic failures.

- The large TOV-versus-Plain result primarily measures the benefit of adding multiple candidate-generation and repair calls plus verified-union anchoring, not the proposed adjudication mechanism. Table 5 shows that the generic verified-union system already reaches 51/90 versus Plain’s 15/90, leaving only the 7-task difference attributable to the final-stage contrast. The paper acknowledges that the 43-rescue result “is not attributed solely to overlap,” but the abstract’s headline emphasis can still leave an inflated impression of the mechanism’s contribution.

- The compute comparison is not fully controlled. TOV and the generic critic have matched call counts and caps, but the paper states that “actual cached/uncached tokens and time were not identical,” and TOV’s final calls were 44–110 seconds slower. Moreover, the structured ledger and audits may induce more reasoning work within the same nominal cap. The evidence therefore supports an accuracy gain at a nominal call budget, not a cost- or compute-matched gain.

- Generality is substantially narrower than the framing suggests. The coding evidence covers “three complete official language tracks, not the complete six-language Aider benchmark,” uses only `gpt-5.6-luna`, and has no repeated same-track runs. The MMLU-Pro and legal results do not repair this gap: one shows a weak selective-arbitration effect, while the legal result is explicitly confounded by simultaneous changes in domain, task, prompt, and label structure.

- The reproducibility claims are stronger than what is directly actionable from the text. The paper lists hashes and says the artifact contains “exact prompts, accepted candidate and judge outputs, private-score scripts, aggregate reports, and tests,” but provides no access location or execution instructions in the submitted paper. Hashes establish identity if the artifacts are obtained, but do not by themselves permit independent verification.

## Questions for the Authors

1. Can you provide repeated independently initialized executions of each complete coding track, or session-level variance estimates, to determine whether the 7/0 matched advantage persists beyond one realized call cluster?

2. What are the results of factorial ablations separating the ledger, semantic-overlap fields, falsification requirement, requirement-to-diff audit, and completion audit? Without these, which component should readers credit for the gain?

3. Can the generic critic be given the same output schema, audit obligations, and effective token budget as TOV while withholding only the semantic-overlap decision rule? How does the matched result change?

4. How much of the 43-task TOV-versus-Plain improvement comes from the verified union before final adjudication, and how often does the final stage actually modify unresolved tasks successfully?

5. Can the released artifact be accompanied by a public access path and a complete reproduction recipe, including the exact model/runtime configuration and serialized evidence packets?

## Scores

Soundness: 3/4 — The controls and disclosures are thoughtful, but the coding inference is conditional on three whole-track calls and the treatment is a multi-component bundle.

Presentation: 3/4 — The paper is clear and unusually explicit about claim boundaries, though the many regimes and result types make the central contribution harder to isolate.

Significance: 3/4 — A robust improvement over a matched final critic on program repair would be valuable, but the current evidence does not establish broad reliability.

Originality: 3/4 — The anchored preservation contract and semantic-overlap/falsification composition are a plausible contribution despite relying on largely known ingredients.

Overall recommendation: 3/6 — Borderline; the result is promising but not yet sufficiently replicated or causally decomposed for acceptance as a strong empirical claim.

Confidence: 3/5 — The paper is self-contained enough to assess, but the decisive numerical artifacts and execution behavior cannot be independently checked here.

## Ethics and Limitations

The study uses public benchmarks and open-source coding tasks without human participants. The handling of legal data is responsible: the paper states that “item texts and outputs [are withheld] pending a separate governance review” because facts may remain re-identifiable. It also appropriately reports the environmental cost, namely “45.97 million tokens across the two OJ3 cohorts.”

The authors are commendably candid about contamination, within-session dependence, single-model evaluation, finite test coverage, incomplete language coverage, and the bundled nature of TOV. In particular, the statement that official tests “are not a proof of semantic correctness beyond the benchmark” is important. These limitations materially constrain the strength of the conclusions but are accurately presented.

## Comment

I recommend borderline acceptance at most. The paper presents a well-motivated preservation-and-adjudication design and a potentially meaningful 7-task gain over a matched generic final critic. The single most important issue is experimental independence and causal attribution: repeated complete-track runs and component-level ablations are needed to show that the result is a reproducible semantic-overlap effect rather than a one-session, bundled-prompt advantage.

### Panel review 3 — scope_ablation (accepted)

# Review: Mini Artichokes: Anchored Semantic-Overlap Verification for LLM Program Repair

## Summary

This paper introduces Anchored Try--Semantic-Overlap--Verify (TOV), a conservative code-repair pipeline that preserves test-verified candidate patches and uses semantic hypothesis comparison plus falsification to adjudicate unresolved tasks. On 90 complete Aider Polyglot tasks, TOV achieves 58/90 versus 51/90 for a matched generic critic and 15/90 for Plain. The paper is unusually candid about compute, negative results, and inferential limits, but the main mechanism claim remains based on three correlated whole-track calls and an unablated bundle of design choices.

## Strengths

- The paper gives a precise and useful distinction between textual consensus and behavioral reasoning: “Semantic overlap means convergence on the same behavioral obligation, not textual intersection of edited lines,” while “disagreement creates a testable burden and triggers falsification.” This is a coherent mechanism hypothesis rather than a generic claim that more agents improve accuracy.

- The matched coding comparison is substantially stronger than the end-to-end Plain baseline. TOV and the generic critic share “all three candidate calls, per-task outcomes, bounded failure traces, evidence serialization, verified union, byte-restoration adapter, model, reasoning effort, one final call, and budget cap,” yet Table 5 reports 58/90 versus 51/90, with “seven correct tasks with no losses.” This directly tests whether the final adjudication procedure adds value conditional on shared evidence.

- The preservation contract is well motivated and operationalized. The method states that “all full solution-file bytes for these tasks become anchors,” and the results report that “all verified anchors survived byte-exactly.” This addresses a real failure mode of iterative repair: sacrificing already-correct work while attempting additional fixes.

- The authors appropriately separate cumulative system evidence from mechanism attribution. They explicitly state that the 58-versus-15 Plain comparison “is not attributed solely to overlap,” report the cluster-level sign result of `p=.125`, and describe the legal result as a negative boundary rather than suppressing it. This candor improves the credibility of the presentation.

## Weaknesses

- The central generalization claim is supported by only three whole-track clusters and one realized call per arm. The paper itself acknowledges that “a cluster-level one-sided sign test is `.125`” and that task-level inference “should not be read as a precise population estimate over languages.” Thus, the reported `p=.0078125` and `[+3.3,+13.3]` interval primarily quantify conditional task-level variation within correlated batch executions, not repeatable performance across languages, sessions, or model instances.

- TOV is an unablated bundle, so the experiment does not establish that semantic overlap or falsification is the causal source of the gain. The limitations explicitly state: “It does not separately identify the ledger, semantic fields, falsification step, or two audits.” The matched generic control establishes an advantage for the complete structured final procedure, but differences in prompt structure, mandatory ledger production, audit requirements, and deliberation behavior remain conflated.

- The large end-to-end improvement over Plain is dominated by additional inference and candidate generation. TOV uses four calls while Plain uses one, and the paper reports a `58/90` versus `15/90` comparison alongside the statement that the system is “a quality-oriented two-call policy, not an efficiency gain.” The more scientifically relevant 7-task matched gain is modest relative to the 43-task end-to-end gain and requires stronger replication than currently provided.

- The coding evaluation covers only three of the six Aider language tracks, and the language selection is not randomized. Although the paper evaluates “every task in the three tracks,” it also concedes that “selecting language tracks is still a scope choice.” The positive results across Rust, Python, and C++ are encouraging, but they do not establish broad program-repair generality, particularly for other toolchains or languages.

- The negative legal experiment does not cleanly identify the proposed boundary of applicability. The paper reports that the legal setup “simultaneously changes domain, task, prompt, and label structure,” so the result cannot distinguish underdetermined facts from domain difficulty, prompt effects, or binary-label effects. It is a useful cautionary result, but it provides limited evidence about when semantic-overlap verification should or should not transfer.

- The MMLU-Pro evidence is informative but only indirectly related to program repair. OJ3 improves D1 by 2.3 points but “does not significantly beat a matched generic judge,” while only 68/2,000 questions trigger arbitration. This supports the claim that agreement alone is insufficient, but it does not materially validate the coding mechanism and adds another regime whose small conflict set leaves the incremental effect imprecise.

## Questions for the Authors

1. Can you provide repeated independent executions of the complete Rust, Python, and C++ tracks, or additional complete language tracks, to estimate session-level variance beyond the reported conditional task-level statistics?

2. What happens in a factorial ablation of the TOV final stage: semantic ledger only, falsification only, completion audits only, and combinations thereof? In particular, does the gain persist when the generic critic is given the same output structure and comparable deliberation budget?

3. Can you report the identities and characteristics of the seven TOV-versus-generic rescues, including whether they are concentrated in a particular task type, failure mode, or track?

4. What is the cost-quality frontier when Plain or a generic critic receives the same total token and wall-clock budget as TOV, rather than merely the same number of final calls?

## Scores

Soundness: 3/4 — The matched treatment contrast and preservation protocol are well designed, but inference is conditional on three correlated whole-track executions and an unablated treatment bundle.

Presentation: 3/4 — The paper is clear and unusually transparent, though the multiple experimental regimes make the main contribution harder to isolate.

Significance: 3/4 — A repeatable coding-repair gain would be valuable, but the demonstrated scope is currently narrow and compute-intensive.

Originality: 3/4 — The individual ingredients are established, but their anchored semantic-adjudication composition is a plausible and well-motivated contribution.

Overall recommendation: 3/6 — Borderline: promising evidence for a bounded coding mechanism, but insufficient independent replication and ablation for a strong ICML acceptance recommendation.

Confidence: 3/5 — The argument and reported comparisons are sufficiently detailed to assess, but the key empirical claims depend on execution artifacts that cannot be independently checked here.

## Ethics and Limitations

The paper responsibly reports increased inference cost, including “45.97 million tokens across the two OJ3 cohorts,” and does not present passing official tests as proof of general correctness. Its handling of the Korean legal data is appropriately cautious: it notes that “full de-identification” was not established and withholds item texts pending governance review. The principal scientific limitations are the one-model, one-runtime setting; within-session dependence; only three coding-language clusters; approximate compute matching; and the inability to attribute the matched gain to individual TOV components.

## Comment

I recommend borderline consideration. The strongest contribution is the carefully controlled 58-versus-51 coding comparison, not the much larger but compute-confounded comparison with Plain. The authors should prioritize independent repeated whole-track validation and component-level ablations, especially controls that match TOV’s structured ledger and audit burden. Without those experiments, the paper supports a promising bounded procedure, but not yet a broadly established semantic-overlap mechanism.
