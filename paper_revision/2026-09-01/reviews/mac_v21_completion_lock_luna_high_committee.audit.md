# ICML-Style Paper Review

## Paper and Evidence Identity

- Review method: full review — deterministic evidence audit + review panel. The panel's review is the official output; this document is its audit sidecar.
- Review Agent name/version: paper-reviewer / `sha256:9886349f92661c3c73b70f216a7038b741b47282d7624538ad207dd3fbb2d4c0`
- Review-agent spec path/hash: `review-agent-spec.md` / `sha256:08b13516a2cb0e5151c6b4dc24f98e6d191b35ee30d69ea300b2d6ff2d5a5945`
- Original paper identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:6f1488a9db785e47a2595dfe2685f032b0181eeba1e6608d3aab3ac17f180268` / `75798` bytes
- Derived Markdown identity: `Mini_Artichokes_manuscript_v4.md` / `text/markdown` / `sha256:6f1488a9db785e47a2595dfe2685f032b0181eeba1e6608d3aab3ac17f180268` / `75798` bytes
- Original PDF page count: `n/a`
- Converter: `none (Markdown source)`
- Paper version/hash: `Mini_Artichokes_manuscript_v4.md` / `sha256:6f1488a9db785e47a2595dfe2685f032b0181eeba1e6608d3aab3ac17f180268`
- Evidence bundle reviewed: none (no evidence bundle supplied)
- Frozen at (UTC): `2026-09-04T06:03:39+00:00`

## Summary

We introduce **Mini Artichokes**, a. It reports 181 quantitative result claim(s) and cites 12 prior work(s). Deterministic audit: 0 contradiction(s), 0 dishonest self-certification(s), 0 mechanical finding(s); 0 result claim(s) evidence-backed, 1145 unverifiable. Overall recommendation: 3/6 [claim-001].

## Strengths

- The paper situates its contribution against prior work (12 citation(s); related-work section present).

## Weaknesses

- The deterministic audit proved no contradiction, arithmetic error, or integrity breach; the remaining concern is limited to claims that could not be independently verified (see Questions).

## Questions for the Authors

1. For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?
2. 181 extracted result/arithmetic claim(s) could not be checked against the supplied evidence and are listed with their source lines in the Evidence Trace — could the authors provide the underlying results?

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
- Frozen review identity: `sha256:81c479c86effc460ff8976e4470cac19232ecd6bb0576ba4c25770b634108800`.
- Verdict labels digest: `sha256:decc6d6f7442c4c9a2e8667f7e012b760e13dcddea7fe5b9ae33439bc2c68f8c`.
- External citation snapshot digest: `sha256:01545e382bf7b0636dcadf97adfec0e438018ba58ffefc7b6167718586eab0a7`.
- Scientific judgment identity: `sha256:3128e3f22083a6420c5fb4da17b8ff37573dcea9ccbdbea5417e7e8aed2aec3a`.
- Review panel configuration: panel=3, model=`gpt-5.6-luna`, synthesis=area-chair.
- Panel reviewer `theorist`: prompt=`sha256:ef1ee8bd94c4c846b8537d4ca30653c259fbf6f13dfe7accad1d6b7a620ff731`, response=`sha256:edbcba2ff8cb7283025402dbaa81ba2e63ff9dbf31fb29f4c0413c701438cba5`, status=ok.
- Panel reviewer `experimentalist`: prompt=`sha256:a4e1933e795799f4b9b1fceab65370c006607b3be60c68caef7bee2a3448097a`, response=`sha256:7716d0eb87772668d104ecd64ac9f5852e5caa577327f8ee5bc50c98382a1b15`, status=ok.
- Panel reviewer `scope_ablation`: prompt=`sha256:31fb2c880302a7ebc03c6b309f68c2ab9337bb7d653cc790bed09484fe8abd7d`, response=`sha256:8a8e56e58f8248316802fb079e5c11cfb96631539a0266e2453d81eca1a958ff`, status=ok.
- Output path: `mac_v21_completion_lock_luna_high_committee.md`.
- Frozen paper input: `Mini_Artichokes_manuscript_v4.md` (`sha256:6f1488a9db785e47a2595dfe2685f032b0181eeba1e6608d3aab3ac17f180268`).
- Frozen original identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:6f1488a9db785e47a2595dfe2685f032b0181eeba1e6608d3aab3ac17f180268`, 75798 bytes, page count=n/a).
- Frozen derived identity: `Mini_Artichokes_manuscript_v4.md` (`text/markdown`, `sha256:6f1488a9db785e47a2595dfe2685f032b0181eeba1e6608d3aab3ac17f180268`, 75798 bytes).
- Frozen converter: `none (Markdown source)`.
- Pre-S1 sanitation: 0 trace(s), 0 injection finding(s).
- S1 parse inventory: 41 sections, 12 tables, 922 numeric tokens with source locations.
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
- S5 DRAFT/GROUND: 181 candidate comment(s), 181 retained, 0 deleted, 181 criticism comment(s) converted to questions.
- S2/S4 claim verdicts:
- [claim-027] **unverifiable** — paper:26 — ordinary repair, and Plain score **47/49**, 47/49, 42/49, and 27/49. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:26`.
- [claim-029] **unverifiable** — paper:28 — tasks, Mini reaches **164/164** versus 157/164 for Plain; ordinary repair — No implemented mechanical check proves or disproves this claim. Evidence: `paper:28`.
- [claim-030] **unverifiable** — paper:29 — already reaches the same ceiling. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:29`.
- [claim-032] **unverifiable** — paper:30 — comparisons, not fixed-resource efficiency results. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:30`.
- [claim-035] **unverifiable** — paper:34 — map to a concrete final-code closure witness after semantic comparison. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:34`.
- [claim-037] **unverifiable** — paper:36 — Mini system scores **164/164**, versus 163/164 for both Generic-plus-Direct and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:36`.
- [claim-052] **unverifiable** — paper:49 — then yields a one-task prospective Java win under matched calls and evidence. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:49`.
- [claim-053] **unverifiable** — paper:50 — Thus verified redundancy is the supported system result; semantic overlap plus — No implemented mechanical check proves or disproves this claim. Evidence: `paper:50`.
- [claim-060] **unverifiable** — paper:61 — can improve over one-pass generation, yet their composition is fragile. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:61`.
- [claim-070] **unverifiable** — paper:71 — hypotheses improve one final repair route. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:71`.
- [claim-075] **unverifiable** — paper:76 — **semantic-relation value:** whether comparing what failed candidates mean — No implemented mechanical check proves or disproves this claim. Evidence: `paper:76`.
- [claim-076] **unverifiable** — paper:77 — improves repair beyond a final agent with the same candidates, evidence, — No implemented mechanical check proves or disproves this claim. Evidence: `paper:77`.
- [claim-105] **unverifiable** — paper:107 — **RQ1:** Does recursive verified redundancy improve Plain, Graph, and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:107`.
- [claim-125] **unverifiable** — paper:130 — complete tracks that expose both positive mean differences and large — No implemented mechanical check proves or disproves this claim. Evidence: `paper:130`.
- [claim-126] **unverifiable** — paper:132 — an exploratory equal-call dual-route comparison and repeated-session union — No implemented mechanical check proves or disproves this claim. Evidence: `paper:132`.
- [claim-138] **unverifiable** — paper:144 — HumanEvalFixDocs Python tasks, which reaches a 164/164 verified ceiling and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:144`.
- [claim-141] **unverifiable** — paper:147 — completion-locked overlap reaches 164/164 versus 163/164 for both matched — No implemented mechanical check proves or disproves this claim. Evidence: `paper:147`.
- [claim-146] **unverifiable** — paper:157 — End-to-end five-call effectiveness | 59/90 original; frozen Go 33/39; frozen JavaScript 47/49; HumanEvalFix Python and Java 164/164 | Supported in the reported test-available setting — No implemented mechanical check proves or disproves this claim. Evidence: `paper:157`.
- [claim-147] **unverifiable** — paper:158 — Advantage over a same-call generic portfolio | Five-track sensitivity 139/178 vs 132/178 (8:1); clean JavaScript tie; Python ceiling tie; prospective Java 164/164 vs 163/164 (1:0) | Positive mixed-stage evidence plus a small prospective Java confirmation; not a population-level claim — No implemented mechanical check proves or disproves this claim. Evidence: `paper:158`.
- [claim-175] **unverifiable** — paper:195 — an indivisible task it reduces to ordinary verifier-selected best-of-multiple. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:195`.
- [claim-222] **unverifiable** — paper:252 — priority affects provenance, not the observed pass label. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:252`.
- [claim-226] **unverifiable** — paper:259 — After its model call, the experiment — No implemented mechanical check proves or disproves this claim. Evidence: `paper:259`.
- [claim-238] **unverifiable** — paper:278 — The semantic comparison is behavioral. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:278`.
- [claim-251] **unverifiable** — paper:290 — The revised final gate therefore enumerates every observed compiler, — No implemented mechanical check proves or disproves this claim. Evidence: `paper:290`.
- [claim-290] **unverifiable** — paper:328 — `/tmp/artifacts/decision_ledger.json` with exactly one record for each frozen — No implemented mechanical check proves or disproves this claim. Evidence: `paper:328`.
- [claim-296] **unverifiable** — paper:332 — They do not score the natural-language diagnoses for — No implemented mechanical check proves or disproves this claim. Evidence: `paper:332`.
- [claim-316] **unverifiable** — paper:353 — verification preserves every observed pass from either included route on the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:353`.
- [claim-318] **unverifiable** — paper:355 — The construction was formulated after final-route crossovers were observed and — No implemented mechanical check proves or disproves this claim. Evidence: `paper:355`.
- [claim-328] **unverifiable** — paper:364 — recursive promotion--rather than a score gain over an offline union of the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:364`.
- [claim-343] **unverifiable** — paper:380 — tasks observed passing in included route `k`, and let `A` be the prior anchor — No implemented mechanical check proves or disproves this claim. Evidence: `paper:380`.
- (+1115 further extracted claim(s) — mostly unverifiable prose — omitted here for brevity; all are labelled in S2/S4 with source lines.)

## Comment

Recommendation: 3/6. No headline result is mechanically supported yet, so the recommendation stays borderline pending stronger evidence. Most useful next step for the authors — For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters; the compute / hardware used. Could the authors clarify these?

## Panel Reviews (provenance)

### Panel review 1 — theorist (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper presents a test-available program-repair system that preserves verifier-passing task states as immutable anchors and applies two heterogeneous repair routes only to unresolved tasks. Its strongest result is an effectiveness comparison: “Mini Artichokes solves 139/178” Aider tasks versus “132/178” for a five-call Generic-plus-Direct portfolio. However, the semantic-overlap component and completion lock are not yet supported by robust causal evidence; the clean prospective JavaScript comparison is tied, while the prospective Java improvement is only one task.

## Strengths

- The preservation mechanism is clearly formalized under explicit assumptions. The paper states that under A1–A5, the promoted output “passes every task in `A union (union_k S_k)`,” and that “no unverified merged state is created.” This is a valid and useful correctness property for modular, test-available tasks.

- The evaluation retains complete benchmark inventories rather than selecting favorable tasks. For example, the paper reports “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” and later evaluates “all 49 official JavaScript tasks” and “all 164 official Java tasks.” This substantially improves auditability over task-level cherry-picking.

- The system-level effectiveness gains over simple baselines are substantial. On the original Aider tracks, Mini reaches “59/90,” compared with “45/90” for ordinary repair and “15/90” for Plain. On JavaScript, it reaches “47/49” versus “42/49” for ordinary repair and “27/49” for Plain.

- The paper is unusually candid about evidential boundaries. It explicitly says that the five-track result is “mixed-stage” and “not a prospective population or overlap-causal claim,” and that “Neither replication establishes session-level superiority at `.05`.” This careful claim hierarchy is a major strength.

## Weaknesses

- The formal novelty is limited by the fact that the central promotion rule is essentially a verifier union. The paper itself states: “a minimal task-wise verifier union is algebraically identical to this promotion rule.” The preservation theorem is sound but conditional and close to a direct max operation; the scientific contribution therefore depends on demonstrating that the particular routes and prompting composition produce reliable gains.

- The semantic-overlap claim lacks a clean, prospective causal demonstration. The semantic-free control “was frozen only after all TOV outcomes and the MAC v9 critique were known,” while the strongest original comparison is explicitly “review-triggered and post hoc.” The clean JavaScript result is an exact tie: “Mini and Direct∪Generic are an exact tie,” and the Java result is only “one rescue and no harms” with `p=.5`. Thus the evidence supports semantic overlap as a plausible mechanism, but not as a robust advantage.

- Nominal call matching does not provide resource matching. The paper acknowledges, “Neither comparison is token-matched.” In the original final-call measurements, TOV takes “29.6 more seconds” than the semantic-free control, and the new portfolios also have substantial differences in input and output tokens. The Java result is close in realized compute, but its one-task difference remains statistically weak.

- The task-level significance results can overstate generality because all tasks in an arm share one whole-track model trajectory. The paper states, “All task rows within one arm share one whole-track model call,” and that task-level tests “condition on the realized calls.” The more appropriate session-level replications contain only five pairs on each of two tracks, with wide intervals such as `[-6.92,+11.54]` percentage points. Consequently, the reported task-level `p`-values should not be interpreted as broad evidence across languages or model runs.

- The applicability contract is narrow. The guarantee assumes “task units whose declared solution files and verifier do not cross task boundaries,” isolated workspaces, complete file copying, and stable tests. The paper also concedes that anchors preserve “benchmark passes, not proof of correctness beyond those tests.” This is appropriate for the stated setting, but it limits the claimed universality and leaves behavior on repositories with shared build state, cross-task dependencies, weak tests, or nondeterminism unresolved.

- The external baseline coverage is limited. The authors state that Graph, Generic Critic, and other methods are “bounded prompt-level realizations,” and that they “do not empirically compare a full contemporary repository agent such as KIRA under matched verifier access, calls, and tokens.” The results therefore establish an internally defined system comparison rather than a strong state-of-the-art comparison.

## Questions for the Authors

1. Can you run a preregistered comparison across several new tracks, models, and independent sessions that factorially separates anchoring, route diversity, semantic overlap, completion locking, and recursive union?

2. How would the semantic-overlap route perform under equal realized token and latency budgets, rather than equal nominal call counts and hard caps?

3. Can independent annotators evaluate the TOV ledger fields—fault location, invariant, counterexample class, and edit intent—and report agreement and predictive validity for successful repairs?

4. How robust is the preservation guarantee on repositories with shared files, cross-task build state, flaky or nondeterministic tests, and verifier failures that are not cleanly attributable to one task?

## Scores

Soundness: 3/4 — The preservation property and experimental accounting are careful, but causal evidence for the central semantic mechanism is weak.

Presentation: 3/4 — The paper is highly transparent and well organized, though its extensive chronology and caveats make the main comparison difficult to isolate.

Significance: 3/4 — Reliable verified redundancy could be practically valuable, but the demonstrated gains are tied to a narrow test-available setting and additional compute.

Originality: 3/4 — The composition of immutable anchors, unresolved-only branching, and heterogeneous routes is coherent, although the core union operation is straightforward.

Overall recommendation: 3/6 — Borderline; the system result is promising, but the principal mechanism is not convincingly isolated or shown to generalize.

Confidence: 4/5 — The paper provides enough self-contained detail for a confident assessment, although the reported artifacts and executions cannot be independently rerun here.

## Ethics and Limitations

The use of public programming tasks and no human participants presents limited direct ethical risk. The paper appropriately notes that models do not receive private tests or gold implementations, while also recognizing that failure output can reveal behavioral expectations. It discloses increased inference compute, latency, and licensing requirements for redistributed task files.

The authors candidly state limitations involving one model and runtime, whole-track call dependence, post-hoc controls, language and benchmark scope, runtime deviations for Python and Java, finite test specifications, and the absence of matched comparisons with contemporary repository agents. These limitations materially constrain claims about generality and efficiency, but they are clearly reported.

## Comment

I recommend borderline reject. The most important next step is a preregistered, multi-session, resource-matched evaluation that separates the mechanical benefit of verifier-backed union from the claimed benefit of semantic overlap and completion locking. Until such evidence exists, the paper’s strongest defensible contribution is a carefully engineered verified-redundancy system for modular, test-available repair, rather than a validated general semantic-overlap method.

### Panel review 2 — experimentalist (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper presents Mini Artichokes, a five-call program-repair system that preserves verifier-passing task states as immutable anchors and applies multiple repair routes only to unresolved tasks. Its strongest contribution is the carefully specified, fail-closed composition of candidate diversity, task-level verification, and recursive promotion. The empirical evidence supports improved effectiveness over one- and two-call baselines, but evidence for superiority over a matched five-call portfolio or for semantic-overlap guidance itself remains limited and largely non-prospective.

## Strengths

- The paper clearly distinguishes its claims, explicitly stating that “the best-supported object is Mini Artichokes as a five-call effectiveness system, not semantic overlap as an isolated causal treatment.” This is appropriately calibrated.

- The preservation mechanism is precisely specified. Under A1–A5, “the construction copies either its prior anchored state or one complete state already observed to pass; no unverified merged state is created.” This gives the central anchoring rule a genuine structural guarantee under its stated assumptions.

- The evaluation retains complete benchmark inventories rather than selecting favorable tasks. For example, the paper states that “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks” were retained and that “No task is ranked, screened, removed, replaced, or topped up.”

- The paper uses stronger controls than a one-pass baseline. In particular, the semantic-free control shares “the same ledger fields, counterexample-based falsification, and two audits as TOV,” while withholding the proposed semantic relations. This is a meaningful attempt to isolate the component.

- The reporting is unusually transparent about protocol failures and deviations. The Generic Go call is described as “transport-null,” the Python HumanEvalFix run used Python 3.13.11 instead of 3.13.5, and the Java run used OpenJDK 17.0.17 instead of Java 18.0.2. These disclosures improve credibility.

- The results demonstrate substantial effectiveness gains in the test-available setting: Mini reaches “33/39” on Go versus 25/39 for ordinary repair and 17/39 for Plain, and reaches 47/49 on JavaScript versus 42/49 and 27/49. These comparisons are not compute-efficient comparisons, but they show practical value under the stated bounded-call regime.

## Weaknesses

- The central matched-system advantage is not yet robustly established. The five-track result of 139/178 versus 132/178 is explicitly “mixed-stage,” with Go relying on a post-primary replacement and JavaScript producing an exact tie. The prospective Java result is only one rescue: “1:0 discordance has one-sided `p=.5`.” Thus the strongest fair comparisons provide suggestive but weak evidence for a general advantage.

- Resource matching is incomplete. The paper acknowledges that “Neither comparison is token-matched,” and Table 9 shows that TOV takes 1,422.3 seconds versus 1,233.6 for Generic Critic while producing different input and output-token totals. The five-call comparison therefore establishes bounded-call effectiveness, but it does not establish superiority at matched compute, latency, or cost.

- The semantic-overlap causal claim is weakened by both post-hoc design and limited replication. The semantic-free control was “frozen only after all TOV outcomes and the MAC v9 critique were known,” and the two replication sets contain only five pairs each. Their confidence intervals include meaningful benefit and harm, and neither reaches significance. This makes the original +7/90 contrast vulnerable to prompt construction and trajectory selection.

- The recursive union is operationally useful but algorithmically modest. The paper itself states that “a minimal task-wise verifier union is algebraically identical to this promotion rule” and that it makes “no claim [of] a new selector beyond that max operation.” Consequently, much of the observed gain may arise from adding a second heterogeneous route and taking the verifier-wise union, rather than from a novel reasoning algorithm. The paper should more sharply separate engineering reliability from scientific algorithmic novelty.

- The task-level statistical precision is overstated if read as population evidence. Each complete track is generated by one whole-track model call, and the paper concedes that “task-level exact tests and bootstrap intervals condition on those realized calls.” Five pair replications in two fixed contexts do not estimate variability across models, independent candidate generations, languages, or benchmark populations.

- The proposed semantic fields are not independently validated. The integrity checks verify that ledgers contain the required rows and fields, but “do not score the natural-language diagnoses for semantic correctness.” Therefore, the mechanistic explanation that TOV succeeds by identifying better behavioral obligations remains plausible case analysis rather than demonstrated causal evidence.

## Questions for the Authors

1. Can you provide a prospective replication in which the complete candidate-generation and final-route pipeline is repeated independently under a frozen protocol, rather than reusing fixed candidate artifacts for the TOV/control sessions?

2. What is the quality–compute curve when systems are matched on realized input tokens, output tokens, reasoning tokens, or wall-clock time rather than nominal call count? The paper reports that “calls and caps are matched, but tokens and latency are not exact.”

3. Can you isolate the contribution of immutable anchoring and recursive promotion with controls using the same route outputs but no anchoring, single-route verification, or a simple offline best-of-multiple union? This would clarify how much of the gain is due to the wrapper versus route construction.

4. Can independent annotators evaluate the correctness of the TOV ledger fields and failure-closure witnesses before outcome inspection? This would test whether the proposed semantic-overlap mechanism is genuinely predictive rather than a post-hoc explanation of successful repairs.

5. How does the method behave with other models, model versions, nondeterministic tests, and repositories with cross-task build dependencies, where assumptions A1–A5 may fail?

## Scores

Soundness: 3/4 — The protocol and caveats are carefully documented, but the decisive comparative evidence is small, mixed-stage, and resource-unmatched.

Presentation: 3/4 — The paper is exceptionally explicit and well organized, though the many evaluation stages and caveats make the central empirical message difficult to distill.

Significance: 3/4 — Reliable preservation and verifier-backed repair are practically useful, but the demonstrated advantage over a matched portfolio is modest.

Originality: 3/4 — The composition of immutable task anchors and heterogeneous verified routes is a useful systems idea, although the union operation itself is acknowledged to be algebraically simple.

Overall recommendation: 3/6 — Borderline; promising and unusually rigorous in reporting, but not yet sufficiently supported as a general improvement over matched alternatives.

Confidence: 4/5 — The paper provides enough methodological and numerical detail for a substantive assessment, although the reported runs and artifacts cannot be independently reproduced here.

## Ethics and Limitations

The study uses public open-source exercises and no human participants, and it withholds private tests and gold implementations from the model. The increased inference cost is disclosed through call, token, and latency reporting. The principal limitations are appropriately acknowledged: one model and runtime, whole-track calls that induce correlated task outcomes, limited independent sessions, post-hoc stages, incomplete compute matching, prompt-level rather than faithful reproductions of some baselines, and dependence on task-local stable verifiers. The benchmark tests preserve observed labels rather than guaranteeing correctness beyond the supplied tests.

## Comment

I recommend borderline acceptance/rejection depending on the venue’s threshold. The most important issue is evidential: the paper should establish the claimed system advantage with a genuinely prospective, independently repeated, compute-matched comparison against the five-call Generic-plus-Direct portfolio. At present, the anchoring construction is convincing as a preservation mechanism, but the empirical superiority of the full method—and especially the causal role of semantic overlap—remains suggestive rather than conclusive.

### Panel review 3 — scope_ablation (accepted)

# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

The paper proposes Mini Artichokes, a five-call program-repair system that preserves task-level solutions passing an external verifier, restricts later edits to unresolved tasks, and recursively unions passing outputs from direct and semantic-overlap repair routes. The strongest evidence supports verified redundancy as an effective bounded-compute strategy in test-available repair, while the paper appropriately presents semantic overlap and completion locking as hypotheses with limited causal evidence.

## Strengths

- The central preservation mechanism is clearly specified and technically well motivated. The paper states that “a complete verified task state is removed from model discretion” and formalizes assumptions A1–A5, including “Promotion copies the complete allowlisted solution-file tuple for a task.” This makes the claimed test-label preservation property understandable and auditable.

- The evaluation retains complete benchmark tracks rather than selecting favorable tasks. For example, it reports “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” as well as complete Go39, JavaScript49, and HumanEvalFixDocs populations. This substantially improves the credibility of the reported aggregate comparisons.

- The paper includes meaningful controls and does not treat Plain as its only baseline. The semantic-free structured control “uses the same ledger fields, counterexample-based falsification, and two audits as TOV,” while withholding candidate relations. This is a stronger comparison than a simple one-pass baseline.

- The authors are unusually candid about the evidence hierarchy and failure cases. They explicitly state that the “repeatable standalone semantic-relation effect” is “Not established,” and retain the Rust `fizzy` harm where “the final file contained an extra closing brace and did not compile.”

- The end-to-end system results are substantial within the tested setting. Mini reaches “139/178” on the five-track Aider inventory versus “132/178” for the same-five-call Direct∪Generic portfolio, and improves over ordinary repair from “112/178” to 139/178. The JavaScript result also gives a clean, complete-track comparison, with Mini and Direct∪Generic tied at 47/49 rather than selectively claiming an advantage.

- The analysis distinguishes mechanical union gains from causal route effects. The statement that “We do not claim a new selector beyond that max operation” is important: it correctly identifies recursive promotion as a verifier-backed construction whose benefit depends on complementary route outputs.

## Weaknesses

- The paper’s strongest causal or mechanistic claims remain underidentified. The original TOV-versus-semantic-free result is 58/90 versus 51/90, but the semantic-free control “was frozen only after all TOV outcomes and the MAC v9 critique were known,” and the paper calls this comparison “review-triggered and post hoc.” The later replications have small, uncertain effects: Python has mean +1.2/34 with CI `[-2.35,+8.24]` pp, while C++ has +0.4/26 with CI `[-6.92,+11.54]` pp. Thus the evidence does not establish that semantic overlap itself, rather than prompt trajectory or other implementation details, causes the gains.

- The cleanest same-call system evidence does not show an advantage. On JavaScript49, “Mini and Direct∪Generic are an exact tie: 0 rescues, 0 harms,” and on HumanEvalFix Python, ordinary repair already reaches “164/164.” The only prospective same-call win is Java164, where Mini gains “one rescue and no harms” and the exact one-sided test is `p=.5`. Consequently, the paper supports effectiveness over weaker or cheaper systems more strongly than superiority over a matched alternative.

- The aggregate 139/178 versus 132/178 comparison is difficult to interpret as general evidence because it combines stages with different evidentiary status. The paper itself says that the result “remains mixed-stage,” with Go using a replacement after a transport-null call and JavaScript being a prospective tie. The task-level `p=.01953` is conditional on a small number of realized whole-track trajectories, while the track-level result is only three positive and two tied outcomes (`p=.125`). This limits claims about population-level generalization beyond these tracks and sessions.

- The nominal five-call matching does not control realized computation. Table 10 reports that TOV uses “4.35% more input tokens and 3.70% more time” on JavaScript, though it is slightly cheaper on the other tracks. Since the proposed route is itself more elaborate, the comparison needs either token/time-matched controls or an analysis showing that the observed gains persist under a fixed realized-compute budget.

- The semantic representation is not independently validated. TOV requires fields such as “fault location,” “violated requirement or invariant,” and “edit intent,” but “Integrity checks ... do not score the natural-language diagnoses for semantic correctness.” Without independent labels or blinded adjudication, it is unclear whether semantic overlap is genuinely measuring behavioral relations or simply providing additional prompt space and a different instruction style.

- The external validity is narrow. The method requires “tasks [that] are modular,” “a trusted external verifier,” and failure output that is informative without revealing gold code. The experiments cover test-available benchmark repair, mostly Exercism-derived tasks plus HumanEvalFixDocs, and do not establish performance on real repositories, weak or flaky test suites, cross-task build state, or settings without tests. The paper’s formal guarantee is therefore a benchmark-observation guarantee rather than a general correctness guarantee.

## Questions for the Authors

1. Can you provide a prospective, token- or reasoning-budget-matched comparison between Mini and Direct∪Generic, with the route order and analysis frozen before calls?

2. What is the causal contribution of each additional component—immutable anchoring, TOV relations, completion locking, and recursive promotion—under a factorial or sequential ablation that preserves the same candidate artifacts and realized budget?

3. Can independent blinded annotators evaluate the TOV ledger fields and test whether ledger quality predicts rescues, harms, or route complementarity?

4. How does the method behave on repositories with shared files, cross-task dependencies, nondeterministic tests, or incomplete/flaky verifiers, where assumptions A1–A5 may fail?

5. Can the Java164 rescue be replicated on additional independently frozen languages or benchmark families before drawing conclusions about completion locking?

## Scores

Soundness: 3/4 — The construction and reporting are careful, but causal attribution and generalization are limited by post-hoc design choices and few independent trajectories.

Presentation: 3/4 — The paper is unusually transparent and well organized, though the many stages, sensitivity analyses, and status labels make the central evidentiary hierarchy difficult to follow.

Significance: 3/4 — Verified task-level redundancy is practically useful for test-available repair, but its broader impact is not yet demonstrated.

Originality: 3/4 — The composition of immutable verified anchors, unresolved-only branching, heterogeneous routes, and recursive promotion is a meaningful systems contribution, although its ingredients are individually familiar.

Overall recommendation: 3/6 — Borderline; promising and carefully executed, but the main superiority claim over a matched portfolio is not yet convincingly established.

Confidence: 4/5 — The paper provides sufficient self-contained detail for a substantive assessment, though the underlying runs and artifacts cannot be independently rerun here.

## Ethics and Limitations

The study uses public code exercises and no human participants, and it discloses that “Models never receive private test source or gold implementations.” The main ethical considerations are compute consumption, licensing of redistributed benchmark files, and the possibility that failure output leaks behavioral expectations; the authors address each explicitly.

The authors also appropriately acknowledge model-specific correlated errors, whole-track call dependence, stage mixing, runtime deviations for Python and Java, limited session replication, prompt-level rather than latent-compute matching, finite-test correctness, and the narrow applicability of A1–A5. These limitations materially constrain the claims, especially outside test-available modular repair.

## Comment

I recommend borderline acceptance/rejection pending stronger evidence. The most important issue is to separate the valuable mechanical verified-union construction from the less-supported claim that semantic overlap or completion locking provides a reliable causal advantage. A preregistered, compute-matched replication with multiple independent whole-track sessions and independently scored ledger quality would substantially clarify whether Mini is more than a useful verifier-backed portfolio construction.
