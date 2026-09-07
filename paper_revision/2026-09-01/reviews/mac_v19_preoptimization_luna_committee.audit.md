# ICML-Style Paper Review

## Paper and Evidence Identity

- Review method: full review — deterministic evidence audit + review panel. The panel's review is the official output; this document is its audit sidecar.
- Review Agent name/version: paper-reviewer / `sha256:9886349f92661c3c73b70f216a7038b741b47282d7624538ad207dd3fbb2d4c0`
- Review-agent spec path/hash: `review-agent-spec.md` / `sha256:08b13516a2cb0e5151c6b4dc24f98e6d191b35ee30d69ea300b2d6ff2d5a5945`
- Original paper identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:b255fe4f6134a2f19f72f73aed5143b04cb093e7087b62e8fcfb193ea7c0d9e4` / `64433` bytes
- Derived Markdown identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:b255fe4f6134a2f19f72f73aed5143b04cb093e7087b62e8fcfb193ea7c0d9e4` / `64433` bytes
- Original PDF page count: `n/a`
- Converter: `none (Markdown source)`
- Paper version/hash: `Mini_Artichokes_manuscript_v4.md` / `sha256:b255fe4f6134a2f19f72f73aed5143b04cb093e7087b62e8fcfb193ea7c0d9e4`
- Evidence bundle reviewed: none (no evidence bundle supplied)
- Frozen at (UTC): `2026-09-04T03:04:39+00:00`

## Summary

We introduce **Mini Artichokes**, a. It reports 150 quantitative result claim(s) and cites 12 prior work(s). Deterministic audit: 0 contradiction(s), 0 dishonest self-certification(s), 0 mechanical finding(s); 0 result claim(s) evidence-backed, 971 unverifiable. Overall recommendation: 3/6 [claim-001].

## Strengths

- The paper situates its contribution against prior work (12 citation(s); related-work section present).

## Weaknesses

- The deterministic audit proved no contradiction, arithmetic error, or integrity breach; the remaining concern is limited to claims that could not be independently verified (see Questions).

## Questions for the Authors

1. For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?
2. 150 extracted result/arithmetic claim(s) could not be checked against the supplied evidence and are listed with their source lines in the Evidence Trace — could the authors provide the underlying results?

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
- Frozen review identity: `sha256:260b7629fe880e599144b13333add714e0b19b577328d06f6f2b9ba58aa1b104`.
- Verdict labels digest: `sha256:173c370d31c437fe944e69b73c05d45b4a1da289ddc943a93fc5fab7e3da76ea`.
- External citation snapshot digest: `sha256:01545e382bf7b0636dcadf97adfec0e438018ba58ffefc7b6167718586eab0a7`.
- Scientific judgment identity: `sha256:5eba307211d764de45f9909d448bb8f1cde37e143b6b47dfa0e34a84d3c349fc`.
- Review panel configuration: panel=3, model=`gpt-5.6-luna`, synthesis=area-chair.
- Panel reviewer `theorist`: prompt=`sha256:7abf145469a819d71786f7d1dbeda9814d3bd416ba119985f473cfa52685cea2`, response=`sha256:a068a9e801cbd2a9fcccda696d01ef2b785f7202276e068a2ba9fd770a4d50d5`, status=ok.
- Panel reviewer `experimentalist`: prompt=`sha256:3c4cda0b4264f6f68b69eae2394520d3abde9dcbf4af0eead0be2aa911c7cbeb`, response=`sha256:c230074f796affdd3730d8327e40b0b9a28f028b3384d084ce9e195d5f923345`, status=ok.
- Panel reviewer `scope_ablation`: prompt=`sha256:acca5f64127fbd192af40c6638f4f1fc8f2f6f5b728b0d3601a835701d5db2a4`, response=`sha256:e7f3f7bd14c559d7bb4427f219a43bbec1afc2d9123f5adb026c89a7b00cd692`, status=ok.
- Output path: `mac_v19_preoptimization_luna_committee.md`.
- Frozen paper input: `Mini_Artichokes_manuscript_v4.md` (`sha256:b255fe4f6134a2f19f72f73aed5143b04cb093e7087b62e8fcfb193ea7c0d9e4`).
- Frozen original identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:b255fe4f6134a2f19f72f73aed5143b04cb093e7087b62e8fcfb193ea7c0d9e4`, 64433 bytes, page count=n/a).
- Frozen derived identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:b255fe4f6134a2f19f72f73aed5143b04cb093e7087b62e8fcfb193ea7c0d9e4`, 64433 bytes).
- Frozen converter: `none (Markdown source)`.
- Pre-S1 sanitation: 0 trace(s), 0 injection finding(s).
- S1 parse inventory: 40 sections, 11 tables, 773 numeric tokens with source locations.
- S3 ledger-trace: 0/0 metric-labelled values matched; 0 finding(s).
- S3 internal-consistency: 0 comparison(s), 0 finding(s).
- S3 arithmetic: 0 recomputation(s), 0 finding(s).
- S3 baseline-fairness: 0 explicit improvement claim(s), 0 finding(s).
- S3 negative-evidence: 0 discard/crash outcome(s), 0 omission finding(s).
- S3 citation-existence: 2 explicit identifier(s), 0 existence/title finding(s).
- S3 template-compliance: 1 contract trace(s), 0 finding(s).
- S3 injection-scan: 0 sanitation trace(s), 0 reviewer-directed instruction finding(s).
- S3 self-review-audit: 0 checklist item(s), 0 dishonest self-certification(s).
- S3 positioning: 12 cited reference(s), related-work section=True, 1 novelty/superiority claim(s), 0 overclaim finding(s), 0 positioning question(s).
- S5 DRAFT/GROUND: 150 candidate comment(s), 150 retained, 0 deleted, 150 criticism comment(s) converted to questions.
- S2/S4 claim verdicts:
- [claim-024] **unverifiable** — paper:24 — before-call-frozen track, all 49 JavaScript tasks, the corresponding scores are — No implemented mechanical check proves or disproves this claim. Evidence: `paper:24`.
- [claim-027] **unverifiable** — paper:27 — reaches **164/164** versus 157/164 for Plain; ordinary repair already reaches — No implemented mechanical check proves or disproves this claim. Evidence: `paper:27`.
- [claim-030] **unverifiable** — paper:29 — fixed-resource efficiency results. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:29`.
- [claim-033] **unverifiable** — paper:32 — same-five-call TOV-plus-Direct portfolio scores 59/90 versus 54/90 for — No implemented mechanical check proves or disproves this claim. Evidence: `paper:32`.
- [claim-037] **unverifiable** — paper:36 — JavaScript comparison is an exact 47/49 tie and HumanEvalFix is ceiling-tied. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:36`.
- [claim-038] **unverifiable** — paper:37 — Thus verified redundancy is the supported system result; semantic overlap is a — No implemented mechanical check proves or disproves this claim. Evidence: `paper:37`.
- [claim-044] **unverifiable** — paper:47 — can improve over one-pass generation, yet their composition is fragile. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:47`.
- [claim-054] **unverifiable** — paper:57 — hypotheses improve one final repair route. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:57`.
- [claim-059] **unverifiable** — paper:62 — **semantic-relation value:** whether comparing what failed candidates mean — No implemented mechanical check proves or disproves this claim. Evidence: `paper:62`.
- [claim-060] **unverifiable** — paper:63 — improves repair beyond a final agent with the same candidates, evidence, — No implemented mechanical check proves or disproves this claim. Evidence: `paper:63`.
- [claim-089] **unverifiable** — paper:93 — **RQ1:** Does recursive verified redundancy improve Plain, Graph, and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:93`.
- [claim-109] **unverifiable** — paper:116 — complete tracks that expose both positive mean differences and large — No implemented mechanical check proves or disproves this claim. Evidence: `paper:116`.
- [claim-110] **unverifiable** — paper:118 — an exploratory equal-call dual-route comparison and repeated-session union — No implemented mechanical check proves or disproves this claim. Evidence: `paper:118`.
- [claim-119] **unverifiable** — paper:127 — HumanEvalFixDocs Python tasks, which reaches a 164/164 verified ceiling and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:127`.
- [claim-124] **unverifiable** — paper:137 — End-to-end five-call effectiveness | 59/90 original; frozen Go 33/39; frozen JavaScript 47/49; HumanEvalFix 164/164 | Supported in the reported test-available setting — No implemented mechanical check proves or disproves this claim. Evidence: `paper:137`.
- [claim-125] **unverifiable** — paper:138 — Advantage over a same-call generic portfolio | 59/90 vs 54/90; Go replacement 33/39 vs 31/39; JavaScript and HumanEvalFix ties | Not prospectively established — No implemented mechanical check proves or disproves this claim. Evidence: `paper:138`.
- [claim-153] **unverifiable** — paper:175 — an indivisible task it reduces to ordinary verifier-selected best-of-multiple. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:175`.
- [claim-200] **unverifiable** — paper:232 — priority affects provenance, not the observed pass label. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:232`.
- [claim-204] **unverifiable** — paper:239 — After its model call, the experiment — No implemented mechanical check proves or disproves this claim. Evidence: `paper:239`.
- [claim-216] **unverifiable** — paper:258 — The semantic comparison is behavioral. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:258`.
- [claim-253] **unverifiable** — paper:293 — `/tmp/artifacts/decision_ledger.json` with exactly one record for each frozen — No implemented mechanical check proves or disproves this claim. Evidence: `paper:293`.
- [claim-259] **unverifiable** — paper:297 — They do not score the natural-language diagnoses for — No implemented mechanical check proves or disproves this claim. Evidence: `paper:297`.
- [claim-279] **unverifiable** — paper:318 — verification preserves every observed pass from either included route on the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:318`.
- [claim-281] **unverifiable** — paper:320 — The construction was formulated after final-route crossovers were observed and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:320`.
- [claim-291] **unverifiable** — paper:329 — recursive promotion--rather than a score gain over an offline union of the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:329`.
- [claim-306] **unverifiable** — paper:345 — tasks observed passing in included route `k`, and let `A` be the prior anchor — No implemented mechanical check proves or disproves this claim. Evidence: `paper:345`.
- [claim-310] **unverifiable** — paper:349 — complete state already observed to pass; no unverified merged state is — No implemented mechanical check proves or disproves this claim. Evidence: `paper:349`.
- [claim-311] **unverifiable** — paper:350 — Hence its observed task score is at least that of the prior anchor set — No implemented mechanical check proves or disproves this claim. Evidence: `paper:350`.
- [claim-327] **unverifiable** — paper:375 — We report both the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:375`.
- [claim-342] **unverifiable** — paper:393 — `counter` task reports `no tests to run`; it is retained in the denominator — No implemented mechanical check proves or disproves this claim. Evidence: `paper:393`.
- (+941 further extracted claim(s) — mostly unverifiable prose — omitted here for brevity; all are labelled in S2/S4 with source lines.)

## Comment

Recommendation: 3/6. No headline result is mechanically supported yet, so the recommendation stays borderline pending stronger evidence. Most useful next step for the authors — For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?

## Panel Reviews (provenance)

### Panel review 1 — theorist (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

The paper presents Mini Artichokes, a five-call program-repair system that preserves task-level solutions passing an external verifier, restricts subsequent edits to unresolved tasks, and unions passing outputs from direct and semantic-overlap repair routes. On complete Aider tracks, it reports 139/178 solved versus 112/178 for ordinary repair and 59/178 for Plain. The paper is appropriately cautious that its strongest evidence supports an end-to-end test-available system, not a standalone causal benefit from semantic overlap.

## Strengths

- The central preservation mechanism is clearly specified and formally characterized. The paper states that “a complete verified task state is removed from model discretion” and gives explicit assumptions A1–A5 governing task locality, isolation, complete-file copying, restoration, and fail-closed behavior.

- The evaluation retains complete benchmark denominators rather than selecting favorable tasks. For example, “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks” are included, followed by complete Go, JavaScript, and HumanEvalFix evaluations.

- The results show substantial end-to-end effectiveness under the stated test-available setting. Mini Artichokes achieves 59/90 versus 45/90 for ordinary repair, 33/39 versus 25/39 on Go, and 47/49 versus 42/49 on JavaScript.

- The paper provides unusually strong negative and boundary evidence. It reports that the strict Java20 gate achieved “5/20 versus 7/20,” that JavaScript produced an “exact equal-call Generic tie,” and that HumanEvalFix reached a ceiling where “ordinary repair also reaches 164/164.”

- The authors distinguish mechanical verifier-union gains from semantic-route gains. They explicitly acknowledge that recursive dominance “is mechanical and uses an additional direct route” and that semantic overlap is “not established” as a repeatable standalone effect.

- The paper reports important operational failures rather than hiding them: the Go Generic call was “transport-null,” two Python replication ledgers violated row order, and one C++ call generated forbidden `a.out`.

## Weaknesses

- The main system comparison is not compute-matched against the strongest baselines. Mini Artichokes uses five model calls, while Plain uses one and ordinary repair uses two; the paper itself says these comparisons are “effectiveness under the stated call cap” and “not efficiency.” Thus the large gains, such as 59/90 versus 15/90, establish the value of additional test-time computation and verification, but do not isolate the proposed structure from simply spending more calls.

- The central semantic-overlap claim is not convincingly established. In the original 90-task comparison, TOV beats the semantic-free control by 58/90 versus 51/90, but the control was “frozen only after all TOV outcomes and the MAC v9 critique were known.” The two five-pair replications produce wide intervals, with Python `[-2.35,+8.24]` percentage points and C++ `[-6.92,+11.54]`, while prospective JavaScript and HumanEvalFix are ties. The evidence therefore supports a plausible exploratory component, not a reliable causal improvement.

- The recursive system’s strongest equal-call result is post hoc. The paper states that “the recursive dual-route analysis was specified only after these repetitions revealed large branch crossovers.” Its 59/90 versus 54/90 advantage is consequently vulnerable to analysis and mechanism selection based on observed outcomes, even though the later Go protocol was frozen.

- The controls do not fully resolve what causes the improvement. TOV differs from semantic-free control in natural-language instructions, attention allocation, and likely realized reasoning trajectories; the authors concede that the ablation “cannot make latent model trajectories identical.” Moreover, the final system bundles candidate diversity, execution feedback, anchoring, two routes, and recursive promotion, so the contribution is a composition whose individual necessity is unclear.

- The statistical treatment appropriately notes clustering, but the principal significance claims still rely heavily on task-level discordance from a single whole-track model call. The paper acknowledges that “task-level tests and bootstrap intervals condition on those realized calls,” and the track-level checks are severely underpowered. Consequently, values such as `p=5.68e-14` should not be interpreted as broad evidence that the method generalizes across runs, languages, or models.

- The applicability assumptions materially limit the scope of the claimed “universal” mechanism. The preservation theorem requires “task-local declared files,” “no cross-task test dependency,” isolated workspaces, and a stable verifier. These assumptions fit the packaged benchmarks but exclude many real repositories with shared build state, integration tests, generated files, or nondeterministic behavior.

- The empirical setting is narrow and potentially favorable to test-time verifier portfolios: all semantic calls use one model and runtime, tasks are processed in whole-track calls, and failure output is exposed between calls. The paper also does not compare against a contemporary repository agent under matched access and budgets, stating that it “makes no state-of-the-art claim.” This makes the practical significance relative to strong repair systems uncertain.

- The semantic ledger is not independently evaluated. The paper requires fields such as “fault location,” “violated requirement,” and “edit intent,” but integrity checks “do not score the natural-language diagnoses for semantic correctness.” The claimed mechanism may therefore be functioning primarily as a prompt-induced extra reasoning pass rather than as meaningful semantic-overlap analysis.

## Questions for the Authors

1. What is the fairest compute-matched comparison between Mini Artichokes and ordinary repair or a generic multi-call verifier portfolio when matching total model tokens, wall-clock time, and evaluator invocations rather than nominal call count?

2. Can you provide a preregistered, multi-seed, multi-track experiment in which TOV, semantic-free structured control, and generic Critic receive identical candidate artifacts and matched realized budgets before any outcomes are observed?

3. How much of the five-call gain remains under an ablation that uses the same two final routes but disables recursive promotion, and under a verifier-only union of the same stored outputs?

4. How are candidate “fault location,” “invariant,” “counterexample,” and “edit intent” annotated or validated independently, and does ledger quality predict successful repairs?

5. Which real repository settings satisfy A1–A5, and what modification preserves the guarantee when tasks share files, build state, or nondeterministic tests?

## Scores

Soundness: 3/4 — The preservation argument is sound under explicit assumptions and the empirical reporting is candid, but causal attribution and generalization remain limited.

Presentation: 3/4 — The paper is unusually transparent and well organized, though the many stages, controls, and post hoc distinctions make the evidential hierarchy difficult to follow.

Significance: 3/4 — Verified task-level preservation is practically useful, but the demonstrated benefit is tied to extra compute and a narrow test-available setting.

Originality: 3/4 — The composition of immutable verified anchors, unresolved-only branching, and recursive union is a meaningful systems design, although its components largely build on known ensembles, reflection, and verifier-based selection.

Overall recommendation: 3/6 — Borderline; the system result is promising, but the paper does not yet establish that the proposed semantic mechanism or overall architecture beats simpler compute-matched alternatives.

Confidence: 4/5 — The paper provides sufficient internal detail and caveats for a reasoned assessment, though the underlying runs and artifacts cannot be independently rerun here.

## Ethics and Limitations

The paper uses public programming exercises and reports no human-participant concerns. It appropriately discusses increased inference cost, bounded failure-output leakage, licensing obligations, finite-test correctness, runtime deviations, and the limits of its task-local preservation theorem. The principal scientific limitation is that benchmark-pass preservation is not semantic correctness beyond the supplied tests, and the reported improvements are not yet robustly separated from additional computation, prompt effects, and post hoc route selection.

## Comment

I recommend borderline rejection in the current form. The most important revision is a genuinely prospective, compute-matched evaluation against generic multi-call repair and verifier-union baselines, with several independent whole-track sessions and a pre-specified analysis. That experiment would determine whether Mini Artichokes is a substantive general repair algorithm or primarily a well-engineered way to spend additional test-time calls while safely retaining observed passes.

### Panel review 2 — experimentalist (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper presents Mini Artichokes, a five-call program-repair system that preserves complete task solutions passing an external verifier, edits only unresolved tasks, and recursively unions passing outputs from direct and semantic-overlap-aware routes. Across complete Aider tracks it reports 139/178 successes versus 112/178 for ordinary repair and 59/178 for Plain. The strongest evidence supports verified multi-route repair under test availability, while the paper itself appropriately argues that semantic overlap has not been causally or reliably established.

## Strengths

- The preservation mechanism is clearly specified and has a genuine structural guarantee. The paper states that “a complete verified task state is removed from model discretion” and formalizes the property under assumptions A1–A5, including “promotion copies the complete allowlisted solution-file tuple for a task.” This is a meaningful reliability contribution for modular, test-available tasks.

- The evaluation retains complete denominators rather than selecting convenient tasks. The paper reports “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” later adding “all 39 official Go tasks” and “all 49 JavaScript tasks.” This substantially improves credibility relative to selective repair demonstrations.

- The system-level results are large against simple baselines. On the original 90 tasks, Mini Artichokes achieves “59/90 (65.6%),” compared with “15/90 (16.7%) for Plain” and “45/90 (50.0%) for ordinary repair.” The paper correctly labels these as “effectiveness comparisons between nested one-, two-, and five-call systems, not efficiency or overlap-only estimates.”

- The paper includes unusually candid negative and boundary evidence. It reports that “JavaScript supplies a clean prospective tie,” that HumanEvalFix “ties at ceiling,” and that the Go equal-call sensitivity “fails both the `.05` directional gate and the separately named +8/39 strong-effect gate.” This substantially improves the paper’s scientific calibration.

- The component analysis is better controlled than a Plain-only comparison. The semantic-free control shares “the same ledger fields, counterexample-based falsification, and two audits,” while withholding candidate relations. The paper also reports the sole harm, Rust `fizzy`, rather than presenting semantic diagnosis as infallible.

- The authors explicitly address clustering and session variance. They note that “all task rows within one arm share one whole-track model call” and provide five-pair replications with wide intervals. This is an important acknowledgment of the limits of task-level significance testing.

## Weaknesses

- The central empirical advantage is not established under a clean, prospective, compute-matched comparison. The original equal-five-call result is explicitly “a post-hoc equal-call system contrast,” and the Go replacement was run “after TOV outcomes were known.” In the clean prospective JavaScript experiment, Mini Artichokes ties the control at “47/49,” while HumanEvalFix is also tied at “164/164.” Thus the strongest causal comparison does not currently demonstrate that the proposed overlap-aware route improves the five-call system.

- The headline system gains conflate several mechanisms and additional computation. Mini Artichokes uses five calls, whereas Plain uses one and ordinary repair uses two. The paper itself states that “candidate diversity, external execution, the verified floor, and both final routes contribute.” Consequently, the large gains over Plain and ordinary repair establish a useful test-time system, but they do not isolate recursive redundancy or semantic overlap as the source of improvement.

- The recursive union is largely an enforcement and accounting operation rather than a novel selection algorithm. The paper concedes that “a minimal task-wise verifier union is algebraically identical to this promotion rule” and “we do not claim a new selector beyond that max operation.” The remaining novelty is therefore mainly the composition and protocol discipline; the paper should sharpen why this composition constitutes a substantive algorithmic contribution beyond best-of-many verified repair with task-level modularity.

- The semantic-overlap evidence is unstable across sessions and contexts. The five-pair replications have means of only “+1.2/34 (+3.53 pp)” and “+0.4/26 (+1.54 pp),” with intervals `[-2.35,+8.24]` and `[-6.92,+11.54]` percentage points. The paper also reports that several tasks “crossed between arms.” This supports semantic overlap as a plausible exploratory route, but not yet as a robust component claim.

- The statistical presentation risks overstating precision when using task-level tests on whole-track calls. For example, the Mini-versus-Plain contrast reports `p=5.68e-14`, although each arm’s 90 task outcomes are generated by only a small number of shared whole-track invocations. The paper acknowledges this dependence and supplies track-level checks, but the headline inferential framing should prioritize session- or track-level uncertainty rather than highly significant conditional task tests.

- The control is not a fully nonlinguistic intervention. The authors state that the semantic-free ablation “cannot make latent model trajectories identical,” and the control was “designed after TOV results and reviewer feedback.” This leaves open whether the observed original 7-task difference reflects semantic relations, prompt wording, attention allocation, or other trajectory effects.

- Generality is narrower than the system framing suggests. The study uses “one model and runtime,” five Aider language tracks, one HumanEvalFix configuration, and test-available modular tasks. The formal guarantee requires “task-local declared files,” “isolated workspaces,” and a stable verifier. These are sensible boundaries, but they limit claims about general program repair or settings without strong external tests.

## Questions for the Authors

1. Can you provide a genuinely prospective, equal-call and approximately token-matched comparison between Mini Artichokes and the strongest generic five-call portfolio, across multiple complete tracks?

2. How much of the improvement remains after ablating each component separately: immutable anchoring, unresolved-only branching, the second route, and semantic-overlap instructions?

3. Can you report confidence intervals and primary significance tests at the whole-track/session level for all principal comparisons, rather than emphasizing task-level tests conditioned on shared calls?

4. What evidence distinguishes semantic-overlap reasoning from generic additional deliberation, increased prompt context, or different output-schema constraints?

5. Can the recursive promotion rule be evaluated on benchmarks with shared build state, nondeterministic tests, or less modular solution boundaries to test the practical scope of assumptions A1–A5?

## Scores

Soundness: 3/4 — The preservation property and evaluation protocol are strong, but causal attribution and independent replication remain limited.

Presentation: 3/4 — The paper is unusually transparent and well organized, though the many stages, controls, and qualifications make the central contribution difficult to isolate.

Significance: 3/4 — Verified multi-route repair could be practically useful, but the demonstrated benefit is specific to test-available modular tasks and extra computation.

Originality: 3/4 — The enforced composition of anchors, unresolved-only repair, and recursive verified union is a coherent contribution, although the union itself is algebraically simple.

Overall recommendation: 3/6 — Borderline; the system result is promising, but the principal mechanism is not prospectively established and the strongest gains are not compute-matched.

Confidence: 4/5 — The paper is sufficiently self-contained to assess its claims, though the underlying experimental artifacts cannot be independently rerun here.

## Ethics and Limitations

The paper identifies the main ethical and practical issues appropriately: it uses public coding exercises, exposes models to bounded test failures, and increases inference compute. Its stated limitations are substantial and credible, including one model/runtime, correlated candidates, whole-track call dependence, post-hoc control design, runtime deviation on HumanEvalFix, finite test specifications, and limited generality beyond modular test-available tasks. The use of benchmark tests as correctness evidence should continue to be distinguished from semantic correctness beyond the supplied suites.

## Comment

I recommend borderline acceptance/rejection depending on the venue’s novelty threshold. The most important revision is to separate the compelling verified-preservation and multi-route effectiveness result from the much less established semantic-overlap claim, and to support the former with a prospective, compute-matched generic multi-route baseline.

### Panel review 3 — scope_ablation (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper proposes Mini Artichokes, a five-call program-repair system that preserves task-level solutions passing an external verifier, restricts later editing to unresolved tasks, and recursively unions passing outputs from direct and semantic-overlap repair routes. Across complete Aider tracks it reaches 139/178 tasks, compared with 112/178 for ordinary repair and 59/178 for Plain. The system-level results are promising, but the paper appropriately acknowledges that the incremental causal value of semantic overlap is not established: prospective comparisons are ties or statistically uncertain, and much of the strongest evidence is post hoc or nested with additional compute.

## Strengths

- The central preservation mechanism is clearly specified and supported by a concrete invariant: “A complete task state that passes the external verifier becomes an immutable anchor; only common failures remain editable.” The A1–A5 contract and the stated property that promotion “copies either its prior anchored state or one complete state already observed to pass” provide a meaningful formal guarantee of test-label preservation.

- The evaluation retains complete benchmark tracks rather than selecting favorable tasks. The paper reports “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” followed by complete Go39 and JavaScript49 evaluations. This makes the reported denominators and rescue/harm accounting substantially more credible than sampled case studies.

- The system-level gains over simpler baselines are large and consistently reported. On all 178 Aider tasks, Mini Artichokes obtains “139/178 (78.1%),” versus “112/178 (62.9%)” for ordinary repair and “59/178 (33.1%)” for Plain. On JavaScript49, it reaches “47/49” versus “42/49” for ordinary repair and “27/49” for Plain.

- The paper makes an important distinction between effectiveness and efficiency. It explicitly states that comparisons are “not efficiency or monetary-cost dominance,” and reports that TOV takes “29.6 more seconds in aggregate” than the semantic-free structured control. This is good scientific calibration given the additional calls and large whole-track contexts.

- The authors provide unusually candid negative and null evidence. They report that the JavaScript overlap comparison is an “exact 47/49 tie,” HumanEvalFix reaches a ceiling where “ordinary repair also reaches 164/164,” and the Go equal-call sensitivity has `p=.3125`. The conclusion correspondingly narrows the claim to “semantic disagreement as one heterogeneous falsification route,” rather than claiming a universal semantic-overlap effect.

- The paper separates mechanical verifier-union benefits from semantic-route effects. It explicitly says that “we do not claim a new selector beyond that max operation,” which is an appropriately modest interpretation of the recursive promotion rule.

## Weaknesses

- The main scientific novelty is not convincingly isolated. The strongest equal-call Mini-versus-control result, “59/90 versus 54/90,” was selected after route crossovers, while the prospective JavaScript comparison is an exact tie and the Go replacement sensitivity is only “33/39 versus 31/39” with `p=.3125`. Thus the paper demonstrates that a verifier can union complementary outputs, but does not establish that the proposed TOV semantics reliably create those complementary outputs.

- The largest gains compare systems with substantially more model calls and compute against Plain or ordinary repair. For example, Mini gains “16/39” over Plain and “8/39” over ordinary repair on Go, but the paper itself concedes these are “nested system comparisons with additional calls.” These results support an effectiveness claim under a generous test-time-compute budget, not a clear algorithmic advantage over stronger compute-matched alternatives.

- The semantic-free ablation is not a fully controlled causal intervention. Although it matches “named instructions,” the paper admits that it “cannot make latent model trajectories identical,” and Table 3 shows substantial session variability: Python differences are `+4,-2,+2,0,+2`, while C++ differences are `+1,-1,0,+5,-3`. The proposed semantic relation may therefore be confounded with prompt-induced reasoning trajectory changes.

- The evaluation scope is narrower than the universal framing suggests. The experiments use “one model and runtime,” five Aider language tracks, and one HumanEvalFix configuration, with each new track generally having one realized session. The paper acknowledges that five sessions in two fixed contexts “do not estimate a broad language, model, or benchmark population.” Claims about general program repair should consequently be substantially more qualified.

- The semantic diagnoses are neither independently annotated nor evaluated for correctness. The paper states that “ledger diagnoses were not independently annotated,” and the integrity checks “do not score the natural-language diagnoses for semantic correctness.” This leaves the purported behavioral-overlap mechanism difficult to inspect or distinguish from a useful but opaque prompt format.

- The recursive union’s benefit is partly tautological once complementary route outputs are available. The paper correctly notes that “a minimal task-wise verifier union is algebraically identical to this promotion rule.” The substantive empirical question is therefore route generation and diversity, but the paper does not provide a sufficiently controlled analysis of what causes the routes to differ or when the overlap route should be selected.

- The benchmark verifier may overstate correctness relative to real repair. The paper itself notes that anchors preserve “benchmark passes, not proof of correctness beyond those tests,” and that one Go task has “no tests to run.” The resulting guarantee is test-label preservation under A1–A5, not semantic correctness or robustness to hidden tests outside the supplied suites.

## Questions for the Authors

1. Can you provide a prospective, compute-matched comparison between TOV and a generic final repair policy across several unseen tracks, with the route and analysis frozen before any outcomes are observed?

2. What measurable property of candidate disagreement predicts a successful TOV rescue? Can this be evaluated using independently labeled fault locations, invariants, or counterexample classes rather than model-generated ledger text?

3. How much of Mini Artichokes’ gain remains when total tokens, latency, or API cost—not merely nominal call count—is matched against a generic multi-attempt verifier-union baseline?

4. Can you replicate the system with multiple models or model versions while keeping the harness and prompts fixed, to test the claimed generality beyond “one model and runtime”?

5. How does the method behave when tasks share build state, solution files, or cross-task dependencies, violating the task-local assumptions in A1 and A3?

## Scores

Soundness: 3/4 — The construction and reported measurements are careful, but the semantic component and broad generalization remain incompletely established.

Presentation: 4/4 — The paper is unusually transparent about chronology, null results, protocol deviations, and claim boundaries.

Significance: 3/4 — Verified task-level preservation and heterogeneous route union are practically useful, though the contribution is presently bounded to test-available repair.

Originality: 3/4 — The composition of immutable verified anchors with recursive route union is a useful systems formulation, but much of the underlying machinery is established or mechanically implied by verification.

Overall recommendation: 3/6 — Borderline; promising system evidence but insufficient prospective evidence for the principal algorithmic claim.

Confidence: 4/5 — The paper is self-contained and the evidence is detailed, though the review cannot independently verify the released artifacts or executions.

## Ethics and Limitations

The paper uses public programming tasks and no human participants, and it discusses licensing, test leakage, compute use, and reproducibility. Its limitations are substantial and appropriately disclosed: one model/runtime, correlated candidates, whole-track calls, limited session replication, post hoc control and recursive-route design, a transport-null Go arm, a runtime deviation in HumanEvalFix, weak-test and finite-specification concerns, and no efficiency claim. These limitations especially constrain claims about semantic-overlap causality and universal program-repair performance.

## Comment

I recommend borderline rejection in the current form. The most important issue is to separate the genuinely compelling verified-union system result from the much less established claim that semantic overlap is the mechanism producing the gain. A stronger prospective, compute-matched, independently evaluated ablation across multiple tracks or models would substantially change my assessment.
