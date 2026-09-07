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
- Frozen at (UTC): `2026-09-04T03:11:21+00:00`

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
- Scientific judgment identity: `sha256:b547b4c67870c0beb901d7b6f9948bec77fccbd6c0f830b6b8f23588ff0513f8`.
- Review panel configuration: panel=3, model=`gpt-5.6-luna`, synthesis=area-chair.
- Panel reviewer `theorist`: prompt=`sha256:1dc6429429890677fe51189a612555b197e725d570701cfc68051004c9444037`, response=`sha256:7fd15c9141d64571628d375fb7482a52d5f300f580d0d6432a8035d1811da845`, status=ok.
- Panel reviewer `experimentalist`: prompt=`sha256:e7a2e416b4ef1634453cf9a2d5653d5fa98c30cb54d8774ea08825d51e83e546`, response=`sha256:b3fe94762c257b1ef2834f2fee5de6d094334e277e753ad4b08c35e3dac2b0ac`, status=ok.
- Panel reviewer `scope_ablation`: prompt=`sha256:4297d650374fdbbc1b545b399187cb8b964d61332d1b00c2644299833c5fd91b`, response=`sha256:2841c641b2c0080d2f77b825b2d56a759bf3c0568afded037f807de81de0e1ad`, status=ok.
- Output path: `mac_v20_equal_call_reframe_luna_committee.md`.
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

This paper proposes Mini Artichokes, a test-available program-repair system that preserves complete task states passing an external verifier, branches only unresolved tasks, and combines direct and semantic-overlap repair routes. Across five Aider Polyglot tracks it reports 139/178 solved tasks versus 132/178 for a nominally equal-call Direct∪Generic portfolio, while acknowledging that this comparison is mixed-stage and that the clean prospective JavaScript result is a tie. The strongest evidence supports verified multi-route redundancy as an effective bounded-compute engineering strategy; it does not yet establish semantic overlap as a causal or reliably superior component.

## Strengths

- The central preservation mechanism is clearly specified and supported by a useful formal argument. The paper states that “a complete verified task state is removed from model discretion” and gives assumptions A1–A5 under which recursive promotion “copies either its prior anchored state or one complete state already observed to pass.” This is a meaningful structural guarantee for modular, test-available repair.

- The evaluation retains complete benchmark tracks rather than selecting favorable tasks. The authors explicitly retain “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” followed by all 39 Go and 49 JavaScript tasks. The full-denominator reporting, starter baselines, task-level outcomes, and byte-audit details make the empirical claims unusually traceable.

- The paper distinguishes system effectiveness from component causality. It directly says that the “best-supported object is Mini Artichokes as a five-call effectiveness system, not semantic overlap as an isolated causal treatment.” This restraint is appropriate given the evidence.

- The results show substantial effectiveness over simple baselines in the reported setting: Mini reaches “59/90” on the original Aider tracks, “33/39” on Go, and “47/49” on JavaScript, compared with Plain’s “15/90,” “17/39,” and “27/49,” respectively. These comparisons are not compute-matched, but they demonstrate that the complete procedure can be practically useful.

- The authors include meaningful negative and integrity evidence. They retain the Rust `fizzy` harm, report that one Generic Go invocation was “transport-null,” and state that “no call was rerun.” The discussion of the earlier manual anchor-loss failure and the strict Java20 gate provides a plausible motivation for byte-exact anchoring and for avoiding hard consensus.

- The paper is commendably candid about uncertainty. It reports that the two five-pair replications “do not establish session-level superiority at `.05`,” that JavaScript is an exact equal-call tie, and that HumanEvalFix is ceiling-tied because ordinary repair already reaches “164/164.”

## Weaknesses

- The headline equal-call advantage is not a clean prospective causal comparison. The reported “139/178 versus 132/178” combines “development, prospective, extension, and sensitivity stages”; Go uses a “separately frozen same-input replacement” after TOV outcomes were known; and the only clean prospective equal-call track, JavaScript, is tied at “47/49.” Thus the strongest aggregate comparison is descriptive rather than confirmatory.

- The core semantic-overlap claim is weakly identified. The semantic-free control was “frozen only after all TOV outcomes and the MAC v9 critique were known,” and the paper admits that the significant 90-task contrast is “review-triggered and post hoc.” More importantly, the control matches named prompt operations but not latent reasoning or realized compute. The authors themselves state that this “natural-language ablation cannot make latent model trajectories identical.” Consequently, the +7-task difference cannot be cleanly attributed to semantic relations rather than prompt-induced attention, output length, or stochastic trajectory effects.

- Much of the system gain is inseparable from additional calls and candidate diversity. Mini is compared with Plain and ordinary repair using five versus one or two calls, and the paper explicitly describes these as “nested, additional-compute comparisons.” The recursive union is also mathematically just task-wise maximum selection over route outcomes: “a minimal task-wise verifier union is algebraically identical to this promotion rule.” The novel contribution is therefore primarily a careful composition and protocol, while the empirical incremental gain over a strong equal-call alternative remains uncertain.

- The statistical evidence risks overstating precision because tasks within a track are generated by a single whole-track model call. Although the paper acknowledges this and reports track-level signs, the aggregate task-level significance—such as `p=.01953` for the 178-task comparison—conditions on a small number of realized trajectories. The relevant independent units are closer to tracks or sessions, where the evidence is only three positive versus two tied tracks (`p=.125`) and replication means have wide intervals.

- The formal guarantee depends on restrictive assumptions that are not fully demonstrated for the principal Aider setting. The property requires that “the benchmark is partitioned into task units whose declared solution files and verifier do not cross task boundaries,” along with stable, isolated verification. The paper’s audits support these conditions for the newer packaged tracks, but also concedes they “do not prove verifier stability outside the observed reruns.” The result may therefore be less universal than the title and framing suggest.

- The semantic ledger is not an evaluated scientific measurement. TOV requires fields for “fault location,” “violated requirement or invariant,” “smallest counterexample class,” and “edit intent,” but “integrity checks … do not score the natural-language diagnoses for semantic correctness,” and “ledger diagnoses were not independently annotated.” The paper consequently cannot show that semantic overlap itself was correctly detected or that the proposed fields mediate the observed gains.

- Generality remains limited. The experiments use “one model and runtime,” five Aider language tracks, and one HumanEvalFix configuration, all in a test-available setting. The authors do not compare against a full contemporary repository repair agent such as KIRA and explicitly make “no state-of-the-art claim.” This is reasonable, but it limits the significance of the universal framing.

## Questions for the Authors

1. Can you provide a preregistered, token- and latency-matched comparison of Mini against Direct∪Generic across multiple independent sessions and complete tracks, with the route prompts randomized or counterbalanced?

2. What is the incremental effect of semantic relations after controlling for output length, reasoning tokens, and prompt size? In particular, can the semantic-free control be implemented as a nonlinguistic or mechanically enforced intervention rather than a natural-language instruction?

3. How often do A1–A5 fail on realistic repositories with shared files, global build state, or nondeterministic tests, and what is the resulting preservation behavior when the promotion unit must be coarsened?

4. Can independent annotators score the TOV ledger fields and test whether ledger quality predicts rescues? Without this, what evidence distinguishes semantic-overlap reasoning from generic additional deliberation?

5. How does Mini compare with a simple verifier union of independently generated direct candidates under the same total token and wall-clock budget? This would clarify whether the structured routes add value beyond diversity plus task-wise selection.

## Scores

Soundness: 3/4 — The preservation property is well motivated and the experiments are carefully caveated, but semantic causality and independent statistical evidence remain limited.

Presentation: 4/4 — The paper is unusually explicit about protocols, chronology, denominators, invalid runs, and claim boundaries.

Significance: 3/4 — Verified multi-route repair is practically relevant, but the benchmark scope and compute requirements limit the broader claim.

Originality: 3/4 — The composition of immutable task anchors, unresolved-only branching, and recursive verifier promotion is a useful systems design, though its selection operation is mechanically simple.

Overall recommendation: 3/6 — Borderline; the system result is promising, but the main comparative claim is not yet prospectively or independently established.

Confidence: 4/5 — The paper is sufficiently self-contained to assess, though the review cannot independently verify the released artifacts and exact runs.

## Ethics and Limitations

The paper uses public coding benchmarks and no human participants. It appropriately notes that failure output may reveal behavioral expectations and that the method increases inference compute. The main limitations are substantial but honestly stated: one model/runtime, correlated candidate errors, whole-track calls, limited independent sessions, post hoc chronology for several comparisons, non-token-matched systems, finite test specifications, possible verifier and task-boundary assumptions, and a runtime deviation in HumanEvalFix. These limitations should be reflected in the title and claims if the work is accepted.

## Comment

I recommend borderline acceptance/revision depending on the venue’s tolerance for systems evidence. The most important issue is causal identification: the paper convincingly shows that verified preservation combined with multiple repair routes can improve bounded-compute task scores, but it does not yet show that semantic overlap is responsible for the improvement or that the equal-call aggregate advantage will replicate prospectively. A stronger matched, independently repeated evaluation—ideally with a mechanically controlled semantic ablation—would substantially improve the paper.

### Panel review 2 — experimentalist (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

The paper presents Mini Artichokes, a five-call code-repair system that generates multiple whole-track candidates, freezes task-level solutions that pass official tests, and applies two additional repair routes only to unresolved tasks. Its main empirical claim is system-level effectiveness: 139/178 Aider tasks versus 132/178 for a same nominal-call Direct∪Generic portfolio, with larger gains over Plain and ordinary repair. The paper appropriately distinguishes this claim from the narrower claim that semantic-overlap reasoning itself is causally beneficial.

## Strengths

- The system has a clear and technically meaningful preservation mechanism. The paper states that “a complete verified task state is removed from model discretion” and defines a concrete A1–A5 contract involving task-local files, isolated verification, complete-file promotion, anchor restoration, and fail-closed behavior.

- The evaluation retains complete benchmark tracks rather than selecting favorable tasks. It reports “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” followed by complete Go39 and JavaScript49 evaluations.

- The paper reports strong, traceable improvements over simple baselines. On the original Aider tracks, Mini solves “59/90,” compared with “15/90” for Plain and “45/90” for ordinary repair. On JavaScript, it reaches “47/49” versus “27/49” for Plain and “42/49” for ordinary repair.

- The authors are commendably candid about what the evidence does not establish. They explicitly write that semantic overlap is “not established” as a “repeatable standalone semantic-relation effect,” and that the five-track comparison is “mixed-stage and not token-matched.”

- The paper includes useful negative and boundary evidence. For example, it reports that the strict Java20 gate solved “5/20 tasks versus 7/20 for matched structured repair,” and that HumanEvalFix reaches a ceiling where “ordinary repair already reaches the same ceiling.”

- The analysis accounts for cluster dependence and session variance rather than treating all task-level observations as independent population samples. The five-session replications report wide intervals, including Python `[-2.35,+8.24]` pp and C++ `[-6.92,+11.54]` pp.

## Weaknesses

- The strongest claimed advantage is not established by a clean prospective, compute-matched comparison. The headline equal-call result, “139/178 versus 132/178,” combines “an original post-hoc analysis,” a Go replacement run performed after TOV outcomes were known, and a clean JavaScript tie. The paper itself acknowledges that “JavaScript is the only clean prospective equal-call track and is a tie.” Thus the central advantage is suggestive but vulnerable to chronology and selection effects.

- The incremental contribution of semantic overlap is weakly identified. The original TOV/control contrast is significant at the task level (`p=.01953125`), but the semantic-free control “was frozen only after all TOV outcomes and the MAC v9 critique were known.” The two prospective five-session replications do not establish superiority: Python has mean `+1.2/34` with `p=.3125`, and C++ has mean `+0.4/26` with `p=.6875`.

- Much of the system gain is attributable to additional model calls and verifier-based best-of-route selection, not to the proposed semantic mechanism. The paper states that “candidate diversity, external execution, the verified floor, and both final routes contribute,” while the formal section concedes that the recursive union is “algebraically identical” to a task-wise verifier union. This makes the novelty primarily an execution protocol and composition rule, whose advantage over simpler multi-attempt verifier selection is not fully isolated.

- The nominal-call matching is not sufficient to support an efficiency or resource-normalized claim. Table 8 shows TOV taking “1,422.3” seconds versus “1,233.6” for Generic and “1,392.7” for the semantic-free control. The authors correctly disclaim efficiency superiority, but the paper still uses the equal-call comparison as its fairest comparison despite substantial realized-compute and latency differences.

- The experimental scope is narrower than the broad systems framing suggests. “Every semantic call uses `gpt-5.6-luna` at medium reasoning,” and the authors state that “other models may produce different candidate diversity and overlap signals.” There is no multi-model or multi-seed evaluation demonstrating that the mechanism generalizes beyond one model/runtime trajectory.

- The baselines are mostly prompt-level internal variants rather than strong contemporary repair systems. The paper acknowledges that Graph, ordinary repair, and the named methods are “bounded prompt-level realizations” and that it “do[es] not empirically compare a full contemporary repository agent such as KIRA.” This limits the significance of the reported gains relative to the broader program-repair literature.

- The semantic analysis is not independently validated. The paper states that “ledger diagnoses were not independently annotated,” and the proposed interface-ambiguity pattern was “formulated after the nine discordant tasks were known.” Consequently, the claimed explanatory account is plausible but post hoc and not yet a measurable semantic-overlap construct.

## Questions for the Authors

1. Can you provide a prospective, multi-track comparison in which Mini and Direct∪Generic are frozen before any route outcomes, with identical model, token, wall-clock, and evaluator budgets rather than only equal call counts?

2. What is the minimal system that achieves the reported 139/178 result: candidate generation plus a verifier union, TOV plus Direct, or recursive promotion specifically? Please report factorial ablations that isolate these components.

3. How sensitive are the results to the fixed priority rules, route order, prompt wording, and model randomness? In particular, would repeated complete-track runs with newly generated `P/G/R` candidates preserve the observed advantage?

4. Can independent annotators label the TOV ledgers for fault location, invariant, counterexample class, and edit intent, and can those labels predict rescues or harms?

5. How does Mini compare against a simpler verifier-selected portfolio with the same number of independently generated repair attempts and the same total evaluation budget?

## Scores

Soundness: 3/4 — The construction and reported measurements are coherent, but causal isolation of semantic overlap and the clean equal-call system advantage remain limited.

Presentation: 4/4 — The paper is unusually explicit about chronology, denominators, protocol failures, statistical units, and limitations.

Significance: 3/4 — Verified preservation and unresolved-only branching are useful systems ideas with promising code-repair results, but broader practical significance is not yet demonstrated.

Originality: 3/4 — The particular composition of immutable task anchors, heterogeneous routes, and recursive verifier promotion is distinctive, although its core selection operation is mechanically simple.

Overall recommendation: 3/6 — Borderline; the system result is credible and useful, but the principal comparative and semantic claims need cleaner prospective and resource-matched evidence.

Confidence: 4/5 — The paper provides enough self-contained methodological and numerical detail for a substantive assessment, though the underlying artifacts and runs cannot be independently checked here.

## Ethics and Limitations

The paper uses public programming tasks and reports no human-participant concerns. It appropriately notes that test feedback can reveal behavioral expectations and that the method increases inference compute. The main scientific limitations are the reliance on one model/runtime, whole-track call clustering, post hoc chronology for several comparisons, unequal realized compute despite equal call counts, limited benchmark and language coverage, weak external-baseline comparison, and the fact that passing finite test suites does not establish correctness beyond those tests. The authors state these limitations candidly, particularly the transport-null Go call and the Python runtime deviation.

## Comment

I recommend borderline acceptance/rejection pending stronger evidence. The most important issue is not presentation but attribution: the paper should establish, under a fully prospective and resource-matched protocol, whether Mini’s advantage comes from its specific recursive heterogeneous design rather than simply from adding more repair attempts and taking the verifier-wise union of their successes.

### Panel review 3 — scope_ablation (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

The paper proposes Mini Artichokes, a five-call program-repair system that preserves complete task states passing an external verifier, restricts later edits to unresolved tasks, and recursively unions passing outputs from direct and semantic-overlap repair routes. Across complete Aider tracks and HumanEvalFixDocs, it reports substantial gains over Plain and ordinary repair, but the evidence for a causal benefit from semantic overlap is mixed and largely exploratory.

## Strengths

- The central preservation mechanism is clearly specified and formally motivated: “a complete verified task state is removed from model discretion, only unresolved units are branched, and passing states from heterogeneous routes are recursively promoted.” Under assumptions A1–A5, the paper gives a coherent test-label preservation property.

- The evaluation retains complete inventories rather than selecting favorable tasks. For example, the paper evaluates “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” and later evaluates “all 39 official Go tasks” and “all 49” JavaScript tasks.

- The system-level results are strong within the test-available setting. Mini Artichokes achieves “139/178 (78.1%)” across five Aider tracks versus “112/178 (62.9%)” for ordinary repair and “59/178 (33.1%)” for Plain.

- The study includes meaningful negative and boundary evidence. It reports that JavaScript is an exact tie against the equal-call portfolio (“47/49” for both), HumanEvalFix reaches a ceiling where “ordinary repair already reaches the same ceiling,” and QuixBugs is “Plain passed 40/40.”

- The authors are unusually candid about causal limitations. They explicitly state that the equal-call result is “mixed-stage and not token-matched,” that the recursive composition “was chosen after observing crossovers,” and that the semantic-relation effect is “not established.”

- The component comparison is better controlled than a Plain-only baseline. The semantic-free control shares “the same ledger fields, counterexample-based falsification, and two audits,” while withholding candidate relations, which is a useful attempt to isolate the proposed instruction.

## Weaknesses

- The strongest empirical comparison is not prospectively or cleanly compute-matched. The five-track result of “139/178 versus 132/178” combines exploratory original tracks, a post-primary Go replacement, and a prospective JavaScript tie. Moreover, the paper acknowledges that the systems are “not token-matched.” Thus the headline advantage cannot establish that Mini’s distinctive mechanism improves accuracy under equal resources.

- Recursive union makes the main system gain partly mechanical and dependent on an additional route. The paper itself states: “Given the same stored route outputs and task tests, a minimal task-wise verifier union is algebraically identical to this promotion rule.” The contribution is therefore primarily a robust composition and execution protocol, while the empirical superiority over alternative five-call portfolios is weaker than the headline system numbers suggest.

- Evidence for semantic overlap as a load-bearing component is inconsistent. On the original 90 tasks, TOV beats the semantic-free control “58/90 versus 51/90,” but the five-session replications have means of only “+1.2/34” and “+0.4/26,” with wide confidence intervals. JavaScript gives an exact tie, and Go gives only “33/39 versus 31/39” with `p=.3125`.

- The semantic-free ablation does not fully isolate semantic relations. The paper concedes that it matches “named instructions, not latent reasoning or exact realized compute,” and that “prompt wording can change attention and trajectory.” Since TOV uses different instructions, output requirements, and token profiles, the causal interpretation remains confounded by prompt-induced behavior.

- The evaluation has substantial protocol-stage dependence. Rust is described as a development track, the semantic-free control was designed after TOV results and reviewer feedback, the recursive composition was selected after observing crossovers, and the Go Generic arm required a post hoc replacement. These disclosures are commendable, but they substantially reduce the strength of the aggregate statistical claims.

- Generalization is narrow. The experiments use “one model and runtime,” task-level external tests, modular repositories, and failure traces. The authors appropriately state that the method is inappropriate “when tests are unavailable or too weak,” but the paper does not demonstrate performance on less modular repositories, noisy verifiers, other models, or genuinely open-ended repair.

- The statistical unit is weaker than the apparent number of task observations suggests. “Each task vector is generated inside one whole-track call,” so task-level tests condition on a small number of realized model trajectories. The paper reports this caveat, but the five-track sign result (`p=.125`) makes clear that population-level generalization is not established.

## Questions for the Authors

1. Can you provide a preregistered, token- and latency-matched comparison between Mini Artichokes and Direct∪Generic across multiple fresh complete tracks, with the route-selection rule fixed before any outcomes are observed?

2. What is the incremental effect of recursive promotion itself when the same final-route outputs are evaluated with and without anchor restoration, and how does this compare with a simple offline per-task verifier union?

3. Can you replace the natural-language semantic-free ablation with a control matched for output schema, prompt length, expected deliberation, and realized tokens, so that the semantic-relation instruction is the principal manipulated variable?

4. How does Mini Artichokes perform with different models, model temperatures/seeds, or repositories where solution files and tests have cross-task dependencies?

5. Which additional-call and evaluator costs are required in practice, and does the system remain preferable under a fixed wall-clock, token, or monetary budget rather than a nominal call cap?

## Scores

Soundness: 3/4 — The mechanism and within-setting measurements are carefully documented, but causal and population-level claims remain limited by post hoc design choices and compute mismatch.

Presentation: 3/4 — The paper is unusually transparent and well organized, though the many evidence stages and caveats make the central claim difficult to disentangle.

Significance: 3/4 — Verified preservation and unresolved-only branching are practically relevant for test-available repair, but the demonstrated scope is narrower than general program repair.

Originality: 3/4 — The recursive verified-union composition and overlap-as-falsification framing are plausible contributions, although their ingredients are largely assembled from known ideas.

Overall recommendation: 3/6 — Borderline; the system result is promising, but the main mechanistic claim and broad generalization are not yet established.

Confidence: 4/5 — The paper provides enough self-contained detail to assess the argument and evidence, although the underlying artifacts and runs cannot be independently checked here.

## Ethics and Limitations

The paper uses public programming tasks and reports no human-participant concerns. It appropriately discusses test leakage risks, licensing, inference cost, finite-test correctness, nondeterministic verifiers, runtime deviations, and the distinction between benchmark pass preservation and semantic correctness. The reported use of private tests and bounded failure output is relevant to reproducibility and potential benchmark overfitting.

## Comment

I recommend borderline acceptance/rejection depending on the conference threshold. The most important issue is to establish whether Mini Artichokes provides a reproducible advantage under a genuinely fixed resource and prospectively frozen evaluation, rather than primarily benefiting from additional heterogeneous routes and a mechanically favorable verifier union.
