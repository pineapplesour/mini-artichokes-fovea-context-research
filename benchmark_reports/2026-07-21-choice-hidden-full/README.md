# Choice-hidden open-response benchmark publication (2026-07-21)

## Project promotion target

As of 2026-07-24, this exact hash-bound 619-case run set is the project's
primary measurable gate. A candidate must beat the sealed no-DB Plain Codex
baseline of 393 pass, 218 fail, and 8 unresolved (`63.4895%`) by exceeding 393
passes on the same cases and scorer. Unresolved rate, latency, calls, tokens,
and cost remain mandatory reports and sustainability checks. The candidate
must also pass the anti-leakage and no-handcrafted-benchmark-routing rules. The
latest evaluated Universal v3 candidate scored
367 pass, 212 fail, and 40 unresolved (`59.2892%`) and is not promoted.

| Benchmark | Cases | Plain Codex pass | Fail | Unresolved |
| --- | ---: | ---: | ---: | ---: |
| Law (LEET 2026) | 16 | 11 | 5 | 0 |
| Korean medicine (Kuksiwon 81) | 37 | 26 | 11 | 0 |
| Christian Bible | 91 | 86 | 5 | 0 |
| Christian Provao 2012 | 85 | 54 | 31 | 0 |
| Islamic finance (CISI) | 86 | 39 | 39 | 8 |
| Islam AQA | 3 | 3 | 0 | 0 |
| Psychology (MIT + Sangmyung) | 301 | 174 | 127 | 0 |
| **Total** | **619** | **393** | **218** | **8** |

This is a concrete current milestone, not permission to specialize to these
cases. New model epochs and broader benchmarks still require a matched
same-model direct-Codex control.

This bundle publishes the benchmark definitions, semantic-rewrite staging data,
fresh Plain Codex runs, closed independent scoring records, policy audits, and
comparison reports used for the 619-case DB-vs-no-DB study.

## Benchmark revision

- The source registry contains 945 converted MCQ cases: 473 were initially
  eligible for option hiding and 472 required meaning-preserving rewriting.
- All 472 rewrite candidates were attempted exactly once per rewrite/judge call
  policy. Closed independent adjudication approved 146 and rejected 326.
- The staged registry therefore contains 619 ready cases and leaves 326 cases
  excluded from the final benchmark.

The original converted registry is in
`benchmarks/open_response_v2/evaluation_registry.open_response.json`. The
approved staging registry and its consolidated manifests are in
`runs/luna-pilot/semantic-rewrite-all-v1/combined/`.

## Fresh 619-case results

| Arm | Pass | Fail | Unresolved | Overall pass rate | Resolved-only pass rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Plain Codex, no DB | 393 | 218 | 8 | 63.49% | 64.32% |
| Plain Codex, optional read-only DB | 364 | 226 | 29 | 58.80% | 61.69% |

The DB arm was 4.68 percentage points lower on the fixed 619-case denominator
and used 16.07% more solver tokens. The model invoked the DB tool in 3 of 80
batches. Only one batch (8 psychology cases) was policy-valid; it changed no
case verdicts relative to no DB. Two Provao batches (13 cases) were policy
quarantined, and two zero-call psychology batches (16 cases) were response
quarantined. Accordingly, this run does not support enabling DB by default for
this benchmark.

## Published evidence

- `runs/luna-pilot/plain-no-db-full-v2/`: solver batches, case results, solver
  ledger, deterministic/semantic judgments, score ledger, and aggregate.
- `runs/luna-pilot/plain-db-only-full-v2/`: the matched optional-DB arm with the
  same evidence structure and DB policy traces.
- `runs/luna-pilot/semantic-rewrite-all-v1/`: the 472-case rewrite staging
  ledger plus consolidated approved manifests. Per-attempt directories that
  duplicate full manifests are intentionally omitted.
- `docs/research/plain_codex_db_vs_no_db_full_comparison_20260721.{json,md}`:
  the cross-arm comparison and audit summary.
- `tools/` and `tests/`: builders, runners, scorers, resource/policy checks, and
  regression coverage required to reproduce and validate the publication.

The earlier full benchmark evidence bundle remains at
`benchmark_reports/2026-07-17-full/`.

## Integrity and caveats

- Solver results were generated fresh; no prior solver answer was reused.
- Each solver batch received a single model call, and semantic scoring used
  closed independent consensus without semantic retries.
- Tool-use and resource audits reported zero audit errors.
- Eight no-DB cases and twenty-nine DB-arm cases remain unresolved and are not
  silently counted as failures in resolved-only accuracy.
- Private manifests and answer-bearing traces are committed for internal
  reproducibility; this repository must remain access-controlled.

## Publication verification

- All 26 staged regression modules passed: 426 tests passed with no failures
  (three dependency/runtime warnings).
- The final comparison audit reports zero errors, 619 linked results in each
  solver arm, closed judge traces, successful post-run dry-run validation, and
  successful artifact hash/link validation.
- Every principal hash in `SHA256SUMS` was rechecked immediately before commit.

See `SHA256SUMS` for the principal immutable inputs and outputs.
