# Shared-failure repair: completion-reserved, maximum-five-pair replication

Fixed before every new execution in this study. This follows result-informed
Java47 development; it is not an untouched-benchmark evaluation.

## Development result and unchanged eligibility boundary

The v1 generic arm completed normally: candidate12/47, verified system14/47.
The overlap arm reached900.008seconds and was timed out. Its persisted candidate
passed18/47 under the full official evaluator, with safe source scope, unchanged
input evidence and a complete47-row ledger. Nonetheless it did not meet v1's
normal-completion gate, has no eligible v1 system report, and lacks final CLI
token-usage telemetry. The original v1 paired primary is therefore unavailable.
The18/47 result is retained as developmental evidence, not a clean win or a new
review score. No old source, gate, duration, or completion flag is changed.

## Fresh calls and common time management

Use the same shared-failure policy, unrestricted generic policy, original R
seed, P/G/R public sources, full test-case feedback, derived overlap fields,
model/account/runtime and all47 official tasks as v1. The policies themselves
are unchanged. Both receive the SAME additional time-management rule:

- Hard agent cap remains900seconds; it is not extended.
- Finish substantive editing by720seconds after the approximate start, reserving
 180seconds for final checks, complete ledger and completion.
- Target the final response by840seconds. Supply the approximate start and
  deadlines as UTC epoch values; permit checking `date +%s`. Actual epochs
  necessarily differ between executions and are recorded separately from the
  stable prompt template.
- Normal completion, exact47-task inventory, allowed source paths, unchanged
  evidence, complete ledger and materialized full-suite re-evaluation remain
  required. Neither scope nor score criteria are relaxed to admit the v1 timeout.

Each system still has four logical agent executions: the fixed shared P/G/R
prefix plus one fresh final repair. The additional probe author and all previous
final repair artifacts remain excluded. There are at most TEN new model calls,
not ten independently regenerated prefixes. Report physical study calls and
logical per-system calls separately.

## Five pair slots and a conservative futility gate

IDs: `shared_failure_v2_b{1..5}_{generic|overlap}`. Call order was fixed using
five independent choice draws from `random.Random(20260905)`:

1. overlap, generic;
2. generic, overlap;
3. overlap, generic;
4. overlap, generic;
5. generic, overlap.

Finish both frozen calls of pair1. If either arm is ineligible, stop before
additional pairs and report the invalid pair without replacement. If both are
eligible but the overlap system's net lead is less than4/47 tasks, stop for
futility. Such a stop makes NO superiority or equivalence declaration. It does
not justify reclassifying a development result as a confirmed effect.

If the eligibility and practical-lead gates pass, run all remaining FOUR pairs
unchanged, including any later negative/tied result. If a later pair is invalid,
finish that pair and stop; no five-pair primary conclusion is available. Never
replace an arm or stop early to declare success. All attempts and partial study
results remain in the artifact.

## Fixed endpoints

Primary effect: mean overlap-minus-generic system task-pass difference across
the five valid pairs. Primary directional test: exact within-pair label-swap
test of the summed task-pass differences across all32 sign assignments, including
ties, one-sided alpha.05, conditional on paired exchangeability and the fixed
prefix/tasks/model setting. The first-pair gate permits futility only, never
early rejection; success requires the full five-pair test. This conservative
gate does not expand the rejection event beyond the fixed full-study test.

Also report every pair, candidate scores, paired task rescues/harms, actual
tokens and agent time. Five pairs on47 tasks are not235 independent tasks or
five regenerated complete pipelines. Do not claim generalization across models
or new tasks. The prefix-based error strata remain descriptive and do not change
the primary denominator or significance threshold. Another complete official
track is required before a cross-track promotion claim.

Driver: `tools/run_shared_failure_replication.py`.
Execution helper: `tools/run_aider_shared_failure_overlap.py` with
`--completion-reserve-seconds 180` and unique candidate IDs.
