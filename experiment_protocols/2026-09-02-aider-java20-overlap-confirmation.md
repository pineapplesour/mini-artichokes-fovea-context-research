# Frozen protocol: Aider Java20 overlap-repair confirmation

Status: frozen before model calls and before private-test scoring.

## Question

On a new official hidden-test coding subset, does a two-call Graph-plus-repair
system beat direct Luna and Graph alone, and does an explicit evidence-overlap
authorization rule add accuracy beyond a matched structured repair?

## Benchmark and selection

- Source: `Aider-AI/polyglot-benchmark`, pinned local official checkout.
- Population: all 47 Java exercises in the pinned checkout.
- Sample: the 20 lowest SHA-256 ranks of
  `mini-artichokes-aider-hidden-java20-v1-20260902 + NUL + java/exercise`.
- No task may be removed or replaced after any model call or score.
- Gold `.meta` material and all `src/test` content are absent from every model
  workspace. Untouched official tests exist only in the private evaluator.
- In its temporary private copy, the evaluator removes only Exercism's
  progressive-unlock `@Disabled` annotations so that every supplied official
  assertion runs; test bodies and expected values are unchanged.

## Arms

All calls use `gpt-5.6-luna`, medium reasoning, one whole-batch call per arm,
and identical public task material.

1. `plain`: direct implementation from the official instructions.
2. `graph`: requirements, implementation choices, edge cases, invariants,
   dependency relations, and attempted counterexamples before editing.
3. `matched_repair`: starts from the frozen Graph patch and exact private-test
   stdout; uses requirement reconstruction, minimal counterexamples, bounded
   edits, and a KIRA-inspired double completion audit.
4. `overlap_repair_v2`: identical budget and the same structured repair
   operations, but explicitly records which of specification, implementation,
   and observed test evidence supports each defect and authorizes a change only
   when at least two views converge on the same unmet obligation.

The two repair arms receive the same Graph seed patch and exact failure output.
They are separate complete-file Luna sessions. Neither can read tests or gold.

## Outcomes and claims

- Primary end-to-end comparison: `overlap_repair_v2` versus `plain` on all 20
  tasks, reporting correct totals, paired rescues/harms, exact McNemar p-values,
  and a paired task bootstrap interval.
- Strong controls: versus `graph` and versus `matched_repair`.
- A system-level gain may be claimed only for contrasts that actually pass.
- An overlap-specific gain may be claimed only if the matched repair contrast
  supports it. A tie or loss must be reported as such.
- Task-level inference is conditional on one realized whole-batch call per arm;
  it is not between-session or cluster-robust population evidence.
- Calls, tokens, elapsed time, unmapped/unsafe outputs, and all 20 task outcomes
  remain in the report. Infrastructure is provenance, not a contribution.

## Stopping rule

Exactly these four arms are allowed. No answer-led rerun, task deletion, prompt
revision, alternative seed, or fifth arm is permitted for this frozen sample.
