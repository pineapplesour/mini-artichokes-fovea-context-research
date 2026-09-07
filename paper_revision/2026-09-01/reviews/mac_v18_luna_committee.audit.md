# ICML-Style Paper Review

## Paper and Evidence Identity

- Review method: full review — deterministic evidence audit + review panel. The panel's review is the official output; this document is its audit sidecar.
- Review Agent name/version: paper-reviewer / `sha256:9886349f92661c3c73b70f216a7038b741b47282d7624538ad207dd3fbb2d4c0`
- Review-agent spec path/hash: `review-agent-spec.md` / `sha256:08b13516a2cb0e5151c6b4dc24f98e6d191b35ee30d69ea300b2d6ff2d5a5945`
- Original paper identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:91d3a3d297871815ac45da249f461d5088ffd134c47c4c0eb280dabcd0d0580a` / `61376` bytes
- Derived Markdown identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:91d3a3d297871815ac45da249f461d5088ffd134c47c4c0eb280dabcd0d0580a` / `61376` bytes
- Original PDF page count: `n/a`
- Converter: `none (Markdown source)`
- Paper version/hash: `Mini_Artichokes_manuscript_v4.md` / `sha256:91d3a3d297871815ac45da249f461d5088ffd134c47c4c0eb280dabcd0d0580a`
- Evidence bundle reviewed: none (no evidence bundle supplied)
- Frozen at (UTC): `2026-09-04T00:36:02+00:00`

## Summary

We introduce **Mini Artichokes**, a. It reports 143 quantitative result claim(s) and cites 12 prior work(s). Deterministic audit: 0 contradiction(s), 0 dishonest self-certification(s), 0 mechanical finding(s); 0 result claim(s) evidence-backed, 922 unverifiable. Overall recommendation: 3/6 [claim-001].

## Strengths

- The paper situates its contribution against prior work (12 citation(s); related-work section present).

## Weaknesses

- The deterministic audit proved no contradiction, arithmetic error, or integrity breach; the remaining concern is limited to claims that could not be independently verified (see Questions).

## Questions for the Authors

1. For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?
2. 143 extracted result/arithmetic claim(s) could not be checked against the supplied evidence and are listed with their source lines in the Evidence Trace — could the authors provide the underlying results?

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
- Frozen review identity: `sha256:742cccadb16d5c7629cefec539ca06e28eb874fed408024e6b6ff628e7185e16`.
- Verdict labels digest: `sha256:6e00428c9b4ffde7000d531f50ab02b9a5ad25fa2284d8f12e31f222b2694397`.
- External citation snapshot digest: `sha256:01545e382bf7b0636dcadf97adfec0e438018ba58ffefc7b6167718586eab0a7`.
- Scientific judgment identity: `sha256:ae8f2b11ea74b4025514f3276d474cfbf659244bc1dd10a24a918a8cfb382d40`.
- Review panel configuration: panel=3, model=`gpt-5.6-luna`, synthesis=area-chair.
- Panel reviewer `theorist`: prompt=`sha256:dfe4a356a2a6c57db45fde4dacbeda8b3865b2ddc7a7fd79bfb26ebe1837bcb3`, response=`sha256:73264dc1718b0bf35ff0c8fb0604a2d1cdf783e181993c01c7bab01ae7c7ba3b`, status=ok.
- Panel reviewer `experimentalist`: prompt=`sha256:5499131c3146f212e9153f015aa8edc1fda40d31ff44e14a576a9e50263fbc13`, response=`sha256:5383bbc90cf328d1a37ba52cf7af73bc142922ae39b68c5a99f92c9cb7116018`, status=ok.
- Panel reviewer `scope_ablation`: prompt=`sha256:c121e88e5220799e3d8ef099375a59eca41e255e134bcf522292018fb1be5010`, response=`sha256:b7374b8ee59a38f7dcdc99ec5641814cb0e2fd6c8d5a8cc790199809929948da`, status=ok.
- Output path: `mac_v18_luna_committee.md`.
- Frozen paper input: `Mini_Artichokes_manuscript_v4.md` (`sha256:91d3a3d297871815ac45da249f461d5088ffd134c47c4c0eb280dabcd0d0580a`).
- Frozen original identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:91d3a3d297871815ac45da249f461d5088ffd134c47c4c0eb280dabcd0d0580a`, 61376 bytes, page count=n/a).
- Frozen derived identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:91d3a3d297871815ac45da249f461d5088ffd134c47c4c0eb280dabcd0d0580a`, 61376 bytes).
- Frozen converter: `none (Markdown source)`.
- Pre-S1 sanitation: 0 trace(s), 0 injection finding(s).
- S1 parse inventory: 40 sections, 11 tables, 743 numeric tokens with source locations.
- S3 ledger-trace: 0/0 metric-labelled values matched; 0 finding(s).
- S3 internal-consistency: 0 comparison(s), 0 finding(s).
- S3 arithmetic: 0 recomputation(s), 0 finding(s).
- S3 baseline-fairness: 0 explicit improvement claim(s), 0 finding(s).
- S3 negative-evidence: 0 discard/crash outcome(s), 0 omission finding(s).
- S3 citation-existence: 2 explicit identifier(s), 0 existence/title finding(s).
- S3 template-compliance: 1 contract trace(s), 0 finding(s).
- S3 injection-scan: 0 sanitation trace(s), 0 reviewer-directed instruction finding(s).
- S3 self-review-audit: 0 checklist item(s), 0 dishonest self-certification(s).
- S3 positioning: 12 cited reference(s), related-work section=True, 0 novelty/superiority claim(s), 0 overclaim finding(s), 0 positioning question(s).
- S5 DRAFT/GROUND: 143 candidate comment(s), 143 retained, 0 deleted, 143 criticism comment(s) converted to questions.
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
- [claim-251] **unverifiable** — paper:291 — `/tmp/artifacts/decision_ledger.json` with exactly one record for each frozen — No implemented mechanical check proves or disproves this claim. Evidence: `paper:291`.
- [claim-257] **unverifiable** — paper:295 — They do not score the natural-language diagnoses for — No implemented mechanical check proves or disproves this claim. Evidence: `paper:295`.
- [claim-277] **unverifiable** — paper:316 — verification preserves every observed pass from either included route on the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:316`.
- [claim-279] **unverifiable** — paper:318 — The construction was formulated after final-route crossovers were observed and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:318`.
- [claim-296] **unverifiable** — paper:335 — tasks observed passing in included route `k`, and let `A` be the prior anchor — No implemented mechanical check proves or disproves this claim. Evidence: `paper:335`.
- [claim-300] **unverifiable** — paper:339 — complete state already observed to pass; no unverified merged state is — No implemented mechanical check proves or disproves this claim. Evidence: `paper:339`.
- [claim-301] **unverifiable** — paper:340 — Hence its observed task score is at least that of the prior anchor set — No implemented mechanical check proves or disproves this claim. Evidence: `paper:340`.
- [claim-317] **unverifiable** — paper:365 — We report both the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:365`.
- [claim-332] **unverifiable** — paper:383 — `counter` task reports `no tests to run`; it is retained in the denominator — No implemented mechanical check proves or disproves this claim. Evidence: `paper:383`.
- [claim-339] **unverifiable** — paper:390 — path; it occurred before any scored call, was invalidated, and the corrected — No implemented mechanical check proves or disproves this claim. Evidence: `paper:390`.
- (+892 further extracted claim(s) — mostly unverifiable prose — omitted here for brevity; all are labelled in S2/S4 with source lines.)

## Comment

Recommendation: 3/6. No headline result is mechanically supported yet, so the recommendation stays borderline pending stronger evidence. Most useful next step for the authors — For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?

## Panel Reviews (provenance)

### Panel review 1 — theorist (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper presents Mini Artichokes, a five-call program-repair system that generates multiple candidate repositories, preserves task-level solutions that pass complete official tests as byte-exact anchors, and applies two final repair routes only to unresolved tasks. Its central formal result is a test-label preservation property under task modularity and verifier assumptions. Empirically, the system substantially outperforms one- and two-call baselines on several test-available repair suites, but the evidence does not isolate whether recursive verification, semantic overlap, or simply additional model calls and candidate diversity produce the gains.

## Strengths

- The paper identifies a practically meaningful systems principle: “a complete verified task state is removed from model discretion, only unresolved units are branched, and passing states from heterogeneous routes are recursively promoted.” This gives the method a clear operational interpretation.

- The preservation mechanism is precisely specified. Under A1–A5, the paper proves that recursive promotion preserves every previously observed pass: “no unverified merged state is created.” The use of complete allowlisted file tuples rather than line-wise patch merging is technically appropriate for avoiding regression.

- The evaluation retains complete benchmark tracks rather than selecting favorable tasks. For example, the paper evaluates “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” and later all 39 Go and 49 JavaScript tasks.

- The empirical system-level improvements are substantial. On the original 90 tasks, Mini Artichokes achieves “59/90 (65.6%),” compared with “15/90 (16.7%) for Plain” and “45/90 (50.0%) for ordinary repair.” The frozen JavaScript result is also strong: “47/49” versus “42/49” for ordinary repair and “27/49” for Plain.

- The authors are unusually candid about the limits of their claims. They explicitly state that semantic overlap is “not established” as a repeatable standalone effect and that the results are “effectiveness comparisons with additional bounded calls, not compute efficiency.”

- The paper includes meaningful negative and boundary evidence: the strict agreement gate solves “5/20 versus 7/20,” QuixBugs is at a “40/40” ceiling, and HumanEvalFix reaches “164/164” already with ordinary repair. These results prevent the method from being presented as universally beneficial.

## Weaknesses

- The primary system comparison does not establish a structural advantage over Plain Codex at matched resources. Mini Artichokes uses five calls, whereas Plain uses one and ordinary repair uses two. The reported +44 tasks over Plain is therefore confounded by “candidate diversity, external execution, the verified floor, and both final routes.” This demonstrates bounded-compute effectiveness, but not that the proposed architecture is superior to a comparably resourced generic strategy.

- The strongest same-call evidence is exploratory or post hoc. The original equal-call result, “59/90 versus 54/90,” was chosen after “final-route crossovers were observed”; the Go replacement was run “only after TOV outcomes were known”; and the paper itself reports exact ties on the prospectively frozen JavaScript track (“Mini and Direct∪Generic are an exact tie”) and on HumanEvalFix (“zero over ordinary repair”). Thus the central architectural advantage is not prospectively established.

- The semantic-overlap component is not supported as a reliable causal contribution. In the original 90-task comparison TOV beats the semantic-free control by seven tasks, but the newly frozen replications yield “+1.2/34” and “+0.4/26,” with confidence intervals “[-2.35,+8.24] pp” and “[-6.92,+11.54] pp.” The Go replacement comparison is also nonsignificant: “33/39 versus 31/39” with `p=.3125`. The paper appropriately acknowledges this, but it substantially weakens the novelty claim around TOV.

- The semantic-free control is only a natural-language ablation. The paper concedes that it “cannot make latent model trajectories identical,” and that it matches “named instructions, not latent reasoning or exact realized compute.” Since prompting differentially changes model attention and behavior, the observed TOV/control difference cannot cleanly be attributed to semantic relations.

- The formal result is correct but relies on strong assumptions that substantially limit generality. A1 requires task-local verifier independence, A2 requires isolated workspaces, and A5 requires fail-closed verification. The property then follows almost directly from copying states already observed to pass. The paper admits that “repositories with global build state or nondeterministic tests require a coarser promotion unit,” but does not evaluate such settings.

- The main benchmark gains may be specific to the unusually favorable test-available, task-modular setting. The paper states that “failure stdout can nonetheless reveal behavioral expectations” and that this is “not a standard one-shot leaderboard protocol.” More evidence is needed to show that the method transfers to realistic repositories, weaker tests, cross-task dependencies, or test-unavailable repair.

- Whole-track calls make the experimental unit and reproducibility interpretation difficult. Although task-level paired tests are reported, “each task vector is generated inside one whole-track call,” so the many task observations are strongly correlated. The authors provide cluster-level caveats, but only five sessions in each of two fixed tracks are insufficient to support broad population-level claims.

- The paper does not provide a genuinely compute-matched generic baseline with the same five-call budget and comparable opportunity to use verification and multiple routes. The “Non-overlap dual-route union” is a useful control, but it was designed after observing route crossovers, and the prospectively frozen JavaScript comparison ties. Consequently, the paper establishes that this particular portfolio can be effective, not that recursive verified redundancy is the best generic way to spend five calls.

## Questions for the Authors

1. Can you provide a prospectively frozen five-call baseline that allocates the same total calls, model, token/time budget, and verifier access using a generic strategy, without post hoc route selection?

2. What is the incremental contribution of each mechanism—candidate diversity, byte-exact anchoring, TOV, direct repair, and recursive promotion—in a factorial or sequential ablation?

3. How sensitive are the results to the fixed priority rules, task partition, file allowlist, failure-tail length, and verifier nondeterminism?

4. Can independent annotators verify the TOV ledger fields and determine whether the claimed semantic overlaps and falsification targets are actually correct?

5. Do the gains persist on repositories with cross-task build dependencies, weaker tests, or test suites that are unavailable during repair?

## Scores

Soundness: 3/4 — The formal preservation argument and reported measurements are coherent, but causal attribution and resource-matched evidence are limited.

Presentation: 3/4 — The paper is unusually transparent and well organized, though the many evaluation stages and overlapping claims make the evidence hierarchy difficult to follow.

Significance: 3/4 — Verified task-level preservation is practically useful for test-available repair, but its scope is narrower than general program repair.

Originality: 3/4 — The composition of task-level anchoring, unresolved-set branching, and recursive promotion is a plausible systems contribution, although its components are largely familiar.

Overall recommendation: 3/6 — Borderline; the system results are promising, but the central architectural and semantic claims need stronger prospective, compute-matched validation.

Confidence: 4/5 — The paper provides enough self-contained methodological and numerical detail for a substantive assessment, although the underlying artifacts and runs cannot be independently checked here.

## Ethics and Limitations

The work uses public code benchmarks and no human participants. It responsibly reports that tests and failure output may reveal behavioral expectations, and it discloses additional inference compute, tokens, and latency. The authors clearly state important limitations: correlated same-model candidates, few whole-track sessions, post hoc stages, test-label rather than semantic correctness, dependence on modular task boundaries, and the ceiling behavior on HumanEvalFix and QuixBugs. These limitations materially constrain the generality of the conclusions but are presented candidly.

## Comment

I recommend borderline acceptance at most. The most important issue is to separate the strong but narrow claim—task-level verified union can improve bounded-compute repair—from the stronger implied claim that Mini Artichokes or TOV provides a validated architectural advantage. A prospective, five-call, resource-matched generic baseline with precommitted analysis and mechanism-level ablations would substantially clarify what is genuinely responsible for the observed gains.

### Panel review 2 — experimentalist (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper proposes Mini Artichokes, a five-call program-repair system that combines three initial repair attempts, byte-exact anchoring of tasks that pass official tests, and two heterogeneous final repair routes. Its central guarantee is that recursive promotion preserves all observed task-level passes under assumptions A1–A5. Empirically, the system improves substantially over one- and two-call baselines on Aider Polyglot and reaches 164/164 on HumanEvalFixDocs, but the evidence for semantic-overlap reasoning as a causal or consistently superior component is weak and explicitly uncertain.

## Strengths

- The paper identifies a clear systems-level problem and gives a precise preservation mechanism: “a complete verified task state is removed from model discretion, only unresolved units are branched, and passing states from heterogeneous routes are recursively promoted.”

- The preservation argument is appropriately conditional and technically concrete. Under A1–A5, “no unverified merged state is created,” and the paper correctly distinguishes test-label preservation from semantic correctness.

- The evaluation retains complete tracks rather than selecting favorable tasks. For example, it reports “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” as well as complete Go, JavaScript, and HumanEvalFix tracks.

- The end-to-end results are substantial in the tested setting. Mini Artichokes obtains “59/90” versus “15/90” for Plain and “45/90” for ordinary repair, and on JavaScript obtains “47/49” versus “27/49” and “42/49.”

- The paper provides unusually candid controls and negative evidence. It states that the earlier strict overlap rule “solved 5/20 tasks versus 7/20,” that Go’s preregistered Generic call was “transport-null,” and that “JavaScript and HumanEvalFix are equal-call ties.”

- The authors appropriately narrow their causal claim. They explicitly conclude that semantic overlap is “a productive heterogeneous route, not a reliably superior standalone policy,” rather than presenting the original 90-task difference as definitive proof.

- The artifact and provenance reporting are strong: the paper reports “frozen protocols, complete task IDs, source commit, public task packets, evaluator hashes, candidate and final patches, bounded traces, ledgers, anchor maps, and paired reports.”

## Weaknesses

- The strongest empirical comparison is not compute-matched. The paper itself says that the systems are “matched on five nominal calls and identical 30-minute hard caps, not realized tokens,” while TOV uses different token counts and latency. Thus the result does not establish that the proposed structure is more effective per unit of inference compute.

- The central recursive result is partly a tautological best-of-two construction. The paper defines the recursive output as `V_rec(t)=max(V_F(t),V_D(t))`; therefore gains over either final route can arise simply from adding and verifier-selecting another route. The paper acknowledges that “Dominance over an included route is purchased with another route,” but the claimed algorithmic contribution beyond best-of-multiple verified candidates remains modest.

- The semantic-overlap evidence is highly vulnerable to post-hoc selection and trajectory variance. The stricter control “was frozen only after all TOV outcomes and the MAC v9 critique were known,” and the recursive composition “was chosen after the later crossovers.” The subsequent replications show wide uncertainty: Python has session differences “`+4,-2,+2,0,+2`,” while C++ has “`+1,-1,0,+5,-3`.”

- The reported task-level significance is not strong evidence of generalization because all tasks within a track share one whole-track model call. The paper correctly states that task-level tests “condition on the realized calls,” but the effective number of independent experimental units is closer to the small number of track-level sessions. The reported three-track sign checks are correspondingly weak (`p=.125` and `p=.5`).

- The main benchmark evidence is narrow in model and setting. “Every semantic call uses `gpt-5.6-luna` at medium reasoning,” and the experiments involve five Aider language tracks plus one HumanEvalFix configuration. This limits conclusions about model robustness, other agent runtimes, and broader program-repair distributions.

- The semantic ledger does not provide an independently verifiable semantic mechanism. The paper states that integrity checks “do not score the natural-language diagnoses for semantic correctness,” and that “ledger diagnoses were not independently annotated.” Consequently, it is unclear whether semantic overlap itself causes the gains or merely changes prompting and model trajectory.

- The benchmark setting may overstate practical reliability. The method depends on “a trusted external verifier” and bounded failure output, while the paper admits that it is “not a standard one-shot leaderboard protocol.” Passing supplied tests is also weaker than correctness beyond those tests, as the authors note.

- The comparison to ordinary repair and Plain is confounded by additional calls and external execution. The paper explicitly characterizes these as “nested one-, two-, and five-call systems,” so the large improvements establish bounded-compute effectiveness but not superiority as a generally preferable repair strategy.

## Questions for the Authors

1. Can you provide a prospectively frozen, token- or reasoning-budget-matched comparison between Mini Artichokes and a generic verified multi-attempt baseline with the same number of evaluator calls?

2. What is the performance of a simpler verifier-only best-of-five or best-of-three union using independent generic repair calls, without TOV, ledgers, or semantic-overlap instructions?

3. Can semantic ledger rows be independently annotated by blinded experts, and do overlap quality, disagreement type, or falsification success predict eventual verified repair?

4. How would the results change across multiple model seeds or independent sessions on each complete track, rather than one whole-track call per arm?

5. Which part of the gain is attributable to anchoring, candidate diversity, the second final route, and recursive promotion? A factorial ablation would substantially clarify the contribution.

6. Can the authors evaluate repositories with cross-task build dependencies, nondeterministic tests, or weaker test suites, where assumptions A1–A5 may not hold?

## Scores

Soundness: 3/4 — The preservation property is well specified and the empirical reporting is candid, but causal and generalization claims are limited by post-hoc design, shared-call dependence, and compute mismatch.

Presentation: 4/4 — The paper is unusually explicit about claim scope, chronology, controls, caveats, and experimental integrity.

Significance: 3/4 — Verified task preservation and route union are practically useful in test-available repair, but the demonstrated advance over simpler verified multi-attempt methods is not yet fully isolated.

Originality: 3/4 — The composition of immutable task anchors, unresolved-set branching, and verifier-based recursive promotion is a meaningful systems formulation, though several ingredients are established.

Overall recommendation: 3/6 — Borderline; the system results are promising, but stronger controlled evidence is needed to support the algorithmic and semantic-overlap claims.

Confidence: 4/5 — The paper provides enough self-contained detail to assess the methodology and evidence, although the underlying artifacts and runs cannot be independently rerun here.

## Ethics and Limitations

The paper uses public programming benchmarks and reports no human participants. It appropriately notes that failure output can reveal behavioral expectations and that benchmark passes do not establish correctness beyond supplied tests. The main limitations are substantial: one model and runtime, few independent sessions, post-hoc design of important controls and the recursive composition, non-token-matched comparisons, incomplete isolation of semantic-overlap effects, and reliance on task-local stable verifiers. The Go transport failure is handled transparently, but it further reduces the strength of the prospective equal-call evidence.

## Comment

I recommend borderline consideration. The paper’s strongest contribution is a clearly specified, auditable verifier-backed preservation and route-union procedure, and its complete-track results are encouraging. The most important issue is attribution: the authors should demonstrate whether Mini Artichokes improves over a simpler compute-matched generic verified multi-attempt/union baseline, with prospectively frozen repeated sessions. Without that comparison, the results show a useful bounded-compute engineering system, but do not yet establish a broadly superior repair algorithm or a reliable causal benefit from semantic overlap.

### Panel review 3 — scope_ablation (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper proposes Mini Artichokes, a test-available program-repair system that preserves complete passing task states as byte-exact anchors and recursively unions independently verified repairs. It also introduces TOV, an overlap-aware repair route that uses candidate agreement and disagreement to guide falsification. Across Aider and HumanEvalFixDocs, the system shows substantial effectiveness gains over one- and two-call baselines, but the evidence for TOV as a causal component is mixed and the strongest comparisons involve additional, unmatched computation.

## Strengths

- The central preservation mechanism is clearly specified and supported by a useful formal property. The paper states that “a complete verified task state is removed from model discretion” and defines conditions A1–A5 under which recursive promotion “passes every task in `A union (union_k S_k)`.”

- The evaluation retains complete benchmark tracks rather than cherry-picking tasks. The authors report “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” followed by complete Go, JavaScript, and HumanEvalFix evaluations.

- The system-level results are substantial within the stated test-available setting. On the original 90 tasks, Mini Artichokes reaches “59/90 (65.6%),” compared with “15/90 (16.7%) for Plain” and “45/90 (50.0%) for ordinary repair.” On JavaScript, it achieves “47/49” versus “42/49” for ordinary repair.

- The paper includes meaningful controls and does not reduce the comparison to Plain alone. The semantic-free structured control shares “the same ledger fields, counterexample-based falsification, and two audits,” while withholding candidate relations.

- The authors are unusually candid about the limits of the component claim. The claim table explicitly marks the “repeatable standalone semantic-relation effect” as “Not established,” and the discussion states that TOV is “a productive heterogeneous branch, not a reliably superior standalone policy.”

- Failure and integrity handling are treated as first-class concerns. The paper retains the Rust `fizzy` harm, reports the C++ forbidden `a.out`, and explains that the Go transport-null call “does not retroactively restore confirmation.”

## Weaknesses

- The main system comparisons confound the proposed mechanism with additional test-time computation. Mini Artichokes uses five calls, whereas Plain uses one and ordinary repair uses two; the paper itself says these are “effectiveness comparisons between nested one-, two-, and five-call systems.” Thus the large gains over Plain and ordinary repair do not isolate recursive verified redundancy or TOV.

- The strongest same-call evidence is not prospective and is partly selected after observing outcomes. The 59/90 versus 54/90 comparison was “chosen after observing crossovers,” and the paper acknowledges it is “a post-hoc equal-call system contrast.” The semantic-free control was also “frozen only after all TOV outcomes and the MAC v9 critique were known.” These choices substantially weaken causal interpretation.

- Prospective evidence does not demonstrate a reliable advantage for the proposed semantic route. The five-session replications have means of only “+3.53 pp” and “+1.54 pp,” with confidence intervals `[-2.35,+8.24]` and `[-6.92,+11.54]`. Go gives 33/39 versus 31/39 with `p=.3125`, while JavaScript and HumanEvalFix are exact ties. The evidence supports possible complementarity, but not a stable TOV effect.

- Recursive union is mechanically guaranteed to improve over an included route when routes have complementary passes, so its apparent gain is partly a selection/property of the verifier rather than evidence that the semantic reasoning is correct. The paper concedes that recursive dominance “uses an additional direct route” and “demonstrates stabilization in the test-available system, not a single-route semantic-relation effect.”

- The statistical precision is overstated if interpreted beyond the realized calls. Although task-level exact tests are reported, “all task rows within one arm share one whole-track model call,” and the track-level checks are explicitly “underpowered.” The 90-task aggregate therefore provides limited evidence about performance across independent sessions, languages, or model runs.

- The semantic intervention is not cleanly measurable. The authors state that the control “cannot make latent model trajectories identical,” that prompt wording can change attention, and that ledger diagnoses “were not independently annotated.” Consequently, it is unclear whether improvements arise from semantic overlap specifically, increased structure, different prompt attention, or extra output/computation.

- Generalization beyond modular, test-available repair is limited. The paper’s applicability contract assumes “task-local declared files,” “isolated workspaces,” and a “stable verifier,” while all evaluations use only one model/runtime and a small set of benchmark families. The conclusion should not travel broadly to general code agents or settings without executable tests.

## Questions for the Authors

1. Can you provide a prospectively frozen, call- and token-matched comparison of Mini Artichokes against a generic multi-attempt verifier across several independent sessions and benchmark families?

2. What is the incremental contribution of recursive promotion itself after fixing the total number of model calls? In particular, can you compare one final route, two final routes, and recursive union under the same total budget and frozen analysis?

3. How often does TOV’s semantic ledger produce a diagnosis that is independently judged correct, and do such diagnoses predict successful repairs better than the semantic-free ledger?

4. Can the complete task-level vectors and verifier receipts be released so that the reported rescue/harm counts and byte-preservation claims can be independently audited?

5. How does the method behave with weaker or noisy tests, cross-task build dependencies, larger repositories, or models other than `gpt-5.6-luna`?

## Scores

Soundness: 3/4 — The preservation construction is well specified and the reported experiments are carefully caveated, but causal attribution is weakened by post-hoc design choices, shared whole-track calls, and unmatched compute.

Presentation: 4/4 — The paper is unusually clear about claim hierarchy, chronology, controls, failure cases, and limitations.

Significance: 3/4 — Verified task-state preservation and recursive promotion are practically useful for test-available repair, though their scope is narrower than general program repair.

Originality: 3/4 — The composition of immutable verified anchors, unresolved-task branching, and verifier-only recursive promotion is a credible systems contribution, while its individual ingredients are largely established.

Overall recommendation: 3/6 — Borderline; the system result is promising, but stronger prospective and compute-matched evidence is needed to establish a general scientific advantage.

Confidence: 4/5 — The paper is sufficiently self-contained to assess its argument and evidence, though the underlying execution artifacts cannot be independently checked here.

## Ethics and Limitations

The paper uses public programming benchmarks and reports no human-participant concerns. It appropriately notes that test feedback can reveal behavioral expectations and labels the setting “test-available program repair.” The main limitations are the single model/runtime, few independent sessions, cumulative and partly post-hoc evaluation chronology, unmatched realized compute, possible weakness of benchmark tests, and dependence on task modularity and stable verifiers. The reported integrity violations and transport-null call are handled transparently, but they further reduce the strength of the confirmatory evidence.

## Comment

I recommend borderline acceptance/rejection depending on the venue’s tolerance for systems evidence. The most important issue is not the size of the observed gains, but whether they survive a prospectively frozen comparison against a generic multi-route verifier with matched total compute and multiple independent sessions. The current paper convincingly establishes a useful verifier-backed preservation mechanism in its test-available setting, but it does not yet establish that TOV or the full Mini Artichokes design provides a broadly generalizable causal advantage.
