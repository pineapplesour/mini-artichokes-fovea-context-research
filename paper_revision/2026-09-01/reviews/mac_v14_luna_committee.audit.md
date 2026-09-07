# ICML-Style Paper Review

## Paper and Evidence Identity

- Review method: full review — deterministic evidence audit + review panel. The panel's review is the official output; this document is its audit sidecar.
- Review Agent name/version: paper-reviewer / `sha256:9886349f92661c3c73b70f216a7038b741b47282d7624538ad207dd3fbb2d4c0`
- Review-agent spec path/hash: `review-agent-spec.md` / `sha256:08b13516a2cb0e5151c6b4dc24f98e6d191b35ee30d69ea300b2d6ff2d5a5945`
- Original paper identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:d1575e49879fdee6566d74f6d0bb78f45b73b79b883161df3b48c5a56c44a311` / `48103` bytes
- Derived Markdown identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:d1575e49879fdee6566d74f6d0bb78f45b73b79b883161df3b48c5a56c44a311` / `48103` bytes
- Original PDF page count: `n/a`
- Converter: `none (Markdown source)`
- Paper version/hash: `Mini_Artichokes_manuscript_v4.md` / `sha256:d1575e49879fdee6566d74f6d0bb78f45b73b79b883161df3b48c5a56c44a311`
- Evidence bundle reviewed: none (no evidence bundle supplied)
- Frozen at (UTC): `2026-09-03T17:24:45+00:00`

## Summary

We introduce Anchored Try--Semantic-Overlap--Verify (TOV),. It reports 98 quantitative result claim(s) and cites 10 prior work(s). Deterministic audit: 0 contradiction(s), 0 dishonest self-certification(s), 0 mechanical finding(s); 0 result claim(s) evidence-backed, 727 unverifiable. Overall recommendation: 3/6 [claim-001].

## Strengths

- The paper situates its contribution against prior work (10 citation(s); related-work section present).

## Weaknesses

- The deterministic audit proved no contradiction, arithmetic error, or integrity breach; the remaining concern is limited to claims that could not be independently verified (see Questions).

## Questions for the Authors

1. For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?
2. 98 extracted result/arithmetic claim(s) could not be checked against the supplied evidence and are listed with their source lines in the Evidence Trace — could the authors provide the underlying results?

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
- Frozen review identity: `sha256:97a5560896bc99bec2ccd7e3ff7902f47fdbbb412d97e85e41e9020af5b14017`.
- Verdict labels digest: `sha256:b099379f607393f4871ee9272366f996e0fd30ca40228ab14e96abdec5f3c4a2`.
- External citation snapshot digest: `sha256:01545e382bf7b0636dcadf97adfec0e438018ba58ffefc7b6167718586eab0a7`.
- Scientific judgment identity: `sha256:31cd5cad6ffb352338b05be023ff50f25eeb84ad73eaca83fa20c9102e24d4e0`.
- Review panel configuration: panel=3, model=`gpt-5.6-luna`, synthesis=area-chair.
- Panel reviewer `theorist`: prompt=`sha256:9b74aa5f0f814236c9c8d7d32f33fd6ac0f27d2b60a7a91b6cb0f344d8717080`, response=`sha256:a70e92cd09caafe4e24d46d549ed6765c8ba98c04b40b57ef467c0c2d9111185`, status=ok.
- Panel reviewer `experimentalist`: prompt=`sha256:13cbfbbbf93cc15727147249d056319f5898cb1eb13a6fbe97cb9c4eece3affa`, response=`sha256:7a66c9a37f2e277fd1e42fe1078626b7d27767fe3513ee260638b8aa129a88d0`, status=ok.
- Panel reviewer `scope_ablation`: prompt=`sha256:828352aef32aa50b91b9f92ed9b959452b1b89b0143674ef30d85ad12b5398f3`, response=`sha256:fadd0c58fc9aa5f55dfddc11a3d2d5741fae0130c17130549882829905091906`, status=ok.
- Output path: `mac_v14_luna_committee.md`.
- Frozen paper input: `Mini_Artichokes_manuscript_v4.md` (`sha256:d1575e49879fdee6566d74f6d0bb78f45b73b79b883161df3b48c5a56c44a311`).
- Frozen original identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:d1575e49879fdee6566d74f6d0bb78f45b73b79b883161df3b48c5a56c44a311`, 48103 bytes, page count=n/a).
- Frozen derived identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:d1575e49879fdee6566d74f6d0bb78f45b73b79b883161df3b48c5a56c44a311`, 48103 bytes).
- Frozen converter: `none (Markdown source)`.
- Pre-S1 sanitation: 0 trace(s), 0 injection finding(s).
- S1 parse inventory: 37 sections, 6 tables, 554 numeric tokens with source locations.
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
- S5 DRAFT/GROUND: 98 candidate comment(s), 98 retained, 0 deleted, 98 criticism comment(s) converted to questions.
- S2/S4 claim verdicts:
- [claim-013] **unverifiable** — paper:16 — run overlap-aware and direct structured repair from the same verified state, — No implemented mechanical check proves or disproves this claim. Evidence: `paper:16`.
- [claim-028] **unverifiable** — paper:32 — small positive mean TOV effects (+3.53 and +1.54 points) but session intervals — No implemented mechanical check proves or disproves this claim. Evidence: `paper:32`.
- [claim-033] **unverifiable** — paper:36 — scored **33/39**, versus 17/39 for Plain, 16/39 for Graph, 25/39 for ordinary — No implemented mechanical check proves or disproves this claim. Evidence: `paper:36`.
- [claim-037] **unverifiable** — paper:40 — prospective equal-call primary comparison failed its integrity gate. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:40`.
- [claim-041] **unverifiable** — paper:43 — The stable result is therefore system-level — No implemented mechanical check proves or disproves this claim. Evidence: `paper:43`.
- [claim-048] **unverifiable** — paper:54 — can improve over one-pass generation, yet their composition is fragile. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:54`.
- [claim-055] **unverifiable** — paper:61 — can relations among failed candidate hypotheses improve the last repair call — No implemented mechanical check proves or disproves this claim. Evidence: `paper:61`.
- [claim-061] **unverifiable** — paper:67 — **semantic-relation value:** whether comparing what failed candidates mean — No implemented mechanical check proves or disproves this claim. Evidence: `paper:67`.
- [claim-062] **unverifiable** — paper:68 — improves repair beyond a final agent with the same candidates, evidence, — No implemented mechanical check proves or disproves this claim. Evidence: `paper:68`.
- [claim-065] **unverifiable** — paper:71 — complementary final-route crossovers into monotone system improvement. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:71`.
- [claim-089] **unverifiable** — paper:95 — **RQ1:** Does the complete anchored TOV system improve Plain, Graph, and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:95`.
- [claim-092] **unverifiable** — paper:99 — outperform generic and structured semantic-free final controls? — No implemented mechanical check proves or disproves this claim. Evidence: `paper:99`.
- [claim-105] **unverifiable** — paper:115 — complete tracks that expose both positive mean differences and large — No implemented mechanical check proves or disproves this claim. Evidence: `paper:115`.
- [claim-106] **unverifiable** — paper:117 — an exploratory equal-call dual-route comparison and repeated-session union — No implemented mechanical check proves or disproves this claim. Evidence: `paper:117`.
- [claim-177] **unverifiable** — paper:207 — priority affects provenance, not the observed pass label. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:207`.
- [claim-193] **unverifiable** — paper:233 — The semantic comparison is behavioral. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:233`.
- [claim-240] **unverifiable** — paper:279 — observed and is analyzed as exploratory rather than preregistered. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:279`.
- [claim-246] **unverifiable** — paper:296 — We report both the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:296`.
- [claim-261] **unverifiable** — paper:314 — `counter` task reports `no tests to run`; it is retained in the denominator — No implemented mechanical check proves or disproves this claim. Evidence: `paper:314`.
- [claim-278] **unverifiable** — paper:336 — Plain | 1 | Direct complete-track solve — No implemented mechanical check proves or disproves this claim. Evidence: `paper:336`.
- [claim-279] **unverifiable** — paper:337 — Graph | 1 | Requirement/invariant/counterexample graph, then edit — No implemented mechanical check proves or disproves this claim. Evidence: `paper:337`.
- [claim-280] **unverifiable** — paper:338 — Ordinary repair | 2 | Graph plus one generic execution-feedback repair — No implemented mechanical check proves or disproves this claim. Evidence: `paper:338`.
- [claim-281] **unverifiable** — paper:339 — Verified union | 3 | Deterministic task-wise union of passing `P/G/R` files — No implemented mechanical check proves or disproves this claim. Evidence: `paper:339`.
- [claim-282] **unverifiable** — paper:340 — Generic Critic | 4 | Verified union plus generic final repair — No implemented mechanical check proves or disproves this claim. Evidence: `paper:340`.
- [claim-283] **unverifiable** — paper:341 — Semantic-free structured | 4 | Union plus TOV ledger/falsification/audits, relations withheld — No implemented mechanical check proves or disproves this claim. Evidence: `paper:341`.
- [claim-284] **unverifiable** — paper:342 — **TOV v2** | **4** | Union plus semantic relations, disagreement falsification, and audits — No implemented mechanical check proves or disproves this claim. Evidence: `paper:342`.
- [claim-285] **unverifiable** — paper:343 — Non-overlap dual-route union | 5 | Recursive verified union of generic and semantic-free final routes — No implemented mechanical check proves or disproves this claim. Evidence: `paper:343`.
- [claim-286] **unverifiable** — paper:344 — **Recursive TOV union** | **5** | Recursive verified union of TOV and semantic-free final routes — No implemented mechanical check proves or disproves this claim. Evidence: `paper:344`.
- [claim-288] **unverifiable** — paper:346 — The supplement reports a — No implemented mechanical check proves or disproves this claim. Evidence: `paper:346`.
- [claim-292] **unverifiable** — paper:349 — That screen is not pooled with code results. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:349`.
- (+697 further extracted claim(s) — mostly unverifiable prose — omitted here for brevity; all are labelled in S2/S4 with source lines.)

## Comment

Recommendation: 3/6. No headline result is mechanically supported yet, so the recommendation stays borderline pending stronger evidence. Most useful next step for the authors — For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?

## Panel Reviews (provenance)

### Panel review 1 — theorist (accepted)

# Review: Mini Artichokes: Recursive Verified Anchoring Stabilizes Semantic-Overlap Program Repair

## Summary

This paper proposes Anchored Try--Semantic-Overlap--Verify (TOV), a test-time code-repair procedure that combines multiple whole-track candidates, immutable preservation of test-passing tasks, semantic comparison of unresolved hypotheses, falsification, and recursive union of independently repaired outputs. On 90 Aider Polyglot tasks, TOV reaches 58/90 versus 15/90 for Plain and 45/90 for ordinary execution-feedback repair. However, the stronger causal claim for semantic overlap is substantially weakened by post hoc design, unequal realized compute, and five-session replications whose intervals cross zero. The evidence supports verified redundant repair as a promising engineering system, but not yet a robust scientific demonstration that semantic-overlap reasoning itself produces repeatable gains.

## Strengths

- The paper clearly separates system-level performance from mechanism-level claims: it distinguishes “*candidate and anchor value*,” “*semantic-relation value*,” and “*recursive redundancy value*.” This is an important conceptual clarification.

- The anchoring mechanism is concrete and operationally meaningful. The paper states that “*for every task with max_j V_j(t)=1... every listed solution file from that candidate*” is installed and that “*an adapter restores all anchored bytes before evaluation*.” This provides a credible monotonicity guarantee on the supplied test suites.

- The primary benchmark retains complete tracks rather than selecting favorable tasks: “*all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks*.” The full-denominator table reports 58/90 for TOV, 45/90 for ordinary repair, and 15/90 for Plain.

- The paper provides useful rescue/harm accounting. Against the generic control, TOV has “*seven rescues and no harms*”; against the stricter semantic-free control, it has “*eight rescues and one harm*.” This is more informative than aggregate accuracy alone.

- The authors are unusually candid about negative and invalid evidence. They explicitly state that the Go Generic call was “*transport-null*,” that the Go replacement was run “*after TOV outcomes were known*,” and that the recursive analysis was “*post hoc*.” This substantially improves the credibility of the presentation.

- The replication analysis does not conceal instability. The Python differences are “*+4,-2,+2,0,+2*” and the C++ differences are “*+1,-1,0,+5,-3*,” with both reported intervals crossing zero. The paper correctly concludes that the semantic-relation instruction has not established session-level superiority.

- The recursive union has a valid mechanical property: “*for every task passed by either route... [bytes] were promoted into a second anchor map*.” The resulting 210/300 repeated task-session passes plausibly demonstrate the benefit of verified complementary redundancy, although not an isolated semantic-overlap effect.

## Weaknesses

- The central causal comparison is not cleanly identified. The semantic-free control was “*frozen only after all TOV outcomes and the MAC v9 critique were known*,” while the recursive composition was “*specified only after these repetitions revealed large branch crossovers*.” Thus the significant original 8:1 comparison and the recursive 59/90 result are both vulnerable to researcher degrees of freedom and post hoc selection.

- The five-session replications substantially undercut the main mechanism claim. The paper reports only “*+3.53 and +1.54 points*,” with session intervals `[-2.35,+8.24]` and `[-6.92,+11.54]` percentage points. Since whole-track calls are the natural experimental units, the task-level significance from the original 90 tasks should not be treated as strong evidence for a general semantic-overlap effect.

- The semantic-free ablation is only a prompt-level manipulation. The authors acknowledge that it “*cannot make latent model trajectories identical*” and that TOV and the control differ in realized tokens and latency. Table 5 shows TOV using 59,551 output tokens versus 54,728 for the semantic-free control and taking 1,422.3 versus 1,392.7 seconds. The observed difference may therefore reflect attention, verbosity, or compute allocation rather than semantic relations.

- The generic-control comparison is not an informative isolation of semantic overlap because TOV additionally imposes “*ledger/falsification/audits*,” whereas the generic Critic has “*no required ledger or audit schema*.” The paper appropriately introduces the stricter control, but that control is post hoc and still does not match exact computation.

- The benchmark evidence is concentrated in one model, one runtime, and four related code-repair tracks. The paper states that “*all semantic calls use one model and runtime*” and that “*only three language clusters exist*.” This leaves open whether the method depends on the particular model’s prompting behavior, the benchmark’s modularity, or the test harness.

- The recursive system is not compute-matched to its single-route competitors. It adds a second final route and then deterministically retains its successes. The authors concede that recursive dominance “*is purchased with another route*.” Consequently, 59/90 versus 54/90 is evidence for a broader redundant-system construction, not for the isolated value of semantic overlap.

- The proposed semantic representation is underspecified and not independently evaluated. The four fields—“*fault location, invariant, counterexample, and edit intent*”—are generated by the same model whose repairs are being judged, yet ledger correctness is not labeled. The paper itself says these fields “*are not independently labeled for diagnostic correctness*,” making it difficult to know whether the purported mechanism is actually semantic alignment or simply a beneficial prompt scaffold.

- External test feedback may make the setting materially easier than ordinary program repair. The paper explicitly describes it as “*test-available program repair*,” and failure tails can reveal behavioral expectations. This is a valid setting, but the claims should be more sharply limited to it; the evidence does not establish usefulness when tests are weak, unavailable, or misleading.

## Questions for the Authors

1. Can you provide a preregistered or otherwise outcome-independent replication of the semantic-free versus TOV comparison across multiple tracks and sessions, with the whole-track session treated as the primary unit?

2. How much of the TOV gain remains when the semantic-free control receives exactly the same output-token budget, audit requirements, and structured prompt length?

3. Can you ablate the four semantic fields individually, and can independent annotators verify whether the generated fault locations, invariants, counterexamples, and edit intents are correct?

4. What is the incremental value of semantic overlap after comparing TOV with a compute-matched structured repair control that retains falsification and audits but receives an equally detailed nonsemantic evidence summary?

5. Can the recursive result be compared against a compute-matched alternative that runs the same number of final routes but uses no semantic-overlap instruction?

6. How do the results change with different models, reasoning levels, or independent candidate-generation prompts?

## Scores

Soundness: 3/4 — The system protocol and caveats are carefully documented, but causal attribution is weakened by post hoc controls, unequal realized compute, and correlated whole-track calls.

Presentation: 4/4 — The paper is unusually clear about protocols, denominators, rescue/harm accounting, invalid runs, and limitations.

Significance: 3/4 — Verified redundant repair could be practically useful, but the current evidence supports an engineering principle more strongly than a broadly established scientific result.

Originality: 3/4 — The combination of immutable verified anchors, semantic disagreement, and recursive promotion is a plausible and differentiated synthesis, though its components are largely established ideas.

Overall recommendation: 3/6 — Borderline; promising system result but insufficiently clean evidence for the central mechanism claim.

Confidence: 4/5 — The paper is self-contained and its main methodological limitations are directly visible, although the empirical artifacts and runs cannot be independently verified here.

## Ethics and Limitations

The paper uses public coding exercises and no human participants. It appropriately notes that failure output can reveal behavioral expectations and that the method increases inference compute. The principal limitations are the single-model evaluation, shared whole-track call trajectories, only three primary language clusters, post hoc construction of the stricter control and recursive composition, unequal realized compute, and finite test-suite guarantees. Passing official tests establishes benchmark success, not correctness beyond the supplied tests. The Go result is also appropriately treated as a system-level sensitivity because the original Generic call failed its transport integrity gate.

## Comment

I recommend borderline consideration. The strongest contribution is the mechanically safe verified-union architecture, especially its ability to retain complementary successes without regressions. The most important issue is to establish, under an outcome-independent and compute-matched protocol, whether semantic-overlap reasoning adds reproducible value beyond structured evidence presentation, falsification, auditing, and simply running multiple repair routes.

### Panel review 2 — experimentalist (accepted)

# Review: Mini Artichokes: Recursive Verified Anchoring Stabilizes Semantic-Overlap Program Repair

## Summary

The paper introduces Anchored Try–Semantic-Overlap–Verify (TOV), a test-time program-repair procedure that preserves verified task solutions, compares unresolved candidate repairs at the level of behavioral obligations, and optionally unions independently verified final routes. On 90 Aider Polyglot tasks, TOV reaches 58/90 versus 51/90 for matched final controls, while recursive TOV reaches 59/90. However, the replication sessions produce small, statistically inconclusive semantic-overlap effects, so the strongest evidence supports verified redundancy as an engineering strategy more clearly than semantic overlap as a causal mechanism.

## Strengths

- The paper cleanly separates system-level and mechanism-level claims: it distinguishes “candidate and anchor value,” “semantic-relation value,” and “recursive redundancy value.” This is an important conceptual clarification for multi-call code agents.

- The verified-union design is concrete and appropriately conservative. The paper states that “every task with `max_j V_j(t)=1`” is frozen and that “a final arm therefore cannot exchange a known pass for a speculative repair.” This provides a meaningful protection against regressions.

- The evaluation retains complete benchmark tracks rather than selecting favorable tasks: “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks.” The paper also reports complete denominators, rescue/harm counts, latency, tokens, and integrity failures.

- The primary realized comparison is compelling at the task level: TOV achieves “58/90 versus 51/90” against the generic control, with “seven rescues and no harms,” and 58/90 versus 51/90 against the semantic-free structured control, with “eight rescues and one harm.”

- The authors are unusually candid about limitations and protocol failures. In particular, they explicitly state that “the original Generic call received no model response because of an endpoint 404,” and correctly treat the Go comparison as a “post-primary component sensitivity” rather than as successful prospective confirmation.

- The recursive rule has a genuine mechanical property: “for every task passed by either route, the complete passing solution-file bytes are promoted into a second anchor map.” The resulting 59/90 versus 54/90 equal-call system comparison is a plausible demonstration of verified complementarity, even though it is exploratory.

- The paper does not overclaim its most fragile result. Its conclusion explicitly says that “semantic-relation instructions do not yet have a repeatable mean superiority claim,” which is consistent with the reported replication intervals.

## Weaknesses

- The central semantic-overlap claim is not established by the replication evidence. The five-session Python differences are `+4,-2,+2,0,+2`, with a bootstrap interval of `[-2.35,+8.24]` percentage points, while C++ gives `+1,-1,0,+5,-3` with `[-6.92,+11.54]`. Thus the main mechanism does not demonstrate reliable superiority beyond session variation.

- The strongest 90-task semantic comparison is post hoc and has only three language-level clusters. Although the paper reports a task-level one-sided `p=.01953125`, it also reports track differences `[-1,+4,+4]` and a cluster sign value of `.5`. The task-level test conditions on shared whole-track calls, so it should not be interpreted as strong population-level evidence.

- The semantic-free control is not a fully independent or preregistered causal ablation. It “was frozen only after all TOV outcomes and the MAC v9 critique were known.” Moreover, the authors acknowledge that it matches “named instructions, not latent reasoning or exact realized compute.” The semantic-free control also has different realized cost: TOV uses 59,551 output tokens versus 54,728 for the structured control and takes 1,422.3 versus 1,392.7 seconds.

- The recursive comparison is substantially confounded by post hoc design and extra-route computation. The paper says that recursive composition “was chosen after the later crossovers,” and recursive dominance is explicitly “mechanical and uses an additional direct route.” Consequently, 59/90 versus 54/90 demonstrates a useful deployment construction, but not a causal benefit of semantic overlap or a compute-matched improvement.

- The Go result does not provide the intended prospective equal-call component test. The original Generic arm was transport-null, while the replacement was run “only after TOV outcomes were known.” The resulting sensitivity comparison, 33/39 versus 31/39 with `p=.3125` and CI `[-5.13,+15.38]`, is compatible with both modest benefit and harm.

- The baseline and prompt realizations are difficult to assess independently from the manuscript. Plain obtains only 15/90, while ordinary repair obtains 45/90 and the candidate union 48/90. Because each complete track is handled by one large model call, these results may be highly sensitive to prompt construction, context organization, and runtime trajectory. The paper reports these factors but does not provide enough controlled prompt or call-level analysis to determine how robust the striking baseline gaps are.

- The claimed semantic explanation is largely post hoc and not independently labeled. The paper states that the “eight-task interface pattern was formulated after the nine discordant tasks were known,” and that ledger fields “are not independently labeled for diagnostic correctness.” The examples are plausible, but they do not yet establish that semantic relations—not simply additional prompt structure or stochastic trajectory differences—caused the rescues.

## Questions for the Authors

1. Can you run a preregistered, multi-track evaluation in which the semantic-relation and semantic-free prompts are frozen before any outcome is observed, with enough independent whole-track sessions to estimate session-level effects?

2. How much of the TOV advantage remains when final arms are matched on realized input/output tokens, latency, and context length rather than only on nominal call count and caps?

3. Can you provide blinded or independently adjudicated labels for whether each ledger’s fault location, invariant, counterexample, and edit intent were correct, and test whether ledger quality predicts TOV rescues?

4. What is the effect of recursive anchoring alone, without semantic-overlap instructions—for example, a union of two independently generated generic final routes under the same verification and file-restoration rules?

5. How sensitive are the results to the initial candidate prompts, candidate ordering, anchor priority, failure-tail length, and model sampling seed?

6. Can the artifact support an independent reproduction of the complete 90-task table and the Go replacement sensitivity, including exact prompts, evaluator commands, and per-call traces?

## Scores

Soundness: 3/4 — The protocol and accounting are careful, but the causal mechanism is weakened by post hoc controls, unmatched realized compute, and inconclusive replications.

Presentation: 4/4 — The paper is unusually clear about experimental chronology, denominators, integrity failures, and the distinction between system and mechanism claims.

Significance: 3/4 — Verified redundancy for modular test-available repair is practically meaningful, but the broader semantic-overlap contribution remains uncertain.

Originality: 3/4 — The combination of behavioral overlap, immutable anchors, and recursive promotion is a distinctive formulation, though it builds on familiar ensembles, critics, and verification.

Overall recommendation: 3/6 — Borderline; the engineering construction is promising, but the main causal claim is not yet reliably supported.

Confidence: 4/5 — The paper is sufficiently self-contained to assess its logic and evidence, though the results and artifact hashes cannot be independently rerun here.

## Ethics and Limitations

The paper uses public coding exercises and no human participants. It appropriately acknowledges that exposing bounded test output creates a “test-available program repair” setting rather than ordinary one-shot code generation. The principal limitations are substantial and well stated by the authors: one model and runtime, correlated candidates, only three language clusters in the primary study, post hoc control and recursive design, finite test-suite validity, and increased inference cost. Verified anchors guarantee passing the supplied tests, not correctness beyond those tests.

## Comment

I recommend borderline rejection in the current form. The paper’s most valuable contribution is the concrete verified-anchoring and recursive-union construction, while its semantic-overlap mechanism remains promising but unconfirmed. The single most important revision is a genuinely prospective, compute-matched, multi-session evaluation with the semantic relation manipulated before outcomes are observed; without that, the reported 7-task advantage should be presented as a realized exploratory result rather than evidence of a repeatable causal improvement.

### Panel review 3 — scope_ablation (accepted)

# Review: Mini Artichokes: Recursive Verified Anchoring Stabilizes Semantic-Overlap Program Repair

## Summary

This paper proposes Anchored Try--Semantic-Overlap--Verify (TOV), a test-time code-repair procedure that preserves verified task solutions, compares unresolved candidate hypotheses at the level of behavioral obligations, and uses external tests to promote successful repairs. Across complete Rust30, Python34, and C++26 tracks, TOV reaches 58/90 versus 51/90 for matched final controls. A recursive dual-route variant reaches 59/90, and a subsequently frozen Go39 evaluation reaches 33/39. The paper is unusually candid about post-hoc design, transport failure, session variance, and the distinction between system-level gains and semantic-overlap causality.

## Strengths

- The paper clearly separates system performance from mechanism claims: it distinguishes “candidate and anchor value,” “semantic-relation value,” and “recursive redundancy value.” This is an important conceptual decomposition for test-time code repair.

- The verified-anchor mechanism is concrete and auditable. The paper states that “for every task with `max_j V_j(t)=1`” passing solution bytes are frozen, and that “an adapter restores all anchored bytes before evaluation.” This gives a meaningful monotonicity guarantee on the supplied test suite.

- The main evaluation retains complete tracks rather than selecting favorable tasks: “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks.” Table 1 reports the full 90-task denominator, with TOV at 58/90 versus 45/90 for ordinary repair.

- The matched-control design is substantially stronger than comparing only against Plain. The semantic-free control shares “the same ledger fields, counterexample-based falsification, and two audits,” while withholding semantic relations. This directly targets the claimed mechanism, even if it does not fully isolate it.

- The paper reports rescue and harm patterns rather than only aggregate accuracy. For example, TOV versus the generic control has “seven rescues and no harms,” while the stricter comparison has “eight rescues and one harm.” This makes the behavioral tradeoff inspectable.

- The authors appropriately qualify their conclusions. They explicitly state that the replications “do not reproduce a reliable session-level mean advantage” and conclude that semantic relations are “a promising but unconfirmed conditional mechanism.” This restraint improves the credibility of the system-level claims.

- The recursive construction has a genuine mechanical property: “for every task passed by either route, the complete passing solution-file bytes are promoted into a second anchor map.” The reported 210/300 repeated task-session passes versus 198 for TOV alone is consistent with the proposed stabilization objective, although it is not a compute-matched causal comparison.

## Weaknesses

- The central semantic-overlap causal claim is not convincingly established. The original TOV advantage is significant at the task level, but the semantic-free control “was frozen only after all TOV outcomes and the MAC v9 critique were known,” and the authors acknowledge that the contrast is “review-triggered and post hoc.” The two new five-session replications yield only “+3.53 and +1.54 points,” with both confidence intervals crossing zero. Thus the evidence supports a successful realized trajectory, not a reliably superior semantic-relation method.

- The effective statistical sample is much smaller than the 90-task presentation suggests. “All task rows within one arm share one whole-track model call,” and the cluster checks use only three language signs. The reported task-level p-values therefore provide limited evidence about generalization across calls, languages, or benchmark populations.

- The controls do not isolate semantic relations cleanly. The paper concedes that the semantic-free ablation is a “natural-language ablation” that “cannot make latent model trajectories identical.” In addition, Table 5 shows substantial compute differences: TOV uses 59,551 output tokens and 1,422.3 seconds versus 54,728 tokens and 1,392.7 seconds for the semantic-free control. The measured difference may therefore reflect prompt-induced reasoning trajectory or compute allocation rather than semantic overlap specifically.

- Recursive TOV is partly selected using the observed results it is later used to summarize. The paper states that “the recursive composition was chosen after the later crossovers,” and calls the equal-call comparison “post-hoc.” The Go evaluation was frozen before Go calls, which is valuable, but its primary Generic arm was transport-null and the valid replacement was run “only after TOV outcomes were known.” Consequently, the strongest prospective-looking result lacks a valid matched primary component comparison.

- The benchmark scope is narrow for the paper’s broader framing. The experiments use one model/runtime, one code-repair benchmark, four programming languages, and test-available evaluation. The authors themselves note that “other models may produce different candidate diversity,” and that the setting “is not a standard one-shot leaderboard protocol.” Claims about general test-time reasoning or universal repair should therefore be narrowed.

- The method’s load-bearing semantic fields are not independently validated. The paper says that “ledger fields are not independently labeled for diagnostic correctness,” and the interface-ambiguity explanation was “formulated after the nine discordant tasks were known.” It remains unclear whether the semantic representation is genuinely useful or merely a prompt format correlated with successful trajectories.

- The external test oracle may make the anchoring result highly benchmark-dependent. The paper states that “recursive verification guarantees monotonicity relative to either included route on the supplied official suites; it does not guarantee correctness beyond those tests.” Stronger validation on hidden tests, held-out repositories, or independent test suites is needed to establish practical program-repair reliability.

- The comparison to Plain conflates several improvements: multiple candidate calls, execution feedback, anchoring, structured prompts, and final repair. The paper correctly says that the Plain comparison “is not an overlap-only estimate,” but the large 43-task gain should not be interpreted as evidence for the specific TOV mechanism.

## Questions for the Authors

1. Can you run a preregistered, model-complete comparison across additional independent tracks or repeated calls in which TOV and the semantic-free control are matched for realized output-token and latency budgets?

2. Which individual components are responsible for the original TOV gain: the four semantic fields, explicit disagreement-driven falsification, the two audits, or simply the longer final prompt and output budget?

3. Can you evaluate final patches on independent tests or held-out repositories to determine whether byte-exact anchoring improves genuine correctness rather than only performance on the official finite suites?

4. How sensitive are the results to the choice of candidate priority `R > G > P`, the failure-tail format, and the amount of test output exposed to the model?

5. Can the semantic-overlap hypothesis be operationalized before observing outcomes—for example, with preregistered predictions about which tasks benefit—and tested independently of post-hoc interface-ambiguity analysis?

## Scores

Soundness: 3/4 — The execution-verified system is carefully specified and honestly analyzed, but causal evidence for semantic overlap is limited and several key comparisons are post hoc.

Presentation: 4/4 — The paper is exceptionally clear about protocols, denominators, controls, failure cases, and inferential limits.

Significance: 3/4 — Verified redundancy could be practically useful for test-available repair, but the broader impact is constrained by the narrow benchmark and expensive test-time procedure.

Originality: 3/4 — The combination of immutable verified anchors, behavioral overlap, and recursive promotion is a meaningful design contribution, although its components draw on established reflection, verification, and ensemble ideas.

Overall recommendation: 3/6 — Borderline; the system-level result is promising, but the paper does not yet establish a reproducible semantic-overlap advantage or broad generalization.

Confidence: 3/5 — The claims and limitations are sufficiently detailed to assess, but the conclusions depend heavily on reported execution artifacts and a small number of correlated whole-track calls.

## Ethics and Limitations

The paper uses public code exercises and reports no human participants or sensitive data. It appropriately discloses that failure output can reveal behavioral expectations and frames the work as test-available repair. The principal limitations are substantial inference cost, dependence on finite and potentially weak official tests, one model/runtime, correlated whole-track calls, narrow language and benchmark coverage, unequal realized compute, and post-hoc selection of the recursive composition. The Go transport failure is transparently reported rather than scored as a valid comparison.

## Comment

I recommend borderline acceptance at most. The strongest contribution is the engineering principle that externally verified partial solutions should become immutable anchors and that complementary repair routes can be safely unioned through verification. The authors’ most important next step is a preregistered, compute-matched evaluation that isolates the semantic-relation instruction across many independent model calls and includes independent correctness tests; without that, the paper supports verified redundancy more strongly than semantic-overlap repair as a causal mechanism.
