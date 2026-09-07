# QuixBugs Python 40/40 complete-suite ceiling screen

## Purpose

This was a whole-benchmark suitability screen for the proposed
Try–Overlap–Verify coding mechanism. No task was selected or removed.

## Frozen benchmark

- Official repository: `jkoppel/QuixBugs`.
- Official commit: `4257f44b0ff1181dedaedee6a447e133219fcebf`.
- Denominator: all 40 Python programs corresponding to all 40 official
  `python_testcases/test_*.py` files.
- Correct implementations were absent from the isolated model workspace.
- Model: `gpt-5.6-luna`, medium reasoning, one complete-suite call.

## Result

The preassigned Plain draft `D1` repaired **40/40 programs**. The complete
post-call official run executed 276 tests with 0 failures and retained 2
official skips. The agent completed in 371.0 seconds.

This is a ceiling result, not evidence for overlap. Because TOV cannot improve
by the preregistered `+8/40` over a 40/40 baseline, no `D2`, `D3`, generic
adjudicator, or TOV call was made. The stopping decision uses the full-suite
score and does not filter failed or inconvenient tasks.

The scorer marked 50 generated `.pyc` files as out-of-scope changes. They are
Python bytecode emitted while executing tests; no test, JSON case, helper
source, or benchmark source file was edited. The scientific performance result
is the complete official test execution, while the candidate remains ineligible
for a clean-artifact claim because those generated files were preserved in its
receipt.

## Interpretation and next benchmark

QuixBugs is too easy for current Luna under this whole-suite repair condition.
It remains useful as an APR provenance check but cannot identify an incremental
overlap mechanism. The next development target is the **complete Aider Polyglot
225-task benchmark**, executed in its six complete language blocks and reported
only on the 225-task aggregate. Previous Java20 and Rust20 subset outcomes are
not promoted into that denominator.

## Evidence

- Protocol: `experiment_protocols/2026-09-02-quixbugs40-try-overlap-verify-development.md`.
- Frozen candidate result:
  `runs/quixbugs40-tov-development-20260902/d1/result.json`.
- Result SHA-256:
  `3c02dc35ad5866f49f62fa8d05c2ad00c7e0b63aed5736cf2b1cb4bfdcddfdf4`.
- Patch SHA-256:
  `2d66c2187d61b1155fd3dc214990e8f834e4fa007ebbcf74b12412aea0c8e6e5`.
