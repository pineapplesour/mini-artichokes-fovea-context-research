# ICML-Style Paper Review

## Paper and Evidence Identity

- Review method: full review — deterministic evidence audit + review panel. The panel's review is the official output; this document is its audit sidecar.
- Review Agent name/version: paper-reviewer / `sha256:9886349f92661c3c73b70f216a7038b741b47282d7624538ad207dd3fbb2d4c0`
- Review-agent spec path/hash: `review-agent-spec.md` / `sha256:08b13516a2cb0e5151c6b4dc24f98e6d191b35ee30d69ea300b2d6ff2d5a5945`
- Original paper identity: `Mini_Artichokes_manuscript_v3.md` / `text/markdown` / `sha256:23f5028e17370bef8178ac84a33651fb476ec68548554463a3db5accad8a2249` / `74098` bytes
- Derived Markdown identity: `Mini_Artichokes_manuscript_v3.md` / `text/markdown` / `sha256:23f5028e17370bef8178ac84a33651fb476ec68548554463a3db5accad8a2249` / `74098` bytes
- Original PDF page count: `n/a`
- Converter: `none (Markdown source)`
- Paper version/hash: `Mini_Artichokes_manuscript_v3.md` / `sha256:23f5028e17370bef8178ac84a33651fb476ec68548554463a3db5accad8a2249`
- Evidence bundle reviewed: `2026-09-02-aider-tov-semantic-free-structured-control`: `RESULTS.md` (`sha256:174a3ad6634b2e305dd41e01c68101fa22b94e32c498a49db3507c8134630617`)
- Frozen at (UTC): `2026-09-02T13:41:42+00:00`

## Summary

We introduce Anchored. It reports 238 quantitative result claim(s) and cites 30 prior work(s). Deterministic audit: 0 contradiction(s), 0 dishonest self-certification(s), 0 mechanical finding(s); 0 result claim(s) evidence-backed, 1127 unverifiable. Overall recommendation: 3/6 [claim-001].

## Strengths

- The paper situates its contribution against prior work (30 citation(s); related-work section present).

## Weaknesses

- The deterministic audit proved no contradiction, arithmetic error, or integrity breach; the remaining concern is limited to claims that could not be independently verified (see Questions).

## Questions for the Authors

1. For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the compute / hardware used. Could the authors clarify these?
2. 238 extracted result/arithmetic claim(s) could not be checked against the supplied evidence and are listed with their source lines in the Evidence Trace — could the authors provide the underlying results?

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
- Frozen review identity: `sha256:287d08baf21f9e50793557b0ed2342ac8f3c109719be471509df69622ea33bcf`.
- Verdict labels digest: `sha256:dfb3d90f402959b70a6648554b6e9f46689433cec9a1b3d546bb0068d436bdcc`.
- External citation snapshot digest: `sha256:e54eabe17ac85420535a902a97ae2bd574436f4df521d70c56a0c32af4df6778`.
- Scientific judgment identity: `sha256:57d44f7d61e478ebd6bd738a44add308a9393591c96fa5895f2f04bc20f4a891`.
- Review panel configuration: panel=3, model=`gpt-5.6-luna`, synthesis=area-chair.
- Panel reviewer `theorist`: prompt=`sha256:123aeb22de1cfea0aedc43485049e22f2e426168358f5d7aff02f2eaa36c3981`, response=`sha256:e592ede200168cba3c111c5065e4c59499b8f14462b356bc2d8b1c8d56d9677d`, status=ok.
- Panel reviewer `experimentalist`: prompt=`sha256:414906913a9942bea6fc9a37431c5e08758db1a6058d13954322d1e9fafd4422`, response=`sha256:4eff4d653225e6372f914cc8032707dfb4a9f5c21ea05dbbaa46fd5856db172e`, status=ok.
- Panel reviewer `scope_ablation`: prompt=`sha256:fedf8c9df5b8028ae5b4bd920285cb52cd20110a6dd2e5c75e35b219b00a02f2`, response=`sha256:2d365995f45e744ac273b1a885c798e314a69759deeae11ac4a39a23053e261c`, status=ok.
- Output path: `mac_v10_luna_committee.md`.
- Frozen paper input: `Mini_Artichokes_manuscript_v3.md` (`sha256:23f5028e17370bef8178ac84a33651fb476ec68548554463a3db5accad8a2249`).
- Frozen original identity: `Mini_Artichokes_manuscript_v3.md` (`text/markdown`, `sha256:23f5028e17370bef8178ac84a33651fb476ec68548554463a3db5accad8a2249`, 74098 bytes, page count=n/a).
- Frozen derived identity: `Mini_Artichokes_manuscript_v3.md` (`text/markdown`, `sha256:23f5028e17370bef8178ac84a33651fb476ec68548554463a3db5accad8a2249`, 74098 bytes).
- Frozen converter: `none (Markdown source)`.
- Pre-S1 sanitation: 0 trace(s), 0 injection finding(s).
- S1 parse inventory: 43 sections, 11 tables, 951 numeric tokens with source locations.
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
- S5 DRAFT/GROUND: 238 candidate comment(s), 238 retained, 0 deleted, 238 criticism comment(s) converted to questions.
- S2/S4 claim verdicts:
- [claim-001] **unverifiable** — paper:5 — Repeated inference can improve large-language-model (LLM) code, but naive — No implemented mechanical check proves or disproves this claim. Evidence: `paper:5`.
- [claim-034] **unverifiable** — paper:35 — answer arbitration improves direct Luna by 2.3 points but ties majority voting — No implemented mechanical check proves or disproves this claim. Evidence: `paper:35`.
- [claim-036] **unverifiable** — paper:36 — Together, the results reject — No implemented mechanical check proves or disproves this claim. Evidence: `paper:36`.
- [claim-056] **unverifiable** — paper:61 — methods show that diversity and selection can outperform a single trajectory. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:61`.
- [claim-065] **unverifiable** — paper:69 — support-aware arbitration improved direct inference but not a compute-matched — No implemented mechanical check proves or disproves this claim. Evidence: `paper:69`.
- [claim-068] **unverifiable** — paper:72 — These results motivate a different question: can overlap be — No implemented mechanical check proves or disproves this claim. Evidence: `paper:72`.
- [claim-097] **unverifiable** — paper:100 — **RQ1:** Does unchanged anchored TOV improve Plain Luna on complete official — No implemented mechanical check proves or disproves this claim. Evidence: `paper:100`.
- [claim-101] **unverifiable** — paper:104 — candidate relations outperform a structured control that withholds them? — No implemented mechanical check proves or disproves this claim. Evidence: `paper:104`.
- [claim-104] **unverifiable** — paper:107 — **RQ4:** Does the earlier support-aware answer-arbitration result transfer as — No implemented mechanical check proves or disproves this claim. Evidence: `paper:107`.
- [claim-110] **unverifiable** — paper:113 — semantic hypothesis comparison, disagreement-driven falsification, and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:113`.
- [claim-116] **unverifiable** — paper:119 — tasks rather than selected subsets--and report paired rescues, harms, exact — No implemented mechanical check proves or disproves this claim. Evidence: `paper:119`.
- [claim-122] **unverifiable** — paper:123 — Receipts, runners, and hashes establish provenance; — No implemented mechanical check proves or disproves this claim. Evidence: `paper:123`.
- [claim-127] **unverifiable** — paper:133 — Cumulative complete-track system evidence | TOV v2 vs Plain on Rust30 + Python34 + C++26 | 58/90 vs 15/90; +47.8 points; 43 rescues, 0 harms; `p=1.14e-13` | The four-call anchored TOV system substantially improved the realized Plain baseline on all three complete tracks | Exact-compute efficiency; other-model or all-language generality; independence of tasks within a call — No implemented mechanical check proves or disproves this claim. Evidence: `paper:133`.
- [claim-128] **unverifiable** — paper:134 — Matched mechanism contrast | TOV v2 vs generic verified-union Critic | 58/90 vs 51/90; +7.8 points; 7 rescues, 0 harms; `p=.0078125` | Given the realized candidates and evidence, the semantic-overlap decision procedure added accuracy beyond anchors and generic repair | Independent track-population significance: only 3/3 track gains, sign `p=.125` — No implemented mechanical check proves or disproves this claim. Evidence: `paper:134`.
- [claim-129] **unverifiable** — paper:135 — Review-triggered stricter mechanism control | TOV v2 vs semantic-free structured verified-union control | 58/90 vs 51/90; +7.8 points; 8 rescues, 1 harm; `p=.01953` | The semantic-relation instruction added accuracy beyond matched ledger, falsification, and audits on the realized tasks | Prospective confirmation; session repeatability; positive direction on Rust (`[-1,+4,+4]` track differences) — No implemented mechanical check proves or disproves this claim. Evidence: `paper:135`.
- [claim-130] **unverifiable** — paper:136 — Prospective confirmation | Unchanged TOV v2 vs Plain / ordinary / generic on complete Python34 | +50.0 / +17.6 / +5.9 points; 17:0 / 6:0 / 2:0 rescue:harm | The development-frozen policy transferred unchanged to a complete held-out language track | Precise incremental estimate versus generic from one call cluster — No implemented mechanical check proves or disproves this claim. Evidence: `paper:136`.
- [claim-131] **unverifiable** — paper:137 — Unchanged-policy extension | TOV v2 vs Plain / generic on complete C++26 | +50.0 / +11.5 points; 13:0 / 3:0 | Positive matched effect recurred under a new language and toolchain | A pre-registered second confirmation; all Aider languages — No implemented mechanical check proves or disproves this claim. Evidence: `paper:137`.
- [claim-132] **unverifiable** — paper:138 — Earlier failure-driven development | Strict overlap vs matched repair on Java20 | 5/20 vs 7/20 | Literal/two-of-three overlap is too brittle; disagreement must trigger falsification rather than veto | Evidence for the later TOV v2 effect — No implemented mechanical check proves or disproves this claim. Evidence: `paper:138`.
- [claim-133] **unverifiable** — paper:139 — Answer-arbitration boundary | OJ3 vs D1 and matched GJ3 on MMLU-Pro replication | +2.3 vs D1; tied SC3; +0.2 vs GJ3, not significant | Same-model agreement can route review | Support counts as a general causal mechanism — No implemented mechanical check proves or disproves this claim. Evidence: `paper:139`.
- [claim-136] **unverifiable** — paper:147 — positive result motivated many inference-time feedback loops. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:147`.
- [claim-140] **unverifiable** — paper:149 — not improve reasoning through intrinsic self-correction without external — No implemented mechanical check proves or disproves this claim. Evidence: `paper:149`.
- [claim-145] **unverifiable** — paper:152 — found that LLM self-critique could reduce planning performance relative to — No implemented mechanical check proves or disproves this claim. Evidence: `paper:152`.
- [claim-163] **unverifiable** — paper:173 — solutions can also improve mathematical reasoning [8]. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:173`.
- [claim-165] **unverifiable** — paper:174 — trained reward model, debate transcript, external execution result, or gold — No implemented mechanical check proves or disproves this claim. Evidence: `paper:174`.
- [claim-168] **unverifiable** — paper:176 — The matched GJ3/OJ3 comparison is intended to — No implemented mechanical check proves or disproves this claim. Evidence: `paper:176`.
- [claim-202] **unverifiable** — paper:214 — The draw roles are fixed before any answer is scored: — No implemented mechanical check proves or disproves this claim. Evidence: `paper:214`.
- [claim-222] **unverifiable** — paper:235 — every reported score and comparison unchanged. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:235`.
- [claim-232] **unverifiable** — paper:247 — support record stating that one anonymous candidate has one complete-file draw — No implemented mechanical check proves or disproves this claim. Evidence: `paper:247`.
- [claim-249] **unverifiable** — paper:270 — the judge improve an answer by synthesizing new content. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:270`.
- [claim-260] **unverifiable** — paper:285 — The private evaluator restores untouched official tests and records — No implemented mechanical check proves or disproves this claim. Evidence: `paper:285`.
- (+1097 further extracted claim(s) — mostly unverifiable prose — omitted here for brevity; all are labelled in S2/S4 with source lines.)

## Comment

Recommendation: 3/6. No headline result is mechanically supported yet, so the recommendation stays borderline pending stronger evidence. Most useful next step for the authors — For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the compute / hardware used. Could the authors clarify these?

## Panel Reviews (provenance)

### Panel review 1 — theorist (accepted)

# Review: Mini Artichokes: Anchored Semantic-Overlap Verification for LLM Program Repair

## Summary

The paper proposes Anchored Try--Semantic-Overlap--Verify (TOV), a code-repair procedure that preserves externally verified patches and uses semantic comparison plus falsification for unresolved tasks. On three complete Aider tracks, TOV achieves 58/90 versus 51/90 for a generic verified-union critic and 15/90 for Plain. The results are promising but provide only conditional evidence for the semantic-overlap mechanism because each language is represented by one whole-track call and the closest control was designed after observing TOV's results.

## Strengths

- The method has a clear safety invariant: “preserve every task already verified by official tests as an immutable byte-level anchor.” This is a concrete and valuable design principle, and the paper reports that “all verified anchors survived byte-exactly.”

- The paper carefully separates system-level improvement from mechanism attribution. Its claim hierarchy explicitly states that the 58/90 versus 15/90 result is “an end-to-end four-call system effect; it is not attributed solely to overlap,” while the 58/90 versus 51/90 contrast is presented as conditional on shared candidates and evidence.

- The coding evaluation avoids task cherry-picking within the selected tracks. The paper evaluates “all 30 Rust, 34 Python, and 26 C++ tasks” and states that “No task is ranked, screened, dropped, or added after scoring.”

- The authors are unusually candid about inferential limitations. They state that “task-level tests and intervals condition on the realized calls” and that the three-track generic contrast has a cluster-level sign test of “`.125`,” rather than presenting the task-level `p=.0078125` as unrestricted population evidence.

- The paper includes informative negative and failure-driven evidence. In particular, “strict two-of-three overlap scored 5/20 versus 7/20,” while the legal reserve “did not transfer.” These results appropriately constrain the claim that agreement or overlap is universally beneficial.

- The reporting is operationally detailed. The paper provides model, effort, call counts, token totals, hashes, anchor counts, ledger-row counts, and the exact outcome tables, making the claimed protocol substantially easier to audit than typical LLM-agent studies.

## Weaknesses

- The central mechanism result is statistically fragile because the true experimental units are whole-track calls, not the 90 individual tasks. There is only one final-stage realization per language, and the paper itself reports “only three whole-track clusters” with cluster sign `p=.125`. The task-level exact test therefore risks overstating evidence by treating correlated within-call outcomes as if they supplied independent replication. Repeated independent final-stage calls, ideally across more languages and models, are needed before the semantic-overlap claim is convincing.

- The closest semantic ablation is post hoc and therefore cannot serve as confirmatory causal evidence. The paper explicitly says that the control “was frozen only after these outcomes and the MAC v9 critique were known.” Its 8:1 result (`p=.01953125`) is consequently vulnerable to design adaptation and researcher degrees of freedom, even though the authors appropriately label it secondary. Moreover, a natural-language instruction that prohibits using candidate relations cannot ensure that the model did not internally use the same information; the paper concedes that it “cannot make internal trajectories identical.”

- The large TOV-versus-Plain result is intrinsically asymmetric and should not be interpreted as evidence that semantic overlap itself produces the 43-task gain. The verified union includes Plain, and the paper acknowledges that “anchors can generate apparent rescues by retaining any verified candidate.” Because passing Plain tasks are mechanically protected, the reported “43 rescues and no harms” partly follows from the preservation contract. The generic verified-union comparison is the scientifically relevant contrast, but its net gain is only 7/90.

- “Semantic overlap” remains a prompt-level behavioral description rather than a measured mechanism. The paper defines it as “convergence on the same behavioral obligation,” but does not report how often candidates actually agreed or disagreed on each semantic field, whether those relations predicted correctness, or whether the final adjudicator followed the ledger's stated falsification process. The post hoc list of eight interface-related rescues is suggestive but explicitly exploratory. Per-task ledgers and an independent audit of the claimed reasoning process would substantially strengthen the attribution.

- The study's external validity is narrow. It uses “one model, one runtime,” only three of the six Aider languages, and one whole-track call per arm. The legal experiment is negative, with OJ3 losing 29 points relative to P1, but the paper correctly notes that “domain, task, prompt, and label structure changed together.” Thus the evidence supports a coding-specific result under a particular batch-solving regime, not a general LLM answer-engine principle.

- The practical benefit is not yet established relative to its cost. TOV uses four semantic calls versus one for Plain, and the MMLU arbitration system consumes “3.53-fold” the direct-draw token budget. The paper reports this honestly, but it does not provide a stronger quality-versus-compute comparison against alternative ways of spending the same budget, such as repeated generic repair calls or independent final-stage samples.

- The MMLU-Pro evidence provides useful boundary information but weak support for the coding mechanism. OJ3 improves D1 by 2.3 points yet “tied majority voting and does not significantly beat a matched generic judge.” This is consistent with the paper's thesis, but it also means the positive general answer-arbitration evidence is limited to a comparison against a single direct draw and does not demonstrate a broadly effective overlap operator.

## Questions for the Authors

1. Can you repeat the generic and semantic-free contrasts with multiple independently initialized final calls per language, or with additional complete language tracks, so that inference is based on whole-track clusters rather than task-level observations?

2. Which exact prompt and protocol decisions were frozen before observing TOV outcomes, and which were chosen after the first review? In particular, can you provide a prospective preregistration of the semantic-free control and its primary analysis?

3. Can you release per-task semantic ledgers showing candidate agreements, disagreements, falsification attempts, selected actions, and anchor provenance? How often did the final model's stated semantic relation actually predict which candidate was correct?

4. What are the incremental contributions of candidate diversity, execution-feedback repair, anchoring, the ledger, falsification, and the two audits? A compute-matched factorial or sequential ablation would clarify whether the gain is specifically due to semantic relations or to the broader structured prompt.

5. How was the choice of Rust, Python, and C++ tracks made, and were language/toolchain choices frozen independently of preliminary outcomes? A broader or randomized language-level evaluation would address the stated `p=.125` cluster limitation.

6. What is the exact identity and reproducibility specification of `gpt-5.6-luna`, including model version stability, context limits, caching behavior, and runtime details? The anomalous D2 session, which scored only 145/1,000, suggests that session-level behavior may be a major source of variance.

## Scores

Soundness: 3/4 — The protocols and limitations are carefully documented, but the mechanism evidence is conditional on three correlated whole-track calls and a post hoc control.

Presentation: 3/4 — The paper is unusually transparent and well organized, although the many experimental regimes and claim boundaries make the central conclusion difficult to isolate.

Significance: 3/4 — A robust verified-union repair procedure could be valuable, but the demonstrated incremental gain is modest and expensive relative to Plain.

Originality: 3/4 — The composition of immutable anchors, semantic hypothesis comparison, and falsification is a useful formulation, though the constituent ideas are largely drawn from existing agent and verification paradigms.

Overall recommendation: 3/6 — Borderline; the coding result is promising but not yet sufficiently replicated or causally identified for acceptance as a general mechanism claim.

Confidence: 3/5 — The paper is self-contained enough to assess, but the conclusions depend heavily on unverified runtime artifacts and a very small number of independent experimental clusters.

## Ethics and Limitations

The paper identifies the main ethical issue responsibly: it states that legal fact patterns “did not establish full de-identification,” acknowledges possible re-identification, and withholds item texts and outputs pending governance review. This is appropriate. The environmental cost is also disclosed: the MMLU experiments consumed “45.97 million tokens.”

The principal scientific limitations are the single-model setting, whole-file session dependence, finite hidden-test coverage, selected language tracks, approximate compute matching, and post hoc semantic-free control. These limitations are not minor, but the authors generally state them candidly rather than hiding them. The legal negative result also argues against deploying same-model agreement in high-stakes settings without external evidence.

## Comment

I recommend borderline treatment. The immutable-anchor design and the complete-track coding results are compelling enough to justify further investigation, but the paper's strongest scientific claim—that semantic candidate relations add accuracy beyond matched structured repair—rests on one realized call per language and a control created after observing the outcome. The most important revision is a prospective, repeated, whole-track evaluation that estimates session-level variance and tests the semantic-relation intervention independently of post hoc prompt design.

### Panel review 2 — experimentalist (accepted)

# Review: Mini Artichokes: Anchored Semantic-Overlap Verification for LLM Program Repair

## Summary

This paper proposes Anchored Try--Semantic-Overlap--Verify (TOV), a multi-call code-repair procedure that preserves tasks passing official tests, compares unresolved candidates using behavioral hypotheses, and uses disagreement to trigger falsification. On 90 complete Rust, Python, and C++ Aider tasks, TOV substantially outperforms one-call Plain Codex, but the more relevant matched comparison is smaller: 58/90 versus 51/90 against a generic final critic. The paper is unusually candid about compute, dependence, post-hoc controls, and domain-boundary failures. However, its central semantic-overlap attribution remains based on a single realized call cluster and a control designed after observing TOV outcomes.

## Strengths

- The paper clearly separates end-to-end performance from mechanism attribution. It explicitly states that the 58/90 versus 15/90 comparison “is an end-to-end four-call system effect; it is not attributed solely to overlap.”

- The anchor mechanism is concrete and safety-oriented. The method “preserve[s] every task already verified by official tests as an immutable byte-level anchor,” and the paper reports that “all verified anchors survived byte-exactly.”

- The coding evaluation uses complete tracks rather than selected favorable tasks: “all 30 Rust, 34 Python, and 26 C++ tasks.” This substantially improves the credibility of the reported 90-task result.

- The strongest matched comparison is reported with appropriate caveats: TOV scores “58/90 versus 51/90,” with “seven rescues with no losses,” while also acknowledging the cluster-level sign test of `p=.125`.

- The paper tests plausible alternatives and negative boundaries. In particular, “strict two-of-three authorization scored 5/20 versus 7/20,” and the legal reserve shows that the approach is not automatically domain-general.

- The statistical reporting is detailed and generally responsible, including rescues, harms, exact paired tests, bootstrap intervals, compute, latency, and explicit discussion that task-level inference conditions on realized whole-track calls.

## Weaknesses

- The central causal claim is not prospectively established. The semantic-free structured control “was frozen only after these outcomes and the MAC v9 critique were known,” so the 8:1 TOV advantage is a review-triggered secondary contrast. Moreover, the paper concedes that this “cannot make internal trajectories identical.” With only one final call per language and three language clusters, the result is evidence of a promising prompt-level effect on these realized artifacts, not strong evidence of a generally reproducible semantic-overlap mechanism.

- The main Plain comparison is confounded by both compute and a favorable monotonicity contract. TOV uses four calls while Plain uses one, and the verified union includes any task solved by Plain, Graph, or ordinary repair. Therefore, the “43 rescues and no harms” relative to Plain is partly guaranteed by preserving the best candidate pool; it does not show that semantic adjudication itself caused those rescues. The paper appropriately says that this is a “four-call system effect,” but the abstract still foregrounds the very large 58/90 versus 15/90 contrast.

- The semantic-overlap operation is not isolated as a precisely measurable algorithm. The generic Critic differs from TOV in the ledger, falsification, and two audits, while the later control removes candidate relations through a natural-language instruction. The paper reports that the control “matches the ledger, falsification, and audits,” but actual final-call inputs and outputs differ substantially (`7.06M/54,728` tokens versus `6.61M/59,551` for TOV). Thus, the 7-task difference could reflect prompt wording, attention allocation, or unobserved reasoning behavior rather than the proposed semantic relation specifically.

- The statistical significance of the coding result is optimistic under the experimental unit actually used. The paper states that “each arm uses one whole-track call,” and that task-level tests “condition on the realized calls.” The exact task-level `p=.0078125` is therefore not evidence of population-level replication; the more conservative language-level result is only `p=.125`. Repeated independent calls on the same complete tracks, or more complete language tracks, are needed to support broader claims.

- The candidate diversity and semantic diagnosis are not independently characterized. The paper claims that TOV aligns “fault locations, invariants, counterexample classes, and edit intentions,” but it does not quantify how often candidates agree, disagree, or identify the correct obligation, nor does it provide independent evaluation of ledger quality. The post-hoc claim that eight TOV-only passes “concentrate in interface and semantic-contract ambiguities” is explicitly exploratory and cannot yet establish the proposed boundary.

- The MMLU-Pro evidence does not support a strong general selective-arbitration claim. Only 68/2,000 questions triggered arbitration; OJ3 tied SC3 and exceeded GJ3 by only two answers (`p=.3633`). The paper correctly acknowledges that “the support annotation's incremental causal effect is unresolved,” but this experiment contributes mainly a negative boundary rather than validation of the general method.

## Questions for the Authors

1. Can you run the TOV and semantic-free control on repeated independent calls over the same complete tracks, with the control specified before seeing TOV outcomes, and analyze the language track or call as the primary experimental unit?

2. What fraction of TOV’s advantage over the generic Critic comes specifically from semantic agreement, semantic disagreement, falsification, and the two audits? Can these components be crossed in a factorial ablation with matched prompts and output budgets?

3. How often are the ledger’s fault locations, invariants, counterexample classes, and edit intentions correct according to an independent evaluator, and do they predict which TOV edits succeed?

4. How would TOV compare with a compute-matched ensemble or verifier that receives the same candidate pool and execution evidence but is allowed equivalent output space and reasoning budget?

5. Can the complete-track experiment be extended to the remaining Aider languages, or can you justify why the selected Rust/Python/C++ tracks provide an unbiased test of language generality?

## Scores

Soundness: 3/4 — The protocols and caveats are unusually explicit, but the central mechanism evidence is post hoc, conditional on realized calls, and based on few experimental clusters.

Presentation: 3/4 — The paper is well organized and transparent about inferential boundaries, though the large end-to-end contrast can distract from the much smaller mechanism result.

Significance: 3/4 — Reliable preservation plus improved repair could be practically valuable, but the demonstrated operating point is expensive and the generality remains narrow.

Originality: 3/4 — The anchored composition and behavioral-overlap/falsification framing are useful, although the individual ingredients are largely prompt-level combinations of existing ideas.

Overall recommendation: 3/6 — Borderline; promising empirical evidence, but insufficient prospective and repeated validation for acceptance as a broadly established mechanism.

Confidence: 3/5 — The paper is self-contained and the reasoning is assessable, but the key claims depend on unverified artifacts and a small number of whole-track executions.

## Ethics and Limitations

The paper responsibly reports that the legal data may remain re-identifiable, with “five selected records” lacking recoverable reuse metadata, and it withholds legal item texts and outputs pending governance review. It also reports the substantial cost of the method: “45.97 million tokens across the two OJ3 cohorts.” The authors are appropriately candid that the coding study covers only three languages, uses one whole-track call per arm, and does not establish session-level repeatability. These limitations are central to interpreting the result, not merely peripheral qualifications.

## Comment

I recommend borderline consideration. The strongest contribution is a carefully engineered, conservative code-repair system with an encouraging 7/90 matched gain over a generic final critic. The single most important next step is a prospective, repeated, compute-matched experiment that isolates semantic candidate relations from the ledger, falsification, audit, and prompt-complexity effects; without that, the paper supports TOV as a promising realized procedure more strongly than it supports semantic overlap as a general causal mechanism.

### Panel review 3 — scope_ablation (accepted)

# Review: Mini Artichokes: Anchored Semantic-Overlap Verification for LLM Program Repair

## Summary

The paper proposes Anchored Try--Semantic-Overlap--Verify (TOV), a code-repair procedure that preserves externally verified patches, compares unresolved candidates by behavioral semantics, and uses disagreement to trigger falsification. On all 90 tasks from three Aider Polyglot tracks, TOV achieves 58/90 versus 51/90 for a generic verified-union critic and 15/90 for Plain. The results are promising but remain conditional on a small number of whole-track calls, one model/runtime, selected languages, and a review-triggered control.

## Strengths

- The paper defines a concrete, conservative mechanism rather than treating agreement as correctness: “verified union, semantic hypothesis comparison, disagreement-driven falsification, and completion auditing.” The byte-level anchor rule is particularly clear: “verified anchors are restored byte for byte.”

- The coding evaluation avoids convenient task selection within the chosen tracks. Table 5 reports every task in Rust30, Python34, and C++26, with TOV improving over Plain by 43 rescues and zero harms: “TOV produces 43 rescues and no harms.”

- The strongest comparison controls several important confounds. The generic critic receives “all three candidate patches, per-task pass/fail outcomes, bounded failure traces, the verified union, and U,” while sharing call count, model, effort, and output caps with TOV.

- The authors are unusually explicit about inferential boundaries. They state that the task-level result is conditional on realized calls and that “a cluster-level one-sided sign test is `.125`,” rather than presenting the task-level `p=.0078125` as unqualified population evidence.

- The negative boundary result is valuable. On the legal reserve, OJ3 falls from 284/464 for the plain arm to 255/464, with “30 rescues but 59 harms.” This prevents the paper from presenting same-model agreement as universally beneficial.

- The paper reports meaningful operational costs rather than hiding them: OJ3 uses “45,973,780 tokens versus 13,009,321 for D1,” a 3.53-fold ratio. It also reports latency, invalid outputs, anchor checks, and artifact hashes.

- The failed predecessor is used constructively. The Java result—“strict two-of-three overlap scored 5/20 versus 7/20 for matched repair”—supports the distinction between semantic disagreement as a falsification target and literal overlap as an editing gate.

## Weaknesses

- The central semantic-overlap attribution is not yet a clean prospective causal result. The semantic-free structured control “was frozen only after these outcomes and the MAC v9 critique were known,” and the paper acknowledges that “this natural-language contrast cannot make internal trajectories identical.” Thus, the 8:1 TOV advantage may reflect prompt wording, attention allocation, output behavior, or other unmeasured differences in addition to semantic relations. The task-level `p=.01953125` is also much less persuasive when the track-level result is `[-1,+4,+4]` with sign `p=.5`.

- The apparent statistical strength is limited by the experimental unit. Each arm uses “one whole-track call,” so the 90 task outcomes are strongly dependent within only three language clusters. The paper appropriately reports cluster-level caveats, but the headline exact tests and bootstrap intervals still occupy much more narrative prominence than the only three independent track-level comparisons justify.

- Scope and generalization are narrow. The coding study covers “three complete official language tracks, not the complete six-language Aider benchmark,” uses one model and runtime, and operates in an unusual whole-file regime. The authors explicitly say it measures “a hidden-test feedback regime, not ordinary interactive local development.” The legal negative result further shows that the mechanism does not transfer automatically outside executable code with informative tests.

- Several load-bearing components remain confounded. TOV combines candidate diversity, verified anchors, semantic relations, falsification, a ledger, and two audits. The generic control tests the full bundle against a simpler final critic, while the semantic-free control changes several prompt-level instructions at once. There is no factorial or prospective ablation isolating anchors, falsification, audits, candidate diversity, and semantic relations separately.

- The comparison against Plain is an end-to-end compute comparison rather than an efficiency comparison. TOV uses four calls while Plain uses one, and the paper reports that TOV is “not compute matched to direct Luna.” The large 58/90 versus 15/90 gap therefore establishes a useful system effect but says little about whether TOV is preferable to a comparably expensive generic multi-call repair strategy beyond the limited controls tested.

- The final-stage controls are not exactly matched in realized computation. TOV uses 59,551 final-call input/output tokens versus 54,728 for the structured control, and its final-call times differ substantially from the generic critic. The matched call budget is useful, but the evidence does not establish that semantic relations improve accuracy at equal token, latency, or monetary cost.

- The MMLU-Pro evidence does not materially validate the proposed coding mechanism. OJ3 improves over D1 by 2.3 points but “ties SC3 and does not significantly beat a matched generic judge.” This is an informative boundary, but it leaves the positive coding result dependent on the special availability of executable feedback and modular code tasks.

- The anomalous D2 session remains unexplained. The paper rules out several integrity failures, but “its semantic cause remains unresolved.” Since the method depends on repeated whole-file sessions and conflict frequency, this instability should motivate repeated same-task pipeline runs before strong claims about robustness.

## Questions for the Authors

1. Can you run a prospective, crossed final-stage experiment with TOV, semantic-free control, and a prompt-length/output-budget-matched control on repeated sessions of the same complete tracks?

2. What are the per-task paired outcome vectors and final-stage outputs for all three coding tracks? These are necessary to assess whether the reported task-level significance is driven by a few correlated whole-track behaviors.

3. Which components are actually load-bearing: immutable anchors, candidate semantic relations, falsification, the ledger, or the two audits? A factorial ablation or at least individually removed components would substantially clarify the contribution.

4. Does TOV retain its advantage when tasks are solved in independent per-task or smaller-batch sessions, rather than one whole-track call? If not, how should the method’s intended deployment setting be characterized?

## Scores

Soundness: 3/4 — The protocols and caveats are strong, but the key mechanism contrast is post hoc and supported by only three dependent whole-track clusters.

Presentation: 4/4 — The paper is unusually clear about controls, costs, statistical boundaries, and negative results, despite its considerable length.

Significance: 3/4 — A potentially useful conservative repair architecture is demonstrated, but its practical and cross-domain significance is not yet established.

Originality: 3/4 — The composition and semantic-relation/falsification framing are interesting, though the constituent ideas are largely drawn from existing iterative-repair and verification patterns.

Overall recommendation: 3/6 — Borderline to weak reject pending stronger prospective and repeated-session evidence.

Confidence: 3/5 — The argument is self-contained and carefully reported, but the central empirical claims depend on artifacts and execution details that cannot be independently verified here.

## Ethics and Limitations

The paper appropriately discusses the 45.97 million-token cost of the MMLU-Pro arbitration study and does not conceal the negative legal result. Its handling of legal data is cautious: outcome text was removed, item texts and outputs are withheld, and it acknowledges that full de-identification was not established. The most important scientific limitations are the single model/runtime, selected language tracks, whole-track dependence, unexplained session instability, approximate compute matching, review-triggered control, and finite official tests that “are not proof beyond the benchmark.”

## Comment

I find the anchored repair architecture promising and the distinction between behavioral overlap and literal agreement well motivated. However, the paper’s main scientific claim—that semantic candidate relations add accuracy beyond the structured repair bundle—currently rests on a post hoc natural-language control and three dependent whole-track calls. I recommend borderline/weak rejection until this effect is tested prospectively with repeated complete-track sessions and component-level ablations.
