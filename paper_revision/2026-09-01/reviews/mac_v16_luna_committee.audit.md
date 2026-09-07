# ICML-Style Paper Review

## Paper and Evidence Identity

- Review method: full review — deterministic evidence audit + review panel. The panel's review is the official output; this document is its audit sidecar.
- Review Agent name/version: paper-reviewer / `sha256:9886349f92661c3c73b70f216a7038b741b47282d7624538ad207dd3fbb2d4c0`
- Review-agent spec path/hash: `review-agent-spec.md` / `sha256:08b13516a2cb0e5151c6b4dc24f98e6d191b35ee30d69ea300b2d6ff2d5a5945`
- Original paper identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:eec5159c38c90813080a75221f82564a784a728adcc9bf965501e4a4595fb9b1` / `52277` bytes
- Derived Markdown identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:eec5159c38c90813080a75221f82564a784a728adcc9bf965501e4a4595fb9b1` / `52277` bytes
- Original PDF page count: `n/a`
- Converter: `none (Markdown source)`
- Paper version/hash: `Mini_Artichokes_manuscript_v4.md` / `sha256:eec5159c38c90813080a75221f82564a784a728adcc9bf965501e4a4595fb9b1`
- Evidence bundle reviewed: none (no evidence bundle supplied)
- Frozen at (UTC): `2026-09-03T17:49:05+00:00`

## Summary

We introduce **Mini Artichokes**, a. It reports 109 quantitative result claim(s) and cites 10 prior work(s). Deterministic audit: 0 contradiction(s), 0 dishonest self-certification(s), 0 mechanical finding(s); 0 result claim(s) evidence-backed, 786 unverifiable. Overall recommendation: 3/6 [claim-001].

## Strengths

- The paper situates its contribution against prior work (10 citation(s); related-work section present).

## Weaknesses

- The deterministic audit proved no contradiction, arithmetic error, or integrity breach; the remaining concern is limited to claims that could not be independently verified (see Questions).

## Questions for the Authors

1. For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?
2. 109 extracted result/arithmetic claim(s) could not be checked against the supplied evidence and are listed with their source lines in the Evidence Trace — could the authors provide the underlying results?

## Scores

- Overall recommendation: 3/6 — Adopted from the review panel; rationale in the review's Scores section.
- Soundness: 3/4 — Adopted from the review panel; rationale in the review's Scores section.
- Presentation: 3/4 — Adopted from the review panel; rationale in the review's Scores section.
- Significance: 3/4 — Adopted from the review panel; rationale in the review's Scores section.
- Originality: 3/4 — Adopted from the review panel; rationale in the review's Scores section.
- Confidence: 4/5 — Adopted from the review panel; rationale in the review's Scores section.

## Ethics and Limitations

Paper text was treated only as data. The injection audit sanitized hidden HTML and Unicode format controls before claim analysis and found 0 reviewer-directed instruction attempt(s). Broader ethics and evidence-quality claims outside S3 remain unverifiable [claim-001].

## Evidence Trace

- Pipeline execution: `S1 parse -> S2 claims -> S3 mech-check -> S4 verdicts -> S5 compose -> S6 freeze`.
- Frozen review identity: `sha256:25dba9760a5652a2523e533146d4c9ad8527a12280c3858eb343e0d9e4218c83`.
- Verdict labels digest: `sha256:41f950dd04c705ecdbd64b055f85cdee61eee1c9d07a466ac3805737c116ae6d`.
- External citation snapshot digest: `sha256:01545e382bf7b0636dcadf97adfec0e438018ba58ffefc7b6167718586eab0a7`.
- Scientific judgment identity: `sha256:09721c5712e84b6f20e90951208310bb37ff65695d7de3d21da279ce08869802`.
- Review panel configuration: panel=3, model=`gpt-5.6-luna`, synthesis=area-chair.
- Panel reviewer `theorist`: prompt=`sha256:f400aaf0fa411c7b4507853bcfd11731b7eadc014bdbe2276e36e7293124f717`, response=`sha256:d3bd49de6e66faec67e18944a790c86efeda589b76df9e40477ad77eb59aca6b`, status=ok.
- Panel reviewer `experimentalist`: prompt=`sha256:5f23eecf2a3e5c1aab35608176b62c5a57901f440fe884c9e77135bee735f6b4`, response=`sha256:7b68bd762235e98e2d20079bd09ac67e16dee329e3905cf40b2575be6997044d`, status=ok.
- Panel reviewer `scope_ablation`: prompt=`sha256:977a901850d44b10d5141c95004c8bf78ed818445f61d8bdff0a685b1582ae7a`, response=`sha256:ad3d1dcbc6336603c546f3fff2853d95b5d1ed9f82ab42dd326d4c5009f8fa5e`, status=ok.
- Output path: `mac_v16_luna_committee.md`.
- Frozen paper input: `Mini_Artichokes_manuscript_v4.md` (`sha256:eec5159c38c90813080a75221f82564a784a728adcc9bf965501e4a4595fb9b1`).
- Frozen original identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:eec5159c38c90813080a75221f82564a784a728adcc9bf965501e4a4595fb9b1`, 52277 bytes, page count=n/a).
- Frozen derived identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:eec5159c38c90813080a75221f82564a784a728adcc9bf965501e4a4595fb9b1`, 52277 bytes).
- Frozen converter: `none (Markdown source)`.
- Pre-S1 sanitation: 0 trace(s), 0 injection finding(s).
- S1 parse inventory: 38 sections, 8 tables, 616 numeric tokens with source locations.
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
- S5 DRAFT/GROUND: 109 candidate comment(s), 109 retained, 0 deleted, 109 criticism comment(s) converted to questions.
- S2/S4 claim verdicts:
- [claim-029] **unverifiable** — paper:29 — At equal five-call count, TOV-plus-Direct scores 59/90 versus 54/90 for the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:29`.
- [claim-031] **unverifiable** — paper:31 — `p=.03125`), but this recursive comparison was selected after route crossovers — No implemented mechanical check proves or disproves this claim. Evidence: `paper:31`.
- [claim-033] **unverifiable** — paper:35 — small positive mean TOV effects (+3.53 and +1.54 points) but session intervals — No implemented mechanical check proves or disproves this claim. Evidence: `paper:35`.
- [claim-038] **unverifiable** — paper:39 — scored **33/39**, versus 17/39 for Plain, 16/39 for Graph, 25/39 for ordinary — No implemented mechanical check proves or disproves this claim. Evidence: `paper:39`.
- [claim-045] **unverifiable** — paper:44 — because of an endpoint 404, so the prospective equal-call component comparison — No implemented mechanical check proves or disproves this claim. Evidence: `paper:44`.
- [claim-050] **unverifiable** — paper:48 — verified redundancy is the supported result; semantic overlap is a productive — No implemented mechanical check proves or disproves this claim. Evidence: `paper:48`.
- [claim-056] **unverifiable** — paper:58 — can improve over one-pass generation, yet their composition is fragile. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:58`.
- [claim-066] **unverifiable** — paper:68 — hypotheses improve one final repair route. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:68`.
- [claim-071] **unverifiable** — paper:73 — **semantic-relation value:** whether comparing what failed candidates mean — No implemented mechanical check proves or disproves this claim. Evidence: `paper:73`.
- [claim-072] **unverifiable** — paper:74 — improves repair beyond a final agent with the same candidates, evidence, — No implemented mechanical check proves or disproves this claim. Evidence: `paper:74`.
- [claim-101] **unverifiable** — paper:104 — **RQ1:** Does recursive verified redundancy improve Plain, Graph, and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:104`.
- [claim-121] **unverifiable** — paper:127 — complete tracks that expose both positive mean differences and large — No implemented mechanical check proves or disproves this claim. Evidence: `paper:127`.
- [claim-122] **unverifiable** — paper:129 — an exploratory equal-call dual-route comparison and repeated-session union — No implemented mechanical check proves or disproves this claim. Evidence: `paper:129`.
- [claim-130] **unverifiable** — paper:142 — End-to-end five-call effectiveness | 59/90 original; before-call-frozen 33/39 Go | Supported in the reported test-available setting — No implemented mechanical check proves or disproves this claim. Evidence: `paper:142`.
- [claim-131] **unverifiable** — paper:143 — Advantage over a same-call generic portfolio | 59/90 vs 54/90; Go replacement 33/39 vs 31/39 | Positive but exploratory/sensitivity-only — No implemented mechanical check proves or disproves this claim. Evidence: `paper:143`.
- [claim-159] **unverifiable** — paper:180 — an indivisible task it reduces to ordinary verifier-selected best-of-multiple. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:180`.
- [claim-206] **unverifiable** — paper:237 — priority affects provenance, not the observed pass label. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:237`.
- [claim-210] **unverifiable** — paper:244 — After its model call, the experiment — No implemented mechanical check proves or disproves this claim. Evidence: `paper:244`.
- [claim-222] **unverifiable** — paper:263 — The semantic comparison is behavioral. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:263`.
- [claim-266] **unverifiable** — paper:306 — verification preserves every observed pass from either included route on the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:306`.
- [claim-268] **unverifiable** — paper:308 — The construction was formulated after final-route crossovers were observed and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:308`.
- [claim-285] **unverifiable** — paper:325 — tasks observed passing in included route `k`, and let `A` be the prior anchor — No implemented mechanical check proves or disproves this claim. Evidence: `paper:325`.
- [claim-289] **unverifiable** — paper:329 — complete state already observed to pass; no unverified merged state is — No implemented mechanical check proves or disproves this claim. Evidence: `paper:329`.
- [claim-290] **unverifiable** — paper:330 — Hence its observed task score is at least that of the prior anchor set — No implemented mechanical check proves or disproves this claim. Evidence: `paper:330`.
- [claim-300] **unverifiable** — paper:350 — We report both the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:350`.
- [claim-315] **unverifiable** — paper:368 — `counter` task reports `no tests to run`; it is retained in the denominator — No implemented mechanical check proves or disproves this claim. Evidence: `paper:368`.
- [claim-332] **unverifiable** — paper:390 — Plain | 1 | Direct complete-track solve — No implemented mechanical check proves or disproves this claim. Evidence: `paper:390`.
- [claim-333] **unverifiable** — paper:391 — Graph | 1 | Requirement/invariant/counterexample graph, then edit — No implemented mechanical check proves or disproves this claim. Evidence: `paper:391`.
- [claim-334] **unverifiable** — paper:392 — Ordinary repair | 2 | Graph plus one generic execution-feedback repair — No implemented mechanical check proves or disproves this claim. Evidence: `paper:392`.
- [claim-335] **unverifiable** — paper:393 — Verified union | 3 | Deterministic task-wise union of passing `P/G/R` files — No implemented mechanical check proves or disproves this claim. Evidence: `paper:393`.
- (+756 further extracted claim(s) — mostly unverifiable prose — omitted here for brevity; all are labelled in S2/S4 with source lines.)

## Comment

Recommendation: 3/6. No headline result is mechanically supported yet, so the recommendation stays borderline pending stronger evidence. Most useful next step for the authors — For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?

## Panel Reviews (provenance)

### Panel review 1 — theorist (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper proposes Mini Artichokes, a five-call program-repair system that preserves complete task solutions passing an external test suite, repairs only unresolved tasks, and recursively unions passing outputs from heterogeneous final routes. Its strongest empirical claim is system-level: 59/90 tasks on three Aider Polyglot tracks and 33/39 on a subsequently frozen Go track. The narrower claim that semantic-overlap reasoning itself is reliably beneficial is appropriately presented as exploratory.

## Strengths

- The paper identifies a clear and practically important systems mechanism: “a complete verified task state is removed from model discretion, only unresolved units are branched, and passing states from heterogeneous routes are recursively promoted.” This is a sensible way to exploit task-level external verification.

- The preservation argument is explicit and appropriately conditional. Under assumptions A1–A5, the paper states that “no unverified merged state is created,” and the formula `Acc(F) = (|A| + Σ V_F(t))/n` makes the source of the observed floor transparent.

- The evaluation retains complete tracks rather than selecting favorable tasks. Table 1 reports “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” with Mini Artichokes achieving 59/90 versus 45/90 for ordinary repair and 15/90 for Plain.

- The paper is unusually candid about evidential boundaries. It explicitly says that “the supported result is verified redundancy,” while “semantic overlap is a productive conditional route, not a universal or 20-point causal gate.” This substantially improves the credibility of the presentation.

- The authors report negative and integrity-related outcomes rather than silently excluding them: the Go Generic call was “transport-null,” the Rust `fizzy` case contained “an extra closing brace,” and one C++ replication generated forbidden `a.out`. This is good experimental hygiene.

- The replication analysis correctly recognizes dependence and variance. The paper notes that task-level tests “condition on the realized calls,” and reports whole-track session differences with intervals that cross zero.

## Weaknesses

- The central system comparison is not compute-matched in the dimensions that matter operationally. Mini Artichokes uses five calls and additional recursive evaluation, while Plain uses one and ordinary repair uses two. The paper reports that TOV took “29.6 more seconds” than the stricter control and explicitly states that “tokens and latency are not exact.” Thus the large gains over Plain and ordinary repair establish effectiveness with more test-time computation, not a clear algorithmic advantage at a fixed budget.

- The strongest equal-call comparison was selected after observing the data. The paper states that “the recursive variant evaluates both final outputs” only after “final-route crossovers were observed,” and calls the 59/90 versus 54/90 result “post-hoc.” The Go evaluation is frozen at the system level, but its equal-call component comparison depends on a replacement Generic run “after TOV outcomes were known.” Consequently, the evidence for superiority over a generic same-budget portfolio remains weak and vulnerable to selection effects.

- The semantic-overlap component is not isolated robustly. The original TOV advantage is seven tasks against the semantic-free control, but the control “was frozen only after all TOV outcomes and the MAC v9 critique were known.” In the two frozen replication studies, the mean effects are only +3.53 and +1.54 percentage points, with intervals `[-2.35,+8.24]` and `[-6.92,+11.54]`. The paper therefore supports TOV as one potentially complementary branch, but not as a demonstrated causal improvement.

- The formal guarantee is valuable but narrow and partly tautological: if a verifier correctly certifies task-local complete states and promotion copies those states without modification, preserving observed test labels follows by construction. The paper itself acknowledges that it “does not guarantee correctness beyond those tests.” The scientific contribution therefore depends primarily on empirical complementarity, which is precisely the part supported by limited and post-hoc evidence.

- The method is underspecified as a reproducible algorithm. TOV’s key operations—“fault location,” “violated requirement,” “smallest counterexample class,” “semantic agreements and disagreements,” and “selected evidence”—are described as ledger fields and natural-language instructions, but no deterministic representation, prompt, parsing rule, or adjudication protocol is given in the paper. Different implementations could instantiate substantially different methods.

- The benchmark evidence is narrow relative to the general framing. All semantic calls use “one model and runtime,” only four programming languages are tested, and the tasks are modular, test-available Exercism-style problems. The preservation mechanism may be much less useful for repositories with cross-task state, nondeterministic tests, or weak test coverage; these assumptions are acknowledged but not stress-tested.

- The statistical significance claims could be overread. The paper reports task-level exact tests such as `p=5.68e-14`, while also admitting that all tasks within an arm share “one whole-track model call.” The subsequent cluster-level checks are underpowered (`p=.125` for three positive generic-control differences), so the paper does not establish population-level generalization across languages or benchmark families.

## Questions for the Authors

1. Can you provide a preregistered, compute-matched comparison between Mini Artichokes, the generic Critic-plus-Direct portfolio, and a strong generic iterative repair baseline, with identical token, wall-clock, and evaluator-call budgets?

2. What exact prompts, schemas, parsing rules, and failure-handling procedures define TOV and the “direct structured route”? Could an independent implementation reproduce the method without access to private experimental artifacts?

3. How does recursive promotion perform on tasks with cross-task file dependencies, nondeterministic tests, incomplete test coverage, or repositories where a task’s solution files are not task-local?

4. Can you run additional independent models and benchmarks under a precommitted protocol to determine whether the observed route complementarity persists beyond `gpt-5.6-luna` and the four Aider tracks?

5. How much of Mini Artichokes’ 59/90 score comes from candidate diversity, ordinary execution feedback, anchoring, direct repair, TOV, and recursive promotion in a fully crossed ablation with matched calls and compute?

## Scores

Soundness: 3/4 — The preservation property is well argued and the empirical accounting is candid, but causal attribution and compute-matched superiority are not established.

Presentation: 3/4 — The paper is unusually clear about chronology and limitations, though the many nested comparisons and route labels make the experimental object difficult to reconstruct.

Significance: 3/4 — Verified task-state preservation is a useful systems idea, but its current evidence is confined to a narrow test-available repair regime.

Originality: 3/4 — The composition of immutable verified anchors with recursive route union is plausibly novel, although its ingredients are individually familiar.

Overall recommendation: 3/6 — Borderline; promising mechanism and careful reporting, but insufficient evidence for a strong general or causal claim.

Confidence: 4/5 — The paper is sufficiently self-contained to assess the argument and reported results, though the underlying artifacts and exact prompts cannot be independently checked here.

## Ethics and Limitations

The paper uses public code-repair tasks and no human participants. It appropriately notes that failure output can reveal behavioral expectations and therefore characterizes the setting as “test-available program repair.” The main limitations are substantial: one model/runtime, correlated candidates, only four language tracks, finite test suites, additional compute, post-hoc recursive composition, and a natural-language rather than mechanistically isolated semantic-free control. The authors are commendably explicit that anchors preserve benchmark passes rather than correctness beyond the supplied tests. I found no hidden reviewer-directed text.

## Comment

I lean borderline rather than reject because the recursive verified-union mechanism is coherent, useful, and supported by substantial full-track measurements. The decisive issue is whether the paper can demonstrate that Mini Artichokes provides a reproducible advantage over a genuinely compute-matched generic portfolio, rather than mainly benefiting from additional calls, post-hoc route selection, and benchmark-specific experimental evolution. A preregistered, independently reproducible, compute-matched evaluation with precise TOV specification would most change my assessment.

### Panel review 2 — experimentalist (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper proposes Mini Artichokes, a test-available program-repair system that preserves task-level passing solutions as byte-exact anchors and recursively unions passing outputs from heterogeneous repair routes. Its strongest claim is system-level effectiveness: 59/90 tasks on three Aider Polyglot tracks and 33/39 on a subsequently frozen Go track. The paper appropriately separates this from the narrower claim that its semantic-overlap route, TOV, is independently superior.

## Strengths

- The central preservation mechanism is clearly specified and has a genuine structural guarantee. The paper states: “A complete verified task state is removed from model discretion, only unresolved units are branched, and passing states from heterogeneous routes are recursively promoted.” Under A1–A5, the stated preservation property follows directly from copying complete passing task states rather than merging speculative edits.

- The evaluation retains complete tracks rather than selecting favorable tasks. It reports “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” followed by a complete Go39 evaluation. This is substantially stronger than reporting only successfully repaired or hand-selected examples.

- The paper provides useful matched comparisons and rescue/harm accounting. In Table 1, Mini Artichokes obtains 59/90 versus 54/90 for the equal-call non-overlap dual-route union, with “five rescues and no harms.” The common-anchor decomposition also makes clear which improvements occur beyond the 48-task verified floor.

- The authors are commendably candid about inferential limits. For example, they explicitly state that “the semantic-relation instruction is therefore supported as a productive heterogeneous branch, not as a reliably superior standalone policy,” and disclose that the Go Generic primary arm was “transport-null.”

- The replication analysis exposes trajectory variance rather than hiding it. The Python sessions have differences `+4,-2,+2,0,+2`, while C++ has `+1,-1,0,+5,-3`; both reported intervals cross zero. This is valuable evidence against an inflated claim of a universally reliable TOV effect.

- The paper distinguishes mechanical test-label preservation from semantic correctness. The qualification that anchors preserve “benchmark passes, not proof of correctness beyond those tests” is important and appropriately stated.

## Weaknesses

- The strongest empirical system comparison is confounded by additional computation and post hoc route selection. Mini Artichokes is a five-call system, while Plain and ordinary repair use one and two calls respectively; the paper itself concedes that these are “nested, additional-compute comparisons.” Moreover, the recursive dual-route design “was specified only after these repetitions revealed large branch crossovers.” Thus 59/90 demonstrates an effective test-time-compute portfolio, but does not establish that the proposed architecture is superior to other five-call generic portfolios.

- The causal evidence for semantic overlap is weak and largely exploratory. The original TOV-versus-control result is significant at the task level, but the paper says the semantic-free control “was frozen only after all TOV outcomes and the MAC v9 critique were known,” and labels the contrast “review-triggered and post hoc.” The five-session replications produce non-significant session-level results with CIs `[-2.35,+8.24]` and `[-6.92,+11.54]` percentage points. This supports a possible small effect, not a robust semantic-overlap advantage.

- The equal-call baseline is incomplete on the most important prospective generalization track. The Go Generic invocation “received no model response because of an endpoint 404,” and the replacement was run “only after TOV outcomes were known.” The resulting 33/39 versus 31/39 comparison is explicitly a post-primary sensitivity and has `p=.3125`. Consequently, Go provides useful evidence for the recursive system versus simpler baselines, but not a clean prospective test against the claimed same-call comparator.

- The benchmark scope is narrow and unusually favorable to the method’s assumptions. The authors require task-local files, isolated verification, informative failure output, and a trusted external test suite. They also acknowledge that one Go task reports “no tests to run.” The results therefore establish effectiveness in a specific test-available, modular benchmark setting, not general program repair.

- The semantic mechanism is not operationally measured independently of final success. The paper states that “ledger diagnoses were not independently annotated,” and the proposed interface-ambiguity pattern was “formulated after the nine discordant tasks were known.” Without blinded labeling or preregistered criteria, it is difficult to determine whether TOV’s semantic fields cause better decisions or merely induce a different model trajectory.

- The reported comparison does not fully match compute. Table 6 shows TOV using 59,551 output tokens and 1,422.3 seconds, compared with 54,728 and 1,392.7 seconds for the semantic-free control. The paper correctly makes no efficiency claim, but the additional output and latency complicate attribution even within equal-call comparisons.

- The system’s final gain over the verified floor is modest on the original tracks: 59/90 versus 48/90, and only one task separates Mini Artichokes from TOV alone. The large Go result is encouraging but rests on one track and lacks a valid prospective equal-call Generic arm. The conclusion should therefore emphasize a promising verified portfolio rather than a broadly validated universal repair method.

## Questions for the Authors

1. Can you provide a preregistered, compute-matched comparison against several generic five-call portfolios, including best-of-five verified union, repeated generic repair, and independent direct attempts, on new complete tracks?

2. How does Mini Artichokes compare with a five-call portfolio that uses the same recursive promotion rule but replaces TOV and Direct with two generic independently prompted repair agents?

3. Can you independently annotate the TOV ledger fields and test whether correct semantic diagnoses predict rescues, rather than analyzing those fields only after observing outcomes?

4. What is the performance when test feedback is less informative, partially unavailable, noisy, or delayed? This would clarify whether the method’s advantage is fundamentally due to anchoring, failure feedback, or semantic overlap.

5. Can the authors report cost-normalized accuracy or a fixed-token/fixed-time comparison, especially since “TOV uses more realized compute than Generic”?

## Scores

Soundness: 3/4 — The preservation construction is sound and the empirical reporting is unusually candid, but causal attribution is limited by post hoc selection, trajectory dependence, and the incomplete Go control.

Presentation: 4/4 — The paper is well organized, technically explicit, and clearly distinguishes structural guarantees from empirical claims.

Significance: 3/4 — Verified task-level redundancy is practically useful, but the demonstrated scope is limited to a favorable test-available benchmark regime.

Originality: 3/4 — The composition of anchors, unresolved-set branching, and recursive verifier promotion is a plausible systems contribution, though its ingredients are related to established ensembles, reflection, and best-of-multiple verification.

Overall recommendation: 3/6 — Borderline; the system result is promising, but the central semantic mechanism and broad generality are not yet sufficiently established.

Confidence: 4/5 — The paper provides enough self-contained detail for a reasonably confident assessment, although the underlying artifacts and runs cannot be independently verified here.

## Ethics and Limitations

The paper uses public coding exercises and no human participants, and it discloses that models do not receive private tests or gold implementations. The main ethical and practical concern is resource usage: the method uses multiple long model calls and external execution, with the paper reporting that “the method increases inference compute.” The authors honestly acknowledge correlated same-model errors, only three original language clusters, post hoc cumulative design, finite test-suite validity, incomplete prospective Go comparison, and the narrow assumptions behind byte-level promotion. These limitations materially constrain the generality of the claims but are presented responsibly.

## Comment

I recommend borderline acceptance/rejection depending on the venue’s tolerance for exploratory systems results. The most important revision is a new, preregistered, compute-matched evaluation of recursive verified redundancy against strong generic five-call portfolios, with a valid prospective comparator and independently assessed semantic diagnoses. This would determine whether the paper’s contribution is a broadly useful verification architecture or primarily an effective but benchmark- and trajectory-dependent engineering portfolio.

### Panel review 3 — scope_ablation (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper proposes Mini Artichokes, a five-call program-repair system that preserves complete task states passing an external test suite, applies multiple repair routes only to unresolved tasks, and recursively promotes newly passing states. Its secondary contribution is TOV, which uses semantic relations among failed hypotheses to guide falsification. On 90 Aider Polyglot tasks, the system reaches 59/90 versus 45/90 for ordinary execution-feedback repair and 15/90 for Plain; on a subsequently frozen Go39 track, it reaches 33/39. The paper appropriately narrows its strongest claim to verified redundancy rather than claiming a universal causal benefit from semantic overlap.

## Strengths

- The central preservation mechanism is clearly specified and supported by a genuine construction argument: “a complete verified task state is removed from model discretion” and “no unverified merged state is created.” The A1–A5 contract makes the scope of the formal guarantee explicit.

- The evaluation retains complete tracks rather than selecting favorable tasks: “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” followed by “all 39 official Go tasks.” This is substantially stronger than reporting only repaired examples or filtered subsets.

- The paper distinguishes nested system effectiveness from component causality. It explicitly states that the 59/90 versus 45/90 comparison is “not efficiency or overlap-only,” and that semantic overlap is “not established” as a repeatable standalone effect. This is unusually careful interpretation.

- The matched original comparison is informative: TOV has “seven rescues and no harms” against Generic and “eight rescues and one harm” against the semantic-free structured control. The semantic-free control also shares “the same ledger fields, counterexample-based falsification, and two audits,” which makes the component comparison more meaningful than a Plain-only baseline.

- The work includes negative and failure evidence rather than presenting only successes. For example, “the sole semantic-free-only pass was Rust `fizzy`,” where TOV’s diagnosis was correct but “the final file contained an extra closing brace.” The paper also reports that QuixBugs was already at “40/40,” leaving no rescue headroom.

- The replication results are honestly reported. The Python and C++ five-session studies have positive means but confidence intervals crossing zero, including C++ differences of “`+1,-1,0,+5,-3`.” This appropriately limits the semantic-overlap conclusion.

- The artifact and integrity reporting are strong in principle: the paper reports source commits, hashes, task IDs, byte comparisons, forbidden-path checks, and transport failures. The Go endpoint failure is disclosed rather than silently replaced in the primary analysis.

## Weaknesses

- The headline system comparison is not compute-matched. Mini Artichokes uses “five calls: `P/G/R`, TOV, and the direct structured route,” whereas Plain uses one call and ordinary repair uses two. Thus the large gains of 59/90 over 15/90 and 45/90 establish an expensive test-available portfolio’s effectiveness, but do not isolate the recursive rule or establish a favorable quality–compute tradeoff.

- The recursive gain is partly mechanically guaranteed and is evaluated after observing route crossovers. The paper itself says “the recursive composition was chosen after the later crossovers” and that dominance “uses an additional direct route.” The 59/90 versus 54/90 result is therefore a post hoc portfolio construction, not strong evidence that recursive redundancy would improve a prespecified deployment policy.

- The strongest semantic-overlap evidence is selection- and trajectory-sensitive. The semantic-free control was “designed after TOV results and reviewer feedback,” and the original TOV advantage is significant at the task level despite only three language clusters. The replications give wide intervals—Python `[-2.35,+8.24]` and C++ `[-6.92,+11.54]` percentage points—so the paper does not establish a stable semantic-relation effect.

- The statistical precision of the 90-task contrasts is easy to overinterpret because all tasks within a language track share one whole-track model call. Although the paper reports cluster-level caveats, values such as `p=5.68e-14` and `p=6.10e-5` primarily quantify realized task discordance, not independent evidence across calls, languages, or benchmark populations.

- The Go confirmation is incomplete for the most relevant equal-call comparison. The preregistered Generic call was “transport-null,” and the replacement was run “after TOV outcomes were known.” Consequently, the impressive frozen Go system result supports end-to-end effectiveness, but the Go evidence does not provide a clean prospective component comparison.

- The key semantic mechanism is not operationally validated independently of outcomes. The paper concedes that “ledger diagnoses were not independently annotated.” Without blinded human or automated assessment of whether the four semantic fields correctly identify obligations, it remains unclear whether TOV’s benefit comes from semantic overlap, additional output structure, prompt-induced effort, or stochastic trajectory differences.

- Generalization is narrow. All experiments use “one model and runtime,” four programming languages from one benchmark family, test-available feedback, and task-local file promotion. The formal property depends on “no cross-task test dependency” and a stable verifier, so the claimed universal-answer-engine implications are not supported by these experiments.

- The comparison is not token- or latency-matched. TOV takes “29.6 more seconds” than the stricter control and produces more output tokens. The paper makes no efficiency claim, but this leaves unresolved whether its modest quality advantage is worth the additional cost in realistic settings.

## Questions for the Authors

1. Can you run a preregistered, multi-track comparison in which the recursive dual-route policy, route order, and analysis are frozen before any outcomes, with a compute-matched non-recursive baseline?

2. What is the marginal contribution of each element—immutable anchoring, TOV’s semantic fields, falsification, audits, and recursive promotion—under a factorial or sequential ablation?

3. Can you provide blinded evaluations of ledger quality, separately measuring whether TOV correctly identifies fault location, invariant, counterexample class, and edit intent?

4. How does Mini Artichokes behave when tasks have cross-file or cross-task dependencies, nondeterministic tests, weaker tests, or no executable verifier?

5. Can the authors report quality as a function of total tokens, wall-clock time, and monetary cost, rather than only call count?

## Scores

Soundness: 3/4 — The construction and measurements are coherent, but causal attribution and independence are limited.

Presentation: 3/4 — Exceptionally transparent and well organized, though the many nested comparisons make the evidential hierarchy difficult to parse.

Significance: 3/4 — Verified task-state preservation is practically useful, but the tested setting is narrow and compute-expensive.

Originality: 3/4 — Recursive verifier-backed promotion and the specific TOV interpretation are plausible compositional contributions, though built from familiar ingredients.

Overall recommendation: 3/6 — Borderline; promising system evidence, but insufficiently isolated mechanism and generalization evidence for acceptance as a strong ICML result.

Confidence: 4/5 — The paper is self-contained enough to assess its argument and reported evidence, though the underlying artifacts and executions were not independently rerun.

## Ethics and Limitations

The paper uses public programming tasks and reports no human participants. It appropriately notes that failure output can reveal behavioral expectations and labels the setting “test-available program repair.” The principal limitations are material: one model/runtime, one benchmark family, few language clusters, additional inference cost, finite test specifications, post hoc recursive composition, and a transport-null primary Go comparator. The paper is commendably candid about these limitations, but they substantially constrain claims of general-purpose robustness.

## Comment

I recommend borderline rather than acceptance. The most important issue is to separate the appealing mechanical preservation property from the empirical claims about recursive redundancy and semantic overlap. A preregistered, compute-matched, multi-track evaluation with component ablations and independent ledger-quality assessment would determine whether Mini Artichokes is a broadly useful algorithmic contribution or primarily an effective but expensive benchmark-specific portfolio.
