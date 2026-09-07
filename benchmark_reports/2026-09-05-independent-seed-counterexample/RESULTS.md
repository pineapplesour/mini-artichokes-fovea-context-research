# Seed-matched counterexample overlap: completed Python, invalid C++ prefix

## Result

Explicit overlap guidance did not improve the completed Python34 comparison.
The planned 60-task primary estimand is unavailable because the C++ shared
fourth execution timed out. No missing C++ contrast is imputed as a tie, loss,
or success; no completed replacement is selected.

| Python34 final condition | Final candidate | Materialized system | Gain above common four-call floor |
|---|---:|---:|---:|
| Generic, fourth feedback supplied | 28 | 28 | +4 |
| Overlap, fourth feedback supplied | 27 | 27 | +3 |
| Generic, fourth feedback withheld | 23 | 25 | +1 |
| Overlap, fourth feedback withheld | 22 | 25 | +1 |

The shared fourth candidate scored 23/34; the union of its output and P/G/R
scored 24/34. All four complete systems were materialized and officially
re-evaluated, with outcome vectors matching their predicted candidate unions.
Within each feedback condition, seed hashes, evidence hashes, and all task IDs
were identical across policies. Every final ledger has all 34 original tasks.

With feedback, overlap has 0 rescues and 1 harm (`aider-python/dot-dsl`):
-1/34 = -2.94 percentage points; conditional two-sided exact McNemar p=1.
Without fourth feedback, the complete system vectors are identical, not merely
the totals. The descriptive policy-by-feedback interaction is -1 task. These
are single realized whole-track executions, not independent task replicates.

Withheld feedback means ONLY the fourth candidate's official outcome packet
is absent during fifth-candidate repair. Earlier P/G/R feedback remains, and
the terminal selector uses official outcomes for all five snapshots in every
arm. This is neither a tool-free condition nor fewer verification calls.

## Realized computation

Each system comprises five logical Codex executions, not five LLM messages.
The shared prefix reduces actual new executions and is counted in each system.

| Python condition | Final agent seconds | Final output tokens | Full-system agent seconds | Full-system output tokens |
|---|---:|---:|---:|---:|
| Generic feedback | 353.25 | 16,078 | 1,933.85 | 82,240 |
| Overlap feedback | 377.48 | 15,716 | 1,958.08 | 81,878 |
| Generic withheld | 278.02 | 11,225 | 1,858.63 | 77,387 |
| Overlap withheld | 266.01 | 11,591 | 1,846.61 | 77,753 |

All new calls use Luna/medium and a 480-second ceiling. Equal ceilings do not
mean equal tokens or time. Summed agent seconds exclude official evaluation
and orchestration; they are not end-to-end wall latency. Full input/cache and
reasoning usage is preserved in every `system-result.json`.

## C++ integrity boundary

`cex_v1_shared4` ended at 480.005 seconds with `agentExit=null`, timeout=true,
no forbidden file edits, and no completed agent turn. Its unfinished code was
still officially evaluated on all26 and passed19, but this is NOT a completed
candidate score eligible for the paired protocol. Each dependent cell stopped
before making a model call. The original artifacts remain intact.

The frozen advancement rule already disallows promotion because the completed
Python feedback contrast is negative; the full60 primary is also missing.
This closes this candidate experiment, not the continuing research objective.

## Next hypothesis, separately frozen

`experiment_protocols/2026-09-05-java47-independent-probe-overlap-v1.md` tests
independently authored executable specification probes followed by a matched
generic/overlap repair contrast on ALL47 Java tasks. It is a different,
result-informed development experiment. It does not repair this experiment's
missing C++ result or provide new-task confirmation.

## Evidence

- Frozen protocol: `experiment_protocols/2026-09-05-aider60-counterexample-overlap-v1.md`.
- Python roots: `runs/aider-python34-tov-v2-confirmation-20260902/arms/cex_v1_{generic_feedback,overlap_feedback,generic_blind,overlap_blind}/system-result.json`.
- C++ incomplete result: `runs/aider-cpp26-tov-v2-extension-20260902/arms/cex_v1_shared4/result.json`.
- No new committee review yet. Last valid final committee remains v25 MAC3/6.
