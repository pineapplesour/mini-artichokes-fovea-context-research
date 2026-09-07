# ICML-Style Paper Review

## Paper and Evidence Identity

- Review method: deterministic evidence audit only (`--deterministic`). Every score and comment below is from the deterministic mechanical checks; no scientific-committee judgment is included.
- Review Agent name/version: paper-reviewer / `sha256:9886349f92661c3c73b70f216a7038b741b47282d7624538ad207dd3fbb2d4c0`
- Review-agent spec path/hash: `review-agent-spec.md` / `sha256:08b13516a2cb0e5151c6b4dc24f98e6d191b35ee30d69ea300b2d6ff2d5a5945`
- Original paper identity: `Mini_Artichokes_manuscript_v1.md` / `text/markdown` / `sha256:8f50203ad80297ee86de83deec3ef14e19795f52b286ec6276f18e16722526f3` / `30781` bytes
- Derived Markdown identity: `Mini_Artichokes_manuscript_v1.md` / `text/markdown` / `sha256:8f50203ad80297ee86de83deec3ef14e19795f52b286ec6276f18e16722526f3` / `30781` bytes
- Original PDF page count: `n/a`
- Converter: `none (Markdown source)`
- Paper version/hash: `Mini_Artichokes_manuscript_v1.md` / `sha256:8f50203ad80297ee86de83deec3ef14e19795f52b286ec6276f18e16722526f3`
- Evidence bundle reviewed: `evidence`: `EVIDENCE_SCOPE.md` (`sha256:7dbc819a9c3306e5f01106a4d439d2319658f55ce6590769a669c50d665e5fc6`), `MMLU_PROTOCOL_CONFIRMATION1.md` (`sha256:f78ea8a6294728e3b1abd3c6c3c74cdf89f474da83da0f0ae7b7f56d637c60ef`), `MMLU_PROTOCOL_REPLICATION2.md` (`sha256:0fe6bd59e759d1c761770267fe9b7a8f2bef5e2f47ba6c768e57cfe35352c9a7`), `MMLU_PRO_CUMULATIVE_RESULTS.md` (`sha256:52cbe8e02c8fe34f72d88ed6c24aa26dcf6afb45c44b3ede70fed4274242a39c`), `UNIVERSAL_DEVELOPMENT_RESULTS.md` (`sha256:e1a542a410331498e46472a0061c344cc806189898e0576b4a20d8188253f791`), `experiments.jsonl` (`sha256:9cea16878f3c750215c300ca473e89b91fb4215e8d6f96b31218ea58e32bd365`), `legal_boundary_score.json` (`sha256:14318b0953051f0ccb4a1ab3390914eb1abab000c45f48c618cd45a7fd8a4ba1`), `mmlu_pro_confirmation1_score.json` (`sha256:5ba78d945aff95e5c3b7d93b0a44d592bbe16b2587d4d2228d179f5e1339128f`), `mmlu_pro_cumulative_score.json` (`sha256:bdf7e36abcf05b8a05d921a259590b919f54da2b7a1658dcc4057acabc905fec`), `mmlu_pro_replication2_score.json` (`sha256:2442d9018a0241e203500f85e859d76c78cda52f74277090856f5b40d3ca7685`)
- Frozen at (UTC): `2026-09-01T12:01:31+00:00`

## Summary

The paper, "Mini Artichokes: Selective Arbitration of Repeated LLM Disagreement", presents a method and supporting experiments. It reports 100 quantitative result claim(s) and cites 23 prior work(s). Deterministic audit: 18 contradiction(s), 0 dishonest self-certification(s), 49 mechanical finding(s); 17 result claim(s) evidence-backed, 440 unverifiable. Overall recommendation: 1/6 [claim-001].

## Strengths

- The result claim is directly supported by the supplied evidence [claim-280].
- The result claim is directly supported by the supplied evidence [claim-281].
- The result claim is directly supported by the supplied evidence [claim-282].
- The result claim is directly supported by the supplied evidence [claim-283].
- The result claim is directly supported by the supplied evidence [claim-284].
- The result claim is directly supported by the supplied evidence [claim-285].
- The result claim is directly supported by the supplied evidence [claim-288].
- The result claim is directly supported by the supplied evidence [claim-301].
- The result claim is directly supported by the supplied evidence [claim-302].
- The result claim is directly supported by the supplied evidence [claim-303].
- The result claim is directly supported by the supplied evidence [claim-304].
- The result claim is directly supported by the supplied evidence [claim-305].
- The result claim is directly supported by the supplied evidence [claim-346].
- The result claim is directly supported by the supplied evidence [claim-347].
- The result claim is directly supported by the supplied evidence [claim-348].
- The result claim is directly supported by the supplied evidence [claim-349].
- The result claim is directly supported by the supplied evidence [claim-359].

## Weaknesses

- The template-compliance check observed required section 'Research Spec' is absent; expected a 'Research Spec' section [finding-001].
- The template-compliance check observed required section 'Self-Review' is absent; expected a 'Self-Review' section [finding-002].
- The template-compliance check observed required section 'Short Paper' is absent; expected a 'Short Paper' section [finding-003].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-004].
- The baseline-fairness check observed claim does not name a baseline: Repeated inference can improve large-language-model (LLM) reasoning, but; expected the improvement claim to identify the compared baseline [finding-005].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-006].
- The baseline-fairness check observed claim does not name a baseline: a statistically reliable improvement over direct inference on the tested; expected the improvement claim to identify the compared baseline [finding-007].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-008].
- The baseline-fairness check observed claim does not name a baseline: methods show that diversity and selection can outperform a single trajectory.; expected the improvement claim to identify the compared baseline [finding-009].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-010].
- The baseline-fairness check observed claim does not name a baseline: - **RQ1:** Does the frozen support-aware policy improve full-denominator; expected the improvement claim to identify the compared baseline [finding-011].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-012].
- The baseline-fairness check observed claim does not name a baseline: - **RQ2:** Does it outperform strong multi-call controls: three-draw majority; expected the improvement claim to identify the compared baseline [finding-013].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-014].
- The baseline-fairness check observed claim does not name a baseline: solutions can also improve mathematical reasoning [8].; expected the improvement claim to identify the compared baseline [finding-015].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-016].
- The baseline-fairness check observed claim does not name a baseline: the judge improve an answer by synthesizing new content.; expected the improvement claim to identify the compared baseline [finding-017].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-018].
- The baseline-fairness check observed claim does not name a baseline: The strict V3 development arm improved 566 to 587; expected the improvement claim to identify the compared baseline [finding-019].
- The baseline-fairness check observed claim does not name a baseline: OJ3 improved over D1 by 27 correct answers (+1.; expected the improvement claim to identify the compared baseline [finding-020].
- The baseline-fairness check observed no common numeric metric across baseline and candidate evidence; expected exactly one common metric for the baseline and candidate comparison [finding-021].
- The ledger-trace check observed paper reports correct=+1.35; expected one of the traceable correct values [613.0] [finding-022].
- The ledger-trace check observed paper reports correct=27; expected one of the traceable correct values [613.0] [finding-023].
- The ledger-trace check observed paper reports harms=+2.3; expected one of the traceable harms values [2.0, 3.0, 5.0, 6.0, 9.0, 13.0, 59.0] [finding-024].
- The ledger-trace check observed paper reports correct=13; expected one of the traceable correct values [613.0] [finding-025].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-026].
- The baseline-fairness check observed claim does not name a baseline: MMLU-Pro evidence: a stricter overlap policy improved 566/941 to 587/941 (+21;; expected the improvement claim to identify the compared baseline [finding-027].
- The ledger-trace check observed paper reports harms=.0005325; expected one of the traceable harms values [2.0, 3.0, 5.0, 6.0, 9.0, 13.0, 59.0] [finding-028].
- The ledger-trace check observed paper reports rescues=255; expected one of the traceable rescues values [6.0, 7.0, 28.0, 29.0, 30.0, 33.0, 35.0] [finding-029].
- The ledger-trace check observed paper reports rescues=464; expected one of the traceable rescues values [6.0, 7.0, 28.0, 29.0, 30.0, 33.0, 35.0] [finding-030].
- The ledger-trace check observed paper reports rescues=54.96; expected one of the traceable rescues values [6.0, 7.0, 28.0, 29.0, 30.0, 33.0, 35.0] [finding-031].
- The ledger-trace check observed paper reports loss=29; expected a rounding-compatible loss value in experiments.jsonl [finding-032].
- The ledger-trace check observed paper reports loss=65; expected a rounding-compatible loss value in experiments.jsonl [finding-033].
- The ledger-trace check observed paper reports correct=32; expected one of the traceable correct values [613.0] [finding-034].
- The ledger-trace check observed paper reports correct=49.2; expected one of the traceable correct values [613.0] [finding-035].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-036].
- The baseline-fairness check observed claim does not name a baseline: The strongest result is straightforward: the unchanged OJ3 policy improved; expected the improvement claim to identify the compared baseline [finding-037].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-038].
- The baseline-fairness check observed claim does not name a baseline: SC3 and GJ3 both significantly improved; expected the improvement claim to identify the compared baseline [finding-039].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-040].
- The baseline-fairness check observed claim does not name a baseline: support-aware policy significantly improved a preassigned direct Luna draw and; expected the improvement claim to identify the compared baseline [finding-041].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-042].
- The baseline-fairness check observed claim does not name a baseline: result is therefore narrow: selective arbitration can improve repeated LLM; expected the improvement claim to identify the compared baseline [finding-043].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-044].
- The baseline-fairness check observed claim does not name a baseline: Improve by Self-critiquing Their Own Plans?; expected the improvement claim to identify the compared baseline [finding-045].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-046].
- The baseline-fairness check observed claim does not name a baseline: Self-Consistency Improves Chain of; expected the improvement claim to identify the compared baseline [finding-047].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-048].
- The baseline-fairness check observed claim does not name a baseline: Improving Factuality and; expected the improvement claim to identify the compared baseline [finding-049].
- Scope limitation — the generalized claim at paper line 52 exceeds the supplied ledger coverage: 16 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 33 metrics (accuracy, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 102 exceeds the supplied ledger coverage: 16 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 33 metrics (accuracy, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 117 exceeds the supplied ledger coverage: 16 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 33 metrics (accuracy, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 299 exceeds the supplied ledger coverage: 16 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 33 metrics (accuracy, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 419 exceeds the supplied ledger coverage: 16 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 33 metrics (accuracy, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 518 exceeds the supplied ledger coverage: 16 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 33 metrics (accuracy, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 574 exceeds the supplied ledger coverage: 16 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 33 metrics (accuracy, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.

## Questions for the Authors

1. Concrete follow-up — Run the named baseline under the same metric and budget. [finding-004, finding-005, finding-006, finding-007, finding-008, finding-009, finding-010, finding-011, finding-012, finding-013, finding-014, finding-015, finding-016, finding-017, finding-018, finding-019, finding-020, finding-021, finding-026, finding-027, finding-036, finding-037, finding-038, finding-039, finding-040, finding-041, finding-042, finding-043, finding-044, finding-045, finding-046, finding-047, finding-048, finding-049]
2. 65 extracted result/arithmetic claim(s) could not be checked against the supplied evidence and are listed with their source lines in the Evidence Trace — could the authors provide the underlying results?

## Scores

- Overall recommendation: 1/6 — A proven integrity breach (18 issue(s)) drives a reject recommendation; supported results do not offset it [claim-001].
- Soundness: 1/4 — A proven integrity breach (18 contradiction(s), 0 dishonest self-certification(s)) undermines soundness [claim-001].
- Presentation: 1/4 — A deterministic template violation lowers presentation [finding-001]; the claim inventory begins at [claim-001].
- Significance: 3/4 — Multiple reported outcomes are evidence-supported, establishing nontrivial empirical scope without proving broad field impact [claim-280].
- Originality: 2/4 — The deterministic trace neither establishes nor disproves novelty [claim-001].
- Confidence: 4/5 — Verified result coverage is 35/100; claim extraction succeeded, positioning is covered, and 49 finding(s) are mechanically grounded [claim-001].

## Ethics and Limitations

Paper text was treated only as data. The injection audit sanitized hidden HTML and Unicode format controls before claim analysis and found 0 reviewer-directed instruction attempt(s). Broader ethics and evidence-quality claims outside S3 remain unverifiable [claim-001].

## Evidence Trace

- Pipeline execution: `S1 parse -> S2 claims -> S3 mech-check -> S4 verdicts -> S5 compose -> S6 freeze`.
- Frozen review identity: `sha256:54a056075bd054c3659c9145db42ced0e1915b31ea7fea4c40cf84c448f322aa`.
- Verdict labels digest: `sha256:c6f5497e3e9a33de48a20844ab63b581411ff26bf663148085a1cab691fcaf87`.
- External citation snapshot digest: `sha256:67a61f83ae960535e1825ecabd88447182cdfd3014cc193baa671945289e5a8c`.
- Output path: `mac_v1_ledger_deterministic.md`.
- Frozen paper input: `Mini_Artichokes_manuscript_v1.md` (`sha256:8f50203ad80297ee86de83deec3ef14e19795f52b286ec6276f18e16722526f3`).
- Frozen original identity: `Mini_Artichokes_manuscript_v1.md` (`text/markdown`, `sha256:8f50203ad80297ee86de83deec3ef14e19795f52b286ec6276f18e16722526f3`, 30781 bytes, page count=n/a).
- Frozen derived identity: `Mini_Artichokes_manuscript_v1.md` (`text/markdown`, `sha256:8f50203ad80297ee86de83deec3ef14e19795f52b286ec6276f18e16722526f3`, 30781 bytes).
- Frozen converter: `none (Markdown source)`.
- Pre-S1 sanitation: 0 trace(s), 0 injection finding(s).
- S1 parse inventory: 35 sections, 4 tables, 350 numeric tokens with source locations.
- S3 ledger-trace: 66/78 metric-labelled values matched; 12 finding(s).
- S3 internal-consistency: 0 comparison(s), 0 finding(s).
- S3 arithmetic: 0 recomputation(s), 0 finding(s).
- S3 baseline-fairness: 17 explicit improvement claim(s), 34 finding(s).
- S3 negative-evidence: 0 discard/crash outcome(s), 0 omission finding(s).
- S3 citation-existence: 4 explicit identifier(s), 0 existence/title finding(s).
- S3 template-compliance: 3 contract trace(s), 3 finding(s).
- S3 injection-scan: 0 sanitation trace(s), 0 reviewer-directed instruction finding(s).
- S3 self-review-audit: 0 checklist item(s), 0 dishonest self-certification(s).
- S3 positioning: 23 cited reference(s), related-work section=True, 0 novelty/superiority claim(s), 0 overclaim finding(s), 0 positioning question(s).
- S5 DRAFT/GROUND: 131 candidate comment(s), 131 retained, 0 deleted, 65 criticism comment(s) converted to questions.
- S2/S4 claim verdicts:
- [claim-001] **contradicted** — paper:5 — Repeated inference can improve large-language-model (LLM) reasoning, but — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-004`, `finding-005`.
- [claim-033] **contradicted** — paper:31 — a statistically reliable improvement over direct inference on the tested — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-006`, `finding-007`.
- [claim-053] **contradicted** — paper:55 — methods show that diversity and selection can outperform a single trajectory. — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-008`, `finding-009`.
- [claim-078] **contradicted** — paper:79 — **RQ1:** Does the frozen support-aware policy improve full-denominator — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-010`, `finding-011`.
- [claim-080] **contradicted** — paper:82 — **RQ2:** Does it outperform strong multi-call controls: three-draw majority — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-012`, `finding-013`.
- [claim-123] **contradicted** — paper:129 — solutions can also improve mathematical reasoning [8]. — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-014`, `finding-015`.
- [claim-186] **contradicted** — paper:211 — the judge improve an answer by synthesizing new content. — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-016`, `finding-017`.
- [claim-266] **contradicted** — paper:301 — The strict V3 development arm improved 566 to 587 — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-018`, `finding-019`.
- [claim-280] **supported** — paper:324 — D1 direct Luna | 597 | 590 | 1,187 | 59.35% — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:1#confirmation_1_correct (number-0118)`, `experiments.jsonl:1#replication_2_correct (number-0119)`, `experiments.jsonl:1#pooled_correct (number-0120)`, `experiments.jsonl:1#pooled_accuracy (number-0121)`.
- [claim-281] **supported** — paper:325 — D2 | 145 | 607 | 752 | 37.60% — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:2#confirmation_1_correct (number-0122)`, `experiments.jsonl:2#replication_2_correct (number-0123)`, `experiments.jsonl:2#pooled_correct (number-0124)`, `experiments.jsonl:2#pooled_accuracy (number-0125)`.
- [claim-282] **supported** — paper:326 — D3 | 587 | 586 | 1,173 | 58.65% — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:3#confirmation_1_correct (number-0126)`, `experiments.jsonl:3#replication_2_correct (number-0127)`, `experiments.jsonl:3#pooled_correct (number-0128)`, `experiments.jsonl:3#pooled_accuracy (number-0129)`.
- [claim-283] **supported** — paper:327 — SC3 majority | 596 | 613 | 1,209 | 60.45% — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:4#confirmation_1_correct (number-0130)`, `experiments.jsonl:4#replication_2_correct (number-0131)`, `experiments.jsonl:6#replication_2_correct (number-0131)`, `experiments.jsonl:4#pooled_correct (number-0132)`, `experiments.jsonl:4#pooled_accuracy (number-0133)`.
- [claim-284] **supported** — paper:328 — GJ3 generic judge | 600 | 611 | 1,211 | 60.55% — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:5#confirmation_1_correct (number-0134)`, `experiments.jsonl:5#replication_2_correct (number-0135)`, `experiments.jsonl:5#pooled_correct (number-0136)`, `experiments.jsonl:5#pooled_accuracy (number-0137)`.
- [claim-285] **supported** — paper:329 — **OJ3 support-aware judge** | **601** | **613** | **1,214** | **60.70%** — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:6#confirmation_1_correct (number-0138)`, `experiments.jsonl:4#replication_2_correct (number-0139)`, `experiments.jsonl:6#replication_2_correct (number-0139)`, `experiments.jsonl:6#pooled_correct (number-0140)`, `experiments.jsonl:6#pooled_accuracy (number-0141)`.
- [claim-287] **contradicted** — paper:335 — OJ3 improved over D1 by 27 correct answers (+1.35 percentage points), with 33 — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-020`, `finding-021`, `finding-022`, `finding-023`.
- [claim-288] **supported** — paper:336 — rescues and 6 harms (Table 2). — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:6#harms (number-0148)`, `experiments.jsonl:8#harms (number-0149)`.
- [claim-301] **supported** — paper:350 — **OJ3 vs D1** | **33** | **6** | **+27** | **7.15e-6** | **+0.75** | **+1.95** — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:6#rescues (number-0156)`, `experiments.jsonl:6#harms (number-0157)`, `experiments.jsonl:6#net_correct (number-0158)`, `experiments.jsonl:6#one_sided_exact_mcnemar_p (number-0159)`, `experiments.jsonl:6#ci_lower_pp (number-0160)`, `experiments.jsonl:6#ci_upper_pp (number-0161)`.
- [claim-302] **supported** — paper:351 — OJ3 vs SC3 | 7 | 2 | +5 | .08984 | -0.05 | +0.55 — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:8#rescues (number-0162)`, `experiments.jsonl:8#harms (number-0163)`, `experiments.jsonl:8#net_correct (number-0164)`, `experiments.jsonl:8#one_sided_exact_mcnemar_p (number-0165)`, `experiments.jsonl:8#ci_lower_pp (number-0166)`, `experiments.jsonl:8#ci_upper_pp (number-0167)`.
- [claim-303] **supported** — paper:352 — OJ3 vs GJ3 | 6 | 3 | +3 | .25391 | -0.15 | +0.45 — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:9#rescues (number-0168)`, `experiments.jsonl:9#net_correct (number-0170)`, `experiments.jsonl:9#one_sided_exact_mcnemar_p (number-0171)`, `experiments.jsonl:9#ci_lower_pp (number-0172)`, `experiments.jsonl:9#ci_upper_pp (number-0173)`.
- [claim-304] **supported** — paper:353 — SC3 vs D1 | 35 | 13 | +22 | .001044 | +0.45 | +1.80 — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:10#rescues (number-0174)`, `experiments.jsonl:10#harms (number-0175)`, `experiments.jsonl:10#net_correct (number-0176)`, `experiments.jsonl:10#one_sided_exact_mcnemar_p (number-0177)`, `experiments.jsonl:10#ci_lower_pp (number-0178)`, `experiments.jsonl:10#ci_upper_pp (number-0179)`, `experiments.jsonl:11#ci_upper_pp (number-0179)`.
- [claim-305] **supported** — paper:354 — GJ3 vs D1 | 29 | 5 | +24 | 1.93e-5 | +0.65 | +1.80 — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:11#rescues (number-0180)`, `experiments.jsonl:7#harms (number-0181)`, `experiments.jsonl:11#harms (number-0181)`, `experiments.jsonl:11#net_correct (number-0182)`, `experiments.jsonl:11#one_sided_exact_mcnemar_p (number-0183)`, `experiments.jsonl:11#ci_lower_pp (number-0184)`, `experiments.jsonl:10#ci_upper_pp (number-0185)`, `experiments.jsonl:11#ci_upper_pp (number-0185)`.
- [claim-307] **contradicted** — paper:357 — rescues, 5 harms, +2.3 percentage points, one-sided exact p=3.31e-5, and paired — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-024`.
- [claim-346] **supported** — paper:407 — D1 | 1 | 13,009,321 | 1.00x — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:1#total_tokens (number-0246)`.
- [claim-347] **supported** — paper:408 — SC3 | 3 | 45,056,433 | 3.46x — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:4#total_tokens (number-0249)`.
- [claim-348] **supported** — paper:409 — GJ3 | 4 | 45,787,649 | 3.52x — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:5#semantic_calls (number-0251)`, `experiments.jsonl:6#semantic_calls (number-0251)`, `experiments.jsonl:5#total_tokens (number-0252)`.
- [claim-349] **supported** — paper:410 — OJ3 | 4 | 45,973,780 | 3.53x — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:5#semantic_calls (number-0254)`, `experiments.jsonl:6#semantic_calls (number-0254)`, `experiments.jsonl:6#total_tokens (number-0255)`.
- [claim-355] **contradicted** — paper:420 — MMLU-Pro evidence: a stricter overlap policy improved 566/941 to 587/941 (+21; — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-026`, `finding-027`.
- [claim-359] **supported** — paper:425 — OJ3 produced 30 rescues but 59 harms — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:13#rescues (number-0279)`, `experiments.jsonl:16#rescues (number-0279)`, `experiments.jsonl:16#harms (number-0280)`.
- [claim-360] **contradicted** — paper:426 — relative to D1, a net loss of 29. — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-032`.
- [claim-361] **contradicted** — paper:426 — On 65 conflicts with a mechanical support — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-033`.
- (+445 further extracted claim(s) — mostly unverifiable prose — omitted here for brevity; all are labelled in S2/S4 with source lines.)

## Comment

Recommendation: 1/6. A proven integrity problem (a contradiction or dishonest self-certification) is the decisive factor and must be resolved before this paper can be accepted. Most useful next step for the authors — The template-compliance check observed required section 'Research Spec' is absent; expected a 'Research Spec' section [finding-001].
