# ICML-Style Paper Review

## Paper and Evidence Identity

- Review method: full review — deterministic evidence audit + review panel. The panel's review is the official output; this document is its audit sidecar.
- Review Agent name/version: paper-reviewer / `sha256:9886349f92661c3c73b70f216a7038b741b47282d7624538ad207dd3fbb2d4c0`
- Review-agent spec path/hash: `review-agent-spec.md` / `sha256:08b13516a2cb0e5151c6b4dc24f98e6d191b35ee30d69ea300b2d6ff2d5a5945`
- Original paper identity: `Mini_Artichokes_manuscript_v3.md` / `text/markdown` / `sha256:c45c5942bb72d9291418afc391a65c383340b97b2f0fc3c386292e1b046d8d04` / `61857` bytes
- Derived Markdown identity: `Mini_Artichokes_manuscript_v3.md` / `text/markdown` / `sha256:c45c5942bb72d9291418afc391a65c383340b97b2f0fc3c386292e1b046d8d04` / `61857` bytes
- Original PDF page count: `n/a`
- Converter: `none (Markdown source)`
- Paper version/hash: `Mini_Artichokes_manuscript_v3.md` / `sha256:c45c5942bb72d9291418afc391a65c383340b97b2f0fc3c386292e1b046d8d04`
- Evidence bundle reviewed: `evidence`: `EVIDENCE_SCOPE.md` (`sha256:a618bf8139997e26e432e82c0f74fea061a96989c6ded9526ed28fcfce2f541d`), `LEGAL_RESERVE_GOVERNANCE.md` (`sha256:33e0abeffb8cc6de841cb58b8f14ecb8926b9886f643d1e04ec77312f529e2d5`), `MMLU_PROTOCOL_CONFIRMATION1.md` (`sha256:f78ea8a6294728e3b1abd3c6c3c74cdf89f474da83da0f0ae7b7f56d637c60ef`), `MMLU_PROTOCOL_REPLICATION2.md` (`sha256:0fe6bd59e759d1c761770267fe9b7a8f2bef5e2f47ba6c768e57cfe35352c9a7`), `MMLU_PRO_CUMULATIVE_RESULTS.md` (`sha256:52cbe8e02c8fe34f72d88ed6c24aa26dcf6afb45c44b3ede70fed4274242a39c`), `SC3_BOUNDARY_AUDIT.md` (`sha256:fc38b4c284c643e4a4f9ba813f57bcac8c15e04069d72307b468e5410d1e7ad2`), `UNIVERSAL_DEVELOPMENT_RESULTS.md` (`sha256:e1a542a410331498e46472a0061c344cc806189898e0576b4a20d8188253f791`), `aider_hidden_java20_results.json` (`sha256:d1abe2a31712c0d446bba8728118246ce2a262bc44124600de95351df75ed9e6`), `aider_hidden_results.json` (`sha256:0c618e58ab5720e1044da799193325a5018c27e911179ed75048351af72461c1`), `aider_java20_ordinary_control_results.json` (`sha256:2f9240417643e193e932d8979052ab137e5450808dbd42e0b6040913d0e03676`), `aider_java20_session_replication_results.json` (`sha256:75eb1d868b5d5663b77d5730107b01e91f372fb4d58d180caef812e7c7b7be9b`), `experiments.jsonl` (`sha256:153c86902a4dff33581c081f09c880e4b0cee069b240f8f2973d4f3f5661271c`), `legal_boundary_score.json` (`sha256:14318b0953051f0ccb4a1ab3390914eb1abab000c45f48c618cd45a7fd8a4ba1`), `mmlu_pro_confirmation1_score.json` (`sha256:5ba78d945aff95e5c3b7d93b0a44d592bbe16b2587d4d2228d179f5e1339128f`), `mmlu_pro_cumulative_score.json` (`sha256:bdf7e36abcf05b8a05d921a259590b919f54da2b7a1658dcc4057acabc905fec`), `mmlu_pro_replication2_score.json` (`sha256:2442d9018a0241e203500f85e859d76c78cda52f74277090856f5b40d3ca7685`), `reasoning_method_screen.json` (`sha256:28122fee17330f5b0c317cf107f182a35604d1ee2c4805145305e950af0dba99`)
- Frozen at (UTC): `2026-09-02T05:50:39+00:00`

## Summary

The paper, "Mini Artichokes: Bounded Verification for Selective LLM Arbitration and Program Repair", presents a method and supporting experiments. It reports 161 quantitative result claim(s) and cites 29 prior work(s). Deterministic audit: 22 contradiction(s), 0 dishonest self-certification(s), 77 mechanical finding(s); 12 result claim(s) evidence-backed, 887 unverifiable. Overall recommendation: 2/6 [claim-001].

## Strengths

- The result claim is directly supported by the supplied evidence [claim-507].
- The result claim is directly supported by the supplied evidence [claim-508].
- The result claim is directly supported by the supplied evidence [claim-509].
- The result claim is directly supported by the supplied evidence [claim-510].
- The result claim is directly supported by the supplied evidence [claim-511].
- The result claim is directly supported by the supplied evidence [claim-512].
- The result claim is directly supported by the supplied evidence [claim-536].
- The result claim is directly supported by the supplied evidence [claim-582].
- The result claim is directly supported by the supplied evidence [claim-583].
- The result claim is directly supported by the supplied evidence [claim-584].
- The result claim is directly supported by the supplied evidence [claim-585].
- The result claim is directly supported by the supplied evidence [claim-597].

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
- The baseline-fairness check observed claim does not name a baseline: imprecise even though both beat D1.; expected the improvement claim to identify the compared baseline [finding-023].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-024].
- The baseline-fairness check observed claim does not name a baseline: The strict V3 development arm improved 566 to 587; expected the improvement claim to identify the compared baseline [finding-025].
- The ledger-trace check observed paper reports ci_lower_pp=-0.4; expected one of the traceable ci_lower_pp values [-0.15, -0.05, 0.45, 0.65, 0.75, 1.2] [finding-026].
- The ledger-trace check observed paper reports net_correct=0; expected one of the traceable net_correct values [-29.0, 3.0, 5.0, 21.0, 22.0, 23.0, 24.0, 27.0] [finding-027].
- The ledger-trace check observed paper reports one_sided_exact_mcnemar_p=.6875; expected one of the traceable one_sided_exact_mcnemar_p values [7.14963061909657e-06, 1.9279075786471367e-05, 3.309384919703007e-05, 0.0005325, 0.0010440536669982237, 0.08984375, 0.25390625] [finding-028].
- The ledger-trace check observed paper reports rescues=2; expected one of the traceable rescues values [6.0, 7.0, 28.0, 29.0, 30.0, 33.0, 35.0] [finding-029].
- The ledger-trace check observed paper reports rescues=2; expected one of the traceable rescues values [6.0, 7.0, 28.0, 29.0, 30.0, 33.0, 35.0] [finding-030].
- The ledger-trace check observed paper reports ci_lower_pp=-0.3; expected one of the traceable ci_lower_pp values [-0.15, -0.05, 0.45, 0.65, 0.75, 1.2] [finding-031].
- The ledger-trace check observed paper reports ci_upper_pp=+0.8; expected one of the traceable ci_upper_pp values [0.45, 0.55, 1.8, 1.95, 3.5] [finding-032].
- The ledger-trace check observed paper reports net_correct=+2; expected one of the traceable net_correct values [-29.0, 3.0, 5.0, 21.0, 22.0, 23.0, 24.0, 27.0] [finding-033].
- The ledger-trace check observed paper reports one_sided_exact_mcnemar_p=.36328; expected one of the traceable one_sided_exact_mcnemar_p values [7.14963061909657e-06, 1.9279075786471367e-05, 3.309384919703007e-05, 0.0005325, 0.0010440536669982237, 0.08984375, 0.25390625] [finding-034].
- The ledger-trace check observed paper reports rescues=5; expected one of the traceable rescues values [6.0, 7.0, 28.0, 29.0, 30.0, 33.0, 35.0] [finding-035].
- The ledger-trace check observed paper reports harms=7; expected one of the traceable harms values [2.0, 3.0, 5.0, 6.0, 9.0, 13.0, 59.0] [finding-036].
- The ledger-trace check observed paper reports one_sided_exact_mcnemar_p=9.55e-5; expected one of the traceable one_sided_exact_mcnemar_p values [7.14963061909657e-06, 1.9279075786471367e-05, 3.309384919703007e-05, 0.0005325, 0.0010440536669982237, 0.08984375, 0.25390625] [finding-037].
- The ledger-trace check observed paper reports ci_lower_pp=+1.1; expected one of the traceable ci_lower_pp values [-0.15, -0.05, 0.45, 0.65, 0.75, 1.2] [finding-038].
- The ledger-trace check observed paper reports ci_upper_pp=+3.1; expected one of the traceable ci_upper_pp values [0.45, 0.55, 1.8, 1.95, 3.5] [finding-039].
- The ledger-trace check observed paper reports one_sided_exact_mcnemar_p=2.46e-5; expected one of the traceable one_sided_exact_mcnemar_p values [7.14963061909657e-06, 1.9279075786471367e-05, 3.309384919703007e-05, 0.0005325, 0.0010440536669982237, 0.08984375, 0.25390625] [finding-040].
- The ledger-trace check observed paper reports rescues=24; expected one of the traceable rescues values [6.0, 7.0, 28.0, 29.0, 30.0, 33.0, 35.0] [finding-041].
- The ledger-trace check observed paper reports correct=13; expected one of the traceable correct values [613.0] [finding-042].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-043].
- The baseline-fairness check observed claim does not name a baseline: MMLU-Pro evidence: a stricter overlap policy improved 566/941 to 587/941 (+21;; expected the improvement claim to identify the compared baseline [finding-044].
- The ledger-trace check observed paper reports harms=.0005325; expected one of the traceable harms values [2.0, 3.0, 5.0, 6.0, 9.0, 13.0, 59.0] [finding-045].
- The ledger-trace check observed paper reports loss=29; expected a rounding-compatible loss value in experiments.jsonl [finding-046].
- The ledger-trace check observed paper reports loss=65; expected a rounding-compatible loss value in experiments.jsonl [finding-047].
- The ledger-trace check observed paper reports correct=32; expected one of the traceable correct values [613.0] [finding-048].
- The ledger-trace check observed paper reports correct=49.2; expected one of the traceable correct values [613.0] [finding-049].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-050].
- The baseline-fairness check observed claim does not name a baseline: same frozen official Java20 set, matched structured repair outperformed both; expected the improvement claim to identify the compared baseline [finding-051].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-052].
- The baseline-fairness check observed claim does not name a baseline: Structured repair improved Plain in all three disjoint; expected the improvement claim to identify the compared baseline [finding-053].
- The ledger-trace check observed paper reports rescues=2; expected one of the traceable rescues values [6.0, 7.0, 28.0, 29.0, 30.0, 33.0, 35.0] [finding-054].
- The ledger-trace check observed paper reports rescues=3; expected one of the traceable rescues values [6.0, 7.0, 28.0, 29.0, 30.0, 33.0, 35.0] [finding-055].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-056].
- The baseline-fairness check observed claim does not name a baseline: MMLU-Pro cohort, the unchanged OJ3 policy improved direct Luna by 2.; expected the improvement claim to identify the compared baseline [finding-057].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-058].
- The baseline-fairness check observed claim does not name a baseline: SC3 and GJ3 both significantly improved; expected the improvement claim to identify the compared baseline [finding-059].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-060].
- The baseline-fairness check observed claim does not name a baseline: Matched repair beat Plain and Graph in all five new sessions, with; expected the improvement claim to identify the compared baseline [finding-061].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-062].
- The baseline-fairness check observed claim does not name a baseline: The confirmatory replication improved by 2.; expected the improvement claim to identify the compared baseline [finding-063].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-064].
- The baseline-fairness check observed claim does not name a baseline: OJ3 beats direct inference but not; expected the improvement claim to identify the compared baseline [finding-065].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-066].
- The baseline-fairness check observed claim does not name a baseline: beats Plain and Graph on the fixed Java20 set, while a later generic repair; expected the improvement claim to identify the compared baseline [finding-067].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-068].
- The baseline-fairness check observed claim does not name a baseline: support-aware policy significantly improved a preassigned direct Luna draw.; expected the improvement claim to identify the compared baseline [finding-069].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-070].
- The baseline-fairness check observed claim does not name a baseline: a frozen official Java20 set, matched structured repair beat direct Luna and; expected the improvement claim to identify the compared baseline [finding-071].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-072].
- The baseline-fairness check observed claim does not name a baseline: Improve by Self-critiquing Their Own Plans?; expected the improvement claim to identify the compared baseline [finding-073].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-074].
- The baseline-fairness check observed claim does not name a baseline: Self-Consistency Improves Chain of; expected the improvement claim to identify the compared baseline [finding-075].
- The baseline-fairness check observed ambiguous common metrics ['accuracy', 'confirmation_1_correct', 'n', 'pooled_accuracy', 'pooled_correct', 'replication_2_correct', 'semantic_calls', 'token_ratio_to_d1', 'total_tokens']; expected exactly one common metric for the baseline and candidate comparison [finding-076].
- The baseline-fairness check observed claim does not name a baseline: Improving Factuality and; expected the improvement claim to identify the compared baseline [finding-077].
- Scope limitation — the generalized claim at paper line 62 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 139 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 154 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 457 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 651 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 905 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 965 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 1011 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.

## Questions for the Authors

1. Concrete follow-up — Run the named baseline under the same metric and budget. [finding-004, finding-005, finding-006, finding-007, finding-008, finding-009, finding-010, finding-011, finding-012, finding-013, finding-014, finding-015, finding-016, finding-017, finding-018, finding-019, finding-020, finding-021, finding-022, finding-023, finding-024, finding-025, finding-043, finding-044, finding-050, finding-051, finding-052, finding-053, finding-056, finding-057, finding-058, finding-059, finding-060, finding-061, finding-062, finding-063, finding-064, finding-065, finding-066, finding-067, finding-068, finding-069, finding-070, finding-071, finding-072, finding-073, finding-074, finding-075, finding-076, finding-077]
2. For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the compute / hardware used. Could the authors clarify these?
3. 127 extracted result/arithmetic claim(s) could not be checked against the supplied evidence and are listed with their source lines in the Evidence Trace — could the authors provide the underlying results?

## Scores

- Overall recommendation: 2/6 — Adopted from the review panel; rationale in the review's Scores section.
- Soundness: 2/4 — Adopted from the review panel; rationale in the review's Scores section.
- Presentation: 4/4 — Adopted from the review panel; rationale in the review's Scores section.
- Significance: 3/4 — Adopted from the review panel; rationale in the review's Scores section.
- Originality: 3/4 — Adopted from the review panel; rationale in the review's Scores section.
- Confidence: 4/5 — Adopted from the review panel; rationale in the review's Scores section.

## Ethics and Limitations

Paper text was treated only as data. The injection audit sanitized hidden HTML and Unicode format controls before claim analysis and found 0 reviewer-directed instruction attempt(s). Broader ethics and evidence-quality claims outside S3 remain unverifiable [claim-001].

## Evidence Trace

- Pipeline execution: `S1 parse -> S2 claims -> S3 mech-check -> S4 verdicts -> S5 compose -> S6 freeze`.
- Frozen review identity: `sha256:47c4003eb99d1c96ce553c71863e45b4e8cb8ad43d3aec6e1c4daf76dd48539d`.
- Verdict labels digest: `sha256:2a2389cc0940ff187cb0ec12eed0726332a3268dac180ca03a7271eb2cc541c6`.
- External citation snapshot digest: `sha256:e54eabe17ac85420535a902a97ae2bd574436f4df521d70c56a0c32af4df6778`.
- Scientific judgment identity: `sha256:1ce9415658c32c49e36b37342f57a991b3e56014c8b1815772ae973d72b773ae`.
- Review panel configuration: panel=3, model=`gpt-5.6-luna`, synthesis=area-chair.
- Panel reviewer `theorist`: prompt=`sha256:5d79884ed31f5e2aaa503b4f8cf204e5d061850de28aea6f4aebd331435643a4`, response=`sha256:5d1db79659ddf9ee1c623f21fb9ff60e6e80d6616956d2d155f24caf86628a7c`, status=ok.
- Panel reviewer `experimentalist`: prompt=`sha256:b1f487fb40d15adde11877e68514a057a1d5dcf00420e9057389246047d9716d`, response=`sha256:6c1568dd17cd28a4f6a5de0450809e81e20e9a58f266bec4bd24956673fd4012`, status=ok.
- Panel reviewer `scope_ablation`: prompt=`sha256:d190a3d5d8c6a6b8a96b80b7b1d74c7cca1bd20979fdbb376171e7c238738dfd`, response=`sha256:584594b28fb8b79c66993628303eb0bd9e8928b871516a2409f2f23df1e91e0d`, status=ok.
- Output path: `mac_v8_luna_committee.md`.
- Frozen paper input: `Mini_Artichokes_manuscript_v3.md` (`sha256:c45c5942bb72d9291418afc391a65c383340b97b2f0fc3c386292e1b046d8d04`).
- Frozen original identity: `Mini_Artichokes_manuscript_v3.md` (`text/markdown`, `sha256:c45c5942bb72d9291418afc391a65c383340b97b2f0fc3c386292e1b046d8d04`, 61857 bytes, page count=n/a).
- Frozen derived identity: `Mini_Artichokes_manuscript_v3.md` (`text/markdown`, `sha256:c45c5942bb72d9291418afc391a65c383340b97b2f0fc3c386292e1b046d8d04`, 61857 bytes).
- Frozen converter: `none (Markdown source)`.
- Pre-S1 sanitation: 0 trace(s), 0 injection finding(s).
- S1 parse inventory: 41 sections, 9 tables, 717 numeric tokens with source locations.
- S3 ledger-trace: 46/70 metric-labelled values matched; 24 finding(s).
- S3 internal-consistency: 0 comparison(s), 0 finding(s).
- S3 arithmetic: 0 recomputation(s), 0 finding(s).
- S3 baseline-fairness: 25 explicit improvement claim(s), 50 finding(s).
- S3 negative-evidence: 0 discard/crash outcome(s), 0 omission finding(s).
- S3 citation-existence: 5 explicit identifier(s), 0 existence/title finding(s).
- S3 template-compliance: 3 contract trace(s), 3 finding(s).
- S3 injection-scan: 0 sanitation trace(s), 0 reviewer-directed instruction finding(s).
- S3 self-review-audit: 0 checklist item(s), 0 dishonest self-certification(s).
- S3 positioning: 29 cited reference(s), related-work section=True, 0 novelty/superiority claim(s), 0 overclaim finding(s), 0 positioning question(s).
- S5 DRAFT/GROUND: 216 candidate comment(s), 216 retained, 0 deleted, 127 criticism comment(s) converted to questions.
- S2/S4 claim verdicts:
- [claim-001] **contradicted** — paper:5 — Repeated inference can improve large-language-model (LLM) outputs, but — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-004`, `finding-005`.
- [claim-063] **contradicted** — paper:65 — methods show that diversity and selection can outperform a single trajectory. — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-008`, `finding-009`.
- [claim-095] **contradicted** — paper:94 — **RQ1:** Does the frozen support-aware policy improve full-denominator — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-010`, `finding-011`.
- [claim-097] **contradicted** — paper:97 — **RQ2:** Does it outperform strong multi-call controls: three-draw majority — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-012`, `finding-013`.
- [claim-101] **contradicted** — paper:101 — **RQ4:** Does a frozen bounded structured-repair system repeatedly improve — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-014`, `finding-015`.
- [claim-157] **contradicted** — paper:166 — solutions can also improve mathematical reasoning [8]. — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-016`, `finding-017`.
- [claim-241] **contradicted** — paper:262 — the judge improve an answer by synthesizing new content. — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-020`, `finding-021`.
- [claim-423] **contradicted** — paper:459 — The strict V3 development arm improved 566 to 587 — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-024`, `finding-025`.
- [claim-507] **supported** — paper:549 — D1 direct Luna | 597 | 590 | 1,187 | 59.35% — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:1#confirmation_1_correct (number-0216)`, `experiments.jsonl:1#replication_2_correct (number-0217)`, `experiments.jsonl:1#pooled_correct (number-0218)`, `experiments.jsonl:1#pooled_accuracy (number-0219)`.
- [claim-508] **supported** — paper:550 — D2 | 145 | 607 | 752 | 37.60% — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:2#confirmation_1_correct (number-0220)`, `experiments.jsonl:2#replication_2_correct (number-0221)`, `experiments.jsonl:2#pooled_correct (number-0222)`, `experiments.jsonl:2#pooled_accuracy (number-0223)`.
- [claim-509] **supported** — paper:551 — D3 | 587 | 586 | 1,173 | 58.65% — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:3#confirmation_1_correct (number-0224)`, `experiments.jsonl:3#replication_2_correct (number-0225)`, `experiments.jsonl:3#pooled_correct (number-0226)`, `experiments.jsonl:3#pooled_accuracy (number-0227)`.
- [claim-510] **supported** — paper:552 — SC3 majority | 596 | 613 | 1,209 | 60.45% — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:4#confirmation_1_correct (number-0228)`, `experiments.jsonl:4#replication_2_correct (number-0229)`, `experiments.jsonl:6#replication_2_correct (number-0229)`, `experiments.jsonl:4#pooled_correct (number-0230)`, `experiments.jsonl:4#pooled_accuracy (number-0231)`.
- [claim-511] **supported** — paper:553 — GJ3 generic judge | 600 | 611 | 1,211 | 60.55% — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:5#confirmation_1_correct (number-0232)`, `experiments.jsonl:5#replication_2_correct (number-0233)`, `experiments.jsonl:5#pooled_correct (number-0234)`, `experiments.jsonl:5#pooled_accuracy (number-0235)`.
- [claim-512] **supported** — paper:554 — **OJ3 support-aware judge** | **601** | **613** | **1,214** | **60.70%** — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:6#confirmation_1_correct (number-0236)`, `experiments.jsonl:4#replication_2_correct (number-0237)`, `experiments.jsonl:6#replication_2_correct (number-0237)`, `experiments.jsonl:6#pooled_correct (number-0238)`, `experiments.jsonl:6#pooled_accuracy (number-0239)`.
- [claim-536] **supported** — paper:581 — **OJ3 vs D1** | **28** | **5** | **+23** | **3.31e-5** | **+1.2** | **+3.5** — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:7#rescues (number-0272)`, `experiments.jsonl:7#harms (number-0273)`, `experiments.jsonl:11#harms (number-0273)`, `experiments.jsonl:7#net_correct (number-0274)`, `experiments.jsonl:7#one_sided_exact_mcnemar_p (number-0275)`, `experiments.jsonl:7#ci_lower_pp (number-0276)`, `experiments.jsonl:7#ci_upper_pp (number-0277)`.
- [claim-537] **contradicted** — paper:582 — OJ3 vs SC3 | 2 | 2 | 0 | .6875 | -0.4 | +0.4 — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-026`, `finding-027`, `finding-028`, `finding-029`, `finding-030`.
- [claim-538] **contradicted** — paper:583 — OJ3 vs GJ3 | 5 | 3 | +2 | .36328 | -0.3 | +0.8 — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-031`, `finding-032`, `finding-033`, `finding-034`, `finding-035`.
- [claim-539] **contradicted** — paper:584 — SC3 vs D1 | 30 | 7 | +23 | 9.55e-5 | +1.2 | +3.5 — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-036`, `finding-037`.
- [claim-540] **contradicted** — paper:585 — GJ3 vs D1 | 24 | 3 | +21 | 2.46e-5 | +1.1 | +3.1 — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-038`, `finding-039`, `finding-040`, `finding-041`.
- [claim-582] **supported** — paper:639 — D1 | 1 | 13,009,321 | 1.00x — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:1#total_tokens (number-0364)`.
- [claim-583] **supported** — paper:640 — SC3 | 3 | 45,056,433 | 3.46x — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:4#total_tokens (number-0367)`.
- [claim-584] **supported** — paper:641 — GJ3 | 4 | 45,787,649 | 3.52x — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:5#semantic_calls (number-0369)`, `experiments.jsonl:6#semantic_calls (number-0369)`, `experiments.jsonl:5#total_tokens (number-0370)`.
- [claim-585] **supported** — paper:642 — OJ3 | 4 | 45,973,780 | 3.53x — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:5#semantic_calls (number-0372)`, `experiments.jsonl:6#semantic_calls (number-0372)`, `experiments.jsonl:6#total_tokens (number-0373)`.
- [claim-591] **contradicted** — paper:652 — MMLU-Pro evidence: a stricter overlap policy improved 566/941 to 587/941 (+21; — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-043`, `finding-044`.
- [claim-597] **supported** — paper:658 — Relative to P1, OJ3 produced 30 rescues — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:13#rescues (number-0400)`, `experiments.jsonl:17#rescues (number-0400)`.
- [claim-598] **contradicted** — paper:659 — but 59 harms, a net loss of 29. — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-046`.
- [claim-599] **contradicted** — paper:659 — On 65 cases carrying the mechanical support — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-047`.
- [claim-600] **contradicted** — paper:660 — signal, the supported outcome was correct only 32 times (49.2%). — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-048`, `finding-049`.
- [claim-607] **contradicted** — paper:669 — same frozen official Java20 set, matched structured repair outperformed both — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-050`, `finding-051`.
- [claim-654] **contradicted** — paper:721 — Structured repair improved Plain in all three disjoint — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-052`, `finding-053`.
- (+891 further extracted claim(s) — mostly unverifiable prose — omitted here for brevity; all are labelled in S2/S4 with source lines.)

## Comment

Recommendation: 2/6. A proven integrity problem (a contradiction or dishonest self-certification) is the decisive factor and must be resolved before this paper can be accepted. Most useful next step for the authors — The template-compliance check observed required section 'Research Spec' is absent; expected a 'Research Spec' section [finding-001].

## Panel Reviews (provenance)

### Panel review 1 — theorist (accepted)

# Review: Mini Artichokes: Bounded Verification for Selective LLM Arbitration and Program Repair

## Summary

This paper proposes a conservative inference-time framework that freezes an initial answer or program patch, uses an observable conflict or execution failure to trigger a second stage, restricts the permitted update, and preserves unaffected work. It reports a statistically significant improvement over a direct Luna baseline on a 1,000-question MMLU-Pro replication and repeatable gains for repair on one fixed 20-task Java set. However, its strongest mechanism claims are not established: support-aware arbitration does not beat a generic judge, and structured repair does not beat an ordinary failure-feedback repair control.

## Strengths

- The paper gives a clear, operationally specified policy rather than an informal prompting recipe: “D1 is the base, and D2/D3 are auxiliary draws,” with review triggered only when “D2=D3≠D1.”

- The full-denominator accounting is appropriate and transparent. On replication 2, OJ3 achieved “28 rescues, 5 harms, +23 correct,” rather than reporting only performance on the triggered subset.

- The paper uses strong controls and explicitly limits its claims. It reports that OJ3 “tied SC3 at 613/1,000” and had only a descriptive “+2 point estimate over GJ3,” correctly avoiding a causal claim for support counts.

- The expected-gain formulation is useful as an organizing framework: “Δ = τ (q01 s01 - q10 s10).” It correctly emphasizes that bounded updating is beneficial only when authorized rescues exceed authorized harms and does not rely on model-level independence.

- The experimental reporting is unusually candid. The authors disclose that “D2 was an extreme low outlier in confirmation 1 (145/1,000)” and that the legal reserve produced a net loss of 29 cases.

- The coding evaluation respects whole-session dependence more carefully than a naïve task-level analysis. The paper states that “the same 20 tasks recur” and treats “the independently initialized 20-task whole-batch session as its inferential unit.”

- The artifact and provenance description is detailed, including commits, frozen protocols, scorer hashes, and accepted outputs. This materially improves reproducibility and auditability.

## Weaknesses

- The principal MMLU-Pro replication is not fully prospective in the usual confirmatory sense. The second cohort was selected only “after that cohort was completely scored,” and the paper says the replication was “authorized after the first cohort was scored.” Although the authors avoid pooling it adaptively, the decision to run exactly one favorable-looking follow-up was itself outcome-informed, weakening the stated confirmatory interpretation.

- The central support-aware mechanism is not demonstrated. The paper reports that OJ3 “was not significantly better than a compute-matched generic judge,” with only 5 versus 3 discordant decisions relative to GJ3. Thus the evidence supports a multi-call judge or selective arbitration effect, but not the claimed value of the support annotation.

- The theory is primarily an accounting identity rather than a substantive guarantee. The equation “Δ = τ (q01 s01 - q10 s10)” decomposes the observed change, but the paper provides no conditions under which the trigger or support information should improve the relevant probabilities. The important question—when agreement is predictive rather than a shared error—is left empirical and unresolved.

- The coding evidence is narrow and partially post hoc. The five-session result uses “the same frozen official Java20 set,” so it establishes repeatability across sessions on those tasks, not generalization to new tasks. Moreover, the ordinary-repair control was “commissioned after the matched outcomes were known,” making the negative mechanism result informative but not a clean prospective test.

- The coding contribution is difficult to distinguish from simply adding a second pass with failure output. The authors report that ordinary repair “matched or exceeded the structured arm in four sessions,” and explicitly concede that there is “no accuracy evidence for the explicit structured bundle.” This substantially narrows the algorithmic contribution relative to the title and framing.

- The two domains instantiate substantially different procedures. Multiple-choice arbitration selects between two fixed answers, whereas program repair edits files using private execution feedback. The paper appropriately calls this “a transfer of the bounded-update contract,” but the shared principle—freeze, inspect, update, preserve—is broad and does not by itself establish a unified method.

- The MMLU-Pro evidence is sensitive to whole-file execution behavior. The anomalous D2 result of “145/1,000” indicates substantial session-level instability, while no identical-item reruns were performed. The reported item-level intervals therefore do not quantify variance from rerunning the complete pipeline, which is particularly important for a method based on multiple complete-file sessions.

- The practical cost is high relative to the headline gain. OJ3 uses “45,973,780 tokens versus 13,009,321 for D1,” a 3.53-fold token ratio, for a 2.3 percentage-point improvement. The paper reports this honestly, but the deployment case is weak unless the authors show settings where the additional cost is economically justified.

## Questions for the Authors

1. Before observing confirmation 1, was the exact replication-2 sampling rule, cohort count, and primary comparison fully registered or otherwise frozen? If not, how should the replication’s p-value be interpreted under the outcome-informed decision to run it?

2. Can the authors provide a prospective, compute-matched comparison of OJ3 versus GJ3 on disjoint tasks with enough eligible conflicts to distinguish a support-count effect from ordinary judging?

3. For the Java study, what evidence supports generalization beyond the repeated 20-task set, and can the same ordinary-versus-structured repair comparison be run prospectively on new tasks?

4. How sensitive are the results to whole-file context, answer-file parsing, and session initialization? In particular, what happens when the same MMLU-Pro items are rerun in fresh independent sessions?

5. What formal or empirical criterion determines when a gold-free conflict trigger is informative? Can the authors characterize task properties that predict the positive MMLU-Pro result and the negative legal result without hand-built domain routing?

## Scores

Soundness: 3/4 — The protocols, controls, and caveats are strong, but prospective validity, narrow coding scope, and unresolved mechanism attribution limit the claims.

Presentation: 4/4 — The paper is exceptionally clear about protocols, claim boundaries, tables, costs, and limitations.

Significance: 3/4 — The bounded-update framing and end-to-end improvements are relevant, but the practical gain is costly and the generality is limited.

Originality: 3/4 — The unified contract is a useful synthesis, though its components and strongest mechanisms are not shown to be novel causes of improvement.

Overall recommendation: 3/6 — Borderline: promising and unusually careful, but not yet sufficiently general or mechanistically supported for acceptance.

Confidence: 4/5 — The paper is sufficiently self-contained for a substantive assessment, although the underlying artifacts and execution cannot be independently checked here.

## Ethics and Limitations

The paper appropriately discusses the risks of using same-model agreement in high-stakes settings and reports that the legal reserve degraded performance. The handling of Korean precedent data is cautious: the authors state that they “did not establish full de-identification of facts” and therefore withhold item texts and outputs pending governance review. The environmental and cost burden is also reported rather than hidden, including 45.97 million tokens for the two MMLU-Pro OJ3 cohorts.

The main scientific limitations are the single-model evaluation, whole-file session dependence, small number of triggered conflicts, fixed-task Java replication, approximate compute matching, and the outcome-informed secondary repair control. These limitations are acknowledged by the authors, but together they constrain the paper’s conclusions to narrow end-to-end improvements rather than a validated general verification mechanism.

## Comment

I lean toward borderline reject. The paper’s strongest asset is its disciplined separation of end-to-end gains from mechanism claims, but that separation also exposes the central problem: support-aware arbitration does not beat a generic judge, and structured repair does not beat ordinary failure-feedback repair. The most important revision would be a genuinely prospective, compute-matched evaluation on new tasks that simultaneously tests generality and isolates whether the proposed bounded structure contributes beyond simply adding an evidence-informed second pass.

### Panel review 2 — experimentalist (accepted)

# Review: Mini Artichokes: Bounded Verification for Selective LLM Arbitration and Program Repair

## Summary

The paper studies a conservative two-stage approach to LLM correction: “freeze a prior state, route only an observable conflict or failure to a separate decision stage, restrict the allowed update, and preserve unaffected work.” On MMLU-Pro, the support-aware judge improves a direct Luna draw by 2.3 points but does not beat self-consistency or a compute-matched generic judge. On a fixed 20-task Java set, a failure-feedback repair pass improves Plain and Graph across five sessions, but a later generic repair control matches or exceeds the structured repair. The strongest conclusion is therefore that bounded, evidence-triggered second passes can help in these settings, while the proposed overlap and structured-operation mechanisms are not established.

## Strengths

- The paper states a precise, auditable arbitration policy: “if D1, D2, or D3 is invalid: return D1” and otherwise reviews only cases where “D2 == D3 and D2 != D1.” This makes the intervention and fallback behavior reproducible.

- The study reports full-denominator outcomes rather than only triggered cases. In replication 2, “OJ3 scored 613/1,000 versus D1's 590/1,000,” with “28 rescues” and “5 harms,” which is a meaningful and appropriately transparent decomposition.

- The paper uses strong controls. It explicitly reports that OJ3 “tied SC3 at 613/1,000” and achieved only “+2 point estimate over GJ3,” with `p=.3633`. This substantially limits the claim that support counts themselves are responsible for the gain.

- The coding evaluation correctly treats whole-batch sessions as the inferential unit. The paper reports that matched repair won all five Java sessions, while acknowledging that “the same 20 tasks recur” and that the result establishes “session repeatability on a fixed official set rather than new-task generality.”

- The expected-gain formulation is useful as an accounting framework. The identity `Δ = τ (q01 s01 - q10 s10)` clearly separates trigger prevalence, candidate quality, and authorized switching, and the paper correctly states that it is “not an independence assumption.”

- The paper is unusually candid about negative and null results. It reports that the legal reserve produced “a net loss of 29,” that strict overlap repair solved “5/20 versus 7/20,” and that ordinary repair exceeded matched repair in four of five sessions.

## Weaknesses

- The principal MMLU-Pro confirmation is less confirmatory than the presentation suggests. Replication 2 was authorized only after confirmation 1 was scored: “Because the direction was favorable but underpowered, we froze exactly one disjoint 1,000-question replication.” Although the policy was unchanged, this is a sequential, outcome-motivated decision without an explicit alpha-spending or pre-registration framework. The nominal `p=3.31e-5` should therefore be interpreted as evidence on the selected second cohort, not as an entirely prospective confirmatory test.

- The central mechanism is not demonstrated. OJ3’s advantage over D1 is accompanied by improvements from both controls: “SC3 and GJ3 both significantly improved over D1,” while “OJ3 was numerically highest” but was not significantly better than GJ3. Since only “68/2,000 questions triggered arbitration,” the paper cannot establish that support metadata causes the gain rather than merely adding another judge to a useful conflict-triggered pipeline.

- The MMLU inference substantially conditions on single whole-file sessions. The paper states that “each 1,000-question draw was generated in one complete-file agent session” and that the anomalous D2 session achieved only “145/1,000.” The reported item-level McNemar tests and bootstrap intervals therefore do not capture session-level variance, context effects, or runtime instability. The paper acknowledges this limitation, but it materially weakens claims about reproducible system performance.

- The coding evidence is narrow and has limited effective sample size. The five-session Java result uses one fixed set of 20 tasks, and “the inferential result is five positive whole-session differences on one fixed official task set.” This supports repeatability under that exact task distribution, but not broad coding generality. The earlier 60-task result has only “three whole-batch call clusters,” so its task-level significance is difficult to interpret as independent evidence.

- The mechanism control for coding was added after the main outcome was known. The ordinary-repair arm was “commissioned after the matched outcomes were known,” and although the paper labels it secondary, it is then used to support the conclusion that the common factor is generic failure feedback. This is reasonable exploratory evidence, but it cannot provide a clean causal attribution. In particular, the paper does not include a predeclared Plain-plus-ordinary-repair comparison under the same protocol.

- The computational trade-off is unfavorable and insufficiently integrated into the headline contribution. OJ3 uses “3.53-fold” the tokens of D1 for a “+2.3 percentage point” improvement, while the coding path takes “about 2.14 times Plain's agent time.” The paper reports these costs, but the practical value of the proposed policy depends heavily on application-specific utility, and no cost-normalized or quality-at-fixed-budget comparison is provided.

- The common theoretical contribution is modest. The expected-gain equation is correct but largely a restatement of rescue-minus-harm accounting. The paper’s broader principle—“freeze a prior state, expose a bounded conflict or failure to a separate decision stage, preserve unaffected state”—is sensible, but the experiments do not show that the full principle is better than simpler generic additional inference.

## Questions for the Authors

1. Given that replication 2 was selected after confirmation 1 showed a favorable direction, what exact inferential status should be assigned to `p=3.31e-5`, and why is no alpha adjustment or sequential-testing correction needed?

2. Can you provide repeated MMLU-Pro runs on the same question cohort, or another estimate of whole-file session variance, given that D2 scored only “145/1,000” in one session and “607/1,000” in the other?

3. How many of the 68 conflict cases were assigned to each anonymous candidate position and support-count configuration, and were these assignments balanced sufficiently to exclude position or formatting effects in OJ3 versus GJ3?

4. Why was a Plain-plus-ordinary-repair arm not included in the original coding protocol? Without it, how do you distinguish the value of failure feedback from the possibility that Graph creates a particularly repairable but inferior intermediate state?

5. What results would you expect on new coding tasks, rather than the repeated Java20 set, and can the authors predeclare such a test without changing the repair prompts or evaluation procedure?

6. Since the method’s main practical advantage is small relative to its cost, how does it compare with simpler alternatives such as one additional direct Luna draw or a compute-matched majority/judge policy under a fixed token or latency budget?

## Scores

Soundness: 3/4 — The protocols, controls, and caveats are careful, but single-session dependence and outcome-motivated replication limit the strength of the empirical claims.

Presentation: 3/4 — The paper is clear, well organized, and unusually explicit about inferential boundaries, though the argument is dense and occasionally repetitive.

Significance: 3/4 — The evidence supports a useful narrow lesson about failure-feedback second passes, but the accuracy gains are modest, costly, and not shown to generalize broadly.

Originality: 2/4 — The bounded-update framing is coherent, but support-aware arbitration and structured repair are not shown to outperform simpler compute-matched alternatives.

Overall recommendation: 3/6 — Borderline: the paper offers careful empirical evidence and valuable negative controls, but its main mechanism and broad universality claims remain unproven.

Confidence: 3/5 — The paper is sufficiently self-contained to assess, but the decisive numerical results and artifact claims cannot be independently verified here, and the effective replication units are limited.

## Ethics and Limitations

The paper appropriately notes that the legal data “did not establish full de-identification of facts” and therefore withholds “item texts and outputs pending a separate governance review.” It also reports the environmental cost—“45.97 million tokens across the two OJ3 cohorts”—rather than presenting the accuracy gain without resource accounting. The principal scientific limitations are the anomalous whole-file session, same-model correlated errors, the 68-case trigger set, the fixed Java task set, and the post hoc ordinary-repair control. The paper states these limitations candidly. No hidden reviewer-directed text is present.

## Comment

I recommend borderline acceptance/rejection consideration rather than a strong accept. The paper’s most credible contribution is the disciplined demonstration that an evidence-triggered second pass can improve a realized baseline, especially in the fixed Java experiment, while overlap metadata and elaborate repair instructions do not earn an advantage. The authors should most importantly strengthen the causal and generalization evidence: predeclare and run repeated, compute-matched evaluations on new tasks or repeated cohorts so that the modest gains can be separated from whole-file session variance and from the generic benefit of simply making another failure-informed model call.

### Panel review 3 — scope_ablation (accepted)

# Review: Mini Artichokes: Bounded Verification for Selective LLM Arbitration and Program Repair

## Summary

This paper proposes a conservative second-pass framework: preserve a base answer or code artifact, invoke additional reasoning only after an observable conflict or test failure, restrict the permitted update, and audit rescues versus harms. On a 1,000-question MMLU-Pro replication, OJ3 improves over direct Luna by 2.3 points, but ties self-consistency and is not significantly better than a compute-matched generic judge. On five sessions over the same 20 Java tasks, structured repair improves over Plain and Graph, although a later ordinary repair control matches or exceeds it. The strongest evidence therefore supports a narrow failure-feedback second pass, not support-aware arbitration or the proposed structured operations as causal mechanisms.

## Strengths

- The paper gives a precise and auditable behavioral contract. The policy explicitly says that on conflicts the judge may select only “the corresponding existing answer,” while “invalid judge output retains D1.” The expected-gain identity, `Δ = τ (q01 s01 - q10 s10)`, usefully makes clear that boundedness does not guarantee positive performance.

- The MMLU-Pro evaluation is carefully designed to avoid several common sources of leakage and post-hoc selection. The authors specify an official benchmark commit, deterministic category-proportional sampling, disjoint cohorts, and that “private gold was not mounted into any model workspace.” Reporting full-denominator scores and paired rescue/harm counts is substantially more informative than reporting only triggered-case accuracy.

- The paper is unusually candid about failed mechanism tests and negative transfer. It explicitly states that “OJ3 and GJ3 selected differently on only a small conflict subset,” that the support annotation’s causal effect is unresolved, and that the legal reserve produced “30 rescues but 59 harms.” This substantially improves the credibility of the conclusions.

- The coding study correctly treats whole-batch sessions as the inferential unit rather than pretending that 20 tasks sharing one model call are independent. The paper states that “the inferential result is five positive whole-session differences on one fixed official task set,” which is an appropriate qualification of the Java result.

- The presentation is clear and well organized. The claim hierarchy, experimental arms, ablations, and limitations make it easy to distinguish end-to-end improvements from mechanism attribution.

## Weaknesses

- The central generalization claim remains very narrow. The paper itself acknowledges that confirmation uses “one model, one runtime, and one primary benchmark,” while the coding evidence reuses “the same 20 Java tasks.” The cross-language evidence has only “three whole-batch call clusters.” Thus, the results establish performance in particular whole-file/session regimes, but provide limited evidence that the method is broadly useful across models, task distributions, or ordinary per-instance deployment.

- The MMLU result does not establish a benefit from support-aware arbitration. OJ3 is compared against a one-call baseline while consuming “3.53-fold” the tokens, ties SC3 at 613/1,000, and is not significantly better than GJ3 (`p=.3633`). Since GJ3 receives the same trigger, candidates, calls, and budget, the evidence supports generic additional judgment after sampling, not the support annotation as a useful mechanism. This is acknowledged by the paper, but it substantially narrows the contribution.

- The coding result does not identify which proposed structured operations matter. The matched repair bundles “counterexamples, preservation, and a double completion audit,” and the ordinary control was commissioned only “after the five-session matched results ... were known.” Ordinary repair scored 27/100 versus 25/100 for matched repair and “matched or exceeded the structured arm in four sessions.” The end-to-end value of a separate failure-feedback pass is plausible, but the paper cannot attribute it to bounded authorization, explicit counterexamples, preservation, or double auditing.

- The whole-file execution design creates substantial unresolved variance. Confirmation 1 includes a D2 session scoring only “145/1,000,” and the authors state that “no MMLU-Pro pipeline was rerun on identical items.” The reported item-level tests therefore condition on realized, potentially highly context-dependent sessions and do not estimate repeatability across session initialization, ordering, or runtime state. The paper is transparent about this limitation, but it affects the strength of the confirmatory inference.

- The confirmatory status of the MMLU replication is weaker than a prospective replication. The paper says, “Because the replication was authorized after the first cohort was scored,” and the second cohort was selected after the first favorable directional result. Treating replication 2 alone as the primary test is defensible, but the decision to run that replication was outcome-informed, and the strongest controls were not part of the formal confirmatory sequence.

- The practical trade-off is not fully characterized. OJ3 uses “45,973,780 tokens” versus 13,009,321 for D1 and has longer critical paths, while the paper does not report monetary cost despite asking what the method costs. The modest gain may be worthwhile in some settings, but the deployment value cannot be assessed without clearer cost and latency normalization.

## Questions for the Authors

1. Can the MMLU pipeline be repeated across independently initialized complete-file sessions, or evaluated with independent per-question calls, to quantify how much of the gain and trigger rate is session-specific?

2. Given that OJ3 ties SC3 and does not significantly beat GJ3, what precise claim about support counts remains that is not explained by generic candidate judgment after extra sampling?

3. Can the coding method be evaluated on newly sampled tasks, languages, or repositories with the ordinary-repair control preregistered before outcomes are observed?

4. Which component of the repair bundle is necessary or useful: failure feedback itself, requirement reconstruction, counterexamples, preservation, or double auditing? A factorial or progressively simplified ablation would clarify this.

5. What are the monetary costs and realistic latency under parallel and sequential deployment, and do the gains persist with a different model or runtime?

## Scores

Soundness: 3/4 — The protocols and caveats are unusually careful, but whole-session dependence, post-outcome control selection, and narrow evaluation limit the strength of the evidence.

Presentation: 4/4 — The paper is clear, well structured, and appropriately distinguishes confirmed findings from unresolved mechanism claims.

Significance: 3/4 — A practical failure-feedback second pass could be useful, but the demonstrated gains are expensive and confined to narrow settings.

Originality: 3/4 — The bounded-update framing and cross-regime comparison are interesting, although the underlying sampling, judging, repair, and auditing components are established ideas.

Overall recommendation: 3/6 — Borderline; the paper contains a credible but narrowly supported empirical contribution.

Confidence: 4/5 — The paper is sufficiently self-contained to assess, though the key numerical claims and artifacts cannot be independently rerun here.

## Ethics and Limitations

The paper appropriately reports that it uses public benchmarks, open-source coding tasks, and locally curated legal text without human participants. The handling of the legal reserve is cautious: the authors note that “Court decisions can remain re-identifiable through distinctive events” and withhold item texts and outputs pending governance review. The study’s substantial compute burden—“45.97 million tokens across the two OJ3 cohorts”—is also disclosed. The main scientific limitations are the single-model evaluation, possible benchmark contamination, same-model correlated errors, whole-file context effects, fixed Java task reuse, lack of a complete Aider evaluation, and confounding in the legal negative boundary.

## Comment

I recommend borderline acceptance. The paper’s most defensible contribution is evidence that a separate second pass supplied with concrete execution failures can improve a frozen coding artifact in a particular fixed-task regime, together with a valuable demonstration that overlap metadata and elaborate repair instructions are not themselves validated mechanisms. The most important revision would be independent, prospective evaluation on new tasks and models with compute-matched controls fixed before outcomes; without that, the broad bounded-verification framing remains substantially ahead of the demonstrated generality.
