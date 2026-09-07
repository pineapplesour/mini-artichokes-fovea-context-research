# ICML-Style Paper Review

## Paper and Evidence Identity

- Review method: full review — deterministic evidence audit + review panel. The panel's review is the official output; this document is its audit sidecar.
- Review Agent name/version: paper-reviewer / `sha256:9886349f92661c3c73b70f216a7038b741b47282d7624538ad207dd3fbb2d4c0`
- Review-agent spec path/hash: `review-agent-spec.md` / `sha256:08b13516a2cb0e5151c6b4dc24f98e6d191b35ee30d69ea300b2d6ff2d5a5945`
- Original paper identity: `Mini_Artichokes_manuscript_v3.md` / `text/markdown` / `sha256:a41f95f33cab406cc04daa54afc0e7f130dacd245898ac377c99596e64d7af9a` / `54706` bytes
- Derived Markdown identity: `Mini_Artichokes_manuscript_v3.md` / `text/markdown` / `sha256:a41f95f33cab406cc04daa54afc0e7f130dacd245898ac377c99596e64d7af9a` / `54706` bytes
- Original PDF page count: `n/a`
- Converter: `none (Markdown source)`
- Paper version/hash: `Mini_Artichokes_manuscript_v3.md` / `sha256:a41f95f33cab406cc04daa54afc0e7f130dacd245898ac377c99596e64d7af9a`
- Evidence bundle reviewed: `evidence`: `EVIDENCE_SCOPE.md` (`sha256:a618bf8139997e26e432e82c0f74fea061a96989c6ded9526ed28fcfce2f541d`), `LEGAL_RESERVE_GOVERNANCE.md` (`sha256:33e0abeffb8cc6de841cb58b8f14ecb8926b9886f643d1e04ec77312f529e2d5`), `MMLU_PROTOCOL_CONFIRMATION1.md` (`sha256:f78ea8a6294728e3b1abd3c6c3c74cdf89f474da83da0f0ae7b7f56d637c60ef`), `MMLU_PROTOCOL_REPLICATION2.md` (`sha256:0fe6bd59e759d1c761770267fe9b7a8f2bef5e2f47ba6c768e57cfe35352c9a7`), `MMLU_PRO_CUMULATIVE_RESULTS.md` (`sha256:52cbe8e02c8fe34f72d88ed6c24aa26dcf6afb45c44b3ede70fed4274242a39c`), `SC3_BOUNDARY_AUDIT.md` (`sha256:fc38b4c284c643e4a4f9ba813f57bcac8c15e04069d72307b468e5410d1e7ad2`), `UNIVERSAL_DEVELOPMENT_RESULTS.md` (`sha256:e1a542a410331498e46472a0061c344cc806189898e0576b4a20d8188253f791`), `aider_hidden_java20_results.json` (`sha256:d1abe2a31712c0d446bba8728118246ce2a262bc44124600de95351df75ed9e6`), `aider_hidden_results.json` (`sha256:0c618e58ab5720e1044da799193325a5018c27e911179ed75048351af72461c1`), `aider_java20_session_replication_results.json` (`sha256:75eb1d868b5d5663b77d5730107b01e91f372fb4d58d180caef812e7c7b7be9b`), `experiments.jsonl` (`sha256:153c86902a4dff33581c081f09c880e4b0cee069b240f8f2973d4f3f5661271c`), `legal_boundary_score.json` (`sha256:14318b0953051f0ccb4a1ab3390914eb1abab000c45f48c618cd45a7fd8a4ba1`), `mmlu_pro_confirmation1_score.json` (`sha256:5ba78d945aff95e5c3b7d93b0a44d592bbe16b2587d4d2228d179f5e1339128f`), `mmlu_pro_cumulative_score.json` (`sha256:bdf7e36abcf05b8a05d921a259590b919f54da2b7a1658dcc4057acabc905fec`), `mmlu_pro_replication2_score.json` (`sha256:2442d9018a0241e203500f85e859d76c78cda52f74277090856f5b40d3ca7685`), `reasoning_method_screen.json` (`sha256:28122fee17330f5b0c317cf107f182a35604d1ee2c4805145305e950af0dba99`)
- Frozen at (UTC): `2026-09-02T04:40:22+00:00`

## Summary

The paper, "Mini Artichokes: Bounded Verification for Selective LLM Arbitration and Program Repair", presents a method and supporting experiments. It reports 136 quantitative result claim(s) and cites 29 prior work(s). Deterministic audit: 22 contradiction(s), 0 dishonest self-certification(s), 75 mechanical finding(s); 12 result claim(s) evidence-backed, 780 unverifiable. Overall recommendation: 2/6 [claim-001].

## Strengths

- The result claim is directly supported by the supplied evidence [claim-441].
- The result claim is directly supported by the supplied evidence [claim-442].
- The result claim is directly supported by the supplied evidence [claim-443].
- The result claim is directly supported by the supplied evidence [claim-444].
- The result claim is directly supported by the supplied evidence [claim-445].
- The result claim is directly supported by the supplied evidence [claim-446].
- The result claim is directly supported by the supplied evidence [claim-470].
- The result claim is directly supported by the supplied evidence [claim-516].
- The result claim is directly supported by the supplied evidence [claim-517].
- The result claim is directly supported by the supplied evidence [claim-518].
- The result claim is directly supported by the supplied evidence [claim-519].
- The result claim is directly supported by the supplied evidence [claim-531].

## Weaknesses

- The template-compliance check observed required section 'Research Spec' is absent; expected a 'Research Spec' section [finding-001].
- The template-compliance check observed required section 'Self-Review' is absent; expected a 'Self-Review' section [finding-002].
- The template-compliance check observed required section 'Short Paper' is absent; expected a 'Short Paper' section [finding-003].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-004].
- The baseline-fairness check observed claim does not name a baseline: Repeated inference can improve large-language-model (LLM) outputs, but; expected the improvement claim to identify the compared baseline [finding-005].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-006].
- The baseline-fairness check observed claim does not name a baseline: set, matched structured repair beat direct Luna and Graph alone in all five; expected the improvement claim to identify the compared baseline [finding-007].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-008].
- The baseline-fairness check observed claim does not name a baseline: methods show that diversity and selection can outperform a single trajectory.; expected the improvement claim to identify the compared baseline [finding-009].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-010].
- The baseline-fairness check observed claim does not name a baseline: - **RQ1:** Does the frozen support-aware policy improve full-denominator; expected the improvement claim to identify the compared baseline [finding-011].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-012].
- The baseline-fairness check observed claim does not name a baseline: - **RQ2:** Does it outperform strong multi-call controls: three-draw majority; expected the improvement claim to identify the compared baseline [finding-013].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-014].
- The baseline-fairness check observed claim does not name a baseline: - **RQ4:** Does a frozen bounded structured-repair system repeatedly improve; expected the improvement claim to identify the compared baseline [finding-015].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-016].
- The baseline-fairness check observed claim does not name a baseline: solutions can also improve mathematical reasoning [8].; expected the improvement claim to identify the compared baseline [finding-017].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-018].
- The baseline-fairness check observed claim does not name a baseline: authorization beats its compute-matched generic control.; expected the improvement claim to identify the compared baseline [finding-019].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-020].
- The baseline-fairness check observed claim does not name a baseline: the judge improve an answer by synthesizing new content.; expected the improvement claim to identify the compared baseline [finding-021].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-022].
- The baseline-fairness check observed claim does not name a baseline: The strict V3 development arm improved 566 to 587; expected the improvement claim to identify the compared baseline [finding-023].
- The ledger-trace check observed paper reports ci_lower_pp=-0.4; expected one of the traceable ci_lower_pp values [-0.15, -0.05, 0.45, 0.65, 0.75, 1.2] [finding-024].
- The ledger-trace check observed paper reports net_correct=0; expected one of the traceable net_correct values [-29.0, 3.0, 5.0, 21.0, 22.0, 23.0, 24.0, 27.0] [finding-025].
- The ledger-trace check observed paper reports one_sided_exact_mcnemar_p=.6875; expected one of the traceable one_sided_exact_mcnemar_p values [7.14963061909657e-06, 1.9279075786471367e-05, 3.309384919703007e-05, 0.0005325, 0.0010440536669982237, 0.08984375, 0.25390625] [finding-026].
- The ledger-trace check observed paper reports rescues=2; expected one of the traceable rescues values [6.0, 7.0, 28.0, 29.0, 30.0, 33.0, 35.0] [finding-027].
- The ledger-trace check observed paper reports rescues=2; expected one of the traceable rescues values [6.0, 7.0, 28.0, 29.0, 30.0, 33.0, 35.0] [finding-028].
- The ledger-trace check observed paper reports ci_lower_pp=-0.3; expected one of the traceable ci_lower_pp values [-0.15, -0.05, 0.45, 0.65, 0.75, 1.2] [finding-029].
- The ledger-trace check observed paper reports ci_upper_pp=+0.8; expected one of the traceable ci_upper_pp values [0.45, 0.55, 1.8, 1.95, 3.5] [finding-030].
- The ledger-trace check observed paper reports net_correct=+2; expected one of the traceable net_correct values [-29.0, 3.0, 5.0, 21.0, 22.0, 23.0, 24.0, 27.0] [finding-031].
- The ledger-trace check observed paper reports one_sided_exact_mcnemar_p=.36328; expected one of the traceable one_sided_exact_mcnemar_p values [7.14963061909657e-06, 1.9279075786471367e-05, 3.309384919703007e-05, 0.0005325, 0.0010440536669982237, 0.08984375, 0.25390625] [finding-032].
- The ledger-trace check observed paper reports rescues=5; expected one of the traceable rescues values [6.0, 7.0, 28.0, 29.0, 30.0, 33.0, 35.0] [finding-033].
- The ledger-trace check observed paper reports harms=7; expected one of the traceable harms values [2.0, 3.0, 5.0, 6.0, 9.0, 13.0, 59.0] [finding-034].
- The ledger-trace check observed paper reports one_sided_exact_mcnemar_p=9.55e-5; expected one of the traceable one_sided_exact_mcnemar_p values [7.14963061909657e-06, 1.9279075786471367e-05, 3.309384919703007e-05, 0.0005325, 0.0010440536669982237, 0.08984375, 0.25390625] [finding-035].
- The ledger-trace check observed paper reports ci_lower_pp=+1.1; expected one of the traceable ci_lower_pp values [-0.15, -0.05, 0.45, 0.65, 0.75, 1.2] [finding-036].
- The ledger-trace check observed paper reports ci_upper_pp=+3.1; expected one of the traceable ci_upper_pp values [0.45, 0.55, 1.8, 1.95, 3.5] [finding-037].
- The ledger-trace check observed paper reports one_sided_exact_mcnemar_p=2.46e-5; expected one of the traceable one_sided_exact_mcnemar_p values [7.14963061909657e-06, 1.9279075786471367e-05, 3.309384919703007e-05, 0.0005325, 0.0010440536669982237, 0.08984375, 0.25390625] [finding-038].
- The ledger-trace check observed paper reports rescues=24; expected one of the traceable rescues values [6.0, 7.0, 28.0, 29.0, 30.0, 33.0, 35.0] [finding-039].
- The ledger-trace check observed paper reports correct=13; expected one of the traceable correct values [613.0] [finding-040].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-041].
- The baseline-fairness check observed claim does not name a baseline: MMLU-Pro evidence: a stricter overlap policy improved 566/941 to 587/941 (+21;; expected the improvement claim to identify the compared baseline [finding-042].
- The ledger-trace check observed paper reports harms=.0005325; expected one of the traceable harms values [2.0, 3.0, 5.0, 6.0, 9.0, 13.0, 59.0] [finding-043].
- The ledger-trace check observed paper reports loss=29; expected a rounding-compatible loss value in experiments.jsonl [finding-044].
- The ledger-trace check observed paper reports loss=65; expected a rounding-compatible loss value in experiments.jsonl [finding-045].
- The ledger-trace check observed paper reports correct=32; expected one of the traceable correct values [613.0] [finding-046].
- The ledger-trace check observed paper reports correct=49.2; expected one of the traceable correct values [613.0] [finding-047].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-048].
- The baseline-fairness check observed claim does not name a baseline: same frozen official Java20 set, matched structured repair outperformed both; expected the improvement claim to identify the compared baseline [finding-049].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-050].
- The baseline-fairness check observed claim does not name a baseline: Structured repair improved Plain in all three disjoint; expected the improvement claim to identify the compared baseline [finding-051].
- The ledger-trace check observed paper reports rescues=2; expected one of the traceable rescues values [6.0, 7.0, 28.0, 29.0, 30.0, 33.0, 35.0] [finding-052].
- The ledger-trace check observed paper reports rescues=3; expected one of the traceable rescues values [6.0, 7.0, 28.0, 29.0, 30.0, 33.0, 35.0] [finding-053].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-054].
- The baseline-fairness check observed claim does not name a baseline: MMLU-Pro cohort, the unchanged OJ3 policy improved direct Luna by 2.; expected the improvement claim to identify the compared baseline [finding-055].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-056].
- The baseline-fairness check observed claim does not name a baseline: SC3 and GJ3 both significantly improved; expected the improvement claim to identify the compared baseline [finding-057].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-058].
- The baseline-fairness check observed claim does not name a baseline: Matched repair beat Plain and Graph in all five new sessions, with; expected the improvement claim to identify the compared baseline [finding-059].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-060].
- The baseline-fairness check observed claim does not name a baseline: The confirmatory replication improved by 2.; expected the improvement claim to identify the compared baseline [finding-061].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-062].
- The baseline-fairness check observed claim does not name a baseline: OJ3 beats direct inference but not; expected the improvement claim to identify the compared baseline [finding-063].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-064].
- The baseline-fairness check observed claim does not name a baseline: the compute-matched generic judge; structured repair repeatedly beats Plain; expected the improvement claim to identify the compared baseline [finding-065].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-066].
- The baseline-fairness check observed claim does not name a baseline: support-aware policy significantly improved a preassigned direct Luna draw.; expected the improvement claim to identify the compared baseline [finding-067].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-068].
- The baseline-fairness check observed claim does not name a baseline: a frozen official Java20 set, matched structured repair beat direct Luna and; expected the improvement claim to identify the compared baseline [finding-069].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-070].
- The baseline-fairness check observed claim does not name a baseline: Improve by Self-critiquing Their Own Plans?; expected the improvement claim to identify the compared baseline [finding-071].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-072].
- The baseline-fairness check observed claim does not name a baseline: Self-Consistency Improves Chain of; expected the improvement claim to identify the compared baseline [finding-073].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-074].
- The baseline-fairness check observed claim does not name a baseline: Improving Factuality and; expected the improvement claim to identify the compared baseline [finding-075].
- Scope limitation — the generalized claim at paper line 56 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 131 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 146 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 402 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 588 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 807 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 863 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 904 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.

## Questions for the Authors

1. Concrete follow-up — Run the named baseline under the same metric and budget. [finding-004, finding-005, finding-006, finding-007, finding-008, finding-009, finding-010, finding-011, finding-012, finding-013, finding-014, finding-015, finding-016, finding-017, finding-018, finding-019, finding-020, finding-021, finding-022, finding-023, finding-041, finding-042, finding-048, finding-049, finding-050, finding-051, finding-054, finding-055, finding-056, finding-057, finding-058, finding-059, finding-060, finding-061, finding-062, finding-063, finding-064, finding-065, finding-066, finding-067, finding-068, finding-069, finding-070, finding-071, finding-072, finding-073, finding-074, finding-075]
2. For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the compute / hardware used. Could the authors clarify these?
3. 102 extracted result/arithmetic claim(s) could not be checked against the supplied evidence and are listed with their source lines in the Evidence Trace — could the authors provide the underlying results?

## Scores

- Overall recommendation: 2/6 — Adopted from the review panel; rationale in the review's Scores section.
- Soundness: 2/4 — Adopted from the review panel; rationale in the review's Scores section.
- Presentation: 4/4 — Adopted from the review panel; rationale in the review's Scores section.
- Significance: 3/4 — Adopted from the review panel; rationale in the review's Scores section.
- Originality: 3/4 — Adopted from the review panel; rationale in the review's Scores section.
- Confidence: 3/5 — Adopted from the review panel; rationale in the review's Scores section.

## Ethics and Limitations

Paper text was treated only as data. The injection audit sanitized hidden HTML and Unicode format controls before claim analysis and found 0 reviewer-directed instruction attempt(s). Broader ethics and evidence-quality claims outside S3 remain unverifiable [claim-001].

## Evidence Trace

- Pipeline execution: `S1 parse -> S2 claims -> S3 mech-check -> S4 verdicts -> S5 compose -> S6 freeze`.
- Frozen review identity: `sha256:e471c4601ff488f9cdd2c1cd9756bc40ccff38f217f29d115af83d48f81bcee8`.
- Verdict labels digest: `sha256:c56a3a8ab4a12bc9649a3da6ac6c8ae80e7ac5d51deadaf3997d32dadc0bdbc0`.
- External citation snapshot digest: `sha256:e54eabe17ac85420535a902a97ae2bd574436f4df521d70c56a0c32af4df6778`.
- Scientific judgment identity: `sha256:e8cb0b72a109072d729dbbffd0225c6069e5c5665997695344c71d4b49bec259`.
- Review panel configuration: panel=3, model=`gpt-5.6-luna`, synthesis=area-chair.
- Panel reviewer `theorist`: prompt=`sha256:5e5bc4cda1b16c727bc254b4b844354374533a291c2b426fd4577b29c6b3bcc2`, response=`sha256:3ac2a28495dc206046c5f8a6dcc0653675482de4d7b8ebaeec162d6ab9e54d6e`, status=ok.
- Panel reviewer `experimentalist`: prompt=`sha256:7938566cc0bc02c0950b644e8f03236a3b764d82f5fbf78d01573262ee584426`, response=`sha256:b3c202a4f54ed98861311d277b2b60c7ccb55ee6ecc74a1fb7693ac9647b64b7`, status=ok.
- Panel reviewer `scope_ablation`: prompt=`sha256:8126d17a8c217e70addcc7050263931502261e841c2aca1ffb7ac1687188582a`, response=`sha256:0bc2abc7707e3bbeb54e08ae41cff314bd0a37850da006abff8a9f921da986a1`, status=ok.
- Output path: `mac_v6_luna_committee.md`.
- Frozen paper input: `Mini_Artichokes_manuscript_v3.md` (`sha256:a41f95f33cab406cc04daa54afc0e7f130dacd245898ac377c99596e64d7af9a`).
- Frozen original identity: `Mini_Artichokes_manuscript_v3.md` (`text/markdown`, `sha256:a41f95f33cab406cc04daa54afc0e7f130dacd245898ac377c99596e64d7af9a`, 54706 bytes, page count=n/a).
- Frozen derived identity: `Mini_Artichokes_manuscript_v3.md` (`text/markdown`, `sha256:a41f95f33cab406cc04daa54afc0e7f130dacd245898ac377c99596e64d7af9a`, 54706 bytes).
- Frozen converter: `none (Markdown source)`.
- Pre-S1 sanitation: 0 trace(s), 0 injection finding(s).
- S1 parse inventory: 40 sections, 8 tables, 622 numeric tokens with source locations.
- S3 ledger-trace: 46/70 metric-labelled values matched; 24 finding(s).
- S3 internal-consistency: 0 comparison(s), 0 finding(s).
- S3 arithmetic: 0 recomputation(s), 0 finding(s).
- S3 baseline-fairness: 24 explicit improvement claim(s), 48 finding(s).
- S3 negative-evidence: 0 discard/crash outcome(s), 0 omission finding(s).
- S3 citation-existence: 5 explicit identifier(s), 0 existence/title finding(s).
- S3 template-compliance: 3 contract trace(s), 3 finding(s).
- S3 injection-scan: 0 sanitation trace(s), 0 reviewer-directed instruction finding(s).
- S3 self-review-audit: 0 checklist item(s), 0 dishonest self-certification(s).
- S3 positioning: 29 cited reference(s), related-work section=True, 0 novelty/superiority claim(s), 0 overclaim finding(s), 0 positioning question(s).
- S5 DRAFT/GROUND: 189 candidate comment(s), 189 retained, 0 deleted, 102 criticism comment(s) converted to questions.
- S2/S4 claim verdicts:
- [claim-001] **contradicted** — paper:5 — Repeated inference can improve large-language-model (LLM) outputs, but — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-004`, `finding-005`.
- [claim-055] **contradicted** — paper:59 — methods show that diversity and selection can outperform a single trajectory. — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-008`, `finding-009`.
- [claim-087] **contradicted** — paper:88 — **RQ1:** Does the frozen support-aware policy improve full-denominator — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-010`, `finding-011`.
- [claim-089] **contradicted** — paper:91 — **RQ2:** Does it outperform strong multi-call controls: three-draw majority — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-012`, `finding-013`.
- [claim-093] **contradicted** — paper:95 — **RQ4:** Does a frozen bounded structured-repair system repeatedly improve — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-014`, `finding-015`.
- [claim-148] **contradicted** — paper:158 — solutions can also improve mathematical reasoning [8]. — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-016`, `finding-017`.
- [claim-232] **contradicted** — paper:254 — the judge improve an answer by synthesizing new content. — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-020`, `finding-021`.
- [claim-366] **contradicted** — paper:404 — The strict V3 development arm improved 566 to 587 — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-022`, `finding-023`.
- [claim-441] **supported** — paper:486 — D1 direct Luna | 597 | 590 | 1,187 | 59.35% — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:1#confirmation_1_correct (number-0190)`, `experiments.jsonl:1#replication_2_correct (number-0191)`, `experiments.jsonl:1#pooled_correct (number-0192)`, `experiments.jsonl:1#pooled_accuracy (number-0193)`.
- [claim-442] **supported** — paper:487 — D2 | 145 | 607 | 752 | 37.60% — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:2#confirmation_1_correct (number-0194)`, `experiments.jsonl:2#replication_2_correct (number-0195)`, `experiments.jsonl:2#pooled_correct (number-0196)`, `experiments.jsonl:2#pooled_accuracy (number-0197)`.
- [claim-443] **supported** — paper:488 — D3 | 587 | 586 | 1,173 | 58.65% — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:3#confirmation_1_correct (number-0198)`, `experiments.jsonl:3#replication_2_correct (number-0199)`, `experiments.jsonl:3#pooled_correct (number-0200)`, `experiments.jsonl:3#pooled_accuracy (number-0201)`.
- [claim-444] **supported** — paper:489 — SC3 majority | 596 | 613 | 1,209 | 60.45% — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:4#confirmation_1_correct (number-0202)`, `experiments.jsonl:4#replication_2_correct (number-0203)`, `experiments.jsonl:6#replication_2_correct (number-0203)`, `experiments.jsonl:4#pooled_correct (number-0204)`, `experiments.jsonl:4#pooled_accuracy (number-0205)`.
- [claim-445] **supported** — paper:490 — GJ3 generic judge | 600 | 611 | 1,211 | 60.55% — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:5#confirmation_1_correct (number-0206)`, `experiments.jsonl:5#replication_2_correct (number-0207)`, `experiments.jsonl:5#pooled_correct (number-0208)`, `experiments.jsonl:5#pooled_accuracy (number-0209)`.
- [claim-446] **supported** — paper:491 — **OJ3 support-aware judge** | **601** | **613** | **1,214** | **60.70%** — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:6#confirmation_1_correct (number-0210)`, `experiments.jsonl:4#replication_2_correct (number-0211)`, `experiments.jsonl:6#replication_2_correct (number-0211)`, `experiments.jsonl:6#pooled_correct (number-0212)`, `experiments.jsonl:6#pooled_accuracy (number-0213)`.
- [claim-470] **supported** — paper:518 — **OJ3 vs D1** | **28** | **5** | **+23** | **3.31e-5** | **+1.2** | **+3.5** — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:7#rescues (number-0246)`, `experiments.jsonl:7#harms (number-0247)`, `experiments.jsonl:11#harms (number-0247)`, `experiments.jsonl:7#net_correct (number-0248)`, `experiments.jsonl:7#one_sided_exact_mcnemar_p (number-0249)`, `experiments.jsonl:7#ci_lower_pp (number-0250)`, `experiments.jsonl:7#ci_upper_pp (number-0251)`.
- [claim-471] **contradicted** — paper:519 — OJ3 vs SC3 | 2 | 2 | 0 | .6875 | -0.4 | +0.4 — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-024`, `finding-025`, `finding-026`, `finding-027`, `finding-028`.
- [claim-472] **contradicted** — paper:520 — OJ3 vs GJ3 | 5 | 3 | +2 | .36328 | -0.3 | +0.8 — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-029`, `finding-030`, `finding-031`, `finding-032`, `finding-033`.
- [claim-473] **contradicted** — paper:521 — SC3 vs D1 | 30 | 7 | +23 | 9.55e-5 | +1.2 | +3.5 — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-034`, `finding-035`.
- [claim-474] **contradicted** — paper:522 — GJ3 vs D1 | 24 | 3 | +21 | 2.46e-5 | +1.1 | +3.1 — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-036`, `finding-037`, `finding-038`, `finding-039`.
- [claim-516] **supported** — paper:576 — D1 | 1 | 13,009,321 | 1.00x — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:1#total_tokens (number-0338)`.
- [claim-517] **supported** — paper:577 — SC3 | 3 | 45,056,433 | 3.46x — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:4#total_tokens (number-0341)`.
- [claim-518] **supported** — paper:578 — GJ3 | 4 | 45,787,649 | 3.52x — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:5#semantic_calls (number-0343)`, `experiments.jsonl:6#semantic_calls (number-0343)`, `experiments.jsonl:5#total_tokens (number-0344)`.
- [claim-519] **supported** — paper:579 — OJ3 | 4 | 45,973,780 | 3.53x — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:5#semantic_calls (number-0346)`, `experiments.jsonl:6#semantic_calls (number-0346)`, `experiments.jsonl:6#total_tokens (number-0347)`.
- [claim-525] **contradicted** — paper:589 — MMLU-Pro evidence: a stricter overlap policy improved 566/941 to 587/941 (+21; — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-041`, `finding-042`.
- [claim-531] **supported** — paper:595 — Relative to P1, OJ3 produced 30 rescues — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:13#rescues (number-0374)`, `experiments.jsonl:17#rescues (number-0374)`.
- [claim-532] **contradicted** — paper:596 — but 59 harms, a net loss of 29. — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-044`.
- [claim-533] **contradicted** — paper:596 — On 65 cases carrying the mechanical support — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-045`.
- [claim-534] **contradicted** — paper:597 — signal, the supported outcome was correct only 32 times (49.2%). — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-046`, `finding-047`.
- [claim-541] **contradicted** — paper:606 — same frozen official Java20 set, matched structured repair outperformed both — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-048`, `finding-049`.
- [claim-565] **contradicted** — paper:632 — Structured repair improved Plain in all three disjoint — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-050`, `finding-051`.
- (+784 further extracted claim(s) — mostly unverifiable prose — omitted here for brevity; all are labelled in S2/S4 with source lines.)

## Comment

Recommendation: 2/6. A proven integrity problem (a contradiction or dishonest self-certification) is the decisive factor and must be resolved before this paper can be accepted. Most useful next step for the authors — The template-compliance check observed required section 'Research Spec' is absent; expected a 'Research Spec' section [finding-001].

## Panel Reviews (provenance)

### Panel review 1 — theorist (accepted)

# Review: Mini Artichokes: Bounded Verification for Selective LLM Arbitration and Program Repair

## Summary

This paper proposes a conservative inference-time framework that freezes an initial answer or program patch, uses an observable conflict or execution failure to trigger a second stage, restricts the permitted update, and preserves unaffected work. The strongest reported result is that support-aware arbitration improves a direct Luna draw from 590/1,000 to 613/1,000, while matched structured repair improves Plain by 13 percentage points across five repeated sessions on the same 20 Java tasks. However, the evidence does not establish that support metadata causes the arbitration gain, nor that the bundled repair procedure generalizes beyond the fixed coding set.

## Strengths

- The arbitration policy is unusually explicit and conservative. The paper defines the trigger as “`D2=D3≠D1`,” restricts the judge to “one of the two existing answers,” and specifies that invalid or non-conflict cases “return D1.” This makes the intervention auditable and prevents unconstrained self-revision.

- The MMLU-Pro evaluation uses a clear full-denominator comparison. The replication reports “OJ3 scored 613/1,000 versus D1's 590/1,000,” with “28 rescues, 5 harms,” and an exact one-sided `p=3.31e-5`. The disjoint category-proportional sampling and explicit separation of confirmation from replication are also methodologically responsible.

- The paper provides strong negative and null controls rather than presenting overlap as a universal solution. In particular, “OJ3 tied SC3 at 613/1,000” and its comparison with GJ3 was “descriptive (`p=.3633`).” The legal reserve likewise produced a net loss of 29 answers, which appropriately constrains the paper’s claims.

- The authors are commendably candid about dependence and scope. They state that “the inferential result is five positive whole-session differences on one fixed official task set” and that the coding evidence “is not a full 225-task Aider leaderboard evaluation.” This substantially improves the credibility of the presentation.

## Weaknesses

- The primary MMLU-Pro significance claim does not adequately support pipeline-level repeatability. Each 1,000-question draw was produced in “one complete-file agent session,” yet the reported McNemar tests and bootstrap intervals resample questions. The paper itself concedes that these tests “quantify item-level uncertainty conditional on the realized sessions” and “do not estimate between-session variance.” The anomalous D2 result—“145/1,000” in one cohort versus “607/1,000” in the next—demonstrates that session-level effects can be substantial. Thus, the result supports an improvement on this realized batch, but the language of a statistically established system improvement is stronger than the experimental unit warrants.

- The central support-aware mechanism is not demonstrated. The paper reports that OJ3 “was not significantly better than a compute-matched generic judge,” with only 5 versus 3 discordant wins in the replication comparison. Since OJ3 and GJ3 share the same trigger, candidates, model, and call budget, this is the key causal comparison, and it is underpowered. The evidence supports conflict-based routing plus generic judging, not the claimed importance of support-aware arbitration.

- The common “bounded verification” principle is more conceptual synthesis than experimentally isolated mechanism. In coding, matched repair bundles “failure feedback, counterexamples, preservation, and double audit,” while in arbitration the judge selects between fixed candidates. The Java ablation shows that strict overlap authorization loses to matched repair—“5/20 versus 7/20”—but does not identify which of the bundled repair operations produces the gain. The paper’s end-to-end results are useful, but they do not establish a shared causal structure across the two regimes.

- The coding comparison confounds the proposed repair design with an additional call and privileged execution feedback. Plain uses “1” call, whereas matched repair uses “2 total” and receives “official failure stdout.” The matched strict-overlap arm controls one authorization rule, but there is no new-Java comparison against a compute-matched generic feedback repair with the same information. Consequently, the result establishes that this particular two-pass feedback pipeline beats the one-call baselines on the tested set, not that its bounded-update structure is responsible.

- Generality remains limited despite the careful disclosures. The strongest coding result reuses “the same 20 Java tasks” across five sessions, and the cross-language result has “only three whole-batch call clusters.” The MMLU experiment also uses one model, one runtime, and whole-file calls. These are meaningful probes, but they are insufficient for the broader framing of a generally useful answer-engine architecture.

## Questions for the Authors

1. Can you repeat the MMLU replication on the same questions with multiple independently initialized whole-file sessions, or otherwise analyze session-level variance, so that the uncertainty reflects the actual unit at which the solver operates?

2. What is the intended inferential status of replication 2, given that it was authorized after confirmation 1 showed a favorable direction? Would a prespecified two-stage or sequential-testing analysis change the reported significance?

3. Can you provide a Java comparison between matched structured repair and a generic second-pass repair receiving exactly the same failure output and token/call budget? This would distinguish the value of the bounded structure from the value of simply performing a feedback-based second pass.

4. Which individual coding components—requirement reconstruction, counterexamples, preservation, or double audit—are necessary for the observed gain?

5. Given that OJ3 does not significantly beat GJ3, what specific claim should readers retain about support counts beyond their role in defining a small conflict set?

## Scores

Soundness: 2/4 — The protocols and arithmetic are unusually transparent, but the main MMLU inference uses item-level statistics despite whole-file session dependence, and mechanism attribution remains unresolved.

Presentation: 3/4 — The paper is well organized and candid about limitations, though the cross-regime abstraction and multiple inferential boundaries make the central contribution somewhat diffuse.

Significance: 3/4 — The work offers a useful empirical design pattern and valuable negative results, but its strongest evidence is narrow and expensive.

Originality: 2/4 — The individual components resemble selective ensembles, generic judging, structured reasoning, and test-feedback repair; the bounded-update framing is reasonable but only modestly novel.

Overall recommendation: 3/6 — Borderline; the paper contains a credible empirical observation but does not yet establish a broadly general or mechanistically validated method.

Confidence: 4/5 — The paper is sufficiently self-contained to assess its protocol, claims, and statistical limitations, although the underlying artifacts and executions cannot be independently rerun here.

## Ethics and Limitations

The paper appropriately identifies the principal ethical concerns: incomplete de-identification of legal facts, unrecoverable reuse metadata for five records, and the substantial compute cost of “45.97 million tokens across the two OJ3 cohorts.” It also correctly warns against deploying same-model agreement in high-stakes settings without external evidence. The stated limitations regarding whole-file context effects, shared model errors, fixed coding tasks, missing local compilation, and approximate compute matching are material rather than cosmetic and should constrain the claims.

## Comment

I recommend borderline consideration. The paper’s most valuable contribution is the disciplined separation of end-to-end improvement from mechanism attribution, together with honest null and negative results. To become convincing for acceptance, it should address the statistical unit problem in the whole-file MMLU experiments and add a feedback-matched generic repair control; otherwise, the evidence supports a narrow collection of useful two-pass policies rather than a validated general principle of bounded verification.

### Panel review 2 — experimentalist (accepted)

# Review: Mini Artichokes: Bounded Verification for Selective LLM Arbitration and Program Repair

## Summary

This paper proposes a bounded-update framework for inference-time correction: preserve a frozen base state, invoke a second decision stage only after an observable conflict or failure, restrict the update to existing candidates or localized repairs, and audit the result. On a 1,000-question MMLU-Pro replication, OJ3 improves over direct Luna by 2.3 points, but does not significantly beat compute-matched controls. On five repeated sessions over the same 20 Java tasks, structured repair improves Plain and Graph. The empirical results are carefully qualified, but the central mechanism remains unresolved and the generality of the gains is limited.

## Strengths

- The paper defines a clear, operational safety contract. The method explicitly says: “freeze a prior state, route only an observable conflict or failure to a separate decision stage, restrict the allowed update, and preserve unaffected work.” This makes the proposed behavior substantially more testable than unconstrained self-correction.

- The MMLU-Pro experiment uses full-denominator evaluation and reports rescues and harms rather than only aggregate accuracy. On replication 2, OJ3 achieves “28 rescues, 5 harms, +23 correct,” with a one-sided exact `p=3.31e-5` and bootstrap interval “[+1.2,+3.5] points.”

- The paper includes strong controls that appropriately weaken its own mechanistic claim. In particular, “OJ3 tied SC3 at 613/1,000” and its comparison to GJ3 was only “descriptive (`p=.3633`).” This supports a gain from additional arbitration or compute, but does not falsely establish that support counts are causal.

- The coding study distinguishes end-to-end performance from component attribution. The paper reports that “strict two-of-three authorization solved 5/20 versus 7/20 for matched repair,” while matched repair won all five new Java sessions. This is useful evidence against attributing the coding gain specifically to overlap authorization.

- The authors are unusually transparent about execution dependence and scope. They state that the five-session result “establishes session repeatability on a fixed official set rather than new-task generality,” and explicitly note that the 60-task coding aggregate has “only three whole-batch call clusters.”

- The presentation is well structured and the claim hierarchy is helpful. The table separating “Supported interpretation” from “Not established” makes the inferential boundaries easy to follow.

## Weaknesses

- The central support-aware mechanism is not demonstrated. OJ3 improves over D1, but it does not significantly outperform either strong alternative: it “tied SC3 at 613/1,000” and exceeded GJ3 by only two answers with `p=.3633`. Thus the evidence supports a multi-call arbitration system, not the claimed incremental value of support-aware arbitration.

- The principal MMLU result is highly sensitive to unstable whole-file sessions. The paper reports that D2 scored only “145/1,000” in confirmation 1 and later “recovered to 607/1,000 in replication 2.” Although the integrity audit rules out several mechanical explanations, the “semantic cause remains unresolved.” Because the trigger and candidate answers depend on these sessions, the reported improvement may partly reflect idiosyncratic session behavior rather than a robust policy effect.

- The item-level statistical tests do not establish repeatability of the complete MMLU pipeline. The authors acknowledge that the tests “quantify item-level uncertainty conditional on the realized sessions, not between-session variance.” There is no rerun on the same questions, so the very small McNemar p-value should not be interpreted as evidence that the complete system reliably produces the same advantage under independent initialization.

- The coding evidence has only five independent session-level observations and one repeated task set. The minimum reported one-sided sign-test value, `p=.03125`, is therefore fragile and does not establish task-general improvement. The same 20 tasks recur, and the authors correctly concede that the result estimates “same-task session repeatability rather than performance on new tasks.”

- The coding improvement cannot be attributed to bounded verification as opposed to the bundled repair procedure. Matched repair combines “failure feedback, counterexamples, preservation, and double audit,” and the paper states that “neither the component responsible for the gain nor an overlap-specific effect is established.” Without ablations isolating failure feedback, counterexample generation, preservation, and auditing, the claimed common principle remains interpretive rather than experimentally identified.

- The accuracy gains come with substantial resource costs. OJ3 consumes “45,973,780 tokens versus 13,009,321 for D1,” a 3.53-fold ratio, while improving replication accuracy by only 2.3 percentage points. The paper reports this honestly, but the practical significance is weak without a quality-per-cost analysis or a lower-cost trigger that can be compared fairly.

- Generality is substantially narrower than the framing suggests. The primary positive evidence uses one model and one MMLU-Pro subset; the coding replication uses one fixed Java20 set; and the paper itself says the coding study is “not a full 225-task Aider leaderboard evaluation.” The negative legal result further shows that the policy can degrade under partial evidence, limiting any broad claim about universal reliability.

## Questions for the Authors

1. Can you run an independent same-task replication of the MMLU-Pro protocol, or otherwise quantify between-session variance, given that “the anomalous D2 result” demonstrates substantial whole-file instability?

2. What is the accuracy and cost of a baseline that receives the same four-call budget but uses a predeclared non-overlap trigger or an unconditional generic judge? This would clarify whether the observed gain comes from the proposed trigger rather than simply additional inference.

3. For coding, which components of the structured repair bundle are necessary: official failure feedback, counterexample derivation, preservation instructions, or the double completion audit?

4. Can you evaluate the coding method on new task sets, rather than only the same 20 Java tasks, while retaining session-level independence as the inferential unit?

5. How should practitioners decide whether the 3.53-fold MMLU token cost is worthwhile? A cost-normalized or accuracy-versus-budget curve would materially affect the practical assessment.

6. What evidence supports the proposed “bounded second-pass verification” principle beyond these two task regimes, given that the legal reserve produced a net loss of 29 answers?

## Scores

Soundness: 3/4 — The experiments are carefully designed and candidly analyzed, but session instability, limited independent units, and unresolved component attribution constrain the conclusions.

Presentation: 4/4 — The paper is unusually clear about protocols, controls, limitations, and the distinction between confirmatory and descriptive evidence.

Significance: 3/4 — The bounded-update framing is useful, but the measured improvements are narrow and expensive, with limited demonstrated generality.

Originality: 3/4 — The common bounded-update contract is a plausible synthesis, although its individual ingredients and closest baselines are established.

Overall recommendation: 3/6 — Borderline; the paper offers credible but narrowly scoped empirical evidence and does not yet establish a distinct support-aware mechanism or broad advantage.

Confidence: 3/5 — The claims are sufficiently self-contained to assess, but the key numerical findings cannot be independently verified here and depend on unusual whole-file execution units.

## Ethics and Limitations

The paper appropriately reports the substantial inference cost and warns against deploying same-model agreement in high-stakes settings. Its legal data may remain re-identifiable: it acknowledges that “full de-identification” was not established and withholds item texts pending governance review. The stated limitations are substantive rather than cosmetic, especially the single-model setting, whole-file session dependence, fixed coding tasks, lack of component attribution, and restricted coding coverage. These limitations materially reduce the strength and generality of the conclusions but are presented with commendable candor.

## Comment

I recommend borderline consideration. The strongest contribution is the disciplined separation of end-to-end improvement from mechanism attribution, supported by full-denominator accuracy, strong controls, and explicit failure reporting. The most important issue is scientific rather than presentational: the paper must establish whether bounded verification itself contributes beyond extra compute and a bundled repair prompt, ideally through independent same-task and new-task replications with component-level ablations.

### Panel review 3 — scope_ablation (accepted)

# Review: Mini Artichokes: Bounded Verification for Selective LLM Arbitration and Program Repair

## Summary

This paper proposes a generic bounded-update framework for LLM inference: preserve a frozen prior state, invoke a second decision or repair stage only after observable disagreement or failure, constrain the permitted update, and audit rescues and harms. It evaluates selective arbitration on two 1,000-question MMLU-Pro cohorts and structured repair on a fixed Java20 hidden-test set. The evidence supports improvements over direct baselines in these settings, but does not establish superiority to compute-matched generic judging, identify the causal component of the repair pipeline, or demonstrate broad task generalization.

## Strengths

- The paper clearly separates end-to-end improvement from mechanism attribution: “support annotation did not beat a generic judge,” and “strict overlap authorization lost to matched Java repair.”

- The MMLU-Pro evaluation uses a pre-frozen, full-denominator protocol. The primary replication reports “28 rescues, 5 harms, +23 correct,” with `p=3.31e-5` and a paired-bootstrap interval of `[+1.2,+3.5]` percentage points.

- The authors use appropriate paired accounting rather than reporting only aggregate accuracy. For example, Table 2 reports both rescues and harms for OJ3 versus each comparator.

- The paper is unusually candid about negative and unstable findings, including that “D2 was an extreme low outlier in confirmation 1 (145/1,000)” and that the legal reserve produced “30 rescues but 59 harms.”

- The coding experiment correctly treats the whole-batch session as the inferential unit. The five Java sessions all favor matched repair, with explicitly reported differences and exact sign-test results.

- Scope limitations are carefully stated. The authors acknowledge that the Java study “establishes session repeatability on a fixed official set rather than new-task generality” and that the 60-task coding aggregate has “only three whole-batch call clusters.”

## Weaknesses

- The main arbitration result is not evidence that support-aware arbitration is the useful mechanism. OJ3 is statistically better than D1, but it ties SC3 and is not significantly better than GJ3: “Its +2 point estimate over GJ3 was descriptive (`p=.3633`).” Thus, the paper’s central support-aware contribution is unresolved, while the demonstrated benefit may primarily come from spending roughly 3.5 times the inference tokens on additional sampling and judging.

- The MMLU-Pro confirmatory result is conditional on a single realized whole-file session per draw and does not establish pipeline-level repeatability. The paper itself notes that “the reported paired p-values and bootstrap intervals therefore condition on the realized sessions and do not estimate between-session repeatability.” The anomalous D2 result of 145/1,000 makes this limitation especially consequential.

- The coding evidence is narrow and strongly bundled. Matched repair combines “failure feedback, counterexamples, preservation, and double audit,” and the paper concedes that “neither the component responsible for the gain nor an overlap-specific effect is established.” Without ablations of these components, the claimed bounded-verification principle is more an organizing description than a tested causal explanation.

- The Java replication reuses exactly the same 20 tasks across five sessions. Although session-level inference is more appropriate than treating 100 task outcomes as independent, this design does not show generalization to unseen tasks. The five-session sign tests establish consistency on this selected task set, not broad coding performance.

- The cross-language transfer evidence is difficult to interpret as replication because “batch 2 corrected a packaging sentence, and the Java repair lead was strengthened before freezing.” The resulting 29/60 versus 17/60 aggregate is appropriately labeled descriptive, but it provides limited evidence for a fixed, reproducible method.

- The comparison to direct Luna is not consistently compute matched. OJ3 uses “45,973,780 tokens versus 13,009,321 for D1,” while the coding path requires “about 2.14 times Plain's agent time.” The accuracy gains may be practically valuable, but the paper does not establish when they justify these costs or whether a simpler additional-call policy would achieve the same results.

- The framework’s generality is asserted across two regimes whose authorization signals are fundamentally different: same-model answer agreement versus official execution failure. The paper acknowledges that coding “is therefore a transfer of the bounded-update contract, not the same algorithm under a different label,” but the experiments do not isolate which properties of the contract transfer across domains.

## Questions for the Authors

1. Can you provide additional repeated whole-file MMLU-Pro runs on a fresh, predeclared item set—or otherwise estimate between-session variance—to determine whether the +2.3-point result is robust to the substantial session instability observed in D2?

2. What is the performance of a simpler compute-matched baseline consisting of additional direct draws plus a generic judge, without support metadata or the special conflict trigger?

3. Within matched repair, how much of the Java improvement comes from failure stdout, requirement reconstruction, counterexample generation, preservation instructions, and the double completion audit?

4. How were the MMLU-Pro category-proportional samples and Java20 tasks selected relative to prior development and prompt tuning, and what safeguards prevent subtle selection effects from favoring the reported subsets?

5. What accuracy, latency, and cost trade-off would result from triggering arbitration using a cheaper uncertainty signal before generating all three auxiliary draws?

## Scores

Soundness: 3/4 — The protocols and statistical accounting are careful, but the principal mechanism and between-session robustness remain unresolved.

Presentation: 4/4 — The paper is clear, well organized, and consistently distinguishes confirmatory, descriptive, and unsupported claims.

Significance: 3/4 — The bounded-update framing and practical results are potentially useful, but the demonstrated gains are narrow and costly.

Originality: 3/4 — The contract is a useful synthesis and empirical framing, although its components draw substantially on existing sampling, judging, graph, and repair methods.

Overall recommendation: 3/6 — Borderline; the empirical results are credible within their stated scope but insufficient for the broader methodological claims.

Confidence: 3/5 — The paper is self-contained enough to assess, but the key numerical results and artifacts cannot be independently verified here.

## Ethics and Limitations

The paper appropriately discusses compute costs and the risks of using same-model agreement in high-stakes settings. Its legal reserve raises legitimate privacy concerns: the authors state that the facts “did not establish full de-identification” and therefore withhold item texts and outputs. The major scientific limitations are the single-model setting, whole-file session dependence, reuse of the same Java tasks, approximate compute matching, bundled repair components, and limited evidence for cross-domain or new-task generalization.

## Comment

I recommend borderline acceptance/rejection depending on the venue threshold. The paper’s strongest contribution is a disciplined empirical demonstration that conservative second-pass processing can improve specific realized baselines, not a validation of support-aware overlap or a general verification principle. The most important revision would be to add repeated, fixed-protocol runs and component-level ablations that distinguish the value of bounded state preservation from the value of simply allocating substantially more inference compute.
