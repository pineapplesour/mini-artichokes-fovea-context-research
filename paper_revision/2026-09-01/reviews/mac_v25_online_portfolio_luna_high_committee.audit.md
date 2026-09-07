# ICML-Style Paper Review

## Paper and Evidence Identity

- Review method: full review — deterministic evidence audit + review panel. The panel's review is the official output; this document is its audit sidecar.
- Review Agent name/version: paper-reviewer / `sha256:9886349f92661c3c73b70f216a7038b741b47282d7624538ad207dd3fbb2d4c0`
- Review-agent spec path/hash: `review-agent-spec.md` / `sha256:08b13516a2cb0e5151c6b4dc24f98e6d191b35ee30d69ea300b2d6ff2d5a5945`
- Original paper identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:fd5750d6ec77cab63ce71afaf852feb65759a8d12b15256b32fb79457bdd2625` / `60967` bytes
- Derived Markdown identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:fd5750d6ec77cab63ce71afaf852feb65759a8d12b15256b32fb79457bdd2625` / `60967` bytes
- Original PDF page count: `n/a`
- Converter: `none (Markdown source)`
- Paper version/hash: `Mini_Artichokes_manuscript_v4.md` / `sha256:fd5750d6ec77cab63ce71afaf852feb65759a8d12b15256b32fb79457bdd2625`
- Evidence bundle reviewed: none (no evidence bundle supplied)
- Frozen at (UTC): `2026-09-04T18:05:56+00:00`

## Summary

The paper, "Mini Artichokes: Verifier-Gated Recursive Portfolios for Test-Available Program Repair", presents a method and supporting experiments. It reports 165 quantitative result claim(s) and cites 13 prior work(s). Deterministic audit: 0 contradiction(s), 0 dishonest self-certification(s), 0 mechanical finding(s); 0 result claim(s) evidence-backed, 908 unverifiable. Overall recommendation: 3/6 [claim-001].

## Strengths

- The paper situates its contribution against prior work (13 citation(s); related-work section present).

## Weaknesses

- The deterministic audit proved no contradiction, arithmetic error, or integrity breach; the remaining concern is limited to claims that could not be independently verified (see Questions).

## Questions for the Authors

1. For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?
2. 165 extracted result/arithmetic claim(s) could not be checked against the supplied evidence and are listed with their source lines in the Evidence Trace — could the authors provide the underlying results?

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
- Frozen review identity: `sha256:3a3fcbfa1ea01c0c7aa339a930c504247a4052a77865f23d70e16541ff4b119e`.
- Verdict labels digest: `sha256:cb68dbe8f71bf215c4e8c27088c31ba4cc4494d1648fb6c20e2f5fc91b829ccb`.
- External citation snapshot digest: `sha256:01545e382bf7b0636dcadf97adfec0e438018ba58ffefc7b6167718586eab0a7`.
- Scientific judgment identity: `sha256:8f5e86ca264c2827b281dccac5bc0816a4b4afceda2666232fdd6bcfa9f1f9a2`.
- Review panel configuration: panel=3, model=`gpt-5.6-luna`, synthesis=area-chair.
- Panel reviewer `theorist`: prompt=`sha256:82753fca31bcb1c3c94516dc6a55385fb9c1f8c4553396777c568e8f42c0f01d`, response=`sha256:cdfab4b95cb23782ec24d6f413f0ddd5644cf902d35fa0c95e86e3b8b30d20e0`, status=ok.
- Panel reviewer `experimentalist`: prompt=`sha256:4dce72fc92331b2b44797a0d2eb8fb5cf68e8b075b7bde6c8f2b2143eb4234ae`, response=`sha256:90d23c9233846c7516bdcc0a27011f7e88da4954995c20b66701adaa62bd8fa5`, status=ok.
- Panel reviewer `scope_ablation`: prompt=`sha256:59c8786fb916f1f182535d5d35ced2cedb22cdda878c8514610bdd4aabddd2a2`, response=`sha256:292e5a6c74312d706200a11342f4f9f3ed9cb1c18f1c3a470d2dd9785ff3c218`, status=ok.
- Output path: `mac_v25_online_portfolio_luna_high_committee.md`.
- Frozen paper input: `Mini_Artichokes_manuscript_v4.md` (`sha256:fd5750d6ec77cab63ce71afaf852feb65759a8d12b15256b32fb79457bdd2625`).
- Frozen original identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:fd5750d6ec77cab63ce71afaf852feb65759a8d12b15256b32fb79457bdd2625`, 60967 bytes, page count=n/a).
- Frozen derived identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:fd5750d6ec77cab63ce71afaf852feb65759a8d12b15256b32fb79457bdd2625`, 60967 bytes).
- Frozen converter: `none (Markdown source)`.
- Pre-S1 sanitation: 0 trace(s), 0 injection finding(s).
- S1 parse inventory: 40 sections, 10 tables, 750 numeric tokens with source locations.
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
- S5 DRAFT/GROUND: 165 candidate comment(s), 165 retained, 0 deleted, 165 criticism comment(s) converted to questions.
- S2/S4 claim verdicts:
- [claim-015] **unverifiable** — paper:17 — The same frozen system reaches 33/39 on Go versus — No implemented mechanical check proves or disproves this claim. Evidence: `paper:17`.
- [claim-019] **unverifiable** — paper:21 — Mini improves on Plain (157/164) and reaches the same ceiling as ordinary — No implemented mechanical check proves or disproves this claim. Evidence: `paper:21`.
- [claim-020] **unverifiable** — paper:22 — These are bounded-call effectiveness results, not — No implemented mechanical check proves or disproves this claim. Evidence: `paper:22`.
- [claim-025] **unverifiable** — paper:27 — That comparison is mixed-stage; the only clean — No implemented mechanical check proves or disproves this claim. Evidence: `paper:27`.
- [claim-035] **unverifiable** — paper:36 — A one-task Java completion-lock result also does not repeat in five — No implemented mechanical check proves or disproves this claim. Evidence: `paper:36`.
- [claim-045] **unverifiable** — paper:49 — can improve over one-pass generation, yet their composition is fragile. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:49`.
- [claim-055] **unverifiable** — paper:59 — hypotheses improve one final repair route. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:59`.
- [claim-060] **unverifiable** — paper:64 — **semantic-relation value:** whether comparing what failed candidates mean — No implemented mechanical check proves or disproves this claim. Evidence: `paper:64`.
- [claim-061] **unverifiable** — paper:65 — improves repair beyond a final agent with the same candidates, evidence, — No implemented mechanical check proves or disproves this claim. Evidence: `paper:65`.
- [claim-090] **unverifiable** — paper:95 — **RQ1:** Does recursive verified redundancy improve Plain, Graph, and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:95`.
- [claim-097] **unverifiable** — paper:104 — secondary component analysis; acceptance of the system result does not require — No implemented mechanical check proves or disproves this claim. Evidence: `paper:104`.
- [claim-110] **unverifiable** — paper:120 — prospective complete-track and repeated-session analyses that establish the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:120`.
- [claim-116] **unverifiable** — paper:130 — Primary | End-to-end bounded-call effectiveness | 59/90 original; frozen Go 33/39; frozen JavaScript 47/49; complete HumanEvalFix extension | Supported in the reported test-available setting — No implemented mechanical check proves or disproves this claim. Evidence: `paper:130`.
- [claim-117] **unverifiable** — paper:131 — Secondary sensitivity | Advantage over a same-call generic portfolio | Mixed-stage Aider 139/178 vs 132/178; clean JavaScript tie | Descriptive; not a primary superiority claim — No implemented mechanical check proves or disproves this claim. Evidence: `paper:131`.
- [claim-118] **unverifiable** — paper:132 — Secondary component analysis | Standalone semantic-relation effect | Original 10-versus-3 matched-control result plus newly frozen paired sessions | Productive heterogeneous route; stable superiority not established — No implemented mechanical check proves or disproves this claim. Evidence: `paper:132`.
- [claim-146] **unverifiable** — paper:168 — an indivisible task it reduces to ordinary verifier-selected best-of-multiple. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:168`.
- [claim-193] **unverifiable** — paper:225 — priority affects provenance, not the observed pass label. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:225`.
- [claim-197] **unverifiable** — paper:232 — After its model call, the experiment — No implemented mechanical check proves or disproves this claim. Evidence: `paper:232`.
- [claim-209] **unverifiable** — paper:251 — The semantic comparison is behavioral. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:251`.
- [claim-222] **unverifiable** — paper:263 — The revised final gate therefore enumerates every observed compiler, — No implemented mechanical check proves or disproves this claim. Evidence: `paper:263`.
- [claim-261] **unverifiable** — paper:301 — `/tmp/artifacts/decision_ledger.json` with exactly one record for each frozen — No implemented mechanical check proves or disproves this claim. Evidence: `paper:301`.
- [claim-267] **unverifiable** — paper:305 — They do not score the natural-language diagnoses for — No implemented mechanical check proves or disproves this claim. Evidence: `paper:305`.
- [claim-287] **unverifiable** — paper:326 — verification preserves every observed pass from either included route on the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:326`.
- [claim-289] **unverifiable** — paper:328 — The construction was formulated after final-route crossovers were observed and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:328`.
- [claim-317] **unverifiable** — paper:356 — tasks observed passing in included route `k`, and let `A` be the prior anchor — No implemented mechanical check proves or disproves this claim. Evidence: `paper:356`.
- [claim-321] **unverifiable** — paper:360 — complete state already observed to pass; no unverified merged state is — No implemented mechanical check proves or disproves this claim. Evidence: `paper:360`.
- [claim-322] **unverifiable** — paper:361 — Hence its observed task score is at least that of the prior anchor set — No implemented mechanical check proves or disproves this claim. Evidence: `paper:361`.
- [claim-338] **unverifiable** — paper:386 — We report both the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:386`.
- [claim-353] **unverifiable** — paper:404 — `counter` task reports `no tests to run`; it is retained in the denominator — No implemented mechanical check proves or disproves this claim. Evidence: `paper:404`.
- [claim-360] **unverifiable** — paper:411 — path; it occurred before any scored call, was invalidated, and the corrected — No implemented mechanical check proves or disproves this claim. Evidence: `paper:411`.
- (+878 further extracted claim(s) — mostly unverifiable prose — omitted here for brevity; all are labelled in S2/S4 with source lines.)

## Comment

Recommendation: 3/6. No headline result is mechanically supported yet, so the recommendation stays borderline pending stronger evidence. Most useful next step for the authors — For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?

## Panel Reviews (provenance)

### Panel review 1 — theorist (accepted)

# Review: Mini Artichokes: Verifier-Gated Recursive Portfolios for Test-Available Program Repair

## Summary

The paper presents Mini Artichokes, a verifier-gated portfolio for test-available program repair. It freezes complete task states that pass the official verifier, restricts later repairs to unresolved tasks, and recursively unions passing outputs from direct and overlap-aware routes. The system shows substantial gains over one- and two-call baselines, but evidence for the specific semantic-overlap mechanism and for superiority under controlled compute remains limited.

## Strengths

- The central preservation mechanism is clearly specified and supported by a convincing construction: “a complete verified task state is removed from model discretion,” while “only unresolved units are branched.” Under assumptions A1–A5, the paper correctly argues that promotion copies a complete previously passing task state rather than an unverified merge.

- The empirical system result is substantial within the stated test-available setting. On the original tracks, “Mini Artichokes solves 59/90,” compared with “45/90 for ordinary repair and 15/90 for one-call Plain.” The frozen Go and JavaScript evaluations provide additional complete-track evidence: “33/39 on Go” and “47/49 on” JavaScript.

- The evaluation retains complete benchmark tracks rather than selecting convenient tasks. Table 1 reports all “90 official tasks,” and the paper states that “No task is ranked, screened, removed, replaced, or topped up.”

- The authors distinguish system effectiveness from causal component claims. They explicitly state that the “best-supported object is Mini Artichokes as a five-call effectiveness system, not semantic overlap as an isolated causal treatment,” and acknowledge that the clean prospective JavaScript comparison is a tie.

- The recursive union is motivated by a meaningful failure mode and has a plausible formal basis. In the repeated sessions, the union reaches “210/300 task-session passes, compared with 198 for TOV alone and 190 for the semantic-free route,” illustrating how a verifier can retain route-specific successes without requiring model voting.

- The paper reports important operational limitations rather than hiding them, including that the portfolios “match nominal calls and caps but not realized tokens or time” and that anchors preserve “observed test labels, not correctness beyond those tests.”

## Weaknesses

- The strongest headline comparisons are substantially confounded by additional model calls and computation. Mini uses five calls, whereas ordinary repair uses two and Plain uses one; the paper itself says these are “effectiveness comparisons between nested one-, two-, and five-call systems.” Thus the results establish the value of a larger bounded test-time budget, but do not isolate the value of the proposed architecture.

- The equal-call comparison is not a clean prospective experiment. The paper reports 139/178 versus 132/178 against Direct∪Generic, but acknowledges that the comparison is “mixed-stage,” that “the original tracks are post hoc,” that Go uses a replacement after the original failure, and that “prospective JavaScript is tied.” This substantially weakens the claim that Mini itself has a robust advantage over a same-budget generic portfolio.

- The causal evidence for semantic overlap is not sufficiently controlled. The semantic-free ablation “cannot equalize latent trajectories or realized compute,” and the initial seven-task advantage was “designed after the original outcomes.” Moreover, the paper reports that five new Java pairs showed “no wins, two losses, three ties.” The evidence supports overlap as a plausible route for generating complementary attempts, but not as a reliable causal improvement.

- The statistical treatment risks overstating precision because all tasks within a track share one model invocation. The authors correctly note that task-level tests “condition on realized calls,” but the reported very small task-level p-values should not be interpreted as broad population-level evidence. The number of independent experimental units is closer to tracks or sessions, where evidence is much weaker: for example, the equal-call track sign test is reported as “p=.125.”

- The verifier-based preservation theorem is conditional and narrower than the practical narrative may suggest. It requires “task units whose declared solution files and verifier do not cross task boundaries,” isolated workspaces, stable tests, and complete allowlisted copying. These assumptions are reasonable for the selected benchmarks but limit applicability to repositories with shared build state, cross-task dependencies, flaky tests, or weak tests. The paper itself concedes that recursive promotion “does not guarantee correctness beyond those tests.”

- The method is evaluated almost entirely with one model and closely related code-repair settings. “All semantic calls use one model and runtime,” while HumanEvalFix C++ reuses “the same underlying tasks.” The JavaScript tie, HumanEvalFix ceiling, and QuixBugs ceiling therefore provide useful boundaries but limited evidence for broad generalization beyond the benchmark regime.

- The semantic diagnosis is not independently validated. “Ledger diagnoses are not independently labelled,” so it remains unclear whether the claimed behavioral overlap fields genuinely improve reasoning or merely correlate with a longer, more structured prompt and more output tokens.

## Questions for the Authors

1. Can you provide a prospective, preregistered, equal-token or equal-latency comparison between Mini Artichokes and a generic verifier-gated portfolio on several complete, previously untouched tracks?

2. How much of Mini’s gain remains when the direct and overlap-aware routes receive identical output-token budgets and wall-clock limits, rather than only identical nominal call counts?

3. Can you perform a factorial ablation separating recursive promotion from the overlap-aware prompt, for example comparing recursive union of two generic routes, recursive union of TOV and generic repair, and a single TOV route under matched resources?

4. What evidence demonstrates that the semantic ledger fields are accurate or useful representations of candidate behavior, rather than an instruction-induced increase in reasoning effort?

5. How sensitive is the preservation result to verifier nondeterminism, shared files, cross-task dependencies, and tests that pass despite semantically incorrect repairs?

6. What are the results on additional unrelated program-repair or software-engineering benchmarks where task boundaries and allowlisted solution files are not already naturally modular?

## Scores

Soundness: 3/4 — The preservation construction is logically sound under explicit assumptions, but causal and population-level empirical claims are limited by resource and chronology confounds.

Presentation: 3/4 — The paper is unusually transparent and well organized, though the many evidence stages and nested comparisons make the main claim difficult to separate from secondary analyses.

Significance: 3/4 — Verifier-gated preservation is practically relevant for test-available repair, but the demonstrated scope is narrower than general program repair.

Originality: 3/4 — The composition of immutable verified anchors, unresolved branching, and recursive promotion is a useful systems contribution, although its components draw substantially on established repair, verification, and iterative-agent ideas.

Overall recommendation: 3/6 — Borderline: strong bounded-call effectiveness evidence, but insufficient controlled evidence that the proposed architecture or semantic-overlap component—not primarily extra computation—drives the improvement.

Confidence: 4/5 — The paper is self-contained enough to assess its logic and reported evidence, though the underlying runs and artifact are not independently verified here.

## Ethics and Limitations

The use of public coding exercises and no human participants presents minimal direct ethical risk. The paper appropriately notes that failure output can reveal behavioral expectations and that the method increases inference compute. Its main limitations are substantive: finite tests do not establish semantic correctness, one model and runtime limit generality, task-level statistics are conditional on shared whole-track calls, and several key comparisons are post hoc, mixed-stage, or not token-matched. The method also depends on modular task ownership and stable external verification, which may fail in realistic repositories with shared state or weak test suites.

## Comment

I recommend borderline acceptance at most. The paper’s most convincing contribution is the fail-closed, verifier-backed preservation and recursive composition rule, together with strong but bounded evidence of improved repair effectiveness. The decisive issue is whether Mini Artichokes offers a genuine structural advantage beyond spending more model calls and exploiting benchmark modularity. A clean prospective comparison against a resource-matched generic portfolio, ideally with factorial ablations of recursive promotion and semantic overlap, would substantially change my assessment.

### Panel review 2 — experimentalist (accepted)

# Review: Mini Artichokes: Verifier-Gated Recursive Portfolios for Test-Available Program Repair

## Summary

This paper presents Mini Artichokes, a verifier-gated portfolio for program repair that preserves complete task states passing an external test suite, restricts later edits to unresolved tasks, and recursively promotes passing outputs from complementary repair routes. The paper reports substantial bounded-call gains over Plain and ordinary execution-feedback repair, but the evidence for the specific semantic-overlap mechanism and for broad generalization is substantially weaker than the headline system results.

## Strengths

- The paper identifies a clear and practically important failure mode in iterative repair: “A critic may replace a task that another attempt already solved.” Its byte-exact anchor mechanism directly addresses this regression risk.

- The central preservation claim is unusually precise. The paper states: “For each task, the construction copies either its prior anchored state or one complete state already observed to pass; no unverified merged state is created.” Under the explicitly stated A1–A5 conditions, this is a meaningful structural property rather than an empirical claim.

- The evaluation retains complete task inventories. For example, Table 3 reports all 39 Go tasks and Table 5 all 49 JavaScript tasks, while the text emphasizes: “No task is ranked, screened, removed, replaced, or topped up.” This is substantially stronger than selective case-study evaluation.

- The reported system-level gains are large in the nested bounded-call comparison: Mini solves “59/90,” versus “45/90 for ordinary repair” and “15/90 for Plain,” with “14 and loses none” relative to ordinary repair.

- The authors appropriately distinguish system effectiveness from mechanism attribution. They explicitly state that the result is “not semantic overlap as an isolated causal treatment” and acknowledge that the five-call comparison is “not token-matched.”

- The negative and replication evidence is reported candidly. In particular, the paper states that “A one-task Java completion-lock result also does not repeat in five new whole-track pairs,” rather than presenting the motivating rescue as stable evidence.

## Weaknesses

- The primary Mini-versus-ordinary-repair improvement is confounded by substantially more model calls and computation. The authors acknowledge that “These are effectiveness comparisons between nested one-, two-, and five-call systems,” so the main gain does not establish that verifier-gated recursion or semantic overlap is responsible for the improvement.

- The fairest nominal-call comparison is not prospective and does not consistently favor Mini. The paper reports “139/178 for Mini and 132/178 for Direct∪Generic,” but also states that this result is “mixed-stage,” while “JavaScript is the only clean prospective equal-call track and is a tie.” Thus the strongest causal interpretation of the claimed portfolio advantage remains unsupported.

- The semantic-overlap ablation is partly post hoc and unstable. The stricter control was “designed after the original outcomes,” and the reported repeated sessions show only “+1.2/34 on Python and +0.4/26 on C++.” The Java replication further reports “no wins, two losses, three ties,” so the evidence supports semantic overlap as a potentially useful route, but not as a reliable improvement over a matched semantic-free route.

- The statistical evidence is limited by the experimental unit. The paper concedes that “All task rows within one arm share one whole-track model call” and that task-level tests “condition on realized calls.” Consequently, the very small task-level p-values do not support inference over independent model runs, languages, or benchmark populations. Only five session pairs on each of two tracks provide limited trajectory-level replication.

- The method’s correctness guarantee is narrow and heavily dependent on benchmark structure. The authors state that recursive verification “does not guarantee correctness beyond those tests,” and their preservation theorem requires modular task ownership, isolated workspaces, complete allowlisted files, and fail-closed verification. The paper does not demonstrate how often these assumptions hold in realistic repositories with shared files, cross-task dependencies, flaky tests, or incomplete test suites.

- Baselines are not fully comparable implementations of the cited methods. The paper describes Graph, Self-Refine-family repair, and related methods as “bounded prompt realizations rather than complete reproductions,” and explicitly says it does not compare against “a matched full repository agent such as KIRA.” This limits conclusions about superiority over established code-agent systems.

## Questions for the Authors

1. Can you provide a prospective, token- and latency-matched comparison between Mini, Direct∪Generic, and a strong single-agent verifier baseline on multiple complete unseen tracks?

2. What is the effect of recursive promotion alone, holding the final repair route fixed—for example, Direct with and without the intermediate verified-union floor?

3. How sensitive are the results to the fixed route priority, especially `R > G > P` and direct-route-first promotion when both final routes pass?

4. Can you evaluate the method on repositories with shared files or cross-task dependencies, or otherwise quantify how frequently assumptions A1–A5 hold outside these benchmark packaging conditions?

5. Do the reported gains persist across multiple model versions, reasoning settings, and independent seeds without changing the prompts or route design?

## Scores

Soundness: 3/4 — The verifier-preservation construction is well specified and the complete-track results are substantial, but causal attribution and independent replication remain limited.

Presentation: 4/4 — The paper is unusually transparent about chronology, protocol deviations, costs, negative results, and claim boundaries.

Significance: 3/4 — The approach offers a useful systems pattern for test-available repair, though its applicability is restricted and its advantage over strong matched alternatives is not established.

Originality: 3/4 — The composition of anchoring, unresolved-task branching, and recursive verifier promotion is a plausible systems contribution, but its ingredients are closely related to existing ensembles, verification, and iterative repair.

Overall recommendation: 3/6 — Borderline; the bounded-call system result is promising, but the paper does not yet establish a clean, prospective advantage attributable to its distinctive mechanism.

Confidence: 4/5 — The paper provides enough methodological and numerical detail for a well-supported assessment, although the experiments cannot be independently rerun here.

## Ethics and Limitations

The paper reports no human participants and uses public programming tasks, while noting licensing requirements and the possibility that failure output reveals behavioral expectations. The principal limitations are appropriately acknowledged: finite tests certify only observed behavior, model errors may be correlated, task-level statistics arise from shared whole-track calls, semantic diagnoses are not independently labeled, and several evaluations use runtime versions or benchmark material that differ from the planned environment. The additional inference-time compute is also material; the paper reports, for example, “1,422.3” seconds for the TOV final call and explicitly makes no efficiency claim.

## Comment

I view this as a carefully engineered and unusually candid borderline paper. The byte-exact verifier-gated promotion rule is clearly specified and the complete-track results show meaningful bounded-call effectiveness. However, the central scientific advantage is difficult to isolate: the strongest comparison is nested in call budget, the equal-call aggregate is mixed-stage, and the clean prospective equal-call result is a tie. The most important revision would be a genuinely prospective, resource-matched evaluation that isolates recursive promotion and semantic-overlap guidance across multiple independent tracks and model sessions.

### Panel review 3 — scope_ablation (accepted)

# Review: Mini Artichokes: Verifier-Gated Recursive Portfolios for Test-Available Program Repair

## Summary

This paper proposes Mini Artichokes, a verifier-gated portfolio for program repair that preserves complete passing task states, restricts later edits to unresolved tasks, and recursively promotes passing outputs from heterogeneous repair routes. The empirical results show substantial gains over one- and two-call baselines in several test-available benchmarks, but the strongest system gains are confounded by additional model calls, while the cleanest equal-call prospective comparison is a tie.

## Strengths

- The central preservation mechanism is clear and technically well specified: “a complete verified task state is removed from model discretion” and “only unresolved units are branched.” Under the explicit A1–A5 assumptions, the task-wise union argument provides a credible construction-level preservation guarantee.

- The paper distinguishes system effectiveness from component causality. It explicitly states that “the best-supported object is Mini Artichokes as a five-call effectiveness system, not semantic overlap as an isolated causal treatment,” which is an appropriately cautious interpretation.

- The experiments retain complete tracks rather than selecting favorable tasks. For example, Table 3 reports all 39 Go tasks and Table 5 reports all 49 JavaScript tasks, with “no task selection.”

- The results are substantial in the bounded-call setting: Mini reaches 59/90 versus 45/90 for ordinary repair and 15/90 for Plain; on Go it reaches 33/39 versus 25/39 and 17/39; and on JavaScript it reaches 47/49 versus 42/49 and 27/49.

- The paper reports negative and non-replicating evidence rather than hiding it. It acknowledges that “the clean prospective equal-call track, JavaScript49, is tied,” and that the Java completion-lock rescue “does not repeat in five new whole-track pairs.”

- The artifact and integrity protocol is unusually concrete. The paper reports byte-identical anchor checks, exact ledger task IDs, changed-path checks, prompt hashes, and rerun outcome hashes. These details make the claimed preservation property substantially more auditable.

## Weaknesses

- The primary effectiveness comparisons are heavily confounded by call count and compute. Mini uses five whole-track model calls, whereas Plain uses one and ordinary repair uses two. The paper itself concedes that these are “effectiveness comparisons between nested one-, two-, and five-call systems, not efficiency or overlap-only estimates.” Thus, the headline gains do not establish that verifier-gated recursion or semantic overlap is responsible for the improvement.

- The strongest nominally equal-call comparison is not a clean prospective causal test. The paper describes the 139/178 versus 132/178 result as “mixed-stage,” notes that the original contrast was post hoc and Go used a replacement sensitivity, and reports that the “only clean prospective equal-call track, JavaScript49, is tied.” This substantially weakens the claim that Mini itself outperforms an equal-budget generic portfolio.

- The semantic-overlap contribution is not isolated convincingly. The strict semantic-free ablation was “designed after the original outcomes,” and the control cannot equalize “latent model trajectories or realized compute.” On the original tracks, TOV’s seven-task advantage is therefore suggestive but vulnerable to post-hoc design and stochastic trajectory differences; on later paired sessions, the standalone route advantage is explicitly unstable.

- Generalization is narrow relative to the broad framing. All semantic calls use “one model and runtime,” every task vector is generated inside “one whole-track call,” and the main evidence concerns test-available, modular code-repair tasks. The paper’s own operating-point description requires “tasks [that] are modular,” “a trusted external verifier,” and informative failure output. It remains unclear whether the method transfers to shared-state repositories, weak or flaky tests, interactive debugging, or tasks without executable verification.

- The benchmark evidence is not statistically independent at the task level. The authors correctly state that task-level tests “condition on realized calls,” but this means the very small task-level p-values should not be interpreted as broad population evidence. The five-pair replication analysis is more relevant for generalization, yet it covers only Python and C++ sessions and produces limited evidence about cross-model or cross-benchmark stability.

- The method’s practical cost is significant and insufficiently characterized. The original final-call table reports roughly 5.4–7.1 million input tokens and 1,234–1,423 seconds for four-call final arms, while the paper explicitly makes “no efficiency or monetary-cost dominance” claim. A stronger comparison should quantify whether the accuracy gain remains attractive under fixed wall-clock, token, or monetary budgets.

- Several benchmark results are ceiling or protocol-deviation cases. HumanEvalFix Python reaches 164/164 for ordinary repair, and the paper notes Python 3.13.11 rather than the anticipated environment. QuixBugs is also already at 40/40 for multiple routes. These results are useful boundaries, but they provide little evidence that the proposed semantic mechanism improves difficult, non-ceiling tasks under standardized conditions.

## Questions for the Authors

1. Can you provide a prospective, same-call, token- or time-matched comparison between Mini and the strongest generic portfolio, using the same model, seeds, and complete-track protocol?

2. How much of Mini’s gain comes from simply adding two additional independent repair calls and taking the verifier union, independent of semantic-overlap reasoning and recursive staging?

3. Can the semantic-overlap contribution be tested with a preregistered control whose prompt, output schema, token budget, and realized compute are matched more tightly, ideally across multiple models?

4. What evidence supports applicability beyond independently testable task units—for example, repositories with shared files, cross-task build state, flaky tests, or only partial verification?

5. How sensitive are the results to model sampling and model choice? Do the preservation mechanism and route complementarity persist when replacing `gpt-5.6-luna` while keeping the harness fixed?

6. Can you report fixed-resource Pareto curves or cost-normalized accuracy, rather than only bounded-call effectiveness?

## Scores

Soundness: 3/4 — The preservation construction is well defined and the results are carefully qualified, but causal attribution and generalization remain limited.

Presentation: 3/4 — The paper is unusually transparent and comprehensive, though the chronology and many overlapping experimental roles make the central evidence difficult to disentangle.

Significance: 3/4 — Verifier-gated preservation is practically relevant for test-available repair, but the demonstrated scope is narrower than broad portfolio claims suggest.

Originality: 3/4 — The composition of immutable task anchors, unresolved-set branching, and recursive verifier promotion is a meaningful systems design, although its ingredients are individually familiar.

Overall recommendation: 3/6 — Borderline; the system result is promising and technically disciplined, but the key mechanism is not established by a clean prospective equal-resource comparison.

Confidence: 3/5 — The paper is self-contained enough to assess, but the main conclusions depend on reported experimental artifacts and complex staged comparisons that cannot be independently verified here.

## Ethics and Limitations

The paper uses public programming benchmarks and reports no human-subject concerns. It appropriately notes that failure output may reveal behavioral expectations and that the method increases inference compute. The main limitations are substantive: one model and runtime, correlated whole-track calls, finite and potentially weak test suites, narrow modularity assumptions, unequal realized compute, post-hoc stages, and limited replication across models and task families. The byte-level preservation guarantee protects observed test labels, not correctness beyond the supplied tests.

## Comment

I recommend borderline acceptance/revision consideration. The verifier-gated recursive union is a clear and potentially useful systems contribution, and the paper is commendably candid about failed replications and protocol limitations. The decisive issue is attribution: the large headline gains arise from a five-call portfolio against substantially cheaper baselines, while the clean prospective equal-call comparison ties. The authors should make a fixed-resource prospective comparison and a stronger ablation of semantic overlap the central validation before claiming that Mini’s particular recursive or semantic design, rather than additional repair attempts plus verification, drives the improvement.
