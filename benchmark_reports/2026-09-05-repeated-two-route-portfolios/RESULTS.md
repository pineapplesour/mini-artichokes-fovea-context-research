# Exhaustive two-route control check on the stored Python34 and C++26 repetitions

## Outcome

The earlier repeated verified-union result compared two final routes with one.
Using every possible distinct-call pair from the five saved overlap draws and
five saved semantic-free Direct draws gives a stronger, equal-call descriptive
control. The heterogeneous portfolio is only slightly above two Direct draws
on Python and slightly below them on C++. It is not the strongest mean
portfolio in either track.

| Complete track | Direct + Direct | Overlap + Direct | Overlap + Overlap | Mixed minus two Direct |
|---|---:|---:|---:|---:|
| Python34 | 23.00/34 | 23.52/34 | 24.10/34 | +0.52 (+1.53 pp) |
| C++26 | 18.50/26 | 18.36/26 | 18.80/26 | -0.14 (-0.54 pp) |
| Sum of the two track means | 41.50/60 | 41.88/60 | 42.90/60 | +0.38 (+0.63 pp) |

These are mean scores over finite combinations, not newly executed whole-track
session results. No added model call or fresh merged-workspace evaluation was
performed. The original repeated 210/300 result is not overturned; its
advantage over a single final route does not establish advantage over two
generic final routes. The present control makes that distinction quantitative.

## Complete enumeration and provenance

For each track, use exactly the five originally predeclared new draws of each
arm, excluding the motivating first call. Enumerate all 25 Overlap + Direct
pairs, all 10 unordered pairs of distinct Direct calls, and all 10 unordered
pairs of distinct Overlap calls. A system never reuses the same call twice.
No favorable pair, task, or session is selected for the headline mean.

Each derived system has the same historical three-call anchored prefix and
two final calls. Calls and original caps are matched; realized tokens, runtime
and exact monetary cost are not. The average recorded final-route agent times
are 943.13 / 936.03 / 928.93 seconds for Python Direct+Direct / mixed /
Overlap+Overlap, and 907.56 / 910.45 / 913.34 seconds for C++ respectively.
These exclude the shared prefix, verifier and host-side combination time and
must not be described as total system latency.

The parser reads actual per-task evaluator JSON lines, not the misleading
aggregate `parsed_passed` count of individual unit tests. Every draw has the
exact frozen 34- or 26-task inventory with Boolean outcomes. All 20 result
hashes match the original replication reports; the original per-session
scores and within-track shared seed hashes also match. Only evaluator-backed
complete-task passes enter the task-wise union.

The saved independent final calls are reused across the enumerated pairs.
Consequently, the 25/10/10 pair counts are NOT independent replications; they
must not be entered into a binomial test, a session sign test, or an ordinary
independent-sample confidence interval. This is post-hoc development analysis
on fixed known tracks, not a prospective population claim.

## Sensitivity and retained deviations

Removing each of the five original paired sessions in turn and enumerating
the remaining draws gives mixed-minus-two-Direct mean differences:

- Python: `[0.0625, 1.1667, 0.2083, 0.9375, 0.2500]` tasks.
- C++: `[-0.2500, -0.1458, -0.0625, -0.6042, 0.3750]` tasks.

These are leave-one-pair-out diagnostics, not confidence limits. Known
deviations from the original studies remain: Python ledger-order deviations
and C++ Overlap repetition 1's forbidden `a.out` file. They are neither removed
nor excused by this analysis. This study cannot retroactively satisfy the
original strict promotion gate.

## Research consequence

Do not promote heterogeneous whole-task union as a demonstrated large
overlap-specific improvement. Repeating the overlap route has a higher finite
mean here, so the data also do not isolate heterogeneity as the cause of the
small mixed-versus-Direct difference. The result does not justify a new
model campaign that merely adds another route.

The ongoing ClassEval-Pro study asks a distinct question: can actual source
fragments from contrasting executions form a better program under the same
saved model history and verifier cap? That full study remains pending; this
historical sensitivity does not prove its candidate will succeed.

Reproduce without model calls:

```bash
python -m tools.analyze_repeated_aider_portfolios --output benchmark_reports/2026-09-05-repeated-two-route-portfolios/analysis.json
```

The full pair matrices, original vectors, source hashes, costs and deviations
are retained in `analysis.json`. Main manuscript, supplement and review score
are unchanged by this diagnostic.
