# Plain Codex DB vs no-DB full comparison (2026-07-21)

Both arms were rerun fresh on the same 619 ready cases, including the 146 newly approved semantic rewrites. Each arm used 80 sequential solver calls with `gpt-5.6-luna` at high reasoning effort. The no-DB arm was fully closed. The DB arm differed only by optional access to an allowlisted read-only subject database. Independent scoring used two closed judges per semantic batch and a third only on disagreement.

## Result

| Arm | Pass | Fail | Unresolved | Accuracy | Resolved-only accuracy | Solver tokens |
|---|---:|---:|---:|---:|---:|---:|
| No DB | 393 | 218 | 8 | 63.49% | 64.32% | 817,390 |
| Optional DB | 364 | 226 | 29 | 58.80% | 61.69% | 948,774 |
| DB minus no DB | -29 | +8 | +21 | -4.68 pp | -2.63 pp | +131,384 (+16.07%) |

The DB arm was lower in this run. At case level, 338 stayed pass, 175 stayed fail, 45 changed from pass to fail, and 24 changed from fail to pass. A further 29 no-DB-resolved cases became unresolved in the DB arm, while all eight no-DB-unresolved CISI cases became resolved (two pass, six fail).

## Actual DB use

The model attempted six DB calls in only 3/80 batches. It used no DB in 77/80 batches and in batches containing 598/619 cases.

- One policy-valid DB-using batch covered eight psychology cases. Relative to no-DB, all eight verdicts were unchanged: three pass-to-pass and five fail-to-fail.
- Two Provao batches covering 13 cases were quarantined for call-budget/query-limit violations and failed calls.
- Two zero-call psychology batches covering 16 cases were response-quarantined for an invalid answer value and mismatched answer IDs.

Thus this run contains no observed verdict gain from a policy-valid DB use. The larger arm-level delta also includes prompt/tool-schema exposure, ordinary model sampling variation, and quarantine behavior; it is not a clean estimate of retrieved-content causality from one run.

## Benchmark breakdown

| Benchmark | No DB | Optional DB | Delta |
|---|---:|---:|---:|
| Law | 68.75% | 62.50% | -6.25 pp |
| TCM | 70.27% | 64.86% | -5.41 pp |
| Bible100 | 94.51% | 94.51% | 0.00 pp |
| Provao | 63.53% | 54.12% | -9.41 pp |
| CISI | 45.35% | 46.51% | +1.16 pp |
| AQA | 100.00% | 100.00% | 0.00 pp |
| Psychology | 57.81% | 51.50% | -6.31 pp |

Provao's resolved-only DB accuracy was 63.89%, close to the no-DB 63.53%; its large overall decline is mainly the 13 policy-quarantined cases. CISI's apparent overall gain comes from resolving the no-DB arm's eight quarantined cases; among resolved cases its accuracy declined from 50.00% to 46.51%.

## Audit and recommendation

All 160 solver artifacts, 1,238 per-case result files, and 130 judge-group artifacts passed hash/link and tool-boundary audits. Solver web, command, skill, and non-database MCP event counts were zero. All 312 judge calls were closed and had zero tool events.

Keep the two benchmark arms separate and retain no-DB as the primary baseline. DB access should remain a targeted, gated ablation until repeated paired runs show a reliable gain. Before another DB run, enforce the two-call budget and query-length/token rules client-side so invalid calls cannot consume and quarantine a batch.

The machine-readable report is `docs/research/plain_codex_db_vs_no_db_full_comparison_20260721.json`.
