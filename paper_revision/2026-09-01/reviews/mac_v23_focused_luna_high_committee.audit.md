# ICML-Style Paper Review

## Paper and Evidence Identity

- Review method: full review — deterministic evidence audit + review panel. The panel's review is the official output; this document is its audit sidecar.
- Review Agent name/version: paper-reviewer / `sha256:9886349f92661c3c73b70f216a7038b741b47282d7624538ad207dd3fbb2d4c0`
- Review-agent spec path/hash: `review-agent-spec.md` / `sha256:08b13516a2cb0e5151c6b4dc24f98e6d191b35ee30d69ea300b2d6ff2d5a5945`
- Original paper identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:f138d5452cad925fe197752cf9637b1dc23b986123ae52c62ef1ecbaadc96fc6` / `59541` bytes
- Derived Markdown identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:f138d5452cad925fe197752cf9637b1dc23b986123ae52c62ef1ecbaadc96fc6` / `59541` bytes
- Original PDF page count: `n/a`
- Converter: `none (Markdown source)`
- Paper version/hash: `Mini_Artichokes_manuscript_v4.md` / `sha256:f138d5452cad925fe197752cf9637b1dc23b986123ae52c62ef1ecbaadc96fc6`
- Evidence bundle reviewed: none (no evidence bundle supplied)
- Frozen at (UTC): `2026-09-04T17:53:34+00:00`

## Summary

The paper, "Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair", presents a method and supporting experiments. It reports 160 quantitative result claim(s) and cites 13 prior work(s). Deterministic audit: 0 contradiction(s), 0 dishonest self-certification(s), 0 mechanical finding(s); 0 result claim(s) evidence-backed, 885 unverifiable. Overall recommendation: 3/6 [claim-001].

## Strengths

- The paper situates its contribution against prior work (13 citation(s); related-work section present).

## Weaknesses

- The deterministic audit proved no contradiction, arithmetic error, or integrity breach; the remaining concern is limited to claims that could not be independently verified (see Questions).

## Questions for the Authors

1. For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?
2. 160 extracted result/arithmetic claim(s) could not be checked against the supplied evidence and are listed with their source lines in the Evidence Trace — could the authors provide the underlying results?

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
- Frozen review identity: `sha256:9838d87724c0fc70efc1c6384b3070200caac5e0fc7ea3b6bce7bcac2c343ba8`.
- Verdict labels digest: `sha256:f868e161476b588a1bc284a21ad9bd28bebcfddf3a1456d3b29fe0e5e4bfb3b4`.
- External citation snapshot digest: `sha256:01545e382bf7b0636dcadf97adfec0e438018ba58ffefc7b6167718586eab0a7`.
- Scientific judgment identity: `sha256:9f10ce39f5505d698b169ceec9c23c4c65b6c6726dce2775e3216df02569b5ea`.
- Review panel configuration: panel=3, model=`gpt-5.6-luna`, synthesis=area-chair.
- Panel reviewer `theorist`: prompt=`sha256:fe61c90c394fc1db270cec6c7e498a9fe6346b89b6c217474ed415a0fe3f1493`, response=`sha256:c39a1d4362f5c9a84f8087eda2c3ac1ac79a652ff6b1992cf1994d45ca0889b9`, status=ok.
- Panel reviewer `experimentalist`: prompt=`sha256:996a27145d0f5ad1e0921db9419a7499cb59c5a46358e2f1aef95372d8dc72cd`, response=`sha256:6768ec6c7198db03e238b53f1e281fdc20227bce96059997e6aeb4d75459b55a`, status=ok.
- Panel reviewer `scope_ablation`: prompt=`sha256:eb9e3a2d253b1a293473653fb0fbcdf4fb9635bc370d5d2aba181c23ca9565a5`, response=`sha256:1b3a501bac9c7263b7763f7820ef0cdfd357bc557b0985c2f1ae0cd0e3e6ce80`, status=ok.
- Output path: `mac_v23_focused_luna_high_committee.md`.
- Frozen paper input: `Mini_Artichokes_manuscript_v4.md` (`sha256:f138d5452cad925fe197752cf9637b1dc23b986123ae52c62ef1ecbaadc96fc6`).
- Frozen original identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:f138d5452cad925fe197752cf9637b1dc23b986123ae52c62ef1ecbaadc96fc6`, 59541 bytes, page count=n/a).
- Frozen derived identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:f138d5452cad925fe197752cf9637b1dc23b986123ae52c62ef1ecbaadc96fc6`, 59541 bytes).
- Frozen converter: `none (Markdown source)`.
- Pre-S1 sanitation: 0 trace(s), 0 injection finding(s).
- S1 parse inventory: 40 sections, 10 tables, 736 numeric tokens with source locations.
- S3 ledger-trace: 0/0 metric-labelled values matched; 0 finding(s).
- S3 internal-consistency: 0 comparison(s), 0 finding(s).
- S3 arithmetic: 0 recomputation(s), 0 finding(s).
- S3 baseline-fairness: 0 explicit improvement claim(s), 0 finding(s).
- S3 negative-evidence: 0 discard/crash outcome(s), 0 omission finding(s).
- S3 citation-existence: 2 explicit identifier(s), 0 existence/title finding(s).
- S3 template-compliance: 1 contract trace(s), 0 finding(s).
- S3 injection-scan: 0 sanitation trace(s), 0 reviewer-directed instruction finding(s).
- S3 self-review-audit: 0 checklist item(s), 0 dishonest self-certification(s).
- S3 positioning: 13 cited reference(s), related-work section=True, 0 novelty/superiority claim(s), 0 overclaim finding(s), 0 positioning question(s).
- S5 DRAFT/GROUND: 160 candidate comment(s), 160 retained, 0 deleted, 160 criticism comment(s) converted to questions.
- S2/S4 claim verdicts:
- [claim-016] **unverifiable** — paper:18 — The equal-call result — No implemented mechanical check proves or disproves this claim. Evidence: `paper:18`.
- [claim-021] **unverifiable** — paper:22 — JavaScript49 track, both five-call systems reach 47/49, while Mini exceeds — No implemented mechanical check proves or disproves this claim. Evidence: `paper:22`.
- [claim-024] **unverifiable** — paper:24 — tasks, Mini improves on Plain (157/164) and reaches the same ceiling as ordinary — No implemented mechanical check proves or disproves this claim. Evidence: `paper:24`.
- [claim-031] **unverifiable** — paper:32 — A one-task Java completion-lock result also does not repeat in five — No implemented mechanical check proves or disproves this claim. Evidence: `paper:32`.
- [claim-041] **unverifiable** — paper:45 — can improve over one-pass generation, yet their composition is fragile. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:45`.
- [claim-051] **unverifiable** — paper:55 — hypotheses improve one final repair route. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:55`.
- [claim-056] **unverifiable** — paper:60 — **semantic-relation value:** whether comparing what failed candidates mean — No implemented mechanical check proves or disproves this claim. Evidence: `paper:60`.
- [claim-057] **unverifiable** — paper:61 — improves repair beyond a final agent with the same candidates, evidence, — No implemented mechanical check proves or disproves this claim. Evidence: `paper:61`.
- [claim-086] **unverifiable** — paper:91 — **RQ1:** Does recursive verified redundancy improve Plain, Graph, and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:91`.
- [claim-103] **unverifiable** — paper:112 — prospective complete-track and repeated-session analyses that establish the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:112`.
- [claim-109] **unverifiable** — paper:122 — End-to-end five-call effectiveness | 59/90 original; frozen Go 33/39; frozen JavaScript 47/49; complete HumanEvalFix extensions | Supported in the reported test-available setting — No implemented mechanical check proves or disproves this claim. Evidence: `paper:122`.
- [claim-110] **unverifiable** — paper:123 — Advantage over a same-call generic portfolio | Mixed-stage Aider 139/178 vs 132/178; clean JavaScript tie; complete-suite robustness checks | Positive descriptive evidence; not established prospectively across sessions — No implemented mechanical check proves or disproves this claim. Evidence: `paper:123`.
- [claim-111] **unverifiable** — paper:124 — Standalone semantic-relation effect | Original 10-versus-3 matched-control result plus newly frozen paired sessions | Productive heterogeneous route; stable superiority not established — No implemented mechanical check proves or disproves this claim. Evidence: `paper:124`.
- [claim-139] **unverifiable** — paper:160 — an indivisible task it reduces to ordinary verifier-selected best-of-multiple. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:160`.
- [claim-186] **unverifiable** — paper:217 — priority affects provenance, not the observed pass label. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:217`.
- [claim-190] **unverifiable** — paper:224 — After its model call, the experiment — No implemented mechanical check proves or disproves this claim. Evidence: `paper:224`.
- [claim-202] **unverifiable** — paper:243 — The semantic comparison is behavioral. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:243`.
- [claim-215] **unverifiable** — paper:255 — The revised final gate therefore enumerates every observed compiler, — No implemented mechanical check proves or disproves this claim. Evidence: `paper:255`.
- [claim-254] **unverifiable** — paper:293 — `/tmp/artifacts/decision_ledger.json` with exactly one record for each frozen — No implemented mechanical check proves or disproves this claim. Evidence: `paper:293`.
- [claim-260] **unverifiable** — paper:297 — They do not score the natural-language diagnoses for — No implemented mechanical check proves or disproves this claim. Evidence: `paper:297`.
- [claim-280] **unverifiable** — paper:318 — verification preserves every observed pass from either included route on the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:318`.
- [claim-282] **unverifiable** — paper:320 — The construction was formulated after final-route crossovers were observed and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:320`.
- [claim-292] **unverifiable** — paper:329 — recursive promotion--rather than a score gain over an offline union of the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:329`.
- [claim-307] **unverifiable** — paper:345 — tasks observed passing in included route `k`, and let `A` be the prior anchor — No implemented mechanical check proves or disproves this claim. Evidence: `paper:345`.
- [claim-311] **unverifiable** — paper:349 — complete state already observed to pass; no unverified merged state is — No implemented mechanical check proves or disproves this claim. Evidence: `paper:349`.
- [claim-312] **unverifiable** — paper:350 — Hence its observed task score is at least that of the prior anchor set — No implemented mechanical check proves or disproves this claim. Evidence: `paper:350`.
- [claim-328] **unverifiable** — paper:375 — We report both the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:375`.
- [claim-343] **unverifiable** — paper:393 — `counter` task reports `no tests to run`; it is retained in the denominator — No implemented mechanical check proves or disproves this claim. Evidence: `paper:393`.
- [claim-350] **unverifiable** — paper:400 — path; it occurred before any scored call, was invalidated, and the corrected — No implemented mechanical check proves or disproves this claim. Evidence: `paper:400`.
- [claim-381] **unverifiable** — paper:436 — Plain | 1 | Direct complete-track solve — No implemented mechanical check proves or disproves this claim. Evidence: `paper:436`.
- (+855 further extracted claim(s) — mostly unverifiable prose — omitted here for brevity; all are labelled in S2/S4 with source lines.)

## Comment

Recommendation: 3/6. No headline result is mechanically supported yet, so the recommendation stays borderline pending stronger evidence. Most useful next step for the authors — For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?

## Panel Reviews (provenance)

### Panel review 1 — theorist (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

The paper presents Mini Artichokes, a five-call program-repair system that freezes task-level passing solutions, repairs only unresolved tasks, and recursively unions verified successes from direct and semantic-overlap routes. It reports strong gains over Plain and ordinary repair, but the central semantic-overlap and equal-call superiority claims remain exploratory because the clean prospective comparison is tied and most aggregate evidence is mixed-stage.

## Strengths

- The core preservation mechanism is clearly specified and formally scoped: under A1–A5, “the recursively promoted output passes every task in `A union (union_k S_k)`,” while explicitly disclaiming “semantic correctness, verifier completeness, or reliability under nondeterministic tests.”
- The paper distinguishes system effectiveness from component causality. It states that “the best-supported object is Mini Artichokes as a five-call effectiveness system, not semantic overlap as an isolated causal treatment.”
- The empirical evaluation retains complete task inventories. Table 5 evaluates all 49 JavaScript tasks, where Mini reaches 47/49, and Table 6 evaluates all 164 HumanEvalFixDocs Python tasks, where Mini reaches 164/164.
- The byte-exact anchoring and fail-closed design are concrete and auditable: “A missing file, forbidden-path change, verifier error, or non-pass fails closed,” and the paper reports that “all 126 route-by-anchor byte checks passed” on JavaScript.
- The authors are unusually candid about negative evidence and scope. They report that the Java completion-lock rescue “does not repeat in five new whole-track pairs” and conclude that semantic relations are “not a reliably superior standalone policy.”

## Weaknesses

- The principal causal claim is not established prospectively. The clean before-call-frozen JavaScript comparison gives Mini and Direct∪Generic exactly 47/49, with “0 rescues, 0 harms, `p=1`,” while the headline 139/178 versus 132/178 result is explicitly “mixed-stage” and has a five-track sign value of only `p=.125`. Thus the evidence supports a useful bounded portfolio, but not a repeatable advantage over a same-call generic portfolio.
- The formal preservation result is largely an algebraic consequence of task-wise best-of-promotion under strong assumptions, rather than a new algorithmic guarantee. The paper itself states that “a minimal task-wise verifier union is algebraically identical to this promotion rule” and that it claims “no new selector beyond that max operation.” The remaining novelty is the composition and execution protocol, which requires stronger evidence to establish scientific significance.
- Applicability is narrow and potentially mismatched with general program repair. The theorem assumes that “the benchmark is partitioned into task units whose declared solution files and verifier do not cross task boundaries,” yet the paper acknowledges that “shared files, cross-task build state, flaky tests, or unavailable tests require a coarser unit or a different method.” No substantial evaluation tests violations of this modularity contract.
- The comparison is confounded by chronology and realized compute. The Go Generic arm is a “separately frozen same-input replacement after TOV outcomes were known,” and the paper concedes that the systems are “call-matched but not token-matched.” Consequently, the equal-call comparison does not isolate semantic guidance or equal computational effort.
- The statistical evidence is appropriately described as conditional, but remains weak for broad claims. “All task rows within one arm share one whole-track model call,” and task-level tests therefore condition on realized calls. The study also evaluates many routes, tracks, ablations, and endpoints without presenting a multiplicity strategy, so nominal exact p-values should not be interpreted as confirmatory evidence.
- Generalization is limited by using “one model and runtime.” The repeated studies cover only Python34 and C++26 sessions, while Java and HumanEvalFix include runtime deviations; this is insufficient to establish robustness across models, runtimes, languages, or benchmark families.

## Questions for the Authors

1. Will the authors run a new, before-call-frozen, token-matched comparison between Mini and Direct∪Generic on several complete tracks, with the route definitions and primary endpoint fixed in advance?
2. Can the authors provide a factorial ablation that separates the effects of candidate diversity, immutable anchoring, recursive union, semantic relations, and completion locking?
3. How does the preservation theorem change when tasks share files, build state, dependencies, or cross-task tests, and can the system detect invalid task modularity automatically?
4. Can the released artifact include a public URL, complete per-task vectors, exact prompts, all transport failures, and enough evaluator information to independently reproduce the headline comparisons?
5. How should the reported p-values be adjusted or interpreted given the number of exploratory contrasts and the post hoc introduction of some controls and route comparisons?

## Scores

Soundness: 3/4 — The mechanism and limitations are carefully specified, but causal attribution and prospective same-call evidence remain insufficient.

Presentation: 3/4 — The paper is unusually transparent and well organized, though the many evidence stages and overlapping claims make the central result difficult to isolate.

Significance: 3/4 — Verified task-state preservation is practically useful, but its applicability and advantage over simpler verifier unions are not yet broad or decisively demonstrated.

Originality: 3/4 — The composition of immutable anchors, unresolved-only repair, and recursive promotion is a plausible systems contribution, although the formal core reduces to task-wise verifier union.

Overall recommendation: 3/6 — Borderline; promising engineering and empirical evidence, but the main comparative claim is not prospectively established.

Confidence: 3/5 — The paper provides substantial internal detail, but the decisive results depend on unreproduced runs, mixed chronology, and artifact/supplement evidence not available here.

## Ethics and Limitations

The use of public programming tasks and no human participants presents limited direct ethical risk. The paper appropriately notes that failure output may reveal behavioral expectations and that the method increases inference compute. Its stated limitations—including finite-test correctness, correlated errors from one model, task-level dependence within whole-track calls, runtime deviations, and the inability of the semantic-free control to equalize latent trajectories—are substantial and should materially constrain the claims.

## Comment

I recommend borderline rejection in the current form. The most important issue is not the preservation construction, which is clear, but whether Mini Artichokes provides a reproducible advantage over a same-call generic verified portfolio. A prospective, token-matched, multi-track evaluation with pre-specified controls and a clean decomposition of anchoring versus semantic guidance would substantially change my assessment.

### Panel review 2 — experimentalist (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper proposes a verifier-gated, task-wise union of multiple LLM repair attempts, with an overlap-aware repair route and recursive promotion of passing task states. The core result is promising in the reported test-available setting: Mini Artichokes solves “59/90” original Aider tasks and “139/178” across five Aider tracks, compared with 54/90 and 132/178 for the corresponding five-call generic portfolio. However, the strongest same-call comparison is mixed-stage and the only clean prospective JavaScript comparison is a tie, so the evidence supports bounded system effectiveness more strongly than a causal claim about semantic overlap or a general superiority claim.

## Strengths

- The paper identifies a clear and practically important failure mode in iterative repair: replacing an already verified solution. The proposed mechanism is concrete: “a complete verified task state is removed from model discretion” and “only unresolved units are branched.”

- The preservation claim is well formalized under explicit assumptions. Under A1–A5, the paper states that recursive promotion yields “`V_rec(t)=max(V_F(t),V_D(t))`,” which makes the claimed test-label preservation mechanically understandable rather than dependent on an LLM selector.

- The evaluation retains complete benchmark inventories. Table 1 reports all 90 original Aider tasks, while Table 4 reports “all 178 official tasks retained.” This is substantially stronger than selecting difficult or favorable subsets.

- The paper is unusually candid about evidential boundaries. It explicitly says that the 139/178 versus 132/178 result is “a mixed-stage descriptive summary,” that JavaScript is “a tie,” and that semantic overlap is “not established” as a stable standalone advantage.

- The failure analyses are useful and connected to design changes. For example, the paper reports that an earlier rule solved “5/20 tasks versus 7/20,” and that manual patch transfer “lost a Plain-passed task,” motivating the current agreement-as-hypothesis and byte-exact anchoring design.

## Weaknesses

- The central equal-call superiority claim is not established prospectively. The headline comparison is “139/178” versus “132/178,” but the paper acknowledges that the original tracks are post hoc, Go uses a replacement after the original invocation failed, and “JavaScript is the only clean prospective equal-call track and is a tie.” Thus the strongest evidence does not isolate a reproducible advantage over the generic five-call portfolio.

- The semantic-overlap contribution is confounded by a weak causal control. The semantic-free control “cannot equalize latent trajectories or realized compute,” and the TOV route uses different prompt requirements, ledger production, and output behavior. Table 7 shows TOV taking 1,422.3 seconds versus 1,392.7 seconds for the semantic-free structured control and producing 59,551 versus 54,728 output tokens. The seven-task original advantage therefore cannot be attributed cleanly to semantic relations.

- The repeated-session evidence is still too narrow to support broad stability claims. The ten sessions cover only Python34 and C++26, and the paper reports mean differences of “+1.2/34” and “+0.4/26,” with intervals including both help and harm. The significant union comparison is structurally guaranteed once route-specific successes are retained and losses are prevented; it demonstrates the value of unioning observed routes, but not that TOV is generally better than alternatives.

- The statistical interpretation remains limited by whole-track calls. “All task rows within one arm share one whole-track model call,” so the task-level p-values condition on a small number of realized model trajectories and are not independent-task or population-level evidence. The paper recognizes this limitation, but the large task-level significance values should not carry the weight of conventional benchmark replication.

- The empirical setting is narrow: one model/runtime, test-available repair, and mostly related code-repair benchmarks. The paper itself states that “all semantic calls use one model and runtime” and that the method is inappropriate “when tests are unavailable or too weak.” This limits claims about a universal answer or repair engine.

- Reproducibility is asserted more than demonstrated in the manuscript. The paper says that the artifact contains “complete task IDs, ... candidate and final patches, ... ledgers, anchor maps, and paired reports,” but the submitted text does not provide the artifact location or enough per-task vectors to independently audit the headline comparisons.

## Questions for the Authors

1. Can you run the complete five-call Mini-versus-Direct∪Generic comparison on several untouched benchmark tracks with both policies frozen before any model calls, and with matched realized token/time budgets?

2. How much of the original TOV advantage remains when the semantic-free control is matched for output budget, prompt length, and execution time rather than only nominal calls?

3. Can you provide the complete per-task outcome vectors and public artifact URL needed to verify the 8:1 discordance, the five unique rescues, and the 210/300 repeated-session union result?

4. What happens when task solution files or build state are genuinely shared across tasks, violating A1, and how does the system detect that the task-wise promotion contract is invalid?

5. Can the authors separate the gain from recursive union itself from the gain attributable to the particular TOV route, for example by evaluating multiple independently frozen generic and overlap-aware routes under the same candidate floor?

## Scores

Soundness: 3/4 — The preservation construction is clear and the reported experiments are carefully qualified, but the main comparative and semantic-causal claims remain confounded and only partly prospective.

Presentation: 4/4 — The paper is unusually explicit about chronology, controls, assumptions, deviations, and claim scope, despite substantial technical density.

Significance: 3/4 — Verifier-gated preservation and recursive task-wise promotion are useful systems ideas for test-available repair, but the practical scope and superiority over matched alternatives are not yet established.

Originality: 3/4 — The composition of immutable verified anchors, unresolved-only repair, and recursive heterogeneous promotion is a meaningful systems contribution, although its components draw on established ensemble, verification, reflection, and structured-reasoning ideas.

Overall recommendation: 3/6 — Borderline; promising mechanism and strong bounded-setting evidence, but insufficient prospective and compute-matched evidence for the main superiority claims.

Confidence: 3/5 — The argument and reported numbers are internally judgeable, but the decisive empirical artifacts and independent reproducibility evidence are not available here.

## Ethics and Limitations

The work uses public code exercises and reports “no human participants.” It appropriately notes that failure output may reveal behavioral expectations and therefore characterizes the setting as “test-available program repair.” The main limitations are substantial but honestly stated: finite and potentially weak tests, correlated errors from one model/runtime, whole-track calls, limited session replication, non-equalized latent trajectories and compute, and possible benchmark contamination for QuixBugs. The increased inference cost is also material: the authors explicitly describe Mini as “an effectiveness system, not an efficiency result.” No hidden reviewer-directed text is reported.

## Comment

I recommend borderline acceptance. The verifier-only promotion rule is well motivated, formally clear, and potentially useful, and the complete-track results show meaningful bounded-call effectiveness. The most important issue is causal and prospective validation: the authors should establish the Mini-versus-generic advantage across multiple before-call-frozen tracks under matched realized compute, while separately isolating whether semantic overlap—not merely an additional structured repair trajectory and recursive union—is responsible for the gain.

### Panel review 3 — scope_ablation (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

The paper proposes a verifier-gated composition of multiple whole-track code-repair attempts. Passing task states become immutable anchors, unresolved tasks are repaired by heterogeneous routes, and passing outputs are recursively unioned. The evidence supports a useful bounded-call repair system: Mini Artichokes reaches “59/90” on the original Aider tracks and “33/39” on Go, but the stronger causal claim about semantic overlap is limited by post-hoc design, trajectory dependence, and a clean prospective tie.

## Strengths

- The preservation mechanism is clearly specified and has a genuine structural guarantee. Under A1–A5, “no unverified merged state is created,” and the paper correctly distinguishes test-label preservation from semantic correctness.

- The evaluation retains complete task inventories rather than selecting convenient examples. The paper states that “No task is ranked, screened, removed, replaced, or topped up,” including all 30 Rust, 34 Python, 26 C++, 39 Go, and 49 JavaScript tasks.

- The system-level results are substantial relative to weak baselines. Mini solves “59/90 (65.6%)” versus “15/90 (16.7%)” for Plain and “45/90 (50.0%)” for ordinary repair, with “14 and loses none” relative to ordinary repair.

- The authors are unusually candid about claim boundaries. They explicitly state that the equal-call result is “a post-hoc equal-call system contrast, not confirmatory mechanism evidence” and that semantic overlap is “not a universally superior final policy.”

- The paper includes meaningful robustness and failure analyses. For example, “five new predeclared whole-track pairs did not repeat” the Java rescue, and HumanEvalFix Python reaches a documented ceiling where “ordinary repair also reaches 164/164.”

- The verifier and artifact integrity procedures are concrete. The paper reports “zero multiply owned declared solution paths,” exact ledger counts, byte comparisons, rerun hashes, and fail-closed behavior for forbidden changes or verifier errors.

## Weaknesses

- The central same-call superiority claim is not prospectively established. The five-track aggregate is explicitly “mixed-stage,” Go uses a replacement after the original transport failure, and the only clean prospective JavaScript comparison is an exact tie: “both Generic and TOV solved the same 47/49 tasks.” Thus, the reported “139/178 versus 132/178” is useful descriptive evidence but not convincing evidence that Mini generalizes better than the matched portfolio.

- The causal contribution of semantic overlap is underidentified. The semantic-free ablation “cannot equalize latent trajectories or realized compute,” and the TOV route uses “more realized compute than Generic.” Moreover, “Ledger diagnoses are not independently labelled,” so the paper does not establish that the semantic relations are accurate or that they, rather than additional output and prompt differences, cause the gains.

- Several load-bearing design choices lack factorial ablations. There is no clear comparison isolating immutable anchoring, unresolved-only branching, recursive promotion, and route heterogeneity while holding the number and identity of model outputs fixed. The authors acknowledge that “we do not claim a new selector beyond that max operation,” which makes it especially important to show which parts of the composition produce practical gains.

- Statistical evidence is weaker than the task-level p-values suggest for broad claims. “All task rows within one arm share one whole-track model call,” and the paper concedes that these tests are “not session- or language-population inference.” The five-track sign result is only `p=.125`, while the five-session studies cover just Python34 and C++26, so the evidence does not support population-level claims about languages or model sessions.

- Generalization is narrow and heavily conditional on the benchmark contract. The method requires that “tasks are partitioned into task units whose declared solution files and verifier do not cross task boundaries,” while the paper does not test shared build state, cross-task dependencies, flaky or weak tests, or unavailable tests. Its strongest guarantee is explicitly only about observed test labels: “it does not guarantee correctness beyond those tests.”

- The practical efficiency case is unresolved. The system uses “five whole-track model calls plus intermediate verification,” and the authors state that it is “an effectiveness system, not an efficiency result.” The final-call table also shows unequal realized costs, with TOV taking “29.6 more seconds” than the stricter control, so the quality advantage is not normalized by tokens, latency, or monetary cost.

- The baselines do not establish superiority over strong repository-level repair systems. The paper states that its Graph, repair, and named reasoning methods are “bounded prompt realizations rather than complete reproductions” and explicitly does not claim superiority over “a matched full repository agent such as KIRA.” This leaves the external significance of the improvement uncertain.

## Questions for the Authors

1. Can you run a prospectively frozen comparison of Mini, Direct∪Generic, and a no-anchor recursive union on several untouched complete tracks, with identical model calls, token caps, and wall-clock budgets?

2. What are the results of a factorial ablation separately removing immutable anchoring, unresolved-only branching, semantic relations, completion locking, and recursive promotion?

3. How much of the TOV–Generic difference remains after matching realized output tokens and latency rather than only nominal call count?

4. Can independent experts label the TOV ledger fields and test whether semantic-overlap accuracy predicts successful repairs or merely correlates with model trajectory?

5. How does the method behave on repositories with shared files, cross-task dependencies, flaky tests, incomplete tests, or no executable verifier?

6. Why should the five-track aggregate be treated as evidence for a general system advantage when the clean prospective JavaScript result is “47/49” for both portfolios and the Go comparator required a post-primary replacement?

## Scores

Soundness: 3/4 — The verifier-preservation construction is sound and the empirical claims are carefully qualified, but causal attribution and statistical generalization remain limited.

Presentation: 4/4 — The paper is exceptionally explicit about protocols, chronology, denominators, deviations, and claim boundaries, though technically dense.

Significance: 3/4 — Reliable preservation and complementary repair could matter in test-available program repair, but the practical and external scope is not yet demonstrated.

Originality: 3/4 — The composition of immutable verified task states and heterogeneous routes is useful, but the promotion rule is acknowledged to be algebraically a task-wise union.

Overall recommendation: 3/6 — Borderline: promising and carefully executed bounded-system evidence, but the main comparative and semantic claims require prospective, compute-matched validation.

Confidence: 4/5 — The paper provides enough self-contained methodological and numerical detail for a confident assessment, although the underlying artifacts and runs cannot be independently rerun here.

## Ethics and Limitations

The study uses public software exercises and no human participants. It appropriately withholds private tests and gold implementations, while acknowledging that failure output may reveal behavioral expectations. The increased inference compute is disclosed, and licensing obligations for Exercism and HumanEvalPack are recognized. A further concern is benchmark contamination: the authors note that “public QuixBugs may occur in training data,” which weakens that transfer diagnostic. The principal limitations are the single model/runtime, correlated candidate errors, finite and potentially weak verifiers, incomplete coverage of non-modular repositories, unequal realized compute, and the absence of stable standalone semantic-route superiority.

## Comment

I recommend borderline rejection in the current form. The strongest contribution is a well-engineered, mechanically test-label-preserving composition rule with promising bounded-call results, not a demonstrated semantic-overlap advantage or broad general-purpose repair improvement. The most important revision is a prospective, compute-matched factorial evaluation that isolates anchoring, route heterogeneity, and recursive promotion across multiple untouched repositories and verifier regimes.
