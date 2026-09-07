# ICML-Style Paper Review

## Paper and Evidence Identity

- Review method: full review — deterministic evidence audit + review panel. The panel's review is the official output; this document is its audit sidecar.
- Review Agent name/version: paper-reviewer / `sha256:9886349f92661c3c73b70f216a7038b741b47282d7624538ad207dd3fbb2d4c0`
- Review-agent spec path/hash: `review-agent-spec.md` / `sha256:08b13516a2cb0e5151c6b4dc24f98e6d191b35ee30d69ea300b2d6ff2d5a5945`
- Original paper identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:c36a3c2e1127e8f1dc98f3da0c5bd58619f18630e9ee9f3ada0f931a1079345c` / `75558` bytes
- Derived Markdown identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:c36a3c2e1127e8f1dc98f3da0c5bd58619f18630e9ee9f3ada0f931a1079345c` / `75558` bytes
- Original PDF page count: `n/a`
- Converter: `none (Markdown source)`
- Paper version/hash: `Mini_Artichokes_manuscript_v4.md` / `sha256:c36a3c2e1127e8f1dc98f3da0c5bd58619f18630e9ee9f3ada0f931a1079345c`
- Evidence bundle reviewed: none (no evidence bundle supplied)
- Frozen at (UTC): `2026-09-04T17:39:10+00:00`

## Summary

The paper, "Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair", presents a method and supporting experiments. It reports 196 quantitative result claim(s) and cites 13 prior work(s). Deterministic audit: 0 contradiction(s), 0 dishonest self-certification(s), 0 mechanical finding(s); 0 result claim(s) evidence-backed, 1138 unverifiable. Overall recommendation: 3/6 [claim-001].

## Strengths

- The paper situates its contribution against prior work (13 citation(s); related-work section present).

## Weaknesses

- The deterministic audit proved no contradiction, arithmetic error, or integrity breach; the remaining concern is limited to claims that could not be independently verified (see Questions).

## Questions for the Authors

1. For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?
2. 196 extracted result/arithmetic claim(s) could not be checked against the supplied evidence and are listed with their source lines in the Evidence Trace — could the authors provide the underlying results?

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
- Frozen review identity: `sha256:2c64c01fa73f7afc5455a54dac1a91d2abfa69b54be00d04216f39e0179e8f4d`.
- Verdict labels digest: `sha256:4bf9230faf6adea55369f604cdb22748ba630148d1cf5e3cf34d4de9bdcef131`.
- External citation snapshot digest: `sha256:01545e382bf7b0636dcadf97adfec0e438018ba58ffefc7b6167718586eab0a7`.
- Scientific judgment identity: `sha256:54ac785ee5f77b45da8cdea56f507206fd07f2191d9f22e0e44c31bbe632f5ce`.
- Review panel configuration: panel=3, model=`gpt-5.6-luna`, synthesis=area-chair.
- Panel reviewer `theorist`: prompt=`sha256:2d697180407f7fdb5a8282c9663c9ad8a3617b59bf4d48cb9292fa27e2f427c8`, response=`sha256:2fd504c14d78813ea07612361f1762a8ba2c43d1ede52d7990763c87025832c3`, status=ok.
- Panel reviewer `experimentalist`: prompt=`sha256:5624bb1088db2bfde4b7fafc31e161cbf36887950823e9f9af33329125f6eef3`, response=`sha256:8eee14eb66ab7f1a9b3b2ea602435f9fb49766f80f4c4c55cb2b73488c79f66f`, status=ok.
- Panel reviewer `scope_ablation`: prompt=`sha256:2c49e885cf3b5bca3561c8693dea9025fbc23bc70851bc65bc3cfb06bc55450b`, response=`sha256:7ea71ed8da1a00642c39186fc74764c4c4eb00cabc8149a4df369000d1ecf257`, status=ok.
- Output path: `mac_v22_balanced_luna_high_committee.md`.
- Frozen paper input: `Mini_Artichokes_manuscript_v4.md` (`sha256:c36a3c2e1127e8f1dc98f3da0c5bd58619f18630e9ee9f3ada0f931a1079345c`).
- Frozen original identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:c36a3c2e1127e8f1dc98f3da0c5bd58619f18630e9ee9f3ada0f931a1079345c`, 75558 bytes, page count=n/a).
- Frozen derived identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:c36a3c2e1127e8f1dc98f3da0c5bd58619f18630e9ee9f3ada0f931a1079345c`, 75558 bytes).
- Frozen converter: `none (Markdown source)`.
- Pre-S1 sanitation: 0 trace(s), 0 injection finding(s).
- S1 parse inventory: 42 sections, 11 tables, 900 numeric tokens with source locations.
- S3 ledger-trace: 0/0 metric-labelled values matched; 0 finding(s).
- S3 internal-consistency: 0 comparison(s), 0 finding(s).
- S3 arithmetic: 0 recomputation(s), 0 finding(s).
- S3 baseline-fairness: 0 explicit improvement claim(s), 0 finding(s).
- S3 negative-evidence: 0 discard/crash outcome(s), 0 omission finding(s).
- S3 citation-existence: 2 explicit identifier(s), 0 existence/title finding(s).
- S3 template-compliance: 1 contract trace(s), 0 finding(s).
- S3 injection-scan: 0 sanitation trace(s), 0 reviewer-directed instruction finding(s).
- S3 self-review-audit: 0 checklist item(s), 0 dishonest self-certification(s).
- S3 positioning: 13 cited reference(s), related-work section=True, 1 novelty/superiority claim(s), 0 overclaim finding(s), 0 positioning question(s).
- S5 DRAFT/GROUND: 196 candidate comment(s), 196 retained, 0 deleted, 196 criticism comment(s) converted to questions.
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
- [claim-107] **unverifiable** — paper:116 — an exploratory equal-call dual-route comparison and repeated-session union — No implemented mechanical check proves or disproves this claim. Evidence: `paper:116`.
- [claim-119] **unverifiable** — paper:128 — HumanEvalFixDocs Python tasks, which reaches a 164/164 verified ceiling and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:128`.
- [claim-127] **unverifiable** — paper:142 — End-to-end five-call effectiveness | 59/90 original; frozen Go 33/39; frozen JavaScript 47/49; complete HumanEvalFix extensions | Supported in the reported test-available setting — No implemented mechanical check proves or disproves this claim. Evidence: `paper:142`.
- [claim-128] **unverifiable** — paper:143 — Advantage over a same-call generic portfolio | Mixed-stage Aider 139/178 vs 132/178; clean JavaScript tie; complete-suite robustness checks | Positive descriptive evidence; not established prospectively across sessions — No implemented mechanical check proves or disproves this claim. Evidence: `paper:143`.
- [claim-129] **unverifiable** — paper:144 — Standalone semantic-relation effect | Original 10-versus-3 matched-control result plus newly frozen paired sessions | Productive heterogeneous route; stable superiority not established — No implemented mechanical check proves or disproves this claim. Evidence: `paper:144`.
- [claim-157] **unverifiable** — paper:180 — an indivisible task it reduces to ordinary verifier-selected best-of-multiple. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:180`.
- [claim-204] **unverifiable** — paper:237 — priority affects provenance, not the observed pass label. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:237`.
- [claim-208] **unverifiable** — paper:244 — After its model call, the experiment — No implemented mechanical check proves or disproves this claim. Evidence: `paper:244`.
- [claim-220] **unverifiable** — paper:263 — The semantic comparison is behavioral. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:263`.
- [claim-233] **unverifiable** — paper:275 — The revised final gate therefore enumerates every observed compiler, — No implemented mechanical check proves or disproves this claim. Evidence: `paper:275`.
- [claim-272] **unverifiable** — paper:313 — `/tmp/artifacts/decision_ledger.json` with exactly one record for each frozen — No implemented mechanical check proves or disproves this claim. Evidence: `paper:313`.
- [claim-278] **unverifiable** — paper:317 — They do not score the natural-language diagnoses for — No implemented mechanical check proves or disproves this claim. Evidence: `paper:317`.
- [claim-298] **unverifiable** — paper:338 — verification preserves every observed pass from either included route on the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:338`.
- [claim-300] **unverifiable** — paper:340 — The construction was formulated after final-route crossovers were observed and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:340`.
- [claim-310] **unverifiable** — paper:349 — recursive promotion--rather than a score gain over an offline union of the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:349`.
- [claim-325] **unverifiable** — paper:365 — tasks observed passing in included route `k`, and let `A` be the prior anchor — No implemented mechanical check proves or disproves this claim. Evidence: `paper:365`.
- [claim-329] **unverifiable** — paper:369 — complete state already observed to pass; no unverified merged state is — No implemented mechanical check proves or disproves this claim. Evidence: `paper:369`.
- [claim-330] **unverifiable** — paper:370 — Hence its observed task score is at least that of the prior anchor set — No implemented mechanical check proves or disproves this claim. Evidence: `paper:370`.
- [claim-346] **unverifiable** — paper:395 — We report both the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:395`.
- [claim-361] **unverifiable** — paper:413 — `counter` task reports `no tests to run`; it is retained in the denominator — No implemented mechanical check proves or disproves this claim. Evidence: `paper:413`.
- [claim-368] **unverifiable** — paper:420 — path; it occurred before any scored call, was invalidated, and the corrected — No implemented mechanical check proves or disproves this claim. Evidence: `paper:420`.
- (+1108 further extracted claim(s) — mostly unverifiable prose — omitted here for brevity; all are labelled in S2/S4 with source lines.)

## Comment

Recommendation: 3/6. No headline result is mechanically supported yet, so the recommendation stays borderline pending stronger evidence. Most useful next step for the authors — For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?

## Panel Reviews (provenance)

### Panel review 1 — theorist (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper proposes Mini Artichokes, a test-verified, task-wise recursive ensemble for program repair. It freezes solutions that pass complete task-level tests, restricts later edits to unresolved tasks, and unions passing outputs from direct and semantic-overlap repair routes. Across several complete benchmark suites, it demonstrates substantial gains over Plain and ordinary repair, but the evidence for a causal or stable advantage of semantic overlap is much weaker than the broader effectiveness claim.

## Strengths

- The central preservation mechanism is clearly specified and formally justified. The paper states: “Under A1--A5... the recursively promoted output passes every task in `A union (union_k S_k)`,” with explicit assumptions covering task modularity, isolated evaluation, complete-file copying, anchor restoration, and fail-closed behavior.

- The evaluation uses complete task inventories rather than selected examples. Table 1 reports all 90 Aider tasks, and the paper emphasizes: “No task is ranked, screened, removed, replaced, or topped up.”

- The paper separates system effectiveness from component causality unusually carefully. It explicitly concludes that “the best-supported object is Mini Artichokes as a five-call effectiveness system, not semantic overlap as an isolated causal treatment.”

- The reported system gains are large in several settings. On the original Aider tracks, Mini reaches 59/90 versus 45/90 for ordinary repair and 15/90 for Plain; on Go39 it reaches 33/39 versus 25/39 and 17/39; and on JavaScript49 it reaches 47/49 versus 42/49 and 27/49.

- The paper includes meaningful negative and replication evidence. The five-session replications yield differences of `+4,-2,+2,0,+2` for Python and `+1,-1,0,+5,-3` for C++, with both session-level intervals containing zero. It also reports that the motivating Java completion-lock result was not reproduced.

- The authors are commendably transparent about protocol deviations and post hoc analyses. For example, they state that the Go Generic call was “transport-null,” that HumanEvalFix used Python 3.13.11 rather than 3.13.5, and that the five-track equal-call result “remains mixed-stage and not token-matched.”

## Weaknesses

- The main claimed semantic contribution is not causally established. The original TOV-versus-semantic-free result is review-triggered and post hoc, while the new paired replications are inconclusive: Python has `p=.3125` with CI `[-2.35,+8.24]` pp, and C++ has `p=.6875` with CI `[-6.92,+11.54]` pp. Thus the evidence supports semantic overlap as one potentially useful route, but not as a reliable improvement over a matched structured control.

- The strongest Mini-versus-portfolio comparison is also not prospective. The paper reports 139/178 versus 132/178, but acknowledges that “the original tracks are post hoc at this layer, Go is a replacement sensitivity, and prospective JavaScript is tied.” The cleanest before-call-frozen equal-call evaluation therefore provides no overlap-specific gain: Mini and Direct∪Generic both score 47/49.

- Task-level significance is potentially misleading because all tasks within a track share a single whole-track model trajectory. Although the paper correctly notes that tests “condition on the realized calls,” the headline exact task-level result of `p=.01953` for the 8:1 five-track discordance does not provide strong evidence across independent sessions. The corresponding track-level sign test is only `p=.125`.

- The comparisons are nominally call-matched but not compute-matched. Table 8 shows TOV taking 1,422.3 seconds versus 1,392.7 for the semantic-free control, with different input and output token counts. The authors appropriately make no efficiency claim, but this leaves the mechanism comparison confounded by realized inference effort.

- The semantic-free control does not guarantee a clean intervention on semantic relations. The paper admits that it “cannot make latent model trajectories identical,” and the crossed replications demonstrate substantial trajectory variation. Consequently, differences may reflect prompt-induced reasoning changes or stochastic model behavior rather than the semantic-overlap operation itself.

- Several comparisons combine heterogeneous stages and protocols. The 139/178 aggregate includes development tracks, a transport-replacement sensitivity, and a prospective tie. The paper calls this “a descriptive inventory sensitivity,” but the abstract still foregrounds it as the main five-track comparison, which risks overstating the evidential status.

- The external verifier certifies only finite test behavior. The authors state that “byte-exact anchors preserve benchmark passes, not proof of correctness beyond those tests.” This is an important limitation because the formal preservation theorem can guarantee preservation of observed labels while offering no guarantee against shared test incompleteness or test overfitting.

- The method’s applicability depends strongly on task modularity and verifier stability. Assumptions A1–A5 exclude cross-task build state, shared files, nondeterministic tests, and weak verifiers. The paper acknowledges this, but the empirical study provides only limited evidence for transfer beyond the selected repositories and test harnesses.

## Questions for the Authors

1. Can you provide a new, preregistered multi-track evaluation in which TOV, semantic-free structured repair, and Generic Critic are compared with independently sampled sessions and token-matched budgets?

2. How much of the Mini-versus-Direct∪Generic difference remains when all routes are matched on realized output tokens, reasoning tokens, wall-clock time, and number of verifier executions?

3. Can the semantic-overlap intervention be isolated with a less prompt-sensitive design, such as supplying identical intermediate diagnoses to both final agents and varying only whether candidate relations are exposed?

4. What empirical tests support the task-boundary assumptions A1 and A2 for repositories with shared build artifacts, shared dependencies, or cross-task configuration?

5. How does Mini perform when the verifier is weaker, partially observable, nondeterministic, or unavailable, rather than the complete deterministic task verifier used here?

## Scores

Soundness: 3/4 — The preservation construction is sound under clearly stated assumptions, but the causal evidence for semantic overlap and the headline portfolio advantage is limited.

Presentation: 3/4 — The paper is unusually transparent and well organized, though the many stages, sensitivities, and caveats make the evidential hierarchy difficult to track.

Significance: 3/4 — Verified task-state preservation and recursive route union are practically useful, with substantial bounded-call gains over weak baselines, but broader impact is limited by the test-available setting.

Originality: 3/4 — The composition of immutable verified anchors, unresolved-only repair, and recursive heterogeneous promotion is a meaningful systems contribution, although its ingredients are individually familiar.

Overall recommendation: 3/6 — Borderline: promising and carefully analyzed, but the central mechanism claim requires stronger prospective and compute-controlled evidence.

Confidence: 4/5 — The paper provides enough self-contained detail to assess its claims, although the underlying runs and artifacts cannot be independently re-executed here.

## Ethics and Limitations

The use of public code-repair benchmarks and disclosure of inference costs raises no major ethical concern. The authors appropriately note that failure output can reveal behavioral expectations and that the method is test-available repair rather than ordinary one-shot generation. The main limitations are substantive: one model and runtime, correlated whole-track trajectories, mixed-stage evaluation, nominal rather than realized compute matching, finite and potentially incomplete tests, and strong dependence on task modularity and verifier stability.

## Comment

I recommend borderline acceptance pending stronger evidence. The most important issue is to separate the genuinely convincing verified-preservation mechanism from the less-established claim that semantic overlap improves repair: the clean prospective equal-call JavaScript result is a tie, and the paired replications have wide uncertainty and substantial trajectory reversals. A new preregistered, independently replicated, compute-matched comparison would substantially clarify whether semantic relations provide a reproducible gain beyond generic structured repair.

### Panel review 2 — experimentalist (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper proposes Mini Artichokes, a five-call program-repair system that preserves complete task states verified by tests, restricts later repair to unresolved tasks, and recursively unions independently generated final routes. The central system-level result is promising: it reaches 139/178 on five Aider tracks versus 132/178 for an equal-call Direct∪Generic portfolio, 112/178 for ordinary repair, and 59/178 for Plain. However, the paper’s strongest evidence supports verified multi-route repair generally, not a stable causal benefit from semantic overlap, and the main equal-call comparison is explicitly mixed-stage and post hoc.

## Strengths

- The paper identifies a clear and practically important failure mode in iterative repair: “A critic may replace a task that another attempt already solved.” Its byte-exact anchoring rule directly addresses regression, and the stated A1–A5 preservation property is logically sound under task independence, isolated verification, complete-file promotion, and fail-closed behavior.

- The experimental scope is unusually complete for this type of work. The authors retain “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” and later evaluate “all 39 official Go tasks,” “all 49” JavaScript tasks, and “all 164 official BigCode HumanEvalFixDocs Python tasks.” This substantially reduces concerns about cherry-picking within the reported tracks.

- The paper uses meaningful controls rather than relying only on Plain. In particular, the semantic-free structured control “uses the same ledger fields, counterexample-based falsification, and two audits as TOV,” while its relation field is fixed to “withheld-by-control.” This is a valuable attempt to isolate the semantic-relation component.

- The authors report failures and protocol deviations candidly. For example, “the preregistered Generic invocation was transport-null,” the HumanEvalFix run used “Python 3.13.11 rather than the protocol’s predeclared 3.13.5,” and “all C++ ledgers preserved both set and order; one C++ TOV call generated forbidden `a.out`.” Retaining these events under intention-to-treat analysis improves credibility.

- The paper’s conclusions are appropriately narrowed in several places. It explicitly states that “the best-supported object is Mini Artichokes as a five-call effectiveness system, not semantic overlap as an isolated causal treatment,” and that the clean prospective JavaScript comparison is an “exact tie.” This restraint is consistent with the evidence.

## Weaknesses

- The principal equal-call superiority claim is not prospectively established. The headline comparison, “Mini has eight task rescues and one harm” and scores 139/178 versus 132/178, combines development, extension, and sensitivity stages; Go uses a replacement run “after TOV outcomes were known,” and JavaScript is an exact tie. The paper itself reports track-level sign `p=.125`, so the aggregate does not provide strong evidence of generalization beyond the realized inventory.

- The semantic-overlap causal claim is particularly weak. The original TOV/control contrast is review-triggered and post hoc: “The semantic-free structured control was frozen only after all TOV outcomes and the MAC v9 critique were known.” The later five-pair replications produce differences `+4,-2,+2,0,+2` for Python and `+1,-1,0,+5,-3` for C++, with confidence intervals spanning both meaningful gains and harms. Thus the evidence supports semantic overlap as one potentially useful route, but not as a reliably beneficial component.

- The task-level significance tests substantially overstate the apparent amount of independent evidence if read as ordinary benchmark-level inference. “All task rows within one arm share one whole-track model call,” yet results such as `p=5.68e-14` and `p=.000122` are prominently reported over task discordances. The paper acknowledges that these tests condition on realized calls and provides cluster checks, but the effective number of independent experimental units is closer to the number of calls or tracks than the number of tasks. The underpowered track/session analyses should carry more weight in the main conclusions.

- The semantic-free ablation does not cleanly isolate semantic reasoning. The authors concede that it “cannot make latent model trajectories identical,” and that it “holds the named structured operations fixed while removing the proposed relational instruction.” Differences could therefore arise from prompt wording, attention allocation, output length, or stochastic trajectory changes rather than semantic overlap itself. The cost table reinforces this concern: TOV and the semantic-free control use different realized tokens and latency.

- The system-level gains are heavily confounded by additional computation and candidate diversity. Mini uses five model calls versus one for Plain and two for ordinary repair, and the paper states that the systems are “call-matched but not token-matched.” The recursive union itself is a deterministic maximum over route outputs; consequently, the 139/178 result demonstrates the value of a larger portfolio with verification, but does not show that the particular TOV mechanism is superior to other ways of spending the same token and wall-clock budget.

- The formal contribution is narrower than the presentation sometimes suggests. The authors acknowledge that “a minimal task-wise verifier union is algebraically identical to this promotion rule.” Under A1–A5, recursive promotion is essentially a straightforward max operation over independently passing task states. The novel scientific content therefore depends mostly on route construction and empirical complementarity, where the strongest controlled evidence is uncertain.

- The benchmark setting limits external validity. It is explicitly “a test-available program repair setting,” with “bounded official failure output,” modular task units, and finite test suites. The paper notes that anchors preserve “benchmark passes, not proof of correctness beyond those tests,” and that QuixBugs may suffer from “training contamination.” These limitations are important because the claimed general answer to repair problems may not transfer to repositories with shared build state, weak tests, unavailable tests, or nondeterministic verifiers.

## Questions for the Authors

1. Can you provide a preregistered, token-matched comparison of Mini against a same-call or same-budget generic portfolio on several previously untouched complete tracks, with the analysis unit being the whole-track session?

2. How much of the 139/178 versus 132/178 difference remains if the generic comparator receives the same output-token budget, audit requirements, and opportunity to produce two heterogeneous final routes, but without semantic-overlap instructions?

3. Can you quantify the contribution of each component through a factorial ablation: candidate diversity, immutable anchoring, TOV relations, falsification, completion locking, and recursive union?

4. For the five-pair replications, what is the prespecified estimand and power analysis for session-level superiority, and how should the paper’s conclusions change given the observed Python and C++ intervals?

5. How robust is the preservation property to cross-task build dependencies, shared generated files, nondeterministic tests, and verifier errors? Can the implementation detect violations of A1 rather than requiring them as an external assumption?

## Scores

Soundness: 3/4 — The preservation construction and integrity reporting are strong, but causal attribution and independent statistical evidence are limited.

Presentation: 3/4 — The paper is unusually transparent and carefully qualifies claims, though the extensive chronology and many overlapping endpoints make the central evidence difficult to prioritize.

Significance: 3/4 — Verified multi-route repair is practically relevant, but the demonstrated advantage is bounded to a specialized test-available setting.

Originality: 3/4 — The enforced composition of immutable task anchors, unresolved-only repair, and heterogeneous route union is a useful systems contribution, although the union rule itself is simple.

Overall recommendation: 3/6 — Borderline; the system idea is credible and the artifact discipline is impressive, but the main superiority and semantic-overlap claims require stronger prospective, budget-matched evidence.

Confidence: 3/5 — The paper is self-contained enough to assess, but the numerical results and execution artifacts cannot be independently verified here, and the effective experimental sample size is limited.

## Ethics and Limitations

The paper uses public open-source programming tasks and no human participants. It appropriately discusses licensing, test leakage risks, benchmark contamination, and the fact that finite official tests certify only observed behavior. The increased inference cost is also disclosed, including the statement that “the method increases inference compute.” The principal scientific limitations are the single-model setting, whole-track call dependence, post hoc control and route design, runtime deviations, and the mismatch between nominal call matching and realized token/latency matching.

## Comment

I recommend borderline acceptance. The most valuable contribution is the fail-closed preservation architecture, which offers a convincing way to prevent iterative repair from destroying verified task successes. The authors should make the paper’s central claim explicitly about verified multi-route effectiveness and substantially strengthen the evidence with preregistered, token-matched, session-level comparisons; at present, the data do not establish that semantic overlap itself yields a stable advantage over a carefully matched generic alternative.

### Panel review 3 — scope_ablation (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper proposes Mini Artichokes, which combines multiple whole-track repair attempts with verifier-backed, task-level anchoring and recursive promotion. The strongest claim is bounded system effectiveness: Mini reaches “59/90” on three Aider tracks and “139/178” across five tracks, but the paper appropriately acknowledges that semantic-overlap superiority is not stably established.

## Strengths

- The task-level preservation mechanism is clearly specified and supported by a useful formal property: “a complete verified task state is removed from model discretion” and, under A1–A5, promotion “passes every task in `A union (union_k S_k)`.”
- The evaluation retains complete benchmark inventories rather than selectively reporting favorable tasks. The paper emphasizes “all 90 official tasks” and later “all 178 official tasks retained,” which substantially improves credibility.
- The paper includes unusually careful controls and negative evidence. In particular, the semantic-free control shares “the same ledger fields, counterexample-based falsification, and two audits as TOV,” while the authors retain the Rust harm and failed replication outcomes.
- The authors are commendably candid about evidential limits. They explicitly state that the equal-call result “remains mixed-stage and not token-matched,” that the clean JavaScript result is a tie, and that semantic overlap is “not a reliably superior standalone policy.”
- The failure-driven design rationale is persuasive at the systems level: the paper explains how a prior manual transfer “lost a Plain-passed task,” motivating byte-exact anchoring, and how compiler-visible failures motivated completion locking.

## Weaknesses

- The central causal claim is not established prospectively. The strongest same-call aggregate is explicitly “mixed-stage,” while the only clean prospective JavaScript comparison is an exact tie: “Mini and Direct∪Generic are an exact tie: 0 rescues, 0 harms.” The new paired replications likewise yield session-level `p=.3125` and `p=.6875`, with confidence intervals spanning both meaningful benefit and harm. Thus the evidence supports one successful realized portfolio, but not a robust advantage of the proposed mechanism.
- The headline gains bundle several interventions and cannot identify the load-bearing component. The paper itself says that “Candidate diversity, external execution, the verified floor, and both final routes contribute,” while also noting that “we do not claim a new selector beyond that max operation.” The large improvements over Plain and ordinary repair therefore do not isolate recursive redundancy, semantic overlap, anchoring, or unresolved-only branching.
- The comparisons are not compute-matched. Although calls and caps are matched, “TOV uses fewer input and more output tokens than the stricter control and takes 29.6 more seconds.” The semantic-free ablation is also only a prompt-level manipulation: it “cannot make latent model trajectories identical.” This leaves open whether part of the observed difference reflects effort allocation or altered model trajectory rather than semantic relations.
- Several important results rely on post hoc or protocol-deviating procedures. The Go Generic arm was “transport-null” and replaced after TOV outcomes were known; HumanEvalFix used Python 3.13.11 rather than the frozen 3.13.5; and the replication runs had failed integrity gates, including “two ledgers” with incorrect row order and one forbidden `a.out`. These issues are disclosed, but they materially weaken claims of confirmatory evidence.
- Generalization is narrow despite the number of task rows. All semantic calls use “one model and runtime,” task outcomes arise from one whole-track call, and the study relies on modular, test-available tasks with informative failure output. The authors acknowledge that “five sessions in each of two fixed contexts still do not estimate a broad language, model, or benchmark population.”
- The preservation theorem is useful but conditional on strong assumptions that may fail in practical repositories. It requires “no cross-task test dependency,” isolated workspaces, stable verification, and task-local allowlisted files. The paper concedes that repositories with “global build state or nondeterministic tests require a coarser promotion unit,” so the claimed structural guarantee does not yet travel to general software repair.

## Questions for the Authors

1. Can you run a pre-call-frozen, token-matched comparison of Mini and Direct∪Generic over multiple independent sessions and several unseen tracks?
2. Which components are individually necessary: immutable anchoring, unresolved-only branching, recursive union, semantic relations, completion locking, or simply adding a second final route?
3. How does the method behave on repositories with shared files, cross-task dependencies, nondeterministic tests, weak tests, or no executable verifier?
4. Can you repeat the study with a different model and runtime while keeping the harness and prompts fixed, to test the claimed model-progress leverage?
5. Can the released artifact support independent reproduction of the task vectors, promotion decisions, and all reported integrity failures?

## Scores

Soundness: 3/4 — The verifier-preservation construction is well specified, but causal attribution and prospective same-call evidence remain limited.

Presentation: 3/4 — The paper is exceptionally transparent and detailed, though its many chronology-dependent evaluations make the central evidence difficult to distill.

Significance: 3/4 — The anchoring and promotion pattern is practically relevant for test-available repair, but its scope beyond this setting is not demonstrated.

Originality: 3/4 — The composition of task-level verified anchoring, unresolved-only repair, and heterogeneous route promotion is a meaningful systems contribution, though its ingredients are familiar.

Overall recommendation: 3/6 — Borderline; the paper presents a credible and carefully documented system result, but the key mechanism advantage is not yet robustly established.

Confidence: 4/5 — The paper provides sufficient methodological and numerical detail for assessment, although the empirical artifacts cannot be independently rerun here.

## Ethics and Limitations

The study uses public programming tasks and no human participants. The authors appropriately note that failure output may reveal behavioral expectations and that the method increases inference compute. Licensing and redistribution obligations are also addressed. The principal limitations are the single-model design, finite and potentially weak official tests, task modularity assumptions, runtime deviations, whole-track call correlation, post hoc chronology, and lack of stable semantic-route superiority. These limitations are stated candidly and should constrain the paper’s claims.

## Comment

I recommend borderline acceptance or rejection depending on the venue’s threshold for empirical systems contributions. The verifier-backed preservation rule is clear and potentially useful, and the complete-suite reporting is a major strength. The most important issue is to establish whether Mini’s advantage over a matched generic portfolio survives a genuinely prospective, independently replicated, compute-matched evaluation; at present, the cleanest such evidence is a tie, while the positive aggregate is explicitly mixed-stage and trajectory-dependent.
