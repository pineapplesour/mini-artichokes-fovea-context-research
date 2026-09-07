# Native paired-boundary probe: ClassEval-Pro development

Status: approved development design; dry-run is the default.  No result is a
scientific claim until the complete frozen inventory and both arms finish.

## Question

With the same 300-task ordinary prefix and the same full canonical A/B inputs,
does an actively paired boundary-probe policy (O) improve repair over a strong
generic native critic/refine policy (G), at the same per-task candidate and
solver-session limits?  This is a policy comparison: adaptive probes may differ
between arms, so it is not a claim of identical trajectories or a token-matched
causal intervention.

## Fixed inputs and arms

- Dataset: official ClassEval-Pro, all 300 task IDs in source order.  The
  ordinary prefix is immutable and must be terminal full-300 with 268 passed
  tasks and U32 unresolved tasks.
- For every unresolved task, validate the frozen E A/B receipts and prompts,
  canonicalize/evaluate those two complete sources exactly once per task, and
  reuse the resulting full (unprojected) A/B views in both arms.  Passing-prefix
  tasks are stopped and remain in the denominator.
- Each arm makes one fresh Luna `gpt-5.6-luna`, medium, 120-second Codex
  session per unresolved task (64 fresh solver sessions total).  A session may
  contain multiple tool/model turns; actual command count, turn usage, tokens,
  duration, and API-request count (or `unknown`) are recorded separately.
- O must attempt at least two actual adaptive probe scripts on both A and B
  through the staged helper, using the same probe bytes and fresh helper
  processes and targeting the static shared boundary S/shared invariant.  G
  receives the identical source, feedback, helper, time, and tool opportunity,
  but has no paired-probe obligation and follows a strong generic repair policy.
  Probe noncompliance is recorded and does not remove a task from the
  denominator.  Empty-S/small-n plans use the common E-style fallback.

## Information, filesystem, and evaluation boundary

Prompts contain only the skeleton, ordinary source, complete canonical A/B,
bounded observed evaluator feedback, and static scope metadata.  Gold/reference
solutions and raw test source are never serialized.  The model can write only
inside its isolated workspace; only a regular `solution.py` is submitted,
while ordinary scratch files are non-submitted.  Network, unapproved host
credentials, approval prompts, plugins, and host paths are disabled by the
native isolated profile; the explicitly bound native helper is the only extra
runtime capability.  The read-only staged `/opt/paired/` contains
`paired_probe.py`, `context.json`, `a.py`, and `b.py`; only trusted
`command_execution` events invoking the fixed helper path with the default
context and valid helper JSON can establish probe compliance.  A model ledger
or prose assertion is not evidence.

For each valid C file, persist its raw evaluator report and then its AST-
canonical full evaluation report.  Selection uses only the common frozen
selector over prefix, full A, full B, and canonical C; raw reports cannot win.
Invalid, parse-error, timeout, or unexpected-exception calls remain recorded in
the same denominator and are never retried.  Unexpected runner/evaluator
exceptions terminate the run as `incomplete` with an error record.

## Accounting and gate

Report shared canonical A/B evaluations once per task (64 total), fresh raw C
and canonical C evaluations separately, and per-arm logical/evaluator totals;
the common suite cap is six evaluations per arm.  Do not equate solver sessions
with API requests or claim equal realized tokens/latency.  Report ordered full
results, prompt/source/helper/config hashes, receipts, call paths, probe hashes,
and scope/visited-method provenance.

The predeclared development advancement condition is O net at least four wins
over G and O net at least four over the old full-300 LL_E reference (278
passes).  Report paired exact two-sided McNemar tests with Holm correction over
the two comparisons, but do not turn this gate into a significance or SOTA
claim.  The old LL_E reference is not tool-matched; an independent fresh
replication is required before any broader conclusion.
