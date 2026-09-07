# ICML-Style Paper Review

## Paper and Evidence Identity

- Review method: full review — deterministic evidence audit + review panel. The panel's review is the official output; this document is its audit sidecar.
- Review Agent name/version: paper-reviewer / `sha256:9886349f92661c3c73b70f216a7038b741b47282d7624538ad207dd3fbb2d4c0`
- Review-agent spec path/hash: `review-agent-spec.md` / `sha256:08b13516a2cb0e5151c6b4dc24f98e6d191b35ee30d69ea300b2d6ff2d5a5945`
- Original paper identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:59b5439835781bdca67d56cc413139b773f02ae61c9d2ba3592f423747241d53` / `36080` bytes
- Derived Markdown identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:59b5439835781bdca67d56cc413139b773f02ae61c9d2ba3592f423747241d53` / `36080` bytes
- Original PDF page count: `n/a`
- Converter: `none (Markdown source)`
- Paper version/hash: `Mini_Artichokes_manuscript_v4.md` / `sha256:59b5439835781bdca67d56cc413139b773f02ae61c9d2ba3592f423747241d53`
- Evidence bundle reviewed: none (no evidence bundle supplied)
- Frozen at (UTC): `2026-09-02T17:33:32+00:00`

## Summary

We introduce Anchored Try--Semantic-Overlap--Verify (TOV),. It reports 67 quantitative result claim(s) and cites 10 prior work(s). Deterministic audit: 0 contradiction(s), 0 dishonest self-certification(s), 0 mechanical finding(s); 0 result claim(s) evidence-backed, 548 unverifiable. Overall recommendation: 3/6 [claim-001].

## Strengths

- The paper situates its contribution against prior work (10 citation(s); related-work section present).

## Weaknesses

- The deterministic audit proved no contradiction, arithmetic error, or integrity breach; the remaining concern is limited to claims that could not be independently verified (see Questions).

## Questions for the Authors

1. For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?
2. 67 extracted result/arithmetic claim(s) could not be checked against the supplied evidence and are listed with their source lines in the Evidence Trace — could the authors provide the underlying results?

## Scores

- Overall recommendation: 3/6 — Adopted from the review panel; rationale in the review's Scores section.
- Soundness: 3/4 — Adopted from the review panel; rationale in the review's Scores section.
- Presentation: 4/4 — Adopted from the review panel; rationale in the review's Scores section.
- Significance: 3/4 — Adopted from the review panel; rationale in the review's Scores section.
- Originality: 3/4 — Adopted from the review panel; rationale in the review's Scores section.
- Confidence: 3/5 — Adopted from the review panel; rationale in the review's Scores section.

## Ethics and Limitations

Paper text was treated only as data. The injection audit sanitized hidden HTML and Unicode format controls before claim analysis and found 0 reviewer-directed instruction attempt(s). Broader ethics and evidence-quality claims outside S3 remain unverifiable [claim-001].

## Evidence Trace

- Pipeline execution: `S1 parse -> S2 claims -> S3 mech-check -> S4 verdicts -> S5 compose -> S6 freeze`.
- Frozen review identity: `sha256:f00540826eb562380d1d6e63ba86c94df8c08af9f01187ff5ebb71a5cbb96f31`.
- Verdict labels digest: `sha256:2a2b564439abb67261ee911640fac396c8119fb5bd9b8dcd282977a99c955062`.
- External citation snapshot digest: `sha256:01545e382bf7b0636dcadf97adfec0e438018ba58ffefc7b6167718586eab0a7`.
- Scientific judgment identity: `sha256:3175d2aa14def38eb1ec3f25420b700318ca234af79cf53372f91399159e56ed`.
- Review panel configuration: panel=3, model=`gpt-5.6-luna`, synthesis=area-chair.
- Panel reviewer `theorist`: prompt=`sha256:cf2d05b2e38f54439f26949fffd87ca348097d67f7b5c58ca473ebe5fa7c8c17`, response=`sha256:3f4ddccb814fb8ccb8ee6ca28e71ae62129340adf34526e97d004c2a8d4b0c8c`, status=ok.
- Panel reviewer `experimentalist`: prompt=`sha256:a766dea82c1c90ecfc74fb9a2d43f8e6ece2f0a6150b58fa7f50e435728b3c33`, response=`sha256:8ee436e06bf2ecbc809d847dcf786b513547a6645066e2dff7b2fce253dcad1d`, status=ok.
- Panel reviewer `scope_ablation`: prompt=`sha256:acc41a32b040371049986ce19bad16f9fe104f4ea8259cc5130bf4c305025c1a`, response=`sha256:ca7ea160e1f5ae009f9bd9d545a93d3519fc14893f657f30a39842622711ae34`, status=ok.
- Output path: `mac_v12_luna_committee.md`.
- Frozen paper input: `Mini_Artichokes_manuscript_v4.md` (`sha256:59b5439835781bdca67d56cc413139b773f02ae61c9d2ba3592f423747241d53`).
- Frozen original identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:59b5439835781bdca67d56cc413139b773f02ae61c9d2ba3592f423747241d53`, 36080 bytes, page count=n/a).
- Frozen derived identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:59b5439835781bdca67d56cc413139b773f02ae61c9d2ba3592f423747241d53`, 36080 bytes).
- Frozen converter: `none (Markdown source)`.
- Pre-S1 sanitation: 0 trace(s), 0 injection finding(s).
- S1 parse inventory: 35 sections, 5 tables, 385 numeric tokens with source locations.
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
- S5 DRAFT/GROUND: 67 candidate comment(s), 67 retained, 0 deleted, 67 criticism comment(s) converted to questions.
- S2/S4 claim verdicts:
- [claim-027] **unverifiable** — paper:31 — `[+4,-2,+2,0,+2]` on Python (mean +3.53 points; sign `p=.3125`; session — No implemented mechanical check proves or disproves this claim. Evidence: `paper:31`.
- [claim-028] **unverifiable** — paper:32 — bootstrap CI `[-2.35,+8.24]`) and `[+1,-1,0,+5,-3]` on C++ (mean +1.54 — No implemented mechanical check proves or disproves this claim. Evidence: `paper:32`.
- [claim-033] **unverifiable** — paper:35 — a realized four-call system effect, while an overlap-specific repeatable mean — No implemented mechanical check proves or disproves this claim. Evidence: `paper:35`.
- [claim-034] **unverifiable** — paper:36 — advantage is not established. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:36`.
- [claim-042] **unverifiable** — paper:47 — can improve over one-pass generation, yet their composition is fragile. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:47`.
- [claim-049] **unverifiable** — paper:54 — can relations among failed candidate hypotheses improve the last repair call — No implemented mechanical check proves or disproves this claim. Evidence: `paper:54`.
- [claim-055] **unverifiable** — paper:60 — **semantic-relation value:** whether comparing what failed candidates mean — No implemented mechanical check proves or disproves this claim. Evidence: `paper:60`.
- [claim-056] **unverifiable** — paper:61 — improves repair beyond a final agent with the same candidates, evidence, — No implemented mechanical check proves or disproves this claim. Evidence: `paper:61`.
- [claim-076] **unverifiable** — paper:82 — **RQ1:** Does the complete anchored TOV system improve Plain, Graph, and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:82`.
- [claim-079] **unverifiable** — paper:86 — outperform generic and structured semantic-free final controls? — No implemented mechanical check proves or disproves this claim. Evidence: `paper:86`.
- [claim-092] **unverifiable** — paper:101 — complete tracks that expose both positive mean differences and large — No implemented mechanical check proves or disproves this claim. Evidence: `paper:101`.
- [claim-160] **unverifiable** — paper:188 — priority affects provenance, not the observed pass label. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:188`.
- [claim-176] **unverifiable** — paper:214 — The semantic comparison is behavioral. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:214`.
- [claim-210] **unverifiable** — paper:257 — We report both the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:257`.
- [claim-236] **unverifiable** — paper:290 — Plain | 1 | Direct complete-track solve — No implemented mechanical check proves or disproves this claim. Evidence: `paper:290`.
- [claim-237] **unverifiable** — paper:291 — Graph | 1 | Requirement/invariant/counterexample graph, then edit — No implemented mechanical check proves or disproves this claim. Evidence: `paper:291`.
- [claim-238] **unverifiable** — paper:292 — Ordinary repair | 2 | Graph plus one generic execution-feedback repair — No implemented mechanical check proves or disproves this claim. Evidence: `paper:292`.
- [claim-239] **unverifiable** — paper:293 — Verified union | 3 | Deterministic task-wise union of passing `P/G/R` files — No implemented mechanical check proves or disproves this claim. Evidence: `paper:293`.
- [claim-240] **unverifiable** — paper:294 — Generic Critic | 4 | Verified union plus generic final repair — No implemented mechanical check proves or disproves this claim. Evidence: `paper:294`.
- [claim-241] **unverifiable** — paper:295 — Semantic-free structured | 4 | Union plus TOV ledger/falsification/audits, relations withheld — No implemented mechanical check proves or disproves this claim. Evidence: `paper:295`.
- [claim-242] **unverifiable** — paper:296 — **TOV v2** | **4** | Union plus semantic relations, disagreement falsification, and audits — No implemented mechanical check proves or disproves this claim. Evidence: `paper:296`.
- [claim-244] **unverifiable** — paper:298 — The supplement reports a — No implemented mechanical check proves or disproves this claim. Evidence: `paper:298`.
- [claim-248] **unverifiable** — paper:301 — That screen is not pooled with code results. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:301`.
- [claim-252] **unverifiable** — paper:307 — Its completed result froze prompts, anchor priority, ledger, — No implemented mechanical check proves or disproves this claim. Evidence: `paper:307`.
- [claim-264] **unverifiable** — paper:316 — This comparison is explicitly secondary. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:316`.
- [claim-269] **unverifiable** — paper:321 — Python34 was run first; C++26 was frozen — No implemented mechanical check proves or disproves this claim. Evidence: `paper:321`.
- [claim-270] **unverifiable** — paper:322 — and run as a second interface-heavy setting. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:322`.
- [claim-273] **unverifiable** — paper:327 — For every paired contrast we report full-denominator accuracy, rescues, harms, — No implemented mechanical check proves or disproves this claim. Evidence: `paper:327`.
- [claim-280] **unverifiable** — paper:333 — We separately reduce effects to — No implemented mechanical check proves or disproves this claim. Evidence: `paper:333`.
- [claim-287] **unverifiable** — paper:340 — We report the paired session differences, exact one-sided sign test over — No implemented mechanical check proves or disproves this claim. Evidence: `paper:340`.
- (+518 further extracted claim(s) — mostly unverifiable prose — omitted here for brevity; all are labelled in S2/S4 with source lines.)

## Comment

Recommendation: 3/6. No headline result is mechanically supported yet, so the recommendation stays borderline pending stronger evidence. Most useful next step for the authors — For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?

## Panel Reviews (provenance)

### Panel review 1 — theorist (accepted)

# Review: Mini Artichokes: Anchored Semantic-Overlap Verification for LLM Program Repair

## Summary

This paper proposes Anchored Try--Semantic-Overlap--Verify (TOV), which preserves test-verified candidate repairs as immutable anchors and uses structured comparison of unresolved candidates to guide a final repair call. On 90 Aider Polyglot tasks, TOV reaches 58/90 versus 51/90 for matched controls and 15/90 for one-call Plain. The paper is unusually candid that the large end-to-end gain is not an overlap-specific result: five-session replications yield small, statistically inconclusive mean improvements with substantial crossovers.

## Strengths

- The paper clearly separates system-level and mechanism-level claims: it asks whether “multiple attempts collectively solve more tasks” and separately whether “comparing what failed candidates mean improves repair.” This is an important distinction for evaluating test-time compute methods.

- The anchoring mechanism is concrete and operationally meaningful. The paper states that “if any candidate passes a task's complete official test command, all solution-file bytes for that task are frozen,” and that final adapters restore “all anchored bytes before evaluation.” This directly addresses regression from later critics.

- The evaluation retains complete benchmark tracks rather than selecting convenient tasks. It reports “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” with the table giving the complete counts of 30, 34, and 26 tasks.

- The paper provides a useful matched-control analysis. TOV and the semantic-free control share “the ledger, falsification, and audits,” while the relation field is withheld. The original contrast of 58/90 versus 51/90, with “eight rescues and one harm,” is more informative than comparing only against Plain.

- The authors appropriately distinguish realized evidence from general conclusions. They explicitly write that “the semantic-relation instruction is a promising but unconfirmed conditional mechanism,” and that the replication intervals “include meaningful help and harm.” This substantially improves the credibility of the presentation.

- Failure and protocol integrity are reported rather than hidden. For example, the paper states that “one C++ TOV call generated forbidden `a.out`” and that “both strict protocol-promotion gates fail.” Retaining this call in intention-to-treat analysis is good experimental practice.

## Weaknesses

- The central semantic-overlap claim is not established prospectively. The original result is 58/90 versus 51/90, but the newly frozen replications produce Python differences `[+4,-2,+2,0,+2]` and C++ differences `[+1,-1,0,+5,-3]`; neither replication is significant and both confidence intervals cross zero. Thus the evidence supports an interesting realized trajectory effect, not a reliable advantage of the proposed mechanism.

- The statistical unit is fundamentally limited by the whole-track calls. The paper acknowledges that “all task rows within one arm share one whole-track model call” and that task-level tests “condition on the realized calls.” The reported task-level p-values therefore cannot support broad population-level claims from 90 nominal task observations. The three-track sign checks and ten-session replication are the more relevant evidence, and those are underpowered and inconclusive.

- The semantic-free control is not a clean causal isolation of semantic relations. The authors concede that it “cannot make latent model trajectories identical” and that it matches “named instructions, not latent reasoning or exact realized compute.” TOV also uses 59,551 output tokens and 1,422.3 seconds versus 54,728 tokens and 1,392.7 seconds for the structured control. These differences may be small relative to the uncertainty, but they weaken attribution to semantic relations.

- The benchmark scope is narrow for a general program-repair claim. The study evaluates only three of six Aider languages, and the paper states that “language choice remains a scope decision.” The tasks are also modular and expose bounded failure output, so it remains unclear whether the method transfers to larger repositories, weaker tests, or settings without informative execution feedback.

- The strongest baseline comparison may overstate the practical gain from the proposed method. Plain solves only 15/90, while ordinary execution-feedback repair already reaches 45/90 and the verified union reaches 48/90. The paper correctly says the Plain contrast is “a realized four-call system effect,” but the practical incremental result over a strong repair baseline is 13/90, and the mechanism-specific result is only 7/90 in one original set and approximately 1–3.5 percentage points in the replications.

- The semantic interpretation is post hoc and weakly measured. The paper says the “interface-ambiguity account was formulated after the nine discordant tasks were known,” and that ledger fields are “not independently labeled for diagnostic correctness.” Consequently, the proposed explanation for why TOV helps is plausible but not validated as a predictor or moderator.

- Reusing immutable candidate artifacts in the replications tests final-stage session variance, not full-system reproducibility. The replications “reused the immutable candidate artifacts” and varied only the final calls. This is a reasonable targeted experiment, but it does not establish that the complete four-call pipeline remains superior when candidate generation is also rerun.

## Questions for the Authors

1. What preregistered experiment would you use to test the semantic-overlap mechanism while independently rerunning candidate generation and final adjudication across multiple tracks and sessions?

2. How much of the 7-task original advantage remains after matching TOV and control on realized input/output tokens, latency, and any differences in tool or workspace interaction?

3. Can you provide an evaluator-blinded, independently annotated analysis showing whether the four ledger fields predict TOV rescues better than generic failure traces alone?

4. How sensitive are the results to the choice of candidate priority `R > G > P`, the bounded failure-tail length, and the exact wording of the semantic-free prompt?

5. Does anchoring itself produce a statistically measurable gain over an otherwise identical final repair system that is allowed to modify previously passing tasks?

## Scores

Soundness: 3/4 — The protocol and caveats are strong, but the mechanism claim is supported mainly by one realized comparison and not by the replications.

Presentation: 4/4 — The paper is clear, well structured, quantitatively detailed, and unusually explicit about negative and invalidating evidence.

Significance: 3/4 — Verified anchoring and the separation of system versus mechanism effects are useful, but the general scientific impact is limited until the semantic component is shown to replicate.

Originality: 3/4 — The combination of immutable verified state with behavioral overlap and falsification is a meaningful integration, although its components draw substantially on existing verification and iterative-repair ideas.

Overall recommendation: 3/6 — Borderline: a valuable and careful empirical study, but not yet sufficient evidence for the paper’s principal semantic-overlap mechanism.

Confidence: 3/5 — The argument and reported evidence are self-contained, but the key numerical results and artifact integrity cannot be independently verified here.

## Ethics and Limitations

The use of public coding tasks and no human participants raises no major direct ethical concern. The paper responsibly discloses that bounded failure output can reveal behavioral expectations and therefore characterizes the setting as test-available repair. Its stated limitations are substantial and well taken: one model and runtime, correlated same-model candidates, whole-track call dependence, only three language clusters, cumulative rather than fully preregistered evidence, finite test-suite validity, prompt-induced trajectory variation, and post hoc semantic analysis. These limitations constrain the strength of the causal and generalization claims but do not invalidate the anchoring result itself.

## Comment

I recommend borderline consideration. The strongest contribution is the experimentally disciplined separation between a reliable verified-union floor and the much less certain value of semantic relations. The authors should make the latter claim explicitly exploratory and prioritize a preregistered, independently replicated experiment that reruns the complete pipeline, matches realized compute, and tests whether ledger-derived semantic overlap predicts gains before outcomes are known.

### Panel review 2 — experimentalist (accepted)

# Review: Mini Artichokes: Anchored Semantic-Overlap Verification for LLM Program Repair

## Summary

This paper introduces Anchored Try--Semantic-Overlap--Verify (TOV), a four-call program-repair procedure that preserves execution-verified candidate solutions as immutable anchors and uses semantic relations among failed candidates to guide final repair. On three complete Aider Polyglot tracks, TOV reaches 58/90 versus 15/90 for one-call Plain and 51/90 for both final controls. However, the newly frozen replications show small, statistically inconclusive mean gains, so the paper supports a strong realized end-to-end system effect but not a repeatable causal advantage from semantic overlap itself.

## Strengths

- The paper clearly separates system-level benefit from mechanism-level benefit: it explicitly distinguishes “candidate and anchor value” from “semantic-relation value,” which is an important experimental clarification.

- Verified anchoring is a concrete and plausible robustness mechanism. The paper specifies that “if any candidate passes the complete official suite for task `t`, all solution-file bytes for that task are frozen,” and reports that “Every final workspace matched its selected anchor bytes.”

- The benchmark coverage is unusually complete for this kind of study. The authors state that they retained “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks” and that no task was “ranked, screened, removed, replaced, or topped up.”

- The paper includes meaningful matched controls rather than relying only on Plain. The semantic-free control shares the “ledger, falsification, and audits” while withholding semantic relations, making the original mechanism comparison substantially more informative than a generic baseline comparison.

- The authors report full-denominator outcomes and rescue/harm accounting. In Table 2, TOV improves over the semantic-free control by “eight rescues and one harm,” rather than presenting only a favorable subset of unresolved tasks.

- The statistical interpretation is appropriately cautious. The paper explicitly states that the replication results “do not reproduce a reliable session-level mean advantage,” and reports confidence intervals crossing zero.

- The failure analysis is honest and useful. For example, the authors retain the Rust `fizzy` harm where “the final file contained an extra closing brace and did not compile,” showing that correct diagnosis is distinguished from successful execution.

- The paper provides substantial reproducibility metadata, including the benchmark commit, result hashes, protocol hashes, task IDs, ledgers, anchor maps, and intention-to-treat decisions.

## Weaknesses

- The central semantic-overlap claim is not established by the strongest evidence in the paper. The original TOV/control comparison is post hoc, while the prospective replications produce differences of `[+4,-2,+2,0,+2]` and `[+1,-1,0,+5,-3]`; both reported bootstrap intervals include zero. Thus the paper demonstrates a promising realized effect, not a reliable general mechanism.

- The main Plain comparison is heavily confounded by test-time compute. TOV uses four calls, whereas Plain uses one, and the paper itself acknowledges that “this contrast measures an expensive four-call system.” The 43-task improvement over Plain therefore cannot be attributed specifically to semantic overlap, verification, or anchoring.

- The control is not fully compute-matched. The paper reports that TOV uses “fewer input and more output tokens than the stricter control” and takes “29.6 more seconds in aggregate.” Because prompt structure and output budget affect model trajectory, the seven-task original advantage is not a clean estimate of semantic relations alone.

- The semantic-free ablation is vulnerable to prompt and attention confounding. The authors concede that it matches “named instructions, not latent reasoning or exact realized compute.” Removing a semantic field and explicitly prohibiting convergence-based reasoning may change the model's entire problem-solving behavior, not only the proposed relation mechanism.

- The evidence is concentrated in one model, one runtime, and three languages. The paper states that “all semantic calls use one model and runtime” and that “only three of six Aider languages are evaluated.” This substantially limits claims about universal program repair or robustness across models.

- The effective number of independent observations is small. Each complete language track is handled by one whole-track call, and the paper notes that task-level tests “condition on those realized calls.” The three-track sign checks are consequently underpowered, and the ten replication sessions remain only two fixed language contexts.

- The final-stage procedures are not specified sufficiently for independent scientific reproduction. The paper names the ledger fields and high-level operations, but does not provide the exact prompts, parsing rules, failure-tail formatting, patch-transfer implementation, or token/output caps needed to determine how much of the result depends on prompt engineering.

- The post hoc interface-ambiguity explanation is suggestive but weakly supported. The paper describes eight TOV-only tasks and says the account “was formulated after the nine discordant tasks were known.” Since the ledgers are not independently labeled for diagnostic correctness, this analysis cannot yet establish that semantic overlap is the cause of the gains.

- The reported replication protocol has at least one operational violation: “one C++ TOV call also violated the allowed-path rule by generating `a.out`.” Although retaining the call is commendably conservative, this raises questions about whether the procedure is sufficiently controlled for a deployment recommendation.

- The paper's contribution is partly a composition of known ingredients. It explicitly characterizes the work as “an execution-verified ensemble followed by a relational final repair,” while acknowledging that testing, critics, graphs, and auditing are individually not novel. The originality therefore depends on the causal value of the specific composition, which remains inconclusive.

## Questions for the Authors

1. What are the exact prompts, schemas, parsing rules, and adapter implementations for TOV and both controls, and can the semantic relation instruction be isolated through a less behaviorally intrusive manipulation?

2. How does TOV compare with a compute-matched control that receives the same token budget, equivalent structured evidence, and the same number of model-generated intermediate outputs but no semantic-overlap language?

3. Can the authors run a preregistered replication over the remaining Aider languages, multiple model versions, and multiple independent whole-track sessions before making a mechanism-level claim?

4. How were the candidate calls made independent, and how much diversity exists among their actual patches and failure hypotheses? Are the reported gains concentrated in a small number of unusually difficult or interface-heavy tasks?

5. What is the performance of a selector that chooses between direct and overlap-aware repairs using only pre-deployment evidence, and how is that selector calibrated without using hidden-test outcomes?

6. How sensitive are the results to anchor priority, failure-tail length, ledger format, output cap, and the requirement to restore anchored files?

## Scores

Soundness: 3/4 — The evaluation is carefully structured and candidly analyzed, but the central causal claim is weakened by post hoc control design, compute mismatch, and inconclusive replications.

Presentation: 3/4 — The paper is unusually transparent and well organized, though the many experimental layers and protocol qualifications make the primary evidential hierarchy somewhat difficult to follow.

Significance: 3/4 — Reliable anchoring and improved multi-call repair would be practically valuable, but the demonstrated semantic-overlap advantage is not yet robust enough for a stronger score.

Originality: 3/4 — The anchored decision boundary and behavioral-overlap framing are interesting compositions of established ideas, with novelty depending on an effect that remains uncertain.

Overall recommendation: 3/6 — Borderline; the realized system result is promising, but the mechanism claim and generality require stronger prospective evidence.

Confidence: 3/5 — The paper contains enough internal detail for a substantive assessment, but the conclusions depend on reported runs and implementation artifacts that cannot be independently checked here.

## Ethics and Limitations

The study uses public code exercises and does not involve human participants. The authors appropriately disclose that private tests and gold implementations are withheld, while acknowledging that failure output may reveal behavioral expectations. The principal limitations are substantial and well stated: finite test suites certify benchmark behavior rather than general correctness; the method costs four calls and additional latency; only one model and three languages are evaluated; whole-track calls create clustered observations; and the semantic-free control does not guarantee identical latent computation. These limitations should constrain the claims to a promising test-time repair procedure rather than a validated universal semantic-verification mechanism.

## Comment

I recommend borderline acceptance or weak rejection depending on the venue's evidence threshold. The paper's strongest contribution is the mechanically enforced verified floor and the careful separation of end-to-end system gains from semantic-overlap gains. The most important next step is a genuinely prospective, compute-matched, multi-session replication that isolates the semantic relation operation and demonstrates a reliable advantage over a direct final repair.

### Panel review 3 — scope_ablation (accepted)

# Review: Mini Artichokes: Anchored Semantic-Overlap Verification for LLM Program Repair

## Summary

This paper introduces Anchored Try--Semantic-Overlap--Verify (TOV), a multi-call program-repair procedure that preserves verified task solutions and uses behavioral relations among failed candidates to guide final repairs. On 90 Aider Polyglot tasks, TOV reaches 58/90 versus 51/90 for two matched final controls, but five-session replications show small, statistically inconclusive mean advantages and substantial crossovers. The paper therefore supports a strong realized-system improvement, while leaving the independent value of semantic overlap unestablished.

## Strengths

- The paper clearly separates end-to-end system benefit from mechanism-specific benefit: “This separates two scientific objects that are often conflated: candidate and anchor value; and semantic-relation value.” This is an important distinction for evaluating test-time systems.

- Verified preservation is a concrete and well-motivated design contribution. The paper states that “if any candidate passes a task's complete official test command, all solution-file bytes for that task are frozen,” and reports that “Every final workspace matched its selected anchor bytes.” This directly addresses regression caused by final critics.

- The evaluation is unusually complete for this setting. It retains “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” reports full-denominator results, and explicitly includes failures and harms. The paper also reports that TOV had “eight rescues and one harm” against the structured control rather than presenting only aggregate accuracy.

- The authors are commendably candid about the limits of the mechanism claim. They write that “an overlap-specific repeatable mean advantage is not established,” and report replication intervals of `[-2.35,+8.24]` and `[-6.92,+11.54]` percentage points.

## Weaknesses

- The central semantic-overlap claim is not convincingly established beyond the original, review-triggered comparison. The semantic-free control was “frozen only after all TOV outcomes and the MAC v9 critique were known,” while the five-session replications found no significant session-level advantage and large crossovers. Thus, the strongest evidence for the proposed mechanism is post hoc and clustered within a small number of realized calls.

- The experimental unit is much smaller than the reported task-level significance suggests. The paper acknowledges that “All task rows within one arm share one whole-track model call” and that task-level tests “condition on the realized calls.” With only three language clusters in the original comparison and five sessions per track in replication, the evidence does not support broad claims about population-level superiority.

- The study cannot isolate which components produce the large improvement over Plain. The authors correctly state that the Plain contrast “measures an expensive four-call system,” but the design does not provide a factorial ablation of candidate diversity, execution feedback, anchoring, ledger structure, falsification, and semantic relations. Consequently, the 43-task gain over Plain is informative operationally but weak evidence for TOV specifically.

- The controls do not fully resolve the possibility that prompt wording or additional output budget, rather than semantic relations, caused the difference. The paper admits that the semantic-free control matches “named instructions, not latent reasoning or exact realized compute,” while Table 4 shows that TOV used 59,551 output tokens versus 54,728 for the structured control and took 1,422.3 versus 1,392.7 seconds.

- Generalization is limited to one model, one runtime, three of six benchmark languages, and a test-available repair setting. The paper states, “Every semantic call uses `gpt-5.6-luna` at medium reasoning,” and acknowledges that “only three of six Aider languages are evaluated.” It is therefore unclear whether the mechanism depends on this model’s particular coding behavior, prompt sensitivity, or the selected language mix.

- The proposed post hoc interface-ambiguity explanation is under-supported. The paper says the pattern was “formulated after the nine discordant tasks were known” and that ledger fields “are not independently labeled for diagnostic correctness.” The listed examples are plausible, but they do not yet establish a predictive moderator or justify selective deployment.

- There is a nontrivial protocol-compliance concern in the replications. “One C++ TOV call also violated the allowed-path rule by generating `a.out`.” Although retaining this call in intention-to-treat analysis is appropriate, the incident indicates that the method’s operational reliability is not yet fully demonstrated.

## Questions for the Authors

1. Can you provide a factorial or otherwise controlled ablation separating verified anchoring, candidate diversity, execution feedback, ledger/falsification, and semantic relations?

2. Why was the semantic-free structured control designed after observing TOV outcomes, and can you run a preregistered comparison with frozen prompts and analysis before new results are collected?

3. What evidence supports the claim that interface ambiguity predicts TOV benefit prospectively, rather than merely describing the nine original discordant tasks?

4. How do results change across additional models, reasoning settings, and the remaining Aider languages?

5. Can the proposed evidence-only selector be evaluated without using private outcomes, and what calibration target or training data would it require?

## Scores

Soundness: 3/4 — The experimental accounting is careful and the limitations are candid, but mechanism attribution and population-level inference remain weak.

Presentation: 4/4 — The paper is unusually clear about protocols, denominators, controls, failures, and uncertainty.

Significance: 3/4 — Verified anchoring and the realized end-to-end gain are practically meaningful, though the incremental semantic-overlap contribution is not yet established.

Originality: 3/4 — The combination of immutable verified anchors with behavioral disagreement-driven falsification is a plausible and distinctive formulation, despite relying on several known ingredients.

Overall recommendation: 3/6 — Borderline: promising, well-presented work with strong realized-system evidence but insufficient prospective evidence for its central mechanism.

Confidence: 4/5 — The paper provides enough self-contained detail for a substantive assessment, although the underlying runs and artifacts cannot be independently rerun here.

## Ethics and Limitations

The use of public coding exercises and no human participants presents minimal direct ethical risk. The authors appropriately note that failure output can reveal behavioral expectations and that finite test suites do not establish correctness beyond the benchmark. The main limitations are scientific: one model and runtime, three language tracks, correlated whole-track calls, post hoc control design, weak cluster-level power, and substantial replication variance. The method also increases inference cost and latency, with the paper explicitly making “no efficiency or monetary-cost dominance” claim.

## Comment

I recommend borderline consideration. The strongest contribution is the careful demonstration that mechanically preserving verified task solutions can provide a robust floor within an expensive multi-call repair system. However, the paper’s central semantic-overlap mechanism is supported mainly by a post hoc 8:1 task contrast, while the prospective whole-track replications show small, non-significant means and large reversals. The most important next step is a preregistered, adequately replicated component ablation that isolates semantic relations from prompt wording, extra output, anchoring, and the other test-time operations.
