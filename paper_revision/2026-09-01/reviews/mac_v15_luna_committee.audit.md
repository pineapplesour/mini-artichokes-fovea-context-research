# ICML-Style Paper Review

## Paper and Evidence Identity

- Review method: full review — deterministic evidence audit + review panel. The panel's review is the official output; this document is its audit sidecar.
- Review Agent name/version: paper-reviewer / `sha256:9886349f92661c3c73b70f216a7038b741b47282d7624538ad207dd3fbb2d4c0`
- Review-agent spec path/hash: `review-agent-spec.md` / `sha256:08b13516a2cb0e5151c6b4dc24f98e6d191b35ee30d69ea300b2d6ff2d5a5945`
- Original paper identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:1c65cc085d16dd9f8160d80ab6f8276c73f6fab6095ffaefb60bf5147615e03b` / `50879` bytes
- Derived Markdown identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:1c65cc085d16dd9f8160d80ab6f8276c73f6fab6095ffaefb60bf5147615e03b` / `50879` bytes
- Original PDF page count: `n/a`
- Converter: `none (Markdown source)`
- Paper version/hash: `Mini_Artichokes_manuscript_v4.md` / `sha256:1c65cc085d16dd9f8160d80ab6f8276c73f6fab6095ffaefb60bf5147615e03b`
- Evidence bundle reviewed: none (no evidence bundle supplied)
- Frozen at (UTC): `2026-09-03T17:44:18+00:00`

## Summary

We introduce **Mini Artichokes**, a. It reports 104 quantitative result claim(s) and cites 10 prior work(s). Deterministic audit: 0 contradiction(s), 0 dishonest self-certification(s), 0 mechanical finding(s); 0 result claim(s) evidence-backed, 770 unverifiable. Overall recommendation: 3/6 [claim-001].

## Strengths

- The paper situates its contribution against prior work (10 citation(s); related-work section present).

## Weaknesses

- The deterministic audit proved no contradiction, arithmetic error, or integrity breach; the remaining concern is limited to claims that could not be independently verified (see Questions).

## Questions for the Authors

1. For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?
2. 104 extracted result/arithmetic claim(s) could not be checked against the supplied evidence and are listed with their source lines in the Evidence Trace — could the authors provide the underlying results?

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
- Frozen review identity: `sha256:2209810884b071753cc58668e287f28fe1aab3c9be45ddb7b897d92c6e3e42e2`.
- Verdict labels digest: `sha256:e00398e6e79202ca2e85a6f13c90ae7aeaad648d4deae5c23cc01f124ba38e9c`.
- External citation snapshot digest: `sha256:01545e382bf7b0636dcadf97adfec0e438018ba58ffefc7b6167718586eab0a7`.
- Scientific judgment identity: `sha256:f8c67e29575d25f3cabe4b27f63fb106348742ccd07748daf2437f33d03a1c45`.
- Review panel configuration: panel=3, model=`gpt-5.6-luna`, synthesis=area-chair.
- Panel reviewer `theorist`: prompt=`sha256:bc644767b27a09849e1d140f07d70eb4f1c3a4a34bade80703ea32dbad4306c6`, response=`sha256:cea485fa27259ffc803363999f5b07ec5d50482c5d3264f9c9637035f71495c5`, status=ok.
- Panel reviewer `experimentalist`: prompt=`sha256:faefdee975690930bcc756c03c8b10ff07a3b2adf0af41a86d53743674654556`, response=`sha256:bb32c48fdcec25012885fbc1e0cff33544e11ce1db086fb529aee3a370be5a47`, status=ok.
- Panel reviewer `scope_ablation`: prompt=`sha256:f777fedc7df472a9d5c3cc62e0e1c1d7d37044fdd2317a3ac484bcc38e32d446`, response=`sha256:279b076450f2fda21c3a0bdae85e1763a858ea71b4de4565dd5b1497a0402c30`, status=ok.
- Output path: `mac_v15_luna_committee.md`.
- Frozen paper input: `Mini_Artichokes_manuscript_v4.md` (`sha256:1c65cc085d16dd9f8160d80ab6f8276c73f6fab6095ffaefb60bf5147615e03b`).
- Frozen original identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:1c65cc085d16dd9f8160d80ab6f8276c73f6fab6095ffaefb60bf5147615e03b`, 50879 bytes, page count=n/a).
- Frozen derived identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:1c65cc085d16dd9f8160d80ab6f8276c73f6fab6095ffaefb60bf5147615e03b`, 50879 bytes).
- Frozen converter: `none (Markdown source)`.
- Pre-S1 sanitation: 0 trace(s), 0 injection finding(s).
- S1 parse inventory: 38 sections, 7 tables, 598 numeric tokens with source locations.
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
- S5 DRAFT/GROUND: 104 candidate comment(s), 104 retained, 0 deleted, 104 criticism comment(s) converted to questions.
- S2/S4 claim verdicts:
- [claim-030] **unverifiable** — paper:31 — small positive mean TOV effects (+3.53 and +1.54 points) but session intervals — No implemented mechanical check proves or disproves this claim. Evidence: `paper:31`.
- [claim-035] **unverifiable** — paper:35 — scored **33/39**, versus 17/39 for Plain, 16/39 for Graph, 25/39 for ordinary — No implemented mechanical check proves or disproves this claim. Evidence: `paper:35`.
- [claim-042] **unverifiable** — paper:40 — because of an endpoint 404, so the prospective equal-call component comparison — No implemented mechanical check proves or disproves this claim. Evidence: `paper:40`.
- [claim-047] **unverifiable** — paper:44 — verified redundancy is the supported result; semantic overlap is a productive — No implemented mechanical check proves or disproves this claim. Evidence: `paper:44`.
- [claim-053] **unverifiable** — paper:54 — can improve over one-pass generation, yet their composition is fragile. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:54`.
- [claim-063] **unverifiable** — paper:64 — hypotheses improve one final repair route. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:64`.
- [claim-068] **unverifiable** — paper:69 — **semantic-relation value:** whether comparing what failed candidates mean — No implemented mechanical check proves or disproves this claim. Evidence: `paper:69`.
- [claim-069] **unverifiable** — paper:70 — improves repair beyond a final agent with the same candidates, evidence, — No implemented mechanical check proves or disproves this claim. Evidence: `paper:70`.
- [claim-096] **unverifiable** — paper:98 — **RQ1:** Does recursive verified redundancy improve Plain, Graph, and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:98`.
- [claim-116] **unverifiable** — paper:121 — complete tracks that expose both positive mean differences and large — No implemented mechanical check proves or disproves this claim. Evidence: `paper:121`.
- [claim-117] **unverifiable** — paper:123 — an exploratory equal-call dual-route comparison and repeated-session union — No implemented mechanical check proves or disproves this claim. Evidence: `paper:123`.
- [claim-190] **unverifiable** — paper:215 — priority affects provenance, not the observed pass label. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:215`.
- [claim-194] **unverifiable** — paper:222 — After its model call, the experiment — No implemented mechanical check proves or disproves this claim. Evidence: `paper:222`.
- [claim-206] **unverifiable** — paper:241 — The semantic comparison is behavioral. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:241`.
- [claim-250] **unverifiable** — paper:284 — verification preserves every observed pass from either included route on the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:284`.
- [claim-252] **unverifiable** — paper:286 — The construction was formulated after final-route crossovers were observed and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:286`.
- [claim-269] **unverifiable** — paper:303 — tasks observed passing in included route `k`, and let `A` be the prior anchor — No implemented mechanical check proves or disproves this claim. Evidence: `paper:303`.
- [claim-273] **unverifiable** — paper:307 — complete state already observed to pass; no unverified merged state is — No implemented mechanical check proves or disproves this claim. Evidence: `paper:307`.
- [claim-274] **unverifiable** — paper:308 — Hence its observed task score is at least that of the prior anchor set — No implemented mechanical check proves or disproves this claim. Evidence: `paper:308`.
- [claim-284] **unverifiable** — paper:328 — We report both the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:328`.
- [claim-299] **unverifiable** — paper:346 — `counter` task reports `no tests to run`; it is retained in the denominator — No implemented mechanical check proves or disproves this claim. Evidence: `paper:346`.
- [claim-316] **unverifiable** — paper:368 — Plain | 1 | Direct complete-track solve — No implemented mechanical check proves or disproves this claim. Evidence: `paper:368`.
- [claim-317] **unverifiable** — paper:369 — Graph | 1 | Requirement/invariant/counterexample graph, then edit — No implemented mechanical check proves or disproves this claim. Evidence: `paper:369`.
- [claim-318] **unverifiable** — paper:370 — Ordinary repair | 2 | Graph plus one generic execution-feedback repair — No implemented mechanical check proves or disproves this claim. Evidence: `paper:370`.
- [claim-319] **unverifiable** — paper:371 — Verified union | 3 | Deterministic task-wise union of passing `P/G/R` files — No implemented mechanical check proves or disproves this claim. Evidence: `paper:371`.
- [claim-320] **unverifiable** — paper:372 — Generic Critic | 4 | Verified union plus generic final repair — No implemented mechanical check proves or disproves this claim. Evidence: `paper:372`.
- [claim-321] **unverifiable** — paper:373 — Semantic-free structured | 4 | Union plus TOV ledger/falsification/audits, relations withheld — No implemented mechanical check proves or disproves this claim. Evidence: `paper:373`.
- [claim-322] **unverifiable** — paper:374 — **TOV v2** | **4** | Union plus semantic relations, disagreement falsification, and audits — No implemented mechanical check proves or disproves this claim. Evidence: `paper:374`.
- [claim-323] **unverifiable** — paper:375 — Non-overlap dual-route union | 5 | Recursive verified union of generic and semantic-free final routes — No implemented mechanical check proves or disproves this claim. Evidence: `paper:375`.
- [claim-324] **unverifiable** — paper:376 — **Mini Artichokes** | **5** | Recursive verified union of TOV and semantic-free direct routes — No implemented mechanical check proves or disproves this claim. Evidence: `paper:376`.
- (+740 further extracted claim(s) — mostly unverifiable prose — omitted here for brevity; all are labelled in S2/S4 with source lines.)

## Comment

Recommendation: 3/6. No headline result is mechanically supported yet, so the recommendation stays borderline pending stronger evidence. Most useful next step for the authors — For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?

## Panel Reviews (provenance)

### Panel review 1 — theorist (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper proposes Mini Artichokes, a test-available program-repair system that preserves complete task solutions passing an external verifier, applies multiple repair routes only to unresolved tasks, and recursively promotes newly passing solutions. Its central empirical claim is system-level: it reaches 59/90 tasks on three Aider Polyglot tracks and 33/39 on a subsequently frozen Go track. A narrower TOV component uses semantic overlap and disagreement among candidate repairs to guide falsification, but the paper appropriately reports that this component is not consistently superior.

## Strengths

- The verified-union mechanism is clearly specified and has a genuine formal guarantee under explicit assumptions: “Under A1--A5... the recursively promoted output passes every task in `A union (union_k S_k)` under the same verifier invocation used for promotion.” This is a useful and correctly scoped preservation property.

- The evaluation retains complete tracks rather than selecting favorable tasks: “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” followed by “all 39 official Go tasks.” Table 1 reports the full 90-task denominator, and Table 4 reports the full Go39 track.

- The paper distinguishes system effectiveness from component causality. It explicitly states that the 59/90 result is “not overlap-specific causal evidence” and that the Go endpoint is “a frozen system evaluation and post-primary component sensitivity.” This is unusually good scientific calibration.

- The controls are thoughtfully constructed. In particular, the semantic-free control retains “the same ledger fields, counterexample-based falsification, and two audits as TOV,” while withholding semantic relations. This directly targets the proposed mechanism more effectively than a Plain-only comparison.

- The paper reports failures and protocol violations rather than hiding them. For example, “The sole semantic-free-only pass was Rust `fizzy`,” where “the final file contained an extra closing brace,” and one C++ call “generated forbidden `a.out`.” The transport-null Go Generic call is also disclosed.

- The route-combination result is practically meaningful in the stated setting: Mini Artichokes achieves 59/90 versus 54/90 for the equal-call non-overlap dual-route union, and the repeated union reaches “210/300 repeated task-session passes, versus 198 for TOV alone.” The paper correctly describes this as mechanical stabilization rather than proof of a standalone semantic effect.

## Weaknesses

- The strongest empirical claims are nested-compute comparisons, not compute-matched improvements over a competitive baseline. Mini Artichokes uses “five calls,” while Plain uses one and ordinary repair uses two; the paper itself says these are “effectiveness comparisons between nested one-, two-, and five-call systems.” Thus the large gains—“+48.9 percentage points” over Plain and “+15.6 points” over ordinary repair—do not establish efficiency or superiority at a fixed test-time budget.

- The central TOV mechanism is not convincingly established. The original semantic-free comparison is “review-triggered and post hoc,” while the two new replications produce means of only “+3.53 and +1.54 points” with intervals `[-2.35,+8.24]` and `[-6.92,+11.54]`. The Go replacement sensitivity is also only “33/39 versus 31/39 (`p=.3125`).” These results support TOV as a potentially useful branch, but not as a reliable causal improvement.

- Recursive promotion is partly a set-union construction whose benefit depends on paying for multiple routes. The paper acknowledges that “Dominance over an included route is purchased with another route.” The reported 210/300 versus 198/300 comparison therefore demonstrates the value of adding and verifying another route, but does not show that the semantic-overlap route itself is necessary or that the method is superior to other equally expensive route portfolios.

- The formal result is narrower than the system framing may suggest. It guarantees preservation only under assumptions including “no cross-task test dependency,” “isolated workspaces,” and a “stable verifier.” These assumptions are plausible for the benchmark but substantially constrain applicability, especially for repositories with shared build state, integration tests, nondeterminism, or interacting files.

- Statistical support is limited by correlated whole-track calls and a small number of clusters. The paper notes that “all task rows within one arm share one whole-track model call” and that “only three language clusters exist.” Consequently, the highly significant task-level tests substantially overstate the independent evidence available for generalization. The session replications help, but five sessions on each of two fixed tracks remain thin.

- The semantic ledger is not independently evaluated. The authors state that “ledger diagnoses were not independently annotated,” and the proposed interface-ambiguity explanation was “formulated after the nine discordant tasks were known.” It is therefore unclear whether the semantic fields provide genuine diagnostic information or merely induce a useful prompt/attention trajectory.

- The comparison does not establish robustness across models or runtimes. “All semantic calls use one model and runtime,” and the paper provides no model ablation, cross-model replication, or comparison against a modern independently implemented program-repair agent. This limits claims about universal or model-progress leverage.

- The benchmark setting is materially narrower than general program repair: it is explicitly “test-available,” exposes “bounded official failure output between calls,” and uses task-local units. The finite test suites also mean that byte-exact anchoring preserves “benchmark passes, not proof of correctness beyond those tests.”

## Questions for the Authors

1. At a matched five-call or matched-token budget, how does Mini Artichokes compare with a strong generic multi-sample-and-verify baseline that uses the same candidate calls and simply selects among all complete passing states?

2. Can you provide a preregistered replication on several unseen tracks or benchmarks in which the recursive route portfolio and analysis are frozen before any candidate or final-route outcomes are observed?

3. What fraction of Mini Artichokes’ gain over ordinary repair comes from candidate diversity, immutable anchoring, the direct route, TOV, and recursive union? A factorial ablation would clarify the contribution of each component.

4. Can independent annotators assess the correctness and usefulness of the four TOV ledger fields, and can you test whether those fields predict rescues prospectively rather than explaining them post hoc?

5. How does the method behave when tests are nondeterministic, task dependencies cross declared boundaries, or a repair requires coordinated changes across multiple task units?

## Scores

Soundness: 3/4 — The formal preservation claim is sound under clearly stated assumptions, but the causal and generalization evidence for the proposed semantic mechanism is limited.

Presentation: 4/4 — The paper is unusually transparent, well organized, and clear about chronology, controls, failures, and inferential boundaries.

Significance: 3/4 — Verified route union is practically relevant for test-available repair, although its scope and compute requirements are narrow.

Originality: 3/4 — The composition of immutable verified anchors, unresolved-set branching, and recursive promotion is useful, but several components are established ideas and the core union operation is conceptually simple.

Overall recommendation: 3/6 — Borderline: promising and carefully reported system evidence, but insufficiently strong causal, compute-matched, and cross-setting evidence for a clear ICML acceptance.

Confidence: 4/5 — The paper is self-contained and its argument is judgeable, though the empirical claims depend on reported experiments that cannot be independently rerun here.

## Ethics and Limitations

The paper uses public coding exercises and no human participants. It appropriately notes that failure output may reveal behavioral expectations and that the method increases inference compute. The main limitations are candidly stated: one model/runtime, correlated whole-track calls, only three language clusters in the primary study, post hoc control and recursive composition, finite test-suite validity, and restrictive task-local verifier assumptions. These limitations substantially constrain claims of universal program-repair improvement but do not invalidate the narrower test-available system result. No hidden reviewer-directed text is present.

## Comment

I find the preservation-and-promotion system promising, but recommend borderline rejection in its current form because the paper’s most novel causal story—semantic overlap as a useful repair mechanism—is not yet established, while the strongest gains are from additional calls and route union. The most important revision would be a genuinely compute-matched, preregistered factorial evaluation that separates the value of verified anchoring and multi-route union from the incremental value of TOV.

### Panel review 2 — experimentalist (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper proposes Mini Artichokes, a test-verified multi-route program-repair system that freezes complete passing task states as byte-exact anchors, repairs only common failures, and recursively promotes passing outputs from heterogeneous final routes. On three complete Aider Polyglot tracks it reaches 59/90 versus 45/90 for ordinary execution-feedback repair and 15/90 for Plain. A before-call-frozen Go evaluation reaches 33/39. The paper is unusually candid that the stronger system-level result is not evidence of compute efficiency or semantic-overlap causality; however, the causal evidence for TOV itself is mixed and the system comparison leaves important alternative explanations insufficiently controlled.

## Strengths

- The central preservation mechanism is clearly specified and supported by a concrete invariant: “a complete verified task state is removed from model discretion, only unresolved units are branched,” while “passing states from heterogeneous routes are recursively promoted.” The assumptions A1–A5 make the stated test-label preservation property precise.

- The evaluation retains complete tracks rather than cherry-picking tasks: “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” followed by a complete Go39 evaluation. The paper reports denominators, per-track results, and negative/ceiling cases.

- The system-level results are substantial within this benchmark. Table 1 reports “Mini Artichokes solves 59/90 (65.6%), compared with ... 45/90 (50.0%) for ordinary repair,” and Table 4 reports “33/39” on Go versus “25” for ordinary repair.

- The authors distinguish nested effectiveness comparisons from causal component claims. For example, they explicitly state that the Plain and ordinary-repair comparisons are “nested, additional-compute comparisons,” and that Go “establish[es] end-to-end value, not an overlap-only effect.”

- The paper includes meaningful ablations and failure accounting. The stricter control yields “eight rescues and one harm,” while the original TOV-versus-control contrast is reported with exact tests and intervals. The authors also retain the Rust `fizzy` harm caused by “an extra closing brace,” rather than presenting semantic diagnosis as sufficient.

- The replication design is stronger than a single benchmark run. Five paired sessions on each Python34 and C++26 track show both gains and reversals, including “`+4,-2,+2,0,+2`” and “`+1,-1,0,+5,-3`,” exposing trajectory variance rather than hiding it.

- Presentation is generally rigorous and appropriately cautious. Statements such as “semantic overlap is a productive conditional route, not a universal or 20-point causal gate” accurately reflect the reported evidence.

## Weaknesses

- The main performance advantage is not cleanly attributable to recursive verified redundancy. Mini Artichokes uses five calls, compared with two for ordinary repair and one for Plain. Even its equal-call comparison is post hoc: “recursive composition was chosen after observing crossovers.” The 59/90 versus 54/90 result therefore demonstrates that this particular pair of routes can be unioned successfully, but not that the proposed mechanism would outperform a pre-specified five-call alternative.

- The strongest TOV comparison is compromised by timing and multiplicity. “The semantic-free structured control was frozen only after all TOV outcomes and the MAC v9 critique were known,” and the paper calls the contrast “secondary.” The observed original advantage is significant at the task level, but the five-session replications have intervals crossing zero: Python `[−2.35,+8.24]` and C++ `[−6.92,+11.54]` percentage points. Thus the paper does not establish a reliable causal benefit from semantic relations.

- The supposedly matched TOV and semantic-free controls are not computationally matched. Table 6 shows TOV using 59,551 output tokens and 1,422.3 seconds, versus 54,728 tokens and 1,392.7 seconds for the semantic-free control. The paper acknowledges this, but the additional output and latency could contribute to the observed difference.

- The baseline suite is incomplete for the central systems claim. The relevant equal-call comparator is “Non-overlap dual-route union,” but it uses a generic Critic plus direct repair, whereas Mini Artichokes uses TOV plus direct repair. There is no prospective comparison against multiple generic final routes, repeated direct sampling, or a call-matched route union selected before observing crossovers. Consequently, the evidence does not isolate recursive promotion from simply adding a second heterogeneous repair attempt.

- The statistical treatment is appropriately caveated but still weak for generalization. The original task-level tests condition on “one whole-track model call,” and only three language clusters exist. The cluster checks are explicitly underpowered (`p=.125` and `p=.5`), while the repeated-session evidence contains only five sessions per track. The paper supports effectiveness on these realized workloads more strongly than population-level superiority.

- The semantic-overlap analysis is partly post hoc and lacks independent measurement validity. The paper states that the “interface-ambiguity account was formulated after the nine discordant tasks were known” and that “ledger diagnoses were not independently annotated.” This makes the proposed behavioral fields difficult to distinguish from a useful prompt style or additional model attention.

- The benchmark setting limits practical scope. The method assumes “a trusted external verifier,” task-local solution files, isolated workspaces, and informative failure output. It also preserves only “benchmark passes, not proof of correctness beyond those tests.” These are reasonable boundaries, but they substantially narrow what the results establish about general program repair.

## Questions for the Authors

1. Can you provide a pre-specified, call-matched comparison against multiple generic final routes or repeated direct repairs, with the route count and union rule fixed before seeing crossover outcomes?

2. How much of the TOV advantage remains after matching total input/output tokens and wall-clock budget, rather than only matching nominal call count?

3. Can you run the recursive promotion rule with randomly selected or pre-registered route pairs to separate the benefit of verifier-backed union from the particular TOV/direct pairing?

4. What are the per-task results and confidence intervals for the verified floor, TOV, direct route, and recursive union across independent seeds or model sessions on Go and additional tracks?

5. Can independent annotators evaluate the four TOV ledger fields and falsification steps, and do ledger quality measures predict rescues without using outcome information?

6. How does Mini Artichokes compare with simple best-of-N execution-verified sampling using the same five-call budget and the same task-level anchoring?

## Scores

Soundness: 3/4 — The system rule and benchmark measurements are coherent, but causal attribution and compute-matched comparisons remain incomplete.

Presentation: 4/4 — The paper is unusually transparent, well organized, and clear about exploratory versus confirmatory evidence.

Significance: 3/4 — Verified preservation and route union are practically relevant, but the demonstrated setting is narrow and the incremental algorithmic contribution is modest.

Originality: 3/4 — The composition of immutable verified anchors with heterogeneous repair routes is a useful systems formulation, though its components and much of its advantage resemble best-of-multiple verified attempts.

Overall recommendation: 3/6 — Borderline; promising empirical systems work, but the central causal and generalization claims are not yet established strongly enough for acceptance.

Confidence: 4/5 — The paper provides sufficient internal detail to judge its logic and evidence, though the underlying artifacts and runs cannot be independently checked here.

## Ethics and Limitations

The paper uses public code-repair tasks and no human participants. It appropriately notes that failure output can reveal behavioral expectations and that finite official suites do not establish semantic correctness. The principal limitations are substantial: one model and runtime, correlated same-model candidates, few language clusters, post hoc recursive composition, non-token-matched final calls, and a transport-null primary Generic call on Go. These are disclosed candidly and should reduce, but do not eliminate, concern about the strength of the conclusions.

## Comment

I recommend borderline. The byte-exact anchoring and recursive promotion rule are clearly specified and the end-to-end gains are credible on the reported tracks, but the paper currently establishes a successful five-call verified route union more convincingly than it establishes a general advantage from recursive redundancy or semantic overlap. The most important revision is a prospective, compute-matched comparison against equally budgeted generic multi-route or repeated-sampling systems, with the route pairing and promotion analysis fixed before outcomes are observed.

### Panel review 3 — scope_ablation (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper proposes Mini Artichokes, a five-call program-repair system that preserves complete task states passing an external test suite, restricts later editing to common failures, and recursively unions passing outputs from heterogeneous repair routes. Its strongest evidence is end-to-end effectiveness on four complete Aider Polyglot tracks: 92/129 tasks, compared with 70/129 for ordinary execution-feedback repair and 32/129 for Plain. The narrower claim that semantic-overlap reasoning itself is causally beneficial is substantially less established.

## Strengths

- The paper identifies a clear and useful systems principle: “a complete verified task state is removed from model discretion,” with promotion copying “the complete allowlisted solution-file tuple” rather than merging edits. Under assumptions A1–A5, the stated test-label preservation property follows mechanically.

- The evaluation retains complete tracks rather than cherry-picking tasks: “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” followed by “all 39 official Go tasks.” This supports credible within-benchmark coverage claims.

- The end-to-end gains are large and consistently reported. Mini Artichokes achieves “59/90 (65.6%)” versus “45/90 (50.0%) for ordinary repair,” and on Go achieves “33/39,” versus “25/39 for ordinary repair.”

- The paper is unusually candid about inferential limits. It explicitly states that the 90-task evidence is “not a single preregistered trial,” that recursive composition “was chosen after the later crossovers,” and that Go’s primary Generic comparison “fails its integrity-promotion gate.”

- The authors provide meaningful negative and boundary evidence: the strict Java gate “solved 5/20 versus 7/20,” while QuixBugs reached “Plain passed 40/40, leaving no room for rescues.” These results help prevent overclaiming universality.

- The route-combination mechanism is empirically plausible. On repeated sessions, recursive union reaches “210/300 repeated task-session passes, versus 198 for TOV alone,” illustrating how verified route complementarity can provide robustness even when individual routes are unstable.

## Weaknesses

- The central system comparison is not compute-matched. Mini Artichokes uses five calls and includes two final routes, whereas Plain and ordinary repair use fewer calls. The paper acknowledges that these are “nested, additional-compute comparisons,” but the headline gains therefore establish an effectiveness/compute tradeoff rather than an algorithmic advantage at a fixed budget.

- The causal evidence for TOV’s semantic-overlap component is weak and partly post hoc. The semantic-free control “was frozen only after all TOV outcomes and the MAC v9 critique were known,” and the recursive rule was “specified only after these repetitions revealed large branch crossovers.” The original 7-task advantage is therefore vulnerable to selection and design adaptation.

- The prospective evidence does not reliably show that TOV is superior to its controls. In the two five-session replications, the intervals are `[-2.35,+8.24]` and `[-6.92,+11.54]` percentage points, and the Go replacement sensitivity is only “33/39 versus 31/39 (`p=.3125`).” The paper appropriately retreats to calling TOV “a productive heterogeneous branch,” but this makes the semantic contribution substantially less conclusive.

- The experimental scope is narrow: one model/runtime, four programming languages from one benchmark, and test-available repair with bounded failure traces. The authors state that “only three language clusters exist” and that the setting “is not a standard one-shot leaderboard protocol.” Claims about universal answer-engine relevance or broad program repair should consequently be restrained.

- The semantic-free ablation is not a clean mechanistic intervention. The paper admits it “matches named instructions, not latent reasoning or exact realized compute,” and the crossed replications show that “trajectory variation is material.” Thus the difference cannot be attributed uniquely to semantic relations rather than prompt-induced reasoning changes or output-budget differences.

- The preservation theorem depends on substantial operational assumptions—“task-local declared files, no cross-task test dependency, isolated workspaces, and a stable verifier.” These assumptions are reasonable for this benchmark, but the paper does not demonstrate how often they hold in realistic repositories or how performance changes when task boundaries are not clean.

- The Go evaluation is informative but not a clean confirmation of the claimed component mechanism. The preregistered Generic call was transport-null, while the replacement was run “only after TOV outcomes were known.” The resulting 33/39 system score is useful evidence for the recursive system, but cannot substitute for the intended prospective equal-call comparison.

## Questions for the Authors

1. Can you provide a compute-matched comparison in which Plain or ordinary repair receives the same total model-token and latency budget as Mini Artichokes, while preserving the one-call-per-track constraint?

2. What is the performance of recursive verified redundancy using two generic independently prompted final routes, with no TOV semantic-overlap instruction? This would separate the value of recursive route diversity from the value of TOV specifically.

3. Can you preregister and run a larger, multi-track replication with the recursive rule and semantic-free control fixed before observing any outcomes, including a valid prospective comparator?

4. How sensitive are the results to the anchor unit? In particular, do file-level or repository-level dependencies cause promotion to fail or create regressions on benchmarks beyond Aider Polyglot?

5. Can independent annotators label the TOV ledger fields and test whether ledger correctness predicts rescues, rather than only analyzing the task outcomes after the fact?

## Scores

Soundness: 3/4 — The preservation mechanism is well specified and the system evidence is carefully caveated, but causal attribution and prospective controls are limited.

Presentation: 4/4 — The paper is unusually clear about protocol chronology, denominators, statistical units, and limitations.

Significance: 3/4 — Verified preservation and route union are practically relevant, though the demonstrated setting is narrow and compute-intensive.

Originality: 3/4 — The composition of immutable verified anchors with recursive route promotion is a plausible original systems contribution, while its components draw on established ideas.

Overall recommendation: 3/6 — Borderline; the system result is promising, but stronger compute-matched and prospective evidence is needed for acceptance.

Confidence: 4/5 — The paper is self-contained and reports enough detail for a substantive assessment, although the underlying artifacts and experiments cannot be independently rerun here.

## Ethics and Limitations

The paper uses public coding tasks and reports no human participants. It appropriately notes that failure output may reveal behavioral expectations and frames the setting as “test-available program repair.” The main limitations are one model/runtime, one benchmark family, correlated whole-track calls, finite test specifications, additional inference cost, post hoc development choices, and a semantic-free control that does not isolate latent reasoning. The paper also correctly acknowledges that byte-exact anchors preserve benchmark passes rather than correctness beyond the supplied tests.

## Comment

I lean borderline because the recursive verified-union system is a coherent and potentially useful contribution, with strong end-to-end gains and unusually honest reporting. The most important issue is to establish whether the claimed advantage survives a genuinely prospective, compute-matched comparison—especially against generic multi-route redundancy—rather than relying primarily on nested additional-call gains and post hoc route composition.
