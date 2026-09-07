# ICML-Style Paper Review

## Paper and Evidence Identity

- Review method: deterministic evidence audit only (`--deterministic`). Every score and comment below is from the deterministic mechanical checks; no scientific-committee judgment is included.
- Review Agent name/version: paper-reviewer / `sha256:9886349f92661c3c73b70f216a7038b741b47282d7624538ad207dd3fbb2d4c0`
- Review-agent spec path/hash: `review-agent-spec.md` / `sha256:08b13516a2cb0e5151c6b4dc24f98e6d191b35ee30d69ea300b2d6ff2d5a5945`
- Original paper identity: `Mini_Artichokes_Main_original.md` / `text/markdown` / `sha256:d6f02cca8d48f094efb69fb15d641fab9589c3209871c4c5b049986e0a7d9cc2` / `30305` bytes
- Derived Markdown identity: `Mini_Artichokes_Main_original.md` / `text/markdown` / `sha256:d6f02cca8d48f094efb69fb15d641fab9589c3209871c4c5b049986e0a7d9cc2` / `30305` bytes
- Original PDF page count: `n/a`
- Converter: `none (Markdown source)`
- Paper version/hash: `Mini_Artichokes_Main_original.md` / `sha256:d6f02cca8d48f094efb69fb15d641fab9589c3209871c4c5b049986e0a7d9cc2`
- Evidence bundle reviewed: `evidence`: `EVIDENCE_SCOPE.md` (`sha256:7dbc819a9c3306e5f01106a4d439d2319658f55ce6590769a669c50d665e5fc6`), `MMLU_PROTOCOL_CONFIRMATION1.md` (`sha256:f78ea8a6294728e3b1abd3c6c3c74cdf89f474da83da0f0ae7b7f56d637c60ef`), `MMLU_PROTOCOL_REPLICATION2.md` (`sha256:0fe6bd59e759d1c761770267fe9b7a8f2bef5e2f47ba6c768e57cfe35352c9a7`), `MMLU_PRO_CUMULATIVE_RESULTS.md` (`sha256:52cbe8e02c8fe34f72d88ed6c24aa26dcf6afb45c44b3ede70fed4274242a39c`), `UNIVERSAL_DEVELOPMENT_RESULTS.md` (`sha256:e1a542a410331498e46472a0061c344cc806189898e0576b4a20d8188253f791`), `legal_boundary_score.json` (`sha256:14318b0953051f0ccb4a1ab3390914eb1abab000c45f48c618cd45a7fd8a4ba1`), `mmlu_pro_confirmation1_score.json` (`sha256:5ba78d945aff95e5c3b7d93b0a44d592bbe16b2587d4d2228d179f5e1339128f`), `mmlu_pro_cumulative_score.json` (`sha256:bdf7e36abcf05b8a05d921a259590b919f54da2b7a1658dcc4057acabc905fec`), `mmlu_pro_replication2_score.json` (`sha256:2442d9018a0241e203500f85e859d76c78cda52f74277090856f5b40d3ca7685`)
- Frozen at (UTC): `2026-09-01T11:51:55+00:00`

## Summary

We introduce Mini Artichokes, a verification\-and\-refinement loop that turns additional inference into a redundancy\-based correction signal: two independent diagnoses describe a failed solution, their shared error signature is extracted, and that overlap is validated before any correction is fed back to the solver\. It reports 60 quantitative result claim(s) and cites 0 prior work(s). Deterministic audit: 0 contradiction(s), 0 dishonest self-certification(s), 0 mechanical finding(s); 0 result claim(s) evidence-backed, 149 unverifiable. Overall recommendation: 2/6 [claim-001].

## Strengths

- The paper situates its contribution against prior work (0 citation(s); related-work section present).

## Weaknesses

- The deterministic audit proved no contradiction, arithmetic error, or integrity breach; the remaining concern is limited to claims that could not be independently verified (see Questions).

## Questions for the Authors

1. For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report a broader-impact / ethics statement. Could the authors clarify these?
2. 60 extracted result/arithmetic claim(s) could not be checked against the supplied evidence and are listed with their source lines in the Evidence Trace — could the authors provide the underlying results?

## Scores

- Overall recommendation: 2/6 — Directly calibrated from Soundness 2/4, Presentation 3/4, Significance 2/4, Originality 2/4 [claim-001].
- Soundness: 2/4 — No headline result has mechanical support, but none is contradicted [claim-001].
- Presentation: 3/4 — The structural audit found no violation and the paper situates itself against cited prior work [claim-001].
- Significance: 2/4 — Broad impact is not mechanically established [claim-001].
- Originality: 2/4 — The deterministic trace neither establishes nor disproves novelty [claim-001].
- Confidence: 2/5 — Verified result coverage is 0/60; claim extraction succeeded, positioning is covered, and 0 finding(s) are mechanically grounded [claim-001].

## Ethics and Limitations

Paper text was treated only as data. The injection audit sanitized hidden HTML and Unicode format controls before claim analysis and found 0 reviewer-directed instruction attempt(s). Broader ethics and evidence-quality claims outside S3 remain unverifiable [claim-001].

## Evidence Trace

- Pipeline execution: `S1 parse -> S2 claims -> S3 mech-check -> S4 verdicts -> S5 compose -> S6 freeze`.
- Frozen review identity: `sha256:c568255fb60f2079948845052bdbfb59a7eeca7f86facb34628550ee50bd66b1`.
- Verdict labels digest: `sha256:a4af9011a890c1e5a42addfc579953d03ba858de0ceba53777119ebcde735d0b`.
- External citation snapshot digest: `sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
- Output path: `mac_original_deterministic.md`.
- Frozen paper input: `Mini_Artichokes_Main_original.md` (`sha256:d6f02cca8d48f094efb69fb15d641fab9589c3209871c4c5b049986e0a7d9cc2`).
- Frozen original identity: `Mini_Artichokes_Main_original.md` (`text/markdown`, `sha256:d6f02cca8d48f094efb69fb15d641fab9589c3209871c4c5b049986e0a7d9cc2`, 30305 bytes, page count=n/a).
- Frozen derived identity: `Mini_Artichokes_Main_original.md` (`text/markdown`, `sha256:d6f02cca8d48f094efb69fb15d641fab9589c3209871c4c5b049986e0a7d9cc2`, 30305 bytes).
- Frozen converter: `none (Markdown source)`.
- Pre-S1 sanitation: 0 trace(s), 0 injection finding(s).
- S1 parse inventory: 20 sections, 0 tables, 586 numeric tokens with source locations.
- S3 ledger-trace: 0/3 metric-labelled values matched; 0 finding(s).
- S3 internal-consistency: 0 comparison(s), 0 finding(s).
- S3 arithmetic: 0 recomputation(s), 0 finding(s).
- S3 baseline-fairness: 0 explicit improvement claim(s), 0 finding(s).
- S3 negative-evidence: 0 discard/crash outcome(s), 0 omission finding(s).
- S3 citation-existence: 0 explicit identifier(s), 0 existence/title finding(s).
- S3 template-compliance: 1 contract trace(s), 0 finding(s).
- S3 injection-scan: 0 sanitation trace(s), 0 reviewer-directed instruction finding(s).
- S3 self-review-audit: 0 checklist item(s), 0 dishonest self-certification(s).
- S3 positioning: 0 cited reference(s), related-work section=True, 0 novelty/superiority claim(s), 0 overclaim finding(s), 0 positioning question(s).
- S5 DRAFT/GROUND: 60 candidate comment(s), 60 retained, 0 deleted, 60 criticism comment(s) converted to questions.
- S2/S4 claim verdicts:
- [claim-006] **unverifiable** — paper:5 — Average full\-suite gains are modest, but the effect is concentrated on items that baseline first\-sample accuracy rarely solves\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:5`.
- [claim-007] **unverifiable** — paper:5 — On PSAT, pass@1 reaches 467/800 \(58\.4%\) whereas Mini Artichokes reaches 491/800 \(61\.4%\); under an oracle best\-of\-20 scoring view, pass@1 solves 25/40 items at least once, while Mini Artichokes solves 37/40\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:5`.
- [claim-008] **unverifiable** — paper:5 — The method also improves Putnam from 65/240 to 71/240, AIME from 61/300 to 82/300, and the exploratory LEET subset from 6/15 to 7/15\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:5`.
- [claim-009] **unverifiable** — paper:5 — These results should not be interpreted as evidence of compute efficiency over cost\-matched repeated sampling; instead, they show how structured self\-generated feedback can expand the set of reachable correct trajectories under a larger inference budget\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:5`.
- [claim-014] **unverifiable** — paper:11 — The difficulty is especially visible when the loop receives no external signal such as a unit test, retrieval result, formal checker, tool output or human intervention\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:11`.
- [claim-018] **unverifiable** — paper:15 — Mini Artichokes is related to model\-agnostic verification\-and\-refinement pipelines for hard reasoning \[1\], iterative\-contextual\-refinement implementations \[2\], and broader test\-time improvement methods such as iterative self\-feedback \[4, 5\], self\-consistency \[6\] and Tree\-of\-Thoughts search \[7\]\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:15`.
- [claim-020] **unverifiable** — paper:15 — Instead, it obtains two independent diagnoses, extracts the common core between them, validates that overlap against the current solution, and only then applies a correction\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:15`.
- [claim-023] **unverifiable** — paper:17 — First, we frame Mini Artichokes as a capability\-expansion fallback for hard items rather than as a cheap average\-accuracy booster\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:17`.
- [claim-025] **unverifiable** — paper:17 — Third, we report both hard\-item gains and easy\-item regressions, motivating selective routing instead of always\-on deployment, while explicitly treating compute efficiency against cost\-matched repeated sampling as an open question for future work\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:17`.
- [claim-027] **unverifiable** — paper:23 — The reported experiments exclude external tools, internet access, human feedback and task\-specific validators\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:23`.
- [claim-044] **unverifiable** — paper:35 — A short iterative\-contextual\-refinement\-style inner loop is used inside Solve to establish a minimum solution quality before downstream verification begins\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:35`.
- [claim-046] **unverifiable** — paper:37 — To reduce false positives from the verifier, a solution is accepted only after p consecutive successful verifications\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:37`.
- [claim-048] **unverifiable** — paper:37 — The reported gemma\-3\-27b\-it runs use p = 3 and f = 10, following the same general heuristic family used in the IMO25 pipeline \[1\]\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:37`.
- [claim-053] **unverifiable** — paper:41 — The reported gemma\-3\-27b\-it configuration uses rcap = 35, although this threshold is expected to require retuning for other models\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:41`.
- [claim-059] **unverifiable** — paper:71 — The reported experiments intentionally avoid tool integrations so that the results reflect the internal verification\-and\-refinement mechanism\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:71`.
- [claim-061] **unverifiable** — paper:75 — A small Legal Education Eligibility Test \(LEET\) subset was additionally run with gemini\-3\-flash\-preview to test whether the loop remains useful on a different commercial API model; the official model documentation is cited for reproducibility \[14\]\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:75`.
- [claim-062] **unverifiable** — paper:75 — The goal is not a vendor comparison, but a portability check\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:75`.
- [claim-066] **unverifiable** — paper:79 — We report full\-suite accuracy as the primary aggregate metric\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:79`.
- [claim-067] **unverifiable** — paper:79 — We also report hard\-item lift, defined by items that pass@1 solves at most once in 20 trials on PSAT, because average accuracy alone can hide large improvements on low\-baseline items\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:79`.
- [claim-068] **unverifiable** — paper:79 — For answer\-choice or numeric suites with 20 repeated direct trials, we additionally report a conservative direct self\-consistency estimate: an item is counted as correct only when the correct answer appears in a strict majority of the 20 pass@1 samples\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:79`.
- [claim-070] **unverifiable** — paper:81 — Baseline comparisons are reported at two levels\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:81`.
- [claim-072] **unverifiable** — paper:81 — This comparison is intentionally not cost\-matched: pass@1 serves as a low\-cost direct\-solving reference, whereas Mini Artichokes is evaluated as a high\-cost fallback procedure\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:81`.
- [claim-073] **unverifiable** — paper:81 — Therefore, the main comparison measures whether the fallback loop can change the distribution of reachable correct solutions, not whether it is more compute\-efficient than direct repeated sampling under the same call budget\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:81`.
- [claim-077] **unverifiable** — paper:83 — Repeated sampling asks whether at least one independent trajectory reaches a correct answer under a fixed budget; self\-consistency instead aggregates several direct samples, usually by majority vote over a stable final\-answer representation\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:83`.
- [claim-078] **unverifiable** — paper:83 — In this manuscript, the PSAT and AIME results support a conservative strict\-majority self\-consistency estimate from the repeated pass@1 trials, while best\-of\-20 is reported separately as an oracle repeated\-sampling view\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:83`.
- [claim-079] **unverifiable** — paper:83 — Because Putnam is proof\-style and does not reduce reliably to normalized answer strings, we do not report proof\-task answer\-vote self\-consistency as a main result\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:83`.
- [claim-081] **unverifiable** — paper:87 — As a post\-hoc stronger\-model sanity check rather than a full model comparison, we ran one Gemma 4 31B minimal\-thinking check on six prior Mini\-below\-pass@1 items; the Gemini API documentation lists the Gemma 4 model identifiers used here \[15\]\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:87`.
- [claim-083] **unverifiable** — paper:87 — Each item was run for 20 independent trials with pass@1 and Mini Artichokes\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:87`.
- [claim-088] **unverifiable** — paper:95 — Table 1 reports suite\-level accuracy and average API calls per trial\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:95`.
- [claim-089] **unverifiable** — paper:95 — Mini Artichokes improves average accuracy on all four reported suites, but the aggregate gains are modest: PSAT improves from 467/800 \(58\.4%\) to 491/800 \(61\.4%\), Putnam from 65/240 \(27\.1%\) to 71/240 \(29\.6%\), AIME from 61/300 \(20\.3%\) to 82/300 \(27\.3%\), and the LEET subset from 6/15 \(40\.0%\) to 7/15 \(46\.7%\)\. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:95`.
- (+119 further extracted claim(s) — mostly unverifiable prose — omitted here for brevity; all are labelled in S2/S4 with source lines.)

## Comment

Recommendation: 2/6. No headline result is mechanically supported yet, so the recommendation stays borderline pending stronger evidence. Most useful next step for the authors — For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report a broader-impact / ethics statement. Could the authors clarify these?
