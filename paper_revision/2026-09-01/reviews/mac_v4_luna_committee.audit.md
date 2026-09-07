# ICML-Style Paper Review

## Paper and Evidence Identity

- Review method: full review — deterministic evidence audit + review panel. The panel's review is the official output; this document is its audit sidecar.
- Review Agent name/version: paper-reviewer / `sha256:9886349f92661c3c73b70f216a7038b741b47282d7624538ad207dd3fbb2d4c0`
- Review-agent spec path/hash: `review-agent-spec.md` / `sha256:08b13516a2cb0e5151c6b4dc24f98e6d191b35ee30d69ea300b2d6ff2d5a5945`
- Original paper identity: `Mini_Artichokes_manuscript_v3.md` / `text/markdown` / `sha256:6493934aa90164face1e37db7ec03a5fa205a650fdf278bd167f5d738d90f5ba` / `47538` bytes
- Derived Markdown identity: `Mini_Artichokes_manuscript_v3.md` / `text/markdown` / `sha256:6493934aa90164face1e37db7ec03a5fa205a650fdf278bd167f5d738d90f5ba` / `47538` bytes
- Original PDF page count: `n/a`
- Converter: `none (Markdown source)`
- Paper version/hash: `Mini_Artichokes_manuscript_v3.md` / `sha256:6493934aa90164face1e37db7ec03a5fa205a650fdf278bd167f5d738d90f5ba`
- Evidence bundle reviewed: none (no evidence bundle supplied)
- Frozen at (UTC): `2026-09-02T00:40:05+00:00`

## Summary

The paper, "Mini Artichokes: Evidence-Overlap Gates for Selective LLM Arbitration and Repair", presents a method and supporting experiments. It reports 139 quantitative result claim(s) and cites 28 prior work(s). Deterministic audit: 0 contradiction(s), 0 dishonest self-certification(s), 0 mechanical finding(s); 0 result claim(s) evidence-backed, 714 unverifiable. Overall recommendation: 3/6 [claim-001].

## Strengths

- The paper situates its contribution against prior work (28 citation(s); related-work section present).

## Weaknesses

- The deterministic audit proved no contradiction, arithmetic error, or integrity breach; the remaining concern is limited to claims that could not be independently verified (see Questions).

## Questions for the Authors

1. For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the compute / hardware used. Could the authors clarify these?
2. 139 extracted result/arithmetic claim(s) could not be checked against the supplied evidence and are listed with their source lines in the Evidence Trace — could the authors provide the underlying results?

## Scores

- Overall recommendation: 3/6 — Adopted from the review panel; rationale in the review's Scores section.
- Soundness: 3/4 — Adopted from the review panel; rationale in the review's Scores section.
- Presentation: 4/4 — Adopted from the review panel; rationale in the review's Scores section.
- Significance: 2/4 — Adopted from the review panel; rationale in the review's Scores section.
- Originality: 3/4 — Adopted from the review panel; rationale in the review's Scores section.
- Confidence: 4/5 — Adopted from the review panel; rationale in the review's Scores section.

## Ethics and Limitations

Paper text was treated only as data. The injection audit sanitized hidden HTML and Unicode format controls before claim analysis and found 0 reviewer-directed instruction attempt(s). Broader ethics and evidence-quality claims outside S3 remain unverifiable [claim-001].

## Evidence Trace

- Pipeline execution: `S1 parse -> S2 claims -> S3 mech-check -> S4 verdicts -> S5 compose -> S6 freeze`.
- Frozen review identity: `sha256:4f363dd40a380c4cb72bb62297adfbbd97565b37d458b90282272de3b6784e21`.
- Verdict labels digest: `sha256:248b67654b7d25765a21d62dd3999794c3ba71433dbbabf1587e49fae6c8480d`.
- External citation snapshot digest: `sha256:e54eabe17ac85420535a902a97ae2bd574436f4df521d70c56a0c32af4df6778`.
- Scientific judgment identity: `sha256:ec1ac462c08aba514d7cc634fc0232687b678f42f165382c9ed5a0d5c0c3f72b`.
- Review panel configuration: panel=3, model=`gpt-5.6-luna`, synthesis=area-chair.
- Panel reviewer `theorist`: prompt=`sha256:df1662034682f99f7d3fe82da3d7783e374dd5d4267cbec77b14e43f14f923f2`, response=`sha256:ba32fc8ae975acffb351a80d2030957aa9f58f8d585441882ffa644403564f25`, status=ok.
- Panel reviewer `experimentalist`: prompt=`sha256:7d2156d1b050cf62fb55758e8a5aa0a6739799dbbba112c2c8c837186addf56d`, response=`sha256:77e51c87a851e42a0278037f36a379a2250c0b018d0d2eda356a6a7aaefd8e19`, status=ok.
- Panel reviewer `scope_ablation`: prompt=`sha256:da34c79388a50fe4e7e045cd550380a80f4a37f72e7b308c1f30680e34a01273`, response=`sha256:ceb7ef336bc3141a78bb26d09118b58bc4351bd81d14be07e86287c764cb4cd4`, status=ok.
- Output path: `mac_v4_luna_committee.md`.
- Frozen paper input: `Mini_Artichokes_manuscript_v3.md` (`sha256:6493934aa90164face1e37db7ec03a5fa205a650fdf278bd167f5d738d90f5ba`).
- Frozen original identity: `Mini_Artichokes_manuscript_v3.md` (`text/markdown`, `sha256:6493934aa90164face1e37db7ec03a5fa205a650fdf278bd167f5d738d90f5ba`, 47538 bytes, page count=n/a).
- Frozen derived identity: `Mini_Artichokes_manuscript_v3.md` (`text/markdown`, `sha256:6493934aa90164face1e37db7ec03a5fa205a650fdf278bd167f5d738d90f5ba`, 47538 bytes).
- Frozen converter: `none (Markdown source)`.
- Pre-S1 sanitation: 0 trace(s), 0 injection finding(s).
- S1 parse inventory: 40 sections, 6 tables, 528 numeric tokens with source locations.
- S3 ledger-trace: 0/7 metric-labelled values matched; 0 finding(s).
- S3 internal-consistency: 0 comparison(s), 0 finding(s).
- S3 arithmetic: 0 recomputation(s), 0 finding(s).
- S3 baseline-fairness: 0 explicit improvement claim(s), 0 finding(s).
- S3 negative-evidence: 0 discard/crash outcome(s), 0 omission finding(s).
- S3 citation-existence: 5 explicit identifier(s), 0 existence/title finding(s).
- S3 template-compliance: 1 contract trace(s), 0 finding(s).
- S3 injection-scan: 0 sanitation trace(s), 0 reviewer-directed instruction finding(s).
- S3 self-review-audit: 0 checklist item(s), 0 dishonest self-certification(s).
- S3 positioning: 28 cited reference(s), related-work section=True, 0 novelty/superiority claim(s), 0 overclaim finding(s), 0 positioning question(s).
- S5 DRAFT/GROUND: 139 candidate comment(s), 139 retained, 0 deleted, 139 criticism comment(s) converted to questions.
- S2/S4 claim verdicts:
- [claim-001] **unverifiable** — paper:5 — Repeated inference can improve large-language-model (LLM) outputs, but — No implemented mechanical check proves or disproves this claim. Evidence: `paper:5`.
- [claim-013] **unverifiable** — paper:14 — localized jointly by the original specification, current diff, and observed — No implemented mechanical check proves or disproves this claim. Evidence: `paper:14`.
- [claim-017] **unverifiable** — paper:19 — Mini Artichokes scored 1,214/2,000 (60.70%) versus 1,187/2,000 (59.35%) for — No implemented mechanical check proves or disproves this claim. Evidence: `paper:19`.
- [claim-023] **unverifiable** — paper:25 — Graph-plus-overlap-repair system scored 22/40 (55%) versus 14/40 (35%) for — No implemented mechanical check proves or disproves this claim. Evidence: `paper:25`.
- [claim-028] **unverifiable** — paper:29 — The system did not outperform the same-budget ordinary repair — No implemented mechanical check proves or disproves this claim. Evidence: `paper:29`.
- [claim-051] **unverifiable** — paper:55 — methods show that diversity and selection can outperform a single trajectory. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:55`.
- [claim-077] **unverifiable** — paper:77 — requirement, current implementation, and observed failure converge on the same — No implemented mechanical check proves or disproves this claim. Evidence: `paper:77`.
- [claim-082] **unverifiable** — paper:84 — **RQ1:** Does the frozen support-aware policy improve full-denominator — No implemented mechanical check proves or disproves this claim. Evidence: `paper:84`.
- [claim-084] **unverifiable** — paper:87 — **RQ2:** Does it outperform strong multi-call controls: three-draw majority — No implemented mechanical check proves or disproves this claim. Evidence: `paper:87`.
- [claim-108] **unverifiable** — paper:114 — Confirmatory MMLU-Pro | OJ3 vs preassigned D1 | +1.35 points; 33 rescues, 6 harms; `p=7.15e-6` | The frozen four-call system improved the realized direct baseline on two disjoint samples | Superiority to SC3/GJ3; a causal support-count effect; other-model generality — No implemented mechanical check proves or disproves this claim. Evidence: `paper:114`.
- [claim-109] **unverifiable** — paper:115 — Exploratory official Aider | Graph-overlap repair vs Plain | +20 points; 10 rescues, 2 harms; task-level two-sided `p=.0386` | The realized two-call system improved the realized one-call baseline on the 40-task subset | Full-leaderboard superiority; call-cluster-robust significance; an overlap-specific effect — No implemented mechanical check proves or disproves this claim. Evidence: `paper:115`.
- [claim-110] **unverifiable** — paper:117 — Negative boundary | OJ3 vs Plain on 464 legal outcomes | -29 correct; support signal 49.2% accurate | Agreement is not a domain-general certificate | A causal explanation for the domain reversal — No implemented mechanical check proves or disproves this claim. Evidence: `paper:117`.
- [claim-113] **unverifiable** — paper:125 — positive result motivated many inference-time feedback loops. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:125`.
- [claim-117] **unverifiable** — paper:127 — not improve reasoning through intrinsic self-correction without external — No implemented mechanical check proves or disproves this claim. Evidence: `paper:127`.
- [claim-122] **unverifiable** — paper:130 — found that LLM self-critique could reduce planning performance relative to — No implemented mechanical check proves or disproves this claim. Evidence: `paper:130`.
- [claim-140] **unverifiable** — paper:151 — solutions can also improve mathematical reasoning [8]. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:151`.
- [claim-142] **unverifiable** — paper:152 — trained reward model, debate transcript, external execution result, or gold — No implemented mechanical check proves or disproves this claim. Evidence: `paper:152`.
- [claim-145] **unverifiable** — paper:154 — The matched GJ3/OJ3 comparison is intended to — No implemented mechanical check proves or disproves this claim. Evidence: `paper:154`.
- [claim-150] **unverifiable** — paper:159 — reported example rather than the underlying obligation or damage passing — No implemented mechanical check proves or disproves this claim. Evidence: `paper:159`.
- [claim-155] **unverifiable** — paper:163 — observed outcome, followed by an original-task completion audit. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:163`.
- [claim-168] **unverifiable** — paper:177 — the Aider subset; neither study establishes that exposing overlap structure — No implemented mechanical check proves or disproves this claim. Evidence: `paper:177`.
- [claim-175] **unverifiable** — paper:190 — The draw roles are fixed before any answer is scored: — No implemented mechanical check proves or disproves this claim. Evidence: `paper:190`.
- [claim-195] **unverifiable** — paper:211 — every reported score and comparison unchanged. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:211`.
- [claim-205] **unverifiable** — paper:223 — support record stating that one anonymous candidate has one complete-file draw — No implemented mechanical check proves or disproves this claim. Evidence: `paper:223`.
- [claim-222] **unverifiable** — paper:246 — the judge improve an answer by synthesizing new content. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:246`.
- [claim-236] **unverifiable** — paper:262 — and observed pass or failure. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:262`.
- [claim-244] **unverifiable** — paper:270 — with Plain or Graph is an end-to-end system comparison; only the ordinary — No implemented mechanical check proves or disproves this claim. Evidence: `paper:270`.
- [claim-255] **unverifiable** — paper:282 — value must be measured through paired rescues and harms. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:282`.
- [claim-273] **unverifiable** — paper:300 — was completely scored, replication 2 was frozen as the immediately following — No implemented mechanical check proves or disproves this claim. Evidence: `paper:300`.
- [claim-296] **unverifiable** — paper:321 — We therefore report actual calls, input, cached input, — No implemented mechanical check proves or disproves this claim. Evidence: `paper:321`.
- (+684 further extracted claim(s) — mostly unverifiable prose — omitted here for brevity; all are labelled in S2/S4 with source lines.)

## Comment

Recommendation: 3/6. No headline result is mechanically supported yet, so the recommendation stays borderline pending stronger evidence. Most useful next step for the authors — For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the compute / hardware used. Could the authors clarify these?

## Panel Reviews (provenance)

### Panel review 1 — theorist (accepted)

# Review: Mini Artichokes: Evidence-Overlap Gates for Selective LLM Arbitration and Repair

## Summary

This paper proposes a conservative inference-time update rule: preserve a base answer unless two auxiliary draws agree against it, then let an anonymous judge select between the existing candidates. A related coding system uses requirement, implementation, and test-output overlap to localize repairs. The MMLU-Pro study shows a statistically significant improvement over direct Luna (1,214/2,000 versus 1,187/2,000), but not over compute-matched generic judging or majority voting. The coding transfer improves Plain Luna (22/40 versus 14/40), but not ordinary same-budget repair (22/40 versus 21/40). Thus, the experiments support an end-to-end benefit from additional inference and structured repair, while the claimed incremental role of overlap remains unestablished.

## Strengths

- The arbitration policy is clearly specified and conservative. The paper defines the trigger as “`C(x)=1 when D1, D2, and D3 are all valid and D2=D3≠D1`” and explicitly preserves D1 outside that conflict set.

- The MMLU-Pro evaluation uses a strong confirmatory structure: “two disjoint, category-proportional 1,000-question samples,” fixed draw roles, full-denominator scoring, and a stated multiple-comparison boundary. This is substantially more rigorous than evaluating only selected conflicts.

- The paper makes an important attribution distinction. It explicitly states that the result establishes improvement over direct Luna but does not establish “a causal support-count effect” or superiority to SC3/GJ3. This restraint is appropriate given Table 2, where OJ3 exceeds GJ3 by only 3 answers with `p=.25391`.

- The authors report meaningful negative evidence and operational limitations rather than hiding them. In particular, the legal reserve produced “30 rescues but 59 harms,” and the coding study acknowledges that its task-level inference conditions on “only two independent batch calls per arm.”

- The presentation is unusually transparent about compute. Table 4 reports 45,973,780 tokens for OJ3 versus 13,009,321 for D1, making the 1.35-point gain interpretable rather than presenting accuracy in isolation.

## Weaknesses

- The central mechanism is not identified. In MMLU-Pro, OJ3’s incremental advantage over GJ3 is only `+3` answers, with `p=.25391` and merely 68 triggered conflicts. In coding, Graph-overlap repair scores 22/40 versus 21/40 for ordinary repair, with “`p=1.0` two-sided.” Therefore the evidence-overlap metadata itself is not shown to help; most of the observed gain can be explained by additional sampling, generic judging, or ordinary test-feedback repair.

- The complete-file session design creates substantial uncertainty that the item-level tests do not capture. The paper reports that D2 scored only “145/1,000” in confirmation 1 but “607/1,000” in replication 2. This is an extreme unexplained session effect, and the authors state that the tests “do not estimate between-session repeatability.” Since the treatment depends on the behavior of these sessions, the significant McNemar result is evidence about these realized calls, not yet strong evidence that the policy reliably improves future runs.

- The confirmatory continuation appears to have been selected after observing the first cohort: “Because the direction was favorable but underpowered, we froze exactly one disjoint 1,000-question replication.” The paper should clarify whether this continuation and the pooled test were fully pre-specified. A two-look alpha statement alone does not establish that the pooled p-value remains valid when the decision to collect the second cohort depends on the first result.

- The coding treatment is not an overlap-only intervention. The proposed arm “reconstructs three views,” derives a “minimal counterexample,” performs two completion audits, and is instructed to repair general obligations, whereas ordinary repair “simply fixes the failures.” Equal call counts and similar inputs do not isolate the causal contribution of overlap from these additional reasoning and auditing instructions.

- The theoretical justification for treating agreement as evidence is underdeveloped. The paper correctly says that same-model draws “can share systematic errors,” and Table 3 finds that both candidates are wrong on 20/68 conflicts. However, it provides no formal condition—such as an error-correlation or calibration assumption—under which the 1-versus-2 support record should improve decisions. The method is consequently a plausible heuristic rather than a theoretically grounded selective rule.

- The practical value is unclear at the reported cost. OJ3 uses “3.53 times the direct tokens” for a 1.35-point improvement, and its advantage over strong controls is statistically unresolved. The paper reports tokens and latency, but does not provide a cost-normalized or budget-frontier analysis showing when this tradeoff dominates simpler additional sampling or generic judging.

- Generalization is limited. The positive confirmatory result uses one model, one runtime, and two samples from one multiple-choice benchmark; the coding transfer covers only 40 Python/Rust tasks and two shared-call clusters. The negative legal result is informative, but because “domain, task, prompt, and label structure changed together,” it cannot explain where the proposed gate should or should not be used.

## Questions for the Authors

1. Was the decision to run replication 2 and the exact pooled analysis pre-registered before observing confirmation 1? If continuation was conditional, what alpha-spending or combination-test argument establishes validity of the reported pooled `p=7.15e-6`?

2. What caused D2’s 145/1,000 result in confirmation 1, and does the policy reproduce its gain when D1–D3 are rerun on the same frozen questions in multiple independent complete-file sessions?

3. Can the authors run repeated OJ3/GJ3 judge sessions on the identical conflict set, with the sole treatment difference being the support annotation, to estimate the support-count effect separately from whole-file session noise?

4. Can the coding experiment compare ordinary repair and overlap repair with identical prompts, audits, and repair requirements, varying only the explicit overlap information?

5. What accuracy, latency, and monetary-cost regimes make OJ3 preferable to simpler compute-matched alternatives such as additional sampling or a generic judge?

## Scores

Soundness: 3/4 — The protocol and reporting are careful, but session-level instability, adaptive continuation, and unresolved mechanism attribution limit the strength of the conclusions.

Presentation: 4/4 — The paper is clear, well organized, quantitatively detailed, and candid about negative and inconclusive results.

Significance: 2/4 — The end-to-end gains are potentially useful, but the incremental scientific contribution over generic extra inference remains small and unresolved.

Originality: 3/4 — The conservative update contract and cross-regime framing are interesting, although they combine largely familiar sampling, judging, graph, and repair techniques.

Overall recommendation: 3/6 — Borderline; the paper is promising and unusually honest, but the principal mechanism claim is not yet experimentally established.

Confidence: 4/5 — The paper provides enough methodological and numerical detail for a substantive assessment, though the underlying artifacts and repeated-run behavior cannot be independently checked here.

## Ethics and Limitations

The paper appropriately notes that it uses no human participants and withholds legal item texts and outputs because the precedent facts may remain re-identifiable. The incomplete de-identification and unrecoverable metadata for five records warrant continued governance review. The 45.97 million-token MMLU-Pro cost is also environmentally and economically relevant, particularly given the modest gain over direct inference. The authors’ stated limitations concerning one model, whole-file session dependence, same-model correlated errors, limited conflict counts, approximate compute matching, and the small two-cluster coding study are substantial and should materially constrain the claims.

## Comment

I recommend borderline acceptance or revision contingent on stronger evidence of repeatability and mechanism isolation. The most important issue is to separate the benefit of extra inference and generic feedback repair from the claimed benefit of evidence overlap: repeated frozen-session evaluations and tightly matched OJ3/GJ3 and coding ablations are needed before overlap can be considered a validated general principle.

### Panel review 2 — experimentalist (accepted)

# Review: Mini Artichokes: Evidence-Overlap Gates for Selective LLM Arbitration and Repair

## Summary

This paper proposes a conservative inference-time update rule: independently generated evidence may authorize a bounded correction, while unaffected answers or artifacts are preserved. It evaluates support-aware arbitration on two 1,000-question MMLU-Pro samples and transfers the idea to hidden-test program repair. The evidence supports improvement over direct inference, but not a mechanism-specific advantage over compute-matched generic judging or ordinary repair.

## Strengths

- The paper defines a precise, testable policy: “two independent auxiliary draws must agree with one another and disagree with a preassigned base,” followed by a judge restricted to “a discrete choice between two already generated answers.”

- The confirmatory comparison is meaningfully controlled and full-denominator: OJ3 achieved “1,214/2,000 (60.70%) versus 1,187/2,000 (59.35%) for direct Luna,” with “33 rescues and 6 harms” and a paired-bootstrap interval of “+0.75 to +1.95 percentage points.”

- The authors appropriately distinguish end-to-end gains from mechanism attribution. They explicitly report that OJ3 “was not significantly better than three-draw majority voting or a compute-matched generic judge,” avoiding an overstated causal claim.

- The study includes useful negative evidence. On the legal reserve, OJ3 scored “255/464 (54.96%)” versus 284/464 for the plain arm, demonstrating that same-model agreement is not treated as universally reliable.

- The coding transfer uses a strong same-budget control: ordinary repair received “the same Graph state, failures, model, and second-call budget,” and the proposed method scored only 22/40 versus 21/40. This substantially improves the paper’s credibility.

- The presentation is unusually transparent about inferential limits, including the statement that coding results “condition on the two realized batch calls” and “cannot establish that the +20-point effect would persist across repeated model sessions.”

## Weaknesses

- The central mechanism claim remains unproven. Although OJ3 beats direct Luna, the decisive comparison against GJ3 is only “+3” answers with “p=.2539,” and the paper itself states that “the support annotation's incremental causal effect is unresolved.” Thus, the evidence supports selective arbitration generally, not evidence-overlap as the source of improvement.

- The MMLU-Pro result is highly dependent on unusual whole-file session behavior. D2 scored “145/1,000” in confirmation 1 but “607/1,000” in replication 2. Because each draw processes 1,000 questions in a single session and no complete pipeline is rerun on identical items, the reported item-level confidence intervals do not measure session-level reproducibility.

- The coding transfer is too clustered and small to support broad conclusions. Each 20-task batch shares one model call, leaving “only two independent batch calls per arm,” while the proposed system’s advantage over ordinary repair is just “22/40” versus “21/40” with “p=1.0.”

- The main accuracy gain is expensive: OJ3 uses “3.53 times the direct tokens” for a “+1.35 percentage point” improvement. This may be acceptable for quality-critical applications, but the paper does not establish that the gain is attractive relative to simpler compute allocation strategies or repeated direct baselines.

- The benchmark evidence is narrow: the confirmatory study uses “one model, one runtime, and one primary benchmark.” The paper properly acknowledges this, but it limits claims about universal answer engines or model-independent robustness.

- The legal negative result is informative but diagnostically weak. The paper concedes that it “simultaneously changes domain, task, prompt, and label structure,” so it cannot determine whether the failure comes from partial observability, legal reasoning, prompt design, or outcome-label characteristics.

## Questions for the Authors

1. Can you provide repeated independent reruns of the same MMLU-Pro items, or another design that estimates variance across complete-file sessions rather than only conditional item-level variance?

2. What is the estimated effect of the support annotation in a substantially larger OJ3-versus-GJ3 comparison, and can the prompts be made byte-identical apart from the support-count field?

3. Why did D2 produce 14.5% accuracy in confirmation 1 and 60.7% in replication 2? Do the traces identify a parsing, context-window, instruction-following, or runtime failure mode?

4. Can you compare OJ3 against a compute-matched strategy that allocates the same tokens to additional direct draws, independent judge calls, or repeated generic judging?

5. For coding, can the ordinary-repair and overlap-repair arms be evaluated over more independent batches or repeated sessions to determine whether the one-task difference is noise?

## Scores

Soundness: 3/4 — The experiments are carefully controlled and candid, but session-level dependence and unresolved mechanism attribution limit the strength of the conclusions.

Presentation: 4/4 — The paper is exceptionally clear about protocols, controls, statistical boundaries, and limitations.

Significance: 3/4 — The conservative update contract and direct-baseline gain are useful, but the incremental scientific value of overlap remains unestablished.

Originality: 3/4 — The specific bounded arbitration formulation and cross-regime evaluation are distinctive, although the underlying ingredients draw heavily on existing consistency, judging, and repair methods.

Overall recommendation: 3/6 — Borderline; the empirical result over direct inference is credible, but the principal mechanism is not supported against the strongest controls and the transfer evidence is highly clustered.

Confidence: 4/5 — The paper is sufficiently self-contained to assess its logic and evidence, though the reported execution results cannot be independently reproduced from the manuscript alone.

## Ethics and Limitations

The paper responsibly reports increased inference cost and does not release potentially re-identifiable legal records or outputs. Its discussion of incomplete de-identification, model contamination, whole-file session effects, limited domain coverage, and two-cluster coding inference is appropriately candid. The main unresolved ethical concern is deployment: the negative legal result shows that same-model agreement should not be treated as a reliability signal in high-stakes settings without external evidence.

## Comment

I recommend borderline acceptance or rejection depending on the venue’s threshold for empirical mechanism papers. The strongest contribution is a disciplined, base-preserving arbitration framework with a convincing improvement over one direct baseline. The single most important issue is to establish whether overlap metadata itself provides value beyond the extra sampling and generic judging; larger repeated-session OJ3-versus-GJ3 experiments would directly determine that claim.

### Panel review 3 — scope_ablation (accepted)

# Review: Mini Artichokes: Evidence-Overlap Gates for Selective LLM Arbitration and Repair

## Summary

This paper proposes a conservative inference-time update policy: independently generated evidence must overlap before a separate judge may replace a base answer or repair an artifact. On two 1,000-question MMLU-Pro cohorts, the support-aware system improves the direct baseline by 1.35 percentage points, but it does not significantly outperform compute-matched generic judging or majority voting. An exploratory 40-task coding transfer improves over Plain Luna, yet not over ordinary same-budget repair. The paper is careful about these boundaries, but the central causal contribution of “evidence overlap” remains unestablished and the generalization evidence is limited.

## Strengths

- The experimental protocol is unusually explicit and conservative. The paper states that “D1 is the base, and D2/D3 are auxiliary draws” and that “No draw is selected as the base after inspecting its quality,” reducing a major source of post-hoc selection bias.

- The primary MMLU-Pro comparison is measured on the full denominator and uses paired outcomes: OJ3 achieves “1,214/2,000 (60.70%) versus 1,187/2,000 (59.35%) for direct Luna,” with “33 rescues, 6 harms” and a paired-bootstrap interval of “+0.75 to +1.95 percentage points.” This is stronger evidence than reporting only triggered cases.

- The authors distinguish end-to-end utility from mechanism attribution. In particular, they explicitly write that “the supported superiority claim is OJ3 over direct Luna, not over either strong multi-call control,” which is an appropriately restrained interpretation of the results.

- The base-preserving and no-synthesis design is clearly specified. The policy says that if the judge does not return exactly one existing candidate, the system should “return D1,” and the paper explains that this “does not let the judge improve an answer by synthesizing new content.” This is a sensible safety boundary for selective arbitration.

- The paper reports negative and inconclusive results rather than presenting only favorable evidence. The legal reserve shows OJ3 at “255/464 (54.96%)” versus P1 at “284/464 (61.21%),” while coding overlap repair scores “22/40 (55%)” versus ordinary repair at “21/40 (52.5%).” These results materially constrain the claims.

- The limitations are substantive and relevant. For example, the authors acknowledge that “Separate sessions do not create model-level independence” and that the coding study has “only two independent batch calls per arm.” This candor makes the empirical claims easier to assess.

## Weaknesses

- The paper does not establish that the proposed overlap metadata is the cause of the MMLU-Pro improvement. OJ3 exceeds GJ3 by only “+3” answers, with “p=.2539,” and the authors state that “the incremental comparison lacked power.” Since GJ3 receives the same trigger, candidate set, model calls, and nearly identical token budget, the central mechanism claim is currently unresolved rather than demonstrated.

- The most important MMLU-Pro evidence is vulnerable to whole-session instability. Table 1 reports D2 at “145/1,000” in confirmation 1 but “607/1,000” in replication 2. The paper acknowledges that “The anomalous D2 result in confirmation 1 (14.5%) demonstrates session-level instability,” but does not rerun the same items or replicate the full pipeline under identical inputs. The pooled gain and conflict structure may therefore depend substantially on one anomalous batch realization.

- The inferential treatment of the 2,000 MMLU-Pro rows does not fully support broad repeatability claims. Each draw “processed all 1,000 public rows in one isolated complete-file session,” and the paper concedes that the tests “quantify item-level uncertainty conditional on the realized sessions, not between-session variance.” Because within-session context and shared runtime effects can correlate outcomes, the very small McNemar p-value should not be interpreted as evidence that the complete pipeline will reliably produce the same gain across sessions.

- The scope of the evidence is narrow relative to the general framing. The study uses “one model, one runtime, and one primary benchmark,” while the coding transfer covers only “40 tasks from only Python and Rust.” The legal result is also explicitly not comparable in a controlled way because “domain, task, prompt, and label structure changed together.” Thus, the proposed general principle has suggestive cross-regime evidence but little evidence across models, independent executions, or broad task distributions.

- The coding result does not isolate the contribution of overlap repair. Although the proposal reaches “22/40 (55%)” versus Plain’s “14/40 (35%),” ordinary repair reaches “21/40 (52.5%),” and the direct proposal-versus-ordinary comparison has “p=1.0” with a bootstrap interval of “[-7.5,+12.5] points.” The coding experiment supports a second feedback call, not specifically the proposed overlap-localization mechanism.

- The support-aware judge is exposed to a potentially influential asymmetric prior, but the paper lacks a sufficiently direct placebo or permutation ablation. The current GJ3 comparison removes the support record entirely, leaving open whether the gain comes from meaningful overlap reasoning, simply from a “two versus one” cue, or from incidental prompt differences. A judge given randomized, reversed, or uninformative support counts would help identify this effect.

- The practical trade-off is unfavorable unless the application places substantial value on a small accuracy increase. OJ3 uses “3.53 times the direct tokens” for a “+1.35 percentage point” gain, and the paper itself characterizes it as “a fallback or batch-quality policy.” This is a reasonable engineering result, but it limits significance absent evidence that the method improves high-value tasks or provides a better accuracy-cost frontier.

## Questions for the Authors

1. How does OJ3 perform under repeated complete-pipeline executions on the same frozen MMLU-Pro items, particularly given D2’s “145/1,000” confirmation result? Does the positive gain persist across session seeds or runtime conditions?

2. Can you add a support-record placebo and permutation ablation—for example, randomized counts, reversed counts, or misleading counts—to determine whether OJ3 benefits from evidence overlap specifically rather than from any additional judge-side cue?

3. What is the expected performance and cost of a policy that first obtains only a base answer and then selectively generates auxiliary draws, rather than paying for all three draws for every question?

4. Can the coding transfer be repeated over more independent batches or sessions? With “only two independent batch calls per arm,” what evidence would support generalization beyond the realized calls?

5. How sensitive are the results to the base-draw assignment? If D2 or D3 is designated as the base under the same frozen policy, does the effect remain positive?

6. Can the authors provide per-category MMLU-Pro results and conflict rates, or another pre-specified analysis of where the overlap signal succeeds and fails, without introducing post-hoc routing?

## Scores

Soundness: 3/4 — The protocol and reporting are strong, but session-level dependence and the anomalous draw weaken repeatability claims.

Presentation: 4/4 — The paper is clear, well organized, and unusually transparent about controls, costs, and inferential limits.

Significance: 3/4 — The conservative update contract is practically relevant, but the measured gain is small and expensive, with limited evidence of broad transfer.

Originality: 3/4 — The explicit overlap-gated update contract is a useful synthesis, but its incremental novelty over generic arbitration and ordinary repair is not empirically established.

Overall recommendation: 3/6 — Borderline; the paper contains a credible empirical observation and careful methodology, but the central mechanism and generalization claims require stronger evidence.

Confidence: 4/5 — The paper is sufficiently self-contained to assess, although independent verification of the reported artifacts and execution traces is unavailable.

## Ethics and Limitations

The paper appropriately discusses the risks of applying same-model agreement to high-stakes decisions, especially after the legal reserve showed that “the supported outcome was correct only 32 times” out of 65 signaled cases. The legal data also raise genuine privacy and governance concerns: the authors acknowledge that metadata minimization “is not a claim of comprehensive de-identification” and withhold item texts pending review. The environmental discussion is also adequate, reporting “45.97 million tokens” for the two MMLU-Pro OJ3 cohorts. The main scientific limitations are the single-model setting, whole-file session dependence, anomalous D2 behavior, small coding sample, two-call-cluster inference, and failure to separate overlap-specific effects from generic additional computation and feedback.

## Comment

I recommend borderline acceptance/rejection depending on the venue’s tolerance for carefully bounded empirical work. The paper’s strongest contribution is not a validated overlap mechanism, but a well-specified and honestly evaluated conservative update framework. The single most important revision is to establish mechanism attribution and repeatability: repeated same-item executions plus direct placebo/permutation controls for the support annotation would determine whether the reported gain reflects evidence overlap or primarily additional sampling and judging.
