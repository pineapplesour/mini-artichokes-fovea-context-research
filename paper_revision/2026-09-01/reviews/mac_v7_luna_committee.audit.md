# ICML-Style Paper Review

## Paper and Evidence Identity

- Review method: full review — deterministic evidence audit + review panel. The panel's review is the official output; this document is its audit sidecar.
- Review Agent name/version: paper-reviewer / `sha256:9886349f92661c3c73b70f216a7038b741b47282d7624538ad207dd3fbb2d4c0`
- Review-agent spec path/hash: `review-agent-spec.md` / `sha256:08b13516a2cb0e5151c6b4dc24f98e6d191b35ee30d69ea300b2d6ff2d5a5945`
- Original paper identity: `Mini_Artichokes_manuscript_v3.md` / `text/markdown` / `sha256:009295b2b75f319eb4c76f9dfdfe4f633123f7f577dbf318411094302f8e12ab` / `59809` bytes
- Derived Markdown identity: `Mini_Artichokes_manuscript_v3.md` / `text/markdown` / `sha256:009295b2b75f319eb4c76f9dfdfe4f633123f7f577dbf318411094302f8e12ab` / `59809` bytes
- Original PDF page count: `n/a`
- Converter: `none (Markdown source)`
- Paper version/hash: `Mini_Artichokes_manuscript_v3.md` / `sha256:009295b2b75f319eb4c76f9dfdfe4f633123f7f577dbf318411094302f8e12ab`
- Evidence bundle reviewed: `evidence`: `EVIDENCE_SCOPE.md` (`sha256:a618bf8139997e26e432e82c0f74fea061a96989c6ded9526ed28fcfce2f541d`), `LEGAL_RESERVE_GOVERNANCE.md` (`sha256:33e0abeffb8cc6de841cb58b8f14ecb8926b9886f643d1e04ec77312f529e2d5`), `MMLU_PROTOCOL_CONFIRMATION1.md` (`sha256:f78ea8a6294728e3b1abd3c6c3c74cdf89f474da83da0f0ae7b7f56d637c60ef`), `MMLU_PROTOCOL_REPLICATION2.md` (`sha256:0fe6bd59e759d1c761770267fe9b7a8f2bef5e2f47ba6c768e57cfe35352c9a7`), `MMLU_PRO_CUMULATIVE_RESULTS.md` (`sha256:52cbe8e02c8fe34f72d88ed6c24aa26dcf6afb45c44b3ede70fed4274242a39c`), `SC3_BOUNDARY_AUDIT.md` (`sha256:fc38b4c284c643e4a4f9ba813f57bcac8c15e04069d72307b468e5410d1e7ad2`), `UNIVERSAL_DEVELOPMENT_RESULTS.md` (`sha256:e1a542a410331498e46472a0061c344cc806189898e0576b4a20d8188253f791`), `aider_hidden_java20_results.json` (`sha256:d1abe2a31712c0d446bba8728118246ce2a262bc44124600de95351df75ed9e6`), `aider_hidden_results.json` (`sha256:0c618e58ab5720e1044da799193325a5018c27e911179ed75048351af72461c1`), `aider_java20_ordinary_control_results.json` (`sha256:2f9240417643e193e932d8979052ab137e5450808dbd42e0b6040913d0e03676`), `aider_java20_session_replication_results.json` (`sha256:75eb1d868b5d5663b77d5730107b01e91f372fb4d58d180caef812e7c7b7be9b`), `experiments.jsonl` (`sha256:153c86902a4dff33581c081f09c880e4b0cee069b240f8f2973d4f3f5661271c`), `legal_boundary_score.json` (`sha256:14318b0953051f0ccb4a1ab3390914eb1abab000c45f48c618cd45a7fd8a4ba1`), `mmlu_pro_confirmation1_score.json` (`sha256:5ba78d945aff95e5c3b7d93b0a44d592bbe16b2587d4d2228d179f5e1339128f`), `mmlu_pro_cumulative_score.json` (`sha256:bdf7e36abcf05b8a05d921a259590b919f54da2b7a1658dcc4057acabc905fec`), `mmlu_pro_replication2_score.json` (`sha256:2442d9018a0241e203500f85e859d76c78cda52f74277090856f5b40d3ca7685`), `reasoning_method_screen.json` (`sha256:28122fee17330f5b0c317cf107f182a35604d1ee2c4805145305e950af0dba99`)
- Frozen at (UTC): `2026-09-02T05:43:04+00:00`

## Summary

The paper, "Mini Artichokes: Bounded Verification for Selective LLM Arbitration and Program Repair", presents a method and supporting experiments. It reports 158 quantitative result claim(s) and cites 29 prior work(s). Deterministic audit: 22 contradiction(s), 0 dishonest self-certification(s), 75 mechanical finding(s); 12 result claim(s) evidence-backed, 855 unverifiable. Overall recommendation: 2/6 [claim-001].

## Strengths

- The result claim is directly supported by the supplied evidence [claim-475].
- The result claim is directly supported by the supplied evidence [claim-476].
- The result claim is directly supported by the supplied evidence [claim-477].
- The result claim is directly supported by the supplied evidence [claim-478].
- The result claim is directly supported by the supplied evidence [claim-479].
- The result claim is directly supported by the supplied evidence [claim-480].
- The result claim is directly supported by the supplied evidence [claim-504].
- The result claim is directly supported by the supplied evidence [claim-550].
- The result claim is directly supported by the supplied evidence [claim-551].
- The result claim is directly supported by the supplied evidence [claim-552].
- The result claim is directly supported by the supplied evidence [claim-553].
- The result claim is directly supported by the supplied evidence [claim-565].

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
- The baseline-fairness check observed claim does not name a baseline: beats Plain and Graph on the fixed Java20 set, while a later generic repair; expected the improvement claim to identify the compared baseline [finding-065].
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
- Scope limitation — the generalized claim at paper line 60 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 136 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 151 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 422 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 616 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 870 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 930 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.
- Scope limitation — the generalized claim at paper line 976 exceeds the supplied ledger coverage: 25 trials; 0 distinct seeds (none stated); GPU types: none stated; 0 benchmarks (none stated); 54 metrics (accuracy, aider_accuracy, aider_calls_per_batch, aider_ci_lower_pp, aider_ci_upper_pp, aider_correct, aider_difference_pp, aider_harms, aider_n, aider_net_correct, aider_one_sided_exact_p, aider_rescues, aider_two_sided_exact_p, base_correct, both_candidates_wrong, candidate_correct, ci_lower_pp, ci_upper_pp, confirmation_1_correct, conflict_cases, consensus_correct, correct, gj3_base_selections, gj3_consensus_selections, gj3_correct, harms, leet_critic_verifier_correct, leet_graph_correct, leet_n, leet_plain_correct, leet_reflexion_correct, leet_sc3_correct, leet_self_refine_correct, leet_skeleton_correct, leet_tot_correct, legal_accuracy, legal_correct, legal_signal_accuracy, legal_signal_cases, legal_signal_correct, n, net_correct, oj3_base_selections, oj3_consensus_selections, oj3_correct, one_sided_exact_mcnemar_p, pooled_accuracy, pooled_correct, reference_accuracy, reference_correct, replication_2_correct, rescues, semantic_calls, token_ratio_to_d1); 1 confirmation run.

## Questions for the Authors

1. Concrete follow-up — Run the named baseline under the same metric and budget. [finding-004, finding-005, finding-006, finding-007, finding-008, finding-009, finding-010, finding-011, finding-012, finding-013, finding-014, finding-015, finding-016, finding-017, finding-018, finding-019, finding-020, finding-021, finding-022, finding-023, finding-041, finding-042, finding-048, finding-049, finding-050, finding-051, finding-054, finding-055, finding-056, finding-057, finding-058, finding-059, finding-060, finding-061, finding-062, finding-063, finding-064, finding-065, finding-066, finding-067, finding-068, finding-069, finding-070, finding-071, finding-072, finding-073, finding-074, finding-075]
2. For reproducibility and completeness (standard ICML/NeurIPS checklist items), the paper does not appear to report the compute / hardware used. Could the authors clarify these?
3. 124 extracted result/arithmetic claim(s) could not be checked against the supplied evidence and are listed with their source lines in the Evidence Trace — could the authors provide the underlying results?

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
- Frozen review identity: `sha256:ed8f215d7b49977726a374c8541e89294e8c44a19886cc071819479c67faed65`.
- Verdict labels digest: `sha256:96fbb2c71e6954812a7dd4b264cfaf175a3b19f62f6e2d98e1ee52ae8103789e`.
- External citation snapshot digest: `sha256:e54eabe17ac85420535a902a97ae2bd574436f4df521d70c56a0c32af4df6778`.
- Scientific judgment identity: `sha256:11e784035e5f5ba3c0d44f466ce4f3a010c55fc90484b38ed6ee935d0ebb3ae4`.
- Review panel configuration: panel=3, model=`gpt-5.6-luna`, synthesis=area-chair.
- Panel reviewer `theorist`: prompt=`sha256:a57f47205e8ef9f677a2bd38778f42dd0532438b7f86098047ad3a382c92dc67`, response=`sha256:86173bf8ec508298cb522d503e40340cc78ddb6fc4ddfd84f613dd7d65ea7b81`, status=ok.
- Panel reviewer `experimentalist`: prompt=`sha256:e2f0c45bf0661e062f4af2f13feb91d84c69a408619c10a7ad3aaee8c5fd1f5e`, response=`sha256:0cf04f60763f3027ebeb713038d6250691e08995adec471d8ff1cc4be9bad8fb`, status=ok.
- Panel reviewer `scope_ablation`: prompt=`sha256:490b52c37f691ba22901518350b173e5d024a58908bfdcf10e38885cd3212fad`, response=`sha256:122089ef44e87950ab5aa391e959278e6f393c84f108970075077cbead2d1764`, status=ok.
- Output path: `mac_v7_luna_committee.md`.
- Frozen paper input: `Mini_Artichokes_manuscript_v3.md` (`sha256:009295b2b75f319eb4c76f9dfdfe4f633123f7f577dbf318411094302f8e12ab`).
- Frozen original identity: `Mini_Artichokes_manuscript_v3.md` (`text/markdown`, `sha256:009295b2b75f319eb4c76f9dfdfe4f633123f7f577dbf318411094302f8e12ab`, 59809 bytes, page count=n/a).
- Frozen derived identity: `Mini_Artichokes_manuscript_v3.md` (`text/markdown`, `sha256:009295b2b75f319eb4c76f9dfdfe4f633123f7f577dbf318411094302f8e12ab`, 59809 bytes).
- Frozen converter: `none (Markdown source)`.
- Pre-S1 sanitation: 0 trace(s), 0 injection finding(s).
- S1 parse inventory: 40 sections, 9 tables, 707 numeric tokens with source locations.
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
- S5 DRAFT/GROUND: 211 candidate comment(s), 211 retained, 0 deleted, 124 criticism comment(s) converted to questions.
- S2/S4 claim verdicts:
- [claim-001] **contradicted** — paper:5 — Repeated inference can improve large-language-model (LLM) outputs, but — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-004`, `finding-005`.
- [claim-060] **contradicted** — paper:63 — methods show that diversity and selection can outperform a single trajectory. — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-008`, `finding-009`.
- [claim-092] **contradicted** — paper:92 — **RQ1:** Does the frozen support-aware policy improve full-denominator — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-010`, `finding-011`.
- [claim-094] **contradicted** — paper:95 — **RQ2:** Does it outperform strong multi-call controls: three-draw majority — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-012`, `finding-013`.
- [claim-098] **contradicted** — paper:99 — **RQ4:** Does a frozen bounded structured-repair system repeatedly improve — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-014`, `finding-015`.
- [claim-154] **contradicted** — paper:163 — solutions can also improve mathematical reasoning [8]. — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-016`, `finding-017`.
- [claim-238] **contradicted** — paper:259 — the judge improve an answer by synthesizing new content. — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-020`, `finding-021`.
- [claim-391] **contradicted** — paper:424 — The strict V3 development arm improved 566 to 587 — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-022`, `finding-023`.
- [claim-475] **supported** — paper:514 — D1 direct Luna | 597 | 590 | 1,187 | 59.35% — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:1#confirmation_1_correct (number-0206)`, `experiments.jsonl:1#replication_2_correct (number-0207)`, `experiments.jsonl:1#pooled_correct (number-0208)`, `experiments.jsonl:1#pooled_accuracy (number-0209)`.
- [claim-476] **supported** — paper:515 — D2 | 145 | 607 | 752 | 37.60% — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:2#confirmation_1_correct (number-0210)`, `experiments.jsonl:2#replication_2_correct (number-0211)`, `experiments.jsonl:2#pooled_correct (number-0212)`, `experiments.jsonl:2#pooled_accuracy (number-0213)`.
- [claim-477] **supported** — paper:516 — D3 | 587 | 586 | 1,173 | 58.65% — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:3#confirmation_1_correct (number-0214)`, `experiments.jsonl:3#replication_2_correct (number-0215)`, `experiments.jsonl:3#pooled_correct (number-0216)`, `experiments.jsonl:3#pooled_accuracy (number-0217)`.
- [claim-478] **supported** — paper:517 — SC3 majority | 596 | 613 | 1,209 | 60.45% — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:4#confirmation_1_correct (number-0218)`, `experiments.jsonl:4#replication_2_correct (number-0219)`, `experiments.jsonl:6#replication_2_correct (number-0219)`, `experiments.jsonl:4#pooled_correct (number-0220)`, `experiments.jsonl:4#pooled_accuracy (number-0221)`.
- [claim-479] **supported** — paper:518 — GJ3 generic judge | 600 | 611 | 1,211 | 60.55% — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:5#confirmation_1_correct (number-0222)`, `experiments.jsonl:5#replication_2_correct (number-0223)`, `experiments.jsonl:5#pooled_correct (number-0224)`, `experiments.jsonl:5#pooled_accuracy (number-0225)`.
- [claim-480] **supported** — paper:519 — **OJ3 support-aware judge** | **601** | **613** | **1,214** | **60.70%** — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:6#confirmation_1_correct (number-0226)`, `experiments.jsonl:4#replication_2_correct (number-0227)`, `experiments.jsonl:6#replication_2_correct (number-0227)`, `experiments.jsonl:6#pooled_correct (number-0228)`, `experiments.jsonl:6#pooled_accuracy (number-0229)`.
- [claim-504] **supported** — paper:546 — **OJ3 vs D1** | **28** | **5** | **+23** | **3.31e-5** | **+1.2** | **+3.5** — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:7#rescues (number-0262)`, `experiments.jsonl:7#harms (number-0263)`, `experiments.jsonl:11#harms (number-0263)`, `experiments.jsonl:7#net_correct (number-0264)`, `experiments.jsonl:7#one_sided_exact_mcnemar_p (number-0265)`, `experiments.jsonl:7#ci_lower_pp (number-0266)`, `experiments.jsonl:7#ci_upper_pp (number-0267)`.
- [claim-505] **contradicted** — paper:547 — OJ3 vs SC3 | 2 | 2 | 0 | .6875 | -0.4 | +0.4 — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-024`, `finding-025`, `finding-026`, `finding-027`, `finding-028`.
- [claim-506] **contradicted** — paper:548 — OJ3 vs GJ3 | 5 | 3 | +2 | .36328 | -0.3 | +0.8 — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-029`, `finding-030`, `finding-031`, `finding-032`, `finding-033`.
- [claim-507] **contradicted** — paper:549 — SC3 vs D1 | 30 | 7 | +23 | 9.55e-5 | +1.2 | +3.5 — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-034`, `finding-035`.
- [claim-508] **contradicted** — paper:550 — GJ3 vs D1 | 24 | 3 | +21 | 2.46e-5 | +1.1 | +3.1 — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-036`, `finding-037`, `finding-038`, `finding-039`.
- [claim-550] **supported** — paper:604 — D1 | 1 | 13,009,321 | 1.00x — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:1#total_tokens (number-0354)`.
- [claim-551] **supported** — paper:605 — SC3 | 3 | 45,056,433 | 3.46x — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:4#total_tokens (number-0357)`.
- [claim-552] **supported** — paper:606 — GJ3 | 4 | 45,787,649 | 3.52x — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:5#semantic_calls (number-0359)`, `experiments.jsonl:6#semantic_calls (number-0359)`, `experiments.jsonl:5#total_tokens (number-0360)`.
- [claim-553] **supported** — paper:607 — OJ3 | 4 | 45,973,780 | 3.53x — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:5#semantic_calls (number-0362)`, `experiments.jsonl:6#semantic_calls (number-0362)`, `experiments.jsonl:6#total_tokens (number-0363)`.
- [claim-559] **contradicted** — paper:617 — MMLU-Pro evidence: a stricter overlap policy improved 566/941 to 587/941 (+21; — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-041`, `finding-042`.
- [claim-565] **supported** — paper:623 — Relative to P1, OJ3 produced 30 rescues — Every S3 evidence-bearing value in this claim has a matching trace. Evidence: `experiments.jsonl:13#rescues (number-0390)`, `experiments.jsonl:17#rescues (number-0390)`.
- [claim-566] **contradicted** — paper:624 — but 59 harms, a net loss of 29. — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-044`.
- [claim-567] **contradicted** — paper:624 — On 65 cases carrying the mechanical support — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-045`.
- [claim-568] **contradicted** — paper:625 — signal, the supported outcome was correct only 32 times (49.2%). — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-046`, `finding-047`.
- [claim-575] **contradicted** — paper:634 — same frozen official Java20 set, matched structured repair outperformed both — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-048`, `finding-049`.
- [claim-622] **contradicted** — paper:686 — Structured repair improved Plain in all three disjoint — A deterministic mechanical finding contradicts this source passage. Evidence: `finding-050`, `finding-051`.
- (+859 further extracted claim(s) — mostly unverifiable prose — omitted here for brevity; all are labelled in S2/S4 with source lines.)

## Comment

Recommendation: 2/6. A proven integrity problem (a contradiction or dishonest self-certification) is the decisive factor and must be resolved before this paper can be accepted. Most useful next step for the authors — The template-compliance check observed required section 'Research Spec' is absent; expected a 'Research Spec' section [finding-001].

## Panel Reviews (provenance)

### Panel review 1 — theorist (accepted)

# Review: Mini Artichokes: Bounded Verification for Selective LLM Arbitration and Program Repair

## Summary

This paper proposes a bounded-update framework for LLM inference: preserve a frozen answer or patch, invoke a separate decision/repair stage only after observable conflict or failure evidence, constrain the update, and audit rescues and harms. It reports a positive but compute-asymmetric MMLU-Pro result, narrow session-level coding gains on one fixed Java task set, and controls indicating that the explicit overlap/support mechanism is not itself responsible for the gains.

## Strengths

- The arbitration policy is clearly specified and mechanically constrained: “if not `(D2 == D3 and D2 != D1)`, return D1,” while the judge “cannot create a third answer.” This makes the intervention auditable and prevents unconstrained rewriting.

- The paper distinguishes routing from evidence and tests this distinction with strong controls. It explicitly states that OJ3 and GJ3 use the “same eligible IDs, anonymous candidate strings, rotation, model, reasoning effort, call count, and fallback,” with support counts as the treatment.

- The primary MMLU-Pro result is reported on the full denominator with paired accounting: OJ3 obtained “28 rescues, 5 harms, +23 correct,” with a one-sided exact `p=3.31e-5` and confidence interval `[+1.2,+3.5]` percentage points.

- The authors appropriately avoid overstating mechanism attribution. They state that “support annotation did not beat a generic judge” and that “the additional support count remains a candidate mechanism rather than a confirmed one.”

- The coding evaluation correctly treats the whole 20-task model invocation as the experimental unit rather than pretending that 100 repeated task-session outcomes are independent. The paper explicitly says that “the inferential result is five positive whole-session differences on one fixed official task set.”

- The manuscript is unusually candid about negative and null findings, including the legal reversal (“OJ3 produced 30 rescues but 59 harms”) and the matched-minus-ordinary coding result of “-2 points” with interval `[-7,+2]`.

- The provenance and reproducibility description is strong. The paper provides frozen commits, protocols, scorers, result hashes, and explicit restrictions against reruns, top-ups, and post-score remapping.

## Weaknesses

- The main MMLU-Pro improvement is not a fair accuracy comparison at equal compute. OJ3 uses “3.53-fold” the tokens of D1, while the paper’s strongest causal comparison, OJ3 versus GJ3, is only `+2` correct with `p=.3633`. Thus the evidence supports benefit from additional inference and generic judging, but not a meaningful advantage for Mini Artichokes over an appropriately compute-matched alternative.

- The confirmatory MMLU inference is conditional on one realized whole-file draw per arm, and the paper acknowledges that “the reported paired p-values and bootstrap intervals therefore condition on the realized sessions and do not estimate between-session repeatability.” This is especially consequential because D2 scored only `145/1,000` in confirmation 1 and then `607/1,000` in replication 2. The integrity checks rule out simple file corruption, but they do not establish that the observed replication effect is stable across fresh sessions.

- The claim that bounded verification improves coding performance is narrow and partly post hoc. The confirmatory Java result uses “the same frozen official Java20 set” across five sessions, so it demonstrates repeatability on those tasks but provides little evidence of new-task generalization. The paper itself concedes that this is “same-task session repeatability rather than performance on new tasks.”

- The explicit structured repair mechanism is not supported by the reported controls. Ordinary repair scored `27/100` versus `25/100` for matched structured repair, and the paper states that ordinary repair “matched or exceeded the structured prompt in four sessions.” Consequently, the scientifically supported intervention appears to be an additional failure-feedback call, not the proposed counterexample, preservation, and double-audit bundle.

- The coding control most directly challenging the structured mechanism was commissioned after the favorable matched results were known. Although the authors correctly label it secondary, this sequencing means that the paper’s strongest mechanistic conclusion rests on an adaptive control rather than a predeclared treatment comparison.

- The common framework is conceptually appealing but theoretically underdeveloped. The paper gives a behavioral contract, but it does not provide conditions under which a conflict trigger or bounded update should improve expected accuracy. For example, there is no formal analysis relating trigger precision, candidate correlation, judge error, and the required rescue-to-harm ratio. The empirical observation that “agreement was informative on MMLU-Pro but far from sufficient” remains descriptive.

- The two regimes share a slogan-level contract but differ materially in their evidence quality: answer arbitration uses correlated same-model agreement, whereas repair uses external hidden-test feedback. The paper correctly says this is “a transfer of the bounded-update contract, not the same algorithm,” but this weakens the claim that one unified method has been demonstrated.

- The legal negative boundary is informative but difficult to interpret. The reserve simultaneously changes “domain, task, prompt, and label structure,” so it cannot distinguish whether the failure arises from partial observability, legal reasoning difficulty, prompt mismatch, or binary outcome formulation. It is therefore a useful warning, but not a controlled test of the proposed operating boundary.

## Questions for the Authors

1. Given that OJ3 uses `3.53x` the tokens of D1 and does not significantly beat GJ3, what practical or statistical basis supports presenting support-aware arbitration as more than a compute-intensive generic judging pipeline?

2. How does the OJ3 advantage vary across fresh whole-file sessions on the same or comparable MMLU-Pro items? The paper reports that D2 changed from `145/1,000` to `607/1,000`; can the authors quantify sensitivity to session initialization and within-file context?

3. Can the authors provide a predeclared, same-budget comparison between ordinary failure-feedback repair and matched structured repair on new coding tasks, rather than relying on the review-triggered Java control?

4. What formal assumptions would make the proposed trigger beneficial? In particular, can the authors derive an expected-gain condition using the trigger prevalence, candidate correctness correlation, judge accuracy, and the observed rescue/harm rates?

5. Why should the coding results be described as evidence for the common bounded-update principle when the strongest coding signal comes from external execution feedback, while the MMLU signal comes from correlated model agreement?

6. Can the authors evaluate whether the coding effect persists when the task set, language, repair prompt, and evaluator setup are all frozen before outcomes are observed, with enough independent task clusters to support task-level inference?

## Scores

Soundness: 3/4 — The experimental accounting and limitations are careful, but the principal gains are compute-asymmetric and conditional on a small number of realized whole-file sessions.

Presentation: 4/4 — The paper is clear, well organized, and unusually precise about protocols, inferential boundaries, and failed controls.

Significance: 3/4 — The bounded-update framing and negative results are useful, but the demonstrated practical advantage over strong matched alternatives is limited.

Originality: 3/4 — The contract is a reasonable synthesis of selective arbitration and evidence-based repair, though its individual components are largely established ideas.

Overall recommendation: 3/6 — Borderline; the paper contains credible empirical observations and strong methodological candor, but does not yet establish a novel mechanism or broad general advantage.

Confidence: 4/5 — The claims and tables are sufficiently self-contained to assess, although the underlying executions and artifacts cannot be independently rerun here.

## Ethics and Limitations

The paper responsibly discusses the risks of deploying same-model agreement in high-stakes settings, stating that the legal result “cautions against deploying same-model agreement as a reliability signal in high-stakes decision support without external evidence and domain-specific validation.” It also reports that legal facts may remain re-identifiable and withholds the legal item texts pending governance review. The principal scientific limitations are substantial: one model and runtime, whole-file session dependence, correlated same-model draws, only `68/2,000` arbitration triggers, approximate compute matching, one fixed 20-task Java set, and a coding control added after matched outcomes were known. These limitations are acknowledged clearly, but they materially constrain the breadth of the conclusions.

## Comment

I recommend borderline acceptance at most. The paper’s strongest contribution is a disciplined empirical demonstration that a separate, evidence-triggered second pass can sometimes improve a frozen baseline, coupled with honest evidence that overlap metadata and elaborate repair instructions are not established causes. The key issue to address is whether the proposed bounded-update framework provides a reproducible advantage over compute-matched generic inference and ordinary failure-feedback repair on independently frozen tasks; without that evidence or a formal account of when the contract should help, the current results support a useful engineering observation more than a broadly validated method.

### Panel review 2 — experimentalist (accepted)

# Review: Mini Artichokes: Bounded Verification for Selective LLM Arbitration and Program Repair

## Summary

This paper proposes a conservative second-pass framework that freezes an initial answer or code patch, invokes additional review only after an observable conflict or failure, restricts the permissible update, and preserves unaffected work. It reports a statistically significant improvement over a single direct Luna draw on a disjoint 1,000-question MMLU-Pro replication, but no significant advantage over compute-matched generic judging. A five-session Java hidden-test study shows repeatability on one fixed task set, while the paper’s own matched ordinary-repair control undermines claims about the explicit structured operations. The work is careful and unusually candid, but its strongest claims are narrow and the central mechanism is not established.

## Strengths

- The paper cleanly defines a conservative arbitration policy with an explicit fallback: “On `C(x)=0`, both judge arms return `D1`,” and the judge “cannot create a third answer.” This makes rescue/harm accounting and comparison with ordinary candidate selection possible.

- The primary MMLU-Pro replication is substantially better controlled than an exploratory aggregate. The authors state that they “did not change any policy, prompt, model, effort, role mapping, conflict rule, fallback, or statistic,” and they use a pre-frozen, disjoint 1,000-question cohort.

- The paper reports both benefits and costs. OJ3 obtains “28 rescues, 5 harms, +23 correct,” but uses “45,973,780 tokens versus 13,009,321 for D1,” a 3.53-fold token ratio. This is important context for evaluating the practical value of a 2.3-point improvement.

- The analysis appropriately distinguishes end-to-end improvement from mechanism attribution. The paper reports that OJ3 “tied SC3 at 613/1,000” and achieved only a descriptive “+2 point estimate over GJ3,” rather than presenting support counts as proven causal evidence.

- The coding experiments correctly recognize whole-batch dependence. The authors state that “the inferential result is five positive whole-session differences on one fixed official task set,” rather than treating the 100 repeated task-session outcomes as independent.

- The limitations are unusually substantive. The paper explicitly notes that “the reported paired p-values and bootstrap intervals therefore condition on the realized sessions and do not estimate between-session repeatability,” and that the Java study “estimates same-task session repeatability rather than performance on new tasks.”

## Weaknesses

- The main MMLU-Pro result is not a compute-matched superiority result. OJ3 uses 4 calls and 3.53 times the tokens of D1, while its comparison against the closest control is null: “OJ3 tied SC3 at 613/1,000,” and OJ3 versus GJ3 had “+2” correct with `p=.36328`. Thus, the evidence supports that additional inference can improve over one draw, not that support-aware arbitration improves over strong generic multi-call alternatives.

- The paper’s central mechanistic claim remains unresolved. Only 68/2,000 questions triggered arbitration, and the paper acknowledges that the support-aware increment over GJ3 “lacked power.” In Table 2, OJ3 versus GJ3 has only 5 rescues and 3 harms. The claim that support-aware arbitration is a meaningful mechanism is therefore not supported beyond a small, non-significant point estimate.

- The coding evidence is narrow despite strong session-level statistics. The study uses “the same 20 tasks” in all five sessions, and the authors concede that this establishes “session repeatability on a fixed official set rather than new-task generality.” Since the Java tasks are reused, the result cannot substantiate broad program-repair generality.

- The post hoc ordinary-repair control substantially weakens the proposed structured mechanism. Matched repair scores 25/100 repeated task-session outcomes versus 27/100 for ordinary repair, with matched-minus-ordinary mean `-2` and bootstrap interval `[-7,+2]`. The paper correctly states that the ordinary prompt “matched or exceeded the explicit structured prompt in four sessions,” but this leaves the specific counterexample, preservation, and double-audit components unsupported.

- The confirmatory interpretation is limited by adaptive study history. Replication 2 was authorized “after the first cohort was scored,” and the first cohort was directionally favorable. Treating replication 2 alone as confirmatory is defensible, but it makes the result a confirmation of a selected follow-up rather than an entirely prospective first test of the method.

- The session-level coding significance is fragile. Both comparisons rely on only five session differences, with `p=.03125`; one changed session outcome would materially alter the inference. Moreover, the paper reports that Plain and Graph call order alternated, but it does not provide enough information to assess whether session initialization, ordering, or other runtime effects could explain part of the consistent advantage.

- The proposed common principle is broader than the evidence. The conclusion claims support for “bounded second-pass verification,” but the two regimes differ materially: arbitration uses same-model answer samples, whereas repair uses external hidden-test failure feedback and permits code edits. The paper itself says this is “a transfer of the bounded-update contract, not the same algorithm,” so the shared abstraction is plausible but not yet demonstrated as a general causal principle.

- Reproducibility is asserted more than demonstrated in the paper. It says that the artifact contains “exact prompts, accepted candidate and judge outputs, private-score scripts, aggregate reports, and tests,” and provides hashes, but no accessible artifact location or representative raw outputs is supplied here. Without those materials, the unusual whole-file execution behavior—especially the 14.5% D2 result in confirmation 1—cannot be independently audited.

## Questions for the Authors

1. Can you provide a prospective or independently held-out evaluation comparing OJ3 directly against GJ3 and SC3 with sufficient triggered conflicts to estimate the support-count effect?

2. Can the Java repair result be replicated on new, previously unused tasks or on a larger set of independently sampled task collections, rather than five sessions over the same 20 tasks?

3. What are the full per-session Graph, matched-repair, and ordinary-repair patches and failure outputs, and do qualitative analyses show that ordinary repair succeeds through the same behaviors claimed for the structured repair?

4. How sensitive are the MMLU results to the complete-file session format, particularly the anomalous D2 confirmation session with only 145/1,000 correct? An independent rerun on the same questions would help distinguish method effects from session-level instability.

## Scores

Soundness: 3/4 — The primary comparisons and caveats are carefully designed, but the strongest mechanism and generality claims are not established.

Presentation: 4/4 — The paper is exceptionally clear about protocols, inferential boundaries, costs, and limitations.

Significance: 3/4 — The bounded-update framing and negative boundary are useful, but the demonstrated gains are modest and narrow.

Originality: 3/4 — The unified contract is a useful synthesis, although its components and strongest coding operations are not shown to be novel causal drivers.

Overall recommendation: 3/6 — Borderline: a careful empirical paper with a credible narrow result, but insufficient evidence for a broadly significant or mechanism-specific contribution.

Confidence: 3/5 — The paper is detailed enough to assess, but the key whole-file executions and artifacts cannot be independently checked from the manuscript.

## Ethics and Limitations

The paper appropriately reports the substantial compute cost: “45.97 million tokens across the two OJ3 cohorts.” Its treatment of the legal reserve is also responsible: it withholds item texts and outputs because full de-identification was not established and notes that court decisions may remain re-identifiable. The negative legal result is valuable as a warning against treating same-model agreement as a high-stakes reliability certificate.

The principal limitations are the single model and runtime, whole-file session dependence, anomalous session behavior, small arbitration conflict set, fixed-task Java replication, lack of full Aider-suite coverage, and post hoc ordinary-control timing. These limitations are clearly acknowledged by the authors and should constrain the paper’s claims rather than count as undisclosed flaws.

## Comment

I recommend borderline acceptance at most. The paper’s strongest defensible contribution is a carefully measured observation that an additional failure- or conflict-triggered pass can improve a realized direct baseline under specific whole-file regimes. The most important issue is to narrow the headline contribution accordingly and provide stronger prospective, compute-matched, and new-task evidence before claiming a general bounded-verification principle or attributing gains to support counts and structured repair operations.

### Panel review 3 — scope_ablation (accepted)

# Review: Mini Artichokes: Bounded Verification for Selective LLM Arbitration and Program Repair

## Summary

This paper proposes a conservative inference-time framework that freezes an initial state, invokes a separate decision or repair stage only after observable disagreement or failure, restricts updates, and preserves unaffected work. It evaluates selective arbitration on a 1,000-question MMLU-Pro replication and bounded repair on five repeated sessions of a fixed 20-task Java benchmark. The results show a modest gain over a direct baseline, but the evidence does not establish that support metadata, explicit structured operations, or the broader “Mini Artichokes” mechanism is responsible for the gains.

## Strengths

- The paper makes a clear distinction between end-to-end performance and mechanism attribution: “The experiments revise the original mechanistic intuition. Agreement is useful for routing on MMLU-Pro, and a feedback-bound second pass is useful on the Aider subsets; neither support annotation nor strict overlap authorization beats its compute-matched generic control.”

- The arbitration protocol is operationally precise and conservative. In particular, “if the judge returns exactly C1 or C2: return the corresponding existing answer,” while invalid or nonconforming judge outputs retain the base answer.

- The MMLU-Pro replication is reported on the full denominator, with paired rescues and harms. OJ3 achieved “28 rescues, 5 harms, +23 correct,” yielding 613/1,000 versus 590/1,000 for D1.

- The paper uses strong controls rather than presenting agreement as proof. OJ3 “tied SC3 at 613/1,000” and had only a descriptive “+2 point estimate over GJ3,” which appropriately limits the mechanistic claim.

- The authors are unusually candid about negative and null evidence. For example, the legal reserve produced “30 rescues but 59 harms, a net loss of 29,” and the later ordinary-repair control scored 27/100 versus 25/100 for structured repair.

- The coding evaluation correctly treats five whole-batch sessions as the inferential units rather than pretending that the 100 repeated task-session outcomes are independent. The paper explicitly states that “the inferential result is five positive whole-session differences on one fixed official task set.”

- The limitations are substantial and generally well integrated into the interpretation, including the anomalous D2 session, same-model dependence, approximate compute matching, fixed-task coding evaluation, and post hoc status of the ordinary control.

## Weaknesses

- The central support-aware arbitration claim is not supported against its most relevant compute-matched control. Although OJ3 significantly beat D1 in replication 2, it “tied SC3 at 613/1,000” and did not significantly beat GJ3, with only “5 rescues, 3 harms” and `p=.36328`. Thus the evidence supports additional sampling plus judgment, not the support-aware mechanism itself.

- The proposed common principle is broader than the evidence. The MMLU-Pro study concerns discrete answer selection, while the coding study concerns hidden-test repair on “one fixed official task set.” The paper itself concedes that the coding result establishes “session repeatability on that fixed set, not new-task generality.” The conceptual unification is plausible, but cross-regime generality is not empirically demonstrated.

- The strongest coding mechanism control was commissioned after the structured-repair outcomes were known. The paper acknowledges that “the arm was commissioned after the matched outcomes were known,” and the result favored ordinary repair: matched-minus-ordinary mean `-2` points with interval `[-7,+2]`. This is useful negative evidence, but it cannot provide an unbiased confirmatory test of the explicit structured operations.

- The coding replication has very low effective task diversity. All five sessions reuse the same 20 Java tasks, and the paper notes that the cross-language study has “only three whole-batch call clusters.” Five favorable session signs establish repeatability under this narrow setup, but they provide limited evidence for robustness across tasks, languages, prompts, or repositories.

- The practical value of the MMLU-Pro improvement is uncertain given the resource cost. OJ3 uses “45,973,780 tokens versus 13,009,321 for D1,” a 3.53-fold ratio, for a 2.3-point replication gain. The paper reports this honestly, but does not analyze quality per unit cost or compare against cheaper alternatives such as fewer samples or adaptive early stopping.

- The anomalous D2 session raises unresolved concerns about whole-file execution. D2 scored only “145/1,000” in confirmation 1, and the authors state that its “semantic cause remains unresolved.” The integrity checks rule out several mechanical explanations, but without repeated same-item runs it remains unclear how much of the observed arbitration behavior depends on unstable batch-level trajectories.

- The trigger is sufficiently rare that its mechanism effect is weakly estimated. Only “68/2,000 questions triggered arbitration,” and the OJ3-versus-GJ3 comparison is based on only 13 differing decisions. The paper appropriately calls this unresolved, but this leaves the most distinctive part of the method underpowered.

- The explicit bounded-update components in program repair are not individually identified. The matched arm bundles “failure feedback, counterexamples, preservation, and a double completion audit,” while the paper admits that there is “no accuracy evidence for the explicit structured bundle, any individual component, or an overlap-specific effect.” Consequently, the demonstrated contribution is closer to adding a second failure-feedback call than to validating the named structured repair design.

## Questions for the Authors

1. Can you provide the exact prompts and per-session outputs for the ordinary-repair control, and explain whether its shorter instruction had any information or formatting advantage relative to matched repair?

2. What happens when OJ3 is compared with GJ3 using a substantially larger number of eligible conflicts, or on repeated runs over the same questions? The current result rests on only “68/2,000” triggered cases and “5 rescues, 3 harms” where the judges differed.

3. How sensitive are the coding results to task selection? In particular, can you evaluate the same repair policies on a newly frozen set of Java tasks or another repository without changing prompts or selecting the set after observing outcomes?

4. What is the intended contribution of the “bounded-update contract” beyond the empirically supported claim that a separate failure-feedback repair call can help? Which aspects of the contract are necessary, and which are merely compatible design choices?

5. Can you report quality-cost curves for one, two, and three auxiliary calls, including latency and monetary cost, rather than only the aggregate “3.53-fold ratio” for OJ3?

## Scores

Soundness: 3/4 — The experiments and caveats are carefully reported, but the main mechanistic and generalization claims remain weakly identified.

Presentation: 4/4 — The paper is unusually clear, well organized, and explicit about confirmatory versus descriptive evidence.

Significance: 2/4 — The observed gains are modest and narrow, with no demonstrated superiority to the strongest matched controls.

Originality: 3/4 — The bounded-update framing and explicit rescue/harm accounting are useful, although the underlying ingredients are familiar.

Overall recommendation: 3/6 — Borderline: technically careful and informative, but not yet sufficiently strong or general for clear acceptance.

Confidence: 4/5 — The paper is self-contained and its claims are traceable, though the underlying artifacts and execution behavior cannot be independently verified here.

## Ethics and Limitations

The paper appropriately discusses increased inference cost, reporting “45.97 million tokens across the two OJ3 cohorts,” and warns against deploying same-model agreement in high-stakes settings after the negative legal result. The legal data governance discussion is also responsible: the authors state that facts may remain re-identifiable and therefore withhold item texts and outputs. The principal scientific limitations are the single model and runtime, whole-file session dependence, same-model correlated errors, rare arbitration triggers, fixed-task Java replication, lack of component ablations, and post hoc ordinary-repair control. These limitations materially constrain the scope of the conclusions but are generally acknowledged by the authors.

## Comment

I recommend borderline acceptance at most. The paper’s strongest contribution is a careful empirical demonstration that selective judgment can improve a realized direct baseline and that a second pass using hidden-test feedback can help on a fixed coding set. However, the evidence does not show that support-aware arbitration beats a generic judge, that the structured repair bundle beats ordinary repair, or that the unified principle generalizes beyond these narrow settings. The most important revision would be a genuinely preplanned, compute-matched evaluation on newly frozen tasks that isolates the claimed bounded-update components from the generic benefit of simply making another evidence-informed call.
