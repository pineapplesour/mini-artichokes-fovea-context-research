# ICML-Style Paper Review

## Paper and Evidence Identity

- Review method: full review — deterministic evidence audit + review panel. The panel's review is the official output; this document is its audit sidecar.
- Review Agent name/version: paper-reviewer / `sha256:9886349f92661c3c73b70f216a7038b741b47282d7624538ad207dd3fbb2d4c0`
- Review-agent spec path/hash: `review-agent-spec.md` / `sha256:08b13516a2cb0e5151c6b4dc24f98e6d191b35ee30d69ea300b2d6ff2d5a5945`
- Original paper identity: `Mini_Artichokes_manuscript_v3.md` / `text/markdown` / `sha256:95c0541a5fa6034a559a87a826ca9949fed1d6afa99faaca2e45353857dae429` / `49842` bytes
- Derived Markdown identity: `Mini_Artichokes_manuscript_v3.md` / `text/markdown` / `sha256:95c0541a5fa6034a559a87a826ca9949fed1d6afa99faaca2e45353857dae429` / `49842` bytes
- Original PDF page count: `n/a`
- Converter: `none (Markdown source)`
- Paper version/hash: `Mini_Artichokes_manuscript_v3.md` / `sha256:95c0541a5fa6034a559a87a826ca9949fed1d6afa99faaca2e45353857dae429`
- Evidence bundle reviewed: `evidence`: `EVIDENCE_SCOPE.md` (`sha256:a618bf8139997e26e432e82c0f74fea061a96989c6ded9526ed28fcfce2f541d`), `LEGAL_RESERVE_GOVERNANCE.md` (`sha256:33e0abeffb8cc6de841cb58b8f14ecb8926b9886f643d1e04ec77312f529e2d5`), `MMLU_PROTOCOL_CONFIRMATION1.md` (`sha256:f78ea8a6294728e3b1abd3c6c3c74cdf89f474da83da0f0ae7b7f56d637c60ef`), `MMLU_PROTOCOL_REPLICATION2.md` (`sha256:0fe6bd59e759d1c761770267fe9b7a8f2bef5e2f47ba6c768e57cfe35352c9a7`), `MMLU_PRO_CUMULATIVE_RESULTS.md` (`sha256:52cbe8e02c8fe34f72d88ed6c24aa26dcf6afb45c44b3ede70fed4274242a39c`), `SC3_BOUNDARY_AUDIT.md` (`sha256:fc38b4c284c643e4a4f9ba813f57bcac8c15e04069d72307b468e5410d1e7ad2`), `UNIVERSAL_DEVELOPMENT_RESULTS.md` (`sha256:e1a542a410331498e46472a0061c344cc806189898e0576b4a20d8188253f791`), `aider_hidden_java20_results.json` (`sha256:d1abe2a31712c0d446bba8728118246ce2a262bc44124600de95351df75ed9e6`), `aider_hidden_results.json` (`sha256:0c618e58ab5720e1044da799193325a5018c27e911179ed75048351af72461c1`), `experiments.jsonl` (`sha256:153c86902a4dff33581c081f09c880e4b0cee069b240f8f2973d4f3f5661271c`), `legal_boundary_score.json` (`sha256:14318b0953051f0ccb4a1ab3390914eb1abab000c45f48c618cd45a7fd8a4ba1`), `mmlu_pro_confirmation1_score.json` (`sha256:5ba78d945aff95e5c3b7d93b0a44d592bbe16b2587d4d2228d179f5e1339128f`), `mmlu_pro_cumulative_score.json` (`sha256:bdf7e36abcf05b8a05d921a259590b919f54da2b7a1658dcc4057acabc905fec`), `mmlu_pro_replication2_score.json` (`sha256:2442d9018a0241e203500f85e859d76c78cda52f74277090856f5b40d3ca7685`), `reasoning_method_screen.json` (`sha256:28122fee17330f5b0c317cf107f182a35604d1ee2c4805145305e950af0dba99`)
- Frozen at (UTC): `2026-09-02T01:58:38+00:00`

## Summary

The paper, "Mini Artichokes: Bounded Verification for Selective LLM Arbitration and Program Repair", presents a method and supporting experiments. It reports 121 quantitative result claim(s) and cites 29 prior work(s). Deterministic audit: 25 contradiction(s), 0 dishonest self-certification(s), 74 mechanical finding(s); 12 result claim(s) evidence-backed, 709 unverifiable. Overall recommendation: 2/6 [claim-001].

## Strengths

- The result claim is directly supported by the supplied evidence [claim-408].
- The result claim is directly supported by the supplied evidence [claim-409].
- The result claim is directly supported by the supplied evidence [claim-410].
- The result claim is directly supported by the supplied evidence [claim-411].
- The result claim is directly supported by the supplied evidence [claim-412].
- The result claim is directly supported by the supplied evidence [claim-413].
- The result claim is directly supported by the supplied evidence [claim-427].
- The result claim is directly supported by the supplied evidence [claim-473].
- The result claim is directly supported by the supplied evidence [claim-474].
- The result claim is directly supported by the supplied evidence [claim-475].
- The result claim is directly supported by the supplied evidence [claim-476].
- The result claim is directly supported by the supplied evidence [claim-488].

## Weaknesses

- The template-compliance check observed required section 'Research Spec' is absent; expected a 'Research Spec' section [finding-001].
- The template-compliance check observed required section 'Self-Review' is absent; expected a 'Self-Review' section [finding-002].
- The template-compliance check observed required section 'Short Paper' is absent; expected a 'Short Paper' section [finding-003].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-004].
- The baseline-fairness check observed claim does not name a baseline: Repeated inference can improve large-language-model (LLM) outputs, but; expected the improvement claim to identify the compared baseline [finding-005].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-006].
- The baseline-fairness check observed claim does not name a baseline: methods show that diversity and selection can outperform a single trajectory.; expected the improvement claim to identify the compared baseline [finding-007].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-008].
- The baseline-fairness check observed claim does not name a baseline: - **RQ1:** Does the frozen support-aware policy improve full-denominator; expected the improvement claim to identify the compared baseline [finding-009].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-010].
- The baseline-fairness check observed claim does not name a baseline: - **RQ2:** Does it outperform strong multi-call controls: three-draw majority; expected the improvement claim to identify the compared baseline [finding-011].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-012].
- The baseline-fairness check observed claim does not name a baseline: solutions can also improve mathematical reasoning [8].; expected the improvement claim to identify the compared baseline [finding-013].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-014].
- The baseline-fairness check observed claim does not name a baseline: authorization beats its compute-matched generic control.; expected the improvement claim to identify the compared baseline [finding-015].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-016].
- The baseline-fairness check observed claim does not name a baseline: the judge improve an answer by synthesizing new content.; expected the improvement claim to identify the compared baseline [finding-017].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-018].
- The baseline-fairness check observed claim does not name a baseline: The strict V3 development arm improved 566 to 587; expected the improvement claim to identify the compared baseline [finding-019].
- The ledger-trace check observed paper reports score=0; expected a rounding-compatible score value in experiments.jsonl [finding-020].
- The ledger-trace check observed paper reports score=20; expected a rounding-compatible score value in experiments.jsonl [finding-021].
- The ledger-trace check observed paper reports ci_lower_pp=-0.4; expected one of the traceable ci_lower_pp values [-0.15, -0.05, 0.45, 0.65, 0.75, 1.2] [finding-022].
- The ledger-trace check observed paper reports net_correct=0; expected one of the traceable net_correct values [-29.0, 3.0, 5.0, 21.0, 22.0, 23.0, 24.0, 27.0] [finding-023].
- The ledger-trace check observed paper reports one_sided_exact_mcnemar_p=.6875; expected one of the traceable one_sided_exact_mcnemar_p values [7.14963061909657e-06, 1.9279075786471367e-05, 3.309384919703007e-05, 0.0005325, 0.0010440536669982237, 0.08984375, 0.25390625] [finding-024].
- The ledger-trace check observed paper reports rescues=2; expected one of the traceable rescues values [6.0, 7.0, 28.0, 29.0, 30.0, 33.0, 35.0] [finding-025].
- The ledger-trace check observed paper reports rescues=2; expected one of the traceable rescues values [6.0, 7.0, 28.0, 29.0, 30.0, 33.0, 35.0] [finding-026].
- The ledger-trace check observed paper reports ci_lower_pp=-0.3; expected one of the traceable ci_lower_pp values [-0.15, -0.05, 0.45, 0.65, 0.75, 1.2] [finding-027].
- The ledger-trace check observed paper reports ci_upper_pp=+0.8; expected one of the traceable ci_upper_pp values [0.45, 0.55, 1.8, 1.95, 3.5] [finding-028].
- The ledger-trace check observed paper reports net_correct=+2; expected one of the traceable net_correct values [-29.0, 3.0, 5.0, 21.0, 22.0, 23.0, 24.0, 27.0] [finding-029].
- The ledger-trace check observed paper reports one_sided_exact_mcnemar_p=.36328; expected one of the traceable one_sided_exact_mcnemar_p values [7.14963061909657e-06, 1.9279075786471367e-05, 3.309384919703007e-05, 0.0005325, 0.0010440536669982237, 0.08984375, 0.25390625] [finding-030].
- The ledger-trace check observed paper reports rescues=5; expected one of the traceable rescues values [6.0, 7.0, 28.0, 29.0, 30.0, 33.0, 35.0] [finding-031].
- The ledger-trace check observed paper reports harms=7; expected one of the traceable harms values [2.0, 3.0, 5.0, 6.0, 9.0, 13.0, 59.0] [finding-032].
- The ledger-trace check observed paper reports one_sided_exact_mcnemar_p=9.55e-5; expected one of the traceable one_sided_exact_mcnemar_p values [7.14963061909657e-06, 1.9279075786471367e-05, 3.309384919703007e-05, 0.0005325, 0.0010440536669982237, 0.08984375, 0.25390625] [finding-033].
- The ledger-trace check observed paper reports ci_lower_pp=+1.1; expected one of the traceable ci_lower_pp values [-0.15, -0.05, 0.45, 0.65, 0.75, 1.2] [finding-034].
- The ledger-trace check observed paper reports ci_upper_pp=+3.1; expected one of the traceable ci_upper_pp values [0.45, 0.55, 1.8, 1.95, 3.5] [finding-035].
- The ledger-trace check observed paper reports one_sided_exact_mcnemar_p=2.46e-5; expected one of the traceable one_sided_exact_mcnemar_p values [7.14963061909657e-06, 1.9279075786471367e-05, 3.309384919703007e-05, 0.0005325, 0.0010440536669982237, 0.08984375, 0.25390625] [finding-036].
- The ledger-trace check observed paper reports rescues=24; expected one of the traceable rescues values [6.0, 7.0, 28.0, 29.0, 30.0, 33.0, 35.0] [finding-037].
- The ledger-trace check observed paper reports correct=13; expected one of the traceable correct values [613.0] [finding-038].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-039].
- The baseline-fairness check observed claim does not name a baseline: MMLU-Pro evidence: a stricter overlap policy improved 566/941 to 587/941 (+21;; expected the improvement claim to identify the compared baseline [finding-040].
- The ledger-trace check observed paper reports harms=.0005325; expected one of the traceable harms values [2.0, 3.0, 5.0, 6.0, 9.0, 13.0, 59.0] [finding-041].
- The ledger-trace check observed paper reports loss=29; expected a rounding-compatible loss value in experiments.jsonl [finding-042].
- The ledger-trace check observed paper reports loss=65; expected a rounding-compatible loss value in experiments.jsonl [finding-043].
- The ledger-trace check observed paper reports correct=32; expected one of the traceable correct values [613.0] [finding-044].
- The ledger-trace check observed paper reports correct=49.2; expected one of the traceable correct values [613.0] [finding-045].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-046].
- The baseline-fairness check observed claim does not name a baseline: The structured second-pass family improved over Plain in all three disjoint; expected the improvement claim to identify the compared baseline [finding-047].
- The ledger-trace check observed paper reports rescues=14; expected one of the traceable rescues values [6.0, 7.0, 28.0, 29.0, 30.0, 33.0, 35.0] [finding-048].
- The ledger-trace check observed paper reports rescues=15; expected one of the traceable rescues values [6.0, 7.0, 28.0, 29.0, 30.0, 33.0, 35.0] [finding-049].
- The ledger-trace check observed paper reports rescues=60; expected one of the traceable rescues values [6.0, 7.0, 28.0, 29.0, 30.0, 33.0, 35.0] [finding-050].
- The ledger-trace check observed paper reports rescues=60; expected one of the traceable rescues values [6.0, 7.0, 28.0, 29.0, 30.0, 33.0, 35.0] [finding-051].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-052].
- The baseline-fairness check observed claim does not name a baseline: MMLU-Pro cohort, the unchanged OJ3 policy improved direct Luna by 2.; expected the improvement claim to identify the compared baseline [finding-053].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-054].
- The baseline-fairness check observed claim does not name a baseline: SC3 and GJ3 both significantly improved; expected the improvement claim to identify the compared baseline [finding-055].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-056].
- The baseline-fairness check observed claim does not name a baseline: A two-call structured-repair family improved Plain by; expected the improvement claim to identify the compared baseline [finding-057].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-058].
- The baseline-fairness check observed claim does not name a baseline: stage can substantially improve the realized Graph artifact on these tasks.; expected the improvement claim to identify the compared baseline [finding-059].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-060].
- The baseline-fairness check observed claim does not name a baseline: The confirmatory replication improved by 2.; expected the improvement claim to identify the compared baseline [finding-061].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-062].
- The baseline-fairness check observed claim does not name a baseline: OJ3 beats direct inference but not; expected the improvement claim to identify the compared baseline [finding-063].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-064].
- The baseline-fairness check observed claim does not name a baseline: the compute-matched generic judge; structured repair beats Plain and Graph,; expected the improvement claim to identify the compared baseline [finding-065].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-066].
- The baseline-fairness check observed claim does not name a baseline: support-aware policy significantly improved a preassigned direct Luna draw.; expected the improvement claim to identify the compared baseline [finding-067].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-068].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-069].
- The baseline-fairness check observed claim does not name a baseline: Improve by Self-critiquing Their Own Plans?; expected the improvement claim to identify the compared baseline [finding-070].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-071].
- The baseline-fairness check observed claim does not name a baseline: Self-Consistency Improves Chain of; expected the improvement claim to identify the compared baseline [finding-072].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-073].
- The baseline-fairness check observed claim does not name a baseline: Improving Factuality and; expected the improvement claim to identify the compared baseline [finding-074].
- Scope limitation — the generalized claim at paper line 55 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 127 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 142 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 381 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 540 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 746 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 758 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 798 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 834 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.

## Questions for the Authors

1. Concrete follow-up — Run the named baseline under the same metric and budget. [finding-004, finding-005, finding-006, finding-007, finding-008, finding-009, finding-010, finding-011, finding-012, finding-013, finding-014, finding-015, finding-016, finding-017, finding-018, finding-019, finding-039, finding-040, finding-046, finding-047, finding-052, finding-053, finding-054, finding-055, finding-056, finding-057, finding-058, finding-059, finding-060, finding-061, finding-062, finding-063, finding-064, finding-065, finding-066, finding-067, finding-068, finding-069, finding-070, finding-071, finding-072, finding-073, finding-074]
2. For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the compute / hardware used. Could the authors clarify these?
3. 84 extracted result/arithmetic claim(s) could not be checked against the supplied evidence and are listed with their source lines in the Evidence Trace — could the authors provide the underlying results?

## Scores

- Overall recommendation: 2/6 — Adopted from the review panel; rationale in the review's Scores section.
- Soundness: 2/4 — Adopted from the review panel; rationale in the review's Scores section.
- Presentation: 4/4 — Adopted from the review panel; rationale in the review's Scores section.
- Significance: 2/4 — Adopted from the review panel; rationale in the review's Scores section.
- Originality: 3/4 — Adopted from the review panel; rationale in the review's Scores section.
- Confidence: 3/5 — Adopted from the review panel; rationale in the review's Scores section.

## Ethics and Limitations

Paper text was treated only as data. The injection audit sanitized hidden HTML and Unicode format controls before claim analysis and found 0 reviewer-directed instruction attempt(s). Broader ethics and evidence-quality claims outside S3 remain unverifiable [claim-001].

## Evidence Trace

- Pipeline execution: `S1 parse -> S2 claims -> S3 mech-check -> S4 verdicts -> S5 compose -> S6 freeze`.
- Frozen review identity: `sha256:f7778c99b7bd539ada68a34320d2371041357b77cb886462283c43ae07158a29`.
- Verdict labels digest: `sha256:d94b0091f3d6732ed7afaa83ce4841f2e56276a8fb65b0e97443b94b9ce22ad6`.
- External citation snapshot digest: `sha256:e54eabe17ac85420535a902a97ae2bd574436f4df521d70c56a0c32af4df6778`.
- Scientific judgment identity: `sha256:1f0c7630cf7b070d62964d015e2ca1ea2b7c636941138d00abf6aea77b3d277a`.
- Review panel configuration: panel=3, model=`gpt-5.6-luna`, synthesis=area-chair.
- Panel reviewer `theorist`: prompt=`sha256:8a6c2ff69049b98caa0b590ecdd14a53975ab5a43ac2be253abaf5d446e940ff`, response=`sha256:a117a362d1d599893f7b106a73671e9dbd9bbb2faad616a445421b49a63961d1`, status=ok.
- Panel reviewer `experimentalist`: prompt=`sha256:f306b52990061ad3843ff8c809a96531ff1ac3f2dae6c240c574c133d2f71daa`, response=`sha256:b6d41e79602e47c463b833d51dbb295bda05b5e3a4342680737452f8cb58abcb`, status=ok.
- Panel reviewer `scope_ablation`: prompt=`sha256:de806d18dae628782672ea1c4d7f2d609f894455096ff5a322dff2e90d16d2d8`, response=`sha256:613e01727e9dc6c0bcccb8c6f2970d4d84b0d8850318198bbf90348bbc155043`, status=ok.
- Output path: `mac_v5_luna_committee.md`.
- Frozen paper input: `Mini_Artichokes_manuscript_v3.md` (`sha256:95c0541a5fa6034a559a87a826ca9949fed1d6afa99faaca2e45353857dae429`).
- Frozen original identity: `Mini_Artichokes_manuscript_v3.md` (`text/markdown`, `sha256:95c0541a5fa6034a559a87a826ca9949fed1d6afa99faaca2e45353857dae429`, 49842 bytes, page count=n/a).
- Frozen derived identity: `Mini_Artichokes_manuscript_v3.md` (`text/markdown`, `sha256:95c0541a5fa6034a559a87a826ca9949fed1d6afa99faaca2e45353857dae429`, 49842 bytes).
- Frozen converter: `none (Markdown source)`.
- Pre-S1 sanitation: 0 trace(s), 0 injection finding(s).
- S1 parse inventory: 40 sections, 6 tables, 573 numeric tokens with source locations.
- S3 ledger-trace: 47/75 metric-labelled values matched; 28 finding(s).
- S3 internal-consistency: 0 comparison(s), 0 finding(s).
- S3 arithmetic: 0 recomputation(s), 0 finding(s).
- S3 baseline-fairness: 22 explicit improvement claim(s), 43 finding(s).
- S3 negative-evidence: 0 discard/crash outcome(s), 0 omission finding(s).
- S3 citation-existence: 5 explicit identifier(s), 0 existence/title finding(s).
- S3 template-compliance: 3 contract trace(s), 3 finding(s).
- S3 injection-scan: 0 sanitation trace(s), 0 reviewer-directed instruction finding(s).
- S3 self-review-audit: 0 checklist item(s), 0 dishonest self-certification(s).
- S3 positioning: 29 cited reference(s), related-work section=True, 0 novelty/superiority claim(s), 0 overclaim finding(s), 0 positioning question(s).
- S5 DRAFT/GROUND: 170 candidate comment(s), 170 retained, 0 deleted, 84 criticism comment(s) converted to questions.
- S2/S4 claim verdicts:
- [claim-001] **contradicted** — paper:5 — Repeated inference can improve large-language-model (LLM) outputs, but — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-004`, `finding-005`.
- [claim-053] **contradicted** — paper:58 — methods show that diversity and selection can outperform a single trajectory. — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-006`, `finding-007`.
- [claim-085] **contradicted** — paper:87 — **RQ1:** Does the frozen support-aware policy improve full-denominator — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-008`, `finding-009`.
- [claim-087] **contradicted** — paper:90 — **RQ2:** Does it outperform strong multi-call controls: three-draw majority — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-010`, `finding-011`.
- [claim-143] **contradicted** — paper:154 — solutions can also improve mathematical reasoning [8]. — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-012`, `finding-013`.
- [claim-227] **contradicted** — paper:250 — the judge improve an answer by synthesizing new content. — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-016`, `finding-017`.
- [claim-350] **contradicted** — paper:383 — The strict V3 development arm improved 566 to 587 — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-018`, `finding-019`.
- [claim-381] **contradicted** — paper:413 — Starter scores were 0/20, — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-020`, `finding-021`.
- [claim-408] **supported** — paper:446 — D1 direct Luna | 597 | 590 | 1,187 | 59.35% — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:1#confirmation_1_correct (number-0186)`, `experiments.jsonl:1#replication_2_correct (number-0187)`, `experiments.jsonl:1#pooled_correct (number-0188)`, `experiments.jsonl:1#pooled_accuracy (number-0189)`.
- [claim-409] **supported** — paper:447 — D2 | 145 | 607 | 752 | 37.60% — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:2#confirmation_1_correct (number-0190)`, `experiments.jsonl:2#replication_2_correct (number-0191)`, `experiments.jsonl:2#pooled_correct (number-0192)`, `experiments.jsonl:2#pooled_accuracy (number-0193)`.
- [claim-410] **supported** — paper:448 — D3 | 587 | 586 | 1,173 | 58.65% — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:3#confirmation_1_correct (number-0194)`, `experiments.jsonl:3#replication_2_correct (number-0195)`, `experiments.jsonl:3#pooled_correct (number-0196)`, `experiments.jsonl:3#pooled_accuracy (number-0197)`.
- [claim-411] **supported** — paper:449 — SC3 majority | 596 | 613 | 1,209 | 60.45% — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:4#confirmation_1_correct (number-0198)`, `experiments.jsonl:4#replication_2_correct (number-0199)`, `experiments.jsonl:6#replication_2_correct (number-0199)`, `experiments.jsonl:4#pooled_correct (number-0200)`, `experiments.jsonl:4#pooled_accuracy (number-0201)`.
- [claim-412] **supported** — paper:450 — GJ3 generic judge | 600 | 611 | 1,211 | 60.55% — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:5#confirmation_1_correct (number-0202)`, `experiments.jsonl:5#replication_2_correct (number-0203)`, `experiments.jsonl:5#pooled_correct (number-0204)`, `experiments.jsonl:5#pooled_accuracy (number-0205)`.
- [claim-413] **supported** — paper:451 — **OJ3 support-aware judge** | **601** | **613** | **1,214** | **60.70%** — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:6#confirmation_1_correct (number-0206)`, `experiments.jsonl:4#replication_2_correct (number-0207)`, `experiments.jsonl:6#replication_2_correct (number-0207)`, `experiments.jsonl:6#pooled_correct (number-0208)`, `experiments.jsonl:6#pooled_accuracy (number-0209)`.
- [claim-427] **supported** — paper:470 — **OJ3 vs D1** | **28** | **5** | **+23** | **3.31e-5** | **+1.2** | **+3.5** — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:7#rescues (number-0236)`, `experiments.jsonl:7#harms (number-0237)`, `experiments.jsonl:11#harms (number-0237)`, `experiments.jsonl:7#net_correct (number-0238)`, `experiments.jsonl:7#one_sided_exact_mcnemar_p (number-0239)`, `experiments.jsonl:7#ci_lower_pp (number-0240)`, `experiments.jsonl:7#ci_upper_pp (number-0241)`.
- [claim-428] **contradicted** — paper:471 — OJ3 vs SC3 | 2 | 2 | 0 | .6875 | -0.4 | +0.4 — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-022`, `finding-023`, `finding-024`, `finding-025`, `finding-026`.
- [claim-429] **contradicted** — paper:472 — OJ3 vs GJ3 | 5 | 3 | +2 | .36328 | -0.3 | +0.8 — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-027`, `finding-028`, `finding-029`, `finding-030`, `finding-031`.
- [claim-430] **contradicted** — paper:473 — SC3 vs D1 | 30 | 7 | +23 | 9.55e-5 | +1.2 | +3.5 — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-032`, `finding-033`.
- [claim-431] **contradicted** — paper:474 — GJ3 vs D1 | 24 | 3 | +21 | 2.46e-5 | +1.1 | +3.1 — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-034`, `finding-035`, `finding-036`, `finding-037`.
- [claim-473] **supported** — paper:528 — D1 | 1 | 13,009,321 | 1.00x — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:1#total_tokens (number-0328)`.
- [claim-474] **supported** — paper:529 — SC3 | 3 | 45,056,433 | 3.46x — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:4#total_tokens (number-0331)`.
- [claim-475] **supported** — paper:530 — GJ3 | 4 | 45,787,649 | 3.52x — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:5#semantic_calls (number-0333)`, `experiments.jsonl:6#semantic_calls (number-0333)`, `experiments.jsonl:5#total_tokens (number-0334)`.
- [claim-476] **supported** — paper:531 — OJ3 | 4 | 45,973,780 | 3.53x — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:5#semantic_calls (number-0336)`, `experiments.jsonl:6#semantic_calls (number-0336)`, `experiments.jsonl:6#total_tokens (number-0337)`.
- [claim-482] **contradicted** — paper:541 — MMLU-Pro evidence: a stricter overlap policy improved 566/941 to 587/941 (+21; — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-039`, `finding-040`.
- [claim-488] **supported** — paper:547 — Relative to P1, OJ3 produced 30 rescues — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:13#rescues (number-0364)`, `experiments.jsonl:17#rescues (number-0364)`.
- [claim-489] **contradicted** — paper:548 — but 59 harms, a net loss of 29. — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-042`.
- [claim-490] **contradicted** — paper:548 — On 65 cases carrying the mechanical support — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-043`.
- [claim-491] **contradicted** — paper:549 — signal, the supported outcome was correct only 32 times (49.2%). — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-044`, `finding-045`.
- [claim-497] **contradicted** — paper:557 — The structured second-pass family improved over Plain in all three disjoint — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-046`, `finding-047`.
- [claim-504] **contradicted** — paper:564 — Against Graph alone, the family scored 29/60 versus 14/60: 15 rescues, no — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-048`, `finding-049`, `finding-050`, `finding-051`.
- (+716 further extracted claim(s) — mostly unverifiable prose — omitted here for brevity; all are labelled in S2/S4 with source lines.)

## Comment

Recommendation: 2/6. A proven integrity problem (a contradiction or dishonest self-certification) is the decisive factor and must be resolved before this paper can be accepted. Most useful next step for the authors — The template-compliance check observed required section 'Research Spec' is absent; expected a 'Research Spec' section [finding-001].

## Panel Reviews (provenance)

### Panel review 1 — theorist (accepted)

# Review: Mini Artichokes: Bounded Verification for Selective LLM Arbitration and Program Repair

## Summary

This paper proposes a bounded-update framework for inference-time correction: freeze an initial answer or patch, trigger a separate decision stage only on observable disagreement or failure, restrict the update, and preserve unaffected work. It evaluates support-aware arbitration on two 1,000-question MMLU-Pro cohorts and structured repair on three 20-task Aider batches. The strongest result is the replication-2 improvement from 590/1,000 to 613/1,000, but the paper also shows that OJ3 does not significantly outperform compute-matched generic judging and that the coding evidence is descriptive and highly clustered.

## Strengths

- The paper makes a clear distinction between routing and evidence. It explicitly states that “agreement identifies cases worth re-examining” while the judge may separately use “the number of supporting draws,” which is an important conceptual separation.

- The arbitration protocol is concrete and reproducible. The method fixes D1 as the base, defines conflicts mechanically as “D2=D3≠D1,” anonymizes candidate provenance, and uses a “base-preserving fallback.” These choices make the intended intervention substantially clearer than an unconstrained self-refinement loop.

- The primary MMLU-Pro comparison is reported on the full denominator and with paired outcomes: “OJ3 scored 613/1,000 versus D1's 590/1,000,” with “28 rescues, 5 harms” and a confidence interval of “[+1.2,+3.5] points.” The paper appropriately avoids presenting the pooled 2,000-question result as confirmatory.

- The authors are unusually candid about mechanism attribution. They state that “the additional support count remains a candidate mechanism rather than a confirmed one,” and report that OJ3 “tied SC3” and was not significantly better than GJ3. This substantially improves the paper’s scientific credibility.

- The coding study uses meaningful external evidence rather than purely intrinsic self-critique. The repair pass receives “complete failure stdout,” derives counterexamples, and audits the final patch against the original requirements. This is a plausible and practically relevant bounded-repair design.

- The paper reports important negative results. In particular, OJ3 lost relative to the plain legal baseline, with “30 rescues but 59 harms,” and strict overlap authorization scored 5/20 versus 7/20 for matched repair. These results prevent the paper from overstating agreement as a universal reliability signal.

- Presentation is strong overall. The claim hierarchy, explicit inferential boundary, rescue/harm accounting, and separate reporting of confirmatory versus descriptive evidence make the argument easy to audit.

## Weaknesses

- The central MMLU-Pro significance claim is not robust to the execution design. Each draw is produced in “one complete-file agent session,” and the paper admits that the results “do not estimate between-session repeatability.” The extreme D2 result—“145/1,000” in confirmation 1 versus “607/1,000” in replication 2—suggests substantial session-level instability. Item-level McNemar tests and bootstraps may therefore substantially understate uncertainty when outcomes are correlated within a shared session.

- The mechanism-specific contribution is not established. OJ3’s advantage over D1 is compatible with spending roughly 3.5 times the inference tokens on multiple draws and a judge; however, the paper reports that OJ3 “tied SC3” and had only a descriptive “+2 point estimate over GJ3.” Thus the evidence supports a particular expensive multi-call system over one direct draw, but not the claimed value of support-aware arbitration as opposed to ordinary candidate selection or majority voting.

- The D2 anomaly is not adequately diagnosed. The paper calls it an “extreme low outlier” but does not provide the invalid-mapping breakdown, output-format failure rate, ordering/context analysis, or session trace needed to determine whether this reflects model variability, whole-file degradation, parsing failure, or another runtime artifact. This matters because the trigger and all multi-draw comparisons depend on the reliability of those complete-file sessions.

- The coding transfer does not provide a clean replication of a fixed method. The authors acknowledge that “batch 2 corrected one language-specific packaging sentence” and that “the Java repair lead was strengthened before freezing.” The 29/60 aggregate is therefore a method-family summary, not an identical-prompt evaluation. Moreover, the paper states that each batch shares “one whole-batch model invocation,” leaving only three call clusters per arm; the task-level p-values and bootstrap interval consequently do not support broad population-level inference.

- The common framework is currently more of a design principle than a demonstrated unified method. In multiple choice, the update is selection between two fixed answers; in coding, it is a separately engineered patch-generation process using host-evaluated failures. The paper itself says this is “a transfer of the bounded-update contract, not the same algorithm.” That is reasonable, but the experiments do not show that the abstract contract predicts when an update is safe or beneficial across regimes.

- The paper offers no formal condition connecting the observable trigger to expected correctness. The MMLU-Pro conflicts contain 35 correct consensus candidates, 13 correct bases, and 20 cases where both are wrong, while the legal reserve reverses the signal. The results demonstrate that overlap can be useful or harmful, but they do not yield a principled, domain-agnostic criterion for deciding when the expected rescue rate will exceed the harm rate before paying for additional inference.

- Generality is limited by the evaluation scope. The primary evidence uses one model family, one runtime, one multiple-choice benchmark, and three small coding batches. The authors appropriately state that the result “does not establish” other-model generality, but this limitation substantially weakens the broad framing of a universal bounded-verification system.

## Questions for the Authors

1. Can you rerun D1–D3 and the judge on the same fixed questions with independently initialized whole-file sessions, and report how often the +2.3-point improvement persists? In particular, what caused the 145/1,000 D2 result, and how many outputs were invalid or malformed?

2. How does OJ3 compare with GJ3 over a substantially larger, independently sampled conflict set? Given that the paper reports “OJ3 vs GJ3” as only 5 rescues versus 3 harms, what evidence supports treating the support annotation as more than an unresolved hypothesis?

3. Can you provide a fully pre-frozen coding evaluation with identical prompts and repair instructions across batches, plus inference at the batch/call-cluster level rather than task-level significance? This would clarify whether the structured-repair gain survives the prompt evolution and whole-batch dependence.

4. Can the authors formulate and test a domain-agnostic pre-inference criterion predicting when agreement is beneficial? The legal reserve achieved only “32” correct supported outcomes out of 65, so the practical value of the proposed trigger currently appears knowable only after observing the outcome.

## Scores

Soundness: 3/4 — The protocol and reporting are careful, but the main statistical evidence conditions on unstable whole-file sessions and does not establish repeatability.

Presentation: 4/4 — The paper is unusually clear about claim boundaries, controls, limitations, and rescue/harm accounting.

Significance: 2/4 — The primary gain is modest and expensive, while the method does not beat its strongest compute-matched controls.

Originality: 2/4 — The bounded-update synthesis is useful, but the underlying components and the selective-judge formulation are close to established inference-time techniques.

Overall recommendation: 3/6 — Borderline; the paper contains a credible empirical observation but does not yet establish a general or mechanism-specific contribution at ICML strength.

Confidence: 3/5 — The paper is sufficiently self-contained to assess, but the absence of repeated identical-session evaluations makes the empirical uncertainty difficult to quantify.

## Ethics and Limitations

The paper appropriately discusses the increased compute cost—“45.97 million tokens across the two OJ3 cohorts”—and cautions against using same-model agreement in high-stakes settings. The legal data raise a genuine privacy concern: the authors state that they “did not establish full de-identification of facts” and that distinctive events may remain re-identifiable. Withholding legal item texts pending governance review is therefore appropriate. The limitations section is candid about model, runtime, session, benchmark, dependence, and coding-scope limitations. These disclosures are strengths, but they also mean that the current evidence should be interpreted as a carefully bounded case study rather than a demonstrated general-purpose verification principle.

## Comment

I recommend borderline consideration. The strongest contribution is the careful empirical distinction between an end-to-end benefit from additional structured inference and a mechanism-specific benefit from overlap metadata; the paper correctly finds evidence for the former but not the latter. The most important revision is to establish session-level repeatability on identical frozen items, diagnose the anomalous D2 run, and use a fully pre-frozen, cluster-aware coding evaluation before making broader claims about bounded verification.

### Panel review 2 — experimentalist (accepted)

# Review: Mini Artichokes: Bounded Verification for Selective LLM Arbitration and Program Repair

## Summary

This paper proposes a conservative inference-time framework that freezes an initial answer or code patch, invokes a bounded second-stage decision only after an observable conflict or failure, and preserves unaffected work. On a 1,000-question MMLU-Pro replication, support-aware arbitration improves one direct Luna run by 2.3 points, but does not significantly outperform compute-matched generic judging. On three small Aider batches, structured repair improves the realized Plain baseline, although the coding evidence is descriptive and does not establish overlap authorization as the cause.

## Strengths

- The paper makes a useful distinction between routing and evidence: “agreement identifies cases worth re-examining” whereas “the judge may use the number of supporting draws.” This is a clear and testable decomposition.

- The arbitration protocol is concrete and conservative. The method requires that “the judge must solve or check the question, may use the support count as a prior, and cannot create a third answer,” with a “base-preserving fallback.”

- The confirmatory MMLU-Pro comparison is reported transparently on the full denominator: OJ3 achieves “613/1,000 versus D1's 590/1,000,” with “28 rescues, 5 harms,” and a paired-bootstrap interval of “[+1.2,+3.5] points.”

- The authors appropriately avoid overstating mechanism attribution. They explicitly report that OJ3 “was not significantly better than a compute-matched generic judge” and that “support annotation did not beat a generic judge.”

- The paper reports meaningful negative and null results, including the legal reserve where “OJ3 produced 30 rescues but 59 harms,” and the Java ablation where strict overlap “lost two tasks to matched repair.”

- The presentation is unusually candid about experimental dependence and scope. For example, the authors state that coding task-level tests “can be optimistic under within-call dependence” and that the study is “not the full 225-task Aider leaderboard.”

## Weaknesses

- The central empirical evidence is based on single realized whole-file sessions rather than repeated independent pipeline runs. The paper itself acknowledges that the reported intervals “do not estimate between-session repeatability,” while the anomalous D2 result was only “145/1,000” in confirmation 1 and “607/1,000” in replication 2. Thus, the strong item-level p-value mainly establishes an improvement over these particular sessions, not robust superiority of the procedure across executions.

- The strongest MMLU result does not establish the paper’s distinctive support-aware mechanism. OJ3 and GJ3 differ on only 13 conflicts; OJ3 versus GJ3 has “5 rescues, 3 harms” and `p=.3633`. Since SC3 and GJ3 already improve over D1, the evidence supports extra compute and generic judging more strongly than support-count arbitration.

- The coding transfer is substantially confounded. The authors state that “batch 2 corrected one language-specific packaging sentence, and the Java repair lead was strengthened before its sample was frozen.” Consequently, the 29/60 aggregate combines changing prompts and a strengthened method, rather than testing one frozen system across independent batches. The reported task-level `p=.00418` is also difficult to interpret when “each 20-task batch shares one whole-batch model invocation”; the cluster-level sign test is only `p=.125`.

- The proposed common principle is broader than what is experimentally isolated. Multiple-choice arbitration and code repair differ materially: coding uses “actual execution feedback,” permits edits, and applies requirement reconstruction and double audits. The paper’s own conclusion narrows the result to “a separate evidence-using repair stage,” leaving unclear which bounded-update components are necessary or whether the unifying abstraction has predictive value.

- The baseline and efficiency claims remain limited. OJ3 uses “3.53 times D1's tokens,” and the main gain is against a single direct draw. Although GJ3 is compute-matched, OJ3 does not win it significantly, so the paper does not demonstrate an accuracy improvement at a fixed practical budget.

- Generality is under-supported: the confirmatory study uses one model, one runtime, and one multiple-choice benchmark, while the coding study covers only “a 60-task subset of three languages.” The legal reversal further suggests that the trigger can fail under partial evidence, making claims about a general answer-engine principle premature.

## Questions for the Authors

1. Across repeated independent runs on the same frozen MMLU-Pro items, how often does OJ3 outperform D1 and GJ3, and how variable are the conflict rate and D2 quality?

2. Can the authors provide a fully frozen coding protocol, including identical prompts and repair instructions, evaluated on additional independently sampled batches or multiple model sessions?

3. What is the practical accuracy-per-token or accuracy-per-second comparison among D1, SC3, GJ3, and OJ3, and under what budget would OJ3 be preferable to simply using a stronger single call?

4. Can the authors isolate the contribution of each coding component—requirement reconstruction, counterexample generation, preservation, and double audit—rather than comparing an evolving repair family?

5. How are hidden-test failure outputs sanitized to ensure they do not expose expected values or other information that would make the repair setting easier than ordinary hidden-test repair?

## Scores

Soundness: 3/4 — The protocols and caveats are careful, but single-session execution and clustered coding calls limit the strength of the statistical conclusions.

Presentation: 4/4 — The paper is clear, well organized, and unusually explicit about inferential boundaries and negative results.

Significance: 3/4 — Bounded second-pass verification is practically relevant, but the demonstrated gains are narrow and expensive.

Originality: 3/4 — The selective arbitration contract is a useful synthesis and framing, though the main components build on established sampling, judging, and repair techniques.

Overall recommendation: 3/6 — Borderline; the empirical direction is promising, but the current evidence does not establish repeatable or mechanism-specific superiority.

Confidence: 4/5 — The paper provides enough self-contained detail for a substantive assessment, though the underlying runs cannot be independently verified here.

## Ethics and Limitations

The paper responsibly discusses compute use, reporting “45.97 million tokens across the two OJ3 cohorts,” and warns against deploying same-model agreement in high-stakes settings. Its treatment of the legal data is appropriately cautious: it acknowledges that facts may remain re-identifiable and withholds item texts pending governance review. The main scientific limitations are the lack of repeated identical-item runs, whole-file session dependence, prompt evolution in the coding aggregate, limited language and model coverage, and the failure to establish support metadata or overlap authorization as the causal mechanism.

## Comment

I view this as a careful and potentially useful empirical study, but currently borderline for ICML because its most compelling result is a single-session improvement over one direct baseline, while its distinctive mechanism fails to beat a compute-matched generic judge. The most important revision would be a fully frozen, independently repeated evaluation that separates session-level repeatability from item-level significance and isolates the causal contribution of the proposed bounded-update components.

### Panel review 3 — scope_ablation (accepted)

# Review: Mini Artichokes: Bounded Verification for Selective LLM Arbitration and Program Repair

## Summary

This paper proposes a bounded-update framework for LLM inference: preserve a frozen base answer or artifact, invoke a second decision stage only after an observable conflict or execution failure, restrict the update to existing candidates or localized repairs, and audit rescues and harms. On a 1,000-question MMLU-Pro replication, support-aware arbitration improves direct Luna by 2.3 points, but does not significantly outperform compute-matched generic judging. On three small Aider coding batches, structured repair improves over Plain Luna, although the evidence is descriptive and the overlap-specific mechanism is not supported.

## Strengths

- The paper makes an unusually clear distinction between an end-to-end gain and a causal mechanism claim: “Agreement is useful for routing on MMLU-Pro, and a feedback-bound second pass is useful on the Aider subsets; neither support annotation nor strict overlap authorization beats its compute-matched generic control.”

- The primary MMLU-Pro comparison is carefully defined and full-denominator. The authors report “28 rescues, 5 harms, +23 correct and +2.3 percentage points” on the frozen replication, together with an exact test and bootstrap interval.

- The arbitration controls are well designed. OJ3 and GJ3 use “the same eligible IDs, anonymous candidate strings, rotation, model, reasoning effort, call count, and fallback,” with support counts as the intended treatment. The paper also prevents synthesis of an untested third answer.

- The authors are commendably candid about negative and null findings. In particular, “support annotation did not beat a generic judge,” while the legal reserve produced “30 rescues but 59 harms.” This substantially improves the credibility of the presentation.

- The paper reports practical costs rather than presenting accuracy in isolation: OJ3 consumed “45,973,780 tokens versus 13,009,321 for D1,” a 3.53-fold ratio, and the coding system required a second call.

- The limitations are substantial and generally stated explicitly, including that coding outcomes share “one whole-batch model invocation” and that “three batch calls per arm are insufficient for cluster-robust generalization.”

## Weaknesses

- The coding transfer does not provide strong evidence for a general bounded-verification principle. The three batches share only three call clusters per arm, batch 2 changed “one language-specific packaging sentence,” and “the Java repair lead was strengthened before its sample was frozen.” Thus, the aggregate 29/60 versus 17/60 comparison is a family summary over changing prompt realizations, not a clean replicated treatment effect. The reported task-level `p=.00418` is explicitly conditional on realized whole-batch calls, while the cluster-level sign test is only `p=.125`.

- The central mechanism is not established. OJ3 improves over D1 in replication 2, but ties SC3 and exceeds GJ3 by only two answers with descriptive `p=.3633`. The paper itself states that “the support annotation's incremental causal effect is unresolved.” Consequently, the strongest evidence supports extra inference and generic arbitration, not support-aware arbitration specifically.

- The MMLU-Pro evidence is vulnerable to whole-file session effects. Each draw processes 1,000 questions in one session, and D2 scores only “145/1,000” in confirmation 1 before recovering to 607/1,000. Although the authors acknowledge this instability, they do not rerun the complete pipeline on identical items, so the paired uncertainty estimates do not measure repeatability across sessions.

- Generalization beyond one model and one benchmark remains largely untested. The limitations state that “confirmation covers one model, one runtime, and one primary benchmark.” MMLU-Pro provides category breadth, but it does not establish transfer to other models, inference runtimes, open-ended tasks, or independent per-question deployments.

- The coding comparison conflates several useful ingredients: Graph prompting, structured requirement reconstruction, counterexample generation, preservation instructions, and double completion audits. The Java ablation isolates strict overlap authorization, but it does not identify which of the remaining repair operations produces the gain. The paper therefore supports a bundled repair recipe more than a sharply characterized algorithm.

- The legal negative boundary is informative but difficult to interpret mechanistically. The paper correctly notes that “domain, task, prompt, and label structure changed together.” This makes the result useful as a warning against universal claims, but it cannot distinguish partial-evidence underdetermination from domain-specific prompting, label effects, or corpus artifacts.

- The practical value of the MMLU gain is uncertain. The confirmatory improvement is 2.3 percentage points at 3.53 times the token cost, and only 68 of 2,000 questions trigger arbitration. The paper reports these costs, but does not establish when the accuracy gain justifies the additional latency and expenditure relative to simpler alternatives.

## Questions for the Authors

1. Can you repeat the MMLU-Pro replication with multiple independently initialized complete-file sessions on the same frozen questions, or with independent per-question calls, to quantify the impact of the anomalous D2 session?

2. What exact prompt and implementation changes distinguish ordinary repair, structured repair, and the strengthened Java repair? Can the strengthened version be evaluated retrospectively on the earlier frozen batches without changing task selection?

3. Can you provide an ablation separating requirement reconstruction, counterexample generation, preservation, and the double completion audit, rather than treating structured repair as one bundled intervention?

4. Can the arbitration policy be evaluated with another model family or runtime while keeping the conflict and judging protocol fixed? This is important for determining whether the observed routing effect is model-specific.

5. Given the small triggered set, what sample size or repeated-session design would be needed to obtain a meaningful test of OJ3 versus GJ3 and the incremental value of support counts?

## Scores

Soundness: 3/4 — The frozen full-denominator MMLU comparison and matched controls are strong, but session dependence and coding confounds limit the broader conclusions.

Presentation: 4/4 — The paper is exceptionally clear about protocols, inferential boundaries, costs, and negative results.

Significance: 3/4 — The bounded-update framing and practical repair result are useful, but the accuracy gain is modest and expensive, with limited generalization.

Originality: 3/4 — The precise contract and rescue/harm accounting are well framed, although the underlying ingredients—sampling, judging, structured reasoning, and repair—are established.

Overall recommendation: 3/6 — Borderline: promising and unusually honest, but the main mechanism and cross-regime generalization are not yet convincingly demonstrated.

Confidence: 3/5 — The paper is self-contained enough to assess conceptually, but the decisive empirical results and execution artifacts cannot be independently verified here.

## Ethics and Limitations

The authors appropriately discuss the risks of re-identification in the Korean precedent data, noting that the pipeline “did not establish full de-identification of facts,” and they withhold item texts pending governance review. They also explicitly report the environmental and monetary-relevant burden of “45.97 million tokens across the two OJ3 cohorts.” The principal scientific limitations are the single-model MMLU setting, whole-file session dependence, small number of coding call clusters, evolving coding prompts, and lack of a causal isolation of the support or overlap mechanism.

## Comment

I recommend borderline. The most important next step is a genuinely matched, independently repeated coding study: freeze one repair prompt and one task allocation across substantially more batches, analyze at the batch/call-cluster level, and ablate the repair components. Such an experiment would determine whether the striking 29/60 coding result reflects a reproducible general advantage or a small number of correlated whole-batch executions.
