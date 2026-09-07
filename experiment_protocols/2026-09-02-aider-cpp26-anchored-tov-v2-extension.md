# Frozen extension protocol: Aider C++26 anchored TOV v2

Status: frozen before the first C++26 model call, after Rust30 development and
Python34 confirmation were complete.

## Purpose

Run the unchanged anchored TOV-v2 policy on a third disjoint complete official
language track. Rust30 and Python34 each showed exactly two TOV rescues and no
harms versus their matched generic verified-union adjudicator. Their cumulative
matched comparison is 4:0 (`p=.0625`, one-sided). One additional rescue with no
harm on a disjoint complete track would make the cumulative exact directional
test significant at .05; the standalone C++ effect and p-value remain required.

## Complete benchmark and freeze

- Official source: `Aider-AI/polyglot-benchmark`, commit
  `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`.
- Benchmark: all 26 official C++ exercises in lexicographic order. No task is
  selected, excluded, replaced, or topped up.
- Starter code passes 0/26 complete official build-and-test commands.
- Agent workspaces exclude `.meta`, `.approaches`, configured test files, and
  the conventional Catch test support directory. The private evaluator
  restores those frozen official files and uses CMake with
  `EXERCISM_RUN_ALL_TESTS=1`; the build target executes the tests.
- Freeze SHA-256:
  `a3feff3bc378bf453c4f11d65221a9761c54b50333364350d0b9ca00da1e2e08`.
- Public task SHA-256:
  `6febe691e7074c0a3ba31d49494b81907bc9f09957e0ac8ab68335cd9140b5b8`.
- Manifest SHA-256:
  `0b87459f5caf5b45d2154b69bd0d53b8d939f19346c0c2a071c4e581c27dddc5`.
- Evaluator SHA-256:
  `b1fa651a691227aca149e955bc044365572f39eee8690673ad272179544e2bc9`.
- Unchanged v2 runner SHA-256:
  `b9336d6a8503b0c41f9303a3241b0cc039f9c387c9ca1060484e15f37cb2fb93`.

## Exact unchanged policy

Use `gpt-5.6-luna`, medium reasoning, web disabled,
`CODEX_HOME=/home/pineapple/.codex-new-account`, and one complete-track call
per arm. Agent and evaluation caps are each 30 minutes.

Exactly five calls are allowed: Plain, Graph, ordinary Graph-feedback repair,
generic verified-union adjudication, and semantic-overlap verified-union
adjudication. The verified candidate priority, byte restoration, evidence
packet, semantic fields, unresolved-only ledger, disagreement-triggered
falsification, and two completion audits are unchanged. There are no retries,
per-task calls, task top-ups, or result-led prompt changes.

## Frozen analysis

Report full 26-task vectors, rescues, harms, paired exact tests, paired
bootstrap intervals, runtime, calls, and tokens. The extension succeeds if:

- TOV beats Plain by at least 6/26 tasks (+23.1 points), with one-sided exact
  `p<.05`;
- TOV has more rescues than harms versus ordinary repair;
- TOV beats matched generic verified-union adjudication by at least 2/26 tasks
  (+7.7 points), with more rescues than harms;
- all anchor bytes, ledger IDs/order, and allowed-path checks pass.

Independently of the two-task extension threshold, report the pre-specified
cumulative matched exact test over all disjoint complete Rust30, Python34, and
C++26 rows. The first two tracks contribute four rescues and zero harms before
the C++ result. Label the three-track analysis cumulative because Rust30 was
developmental and C++26 is an extension, not a second pure confirmation.

Benchmark packaging and evaluation are provenance only. The scientific object
is the unchanged anchored TOV mechanism.
