# Java47 independent-probe development: primary comparison

The complete official Java track was evaluated: all47 pinned task IDs, with no
post-result task removal. This is exposed-task development, not untouched-task
confirmation. The protocol and pre-score ID-only amendment are in
`experiment_protocols/2026-09-05-java47-independent-probe-overlap-v1.md` and
`experiment_protocols/2026-09-05-java47-probe-prescore-id-amendment.md`.

## Completed five-execution comparison

Both systems share Plain, Graph, ordinary repair, and the same independently
authored but fallible probe packet. Each adds one final repair execution. The
author counts as compute, so each system has five agent executions but four
implementation candidates. All new calls use Luna/medium with a900-second cap.
This equalizes the allowance, not realized tokens or latency.

| Final repair policy | Final candidate | Materialized system | Total agent seconds | Total output tokens |
|---|---:|---:|---:|---:|
| General repair A | 11/47 | 12/47 | 2720.405 | 106065 |
| Executable semantic overlap | 12/47 | 13/47 | 2367.432 | 96885 |

The shared three-implementation floor is11/47. The system contrast is therefore
**+1/47 = +2.13 percentage points**, with two rescues (`pov`, `rest-api`) and one
harm (`custom-set`) relative to the generic system. The conditional exact
McNemar p-values are one-sided.5 and two-sided1.0. This is a small realized lead,
not statistically supported superiority. All47 rows share whole-track calls;
the task-conditional test does not create47 independent model sessions.

Both materialized systems were re-evaluated on the full official test suite;
their vectors exactly match their declared task-wise unions. Final executions
ended normally, retained safe source paths and all47 ledger IDs, and left the
shared evidence unchanged. Seed, evidence, task inventory, model settings and
agent caps match. Agent times sum model/agent execution only, excluding official
evaluation and therefore are not end-to-end latency. The overlap final took
545.156seconds; generic A took898.129seconds. Less observed compute in this one
overlap draw is descriptive, not a repeated efficiency result.

## Mechanism audit and next comparison

The overlap trace really executed the probe replay, but not every rescue has
probe-overlap support: `rest-api` had no useful executable probe and was repaired
through source/specification inspection. Conversely, the generic route fixed
the reversed subset relation in `custom-set`, where the overlap route retained
a probe-passing yet officially failing state. One simple auxiliary example is
therefore not a sufficient completion criterion. See `PRESCORE_DIAGNOSTIC.md`
for the separately retained probe-quality audit; it was not supplied to either
repair agent.

A different, six-execution sibling portfolio comparison was frozen before
reading the overlap score and before either generic result. It was to compare
Generic-A+Overlap with Generic-A+Generic-B on the identical shared prefix.
Generic B was a fresh draw from the unchanged generic prompt, seed and evidence,
not a replacement for A. Each planned system has six agent executions and five
implementation candidates.

**That sibling comparison did not yield a valid primary result.** Generic B
ended normally in711.787seconds and its unfiltered candidate passed12/47, but
it added a no-argument constructor to
`tasks/java/bank-account/src/main/java/BankAccountActionInvalidException.java`.
The task explicitly permits edits only to `BankAccount.java`. The guard
therefore correctly rejected B for a source-scope violation before terminal
system materialization. The modification was not a test edit; nevertheless it
violates the frozen source contract. Its raw score is diagnostic, not an
eligible system score. The original candidate and added constructor are
preserved; no post-score file repair, replacement B draw, zero imputation or
relaxed primary analysis was performed. The queued portfolio analyzer stopped
because the required valid B report was absent. No six-execution superiority
claim is made. This does not invalidate the completed five-execution contrast.

## Exact artifacts

- Run root: `runs/aider-java47-tov-development-20260902`.
- Complete primary reports: `arms/probe_v1_overlap/system-result.json` and
  `arms/probe_v1_generic/system-result.json` under that root.
- Original attempts, prompts, input hashes, ledgers and actual execution traces
  remain under their respective arm directories.
- Sibling protocol: `experiment_protocols/2026-09-05-java47-probe-portfolio-v1.md`.
- Sibling materialization/analysis (stopped at the input gate):
  `tools/analyze_aider_probe_portfolio.py`.
- The subsequent, zero-new-model-call diagnostic of existing P/G/R test-case
  coverage is under `diagnostics/partial-repairs-v1` in the same run root. It
  does not modify or replace this experiment.

The latest valid final manuscript committee review remains v25 MAC3/6. This
development comparison has not yet been inserted into a rebuilt or reviewed
paper and does not by itself meet the active research goal.
