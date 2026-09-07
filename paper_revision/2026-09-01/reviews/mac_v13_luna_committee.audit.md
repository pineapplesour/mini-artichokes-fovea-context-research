# ICML-Style Paper Review

## Paper and Evidence Identity

- Review method: full review — deterministic evidence audit + review panel. The panel's review is the official output; this document is its audit sidecar.
- Review Agent name/version: paper-reviewer / `sha256:9886349f92661c3c73b70f216a7038b741b47282d7624538ad207dd3fbb2d4c0`
- Review-agent spec path/hash: `review-agent-spec.md` / `sha256:08b13516a2cb0e5151c6b4dc24f98e6d191b35ee30d69ea300b2d6ff2d5a5945`
- Original paper identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:5a5ed887df8e59fb283814727fb271ccd0ef686ca10df20b671272f329bc9695` / `42091` bytes
- Derived Markdown identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:5a5ed887df8e59fb283814727fb271ccd0ef686ca10df20b671272f329bc9695` / `42091` bytes
- Original PDF page count: `n/a`
- Converter: `none (Markdown source)`
- Paper version/hash: `Mini_Artichokes_manuscript_v4.md` / `sha256:5a5ed887df8e59fb283814727fb271ccd0ef686ca10df20b671272f329bc9695`
- Evidence bundle reviewed: none (no evidence bundle supplied)
- Frozen at (UTC): `2026-09-02T17:45:13+00:00`

## Summary

We introduce Anchored Try--Semantic-Overlap--Verify (TOV),. It reports 83 quantitative result claim(s) and cites 10 prior work(s). Deterministic audit: 0 contradiction(s), 0 dishonest self-certification(s), 0 mechanical finding(s); 0 result claim(s) evidence-backed, 635 unverifiable. Overall recommendation: 3/6 [claim-001].

## Strengths

- The paper situates its contribution against prior work (10 citation(s); related-work section present).

## Weaknesses

- The deterministic audit proved no contradiction, arithmetic error, or integrity breach; the remaining concern is limited to claims that could not be independently verified (see Questions).

## Questions for the Authors

1. For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?
2. 83 extracted result/arithmetic claim(s) could not be checked against the supplied evidence and are listed with their source lines in the Evidence Trace — could the authors provide the underlying results?

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
- Frozen review identity: `sha256:e4b60e3196ae3083bbd29418789a0315e2b1723a4aef0f51df39551521df4b28`.
- Verdict labels digest: `sha256:94472116a506d52b6a53bf83914f0469130cf3c3116c46cbb0c7e6dda78ca158`.
- External citation snapshot digest: `sha256:01545e382bf7b0636dcadf97adfec0e438018ba58ffefc7b6167718586eab0a7`.
- Scientific judgment identity: `sha256:c19e08622c45107f53a143eb7275d5d9a4de5a132566ed874b9134bd53e8bc6c`.
- Review panel configuration: panel=3, model=`gpt-5.6-luna`, synthesis=area-chair.
- Panel reviewer `theorist`: prompt=`sha256:aff9361c7660b89fddf38d29d95a79acf9f03ef2c9f8feabbddbcbe4a6a54ec1`, response=`sha256:645b78d8d4f80d7ec317e15632e89dc95f72af7fbb267d00cd4cb7b67d199652`, status=ok.
- Panel reviewer `experimentalist`: prompt=`sha256:24a483eae425c90eaa7b9b3d7076273aa035e86b115c4ab0450f8ca5e8dcea12`, response=`sha256:1472019e7d75d5d713804a13d26c069d7a040b6d51c90390a6fe54c83217b15a`, status=ok.
- Panel reviewer `scope_ablation`: prompt=`sha256:d61648f5d77d6cbdad6f89d9baa8ef39078183fc9bbbbd2374b941b3caecc2b7`, response=`sha256:6692c79428667ec0a2f80dc50a842d9fc1e9d380f8310dff1972cfc7cd951c27`, status=ok.
- Output path: `mac_v13_luna_committee.md`.
- Frozen paper input: `Mini_Artichokes_manuscript_v4.md` (`sha256:5a5ed887df8e59fb283814727fb271ccd0ef686ca10df20b671272f329bc9695`).
- Frozen original identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:5a5ed887df8e59fb283814727fb271ccd0ef686ca10df20b671272f329bc9695`, 42091 bytes, page count=n/a).
- Frozen derived identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:5a5ed887df8e59fb283814727fb271ccd0ef686ca10df20b671272f329bc9695`, 42091 bytes).
- Frozen converter: `none (Markdown source)`.
- Pre-S1 sanitation: 0 trace(s), 0 injection finding(s).
- S1 parse inventory: 36 sections, 5 tables, 463 numeric tokens with source locations.
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
- S5 DRAFT/GROUND: 83 candidate comment(s), 83 retained, 0 deleted, 83 criticism comment(s) converted to questions.
- S2/S4 claim verdicts:
- [claim-013] **unverifiable** — paper:16 — run overlap-aware and direct structured repair from the same verified state, — No implemented mechanical check proves or disproves this claim. Evidence: `paper:16`.
- [claim-030] **unverifiable** — paper:33 — `[+4,-2,+2,0,+2]` on Python (mean +3.53 points; sign `p=.3125`; session — No implemented mechanical check proves or disproves this claim. Evidence: `paper:33`.
- [claim-031] **unverifiable** — paper:34 — bootstrap CI `[-2.35,+8.24]`) and `[+1,-1,0,+5,-3]` on C++ (mean +1.54 — No implemented mechanical check proves or disproves this claim. Evidence: `paper:34`.
- [claim-034] **unverifiable** — paper:36 — mean superiority is not established. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:36`.
- [claim-039] **unverifiable** — paper:39 — five-call overlap-plus-direct union scores 59/90, versus 54/90 for an equal-call — No implemented mechanical check proves or disproves this claim. Evidence: `paper:39`.
- [claim-048] **unverifiable** — paper:52 — can improve over one-pass generation, yet their composition is fragile. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:52`.
- [claim-055] **unverifiable** — paper:59 — can relations among failed candidate hypotheses improve the last repair call — No implemented mechanical check proves or disproves this claim. Evidence: `paper:59`.
- [claim-061] **unverifiable** — paper:65 — **semantic-relation value:** whether comparing what failed candidates mean — No implemented mechanical check proves or disproves this claim. Evidence: `paper:65`.
- [claim-062] **unverifiable** — paper:66 — improves repair beyond a final agent with the same candidates, evidence, — No implemented mechanical check proves or disproves this claim. Evidence: `paper:66`.
- [claim-065] **unverifiable** — paper:69 — complementary final-route crossovers into monotone system improvement. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:69`.
- [claim-089] **unverifiable** — paper:93 — **RQ1:** Does the complete anchored TOV system improve Plain, Graph, and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:93`.
- [claim-092] **unverifiable** — paper:97 — outperform generic and structured semantic-free final controls? — No implemented mechanical check proves or disproves this claim. Evidence: `paper:97`.
- [claim-105] **unverifiable** — paper:113 — complete tracks that expose both positive mean differences and large — No implemented mechanical check proves or disproves this claim. Evidence: `paper:113`.
- [claim-106] **unverifiable** — paper:115 — an exploratory equal-call dual-route comparison and repeated-session union — No implemented mechanical check proves or disproves this claim. Evidence: `paper:115`.
- [claim-174] **unverifiable** — paper:202 — priority affects provenance, not the observed pass label. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:202`.
- [claim-190] **unverifiable** — paper:228 — The semantic comparison is behavioral. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:228`.
- [claim-237] **unverifiable** — paper:274 — observed and is analyzed as exploratory rather than preregistered. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:274`.
- [claim-243] **unverifiable** — paper:291 — We report both the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:291`.
- [claim-269] **unverifiable** — paper:324 — Plain | 1 | Direct complete-track solve — No implemented mechanical check proves or disproves this claim. Evidence: `paper:324`.
- [claim-270] **unverifiable** — paper:325 — Graph | 1 | Requirement/invariant/counterexample graph, then edit — No implemented mechanical check proves or disproves this claim. Evidence: `paper:325`.
- [claim-271] **unverifiable** — paper:326 — Ordinary repair | 2 | Graph plus one generic execution-feedback repair — No implemented mechanical check proves or disproves this claim. Evidence: `paper:326`.
- [claim-272] **unverifiable** — paper:327 — Verified union | 3 | Deterministic task-wise union of passing `P/G/R` files — No implemented mechanical check proves or disproves this claim. Evidence: `paper:327`.
- [claim-273] **unverifiable** — paper:328 — Generic Critic | 4 | Verified union plus generic final repair — No implemented mechanical check proves or disproves this claim. Evidence: `paper:328`.
- [claim-274] **unverifiable** — paper:329 — Semantic-free structured | 4 | Union plus TOV ledger/falsification/audits, relations withheld — No implemented mechanical check proves or disproves this claim. Evidence: `paper:329`.
- [claim-275] **unverifiable** — paper:330 — **TOV v2** | **4** | Union plus semantic relations, disagreement falsification, and audits — No implemented mechanical check proves or disproves this claim. Evidence: `paper:330`.
- [claim-276] **unverifiable** — paper:331 — Non-overlap dual-route union | 5 | Recursive verified union of generic and semantic-free final routes — No implemented mechanical check proves or disproves this claim. Evidence: `paper:331`.
- [claim-277] **unverifiable** — paper:332 — **Recursive TOV union** | **5** | Recursive verified union of TOV and semantic-free final routes — No implemented mechanical check proves or disproves this claim. Evidence: `paper:332`.
- [claim-279] **unverifiable** — paper:334 — The supplement reports a — No implemented mechanical check proves or disproves this claim. Evidence: `paper:334`.
- [claim-283] **unverifiable** — paper:337 — That screen is not pooled with code results. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:337`.
- [claim-287] **unverifiable** — paper:343 — Its completed result froze prompts, anchor priority, ledger, — No implemented mechanical check proves or disproves this claim. Evidence: `paper:343`.
- (+605 further extracted claim(s) — mostly unverifiable prose — omitted here for brevity; all are labelled in S2/S4 with source lines.)

## Comment

Recommendation: 3/6. No headline result is mechanically supported yet, so the recommendation stays borderline pending stronger evidence. Most useful next step for the authors — For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?

## Panel Reviews (provenance)

### Panel review 1 — theorist (accepted)

# Review: Mini Artichokes: Recursive Verified Anchoring Stabilizes Semantic-Overlap Program Repair

## Summary

This paper proposes Anchored Try--Semantic-Overlap--Verify (TOV), a test-time program-repair procedure that preserves verifier-passing task solutions, compares unresolved candidate failures using behavioral relations, and recursively unions independently verified final routes. On 90 Aider Polyglot tasks, TOV substantially outperforms one-call and ordinary repair baselines, but the paper’s own replications show that semantic-overlap instructions do not produce reliable session-level superiority. The strongest contribution is therefore verified monotone anchoring and heterogeneous-route union; the causal claim about semantic overlap remains preliminary.

## Strengths

- The paper clearly separates system-level improvement from mechanism-level evidence: it distinguishes “candidate and anchor value,” “semantic-relation value,” and “recursive redundancy value.” This decomposition is conceptually important and avoids attributing the full `58/90` result to overlap alone.

- The anchoring rule is precise and practically meaningful. The paper states that “for every task with `max_j V_j(t)=1`... every listed solution file from that candidate” is frozen, and that “a final arm therefore cannot exchange a known pass for a speculative repair.” This gives a genuine monotonicity guarantee on the supplied test suites.

- The experimental coverage is stronger than a selected-task demonstration. The authors retain “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” and explicitly state that no task was “ranked, screened, removed, replaced, or topped up.”

- The paper includes relevant matched controls. The semantic-free structured control shares “the same ledger fields, counterexample-based falsification, and two audits as TOV,” while setting the relation field to `withheld-by-control`. This is substantially more informative than comparing only against Plain.

- The authors report failures and uncertainty candidly. They state that neither new replication establishes superiority at `.05`, with session intervals `[-2.35,+8.24]` and `[-6.92,+11.54]` percentage points, and explicitly conclude that semantic overlap is “promising but unconfirmed.”

- The recursive union has a valid mechanical property: “for every task passed by either route, the complete passing solution-file bytes are promoted.” The distinction between this verifier-backed guarantee and a model vote is well articulated.

## Weaknesses

- The central semantic-overlap mechanism is not established by the strongest evidence. The original comparison gives TOV `58/90` versus `51/90`, but the control was “frozen only after all TOV outcomes and the MAC v9 critique were known,” and the paper acknowledges that the comparison is “secondary.” The ten new paired sessions produce small positive means but wide intervals crossing zero. Thus the title’s stabilization claim is stronger than the demonstrated causal evidence.

- The semantic-free ablation is not a clean intervention on semantic relations. The paper concedes that the “natural-language ablation cannot make latent model trajectories identical” and that it matches “named instructions, not latent reasoning or exact realized compute.” Since TOV uses `6,608,440` input and `59,551` output tokens while the structured control uses `7,060,198` input and `54,728` output tokens, differences may reflect prompt-induced reasoning trajectories, context use, or output behavior rather than the proposed relation operation specifically.

- The statistical evidence is vulnerable to unit-of-analysis and selection effects. The impressive task-level result has track differences `[+2,+2,+3]`, whose three-track sign test is `.125`; the paper also reports that the recursive composition was “specified only after these repetitions revealed large branch crossovers.” The reported significant task-level tests therefore provide limited evidence for generalization beyond these realized calls and post hoc choices.

- The primary comparison conflates several mechanisms and budgets. TOV’s `58/90` versus Plain’s `15/90` reflects candidate diversity, execution feedback, anchoring, additional calls, and the final adjudicator, as the authors themselves note: “Candidate diversity, external execution, verified union, and a final call all contribute.” This is a useful end-to-end result, but it cannot support a specific claim that semantic overlap is responsible for most of the gain.

- The recursive result is partly tautological as a quality guarantee and does not isolate the value of TOV. The paper correctly says that recursive dominance “is mechanical and uses an additional direct route.” Consequently, `59/90` versus `54/90` demonstrates the value of externally verified union of two routes under these tests, but not that overlap-aware routing is intrinsically better than a sufficiently diverse alternative route.

- Generality is presently narrow. Only “three of six Aider languages are evaluated,” all semantic calls use “one model and runtime,” and the tasks are modular with informative external tests. The paper’s own operating-point description requires “a trusted external verifier” and failure output that is informative without revealing gold code, which limits claims about universal program repair or broader reasoning settings.

- The semantic interpretation is post hoc and not independently validated. The eight-task interface account was “formulated after the nine discordant tasks were known,” and “ledger fields are not independently labeled for diagnostic correctness.” Without blinded labeling, preregistered defect categories, or prospective prediction, the explanation of why overlap helps risks being a narrative fitted to outcomes.

- The source-call protocol violations weaken the integrity claims, even if the authors retain them in intention-to-treat analysis. The paper reports that “one C++ TOV call generated forbidden `a.out`” and that “both strict protocol-promotion gates fail.” This does not invalidate every result, but it is especially relevant when the proposed contribution depends on reliable artifact and anchor handling.

## Questions for the Authors

1. Can you provide a preregistered, multi-track replication in which the semantic-relation instruction is the only planned intervention and the primary unit is the whole-track session rather than the task?

2. How would TOV compare with a compute-matched control that receives the same candidate evidence and the same total prompt/output budget, but is allowed an alternative generic evidence-organization procedure rather than a relation field simply withheld?

3. What prospective, blinded protocol will test the claim that interface ambiguity or competing obligations moderate TOV’s benefit without using hidden outcomes from the target track?

4. How often does recursive union improve over the best included route after accounting for its additional direct route, latency, and token cost? Please report cost-quality frontiers rather than only pass counts.

5. What evidence shows that the verifier is sufficiently strong for the claimed monotonicity to transfer beyond the finite official suites, especially for tasks where tests are incomplete or adversarially weak?

## Scores

Soundness: 3/4 — The protocol and guarantees are coherent, but the semantic mechanism is supported mainly by post hoc, trajectory-sensitive evidence.

Presentation: 3/4 — The paper is unusually transparent and well organized, though the many nested comparisons make the evidentiary hierarchy easy to overread.

Significance: 3/4 — Verified anchoring and route union are practically useful, but the broader semantic-overlap contribution remains unconfirmed.

Originality: 3/4 — The combination of behavioral overlap, falsification, and immutable verified state is a plausible novel composition despite relying on familiar ingredients.

Overall recommendation: 3/6 — Borderline: promising system result, insufficiently decisive mechanism evidence for acceptance as a strong empirical claim.

Confidence: 3/5 — The paper is self-contained enough for substantive assessment, but the reported artifacts and implementation cannot be independently verified here.

## Ethics and Limitations

The use of public programming exercises and no human participants presents minimal direct ethical risk. The paper appropriately notes that failure output can reveal behavioral expectations and that the setting is “test-available program repair,” not ordinary one-shot generation. The main limitations are scientific: one model and runtime, only three languages, whole-track calls that induce correlated task outcomes, post hoc controls and recursive composition, finite test-suite validity, and unequal realized token and latency costs. The reported forbidden `a.out` artifact also indicates that protocol compliance remains an operational concern.

## Comment

I recommend borderline consideration. The paper’s most defensible contribution is a verifier-backed architecture that preserves passing subproblems and safely combines complementary repair routes; that result is clearly separated from the weaker semantic-overlap claim. The decisive revision would be a preregistered, compute-matched, multi-track replication that isolates semantic relations as the intervention and evaluates whole-session reliability rather than relying primarily on task-level discordance.

### Panel review 2 — experimentalist (accepted)

# Review: Mini Artichokes: Recursive Verified Anchoring Stabilizes Semantic-Overlap Program Repair

## Summary

This paper proposes Anchored Try--Semantic-Overlap--Verify (TOV), a code-repair procedure that preserves verifier-passing task artifacts, uses semantic relations among failed candidates, and recursively promotes independently verified repairs. On 90 Aider Polyglot tasks, TOV reaches 58/90 versus 51/90 for matched final controls, while the recursive two-route union reaches 59/90. The paper is unusually candid that semantic-overlap superiority is not reliably replicated, framing verified redundancy as the more stable finding.

## Strengths

- The paper evaluates complete benchmark tracks rather than selected tasks: it retains “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” and reports “No task is ranked, screened, removed, replaced, or topped up.”

- The anchor mechanism is clearly specified and operationally meaningful: “if any candidate passes the complete official suite for task `t`, all solution-file bytes for that task are frozen.” This directly addresses regression from later repair calls.

- The main comparison includes informative controls. The semantic-free control shares “the same ledger fields, counterexample-based falsification, and two audits as TOV,” while relations are withheld, making the proposed mechanism more directly testable than a Plain-only comparison.

- The paper reports rescue and harm accounting rather than aggregate accuracy alone. Against the stricter control, TOV has “eight rescues and one harm,” and the harm is retained and explained through the Rust `fizzy` example.

- The statistical reporting is appropriately cautious in several places. The authors explicitly state that neither five-session replication “establishes session-level superiority at `.05`” and that the recursive analysis is “exploratory.”

- The recursive union is a compelling systems construction. Because “for every task passed by either route, the complete passing solution-file bytes are promoted,” it provides a mechanically monotone guarantee on the supplied tests.

- The manuscript demonstrates strong experimental provenance, including “frozen protocols, complete task IDs, source commit, public task packets, evaluator hashes, candidate and final patches, bounded traces, per-task outcomes, ledgers, anchor maps, and paired reports.”

## Weaknesses

- The central semantic-overlap claim is not established by the prospective replications. The paper reports Python differences of `[+4,-2,+2,0,+2]` and C++ differences of `[+1,-1,0,+5,-3]`, with confidence intervals “including meaningful help and harm.” Thus the strongest evidence for semantic relations comes from the original, partly post hoc comparison rather than a consistently replicated effect.

- The semantic-free control was designed after seeing the TOV results: “The semantic-free structured control was frozen only after all TOV outcomes and the MAC v9 critique were known.” This makes the original 8-to-1 task-level contrast vulnerable to experimenter degrees of freedom, even though the authors appropriately label it secondary.

- The recursive result is not a compute-matched causal demonstration of TOV. The recursive union “uses an additional route,” and the paper itself concedes that “Recursive dominance over an included route is purchased with another route.” The 59/90 versus 54/90 result therefore supports a verified multi-route system, but not necessarily semantic overlap as the cause of improvement.

- The effective statistical sample is much smaller than 90 tasks for broad generalization. The paper acknowledges that “Only three language clusters exist” and that task-level tests “condition on those realized calls.” Since each entire track is generated by one whole-track call, task-level significance substantially overstates independent evidence about model behavior across tasks.

- The baselines are useful but not sufficiently broad to support a strong state-of-the-art claim. The ordinary repair arm is described as “a bounded execution-feedback realization,” and Graph is “a prompt-level realization rather than a full reproduction.” More competitive, carefully matched repair agents or established code-agent baselines would clarify whether TOV adds value beyond the particular prompt implementations.

- The semantic representation is not independently validated. The paper states that “Ledger fields are not independently labeled for diagnostic correctness,” so the claimed behavioral interpretation may be post hoc narrative rationalization rather than a reliably measured intermediate mechanism.

- There are protocol-compliance failures in the replication calls: “two ledgers preserved the exact ID set but not the frozen row order,” and “one C++ TOV call generated forbidden `a.out`.” Although the intention-to-treat handling is commendable, these violations weaken confidence in the strictness and reproducibility of the reported protocol.

- The practical cost is substantial and the paper offers no efficiency advantage. TOV requires “6,608,440” input tokens and “1,422.3” seconds for the final call, compared with 51/90 for the generic critic. The method may be worthwhile for quality-sensitive repair, but its deployment value depends on a stronger and more stable gain than currently demonstrated.

## Questions for the Authors

1. Can you run a preregistered replication in additional complete tracks, with the semantic-free control frozen before observing TOV outcomes, to distinguish a stable semantic-relations effect from trajectory noise?

2. What fraction of TOV’s original advantage remains when all final arms receive exactly matched realized input and output-token budgets, rather than only matched nominal caps?

3. How reliably do independent annotators or automated checks recover the four ledger fields—fault location, invariant, counterexample class, and edit intent—and does ledger accuracy predict rescue probability?

4. Can the recursive two-route system be compared against a compute-matched system with the same number of calls and verification opportunities but no semantic-overlap instruction?

5. How sensitive are the results to the fixed priority `R > G > P`, the failure-tail budget, and the particular model version `gpt-5.6-luna`?

## Scores

Soundness: 3/4 — The protocol and analyses are largely careful, but the primary mechanism evidence is partly post hoc and not replicated at session level.

Presentation: 4/4 — The paper is exceptionally clear about procedure, denominators, caveats, and exploratory versus confirmatory claims.

Significance: 3/4 — Verified artifact preservation and recursive promotion are practically relevant, but the incremental semantic-overlap contribution remains uncertain.

Originality: 3/4 — The combination of behavioral overlap, immutable anchors, and recursive verification is a meaningful systems contribution, although its components draw on established ideas.

Overall recommendation: 3/6 — Borderline; promising and unusually rigorous in disclosure, but the central causal claim needs stronger prospective evidence.

Confidence: 4/5 — The paper provides enough self-contained detail for a reasonably confident assessment, though the experimental artifacts cannot be independently rerun here.

## Ethics and Limitations

The study uses public coding tasks and no human participants, and it explicitly withholds private tests and gold implementations. However, test feedback can reveal behavioral expectations, so the distinction between test-available repair and ordinary code generation should remain prominent. The method also increases inference cost and may encourage substantial compute expenditure. The authors appropriately state limitations involving one model/runtime, correlated whole-track calls, only three languages, post hoc control design, finite test suites, protocol violations, and the inability of passing anchors to establish correctness beyond the official tests.

## Comment

I recommend borderline acceptance. The strongest contribution is the mechanically safe verified-union and recursive promotion framework, not yet a demonstrated universal benefit from semantic overlap. The most important revision is a preregistered, compute-matched replication with controls frozen in advance and enough independent whole-track sessions to determine whether semantic relations provide a reproducible gain beyond generic verified redundancy.

### Panel review 3 — scope_ablation (accepted)

# Review: Mini Artichokes: Recursive Verified Anchoring Stabilizes Semantic-Overlap Program Repair

## Summary

This paper introduces Anchored Try--Semantic-Overlap--Verify (TOV), a test-time program-repair procedure that preserves verifier-passing task solutions as immutable anchors and uses semantic comparisons among failed candidates to guide final repair. On 90 Aider Polyglot tasks across Rust, Python, and C++, TOV reaches 58/90, while a recursive union of heterogeneous repair routes reaches 59/90. The paper usefully distinguishes the strong end-to-end benefit of verified redundancy from the much less established causal benefit of semantic overlap.

## Strengths

- The paper cleanly isolates verified preservation as a system invariant: “if any candidate passes a task's complete official test command, all solution-file bytes for that task are frozen.” This is a concrete and practically important safeguard against critic-induced regressions.

- The evaluation retains complete benchmark tracks: “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” with “No task ... ranked, screened, removed, replaced, or topped up.” This substantially strengthens the ecological validity of the reported end-to-end comparison.

- The paper reports meaningful rescue/harm decompositions rather than only aggregate accuracy. For example, TOV versus the generic control has “seven rescues and no harms,” while the stricter comparison has “eight rescues and one harm.”

- The controls are thoughtfully designed. The semantic-free control “shares TOV's decision ledger, counterexample falsification, and two completion audits,” while withholding semantic relations. This is a substantially stronger comparison than a one-call Plain baseline.

- The authors are unusually candid about evidential limits. They explicitly state that “overlap-specific repeatable mean superiority is not established” and that recursive results are “exploratory.” This appropriately prevents the strongest system result from being overstated as a confirmed mechanism result.

- The replication analysis directly exposes instability: Python differences are `[+4,-2,+2,0,+2]` and C++ differences are `[+1,-1,0,+5,-3]`. Reporting these crossovers, rather than only the favorable original comparison, is valuable scientific practice.

- The artifact and integrity claims are concrete: “complete task IDs, source commit, public task packets, evaluator hashes, candidate and final patches, bounded traces, per-task outcomes, ledgers, anchor maps, and paired reports.” If made available as described, this would support unusually strong auditability.

## Weaknesses

- The central semantic-overlap mechanism is not established by the strongest evidence. The original 8-rescue/1-harm comparison was “review-triggered and post hoc,” while both new whole-track replication intervals include zero and show substantial crossovers. Thus the paper supports verified multi-route redundancy much more strongly than it supports semantic relations as the causal source of improvement.

- The recursive result is not a clean test of semantic overlap. The recursive system adds a direct route and was “specified only after these repetitions revealed large branch crossovers.” Its 59/90 versus 54/90 comparison therefore demonstrates the value of verifier-backed union over these realized routes, but cannot show that TOV's semantic representation is responsible for the gain.

- Several load-bearing components remain unablated. TOV combines candidate relations, disagreement-triggered falsification, a structured ledger, two audits, and a particular prompt realization. The semantic-free control removes the proposed relation field but cannot ensure equal latent attention or reasoning: the paper concedes that it “cannot make latent model trajectories identical.” There is no factorial or staged ablation showing which of these components produces the observed effect.

- The statistical evidence is vulnerable to limited independent replication. The authors note that “all task rows within one arm share one whole-track model call” and that only “three language clusters exist.” The task-level exact tests therefore provide evidence about these realized calls, not robust population-level generalization. The replication has only five sessions per track and still yields wide intervals.

- Generalization is narrow relative to the claims. The study uses “one model and runtime,” only “three of six Aider languages,” and a test-available setting with bounded failure output. The paper appropriately calls this a limitation, but the current evidence does not establish that semantic overlap transfers to other models, repair environments, unavailable-test settings, or non-code reasoning tasks.

- The comparisons are not fully compute matched in realized usage. The TOV final call uses 6,608,440 input tokens and 59,551 output tokens, compared with 7,060,198 and 54,728 for the semantic-free control, and takes 29.6 more seconds than the control. Since the paper claims quality rather than efficiency superiority, this is not fatal, but it complicates attribution to the semantic operation alone.

- The semantic analysis is partly retrospective and lacks independently labeled diagnostic ground truth. The paper states that “the eight-task interface pattern is post hoc and small” and that ledger fields “are not independently labeled for diagnostic correctness.” Consequently, the proposed explanation for why overlap helps remains plausible interpretation rather than validated evidence.

## Questions for the Authors

1. Can you provide a preregistered, factorial ablation separating semantic relations, disagreement-triggered falsification, the ledger, and the completion audits, ideally with multiple independent whole-track sessions?

2. How much of the TOV advantage remains when all final arms receive exactly matched input/output-token or wall-clock budgets rather than only matched call counts and caps?

3. Can you evaluate the method on additional models and the remaining Aider languages, while keeping the complete-track protocol and anchor restoration unchanged?

4. What independently verifiable evidence shows that the semantic ledger fields correctly identify fault locations, invariants, and counterexample classes, rather than merely rationalizing successful repairs after the fact?

5. For the recursive system, can you compare against an equal-call union containing the same direct route and a non-semantic alternative with otherwise identical prompt structure and output budget?

## Scores

Soundness: 3/4 — The protocol and caveats are strong, but the causal semantic-overlap claim is undermined by post hoc design and weak replication.

Presentation: 3/4 — The paper is unusually transparent and well organized, although the many nested system variants and analyses make the evidential hierarchy difficult to track.

Significance: 3/4 — Verified preservation and heterogeneous-route union are practically useful, but the broader semantic-overlap contribution remains conditional.

Originality: 3/4 — The combination of immutable verified anchors with behavioral overlap and falsification is a credible novel formulation, despite relying on familiar ingredients.

Overall recommendation: 3/6 — Borderline; the paper contains a valuable system idea and strong empirical candor, but needs stronger prospective evidence for its central mechanism.

Confidence: 3/5 — The paper is sufficiently self-contained to assess, but the main empirical claims depend on experiments and artifacts that cannot be independently rerun here.

## Ethics and Limitations

The study uses public programming exercises and no human participants, and it explicitly withholds private tests and gold implementations from the model. The authors appropriately acknowledge that failure output can reveal behavioral expectations and that the setting is test-available rather than ordinary one-shot generation. The main limitations are substantial: one model and runtime, three language tracks, correlated whole-track calls, finite test-suite correctness, unequal realized token usage, post hoc control and recursive analyses, and no independently validated semantic-diagnosis labels. The additional inference cost is also relevant for deployment, especially because “TOV uses four calls and the recursive system uses five.”

## Comment

I recommend borderline acceptance/rejection depending on the venue’s tolerance for exploratory systems evidence. The paper makes a convincing case that verifier-backed anchoring and union over heterogeneous repair routes can prevent regressions and improve realized benchmark performance. However, its central semantic-overlap mechanism is not yet reliably demonstrated: the original advantage is post hoc, the prospective replications cross substantially, and the recursive result adds another route after observing those crossovers. The most important next step is a preregistered, compute-matched, component-level ablation across additional models and complete tracks.
