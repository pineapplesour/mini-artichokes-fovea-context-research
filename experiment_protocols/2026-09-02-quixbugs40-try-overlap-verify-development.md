# QuixBugs-40 Try–Overlap–Verify development protocol

Status: development protocol frozen before the first full-suite candidate call.

## Scientific question

Can semantic overlap across independently generated repairs and their observed
test behavior make candidate verification materially better than (a) one
whole-suite Luna repair, (b) deterministic majority/self-consistency, and (c)
a compute-matched generic candidate adjudicator?

This is a performance study. Repository preparation, isolation, and scoring
are evidence controls and are not scientific contributions.

## Complete benchmark denominator

- Official source: `jkoppel/QuixBugs`.
- Frozen commit: `4257f44b0ff1181dedaedee6a447e133219fcebf`.
- Development denominator: all 40 Python programs named by the 40 official
  `python_testcases/test_*.py` files.
- No program may be excluded, replaced, or selected after observing results.
- A program passes only if its complete official pytest file passes. Timeouts
  and malformed patches count as failures.
- Correct Python implementations and every gold/correct-program directory are
  unavailable to model calls. Official buggy programs and public tests are
  visible, as specified by QuixBugs.

QuixBugs is used for mechanism development because it is a complete, small APR
suite with one buggy program and executable tests per task. Its known
single-line structure and public age limit external-validity claims.

## Candidate generation shared by both selectors

Create exactly three independently initialized whole-suite drafts, `D1`, `D2`,
and `D3`:

- Model: `gpt-5.6-luna`.
- Reasoning effort: `medium`.
- Codex home: `/home/pineapple/.codex-new-account`.
- Each call receives the identical complete 40-program repository and the same
  instruction to repair every program, run all official tests, preserve helper
  and test files, and stop only at the fixed timeout.
- Candidate calls cannot see one another.
- `D1` is the preassigned one-call Plain reference. `D2` and `D3` are not
  replacements or top-ups; all three individual scores are reported.

For each draft, freeze its patch, changed-file list, full test result, and
per-program failure stdout before either selector runs.

## Baselines

1. **Plain (`D1`)**: the preassigned first complete-suite repair call.
2. **SC3/majority**: per program, normalize the three candidate diffs; a
   two-of-three identical semantic edit wins. A tie falls back to `D1`. This
   selector uses no gold or tests.
3. **Generic adjudication**: one new Luna/medium call receives the original
   program, the three candidate patches, and the three frozen test outcomes
   for every program. It may choose or synthesize a repair but receives no
   overlap schema. It must output all 40 repairs.

## Proposed treatment: Try–Overlap–Verify (TOV)

TOV uses the same `D1`–`D3` candidates, identical original programs, identical
test evidence, one Luna/medium selector call, and the same timeout as generic
adjudication. Its only treatment difference is a mandatory per-program
overlap-and-falsification ledger.

For each of all 40 programs, the selector must record internally and use:

1. the static obligation suggested by the specification and buggy code;
2. the dynamic obligation exposed by candidate test failures or passes;
3. the defect location, violated invariant, counterexample class, and edit
   intent recurring across at least two independent candidates;
4. any disagreement or correlated failure shared by candidates;
5. one falsification attempt against the leading repair;
6. the final choose/synthesize/preserve decision.

Semantic overlap is a confidence and routing signal, not an exact-line edit
restriction. If candidates agree on a defective invariant but express
different patches, the selector may synthesize a new patch. If candidate
agreement conflicts with test evidence, test evidence wins. A task already
passing in a candidate is not changed without a concrete counterexample.

The final completion check is KIRA-inspired but task-facing: verify every
original requirement, rerun every official test, inspect the final patch for
scope regressions, and repeat the check once before finishing. Tool protocol,
polling, or harness behavior is not part of the treatment claim.

## Development decision rule

The mechanism is promising only if, over all 40 programs:

- TOV exceeds the preassigned Plain `D1` by at least 8 programs (`+20%p`);
- TOV exceeds generic adjudication by at least 4 programs (`+10%p`); and
- TOV has more paired rescues than harms against both comparators.

All scores, paired rescue/harm tables, exact McNemar tests, and bootstrap
intervals are reported even if these thresholds are missed. No subset-only
positive result may replace the full-suite result.

## Confirmation boundary fixed before development outcomes

QuixBugs results remain development evidence. If the rule above is met, the
next confirmation target is the complete HumanEvalFix test set: all 164 bug
families in all six official languages (984 language-task instances), with no
task filtering. HumanEvalFix documentation-only and test-only prompts provide
the two orthogonal evidence views; final scoring uses the official tests.

The HumanEvalFix treatment and controls must be frozen before any confirmation
score is observed. A later Aider result must use the complete 225-task Polyglot
benchmark, not a 20-task or language-selected subset.

## Superseded evidence boundary

The prior Aider Java20 and Rust20 results remain useful development diagnostics
about session variance and failure-feedback repair. Java20 is 20 of 47 Java
tasks, and Rust20 is 20 of 30 Rust tasks; neither may serve as a complete-suite
headline result under this protocol.

## Post-D1 ceiling amendment

Recorded after the preassigned `D1` result and before any `D2`, `D3`, generic
adjudication, or TOV call. `D1` passed all 40/40 programs (276 executed tests,
0 failures, 2 official skips). Therefore the preregistered requirement that TOV
beat Plain by at least 8 programs is mathematically impossible on this suite.

The QuixBugs campaign stops for benchmark unsuitability rather than selecting
or excluding tasks. The 40/40 result is retained as the complete-suite outcome;
no TOV efficacy claim is made. Continuing candidate calls would consume budget
without identifying an incremental overlap effect. Development moves to the
complete 225-task Aider Polyglot benchmark, whose previous complete-track
inventory and subset diagnostics show non-ceiling behavior.
