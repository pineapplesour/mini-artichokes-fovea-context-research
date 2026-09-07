# Official Aider hidden-test confirmation and replication

Date: 2026-09-02 KST

## Outcome

On 40 disjoint official tasks from `Aider-AI/polyglot-benchmark`, the complete
Graph → overlap/KIRA-style repair system solved **22/40 (55%)**, compared with
**14/40 (35%)** for one-call Plain Luna: **+8 tasks / +20 percentage points**.
The paired changes were 10 rescues and 2 harms. The exact McNemar result is
one-sided `p = 0.019287` and two-sided `p = 0.038574`; the fixed-seed task-level
paired bootstrap 95% interval is `[+5, +35]` percentage points.

This supports a paired advantage over Plain Luna on these frozen official
tasks. It is not a full 225-task Aider leaderboard result, and the two 20-task
batches provide only two independent model-call clusters per arm.

## Authority and freeze

- Official repository: <https://github.com/Aider-AI/polyglot-benchmark>
- Source commit: `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`
- Confirmation: deterministic 10 unseen Python + 10 Rust selection; freeze
  SHA-256 `aa21718408670a2367687c42be538d1766ad74e222e61d726b54f1c13cdaa3e9`.
- Replication: every one of the 20 official Rust exercises not present in the
  confirmation batch, selected before model calls; freeze SHA-256
  `b3634fb1f3e424f77112996e877adc379af9ce9901c270c855b13f49d7d6ec7e`.
- The two task-ID sets are disjoint. Gold `.meta/example.*` implementations
  were removed everywhere. Official tests were retained only in the private
  evaluator and masked from the agent with Bubblewrap.
- The untouched starter state scored 0/20 in both batches. All accepted arms
  completed normally and changed only official solution paths.

The Rust-only replication corrected one language-specific packaging sentence:
confirmation Rust tasks inherited a generic clause saying “Python standard
library,” whereas replication tasks correctly said Rust standard library and
existing declared dependencies. Every arm within a batch received identical
task bytes, and the Graph/repair method prompts were unchanged, but the two
batches are not byte-identical protocol replications.

The machine-readable task outcomes, hashes, usage, paired comparisons, and
limitations are in `results.json` in this directory.

## Arms

- **Plain**: one Luna/medium call solves all 20 tasks directly.
- **Graph**: one Luna/medium call builds requirement, implementation, edge-case,
  invariant, and counterexample relations before editing.
- **Ordinary repair**: a second Luna/medium call starts from the exact Graph
  patch and receives the exact official failure stdout, but not test source.
- **Graph-overlap repair (proposal)**: the same second-call budget and evidence
  as ordinary repair, with three-view obligation overlap, general-counterexample
  repair, passing-task preservation, and a KIRA-inspired double completion
  audit against the original instructions.

These are budgeted prompt-level realizations. They are not claims of reproducing
the full original Graph-of-Thought or KIRA implementations.

## Results by frozen batch

| Batch | Plain | Graph | Ordinary repair | Proposal | Proposal − Plain |
| --- | ---: | ---: | ---: | ---: | ---: |
| Confirmation (10 Python + 10 Rust) | 8/20 (40%) | 5/20 (25%) | 12/20 (60%) | 13/20 (65%) | +25 pp |
| Disjoint Rust replication | 6/20 (30%) | 6/20 (30%) | 9/20 (45%) | 9/20 (45%) | +15 pp |
| **Pooled** | **14/40 (35%)** | **11/40 (27.5%)** | **21/40 (52.5%)** | **22/40 (55%)** | **+20 pp** |

The direction of the proposal-versus-Plain effect replicated in the disjoint
batch, although the replication batch alone is not significant (`4` rescues,
`1` harm; two-sided exact `p = 0.375`).

## Paired pooled comparisons

| Comparison | Rescues | Harms | Difference | Exact McNemar p (one/two-sided) | Task bootstrap 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: |
| Proposal vs Plain | 10 | 2 | +20 pp | 0.019287 / 0.038574 | [+5, +35] pp |
| Proposal vs Graph | 11 | 0 | +27.5 pp | 0.000488 / 0.000977 | [+15, +42.5] pp |
| Proposal vs ordinary repair | 3 | 2 | +2.5 pp | 0.5 / 1.0 | [−7.5, +12.5] pp |

The proposal therefore establishes an end-to-end advantage over Plain and
Graph on this sample, but **does not establish that its structured repair is
better than an ordinary same-budget repair**. The latter control explains most
of the gain and must remain visible in the paper.

## Efficiency

| Batch / path | Calls | Agent time | Input tokens | Output tokens |
| --- | ---: | ---: | ---: | ---: |
| Confirmation Plain | 1 | 315.945 s | 541,362 | 14,300 |
| Confirmation Graph + ordinary | 2 | 768.443 s | 2,163,137 | 35,137 |
| Confirmation Graph + proposal | 2 | 790.954 s | 2,401,902 | 36,142 |
| Replication Plain | 1 | 482.176 s | 1,707,134 | 21,790 |
| Replication Graph + ordinary | 2 | 805.642 s | 2,721,842 | 35,864 |
| Replication Graph + proposal | 2 | 867.156 s | 2,756,476 | 38,703 |

Input token counts include cached input as reported by Codex. The proposal is
materially slower and more token-intensive than Plain; this is a real tradeoff,
not an infrastructure contribution.

## Statistical boundary

The exact test and bootstrap treat official tasks as paired observations.
Because all 20 tasks in a batch share one solver call, outcomes can be dependent
within a batch. Forty task rows are not forty independent model invocations.
The two disjoint batch replications reduce selection risk but do not support a
cluster-robust population claim. A later paper-strength extension should add
more independently frozen batches or repeated calls without selecting favorable
runs.

Two invalid preparatory campaigns are excluded by contract rather than score.
One was stopped before any model call after two unlisted Rust test files were
found in the public workspace. In the next, a single Plain call exposed a
generator contradiction that both allowed and forbade an official solution
`Cargo.toml`; it was marked unsafe, no competing arm was run, and the entire
campaign was archived before v2. The accepted v2 contract has zero
allowed/forbidden-path intersections. These excluded outputs are not present in
`results.json`.

## Reproduce scoring

```bash
python -m tools.score_aider_hidden_campaigns \
  --confirmation runs/aider-hidden-py10-rust10-luna-medium-20260902-v1 \
  --replication runs/aider-hidden-rust20-replication-luna-medium-20260902-v2 \
  --output benchmark_reports/2026-09-02-aider-hidden-official/results.json
```
