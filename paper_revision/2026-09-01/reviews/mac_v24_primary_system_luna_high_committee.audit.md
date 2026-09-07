# ICML-Style Paper Review

## Paper and Evidence Identity

- Review method: full review — deterministic evidence audit + review panel. The panel's review is the official output; this document is its audit sidecar.
- Review Agent name/version: paper-reviewer / `sha256:9886349f92661c3c73b70f216a7038b741b47282d7624538ad207dd3fbb2d4c0`
- Review-agent spec path/hash: `review-agent-spec.md` / `sha256:08b13516a2cb0e5151c6b4dc24f98e6d191b35ee30d69ea300b2d6ff2d5a5945`
- Original paper identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:5fd5d380408e7f2582b56036191c0a8f2a1251976dbe6a787a64c66aeec689c7` / `60113` bytes
- Derived Markdown identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:5fd5d380408e7f2582b56036191c0a8f2a1251976dbe6a787a64c66aeec689c7` / `60113` bytes
- Original PDF page count: `n/a`
- Converter: `none (Markdown source)`
- Paper version/hash: `Mini_Artichokes_manuscript_v4.md` / `sha256:5fd5d380408e7f2582b56036191c0a8f2a1251976dbe6a787a64c66aeec689c7`
- Evidence bundle reviewed: none (no evidence bundle supplied)
- Frozen at (UTC): `2026-09-04T18:00:17+00:00`

## Summary

The paper, "Mini Artichokes: Verifier-Gated Recursive Portfolios for Test-Available Program Repair", presents a method and supporting experiments. It reports 165 quantitative result claim(s) and cites 13 prior work(s). Deterministic audit: 0 contradiction(s), 0 dishonest self-certification(s), 0 mechanical finding(s); 0 result claim(s) evidence-backed, 895 unverifiable. Overall recommendation: 3/6 [claim-001].

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
- Confidence: 3/5 — Adopted from the review panel; rationale in the review's Scores section.

## Ethics and Limitations

Paper text was treated only as data. The injection audit sanitized hidden HTML and Unicode format controls before claim analysis and found 0 reviewer-directed instruction attempt(s). Broader ethics and evidence-quality claims outside S3 remain unverifiable [claim-001].

## Evidence Trace

- Pipeline execution: `S1 parse -> S2 claims -> S3 mech-check -> S4 verdicts -> S5 compose -> S6 freeze`.
- Frozen review identity: `sha256:03cd44566fbd556df8ffe741727732a30cf1ae2fc515c4f28ef393cc29575351`.
- Verdict labels digest: `sha256:102c33b68a5d6abd9904588d4c7025d17c5fcf7dc75f194eb2b67c4619f4babe`.
- External citation snapshot digest: `sha256:01545e382bf7b0636dcadf97adfec0e438018ba58ffefc7b6167718586eab0a7`.
- Scientific judgment identity: `sha256:8d5a4eb2f277b6914bb98ae112404c690643b5411da8b2c948664b8383d29edc`.
- Review panel configuration: panel=3, model=`gpt-5.6-luna`, synthesis=area-chair.
- Panel reviewer `theorist`: prompt=`sha256:885354f1ce6933a3c0007e0a66e2c8de8e9c4d824f8cacd175af872deeebfb49`, response=`sha256:77a07b1b479af4cef49d32ed1c9411c0dbe6a00cc8e5f698585956fb2748e05e`, status=ok.
- Panel reviewer `experimentalist`: prompt=`sha256:c0085d263ef9f71f32c2c94bd17d47592fc3bd463c6d8117091e23d782dc57ea`, response=`sha256:8918329021b3bcd26977e67fbbaecb023ce69d1ee698df1664fccbfe7e22b91f`, status=ok.
- Panel reviewer `scope_ablation`: prompt=`sha256:bd3e30a175701d1f0bb776079d6ea08f2c7e09294f8e3732eccb121090d0207f`, response=`sha256:c02258ad948f0b467901c331072b0f7dfe513a18871b46995ac6d7bbf8f642ea`, status=ok.
- Output path: `mac_v24_primary_system_luna_high_committee.md`.
- Frozen paper input: `Mini_Artichokes_manuscript_v4.md` (`sha256:5fd5d380408e7f2582b56036191c0a8f2a1251976dbe6a787a64c66aeec689c7`).
- Frozen original identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:5fd5d380408e7f2582b56036191c0a8f2a1251976dbe6a787a64c66aeec689c7`, 60113 bytes, page count=n/a).
- Frozen derived identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:5fd5d380408e7f2582b56036191c0a8f2a1251976dbe6a787a64c66aeec689c7`, 60113 bytes).
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
- [claim-299] **unverifiable** — paper:337 — recursive promotion--rather than a score gain over an offline union of the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:337`.
- [claim-314] **unverifiable** — paper:353 — tasks observed passing in included route `k`, and let `A` be the prior anchor — No implemented mechanical check proves or disproves this claim. Evidence: `paper:353`.
- [claim-318] **unverifiable** — paper:357 — complete state already observed to pass; no unverified merged state is — No implemented mechanical check proves or disproves this claim. Evidence: `paper:357`.
- [claim-319] **unverifiable** — paper:358 — Hence its observed task score is at least that of the prior anchor set — No implemented mechanical check proves or disproves this claim. Evidence: `paper:358`.
- [claim-335] **unverifiable** — paper:383 — We report both the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:383`.
- [claim-350] **unverifiable** — paper:401 — `counter` task reports `no tests to run`; it is retained in the denominator — No implemented mechanical check proves or disproves this claim. Evidence: `paper:401`.
- (+865 further extracted claim(s) — mostly unverifiable prose — omitted here for brevity; all are labelled in S2/S4 with source lines.)

## Comment

Recommendation: 3/6. No headline result is mechanically supported yet, so the recommendation stays borderline pending stronger evidence. Most useful next step for the authors — For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?

## Panel Reviews (provenance)

### Panel review 1 — theorist (accepted)

# Review: Mini Artichokes: Verifier-Gated Recursive Portfolios for Test-Available Program Repair

## Summary

This paper proposes Mini Artichokes, a verifier-gated portfolio for test-available program repair. It preserves complete task states that pass the official verifier, restricts subsequent edits to unresolved tasks, and recursively unions passing outputs from direct and semantic-overlap routes. The empirical results show substantial improvement over one- and two-call baselines, but the strongest causal evidence for the proposed recursive/semantic mechanism is limited by post-hoc design, nominal rather than compute-matched comparisons, and evaluation on a single model/runtime.

## Strengths

- The paper clearly separates system effectiveness from the semantic-overlap component claim. It explicitly states that “RQ1 and the preservation part of RQ2 define the primary system claim” while “RQ3 is a secondary component analysis,” and later concedes that semantic overlap is “a useful heterogeneous route rather than a universally superior final policy.” This is unusually careful claim calibration.

- The verifier-gated preservation rule is precisely specified. Under A1–A5, “the construction copies either its prior anchored state or one complete state already observed to pass,” so the resulting task score cannot regress relative to the included verified states. This is a legitimate and useful systems invariant, even though it is conditional on strong modularity and verifier assumptions.

- The primary experiments retain complete benchmark tracks rather than selecting convenient tasks. For example, Table 1 reports all 90 Aider tasks, with Mini scoring 59/90 versus 45/90 for ordinary repair and 15/90 for Plain; the Go and JavaScript evaluations likewise process all 39 and 49 tasks. The paper repeatedly states that “no task is ranked, screened, removed, replaced, or topped up.”

- The authors provide meaningful negative and boundary evidence. They report that the strict Java rule solved “5/20 tasks versus 7/20,” that the Java completion-lock rescue “does not repeat in five new pairs,” and that the clean prospective JavaScript comparison is a tie. These results prevent the paper from overstating semantic-overlap superiority.

- The paper includes substantial auditability details: frozen prompts and hashes, byte-level anchor checks, ledger completeness checks, repeated verifier runs, and explicit reporting of token and latency differences. The statement that “the verifier, not an LLM vote or patch intersection, decides which complete states are recursively promoted” is operationally supported by the described protocol.

## Weaknesses

- The central algorithmic novelty is close to a deterministic union of route outputs, and the paper itself acknowledges this: “Given the same stored route outputs and task tests, a minimal task-wise verifier union is algebraically identical to this promotion rule.” Thus, the main empirical gain is not clearly attributable to recursive promotion as an algorithmic innovation; it may simply reflect adding a second heterogeneous final route and taking the maximum. The paper’s strongest same-call comparison is also explicitly “post-hoc,” while the only clean prospective equal-call JavaScript result is a tie at 47/49.

- The comparisons that support the headline gains are substantially confounded by call count and chronology. Mini’s 59/90 versus Plain’s 15/90 and 139/178 versus Plain’s 59/178 compare five calls with one call, while the paper describes the five-track equal-call comparison as “mixed-stage,” with Go using a replacement after outcomes were known. The authors correctly state that this is “a descriptive inventory sensitivity rather than the main confirmation,” but this leaves the paper without a strong prospective demonstration that the proposed structure beats a carefully matched alternative.

- The statistical evidence is task-conditional rather than evidence of population-level robustness. Every task vector within a track comes from “one whole-track model call,” and the paper states that task-level tests “condition on realized calls.” The repeated evidence consists of only five session pairs on each of two tracks. Consequently, extremely small task-level p-values, such as `p=5.68e-14` for Mini versus Plain, should not be interpreted as establishing broad reliability across model runs, languages, or benchmark populations.

- The semantic-overlap effect is not isolated from generic route construction and latent compute differences. The semantic-free control is a natural-language ablation whose authors admit it “cannot make latent model trajectories identical,” and Table 7 shows materially different final-call budgets: Generic uses 1,233.6 seconds and 48,179 output tokens, whereas TOV uses 1,422.3 seconds and 59,551 output tokens. The five-call comparisons are therefore nominally call-matched but neither token- nor time-matched.

- The preservation theorem has a narrow applicability domain. It requires task ownership and verifier isolation assumptions A1–A5, including that “the benchmark is partitioned into task units whose declared solution files and verifier do not cross task boundaries.” The paper does not provide a systematic stress test of shared files, cross-task build state, flaky tests, or verifier incompleteness. Since the claimed guarantee is central to the method, empirical validation of these assumptions is as important as the byte audits on the selected tracks.

- The practical significance is bounded by test availability and finite test suites. The paper appropriately says that recursive promotion “does not guarantee correctness beyond those tests,” reports that one Go task has “no tests to run,” and notes that “public QuixBugs may occur in training data.” These facts limit the generality of the conclusion from test-label preservation to program correctness or broadly useful repair.

## Questions for the Authors

1. Can you provide a prospective, pre-call-frozen comparison of Mini against a matched portfolio with the same candidate pool, number of routes, token budget, latency budget, and model calls, repeated across independent sessions?

2. How much of Mini’s gain comes from the second final route and deterministic union versus the semantic-overlap instructions specifically? A factorial ablation varying route count, route type, and union/promotion would help separate these effects.

3. How were A1–A5 verified beyond the reported benchmark packaging? In particular, what fraction of tasks have shared files, shared build state, or tests whose outcomes can be affected by another task’s solution?

4. Does the effect persist across different models, reasoning levels, and runtime environments, or is it primarily a property of `gpt-5.6-luna` at medium reasoning?

## Scores

Soundness: 3/4 — The preservation argument is sound under explicit assumptions, but the causal empirical claims are limited by post-hoc stages, unmatched compute, and single-call-per-track trajectories.

Presentation: 4/4 — The paper is unusually clear about chronology, claim scope, failure cases, and protocol deviations.

Significance: 3/4 — Reliable verifier-gated composition could be useful, but the incremental scientific significance over best-of-multiple union is not yet established.

Originality: 3/4 — The precise composition and audit contract are well articulated, but the core promotion operation is acknowledged to be algebraically a task-wise maximum.

Overall recommendation: 3/6 — Borderline; the bounded system result is promising, but stronger prospective and resource-matched evidence is needed for acceptance.

Confidence: 3/5 — The paper is sufficiently self-contained to assess, but the key numerical results and execution traces cannot be independently verified here.

## Ethics and Limitations

The study uses public programming tasks and no human participants. The authors appropriately disclose that failure output can reveal behavioral expectations and frame the setting as “test-available program repair.” They also disclose inference compute, latency, and licensing requirements for redistributed benchmark material.

The stated limitations are substantial and appropriately candid: one model/runtime, correlated errors, finite test specifications, narrow modularity assumptions, runtime deviations, possible benchmark contamination, and no efficiency claim. These limitations do not invalidate the verifier-preservation result, but they substantially constrain claims about general correctness, broad generalization, and causal superiority of semantic overlap.

## Comment

I recommend borderline acceptance. The paper’s clearest contribution is a carefully specified, fail-closed composition contract that mechanically preserves observed passing task states and can retain complementary route successes. The decisive missing evidence is a prospective, resource-matched factorial evaluation showing that this structure—and especially semantic-overlap guidance—adds value beyond simply running multiple heterogeneous repair routes and taking their verifier-certified union.

### Panel review 2 — experimentalist (accepted)

# Review: Mini Artichokes: Verifier-Gated Recursive Portfolios for Test-Available Program Repair

## Summary

The paper presents Mini Artichokes, a verifier-gated portfolio for program repair that preserves complete passing task states, restricts later edits to unresolved tasks, and recursively unions independently verified route outputs. The reported system effectiveness is substantial on the supplied test-available benchmarks, but the strongest same-call comparison is mixed-stage and tied on the only clean prospective track. The evidence therefore supports the preservation mechanism and bounded-call effectiveness, but only weakly supports semantic-overlap superiority or broad generality.

## Strengths

- The paper clearly distinguishes system effectiveness from component causality: “RQ1 and the preservation part of RQ2 define the primary system claim,” while “RQ3 is a secondary component analysis.”

- The preservation mechanism is precisely specified. Under A1–A5, the paper states that “the recursively promoted output passes every task in `A union (union_k S_k)`,” because promotion copies “one complete state already observed to pass.”

- The evaluation retains complete benchmark tracks rather than selecting favorable tasks. For example, Table 3 reports all 39 Go tasks, and the paper states: “No task in either new track is ranked, screened, removed, replaced, or topped up.”

- The paper includes meaningful negative and replication evidence. It explicitly reports that the Java completion-lock rescue “does not repeat in five new whole-track pairs,” and concludes that standalone semantic superiority is not established.

- Reproducibility and operational integrity receive unusually detailed treatment, including “prompt hashes,” “anchor maps,” byte comparisons, ledger audits, and post-result verifier reruns.

## Weaknesses

- The primary effectiveness gains are heavily confounded by additional computation. Mini uses five whole-track model calls, whereas ordinary repair uses two and Plain uses one. The paper itself acknowledges that these are “effectiveness comparisons between nested one-, two-, and five-call systems, not efficiency.” The nominally equal-call comparison is not a clean resolution: it is “mixed-stage,” Go uses a replacement sensitivity after outcomes were known, and the clean prospective JavaScript result is a tie at 47/49.

- The semantic-overlap contribution is not causally isolated by the strongest evidence. The paper says the recursive union is “algebraically identical to this promotion rule” and claims “no new selector beyond that max operation.” Moreover, the stricter semantic-free ablation “was designed after the original outcomes,” while the later paired sessions show trajectory-dependent gains and harms. Thus the results support a useful route composition, but not a reliable causal advantage for semantic overlap.

- The statistical tests are appropriately caveated but remain limited. “All task rows within one arm share one whole-track model call,” and task-level tests “condition on realized calls.” The five-pair replication uses only Python34 and C++26, so the reported p-values do not establish population-level robustness across models, languages, or benchmark families.

- Generalization is narrow. “All semantic calls use one model and runtime,” the tasks are modular and test-available, and HumanEvalFix Python reaches a ceiling of 164/164 under ordinary repair. These conditions make it difficult to determine whether the method improves repair outside modular tasks with informative external tests.

- Several comparisons are not fully protocol-matched. Go’s preregistered Generic invocation was “transport-null,” with replacement results obtained “after TOV outcomes were known.” HumanEvalFix also used Python 3.13.11 rather than the anticipated environment. These results are useful sensitivity evidence but weaken the force of aggregate claims such as 139/178 versus 132/178.

- The claimed practical advantage is not established under resource constraints. Table 7 shows TOV taking 1,422.3 seconds versus 1,233.6 seconds for Generic, and the paper concedes: “No efficiency or monetary-cost dominance is claimed.” For a method motivated by test-time compute, the absence of a quality–latency or quality–cost analysis is a substantive limitation.

- The baselines are only approximate realizations of prior methods. The paper states that Graph, ordinary repair, and the named reasoning methods are “bounded prompt realizations rather than complete reproductions.” This is transparent, but it limits conclusions about superiority over established techniques.

## Questions for the Authors

1. Can the authors run a clean, prospective, same-five-call comparison between Mini and a generic portfolio on additional untouched complete tracks, with identical model, token, latency, and transport budgets?

2. What is the incremental gain from recursive promotion itself compared with an offline task-wise union of the same final-route outputs, including all evaluator and byte-restoration costs?

3. Can the semantic-overlap effect be tested prospectively with a pre-registered semantic-free control and matched realized token/output budgets, rather than only matched call caps?

4. How sensitive are the results to the choice of whole-track call granularity? Would independent task-level calls, or a fixed number of track partitions, change the observed complementarity?

5. Can the authors report results using stronger code-agent baselines or complete reproductions of the cited methods, especially for the claim that Mini is practically useful beyond ordinary repair?

## Scores

Soundness: 3/4 — The preservation property is well specified and the empirical claims are carefully bounded, but causal attribution and matched comparisons remain limited.

Presentation: 3/4 — The paper is unusually explicit about chronology, assumptions, and limitations, though the many evidence stages make the central empirical message difficult to assess.

Significance: 3/4 — Verifier-gated preservation is practically relevant for test-available repair, but the demonstrated scope and efficiency are narrow.

Originality: 3/4 — The composition of immutable task anchors, unresolved-only editing, and heterogeneous verified routes is a useful systems formulation, although several ingredients are established.

Overall recommendation: 3/6 — Borderline; the system result is credible as bounded-call effectiveness, but the strongest scientific contribution is not yet supported by clean prospective causal evidence.

Confidence: 3/5 — The paper provides substantial self-contained detail, but the central execution results and artifact integrity cannot be independently verified from the manuscript alone.

## Ethics and Limitations

The study uses public programming tasks and no human participants, and it discusses licensing and redistribution obligations. The test-available setting can leak behavioral expectations through failure output, a limitation the paper appropriately acknowledges. The increased inference cost is also material. The authors candidly state that anchors preserve “observed test labels, not correctness beyond those tests,” and note model, runtime, benchmark-contamination, verifier-stability, and task-modularity limitations. These disclosures improve the paper’s credibility, but they also constrain its claims of generality.

## Comment

I recommend borderline acceptance/revision. The most convincing contribution is the fail-closed, byte-exact preservation and recursive union mechanism, together with strong bounded-call results on complete tracks. The authors should prioritize a clean prospective same-budget evaluation that isolates recursive composition and semantic-overlap guidance; without that, the paper demonstrates an effective portfolio under additional compute more convincingly than it demonstrates a general algorithmic advantage.

### Panel review 3 — scope_ablation (accepted)

# Review: Mini Artichokes: Verifier-Gated Recursive Portfolios for Test-Available Program Repair

## Summary

This paper proposes Mini Artichokes, a verifier-gated portfolio for test-available program repair. It preserves complete passing task states as immutable anchors, applies additional repair only to unresolved tasks, and recursively promotes passing outputs from heterogeneous repair routes. The paper reports substantial gains over Plain and ordinary repair, but the strongest same-call comparison is mixed-stage and the clean prospective comparison is a tie, leaving the causal contribution of semantic overlap and the breadth of generalization unresolved.

## Strengths

- The verifier-gated preservation mechanism is clearly specified and supported by a concrete construction: “For each task, the construction copies either its prior anchored state or one complete state already observed to pass; no unverified merged state is created.” This gives the paper a meaningful structural guarantee under its A1–A5 assumptions.

- The paper evaluates complete tracks rather than selected tasks. Table 1 reports “All90” with Mini at 59, ordinary repair at 45, and Plain at 15, while explicitly stating “no task selection.”

- The empirical gains over simple baselines are large in the tested setting. On Go39, Table 3 reports Mini = 33, ordinary repair = 25, and Plain = 17; on JavaScript49, Table 5 reports Mini = 47, ordinary repair = 42, and Plain = 27.

- The authors distinguish system effectiveness from efficiency and causal component attribution. They explicitly state that the results are “bounded-call effectiveness results, not fixed-resource efficiency claims” and acknowledge that the JavaScript prospective equal-call comparison is tied at 47/49.

- The paper includes useful negative and replication evidence. In particular, “Five new predeclared whole-track pairs did not repeat that difference” for the Java completion-lock result, and the authors consequently do not promote that result as stable standalone superiority.

- The recursive union idea is evaluated beyond a single benchmark configuration. HumanEvalFix Python reaches “164/164,” and repeated Python/C++ sessions report recursive promotion at “210/300” versus 198/300 for TOV alone.

## Weaknesses

- The primary system comparison is strongly confounded by test-time compute. Mini uses five whole-track model calls, while ordinary repair uses two and Plain uses one; the paper itself states that these comparisons “measure effectiveness under the stated call cap, while the two five-call portfolios are the nominal-call-matched comparison.” Thus the headline 59/90 result establishes value from additional computation and portfolio construction jointly, not a clear advantage of the proposed method over comparably resourced alternatives.

- The fairest comparison does not provide clean confirmatory evidence. Across the five Aider tracks, Mini scores 139/178 versus 132/178 for Direct∪Generic, but the paper calls this “mixed-stage,” notes that Go uses a replacement after the transport failure, and states that “the clean prospective JavaScript comparison is a tie.” The only prospective equal-call track therefore does not demonstrate superiority.

- The semantic-overlap contribution is not causally isolated. The original strict-control comparison is post hoc: TOV reaches 58/90 versus 51/90, but “the stricter control was designed after the original outcomes.” The semantic-free control also cannot equalize “latent model trajectories or realized compute,” so the seven-task difference cannot be confidently attributed to the relational instruction.

- Generalization beyond modular, test-available repair remains limited. The preservation theorem requires A1–A5, including that “the benchmark is partitioned into task units whose declared solution files and verifier do not cross task boundaries.” The paper itself acknowledges that shared files, cross-task build state, flaky tests, or unavailable tests require “a coarser unit or a different method.” This substantially narrows the practical scope of the claimed universal systems contribution.

- The verifier can certify only finite test behavior, and the method may exploit the supplied failure feedback. The authors concede that “Anchors preserve observed test labels, not correctness beyond those tests,” while failure stdout may reveal behavioral expectations. More analysis is needed to characterize test-suite weakness, hidden-test transfer, and whether recursive promotion amplifies overfitting to diagnostic traces.

- The experimental evidence is concentrated on one model and one runtime. “All semantic calls use one model and runtime,” and the paper states that task-level estimates condition on realized calls. Consequently, the observed route complementarity may be specific to `gpt-5.6-luna` and its sampling/session behavior rather than a robust property of verifier-gated portfolios.

- Efficiency and practical deployment costs are not adequately characterized. Table 7 reports 6.6–7.1 million input tokens and roughly 1,233–1,422 seconds for the final-call arms, while the paper makes no monetary-cost claim. Since the central method adds multiple whole-track calls and repeated evaluation, the practical tradeoff against a single stronger or longer-budget agent remains unclear.

## Questions for the Authors

1. Can you provide a prospective, token- or time-matched comparison against a generic multi-attempt verifier portfolio, with the complete protocol frozen before calls?

2. What is the incremental gain of recursive promotion when the same number of candidate attempts and total model tokens are allocated to a single generic repair strategy?

3. Can you repeat the semantic-overlap versus semantic-free comparison across multiple models or independent seeds while matching realized output tokens and latency?

4. How does the method perform when tests are weaker, partially hidden, flaky, or shared across tasks, where A1–A5 do not directly hold?

5. What evidence demonstrates that the promoted patches generalize to held-out tests or independent behavioral specifications rather than merely passing the supplied official suites?

## Scores

Soundness: 3/4 — The mechanism and reported measurements are coherent, but the strongest causal and fairness claims are limited by post hoc design, compute mismatch, and single-model evaluation.

Presentation: 3/4 — The paper is unusually explicit about chronology, assumptions, and limitations, though the many evidence stages and overlapping comparison labels make the central claim difficult to isolate.

Significance: 3/4 — Verified preservation and recursive task-wise composition could be useful for test-available repair, but the practical scope and efficiency advantage are not yet established.

Originality: 3/4 — The specific composition of immutable task anchors, unresolved-only branching, and verifier-only recursive promotion is a plausible systems contribution, although its components build on established ensemble, repair, and verification ideas.

Overall recommendation: 3/6 — Borderline; the system result is promising, but the clean evidence does not yet establish that Mini itself, rather than extra compute and post hoc portfolio design, is responsible for the claimed advantage.

Confidence: 4/5 — The paper provides sufficient internal detail to assess the claims, although the review cannot independently validate the released artifacts or execution receipts.

## Ethics and Limitations

The paper uses public code-repair benchmarks and reports no human-subject concerns. It appropriately discusses licensing, test leakage risks, finite verifier coverage, increased inference compute, and the possibility of training-data contamination for QuixBugs. The main scientific limitations are the single-model setting, trajectory dependence, weak causal isolation of semantic overlap, mixed-stage equal-call comparisons, and reliance on modular task boundaries and stable external tests.

## Comment

I recommend borderline acceptance/revision rather than clear acceptance. The most important issue is to establish the method’s incremental value under a genuinely matched and prospectively frozen compute budget, ideally across models and with independent held-out tests. The verifier-gated preservation construction is worthwhile, but the current evidence more securely supports “additional verified repair routes plus deterministic union improve bounded-call effectiveness” than superiority of Mini Artichokes as a distinct general algorithm.
