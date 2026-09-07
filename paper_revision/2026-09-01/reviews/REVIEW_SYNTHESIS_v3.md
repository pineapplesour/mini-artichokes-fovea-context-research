# Review-agent synthesis for the official-benchmark revision

## Inputs

- Last successful evidence-bound Review Court report: `review_court_v2.md`.
- Current deterministic MAC ledger audit: `mac_v2_ledger_deterministic.md`.
- Current manuscript: `Mini_Artichokes_manuscript_v3.md`.
- Frozen official Aider evidence: `../evidence/aider_hidden_results.json`, SHA-256 `0c618e58ab5720e1044da799193325a5018c27e911179ed75048351af72461c1`.
- Frozen official LEET development screen: `../evidence/reasoning_method_screen.json`.

## Review execution record

The previous Review Court run completed and scored the pre-coding-transfer
paper 3/6, with soundness 2/4, presentation 3/4, significance 2/4, and
originality 3/4. Its central scientific criticisms were: no established gain
over SC3/GJ3, one judge session per arm, a small MMLU-Pro effect relative to
compute, an unisolated legal boundary, and no identical-item session
repeatability.

Two bounded Review Court attempts on the new PDF terminated before producing a
review with `SPECIALIST_PROVIDER_INVALID_OUTPUT`. Their terminal checkpoints
are preserved under `review_court_v3_runtime/` and
`review_court_v3b_runtime/`. This is a provider/schema infrastructure failure,
not a paper verdict; no score from either attempt is reported.

The deterministic MAC run successfully verified and froze the current evidence
bundle. Its 1/6 paper score is not treated as a scientific review because the
tool enforced Ralphthon-event-only sections (`Research Spec`, `Self-Review`,
and `Short Paper`) on an ordinary manuscript and its baseline-fairness pass
pooled distinct experiments in one JSONL ledger. The resulting contradictions
are structural false positives. Its evidence-identity and claim-trace receipts
remain useful.

## Actionable findings and disposition

| Review finding | Disposition in the new manuscript |
|---|---|
| Breadth limited to one multiple-choice benchmark | Added an exploratory transfer on 40 disjoint tasks from the official Aider Polyglot benchmark, with hidden official tests and gold. |
| MMLU-Pro gain is only +1.35 points at 3.53x tokens | Retained without inflation; added the larger +20-point coding system result and full coding latency/token costs. |
| OJ3 does not establish superiority over SC3 or GJ3 | Retained as an explicit null mechanism-control result in the abstract, claim hierarchy, results, discussion, limitations, and conclusion. |
| One judge session cannot identify the support-record treatment | Retained as a limitation; no causal support-count claim is made. |
| Coding gain could be a second repair call rather than overlap | Added an ordinary same-budget repair control. It scores 21/40 versus 22/40 for the proposal, so overlap-specific superiority is explicitly rejected. |
| Task-level significance may overstate independence | The abstract, design, results, discussion, claim hierarchy, and limitations now state that each 20-task batch shares one call and only two call clusters exist per arm. |
| Negative legal result does not isolate its cause | Retained as a boundary result only; no predictive causal explanation is claimed. |
| Readers may conflate system and mechanism effects | Added a claim hierarchy separating confirmatory system evidence, exploratory system evidence, compute-matched mechanism controls, and the negative boundary. |

## Final claim boundary

The paper can support two end-to-end claims: the frozen OJ3 system improved the
preassigned direct realization on two disjoint MMLU-Pro cohorts, and the
exploratory two-call coding system improved the realized Plain baseline on the
40-task official Aider subset. It cannot support that overlap metadata itself
beats strong compute-matched controls, that the coding result is a full Aider
leaderboard result, or that task-level significance generalizes across model
calls. Those distinctions are now made explicit wherever the headline results
appear.
