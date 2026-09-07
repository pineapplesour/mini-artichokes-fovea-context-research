# ICML-Style Paper Review

## Paper and Evidence Identity

- Review method: full review — deterministic evidence audit + review panel. The panel's review is the official output; this document is its audit sidecar.
- Review Agent name/version: paper-reviewer / `sha256:9886349f92661c3c73b70f216a7038b741b47282d7624538ad207dd3fbb2d4c0`
- Review-agent spec path/hash: `review-agent-spec.md` / `sha256:08b13516a2cb0e5151c6b4dc24f98e6d191b35ee30d69ea300b2d6ff2d5a5945`
- Original paper identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:8aa96602e48e3438b83ef804849c974271822a8a176c9a91094d98749136e5b9` / `68539` bytes
- Derived Markdown identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:8aa96602e48e3438b83ef804849c974271822a8a176c9a91094d98749136e5b9` / `68539` bytes
- Original PDF page count: `n/a`
- Converter: `none (Markdown source)`
- Paper version/hash: `Mini_Artichokes_manuscript_v4.md` / `sha256:8aa96602e48e3438b83ef804849c974271822a8a176c9a91094d98749136e5b9`
- Evidence bundle reviewed: none (no evidence bundle supplied)
- Frozen at (UTC): `2026-09-05T01:15:02+00:00`

## Summary

In this paper, a "call" counts one complete Codex agent execution, which can. It reports 181 quantitative result claim(s) and cites 25 prior work(s). Deterministic audit: 0 contradiction(s), 0 dishonest self-certification(s), 0 mechanical finding(s); 0 result claim(s) evidence-backed, 1016 unverifiable. Overall recommendation: 3/6 [claim-001].

## Strengths

- The paper situates its contribution against prior work (25 citation(s); related-work section present).

## Weaknesses

- The deterministic audit proved no contradiction, arithmetic error, or integrity breach; the remaining concern is limited to claims that could not be independently verified (see Questions).

## Questions for the Authors

1. For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters. Could the authors clarify these?
2. 181 extracted result/arithmetic claim(s) could not be checked against the supplied evidence and are listed with their source lines in the Evidence Trace — could the authors provide the underlying results?

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
- Frozen review identity: `sha256:3e55f78dc229b0a89ba26269313a922f2d8f45cf09b95e46c29ecf424ee55fe9`.
- Verdict labels digest: `sha256:2d0ca3e382dd1c9f91cecfbc401ac0ff7aebfccc7e0f7852872d26e4781cd4b0`.
- External citation snapshot digest: `sha256:50960176ebe79c57028cdaef5999fb67d1a0c6fde5a557d4303b7e7d4e76af76`.
- Scientific judgment identity: `sha256:3cf14d9fe26d1cb85c5a425edc96196ef2680cb1a138456649cbe3628bfcdfcc`.
- Review panel configuration: panel=3, model=`gpt-5.6-luna`, synthesis=area-chair.
- Panel reviewer `theorist`: prompt=`sha256:fe881f2607de7ccb3eec2353c17530cb4378a4aaea99233a3a24bf6e8d870ea6`, response=`sha256:00f7cc2aa978848e000f8abbd77581a1079bb3f8b9bd2dc8a35589ec5fcb2092`, status=ok.
- Panel reviewer `experimentalist`: prompt=`sha256:4fc2e942b5cb85c00ed583bbdb6888b8b50b671a227870ab320bda237b419400`, response=`sha256:19086809801fbff2cab8dde1243c4d7ea32844e6efdbeb4b1ab4aacb15fc6388`, status=ok.
- Panel reviewer `scope_ablation`: prompt=`sha256:94a9d9d54fc87a3ec7833e251cfbe15dccebc7c67070d7f5a49b776a8e1f8cb9`, response=`sha256:74b7d0e6658599e31c8bcfef8dfb000feba33b3116f3a80fd8086387932d4404`, status=ok.
- Output path: `mac_v26_obligation_view_luna_high_committee.md`.
- Frozen paper input: `Mini_Artichokes_manuscript_v4.md` (`sha256:8aa96602e48e3438b83ef804849c974271822a8a176c9a91094d98749136e5b9`).
- Frozen original identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:8aa96602e48e3438b83ef804849c974271822a8a176c9a91094d98749136e5b9`, 68539 bytes, page count=n/a).
- Frozen derived identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:8aa96602e48e3438b83ef804849c974271822a8a176c9a91094d98749136e5b9`, 68539 bytes).
- Frozen converter: `none (Markdown source)`.
- Pre-S1 sanitation: 0 trace(s), 0 injection finding(s).
- S1 parse inventory: 42 sections, 11 tables, 825 numeric tokens with source locations.
- S3 ledger-trace: 0/0 metric-labelled values matched; 0 finding(s).
- S3 internal-consistency: 0 comparison(s), 0 finding(s).
- S3 arithmetic: 0 recomputation(s), 0 finding(s).
- S3 baseline-fairness: 0 explicit improvement claim(s), 0 finding(s).
- S3 negative-evidence: 0 discard/crash outcome(s), 0 omission finding(s).
- S3 citation-existence: 6 explicit identifier(s), 0 existence/title finding(s).
- S3 template-compliance: 1 contract trace(s), 0 finding(s).
- S3 injection-scan: 0 sanitation trace(s), 0 reviewer-directed instruction finding(s).
- S3 self-review-audit: 0 checklist item(s), 0 dishonest self-certification(s).
- S3 positioning: 25 cited reference(s), related-work section=True, 0 novelty/superiority claim(s), 0 overclaim finding(s), 0 positioning question(s).
- S5 DRAFT/GROUND: 181 candidate comment(s), 181 retained, 0 deleted, 181 criticism comment(s) converted to questions.
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
- [claim-176] **unverifiable** — paper:201 — These precedents mean that execution, repeated revision, and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:201`.
- [claim-216] **unverifiable** — paper:245 — priority affects provenance, not the observed pass label. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:245`.
- [claim-220] **unverifiable** — paper:252 — After its model call, the experiment — No implemented mechanical check proves or disproves this claim. Evidence: `paper:252`.
- [claim-232] **unverifiable** — paper:271 — The semantic comparison is behavioral. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:271`.
- [claim-245] **unverifiable** — paper:283 — The revised final gate therefore enumerates every observed compiler, — No implemented mechanical check proves or disproves this claim. Evidence: `paper:283`.
- [claim-284] **unverifiable** — paper:321 — `/tmp/artifacts/decision_ledger.json` with exactly one record for each frozen — No implemented mechanical check proves or disproves this claim. Evidence: `paper:321`.
- [claim-290] **unverifiable** — paper:325 — They do not score the natural-language diagnoses for — No implemented mechanical check proves or disproves this claim. Evidence: `paper:325`.
- [claim-310] **unverifiable** — paper:346 — verification preserves every observed pass from either included route on the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:346`.
- [claim-312] **unverifiable** — paper:348 — The construction was formulated after final-route crossovers were observed and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:348`.
- [claim-340] **unverifiable** — paper:376 — tasks observed passing in included route `k`, and let `A` be the prior anchor — No implemented mechanical check proves or disproves this claim. Evidence: `paper:376`.
- [claim-344] **unverifiable** — paper:380 — complete state already observed to pass; no unverified merged state is — No implemented mechanical check proves or disproves this claim. Evidence: `paper:380`.
- [claim-345] **unverifiable** — paper:381 — Hence its observed task score is at least that of the prior anchor set — No implemented mechanical check proves or disproves this claim. Evidence: `paper:381`.
- [claim-361] **unverifiable** — paper:406 — We report both the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:406`.
- [claim-369] **unverifiable** — paper:416 — layer that separates a recognized displayed expectation from the observed — No implemented mechanical check proves or disproves this claim. Evidence: `paper:416`.
- (+986 further extracted claim(s) — mostly unverifiable prose — omitted here for brevity; all are labelled in S2/S4 with source lines.)

## Comment

Recommendation: 3/6. No headline result is mechanically supported yet, so the recommendation stays borderline pending stronger evidence. Most useful next step for the authors — For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters. Could the authors clarify these?

## Panel Reviews (provenance)

### Panel review 1 — theorist (accepted)

# Review: Mini Artichokes: Verifier-Gated Recursive Portfolios for Test-Available Program Repair

## Summary

This paper proposes a verifier-gated portfolio for program repair: successful task states become immutable anchors, while unresolved tasks are processed by heterogeneous final routes and promoted only after passing tests. The central claim is bounded-call system effectiveness, supported by results such as “Mini Artichokes solves 59/90” Aider tasks and “33/39” Go tasks. The paper appropriately distinguishes this from efficiency and from a claim that semantic overlap is uniformly superior.

## Strengths

- The preservation mechanism is clearly specified and formally justified. Under assumptions A1–A5, “no unverified merged state is created,” yielding a valid test-label preservation property. This is a useful safety invariant for task-modular repair.

- The principal evaluations retain complete tracks rather than selecting convenient tasks. The paper states that “No task is ranked, screened, removed, replaced, or topped up,” and reports complete denominators such as Rust30, Python34, C++26, Go39, and JavaScript49.

- The empirical reporting is unusually candid about confounds. The authors explicitly state that the five-call comparisons are “not token-matched,” that the aggregate comparison is “mixed-stage,” and that “the clean prospective JavaScript comparison is a tie.”

- The paper includes meaningful negative evidence. The earlier agreement-gated method solved “5/20 tasks versus 7/20,” and the motivating Java completion-lock improvement “does not repeat in five new whole-track pairs.” These results prevent the narrative from overstating semantic overlap.

- Protocol integrity is treated as part of the method. For Go, the paper reports “78/78 route-by-anchor file comparisons were exact,” exact ledger IDs, and `withheld-by-control` relation fields. This supports the claim that observed preservation was actually enforced.

## Weaknesses

- The primary effectiveness result is substantially confounded by additional model calls and compute. Mini uses “five calls,” whereas Plain uses one and ordinary repair uses two; the authors themselves call these “effectiveness comparisons between nested one-, two-, and five-call systems.” The only clean prospective equal-call Aider comparison, JavaScript49, is tied at “47/49.” Thus the paper does not yet show that the proposed structure beats a competitive same-budget alternative.

- The semantic-overlap component is not causally established. The strongest original comparison is explicitly “secondary because the stricter control was designed after the original outcomes,” while the Java replication found “no wins, two losses, three ties.” More importantly, the fresh Java comparison gives “18/47 for P/G/R+A+O versus 22/47 for P/G/R+A+B,” with overlap losing seven tasks and rescuing three. This supports overlap as a potentially useful route, but not as a demonstrated advantage.

- The formal theorem is correct but narrow and close to a construction-level invariant. It guarantees only that the promoted output passes “under the same verifier invocation used for promotion,” and the paper concedes that this is “not a claim of semantic correctness, verifier completeness, or reliability under nondeterministic tests.” The scientific value therefore depends almost entirely on showing that the added routes produce useful complementary passes under fair resource controls.

- The control does not isolate semantic guidance cleanly enough for strong attribution. The authors acknowledge that the semantic-free ablation “cannot equalize latent trajectories or realized compute.” Table 7 also shows different costs: TOV uses 6,608,440 input tokens and 59,551 output tokens versus 7,060,198 and 54,728 for the structured control, with TOV taking 1,422.3 seconds versus 1,392.7. The observed difference could therefore reflect prompt-induced trajectories, output budget usage, or compute allocation rather than the proposed relation operation.

- Generalization is limited by a single model/runtime and highly favorable task conditions. “All semantic calls use one model and runtime,” and the method assumes “modular task ownership, isolated workspaces, and a stable task verifier.” The repeated evidence consists of ten sessions on only Python34 and C++26, while HumanEvalFix Python reaches an ordinary-repair ceiling of “164/164.” These results establish a plausible operating regime, but not broad robustness across models, agents, repositories with shared state, weak verifiers, or unavailable tests.

- The statistical analysis is careful but cannot overcome the experimental unit limitations. The paper notes that “each task vector is also produced inside one whole-track call,” so task-level tests condition on a realized trajectory rather than providing independent task-level evidence. The reported small p-values therefore should not be interpreted as broad population-level confirmation.

## Questions for the Authors

1. Can you run a prospective, same-model comparison between Mini and a genuinely competitive five-call generic portfolio, with matched total tokens, latency, and tool/evaluator budgets? The current clean prospective result is “a tie” on JavaScript49.

2. What is the effect of recursive promotion when the competing system receives the same total number of calls and can spend the final calls on additional generic repair rather than on the TOV/direct route split?

3. Can the semantic-overlap claim be tested across multiple independently seeded whole-track sessions with a predeclared analysis, rather than relying primarily on the post hoc “8:1” original discordance?

4. How does the method behave when A1 fails—for example, shared solution files, cross-task build state, flaky tests, or a verifier that exposes misleading failure tails? Can you provide an explicit failure-mode evaluation?

5. Which gains remain when using models and runtimes other than “gpt-5.6-luna at medium reasoning,” and how sensitive are the results to public-benchmark contamination, especially given the acknowledgment that “public QuixBugs may occur in training data”?

## Scores

Soundness: 3/4 — The preservation invariant is sound under its explicit assumptions, but the empirical causal and resource-matched claims remain incomplete.

Presentation: 4/4 — The paper is exceptionally clear about chronology, denominators, controls, deviations, and limitations.

Significance: 3/4 — Verifier-backed preservation is practically relevant, but the incremental benefit over equally budgeted generic repair is not yet established.

Originality: 3/4 — The composition of immutable task anchors with recursive heterogeneous promotion is a meaningful systems idea, though it builds on familiar verification and iterative-repair mechanisms.

Overall recommendation: 3/6 — Borderline: the paper contains a real and carefully bounded contribution, but its strongest comparative claims are either call-confounded or unstable.

Confidence: 3/5 — The paper is self-contained and unusually transparent, but the decisive artifact results and trajectory-dependent comparisons cannot be independently verified here.

## Ethics and Limitations

The study uses public code exercises and no human participants, but it increases inference compute and exposes models to potentially informative failure output. The authors disclose calls, tokens, latency, licenses, and the risk that finite tests certify behavior rather than full correctness. The main ethical and scientific concern is therefore not misuse of data, but overgeneralizing test-label preservation into semantic correctness; the paper generally avoids that mistake.

## Comment

I recommend borderline consideration. The most important issue is a prospective, resource-matched comparison against a strong generic five-call repair portfolio, accompanied by repeated sessions for the semantic component. Until Mini demonstrates a repeatable advantage under that control, the evidence supports verifier-gated portfolio effectiveness in a favorable test-available setting, but not a decisive superiority claim for the proposed structure or semantic overlap.

### Panel review 2 — experimentalist (accepted)

# Review: Mini Artichokes: Verifier-Gated Recursive Portfolios for Test-Available Program Repair

## Summary

This paper proposes Mini Artichokes, a five-call program-repair portfolio that generates multiple candidates, freezes task-level solutions that pass the official verifier, and recursively promotes passing outputs from heterogeneous repair routes. The paper presents strong bounded-call effectiveness results—59/90 on three Aider tracks, 33/39 on Go, and 47/49 on JavaScript—but the evidence for an advantage over equally budgeted alternatives is substantially weaker and largely post hoc or mixed-stage.

## Strengths

- The paper clearly separates its scientific claims into “candidate and anchor value,” “semantic-relation value,” and “recursive redundancy value,” avoiding the common mistake of attributing the entire gain to semantic overlap.

- The preservation mechanism is precisely specified. The paper states that “a complete verified task state is removed from model discretion” and formalizes conditions A1–A5 under which “the construction copies either its prior anchored state or one complete state already observed to pass.”

- The experiments use complete task inventories rather than selected examples. For example, Table 3 reports all 39 Go tasks, and the paper explicitly states that “No task in either new track is ranked, screened, removed, replaced, or topped up.”

- The headline bounded-call results are substantial. On the original tracks, Mini solves 59/90 versus 45/90 for ordinary repair and 15/90 for Plain; on Go it reaches 33/39 versus 25/39 and 17/39; and on JavaScript it reaches 47/49 versus 42/49 and 27/49.

- The paper demonstrates commendable negative-result discipline. It explicitly reports that “one Java completion-lock result also does not repeat in five new whole-track pairs” and that the clean prospective JavaScript comparison is tied at 47/49.

- The paper provides unusually detailed integrity and reproducibility information, including “prompt hashes,” “candidate and final patches,” “decision ledgers,” “anchor maps,” and repeated verifier audits with outcome hashes.

## Weaknesses

- The primary effectiveness comparisons are not resource-matched. Mini uses five whole-track model calls, while Plain uses one and ordinary repair uses two. The paper itself acknowledges that these are “effectiveness comparisons between nested one-, two-, and five-call systems, not efficiency.” Thus the large gains over Plain and ordinary repair establish that more structured test-time computation helps, but do not establish that Mini’s particular architecture is superior at a fixed compute budget.

- The strongest equal-call comparison is not cleanly prospective. Across five Aider tracks, Mini scores 139/178 versus 132/178 for Direct∪Generic, but the paper states that the aggregate is “mixed-stage,” that Go uses a replacement after a transport failure, and that “JavaScript is the only clean prospective equal-call track and is a tie.” Consequently, the central architectural superiority claim is not convincingly demonstrated prospectively.

- The semantic-overlap component is not causally isolated. The strict semantic-free control was “designed after the original outcomes,” and the paper concedes that the natural-language ablation “cannot make latent model trajectories identical.” The original 58/90 versus 51/90 contrast is therefore vulnerable to prompt and trajectory differences, while the five new Java replication pairs show no wins and two losses for completion-locked TOV.

- The statistical evidence is weaker than the task-level p-values suggest. The paper notes that “all task rows within one arm share one whole-track model call” and that task-level tests “condition on realized calls.” Treating correlated tasks within a single call as independent discordant observations can substantially overstate inferential strength. The more appropriate track/session-level evidence is limited: the original study has only three tracks, and the five-track aggregate is explicitly mixed-stage.

- The preservation theorem is mechanically correct but narrow in scientific scope. It guarantees preservation of observed test labels under A1–A5, not semantic correctness, robustness to hidden tests, or generalization. The paper acknowledges that “anchors preserve observed test labels, not correctness beyond those tests,” but the practical value of the method therefore depends heavily on verifier strength and task modularity.

- The baselines are mostly prompt-level realizations rather than strong implementations of competing code-agent systems. The paper states that Graph, ordinary repair, Generic Critic, and related methods are “bounded prompt realizations rather than complete reproductions,” and it does not compare against a matched full repository agent such as KIRA. This limits conclusions about state-of-the-art performance.

- The reported semantic mechanism remains under-validated. The paper says that “ledger diagnoses are not independently labelled,” so the claim that overlap improves repair through more accurate obligation identification is plausible but not directly measured.

## Questions for the Authors

1. Can you provide a genuinely prospective, equal-token or equal-time comparison between Mini and a generic verified portfolio, with the portfolio rule and all prompts frozen before any outcome is observed?

2. How do the conclusions change when inference is performed at the whole-track or session level rather than using task-level McNemar/binomial tests within correlated whole-track calls?

3. Can you quantify the contribution of each additional stage—candidate diversity, verified anchoring, TOV, direct routing, and recursive promotion—under matched calls and matched realized compute?

4. How often do the promoted solutions fail on hidden tests or broader regression suites, and can you evaluate whether task-wise promotion introduces cross-task integration failures on benchmarks with shared files or build state?

5. Can the semantic ledger be independently annotated or audited to test whether its obligation diagnoses are actually more accurate than those of the semantic-free control?

## Scores

Soundness: 3/4 — The verifier-gated construction is well specified and the empirical accounting is candid, but fixed-resource causal evidence is limited.

Presentation: 3/4 — The paper is unusually transparent and comprehensive, although the many evidence stages and mixed comparisons make the central claim difficult to isolate.

Significance: 3/4 — Reliable preservation and complementary repair could be useful in test-available settings, but the incremental advantage over generic equal-budget portfolios remains uncertain.

Originality: 3/4 — The recursive verifier-gated composition is a plausible systems contribution, while its individual ingredients overlap substantially with prior repair and test-time-compute methods.

Overall recommendation: 3/6 — Borderline; the bounded-call system results are promising, but the main architectural superiority claim requires cleaner prospective and resource-matched evidence.

Confidence: 3/5 — The paper is sufficiently detailed to assess conceptually, but the central numerical results and implementation behavior cannot be independently verified from the manuscript alone.

## Ethics and Limitations

The paper uses public code-repair tasks and no human participants, and it appropriately notes that failure output may reveal behavioral expectations. Its stated limitations are substantial: one model/runtime, correlated candidate errors, finite and potentially weak test suites, narrow modularity assumptions, mixed experimental stages, unequal realized compute, environment-version deviations, and possible benchmark contamination for QuixBugs. These limitations are honestly reported and materially constrain generalization.

## Comment

I recommend borderline acceptance at most. The strongest contribution is the fail-closed, verifier-backed preservation and recursive composition rule, supported by impressive bounded-call results. The most important issue is whether Mini provides a reproducible advantage over a generic portfolio with the same prospective protocol and genuinely matched compute; the current evidence is mixed-stage, post hoc in key places, and tied on the clean prospective JavaScript comparison.

### Panel review 3 — scope_ablation (accepted)

# Review: Mini Artichokes: Verifier-Gated Recursive Portfolios for Test-Available Program Repair

## Summary

This paper proposes a verifier-gated portfolio for modular, test-available program repair. Its central mechanism freezes complete passing task states as byte-exact anchors and applies additional repair only to unresolved tasks; as stated in the abstract, “the verifier, rather than a model vote or patch intersection, is the only promotion authority.” On the reported Aider tracks, Mini reaches 59/90 versus 45/90 for ordinary repair and 15/90 for Plain, but the strongest architectural comparisons remain limited and partly post hoc.

## Strengths

- The preservation mechanism is clearly specified and supported by a useful conditional argument. The paper states that “a complete verified task state is removed from model discretion” and formalizes the guarantee under assumptions A1–A5: the recursive output “passes every task in `A union (union_k S_k)`.” This is a genuine structural property, not merely an empirical claim.

- The evaluation retains complete benchmark tracks rather than selecting favorable tasks. The authors explicitly state: “No task is ranked, screened, removed, replaced, or topped up,” and Table 1 reports all 90 official Aider tasks. This substantially improves auditability relative to cherry-picked repair examples.

- The paper separates system effectiveness from component causality unusually well. Its claim hierarchy labels the 59/90 result as “End-to-end bounded-call effectiveness” while marking standalone semantic-relation superiority as “not established.” This restraint is reinforced by the statement that the work claims “strong bounded-call system effectiveness” but treats semantic overlap as only “a useful heterogeneous route.”

- The controls are thoughtfully designed. The semantic-free control shares “the same ledger fields, counterexample-based falsification, and two audits as TOV,” while its relation field is fixed to `withheld-by-control`. The paper also reports a negative result from an earlier consensus rule, where it “solved 5/20 tasks versus 7/20 for otherwise matched repair,” which motivates the current verifier-authorized design.

- The authors provide substantial reproducibility and integrity evidence. They report exact task counts, hashes, byte comparisons, ledger completeness, forbidden-path checks, and rerun stability; for example, JavaScript reproduced “the identical 47/49 task vector in both reruns.” These checks support the claimed preservation implementation, even though they do not establish broad generalization.

## Weaknesses

- The primary performance gains are strongly confounded by additional test-time compute. Mini uses five whole-track model calls, compared with one for Plain and two for ordinary repair, and the paper acknowledges that these are “nested one-, two-, and five-call systems.” Thus 59/90 versus 45/90 demonstrates effectiveness at a larger call budget, but does not isolate the value of recursive verification or semantic overlap from simply allowing more model executions.

- The fairest nominal-call comparison does not provide clean prospective evidence of architectural superiority. The paper reports 139/178 for Mini versus 132/178 for Direct∪Generic, but explicitly calls this “mixed-stage,” noting that “the original tracks are post hoc at this layer, Go is a replacement sensitivity, and prospective JavaScript is tied.” Since the only clean prospective equal-call track is tied at 47/49, the central superiority claim remains suggestive rather than convincingly causal.

- The semantic-overlap component is not shown to be stable. On the original tracks TOV has an advantage of 58/90 versus 51/90, but this stricter ablation “was designed after the original outcomes.” In five new Java pairs, TOV has “no wins, two losses, three ties,” and the paper reports that the initial Java rescue “does not repeat.” The authors appropriately downgrade the claim, but this leaves the proposed semantic mechanism without a reliable standalone effect.

- The semantic-free ablation cannot fully equalize the competing trajectories or computational resources. The paper concedes that it “cannot equalize latent trajectories or realized compute,” while Table 7 shows that TOV and the structured control differ in tokens and latency. Consequently, the observed route differences cannot be attributed solely to the presence or absence of semantic relations.

- Generalization is narrower than the broad systems framing may suggest. All core coding executions use “`gpt-5.6-luna` at medium reasoning,” and the paper states that “each task vector is also produced inside one whole-track call.” The evidence is therefore conditioned on one model/runtime and a small number of benchmark families, mostly related code-repair tasks. HumanEvalFix reaches a ceiling of 164/164 for ordinary repair, C++ reuses the same underlying tasks, and the authors note that public QuixBugs “may occur in training data.” These results provide useful boundary checks but do not establish broad transfer.

- The preservation theorem depends on a restrictive deployment contract and finite, potentially incomplete tests. The method requires that task solution files and verifiers “do not cross task boundaries,” that tests be stable, and that complete allowlisted file tuples can be copied safely. The paper itself cautions that anchors preserve “observed test labels, not correctness beyond those tests.” Shared repositories, flaky tests, cross-task build state, or weak test suites could therefore invalidate the practical guarantee.

## Questions for the Authors

1. Can you run a prospective, untouched-track comparison between Mini and a generic five-call verifier-gated portfolio with matched token, latency, and model budgets? The current JavaScript result is a tie, while the aggregate advantage is explicitly mixed-stage.

2. Which operations are actually load-bearing: initial anchoring, recursive promotion, semantic overlap, completion locking, or simply the number of final routes? A factorial ablation would substantially clarify the mechanism.

3. How does Mini perform across multiple independent sessions, models, and runtimes on the same complete tracks? The paper reports five pairs on two tracks, but these show substantial trajectory variation and do not support population-level inference.

4. What happens when task ownership is not modular or when tests share build state and files? Can the system detect violations of assumptions A1–A5 before applying recursive promotion?

5. Can the method be compared against a stronger complete repository-level repair agent, rather than only the paper’s bounded prompt realizations? The paper states, “We do not claim state-of-the-art superiority over a matched full repository agent such as KIRA.”

## Scores

Soundness: 3/4 — The preservation property and protocol checks are strong, but the empirical architectural claims remain confounded and unstable.

Presentation: 3/4 — The paper is unusually transparent and comprehensive, though its many evidence stages, controls, and caveats make the main causal message difficult to follow.

Significance: 3/4 — Verifier-gated preservation is practically meaningful for modular test-available repair, but broader impact is limited by the narrow setting and compute confounding.

Originality: 3/4 — The composition of immutable task anchors, unresolved-set branching, and recursive verifier promotion is a plausible systems contribution, although its ingredients build on established iterative repair and verification ideas.

Overall recommendation: 3/6 — Borderline: the system result is substantial, but the paper does not yet establish a clean, prospective, compute-matched advantage for its distinctive mechanisms.

Confidence: 4/5 — The paper provides enough self-contained protocol and result detail to assess the claims, although the underlying artifacts and executions cannot be independently verified here.

## Ethics and Limitations

The study states that it uses “public open-source exercises and no human participants,” and that models do not receive private tests or gold implementations. The disclosure that failure output may reveal “behavioral expectations” is appropriate. The principal concerns are increased inference compute, finite-test overfitting, possible benchmark contamination for public repair suites, and limited evidence across models and task populations. The licensing discussion is responsible, particularly the instruction to retain upstream notices when redistributing task files.

## Comment

I find the verifier-gated preservation rule technically sound and the complete-track evidence valuable, but recommend borderline acceptance because the main empirical advantage is obtained with more calls and the clean prospective equal-call comparison is a tie. The most important revision is a pre-specified, compute-matched evaluation that independently tests recursive promotion and semantic overlap across multiple fresh tracks and sessions; without that, the paper supports a useful bounded-call repair system more strongly than it supports the claimed architectural advantage.
