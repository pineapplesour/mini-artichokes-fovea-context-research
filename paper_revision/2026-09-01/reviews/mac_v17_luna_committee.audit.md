# ICML-Style Paper Review

## Paper and Evidence Identity

- Review method: full review — deterministic evidence audit + review panel. The panel's review is the official output; this document is its audit sidecar.
- Review Agent name/version: paper-reviewer / `sha256:9886349f92661c3c73b70f216a7038b741b47282d7624538ad207dd3fbb2d4c0`
- Review-agent spec path/hash: `review-agent-spec.md` / `sha256:08b13516a2cb0e5151c6b4dc24f98e6d191b35ee30d69ea300b2d6ff2d5a5945`
- Original paper identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:ffc264435c0a2d84f48fc8301faaec6e29a241b6e7028763d5f69a9a26fd2e7e` / `53788` bytes
- Derived Markdown identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:ffc264435c0a2d84f48fc8301faaec6e29a241b6e7028763d5f69a9a26fd2e7e` / `53788` bytes
- Original PDF page count: `n/a`
- Converter: `none (Markdown source)`
- Paper version/hash: `Mini_Artichokes_manuscript_v4.md` / `sha256:ffc264435c0a2d84f48fc8301faaec6e29a241b6e7028763d5f69a9a26fd2e7e`
- Evidence bundle reviewed: none (no evidence bundle supplied)
- Frozen at (UTC): `2026-09-03T18:10:42+00:00`

## Summary

We introduce **Mini Artichokes**, a. It reports 121 quantitative result claim(s) and cites 10 prior work(s). Deterministic audit: 0 contradiction(s), 0 dishonest self-certification(s), 0 mechanical finding(s); 0 result claim(s) evidence-backed, 817 unverifiable. Overall recommendation: 3/6 [claim-001].

## Strengths

- The paper situates its contribution against prior work (10 citation(s); related-work section present).

## Weaknesses

- The deterministic audit proved no contradiction, arithmetic error, or integrity breach; the remaining concern is limited to claims that could not be independently verified (see Questions).

## Questions for the Authors

1. For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?
2. 121 extracted result/arithmetic claim(s) could not be checked against the supplied evidence and are listed with their source lines in the Evidence Trace — could the authors provide the underlying results?

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
- Frozen review identity: `sha256:b8de1b8bc343f5ef45389959eae84d9bb86197d44aa803dcdbaab71818dffa33`.
- Verdict labels digest: `sha256:8d20e6bfd87597317a5278ccc734f26061b6e1469f8e64f8c92e78a428cf8c29`.
- External citation snapshot digest: `sha256:01545e382bf7b0636dcadf97adfec0e438018ba58ffefc7b6167718586eab0a7`.
- Scientific judgment identity: `sha256:17886850ff75cabc67a87391ed9f23c0d3e1f3dc4220536707c150ad8c3f89d0`.
- Review panel configuration: panel=3, model=`gpt-5.6-luna`, synthesis=area-chair.
- Panel reviewer `theorist`: prompt=`sha256:513c457aae00398daf5d9d3c241d3a8d4e2620462ace9790d8f1fef251825382`, response=`sha256:fd9b21cba9548d3b071aef47c1f1cd5a0cf3b08d7c3b6deeca7029907cdc3138`, status=ok.
- Panel reviewer `experimentalist`: prompt=`sha256:a43df80383030b0e87ec131234b575640c20c55eb4124e55074d799778fb220f`, response=`sha256:cce59ded858e6175d647ac0fd23beb1904d883d51b564b4dd3569f4d444c530a`, status=ok.
- Panel reviewer `scope_ablation`: prompt=`sha256:221029dd00c21b993f975e14fb2a902f90a952c1b2023627e59ddc6518d2b136`, response=`sha256:08fabc2b62417ddafd4e90e0a90cd9a643109661757c07ee7a4688993d17e97d`, status=ok.
- Output path: `mac_v17_luna_committee.md`.
- Frozen paper input: `Mini_Artichokes_manuscript_v4.md` (`sha256:ffc264435c0a2d84f48fc8301faaec6e29a241b6e7028763d5f69a9a26fd2e7e`).
- Frozen original identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:ffc264435c0a2d84f48fc8301faaec6e29a241b6e7028763d5f69a9a26fd2e7e`, 53788 bytes, page count=n/a).
- Frozen derived identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:ffc264435c0a2d84f48fc8301faaec6e29a241b6e7028763d5f69a9a26fd2e7e`, 53788 bytes).
- Frozen converter: `none (Markdown source)`.
- Pre-S1 sanitation: 0 trace(s), 0 injection finding(s).
- S1 parse inventory: 38 sections, 8 tables, 595 numeric tokens with source locations.
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
- S5 DRAFT/GROUND: 121 candidate comment(s), 121 retained, 0 deleted, 121 criticism comment(s) converted to questions.
- S2/S4 claim verdicts:
- [claim-024] **unverifiable** — paper:24 — scores **33/39**, versus 17/39 for Plain and 25/39 for ordinary repair: +41.03 — No implemented mechanical check proves or disproves this claim. Evidence: `paper:24`.
- [claim-029] **unverifiable** — paper:27 — effectiveness comparisons, not fixed-resource efficiency results. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:27`.
- [claim-032] **unverifiable** — paper:30 — same-five-call TOV-plus-Direct portfolio scores 59/90 versus 54/90 for — No implemented mechanical check proves or disproves this claim. Evidence: `paper:30`.
- [claim-033] **unverifiable** — paper:31 — Generic-plus-Direct, but this comparison was selected after route crossovers — No implemented mechanical check proves or disproves this claim. Evidence: `paper:31`.
- [claim-038] **unverifiable** — paper:36 — Thus verified redundancy is the supported system result; — No implemented mechanical check proves or disproves this claim. Evidence: `paper:36`.
- [claim-045] **unverifiable** — paper:47 — can improve over one-pass generation, yet their composition is fragile. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:47`.
- [claim-055] **unverifiable** — paper:57 — hypotheses improve one final repair route. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:57`.
- [claim-060] **unverifiable** — paper:62 — **semantic-relation value:** whether comparing what failed candidates mean — No implemented mechanical check proves or disproves this claim. Evidence: `paper:62`.
- [claim-061] **unverifiable** — paper:63 — improves repair beyond a final agent with the same candidates, evidence, — No implemented mechanical check proves or disproves this claim. Evidence: `paper:63`.
- [claim-090] **unverifiable** — paper:93 — **RQ1:** Does recursive verified redundancy improve Plain, Graph, and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:93`.
- [claim-110] **unverifiable** — paper:116 — complete tracks that expose both positive mean differences and large — No implemented mechanical check proves or disproves this claim. Evidence: `paper:116`.
- [claim-111] **unverifiable** — paper:118 — an exploratory equal-call dual-route comparison and repeated-session union — No implemented mechanical check proves or disproves this claim. Evidence: `paper:118`.
- [claim-119] **unverifiable** — paper:131 — End-to-end five-call effectiveness | 59/90 original; before-call-frozen 33/39 Go | Supported in the reported test-available setting — No implemented mechanical check proves or disproves this claim. Evidence: `paper:131`.
- [claim-120] **unverifiable** — paper:132 — Advantage over a same-call generic portfolio | 59/90 vs 54/90; Go replacement 33/39 vs 31/39 | Positive but exploratory/sensitivity-only — No implemented mechanical check proves or disproves this claim. Evidence: `paper:132`.
- [claim-148] **unverifiable** — paper:169 — an indivisible task it reduces to ordinary verifier-selected best-of-multiple. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:169`.
- [claim-195] **unverifiable** — paper:226 — priority affects provenance, not the observed pass label. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:226`.
- [claim-199] **unverifiable** — paper:233 — After its model call, the experiment — No implemented mechanical check proves or disproves this claim. Evidence: `paper:233`.
- [claim-211] **unverifiable** — paper:252 — The semantic comparison is behavioral. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:252`.
- [claim-246] **unverifiable** — paper:285 — `/tmp/artifacts/decision_ledger.json` with exactly one record for each frozen — No implemented mechanical check proves or disproves this claim. Evidence: `paper:285`.
- [claim-252] **unverifiable** — paper:289 — They do not score the natural-language diagnoses for — No implemented mechanical check proves or disproves this claim. Evidence: `paper:289`.
- [claim-272] **unverifiable** — paper:310 — verification preserves every observed pass from either included route on the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:310`.
- [claim-274] **unverifiable** — paper:312 — The construction was formulated after final-route crossovers were observed and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:312`.
- [claim-291] **unverifiable** — paper:329 — tasks observed passing in included route `k`, and let `A` be the prior anchor — No implemented mechanical check proves or disproves this claim. Evidence: `paper:329`.
- [claim-295] **unverifiable** — paper:333 — complete state already observed to pass; no unverified merged state is — No implemented mechanical check proves or disproves this claim. Evidence: `paper:333`.
- [claim-296] **unverifiable** — paper:334 — Hence its observed task score is at least that of the prior anchor set — No implemented mechanical check proves or disproves this claim. Evidence: `paper:334`.
- [claim-312] **unverifiable** — paper:359 — We report both the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:359`.
- [claim-327] **unverifiable** — paper:377 — `counter` task reports `no tests to run`; it is retained in the denominator — No implemented mechanical check proves or disproves this claim. Evidence: `paper:377`.
- [claim-344] **unverifiable** — paper:399 — Plain | 1 | Direct complete-track solve — No implemented mechanical check proves or disproves this claim. Evidence: `paper:399`.
- [claim-345] **unverifiable** — paper:400 — Graph | 1 | Requirement/invariant/counterexample graph, then edit — No implemented mechanical check proves or disproves this claim. Evidence: `paper:400`.
- [claim-346] **unverifiable** — paper:401 — Ordinary repair | 2 | Graph plus one generic execution-feedback repair — No implemented mechanical check proves or disproves this claim. Evidence: `paper:401`.
- (+787 further extracted claim(s) — mostly unverifiable prose — omitted here for brevity; all are labelled in S2/S4 with source lines.)

## Comment

Recommendation: 3/6. No headline result is mechanically supported yet, so the recommendation stays borderline pending stronger evidence. Most useful next step for the authors — For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?

## Panel Reviews (provenance)

### Panel review 1 — theorist (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper presents Mini Artichokes, a test-available program-repair system that preserves complete task solutions that pass an external verifier and applies two final repair routes only to unresolved tasks. One route uses semantic-overlap reasoning (TOV), while the other is a direct structured repair route; passing outputs from either are recursively promoted. On three complete Aider tracks, the system obtains 59/90 passes versus 45/90 for ordinary execution-feedback repair and 15/90 for Plain. On a subsequently frozen Go39 track, it obtains 33/39. The paper is commendably explicit that these are additional-compute effectiveness results and that the causal contribution of semantic overlap is not established.

## Strengths

- The central preservation mechanism is clearly specified and supported by a useful formal argument. The paper states that “a complete verified task state is removed from model discretion” and defines assumptions A1–A5, including “promotion copies the complete allowlisted solution-file tuple for a task.” Under these assumptions, the claimed union property is logically sound.

- The evaluation retains complete benchmark tracks rather than selecting favorable tasks. Table 1 reports all “30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” and the paper additionally evaluates “all 39 official Go tasks.” This substantially improves the credibility of the reported system-level comparison.

- The paper uses an appropriate task-level verifier and explicitly distinguishes test-label preservation from semantic correctness. The authors correctly state that recursive promotion “does not guarantee correctness beyond those tests,” and Section 3.6 makes clear that the formal property is not a claim of verifier completeness.

- The comparisons are unusually transparent about resource asymmetry. The paper says that the results are “effectiveness under the stated call cap,” not efficiency, and reports that “TOV uses fewer input and more output tokens than the stricter control and takes 29.6 more seconds.” This is important because the main gains involve substantially more model calls than Plain.

- The authors show good scientific restraint regarding the semantic-overlap hypothesis. They report that ten paired sessions have “small positive means with intervals crossing zero,” that C++ sessions include both a five-task TOV lead and a three-task control lead, and conclude that semantic overlap is “a productive conditional route, not a universal or 20-point causal gate.”

- The failure analysis is concrete and relevant. For example, Rust `fizzy` is retained as a harm because “the final file contained an extra closing brace and did not compile,” demonstrating that a correct diagnosis does not ensure a safe edit.

## Weaknesses

- The main empirical contribution is difficult to separate from additional test-time compute and best-of-multiple verification. Mini Artichokes uses five calls, ordinary repair uses two, and Plain uses one. The paper itself acknowledges that “candidate diversity, external execution, the verified floor, and both final routes contribute.” Thus the 59/90 versus 15/90 result establishes a larger compute-and-verification system, but not that the proposed recursive or semantic structure is responsible for most of the gain.

- The strongest same-call comparison is exploratory and only marginal under a two-sided test. Mini Artichokes obtains 59/90 versus 54/90 for the non-overlap union, but the paper reports “two-sided exact `p=.0625`” and explicitly says the recursive composition “was chosen after observing crossovers.” The Go replacement sensitivity is similarly weak: 33/39 versus 31/39 with `p=.3125` and a bootstrap interval of `[-5.13,+15.38]`.

- The prospective Go comparison is compromised at exactly the point where it would provide the strongest confirmation. The paper states that the preregistered Generic call was “transport-null,” containing “no model message, reasoning item, tool call, usage event, or final message.” The replacement was run only after TOV outcomes were known. Consequently, the frozen Go result supports the system’s performance against Plain and ordinary repair, but does not provide a valid prospective equal-call comparison against the generic portfolio.

- The semantic-free control is not a clean causal intervention. Although it matches ledger fields and audits, the paper concedes that it “matches named instructions, not latent reasoning or exact realized compute.” Since the proposed treatment is itself a natural-language instruction, this limitation is central: the observed difference may reflect prompt-induced trajectory changes, output length, or attention effects rather than semantic relations specifically.

- The replication evidence does not establish a reliable TOV advantage. Across ten paired sessions, Python differences are `+4,-2,+2,0,+2`, while C++ differences are `+1,-1,0,+5,-3`; both confidence intervals include substantial negative and positive effects. The paper appropriately reports this, but it substantially weakens any claim that TOV is a stable component rather than one occasionally productive stochastic route.

- The formal result is conditional on a narrow modularity assumption that limits generality. A1 requires that “the benchmark is partitioned into task units whose declared solution files and verifier do not cross task boundaries.” Many realistic repositories have shared modules, global build state, integration tests, or cross-task dependencies. The paper acknowledges this in Section 7, but the central recursive mechanism is therefore a benchmark-compatible construction rather than a broadly established program-repair principle.

- The benchmark evidence is concentrated in one model, one runtime, and four related tracks. The paper states, “all semantic calls use one model and runtime,” and only three language clusters are used for the original comparisons. The Go result helps, but its most discriminating comparator is post hoc. This leaves uncertainty about whether the observed candidate diversity and route complementarity generalize across models or repositories.

- The TOV ledger provides no independently validated semantic measurement. The protocol checks “parseability, task-ID set and order, row count, anchor bytes, integrity checks, and changed paths,” but “do[es] not score the natural-language diagnoses for semantic correctness.” Therefore, the paper demonstrates a prompt-and-route effect, not that the four behavioral fields are accurate representations of fault semantics.

## Questions for the Authors

1. Can you provide a compute-matched ablation in which all systems receive the same total model-token or wall-clock budget, including a generic best-of-multiple or repeated-repair baseline?

2. What is the incremental effect of recursive promotion alone, without TOV, relative to a verifier-selected multi-route system with the same number of calls?

3. Can the Go generic arm be rerun under a genuinely prospective protocol on a new untouched complete track, with the comparator frozen before either route is executed?

4. How sensitive are the results to the fixed priority rules (`R > G > P` and direct-route-first), the number of candidate routes, and the number of final routes?

5. Can independent annotators or programmatic checks validate whether TOV’s fault-location, invariant, counterexample, and edit-intent fields are correct and whether correctness of these fields predicts successful repair?

6. How does the method behave on repositories with shared solution files, integration tests, nondeterministic tests, or non-modular task dependencies, where A1 does not hold?

## Scores

Soundness: 3/4 — The preservation argument is valid under explicit assumptions, and the empirical results are carefully qualified, but causal attribution and prospective matched comparisons remain weak.

Presentation: 4/4 — The paper is unusually clear about chronology, denominators, integrity failures, resource asymmetry, and the limits of its claims.

Significance: 3/4 — Verified task-level redundancy could be practically useful, but the demonstrated contribution is specialized to test-available modular repair and additional compute.

Originality: 3/4 — The composition of immutable anchors, unresolved-set branching, and recursive promotion is a reasonable systems contribution, though much of the underlying machinery is familiar ensemble, verification, and iterative-repair design.

Overall recommendation: 3/6 — Borderline; the system result is promising, but the core mechanism is not isolated convincingly enough for a strong acceptance recommendation.

Confidence: 4/5 — The paper is self-contained and reports enough methodological detail to assess its logic and evidence, although the artifact-dependent experimental claims cannot be independently reproduced here.

## Ethics and Limitations

The paper uses public programming exercises and no human participants. It appropriately notes that failure output can reveal behavioral expectations and characterizes the setting as “test-available program repair.” The main limitations are substantial but candidly reported: one model and runtime, correlated candidate errors, only a few language clusters, post hoc design of some controls and recursive composition, finite test-suite specifications, weak causal isolation of semantic overlap, and increased compute and latency. The byte-preserving promotion mechanism protects observed benchmark passes, but it should not be interpreted as preserving real-world correctness beyond the supplied tests.

## Comment

I recommend borderline acceptance/rejection pending stronger evidence. The most important issue is to isolate recursive verified redundancy from simply spending more calls and taking the union of independently generated, test-passing repairs. A prospective, compute-matched comparison against a generic multi-attempt verifier on additional complete tracks would determine whether Mini Artichokes is a genuinely general algorithmic advance or primarily an effective benchmark-specific orchestration of extra test-time compute.

### Panel review 2 — experimentalist (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper proposes Mini Artichokes, a five-call program-repair system that generates Plain, Graph, and execution-feedback candidates, preserves complete task states that pass official tests as byte-exact anchors, and applies two final repair routes whose passing outputs are recursively unioned. Its strongest empirical claim is system-level effectiveness: it solves 59/90 Aider Polyglot tasks versus 45/90 for ordinary repair and 15/90 for Plain, and 33/39 Go tasks in a before-call-frozen evaluation. The narrower semantic-overlap component is presented more cautiously, since replications produce positive but uncertain effects.

## Strengths

- The paper clearly separates structural, system, and component claims. It explicitly states that “the primary claim concerns this verified system” and that semantic overlap is “a component hypothesis,” avoiding the common mistake of presenting an exploratory mechanism as established.

- The anchoring rule is conceptually clean and formally justified. Under A1–A5, “no unverified merged state is created,” and the stated preservation property follows from copying only complete task states already observed to pass. This is a genuine advantage over patch intersection or LLM voting when tasks are modular.

- The evaluation retains complete tracks rather than selecting favorable tasks. Table 1 reports all 30 Rust, 34 Python, and 26 C++ tasks, while Table 4 reports “all 39 official Go tasks.” The paper also states that tasks were “not ranked, screened, removed, replaced, or topped up.”

- The system result is substantial within the stated test-available setting. Mini Artichokes reaches “59/90 (65.6%)” versus “45/90 (50.0%)” for ordinary repair, and the Go evaluation reaches “33/39,” versus 25/39 for ordinary repair. The paper appropriately describes these as additional-compute effectiveness comparisons rather than efficiency results.

- The paper includes useful negative and boundary evidence. It reports that the earlier strict agreement gate solved “5/20 versus 7/20,” that QuixBugs Plain achieved “40/40,” and that the Go Generic invocation was “transport-null.” These disclosures make the empirical narrative more credible.

- The authors are unusually candid about uncertainty and post hoc choices. They acknowledge that the dual-route construction was chosen “after final-route crossovers were observed,” that the semantic-free control was designed after reviewer feedback, and that the replications “do not establish session-level superiority at `.05`.”

- Reproducibility and integrity safeguards are unusually detailed. The paper reports prompt and result hashes, exact ledger requirements, anchor-byte checks, forbidden-path checks, intention-to-treat handling, and realized token/latency measurements.

## Weaknesses

- The central system comparison is not a clean test of the proposed semantic mechanism. Mini Artichokes is effectively a verifier-selected union of two final routes, and its equal-call comparator differs by replacing Generic with TOV. The 59/90 versus 54/90 result is explicitly post hoc, while the before-call-frozen Go equal-call comparison is only 33/39 versus 31/39 with `p=.3125`. Thus the strong system gain over Plain or ordinary repair is confounded by extra calls and route multiplicity, whereas the mechanism-specific evidence is weak.

- The primary statistical evidence treats individual tasks as paired observations even though all tasks within an arm share one whole-track model call. The paper itself admits that “all task rows within one arm share one whole-track model call” and that task-level tests “condition on the realized calls.” Consequently, values such as `p=5.68e-14` for Mini Artichokes versus Plain substantially overstate evidence for generalization across calls or task populations. The reported three-track sign checks (`p=.125` and `p=.5`) are more appropriate, but they are underpowered and should receive greater prominence.

- The semantic-free control is not a fully controlled causal ablation. The paper concedes that it “matches named instructions, not latent reasoning or exact realized compute,” and Table 6 shows materially different final-call costs: TOV takes 1,422.3 seconds versus 1,392.7 for semantic-free structured and uses 59,551 versus 54,728 output tokens. The intervention may therefore change both semantic guidance and model behavior, length, and attention allocation.

- The most important prospective comparator failed operationally. The paper says the preregistered Go Generic call contained “no model message, reasoning item, tool call, usage event, or final message,” so the primary equal-call endpoint was unavailable. The replacement was run “after TOV outcomes were known.” Although this is honestly reported, it leaves the headline prospective system comparison without a valid matched control.

- The baseline protocol is unusual and may favor multi-stage systems. Plain is required to solve an entire 30-, 34-, 26-, or 39-task track in one call, producing 15/90 on the original tracks, while later methods receive intermediate test feedback and several calls. This is a legitimate bounded-compute experiment, but it is not directly comparable to standard per-task program-repair evaluations. The paper should establish whether the baseline is a strong deployment-relevant Plain Codex control rather than merely a deliberately difficult whole-track control.

- The paper does not provide a clean factorial ablation isolating the contribution of byte-exact anchoring, candidate diversity, recursive promotion, and the two-route union. The verified floor reaches 48/90, but there is no matched “same candidates, no anchoring” condition; recursive promotion is shown to be label-preserving by construction, but its incremental value over simply selecting the best final route is not isolated under a preregistered protocol.

- Claims about semantic overlap remain largely interpretive. The paper says that ledgers “selected a more specific obligation,” but also states that “ledger diagnoses were not independently annotated.” The eight-task interface pattern was “formulated after the nine discordant tasks were known,” so the qualitative account is plausible but not validated as a measurable mediator or predictor.

- Generality is narrower than the title and broader framing may suggest. The evidence is limited to four Exercism-derived programming languages under test availability, with private tests and bounded failure tails. The authors correctly state that this is not ordinary one-shot code generation, but the paper provides little evidence that the procedure transfers to repositories with cross-task state, nondeterministic tests, weak tests, or unavailable verifiers.

## Questions for the Authors

1. Can you provide a preregistered, call-matched comparison of Mini Artichokes against a generic two-route verifier union, with the route choice and analysis fixed before any final-route outcomes are observed?

2. How does Plain perform under a matched per-task or matched-total-token protocol, rather than one whole-track call, and would the system-level gains remain against that stronger baseline?

3. What is the incremental effect of anchoring alone, recursive promotion alone, candidate diversity, and dual-route execution in a factorial ablation with identical candidate artifacts and compute accounting?

4. Can you independently annotate the TOV ledger fields and test whether semantic-overlap features predict rescues prospectively, rather than explaining the nine discordant tasks post hoc?

5. How should the reported significance be interpreted when each arm’s 30–39 task outcomes are generated by a single correlated whole-track call? Can you report confidence intervals and tests whose resampling unit is the model call across more independent tracks or sessions?

## Scores

Soundness: 3/4 — The construction is well specified and the reported results are internally coherent, but mechanism-specific causal evidence and independent-call statistical support are limited.

Presentation: 4/4 — The paper is unusually clear about chronology, controls, caveats, integrity checks, and the distinction between system and component claims.

Significance: 3/4 — Verified recursive promotion is a useful systems idea with substantial gains in this setting, though its practical and broader significance depend on stronger matched baselines.

Originality: 3/4 — The composition of immutable verifier-backed anchors with heterogeneous final routes appears meaningful, but its ingredients build on established ensembles, execution feedback, and self-correction methods.

Overall recommendation: 4/6 — Weak accept / borderline accept; the system contribution is promising and well documented, but the main causal and generalization claims need stronger evidence.

Confidence: 4/5 — The paper is sufficiently self-contained to assess, though the empirical conclusions depend on reported artifacts and unusual whole-track experimental units.

## Ethics and Limitations

The paper uses public programming exercises and reports no human participants. It appropriately notes that failure output can reveal behavioral expectations and describes the setting as test-available repair rather than ordinary code generation. The main limitations are candidly stated: one model and runtime, correlated whole-track calls, only three original language clusters, cumulative rather than fully preregistered evidence, a post hoc recursive composition, an invalid primary Go Generic call, finite test suites, and assumptions about task-local files and stable verifiers. These limitations materially constrain causal attribution and transfer, but they do not invalidate the preservation property or the reported bounded-setting results.

## Comment

I recommend weak accept. The paper’s strongest contribution is the precise, verifier-backed composition rule that preserves complete passing task states and can exploit route complementarity without destructive patch merging. The single most important revision is to separate this structural/system claim from the semantic-overlap claim through a genuinely preregistered, call-matched, independently replicated comparison with a stronger Plain baseline and call-level statistical analysis.

### Panel review 3 — scope_ablation (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper introduces Mini Artichokes, a five-call program-repair system that preserves task-level solutions passing an external test suite and recursively unions passing outputs from direct and semantic-overlap repair routes. Across complete Rust, Python, and C++ tracks it reports 59/90 versus 45/90 for ordinary repair and 15/90 for Plain; on a subsequently frozen Go track it reports 33/39. The paper appropriately distinguishes the stronger system-level claim from the weaker, uncertain causal claim about semantic overlap.

## Strengths

- The central preservation mechanism is clearly specified and formally motivated: “a complete verified task state is removed from model discretion,” and under A1–A5 “its observed task score is at least that of the prior anchor set and each included route.”

- The evaluation retains full denominators rather than selecting easy tasks: “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” followed by “all 39 official Go tasks.”

- The paper provides meaningful controls. In particular, the semantic-free structured control “uses the same ledger fields, counterexample-based falsification, and two audits as TOV,” while withholding relations.

- The authors are commendably candid about inferential limits. They explicitly state that the semantic-relation effect is “not established,” that the Go equal-call sensitivity “fails both the .05 directional gate and the separately named +8/39 strong-effect gate,” and that the reported comparisons are “not compute efficiency or correctness beyond the supplied tests.”

- The repeated-session analysis is useful for exposing trajectory variance rather than hiding it: the paired differences are `+4,-2,+2,0,+2` for Python and `+1,-1,0,+5,-3` for C++, with intervals crossing zero.

- The paper reports failure cases and protocol violations, including “the sole semantic-free-only pass” lost because of “an extra closing brace,” and a C++ call that “generated forbidden `a.out`.” This improves credibility and makes the proposed safeguards concrete.

## Weaknesses

- The strongest empirical advantage is not isolated to recursive verified redundancy. Mini Artichokes changes several factors simultaneously: candidate diversity, external execution feedback, additional calls, anchoring, TOV, and a second final route. The paper itself concedes that “Candidate diversity, external execution, the verified floor, and both final routes contribute.” Consequently, the 59/90 versus 15/90 or 45/90 comparisons establish an effectiveness result under a larger compute budget, but do not identify which mechanism is responsible.

- The most relevant equal-call comparison is post hoc. “The recursive dual-route analysis was specified only after these repetitions revealed large branch crossovers,” and the 59/90 versus 54/90 result is therefore “a post-hoc equal-call system contrast.” The Go result does not repair this limitation because its prospective Generic arm was “transport-null,” while the replacement was run “after TOV outcomes were known.”

- The semantic-overlap claim is weakly supported relative to the prominence of the proposed method. The original TOV advantage is statistically positive at the task level, but the five-session replications have wide intervals—Python `[-2.35,+8.24]` percentage points and C++ `[-6.92,+11.54]`—and neither establishes session-level superiority at `.05`. The paper appropriately acknowledges this, but the component’s general value remains unresolved.

- Task-level significance is liable to overstate evidence because “each task vector is generated inside one whole-track call.” The paper reports cluster checks, but only three language clusters exist; thus the apparent 7-task TOV advantage and 16-task system advantage are based on few stochastic whole-track trajectories.

- The semantic-free ablation is not fully causal. Although named fields and audits are held fixed, the authors state that it “cannot make latent model trajectories identical,” and the controls are not matched for realized tokens or latency. TOV uses 59,551 output tokens versus 54,728 for the semantic-free control and takes 1,422.3 versus 1,392.7 seconds. This leaves prompt-induced attention and compute differences as plausible explanations.

- Generalization beyond test-available, task-modular repositories is limited. The preservation theorem requires “no cross-task test dependency,” “isolated workspaces,” and a “stable verifier,” while the study exposes bounded official failure output between calls. These are important assumptions, not merely implementation details, and the experiments do not test settings where tests are weak, unavailable, nondeterministic, or globally coupled.

- The claimed semantic explanation is post hoc and not independently measured. The paper says the eight-task “interface pattern was formulated after the nine discordant tasks were known” and that “ledger diagnoses were not independently annotated.” Thus the interpretation that TOV succeeds by identifying interface obligations is plausible but currently speculative.

- The comparison to Plain is practically incomplete as a deployment argument. Mini Artichokes uses five whole-track model calls plus intermediate test execution, and the paper states that it is “intended for quality-sensitive repair, not cheap default completion.” Without a quality-at-fixed-token, fixed-latency, or cost-normalized comparison, the practical significance of the gains is uncertain.

## Questions for the Authors

1. Can you provide a preregistered, compute-matched comparison of recursive verified redundancy against a generic two-route or multi-route portfolio, with all route choices and promotion rules frozen before model calls?

2. How much of the Mini Artichokes gain remains after ablating each component separately: Graph, ordinary repair, anchoring, TOV, direct repair, and recursive promotion?

3. Can you evaluate the method on repositories with cross-task dependencies, weaker or nondeterministic tests, or no test feedback, to establish the boundary of the preservation argument?

4. What is the performance at matched total tokens, latency, and monetary cost rather than matched nominal call count?

5. Can independent annotators label the TOV ledger fields and test whether semantic overlap predicts successful repairs prospectively, rather than only explaining already observed discordances?

6. How sensitive are the results to model family, reasoning level, prompt paraphrases, and candidate correlation?

## Scores

Soundness: 3/4 — The system construction and test-label preservation argument are strong, but causal attribution and generalization are limited.

Presentation: 4/4 — The paper is unusually explicit about protocols, chronology, controls, failures, and evidential boundaries.

Significance: 3/4 — Verified task-level promotion is practically relevant, but the evidence is confined to a narrow test-available repair regime.

Originality: 3/4 — The composition of immutable verified anchors, unresolved-set branching, and recursive promotion is interesting, though its ingredients are individually familiar.

Overall recommendation: 3/6 — Borderline; promising system result, but the central mechanism and broader scientific claim need stronger matched and prospective evidence.

Confidence: 4/5 — The paper is sufficiently self-contained to assess its argument and reported evidence, though the underlying artifacts and experiments cannot be independently rerun here.

## Ethics and Limitations

The study uses public code exercises and no human participants. The authors appropriately disclose that failure output can reveal behavioral expectations and that the method increases inference compute. The main limitations are substantive: one model/runtime, correlated candidates, few language clusters, post hoc control and route design, unvalidated ledger semantics, finite test specifications, and substantial extra compute. Passing tests therefore certifies only benchmark behavior, not general program correctness.

## Comment

I recommend borderline acceptance. The strongest contribution is the test-label-preserving recursive union, which is clearly defined and supported by complete-track effectiveness results; the semantic-overlap route should be presented as exploratory rather than as an established causal improvement. The most important revision is a genuinely prospective, compute-matched ablation that isolates recursive promotion from TOV, candidate diversity, and the additional final route, ideally across more independent tracks or models.
