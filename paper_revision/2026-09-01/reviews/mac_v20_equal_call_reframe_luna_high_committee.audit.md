# ICML-Style Paper Review

## Paper and Evidence Identity

- Review method: full review — deterministic evidence audit + review panel. The panel's review is the official output; this document is its audit sidecar.
- Review Agent name/version: paper-reviewer / `sha256:9886349f92661c3c73b70f216a7038b741b47282d7624538ad207dd3fbb2d4c0`
- Review-agent spec path/hash: `review-agent-spec.md` / `sha256:08b13516a2cb0e5151c6b4dc24f98e6d191b35ee30d69ea300b2d6ff2d5a5945`
- Original paper identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:c945461730231c7ee59334b6e48d43668bd2cbb95fadd5b2586d7d9603456c21` / `67690` bytes
- Derived Markdown identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:c945461730231c7ee59334b6e48d43668bd2cbb95fadd5b2586d7d9603456c21` / `67690` bytes
- Original PDF page count: `n/a`
- Converter: `none (Markdown source)`
- Paper version/hash: `Mini_Artichokes_manuscript_v4.md` / `sha256:c945461730231c7ee59334b6e48d43668bd2cbb95fadd5b2586d7d9603456c21`
- Evidence bundle reviewed: none (no evidence bundle supplied)
- Frozen at (UTC): `2026-09-04T03:15:42+00:00`

## Summary

We introduce **Mini Artichokes**, a. It reports 158 quantitative result claim(s) and cites 12 prior work(s). Deterministic audit: 0 contradiction(s), 0 dishonest self-certification(s), 0 mechanical finding(s); 0 result claim(s) evidence-backed, 1022 unverifiable. Overall recommendation: 3/6 [claim-001].

## Strengths

- The paper situates its contribution against prior work (12 citation(s); related-work section present).

## Weaknesses

- The deterministic audit proved no contradiction, arithmetic error, or integrity breach; the remaining concern is limited to claims that could not be independently verified (see Questions).

## Questions for the Authors

1. For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?
2. 158 extracted result/arithmetic claim(s) could not be checked against the supplied evidence and are listed with their source lines in the Evidence Trace — could the authors provide the underlying results?

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
- Frozen review identity: `sha256:3d135925f567ae2cde3907bdf81b004bd99085e9e73bbda63995d089754faabe`.
- Verdict labels digest: `sha256:1313d31b83695a1300d2c37f5862a292da464773c58eaef4379112f750953916`.
- External citation snapshot digest: `sha256:01545e382bf7b0636dcadf97adfec0e438018ba58ffefc7b6167718586eab0a7`.
- Scientific judgment identity: `sha256:57117cb7450bd155145d3479b335e173a6313df1ddac12bb0f02bc460f8fcd8b`.
- Review panel configuration: panel=3, model=`gpt-5.6-luna`, synthesis=area-chair.
- Panel reviewer `theorist`: prompt=`sha256:1dc6429429890677fe51189a612555b197e725d570701cfc68051004c9444037`, response=`sha256:02beeed1ab7e720bedcac6a4065c78fd3791d7c626b3d11c2397e49eda85c2ee`, status=ok.
- Panel reviewer `experimentalist`: prompt=`sha256:e7a2e416b4ef1634453cf9a2d5653d5fa98c30cb54d8774ea08825d51e83e546`, response=`sha256:7f546b0d4c2e281a37b09c2a851d0050c47f5b5c71ef58412cdcbc0fa60c17d2`, status=ok.
- Panel reviewer `scope_ablation`: prompt=`sha256:4297d650374fdbbc1b545b399187cb8b964d61332d1b00c2644299833c5fd91b`, response=`sha256:03e31896d2cb4ef108015959d31d68c61fc0e082d47dabea9bdd13e4c6eadc65`, status=ok.
- Output path: `mac_v20_equal_call_reframe_luna_high_committee.md`.
- Frozen paper input: `Mini_Artichokes_manuscript_v4.md` (`sha256:c945461730231c7ee59334b6e48d43668bd2cbb95fadd5b2586d7d9603456c21`).
- Frozen original identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:c945461730231c7ee59334b6e48d43668bd2cbb95fadd5b2586d7d9603456c21`, 67690 bytes, page count=n/a).
- Frozen derived identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:c945461730231c7ee59334b6e48d43668bd2cbb95fadd5b2586d7d9603456c21`, 67690 bytes).
- Frozen converter: `none (Markdown source)`.
- Pre-S1 sanitation: 0 trace(s), 0 injection finding(s).
- S1 parse inventory: 40 sections, 11 tables, 826 numeric tokens with source locations.
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
- S5 DRAFT/GROUND: 158 candidate comment(s), 158 retained, 0 deleted, 158 criticism comment(s) converted to questions.
- S2/S4 claim verdicts:
- [claim-027] **unverifiable** — paper:26 — ordinary repair, and Plain score **47/49**, 47/49, 42/49, and 27/49. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:26`.
- [claim-029] **unverifiable** — paper:28 — tasks, Mini reaches **164/164** versus 157/164 for Plain; ordinary repair — No implemented mechanical check proves or disproves this claim. Evidence: `paper:28`.
- [claim-030] **unverifiable** — paper:29 — already reaches the same ceiling. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:29`.
- [claim-032] **unverifiable** — paper:30 — comparisons, not fixed-resource efficiency results. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:30`.
- [claim-044] **unverifiable** — paper:40 — the supported system result; semantic overlap is a productive heterogeneous — No implemented mechanical check proves or disproves this claim. Evidence: `paper:40`.
- [claim-050] **unverifiable** — paper:50 — can improve over one-pass generation, yet their composition is fragile. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:50`.
- [claim-060] **unverifiable** — paper:60 — hypotheses improve one final repair route. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:60`.
- [claim-065] **unverifiable** — paper:65 — **semantic-relation value:** whether comparing what failed candidates mean — No implemented mechanical check proves or disproves this claim. Evidence: `paper:65`.
- [claim-066] **unverifiable** — paper:66 — improves repair beyond a final agent with the same candidates, evidence, — No implemented mechanical check proves or disproves this claim. Evidence: `paper:66`.
- [claim-095] **unverifiable** — paper:96 — **RQ1:** Does recursive verified redundancy improve Plain, Graph, and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:96`.
- [claim-115] **unverifiable** — paper:119 — complete tracks that expose both positive mean differences and large — No implemented mechanical check proves or disproves this claim. Evidence: `paper:119`.
- [claim-116] **unverifiable** — paper:121 — an exploratory equal-call dual-route comparison and repeated-session union — No implemented mechanical check proves or disproves this claim. Evidence: `paper:121`.
- [claim-128] **unverifiable** — paper:133 — HumanEvalFixDocs Python tasks, which reaches a 164/164 verified ceiling and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:133`.
- [claim-133] **unverifiable** — paper:143 — End-to-end five-call effectiveness | 59/90 original; frozen Go 33/39; frozen JavaScript 47/49; HumanEvalFix 164/164 | Supported in the reported test-available setting — No implemented mechanical check proves or disproves this claim. Evidence: `paper:143`.
- [claim-134] **unverifiable** — paper:144 — Advantage over a same-call generic portfolio | Five-track sensitivity 139/178 vs 132/178 (8:1); clean JavaScript 47/49 tie; HumanEvalFix ceiling tie | Positive mixed-stage sensitivity; not prospectively established — No implemented mechanical check proves or disproves this claim. Evidence: `paper:144`.
- [claim-162] **unverifiable** — paper:181 — an indivisible task it reduces to ordinary verifier-selected best-of-multiple. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:181`.
- [claim-209] **unverifiable** — paper:238 — priority affects provenance, not the observed pass label. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:238`.
- [claim-213] **unverifiable** — paper:245 — After its model call, the experiment — No implemented mechanical check proves or disproves this claim. Evidence: `paper:245`.
- [claim-225] **unverifiable** — paper:264 — The semantic comparison is behavioral. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:264`.
- [claim-262] **unverifiable** — paper:299 — `/tmp/artifacts/decision_ledger.json` with exactly one record for each frozen — No implemented mechanical check proves or disproves this claim. Evidence: `paper:299`.
- [claim-268] **unverifiable** — paper:303 — They do not score the natural-language diagnoses for — No implemented mechanical check proves or disproves this claim. Evidence: `paper:303`.
- [claim-288] **unverifiable** — paper:324 — verification preserves every observed pass from either included route on the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:324`.
- [claim-290] **unverifiable** — paper:326 — The construction was formulated after final-route crossovers were observed and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:326`.
- [claim-300] **unverifiable** — paper:335 — recursive promotion--rather than a score gain over an offline union of the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:335`.
- [claim-315] **unverifiable** — paper:351 — tasks observed passing in included route `k`, and let `A` be the prior anchor — No implemented mechanical check proves or disproves this claim. Evidence: `paper:351`.
- [claim-319] **unverifiable** — paper:355 — complete state already observed to pass; no unverified merged state is — No implemented mechanical check proves or disproves this claim. Evidence: `paper:355`.
- [claim-320] **unverifiable** — paper:356 — Hence its observed task score is at least that of the prior anchor set — No implemented mechanical check proves or disproves this claim. Evidence: `paper:356`.
- [claim-336] **unverifiable** — paper:381 — We report both the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:381`.
- [claim-351] **unverifiable** — paper:399 — `counter` task reports `no tests to run`; it is retained in the denominator — No implemented mechanical check proves or disproves this claim. Evidence: `paper:399`.
- [claim-358] **unverifiable** — paper:406 — path; it occurred before any scored call, was invalidated, and the corrected — No implemented mechanical check proves or disproves this claim. Evidence: `paper:406`.
- (+992 further extracted claim(s) — mostly unverifiable prose — omitted here for brevity; all are labelled in S2/S4 with source lines.)

## Comment

Recommendation: 3/6. No headline result is mechanically supported yet, so the recommendation stays borderline pending stronger evidence. Most useful next step for the authors — For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?

## Panel Reviews (provenance)

### Panel review 1 — theorist (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper proposes a verifier-backed program-repair system that preserves complete task solutions once they pass tests, edits only unresolved tasks, and combines direct and semantic-overlap repair routes. The construction is carefully specified and empirically effective relative to one- and two-call baselines. However, the strongest same-call comparison is retrospective and compute-unmatched, while the causal contribution of semantic overlap is not established. The paper supports a useful bounded-compute engineering result more strongly than a general algorithmic or causal claim.

## Strengths

- The preservation mechanism is clearly formalized. The paper states that “a complete verified task state is removed from model discretion” and gives explicit assumptions A1–A5. Under those assumptions, the claimed property that recursive promotion “passes every task in `A union (union_k S_k)`” follows directly from copying complete previously verified states.

- The experiments retain complete benchmark inventories rather than selecting favorable tasks. For example, Table 1 reports all 90 Aider tasks, and Table 6 reports “all 49 official JavaScript tasks.” This substantially improves auditability over cherry-picked repair demonstrations.

- The system shows large practical gains over simple baselines in the reported setting. Mini Artichokes reaches “59/90” versus “15/90” for Plain and “45/90” for ordinary repair, and on Go reaches “33/39” versus “17/39” for Plain.

- The paper is unusually candid about evidential boundaries. Its claim table explicitly labels the “Advantage over a same-call generic portfolio” as “Positive mixed-stage sensitivity; not prospectively established,” and labels a “Repeatable standalone semantic-relation effect” as “Not established.”

- The authors provide useful integrity and provenance details, including byte audits, frozen hashes, transport failures, runtime deviations, and intention-to-treat handling. Retaining the failed Go invocation rather than silently replacing it is a particularly good experimental practice.

## Weaknesses

- The central same-call superiority claim is not established by a clean confirmatory experiment. The headline result, “139/178 versus 132/178,” combines “an original post-hoc analysis,” a Go replacement run performed “after TOV outcomes were known,” and a clean JavaScript tie. Indeed, the only explicitly prospective equal-call Aider result is an “exact tie” at 47/49. Thus the evidence supports a bounded realized-portfolio advantage, but not a general advantage of Mini Artichokes.

- The recursive redundancy rule has limited algorithmic novelty once its assumptions hold. The paper itself concedes that “a minimal task-wise verifier union is algebraically identical to this promotion rule” and “we do not claim a new selector beyond that max operation.” The empirical gain therefore depends almost entirely on the quality and diversity of the additional routes. The paper does not cleanly separate the contribution of anchoring, route multiplicity, and route design through a factorized ablation.

- The semantic-overlap component lacks reliable causal evidence. The semantic-free control “was frozen only after all TOV outcomes and the MAC v9 critique were known,” and the authors acknowledge that the ablation “cannot make latent model trajectories identical.” The five-pair replications are small, with intervals such as `[-6.92,+11.54]` percentage points, and the paper states that “Neither replication establishes session-level superiority at .05.” Ledger diagnoses also “were not independently annotated,” so the proposed semantic mechanism is not directly measured.

- The task-level significance values overstate the effective amount of independent evidence if read as population inference. The paper notes that “each task vector is generated inside one whole-track call” and that task-level analyses “condition on those realized calls.” The relevant independent units are closer to tracks or sessions, where the evidence is weak: the five-track sign value is `.125`, and the replication analyses contain only five paired sessions per context. The paper acknowledges this, but the numerous task-level p-values still dominate the results narrative.

- Comparisons are matched in nominal calls but not in realized computation. The paper reports that TOV uses “29.6 more seconds” than the semantic-free control, and explicitly states that “call matching is not token matching.” Consequently, the five-call Mini-versus-Generic comparison does not establish an efficiency-neutral structural advantage.

- External validity is narrow. The preservation theorem requires “a narrow contract” involving task-local files, isolated workspaces, and stable verifiers, while the study is explicitly “a test-available program repair setting, not a one-shot leaderboard protocol.” The finite test suites certify only test-label preservation, not semantic correctness beyond the supplied tests.

- Baseline strength is limited for an ICML claim. The paper states, “We do not empirically compare a full contemporary repository agent such as KIRA under matched verifier access, calls, and tokens.” The prompt-level Graph, repair, and Critic baselines are informative, but they do not establish superiority over strong existing repository-repair systems.

- The description of candidate independence is imprecise: the paper says that “Three independent whole-track calls create candidate repositories,” but ordinary repair “starts from `G`.” This dependence matters when interpreting candidate diversity and should be described and quantified more carefully.

## Questions for the Authors

1. Can the authors run a preregistered comparison of Mini versus Direct∪Generic with identical token/reasoning budgets, fresh complete tracks, and no post hoc route or replacement decisions?

2. What is the result of a factorized ablation separating immutable anchoring, unresolved-only branching, adding a second final route, and the verifier union itself?

3. How much candidate diversity exists between Plain, Graph, and Ordinary repair, given that Ordinary starts from Graph rather than being independent? Per-task overlap and failure-correlation statistics would clarify this.

4. Can the authors provide independently labeled semantic ledgers or a blinded annotation study showing that TOV’s behavioral fields and disagreement targets are accurate and predictive?

5. How does the method behave on repositories with shared build state, flaky tests, cross-task dependencies, or weaker/incomplete test suites, where A1–A5 may fail?

6. How does Mini compare against a strong contemporary repository-level repair agent under the same verifier, model, call, and token constraints?

## Scores

Soundness: 3/4 — The preservation construction is sound under explicit assumptions, but the empirical causal and generalization claims are limited.

Presentation: 4/4 — The paper is unusually clear about chronology, failed runs, statistical units, and claim boundaries.

Significance: 2/4 — The result is practically useful for a narrow test-available setting, but broad significance is not yet demonstrated.

Originality: 3/4 — The composition of verified anchoring and heterogeneous repair routes is thoughtful, although the core union operation is algebraically simple.

Overall recommendation: 3/6 — Borderline; promising systems evidence, but insufficient clean evidence for the main structural advantage.

Confidence: 3/5 — The claims and limitations are self-contained enough to assess, but the key numerical results and artifact integrity cannot be independently verified here.

## Ethics and Limitations

The use of public coding tasks and no human participants presents minimal direct ethical risk. The paper appropriately notes that failure output can reveal behavioral expectations and discloses increased inference compute, tokens, and latency. License preservation for redistributed benchmark material is also handled responsibly.

The authors honestly document the principal limitations: correlated same-model calls, few independent sessions, post hoc components, non-token-matched comparisons, finite test-suite validity, the Go transport-null arm, and the HumanEvalFix Python-version deviation. These limitations substantially constrain the paper’s claims but do not invalidate its bounded empirical observation.

## Comment

I recommend borderline rejection in its current form. The most important issue is to replace the mixed-stage, post hoc equal-call evidence with a genuinely prospective, token-matched comparison that isolates whether the proposed route composition provides a repeatable advantage beyond simply adding another repair attempt and taking the verifier-backed union.

### Panel review 2 — experimentalist (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

The paper proposes Mini Artichokes, a five-call program-repair system that preserves complete task states passing an external verifier, restricts later edits to unresolved tasks, and recursively unions passing outputs from direct and semantic-overlap repair routes. The formal preservation property is clear, and the reported system improves substantially over Plain and ordinary repair in the tested setting. However, the evidence for a general advantage over same-call alternatives is largely post hoc, task-level statistics substantially exceed the independent session count, and the semantic-overlap mechanism is not isolated convincingly.

## Strengths

- The paper clearly separates its claims. It explicitly states that “verified redundancy is the supported system result” while “semantic overlap is a productive heterogeneous route, not a universal or 20-point causal gate.” This is unusually disciplined claim calibration.

- The preservation mechanism is formally specified and intuitively sound under its assumptions. The paper defines the recursive result as `V_rec(t)=max(V_F(t),V_D(t))` and states that “no unverified merged state is created.” The A1–A5 contract, complete-file copying, anchor restoration, and fail-closed handling make the central engineering guarantee auditable.

- The experiments retain complete denominators rather than selecting favorable tasks. The paper reports all 178 Aider tasks and all 164 HumanEvalFixDocs tasks, and explicitly says that “No task in either new track is ranked, screened, removed, replaced, or topped up.” This strengthens the reported system-level comparisons.

- The empirical reporting is transparent about negative and ambiguous evidence. For example, JavaScript yields an exact tie between Mini and the equal-call comparison, while the paper retains the “sole semantic-free-only pass” on Rust `fizzy` as a harm. It also reports that both replication intervals include “meaningful help and harm.”

- The study includes stronger controls than a Plain-only comparison. The generic Critic receives “the identical original tasks, candidate patches, per-task outcomes, bounded traces, union, anchors, model, effort, final-call cap, and output cap,” and the semantic-free control retains the ledger and falsification structure. This is a serious attempt to test mechanism-level claims.

## Weaknesses

- The strongest same-call result is not a clean confirmatory experiment. The headline comparison, 139/178 versus 132/178, is explicitly described as “mixed-stage,” with the original recursive composition “chosen after observing crossovers,” Go relying on a replacement run after TOV outcomes were known, and JavaScript producing a prospective tie. Thus the `p=.01953` task-level result supports a realized portfolio observation, but not a general or prospectively established advantage of Mini over the generic portfolio.

- The independent experimental unit is the whole-track call, not the individual task. The paper acknowledges that “each task vector is generated inside one whole-track call” and that task-level analyses “condition on those realized calls.” Nevertheless, much of the strongest statistical language relies on 90 or 178 task comparisons. Within-track bootstrap and McNemar tests cannot remove correlation induced by a single model trajectory; the track-level evidence is only three positive versus two tied tracks, with sign `p=.125`. The five-pair replications are more appropriate, but their means are small and their intervals wide.

- The semantic-overlap causal attribution remains confounded by prompt-induced computation. The paper concedes that the natural-language ablation “cannot make latent model trajectories identical,” and Table 8 shows that TOV and the semantic-free control differ in realized input, output, and latency. The TOV-versus-control result could therefore reflect different prompt length, attention, reasoning allocation, or output behavior rather than semantic relations specifically. The JavaScript tie and the two non-significant replication studies reinforce that this mechanism is not yet established.

- The contribution of recursive anchoring is not experimentally isolated from candidate diversity and extra repair calls. The verified floor already rises to 48/90 from Plain’s 15/90, while Mini reaches 59/90; the paper itself says that “Candidate diversity, external execution, the verified floor, and both final routes contribute.” The preservation theorem establishes a conditional safety property, but there is no controlled comparison that removes anchoring while holding the same routes and compute fixed, so the empirical gain attributable specifically to recursion is unclear.

- The evaluation supports a bounded test-available repair claim rather than the broader framing of a general program-repair advance. All semantic calls use “one model and runtime,” tests are available between calls, and the paper does not compare against a contemporary repository agent such as KIRA under matched conditions. HumanEvalFix is also ceiling-tied because “ordinary repair reaches 164/164.” These choices are honestly disclosed, but they limit significance and external validity.

- Several protocol deviations weaken the confirmatory status of the newer evidence. The Go Generic primary call was “transport-null,” the replacement was post-primary; replication gates failed because of ledger-order and forbidden-file violations; and HumanEvalFix used Python 3.13.11 instead of the frozen 3.13.5. The intention-to-treat reporting is commendable, but the resulting collection of primary, replacement, exploratory, and ceiling analyses makes the overall evidence difficult to interpret as one precommitted test.

## Questions for the Authors

1. Can you run a prospectively frozen comparison of Mini versus Direct∪Generic across several independent tracks and sessions, with matched wall-clock or token budgets rather than nominal call counts?

2. What is the Mini-versus-no-anchoring result when the same candidate and final routes are used but previously passing task states are allowed to be modified? This would quantify the empirical contribution of anchoring separately from route diversity.

3. Can independent blinded annotators assess the TOV ledger fields and test whether the proposed “interface ambiguity” diagnoses predict future TOV-only rescues? At present, the paper says that ledger diagnoses “were not independently annotated.”

4. How do the results change if the semantic-free and TOV prompts are matched for output schema, token budget, and realized reasoning effort? This would address whether the observed differences are caused by semantic relations rather than prompt and trajectory effects.

## Scores

Soundness: 2/4 — The preservation property is sound conditionally, but the causal and statistical evidence for superiority is not yet sufficiently independent or compute-matched.

Presentation: 3/4 — The paper is unusually explicit about chronology, deviations, denominators, and claim boundaries, although the many nested stages and evidence labels make the main conclusion harder to isolate.

Significance: 3/4 — A potentially useful verified-repair composition shows substantial bounded-setting gains over simple baselines, but its practical and general impact beyond test-available suites is not established.

Originality: 3/4 — The composition of immutable task anchors, unresolved-only branching, and verifier-based recursive promotion is distinctive, though most individual ingredients are established techniques.

Overall recommendation: 3/6 — Borderline; promising systems result, but the central same-call advantage requires cleaner prospective and compute-matched evidence.

Confidence: 4/5 — The paper provides enough self-contained methodological and numerical detail for a substantive assessment, though the underlying artifacts and runs were not independently rerun.

## Ethics and Limitations

The study uses public programming exercises and no human participants. It appropriately notes that failure output can reveal behavioral expectations and that generated patches must preserve upstream licenses. The authors also candidly acknowledge limitations involving one model and runtime, whole-track call dependence, finite test specifications, test-available interaction, runtime deviations, and the lack of a matched comparison with contemporary repository agents. The main ethical concern is modest: the method increases inference compute, though the paper reports tokens and latency.

## Comment

I recommend borderline acceptance/rejection depending on the conference threshold. The paper has a clear and potentially valuable verified-preservation construction, and its system-level gains over Plain and ordinary repair appear meaningful in the reported benchmark setting. The most important issue is scientific attribution: a clean, prospective, independent, token- or time-matched comparison is needed to determine whether Mini’s advantage comes from recursive verification and semantic-overlap reasoning, rather than additional trajectory diversity and post hoc route selection.

### Panel review 3 — scope_ablation (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper proposes Mini Artichokes, a five-call program-repair system that preserves task-level solutions verified by official tests, restricts later edits to unresolved tasks, and recursively unions passing outputs from heterogeneous repair routes. The paper carefully distinguishes the mechanical preservation guarantee, the end-to-end benefit of additional test-time computation, and the narrower causal claim for semantic-overlap reasoning. Its empirical evidence supports effectiveness in the tested test-available setting, but provides limited evidence for a general advantage over compute-matched alternatives.

## Strengths

- The central preservation mechanism is clearly specified and formally justified. The paper states that “a complete verified task state is removed from model discretion” and gives explicit assumptions A1–A5, including “Promotion copies the complete allowlisted solution-file tuple for a task.” This makes the claimed test-label preservation property precise rather than rhetorical.

- The evaluation retains complete benchmark tracks rather than selecting favorable tasks. The paper reports “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” followed by complete Go, JavaScript, and HumanEvalFix evaluations. This is a meaningful strength for assessing system-level coverage.

- The paper includes appropriate controls and does not treat Plain as its only baseline. In particular, the generic Critic “receives the identical original tasks, candidate patches, per-task outcomes, bounded traces, union, anchors, model, effort, final-call cap, and output cap.” The semantic-free structured control further matches “the same ledger fields, counterexample-based falsification, and two audits.”

- The authors are unusually candid about evidential limits. They explicitly state that the five-track result is “mixed-stage and not token-matched,” that JavaScript is “the only clean prospective equal-call track and is a tie,” and that semantic overlap is “not a reliably superior standalone policy.” This substantially improves the credibility of the presentation.

- The paper reports failure and integrity cases rather than suppressing them. For example, “The sole semantic-free-only pass was Rust `fizzy`,” where TOV’s final file had “an extra closing brace and did not compile,” and one C++ replication generated forbidden `a.out`. Retaining these cases demonstrates a serious intention-to-treat analysis.

- The results show substantial system-level gains over low-compute baselines in the stated setting. On the JavaScript track, Mini reaches “47/49” versus “42/49” for ordinary repair and “27/49” for Plain; on Go, it reaches “33/39” versus “25/39” and “17/39.” These are practically meaningful improvements, even though they are not compute-matched causal comparisons.

- The paper separates verifier correctness from semantic correctness. It explicitly says recursive promotion “does not guarantee correctness beyond those tests,” and Section 5.8 notes that byte audits “do not prove verifier stability outside the observed reruns.” This is an appropriate limitation for test-available repair.

## Weaknesses

- The main empirical advantage is strongly confounded by additional computation and model calls. Mini uses five calls, whereas Plain uses one and ordinary repair uses two; the paper itself says these are “effectiveness comparisons between nested one-, two-, and five-call systems, not efficiency or overlap-only estimates.” The only nominal-call-matched comparison is mixed-stage, and the clean prospective JavaScript result is an exact tie. Thus the paper does not establish that the proposed architecture beats a generic five-call strategy under a fair prospective comparison.

- The strongest same-call aggregate is assembled from heterogeneous and partially post hoc evidence. The 139/178 versus 132/178 comparison combines “an original post-hoc analysis,” a Go “post-primary replacement sensitivity,” and a prospective JavaScript tie. Although the paper labels this honestly, it remains the headline comparison and cannot support broad claims about repeatable superiority.

- The incremental contribution of semantic overlap is not convincingly identified. On the original tracks, TOV beats the semantic-free control by seven tasks, but the control “was frozen only after all TOV outcomes and the MAC v9 critique were known.” The two subsequent five-pair replications have wide intervals, with Python `[-2.35,+8.24]` percentage points and C++ `[-6.92,+11.54]`, while JavaScript and HumanEvalFix are ties at the relevant ceiling. The evidence supports TOV as a potentially useful route, but not as a robust causal component.

- The load-bearing role of route diversity is not sufficiently ablated. The system’s gains may arise primarily from adding multiple independently generated whole-track attempts and taking a task-wise verifier union. The authors acknowledge that “the proposed systems contribution is the enforced composition” and that “the promotion property is mechanical,” but do not provide a controlled experiment varying candidate diversity, number of candidates, route quality, or correlated versus independent candidates. Consequently, it is difficult to determine how much value comes from recursive anchoring versus simply generating more repair attempts.

- The comparison to a generic portfolio remains incomplete despite the careful controls. The non-overlap control uses a generic Critic and Direct route, but there is no broader compute-matched portfolio containing multiple generic independent repairs, alternative verifier policies, or a generic reranking/search strategy. Since the proposed union is “algebraically identical” to a task-wise max over route outputs, the scientific novelty depends heavily on whether the chosen route construction yields better candidates—not merely on the union operation.

- Generalization beyond modular, test-available repositories is only weakly supported. The paper’s formal guarantee requires “task-local declared files, no cross-task test dependency, isolated workspaces, and a stable verifier,” and the tested setting exposes “bounded official failure output between calls.” These assumptions are reasonable for the benchmark, but they substantially narrow the scope of the claim “universal answer engine” implied by the broader framing. No evidence is given for repository-level repairs with shared state, weak tests, nondeterministic tests, or unavailable external verification.

- The statistical treatment correctly notes clustering but still leaves the principal evidence underpowered for generalization. The five track-level differences are `0, +2, +3, +2, 0`, with sign `p=.125`, and the paper admits that “five sessions in each of two fixed contexts still do not estimate a broad language, model, or benchmark population.” Task-level exact tests therefore describe these realized trajectories rather than providing strong population-level evidence.

- The HumanEvalFix result contributes little discrimination between methods. Ordinary repair already reaches “164/164,” leaving every final route at the same ceiling. Moreover, the run used Python 3.13.11 instead of the predeclared 3.13.5, so the authors appropriately classify it as “a ceiling/portability evaluation, not a strict protocol-confirming endpoint.” This benchmark is useful as a boundary case but should not materially bolster the claim of superiority.

- The semantic ledger is not validated as a meaningful intermediate representation. The integrity checks “do not score the natural-language diagnoses for semantic correctness,” and the paper acknowledges that “ledger diagnoses were not independently annotated.” Therefore, the proposed four behavioral fields may be explanatory post hoc descriptions rather than demonstrated causal mechanisms.

## Questions for the Authors

1. Can you provide a prospective, compute- and token-matched comparison between Mini Artichokes and several generic five-call portfolios, with the portfolio design frozen before any target-track outcomes are observed?

2. How much of the gain remains if the system uses the same number and type of candidate calls but removes recursive anchoring, or alternatively uses anchoring without TOV and without a second heterogeneous route?

3. What is the effect of varying the number of candidate routes and their source of diversity? In particular, does Mini still help when candidates are generated with independent seeds, different models, or deliberately correlated prompts?

4. Can independent annotators evaluate the TOV ledger fields and test whether ledger-measured agreement, disagreement, or falsification quality predicts successful repairs?

5. Which assumptions in A1–A5 are necessary in practice? How does the method behave on tasks with shared files, cross-task build state, flaky tests, or incomplete/weak official test suites?

6. Can the complete artifact support an independently reproduced run under the exact frozen runtime versions, especially for the Go and HumanEvalFix protocols?

## Scores

Soundness: 3/4 — The preservation construction is sound under explicit assumptions, but causal attribution and generalization are limited.

Presentation: 4/4 — The paper is unusually clear about chronology, controls, statistical caveats, and what its results do not establish.

Significance: 3/4 — Verified task-level preservation is useful, but the demonstrated advantage over fair compute-matched alternatives is modest and uncertain.

Originality: 3/4 — The composition of immutable verified anchors, unresolved-only repair, and heterogeneous route union is well-motivated, though much of the individual machinery is familiar.

Overall recommendation: 3/6 — Borderline; the system result is promising and carefully reported, but the central comparative claim needs stronger prospective compute-matched evidence.

Confidence: 4/5 — The paper is self-contained enough to assess, although the empirical artifacts and external benchmark execution cannot be independently verified here.

## Ethics and Limitations

The paper uses public code-repair benchmarks and no human participants. It appropriately notes that failure output can reveal behavioral expectations and therefore frames the setting as “test-available program repair rather than one-shot code generation.” The main limitations are substantial: one model and runtime, few whole-track sessions, post hoc selection of important comparisons, unequal realized tokens and latency, finite and potentially incomplete test suites, and assumptions of task modularity and verifier stability. These limitations are clearly disclosed and should constrain the paper’s claims.

## Comment

I recommend borderline acceptance or rejection depending on the conference threshold. The most important issue is not presentation but identification: the paper should establish, with a fully prospective and compute-matched experiment, whether Mini Artichokes contributes beyond the generic benefit of generating and verifying more repair attempts. The preservation rule is compelling as a safety property, while the semantic-overlap route remains an interesting but currently unproven component.
