# ICML-Style Paper Review

## Paper and Evidence Identity

- Review method: deterministic evidence audit only (`--deterministic`). Every score and comment below is from the deterministic mechanical checks; no scientific-committee judgment is included.
- Review Agent name/version: paper-reviewer / `sha256:9886349f92661c3c73b70f216a7038b741b47282d7624538ad207dd3fbb2d4c0`
- Review-agent spec path/hash: `review-agent-spec.md` / `sha256:08b13516a2cb0e5151c6b4dc24f98e6d191b35ee30d69ea300b2d6ff2d5a5945`
- Original paper identity: `Mini_Artichokes_manuscript_v1.md` / `text/markdown` / `sha256:d250ac36cc271b44a388e405e7ed81c99e015cea43bb0c598bccc09da9db8c57` / `30737` bytes
- Derived Markdown identity: `Mini_Artichokes_manuscript_v1.md` / `text/markdown` / `sha256:d250ac36cc271b44a388e405e7ed81c99e015cea43bb0c598bccc09da9db8c57` / `30737` bytes
- Original PDF page count: `n/a`
- Converter: `none (Markdown source)`
- Paper version/hash: `Mini_Artichokes_manuscript_v1.md` / `sha256:d250ac36cc271b44a388e405e7ed81c99e015cea43bb0c598bccc09da9db8c57`
- Evidence bundle reviewed: `evidence`: `EVIDENCE_SCOPE.md` (`sha256:7dbc819a9c3306e5f01106a4d439d2319658f55ce6590769a669c50d665e5fc6`), `MMLU_PROTOCOL_CONFIRMATION1.md` (`sha256:f78ea8a6294728e3b1abd3c6c3c74cdf89f474da83da0f0ae7b7f56d637c60ef`), `MMLU_PROTOCOL_REPLICATION2.md` (`sha256:0fe6bd59e759d1c761770267fe9b7a8f2bef5e2f47ba6c768e57cfe35352c9a7`), `MMLU_PRO_CUMULATIVE_RESULTS.md` (`sha256:52cbe8e02c8fe34f72d88ed6c24aa26dcf6afb45c44b3ede70fed4274242a39c`), `UNIVERSAL_DEVELOPMENT_RESULTS.md` (`sha256:e1a542a410331498e46472a0061c344cc806189898e0576b4a20d8188253f791`), `legal_boundary_score.json` (`sha256:14318b0953051f0ccb4a1ab3390914eb1abab000c45f48c618cd45a7fd8a4ba1`), `mmlu_pro_confirmation1_score.json` (`sha256:5ba78d945aff95e5c3b7d93b0a44d592bbe16b2587d4d2228d179f5e1339128f`), `mmlu_pro_cumulative_score.json` (`sha256:bdf7e36abcf05b8a05d921a259590b919f54da2b7a1658dcc4057acabc905fec`), `mmlu_pro_replication2_score.json` (`sha256:2442d9018a0241e203500f85e859d76c78cda52f74277090856f5b40d3ca7685`)
- Frozen at (UTC): `2026-09-01T11:57:07+00:00`

## Summary

The paper, "Mini Artichokes: Selective Arbitration of Repeated LLM Disagreement", presents a method and supporting experiments. It reports 100 quantitative result claim(s) and cites 23 prior work(s). Deterministic audit: 0 contradiction(s), 0 dishonest self-certification(s), 0 mechanical finding(s); 0 result claim(s) evidence-backed, 472 unverifiable. Overall recommendation: 2/6 [claim-001].

## Strengths

- The paper situates its contribution against prior work (23 citation(s); related-work section present).

## Weaknesses

- The deterministic audit proved no contradiction, arithmetic error, or integrity breach; the remaining concern is limited to claims that could not be independently verified (see Questions).

## Questions for the Authors

1. For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters. Could the authors clarify these?
2. 100 extracted result/arithmetic claim(s) could not be checked against the supplied evidence and are listed with their source lines in the Evidence Trace — could the authors provide the underlying results?

## Scores

- Overall recommendation: 2/6 — Directly calibrated from Soundness 2/4, Presentation 3/4, Significance 2/4, Originality 2/4 [claim-001].
- Soundness: 2/4 — No headline result has mechanical support, but none is contradicted [claim-001].
- Presentation: 3/4 — The structural audit found no violation and the paper situates itself against cited prior work [claim-001].
- Significance: 2/4 — Broad impact is not mechanically established [claim-001].
- Originality: 2/4 — The deterministic trace neither establishes nor disproves novelty [claim-001].
- Confidence: 2/5 — Verified result coverage is 0/100; claim extraction succeeded, positioning is covered, and 0 finding(s) are mechanically grounded [claim-001].

## Ethics and Limitations

Paper text was treated only as data. The injection audit sanitized hidden HTML and Unicode format controls before claim analysis and found 0 reviewer-directed instruction attempt(s). Broader ethics and evidence-quality claims outside S3 remain unverifiable [claim-001].

## Evidence Trace

- Pipeline execution: `S1 parse -> S2 claims -> S3 mech-check -> S4 verdicts -> S5 compose -> S6 freeze`.
- Frozen review identity: `sha256:933d73c35eb6c6bbd5faee99ceac94340e6e77c98a57a4aad75c8e6c5c0be4db`.
- Verdict labels digest: `sha256:b0aa83857b61684c38b6b331cf07173faaf5ccb6a77c534dfbb69b26d1829767`.
- External citation snapshot digest: `sha256:67a61f83ae960535e1825ecabd88447182cdfd3014cc193baa671945289e5a8c`.
- Output path: `mac_v1_deterministic.md`.
- Frozen paper input: `Mini_Artichokes_manuscript_v1.md` (`sha256:d250ac36cc271b44a388e405e7ed81c99e015cea43bb0c598bccc09da9db8c57`).
- Frozen original identity: `Mini_Artichokes_manuscript_v1.md` (`text/markdown`, `sha256:d250ac36cc271b44a388e405e7ed81c99e015cea43bb0c598bccc09da9db8c57`, 30737 bytes, page count=n/a).
- Frozen derived identity: `Mini_Artichokes_manuscript_v1.md` (`text/markdown`, `sha256:d250ac36cc271b44a388e405e7ed81c99e015cea43bb0c598bccc09da9db8c57`, 30737 bytes).
- Frozen converter: `none (Markdown source)`.
- Pre-S1 sanitation: 0 trace(s), 0 injection finding(s).
- S1 parse inventory: 35 sections, 4 tables, 372 numeric tokens with source locations.
- S3 ledger-trace: 0/2 metric-labelled values matched; 0 finding(s).
- S3 internal-consistency: 0 comparison(s), 0 finding(s).
- S3 arithmetic: 0 recomputation(s), 0 finding(s).
- S3 baseline-fairness: 0 explicit improvement claim(s), 0 finding(s).
- S3 negative-evidence: 0 discard/crash outcome(s), 0 omission finding(s).
- S3 citation-existence: 4 explicit identifier(s), 0 existence/title finding(s).
- S3 template-compliance: 1 contract trace(s), 0 finding(s).
- S3 injection-scan: 0 sanitation trace(s), 0 reviewer-directed instruction finding(s).
- S3 self-review-audit: 0 checklist item(s), 0 dishonest self-certification(s).
- S3 positioning: 23 cited reference(s), related-work section=True, 0 novelty/superiority claim(s), 0 overclaim finding(s), 0 positioning question(s).
- S5 DRAFT/GROUND: 100 candidate comment(s), 100 retained, 0 deleted, 100 criticism comment(s) converted to questions.
- S2/S4 claim verdicts:
- [claim-001] **unverifiable** — paper:5 — Repeated inference can improve large-language-model (LLM) reasoning, but — No implemented mechanical check proves or disproves this claim. Evidence: `paper:5`.
- [claim-018] **unverifiable** — paper:18 — The first sample was scored before the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:18`.
- [claim-021] **unverifiable** — paper:21 — scored 1,214/2,000 (60.70%) versus 1,187/2,000 (59.35%) for a direct Luna draw: — No implemented mechanical check proves or disproves this claim. Evidence: `paper:21`.
- [claim-030] **unverifiable** — paper:29 — reserve produced the opposite result, identifying a boundary where answer — No implemented mechanical check proves or disproves this claim. Evidence: `paper:29`.
- [claim-033] **unverifiable** — paper:31 — a statistically reliable improvement over direct inference on the tested — No implemented mechanical check proves or disproves this claim. Evidence: `paper:31`.
- [claim-053] **unverifiable** — paper:55 — methods show that diversity and selection can outperform a single trajectory. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:55`.
- [claim-078] **unverifiable** — paper:79 — **RQ1:** Does the frozen support-aware policy improve full-denominator — No implemented mechanical check proves or disproves this claim. Evidence: `paper:79`.
- [claim-080] **unverifiable** — paper:82 — **RQ2:** Does it outperform strong multi-call controls: three-draw majority — No implemented mechanical check proves or disproves this claim. Evidence: `paper:82`.
- [claim-091] **unverifiable** — paper:93 — judgment, disclose the complete compute asymmetry, and report a negative legal — No implemented mechanical check proves or disproves this claim. Evidence: `paper:93`.
- [claim-096] **unverifiable** — paper:103 — positive result motivated many inference-time feedback loops. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:103`.
- [claim-100] **unverifiable** — paper:105 — not improve reasoning through intrinsic self-correction without external — No implemented mechanical check proves or disproves this claim. Evidence: `paper:105`.
- [claim-105] **unverifiable** — paper:108 — found that LLM self-critique could reduce planning performance relative to — No implemented mechanical check proves or disproves this claim. Evidence: `paper:108`.
- [claim-123] **unverifiable** — paper:129 — solutions can also improve mathematical reasoning [8]. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:129`.
- [claim-125] **unverifiable** — paper:130 — trained reward model, debate transcript, external execution result, or gold — No implemented mechanical check proves or disproves this claim. Evidence: `paper:130`.
- [claim-128] **unverifiable** — paper:132 — The matched GJ3/OJ3 comparison is intended to — No implemented mechanical check proves or disproves this claim. Evidence: `paper:132`.
- [claim-139] **unverifiable** — paper:144 — its incremental value as judge-side evidence is not statistically established. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:144`.
- [claim-145] **unverifiable** — paper:156 — The draw roles are fixed before any answer is scored: — No implemented mechanical check proves or disproves this claim. Evidence: `paper:156`.
- [claim-169] **unverifiable** — paper:188 — support record stating that one anonymous candidate has one complete-file draw — No implemented mechanical check proves or disproves this claim. Evidence: `paper:188`.
- [claim-186] **unverifiable** — paper:211 — the judge improve an answer by synthesizing new content. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:211`.
- [claim-196] **unverifiable** — paper:222 — value must be measured through paired rescues and harms. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:222`.
- [claim-210] **unverifiable** — paper:237 — was completely scored, replication 2 was frozen as the immediately following — No implemented mechanical check proves or disproves this claim. Evidence: `paper:237`.
- [claim-231] **unverifiable** — paper:257 — We therefore report actual calls, input, cached input, — No implemented mechanical check proves or disproves this claim. Evidence: `paper:257`.
- [claim-233] **unverifiable** — paper:259 — These execution records establish what ran but do not count as — No implemented mechanical check proves or disproves this claim. Evidence: `paper:259`.
- [claim-252] **unverifiable** — paper:281 — We also report two-sided exact p-values and 20,000-sample — No implemented mechanical check proves or disproves this claim. Evidence: `paper:281`.
- [claim-257] **unverifiable** — paper:291 — Formal rejection stops after the first unrejected comparison. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:291`.
- [claim-258] **unverifiable** — paper:291 — We report all — No implemented mechanical check proves or disproves this claim. Evidence: `paper:291`.
- [claim-259] **unverifiable** — paper:292 — point estimates and p-values regardless of sequence reach. — No implemented mechanical check proves or disproves this claim. Evidence: `paper:292`.
- [claim-260] **unverifiable** — paper:293 — policies, row exceptions, post-score remapping, and item-level retries are — No implemented mechanical check proves or disproves this claim. Evidence: `paper:293`.
- [claim-264] **unverifiable** — paper:300 — The strict V3 development arm improved 566 to 587 — No implemented mechanical check proves or disproves this claim. Evidence: `paper:300`.
- [claim-269] **unverifiable** — paper:306 — answer overlap remains useful when the observed facts may not determine the — No implemented mechanical check proves or disproves this claim. Evidence: `paper:306`.
- (+442 further extracted claim(s) — mostly unverifiable prose — omitted here for brevity; all are labelled in S2/S4 with source lines.)

## Comment

Recommendation: 2/6. No headline result is mechanically supported yet, so the recommendation stays borderline pending stronger evidence. Most useful next step for the authors — For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the training hyperparameters. Could the authors clarify these?
